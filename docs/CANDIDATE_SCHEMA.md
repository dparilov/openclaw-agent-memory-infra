# Candidate Schema v1

> L1 Candidate Knowledge — data model for facts waiting to be promoted to L2 working memory.

---

## Purpose

Every fact that passes through the L1 candidate layer must be traceable:
- **Where** did this come from?
- **When** was it observed?
- **How confident** are we?
- **What is the risk** of promoting it?
- **Who/what** promoted it, and why?

This schema enforces these requirements before any fact reaches L2.

---

## Full Schema

```yaml
# Required fields
id: CAND-20260427-0001          # Unique ID: CAND-YYYYMMDD-NNNN or CAND-<uuid8>
schema_version: 1               # Must be 1
created_at: "2026-04-27T20:00:00+03:00"
created_by: "infra-agent"       # agent name, session ID, or "human"
topic_id: "7301"

# Optional metadata
project: "openclaw-agent-memory-infra"  # Optional — omit if single-project setup

type: "architecture_decision"   # See type list below
claim: "The project uses L0-L4 memory layers."
summary: "Short human-readable explanation of the claim and why it matters."

# Evidence — required for promotion, must be non-empty
evidence:
  - kind: "session_history"     # See evidence kinds below
    topic_id: "7301"
    file: "/path/to/session.jsonl"
    locator: "messages 1842-1855"
    observed_at: "2026-04-27T20:00:00+03:00"
  - kind: "repo_doc"
    path: "docs/ROADMAP.md"
    locator: "Phase 4"
    observed_at: "2026-04-27T20:00:00+03:00"

confidence: "medium"            # low | medium | high
risk: "medium"                  # low | medium | high
                                # NOTE: only risk=low qualifies for auto-promotion

classification:
  auto_promotable: false
  needs_human_approval: true
  reason: "Architecture decision type always requires human approval."

# Optional fields
suggested_targets:
  - ".agent/memory/working/active-decisions.md"
  - "docs/adr/ADR-memory-layers.md"

related:                        # Optional
  tasks: []
  prs: []
  decisions: []
  candidates: []

status: "needs-approval"        # See status lifecycle below

# Human review — populated when status reaches approved/rejected
human_review:
  required: true
  decision: null                # null | "approved" | "rejected"
  reviewer: null                # name or agent ID
  reviewed_at: null
  notes: null
```

---

## Field Definitions

### `type`

| Type | Risk | Auto-promotable | Description |
|------|------|-----------------|-------------|
| `fact` | low | yes | Objective observable fact |
| `person` | low | yes | Person/role/contact info |
| `project_state` | low–medium | yes (if low-risk) | Current project status |
| `preference` | low | yes | Non-binding style/preference |
| `resolved_issue` | low | yes | Fixed bug, closed task |
| `architecture_decision` | high | **never** | Structural/design decision |
| `constraint` | high | **never** | Hard rule or limitation |
| `process_rule` | high | **never** | Workflow, policy, or procedure |
| `agent_policy` | high | **never** | Agent behavior rules |
| `security_note` | high | **never** | Security-sensitive fact |
| `rejected_approach` | high | **never** | Explicitly discarded direction |

### `confidence`

| Value | Meaning |
|-------|---------|
| `low` | Inferred, unconfirmed, or single source |
| `medium` | Observed in multiple places or confirmed by context |
| `high` | Explicit statement from authoritative source |

### `risk`

| Value | Meaning |
|-------|---------|
| `low` | Safe to act on without human review |
| `medium` | Review recommended before acting |
| `high` | Must not be used without explicit human approval |

### Evidence kinds

The `kind` field must be one of the following (enforced by `VALID_EVIDENCE_KINDS` in `manage-candidates.py` and argparse `choices`):

| Kind | Description |
|------|-------------|
| `session_history` | OpenClaw JSONL session transcript |
| `repo_doc` | File in this repository |
| `pr` | GitHub pull request |
| `review` | Code or design review comment |
| `pyrogram` | Live Telegram message read via Pyrogram |
| `memory_md` | Existing `.agent/memory/topic-*.md` entry |
| `manual` | Human-entered fact |
| `candidate` | Derived from another candidate |

**All three fields `kind`, `ref`, and `locator` must be non-empty strings.** `observed_at` is also required. Validation is enforced by `validate_evidence_entry()` and `make_evidence_entry()`.

---

## Status Lifecycle

```
candidate
    │
    ├─────────────────────────────────────┐
    │  (auto_promotable = true            │  (needs_human_approval = true
    │   risk = low, evidence non-empty,   │   OR risk = medium/high
    │   no high-risk keywords)            │   OR high-risk type)
    ▼                                     ▼
auto-promoted                      needs-approval
    │                                     │
    │  (written to L2)           ┌────────┤
    ▼                            ▼        ▼
(done)                       approved  rejected
                                 │
                                 ▼
                           (written to L2)

Also possible:
  duplicate   → superseded by existing L2 fact
  obsolete    → superseded by newer candidate on same topic
```

---

## Auto-Promotion Gate

A candidate is auto-promotable **only if ALL** of the following are true:

| Condition | Requirement |
|-----------|-------------|
| `status` | `"candidate"` |
| `risk` | `"low"` — **medium and high are NOT auto-promotable** |
| `confidence` | `"medium"` or `"high"` |
| `evidence` | Non-empty list with valid entries (kind, ref, locator all non-empty) |
| `type` | In auto-promotable type list |
| `claim` | No high-risk keywords (see below) |
| `classification.auto_promotable` | `true` |
| Schema | `schema_version == 1` and all required fields valid |

### High-risk keywords (claim text scan)

Any claim containing these words/phrases is flagged as high-risk regardless of `type`:

```
architecture, canonical, source of truth,
deprecated, deprecate, suspended,
security, secret, credential, token, key,
billing, deployment, production,
permission, agent policy,
merge, release, auto-merge,
human approval
```

---

## Validation Rules

`manage-candidates.py --promote-auto` and `--approve` MUST refuse candidates that:

1. Have no `evidence` entries
2. Have `risk != "low"` (for auto-promotion)
3. Have `type` in high-risk type list (for auto-promotion)
4. Contain high-risk keywords in `claim` (for auto-promotion)
5. Have `schema_version` missing or != 1

---

## Migration Note

Candidates created before schema v1 (without `schema_version`, `evidence`, `confidence`, `risk`, `classification`) are treated as `schema_version: 0` (legacy).

### Runtime compatibility

`load_and_migrate()` applies `migrate_legacy()` at read-time as an **in-memory shim** — changes are NOT written to disk. This allows the tool to operate on legacy files without requiring a prior migration step.

### Persisting migration

Use `--migrate-legacy` to write v1-upgraded candidates to disk:

```bash
# Preview
python3 manage-candidates.py 7301 --migrate-legacy --dry-run

# Apply
python3 manage-candidates.py 7301 --migrate-legacy
```

### Migration defaults

| Field | Migrated default |
|-------|------------------|
| `schema_version` | `1` |
| `confidence` | `"medium"` |
| `risk` | `"medium"` |
| `evidence[0].kind` | `"manual"` |
| `evidence[0].ref` | `"legacy-migration"` |
| `evidence[0].locator` | `"migrated-v0"` *(non-empty, passes deep validation)* |
| `classification.auto_promotable` | `false` |
| `status` | `"needs-approval"` *(all non-terminal)* |

Migrated candidates are never auto-promoted. Human review is required before any L2 write.

---

## Example: Low-Risk Auto-Promotable Candidate

```yaml
id: CAND-20260427-0001
schema_version: 1
created_at: "2026-04-27T17:30:00Z"
created_by: "infra-agent"
project: "openclaw-agent-memory-infra"
topic_id: "15222"
type: "fact"
claim: "- archive-batch-v2.py deduplicates messages by telegram message ID"
summary: "Deduplication key is telegram:<chat>:<topic>:<msg>:<role> when metadata present."
evidence:
  - kind: "repo_doc"
    path: "scripts/context_access/archive-batch-v2.py"
    locator: "function dedupe_key"
    observed_at: "2026-04-27T17:30:00Z"
confidence: "high"
risk: "low"
classification:
  auto_promotable: true
  needs_human_approval: false
  reason: "Objective code fact, low risk, high confidence."
suggested_targets:
  - ".agent/memory/topic-15222.md"
related:
  tasks: []
  prs: []
  decisions: []
  candidates: []
status: "candidate"
human_review:
  required: false
  decision: null
  reviewer: null
  reviewed_at: null
  notes: null
```

## Example: High-Risk Candidate Requiring Approval

```yaml
id: CAND-20260427-0002
schema_version: 1
created_at: "2026-04-27T19:11:00Z"
created_by: "infra-agent"
project: "openclaw-agent-memory-infra"
topic_id: "15222"
type: "architecture_decision"
claim: "- Decided to use append-only memory format to avoid concurrent write conflicts"
summary: "The L2 memory file uses append-only batch sections. Compaction is a separate controlled operation."
evidence:
  - kind: "session_history"
    topic_id: "15222"
    file: "sessions/main-topic-15222.jsonl"
    locator: "message 15897"
    observed_at: "2026-04-27T16:10:00Z"
confidence: "high"
risk: "high"
classification:
  auto_promotable: false
  needs_human_approval: true
  reason: "Architecture decision. Affects all write operations."
suggested_targets:
  - "docs/adr/ADR-append-only-memory.md"
  - ".agent/memory/working/active-decisions.md"
related:
  tasks: []
  prs: []
  decisions: []
  candidates: []
status: "needs-approval"
human_review:
  required: true
  decision: null
  reviewer: null
  reviewed_at: null
  notes: null
```
