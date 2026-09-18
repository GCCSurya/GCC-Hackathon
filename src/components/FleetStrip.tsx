import React from 'react';

export interface FleetItem {
  name: string;
  status: 'AT_RISK' | 'HEALTHY';
  risk_score: number;
  status_desc: string;
}

interface FleetStripProps {
  fleet: FleetItem[];
}

export const FleetStrip: React.FC<FleetStripProps> = ({ fleet }) => {
  return (
    <div className="fleet-section">
      <div className="section-label">Database Fleet Status</div>
      <div className="fleet-list">
        {fleet.map((db) => {
          const isRisk = db.status === 'AT_RISK';
          return (
            <div
              key={db.name}
              className={`fleet-row ${isRisk ? 'at-risk' : 'healthy'}`}
            >
              <div className="fleet-info">
                <span className={`status-tick ${isRisk ? 'coral' : 'sage'}`}></span>
                <span className="db-name">{db.name}</span>
                <span className="db-status-desc">{db.status_desc}</span>
              </div>
              <span className={`risk-score ${isRisk ? 'high' : 'normal'}`}>
                {isRisk ? `RISK ${db.risk_score}/100` : 'HEALTHY'}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
};
