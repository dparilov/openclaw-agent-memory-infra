#!/usr/bin/env bash
# install-meridiana.sh — Install MeridianA proxy for OpenClaw.
#
# MeridianA = @rynfar/meridian v1.30.2 with OpenClaw compatibility patches,
# distributed as a pre-built dist in vendor/meridiana-dist/.
# Base package license: MIT (https://github.com/rynfar/meridian).
#
# Usage:
#   bash scripts/install-meridiana.sh [OPTIONS]
#
# Options:
#   --target <dir>   Install directory (default: ~/meridiana-openclaw)
#   --port <port>    Default proxy port written to env file (default: 3470)
#   --dry-run        Print planned actions; do not install or modify anything
#   --help | -h      Show this help and exit
#
# Requirements (checked at startup):
#   - Node.js >= 22
#   - npm (any recent version)
#
# No bun required. No build step. Pre-built dist is vendored in this repo.
#
# After successful install:
#   1. Authenticate Claude Max account (run once per machine, requires browser):
#        node <target>/dist/cli.js profile add
#   2. Start the proxy:
#        MERIDIAN_PORT=3470 node <target>/dist/cli.js
#   3. Configure OpenClaw meridiana/* aliases to point to port 3470.
#
# Exit codes:
#   0 = success
#   1 = requirement not met or install failed
#   2 = --dry-run completed (nothing installed)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
VENDOR_DIR="${REPO_ROOT}/vendor/meridiana-dist"

DEFAULT_TARGET="${HOME}/meridiana-openclaw"
DEFAULT_PORT=3470

TARGET="${DEFAULT_TARGET}"
PORT="${DEFAULT_PORT}"
DRY_RUN=0

# ── Parse args ────────────────────────────────────────────────────────────────
for arg in "$@"; do
  case "$arg" in
    --dry-run)    DRY_RUN=1 ;;
    --help|-h)
      grep '^#' "$0" | sed 's/^# \?//'
      exit 0
      ;;
    --) ;;
    *)  ;;
  esac
done

i=0
args=("$@")
while [[ $i -lt ${#args[@]} ]]; do
  case "${args[$i]}" in
    --target) TARGET="${args[$((i+1))]}"; i=$((i+2)) ;;
    --port)   PORT="${args[$((i+1))]}"; i=$((i+2)) ;;
    *)        i=$((i+1)) ;;
  esac
done

_ok()   { echo "  OK    $*"; }
_fail() { echo "  FAIL  $*" >&2; exit 1; }
_dry()  { echo "  [dry-run] $*"; }

echo "── MeridianA installer ─────────────────────────────────────────────"
echo "  source:  ${VENDOR_DIR}"
echo "  target:  ${TARGET}"
echo "  port:    ${PORT}"
[[ $DRY_RUN -eq 1 ]] && echo "  mode:    DRY RUN — nothing will be modified"
echo "────────────────────────────────────────────────────────────────────"

# ── Step 1: Check requirements ────────────────────────────────────────────────
echo "Step 1: Check requirements"

if ! command -v node >/dev/null 2>&1; then
  _fail "node not found. Install Node.js >= 22 from https://nodejs.org"
fi
NODE_MAJOR=$(node --version | sed 's/v//' | cut -d. -f1)
if [[ $NODE_MAJOR -lt 22 ]]; then
  _fail "Node.js >= 22 required, found $(node --version). Upgrade at https://nodejs.org"
fi
_ok "node $(node --version)"

if ! command -v npm >/dev/null 2>&1; then
  _fail "npm not found. Install Node.js with npm from https://nodejs.org"
fi
_ok "npm $(npm --version)"

if [[ ! -d "${VENDOR_DIR}" ]]; then
  _fail "vendor directory not found: ${VENDOR_DIR}. Run from openclaw-agent-memory-infra repo root."
fi
if [[ ! -f "${VENDOR_DIR}/cli.js" ]]; then
  _fail "cli.js not found in ${VENDOR_DIR}. Repo may be incomplete."
fi
_ok "vendor dir: ${VENDOR_DIR} ($(ls "${VENDOR_DIR}"/*.js | wc -l) JS files)"

# ── Step 2: Create target directory ───────────────────────────────────────────
echo "Step 2: Create target directory"
if [[ $DRY_RUN -eq 1 ]]; then
  _dry "would create: ${TARGET}/dist/"
else
  mkdir -p "${TARGET}/dist"
  _ok "directory ready: ${TARGET}"
fi

# ── Step 3: Copy vendored dist ────────────────────────────────────────────────
echo "Step 3: Copy pre-built dist"
if [[ $DRY_RUN -eq 1 ]]; then
  _dry "would copy: ${VENDOR_DIR}/*.js → ${TARGET}/dist/"
  _dry "would copy: ${VENDOR_DIR}/package.json → ${TARGET}/package.json"
else
  cp "${VENDOR_DIR}"/*.js "${TARGET}/dist/"
  cp "${VENDOR_DIR}/package.json" "${TARGET}/package.json"
  _ok "dist copied: $(ls "${TARGET}/dist/"*.js | wc -l) JS files"
fi

# ── Step 4: Install runtime dependencies ──────────────────────────────────────
echo "Step 4: Install runtime dependencies"
if [[ $DRY_RUN -eq 1 ]]; then
  _dry "would run: npm install in ${TARGET}"
else
  cd "${TARGET}"
  npm install --omit=dev --prefer-offline 2>/dev/null || npm install --omit=dev
  _ok "node_modules installed"
fi

# ── Step 5: Smoke test ────────────────────────────────────────────────────────
echo "Step 5: Smoke test"
if [[ $DRY_RUN -eq 1 ]]; then
  _dry "would run: node ${TARGET}/dist/cli.js --help"
else
  if node "${TARGET}/dist/cli.js" --help 2>&1 | grep -q "meridian"; then
    _ok "cli.js responds to --help"
  else
    _fail "cli.js did not respond correctly to --help"
  fi
fi

# ── Step 6: Write env file ────────────────────────────────────────────────────
echo "Step 6: Write port config"
ENV_FILE="${TARGET}/.meridiana.env"
if [[ $DRY_RUN -eq 1 ]]; then
  _dry "would write: ${ENV_FILE} with MERIDIAN_PORT=${PORT}"
else
  cat > "${ENV_FILE}" << EOF
# MeridianA proxy configuration
# Base: @rynfar/meridian v1.30.2 + OpenClaw patch (MIT)
# Vendor: vendor/meridiana-dist/ in openclaw-agent-memory-infra

MERIDIAN_PORT=${PORT}
MERIDIAN_HOST=127.0.0.1
# MERIDIAN_PASSTHROUGH=0
EOF
  _ok "env file: ${ENV_FILE}"
fi

# ── Summary ───────────────────────────────────────────────────────────────────
echo "────────────────────────────────────────────────────────────────────"
if [[ $DRY_RUN -eq 1 ]]; then
  echo "Dry run complete. Re-run without --dry-run to install."
  exit 2
fi

echo ""
echo "MeridianA installed at: ${TARGET}"
echo ""
echo "NEXT STEPS — required before use:"
echo ""
echo "  1. Authenticate Claude Max account (once per machine, requires browser):"
echo "       node ${TARGET}/dist/cli.js profile add"
echo "     OAuth browser opens. Tokens stored by meridian."
echo "     Do NOT copy tokens between machines."
echo ""
echo "  2. Start the proxy:"
echo "       MERIDIAN_PORT=${PORT} node ${TARGET}/dist/cli.js"
echo "     Or:"
echo "       source ${ENV_FILE} && node ${TARGET}/dist/cli.js"
echo ""
echo "  3. Verify proxy:"
echo "       curl -s http://127.0.0.1:${PORT}/v1/models | head -3"
echo ""
echo "  4. Configure OpenClaw meridiana/* aliases → port ${PORT}."
echo "     See docs/MERIDIANA_DEPENDENCY.md."
echo ""
echo "  AUTH COMMAND: node ${TARGET}/dist/cli.js profile add"
echo ""
exit 0
