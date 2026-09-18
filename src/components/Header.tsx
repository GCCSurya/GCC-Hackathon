import React from 'react';

interface HeaderProps {
  lastPolledSecAgo: number;
  currentView?: 'dashboard' | 'create-incident';
  onNavigate?: (view: 'dashboard' | 'create-incident') => void;
  appMode?: 'agent' | 'dba';
  onToggleMode?: (mode: 'agent' | 'dba') => void;
}

export const Header: React.FC<HeaderProps> = ({
  lastPolledSecAgo,
  currentView = 'dashboard',
  onNavigate,
  appMode = 'agent',
  onToggleMode
}) => {
  return (
    <header className="header-container">
      <div className="brand-group" onClick={() => onNavigate && onNavigate('dashboard')} style={{ cursor: 'pointer' }}>
        <span className="brand-title">dbpulse</span>
        <span className="brand-subtitle">Postgres reliability agent</span>
      </div>

      {/* Mode Switcher: Agent Mode vs DBA Mode */}
      {onToggleMode && (
        <div className="mode-toggle-pill">
          <button
            type="button"
            className={`mode-pill-btn ${appMode === 'agent' ? 'active-agent' : ''}`}
            onClick={() => onToggleMode('agent')}
            title="Agent Mode: Autonomous monitoring, RAG diagnosis & auto-remediation"
          >
            <span className="mode-icon">🤖</span>
            <span>Agent Mode</span>
            {appMode === 'agent' && <span className="mode-active-dot agent-dot"></span>}
          </button>
          <button
            type="button"
            className={`mode-pill-btn ${appMode === 'dba' ? 'active-dba' : ''}`}
            onClick={() => onToggleMode('dba')}
            title="DBA Mode: Hands-on manual telemetry queries & interactive SQL workbench"
          >
            <span className="mode-icon">🛠️</span>
            <span>DBA Mode</span>
            {appMode === 'dba' && <span className="mode-active-dot dba-dot"></span>}
          </button>
        </div>
      )}

      <div className="header-right-actions">
        {onNavigate && (
          currentView === 'dashboard' ? (
            <button
              className="btn-header-incident"
              onClick={() => onNavigate('create-incident')}
              title="Manually open incident creation form"
            >
              + Create Incident
            </button>
          ) : (
            <button
              className="btn-header-incident secondary"
              onClick={() => onNavigate('dashboard')}
              title="Return to fleet overview"
            >
              ← Fleet Console
            </button>
          )
        )}
        <div className="status-badge">
          <span className="pulse-dot"></span>
          <span>last polled {lastPolledSecAgo}s ago</span>
        </div>
      </div>
    </header>
  );
};
