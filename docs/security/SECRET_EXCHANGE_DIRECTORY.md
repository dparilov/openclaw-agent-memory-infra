# Secret Exchange Directory

Specifies the exchange directory structure and lifecycle for moving secret files between the human (Windows) and the Linux runtime host.

---

## Fixed path

```text
~/.agent-secrets/exchange/
```

---

## Subdirectory structure

```text
~/.agent-secrets/exchange/
  templates/
  incoming/
  processed/
```

| Subdirectory | Owner | Purpose |
|---|---|---|
| `templates/` | Agent writes | Placeholder template files with no real secrets |
| `incoming/` | Human uploads | Completed secret files placed by the human |
| `processed/` | Agent archives | Installed copies archived after successful placement |

---

## Initialization

Create the exchange directory structure with safe permissions:

```bash
mkdir -p ~/.agent-secrets/exchange/templates \
         ~/.agent-secrets/exchange/incoming \
         ~/.agent-secrets/exchange/processed
chmod 700 ~/.agent-secrets
find ~/.agent-secrets -type d -exec chmod 700 {} \;
find ~/.agent-secrets -type f -exec chmod 600 {} \;
```

Agents may create this structure when explicitly asked to initialize the secrets workflow.

---

## Lifecycle

### 1. Template creation

The agent writes a placeholder template to `exchange/templates/`:

```text
~/.agent-secrets/exchange/templates/<filename>.template
```

Template content must use placeholders only:

```env
SECRET_KEY=<PASTE_VALUE_HERE>
API_TOKEN=<PASTE_VALUE_HERE>
```

Templates must not contain real secret values.

### 2. Human upload

The human fills the template locally on Windows, then uploads the completed file to:

```text
~/.agent-secrets/exchange/incoming/<filename>
```

See [WINDOWS_TO_LINUX_SECRET_PLACEMENT.md](WINDOWS_TO_LINUX_SECRET_PLACEMENT.md) for upload methods (WinSCP / SCP / VS Code Remote SSH).

### 3. Installation

After the human replies `done`, the agent:

1. Verifies the file appeared in `incoming/`.
2. Moves (not copies) it to the final secret location:
   ```bash
   mv ~/.agent-secrets/exchange/incoming/<filename> ~/.agent-secrets/<final-path>
   chmod 600 ~/.agent-secrets/<final-path>
   ```
3. Optionally archives the installed copy to `processed/`:
   ```bash
   cp ~/.agent-secrets/<final-path> ~/.agent-secrets/exchange/processed/<filename>.installed
   chmod 600 ~/.agent-secrets/exchange/processed/<filename>.installed
   ```
4. Reports availability status only — no file contents printed.

---

## Security rules

| Rule | Details |
|------|--------|
| `incoming/` is not a permanent store | Files must be moved out after installation |
| Never print `incoming/` contents | Even if readable — move and verify only |
| Permissions | All files under `~/.agent-secrets/` must be `600`; all directories `700` |
| No commits | Exchange files must not be committed to any repository |
| Templates are safe only when placeholders are empty | Never write real values into template files |
| `processed/` is optional | Delete or keep as audit trail; ensure `600` permissions |

---

## File naming convention

| Template | `<alias-id>.template` |
|----------|----------------------|
| Incoming | `<alias-id>` or `<alias-id>.<ext>` |
| Processed archive | `<alias-id>.installed` |

Examples:

| Stage | Example path |
|-------|--------------|
| Template | `~/.agent-secrets/exchange/templates/n8n.local.env.template` |
| Incoming | `~/.agent-secrets/exchange/incoming/n8n.local.env` |
| Processed | `~/.agent-secrets/exchange/processed/n8n.local.env.installed` |
| Final location | `~/.agent-secrets/projects/personal-assistant-n8n/.env` |

---

## Related docs

- [SECRETS_REGISTRY_PROTOCOL.md](SECRETS_REGISTRY_PROTOCOL.md) — registry format and missing-secret flow
- [AGENT_SECRET_ACCESS_RULES.md](AGENT_SECRET_ACCESS_RULES.md) — what agents may and must not do
- [WINDOWS_TO_LINUX_SECRET_PLACEMENT.md](WINDOWS_TO_LINUX_SECRET_PLACEMENT.md) — upload methods (WinSCP, SCP, SSH)
