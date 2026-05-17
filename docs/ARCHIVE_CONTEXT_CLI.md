# archive-context.py — CLI Reference (v1)

**Status:** implemented and tested on `main`.

For the full pipeline including compile and user-facing supercommands, see
`docs/REFRESH_MEMORY_COMMANDS.md`.
For the design contract, see `docs/V1_CONTEXT_ARCHIVE_CONTRACT.md`.

---

## What it does

`archive-context.py` reads an explicit local input file and writes Markdown
archive chunks to `.agent/memory/raw/topic-<id>/`. These chunks are source
material for the later compile step (`compile-working-memory.py`) that
produces the working memory pack agents load at startup.

**This script does NOT:**
- Read Telegram
- Call any LLM API
- Write to `.agent/memory/working/`
- Commit or push anything
- Touch candidates, wiki, or index directories

---

## Quick start

```bash
# Dry-run (default — writes nothing)
python3 scripts/archive-context.py \
  --target /path/to/project \
  --topic 7301 \
  --role coder \
  --input /path/to/context.md \
  --source-type markdown_export

# Write chunks
python3 scripts/archive-context.py \
  --target /path/to/project \
  --topic 7301 \
  --role coder \
  --input /path/to/context.md \
  --source-type markdown_export \
  --write
```

---

## Flags

| Flag | Required | Default | Description |
|---|---|---|---|
| `--target` | yes | — | Project root. Must exist and be a directory. |
| `--topic` | yes | — | Topic ID string, e.g. `7301`. Names the output directory. |
| `--role` | yes | — | One of: `coder`, `reviewer`, `infra`, `unknown`. |
| `--input` | yes | — | Path to local input file. Must exist. |
| `--source-type` | yes | — | One of: `session_jsonl`, `markdown_export`, `operator_note`, `telegram_topic`. |
| `--chat-id` | no | `""` | Stored in chunk front-matter only. No network call. |
| `--chunk-size` | no | `200` | Lines or JSONL records per chunk. Must be positive. |
| `--out` | no | auto | Override output directory. Must resolve inside `--target`. |
| `--write` | no | false | Write chunks to disk. Default is dry-run. |

Default output path: `<target>/.agent/memory/raw/topic-<topic>/`

---

## Source types

| `--source-type` | Chunking |
|---|---|
| `session_jsonl` | Splits on JSONL lines; extracts timestamps from JSON fields |
| `markdown_export` | Splits on plain lines |
| `operator_note` | Splits on plain lines |
| `telegram_topic` | Splits on plain lines |

---

## Output format

Each chunk is a Markdown file with YAML front-matter followed by the
(redacted) body:

```
.agent/memory/raw/topic-7301/
  chunk-0001.md
  chunk-0002.md
```

Chunk filename: `chunk-NNNN.md` (4-digit, 1-based).

Front-matter schema:

```yaml
---
source_type: markdown_export
chat_id: ""
topic_id: "7301"
topic_role: coder
range:
  message_count: 200
  ts_start: ""
  ts_end: ""
created_at: "2026-05-17T10:00:00Z"
redaction_status: clean
---
```

`redaction_status`: `clean` (no sensitive patterns) or `redacted` (patterns found and masked).

---

## Sensitive data

Before writing, the script scans each chunk body and masks credential patterns
with `[REDACTED:<category>]`. Categories: `pem_key`, `telegram_bot_token`,
`bearer_token`, `password`, `api_key`, `token`, `oauth_secret`,
`aws_credential`. Raw values are never written to disk.

---

## Safety guards

| Guard | Behaviour |
|---|---|
| `--chunk-size <= 0` | Error exit |
| `--target` missing | Error exit |
| `--input` missing | Error exit |
| `--out` outside `--target` | Error exit |
| Existing `chunk-*.md` in output dir | Error exit (overwrite guard) |
| No `--write` | Dry-run — writes nothing |

The overwrite guard prevents double-archive. To re-archive: remove the existing
chunk directory first.

---

## Pipeline position

```
archive-context.py
  |
.agent/memory/raw/topic-<id>/chunk-*.md
  |
compile-working-memory.py  ->  .agent/memory/working/*.md
  |
recover-memory.py          ->  agent startup context
```

Or via the supercommand (`refresh-memory.py` wraps both steps).

---

## Related docs

| Doc | Scope |
|---|---|
| `docs/V1_CONTEXT_ARCHIVE_CONTRACT.md` | Design contract and non-goals |
| `docs/COMPILE_WORKING_MEMORY_CLI.md` | Next step: compile chunks -> working memory |
| `docs/REFRESH_MEMORY_COMMANDS.md` | Supercommand and full usage guide |
| `docs/MEMORY_EXTRACTION_POLICY.md` | What facts to extract from chunks |
