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
#   --test, --smoke-test                 Verify setup without live Telegram
#   --require-telegram                   Promote pyrogram absence from WARN to FAIL
#   -h|--help                            Show this help

set -euo pipefail

PYTHON="${PYTHON:-python3}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ── Portable realpath (macOS lacks GNU coreutils) ─────────────────────────────
_realpath() {
  if command -v realpath >/dev/null 2>&1; then
    realpath -- "$1"
  else
    "$PYTHON" -c "import os, sys; print(os.path.realpath(sys.argv[1]))" -- "$1"
  fi
}

usage() {
  cat <<'USAGE'
Usage: bash setup.sh --target <dir> [options]

Options:
  --target <dir>                       Target project directory (required)
  --topic-id <id>                      Telegram topic ID (seeds memory file, optional)
  --install-scripts copy|symlink|none  Install scripts to .agent/tools/context_access/ (default: none)
  --dry-run                            Print planned actions, create nothing
  --force                              Overwrite existing files
  --test, --smoke-test                 Verify setup without live Telegram
  --require-telegram                   Promote pyrogram absence from WARN to FAIL
  -h|--help                            Show this help
USAGE
}

# ── Defaults ──────────────────────────────────────────────────────────────────
TARGET=""
TOPIC_ID=""
INSTALL_SCRIPTS="none"
DRY_RUN=0
FORCE=0
SMOKE_TEST=0
REQUIRE_TELEGRAM=0

# ── Parse args ────────────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
  case "$1" in
    --target)             TARGET="$2";          shift 2 ;;
    --topic-id)           TOPIC_ID="$2";        shift 2 ;;
    --install-scripts)    INSTALL_SCRIPTS="$2"; shift 2 ;;
    --dry-run)            DRY_RUN=1;            shift   ;;
    --force)              FORCE=1;              shift   ;;
    --test|--smoke-test)  SMOKE_TEST=1;         shift   ;;
    --require-telegram)   REQUIRE_TELEGRAM=1;   shift   ;;
    -h|--help)            usage; exit 0 ;;
    *)                    echo "Unknown option: $1" >&2; usage >&2; exit 1 ;;
  esac
done

# ── Require --target ──────────────────────────────────────────────────────────
if [[ -z "$TARGET" ]]; then
  echo "Error: --target <dir> is required." >&2
  usage >&2
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

# Write content from stdin to $1.
# Skips if file exists and --force not set (dry-run: prints intent).
# Returns 0 if written/would-write, 1 if skipped.
write_file() {
  local dst="$1"
  local content
  content="$(cat)"
  if [[ -f "$dst" && $FORCE -eq 0 ]]; then
    [[ $DRY_RUN -eq 1 ]] && echo "[dry-run] skip (exists) $dst"
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
make_dir "$TARGET/.agent/memory/.locks"
make_dir "$TARGET/.agent/.locks"
make_dir "$TARGET/.agent/checkpoints"
make_dir "$TARGET/.agent/tasks"
make_dir "$TARGET/.agent/reviews"
make_dir "$TARGET/.agent/decisions"
make_dir "$TARGET/.agent/runbooks"
make_dir "$TARGET/.agent/handoffs"
make_dir "$TARGET/.agent/tools/context_access"

# .gitkeep so git tracks otherwise-empty dirs
if [[ $DRY_RUN -eq 0 ]]; then
  for d in raw candidates promoted wiki .locks; do
    touch "$TARGET/.agent/memory/$d/.gitkeep"
  done
  touch "$TARGET/.agent/.locks/.gitkeep"
fi

# ── Mandatory templates (skip if file exists and no --force) ──────────────────

write_file "$TARGET/.agent/AGENT_CONTEXT.md" <<'_T_'
# Agent Context

## Project Overview
<!-- Describe the project purpose, tech stack, key architecture decisions -->

## Entity Table
<!-- List key entities: services, databases, external APIs, people, etc. -->

| Entity | Type | Notes |
|--------|------|-------|

## Active Topic IDs
<!-- Map topic names to Telegram topic IDs -->

| Topic Name | Chat ID | Thread ID | Description |
|-----------|---------|-----------|-------------|

## Important Invariants
<!-- Rules/constraints the agent must always respect -->
_T_

write_file "$TARGET/.agent/memory/README.md" <<'_T_'
# Memory System

## Layers

| Dir | Layer | Description |
|-----|-------|-------------|
| raw/ | L0 | Audit logs — auto-managed |
| candidates/ | L1 | YAML extraction candidates — auto-managed |
| working/ | L2 | Active working memory — agent-maintained |
| promoted/ | L3 | Promoted facts — stable |
| reports/ | — | Pending reviews and contradictions |
| wiki/ | L3 | Built knowledge vault (run build-wiki.py) |

## Working Memory Files
- `current-state.md` — What is happening right now
- `active-decisions.md` — Decisions in flight
- `known-issues.md` — Known bugs/blockers
- `unresolved-questions.md` — Open questions
- `glossary.md` — Project-specific terms
- `agent-operating-context.md` — Agent instructions and context
_T_

write_file "$TARGET/.agent/memory/working/current-state.md" <<'_T_'
# Current State

_Last updated: —_

## In Progress
<!-- What is currently being worked on -->

## Recent Completions
<!-- Recently finished items -->

## Blockers
<!-- Anything blocking progress -->
_T_

write_file "$TARGET/.agent/memory/working/active-decisions.md" <<'_T_'
# Active Decisions

_Last updated: —_

<!-- Decisions that have been made but not yet fully implemented or validated -->

| Decision | Status | Owner | Notes |
|----------|--------|-------|-------|
_T_

write_file "$TARGET/.agent/memory/working/known-issues.md" <<'_T_'
# Known Issues

_Last updated: —_

<!-- Known bugs, blockers, or technical debt items -->

| Issue | Severity | Status | Notes |
|-------|----------|--------|-------|
_T_

write_file "$TARGET/.agent/memory/working/unresolved-questions.md" <<'_T_'
# Unresolved Questions

_Last updated: —_

<!-- Questions that need answers before work can proceed -->

| Question | Context | Priority |
|----------|---------|----------|
_T_

write_file "$TARGET/.agent/memory/working/glossary.md" <<'_T_'
# Glossary

_Last updated: —_

<!-- Project-specific terms, acronyms, and their definitions -->

| Term | Definition |
|------|-----------|
_T_

write_file "$TARGET/.agent/memory/working/agent-operating-context.md" <<'_T_'
# Agent Operating Context

## Purpose
<!-- What this agent is for and what it should optimise for -->

## Workflow
<!-- Step-by-step process the agent should follow -->

## Constraints
<!-- Hard rules the agent must not violate -->

## Session Startup Checklist
<!-- What the agent should check at the start of each session -->
- [ ] Read AGENT_CONTEXT.md
- [ ] Read memory/working/current-state.md
- [ ] Read memory/working/active-decisions.md
_T_

write_file "$TARGET/.agent/memory/reports/pending-approval.md" <<'_T_'
# Pending Approval

_Last updated: —_

<!-- Memory promotions or decisions waiting for human approval -->

| Item | Type | Proposed | Reason |
|------|------|----------|--------|
_T_

write_file "$TARGET/.agent/memory/reports/contradictions.md" <<'_T_'
# Contradictions

_Last updated: —_

<!-- Facts in working memory that contradict each other or known state -->

| Claim A | Claim B | Source | Status |
|---------|---------|--------|--------|
_T_

write_file "$TARGET/.agent/memory/reports/stale-claims.md" <<'_T_'
# Stale Claims

_Last updated: —_

<!-- Claims in memory that may be outdated and need verification -->

| Claim | Added | Reason for Review |
|-------|-------|-------------------|
_T_

write_file "$TARGET/.agent/tasks/README.md" <<'_T_'
# Tasks

Each task is a markdown file describing a discrete unit of work.
Use TASK_TEMPLATE.md as the starting point.

Naming convention: `YYYY-MM-DD-<slug>.md`
_T_

write_file "$TARGET/.agent/tasks/TASK_TEMPLATE.md" <<'_T_'
# Task: <title>

**Created:** YYYY-MM-DD
**Status:** draft | active | blocked | done
**Owner:** —

## Goal
<!-- What needs to be accomplished -->

## Acceptance Criteria
- [ ] ...

## Notes
<!-- Context, links, related decisions -->
_T_

write_file "$TARGET/.agent/reviews/README.md" <<'_T_'
# Reviews

Code, design, and document reviews.
Use REVIEW_TEMPLATE.md as the starting point.

Naming convention: `YYYY-MM-DD-<slug>.md`
_T_

write_file "$TARGET/.agent/reviews/REVIEW_TEMPLATE.md" <<'_T_'
# Review: <subject>

**Date:** YYYY-MM-DD
**Reviewer:** —
**Status:** pending | approved | changes-requested

## Summary
<!-- What was reviewed and the overall verdict -->

## Issues Found
| Severity | Location | Description |
|----------|----------|-------------|

## Decision
<!-- Approved / Changes Required / Rejected + rationale -->
_T_

write_file "$TARGET/.agent/decisions/README.md" <<'_T_'
# Decisions (ADRs)

Architecture Decision Records. Each file captures one decision.
Use ADR_CANDIDATE_TEMPLATE.md as the starting point.

Naming convention: `YYYY-MM-DD-<slug>.md`
_T_

write_file "$TARGET/.agent/decisions/ADR_CANDIDATE_TEMPLATE.md" <<'_T_'
# ADR: <title>

**Date:** YYYY-MM-DD
**Status:** candidate | accepted | superseded | rejected

## Context
<!-- What situation led to this decision -->

## Decision
<!-- What was decided -->

## Consequences
<!-- What changes as a result -->

## Alternatives Considered
<!-- What else was evaluated and why it was not chosen -->
_T_

write_file "$TARGET/.agent/runbooks/README.md" <<'_T_'
# Runbooks

Step-by-step operational procedures. Each runbook is a markdown file.

Naming convention: `<operation-name>.md`
_T_

write_file "$TARGET/.agent/handoffs/README.md" <<'_T_'
# Handoffs

Session handoff documents. Each file records the state at the end of a session,
enabling the next agent to resume without loss of context.

Naming convention: `YYYY-MM-DD-HHMMSS-<slug>.md`
_T_

# ── Runbook templates ────────────────────────────────────────────────────────

write_file "$TARGET/.agent/runbooks/coder-agent.md" <<'_T_'
# Runbook: Coder Agent

## Role
Implements features, fixes bugs, writes tests. Follows task files in `.agent/tasks/`.

## Session Startup
1. Read `.agent/AGENT_CONTEXT.md`
2. Read `.agent/memory/working/current-state.md`
3. Read `.agent/memory/working/active-decisions.md`
4. Check `.agent/tasks/` for active tasks

## Workflow
1. Pick the next `active` task from `.agent/tasks/`
2. Implement per acceptance criteria
3. Write/update tests
4. Update `current-state.md` on completion
5. Create handoff in `.agent/handoffs/` before ending session

## Constraints
- Never commit without passing tests
- Never modify `.agent/memory/promoted/` directly
_T_

write_file "$TARGET/.agent/runbooks/reviewer-agent.md" <<'_T_'
# Runbook: Reviewer Agent

## Role
Reviews code, decisions, and documents. Produces review files in `.agent/reviews/`.

## Session Startup
1. Read `.agent/AGENT_CONTEXT.md`
2. Check `.agent/reviews/` for pending reviews

## Workflow
1. Read the subject (PR diff, ADR, design doc)
2. Fill in `REVIEW_TEMPLATE.md` — copy as `YYYY-MM-DD-<slug>.md`
3. Set status: `approved` | `changes-requested`
4. Notify owner via task or handoff

## Constraints
- One review file per subject
- Never approve without checking acceptance criteria
_T_

write_file "$TARGET/.agent/runbooks/infra-agent.md" <<'_T_'
# Runbook: Infra Agent

## Role
Manages infrastructure, deployments, and operational runbooks.

## Session Startup
1. Read `.agent/AGENT_CONTEXT.md`
2. Read `.agent/memory/working/known-issues.md`

## Workflow
1. Follow the relevant runbook in `.agent/runbooks/`
2. Document any deviations as a new decision in `.agent/decisions/`
3. Update `current-state.md` after significant ops

## Constraints
- Never apply destructive ops without a dry-run first
- Record all infra changes in `active-decisions.md`
_T_

write_file "$TARGET/.agent/runbooks/memory-extraction-policy.md" <<'_T_'
# Policy: Memory Extraction

## When to Extract
- After each significant session turn that produces a durable fact
- When a decision is confirmed
- When a bug is resolved

## What to Extract
- Facts: stable, verifiable claims (e.g. "service X listens on port 8080")
- Decisions: architecture or process choices
- Constraints: hard rules that must not be violated

## How to Extract
1. Run `archive-batch-v2.py` to write raw batch to `.agent/memory/`
2. Run `manage-candidates.py extract` to produce YAML candidates
3. Review candidates in `.agent/memory/candidates/`

## What NOT to Extract
- Transient state (in-progress work)
- Opinions without evidence
- Duplicates already in `promoted/`
_T_

write_file "$TARGET/.agent/runbooks/memory-promotion-policy.md" <<'_T_'
# Policy: Memory Promotion

## Auto-promotion Criteria
A candidate may be auto-promoted when ALL of the following hold:
- `risk: low`
- `confidence: medium` or higher
- No high-risk keywords (secret, token, password, production, gdpr)
- `status: needs-approval` is NOT set

## Manual Approval Required
- `risk: medium` or `high`
- Type: `architecture-decision`, `constraint`, `process-rule`
- Any claim containing high-risk keywords

## Process
1. `manage-candidates.py promote --auto` — promotes qualifying candidates
2. Review `.agent/memory/reports/pending-approval.md` for manual items
3. After human approval, run `manage-candidates.py promote --id <id>`

## After Promotion
- Promoted facts land in `.agent/memory/promoted/`
- Run `build-wiki.py` to rebuild `.agent/memory/wiki/`
_T_

write_file "$TARGET/.agent/runbooks/session-history-usage-policy.md" <<'_T_'
# Policy: Session History Usage

## Purpose
Session history (Telegram batches, agent transcripts) is raw input for memory extraction.
It must NOT be treated as ground truth for decisions.

## Allowed Uses
- Source evidence for candidate extraction
- Reconstructing context when working memory is incomplete
- Auditing past decisions

## Prohibited Uses
- Do not copy-paste history into `promoted/` directly
- Do not use history as a substitute for reading `AGENT_CONTEXT.md`
- Do not re-process already-archived batches (check `last-batch` header)

## Batch Tracking
Each memory file carries `<!-- last-batch: N -->` in its header.
Always pass `--batch` or let `archive-batch-v2.py` infer the next batch number.
_T_

write_file "$TARGET/.agent/runbooks/task-handoff-policy.md" <<'_T_'
# Policy: Task Handoff

## When to Create a Handoff
- Before ending a session with incomplete work
- When handing a task to a different agent role
- After a blocking issue is discovered

## Handoff File Format
Location: `.agent/handoffs/YYYY-MM-DD-HHMMSS-<slug>.md`

Required sections:
- **Status** — what was done, what remains
- **Blockers** — anything preventing continuation
- **Next Steps** — ordered list for the receiving agent
- **Context Refs** — files the next agent must read

## On Session Start
Check `.agent/handoffs/` for the most recent file before reading anything else.
_T_

write_file "$TARGET/.agent/runbooks/review-handoff-policy.md" <<'_T_'
# Policy: Review Handoff

## When to Create a Review Handoff
- When a review requires domain knowledge the current agent lacks
- When a review is blocked pending external information
- When routing a review to a human approver

## Handoff File Format
Location: `.agent/reviews/YYYY-MM-DD-<slug>.md` (status: `pending`)

Required sections:
- **Subject** — what is under review
- **Blocking Reason** — why the review cannot proceed
- **Required Input** — what information or approval is needed
- **Owner** — who should pick this up

## Resolution
Once unblocked, update the review file status to `approved` or `changes-requested`.
_T_

write_file "$TARGET/.agent/runbooks/portability-policy.md" <<'_T_'
# Policy: Portability

## Scope
All scripts and tooling in this repository must run without modification on:
- Linux (Ubuntu 20.04+)
- macOS (12+, both Intel and Apple Silicon)
- Any environment where Python 3.9+ and Bash 4+ are available

## Rules
1. **No GNU-only coreutils** — use Python fallbacks for `realpath`, `date -d`, etc.
2. **No hardcoded paths** — use `SCRIPT_DIR`, `TARGET`, env vars
3. **No global installs** — scripts install to `.agent/tools/`, never to `~/.local/bin`
4. **Python stdlib only** — no third-party pip dependencies in core scripts
5. **POSIX-safe heredocs** — avoid nested heredocs; use Python writes for complex templates

## Testing Portability
Run `bash -n setup.sh` and `python3 -m py_compile scripts/context_access/*.py`
before every commit.
_T_

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
        echo "  [dry-run] cp $(basename "$rel")"
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
        echo "  [dry-run] ln -sf $(basename "$rel")"
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
# ── B4: non-live smoke test ───────────────────────────────────────────────────
if [[ $SMOKE_TEST -eq 1 ]]; then
  _SP=0; _SW=0; _SF=0

  _smoke_pass() { printf '  PASS  %s\n' "$1"; _SP=$((_SP+1)); }
  _smoke_warn() { printf '  WARN  %s\n' "$1"; _SW=$((_SW+1)); }
  _smoke_fail() { printf '  FAIL  %s\n' "$1"; _SF=$((_SF+1)); }

  echo "── Smoke test: $TARGET ──────────────────────────────────────────"

  # Python >= 3.10
  _pyver=$("$PYTHON" --version 2>&1 || echo 'not found')
  if "$PYTHON" -c "import sys; assert sys.version_info >= (3,10)" 2>/dev/null; then
    _smoke_pass "Python >= 3.10"
  else
    _smoke_fail "Python >= 3.10 (got: $_pyver)"
  fi

  # PyYAML
  if "$PYTHON" -c "import yaml" 2>/dev/null; then
    _smoke_pass "PyYAML importable"
  else
    _smoke_fail "PyYAML not importable (pip install pyyaml)"
  fi

  # .agent/ structure (7 required dirs)
  for _d in memory checkpoints tasks reviews decisions runbooks handoffs; do
    if [[ -d "$TARGET/.agent/$_d" ]]; then
      _smoke_pass ".agent/$_d/"
    else
      _smoke_fail ".agent/$_d/ missing"
    fi
  done

  # Tool --help (4 tools; installed copy takes priority, falls back to source)
  _TOOL_DIR="$TARGET/.agent/tools/context_access"
  for _tool in read-topic.py archive-batch-v2.py manage-candidates.py build-wiki.py; do
    _tp="$_TOOL_DIR/$_tool"
    if [[ ! -f "$_tp" ]]; then
      _tp="$SCRIPT_DIR/scripts/context_access/$_tool"
    fi
    if [[ -f "$_tp" ]] && "$PYTHON" "$_tp" --help >/dev/null 2>&1; then
      _smoke_pass "$_tool --help"
    else
      _smoke_fail "$_tool --help (not found or failed: $_tp)"
    fi
  done

  # pyrogram — WARN unless --require-telegram
  if "$PYTHON" -c "import pyrogram" 2>/dev/null; then
    _smoke_pass "pyrogram importable"
  elif [[ $REQUIRE_TELEGRAM -eq 1 ]]; then
    _smoke_fail "pyrogram not importable (pip install pyrogram)"
  else
    _smoke_warn "pyrogram not importable (Telegram features disabled)"
  fi

  # Claude Code CLI — optional
  if command -v claude >/dev/null 2>&1; then
    _smoke_pass "Claude Code CLI"
  else
    _smoke_warn "Claude Code CLI not found (optional)"
  fi

  echo "────────────────────────────────────────────────────────────────"
  printf '  PASS: %d  WARN: %d  FAIL: %d\n' "$_SP" "$_SW" "$_SF"
  if [[ $_SF -gt 0 ]]; then
    echo "Smoke test FAILED." >&2
    exit 1
  fi
  echo "Smoke test passed."
fi
