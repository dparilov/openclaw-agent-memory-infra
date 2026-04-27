# Runbook: Reviewer Agent

> Standard operating procedure for an agent reviewing code or decisions
> on a project with openclaw memory infrastructure.

---

## Session Start

1. **Load context for the topic being reviewed:**
   ```
   /read-context
   ```

2. **Check who made the decisions** — read memory for relevant entity context:
   ```bash
   python3 .../read-topic.py <author-topic-id>
   ```
   This gives you prior known positions/constraints of the author.

3. **Review the handoff note** if provided (see `HANDOFF_TEMPLATE.md`).

---

## During Review

- Cross-reference decisions with `memory/topic-<id>.md` — flag if a decision
  contradicts a previously established constraint.
- Note any new facts discovered during review (will be archived at end).
- If a decision was already reviewed before, memory may contain prior review notes.

---

## Session End

1. **Archive review conclusions:**
   ```bash
   python3 .../archive-batch-v2.py <topic-id> \
     --write \
     --session-id "review-$(date +%Y%m%d-%H%M%S)" \
     --auto-mark-done
   ```

2. **Produce handoff note** back to Coder agent if changes requested.

---

## What Belongs in Memory After Review

✅ Archive:
- "Decision X was reviewed and approved on DATE"
- "Constraint Y was identified during review of PR Z"
- "Architecture approach A was rejected because B"

❌ Do NOT archive:
- Line-by-line code comments (too granular, volatile)
- Temporary WIP notes
- Duplicate facts already in memory

---

## Error Handling

Same as Coder Agent runbook.
