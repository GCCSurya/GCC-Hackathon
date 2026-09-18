-- =============================================================================
-- Schema Definition for testdb (PNC Hackathon: dbpulse)
-- =============================================================================
-- Run with: psql -U postgres -d testdb -f schema.sql

-- Drop existing tables if re-initializing (in reverse dependency order)
DROP TABLE IF EXISTS recon_records CASCADE;
DROP TABLE IF EXISTS audit_logs CASCADE;
DROP TABLE IF EXISTS orders CASCADE;
DROP TABLE IF EXISTS accounts CASCADE;
DROP TABLE IF EXISTS customers CASCADE;

-- 1. Customers Table
CREATE TABLE customers (
    customer_id SERIAL PRIMARY KEY,
    first_name VARCHAR(64) NOT NULL,
    last_name VARCHAR(64) NOT NULL,
    email VARCHAR(128) UNIQUE NOT NULL,
    phone VARCHAR(32),
    tier VARCHAR(32) DEFAULT 'STANDARD',
    status VARCHAR(32) DEFAULT 'ACTIVE',
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 2. Accounts Table
CREATE TABLE accounts (
    account_id SERIAL PRIMARY KEY,
    customer_id INT NOT NULL REFERENCES customers(customer_id) ON DELETE CASCADE,
    account_number VARCHAR(32) UNIQUE NOT NULL,
    account_type VARCHAR(32) NOT NULL,
    balance NUMERIC(15, 2) NOT NULL DEFAULT 0.00,
    currency VARCHAR(3) DEFAULT 'USD',
    status VARCHAR(32) DEFAULT 'ACTIVE',
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_accounts_customer_id ON accounts(customer_id);

-- 3. Orders Table (Subject of Scenario: LOCK_CONTENTION)
CREATE TABLE orders (
    order_id SERIAL PRIMARY KEY,
    account_id INT NOT NULL REFERENCES accounts(account_id) ON DELETE CASCADE,
    customer_id INT NOT NULL REFERENCES customers(customer_id) ON DELETE CASCADE,
    order_type VARCHAR(64) NOT NULL,
    amount NUMERIC(15, 2) NOT NULL,
    currency VARCHAR(3) DEFAULT 'USD',
    status VARCHAR(32) NOT NULL DEFAULT 'PENDING',
    merchant_name VARCHAR(128) NOT NULL,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_orders_account_id ON orders(account_id);
CREATE INDEX idx_orders_status ON orders(status);

-- 4. Audit Logs Table (Subject of Scenario: RUNAWAY_QUERY)
-- NOTE: 'payload' is intentionally unindexed to demonstrate missing-index sequential scans
CREATE TABLE audit_logs (
    log_id BIGSERIAL PRIMARY KEY,
    user_id VARCHAR(64) NOT NULL,
    action VARCHAR(64) NOT NULL,
    entity_type VARCHAR(64) NOT NULL,
    entity_id INT NOT NULL,
    payload TEXT NOT NULL,
    ip_address VARCHAR(45) NOT NULL,
    status_code INT NOT NULL DEFAULT 200,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_audit_logs_created_at ON audit_logs(created_at);
-- Recommended Remediation index from agent:
-- CREATE INDEX CONCURRENTLY idx_audit_logs_payload ON public.audit_logs(payload);

-- 5. Reconciliation Records Table (Simulating RECON_DB)
CREATE TABLE recon_records (
    recon_id SERIAL PRIMARY KEY,
    source_system VARCHAR(64) NOT NULL,
    external_ref VARCHAR(64) NOT NULL,
    internal_order_id INT,
    amount NUMERIC(15, 2) NOT NULL,
    currency VARCHAR(3) DEFAULT 'USD',
    status VARCHAR(32) NOT NULL DEFAULT 'MATCHED',
    discrepancy_reason VARCHAR(128),
    reconciled_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_recon_records_status ON recon_records(status);

-- Verify table creation
\dt
