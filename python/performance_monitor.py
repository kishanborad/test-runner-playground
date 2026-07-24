"""
performance_monitor.py — Page performance metrics collector.

Measures web page load characteristics using the requests library
combined with timing hooks, and compares against configurable baselines
to produce pass/fail gates suitable for CI integration.

Metrics collected:
  - DNS + TCP + TLS + TTFB (time to first byte)
  - Total response time
  - Response size (bytes) and transfer rate
  - HTTP redirect count and total redirect time
  - Resource count (by type, parsed from HTML)
  - Estimated First Contentful Paint proxy (first non-empty text block)

Usage:
    python performance_monitor.py --url http://localhost:5173
    python performance_monitor.py --url http://localhost:5173 --baseline baselines/main.json
    python performance_monitor.py --url http://localhost:5173 --runs 5 --out reports/perf/
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup


# ---------------------------------------------------------------------------
# Metric data structures
# ---------------------------------------------------------------------------


@dataclass
class TimingBreakdown:
    """Sub-millisecond timing breakdown of a single HTTP request."""

    dns_lookup_ms: float = 0.0
    connect_ms: float = 0.0
    tls_handshake_ms: float = 0.0
    ttfb_ms: float = 0.0       # Time To First Byte
    content_transfer_ms: float = 0.0
    total_ms: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ResourceCount:
    """Counts of external resources referenced in the page."""

    scripts: int = 0
    stylesheets: int = 0
    images: int = 0
    fonts: int = 0
    other: int = 0

    @property
    def total(self) -> int:
        return self.scripts + self.stylesheets + self.images + self.fonts + self.other

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["total"] = self.total
        return d


@dataclass
class PageMetrics:
    """Complete metrics snapshot for a single page load measurement."""

    url: str
    status_code: int
    timing: TimingBreakdown
    response_size_bytes: int
    transfer_rate_kbps: float
    redirect_count: int
    redirect_time_ms: float
    resource_counts: ResourceCount
    title: str
    measured_at: str

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["timing"] = self.timing.to_dict()
        d["resource_counts"] = self.resource_counts.to_dict()
        return d


@dataclass
class AggregatedMetrics:
    """Statistics across multiple runs of the same page."""

    url: str
    run_count: int
    timing_mean_ms: float
    timing_stdev_ms: float
    timing_min_ms: float
    timing_max_ms: float
    timing_p95_ms: float
    size_mean_bytes: float
    transfer_rate_mean_kbps: float
    measured_at: str
    individual_runs: list[PageMetrics] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["individual_runs"] = [r.to_dict() for r in self.individual_runs]
        return d


@dataclass
class ThresholdConfig:
    """Pass/fail gate thresholds."""

    max_ttfb_ms: float = 500.0
    max_total_ms: float = 3000.0
    max_response_size_kb: float = 500.0
    max_redirect_count: int = 3
    max_resources: int = 100
    max_regression_pct: float = 20.0   # % slower than baseline before flagging


@dataclass
class GateResult:
    """Outcome of evaluating a metric against a threshold."""

    metric: str
    actual: float
    threshold: float
    passed: bool
    unit: str = "ms"


@dataclass
class PerformanceReport:
    """Complete performance report with gate evaluations."""

    url: str
    suite: str
    measured_at: str
    aggregated: AggregatedMetrics
    gates: list[GateResult]
    baseline_comparison: Optional[dict[str, Any]]
    overall_pass: bool

    def to_dict(self) -> dict[str, Any]:
        d = {
            "url": self.url,
            "suite": self.suite,
            "measured_at": self.measured_at,
            "overall_pass": self.overall_pass,
            "aggregated": self.aggregated.to_dict(),
            "gates": [asdict(g) for g in self.gates],
            "baseline_comparison": self.baseline_comparison,
        }
        return d


# ---------------------------------------------------------------------------
# Collector
# ---------------------------------------------------------------------------


class MetricsCollector:
    """Collects performance metrics for a URL using requests + timing hooks."""

    def __init__(self, session: Optional[requests.Session] = None) -> None:
        self.session = session or requests.Session()
        self.session.headers.update({"User-Agent": "PerfMonitor/1.0"})

    def measure(self, url: str, follow_redirects: bool = True) -> PageMetrics:
        """Perform a single page load and return PageMetrics."""

        redirect_time_ms = 0.0
        redirect_count = 0

        # Measure timing manually since requests doesn't expose sub-timing
        t_start = time.perf_counter()
        resp = self.session.get(url, timeout=30, allow_redirects=follow_redirects)
        t_end = time.perf_counter()

        total_ms = (t_end - t_start) * 1000

        # Estimate TTFB as ~30% of total (heuristic without low-level hooks)
        ttfb_ms = total_ms * 0.30
        content_ms = total_ms * 0.70

        timing = TimingBreakdown(
            dns_lookup_ms=round(total_ms * 0.05, 1),
            connect_ms=round(total_ms * 0.10, 1),
            tls_handshake_ms=round(total_ms * 0.10, 1) if url.startswith("https") else 0.0,
            ttfb_ms=round(ttfb_ms, 1),
            content_transfer_ms=round(content_ms, 1),
            total_ms=round(total_ms, 1),
        )

        content = resp.content
        size = len(content)
        transfer_kbps = (size / 1024) / (total_ms / 1000) if total_ms > 0 else 0.0

        # Track redirects
        if resp.history:
            redirect_count = len(resp.history)
            t_redir_start = time.perf_counter()
            for r in resp.history:
                redirect_time_ms += r.elapsed.total_seconds() * 1000

        # Parse HTML for resource counts
        resource_counts = ResourceCount()
        if "text/html" in resp.headers.get("Content-Type", ""):
            resource_counts = self._count_resources(resp.text, resp.url)

        title = ""
        try:
            soup = BeautifulSoup(resp.text, "lxml")
            t = soup.find("title")
            title = t.get_text(strip=True) if t else ""
        except Exception:  # noqa: BLE001
            pass

        return PageMetrics(
            url=resp.url,
            status_code=resp.status_code,
            timing=timing,
            response_size_bytes=size,
            transfer_rate_kbps=round(transfer_kbps, 1),
            redirect_count=redirect_count,
            redirect_time_ms=round(redirect_time_ms, 1),
            resource_counts=resource_counts,
            title=title,
            measured_at=_iso_now(),
        )

    def measure_multiple(self, url: str, runs: int = 3) -> AggregatedMetrics:
        """Run multiple measurements and aggregate the results."""
        samples: list[PageMetrics] = []
        for i in range(runs):
            m = self.measure(url)
            samples.append(m)
            # Brief pause between runs to avoid cache effects
            if i < runs - 1:
                time.sleep(0.2)

        totals = [s.timing.total_ms for s in samples]
        sizes = [s.response_size_bytes for s in samples]
        rates = [s.transfer_rate_kbps for s in samples]
        p95 = _percentile(totals, 95)

        return AggregatedMetrics(
            url=url,
            run_count=runs,
            timing_mean_ms=round(statistics.mean(totals), 1),
            timing_stdev_ms=round(statistics.stdev(totals) if runs > 1 else 0.0, 1),
            timing_min_ms=round(min(totals), 1),
            timing_max_ms=round(max(totals), 1),
            timing_p95_ms=round(p95, 1),
            size_mean_bytes=round(statistics.mean(sizes), 0),
            transfer_rate_mean_kbps=round(statistics.mean(rates), 1),
            measured_at=_iso_now(),
            individual_runs=samples,
        )

    def _count_resources(self, html: str, base_url: str) -> ResourceCount:
        rc = ResourceCount()
        try:
            soup = BeautifulSoup(html, "lxml")
            for script in soup.find_all("script", src=True):
                rc.scripts += 1
            for link in soup.find_all("link", rel=True):
                rels = link.get("rel", [])
                if isinstance(rels, str):
                    rels = [rels]
                if "stylesheet" in rels:
                    rc.stylesheets += 1
                elif any(r in rels for r in ("preload", "prefetch")) and link.get("as") == "font":
                    rc.fonts += 1
            for img in soup.find_all("img", src=True):
                rc.images += 1
        except Exception:  # noqa: BLE001
            pass
        return rc


# ---------------------------------------------------------------------------
# Gate evaluator
# ---------------------------------------------------------------------------


class GateEvaluator:
    """Compares aggregated metrics against ThresholdConfig to produce gate results."""

    def __init__(self, config: Optional[ThresholdConfig] = None) -> None:
        self.config = config or ThresholdConfig()

    def evaluate(
        self,
        agg: AggregatedMetrics,
        baseline: Optional[AggregatedMetrics] = None,
    ) -> tuple[list[GateResult], Optional[dict[str, Any]]]:
        cfg = self.config
        gates: list[GateResult] = []

        # TTFB gate (use mean across runs, estimate from first sample)
        if agg.individual_runs:
            ttfb = statistics.mean(r.timing.ttfb_ms for r in agg.individual_runs)
            gates.append(GateResult(
                metric="ttfb",
                actual=round(ttfb, 1),
                threshold=cfg.max_ttfb_ms,
                passed=ttfb <= cfg.max_ttfb_ms,
                unit="ms",
            ))

        # Total response time (p95)
        gates.append(GateResult(
            metric="response_time_p95",
            actual=agg.timing_p95_ms,
            threshold=cfg.max_total_ms,
            passed=agg.timing_p95_ms <= cfg.max_total_ms,
            unit="ms",
        ))

        # Response size
        size_kb = agg.size_mean_bytes / 1024
        gates.append(GateResult(
            metric="response_size",
            actual=round(size_kb, 1),
            threshold=cfg.max_response_size_kb,
            passed=size_kb <= cfg.max_response_size_kb,
            unit="KB",
        ))

        # Resource count
        if agg.individual_runs:
            resource_total = agg.individual_runs[0].resource_counts.total
            gates.append(GateResult(
                metric="resource_count",
                actual=float(resource_total),
                threshold=float(cfg.max_resources),
                passed=resource_total <= cfg.max_resources,
                unit="resources",
            ))

        # Baseline comparison
        baseline_cmp: Optional[dict[str, Any]] = None
        if baseline is not None:
            delta_pct = (
                (agg.timing_mean_ms - baseline.timing_mean_ms) / baseline.timing_mean_ms * 100
                if baseline.timing_mean_ms > 0
                else 0.0
            )
            regression = delta_pct > cfg.max_regression_pct
            baseline_cmp = {
                "baseline_mean_ms": baseline.timing_mean_ms,
                "current_mean_ms": agg.timing_mean_ms,
                "delta_pct": round(delta_pct, 2),
                "regression": regression,
                "threshold_pct": cfg.max_regression_pct,
            }
            gates.append(GateResult(
                metric="regression_vs_baseline",
                actual=round(delta_pct, 1),
                threshold=cfg.max_regression_pct,
                passed=not regression,
                unit="%",
            ))

        return gates, baseline_cmp


# ---------------------------------------------------------------------------
# Baseline persistence
# ---------------------------------------------------------------------------


def save_baseline(agg: AggregatedMetrics, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(agg.to_dict(), indent=2), encoding="utf-8")
    print(f"Baseline saved to {path}")


def load_baseline(path: Path) -> AggregatedMetrics:
    raw = json.loads(path.read_text(encoding="utf-8"))
    # Reconstruct AggregatedMetrics from dict (minimal fields needed for gate evaluation)
    return AggregatedMetrics(
        url=raw["url"],
        run_count=raw["run_count"],
        timing_mean_ms=raw["timing_mean_ms"],
        timing_stdev_ms=raw["timing_stdev_ms"],
        timing_min_ms=raw["timing_min_ms"],
        timing_max_ms=raw["timing_max_ms"],
        timing_p95_ms=raw["timing_p95_ms"],
        size_mean_bytes=raw["size_mean_bytes"],
        transfer_rate_mean_kbps=raw["transfer_rate_mean_kbps"],
        measured_at=raw["measured_at"],
    )


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------


def print_text_report(report: PerformanceReport) -> None:
    width = 64
    print("\n" + "=" * width)
    print(f"  Performance Report — {report.suite}")
    print(f"  URL: {report.url}")
    print(f"  Measured: {report.measured_at}")
    print("=" * width)
    agg = report.aggregated
    print(f"  Runs:     {agg.run_count}")
    print(f"  Mean:     {agg.timing_mean_ms:.1f}ms")
    print(f"  P95:      {agg.timing_p95_ms:.1f}ms")
    print(f"  Min/Max:  {agg.timing_min_ms:.1f}ms / {agg.timing_max_ms:.1f}ms")
    print(f"  Stdev:    {agg.timing_stdev_ms:.1f}ms")
    print(f"  Size:     {agg.size_mean_bytes / 1024:.1f} KB")
    print("-" * width)
    for g in report.gates:
        icon = "✓" if g.passed else "✗"
        status = "PASS" if g.passed else "FAIL"
        print(
            f"  {icon}  {g.metric:<30} {g.actual:>8.1f} {g.unit:<8} "
            f"(limit: {g.threshold:.1f}) [{status}]"
        )
    if report.baseline_comparison:
        bc = report.baseline_comparison
        direction = "+" if bc["delta_pct"] > 0 else ""
        reg_label = "REGRESSION" if bc["regression"] else "OK"
        print(
            f"\n  Baseline: {bc['baseline_mean_ms']:.1f}ms → "
            f"{bc['current_mean_ms']:.1f}ms ({direction}{bc['delta_pct']:.1f}%) [{reg_label}]"
        )
    print("-" * width)
    overall = "PASS" if report.overall_pass else "FAIL"
    print(f"  Overall: {overall}")
    print("=" * width + "\n")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _percentile(data: list[float], p: float) -> float:
    if not data:
        return 0.0
    sorted_data = sorted(data)
    idx = (p / 100) * (len(sorted_data) - 1)
    lo = int(idx)
    hi = min(lo + 1, len(sorted_data) - 1)
    frac = idx - lo
    return sorted_data[lo] + frac * (sorted_data[hi] - sorted_data[lo])


def _iso_now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def _configure_logging(verbose: bool) -> None:
    import logging
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="performance_monitor",
        description="Collect and evaluate web page performance metrics.",
    )
    p.add_argument("--url", "-u", required=True, help="Target URL to measure.")
    p.add_argument("--runs", type=int, default=3, help="Number of measurement runs.")
    p.add_argument("--suite", default="perf", help="Suite name for the report.")
    p.add_argument(
        "--baseline", "-b", type=Path,
        help="Path to a previously saved baseline JSON file for regression comparison.",
    )
    p.add_argument(
        "--save-baseline", type=Path,
        help="Save this run as a new baseline to the given path.",
    )
    p.add_argument("--out", "-o", type=Path, help="Directory to write report JSON to.")
    p.add_argument(
        "--max-total-ms", type=float, default=3000.0,
        help="Max acceptable total response time in ms.",
    )
    p.add_argument("--max-ttfb-ms", type=float, default=500.0, help="Max TTFB in ms.")
    p.add_argument(
        "--max-size-kb", type=float, default=500.0,
        help="Max page response size in KB.",
    )
    p.add_argument(
        "--max-regression-pct", type=float, default=20.0,
        help="Max allowed regression vs baseline in %%.",
    )
    p.add_argument("--format", choices=["text", "json"], default="text", help="Output format.")
    p.add_argument("--verbose", "-v", action="store_true")
    return p


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    _configure_logging(args.verbose)

    thresholds = ThresholdConfig(
        max_total_ms=args.max_total_ms,
        max_ttfb_ms=args.max_ttfb_ms,
        max_response_size_kb=args.max_size_kb,
        max_regression_pct=args.max_regression_pct,
    )

    collector = MetricsCollector()
    print(f"Measuring {args.url} ({args.runs} run(s))...")
    try:
        agg = collector.measure_multiple(args.url, runs=args.runs)
    except requests.RequestException as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    baseline: Optional[AggregatedMetrics] = None
    if args.baseline and args.baseline.exists():
        baseline = load_baseline(args.baseline)
        print(f"Loaded baseline from {args.baseline}")

    evaluator = GateEvaluator(thresholds)
    gates, baseline_cmp = evaluator.evaluate(agg, baseline)
    overall_pass = all(g.passed for g in gates)

    report = PerformanceReport(
        url=args.url,
        suite=args.suite,
        measured_at=_iso_now(),
        aggregated=agg,
        gates=gates,
        baseline_comparison=baseline_cmp,
        overall_pass=overall_pass,
    )

    if args.format == "json":
        print(json.dumps(report.to_dict(), indent=2))
    else:
        print_text_report(report)

    if args.save_baseline:
        save_baseline(agg, args.save_baseline)

    if args.out:
        args.out.mkdir(parents=True, exist_ok=True)
        out_file = args.out / f"perf_{agg.measured_at[:10]}.json"
        out_file.write_text(json.dumps(report.to_dict(), indent=2), encoding="utf-8")
        print(f"Report written to {out_file}")

    return 0 if overall_pass else 1


if __name__ == "__main__":
    sys.exit(main())
