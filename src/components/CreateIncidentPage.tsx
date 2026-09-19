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
  const [incidentId, setIncidentId] = useState<string>('Assigned on submission');
  const [title, setTitle] = useState<string>(() => anomaly?.title || 'Database Performance Anomaly - Requires DBA Inspection');
  const [database, setDatabase] = useState<string>(() => anomaly?.database || 'gcc_banking_core');
  const [severity, setSeverity] = useState<string>('HIGH');
  const [category, setCategory] = useState<string>('Database - PostgreSQL Fleet');
  const [assignedTo, setAssignedTo] = useState<string>('DBA Operations / Reliability Engineering');
  const [rootCause, setRootCause] = useState<string>(() => diagnosis?.root_cause || '');
  const [remediationSql, setRemediationSql] = useState<string>(() =>
    diagnosis?.remediation_steps.map(step => `-- Step ${step.step}: ${step.title}\n${step.sql}`).join('\n\n') || '');
  const [notes, setNotes] = useState<string>(() => appMode === 'dba' ? 'Manual incident dispatch logged via DBA Console.' : '');
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [submitError, setSubmitError] = useState<string>('');
  const [submittedIncident, setSubmittedIncident] = useState<IncidentData | null>(null);
  const [copied, setCopied] = useState<boolean>(false);

  useEffect(() => {
    let cancelled = false;
    fetch('/api/next-incident-id')
      .then(res => res.json())
      .then(data => {
        if (!cancelled && data.next_incident_id) {
          setIncidentId(data.next_incident_id);
        }
      })
      .catch(() => {
        if (!cancelled) setIncidentId('Assigned on submission');
      });
    return () => { cancelled = true; };
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    setSubmitError('');

    const nowTime = new Date().toTimeString().split(' ')[0].substring(0, 5);

    const payload = {
      ...(incidentId.startsWith('INC-') ? { incident_id: incidentId } : {}),
      severity,
      title: title || 'PostgreSQL Fleet Anomaly',
      database,
      category,
      assigned_to: assignedTo,
      raised_by: appMode === 'dba' ? 'Human DBA Operations' : 'dbpulse AI Agent',
      created_at: nowTime,
      root_cause: rootCause,
      remediation_steps: remediationSql.trim()
        ? [{ step: 1, title: 'Reviewed remediation SQL', sql: remediationSql }]
        : [],
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
      const data = await res.json().catch(() => ({}));
      setSubmitError(data.error || 'Incident could not be stored.');
    } catch {
      setSubmitError('Incident could not be stored because the backend is unavailable.');
    } finally {
      setIsSubmitting(false);
    }
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
          <h2 className="success-title">Incident Successfully Stored</h2>
          <p className="success-subtitle">
            The incident record was persisted to the PostgreSQL incident store at test.public.incidents.
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
              <span className="receipt-val highlight">
                {submittedIncident.remediation_steps?.length || 0} step(s) stored with the incident
              </span>
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
        {submitError && <div className="form-error" role="alert">{submitError}</div>}
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
            <label>Suggested Root Cause</label>
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
            <span>Guidance: <strong>PostgreSQL Wait-Event Runbooks</strong></span>
          </div>
        </div>
      </form>
    </div>
  );
};
