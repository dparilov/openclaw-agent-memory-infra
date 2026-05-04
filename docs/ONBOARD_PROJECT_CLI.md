# Onboard Project CLI

`scripts/onboard-project.py` — deterministic fast project onboarding CLI for
openclaw-agent-memory-infra.

## Why This Exists

The manual Phase 0 / Path B → Phase 2/3 onboarding flow requires copying long
prompt blocks between an external assistant and the infra agent. This is slow,
error-prone, and not product-grade.

This CLI replaces the repetitive steps with a single command that:

1. Runs read-only preflight checks (env, auth, target repo)
2. Detects the `.agent/` scaffold
3. Computes a tool sync diff (source: `scripts/context_access/`, dest: `.agent/tools/context_access/`)
4. Optionally copies changed/missing tool files (`--sync-tools`)
5. Optionally creates a PR for the sync (`--create-pr`)
6. Runs an initial-index dry-run for all three topics

The human is only asked to intervene at real decision points: approve/merge the
PR, confirm OAuth, choose A/B/C.

## Example: Fast Onboarding

```bash
python3 scripts/onboard-project.py \
  --target /home/dima/projects/telemost/olcRTC \
  --mode fast \
  --repo https://github.com/dparilov/olcRTC \
  --chat-id -1003596522926 \
  --infra-topic 15222 \
  --coder-topic 7301 \
  --reviewer-topic 13350 \
  --escalation @pariloff
```

This runs in **dry-run mode** by default — no files are copied, no commits are
made. The report shows what *would* happen.

## Dry-Run Default

All file operations default to dry-run. The report shows:

- `COPY (dry-run)` — file is missing in destination; would be copied
- `UPDATE (dry-run)` — file exists but content differs; would be updated
- `UNCHANGED` — file is identical; no action needed
- `EXTRA` — file exists in destination only; not touched

To actually copy files, pass `--sync-tools`.

## `--sync-tools`

Copies changed/missing `.py` tool files from `scripts/context_access/` into
`<target>/.agent/tools/context_access/`. Creates the destination directory if
it does not exist.

```bash
python3 scripts/onboard-project.py \
  --target /home/dima/projects/telemost/olcRTC \
  --mode fast \
  --repo https://github.com/dparilov/olcRTC \
  --chat-id -1003596522926 \
  --infra-topic 15222 \
  --coder-topic 7301 \
  --reviewer-topic 13350 \
  --escalation @pariloff \
  --sync-tools
```

After `--sync-tools`, the CLI automatically runs `py_compile` and
`initial-index.py --help` to verify the copied files are valid.

## `--create-pr`

Creates a git branch, stages only the synced tool files, commits, pushes, and
opens a PR. Requires `--sync-tools` to have been passed (files must be written
before staging).

```bash
python3 scripts/onboard-project.py \
  --target /home/dima/projects/telemost/olcRTC \
  --mode fast \
  --repo https://github.com/dparilov/olcRTC \
  --chat-id -1003596522926 \
  --infra-topic 15222 \
  --coder-topic 7301 \
  --reviewer-topic 13350 \
  --escalation @pariloff \
  --sync-tools \
  --create-pr
```

Default branch name: `infra/sync-agent-tools-YYYY-MM-DD`. Override with
`--branch`. Default commit message: `"infra: sync agent context tools"`.
Override with `--commit-message`.

Without `--create-pr`, the CLI prints the exact git and `gh` commands that
would be run — no action taken.

## Safety Allowlist

The CLI enforces a strict allowlist for all file and git operations.

**Will copy:** `scripts/context_access/*.py` → `.agent/tools/context_access/*.py`

**Will never touch:**
- `.agent/AGENT_CONTEXT.md`
- `.agent/config.yaml`
- `.agent/memory/**`
- `.agent/handoffs/**`, `.agent/tasks/**`, `.agent/reviews/**`, `.agent/decisions/**`, `.agent/runbooks/**`
- Any file outside `.agent/tools/context_access/`
- Build binaries, lock files, untracked artifacts

**Will never stage:** anything outside `.agent/tools/context_access/*.py` —
enforced by regex before every `git add`.

**Will never run:**
- `git clean`
- `openclaw doctor --fix`
- OpenClaw auth flows
- Real indexing writes (`--dry-run` always on for index step)
- Destructive git operations

## What PR27 MVP Does Not Do Yet

The following are explicitly out of scope for this PR:

| Feature | Status |
|---------|--------|
| `--mode full` | Placeholder — exits with "not implemented" |
| `--mode repair` | Placeholder — exits with "not implemented" |
| `--mode audit` | Placeholder — exits with "not implemented" |
| Full scaffold creation (`.agent/` bootstrap) | Not implemented; use `setup.sh` |
| Memory indexing writes | Never — index step is dry-run only |
| Candidate promotion | Not implemented |
| Wiki build | Not implemented |
| OpenClaw config validation | Not implemented |

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success / ready for next phase |
| 1 | Validation error (missing args, unimplemented mode, blockers) |
| 2 | Preflight hard fail (infra repo not detected, gh auth failed) |
| 3 | Scaffold missing (`.agent/` not found — run `setup.sh` first) |
| 4 | Tool sync failed |
| 5 | Compile or `--help` check failed |
| 6 | Git / PR creation failed |
| 7 | Index dry-run failed |

## Additional Flags

| Flag | Default | Description |
|------|---------|-------------|
| `--strict` | off | Treat OpenClaw warnings as failures |
| `--branch NAME` | `infra/sync-agent-tools-YYYY-MM-DD` | Override PR branch name |
| `--base-branch NAME` | current branch | PR base branch |
| `--commit-message MSG` | `infra: sync agent context tools` | Commit message |
