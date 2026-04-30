# Full Environment Onboarding Checklist

Use this doc when setting up a **brand-new VPS or workstation** to run OpenClaw with agent memory.  
Complete every section in order. Each gate must pass before proceeding.

---

## A. OS Baseline

| Check | Command | Expected |
|-------|---------|----------|
| Ubuntu 22.04+ | `lsb_release -rs` | `22.04` or higher |
| 2+ GB RAM | `free -h` | `Mem:` row ≥ 2.0G |
| 10+ GB disk free | `df -h /` | Available ≥ 10G |
| sudo works | `sudo echo ok` | `ok` |

**Gate A: PASS** — all four checks green.

---

## B. System Packages

```bash
sudo apt-get update -qq
sudo apt-get install -y git curl wget unzip jq python3 python3-pip python3-venv
```

| Package | Verify | Expected |
|---------|--------|----------|
| git | `git --version` | `git version 2.*` |
| curl | `curl --version` | first line contains `curl` |
| python3 | `python3 --version` | `Python 3.10+` |
| jq | `jq --version` | `jq-1.*` |

**Gate B: PASS** — all packages installed.

### GitHub CLI (gh)

```bash
# Ubuntu/Debian — install GitHub CLI
curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg \
  | sudo dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" \
  | sudo tee /etc/apt/sources.list.d/github-cli.list > /dev/null
sudo apt-get update -qq && sudo apt-get install -y gh
gh --version   # confirm install
```

**Gate B2: PASS** — `gh --version` prints a version string.

---

## C. GitHub & Git Identity

```bash
git config --global user.name  "Your Name"
git config --global user.email "you@example.com"
gh auth login          # choose HTTPS, browser or token
gh auth status         # must show ✓ Logged in
```

**Gate C: PASS** — `gh auth status` shows logged-in account.

---

## D. Clone Infrastructure Repo

```bash
mkdir -p ~/projects && cd ~/projects
gh repo clone dparilov/openclaw-agent-memory-infra
cd openclaw-agent-memory-infra
git log --oneline -3    # confirm recent history visible
```

**Gate D: PASS** — repo cloned, recent commits visible.

---

## E. OpenClaw Install

Follow the install guide in your OpenClaw distribution.  
After install:

```bash
openclaw --version      # any semver output
openclaw status         # no fatal errors
```

**Gate E: PASS** — version prints, status clean.

---

## F. Telegram Integration

```bash
openclaw config telegram   # interactive setup
```

Send `/start` to your bot. Confirm a response arrives.

**Gate F: PASS** — bot replies to `/start`.

---

## G. Model Providers

Configure at least one LLM provider (Anthropic, OpenAI, Google, or local):

```bash
openclaw config model list     # should show at least one provider
openclaw config model test     # sends a test prompt
```

**Gate G: PASS** — test prompt returns a response.

---

## H. Codex OAuth (if using Codex agent)

```bash
codex login    # or: openclaw config codex
codex whoami   # shows authenticated identity
```

If Codex is not part of your stack, mark this N/A.

**Gate H: PASS or N/A**

---

## I. MeridianA Install (required for `meridiana/*` model aliases)

MeridianA is a patched local proxy (`@rynfar/meridian` v1.30.2 + OpenClaw adapter).
Required for agents using `meridiana/claude-opus-4-7` or similar aliases.

```bash
# Install MeridianA (builds locally from public npm + vendored patch)
bash scripts/install-meridiana.sh --target ~/meridiana-openclaw --port 3470

# After install, authenticate Claude Max account (once per machine):
node ~/meridiana-openclaw/dist/cli.js profile add
# Follow browser OAuth prompt. Do NOT copy tokens between machines.

# Start the proxy:
MERIDIAN_PORT=3470 node ~/meridiana-openclaw/dist/cli.js
```

Requirements: Node.js >= 22, npm, GNU patch (`sudo apt-get install patch`).
`bun` is installed automatically if missing.

| Check | Command | Expected |
|-------|---------|----------|
| Proxy running | `curl -s http://127.0.0.1:3470/v1/models` | JSON models list |
| Auth complete | `node ~/meridiana-openclaw/dist/cli.js profile list` | at least one profile |

See `docs/MERIDIANA_DEPENDENCY.md` for model alias configuration and troubleshooting.

**Gate I: PASS** — proxy responds on port 3470 and at least one Claude Max profile is active.

---

## J. Role & Topic Planning

Before onboarding agents, decide:

| Decision | Guidance |
|----------|----------|
| Which topics will this operator own? | See `docs/MEMORY_MIGRATION_PLAYBOOK.md` §1 |
| Which agent roles are needed? | infra / coder / reviewer — map each to a topic ID |
| Is this a fresh install or a migration? | Migration → read `docs/MEMORY_MIGRATION_PLAYBOOK.md` first |

**Gate J: PASS** — at least one topic assigned to at least one role.

---

## K. Ready-for-Handoff Report

Before handing off to the infra agent, produce this report:

```
=== READY-FOR-HANDOFF REPORT ===
Date:
Operator:
Host:           <hostname or VPS label>
OS:             <Ubuntu XX.XX>
OpenClaw:       <version>
Model provider: <Anthropic / OpenAI / Google / local>
Codex:          <version or N/A>
MeridianA:      <version or N/A>
Topics planned: <list>
Roles planned:  <list>
Gate summary:   A=PASS B=PASS C=PASS D=PASS E=PASS F=PASS G=PASS H=PASS/N/A J=PASS
Open issues:    <none / list>
```

Paste this report into your first message to the infra agent.  
See `docs/EXTERNAL_TO_INFRA_HANDOFF.md` for the expected handoff sequence.
