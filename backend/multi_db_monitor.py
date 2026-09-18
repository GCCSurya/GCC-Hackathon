import os
import time
import logging
from datetime import datetime, timezone

from psycopg2 import sql

logger = logging.getLogger("multi_db_monitor")


class MultiDBMonitor:
    DATABASES = {
        "gcc_banking_core": "Banking core",
        "gcc_reconciliation": "Reconciliation",
        "gcc_audit_service": "Audit service",
    }

    def __init__(self):
        self.pg_url = os.getenv("POSTGRES_URL") or os.getenv("DATABASE_URL")
        self.pghost = os.getenv("PGHOST")
        self.pguser = os.getenv("PGUSER")
        self.pgpassword = os.getenv("PGPASSWORD")
        self.pgport = os.getenv("PGPORT", "5432")
        self.pgsslmode = os.getenv("PGSSLMODE", "require")
        self.active_scenario = "LOCK_CONTENTION"
        self.last_poll_time = time.time()
        self._latest_metrics = {}
        configured = bool(self.pg_url or self.pghost)
        self.connection_status = {
            "state": "unchecked" if configured else "not_configured",
            "data_source": "demo",
            "checked_at": None,
            "message": "Connection not checked yet." if configured else "No PostgreSQL configuration in this backend process. Showing demo data.",
            "error_type": None,
        }

    def _connect(self, database):
        import psycopg2

        options = {"connect_timeout": 3, "options": "-c statement_timeout=5000"}
        if self.pg_url:
            connection = psycopg2.connect(self.pg_url, dbname=database, **options)
        else:
            connection = psycopg2.connect(
                host=self.pghost,
                user=self.pguser,
                password=self.pgpassword,
                dbname=database,
                port=self.pgport,
                sslmode=self.pgsslmode,
                **options,
            )
        connection.set_session(readonly=True)
        return connection

    def set_scenario(self, scenario_name):
        if scenario_name not in {"LOCK_CONTENTION", "POOL_EXHAUSTION", "RUNAWAY_QUERY", "HEALTHY"}:
            return False
        self.active_scenario = scenario_name
        return True

    def get_connection_status(self):
        return dict(self.connection_status)

    def _scenario_anomaly(self, database):
        if self.active_scenario == "HEALTHY":
            return None
        if self.active_scenario == "RUNAWAY_QUERY" and database == "gcc_audit_service":
            return {
                "type": "RUNAWAY_QUERY", "database": database,
                "title": "Simulated runaway scan on public.audit_logs",
                "target_table": "public.audit_logs", "blocking_pid": None,
                "wait_event": "DataFileRead", "waiting_count": 0, "duration_sec": 412,
            }
        if self.active_scenario == "POOL_EXHAUSTION" and database == "gcc_banking_core":
            return {
                "type": "POOL_EXHAUSTION", "database": database,
                "title": "Simulated connection pool exhaustion",
                "target_table": "connection_pool", "blocking_pid": None,
                "wait_event": "ClientRead", "waiting_count": 24, "duration_sec": 95,
            }
        if self.active_scenario == "LOCK_CONTENTION" and database == "gcc_banking_core":
            return {
                "type": "LOCK_CONTENTION", "database": database,
                "title": "Simulated lock contention on public.orders",
                "target_table": "public.orders", "blocking_pid": 48219,
                "wait_event": "Lock:tuple", "waiting_count": 4, "duration_sec": 184,
            }
        return None

    def _demo_metrics(self, database, error_type=None):
        anomaly = self._scenario_anomaly(database)
        return {
            "status": "AT_RISK" if anomaly or error_type else "HEALTHY",
            "risk_score": 88 if anomaly else (70 if error_type else 10),
            "status_desc": f"{self.DATABASES[database]} · " + ("Connection failed" if error_type else ("Simulated anomaly" if anomaly else "Demo healthy")),
            "active_sessions": 0,
            "blocked_sessions": anomaly.get("waiting_count", 0) if anomaly else 0,
            "cache_hit_ratio": 0,
            "avg_query_time_ms": 0,
            "size_bytes": 0,
            "data_source": "demo",
            "error_type": error_type,
            "anomaly": anomaly,
        }

    def _poll_database(self, database):
        connection = self._connect(database)
        try:
            with connection.cursor() as cursor:
                cursor.execute("""
                    SELECT count(*) FILTER (WHERE state = 'active'),
                           count(*) FILTER (WHERE wait_event_type = 'Lock' OR cardinality(pg_blocking_pids(pid)) > 0)
                    FROM pg_stat_activity WHERE datname = current_database()
                """)
                active, blocked = cursor.fetchone()
                cursor.execute("""
                    SELECT CASE WHEN blks_hit + blks_read = 0 THEN 100
                                ELSE blks_hit::float / (blks_hit + blks_read) * 100 END,
                           pg_database_size(current_database())
                    FROM pg_stat_database WHERE datname = current_database()
                """)
                cache_hit, size_bytes = cursor.fetchone()
            simulated = self._scenario_anomaly(database)
            status = "AT_RISK" if blocked or simulated else "HEALTHY"
            risk = 88 if blocked or simulated else 10
            description = "Live lock contention" if blocked else ("Simulated anomaly" if simulated else "Live telemetry healthy")
            return {
                "status": status,
                "risk_score": risk,
                "status_desc": f"{self.DATABASES[database]} · {description}",
                "active_sessions": active or 0,
                "blocked_sessions": blocked or 0,
                "cache_hit_ratio": round(float(cache_hit or 100), 1),
                "avg_query_time_ms": 0,
                "size_bytes": int(size_bytes or 0),
                "data_source": "live",
                "error_type": None,
                "anomaly": simulated,
            }
        finally:
            connection.close()

    def poll_metrics(self):
        self.last_poll_time = time.time()
        self.connection_status["checked_at"] = datetime.now(timezone.utc).isoformat()
        if not (self.pg_url or self.pghost):
            self._latest_metrics = {database: self._demo_metrics(database) for database in self.DATABASES}
            return self._latest_metrics

        metrics = {}
        failures = []
        for database in self.DATABASES:
            try:
                metrics[database] = self._poll_database(database)
            except Exception as error:
                error_type = type(error).__name__
                logger.warning("Telemetry failed for %s (%s)", database, error_type, exc_info=True)
                failures.append(database)
                metrics[database] = self._demo_metrics(database, error_type)

        connected = len(self.DATABASES) - len(failures)
        self.connection_status.update(
            state="connected" if not failures else "error",
            data_source="mixed" if failures else "live",
            error_type=metrics[failures[0]]["error_type"] if failures else None,
            message=f"Connected to {connected}/{len(self.DATABASES)} configured databases. "
                    + ("Some fleet entries use demo fallback." if failures else "Fleet health and table metadata are live; anomaly scenarios remain simulated."),
        )
        self._latest_metrics = metrics
        return metrics

    def get_fleet_summary(self):
        return [
            {"name": name, **{key: data[key] for key in ("status", "risk_score", "status_desc", "active_sessions", "blocked_sessions", "cache_hit_ratio", "size_bytes", "data_source", "error_type")}}
            for name, data in self.poll_metrics().items()
        ]

    def get_active_anomaly(self):
        metrics = self.poll_metrics()
        return next((data["anomaly"] for data in metrics.values() if data.get("anomaly")), None)

    def get_inventory(self, database):
        if database not in self.DATABASES:
            raise ValueError("Unknown configured database")
        connection = self._connect(database)
        try:
            with connection.cursor() as cursor:
                cursor.execute("""
                    SELECT table_name FROM information_schema.tables
                    WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
                    ORDER BY table_name
                """)
                tables = []
                for (table_name,) in cursor.fetchall():
                    cursor.execute(sql.SQL("SELECT count(*) FROM {}.{}").format(sql.Identifier("public"), sql.Identifier(table_name)))
                    tables.append({"schema": "public", "name": table_name, "row_count": cursor.fetchone()[0]})
                return tables
        finally:
            connection.close()

    def get_table_preview(self, database, table_name, limit=20):
        tables = {table["name"] for table in self.get_inventory(database)}
        if table_name not in tables:
            raise ValueError("Unknown table")
        connection = self._connect(database)
        try:
            with connection.cursor() as cursor:
                cursor.execute(sql.SQL("SELECT * FROM {}.{} LIMIT %s").format(sql.Identifier("public"), sql.Identifier(table_name)), (min(max(limit, 1), 50),))
                columns = [item.name for item in cursor.description]
                rows = [[str(value) if value is not None else None for value in row] for row in cursor.fetchall()]
                return {"columns": columns, "rows": rows}
        finally:
            connection.close()