# OpenClaw Agent Memory Infra

Infrastructure project for reproducible multi-agent development workflows on OpenClaw / Meridian / MeridianA / Codex / Claude-style agents.

Goal: provide portable task/review handoff, context access, shared memory ingestion, candidate knowledge extraction, low-risk promotion, and human approval workflows.

This repository is the source of truth for the infrastructure itself.

Pilot project: `olcRTC / Telemost`.

## Source of Truth Model

- This repo: canonical infrastructure specs, scripts, skills, templates, and runbooks.
- Consumer project repos: pilot/adopter-specific `.agent/` state and project artifacts.
- Telegram/session history/OpenClaw transcripts: evidence, not truth.
- Agent memory files: operational memory, not canonical unless promoted into this repo or a consumer repo by policy.

## Initial Docs

- `docs/OPENCLAW_SHARED_MEMORY_INFRA_SPEC.md` — original project specification / onboarding document.
- `docs/CONTEXT_ACCESS_SCOPE.md` — scope for reliable Telegram/topic/transcript context access and memory ingestion.
- `docs/ROADMAP.md` — first implementation roadmap.
- `examples/olcRTC/environment-inventory.md` — pilot inventory snapshot.
