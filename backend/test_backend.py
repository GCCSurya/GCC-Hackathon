import unittest
import json
from db_monitor import DBMonitor
from rag_engine import RAGEngine
from agent import AgentEngine
from app import app

class TestDBPulseBackend(unittest.TestCase):
    def setUp(self):
        self.app = app.test_client()
        self.app.testing = True

    def test_db_monitor_scenarios(self):
        monitor = DBMonitor()
        monitor.set_scenario("LOCK_CONTENTION")
        metrics = monitor.poll_metrics()
        self.assertIn("PNCPRD01", metrics)
        self.assertEqual(metrics["PNCPRD01"]["status"], "AT_RISK")
        self.assertIsNotNone(metrics["PNCPRD01"]["anomaly"])

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

    def test_flask_routes(self):
        res_fleet = self.app.get("/api/fleet")
        self.assertEqual(res_fleet.status_code, 200)
        fleet_data = json.loads(res_fleet.data)
        self.assertEqual(len(fleet_data["fleet"]), 3)

        res_kpis = self.app.get("/api/kpis?db=PNCPRD01")
        self.assertEqual(res_kpis.status_code, 200)

        res_anomaly = self.app.get("/api/anomaly")
        self.assertEqual(res_anomaly.status_code, 200)

        res_diag = self.app.post("/api/diagnose")
        self.assertEqual(res_diag.status_code, 200)

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

if __name__ == "__main__":
    unittest.main()
