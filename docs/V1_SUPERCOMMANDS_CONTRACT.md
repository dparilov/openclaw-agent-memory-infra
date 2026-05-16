# V1 Supercommands Contract

> Defines two user-facing commands that hide the low-level v1 memory pipeline.
>
> This is a contract document — not implementation.
> Implementation is PR37 (recover-memory) and PR38 (refresh-memory).

---

## Goal

Define two user-facing commands that hide the low-level v1 memory pipeline.

The user/operator should not need to remember the sequence of low-level tools.

```text
Low-level pipeline (implemented):
  archive-context.py
  compile-working-memory.py

User-facing layer (this contract):
  refresh-memory   — ingestion + compile in one command
  recover-memory   — load saved memory for agent startup
```

---

## Commands

### `refresh-memory`

**Purpose:**

```text
explicit source context
→ raw Markdown chunks       (archive-context.py)
→ working Markdown memory   (compile-working-memory.py)
→ context packet + extraction prompt printed for agent-assisted extraction
→ final diff for review
```

This command is used when memory must be refreshed from topic/session/local context.

It may call internally:
- `archive-context.py`
- `compile-working-memory.py`
- `read-topic.py` — **only on explicit operator request** and with bounded scope; never silently

It **must not** run silently on startup or heartbeat.

---

### `recover-memory`

**Purpose:**

```text
saved working Markdown memory
→ concise agent startup context
```

This command is used when an agent starts, loses context, or needs to recover project memory.

It reads **only**:
- `.agent/AGENT_CONTEXT.md`
- `.agent/memory/working/agent-brief.md`
- `.agent/memory/working/current-state.md`
- `.agent/memory/working/known-issues.md`
- `.agent/memory/working/decisions.md` (optional)
- `.agent/memory/working/open-questions.md` (optional)

It **must not** read:
- Telegram
- Raw chunks
- Index files
- Candidates
- Wiki
- OpenClaw memory-core
- Vector DB

---

## Non-goals

- No vector DB
- No OpenAI embeddings
- No OpenClaw memory-core
- No hidden API spend
- No LLM API calls inside scripts
- No candidate promotion
- No mandatory wiki build
- No cross-topic SendMessage dependency
- No automatic full `read-topic`
- No human-gate-heavy UX

---

## Command semantics

### `refresh-memory` semantics

#### Inputs

Explicit source, one of:
- `--input <file>` — local Markdown export or JSONL session file
- `--read-topic --chat-id <id> --topic <id> --limit <n>` — bounded Telegram read, explicit only
- *(later)* `--session-jsonl <file>` — structured session export

#### Required arguments

| Argument | Description |
|----------|-------------|
| `--target` | Path to target project repo root |
| `--topics` | Comma-separated `<id>:<role>` pairs |
| source mode | One of `--input`, `--read-topic`, or later `--session-jsonl` |

#### Flags

| Flag | Behavior |
|------|----------|
| *(none)* | Dry-run (default) |
| `--write` | Write chunks and working drafts |
| `--notes <file>` | Optional operator notes |

#### Dry-run behavior

- Validate inputs
- Run archive-context dry-run
- Run compile-working-memory dry-run
- Print planned output files
- Print context packet + extraction prompt
- Print warnings
- **Write nothing**

#### Write behavior

1. Archive step: write `raw/topic-<id>/chunk-*.md`
2. Compile step: write `working/agent-brief.md`, `working/current-state.md`, `working/known-issues.md`
3. Print context packet + extraction prompt for agent-assisted extraction
4. Print diff summary for review

#### Human review

- One review point only: final Markdown diff
- No intermediate approval gates

#### Safety

- Bounded reads only by default
- Raw chunks stay gitignored
- No raw secrets in `working/*.md`
- No auto-commit or auto-push
- Overwrite guard inherited from `archive-context.py` (raw chunks)
- `working/*.md` overwrite prints warning but is allowed (reviewed drafts)

---

### `recover-memory` semantics

#### Inputs

| Argument | Description |
|----------|-------------|
| `--target` | Path to target project repo root |
| `--topics` | Optional; filter output to specific topic/role |

#### Required behavior

1. Read saved working Markdown files in startup load order:
   1. `.agent/AGENT_CONTEXT.md`
   2. `working/agent-brief.md`
   3. `working/current-state.md`
   4. `working/known-issues.md`
   5. `working/decisions.md` (if present)
   6. `working/open-questions.md` (if present)
2. Print concise recovery summary:
   - Project identity and current objective
   - Active topics and roles
   - Current state summary
   - Known issues (severity: high first)
   - Do-not-do rules
   - Next useful actions (if present in agent-brief.md)
3. Report missing or stale files with `[MISSING]` / `[STALE]` markers
4. Report which files were loaded and when they were last compiled

#### Exit codes

| Code | Condition |
|------|-----------|
| `0` | Recovery summary printed (even if some files missing/stale) |
| `1` | `--target` does not exist or is not a directory |
| `1` | `.agent/AGENT_CONTEXT.md` is unreadable (critical file) |

#### Must not

- Modify any files
- Call external services
- Read Telegram or raw chunks
- Call LLM APIs

---

## Proposed CLI shapes

### `refresh-memory`

```bash
# Dry-run (default) — local input
python3 scripts/refresh-memory.py \
  --target /path/to/project \
  --topic 15222:infra \
  --input /path/to/session.jsonl \
  --source-type session_jsonl \
  --dry-run

# Dry-run — bounded Telegram read (explicit only)
python3 scripts/refresh-memory.py \
  --target /path/to/project \
  --topic 15222:infra \
  --read-topic \
  --chat-id -1003596522926 \
  --limit 200 \
  --dry-run

# Write mode — local Markdown export, multiple topics
python3 scripts/refresh-memory.py \
  --target /path/to/project \
  --topics 7301:coder,13350:reviewer,15222:infra \
  --input /path/to/export.md \
  --source-type markdown_export \
  --write
```

### `recover-memory`

```bash
# Default — print recovery summary
python3 scripts/recover-memory.py \
  --target /path/to/project

# With topic + role filter
python3 scripts/recover-memory.py \
  --target /path/to/project \
  --topic 7301 \
  --role coder
```

---

## Internal pipeline mapping

| User action | Internal calls |
|-------------|----------------|
| `refresh-memory --input ... --write` | `archive-context.py --write` → `compile-working-memory.py --write` |
| `refresh-memory --read-topic ... --write` | `read-topic.py` (bounded) → `archive-context.py --write` → `compile-working-memory.py --write` |
| `refresh-memory` (dry-run) | `archive-context.py` (dry-run) → `compile-working-memory.py` (dry-run) |
| `recover-memory` | Read `working/*.md` → print summary |

---

## Success criteria

- [ ] `refresh-memory --write` produces same output as running `archive-context.py --write` + `compile-working-memory.py --write` manually
- [ ] `refresh-memory` (dry-run default) writes nothing
- [ ] `recover-memory` prints usable startup context from `working/*.md` alone
- [ ] `recover-memory` reports missing/stale files without crashing
- [ ] No LLM API calls in scripts
- [ ] No vector DB, embeddings, or memory-core
- [ ] No Telegram reads in `recover-memory`
- [ ] No `read-topic` in `refresh-memory` unless `--read-topic` explicitly passed
- [ ] No auto-commit or auto-push

---

## Startup recall test

After `recover-memory`, a fresh agent must be able to answer without `read-topic`, raw chunk reading, or vector search:

1. What is this project?
2. What is the current objective?
3. Which topic/role am I?
4. What are the current blockers?
5. What should I not do next?

---

## Relation to other contracts

| Contract | Scope |
|----------|-------|
| `docs/V1_CONTEXT_ARCHIVE_CONTRACT.md` | Ingest layer — explicit input → raw chunks |
| `docs/V1_WORKING_MEMORY_COMPILE_CONTRACT.md` | Compile layer — raw chunks → working memory |
| **This document** | Supercommand layer — user-facing wrappers |
| `.agent-template/AGENT_CONTEXT.md` | Startup load order consumed by `recover-memory` |
