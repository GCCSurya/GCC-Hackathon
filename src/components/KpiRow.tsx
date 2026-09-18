import React from 'react';

export interface KpiData {
  active_sessions: number;
  blocked_sessions: number;
  cache_hit_ratio: number;
  avg_query_time_ms: number;
}

interface KpiRowProps {
  kpis: KpiData;
}

export const KpiRow: React.FC<KpiRowProps> = ({ kpis }) => {
  return (
    <div className="kpi-row">
      <div className="kpi-item">
        <span className="kpi-label">Active Sessions</span>
        <span className="kpi-value">{kpis.active_sessions}</span>
      </div>
      <div className="kpi-item">
        <span className="kpi-label">Blocked Sessions</span>
        <span className={`kpi-value ${kpis.blocked_sessions > 0 ? 'alert' : ''}`}>
          {kpis.blocked_sessions}
        </span>
      </div>
      <div className="kpi-item">
        <span className="kpi-label">Cache Hit Ratio</span>
        <span className="kpi-value">{kpis.cache_hit_ratio}%</span>
      </div>
      <div className="kpi-item">
        <span className="kpi-label">Avg Query Duration</span>
        <span className={`kpi-value ${kpis.avg_query_time_ms > 200 ? 'alert' : ''}`}>
          {kpis.avg_query_time_ms}ms
        </span>
      </div>
    </div>
  );
};
