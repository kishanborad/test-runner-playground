import type { TestRun } from '../types';

export function generateReport(run: TestRun): string {
  const passed = run.steps.filter((s) => s.status === 'passed').length;
  const failed = run.steps.filter((s) => s.status === 'failed').length;
  const duration = run.completedAt ? run.completedAt - run.startedAt : 0;
  const date = new Date(run.startedAt).toLocaleString();

  const stepsHtml = run.steps
    .map((s, i) => {
      const icon = s.status === 'passed' ? '&#10003;' : '&#10007;';
      const color = s.status === 'passed' ? '#4ec9b0' : '#f14c4c';
      const screenshotHtml = s.screenshot
        ? `<img src="${s.screenshot}" style="max-width:100%;border:1px solid #3e3e42;border-radius:4px;margin-top:8px;" />`
        : '';
      const errorHtml =
        s.status === 'failed' && s.error
          ? `<p style="color:#f14c4c;font-size:12px;margin:4px 0;">&#x26A0; ${escapeHtml(s.error)}</p>`
          : '';
      const detailHtml =
        s.expected
          ? `<p style="color:#999;font-size:12px;">Expected: <span style="color:#4ec9b0;">${escapeHtml(String(s.expected))}</span>${
              s.actual ? ` | Actual: <span style="color:#f14c4c;">${escapeHtml(s.actual)}</span>` : ''
            }</p>`
          : '';

      return `
        <div style="border-bottom:1px solid #3e3e42;padding:8px 12px;">
          <div style="display:flex;align-items:center;gap:8px;">
            <span style="color:${color};font-family:monospace;font-size:16px;">${icon}</span>
            <span style="color:#999;font-family:monospace;font-size:12px;">${i + 1}.</span>
            <span style="color:#ccc;font-size:13px;flex:1;">${escapeHtml(s.step.raw)}</span>
            <span style="color:#666;font-size:11px;">${s.duration.toFixed(0)}ms</span>
          </div>
          ${errorHtml}${detailHtml}${screenshotHtml}
        </div>`;
    })
    .join('');

  return `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>Test Report — ${escapeHtml(run.name)}</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { background: #1e1e1e; color: #ccc; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; padding: 24px; }
  .header { margin-bottom: 24px; }
  .header h1 { font-size: 20px; color: #fff; margin-bottom: 8px; }
  .meta { font-size: 12px; color: #999; }
  .summary { display: flex; gap: 16px; padding: 12px 16px; background: #252526; border-radius: 6px; margin-bottom: 16px; font-size: 14px; }
  .passed { color: #4ec9b0; }
  .failed { color: #f14c4c; }
</style>
</head>
<body>
<div class="header">
  <h1>Test Report: ${escapeHtml(run.name)}</h1>
  <p class="meta">${date} &middot; ${navigator.userAgent.split(' ').slice(-1)[0]}</p>
</div>
<div class="summary">
  <span class="passed">${passed} passed</span>
  <span class="failed">${failed} failed</span>
  <span style="color:#999;">${(duration / 1000).toFixed(1)}s total</span>
</div>
<div>${stepsHtml}</div>
</body>
</html>`;
}

function escapeHtml(str: string): string {
  return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}
