# Handoff Dispatch Protocol

Documents the automation layer for CODER/REVIEWER collaboration: converting `.agent/handoffs/ACTIVE.md` state into Telegram trigger messages sent via a Pyrogram user session.

> **Status:** Protocol and config docs only. Runtime implementation (dispatcher script) comes in a future PR.

---

## 1. Core principle

`.agent/handoffs/ACTIVE.md` is the **source of truth**.

The Telegram dispatch message is only a **wake trigger**. It does not carry the full task or review content. The receiving agent must read `ACTIVE.md` after receiving the trigger.

---

## 2. Transport

Use a **Pyrogram user session**, not a Telegram Bot API bot.

**Reason:**
- OpenClaw reads operator/user messages but may ignore bot messages.
- Dispatch messages sent from a trusted Telegram user session are treated as normal user messages.
- A dedicated service user is preferable to using the human's personal account.

> Configure OpenClaw Telegram channel policy so the dispatcher user is treated as a trusted/allowed sender.

If using the human's user session, document the operational risk and keep session files local (never committed).

---

## 3. Dispatch events

| `ACTIVE.md` state | Destination | Trigger message |
|---|---|---|
| `to_role: CODER`, `status: ready_for_implementation` | coder topic | `Read ACTIVE handoff and implement the task.` |
| `to_role: CODER`, `status: changes_requested` | coder topic | `Read ACTIVE handoff and fix reviewer blockers only.` |
| `to_role: REVIEWER`, `status: ready_for_review` | reviewer topic | `Read ACTIVE handoff and review the implementation.` |
| `to_role: HUMAN`, `status: approved` | human/reviewer topic | `APPROVED. Human may merge after final checks.` |

See [HANDOFF_DISPATCH_MESSAGES.md](HANDOFF_DISPATCH_MESSAGES.md) for full message templates and format rules.

---

## 4. Human approval rules

### 4a. First handoff for a new task

When REVIEWER/approver has discussed a new task with the human but no first CODER handoff has been sent yet:

- REVIEWER **must wait for explicit human instruction**, for example:
  - `Ок, отправляй handoff кодеру.`
  - `Send handoff to coder.`

After receiving instruction, REVIEWER:

1. Creates or updates `ACTIVE.md`.
2. Sets `status: ready_for_implementation`.
3. Sets `to_role: CODER`.
4. Persists the handoff.
5. Dispatches CODER trigger via Pyrogram.

### 4b. Review feedback after CODER work

When REVIEWER is already reviewing a CODER implementation and finds blockers:

- REVIEWER does **not** ask the human again.
- REVIEWER automatically:
  1. Updates `ACTIVE.md`.
  2. Fills `## Reviewer report`.
  3. Sets `status: changes_requested`.
  4. Sets `to_role: CODER`.
  5. Dispatches CODER trigger via Pyrogram.

### 4c. Approval

If REVIEWER approves:

1. Sets `status: approved`.
2. Sets `to_role: HUMAN`.
3. Dispatches human/reviewer notification if configured.
4. Does **not** merge automatically.

---

## 5. CODER dispatch rules

CODER automatically dispatches REVIEWER when it finishes implementation. CODER does not ask the human whether to send the review handoff.

CODER must:

1. Update `ACTIVE.md`.
2. Fill `## Coder implementation report`.
3. Set `status: ready_for_review`.
4. Set `to_role: REVIEWER`.
5. Fill `branch:` and `pr:` if applicable.
6. Dispatch REVIEWER trigger via Pyrogram.

---

## 6. Idempotency

Add optional dispatch metadata to `ACTIVE.md` frontmatter:

```yaml
dispatch:
  last_status: ""
  last_to_role: ""
  dispatched_at: ""
  transport: ""
  telegram_chat_id: ""
  telegram_topic_id: ""
  telegram_message_id: ""
```

Rules:

- Dispatcher must **not** send a duplicate trigger if:
  - `dispatch.last_status == status` **and** `dispatch.last_to_role == to_role`
- Dispatcher may send again only if:
  - `status` or `to_role` changed, **or**
  - `--force` is used (future runtime implementation).
- Dispatch metadata is optional in ACTIVE.md now; it will be required when the dispatcher script is implemented.

---

## 7. Human command examples

### First task handoff from approver/reviewer

Human to REVIEWER:

```
Ок, отправляй handoff кодеру.
```

or:

```
Send handoff to coder.
```

Expected REVIEWER behavior: create/update `ACTIVE.md`, then dispatch CODER trigger.

### Trigger messages received by agents

| Recipient | Message |
|-----------|---------|
| CODER (new task) | `Read ACTIVE handoff and implement the task.` |
| CODER (fix requested) | `Read ACTIVE handoff and fix reviewer blockers only.` |
| REVIEWER | `Read ACTIVE handoff and review the implementation.` |
| HUMAN | `APPROVED. Human may merge after final checks.` |

---

## 8. Non-goals (PR54)

This PR documents the protocol only. The following are explicitly deferred:

- Runtime Python dispatcher script
- Scheduler or polling
- Queue or database
- Multi-active-task support
- Auto-merge
- Telegram Bot transport
- OpenClaw config mutation
- Secrets in repo
- Changes to ASSISTANT DM mode

---

## 9. Next implementation PR (PR55)

PR55 will add:

- `scripts/handoff-dispatch.py`
- Tests
- Pyrogram transport
- Dry-run mode
- Idempotency enforcement
- Config parsing from `.agent/config.yaml`
- Dispatch metadata update in `ACTIVE.md`

---

## Related docs

| Doc | Purpose |
|-----|---------|
| [ACTIVE_HANDOFF_PROTOCOL.md](ACTIVE_HANDOFF_PROTOCOL.md) | Full ACTIVE.md lifecycle |
| [HANDOFF_DISPATCH_CONFIG.md](HANDOFF_DISPATCH_CONFIG.md) | Config reference for dispatcher |
| [HANDOFF_DISPATCH_MESSAGES.md](HANDOFF_DISPATCH_MESSAGES.md) | Message templates and format rules |
