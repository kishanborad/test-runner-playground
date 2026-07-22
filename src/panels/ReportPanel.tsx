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

      {/* Download bar */}
      {run && (
        <div className="flex items-center gap-2 px-4 py-2 border-b border-panel-border">
          <button
            onClick={handleDownloadReport}
            className="px-3 py-1 text-xs bg-panel-accent text-white rounded hover:bg-blue-700">
            Download Report
          </button>
          {videoBlob && (
            <button
              onClick={handleDownloadVideo}
              className="px-3 py-1 text-xs bg-panel-surface text-panel-text border border-panel-border rounded hover:bg-panel-border">
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
