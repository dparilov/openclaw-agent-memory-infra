# Bootstrap Prerequisites Checklist

Environment readiness check before onboarding a project into the OpenClaw memory system.

**This document is for external operators and external assistants.**
It is designed to be readable by any model outside OpenClaw (ChatGPT, Claude web, etc.).

---

## 1. Purpose

This checklist verifies that the environment is ready for project onboarding.

**This is NOT:**
- Project migration (see `docs/MEMORY_MIGRATION_PLAYBOOK.md`)
- Live-agent testing (see `docs/PRE_LIVE_CHECKLIST.md`)
- Memory extraction or archiving

**This IS:**
- A pre-flight check that must pass before any infra agent begins project setup
- A structured protocol an external assistant can follow without OpenClaw access
- A gate that produces an explicit READY / NOT READY verdict

---

## 2. Readiness Levels

| Level | Name | Meaning |
|-------|------|---------|
| **Level 0** | External review ready | The repo can be read by a human or external assistant |
| **Level 1** | Discovery ready | OpenClaw session_history and/or GitHub access are sufficient to discover project info from topic IDs |
| **Level 2** | Setup ready | The target project can be bootstrapped with `setup.sh` |
| **Level 3** | Migration ready | Existing project history can be inventoried and migrated safely |
| **Level 4** | Live-agent test ready | Coder / reviewer / infra agents can communicate, create tasks/PRs/reviews, and escalate to human |

Each higher level requires all lower levels to pass first.

---

## 3. Prerequisites Checklist

---

### A. Local Environment

Run each command and record output.

```bash
pwd
uname -a
python3 --version
python3 -c "import sys; assert sys.version_info >= (3,10); print(sys.version)"
python3 -c "import yaml; print('PyYAML OK')"
git --version
bash --version
```

**Expected:**
- Python 3.10 or higher
- PyYAML importable without error
- Git available
- Bash available

**Failure action:** Install missing tools before proceeding.

---

### B. openclaw-agent-memory-infra Repo

```bash
# If not already cloned:
git clone <memory-infra-repo-url>
cd openclaw-agent-memory-infra

git status --short --branch
python3 -m py_compile scripts/context_access/*.py
pytest -v --tb=short
bash setup.sh --help
```

**Expected:**
- Repo is on main or a known branch, no unexpected dirty state
- All scripts compile without errors
- Tests pass (or known acceptable skips are documented)
- `setup.sh --help` prints usage without error

**Failure action:** Fix compile errors or failing tests before proceeding.

---

### C. OpenClaw Runtime

Command names may vary by install. Use equivalent commands for your OpenClaw version.

```bash
openclaw status --all
openclaw doctor
openclaw gateway status
openclaw channels status --probe
openclaw models status
```

**Expected:**
- OpenClaw installed and responsive
- Gateway reachable
- Telegram channel configured (if project discovery uses Telegram topics)
- Required model aliases visible

**Note:** If command names differ in your installation, record the equivalent output and note the variant used.

---

### D. Model / Runtime Access

Fill in for your project configuration. No vendor is hardcoded — examples are illustrative only.

```
Infra agent model available:        yes / no / (model name)
Coder model/runtime available:      yes / no / (model name)
Reviewer model/runtime available:   yes / no / (model name)
Meridian/MeridianA available:       yes / no / not needed
OpenClaw OAuth/API auth works:      yes / no
```

**Example configurations (non-prescriptive):**
- Coder: Opus 4.7 via Meridian/MeridianA
- Reviewer: GPT-5.5 via OpenClaw OAuth
- Infra: any sufficiently capable model with shell / GitHub / OpenClaw access

**Failure action:** If a required model is unavailable, escalate to human before proceeding.

---

### E. Telegram / Topic Access

```
Infra topic ID known:                         yes / no → (ID)
Coder topic ID known:                         yes / no → (ID)
Reviewer topic ID known:                      yes / no → (ID)
Infra agent can read session_history:         yes / no
Pyrogram live read needed:                    yes / no / unknown
```

If Pyrogram is required:

```bash
python3 -c "import pyrogram; print('Pyrogram OK')"
```

**Note:** Pyrogram is NOT required for session_history-only discovery. Only check if the project policy explicitly requires live Telegram reads.

**Failure action:** If topic IDs are unknown, project is discovery-ready but not setup-ready.

---

### F. GitHub Access

```bash
git ls-remote <target-project-repo-url>
gh auth status
gh repo view <owner/repo>
```

If `gh` CLI is unavailable, confirm via GitHub UI or equivalent GitHub connector.

**Expected:**
- Can read the target repo
- Can create branches and PRs (if the agent will write)
- Can read PRs, comments, and diffs
- Merge policy is documented (squash-merge only / any / etc.)

**Failure action:** If read-only access is confirmed but write is missing, note as WARN — discovery is possible, setup may be blocked.

---

### G. Target Project Workspace

```bash
ls -la <workspace-path>
git clone <target-project-repo-url>   # if not already cloned
cd <target-project>
git status --short --branch
```

If the repo path is unknown, mark as **not setup-ready** but possibly **discovery-ready**.

**Expected:**
- Local path exists and is accessible
- Repo is on canonical branch or known working branch
- No unexpected dirty state

---

### H. Sensitive Data Posture

Answer each item:

```
Agents may detect secrets but must NOT copy secret values into memory:
  acknowledged: yes / no

Session history may contain access material:
  yes / no / unknown

Human escalation handle is known:
  yes / no → (@handle)

Policy for secret-containing batches:
  skip / manual review / redact / abort migration
```

**Failure action:** If policy is unknown, escalate to human before starting migration.

---

### I. Human Escalation

```
Human @handle:
```

**Always escalate to human for:**
- Repo path or target ambiguity
- Secrets or access material detected in session history
- Any failed P0 prerequisite
- Model or runtime unavailable
- GitHub auth missing
- OpenClaw topic access missing or ambiguous

---

## 4. Output Format

After completing the checklist, produce this report:

```markdown
# Bootstrap Prerequisites Report

Date:
Operator:
Environment:          (machine / OS / OpenClaw version)
Repo:                 (target project URL or path)

## Summary

Verdict:
- [ ] READY FOR PROJECT DISCOVERY   (Level 1)
- [ ] READY FOR PROJECT SETUP       (Level 2)
- [ ] READY FOR MIGRATION INVENTORY (Level 3)
- [ ] NOT READY — fix blockers first

## Checks

| Area                   | Status        | Evidence         | Notes |
|------------------------|---------------|------------------|-------|
| Local environment      | PASS/WARN/FAIL | command output  |       |
| Memory infra repo      | PASS/WARN/FAIL | command output  |       |
| OpenClaw runtime       | PASS/WARN/FAIL | command output  |       |
| Models / runtimes      | PASS/WARN/FAIL | evidence        |       |
| Telegram / topics      | PASS/WARN/FAIL | evidence        |       |
| GitHub access          | PASS/WARN/FAIL | evidence        |       |
| Target workspace       | PASS/WARN/FAIL | evidence        |       |
| Sensitive data posture | PASS/WARN/FAIL | policy          |       |
| Human escalation       | PASS/WARN/FAIL | @handle         |       |

## Blockers

(List each FAIL item with required fix action.)

## Warnings

(List each WARN item with recommended action.)

## Recommended next step

(One of: proceed to PROJECT_DISCOVERY / proceed to setup.sh / fix blockers / escalate to human)
```

---

## 5. Transition Rules

| Condition | Next step |
|-----------|-----------|
| Level 1 passes | Proceed to `docs/PROJECT_DISCOVERY_FROM_TOPICS.md` with topic IDs only |
| Level 2 passes | Infra agent may run `setup.sh` after Project Intake draft is confirmed |
| Level 3 passes | Proceed to `docs/MEMORY_MIGRATION_PLAYBOOK.md` M0/M1 |
| Any P0 prerequisite fails | **Stop.** Do not start project onboarding. Escalate to human if unclear. |

**P0 prerequisites** (blocking):
- Python 3.10+
- PyYAML available
- Memory infra repo scripts compile
- Human escalation handle known

**P1 prerequisites** (warn, not blocking for discovery):
- OpenClaw runtime reachable
- GitHub write access
- Target workspace cloned

---

## 6. How to Use This with an External Assistant

If you are using an external model (ChatGPT, Claude web, Gemini, etc.) to walk through this checklist, use the following prompt:

---

```
I want you to act as an external onboarding operator for this repo.

Read docs/BOOTSTRAP_PREREQUISITES.md.

Walk me through the checklist one area at a time (A through I).

For each area:
1. Tell me exactly what command to run or what evidence to provide.
2. Wait for my answer.
3. Mark PASS, WARN, or FAIL with a brief reason.
4. Continue to the next area.

After all areas are complete, produce the Bootstrap Prerequisites Report with a final verdict:
- READY FOR PROJECT DISCOVERY
- READY FOR PROJECT SETUP
- READY FOR MIGRATION INVENTORY
- NOT READY

Do not proceed to project onboarding until you explicitly state that prerequisites are satisfied.
```

---

## 7. Relationship to Other Docs

**Document order for a new project:**

```
docs/BOOTSTRAP_PREREQUISITES.md          ← you are here
  → docs/PROJECT_DISCOVERY_FROM_TOPICS.md
  → docs/PROJECT_INTAKE_QUESTIONNAIRE.md  (confirmation)
  → setup.sh
  → docs/PRE_LIVE_CHECKLIST.md
  → docs/MEMORY_MIGRATION_PLAYBOOK.md
  → docs/AGENT_COLLABORATION_PROTOCOL.md  (live agent tests)
```

**Reference docs:**

| Doc | Purpose |
|-----|---------|
| `docs/PROJECT_DISCOVERY_FROM_TOPICS.md` | Discover project state from OpenClaw topics |
| `docs/PROJECT_INTAKE_QUESTIONNAIRE.md` | Structured intake for new projects |
| `docs/MEMORY_MIGRATION_PLAYBOOK.md` | Safe staged memory migration |
| `docs/AGENT_COLLABORATION_PROTOCOL.md` | Reviewer / coder / infra collaboration flow |
| `docs/HUMAN_COMMAND_CHEAT_SHEET.md` | Daily operator quick-reference |
| `docs/PRE_LIVE_CHECKLIST.md` | Pre-live checklist before live agent tests |
