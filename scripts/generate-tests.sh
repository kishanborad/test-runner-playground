#!/usr/bin/env bash
# scripts/generate-tests.sh — Generate test cases from a target URL
#
# Fetches a live web page, analyzes its DOM, and generates:
#   - Python pytest file (generated/<prefix>_test.py)
#   - TypeScript Playwright spec (generated/<prefix>.spec.ts)
#
# The generator detects forms, buttons, links, and images, then outputs
# tests for common interaction patterns and accessibility-aware assertions.
#
# Usage:
#   ./scripts/generate-tests.sh
#   ./scripts/generate-tests.sh --url http://localhost:5173/checkout
#   ./scripts/generate-tests.sh --url http://localhost:5173 --format pytest
#   ./scripts/generate-tests.sh --url http://localhost:5173 --prefix smoke --out tests/generated
#   ./scripts/generate-tests.sh --url http://localhost:5173 --max-links 5 --max-buttons 6
#   ./scripts/generate-tests.sh --all-pages  (auto-discover pages from sitemap/links)

set -euo pipefail

# ─── colours ──────────────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
CYAN='\033[0;36m'
RESET='\033[0m'

info()    { echo -e "${BLUE}[gen]${RESET} $*"; }
success() { echo -e "${GREEN}[gen] ✓${RESET} $*"; }
warn()    { echo -e "${YELLOW}[gen] ⚠${RESET} $*"; }
error()   { echo -e "${RED}[gen] ✗${RESET} $*" >&2; }
section() { echo -e "\n${CYAN}${BOLD}── $* ──────────────────────────────────${RESET}"; }

# ─── argument parsing ─────────────────────────────────────────────────────────
TARGET_URL="http://localhost:5173"
FORMAT="both"
OUTPUT_DIR="generated"
PREFIX="generated"
MAX_LINKS=10
MAX_BUTTONS=8
ALL_PAGES=false
VERBOSE=false
OPEN_FILES=false

for arg in "$@"; do
  case "$arg" in
    --url=*)         TARGET_URL="${arg#--url=}" ;;
    --format=*)      FORMAT="${arg#--format=}" ;;
    --out=*)         OUTPUT_DIR="${arg#--out=}" ;;
    --prefix=*)      PREFIX="${arg#--prefix=}" ;;
    --max-links=*)   MAX_LINKS="${arg#--max-links=}" ;;
    --max-buttons=*) MAX_BUTTONS="${arg#--max-buttons=}" ;;
    --all-pages)     ALL_PAGES=true ;;
    --open)          OPEN_FILES=true ;;
    --verbose|-v)    VERBOSE=true ;;
    --help|-h)
      cat << 'HELP'
Usage: ./scripts/generate-tests.sh [options]

Options:
  --url=URL           Target URL to analyze (default: http://localhost:5173)
  --format=FORMAT     Output format: pytest|playwright|both (default: both)
  --out=DIR           Output directory (default: generated/)
  --prefix=NAME       Filename prefix (default: generated)
  --max-links=NUM     Max links to generate tests for (default: 10)
  --max-buttons=NUM   Max buttons to generate tests for (default: 8)
  --all-pages         Discover and generate tests for all internal pages
  --open              Open generated files after creation (macOS: open)
  --verbose, -v       Verbose output
  --help              Show this message

Examples:
  # Generate tests for the homepage
  ./scripts/generate-tests.sh

  # Generate tests for the checkout page, pytest only
  ./scripts/generate-tests.sh --url http://localhost:5173/checkout --format pytest --prefix checkout

  # Generate Playwright tests for all pages
  ./scripts/generate-tests.sh --format playwright --all-pages
HELP
      exit 0
      ;;
    *)
      error "Unknown argument: $arg"
      exit 1
      ;;
  esac
done

# ─── validate format ──────────────────────────────────────────────────────────
if [[ "$FORMAT" != "pytest" && "$FORMAT" != "playwright" && "$FORMAT" != "both" ]]; then
  error "Invalid format: $FORMAT. Choose pytest, playwright, or both."
  exit 1
fi

# ─── project root ─────────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

# ─── locate Python ────────────────────────────────────────────────────────────
PYTHON_CMD=""
for candidate in python3 python; do
  if command -v "$candidate" &>/dev/null; then
    PY_MAJOR=$("$candidate" -c "import sys; print(sys.version_info.major)" 2>/dev/null || echo "0")
    if [[ "$PY_MAJOR" == "3" ]]; then
      PYTHON_CMD="$candidate"
      break
    fi
  fi
done

if [[ -z "$PYTHON_CMD" ]]; then
  error "Python 3 not found. Run ./scripts/setup.sh first."
  exit 1
fi

# Use venv if available
if [[ -d "$PROJECT_ROOT/.venv" ]]; then
  # shellcheck source=/dev/null
  source "$PROJECT_ROOT/.venv/bin/activate"
  [[ "$VERBOSE" == "true" ]] && info "Using .venv ($("$PYTHON_CMD" --version))"
fi

# Check required packages
for pkg in bs4 requests lxml; do
  if ! "$PYTHON_CMD" -c "import $pkg" &>/dev/null; then
    error "Missing Python package: $pkg"
    error "Run: pip install -r python/requirements.txt"
    exit 1
  fi
done

# ─── check server is reachable ───────────────────────────────────────────────
section "Checking target"
info "URL: $TARGET_URL"

if ! curl -sf --max-time 5 "$TARGET_URL" > /dev/null 2>&1; then
  warn "Cannot reach $TARGET_URL directly."
  warn "If the dev server is not running, start it first:"
  warn "  npm run dev  (in another terminal)"
  warn ""
  warn "Continuing anyway — generator will show the error..."
fi

# ─── generate tests ───────────────────────────────────────────────────────────
section "Generating test cases"

mkdir -p "$OUTPUT_DIR"

GENERATOR_ARGS=(
  "--url"         "$TARGET_URL"
  "--format"      "$FORMAT"
  "--out"         "$OUTPUT_DIR"
  "--prefix"      "$PREFIX"
  "--max-links"   "$MAX_LINKS"
  "--max-buttons" "$MAX_BUTTONS"
)
[[ "$VERBOSE" == "true" ]] && GENERATOR_ARGS+=("--verbose")

info "Running: $PYTHON_CMD python/test_generator.py ${GENERATOR_ARGS[*]}"

if "$PYTHON_CMD" python/test_generator.py "${GENERATOR_ARGS[@]}"; then
  success "Test generation complete"
else
  error "Test generation failed"
  exit 1
fi

# ─── multi-page generation ───────────────────────────────────────────────────
if [[ "$ALL_PAGES" == "true" ]]; then
  section "Discovering additional pages"

  # Extract internal links from the homepage
  DISCOVERED_PAGES=$("$PYTHON_CMD" - <<PYEOF
import sys, json
sys.path.insert(0, "python")
try:
    import requests
    from bs4 import BeautifulSoup
    from urllib.parse import urlparse, urljoin

    base = "$TARGET_URL"
    resp = requests.get(base, timeout=10)
    soup = BeautifulSoup(resp.text, "lxml")
    base_domain = urlparse(base).netloc

    seen = set()
    for a in soup.find_all("a", href=True):
        href = a["href"]
        abs_href = urljoin(base, href)
        parsed = urlparse(abs_href)
        if parsed.netloc == base_domain and href.startswith("/") and href not in seen:
            seen.add(href)
    print(json.dumps(sorted(seen)))
except Exception as e:
    print("[]", file=sys.stderr)
    sys.exit(0)
PYEOF
  )

  PAGE_COUNT=$(echo "$DISCOVERED_PAGES" | "$PYTHON_CMD" -c "import sys,json; print(len(json.loads(sys.stdin.read())))")
  info "Discovered $PAGE_COUNT internal page(s)"

  if [[ "$PAGE_COUNT" -gt 0 ]]; then
    echo "$DISCOVERED_PAGES" | "$PYTHON_CMD" - <<PYEOF
import sys, json, subprocess

pages = json.loads(sys.stdin.read())
base_url = "$TARGET_URL"
output_dir = "$OUTPUT_DIR"
format_arg = "$FORMAT"

for i, path in enumerate(pages[:5]):  # Limit to 5 pages
    page_url = base_url.rstrip("/") + path
    slug = path.strip("/").replace("/", "-") or "home"
    prefix = f"page_{i+1}_{slug}"[:40]
    print(f"  Generating tests for: {page_url} (prefix: {prefix})")
    try:
        result = subprocess.run(
            [
                sys.executable, "python/test_generator.py",
                "--url",    page_url,
                "--format", format_arg,
                "--out",    output_dir,
                "--prefix", prefix,
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            print(f"    ✓ {prefix}")
        else:
            print(f"    ⚠ {prefix}: {result.stderr.strip()[:80]}")
    except subprocess.TimeoutExpired:
        print(f"    ⚠ {prefix}: timed out")
PYEOF
    success "Multi-page generation complete"
  fi
fi

# ─── list generated files ─────────────────────────────────────────────────────
section "Generated files"

if ls "$OUTPUT_DIR"/*.py "$OUTPUT_DIR"/*.ts "$OUTPUT_DIR"/*.spec.ts 2>/dev/null | head -20; then
  :
else
  warn "No files found in $OUTPUT_DIR"
fi

TOTAL_FILES=$(find "$OUTPUT_DIR" -maxdepth 1 \( -name "*.py" -o -name "*.ts" \) 2>/dev/null | wc -l | tr -d ' ')
TOTAL_BYTES=$(du -sh "$OUTPUT_DIR" 2>/dev/null | cut -f1)
info "Total: $TOTAL_FILES file(s) in $OUTPUT_DIR/ ($TOTAL_BYTES)"

# ─── open generated files ─────────────────────────────────────────────────────
if [[ "$OPEN_FILES" == "true" ]]; then
  if command -v open &>/dev/null; then
    open "$OUTPUT_DIR"
  elif command -v xdg-open &>/dev/null; then
    xdg-open "$OUTPUT_DIR"
  else
    warn "--open: No suitable file opener found (tried open, xdg-open)"
  fi
fi

# ─── next steps ───────────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}Next steps:${RESET}"
echo ""

if [[ "$FORMAT" == "pytest" || "$FORMAT" == "both" ]]; then
  echo -e "  ${GREEN}# Run generated pytest suite${RESET}"
  echo -e "  cd python && python -m pytest ../$OUTPUT_DIR/${PREFIX}_test.py -v"
  echo ""
fi

if [[ "$FORMAT" == "playwright" || "$FORMAT" == "both" ]]; then
  echo -e "  ${GREEN}# Run generated Playwright spec (requires Playwright installation)${RESET}"
  echo -e "  npx playwright test $OUTPUT_DIR/${PREFIX}.spec.ts"
  echo ""
fi

echo -e "  ${CYAN}Generated files are in: $OUTPUT_DIR/${RESET}"
echo ""
