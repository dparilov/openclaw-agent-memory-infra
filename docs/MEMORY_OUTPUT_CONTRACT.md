# Memory Output Contract: `memory/topic-<id>.md`

## Overview

This document defines the canonical format for per-topic memory files produced by the
archive writer (`archive-batch-v2.py --write`). The format is designed to be:

- **Agent-readable**: a model reading the full file gets the equivalent of having read all
  source batches in sequence, with natural conflict resolution by recency.
- **Append-only**: no entry is ever deleted or overwritten. History is preserved.
- **Compact-friendly**: a periodic compaction pass produces a shorter file in the same format.
- **Human-inspectable**: timestamps, batch references, and conflict markers are readable
  without tooling.

---

## File Location

```
<project-repo>/.agent/memory/topic-<id>.md
```

Where `<id>` is the numeric Telegram topic ID (e.g. `7301` for `telemost`).

---

## Format

### Normal (append-only, no compaction yet)

```markdown
# Memory: topic-7301 (telemost)

<!-- last-batch: 10 | last-write: 2026-04-27T18:00Z | batches: 1–10 -->

## [2026-04-20] Batch 5 — session abc123
- Project X использует PostgreSQL для хранения данных
- Deploy происходит через GitHub Actions

## [2026-04-27] Batch 10 — session def456
- Project X мигрировал на MongoDB (март 2026)
- ⚠️ CONFLICT: предыдущая запись (Batch 5) указывала PostgreSQL
```

### After compaction

```markdown
# Memory: topic-7301 (telemost)

<!-- compacted: 2026-05-10T09:00Z | batches: 1–10 | session: ghi789 -->
<!-- last-batch: 12 | last-write: 2026-05-12T14:00Z | batches: 11–12 -->

## Canonical facts (as of 2026-05-10, batches 1–10)
- Project X использует MongoDB (мигрировал в марте 2026; PostgreSQL устарел)
- Deploy через GitHub Actions

---

## [2026-05-12] Batch 11 — session jkl012
- Добавлен staging-окружение
- Feature flags управляются через LaunchDarkly
```

---

## Rules

### Append-only
- Each `--write` call appends a new `## [date] Batch N — session XYZ` section.
- Existing sections are never modified or deleted.
- A compaction pass is the only operation that rewrites the file, and it preserves
  all batches written after the compaction cutoff.

### Conflict detection (writer responsibility)
- Before appending, the writer scans the existing file for keyword overlap between
  new facts and existing entries (same entity, different attribute values).
- If a potential conflict is detected, the new entry is annotated:
  `⚠️ CONFLICT: предыдущая запись (Batch N) указывала <old-value>`
- Conflict detection is heuristic (keyword-based), not semantic. False negatives are
  expected and acceptable at Phase 1. Semantic resolution is Phase 3.

### Conflict resolution (reader responsibility)
- A model reading the file resolves conflicts by recency: the later entry is authoritative.
- The `⚠️ CONFLICT` marker is informational — it helps humans and is not required for
  correct agent behavior.
- Human review of flagged conflicts is handled by the pending approval report (Phase 3).

### Timestamps
- Batch header date: ISO-8601 date (`2026-04-27`), local time of the write.
- HTML comment metadata: ISO-8601 UTC datetime (`2026-04-27T18:00Z`).
- Compaction header: UTC datetime of the compaction run.

### Compaction
- Triggered manually or when the file exceeds a size threshold (suggested: 50 KB).
- Compaction runs the canonical section through an LLM that:
  1. Merges contradicting entries, keeping the most recent value.
  2. Removes entries superseded by later ones.
  3. Deduplicates equivalent facts.
- Compaction does NOT touch batches appended after the compaction cutoff date.
- The compacted file is structurally identical to the append-only format:
  `Canonical facts` section followed by new batches append-only.
- Compaction is idempotent: running it twice produces the same result.

### Idempotency (writer responsibility)
- A batch is identified by its session ID. Re-running `--write` for the same session
  ID must not produce a duplicate entry.
- The writer checks the existing file for the session ID before appending.

---

## Header comment fields

| Field | Description |
|-------|-------------|
| `last-batch` | Highest batch number written to this file |
| `last-write` | UTC datetime of the most recent write |
| `batches` | Range of batches present in this file |
| `compacted` | UTC datetime of last compaction (only after first compaction) |
| `session` | Session ID of the compaction agent (only after first compaction) |

---

## Extraction scope

The content of each batch section is produced by the archive agent from the source
transcript batch. The writer does not control what facts are extracted — that is the
agent's responsibility. The contract only governs structure, metadata, and conflict
annotation.

---

## Example full file (pre-compaction)

```markdown
# Memory: topic-7301 (telemost)

<!-- last-batch: 3 | last-write: 2026-04-27T18:00Z | batches: 1–3 -->

## [2026-04-10] Batch 1 — session aaa001
- Проект olcRTC — мобильное приложение для видеозвонков
- Команда: Дима (продукт), Антон (iOS), Саша (бэкенд)
- Используется WebRTC через Telemost SDK

## [2026-04-18] Batch 2 — session bbb002
- Релиз v1.2 планируется на конец апреля
- Основной блокер: баг с реконнектом при переключении сети

## [2026-04-27] Batch 3 — session ccc003
- Релиз v1.2 перенесён на май из-за ревью в App Store
- ⚠️ CONFLICT: Batch 2 указывал конец апреля
- Баг с реконнектом закрыт в PR #47
```
