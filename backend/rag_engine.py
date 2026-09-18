import logging

logger = logging.getLogger("rag_engine")

KNOWLEDGE_BASE = [
    {
        "id": "kb_lock_contention",
        "category": "Lock:tuple",
        "keywords": ["lock", "blocking", "blocked", "tuple", "orders", "exclusive"],
        "title": "PostgreSQL Row Lock Contention & Transaction Blocks",
        "content": """
PostgreSQL Row Lock Contention occurs when a transaction acquires an exclusive row-level lock (e.g. via UPDATE, SELECT FOR UPDATE, or DELETE) and remains uncommitted for an extended duration.
Symptoms: Multiple backend processes in 'Lock:tuple' or 'Lock:transactionid' wait state, rapid increase in blocked_sessions metric.
Diagnostic Query:
  SELECT pid, pg_blocking_pids(pid) as blocked_by, query, now() - query_start as duration 
  FROM pg_stat_activity WHERE wait_event_type = 'Lock';
Remediation Protocol:
  1. Inspect blocking process PID using pg_stat_activity.
  2. Attempt graceful query cancellation: SELECT pg_cancel_backend(blocking_pid);
  3. If process does not terminate within 15 seconds, execute forceful termination: SELECT pg_terminate_backend(blocking_pid);
  4. Ensure application code uses strict query timeouts (statement_timeout = 30000ms).
"""
    },
    {
        "id": "kb_pool_exhaustion",
        "category": "ClientRead",
        "keywords": ["pool", "connection", "max_connections", "clientread", "exhaustion"],
        "title": "PostgreSQL Connection Pool Exhaustion & Idle Connections",
        "content": """
Connection Pool Exhaustion occurs when application clients open connections exceeding max_connections or application connection pool limits without returning them.
Symptoms: High active_sessions ratio (>90%), client connection timeouts, wait event 'ClientRead'.
Diagnostic Query:
  SELECT state, count(*) FROM pg_stat_activity GROUP BY state;
Remediation Protocol:
  1. Identify leaked 'idle in transaction' backends:
     SELECT pid, now() - state_change as idle_duration FROM pg_stat_activity WHERE state = 'idle in transaction';
  2. Terminate stale idle connections:
     SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE state = 'idle in transaction' AND now() - state_change > interval '5 minutes';
  3. Deploy connection pooling layer (e.g. PgBouncer) or increase idle_in_transaction_session_timeout.
"""
    },
    {
        "id": "kb_runaway_query",
        "category": "DataFileRead",
        "keywords": ["runaway", "scan", "sequential", "audit_logs", "index", "datafileread", "cpu"],
        "title": "PostgreSQL Sequential Scan & Long-Running Runaway Query",
        "content": """
Runaway queries occur when a query executes a sequential scan over tens of millions of rows due to missing indexes or stale table statistics.
Symptoms: High disk read I/O, wait event 'DataFileRead', low cache hit ratio, query execution time > 300 seconds.
Diagnostic Query:
  SELECT pid, now() - query_start as runtime, query 
  FROM pg_stat_activity WHERE state = 'active' ORDER BY runtime DESC LIMIT 5;
Remediation Protocol:
  1. Inspect query execution plan using EXPLAIN (ANALYZE, BUFFERS).
  2. Cancel current runaway execution: SELECT pg_cancel_backend(runaway_pid);
  3. Create missing index on predicate columns (e.g. CREATE INDEX CONCURRENTLY idx_tablename_col ON tablename(col);).
  4. Run ANALYZE tablename to refresh planner statistics.
"""
    }
]

class RAGEngine:
    def __init__(self):
        self.documents = KNOWLEDGE_BASE
        logger.info(f"RAGEngine initialized with {len(self.documents)} knowledge documents")

    def retrieve_relevant_docs(self, query_text, top_k=2):
        query_words = set(query_text.lower().split())
        scored_docs = []
        
        for doc in self.documents:
            score = 0
            # Match keywords
            for kw in doc["keywords"]:
                if kw.lower() in query_text.lower():
                    score += 3
            # Match content words
            doc_words = set(doc["content"].lower().split())
            overlap = len(query_words.intersection(doc_words))
            score += overlap
            
            scored_docs.append((score, doc))
            
        scored_docs.sort(key=lambda x: x[0], reverse=True)
        return [doc for score, doc in scored_docs[:top_k]]
