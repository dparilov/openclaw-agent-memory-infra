# Secrets Registry Protocol

Defines a local, agent-visible secrets registry. Secrets stay on the Linux host; only metadata (aliases, paths, status) travels through agent memory, chat, handoffs, or PRs.

---

## 1. Core model

### Permanent secret root

```text
~/.agent-secrets/
```

Suggested layout:

```text
~/.agent-secrets/
  global/
    registry.yaml
  projects/
    <project-name>/
      registry.yaml
      .env
      oauth/
      service-accounts/
  pyrogram/
    handoff_dispatcher.session
  exchange/
    templates/
    incoming/
    processed/
```

Required permissions:

```bash
mkdir -p ~/.agent-secrets/exchange/templates \
         ~/.agent-secrets/exchange/incoming \
         ~/.agent-secrets/exchange/processed
chmod 700 ~/.agent-secrets
find ~/.agent-secrets -type d -exec chmod 700 {} \;
find ~/.agent-secrets -type f -exec chmod 600 {} \;
```

---

## 2. Registry reference in project config

`<target>/.agent/config.yaml` or `<target>/.agent/AGENT_CONTEXT.md` may point to the registry:

```yaml
secrets:
  global_registry: ~/.agent-secrets/global/registry.yaml
  project_registry: ~/.agent-secrets/projects/<project-name>/registry.yaml
  exchange_dir: ~/.agent-secrets/exchange
```

The registry contains aliases and metadata **only** — not raw secret values.

---

## 3. Registry format

See [`SECRETS_REGISTRY_TEMPLATE.yaml`](SECRETS_REGISTRY_TEMPLATE.yaml) for the canonical template.

Example entry for a project registry:

```yaml
version: 1
scope: project
project: personal-assistant-n8n

secret_root: ~/.agent-secrets
exchange_dir: ~/.agent-secrets/exchange

secrets:
  - id: telegram.pyrogram.handoff_dispatcher
    type: pyrogram_session
    location: ~/.agent-secrets/pyrogram/handoff_dispatcher.session
    purpose: Send handoff dispatch messages to Telegram topics.
    access_policy: local_only
    owner: human

  - id: n8n.local.env
    type: env_file
    location: ~/.agent-secrets/projects/personal-assistant-n8n/.env
    purpose: Local n8n runtime credentials and webhook URLs.
    access_policy: local_only
    owner: human

accounts:
  - id: telegram.dispatcher_user
    service: Telegram
    login_hint: "@handoff_dispatcher"
    purpose: Pyrogram user session for handoff dispatch.
    secret_ref: telegram.pyrogram.handoff_dispatcher

  - id: n8n.local_admin
    service: n8n
    url: "http://localhost:5678"
    login_hint: "local admin"
    secret_ref: n8n.local.env
```

---

## 4. Missing-secret flow

When the agent needs a secret that is not present, it must **not** ask the human to paste the value into chat.

Instead, the agent generates a placement package and outputs:

```text
Secret required: n8n.local.env

I created a template on the Linux host:
~/.agent-secrets/exchange/templates/n8n.local.env.template

Download or open it, replace placeholders locally on Windows, then upload the completed file to:
~/.agent-secrets/exchange/incoming/n8n.local.env

Do not paste secret values into chat.

After upload, reply: done.
```

Template content example (written to `exchange/templates/`):

```env
N8N_ENCRYPTION_KEY=<PASTE_VALUE_HERE>
N8N_BASIC_AUTH_USER=<PASTE_VALUE_HERE>
N8N_BASIC_AUTH_PASSWORD=<PASTE_VALUE_HERE>
WEBHOOK_URL=<PASTE_VALUE_HERE>
```

Install command (run by agent after human replies `done`):

```bash
mkdir -p ~/.agent-secrets/projects/personal-assistant-n8n
mv ~/.agent-secrets/exchange/incoming/n8n.local.env \
   ~/.agent-secrets/projects/personal-assistant-n8n/.env
chmod 600 ~/.agent-secrets/projects/personal-assistant-n8n/.env
```

Optional archive:

```bash
mkdir -p ~/.agent-secrets/exchange/processed
cp ~/.agent-secrets/projects/personal-assistant-n8n/.env \
   ~/.agent-secrets/exchange/processed/n8n.local.env.installed
chmod 600 ~/.agent-secrets/exchange/processed/n8n.local.env.installed
```

Verification command:

```bash
test -f ~/.agent-secrets/projects/personal-assistant-n8n/.env && \
  stat -c "%a %n" ~/.agent-secrets/projects/personal-assistant-n8n/.env
```

After `done`, the agent reports only:

```text
Secret alias: n8n.local.env
Status: available
Location: ~/.agent-secrets/projects/personal-assistant-n8n/.env
No secret values printed.
```

---

## 5. Memory restore behavior

After restore/refresh, the agent loads secret registry pointers and reports only metadata:

```text
Secrets registry: found
Exchange directory: ~/.agent-secrets/exchange
Available aliases:
- telegram.pyrogram.handoff_dispatcher — pyrogram_session — available
- n8n.local.env — env_file — available
Missing:
- google.calendar.oauth — path not found
No secret values printed.
```

If the registry path is missing:

```text
Secrets registry: not configured
```

Continue normal operation. Ask only if the current task requires a secret.

If the exchange directory is missing, the agent may create the directory structure with safe permissions when **explicitly asked** to initialize the secrets workflow.

---

## 6. Security classifications

| Category | Examples | Rule |
|----------|----------|------|
| Public config | `chat_id`, `topic_id` | OK in committed config |
| Sensitive metadata | `login_hint` (non-secret) | OK if not revealing actual credential |
| Secret material | API token, password, session string, private key, OAuth token, `.session`, `.env` | **Never** in git / memory / chat / handoff / PR |
| Derived secret material | OAuth refresh token, Pyrogram `.session` | **Never** in git / memory / chat / handoff / PR |
| Exchange templates | Placeholder files in `templates/` | OK if placeholders contain no real values |
| Completed exchange files | Files in `incoming/` / `processed/` | Secret material — never committed or printed |

---

## 7. Related docs

| Doc | Purpose |
|-----|---------|
| [SECRETS_REGISTRY_TEMPLATE.yaml](SECRETS_REGISTRY_TEMPLATE.yaml) | Copy-paste registry template |
| [AGENT_SECRET_ACCESS_RULES.md](AGENT_SECRET_ACCESS_RULES.md) | What agents may and must not do with secrets |
| [WINDOWS_TO_LINUX_SECRET_PLACEMENT.md](WINDOWS_TO_LINUX_SECRET_PLACEMENT.md) | Step-by-step placement methods (WinSCP, SCP, SSH) |
| [SECRET_EXCHANGE_DIRECTORY.md](SECRET_EXCHANGE_DIRECTORY.md) | Exchange directory structure and lifecycle |
