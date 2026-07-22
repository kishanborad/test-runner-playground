import { useState, useRef, useCallback } from 'react';
import type { StepResult, TestRun } from './types';
import type { HighlightInfo } from './engine/executor';
import { parseTest } from './engine/parser';
import { executeTest } from './engine/executor';
import TestListPanel from './panels/TestListPanel';
import ShopPanel from './panels/ShopPanel';
import ReportPanel from './panels/ReportPanel';
import EditorTab from './editor/EditorTab';

const BUILT_IN_SHOP_URL = '/shop.html';

export default function App() {
  const iframeRef = useRef<HTMLIFrameElement>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [source, setSource] = useState('');
  const [tab, setTab] = useState<'list' | 'editor'>('list');
  const [customUrl, setCustomUrl] = useState('');

  const [running, setRunning] = useState(false);
  const [liveResults, setLiveResults] = useState<StepResult[]>([]);
  const [runningIndex, setRunningIndex] = useState(-1);
  const [completedRun, setCompletedRun] = useState<TestRun | null>(null);

  const [cursorPos, setCursorPos] = useState<{ x: number; y: number } | null>(null);
  const [highlight, setHighlight] = useState<HighlightInfo | null>(null);

  const shopUrl = customUrl || BUILT_IN_SHOP_URL;

  const handleSelect = useCallback((id: string, src: string) => {
    setSelectedId(id);
    setSource(src);
  }, []);

  const handleRun = useCallback(async () => {
    if (!source.trim() || running) return;

    const iframe = iframeRef.current;
    if (!iframe) return;

    const parsed = parseTest(source);
    if (parsed.steps.length === 0) return;

    setRunning(true);
    setLiveResults([]);
    setCompletedRun(null);
    setRunningIndex(0);
    setCursorPos(null);
    setHighlight(null);

    // Reset shop to home before running
    if (iframe.contentWindow) {
      iframe.contentWindow.location.hash = '#/';
      await new Promise((r) => setTimeout(r, 500));
    }

    const startedAt = Date.now();

    try {
      const results = await executeTest(parsed.steps, iframe, {
        onStepStart: (i) => setRunningIndex(i),
        onStepComplete: (_i, result) =>
          setLiveResults((prev) => [...prev, result]),
        onComplete: (results) => {
          setCompletedRun({
            name: parsed.name,
            startedAt,
            completedAt: Date.now(),
            steps: results,
          });
        },
        onCursorMove: async (x, y) => setCursorPos({ x, y }),
        onHighlight: (info) => setHighlight(info),
        onScreenshot: async () => undefined, // Added in Task 8
      });
      void results;
    } catch (err) {
      console.error('Execution error:', err);
    } finally {
      setRunning(false);
      setCursorPos(null);
      setHighlight(null);
    }
  }, [source, running]);

  return (
    <div className="h-screen flex flex-col bg-panel-bg text-panel-text">
      {/* Header */}
      <header className="flex items-center justify-between px-4 py-2 border-b border-panel-border">
        <h1 className="text-sm font-bold text-panel-text">
          Test Runner Playground
        </h1>
        <span className="text-xs text-panel-text/40">Playwright-style testing in the browser</span>
      </header>

      {/* Three panels */}
      <div className="flex-1 flex overflow-hidden">
        {/* Left panel */}
        <div className="w-72 border-r border-panel-border shrink-0">
          <TestListPanel
            selectedId={selectedId}
            onSelect={handleSelect}
            running={running}
            onRun={handleRun}
            tab={tab}
            onTabChange={setTab}
            editorSlot={
              <EditorTab
                source={source}
                onChange={(v) => {
                  setSource(v);
                  setSelectedId(null);
                }}
              />
            }
            customUrl={customUrl}
            onCustomUrlChange={setCustomUrl}
          />
        </div>

        {/* Center panel */}
        <div className="flex-1 min-w-0">
          <ShopPanel
            ref={iframeRef}
            shopUrl={shopUrl}
            cursorPos={cursorPos}
            highlight={highlight}
            overlayVisible={running}
          />
        </div>

        {/* Right panel */}
        <div className="w-80 border-l border-panel-border shrink-0">
          <ReportPanel
            run={completedRun}
            liveResults={liveResults}
            runningIndex={runningIndex}
          />
        </div>
      </div>
    </div>
  );
}
