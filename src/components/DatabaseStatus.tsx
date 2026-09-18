export interface ConnectionStatus {
  state: 'checking' | 'unchecked' | 'connected' | 'not_configured' | 'error' | 'unavailable' | 'unknown';
  message: string;
}

const LABELS: Record<ConnectionStatus['state'], string> = {
  checking: 'Checking database status',
  unchecked: 'Database not checked yet',
  connected: 'PostgreSQL connected · Mixed live/demo data',
  not_configured: 'Demo data · Database not configured',
  error: 'Demo fallback · Database check failed',
  unavailable: 'Backend unavailable · Data may be stale or demo',
  unknown: 'Database status unknown · Restart updated backend',
};

export function DatabaseStatus({ connection }: { connection: ConnectionStatus }) {
  return (
    <div role="status" style={{
      padding: '12px 16px',
      marginBottom: 16,
      border: '1px solid var(--dba-amber-border)',
      borderRadius: 8,
      background: 'var(--dba-amber-bg)',
      fontSize: 13,
    }}>
      <strong style={{ color: 'var(--dba-amber)' }}>{LABELS[connection.state]}</strong>
      <div style={{ color: 'var(--text-secondary)', marginTop: 4 }}>{connection.message}</div>
    </div>
  );
}