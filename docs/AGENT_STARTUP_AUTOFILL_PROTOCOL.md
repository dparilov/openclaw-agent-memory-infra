# Agent Startup / Autofill Protocol (v1)

**Status:** active — applies to all agents using Project Memory Extractor v1.

This document defines the full startup sequence, autofill rules, private memory
handling, and the MEMORY STARTUP REPORT contract.

For operator-facing templates, see:
- `docs/PROJECT_START_TEMPLATE.md` — sent to agent to start or resume a project
- `docs/MEMORY_RULES_TEMPLATE.md` — universal agent rules (no per-project edits)

---

## Overview

Two commands. One startup sequence. One report.

```
refresh-memory   — ingest context → archive chunks → compile working memory drafts
recover-memory   — load working memory → print startup context
```

The agent (not the scripts) performs semantic autofill between refresh and recover.
Scripts never call LLM APIs.

---

## Startup sequence

```
SESSION START
  │
  ├─ 1. Infer role (coder / reviewer / infra)
  ├─ 2. Infer Telegram chat and topic from session metadata (if available)
  ├─ 3. Locate memory extractor at /home/dima/projects/openclaw-agent-memory-infra
  ├─ 4. Locate target project under /home/dima/projects/<project-name>/
  │      ├─ NOT FOUND + coder   → propose creation, wait for operator approval
  │      └─ NOT FOUND + reviewer/infra → report blocker, stop
  │
  ├─ 5. Check .agent/AGENT_CONTEXT.md
  │      └─ MISSING → create from bootstrap template, report CREATED
  │
  ├─ 6. Check working memory freshness
  │      └─ STALE (>24h) or MISSING or operator requested refresh?
  │           YES → go to step 7
  │           NO  → skip to step 10
  │
  ├─ 7. refresh-memory (dry-run first, then write if PASS)
  │      └─ FAIL → report blocker, stop
  │
  ├─ 8. Autofill working memory (mandatory — agent semantic step)
  │      ├─ Fill agent-brief.md
  │      ├─ Fill current-state.md
  │      └─ Fill known-issues.md
  │
  ├─ 9. Update private memory (if access/infra facts present)
  │      ├─ access.md
  │      ├─ credentials.md
  │      └─ infrastructure.md
  │
  ├─ 10. recover-memory
  │
  └─ 11. Return MEMORY STARTUP REPORT
```

---

## Step 7 — refresh-memory

```bash
# Dry-run first (always)
python3 /home/dima/projects/openclaw-agent-memory-infra/scripts/refresh-memory.py \
  --target /home/dima/projects/<project-dir> \
  --topic <topic-id>:<role> \
  --input <context-file> \
  --source-type <markdown_export|session_jsonl|operator_note>

# Write only if Archive step: PASS and Compile step: PASS
python3 /home/dima/projects/openclaw-agent-memory-infra/scripts/refresh-memory.py \
  --target /home/dima/projects/<project-dir> \
  --topic <topic-id>:<role> \
  --input <context-file> \
  --source-type <markdown_export|session_jsonl|operator_note> \
  --write
```

Telegram mode (explicit operator request only — never automatic):
```bash
python3 /home/dima/projects/openclaw-agent-memory-infra/scripts/refresh-memory.py \
  --target /home/dima/projects/<project-dir> \
  --topic <topic-id>:<role> \
  --read-topic \
  --chat-id <chat-id> \
  --limit 200 \
  --write
```

---

## Step 8 — Autofill working memory

This is a mandatory agent-performed semantic step. Do not leave placeholder files.

### What to fill

**`agent-brief.md`**
- Project identity: name, repo, purpose, stakeholders
- Active topics and roles
- Current objective (from context)
- Do-not-do rules (from MEMORY_RULES_TEMPLATE.md §9 + any project-specific rules)
- Memory load order
- Next useful actions (1–5 bullets, confirmed or inferred from context)

**`current-state.md`**
- Last updated timestamp
- Active branch / repo status (mark `[stale]` if not freshly verified)
- Recent completed work (with chunk source references)
- In-progress work
- Current blockers
- Relevant PRs / commits

**`known-issues.md`**
- Per issue: description, severity (`low` / `medium` / `high` / `critical`),
  status, source chunk, next action
- Mark contradictions as `needs_review`

### Autofill fact labels

| Label | When to use |
|---|---|
| `confirmed` | Directly stated in source — no inference |
| `inferred` | Derived from multiple sources; not explicitly stated |
| `stale` | May no longer be true; not freshly verified |
| `needs_review` | Contradiction detected between sources |

### Autofill constraints

- Do not invent facts not present in the source
- Do not include raw secrets — note `[REDACTED:<category>]` at category level only
- Keep files dense — no prose padding
- Replace ALL `<!-- TODO -->` placeholders before running recover-memory

---

## Step 9 — Private memory

### Location

```
<target>/.agent/memory/private/
  access.md
  credentials.md
  infrastructure.md
```

### access.md — allowed content

```markdown
## VPS / SSH access

- host: <hostname or IP>
- user: <ssh-username>
- command: ssh <user>@<host> -i <key-path>
- key location: <path-on-local-machine>
- config: <path to ssh config entry>
```

### credentials.md — allowed content

```markdown
## Token inventory

- <token-name>: purpose=<what it's used for>, location=<env file path or service>
- <token-name>: purpose=<what it's used for>, location=<env file path or service>
```

No raw token values. Name and purpose only.

### infrastructure.md — allowed content

```markdown
## Services

- <service-name>: port=<port>, url=<admin-url>, restart=<command>

## Deployment

- deploy command: <command>
- rollback: <command>

## Recovery

- <procedure name>: <steps>
```

### Private memory rules (summary)

- Never commit this directory — it is gitignored
- Never copy content into `working/*.md`, docs, PR descriptions, or commits
- When reporting: summarize category-level changes only
  - OK: "updated SSH access for vps-prod"
  - NOT OK: printing IP, username, or any credential value
- If chunks contain `[REDACTED:<category>]`, note the category only

---

## Step 10 — recover-memory

```bash
python3 /home/dima/projects/openclaw-agent-memory-infra/scripts/recover-memory.py \
  --target /home/dima/projects/<project-dir> \
  --topic <topic-id> \
  --role <role>
```

Reads only: `AGENT_CONTEXT.md` + `working/*.md`
Does not read: Telegram, raw chunks, index, candidates, wiki, vector DB

---

## Step 11 — MEMORY STARTUP REPORT

Return this report after every startup sequence:

```
MEMORY STARTUP REPORT

Role:          <coder|reviewer|infra>
Topic:         <topic-id>
Project:       <project-name>
Target path:   <absolute path>

Memory status:
  AGENT_CONTEXT.md:    OK | MISSING | CREATED
  agent-brief.md:      OK | MISSING | STALE | REFRESHED
  current-state.md:    OK | MISSING | STALE | REFRESHED
  known-issues.md:     OK | MISSING | STALE | REFRESHED
  decisions.md:        OK | MISSING | optional
  open-questions.md:   OK | MISSING | optional

Refresh:        SKIPPED | PASS | FAIL
Autofill:       SKIPPED | DONE | PARTIAL (<what was not filled>)
Private memory: SKIPPED | UPDATED (categories: <access|credentials|infrastructure>)
Recover:        PASS | FAIL

Current objective:   <one line from agent-brief.md>
Active blockers:     <N> — <severity of highest: low|medium|high|critical>
Next useful actions:
  - <action 1>
  - <action 2>
  - <action 3>

Warnings: <list or none>
```

---

## LLM policy

| Component | Calls LLM? |
|---|---|
| `refresh-memory.py` | NO |
| `recover-memory.py` | NO |
| `archive-context.py` | NO |
| `compile-working-memory.py` | NO |
| Agent (startup protocol) | YES — agent IS the LLM |

The agent performs:
- Role inference
- Project location
- Semantic autofill of `working/*.md`
- Private memory categorization and update
- MEMORY STARTUP REPORT generation

This is intentional. Scripts are deterministic. Semantic work is agent-performed.
No hidden API spend from scripts.

---

## What is NOT in this protocol

| Feature | Status |
|---|---|
| Coder/reviewer collaboration | Not in v1 |
| Multi-topic orchestration | Not in v1 |
| Full / unbounded read-topic | Not in v1 |
| Date ranges (`--since`, `--until`) | Not in v1 |
| Message ID ranges (`--since-id`, `--until-id`) | Not in v1 |
| Vector DB / embeddings | Not in v1 |
| OpenClaw memory-core | Not in v1 |
| Candidate promotion | Not in v1 |
| Wiki build | Not in v1 |
| Heartbeat / auto-refresh | Not in v1 |
| Auto-commit | Not in v1 |
| Remote GitHub repo creation | Requires explicit operator approval |
