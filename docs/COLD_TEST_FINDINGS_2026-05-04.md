# Cold Test Findings — 2026-05-04

Real Phase 1 run findings after PR #25. All items below are confirmed against live environment.
Reviewer: external human operator. Infra agent: openclaw/main (meridian/claude-sonnet-4-6).

---

## FINDING-1: Phase 1 Must Be Target-Project Agnostic

**Observed:** Gate 1C probed `dparilov/olcRTC` (a product repo) during GitHub CLI checks, before
`PROJECT_TARGET_ACK` was issued. This was caught and corrected by the external reviewer mid-run.

**Rule:**
> Phase 1 is target-project agnostic. No product repo URL, branch, `.agent/` scaffold status,
> topic role assumptions, or project-specific blocker language may appear before `PROJECT_TARGET_ACK`.

**Applies to:** Wizard prompt templates, Gate 1C (GitHub repo probe), Gate 1D (memory-infra only),
Phase 1 Summary output.

**Enforcement:** Gate 1C must check only: `gh auth status`, token scopes, `gh repo view` of the
memory-infra repo itself. Any other repo check is Phase 2+.

---

## FINDING-2: Add Phase 0 — Path Selection

**Observed:** The wizard launched directly into a full 10-gate Phase 1 cold audit for an environment
that had been set up recently and was mostly healthy. This was unnecessarily heavy.

**Rule:** The wizard must begin with Phase 0 — path selection:

| Path | When to use |
|------|-------------|
| A. Full Environment Cold Start | First-time setup, unknown environment state |
| B. Fast Project Onboarding in Known-Good Environment | Env recently verified, onboarding a new project |
| C. Repair / Resume Failed Setup | Previous run left blockers; known partial state |
| D. Audit Only | Operator wants read-only status, no changes |

Path B (Fast Project Onboarding) uses a Fast Preflight instead of full Phase 1. See SETUP_WIZARD_FLOW.md.

---

## FINDING-3: OAuth Gates Are Human-Operated

**Observed:** The infra agent attempted to complete OAuth flows autonomously (browser login, device
pairing) and produced misleading status messages when they could not complete without human action.

**Rule:**
- The agent detects the auth problem and describes it.
- The agent presents the human with the exact URL/code/command needed.
- The agent waits. It does not poll aggressively or retry failed flows.
- The agent verifies after the human confirms completion.
- The agent must not state "completing OAuth" or "OAuth succeeded" until verification passes.

**Applies to:** Gate 1H (Codex OAuth), Gate 1G (model provider auth), Gate 1I (MeridianA auth),
any future OAuth gate.

---

## FINDING-4: Headless Codex OAuth — Fallback Paths

**Observed:** Two failures before auth was resolved:

1. **Browser Login on VPS** — `localhost:1455` callback is not reachable from a remote browser.
   The flow hangs. The session times out.

2. **Device Pairing via OpenClaw** — OpenClaw's openai-codex provider sent the user to
   `https://platform.openai.com/device`, which returns 404 (stale/deprecated endpoint).
   In OpenClaw 2026.5, Device Pairing may reach `https://auth.openai.com/codex/device` but
   fail by not displaying the required device code — making it non-completable without the code.
   This is an OpenClaw provider plugin issue to report upstream.
   Note: the official Codex CLI (`codex login --device-auth`) uses a separate auth path
   and should not be conflated with OpenClaw's built-in provider device pairing flow.

3. **Non-default profile fallback** — After the operator added a second OAuth profile
   (`dmitry@datamint.ai`), OpenClaw automatically fell back to the valid profile when the
   `default` profile was expired. The codex agent became functional without any config change.

**Rules for wizard:**
- On VPS/headless: warn that Browser Login requires an SSH tunnel (`ssh -L 1455:localhost:1455 <vps>`).
- Do not present OpenClaw device-pairing as a reliable option until the endpoint and code-display issues are resolved.
- After any new profile is added: re-run `openclaw models status` and check for valid non-expired profiles.
- A functional Telegram test (send message to the bound topic; verify agent response) is the only
  reliable end-to-end confirmation of model call success.

**Known-working remediation order (2026-05-04):**
1. Add new OAuth profile: `openclaw models auth login --provider openai-codex`
2. Select Browser Login (requires SSH tunnel to VPS) or use Codex CLI device auth directly.
3. Verify: `openclaw models status | grep openai-codex` — new profile shows `ok`.
4. Confirm: send test message to codex agent Telegram topic; verify response.

---

## FINDING-5: OpenClaw 2026.5 Config Migration Issue

**Observed:** Every `openclaw models` command printed:
```
Config was last written by a newer OpenClaw (2026.5.3-1); current version is 2026.4.23.
```
This appeared on every invocation and cluttered gate output. It did not block operation but
indicates a config schema mismatch. A related known issue is that `agents.defaults.llm` (legacy key)
can appear in configs written by older wizard scripts or manual edits and causes validation errors
in 2026.5+.

**Recovery card:**

**Symptom:** `openclaw doctor` or `openclaw models status` prints:
```
agents.defaults: Unrecognized key: "llm"
```

**Steps:**
```bash
# 1. Backup config before touching it
cp ~/.openclaw/openclaw.json ~/.openclaw/openclaw.json.bak-$(date +%Y%m%d)

# 2. Remove the legacy key
python3 -c "
import json
with open('$HOME/.openclaw/openclaw.json') as f:
    d = json.load(f)
d.get('agents', {}).get('defaults', {}).pop('llm', None)
with open('$HOME/.openclaw/openclaw.json', 'w') as f:
    json.dump(d, f, indent=2)
print('done')
"

# 3. Verify
openclaw doctor
openclaw models status | head -5
```

**Warning:** Do not run `openclaw doctor --fix` repeatedly during recovery. Each run may re-write
config and increment the version mismatch. Run once, inspect output, then verify manually.

---

## FINDING-6: Gate S Security ACK Must Be Scoped

**Observed:** `groupPolicy=open` (5 occurrences) was found in `openclaw.json`. No `allowedTools`
restrictions. No `approval` flow. The wizard correctly halted and requested an ACK.

The ACK provided by the operator included explicit scope:
> "accepted only for the current trusted Clearmind_projects test environment;
>  not accepted as a recommended production default;
>  record as security finding for future hardening docs."

**Rule:** The wizard must not offer CONTINUE after detecting `groupPolicy=open` until the operator
provides `ACK: groupPolicy=accept` with explicit scope. The ACK and scope must be recorded in the
Phase 1 Summary under "Warnings accepted."

**Security finding SEC-001 (recorded for hardening backlog):**
- No per-agent `allowedTools` allowlists in any agent config
- No `approval` flow configured
- `groupPolicy=open` on all channels
- Recommended mitigations (do not apply automatically):
  - Add `allowedTools` per agent to restrict to minimum required tool set
  - Set `groupPolicy` to `members` or `allowlist` for production environments
  - Add `approval` flow for high-risk tool calls (exec, filesystem writes)

---

## FINDING-7: Full Phase 1 Is Too Heavy for Repeated Onboarding

**Observed:** The full 10-gate Phase 1 audit takes significant wall-clock time (30–45 min with human
review at each gate). For an environment that was set up recently and is mostly healthy, running
the full audit every time a new project is onboarded is wasteful.

**Rule:** Introduce a Fast Preflight (Path B) that checks only the minimum set of gates required to
confirm the environment is still in the state last audited:

Fast Preflight gates:
1. memory-infra repo current (git pull --dry-run; current branch/SHA)
2. OpenClaw gateway reachable (port check; `openclaw status`)
3. Telegram transport healthy (bot polling active; `in:just now`)
4. GitHub auth valid (`gh auth status`)
5. Required role models available and authenticated
6. Security ACK still valid (was issued in last N days; environment unchanged)
7. Target repo checked only after Phase 2 `PROJECT_TARGET_ACK`

Fast Preflight does not run OS baseline, system tools, or MeridianA if those were PASS in the
last full cold audit and no infrastructure changes have been made.

---

## FINDING-8: Failed Gates Need Deterministic Remediation Cards

**Observed:** Multiple gates (1H, 1I, 1S) required back-and-forth clarification because the
wizard's FAIL output did not present all remediation options in a structured, operator-actionable
format.

**Rule:** Every FAIL or WARN gate output must include a remediation card with exactly these options
(mark N/A if not applicable):

```
Remediation options:
A. Fix now — exact commands: ...
B. Mark N/A — condition: ...
C. Choose alternate model — command: ...
D. Continue with WARN — ACK required: ...
E. STOP — reason: ...
```

The wizard waits for the operator to select A/B/C/D/E before proceeding. It does not auto-select.

See also: `docs/OAUTH_GATE_CARDS.md` for pre-written remediation cards for known auth failures.
