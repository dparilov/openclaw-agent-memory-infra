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
$PME_REPO/scripts/
```

Do not use vendored copies or other paths unless the operator explicitly overrides.

---

## 3. Target project location

Default search path: `$PROJECTS_ROOT/<project-name>/`

If not found:
- **Coder:** propose creating the local project directory and initial scaffold.
  Do not create a remote GitHub repository without explicit operator approval.
  Do not run destructive commands.
- **Reviewer / Infra:** report as blocker — do not create the project.

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
- Never copy private memory content into `working/*.md`, docs, PR descriptions, or commit messages
- When reporting on private memory updates, summarize category-level changes only
  - OK: "updated SSH access for vps-prod"
  - NOT OK: printing any IP, username, or credential value
- If a chunk contains `[REDACTED:<category>]`, note the category only — do not reconstruct the value

---

## 9. Git policy

**Never commit:**
- `.agent/memory/private/`
- `.agent/memory/raw/`
- `.agent/memory/index/`
- `.agent/memory/candidates/`
- `.agent/memory/.locks/`

**Working memory** (`.agent/memory/working/*.md`) may be committed only after
explicit operator approval. Do not auto-commit or auto-push.

**No auto-push.** The operator approves all git operations.

---

## 10. Secrets policy

Never put secrets (passwords, tokens, private keys, API keys, OAuth secrets) into:
- `.agent/memory/working/*.md`
- `README.md`
- `docs/`
- PR descriptions
- Commit messages

Use private memory (`.agent/memory/private/`) for sensitive access and
infrastructure facts.

When reporting on private memory updates, summarize at category level only.
Do not print raw values in any report or message.

---

## 11. Standard report

After completing the startup sequence, return exactly this report:

```
MEMORY STARTUP REPORT

Project:                   <project-name>
Project path:              <absolute path>
Role:                      <coder|reviewer|infra>
Topic:                     <topic-id>
Repository:                <git remote URL or local path>
AGENT_CONTEXT:             OK | MISSING | CREATED

Refresh:                   SKIPPED | PASS | FAIL
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

## 12. LLM policy

Scripts (`refresh-memory.py`, `recover-memory.py`, `archive-context.py`,
`compile-working-memory.py`) MUST NOT call LLM APIs.

The agent receiving this protocol IS the LLM and performs:
- Role inference
- Project location
- Semantic autofill of `working/*.md`
- Private memory categorization and update
- MEMORY STARTUP REPORT generation

This is intentional and documented. No hidden API spend from scripts.

---

## What agents must NOT do

- Do not run `read-topic` automatically on startup or heartbeat
- Do not use vector DB, embeddings, or OpenClaw memory-core
- Do not call LLM APIs from scripts
- Do not auto-commit or auto-push working or private memory
- Do not add candidate promotion, wiki build, or multi-topic orchestration
- Do not create remote GitHub repos without operator approval
- Do not touch target project repos beyond `.agent/memory/`
- Do not leave `<!-- TODO -->` placeholders after a refresh cycle
