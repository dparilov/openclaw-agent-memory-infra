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

## Agent Behavior Notes

<!-- Project-specific rules for agents working in this context -->
<!-- e.g. "Always check memory before asking Dima about X" -->
<!-- e.g. "Decisions about Y require Dima's approval" -->
