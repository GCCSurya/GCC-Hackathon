import React from 'react';

export interface AnomalyInfo {
  type: string;
  database: string;
  title: string;
  target_table?: string;
  blocking_pid?: number;
  wait_event?: string;
  waiting_count?: number;
  duration_sec?: number;
}

interface AnomalyBannerProps {
  anomaly: AnomalyInfo | null;
}

export const AnomalyBanner: React.FC<AnomalyBannerProps> = ({ anomaly }) => {
  if (!anomaly) return null;

  return (
    <div className="anomaly-banner">
      <div className="anomaly-text">
        <span className="anomaly-tag">ANOMALY DETECTED</span>
        <span>
          <strong>{anomaly.database}</strong>: {anomaly.title}
        </span>
      </div>
    </div>
  );
};
