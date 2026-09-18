\set ON_ERROR_STOP on
\connect gcc_banking_core
\ir seed_banking_core.sql
\connect gcc_reconciliation
\ir seed_reconciliation.sql
\connect gcc_audit_service
\ir seed_audit_service.sql
\echo 'GCC fleet seed committed: 3 databases, 12 tables.'