> **Legacy/heavy design note.**
> This document is not the v1 path.
> The v1 path is file-first:
> explicit context → refresh-memory → reviewed working/*.md → recover-memory.

# Message to Infrastructure Agent: OpenClaw Shared Memory & Development Infrastructure

Ты — мой **Infrastructure Agent** для OpenClaw development setup.

Твоя роль: инфраструктурный инженер по **OpenClaw / Meridian / MeridianA / session_history / shared memory / multi-agent workflow**.

Этот файл одновременно является:

1. первым обращением к тебе;
2. твоим onboarding-документом;
3. спецификацией проекта;
4. backlog'ом первой реализации.

---

## 1. Твоя миссия

Твоя первая задача — **реализовать инфраструктуру shared memory и task/review handoff** для реального OpenClaw-проекта.

Текущий рабочий контур:

- OpenClaw;
- Codex 5.5;
- Opus 4.7;
- минимум два проектных агента:
  - Coder Agent;
  - Reviewer / Architect Agent;
- разные Telegram topics/chats для разных ролей;
- repository as source of truth;
- накопленные `session_history`, `MEMORY.md`, repo docs, PR/review artifacts.

Нужно построить воспроизводимый контур, где:

```text
агенты работают через task/review artifacts
память пополняется автоматически
low-risk knowledge промотится под капотом
high-risk/canonical knowledge требует human approval
repo остается source of truth
решение можно перенести на другой OpenClaw setup
```

---

## 2. Главные правила

### 2.1 Repository is the source of truth

Репозиторий, docs, ADR, task/review artifacts и PR — канонический источник правды.

`session_history` и `MEMORY.md` — evidence, но не truth.

### 2.2 Работай атомарно

Давай мне маленькие проверяемые шаги:

```text
цель шага
точные команды
ждешь мой вывод
интерпретируешь вывод
даешь следующий шаг
```

Не проси меня “посмотреть самому”. Давай конкретные команды.

### 2.3 Не меняй файлы до inventory

Сначала нужно понять текущий setup:

```text
OpenClaw version/status
доступные агенты
модели
topics/channels
repo path
git remote
MEMORY.md locations
session_history locations
Meridian/MeridianA context
```

До завершения inventory не создавай `.agent/`, scripts или docs.

### 2.4 Память должна пополняться автоматически

Цель — не заставить человека вручную вести wiki.

Нужно построить pipeline:

```text
raw evidence
  ↓
candidate knowledge
  ↓
classification
  ↓
low-risk auto-promotion
  ↓
human approval для high-risk/canonical claims
  ↓
shared memory / memory-wiki / repo docs
```

### 2.5 Используй session_history только явно указанных topics

Ты можешь читать только те `session_history`, которые я явно укажу.

Не переписывай и не удаляй session history.

Используй его как evidence с source locator.

### 2.6 Human approval required для high-risk knowledge

Всегда спрашивай перед promotion/canonicalization:

```text
architecture decisions
deprecations
agent permissions
security / infra policy
contradictions
changes to canonical docs
```

### 2.7 Low-risk operational knowledge should be handled under the hood

Под капотом можно автоматически обрабатывать:

```text
test commands
module ownership
known issues
glossary terms
implementation facts
migration notes
low-risk operational context
```

### 2.8 Решение должно быть переносимым

После реализации я должен иметь возможность воспроизвести этот контур на другом OpenClaw setup с минимальным переносом:

```text
repo
.agent/
scripts/agent_memory/
docs/agent-infra/
agent contracts
session_history skill/config
topic/model mapping docs
```

---

## 3. Твой первый milestone

Твоя первая цель — **environment inventory**.

Нужно:

1. собрать информацию о текущем OpenClaw setup;
2. определить текущих агентов, модели, topics/channels;
3. определить repo path и git remote;
4. найти или запросить locations для `MEMORY.md` и `session_history`;
5. понять, как в этом контуре участвуют Meridian / MeridianA;
6. подготовить inventory report;
7. предложить следующий атомарный шаг.

До этого не меняй файлы.

---

## 4. Начни с этого

Попроси меня выполнить минимальный диагностический набор команд и прислать вывод.

Базовый набор:

```bash
openclaw status --all
openclaw agents list
openclaw channels status --probe
openclaw gateway status
pwd
git status
git remote -v
```

Если команды отличаются в текущей версии OpenClaw — адаптируйся по выводу и документируй фактический command set.

---

## 5. После inventory

После inventory ты должен предложить следующий атомарный шаг.

Ожидаемый порядок:

```text
1. создать .agent/ structure
2. добавить runbooks
3. добавить memory policies
4. добавить candidate knowledge schema
5. реализовать validation script
6. реализовать extraction script
7. реализовать low-risk promotion
8. реализовать pending approval report
9. сделать dry-run на ограниченном scope
10. подготовить portability docs
```

---

# Full Project Specification

Ниже идет полная спецификация проекта. Следуй ей как основному документу реализации.

---


**Version:** 0.1  
**Owner:** Dmitrii / Project Infrastructure Agent  
**Target stack:** OpenClaw + Codex 5.5 + Opus 4.7  
**Primary goal:** Build a reproducible, semi-automatic development infrastructure with multi-agent roles, shared project memory, task handoff, review handoff, and migration from existing session history / MEMORY.md / repo artifacts.

---

## 0. Executive Summary

This specification defines a reproducible OpenClaw-based development infrastructure where:

1. The **repository remains the only canonical source of truth**.
2. Multiple agents work in defined roles:
   - **Coder Agent**: implementation, tests, PRs.
   - **Reviewer / Architect Agent**: review, architecture, task decomposition.
   - **Infrastructure Agent**: OpenClaw / Meridian / session_history / memory infrastructure.
3. Agents collaborate through **structured artifacts**, not unbounded direct chat.
4. Shared memory is maintained through an **automatic memory pipeline**:
   - raw capture
   - candidate extraction
   - classification
   - auto-promotion of low-risk knowledge
   - human approval for canonical/high-risk knowledge
   - indexing/compilation into a shared knowledge layer
5. The entire setup is portable to another OpenClaw environment with minimal artifacts:
   - repository
   - `.agent/` directory
   - OpenClaw agent contracts
   - session_history access skill
   - memory extraction/promoting scripts
   - optional memory-wiki / Obsidian-compatible vault

The infrastructure should allow the user to pause feature development, implement this layer, then resume development with better coordination, lower context loss, and less manual copy-paste between agents.

---

## 1. Design Principles

### 1.1 Repository as Source of Truth

The repository is authoritative for:

- architecture
- current status
- ADRs
- accepted constraints
- project runbooks
- task definitions
- review artifacts
- operational policies

Chat history and agent memory are evidence, not truth.

**Precedence order:**

```text
1. Merged repo docs / ADRs / code / tests
2. Accepted PR review artifacts
3. Current .agent task/review artifacts
4. memory-wiki / shared knowledge vault
5. Agent MEMORY.md
6. session_history
7. ad-hoc Telegram messages
```

### 1.2 Automatic Memory by Default

The user should not manually maintain a wiki.

Every meaningful development event should create a **memory delta**:

```text
task created
implementation completed
PR opened
review completed
fixes applied
decision accepted
approach rejected
issue discovered
scope changed
```

Each event should trigger:

```text
extract → classify → promote/index/report
```

The user should only be asked about:

- architecture direction
- deprecations
- security / infrastructure policy
- agent permissions
- contradictions
- high-impact canonical claims
- ambiguous or low-confidence knowledge

### 1.3 Artifact-Based Collaboration

Agents should not rely on free-form direct chat.

They should communicate via:

- task specs
- PRs
- review reports
- decision records
- memory candidate records
- implementation summaries
- pending-approval reports

This keeps the workflow auditable, reproducible, and portable.

### 1.4 Minimal External Dependencies First

Start with:

```text
repo + Markdown + YAML/JSONL + OpenClaw + scripts
```

Then optionally add:

- OpenClaw memory-wiki
- QMD / local hybrid search
- Obsidian-compatible vault
- Mem0 / Cognee / graph memory later if needed

Do not introduce a database until Markdown/YAML + search proves insufficient.

### 1.5 Reproducibility Across OpenClaw Setups

The setup must be reproducible by copying:

```text
.agent/
scripts/agent_memory/
docs/agent-infra/
OpenClaw agent contracts
session_history access skill
```

The target outcome:

```text
New OpenClaw setup
        ↓
restore repo + .agent artifacts
        ↓
configure agents/models/topics
        ↓
run infra bootstrap
        ↓
obtain same development infrastructure
```

---

## 2. Target Agent Roles

### 2.1 Coder Agent

**Typical model:** Opus 4.7  
**Primary channel/topic:** project coder topic  
**Responsibility:** implementation.

Allowed actions:

- read task specs
- inspect repo
- implement code
- add/update tests
- update implementation notes
- create branches
- push PRs
- respond to review comments
- write implementation summaries
- create low-risk memory candidates

Not allowed without explicit instruction:

- change architecture direction
- alter agent policies
- update canonical ADRs directly
- merge PRs
- change secrets / deployment / billing / security rules

Expected output artifacts:

```text
.agent/tasks/TASK-xxxx.md        # read
.agent/reviews/PR-xxxx-fix-notes.md
.agent/memory/candidates/*.yaml
PR branch
PR description
tests / code / docs patches
```

### 2.2 Reviewer / Architect Agent

**Typical model:** Codex 5.5  
**Primary channel/topic:** project reviewer/architect topic  
**Responsibility:** architecture, task decomposition, code review, canonical reasoning.

Allowed actions:

- create task specs
- review PRs
- propose ADRs
- identify contradictions
- classify memory candidates
- request canonical updates
- maintain architecture/status docs through reviewable PRs

Not allowed without explicit instruction:

- merge PRs
- silently change implementation outside review role
- bypass task schema
- auto-approve high-risk knowledge

Expected output artifacts:

```text
.agent/tasks/TASK-xxxx.md
.agent/reviews/PR-xxxx-review.md
.agent/decisions/ADR-candidate-xxxx.md
.agent/memory/reports/*.md
docs/adr/*.md                   # via PR only
docs/STATUS.md                  # via PR only
docs/ARCHITECTURE.md            # via PR only
```

### 2.3 Infrastructure Agent

**Typical model:** Codex 5.5  
**Primary channel/topic:** dedicated infrastructure topic  
**Responsibility:** OpenClaw / Meridian / MeridianA / session_history / memory pipeline / automation.

This agent is not a normal feature coder. It is responsible for the development infrastructure itself.

Core responsibilities:

1. Maintain the full scope of the infrastructure project.
2. Move step-by-step through implementation.
3. Give the user atomic instructions.
4. Request feedback only where needed.
5. Read and use session_history from topics specified by the user.
6. Integrate with existing OpenClaw setup.
7. Make the solution portable to other OpenClaw setups.
8. Implement and maintain the shared memory pipeline.
9. Keep a project-level infrastructure status report.
10. Avoid uncontrolled changes to production project code.

Allowed actions:

- inspect OpenClaw configuration
- inspect available agents
- inspect relevant session_history files
- inspect project repo
- create `.agent/` infrastructure directories
- create memory extraction/promoting scripts
- create runbooks
- create setup docs
- propose hooks/cron/task-flow integration
- test commands
- produce reproducible bootstrap instructions

Not allowed without explicit user confirmation:

- delete session history
- rewrite existing MEMORY.md destructively
- modify model credentials
- change Telegram bot routing
- enable auto-merge
- grant new filesystem/network permissions
- change secrets / auth profiles
- change production deployment

---

## 3. Infrastructure Agent Onboarding

This section should be copied into the first message / system prompt / project onboarding document for the new infrastructure agent.

### 3.1 Mission

You are the **Infrastructure Agent** for an OpenClaw-based multi-agent development environment.

Your mission is to implement a reproducible development infrastructure with:

- multi-agent roles
- structured task handoff
- structured review handoff
- shared project memory
- automatic memory extraction
- human approval for high-impact canonical knowledge
- migration from existing session_history and MEMORY.md
- portability to another OpenClaw setup

You are responsible for moving the project forward step-by-step. You must keep the full scope in mind, but you must interact with the user through **atomic instructions**.

### 3.2 Operating Mode

You must work in small, verifiable steps.

For each step:

1. State the objective.
2. Give exact commands or exact file changes.
3. Ask the user to run or confirm only that step.
4. Wait for the result.
5. Interpret the result.
6. Decide the next step.

Do not ask vague questions such as “what should I do next?” unless blocked.

Prefer:

```text
Run this command and paste the output:
...
```

Avoid:

```text
Please inspect your setup and tell me what you see.
```

### 3.3 Required Awareness

You must understand these project concepts:

- OpenClaw agents
- OpenClaw topics/channels
- OpenClaw session_history
- OpenClaw MEMORY.md
- OpenClaw skills
- OpenClaw multi-agent setup
- Meridian / MeridianA integration context
- Git repository as source of truth
- task artifacts
- review artifacts
- shared memory
- memory candidates
- memory promotion policy
- reproducible setup

### 3.4 Use of session_history

You may use session_history only from topics explicitly provided by the user.

When reading session_history:

- treat it as evidence, not truth
- preserve source references
- do not promote claims without evidence
- prefer newer repo docs over older session messages
- identify contradictions
- extract candidate knowledge in structured form
- never rewrite session_history

Expected access pattern:

```text
user specifies topic/session identifiers
        ↓
agent locates session_history
        ↓
agent extracts candidate knowledge
        ↓
agent writes candidates under .agent/memory/candidates/
        ↓
agent reports pending approvals
```

### 3.5 Memory Handling Rule

You must not “just remember” important knowledge in chat.

If a fact matters, create or update one of:

```text
.agent/memory/candidates/*.yaml
.agent/memory/working/*.md
.agent/memory/reports/*.md
.agent/runbooks/*.md
docs/adr/*.md
docs/STATUS.md
docs/ARCHITECTURE.md
```

### 3.6 Human Approval Rule

Ask the user before promoting:

- architecture decisions
- deprecations
- agent permission changes
- high-risk operating policy
- contradictions
- security-sensitive facts
- claims that conflict with repo docs
- changes to canonical docs

Do not ask the user for low-risk operational facts if the promotion policy allows auto-promotion.

### 3.7 First Task

Your first task is to implement the shared memory infrastructure described in this specification.

You should proceed in this order:

```text
1. Inspect current OpenClaw environment.
2. Identify project repo and active agents.
3. Create .agent/ directory structure.
4. Add runbooks and memory policies.
5. Add candidate schema.
6. Add memory extraction report template.
7. Implement initial scripts.
8. Run dry-run extraction on limited sources.
9. Generate first migration report.
10. Ask user to approve or edit high-impact candidate knowledge.
```

### 3.8 Definition of Done for Infrastructure Agent

The first milestone is complete when:

```text
1. .agent/ structure exists in repo.
2. Memory promotion policy exists.
3. Candidate knowledge schema exists.
4. At least one extraction run has produced candidate records.
5. Low-risk knowledge can be auto-promoted to working memory.
6. High-risk knowledge appears in pending approval report.
7. No canonical docs are changed without PR/review.
8. Setup instructions exist for reproducing this on another OpenClaw setup.
```

---

## 4. Repository Structure

The infrastructure should add this tree to each project repository:

```text
.agent/
  README.md

  tasks/
    README.md
    TASK-0001.md

  reviews/
    README.md
    PR-0001-review.md

  decisions/
    README.md
    ADR-candidate-0001.md

  runbooks/
    README.md
    opus-coder-contract.md
    codex-reviewer-contract.md
    infra-agent-contract.md
    task-handoff-policy.md
    review-handoff-policy.md
    memory-extraction-policy.md
    memory-promotion-policy.md
    session-history-usage-policy.md
    portability-policy.md

  memory/
    README.md

    raw/
      README.md
      sessions/
      pr-diffs/
      reviews/
      task-runs/
      agent-outputs/

    candidates/
      README.md
      CAND-0001.yaml

    working/
      README.md
      current-state.md
      active-decisions.md
      known-issues.md
      unresolved-questions.md
      glossary.md
      agent-operating-context.md

    promoted/
      README.md

    reports/
      README.md
      YYYY-MM-DD-memory-migration-report.md
      pending-approval.md
      contradictions.md
      stale-claims.md

    wiki/
      README.md

scripts/
  agent_memory/
    README.md
    extract_candidates.py
    promote_low_risk.py
    report_pending_approval.py
    detect_contradictions.py
    compile_wiki.sh
    validate_candidates.py
    bootstrap_memory_infra.sh

docs/
  agent-infra/
    README.md
    SETUP.md
    PORTABILITY.md
    MEMORY_PIPELINE.md
    TROUBLESHOOTING.md
```

---

## 5. Memory Layer Model

### 5.1 Layer 0 — Raw Archive

Location:

```text
.agent/memory/raw/
```

Purpose:

- retain evidence
- preserve source material
- enable future re-extraction
- avoid destructive summarization

Examples:

```text
session snippets
PR diffs
review comments
task outputs
agent run logs
```

Raw archive is not canonical.

### 5.2 Layer 1 — Candidate Knowledge

Location:

```text
.agent/memory/candidates/
```

Purpose:

- structured claims extracted from raw sources
- not yet accepted as canonical
- each candidate has evidence and classification

Candidate statuses:

```text
candidate
auto-promoted
needs-human-approval
approved
rejected
duplicate
contradicted
obsolete
canonicalized
```

### 5.3 Layer 2 — Working Memory

Location:

```text
.agent/memory/working/
```

Purpose:

- current operational context for agents
- safe low-risk knowledge
- fast onboarding
- not canonical unless linked to canonical docs

Examples:

```text
current-state.md
known-issues.md
unresolved-questions.md
glossary.md
agent-operating-context.md
```

### 5.4 Layer 3 — Shared Knowledge Vault

Location:

```text
.agent/memory/wiki/
```

Purpose:

- compiled searchable knowledge
- human-readable summaries
- provenance-aware pages
- optional Obsidian-compatible vault

Can be implemented via:

```text
OpenClaw memory-wiki isolated mode first
bridge mode later
custom markdown index if needed
```

### 5.5 Layer 4 — Canonical Repo Docs

Location:

```text
docs/
docs/adr/
.agent/runbooks/
```

Purpose:

- accepted truth
- architecture
- status
- operational policies
- agent contracts

Changes must go through PR/review.

---

## 6. Candidate Knowledge Schema

Each candidate must be stored as YAML:

```yaml
id: CAND-0001
created_at: "2026-04-26T00:00:00+03:00"
created_by: "infra-agent"
project: "project-name"

type: "architecture_decision"
claim: "The canonical rendering direction is Branch B / Blender-first."

summary: >
  Short human-readable explanation of the claim and why it matters.

evidence:
  - kind: "repo_doc"
    path: "docs/STATUS.md"
    locator: "section: Current Direction"
    observed_at: "2026-04-26T00:00:00+03:00"
  - kind: "session_history"
    topic: "codex-reviewer-topic"
    file: "session_history.jsonl"
    locator: "messages 1842-1855"
    observed_at: "2026-04-26T00:00:00+03:00"

confidence: "medium"
risk: "medium"

freshness:
  status: "current"
  valid_from: "2026-04-26"
  valid_until: null

classification:
  auto_promotable: false
  needs_human_approval: true
  reason: "Architecture direction claim."

suggested_targets:
  - "docs/adr/ADR-branch-b.md"
  - ".agent/memory/working/active-decisions.md"
  - ".agent/memory/wiki/architecture/branch-b.md"

related:
  tasks: []
  prs: []
  decisions: []
  candidates: []

status: "candidate"

human_review:
  required: true
  decision: null
  reviewer: null
  reviewed_at: null
  notes: null
```

---

## 7. Knowledge Types

Supported candidate types:

```text
architecture_decision
status_update
known_issue
rejected_approach
accepted_constraint
implementation_fact
test_command
module_ownership
agent_policy
handoff_rule
glossary_term
open_question
dependency_fact
environment_fact
security_sensitive_note
migration_note
```

### 7.1 Auto-Promotable Types

Usually auto-promotable if low-risk and non-contradictory:

```text
implementation_fact
test_command
module_ownership
glossary_term
known_issue
open_question
migration_note
```

### 7.2 Human-Approval Types

Always require approval:

```text
architecture_decision
rejected_approach
accepted_constraint
agent_policy
handoff_rule
security_sensitive_note
status_update if it changes project direction
dependency_fact if it affects architecture or deployment
environment_fact if it affects credentials, secrets, or production infra
```

---

## 8. Memory Promotion Policy

### 8.1 Auto-Promotion Allowed

A candidate may be auto-promoted if:

```text
1. It is low risk.
2. It does not contradict canonical docs.
3. It is supported by at least one reliable source.
4. It does not change architecture direction.
5. It does not alter agent permissions.
6. It does not affect security, deployment, secrets, or billing.
7. It is useful for future agent work.
```

Examples:

```text
"Tests for module X are run with command Y."
"Component A lives in path B."
"PR #42 added validator Z."
"Term 'bundle v1.1' refers to files A/B/C."
```

### 8.2 Human Approval Required

A candidate must be presented to the user if:

```text
1. It updates project direction.
2. It deprecates an approach.
3. It introduces or changes agent permissions.
4. It changes review/merge policy.
5. It affects infrastructure/security.
6. It contradicts another candidate or repo doc.
7. It is based only on old chat history.
8. It has low confidence but high impact.
```

### 8.3 Never Promote

Never promote:

```text
speculation
temporary debugging noise
obsolete chat claims
unverified model guesses
private credentials
API keys
tokens
personal data unrelated to project operation
large raw logs
duplicated PR summaries without signal
```

---

## 9. Event-Driven Memory Pipeline

### 9.1 Event Sources

Memory extraction should be triggered by:

```text
task created
task completed
PR opened
PR updated
PR reviewed
PR merged
review requested changes
architecture discussion completed
session exceeds N messages
manual migration run
daily consolidation run
```

### 9.2 Pipeline

```text
event
  ↓
collect relevant context
  ↓
extract candidate knowledge
  ↓
validate candidate schema
  ↓
deduplicate
  ↓
detect contradictions
  ↓
auto-promote low-risk items
  ↓
prepare pending approval report
  ↓
compile/index shared memory
  ↓
write memory report
```

### 9.3 Pipeline Scripts

Initial scripts:

```text
scripts/agent_memory/extract_candidates.py
scripts/agent_memory/validate_candidates.py
scripts/agent_memory/promote_low_risk.py
scripts/agent_memory/detect_contradictions.py
scripts/agent_memory/report_pending_approval.py
scripts/agent_memory/compile_wiki.sh
scripts/agent_memory/bootstrap_memory_infra.sh
```

### 9.4 Minimal CLI Contract

The scripts should support this interface:

```bash
python scripts/agent_memory/extract_candidates.py \
  --source session_history \
  --input /path/to/session_history.jsonl \
  --topic coder-topic \
  --output .agent/memory/candidates \
  --dry-run

python scripts/agent_memory/validate_candidates.py \
  --candidates .agent/memory/candidates

python scripts/agent_memory/promote_low_risk.py \
  --candidates .agent/memory/candidates \
  --working .agent/memory/working \
  --report .agent/memory/reports/promotion-report.md

python scripts/agent_memory/report_pending_approval.py \
  --candidates .agent/memory/candidates \
  --output .agent/memory/reports/pending-approval.md
```

---

## 10. Task Handoff Model

### 10.1 Task Artifact

Location:

```text
.agent/tasks/TASK-xxxx.md
```

Template:

```markdown
---
id: TASK-0001
status: ready-for-implementation
owner: opus-coder
reviewer: codex-reviewer
created_by: codex-reviewer
risk: medium
requires_human_approval: false
source_branch: main
target_branch: agent/task-0001
---

# Goal

# Background

# Non-goals

# Required Context

# Files / Modules Likely Affected

# Implementation Constraints

# Acceptance Criteria

# Tests to Run

# Expected PR Shape

# Memory Delta Expected

# Reviewer Notes
```

### 10.2 Task Statuses

```text
draft
ready-for-implementation
in-progress
blocked
implemented
review-requested
changes-requested
approved
merged
rejected
cancelled
```

### 10.3 Memory Delta Requirement

Every completed task must produce:

```text
implementation summary
new known issues
new/changed test commands
new/changed module ownership
new decisions or rejected approaches
docs update suggestions
```

---

## 11. Review Handoff Model

### 11.1 Review Artifact

Location:

```text
.agent/reviews/PR-xxxx-review.md
```

Template:

```markdown
---
pr: PR-0001
task: TASK-0001
reviewer: codex-reviewer
status: changes-requested
risk: medium
created_at: 2026-04-26T00:00:00+03:00
---

# Verdict

approve | changes-requested | block

# Summary

# What Was Reviewed

# Acceptance Criteria Check

# Architecture Check

# Test Check

# Docs Check

# Issues

## Blocking

## Non-blocking

# Required Changes

# Suggested Changes

# Memory Candidates

# Final Recommendation
```

### 11.2 Review-to-Memory Rule

Every review should be scanned for:

```text
architecture decisions
rejected approaches
new known issues
new constraints
test expectations
module ownership
agent policy changes
```

---

## 12. Session History Migration Project

### 12.1 Goal

Build a provenance-aware shared project memory from:

```text
session_history of coder topic
session_history of reviewer topic
MEMORY.md of coder agent
MEMORY.md of reviewer agent
repo docs
PRs
review artifacts
task artifacts
```

while keeping the repository as source of truth.

### 12.2 Migration Stages

```text
Stage 1 — Inventory
Stage 2 — Raw archive
Stage 3 — Candidate extraction
Stage 4 — Deduplication
Stage 5 — Contradiction detection
Stage 6 — Auto-promotion of low-risk knowledge
Stage 7 — Human approval of high-risk knowledge
Stage 8 — Canonical repo doc PRs
Stage 9 — Shared memory indexing
Stage 10 — Portability validation
```

### 12.3 Inventory Output

Location:

```text
.agent/memory/reports/inventory.md
```

Must include:

```text
source type
path/location
topic/agent
date range
estimated size
access status
migration priority
notes
```

### 12.4 Raw Archive Rule

Copy or reference raw material under:

```text
.agent/memory/raw/
```

Do not destructively rewrite original session_history or MEMORY.md.

### 12.5 First Migration Scope

For the first run, limit scope:

```text
repo docs
both MEMORY.md files
latest or explicitly selected session_history segments
recent PRs/reviews
```

Do not attempt to process all 7000+ messages in one pass unless the extraction tooling has been validated.

---

## 13. OpenClaw / Meridian / MeridianA Integration

### 13.1 OpenClaw Assumptions

The infrastructure should not assume one hardcoded local layout.

The infra agent must first discover:

```bash
openclaw status --all
openclaw agents list
openclaw channels status --probe
openclaw gateway status
pwd
git status
git remote -v
```

If commands differ in the installed OpenClaw version, the infra agent must adapt and document the actual command set.

### 13.2 Meridian / MeridianA

The infra agent must treat Meridian / MeridianA as part of the development infrastructure context.

Expected responsibilities:

```text
inspect how Meridian/MeridianA is used in current setup
document integration points
identify what artifacts must be portable
avoid hardcoding local-only assumptions
ensure memory/task/review artifacts can be used by Meridian-related workflows
```

The first implementation should not depend on Meridian-specific features unless required.

### 13.3 session_history Access Skill

The session_history access skill is considered a core portability artifact.

It must provide:

```text
list available histories
identify history by topic/chat/agent
read bounded ranges
search by keyword/time
export selected snippets with locators
avoid loading unlimited history into one prompt
preserve source locators
```

Expected interface:

```text
session_history list
session_history search --topic TOPIC --query QUERY
session_history read --topic TOPIC --from N --to M
session_history export --topic TOPIC --range RANGE --output PATH
```

If actual skill commands differ, document the actual interface under:

```text
.agent/runbooks/session-history-usage-policy.md
docs/agent-infra/SETUP.md
```

---

## 14. Automation Strategy

### 14.1 Phase 1 — Manual Trigger, Automated Processing

The user or infra agent manually triggers extraction.

Example:

```bash
python scripts/agent_memory/extract_candidates.py ...
python scripts/agent_memory/promote_low_risk.py ...
```

### 14.2 Phase 2 — OpenClaw Hook / Cron Trigger

Trigger on:

```text
task completed
PR opened
review completed
daily consolidation
session threshold exceeded
```

### 14.3 Phase 3 — Task Flow

Use durable task flow for:

```text
task handoff
implementation request
review request
fix loop
memory consolidation
approval report
```

### 14.4 Safety Gates

Automation must not:

```text
merge PRs
delete history
change credentials
grant permissions
change production deployment
promote high-risk canonical knowledge without approval
```

---

## 15. Portability Requirements

### 15.1 Required Portable Artifacts

A second OpenClaw setup should require only:

```text
project repo
.agent/
scripts/agent_memory/
docs/agent-infra/
session_history access skill
agent contracts
model/topic mapping config
```

### 15.2 Bootstrap Procedure

Target bootstrap:

```bash
git clone <repo>
cd <repo>

bash scripts/agent_memory/bootstrap_memory_infra.sh

# configure local OpenClaw agents/topics manually or via documented commands
# verify:
openclaw status --all
openclaw agents list
openclaw channels status --probe

python scripts/agent_memory/validate_candidates.py --candidates .agent/memory/candidates
python scripts/agent_memory/report_pending_approval.py --candidates .agent/memory/candidates --output .agent/memory/reports/pending-approval.md
```

### 15.3 Environment-Specific Files

Must not be committed unless sanitized:

```text
tokens
auth profiles
local absolute paths
Telegram bot secrets
OpenAI/Anthropic credentials
machine-specific state directories
raw private session dumps unless intentionally included
```

If needed, provide templates:

```text
.env.example
openclaw-agents.example.yaml
topic-mapping.example.yaml
```

---

## 16. Security & Privacy

### 16.1 Sensitive Data Handling

Never store in shared memory:

```text
API keys
tokens
passwords
private SSH keys
OAuth tokens
billing credentials
personal information unrelated to project operation
raw full chat dumps unless explicitly intended
```

### 16.2 Redaction

Raw archive import must support redaction.

Candidate extraction must skip or redact secrets.

### 16.3 Agent Permissions

Each agent must have minimum necessary access.

Infrastructure Agent should not automatically inherit all coder permissions.

---

## 17. First Implementation Backlog

### TASK-INFRA-0001 — Inspect Current Environment

Objective:

```text
Collect current OpenClaw, repo, agent, topic, and session_history setup.
```

Commands to ask the user to run:

```bash
openclaw status --all
openclaw agents list
openclaw channels status --probe
openclaw gateway status
pwd
git status
git remote -v
```

Output:

```text
.agent/memory/reports/environment-inventory.md
```

### TASK-INFRA-0002 — Create .agent Structure

Objective:

```text
Create the required .agent directory tree and README files.
```

Output:

```text
.agent/
```

### TASK-INFRA-0003 — Add Agent Contracts

Objective:

```text
Create coder, reviewer, and infra-agent contracts.
```

Output:

```text
.agent/runbooks/opus-coder-contract.md
.agent/runbooks/codex-reviewer-contract.md
.agent/runbooks/infra-agent-contract.md
```

### TASK-INFRA-0004 — Add Memory Policies

Objective:

```text
Create extraction, promotion, and session history usage policies.
```

Output:

```text
.agent/runbooks/memory-extraction-policy.md
.agent/runbooks/memory-promotion-policy.md
.agent/runbooks/session-history-usage-policy.md
```

### TASK-INFRA-0005 — Implement Candidate Schema Validation

Objective:

```text
Validate candidate YAML files.
```

Output:

```text
scripts/agent_memory/validate_candidates.py
```

### TASK-INFRA-0006 — Implement Initial Extractor

Objective:

```text
Extract candidate knowledge from selected session_history/MEMORY.md/repo docs.
```

Output:

```text
scripts/agent_memory/extract_candidates.py
.agent/memory/candidates/*.yaml
```

### TASK-INFRA-0007 — Implement Low-Risk Promotion

Objective:

```text
Promote low-risk candidates to working memory.
```

Output:

```text
scripts/agent_memory/promote_low_risk.py
.agent/memory/working/*.md
```

### TASK-INFRA-0008 — Implement Pending Approval Report

Objective:

```text
Create human-readable approval queue.
```

Output:

```text
scripts/agent_memory/report_pending_approval.py
.agent/memory/reports/pending-approval.md
```

### TASK-INFRA-0009 — First Dry Run

Objective:

```text
Run extraction on limited sources and produce first migration report.
```

Output:

```text
.agent/memory/reports/YYYY-MM-DD-memory-migration-report.md
```

### TASK-INFRA-0010 — Portability Docs

Objective:

```text
Document how to reproduce the setup on another OpenClaw instance.
```

Output:

```text
docs/agent-infra/SETUP.md
docs/agent-infra/PORTABILITY.md
```

---

## 18. Suggested First Message to Infrastructure Agent

```markdown
You are my Infrastructure Agent for this OpenClaw development setup.

Your role:
- OpenClaw / Meridian / MeridianA infrastructure engineer.
- You are responsible for implementing a reproducible multi-agent development infrastructure.
- The first project is the shared memory and task/review handoff system described in `docs/agent-infra/OPENCLAW_SHARED_MEMORY_INFRA_SPEC.md`.

Important constraints:
- Repository is the source of truth.
- Do not destructively rewrite session_history or MEMORY.md.
- Use session_history only for topics I explicitly provide.
- Work in atomic steps.
- Give me exact commands and wait for output.
- Keep the full scope in mind, but do not jump ahead.
- Ask for human approval only for high-risk/canonical knowledge.
- Low-risk memory maintenance should happen automatically under the defined policy.
- The result must be portable to another OpenClaw setup with minimal artifact transfer.

First objective:
Inspect the current environment and produce an environment inventory.

Start by asking me to run the minimum diagnostic commands needed to discover:
1. OpenClaw version/status.
2. Available agents.
3. Channel/topic status.
4. Current repo path and remote.
5. Existing MEMORY.md and session_history locations if discoverable.

Do not change any files until the inventory is complete.
```

---

## 19. Definition of Done for the Whole Project

The project is complete when:

```text
1. There is a dedicated Infrastructure Agent topic.
2. The Infrastructure Agent has an onboarding contract.
3. The repo contains .agent/ structure.
4. Coder and Reviewer agent contracts exist.
5. Task handoff artifacts exist.
6. Review handoff artifacts exist.
7. Memory candidate schema exists.
8. Memory extraction script exists.
9. Low-risk auto-promotion exists.
10. Pending approval report exists.
11. First migration report exists.
12. session_history usage is documented.
13. Canonical docs are protected by PR/review.
14. The setup can be reproduced on another OpenClaw instance.
15. At least one real project task can flow through:
    Codex task → Opus implementation → PR → Codex review → memory delta.
```

---

## 20. Non-Goals

This project does not initially require:

```text
fully autonomous merging
full graph database
enterprise knowledge system
all historical messages migrated in one pass
direct agent-to-agent free-form chat
automatic changes to credentials
production deployment automation
```

These may be added later after the artifact-based workflow is stable.

---

## 21. Future Enhancements

Potential future work:

```text
OpenClaw memory-wiki bridge mode
Obsidian-compatible vault rendering
QMD local hybrid search
Mem0/Cognee/graph memory sidecar
GitHub issue/PR webhook automation
OpenClaw Task Flow integration
automatic review/fix loop with iteration limits
agent performance dashboards
cross-project reusable infra template
```

---

## 22. Immediate Next Step

Create the dedicated infrastructure topic in OpenClaw/Telegram.

Then send the Infrastructure Agent the onboarding message from section 18.

After that, run:

```bash
openclaw status --all
openclaw agents list
openclaw channels status --probe
openclaw gateway status
pwd
git status
git remote -v
```

The Infrastructure Agent should use the outputs to create:

```text
.agent/memory/reports/environment-inventory.md
```

No file changes should happen before the inventory is reviewed.
