# V1 Working Memory Compile Contract

> Defines the contract for compiling raw Markdown archive chunks into the reviewed
> working memory pack that agents load at startup.
>
> This is a contract document — not implementation.
> Implementation is PR35.

---

## Goal

Define the v1 contract for compiling raw Markdown archive chunks into a small reviewed
Markdown memory pack that agents load at startup.

---

## Product flow

```text
raw/topic-<id>/chunk-*.md
+ .agent/AGENT_CONTEXT.md
+ optional operator notes
→ draft working/*.md
→ final human diff review
→ agents load working/*.md
```

Human review happens once: final Markdown diff only.
No intermediate gates.

---

## Non-goals

- No vector DB
- No OpenAI embeddings
- No OpenClaw memory-core
- No hidden API spend
- No LLM API calls inside scripts
- No candidate promotion workflow
- No mandatory wiki build
- No cross-topic SendMessage dependency
- No full Telegram read during compile
- No automatic commit/push

---

## Inputs

### Allowed explicit inputs

| Input | Description |
|-------|-------------|
| `.agent/memory/raw/topic-<id>/chunk-*.md` | Raw archive chunks produced by `archive-context.py` |
| `.agent/AGENT_CONTEXT.md` | Project identity, startup load order, contact table |
| Existing `.agent/memory/working/*.md` | Prior working memory pack (for update mode) |
| Operator notes file | Optional free-form notes provided via `--notes` |
| Local git/gh metadata | Optional; only if available locally, never fetched silently |

### Not allowed

- Silent Telegram reads
- OpenClaw memory-core
- Vector search
- Hidden external API calls
- Raw credentials or secrets

---

## Outputs

### Required v1 working memory pack

```
.agent/memory/working/agent-brief.md
.agent/memory/working/current-state.md
.agent/memory/working/known-issues.md
```

### Optional (later phases)

```
.agent/memory/working/decisions.md
.agent/memory/working/open-questions.md
```

These files are reviewed compiled Markdown and may be committed after human review.
The compile step does not commit or push.

---

## Output file responsibilities

### `agent-brief.md`

Short startup brief for agents:

- Project identity (name, purpose, stakeholders)
- Repo path / repo URL
- Active topics and roles (from AGENT_CONTEXT.md)
- Current objective
- Do-not-do rules
- Which memory files to read and in what order
- Next useful actions for a new agent

### `current-state.md`

Current project state:

- Last updated timestamp
- Active branch / repo status if known
- Recent completed work (with source reference)
- In-progress work
- Current blockers
- Relevant PRs / commits
- Stale facts clearly marked `[stale]`

### `known-issues.md`

Known issues and risks, each entry containing:

- Issue description
- Severity (`high` / `medium` / `low`)
- Status (`open` / `resolved` / `mitigated`)
- Evidence/source (chunk path or operator note)
- Recommended next action
- Do-not-do constraints if relevant

---

## Source attribution

Every non-obvious fact in working memory must be traceable to one of:

- Source chunk file path (e.g. `raw/topic-7301/chunk-0003.md`)
- `AGENT_CONTEXT.md`
- Operator note
- Explicit local git/gh metadata

Use concise inline source notes — not verbose citations.

Example:
```markdown
- v1.2 shipped 2026-04-30 (raw/topic-7301/chunk-0005.md)
```

---

## Fact quality labels

Compiled facts may carry one of the following labels:

| Label | Meaning |
|-------|---------|
| `confirmed` | Directly stated in source; no inference |
| `inferred` | Derived from multiple sources; not explicitly stated |
| `stale` | May no longer be true; not freshly verified |
| `needs_review` | Contradiction detected between sources |

Rules:

- Do not present `inferred` facts as `confirmed`.
- Mark old branch/repo status as `stale` unless freshly verified.
- Mark contradictions as `needs_review`.
- Never include raw secrets.

---

## Sensitive data policy

The compile step must not write raw secrets into `working/*.md`.

If raw chunks contain `[REDACTED:<category>]` placeholders, the compiler may
mention that sensitive content existed at category level only.

Allowed example:
```
Topic 7301 contains credential-bearing chunks; review required before using
those chunks for detailed extraction. (bearer_token: 1, api_key: 2)
```

Forbidden:
- Reconstructing or guessing redacted values
- Printing any `[REDACTED:*]` placeholder contents
- Logging secrets to stdout/stderr

---

## Expected CLI shape

> This is a contract. Implementation is PR35.

### Dry-run (default)

```bash
python3 scripts/compile-working-memory.py \
  --target /path/to/project \
  --topics 7301:coder,13350:reviewer,15222:infra \
  --notes /path/to/operator-notes.md \
  --dry-run
```

### Write mode

```bash
python3 scripts/compile-working-memory.py \
  --target /path/to/project \
  --topics 7301:coder,13350:reviewer,15222:infra \
  --write
```

### Dry-run behaviour

- Read all inputs
- Produce draft content or patch preview
- Print warnings (redacted chunks, stale facts, contradictions)
- Print count of chunk files found per topic
- **Do not write files**

### Write mode behaviour

- Update only `.agent/memory/working/*.md`
- Do not touch `raw/`, index files, candidates, or wiki
- Do not stage or commit
- Print summary of files written and fact counts

---

## Agent-assisted extraction mode

For v1, semantic extraction is agent-assisted rather than fully deterministic.

The script may prepare:

1. A bounded context packet — the relevant raw chunk content, filtered by topic/role
2. An extraction prompt — instructions telling the agent what to extract and in what format
3. Draft file templates — empty or partially populated `working/*.md` files

Scripts must not call LLM APIs directly.
The agent (OpenClaw or Claude CLI) receives the context packet + prompt and writes the draft.
The operator reviews the diff before committing.

---

## Success criteria

- [ ] `working/*.md` can be generated or updated from raw chunks and `AGENT_CONTEXT.md`
- [ ] No vector DB or embeddings required
- [ ] No OpenClaw memory-core required
- [ ] No `read-topic` required during compile
- [ ] No raw secrets written to `working/*.md`
- [ ] Diff review is the only human review point
- [ ] Agents can answer startup questions from `working/*.md` without reading raw chunks

---

## Startup recall test

After compile, a fresh agent loading only `working/*.md` must be able to answer:

1. What is this project?
2. What is the current objective?
3. Which topic/role am I?
4. What are the current blockers?
5. What should I not do next?

Validation: no `read-topic`, no raw chunk reading, no vector search permitted during
the recall test.

---

## Relation to other contracts

| Contract | Scope |
|----------|-------|
| `docs/V1_CONTEXT_ARCHIVE_CONTRACT.md` | Ingest layer — explicit input → raw chunks |
| **This document** | Compile layer — raw chunks → working memory pack |
| `docs/MEMORY_OUTPUT_CONTRACT.md` | Archive log format (`topic-<id>.md`) — separate layer, not replaced |
| `.agent-template/AGENT_CONTEXT.md` | Startup load order — consumed by agents reading working memory |
