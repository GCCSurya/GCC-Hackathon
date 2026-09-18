import React, { useState } from 'react';
import type { AnomalyInfo } from './AnomalyBanner';
import type { DiagnosisData } from './AgentPanel';

interface DbaConsolePanelProps {
  anomaly: AnomalyInfo | null;
  diagnosis: DiagnosisData | null;
  onCreateIncident: () => void;
  onConsultAgent: () => void;
  showAgentSuggestion: boolean;
}

interface QueryResultRow {
  pid: number;
  blocked_by: string;
  wait_event: string;
  state: string;
  duration: string;
  query: string;
}

const SAMPLE_LOCK_ROWS: QueryResultRow[] = [
  { pid: 48219, blocked_by: 'None (Root Blocker)', wait_event: 'ClientRead', state: 'active', duration: '184s', query: "UPDATE public.orders SET status = 'PROCESSING' WHERE order_id = 10042;" },
  { pid: 48225, blocked_by: '48219', wait_event: 'Lock:tuple', state: 'active', duration: '162s', query: "UPDATE public.orders SET status = 'COMPLETED' WHERE order_id = 10042;" },
  { pid: 48228, blocked_by: '48219', wait_event: 'Lock:tuple', state: 'active', duration: '115s', query: "UPDATE public.orders SET amount = amount + 50.00 WHERE order_id = 10042;" },
  { pid: 48231, blocked_by: '48219', wait_event: 'Lock:tuple', state: 'active', duration: '94s', query: "SELECT * FROM public.orders WHERE order_id = 10042 FOR UPDATE;" }
];

const SAMPLE_POOL_ROWS: QueryResultRow[] = [
  { pid: 31012, blocked_by: 'None', wait_event: 'ClientRead', state: 'idle in transaction', duration: '412s', query: "SELECT * FROM public.accounts WHERE customer_id = 1042;" },
  { pid: 31015, blocked_by: 'None', wait_event: 'ClientRead', state: 'idle in transaction', duration: '389s', query: "BEGIN; UPDATE public.accounts SET balance = balance - 100;" },
  { pid: 31020, blocked_by: 'None', wait_event: 'ClientRead', state: 'idle in transaction', duration: '350s', query: "SELECT count(*) FROM public.recon_records;" }
];

const SAMPLE_SCAN_ROWS: QueryResultRow[] = [
  { pid: 31092, blocked_by: 'None', wait_event: 'DataFileRead', state: 'active', duration: '412s', query: "SELECT count(*) FROM public.audit_logs WHERE payload LIKE '%Elevated risk%';" }
];

export const DbaConsolePanel: React.FC<DbaConsolePanelProps> = ({
  anomaly,
  diagnosis,
  onCreateIncident,
  onConsultAgent,
  showAgentSuggestion
}) => {
  const [selectedQueryType, setSelectedQueryType] = useState<'locks' | 'pool' | 'scans'>('locks');
  const [sqlWorkbench, setSqlWorkbench] = useState<string>(
    anomaly?.blocking_pid
      ? `SELECT pg_cancel_backend(${anomaly.blocking_pid});`
      : 'SELECT pid, pg_blocking_pids(pid), wait_event, query FROM pg_stat_activity WHERE wait_event_type = \'Lock\';'
  );
  const [executionOutput, setExecutionOutput] = useState<string | null>(null);

  const getActiveRows = (): QueryResultRow[] => {
    if (selectedQueryType === 'pool') return SAMPLE_POOL_ROWS;
    if (selectedQueryType === 'scans') return SAMPLE_SCAN_ROWS;
    return SAMPLE_LOCK_ROWS;
  };

  const handleRunSql = () => {
    setExecutionOutput(`[Query Executed] ${new Date().toLocaleTimeString()} UTC — 1 row affected.\npg_cancel_backend: true (Signal SIGINT sent to backend process).`);
    setTimeout(() => setExecutionOutput(null), 5000);
  };

  return (
    <div className="dba-console-panel">
      {/* Header */}
      <div className="dba-panel-header">
        <div className="dba-title-group">
          <div className="dba-badge-icon">🛠️</div>
          <div>
            <span className="dba-panel-title">DBA Manual Triage Console</span>
            <span className="dba-panel-subtitle">Direct SQL Inspection & Manual Remediation Workbench</span>
          </div>
        </div>
        <div className="dba-mode-indicator">
          <span className="manual-pulse"></span>
          <span>MANUAL CONTROL ACTIVE</span>
        </div>
      </div>

      {/* Interactive Diagnostic Query Selector */}
      <div className="dba-query-selector">
        <span className="selector-label">Manual Telemetry Queries:</span>
        <div className="query-btn-group">
          <button
            className={`btn-query-tab ${selectedQueryType === 'locks' ? 'active' : ''}`}
            onClick={() => {
              setSelectedQueryType('locks');
              setSqlWorkbench('SELECT pid, pg_blocking_pids(pid), wait_event, query FROM pg_stat_activity WHERE wait_event_type = \'Lock\';');
            }}
          >
            1. Lock Contention (`pg_locks`)
          </button>
          <button
            className={`btn-query-tab ${selectedQueryType === 'pool' ? 'active' : ''}`}
            onClick={() => {
              setSelectedQueryType('pool');
              setSqlWorkbench("SELECT pid, state, now() - state_change AS idle_time FROM pg_stat_activity WHERE state = 'idle in transaction';");
            }}
          >
            2. Idle Connections (`ClientRead`)
          </button>
          <button
            className={`btn-query-tab ${selectedQueryType === 'scans' ? 'active' : ''}`}
            onClick={() => {
              setSelectedQueryType('scans');
              setSqlWorkbench("SELECT pid, now() - query_start AS runtime, query FROM pg_stat_activity WHERE wait_event = 'DataFileRead';");
            }}
          >
            3. Table Scans (`DataFileRead`)
          </button>
        </div>
      </div>

      {/* Raw Output Inspector Table */}
      <div className="dba-table-container">
        <div className="table-header-label">
          <span>Live Session Query Output (PNCPRD01)</span>
          <span className="table-count-badge">{getActiveRows().length} sessions detected</span>
        </div>
        <div className="table-scroll-wrapper">
          <table className="dba-raw-table">
            <thead>
              <tr>
                <th>PID</th>
                <th>Blocked By</th>
                <th>Wait Event</th>
                <th>State</th>
                <th>Duration</th>
                <th>Query</th>
              </tr>
            </thead>
            <tbody>
              {getActiveRows().map((row) => (
                <tr key={row.pid} className={row.blocked_by.includes('Root') ? 'row-blocker' : ''}>
                  <td className="mono-val pid-col">{row.pid}</td>
                  <td className="mono-val">{row.blocked_by}</td>
                  <td className="mono-val wait-col">{row.wait_event}</td>
                  <td><span className="state-tag">{row.state}</span></td>
                  <td className="mono-val duration-col">{row.duration}</td>
                  <td className="mono-val query-col">{row.query}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Manual Remediation Workbench */}
      <div className="dba-workbench-box">
        <div className="workbench-header">
          <span className="workbench-title">Manual Remediation Query Buffer:</span>
          <span className="workbench-tip">Execute directly or attach to manual incident</span>
        </div>
        <textarea
          className="dba-sql-input"
          rows={3}
          value={sqlWorkbench}
          onChange={(e) => setSqlWorkbench(e.target.value)}
          placeholder="Enter PostgreSQL administrative query..."
        />
        <div className="workbench-actions">
          <button className="btn-dba-execute" onClick={handleRunSql}>
            ▶ Run Query on PNCPRD01
          </button>
          {executionOutput && (
            <span className="dba-exec-output">{executionOutput}</span>
          )}
        </div>
      </div>

      {/* Optional Agent Consult Box */}
      {showAgentSuggestion && diagnosis && (
        <div className="dba-agent-consult-box">
          <div className="consult-header">
            <span className="consult-tag">AI Copilot Recommendation</span>
            <span className="consult-model">{diagnosis.model}</span>
          </div>
          <p className="consult-text">{diagnosis.root_cause}</p>
          <div className="consult-sql">
            {diagnosis.remediation_steps.map(s => (
              <code key={s.step}>{s.sql}</code>
            ))}
          </div>
        </div>
      )}

      {/* Actions Row */}
      <div className="dba-actions-footer">
        <button
          className="btn-consult-agent"
          onClick={onConsultAgent}
        >
          {showAgentSuggestion ? 'Hide AI Suggestion' : '🤖 Ask Agent for Suggestion'}
        </button>

        <button
          className="btn-create-manual-inc"
          onClick={onCreateIncident}
        >
          + Create Incident Manually
        </button>
      </div>
    </div>
  );
};
