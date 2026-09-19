import os
import time
import logging
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

from multi_db_monitor import MultiDBMonitor
from incident_store import IncidentStore
from rag_engine import RAGEngine
from agent import AgentEngine

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("app")

app = Flask(__name__, static_folder="../dist", static_url_path="")
CORS(app)

# Initialize modules
db_monitor = MultiDBMonitor()
incident_store = IncidentStore()
rag_engine = RAGEngine()
agent_engine = AgentEngine(rag_engine)

# In-memory timeline state
timeline_events = [
    {"timestamp": time.strftime("%H:%M:%S"), "event": "Fleet monitoring initialized", "type": "system"}
]
incidents_db = []

@app.route("/healthz", methods=["GET"])
def get_liveness():
    return jsonify({"status": "ok"})

@app.route("/api/fleet", methods=["GET"])
def get_fleet():
    summary = db_monitor.get_fleet_summary()
    return jsonify({
        "success": True,
        "fleet": summary,
        "simulation_enabled": db_monitor.simulation_enabled,
        "active_scenario": db_monitor.active_scenario,
        "last_polled_sec_ago": int(time.time() - db_monitor.last_poll_time)
    })

@app.route("/api/db-health", methods=["GET"])
def get_db_health():
    # Exercise the actual monitoring queries, not the synthetic fallback alone.
    db_monitor.poll_metrics()
    status = db_monitor.get_connection_status()
    connected = status["state"] == "connected"
    return jsonify({"success": connected, "connection": status}), 200 if connected else 503

@app.route("/api/kpis", methods=["GET"])
def get_kpis():
    db_name = request.args.get("db", "gcc_banking_core")
    metrics = db_monitor.poll_metrics()
    if db_name not in metrics:
        return jsonify({"success": False, "error": "Unknown configured database"}), 404
    db_metrics = metrics[db_name]
    return jsonify({
        "success": True,
        "database": db_name,
        "connection": db_monitor.get_connection_status(),
        "kpis": {
            "active_sessions": db_metrics["active_sessions"],
            "blocked_sessions": db_metrics["blocked_sessions"],
            "cache_hit_ratio": db_metrics["cache_hit_ratio"],
            "avg_query_time_ms": db_metrics["avg_query_time_ms"]
        }
    })

@app.route("/api/databases/<database>/tables", methods=["GET"])
def get_database_tables(database):
    try:
        tables = db_monitor.get_inventory(database)
    except ValueError as error:
        return jsonify({"success": False, "error": str(error)}), 404
    except Exception as error:
        logger.warning("Table inventory failed for %s (%s)", database, type(error).__name__)
        return jsonify({"success": False, "error": "Table inventory query failed"}), 503
    return jsonify({"success": True, "database": database, "tables": tables})

@app.route("/api/databases/<database>/tables/<table>/rows", methods=["GET"])
def get_table_rows(database, table):
    try:
        preview = db_monitor.get_table_preview(database, table, request.args.get("limit", 20, type=int))
    except ValueError as error:
        return jsonify({"success": False, "error": str(error)}), 404
    except Exception as error:
        logger.warning("Table preview failed for %s.%s (%s)", database, table, type(error).__name__)
        return jsonify({"success": False, "error": "Table preview query failed"}), 503
    return jsonify({"success": True, "database": database, "table": table, **preview})

@app.route("/api/anomaly", methods=["GET"])
def get_anomaly():
    anomaly = db_monitor.get_active_anomaly()
    return jsonify({
        "success": True,
        "anomaly": anomaly
    })

@app.route("/api/agent-status", methods=["GET"])
def get_agent_status():
    return jsonify({"success": True, "agent": agent_engine.get_status()})

@app.route("/api/readiness", methods=["GET"])
def get_readiness():
    db_monitor.poll_metrics()
    connection = db_monitor.get_connection_status()
    storage = incident_store.check_readiness()
    ready = connection["state"] == "connected" and storage["state"] == "connected"
    return jsonify({"success": ready, "connection": connection, "incident_storage": storage}), 200 if ready else 503

@app.route("/api/diagnose", methods=["POST"])
def run_diagnosis():
    metrics = db_monitor.poll_metrics()
    if not metrics or any(data.get("data_source") == "unavailable" for data in metrics.values()):
        return jsonify({"success": False, "error": "Live fleet telemetry is unavailable"}), 503
    anomaly = next((data["anomaly"] for data in metrics.values() if data.get("anomaly")), None)
    diagnosis = agent_engine.diagnose_anomaly(anomaly, metrics)
    
    # Append timeline event
    now_str = time.strftime("%H:%M:%S")
    timeline_events.append({
        "timestamp": now_str,
        "event": f"{anomaly.get('database', 'gcc_banking_core') if anomaly else 'gcc_banking_core'} diagnosed by dbpulse ({diagnosis.get('model', 'Agent')})",
        "type": "diagnosis"
    })
    
    return jsonify({
        "success": True,
        "diagnosis": diagnosis,
        "anomaly": anomaly
    })

@app.route("/api/next-incident-id", methods=["GET"])
def get_next_incident_id():
    try:
        inc_id = incident_store.get_next_incident_id()
    except Exception as error:
        logger.warning("Next incident ID query failed (%s)", type(error).__name__)
        return jsonify({"success": False, "error": "Incident database query failed"}), 503
    return jsonify({
        "success": True,
        "next_incident_id": inc_id
    })

@app.route("/api/raise-incident", methods=["POST"])
def raise_incident():
    data = request.get_json(silent=True) or {}
    if not isinstance(data, dict):
        return jsonify({"success": False, "error": "Incident must be a JSON object"}), 400
    if "root_cause" in data and not isinstance(data["root_cause"], str):
        return jsonify({"success": False, "error": "Root cause must be text"}), 400
    if "remediation_steps" in data:
        steps = data["remediation_steps"]
        if not isinstance(steps, list) or any(
            not isinstance(step, dict)
            or not isinstance(step.get("step"), int)
            or not isinstance(step.get("title"), str)
            or not isinstance(step.get("sql"), str)
            for step in steps
        ):
            return jsonify({"success": False, "error": "Invalid remediation steps"}), 400
    anomaly = None
    diagnosis = {}
    if any(field not in data for field in ("title", "database", "root_cause", "remediation_steps")):
        metrics = db_monitor.poll_metrics()
        anomaly = next((entry["anomaly"] for entry in metrics.values() if entry.get("anomaly")), None)
        if "root_cause" not in data or "remediation_steps" not in data:
            diagnosis = agent_engine.diagnose_anomaly(anomaly, metrics)

    try:
        inc_id = data.get("incident_id") or incident_store.get_next_incident_id()
    except Exception as error:
        logger.warning("Incident ID generation failed (%s)", type(error).__name__)
        return jsonify({"success": False, "error": "Incident ID could not be generated"}), 503
    now_str = time.strftime("%H:%M:%S")
    
    incident = {
        "incident_id": inc_id,
        "severity": data.get("severity", "HIGH"),
        "title": data.get("title") or (anomaly.get("title", "PostgreSQL Database Anomaly") if anomaly else "DB Incident"),
        "database": data.get("database") or (anomaly.get("database", "gcc_banking_core") if anomaly else "gcc_banking_core"),
        "category": data.get("category", "Database - PostgreSQL Fleet"),
        "assigned_to": data.get("assigned_to", "DBA on-call"),
        "raised_by": data.get("raised_by", "dbpulse agent"),
        "created_at": now_str,
        "root_cause": data.get("root_cause", diagnosis.get("root_cause")),
        "remediation_steps": data.get("remediation_steps", diagnosis.get("remediation_steps")),
        "notes": data.get("notes", "")
    }
    try:
        incident_store.save(incident)
    except Exception as error:
        logger.warning("Incident persistence failed (%s)", type(error).__name__)
        return jsonify({"success": False, "error": "Incident could not be stored"}), 503

    incidents_db.append(incident)
    
    timeline_events.append({
        "timestamp": now_str,
        "event": f"Incident raised {inc_id} (Assigned: {incident['assigned_to']})",
        "type": "incident"
    })
    
    return jsonify({
        "success": True,
        "incident": incident
    })

@app.route("/api/trigger-anomaly", methods=["POST"])
def trigger_anomaly():
    if not db_monitor.simulation_enabled:
        return jsonify({"success": False, "error": "Simulation is disabled in live mode"}), 403
    data = request.get_json() or {}
    scenario = data.get("scenario", "LOCK_CONTENTION")
    success = db_monitor.set_scenario(scenario)
    
    now_str = time.strftime("%H:%M:%S")
    timeline_events.append({
        "timestamp": now_str,
        "event": f"Scenario changed to: {scenario}",
        "type": "control"
    })
    
    return jsonify({
        "success": success,
        "active_scenario": db_monitor.active_scenario
    })

@app.route("/api/reset", methods=["POST"])
def reset_fleet():
    db_monitor.set_scenario("HEALTHY")
    now_str = time.strftime("%H:%M:%S")
    timeline_events.append({
        "timestamp": now_str,
        "event": "Simulated scenario cleared; live anomalies remain visible",
        "type": "control"
    })
    return jsonify({
        "success": True,
        "active_scenario": "HEALTHY"
    })

@app.route("/api/timeline", methods=["GET"])
def get_timeline():
    return jsonify({
        "success": True,
        "timeline": timeline_events
    })

# Serve React static app
@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def serve_frontend(path):
    dist_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../dist"))
    if path != "" and os.path.exists(os.path.join(dist_dir, path)):
        return send_from_directory(dist_dir, path)
    else:
        return send_from_directory(dist_dir, "index.html")

def require_live_database():
    if not (db_monitor.pg_url or db_monitor.pghost):
        raise SystemExit("PostgreSQL is not configured. On Windows run .\\start-dbpulse.ps1 to load the encrypted profile. For intentional demo mode set DBPULSE_ALLOW_DEMO=1.")
    db_monitor.poll_metrics()
    if db_monitor.get_connection_status()["state"] != "connected":
        raise SystemExit("Live PostgreSQL startup check failed. Check connectivity and credentials; use .\\start-dbpulse.ps1 -ResetCredentials to replace the saved Windows profile. No demo server was started.")
    if incident_store.check_readiness()["state"] != "connected":
        raise SystemExit("Incident storage startup check failed. Verify public.incidents schema and INSERT/SELECT privileges in INCIDENT_DATABASE. No server was started.")


if __name__ == "__main__":
    if os.getenv("DBPULSE_ALLOW_DEMO") != "1":
        require_live_database()
    port = int(os.getenv("PORT", 5000))
    logger.info(f"Starting dbpulse backend on port {port}")
    app.run(host="0.0.0.0", port=port, debug=False)
