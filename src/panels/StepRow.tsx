import type { StepResult } from '../types';

interface Props {
  index: number;
  result: StepResult;
  expanded: boolean;
  onToggle: () => void;
}

export default function StepRow({ index, result, expanded, onToggle }: Props) {
  const isPassed = result.status === 'passed';
  const isFailed = result.status === 'failed';

  const borderColor = isPassed
    ? 'border-l-panel-success'
    : isFailed
      ? 'border-l-panel-error'
      : 'border-l-panel-muted';

  const dotColor = isPassed
    ? 'bg-panel-success'
    : isFailed
      ? 'bg-panel-error'
      : 'bg-panel-warn';

  return (
    <div className={`border-b border-panel-border border-l-2 ${borderColor}`}>
      <button
        onClick={onToggle}
        className="w-full flex items-center gap-3 px-3 py-2.5 text-left hover:bg-white/[0.03] text-sm transition-colors duration-150">
        <span
          className={`w-2 h-2 rounded-full shrink-0 ${dotColor} ${
            !isPassed && !isFailed ? 'animate-pulse' : ''
          }`}
        />
        <span className="text-panel-muted font-mono text-xs w-5 shrink-0">{index + 1}.</span>
        <span className="text-panel-secondary flex-1 truncate">{result.step.raw}</span>
        <span className="text-panel-muted text-xs font-mono shrink-0">{result.duration.toFixed(0)}ms</span>
      </button>
      {expanded && (
        <div className="px-4 pb-3 space-y-2 ml-5">
          {result.error && (
            <p className="text-panel-error text-xs">{result.error}</p>
          )}
          {result.expected && (
            <p className="text-xs text-panel-muted">
              Expected: <span className="text-panel-success">{result.expected}</span>
              {result.actual && (
                <> | Actual: <span className="text-panel-error">{result.actual}</span></>
              )}
            </p>
          )}
          {result.screenshot && (
            <img
              src={result.screenshot}
              alt={`Step ${index + 1} screenshot`}
              className="rounded-lg border border-panel-border max-h-48 w-full object-contain"
            />
          )}
        </div>
      )}
    </div>
  );
}
