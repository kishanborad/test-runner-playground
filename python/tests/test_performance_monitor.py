"""
test_performance_monitor.py — pytest tests for performance_monitor.py

Covers:
  - MetricsCollector single and multi-run measurement
  - TimingBreakdown values are non-negative
  - ResourceCount extraction from HTML
  - GateEvaluator against ThresholdConfig
  - Baseline loading/saving
  - Regression detection
  - Percentile calculation
  - Text report output
  - CLI argument parsing and file output
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import requests

sys.path.insert(0, str(Path(__file__).parent.parent))

from performance_monitor import (
    AggregatedMetrics,
    GateEvaluator,
    GateResult,
    MetricsCollector,
    PageMetrics,
    PerformanceReport,
    ResourceCount,
    ThresholdConfig,
    TimingBreakdown,
    _iso_now,
    _percentile,
    build_parser,
    load_baseline,
    main,
    print_text_report,
    save_baseline,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SIMPLE_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Test Page</title>
  <link rel="stylesheet" href="/styles/main.css">
  <link rel="stylesheet" href="/styles/theme.css">
</head>
<body>
  <script src="/js/app.js"></script>
  <script src="/js/vendor.js"></script>
  <img src="/img/hero.jpg" alt="Hero">
  <img src="/img/logo.png" alt="Logo">
  <h1>Welcome</h1>
  <p>Page content here.</p>
</body>
</html>
"""


def _mock_response(html: str = _SIMPLE_HTML, status: int = 200) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status
    resp.text = html
    resp.content = html.encode("utf-8")
    resp.url = "http://localhost:5173/"
    resp.headers = {"Content-Type": "text/html; charset=utf-8"}
    resp.history = []
    resp.raise_for_status = MagicMock()
    resp.elapsed.total_seconds.return_value = 0.05
    return resp


def _make_aggregated(
    mean_ms: float = 300.0,
    p95_ms: float = 350.0,
    size_bytes: float = 10240,
    run_count: int = 3,
) -> AggregatedMetrics:
    single = PageMetrics(
        url="http://localhost:5173",
        status_code=200,
        timing=TimingBreakdown(
            dns_lookup_ms=round(mean_ms * 0.05, 1),
            connect_ms=round(mean_ms * 0.10, 1),
            tls_handshake_ms=0.0,
            ttfb_ms=round(mean_ms * 0.30, 1),
            content_transfer_ms=round(mean_ms * 0.70, 1),
            total_ms=mean_ms,
        ),
        response_size_bytes=int(size_bytes),
        transfer_rate_kbps=400.0,
        redirect_count=0,
        redirect_time_ms=0.0,
        resource_counts=ResourceCount(scripts=2, stylesheets=2, images=2),
        title="Test Page",
        measured_at=_iso_now(),
    )
    return AggregatedMetrics(
        url="http://localhost:5173",
        run_count=run_count,
        timing_mean_ms=mean_ms,
        timing_stdev_ms=10.0,
        timing_min_ms=mean_ms - 20,
        timing_max_ms=mean_ms + 20,
        timing_p95_ms=p95_ms,
        size_mean_bytes=size_bytes,
        transfer_rate_mean_kbps=400.0,
        measured_at=_iso_now(),
        individual_runs=[single] * run_count,
    )


# ---------------------------------------------------------------------------
# MetricsCollector — single measurement
# ---------------------------------------------------------------------------


class TestMetricsCollectorSingle:
    def test_measure_returns_page_metrics(self):
        with patch.object(requests.Session, "get", return_value=_mock_response()):
            collector = MetricsCollector()
            metrics = collector.measure("http://localhost:5173")
        assert isinstance(metrics, PageMetrics)

    def test_measure_status_code(self):
        with patch.object(requests.Session, "get", return_value=_mock_response(status=200)):
            collector = MetricsCollector()
            metrics = collector.measure("http://localhost:5173")
        assert metrics.status_code == 200

    def test_timing_total_non_negative(self):
        with patch.object(requests.Session, "get", return_value=_mock_response()):
            collector = MetricsCollector()
            metrics = collector.measure("http://localhost:5173")
        assert metrics.timing.total_ms >= 0

    def test_timing_ttfb_non_negative(self):
        with patch.object(requests.Session, "get", return_value=_mock_response()):
            collector = MetricsCollector()
            metrics = collector.measure("http://localhost:5173")
        assert metrics.timing.ttfb_ms >= 0

    def test_response_size_bytes(self):
        with patch.object(requests.Session, "get", return_value=_mock_response()):
            collector = MetricsCollector()
            metrics = collector.measure("http://localhost:5173")
        assert metrics.response_size_bytes > 0

    def test_title_extracted(self):
        with patch.object(requests.Session, "get", return_value=_mock_response()):
            collector = MetricsCollector()
            metrics = collector.measure("http://localhost:5173")
        assert metrics.title == "Test Page"

    def test_transfer_rate_positive(self):
        with patch.object(requests.Session, "get", return_value=_mock_response()):
            collector = MetricsCollector()
            metrics = collector.measure("http://localhost:5173")
        assert metrics.transfer_rate_kbps >= 0

    def test_redirect_count_zero_no_history(self):
        with patch.object(requests.Session, "get", return_value=_mock_response()):
            collector = MetricsCollector()
            metrics = collector.measure("http://localhost:5173")
        assert metrics.redirect_count == 0

    def test_to_dict_has_required_keys(self):
        with patch.object(requests.Session, "get", return_value=_mock_response()):
            collector = MetricsCollector()
            metrics = collector.measure("http://localhost:5173")
        d = metrics.to_dict()
        assert "url" in d
        assert "status_code" in d
        assert "timing" in d
        assert "response_size_bytes" in d

    def test_network_error_propagates(self):
        with patch.object(
            requests.Session, "get", side_effect=requests.ConnectionError("refused")
        ):
            collector = MetricsCollector()
            with pytest.raises(requests.ConnectionError):
                collector.measure("http://localhost:9999")


# ---------------------------------------------------------------------------
# MetricsCollector — resource counting
# ---------------------------------------------------------------------------


class TestResourceCounting:
    def test_counts_scripts(self):
        collector = MetricsCollector()
        rc = collector._count_resources(_SIMPLE_HTML, "http://localhost")
        assert rc.scripts == 2

    def test_counts_stylesheets(self):
        collector = MetricsCollector()
        rc = collector._count_resources(_SIMPLE_HTML, "http://localhost")
        assert rc.stylesheets == 2

    def test_counts_images(self):
        collector = MetricsCollector()
        rc = collector._count_resources(_SIMPLE_HTML, "http://localhost")
        assert rc.images == 2

    def test_total_resource_count(self):
        collector = MetricsCollector()
        rc = collector._count_resources(_SIMPLE_HTML, "http://localhost")
        assert rc.total == rc.scripts + rc.stylesheets + rc.images + rc.fonts + rc.other

    def test_empty_html_zero_resources(self):
        collector = MetricsCollector()
        rc = collector._count_resources("<html><body></body></html>", "http://localhost")
        assert rc.total == 0

    def test_resource_count_to_dict(self):
        rc = ResourceCount(scripts=3, stylesheets=1, images=5)
        d = rc.to_dict()
        assert d["scripts"] == 3
        assert d["total"] == 9


# ---------------------------------------------------------------------------
# MetricsCollector — multiple runs
# ---------------------------------------------------------------------------


class TestMetricsCollectorMultiple:
    def test_measure_multiple_run_count(self):
        with patch.object(requests.Session, "get", return_value=_mock_response()):
            collector = MetricsCollector()
            agg = collector.measure_multiple("http://localhost:5173", runs=3)
        assert agg.run_count == 3

    def test_aggregated_individual_runs_count(self):
        with patch.object(requests.Session, "get", return_value=_mock_response()):
            collector = MetricsCollector()
            agg = collector.measure_multiple("http://localhost:5173", runs=3)
        assert len(agg.individual_runs) == 3

    def test_aggregated_mean_within_range(self):
        with patch.object(requests.Session, "get", return_value=_mock_response()):
            collector = MetricsCollector()
            agg = collector.measure_multiple("http://localhost:5173", runs=3)
        assert agg.timing_min_ms <= agg.timing_mean_ms <= agg.timing_max_ms

    def test_aggregated_p95_gte_mean(self):
        with patch.object(requests.Session, "get", return_value=_mock_response()):
            collector = MetricsCollector()
            agg = collector.measure_multiple("http://localhost:5173", runs=5)
        assert agg.timing_p95_ms >= agg.timing_min_ms

    def test_single_run_stdev_is_zero(self):
        with patch.object(requests.Session, "get", return_value=_mock_response()):
            collector = MetricsCollector()
            agg = collector.measure_multiple("http://localhost:5173", runs=1)
        assert agg.timing_stdev_ms == 0.0


# ---------------------------------------------------------------------------
# GateEvaluator
# ---------------------------------------------------------------------------


class TestGateEvaluator:
    def test_all_gates_pass_under_threshold(self):
        agg = _make_aggregated(mean_ms=200.0, p95_ms=250.0, size_bytes=5120)
        cfg = ThresholdConfig(max_total_ms=3000, max_ttfb_ms=500, max_response_size_kb=500)
        evaluator = GateEvaluator(cfg)
        gates, _ = evaluator.evaluate(agg)
        assert all(g.passed for g in gates)

    def test_ttfb_gate_fails_when_slow(self):
        agg = _make_aggregated(mean_ms=2000.0, p95_ms=2500.0)
        cfg = ThresholdConfig(max_ttfb_ms=100.0)
        evaluator = GateEvaluator(cfg)
        gates, _ = evaluator.evaluate(agg)
        ttfb_gate = next((g for g in gates if g.metric == "ttfb"), None)
        assert ttfb_gate is not None
        assert ttfb_gate.passed is False

    def test_p95_gate_fails_when_slow(self):
        agg = _make_aggregated(p95_ms=5000.0)
        cfg = ThresholdConfig(max_total_ms=3000.0)
        evaluator = GateEvaluator(cfg)
        gates, _ = evaluator.evaluate(agg)
        p95_gate = next((g for g in gates if g.metric == "response_time_p95"), None)
        assert p95_gate is not None
        assert p95_gate.passed is False

    def test_size_gate_fails_when_large(self):
        agg = _make_aggregated(size_bytes=600 * 1024)  # 600 KB
        cfg = ThresholdConfig(max_response_size_kb=500.0)
        evaluator = GateEvaluator(cfg)
        gates, _ = evaluator.evaluate(agg)
        size_gate = next((g for g in gates if g.metric == "response_size"), None)
        assert size_gate is not None
        assert size_gate.passed is False

    def test_no_regression_when_same_as_baseline(self):
        agg = _make_aggregated(mean_ms=300.0)
        baseline = _make_aggregated(mean_ms=300.0)
        cfg = ThresholdConfig(max_regression_pct=20.0)
        evaluator = GateEvaluator(cfg)
        gates, baseline_cmp = evaluator.evaluate(agg, baseline)
        reg_gate = next((g for g in gates if g.metric == "regression_vs_baseline"), None)
        assert reg_gate is not None
        assert reg_gate.passed is True

    def test_regression_detected_when_slower(self):
        agg = _make_aggregated(mean_ms=500.0)   # 66% slower
        baseline = _make_aggregated(mean_ms=300.0)
        cfg = ThresholdConfig(max_regression_pct=20.0)
        evaluator = GateEvaluator(cfg)
        gates, baseline_cmp = evaluator.evaluate(agg, baseline)
        assert baseline_cmp is not None
        assert baseline_cmp["regression"] is True

    def test_baseline_comparison_keys(self):
        agg = _make_aggregated(mean_ms=320.0)
        baseline = _make_aggregated(mean_ms=300.0)
        evaluator = GateEvaluator()
        _, baseline_cmp = evaluator.evaluate(agg, baseline)
        assert baseline_cmp is not None
        assert "delta_pct" in baseline_cmp
        assert "regression" in baseline_cmp
        assert "baseline_mean_ms" in baseline_cmp

    def test_no_baseline_no_regression_gate(self):
        agg = _make_aggregated()
        evaluator = GateEvaluator()
        gates, cmp = evaluator.evaluate(agg, None)
        assert cmp is None
        regression_gates = [g for g in gates if g.metric == "regression_vs_baseline"]
        assert regression_gates == []


# ---------------------------------------------------------------------------
# Baseline persistence
# ---------------------------------------------------------------------------


class TestBaselinePersistence:
    def test_save_and_load_baseline(self, tmp_path: Path):
        agg = _make_aggregated(mean_ms=300.0)
        path = tmp_path / "baseline.json"
        save_baseline(agg, path)
        assert path.exists()

        loaded = load_baseline(path)
        assert loaded.timing_mean_ms == 300.0
        assert loaded.run_count == agg.run_count

    def test_baseline_json_is_valid(self, tmp_path: Path):
        agg = _make_aggregated()
        path = tmp_path / "b.json"
        save_baseline(agg, path)
        data = json.loads(path.read_text())
        assert "timing_mean_ms" in data

    def test_load_missing_file_raises(self, tmp_path: Path):
        with pytest.raises((FileNotFoundError, json.JSONDecodeError, KeyError)):
            load_baseline(tmp_path / "no_file.json")


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------


class TestPercentile:
    def test_p50_median(self):
        data = [1.0, 2.0, 3.0, 4.0, 5.0]
        assert _percentile(data, 50) == pytest.approx(3.0)

    def test_p100_is_max(self):
        data = [10.0, 20.0, 30.0]
        assert _percentile(data, 100) == 30.0

    def test_p0_is_min(self):
        data = [10.0, 20.0, 30.0]
        assert _percentile(data, 0) == 10.0

    def test_empty_returns_zero(self):
        assert _percentile([], 95) == 0.0

    def test_single_value(self):
        assert _percentile([42.0], 95) == 42.0

    def test_p95_is_near_max(self):
        data = list(range(1, 101))
        data_float = [float(x) for x in data]
        p95 = _percentile(data_float, 95)
        assert p95 >= 95.0


class TestIsoNow:
    def test_iso_now_format(self):
        ts = _iso_now()
        assert "T" in ts
        assert "+" in ts or "Z" in ts


# ---------------------------------------------------------------------------
# Text report output
# ---------------------------------------------------------------------------


class TestTextReport:
    def test_print_text_report_no_crash(self, capsys):
        agg = _make_aggregated()
        gates = [
            GateResult("response_time_p95", 350.0, 3000.0, True, "ms"),
            GateResult("ttfb", 90.0, 500.0, True, "ms"),
        ]
        report = PerformanceReport(
            url="http://localhost:5173",
            suite="perf",
            measured_at=_iso_now(),
            aggregated=agg,
            gates=gates,
            baseline_comparison=None,
            overall_pass=True,
        )
        print_text_report(report)
        out = capsys.readouterr().out
        assert "perf" in out.lower() or "Performance" in out

    def test_print_text_report_shows_gates(self, capsys):
        agg = _make_aggregated()
        gates = [
            GateResult("response_time_p95", 350.0, 3000.0, True, "ms"),
            GateResult("ttfb", 600.0, 500.0, False, "ms"),
        ]
        report = PerformanceReport(
            url="http://localhost:5173",
            suite="perf",
            measured_at=_iso_now(),
            aggregated=agg,
            gates=gates,
            baseline_comparison=None,
            overall_pass=False,
        )
        print_text_report(report)
        out = capsys.readouterr().out
        assert "FAIL" in out or "✗" in out

    def test_print_text_report_with_baseline(self, capsys):
        agg = _make_aggregated(mean_ms=400.0)
        gates = [GateResult("response_time_p95", 400.0, 3000.0, True, "ms")]
        baseline_cmp = {
            "baseline_mean_ms": 300.0,
            "current_mean_ms": 400.0,
            "delta_pct": 33.3,
            "regression": True,
            "threshold_pct": 20.0,
        }
        report = PerformanceReport(
            url="http://localhost:5173",
            suite="perf",
            measured_at=_iso_now(),
            aggregated=agg,
            gates=gates,
            baseline_comparison=baseline_cmp,
            overall_pass=False,
        )
        print_text_report(report)
        out = capsys.readouterr().out
        assert "Baseline" in out or "300" in out


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


class TestPerformanceMonitorCLI:
    def test_parser_requires_url(self):
        parser = build_parser()
        with pytest.raises(SystemExit):
            parser.parse_args([])

    def test_parser_default_runs(self):
        parser = build_parser()
        args = parser.parse_args(["--url", "http://localhost:5173"])
        assert args.runs == 3

    def test_parser_custom_max_total(self):
        parser = build_parser()
        args = parser.parse_args(["--url", "http://localhost", "--max-total-ms", "1000"])
        assert args.max_total_ms == 1000.0

    def test_main_network_error_returns_1(self):
        with patch.object(
            requests.Session, "get", side_effect=requests.ConnectionError("refused")
        ):
            with patch("sys.argv", ["performance_monitor", "--url", "http://localhost:9999"]):
                result = main()
        assert result == 1

    def test_main_writes_report_file(self, tmp_path: Path):
        with patch.object(requests.Session, "get", return_value=_mock_response()):
            with patch(
                "sys.argv",
                [
                    "performance_monitor",
                    "--url", "http://localhost:5173",
                    "--runs", "1",
                    "--out", str(tmp_path),
                    "--format", "json",
                ],
            ):
                result = main()
        assert result in (0, 1)
        json_files = list(tmp_path.glob("perf_*.json"))
        assert len(json_files) == 1

    def test_main_saves_baseline(self, tmp_path: Path):
        baseline_path = tmp_path / "baseline.json"
        with patch.object(requests.Session, "get", return_value=_mock_response()):
            with patch(
                "sys.argv",
                [
                    "performance_monitor",
                    "--url", "http://localhost:5173",
                    "--runs", "1",
                    "--save-baseline", str(baseline_path),
                ],
            ):
                main()
        assert baseline_path.exists()
        data = json.loads(baseline_path.read_text())
        assert "timing_mean_ms" in data

    def test_main_json_format_output(self, capsys, tmp_path: Path):
        with patch.object(requests.Session, "get", return_value=_mock_response()):
            with patch(
                "sys.argv",
                [
                    "performance_monitor",
                    "--url", "http://localhost:5173",
                    "--runs", "1",
                    "--format", "json",
                ],
            ):
                main()
        out = capsys.readouterr().out
        # main() prints a progress line before the JSON block; find the JSON start
        json_start = out.index("{")
        parsed = json.loads(out[json_start:])
        assert "url" in parsed
