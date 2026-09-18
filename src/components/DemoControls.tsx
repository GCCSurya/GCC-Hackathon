import React from 'react';

interface DemoControlsProps {
  activeScenario: string;
  onSelectScenario: (scenario: string) => void;
  onReset: () => void;
}

export const DemoControls: React.FC<DemoControlsProps> = ({
  activeScenario,
  onSelectScenario,
  onReset
}) => {
  return (
    <div className="demo-controls">
      <span>SEEDED ANOMALY SIMULATION:</span>
      <div className="control-btn-group">
        <button
          className={`btn-demo-scenario ${activeScenario === 'LOCK_CONTENTION' ? 'active' : ''}`}
          onClick={() => onSelectScenario('LOCK_CONTENTION')}
        >
          Row Lock Contention
        </button>
        <button
          className={`btn-demo-scenario ${activeScenario === 'POOL_EXHAUSTION' ? 'active' : ''}`}
          onClick={() => onSelectScenario('POOL_EXHAUSTION')}
        >
          Pool Exhaustion
        </button>
        <button
          className={`btn-demo-scenario ${activeScenario === 'RUNAWAY_QUERY' ? 'active' : ''}`}
          onClick={() => onSelectScenario('RUNAWAY_QUERY')}
        >
          Runaway Scan
        </button>
        <button
          className={`btn-demo-scenario ${activeScenario === 'HEALTHY' ? 'active' : ''}`}
          onClick={onReset}
        >
          Reset (Healthy)
        </button>
      </div>
    </div>
  );
};
