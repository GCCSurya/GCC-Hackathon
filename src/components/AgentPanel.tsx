import React, { useState } from 'react';

export interface RemediationStep {
  step: number;
  title: string;
  sql: string;
}

export interface DiagnosisData {
  model: string;
  root_cause: string;
  citations: string;
  remediation_steps: RemediationStep[];
  disclaimer: string;
}

interface AgentPanelProps {
  diagnosis: DiagnosisData | null;
  onRaiseIncident: () => void;
  incidentRaised: boolean;
  isDiagnosing: boolean;
}

export const AgentPanel: React.FC<AgentPanelProps> = ({
  diagnosis,
  onRaiseIncident,
  incidentRaised,
  isDiagnosing
}) => {
  const [copiedStep, setCopiedStep] = useState<number | null>(null);

  const handleCopy = (stepNum: number, text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedStep(stepNum);
    setTimeout(() => setCopiedStep(null), 2000);
  };

  if (isDiagnosing) {
    return (
      <div className="agent-panel" style={{ opacity: 0.8 }}>
        <div className="agent-header">
          <div className="agent-title-group">
            <div className="agent-avatar">AI</div>
            <span className="agent-title">Analyzing Telemetry & RAG Knowledge Base...</span>
          </div>
        </div>
        <p className="root-cause-desc">Querying pg_stat_activity & matching wait-event patterns...</p>
      </div>
    );
  }

  if (!diagnosis) return null;

  return (
    <div className="agent-panel">
      <div className="agent-header">
        <div className="agent-title-group">
          <div className="agent-avatar">AI</div>
          <span className="agent-title">Root Cause Diagnosis & Remediation</span>
        </div>
        <span className="agent-meta">Model: {diagnosis.model}</span>
      </div>

      <div className="root-cause-box">
        <p className="root-cause-desc">{diagnosis.root_cause}</p>
        <span className="citation-line">{diagnosis.citations}</span>
      </div>

      {diagnosis.remediation_steps && diagnosis.remediation_steps.length > 0 && (
        <div className="fix-section">
          <span className="fix-title">Suggested Remediation Steps:</span>
          <div className="fix-steps">
            {diagnosis.remediation_steps.map((step) => (
              <div key={step.step} className="fix-step">
                <div className="step-header">
                  <span>Step {step.step}: {step.title}</span>
                  <button
                    className="btn-copy"
                    onClick={() => handleCopy(step.step, step.sql)}
                  >
                    {copiedStep === step.step ? 'Copied ✓' : 'Copy SQL'}
                  </button>
                </div>
                <pre className="sql-code">{step.sql}</pre>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="disclaimer-line">
        <span className="disclaimer-icon">🛡</span>
        <span>{diagnosis.disclaimer}</span>
      </div>

      <div className="action-row">
        <button
          className="btn-raise"
          onClick={onRaiseIncident}
          disabled={incidentRaised}
        >
          {incidentRaised ? 'Incident Raised ✓' : 'Raise Incident'}
        </button>
      </div>
    </div>
  );
};
