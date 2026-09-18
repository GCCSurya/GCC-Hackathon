import json
import logging
import os


logger = logging.getLogger("incident_store")


class IncidentStore:
    def __init__(self):
        self.database = os.getenv("INCIDENT_DATABASE", "test")
        self.pg_url = os.getenv("POSTGRES_URL") or os.getenv("DATABASE_URL")
        self.pghost = os.getenv("PGHOST")
        self.pguser = os.getenv("PGUSER")
        self.pgpassword = os.getenv("PGPASSWORD")
        self.pgport = os.getenv("PGPORT", "5432")
        self.pgsslmode = os.getenv("PGSSLMODE", "require")

    def _connect(self):
        import psycopg2

        options = {"connect_timeout": 3, "options": "-c statement_timeout=5000"}
        if self.pg_url:
            return psycopg2.connect(self.pg_url, dbname=self.database, **options)
        if not self.pghost:
            raise RuntimeError("PostgreSQL is not configured")
        return psycopg2.connect(
            host=self.pghost,
            user=self.pguser,
            password=self.pgpassword,
            dbname=self.database,
            port=self.pgport,
            sslmode=self.pgsslmode,
            **options,
        )

    def get_next_incident_id(self):
        connection = self._connect()
        try:
            with connection.cursor() as cursor:
                cursor.execute("""
                    SELECT 'INC-' || LPAD((COALESCE(MAX(
                        CASE WHEN incident_id ~ '^INC-[0-9]+$'
                             THEN SUBSTRING(incident_id FROM '[0-9]+$')::integer
                        END
                    ), 457) + 1)::text, 5, '0')
                    FROM public.incidents
                """)
                return cursor.fetchone()[0]
        finally:
            connection.close()

    def save(self, incident):
        connection = self._connect()
        try:
            with connection.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO public.incidents (
                        incident_id, severity, title, affected_database, category,
                        assigned_to, raised_by, root_cause, remediation_steps, notes
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s)
                """, (
                    incident["incident_id"], incident["severity"], incident["title"],
                    incident["database"], incident["category"], incident["assigned_to"],
                    incident["raised_by"], incident.get("root_cause"),
                    json.dumps(incident.get("remediation_steps") or []), incident.get("notes", ""),
                ))
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()
