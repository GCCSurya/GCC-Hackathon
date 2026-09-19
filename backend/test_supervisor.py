import os
import signal
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import monitor_worker
import run_dashboard


def fake_child(return_code=None):
    child = Mock()
    child.pid = 12345
    child.poll.return_value = return_code
    child.wait.return_value = 0
    return child


class SupervisorTests(unittest.TestCase):
    def test_launch_contract_and_unexpected_exit(self):
        for exited_index in (0, 1):
            for return_code in (0, 7):
                with self.subTest(exited_index=exited_index, return_code=return_code):
                    children = [fake_child(), fake_child()]
                    children[exited_index].poll.return_value = return_code
                    with patch.object(run_dashboard.subprocess, "Popen", side_effect=children) as launch:
                        with patch.object(run_dashboard.signal, "signal"):
                            self.assertEqual(run_dashboard.main(), 1)
                    self.assertEqual(launch.call_count, 2)
                    for call, script in zip(launch.call_args_list, ("app.py", "monitor_worker.py")):
                        backend = Path(run_dashboard.__file__).resolve().parent
                        self.assertEqual(call.args, ([sys.executable, "-u", str(backend / script)],))
                        self.assertEqual(call.kwargs, {"cwd": backend})
                    children[exited_index].terminate.assert_not_called()
                    children[1 - exited_index].terminate.assert_called_once()
                    for child in children:
                        child.wait.assert_called_once()

    def test_partial_launch_failure_cleans_up_first_child(self):
        child = fake_child()
        with patch.object(run_dashboard.subprocess, "Popen", side_effect=[child, OSError("redacted")]):
            with patch.object(run_dashboard.signal, "signal"):
                self.assertEqual(run_dashboard.main(), 1)
        child.terminate.assert_called_once()
        child.wait.assert_called_once()

    def test_first_launch_failure(self):
        with patch.object(run_dashboard.subprocess, "Popen", side_effect=OSError("redacted")) as launch:
            with patch.object(run_dashboard.signal, "signal"):
                self.assertEqual(run_dashboard.main(), 1)
        launch.assert_called_once()

    def test_ctrl_c_during_startup_tracks_child_before_cleanup(self):
        child = fake_child()
        handlers = {}

        def register(signum, handler):
            handlers[signum] = handler
            return signal.SIG_DFL

        def launch(*args, **kwargs):
            handlers[signal.SIGINT](signal.SIGINT, None)
            return child

        with patch.object(run_dashboard.signal, "signal", side_effect=register) as register_signal:
            with patch.object(run_dashboard.subprocess, "Popen", side_effect=launch) as start:
                self.assertEqual(run_dashboard.main(), 130)
        start.assert_called_once()
        child.terminate.assert_called_once()
        child.wait.assert_called_once()
        self.assertEqual(register_signal.call_count, 4)
        self.assertTrue(all(handler == signal.SIG_DFL for handler in handlers.values()))

    def test_repeated_ctrl_c_and_already_exited_children(self):
        children = [fake_child(), fake_child()]
        handlers = {}

        def register(signum, handler):
            handlers[signum] = handler
            return signal.SIG_DFL

        def interrupt():
            handlers[signal.SIGINT](signal.SIGINT, None)
            for child in children:
                child.poll.return_value = 130

        def wait(**kwargs):
            handlers[signal.SIGINT](signal.SIGINT, None)
            return 130

        children[0].wait.side_effect = wait
        with patch.object(run_dashboard.signal, "signal", side_effect=register):
            with patch.object(run_dashboard.subprocess, "Popen", side_effect=children):
                with patch.object(run_dashboard.time, "sleep", side_effect=lambda interval: interrupt()):
                    self.assertEqual(run_dashboard.main(), 130)
        for child in children:
            child.terminate.assert_not_called()
            child.wait.assert_called_once()

    def test_terminate_race_is_harmless(self):
        child = fake_child()
        child.poll.side_effect = [None, 130]
        child.terminate.side_effect = PermissionError()
        self.assertTrue(run_dashboard.stop_children([child]))
        child.wait.assert_called_once()

    def test_timeout_kills_and_reaps_owned_child(self):
        child = fake_child()
        child.wait.side_effect = [subprocess.TimeoutExpired("fixture", 5), 0]
        self.assertTrue(run_dashboard.stop_children([child]))
        child.kill.assert_called_once()
        self.assertEqual(child.wait.call_count, 2)

    def test_kill_race_is_harmless(self):
        child = fake_child()
        child.poll.side_effect = [None, 0]
        child.wait.side_effect = [subprocess.TimeoutExpired("fixture", 5), 0]
        child.kill.side_effect = ProcessLookupError()
        self.assertTrue(run_dashboard.stop_children([child]))
        self.assertEqual(child.wait.call_count, 2)

    def test_cleanup_failure_does_not_skip_sibling(self):
        child = fake_child()
        child.terminate.side_effect = PermissionError()
        child.wait.side_effect = subprocess.TimeoutExpired("fixture", 5)
        sibling = fake_child()
        self.assertFalse(run_dashboard.stop_children([child, sibling]))
        sibling.terminate.assert_called_once()
        sibling.wait.assert_called_once()

    def test_short_lived_fixture_is_reaped_without_touching_other_processes(self):
        child = subprocess.Popen([sys.executable, "-u", "-c", "raise SystemExit(0)"])
        try:
            child.wait(timeout=10)
            self.assertTrue(run_dashboard.stop_children([child]))
            self.assertEqual(child.returncode, 0)
        finally:
            if child.poll() is None:
                child.kill()
                child.wait(timeout=10)


class WorkerTests(unittest.TestCase):
    def setUp(self):
        environment = patch.dict(os.environ, {}, clear=True)
        environment.start()
        self.addCleanup(environment.stop)
        self.monitor = Mock()
        self.monitor.pg_url = None
        self.monitor.pghost = "fixture-host"
        self.monitor.get_connection_status.return_value = {
            "state": "connected", "data_source": "live", "error_type": None,
        }
        self.monitor.poll_metrics.return_value = {
            "fixture-db": {"data_source": "live", "error_type": None, "risk_score": 10, "anomaly": None},
        }

    def test_missing_configuration_fails_before_poll(self):
        self.monitor.pghost = None
        with self.assertRaisesRegex(RuntimeError, "not configured"):
            monitor_worker.require_live_database(self.monitor)
        self.monitor.poll_metrics.assert_not_called()

    def test_live_host_or_url_configuration_requires_successful_poll(self):
        for use_url in (False, True):
            with self.subTest(use_url=use_url):
                self.monitor.pg_url = "postgresql://fixture" if use_url else None
                self.monitor.pghost = None if use_url else "fixture-host"
                self.monitor.poll_metrics.reset_mock()
                monitor_worker.require_live_database(self.monitor)
                self.monitor.poll_metrics.assert_called_once_with()

    def test_failed_or_demo_connection_is_rejected(self):
        for state, source in (("error", "mixed"), ("unchecked", "demo"), ("connected", "mixed")):
            with self.subTest(state=state, source=source):
                self.monitor.get_connection_status.return_value.update(state=state, data_source=source)
                with self.assertRaisesRegex(RuntimeError, "fleet poll failed"):
                    monitor_worker.require_live_database(self.monitor)

    def test_empty_or_fallback_metrics_are_rejected(self):
        for metrics in ({}, {"fixture-db": {"data_source": "demo", "error_type": "OperationalError", "risk_score": 70}}):
            with self.subTest(metrics=metrics):
                self.monitor.poll_metrics.return_value = metrics
                with self.assertRaisesRegex(RuntimeError, "fleet poll failed"):
                    monitor_worker.require_live_database(self.monitor)

    def test_only_exact_demo_opt_in_bypasses_guard(self):
        self.monitor.pghost = None
        for setting in ("", "0", "true", "yes", "1"):
            with self.subTest(setting=setting), patch.dict(os.environ, {"DBPULSE_ALLOW_DEMO": setting}):
                if setting == "1":
                    monitor_worker.require_live_database(self.monitor)
                else:
                    with self.assertRaises(RuntimeError):
                        monitor_worker.require_live_database(self.monitor)
        self.monitor.poll_metrics.assert_not_called()

    def test_startup_poll_exception_is_fatal_and_redacted(self):
        self.monitor.poll_metrics.side_effect = RuntimeError("fixture-secret-not-for-logs")
        with patch.object(monitor_worker, "MultiDBMonitor", return_value=self.monitor):
            with patch.object(monitor_worker, "AgentEngine") as agent:
                with self.assertLogs("monitor_worker", level="ERROR") as logs:
                    self.assertEqual(monitor_worker.main(), 1)
        agent.assert_not_called()
        self.assertIn("startup refused", " ".join(logs.output))
        self.assertNotIn("fixture-secret-not-for-logs", " ".join(logs.output))

    def test_heartbeat_reports_connectivity_and_failures(self):
        self.monitor.get_connection_status.return_value.update(
            state="error", data_source="mixed", error_type="OperationalError",
        )
        self.monitor.poll_metrics.return_value["fixture-db"].update(
            data_source="demo", error_type="OperationalError",
        )
        agent = Mock()
        with self.assertLogs("monitor_worker", level="WARNING") as logs:
            self.assertEqual(monitor_worker.poll_once(self.monitor, agent, set()), set())
        output = " ".join(logs.output)
        for expected in ("connectivity=error", "source=mixed", "failures=1", "OperationalError"):
            self.assertIn(expected, output)
        agent.diagnose_anomaly.assert_not_called()

    def test_heartbeat_precedes_diagnosis_failure(self):
        self.monitor.poll_metrics.return_value["fixture-db"]["anomaly"] = {"type": "LOCK_CONTENTION"}
        agent = Mock()
        agent.diagnose_anomaly.side_effect = RuntimeError()
        with self.assertLogs("monitor_worker", level="INFO") as logs:
            with self.assertRaises(RuntimeError):
                monitor_worker.poll_once(self.monitor, agent, set())
        self.assertIn("connectivity=connected", " ".join(logs.output))

    def test_anomalies_are_diagnosed_once_until_cleared(self):
        metrics = self.monitor.poll_metrics.return_value
        metrics["fixture-db"]["anomaly"] = {"type": "LOCK_CONTENTION"}
        agent = Mock()
        agent.diagnose_anomaly.return_value = {"root_cause": "fixture diagnosis"}
        diagnosed = monitor_worker.poll_once(self.monitor, agent, set())
        self.assertEqual(diagnosed, {("fixture-db", "LOCK_CONTENTION")})
        monitor_worker.poll_once(self.monitor, agent, diagnosed)
        agent.diagnose_anomaly.assert_called_once()
        metrics["fixture-db"]["anomaly"] = None
        self.assertEqual(monitor_worker.poll_once(self.monitor, agent, diagnosed), set())

    def test_cycle_failure_is_visible_and_ctrl_c_stops_worker(self):
        self.monitor.poll_metrics.side_effect = [
            self.monitor.poll_metrics.return_value, RuntimeError("fixture-secret-not-for-logs"),
        ]
        with patch.object(monitor_worker, "MultiDBMonitor", return_value=self.monitor):
            with patch.object(monitor_worker, "AgentEngine"), patch.object(monitor_worker, "RAGEngine"):
                with patch.object(monitor_worker.time, "sleep", side_effect=KeyboardInterrupt):
                    with self.assertLogs("monitor_worker", level="INFO") as logs:
                        self.assertEqual(monitor_worker.main(), 0)
        output = " ".join(logs.output)
        self.assertIn("Monitoring cycle failed (RuntimeError)", output)
        self.assertIn("connectivity=connected", output)
        self.assertIn("log-only, no incident persistence", output)
        self.assertNotIn("fixture-secret-not-for-logs", output)


if __name__ == "__main__":
    unittest.main()