# Cold Test Findings — 2026-04-30

Date: 2026-04-30
Operator: external ChatGPT cold-start walkthrough
Host: openclaw (Ubuntu 24.04)
OpenClaw: 2026.4.23 (a979721)

This document records factual findings from the first documented cold-start onboarding
test. It is not a blame document — it is a design input for the next iteration of the
setup flow.

---

## What Worked

All environment gates A–J passed or passed conditionally:
- OS baseline, packages, GitHub CLI, auth, repo clone: all clean
- OpenClaw install, Telegram, model providers: working
- MeridianA PR #22 install path worked cleanly — proxy on port 3470 confirmed
- Codex OAuth via OpenClaw-managed path: functional
- Topic planning (Gate J): three roles defined — infra, coder, reviewer

---

## Findings

### Finding 1 — Stale OpenClaw commands in docs

**What happened:** `docs/FULL_ENVIRONMENT_ONBOARDING.md` §F and §G referenced:
```
openclaw config telegram
openclaw config model list
openclaw config model test
```
These commands are not present in OpenClaw 2026.4.23.

**Impact:** Gates F and G still passed because the operator had already configured
Telegram and model providers. A true cold-start operator would encounter errors here.

**Working equivalents observed:**
```
openclaw channels status --probe
openclaw models status
openclaw models --help
```

**Recommendation:** Update §F and §G with version-aware instructions and `--help` fallback.

---

### Finding 2 — Infra agent handoff added too many round-trips

**What happened:** After Gate K, the flow entered `EXTERNAL_TO_INFRA_HANDOFF.md`.
This required: ORIENTATION REPORT → operator ACK → PREREQUISITES REPORT → operator ACK
→ TOPIC RESOLUTION REPORT → operator ACK → PROJECT INTAKE DRAFT → W1/W2/W3/W4 → SETUP
REPORT. Five stop-and-wait cycles before any useful work began.

**Impact:** Poor UX for standard new-environment setup. External GPT was capable of
driving setup further without requiring infra agent involvement at each step.

**Recommendation:** Demote infra handoff to fallback/escalation. Implement a wizard
flow (`docs/SETUP_WIZARD_FLOW.md`) as the primary path.

---

### Finding 3 — PR #24 opened in error: installer repo treated as target

**What happened:** The infra agent created `.agent/AGENT_CONTEXT.md` and
`.agent/memory/topic-15222.md` inside `openclaw-agent-memory-infra` and opened PR #24.

**Impact:** Wasted PR cycle. PR #24 was immediately closed (not merged). Main branch
was not affected.

**Root cause:** No explicit gate distinguishing installer repo from target project.
No rule preventing `.agent/` writes into the installer repo by default.

**Recommendation:** Add a mandatory Target Project Selection Gate before any writes.

---

### Finding 4 — Target Project Selection Gate was missing

**What happened:** The flow moved from topic planning (Gate J) directly to infra
handoff without explicitly asking: *which product repo is being onboarded?*

**Impact:** The installer repo became the de-facto target by proximity.

**Recommendation:** `docs/TARGET_PROJECT_SELECTION.md` must be a mandatory gate
before any scaffold or memory write.

---

### Finding 5 — Topic name case mismatch

**What happened:** Operator supplied `Telemost_Review`. Prior session history had
`Telemost_review`. Topic ID 13350 was the stable identifier.

**Impact:** Potential for missed topic resolution if code does exact-string matching.

**Recommendation:** Topic name matching must be case-insensitive and fuzzy.
Topic ID (integer) is the primary key; name is display label only.

---

### Finding 6 — Two-level workspace memory model not documented

**What happened:** The on-disk layout discovered empirically:
```
~/projects/telemost/.agent/memory/topic-7301.md    <- coder memory (local only)
~/projects/telemost/.agent/memory/topic-13350.md   <- reviewer memory (local only)
~/projects/telemost/olcRTC/.agent/                  <- product scaffold (committed)
```
This two-level pattern (workspace parent for topic memory; repo dir for scaffold)
was not documented anywhere.

**Impact:** The infra agent had to discover the layout by reading the filesystem.
New operators or wizards will not know where to write runtime memory files.

**Recommendation:** Document the two-level layout explicitly in `TARGET_PROJECT_SELECTION.md`
and `SETUP_WIZARD_FLOW.md`.

---

### Finding 7 — W1/W2/W3/W4 approval language not user-friendly

**What happened:** The PROJECT INTAKE DRAFT asked:
```
INTAKE APPROVED: W1=yes W2=yes W3=yes W4=<pr|direct>
```

**Impact:** Internal technical notation, not a user-facing choice. Unfamiliar operators
had to ask what each item meant.

**Recommendation:** Replace with outcome-oriented choices:
```
CONTINUE WITH PR      -- proceed, gate repo commits behind a PR
CONTINUE LOCAL ONLY   -- proceed, no repo commits
SHOW DETAILS          -- expand all proposed changes before proceeding
STOP                  -- pause; escalate to infra agent
```

---

### Finding 8 — Existing scaffold should be read before any write

**What happened:** `~/projects/telemost/olcRTC/.agent/` already existed with a full
scaffold. The infra agent correctly produced a SCAFFOLD REVIEW REPORT after an operator
reminder, but only after the operator said "verify path consistency first."

**Impact:** A less careful operator could trigger scaffold creation over an existing
scaffold, overwriting AGENT_CONTEXT.md.

**Recommendation:** Wizard must detect `.agent/` existence before any write.
If exists (populated): read-only review -> propose diff -> wait for approval.
If missing: propose creation.

---

### Finding 9 — config.yaml write/readback ambiguity

**What happened:** During `config.yaml` activation, the write tool reported
"Successfully edited" but `cat` readback showed the original commented-out content.
The step was not marked complete — it was flagged as ambiguous and sent back to the
operator for manual verification.

**Impact:** Trust in write operations reduced. Step could not be confirmed without
operator running `cat` manually.

**Recommendation:** After any config file write, the wizard must read back the file
and compare. If readback does not match proposed values: STOP and report. Do not
proceed on ambiguous write success.

---

### Finding 10 — Manual candidate migration too heavyweight for initial setup

**What happened:** The setup was stopped before reaching memory indexing. The previous
flow assumed manual L1 candidate extraction would be the first memory operation.

**Impact:** Setup cannot be considered complete without a memory baseline. Manual
candidate review of potentially hundreds of facts is not a practical setup step.

**Recommendation:** Use PR #20 automatic indexing (`initial-index.py`) as the default
for initial setup. Candidate promotion happens during real work sessions, not setup.

---

### Finding 11 — Codex standalone OAuth stale; OpenClaw-managed OAuth OK

**What happened:** `codex whoami` failed for standalone CLI. OpenClaw-managed
`openai-codex` OAuth was functional.

**Impact:** Low — standalone CLI was not in active use in any agent workflow.
Accepted as-is for cold test.

**Recommendation:** Gate H should distinguish the two paths. If only OpenClaw-managed
Codex OAuth is used, standalone CLI stale token is not a blocker.

---

### Finding 12 — Setup ended without a terminal deliverable

**What happened:** The session ended without ready-to-send agent instruction prompts.
The operator had to ask "what next?" at the end.

**Impact:** Operator cannot start agent work without knowing what to send to each
Telegram topic.

**Recommendation:** Every successful setup run must end with an Agent Instruction Pack:
three ready-to-paste prompts for infra, coder, and reviewer agents.

---

## Summary

| Finding | Severity | Status |
|---------|----------|--------|
| Stale OpenClaw commands | MEDIUM | Docs fix in this PR |
| Infra handoff too many round-trips | HIGH | Wizard flow in this PR |
| PR #24 installer repo treated as target | HIGH | Target gate in this PR |
| Target Project Selection Gate missing | HIGH | New doc in this PR |
| Topic name case mismatch | MEDIUM | Fuzzy matching documented in this PR |
| Two-level workspace not documented | MEDIUM | Documented in this PR |
| W1/W2/W3/W4 not user-friendly | MEDIUM | Wizard UX in this PR |
| Existing scaffold not read first | HIGH | Wizard phase 4 in this PR |
| config.yaml write/readback ambiguity | MEDIUM | Wizard phase 6 in this PR |
| Manual candidate migration heavyweight | MEDIUM | Auto-index default in this PR |
| Codex standalone OAuth stale | LOW | Documented; Gate H note |
| No terminal deliverable | HIGH | Instruction pack in this PR |
