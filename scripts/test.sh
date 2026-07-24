#!/usr/bin/env bash
# scripts/test.sh — Full test suite runner (Python + frontend)
#
# Runs all tests in the correct order and produces a unified exit code:
#   1. Python unit tests (pytest in python/)
#   2. Frontend Vitest unit tests
#   3. TypeScript type check (tsc --noEmit)
#
# Flags:
#   --python-only   Skip frontend tests
#   --frontend-only Skip Python tests
#   --coverage      Collect and report coverage for both stacks
#   --verbose       Enable verbose test output
#   --fail-fast     Stop on first failure (across test suites)
#   --watch         Run tests in watch mode (frontend only for now)
#
# Exit codes:
#   0  All tests passed
#   1  One or more suites failed
#   2  Environment prerequisite missing

set -euo pipefail

# ─── colours ──────────────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
CYAN='\033[0;36m'
RESET='\033[0m'

info()    { echo -e "${BLUE}[test]${RESET} $*"; }
success() { echo -e "${GREEN}[test] ✓${RESET} $*"; }
warn()    { echo -e "${YELLOW}[test] ⚠${RESET} $*"; }
error()   { echo -e "${RED}[test] ✗${RESET} $*" >&2; }
section() { echo -e "\n${CYAN}${BOLD}══ $* ══${RESET}"; }

# ─── argument parsing ─────────────────────────────────────────────────────────
PYTHON_ONLY=false
FRONTEND_ONLY=false
COVERAGE=false
VERBOSE=false
FAIL_FAST=false
WATCH=false

for arg in "$@"; do
  case "$arg" in
    --python-only)   PYTHON_ONLY=true ;;
    --frontend-only) FRONTEND_ONLY=true ;;
    --coverage)      COVERAGE=true ;;
    --verbose|-v)    VERBOSE=true ;;
    --fail-fast|-x)  FAIL_FAST=true ;;
    --watch)         WATCH=true ;;
    --help|-h)
      cat << 'HELP'
Usage: ./scripts/test.sh [options]

Options:
  --python-only    Only run Python tests
  --frontend-only  Only run frontend tests
  --coverage       Collect coverage reports
  --verbose, -v    Verbose test output
  --fail-fast, -x  Stop on first failure
  --watch          Watch mode (frontend only)
  --help           Show this message
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

# ─── tracking ─────────────────────────────────────────────────────────────────
PYTHON_RESULT=0
FRONTEND_RESULT=0
TYPECHECK_RESULT=0
START_TIME=$(date +%s)

# ─── Python tests ─────────────────────────────────────────────────────────────
if [[ "$FRONTEND_ONLY" == "false" ]]; then
  section "Python Unit Tests"

  # Check Python is available
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
    exit 2
  fi

  # Activate venv if it exists
  if [[ -d "$PROJECT_ROOT/.venv" ]]; then
    # shellcheck source=/dev/null
    source "$PROJECT_ROOT/.venv/bin/activate"
    info "Using .venv ($("$PYTHON_CMD" --version))"
  else
    warn "No .venv found — using system Python. Run ./scripts/setup.sh for isolation."
  fi

  # Check pytest is available
  if ! "$PYTHON_CMD" -m pytest --version &>/dev/null; then
    error "pytest not found. Run: pip install -r python/requirements.txt"
    PYTHON_RESULT=2
  else
    PYTEST_ARGS=(
      "python/tests/"
      "--tb=short"
    )

    [[ "$VERBOSE" == "true" ]]   && PYTEST_ARGS+=("-v")
    [[ "$FAIL_FAST" == "true" ]] && PYTEST_ARGS+=("-x")

    if [[ "$COVERAGE" == "true" ]]; then
      PYTEST_ARGS+=(
        "--cov=python"
        "--cov-report=term-missing"
        "--cov-report=html:coverage/python"
        "--cov-report=xml:coverage/python.xml"
      )
      mkdir -p coverage
    fi

    info "Running: $PYTHON_CMD -m pytest ${PYTEST_ARGS[*]}"
    if "$PYTHON_CMD" -m pytest "${PYTEST_ARGS[@]}"; then
      success "Python tests passed"
    else
      error "Python tests FAILED"
      PYTHON_RESULT=1
      if [[ "$FAIL_FAST" == "true" ]]; then
        error "Stopping early (--fail-fast)"
        exit 1
      fi
    fi
  fi
fi

# ─── TypeScript type check ─────────────────────────────────────────────────────
if [[ "$PYTHON_ONLY" == "false" ]]; then
  section "TypeScript Type Check"

  if ! command -v npx &>/dev/null; then
    error "npx not found. Run ./scripts/setup.sh first."
    exit 2
  fi

  if npx tsc --noEmit; then
    success "TypeScript type check passed"
  else
    error "TypeScript type check FAILED"
    TYPECHECK_RESULT=1
    if [[ "$FAIL_FAST" == "true" ]]; then
      exit 1
    fi
  fi
fi

# ─── Frontend / Vitest tests ──────────────────────────────────────────────────
if [[ "$PYTHON_ONLY" == "false" ]]; then
  section "Frontend Tests (Vitest)"

  if ! command -v npm &>/dev/null; then
    error "npm not found. Run ./scripts/setup.sh first."
    exit 2
  fi

  if [[ ! -d "$PROJECT_ROOT/node_modules" ]]; then
    error "node_modules not found. Run: npm ci"
    FRONTEND_RESULT=2
  else
    VITEST_ARGS=()
    [[ "$WATCH" == "true" ]]    && VITEST_ARGS+=("--watch")
    [[ "$VERBOSE" == "true" ]]  && VITEST_ARGS+=("--reporter=verbose")
    [[ "$COVERAGE" == "true" ]] && VITEST_ARGS+=("--coverage")

    if [[ "$WATCH" == "false" ]]; then
      VITEST_ARGS+=("--run")
    fi

    info "Running: npm test -- ${VITEST_ARGS[*]}"
    if npm test -- "${VITEST_ARGS[@]}"; then
      success "Frontend tests passed"
    else
      error "Frontend tests FAILED"
      FRONTEND_RESULT=1
      if [[ "$FAIL_FAST" == "true" ]]; then
        exit 1
      fi
    fi
  fi
fi

# ─── Summary ──────────────────────────────────────────────────────────────────
END_TIME=$(date +%s)
ELAPSED=$((END_TIME - START_TIME))

section "Test Summary"
echo ""

print_result() {
  local label="$1"
  local result="$2"
  local skipped="$3"

  if [[ "$skipped" == "true" ]]; then
    echo -e "  ${YELLOW}⊘${RESET}  ${label}: ${YELLOW}SKIPPED${RESET}"
  elif [[ "$result" == "0" ]]; then
    echo -e "  ${GREEN}✓${RESET}  ${label}: ${GREEN}PASSED${RESET}"
  else
    echo -e "  ${RED}✗${RESET}  ${label}: ${RED}FAILED${RESET}"
  fi
}

print_result "Python tests"         "$PYTHON_RESULT"    "$FRONTEND_ONLY"
print_result "TypeScript typecheck" "$TYPECHECK_RESULT" "$PYTHON_ONLY"
print_result "Frontend tests"       "$FRONTEND_RESULT"  "$PYTHON_ONLY"

echo ""
echo -e "  Total time: ${ELAPSED}s"
echo ""

# Overall exit code
OVERALL=$((PYTHON_RESULT + FRONTEND_RESULT + TYPECHECK_RESULT))
if [[ "$OVERALL" -eq 0 ]]; then
  echo -e "${GREEN}${BOLD}All tests passed.${RESET}"
  exit 0
else
  echo -e "${RED}${BOLD}One or more test suites failed.${RESET}"
  exit 1
fi
