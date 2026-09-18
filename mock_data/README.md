# PostgreSQL Mockup Data for `testdb` (`dbpulse`)

This directory contains pre-generated mockup data CSV files, database schemas, and import scripts for testing the **dbpulse** PostgreSQL Reliability Agent on your VM.

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
