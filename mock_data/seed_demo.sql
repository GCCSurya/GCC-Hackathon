\set ON_ERROR_STOP on

BEGIN;
CREATE SCHEMA dbpulse_demo;
SET LOCAL search_path TO dbpulse_demo;

\ir schema.sql
\ir import_data.sql

COMMIT;
\echo 'Committed demo dataset in dbpulse_demo. Existing schemas were not modified.'