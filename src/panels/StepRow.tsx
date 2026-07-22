import type { StepResult } from '../types';

interface Props {
  index: number;
  result: StepResult;
  expanded: boolean;
  onToggle: () => void;
}

export default function StepRow({ index, result, expanded, onToggle }: Props) {
  const icon = result.status === 'passed' ? '✓' : result.status === 'failed' ? '✗' : '⏳';
  const color =
    result.status === 'passed'
      ? 'text-panel-success'
      : result.status === 'failed'
        ? 'text-panel-error'
        : 'text-panel-warn';

  return (
    <div className="border-b border-panel-border">
      <button
        onClick={onToggle}
        className="w-full flex items-center gap-2 px-3 py-2 text-left hover:bg-panel-surface text-sm">
        <span className={`font-mono ${color}`}>{icon}</span>
        <span className="text-panel-text/60 font-mono w-6">{index + 1}.</span>
        <span className="text-panel-text flex-1 truncate">{result.step.raw}</span>
        <span className="text-panel-text/40 text-xs">{result.duration.toFixed(0)}ms</span>
      </button>
      {expanded && (
        <div className="px-3 pb-3 space-y-2">
          {result.error && (
            <p className="text-panel-error text-xs">{result.error}</p>
          )}
          {result.expected && (
            <p className="text-xs text-panel-text/60">
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
              className="rounded border border-panel-border max-h-48 w-full object-contain"
            />
          )}
        </div>
      )}
    </div>
  );
}
