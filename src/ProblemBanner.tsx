import { useState } from 'react';

export function ProblemBanner() {
  const [dismissed, setDismissed] = useState(false);
  if (dismissed) return null;

  return (
    <div className="flex items-center justify-between gap-4 px-4 py-2 bg-white/[0.04] border-b border-panel-border text-[11px] text-panel-muted">
      <div className="flex items-center gap-3 min-w-0">
        <span className="shrink-0 px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 font-medium uppercase tracking-wider text-[10px]">Free</span>
        <span className="truncate">
          Playwright requires Node.js, npm, and browser drivers. BrowserStack costs $29/mo. PlaywrightPad runs tests server-side. This executes Playwright-style tests against a live page entirely in your browser — with step-by-step DOM highlighting and full reports.
        </span>
      </div>
      <button onClick={() => setDismissed(true)} className="shrink-0 text-panel-muted hover:text-panel-text cursor-pointer" aria-label="Dismiss">&#x2715;</button>
    </div>
  );
}
