-- =============================================================================
-- Scenario Simulation Scripts for PostgreSQL testdb (PNC Hackathon: dbpulse)
-- =============================================================================
-- These queries let you reproduce the real anomalies monitored by the dbpulse agent.

-- -----------------------------------------------------------------------------
-- SCENARIO 1: Lock Contention on public.orders
-- -----------------------------------------------------------------------------
-- In Terminal 1 (The Blocker):
-- Start a transaction, acquire an exclusive row lock, and leave it uncommitted:
BEGIN;
UPDATE orders 
SET status = 'PROCESSING', updated_at = NOW() 
WHERE order_id = 10042;
-- (Do NOT run COMMIT; leave this session open to hold the row lock)

-- In Terminal 2 (Blocked Session A):
BEGIN;
UPDATE orders 
SET status = 'COMPLETED', updated_at = NOW() 
WHERE order_id = 10042;
-- (Notice: This will hang waiting for Terminal 1 to release the lock)

-- In Terminal 3 (Blocked Session B):
BEGIN;
UPDATE orders 
SET amount = amount + 50.00, updated_at = NOW() 
WHERE order_id = 10042;
-- (Notice: Also blocked!)

-- In Terminal 4 (Monitoring Query - see the locks in real time):
SELECT 
    pid, 
    pg_blocking_pids(pid) AS blocked_by, 
    wait_event_type, 
    wait_event, 
    state, 
    now() - query_start AS duration, 
    query 
FROM pg_stat_activity 
WHERE wait_event_type = 'Lock' OR pg_blocking_pids(pid) <> '{}';

-- Agent Remediation Query (to unblock):
-- SELECT pg_cancel_backend(<BLOCKING_PID>);


-- -----------------------------------------------------------------------------
-- SCENARIO 2: Runaway Sequential Scan Query on public.audit_logs
-- -----------------------------------------------------------------------------
-- Simulates a query scanning all unindexed rows with intensive regex or text matching:

EXPLAIN ANALYZE
SELECT count(*), entity_type, max(created_at)
FROM audit_logs
WHERE payload LIKE '%Elevated risk threshold exceeded%'
  AND status_code >= 400
GROUP BY entity_type;

-- To generate heavy load / long execution:
SELECT count(*), max(payload)
FROM audit_logs a1
CROSS JOIN (SELECT generate_series(1, 500)) s
WHERE a1.payload ILIKE '%review_required%'
  AND md5(a1.payload) NOT LIKE '%000%';

-- Agent Remediation Query:
-- CREATE INDEX CONCURRENTLY idx_audit_logs_payload ON public.audit_logs(payload);
-- ANALYZE public.audit_logs;


-- -----------------------------------------------------------------------------
-- SCENARIO 3: Connection Pool Exhaustion (Idle in Transaction sessions)
-- -----------------------------------------------------------------------------
-- Check active vs idle connections:
SELECT 
    count(*) AS total_connections,
    count(*) FILTER (WHERE state = 'active') AS active,
    count(*) FILTER (WHERE state = 'idle in transaction') AS idle_in_tx,
    count(*) FILTER (WHERE state = 'idle') AS idle
FROM pg_stat_activity;

-- Identify sessions lingering in 'idle in transaction':
SELECT 
    pid, 
    usename, 
    client_addr, 
    now() - state_change AS idle_duration, 
    query 
FROM pg_stat_activity 
WHERE state = 'idle in transaction' 
ORDER BY idle_duration DESC;

-- Terminate stale idle connections (> 5 minutes):
-- SELECT pg_terminate_backend(pid) 
-- FROM pg_stat_activity 
-- WHERE state = 'idle in transaction' 
--   AND now() - state_change > interval '5 minutes';
