# Roadmap

## Phase 0 — Source of Truth

- [x] Create local infrastructure repo.
- [x] Add original shared-memory infrastructure specification.
- [x] Add context-access scope extension.
- [x] Add pilot environment inventory from olcRTC.

## Phase 1 — Context Access Stabilization

- [ ] Inventory current context scripts and skills.
- [ ] Diagnose OpenClaw Telegram skill/native command execution failure.
- [ ] Define stable script-first CLI contract.
- [ ] Make stats/search/read/archive behavior reproducible.
- [ ] Add lock/flood-wait handling strategy for Pyrogram userbot reads.
- [ ] Document fallback order: memory archive → OpenClaw transcripts → Telegram live read.

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
