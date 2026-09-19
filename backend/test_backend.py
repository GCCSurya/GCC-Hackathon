import unittest
import json
import os
from unittest.mock import MagicMock, patch
from incident_store import IncidentStore
from multi_db_monitor import MultiDBMonitor
from rag_engine import RAGEngine
from agent import AgentEngine
from app import app, require_live_database


class TestLiveStartup(unittest.TestCase):
    def test_missing_configuration_stops_before_polling(self):
        monitor = MagicMock(pg_url=None, pghost=None)
        with patch("app.db_monitor", monitor):
            with self.assertRaisesRegex(SystemExit, "start-dbpulse"):
                require_live_database()
        monitor.poll_metrics.assert_not_called()

    def test_failed_or_partial_connection_stops_startup(self):
        for state in ("failed", "partial", "not_configured"):
            with self.subTest(state=state):
                monitor = MagicMock(pg_url=None, pghost="example.invalid")
                monitor.get_connection_status.return_value = {"state": state}
                with patch("app.db_monitor", monitor):
                    with self.assertRaisesRegex(SystemExit, "No demo server was started"):
                        require_live_database()
                monitor.poll_metrics.assert_called_once()

    def test_connected_fleet_allows_startup(self):
        monitor = MagicMock(pg_url=None, pghost="example.invalid")
        monitor.get_connection_status.return_value = {"state": "connected"}
        with patch("app.db_monitor", monitor), patch("app.incident_store.check_readiness", return_value={"state": "connected"}):
            require_live_database()
        monitor.poll_metrics.assert_called_once()

    def test_unready_incident_store_stops_startup(self):
        monitor = MagicMock(pg_url=None, pghost="example.invalid")
        monitor.get_connection_status.return_value = {"state": "connected"}
        with patch("app.db_monitor", monitor), patch("app.incident_store.check_readiness", return_value={"state": "error"}):
            with self.assertRaisesRegex(SystemExit, "Incident storage startup check failed"):
                require_live_database()

class TestDBPulseBackend(unittest.TestCase):
    def setUp(self):
        # Tests must never contact the shared database or paid LLM services.
        environment = patch.dict(os.environ, {}, clear=True)
        environment.start()
        self.addCleanup(environment.stop)
        self.incident_store = MagicMock()
        self.incident_store.get_next_incident_id.return_value = "INC-00458"
        self.incidents = []
        for target, value in (
            ("app.db_monitor", MultiDBMonitor()),
            ("app.agent_engine", AgentEngine(RAGEngine())),
            ("app.incident_store", self.incident_store),
            ("app.incidents_db", self.incidents),
        ):
            replacement = patch(target, value)
            replacement.start()
            self.addCleanup(replacement.stop)
        self.app = app.test_client()
        self.app.testing = True

    def test_db_monitor_scenarios(self):
        with patch.dict(os.environ, {"DBPULSE_ALLOW_DEMO": "1"}):
            monitor = MultiDBMonitor()
        monitor.set_scenario("LOCK_CONTENTION")
        metrics = monitor.poll_metrics()
        self.assertEqual(set(metrics), set(MultiDBMonitor.DATABASES))
        self.assertEqual(metrics["gcc_banking_core"]["status"], "AT_RISK")
        self.assertIsNotNone(metrics["gcc_banking_core"]["anomaly"])

    def test_rag_engine_retrieval(self):
        rag = RAGEngine()
        docs = rag.retrieve_relevant_docs("LOCK_CONTENTION public.orders")
        self.assertTrue(len(docs) > 0)
        self.assertIn("Lock", docs[0]["title"])

    def test_agent_diagnosis_fallback(self):
        rag = RAGEngine()
        agent = AgentEngine(rag)
        anomaly = {
            "type": "LOCK_CONTENTION",
            "database": "PNCPRD01",
            "title": "Lock contention on public.orders",
            "target_table": "public.orders"
        }
        diag = agent.diagnose_anomaly(anomaly, {})
        self.assertIn("root_cause", diag)
        self.assertTrue(len(diag["remediation_steps"]) > 0)
        self.assertEqual(diag["model"], "dbpulse rule-based runbook")
        self.assertTrue(diag["citations"].startswith("Runbook references:"))

    def test_azure_responses_api_diagnosis(self):
        model_response = MagicMock()
        model_response.output_text = '{"root_cause":"Live analysis","citations":"source: pg_stat_activity","remediation_steps":[]}'
        sdk_client = MagicMock()
        sdk_client.responses.create.return_value = model_response
        environment = {
            "AGENT_PROVIDER": "azure",
            "AZURE_FOUNDRY_ENDPOINT": "https://example.services.ai.azure.com/openai/v1/responses",
            "AZURE_FOUNDRY_KEY": "test-key",
            "AZURE_FOUNDRY_MODEL": "test-deployment",
        }
        with patch.dict(os.environ, environment, clear=True), patch("openai.OpenAI", return_value=sdk_client) as openai_client:
            agent = AgentEngine(RAGEngine())
            diagnosis = agent.diagnose_anomaly({"type": "LOCK_CONTENTION", "title": "test"}, {})
        self.assertIn("Azure AI Foundry: test-deployment", diagnosis["model"])
        openai_client.assert_called_once_with(
            base_url="https://example.services.ai.azure.com/openai/v1", api_key="test-key"
        )
        sdk_client.responses.create.assert_called_once()
        self.assertEqual(sdk_client.responses.create.call_args.kwargs["model"], "test-deployment")

    def test_azure_status_requires_model_and_key(self):
        with patch.dict(os.environ, {"AGENT_PROVIDER": "azure", "AZURE_FOUNDRY_ENDPOINT": "https://example/responses"}, clear=True):
            status = AgentEngine(RAGEngine()).get_status()
        self.assertFalse(status["configured"])
        self.assertEqual(status["missing"], ["authentication", "model"])

    def test_azure_responses_api_falls_back_to_chat_for_bad_request(self):
        token_response = MagicMock(status_code=200)
        token_response.json.return_value = {"access_token": "test-token"}
        responses_failure = MagicMock(status_code=400)
        responses_failure.json.return_value = {}
        chat_success = MagicMock(status_code=200)
        chat_success.json.return_value = {
            "choices": [{"message": {"content": '{"root_cause":"Live chat analysis","citations":"source: metrics","remediation_steps":[]}'}}]
        }
        environment = {
            "AGENT_PROVIDER": "azure",
            "AZURE_FOUNDRY_ENDPOINT": "https://example.services.ai.azure.com/openai/v1/responses",
            "AZURE_FOUNDRY_MODEL": "gpt-5.6-sol",
            "AZURE_FOUNDRY_USE_MANAGED_IDENTITY": "true",
        }
        with patch.dict(os.environ, environment, clear=True), patch(
            "requests.get", return_value=token_response
        ), patch("requests.post", side_effect=[responses_failure, chat_success]) as post:
            diagnosis = AgentEngine(RAGEngine()).diagnose_anomaly(
                {"type": "LOCK_CONTENTION", "title": "test"}, {}
            )
        self.assertIn("gpt-5.6-sol", diagnosis["model"])
        self.assertEqual(post.call_args_list[1].args[0], "https://example.services.ai.azure.com/openai/v1/chat/completions")

    def test_azure_status_reports_sanitized_provider_failure(self):
        sdk_error = RuntimeError("secret-key must not leak")
        sdk_error.status_code = 401
        sdk_error.body = None
        sdk_error.response = MagicMock()
        sdk_error.response.json.return_value = {
            "error": {
                "code": "unsupported_parameter",
                "message": "The input field is unsupported",
                "param": "input",
            },
            "request": {"authorization": "secret-key must not leak"},
        }
        sdk_client = MagicMock()
        sdk_client.responses.create.side_effect = sdk_error
        environment = {
            "AGENT_PROVIDER": "azure",
            "AZURE_FOUNDRY_ENDPOINT": "https://example.services.ai.azure.com/openai/v1/responses",
            "AZURE_FOUNDRY_KEY": "test-key",
            "AZURE_FOUNDRY_MODEL": "gpt-5.6-sol",
        }
        with patch.dict(os.environ, environment, clear=True), patch("openai.OpenAI", return_value=sdk_client):
            agent = AgentEngine(RAGEngine())
            diagnosis = agent.diagnose_anomaly({"type": "LOCK_CONTENTION", "title": "test"}, {})
        self.assertEqual(diagnosis["model"], "dbpulse rule-based runbook")
        self.assertEqual(
            agent.get_status()["last_error"],
            "Azure OpenAI SDK returned HTTP 401: unsupported_parameter: The input field is unsupported: input",
        )
        self.assertNotIn("secret-key", agent.get_status()["last_error"])

    def test_azure_responses_api_supports_managed_identity(self):
        token_response = MagicMock(status_code=200)
        token_response.json.return_value = {"access_token": "test-token"}
        model_response = MagicMock(status_code=200)
        model_response.json.return_value = {
            "output": [{"content": [{
                "type": "output_text",
                "text": '{"root_cause":"Managed identity analysis","citations":"source: metrics","remediation_steps":[]}',
            }]}],
        }
        environment = {
            "AGENT_PROVIDER": "azure",
            "AZURE_FOUNDRY_ENDPOINT": "https://example.services.ai.azure.com/openai/v1/responses",
            "AZURE_FOUNDRY_MODEL": "gpt-5.6-sol",
            "AZURE_FOUNDRY_USE_MANAGED_IDENTITY": "true",
        }
        with patch.dict(os.environ, environment, clear=True), patch("requests.get", return_value=token_response) as get, patch(
            "requests.post", return_value=model_response
        ) as post:
            agent = AgentEngine(RAGEngine())
            diagnosis = agent.diagnose_anomaly({"type": "LOCK_CONTENTION", "title": "test"}, {})
        self.assertIn("gpt-5.6-sol", diagnosis["model"])
        self.assertEqual(agent.get_status()["authentication"], "managed_identity")
        self.assertEqual(get.call_args.kwargs["headers"], {"Metadata": "true"})
        self.assertEqual(post.call_args.kwargs["headers"]["Authorization"], "Bearer test-token")

    def test_flask_routes(self):
        res_fleet = self.app.get("/api/fleet")
        self.assertEqual(res_fleet.status_code, 200)
        fleet_data = json.loads(res_fleet.data)
        self.assertEqual(len(fleet_data["fleet"]), 3)

        res_kpis = self.app.get("/api/kpis?db=gcc_banking_core")
        self.assertEqual(res_kpis.status_code, 200)

        res_anomaly = self.app.get("/api/anomaly")
        self.assertEqual(res_anomaly.status_code, 200)

        res_agent_status = self.app.get("/api/agent-status")
        self.assertEqual(res_agent_status.status_code, 200)

        res_diag = self.app.post("/api/diagnose")
        self.assertEqual(res_diag.status_code, 503)
        self.assertEqual(res_diag.json["error"], "Live fleet telemetry is unavailable")

        res_next = self.app.get("/api/next-incident-id")
        self.assertEqual(res_next.status_code, 200)
        next_id = json.loads(res_next.data).get("next_incident_id")
        self.assertTrue(next_id.startswith("INC-00"))

        res_inc = self.app.post("/api/raise-incident", json={
            "title": "Custom Test Incident",
            "severity": "CRITICAL",
            "database": "PNCPRD01"
        })
        self.assertEqual(res_inc.status_code, 200)
        inc_data = json.loads(res_inc.data)["incident"]
        self.assertEqual(inc_data["title"], "Custom Test Incident")
        self.assertEqual(inc_data["severity"], "CRITICAL")
        self.incident_store.save.assert_called_once_with(inc_data)

    def test_incident_persistence_failure_returns_service_unavailable(self):
        with patch("app.incident_store.save", side_effect=RuntimeError("database unavailable")):
            response = self.app.post("/api/raise-incident", json={"title": "Persistence test"})
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json["error"], "Incident could not be stored")
        self.assertEqual(len(self.incidents), 0)

    def test_reviewed_incident_fields_are_preserved(self):
        for steps in ([], [{"step": 1, "title": "Reviewed SQL", "sql": "SELECT 42;"}]):
            with self.subTest(steps=steps), patch("app.agent_engine.diagnose_anomaly") as diagnose:
                response = self.app.post("/api/raise-incident", json={
                    "title": "Reviewed incident", "database": "gcc_banking_core",
                    "root_cause": "", "remediation_steps": steps,
                })
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json["incident"]["remediation_steps"], steps)
                self.assertEqual(response.json["incident"]["root_cause"], "")
                self.assertEqual(self.incident_store.save.call_args.args[0]["remediation_steps"], steps)
                diagnose.assert_not_called()

    def test_invalid_remediation_is_rejected(self):
        for steps in (None, "SELECT 1", [{"sql": 123}]):
            with self.subTest(steps=steps):
                response = self.app.post("/api/raise-incident", json={"remediation_steps": steps})
                self.assertEqual(response.status_code, 400)
        self.incident_store.save.assert_not_called()

    def test_diagnosis_returns_its_snapshot_anomaly(self):
        anomaly = {"type": "LOCK_CONTENTION", "database": "gcc_reconciliation", "title": "Lock wait"}
        metrics = {"gcc_reconciliation": {"anomaly": anomaly}}
        with patch("app.db_monitor.poll_metrics", return_value=metrics) as poll, patch(
            "app.agent_engine.diagnose_anomaly", return_value={"model": "test"}
        ) as diagnose:
            response = self.app.post("/api/diagnose")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["anomaly"], anomaly)
        poll.assert_called_once()
        diagnose.assert_called_once_with(anomaly, metrics)

    def test_readiness_requires_fleet_and_storage(self):
        for fleet_state, storage_state, expected in (
            ("connected", "connected", 200), ("connected", "error", 503), ("error", "connected", 503),
        ):
            with self.subTest(fleet=fleet_state, storage=storage_state), patch(
                "app.db_monitor.get_connection_status", return_value={"state": fleet_state}
            ):
                self.incident_store.check_readiness.return_value = {"state": storage_state}
                response = self.app.get("/api/readiness")
                self.assertEqual(response.status_code, expected)

class TestDBConnectivity(unittest.TestCase):
    def setUp(self):
        environment = patch.dict(os.environ, {}, clear=True)
        environment.start()
        self.addCleanup(environment.stop)
        self.client = app.test_client()

    def configured_monitor(self):
        with patch.dict(os.environ, {"PGHOST": "example.invalid", "PGPASSWORD": "test-secret"}):
            return MultiDBMonitor()

    def test_unconfigured_health_is_not_success(self):
        monitor = MultiDBMonitor()
        with patch("app.db_monitor", monitor), patch("psycopg2.connect") as connect:
            response = self.client.get("/api/db-health")
        self.assertEqual(response.status_code, 503)
        self.assertFalse(response.json["success"])
        self.assertEqual(response.json["connection"]["state"], "not_configured")
        connect.assert_not_called()

    def test_live_telemetry_reports_mixed_and_preserves_zero(self):
        monitor = self.configured_monitor()
        connection = MagicMock()
        cursor = connection.cursor.return_value.__enter__.return_value
        cursor.fetchone.side_effect = [(0, 0, 0, 0, 12, 100), (99.7, 1024)] * 3
        with patch("psycopg2.connect", return_value=connection) as connect:
            metrics = monitor.poll_metrics()
        self.assertEqual(metrics["gcc_banking_core"]["active_sessions"], 0)
        status = monitor.get_connection_status()
        self.assertEqual(status["state"], "connected")
        self.assertEqual(status["data_source"], "live")
        self.assertIsNotNone(status["checked_at"])
        self.assertNotIn("test-secret", json.dumps(status))
        self.assertEqual(connect.call_count, 3)
        self.assertEqual({call.kwargs["dbname"] for call in connect.call_args_list}, set(MultiDBMonitor.DATABASES))
        self.assertEqual(connect.call_args.kwargs["connect_timeout"], 3)
        self.assertEqual(connection.set_session.call_count, 3)
        self.assertEqual(connection.close.call_count, 3)

    def test_live_blocked_sessions_create_actionable_anomaly(self):
        monitor = self.configured_monitor()
        connection = MagicMock()
        cursor = connection.cursor.return_value.__enter__.return_value
        cursor.fetchone.side_effect = [(3, 2, 1250, 4000, 24, 100), (98.4, 2048)] * 3
        with patch("psycopg2.connect", return_value=connection):
            metrics = monitor.poll_metrics()
        anomaly = metrics["gcc_banking_core"]["anomaly"]
        self.assertEqual(anomaly["type"], "LOCK_CONTENTION")
        self.assertEqual(anomaly["waiting_count"], 2)
        self.assertEqual(anomaly["database"], "gcc_banking_core")
        self.assertGreaterEqual(metrics["gcc_banking_core"]["risk_score"], 50)

    def test_live_query_duration_and_connection_pressure_are_data_driven(self):
        monitor = self.configured_monitor()
        connection = MagicMock()
        cursor = connection.cursor.return_value.__enter__.return_value
        cursor.fetchone.side_effect = [(4, 0, 2375.4, 9000, 30 + 30 + 25, 100), (99.2, 2048)] * 3
        with patch("psycopg2.connect", return_value=connection):
            metrics = monitor.poll_metrics()
        banking = metrics["gcc_banking_core"]
        self.assertEqual(banking["avg_query_time_ms"], 2375.4)
        self.assertEqual(banking["connection_utilization_percent"], 85.0)
        self.assertEqual(banking["anomaly"]["type"], "POOL_EXHAUSTION")

    def test_live_long_running_query_creates_runaway_anomaly(self):
        monitor = self.configured_monitor()
        connection = MagicMock()
        cursor = connection.cursor.return_value.__enter__.return_value
        cursor.fetchone.side_effect = [(1, 0, 121000, 121000, 15, 100), (99.5, 2048)] * 3
        with patch("psycopg2.connect", return_value=connection):
            metrics = monitor.poll_metrics()
        self.assertEqual(metrics["gcc_banking_core"]["anomaly"]["type"], "RUNAWAY_QUERY")

    def test_health_success_requires_real_query_path(self):
        monitor = self.configured_monitor()
        connection = MagicMock()
        cursor = connection.cursor.return_value.__enter__.return_value
        cursor.fetchone.side_effect = [(2, 0, 120, 200, 15, 100), (99.5, 2048)] * 3
        with patch("app.db_monitor", monitor), patch("psycopg2.connect", return_value=connection):
            response = self.client.get("/api/db-health")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json["success"])
        self.assertEqual(cursor.execute.call_count, 6)

    def test_connection_failure_is_sanitized(self):
        monitor = self.configured_monitor()
        with patch("app.db_monitor", monitor), patch(
            "psycopg2.connect", side_effect=RuntimeError("password=test-secret")
        ), self.assertLogs("multi_db_monitor", level="WARNING") as logs:
            response = self.client.get("/api/db-health")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json["connection"]["state"], "error")
        self.assertEqual(response.json["connection"]["error_type"], "RuntimeError")
        self.assertNotIn("test-secret", response.get_data(as_text=True))
        self.assertNotIn("test-secret", " ".join(logs.output))

    def test_query_failure_closes_connection_and_falls_back(self):
        monitor = self.configured_monitor()
        connection = MagicMock()
        connection.cursor.return_value.__enter__.return_value.execute.side_effect = RuntimeError("query failed")
        with patch("psycopg2.connect", return_value=connection):
            metrics = monitor.poll_metrics()
        self.assertIn("gcc_banking_core", metrics)
        self.assertEqual(monitor.get_connection_status()["data_source"], "unavailable")
        self.assertIsNone(metrics["gcc_banking_core"]["risk_score"])
        self.assertIsNone(metrics["gcc_banking_core"]["anomaly"])
        self.assertEqual(connection.close.call_count, 3)

    def test_status_recovers_after_failure(self):
        monitor = self.configured_monitor()
        connection = MagicMock()
        cursor = connection.cursor.return_value.__enter__.return_value
        cursor.fetchone.side_effect = [(1, 0, 150, 150, 9, 100), (99.0, 1024)] * 3
        with patch("psycopg2.connect", side_effect=[RuntimeError("offline")] * 3 + [connection] * 3):
            monitor.poll_metrics()
            self.assertEqual(monitor.get_connection_status()["state"], "error")
            monitor.poll_metrics()
        self.assertEqual(monitor.get_connection_status()["state"], "connected")
        self.assertIsNone(monitor.get_connection_status()["error_type"])

    def test_kpis_include_demo_status(self):
        with patch("app.db_monitor", MultiDBMonitor()):
            response = self.client.get("/api/kpis")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["connection"]["state"], "not_configured")
        self.assertIsNone(response.json["kpis"]["active_sessions"])

    def test_live_mode_blocks_scenario_api_and_exposes_mode(self):
        with patch("app.db_monitor", MultiDBMonitor()):
            response = self.client.post("/api/trigger-anomaly", json={"scenario": "LOCK_CONTENTION"})
            fleet = self.client.get("/api/fleet").json
        self.assertEqual(response.status_code, 403)
        self.assertFalse(fleet["simulation_enabled"])
        self.assertEqual(fleet["active_scenario"], "HEALTHY")

    def test_unavailable_telemetry_is_not_diagnosed_as_healthy(self):
        with patch("app.db_monitor", MultiDBMonitor()), patch("app.agent_engine.diagnose_anomaly") as diagnose:
            response = self.client.post("/api/diagnose")
        self.assertEqual(response.status_code, 503)
        diagnose.assert_not_called()

    def test_explicit_demo_mode_allows_scenarios(self):
        with patch.dict(os.environ, {"DBPULSE_ALLOW_DEMO": "1"}):
            monitor = MultiDBMonitor()
        with patch("app.db_monitor", monitor):
            response = self.client.post("/api/trigger-anomaly", json={"scenario": "LOCK_CONTENTION"})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json["success"])

    def test_unknown_database_and_table_are_rejected(self):
        monitor = self.configured_monitor()
        with self.assertRaisesRegex(ValueError, "Unknown configured database"):
            monitor.get_inventory("postgres")
        with patch("app.db_monitor", monitor):
            response = self.client.get("/api/databases/postgres/tables")
        self.assertEqual(response.status_code, 404)

class TestIncidentStore(unittest.TestCase):
    def test_random_incident_id_is_checked_for_collision(self):
        store = IncidentStore()
        connection = MagicMock()
        cursor = connection.cursor.return_value.__enter__.return_value
        cursor.fetchone.side_effect = [(True,), (False,)]
        with patch.object(store, "_connect", return_value=connection), patch(
            "incident_store.secrets.token_hex", side_effect=["deadbeef", "1234abcd"]
        ):
            incident_id = store.get_next_incident_id()
        self.assertEqual(incident_id, "INC-1234ABCD")
        self.assertEqual(cursor.execute.call_count, 2)
        connection.close.assert_called_once()

if __name__ == "__main__":
    unittest.main()
