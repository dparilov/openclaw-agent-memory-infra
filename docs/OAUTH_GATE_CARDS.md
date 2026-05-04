# OAuth Gate Cards

Remediation reference for OAuth and auth failures during OpenClaw wizard setup.

---

## Card OA-1: GitHub CLI Not Authenticated

**Symptom:** `gh auth status` returns `not logged in`

**Fix:**
```bash
gh auth login --web
```

**Verify:**
```bash
gh auth status
```

---

## Card OA-2: Anthropic Token Missing / Invalid

**Symptom:** `openclaw models status` shows `anthropic:default` missing or auth error

**Fix:**
```bash
openclaw models auth add --provider anthropic
```

**Verify:**
```bash
openclaw models status | grep anthropic
```

---

## Card OA-3: MeridianA Not Installed

**Symptom:** `openclaw models status` shows `meridiana effective=models.json:no...ed`

**Fix:**
```bash
bash scripts/install-meridiana.sh
# Then add credentials:
node ~/meridiana-openclaw/dist/cli.js profile add
```

**Verify:**
```bash
openclaw models status | grep meridiana
curl -s http://127.0.0.1:3470/v1/models
```

---

## Card OA-4: Codex OAuth Expired — refresh_token_reused

**Symptom:**
```
openai-codex:default expired expires in 0m
Token refresh failed: 401 { "code": "refresh_token_reused" }
```

**Cause:** The stored refresh token was already rotated (possibly by another session or device).
OpenClaw cannot auto-renew. Manual re-auth required.

**Fix options (present to operator; do not auto-select):**

**Option A — Add new profile via SSH tunnel + Browser Login (VPS environments):**
```bash
# Step 1: On your LOCAL machine, open an SSH tunnel to the VPS
ssh -L 1455:localhost:1455 <your-vps-host>

# Step 2: On the VPS (via the tunnel session), start the login flow
openclaw models auth login --provider openai-codex
# Select: OpenAI Codex Browser Login

# Step 3: Open the displayed URL in your LOCAL browser
# The OAuth callback will be forwarded through the tunnel to the VPS

# Step 4: Verify
openclaw models status | grep openai-codex
```

**Option B — Alternate reviewer model (no re-auth needed):**
```bash
# Reassign the codex agent to a functional model
# (edit openclaw.json or agent config — operator action required)
# Then verify the agent responds via Telegram test
```

**Verify after fix:**
```bash
openclaw models status | grep -A4 openai-codex
# Confirm: new profile shows "ok expires in Xd"
# Then send a test message to the codex agent Telegram topic and confirm response
```

**Notes:**
- If a valid non-default profile already exists (e.g. `openai-codex:dmitry@example.com ok`),
  OpenClaw will automatically fall back to it. Run the Telegram test to confirm before declaring
  BLOCKER cleared.
- The expired `default` profile does not need to be deleted — fallback works automatically.

---

## Card OA-5: Codex Browser Login Fails on VPS (localhost callback)

**Symptom:** Browser Login selected; `openclaw` opens the OAuth URL; session hangs or times out
waiting for `localhost:1455/auth/callback` — because the callback is on the VPS, not the local machine.

**Cause:** OAuth browser login uses `localhost:1455` as the redirect URI. On a headless VPS,
the browser opens on the VPS (or not at all), and the callback never completes from a remote browser.

**Fix:** Use SSH port forwarding to bridge the callback:
```bash
# On your LOCAL machine:
ssh -L 1455:localhost:1455 <vps-host>

# Then retry the login on the VPS — the callback will route through the tunnel
openclaw models auth login --provider openai-codex
```

**Alternative:** Use Codex CLI directly if installed:
```bash
npm i -g @openai/codex
codex login --device-auth
# Expected device URL: https://chatgpt.com/activate
```

---

## Card OA-6: Codex Device Pairing Fails (Stale Endpoint or No Code Displayed)

**Symptom A:** OpenClaw device-pairing flow directs operator to
`https://platform.openai.com/device` which returns 404 (page not found).

**Symptom B (OpenClaw 2026.5+):** Device Pairing may reach `https://auth.openai.com/codex/device`
but the flow fails to display a device code, making it impossible to complete.

**Important distinction:**
- OpenClaw's built-in `--method device-pairing` uses an internal provider plugin with known
  endpoint and code-display issues.
- The **official Codex CLI** (`codex login --device-auth`) is a separate auth path and is
  **not the same flow**. Do not conflate the two. The Codex CLI device auth may work independently
  even when OpenClaw's built-in device pairing fails.

**Workaround:**
- Do not rely on `openclaw models auth login --provider openai-codex --method device-pairing`
  until the endpoint and code-display issues are fixed upstream.
- Preferred alternative: Browser Login with SSH tunnel (Card OA-5).
- If Codex CLI is available: `codex login --device-auth` (separate flow; verify credential
  bridge to OpenClaw separately).

**Upstream bug:** Report to OpenClaw maintainers — openai-codex provider device-pairing
has two issues: stale endpoint (`platform.openai.com/device`) and missing code display
in the updated flow (`auth.openai.com/codex/device`).

---

## Card OA-7: Codex Valid Non-Default Profile — Confirm Fallback

**Symptom:**
```
openai-codex:default expired expires in 0m
openai-codex:someuser@example.com ok expires in Xd
```
Agent may or may not be functional — depends on whether OpenClaw falls back automatically.

**Check:**
```bash
openclaw models status | grep -A6 openai-codex
# If at least one profile shows "ok", proceed to Telegram test
```

**Confirm end-to-end:**
Send a minimal message (e.g. `ping`) to the Telegram topic bound to the codex agent.
If the agent responds → fallback works → BLOCKER cleared.
If the agent does not respond within ~30s → set explicit auth order:

```bash
openclaw models auth order set --provider openai-codex --order someuser@example.com,default
# Then re-test via Telegram
```

---

## Card OA-8: OpenClaw Config Migration — agents.defaults.llm Legacy Key

**Symptom:**
```
agents.defaults: Unrecognized key: "llm"
```
or:
```
Config was last written by a newer OpenClaw (2026.5.x); current version is 2026.4.x.
```

**Cause:** The `agents.defaults.llm` key was used in older versions of openclaw.json.
OpenClaw 2026.5+ does not recognise it and may print a warning or validation error.
The version mismatch warning appears when a newer OpenClaw instance wrote the config
but an older instance is running.

**Fix for `agents.defaults.llm` key:**
```bash
# 1. Backup config
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

**Fix for version mismatch warning:** Update OpenClaw to the version that wrote the config:
```bash
# Check what version wrote the config vs what is running
openclaw models status | grep "Config was last written"
openclaw --version

# Update if needed (operator action — do not auto-update)
```

**Warning:** Do not run `openclaw doctor --fix` repeatedly during recovery. Each invocation
may re-write the config and increment the version. Run once, inspect, then verify manually.
