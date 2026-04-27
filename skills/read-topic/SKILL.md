---
name: read-topic
description: Read Telegram topic history via Pyrogram userbot and output structured transcript.
---

# read-topic

Reads live Telegram topic messages via Pyrogram userbot.  
Outputs raw transcript or structured `--batch-format` for write-pipeline integration.

Primary script:

```bash
python3 /home/dima/projects/openclaw-agent-memory-infra/scripts/context_access/read-topic.py \
  <topic_id|topic_name> [options]
```

## When to use

Use this skill when the user asks:

- `/read-topic <topic_id>`
- `/read-topic telemost --limit 200`
- "прочитай топик telemost"
- "покажи последние 100 сообщений из топика 7301"
- "получи свежие сообщения из чата, которых нет в сессиях OpenClaw"

## Absolute rules

1. **topic_id or name is REQUIRED.** Ask if not provided.
2. **Requires Pyrogram userbot session.** If `.session` file not found, report error and suggest setting `PYROGRAM_SESSION` env var.
3. **Read-only by default.** This script does NOT write to memory files.
4. **FloodWait is handled automatically** (4 retries with backoff). If all retries fail, report the error verbatim.
5. **NEVER fabricate script output.** If execution fails, say so explicitly.
6. **If tool execution fails or returns no output**, respond with:
   ```
   [blocked] Script did not run — tool execution failed or returned no output.
   Run manually:
   python3 .../read-topic.py <topic_id>
   ```

## Syntax

```text
/read-topic <topic_id|topic_name>
/read-topic <topic_id|topic_name> --limit N
/read-topic <topic_id|topic_name> --since-id MSG_ID
/read-topic <topic_id|topic_name> --batch-format
/read-topic <topic_id|topic_name> --chat-id CHAT_ID
```

## Options

| Option | Default | Description |
|--------|---------|-------------|
| `--limit N` | 500 | Max messages to fetch |
| `--since-id ID` | None | Only fetch messages after this message ID (delta read) |
| `--batch-format` | off | Structured transcript for write-pipeline |
| `--chat-id ID` | auto | Override chat_id (skip auto-discovery from session metadata) |

## Default output (raw transcript)

```
=== Топик 7301 в чате -100XXXXXXX (42 сообщений) ===

[27.04 19:11] Dima: some message text
[27.04 19:15] Alex: reply text
...
=== END ===
```

## Batch-format output (write-pipeline)

For downstream archiving, use `--batch-format`:

```bash
python3 .../read-topic.py 7301 --batch-format --since-id 15800
```

Output:
```
## Transcript — 2026-04-27T19:11:00
## Source: telegram:-100XXXXXXX:7301 | messages: 42
## Range: 2026-04-27T16:00:00 → 2026-04-27T19:11:00 | last-id: 15899

[2026-04-27T16:00] Dima: some message text
...

## END TRANSCRIPT
```

This output is suitable for LLM fact-extraction, after which facts can be passed to `archive-batch-v2.py --write`.

## Chaining with archive pipeline

```bash
# 1. Read new messages since last archived ID
python3 .../read-topic.py 7301 --batch-format --since-id 15800 > /tmp/transcript.txt

# 2. Agent extracts facts from transcript.txt
# ... LLM step ...

# 3. Archive extracted facts
python3 .../archive-batch-v2.py 7301 --write --session-id <uuid>
```

## Environment variables

| Var | Default | Description |
|-----|---------|-------------|
| `OPENCLAW_AGENTS` | `~/.openclaw/agents` | Path to agents directory |
| `PYROGRAM_SESSION` | `~/.openclaw/workspace/ops/userbot` | Path to .session file |
| `PYROGRAM_VENV` | auto-detect | Path to site-packages with pyrogram |

## Known provider issue

If running under Meridian/MeridianA and tools return `Forwarding to client for execution`,
run the script directly in an OpenClaw exec-capable session or host shell.
