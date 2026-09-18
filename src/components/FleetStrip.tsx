import React from 'react';

export interface FleetItem {
  name: string;
  status: 'AT_RISK' | 'HEALTHY';
  risk_score: number;
  status_desc: string;
  active_sessions?: number;
  blocked_sessions?: number;
  cache_hit_ratio?: number;
  size_bytes?: number;
  data_source?: 'live' | 'demo';
  error_type?: string | null;
}

interface FleetStripProps {
  fleet: FleetItem[];
  selectedDatabase?: string;
  onSelect?: (database: string) => void;
}

export const FleetStrip: React.FC<FleetStripProps> = ({ fleet, selectedDatabase, onSelect }) => {
  return (
    <div className="fleet-section">
      <div className="section-label">Database Fleet Status</div>
      <div className="fleet-list">
        {fleet.map((db) => {
          const isRisk = db.status === 'AT_RISK';
          return (
            <div
              key={db.name}
              className={`fleet-row ${isRisk ? 'at-risk' : 'healthy'} ${selectedDatabase === db.name ? 'selected' : ''}`}
              onClick={() => onSelect?.(db.name)}
              role={onSelect ? 'button' : undefined}
              tabIndex={onSelect ? 0 : undefined}
              onKeyDown={(event) => { if (onSelect && (event.key === 'Enter' || event.key === ' ')) onSelect(db.name); }}
            >
              <div className="fleet-info">
                <span className={`status-tick ${isRisk ? 'coral' : 'sage'}`}></span>
                <span className="db-name">{db.name}</span>
                <span className="db-status-desc">{db.status_desc}</span>
                <span className={`source-chip ${db.data_source === 'live' ? 'live' : 'demo'}`}>{db.data_source ?? 'demo'}</span>
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
