> **Legacy/heavy design note.**
> This document is not the v1 path.
> The v1 path is file-first:
> explicit context → refresh-memory → reviewed working/*.md → recover-memory.

# Setup Wizard Flow

This is the canonical setup UX for onboarding a new project into OpenClaw agent memory.

> **The infra agent handoff is no longer the default setup path.**
> It is an optional fallback/escalation path.
> See `docs/EXTERNAL_TO_INFRA_HANDOFF.md` for when to use it.

The wizard can be driven by an external GPT assistant, a future local CLI wizard,
or the infra agent in escalation mode.

---

## Overview

```
Phase 0 -- Repo orientation
Phase 1 -- Environment readiness (gates A-J + optional Gate S)
Phase 2 -- Target project selection
Phase 3 -- Topic resolution
Phase 4 -- Scaffold review or creation
Phase 5 -- Runtime memory boundary
Phase 6 -- Config activation
Phase 7 -- Automatic initial indexing
Phase 8 -- Final agent instruction pack
Phase 9 -- Live readiness check
```

At the end of each phase, the wizard presents one of four choices:

```
  CONTINUE WITH PR      -- proceed; gate any repo commits behind a PR
  CONTINUE LOCAL ONLY   -- proceed; no repo commits
  SHOW DETAILS          -- expand all proposed changes before proceeding
  STOP                  -- pause; ask questions; or escalate to infra agent
```

---

## Path Selection — Choose Setup Mode

Before starting Phase 0, select the appropriate setup path. The wizard must present
these options and wait for explicit operator selection. It must not auto-select.

| Path | Label | When to use |
|------|-------|-------------|
| A | Full Environment Cold Start | First-time setup, or unknown/unverified environment state |
| B | Fast Project Onboarding | Environment recently verified; onboarding a new project |
| C | Repair / Resume | Previous wizard run left open blockers; known partial state |
| D | Audit Only | Read-only status check; no changes to be made |

**Path A** → run all phases (Phase 0 through Phase 9).
**Path B** → run Fast Preflight (see below) instead of full Phase 1, then skip to Phase 2.
**Path C** → load last known gate state; resume from first open blocker.
**Path D** → run Phase 0 and Phase 1 in read-only mode; produce audit report only.

### Fast Preflight (Path B)

Used when the environment was recently audited. Checks only:

1. memory-infra repo current (`git fetch --dry-run`; confirm branch/SHA)
2. OpenClaw gateway reachable (`openclaw status`)
3. Telegram transport healthy (bot polling `in:just now`)
4. GitHub auth valid (`gh auth status`)
5. Required role models available and authenticated (`openclaw models status`)
6. Security ACK still valid (issued within last 30 days; environment/groupPolicy unchanged)

**Hard rule:** Target repo is NOT checked in Fast Preflight. It is checked only after
`PROJECT_TARGET_ACK` in Phase 2.

If any Fast Preflight check fails → run full Phase 1 for the failing gate, or escalate to Path C.

---

## Phase 0 -- Repo Orientation

**Goal:** Confirm the operator understands what this repo is and is not.

Wizard output:
```
This repo: openclaw-agent-memory-infra
Role: installer / source of truth

Contains: docs, scripts, templates, vendor (MeridianA), patches, tests.
This is NOT a target project repo.
Do not write per-installation state here.

Your target project is a separate product repo.
You will select it in Phase 2.
```

Stop condition: None. Always proceeds to Phase 1.

---

## Phase 1 -- Environment Readiness

> **HARD RULE: Phase 1 is target-project agnostic.**
> No product repo URL, branch, `.agent/` scaffold status, topic role assumptions, or
> project-specific blocker language may appear in Phase 1 output before `PROJECT_TARGET_ACK`
> is issued in Phase 2. Gates B2/C check the memory-infra repo only. Any other repo is Phase 2+.

**Goal:** All gates A-J pass (Gate S optional).

**Follow:** `docs/FULL_ENVIRONMENT_ONBOARDING.md` gate by gate.

| Gate | Name | Blocker? |
|------|------|----------|
| A | OS baseline | yes |
| B | System packages | yes |
| B2 | GitHub CLI | yes |
| C | GitHub auth | yes |
| D | Installer repo cloned | yes |
| E | OpenClaw installed | yes |
| F | Telegram integration | yes |
| G | Model providers | yes |
| H | Codex OAuth | no (N/A if not using Codex); see `docs/OAUTH_GATE_CARDS.md` OA-4 to OA-7 |
| I | MeridianA install | no (N/A if not using meridiana/* aliases) |
| J | Topic planning | yes |
| S | Security (groupPolicy) | no (CRITICAL items require ACK) |

**Gate S:** If groupPolicy=open with elevated/runtime/filesystem tools: flag CRITICAL.
Wizard does not offer CONTINUE until: `ACK: groupPolicy=accept`

Phase 1 completion prompt:
```
ENVIRONMENT GATES COMPLETE
  A B B2 C D E F G H I J: all pass
  Open issues: <list or none>

  CONTINUE WITH PR    -> target project selection
  SHOW DETAILS        -> full gate log
  STOP                -> pause here
```

---

## Phase 2 -- Target Project Selection

**Goal:** Identify the product repo. Prevent writes to installer repo.

**Read:** `docs/TARGET_PROJECT_SELECTION.md` for full mode definitions and ACK formats.

Wizard actions:
1. Ask operator for repo/path or topic IDs
2. Determine mode: A (new), B (provided), C (discovered), D (installer itself)
3. If mode C: search session history; produce PROJECT TARGET DISCOVERY REPORT
4. Detect `.agent/` status in target
5. Collect all three topic IDs

Required ack before any write:
```
PROJECT_TARGET_ACK: mode=<mode> path=<local_path> repo=<repo_url>
```

Stop condition: No writes performed until PROJECT_TARGET_ACK received.

Phase 2 completion prompt:
```
TARGET PROJECT CONFIRMED
  Repo:     <name>
  Path:     <local path>
  Mode:     <new|existing|discovered>
  .agent/:  <exists-populated | exists-empty | missing>
  Topics:   coder=<id>  reviewer=<id>  infra=<id>

  CONTINUE            -> topic resolution
  SHOW DETAILS        -> full registration
  STOP                -> pause here
```

---

## Phase 3 -- Topic Resolution

**Goal:** Map topic labels to numeric Telegram IDs for all three roles.

Rules:
- Topic ID is the primary key (integer)
- Name matching: case-insensitive, fuzzy, underscore/space/hyphen interchangeable
- If ambiguous: require `TOPIC_ACK: <label>=<id>`

Wizard output:
```
TOPIC RESOLUTION REPORT
  Label            ID      Confidence  Source
  -----------------------------------------------
  OpenClaw_infra   15222   confirmed   Telegram metadata
  Telemost         7301    confirmed   session history
  Telemost_Review  13350   confirmed   TOPIC_ACK supplied
```

Stop condition: All three topic IDs confirmed before Phase 4.

---

## Phase 4 -- Scaffold Review or Creation

**Goal:** Ensure target project has a valid `.agent/` scaffold. Always read before write.

### If `.agent/` does NOT exist

Propose creation from `.agent-template/`:
```
SCAFFOLD CREATION PLAN
  <target>/.agent/AGENT_CONTEXT.md     <- from template + project registration
  <target>/.agent/config.yaml          <- paths commented out (activated Phase 6)
  <target>/.agent/memory/              <- empty
  <target>/.agent/tasks/               <- empty
  <target>/.agent/reviews/             <- empty
  <target>/.agent/decisions/           <- empty
  <target>/.agent/handoffs/            <- empty
  <target>/.agent/checkpoints/         <- empty
  <target>/.agent/tools/               <- copied from .agent-template/tools/

  CONTINUE WITH PR    -> create scaffold, commit via PR
  CONTINUE LOCAL ONLY -> create scaffold, do not commit
  SHOW DETAILS        -> see full file contents before write
  STOP                -> pause here
```

### If `.agent/` EXISTS (populated)

Read-only first. Produce SCAFFOLD REVIEW REPORT:
```
SCAFFOLD REVIEW REPORT
  AGENT_CONTEXT.md: exists (N lines, last updated <date>)
  Topic IDs match registration: yes/no
  config.yaml: exists, all values commented out (needs Phase 6 activation)
  memory/: <N files or empty>

Proposed diff:
  - update topic registry if IDs differ
  - activate config.yaml in Phase 6
  - no structural changes required

  CONTINUE            -> proceed with diff proposal
  SHOW DETAILS        -> see full file contents
  STOP                -> pause here
```

**Never overwrite existing AGENT_CONTEXT.md without operator approval.**

---

## Phase 5 -- Runtime Memory Boundary

**Goal:** Create local-only topic memory seed files. Nothing committed.

Wizard creates (local only, never git-tracked):
```
<workspace-parent>/.agent/memory/topic-<coder-id>.md      <- batch-0 seed
<workspace-parent>/.agent/memory/topic-<reviewer-id>.md   <- batch-0 seed
```

Wizard confirms:
```
RUNTIME MEMORY BOUNDARY
  Seeds created (local only):
    topic-<coder-id>.md
    topic-<reviewer-id>.md
  NOT in installer repo. NOT committed to product repo.
```

---

## Phase 6 -- Config Activation

**Goal:** Activate `config.yaml` in target project scaffold.

Proposed values:
```yaml
pyrogram_session: <absolute-path>/userbot   # without .session extension
checkpoint_dir:   <target>/.agent/checkpoints
agents_base:      ~/.openclaw/agents
```

After writing, wizard **immediately reads back** the file and compares.

If readback matches -> CONFIG ACTIVATED.

If readback does not match -> **STOP. Do not proceed.**
```
CONFIG ACTIVATION AMBIGUOUS
  Write reported success but readback shows original content.
  Please verify: cat <target>/.agent/config.yaml
  Reply CONFIG_VERIFIED to proceed, or STOP to pause.
```

Operator must confirm before Phase 7.

---

## Phase 7 -- Automatic Initial Indexing

**Goal:** Run initial-index.py. Do NOT force manual candidate promotion during setup.

If Pyrogram session available at config path:
```bash
python3 <target>/.agent/tools/context_access/initial-index.py \
  --topic <coder-id> --output <target>/.agent/memory/index/
```

Outputs are local only (not committed). Sensitive categories detected, not values.

If Pyrogram session unavailable:
```
INDEXING SKIPPED
  Run manually later: /recover-memory
  Candidate promotion happens during real work sessions, not setup.
```

No manual L1 candidate extraction during setup.

---

## Phase 8 -- Final Agent Instruction Pack

**Goal:** Generate ready-to-send prompts for each agent role.

See `docs/FINAL_AGENT_INSTRUCTION_PACK.md` for full templates.

```
SETUP COMPLETE -- Agent Instruction Pack Ready

  SHOW INFRA PROMPT      -> paste to OpenClaw_infra topic
  SHOW CODER PROMPT      -> paste to coder topic
  SHOW REVIEWER PROMPT   -> paste to reviewer topic
  SHOW HUMAN CHEAT SHEET -> keep for reference
```

Human cheat sheet:
```
START CODER      -- send coder first-session prompt to coder topic
START REVIEWER   -- send reviewer first-session prompt to reviewer topic
RECOVER MEMORY   -- run /recover-memory in relevant topic
ASK INFRA        -- send infra escalation prompt to infra topic
STOP             -- pause; infra agent will hold state
SHOW STATUS      -- ask any agent for current task status
```

---

## Phase 9 -- Live Readiness Check

**Goal:** Confirm all three agents are reachable and responding.

Sequence:
1. Human sends infra prompt to infra topic -> infra agent confirms context read
2. Human sends coder prompt to coder topic -> coder confirms project identity
3. Human sends reviewer prompt to reviewer topic -> reviewer confirms review policy
4. Human verifies MeridianA: `curl http://127.0.0.1:3470/v1/models`

Readiness criteria:
```
  Infra agent:    confirmed context read
  Coder agent:    confirmed context read, project identity correct
  Reviewer agent: confirmed context read, review policy confirmed
  MeridianA:      responding on port 3470
```

---

## Infra Agent Role -- Fallback and Escalation Only

The infra agent handles: post-setup memory operations, incident recovery, advanced
role changes, cross-topic orchestration, and cases where wizard cannot inspect local
runtime (e.g. remote operator).

**The infra agent is NOT the primary setup path.**

To escalate from wizard:
```
/handoff
TRIGGER: wizard-escalation
WIZARD STATE: Phase <N> -- <reason>
<paste wizard status block>
```

See `docs/EXTERNAL_TO_INFRA_HANDOFF.md`.

---

## Appendix: Gate Remediation Card Format

Every FAIL or WARN gate must output a remediation card in this exact format
(mark N/A for options that do not apply):

```
Remediation options:
A. Fix now — exact commands: ...
B. Mark N/A — condition: ...
C. Choose alternate model — command: ...
D. Continue with WARN — ACK required: ...
E. STOP — reason: ...
```

The wizard waits for operator selection. It does not auto-select.

For auth-specific remediation cards, see `docs/OAUTH_GATE_CARDS.md`.
For cold-run process findings, see `docs/COLD_TEST_FINDINGS_2026-05-04.md`.

---

## Quick Reference

| Action | Actor | Approval |
|--------|-------|----------|
| Environment gates | Human + wizard | gate pass/fail |
| Target project ack | Human | PROJECT_TARGET_ACK |
| Topic resolution | Wizard | TOPIC_ACK if ambiguous |
| Scaffold creation/review | Wizard | CONTINUE choice |
| Runtime memory seeds | Wizard | implicit in CONTINUE |
| Config activation | Wizard | CONFIG_VERIFIED |
| Repo commit | Wizard | CONTINUE WITH PR |
| Archive session facts | Infra agent | promote flow |
| Promote memory candidates | Infra agent | human approve |
