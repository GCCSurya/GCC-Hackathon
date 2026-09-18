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
    {"timestamp": "14:00:00", "event": "Fleet monitoring initialized", "type": "system"},
    {"timestamp": "14:02:15", "event": "gcc_banking_core: Simulated anomaly selected (Lock Contention)", "type": "anomaly"}
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

@app.route("/api/diagnose", methods=["POST"])
def run_diagnosis():
    anomaly = db_monitor.get_active_anomaly()
    metrics = db_monitor.poll_metrics()
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
        "diagnosis": diagnosis
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
    anomaly = db_monitor.get_active_anomaly()
    diagnosis = agent_engine.diagnose_anomaly(anomaly, db_monitor.poll_metrics())
    
    inc_id = data.get("incident_id") or f"INC-00{len(incidents_db) + 458}"
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
        "root_cause": data.get("root_cause") or diagnosis.get("root_cause"),
        "remediation_steps": data.get("remediation_steps") or diagnosis.get("remediation_steps"),
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
        "event": "Fleet reset to healthy operational state",
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

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    logger.info(f"Starting dbpulse backend on port {port}")
    app.run(host="0.0.0.0", port=port, debug=False)
