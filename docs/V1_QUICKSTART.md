# V1 Quickstart — Project Memory Extractor

The v1 flow is file-first and explicit. No Telegram, no vector DB, no LLM API spend required.

```text
explicit context → refresh-memory → reviewed working/*.md → recover-memory
```

---

## Prerequisites

- Python 3.10+
- `scripts/archive-context.py`, `scripts/compile-working-memory.py`,
  `scripts/refresh-memory.py`, `scripts/recover-memory.py` present on `main`
- A target project directory with `.agent/AGENT_CONTEXT.md`

No external packages required (stdlib only).

---

## Step 1 — Prepare your target

```bash
mkdir -p /path/to/project/.agent
cat > /path/to/project/.agent/AGENT_CONTEXT.md <<'EOF'
# Agent Context — My Project

## Project Overview
<brief description>

## Active Topics
- topic-7301 — coder role

## Agent Behavior Notes
- Use working Markdown memory at startup.
- Do not read Telegram without explicit operator request.
EOF
```

---

## Step 2 — Prepare your context input

Collect recent session context, notes, or exported markdown into a single file:

```bash
cat > /tmp/context.md <<'EOF'
## Current Objective
<what the team is working on>

## Current State
<bullet facts about the project state>

## Known Issues
<known problems and blockers>

## Do Not Do
<constraints and forbidden actions>

## Next Useful Actions
<what a new agent should do first>
EOF
```

---

## Step 3 — Dry-run (verify, write nothing)

```bash
python3 scripts/refresh-memory.py \
  --target /path/to/project \
  --topic 7301:coder \
  --input /tmp/context.md \
  --source-type markdown_export
```

Check the report: `Input processed`, `Archive step: PASS`, `Compile step: PASS`,
`Files written: none`.

---

## Step 4 — Write

```bash
python3 scripts/refresh-memory.py \
  --target /path/to/project \
  --topic 7301:coder \
  --input /tmp/context.md \
  --source-type markdown_export \
  --write
```

---

## Step 5 — Verify files created

```bash
find /path/to/project/.agent/memory -type f | sort
```

Expected:
```
.agent/memory/raw/topic-7301/chunk-0001.md
.agent/memory/working/agent-brief.md
.agent/memory/working/current-state.md
.agent/memory/working/known-issues.md
```

The working files contain `<!-- TODO -->` placeholders. An LLM agent fills them
using the context packet and extraction prompt printed by compile-working-memory.

---

## Step 6 — Recover memory at agent startup

```bash
python3 scripts/recover-memory.py \
  --target /path/to/project \
  --topic 7301 \
  --role coder
```

The output lists loaded files, startup context, blockers, and next actions.

---

## Source types

| `--source-type` | Use when |
|-----------------|----------|
| `markdown_export` | Exported Markdown session notes, context dumps |
| `session_jsonl` | OpenClaw JSONL session transcripts |
| `operator_note` | Short operator-written notes |

---

## What v1 intentionally does NOT use

- Telegram / Pyrogram (`--read-topic` not yet wired)
- OpenAI embeddings
- Vector DB
- OpenClaw memory-core
- Wiki build (`docs/AUTOMATIC_INITIAL_INDEXING.md` — legacy)
- Candidate promotion (`docs/CANDIDATE_SCHEMA.md` — legacy)
- Phase/gate wizard (`docs/SETUP_WIZARD_FLOW.md` — legacy)

---

## Options reference

### `refresh-memory.py`

| Flag | Default | Description |
|------|---------|-------------|
| `--target` | required | Path to project root |
| `--topic` | required | `<id>:<role>` e.g. `7301:coder` |
| `--input` | required | Path to local input file |
| `--source-type` | required | `session_jsonl` \| `markdown_export` \| `operator_note` |
| `--chunk-size` | 200 | Lines per raw chunk |
| `--notes` | — | Optional operator notes file |
| `--write` | false | Write files (default: dry-run) |

### `recover-memory.py`

| Flag | Default | Description |
|------|---------|-------------|
| `--target` | required | Path to project root |
| `--topic` | — | Optional topic ID filter |
| `--role` | — | Optional role filter |
| `--format` | markdown | `markdown` \| `text` |
