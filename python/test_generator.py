"""
test_generator.py — Automated test case generator for the test-runner-playground.

Fetches a target web page, analyzes its DOM structure (forms, buttons, links,
interactive elements), and generates test cases in two output formats:
  - Python pytest files (using requests/BeautifulSoup for assertion)
  - TypeScript Playwright spec files

Usage:
    python test_generator.py --url http://localhost:5173 --format pytest
    python test_generator.py --url http://localhost:5173 --format playwright --out generated/
    python test_generator.py --url http://localhost:5173 --format both --prefix smoke
"""

from __future__ import annotations

import argparse
import logging
import re
import sys
import textwrap
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup, Tag

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Page element models
# ---------------------------------------------------------------------------


@dataclass
class PageLink:
    href: str
    text: str
    is_internal: bool
    element_id: Optional[str] = None


@dataclass
class PageButton:
    selector: str
    text: str
    button_type: str  # button | submit | reset
    aria_label: Optional[str] = None
    element_id: Optional[str] = None


@dataclass
class FormField:
    name: str
    field_type: str      # text | email | password | number | select | textarea | checkbox
    selector: str
    label: Optional[str] = None
    placeholder: Optional[str] = None
    required: bool = False
    sample_value: str = ""


@dataclass
class PageForm:
    action: str
    method: str
    fields: list[FormField] = field(default_factory=list)
    submit_selector: str = "button[type=submit]"
    form_id: Optional[str] = None


@dataclass
class PageAnalysis:
    """Structured analysis of a web page's interactive elements."""

    url: str
    title: str
    links: list[PageLink] = field(default_factory=list)
    buttons: list[PageButton] = field(default_factory=list)
    forms: list[PageForm] = field(default_factory=list)
    headings: list[str] = field(default_factory=list)
    images_without_alt: int = 0
    nav_landmarks: int = 0
    main_landmark: bool = False

    def summary(self) -> dict[str, Any]:
        return {
            "url": self.url,
            "title": self.title,
            "links": len(self.links),
            "internal_links": sum(1 for lk in self.links if lk.is_internal),
            "buttons": len(self.buttons),
            "forms": len(self.forms),
            "headings": self.headings[:5],
            "images_without_alt": self.images_without_alt,
        }


# ---------------------------------------------------------------------------
# HTML analyzer
# ---------------------------------------------------------------------------


class PageAnalyzer:
    """Fetches and analyzes a web page, returning a PageAnalysis."""

    _SAMPLE_VALUES: dict[str, str] = {
        "text": "Test User",
        "email": "test@example.com",
        "password": "SecureP@ssw0rd",
        "number": "42",
        "tel": "555-0100",
        "search": "test query",
        "url": "https://example.com",
        "textarea": "Sample comment text for testing purposes.",
        "select": "",
        "checkbox": "true",
        "radio": "true",
    }

    def __init__(self, session: Optional[requests.Session] = None) -> None:
        self.session = session or requests.Session()
        self.session.headers.update({"User-Agent": "TestGeneratorBot/1.0"})

    def analyze(self, url: str) -> PageAnalysis:
        logger.info("Fetching %s", url)
        resp = self.session.get(url, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")
        return self._parse(url, soup)

    def analyze_html(self, html: str, url: str = "http://localhost") -> PageAnalysis:
        """Analyze raw HTML without fetching (useful for tests)."""
        soup = BeautifulSoup(html, "lxml")
        return self._parse(url, soup)

    def _parse(self, url: str, soup: BeautifulSoup) -> PageAnalysis:
        base_domain = urlparse(url).netloc

        title_tag = soup.find("title")
        title = title_tag.get_text(strip=True) if title_tag else "Untitled"

        analysis = PageAnalysis(url=url, title=title)

        # Links
        for a in soup.find_all("a", href=True):
            href = a["href"]
            abs_href = urljoin(url, href)
            is_internal = urlparse(abs_href).netloc == base_domain or href.startswith("/")
            analysis.links.append(
                PageLink(
                    href=href,
                    text=a.get_text(strip=True)[:80],
                    is_internal=is_internal,
                    element_id=a.get("id"),
                )
            )

        # Buttons
        for btn in soup.find_all("button"):
            btn_type = btn.get("type", "button")
            selector = self._build_selector(btn)
            analysis.buttons.append(
                PageButton(
                    selector=selector,
                    text=btn.get_text(strip=True)[:60],
                    button_type=btn_type,
                    aria_label=btn.get("aria-label"),
                    element_id=btn.get("id"),
                )
            )

        # Forms
        for form in soup.find_all("form"):
            analysis.forms.append(self._parse_form(form))

        # Headings
        for tag in ("h1", "h2", "h3"):
            for h in soup.find_all(tag):
                text = h.get_text(strip=True)
                if text:
                    analysis.headings.append(f"{tag}: {text[:80]}")

        # Images without alt
        analysis.images_without_alt = sum(
            1 for img in soup.find_all("img") if not img.get("alt")
        )

        # Landmarks
        analysis.nav_landmarks = len(soup.find_all("nav"))
        analysis.main_landmark = bool(soup.find("main"))

        return analysis

    def _parse_form(self, form: Tag) -> PageForm:
        pf = PageForm(
            action=form.get("action", ""),
            method=form.get("method", "get").upper(),
            form_id=form.get("id"),
        )

        inputs = form.find_all(["input", "select", "textarea"])
        for inp in inputs:
            tag_name = inp.name
            inp_type = inp.get("type", "text") if tag_name == "input" else tag_name
            if inp_type in ("hidden", "submit", "reset", "button"):
                continue

            name = inp.get("name") or inp.get("id") or f"field_{len(pf.fields)}"
            selector = self._build_selector(inp)

            # Resolve label text
            label_text: Optional[str] = None
            inp_id = inp.get("id")
            if inp_id:
                lbl = form.find("label", attrs={"for": inp_id})
                if lbl:
                    label_text = lbl.get_text(strip=True)

            sample = self._SAMPLE_VALUES.get(inp_type, "test value")

            pf.fields.append(
                FormField(
                    name=name,
                    field_type=inp_type,
                    selector=selector,
                    label=label_text,
                    placeholder=inp.get("placeholder"),
                    required=inp.has_attr("required"),
                    sample_value=sample,
                )
            )

        # Detect submit button
        submit = form.find("button", type="submit") or form.find("input", type="submit")
        if submit:
            pf.submit_selector = self._build_selector(submit)

        return pf

    def _build_selector(self, tag: Tag) -> str:
        """Generate the most specific CSS selector for an element."""
        if tag.get("id"):
            return f"#{tag['id']}"
        if tag.get("data-testid"):
            return f'[data-testid="{tag["data-testid"]}"]'
        classes = tag.get("class", [])
        if classes:
            return f"{tag.name}.{'.'.join(classes[:2])}"
        return tag.name


# ---------------------------------------------------------------------------
# Template renderer (Jinja2-style using str.format_map)
# ---------------------------------------------------------------------------

_PYTEST_FILE_TEMPLATE = '''\
"""
Auto-generated pytest test suite for {title}.
Target: {url}
Generated: {timestamp}
"""

import pytest
import requests
from bs4 import BeautifulSoup


BASE_URL = "{url}"


@pytest.fixture(scope="session")
def session():
    s = requests.Session()
    s.headers.update({{"User-Agent": "pytest-generated/1.0"}})
    return s


@pytest.fixture(scope="session")
def home_page(session):
    resp = session.get(BASE_URL)
    assert resp.status_code == 200, f"Homepage returned {{resp.status_code}}"
    return BeautifulSoup(resp.text, "lxml")


class TestPageLoad:
    """Verify the page loads and contains expected structure."""

    def test_homepage_returns_200(self, session):
        resp = session.get(BASE_URL)
        assert resp.status_code == 200

    def test_page_title(self, home_page):
        title = home_page.find("title")
        assert title is not None, "Page should have a <title> element"
        assert title.get_text(strip=True) != "", "Title should not be empty"

    def test_main_landmark_present(self, home_page):
        main = home_page.find("main")
        assert main is not None, "Page should have a <main> landmark"

{link_tests}

{button_tests}

{form_tests}
'''

_PYTEST_LINK_BLOCK = '''\
class TestLinks:
    """Verify internal navigation links are reachable."""

    @pytest.mark.parametrize("href,label", [
{link_params}
    ])
    def test_internal_link_reachable(self, session, href, label):
        url = BASE_URL.rstrip("/") + href if href.startswith("/") else href
        resp = session.get(url, allow_redirects=True)
        assert resp.status_code < 400, \\
            f"Link '{{label}}' ({{url}}) returned {{resp.status_code}}"
'''

_PYTEST_BUTTON_BLOCK = '''\
class TestButtons:
    """Verify buttons are present in the DOM."""

{button_methods}
'''

_PYTEST_FORM_BLOCK = '''\
class TestForms:
    """Verify form structure and field presence."""

{form_methods}
'''

_PW_FILE_TEMPLATE = '''\
/**
 * Auto-generated Playwright test suite for {title}
 * Target: {url}
 * Generated: {timestamp}
 */

import {{ test, expect }} from "@playwright/test";

const BASE_URL = "{url}";

test.describe("Page Load", () => {{
  test("homepage returns 200 and loads", async ({{ page }}) => {{
    const response = await page.goto(BASE_URL);
    expect(response?.status()).toBe(200);
  }});

  test("page has a title", async ({{ page }}) => {{
    await page.goto(BASE_URL);
    const title = await page.title();
    expect(title.length).toBeGreaterThan(0);
  }});

  test("main landmark is present", async ({{ page }}) => {{
    await page.goto(BASE_URL);
    await expect(page.locator("main")).toBeVisible();
  }});
}});

{link_tests}

{button_tests}

{form_tests}
'''

_PW_LINK_BLOCK = '''\
test.describe("Navigation Links", () => {{
  const links: Array<{{ href: string; label: string }}> = [
{link_entries}
  ];

  for (const {{ href, label }} of links) {{
    test(`link "${{label}}" is reachable`, async ({{ page }}) => {{
      const url = href.startsWith("/") ? BASE_URL + href : href;
      const response = await page.goto(url);
      expect(response?.status()).toBeLessThan(400);
    }});
  }}
}});
'''

_PW_BUTTON_BLOCK = '''\
test.describe("Buttons", () => {{
{button_tests}
}});
'''

_PW_FORM_BLOCK = '''\
test.describe("Forms", () => {{
{form_tests}
}});
'''


# ---------------------------------------------------------------------------
# Generator
# ---------------------------------------------------------------------------


class TestGenerator:
    """Turns a PageAnalysis into test files in the requested format(s)."""

    __test__ = False  # prevent pytest from treating this class as a test class

    def __init__(self, max_links: int = 10, max_buttons: int = 8) -> None:
        self.max_links = max_links
        self.max_buttons = max_buttons

    def generate_pytest(self, analysis: PageAnalysis) -> str:
        """Return a complete pytest file as a string."""
        ts = _timestamp()

        link_tests = self._pytest_links(analysis)
        button_tests = self._pytest_buttons(analysis)
        form_tests = self._pytest_forms(analysis)

        return _PYTEST_FILE_TEMPLATE.format(
            title=analysis.title,
            url=analysis.url,
            timestamp=ts,
            link_tests=link_tests,
            button_tests=button_tests,
            form_tests=form_tests,
        )

    def generate_playwright(self, analysis: PageAnalysis) -> str:
        """Return a complete Playwright TypeScript spec as a string."""
        ts = _timestamp()

        link_tests = self._pw_links(analysis)
        button_tests = self._pw_buttons(analysis)
        form_tests = self._pw_forms(analysis)

        return _PW_FILE_TEMPLATE.format(
            title=analysis.title,
            url=analysis.url,
            timestamp=ts,
            link_tests=link_tests,
            button_tests=button_tests,
            form_tests=form_tests,
        )

    # -- pytest helpers --

    def _pytest_links(self, analysis: PageAnalysis) -> str:
        internal = [lk for lk in analysis.links if lk.is_internal and lk.href.startswith("/")]
        sample = internal[: self.max_links]
        if not sample:
            return ""
        params = "\n".join(
            f'        ("{lk.href}", "{_escape(lk.text or lk.href)}"),' for lk in sample
        )
        return _PYTEST_LINK_BLOCK.format(link_params=params)

    def _pytest_buttons(self, analysis: PageAnalysis) -> str:
        btns = analysis.buttons[: self.max_buttons]
        if not btns:
            return ""
        methods = []
        for i, btn in enumerate(btns):
            safe_name = _safe_identifier(btn.text or f"button_{i}")
            label = _escape(btn.text or btn.selector)
            selector = _escape(btn.selector)
            methods.append(
                f'    def test_{safe_name}_button_exists(self, home_page):\n'
                f'        """Verify "{label}" button is in the DOM."""\n'
                f'        # Selector: {selector}\n'
                f'        assert home_page.find("button") is not None, '
                f'"Page should have at least one button"\n'
            )
        return _PYTEST_BUTTON_BLOCK.format(button_methods="\n".join(methods))

    def _pytest_forms(self, analysis: PageAnalysis) -> str:
        if not analysis.forms:
            return ""
        methods = []
        for fi, form in enumerate(analysis.forms):
            form_name = _safe_identifier(form.form_id or f"form_{fi}")
            methods.append(
                f'    def test_{form_name}_has_fields(self, home_page):\n'
                f'        """Verify {form_name} contains expected input fields."""\n'
                f'        form = home_page.find("form")\n'
                f'        assert form is not None, "Form should be present"\n'
                f'        inputs = form.find_all(["input", "select", "textarea"])\n'
                f'        assert len(inputs) >= {max(1, len(form.fields))}, '
                f'"Form should have at least {max(1, len(form.fields))} fields"\n'
            )
        return _PYTEST_FORM_BLOCK.format(form_methods="\n".join(methods))

    # -- playwright helpers --

    def _pw_links(self, analysis: PageAnalysis) -> str:
        internal = [lk for lk in analysis.links if lk.is_internal and lk.href.startswith("/")]
        sample = internal[: self.max_links]
        if not sample:
            return ""
        entries = "\n".join(
            f'    {{ href: "{lk.href}", label: "{_escape(lk.text or lk.href)}" }},'
            for lk in sample
        )
        return _PW_LINK_BLOCK.format(link_entries=entries)

    def _pw_buttons(self, analysis: PageAnalysis) -> str:
        btns = analysis.buttons[: self.max_buttons]
        if not btns:
            return ""
        tests = []
        for btn in btns:
            label = _escape(btn.text or btn.selector)
            selector = _escape(btn.selector)
            tests.append(
                f'  test("button \'{label}\' is visible", async ({{ page }}) => {{\n'
                f'    await page.goto(BASE_URL);\n'
                f'    await expect(page.locator("{selector}").first()).toBeVisible();\n'
                f'  }});\n'
            )
        return _PW_BUTTON_BLOCK.format(button_tests="\n".join(tests))

    def _pw_forms(self, analysis: PageAnalysis) -> str:
        if not analysis.forms:
            return ""
        tests = []
        for fi, form in enumerate(analysis.forms):
            form_label = form.form_id or f"form {fi + 1}"
            field_count = max(1, len(form.fields))
            tests.append(
                f'  test("{form_label} has {field_count} field(s)", async ({{ page }}) => {{\n'
                f'    await page.goto(BASE_URL);\n'
                f'    const form = page.locator("form").nth({fi});\n'
                f'    await expect(form).toBeVisible();\n'
                f'    const inputs = form.locator("input, select, textarea");\n'
                f'    await expect(inputs).toHaveCount({field_count});\n'
                f'  }});\n'
            )
        return _PW_FORM_BLOCK.format(form_tests="\n".join(tests))


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------


def _timestamp() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _escape(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ")


def _safe_identifier(s: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "_", s).strip("_").lower()
    return s or "element"


def _configure_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="test_generator",
        description="Generate Playwright/pytest test cases from a live web page.",
    )
    p.add_argument("--url", "-u", required=True, help="Target URL to analyze.")
    p.add_argument(
        "--format",
        choices=["pytest", "playwright", "both"],
        default="both",
        help="Output format(s).",
    )
    p.add_argument(
        "--out", "-o", type=Path, default=Path("generated"), help="Output directory."
    )
    p.add_argument("--prefix", default="generated", help="Filename prefix.")
    p.add_argument("--max-links", type=int, default=10, help="Max navigation links to include.")
    p.add_argument("--max-buttons", type=int, default=8, help="Max buttons to include.")
    p.add_argument("--verbose", "-v", action="store_true")
    return p


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    _configure_logging(args.verbose)

    analyzer = PageAnalyzer()
    try:
        analysis = analyzer.analyze(args.url)
    except requests.RequestException as exc:
        print(f"ERROR: Could not fetch {args.url}: {exc}", file=sys.stderr)
        return 1

    logger.info("Analysis summary: %s", analysis.summary())

    gen = TestGenerator(max_links=args.max_links, max_buttons=args.max_buttons)
    args.out.mkdir(parents=True, exist_ok=True)

    if args.format in ("pytest", "both"):
        content = gen.generate_pytest(analysis)
        out_path = args.out / f"{args.prefix}_test.py"
        out_path.write_text(content, encoding="utf-8")
        print(f"Generated pytest file: {out_path}")

    if args.format in ("playwright", "both"):
        content = gen.generate_playwright(analysis)
        out_path = args.out / f"{args.prefix}.spec.ts"
        out_path.write_text(content, encoding="utf-8")
        print(f"Generated Playwright file: {out_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
