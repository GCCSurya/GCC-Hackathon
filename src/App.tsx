import { useState, useEffect } from 'react';
import { Header } from './components/Header';
import { FleetStrip } from './components/FleetStrip';
import type { FleetItem } from './components/FleetStrip';
import { KpiRow } from './components/KpiRow';
import type { KpiData } from './components/KpiRow';
import { AnomalyBanner } from './components/AnomalyBanner';
import type { AnomalyInfo } from './components/AnomalyBanner';
import { AgentPanel } from './components/AgentPanel';
import type { DiagnosisData } from './components/AgentPanel';
import { IncidentCard } from './components/IncidentCard';
import type { IncidentData } from './components/IncidentCard';
import { CreateIncidentPage } from './components/CreateIncidentPage';
import { DbaConsolePanel } from './components/DbaConsolePanel';
import { TimelineFooter } from './components/TimelineFooter';
import type { TimelineEntry } from './components/TimelineFooter';
import { DemoControls } from './components/DemoControls';
import { DatabaseStatus } from './components/DatabaseStatus';
import type { ConnectionStatus } from './components/DatabaseStatus';
import { DatabaseExplorer } from './components/DatabaseExplorer';
import './index.css';

// Default initial state matching Section 11/12 spec
const DEFAULT_FLEET: FleetItem[] = [
  { name: 'gcc_banking_core', status: 'AT_RISK', risk_score: 88, status_desc: 'Banking core · Simulated anomaly' },
  { name: 'gcc_reconciliation', status: 'HEALTHY', risk_score: 10, status_desc: 'Reconciliation · Awaiting telemetry' },
  { name: 'gcc_audit_service', status: 'HEALTHY', risk_score: 10, status_desc: 'Audit service · Awaiting telemetry' }
];

const DEFAULT_KPIS: KpiData = {
  active_sessions: 42,
  blocked_sessions: 4,
  cache_hit_ratio: 99.4,
  avg_query_time_ms: 840
};

const DEFAULT_ANOMALY: AnomalyInfo = {
  type: 'LOCK_CONTENTION',
  database: 'gcc_banking_core',
  title: 'Simulated lock contention on public.orders',
  target_table: 'public.orders',
  blocking_pid: 48219,
  wait_event: 'Lock:tuple',
  waiting_count: 4,
  duration_sec: 184
};

const DEFAULT_DIAGNOSIS: DiagnosisData = {
  model: 'dbpulse deterministic RAG fallback',
  root_cause: 'Session PID 48219 has held an uncommitted row lock on table public.orders for over 180s during a bulk update batch. This block is cascading to 4 subsequent transactions attempting write locks on the same partition.',
  citations: 'source: pg_stat_activity, pg_locks',
  remediation_steps: [
    {
      step: 1,
      title: 'Inspect blocking query details',
      sql: 'SELECT pid, now() - query_start AS duration, query, state \nFROM pg_stat_activity WHERE pid = 48219;'
    },
    {
      step: 2,
      title: 'Terminate blocking backend safely',
      sql: 'SELECT pg_cancel_backend(48219); -- Attempt graceful cancellation first\n-- If unresponsive: SELECT pg_terminate_backend(48219);'
    }
  ],
  disclaimer: 'generates SQL for a human to run — nothing executes automatically.'
};

export function App() {
  const [appMode, setAppMode] = useState<'agent' | 'dba'>('agent');
  const [showAgentSuggestion, setShowAgentSuggestion] = useState<boolean>(false);
  const [currentView, setCurrentView] = useState<'dashboard' | 'create-incident'>('dashboard');
  const [fleet, setFleet] = useState<FleetItem[]>(DEFAULT_FLEET);
  const [kpis, setKpis] = useState<KpiData>(DEFAULT_KPIS);
  const [anomaly, setAnomaly] = useState<AnomalyInfo | null>(DEFAULT_ANOMALY);
  const [diagnosis, setDiagnosis] = useState<DiagnosisData | null>(DEFAULT_DIAGNOSIS);
  const [incident, setIncident] = useState<IncidentData | null>(null);
  const [timeline, setTimeline] = useState<TimelineEntry[]>([
    { timestamp: '14:00:00', event: 'Fleet monitoring initialized', type: 'system' },
    { timestamp: '14:02:15', event: 'gcc_banking_core: Simulated anomaly selected (Lock Contention)', type: 'anomaly' },
    { timestamp: '14:02:18', event: 'gcc_banking_core diagnosed by dbpulse (deterministic RAG fallback)', type: 'diagnosis' }
  ]);
  const [lastPolledSecAgo, setLastPolledSecAgo] = useState(2);
  const [activeScenario, setActiveScenario] = useState('LOCK_CONTENTION');
  const [isDiagnosing, setIsDiagnosing] = useState(false);
  const [connection, setConnection] = useState<ConnectionStatus>({
    state: 'checking', message: 'Waiting for a backend telemetry check. Initial dashboard values are demo data.',
  });
  const [selectedDatabase, setSelectedDatabase] = useState('gcc_banking_core');

  // Hash-based back/forward routing support
  useEffect(() => {
    const handleHashChange = () => {
      if (window.location.hash === '#create-incident') {
        setCurrentView('create-incident');
      } else {
        setCurrentView('dashboard');
      }
    };

    window.addEventListener('hashchange', handleHashChange);
    if (window.location.hash === '#create-incident') {
      setCurrentView('create-incident');
    }

    return () => window.removeEventListener('hashchange', handleHashChange);
  }, []);

  const handleNavigate = (view: 'dashboard' | 'create-incident') => {
    setCurrentView(view);
    window.location.hash = view === 'create-incident' ? '#create-incident' : '';
  };

  // Poll backend API (with client fallback)
  useEffect(() => {
    let stopped = false;
    let timer: ReturnType<typeof setTimeout>;
    const fetchData = async () => {
      try {
        const fleetRes = await fetch('/api/fleet', { signal: AbortSignal.timeout(15000) });
        if (!fleetRes.ok) throw new Error('Fleet request failed');
        if (fleetRes.ok) {
          const fleetData = await fleetRes.json();
          setFleet(fleetData.fleet);
          setLastPolledSecAgo(fleetData.last_polled_sec_ago || 1);
        }

        const kpiRes = await fetch(`/api/kpis?db=${encodeURIComponent(selectedDatabase)}`, { signal: AbortSignal.timeout(15000) });
        if (!kpiRes.ok) throw new Error('KPI request failed');
        if (kpiRes.ok) {
          const kpiData = await kpiRes.json();
          setKpis(kpiData.kpis);
          setConnection(kpiData.connection ?? {
            state: 'unknown', message: 'This backend does not report database status. Restart it with the updated code.',
          });
        }

        const anomalyRes = await fetch('/api/anomaly', { signal: AbortSignal.timeout(15000) });
        if (anomalyRes.ok) {
          const anomalyData = await anomalyRes.json();
          setAnomaly(anomalyData.anomaly);
        }

        const timelineRes = await fetch('/api/timeline', { signal: AbortSignal.timeout(15000) });
        if (timelineRes.ok) {
          const timelineData = await timelineRes.json();
          setTimeline(timelineData.timeline);
        }
      } catch {
        setConnection({ state: 'unavailable', message: 'Could not complete the backend poll. Live database connectivity is not confirmed.' });
        // Increment timer if running standalone
        setLastPolledSecAgo(prev => (prev >= 5 ? 1 : prev + 1));
      } finally {
        // Avoid piling up database requests when a connection is slow or unavailable.
        if (!stopped) timer = setTimeout(fetchData, 3000);
      }
    };

    fetchData();
    return () => { stopped = true; clearTimeout(timer); };
  }, [selectedDatabase]);

  // Handle Scenario Switch
  const handleSelectScenario = async (scenario: string) => {
    setActiveScenario(scenario);
    setIncident(null);
    setIsDiagnosing(true);

    try {
      await fetch('/api/trigger-anomaly', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ scenario })
      });

      const diagRes = await fetch('/api/diagnose', { method: 'POST' });
      if (diagRes.ok) {
        const diagData = await diagRes.json();
        setDiagnosis(diagData.diagnosis);
      }
    } catch {
      // Local fallback for static preview
      if (scenario === 'LOCK_CONTENTION') {
        setFleet(DEFAULT_FLEET);
        setKpis(DEFAULT_KPIS);
        setAnomaly(DEFAULT_ANOMALY);
        setDiagnosis(DEFAULT_DIAGNOSIS);
      } else if (scenario === 'POOL_EXHAUSTION') {
        setFleet([
          { name: 'gcc_banking_core', status: 'AT_RISK', risk_score: 92, status_desc: 'Banking core · Simulated connection pool exhaustion' },
          { name: 'gcc_reconciliation', status: 'HEALTHY', risk_score: 10, status_desc: 'Reconciliation · Demo healthy' },
          { name: 'gcc_audit_service', status: 'HEALTHY', risk_score: 10, status_desc: 'Audit service · Demo healthy' }
        ]);
        setKpis({ active_sessions: 98, blocked_sessions: 24, cache_hit_ratio: 96.2, avg_query_time_ms: 1420 });
        setAnomaly({
          type: 'POOL_EXHAUSTION',
          database: 'gcc_banking_core',
          title: 'Max connections reached (98/100 active connections in ClientRead wait)',
          target_table: 'global_pool'
        });
        setDiagnosis({
          model: 'dbpulse deterministic RAG fallback',
          root_cause: 'A simulated connection pool exhaustion scenario was selected for gcc_banking_core.',
          citations: 'source: pg_stat_activity, pg_stat_database',
          remediation_steps: [
            { step: 1, title: 'Inspect idle connections', sql: "SELECT pid, state, now() - state_change FROM pg_stat_activity WHERE state = 'idle in transaction';" },
            { step: 2, title: 'Terminate stale connections (>5m)', sql: "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE state = 'idle in transaction' AND now() - state_change > interval '5 minutes';" }
          ],
          disclaimer: 'generates SQL for a human to run — nothing executes automatically.'
        });
      } else if (scenario === 'RUNAWAY_QUERY') {
        setFleet([
          { name: 'gcc_banking_core', status: 'HEALTHY', risk_score: 10, status_desc: 'Banking core · Demo healthy' },
          { name: 'gcc_reconciliation', status: 'HEALTHY', risk_score: 10, status_desc: 'Reconciliation · Demo healthy' },
          { name: 'gcc_audit_service', status: 'AT_RISK', risk_score: 78, status_desc: 'Audit service · Simulated sequential scan' }
        ]);
        setKpis({ active_sessions: 31, blocked_sessions: 0, cache_hit_ratio: 84.1, avg_query_time_ms: 2100 });
        setAnomaly({
          type: 'RUNAWAY_QUERY',
          database: 'gcc_audit_service',
          title: 'Simulated runaway scan on public.audit_logs',
          target_table: 'public.audit_logs'
        });
        setDiagnosis({
          model: 'dbpulse deterministic RAG fallback',
          root_cause: 'Runaway query PID 31092 scanning 42M rows sequentially on public.audit_logs due to missing predicate index.',
          citations: 'source: pg_stat_activity, DataFileRead wait events',
          remediation_steps: [
            { step: 1, title: 'Cancel runaway query', sql: 'SELECT pg_cancel_backend(31092);' },
            { step: 2, title: 'Create missing index', sql: 'CREATE INDEX CONCURRENTLY idx_audit_logs_payload ON public.audit_logs(payload); ANALYZE public.audit_logs;' }
          ],
          disclaimer: 'generates SQL for a human to run — nothing executes automatically.'
        });
      }
    } finally {
      setIsDiagnosing(false);
    }
  };

  const handleReset = async () => {
    setActiveScenario('HEALTHY');
    setIncident(null);
    setIsDiagnosing(false);

    try {
      await fetch('/api/reset', { method: 'POST' });
    } catch {
      // Local fallback
    }

    setFleet([
      { name: 'gcc_banking_core', status: 'HEALTHY', risk_score: 10, status_desc: 'Banking core · Healthy' },
      { name: 'gcc_reconciliation', status: 'HEALTHY', risk_score: 10, status_desc: 'Reconciliation · Healthy' },
      { name: 'gcc_audit_service', status: 'HEALTHY', risk_score: 10, status_desc: 'Audit service · Healthy' }
    ]);
    setKpis({ active_sessions: 12, blocked_sessions: 0, cache_hit_ratio: 99.8, avg_query_time_ms: 14 });
    setAnomaly(null);
    setDiagnosis(null);
  };

  const handleToggleMode = (mode: 'agent' | 'dba') => {
    setAppMode(mode);
    const nowTime = new Date().toTimeString().split(' ')[0].substring(0, 5);
    setTimeline(prev => [
      ...prev,
      {
        timestamp: nowTime,
        event: mode === 'dba'
          ? 'Operational mode switched: DBA Manual Control (Hands-on SQL inspection active)'
          : 'Operational mode switched: Agent Autonomous Mode (Proactive AI watcher active)',
        type: 'control'
      }
    ]);
  };

  // Called when incident is finalized
  const handleIncidentCreated = (newInc: IncidentData) => {
    setIncident(newInc);
    const nowTime = new Date().toTimeString().split(' ')[0].substring(0, 5);
    setTimeline(prev => [
      ...prev,
      { timestamp: nowTime, event: `Incident registered ${newInc.incident_id} (Assigned: ${newInc.assigned_to})`, type: 'incident' }
    ]);
  };

  return (
    <div className="app-container">
      <Header
        lastPolledSecAgo={lastPolledSecAgo}
        currentView={currentView}
        onNavigate={handleNavigate}
        appMode={appMode}
        onToggleMode={handleToggleMode}
      />

      <DatabaseStatus connection={connection} />

      {currentView === 'create-incident' ? (
        <CreateIncidentPage
          anomaly={anomaly}
          diagnosis={diagnosis}
          fleet={fleet}
          appMode={appMode}
          onCancel={() => handleNavigate('dashboard')}
          onIncidentCreated={handleIncidentCreated}
        />
      ) : (
        <>
          <FleetStrip fleet={fleet} selectedDatabase={selectedDatabase} onSelect={setSelectedDatabase} />
          <KpiRow kpis={kpis} />
          <DatabaseExplorer database={selectedDatabase} />
          <AnomalyBanner anomaly={anomaly} />

          {appMode === 'agent' ? (
            <AgentPanel
              diagnosis={diagnosis}
              onRaiseIncident={() => handleNavigate('create-incident')}
              incidentRaised={!!incident}
              isDiagnosing={isDiagnosing}
            />
          ) : (
            <DbaConsolePanel
              anomaly={anomaly}
              diagnosis={diagnosis}
              onCreateIncident={() => handleNavigate('create-incident')}
              onConsultAgent={() => setShowAgentSuggestion(prev => !prev)}
              showAgentSuggestion={showAgentSuggestion}
            />
          )}

          <IncidentCard incident={incident} />
          <DemoControls
            activeScenario={activeScenario}
            onSelectScenario={handleSelectScenario}
            onReset={handleReset}
          />
        </>
      )}

      <TimelineFooter timeline={timeline} />
    </div>
  );
}

export default App;
