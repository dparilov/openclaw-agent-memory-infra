# PME v1 Portability Guide

Project Memory Extractor v1 is designed to run on any Unix system without
modification.  Two environment variables control all path resolution; no file
in the repo contains hardcoded user or machine paths.

---

## Environment variables

| Variable | Default | Purpose |
|---|---|---|
| `PME_REPO` | `$HOME/projects/openclaw-agent-memory-infra` | Absolute path to the cloned PME repository |
| `PROJECTS_ROOT` | `$HOME/projects` | Parent directory that contains all agent-managed project directories |

Set them in `~/.bashrc`, `~/.zshrc`, or any shell profile:

```bash
export PME_REPO="$HOME/projects/openclaw-agent-memory-infra"
export PROJECTS_ROOT="$HOME/projects"
```

Scripts read these variables at runtime.  You never need to edit a script to
move the repo or change the projects root.

---

## PME repo discovery order

When a script or template references `$PME_REPO` the resolution order is:

1. `$PME_REPO` environment variable (explicit, always wins)
2. `$HOME/projects/openclaw-agent-memory-infra` (default fallback)

`$PROJECTS_ROOT` follows the same pattern:

1. `$PROJECTS_ROOT` environment variable
2. `$HOME/projects` (default fallback)

---

## What is portable

- All five scripts (`archive-context.py`, `compile-working-memory.py`,
  `refresh-memory.py`, `recover-memory.py`, `bootstrap-memory.py`) — stdlib
  only, no pip installs required for local mode.
- All operator templates (`PROJECT_START_TEMPLATE.md`,
  `MEMORY_RULES_TEMPLATE.md`) — reference only `$PME_REPO` and
  `$PROJECTS_ROOT`.
- `AGENT_STARTUP_AUTOFILL_PROTOCOL.md` — all paths expressed as env vars.
- `INSTALL.md`, `V1_QUICKSTART.md` — use `<PME_GIT_URL>` placeholder and env
  vars throughout.

---

## Intentionally not included

PME v1 deliberately excludes:

| Excluded | Reason |
|---|---|
| OpenAI / any LLM API calls | Scripts are stdlib-only pipelines; the agent IS the LLM |
| Vector DB | No embeddings layer; working memory is plain Markdown |
| `memory-core` or any framework dependency | Zero runtime deps for local mode |
| Hardcoded Telegram chat IDs | `--chat-id` is always an explicit operator argument |
| Hardcoded GitHub owner | `<PME_GIT_URL>` placeholder; operator fills in at install time |
| Hardcoded project root | `$PROJECTS_ROOT` with `$HOME/projects` default |
| Hardcoded user home paths | All paths derive from `$PME_REPO` / `$PROJECTS_ROOT` / `$HOME` |
| Billing or quota management | No external service calls from scripts |

---

## What is NOT portable (requires operator action)

| Item | What to change |
|---|---|
| `<PME_GIT_URL>` placeholder in `INSTALL.md` | Replace with the actual private GitHub repo URL once the repo is shared |
| Pyrogram `api_id` / `api_hash` in `~/.agent/memory/private/credentials.md` | Per-machine Telegram credentials; never committed |
| Project-specific `MEMORY.md` content | Filled by the agent at startup per project |
| `.agent/memory/private/` directory contents | Machine-local, gitignored, never shared |

---

## Private GitHub repo setup

PME v1 is designed to be hosted in a **private** GitHub repository.

1. Create a private repo on GitHub.
2. Push this repo: `git remote set-url origin <your-private-url> && git push`.
3. Replace `<PME_GIT_URL>` in `docs/INSTALL.md` with the private URL.
4. Share access with collaborators via GitHub team permissions — scripts and
   templates contain no secrets.
5. Each operator clones the repo and sets `PME_REPO` / `PROJECTS_ROOT` in
   their shell profile.

Private memory (`~/.agent/memory/private/`) is **never** committed and is
listed in `.gitignore`.  Credentials stay on the local machine only.

---

## Telegram dependency

Telegram ingestion (`--read-topic`) requires **Pyrogram**:

```bash
pip install pyrogram tgcrypto
```

Local mode (file-based input only) runs with zero pip installs — stdlib Python
3.9+ is sufficient.

---

## Verification

After cloning and setting env vars, verify portability:

```bash
python3 "$PME_REPO/scripts/refresh-memory.py" --help
python3 "$PME_REPO/scripts/recover-memory.py" --help
echo "PME_REPO=$PME_REPO"
echo "PROJECTS_ROOT=$PROJECTS_ROOT"
```

All paths in `--help` output should resolve under your configured roots.

---

## See also

- [INSTALL.md](INSTALL.md) — full installation walkthrough
- [V1_QUICKSTART.md](V1_QUICKSTART.md) — two-command daily workflow
- [AGENT_STARTUP_AUTOFILL_PROTOCOL.md](AGENT_STARTUP_AUTOFILL_PROTOCOL.md) — startup sequence
