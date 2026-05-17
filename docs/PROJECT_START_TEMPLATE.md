# Project Start — [PROJECT NAME]

<!--
OPERATOR: edit only the two sections marked EDIT below.
Everything else is handled automatically by the agent.
-->

## EDIT: Project name

[PROJECT NAME]

## EDIT: Project scope

[One paragraph describing what this project does and its current focus.]

---

<!-- The sections below are filled by the agent automatically. Do not edit. -->

## Agent instructions

You are receiving this template to start or resume work on a project using the
Project Memory Extractor v1 pipeline.

Follow `docs/MEMORY_RULES_TEMPLATE.md` exactly.

### What the agent must do

1. **Infer role** from the current agent/topic context (coder / reviewer / infra).
2. **Infer Telegram chat and topic** from the current session metadata if available.
3. **Locate the memory extractor** at `/home/dima/projects/openclaw-agent-memory-infra`.
4. **Locate the target project** under `/home/dima/projects/` using the project name above.
5. **If the project does not exist:**
   - Coder role: propose creating it (name, directory, initial scaffold) — wait for operator approval before any `git init` or `mkdir`.
   - Reviewer / infra role: report blocker — do not create the project.
   - Never create a remote GitHub repo without explicit operator approval.
6. **Ensure `.agent/AGENT_CONTEXT.md` exists.** If missing, create it from the bootstrap template in `docs/REFRESH_MEMORY_COMMANDS.md`.
7. **Run refresh-memory** if memory is missing, stale (working/*.md older than 24 h), or operator explicitly requested refresh.
8. **Autofill working memory** — do not leave `<!-- TODO -->` placeholders. Fill all sections using context from the refresh output.
9. **Update private memory** if access/infrastructure facts are present in the context.
10. **Run recover-memory.**
11. **Return the MEMORY STARTUP REPORT** (format defined in `docs/AGENT_STARTUP_AUTOFILL_PROTOCOL.md`).

### Commands

```bash
# Refresh from local context (adjust source-type as needed)
python3 /home/dima/projects/openclaw-agent-memory-infra/scripts/refresh-memory.py \
  --target /home/dima/projects/<project-dir> \
  --topic <topic-id>:<role> \
  --input /path/to/context.md \
  --source-type markdown_export \
  --write

# Or: Telegram bounded read (explicit operator request only)
python3 /home/dima/projects/openclaw-agent-memory-infra/scripts/refresh-memory.py \
  --target /home/dima/projects/<project-dir> \
  --topic <topic-id>:<role> \
  --read-topic \
  --chat-id <chat-id> \
  --limit 200 \
  --write

# Recover
python3 /home/dima/projects/openclaw-agent-memory-infra/scripts/recover-memory.py \
  --target /home/dima/projects/<project-dir> \
  --topic <topic-id> \
  --role <role>
```
