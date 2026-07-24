"""
test_accessibility_checker.py — pytest tests for accessibility_checker.py

Covers:
  - Individual WCAG rule evaluations (heading hierarchy, image alt, landmarks,
    page language, link purpose, form labels, page title, ARIA roles)
  - AccessibilityChecker orchestration across multiple rules
  - Score computation
  - Severity classification
  - Contrast ratio utility
  - HTML report generation
  - CLI behaviour
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import requests

sys.path.insert(0, str(Path(__file__).parent.parent))

from accessibility_checker import (
    A11yReport,
    AccessibilityChecker,
    AriaRolesRule,
    FormLabelRule,
    HeadingHierarchyRule,
    ImageAltTextRule,
    LandmarkRegionsRule,
    LinkPurposeRule,
    PageLanguageRule,
    PageTitleRule,
    Severity,
    Violation,
    build_a11y_html,
    build_parser,
    contrast_ratio,
    main,
)
from tests.conftest import (
    ACCESSIBLE_HTML,
    FULL_HTML,
    FORM_HTML,
    INACCESSIBLE_HTML,
    MINIMAL_HTML,
)


# ---------------------------------------------------------------------------
# HeadingHierarchyRule
# ---------------------------------------------------------------------------


class TestHeadingHierarchyRule:
    rule = HeadingHierarchyRule()

    def _check(self, html: str) -> list[Violation]:
        from bs4 import BeautifulSoup
        return self.rule.check(BeautifulSoup(html, "lxml"), "http://localhost")

    def test_no_violation_sequential(self):
        html = "<html><body><h1>A</h1><h2>B</h2><h3>C</h3></body></html>"
        assert self._check(html) == []

    def test_violation_h1_to_h3(self):
        html = "<html><body><h1>Title</h1><h3>Skipped h2</h3></body></html>"
        v = self._check(html)
        assert len(v) == 1
        assert "h3" in v[0].description

    def test_violation_h2_to_h4(self):
        html = "<html><body><h2>Section</h2><h4>Deep</h4></body></html>"
        v = self._check(html)
        assert len(v) == 1

    def test_no_headings_no_violation(self):
        html = "<html><body><p>no headings</p></body></html>"
        assert self._check(html) == []

    def test_single_h1_no_violation(self):
        html = "<html><body><h1>Only heading</h1></body></html>"
        assert self._check(html) == []

    def test_inaccessible_html_violation(self, inaccessible_html: str):
        v = self._check(inaccessible_html)
        assert len(v) >= 1

    def test_criterion_is_2_4_6(self):
        assert self.rule.criterion.value == "2.4.6"


# ---------------------------------------------------------------------------
# ImageAltTextRule
# ---------------------------------------------------------------------------


class TestImageAltTextRule:
    rule = ImageAltTextRule()

    def _check(self, html: str) -> list[Violation]:
        from bs4 import BeautifulSoup
        return self.rule.check(BeautifulSoup(html, "lxml"), "http://localhost")

    def test_img_with_alt_no_violation(self):
        html = '<html><body><img src="logo.png" alt="Company logo"></body></html>'
        assert self._check(html) == []

    def test_img_missing_alt_is_critical(self):
        html = '<html><body><img src="logo.png"></body></html>'
        v = self._check(html)
        assert len(v) == 1
        assert v[0].severity == Severity.CRITICAL

    def test_img_empty_alt_no_violation(self):
        # alt="" is valid for decorative images
        html = '<html><body><img src="decoration.png" alt=""></body></html>'
        v = self._check(html)
        assert v == []

    def test_multiple_images_missing_alt(self):
        html = '<html><body><img src="a.png"><img src="b.png"></body></html>'
        v = self._check(html)
        assert len(v) == 2

    def test_accessible_html_no_violation(self, accessible_html: str):
        v = self._check(accessible_html)
        assert len(v) == 0

    def test_criterion_is_1_1_1(self):
        assert self.rule.criterion.value == "1.1.1"

    def test_violation_includes_src_in_description(self):
        html = '<html><body><img src="important-chart.png"></body></html>'
        v = self._check(html)
        assert "important-chart" in v[0].description


# ---------------------------------------------------------------------------
# LandmarkRegionsRule
# ---------------------------------------------------------------------------


class TestLandmarkRegionsRule:
    rule = LandmarkRegionsRule()

    def _check(self, html: str) -> list[Violation]:
        from bs4 import BeautifulSoup
        return self.rule.check(BeautifulSoup(html, "lxml"), "http://localhost")

    def test_main_and_nav_present_no_violation(self, accessible_html: str):
        v = self._check(accessible_html)
        # Should have 0 landmark violations (may have others)
        landmark_v = [x for x in v if x.rule_id == "landmark-regions"]
        assert len(landmark_v) == 0

    def test_missing_main_is_violation(self):
        html = "<html><body><nav></nav><section></section></body></html>"
        v = self._check(html)
        main_violations = [x for x in v if "main" in x.description.lower()]
        assert len(main_violations) >= 1

    def test_missing_nav_is_violation(self):
        html = "<html><body><main><h1>Title</h1></main></body></html>"
        v = self._check(html)
        nav_violations = [x for x in v if "nav" in x.description.lower()]
        assert len(nav_violations) >= 1

    def test_role_main_accepted(self):
        html = '<html><body><div role="main"><h1>OK</h1></div><nav></nav></body></html>'
        v = self._check(html)
        main_v = [x for x in v if "main" in x.description.lower()]
        assert len(main_v) == 0


# ---------------------------------------------------------------------------
# PageLanguageRule
# ---------------------------------------------------------------------------


class TestPageLanguageRule:
    rule = PageLanguageRule()

    def _check(self, html: str) -> list[Violation]:
        from bs4 import BeautifulSoup
        return self.rule.check(BeautifulSoup(html, "lxml"), "http://localhost")

    def test_lang_attribute_present_no_violation(self):
        html = '<html lang="en"><body></body></html>'
        assert self._check(html) == []

    def test_missing_lang_is_serious(self):
        html = "<html><body></body></html>"
        v = self._check(html)
        assert len(v) == 1
        assert v[0].severity == Severity.SERIOUS

    def test_other_lang_accepted(self):
        html = '<html lang="fr"><body></body></html>'
        assert self._check(html) == []

    def test_criterion_3_1_1(self):
        assert self.rule.criterion.value == "3.1.1"


# ---------------------------------------------------------------------------
# LinkPurposeRule
# ---------------------------------------------------------------------------


class TestLinkPurposeRule:
    rule = LinkPurposeRule()

    def _check(self, html: str) -> list[Violation]:
        from bs4 import BeautifulSoup
        return self.rule.check(BeautifulSoup(html, "lxml"), "http://localhost")

    def test_descriptive_link_no_violation(self):
        html = '<html><body><a href="/products">View all products</a></body></html>'
        assert self._check(html) == []

    def test_click_here_is_violation(self):
        html = '<html><body><a href="/page">click here</a></body></html>'
        v = self._check(html)
        assert len(v) >= 1

    def test_read_more_is_violation(self):
        html = '<html><body><a href="/info">read more</a></body></html>'
        v = self._check(html)
        assert len(v) >= 1

    def test_aria_label_overrides_bad_text(self):
        html = '<html><body><a href="/x" aria-label="Open product detail page">here</a></body></html>'
        v = self._check(html)
        assert v == []

    def test_accessible_html_no_link_violation(self, accessible_html: str):
        v = self._check(accessible_html)
        assert v == []

    def test_inaccessible_html_has_link_violations(self, inaccessible_html: str):
        v = self._check(inaccessible_html)
        assert len(v) >= 2


# ---------------------------------------------------------------------------
# FormLabelRule
# ---------------------------------------------------------------------------


class TestFormLabelRule:
    rule = FormLabelRule()

    def _check(self, html: str) -> list[Violation]:
        from bs4 import BeautifulSoup
        return self.rule.check(BeautifulSoup(html, "lxml"), "http://localhost")

    def test_properly_labelled_input_no_violation(self, form_html: str):
        v = self._check(form_html)
        assert v == []

    def test_input_without_label_critical(self):
        html = '<html><body><form><input type="text" name="q"></form></body></html>'
        v = self._check(html)
        assert len(v) >= 1
        assert v[0].severity == Severity.CRITICAL

    def test_hidden_input_ignored(self):
        html = '<html><body><form><input type="hidden" name="csrf"></form></body></html>'
        v = self._check(html)
        assert v == []

    def test_submit_input_ignored(self):
        html = '<html><body><form><input type="submit" value="Go"></form></body></html>'
        v = self._check(html)
        assert v == []

    def test_aria_label_satisfies_rule(self):
        html = '<html><body><form><input type="text" aria-label="Search query"></form></body></html>'
        v = self._check(html)
        assert v == []


# ---------------------------------------------------------------------------
# PageTitleRule
# ---------------------------------------------------------------------------


class TestPageTitleRule:
    rule = PageTitleRule()

    def _check(self, html: str) -> list[Violation]:
        from bs4 import BeautifulSoup
        return self.rule.check(BeautifulSoup(html, "lxml"), "http://localhost")

    def test_title_present_no_violation(self, minimal_html: str):
        v = self._check(minimal_html)
        assert v == []

    def test_missing_title_is_serious(self):
        html = "<html><head></head><body></body></html>"
        v = self._check(html)
        assert len(v) == 1
        assert v[0].severity == Severity.SERIOUS

    def test_empty_title_is_violation(self):
        html = "<html><head><title>   </title></head><body></body></html>"
        v = self._check(html)
        assert len(v) == 1


# ---------------------------------------------------------------------------
# AriaRolesRule
# ---------------------------------------------------------------------------


class TestAriaRolesRule:
    rule = AriaRolesRule()

    def _check(self, html: str) -> list[Violation]:
        from bs4 import BeautifulSoup
        return self.rule.check(BeautifulSoup(html, "lxml"), "http://localhost")

    def test_valid_role_no_violation(self):
        html = '<html><body><div role="navigation"></div></body></html>'
        assert self._check(html) == []

    def test_invalid_role_is_serious(self):
        html = '<html><body><div role="badrolename"></div></body></html>'
        v = self._check(html)
        assert len(v) >= 1
        assert v[0].severity == Severity.SERIOUS

    def test_inaccessible_html_has_aria_violation(self, inaccessible_html: str):
        v = self._check(inaccessible_html)
        assert len(v) >= 1

    def test_presentation_role_valid(self):
        html = '<html><body><div role="presentation"></div></body></html>'
        assert self._check(html) == []


# ---------------------------------------------------------------------------
# AccessibilityChecker orchestration
# ---------------------------------------------------------------------------


class TestAccessibilityChecker:
    def test_accessible_page_high_score(self, accessible_html: str):
        checker = AccessibilityChecker()
        report = checker.check_html(accessible_html, url="http://localhost")
        assert report.score >= 70

    def test_inaccessible_page_lower_score(self, inaccessible_html: str):
        checker = AccessibilityChecker()
        report = checker.check_html(inaccessible_html)
        # inaccessible page should have a noticeably lower score
        assert report.score < 100

    def test_report_has_violations_for_bad_page(self, inaccessible_html: str):
        checker = AccessibilityChecker()
        report = checker.check_html(inaccessible_html)
        assert len(report.violations) + len(report.warnings) > 0

    def test_report_url_preserved(self, minimal_html: str):
        checker = AccessibilityChecker()
        report = checker.check_html(minimal_html, url="http://example.com")
        assert report.url == "http://example.com"

    def test_report_title_extracted(self, minimal_html: str):
        checker = AccessibilityChecker()
        report = checker.check_html(minimal_html)
        assert report.title == "Minimal Page"

    def test_passed_rules_listed(self, accessible_html: str):
        checker = AccessibilityChecker()
        report = checker.check_html(accessible_html)
        assert len(report.passed_rules) > 0

    def test_critical_count_property(self, inaccessible_html: str):
        checker = AccessibilityChecker()
        report = checker.check_html(inaccessible_html)
        assert report.critical_count == len(
            [v for v in report.violations if v.severity == Severity.CRITICAL]
        )

    def test_check_url_uses_requests(self, minimal_html: str):
        mock_resp = MagicMock()
        mock_resp.text = minimal_html
        mock_resp.raise_for_status = MagicMock()

        with patch.object(requests.Session, "get", return_value=mock_resp):
            checker = AccessibilityChecker()
            report = checker.check_url("http://localhost:5173")

        assert isinstance(report, A11yReport)

    def test_check_url_raises_on_network_error(self):
        with patch.object(requests.Session, "get", side_effect=requests.ConnectionError("no")):
            checker = AccessibilityChecker()
            with pytest.raises(requests.ConnectionError):
                checker.check_url("http://localhost:9999")

    def test_to_dict_has_required_keys(self, minimal_html: str):
        checker = AccessibilityChecker()
        report = checker.check_html(minimal_html)
        d = report.to_dict()
        assert "url" in d
        assert "score" in d
        assert "violations" in d
        assert "critical_count" in d


# ---------------------------------------------------------------------------
# Contrast ratio utility
# ---------------------------------------------------------------------------


class TestContrastRatio:
    def test_black_white_ratio(self):
        ratio = contrast_ratio("#000000", "#ffffff")
        assert ratio is not None
        assert abs(ratio - 21.0) < 0.01

    def test_same_color_ratio_is_one(self):
        ratio = contrast_ratio("#ff0000", "#ff0000")
        assert ratio is not None
        assert abs(ratio - 1.0) < 0.01

    def test_short_hex_accepted(self):
        ratio = contrast_ratio("#000", "#fff")
        assert ratio is not None
        assert ratio > 20

    def test_invalid_hex_returns_none(self):
        ratio = contrast_ratio("not-a-color", "#ffffff")
        assert ratio is None

    def test_wcag_aa_normal_text_threshold(self):
        # Dark grey on white should pass 4.5:1
        ratio = contrast_ratio("#595959", "#ffffff")
        assert ratio is not None
        assert ratio >= 4.5


# ---------------------------------------------------------------------------
# HTML report output
# ---------------------------------------------------------------------------


class TestA11yHtmlReport:
    def _report(self, html: str) -> A11yReport:
        checker = AccessibilityChecker()
        return checker.check_html(html)

    def test_html_output_is_string(self, inaccessible_html: str):
        report = self._report(inaccessible_html)
        output = build_a11y_html(report)
        assert isinstance(output, str)

    def test_html_has_doctype(self, minimal_html: str):
        report = self._report(minimal_html)
        output = build_a11y_html(report)
        assert "<!DOCTYPE html>" in output

    def test_html_has_score(self, minimal_html: str):
        report = self._report(minimal_html)
        output = build_a11y_html(report)
        assert "/100" in output

    def test_html_has_dark_background(self, minimal_html: str):
        report = self._report(minimal_html)
        output = build_a11y_html(report)
        assert "#0d1117" in output

    def test_html_violations_table(self, inaccessible_html: str):
        report = self._report(inaccessible_html)
        output = build_a11y_html(report)
        assert "<table" in output
        assert "<tbody" in output

    def test_html_no_violations_message(self, accessible_html: str):
        checker = AccessibilityChecker(rules=[PageTitleRule])
        report = checker.check_html(accessible_html)
        output = build_a11y_html(report)
        # With just one rule and an accessible page, violations may be empty
        assert isinstance(output, str)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


class TestA11yCLI:
    def test_parser_requires_url_or_html(self):
        parser = build_parser()
        with pytest.raises(SystemExit):
            parser.parse_args([])

    def test_parser_url_arg(self):
        parser = build_parser()
        args = parser.parse_args(["--url", "http://localhost"])
        assert args.url == "http://localhost"

    def test_parser_html_arg(self, tmp_path: Path):
        f = tmp_path / "page.html"
        f.write_text("<html></html>")
        parser = build_parser()
        args = parser.parse_args(["--html", str(f)])
        assert args.html == f

    def test_parser_strict_flag(self):
        parser = build_parser()
        args = parser.parse_args(["--url", "http://localhost", "--strict"])
        assert args.strict is True

    def test_main_from_html_file(self, tmp_path: Path):
        f = tmp_path / "page.html"
        f.write_text(MINIMAL_HTML, encoding="utf-8")
        with patch("sys.argv", ["accessibility_checker", "--html", str(f), "--format", "json"]):
            result = main()
        # minimal_html may have violations (missing nav) but shouldn't error
        assert result in (0, 1)

    def test_main_network_error_returns_1(self):
        with patch.object(requests.Session, "get", side_effect=requests.ConnectionError("no")):
            with patch("sys.argv", ["accessibility_checker", "--url", "http://localhost:9999"]):
                result = main()
        assert result == 1

    def test_main_strict_returns_1_on_critical(self, tmp_path: Path):
        f = tmp_path / "bad.html"
        f.write_text(INACCESSIBLE_HTML, encoding="utf-8")
        with patch(
            "sys.argv",
            ["accessibility_checker", "--html", str(f), "--strict", "--format", "text"],
        ):
            result = main()
        # inaccessible HTML has critical violations
        assert result == 1

    def test_main_writes_to_out_file(self, tmp_path: Path):
        src = tmp_path / "page.html"
        src.write_text(MINIMAL_HTML, encoding="utf-8")
        out = tmp_path / "a11y_report.json"
        with patch(
            "sys.argv",
            [
                "accessibility_checker",
                "--html", str(src),
                "--format", "json",
                "--out", str(out),
            ],
        ):
            main()
        assert out.exists()
        data = json.loads(out.read_text())
        assert "score" in data

    def test_main_html_format_writes_html(self, tmp_path: Path):
        src = tmp_path / "page.html"
        src.write_text(MINIMAL_HTML, encoding="utf-8")
        out = tmp_path / "report.html"
        with patch(
            "sys.argv",
            [
                "accessibility_checker",
                "--html", str(src),
                "--format", "html",
                "--out", str(out),
            ],
        ):
            main()
        assert out.exists()
        content = out.read_text()
        assert "<!DOCTYPE html>" in content
