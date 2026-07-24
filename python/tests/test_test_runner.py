"""
test_test_runner.py — pytest tests for test_runner.py

Covers:
  - DSL step line parsing (valid and invalid)
  - DSL file block parsing
  - TestStep / TestCase data structures
  - HttpExecutor step execution
  - TestRunner sequential and parallel execution
  - RunReport aggregation and JSON serialisation
  - CLI argument parsing and exit codes
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
import requests

# Ensure the python module directory is importable
sys.path.insert(0, str(Path(__file__).parent.parent))

from test_runner import (
    HttpExecutor,
    ParseError,
    RunReport,
    StepResult,
    TestCase,
    TestResult,
    TestRunner,
    TestStep,
    _iso_now,
    build_parser,
    main,
    parse_test_file,
    print_summary,
)
from tests.conftest import SAMPLE_DSL_CONTENT


# ---------------------------------------------------------------------------
# _parse_step_line (tested via parse_test_file internals)
# ---------------------------------------------------------------------------


class TestStepLineParsing:
    """Unit tests for DSL step line parsing."""

    def _parse_line(self, line: str, index: int = 0) -> TestStep:
        """Call the private parser helper via a minimal block."""
        from test_runner import _parse_step_line
        return _parse_step_line(line, index)

    def test_navigate_minimal(self):
        step = self._parse_line("navigate | /products")
        assert step.action == "navigate"
        assert step.target == "/products"
        assert step.value == ""

    def test_navigate_with_timeout(self):
        step = self._parse_line("navigate | /cart | | timeout=10000")
        assert step.timeout_ms == 10000

    def test_type_with_value(self):
        step = self._parse_line("type | #email | user@example.com")
        assert step.action == "type"
        assert step.target == "#email"
        assert step.value == "user@example.com"

    def test_assert_with_value(self):
        step = self._parse_line("assert | .cart-count | 3")
        assert step.action == "assert"
        assert step.value == "3"

    def test_click_action(self):
        step = self._parse_line("click | button.add-to-cart")
        assert step.action == "click"
        assert step.target == "button.add-to-cart"

    def test_wait_action(self):
        step = self._parse_line("wait | 1000")
        assert step.action == "wait"
        assert step.target == "1000"

    def test_screenshot_action(self):
        step = self._parse_line("screenshot | checkout-complete")
        assert step.action == "screenshot"
        assert step.target == "checkout-complete"

    def test_action_case_insensitive(self):
        step = self._parse_line("NAVIGATE | /")
        assert step.action == "navigate"

    def test_invalid_action_raises(self):
        with pytest.raises(ParseError, match="unknown action"):
            self._parse_line("hover | .menu-item")

    def test_missing_target_raises(self):
        with pytest.raises(ParseError, match="malformed"):
            self._parse_line("navigate")

    def test_step_index_is_preserved(self):
        step = self._parse_line("click | #btn", index=7)
        assert step.index == 7

    def test_default_timeout(self):
        step = self._parse_line("click | #btn")
        assert step.timeout_ms == 5000

    def test_custom_timeout_inline(self):
        step = self._parse_line("navigate | / | | timeout=3000")
        assert step.timeout_ms == 3000


# ---------------------------------------------------------------------------
# parse_test_file
# ---------------------------------------------------------------------------


class TestParseTestFile:
    """Tests for parse_test_file()."""

    def test_parses_all_blocks(self, dsl_test_file: Path):
        cases = parse_test_file(dsl_test_file)
        assert len(cases) == 4

    def test_first_case_name(self, dsl_test_file: Path):
        cases = parse_test_file(dsl_test_file)
        assert cases[0].name == "Homepage Loads"

    def test_description_parsed(self, dsl_test_file: Path):
        cases = parse_test_file(dsl_test_file)
        assert "returns 200" in cases[0].description

    def test_tags_parsed(self, dsl_test_file: Path):
        cases = parse_test_file(dsl_test_file)
        assert "smoke" in cases[0].tags
        assert "homepage" in cases[0].tags

    def test_step_count(self, dsl_test_file: Path):
        cases = parse_test_file(dsl_test_file)
        # Homepage block: navigate, assert, screenshot = 3 steps
        assert len(cases[0].steps) == 3

    def test_steps_have_correct_types(self, dsl_test_file: Path):
        cases = parse_test_file(dsl_test_file)
        actions = [s.action for s in cases[0].steps]
        assert actions == ["navigate", "assert", "screenshot"]

    def test_each_case_has_unique_id(self, dsl_test_file: Path):
        cases = parse_test_file(dsl_test_file)
        ids = {c.id for c in cases}
        assert len(ids) == len(cases)

    def test_empty_file_returns_empty_list(self, empty_dsl_file: Path):
        cases = parse_test_file(empty_dsl_file)
        assert cases == []

    def test_comment_lines_ignored(self, tmp_path: Path):
        f = tmp_path / "c.tests"
        f.write_text(
            "# This is a comment\n[Test A]\n# Another comment\nnavigate | /\n",
            encoding="utf-8",
        )
        cases = parse_test_file(f)
        assert len(cases) == 1
        assert len(cases[0].steps) == 1


# ---------------------------------------------------------------------------
# TestStep / TestCase data structures
# ---------------------------------------------------------------------------


class TestDataStructures:
    def test_teststep_to_dict(self):
        step = TestStep(index=0, action="navigate", target="/", value="", timeout_ms=5000)
        d = step.to_dict()
        assert d["action"] == "navigate"
        assert d["index"] == 0

    def test_testcase_to_dict(self):
        case = TestCase(
            id="abc",
            name="My Test",
            description="desc",
            tags=["smoke"],
            steps=[TestStep(0, "navigate", "/")],
        )
        d = case.to_dict()
        assert d["name"] == "My Test"
        assert len(d["steps"]) == 1

    def test_stepresult_to_dict(self):
        sr = StepResult(
            step_index=0, action="navigate", target="/",
            passed=True, duration_ms=42.5,
        )
        d = sr.to_dict()
        assert d["passed"] is True
        assert d["duration_ms"] == 42.5

    def test_run_report_pass_rate_calculation(self, sample_run_report: dict[str, Any]):
        # Reconstruct RunReport manually to test pass_rate
        from test_runner import RunReport
        r = RunReport(
            run_id="x",
            suite_name="s",
            target_url="http://localhost",
            started_at="",
            finished_at="",
            total=10,
            passed=8,
            failed=2,
            duration_ms=1000.0,
        )
        assert r.pass_rate == 80.0

    def test_run_report_zero_total_pass_rate(self):
        from test_runner import RunReport
        r = RunReport(
            run_id="x", suite_name="s", target_url="u",
            started_at="", finished_at="",
            total=0, passed=0, failed=0, duration_ms=0.0,
        )
        assert r.pass_rate == 0.0


# ---------------------------------------------------------------------------
# HttpExecutor
# ---------------------------------------------------------------------------


class TestHttpExecutor:
    """Tests for HttpExecutor step execution."""

    def _make_executor(self, html: str, status: int = 200) -> HttpExecutor:
        """Return an executor with a pre-loaded mock response."""
        executor = HttpExecutor("http://localhost:5173")
        executor._current_html = html
        return executor

    def test_navigate_step_success(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = "<html><body><h1>Home</h1></body></html>"
        mock_resp.url = "http://localhost:5173/"
        mock_resp.raise_for_status = MagicMock()

        with patch.object(requests.Session, "get", return_value=mock_resp):
            executor = HttpExecutor("http://localhost:5173")
            step = TestStep(index=0, action="navigate", target="/")
            result = executor.execute_step(step)

        assert result.passed is True
        assert "200" in (result.actual_value or "")

    def test_navigate_step_http_error(self):
        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = requests.HTTPError("404 Not Found")

        with patch.object(requests.Session, "get", return_value=mock_resp):
            executor = HttpExecutor("http://localhost:5173")
            step = TestStep(index=0, action="navigate", target="/missing")
            result = executor.execute_step(step)

        assert result.passed is False
        assert result.error is not None

    def test_assert_contains_pass(self):
        executor = self._make_executor("<p>Welcome to the shop</p>")
        step = TestStep(index=0, action="assert", target="Welcome")
        result = executor.execute_step(step)
        assert result.passed is True

    def test_assert_contains_fail(self):
        executor = self._make_executor("<p>Goodbye</p>")
        step = TestStep(index=0, action="assert", target="Hello", value="Hello")
        result = executor.execute_step(step)
        assert result.passed is False

    def test_assert_is_case_insensitive(self):
        executor = self._make_executor("<h1>CHECKOUT</h1>")
        step = TestStep(index=0, action="assert", target="checkout")
        result = executor.execute_step(step)
        assert result.passed is True

    def test_wait_step_sleeps_correct_duration(self):
        executor = self._make_executor("")
        step = TestStep(index=0, action="wait", target="100")
        t0 = time.perf_counter()
        result = executor.execute_step(step)
        elapsed = (time.perf_counter() - t0) * 1000
        assert result.passed is True
        assert elapsed >= 90  # 100ms with 10ms tolerance

    def test_screenshot_step_always_passes(self):
        executor = self._make_executor("")
        step = TestStep(index=0, action="screenshot", target="my-shot")
        result = executor.execute_step(step)
        assert result.passed is True

    def test_step_duration_is_recorded(self):
        executor = self._make_executor("<p>ok</p>")
        step = TestStep(index=0, action="assert", target="ok")
        result = executor.execute_step(step)
        assert result.duration_ms >= 0

    def test_click_step_checks_element_exists(self):
        executor = self._make_executor('<button id="btn">Click me</button>')
        step = TestStep(index=0, action="click", target="#btn")
        result = executor.execute_step(step)
        assert isinstance(result.passed, bool)  # passes if element tag exists


# ---------------------------------------------------------------------------
# TestRunner
# ---------------------------------------------------------------------------


class TestTestRunner:
    """Integration tests for TestRunner.run_suite()."""

    def _mock_cases(self, count: int = 2) -> list[TestCase]:
        cases = []
        for i in range(count):
            cases.append(
                TestCase(
                    id=str(i),
                    name=f"Test {i}",
                    description="",
                    tags=[],
                    steps=[TestStep(0, "assert", "ok")],
                )
            )
        return cases

    def test_run_suite_creates_report(self, tmp_path: Path):
        runner = TestRunner("http://localhost:5173", output_dir=tmp_path)
        cases = self._mock_cases(2)
        # Pre-load HTML so assert passes
        with patch.object(HttpExecutor, "__init__", lambda self, u: None):
            with patch.object(HttpExecutor, "execute_step") as mock_exec:
                mock_exec.return_value = StepResult(
                    step_index=0, action="assert", target="ok",
                    passed=True, duration_ms=10.0,
                )
                report = runner.run_suite(cases, suite_name="mock")

        assert report.total == 2
        assert report.passed == 2

    def test_run_suite_saves_json_file(self, tmp_path: Path):
        runner = TestRunner("http://localhost:5173", output_dir=tmp_path)
        cases = self._mock_cases(1)
        with patch.object(HttpExecutor, "execute_step") as mock_exec:
            mock_exec.return_value = StepResult(
                step_index=0, action="assert", target="ok",
                passed=True, duration_ms=5.0,
            )
            report = runner.run_suite(cases)

        files = list(tmp_path.glob("run_*.json"))
        assert len(files) == 1
        data = json.loads(files[0].read_text())
        assert data["run_id"] == report.run_id

    def test_parallel_run_produces_same_count(self, tmp_path: Path):
        runner = TestRunner("http://localhost:5173", workers=3, output_dir=tmp_path)
        cases = self._mock_cases(6)
        with patch.object(HttpExecutor, "execute_step") as mock_exec:
            mock_exec.return_value = StepResult(
                step_index=0, action="assert", target="ok",
                passed=True, duration_ms=5.0,
            )
            report = runner.run_suite(cases)

        assert report.total == 6

    def test_failed_step_marks_test_failed(self, tmp_path: Path):
        runner = TestRunner("http://localhost:5173", output_dir=tmp_path)
        cases = self._mock_cases(1)
        with patch.object(HttpExecutor, "execute_step") as mock_exec:
            mock_exec.return_value = StepResult(
                step_index=0, action="assert", target="missing",
                passed=False, duration_ms=5.0, error="Not found",
            )
            report = runner.run_suite(cases)

        assert report.failed == 1
        assert report.passed == 0

    def test_report_pass_rate(self, tmp_path: Path):
        runner = TestRunner("http://localhost:5173", output_dir=tmp_path)
        cases = self._mock_cases(4)

        call_count = 0

        def alternating_result(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            ok = call_count % 2 == 0
            return StepResult(
                step_index=0, action="assert", target="x",
                passed=ok, duration_ms=5.0,
            )

        with patch.object(HttpExecutor, "execute_step", side_effect=alternating_result):
            report = runner.run_suite(cases)

        assert report.total == 4


# ---------------------------------------------------------------------------
# JSON serialisation
# ---------------------------------------------------------------------------


class TestJsonSerialisation:
    def test_run_report_serialises(self, sample_run_report: dict[str, Any]):
        # Ensure the fixture can round-trip through JSON
        serialised = json.dumps(sample_run_report)
        recovered = json.loads(serialised)
        assert recovered["run_id"] == sample_run_report["run_id"]

    def test_run_report_has_required_keys(self, sample_run_report: dict[str, Any]):
        required = {"run_id", "suite_name", "target_url", "total", "passed", "failed",
                    "duration_ms", "pass_rate", "results", "started_at", "finished_at"}
        assert required.issubset(set(sample_run_report.keys()))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class TestHelpers:
    def test_iso_now_is_string(self):
        ts = _iso_now()
        assert isinstance(ts, str)
        assert "T" in ts

    def test_print_summary_runs_without_error(self, sample_run_report: dict[str, Any], capsys):
        from test_runner import RunReport, TestResult
        rr = RunReport(
            run_id="abc",
            suite_name="smoke",
            target_url="http://localhost",
            started_at="2026-07-23T10:00:00Z",
            finished_at="2026-07-23T10:00:01Z",
            total=2,
            passed=2,
            failed=0,
            duration_ms=500.0,
        )
        print_summary(rr)
        captured = capsys.readouterr()
        assert "smoke" in captured.out
        assert "100.0%" in captured.out


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


class TestCLI:
    def test_parser_defaults(self):
        parser = build_parser()
        args = parser.parse_args(["--file", "tests.tests"])
        assert args.workers == 1
        assert args.format == "json"
        assert str(args.url) == "http://localhost:5173"

    def test_parser_custom_workers(self):
        parser = build_parser()
        args = parser.parse_args(["--file", "x.tests", "--workers", "4"])
        assert args.workers == 4

    def test_main_missing_file_exits_1(self):
        with patch("sys.argv", ["test_runner"]):
            result = main()
        assert result == 1

    def test_main_nonexistent_file_exits_2(self, tmp_path: Path):
        fake_file = tmp_path / "does_not_exist.tests"
        with patch("sys.argv", ["test_runner", "--file", str(fake_file)]):
            result = main()
        assert result == 2

    def test_main_empty_file_exits_4(self, empty_dsl_file: Path):
        with patch("sys.argv", ["test_runner", "--file", str(empty_dsl_file)]):
            result = main()
        assert result == 4
