# Fallback Order: Context Access

## Overview

When an agent needs historical context for a topic, it should attempt sources in
the following order, from fastest/most-reliable to slowest/most-expensive.

---

## Order

### 1. Memory file — `<project>/.agent/memory/topic-<id>.md`

**Use when:** The topic has been previously archived and a memory file exists.

**How:** Read the file directly. It contains pre-extracted, deduplicated facts
organised by batch with timestamps. Conflicts are annotated with ⚠️ CONFLICT;
resolve by recency (newer entry wins).

**Pros:** Instant, no network, compact, agent-friendly format.  
**Cons:** Only as current as the last `--write` run; may lag behind live activity.

**Tool:** `Read` / `mcp__oc__read` on the memory file path, or a dedicated
`/read-context` skill invocation.

---

### 2. OpenClaw session transcripts — `~/.openclaw/agents/*/sessions/`

**Use when:** Memory file is absent or stale (last-write > N days ago) and the
topic has active OpenClaw sessions.

**How:** Run `archive-batch-v2.py <topic_id> --batch <n>` to read deduplicated
transcript batches directly from JSONL files. No network required.

**Pros:** No network, covers full session history, deduplication built-in.  
**Cons:** Raw conversation format (not pre-extracted facts); agent must extract
facts itself; can be slow for large topics (72+ batches for telemost).

**Tool:** `archive-batch-v2.py` via `/archive-context` skill or direct Bash call.

---

### 3. Telegram live read — Pyrogram userbot

**Use when:** Transcript files are absent or incomplete (e.g. topic predates the
current OpenClaw installation) and live Telegram messages are needed.

**How:** Run `read-topic.py <topic_id>` via Pyrogram userbot session. Reads
messages directly from Telegram API.

**Pros:** Covers full Telegram history regardless of OpenClaw session coverage.  
**Cons:** Requires live network + authenticated userbot session; subject to
Telegram flood-wait and SQLite lock (see `docs/PYROGRAM_FLOOD_WAIT.md` when
written); slower than transcript read; not available in isolated agent sessions.

**Tool:** `read-topic.py` in `~/.openclaw/workspace/ops/` (not part of this repo).

---

## Decision tree

```
Need context for topic T?
  │
  ├─ memory/topic-T.md exists and last-write < 7 days?
  │    └─ YES → use memory file (source 1)
  │
  ├─ OpenClaw JSONL sessions exist for topic T?
  │    └─ YES → run archive-batch-v2.py (source 2)
  │         └─ after reading: run --write to update memory file
  │
  └─ fallback → Pyrogram live read (source 3)
       └─ after reading: extract facts and --write to memory file
```

---

## Staleness threshold

The suggested threshold for "stale memory file" is **7 days**. Adjust per
project: a fast-moving development topic may need daily archiving, while a
dormant project may be fine with weekly.

Check with: `grep "last-write" <memory-file>`

---

## Notes

- Sources 2 and 3 both produce raw conversation; the agent must extract facts
  and write them with `--write` to keep the memory file current.
- Source 1 is the only source suitable for use in an isolated/sandboxed session
  with no network or filesystem access outside the project repo.
- Telegram/session history/OpenClaw transcripts are **evidence, not truth** —
  the memory file (after human review) is the canonical source of truth per the
  Source of Truth Model in `README.md`.
