import { useState, useRef, useCallback } from 'react';
import type { StepResult, TestRun } from './types';
import type { HighlightInfo } from './engine/executor';
import { parseTest } from './engine/parser';
import { executeTest } from './engine/executor';
import TestListPanel from './panels/TestListPanel';
import ShopPanel from './panels/ShopPanel';
import ReportPanel from './panels/ReportPanel';
import EditorTab from './editor/EditorTab';
import html2canvas from 'html2canvas';
import { VideoRecorder } from './report/videoRecorder';
import { ProblemBanner } from './ProblemBanner';

const BUILT_IN_SHOP_URL = import.meta.env.BASE_URL + 'shop.html';

export default function App() {
  const iframeRef = useRef<HTMLIFrameElement>(null);
  const videoRef = useRef(new VideoRecorder());
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [source, setSource] = useState('');
  const [tab, setTab] = useState<'list' | 'editor'>('list');
  const [customUrl, setCustomUrl] = useState('');

  const [running, setRunning] = useState(false);
  const [liveResults, setLiveResults] = useState<StepResult[]>([]);
  const [runningIndex, setRunningIndex] = useState(-1);
  const [completedRun, setCompletedRun] = useState<TestRun | null>(null);
  const [videoBlob, setVideoBlob] = useState<Blob | null>(null);

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
    setVideoBlob(null);

    // Reset shop to home before running
    if (iframe.contentWindow) {
      iframe.contentWindow.location.hash = '#/';
      await new Promise((r) => setTimeout(r, 500));
    }

    const startedAt = Date.now();
    videoRef.current.start(iframe);

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
        onScreenshot: async () => {
          try {
            const doc = iframe.contentDocument;
            if (!doc?.body) return undefined;
            const canvas = await html2canvas(doc.body, {
              width: iframe.clientWidth,
              height: iframe.clientHeight,
              useCORS: true,
            });
            return canvas.toDataURL('image/png');
          } catch {
            return undefined;
          }
        },
      });
      void results;
    } catch (err) {
      console.error('Execution error:', err);
    } finally {
      setRunning(false);
      setCursorPos(null);
      setHighlight(null);
      const blob = await videoRef.current.stop();
      if (blob) setVideoBlob(blob);
    }
  }, [source, running]);

  return (
    <div className="h-screen flex flex-col bg-panel-bg text-panel-text">
      <ProblemBanner />
      {/* Header */}
      <header className="flex items-center justify-between px-6 py-3 border-b border-panel-border bg-panel-surface backdrop-blur-glass">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-panel-accentDim to-panel-accent flex items-center justify-center shadow-glow">
            <span className="text-white text-sm font-bold">TR</span>
          </div>
          <h1 className="text-lg font-semibold bg-gradient-to-r from-panel-text to-panel-secondary bg-clip-text text-transparent">
            Test Runner Playground
          </h1>
        </div>
        <span className="text-xs text-panel-muted tracking-wide">
          Playwright-style testing in the browser
        </span>
      </header>

      {/* Three panels */}
      <div className="flex-1 flex overflow-hidden">
        {/* Left panel */}
        <div className="w-72 border-r border-panel-border shrink-0 bg-panel-surface backdrop-blur-glass">
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
        <div className="w-80 border-l border-panel-border shrink-0 bg-panel-surface backdrop-blur-glass">
          <ReportPanel
            run={completedRun}
            liveResults={liveResults}
            runningIndex={runningIndex}
            videoBlob={videoBlob}
          />
        </div>
      </div>
    </div>
  );
}
