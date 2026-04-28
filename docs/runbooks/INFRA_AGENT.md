# Runbook: Infra Agent

> Standard operating procedure for an agent responsible for maintaining
> the memory infrastructure itself.

---

## Regular Maintenance Tasks

### Check memory health across all topics
```bash
for topic_id in $(ls memory/ | grep -oP '(?<=topic-)\d+'); do
  python3 .../archive-batch-v2.py $topic_id --status
done
```

### Identify stale memory files (>7 days since last write)
```bash
python3 -c "
from pathlib import Path
from datetime import datetime, timezone
import re

for f in Path('memory').glob('topic-*.md'):
    text = f.read_text()
    m = re.search(r'last-write: ([^|]+)', text)
    if m:
        ts = datetime.fromisoformat(m.group(1).strip())
        age = (datetime.now(timezone.utc) - ts).days
        if age > 7:
            print(f'{age}d stale: {f}')
"
```

### Run archive pass on stale topics
```bash
python3 .../archive-batch-v2.py <topic-id> \
  --write \
  --session-id "infra-maintenance-$(date +%Y%m%d)" \
  --auto-mark-done
```

---

## Bootstrap a New Project

```bash
# In the target project directory:
bash /path/to/openclaw-agent-memory-infra/.agent-template/bootstrap.sh .

# Then fill in AGENT_CONTEXT.md and run initial archive:
python3 .../archive-batch-v2.py <topic-id> \
  --write \
  --session-id "infra-init-$(date +%Y%m%d)"
```

---

## Memory File Audit

Check for ⚠️ CONFLICT markers:
```bash
grep -r "CONFLICT" memory/
```

Each CONFLICT should be reviewed:
- If the conflict is resolved by the most recent entry → leave as-is (reader uses recency)
- If the conflict indicates a genuine uncertainty → add a clarifying fact in a new archive pass
- Semantic deduplication (Phase 3) will eventually compact these automatically

---

## Backup

Memory files are plain Markdown in `.agent/memory/`. They're committed to the project repo.
No special backup needed beyond regular git commits.

---

## Adding a New Topic

1. Identify the Telegram chat_id and topic_id for the new topic
2. Create an initial archive pass:
   ```bash
   python3 .../archive-batch-v2.py <new-topic-id> --status  # verify detection
   python3 .../archive-batch-v2.py <new-topic-id> --write --session-id init-<date>
   ```
3. Add the topic to `.agent/AGENT_CONTEXT.md` under "Active Topics"
4. Commit the new `memory/topic-<id>.md`

---

## Incident: Tool Calls Blocked ("Forwarding to client for execution")

### Symptoms

All standard tool calls (Bash, Edit, Write, Skill, etc.) return:
```
Forwarding to client for execution
```
or
```
PreToolUse:Callback hook blocking error from command: "callback": Forwarding to client for execution
```

### Root cause

OpenClaw gateway injects a `PreToolUse:Callback` hook at runtime when a pending
client-side callback is queued and not yet resolved. This is NOT stored in
`openclaw.json` — it is a built-in gateway mechanism.

Known triggers:
- Calling the `Skill` tool mid-session (skills execute via Telegram client callback)
- Calling `sys_ctrl restart` with a `continuationMessage` parameter (creates a new
  pending callback after restart)
- Any tool call that times out while the gateway is waiting for client acknowledgement

### Diagnostic steps

1. **Check if mcp__oc__sys_ctrl works** — it almost always bypasses the hook:
   ```
   sys_ctrl → config.get path=agents.defaults.hooks
   ```
   If it returns `PreToolUse` entries, the hook is active.

2. **Verify tools were working recently** — check conversation history.
   If tools worked earlier in this session and `openclaw.json` was not changed,
   the block is transient (pending callback queue), not a configuration issue.

3. **Do NOT modify settings.json or openclaw.json** — the hook is runtime-injected,
   config changes will have no effect and may cause unintended side effects.

### Fix

**Trigger a gateway restart (SIGUSR1):**
```
sys_ctrl → action: restart, note: "Clear PreToolUse callback queue"
```

**Important:** do NOT include a `continuationMessage` parameter — it creates a new
pending callback immediately, which may re-trigger the block after restart.

After restart, send a plain user message ("Continue" or similar) to re-activate
the session. Tools should work again on the next turn.

### Prevention

- Do not call `Skill` tool (`/read-context`, `/archive-context`, etc.) in the
  middle of an active coding/tool-heavy session. Run skills at the beginning or
  end of a session.
- When using `sys_ctrl restart`, omit `continuationMessage` unless you specifically
  need it and know the callback will be resolved quickly.
- If you encounter this block: stop, do not retry tool calls in a loop,
  trigger one gateway restart, wait for the user's next message.
