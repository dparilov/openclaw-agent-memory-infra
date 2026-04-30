# External Operator → Infra Agent Handoff

> **This is the fallback and escalation path.**
> The primary setup path is the **[Setup Wizard](SETUP_WIZARD_FLOW.md)**.
> Use this doc when: (a) the wizard cannot complete setup, (b) you need to
> escalate from the wizard, or (c) you are handling post-setup memory operations.

### When to escalate from the wizard

```
/handoff
TRIGGER: wizard-escalation
WIZARD STATE: Phase <N> — <reason why wizard cannot proceed>
<paste wizard status block>
```

The infra agent will resume from the wizard state and complete setup.

---

## Why This Boundary Exists

External operators (humans or non-infra agents) interact with OpenClaw through  
Telegram or API. The infra agent owns the memory infrastructure: topic routing,  
candidate promotion, wiki maintenance, and environment health.

Crossing this boundary without a structured handoff leads to:
- Missing prerequisites that block memory operations
- Duplicate or conflicting topic assignments
- Candidates promoted without human review

---

## When to Use This Handoff

Trigger a formal handoff when:

1. **New environment** — first-time setup on a new VPS or workstation
2. **New project** — adding a product repo that needs `.agent/` scaffold
3. **Memory recovery** — recovering from a lost or corrupted memory state
4. **Role change** — adding or removing agent roles for a topic
5. **Post-incident** — after any unplanned interruption during a memory operation

---

## Handoff Prompt Template

Copy and paste this into Telegram (or your infra agent channel):

```
/handoff

OPERATOR: <your name or handle>
DATE: <YYYY-MM-DD>
HOST: <hostname or VPS label>
TRIGGER: <new-environment | new-project | memory-recovery | role-change | post-incident>

READY-FOR-HANDOFF REPORT:
<paste from docs/FULL_ENVIRONMENT_ONBOARDING.md §K>

ADDITIONAL CONTEXT:
<anything the infra agent should know that isn't in the report>
```

---

## Expected Output Sequence

The infra agent will respond in this order:

1. **ORIENTATION REPORT** — confirms it received your handoff, summarises what it sees
2. **LEVEL 0 / LEVEL 1 PREREQUISITES REPORT** — lists any missing gates and how to fix them
3. **TOPIC RESOLUTION REPORT** — maps your planned topics to existing memory state
4. **PROJECT INTAKE DRAFT** — proposes `.agent/` scaffold changes (if new project)
5. **SETUP REPORT** — summarises actions taken
6. **POST-SETUP VERIFICATION REPORT** — confirms memory operations are healthy

If the infra agent skips a step or the sequence is out of order, ask it to produce  
the missing report before proceeding.

---

## What the Infra Agent Will NOT Do Without Approval

- Promote memory candidates (requires human `approve` command)
- Commit or push to product repos (requires human review of PRE-COMMIT REPORT)
- Run manual migration (M0–M5) without explicit operator sign-off at each milestone
- Modify topic assignments outside the current scope
