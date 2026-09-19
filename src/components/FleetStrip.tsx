import React from 'react';

export interface FleetItem {
  name: string;
  status: 'AT_RISK' | 'HEALTHY' | 'UNAVAILABLE';
  risk_score: number | null;
  status_desc: string;
  active_sessions?: number | null;
  blocked_sessions?: number | null;
  cache_hit_ratio?: number | null;
  size_bytes?: number | null;
  data_source?: 'live' | 'demo' | 'unavailable';
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
          const unavailable = db.status === 'UNAVAILABLE' || db.risk_score == null;
          return (
            <div
              key={db.name}
              className={`fleet-row ${unavailable ? 'unavailable' : isRisk ? 'at-risk' : 'healthy'} ${selectedDatabase === db.name ? 'selected' : ''}`}
              onClick={() => onSelect?.(db.name)}
              role={onSelect ? 'button' : undefined}
              tabIndex={onSelect ? 0 : undefined}
              onKeyDown={(event) => { if (onSelect && (event.key === 'Enter' || event.key === ' ')) onSelect(db.name); }}
            >
              <div className="fleet-info">
                <span className={`status-tick ${unavailable ? 'unknown' : isRisk ? 'coral' : 'sage'}`}></span>
                <span className="db-name">{db.name}</span>
                <span className="db-status-desc">{db.status_desc}</span>
                <span className={`source-chip ${db.data_source ?? 'unavailable'}`}>{db.data_source ?? 'unavailable'}</span>
              </div>
              <span className={`risk-score ${unavailable ? 'unknown' : isRisk ? 'high' : 'normal'}`}>
                {unavailable ? 'RISK N/A' : `RISK ${db.risk_score}/100`}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
};
