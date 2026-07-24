import { prewrittenTests } from '../tests/prewritten';

interface Props {
  selectedId: string | null;
  onSelect: (id: string, source: string) => void;
  running: boolean;
  onRun: () => void;
  tab: 'list' | 'editor';
  onTabChange: (tab: 'list' | 'editor') => void;
  editorSlot: React.ReactNode;
  customUrl: string;
  onCustomUrlChange: (url: string) => void;
}

export default function TestListPanel({
  selectedId,
  onSelect,
  running,
  onRun,
  tab,
  onTabChange,
  editorSlot,
  customUrl,
  onCustomUrlChange,
}: Props) {
  return (
    <div className="flex flex-col h-full">
      <div className="flex border-b border-panel-border">
        <button
          onClick={() => onTabChange('list')}
          className={`flex-1 px-4 py-2.5 text-sm font-medium transition-all duration-200 ${
            tab === 'list'
              ? 'text-panel-accent border-b-2 border-panel-accent bg-panel-accent/5'
              : 'text-panel-muted hover:text-panel-secondary'
          }`}>
          Pre-written
        </button>
        <button
          onClick={() => onTabChange('editor')}
          className={`flex-1 px-4 py-2.5 text-sm font-medium transition-all duration-200 ${
            tab === 'editor'
              ? 'text-panel-accent border-b-2 border-panel-accent bg-panel-accent/5'
              : 'text-panel-muted hover:text-panel-secondary'
          }`}>
          Write your own
        </button>
      </div>

      <div className="px-3 py-2 border-b border-panel-border">
        <input
          type="text"
          placeholder="Custom URL (leave empty for built-in shop)"
          value={customUrl}
          onChange={(e) => onCustomUrlChange(e.target.value)}
          className="w-full px-3 py-2 text-xs rounded-lg bg-panel-deep border border-panel-border text-panel-text
            placeholder:text-panel-muted
            focus:outline-none focus:border-panel-accent focus:ring-1 focus:ring-panel-accent/30 focus:shadow-glow
            transition-all duration-200"
        />
      </div>

      {tab === 'list' ? (
        <div className="flex-1 overflow-y-auto">
          {prewrittenTests.map((test) => (
            <button
              key={test.id}
              onClick={() => onSelect(test.id, test.source)}
              className={`w-full text-left px-4 py-3 text-sm border-b border-panel-border transition-all duration-200 hover:bg-white/[0.03] ${
                selectedId === test.id
                  ? 'bg-panel-accent/5 text-panel-accent border-l-2 border-l-panel-accent'
                  : 'text-panel-secondary hover:text-panel-text'
              }`}>
              {test.name}
            </button>
          ))}
        </div>
      ) : (
        <div className="flex-1 overflow-hidden">{editorSlot}</div>
      )}

      <div className="p-3 border-t border-panel-border">
        <button
          onClick={onRun}
          disabled={running}
          className="w-full py-2.5 rounded-lg text-sm font-medium text-white
            bg-gradient-to-r from-panel-accentDim to-panel-accent
            hover:from-panel-accent hover:to-panel-accentDim
            hover:shadow-glow hover:scale-[1.02]
            active:scale-[0.98]
            transition-all duration-200
            disabled:opacity-40 disabled:cursor-not-allowed disabled:hover:scale-100">
          {running ? 'Running...' : 'Run Test'}
        </button>
      </div>
    </div>
  );
}
