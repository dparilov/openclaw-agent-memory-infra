---
name: compact-memory
description: Semantic deduplication and compaction of a topic memory file. LLM pass that merges duplicates, resolves conflicts, and removes obsolete facts. Non-destructive — original preserved in L0 audit log.
---

# compact-memory

LLM-driven compaction of `memory/topic-<id>.md`. Reduces noise by merging
semantically duplicate facts, resolving ⚠️ CONFLICT markers, and removing
obsolete entries. Non-destructive: original content is preserved in the L0
audit log before any write.

Primary invocation:
```
/compact-memory <topic_id|topic_name>
```

---

## When to Use

### ✅ Call when:
- Memory file has accumulated >50 bullets with visible duplicates
- Multiple ⚠️ CONFLICT markers exist (> 3–5)
- File is getting unwieldy (>200 lines / >10KB)
- Before a major handoff — clean context for receiving agent
- Periodically as maintenance (monthly or when file crosses size threshold)

### ❌ Do NOT call if:
- Memory file has < 20 bullets (too small to benefit)
- File was compacted recently (check `last-compact` in header)
- Compaction would destroy important audit trail (check L0 first)

---

## 3-Step Protocol

### Step 1: PREPARE

```bash
python3 /path/to/archive-batch-v2.py <topic-id> \
  --compact \
  --memory-file .agent/memory/topic-<id>.md
```

This prints:
- Summary stats (bullet count, conflict count, size)
- Full memory file content formatted for LLM input
- Is **read-only** — no file modifications

Verify: file should have > 10 bullets to be worth compacting.

---

### Step 2: COMPACT (LLM pass)

Read the `--compact` output and apply these rules:

**Merge:** semantically equivalent facts → single canonical statement
```
Before:
  - Using append-only format to avoid conflicts
  - Memory writes are append-only (no overwrite)
After:
  - Memory file uses append-only writes to avoid concurrent conflicts
```

**Resolve conflicts:** ⚠️ CONFLICT pairs → keep most recent, explain resolution
```
Before:
  - Decided to use Blender for rendering (2026-03-01)
  - ⚠️ CONFLICT: Batch 0 указывал: ...decided on Unreal...
After:
  - Rendering: switched from Unreal to Blender (2026-03-01); prior decision superseded
```

**Drop obsolete:** facts explicitly superseded by newer entries
```
Before:
  - v1.2 is in development (2026-01-15)
  - v1.2 shipped (2026-02-01)
After:
  - v1.2 shipped 2026-02-01
```

**Preserve:** all facts with no clear duplicate/conflict/obsolete status.
When in doubt — keep.

**Output format:** plain bullet list, one fact per line, starting with `- `:
```
- <compacted fact 1>
- <compacted fact 2>
...
```

---

### Step 3: WRITE BACK

Write compacted facts using the standard pipeline:

```bash
# L0 audit log is written automatically before the write
python3 /path/to/archive-batch-v2.py <topic-id> \
  --write <compacted-facts-file> \
  --session-id "compact-$(date +%Y%m%d)" \
  --memory-file .agent/memory/topic-<id>.md \
  --auto-mark-done
```

Then **replace the old sections** with the compacted output:
- The `--write` appends a new batch section
- After write, manually (or via agent) remove the superseded batch sections,
  leaving only: the header comment + the new compacted batch section

**Update header** to record compaction:
```
<!-- last-batch: N | last-write: TIMESTAMP | batches: 0-N | last-compact: TIMESTAMP -->
```

---

## Absolute Rules

1. **Non-destructive:** L0 audit log is written by `--write` before any file mutation
2. **Preserve more, not less:** when uncertain whether a fact is duplicate → keep it
3. **Never invent facts:** compaction only reorganizes existing facts, never adds new ones
4. **Never remove timestamps:** keep date context even in merged facts
5. **Never compact L0:** audit log is immutable — only `topic-<id>.md` is compacted
6. **Report stats after compaction:**
   ```
   Compaction complete: N bullets → M bullets (K% reduction)
   Conflicts resolved: X | Duplicates merged: Y | Obsolete dropped: Z
   L0 audit entry written before write.
   ```

---

## Compaction Quality Checklist

Before writing back, verify:
- [ ] No facts were invented (only existing facts reorganized)
- [ ] All timestamps preserved or explicitly noted as approximated
- [ ] No ⚠️ CONFLICT markers remain unresolved
- [ ] Bullet count is lower than original
- [ ] Each bullet is still atomic (one fact per bullet)
- [ ] Compacted file still passes `MEMORY_EXTRACTION_POLICY.md` criteria

---

## Environment Variables

Same as `archive-context` skill — see `SKILL_VOCABULARY.md`.
