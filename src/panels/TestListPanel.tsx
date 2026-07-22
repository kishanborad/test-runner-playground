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
    <div className="flex flex-col h-full bg-panel-bg">
      <div className="flex border-b border-panel-border">
        <button
          onClick={() => onTabChange('list')}
          className={`flex-1 px-4 py-2 text-sm ${
            tab === 'list' ? 'bg-panel-surface text-panel-text' : 'text-panel-text/50'
          }`}>
          Pre-written
        </button>
        <button
          onClick={() => onTabChange('editor')}
          className={`flex-1 px-4 py-2 text-sm ${
            tab === 'editor' ? 'bg-panel-surface text-panel-text' : 'text-panel-text/50'
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
          className="w-full px-2 py-1 text-xs bg-panel-surface border border-panel-border rounded text-panel-text placeholder:text-panel-text/30"
        />
      </div>

      {tab === 'list' ? (
        <div className="flex-1 overflow-y-auto">
          {prewrittenTests.map((test) => (
            <button
              key={test.id}
              onClick={() => onSelect(test.id, test.source)}
              className={`w-full text-left px-3 py-2 text-sm border-b border-panel-border hover:bg-panel-surface ${
                selectedId === test.id ? 'bg-panel-surface text-panel-accent' : 'text-panel-text'
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
          className="w-full bg-panel-accent text-white py-2 rounded text-sm font-medium disabled:opacity-40 disabled:cursor-not-allowed hover:bg-blue-700 transition-colors">
          {running ? 'Running...' : 'Run Test'}
        </button>
      </div>
    </div>
  );
}
