# Security

Local secrets registry protocol and agent access rules.

## Contents

- [SECRETS_REGISTRY_PROTOCOL.md](SECRETS_REGISTRY_PROTOCOL.md) — core model, registry format, missing-secret flow, restore behavior, security classifications
- [SECRETS_REGISTRY_TEMPLATE.yaml](SECRETS_REGISTRY_TEMPLATE.yaml) — copy-paste template for `~/.agent-secrets/*/registry.yaml`
- [AGENT_SECRET_ACCESS_RULES.md](AGENT_SECRET_ACCESS_RULES.md) — what agents may and must not do with secrets
- [WINDOWS_TO_LINUX_SECRET_PLACEMENT.md](WINDOWS_TO_LINUX_SECRET_PLACEMENT.md) — WinSCP, SCP, and VS Code Remote SSH upload methods
- [SECRET_EXCHANGE_DIRECTORY.md](SECRET_EXCHANGE_DIRECTORY.md) — exchange directory structure and file lifecycle

## Quick start

1. Initialize the secret root and exchange directory:
   ```bash
   mkdir -p ~/.agent-secrets/exchange/templates \
            ~/.agent-secrets/exchange/incoming \
            ~/.agent-secrets/exchange/processed
   chmod 700 ~/.agent-secrets
   find ~/.agent-secrets -type d -exec chmod 700 {} \;
   ```
2. Copy `SECRETS_REGISTRY_TEMPLATE.yaml` to `~/.agent-secrets/global/registry.yaml` and fill in paths.
3. Reference the registry from `.agent/config.yaml`:
   ```yaml
   secrets:
     global_registry: ~/.agent-secrets/global/registry.yaml
     exchange_dir: ~/.agent-secrets/exchange
   ```
4. When an agent needs a secret, it writes a template to `exchange/templates/` and asks you to upload the completed file to `exchange/incoming/`.
5. Reply `done` after upload — the agent installs and verifies permissions.
