
---

## Private memory

Private memory stores local access and infrastructure facts that must not be lost between sessions but must never be committed.

**Location:** `.agent/memory/private/` (gitignored)

```
.agent/memory/private/
  access.md          VPS / SSH access patterns, key locations
  credentials.md     Token names, purposes, env file locations
  infrastructure.md  Service ports, admin URLs, deployment/restart commands
```

**Rules:**
- Never commit `.agent/memory/private/`
- Never copy content into `working/*.md`, docs, PR descriptions, or commit messages
- Raw secret values are never written — name and purpose only
- When reporting: summarize category-level changes only

See `docs/AGENT_STARTUP_AUTOFILL_PROTOCOL.md` §9 for full content schema.

---

## Agent autofill protocol

After `refresh-memory --write`, the agent MUST fill all `<!-- TODO -->` placeholders
in `working/*.md` before running `recover-memory`. Scripts do not call LLM APIs —
the agent performs the semantic autofill step.

See `docs/AGENT_STARTUP_AUTOFILL_PROTOCOL.md` for the full startup sequence,
autofill rules, and MEMORY STARTUP REPORT format.

---

## Operator model

The operator sends two files to the agent:

1. `docs/PROJECT_START_TEMPLATE.md` — edit only: Project name, Project scope
2. `docs/MEMORY_RULES_TEMPLATE.md` — no edits required

The agent handles everything else: role inference, project location, refresh,
autofill, private memory, recover, and the MEMORY STARTUP REPORT.

---

## Telegram read parameters (--read-topic)

`--read-topic` requires `--chat-id` and at least one read selector.

| Flag | Description |
|---|---|
| `--limit <N>` | Max messages to fetch (must be positive) |
| `--since-id <ID>` | Only fetch messages after this message ID |
| `--until-id <ID>` | Only fetch up to this message ID (requires `--since-id`) |
| `--since <YYYY-MM-DD>` | Only fetch messages after this date |
| `--until <YYYY-MM-DD>` | Only fetch messages before this date (requires `--since`) |
| `--full` | Read entire topic history (requires `--confirm-large-read`) |
| `--confirm-large-read` | Acknowledge that `--full` may fetch many messages |

**Read modes** (auto-detected from flags):

- `limit` — `--limit` only
- `since-id` — `--since-id` only
- `message-id-range` — `--since-id` + `--until-id`
- `since-date` — `--since` only
- `date-range` — `--since` + `--until`
- `full` — `--full --confirm-large-read`

**Validation rules:**
- `--full` cannot be combined with `--limit`, `--since-id`, `--until-id`, `--since`, or `--until`
- `--until-id` requires `--since-id`
- `--until` requires `--since`
- `--topics` is not supported (single-topic mode only)
