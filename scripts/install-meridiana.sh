#!/usr/bin/env bash
# install-meridiana.sh — Install MeridianA: patched @rynfar/meridian proxy for OpenClaw.
#
# MeridianA = @rynfar/meridian v1.30.2 + OpenClaw compatibility patch.
# The patch (patches/meridiana-openclaw.patch) is vendored in this repo.
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
#   - bun  (installed automatically if missing)
#   - patch (GNU patch, from system package manager)
#   - Internet access to registry.npmjs.org
#
# After successful install:
#   1. Authenticate Claude Max account:
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
PATCH_FILE="${REPO_ROOT}/patches/meridiana-openclaw.patch"

BASE_PKG="@rynfar/meridian"
BASE_VERSION="1.30.2"
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

# Parse key=value style args
i=0
args=("$@")
while [[ $i -lt ${#args[@]} ]]; do
  case "${args[$i]}" in
    --target) TARGET="${args[$((i+1))]}"; i=$((i+2)) ;;
    --port)   PORT="${args[$((i+1))]}"; i=$((i+2)) ;;
    *)        i=$((i+1)) ;;
  esac
done

_log()  { echo "  [meridiana] $*"; }
_ok()   { echo "  OK    $*"; }
_fail() { echo "  FAIL  $*" >&2; exit 1; }
_dry()  { echo "  [dry-run] $*"; }

echo "── MeridianA installer ─────────────────────────────────────────────"
echo "  base:    ${BASE_PKG}@${BASE_VERSION}"
echo "  target:  ${TARGET}"
echo "  port:    ${PORT}"
echo "  patch:   ${PATCH_FILE}"
[[ $DRY_RUN -eq 1 ]] && echo "  mode:    DRY RUN — nothing will be modified"
echo "────────────────────────────────────────────────────────────────────"

# ── Step 1: Check requirements ────────────────────────────────────────────────
echo "Step 1: Check requirements"

# Node >= 22
if ! command -v node >/dev/null 2>&1; then
  _fail "node not found. Install Node.js >= 22 from https://nodejs.org"
fi
NODE_MAJOR=$(node --version | sed 's/v//' | cut -d. -f1)
if [[ $NODE_MAJOR -lt 22 ]]; then
  _fail "Node.js >= 22 required, found $(node --version). Upgrade at https://nodejs.org"
fi
_ok "node $(node --version)"

# npm
if ! command -v npm >/dev/null 2>&1; then
  _fail "npm not found. Install Node.js with npm from https://nodejs.org"
fi
_ok "npm $(npm --version)"

# patch
if ! command -v patch >/dev/null 2>&1; then
  _fail "GNU patch not found. Install with: sudo apt-get install patch"
fi
_ok "patch $(patch --version | head -1)"

# Patch file
if [[ ! -f "${PATCH_FILE}" ]]; then
  _fail "patch file not found: ${PATCH_FILE}"
fi
_ok "patch file: ${PATCH_FILE} ($(wc -l < "${PATCH_FILE}") lines)"

# bun (auto-install if missing)
if ! command -v bun >/dev/null 2>&1; then
  _log "bun not found — installing via official installer..."
  if [[ $DRY_RUN -eq 1 ]]; then
    _dry "would run: curl -fsSL https://bun.sh/install | bash"
  else
    curl -fsSL https://bun.sh/install | bash
    export PATH="${HOME}/.bun/bin:${PATH}"
    if ! command -v bun >/dev/null 2>&1; then
      _fail "bun install failed. Install manually: https://bun.sh"
    fi
  fi
fi
if command -v bun >/dev/null 2>&1; then
  _ok "bun $(bun --version)"
fi

# ── Step 2: Prepare target directory ─────────────────────────────────────────
echo "Step 2: Prepare target directory"
if [[ $DRY_RUN -eq 1 ]]; then
  _dry "would create: ${TARGET}"
else
  mkdir -p "${TARGET}"
  _ok "target directory ready: ${TARGET}"
fi

# ── Step 3: Download base package ────────────────────────────────────────────
echo "Step 3: Download ${BASE_PKG}@${BASE_VERSION}"
if [[ $DRY_RUN -eq 1 ]]; then
  _dry "would run: npm pack ${BASE_PKG}@${BASE_VERSION} in ${TARGET}"
else
  cd "${TARGET}"
  TARBALL=$(npm pack "${BASE_PKG}@${BASE_VERSION}" 2>/dev/null)
  _ok "downloaded: ${TARBALL}"
  tar xzf "${TARBALL}" --strip-components=1
  rm -f "${TARBALL}"
  _ok "source extracted to ${TARGET}"
fi

# ── Step 4: Apply OpenClaw compatibility patch ────────────────────────────────
echo "Step 4: Apply OpenClaw compatibility patch"
if [[ $DRY_RUN -eq 1 ]]; then
  _dry "would run: patch -p1 < ${PATCH_FILE} in ${TARGET}"
else
  cd "${TARGET}"
  if patch -p1 --dry-run < "${PATCH_FILE}" >/dev/null 2>&1; then
    patch -p1 < "${PATCH_FILE}"
    _ok "patch applied cleanly"
  else
    _fail "patch did not apply cleanly. Source version may have diverged from ${BASE_VERSION}."
  fi
fi

# ── Step 5: Install dependencies ──────────────────────────────────────────────
echo "Step 5: Install dependencies"
if [[ $DRY_RUN -eq 1 ]]; then
  _dry "would run: bun install in ${TARGET}"
else
  cd "${TARGET}"
  bun install --frozen-lockfile 2>/dev/null || bun install
  _ok "dependencies installed"
fi

# ── Step 6: Build ────────────────────────────────────────────────────────────
echo "Step 6: Build"
if [[ $DRY_RUN -eq 1 ]]; then
  _dry "would run: bun run build in ${TARGET}"
else
  cd "${TARGET}"
  bun run build
  if [[ ! -f "${TARGET}/dist/cli.js" ]]; then
    _fail "build completed but dist/cli.js not found"
  fi
  _ok "built: ${TARGET}/dist/cli.js"
fi

# ── Step 7: Write env file ────────────────────────────────────────────────────
echo "Step 7: Write port config"
ENV_FILE="${TARGET}/.meridiana.env"
if [[ $DRY_RUN -eq 1 ]]; then
  _dry "would write: ${ENV_FILE} with MERIDIAN_PORT=${PORT}"
else
  cat > "${ENV_FILE}" << EOF
# MeridianA proxy configuration
# Source this file before starting the proxy, or set these variables in your
# OpenClaw service definition.
#
# Base: ${BASE_PKG}@${BASE_VERSION} + OpenClaw patch
# Patch: patches/meridiana-openclaw.patch (from openclaw-agent-memory-infra)

MERIDIAN_PORT=${PORT}
MERIDIAN_HOST=127.0.0.1
# MERIDIAN_PASSTHROUGH=0   # Set to 1 to enable tool passthrough (not recommended)
EOF
  _ok "env file written: ${ENV_FILE}"
fi

# ── Summary and next steps ────────────────────────────────────────────────────
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
echo "  1. Authenticate Claude Max account (run once per machine):"
echo "       node ${TARGET}/dist/cli.js profile add"
echo "     Follow the browser OAuth prompt. Tokens are stored by meridian;"
echo "     do NOT copy tokens between machines."
echo ""
echo "  2. Start the proxy:"
echo "       MERIDIAN_PORT=${PORT} node ${TARGET}/dist/cli.js"
echo "     Or source the env file and start:"
echo "       source ${ENV_FILE} && node ${TARGET}/dist/cli.js"
echo ""
echo "  3. Configure OpenClaw model aliases (meridiana/* → port ${PORT})."
echo "     See docs/MERIDIANA_DEPENDENCY.md for alias configuration."
echo ""
echo "  4. Verify with a test call through the proxy."
echo ""
echo "  AUTH COMMAND: node ${TARGET}/dist/cli.js profile add"
echo ""
exit 0
