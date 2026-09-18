\set ON_ERROR_STOP on
BEGIN;

CREATE TABLE public.audit_logs (
    log_id BIGINT PRIMARY KEY, user_id VARCHAR(64), action VARCHAR(64), entity_type VARCHAR(64), entity_id INT,
    payload TEXT, ip_address VARCHAR(45), status_code INT, created_at TIMESTAMP
);
CREATE TABLE public.application_users (
    user_id VARCHAR(64) PRIMARY KEY, event_count INT NOT NULL, last_seen_at TIMESTAMP, status VARCHAR(16) NOT NULL
);
CREATE TABLE public.security_events (
    event_id BIGSERIAL PRIMARY KEY, log_id BIGINT NOT NULL REFERENCES public.audit_logs(log_id),
    event_type VARCHAR(64), severity VARCHAR(16), source_ip VARCHAR(45), detected_at TIMESTAMP
);
CREATE TABLE public.event_rules (
    rule_id SERIAL PRIMARY KEY, rule_name VARCHAR(64) UNIQUE NOT NULL, severity VARCHAR(16), enabled BOOLEAN DEFAULT true
);

\copy public.audit_logs FROM 'audit_logs.csv' WITH (FORMAT csv, HEADER true)
INSERT INTO public.application_users(user_id, event_count, last_seen_at, status)
SELECT user_id, count(*), max(created_at), 'ACTIVE' FROM public.audit_logs GROUP BY user_id;
INSERT INTO public.security_events(log_id, event_type, severity, source_ip, detected_at)
SELECT log_id, action, CASE WHEN status_code >= 500 THEN 'HIGH' WHEN status_code >= 400 THEN 'MEDIUM' ELSE 'LOW' END,
       ip_address, created_at FROM public.audit_logs WHERE status_code >= 400;
INSERT INTO public.event_rules(rule_name, severity) VALUES
('SERVER_ERROR', 'HIGH'), ('ACCESS_DENIED', 'MEDIUM'), ('RISK_OVERRIDE', 'HIGH');

CREATE INDEX idx_audit_created ON public.audit_logs(created_at);
CREATE INDEX idx_security_severity ON public.security_events(severity);
ANALYZE;
COMMIT;