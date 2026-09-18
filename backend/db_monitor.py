import os
import time
import random
import logging
from datetime import datetime, timezone

logger = logging.getLogger("db_monitor")

class DBMonitor:
    def __init__(self):
        self.pg_url = os.getenv("POSTGRES_URL") or os.getenv("DATABASE_URL")
        # Azure Postgres parameters fallback
        self.pghost = os.getenv("PGHOST")
        self.pguser = os.getenv("PGUSER")
        self.pgpassword = os.getenv("PGPASSWORD")
        self.pgdatabase = os.getenv("PGDATABASE", "postgres")
        self.pgport = os.getenv("PGPORT", "5432")
        self.pgsslmode = os.getenv("PGSSLMODE", "require")
        self.connection_status = {
            "state": "unchecked" if self.pg_url or self.pghost else "not_configured",
            "data_source": "demo",
            "checked_at": None,
            "message": "Connection not checked yet." if self.pg_url or self.pghost else
                       "No PostgreSQL configuration in this backend process. Showing demo data.",
            "error_type": None,
        }
        
        self.active_scenario = "LOCK_CONTENTION"  # Default scenario for demo
        self.last_poll_time = time.time()
        
    def set_scenario(self, scenario_name):
        valid = ["LOCK_CONTENTION", "POOL_EXHAUSTION", "RUNAWAY_QUERY", "HEALTHY"]
        if scenario_name in valid:
            self.active_scenario = scenario_name
            logger.info(f"DB Monitor scenario changed to: {scenario_name}")
            return True
        return False

    def get_connection_status(self):
        """Return credential-free status of the latest telemetry attempt."""
        return dict(self.connection_status)

    def poll_metrics(self):
        self.last_poll_time = time.time()
        self.connection_status["checked_at"] = datetime.now(timezone.utc).isoformat()
        
        # Try real PostgreSQL if configured
        if self.pg_url or self.pghost:
            conn = None
            try:
                import psycopg2
                if self.pg_url:
                    conn = psycopg2.connect(self.pg_url, connect_timeout=3, options="-c statement_timeout=5000")
                else:
                    conn = psycopg2.connect(
                        host=self.pghost,
                        user=self.pguser,
                        password=self.pgpassword,
                        dbname=self.pgdatabase,
                        port=self.pgport,
                        sslmode=self.pgsslmode,
                        connect_timeout=3,
                        options="-c statement_timeout=5000"
                    )
                conn.set_session(readonly=True)
                cursor = conn.cursor()
                
                # 1. Query active & blocked sessions on current database (modern Postgres compatible)
                cursor.execute("""
                    SELECT 
                        count(*) as total_active,
                        count(*) FILTER (WHERE wait_event_type = 'Lock' OR cardinality(pg_blocking_pids(pid)) > 0) as blocked
                    FROM pg_stat_activity 
                    WHERE state = 'active' AND datname = current_database();
                """)
                row = cursor.fetchone()
                active = row[0] if row and row[0] is not None else 0
                blocked = row[1] if row and row[1] is not None else 0
                
                # Query blocking details if blocked sessions exist
                blocking_pid = None
                wait_event = "Lock:tuple"
                max_duration = 184
                if blocked > 0:
                    cursor.execute("""
                        SELECT 
                            pid, 
                            pg_blocking_pids(pid) AS blocked_by, 
                            wait_event_type, 
                            wait_event, 
                            extract(epoch from (now() - query_start)) as duration
                        FROM pg_stat_activity 
                        WHERE (wait_event_type = 'Lock' OR cardinality(pg_blocking_pids(pid)) > 0)
                          AND datname = current_database()
                        LIMIT 1;
                    """)
                    block_row = cursor.fetchone()
                    if block_row:
                        if block_row[1] and len(block_row[1]) > 0:
                            blocking_pid = block_row[1][0]
                        wait_event = f"{block_row[2]}:{block_row[3]}" if block_row[2] and block_row[3] else "Lock:tuple"
                        if block_row[4]:
                            max_duration = int(block_row[4])

                # 2. Query cache hit ratio from pg_stat_database using blks_hit / blks_read
                cursor.execute("""
                    SELECT 
                        sum(blks_hit)::float / nullif(sum(blks_hit) + sum(blks_read), 0) * 100 as cache_hit_ratio
                    FROM pg_stat_database
                    WHERE datname = current_database()
                    GROUP BY datname;
                """)
                db_row = cursor.fetchone()
                cache_hit = db_row[0] if db_row and db_row[0] is not None else 99.4
                
                cursor.close()
                
                # Determine PNCPRD01 anomaly & status based on live telemetry and active scenario
                if blocked > 0:
                    pnc_status = "AT_RISK"
                    pnc_risk = 88
                    pnc_desc = "Primary cluster · Lock contention detected"
                    pnc_avg_query = 840
                    pnc_anomaly = {
                        "type": "LOCK_CONTENTION",
                        "database": "PNCPRD01",
                        "title": f"Lock contention on public.orders (PID {blocking_pid or 48219} holding exclusive tuple lock)",
                        "target_table": "public.orders",
                        "blocking_pid": blocking_pid or 48219,
                        "wait_event": wait_event,
                        "waiting_count": blocked,
                        "duration_sec": max_duration
                    }
                elif self.active_scenario == "POOL_EXHAUSTION":
                    pnc_status = "AT_RISK"
                    pnc_risk = 92
                    pnc_desc = "Primary cluster · Connection pool exhaustion"
                    pnc_avg_query = 1420
                    pnc_anomaly = {
                        "type": "POOL_EXHAUSTION",
                        "database": "PNCPRD01",
                        "title": "Max connections reached (98/100 active connections in ClientRead wait)",
                        "target_table": "global_pool",
                        "blocking_pid": None,
                        "wait_event": "ClientRead",
                        "waiting_count": 24,
                        "duration_sec": 95
                    }
                elif self.active_scenario == "RUNAWAY_QUERY":
                    pnc_status = "AT_RISK"
                    pnc_risk = 78
                    pnc_desc = "Primary cluster · Runaway unindexed sequential scan"
                    pnc_avg_query = 2100
                    pnc_anomaly = {
                        "type": "RUNAWAY_QUERY",
                        "database": "PNCPRD01",
                        "title": "Runaway query PID 31092 scanning 42M rows without index on audit_logs",
                        "target_table": "public.audit_logs",
                        "blocking_pid": 31092,
                        "wait_event": "DataFileRead",
                        "waiting_count": 0,
                        "duration_sec": 412
                    }
                elif self.active_scenario == "LOCK_CONTENTION":
                    pnc_status = "AT_RISK"
                    pnc_risk = 88
                    pnc_desc = "Primary cluster · Lock contention detected"
                    pnc_avg_query = 840
                    pnc_anomaly = {
                        "type": "LOCK_CONTENTION",
                        "database": "PNCPRD01",
                        "title": "Lock contention on public.orders (PID 48219 holding exclusive tuple lock)",
                        "target_table": "public.orders",
                        "blocking_pid": 48219,
                        "wait_event": "Lock:tuple",
                        "waiting_count": 4,
                        "duration_sec": 184
                    }
                else:
                    pnc_status = "HEALTHY"
                    pnc_risk = 10
                    pnc_desc = "Primary cluster · Healthy"
                    pnc_avg_query = 14
                    pnc_anomaly = None

                logger.info(f"Polled live PostgreSQL (PNCPRD01): active={active}, blocked={blocked}, cache_hit={cache_hit:.1f}%")
                self.connection_status.update(
                    state="connected",
                    data_source="mixed",
                    error_type=None,
                    message="PostgreSQL telemetry queries succeeded. PNCPRD01 uses live session counts and available cache statistics; demo scenarios, peer databases and other values remain simulated.",
                )
                return {
                    "PNCPRD01": {
                        "status": pnc_status,
                        "risk_score": pnc_risk,
                        "status_desc": pnc_desc,
                        "active_sessions": active,
                        "blocked_sessions": blocked,
                        "cache_hit_ratio": round(float(cache_hit), 1),
                        "avg_query_time_ms": pnc_avg_query,
                        "anomaly": pnc_anomaly
                    },
                    "RECON_DB": {
                        "status": "HEALTHY",
                        "risk_score": 12,
                        "status_desc": "Reconciliation service · Healthy",
                        "active_sessions": 14,
                        "blocked_sessions": 0,
                        "cache_hit_ratio": 99.8,
                        "avg_query_time_ms": 18,
                        "anomaly": None
                    },
                    "MBL_STG": {
                        "status": "HEALTHY",
                        "risk_score": 8,
                        "status_desc": "Mobile staging · Healthy",
                        "active_sessions": 6,
                        "blocked_sessions": 0,
                        "cache_hit_ratio": 99.9,
                        "avg_query_time_ms": 12,
                        "anomaly": None
                    }
                }
            except Exception as e:
                # Raw driver errors can contain connection strings or credentials.
                error_type = type(e).__name__
                logger.warning("PostgreSQL telemetry failed (%s); using demo data", error_type)
                self.connection_status.update(
                    state="error",
                    data_source="demo",
                    error_type=error_type,
                    message="PostgreSQL connection or telemetry query failed. Showing demo data; check credentials, network access and monitoring permissions.",
                )
            finally:
                if conn is not None:
                    conn.close()
        
        # Synthetic simulation engine fallback
        return self._get_synthetic_metrics()

    def _get_synthetic_metrics(self):
        if self.active_scenario == "LOCK_CONTENTION":
            return {
                "PNCPRD01": {
                    "status": "AT_RISK",
                    "risk_score": 88,
                    "status_desc": "Primary cluster · Lock contention detected",
                    "active_sessions": 42 + random.randint(-2, 2),
                    "blocked_sessions": 4,
                    "cache_hit_ratio": 99.4,
                    "avg_query_time_ms": 840 + random.randint(-30, 30),
                    "anomaly": {
                        "type": "LOCK_CONTENTION",
                        "database": "PNCPRD01",
                        "title": "Lock contention on public.orders (PID 48219 holding exclusive tuple lock)",
                        "target_table": "public.orders",
                        "blocking_pid": 48219,
                        "wait_event": "Lock:tuple",
                        "waiting_count": 4,
                        "duration_sec": 184
                    }
                },
                "RECON_DB": {
                    "status": "HEALTHY",
                    "risk_score": 12,
                    "status_desc": "Reconciliation service · Healthy",
                    "active_sessions": 14,
                    "blocked_sessions": 0,
                    "cache_hit_ratio": 99.8,
                    "avg_query_time_ms": 18,
                    "anomaly": None
                },
                "MBL_STG": {
                    "status": "HEALTHY",
                    "risk_score": 8,
                    "status_desc": "Mobile staging · Healthy",
                    "active_sessions": 6,
                    "blocked_sessions": 0,
                    "cache_hit_ratio": 99.9,
                    "avg_query_time_ms": 12,
                    "anomaly": None
                }
            }
        elif self.active_scenario == "POOL_EXHAUSTION":
            return {
                "PNCPRD01": {
                    "status": "AT_RISK",
                    "risk_score": 92,
                    "status_desc": "Primary cluster · Connection pool exhaustion",
                    "active_sessions": 98,
                    "blocked_sessions": 24,
                    "cache_hit_ratio": 96.2,
                    "avg_query_time_ms": 1420,
                    "anomaly": {
                        "type": "POOL_EXHAUSTION",
                        "database": "PNCPRD01",
                        "title": "Max connections reached (98/100 active connections in ClientRead wait)",
                        "target_table": "global_pool",
                        "blocking_pid": None,
                        "wait_event": "ClientRead",
                        "waiting_count": 24,
                        "duration_sec": 95
                    }
                },
                "RECON_DB": {
                    "status": "HEALTHY",
                    "risk_score": 14,
                    "status_desc": "Reconciliation service · Healthy",
                    "active_sessions": 16,
                    "blocked_sessions": 0,
                    "cache_hit_ratio": 99.7,
                    "avg_query_time_ms": 22,
                    "anomaly": None
                },
                "MBL_STG": {
                    "status": "HEALTHY",
                    "risk_score": 5,
                    "status_desc": "Mobile staging · Healthy",
                    "active_sessions": 8,
                    "blocked_sessions": 0,
                    "cache_hit_ratio": 99.9,
                    "avg_query_time_ms": 14,
                    "anomaly": None
                }
            }
        elif self.active_scenario == "RUNAWAY_QUERY":
            return {
                "PNCPRD01": {
                    "status": "AT_RISK",
                    "risk_score": 78,
                    "status_desc": "Primary cluster · Runaway unindexed sequential scan",
                    "active_sessions": 31,
                    "blocked_sessions": 0,
                    "cache_hit_ratio": 84.1,
                    "avg_query_time_ms": 2100,
                    "anomaly": {
                        "type": "RUNAWAY_QUERY",
                        "database": "PNCPRD01",
                        "title": "Runaway query PID 31092 scanning 42M rows without index on audit_logs",
                        "target_table": "public.audit_logs",
                        "blocking_pid": 31092,
                        "wait_event": "DataFileRead",
                        "waiting_count": 0,
                        "duration_sec": 412
                    }
                },
                "RECON_DB": {
                    "status": "HEALTHY",
                    "risk_score": 10,
                    "status_desc": "Reconciliation service · Healthy",
                    "active_sessions": 12,
                    "blocked_sessions": 0,
                    "cache_hit_ratio": 99.8,
                    "avg_query_time_ms": 16,
                    "anomaly": None
                },
                "MBL_STG": {
                    "status": "HEALTHY",
                    "risk_score": 6,
                    "status_desc": "Mobile staging · Healthy",
                    "active_sessions": 5,
                    "blocked_sessions": 0,
                    "cache_hit_ratio": 99.9,
                    "avg_query_time_ms": 11,
                    "anomaly": None
                }
            }
        else: # HEALTHY
            return {
                "PNCPRD01": {
                    "status": "HEALTHY",
                    "risk_score": 10,
                    "status_desc": "Primary cluster · Healthy",
                    "active_sessions": 12,
                    "blocked_sessions": 0,
                    "cache_hit_ratio": 99.8,
                    "avg_query_time_ms": 14,
                    "anomaly": None
                },
                "RECON_DB": {
                    "status": "HEALTHY",
                    "risk_score": 12,
                    "status_desc": "Reconciliation service · Healthy",
                    "active_sessions": 14,
                    "blocked_sessions": 0,
                    "cache_hit_ratio": 99.8,
                    "avg_query_time_ms": 18,
                    "anomaly": None
                },
                "MBL_STG": {
                    "status": "HEALTHY",
                    "risk_score": 8,
                    "status_desc": "Mobile staging · Healthy",
                    "active_sessions": 6,
                    "blocked_sessions": 0,
                    "cache_hit_ratio": 99.9,
                    "avg_query_time_ms": 12,
                    "anomaly": None
                }
            }

    def get_fleet_summary(self):
        metrics = self.poll_metrics()
        fleet = []
        for db_name, data in metrics.items():
            fleet.append({
                "name": db_name,
                "status": data["status"],
                "risk_score": data["risk_score"],
                "status_desc": data["status_desc"]
            })
        return fleet

    def get_active_anomaly(self):
        metrics = self.poll_metrics()
        for db_name, data in metrics.items():
            if data.get("anomaly"):
                return data["anomaly"]
        return None
