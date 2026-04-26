# Archive Context Analysis

Date: 2026-04-26
Status: initial read-only analysis

## Objective

Understand the current `/archive-context` implementation and why it is not yet reliable enough as the foundation for project memory ingestion.

## Components

### Skill wrapper

Path: `/home/dima/.openclaw/workspace/skills/archive-context/SKILL.md`

Intended behavior:

- user invokes `/archive-context [topic]`;
- agent runs `archive-batch.py`;
- agent extracts facts from one batch;
- agent appends facts to `memory/topic-<topic>.md`;
- agent marks the batch done;
- agent prints mandatory archive stats.

### Claude command wrapper

Path: `/home/dima/.claude/commands/archive-context.md`

Similar intent, but command execution currently appears affected by native command / client-forwarding behavior in Telegram contexts.

### Batch script

Path: `/home/dima/.openclaw/workspace/ops/archive-batch.py`

Observed capabilities:

- finds OpenClaw transcript files by topic filename pattern `*-topic-<id>.jsonl` and `*.reset.*`;
- reads user/assistant transcript messages;
- emits one batch, default 100 messages;
- tracks progress in `/home/dima/.openclaw/workspace/ops/archive-progress-<topic>.json`;
- intended memory target: `/home/dima/.openclaw/workspace/memory/topic-<topic>.md`.

## Read-only Test: topic 7301

Commands run:

```bash
python3 /home/dima/.openclaw/workspace/ops/archive-batch.py 7301 --status
python3 /home/dima/.openclaw/workspace/ops/archive-batch.py 7301 --total
python3 /home/dima/.openclaw/workspace/ops/archive-batch.py 7301 --batch 0
```

Observed:

```text
Archive progress  [topic:7301]
  Batches done  : 0/105  (0%)
  Next batch    : 0

topic:7301  total_msgs:10469  batch_size:100  total_batches:105
```

No existing archive state was found:

```text
/home/dima/.openclaw/workspace/memory/topic-7301.md — missing
/home/dima/.openclaw/workspace/ops/archive-progress-7301.json — missing
```

Transcript files found for topic 7301: 13 files, including reset files from 2026-04-12 through 2026-04-26.

## Key Finding: Duplicate Messages

`archive-batch.py --batch 0` emitted repeated copies of the same initial Telegram message (`message_id: 7302`, “Привет”).

A quick duplicate scan found:

```text
files: 13
raw user/assistant transcript messages: 10469
telegram message ids found: 1216
duplicate telegram ids: 256
some ids appear 3 times
```

Likely cause:

- reset transcript files contain overlapping copied history;
- current dedupe key is `(basename, seq, ts_ms)`, so the same Telegram message repeated in different reset files is not deduplicated;
- chronological merge across reset files therefore inflates batch count and pollutes the first archive batches.

## Current Reliability Assessment

`archive-batch.py` is useful as a prototype, but not safe as the canonical archive ingestion engine yet.

Blocking issues before real archiving:

1. Cross-file deduplication is missing.
2. Batch counts are inflated by reset-file overlap.
3. Archive memory target is workspace-local, not portable.
4. Skill execution wrapper is unreliable in Telegram due native command / client-forwarding behavior.
5. LLM fact extraction from batches is not schema-validated.
6. `--reset` deletes progress and memory target; wrapper must require explicit approval before exposing it.

## Recommended Next Atomic Fix

Patch `archive-batch.py` or create a portable successor script with stable dedupe.

Minimal dedupe rule:

1. If a message contains trusted Telegram inbound metadata with `message_id`, dedupe by:

```text
telegram:<chat_id>:<topic_id>:<message_id>:<role>
```

2. Else dedupe by fallback content fingerprint:

```text
fallback:<role>:<timestamp bucket>:sha256(normalized text)
```

3. Report both raw and deduped counts in stats.

Acceptance check for topic 7301:

- batch 0 must not contain three copies of the same `message_id: 7302`;
- stats must show raw vs deduped messages;
- `--total` must be based on deduped messages;
- no archive write or mark-done happens during dry-run.

## Relationship to Infrastructure Project

This becomes part of Phase 1: Context Access Stabilization.

The memory pipeline must use a stable context-access layer before candidate extraction/promotion is implemented.
