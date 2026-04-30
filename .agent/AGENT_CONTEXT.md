# AGENT_CONTEXT — openclaw-agent-memory-infra

_Infra agent scaffold. Created via handoff sequence PR W4. Do not edit manually._

---

## Project Identity

| Field | Value |
|-------|-------|
| Repo | `openclaw-agent-memory-infra` |
| Role | OpenClaw infrastructure — agent memory system, hooks, onboarding, MeridianA proxy |
| Primary agent | infra-agent (this session) |
| Operator | @pariloff |
| Cold-test status | Active — MeridianA install reproducible (PR #22 merged), rebase audit done (PR #23 merged) |

---

## Workspace Layout

Two-level memory hierarchy:

```
~/projects/<project>/.agent/memory/topic-<id>.md   ← topic containers (workspace, not committed to product repos)
<repo>/.agent/                                       ← product scaffold (committed, PR-gated)
```

This file lives at level 2 (product scaffold) inside `openclaw-agent-memory-infra`.

---

## Memory Topic Registry

| Topic ID | Label | Location | Notes |
|----------|-------|----------|-------|
| 15222 | infra-agent-memory | `.agent/memory/topic-15222.md` (this repo) | Batch 0 — seeded in W4 PR |
| 13350 | Telemost_Review | `~/projects/telemost/.agent/memory/topic-13350.md` | Local workspace only — not committed to product repo |
| 7301 | (existing) | `~/projects/telemost/.agent/memory/topic-7301.md` | Pre-existing |

---

## Repo PR History

| PR | Title | Status |
|----|-------|--------|
| #19 | Full UX redesign — onboarding, handoff, automatic indexing | merged |
| #20 | Automatic initial memory indexing — runtime implementation | merged |
| #21 | PreToolUse hook self-healing runbook and fix script | merged |
| #22 | Reproducible MeridianA install — patch, script, tests, docs | merged |
| #23 | Meridian public upstream rebase audit | merged |
| #24 | Agent scaffold W1+W2 (.agent/ directory) | this PR |

---

## Key Documents

| Path | Purpose |
|------|---------|
| `docs/EXTERNAL_TO_INFRA_HANDOFF.md` | Handoff protocol sequence (Orientation → Prerequisites → Topic Resolution → Project Intake → Setup → Post-Setup Verification) |
| `docs/MERIDIANA_DEPENDENCY.md` | MeridianA v1.30.2 vendored install guide |
| `docs/MERIDIANA_REBASE_AUDIT.md` | PR #23 forensic audit — 6 patches, 7 failing hunks against 1.40.0 |
| `docs/FULL_ENVIRONMENT_ONBOARDING.md` | End-to-end cold-start onboarding (Gate I = MeridianA install) |
| `scripts/install-meridiana.sh` | Reproducible install script — uses `npm ci --omit=dev`, fails fast on missing lockfile |
| `vendor/meridiana-dist/` | 14 compiled JS files (744 KB), exact-pinned deps, package-lock.json |

---

## Active Constraints (from operator, 2026-04-30)

- Do not modify `~/projects/telemost/olcRTC/.agent/` during setup
- Do not commit local runtime memory from `~/projects/telemost/.agent/` to any product GitHub repo
- W3 (topic-13350.md) is local-only workspace memory
- All commits to this repo go through PR, not direct main push

---

## Pending Workstreams

| ID | Work | Notes |
|----|------|-------|
| PR23-impl | Port OpenClaw adapter to @rynfar/meridian@1.40.0 | Does not block cold test; openclaw.ts must be created from scratch |
| security | groupPolicy=open hardening (Telegram allowlist) | Accepted for cold test, follow-up later |
| docs | Update stale openclaw config commands in FULL_ENVIRONMENT_ONBOARDING.md §F and §G | Minor |
