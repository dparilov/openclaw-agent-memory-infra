# Handoff Dispatch Config

Configuration reference for the handoff dispatcher.

Config file location: `<target>/.agent/config.yaml`

> **Status:** Config schema documented here. Runtime config parsing is implemented in a future PR (PR55).

---

## 1. Example config

```yaml
handoff_dispatch:
  enabled: true
  transport: pyrogram_user

  telegram:
    chat_id: -1003596522926
    topics:
      coder: 7301
      reviewer: 13350
      human: 15222

  pyrogram:
    session_name: handoff_dispatcher
    workdir: ~/.pyrogram
    # actual auth/session files are local secrets and must not be committed

  trusted_sender:
    type: user_session
    note: "OpenClaw must be configured to accept messages from this Telegram user."

  messages:
    ready_for_implementation: "Read ACTIVE handoff and implement the task."
    changes_requested: "Read ACTIVE handoff and fix reviewer blockers only."
    ready_for_review: "Read ACTIVE handoff and review the implementation."
    approved: "APPROVED. Human may merge after final checks."
```

---

## 2. Field reference

### `handoff_dispatch`

| Field | Type | Description |
|-------|------|-------------|
| `enabled` | bool | Enable or disable dispatch. Set `false` to disable without removing config. |
| `transport` | string | Transport to use. Only `pyrogram_user` is documented for MVP. |

### `handoff_dispatch.telegram`

| Field | Type | Description |
|-------|------|-------------|
| `chat_id` | int | Telegram group chat id (negative for groups). |
| `topics.coder` | int | Forum thread topic id for the CODER agent. |
| `topics.reviewer` | int | Forum thread topic id for the REVIEWER agent. |
| `topics.human` | int | Forum thread topic id for the human/approver. |

### `handoff_dispatch.pyrogram`

| Field | Type | Description |
|-------|------|-------------|
| `session_name` | string | Name of the Pyrogram session file (without `.session` extension). |
| `workdir` | string | Directory where the session file is stored. Must not be in the committed repo. |

### `handoff_dispatch.trusted_sender`

| Field | Type | Description |
|-------|------|-------------|
| `type` | string | `user_session` for Pyrogram user session transport. |
| `note` | string | Human-readable note about the OpenClaw channel trust requirement. |

### `handoff_dispatch.messages`

| Field | Description |
|-------|-------------|
| `ready_for_implementation` | Trigger sent to CODER when a new task is ready. |
| `changes_requested` | Trigger sent to CODER when review blockers are returned. |
| `ready_for_review` | Trigger sent to REVIEWER when CODER finishes implementation. |
| `approved` | Notification sent to HUMAN when REVIEWER approves. |

---

## 3. Security rules

The config file **must not contain**:

- Telegram API hash
- Telegram API ID
- Phone number
- Session string
- Bot token
- Any other secrets or credentials

Pyrogram session files (`.session`) must remain local and must never be committed to the repo.

If the `.agent/config.yaml` file is committed to a repo, ensure it contains only non-secret values (chat/topic IDs and message strings are acceptable).

---

## 4. OpenClaw trusted sender setup

The Pyrogram dispatcher sends messages from a user account (or service user), not a bot.

OpenClaw must be configured to accept messages from this user account in the relevant topics. If OpenClaw ignores the dispatcher's messages:

1. Identify the Telegram user id of the Pyrogram session being used.
2. Add that user id to the allowed/trusted sender list in the OpenClaw Telegram channel configuration.
3. The exact OpenClaw config key for this depends on your OpenClaw version — consult your OpenClaw channel policy documentation.

---

## 5. Dispatch metadata in ACTIVE.md

When the dispatcher runs, it may optionally update `ACTIVE.md` frontmatter with dispatch metadata:

```yaml
dispatch:
  last_status: ready_for_implementation
  last_to_role: CODER
  dispatched_at: "2026-05-20T10:00:00Z"
  transport: pyrogram_user
  telegram_chat_id: -1003596522926
  telegram_topic_id: 7301
  telegram_message_id: 18900
```

This metadata enables idempotency: the dispatcher checks `last_status` and `last_to_role` before sending to avoid duplicate triggers.

See [HANDOFF_DISPATCH_PROTOCOL.md](HANDOFF_DISPATCH_PROTOCOL.md) section 6 for idempotency rules.
