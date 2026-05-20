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

## 2. Pre-restore: confirm metadata and workspace

Before running restore, verify the following:

| Item | Source |
|------|--------|
| `<assistant-memory-workspace>` | `$ASSISTANT_MEMORY_WORKSPACE` or `$HOME/.assistant-memory` |
| Workspace exists on disk | Check with `ls <assistant-memory-workspace>/.agent/` |
| `<topic-id>` | `$OPENCLAW_TOPIC_ID` or runtime context. **For Telegram DMs (no forum thread), use `0`.** |
| `<chat-id>` | `$OPENCLAW_CHAT_ID` or runtime context |
| `<PME_REPO>` | Local path to `openclaw-agent-memory-infra` |

**If workspace is missing in ASSISTANT DM mode:** the workspace must have been auto-initialized during bootstrap (see `ASSISTANT_BOOTSTRAP.md` section 2c). If it is still missing at restore time, the agent must initialize it now — no confirmation needed. Missing workspace is **not** a blocking condition.

A blocking question about workspace creation is allowed **only** if the agent cannot create the workspace due to a filesystem permission error or runtime error.

**`<PME_REPO>` resolution:** Use the discovery order from `ASSISTANT_BOOTSTRAP.md` section 2d. Do **not** block on a missing local PME repo — auto-provision first (see pre-step below).

If any other item is unknown and cannot be inferred, ask **one blocking question** covering all missing items before proceeding.

---

## 2b. Pre-step: ensure PME tooling checkout

Before running `refresh-memory.py` or `recover-memory.py`, the agent must:

1. Resolve `PME_REPO` using the discovery order from `ASSISTANT_BOOTSTRAP.md` section 2d.
2. If no valid path is found, auto-provision:
   ```bash
   mkdir -p "$HOME/.pme"

   if [ ! -d "$HOME/.pme/openclaw-agent-memory-infra/.git" ]; then
     git clone https://github.com/dparilov/openclaw-agent-memory-infra.git \
       "$HOME/.pme/openclaw-agent-memory-infra"
   else
     git -C "$HOME/.pme/openclaw-agent-memory-infra" pull --ff-only
   fi

   PME_REPO="$HOME/.pme/openclaw-agent-memory-infra"
   ```
3. Validate that both scripts exist:
   ```bash
   test -f "$PME_REPO/scripts/refresh-memory.py" && \
   test -f "$PME_REPO/scripts/recover-memory.py"
   ```
4. Only then proceed to the restore commands.

Restore may be blocked only after auto-provisioning has been **attempted and failed**, with a concrete reason:
- `git` unavailable;
- clone failed;
- pull failed;
- scripts still missing after clone/pull;
- permission denied;
- `chat-id` unavailable;
- runtime error from `refresh-memory.py` or `recover-memory.py`.

See [`PME_TOOLING_CHECKOUT.md`](PME_TOOLING_CHECKOUT.md) for the full reference.

---

## 3. Restore commands (PME available)

### Step 1 — Refresh memory from topic

For **Telegram DM** (no forum thread, `Topic: unknown (DM)`):

```bash
python3 "$PME_REPO"/scripts/refresh-memory.py \
  --target "$ASSISTANT_MEMORY_WORKSPACE" \
  --topic 0:unknown \
  --read-topic \
  --chat-id <chat-id> \
  --full \
  --confirm-large-read \
  --write
```

For **forum thread** (topic-id is known):

```bash
python3 "$PME_REPO"/scripts/refresh-memory.py \
  --target "$ASSISTANT_MEMORY_WORKSPACE" \
  --topic <topic-id>:unknown \
  --read-topic \
  --chat-id <chat-id> \
  --full \
  --confirm-large-read \
  --write
```

- `--topic 0:unknown`: use `0` when there is no forum thread id (Telegram DM / main chat).
- `--full`: read all available messages. Appropriate for small DM topics.
- `--confirm-large-read`: prompts before reading unexpectedly large topics.
- `--write`: persist the extracted memory to the workspace.

### Step 2 — Recover structured memory

```bash
python3 "$PME_REPO"/scripts/recover-memory.py \
  --target "$ASSISTANT_MEMORY_WORKSPACE" \
  --topic <topic-id-or-0> \
  --role unknown
```

Use `0` in place of `<topic-id-or-0>` when operating in DM mode without a forum thread.

> **Note:** `--role unknown` is the safe fallback for the current CLI. Use `--role assistant` only after first-class assistant role support is added in a separate runtime PR.

---

## 4. Restore fallback (PME not available)

If the PME scripts are not accessible:

1. Report: `PME commands not available in this environment.`
2. Attempt to read memory files directly:
   ```bash
   ls <assistant-memory-workspace>/.agent/memory/working/
   cat <assistant-memory-workspace>/.agent/memory/working/current-state.md 2>/dev/null
   cat <assistant-memory-workspace>/.agent/memory/working/agent-brief.md 2>/dev/null
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

Reason: <git unavailable / clone failed / chat-id missing / read failed>
PME repo: <resolved path or "provisioning failed">
Partial context: <what was found, if anything>
Next safe action: ask blocking question / continue without memory
```

If PME tooling is ready but no prior memory exists:

```
MEMORY RESTORE: completed

Workspace: ~/.assistant-memory
PME repo: <resolved path>
Result: no prior memory artifacts found
```

---

## 6. After restore

Continue the conversation normally. Do not re-run restore unless the human requests it again.
