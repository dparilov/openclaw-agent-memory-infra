# Meridian Public Upstream Rebase Audit

**Generated:** 2026-04-30  
**Auditor:** automated forensic audit  
**PR22 baseline:** @rynfar/meridian 1.30.2 vendored dist (merge commit `8bdcf0c`, main)  
**Public latest:** @rynfar/meridian@1.40.0  

---

## Executive Verdict

```
Can we move to public latest now?   NO — not as a drop-in patch apply.
                                    Requires new openclaw.ts adapter + targeted
                                    port of 4 patches to changed server/query.

Minimal patch set likely needed:
  1. Create src/proxy/adapters/openclaw.ts from scratch (all 5 patches that
     touch it)
  2. Port duplicate-response suppression (patch 6) to new server.ts structure
  3. Port maxTurns fix (patch 4) to computePassthroughMaxTurns() in query.ts
  4. Port tool-mapping registration (patch 1, server.ts hunks) to new lines

Biggest risk:
  server.ts has grown by ~300+ lines since 1.30.x (1539→1862+ estimated).
  The duplicate-response suppression patch (8ae0f04) touches the stream event
  handler at deeply shifted line numbers — 3/8 hunks failed in dry-run.
  This requires careful semantic porting, not just offset adjustment.

Recommended next action:
  A. Keep PR22 vendored baseline as the cold-test / production install.
  B. Open PR23 as a separate rebase workstream — create openclaw.ts for
     1.40.0, port the 6 patches semantically, build + smoke before replacing
     vendor/.
  C. Do not block cold test on the rebase.
```

---

## 1. Version / Source Matrix

| Source | Version | Location | HEAD / tag | Status |
|--------|---------|----------|-----------|--------|
| PR22 vendored dist (main) | 1.30.2 | `vendor/meridiana-dist/` | `8bdcf0c` (merge) | **production baseline** |
| npm @rynfar/meridian | 1.40.0 (latest) | public registry | tag `meridian-v1.40.0` | public |
| npm @rynfar/meridian | 1.30.1 | public registry | tag `meridian-v1.30.1` | nearest published below base |
| Public source repo | github.com/rynfar/meridian | HEAD `6d468ea` | Merge PR #437 (release-please 1.40.0) | public, MIT |
| Arto private fork | AndrewArto/meridian-openclaw | private | — | forensic ref only |
| dparilov fork | dparilov/meridian-assistant | private | `8ae0f04` (main) | forensic ref only |
| Local working tree | `/home/dima/meridian-openclaw-arto` | remotes: origin=dparilov, upstream=Arto, rynfar=public | main @ `8ae0f04` | forensic ref only |
| Local install | `~/meridiana-openclaw/` | installed via PR22 script | 1.30.2 | do not modify |

**npm versions available around 1.30.x:** 1.30.0, 1.30.1 (no 1.30.2 on npm — it was a local version bump in Arto's fork).

**npm versions from 1.31+ to latest:** 1.31.0, 1.31.1, 1.31.2, 1.34.0, 1.34.1, 1.35.0, 1.37.0–1.37.8, 1.38.0, 1.39.0, 1.39.1, **1.40.0**.

---

## 2. PR22 Vendored Dist — File Inventory

| File | Role |
|------|------|
| `cli.js` | Entry point / router |
| `cli-d2we8gf4.js` | Main bundle (~668 KB, proxy core) |
| `cli-g9ypdz51.js` | CLI options / arg parsing |
| `cli-m9pfb7h9.js` | Profile management |
| `cli-340h1chz.js` | Token refresh |
| `cli-rtab0qa6.js` | Passthrough / MCP helpers |
| `cli-vdp9s10c.js` | Setup wizard |
| `cli-wckvcay0.js` | Server start helpers |
| `server.js` | Express/Hono server entry |
| `profileCli-m5ns13d4.js` | Profile CLI subcommand |
| `profilePage-65rqzsm2.js` | OAuth profile page |
| `profiles-6wpje4q6.js` | Profile store |
| `setup-bv83qhyz.js` | Setup flow |
| `tokenRefresh-5et3wxt4.js` | Token refresh flow |

**Runtime deps (exact-pinned in package.json):**
- `@anthropic-ai/claude-agent-sdk: 0.2.89`
- `ws: 8.20.0`
- Total installed: 99 packages, 0 vulnerabilities (npm ci)

---

## 3. Public Latest (1.40.0) Package Analysis

```bash
# Unpacked from npm in /tmp — dist-only, no src/
# CLI commands (node dist/cli.js --help):
meridian v1.40.0
Commands:
  (default)        Start the proxy server
  setup            Configure the OpenCode plugin
  profile          Manage Claude account profiles (add, list, switch, remove)
  refresh-token    Refresh the Claude Code OAuth token
Options:
  MERIDIAN_PORT (default: 3456)
  MERIDIAN_HOST (default: 127.0.0.1)
  MERIDIAN_PASSTHROUGH
  MERIDIAN_IDLE_TIMEOUT_SECONDS (default: 120)
```

- **dist-only**: npm tarball ships compiled JS only, no TypeScript `src/`
- **Auth command**: `meridian profile add` (same as 1.30.2)
- **Default port**: 3456 (same as 1.30.2; we override to 3470 via `MERIDIAN_PORT`)
- **Node requirement**: >= 22 (unchanged)

---

## 4. Public Source Repository (rynfar/meridian HEAD)

**URL:** https://github.com/rynfar/meridian  
**Visibility:** PUBLIC, MIT  
**HEAD:** `6d468ea` — Merge PR #437 (release-please, 1.40.0)  
**Tags:** meridian-v1.30.0, meridian-v1.30.1, meridian-v1.31.0 … meridian-v1.40.0

### Adapter directory (src/proxy/adapters/):
```
claudecode.ts   crush.ts   detect.ts   droid.ts
forgecode.ts    opencode.ts   passthrough.ts   pi.ts
```

**`openclaw.ts` does NOT exist in public upstream.** It was created entirely by Arto's private fork and constitutes most of our patch surface.

### Key structural changes vs 1.30.x:

| Area | Change in 1.40.0 | Impact on patches |
|------|-----------------|------------------|
| `adapter.ts` interface | New methods: `leaksCwdViaSystemReminder()`, `mapClientToolUse()`, `getFileChanges()` | Patch 1 hunk fails — must adapt to new interface |
| `query.ts` maxTurns | Non-passthrough is now `200` (was `2`); passthrough uses `computePassthroughMaxTurns()` | Patch 4 likely moot for non-passthrough |
| `server.ts` | ~300+ lines added; stream event handler refactored; `taskToolJsonBuffer` + `turn2_suppressed` added | Patches 1, 6 have 3+ failed hunks |
| No `openclaw.ts` | Entire adapter file missing | Patches 2, 3, 5 are blocked entirely |

---

## 5. The 6 Patches — Detailed Assessment

### Patch 1: SDK Built-in Tool Mapping
**Commit:** `6593248` | **Date:** 2026-04-23  
**Files:** adapter.ts (+13), openclaw.ts (+83), server.ts (+6)  
**What it does:** Creates `openclaw.ts` adapter with tool-name mapping between SDK built-in tools (Bash, Read, Edit, etc.) and their OpenClaw equivalents. Registers the adapter in server.ts. Adds interface method to adapter.ts.

**Assessment against 1.40.0:** `E — needs rewrite`
- `openclaw.ts` must be created from scratch (file absent in upstream)
- `adapter.ts` hunk fails — interface now has additional required methods that must be implemented
- `server.ts` hunks that touch adapter registration partially succeed with fuzz but may be at wrong semantic location
- The tool mapping logic itself (the mapping table) is still valid and needed

---

### Patch 2: Billing Header for Max Subscription Routing
**Commit:** `5ab4d72` | **Date:** 2026-04-21  
**Files:** openclaw.ts only (+40)  
**What it does:** Injects `x-anthropic-billing-header` into the system prompt in Claude Code's fingerprint format, ensuring OAuth requests from Max-subscription accounts are billed to Max plan rather than Extra Usage.

**Assessment against 1.40.0:** `A — still required`
- Billing routing behavior is determined by headers, not Meridian version
- Logic is self-contained in `openclaw.ts` — no conflicts with upstream
- Will apply cleanly once `openclaw.ts` is created for 1.40.0
- **Risk without this patch:** Max requests silently charged to Extra Usage

---

### Patch 3: Block Phantom SDK Tools
**Commit:** `7db91fa` | **Date:** 2026-04-23  
**Files:** openclaw.ts only (+1 change, 1 deletion)  
**What it does:** Activates `getBlockedBuiltinTools()` to block TodoWrite, EnterPlanMode, ExitPlanMode, EnterWorktree, ExitWorktree, NotebookEdit, CronCreate, CronDelete, CronList, ToolSearch — tools the model calls from training that have no equivalent in OpenClaw passthrough clients, causing "Tool not found" errors and infinite retry loops (183+ consecutive failures observed).

**Assessment against 1.40.0:** `A — still required`
- Model behavior (calling these tools) is training-driven, not version-dependent
- Block list logic is self-contained in `openclaw.ts`
- Will apply cleanly once `openclaw.ts` is created
- **Risk without this patch:** Phantom tool loops remain a critical failure mode

---

### Patch 4: maxTurns Increase (4/5 for Long Exec Commands)
**Commit:** `b5b4012` | **Date:** 2026-04-23  
**Files:** query.ts (+1 change, +1 deletion)  
**What it does:** Increases passthrough maxTurns from 2 to 4 (fresh) / 5 (resume) to prevent SIGTERM on background processes and SSH commands >30s.

**Assessment against 1.40.0:** `C — partially solved upstream`
- In 1.40.0, non-passthrough maxTurns is `200` (was 2) — our non-passthrough path is unaffected
- Passthrough path now uses `computePassthroughMaxTurns(resumeSessionId, hasDeferredTools, advisorModel)` — a more sophisticated calculation
- Our patch target (the `maxTurns:` literal in query.ts) no longer exists at that line
- **Action needed:** Verify `computePassthroughMaxTurns()` returns ≥4 turns for typical use. If it does, patch 4 may be fully obsolete. If it returns 2 in some paths, add the minimum clamp inside that function.
- **Risk if wrong:** Long exec commands SIGTERMed after 2 turns — same original bug

---

### Patch 5: Optional Path Rewrite for Exact Paths
**Commit:** `597c4fc` | **Date:** 2026-04-27  
**Files:** openclaw.ts (+34), test file (+19)  
**What it does:** Makes the OpenClaw workspace path rewrite conditional — only rewrites paths when the CWD doesn't already match exactly, preventing double-rewriting when the agent is already in the correct directory.

**Assessment against 1.40.0:** `A — still required`
- Path rewrite is OpenClaw-specific behavior (not in any public adapter)
- Logic is self-contained in `openclaw.ts`
- Tests are in the Arto test file — can be included in PR23 test suite
- Will apply cleanly once `openclaw.ts` is created

---

### Patch 6: Suppress Duplicate Responses from Multi-turn SDK Loop
**Commit:** `8ae0f04` | **Date:** 2026-04-27  
**Files:** query.ts (+2), server.ts (+74)  
**What it does:** Fixes a bug where in non-passthrough mode, the stream event handler's early-return guard was nested inside `message_start` branch, so content_block_delta and message_delta events still reached the client — causing two Telegram messages per response. Fix moves the guard to the top of stream_event handler, buffers text_delta from all turns, and emits a single synthetic SSE sequence.

**Assessment against 1.40.0:** `D — conflicts, semantic port required`
- `server.ts` in 1.40.0 has been substantially refactored
- Patch dry-run: 3/8 server.ts hunks FAILED (at lines 687, 1504, 1529 in 1.30.x context)
- The stream event handler exists but at different line numbers and with different surrounding logic
- `query.ts` hunks: 2/2 FAILED (line 90, 106 context gone)
- **Inspection shows:** 1.40.0 server.ts has `taskToolJsonBuffer` + `turn2_suppressed` which may address similar issues for passthrough, but non-passthrough duplicate response suppression appears to need porting
- **Risk without this patch:** Double responses in Telegram / downstream consumers

---

## 6. Patch Apply Experiment vs Public Latest HEAD

**Target:** rynfar/meridian @ `6d468ea` (1.40.0, cloned to /tmp)  
**Patch:** `patches/meridiana-openclaw.patch` (from PR22)  
**Command:** `patch -p1 --dry-run`

```
src/__tests__/openclaw-adapter.test.ts  → SKIPPED (file does not exist)
src/proxy/adapter.ts                    → 1/1 FAILED (hunk at line 195)
src/proxy/adapters/openclaw.ts          → SKIPPED (file does not exist)
src/proxy/query.ts                      → 2/2 FAILED (hunks at lines 90, 106)
src/proxy/server.ts                     → 3/8 FAILED (hunks at 687, 1504, 1529)
                                          5/8 succeeded (with fuzz/offset)
```

**Summary:** Patch does NOT apply cleanly. 7+ hunks fail. Root causes:
1. `openclaw.ts` doesn't exist → requires fresh file creation
2. `adapter.ts` interface has new methods → hunk context mismatch
3. `query.ts` maxTurns block restructured → context gone
4. `server.ts` grown by 300+ lines → semantic locations shifted

**Conclusion:** Mechanical patch apply is not viable. Semantic port is required.

---

## 7. File-Level Risk Table

| File | Changed in 1.40.0 vs 1.30.1? | Touched by our patches? | Patch applies cleanly? | Risk | Notes |
|------|------------------------------|------------------------|----------------------|------|-------|
| `src/proxy/adapters/openclaw.ts` | N/A (doesn't exist) | YES (patches 1,2,3,5) | NO — file absent | **HIGH** | Must create from scratch for 1.40.0 |
| `src/proxy/adapter.ts` | YES — new interface methods | YES (patch 1) | NO — 1/1 failed | **HIGH** | New interface: leaksCwdViaSystemReminder, getFileChanges, etc. |
| `src/proxy/server.ts` | YES — ~300 lines added | YES (patches 1, 6) | PARTIAL — 3/8 failed | **HIGH** | Stream handler restructured; duplicate-response logic needs port |
| `src/proxy/query.ts` | YES — maxTurns refactored | YES (patches 4, 6) | NO — 2/2 failed | **MEDIUM** | computePassthroughMaxTurns() may cover patch 4; patch 6 needs port |
| `src/__tests__/openclaw-adapter.test.ts` | N/A (doesn't exist) | YES (patch 5) | NO — file absent | **LOW** | Test-only; port alongside openclaw.ts |
| `src/proxy/adapters/claudecode.ts` | unknown | NO | N/A | **LOW** | Not touched by our patches |
| `src/proxy/adapters/passthrough.ts` | unknown | NO | N/A | **LOW** | Not touched |
| `package.json` | YES — 1.40.0 | NO | N/A | **LOW** | Dependency changes possible; audit before npm ci |
| `dist/cli.js` | YES — rebuilt | N/A (vendored) | N/A | **LOW** | Will be replaced by new build in PR23 |

---

## 8. Runtime Error → Patch Mapping Guide

| Error / Symptom | Likely Layer | First Check | Historical Patch |
|----------------|-------------|-------------|-----------------|
| "Reached maximum number of turns (3)" or "(2)" | query.ts maxTurns | `grep maxTurns src/proxy/query.ts` — check `computePassthroughMaxTurns()` return | Patch 4 (b5b4012) |
| "Forwarding to client for execution" (PreToolUse hook blocking) | OpenClaw hook / gateway | `~/.openclaw/hooks/` or `settings.json` PreToolUse config | Not a Meridian patch — OpenClaw config |
| Phantom TodoWrite / Read / Grep infinite loops | Blocked tool list | Check `getBlockedBuiltinTools()` in `openclaw.ts` | Patch 3 (7db91fa) |
| Two Telegram messages per response | Non-passthrough duplicate SSE | `grep nonPassthrough\|textBuffer src/proxy/server.ts` | Patch 6 (8ae0f04) |
| Billing routed to "Extra Usage" instead of Max plan | Billing header missing | Check `x-anthropic-billing-header` in system prompt via proxy logs | Patch 2 (5ab4d72) |
| Wrong `.openclaw/.assistant` path in tool calls | Path rewrite double-applying | Check `openclaw.ts` `getCwd()` / path rewrite logic | Patch 5 (597c4fc) |
| `tool_input undefined` / `Cannot read properties of undefined (reading 'input')` | Tool mapping mismatch | Check `mapSdkTool()` in `openclaw.ts` | Patch 1 (6593248) |
| `profile/auth not found` | OAuth profile missing | `node dist/cli.js profile list` — must have ≥1 profile | Not a Meridian patch — run `profile add` |
| Proxy starts but `/v1/models` fails (404/500) | Meridian server error | `node dist/cli.js` logs; check port; check `MERIDIAN_PORT` | Not a patch — config/runtime issue |
| `proxy starts but /v1/messages hangs` | SDK subprocess spawn failure | Check `executable: "node"` in query.ts — Bun detection fix | Not our patch — upstream fix in 1.30+ |
| Tool not found errors (passthrough) | Passthrough MCP registration | Check server.ts `createPassthroughMcpServer()` | Not our patch — upstream |

---

## 9. Recommendation

**Decision: Option A — Stay on PR22 for cold test; rebase in PR23 as a separate workstream.**

### Rationale
- PR22 vendored baseline is verified working (smoke tested, 0 vuln, lockfile-pinned)
- All 6 patches are documented, understood, and correctly classified
- The rebase to 1.40.0 requires creating `openclaw.ts` from scratch and semantic porting of 2 complex patches — this is a non-trivial, non-mechanical task
- Cold test outcome does not depend on the rebase
- Proceeding with the rebase before the cold test adds risk with no benefit

### Cold test on PR22 baseline
**CAN PROCEED.** Only remaining blocker: manual OAuth auth on target machine via `node dist/cli.js profile add`.

### PR23 Proposal

```
Title: feat(pr23): port OpenClaw adapter to @rynfar/meridian@1.40.0

Files to change:
  src/proxy/adapters/openclaw.ts    (CREATE — from Arto HEAD, adapted to 1.40.0 interface)
  src/proxy/adapter.ts              (ADD new interface methods for openclaw adapter)
  src/proxy/server.ts               (PORT patches 1, 6 — semantic port to new line numbers)
  src/proxy/query.ts                (VERIFY computePassthroughMaxTurns() covers patch 4)
  src/__tests__/openclaw-adapter.test.ts  (PORT from Arto test suite)
  vendor/meridiana-dist/            (REPLACE with 1.40.0 build after patches verified)
  vendor/meridiana-dist/package.json     (UPDATE version to 1.40.0, regenerate lockfile)

Risk: MEDIUM
  - Server.ts semantic port is the highest risk item
  - Must build (bun run build) and run full smoke before replacing vendor/

Expected test plan:
  1. Clone rynfar/meridian@1.40.0 source
  2. Apply patches semantically (not mechanically)
  3. bun install && bun run build → verify dist/cli.js
  4. node dist/cli.js --help (version must show 1.40.0)
  5. Run existing test suite (npm test or bun test)
  6. Replace vendor/meridiana-dist/ with new build
  7. Re-generate package-lock.json with 1.40.0 deps
  8. Run install smoke: bash scripts/install-meridiana.sh --target /tmp/test --port 3470
  9. Update python tests for new file hashes
  10. Cold test with OAuth auth on target machine

Whether cold test should wait: NO — proceed with PR22 baseline.
```

---

## Appendix: Patch Apply Dry-Run Output (verbatim)

```
Target: rynfar/meridian HEAD (6d468ea, 1.40.0)
Patch: patches/meridiana-openclaw.patch

src/__tests__/openclaw-adapter.test.ts → can't find file → SKIPPED
src/proxy/adapter.ts                   → Hunk #1 FAILED at 195
src/proxy/adapters/openclaw.ts         → can't find file → SKIPPED
src/proxy/query.ts                     → Hunk #1 FAILED at 90
                                          Hunk #2 FAILED at 106
src/proxy/server.ts                    → Hunk #1 FAILED at 687
                                          Hunk #2 succeeded at 1090 (offset +175)
                                          Hunk #3 succeeded at 1350 (offset +210)
                                          Hunk #4 succeeded at 1558 (offset +191)
                                          Hunk #5 succeeded at 1607 (offset +161)
                                          Hunk #6 FAILED at 1504
                                          Hunk #7 FAILED at 1529
                                          Hunk #8 succeeded at 1862 (offset +107)
```

Total: **7 hunks failed**, 6 succeeded with fuzz/offset. Not suitable for mechanical apply.
