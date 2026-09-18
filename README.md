# PNC GCC Hackathon — DB Reliability Agent (`dbpulse`)

> **Proactive Postgres DB Reliability Agent**: Watches PostgreSQL KPIs, detects anomalies, performs RAG-grounded root-cause diagnosis in plain English, provides interactive DBA triage tooling, and handles end-to-end incident dispatching — before customers notice impact.

![Theme Fit](https://img.shields.io/badge/Theme-Business%20Impact%20%26%20Risk-blue)
![Secondary Fit](https://img.shields.io/badge/Theme-Engineering%20Velocity-green)
![Tech Stack](https://img.shields.io/badge/Stack-Flask%20%7C%20React%20%7C%20Postgres%20%7C%20RAG-orange)

---

## 🚀 Key Features

### 1. 🔄 Dual Operational Modes (Agent vs. DBA)
Switch seamlessly via the top navigation bar between two operational paradigms:
- **🤖 Agent Mode (Autonomous)**: The agent continuously monitors fleet telemetry, auto-detects KPI anomalies, performs RAG-grounded root cause diagnosis, auto-generates copyable SQL remediation scripts, and pre-populates enterprise incident reports for one-click dispatch.
- **🛠️ DBA Mode (Manual Control & Workbench)**: Hands-on console for senior database administrators:
  - **3 Query Profiles**: One-click session filters (`Lock Contention / pg_locks`, `Idle Connections / ClientRead`, `Table Scans / DataFileRead`).
  - **Raw Session Table**: Detailed process inspector displaying PID, blocking chains, wait event, query duration, and query text.
  - **Interactive SQL Workbench**: Editable query buffer allowing DBAs to test and dry-run administrative SQL (`SELECT pg_cancel_backend(...)`).
  - **On-Demand AI Copilot**: **"🤖 Ask Agent for Suggestion"** button expands AI diagnostic recommendations and generated SQL without leaving manual mode.
  - **Manual Incident Creation**: Direct button to author and dispatch custom incidents manually.

### 2. 📋 Enterprise Incident Management (`#create-incident`)
- **Dedicated Incident Creation Flow**: Full-screen dispatch form accessible from both Agent and DBA modes.
- **Mode-Specific Badging**: Clearly marks incidents as either `AGENT AUTONOMOUS DISPATCH` (reported by `dbpulse AI Reliability Agent`) or `DBA MANUAL DISPATCH` (reported by `Human DBA Operations`).
- **Sequential Incident IDs**: Real-time ID generator (`GET /api/next-incident-id`) issuing sequential incident tracking numbers (`INC-00459`, `INC-00460`, ...).
- **Confirmation Receipts**: Instant receipt view with incident ID, priority badge, category, remediation action, and full audit timestamp.

### 3. 🧠 RAG-Grounded Root Cause Diagnosis
- Grounds LLM reasoning (Claude 3.5 Sonnet / GPT-4o / Azure AI Foundry) with a specialized PostgreSQL wait-event knowledge base.
- Explains root causes in plain English with source citations (`source: pg_stat_activity, pg_locks`).
- Strictly adheres to human-in-the-loop safety: **generates SQL for a human to review and execute — never executes destructive SQL autonomously**.

### 4. 🐘 Modern PostgreSQL 16+ Telemetry Engine
- Compatible with modern Postgres system catalogs: uses `cardinality(pg_blocking_pids(pid))` and `wait_event_type` (replaces deprecated `waiting` column) and groups cache hits by `datname`.
- Fleet-aware architecture: monitors primary production node (`PNCPRD01`) alongside fleet peers (`RECON_DB`, `MBL_STG`).
- Zero-risk fallback: built-in synthetic database engine and cached diagnosis fallback ensure the application runs 100% out-of-the-box even without a live database or cloud API key.

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
│   ├── db_monitor.py       # PostgreSQL 16+ queries & synthetic DB engine
│   ├── rag_engine.py       # PostgreSQL wait event RAG knowledge base
│   ├── agent.py            # AI diagnosis reasoning engine & fallback
│   ├── test_backend.py     # Unit test suite (fleet status, scenarios, incident generation)
│   └── requirements.txt    # Python dependencies
├── src/
│   ├── components/         # Modular React components
│   │   ├── Header.tsx             # Top bar with [🤖 Agent Mode] vs [🛠️ DBA Mode] pill switcher
│   │   ├── FleetStrip.tsx         # Fleet node status (PNCPRD01, RECON_DB, MBL_STG)
│   │   ├── KpiRow.tsx             # 4 live KPI cards (Lock Contention, Cache Hit, Idle, Commits)
│   │   ├── AnomalyBanner.tsx      # Anomaly alert banner
│   │   ├── AgentPanel.tsx         # Autonomous AI diagnosis, RAG grounding & remediation
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
│   └── account_balances.csv# Customer accounts & ledgers
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

```bash
# Navigate to backend directory and install dependencies
cd backend
pip install -r requirements.txt

# (Optional) Set environment variables for live PostgreSQL & LLM API
export POSTGRES_URL="postgresql://user:password@localhost:5432/postgres"
export ANTHROPIC_API_KEY="your-key-here"

# Run Flask backend server (serves API on port 5000)
python app.py
```

### 2. Frontend Setup & Build

```bash
# Install Node dependencies
npm install

# Build production React bundle (served directly by Flask at http://localhost:5000)
npm run build

# Or run Vite dev server for hot reload (http://localhost:5173)
npm run dev
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

- **PostgreSQL connected · Mixed live/demo data:** monitoring queries succeeded.
   PNCPRD01 uses live session counts and available cache statistics. Demo scenarios,
   peer databases, risk scores, query-time estimates and other values remain simulated.
- **Demo data · Database not configured:** this backend process has no database target.
- **Demo fallback · Database check failed:** connection or monitoring queries failed.
- **Backend unavailable / status unknown:** connectivity is not confirmed; check the
   backend process and restart it if it predates the status endpoint.

For a direct check, open `http://localhost:5000/api/db-health`. It executes the
read-only monitoring queries and returns HTTP **200** only when they succeed;
HTTP **503** with a credential-free reason means live telemetry is unavailable.
An HTTP 200 from `/api/fleet` or `/api/kpis` alone is not proof of a live database.

### Configure Azure AI Foundry agent diagnoses

The checked-in launcher selects `gpt-5.6-sol`. Use managed identity when the VM
has an Azure inference role:

```powershell
.\start-dbpulse.ps1
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
its model label includes `gpt-5.6-sol`. If Azure rejects authentication, the live
call falls back to deterministic RAG and labels the result accurately.

Monitoring uses read-only transactions, a 3-second connection timeout and a
5-second per-statement timeout. Use a monitoring account with suitable permissions;
do not run cancellation/termination SQL against the shared database for demo testing.
Incidents are persisted in `test.public.incidents`, and LLM connectivity is
separate from DB connectivity.

For now, Flask on port 5000 is the recommended full-stack entry point. Vite's dev
server needs an `/api` proxy to Flask before its relative API calls reach the backend.

Once the app is running at `http://localhost:5000` (or `http://localhost:5173`), follow these steps to experience and evaluate both operational modes:

### 🤖 Testing Mode 1: Agent Mode (Autonomous AI Operations)

1. **Verify Mode**: Ensure **`[🤖 Agent Mode]`** is active in the top-right header (active by default with a teal glow).
2. **Inject Anomaly**: In the bottom **Demo Controls** bar, click **"Lock Contention"** (or **"Idle Connections"**).
3. **Observe Autonomous AI Triage**:
   - The fleet strip and KPI row update in real time with anomaly metrics.
   - The **Agent Reliability Copilot** immediately detects the anomaly, queries the wait-event RAG knowledge base, and displays a plain-English root cause analysis with system view citations (`pg_stat_activity`, `pg_locks`).
   - A step-by-step copyable SQL remediation script (`SELECT pg_cancel_backend(...)`) is automatically drafted.
4. **Dispatch Pre-Staged Incident**:
   - Click **"Raise Incident"** on the staged Incident Card (or navigate to `#create-incident`).
   - Notice the form is **automatically pre-populated** with the AI diagnosis, attached SQL fix, and marked with the **`AGENT AUTONOMOUS DISPATCH`** badge (Reporter: `dbpulse AI Reliability Agent`).
   - Click **"Submit & Dispatch Incident"** to view the live confirmation receipt with an auto-generated sequential ID (e.g. `INC-00459`).

---

### 🛠️ Testing Mode 2: DBA Mode (Manual Control & Technical Workbench)

1. **Switch Mode**: In the top navigation bar, click the toggle to switch to **`[🛠️ DBA Mode]`**.
   - Notice the console shifts into an amber-accented technical workbench (`#E5A93C`) designed for senior database engineers.
2. **Inspect Raw Session Telemetry**:
   - Click through the 3 query profile tabs:
     - `Lock Contention (pg_locks)` $\rightarrow$ shows blocking PIDs and waiting transaction queries.
     - `Idle Connections (ClientRead)` $\rightarrow$ displays lingering idle application sessions.
     - `Table Scans (DataFileRead)` $\rightarrow$ identifies queries reading heavily from disk.
   - The **Raw Session Inspector** updates dynamically, highlighting root blocker processes in coral (`#D9643A`).
3. **Use the Interactive SQL Workbench**:
   - Review or edit the SQL script in the **Manual Remediation SQL Buffer**.
   - Click **"▶ Run Query (Dry Run)"** to test administrative actions safely.
4. **Consult the On-Demand AI Copilot**:
   - Need AI assistance while staying in full manual control? Click **"🤖 Ask Agent for Suggestion"**.
   - An on-demand copilot drawer opens with the RAG root-cause assessment and suggested SQL fix.
5. **Create & Dispatch a Manual Incident**:
   - Click **"+ Create Incident Manually"** (or click "Create Incident" in the header).
   - The dispatch form opens in manual authoring mode, labeled with the **`DBA MANUAL DISPATCH`** badge (Reporter: `Human DBA Operations`).
   - Fill in or adjust the title, priority, and notes, then click **"Submit & Dispatch Incident"** to view the confirmation receipt with a sequential ID (e.g. `INC-00460`).

---

## 🧪 Testing

### Backend Unit Tests
Run the comprehensive backend test suite:
```bash
python backend/test_backend.py
```
*Validates 3-node fleet architecture, scenario injection, dynamic sequential incident IDs, and custom incident payloads.*

### Frontend Verification
Run TypeScript type-check and build:
```bash
npm run build
```

---

## 👥 Authors
- **Surya Teja Vajjhala (CGI)**
- Built for the **PNC GCC Hackathon**

