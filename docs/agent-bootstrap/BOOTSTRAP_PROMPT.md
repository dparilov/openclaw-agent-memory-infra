# Agent Bootstrap Prompt (Universal)

This is the universal dispatcher for agent initialization. It routes to the correct role-specific bootstrap document.

---

## 1. Parse your prompt

Your one-line prompt contains:

| Field | Values |
|-------|--------|
| **role** | `CODER` or `REVIEWER` |
| **project** | project name |
| **scope** | what to work on |

Extract all three from the prompt text.

---

## 2. Route to role bootstrap

Based on the role field:

- **CODER** -- follow [CODER_BOOTSTRAP.md](CODER_BOOTSTRAP.md) starting from step 2.
- **REVIEWER** -- follow [REVIEWER_BOOTSTRAP.md](REVIEWER_BOOTSTRAP.md) starting from step 2.

If the role is neither CODER nor REVIEWER, ask the operator which role applies.

---

## 3. Common initialization (both roles)

These steps are shared by both roles and described in detail in each role doc:

1. **Locate the project** -- resolve `$TARGET` from environment, cwd, or `$HOME/projects/`.
2. **Load context** -- read `.agent/AGENT_CONTEXT.md` and `.agent/memory/working/*.md` if available.
3. **Discover missing metadata** -- if topic IDs, chat IDs, or other metadata are needed, look in `.agent/config.yaml`, memory reports, or repo files before asking.
4. **Ask at most one blocking question** if critical metadata cannot be discovered.

The canonical bootstrap source is the **Project Memory Extractor (PME)** repo:
`https://github.com/dparilov/openclaw-agent-memory-infra`

---

## 4. READY response format

Both roles use the same structure:

```
<ROLE> READY

Project: <project>
Path: <resolved target path>
Scope: <scope>
Context loaded: <yes/no>
Active handoff: <found / not found / assigned to other role>
Next safe action: <wait for ACTIVE handoff | implement/review ACTIVE handoff | ask blocking question>
```

CODER adds: `Branch: <current branch>`
REVIEWER adds: `Review target: <PR number or branch>`

---

## 5. Post-READY discipline

**READY means initialization is complete — not permission to begin arbitrary work.**

After reporting READY:

- Read `.agent/handoffs/ACTIVE.md` if it exists and follow the [Active Handoff Protocol](../agent-collaboration/ACTIVE_HANDOFF_PROTOCOL.md).
- If no ACTIVE handoff is found, or it is assigned to a different role: **wait**.
- Work begins only from an ACTIVE handoff assigned to your role, or from an explicit human instruction.
- Do not invent implementation tasks, review targets, or next actions.
