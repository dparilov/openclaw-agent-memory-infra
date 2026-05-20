# Restore Memory Flow

This document describes the full restore-memory flow for the ASSISTANT role in DM mode.

---

## 1. Trigger

Memory restore is initiated by the human. The agent must not run restore unprompted.

### Default restore (local-first)

**Recognized trigger phrases:**

- `восстанови память`
- `restore memory`
- Close variants: "восстанови контекст", "reload memory", "load memory"

Default restore reads the local assistant memory workspace. It does **not** run `refresh-memory.py --read-topic`. Pyrogram and a Telegram session are not required.

### Explicit Telegram history import

**Recognized trigger phrases:**

- `восстанови память из Telegram`
- `импортируй историю Telegram`
- `import Telegram history`
- `backfill from Telegram`

Explicit Telegram import runs `refresh-memory.py --read-topic --full`. Pyrogram and a Telegram session are required. If unavailable, the agent reports `TELEGRAM HISTORY IMPORT: unavailable` and continues with local memory.

---

## 2. Pre-restore: confirm metadata and workspace

Before running restore, verify the following:

| Item | Source |
|------|--------|
| `<assistant-memory-workspace>` | `$ASSISTANT_MEMORY_WORKSPACE` or `$HOME/.assistant-memory` |
| Workspace exists on disk | Check with `ls <assistant-memory-workspace>/.agent/` |
| `<topic-id>` | `$OPENCLAW_TOPIC_ID` or runtime context. **For Telegram DMs (no forum thread), use `0`.** |
| `<chat-id>` | `$OPENCLAW_CHAT_ID` or runtime context (needed for explicit Telegram import only) |
| `<PME_REPO>` | Local path to `openclaw-agent-memory-infra` (needed for PME script flows only) |
| Pyrogram capability | Optional — needed only for explicit Telegram import. Missing Pyrogram is **not** a blocking condition for default local-first restore. See [`docs/security/PYROGRAM_CAPABILITY.md`](../security/PYROGRAM_CAPABILITY.md). |

**If workspace is missing in ASSISTANT DM mode:** the workspace must have been auto-initialized during bootstrap (see `ASSISTANT_BOOTSTRAP.md` section 2c). If it is still missing at restore time, the agent must initialize it now — no confirmation needed. Missing workspace is **not** a blocking condition.

A blocking question about workspace creation is allowed **only** if the agent cannot create the workspace due to a filesystem permission error or runtime error.

**`<PME_REPO>` resolution:** Needed only for `recover-memory.py` (step 2 of default restore) and explicit Telegram import. Use the discovery order from `ASSISTANT_BOOTSTRAP.md` section 2e. Do **not** block on a missing local PME repo — auto-provision first (see section 2b).

---

## 2b. Pre-step: ensure PME tooling checkout (if using PME scripts)

Required before running `recover-memory.py` or `refresh-memory.py`.

1. Resolve `PME_REPO` using the discovery order from `ASSISTANT_BOOTSTRAP.md` section 2e.
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

See [`PME_TOOLING_CHECKOUT.md`](PME_TOOLING_CHECKOUT.md) for the full reference.

---

## 3. Default restore — local-first

`восстанови память` / `restore memory` reads local workspace files. No Telegram access. No Pyrogram required.

### Step 1 — Read local workspace files

```bash
WORKSPACE="${ASSISTANT_MEMORY_WORKSPACE:-$HOME/.assistant-memory}"

# Core context
cat "$WORKSPACE/.agent/AGENT_CONTEXT.md" 2>/dev/null

# Working memory
for f in "$WORKSPACE/.agent/memory/working/"*.md; do
  [ -f "$f" ] && cat "$f"
done

# Promoted memory (if present)
for f in "$WORKSPACE/.agent/memory/promoted/"*.md; do
  [ -f "$f" ] && cat "$f"
done

# Raw memory (if present)
for f in "$WORKSPACE/.agent/memory/raw/"*.md; do
  [ -f "$f" ] && cat "$f"
done
```

### Step 2 — Structured recovery (optional, if PME available)

If `PME_REPO` is available (after auto-provisioning per section 2b), run:

```bash
python3 "$PME_REPO"/scripts/recover-memory.py \
  --target "$ASSISTANT_MEMORY_WORKSPACE" \
  --topic 0 \
  --role unknown
```

Use `0` for DM mode without a forum thread. If `PME_REPO` is unavailable, skip this step and continue with the files read in step 1.

### Step 3 — Report

If memory files contain substantive notes:

```
MEMORY RESTORED

Mode: DM
Source: local workspace
Workspace: ~/.assistant-memory
Context loaded: yes
Current state: <short summary>
Open loops:
- <item or "none">
Relevant memory:
- <key facts>
Next safe action: continue conversation
```

If only bootstrap stubs are found (freshly initialized workspace):

```
MEMORY RESTORE: completed

Mode: DM
Source: local workspace
Workspace: ~/.assistant-memory
Result: local memory contains only bootstrap stubs; no prior notes yet
Next safe action: continue conversation
```

---

## 4. Explicit Telegram history import / backfill

Triggered only by explicit phrases: `восстанови память из Telegram`, `импортируй историю Telegram`, `import Telegram history`, `backfill from Telegram`.

Requires: Pyrogram installed + session available + `chat-id` known + PME tooling available.

### Step 0 — Check Pyrogram capability

```bash
python3 -c "import pyrogram" 2>/dev/null || echo "unavailable"
# Also check session candidates (see docs/security/PYROGRAM_CAPABILITY.md)
```

If Pyrogram is unavailable:

```
TELEGRAM HISTORY IMPORT: unavailable

Reason: Pyrogram user session not configured / pyrogram not installed
Local memory: available (run "восстанови память" for local restore)
```

Stop here. Do not attempt `refresh-memory.py --read-topic`.

### Step 1 — Ensure PME tooling (section 2b)

### Step 2 — Refresh memory from Telegram topic

For **Telegram DM** (no forum thread):

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

### Step 3 — Structured recovery

```bash
python3 "$PME_REPO"/scripts/recover-memory.py \
  --target "$ASSISTANT_MEMORY_WORKSPACE" \
  --topic <topic-id-or-0> \
  --role unknown
```

> **Note:** `--role unknown` is the safe fallback for the current CLI.

### Step 4 — Report

```
MEMORY RESTORED

Mode: DM
Source: Telegram history import
Workspace: ~/.assistant-memory
Messages fetched: <n / unknown>
Context loaded: yes / no
Current state: <short summary>
Open loops:
- <item or "none">
Relevant memory:
- <key facts>
Next safe action: continue conversation
```

---

## 5. Blocked / error output

If restore was blocked or partially failed:

```
MEMORY RESTORE BLOCKED

Reason: <workspace creation failed / PME provisioning failed / read error>
PME repo: <resolved path or "provisioning failed">
Partial context: <what was found, if anything>
Next safe action: ask blocking question / continue without memory
```

Reasons that are **not** blocking for default local-first restore:
- Missing Pyrogram
- Missing Telegram session
- Missing `chat-id`
- Missing PME repo (only blocks `recover-memory.py` step, not local file read)

---

## 6. After restore

Continue the conversation normally. Do not re-run restore unless the human requests it again.
