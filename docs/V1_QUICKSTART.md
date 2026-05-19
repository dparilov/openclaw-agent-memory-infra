# Project Memory Extractor v1 — Quick Start

**Full command reference:** [docs/REFRESH_MEMORY_COMMANDS.md](REFRESH_MEMORY_COMMANDS.md)
**Installation:** [docs/INSTALL.md](INSTALL.md)
**Portability:** [docs/PORTABILITY.md](PORTABILITY.md)

---

## Prerequisites

- Python 3.10+ (stdlib only — no pip packages for local modes)
- Target directory with `.agent/AGENT_CONTEXT.md`
- Pyrogram userbot session for Telegram mode only

---

## Environment variables (optional, set once)

```bash
export PME_REPO="${PME_REPO:-$HOME/projects/openclaw-agent-memory-infra}"
export PROJECTS_ROOT="${PROJECTS_ROOT:-$HOME/projects}"
```

If not set, scripts default to `$HOME/projects/openclaw-agent-memory-infra`.

---

## Step 1 — Bootstrap a new target

```bash
mkdir -p "$PROJECTS_ROOT/<project-dir>/.agent/memory/working"

cat > "$PROJECTS_ROOT/<project-dir>/.agent/AGENT_CONTEXT.md" <<'EOF'
# Agent Context — My Project

## Project Overview
TBD

## Active Topics
- topic-<TOPIC_ID> — <ROLE> role

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
python3 "$PME_REPO/scripts/refresh-memory.py" \
  --target "$PROJECTS_ROOT/<project-dir>" \
  --topic <TOPIC_ID>:<ROLE> \
  --input /path/to/context.md \
  --source-type markdown_export \
  --write
```

**Telegram bounded read** (explicit operator request only):
```bash
# By message count
python3 "$PME_REPO/scripts/refresh-memory.py" \
  --target "$PROJECTS_ROOT/<project-dir>" \
  --topic <TOPIC_ID>:<ROLE> \
  --read-topic --chat-id <chat-id> \
  --limit 200 --write

# By message ID range
python3 "$PME_REPO/scripts/refresh-memory.py" \
  --target "$PROJECTS_ROOT/<project-dir>" \
  --topic <TOPIC_ID>:<ROLE> \
  --read-topic --chat-id <chat-id> \
  --since-id 15000 --until-id 16000 --write

# By date range
python3 "$PME_REPO/scripts/refresh-memory.py" \
  --target "$PROJECTS_ROOT/<project-dir>" \
  --topic <TOPIC_ID>:<ROLE> \
  --read-topic --chat-id <chat-id> \
  --since 2026-05-01 --until 2026-05-15 --write

# Full topic (requires confirmation)
python3 "$PME_REPO/scripts/refresh-memory.py" \
  --target "$PROJECTS_ROOT/<project-dir>" \
  --topic <TOPIC_ID>:<ROLE> \
  --read-topic --chat-id <chat-id> \
  --full --confirm-large-read --write
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
python3 "$PME_REPO/scripts/recover-memory.py" \
  --target "$PROJECTS_ROOT/<project-dir>" \
  --topic <TOPIC_ID> \
  --role <ROLE>
```

The agent reads `.agent/AGENT_CONTEXT.md` and `working/*.md` only —
no Telegram, no raw chunks, no vector DB.

---

## One-prompt agent guide

See the **"One-prompt usage guide for agents"** section in
[docs/REFRESH_MEMORY_COMMANDS.md](REFRESH_MEMORY_COMMANDS.md) for a
ready-to-paste prompt covering the full dry-run → write → fill → verify cycle.

---

## What is NOT implemented in v1

```bash
# Future only — do not use:
## What is NOT implemented in v1

The following flags are future-only. Do not use them in v1:

- `--since-id` / `--until-id` — message id range
- `--since` / `--until` — date range
- `--full` / `--confirm-large-read` — full history
- `--topics <multi>` — multi-topic in one call
```

---

## Constraints (always apply)

- Single topic per invocation
- `--limit` required for Telegram mode (positive integer)
- `--read-topic` never runs on startup or heartbeat — explicit only
- No LLM API calls inside scripts
- No auto-commit or auto-push
