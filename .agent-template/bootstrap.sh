#!/usr/bin/env bash
# bootstrap.sh — Set up .agent/ memory structure in a project directory.
#
# Usage: bash .agent-template/bootstrap.sh [target-dir]
#   target-dir defaults to current working directory

set -euo pipefail

TARGET="${1:-.}"
AGENT_DIR="$TARGET/.agent"

if [ -d "$AGENT_DIR" ]; then
  echo "[bootstrap] .agent/ already exists at $AGENT_DIR — skipping"
  exit 0
fi

mkdir -p "$AGENT_DIR/memory"
touch "$AGENT_DIR/memory/.gitkeep"

# Copy template context file
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cp "$SCRIPT_DIR/AGENT_CONTEXT.md" "$AGENT_DIR/AGENT_CONTEXT.md"

echo "[bootstrap] Created .agent/ structure at $AGENT_DIR"
echo ""
echo "Next steps:"
echo "  1. Edit $AGENT_DIR/AGENT_CONTEXT.md — fill in project overview, entities, topic IDs"
echo "  2. Run initial archive:"
echo "     python3 /path/to/archive-batch-v2.py <topic-id> --write --session-id init-$(date +%Y%m%d)"
echo "  3. Commit .agent/ to your repo (memory/*.md files are living documents)"
