# Windows-to-Linux Secret Placement

How to move completed secret files from Windows to the Linux host.

The human works on Windows. The Linux runtime host is reachable over Tailscale.
The agent prepares placeholder templates; the human fills them locally and uploads the completed file.

**Never paste secret values into Telegram, chat, or any agent conversation.**

---

## Fixed target path for all uploads

```text
~/.agent-secrets/exchange/incoming/<filename>
```

The agent provides the exact filename in the placement package it outputs.

---

## Method 1 — WinSCP GUI (Recommended)

WinSCP connects to the Linux host over SFTP/SCP via Tailscale.

### Steps

1. The agent writes a placeholder template to:
   ```text
   ~/.agent-secrets/exchange/templates/<filename>.template
   ```
2. The agent outputs a placement package with target path and instructions.
3. On Windows, download or read the template (SCP/WinSCP from `templates/`, or copy the placeholder text from the agent message).
4. Fill in the real values locally on Windows. **Do not open the file in a shared or synced location.**
5. Open WinSCP.
6. Connect to the Linux host:
   - Protocol: SFTP or SCP
   - Host: Tailscale DNS name or Tailscale IP of the Linux host
   - Port: 22
   - Username: Linux user
7. Navigate to:
   ```text
   ~/.agent-secrets/exchange/incoming/
   ```
8. Upload the completed file.
9. Reply to the agent:
   ```text
   done
   ```
10. The agent installs the file from `incoming/` to the final secret location and verifies permissions.

---

## Method 2 — PowerShell SCP

Standard command from a Windows PowerShell terminal:

```powershell
scp .\<local-secret-file> <linux-user>@<tailscale-host>:~/.agent-secrets/exchange/incoming/<secret-file>
```

Example:

```powershell
scp .\n8n.local.env admin@my-linux-host.tailnet.ts.net:~/.agent-secrets/exchange/incoming/n8n.local.env
```

After upload, reply to the agent:
```text
done
```

The agent then runs the install/move/chmod commands on the Linux host.

---

## Method 3 — VS Code Remote SSH / Tailscale SSH

Allowed as a manual placement method if more convenient.

1. Open a remote SSH session to the Linux host in VS Code (via Tailscale SSH or standard SSH).
2. Copy the completed secret file using the VS Code file explorer or any terminal `cp` / drag-drop.
3. Target path:
   ```text
   ~/.agent-secrets/exchange/incoming/<filename>
   ```
4. Reply to the agent:
   ```text
   done
   ```

---

## Agent install commands after upload

After the human replies `done`, the agent verifies and installs:

```bash
# Example for n8n.local.env
mkdir -p ~/.agent-secrets/projects/personal-assistant-n8n
mv ~/.agent-secrets/exchange/incoming/n8n.local.env \
   ~/.agent-secrets/projects/personal-assistant-n8n/.env
chmod 600 ~/.agent-secrets/projects/personal-assistant-n8n/.env
```

Optional: archive the installed copy

```bash
mkdir -p ~/.agent-secrets/exchange/processed
cp ~/.agent-secrets/projects/personal-assistant-n8n/.env \
   ~/.agent-secrets/exchange/processed/n8n.local.env.installed
chmod 600 ~/.agent-secrets/exchange/processed/n8n.local.env.installed
```

Verification:

```bash
test -f ~/.agent-secrets/projects/personal-assistant-n8n/.env && \
  stat -c "%a %n" ~/.agent-secrets/projects/personal-assistant-n8n/.env
```

Agent reports:

```text
Secret alias: n8n.local.env
Status: available
Location: ~/.agent-secrets/projects/personal-assistant-n8n/.env
No secret values printed.
```

---

## Security checklist

| Step | Requirement |
|------|-------------|
| Fill template | On Windows, locally — not in a synced/shared folder |
| Upload path | `~/.agent-secrets/exchange/incoming/` only |
| Do not paste | Never paste secret values into chat or Telegram |
| Permissions | Agent must set `600` after install |
| Directory permissions | `~/.agent-secrets/` must be `700` |
| Temp files | Do not leave filled templates in `/tmp` or synced folders on Windows |
