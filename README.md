# PNC GCC Hackathon — DB Reliability Agent (`dbpulse`)

> **Postgres DB Reliability Agent**: Reads PostgreSQL KPIs, detects threshold-based anomalies, suggests rule-based runbook guidance, and persists incident records for DBA follow-up.

**Security boundary:** Authentication is not implemented. This is a trusted-environment prototype, not a production-ready service. Restrict network access; do not expose its APIs publicly.

![Theme Fit](https://img.shields.io/badge/Theme-Business%20Impact%20%26%20Risk-blue)
![Secondary Fit](https://img.shields.io/badge/Theme-Engineering%20Velocity-green)
![Tech Stack](https://img.shields.io/badge/Stack-Flask%20%7C%20React%20%7C%20Postgres%20%7C%20RAG-orange)

---

## 🚀 Key Features

### 1. 🔄 Dual Operational Modes (Agent vs. DBA)
Switch seamlessly via the top navigation bar between two operational paradigms:
- **🤖 Agent Mode**: While the dashboard is open, the browser polls every three seconds, displays live KPI anomalies, requests runbook guidance, and pre-populates incident drafts. `npm start` also supervises a separate read-only monitor that keeps running without an open browser.
- **🛠️ DBA Mode (Manual Control & Workbench)**: Hands-on console for senior database administrators:
  - **3 Query Profiles**: One-click session filters (`Lock Contention / pg_locks`, `Idle Connections / ClientRead`, `Table Scans / DataFileRead`).
   - **Demonstration Session Table**: Sample process rows for presenting blocking chains, wait events, query duration, and query text. It is not live telemetry.
   - **SQL Preview Buffer**: Editable SQL drafting area. The preview button never submits SQL to PostgreSQL.
  - **On-Demand AI Copilot**: **"🤖 Ask Agent for Suggestion"** button expands AI diagnostic recommendations and generated SQL without leaving manual mode.
  - **Manual Incident Creation**: Direct button to author and dispatch custom incidents manually.

### 2. 📋 Enterprise Incident Management (`#create-incident`)
- **Dedicated Incident Creation Flow**: Full-screen dispatch form accessible from both Agent and DBA modes.
- **Mode-Specific Badging**: Clearly marks incidents as either `AGENT AUTONOMOUS DISPATCH` (reported by `dbpulse AI Reliability Agent`) or `DBA MANUAL DISPATCH` (reported by `Human DBA Operations`).
- **Random Incident IDs**: Collision-checked identifiers from `GET /api/next-incident-id`, formatted as `INC-` plus eight random hexadecimal characters.
- **PostgreSQL Receipts**: A receipt appears only after the incident is persisted to `test.public.incidents`; a failed write remains an error and does not produce a local success receipt.

### 3. 🧠 Rule-Based Runbook Guidance
- The default selects fixed remediation templates by anomaly type; it does not generate answers from retrieved documents. No cloud model or API key is required.
- Azure AI Foundry, Anthropic, and OpenAI adapters remain optional and require an explicit `AGENT_PROVIDER` setting plus valid credentials.
- Optional cloud calls include retrieved knowledge-base context. Default runbook references identify relevant PostgreSQL views, not evidence proving a root cause. Validate suggested causes, object names, and SQL against the current database before use.
- Strictly adheres to human-in-the-loop safety: **generates SQL for a human to review and execute — never executes destructive SQL autonomously**.

### 4. 🐘 PostgreSQL Telemetry Engine
- Compatible with modern Postgres system catalogs: uses `cardinality(pg_blocking_pids(pid))` and `wait_event_type` (replaces deprecated `waiting` column) and groups cache hits by `datname`.
- Fleet-aware architecture: reads `gcc_banking_core`, `gcc_reconciliation`, and `gcc_audit_service` using read-only sessions.
- Measures per-database active and blocked sessions, average and longest active-query duration, cache hit ratio, and database size. Connection pressure uses cluster-wide client connections against global `max_connections`.
- Normal operation is live-only: every poll recalculates risk from PostgreSQL telemetry. Any blocked session triggers lock contention; cluster connection utilization at or above 80% triggers pool pressure; an active query running at least 120 seconds triggers a long-running-query anomaly. These are operational warning thresholds, not proof of a root cause.
- The 0-100 heuristic score combines blocked sessions (25 each, capped at 60), connection utilization above 60% (1.5 points per percentage point), query runtime above 30 seconds (one point per 3 seconds), and cache hit ratio below 95% (2 points per percentage point). A detected anomaly or score of at least 50 marks a database at risk. Cache statistics are cumulative, not a recent-window measurement. Scores are not predicted failure probabilities.
- Failed or unconfigured reads show unavailable telemetry and `N/A`, never an invented healthy or risk score. These checks monitor database operation, not correctness of banking, order, or reconciliation records.
- Simulation controls and the scenario API require `DBPULSE_ALLOW_DEMO=1` before backend startup. Live anomalies take priority, simulated risk is labeled demo, and reset only clears simulation. Even with demo enabled, a failed real read stays unavailable. Without PostgreSQL, explicitly enabled demo mode offers sample scenarios but no table previews or persisted incident receipts.

---

## 🎨 Visual Design System ("Terminal Glow")

Dark technical console designed specifically for database reliability engineers under incident pressure:
- **Background**: `#14171C` (Deep slate)
- **Agent Presence**: `#3FA9A0` (Teal glow & accents reserved strictly for AI presence)
- **DBA Workbench**: `#E5A93C` (Warm amber accent reserved for human DBA manual control)
- **Risk Indicator**: `#D9643A` (Coral accent for anomaly signals & blocking PIDs)
- **Healthy Fleet**: `#5B8C6E` (Sage accent for healthy nodes)
- **Typography**: `IBM Plex Sans` + `IBM Plex Mono`

---

## 🛠 Project Structure

```
├── backend/
│   ├── app.py              # Flask server, REST APIs (/api/next-incident-id, /api/raise-incident)
│   ├── multi_db_monitor.py # Read-only fleet telemetry and explicit scenarios
│   ├── incident_store.py   # PostgreSQL incident persistence and random IDs
│   ├── monitor_worker.py   # Browser-independent polling process
│   ├── rag_engine.py       # PostgreSQL wait event RAG knowledge base
│   ├── agent.py            # AI diagnosis reasoning engine & fallback
│   ├── test_backend.py     # Unit test suite (fleet status, scenarios, incident generation)
│   └── requirements.txt    # Python dependencies
├── src/
│   ├── components/         # Modular React components
│   │   ├── Header.tsx             # Top bar with [🤖 Agent Mode] vs [🛠️ DBA Mode] pill switcher
│   │   ├── FleetStrip.tsx         # Three-database fleet status
│   │   ├── KpiRow.tsx             # 4 live KPI cards (Lock Contention, Cache Hit, Idle, Commits)
│   │   ├── AnomalyBanner.tsx      # Anomaly alert banner
│   │   ├── AgentPanel.tsx         # Suggested diagnosis and reviewable remediation
│   │   ├── DbaConsolePanel.tsx    # Manual DBA triage console, session inspector & SQL buffer
│   │   ├── CreateIncidentPage.tsx # Dedicated incident creation page & success receipts
│   │   ├── IncidentCard.tsx       # Staged incident card & dispatch trigger
│   │   ├── DemoControls.tsx       # Anomaly scenario simulator (Lock Contention, Idle, Normal)
│   │   └── TimelineFooter.tsx     # Fleet event timeline and audit trail
│   ├── App.tsx             # Main dashboard layout & hash router (#create-incident)
│   └── index.css           # Global design tokens, amber/teal accents & terminal glow styles
├── mock_data/              # Enterprise banking test datasets (10,000+ records)
│   ├── generate_mock_data.py # Data generator for recon records, audit logs & accounts
│   ├── recon_records.csv   # Reconciliation transactions
│   ├── audit_logs.csv      # Security & administrative audit logs
│   └── accounts.csv        # Customer accounts & ledgers
├── design/
│   └── reference.html      # Interactive standalone reference design
└── package.json            # Node.js dependencies & scripts
```

---

## ⚡ Quickstart Guide

### Prerequisites
- Node.js 20.19+ or 22.12+ (supported by Vite 8) & npm
- Python 3.11+

### 1. Backend Setup & Run

On Windows, use the secure launcher from the project root after installing the
backend dependencies in `.venv` and building the frontend:

```powershell
npm start
```

The first launch prompts privately for PostgreSQL credentials, verifies live fleet
connectivity and incident-storage readiness, and saves the profile at `%LOCALAPPDATA%\dbpulse\postgres.clixml`.
The password is encrypted with Windows DPAPI for the current Windows user on this
machine, outside the repository. Subsequent launches, including after a reboot,
reuse it without another prompt. Do not copy the profile to another user or machine.

The launcher supervises Flask and the monitoring worker with the same credential
environment. Closing the browser does not stop monitoring. Ctrl+C stops both;
unexpected child exit stops the remaining child and reports failure. This is not
a Windows service and does not start automatically after a reboot: run `npm start`
again. Forced process termination can bypass cleanup.

Incident storage must already exist in `INCIDENT_DATABASE` (default `test`). Review
[mock_data/seed_incident_store.sql](mock_data/seed_incident_store.sql) before an
authorized provisioning step. Startup never creates or modifies schema. Readiness
checks expected columns, types, required defaults, schema access, table
`INSERT`/`SELECT`, and applicable sequence privileges without inserting rows.
Row-security policies and triggers can still reject a real write, which remains
an HTTP 503 error rather than a success receipt.

To enroll credentials while the dashboard is already running:

```powershell
.\start-dbpulse.ps1 -ConfigureOnly
```

Use `-ResetCredentials` to replace the saved password (combine with `-ConfigureOnly`
to leave an existing server running). Explicit `PG*` environment settings override
saved settings; the saved password is reused only for the matching host, port, and
user. The launcher rejects URL-based overrides and occupied server ports rather
than accidentally using another configuration or starting a competing process.

Direct `python backend/app.py` startup requires a live database check to succeed;
it does not load the Windows profile. Missing or failed database configuration
stops startup with instructions instead of silently serving demo data. For an
intentional standalone demo, explicitly set `DBPULSE_ALLOW_DEMO=1`. This startup
guard applies to the direct Python entry point; WSGI deployments must configure
their own environment and use `/api/readiness` for readiness checks. `startup.sh`
uses exactly one Gunicorn worker because scenarios and timeline state are in memory;
do not scale replicas without moving that state into shared storage.

For environment-managed setups on other platforms:

```bash
# Navigate to backend directory and install dependencies
cd backend
pip install -r requirements.txt

# Set environment variables for live PostgreSQL
export POSTGRES_URL="postgresql://user:password@localhost:5432/postgres"

# Deterministic rules are the default diagnosis provider
export AGENT_PROVIDER="deterministic"

# Run Flask backend server (serves API on port 5000)
python app.py
```

### 2. Frontend Setup & Build

```bash
# Install Node dependencies
npm install

# Build production React bundle (served directly by Flask at http://localhost:5000)
npm run build

# Vite is suitable for frontend-only work; relative /api calls require a proxy.
# Use Flask on port 5000 for the working full-stack application.
```

---

## 🎮 How to Run & Test in Both Modes

### Verify Azure PostgreSQL connectivity (Windows PowerShell)

pgAdmin and dbpulse connect independently. A working pgAdmin session or dashboard
does not prove that the backend has received database credentials. Run the following
in the same terminal that will start the backend, using the connection details from
pgAdmin's server properties:

```powershell
$env:PGHOST = "<server>.postgres.database.azure.com"
$env:PGPORT = "5432"
$env:PGDATABASE = "<database>"
$env:PGUSER = "<monitoring-user>"
$env:PGSSLMODE = "require"
$credential = Get-Credential -UserName $env:PGUSER -Message "Enter database credentials privately"
$env:PGPASSWORD = $credential.GetNetworkCredential().Password

# From the project root, after stopping the old backend with Ctrl+C:
python backend/app.py
```

Do not paste passwords into chat, source files, or command literals. Variables apply
only to this terminal and its child processes. `POSTGRES_URL` / `DATABASE_URL`, if
set, take precedence over `PG*` settings; remove stale URL variables when switching
to this setup. The current startup code does **not** automatically load `.env` files.

After rebuilding the frontend (`npm run build`) and restarting Flask, open
`http://localhost:5000`. The database status banner distinguishes:

- **PostgreSQL connected:** all configured fleet databases returned live telemetry.
   Risk, active-query duration, connection pressure, and anomalies are calculated from
   PostgreSQL data. Explicit demo opt-in adds a **Simulation enabled** label.
- **Database not configured:** this backend process has no database target; normal mode shows `N/A`.
- **Database check failed:** connection or monitoring queries failed; affected databases show unavailable risk and KPI values.
- **Backend unavailable / status unknown:** connectivity is not confirmed; check the
   backend process and restart it if it predates the status endpoint.

For a direct check, open `http://localhost:5000/api/db-health`. It executes the
read-only monitoring queries and returns HTTP **200** only when they succeed;
HTTP **503** with a credential-free reason means live telemetry is unavailable.
An HTTP 200 from `/api/fleet` or `/api/kpis` alone is not proof of a live database.
Use `/api/readiness` for the combined fleet and incident-storage check. It returns
200 only when both are ready, otherwise 503 with credential-free status messages.

### Diagnosis provider

No AI credentials are needed for the supported default:

```powershell
$env:AGENT_PROVIDER = "deterministic"
```

The default launcher uses deterministic runbook rules and reuses the encrypted PostgreSQL
profile, prompting privately only when credentials are not available:

```powershell
.\start-dbpulse.ps1
```

Azure AI Foundry is optional. To attempt Azure diagnosis, select an Azure
authentication mode explicitly.

The Azure modes select `gpt-5.6-sol`. Use managed identity when the VM
has an Azure inference role:

```powershell
.\start-dbpulse.ps1 -Authentication ManagedIdentity
```

The VM identity needs `Azure AI User` or `Cognitive Services OpenAI User` on the
Foundry resource. If RBAC cannot be assigned, rotate the previously exposed key
and use the API-key mode. Enter the new key only at the masked terminal prompt;
do not put it in chat, source files, or command arguments:

```powershell
.\start-dbpulse.ps1 -Authentication ApiKey
```

The launcher removes the key from its environment when Flask exits. Verify
non-secret configuration at
`http://localhost:5000/api/agent-status`; `configured` must be `true` and
`authentication` must match the selected mode. Trigger a diagnosis and confirm
its model label includes `gpt-5.6-sol`. If Azure rejects authentication, diagnosis
falls back to rule-based runbook guidance and labels the result accurately.

### Independent monitoring worker

`npm start` already launches one monitor alongside Flask. Do not launch a second
worker for the same deployment. For a separately managed deployment, configure
the same PostgreSQL environment and run the worker explicitly; standalone Python
does not decrypt the Windows profile and refuses unconfigured or failed live
connectivity unless `DBPULSE_ALLOW_DEMO=1` is explicitly set:

```powershell
$env:AGENT_PROVIDER = "deterministic"
$env:MONITOR_INTERVAL_SECONDS = "30"
python backend/monitor_worker.py
```

For deployment, manage exactly one worker with your process manager. No boot-time
service is installed by this project. Do not start it from Flask module import: Gunicorn
workers would each create a duplicate poller. The worker logs one diagnosis when an
anomaly first appears and does not execute SQL or automatically create incidents.

Monitoring uses read-only transactions, a 3-second connection timeout and a
5-second per-statement timeout. Use a monitoring account with suitable permissions;
do not run cancellation/termination SQL against the shared database for demo testing.
Incidents are persisted in `test.public.incidents`, and LLM connectivity is
separate from DB connectivity.

For now, Flask on port 5000 is the recommended full-stack entry point. Vite's dev
server needs an `/api` proxy to Flask before its relative API calls reach the backend.

Once the app is running at `http://localhost:5000`, follow these steps to experience and evaluate both operational modes:

### 🤖 Testing Mode 1: Agent Mode (Autonomous AI Operations)

1. **Verify Mode**: Ensure **`[🤖 Agent Mode]`** is active in the top-right header (active by default with a teal glow).
2. **Observe Live Risk**: The fleet scores update from database telemetry automatically. If no warning threshold is crossed, no anomaly is staged. For a synthetic walkthrough only, set `$env:DBPULSE_ALLOW_DEMO = '1'` before restarting the backend, then select **Lock Contention** in **Demo Controls**. Remove that environment variable and restart to return to live-only mode; do not provoke real incidents on shared databases.
3. **Observe Autonomous AI Triage**:
   - The fleet strip and KPI row update from telemetry. A simulated risk does not replace available live KPI measurements.
   - The **Agent Reliability Copilot** requests guidance for the detected anomaly and displays a rule-based suggested cause with runbook references (`pg_stat_activity`, `pg_locks`).
   - A step-by-step copyable SQL remediation script (`SELECT pg_cancel_backend(...)`) is automatically drafted.
4. **Dispatch Pre-Staged Incident**:
   - Click **"Raise Incident"** on the staged Incident Card (or navigate to `#create-incident`).
   - Notice the form is **automatically pre-populated** with the AI diagnosis, attached SQL fix, and marked with the **`AGENT AUTONOMOUS DISPATCH`** badge (Reporter: `dbpulse AI Reliability Agent`).
   - Click **"Submit & Dispatch Incident"** to persist the record and view its random incident ID.

#### Automated Agent Demo

With Flask explicitly started with `DBPULSE_ALLOW_DEMO=1` on port 5000, install
Chromium once and run the visible Playwright walkthrough. Simulation is disabled
in normal operation, so this injection-based runner requires that opt-in:

```powershell
npx playwright install chromium
npm run demo:agent
```

The runner activates Agent Mode, injects an anomaly, waits for diagnosis,
scrolls through the remediation and incident views, captures screenshots under
`artifacts/agent-demo`, and returns to the fleet console. It submits the incident
only when the dashboard reports a live PostgreSQL connection; this avoids showing
a demo receipt for an incident that was not persisted.

Optional environment variables are `DASHBOARD_URL`, `AGENT_DEMO_SCENARIO`
(`LOCK_CONTENTION`, `POOL_EXHAUSTION`, or `RUNAWAY_QUERY`), `HEADLESS=true`, and
`SUBMIT_INCIDENT=false`.

---

### 🛠️ Testing Mode 2: DBA Mode (Manual Control & Technical Workbench)

1. **Switch Mode**: In the top navigation bar, click the toggle to switch to **`[🛠️ DBA Mode]`**.
   - Notice the console shifts into an amber-accented technical workbench (`#E5A93C`) designed for senior database engineers.
2. **Inspect Demonstration Session Data**:
   - Click through the 3 query profile tabs:
     - `Lock Contention (pg_locks)` $\rightarrow$ shows blocking PIDs and waiting transaction queries.
     - `Idle Connections (ClientRead)` $\rightarrow$ displays lingering idle application sessions.
     - `Table Scans (DataFileRead)` $\rightarrow$ identifies queries reading heavily from disk.
   - The sample inspector changes with the selected profile and highlights a representative root blocker.
3. **Use the Interactive SQL Workbench**:
   - Review or edit the SQL script in the **Manual Remediation SQL Buffer**.
   - Click **"Preview Query"** to confirm that execution is disabled. Copy reviewed SQL into an approved DBA tool when appropriate.
4. **Consult the On-Demand AI Copilot**:
   - Need AI assistance while staying in full manual control? Click **"🤖 Ask Agent for Suggestion"**.
   - An on-demand copilot drawer opens with a suggested cause and SQL. **Refresh Agent Suggestion** requests a fresh diagnosis; recovery clears old guidance.
5. **Create & Dispatch a Manual Incident**:
   - Click **"+ Create Incident Manually"** (or click "Create Incident" in the header).
   - The dispatch form opens in manual authoring mode, labeled with the **`DBA MANUAL DISPATCH`** badge (Reporter: `Human DBA Operations`).
   - Fill in or adjust the title, priority, and notes, then submit it to `test.public.incidents` and view the persistence receipt.

---

## 🧪 Testing

### Backend Unit Tests
Run the comprehensive backend test suite:
```bash
python -m unittest discover -s backend -p "test_*.py"
```
*Uses mocks to validate telemetry, scenario precedence, readiness, incident payload preservation, provider routing, and supervisor lifecycle without database writes.*

### Frontend Verification
Run TypeScript type-check and build:
```bash
npm run build
npm run lint
node scripts/test-dashboard.mjs
```

The browser regression script serves the built UI locally with mocked APIs. It
checks draft persistence, reviewed and empty SQL, diagnosis refresh/recovery,
stale responses, and reset behavior without contacting PostgreSQL. Install its
browser once with `npx playwright install chromium`.

---

## 👥 Authors
- **Surya Teja Vajjhala (CGI)**
- Built for the **PNC GCC Hackathon**

