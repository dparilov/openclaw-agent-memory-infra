// src/proxy/tokenRefresh.ts
import { execFile as execFileCb } from "child_process";
import { existsSync, readFileSync, writeFileSync } from "fs";
import { homedir, platform, userInfo } from "os";
import { promisify } from "util";

// src/logger.ts
import { AsyncLocalStorage } from "node:async_hooks";
var contextStore = new AsyncLocalStorage;
var shouldLog = () => process.env["OPENCODE_CLAUDE_PROVIDER_DEBUG"];
var shouldLogStreamDebug = () => process.env["OPENCODE_CLAUDE_PROVIDER_STREAM_DEBUG"];
var isVerboseStreamEvent = (event) => {
  return event.startsWith("stream.") || event === "response.empty_stream";
};
var REDACTED_KEYS = new Set([
  "authorization",
  "cookie",
  "x-api-key",
  "apiKey",
  "apikey",
  "prompt",
  "messages",
  "content"
]);
var sanitize = (value) => {
  if (value === null || value === undefined)
    return value;
  if (typeof value === "string") {
    if (value.length > 512) {
      return `${value.slice(0, 512)}... [truncated=${value.length}]`;
    }
    return value;
  }
  if (Array.isArray(value)) {
    return value.map(sanitize);
  }
  if (typeof value === "object") {
    const out = {};
    for (const [k, v] of Object.entries(value)) {
      if (REDACTED_KEYS.has(k)) {
        if (typeof v === "string") {
          out[k] = `[redacted len=${v.length}]`;
        } else if (Array.isArray(v)) {
          out[k] = `[redacted array len=${v.length}]`;
        } else {
          out[k] = "[redacted]";
        }
      } else {
        out[k] = sanitize(v);
      }
    }
    return out;
  }
  return value;
};
var withClaudeLogContext = (context, fn) => {
  return contextStore.run(context, fn);
};
var claudeLog = (event, extra) => {
  if (!shouldLog())
    return;
  if (isVerboseStreamEvent(event) && !shouldLogStreamDebug())
    return;
  const context = contextStore.getStore() || {};
  const payload = sanitize({ ts: new Date().toISOString(), event, ...context, ...extra || {} });
  console.debug(`[opencode-claude-code-provider] ${JSON.stringify(payload)}`);
};

// src/proxy/tokenRefresh.ts
var execFile = promisify(execFileCb);
var OAUTH_TOKEN_URL = "https://platform.claude.com/v1/oauth/token";
var OAUTH_CLIENT_ID = "9d1c250a-e61b-44d9-88ed-5944d1962f5e";
var KEYCHAIN_SERVICE = "Claude Code-credentials";
var CREDENTIALS_FILE = `${homedir()}/.claude/.credentials.json`;
function parseKeychainValue(raw) {
  const trimmed = raw.trim();
  try {
    return { credentials: JSON.parse(trimmed), wasHex: false };
  } catch {}
  try {
    const decoded = Buffer.from(trimmed, "hex").toString("utf-8");
    return { credentials: JSON.parse(decoded), wasHex: true };
  } catch {}
  return null;
}
var keychainWasHex = false;
var macosStore = {
  async read() {
    try {
      const { stdout } = await execFile("/usr/bin/security", ["find-generic-password", "-s", KEYCHAIN_SERVICE, "-a", userInfo().username, "-w"], { timeout: 5000 });
      const parsed = parseKeychainValue(stdout);
      if (!parsed)
        throw new Error("Could not parse keychain value as JSON or hex-encoded JSON");
      keychainWasHex = parsed.wasHex;
      return parsed.credentials;
    } catch (err) {
      claudeLog("token_refresh.keychain_read_failed", { error: String(err) });
      return null;
    }
  },
  async write(credentials) {
    const json = JSON.stringify(credentials, null, 2);
    const value = keychainWasHex ? Buffer.from(json).toString("hex") : json;
    try {
      await execFile("/usr/bin/security", ["add-generic-password", "-U", "-s", KEYCHAIN_SERVICE, "-a", userInfo().username, "-w", value], { timeout: 5000 });
      return true;
    } catch (err) {
      claudeLog("token_refresh.keychain_write_failed", { error: String(err) });
      return false;
    }
  }
};
var fileStore = {
  async read() {
    try {
      if (!existsSync(CREDENTIALS_FILE))
        return null;
      return JSON.parse(readFileSync(CREDENTIALS_FILE, "utf-8"));
    } catch (err) {
      claudeLog("token_refresh.file_read_failed", { error: String(err) });
      return null;
    }
  },
  async write(credentials) {
    try {
      writeFileSync(CREDENTIALS_FILE, JSON.stringify(credentials, null, 2), "utf-8");
      return true;
    } catch (err) {
      claudeLog("token_refresh.file_write_failed", { error: String(err) });
      return false;
    }
  }
};
function createPlatformCredentialStore() {
  return platform() === "darwin" ? macosStore : fileStore;
}
var inflightRefresh = null;
async function refreshOAuthToken(store) {
  if (inflightRefresh)
    return inflightRefresh;
  inflightRefresh = doRefresh(store ?? createPlatformCredentialStore()).finally(() => {
    inflightRefresh = null;
  });
  return inflightRefresh;
}
async function doRefresh(store) {
  const credentials = await store.read();
  if (!credentials) {
    claudeLog("token_refresh.no_credentials", {});
    return false;
  }
  const { refreshToken } = credentials.claudeAiOauth;
  if (!refreshToken) {
    claudeLog("token_refresh.no_refresh_token", {});
    return false;
  }
  let response;
  try {
    response = await fetch(OAUTH_TOKEN_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        grant_type: "refresh_token",
        client_id: OAUTH_CLIENT_ID,
        refresh_token: refreshToken
      }),
      signal: AbortSignal.timeout(15000)
    });
  } catch (err) {
    claudeLog("token_refresh.request_failed", { error: String(err) });
    return false;
  }
  if (!response.ok) {
    const body = await response.text().catch(() => "");
    claudeLog("token_refresh.bad_response", { status: response.status, body });
    return false;
  }
  let tokenData;
  try {
    tokenData = await response.json();
  } catch (err) {
    claudeLog("token_refresh.parse_failed", { error: String(err) });
    return false;
  }
  const now = Date.now();
  const expiresAt = tokenData.expires_at ?? (tokenData.expires_in ? now + tokenData.expires_in * 1000 : now + 8 * 60 * 60 * 1000);
  credentials.claudeAiOauth = {
    ...credentials.claudeAiOauth,
    accessToken: tokenData.access_token,
    refreshToken: tokenData.refresh_token ?? refreshToken,
    expiresAt
  };
  const written = await store.write(credentials);
  if (!written)
    return false;
  claudeLog("token_refresh.success", { expiresAt });
  return true;
}
function resetInflightRefresh() {
  inflightRefresh = null;
}

export { withClaudeLogContext, claudeLog, createPlatformCredentialStore, refreshOAuthToken, resetInflightRefresh };
