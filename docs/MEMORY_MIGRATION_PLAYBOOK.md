# Memory Migration Playbook

> ⚠️ **Manual migration is an advanced, exceptional workflow.**
>
> **When to use:** you have pre-existing session history that the agent has never seen,
> AND automatic initial indexing (see `docs/AUTOMATIC_INITIAL_INDEXING.md`) is not
> sufficient — e.g., the history is too large, contains known sensitive data, or requires
> human curation before any indexing occurs.
>
> **When NOT to use:** for normal first-time setup, new topics, or routine memory
> recovery. Use `RECOVER MEMORY` instead (see `docs/HUMAN_COMMAND_CHEAT_SHEET.md`).
>
> **Product repo artifact policy:** raw session data, candidate files, index artifacts,
> and wiki drafts are NOT committed to product repos by default. Only commit
> `.agent/AGENT_CONTEXT.md`, `.agent/handoffs/`, and `.agent/memory/reports/`.

Safe staged process for migrating existing project history into the OpenClaw memory system.

Run this playbook when onboarding a project that already has agent work, session history,
notes, or legacy memory files. Each stage requires explicit human approval before proceeding.

---

## Non-Goals

```
Do not migrate secrets, tokens, or credentials into memory.
Do not auto-promote high-risk facts (architecture, security, access, policy).
Do not resolve memory conflicts silently — flag all conflicts for human review.
Do not start live-agent tests during migration.
Do not archive batches that have already been archived (check last-batch header).
```

---

## M0 — Source Inventory

**Read-only.** Infra agent enumerates available sources without writing anything.

Inventory targets:

```
OpenClaw session_history — coder, reviewer, infra topics
Repo docs                — docs/, .agent/, README, ADRs
PR history               — merged PRs with descriptions, important commit messages
Old memory files         — any existing topic-*.md, if present
Old notes                — ad-hoc markdown, shared docs, Telegram summaries
```

For each source, record in the inventory:

```
Source:                  <path or topic ID>
Type:                    session_history / repo_doc / pr_history / memory_file / notes
Coverage:                <date range or batch range>
Already archived:        yes / no / partial
Sensitive data risk:     none / possible / confirmed (do not copy values)
```

Output: inventory table posted to human for review.

---

## M1 — Migration Map

**Read-only.** Infra agent produces a proposed migration plan for human approval.

For each source from M0, record:

```
Source:                  <reference>
Useful knowledge:        high / medium / low / none
Risk level:              low / medium / high
Proposed target layer:   L0 (raw archive) / L1 (candidates) / L2 (memory) / L4 (docs)
Human approval required: yes / no
Sensitive data risk:     none / possible / confirmed
```

Migration map example:

| Source | Useful | Risk | Target | Human approval | Sensitive |
|--------|--------|------|--------|----------------|-----------|
| coder session batch 0–5 | high | low | L0 → L1 → L2 | no (auto-promote eligible) | none |
| reviewer session batch 0–3 | high | medium | L1 → human review | yes | none |
| old notes.md | medium | high | L4 candidate | yes | possible |
| infra topic | low | low | L0 archive only | no | none |

**Wait for human approval of the migration map before proceeding.**

---

## M2 — Read / Preview Source Batches

**Read-only.** Inspect available batches and preview content before any write.

Rules:
- Do not write or promote in this stage.
- Check `last-batch` header to identify already-archived batches.
- Preview each batch before passing to M3.

```bash
# Check batch status for a topic
python .agent/tools/context_access/archive-batch-v2.py <topic-id> --status

# Preview a specific batch (save for M3 extraction)
python .agent/tools/context_access/archive-batch-v2.py <topic-id> --batch N > /tmp/topic-N-batch.txt
```

Report after each source:

```
Source: <topic-id>
Batches available: <N>
Already archived: <M>
Previewed to: /tmp/topic-N-batch.txt
Status: OK / ERROR
```

---

## M3 — Extract Durable Facts and Create Candidates

**Write.** Extract durable bullet facts from batch previews and create candidates.

Step 1 — manually extract durable facts from the previewed batch into a facts file (`facts.txt`), one fact per line.

Step 2 — create candidates with full evidence flags:

```bash
python .agent/tools/context_access/manage-candidates.py <topic> \
  --add facts.txt \
  --memory-dir .agent/memory \
  --source-kind session_history \
  --source-ref "topic:<topic-id> batch:<N>" \
  --locator "batch:<N>"
```

For each candidate, the agent must record:

```
Text:         <fact text>
Evidence:     <source reference — topic, batch N>
Risk:         low / medium / high
Confidence:   high / medium / low
Provenance:   <topic / session>
Status:       candidate (initial)
```

Do not promote any candidates in this stage. All candidates wait for M4.

---

## M4 — Human Approval

**Approval gate.** High-risk candidates require explicit human decision.

High-risk categories (always require approval):

```
architecture_decision
constraint
process_rule
security / deployment / access
merge policy
agent authority boundary
canonical project decisions
```

For each high-risk candidate, the agent presents:

```
Candidate ID: <CAND-XXXXXXXX>
Type:         <fact_type>
Text:         <fact text>
Evidence:     <source reference>
Risk:         high
Options:      A) Approve → promote to L2
              B) Reject → discard
              C) Defer → leave as needs-approval
              D) Rewrite → human provides corrected text
```

Low-risk candidates may be auto-promoted after human confirms M1 map allows it:

```bash
python .agent/tools/context_access/manage-candidates.py <topic> \
  --promote-auto \
  --memory-dir .agent/memory
```

---

## M5 — Build Wiki + Validate

**Write + Read.** After each migration pass, rebuild and validate the wiki.

```bash
python .agent/tools/context_access/build-wiki.py \
  --memory-dir .agent/memory

python .agent/tools/context_access/validate-wiki.py \
  --memory-dir .agent/memory
```

For strict mode (treat warnings as errors):

```bash
python .agent/tools/context_access/validate-wiki.py \
  --memory-dir .agent/memory \
  --strict
```

If validator returns errors: **stop, report to human, do not proceed to next source.**

If validator returns only warnings: report to human, proceed only with explicit approval.

---

## M6 — Migration Report

**Write.** After each migration pass (or at end of full migration), write a report.

Output path:

```
.agent/handoffs/<YYYY-MM-DD>-migration-report.md
```

Required report sections:

```markdown
# Migration Report — <date>

## Sources Processed
<table: source / batches / facts archived>

## Candidates Created
<count> total: <count> low-risk / <count> medium / <count> high-risk

## Promoted Facts
<count> auto-promoted / <count> human-approved

## Pending Approval
<list of candidate IDs still in needs-approval state>

## Conflicts
<list of CONFLICT markers found during promotion, with source references>

## Validator Result
<paste validate-wiki.py output>

## Next Actions
<list: remaining sources / pending approvals / open questions for human>
```

Post the report to the infra topic and notify the human.

---

## Stage Gate Summary

| Stage | Action | Human gate |
|-------|--------|-----------|
| M0 | Source inventory | Review required |
| M1 | Migration map | Approval required before M2 |
| M2 | Read / preview source batches | Approval of M1 map sufficient |
| M3 | Extract facts and create candidates | No additional gate |
| M4 | Promote candidates | High-risk: explicit approval per candidate |
| M5 | Build + validate wiki | Errors: stop and report |
| M6 | Write migration report | No gate — always write |
