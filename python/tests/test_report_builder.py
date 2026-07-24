"""
test_report_builder.py — pytest tests for report_builder.py

Covers:
  - JSON run loading (single file and directory)
  - JUnit XML structure and content
  - HTML report generation (structure, dark theme CSS, score)
  - Trend analysis computation
  - Flaky test detection
  - Duration statistics
  - CLI argument parsing and file output
"""

from __future__ import annotations

import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from report_builder import (
    RunSummary,
    ResultSummary,
    StepSummary,
    TrendPoint,
    build_html_report,
    build_junit_xml,
    build_parser,
    compute_trends,
    detect_flaky_tests,
    duration_trend,
    load_run,
    load_runs_from_dir,
    main,
)
from tests.conftest import make_run_report


# ---------------------------------------------------------------------------
# JSON loading
# ---------------------------------------------------------------------------


class TestLoadRun:
    def test_loads_valid_json_file(self, run_report_file: Path):
        run = load_run(run_report_file)
        assert isinstance(run, RunSummary)

    def test_run_id_preserved(self, run_report_file: Path, sample_run_report: dict):
        run = load_run(run_report_file)
        assert run.run_id == sample_run_report["run_id"]

    def test_result_count_matches(self, run_report_file: Path, sample_run_report: dict):
        run = load_run(run_report_file)
        assert len(run.results) == sample_run_report["total"]

    def test_result_names_preserved(self, run_report_file: Path):
        run = load_run(run_report_file)
        names = [r.test_name for r in run.results]
        assert all(isinstance(n, str) and len(n) > 0 for n in names)

    def test_step_results_loaded(self, run_report_file: Path):
        run = load_run(run_report_file)
        # All results should have step_results
        for r in run.results:
            assert isinstance(r.steps, list)

    def test_passed_flag_correct(self, run_report_file: Path):
        run = load_run(run_report_file)
        # sample_run_report is 4/4 passing
        assert all(r.passed for r in run.results)

    def test_pass_rate_calculated(self, run_report_file: Path):
        run = load_run(run_report_file)
        assert run.pass_rate == 100.0

    def test_missing_key_raises(self, tmp_path: Path):
        bad = tmp_path / "bad.json"
        bad.write_text('{"run_id": "x"}', encoding="utf-8")
        with pytest.raises(KeyError):
            load_run(bad)


class TestLoadRunsFromDir:
    def test_loads_multiple_files(self, run_reports_dir: Path):
        runs = load_runs_from_dir(run_reports_dir)
        assert len(runs) == 3

    def test_ignores_non_run_files(self, run_reports_dir: Path):
        (run_reports_dir / "unrelated.json").write_text('{"x": 1}', encoding="utf-8")
        runs = load_runs_from_dir(run_reports_dir)
        assert len(runs) == 3

    def test_empty_dir_returns_empty(self, tmp_path: Path):
        runs = load_runs_from_dir(tmp_path)
        assert runs == []

    def test_corrupt_file_logged_skipped(self, run_reports_dir: Path):
        (run_reports_dir / "run_corrupt.json").write_text("not json!", encoding="utf-8")
        # Should not raise, just skip
        runs = load_runs_from_dir(run_reports_dir)
        assert len(runs) == 3


# ---------------------------------------------------------------------------
# JUnit XML
# ---------------------------------------------------------------------------


class TestJUnitXml:
    def _run(self, total: int = 4, passed: int | None = None) -> RunSummary:
        data = make_run_report(total=total, passed=passed if passed is not None else total)
        return load_run(
            _write_and_return(data, Path("/tmp") / f"run_{data['run_id']}.json")
        )

    def test_xml_is_valid(self, run_report_file: Path):
        run = load_run(run_report_file)
        xml_str = build_junit_xml(run)
        root = ET.fromstring(xml_str)  # raises if invalid
        assert root is not None

    def test_xml_has_testsuite_tag(self, run_report_file: Path):
        run = load_run(run_report_file)
        xml_str = build_junit_xml(run)
        assert "<testsuite" in xml_str

    def test_xml_test_count_attribute(self, run_report_file: Path, sample_run_report: dict):
        run = load_run(run_report_file)
        xml_str = build_junit_xml(run)
        root = ET.fromstring(xml_str)
        assert root.get("tests") == str(sample_run_report["total"])

    def test_xml_failures_count(self, tmp_path: Path):
        data = make_run_report(total=4, passed=2)
        path = tmp_path / f"run_{data['run_id']}.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        run = load_run(path)
        xml_str = build_junit_xml(run)
        root = ET.fromstring(xml_str)
        assert root.get("failures") == "2"

    def test_xml_testcase_elements(self, run_report_file: Path, sample_run_report: dict):
        run = load_run(run_report_file)
        xml_str = build_junit_xml(run)
        root = ET.fromstring(xml_str)
        testcases = root.findall("testcase")
        assert len(testcases) == sample_run_report["total"]

    def test_xml_failed_has_failure_element(self, tmp_path: Path):
        data = make_run_report(total=2, passed=1)
        path = tmp_path / f"run_{data['run_id']}.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        run = load_run(path)
        xml_str = build_junit_xml(run)
        root = ET.fromstring(xml_str)
        failures = root.findall(".//failure")
        assert len(failures) >= 1

    def test_xml_passed_has_no_failure_element(self, run_report_file: Path):
        run = load_run(run_report_file)
        xml_str = build_junit_xml(run)
        root = ET.fromstring(xml_str)
        # All tests pass — no failure elements
        assert root.findall(".//failure") == []

    def test_xml_suite_name_attribute(self, run_report_file: Path, sample_run_report: dict):
        run = load_run(run_report_file)
        xml_str = build_junit_xml(run)
        root = ET.fromstring(xml_str)
        assert root.get("name") == sample_run_report["suite_name"]


def _write_and_return(data: dict, path: Path) -> Path:
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# HTML report
# ---------------------------------------------------------------------------


class TestHtmlReport:
    def test_html_written_to_file(self, run_reports_dir: Path, tmp_path: Path):
        runs = load_runs_from_dir(run_reports_dir)
        out = tmp_path / "report.html"
        build_html_report(runs, out)
        assert out.exists()
        assert out.stat().st_size > 500

    def test_html_has_doctype(self, run_reports_dir: Path, tmp_path: Path):
        runs = load_runs_from_dir(run_reports_dir)
        out = tmp_path / "report.html"
        build_html_report(runs, out)
        content = out.read_text()
        assert "<!DOCTYPE html>" in content

    def test_html_has_dark_background(self, run_reports_dir: Path, tmp_path: Path):
        runs = load_runs_from_dir(run_reports_dir)
        out = tmp_path / "report.html"
        build_html_report(runs, out)
        content = out.read_text()
        assert "#0d1117" in content  # dark background color

    def test_html_contains_suite_name(self, run_reports_dir: Path, tmp_path: Path):
        runs = load_runs_from_dir(run_reports_dir)
        out = tmp_path / "report.html"
        build_html_report(runs, out)
        content = out.read_text()
        assert "smoke" in content

    def test_html_contains_pass_stats(self, run_reports_dir: Path, tmp_path: Path):
        runs = load_runs_from_dir(run_reports_dir)
        out = tmp_path / "report.html"
        build_html_report(runs, out)
        content = out.read_text()
        assert "Passed" in content or "passed" in content

    def test_html_contains_results_table(self, run_reports_dir: Path, tmp_path: Path):
        runs = load_runs_from_dir(run_reports_dir)
        out = tmp_path / "report.html"
        build_html_report(runs, out)
        content = out.read_text()
        assert "<table" in content
        assert "<tbody" in content

    def test_html_progress_bar_present(self, run_reports_dir: Path, tmp_path: Path):
        runs = load_runs_from_dir(run_reports_dir)
        out = tmp_path / "report.html"
        build_html_report(runs, out)
        content = out.read_text()
        assert "progress-fill" in content

    def test_html_empty_runs_no_crash(self, tmp_path: Path, capsys):
        out = tmp_path / "report.html"
        build_html_report([], out)
        captured = capsys.readouterr()
        assert "No runs" in captured.err

    def test_html_run_history_section(self, run_reports_dir: Path, tmp_path: Path):
        runs = load_runs_from_dir(run_reports_dir)
        out = tmp_path / "report.html"
        build_html_report(runs, out)
        content = out.read_text()
        assert "Run History" in content


# ---------------------------------------------------------------------------
# Trend analysis
# ---------------------------------------------------------------------------


class TestComputeTrends:
    def _runs(self, specs: list[tuple[int, int]]) -> list[RunSummary]:
        results = []
        for total, passed in specs:
            data = make_run_report(total=total, passed=passed)
            tmp = Path("/tmp") / f"run_{data['run_id']}.json"
            tmp.write_text(json.dumps(data))
            results.append(load_run(tmp))
        return results

    def test_trend_count_matches_runs(self):
        runs = self._runs([(4, 4), (4, 3), (4, 4)])
        trends = compute_trends(runs)
        assert len(trends) == 3

    def test_trend_pass_rates(self):
        runs = self._runs([(4, 4), (4, 2)])
        trends = compute_trends(runs)
        assert trends[0].pass_rate == 100.0
        assert trends[1].pass_rate == 50.0

    def test_trend_point_has_run_id(self):
        runs = self._runs([(4, 4)])
        trends = compute_trends(runs)
        assert isinstance(trends[0].run_id, str)
        assert len(trends[0].run_id) > 0

    def test_trend_duration_preserved(self):
        runs = self._runs([(4, 4)])
        trends = compute_trends(runs)
        assert trends[0].duration_ms > 0


class TestDetectFlakyTests:
    def _runs(self, specs: list[tuple[int, int]]) -> list[RunSummary]:
        results = []
        for total, passed in specs:
            data = make_run_report(total=total, passed=passed)
            tmp = Path("/tmp") / f"run_{data['run_id']}.json"
            tmp.write_text(json.dumps(data))
            results.append(load_run(tmp))
        return results

    def test_no_flaky_when_all_pass(self):
        runs = self._runs([(4, 4), (4, 4), (4, 4)])
        flaky = detect_flaky_tests(runs)
        assert flaky == {}

    def test_detects_flaky_test(self):
        runs = self._runs([(4, 4), (4, 3), (4, 4)])
        flaky = detect_flaky_tests(runs)
        # "Test Case 4" fails in second run only
        assert len(flaky) >= 1

    def test_flaky_has_required_keys(self):
        runs = self._runs([(4, 3), (4, 4)])
        flaky = detect_flaky_tests(runs)
        for name, info in flaky.items():
            assert "runs" in info
            assert "flakiness_rate" in info
            assert "pass_count" in info
            assert "fail_count" in info

    def test_single_run_no_flaky(self):
        runs = self._runs([(4, 3)])
        flaky = detect_flaky_tests(runs)
        assert flaky == {}


class TestDurationTrend:
    def _runs(self, specs: list[tuple[int, int]]) -> list[RunSummary]:
        results = []
        for total, passed in specs:
            data = make_run_report(total=total, passed=passed)
            tmp = Path("/tmp") / f"run_{data['run_id']}.json"
            tmp.write_text(json.dumps(data))
            results.append(load_run(tmp))
        return results

    def test_returns_empty_for_no_runs(self):
        assert duration_trend([]) == {}

    def test_returns_stats_for_runs(self):
        runs = self._runs([(4, 4), (4, 4), (4, 4)])
        stats = duration_trend(runs)
        assert "min_ms" in stats
        assert "max_ms" in stats
        assert "mean_ms" in stats
        assert "stdev_ms" in stats

    def test_min_lte_mean_lte_max(self):
        runs = self._runs([(4, 4), (4, 3), (4, 2)])
        stats = duration_trend(runs)
        assert stats["min_ms"] <= stats["mean_ms"] <= stats["max_ms"]


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


class TestReportBuilderCLI:
    def test_parser_requires_results(self):
        parser = build_parser()
        with pytest.raises(SystemExit):
            parser.parse_args([])

    def test_parser_default_format(self):
        parser = build_parser()
        args = parser.parse_args(["--results", "results/"])
        assert args.format == "all"

    def test_main_nonexistent_path_returns_1(self):
        with patch("sys.argv", ["report_builder", "--results", "/no/such/path"]):
            result = main()
        assert result == 1

    def test_main_generates_html_file(self, run_report_file: Path, tmp_path: Path):
        with patch(
            "sys.argv",
            [
                "report_builder",
                "--results", str(run_report_file),
                "--format", "html",
                "--out", str(tmp_path),
            ],
        ):
            result = main()
        assert result == 0
        html_files = list(tmp_path.glob("report_*.html"))
        assert len(html_files) == 1

    def test_main_generates_junit_xml(self, run_report_file: Path, tmp_path: Path):
        with patch(
            "sys.argv",
            [
                "report_builder",
                "--results", str(run_report_file),
                "--format", "junit",
                "--out", str(tmp_path),
            ],
        ):
            result = main()
        assert result == 0
        xml_files = list(tmp_path.glob("junit_*.xml"))
        assert len(xml_files) == 1

    def test_main_all_format_generates_both(self, run_reports_dir: Path, tmp_path: Path):
        with patch(
            "sys.argv",
            [
                "report_builder",
                "--results", str(run_reports_dir),
                "--format", "all",
                "--out", str(tmp_path),
            ],
        ):
            result = main()
        assert result == 0
        assert len(list(tmp_path.glob("report_*.html"))) == 1
        assert len(list(tmp_path.glob("junit_*.xml"))) == 1
        assert len(list(tmp_path.glob("trend_analysis.json"))) == 1
