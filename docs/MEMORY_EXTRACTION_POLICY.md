# Memory Extraction and Promotion Policy

> Defines WHAT facts to extract from sessions and WHEN to promote them
> to long-term memory in `memory/topic-<id>.md`.

---

## Principle

Memory files are **high-signal, low-noise**. They contain facts that:
- Remain true beyond the current session
- Would need to be re-established if lost
- Reduce re-work or re-asking in future sessions

The goal is not to log everything — it is to capture what a new agent would need
to be fully oriented for this project/person/topic.

---

## What to Extract

### ✅ Extract (promote to memory)

| Category | Examples |
|----------|---------|
| **Decisions** | "Decided to use X over Y because Z" |
| **Constraints** | "Cannot use library X due to license" |
| **Architecture** | "Service A communicates with B via gRPC, not REST" |
| **Preferences** | "Dima prefers short daily updates, not long reports" |
| **People / roles** | "Alex is the infra lead; Dima owns product decisions" |
| **Project state** | "v1.2 shipped on DATE; v1.3 target is END OF MONTH" |
| **Known blockers** | "Blocked on legal approval for feature Y since DATE" |
| **Resolved issues** | "Bug X was caused by Y and fixed in commit Z" |
| **Process rules** | "All PRs require review from Alex before merge" |

### ❌ Do NOT extract

| Category | Reason |
|----------|--------|
| Raw message transcripts | Too voluminous; use `read-topic.py` for live access |
| Temporary WIP notes | Volatile; will be stale immediately |
| Code snippets | Code lives in the repo, not in memory |
| Line-level review comments | Too granular; summarize the decision instead |
| Questions without answers | Not facts yet; archive the answer when known |
| Duplicate facts already in memory | Creates noise; idempotency check handles exact dupes but not paraphrases |

---

## Promotion Threshold

A fact should be promoted when it meets ALL of:

1. **Durability** — likely to still be true in 7+ days
2. **Relevance** — would change how a future agent behaves
3. **Non-obvious** — can't be inferred from the codebase or public docs alone
4. **Actionable** — knowing this fact changes a decision or saves time

When in doubt: **promote**. Phase 3 semantic dedup will compact over-extraction.
Under-extraction is harder to recover from.

---

## Granularity

Write facts at **decision level**, not implementation level:

```
✅ "Chose append-only memory format to avoid concurrent write conflicts (2026-04-26)"
❌ "Line 47 of archive-batch-v2.py has the append logic"
```

One fact per bullet. No compound facts:

```
✅ "Using topic-<id>.md as canonical memory file per MEMORY_OUTPUT_CONTRACT"
✅ "Archive writer uses session-ID for idempotency"
❌ "Using topic-<id>.md as canonical memory file with session-ID idempotency per contract"
```

---

## When to Promote (Timing)

| Trigger | Action |
|---------|--------|
| End of work session | Archive all facts established during session |
| Decision made that affects future work | Archive immediately (don't wait) |
| Constraint discovered that limits options | Archive immediately |
| Prior memory entry contradicted | Archive the correction (conflict detection will flag it) |
| Fact needed in 3+ sessions in a row | Already in memory — no action needed |
| Memory file >7 days stale + active topic | Run fresh archive pass |

---

## Conflict Handling

When a new fact contradicts an existing memory entry:

1. **Write the new fact** — append to memory as usual
2. The writer adds a `⚠️ CONFLICT` marker on the old entry
3. **Reader uses the most recent entry** (recency wins)
4. Do NOT delete old entries manually — they serve as audit trail
5. Phase 3 semantic compaction will resolve/merge conflicts automatically

---

## Promotion from Pyrogram Transcript

When using `read-topic.py --batch-format` output:

1. Agent reads the transcript
2. Agent extracts facts matching the criteria above
3. Facts are passed to `archive-batch-v2.py --write` as a new batch
4. The `last-pyrogram-id` in the header advances to prevent re-reading

Do NOT archive the raw transcript — only the extracted facts.

---

## Quality Check Before Archive

Before running `--write`, review the fact list:

- [ ] Each bullet is a single, atomic fact
- [ ] No code snippets
- [ ] No questions (only answers)
- [ ] No "maybe" or "probably" — only confirmed facts
- [ ] Each fact passes the durability + relevance test
- [ ] Timestamp is accurate (when was this established?)
