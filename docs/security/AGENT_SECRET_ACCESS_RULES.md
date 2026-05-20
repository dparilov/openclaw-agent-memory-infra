# Agent Secret Access Rules

Defines what agents may and must not do when handling secrets.

---

## Agents MAY

- Read registry files (`~/.agent-secrets/*/registry.yaml`) to discover aliases and metadata.
- List secret aliases and their availability status.
- Check whether a referenced local path exists:
  ```bash
  test -f ~/.agent-secrets/pyrogram/handoff_dispatcher.session
  ```
- Check file permissions:
  ```bash
  stat -c "%a %n" ~/.agent-secrets/projects/<project-name>/.env
  ```
- Create placeholder templates under `~/.agent-secrets/exchange/templates/`.
- Ask the human to upload completed files to `~/.agent-secrets/exchange/incoming/`.
- Move uploaded files from `incoming/` to final secret locations after the human replies `done`.
- Use a secret locally when executing a tool or command that requires it (e.g., running a Pyrogram script that reads `.session`).
- Report availability status (alias + status only, no values).
- Create the exchange directory structure with safe permissions when explicitly asked:
  ```bash
  mkdir -p ~/.agent-secrets/exchange/templates \
           ~/.agent-secrets/exchange/incoming \
           ~/.agent-secrets/exchange/processed
  chmod 700 ~/.agent-secrets
  find ~/.agent-secrets -type d -exec chmod 700 {} \;
  find ~/.agent-secrets -type f -exec chmod 600 {} \;
  ```

---

## Agents MUST NOT

- **Print secret values** — in any output, log, summary, or status message.
- **Ask the human to paste secret values into chat** — use the exchange directory template flow instead.
- **Copy secret values into chat** — even partially or in truncated form.
- **Commit secret files** — `.session`, `.env`, OAuth tokens, API keys, passwords, private keys.
- **Include secret values in memory files** — not in `MEMORY.md`, `current-state.md`, `agent-brief.md`, or any other memory artifact.
- **Include secret values in `ACTIVE.md`** — handoff files must not contain credentials.
- **Include secret values in handoff/review reports** — the `## Coder implementation report` and `## Reviewer report` sections must stay clean.
- **Include secret values in GitHub PR comments, PR bodies, or commit messages**.
- **Summarize secret values during restore/refresh** — availability status only.
- **Leave completed secret files world-readable** — always enforce `600` permissions.
- **Leave secret files in `/tmp` or random temp locations** unless immediately moved and permissions fixed.
- **Reveal the contents of `exchange/incoming/` files** even if accidentally readable — move them, do not print them.

---

## Secret-required task flow

1. Check registry: does the alias exist and is the path available?
2. If available: proceed and use the secret locally without printing it.
3. If missing or path not found:
   a. Do not ask the human to paste the value.
   b. Write a placeholder template to `exchange/templates/`.
   c. Output a placement package (see [SECRETS_REGISTRY_PROTOCOL.md §4](SECRETS_REGISTRY_PROTOCOL.md)).
   d. Wait for human to reply `done`.
4. After `done`:
   a. Verify the file appeared in `incoming/`.
   b. Move/install to final location.
   c. Set `600` permissions.
   d. Report alias + status only (no values).

---

## Secret availability report format

After restore/refresh, agents report only:

```text
Secrets registry: found
Exchange directory: ~/.agent-secrets/exchange
Available aliases:
- <alias-id> — <type> — available
- <alias-id> — <type> — available
Missing:
- <alias-id> — path not found
No secret values printed.
```

If registry is absent:

```text
Secrets registry: not configured
```

---

## Accidental exposure recovery

If an agent realizes it has printed or logged secret material:

1. Acknowledge the exposure immediately.
2. Do not repeat or reference the exposed value.
3. Inform the human: the secret should be rotated.
4. Do not include the exposed value in any summary, memory write, or handoff.
