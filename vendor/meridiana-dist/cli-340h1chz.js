// src/proxy/settings.ts
import { existsSync, readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { join, dirname } from "node:path";
import { homedir } from "node:os";
var SETTINGS_FILE = join(homedir(), ".config", "meridian", "settings.json");
function loadSettings() {
  try {
    if (!existsSync(SETTINGS_FILE))
      return {};
    return JSON.parse(readFileSync(SETTINGS_FILE, "utf-8"));
  } catch {
    return {};
  }
}
function saveSettings(updates) {
  const current = loadSettings();
  const merged = { ...current, ...updates };
  try {
    mkdirSync(dirname(SETTINGS_FILE), { recursive: true });
    writeFileSync(SETTINGS_FILE, JSON.stringify(merged, null, 2) + `
`, { mode: 384 });
  } catch (err) {
    console.warn(`[meridian] Failed to write ${SETTINGS_FILE}: ${err instanceof Error ? err.message : err}`);
  }
}
function getSetting(key) {
  return loadSettings()[key];
}
function setSetting(key, value) {
  saveSettings({ [key]: value });
}

export { getSetting, setSetting };
