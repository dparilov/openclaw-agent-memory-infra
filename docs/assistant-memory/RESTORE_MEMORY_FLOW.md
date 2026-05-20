# Restore Memory Flow

This document describes the full restore-memory flow for the ASSISTANT role in DM mode.

---

## 1. Trigger

Memory restore is initiated by the human. The agent must not run restore unprompted.

**Recognized trigger phrases:**

- `восстанови память`
- `restore memory`
- Close variants: "восстанови контекст", "reload memory", "load memory"

---

## 2. Pre-restore: confirm metadata

Before running restore, verify the following are known:

| Item | Source |
|------|--------|
| `<assistant-memory-workspace>` | `$ASSISTANT_MEMORY_WORKSPACE` or `$HOME/.assistant-memory` |
| `<topic-id>` | `$OPENCLAW_TOPIC_ID` or runtime context |
| `<chat-id>` | `$OPENCLAW_CHAT_ID` or runtime context |
| `<PME_REPO>` | Local path to `openclaw-agent-memory-infra` |

If any item is unknown and cannot be inferred, ask **one blocking question** covering all missing items before proceeding.

---

## 3. Restore commands (PME available)

### Step 1 — Refresh memory from topic

```bash
python3 <PME_REPO>/scripts/refresh-memory.py \
  --target <assistant-memory-workspace> \
  --topic <topic-id>:assistant \
  --read-topic \
  --chat-id <chat-id> \
  --full \
  --confirm-large-read \
  --write
```

- `--full`: read all available messages. Appropriate for small DM topics.
- `--confirm-large-read`: prompts before reading unexpectedly large topics.
- `--write`: persist the extracted memory to the workspace.

### Step 2 — Recover structured memory

```bash
python3 <PME_REPO>/scripts/recover-memory.py \
  --target <assistant-memory-workspace> \
  --topic <topic-id> \
  --role assistant
```

**Fallback:** If `--role assistant` is not yet supported, use `--role unknown` until first-class assistant role support is added to `recover-memory.py`.

---

## 4. Restore fallback (PME not available)

If the PME scripts are not accessible:

1. Report: `PME commands not available in this environment.`
2. Attempt to read memory files directly:
   ```bash
   ls <assistant-memory-workspace>/
   cat <assistant-memory-workspace>/current-state.md 2>/dev/null
   cat <assistant-memory-workspace>/agent-brief.md 2>/dev/null
   ```
3. Summarize what was found, or report that memory restore is blocked.

---

## 5. MEMORY RESTORED output format

After a successful restore, output:

```
MEMORY RESTORED

Mode: DM
Read mode: full
Messages fetched: <n / unknown>
Context loaded: <yes / no>
Current state: <short summary of what was restored>
Open loops:
- <item or "none">
Relevant memory:
- <key facts or "none">
Next safe action: continue conversation
```

If restore was blocked or partially failed:

```
MEMORY RESTORE BLOCKED

Reason: <PME unavailable / metadata missing / read failed>
Partial context: <what was found, if anything>
Next safe action: ask blocking question / continue without memory
```

---

## 6. After restore

Continue the conversation normally. Do not re-run restore unless the human requests it again.
