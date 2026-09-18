\set ON_ERROR_STOP on
BEGIN;

CREATE TABLE public.incidents (
    incident_id VARCHAR(32) PRIMARY KEY,
    severity VARCHAR(16) NOT NULL,
    title TEXT NOT NULL,
    affected_database VARCHAR(128) NOT NULL,
    category VARCHAR(128) NOT NULL,
    assigned_to VARCHAR(128) NOT NULL,
    raised_by VARCHAR(128) NOT NULL,
    status VARCHAR(24) NOT NULL DEFAULT 'OPEN',
    root_cause TEXT,
    remediation_steps JSONB NOT NULL DEFAULT '[]'::jsonb,
    notes TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_incidents_created_at ON public.incidents(created_at DESC);
CREATE INDEX idx_incidents_database ON public.incidents(affected_database);

COMMIT;
\echo 'Incident store committed: test.public.incidents.'