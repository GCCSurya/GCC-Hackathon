import React from 'react';
import type { RemediationStep } from './AgentPanel';

export interface IncidentData {
  incident_id: string;
  severity: string;
  title: string;
  database: string;
  assigned_to: string;
  raised_by: string;
  created_at: string;
  root_cause?: string;
  remediation_steps?: RemediationStep[];
}

interface IncidentCardProps {
  incident: IncidentData | null;
}

export const IncidentCard: React.FC<IncidentCardProps> = ({ incident }) => {
  if (!incident) return null;

  return (
    <div className="incident-card">
      <div className="incident-header">
        <span className="incident-id">{incident.incident_id} — Incident Created</span>
        <span className="severity-badge">{incident.severity} SEVERITY</span>
      </div>
      <div className="incident-meta">
        Assigned: {incident.assigned_to} · Raised by: {incident.raised_by} · Database: {incident.database}
      </div>
      <p style={{ fontSize: '13px', color: 'var(--text-primary)' }}>
        {incident.title}. Diagnostic and remediation queries automatically attached to incident.
      </p>
    </div>
  );
};
