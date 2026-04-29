# Automatic Initial Indexing

> **Status: product design contract.**  
> The runtime indexer is not implemented in this PR.  
> Until implementation lands, infra agents must treat this document as the required behavior
> and report when a step is simulated or unavailable.

## Core Principle

When an agent first encounters a topic with existing session history, it **automatically**  
reads and indexes that history. This is a read/index operation — no per-fact human review  
is required, and no new human commands are introduced.

Automatic indexing is the **default path**. Manual migration (see  
`docs/MEMORY_MIGRATION_PLAYBOOK.md`) is the exception for advanced or unusual cases.

---

## How It Fits Into Existing Commands

No new commands are added. Automatic indexing happens as a side effect of:

| Existing command | Intended indexing behavior |
|-----------------|--------------------------|
| Agent starts on a topic | On first turn if no baseline index exists |
| `RECOVER MEMORY` | Rebuilds baseline index + applies deltas |
| `PRE-LIVE CHECK` | Detects missing baseline, triggers index if absent |

Operators do **not** need to explicitly invoke indexing. If the agent reports  
"no baseline index found", run `RECOVER MEMORY` and the agent will index automatically.

---

## Target Artifact Structure

After indexing, the agent writes to `.agent/memory/index/topic-<id>/`:

```
.agent/memory/index/topic-<id>/
├── INDEX_META.json        # schema version, source commit range, index timestamp
├── timeline.md            # chronological event summary (human-readable)
├── cluster-map.md         # thematic clusters with evidence references
├── sensitive-map.md       # flags any PII / credentials detected (no raw values)
├── recovery-index.md      # minimal fact set needed to recover agent context
└── windows/               # sliding window summaries (optional, large topics only)
    ├── 001.md
    └── ...
```

---

## Product Repo Policy

| Artifact | Commit to product repo? |
|----------|------------------------|
| `.agent/AGENT_CONTEXT.md` | **YES** — always commit |
| `.agent/handoffs/` | **YES** — always commit |
| `.agent/memory/reports/` | **YES, after human review** — do not commit reports containing secret values or unreviewed sensitive findings |
| `.agent/memory/candidates/` | **NO** — do not commit by default |
| `.agent/memory/raw/` | **NO** — do not commit |
| `.agent/memory/index/` | **NO** — do not commit |
| `.agent/memory/wiki/` | **NO** — do not commit |

Add untracked paths to `.gitignore` in the product repo if needed:

```gitignore
# Agent memory — do not commit
.agent/memory/candidates/
.agent/memory/raw/
.agent/memory/index/
.agent/memory/wiki/
```

---

## Sensitive Data Behaviour

The indexer scans for common sensitive patterns (API keys, tokens, passwords, PII).  
When detected:

- The value is **not stored** in any index artifact
- A flag is written to `sensitive-map.md` with the session ID and field name only
- The operator is notified in the next ORIENTATION REPORT

If you believe a session contains sensitive data, run `PRE-LIVE CHECK` before  
allowing the agent to index it.

---

## Human Approval Points

Automatic indexing does **not** require per-fact approval. Human approval is required at:

1. **Cluster-level decisions** — when the agent proposes to promote a cluster to wiki
2. **Architecture decisions** — any candidate with `type: architecture_decision`
3. **Sensitive-map review** — before indexing resumes after a sensitive-data flag

Everything else proceeds automatically.
