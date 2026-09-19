import logging
import os
import time

from agent import AgentEngine
from multi_db_monitor import MultiDBMonitor
from rag_engine import RAGEngine


logger = logging.getLogger("monitor_worker")


def log_heartbeat(monitor, metrics):
    connection = monitor.get_connection_status()
    failures = sum(bool(item.get("error_type")) for item in metrics.values())
    log = logger.warning if failures or connection["state"] == "error" else logger.info
    log(
        "Poll complete: connectivity=%s, source=%s, failures=%s, error_type=%s, "
        "databases=%s, anomalies=%s, max_risk=%s",
        connection["state"], connection["data_source"], failures, connection.get("error_type"),
        len(metrics), sum(bool(item.get("anomaly")) for item in metrics.values()),
        max((item["risk_score"] for item in metrics.values() if item.get("risk_score") is not None), default=None),
    )


def require_live_database(monitor):
    if os.getenv("DBPULSE_ALLOW_DEMO") == "1":
        logger.warning("Demo mode explicitly allowed; live database startup check skipped")
        return
    if not (monitor.pg_url or monitor.pghost):
        raise RuntimeError("PostgreSQL is not configured")
    metrics = monitor.poll_metrics()
    log_heartbeat(monitor, metrics)
    connection = monitor.get_connection_status()
    if (
        connection["state"] != "connected"
        or connection["data_source"] != "live"
        or not metrics
        or any(item.get("data_source") != "live" or item.get("error_type") for item in metrics.values())
    ):
        raise RuntimeError("Initial live PostgreSQL fleet poll failed")


def poll_once(monitor, agent, diagnosed):
    metrics = monitor.poll_metrics()
    log_heartbeat(monitor, metrics)
    current = set()
    for database, database_metrics in metrics.items():
        anomaly = database_metrics.get("anomaly")
        if not anomaly:
            continue
        signature = (database, anomaly["type"])
        current.add(signature)
        if signature not in diagnosed:
            diagnosis = agent.diagnose_anomaly(anomaly, metrics)
            logger.warning(
                "%s on %s (risk %s): %s",
                anomaly["type"], database, database_metrics["risk_score"], diagnosis["root_cause"],
            )
    return current


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        force=True,
    )
    try:
        interval = max(int(os.getenv("MONITOR_INTERVAL_SECONDS", "30")), 5)
        monitor = MultiDBMonitor()
        try:
            require_live_database(monitor)
        except Exception as error:
            logger.error(
                "Worker startup refused (%s): live PostgreSQL configuration and a successful "
                "fleet poll are required unless DBPULSE_ALLOW_DEMO=1",
                type(error).__name__,
            )
            return 1
        agent = AgentEngine(RAGEngine())
        diagnosed = set()
        logger.info(
            "Starting independent read-only monitor with a %s second interval; "
            "diagnoses are log-only, no incident persistence",
            interval,
        )
        while True:
            try:
                diagnosed = poll_once(monitor, agent, diagnosed)
            except Exception as error:
                connection = monitor.get_connection_status()
                logger.error(
                    "Monitoring cycle failed (%s): connectivity=%s, source=%s",
                    type(error).__name__, connection["state"], connection["data_source"],
                )
            time.sleep(interval)
    except KeyboardInterrupt:
        logger.info("Monitoring worker stopped")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())