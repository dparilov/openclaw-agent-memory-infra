# Human Command Cheat Sheet

Printable operator reference for the OpenClaw agent memory system.

---

## Operator Principle

```
Human gives short canonical commands.
Agent resolves project / repo / topic / role / context where possible.
Agent asks narrow follow-up questions only when needed.
Read-only is the default for READ / VALIDATE / AUDIT commands.
Writes require commands that explicitly imply write, or explicit human approval.
Merge, high-risk promotion, and human authority are NEVER implicit.
```

---

## Command Dictionary

### READ CONTEXT
```
Purpose:       Load full agent context at session start (L2–L4).
Safe default:  Read-only.
Agent infers:  Active project, topic ID from config or chat context.
May ask:       Which topic if ambiguous.
Output:        Memory summary, current state, recent decisions.
```

### RECOVER MEMORY
```
Purpose:       Full context restore after >24h gap or stale session.
Safe default:  Read-only.
Agent infers:  Topic, last-write timestamp, staleness.
May ask:       Confirm recovery scope if multiple topics.
Output:        Full L2–L4 context reload + staleness report.
```
> Target behavior: rebuilds/updates baseline index when indexing support is available; otherwise the agent must report that indexing is not implemented and use read-only recovery.

### READ L0
```
Purpose:       Show raw session archive for a topic.
Safe default:  Read-only.
Agent infers:  Topic ID, batch range from project config.
May ask:       Which batch range if not specified.
Output:        Raw archived batches from .agent/memory/raw/.
```

### READ L1
```
Purpose:       Show candidate queue status.
Safe default:  Read-only.
Agent infers:  Topic ID.
May ask:       Which topic or all topics.
Output:        Candidate list with status, risk, type.
```

### READ L2
```
Purpose:       Show canonical working memory for a topic.
Safe default:  Read-only.
Agent infers:  Topic ID.
May ask:       Which topic if ambiguous.
Output:        Contents of .agent/memory/topic-<id>.md.
```

### READ L3
```
Purpose:       Show knowledge wiki for a topic or all topics.
Safe default:  Read-only.
Agent infers:  Topic ID from context.
May ask:       Which topic or all topics.
Output:        Rendered wiki pages from .agent/memory/wiki/.
```

### READ L4
```
Purpose:       Show canonical docs and runbooks.
Safe default:  Read-only.
Agent infers:  Relevant doc based on task context.
May ask:       Which document if ambiguous.
Output:        AGENT_CONTEXT.md, runbooks, ADRs, deployment guide.
```

### VALIDATE L3
```
Purpose:       Run pre-live integrity check on wiki.
Safe default:  Read-only.
Agent infers:  memory-dir from project config.
May ask:       --strict flag if not clear.
Output:        validate-wiki.py report (errors/warnings/pass).
```

### ARCHIVE CONTEXT
```
Purpose:       Persist new facts from session to L2 memory.
Safe default:  Write (explicit command implies write).
Agent infers:  Topic, session ID, memory dir.
May ask:       Confirm batch content before write if uncertain.
Output:        Updated topic-<id>.md, batch appended.
```
> Not for bulk historical archiving. Use for incremental context snapshots only.

### CREATE CANDIDATES
```
Purpose:       Extract fact candidates from session/batch to L1.
Safe default:  Write (explicit command implies write).
Agent infers:  Source batch, topic, memory dir.
May ask:       Which batch or session if not specified.
Output:        YAML candidates written to .agent/memory/candidates/.
```
> Explicit candidate workflow — not the default path for new topics. Default is automatic initial indexing.

### PROMOTE AUTO
```
Purpose:       Auto-promote low-risk candidates to L2.
Safe default:  Write (explicit command implies write).
Agent infers:  Topic from context.
May ask:       Which topic or all topics.
Output:        Promotion report; pending-approval items listed.
```
> Same caveat as CREATE CANDIDATES — use only when explicit promotion is warranted.

### APPROVE CANDIDATE
```
Purpose:       Manually approve a specific high-risk candidate.
Safe default:  Write (human approval is the command itself).
Agent infers:  Topic, candidate ID if provided or recent.
May ask:       Candidate ID if not specified.
Output:        Candidate promoted to L2; status updated to approved.
```

### BUILD WIKI
```
Purpose:       Rebuild L3 Knowledge Vault from all L2 files.
Safe default:  Write (explicit command implies write).
Agent infers:  memory-dir from project config.
May ask:       --clean flag if rebuild from scratch needed.
Output:        Updated .agent/memory/wiki/.
```

### AUDIT WIKI
```
Purpose:       Run full wiki audit with report.
Safe default:  Read-only (report write optional).
Agent infers:  memory-dir, output path.
May ask:       Whether to write report file.
Output:        validate-wiki.py --write-report output.
```

### CREATE TASK
```
Purpose:       Write a task spec for coder agent.
Safe default:  Write (explicit command implies write).
Agent infers:  Repo, branch convention, task format.
May ask:       Task title, acceptance criteria, non-goals.
Output:        .agent/tasks/<task>.md created.
```

### TAKE TASK
```
Purpose:       Coder agent accepts and starts a task.
Safe default:  Read (task read); write begins only on implementation.
Agent infers:  Task path from pointer.
May ask:       Which task if multiple open.
Output:        Task context loaded; implementation plan stated.
```

### REVIEW PR
```
Purpose:       Reviewer agent reviews a pull request.
Safe default:  Read-only.
Agent infers:  PR number, repo from context or task handoff.
May ask:       Whether to proceed without handoff if missing.
Output:        Review verdict: approved / changes-requested / blocked / needs-human-approval.
```

### FIX REVIEW
```
Purpose:       Coder addresses reviewer feedback.
Safe default:  Write (implementation implied).
Agent infers:  PR, review comments, branch.
May ask:       Clarification on specific review point if ambiguous.
Output:        Commits pushed; PR updated; reviewer notified.
```

### MERGE READY CHECK
```
Purpose:       Verify PR is ready to merge (tests, smoke, review status).
Safe default:  Read-only.
Agent infers:  PR number, CI status, review verdict.
May ask:       None (fully resolvable from repo state).
Output:        Pass/fail checklist; merge recommendation.
```

### NOTIFY CODER
```
Purpose:       Send task-ready notification to coder topic.
Safe default:  Write (message send).
Agent infers:  Coder topic ID from project config.
May ask:       Task path if not specified.
Output:        Notification posted to coder topic.
```

### NOTIFY REVIEWER
```
Purpose:       Send PR-ready notification to reviewer topic.
Safe default:  Write (message send).
Agent infers:  Reviewer topic ID from project config.
May ask:       PR URL if not specified.
Output:        Notification posted to reviewer topic.
```

### ESCALATE TO HUMAN
```
Purpose:       Flag a decision or blocker for human authority.
Safe default:  Write (escalation message).
Agent infers:  Human handle from project config.
May ask:       Urgency level if not clear.
Output:        Escalation message sent using the required template.
```

### PRE-LIVE CHECK
```
Purpose:       Full pre-live integrity run before business review.
Safe default:  Read-only (runs tests + smoke + validator).
Agent infers:  Project paths, memory-dir.
May ask:       None (all paths from config).
Output:        pytest + smoke + validate-wiki results; GO / STOP verdict.
```
> Verifies baseline index exists. If absent, run RECOVER MEMORY first.

---

## Missing Parameter Behavior

| Command | Missing param | Agent behavior |
|---------|---------------|----------------|
| `READ L3` | no topic | Ask: "Which topic or all topics?" |
| `REVIEW PR #18` | no handoff | Search `.agent/handoffs/`; if missing, ask whether to continue without handoff |
| `PROMOTE AUTO` | no topic | Ask: "Which topic or all topics?" |
| `APPROVE CANDIDATE` | no candidate ID | Show pending approval list; ask which to approve |
| `NOTIFY CODER` | no task path | Ask: "Which task spec to reference?" |
| `ESCALATE TO HUMAN` | no handle | Use handle from `.agent/config.yaml`; if missing, ask |

---

## Human Escalation Format

Use this template when sending an escalation:

```
@<handle> ESCALATION REQUIRED
Reason:           <what triggered escalation>
Decision needed:  <what the human must decide>
Options:          <option A / option B / ...>
Recommended:      <agent recommendation>
Links:            <PR / task / file URLs>
Urgency:          low / medium / high / blocking
```

See `docs/PROJECT_INTAKE_QUESTIONNAIRE.md` for escalation trigger list.
