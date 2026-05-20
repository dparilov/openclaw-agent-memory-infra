# Assistant Agent One-Line Prompts

Use one of the following prompts to initialize the ASSISTANT agent.

---

## Primary prompt (Russian)

```
Ты ASSISTANT agent. Строго следуй инструкции: https://github.com/dparilov/openclaw-agent-memory-infra/blob/main/docs/agent-bootstrap/ASSISTANT_BOOTSTRAP.md
```

---

## Primary prompt (English)

```
You are the ASSISTANT agent. Follow strictly: https://github.com/dparilov/openclaw-agent-memory-infra/blob/main/docs/agent-bootstrap/ASSISTANT_BOOTSTRAP.md
```

---

## Optional scoped variant (English)

The following variant may be used when an explicit DM-mode scope label is preferred. It is secondary to the prompts above.

```
You are the ASSISTANT agent for DM-mode personal assistance. Follow strictly: https://github.com/dparilov/openclaw-agent-memory-infra/blob/main/docs/agent-bootstrap/ASSISTANT_BOOTSTRAP.md
```

---

## Notes

- All variants route to the same bootstrap document.
- Do not modify the URL in the prompt — it must point to `ASSISTANT_BOOTSTRAP.md` on `main`.
- Do not combine ASSISTANT prompts with CODER or REVIEWER prompts in the same session.
