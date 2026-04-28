# Project Intake Questionnaire

Standard intake protocol for applying the OpenClaw memory system to a new project.

Complete this form before running `setup.sh`. All fields with `*` are required.

---

## 1. Project Identity

```
Project name *:
GitHub repo URL *:
Local repo path *:
Short project goal:
Canonical branch *:          (e.g. main)
```

---

## 2. Agent Roles

```
Infra topic ID *:
Coder topic ID *:
Reviewer/Architect topic ID *:
Infra runtime/model:         (e.g. openclaw/claude-sonnet-4)
Coder runtime/model:
Reviewer runtime/model:
```

---

## 3. Source of Truth

```
Canonical repo *:
Canonical branch *:
PR policy *:                 (e.g. squash-merge only, no force-push to main)
Who may merge *:             (human only / reviewer + human / any with CI green)
Are direct commits allowed:  yes / no / yes with restrictions: <describe>
Where are task specs stored: (e.g. .agent/tasks/)
Where are review docs stored: (e.g. .agent/reviews/)
Where are handoffs stored: (e.g. .agent/handoffs/)
```

---

## 4. Memory Policy

```
Session history source:      OpenClaw session_history only / Pyrogram live reads too
Topics to archive first:     (comma-separated topic IDs, in priority order)
Auto-promotable fact types:  (e.g. fact, preference, project_state, resolved_issue)
Always requires human approval: (e.g. architecture_decision, constraint, process_rule)
Conflict handling:           (e.g. flag with CONFLICT marker, escalate to human)
```

---

## 5. Cross-Agent Communication

```
May reviewer post task notifications directly to coder topic?    yes / no
May coder post PR-ready notifications directly to reviewer topic? yes / no
May infra post setup/preflight reports to project topics?        yes / no
Required notification format:  (free-form summary / repo+file links only / template below)
Should notifications include summaries or only repo/file links?
```

**Standard notification format** (default if not overridden):

```
Task ready:
- Task: <path>
- Branch: <branch>
- Acceptance: <one-line summary>
- Non-goals: <one-line summary>
- On completion: open PR and write handoff
```

---

## 6. Human Escalation

```
Human Telegram handle *:     (e.g. @pariloff)
```

**Escalation triggers** — the following always require explicit human decision:

```
[ ] High-risk architecture decision
[ ] Merge approval
[ ] Production / deployment / security change
[ ] Unresolved reviewer/coder disagreement
[ ] Failed validator or pre-live check with no clear fix
[ ] Memory conflict requiring canonical resolution
[ ] Sensitive data / access material encountered
[ ] Any item outside agent authority as defined in AGENT_CONTEXT.md
```

**Required escalation format:**

```
@<handle> ESCALATION REQUIRED
Reason:           <what triggered escalation>
Decision needed:  <what the human must decide>
Options:          <option A / option B / ...>
Recommended:      <agent recommendation, or "no recommendation">
Links:            <PR / task / file URLs>
Urgency:          low / medium / high / blocking
```

---

## Completion Checklist

Before running `setup.sh`:

- [ ] All `*` fields filled
- [ ] Canonical branch confirmed in repo
- [ ] Agent topic IDs verified against live OpenClaw topics
- [ ] Human handle confirmed reachable
- [ ] Memory policy reviewed and agreed
- [ ] Escalation triggers acknowledged

After setup:

- [ ] `bash setup.sh --target <project-path> --install-scripts copy --test` passes
- [ ] `.agent/config.yaml` reflects intake values
- [ ] Discovery draft reviewed (see `docs/PROJECT_DISCOVERY_FROM_TOPICS.md`)
