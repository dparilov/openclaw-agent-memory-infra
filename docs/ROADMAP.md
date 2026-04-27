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
- [ ] Write skill invocation vocabulary: how to call `/archive-context`, `/read-context`, `/read-topic` and when to use each.
- [ ] Add `.agent-template/` structure.
- [ ] Add runbooks for Coder, Reviewer, Infrastructure Agent.
- [ ] Add task/review handoff templates.
- [ ] Add memory extraction and promotion policies.

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
