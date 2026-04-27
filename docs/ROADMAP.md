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
- [ ] Add lock/flood-wait handling strategy for Pyrogram userbot reads.
- [ ] Document fallback order: memory archive → OpenClaw transcripts → Telegram live read.
- [ ] Test name resolver end-to-end in telemost topic (verify `telemost` resolves to `7301`).

## Phase 2 — Portable Templates

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

## Phase 6 — Archive Writer (next after Phase 1 complete)

- [ ] Define output contract for `memory/topic-<id>.md`.
- [ ] Implement `--write` mode in `archive-batch-v2.py` (or separate `archive-writer.py`).
- [ ] Add idempotency: skip already-written batches.
- [ ] Integrate `--mark-done` into write flow.
- [ ] Validate: no duplicate memory entries across batches.
