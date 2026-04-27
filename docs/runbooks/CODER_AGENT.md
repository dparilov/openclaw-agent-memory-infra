# Runbook: Coder Agent

> Standard operating procedure for an agent doing implementation work
> on a project with openclaw memory infrastructure.

---

## Session Start

1. **Load project context:**
   ```
   /read-context
   ```
   This reads `.agent/AGENT_CONTEXT.md` + relevant `memory/topic-<id>.md` files.

2. **Check memory staleness** — if header shows `last-write` > 7 days ago:
   ```bash
   python3 .../archive-batch-v2.py <topic-id> --status
   ```
   Run a fresh archive pass before starting work if stale.

3. **Note the current session UUID** (available in `$OPENCLAW_SESSION_ID` or generate one):
   ```bash
   SESSION_ID="coder-$(date +%Y%m%d-%H%M%S)"
   ```

---

## During Session

- Refer to `memory/topic-<id>.md` for known decisions, constraints, prior art.
- Do NOT re-ask the user for facts already in memory.
- If you discover a fact that contradicts memory, note it but continue — it will
  be conflict-detected during archive. Do not edit memory files manually.
- If you need live Telegram context not in session files:
  ```bash
  python3 .../read-topic.py <topic-id> --limit 100 --since-id <last-known-id>
  ```

---

## Session End

1. **Archive what was learned:**
   ```bash
   python3 .../archive-batch-v2.py <topic-id> \
     --write \
     --session-id $SESSION_ID \
     --auto-mark-done
   ```

2. **Verify write:**
   ```bash
   python3 .../archive-batch-v2.py <topic-id> --status
   ```
   Confirm `last-write` timestamp updated.

3. **If handing off to Reviewer agent**, create handoff note (see `HANDOFF_TEMPLATE.md`).

---

## Skip Archive If

- Session was purely exploratory (no decisions made, no code written)
- Facts were already archived in a prior run with same `SESSION_ID`
- No topic-relevant content was discussed

---

## Error Handling

| Error | Action |
|-------|--------|
| `no session files found for topic X` | Check topic ID; may need `--status` to verify |
| `Idempotency skip` | Normal — session already archived, no action |
| `⚠️ CONFLICT` in memory | Expected; reader uses most recent entry |
| Archive script blocked | Run manually in host shell; see `SKILL_VOCABULARY.md` |
