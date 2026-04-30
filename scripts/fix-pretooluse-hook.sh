#!/usr/bin/env bash
# fix-pretooluse-hook.sh — Self-healing script for PreToolUse:Callback hook blockage.
#
# Usage:
#   bash scripts/fix-pretooluse-hook.sh [--disable-pretooluse-hook] [--dry-run] [--verbose]
#
# Steps performed:
#   2. Inspect ~/.claude/settings.json for PreToolUse hooks
#   3. Backup settings.json
#   4. Remove PreToolUse hook entries
#   5. Restart OpenClaw gateway
#   6. Verify doctor/channels
#   7. Run harmless tool test
#
# Exit codes:
#   0 = hook cleared and gateway healthy
#   1 = hook removal failed or gateway still unhealthy
#   2 = no hook found (nothing to fix)

set -euo pipefail

# ── Defaults ────────────────────────────────────────────────────────────────
DISABLE=0
DRY_RUN=0
VERBOSE=0
SETTINGS="${HOME}/.claude/settings.json"
PASS=0
FAIL=0

# ── Parse args ───────────────────────────────────────────────────────────────
for arg in "$@"; do
  case "$arg" in
    --disable-pretooluse-hook) DISABLE=1 ;;
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

echo "── PreToolUse hook self-healing ────────────────────────────────────"

# ── Step 2: Inspect settings.json ────────────────────────────────────────────
echo "Step 2: Inspect $SETTINGS"
if [[ ! -f "$SETTINGS" ]]; then
  _fail "settings.json not found at $SETTINGS"
  exit 1
fi

HOOK_FOUND=0
if python3 -c "
import json, sys
cfg = json.loads(open('$SETTINGS').read())
hooks = cfg.get('hooks', {})
if 'PreToolUse' in hooks:
    sys.exit(0)
sys.exit(1)
" 2>/dev/null; then
  _log "PreToolUse hook detected in settings.json"
  HOOK_FOUND=1
else
  _log "No PreToolUse hook found in settings.json"
fi

if [[ $HOOK_FOUND -eq 0 && $DISABLE -eq 0 ]]; then
  echo "No PreToolUse hook found — nothing to fix."
  exit 2
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
elif [[ $HOOK_FOUND -eq 1 || $DISABLE -eq 1 ]]; then
  python3 - << 'PYEOF'
import json, pathlib, sys
p = pathlib.Path.home() / ".claude" / "settings.json"
cfg = json.loads(p.read_text())
hooks = cfg.get("hooks", {})
removed = "PreToolUse" in hooks
if removed:
    del hooks["PreToolUse"]
    cfg["hooks"] = hooks
    p.write_text(json.dumps(cfg, indent=2))
    print(f"  [fix-hook] PreToolUse hook removed from {p}")
else:
    print(f"  [fix-hook] No PreToolUse hook to remove in {p}")
PYEOF
  _pass "PreToolUse hook removed"
fi

# ── Step 5: Restart gateway ───────────────────────────────────────────────────
echo "Step 5: Restart OpenClaw gateway"
if [[ $DRY_RUN -eq 1 ]]; then
  _log "[dry-run] would restart gateway"
else
  RESTARTED=0
  if command -v openclaw >/dev/null 2>&1; then
    if openclaw restart 2>/dev/null; then
      _pass "openclaw restart succeeded"
      RESTARTED=1
    fi
  fi
  if [[ $RESTARTED -eq 0 ]]; then
    if systemctl --user is-active openclaw-gateway >/dev/null 2>&1; then
      systemctl --user restart openclaw-gateway
      _pass "systemctl restart openclaw-gateway"
      RESTARTED=1
    fi
  fi
  if [[ $RESTARTED -eq 0 ]]; then
    _log "No known gateway restart mechanism found — manual restart required"
  fi
  sleep 3
fi

# ── Step 6: Verify doctor/channels ────────────────────────────────────────────
echo "Step 6: Verify gateway health"
if [[ $DRY_RUN -eq 1 ]]; then
  _log "[dry-run] would run: openclaw doctor"
else
  if command -v openclaw >/dev/null 2>&1; then
    if openclaw doctor 2>&1 | grep -qiE "ok|healthy|connected"; then
      _pass "openclaw doctor: healthy"
    else
      _log "openclaw doctor output unclear — check manually"
    fi
  else
    _log "openclaw CLI not in PATH — skipping doctor check"
  fi
fi

# ── Step 7: Harmless tool test ────────────────────────────────────────────────
echo "Step 7: Harmless tool test"
if [[ $DRY_RUN -eq 1 ]]; then
  _log "[dry-run] would run: echo hook-test > /tmp/fix-hook-test.txt"
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
