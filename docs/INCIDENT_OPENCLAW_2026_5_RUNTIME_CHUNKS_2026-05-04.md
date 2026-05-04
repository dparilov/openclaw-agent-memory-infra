# Incident — OpenClaw 2026.5 runtime chunk failures on gateway

Date: 2026-05-04
Environment: Clearmind_projects VPS
Impact: Telegram group/topic replies stopped working for 15222, 7301, 13350.

## Symptoms

- Gateway/Telegram transport appeared reachable.
- Direct messages still partially worked.
- Group/topic messages were received but dispatch failed or sessions got stuck.
- Logs showed ERR_MODULE_NOT_FOUND for OpenClaw dist runtime chunks.

Observed errors:

- Cannot find module '/usr/lib/node_modules/openclaw/dist/apply.runtime-DYU1MJCD.js' imported from /usr/lib/node_modules/openclaw/dist/get-reply-1y8kEvLp.js
- Cannot find module '/usr/lib/node_modules/openclaw/dist/apply.runtime-DcqsWjod.js' imported from /usr/lib/node_modules/openclaw/dist/get-reply-1y8kEvLp.js
- On beta attempt: Cannot find module '/usr/lib/node_modules/openclaw/dist/server-close-Dlv4F607.js' imported from /usr/lib/node_modules/openclaw/dist/server.impl-9zSO16MG.js

## Versions tested

- openclaw@2026.5.3-1: failed in gateway reply path with missing runtime chunks.
- openclaw@2026.5.4-beta.1: also failed / showed missing runtime chunk on shutdown path.
- openclaw@2026.4.23: restored working group/topic replies.

## Additional config compatibility issue

During 2026.5 testing, openclaw doctor wrote:

```
messages.groupChat.visibleReplies
```

`openclaw@2026.4.23` does not recognize this key and failed with:

```
messages.groupChat: Unrecognized key: "visibleReplies"
```

Manual rollback fix:

```bash
cp ~/.openclaw/openclaw.json ~/.openclaw/openclaw.json.bak-remove-visibleReplies-$(date +%Y%m%d-%H%M%S)

python3 - <<'PY'
import json
from pathlib import Path

p = Path.home() / ".openclaw" / "openclaw.json"
data = json.loads(p.read_text())
data.get("messages", {}).get("groupChat", {}).pop("visibleReplies", None)
p.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
print("removed messages.groupChat.visibleReplies")
PY
```

## Recovery performed

```bash
sudo npm uninstall -g openclaw
sudo rm -rf /usr/lib/node_modules/openclaw
sudo npm install -g openclaw@2026.4.23

systemctl --user reset-failed openclaw-gateway.service
systemctl --user restart openclaw-gateway.service
```

Validated:

* Gateway connectivity: OK
* Telegram transport: OK
* Topic 15222: replies OK
* Topic 7301: replies OK
* Topic 13350: replies OK

## Current safe state

* Gateway service package pinned to openclaw@2026.4.23.
* Shell CLI may still resolve to OpenClaw 2026.5.3-1 via nvm.
* Do not run `openclaw doctor --fix` or `openclaw doctor --repair` from 2026.5 CLI while gateway is pinned to 2026.4.23, because it may write config keys incompatible with 2026.4.23.

## Follow-up recommendations

1. Pin gateway package/version explicitly until a fixed OpenClaw release is available.
2. Add an OpenClaw version skew check to onboarding/preflight:
   - shell CLI version
   - service package version
   - gateway self version
3. Add recovery card to docs:
   - missing runtime chunk
   - rollback to known-good version
   - remove incompatible visibleReplies
4. Report upstream:
   - npm packages 2026.5.3-1 and 2026.5.4-beta.1 appear to miss required dist runtime chunks in gateway paths.
