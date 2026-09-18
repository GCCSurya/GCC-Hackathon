\set ON_ERROR_STOP on
BEGIN;

CREATE TABLE public.recon_records (
    recon_id INT PRIMARY KEY, source_system VARCHAR(64), external_ref VARCHAR(64), internal_order_id INT,
    amount NUMERIC(15,2), currency VARCHAR(3), status VARCHAR(32), discrepancy_reason VARCHAR(128), reconciled_at TIMESTAMP
);
CREATE TABLE public.recon_batches (
    batch_id BIGSERIAL PRIMARY KEY, source_system VARCHAR(64) NOT NULL, record_count INT NOT NULL,
    total_amount NUMERIC(18,2) NOT NULL, batch_status VARCHAR(32) NOT NULL, processed_at TIMESTAMP
);
CREATE TABLE public.recon_exceptions (
    exception_id BIGSERIAL PRIMARY KEY, recon_id INT NOT NULL REFERENCES public.recon_records(recon_id),
    reason VARCHAR(128), severity VARCHAR(16), resolved BOOLEAN DEFAULT false, created_at TIMESTAMP
);
CREATE TABLE public.source_systems (
    source_system VARCHAR(64) PRIMARY KEY, active BOOLEAN NOT NULL DEFAULT true, last_reconciled_at TIMESTAMP
);

\copy public.recon_records FROM 'recon_records.csv' WITH (FORMAT csv, HEADER true)
INSERT INTO public.source_systems(source_system, last_reconciled_at)
SELECT source_system, max(reconciled_at) FROM public.recon_records GROUP BY source_system;
INSERT INTO public.recon_batches(source_system, record_count, total_amount, batch_status, processed_at)
SELECT source_system, count(*), sum(amount), 'COMPLETED', max(reconciled_at) FROM public.recon_records GROUP BY source_system;
INSERT INTO public.recon_exceptions(recon_id, reason, severity, created_at)
SELECT recon_id, discrepancy_reason, CASE WHEN status = 'DISCREPANCY' THEN 'HIGH' ELSE 'MEDIUM' END, reconciled_at
FROM public.recon_records WHERE status IN ('DISCREPANCY', 'UNMATCHED');

CREATE INDEX idx_recon_status ON public.recon_records(status);
CREATE INDEX idx_recon_exceptions_record ON public.recon_exceptions(recon_id);
ANALYZE;
COMMIT;