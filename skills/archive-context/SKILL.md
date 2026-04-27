---
name: archive-context
description: Incrementally inspect and archive OpenClaw Telegram topic/session context using the archive-batch-v2 script.
---

# archive-context

Thin wrapper for the script-first archive pipeline.

Primary script:

```bash
python3 /home/dima/projects/openclaw-agent-memory-infra/scripts/context_access/archive-batch-v2.py <topic_id|topic_name> [options]
```

## When to use

Use this skill when the user asks:

- `/archive-context <topic_id>`
- `/archive-context <topic_name> --status`
- "заархивируй контекст топика telemost"
- "покажи статус архива топика 7301"
- "подготовь batch контекста"

## Absolute rules

1. **topic_id is REQUIRED.** Never run without an explicit topic id or name. If the user does not provide one, ask: "Укажи topic ID или имя топика (например: 7301 или telemost)."
2. **Script first.** Always run `archive-batch-v2.py`; do not emulate status from memory.
3. **Read-only for `--status`.** If user asks `--status`, do not write memory files and do not mark progress.
4. **No hidden archive writes.** Do not append to `memory/*.md` unless the user explicitly asks to process/archive a batch.
5. **No reset without explicit confirmation.** `--reset` is destructive; ask before running it.
6. **Report stdout verbatim for status.** For `--status`, paste the script output exactly. Do NOT paraphrase, summarize, or reformat it.
7. **NEVER fabricate script output.** If you did not receive actual stdout from the script, you MUST say so explicitly. Do not describe what the output "probably" looks like. Do not invent file paths, message counts, or status summaries.
8. **If tool execution fails or returns no output**, respond with exactly:
   ```
   [blocked] Script did not run — tool execution failed or returned no output.
   Run manually:
   python3 /home/dima/projects/openclaw-agent-memory-infra/scripts/context_access/archive-batch-v2.py <topic_id> --status
   ```
   Then stop. Do not attempt to reconstruct or guess the output.

## Syntax

```text
/archive-context <topic_id|topic_name> [--status]
/archive-context <topic_id|topic_name> --batch N
/archive-context <topic_id|topic_name> --total
```

**topic_id is always required** — numeric (e.g. `7301`) or topic name (e.g. `telemost`, `OpenClaw_infra`).

Name resolution is handled automatically by `archive-batch-v2.py`. If the name is not found, the script will print all known topic names.

## Status mode

For:

```text
/archive-context 7301 --status
```

run exactly:

```bash
python3 /home/dima/projects/openclaw-agent-memory-infra/scripts/context_access/archive-batch-v2.py 7301 --status
```

Or by name:

```bash
python3 /home/dima/projects/openclaw-agent-memory-infra/scripts/context_access/archive-batch-v2.py telemost --status
```

Then reply with:

```text
ARCHIVE-CONTEXT STATUS
<verbatim script stdout>

No files were modified.
```

## Total mode

For:

```text
/archive-context 7301 --total
```

run:

```bash
python3 /home/dima/projects/openclaw-agent-memory-infra/scripts/context_access/archive-batch-v2.py 7301 --total
```

## Batch preview mode

For:

```text
/archive-context 7301 --batch 0
```

run read-only preview:

```bash
python3 /home/dima/projects/openclaw-agent-memory-infra/scripts/context_access/archive-batch-v2.py 7301 --batch 0 --max-text 1200
```

This prints a deduplicated batch for inspection. It does **not** write memory and does **not** mark progress.

## Actual archive/write mode

**Implemented.** Use `--write` to append a batch to `memory/topic-<id>.md`:

```bash
python3 /home/dima/projects/openclaw-agent-memory-infra/scripts/context_access/archive-batch-v2.py \
  <topic_id> \
  --write \
  --session-id <uuid> \
  --auto-mark-done
```

- `--session-id` enables idempotency (same session-id will be skipped on re-run)
- `--auto-mark-done` marks the batch as processed in progress file
- Output file: `<project>/.agent/memory/topic-<id>.md`
- Conflict detection is heuristic (⚠️ CONFLICT markers); semantic dedup is Phase 3

For explicit memory-file path override:
```bash
... --memory-file /path/to/memory/topic-<id>.md
```

## Known provider issue

If running under Meridian/MeridianA and tools return:

```text
Forwarding to client for execution
```

then this is a provider/runtime execution path issue. The fallback is to run the explicit script command through an OpenClaw `exec`-capable session or host shell.

Known-good fallback command:

```bash
python3 /home/dima/projects/openclaw-agent-memory-infra/scripts/context_access/archive-batch-v2.py 7301 --status
```
