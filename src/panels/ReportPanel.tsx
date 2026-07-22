import { useState } from 'react';
import type { StepResult, TestRun } from '../types';
import StepRow from './StepRow';

interface Props {
  run: TestRun | null;
  liveResults: StepResult[];
  runningIndex: number;
}

export default function ReportPanel({ run, liveResults, runningIndex }: Props) {
  const [expandedStep, setExpandedStep] = useState<number | null>(null);

  const results = run?.steps ?? liveResults;
  const isRunning = !run && liveResults.length > 0;
  const passed = results.filter((r) => r.status === 'passed').length;
  const failed = results.filter((r) => r.status === 'failed').length;
  const totalDuration = results.reduce((sum, r) => sum + r.duration, 0);

  if (results.length === 0) {
    return (
      <div className="flex items-center justify-center h-full text-panel-text/30 text-sm">
        Select a test and click Run
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full bg-panel-bg">
      {/* Summary bar */}
      <div className="flex items-center gap-4 px-4 py-3 border-b border-panel-border text-sm">
        {run && <span className="font-medium text-panel-text">{run.name}</span>}
        <span className="text-panel-success">{passed} passed</span>
        <span className="text-panel-error">{failed} failed</span>
        <span className="text-panel-text/40 ml-auto">{(totalDuration / 1000).toFixed(1)}s</span>
        {isRunning && (
          <span className="text-panel-warn animate-pulse">Running step {runningIndex + 1}...</span>
        )}
      </div>

      {/* Step list */}
      <div className="flex-1 overflow-y-auto">
        {results.map((result, i) => (
          <StepRow
            key={i}
            index={i}
            result={result}
            expanded={expandedStep === i || result.status === 'failed'}
            onToggle={() => setExpandedStep(expandedStep === i ? null : i)}
          />
        ))}
      </div>
    </div>
  );
}
