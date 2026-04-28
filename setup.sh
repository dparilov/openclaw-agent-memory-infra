#!/usr/bin/env bash
# setup.sh — Bootstrap .agent/ skeleton for a project using openclaw-agent-memory-infra tools.
#
# Usage:
#   bash setup.sh --target <dir> [options]
#
# Options:
#   --target <dir>                       Target project directory (required)
#   --topic-id <id>                      Telegram topic ID (seeds memory file, optional)
#   --install-scripts copy|symlink|none  Install scripts to .agent/tools/context_access/ (default: none)
#   --dry-run                            Print planned actions, create nothing
#   --force                              Overwrite existing files
#   -h|--help                            Show this help

set -euo pipefail

PYTHON="${PYTHON:-python3}"

# BASH_SOURCE[0] is the script itself even when sourced; more portable than $0
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ── Portable realpath (macOS lacks GNU coreutils) ─────────────────────────────
_realpath() {
  if command -v realpath >/dev/null 2>&1; then
    realpath -- "$1"
  else
    "$PYTHON" -c "import os, sys; print(os.path.realpath(sys.argv[1]))" -- "$1"
  fi
}

# ── Defaults ──────────────────────────────────────────────────────────────────
TARGET=""
TOPIC_ID=""
INSTALL_SCRIPTS="none"
DRY_RUN=0
FORCE=0

# ── Parse args ────────────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
  case "$1" in
    --target)             TARGET="$2";          shift 2 ;;
    --topic-id)           TOPIC_ID="$2";        shift 2 ;;
    --install-scripts)    INSTALL_SCRIPTS="$2"; shift 2 ;;
    --dry-run)            DRY_RUN=1;            shift   ;;
    --force)              FORCE=1;              shift   ;;
    -h|--help)
      sed -n '2,9p' "${BASH_SOURCE[0]}" | sed 's/^# \?//'
      exit 0 ;;
    *)
      echo "Unknown option: $1" >&2; exit 1 ;;
  esac
done

# ── Require --target ──────────────────────────────────────────────────────────
if [[ -z "$TARGET" ]]; then
  echo "Error: --target <dir> is required." >&2
  exit 1
fi

TARGET="$(_realpath "$TARGET")"

# ── Helpers ───────────────────────────────────────────────────────────────────
make_dir() {
  local d="$1"
  if [[ $DRY_RUN -eq 1 ]]; then
    echo "[dry-run] mkdir -p $d"
  else
    mkdir -p "$d"
  fi
}

# Write content from stdin to $1, honouring --force and --dry-run.
# Returns 0 if written/would-write, 1 if skipped.
write_file() {
  local dst="$1"
  local content
  content="$(cat)"
  if [[ -f "$dst" && $FORCE -eq 0 ]]; then
    [[ $DRY_RUN -eq 1 ]] && echo "[dry-run] skip (exists) $dst" || true
    return 1
  fi
  if [[ $DRY_RUN -eq 1 ]]; then
    echo "[dry-run] write $dst"
  else
    mkdir -p "$(dirname "$dst")"
    printf '%s\n' "$content" > "$dst"
  fi
}

echo "Bootstrap: $TARGET"

# ── B1: Full .agent/ directory structure ─────────────────────────────────────
make_dir "$TARGET/.agent/memory/raw"
make_dir "$TARGET/.agent/memory/candidates"
make_dir "$TARGET/.agent/memory/working"
make_dir "$TARGET/.agent/memory/promoted"
make_dir "$TARGET/.agent/memory/reports"
make_dir "$TARGET/.agent/memory/wiki"
make_dir "$TARGET/.agent/checkpoints"
make_dir "$TARGET/.agent/tasks"
make_dir "$TARGET/.agent/reviews"
make_dir "$TARGET/.agent/decisions"
make_dir "$TARGET/.agent/runbooks"
make_dir "$TARGET/.agent/handoffs"
make_dir "$TARGET/.agent/tools/context_access"
make_dir "$TARGET/.agent/.locks"

# .gitkeep so git tracks otherwise-empty dirs
if [[ $DRY_RUN -eq 0 ]]; then
  for d in raw candidates promoted wiki .locks; do
    touch "$TARGET/.agent/memory/$d/.gitkeep" 2>/dev/null || true
  done
fi

# Optional: seed topic memory file
if [[ -n "$TOPIC_ID" ]]; then
  MEM_FILE="$TARGET/.agent/memory/topic-${TOPIC_ID}.md"
  printf '# Memory: topic-%s\n\n<!-- last-batch: -1 | last-write: none | batches: none -->\n' \
    "$TOPIC_ID" | write_file "$MEM_FILE" || true
fi

# ── B2: Install scripts to .agent/tools/context_access/ ──────────────────────
# Never installs to ~/.local/bin or any other global path.
SCRIPTS_LIST=(
  "scripts/context_access/archive-batch-v2.py"
  "scripts/context_access/read-topic.py"
  "scripts/context_access/manage-candidates.py"
  "scripts/context_access/build-wiki.py"
  "scripts/context_access/io_utils.py"
)
TOOL_DIR="$TARGET/.agent/tools/context_access"

case "$INSTALL_SCRIPTS" in
  copy)
    echo "Installing scripts (copy) → $TOOL_DIR"
    for rel in "${SCRIPTS_LIST[@]}"; do
      src="$SCRIPT_DIR/$rel"
      dst="$TOOL_DIR/$(basename "$rel")"
      if [[ ! -f "$src" ]]; then
        echo "  WARN: not found: $src"
        continue
      fi
      if [[ $DRY_RUN -eq 1 ]]; then
        echo "  [dry-run] cp $src"
      else
        cp "$src" "$dst"
        chmod +x "$dst"
        echo "  copied: $(basename "$rel")"
      fi
    done
    ;;
  symlink)
    echo "Installing scripts (symlink — dev-only, non-portable) → $TOOL_DIR"
    for rel in "${SCRIPTS_LIST[@]}"; do
      src="$SCRIPT_DIR/$rel"
      dst="$TOOL_DIR/$(basename "$rel")"
      if [[ ! -f "$src" ]]; then
        echo "  WARN: not found: $src"
        continue
      fi
      if [[ $DRY_RUN -eq 1 ]]; then
        echo "  [dry-run] ln -sf $src"
      else
        ln -sf "$src" "$dst"
        echo "  linked: $(basename "$rel")"
      fi
    done
    ;;
  none)
    : # no-op — scripts run directly from repo
    ;;
  *)
    echo "Error: --install-scripts must be copy, symlink, or none" >&2
    exit 1
    ;;
esac

echo "Done. Target: $TARGET"
