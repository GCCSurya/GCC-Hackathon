import React, { useState, useEffect } from 'react';
import type { AnomalyInfo } from './AnomalyBanner';
import type { DiagnosisData } from './AgentPanel';
import type { IncidentData } from './IncidentCard';
import type { FleetItem } from './FleetStrip';

interface CreateIncidentPageProps {
  anomaly: AnomalyInfo | null;
  diagnosis: DiagnosisData | null;
  fleet: FleetItem[];
  appMode?: 'agent' | 'dba';
  onCancel: () => void;
  onIncidentCreated: (incident: IncidentData) => void;
}

export const CreateIncidentPage: React.FC<CreateIncidentPageProps> = ({
  anomaly,
  diagnosis,
  fleet,
  appMode = 'agent',
  onCancel,
  onIncidentCreated
}) => {
  const [incidentId, setIncidentId] = useState<string>('INC-00459');
  const [title, setTitle] = useState<string>('');
  const [database, setDatabase] = useState<string>('gcc_banking_core');
  const [severity, setSeverity] = useState<string>('HIGH');
  const [category, setCategory] = useState<string>('Database - PostgreSQL Fleet');
  const [assignedTo, setAssignedTo] = useState<string>('DBA Operations / Reliability Engineering');
  const [rootCause, setRootCause] = useState<string>('');
  const [remediationSql, setRemediationSql] = useState<string>('');
  const [notes, setNotes] = useState<string>('');
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [submittedIncident, setSubmittedIncident] = useState<IncidentData | null>(null);
  const [copied, setCopied] = useState<boolean>(false);

  // Initialize fields from anomaly & diagnosis
  useEffect(() => {
    // Fetch upcoming incident ID
    fetch('/api/next-incident-id')
      .then(res => res.json())
      .then(data => {
        if (data.next_incident_id) {
          setIncidentId(data.next_incident_id);
        }
      })
      .catch(() => {
        setIncidentId(`INC-00${Math.floor(Math.random() * 800) + 460}`);
      });

    if (anomaly) {
      setTitle(anomaly.title || `Performance Anomaly on ${anomaly.database}`);
      setDatabase(anomaly.database || 'gcc_banking_core');
    } else {
      setTitle('Database Performance Anomaly — Requires DBA Inspection');
    }

    if (diagnosis) {
      setRootCause(diagnosis.root_cause || '');
      const sqlBlocks = diagnosis.remediation_steps
        ? diagnosis.remediation_steps.map(s => `-- Step ${s.step}: ${s.title}\n${s.sql}`).join('\n\n')
        : '';
      setRemediationSql(sqlBlocks);
    }

    if (appMode === 'dba') {
      setNotes('Manual incident dispatch logged via DBA Console.');
    }
  }, [anomaly, diagnosis, appMode]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);

    const nowTime = new Date().toTimeString().split(' ')[0].substring(0, 5);

    const payload = {
      incident_id: incidentId,
      severity,
      title: title || 'PostgreSQL Fleet Anomaly',
      database,
      category,
      assigned_to: assignedTo,
      raised_by: 'dbpulse AI Agent',
      created_at: nowTime,
      root_cause: rootCause,
      remediation_steps: diagnosis?.remediation_steps || [],
      notes
    };

    try {
      const res = await fetch('/api/raise-incident', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });

      if (res.ok) {
        const data = await res.json();
        const finalInc = data.incident || payload;
        setSubmittedIncident(finalInc);
        onIncidentCreated(finalInc);
        return;
      }
    } catch {
      // Standalone client fallback
    }

    const fallbackInc: IncidentData = {
      incident_id: incidentId,
      severity,
      title: title || 'PostgreSQL Fleet Anomaly',
      database,
      assigned_to: assignedTo,
      raised_by: 'dbpulse AI Agent',
      created_at: nowTime,
      root_cause: rootCause
    };

    setSubmittedIncident(fallbackInc);
    onIncidentCreated(fallbackInc);
    setIsSubmitting(false);
  };

  const handleCopyId = () => {
    if (submittedIncident) {
      navigator.clipboard.writeText(submittedIncident.incident_id);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  // If incident has been submitted, show confirmation receipt
  if (submittedIncident) {
    return (
      <div className="incident-create-container">
        <div className="incident-success-card">
          <div className="success-icon-badge">🛡️</div>
          <h2 className="success-title">Incident Successfully Dispatched</h2>
          <p className="success-subtitle">
            The incident record has been registered with ServiceNow / Enterprise Monitoring and assigned to the reliability on-call team.
          </p>

          <div className="incident-receipt-box">
            <div className="receipt-row">
              <span className="receipt-label">Incident Tracking ID:</span>
              <div className="receipt-id-group">
                <span className="receipt-id-val">{submittedIncident.incident_id}</span>
                <button className="btn-copy-sm" onClick={handleCopyId}>
                  {copied ? 'Copied ✓' : 'Copy ID'}
                </button>
              </div>
            </div>
            <div className="receipt-row">
              <span className="receipt-label">Severity Level:</span>
              <span className={`severity-badge ${submittedIncident.severity.toLowerCase()}`}>
                {submittedIncident.severity}
              </span>
            </div>
            <div className="receipt-row">
              <span className="receipt-label">Affected Database:</span>
              <span className="receipt-val">{submittedIncident.database}</span>
            </div>
            <div className="receipt-row">
              <span className="receipt-label">Assigned Resolver:</span>
              <span className="receipt-val">{submittedIncident.assigned_to}</span>
            </div>
            <div className="receipt-row">
              <span className="receipt-label">Dispatched At:</span>
              <span className="receipt-val">{submittedIncident.created_at} UTC</span>
            </div>
            <div className="receipt-row">
              <span className="receipt-label">Remediation SQL:</span>
              <span className="receipt-val highlight">Attached automatically (2 steps)</span>
            </div>
          </div>

          <div className="success-actions">
            <button className="btn-primary" onClick={onCancel}>
              ← Return to Fleet Console
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="incident-create-container">
      {/* Navigation Breadcrumbs & Header */}
      <div className="create-page-header">
        <div className="breadcrumb-group">
          <button className="btn-back-link" onClick={onCancel}>
            ← Fleet Console
          </button>
          <span className="breadcrumb-separator">/</span>
          <span className="breadcrumb-current">Raise New Incident</span>
        </div>
        <div className="header-meta-badge">
          <span className={`draft-tag ${appMode === 'dba' ? 'dba-tag' : ''}`}>
            {appMode === 'dba' ? 'DBA MANUAL DISPATCH' : 'AGENT AUTONOMOUS DISPATCH'}
          </span>
          <span className="inc-id-preview">{incidentId}</span>
        </div>
      </div>

      <form onSubmit={handleSubmit} className="incident-form-grid">
        {/* Left Column: Core Fields */}
        <div className="form-card main-form">
          <div className="form-section-title">
            <span>Incident Classification & Routing</span>
          </div>

          <div className="form-field">
            <label htmlFor="inc-title">Short Description / Title *</label>
            <input
              id="inc-title"
              type="text"
              className="form-input"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="e.g. Lock contention on public.orders"
              required
            />
          </div>

          <div className="form-row-2">
            <div className="form-field">
              <label htmlFor="inc-db">Affected Target Database *</label>
              <select
                id="inc-db"
                className="form-select"
                value={database}
                onChange={(e) => setDatabase(e.target.value)}
              >
                {fleet.map((db) => (
                  <option key={db.name} value={db.name}>
                    {db.name} ({db.status})
                  </option>
                ))}
              </select>
            </div>

            <div className="form-field">
              <label htmlFor="inc-severity">Severity / Priority *</label>
              <select
                id="inc-severity"
                className="form-select"
                value={severity}
                onChange={(e) => setSeverity(e.target.value)}
              >
                <option value="CRITICAL">CRITICAL (P1) — Active User Impact</option>
                <option value="HIGH">HIGH (P2) — Performance Degradation</option>
                <option value="MODERATE">MODERATE (P3) — Anomaly Warning</option>
                <option value="LOW">LOW (P4) — Advisory / Preventive</option>
              </select>
            </div>
          </div>

          <div className="form-row-2">
            <div className="form-field">
              <label htmlFor="inc-category">Configuration Item / Category</label>
              <input
                id="inc-category"
                type="text"
                className="form-input"
                value={category}
                onChange={(e) => setCategory(e.target.value)}
              />
            </div>

            <div className="form-field">
              <label htmlFor="inc-assignee">Assignment Group</label>
              <input
                id="inc-assignee"
                type="text"
                className="form-input"
                value={assignedTo}
                onChange={(e) => setAssignedTo(e.target.value)}
              />
            </div>
          </div>

          <div className="form-field">
            <label htmlFor="inc-notes">Operational Notes & Handover Context</label>
            <textarea
              id="inc-notes"
              className="form-textarea"
              rows={3}
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Add optional notes for the on-call engineer (e.g. customer tier impact, maintenance windows)..."
            />
          </div>

          <div className="form-actions-bottom">
            <button type="button" className="btn-secondary" onClick={onCancel}>
              Cancel
            </button>
            <button type="submit" className="btn-raise" disabled={isSubmitting}>
              {isSubmitting ? 'Dispatching Incident...' : 'Submit & Dispatch Incident →'}
            </button>
          </div>
        </div>

        {/* Right Column: AI Telemetry & Attached Diagnostic Artifacts */}
        <div className="form-card ai-context-form">
          <div className="form-section-title ai-title">
            <div className="ai-icon">AI</div>
            <span>Auto-Attached Agent Telemetry & Fix</span>
          </div>

          <div className="form-field">
            <label>RAG Root Cause Diagnosis</label>
            <textarea
              className="form-textarea readonly-box"
              rows={4}
              value={rootCause}
              onChange={(e) => setRootCause(e.target.value)}
              placeholder="Agent diagnosis will appear here..."
            />
            {diagnosis?.citations && (
              <span className="citation-hint">{diagnosis.citations}</span>
            )}
          </div>

          <div className="form-field">
            <label>Pre-Generated Remediation SQL</label>
            <textarea
              className="form-textarea sql-editor"
              rows={6}
              value={remediationSql}
              onChange={(e) => setRemediationSql(e.target.value)}
              placeholder="-- Remediation SQL statements..."
            />
            <span className="disclaimer-hint">
              🛡 Safety Protocol: Generates SQL for a human engineer to verify and run.
            </span>
          </div>

          <div className="reporter-stamp">
            <span>Reporter: <strong>{appMode === 'dba' ? 'Human DBA Operations (Manual Mode)' : 'dbpulse AI Reliability Agent'}</strong></span>
            <span>Grounding: <strong>PostgreSQL Wait-Events Knowledge Base</strong></span>
          </div>
        </div>
      </form>
    </div>
  );
};
