# Agent Collaboration

Minimal protocols for CODER/REVIEWER agent collaboration.

## Contents

- [ACTIVE_HANDOFF_PROTOCOL.md](ACTIVE_HANDOFF_PROTOCOL.md) — how agents pass work back and forth using `.agent/handoffs/ACTIVE.md`
- [ACTIVE_HANDOFF_TEMPLATE.md](ACTIVE_HANDOFF_TEMPLATE.md) — copy-paste template for creating a new handoff
- [HANDOFF_DISPATCH_PROTOCOL.md](HANDOFF_DISPATCH_PROTOCOL.md) — automating handoff routing via Pyrogram Telegram dispatch
- [HANDOFF_DISPATCH_CONFIG.md](HANDOFF_DISPATCH_CONFIG.md) — config reference for the dispatcher (`.agent/config.yaml`)
- [HANDOFF_DISPATCH_MESSAGES.md](HANDOFF_DISPATCH_MESSAGES.md) — canonical trigger messages and agent behavior on receipt

## Quick start

1. REVIEWER or HUMAN creates `.agent/handoffs/ACTIVE.md` from the template.
2. CODER reads it, implements, updates the file.
3. REVIEWER reads it, reviews, updates the file.
4. HUMAN archives after completion.

See [ACTIVE_HANDOFF_PROTOCOL.md](ACTIVE_HANDOFF_PROTOCOL.md) for full rules.
