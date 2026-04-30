// src/proxy/setup.ts
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "fs";
import { homedir, platform } from "os";
import { dirname, join } from "path";
import { fileURLToPath } from "url";
function findOpencodeConfigPath() {
  if (process.env.OPENCODE_CONFIG_DIR) {
    return join(process.env.OPENCODE_CONFIG_DIR, "opencode.json");
  }
  if (process.env.XDG_CONFIG_HOME) {
    return join(process.env.XDG_CONFIG_HOME, "opencode", "opencode.json");
  }
  if (platform() === "win32" && process.env.APPDATA) {
    return join(process.env.APPDATA, "opencode", "opencode.json");
  }
  return join(homedir(), ".config", "opencode", "opencode.json");
}
function findPluginPath(fromUrl) {
  const dir = dirname(fileURLToPath(fromUrl));
  return join(dir, "..", "plugin", "meridian.ts");
}
var STALE_PATTERNS = [
  "opencode-claude-max-proxy",
  "claude-max-headers",
  "meridian-agent-mode"
];
function isMeridianEntry(entry) {
  return STALE_PATTERNS.some((p) => entry.includes(p)) || entry.includes("meridian.ts") || entry.includes("@rynfar/meridian");
}
function checkPluginConfigured(configPath) {
  const path = configPath ?? findOpencodeConfigPath();
  if (!existsSync(path))
    return false;
  try {
    const raw = readFileSync(path, "utf-8");
    const config = JSON.parse(raw);
    const plugins = Array.isArray(config.plugin) ? config.plugin : [];
    return plugins.some((p) => typeof p === "string" && isMeridianEntry(p));
  } catch {
    return false;
  }
}
function runSetup(pluginPath, configPath) {
  const path = configPath ?? findOpencodeConfigPath();
  const dir = dirname(path);
  let config = {};
  let created = false;
  if (existsSync(path)) {
    try {
      config = JSON.parse(readFileSync(path, "utf-8"));
    } catch {}
  } else {
    created = true;
    if (!existsSync(dir))
      mkdirSync(dir, { recursive: true });
  }
  const existing = Array.isArray(config.plugin) ? config.plugin.filter((p) => typeof p === "string") : [];
  const removedStale = existing.filter(isMeridianEntry);
  const others = existing.filter((p) => !isMeridianEntry(p));
  const alreadyConfigured = removedStale.some((p) => p === pluginPath);
  config.plugin = [...others, pluginPath];
  writeFileSync(path, JSON.stringify(config, null, 2) + `
`, "utf-8");
  return { configPath: path, pluginPath, alreadyConfigured, removedStale, created };
}

export { findOpencodeConfigPath, findPluginPath, checkPluginConfigured, runSetup };
