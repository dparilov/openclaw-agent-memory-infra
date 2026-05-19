# Active Handoff Protocol

Minimal collaboration protocol for CODER and REVIEWER agents using one active markdown handoff file per project.

---

## Overview

- **One active task per project** at a time.
- The task lives in `.agent/handoffs/ACTIVE.md`.
- Completed handoffs are archived to `.agent/handoffs/archive/`.
- No queues, schedulers, databases, or automation — just a markdown file that agents read and update.

---

## Statuses

| Status | Owner | Meaning |
|--------|-------|---------|
| `ready_for_implementation` | CODER | Task is defined; coder should begin work |
| `ready_for_review` | REVIEWER | Coder finished; reviewer should review |
| `changes_requested` | CODER | Reviewer found blockers; coder should fix |
| `approved` | HUMAN | Reviewer approved; human decides next step |
| `done` | — | Human archived the handoff after merge/closure |

---

## Flow

```
HUMAN/REVIEWER creates ACTIVE.md
        │
        ▼
  ready_for_implementation  ──►  CODER works
        │                              │
        │                              ▼
        │                     ready_for_review  ──►  REVIEWER reviews
        │                              │                     │
        │                              │          ┌──────────┤
        │                              │          ▼          ▼
        │                     changes_requested   approved
        │                              │              │
        │                              ▼              ▼
        │                        CODER fixes       HUMAN
        │                              │          archives
        │                              ▼              │
        │                     ready_for_review        ▼
        │                          (loop)           done
```

---

## Agent behavior rules

### CODER

1. Only act when `to_role: CODER` **and** status is `ready_for_implementation` or `changes_requested`.
2. If `ACTIVE.md` is assigned to another role, **stop** and report the current owner and status.
3. After completing work, update `ACTIVE.md`:
   - Fill in `## Coder implementation report`.
   - Set `status: ready_for_review`, `from_role: CODER`, `to_role: REVIEWER`.
   - Set `branch:` and `pr:` if applicable.
   - Update `updated_at:`.

### REVIEWER

1. Only act when `to_role: REVIEWER` **and** status is `ready_for_review`.
2. If `ACTIVE.md` is assigned to another role, **stop** and report the current owner and status.
3. After reviewing, update `ACTIVE.md`:
   - Fill in `## Reviewer report`.
   - Set status to `changes_requested` (with blockers listed) or `approved`.
   - Set `from_role: REVIEWER`, `to_role: CODER` (if changes requested) or `to_role: HUMAN` (if approved).
   - Update `updated_at:`.

### Creating the initial handoff

The REVIEWER (or HUMAN) creates `ACTIVE.md` from a task discussion. The initial status is `ready_for_implementation` with `to_role: CODER`.

### Agents do not create parallel files

In MVP, both agents update the same `ACTIVE.md`. No parallel handoff files.

---

## Archiving

After final completion (merge, closure), the human archives the handoff:

```bash
mkdir -p .agent/handoffs/archive/
mv .agent/handoffs/ACTIVE.md .agent/handoffs/archive/H-YYYYMMDD-001.md
```

Or asks an agent to do it.

---

## Human commands

These are natural-language commands a human gives to agents:

### After discussing a task with reviewer:
> Create ACTIVE handoff for CODER from our discussion. Include task, background, acceptance criteria, constraints, and suggested test plan.

### To coder:
> Read ACTIVE handoff and implement the task.

### To reviewer after coder finishes:
> Read ACTIVE handoff and review the implementation.

### To coder after reviewer requests changes:
> Read ACTIVE handoff and fix reviewer blockers only.

### After reviewer approves:
> Mark ACTIVE handoff done and archive it.

---

## What this protocol does NOT do

- No multi-task queues or parallel handoffs.
- No automated Telegram notifications.
- No scheduler, heartbeat, or polling.
- No database, vector store, or task tracker.
- No changes to agent one-line prompts or bootstrap flow.
