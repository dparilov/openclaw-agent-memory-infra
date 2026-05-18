# openclaw-agent-memory-infra

**Shared memory infrastructure for OpenClaw agents.** The current active path
is the **Project Memory Extractor v1** — a simple, stdlib-only pipeline with no
vector DB, no LLM API calls in scripts, and no auto-commit.

---

## New users — start here

1. [docs/INSTALL.md](docs/INSTALL.md) — installation walkthrough
2. [docs/V1_QUICKSTART.md](docs/V1_QUICKSTART.md) — four-step daily workflow
3. [docs/PROJECT_START_TEMPLATE.md](docs/PROJECT_START_TEMPLATE.md) — send to agent to start a project
4. [docs/MEMORY_RULES_TEMPLATE.md](docs/MEMORY_RULES_TEMPLATE.md) — universal agent rules

---

## Install

```bash
git clone <PME_GIT_URL> "$HOME/projects/openclaw-agent-memory-infra"
export PME_REPO="$HOME/projects/openclaw-agent-memory-infra"
export PROJECTS_ROOT="$HOME/projects"
```

Add the two `export` lines to `~/.bashrc` or `~/.zshrc`.  No pip installs
required for local mode.  See [docs/INSTALL.md](docs/INSTALL.md) for full
prerequisites and Telegram setup.

---

## v1 — Project Memory Extractor (current active path)

Two commands cover the full daily cycle:

```bash
# Refresh from Telegram bounded read
python3 "$PME_REPO/scripts/refresh-memory.py" \
  --target "$PROJECTS_ROOT/<project-dir>" \
  --topic "<TOPIC_ID>:<ROLE>" \
  --read-topic \
  --chat-id "<CHAT_ID>" \
  --limit 200 \
  --write

# Agent startup recovery
python3 "$PME_REPO/scripts/recover-memory.py" \
  --target "$PROJECTS_ROOT/<project-dir>" \
  --topic "<TOPIC_ID>" \
  --role "<ROLE>"
```

`<ROLE>` is one of: `coder`, `reviewer`, `infra`.

**Full command reference:** [docs/REFRESH_MEMORY_COMMANDS.md](docs/REFRESH_MEMORY_COMMANDS.md)

---

## v1 docs

| Doc | Purpose |
|---|---|
| [docs/INSTALL.md](docs/INSTALL.md) | Installation walkthrough |
| [docs/V1_QUICKSTART.md](docs/V1_QUICKSTART.md) | Four-step daily workflow |
| [docs/PORTABILITY.md](docs/PORTABILITY.md) | Env vars, discovery order, private repo setup |
| [docs/AGENT_STARTUP_AUTOFILL_PROTOCOL.md](docs/AGENT_STARTUP_AUTOFILL_PROTOCOL.md) | Startup sequence + MEMORY STARTUP REPORT |
| [docs/PROJECT_START_TEMPLATE.md](docs/PROJECT_START_TEMPLATE.md) | Operator template for new projects |
| [docs/MEMORY_RULES_TEMPLATE.md](docs/MEMORY_RULES_TEMPLATE.md) | Universal agent rules (no per-project edits required) |
| [docs/REFRESH_MEMORY_COMMANDS.md](docs/REFRESH_MEMORY_COMMANDS.md) | Full command reference |

---

## Operator model

The operator sends two files to the agent:

1. `docs/PROJECT_START_TEMPLATE.md` — edit only: **Project name**, **Project scope**
2. `docs/MEMORY_RULES_TEMPLATE.md` — no edits required

No required edits for: chat ID, topic ID, role, path, repo URL, GitHub owner.
The agent infers or discovers those from session metadata, or reports a blocker
if unavailable.

---

## Dependencies

| Dependency | Required for |
|---|---|
| `git` | cloning the PME repo |
| Python 3.10+ | all scripts (stdlib only for local mode) |
| GitHub access (SSH or HTTPS token) | cloning the private PME repo |
| Pyrogram userbot session | `--read-topic` Telegram mode only |

**Not required:**
- OpenAI or any other LLM API — scripts are stdlib-only pipelines; the agent IS the LLM
- Vector DB / embeddings
- OpenClaw `memory-core` or any framework dependency
- wiki build, candidate promotion
- LLM API calls from scripts

---

## Validated v1 flow

```
operator sends PROJECT_START_TEMPLATE.md + MEMORY_RULES_TEMPLATE.md
→ agent infers topic / chat ID / role from session metadata
→ refresh-memory --read-topic --limit 200 --write
→ existing raw chunks replaced automatically (no manual cleanup needed)
→ agent autofills working memory
→ recover-memory
→ MEMORY STARTUP REPORT returned
```

---

## Development

```bash
python3 -m pytest tests/ -v
```

---

## Legacy / historical docs

The documents below predate the simplified v1 path and are retained for
historical reference only. **They are not the active v1 path.**

The active v1 path is:
two operator templates → `refresh-memory` → agent autofill → `recover-memory`.

| Doc | Notes |
|---|---|
| `docs/ROADMAP.md` | Implementation phases 1–5 (pre-v1) |
| `docs/SETUP_WIZARD_FLOW.md` | Wizard-based setup (replaced by two-template operator model) |
| `docs/FULL_ENVIRONMENT_ONBOARDING.md` | Old environment gate reference (A–K) |
| `docs/FINAL_AGENT_INSTRUCTION_PACK.md` | Pre-v1 agent prompt packs |
| `docs/COLD_TEST_FINDINGS_2026-05-04.md` | Cold run findings from earlier phase |
| `docs/MEMORY_EXTRACTION_POLICY.md` | L1/L2 extraction policy (heavy path) |
| `docs/CANDIDATE_SCHEMA.md` | L1 candidate lifecycle schema |
| `docs/MEMORY_OUTPUT_CONTRACT.md` | Output format spec (heavy path) |
| `docs/PYROGRAM_FLOOD_WAIT.md` | FloodWait handling (direct read-topic usage) |
| `docs/SKILL_VOCABULARY.md` | Skill decision guide (heavy path) |
| `docs/FALLBACK_ORDER.md` | Context access fallback chain (heavy path) |
| `docs/ARCHIVE_CONTEXT_CLI.md` | Direct CLI reference for archive-context.py |
| `docs/COMPILE_WORKING_MEMORY_CLI.md` | Direct CLI reference for compile-working-memory.py |

---

## License

MIT
