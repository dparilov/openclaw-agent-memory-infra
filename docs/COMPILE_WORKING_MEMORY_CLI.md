# compile-working-memory.py — CLI Reference (v1)

**Status:** implemented and tested on `main`.

For the full pipeline including user-facing supercommands, see
`docs/REFRESH_MEMORY_COMMANDS.md`.
For the design contract, see `docs/V1_WORKING_MEMORY_COMPILE_CONTRACT.md`.

---

## What it does

`compile-working-memory.py` reads raw archive chunks from
`.agent/memory/raw/topic-<id>/` and `.agent/AGENT_CONTEXT.md`, then:

- **Dry-run (default):** prints a context packet and an extraction prompt for
  agent-assisted extraction — writes nothing.
- **Write mode:** writes draft `working/*.md` files with `<!-- TODO -->`
  placeholders for an agent to fill in.

**This script does NOT:**
- Read Telegram
- Call any LLM API
- Touch `raw/`, `index/`, `candidates/`, or `wiki/` directories
- Commit or push anything

---

## Quick start

```bash
# Dry-run (default — writes nothing, prints context + prompt)
python3 scripts/compile-working-memory.py \
  --target /path/to/project \
  --topics 7301:coder

# Write draft working/*.md files
python3 scripts/compile-working-memory.py \
  --target /path/to/project \
  --topics 7301:coder \
  --write

# Multiple topics
python3 scripts/compile-working-memory.py \
  --target /path/to/project \
  --topics 7301:coder,13350:reviewer,15222:infra \
  --write
```

---

## Flags

| Flag | Required | Default | Description |
|---|---|---|---|
| `--target` | yes | — | Project root. Must exist and be a directory. |
| `--topics` | yes | — | Comma-separated `<id>:<role>` pairs, e.g. `7301:coder,13350:reviewer`. |
| `--notes` | no | — | Optional operator notes file (Markdown or plain text). |
| `--dry-run` | no | false | Explicit dry-run flag (same as default when `--write` absent). |
| `--write` | no | false | Write draft `working/*.md` files to disk. |

Allowed roles: `coder`, `reviewer`, `infra`, `unknown`.

---

## Inputs read

| Source | Path | Required |
|---|---|---|
| Project context | `.agent/AGENT_CONTEXT.md` | No (silently skipped if missing) |
| Raw chunks | `.agent/memory/raw/topic-<id>/chunk-*.md` | No (empty compile if missing) |
| Operator notes | `--notes <path>` | No |
| Existing working files | `.agent/memory/working/*.md` | No (read for context, not overwritten unless `--write`) |

Context packet is bounded to 32,000 characters total. Chunks are included in
sorted order until the limit is reached.

---

## Output files (write mode only)

```
.agent/memory/working/
  agent-brief.md       project identity, objective, do-not-do rules, load order
  current-state.md     last updated, branch, completed/in-progress work, blockers
  known-issues.md      per-issue description, severity, status, next action
```

All files are written as drafts with `<!-- TODO -->` placeholders. An agent
must fill in the placeholders using the context packet and extraction prompt
printed to stdout during the compile run.

---

## Dry-run output

Dry-run prints:

```
=== compile-working-memory dry-run ===
target:   /path/to/project
topics:   7301:coder
chunks:   3 found (topic-7301: 3)
...

WARNINGS:
  ...

=== CONTEXT PACKET ===
...bounded content...

=== EXTRACTION PROMPT ===
...instructions for agent-assisted extraction...

(pass --write to write draft working/*.md files)
```

---

## Write output

Write mode prints the same context packet and extraction prompt, plus:

```
=== compile-working-memory write ===
working dir: /path/to/project/.agent/memory/working
files written:
  agent-brief.md
  current-state.md
  known-issues.md
...
```

---

## Warnings

The compile step prints warnings for:

| Condition | Warning |
|---|---|
| `.agent/AGENT_CONTEXT.md` missing | `[WARN] AGENT_CONTEXT.md not found` |
| No raw chunks found for a topic | `[WARN] No chunks found for topic-<id>` |
| Chunks with redacted content | `[WARN] N chunk(s) contain [REDACTED:*] — handle with care` |
| Context packet truncated | `[WARN] Context packet truncated at 32000 chars` |

---

## Forbidden directories

The compile step will never read from or write to:

```
.agent/memory/index/
.agent/memory/candidates/
.agent/memory/wiki/
```

---

## Agent-assisted extraction flow

1. Run compile in write mode to generate draft `working/*.md` with placeholders
2. The context packet and extraction prompt are printed to stdout
3. Paste the context packet + extraction prompt into an agent (OpenClaw or Claude CLI)
4. The agent fills in all `<!-- TODO -->` sections
5. Operator reviews the diff before committing

Scripts never call LLM APIs directly.

---

## Exit codes

| Code | Condition |
|---|---|
| `0` | Success (dry-run or write) |
| `1` | `--target` missing or not a directory |
| `1` | `--notes` file does not exist |
| `1` | Invalid `--topics` format or unknown role |

---

## Pipeline position

```
archive-context.py  ->  .agent/memory/raw/topic-<id>/chunk-*.md
                                          |
                              compile-working-memory.py
                                          |
                              .agent/memory/working/*.md
                                          |
                              recover-memory.py  ->  agent startup context
```

Or via the supercommand (`refresh-memory.py` wraps both steps).

---

## Related docs

| Doc | Scope |
|---|---|
| `docs/V1_WORKING_MEMORY_COMPILE_CONTRACT.md` | Design contract and non-goals |
| `docs/ARCHIVE_CONTEXT_CLI.md` | Previous step: input -> raw chunks |
| `docs/REFRESH_MEMORY_COMMANDS.md` | Supercommand and full usage guide |
| `docs/MEMORY_EXTRACTION_POLICY.md` | What facts to extract |
