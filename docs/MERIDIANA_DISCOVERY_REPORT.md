# MeridianA Discovery Report — PR #22 Pre-Implementation

> **⚠️ Historical document — superseded by PR #22 implementation.**  
> This report was the discovery phase before implementation began.  
> For current install instructions see [`docs/MERIDIANA_DEPENDENCY.md`](MERIDIANA_DEPENDENCY.md)  
> and [`scripts/install-meridiana.sh`](../scripts/install-meridiana.sh).

> Generated: 2026-04-30  
> Purpose: Identify the installable unit, document the current gap, and propose implementation options for reproducible MeridianA install.

---

## 1. What MeridianA Is

MeridianA is a **patched local proxy** that sits between OpenClaw/Claude Code agents and the Anthropic API, routing requests through a Claude Max subscription via OAuth. It is built on top of the public npm package **`@rynfar/meridian`** with OpenClaw-specific adapter patches applied.

```
Telegram → openclaw-gateway → Claude Code CLI → meridian proxy → Anthropic API (Claude Max OAuth)
```

The `meridiana/` prefix in OpenClaw agent configs (e.g. `meridiana/claude-opus-4-7`) refers to agents routed through this patched proxy instance, typically listening on port **3470**.

---

## 2. Component Map

| Component | Location | Visibility | Notes |
|-----------|----------|-----------|-------|
| Public npm base | `@rynfar/meridian` | **Public** (MIT) | npm v1.40.0 current; v1.30.2 is the base used locally |
| Upstream source | `github.com/AndrewArto/meridian-openclaw` | **Private** | Source of the npm package |
| Dmitri's patched fork | `github.com/dparilov/meridian-assistant` | **Private** | Contains all 6 local patches |
| Local working tree | `/home/dima/meridian-openclaw-arto` | local | Actively running; remote = `dparilov/meridian-assistant` |
| Runtime binary | `/home/dima/meridian-openclaw-arto/dist/cli.js` | local | Node.js >= 22 |
| Build tool | `bun` 1.3.12 | local | Required for `bun build` |

---

## 3. Local Patches Over Upstream

6 commits, **262 lines across 5 files**, all in `src/proxy/`:

| Commit | Title | Files |
|--------|-------|-------|
| `5ab4d72` | feat: inject billing header for Max subscription routing | `server.ts` |
| `6593248` | feat(openclaw): add SDK built-in tool mapping to OpenClaw equivalents | `openclaw.ts`, `adapter.ts` |
| `7db91fa` | feat(assistant): block SDK built-in tools that cause phantom loops | `openclaw.ts`, `server.ts` |
| `b5b4012` | fix(passthrough): increase maxTurns to 4/5 for long exec commands | `openclaw.ts` |
| `597c4fc` | Make OpenClaw path rewrite optional for exact paths | `openclaw.ts`, `query.ts` |
| `8ae0f04` | fix(non-passthrough): suppress duplicate responses from multi-turn SDK loop | `server.ts` |

**Patch volume by file:**

```
src/__tests__/openclaw-adapter.test.ts  | +19  lines
src/proxy/adapter.ts                    | +13  lines (interface extension)
src/proxy/adapters/openclaw.ts          | +157 lines (core OpenClaw adapter)
src/proxy/query.ts                      | +4   lines
src/proxy/server.ts                     | +80  lines
```

The `openclaw.ts` adapter is the critical piece: it implements the `openclawAdapter` that translates Claude SDK tool calls to OpenClaw-compatible calls and suppresses passthrough forwarding loops.

---

## 4. Model Aliases Used in This Environment

From `examples/olcRTC/environment-inventory.md`:

| Alias | Provider | Used by |
|-------|----------|---------|
| `meridian/claude-sonnet-4-6` | Meridian (unpatched) | `main`, `reviewer`, `alena` agents |
| `meridiana/claude-opus-4-7` | MeridianA (patched, port 3470) | `uae`, `tanya`, `andrey` agents |

---

## 5. Current Install Gap

A clean machine can install `@rynfar/meridian` from npm:

```bash
npm install -g @rynfar/meridian@1.30.2
```

But this produces the **unpatched** version. The 6 local patches are **only** in the private `dparilov/meridian-assistant` repo. Without them:

- `meridiana/` model aliases route through the proxy, but:
  - No OpenClaw SDK built-in tool mapping → phantom tool loops
  - No passthrough suppression → duplicate responses
  - No billing header → Max subscription not routed correctly
  - `Forwarding to client for execution` errors persist

**The gap:** no public, pinned, reproducible path from this infra repo to the working patched proxy.

---

## 6. Version Divergence

| | Version |
|---|---|
| Local working tree base | `@rynfar/meridian@1.30.2` |
| npm latest | `@rynfar/meridian@1.40.0` |
| Gap | ~10 minor versions (44 total published) |

The patches were written against 1.30.2. Whether they apply cleanly to 1.40.0 is unknown — requires a rebase test.

---

## 7. Implementation Options

### Option A — Vendor the patch as a diff file (recommended first step)

1. Extract `git diff upstream/main HEAD` from `meridian-openclaw-arto` → commit as `patches/meridiana-openclaw.patch` in this repo
2. Write `scripts/install-meridiana.sh`:
   ```bash
   npm pack @rynfar/meridian@1.30.2   # or clone source at pinned commit
   patch -p1 < patches/meridiana-openclaw.patch
   bun install && bun run build
   ```
3. Update `docs/FULL_ENVIRONMENT_ONBOARDING.md` section I
4. Update `docs/MERIDIANA_DEPENDENCY.md` with exact version pin

**Pros:** No private source in this repo. Patch is 262 lines of MIT-licensed diff.  
**Cons:** Patch may drift if upstream moves. Requires bun for rebuild.

### Option B — Make `dparilov/meridian-assistant` public

1. Owner changes repo visibility to public
2. Install script: `git clone github.com/dparilov/meridian-assistant && bun install && bun run build`
3. This repo documents the URL and pinned commit SHA

**Pros:** Simplest for users. Full source, full history.  
**Cons:** Requires owner action. Exposes fork history publicly.

### Option C — Rebase patches to latest npm version

1. Test if 6 patches apply to `@rynfar/meridian@1.40.0`
2. If yes: vendor against latest, avoiding version pinning to 1.30.2
3. If no: document conflicts and port manually

**Pros:** Stays on latest, benefits from upstream fixes.  
**Cons:** Requires manual rebase work. May need repeated updates.

### Option D — Publish patched fork to npm as `@dparilov/meridiana-openclaw`

1. Fork → publish as separate npm scoped package
2. Install: `npm install -g @dparilov/meridiana-openclaw`
3. Update OpenClaw config to point to this binary

**Pros:** Cleanest end-user experience.  
**Cons:** Requires npm publish setup. Another package to maintain.

---

## 8. Recommended Approach

**For PR #22:**

1. **Immediate:** Extract the patch and vendor it in this repo (Option A). Unblocks cold test.
2. **Follow-up:** Ask @pariloff whether `dparilov/meridian-assistant` can be made public (Option B). If yes, switch install script to `git clone`.
3. **Later:** Test patch rebase to 1.40.0 (Option C) for long-term maintainability.

---

## 9. Questions / Blockers for @pariloff

1. **Can `dparilov/meridian-assistant` be made public?** This simplifies everything — one `git clone` instead of patch + build.

2. **Patch against 1.30.2 or 1.40.0?** Should we pin to 1.30.2 (known working) or test rebase to 1.40.0 (latest)?

3. **Authentication on fresh machine:** How is Claude Max OAuth set up after install? Is there a `meridian auth` or `~/.meridian/` config that needs documenting?

4. **Port configuration:** Port 3470 for MeridianA instance — is this hardcoded or configured? Where is this set in OpenClaw's agent config?

5. **Licensing confirmation:** Vendoring the 262-line diff (MIT upstream) into this repo — confirm OK to commit.

---

## 10. Proposed PR #22 File List

```
patches/
  meridiana-openclaw.patch          # git diff of 6 local commits over upstream
scripts/
  install-meridiana.sh              # install + patch + build script
docs/
  MERIDIANA_DEPENDENCY.md           # update: add version pin, auth steps
  FULL_ENVIRONMENT_ONBOARDING.md   # update: section I with actual install steps
  MERIDIANA_DISCOVERY_REPORT.md    # this file → move to docs/archive/ after merge
```

---

*Pending @pariloff answers to section 9 before implementation begins.*
