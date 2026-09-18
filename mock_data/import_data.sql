-- =============================================================================
-- Data Import Script for testdb
-- =============================================================================
-- Execute this script from inside the directory containing the CSV files:
--   psql -U postgres -d testdb -f import_data.sql
--
-- Note: \copy is a psql meta-command that reads files from the client machine
-- without requiring PostgreSQL superuser file system privileges.

\echo 'Importing customers...'
\copy customers(customer_id, first_name, last_name, email, phone, tier, status, created_at) FROM 'customers.csv' WITH (FORMAT csv, HEADER true);

\echo 'Importing accounts...'
\copy accounts(account_id, customer_id, account_number, account_type, balance, currency, status, created_at) FROM 'accounts.csv' WITH (FORMAT csv, HEADER true);

\echo 'Importing orders...'
\copy orders(order_id, account_id, customer_id, order_type, amount, currency, status, merchant_name, created_at, updated_at) FROM 'orders.csv' WITH (FORMAT csv, HEADER true);

\echo 'Importing audit_logs...'
\copy audit_logs(log_id, user_id, action, entity_type, entity_id, payload, ip_address, status_code, created_at) FROM 'audit_logs.csv' WITH (FORMAT csv, HEADER true);

\echo 'Importing recon_records...'
\copy recon_records(recon_id, source_system, external_ref, internal_order_id, amount, currency, status, discrepancy_reason, reconciled_at) FROM 'recon_records.csv' WITH (FORMAT csv, HEADER true);

-- Update serial sequence counters to match imported IDs
SELECT setval(pg_get_serial_sequence('customers', 'customer_id'), COALESCE(max(customer_id), 1)) FROM customers;
SELECT setval(pg_get_serial_sequence('accounts', 'account_id'), COALESCE(max(account_id), 1)) FROM accounts;
SELECT setval(pg_get_serial_sequence('orders', 'order_id'), COALESCE(max(order_id), 1)) FROM orders;
SELECT setval(pg_get_serial_sequence('audit_logs', 'log_id'), COALESCE(max(log_id), 1)) FROM audit_logs;
SELECT setval(pg_get_serial_sequence('recon_records', 'recon_id'), COALESCE(max(recon_id), 1)) FROM recon_records;

-- Run ANALYZE to populate planner statistics
ANALYZE customers;
ANALYZE accounts;
ANALYZE orders;
ANALYZE audit_logs;
ANALYZE recon_records;

-- Verification counts
\echo '================== IMPORT SUMMARY =================='
SELECT 'customers' as table_name, count(*) as row_count FROM customers
UNION ALL
SELECT 'accounts', count(*) FROM accounts
UNION ALL
SELECT 'orders', count(*) FROM orders
UNION ALL
SELECT 'audit_logs', count(*) FROM audit_logs
UNION ALL
SELECT 'recon_records', count(*) FROM recon_records;
\echo '===================================================='
