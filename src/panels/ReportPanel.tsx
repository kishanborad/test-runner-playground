import { useState } from 'react';
import type { StepResult, TestRun } from '../types';
import StepRow from './StepRow';
import { generateReport } from '../report/generateReport';

interface Props {
  run: TestRun | null;
  liveResults: StepResult[];
  runningIndex: number;
  videoBlob: Blob | null;
}

export default function ReportPanel({ run, liveResults, runningIndex, videoBlob }: Props) {
  const [expandedStep, setExpandedStep] = useState<number | null>(null);

  const results = run?.steps ?? liveResults;
  const isRunning = !run && liveResults.length > 0;
  const passed = results.filter((r) => r.status === 'passed').length;
  const failed = results.filter((r) => r.status === 'failed').length;
  const totalDuration = results.reduce((sum, r) => sum + r.duration, 0);

  const handleDownloadReport = () => {
    if (!run) return;
    const html = generateReport(run);
    const blob = new Blob([html], { type: 'text/html' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `test-report-${run.name.toLowerCase().replace(/\s+/g, '-')}.html`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleDownloadVideo = () => {
    if (!videoBlob) return;
    const url = URL.createObjectURL(videoBlob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `test-recording-${Date.now()}.webm`;
    a.click();
    URL.revokeObjectURL(url);
  };

  if (results.length === 0) {
    return (
      <div className="flex items-center justify-center h-full text-panel-muted text-sm">
        Select a test and click Run
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full">
      {/* Summary bar */}
      <div className="flex items-center gap-4 px-4 py-3 border-b border-panel-border text-sm bg-panel-surface">
        {run && <span className="font-semibold text-panel-text">{run.name}</span>}
        <span className="px-2 py-0.5 rounded-full bg-panel-success/10 text-panel-success text-xs font-medium">
          {passed} passed
        </span>
        <span className="px-2 py-0.5 rounded-full bg-panel-error/10 text-panel-error text-xs font-medium">
          {failed} failed
        </span>
        <span className="text-panel-muted ml-auto font-mono text-xs">{(totalDuration / 1000).toFixed(1)}s</span>
        {isRunning && (
          <span className="text-panel-warn animate-pulse">Running step {runningIndex + 1}...</span>
        )}
      </div>

      {/* Download bar */}
      {run && (
        <div className="flex items-center gap-2 px-4 py-2 border-b border-panel-border">
          <button
            onClick={handleDownloadReport}
            className="px-4 py-1.5 text-xs font-medium text-white rounded-lg
              bg-gradient-to-r from-panel-accentDim to-panel-accent
              hover:shadow-glow transition-all duration-200">
            Download Report
          </button>
          {videoBlob && (
            <button
              onClick={handleDownloadVideo}
              className="px-4 py-1.5 text-xs font-medium text-panel-secondary rounded-lg
                border border-panel-border hover:border-panel-borderHover hover:text-panel-text
                transition-all duration-200">
              Download Video
            </button>
          )}
        </div>
      )}

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
