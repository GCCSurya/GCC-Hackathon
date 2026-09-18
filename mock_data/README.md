# PostgreSQL Mockup Data for `testdb` (`dbpulse`)

This directory contains pre-generated mockup data CSV files, database schemas, and import scripts for testing the **dbpulse** PostgreSQL Reliability Agent on your VM.

## Three-Database GCC Fleet

The dashboard is configured for these existing databases:

| Database | Seeded tables |
| :--- | :--- |
| `gcc_banking_core` | `customers`, `accounts`, `orders`, `transactions` |
| `gcc_reconciliation` | `recon_records`, `recon_batches`, `recon_exceptions`, `source_systems` |
| `gcc_audit_service` | `audit_logs`, `application_users`, `security_events`, `event_rules` |

To seed all three from pgAdmin's PSQL Tool, run:

```text
\cd 'C:/Users/GCCHackVM.ILB-3790VM-67/Desktop/GCC-Hackathon/mock_data'
\i seed_gcc_fleet.sql
```

Each database script runs in its own transaction, stops on the first error, and
creates tables without `DROP` or `IF NOT EXISTS`. This intentionally refuses to
overwrite an existing table. Because PostgreSQL transactions do not span
databases, an error in a later database does not undo an earlier database's
successful commit. Review the error instead of dropping existing objects.

After seeding, restart the Flask backend in the terminal containing the `PG*`
credentials. The monitor reuses the same host and credentials but connects to
each configured database by name. Select a fleet row to view its live KPIs,
table counts, and a read-only preview limited to 20 rows.

### Incident Store

Incident reports are stored in `test.public.incidents`. In pgAdmin's PSQL Tool,
connect to the `test` database and run:

```text
\cd 'C:/Users/GCCHackVM.ILB-3790VM-67/Desktop/GCC-Hackathon/mock_data'
\i seed_incident_store.sql
```

The backend uses `INCIDENT_DATABASE=test` by default. Set `INCIDENT_DATABASE`
before starting Flask if the system database has a different name.

## Safe Import Into the Shared Azure Database

Use `seed_demo.sql` for the assigned Azure database `test`. Do not run
`schema.sql` directly against a shared database: it drops existing tables with
`CASCADE`.

The safe entry point creates a new `dbpulse_demo` schema, then loads all five
CSV files in a single transaction. It stops on the first error and refuses to
run if that schema already exists. It does not overwrite existing data or
perform an ongoing synchronization. On failure, the transaction is rolled back
when psql exits. This requires permission to create a schema in `test`.

In PowerShell, from the repository root, use the terminal where your `PGHOST`,
`PGPORT`, `PGDATABASE`, `PGUSER`, `PGSSLMODE`, and private `PGPASSWORD` are set:

```powershell
Push-Location .\mock_data
try {
	psql -X -h $env:PGHOST -p $env:PGPORT -U $env:PGUSER -d $env:PGDATABASE -f .\seed_demo.sql
	if ($LASTEXITCODE -ne 0) { throw 'Demo import failed; no transaction was committed.' }
} finally {
	Pop-Location
}
```

`psql` must be installed and on PATH. It reads these CSVs from your computer;
server-side filesystem access is not needed. Without `PGPASSWORD`, psql may
prompt for the password privately. Never paste passwords into chat. Set
`PGSSLMODE=require` for Azure. PostgreSQL client commands use `PG*` settings;
the backend additionally recognizes `POSTGRES_URL` and `DATABASE_URL`, which
override its `PG*` settings. Ensure both tools target the same database.

After a successful commit, verify counts in pgAdmin connected to `test`:

```sql
SELECT 'customers' AS table_name, count(*) FROM dbpulse_demo.customers
UNION ALL SELECT 'accounts', count(*) FROM dbpulse_demo.accounts
UNION ALL SELECT 'orders', count(*) FROM dbpulse_demo.orders
UNION ALL SELECT 'audit_logs', count(*) FROM dbpulse_demo.audit_logs
UNION ALL SELECT 'recon_records', count(*) FROM dbpulse_demo.recon_records;
```

Expected counts are 500, 1,000, 5,000, 10,000, and 2,500 respectively.
If the schema already exists, inspect its data before choosing a merge or
replacement strategy; do not drop it just to rerun the seed.

Next, restart the updated backend in its credential-configured terminal and
check `/api/db-health`. A 200 response with `connection.state=connected`
confirms monitoring queries work. Importing rows does not generate active
sessions or lock contention, and the dashboard still mixes live and demo
metrics. Existing scenario SQL and remediation suggestions reference
`public.orders` or `public.audit_logs`; do not execute them against the shared
database. Any later workload must explicitly target `dbpulse_demo` and be
bounded and separately approved.

---

## 📁 Files Overview

| File | Rows | Description |
| :--- | :--- | :--- |
| **`customers.csv`** | 500 | Enterprise & retail banking customer profiles |
| **`accounts.csv`** | 1,000 | Checking, savings, treasury, & escrow accounts |
| **`orders.csv`** | 5,000 | High-volume financial transactions (used for **Lock Contention** scenario) |
| **`audit_logs.csv`** | 10,000 | System & security audit logs with JSON payloads (used for **Runaway Query** scenario) |
| **`recon_records.csv`** | 2,500 | Reconciliation data matching the `RECON_DB` fleet service |
| **`schema.sql`** | - | Complete DDL defining tables, primary keys, foreign keys, & indexes |
| **`import_data.sql`** | - | PostgreSQL `\copy` script to import all CSV files and refresh sequence counters |
| **`generate_mock_data.py`** | - | Re-generator script to scale dataset to 50k, 100k, or 1M+ rows if needed |
| **`simulate_anomalies.sql`** | - | Interactive SQL queries to reproduce Lock Contention, Runaway Queries, & Pool Exhaustion |

---

## 🚀 Setup on your VM (Step-by-Step)

### 1. Create `testdb` in PostgreSQL

Connect to PostgreSQL on your VM:
```bash
# As postgres user:
psql -U postgres
```

Inside PostgreSQL shell:
```sql
CREATE DATABASE testdb;
\q
```

---

### 2. Run Table Schema

Navigate to the `mock_data` folder on your VM and run:
```bash
psql -U postgres -d testdb -f schema.sql
```

This creates the 5 tables: `customers`, `accounts`, `orders`, `audit_logs`, and `recon_records`.

---

### 3. Import CSV Data

From inside the `mock_data` directory, run:
```bash
psql -U postgres -d testdb -f import_data.sql
```

The script will:
- Fast-load all 5 CSV files via `\copy` (client-side, no superuser filesystem restrictions)
- Align PostgreSQL `SERIAL` sequence IDs
- Run `ANALYZE` to update query planner statistics
- Print a verification row count table

---

### 4. Connect the `dbpulse` Backend to `testdb`

In your backend `.env` or terminal before launching Flask:
```bash
export POSTGRES_URL="postgresql://postgres:<your-password>@localhost:5432/testdb"
python backend/app.py
```

`db_monitor.py` will automatically detect `POSTGRES_URL` and query live metrics from `pg_stat_activity` and `pg_stat_database`!

---

### 5. (Optional) Generate Larger Datasets

If you want 100,000 orders or 500,000 audit logs to test heavier sequential scans on the VM:
```bash
python generate_mock_data.py --orders 100000 --audit-logs 500000
```
Then re-run `psql -U postgres -d testdb -f import_data.sql`.

---

### 6. Reproduce Anomalies

Use `simulate_anomalies.sql` to trigger real lock contentions on `orders` or sequential scan loads on `audit_logs` and watch the `dbpulse` dashboard detect and diagnose them live!
