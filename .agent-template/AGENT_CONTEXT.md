# Agent Context — <project-name>

> Load this file first at every session start.
> It provides project-level orientation that does not change frequently.
> Facts that evolve between sessions belong in `memory/working/*.md`.

## Project Overview

<!-- One paragraph: what this project is, its purpose, primary stakeholders -->

## Key Entities

| Name | Type | Topic ID | Notes |
|------|------|----------|-------|
| <!-- e.g. Dima --> | person | <!-- e.g. 125132275 --> | <!-- project owner --> |
| <!-- e.g. telemost --> | project | <!-- e.g. 7301 --> | <!-- main work channel --> |

## Active Topics

<!-- List of active Telegram topics/channels relevant to this project -->
<!-- Format: topic-<id> — <description> — <role: coder/reviewer/infra> -->

---

## Startup Memory Load Order (v1)

At the start of every session, read these files in order:

1. `.agent/AGENT_CONTEXT.md` — this file (project identity, scope, contacts)
2. `.agent/memory/working/agent-brief.md` — what to do and what not to touch
3. `.agent/memory/working/current-state.md` — what is working, in progress, next step
4. `.agent/memory/working/known-issues.md` — active blockers, risks, open bugs
5. `.agent/memory/working/decisions.md` — architecture decisions *(optional, if present)*
6. `.agent/memory/working/open-questions.md` — unresolved questions *(optional, if present)*

Do not skip steps 2–4 even if they seem short. They are the compiled memory pack.

---

## Memory Layers (D-1 — coexistence, not replacement)

Two layers coexist and serve different purposes:

| Layer | Location | Purpose |
|-------|----------|---------|
| Archive log | `.agent/memory/topic-<id>.md` | Raw/append-only source material; written by `archive-batch-v2.py`; never read directly by agents at startup |
| Working memory | `.agent/memory/working/*.md` | Reviewed compiled memory pack; what agents read at startup |

`archive-batch-v2.py` writes to the archive log only.  
Working memory is produced by a separate extraction + human review step.  
Do not conflate the two layers.

---

## Memory Protocol (MANDATORY — do not remove or override)

- **NEVER** start a session without reading the startup memory load order above
- **NEVER** ask the user for information already present in `memory/working/*.md`
- **NEVER** write to `memory/working/*.md` directly — changes go through the extraction + review flow
- **NEVER** silently accept a contradiction between memory and observed reality —
  report it to the operator and note it for the next memory refresh
- **IF** working memory files are missing or >24 hours stale → report to operator before proceeding

### read-topic rule

Do **not** run `read-topic.py` automatically on startup or on any heartbeat/scheduled trigger.

Use `read-topic.py` only on **explicit operator request**, and always scope it:
```bash
# Bounded by message count
python3 read-topic.py <topic-id> --limit 200

# Bounded by message ID range
python3 read-topic.py <topic-id> --since-id <id>
```
Full unbounded topic reads are expensive and slow. Never run them silently.

---

## v1 Non-Goals

The startup path must not require any of the following:

- Vector DB or embeddings (OpenAI, local, or otherwise)
- OpenClaw memory-core or knowledge_search
- Automatic candidate promotion
- Mandatory wiki build
- Cross-topic SendMessage automation
- Full Telegram topic read on startup

---

## Quick Commands

```bash
# Check archive log status for a topic
python3 /path/to/archive-batch-v2.py <topic-id> --status

# Archive current session facts to the archive log
python3 /path/to/archive-batch-v2.py <topic-id> --write facts.txt \
  --session-id <uuid> --memory-dir .agent/memory --auto-mark-done

# Read topic on explicit operator request (bounded)
python3 /path/to/read-topic.py <topic-id> --limit 200
python3 /path/to/read-topic.py <topic-id> --since-id <last-known-id>
```

---

## Agent Behavior Notes

<!-- Project-specific rules for agents working in this context -->
<!-- e.g. "Always check working memory before asking the operator about X" -->
<!-- e.g. "Decisions about Y require operator approval" -->
