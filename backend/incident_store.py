import json
import logging
import os
import secrets


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

    def check_readiness(self):
        inserted_columns = {
            "incident_id", "severity", "title", "affected_database", "category",
            "assigned_to", "raised_by", "root_cause", "remediation_steps", "notes",
        }
        expected_columns = inserted_columns | {"status", "created_at"}
        connection = None
        ready = False
        try:
            connection = self._connect()
            connection.set_session(readonly=True)
            with connection.cursor() as cursor:
                cursor.execute("""
                    SELECT relation.oid, has_schema_privilege(namespace.oid, 'USAGE')
                    FROM pg_catalog.pg_class AS relation
                    JOIN pg_catalog.pg_namespace AS namespace ON namespace.oid = relation.relnamespace
                    WHERE namespace.nspname = 'public' AND relation.relname = 'incidents'
                      AND relation.relkind IN ('r', 'p')
                """)
                relation = cursor.fetchone()
                if not relation or not relation[1]:
                    raise RuntimeError("Incident table unavailable")
                cursor.execute("""
                    SELECT attribute.attname, type.typname, attribute.attnotnull,
                           defaults.oid IS NOT NULL, attribute.attidentity, attribute.attgenerated,
                           pg_get_serial_sequence('public.incidents', attribute.attname),
                           has_column_privilege(attribute.attrelid, attribute.attnum, 'INSERT'),
                           has_column_privilege(attribute.attrelid, attribute.attnum, 'SELECT')
                    FROM pg_catalog.pg_attribute AS attribute
                    JOIN pg_catalog.pg_type AS type ON type.oid = attribute.atttypid
                    LEFT JOIN pg_catalog.pg_attrdef AS defaults
                      ON defaults.adrelid = attribute.attrelid AND defaults.adnum = attribute.attnum
                    WHERE attribute.attrelid = %s AND attribute.attnum > 0 AND NOT attribute.attisdropped
                """, (relation[0],))
                columns = {column[0]: column for column in cursor.fetchall()}
                if not expected_columns.issubset(columns):
                    raise RuntimeError("Incident columns unavailable")
                for name, column in columns.items():
                    _, type_name, not_null, has_default, identity, generated, sequence, can_insert, can_select = column
                    if name in expected_columns:
                        accepted_types = (
                            {"jsonb"} if name == "remediation_steps" else
                            {"timestamp", "timestamptz"} if name == "created_at" else
                            {"text", "varchar", "bpchar"}
                        )
                        if type_name not in accepted_types:
                            raise RuntimeError("Incident column type incompatible")
                    if name in inserted_columns and (not can_insert or generated or identity == 'a'):
                        raise RuntimeError("Incident insert unavailable")
                    if name == "incident_id" and not can_select:
                        raise RuntimeError("Incident lookup unavailable")
                    if name not in inserted_columns:
                        if not_null and not (has_default or identity or generated):
                            raise RuntimeError("Incident column default unavailable")
                        if sequence and not identity and not generated:
                            cursor.execute("SELECT has_sequence_privilege(%s, 'USAGE,UPDATE')", (sequence,))
                            if not cursor.fetchone()[0]:
                                raise RuntimeError("Incident sequence unavailable")
            ready = True
        except Exception:
            ready = False
        finally:
            if connection is not None:
                try:
                    connection.close()
                except Exception:
                    ready = False
        return {
            "state": "connected" if ready else "error",
            "database": self.database,
            "message": "Incident storage is ready." if ready else "Incident storage is unavailable or incompatible.",
        }

    def get_next_incident_id(self):
        connection = self._connect()
        try:
            with connection.cursor() as cursor:
                for _ in range(10):
                    incident_id = f"INC-{secrets.token_hex(4).upper()}"
                    cursor.execute(
                        "SELECT EXISTS (SELECT 1 FROM public.incidents WHERE incident_id = %s)",
                        (incident_id,),
                    )
                    if not cursor.fetchone()[0]:
                        return incident_id
            raise RuntimeError("Could not allocate a unique incident ID")
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
