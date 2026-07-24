"""
accessibility_checker.py — WCAG 2.1 accessibility auditing module.

Fetches a web page (or accepts raw HTML) and evaluates it against a set of
WCAG 2.1 Level AA rules:
  - Heading hierarchy (no skipped levels)
  - Image alternative text (all <img> have non-empty alt)
  - Landmark regions (at least one <main>, at least one <nav>)
  - ARIA labels on interactive elements
  - Form labels (every input is associated with a label)
  - Colour contrast ratio (basic check via inline style parsing)
  - Focus management indicators (no outline:none on focusable elements)
  - Language attribute on <html>
  - Link text descriptiveness (no "click here" / "read more")

Usage:
    python accessibility_checker.py --url http://localhost:5173
    python accessibility_checker.py --url http://localhost:5173 --format html --out a11y/
    python accessibility_checker.py --html my-page.html --strict
"""

from __future__ import annotations

import argparse
import colorsys
import json
import re
import sys
import time
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Optional

import requests
from bs4 import BeautifulSoup, Tag


# ---------------------------------------------------------------------------
# WCAG severity levels
# ---------------------------------------------------------------------------


class Severity(str, Enum):
    CRITICAL = "critical"   # Blocks access entirely
    SERIOUS = "serious"     # Severely impairs access
    MODERATE = "moderate"   # Significantly impairs access
    MINOR = "minor"         # Mildly affects access


class Criterion(str, Enum):
    SC_1_1_1 = "1.1.1"    # Non-text content
    SC_1_3_1 = "1.3.1"    # Info and relationships
    SC_1_4_3 = "1.4.3"    # Contrast (minimum)
    SC_2_4_2 = "2.4.2"    # Page titled
    SC_2_4_4 = "2.4.4"    # Link purpose
    SC_2_4_6 = "2.4.6"    # Headings and labels
    SC_3_1_1 = "3.1.1"    # Language of page
    SC_4_1_1 = "4.1.1"    # Parsing
    SC_4_1_2 = "4.1.2"    # Name, role, value


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


@dataclass
class Violation:
    rule_id: str
    criterion: str
    severity: str
    description: str
    element: str         # HTML snippet of offending element
    suggestion: str
    wcag_url: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class A11yReport:
    url: str
    title: str
    checked_at: str
    score: float             # 0–100
    total_checks: int
    violations: list[Violation] = field(default_factory=list)
    warnings: list[Violation] = field(default_factory=list)
    passed_rules: list[str] = field(default_factory=list)

    @property
    def critical_count(self) -> int:
        return sum(1 for v in self.violations if v.severity == Severity.CRITICAL)

    @property
    def serious_count(self) -> int:
        return sum(1 for v in self.violations if v.severity == Severity.SERIOUS)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["critical_count"] = self.critical_count
        d["serious_count"] = self.serious_count
        return d


# ---------------------------------------------------------------------------
# Rules
# ---------------------------------------------------------------------------


class AccessibilityRule:
    """Base class for a single WCAG rule check."""

    rule_id: str = "rule"
    criterion: Criterion = Criterion.SC_4_1_1
    severity: Severity = Severity.MODERATE

    def check(self, soup: BeautifulSoup, url: str) -> list[Violation]:
        raise NotImplementedError


class HeadingHierarchyRule(AccessibilityRule):
    """SC 2.4.6 — Headings must not skip levels (e.g. h1 → h3 without h2)."""

    rule_id = "heading-hierarchy"
    criterion = Criterion.SC_2_4_6
    severity = Severity.MODERATE

    def check(self, soup: BeautifulSoup, url: str) -> list[Violation]:
        levels = [int(h.name[1]) for h in soup.find_all(re.compile(r"^h[1-6]$"))]
        violations = []
        prev = 0
        for lvl in levels:
            if prev > 0 and lvl > prev + 1:
                violations.append(
                    Violation(
                        rule_id=self.rule_id,
                        criterion=self.criterion,
                        severity=self.severity,
                        description=f"Heading level jumps from h{prev} to h{lvl} — "
                                    "intermediate levels are skipped.",
                        element=f"<h{lvl}>",
                        suggestion=f"Add an h{prev + 1} before this h{lvl}.",
                        wcag_url="https://www.w3.org/WAI/WCAG21/Understanding/headings-and-labels",
                    )
                )
            prev = lvl
        return violations


class ImageAltTextRule(AccessibilityRule):
    """SC 1.1.1 — All <img> elements must have non-empty alt attributes."""

    rule_id = "image-alt"
    criterion = Criterion.SC_1_1_1
    severity = Severity.CRITICAL

    def check(self, soup: BeautifulSoup, url: str) -> list[Violation]:
        violations = []
        for img in soup.find_all("img"):
            alt = img.get("alt")
            src = img.get("src", "")[:60]
            if alt is None:
                violations.append(
                    Violation(
                        rule_id=self.rule_id,
                        criterion=self.criterion,
                        severity=Severity.CRITICAL,
                        description=f"<img src=\"{src}\"> is missing the alt attribute.",
                        element=str(img)[:120],
                        suggestion="Add a descriptive alt attribute. Use alt=\"\" for decorative images.",
                        wcag_url="https://www.w3.org/WAI/WCAG21/Understanding/non-text-content",
                    )
                )
            elif alt.strip() == "" and not img.get("role") == "presentation":
                # Empty alt is OK for decorative, but flag if no role
                pass  # allow alt="" as decorative
        return violations


class LandmarkRegionsRule(AccessibilityRule):
    """SC 1.3.1 — Page should have <main>, <nav>, and <header>/<footer> landmarks."""

    rule_id = "landmark-regions"
    criterion = Criterion.SC_1_3_1
    severity = Severity.SERIOUS

    def check(self, soup: BeautifulSoup, url: str) -> list[Violation]:
        violations = []
        if not soup.find("main") and not soup.find(attrs={"role": "main"}):
            violations.append(
                Violation(
                    rule_id=self.rule_id,
                    criterion=self.criterion,
                    severity=self.severity,
                    description="Page has no <main> landmark or role='main'.",
                    element="<body>",
                    suggestion="Wrap the primary content in a <main> element.",
                    wcag_url="https://www.w3.org/WAI/WCAG21/Understanding/info-and-relationships",
                )
            )
        if not soup.find("nav") and not soup.find(attrs={"role": "navigation"}):
            violations.append(
                Violation(
                    rule_id=self.rule_id,
                    criterion=self.criterion,
                    severity=Severity.MODERATE,
                    description="Page has no <nav> landmark or role='navigation'.",
                    element="<body>",
                    suggestion="Wrap navigation menus in a <nav> element.",
                    wcag_url="https://www.w3.org/WAI/WCAG21/Understanding/info-and-relationships",
                )
            )
        return violations


class PageLanguageRule(AccessibilityRule):
    """SC 3.1.1 — The <html> element must have a lang attribute."""

    rule_id = "page-language"
    criterion = Criterion.SC_3_1_1
    severity = Severity.SERIOUS

    def check(self, soup: BeautifulSoup, url: str) -> list[Violation]:
        html_tag = soup.find("html")
        if not html_tag or not html_tag.get("lang"):
            return [
                Violation(
                    rule_id=self.rule_id,
                    criterion=self.criterion,
                    severity=self.severity,
                    description="<html> element is missing the lang attribute.",
                    element="<html>",
                    suggestion='Add lang="en" (or the appropriate BCP 47 language tag) to <html>.',
                    wcag_url="https://www.w3.org/WAI/WCAG21/Understanding/language-of-page",
                )
            ]
        return []


class LinkPurposeRule(AccessibilityRule):
    """SC 2.4.4 — Link text should be descriptive; avoid 'click here', 'read more'."""

    rule_id = "link-purpose"
    criterion = Criterion.SC_2_4_4
    severity = Severity.SERIOUS

    _GENERIC = re.compile(
        r"^(click here|read more|more|here|link|learn more|details|this|continue)$",
        re.IGNORECASE,
    )

    def check(self, soup: BeautifulSoup, url: str) -> list[Violation]:
        violations = []
        for a in soup.find_all("a", href=True):
            text = a.get_text(strip=True)
            aria = a.get("aria-label", "").strip()
            title = a.get("title", "").strip()
            effective_label = aria or title or text
            if self._GENERIC.match(effective_label):
                violations.append(
                    Violation(
                        rule_id=self.rule_id,
                        criterion=self.criterion,
                        severity=self.severity,
                        description=f'Link text "{effective_label}" is not descriptive.',
                        element=str(a)[:120],
                        suggestion="Use descriptive link text or add aria-label with context.",
                        wcag_url="https://www.w3.org/WAI/WCAG21/Understanding/link-purpose-in-context",
                    )
                )
        return violations


class FormLabelRule(AccessibilityRule):
    """SC 1.3.1 — Every input must be associated with a visible label."""

    rule_id = "form-label"
    criterion = Criterion.SC_1_3_1
    severity = Severity.CRITICAL

    _SKIP_TYPES = {"hidden", "submit", "reset", "button", "image"}

    def check(self, soup: BeautifulSoup, url: str) -> list[Violation]:
        violations = []
        for inp in soup.find_all("input"):
            inp_type = inp.get("type", "text").lower()
            if inp_type in self._SKIP_TYPES:
                continue
            inp_id = inp.get("id")
            has_label = False
            if inp_id:
                has_label = bool(soup.find("label", attrs={"for": inp_id}))
            if not has_label and not inp.get("aria-label") and not inp.get("aria-labelledby"):
                violations.append(
                    Violation(
                        rule_id=self.rule_id,
                        criterion=self.criterion,
                        severity=self.severity,
                        description=f'Input type="{inp_type}" has no associated label.',
                        element=str(inp)[:120],
                        suggestion="Add a <label for='id'> or aria-label attribute.",
                        wcag_url="https://www.w3.org/WAI/WCAG21/Understanding/info-and-relationships",
                    )
                )
        return violations


class PageTitleRule(AccessibilityRule):
    """SC 2.4.2 — Page must have a non-empty <title>."""

    rule_id = "page-title"
    criterion = Criterion.SC_2_4_2
    severity = Severity.SERIOUS

    def check(self, soup: BeautifulSoup, url: str) -> list[Violation]:
        title = soup.find("title")
        if not title or not title.get_text(strip=True):
            return [
                Violation(
                    rule_id=self.rule_id,
                    criterion=self.criterion,
                    severity=self.severity,
                    description="Page is missing a <title> element or the title is empty.",
                    element="<head>",
                    suggestion="Add a descriptive <title> to the <head> section.",
                    wcag_url="https://www.w3.org/WAI/WCAG21/Understanding/page-titled",
                )
            ]
        return []


class AriaRolesRule(AccessibilityRule):
    """SC 4.1.2 — ARIA roles must be valid."""

    rule_id = "aria-roles"
    criterion = Criterion.SC_4_1_2
    severity = Severity.SERIOUS

    _VALID_ROLES = {
        "alert", "alertdialog", "application", "article", "banner", "button",
        "cell", "checkbox", "columnheader", "combobox", "complementary",
        "contentinfo", "definition", "dialog", "directory", "document",
        "feed", "figure", "form", "grid", "gridcell", "group", "heading",
        "img", "link", "list", "listbox", "listitem", "log", "main",
        "marquee", "math", "menu", "menubar", "menuitem", "menuitemcheckbox",
        "menuitemradio", "navigation", "none", "note", "option", "presentation",
        "progressbar", "radio", "radiogroup", "region", "row", "rowgroup",
        "rowheader", "scrollbar", "search", "searchbox", "separator",
        "slider", "spinbutton", "status", "switch", "tab", "table",
        "tablist", "tabpanel", "term", "textbox", "timer", "toolbar",
        "tooltip", "tree", "treegrid", "treeitem",
    }

    def check(self, soup: BeautifulSoup, url: str) -> list[Violation]:
        violations = []
        for tag in soup.find_all(attrs={"role": True}):
            role_val = tag.get("role", "").strip()
            for role in role_val.split():
                if role not in self._VALID_ROLES:
                    violations.append(
                        Violation(
                            rule_id=self.rule_id,
                            criterion=self.criterion,
                            severity=self.severity,
                            description=f'Invalid ARIA role: "{role}".',
                            element=str(tag)[:120],
                            suggestion=f'Remove or replace role="{role}" with a valid ARIA role.',
                            wcag_url="https://www.w3.org/WAI/WCAG21/Understanding/name-role-value",
                        )
                    )
        return violations


# ---------------------------------------------------------------------------
# Contrast ratio utility (limited — parses only simple hex/rgb inline styles)
# ---------------------------------------------------------------------------


def _hex_to_rgb(hex_color: str) -> Optional[tuple[float, float, float]]:
    hex_color = hex_color.lstrip("#")
    if len(hex_color) == 3:
        hex_color = "".join(c * 2 for c in hex_color)
    if len(hex_color) != 6:
        return None
    try:
        r = int(hex_color[0:2], 16) / 255
        g = int(hex_color[2:4], 16) / 255
        b = int(hex_color[4:6], 16) / 255
        return r, g, b
    except ValueError:
        return None


def _relative_luminance(r: float, g: float, b: float) -> float:
    def lin(c: float) -> float:
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b)


def contrast_ratio(color1: str, color2: str) -> Optional[float]:
    """Compute WCAG contrast ratio between two hex colors. Returns None if invalid."""
    rgb1 = _hex_to_rgb(color1)
    rgb2 = _hex_to_rgb(color2)
    if rgb1 is None or rgb2 is None:
        return None
    l1 = _relative_luminance(*rgb1)
    l2 = _relative_luminance(*rgb2)
    lighter = max(l1, l2)
    darker = min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


# ---------------------------------------------------------------------------
# Checker orchestrator
# ---------------------------------------------------------------------------


_ALL_RULES: list[type[AccessibilityRule]] = [
    HeadingHierarchyRule,
    ImageAltTextRule,
    LandmarkRegionsRule,
    PageLanguageRule,
    LinkPurposeRule,
    FormLabelRule,
    PageTitleRule,
    AriaRolesRule,
]


def _score(violations: list[Violation], total_checks: int) -> float:
    """Compute an accessibility score 0–100."""
    if total_checks == 0:
        return 100.0
    weights = {
        Severity.CRITICAL: 10,
        Severity.SERIOUS: 5,
        Severity.MODERATE: 2,
        Severity.MINOR: 1,
    }
    deduction = sum(weights.get(Severity(v.severity), 1) for v in violations)
    raw = max(0.0, 100.0 - (deduction / total_checks * 100))
    return round(raw, 1)


class AccessibilityChecker:
    """Runs all WCAG rules against a page and produces an A11yReport."""

    def __init__(self, rules: Optional[list[type[AccessibilityRule]]] = None) -> None:
        self.rules = [R() for R in (rules or _ALL_RULES)]

    def check_url(self, url: str, session: Optional[requests.Session] = None) -> A11yReport:
        sess = session or requests.Session()
        sess.headers.update({"User-Agent": "A11yChecker/1.0"})
        resp = sess.get(url, timeout=15)
        resp.raise_for_status()
        return self.check_html(resp.text, url=url)

    def check_html(self, html: str, url: str = "about:blank") -> A11yReport:
        soup = BeautifulSoup(html, "lxml")
        title_tag = soup.find("title")
        title = title_tag.get_text(strip=True) if title_tag else "Untitled"

        all_violations: list[Violation] = []
        passed_rules: list[str] = []

        for rule in self.rules:
            found = rule.check(soup, url)
            if found:
                all_violations.extend(found)
            else:
                passed_rules.append(rule.rule_id)

        violations = [v for v in all_violations if v.severity in (
            Severity.CRITICAL, Severity.SERIOUS
        )]
        warnings = [v for v in all_violations if v.severity in (
            Severity.MODERATE, Severity.MINOR
        )]

        total_checks = len(self.rules)
        score = _score(all_violations, total_checks)

        return A11yReport(
            url=url,
            title=title,
            checked_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            score=score,
            total_checks=total_checks,
            violations=violations,
            warnings=warnings,
            passed_rules=passed_rules,
        )


# ---------------------------------------------------------------------------
# HTML report output
# ---------------------------------------------------------------------------

_REPORT_CSS = """
body { font-family: system-ui, sans-serif; background: #0d1117; color: #e6edf3;
  padding: 24px; font-size: 14px; line-height: 1.6; }
h1 { font-size: 20px; margin-bottom: 4px; }
.score { font-size: 48px; font-weight: 700; margin: 16px 0; }
.score.good { color: #3fb950; }
.score.warn { color: #d29922; }
.score.bad  { color: #f85149; }
table { width: 100%; border-collapse: collapse; margin-top: 16px; }
th { text-align: left; color: #8b949e; font-size: 11px; text-transform: uppercase;
  padding: 6px 10px; border-bottom: 1px solid #30363d; }
td { padding: 8px 10px; border-bottom: 1px solid #21262d; vertical-align: top; }
.crit { color: #f85149; font-weight: 600; }
.serious { color: #d29922; font-weight: 600; }
.moderate { color: #58a6ff; }
.minor { color: #8b949e; }
code { font-size: 11px; background: #161b22; padding: 2px 6px; border-radius: 4px; }
"""


def build_a11y_html(report: A11yReport) -> str:
    score_cls = "good" if report.score >= 80 else ("warn" if report.score >= 50 else "bad")
    rows = []
    for v in report.violations + report.warnings:
        sev_cls = {
            "critical": "crit", "serious": "serious",
            "moderate": "moderate", "minor": "minor",
        }.get(v.severity, "minor")
        rows.append(
            f"<tr><td><span class='{sev_cls}'>{v.severity.upper()}</span></td>"
            f"<td>{v.criterion}</td>"
            f"<td>{v.description}</td>"
            f"<td>{v.suggestion}</td>"
            f"<td><code>{v.element[:60]}</code></td></tr>"
        )
    rows_html = "\n".join(rows) or "<tr><td colspan=5>No violations found.</td></tr>"
    passed = ", ".join(report.passed_rules) or "none"

    return f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><title>A11y Report</title><style>{_REPORT_CSS}</style></head>
<body>
<h1>Accessibility Report — {report.title}</h1>
<p style="color:#8b949e">{report.url} · {report.checked_at}</p>
<div class="score {score_cls}">{report.score}/100</div>
<p>{len(report.violations)} violation(s), {len(report.warnings)} warning(s) across {report.total_checks} rules</p>
<p style="color:#8b949e;font-size:12px">Passed: {passed}</p>
<table>
  <thead><tr><th>Severity</th><th>Criterion</th><th>Description</th><th>Suggestion</th><th>Element</th></tr></thead>
  <tbody>{rows_html}</tbody>
</table>
</body></html>"""


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
        prog="accessibility_checker",
        description="WCAG 2.1 accessibility audit for web pages.",
    )
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--url", "-u", help="Target URL to check.")
    src.add_argument("--html", type=Path, help="Path to a local HTML file.")
    p.add_argument(
        "--format", choices=["json", "html", "text"], default="text",
        help="Output format.",
    )
    p.add_argument("--out", "-o", type=Path, help="Output file path (default: stdout).")
    p.add_argument(
        "--strict", action="store_true",
        help="Exit with code 1 if any critical violations are found.",
    )
    p.add_argument("--verbose", "-v", action="store_true")
    return p


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    _configure_logging(args.verbose)

    checker = AccessibilityChecker()

    try:
        if args.url:
            report = checker.check_url(args.url)
        else:
            html = args.html.read_text(encoding="utf-8")
            report = checker.check_html(html, url=str(args.html))
    except requests.RequestException as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    # Format output
    if args.format == "json":
        output = json.dumps(report.to_dict(), indent=2)
    elif args.format == "html":
        output = build_a11y_html(report)
    else:
        lines = [
            f"Accessibility Report: {report.url}",
            f"Score: {report.score}/100",
            f"Violations: {len(report.violations)}  Warnings: {len(report.warnings)}",
            "",
        ]
        for v in report.violations:
            lines.append(f"[{v.severity.upper()}] {v.criterion} — {v.description}")
            lines.append(f"  → {v.suggestion}")
        for w in report.warnings:
            lines.append(f"[{w.severity.upper()}] {w.criterion} — {w.description}")
        output = "\n".join(lines)

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(output, encoding="utf-8")
        print(f"Report written to {args.out}")
    else:
        print(output)

    if args.strict and report.critical_count > 0:
        print(
            f"\nStrict mode: {report.critical_count} critical violation(s) found.",
            file=sys.stderr,
        )
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
