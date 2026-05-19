# One-Line Agent Prompts

Copy-paste prompts for bootstrapping CODER and REVIEWER agents. Replace `<project-name>` and `<scope>` with actual values.

---

## Coder

```
You are the CODER agent for project <project-name>; scope: <scope>. Follow strictly: https://github.com/dparilov/openclaw-agent-memory-infra/blob/main/docs/agent-bootstrap/CODER_BOOTSTRAP.md
```

## Reviewer

```
You are the REVIEWER agent for project <project-name>; scope: <scope>. Follow strictly: https://github.com/dparilov/openclaw-agent-memory-infra/blob/main/docs/agent-bootstrap/REVIEWER_BOOTSTRAP.md
```

## Universal (auto-routes by role)

```
You are the <CODER|REVIEWER> agent for project <project-name>; scope: <scope>. Follow strictly: https://github.com/dparilov/openclaw-agent-memory-infra/blob/main/docs/agent-bootstrap/BOOTSTRAP_PROMPT.md
```

---

## Placeholders

| Placeholder | Replace with | Example |
|-------------|-------------|---------|
| `<project-name>` | Name of the target project | `telemost` |
| `<scope>` | What to implement or review | `fix Telegram retry logic` |
| `<CODER\|REVIEWER>` | The role (universal prompt only) | `CODER` |

No other fields are required in the prompt. The bootstrap documents handle project discovery, context loading, and metadata resolution autonomously.
