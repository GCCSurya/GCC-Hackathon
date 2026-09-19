export interface ConnectionStatus {
  state: 'checking' | 'unchecked' | 'connected' | 'not_configured' | 'error' | 'unavailable' | 'unknown';
  message: string;
  simulation_enabled?: boolean;
}

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
      <strong style={{ color: 'var(--dba-amber)' }}>{connection.message}</strong>
      {connection.simulation_enabled && (
        <div style={{ color: 'var(--text-secondary)', marginTop: 4 }}>Simulation enabled</div>
      )}
    </div>
  );
}