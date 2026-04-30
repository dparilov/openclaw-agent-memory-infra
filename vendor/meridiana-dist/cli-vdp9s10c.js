import {
  getSetting,
  setSetting
} from "./cli-340h1chz.js";

// src/proxy/profiles.ts
import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { homedir } from "node:os";
var CONFIG_FILE = join(homedir(), ".config", "meridian", "profiles.json");
var DISK_CACHE_TTL_MS = 5000;
var diskProfilesCache = [];
var diskProfilesCacheAt = 0;
function loadProfilesFromDisk() {
  if (diskProfilesCacheAt > 0 && Date.now() - diskProfilesCacheAt < DISK_CACHE_TTL_MS) {
    return diskProfilesCache;
  }
  try {
    if (!existsSync(CONFIG_FILE)) {
      diskProfilesCache = [];
    } else {
      diskProfilesCache = JSON.parse(readFileSync(CONFIG_FILE, "utf-8"));
    }
    diskProfilesCacheAt = Date.now();
    return diskProfilesCache;
  } catch (err) {
    console.warn(`[meridian] Failed to read ${CONFIG_FILE}: ${err instanceof Error ? err.message : err}`);
    diskProfilesCacheAt = Date.now();
    diskProfilesCache = [];
    return [];
  }
}
var DEFAULT_PROFILE_ID = "default";
var activeProfileId;
function setActiveProfile(profileId) {
  activeProfileId = profileId;
  setSetting("activeProfile", profileId);
}
function getActiveProfileId() {
  return activeProfileId;
}
function resetActiveProfile() {
  activeProfileId = undefined;
}
function restoreActiveProfile(configProfiles) {
  if (activeProfileId)
    return;
  if (!diskDiscoveryEnabled)
    return;
  const saved = getSetting("activeProfile");
  if (!saved)
    return;
  const effective = getEffectiveProfiles(configProfiles);
  if (effective.length === 0 || effective.some((p) => p.id === saved)) {
    activeProfileId = saved;
  } else {
    console.warn(`[meridian] Saved active profile "${saved}" not found. Using default.`);
  }
}
var diskDiscoveryEnabled = false;
function enableDiskProfileDiscovery() {
  diskDiscoveryEnabled = true;
}
function getEffectiveProfiles(configProfiles) {
  const fromConfig = configProfiles ?? [];
  if (!diskDiscoveryEnabled)
    return fromConfig;
  const fromDisk = loadProfilesFromDisk();
  const configIds = new Set(fromConfig.map((p) => p.id));
  return [...fromConfig, ...fromDisk.filter((p) => !configIds.has(p.id))];
}
function hasProfiles(configProfiles) {
  return getEffectiveProfiles(configProfiles).length > 0;
}
function resolveProfile(profiles, defaultProfile, requestedId) {
  const effective = getEffectiveProfiles(profiles);
  if (effective.length === 0) {
    return { id: DEFAULT_PROFILE_ID, type: "claude-max", env: {} };
  }
  const resolvedId = requestedId || activeProfileId || defaultProfile || effective[0].id;
  const profile = effective.find((p) => p.id === resolvedId);
  if (!profile) {
    console.warn(`[meridian] Unknown profile "${resolvedId}". Using first configured profile.`);
    return buildResolvedProfile(effective[0]);
  }
  return buildResolvedProfile(profile);
}
function buildResolvedProfile(profile) {
  const type = profile.type ?? "claude-max";
  if (type === "api") {
    const env2 = {};
    if (profile.apiKey)
      env2.ANTHROPIC_API_KEY = profile.apiKey;
    if (profile.baseUrl)
      env2.ANTHROPIC_BASE_URL = profile.baseUrl;
    return { id: profile.id, type, env: env2 };
  }
  const env = {};
  if (profile.claudeConfigDir)
    env.CLAUDE_CONFIG_DIR = profile.claudeConfigDir;
  return { id: profile.id, type, env };
}
function listProfiles(profiles, defaultProfile) {
  const effective = getEffectiveProfiles(profiles);
  if (effective.length === 0)
    return [];
  const currentActive = activeProfileId || defaultProfile || effective[0].id;
  return effective.map((p) => ({
    id: p.id,
    type: p.type ?? "claude-max",
    isActive: p.id === currentActive
  }));
}

export { loadProfilesFromDisk, setActiveProfile, getActiveProfileId, resetActiveProfile, restoreActiveProfile, enableDiskProfileDiscovery, getEffectiveProfiles, hasProfiles, resolveProfile, listProfiles };
