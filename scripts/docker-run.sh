#!/usr/bin/env bash
# scripts/docker-run.sh — Build and run the Docker test automation stack
#
# Manages the full Docker Compose lifecycle:
#   - Builds the test-runner image
#   - Runs the test suite against a target URL
#   - Optionally runs the report server
#   - Supports individual service invocations (a11y, perf, generate)
#
# Usage:
#   ./scripts/docker-run.sh
#   ./scripts/docker-run.sh --url http://host.docker.internal:5173
#   ./scripts/docker-run.sh --service a11y
#   ./scripts/docker-run.sh --service perf --runs 5
#   ./scripts/docker-run.sh --no-cache
#   ./scripts/docker-run.sh --serve-reports
#   ./scripts/docker-run.sh --down

set -euo pipefail

# ─── colours ──────────────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
CYAN='\033[0;36m'
RESET='\033[0m'

info()    { echo -e "${BLUE}[docker]${RESET} $*"; }
success() { echo -e "${GREEN}[docker] ✓${RESET} $*"; }
warn()    { echo -e "${YELLOW}[docker] ⚠${RESET} $*"; }
error()   { echo -e "${RED}[docker] ✗${RESET} $*" >&2; }
section() { echo -e "\n${CYAN}${BOLD}── $* ──────────────────────────────────${RESET}"; }

# ─── argument parsing ─────────────────────────────────────────────────────────
TARGET_URL="${TARGET_URL:-http://host.docker.internal:5173}"
SERVICE="test-runner"
NO_CACHE=false
SERVE_REPORTS=false
REPORT_PORT=8080
WORKERS=2
PERF_RUNS=5
DO_DOWN=false
DO_LOGS=false
TEST_FILE=""

for arg in "$@"; do
  case "$arg" in
    --url=*)           TARGET_URL="${arg#--url=}" ;;
    --service=*)       SERVICE="${arg#--service=}" ;;
    --no-cache)        NO_CACHE=true ;;
    --serve-reports)   SERVE_REPORTS=true ;;
    --report-port=*)   REPORT_PORT="${arg#--report-port=}" ;;
    --workers=*)       WORKERS="${arg#--workers=}" ;;
    --runs=*)          PERF_RUNS="${arg#--runs=}" ;;
    --down)            DO_DOWN=true ;;
    --logs)            DO_LOGS=true ;;
    --file=*)          TEST_FILE="${arg#--file=}" ;;
    --help|-h)
      cat << 'HELP'
Usage: ./scripts/docker-run.sh [options]

Options:
  --url=URL           Target URL for tests (default: http://host.docker.internal:5173)
  --service=NAME      Service to run: test-runner|a11y|perf|generate (default: test-runner)
  --no-cache          Rebuild Docker image without cache
  --serve-reports     Start the report server after running tests
  --report-port=NUM   Report server port (default: 8080)
  --workers=NUM       Parallel test workers (default: 2)
  --runs=NUM          Performance monitor runs (default: 5)
  --file=PATH         DSL test file to run (test-runner service)
  --down              Stop and remove all containers
  --logs              Show container logs
  --help              Show this message

Services:
  test-runner    Run the Python test suite
  a11y           Run the accessibility checker
  perf           Run the performance monitor
  generate       Generate test cases from the target URL
  reports        Start the report server only
  all            Run test-runner + report-builder + report-server

Examples:
  ./scripts/docker-run.sh --url http://localhost:5173
  ./scripts/docker-run.sh --service a11y --url http://localhost:5173
  ./scripts/docker-run.sh --service perf --runs 10
  ./scripts/docker-run.sh --serve-reports
  ./scripts/docker-run.sh --down
HELP
      exit 0
      ;;
    *)
      error "Unknown argument: $arg"
      exit 1
      ;;
  esac
done

# ─── prerequisites ────────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

if ! command -v docker &>/dev/null; then
  error "Docker is not installed. Install from https://docker.com"
  exit 1
fi

if ! docker info &>/dev/null; then
  error "Docker daemon is not running. Start Docker and try again."
  exit 1
fi

COMPOSE_CMD=""
if docker compose version &>/dev/null 2>&1; then
  COMPOSE_CMD="docker compose"
elif command -v docker-compose &>/dev/null; then
  COMPOSE_CMD="docker-compose"
else
  error "Docker Compose is not available. Install Docker Desktop or the Compose plugin."
  exit 1
fi

info "Using: $COMPOSE_CMD"
info "Project root: $PROJECT_ROOT"

# ─── tear down ────────────────────────────────────────────────────────────────
if [[ "$DO_DOWN" == "true" ]]; then
  section "Stopping containers"
  $COMPOSE_CMD down --remove-orphans
  success "All containers stopped and removed"
  exit 0
fi

# ─── show logs ────────────────────────────────────────────────────────────────
if [[ "$DO_LOGS" == "true" ]]; then
  section "Container logs"
  $COMPOSE_CMD logs --tail=100 --follow
  exit 0
fi

# ─── export environment variables for docker-compose ─────────────────────────
export TARGET_URL
export WORKERS
export REPORT_PORT
export PERF_RUNS

# ─── build ────────────────────────────────────────────────────────────────────
section "Building Docker image"

BUILD_ARGS=()
[[ "$NO_CACHE" == "true" ]] && BUILD_ARGS+=("--no-cache")

info "Building test-runner-playground:latest ..."
$COMPOSE_CMD build "${BUILD_ARGS[@]}" test-runner
success "Image built"

# ─── run the requested service ────────────────────────────────────────────────
section "Running service: $SERVICE"
info "Target URL: $TARGET_URL"

case "$SERVICE" in

  test-runner)
    CMD_PARTS=("python" "test_runner.py"
      "--url"     "$TARGET_URL"
      "--workers" "$WORKERS"
      "--output"  "/app/results"
      "--format"  "summary"
    )
    [[ -n "$TEST_FILE" ]] && CMD_PARTS+=("--file" "/app/$TEST_FILE")
    $COMPOSE_CMD run --rm \
      -e TARGET_URL="$TARGET_URL" \
      test-runner "${CMD_PARTS[@]}"
    ;;

  a11y)
    $COMPOSE_CMD run --rm \
      --profile a11y \
      -e TARGET_URL="$TARGET_URL" \
      a11y-checker \
      python accessibility_checker.py \
        --url    "$TARGET_URL" \
        --format html \
        --out    "/app/reports/a11y_report.html"
    info "Report written to reports/a11y_report.html (inside container volume)"
    ;;

  perf)
    $COMPOSE_CMD run --rm \
      --profile perf \
      -e TARGET_URL="$TARGET_URL" \
      -e PERF_RUNS="$PERF_RUNS" \
      perf-monitor \
      python performance_monitor.py \
        --url   "$TARGET_URL" \
        --runs  "$PERF_RUNS" \
        --out   "/app/reports/perf" \
        --format text
    ;;

  generate)
    $COMPOSE_CMD run --rm \
      -e TARGET_URL="$TARGET_URL" \
      test-runner \
      python test_generator.py \
        --url    "$TARGET_URL" \
        --format both \
        --out    "/app/generated" \
        --prefix "generated"
    info "Generated files written to /app/generated (inside container volume)"
    ;;

  reports)
    info "Starting report server on port $REPORT_PORT ..."
    $COMPOSE_CMD up -d report-server
    success "Report server running at http://localhost:$REPORT_PORT"
    exit 0
    ;;

  all)
    info "Running full stack: test-runner → report-builder → report-server"
    $COMPOSE_CMD up --build --abort-on-container-exit
    ;;

  *)
    error "Unknown service: $SERVICE"
    error "Valid services: test-runner, a11y, perf, generate, reports, all"
    exit 1
    ;;
esac

# ─── optional report server ───────────────────────────────────────────────────
if [[ "$SERVE_REPORTS" == "true" && "$SERVICE" != "reports" ]]; then
  section "Starting report server"

  # First, generate the reports from whatever results exist
  info "Generating HTML reports..."
  $COMPOSE_CMD run --rm \
    test-runner \
    python report_builder.py \
      --results /app/results \
      --out     /app/reports \
      --format  all \
  || warn "Report generation had issues (may be no results yet)"

  # Start the server
  $COMPOSE_CMD up -d report-server
  success "Report server running at http://localhost:$REPORT_PORT"
fi

# ─── summary ──────────────────────────────────────────────────────────────────
section "Done"
echo ""
echo -e "  ${BOLD}Service:${RESET}  $SERVICE"
echo -e "  ${BOLD}Target:${RESET}   $TARGET_URL"
if [[ "$SERVE_REPORTS" == "true" ]]; then
  echo -e "  ${BOLD}Reports:${RESET}  http://localhost:$REPORT_PORT"
fi
echo ""
echo -e "  Run ${CYAN}./scripts/docker-run.sh --down${RESET} to stop all containers"
echo ""
