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

## Phase 3 — Candidate Knowledge Pipeline

- [ ] Define YAML candidate schema.
- [ ] Implement candidate validator.
- [ ] Implement bounded extractor from selected sources.
- [ ] Implement low-risk promotion.
- [ ] Implement pending approval report.

## Phase 4 — Pilot on olcRTC

- [ ] Apply template to olcRTC in a separate controlled step.
- [ ] Run limited extraction on allowed topics.
- [ ] Produce first migration report.
- [ ] Validate handoff flow: task → implementation → review → memory delta.

## Phase 5 — Portability

- [ ] Document setup for another OpenClaw instance.
- [ ] Add sanitized example configs.
- [ ] Decide whether to publish a GitHub remote.
