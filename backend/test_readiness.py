import os
import unittest
from unittest.mock import MagicMock, patch

from incident_store import IncidentStore
from multi_db_monitor import MultiDBMonitor


class TestClusterTelemetry(unittest.TestCase):
    def test_demo_opt_in_does_not_hide_failed_live_reads(self):
        with patch.dict(os.environ, {"PGHOST": "example.invalid", "DBPULSE_ALLOW_DEMO": "1"}, clear=True):
            monitor = MultiDBMonitor()
        monitor.set_scenario("LOCK_CONTENTION")
        with patch.object(monitor, "_connect", side_effect=RuntimeError("offline")):
            metrics = monitor.poll_metrics()
        from monitor_worker import log_heartbeat
        log_heartbeat(monitor, metrics)
        self.assertEqual(monitor.get_connection_status()["data_source"], "unavailable")
        for item in metrics.values():
            self.assertIsNone(item["risk_score"])
            self.assertIsNone(item["anomaly"])

    def test_live_mode_rejects_simulation_and_unconfigured_scores(self):
        with patch.dict(os.environ, {}, clear=True):
            monitor = MultiDBMonitor()
        self.assertFalse(monitor.set_scenario('LOCK_CONTENTION'))
        monitor.active_scenario = 'LOCK_CONTENTION'
        self.assertIsNone(monitor._scenario_anomaly('gcc_banking_core'))
        for metrics in monitor.poll_metrics().values():
            self.assertEqual(metrics['status'], 'UNAVAILABLE')
            self.assertIsNone(metrics['risk_score'])
            self.assertIsNone(metrics['active_sessions'])
            self.assertIsNone(metrics['anomaly'])

    def test_risk_follows_database_changes_and_recovery(self):
        with patch.dict(os.environ, {'PGHOST': 'example.invalid'}, clear=True):
            monitor = MultiDBMonitor()
        connection = MagicMock()
        cursor = connection.cursor.return_value.__enter__.return_value
        cursor.fetchone.side_effect = [
            (1, 0, 100, 100, 10, 100), (99, 1024),
            (3, 2, 1000, 4000, 10, 100), (99, 1024),
            (1, 0, 100, 100, 10, 100), (99, 1024),
        ]
        with patch.object(monitor, '_connect', return_value=connection):
            healthy = monitor._poll_database('gcc_banking_core')
            blocked = monitor._poll_database('gcc_banking_core')
            recovered = monitor._poll_database('gcc_banking_core')
        self.assertEqual(healthy['risk_score'], 0)
        self.assertEqual(blocked['risk_score'], 50)
        self.assertEqual(blocked['anomaly']['type'], 'LOCK_CONTENTION')
        self.assertEqual(recovered['risk_score'], 0)
        self.assertIsNone(recovered['anomaly'])

    def test_connections_spread_across_databases_trigger_pool_pressure(self):
        with patch.dict(os.environ, {}, clear=True):
            monitor = MultiDBMonitor()
        connection = MagicMock()
        cursor = connection.cursor.return_value.__enter__.return_value
        database_connections = [30, 30, 25]
        cursor.fetchone.side_effect = [
            (2, 0, 125, 250, sum(database_connections), 100), (99, 1024)
        ]
        with patch.object(monitor, '_connect', return_value=connection):
            metrics = monitor._poll_database('gcc_banking_core')
        query = ' '.join(cursor.execute.call_args_list[0].args[0].split())
        self.assertIn(
            "(SELECT count(*) FROM pg_stat_activity WHERE backend_type = 'client backend')",
            query,
        )
        self.assertIn('WHERE datname = current_database() AND pid <> pg_backend_pid()', query)
        self.assertIn("FILTER (WHERE state = 'active')", query)
        self.assertIn("wait_event_type = 'Lock' OR cardinality(pg_blocking_pids(pid)) > 0", query)
        self.assertIn("current_setting('max_connections')::integer", query)
        self.assertEqual(metrics['connection_utilization_percent'], 85)
        self.assertEqual(metrics['anomaly']['type'], 'POOL_EXHAUSTION')
        self.assertEqual(metrics['risk_score'], 38)
        self.assertEqual(metrics['active_sessions'], 2)
        self.assertEqual(metrics['blocked_sessions'], 0)
        self.assertEqual(metrics['avg_query_time_ms'], 125)
        connection.close.assert_called_once()

    def test_telemetry_connection_is_readonly_and_bounded(self):
        with patch.dict(os.environ, {'PGHOST': 'example.invalid'}, clear=True):
            monitor = MultiDBMonitor()
        with patch('psycopg2.connect') as connect:
            connection = monitor._connect('gcc_banking_core')
        self.assertEqual(connect.call_args.kwargs['connect_timeout'], 3)
        self.assertEqual(connect.call_args.kwargs['options'], '-c statement_timeout=5000')
        connection.set_session.assert_called_once_with(readonly=True)


class TestIncidentReadiness(unittest.TestCase):
    def setUp(self):
        with patch.dict(os.environ, {}, clear=True):
            self.store = IncidentStore()
        self.connection = MagicMock()
        self.cursor = self.connection.cursor.return_value.__enter__.return_value
        self.cursor.fetchone.return_value = (1234, True)
        self.columns = [
            (name, 'varchar', True, False, '', '', None, True, True)
            for name in ('incident_id', 'severity', 'title', 'affected_database',
                         'category', 'assigned_to', 'raised_by', 'root_cause', 'notes')
        ] + [
            ('remediation_steps', 'jsonb', True, True, '', '', None, True, True),
            ('status', 'varchar', True, True, '', '', None, True, True),
            ('created_at', 'timestamptz', True, True, '', '', None, True, True),
        ]
        self.cursor.fetchall.return_value = self.columns
        replacement = patch.object(self.store, '_connect', return_value=self.connection)
        self.connect = replacement.start()
        self.addCleanup(replacement.stop)

    def check(self, expected_state):
        result = self.store.check_readiness()
        self.assertEqual(result, {
            'state': expected_state,
            'database': 'test',
            'message': 'Incident storage is ready.' if expected_state == 'connected'
                       else 'Incident storage is unavailable or incompatible.',
        })
        self.connection.close.assert_called_once()
        self.connection.commit.assert_not_called()
        self.connection.rollback.assert_not_called()
        for call in self.cursor.execute.call_args_list:
            query = call.args[0].strip().upper()
            self.assertTrue(query.startswith('SELECT '))
            self.assertNotIn('NEXTVAL(', query)
            self.assertNotIn('SETVAL(', query)
        return result

    def test_valid_schema_is_readonly_and_checks_column_privileges(self):
        self.check('connected')
        self.connection.set_session.assert_called_once_with(readonly=True)
        query = self.cursor.execute.call_args_list[1].args[0]
        self.assertIn("has_column_privilege(attribute.attrelid, attribute.attnum, 'INSERT')", query)
        self.assertIn("has_column_privilege(attribute.attrelid, attribute.attnum, 'SELECT')", query)
        self.assertEqual(self.cursor.execute.call_args_list[1].args[1], (1234,))
        self.assertEqual(self.cursor.execute.call_count, 2)

    def test_connection_timeout_is_bounded(self):
        with patch.dict(os.environ, {'PGHOST': 'example.invalid'}, clear=True):
            store = IncidentStore()
        with patch('psycopg2.connect') as connect:
            store._connect()
        self.assertEqual(connect.call_args.kwargs['connect_timeout'], 3)
        self.assertEqual(connect.call_args.kwargs['options'], '-c statement_timeout=5000')

    def test_missing_table(self):
        self.cursor.fetchone.return_value = None
        self.check('error')

    def test_missing_schema_usage(self):
        self.cursor.fetchone.return_value = (1234, False)
        self.check('error')

    def test_missing_expected_column(self):
        self.cursor.fetchall.return_value = self.columns[:-1]
        self.check('error')

    def test_missing_insert_privilege(self):
        self.columns[1] = (*self.columns[1][:7], False, True)
        self.check('error')

    def test_missing_select_privilege(self):
        self.columns[0] = (*self.columns[0][:8], False)
        self.check('error')

    def test_unneeded_column_privileges_are_not_required(self):
        self.cursor.fetchall.return_value = [
            (*column[:7], column[0] not in {'status', 'created_at'}, column[0] == 'incident_id')
            for column in self.columns
        ]
        self.check('connected')

    def test_text_incident_id_is_supported_without_sequence(self):
        self.columns[0] = ('incident_id', 'text', *self.columns[0][2:])
        self.check('connected')
        self.assertEqual(self.cursor.execute.call_count, 2)

    def test_uuid_incident_id_cannot_accept_generated_incident_ids(self):
        self.columns[0] = ('incident_id', 'uuid', *self.columns[0][2:])
        self.check('error')

    def test_uuid_surrogate_id_with_default_needs_no_sequence(self):
        self.columns.append(('id', 'uuid', True, True, '', '', None, False, False))
        self.check('connected')
        self.assertEqual(self.cursor.execute.call_count, 2)

    def test_missing_default_for_omitted_required_column(self):
        self.columns[-1] = ('created_at', 'timestamptz', True, False, '', '', None, True, True)
        self.check('error')

    def test_extra_required_column_without_default(self):
        self.columns.append(('id', 'uuid', True, False, '', '', None, False, False))
        self.check('error')

    def test_generated_insert_column_is_incompatible(self):
        self.columns[1] = ('severity', 'text', True, True, '', 's', None, True, True)
        self.check('error')

    def test_serial_surrogate_checks_nextval_privilege_without_consuming_value(self):
        self.columns.append(('id', 'int8', True, True, '', '', 'public.incidents_id_seq', False, False))
        self.cursor.fetchone.side_effect = [(1234, True), (True,)]
        self.check('connected')
        self.cursor.execute.assert_called_with(
            "SELECT has_sequence_privilege(%s, 'USAGE,UPDATE')", ('public.incidents_id_seq',)
        )

    def test_missing_serial_sequence_privilege(self):
        self.columns.append(('id', 'int8', True, True, '', '', 'public.incidents_id_seq', False, False))
        self.cursor.fetchone.side_effect = [(1234, True), (False,)]
        self.check('error')

    def test_identity_surrogate_does_not_require_sequence_privileges(self):
        self.columns.append(('id', 'int8', True, False, 'a', '', 'public.incidents_id_seq', False, False))
        self.check('connected')
        self.assertEqual(self.cursor.execute.call_count, 2)

    def test_connection_error_is_sanitized(self):
        self.connect.side_effect = RuntimeError('secret connection details')
        result = self.store.check_readiness()
        self.assertEqual(result['state'], 'error')
        self.assertNotIn('secret', str(result))
        self.connection.close.assert_not_called()

    def test_query_error_is_sanitized_and_connection_closed(self):
        self.cursor.execute.side_effect = RuntimeError('secret query details')
        self.check('error')

    def test_session_setup_error_closes_connection(self):
        self.connection.set_session.side_effect = RuntimeError('secret session details')
        self.check('error')

    def test_close_error_is_sanitized(self):
        self.connection.close.side_effect = RuntimeError('secret close details')
        self.check('error')


if __name__ == '__main__':
    unittest.main()