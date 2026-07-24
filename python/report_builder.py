"""
report_builder.py — Test report generator for the test-runner-playground.

Consumes test result JSON files produced by test_runner.py and outputs:
  - Dark-themed HTML report (standalone, no external dependencies)
  - JUnit XML (for CI systems: Jenkins, GitHub Actions, etc.)
  - Trend analysis across multiple run JSON files

Usage:
    python report_builder.py --results results/ --out reports/
    python report_builder.py --results results/run_abc123.json --format junit
    python report_builder.py --results results/ --format trend
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional


# ---------------------------------------------------------------------------
# Data models (mirrors test_runner.py output, loaded from JSON)
# ---------------------------------------------------------------------------


@dataclass
class StepSummary:
    step_index: int
    action: str
    target: str
    passed: bool
    duration_ms: float
    error: Optional[str]


@dataclass
class ResultSummary:
    run_id: str
    test_name: str
    passed: bool
    duration_ms: float
    start_time: str
    steps: list[StepSummary]
    error: Optional[str]


@dataclass
class RunSummary:
    run_id: str
    suite_name: str
    target_url: str
    started_at: str
    finished_at: str
    total: int
    passed: int
    failed: int
    duration_ms: float
    pass_rate: float
    results: list[ResultSummary]


@dataclass
class TrendPoint:
    run_id: str
    started_at: str
    total: int
    passed: int
    failed: int
    duration_ms: float
    pass_rate: float


# ---------------------------------------------------------------------------
# JSON loader
# ---------------------------------------------------------------------------


def load_run(path: Path) -> RunSummary:
    """Load a single run report JSON into a RunSummary."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    results = []
    for r in raw.get("results", []):
        steps = [
            StepSummary(
                step_index=s["step_index"],
                action=s["action"],
                target=s["target"],
                passed=s["passed"],
                duration_ms=s["duration_ms"],
                error=s.get("error"),
            )
            for s in r.get("step_results", [])
        ]
        results.append(
            ResultSummary(
                run_id=r["run_id"],
                test_name=r["test_name"],
                passed=r["passed"],
                duration_ms=r["duration_ms"],
                start_time=r["start_time"],
                steps=steps,
                error=r.get("error"),
            )
        )
    return RunSummary(
        run_id=raw["run_id"],
        suite_name=raw["suite_name"],
        target_url=raw["target_url"],
        started_at=raw["started_at"],
        finished_at=raw["finished_at"],
        total=raw["total"],
        passed=raw["passed"],
        failed=raw["failed"],
        duration_ms=raw["duration_ms"],
        pass_rate=raw.get("pass_rate", 0.0),
        results=results,
    )


def load_runs_from_dir(directory: Path) -> list[RunSummary]:
    """Load all run JSON files from a directory, sorted oldest-first."""
    files = sorted(directory.glob("run_*.json"), key=lambda p: p.stat().st_mtime)
    runs = []
    for f in files:
        try:
            runs.append(load_run(f))
        except (KeyError, json.JSONDecodeError) as exc:
            print(f"WARNING: Could not parse {f}: {exc}", file=sys.stderr)
    return runs


# ---------------------------------------------------------------------------
# JUnit XML
# ---------------------------------------------------------------------------


def build_junit_xml(run: RunSummary) -> str:
    """Generate a JUnit XML string from a RunSummary."""
    root = ET.Element(
        "testsuite",
        name=run.suite_name,
        tests=str(run.total),
        failures=str(run.failed),
        errors="0",
        time=f"{run.duration_ms / 1000:.3f}",
        timestamp=run.started_at,
    )

    for r in run.results:
        tc = ET.SubElement(
            root,
            "testcase",
            name=r.test_name,
            classname=run.suite_name,
            time=f"{r.duration_ms / 1000:.3f}",
        )
        if not r.passed:
            message = r.error or "Test failed"
            failure = ET.SubElement(tc, "failure", message=message, type="AssertionError")
            # Build step trace
            step_lines = [
                f"  step[{s.step_index}] {s.action} {s.target}: "
                f"{'PASS' if s.passed else 'FAIL'}"
                + (f" — {s.error}" if s.error else "")
                for s in r.steps
            ]
            failure.text = "\n".join(step_lines)

    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ")
    import io
    buf = io.BytesIO()
    tree.write(buf, encoding="utf-8", xml_declaration=True)
    return buf.getvalue().decode("utf-8")


# ---------------------------------------------------------------------------
# Trend analysis
# ---------------------------------------------------------------------------


def compute_trends(runs: list[RunSummary]) -> list[TrendPoint]:
    return [
        TrendPoint(
            run_id=r.run_id,
            started_at=r.started_at,
            total=r.total,
            passed=r.passed,
            failed=r.failed,
            duration_ms=r.duration_ms,
            pass_rate=r.pass_rate,
        )
        for r in runs
    ]


def detect_flaky_tests(runs: list[RunSummary]) -> dict[str, dict[str, Any]]:
    """Identify tests that sometimes pass and sometimes fail across runs."""
    all_tests: dict[str, list[bool]] = {}
    for run in runs:
        for r in run.results:
            all_tests.setdefault(r.test_name, []).append(r.passed)

    flaky: dict[str, dict[str, Any]] = {}
    for name, outcomes in all_tests.items():
        if len(outcomes) < 2:
            continue
        pass_count = sum(outcomes)
        fail_count = len(outcomes) - pass_count
        if pass_count > 0 and fail_count > 0:
            flaky[name] = {
                "runs": len(outcomes),
                "pass_count": pass_count,
                "fail_count": fail_count,
                "flakiness_rate": round(fail_count / len(outcomes) * 100, 1),
            }
    return flaky


def duration_trend(runs: list[RunSummary]) -> dict[str, float]:
    """Return duration statistics across all runs."""
    durations = [r.duration_ms for r in runs if r.total > 0]
    if not durations:
        return {}
    return {
        "min_ms": min(durations),
        "max_ms": max(durations),
        "mean_ms": round(statistics.mean(durations), 1),
        "stdev_ms": round(statistics.stdev(durations), 1) if len(durations) > 1 else 0.0,
    }


# ---------------------------------------------------------------------------
# HTML report
# ---------------------------------------------------------------------------

_CSS = """
:root {
  --bg: #0d1117;
  --surface: #161b22;
  --border: #30363d;
  --text: #e6edf3;
  --muted: #8b949e;
  --green: #3fb950;
  --red: #f85149;
  --yellow: #d29922;
  --accent: #58a6ff;
  --radius: 8px;
}
* { box-sizing: border-box; margin: 0; padding: 0; }
body { background: var(--bg); color: var(--text); font-family: -apple-system, BlinkMacSystemFont,
  "Segoe UI", Roboto, sans-serif; font-size: 14px; line-height: 1.6; padding: 24px; }
h1 { font-size: 22px; font-weight: 700; margin-bottom: 4px; }
h2 { font-size: 16px; font-weight: 600; margin-bottom: 16px; color: var(--muted); }
h3 { font-size: 14px; font-weight: 600; margin-bottom: 12px; }
.meta { color: var(--muted); font-size: 12px; margin-bottom: 24px; }
.grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
  gap: 12px; margin-bottom: 32px; }
.card { background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius);
  padding: 16px; }
.card-label { font-size: 11px; text-transform: uppercase; letter-spacing: .06em;
  color: var(--muted); margin-bottom: 8px; }
.card-value { font-size: 28px; font-weight: 700; }
.card-value.green { color: var(--green); }
.card-value.red { color: var(--red); }
.card-value.blue { color: var(--accent); }
.progress-bar { height: 8px; background: var(--border); border-radius: 4px;
  overflow: hidden; margin-bottom: 32px; }
.progress-fill { height: 100%; background: var(--green); border-radius: 4px;
  transition: width .4s; }
.results-table { width: 100%; border-collapse: collapse; margin-bottom: 32px; }
.results-table th { text-align: left; font-size: 11px; text-transform: uppercase;
  letter-spacing: .06em; color: var(--muted); padding: 8px 12px;
  border-bottom: 1px solid var(--border); }
.results-table td { padding: 10px 12px; border-bottom: 1px solid var(--border); }
.results-table tr:hover td { background: var(--surface); }
.badge { display: inline-block; padding: 2px 8px; border-radius: 12px; font-size: 11px;
  font-weight: 600; }
.badge.pass { background: rgba(63,185,80,.15); color: var(--green); }
.badge.fail { background: rgba(248,81,73,.15); color: var(--red); }
.steps-block { margin-top: 6px; padding-left: 16px; border-left: 2px solid var(--border);
  font-size: 12px; color: var(--muted); }
.steps-block .step-pass { color: var(--green); }
.steps-block .step-fail { color: var(--red); }
.trend-section { margin-bottom: 32px; }
.trend-list { list-style: none; }
.trend-list li { padding: 6px 0; border-bottom: 1px solid var(--border); display: flex;
  justify-content: space-between; }
.flaky-tag { color: var(--yellow); font-size: 11px; font-weight: 600; }
footer { margin-top: 40px; padding-top: 16px; border-top: 1px solid var(--border);
  color: var(--muted); font-size: 12px; text-align: center; }
"""


def build_html_report(runs: list[RunSummary], output_path: Path) -> None:
    """Generate a single-file dark HTML report for one or more runs."""
    # Use the most recent run for the primary summary
    if not runs:
        print("No runs to report on.", file=sys.stderr)
        return

    latest = runs[-1]
    trends = compute_trends(runs)
    flaky = detect_flaky_tests(runs) if len(runs) > 1 else {}
    dur_stats = duration_trend(runs) if len(runs) > 1 else {}

    pass_pct = round(latest.pass_rate, 1)

    # Build results rows
    rows = []
    for r in latest.results:
        status_cls = "pass" if r.passed else "fail"
        status_label = "PASS" if r.passed else "FAIL"
        steps_html = ""
        if r.steps:
            step_lines = []
            for s in r.steps:
                cls = "step-pass" if s.passed else "step-fail"
                icon = "✓" if s.passed else "✗"
                err = f" — {s.error}" if s.error else ""
                step_lines.append(
                    f'<span class="{cls}">{icon} [{s.action}] {_esc(s.target)}{_esc(err)}</span>'
                )
            steps_html = (
                '<div class="steps-block">' + "<br>".join(step_lines) + "</div>"
            )

        rows.append(
            f"<tr><td>{_esc(r.test_name)}</td>"
            f'<td><span class="badge {status_cls}">{status_label}</span></td>'
            f"<td>{r.duration_ms:.0f}ms</td>"
            f"<td>{len(r.steps)}</td>"
            f"<td>{steps_html}</td></tr>"
        )

    results_html = "\n".join(rows)

    # Build trend table
    trend_rows = []
    for tp in reversed(trends[-10:]):
        icon = "✓" if tp.failed == 0 else "✗"
        color = "green" if tp.failed == 0 else "red"
        trend_rows.append(
            f'<li><span style="color:var(--{color})">{icon} {tp.started_at[:19]}</span>'
            f"<span>{tp.passed}/{tp.total} passed ({tp.pass_rate:.1f}%) — "
            f"{tp.duration_ms:.0f}ms</span></li>"
        )
    trend_html = (
        f'<ul class="trend-list">{"".join(trend_rows)}</ul>'
        if trend_rows
        else "<p>Only one run available — run more tests to see trends.</p>"
    )

    # Flaky tests section
    flaky_html = ""
    if flaky:
        items = []
        for name, info in sorted(flaky.items(), key=lambda x: -x[1]["flakiness_rate"]):
            items.append(
                f'<li><span class="flaky-tag">FLAKY {info["flakiness_rate"]}%</span> '
                f"{_esc(name)} — {info['fail_count']}/{info['runs']} failures</li>"
            )
        flaky_html = (
            '<h3>Flaky Tests</h3><ul class="trend-list">' + "".join(items) + "</ul>"
        )

    # Duration stats
    dur_html = ""
    if dur_stats:
        dur_html = (
            f'<p class="meta">Duration across {len(runs)} runs — '
            f'min: {dur_stats["min_ms"]:.0f}ms · '
            f'max: {dur_stats["max_ms"]:.0f}ms · '
            f'avg: {dur_stats["mean_ms"]:.0f}ms · '
            f'stdev: {dur_stats["stdev_ms"]:.0f}ms</p>'
        )

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Test Report — {_esc(latest.suite_name)}</title>
  <style>{_CSS}</style>
</head>
<body>
  <h1>{_esc(latest.suite_name)}</h1>
  <h2>Run ID: {latest.run_id}</h2>
  <p class="meta">
    Target: {_esc(latest.target_url)} ·
    Started: {latest.started_at[:19]} ·
    Duration: {latest.duration_ms:.0f}ms
  </p>

  <div class="grid">
    <div class="card">
      <div class="card-label">Total</div>
      <div class="card-value blue">{latest.total}</div>
    </div>
    <div class="card">
      <div class="card-label">Passed</div>
      <div class="card-value green">{latest.passed}</div>
    </div>
    <div class="card">
      <div class="card-label">Failed</div>
      <div class="card-value{'  red' if latest.failed else ''}">{latest.failed}</div>
    </div>
    <div class="card">
      <div class="card-label">Pass Rate</div>
      <div class="card-value{'  green' if pass_pct >= 80 else '  red'}">{pass_pct}%</div>
    </div>
  </div>

  <div class="progress-bar">
    <div class="progress-fill" style="width:{pass_pct}%"></div>
  </div>

  <h3>Test Results</h3>
  <table class="results-table">
    <thead>
      <tr>
        <th>Test Name</th>
        <th>Status</th>
        <th>Duration</th>
        <th>Steps</th>
        <th>Step Detail</th>
      </tr>
    </thead>
    <tbody>
      {results_html}
    </tbody>
  </table>

  <div class="trend-section">
    <h3>Run History</h3>
    {dur_html}
    {trend_html}
  </div>

  {flaky_html}

  <footer>
    Generated by report_builder.py · test-runner-playground ·
    {time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime())}
  </footer>
</body>
</html>"""

    output_path.write_text(html, encoding="utf-8")
    print(f"HTML report written to {output_path}")


def _esc(s: str) -> str:
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _configure_logging(verbose: bool) -> None:
    import logging
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="report_builder",
        description="Generate HTML and JUnit XML reports from test_runner.py JSON output.",
    )
    p.add_argument(
        "--results", "-r", type=Path, required=True,
        help="Path to a results JSON file or a directory of run_*.json files.",
    )
    p.add_argument(
        "--out", "-o", type=Path, default=Path("reports"),
        help="Output directory for reports.",
    )
    p.add_argument(
        "--format",
        choices=["html", "junit", "trend", "all"],
        default="all",
        help="Report format(s) to generate.",
    )
    p.add_argument("--verbose", "-v", action="store_true")
    return p


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    _configure_logging(args.verbose)

    # Load runs
    results_path: Path = args.results
    if results_path.is_dir():
        runs = load_runs_from_dir(results_path)
    elif results_path.is_file():
        runs = [load_run(results_path)]
    else:
        print(f"ERROR: {results_path} does not exist.", file=sys.stderr)
        return 1

    if not runs:
        print("No valid run files found.", file=sys.stderr)
        return 2

    args.out.mkdir(parents=True, exist_ok=True)
    latest = runs[-1]

    if args.format in ("html", "all"):
        out = args.out / f"report_{latest.run_id}.html"
        build_html_report(runs, out)

    if args.format in ("junit", "all"):
        xml_str = build_junit_xml(latest)
        out = args.out / f"junit_{latest.run_id}.xml"
        out.write_text(xml_str, encoding="utf-8")
        print(f"JUnit XML written to {out}")

    if args.format in ("trend", "all") and len(runs) > 1:
        trends = compute_trends(runs)
        flaky = detect_flaky_tests(runs)
        trend_data = {
            "runs": len(trends),
            "duration_stats": duration_trend(runs),
            "pass_rates": [t.pass_rate for t in trends],
            "flaky_tests": flaky,
        }
        out = args.out / "trend_analysis.json"
        out.write_text(json.dumps(trend_data, indent=2), encoding="utf-8")
        print(f"Trend analysis written to {out}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
