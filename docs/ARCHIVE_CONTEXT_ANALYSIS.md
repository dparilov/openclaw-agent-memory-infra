# Archive Context Analysis

Date: 2026-04-26
Status: initial read-only analysis

## Objective

Understand the current `/archive-context` implementation and why it is not yet reliable enough as the foundation for project memory ingestion.

## Components

### Skill wrapper

Path: `/home/dima/.openclaw/workspace/skills/archive-context/SKILL.md`

Intended behavior:

- user invokes `/archive-context [topic]`;
- agent runs `archive-batch.py`;
- agent extracts facts from one batch;
- agent appends facts to `memory/topic-<topic>.md`;
- agent marks the batch done;
- agent prints mandatory archive stats.

### Claude command wrapper

Path: `/home/dima/.claude/commands/archive-context.md`

Similar intent, but command execution currently appears affected by native command / client-forwarding behavior in Telegram contexts.

### Batch script

Path: `/home/dima/.openclaw/workspace/ops/archive-batch.py`

Observed capabilities:

- finds OpenClaw transcript files by topic filename pattern `*-topic-<id>.jsonl` and `*.reset.*`;
- reads user/assistant transcript messages;
- emits one batch, default 100 messages;
- tracks progress in `/home/dima/.openclaw/workspace/ops/archive-progress-<topic>.json`;
- intended memory target: `/home/dima/.openclaw/workspace/memory/topic-<topic>.md`.

## Read-only Test: topic 7301

Commands run:

```bash
python3 /home/dima/.openclaw/workspace/ops/archive-batch.py 7301 --status
python3 /home/dima/.openclaw/workspace/ops/archive-batch.py 7301 --total
python3 /home/dima/.openclaw/workspace/ops/archive-batch.py 7301 --batch 0
```

Observed:

```text
Archive progress  [topic:7301]
  Batches done  : 0/105  (0%)
  Next batch    : 0

topic:7301  total_msgs:10469  batch_size:100  total_batches:105
```

No existing archive state was found:

```text
/home/dima/.openclaw/workspace/memory/topic-7301.md — missing
/home/dima/.openclaw/workspace/ops/archive-progress-7301.json — missing
```

Transcript files found for topic 7301: 13 files, including reset files from 2026-04-12 through 2026-04-26.

## Key Finding: Duplicate Messages

`archive-batch.py --batch 0` emitted repeated copies of the same initial Telegram message (`message_id: 7302`, “Привет”).

A quick duplicate scan found:

```text
files: 13
raw user/assistant transcript messages: 10469
telegram message ids found: 1216
duplicate telegram ids: 256
some ids appear 3 times
```

Likely cause:

- reset transcript files contain overlapping copied history;
- current dedupe key is `(basename, seq, ts_ms)`, so the same Telegram message repeated in different reset files is not deduplicated;
- chronological merge across reset files therefore inflates batch count and pollutes the first archive batches.

## Current Reliability Assessment

`archive-batch.py` is useful as a prototype, but not safe as the canonical archive ingestion engine yet.

Blocking issues before real archiving:

1. Cross-file deduplication is missing.
2. Batch counts are inflated by reset-file overlap.
3. Archive memory target is workspace-local, not portable.
4. Skill execution wrapper is unreliable in Telegram due native command / client-forwarding behavior.
5. LLM fact extraction from batches is not schema-validated.
6. `--reset` deletes progress and memory target; wrapper must require explicit approval before exposing it.

## Recommended Next Atomic Fix

Patch `archive-batch.py` or create a portable successor script with stable dedupe.

Minimal dedupe rule:

1. If a message contains trusted Telegram inbound metadata with `message_id`, dedupe by:

```text
telegram:<chat_id>:<topic_id>:<message_id>:<role>
```

2. Else dedupe by fallback content fingerprint:

```text
fallback:<role>:<timestamp bucket>:sha256(normalized text)
```

3. Report both raw and deduped counts in stats.

Acceptance check for topic 7301:

- batch 0 must not contain three copies of the same `message_id: 7302`;
- stats must show raw vs deduped messages;
- `--total` must be based on deduped messages;
- no archive write or mark-done happens during dry-run.

## Relationship to Infrastructure Project

This becomes part of Phase 1: Context Access Stabilization.

The memory pipeline must use a stable context-access layer before candidate extraction/promotion is implemented.

## Follow-up: `archive-batch-v2.py` Prototype

Created a safe successor script in the infra repo:

```text
scripts/context_access/archive-batch-v2.py
```

The original workspace prototype was not modified.

Initial dry-run on topic `7301`:

```text
Archive progress v2  [topic:7301]
  Batches done  : 0/71  (0%)
  Raw messages  : 10469
  Deduped msgs   : 7077
  Duplicates     : 3392
  Next batch    : 0
```

Validation checks:

- `python3 -m py_compile scripts/context_access/archive-batch-v2.py` passes.
- `message_id:7302` appears once in batch 0, not three times.
- empty assistant transcript records are skipped.
- total batches dropped from 105 raw batches to 71 deduped batches.
- status/total/batch dry-runs do not write archive memory or mark progress.

Remaining before production use:

- decide where portable progress files should live;
- add tests with tiny fixture transcripts;
- add a wrapper command/skill only after direct script behavior is stable;
- avoid `--mark-done` until archive writing policy is implemented.

## Execution Path Check — 2026-04-27

### Step 1: Current OpenClaw infra topic runtime

Command:

```bash
python3 /home/dima/projects/openclaw-agent-memory-infra/scripts/context_access/archive-batch-v2.py 7301 --status
```

Result: success.

```text
Archive progress v2  [topic:7301]
  Batches done  : 0/71  (0%)
  Raw messages  : 10469
  Deduped msgs   : 7077
  Duplicates     : 3392
  Next batch    : 0
  Progress file : /home/dima/.openclaw/workspace/ops/archive-progress-7301-v2.json
```

### Step 2: Host shell

User ran the same command manually on host shell. Result: success.

### Step 3: Telemost topic 7301 agent via exec tool

User requested the agent in topic 7301 to run the same command through exec tool. Result: success.

```text
Archive progress v2 [topic:7301]
 Batches done : 0/71 (0%)
 Raw messages : 10471
 Deduped msgs : 7078
 Duplicates : 3393
 Next batch : 0
 Progress file : /home/dima/.openclaw/workspace/ops/archive-progress-7301-v2.json
```

Interpretation:

- Direct script execution works in the problematic Telemost agent session.
- The remaining execution problem is likely in slash command / skill wrapper invocation, not in Python/path/permissions/tool availability.
- Counts changed slightly because new messages arrived in topic 7301 between checks; this is expected for live transcript state.

## Skill Wrapper Check — 2026-04-27

User asked the Telemost topic 7301 agent to run:

```text
/archive-context 7301 --status
```

Observed reply:

```text
I can't use the tool "skill" here because it isn't available. I need to stop retrying it and answer without that tool.
```

Additional read-only diagnostics:

- `exec` tool works in topic 7301.
- `archive-batch-v2.py` runs successfully through that exec path.
- The current session `skillsSnapshot` for topic 7301 contains only bundled OpenClaw skills:
  - `gh-issues`, `github`, `healthcheck`, `node-connect`, `skill-creator`, `taskflow`, `taskflow-inbox-triage`, `video-frames`, `weather`.
- It does **not** contain `archive-context`, `read-context`, or `read-topic`.
- `openclaw skills list` shows only OpenClaw-bundled skills as ready; local workspace directories under `~/.openclaw/workspace/skills/*` are not currently registered as eligible OpenClaw skills.

Interpretation:

- The failure is not Python/path/permission/tool execution.
- The immediate failure is that `archive-context` is not an eligible loaded OpenClaw skill in the agent prompt/snapshot.
- The agent then incorrectly attempts to call a nonexistent tool named `skill` and reports that the tool is unavailable.
- Therefore `/archive-context` must not depend on a non-existent skill tool. It needs either:
  1. a real OpenClaw-bundled/installed skill registration path, or
  2. a text-command/native-command route, or
  3. a documented explicit exec fallback.

## Local Skill Registration Finding — 2026-04-27

OpenClaw does discover workspace skills under:

```text
<workspace>/skills/*/SKILL.md
<workspace>/.agents/skills/*/SKILL.md
~/.openclaw/skills
~/.agents/skills
skills.load.extraDirs
plugin skill dirs
```

But the local skill loader requires valid frontmatter with at least:

```yaml
---
name: archive-context
description: ...
---
```

If `description` is missing, `loadSingleSkillDirectory()` returns null and the skill is silently absent from `openclaw skills list` and from session `skillsSnapshot`.

Applied minimal local workspace fix to:

```text
/home/dima/.openclaw/workspace/skills/archive-context/SKILL.md
```

Added frontmatter:

```yaml
---
name: archive-context
description: Incrementally archive OpenClaw topic/session context into memory markdown using batch scripts.
---
```

Verification:

```text
openclaw skills info archive-context
→ archive-context ✓ Ready
Source: openclaw-workspace

openclaw skills check
→ Total: 53
→ Eligible: 10
→ Ready includes archive-context
```

Important: existing sessions may still have old `skillsSnapshot` without `archive-context`. A new/reset session or skill snapshot refresh may be required before the topic 7301 agent sees it in `<available_skills>`.

## Post-registration Topic 7301 Test — 2026-04-27 00:58 MSK

After adding valid frontmatter to `archive-context`, Dmitrii reset/new-started topic 7301 and asked for `/archive-context 7301 --status`.

Observed from topic 7301 agent:

```text
Да, вижу archive-context в списке доступных skills. Загружаю SKILL.md.
Skill вернул "Forwarding to client for execution" ...
Все инструменты возвращают "Forwarding to client for execution" ...
```

Interpretation:

- Local skill registration issue is solved: `archive-context` is now visible in available skills for a new topic 7301 session.
- A second issue remains: the Meridian provider/session path in topic 7301 forwards tool calls to a client instead of executing them in the OpenClaw agent runtime.
- This affects at least Skill/read/bash-like tool execution in that session, even though direct `exec` had previously worked when explicitly requested.

Read-only session comparison:

```text
topic 7301:
  agent: main
  sessionId: 7ed97a97-ef05-4752-b83c-303a2abd1138
  modelProvider: meridian
  model: claude-sonnet-4-6
  skillsSnapshot includes archive-context: true

topic 15222:
  agent: main
  modelProvider: openai-codex
  model: gpt-5.5
  providerOverride: openai-codex
```

Working hypothesis:

- The remaining blocker is provider/runtime-specific: `meridian/claude-sonnet-4-6` topic session is going through a Meridian passthrough/client-forwarding execution mode.
- `archive-context` should therefore remain script-first and executable by explicit OpenClaw `exec`; skill wrapper must be tested under the same provider/runtime where it will be used.

Next atomic diagnostic options:

1. Switch topic 7301 temporarily to `openai-codex/gpt-5.5` and retry `/archive-context 7301 --status`.
2. Keep model as Meridian and inspect Meridian/MeridianA provider config for passthrough/client-forwarding mode.
3. Avoid skill wrapper for now and standardize explicit exec fallback.

## Codex Model Retest — 2026-04-27 01:01 MSK

After switching topic 7301 to Codex (`gpt55`) and starting a new session, `/archive-context 7301 --status` was tested again.

Observed reply:

```text
/archive-context 7301 --status read-only выполнен.

Archive file: memory/2026-04-27.md
Last archived: never
Messages since last archive: 3

Forwarding to client for execution не появлялось. Файлы не менял, архивирование не запускал.
```

Interpretation:

- Under Codex/OpenAI provider path, the wrapper no longer hits `Forwarding to client for execution`.
- This strongly supports the hypothesis that the forwarding issue is specific to the Meridian provider/session execution path, not Telegram topic routing, local skill discovery, or Python script permissions.
- However, the current `/archive-context` skill content is outdated: it reports daily-memory style status (`memory/2026-04-27.md`, messages since last archive 3) rather than the new `archive-batch-v2.py` topic archive status (`0/71`, raw/deduped counts).

Next needed fix:

- Update `~/.openclaw/workspace/skills/archive-context/SKILL.md` to use `archive-batch-v2.py` for `--status` and batch reads.
- The skill should be a thin wrapper over the script-first implementation in `/home/dima/projects/openclaw-agent-memory-infra/scripts/context_access/archive-batch-v2.py`.
- Then retest `/archive-context 7301 --status` under Codex and require the v2 stats block.

## Skill Wrapper Updated to v2 — 2026-04-27

Updated local workspace skill:

```text
/home/dima/.openclaw/workspace/skills/archive-context/SKILL.md
```

New behavior:

- Valid OpenClaw skill frontmatter retained.
- `--status` must run:

```bash
python3 /home/dima/projects/openclaw-agent-memory-infra/scripts/context_access/archive-batch-v2.py <topic> --status
```

- `--total` and `--batch N` are read-only script wrappers.
- Real archive/write mode is explicitly marked `[blocked]` until a stable writer contract exists.
- Skill documents known Meridian/MeridianA forwarding issue and explicit exec fallback.

Verification:

```text
openclaw skills info archive-context
→ archive-context ✓ Ready
Source: openclaw-workspace
```

Direct v2 status check after update:

```text
Archive progress v2  [topic:7301]
  Batches done  : 0/71  (0%)
  Raw messages  : 10488
  Deduped msgs   : 7091
  Duplicates     : 3397
  Next batch    : 0
  Progress file : /home/dima/.openclaw/workspace/ops/archive-progress-7301-v2.json
```

## Updated Skill Wrapper Retest — 2026-04-27 01:03 MSK

After updating `archive-context` to call `archive-batch-v2.py`, Dmitrii retested in topic 7301.

Observed reply:

```text
ARCHIVE-CONTEXT STATUS

Archive progress v2 [topic:7301]
 Batches done : 0/71 (0%)
 Raw messages : 10493
 Deduped msgs : 7094
 Duplicates : 3399
 Next batch : 0
 Progress file : /home/dima/.openclaw/workspace/ops/archive-progress-7301-v2.json

No files were modified.
```

Conclusion:

- On Codex/gpt55 execution path, `/archive-context 7301 --status` now works end-to-end as a read-only skill wrapper over `archive-batch-v2.py`.
- Counts continue to change slightly as new topic messages arrive; this is expected.
- Remaining known limitation: Meridian/MeridianA sessions can still hit `Forwarding to client for execution` and need separate provider/runtime diagnosis or explicit exec fallback.

## Total and Batch Preview Retest — 2026-04-27 01:06 MSK

Dmitrii retested read-only wrapper modes in topic 7301:

```text
/archive-context 7301 --total
/archive-context 7301 --batch 0
```

Observed:

```text
ARCHIVE-CONTEXT PREVIEW

Total

topic:7301 raw_msgs:10497 deduped_msgs:7096 duplicates:3401 batch_size:100 total_batches:71

Batch 0 preview

============================================================
ARCHIVE SOURCE STATS [topic:7301]
 Session files : 16
 Raw messages : 10497
 Duplicates : 3401
 Deduped msgs : 7096
 Batch size : 100
 Total batches : 71
============================================================
BATCH 0/70 [topic:7301]
 Messages : 0–99 (100 total, deduped index)
 From : 2026-04-12 08:58 UTC
 To : 2026-04-12 10:50 UTC
 Progress : 0/71 done before this batch
============================================================

[preview output continued through END BATCH 0/70 as produced by archive-batch-v2.py]

Файлы не менялись. --mark-done не запускался.
```

Conclusion:

- Read-only wrapper modes `--status`, `--total`, and `--batch 0` are working on Codex/gpt55 path.
- No progress was marked and no memory file was written.
- Read-only context access via `archive-context` can now be considered stable enough for the next design step: define a real archive writer contract.

Operational note:

- Context/archive tooling can run under Codex/OpenAI as an infra/control-plane model even if the main coding agent uses Opus/MeridianA. Prepared memory artifacts can then be consumed by other agents.

## Meridian/MeridianA Forwarding Root Cause — 2026-04-27

Read-only source/process inspection found:

- Both running Meridian processes use `MERIDIAN_DEFAULT_AGENT=openclaw`.
- `meridian-assistant` source adapter `src/proxy/adapters/openclaw.ts` contains:

```ts
usesPassthrough(): boolean {
  return true
}
```

- In `src/proxy/server.ts`, when `passthrough` is true, Meridian installs a `PreToolUse` hook matching all tools and returns:

```ts
return {
  decision: "block" as const,
  reason: "Forwarding to client for execution",
}
```

Running processes observed:

```text
PID 3038807: /home/dima/meridian-openclaw-arto/dist/cli.js
  MERIDIAN_PORT=3470
  MERIDIAN_DEFAULT_AGENT=openclaw
  MERIDIAN_BETA_POLICY=strip-all

PID 3038834: /home/dima/meridian-openclaw/dist/cli.js
  MERIDIAN_PORT=3469
  MERIDIAN_DEFAULT_AGENT=openclaw
  MERIDIAN_IDLE_TIMEOUT_SECONDS=3600
```

Interpretation:

- `Forwarding to client for execution` is the expected behavior of the hardcoded OpenClaw adapter passthrough mode.
- The next fix should be a controlled Meridian experiment, not another OpenClaw skill/config tweak.
- Candidate approaches:
  1. Patch `openclawAdapter.usesPassthrough()` to be env-controlled instead of hardcoded `true`.
  2. Run one Meridian instance with `openclaw` adapter internal/direct tool execution and test `/archive-context` there.
  3. Keep passthrough for coding workflows if needed and use Codex/OpenAI as control-plane fallback for context/archive tooling.

Risk:

- Changing passthrough behavior may affect normal OpenClaw/Meridian tool routing and coding workflows. Test on one Meridian instance first, preferably the non-primary/experimental one.

## MeridianA Env-Controlled Passthrough Patch — 2026-04-27

With Dmitrii approval, patched only the MeridianA working tree:

```text
/home/dima/meridian-openclaw-arto
```

Changed source:

```text
src/proxy/adapters/openclaw.ts
```

New behavior:

```ts
usesPassthrough(): boolean {
  const envVal = process.env.MERIDIAN_OPENCLAW_PASSTHROUGH
  if (envVal === "0" || envVal === "false" || envVal === "no") {
    return false
  }
  return true
}
```

Also patched the currently used built dist bundle:

```text
dist/cli-39bfednj.js
```

Safety:

- Default behavior remains unchanged (`passthrough=true`) unless `MERIDIAN_OPENCLAW_PASSTHROUGH=0|false|no` is set.
- No MeridianA restart was performed in this step.
- `node --check /home/dima/meridian-openclaw-arto/dist/cli-39bfednj.js` passed.

Next step:

- Restart only MeridianA (`port 3470`) with `MERIDIAN_OPENCLAW_PASSTHROUGH=0` and test `/archive-context 7301 --status` under a `meridiana/*` model.
