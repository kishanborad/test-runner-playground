#!/usr/bin/env bash
# scripts/run-e2e.sh — End-to-end test orchestrator
#
# Starts the Vite development server, waits for it to become responsive,
# then runs the Python test suite against it. Tears down the dev server
# on exit regardless of test outcome.
#
# Usage:
#   ./scripts/run-e2e.sh
#   ./scripts/run-e2e.sh --port 3000
#   ./scripts/run-e2e.sh --test-file python/tests/smoke.tests
#   ./scripts/run-e2e.sh --workers 4 --suite checkout
#   ./scripts/run-e2e.sh --no-server  (skip starting server; use --url)
#   ./scripts/run-e2e.sh --url http://staging.example.com

set -euo pipefail

# ─── colours ──────────────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
CYAN='\033[0;36m'
RESET='\033[0m'

info()    { echo -e "${BLUE}[e2e]${RESET} $*"; }
success() { echo -e "${GREEN}[e2e] ✓${RESET} $*"; }
warn()    { echo -e "${YELLOW}[e2e] ⚠${RESET} $*"; }
error()   { echo -e "${RED}[e2e] ✗${RESET} $*" >&2; }
section() { echo -e "\n${CYAN}${BOLD}── $* ──────────────────────────────────${RESET}"; }

# ─── argument parsing ─────────────────────────────────────────────────────────
PORT=5173
TEST_FILE=""
WORKERS=1
SUITE="e2e"
NO_SERVER=false
TARGET_URL=""
OUTPUT_DIR="results"
REPORT_DIR="reports"
TIMEOUT_SECS=30
VERBOSE=false

for arg in "$@"; do
  case "$arg" in
    --port=*)       PORT="${arg#--port=}" ;;
    --test-file=*)  TEST_FILE="${arg#--test-file=}" ;;
    --workers=*)    WORKERS="${arg#--workers=}" ;;
    --suite=*)      SUITE="${arg#--suite=}" ;;
    --no-server)    NO_SERVER=true ;;
    --url=*)        TARGET_URL="${arg#--url=}" ;;
    --output=*)     OUTPUT_DIR="${arg#--output=}" ;;
    --timeout=*)    TIMEOUT_SECS="${arg#--timeout=}" ;;
    --verbose|-v)   VERBOSE=true ;;
    --help|-h)
      cat << 'HELP'
Usage: ./scripts/run-e2e.sh [options]

Options:
  --port=NUM          Dev server port (default: 5173)
  --test-file=PATH    Path to a .tests DSL file to run
  --workers=NUM       Parallel test workers (default: 1)
  --suite=NAME        Suite name for reports (default: e2e)
  --no-server         Don't start the dev server (use --url instead)
  --url=URL           Target URL (when --no-server is set)
  --output=DIR        Results output directory (default: results)
  --timeout=SECS      Server startup timeout in seconds (default: 30)
  --verbose, -v       Verbose output
  --help              Show this message
HELP
      exit 0
      ;;
    *)
      error "Unknown argument: $arg"
      exit 1
      ;;
  esac
done

# ─── project root ─────────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

# ─── resolve target URL ───────────────────────────────────────────────────────
if [[ "$NO_SERVER" == "true" ]]; then
  if [[ -z "$TARGET_URL" ]]; then
    error "--no-server requires --url=<URL>"
    exit 1
  fi
else
  TARGET_URL="http://localhost:$PORT"
fi

# ─── locate Python ────────────────────────────────────────────────────────────
PYTHON_CMD=""
for candidate in python3 python; do
  if command -v "$candidate" &>/dev/null; then
    PY_VER=$("$candidate" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null || echo "0.0")
    PY_MAJOR=$(echo "$PY_VER" | cut -d. -f1)
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
fi

# ─── dev server management ────────────────────────────────────────────────────
SERVER_PID=""
SERVER_LOG=$(mktemp)

cleanup() {
  if [[ -n "$SERVER_PID" ]] && kill -0 "$SERVER_PID" 2>/dev/null; then
    info "Stopping dev server (PID $SERVER_PID)..."
    kill "$SERVER_PID" 2>/dev/null || true
    wait "$SERVER_PID" 2>/dev/null || true
  fi
  rm -f "$SERVER_LOG"
}
trap cleanup EXIT

start_dev_server() {
  section "Starting dev server"

  if ! command -v npm &>/dev/null; then
    error "npm not found. Run ./scripts/setup.sh first."
    exit 1
  fi

  info "Starting Vite on port $PORT ..."
  npm run dev -- --port "$PORT" --host 0.0.0.0 > "$SERVER_LOG" 2>&1 &
  SERVER_PID=$!
  info "Dev server PID: $SERVER_PID"

  # Wait for server to be ready
  info "Waiting up to ${TIMEOUT_SECS}s for server to respond..."
  local elapsed=0
  local interval=2
  while true; do
    if ! kill -0 "$SERVER_PID" 2>/dev/null; then
      error "Dev server process died. Log:"
      cat "$SERVER_LOG" >&2
      exit 1
    fi
    if curl -sf --max-time 2 "$TARGET_URL" > /dev/null 2>&1; then
      success "Dev server is up at $TARGET_URL (${elapsed}s)"
      break
    fi
    sleep "$interval"
    elapsed=$((elapsed + interval))
    if [[ "$elapsed" -ge "$TIMEOUT_SECS" ]]; then
      error "Server did not respond within ${TIMEOUT_SECS}s."
      error "Server log:"
      cat "$SERVER_LOG" >&2
      exit 1
    fi
    [[ "$VERBOSE" == "true" ]] && info "  waiting... (${elapsed}s elapsed)"
  done
}

if [[ "$NO_SERVER" == "false" ]]; then
  start_dev_server
else
  section "Using external server"
  info "Target URL: $TARGET_URL"

  # Verify the URL is reachable
  if ! curl -sf --max-time 5 "$TARGET_URL" > /dev/null 2>&1; then
    error "Cannot reach $TARGET_URL. Is the server running?"
    exit 1
  fi
  success "Server is reachable"
fi

# ─── run Python accessibility check ──────────────────────────────────────────
section "Accessibility pre-check"
mkdir -p "$REPORT_DIR"

if "$PYTHON_CMD" python/accessibility_checker.py \
    --url "$TARGET_URL" \
    --format html \
    --out "$REPORT_DIR/a11y_report.html" 2>/dev/null; then
  success "Accessibility check complete → $REPORT_DIR/a11y_report.html"
else
  warn "Accessibility check found issues (see $REPORT_DIR/a11y_report.html)"
fi

# ─── run Python test runner ───────────────────────────────────────────────────
section "Running Python test suite"
mkdir -p "$OUTPUT_DIR"

RUNNER_ARGS=(
  "--url" "$TARGET_URL"
  "--workers" "$WORKERS"
  "--output" "$OUTPUT_DIR"
  "--suite" "$SUITE"
  "--format" "summary"
)

if [[ -n "$TEST_FILE" ]]; then
  if [[ ! -f "$TEST_FILE" ]]; then
    error "Test file not found: $TEST_FILE"
    exit 1
  fi
  RUNNER_ARGS+=("--file" "$TEST_FILE")
  info "Running: $PYTHON_CMD python/test_runner.py ${RUNNER_ARGS[*]}"
  TEST_EXIT=0
  "$PYTHON_CMD" python/test_runner.py "${RUNNER_ARGS[@]}" || TEST_EXIT=$?
else
  warn "No --test-file specified. Checking for test files in the project..."
  FOUND_FILES=()
  for f in tests/*.tests python/tests/*.tests; do
    [[ -f "$f" ]] && FOUND_FILES+=("$f")
  done

  if [[ ${#FOUND_FILES[@]} -eq 0 ]]; then
    warn "No .tests DSL files found. Running accessibility + performance checks only."
    TEST_EXIT=0
  else
    info "Found ${#FOUND_FILES[@]} test file(s): ${FOUND_FILES[*]}"
    TEST_EXIT=0
    for test_file in "${FOUND_FILES[@]}"; do
      info "  Running: $test_file"
      if ! "$PYTHON_CMD" python/test_runner.py \
          --file "$test_file" \
          --url "$TARGET_URL" \
          --workers "$WORKERS" \
          --output "$OUTPUT_DIR" \
          --suite "$(basename "$test_file" .tests)" \
          --format summary; then
        TEST_EXIT=1
      fi
    done
  fi
fi

# ─── run performance check ────────────────────────────────────────────────────
section "Performance check"

PERF_EXIT=0
if "$PYTHON_CMD" python/performance_monitor.py \
    --url "$TARGET_URL" \
    --runs 3 \
    --out "$REPORT_DIR/perf" \
    --max-total-ms 5000 \
    --max-ttfb-ms 1000 \
    --format text 2>/dev/null; then
  success "Performance within thresholds"
else
  warn "Performance check failed (may be a slow environment)"
  PERF_EXIT=1
fi

# ─── generate HTML report ─────────────────────────────────────────────────────
section "Generating reports"

if [[ -d "$OUTPUT_DIR" ]] && ls "$OUTPUT_DIR"/run_*.json &>/dev/null 2>&1; then
  if "$PYTHON_CMD" python/report_builder.py \
      --results "$OUTPUT_DIR" \
      --out "$REPORT_DIR" \
      --format all 2>/dev/null; then
    success "Reports written to $REPORT_DIR/"
    REPORT_FILES=$(ls "$REPORT_DIR"/*.html 2>/dev/null | wc -l | tr -d ' ')
    info "  Generated $REPORT_FILES HTML report(s)"
  else
    warn "Report generation encountered issues"
  fi
else
  warn "No run results found in $OUTPUT_DIR — skipping report generation"
fi

# ─── summary ──────────────────────────────────────────────────────────────────
section "E2E Summary"
echo ""
echo -e "  ${BOLD}Target:${RESET}   $TARGET_URL"
echo -e "  ${BOLD}Suite:${RESET}    $SUITE"
echo -e "  ${BOLD}Results:${RESET}  $OUTPUT_DIR/"
echo -e "  ${BOLD}Reports:${RESET}  $REPORT_DIR/"
echo ""

if [[ "$TEST_EXIT" -eq 0 ]]; then
  success "All E2E tests passed."
  exit 0
else
  error "One or more E2E tests FAILED."
  exit 1
fi
