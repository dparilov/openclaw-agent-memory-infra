# Context Access Scope

## Purpose

Build a reliable context ingestion layer for OpenClaw-based development agents.

The layer must support rough but dependable reading of large Telegram topic histories and OpenClaw transcripts on demand, then feed the shared memory tools under development.

This is a core dependency of the shared-memory pipeline. Candidate extraction and memory promotion should not rely on fragile chat recall or truncated `sessions_history` output.

## Problem Statement

Current agents lose important project context after compaction/restart. In active developer topics this causes loss of:

- credentials and test environment details;
- current branch/repo/deployment state;
- task decisions and rejected paths;
- test commands and known bugs;
- recent handoff state between Coder/Reviewer/Infrastructure agents.

Existing OpenClaw session tools can return truncated history. Telegram skills/commands can also fail to execute because command invocation may be intercepted by native skill forwarding / PreToolUse callback behavior.

Therefore context access must be implemented script-first, with skills/commands as thin wrappers only.

## Existing Components Observed

### `read-topic.py`

Path: `/home/dima/.openclaw/workspace/ops/read-topic.py`

Role: live Telegram topic reader through Pyrogram userbot.

Current behavior:

- command: `python3 ~/.openclaw/workspace/ops/read-topic.py <chat_id> <topic_id> [limit]`;
- uses Pyrogram `Client("userbot", workdir="/home/dima/.openclaw/workspace/ops")`;
- prints topic messages to stdout;
- does not persist output unless caller redirects stdout;
- for non-zero topics filters by root message id / `message_thread_id` / `reply_to_message_id`;
- for General uses `topic_id=0` and keeps messages without thread id;
- truncates each message preview to 500 characters;
- reads from Telegram, not OpenClaw transcript files.

Known limitations:

- large reads can trigger Telegram flood-wait;
- parallel invocations can fail with `sqlite3.OperationalError: database is locked` on the userbot session;
- output is not a raw complete archive because message text is truncated to 500 chars;
- no built-in date filtering, search, stats, checkpointing, or persistent archive path;
- suitable for rough inspection, not sufficient alone for canonical ingestion.

### `read-full-transcript.py`

Path: `/home/dima/.openclaw/workspace/ops/read-full-transcript.py`

Role: OpenClaw JSONL transcript reader.

Current behavior:

- command examples:
  - `python3 read-full-transcript.py 7301 --stats`
  - `python3 read-full-transcript.py 7301 --full`
  - `python3 read-full-transcript.py 7301 --last 60 --summary`
  - `python3 read-full-transcript.py 7301 --since 2026-04-12`
  - `python3 read-full-transcript.py 7301 --find "ssh"`
- resolves numeric topic id by filename pattern `*-topic-<id>.jsonl` and reset files;
- intentionally avoids content scanning for topic detection because that creates false positives;
- merges multiple session files chronologically;
- prints a mandatory transcript stats block;
- supports last/since/search/find filters.

Known limitations:

- reads OpenClaw transcript files, not Telegram server history;
- only sees messages captured by OpenClaw sessions;
- needs portability work before becoming a repo-contained tool.

### `archive-batch.py`

Path: `/home/dima/.openclaw/workspace/ops/archive-batch.py`

Role: batch context archiver helper.

Current behavior:

- reads topic transcript messages in batches, default 100 messages;
- progress tracker: `/home/dima/.openclaw/workspace/ops/archive-progress-<topic>.json`;
- intended memory output: `/home/dima/.openclaw/workspace/memory/topic-<topic>.md`;
- supports status, batch selection, total, reset, and mark-done modes.

Known limitations:

- currently workspace-local;
- memory extraction is LLM-mediated, not yet schema-validated;
- `--reset` is destructive and must require explicit user confirmation;
- command/skill execution wrapper is unstable in Telegram until native skill forwarding issue is resolved.

### `read-context` and `archive-context`

Current forms:

- OpenClaw skills:
  - `/home/dima/.openclaw/workspace/skills/read-context/SKILL.md`
  - `/home/dima/.openclaw/workspace/skills/archive-context/SKILL.md`
- Claude command files:
  - `/home/dima/.claude/commands/read-context.md`
  - `/home/dima/.claude/commands/archive-context.md`

Intended role:

- user-facing commands for context restoration and incremental archive updates;
- wrappers over stable scripts, not primary implementation.

Known execution problem:

- in Telegram/OpenClaw contexts, skill/command execution may return or be interpreted as:
  - `Skill tool not available`;
  - `Forwarding to client for execution`;
  - `PreToolUse:Callback hook blocking error`;
- changing `channels.telegram.commands.nativeSkills` and restarting gateway was attempted but did not fully resolve the behavior;
- this must be diagnosed as part of the infrastructure project.

## Required Canonical Interface

The infrastructure should provide a portable command surface with at least:

```bash
context-access stats --topic <id>
context-access read --topic <id> --last <N>
context-access read --topic <id> --since <YYYY-MM-DD>
context-access read --topic <id> --full
context-access find --topic <id> --query <term>
context-access archive --topic <id> --batch-size 100
context-access archive --topic <id> --all
context-access status --topic <id>
```

Implementation may initially be Python scripts instead of a single CLI, but behavior and output contracts should match this interface.

## Source Fallback Order

For a requested topic, try:

1. Existing persistent memory archive: `memory/topic-<id>.md` or project `.agent/memory/working` equivalent.
2. OpenClaw transcript JSONL: `~/.openclaw/agents/*/sessions/*-topic-<id>.jsonl*`.
3. Telegram live history through Pyrogram userbot.
4. Explicit user-provided transcript/export.

The tool must clearly report which source was used.

## Safety and Privacy

- Do not store raw secrets in portable repos.
- Redact or segregate credentials before writing shared memory.
- Raw local archives can exist under user-controlled local workspace, but must not be committed unless explicitly intended and sanitized.
- High-risk facts, credentials, security policies, and infrastructure access rules require human approval before canonicalization.

## Execution Policy

Scripts are primary. Skills/commands are wrappers.

Acceptance requirement: every user-facing wrapper must show the exact script command it ran or enough stats to prove it ran.

Wrappers must never say “I already know”; if the user asks to read context, the tool must execute and print stats.

## Acceptance Criteria

A stable context-access layer is acceptable when it can:

1. Read a large Telegram topic or transcript by topic id on demand.
2. Print a mandatory stats block with source, file/message counts, first/last dates, shown range, and coverage.
3. Search for a term across the selected context source.
4. Read by depth: `last N`, `since DATE`, or `full`.
5. Archive context incrementally in batches with progress tracking.
6. Serialize userbot access or otherwise avoid sqlite locks.
7. Handle Telegram flood waits without corrupting output.
8. Feed memory candidate extraction without requiring manual copy-paste.
9. Keep raw evidence distinct from promoted/canonical knowledge.
10. Work even if Telegram skill forwarding/native command execution is broken, by allowing direct script execution.

## Open Questions

- Should the canonical implementation be a single `context-access` CLI or a set of scripts?
- Where should local raw archives live by default in a portable setup?
- How should credentials be redacted while still preserving enough operational context for agents?
- What OpenClaw config/hook setting is causing skill forwarding to client in Telegram sessions?
- Should General topic reads be allowed globally or only by explicit user authorization per run?
