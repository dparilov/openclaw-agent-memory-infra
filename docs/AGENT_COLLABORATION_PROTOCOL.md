# Agent Collaboration Protocol

Canonical flow for reviewer / coder / infra collaboration on the OpenClaw memory system.

---

## 1. Roles

| Role | Responsibilities |
|------|-----------------|
| **Infra agent** | Setup, preflight checks, migration support, tooling health, wiki validation |
| **Reviewer / Architect agent** | Requirements, task specs, architecture decisions, PR reviews, authority recommendations |
| **Coder agent** | Implementation, tests, PRs, handoffs |
| **Human** | Product priority, authority gate, merge approval, high-risk decisions |

Authority hierarchy: Human > Reviewer > Coder > Infra (for escalation routing).

---

## 2. Reviewer → Coder Flow

### Step 1: Reviewer creates task spec

```
.agent/tasks/<YYYY-MM-DD>-<slug>.md
```

Required task spec fields:

```markdown
# Task: <title>

## Branch
<branch-name>

## Acceptance criteria
<numbered list>

## Non-goals
<list>

## References
<PR links, docs, ADR links>

## On completion
Open PR against <canonical-branch> and write handoff to .agent/handoffs/.
```

### Step 2: Reviewer notifies coder topic

Notification template:

```
Task ready:
- Task: .agent/tasks/<filename>
- Branch: <branch>
- Acceptance: <one-line summary>
- Non-goals: <one-line summary>
- On completion: open PR and write handoff to .agent/handoffs/
```

**The coder reads the task from the repo file, not from the chat summary.**

---

## 3. Coder → Reviewer Flow

### Step 1: Coder opens PR

- PR against canonical branch (e.g., `main`).
- PR title follows project commit convention.
- PR description includes: summary, test plan, definition of done.

### Step 2: Coder writes handoff

```
.agent/handoffs/<YYYY-MM-DD>-<slug>-handoff.md
```

Required handoff fields:

```markdown
# Handoff: <title>

## PR
<URL>

## Branch
<branch>

## Task
.agent/tasks/<filename>

## What was done
<summary>

## Tests
<test summary — counts, files, key cases>

## Known limitations / deferred
<list or "none">

## Memory update needed
<yes/no — if yes, list facts to archive after merge>
```

### Step 3: Coder notifies reviewer topic

Notification template:

```
Implementation ready:
- PR: <URL or #number>
- Branch: <branch>
- Task: .agent/tasks/<filename>
- Handoff: .agent/handoffs/<filename>
- Tests: <one-line summary>
Please review.
```

---

## 4. Reviewer Decision Flow

The reviewer reads the PR, handoff, and task spec from the repo — not from chat summaries.

### Verdicts

| Verdict | Meaning | Action |
|---------|---------|--------|
| `approved` | Ready to merge | Notify coder; human merges if required by policy |
| `changes-requested` | Specific fixes needed | List changes in review; notify coder |
| `blocked` | Cannot proceed without external input | State blocker; escalate to human if needed |
| `needs-human-approval` | Decision outside reviewer authority | Escalate to human using ESCALATION template |

### Changes-requested format

```
Review verdict: changes-requested

Required changes:
1. <specific change with file/line reference>
2. <...>

Non-blocking notes:
- <observation that does not block merge>

Re-review: required / not required after changes
```

---

## 5. Human Escalation

Escalation triggers (any agent may escalate):

```
High-risk architecture decision
Merge approval (when policy requires human gate)
Production / deployment / security change
Unresolved reviewer/coder disagreement
Failed validator or pre-live check with no clear fix
Memory conflict requiring canonical resolution
Sensitive data / access material encountered
Any item outside agent authority as defined in AGENT_CONTEXT.md
```

Required escalation format:

```
@<handle> ESCALATION REQUIRED
Reason:           <what triggered escalation>
Decision needed:  <what the human must decide>
Options:          <option A / option B / ...>
Recommended:      <agent recommendation, or "no recommendation">
Links:            <PR / task / handoff / file URLs>
Urgency:          low / medium / high / blocking
```

---

## 6. After Merge

After a PR is merged, the responsible agent must:

```
1. Archive session facts if new durable facts were established:
   python .agent/tools/context_access/archive-batch-v2.py <topic> --write <facts> ...

2. Rebuild wiki:
   python .agent/tools/context_access/build-wiki.py --memory-dir .agent/memory

3. Validate wiki:
   python .agent/tools/context_access/validate-wiki.py --memory-dir .agent/memory

4. Update or close the task:
   - Mark task status in .agent/tasks/<filename>: completed / closed
   - If applicable, update .agent/AGENT_CONTEXT.md current-state section

5. Notify human if any post-merge actions require attention.
```

If the validator reports errors after merge, escalate to human immediately.

---

## 7. Cross-Topic Communication Rules

| Rule | Rationale |
|------|-----------|
| Agents read task and handoff from repo, not from chat | Repo is single source of truth |
| Notifications contain repo paths, not content summaries | Avoids drift between chat and repo |
| Infra does not make architecture decisions | Authority boundary |
| Coder does not merge without reviewer verdict or human gate | Prevents unauthorized merges |
| Reviewer does not write implementation code | Separation of concerns |
| All escalations go to human via defined template | Consistent escalation path |
| Sensitive data is never copied into notifications, memory, or wiki | Security boundary |
