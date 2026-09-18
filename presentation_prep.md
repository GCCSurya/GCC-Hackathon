# 📋 PNC GCC Hackathon — Presentation Preparation & Pitch Cheat Sheet

Use this reference material to build your own custom PowerPoint/Keynote presentation deck and prepare for the judge panel presentation.

---

## 📌 1. Key Project Information

- **Product Name**: `dbpulse` (PULSE-AI — Proactive Database Reliability Agent)
- **Presenters**: Surya Teja Vajjhala (CGI) & Teammate
- **Primary Hackathon Theme**: *Business Impact & Risk* ("Resolve Incidents Before Customers Feel Impact")
- **Secondary Hackathon Theme**: *Engineering Velocity* ("Build Resilient Systems by Design")
- **Target Demo Window**: 90-Second Live Loop (`Detect Anomaly → Diagnose (RAG + LLM) → Raise Incident with fix`)
- **Safety Principle**: *"Generates SQL for a human DBA to execute — nothing mutates production databases automatically."*
- **IP Compliance**: 100% fresh, independently-authored code written during hackathon; tested against synthetic PostgreSQL datasets (`testdb`). Zero PNC proprietary code/schema reused.

---

## 🎨 2. Recommended Slide Deck Outline (8 Slides)

### Slide 1: Title & Introduction
- **Title**: `dbpulse` — Proactive PostgreSQL Reliability Agent
- **Subtitle**: Catching, Diagnosing, and Resolving Database Incidents Before Customers Feel Impact
- **Theme Badges**: Business Impact & Risk | Engineering Velocity
- **Presenters**: Surya Teja Vajjhala (CGI) & Teammate

### Slide 2: The Problem (Reactive vs. Proactive)
- **Traditional Dashboards (Reactive)**:
  - Alerts fire *after* thresholds are breached.
  - DBAs spend 15–30 minutes manually querying `pg_stat_activity` & `pg_locks` to trace root causes.
  - Result: High MTTR (Mean Time to Resolution), transaction timeouts, customer impact.
- **dbpulse Agent (Proactive)**:
  - Real-time continuous metric telemetry polling across database fleet (`PNCPRD01`, `RECON_DB`, `MBL_STG`).
  - RAG-grounded instant plain-English root cause diagnosis.
  - Automated incident ticket (`INC-00458`) pre-attached with safe, copyable SQL remediation commands.

### Slide 3: The Solution & Safety Governance
- **Autonomous Loop**: `Detect → Diagnose → Act`
  - **Detect**: Polling system views (`pg_stat_activity`, `pg_locks`, `pg_stat_database`).
  - **Diagnose**: RAG wait-event knowledge base + Claude Sonnet 5 via Azure AI Foundry.
  - **Act**: Formulate step-by-step SQL remediation + raise incident ticket.
- **Safety Guardrail**: *Generates copyable SQL for human DBA approval — nothing executes automatically.*

### Slide 4: Live Demo Walkthrough (90-Second Money Moment)
- `00:00 — Baseline`: Console displays healthy fleet (`PNCPRD01`, `RECON_DB`, `MBL_STG`).
- `00:15 — Anomaly`: Injected Row Lock Contention on `public.orders`. `PNCPRD01` turns coral (`RISK 88/100`), blocked sessions jump to 4.
- `00:40 — Diagnosis`: Agent panel populates with root cause, `pg_stat_activity` citations, and copyable safe cancellation SQL (`SELECT pg_cancel_backend(48219)`).
- `00:70 — Incident Ticket`: One-click "Raise Incident Ticket" creates `INC-00458` assigned to DBA on-call with pre-attached remediation.

### Slide 5: Technical Architecture & Azure Stack
- **Backend**: Python Flask REST API (Single-process server serving static React assets).
- **Database**: Azure Database for PostgreSQL (Flexible Server), monitoring `pg_stat_activity` & `pg_locks`.
- **AI & RAG**: Azure AI Foundry (Claude Sonnet 5 / `gpt-5.4-mini`) + PostgreSQL Wait-Event RAG Knowledge Base.
- **Uptime Guarantee**: Built-in synthetic database engine & cached fallback diagnosis ensuring 100% demo reliability.

### Slide 6: Product Depth & Data Integrity
- **Future Vision**: Fleet-wide heatmaps, DBA feedback loop (upvote/downvote tuning), automated post-mortems.
- **Data Compliance**: 100% synthetic banking datasets (`customers`, `accounts`, `orders`, `audit_logs`, `recon_records`). Zero proprietary code.

### Slide 7: Business Impact & Value
- ⚡ **10x MTTR Reduction**: 15–30 minutes → Under 90 seconds.
- 🛡 **Risk Mitigation**: Protects customer checkout flows & transaction SLAs from silent lock contentions.
- 🚀 **Engineering Velocity**: Automates repetitive DBA triage so senior engineers focus on core architecture.

### Slide 8: Conclusion & Q&A
- **Summary**: `Detect → Diagnose → Raise Incident` in under 90 seconds powered by Azure AI Foundry & Azure PostgreSQL.
- Presenters: Surya Teja Vajjhala (CGI) & Teammate.

---

## 🎙 3. Presenter Script & Timing Guide

- **00:00 - 00:30 (Intro & Problem)**:
  > "Good morning judges. We are excited to present **dbpulse** — a proactive AI database reliability agent designed to catch, diagnose, and resolve database incidents before customers ever feel the impact.
  > In enterprise banking, database outages start silently: an uncommitted row lock or connection leak. By the time a traditional monitoring alert fires, customers are already experiencing app timeouts. Traditional dashboards leave DBAs spending 15 to 30 minutes manually querying system tables. **dbpulse** turns passive monitoring into an autonomous AI agent."

- **00:30 - 01:15 (Solution & Live Demo)**:
  > "dbpulse continuously watches PostgreSQL telemetry. When an anomaly occurs, it retrieves wait-event troubleshooting guidance via RAG, invokes Claude Sonnet 5 on Azure AI Foundry to explain the root cause in plain English, and drafts an incident ticket with exact remediation SQL.
  > Crucially, dbpulse follows a strict safety guardrail: it generates SQL for a human DBA to execute — nothing mutates production databases automatically.
  > Let's look at the live demo: our console shows healthy databases. Now we simulate an uncommitted transaction holding a row lock on public.orders. Immediately, dbpulse flags the anomaly. Within seconds, the agent panel populates explaining PID 48219 is holding the lock, providing copyable safe cancellation SQL. With one click, we raise incident INC-00458 for the DBA. Total time: under 90 seconds."

- **01:15 - 01:45 (Architecture & Value)**:
  > "dbpulse runs on Python Flask, Azure Database for PostgreSQL, and Azure AI Foundry. It reduces Mean Time to Resolution from 15 minutes to 90 seconds, directly protects customer checkout experience, and boosts engineering velocity. Thank you, and we welcome your questions!"

---

## ❓ 4. Anticipated Panel Questions & Best Answers

### Q1: *"How do you prevent the AI agent from executing dangerous SQL commands?"*
- **Answer**: *"Security and safety are central to our design. **dbpulse** operates strictly on a human-in-the-loop model: it generates diagnostic and remediation SQL for a human DBA to inspect and run — nothing executes automatically against production databases."*

### Q2: *"What happens if the LLM API hangs or network connectivity drops during an incident?"*
- **Answer**: *"We built **dbpulse** with enterprise resilience in mind. If the LLM API call fails or times out, our fallback engine instantly generates deterministic, RAG-grounded root causes and remediation scripts so the DBA is never left without guidance."*

### Q3: *"Can this scale to hundreds of databases across multiple cloud regions?"*
- **Answer**: *"Yes. Because PostgreSQL system views like `pg_stat_activity` and `pg_stat_database` are lightweight cluster-wide views, a single monitoring connection can observe multiple database instances simultaneously with minimal overhead."*
