# Project Discovery From Topics

Protocol for infra agent to perform read-only discovery from OpenClaw session history,
starting from only three Telegram topic IDs.

---

## 1. Inputs

The human provides only:

```
Infra topic ID:             <id>
Coder topic ID:             <id>
Reviewer/Architect topic ID:<id>
Human escalation handle:    @<handle>
```

No other configuration is required to begin discovery. Setup does not start until the
human confirms the Project Intake Draft produced by this protocol.

---

## 2. Discovery Phase

The infra agent performs **read-only** discovery from OpenClaw `session_history` for
all three topics. No writes occur during discovery.

Targets to extract:

```
repo URL candidates          — from git commands, mentions of github.com URLs
local path candidates        — from cd, ls, file references in sessions
project name                 — from repo name, project mentions, topic names
role mapping                 — which sessions are coder / reviewer / infra
model/runtime hints          — from session metadata, @mentions, handoffs
active branches / PRs        — from git branch, gh pr, merge references
task / spec / review docs    — from .agent/tasks/, .agent/handoffs/ references
sensitive-data indicators    — tokens, passwords, API keys — detect presence only;
                               do not copy values into draft, memory, or candidates
```

Discovery reads:
- OpenClaw `session_history` JSONL for all three topic IDs
- Any `.agent/` files reachable from the local repo path (if one candidate is found)
- Recent commit history (read-only, `git log`)

Discovery does **not**:
- Write to memory, candidates, wiki, or any file
- Execute `setup.sh`
- Archive any batch
- Copy secret values anywhere

---

## 3. Project Intake Draft Format

The infra agent produces a draft in this exact format after discovery:

```
PROJECT INTAKE DRAFT
Generated: <ISO timestamp>

Project name:         <value> | confidence: <level>
Repo URL:             <value> | confidence: <level>
Local path:           <value> | confidence: <level>
Canonical branch:     <value> | confidence: <level>

Infra topic:          <id>
Coder topic:          <id>
Reviewer topic:       <id>

Coder runtime/model:  <value> | confidence: <level>
Reviewer runtime/model: <value> | confidence: <level>

Human escalation:     <handle>

Known active PRs/branches:
  <list or "none found">

Known docs/specs:
  <list of .agent/tasks/, .agent/handoffs/, relevant docs or "none found">

Sensitive-data warning:
  <"none detected" or "possible secrets found in <topic>; do not copy — escalate">

Missing fields:
  <list of fields not found, with discovery notes>

Confidence summary:
  <count> high / <count> medium / <count> low / <count> missing

Decision: GO to setup / NEED HUMAN CONFIRMATION
  <reason if NEED HUMAN CONFIRMATION>
```

The agent outputs this draft to the human and **waits for explicit confirmation** before
proceeding to any setup step.

---

## 4. Confidence Levels

| Level | Meaning |
|-------|---------|
| `high` | Multiple independent sources agree on the same value |
| `medium` | One strong source found (e.g., direct URL mention in session) |
| `low` | Weak hint only (e.g., partial path, ambiguous reference) |
| `missing` | Not found in any discovered source |

Fields with `low` or `missing` confidence must be listed under **Missing fields**
and the draft decision must be `NEED HUMAN CONFIRMATION`.

---

## 5. Sensitive Data Handling

Rules the infra agent must follow during discovery:

```
1. Detect presence of secrets, tokens, passwords, API keys in session history.
2. Do NOT copy secret values into the draft, memory files, candidates, wiki, or reports.
3. Record only: "possible secrets found in <topic/session reference>".
4. Escalate to human via @handle before setup if sensitive material is needed.
5. If secrets are found in session history that should NOT be in memory, flag this
   explicitly as a sensitive-data warning in the draft.
```

Escalation format for sensitive data:

```
@<handle> ESCALATION REQUIRED
Reason:           Sensitive material detected in session history during discovery.
Decision needed:  How to handle: exclude / redact / manual review before archive.
Options:          A) Skip affected batches  B) Manual review before archive  C) Abort discovery
Recommended:      B) Manual review before archive
Links:            <topic IDs where material was found>
Urgency:          high
```

---

## 6. Transition to Setup

Setup begins **only** after the human confirms the Project Intake Draft with an explicit
approval message (e.g., "confirmed", "proceed", "OK").

After confirmation:

1. Infra agent fills in `.agent/config.yaml` with confirmed values.
2. Infra agent runs `setup.sh --target <path> --install-scripts copy --test`.
3. Smoke test must pass before any memory operations begin.
4. Infra agent reports smoke result to human.
5. Memory migration (if applicable) follows `docs/MEMORY_MIGRATION_PLAYBOOK.md`.
