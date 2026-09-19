import { useState, useEffect, useRef } from 'react';
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

const anomalyKey = (value: AnomalyInfo | null) => value
  ? JSON.stringify([value.database, value.type, value.target_table, value.blocking_pid, value.wait_event])
  : null;
const EMPTY_KPIS: KpiData = { active_sessions: null, blocked_sessions: null, cache_hit_ratio: null, avg_query_time_ms: null };
// Default initial state matching Section 11/12 spec

export function App() {
  const [appMode, setAppMode] = useState<'agent' | 'dba'>('agent');
  const [showAgentSuggestion, setShowAgentSuggestion] = useState<boolean>(false);
  const [currentView, setCurrentView] = useState<'dashboard' | 'create-incident'>('dashboard');
  const [fleet, setFleet] = useState<FleetItem[]>([]);
  const [kpis, setKpis] = useState<KpiData>(EMPTY_KPIS);
  const [anomaly, setAnomaly] = useState<AnomalyInfo | null>(null);
  const [diagnosis, setDiagnosis] = useState<DiagnosisData | null>(null);
  const [incident, setIncident] = useState<IncidentData | null>(null);
  const [timeline, setTimeline] = useState<TimelineEntry[]>([]);
  const [lastPolledSecAgo, setLastPolledSecAgo] = useState(2);
  const [activeScenario, setActiveScenario] = useState('HEALTHY');
  const [simulationEnabled, setSimulationEnabled] = useState(false);
  const [isDiagnosing, setIsDiagnosing] = useState(false);
  const [connection, setConnection] = useState<ConnectionStatus>({
    state: 'checking', message: 'Waiting for a backend telemetry check.',
  });
  const [selectedDatabase, setSelectedDatabase] = useState('gcc_banking_core');
  const lastDiagnosedAnomaly = useRef<string | null>(null);
  const requestGeneration = useRef(0);
  const [refreshVersion, setRefreshVersion] = useState(0);

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
    const generation = ++requestGeneration.current;
    const isCurrent = () => !stopped && generation === requestGeneration.current;
    const fetchData = async () => {
      try {
        const fleetRes = await fetch('/api/fleet', { signal: AbortSignal.timeout(15000) });
        if (!fleetRes.ok) throw new Error('Fleet request failed');
        if (fleetRes.ok) {
          const fleetData = await fleetRes.json();
          if (!isCurrent()) return;
          setFleet(fleetData.fleet);
          setSimulationEnabled(fleetData.simulation_enabled === true);
          setActiveScenario(fleetData.active_scenario ?? 'HEALTHY');
          setLastPolledSecAgo(fleetData.last_polled_sec_ago || 1);
        }

        const kpiRes = await fetch(`/api/kpis?db=${encodeURIComponent(selectedDatabase)}`, { signal: AbortSignal.timeout(15000) });
        if (!kpiRes.ok) throw new Error('KPI request failed');
        if (kpiRes.ok) {
          const kpiData = await kpiRes.json();
          if (!isCurrent()) return;
          setKpis(kpiData.kpis);
          setConnection(kpiData.connection ?? {
            state: 'unknown', message: 'This backend does not report database status. Restart it with the updated code.',
          });
        }

        const anomalyRes = await fetch('/api/anomaly', { signal: AbortSignal.timeout(15000) });
        if (!anomalyRes.ok) throw new Error('Anomaly request failed');
        if (anomalyRes.ok) {
          const anomalyData = await anomalyRes.json();
          if (!isCurrent()) return;
          const nextAnomaly = anomalyData.anomaly as AnomalyInfo | null;
          setAnomaly(nextAnomaly);
          if (lastDiagnosedAnomaly.current !== anomalyKey(nextAnomaly)) {
            setDiagnosis(null);
            lastDiagnosedAnomaly.current = null;
          }
          if (!nextAnomaly) {
            lastDiagnosedAnomaly.current = null;
            setDiagnosis(null);
          } else if ((appMode === 'agent' || showAgentSuggestion) && lastDiagnosedAnomaly.current !== anomalyKey(nextAnomaly)) {
            setDiagnosis(null);
            setIsDiagnosing(true);
            try {
              const diagnosisRes = await fetch('/api/diagnose', { method: 'POST', signal: AbortSignal.timeout(30000) });
              if (!diagnosisRes.ok) throw new Error('Diagnosis request failed');
              if (diagnosisRes.ok) {
                const diagnosisData = await diagnosisRes.json();
                if (!isCurrent() || anomalyKey(diagnosisData.anomaly) !== anomalyKey(nextAnomaly)) return;
                setDiagnosis(diagnosisData.diagnosis);
                lastDiagnosedAnomaly.current = anomalyKey(nextAnomaly);
              }
            } finally {
              if (isCurrent()) setIsDiagnosing(false);
            }
          }
        }

        const timelineRes = await fetch('/api/timeline', { signal: AbortSignal.timeout(15000) });
        if (timelineRes.ok) {
          const timelineData = await timelineRes.json();
          if (!isCurrent()) return;
          setTimeline(timelineData.timeline);
        }
      } catch {
        if (!isCurrent()) return;
        setAnomaly(null);
        setKpis(EMPTY_KPIS);
        setFleet(previous => previous.map(database => ({
          ...database, status: 'UNAVAILABLE', risk_score: null,
          data_source: 'unavailable', status_desc: 'Telemetry unavailable',
        })));
        setDiagnosis(null);
        lastDiagnosedAnomaly.current = null;
        setConnection({ state: 'unavailable', message: 'Could not complete the backend poll. Live database connectivity is not confirmed.' });
        // Increment timer if running standalone
        setLastPolledSecAgo(prev => (prev >= 5 ? 1 : prev + 1));
      } finally {
        // Avoid piling up database requests when a connection is slow or unavailable.
        if (isCurrent()) timer = setTimeout(fetchData, 3000);
      }
    };

    fetchData();
    return () => { stopped = true; clearTimeout(timer); };
  }, [selectedDatabase, appMode, showAgentSuggestion, refreshVersion]);

  // Handle Scenario Switch
  const invalidateDiagnosis = () => {
    requestGeneration.current += 1;
    lastDiagnosedAnomaly.current = null;
    setDiagnosis(null);
    setIsDiagnosing(false);
  };

  const handleSelectScenario = async (scenario: string) => {
    invalidateDiagnosis();
    setIncident(null);
    try {
      const response = await fetch(scenario === 'HEALTHY' ? '/api/reset' : '/api/trigger-anomaly', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ scenario }),
        signal: AbortSignal.timeout(15000),
      });
      if (!response.ok) throw new Error('Scenario request failed');
      const data = await response.json();
      if (!data.success) throw new Error('Scenario rejected');
      setActiveScenario(data.active_scenario);
    } catch {
      setConnection({ state: 'unavailable', message: 'Scenario change failed. Refreshing backend status.' });
    } finally {
      setRefreshVersion(previous => previous + 1);
    }
  };

  const handleToggleMode = (mode: 'agent' | 'dba') => {
    invalidateDiagnosis();
    setShowAgentSuggestion(false);
    setRefreshVersion(previous => previous + 1);
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
              onConsultAgent={() => {
                invalidateDiagnosis();
                setShowAgentSuggestion(true);
                setRefreshVersion(previous => previous + 1);
              }}
              showAgentSuggestion={showAgentSuggestion}
            />
          )}

          <IncidentCard incident={incident} />
          {simulationEnabled && <DemoControls
            activeScenario={activeScenario}
            onSelectScenario={handleSelectScenario}
            onReset={() => handleSelectScenario('HEALTHY')}
          />}
        </>
      )}

      <TimelineFooter timeline={timeline} />
    </div>
  );
}

export default App;
