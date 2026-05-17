# Memory Rules — Universal Agent Protocol (v1)

**Version:** v1  
**Scope:** All agents using Project Memory Extractor v1.  
**No per-project edits required.**

---

## 1. Role inference

At session start, infer your role:
- From current topic/agent context (coder / reviewer / infra)
- From `.agent/AGENT_CONTEXT.md` active topics list if already present
- If role is ambiguous, ask the operator once and remember the answer

---

## 2. Memory extractor location

Always use:
```
/home/dima/projects/openclaw-agent-memory-infra/scripts/
```

Do not use vendored copies or other paths unless the operator explicitly overrides.

---

## 3. Target project location

Default search path: `/home/dima/projects/<project-name>/`

If not found:
- **Coder:** propose creating it — wait for approval before `mkdir` or `git init`
- **Reviewer / Infra:** report as blocker — do not create

Never create a remote GitHub repository without explicit operator approval.

---

## 4. Startup sequence (mandatory)

Run this sequence at every session start:

```
1. locate target project
2. check .agent/AGENT_CONTEXT.md — create from template if missing
3. check working memory freshness (working/*.md mtime)
4. if memory missing or stale (>24h) or operator requested refresh:
     → run refresh-memory (write mode)
     → autofill working memory (mandatory — see Rule 6)
     → update private memory if access/infra facts present (see Rule 8)
5. run recover-memory
6. return MEMORY STARTUP REPORT
```

---

## 5. refresh-memory rules

- Always dry-run first, then write if Archive step: PASS
- Single topic per invocation
- `--read-topic` only on explicit operator request — never on startup automatically
- `--limit` is required for Telegram mode
- Do not use `--since-id`, `--until-id`, `--since`, `--until`, `--full` — not implemented
- Do not use `--topics` (multi-topic) — not implemented

---

## 6. Autofill after refresh (mandatory)

After `refresh-memory --write`, the agent MUST fill all `<!-- TODO -->` placeholders
in working memory before running recover-memory. Do not stop at draft files.

Files to fill:
```
.agent/memory/working/agent-brief.md
.agent/memory/working/current-state.md
.agent/memory/working/known-issues.md
```

Autofill rules:
- Use the context packet and extraction prompt printed by the compile step
- Label each fact: `confirmed` | `inferred` | `stale` | `needs_review`
- Do not invent facts not present in the source
- Do not include raw secrets — use `[REDACTED:<category>]` at category level only
- Mark contradictions as `needs_review`
- Mark unverified branch/repo status as `stale`

Scripts never call LLM APIs. The agent itself performs the semantic autofill step.

---

## 7. recover-memory rules

Run `recover-memory` after every refresh and autofill cycle.
Also run at session start when memory is fresh (no refresh needed).

`recover-memory` reads ONLY:
- `.agent/AGENT_CONTEXT.md`
- `.agent/memory/working/agent-brief.md`
- `.agent/memory/working/current-state.md`
- `.agent/memory/working/known-issues.md`
- `.agent/memory/working/decisions.md` (if present)
- `.agent/memory/working/open-questions.md` (if present)

It does NOT read Telegram, raw chunks, index, candidates, wiki, or vector DB.

---

## 8. Private memory rules

Private memory lives at:
```
.agent/memory/private/
  access.md          VPS / SSH access patterns, key locations
  credentials.md     Token names, purposes, env file locations
  infrastructure.md  Service ports, admin URLs, deployment/restart commands
```
MEMORY STARTUP REPORT

Project:                  <project-name>
Project path:             <absolute path>
Role:                     <coder|reviewer|infra>
Topic:                    <topic-id>
Repository:               <git remote URL or local path>
AGENT_CONTEXT:            OK | MISSING | CREATED

Refresh:                  SKIPPED | PASS | FAIL
Telegram messages fetched: <N> | N/A
Telegram messages archived: <N> | N/A
Raw chunks written:        <N> | N/A
Working memory updated:    SKIPPED | DONE | PARTIAL (<what was not filled>)
Private memory updated:    SKIPPED | UPDATED (categories: <access|credentials|infrastructure>)
Recover-memory:            PASS | FAIL

Ready to work:             YES | NO
Warnings:                  <list or none>
Blockers:                  <list or none>
```

---

## 11. LLM policy

Scripts (`refresh-memory.py`, `recover-memory.py`, `archive-context.py`,
`compile-working-memory.py`) MUST NOT call LLM APIs.

The agent receiving this protocol IS the LLM and performs:
- Role inference
- Project location
- Semantic autofill of working memory
- Private memory categorization
- MEMORY STARTUP REPORT generation

This is intentional and documented. No hidden API spend from scripts.
