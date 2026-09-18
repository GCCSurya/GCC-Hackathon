import React from 'react';

export interface TimelineEntry {
  timestamp: string;
  event: string;
  type: string;
}

interface TimelineFooterProps {
  timeline: TimelineEntry[];
}

export const TimelineFooter: React.FC<TimelineFooterProps> = ({ timeline }) => {
  const latestEvents = timeline.slice(-3).map(t => `${t.timestamp} ${t.event}`).join(' → ');

  return (
    <footer className="timeline-footer">
      <div>System Status: Operational</div>
      <div>
        Timeline: <span className="timeline-event">{latestEvents || 'Awaiting telemetry...'}</span>
      </div>
    </footer>
  );
};
