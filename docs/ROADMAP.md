# Roadmap

## Phase 0 — Source of Truth

- [x] Create local infrastructure repo.
- [x] Add original shared-memory infrastructure specification.
- [x] Add context-access scope extension.
- [x] Add pilot environment inventory from olcRTC.

## Phase 1 — Context Access Stabilization

- [x] Inventory current context scripts and skills.
- [x] Diagnose OpenClaw Telegram skill/native command execution failure.
- [x] Define stable script-first CLI contract (`archive-batch-v2.py`).
- [x] Make stats/search/read/archive behavior reproducible (dedupe, `--status`, `--total`, `--batch`).
- [x] Add fixture tests for dedupe logic.
- [x] Fix skill registration (YAML frontmatter requirement for OpenClaw skill discovery).
- [x] Add topic name resolver (numeric ID or name, e.g. `telemost`).
- [x] Forbid `/archive-context` without explicit topic — update SKILL.md.
- [x] Document MeridianA/OpenClaw runtime dependency (`docs/MERIDIANA_DEPENDENCY.md`).
- [x] Add lock/flood-wait handling strategy for Pyrogram userbot reads. See `docs/PYROGRAM_FLOOD_WAIT.md`.
- [x] Document fallback order: memory archive → OpenClaw transcripts → Telegram live read. See `docs/FALLBACK_ORDER.md`.
- [x] Test name resolver end-to-end in telemost topic (verify `telemost` resolves to `7301`).
- [x] Define output contract for `memory/topic-<id>.md` (archive writer format). See `docs/MEMORY_OUTPUT_CONTRACT.md`.
- [x] Implement archive writer: `--write` mode, idempotency, `--mark-done` integration.
- [x] Validate: no duplicate memory entries across batches after write. (session-ID idempotency confirmed; semantic dedup → Phase 3)

## Phase 2 — Portable Templates

- [ ] Bring `read-topic.py` (Pyrogram userbot fallback) into the repo as a first-class tool with flood-wait/lock handling built in.
- [ ] Make `read-topic.py` output compatible with `--write` pipeline: batched output in same format as `archive-batch-v2.py --batch`, so agent can extract facts and write to memory file via the same flow.
- [ ] Write skill invocation vocabulary: how to call `/archive-context`, `/read-context`, `/read-topic` and when to use each.
- [ ] Add `.agent-template/` structure.
- [ ] Add runbooks for Coder, Reviewer, Infrastructure Agent.
- [ ] Add task/review handoff templates.
- [ ] Add memory extraction and promotion policies.


### Phase 2 — additional backlog items (added 2026-04-27)

#### 2.5 — Unified read-merge-write archiver (Pyrogram + OpenClaw sessions)

Extend `archive-batch-v2.py` with a **read-before-write** Pyrogram step:

```
1. Read Pyrogram delta (messages since last-pyrogram-id in header)
2. Read OpenClaw session transcripts (existing logic)
3. Merge + conflict detect
4. Write to memory/topic-<id>.md
```

**Header comment v3:**
```
<!-- last-batch: 3 | last-write: 2026-04-27T19:11:00 | batches: 3 | last-pyrogram-id: 15897 | pyrogram-ts: 2026-04-27T16:00:00 -->
```

**Key rules:**
- `last-pyrogram-id` → idempotency; next run reads only new messages
- Pyrogram mandatory on first `--write` (no memory file), optional delta on subsequent runs
- `--reset` → full Pyrogram read from topic start
- **Batching required:** if Pyrogram returns >200 messages, split into sub-batches;
  each sub-batch writes its own `last-pyrogram-id` checkpoint (partial progress preserved)
- FloodWait: retry policy in `PYROGRAM_FLOOD_WAIT.md`

#### 2.6 — Skill invocation vocabulary doc

`docs/SKILL_VOCABULARY.md` — decision guide for when/how to call `/archive-context`,
`/read-context`, `read-topic.py`. Includes decision tree, chaining example, staleness policy.

**Status:** drafted, pending commit.

## Phase 3 — Semantic Dedup / Compaction

> Status: **planned**

LLM-based compaction pass over `memory/topic-<id>.md`:

- Identify semantically duplicate facts (paraphrases of the same claim)
- Merge contradicting entries into a single canonical statement
- Remove obsolete entries (superseded by newer facts)
- Preserve audit trail in L0 raw archive (see Phase 3.5)
- Output: compacted `topic-<id>.md` with fewer, higher-quality bullets
- Trigger: manual (`--compact`) or automatic when file exceeds N lines

### Key design decisions
- Compaction is **non-destructive**: original facts moved to L0 raw archive before rewrite
- LLM prompt receives full topic file + compaction policy from `MEMORY_EXTRACTION_POLICY.md`
- Result reviewed by agent before write (no silent overwrites)
- Session-ID for the compaction run stored in header for idempotency

---

## Phase 3.5 — L0 Raw Archive (Audit Log)

> Status: **planned**

Append-only audit log written BEFORE every `--write` to `topic-<id>.md`:

```
.agent/memory/raw/topic-<id>-audit.log
```

Format: one entry per archive operation, includes:
- timestamp, session-id
- full raw fact list (pre-compaction)
- source metadata (session files used, Pyrogram msg-id range)

**Purpose:**
- Evidence trail for every memory write
- Recovery source if `topic-<id>.md` gets corrupted or over-compacted
- Input for future re-extraction passes

Implementation: extend `archive-batch-v2.py --write` to emit audit entry before
any file mutation. Audit file is never modified — only appended.

---

## Phase 4 — L1 Candidate Schema + L3 Knowledge Vault

> Status: **planned**

### 4.1 — L1 Candidate Knowledge (YAML schema + status lifecycle)

Formal candidate knowledge layer between raw extraction and working memory:

```yaml
id: CAND-0001
created_at: "2026-04-27T00:00:00+03:00"
created_by: "infra-agent"
project: "project-name"
type: "architecture_decision"
claim: "..."
status: "auto-promoted"   # candidate | auto-promoted | approved | rejected | contradicted | obsolete
evidence: [...]
```

Statuses managed by LLM (auto-promotion) + human approval gate for high-risk types.

### 4.2 — L3 Shared Knowledge Vault (neutral, searchable wiki)

Project-neutral compiled knowledge vault:

```
.agent/memory/wiki/
```

- Human-readable summaries, provenance-aware pages
- Searchable index (markdown + optional Obsidian-compatible)
- Populated by promoted L1 candidates
- Not agent-specific — shared across all agents on the project

Both L1 and L3 are **neutral infrastructure** — no agent-specific logic.

---

### 4.3 — Self-Recovery Skill + Mandatory Memory Protocol

#### `/recover-memory` — Ultimate Memory Restoration Skill

A superscript over the entire L0–L4 stack. Triggered by user (`/recover-memory <topic-id>`)
or automatically when agent reality check fails.

**4-step protocol:**

```
Step 1: REALITY CHECK
  Read header of memory/topic-<id>.md.
  If last-write > 7 days OR file missing → STALE → proceed to Step 2.
  If fresh → load and report "memory current as of <timestamp>".

Step 2: AUDIT
  archive-batch-v2.py <topic> --status
    → how many unprocessed batches remain?
  read-topic.py <topic> --since-id <last-pyrogram-id>
    → is there new Pyrogram content not yet archived?

Step 3: ARCHIVE (if needed)
  If unprocessed batches → archive-batch-v2.py --write --session-id recover-<date>
  If new Pyrogram content → read-topic.py --batch-format → LLM fact-extract → --write

Step 4: LOAD
  /read-context → read updated L2–L4 stack (skip L0 raw)
  Report: "Restored N facts. Memory current as of <timestamp>."
```

**Absolute rules:**
- Always runs Steps 1–4 in order; never skips Step 2 even if Step 1 is green
- Never fabricates recovery status — runs actual scripts or reports failure
- If Step 3 fails (FloodWait exhaust etc.) → reports partial recovery + exact error
- Idempotent: safe to call multiple times

**Implementation:** `skills/recover-memory/SKILL.md`

#### Mandatory Memory Protocol in `.agent-template`

Hardcoded `## Memory Protocol (MANDATORY)` section in `AGENT_CONTEXT.md`:

```markdown
## Memory Protocol (MANDATORY — do not remove or override)

- NEVER start a session without /read-context (or /recover-memory if stale)
- NEVER end a session without /archive-context if any facts were established
- NEVER ask the user for info already in memory/topic-*.md
- NEVER write to memory files directly — only via archive-batch-v2.py --write
- NEVER silently accept contradiction between memory and reality —
  archive the correction and flag the conflict
- IF memory staleness > 7 days → run /recover-memory before any task work
- IF /recover-memory fails → report to user; do not proceed as if memory is current
```

This section is non-negotiable — equivalent to system prompt instructions.

---

## Phase 5 — Agents Migration

> Status: **planned** (blocked on Phase 4 completion)

Migration of existing agents into the complete L0–L4 memory stack:

- Bootstrap `.agent/` structure for each agent project (via `.agent-template/bootstrap.sh`)
- Initial archive pass: populate L2 working memory from existing session history
- Validate L1 candidate pipeline end-to-end
- Run compaction (Phase 3) on accumulated memory files
- Integration tests: Coder → Reviewer handoff with full memory context
- Acceptance criterion: agent can resume work after 7+ day gap without re-asking known facts

**This phase = final validation of the complete infrastructure.**
