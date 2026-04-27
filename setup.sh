#!/usr/bin/env bash
# setup.sh — Bootstrap openclaw-agent-memory-infra in a project directory.
#
# Usage:
#   bash setup.sh [--target <dir>] [--topic-id <id>] [--agents-base <path>]
#
# Options:
#   --target <dir>        Project directory to set up (default: current directory)
#   --topic-id <id>       Telegram topic ID for initial archive (optional)
#   --agents-base <path>  Path to OpenClaw agents dir (default: ~/.openclaw/agents)
#   --dry-run             Show what would be done without making changes

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TARGET="."
TOPIC_ID=""
AGENTS_BASE="${HOME}/.openclaw/agents"
DRY_RUN=false
PYTHON="${PYTHON:-python3}"

# ── Parse args ────────────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
  case "$1" in
    --target)   TARGET="$2"; shift 2 ;;
    --topic-id) TOPIC_ID="$2"; shift 2 ;;
    --agents-base) AGENTS_BASE="$2"; shift 2 ;;
    --dry-run)  DRY_RUN=true; shift ;;
    -h|--help)
      echo "Usage: bash setup.sh [--target DIR] [--topic-id ID] [--agents-base PATH] [--dry-run]"
      exit 0 ;;
    *) echo "Unknown option: $1" >&2; exit 1 ;;
  esac
done

TARGET="$(realpath "$TARGET")"
AGENT_DIR="$TARGET/.agent"
MEMORY_DIR="$AGENT_DIR/memory"
SCRIPTS="$SCRIPT_DIR/scripts/context_access"

log() { echo "[setup] $*"; }
run() {
  if $DRY_RUN; then
    echo "[dry-run] $*"
  else
    "$@"
  fi
}

# ── Python check ──────────────────────────────────────────────────────────────
log "Checking Python..."
if ! command -v "$PYTHON" &>/dev/null; then
  echo "ERROR: python3 not found. Install Python 3.10+ first." >&2
  exit 1
fi
PY_VER=$("$PYTHON" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
log "Python $PY_VER found."

# Optional: check PyYAML for manage-candidates.py
if ! "$PYTHON" -c "import yaml" 2>/dev/null; then
  log "WARNING: PyYAML not found. manage-candidates.py will use fallback (no YAML parsing)."
  log "         Install with: pip install pyyaml"
fi

# ── Create .agent/ structure ──────────────────────────────────────────────────
log "Setting up .agent/ structure in $TARGET ..."

run mkdir -p "$MEMORY_DIR/raw"
run mkdir -p "$MEMORY_DIR/candidates"
run mkdir -p "$MEMORY_DIR/wiki"
run mkdir -p "$AGENT_DIR/handoffs"

# Copy AGENT_CONTEXT.md template
TEMPLATE="$SCRIPT_DIR/.agent-template/AGENT_CONTEXT.md"
CONTEXT_FILE="$AGENT_DIR/AGENT_CONTEXT.md"
if [[ -f "$TEMPLATE" ]]; then
  if [[ -f "$CONTEXT_FILE" ]]; then
    log "AGENT_CONTEXT.md already exists — skipping (no overwrite)"
  else
    run cp "$TEMPLATE" "$CONTEXT_FILE"
    log "Created $CONTEXT_FILE (fill in project details)"
  fi
fi

# .gitkeep placeholders
for d in raw candidates wiki; do
  if [[ ! -f "$MEMORY_DIR/$d/.gitkeep" ]]; then
    run touch "$MEMORY_DIR/$d/.gitkeep"
  fi
done

log ""
log "Structure created:"
log "  $AGENT_DIR/"
log "  ├── AGENT_CONTEXT.md      ← fill in project overview + entity table"
log "  └── memory/"
log "      ├── raw/              ← L0 audit logs (auto-managed)"
log "      ├── candidates/       ← L1 candidate YAML (auto-managed)"
log "      ├── wiki/             ← L3 knowledge vault (run build-wiki.py)"
log "      └── topic-<id>.md    ← L2 working memory (run archive-batch-v2.py)"

# ── Optional initial archive ──────────────────────────────────────────────────
if [[ -n "$TOPIC_ID" ]]; then
  log ""
  log "Running initial archive for topic $TOPIC_ID ..."
  ARCHIVE_SCRIPT="$SCRIPTS/archive-batch-v2.py"
  if [[ ! -f "$ARCHIVE_SCRIPT" ]]; then
    echo "ERROR: archive-batch-v2.py not found at $ARCHIVE_SCRIPT" >&2
    exit 1
  fi
  SESSION_ID="init-$(date +%Y%m%d-%H%M%S)"
  run "$PYTHON" "$ARCHIVE_SCRIPT" "$TOPIC_ID" --status --agents-base "$AGENTS_BASE"
  log ""
  log "Status shown above. To archive:"
  log "  python3 $ARCHIVE_SCRIPT $TOPIC_ID --write - --session-id $SESSION_ID --memory-dir $MEMORY_DIR --auto-mark-done"
fi

# ── .gitignore suggestion ─────────────────────────────────────────────────────
GITIGNORE="$TARGET/.gitignore"
if [[ -f "$GITIGNORE" ]] && ! grep -q ".agent/memory/raw/" "$GITIGNORE" 2>/dev/null; then
  log ""
  log "TIP: Add to $GITIGNORE to exclude audit logs (optional):"
  log "  .agent/memory/raw/*.log"
  log "  .agent/memory/wiki/WIKI_META.json"
fi

log ""
log "Setup complete."
log ""
log "Next steps:"
log "  1. Edit $CONTEXT_FILE — add project overview, entities, topic IDs"
log "  2. Archive a topic:"
log "       python3 $SCRIPTS/archive-batch-v2.py <topic-id> --status"
log "       python3 $SCRIPTS/archive-batch-v2.py <topic-id> --write - --session-id init --memory-dir $MEMORY_DIR"
log "  3. Build wiki:"
log "       python3 $SCRIPTS/build-wiki.py --memory-dir $MEMORY_DIR"
log "  4. Commit .agent/ to your repo"
