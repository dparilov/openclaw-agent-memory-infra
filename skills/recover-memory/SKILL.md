---
name: recover-memory
description: Ultimate memory restoration skill. Runs a 4-step reality check → audit → archive → load cycle over the full L0–L4 memory stack for a given topic.
---

# recover-memory

Superscript over the entire memory stack. Use when context may be stale, missing,
or when starting work on a topic after a significant gap.

Primary invocation:
```
/recover-memory <topic_id|topic_name>
```

---

## When to Use

### ✅ Call when:
- Starting work on a topic after >7 days gap
- Memory file is missing or shows stale `last-write` header
- Agent is unsure whether it has full project context
- User explicitly asks: "восстанови память", "recover memory", "check your context"
- After a session crash or interrupted archive run
- Handing off work to another agent (receiver should call this first)

### ❌ Do NOT call if:
- Memory was just loaded this session (< 1 day since last-write)
- Topic is new with no history — use bootstrap instead
- Already ran `/recover-memory` successfully this session

---

## 4-Step Protocol (MANDATORY — execute in order, never skip)

### Step 1: REALITY CHECK

Read the memory file header:
```bash
head -5 .agent/memory/topic-<id>.md 2>/dev/null || echo "FILE_MISSING"
```

Parse `last-write` from `<!-- last-batch: N | last-write: TIMESTAMP | ... -->`.

**Decision:**
- File missing → STALE → proceed to Step 2
- `last-write` > 7 days ago → STALE → proceed to Step 2  
- `last-write` ≤ 7 days → proceed to Step 4 directly (load only)

**Always proceed to Step 2** regardless of Step 1 result — audit is mandatory.

---

### Step 2: AUDIT

Run both checks in parallel:

```bash
# Check unprocessed session batches
python3 /path/to/archive-batch-v2.py <topic-id> --status

# Check for new Pyrogram content since last archive
python3 /path/to/read-topic.py <topic-id> --since-id <last-pyrogram-id> --limit 50
```

Where `last-pyrogram-id` is read from memory file header
(`<!-- ... | last-pyrogram-id: XXXXXX | ... -->`).
If not present, use `--since-id 0` (read all).

**Decision:**
- Unprocessed batches > 0 → archive needed
- Pyrogram returned messages → archive needed
- Both empty → skip Step 3, proceed to Step 4

---

### Step 3: ARCHIVE (only if needed)

```bash
SESSION_ID="recover-$(date +%Y%m%d-%H%M%S)"

# Archive unprocessed session batches
python3 /path/to/archive-batch-v2.py <topic-id> \
  --write \
  --session-id $SESSION_ID \
  --auto-mark-done

# If new Pyrogram content exists:
python3 /path/to/read-topic.py <topic-id> --batch-format --since-id <last-id> \
  | <LLM fact extraction> \
  | python3 /path/to/archive-batch-v2.py <topic-id> --write --session-id $SESSION_ID-pyrogram
```

**On failure:**
- Report exact error verbatim
- Do NOT proceed to Step 4 as if archive succeeded
- Report: "Partial recovery — archive step failed: <error>"

---

### Step 4: LOAD

```
/read-context
```

Read the updated memory file (L2 working memory + L4 canonical docs).
Skip L0 raw archive (audit log only, too voluminous).

**Final report (mandatory):**
```
Memory recovery complete.
  Topic:      <topic-id> (<topic-name>)
  Last write: <timestamp>
  Facts:      ~N bullets in memory file
  Status:     [fresh | recovered | partial]
  Action:     [no archive needed | archived N facts | archive failed: <error>]
```

---

## Absolute Rules

1. **Always run all 4 steps in order** — never skip audit (Step 2) even if Step 1 is green
2. **Never fabricate recovery status** — run actual scripts; if blocked, report it
3. **Never claim "memory current" without running Step 4** (actual /read-context)
4. **Idempotent** — safe to call multiple times in a session
5. **If tool execution is blocked**, respond with:
   ```
   [blocked] recover-memory could not run — tool execution unavailable.
   Run manually:
     python3 .../archive-batch-v2.py <topic-id> --status
     python3 .../read-topic.py <topic-id> --since-id <last-id>
   ```
6. **Partial recovery is valid** — if Step 3 fails but Step 4 loads existing memory,
   report as "partial" — do not claim full recovery

---

## Environment Variables

| Var | Default | Description |
|-----|---------|-------------|
| `OPENCLAW_AGENTS` | `~/.openclaw/agents` | Session files location |
| `PYROGRAM_SESSION` | auto-detect | Pyrogram userbot session |
| `OPENCLAW_MEMORY_DIR` | `.agent/memory` | Memory files directory |

---

## Integration with Agent Templates

In `.agent-template/AGENT_CONTEXT.md`, the mandatory memory protocol requires:

```
IF memory staleness > 7 days → run /recover-memory before any task work
IF /recover-memory fails → report to user; do not proceed as if memory is current
```

Agents must treat this as a system-level, non-negotiable rule.
