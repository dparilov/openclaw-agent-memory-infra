# MeridianA / OpenClaw Runtime Dependency

## Overview

The `openclaw-agent-memory-infra` project is developed and maintained alongside a live
MeridianA/OpenClaw agent installation. This document records what the infra project depends on
from that runtime, so the setup can be reproduced on a clean instance.

## Runtime Environment

| Component | Role | Notes |
|-----------|------|-------|
| `~/.openclaw/agents/` | JSONL transcript store | archive-batch-v2.py reads from here |
| `~/.openclaw/workspace/ops/` | Default progress-file directory | `archive-progress-<id>-v2.json` stored here |
| `~/.openclaw/workspace/skills/` | Local skill registration directory | `archive-context/SKILL.md` and `read-context/SKILL.md` must be here |
| Pyrogram userbot (`userbot.session`) | Live Telegram read via `read-topic.py` | Separate from transcript reading; requires session file |
| OpenClaw skill YAML frontmatter | Skill discovery | Skills without frontmatter `description:` are silently ignored |

## Skills Registered in `~/.openclaw/workspace/skills/`

These skills were created/modified as part of this infra project and must exist on the target instance:

### `archive-context/SKILL.md`
- **What it does:** Wraps `archive-batch-v2.py` for Telegram chat invocation
- **Requires:** `name:` and `description:` in YAML frontmatter (otherwise OpenClaw ignores it)
- **Fix applied 2026-04-27:** Added frontmatter — previously had none, causing silent registration failure

### `read-context/SKILL.md`
- **What it does:** Reads OpenClaw session history for context restoration
- **Requires:** `sessions_history` and `sessions_list` tools in agent toolset

## Script Dependencies

### `archive-batch-v2.py`
- **Path:** `scripts/context_access/archive-batch-v2.py`
- **Runtime deps:** Python 3.10+, stdlib only (no pip packages)
- **Reads:** `~/.openclaw/agents/*/sessions/*-topic-<id>.jsonl` and `.jsonl.reset.*`
- **Writes:** `~/.openclaw/workspace/ops/archive-progress-<id>-v2.json` (only on `--mark-done`/`--reset`)
- **Topic resolution:** Scans session files for `topic_name` metadata; falls back to numeric ID

### `read-topic.py` (in `~/.openclaw/workspace/ops/`)
- **Not part of this repo**, but referenced in memory as a fallback
- Requires Pyrogram userbot session at `~/.openclaw/workspace/ops/userbot.session`
- Can hit Telegram flood-wait and SQLite lock — use only when transcript read is insufficient

### `read-full-transcript.py` / `read-session-transcript.py` (in `~/.openclaw/workspace/ops/`)
- **Not part of this repo**, but used by `read-context` skill
- Reads JSONL transcripts directly; no network required

## Known Issues and Workarounds

### MeridianA "Forwarding to client for execution"
Some OpenClaw topics running under MeridianA/claude-opus-4-7 intercept tool calls with
`Forwarding to client for execution` errors. This prevents `exec`/`Bash` from running scripts.

**Workaround:** Run scripts from a non-MeridianA session (e.g., default Claude provider topic,
or host shell directly).

**Affected topics:** Varies; infra topic 15222 has shown this behavior.

### Skill `skillsSnapshot` Staleness
OpenClaw snapshots available skills at session start. A new skill registered after the snapshot
will not be available until `/new` is called in that topic.

**Fix:** After registering or modifying a skill, run `/new` in the target topic.

## Reproducibility Checklist

To set up on a clean MeridianA/OpenClaw instance:

1. Clone this repo to `/home/<user>/projects/openclaw-agent-memory-infra`
2. Copy `skills/archive-context/SKILL.md` → `~/.openclaw/workspace/skills/archive-context/SKILL.md`
   - Verify YAML frontmatter contains `name:` and `description:`
3. Verify `openclaw skills check` shows `archive-context` as eligible
4. Run `/new` in any topic where you want to use the skill
5. Test: `/archive-context <topic_id> --status`

No pip installs required. Python 3.10+ stdlib is sufficient for all scripts in this repo.
