# openclaw-agent-memory-infra

**Shared memory infrastructure for OpenClaw agents.** Provides a multi-layer
knowledge management system (L0–L4) that lets agents persist, retrieve, and
compact facts across sessions — without losing context between handoffs.

---

## Overview

Agents lose context between sessions. This repo provides the tooling to make
memory **persistent, structured, and shared** across agents working on the same
project or Telegram topic.

### Memory Layer Model

```
L0  Raw Archive    .agent/memory/raw/          Audit log — append-only, never read by agents
L1  Candidates     .agent/memory/candidates/   YAML fact queue — promote or reject
L2  Working Memory .agent/memory/topic-<id>.md Canonical facts — loaded at session start
L3  Knowledge Wiki .agent/memory/wiki/         Cross-referenced, searchable (auto-built)
L4  Canonical Docs docs/ + .agent/AGENT_CONTEXT.md  Architecture, runbooks, ADR
```

### Skill Stack

| Skill | When to call |
|-------|-------------|
| `/read-context` | Session start — load L2–L4 context |
| `/archive-context` | Session end — persist new facts to L2 |
| `/recover-memory` | After >24h gap — reality check + full restore |
| `/compact-memory` | Periodic — merge duplicates, resolve conflicts |
| `read-topic.py` | Live Telegram read — Pyrogram fallback |

---

## Quick Start

```bash
# 1. Clone
git clone https://github.com/your-org/openclaw-agent-memory-infra
cd openclaw-agent-memory-infra

# 2. Bootstrap your project
bash setup.sh --target /path/to/your/project --topic-id 7301

# 3. Edit AGENT_CONTEXT.md
nano /path/to/your/project/.agent/AGENT_CONTEXT.md

# 4. Archive existing session history
python3 scripts/context_access/archive-batch-v2.py 7301 --status
python3 scripts/context_access/archive-batch-v2.py 7301 \
  --write - --session-id init-$(date +%Y%m%d) \
  --memory-dir /path/to/your/project/.agent/memory \
  --auto-mark-done

# 5. Build wiki
python3 scripts/context_access/build-wiki.py \
  --memory-dir /path/to/your/project/.agent/memory
```

**Requirements:** Python 3.10+, `pyyaml`, `pyrogram` — see [docs/deployment.md](docs/deployment.md) for full setup including CLI requirements for skill commands.

---

## Scripts

### `scripts/context_access/archive-batch-v2.py`

Core archive engine. Reads OpenClaw JSONL session transcripts, deduplicates,
and writes facts to the L2 memory file.

```bash
# Check archive status
python3 archive-batch-v2.py <topic-id> --status

# Preview a batch (read-only)
python3 archive-batch-v2.py <topic-id> --batch 0

# Write facts to memory
python3 archive-batch-v2.py <topic-id> --write facts.txt \
  --session-id <uuid> --memory-dir .agent/memory --auto-mark-done

# Prepare file for LLM compaction (read-only)
python3 archive-batch-v2.py <topic-id> --compact \
  --memory-file .agent/memory/topic-<id>.md
```

**Key flags:**

| Flag | Description |
|------|-------------|
| `--status` | Show progress, batch counts, dedupe stats |
| `--total` | Show total message/batch counts |
| `--batch N` | Preview batch N (read-only) |
| `--write FILE` | Append facts from FILE (or `-` for stdin) to memory |
| `--session-id ID` | Idempotency key — same ID skips re-archiving |
| `--memory-file PATH` | Explicit memory file path |
| `--memory-dir DIR` | Auto-named `topic-<id>.md` in this directory |
| `--auto-mark-done` | Mark batch as processed after successful write |
| `--compact` | Print memory file for LLM compaction (read-only) |
| `--reset` | Clear progress file (destructive) |
| `--agents-base PATH` | Override `~/.openclaw/agents/` |

### `scripts/context_access/read-topic.py`

Pyrogram userbot reader. Fetches live Telegram topic history as fallback when
session files don't cover a time period.

```bash
# Read last 200 messages
python3 read-topic.py telemost --limit 200

# Read only new messages since last checkpoint
python3 read-topic.py 7301 --since-id 15800

# Structured output for write pipeline
python3 read-topic.py 7301 --batch-format --since-id 15800

# Sub-batch with checkpoint (large topics)
python3 read-topic.py 7301 --limit 2000 --sub-batch-size 200
python3 read-topic.py 7301 --resume  # continue from checkpoint
```

**Key flags:**

| Flag | Description |
|------|-------------|
| `--limit N` | Max messages (default: 500) |
| `--since-id ID` | Delta read — only messages after this ID |
| `--batch-format` | Structured transcript for write pipeline |
| `--sub-batch-size N` | Output N messages, write checkpoint (default: 200) |
| `--resume` | Load `since_id` from checkpoint automatically |
| `--clear-checkpoint` | Delete checkpoint file |
| `--chat-id ID` | Override auto-discovered chat ID |

**Environment:**

| Var | Default | Description |
|-----|---------|-------------|
| `OPENCLAW_AGENTS` | `~/.openclaw/agents` | Session files root |
| `PYROGRAM_SESSION` | `~/.openclaw/workspace/ops/userbot` | Session file path |
| `PYROGRAM_VENV` | auto-detect | PyPI packages path |

### `scripts/context_access/manage-candidates.py`

L1 candidate knowledge manager. Intermediate layer between fact extraction and
L2 memory — each fact goes through a status lifecycle before promotion.

```bash
# Add candidates from fact file
python3 manage-candidates.py 7301 --add facts.txt --memory-dir .agent/memory

# List all candidates
python3 manage-candidates.py 7301 --list

# Auto-promote low-risk candidates to L2
python3 manage-candidates.py 7301 --promote-auto

# Human approval for high-risk candidates
python3 manage-candidates.py 7301 --approve CAND-A1B2C3D4

# Reject a candidate
python3 manage-candidates.py 7301 --reject CAND-A1B2C3D4
```

**Candidate statuses:**

| Status | Meaning |
|--------|---------|
| `candidate` | Freshly extracted, pending review |
| `auto-promoted` | Low-risk type, auto-written to L2 |
| `needs-approval` | High-risk type (decisions, constraints), requires human gate |
| `approved` | Manually approved, written to L2 |
| `rejected` | Explicitly discarded |
| `obsolete` | Superseded by newer candidate |
| `duplicate` | Semantically equivalent to existing L2 fact |

**Type classification** (heuristic, from fact text):

- `architecture_decision` → requires approval
- `constraint` → requires approval
- `process_rule` → requires approval
- `fact`, `preference`, `project_state`, `resolved_issue` → auto-promotable

### `scripts/context_access/build-wiki.py`

L3 Knowledge Vault builder. Generates a cross-referenced Markdown wiki from
all L2 memory files. Neutral — no agent-specific logic.

```bash
# Build wiki from all memory files
python3 build-wiki.py --memory-dir .agent/memory

# Rebuild from scratch
python3 build-wiki.py --memory-dir .agent/memory --clean

# Single topic
python3 build-wiki.py --memory-dir .agent/memory --topic telemost
```

**Output structure:**
```
.agent/memory/wiki/
├── index.md              Master index (all topics + stats)
├── topic-<id>.md         Per-topic wiki (facts grouped by type)
├── by-type/
│   ├── decisions.md      Architecture decisions across all topics
│   ├── constraints.md
│   ├── process.md
│   └── ...
└── WIKI_META.json        Build metadata
```

---

## Skills

Copy skills to your Claude Code skill directory:

```bash
cp -r skills/archive-context ~/.claude/skills/
cp -r skills/read-topic ~/.claude/skills/
cp -r skills/recover-memory ~/.claude/skills/
cp -r skills/compact-memory ~/.claude/skills/
```

| Skill | Trigger |
|-------|---------|
| `archive-context` | `/archive-context <topic>` |
| `read-topic` | `/read-topic <topic>` |
| `recover-memory` | `/recover-memory <topic>` — full 4-step restore |
| `compact-memory` | `/compact-memory <topic>` — LLM dedup pass |

See `docs/SKILL_VOCABULARY.md` for decision guide on when to call each skill.

---

## Project Structure

```
.
├── .agent-template/            Bootstrap template for new projects
│   ├── AGENT_CONTEXT.md        Project context template (copy to .agent/)
│   ├── bootstrap.sh            Quick bootstrap script
│   └── memory/
├── docs/
│   ├── ROADMAP.md              Implementation phases (1–5)
│   ├── MEMORY_OUTPUT_CONTRACT.md  Output format spec for memory files
│   ├── MEMORY_EXTRACTION_POLICY.md  What to extract and when
│   ├── SKILL_VOCABULARY.md     When to call which skill
│   ├── FALLBACK_ORDER.md       Context access fallback chain
│   ├── PYROGRAM_FLOOD_WAIT.md  FloodWait + SQLite lock handling
│   └── runbooks/
│       ├── CODER_AGENT.md
│       ├── REVIEWER_AGENT.md
│       ├── INFRA_AGENT.md
│       └── HANDOFF_TEMPLATE.md
├── scripts/
│   └── context_access/
│       ├── archive-batch-v2.py  Core archive engine (L2 write)
│       ├── read-topic.py        Pyrogram reader (L0/live fallback)
│       ├── manage-candidates.py L1 candidate lifecycle manager
│       └── build-wiki.py        L3 wiki builder
├── skills/
│   ├── archive-context/SKILL.md
│   ├── read-topic/SKILL.md
│   ├── recover-memory/SKILL.md
│   └── compact-memory/SKILL.md
├── tests/
│   └── test_name_resolver.py
├── examples/
│   └── memory/
│       └── topic-7301.md       Example memory file (telemost pilot)
├── setup.sh                    Bootstrap script
└── README.md
```

---

## Memory File Format

```markdown
# Memory: topic-7301

<!-- last-batch: 3 | last-write: 2026-04-27T19:11:00Z | batches: 0-3 -->

## [2026-04-26] Batch 0 — session init-20260426

- Project telemost uses OpenClaw for session management
- Primary contact: Dima (Telegram: @pariloff)
- Decided to use append-only memory format to avoid concurrent write conflicts

## [2026-04-27] Batch 1 — session abc123

- Pyrogram FloodWait retry policy: 4 attempts with exponential backoff
  - ⚠️ CONFLICT: Batch 0 указывал: ...3 attempts...
```

**Header fields:**
- `last-batch` — most recent batch number
- `last-write` — ISO timestamp of last write
- `batches` — range of batch numbers in file
- `last-pyrogram-id` — last Pyrogram message ID archived (optional)
- `last-compact` — timestamp of last compaction (optional)

---

## Mandatory Memory Protocol

Every agent using this infrastructure MUST follow these rules (see `.agent-template/AGENT_CONTEXT.md`):

- **NEVER** start a session without `/read-context` (or `/recover-memory` if stale)
- **NEVER** end a session without `/archive-context` if facts were established
- **NEVER** ask the user for information already in `memory/topic-*.md`
- **NEVER** write to memory files directly — only via `archive-batch-v2.py --write`
- **NEVER** silently accept a contradiction — archive the correction, flag the conflict
- **IF** `last-write` > 24 hours → run `/recover-memory` before task work
- **IF** `/recover-memory` fails → report to user; do not proceed as if memory is current

---

## Development

```bash
# Run tests
python3 -m pytest tests/ -v

# Syntax check all scripts
python3 -m py_compile scripts/context_access/*.py

# Check a specific memory file
python3 scripts/context_access/archive-batch-v2.py <topic> --status
```

---

## Roadmap

| Phase | Status | Description |
|-------|--------|-------------|
| 1 | ✅ Done | Core read/write pipeline, validation, E2E tests |
| 2 | ✅ Done | `read-topic.py`, skill definitions, runbooks, `.agent-template/` |
| 3 | ✅ Done | L0 audit log, sub-batch checkpointing, `--compact` flag |
| 4 | ✅ Done | L1 candidate schema, L3 wiki builder, `setup.sh`, docs |
| 5 | Planned | Agents migration — integration test of complete L0–L4 stack |

See `docs/ROADMAP.md` for full detail.

---

## License

MIT
