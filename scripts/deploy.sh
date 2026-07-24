#!/usr/bin/env bash
# scripts/deploy.sh — Build and deploy to GitHub Pages
#
# Builds the Vite frontend bundle, optionally runs tests first, then pushes
# the dist/ directory to the gh-pages branch using git worktree.
#
# Usage:
#   ./scripts/deploy.sh
#   ./scripts/deploy.sh --skip-tests
#   ./scripts/deploy.sh --dry-run
#   ./scripts/deploy.sh --branch staging-pages

set -euo pipefail

# ─── colours ──────────────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
RESET='\033[0m'

info()    { echo -e "${BLUE}[deploy]${RESET} $*"; }
success() { echo -e "${GREEN}[deploy] ✓${RESET} $*"; }
warn()    { echo -e "${YELLOW}[deploy] ⚠${RESET} $*"; }
error()   { echo -e "${RED}[deploy] ✗${RESET} $*" >&2; }
step()    { echo -e "\n${BOLD}── $* ────────────────────────────────────${RESET}"; }

# ─── argument parsing ─────────────────────────────────────────────────────────
SKIP_TESTS=false
DRY_RUN=false
PAGES_BRANCH="gh-pages"

for arg in "$@"; do
  case "$arg" in
    --skip-tests)   SKIP_TESTS=true ;;
    --dry-run)      DRY_RUN=true ;;
    --branch=*)     PAGES_BRANCH="${arg#--branch=}" ;;
    --help|-h)
      cat << 'HELP'
Usage: ./scripts/deploy.sh [options]

Options:
  --skip-tests      Skip running tests before building
  --dry-run         Build but do not push to gh-pages
  --branch=NAME     Target Pages branch (default: gh-pages)
  --help            Show this message
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

for cmd in git node npm; do
  if ! command -v "$cmd" &>/dev/null; then
    error "Required command not found: $cmd"
    exit 1
  fi
done

# Must be a git repo
if ! git rev-parse --is-inside-work-tree &>/dev/null; then
  error "Not inside a git repository."
  exit 1
fi

CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
COMMIT_SHA=$(git rev-parse --short HEAD)
DEPLOY_TIME=$(date -u +"%Y-%m-%d %H:%M UTC")

info "Branch: $CURRENT_BRANCH ($COMMIT_SHA)"
info "Deploying to: $PAGES_BRANCH"
[[ "$DRY_RUN" == "true" ]] && warn "DRY RUN mode — nothing will be pushed"

# ─── check working tree ────────────────────────────────────────────────────────
if [[ -n "$(git status --porcelain)" ]]; then
  warn "You have uncommitted changes. Consider committing before deploying."
fi

# ─── run tests ────────────────────────────────────────────────────────────────
if [[ "$SKIP_TESTS" == "false" ]]; then
  step "Running tests before build"
  if bash "$SCRIPT_DIR/test.sh" --frontend-only; then
    success "Tests passed"
  else
    error "Tests failed. Fix them before deploying, or use --skip-tests."
    exit 1
  fi
fi

# ─── build ────────────────────────────────────────────────────────────────────
step "Building production bundle"

info "Installing dependencies..."
npm ci --prefer-offline

info "Running build..."
NODE_ENV=production npm run build

if [[ ! -d "$PROJECT_ROOT/dist" ]]; then
  error "Build failed — dist/ directory not found."
  exit 1
fi

DIST_SIZE=$(du -sh "$PROJECT_ROOT/dist" | cut -f1)
success "Build complete (dist size: $DIST_SIZE)"

# ─── dry run: just show what would happen ─────────────────────────────────────
if [[ "$DRY_RUN" == "true" ]]; then
  step "Dry run — skipping push"
  info "Would push dist/ to branch: $PAGES_BRANCH"
  info "dist/ contents:"
  find "$PROJECT_ROOT/dist" -type f | sort | head -30 | sed 's/^/    /'
  echo ""
  success "Dry run complete. Use without --dry-run to actually deploy."
  exit 0
fi

# ─── deploy via git worktree ──────────────────────────────────────────────────
step "Deploying to $PAGES_BRANCH"

WORKTREE_DIR=$(mktemp -d)
trap 'git worktree remove --force "$WORKTREE_DIR" 2>/dev/null || rm -rf "$WORKTREE_DIR"' EXIT

# Create or check out the gh-pages branch
if git ls-remote --exit-code origin "$PAGES_BRANCH" &>/dev/null; then
  info "Checking out existing $PAGES_BRANCH branch..."
  git worktree add "$WORKTREE_DIR" "$PAGES_BRANCH"
else
  info "Creating orphan $PAGES_BRANCH branch..."
  git worktree add --orphan "$WORKTREE_DIR" "$PAGES_BRANCH"
fi

# Clear the worktree and copy new build
info "Syncing dist/ to worktree..."
find "$WORKTREE_DIR" -mindepth 1 -not -name '.git' -delete 2>/dev/null || true
cp -r "$PROJECT_ROOT/dist/." "$WORKTREE_DIR/"

# Add .nojekyll so GitHub Pages doesn't process the files through Jekyll
touch "$WORKTREE_DIR/.nojekyll"

# Commit and push
cd "$WORKTREE_DIR"

if [[ -z "$(git status --porcelain)" ]]; then
  info "No changes to deploy."
  exit 0
fi

git add -A

git commit -m "deploy: $CURRENT_BRANCH@$COMMIT_SHA — $DEPLOY_TIME

Built from commit $COMMIT_SHA on branch $CURRENT_BRANCH.
Deployed at $DEPLOY_TIME."

info "Pushing to origin/$PAGES_BRANCH..."
git push origin "$PAGES_BRANCH"

success "Deployed to $PAGES_BRANCH (commit: $(git rev-parse --short HEAD))"
echo ""
info "GitHub Pages URL: https://$(git remote get-url origin | sed 's/.*github.com[:/]//' | sed 's/\.git//' | tr '/' '.').github.io/$(git remote get-url origin | sed 's|.*/||' | sed 's/\.git//')"
