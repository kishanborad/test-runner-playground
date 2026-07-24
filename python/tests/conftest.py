"""
conftest.py — Shared pytest fixtures for the test-runner-playground Python test suite.

Provides:
  - Sample HTML pages (minimal, full, form-heavy, accessible, inaccessible)
  - Mock test case and step objects
  - Pre-built RunReport / StepResult instances
  - Fake HTTP responses via requests-mock
  - Temp directory helpers
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

import pytest


# ---------------------------------------------------------------------------
# HTML fixtures
# ---------------------------------------------------------------------------

MINIMAL_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><title>Minimal Page</title></head>
<body>
  <main>
    <h1>Hello World</h1>
    <p>A minimal test page.</p>
  </main>
</body>
</html>
"""

FULL_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>E-Commerce Shop | Test Runner Playground</title>
</head>
<body>
  <header>
    <nav aria-label="Main navigation">
      <a href="/">Home</a>
      <a href="/products">Products</a>
      <a href="/cart">Cart</a>
    </nav>
  </header>
  <main>
    <h1>Featured Products</h1>
    <h2>Electronics</h2>
    <section class="product-grid">
      <article class="product-card" data-testid="product-1">
        <img src="/img/laptop.jpg" alt="Laptop Pro 15">
        <h3>Laptop Pro 15</h3>
        <p class="price">$1,299.00</p>
        <button type="button" id="add-to-cart-1" data-product-id="1">Add to Cart</button>
      </article>
      <article class="product-card" data-testid="product-2">
        <img src="/img/phone.jpg" alt="Smartphone X">
        <h3>Smartphone X</h3>
        <p class="price">$799.00</p>
        <button type="button" id="add-to-cart-2" data-product-id="2">Add to Cart</button>
      </article>
    </section>
    <div class="cart-summary">
      <span class="cart-count">0</span> items in cart
    </div>
  </main>
  <footer>
    <p>&copy; 2026 Test Runner Playground</p>
  </footer>
</body>
</html>
"""

FORM_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><title>Checkout</title></head>
<body>
  <main>
    <h1>Checkout</h1>
    <form id="checkout-form" action="/checkout" method="post">
      <div class="field-group">
        <label for="first-name">First Name</label>
        <input type="text" id="first-name" name="firstName" required placeholder="Jane">
      </div>
      <div class="field-group">
        <label for="last-name">Last Name</label>
        <input type="text" id="last-name" name="lastName" required placeholder="Doe">
      </div>
      <div class="field-group">
        <label for="email">Email Address</label>
        <input type="email" id="email" name="email" required placeholder="jane@example.com">
      </div>
      <div class="field-group">
        <label for="card-number">Card Number</label>
        <input type="text" id="card-number" name="cardNumber" required placeholder="4111 1111 1111 1111">
      </div>
      <div class="field-group">
        <label for="expiry">Expiry Date</label>
        <input type="text" id="expiry" name="expiry" required placeholder="MM/YY">
      </div>
      <button type="submit" id="place-order">Place Order</button>
    </form>
  </main>
</body>
</html>
"""

INACCESSIBLE_HTML = """\
<!DOCTYPE html>
<html>
<head></head>
<body>
  <div>
    <h1>Big Heading</h1>
    <h4>Skipped to h4</h4>
    <img src="logo.png">
    <img src="banner.jpg">
    <a href="/contact">click here</a>
    <a href="/more">read more</a>
    <input type="text" name="search" placeholder="Search...">
    <div role="badrolename">Content</div>
    <button>OK</button>
  </div>
</body>
</html>
"""

ACCESSIBLE_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><title>Accessible Page</title></head>
<body>
  <header><nav aria-label="Site navigation"><a href="/">Go to homepage</a></nav></header>
  <main>
    <h1>Page Title</h1>
    <h2>Section One</h2>
    <img src="product.jpg" alt="Blue running shoes, size 10">
    <a href="/products/shoes">View all running shoes</a>
    <form id="search-form">
      <label for="search-input">Search products</label>
      <input type="text" id="search-input" name="q" placeholder="Search...">
      <button type="submit">Search</button>
    </form>
  </main>
</body>
</html>
"""


@pytest.fixture
def minimal_html() -> str:
    return MINIMAL_HTML


@pytest.fixture
def full_html() -> str:
    return FULL_HTML


@pytest.fixture
def form_html() -> str:
    return FORM_HTML


@pytest.fixture
def inaccessible_html() -> str:
    return INACCESSIBLE_HTML


@pytest.fixture
def accessible_html() -> str:
    return ACCESSIBLE_HTML


# ---------------------------------------------------------------------------
# Mock test results (matching test_runner.py output format)
# ---------------------------------------------------------------------------

def _make_step_result(
    index: int,
    action: str = "navigate",
    target: str = "/",
    passed: bool = True,
    duration_ms: float = 45.0,
    error: str | None = None,
) -> dict[str, Any]:
    return {
        "step_index": index,
        "action": action,
        "target": target,
        "passed": passed,
        "duration_ms": duration_ms,
        "error": error,
        "screenshot_path": None,
        "actual_value": f"HTTP 200" if passed else None,
    }


def _make_test_result(
    test_name: str = "Test Homepage",
    passed: bool = True,
    duration_ms: float = 120.0,
    step_count: int = 3,
    run_id: str | None = None,
    error: str | None = None,
) -> dict[str, Any]:
    rid = run_id or str(uuid.uuid4())[:8]
    return {
        "run_id": rid,
        "test_id": str(uuid.uuid4()),
        "test_name": test_name,
        "passed": passed,
        "duration_ms": duration_ms,
        "start_time": "2026-07-23T10:00:00.000Z",
        "end_time": "2026-07-23T10:00:00.120Z",
        "step_results": [
            _make_step_result(i, passed=passed if i == step_count - 1 else True)
            for i in range(step_count)
        ],
        "error": error if not passed else None,
        "worker_id": 0,
    }


def make_run_report(
    total: int = 4,
    passed: int | None = None,
    suite_name: str = "smoke",
    run_id: str | None = None,
) -> dict[str, Any]:
    """Build a minimal run report dict compatible with test_runner.py output."""
    if passed is None:
        passed = total
    failed = total - passed
    rid = run_id or str(uuid.uuid4())[:8]
    results = []
    for i in range(total):
        ok = i < passed
        results.append(
            _make_test_result(
                test_name=f"Test Case {i + 1}",
                passed=ok,
                run_id=rid,
                error="Element not found" if not ok else None,
            )
        )
    total_dur = sum(r["duration_ms"] for r in results)
    return {
        "run_id": rid,
        "suite_name": suite_name,
        "target_url": "http://localhost:5173",
        "started_at": "2026-07-23T10:00:00.000Z",
        "finished_at": "2026-07-23T10:00:01.500Z",
        "total": total,
        "passed": passed,
        "failed": failed,
        "duration_ms": total_dur,
        "pass_rate": round(passed / total * 100, 2) if total > 0 else 0.0,
        "results": results,
    }


@pytest.fixture
def sample_run_report() -> dict[str, Any]:
    """A 4/4 passing run report dict."""
    return make_run_report(total=4, passed=4)


@pytest.fixture
def partial_run_report() -> dict[str, Any]:
    """A 3/4 passing run report dict."""
    return make_run_report(total=4, passed=3)


@pytest.fixture
def failing_run_report() -> dict[str, Any]:
    """A 0/4 passing run report dict."""
    return make_run_report(total=4, passed=0)


@pytest.fixture
def run_report_file(tmp_path: Path, sample_run_report: dict[str, Any]) -> Path:
    """Write a sample run report to a temp file and return its path."""
    rid = sample_run_report["run_id"]
    out = tmp_path / f"run_{rid}.json"
    out.write_text(json.dumps(sample_run_report), encoding="utf-8")
    return out


@pytest.fixture
def run_reports_dir(tmp_path: Path) -> Path:
    """Create a directory with 3 run report files for trend testing."""
    reports_dir = tmp_path / "results"
    reports_dir.mkdir()
    for i, (total, passed) in enumerate([(4, 4), (4, 3), (4, 4)]):
        report = make_run_report(total=total, passed=passed, suite_name="smoke")
        rid = report["run_id"]
        out = reports_dir / f"run_{rid}.json"
        out.write_text(json.dumps(report), encoding="utf-8")
    return reports_dir


# ---------------------------------------------------------------------------
# DSL test file fixtures
# ---------------------------------------------------------------------------

SAMPLE_DSL_CONTENT = """\
[Homepage Loads]
description: Verify the homepage returns 200 and shows expected content
tags: smoke, homepage
navigate | /
assert | Welcome | Test Runner Playground
screenshot | homepage

---

[Product List Visible]
description: Product cards appear on the homepage
tags: smoke, products
navigate | /
assert | Laptop Pro
assert | Smartphone X
assert | Add to Cart

---

[Cart Count Updates]
description: Adding a product increments the cart counter
tags: cart
navigate | /
click | #add-to-cart-1
assert | .cart-count | 1

---

[Checkout Form Submits]
description: The checkout form accepts valid input
tags: checkout
navigate | /checkout
type | #first-name | Jane
type | #last-name | Doe
type | #email | jane@example.com
type | #card-number | 4111111111111111
type | #expiry | 12/28
click | #place-order
assert | Order Confirmed
"""


@pytest.fixture
def dsl_test_file(tmp_path: Path) -> Path:
    """Write the sample DSL test content to a temp file."""
    f = tmp_path / "smoke.tests"
    f.write_text(SAMPLE_DSL_CONTENT, encoding="utf-8")
    return f


@pytest.fixture
def empty_dsl_file(tmp_path: Path) -> Path:
    """An empty test file."""
    f = tmp_path / "empty.tests"
    f.write_text("# Just a comment\n", encoding="utf-8")
    return f


# ---------------------------------------------------------------------------
# Performance metric fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_perf_metrics() -> dict[str, Any]:
    """A minimal aggregated metrics dict."""
    return {
        "url": "http://localhost:5173",
        "run_count": 3,
        "timing_mean_ms": 320.0,
        "timing_stdev_ms": 15.0,
        "timing_min_ms": 305.0,
        "timing_max_ms": 340.0,
        "timing_p95_ms": 338.0,
        "size_mean_bytes": 12288,
        "transfer_rate_mean_kbps": 450.0,
        "measured_at": "2026-07-23T10:00:00.000Z",
        "individual_runs": [],
    }
