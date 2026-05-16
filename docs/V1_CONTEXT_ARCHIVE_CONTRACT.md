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
| `.agent/AGENT_CONTEXT.md` | Read automatically at startup (project identity only) |
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

Archive scripts must:
- Detect credential patterns (tokens, keys, passwords, PEM blocks) before writing
- Mask detected values — write `[REDACTED:<category>]` in place of the value
- Set `redaction_status: redacted` in the chunk header if any masking occurred
- Set `redaction_status: needs_review` if a pattern was detected but could not be masked automatically
- **Never** write raw credential values to disk, even in `raw/`

Detection uses the pattern set already defined in `initial-index.py` (`SENSITIVE_PATTERNS`). The archive tool imports or replicates this list — no separate sensitivity model required.

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

The extraction pass is **not** part of this contract. It is defined in the next PR.  
This contract covers only the ingest → raw chunk step.
