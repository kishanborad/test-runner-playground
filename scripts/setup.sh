#!/usr/bin/env bash
# scripts/setup.sh — Development environment setup
#
# Installs and verifies all prerequisites for the test-runner-playground:
#   - Node.js (via nvm or system) with required version
#   - Python 3.9+ with pip
#   - npm dependencies (package.json)
#   - Python dependencies (python/requirements.txt)
#   - Git hooks (optional)
#
# Usage:
#   ./scripts/setup.sh
#   ./scripts/setup.sh --skip-python
#   ./scripts/setup.sh --skip-node

set -euo pipefail

# ─── colours ──────────────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
RESET='\033[0m'

# ─── logging helpers ──────────────────────────────────────────────────────────
info()    { echo -e "${BLUE}[setup]${RESET} $*"; }
success() { echo -e "${GREEN}[setup] ✓${RESET} $*"; }
warn()    { echo -e "${YELLOW}[setup] ⚠${RESET} $*"; }
error()   { echo -e "${RED}[setup] ✗${RESET} $*" >&2; }
step()    { echo -e "\n${BOLD}── $* ─────────────────────────────────────${RESET}"; }

# ─── argument parsing ─────────────────────────────────────────────────────────
SKIP_NODE=false
SKIP_PYTHON=false
SKIP_HOOKS=false

for arg in "$@"; do
  case "$arg" in
    --skip-node)   SKIP_NODE=true ;;
    --skip-python) SKIP_PYTHON=true ;;
    --skip-hooks)  SKIP_HOOKS=true ;;
    --help|-h)
      echo "Usage: $0 [--skip-node] [--skip-python] [--skip-hooks]"
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
info "Project root: $PROJECT_ROOT"

# ─── version requirements ─────────────────────────────────────────────────────
REQUIRED_NODE_MAJOR=18
REQUIRED_PYTHON_MAJOR=3
REQUIRED_PYTHON_MINOR=9

# ─── Node.js + npm setup ──────────────────────────────────────────────────────
if [[ "$SKIP_NODE" == "false" ]]; then
  step "Node.js & npm"

  if command -v node &>/dev/null; then
    NODE_VERSION=$(node --version | sed 's/v//')
    NODE_MAJOR=$(echo "$NODE_VERSION" | cut -d. -f1)
    if [[ "$NODE_MAJOR" -lt "$REQUIRED_NODE_MAJOR" ]]; then
      warn "Node.js $NODE_VERSION found but v${REQUIRED_NODE_MAJOR}+ is required."
      warn "Install the latest LTS from https://nodejs.org or use nvm:"
      warn "  nvm install --lts && nvm use --lts"
    else
      success "Node.js $NODE_VERSION"
    fi
  else
    error "Node.js is not installed."
    error "Install from https://nodejs.org or via nvm:"
    error "  curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash"
    error "  nvm install --lts && nvm use --lts"
    exit 1
  fi

  if command -v npm &>/dev/null; then
    success "npm $(npm --version)"
  else
    error "npm is not available. It should come with Node.js."
    exit 1
  fi

  info "Installing npm dependencies..."
  npm ci --prefer-offline 2>&1 | tail -5
  success "npm dependencies installed ($(npm ls --depth=0 2>/dev/null | wc -l | tr -d ' ') packages)"
fi

# ─── Python setup ─────────────────────────────────────────────────────────────
if [[ "$SKIP_PYTHON" == "false" ]]; then
  step "Python"

  # Find Python 3 executable
  PYTHON_CMD=""
  for candidate in python3 python python3.12 python3.11 python3.10 python3.9; do
    if command -v "$candidate" &>/dev/null; then
      PY_MAJOR=$("$candidate" -c "import sys; print(sys.version_info.major)")
      PY_MINOR=$("$candidate" -c "import sys; print(sys.version_info.minor)")
      if [[ "$PY_MAJOR" -eq "$REQUIRED_PYTHON_MAJOR" && "$PY_MINOR" -ge "$REQUIRED_PYTHON_MINOR" ]]; then
        PYTHON_CMD="$candidate"
        break
      fi
    fi
  done

  if [[ -z "$PYTHON_CMD" ]]; then
    error "Python ${REQUIRED_PYTHON_MAJOR}.${REQUIRED_PYTHON_MINOR}+ is required but not found."
    error "Install from https://python.org or via pyenv:"
    error "  pyenv install 3.12.0 && pyenv local 3.12.0"
    exit 1
  fi

  PYTHON_VERSION=$("$PYTHON_CMD" --version | awk '{print $2}')
  success "Python $PYTHON_VERSION ($PYTHON_CMD)"

  # pip
  if ! "$PYTHON_CMD" -m pip --version &>/dev/null; then
    error "pip is not available for $PYTHON_CMD."
    error "Install it: $PYTHON_CMD -m ensurepip --upgrade"
    exit 1
  fi
  success "pip $("$PYTHON_CMD" -m pip --version | awk '{print $2}')"

  # Virtual environment (recommended but not required)
  if [[ ! -d "$PROJECT_ROOT/.venv" ]]; then
    info "Creating Python virtual environment at .venv ..."
    "$PYTHON_CMD" -m venv "$PROJECT_ROOT/.venv"
    success "Virtual environment created"
  else
    info "Virtual environment .venv already exists"
  fi

  # Activate venv for the rest of this script
  # shellcheck source=/dev/null
  source "$PROJECT_ROOT/.venv/bin/activate"
  info "Activated .venv ($(python --version))"

  # Install Python dependencies
  info "Installing Python dependencies from python/requirements.txt ..."
  pip install --quiet --upgrade pip
  pip install --quiet -r python/requirements.txt
  INSTALLED=$(pip list --format=columns 2>/dev/null | wc -l | tr -d ' ')
  success "Python packages installed ($INSTALLED packages in .venv)"

  # Install the project in editable mode for CLI entry points
  if [[ -f "$PROJECT_ROOT/python/setup.py" ]]; then
    info "Installing project in editable mode (setup.py) ..."
    pip install --quiet -e python/
    success "Project installed (tr-run, tr-generate, tr-report, tr-a11y, tr-perf available)"
  fi
fi

# ─── Git hooks ────────────────────────────────────────────────────────────────
if [[ "$SKIP_HOOKS" == "false" && -d "$PROJECT_ROOT/.git" ]]; then
  step "Git hooks"

  PRE_COMMIT="$PROJECT_ROOT/.git/hooks/pre-commit"
  if [[ ! -f "$PRE_COMMIT" ]]; then
    cat > "$PRE_COMMIT" << 'HOOK'
#!/usr/bin/env bash
# pre-commit hook: run type-check and lint before committing
set -euo pipefail

echo "[pre-commit] Running TypeScript type check..."
npx tsc --noEmit

echo "[pre-commit] Checks passed."
HOOK
    chmod +x "$PRE_COMMIT"
    success "Pre-commit hook installed"
  else
    info "Pre-commit hook already exists"
  fi
fi

# ─── Summary ──────────────────────────────────────────────────────────────────
step "Setup complete"

echo ""
echo -e "${BOLD}Next steps:${RESET}"

if [[ "$SKIP_NODE" == "false" ]]; then
  echo -e "  ${GREEN}npm run dev${RESET}          — start the frontend dev server"
  echo -e "  ${GREEN}npm test${RESET}             — run Vitest unit tests"
  echo -e "  ${GREEN}npm run build${RESET}        — build production bundle"
fi

if [[ "$SKIP_PYTHON" == "false" ]]; then
  echo ""
  echo -e "  ${GREEN}source .venv/bin/activate${RESET}"
  echo -e "  ${GREEN}cd python && python -m pytest tests/ -v${RESET}  — run Python tests"
  echo -e "  ${GREEN}tr-run --url http://localhost:5173 --file tests/smoke.tests${RESET}"
  echo -e "  ${GREEN}tr-a11y --url http://localhost:5173${RESET}"
  echo -e "  ${GREEN}tr-perf --url http://localhost:5173 --runs 5${RESET}"
fi

echo ""
echo -e "  ${GREEN}./scripts/test.sh${RESET}   — run the full test suite"
echo -e "  ${GREEN}./scripts/run-e2e.sh${RESET} — start dev server + run e2e tests"
echo ""
