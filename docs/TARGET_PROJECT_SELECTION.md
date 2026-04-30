# Target Project Selection

Before any `.agent/` scaffold or memory file is created, you must identify the
**target project** — the product repo being onboarded for agent memory.

This gate comes **after** environment gates A-J and **before** any setup writes.
No writes are permitted until this gate is complete and acknowledged.

---

## Three Concepts — Do Not Confuse Them

### 1. Installer / source repo

`dparilov/openclaw-agent-memory-infra`

- Contains: docs, scripts, templates, vendor, patches, tests
- Cloned once per machine; used as a reference throughout setup
- **Never** write per-installation state here by default
- **Never** create `.agent/` here by default
- Exception: only if operator explicitly issues `PROJECT_TARGET_ACK: mode=installer_repo_itself`

### 2. Target project repo

The product repo you are onboarding agents for.

- Example: `dparilov/olcRTC` at `~/projects/telemost/olcRTC`
- `.agent/AGENT_CONTEXT.md`, `config.yaml`, `tasks/`, `reviews/`, `decisions/` live here
- These files may be committed to the product repo via PR

### 3. Local runtime memory workspace

Ephemeral topic memory — never committed.

- Default: `<workspace-parent>/.agent/memory/topic-<id>.md`
- Example: `~/projects/telemost/.agent/memory/topic-7301.md`
- **Never** committed to any GitHub repo unless explicitly approved

---

## Two-Level Workspace Layout

The standard on-disk pattern observed in production:

```
~/projects/
  <project-parent>/                    <- workspace container (NOT a git repo)
    .agent/
      memory/
        topic-<coder-id>.md            <- local runtime memory ONLY
        topic-<reviewer-id>.md         <- local runtime memory ONLY
    <repo-name>/                       <- git repo (target project)
      .agent/
        AGENT_CONTEXT.md               <- committed to product repo (PR-gated)
        config.yaml                    <- committed to product repo (PR-gated)
        checkpoints/                   <- local only
        memory/candidates/             <- local only
        tasks/                         <- committed
        reviews/                       <- committed
        decisions/                     <- committed
        handoffs/                      <- committed
```

Example from 2026-04-30 cold test:

```
~/projects/telemost/                   <- workspace container
  .agent/memory/
    topic-7301.md                      <- coder runtime memory (local only)
    topic-13350.md                     <- reviewer runtime memory (local only)
  olcRTC/                              <- git repo (target project)
    .agent/
      AGENT_CONTEXT.md
      config.yaml
      memory/, tasks/, reviews/, ...
```

---

## Target Project Modes

### Mode A — New project

Repo does not yet exist. Wizard collects name, owner, local path, topics.
Instructs repo creation before any `.agent/` write.

ACK: `PROJECT_TARGET_ACK: mode=new repo=https://github.com/you/proj local_path=~/projects/proj`

### Mode B — Existing project (provided)

Operator supplies repo URL and/or local path directly.
Wizard verifies git remote, branch, `.agent/` status.
If `.agent/` exists (populated) -> read-only scaffold review before any write.

ACK: `PROJECT_TARGET_ACK: mode=existing path=~/projects/telemost/olcRTC repo=https://github.com/dparilov/olcRTC`

### Mode C — Existing project (discovered)

Operator provides only topic names/IDs. Wizard searches session history.
Must produce PROJECT TARGET DISCOVERY REPORT with evidence/confidence.
**No writes before PROJECT_TARGET_ACK.**

```
PROJECT TARGET DISCOVERY REPORT
  Candidate: ~/projects/telemost/olcRTC
  Evidence:
    - topic 7301 session history (12 refs)
    - git remote: https://github.com/dparilov/olcRTC
    - .agent: exists (populated)
  Confidence: high
  Required: PROJECT_TARGET_ACK: mode=discovered accept=yes path=~/projects/telemost/olcRTC
```

ACK: `PROJECT_TARGET_ACK: mode=discovered accept=yes path=<path>`

### Mode D — Installer repo itself (exceptional)

Requires explicit confirmation.
ACK: `PROJECT_TARGET_ACK: mode=installer_repo_itself confirm=yes`

---

## Topic Resolution

**Primary key:** topic ID (integer from Telegram)
**Name matching:** case-insensitive, fuzzy — `Telemost_Review` = `Telemost_review` = `telemost review`

If ambiguous: `TOPIC_ACK: <label>=<id>`

```
TOPIC RESOLUTION REPORT
  Label            ID      Confidence  Source
  -----------------------------------------------
  OpenClaw_infra   15222   confirmed   Telegram metadata
  Telemost         7301    confirmed   session history
  Telemost_Review  13350   confirmed   TOPIC_ACK supplied
```

---

## Existing Scaffold Detection

Before writing anything to `.agent/`:

| `.agent/` state | Action |
|-----------------|--------|
| Missing | Propose creation from `.agent-template/` |
| Exists, empty | Populate `AGENT_CONTEXT.md` and `config.yaml` |
| Exists, populated | Read-only review; propose diff; wait for approval |

**Never overwrite existing `AGENT_CONTEXT.md` without operator approval of the diff.**

---

## Target Project Registration Form

```
=== TARGET PROJECT REGISTRATION ===
Mode:                  <new | existing_provided | existing_discovered | installer_repo_itself>
Project name:          ________________________________
Repo URL:              ________________________________
Local path:            ________________________________
Workspace parent:      ________________________________
Default branch:        ________________________________
Telegram chat ID:      ________________________________
Coder topic ID:        ________________________________
Reviewer topic ID:     ________________________________
Infra topic ID:        ________________________________
.agent/ status:        <missing | exists_empty | exists_populated>
```

Submit as: `PROJECT_TARGET_ACK: mode=<mode> path=<local_path> repo=<repo_url>`

---

## Write Rules

| Action | Before ACK | After ACK |
|--------|-----------|-----------|
| Read installer repo docs | yes | yes |
| Read target project files | yes | yes |
| Write local runtime memory | no | yes |
| Write target project `.agent/` | no | yes (with further approval) |
| Write installer repo `.agent/` | no | only mode D |
| Commit to product repo | no | only via PR, explicit approval |
| Commit runtime memory to GitHub | no | no (never by default) |
