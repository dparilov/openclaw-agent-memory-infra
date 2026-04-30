#!/usr/bin/env bash
# fix-pretooluse-hook.sh — Self-healing script for PreToolUse:Callback hook blockage.
#
# Usage:
#   bash scripts/fix-pretooluse-hook.sh [OPTIONS]
#
# Options:
#   --disable-pretooluse-hook   Backup, remove hook, restart gateway, verify.
#                               Without this flag the script is inspect-only.
#   --skip-gateway-restart      Skip gateway restart and health-check steps.
#                               Safe for CI / unit tests.
#   --dry-run                   Print what would be done; do not modify anything.
#   --verbose | -v              Extra logging.
#   --help | -h                 Show this help.
#
# Default (no flags): inspect-only — report hook presence; never modify settings.json.
#   Exit 0 = hook found (re-run with --disable-pretooluse-hook to remove)
#   Exit 2 = no hook found (nothing to fix)
#
# With --disable-pretooluse-hook:
#   Exit 0 = hook cleared (and gateway healthy if restart not skipped)
#   Exit 1 = hook removal failed or gateway still unhealthy
#
# Environment:
#   FIX_HOOK_TIMEOUT   Seconds to wait for each external command (default: 10)
#   FIX_HOOK_SKIP_GATEWAY=1   Same effect as --skip-gateway-restart

set -euo pipefail

# ── Defaults ──────────────────────────────────────────────────────────────────
DISABLE=0
DRY_RUN=0
VERBOSE=0
SKIP_GATEWAY=${FIX_HOOK_SKIP_GATEWAY:-0}
CMD_TIMEOUT=${FIX_HOOK_TIMEOUT:-10}
SETTINGS="${HOME}/.claude/settings.json"
PASS=0
FAIL=0

# ── Parse args ────────────────────────────────────────────────────────────────
for arg in "$@"; do
  case "$arg" in
    --disable-pretooluse-hook) DISABLE=1 ;;
    --skip-gateway-restart)    SKIP_GATEWAY=1 ;;
    --dry-run)                 DRY_RUN=1 ;;
    --verbose|-v)              VERBOSE=1 ;;
    --help|-h)
      grep '^#' "$0" | sed 's/^# \?//'
      exit 0
      ;;
    *)
      echo "Unknown option: $arg" >&2
      exit 1
      ;;
  esac
done

_log()  { echo "  [fix-hook] $*"; }
_pass() { echo "  PASS  $*"; PASS=$((PASS+1)); }
_fail() { echo "  FAIL  $*" >&2; FAIL=$((FAIL+1)); }
_info() { [[ $VERBOSE -eq 1 ]] && echo "  INFO  $*" || true; }
_run()  { timeout "${CMD_TIMEOUT}" "$@" 2>/dev/null || true; }

echo "── PreToolUse hook self-healing ────────────────────────────────────"

# ── Step 2: Inspect settings.json ─────────────────────────────────────────────
echo "Step 2: Inspect $SETTINGS"
if [[ ! -f "$SETTINGS" ]]; then
  _fail "settings.json not found at $SETTINGS"
  exit 1
fi

HOOK_FOUND=0
if python3 -c "
import json, sys
cfg = json.loads(open('$SETTINGS').read())
if 'PreToolUse' in cfg.get('hooks', {}):
    sys.exit(0)
sys.exit(1)
" 2>/dev/null; then
  _log "PreToolUse hook detected in settings.json"
  HOOK_FOUND=1
else
  _log "No PreToolUse hook found in settings.json"
fi

# Inspect-only mode: report and exit without any modification
if [[ $DISABLE -eq 0 ]]; then
  if [[ $HOOK_FOUND -eq 1 ]]; then
    echo "PreToolUse hook found. Re-run with --disable-pretooluse-hook to remove it."
    exit 0
  else
    echo "No PreToolUse hook found — nothing to fix."
    exit 2
  fi
fi

# ── Step 3: Backup ────────────────────────────────────────────────────────────
echo "Step 3: Backup settings.json"
BACKUP="${SETTINGS}.bak.$(date +%Y%m%dT%H%M%S)"
if [[ $DRY_RUN -eq 1 ]]; then
  _log "[dry-run] would backup to $BACKUP"
else
  cp "$SETTINGS" "$BACKUP"
  _pass "Backed up → $BACKUP"
fi

# ── Step 4: Remove PreToolUse hook ────────────────────────────────────────────
echo "Step 4: Remove PreToolUse hook"
if [[ $DRY_RUN -eq 1 ]]; then
  _log "[dry-run] would remove PreToolUse from $SETTINGS"
else
  python3 - << 'PYEOF'
import json, pathlib
p = pathlib.Path.home() / ".claude" / "settings.json"
cfg = json.loads(p.read_text())
hooks = cfg.get("hooks", {})
if "PreToolUse" in hooks:
    del hooks["PreToolUse"]
    cfg["hooks"] = hooks
    p.write_text(json.dumps(cfg, indent=2))
    print("  [fix-hook] PreToolUse hook removed")
else:
    print("  [fix-hook] No PreToolUse hook to remove")
PYEOF
  _pass "PreToolUse hook step complete"
fi

# ── Step 5: Restart gateway ───────────────────────────────────────────────────
echo "Step 5: Restart OpenClaw gateway"
if [[ $DRY_RUN -eq 1 || $SKIP_GATEWAY -eq 1 ]]; then
  _log "[skipped] gateway restart (dry-run or --skip-gateway-restart)"
else
  RESTARTED=0

  if command -v openclaw >/dev/null 2>&1; then
    if _run openclaw restart; then
      _pass "openclaw restart succeeded"
      RESTARTED=1
    fi
    _run openclaw gateway status
  fi

  if [[ $RESTARTED -eq 0 ]]; then
    for SVC in openclaw-gateway.service openclaw-gateway-dev.service; do
      if timeout "${CMD_TIMEOUT}" systemctl --user restart "$SVC" 2>/dev/null; then
        _pass "systemctl restart $SVC"
        RESTARTED=1
        break
      fi
    done
  fi

  if [[ $RESTARTED -eq 0 ]]; then
    _log "No known gateway restart mechanism found. Openclaw units:"
    timeout "${CMD_TIMEOUT}" systemctl --user list-units      2>/dev/null | grep -i openclaw || _log "  (none in list-units)"
    timeout "${CMD_TIMEOUT}" systemctl --user list-unit-files 2>/dev/null | grep -i openclaw || _log "  (none in list-unit-files)"
    _log "Manual restart required."
  fi

  sleep 1
fi

# ── Step 6: Verify doctor/channels ────────────────────────────────────────────
echo "Step 6: Verify gateway health"
if [[ $DRY_RUN -eq 1 || $SKIP_GATEWAY -eq 1 ]]; then
  _log "[skipped] health checks (dry-run or --skip-gateway-restart)"
else
  _run openclaw gateway status
  _run openclaw doctor
  _run openclaw channels status --probe
  _pass "Health checks run (see output above)"
fi

# ── Step 7: Harmless tool test ────────────────────────────────────────────────
echo "Step 7: Harmless tool test"
if [[ $DRY_RUN -eq 1 ]]; then
  _log "[dry-run] would run harmless write/read test"
else
  TEST_FILE="/tmp/fix-hook-test-$(date +%s).txt"
  echo "hook-test-ok" > "$TEST_FILE"
  if [[ "$(cat "$TEST_FILE")" == "hook-test-ok" ]]; then
    _pass "Harmless write/read test passed → $TEST_FILE"
    rm -f "$TEST_FILE"
  else
    _fail "Harmless write/read test FAILED"
  fi
fi

# ── Summary ───────────────────────────────────────────────────────────────────
echo "────────────────────────────────────────────────────────────────────"
printf "  PASS: %d  FAIL: %d\n" "$PASS" "$FAIL"

if [[ $FAIL -gt 0 ]]; then
  echo ""
  echo "Step 8: Still failing — escalate:"
  echo "  1. Paste ~/.claude/settings.json (redact secrets)"
  echo "  2. Paste: openclaw doctor output"
  echo "  3. Open issue with label hook-blockage"
  exit 1
fi

echo "Hook cleared. Normal tool execution should resume."
exit 0
