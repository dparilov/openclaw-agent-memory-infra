# V1 Context Archive Contract

**Status:** Working design  
**Date:** 2026-05-16  
**Scope:** Defines the v1 contract for converting explicit topic/session context into Markdown archive chunks that can later be used to compile the working memory pack.

---

## Goal

Convert explicit, bounded topic/session context into Markdown archive chunks.  
These chunks are source material for a later extraction + review step that produces the working memory pack agents load at startup.

The flow:

```
explicit context input
  → Markdown archive chunks   (.agent/memory/raw/)
  → compile working memory    (.agent/memory/working/*.md)   ← human reviews diff here
  → agents load memory pack
```

Human review happens **once** — at the final Markdown diff before commit.  
No intermediate approval gates.

---

## Non-Goals

- No vector DB or embeddings (OpenAI, local, or otherwise)
- No OpenClaw memory-core or knowledge_search dependency
- No hidden API spend
- No LLM API calls inside archive scripts
- No candidate promotion workflow
- No mandatory wiki build
- No cross-topic SendMessage dependency
- No automatic full `read-topic` on startup or heartbeat
- No human-gate-heavy UX between ingest and final diff

---

## Inputs

Allowed input sources (all must be **explicit** — no silent reads):

| Source | How to provide |
|--------|---------------|
| Bounded Pyrogram/read-topic output | `read-topic.py <topic-id> --limit N` or `--since-id <id>`, explicitly invoked by operator |
| Local OpenClaw session JSONL | Path passed explicitly to the archive tool |
| Existing Markdown context export | Path passed explicitly |
| `.agent/AGENT_CONTEXT.md` | Read by the compile step as project identity context when `--target` is explicitly provided |
| Operator notes | Plain text or Markdown file passed explicitly |

The tool must **not**:
- silently read Telegram on startup or on any scheduled trigger
- run full unbounded topic history reads without operator instruction
- auto-discover or auto-ingest sessions without explicit invocation

---

## Output

Archive chunks are written to the raw archive layer.

### Location

```
.agent/memory/raw/topic-<topic-id>/
```

### Chunk naming

```
.agent/memory/raw/topic-<topic-id>/chunk-0001.md
.agent/memory/raw/topic-<topic-id>/chunk-0002.md
...
```

Chunks are numbered sequentially per topic. The numbering restarts if the raw directory is cleared.

### Chunk metadata header

Each chunk begins with a YAML front-matter block:

```yaml
---
source_type: telegram_topic | session_jsonl | markdown_export | operator_note
chat_id: <chat_id or blank>
topic_id: <topic_id or blank>
topic_role: coder | reviewer | infra | unknown
range:
  message_count: <integer or blank>
  ts_start: <ISO-8601 or blank>
  ts_end: <ISO-8601 or blank>
created_at: <ISO-8601>
redaction_status: clean | redacted | needs_review
---
```

`redaction_status`:
- `clean` — no sensitive data detected
- `redacted` — sensitive patterns found and masked before write
- `needs_review` — sensitive patterns found but masking could not be applied automatically; operator must review before promotion

### Chunk body

The body preserves enough context for later fact extraction. It is **not** the final agent memory.  
No transformation is applied beyond chunking and redaction.  
Raw message text, tool outputs, or operator notes are preserved as-is (after redaction).

---

## What Archive Chunks Are NOT

- Not agent startup memory — agents do not read `raw/` at startup
- Not the working memory pack — that lives in `working/*.md`
- Not searchable by default — no index, no embedding, no vector lookup
- Not committed by default — `raw/` is gitignored

```
# .gitignore additions for target projects
.agent/memory/raw/
.agent/memory/index/
.agent/memory/candidates/
.agent/memory/.locks/
```

---

## Relationship to Working Memory (D-1 Coexistence)

Two layers coexist:

| Layer | Location | Written by | Read by |
|-------|----------|-----------|---------|
| Archive chunks | `.agent/memory/raw/topic-<id>/chunk-*.md` | archive tool | extraction step only |
| Archive log (L2) | `.agent/memory/topic-<id>.md` | `archive-batch-v2.py` | extraction step only |
| Working memory | `.agent/memory/working/*.md` | extraction + review flow | agents at startup |

`archive-batch-v2.py` continues to write to `topic-<id>.md` (append-only L2 log).  
The new raw chunk format is the preferred ingest path for v1.  
Both are source material. Neither is read by agents at startup.

The final v1 agent startup memory is:

```
.agent/memory/working/agent-brief.md       (required)
.agent/memory/working/current-state.md     (required)
.agent/memory/working/known-issues.md      (required)
.agent/memory/working/decisions.md         (optional)
.agent/memory/working/open-questions.md    (optional)
```

---

## Sensitive Data Policy

The archive layer may contain redacted source context.  
Compiled working memory (`working/*.md`) must **never** contain raw secrets.

Archive scripts must:
- Detect credential patterns (tokens, keys, passwords, private keys, PEM blocks, API keys) before writing
- Mask detected values — write `[REDACTED:<category>]` in place of the value
- Set `redaction_status: redacted` in the chunk header if any masking occurred
- Set `redaction_status: needs_review` if a pattern was detected but could not be safely masked; operator must review before promotion
- **Never** write raw credential values to disk, even in `raw/`
- **Never** print or log raw secrets to stdout/stderr

The compilation step (raw → working/*.md) must not promote any chunk with `redaction_status: needs_review` without explicit operator acknowledgement.

Detection reuses the pattern set from `initial-index.py` (`SENSITIVE_PATTERNS`). No separate sensitivity model required for v1.

---

## Git Policy

Generated/private artifacts are gitignored — never commit by default:

```gitignore
.agent/memory/raw/
.agent/memory/index/
.agent/memory/candidates/
.agent/memory/.locks/
```

Reviewed compiled Markdown may be committed after human review:

```
.agent/memory/working/*.md     ✅ commit after review
.agent/memory/promoted/*.md    ✅ commit after review
.agent/memory/wiki/*.md        ✅ commit after review (optional, future)
```

Raw archive chunks must not be committed. Working memory is committed only after the operator reviews the diff.

---

## read-topic Policy

`read-topic.py` is allowed **only** as an explicit operator-requested ingestion command.

Default behaviour when used through the archive tool:
- Always bounded: `--limit`, `--since-id`, `--since`/`--until`, or explicit topic/window scope
- Dry-run available: show what would be fetched before writing
- Full unbounded reads require an explicit `--confirm-large-read` flag
- Never invoked silently on startup, heartbeat, or scheduled trigger

```bash
# Bounded by message count (default safe path)
memory-extract read-topic --topic 7301 --limit 200 --dry-run

# Bounded by message ID
memory-extract read-topic --topic 7301 --since-id 18000 --dry-run

# Full read — requires explicit confirmation flag
memory-extract read-topic --topic 7301 --confirm-large-read
```

---

## CLI Shape (Contract, Not Final Implementation)

The v1 archive tool (`memory-extract`) exposes two commands:

### `archive-session` — ingest from local session JSONL

```bash
memory-extract archive-session \
  --target /path/to/project \
  --topic 7301 \
  --role coder \
  --input ~/.openclaw/agents/main/sessions/<file>.jsonl \
  --out .agent/memory/raw/topic-7301/ \
  --dry-run
```

### `read-topic` — ingest from live Telegram topic (bounded)

```bash
memory-extract read-topic \
  --target /path/to/project \
  --chat-id -1003596522926 \
  --topic 7301 \
  --role coder \
  --limit 200 \
  --out .agent/memory/raw/topic-7301/ \
  --dry-run
```

Both commands:
- Default to `--dry-run` (no files written unless flag is removed)
- Write `chunk-NNNN.md` files with YAML front-matter
- Apply sensitive data detection and masking before write
- Print a summary of chunks that would be written (or were written)
- Never touch `.agent/memory/working/` — that is the compilation step

---

## Success Criteria

The v1 archive layer is complete when:

- [ ] Context can be archived into Markdown chunks from at least one explicit input source (session JSONL or bounded read-topic)
- [ ] No vector DB or embeddings required at any step
- [ ] No LLM API call inside the archive script
- [ ] No target project memory is touched unless `--target` is explicitly provided
- [ ] Raw/archive chunks remain gitignored and not committed by default
- [ ] The compilation step (next PR) can consume chunks from this path
- [ ] Existing topic contexts (7301 coder, 13350 reviewer, 15222 infra) can be ingested through this path

---

## Next Step: Compilation

After archive chunks exist, a separate extraction pass compiles them into working memory:

```
raw chunks + operator notes
  → extraction pass (LLM-assisted or agent-assisted, not scripted API call)
  → draft working/*.md files
  → git diff shown to operator
  → operator approves / edits
  → commit working/*.md
```

The extraction pass is **not** part of this contract. It is defined in PR5 (working memory pack generator).  
This contract (PR3) covers only the ingest → raw chunk step.  
PR4 implements the minimal archive command (`memory-extract`).
