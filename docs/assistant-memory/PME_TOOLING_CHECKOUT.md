# PME Tooling Checkout

Reference for auto-provisioning the local `openclaw-agent-memory-infra` PME tooling checkout required by ASSISTANT memory restore.

---

## Purpose

ASSISTANT memory restore uses two PME scripts:

```text
scripts/refresh-memory.py
scripts/recover-memory.py
```

These scripts are part of the `openclaw-agent-memory-infra` repository. A local checkout of this repository must be available before restore commands can run.

This checkout is **not**:
- a product repository;
- a product project scaffold;
- an ACTIVE handoff workspace;
- a CODER or REVIEWER workspace.

It is allowed to be provisioned automatically by ASSISTANT in DM mode without human confirmation.

---

## PME_REPO discovery order

Resolve `PME_REPO` using this order. A path is **valid** only if both scripts exist:

```bash
test -f "$CANDIDATE/scripts/refresh-memory.py" && \
test -f "$CANDIDATE/scripts/recover-memory.py"
```

| Priority | Source |
|----------|--------|
| 1 | `$PME_REPO` environment variable, if set and valid |
| 2 | `$OPENCLAW_AGENT_MEMORY_INFRA` environment variable, if set and valid |
| 3 | `$HOME/openclaw-agent-memory-infra`, if valid |
| 4 | `$HOME/.pme/openclaw-agent-memory-infra`, if valid |
| 5 | Auto-provision: clone into `$HOME/.pme/openclaw-agent-memory-infra` |

---

## Deterministic clone target

If none of the above paths is valid, the agent clones into:

```text
~/.pme/openclaw-agent-memory-infra
```

This path is fixed and deterministic.

---

## Auto-provisioning commands

```bash
mkdir -p "$HOME/.pme"

if [ ! -d "$HOME/.pme/openclaw-agent-memory-infra/.git" ]; then
  git clone https://github.com/dparilov/openclaw-agent-memory-infra.git \
    "$HOME/.pme/openclaw-agent-memory-infra"
else
  git -C "$HOME/.pme/openclaw-agent-memory-infra" pull --ff-only
fi

PME_REPO="$HOME/.pme/openclaw-agent-memory-infra"
```

Validation after provisioning:

```bash
test -f "$PME_REPO/scripts/refresh-memory.py" && \
test -f "$PME_REPO/scripts/recover-memory.py"
```

---

## Failure semantics

Missing local PME repo before auto-provisioning is **not** a blocking condition.

Blocking is allowed only if one of these occurs after an auto-provisioning attempt:

| Failure | Effect |
|---------|--------|
| `git` is unavailable | READY: `PME tooling: blocked (git unavailable)` |
| GitHub/network access fails | READY: `PME tooling: blocked (clone failed: network error)` |
| `git clone` fails | READY: `PME tooling: blocked (clone failed: <error>)` |
| `git pull` fails | READY: `PME tooling: blocked (pull failed: <error>)` |
| Scripts missing after clone/pull | READY: `PME tooling: blocked (scripts not found after clone)` |
| Filesystem permission error | READY: `PME tooling: blocked (permission denied: ~/.pme)` |

When PME tooling is blocked, `Memory capability` remains `ready` (workspace is independent of PME tooling). Restore will ask for a PME tooling path before proceeding.

---

## READY output with PME tooling status

Cloned on first run:

```text
PME tooling: ready (~/.pme/openclaw-agent-memory-infra, cloned)
```

Already present and updated:

```text
PME tooling: ready (~/.pme/openclaw-agent-memory-infra, up to date)
```

Found at a higher-priority path (no update):

```text
PME tooling: ready (~/<path>, exists)
```

Provisioning failed:

```text
PME tooling: blocked (<reason>)
```

---

## Prohibited behaviors

After PR58, ASSISTANT must not:

- Say `PME repo: not found locally` without first attempting auto-provisioning.
- Say `По правилам бутстрапа сам ничего не клонирую` when referring to this PME tooling checkout.
- Report `Memory capability: blocked` on READY only because the PME repo was missing before a clone attempt.

---

## Related docs

- [ASSISTANT_BOOTSTRAP.md](../agent-bootstrap/ASSISTANT_BOOTSTRAP.md) — section 2d: PME tooling checkout auto-provisioning
- [RESTORE_MEMORY_FLOW.md](RESTORE_MEMORY_FLOW.md) — section 2b: pre-step before restore commands
