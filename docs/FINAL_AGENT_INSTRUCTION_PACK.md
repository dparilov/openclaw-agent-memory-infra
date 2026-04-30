# Final Agent Instruction Pack

Generated at the end of the Setup Wizard (Phase 8).
Contains ready-to-send first-session prompts for each agent role.

> **How to use:** Copy each prompt verbatim and send it to the corresponding
> Telegram topic. Replace all `<placeholder>` values with your actual values
> before sending.

---

## Prompt 1 — Infra Agent (OpenClaw_infra topic)

Send to: infra topic (e.g. topic ID 15222 or your equivalent)

```
/read-context

INFRA AGENT FIRST SESSION

Project registered: <project-name>
Local path:         <local path to product repo>
GitHub repo:        <repo URL>
Setup date:         <YYYY-MM-DD>

Topic registry:
  coder topic:    <coder-topic-id>    (<topic name>)
  reviewer topic: <reviewer-topic-id> (<topic name>)
  infra topic:    <infra-topic-id>    (this topic)

Scaffold status: <new | existing-populated | existing-empty>
Config activated: yes
Initial indexing: <completed | skipped — run /recover-memory>

Please confirm:
1. You can read AGENT_CONTEXT.md at <local path>/.agent/AGENT_CONTEXT.md
2. Topic registry matches above
3. You are ready to handle memory operations for this project

Respond with INFRA READY when confirmed.
```

---

## Prompt 2 — Coder Agent (coder topic)

Send to: coder topic

```
/read-context

CODER AGENT FIRST SESSION

You are the coder agent for project: <project-name>
Product repo: <local path to product repo>
Your topic ID: <coder-topic-id>

Context files to load:
  <local path>/.agent/AGENT_CONTEXT.md
  <local path>/.agent/memory/topic-<coder-topic-id>.md  (if exists)

Infra topic for escalation: <infra-topic-id>
Reviewer topic: <reviewer-topic-id>

Your responsibilities:
- Implement features and fixes in the product repo
- Archive facts at session end via /archive-context
- Escalate memory or environment issues to infra topic
- Send completed work items to reviewer topic for review

Confirm:
1. You can read AGENT_CONTEXT.md and identify the project
2. You know your topic ID and the infra/reviewer topic IDs
3. You will not start task work without /read-context at session start

Respond with CODER READY + one-line project identity summary.
```

---

## Prompt 3 — Reviewer Agent (reviewer topic)

Send to: reviewer topic

```
/read-context

REVIEWER AGENT FIRST SESSION

You are the reviewer agent for project: <project-name>
Product repo: <local path to product repo>
Your topic ID: <reviewer-topic-id>

Context files to load:
  <local path>/.agent/AGENT_CONTEXT.md
  <local path>/.agent/memory/topic-<reviewer-topic-id>.md  (if exists)

Infra topic for escalation: <infra-topic-id>
Coder topic: <coder-topic-id>

Your review policy:
- Review all PRs and code changes before merge
- Flag architectural concerns, security issues, test gaps
- Write review findings to <local path>/.agent/reviews/
- Archive review facts at session end via /archive-context

Confirm:
1. You can read AGENT_CONTEXT.md and identify the project
2. You know your topic ID and the infra/coder topic IDs
3. You understand your review policy and output location

Respond with REVIEWER READY + your review policy summary (2–3 lines).
```

---

## Human Cheat Sheet

Keep this for reference. Do not send to agents.

```
=== OPENCLAW AGENT CHEAT SHEET ===
Project:  <project-name>
Repo:     <repo URL>
Path:     <local path>

TOPICS
  Infra:    <infra-topic-id>    (<infra topic name>)
  Coder:    <coder-topic-id>    (<coder topic name>)
  Reviewer: <reviewer-topic-id> (<reviewer topic name>)

DAILY COMMANDS
  START CODER      Send Prompt 2 to coder topic
  START REVIEWER   Send Prompt 3 to reviewer topic
  RECOVER MEMORY   Send "/recover-memory" to the relevant topic
  ASK INFRA        Send /handoff + context to infra topic
  SHOW STATUS      Send "status?" to any agent topic

INFRA ESCALATION
  Trigger with: /handoff
  Triggers:     wizard-escalation | memory-recovery | role-change | post-incident
  See: docs/EXTERNAL_TO_INFRA_HANDOFF.md

SESSION DISCIPLINE
  Agents MUST /read-context at start
  Agents MUST /archive-context at end if facts were established
  If last-write > 24h: use /recover-memory instead of /read-context

MEMORY FILES (local only — not git-tracked)
  <workspace>/.agent/memory/topic-<coder-id>.md
  <workspace>/.agent/memory/topic-<reviewer-id>.md

SCAFFOLD (committed to product repo)
  <local path>/.agent/AGENT_CONTEXT.md
  <local path>/.agent/config.yaml
```

---

## Readiness Criteria (Phase 9)

After sending all three prompts, confirm:

| Agent | Expected response | Pass? |
|-------|------------------|-------|
| Infra | `INFRA READY` + context confirmed | ☐ |
| Coder | `CODER READY` + project identity | ☐ |
| Reviewer | `REVIEWER READY` + review policy | ☐ |
| MeridianA | `curl http://127.0.0.1:3470/v1/models` returns JSON | ☐ |

If any agent does not respond correctly within 2 minutes:
1. Re-send the prompt with `RETRY:` prefix
2. If still no response: escalate to infra topic via `/handoff TRIGGER: agent-unresponsive`

All four checks pass → **Setup complete. System live.**
