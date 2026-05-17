# Project Memory Extractor v1 — Quick Start

**Full command reference:** `docs/REFRESH_MEMORY_COMMANDS.md`

---

## What is this?

A minimal stdlib-only pipeline to archive topic/session context into Markdown
chunks and compile a working memory pack that agents load at startup.

No vector DB. No LLM API calls in scripts. No auto-commit. Explicit only.

---

## Prerequisites

- Python 3.10+ (no pip packages required for local modes)
- Target directory with `.agent/AGENT_CONTEXT.md`
- For Telegram mode: Pyrogram userbot session

---

## Step 1 — Bootstrap a new target

```bash
mkdir -p /path/to/project/.agent/memory/working

cat > /path/to/project/.agent/AGENT_CONTEXT.md <<'EOF'
# Agent Context — My Project

## Project Overview
TBD

## Active Topics
- topic-7301 — coder role
- topic-15222 — infra role

## Agent Behavior Notes
- Use working Markdown memory at startup.
- Do not read Telegram unless explicitly requested.
- Do not use vector DB / embeddings / memory-core for v1.
EOF
```

---

## Step 2 — Archive context (pick one source)

**Local Markdown file:**
```bash
python3 scripts/refresh-memory.py \
  --target /path/to/project \
  --topic 7301:coder \
  --input /path/to/context.md \
  --source-type markdown_export \
  --write
```

**Telegram bounded read** (explicit operator request only):
```bash
python3 scripts/refresh-memory.py \
  --target /path/to/project \
  --topic 7301:coder \
  --read-topic \
  --chat-id -1003596522926 \
  --limit 200 \
  --write
```

Review the report. Archive step must show `PASS`.

---

## Step 3 — Fill working memory

The compile step prints a context packet and extraction prompt to stdout.
Paste both into an agent (OpenClaw or Claude CLI) and ask it to fill the
`<!-- TODO -->` sections in `.agent/memory/working/*.md`.

Review the diff before committing.

---

## Step 4 — Recover at agent startup

```bash
python3 scripts/recover-memory.py \
  --target /path/to/project \
  --topic 7301 \
  --role coder
```

The agent reads `.agent/AGENT_CONTEXT.md` and `working/*.md` only —
no Telegram, no raw chunks, no vector DB.

---

## One-prompt agent guide

See the **"One-prompt usage guide for agents"** section in
`docs/REFRESH_MEMORY_COMMANDS.md` for a ready-to-paste prompt covering
the full dry-run → write → fill → verify cycle.

---

## What is NOT implemented in v1

```bash
# Future only — do not use:
--since-id / --until-id      # message id range
--since / --until            # date range
--full / --confirm-large-read  # full history
--topics <multi>             # multi-topic in one call
```

---

## Constraints (always apply)

- Single topic per invocation
- `--limit` required for Telegram mode (must be a positive integer)
- `--read-topic` never runs on startup or heartbeat — explicit only
- No LLM API calls inside scripts
- No auto-commit or auto-push
