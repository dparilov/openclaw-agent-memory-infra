# Skill Invocation Vocabulary

> When to call which memory skill — decision guide for agents and humans.

---

## Overview

Three skills form the memory pipeline:

| Skill | Command | Purpose |
|-------|---------|---------|
| **archive-context** | `/archive-context` | Extract facts from current session → write to topic memory file |
| **read-context** | `/read-context` | Restore full context from memory + transcripts before starting work |
| **read-topic** | `read-topic.py <topic-id>` | Fetch latest known state of a specific topic (person, project, thread) |

---

## `/archive-context` — When to Call

### ✅ Call at end of any meaningful work session

**Trigger conditions:**
- Session produced decisions, code, or conclusions not yet in memory
- About to hand off work to another agent or resume later
- Memory file is >7 days stale (check `<!-- last-write: -->` header)
- Session touched a known topic (person, project, thread with `topic-<id>.md`)

**Do NOT call if:**
- Session was purely read-only / exploratory with no conclusions
- Facts already archived in a prior run with same `--session-id`
- Nothing meaningful was established beyond what's in existing memory

**Typical invocation (agent):**
```bash
python scripts/context_access/archive-batch-v2.py <topic-id> \
  --write \
  --session-id <session-uuid> \
  --auto-mark-done
```

---

## `/read-context` — When to Call

### ✅ Call at the START of a session when prior context matters

**Trigger conditions:**
- Resuming work on a project after >1 day gap
- Starting a task that references a person or project with known history
- Onboarding to an existing codebase/thread — avoid re-asking known facts
- Another agent hands off a task with a topic ID

**Do NOT call if:**
- Starting completely fresh work with no relevant prior state
- Memory file was already loaded in this session
- Task is self-contained and doesn't depend on history

**What it returns:**
- Content of `memory/topic-<id>.md` (most recent facts, conflict-resolved by recency)
- Summary of relevant transcript excerpts if memory is stale
- Staleness indicator (days since last archive)

---

## `read-topic.py` — When to Call

### ✅ Call when you need focused state of ONE specific entity

```bash
python scripts/context_access/read-topic.py <topic-name-or-id>
```

**Trigger conditions:**
- Need current known state of a person (`dima`, `alex`, etc.)
- Need latest status of a project thread
- Pre-flight check before writing a message to someone
- Verifying last known decision before making a related decision

**Do NOT call if:**
- Need full session context restoration → use `/read-context` instead
- Topic ID unknown → resolve first via topic name lookup

**Output format (write-pipeline compatible):**
```markdown
## Facts — <ISO-8601 date>

- <fact 1>
- <fact 2>
```
This format feeds directly into `archive-batch-v2.py --batch` for downstream archiving.

---

## Decision Tree

```
Starting a session?
├─ Has prior context on this topic? → /read-context
└─ No prior context needed → start directly

During a session, need specific entity state?
└─ → read-topic.py <id>

Ending a session?
├─ Produced meaningful facts/decisions? → /archive-context
└─ Read-only session → skip
```

---

## Chaining Example

```bash
# 1. Start: restore context for project "telemost"
/read-context  # reads memory/topic-7301.md

# ... do work ...

# 2. Mid-session: check specific person's state
python read-topic.py dima

# ... more work ...

# 3. End: archive what was learned
/archive-context  # appends new facts to memory/topic-7301.md
```

---

## Topic ID Resolution

Topic IDs are Telegram chat/channel IDs. Use name aliases for convenience:

```bash
python read-topic.py telemost     # → resolves to 7301
python read-topic.py dima         # → resolves to numeric ID
python read-topic.py 7301         # → numeric ID directly
```

Name aliases are defined in `~/.openclaw/agents/` directory structure.

---

## Staleness Policy

| Age of last archive | Action |
|---------------------|--------|
| < 1 day | Memory file sufficient |
| 1–7 days | Use memory file; transcript supplement optional |
| > 7 days | Mandatory transcript scan before relying on memory file |
| No memory file | Run `/read-context` + `/archive-context` to bootstrap |

Staleness is visible in the memory file header:
```
<!-- last-batch: 3 | last-write: 2026-04-27T14:30:00 | batches: 3 -->
```

---

## Error Handling

| Error | Cause | Fix |
|-------|-------|-----|
| `Topic not found` | Name not in resolver | Use numeric ID directly |
| `Idempotency skip` | Same `--session-id` already archived | Normal — no action needed |
| `⚠️ CONFLICT` in memory file | Contradicting facts detected | Reader uses most recent; compaction in Phase 3 |
| `No transcript found` | Session too old or purged | Fall back to memory file only |
| Pyrogram `FloodWait` | Too many rapid reads | Retry with exponential backoff (see `PYROGRAM_FLOOD_WAIT.md`) |
