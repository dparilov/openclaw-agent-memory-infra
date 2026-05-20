# Handoff Dispatch Messages

Trigger message templates for the handoff dispatcher.

---

## 1. Message format rules

- Messages must be **short** — one sentence.
- Messages must not contain the full task spec, PR diff, or review report.
- Messages are wake triggers only. The receiving agent reads `.agent/handoffs/ACTIVE.md` for full context.
- Messages must be stable enough for agents to recognize them as dispatch triggers.

---

## 2. Canonical trigger messages

| Event | Recipient | Message |
|-------|-----------|---------|
| New task ready for implementation | CODER | `Read ACTIVE handoff and implement the task.` |
| Review blockers returned to coder | CODER | `Read ACTIVE handoff and fix reviewer blockers only.` |
| Implementation ready for review | REVIEWER | `Read ACTIVE handoff and review the implementation.` |
| Implementation approved | HUMAN | `APPROVED. Human may merge after final checks.` |

These messages correspond to the `handoff_dispatch.messages` keys in `.agent/config.yaml`.

---

## 3. Message delivery

Messages are sent to the appropriate Telegram forum thread topic:

| Recipient | Config key | Default behavior |
|-----------|-----------|-----------------|
| CODER | `telegram.topics.coder` | Sent to CODER agent topic |
| REVIEWER | `telegram.topics.reviewer` | Sent to REVIEWER agent topic |
| HUMAN | `telegram.topics.human` | Sent to human/approver topic |

The dispatcher does not broadcast. Each trigger goes to exactly one topic.

---

## 4. Agent behavior on trigger receipt

When an agent receives a dispatch trigger:

1. Read `.agent/handoffs/ACTIVE.md`.
2. Verify the `to_role` field matches the current agent role.
3. Verify the `status` field matches the expected state (see table below).
4. Proceed with the role-specific action.

| Trigger received | Expected `to_role` | Expected `status` | Action |
|-----------------|-------------------|-------------------|--------|
| `Read ACTIVE handoff and implement the task.` | `CODER` | `ready_for_implementation` | Implement task |
| `Read ACTIVE handoff and fix reviewer blockers only.` | `CODER` | `changes_requested` | Fix blockers only |
| `Read ACTIVE handoff and review the implementation.` | `REVIEWER` | `ready_for_review` | Review PR/branch |
| `APPROVED. Human may merge after final checks.` | `HUMAN` | `approved` | Verify and merge |

If `to_role` or `status` does not match, do not proceed. Report the mismatch and wait for human clarification.

---

## 5. Out-of-scope message types

The following are **not** dispatch trigger messages:

- Task spec discussions (stay in conversation)
- PR comments (handled via GitHub PR review flow)
- Architecture decisions (stay in memory/docs)
- Status updates (report inline in conversation)

Dispatch triggers only route work between CODER, REVIEWER, and HUMAN via `ACTIVE.md`.
