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

**Allowed content:**
- VPS IPs / hostnames
- SSH usernames and command patterns
- Where keys and configs are located (path only, not key content)
- Env file locations (path only, not contents)
- Service ports and admin URLs
- Token names and their purpose (not values)
- Deployment and restart commands
- Recovery procedures

**Forbidden content:**
- Raw secret values (passwords, tokens, private keys, API keys)
- GitHub tokens, Telegram bot tokens, OAuth secrets

**Rules:**
- Never commit `.agent/memory/private/` — it must be in `.gitignore`
- Never copy private memory content into `working/*.md`, `README`, docs, PR descriptions, or commit messages
- When reporting on private memory updates, summarize category-level changes only: e.g. "updated SSH access pattern for VPS-1" — not the actual values
- If a chunk contains `[REDACTED:<category>]`, note the category in private memory without reconstructing the value

---

## 9. What agents must NOT do

- Do not run `read-topic` automatically on startup or heartbeat
- Do not use vector DB, embeddings, or OpenClaw memory-core
- Do not call LLM APIs from scripts
- Do not auto-commit or auto-push working or private memory
- Do not add candidate promotion, wiki build, or multi-topic orchestration
- Do not create GitHub repos without operator approval
- Do not touch target project repos beyond `.agent/memory/`
- Do not leave `<!-- TODO -->` placeholders after a refresh cycle

---

## 10. MEMORY STARTUP REPORT format

After completing the startup sequence, return exactly this report:

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

Refresh:       SKIPPED | PASS | FAIL
Autofill:      SKIPPED | DONE | PARTIAL (list what was not filled)
Private memory: SKIPPED | UPDATED (categories: access | credentials | infrastructure)
Recover:       PASS | FAIL

Current objective:   <one line from agent-brief.md>
Active blockers:     <count> — <severity of highest>
Next useful actions: <1-3 bullets from agent-brief.md>

Warnings:      <list or none>
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
