# Agent Context — <project-name>

> This file is loaded by the agent at session start via `/read-context`.
> It provides project-level orientation that doesn't change frequently.
> Keep it concise — facts that evolve belong in `memory/topic-<id>.md`.

## Project Overview

<!-- One paragraph: what this project is, its purpose, primary stakeholders -->

## Key Entities

| Name | Type | Topic ID | Notes |
|------|------|----------|-------|
| <!-- e.g. Dima --> | person | <!-- e.g. 125132275 --> | <!-- project owner --> |
| <!-- e.g. telemost --> | project | <!-- e.g. 7301 --> | <!-- main work channel --> |

## Active Topics

<!-- List of active Telegram topics/channels relevant to this project -->
<!-- Format: topic-<id>.md — <description> -->

## Memory Files

| File | Description | Last Updated |
|------|-------------|--------------|
| <!-- memory/topic-7301.md --> | <!-- telemost main channel --> | <!-- check header --> |

## Quick Commands

```bash
# Check archive status
python3 /path/to/archive-batch-v2.py <topic-id> --status

# Archive current session
python3 /path/to/archive-batch-v2.py <topic-id> --write --session-id <uuid> --auto-mark-done

# Read live topic (Pyrogram)
python3 /path/to/read-topic.py <topic-id> --limit 200
```

## Memory Protocol (MANDATORY — do not remove or override)

- NEVER start a session without `/read-context` (or `/recover-memory` if stale)
- NEVER end a session without `/archive-context` if any facts were established
- NEVER ask the user for information already present in `memory/topic-*.md`
- NEVER write to memory files directly — only via `archive-batch-v2.py --write`
- NEVER silently accept a contradiction between memory and observed reality —
  archive the correction and flag the conflict
- IF `last-write` in memory header > 24 hours ago → run `/recover-memory` before any task work
- IF `/recover-memory` fails → report to user; do not proceed as if memory is current

---

## Agent Behavior Notes

<!-- Project-specific rules for agents working in this context -->
<!-- e.g. "Always check memory before asking Dima about X" -->
<!-- e.g. "Decisions about Y require Dima's approval" -->
