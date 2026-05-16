# Simplification Inventory — Memory Extractor v1

**Branch:** `docs/simplify-memory-extractor-inventory`  
**Date:** 2026-05-16  
**Purpose:** Classify all repo files against v1 keep criteria.  
**Scope:** No code changes in this PR — inventory and cleanup plan only.

---

## v1 Keep Criteria

A file is **KEEP_FOR_V1** if it:
- Helps explicitly read context (Telegram topic, JSONL, Markdown, operator notes)
- Helps archive context into Markdown chunks
- Helps generate a small working Markdown memory pack
- Helps protect secrets
- Has simple deterministic tests

A file is **DEPRECATE_FOR_V1** if it:
- Implements candidate promotion as a user-facing workflow
- Builds or validates a wiki
- Assumes vector DB / embeddings / memory-core
- Implements heavy phase/gate UX
- Depends on cross-topic SendMessage

---

## Scripts (`scripts/`)

| File | Classification | Reason |
|------|---------------|--------|
| `scripts/context_access/read-topic.py` | **KEEP_FOR_V1** | Bounded Pyrogram/topic read is a v1 input source; `--batch-format` output feeds extraction |
| `scripts/context_access/initial-index.py` | **KEEP_FOR_V1 (helper, not mandatory)** | Useful for clustering/windowing session content; v1 must not require it, but it may assist |
| `scripts/context_access/archive-batch-v2.py` | **KEEP_FOR_V1 (needs output format decision — see UNKNOWN)** | Core append logic and JSONL → Markdown pipeline is sound; output targets `topic-<id>.md` not `working/*.md` |
| `scripts/context_access/io_utils.py` | **KEEP_FOR_V1** | Shared IO utilities used by read-topic and archive-batch; no v1 conflict |
| `scripts/context_access/manage-candidates.py` | **DEPRECATE_FOR_V1** | L1 candidate promotion workflow is explicitly out of v1 scope |
| `scripts/context_access/build-wiki.py` | **DEPRECATE_FOR_V1** | Mandatory wiki build is a v1 non-goal |
| `scripts/context_access/validate-wiki.py` | **DEPRECATE_FOR_V1** | Wiki integrity checks only make sense with wiki build; no v1 role |
| `scripts/onboard-project.py` | **KEEP_FOR_V1** | Preflight, scaffold detection, tool sync; does not write memory — safe to keep |

---

## Tests (`tests/`)

| File | Classification | Reason |
|------|---------------|--------|
| `tests/test_onboard_project.py` | **KEEP_FOR_V1** | Covers onboard-project.py; deterministic, no external deps |
| `tests/test_initial_index.py` | **KEEP_FOR_V1** | Covers initial-index.py helper; keep while helper is kept |
| `tests/context_access/test_archive_batch_v2.py` | **KEEP_FOR_V1** | Covers archive-batch-v2.py; core extraction logic |
| `tests/test_io_utils.py` | **KEEP_FOR_V1** | Utility coverage; no v1 conflict |
| `tests/test_read_topic_portability.py` | **KEEP_FOR_V1** | Portability checks for read-topic.py |
| `tests/test_dry_run.py` | **KEEP_FOR_V1** | Dry-run safety checks; directly relevant to v1 safety contract |
| `tests/test_candidates.py` | **REMOVE_LATER** | Only covers manage-candidates.py (deprecated for v1) |
| `tests/test_validate_wiki.py` | **REMOVE_LATER** | Only covers validate-wiki.py (deprecated for v1) |
| `tests/test_wiki_provenance.py` | **REMOVE_LATER** | Wiki provenance; no v1 role |
| `tests/test_wiki_rendering_provenance.py` | **REMOVE_LATER** | Wiki rendering; no v1 role |
| `tests/test_setup_smoke.py` | **KEEP_FOR_V1** | Smoke test for setup structure; low-risk |
| `tests/test_setup_structure.py` | **KEEP_FOR_V1** | Repo structure checks; low-risk |
| `tests/test_fix_pretooluse_hook.py` | **UNKNOWN_NEEDS_DECISION** | Covers a hook fix script — unclear if hook is still used in v1 flow |
| `tests/test_install_meridiana.py` | **UNKNOWN_NEEDS_DECISION** | MeridianA is an optional accelerator; unclear if still relevant |
| `tests/test_name_resolver_e2e.py` | **UNKNOWN_NEEDS_DECISION** | E2E test — unclear scope without reading the source |

---

## Docs (`docs/`)

| File | Classification | Reason |
|------|---------------|--------|
| `docs/MEMORY_EXTRACTION_POLICY.md` | **KEEP_FOR_V1** | Defines what facts to extract; directly maps to v1 extraction logic |
| `docs/FALLBACK_ORDER.md` | **KEEP_FOR_V1** | Context fallback chain (JSONL → Pyrogram → operator notes); directly v1 relevant |
| `docs/ONBOARD_PROJECT_CLI.md` | **KEEP_FOR_V1** | Documents onboard-project.py; keep as-is |
| `docs/COLD_TEST_FINDINGS_2026-05-04.md` | **KEEP_FOR_V1** | Live findings that shaped v1 constraints; keep as reference |
| `docs/COLD_TEST_FINDINGS_2026-04-30.md` | **KEEP_FOR_V1** | Earlier findings; keep as historical reference |
| `docs/CONTEXT_ACCESS_SCOPE.md` | **KEEP_FOR_V1** | Defines what context is accessible to agents; v1 relevant |
| `docs/SENSITIVE_DATA_HANDLING.md` | **KEEP_FOR_V1** | Secrets policy; v1 must protect secrets — directly relevant |
| `docs/PYROGRAM_FLOOD_WAIT.md` | **KEEP_FOR_V1** | Operational runbook for read-topic.py failures |
| `docs/EXTERNAL_TO_INFRA_HANDOFF.md` | **KEEP_FOR_V1** | Escalation path; keep |
| `docs/AGENT_COLLABORATION_PROTOCOL.md` | **KEEP_FOR_V1** | Agent coordination rules; keep |
| `docs/PROJECT_HISTORY.md` | **KEEP_FOR_V1** | Historical context for this repo itself |
| `docs/OAUTH_GATE_CARDS.md` | **KEEP_FOR_V1** | Auth remediation cards for onboarding; keep while onboard-project.py is kept |
| `docs/BOOTSTRAP_PREREQUISITES.md` | **KEEP_FOR_V1** | Concise env prerequisites; keep |
| `docs/deployment.md` | **KEEP_FOR_V1** | Deployment reference; keep |
| `docs/INCIDENT_OPENCLAW_2026_5_RUNTIME_CHUNKS_2026-05-04.md` | **KEEP_FOR_V1** | Incident record; keep as historical reference |
| `docs/MEMORY_OUTPUT_CONTRACT.md` | **UNKNOWN_NEEDS_DECISION** | Defines `topic-<id>.md` format (L2 append-only); v1 uses `working/*.md` instead — these are different schemas. Decide: keep as L2 spec alongside v1 working files, or supersede? |
| `docs/CANDIDATE_SCHEMA.md` | **DEPRECATE_FOR_V1** | L1 candidate schema; candidate promotion is out of v1 scope |
| `docs/AUTOMATIC_INITIAL_INDEXING.md` | **DEPRECATE_FOR_V1** | Describes mandatory automatic indexing flow; v1 does not mandate initial-index.py |
| `docs/OPENCLAW_SHARED_MEMORY_INFRA_SPEC.md` | **DEPRECATE_FOR_V1** | Describes heavy L0–L4 multi-layer system with vector search; conflicts with v1 simplification goal |
| `docs/SETUP_WIZARD_FLOW.md` | **DEPRECATE_FOR_V1** | 9-phase wizard UX; replaced by simple 3-step user flow in v1 |
| `docs/FULL_ENVIRONMENT_ONBOARDING.md` | **DEPRECATE_FOR_V1** | 10-gate full env audit; too heavy for v1 |
| `docs/FINAL_AGENT_INSTRUCTION_PACK.md` | **UNKNOWN_NEEDS_DECISION** | Wizard Phase 8 output; may be superseded by a simpler agent startup instruction |
| `docs/MERIDIANA_DEPENDENCY.md` | **UNKNOWN_NEEDS_DECISION** | MeridianA is listed as optional accelerator; unclear if it has any v1 role |
| `docs/MERIDIANA_DISCOVERY_REPORT.md` | **UNKNOWN_NEEDS_DECISION** | Same |
| `docs/MERIDIANA_REBASE_AUDIT.md` | **UNKNOWN_NEEDS_DECISION** | Same |
| `docs/PRE_LIVE_CHECKLIST.md` | **UNKNOWN_NEEDS_DECISION** | Pre-live integrity workflow; references wiki build and validate-wiki — partially relevant |
| `docs/TARGET_PROJECT_SELECTION.md` | **KEEP_FOR_V1** | Project selection modes and ACK format; used by onboard-project.py |
| `docs/SKILL_VOCABULARY.md` | **UNKNOWN_NEEDS_DECISION** | Describes when to call each skill; some skills (compact-memory, recover-memory) may be too heavy for v1 |
| `docs/PROJECT_DISCOVERY_FROM_TOPICS.md` | **UNKNOWN_NEEDS_DECISION** | Unclear scope without reading |
| `docs/PROJECT_INTAKE_QUESTIONNAIRE.md` | **UNKNOWN_NEEDS_DECISION** | Unclear if this is still used |
| `docs/PRETOOLUSE_HOOK_RUNBOOK.md` | **UNKNOWN_NEEDS_DECISION** | Hook self-healing runbook; unclear v1 relevance |
| `docs/ARCHIVE_CONTEXT_ANALYSIS.md` | **KEEP_FOR_V1** | Analysis of archive-context flow; relevant to keeping archive-batch-v2.py |
| `docs/TELEGRAM_CHANNEL_READER.md` | **KEEP_FOR_V1** | Documents read-topic.py; relevant |
| `docs/runbooks/CODER_AGENT.md` | **KEEP_FOR_V1** | Agent runbook; keep |
| `docs/runbooks/REVIEWER_AGENT.md` | **KEEP_FOR_V1** | Agent runbook; keep |
| `docs/runbooks/INFRA_AGENT.md` | **KEEP_FOR_V1** | Agent runbook; keep |
| `docs/runbooks/HANDOFF_TEMPLATE.md` | **KEEP_FOR_V1** | Session handoff template; keep |

---

## Skills (`skills/`)

| File | Classification | Reason |
|------|---------------|--------|
| `skills/read-topic/SKILL.md` | **KEEP_FOR_V1** | Reads topic context; directly v1 relevant |
| `skills/archive-context/SKILL.md` | **KEEP_FOR_V1** | Archives session facts to Markdown; directly v1 relevant |
| `skills/recover-memory/SKILL.md` | **UNKNOWN_NEEDS_DECISION** | 4-step full restore; may be too heavy for v1, but the stale-memory case is real |
| `skills/compact-memory/SKILL.md` | **DEPRECATE_FOR_V1** | Requires LLM compaction pass and candidates; out of v1 scope |

---

## Agent Template (`.agent-template/`)

| File | Classification | Reason |
|------|---------------|--------|
| `.agent-template/AGENT_CONTEXT.md` | **KEEP_FOR_V1 (needs update)** | Template for target projects; currently references `topic-<id>.md` commands and `/read-context` skill — needs updating to reflect `working/*.md` startup load order |
| `.agent-template/bootstrap.sh` | **KEEP_FOR_V1** | Scaffold helper; keep |
| `.agent-template/memory/.gitkeep` | **KEEP_FOR_V1** | Directory placeholder; harmless |

---

## Root Files

| File | Classification | Reason |
|------|---------------|--------|
| `README.md` | **UNKNOWN_NEEDS_DECISION** | Describes old L0–L4 system with complex toolchain; will need rewrite once v1 shape is finalised — do not touch yet |
| `examples/olcRTC/environment-inventory.md` | **KEEP_FOR_V1** | Example inventory for a target project; harmless reference |
| `.github/workflows/ci.yml` | **KEEP_FOR_V1** | CI; keep |
| `.gitignore` | **KEEP_FOR_V1** | Gitignore; keep |

---

## Summary Counts

| Classification | Count |
|---------------|-------|
| KEEP_FOR_V1 | ~38 |
| DEPRECATE_FOR_V1 | ~10 |
| REMOVE_LATER | ~4 |
| UNKNOWN_NEEDS_DECISION | ~14 |

---

## Key Decision Points (UNKNOWN items requiring resolution)

| # | Item | Question |
|---|------|----------|
| D-1 | `docs/MEMORY_OUTPUT_CONTRACT.md` + `archive-batch-v2.py` | v1 writes to `working/*.md`; archive-batch-v2.py writes to `topic-<id>.md` (L2 append-only). Do these coexist (different purposes) or does v1 replace L2 with working/*.md? **Recommendation: coexist — working/*.md is the compiled human-reviewed pack; topic-<id>.md remains the raw append log.** |
| D-2 | `skills/recover-memory/SKILL.md` | 4-step restore is heavy but the stale-memory problem is real. Simplify to a 2-step version (read working/*.md + re-run extraction if >24h stale) or keep as-is? |
| D-3 | `README.md` | Describes old L0–L4 system. Needs rewrite once v1 shape is locked. Do not rewrite in this PR — flag for PR3+. |
| D-4 | MeridianA docs (3 files) | MeridianA is listed as optional accelerator. Is it still used in any v1 workflow? If not, move to DEPRECATE_FOR_V1. |
| D-5 | `docs/FINAL_AGENT_INSTRUCTION_PACK.md` | Wizard Phase 8 output; does v1 produce its own agent instruction pack (from AGENT_CONTEXT.md + working/*.md), or does this doc stay? |
| D-6 | `docs/PRE_LIVE_CHECKLIST.md` | References wiki build and validate-wiki (both deprecated for v1). Update to remove wiki steps, or deprecate? |
| D-7 | `docs/SKILL_VOCABULARY.md` | Mixed: read-topic and archive-context are v1; compact-memory is deprecated. Update to reflect v1 skills only, or deprecate? |
| D-8 | `tests/test_fix_pretooluse_hook.py` | Keep if PreToolUse hook is still part of v1 setup; remove if not. |
| D-9 | `tests/test_install_meridiana.py` | Keep if MeridianA is v1; remove otherwise (tied to D-4). |
| D-10 | `tests/test_name_resolver_e2e.py` | Need to read the source to classify. |
| D-11 | `docs/PROJECT_INTAKE_QUESTIONNAIRE.md` | Still used? Or replaced by AGENT_CONTEXT.md template? |
| D-12 | `docs/PROJECT_DISCOVERY_FROM_TOPICS.md` | Still used? Or superseded by simpler flow? |
| D-13 | `docs/PRETOOLUSE_HOOK_RUNBOOK.md` | Is PreToolUse hook still relevant to v1 agent setup? |
| D-14 | `.agent-template/AGENT_CONTEXT.md` update | Currently references L2 commands and `/read-context`; needs updating to `working/*.md` startup order — but do not change until v1 working file format is locked (D-1). |

---

## Warnings

- `archive-batch-v2.py` output format (`topic-<id>.md`) differs from v1 working files (`working/*.md`). These serve different roles — do not conflate. Resolve D-1 before writing any extraction script.
- `initial-index.py` is listed as KEEP_FOR_V1 (helper) but the new `docs/PROJECT_MEMORY_EXTRACTOR_V1.md` (committed to branch `docs/pr29-clarify-onboard-cli-mvp-status`, not yet on main) introduced it as a mandatory Step 1. That doc needs updating to reflect "helper, not mandatory" once this inventory is reviewed.
- `docs/SETUP_WIZARD_FLOW.md` and `docs/FULL_ENVIRONMENT_ONBOARDING.md` are deprecated for v1 but should not be deleted — they remain valid for full cold-start scenarios. Mark as `[HEAVY — not v1 path]` in their headers in a later PR.

---

## Blockers

None for this PR. The inventory does not change any code or delete any files.  
Decisions D-1 through D-14 should be resolved before implementation PRs begin.

---

## Recommended Next PRs

| PR | Scope |
|----|-------|
| **PR2** | Resolve D-1 (output format decision) and update `.agent-template/AGENT_CONTEXT.md` to reflect v1 startup load order |
| **PR3** | Implement `scripts/extract-memory.py` — deterministic context prep + extraction prompt builder (no LLM API calls inside the script) |
| **PR4** | Update README.md to describe v1 flow; deprecate SETUP_WIZARD_FLOW and FULL_ENVIRONMENT_ONBOARDING |
| **PR5** | Remove REMOVE_LATER test files once their source modules are formally deprecated |
