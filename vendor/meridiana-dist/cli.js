#!/usr/bin/env node
import {
  startProxyServer
} from "./cli-d2we8gf4.js";
import"./cli-g9ypdz51.js";
import"./cli-rtab0qa6.js";
import"./cli-m9pfb7h9.js";
import"./cli-vdp9s10c.js";
import"./cli-340h1chz.js";
import {
  __require
} from "./cli-wckvcay0.js";

// bin/cli.ts
import { createRequire } from "module";
import { exec as execCallback } from "child_process";
import { promisify } from "util";
var require2 = createRequire(import.meta.url);
var { version } = require2("../package.json");
var args = process.argv.slice(2);
if (args.includes("--version") || args.includes("-v")) {
  console.log(version);
  process.exit(0);
}
if (args.includes("--help") || args.includes("-h")) {
  console.log(`meridian v${version}

Local Anthropic API powered by your Claude Max subscription.

Usage: meridian [command] [options]

Commands:
  (default)        Start the proxy server
  setup            Configure the OpenCode plugin (run once after install)
  profile          Manage Claude account profiles (add, list, switch, remove)
  refresh-token    Refresh the Claude Code OAuth token

Options:
  -v, --version   Show version
  -h, --help      Show this help

Environment variables:
  MERIDIAN_PORT                     Port to listen on (default: 3456)
  MERIDIAN_HOST                     Host to bind to (default: 127.0.0.1)
  MERIDIAN_PASSTHROUGH              Enable passthrough mode (tools forwarded to client)
  MERIDIAN_IDLE_TIMEOUT_SECONDS     Idle timeout in seconds (default: 120)

See https://github.com/rynfar/meridian for full documentation.`);
  process.exit(0);
}
if (args[0] === "profile") {
  const { profileAdd, profileList, profileRemove, profileSwitch, profileLogin, profileHelp } = await import("./profileCli-m5ns13d4.js");
  const subcommand = args[1];
  const profileId = args[2];
  if (subcommand === "add" && profileId)
    profileAdd(profileId);
  else if (subcommand === "list" || subcommand === "ls")
    profileList();
  else if (subcommand === "remove" && profileId)
    profileRemove(profileId);
  else if (subcommand === "switch" && profileId)
    await profileSwitch(profileId);
  else if (subcommand === "login" && profileId)
    profileLogin(profileId);
  else
    profileHelp();
  process.exit(0);
}
if (args[0] === "setup") {
  const { findPluginPath, runSetup } = await import("./setup-bv83qhyz.js");
  const pluginPath = findPluginPath(import.meta.url);
  const result = runSetup(pluginPath);
  if (result.alreadyConfigured) {
    console.log(`\x1B[32m✓ Meridian plugin already configured\x1B[0m`);
    console.log(`  ${result.configPath}`);
  } else {
    if (result.removedStale.length > 0) {
      console.log(`  Removed ${result.removedStale.length} stale plugin entr${result.removedStale.length === 1 ? "y" : "ies"}`);
    }
    console.log(`\x1B[32m✓ Meridian plugin configured\x1B[0m`);
    console.log(`  Config: ${result.configPath}`);
    console.log(`  Plugin: ${result.pluginPath}`);
    if (!result.created) {
      console.log(`
Restart OpenCode for the plugin to take effect.`);
    }
  }
  process.exit(0);
}
if (args[0] === "refresh-token") {
  const { refreshOAuthToken } = await import("./tokenRefresh-5et3wxt4.js");
  const success = await refreshOAuthToken();
  if (success) {
    console.log("Token refreshed successfully");
    process.exit(0);
  } else {
    console.error("Token refresh failed. If the problem persists, run: claude login");
    process.exit(1);
  }
}
var exec = promisify(execCallback);
process.on("uncaughtException", (err) => {
  console.error(`[PROXY] Uncaught exception (recovered): ${err.message}`);
});
process.on("unhandledRejection", (reason) => {
  console.error(`[PROXY] Unhandled rejection (recovered): ${reason instanceof Error ? reason.message : reason}`);
});
var port = parseInt(process.env.MERIDIAN_PORT ?? process.env.CLAUDE_PROXY_PORT ?? "3456", 10);
var host = process.env.MERIDIAN_HOST ?? process.env.CLAUDE_PROXY_HOST ?? "127.0.0.1";
var idleTimeoutSeconds = parseInt(process.env.MERIDIAN_IDLE_TIMEOUT_SECONDS ?? process.env.CLAUDE_PROXY_IDLE_TIMEOUT_SECONDS ?? "120", 10);
var profiles;
var defaultProfile;
try {
  const raw = process.env.MERIDIAN_PROFILES;
  if (raw) {
    profiles = JSON.parse(raw);
    defaultProfile = process.env.MERIDIAN_DEFAULT_PROFILE || undefined;
  }
} catch (e) {
  console.error(`[meridian] Failed to parse MERIDIAN_PROFILES: ${e instanceof Error ? e.message : e}`);
}
async function runCli(start = startProxyServer, runExec = exec) {
  try {
    const { findOpencodeConfigPath, checkPluginConfigured, findPluginPath } = await import("./setup-bv83qhyz.js");
    const configPath = findOpencodeConfigPath();
    const { existsSync } = await import("fs");
    if (existsSync(configPath) && !checkPluginConfigured(configPath)) {
      const pluginPath = findPluginPath(import.meta.url);
      console.error("\x1B[33m⚠ Meridian plugin not found in OpenCode config.\x1B[0m");
      console.error("  Session tracking and subagent model selection won't work.");
      console.error(`  Fix: meridian setup`);
      console.error("");
    }
  } catch {}
  try {
    const { stdout } = await runExec("claude auth status", { timeout: 5000 });
    const auth = JSON.parse(stdout);
    if (!auth.loggedIn) {
      console.error("\x1B[31m✗ Not logged in to Claude.\x1B[0m Run: claude login");
      process.exit(1);
    }
    if (auth.subscriptionType !== "max") {
      console.error(`\x1B[33m⚠ Claude subscription: ${auth.subscriptionType || "unknown"} (Max recommended)\x1B[0m`);
    }
  } catch {
    console.error("\x1B[33m⚠ Could not verify Claude auth status. If requests fail, run: claude login\x1B[0m");
  }
  if (!profiles) {
    const { enableDiskProfileDiscovery } = await import("./profiles-6wpje4q6.js");
    enableDiskProfileDiscovery();
  }
  const proxy = await start({ port, host, idleTimeoutSeconds, profiles, defaultProfile });
  proxy.server.on("error", (error) => {
    if (error.code === "EADDRINUSE") {
      process.exit(1);
    }
  });
}
if (__require.main == __require.module) {
  await runCli();
}
export {
  runCli
};
