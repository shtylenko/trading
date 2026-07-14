// background.js — Webull Stock Monitor (MV3 service worker)
// Responsibilities:
// - Receive messages from content.js
// - Proxy HTTP POSTs to local backend (avoids https->http mixed content)
// - Health checks / config
// - Icon state: gray / blue (on page, idle) / green (chart capture OR screener armed)

const DEFAULT_BACKEND = "http://127.0.0.1:8787";

let backendUrl = DEFAULT_BACKEND;

// === Dynamic action icon states ===
// gray  = not on Webull monitor page
// blue  = chart capture off OR screener open but not armed
// green = chart capture active OR screener armed (Gap'n'Go selected)
const ICON_PATHS = {
  gray: {
    16: "icons/icon-gray-16.png",
    32: "icons/icon-gray-32.png",
    128: "icons/icon-gray-128.png",
  },
  blue: {
    16: "icons/icon-blue-16.png",
    32: "icons/icon-blue-32.png",
    128: "icons/icon-blue-128.png",
  },
  green: {
    16: "icons/icon-green-16.png",
    32: "icons/icon-green-32.png",
    128: "icons/icon-green-128.png",
  },
};

function isWebullMonitorUrl(url) {
  if (!url || !url.includes("app.webull.com")) return false;
  try {
    const p = new URL(url).pathname.toLowerCase();
    return p.includes("/stocks") || p.includes("/screener") || p.includes("/quote");
  } catch {
    return url.includes("app.webull.com");
  }
}

function detectModeFromUrl(url) {
  if (!url) return "other";
  try {
    const p = new URL(url).pathname.toLowerCase();
    if (p.includes("/screener")) return "screener";
    if (p.includes("/stocks") || p.includes("/quote")) return "chart";
    return "other";
  } catch {
    return "other";
  }
}

async function setExtensionIcon(tabId, state) {
  const paths = ICON_PATHS[state] || ICON_PATHS.gray;
  try {
    await chrome.action.setIcon({ tabId, path: paths });
  } catch (e) {
    // Tab may have closed or other transient error
  }
}

async function setDefaultIcon(state = "gray") {
  const paths = ICON_PATHS[state] || ICON_PATHS.gray;
  try {
    await chrome.action.setIcon({ path: paths });
  } catch (e) {}
}

async function updateIconForTab(tabId) {
  try {
    const tab = await chrome.tabs.get(tabId);
    if (!tab || !isWebullMonitorUrl(tab.url)) {
      await setExtensionIcon(tabId, "gray");
      return;
    }

    const mode = detectModeFromUrl(tab.url);

    // Chart or screener — ask content script for active state
    chrome.tabs.sendMessage(tabId, { type: "GET_PAGE_STATUS" }, (resp) => {
      if (chrome.runtime.lastError || !resp) {
        setExtensionIcon(tabId, "blue").catch(() => {});
        return;
      }
      const state = iconStateFromStatus(resp, mode);
      setExtensionIcon(tabId, state).catch(() => {});
    });
  } catch (e) {
    setExtensionIcon(tabId, "gray").catch(() => {});
  }
}

function iconStateFromStatus(resp, urlMode) {
  const mode = resp?.mode || urlMode || "other";
  if (mode === "other") return "gray";
  if (mode === "chart") {
    return !!(resp.captureEnabled ?? resp.enabled) ? "green" : "blue";
  }
  if (mode === "screener") {
    // Green when Gap'n'Go (configured screener) is armed
    const armed = !!(resp.screener?.armed ?? resp.armed ?? resp.enabled);
    return armed ? "green" : "blue";
  }
  return "blue";
}

// Track last known states (helpful for quick decisions)
const tabCaptureState = new Map(); // tabId -> true/false

async function applyIconState(tabId, enabled, mode, armed) {
  if (!tabId) return;
  const isActive = mode === "screener" ? !!(armed ?? enabled) : !!enabled;
  tabCaptureState.set(tabId, isActive);
  let state = "blue";
  if (mode === "other") state = "gray";
  else if (mode === "chart" && enabled) state = "green";
  else if (mode === "screener" && (armed ?? enabled)) state = "green";
  else state = "blue"; // on page but idle
  await setExtensionIcon(tabId, state);
}

chrome.runtime.onInstalled.addListener(() => {
  console.log("[stock-monitor] Extension installed/updated");
  chrome.storage.local.get(["backendUrl"], (result) => {
    if (result.backendUrl) backendUrl = result.backendUrl;
  });
  setDefaultIcon("gray");
});

chrome.runtime.onStartup.addListener(() => {
  setDefaultIcon("gray");
});

chrome.storage.onChanged.addListener((changes) => {
  if (changes.backendUrl) {
    backendUrl = changes.backendUrl.newValue || DEFAULT_BACKEND;
  }
});

// Listen for messages from content script
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type === "PUSH_CANDLES") {
    console.log("[background] received PUSH_CANDLES for", message.payload?.symbol, message.payload?.timeframe);
    handlePushCandles(message.payload)
      .then((result) => {
        console.log("[background] backend accepted push");
        sendResponse({ ok: true, result });
      })
      .catch((err) => {
        console.error("[background] push failed:", err);
        sendResponse({ ok: false, error: String(err) });
      });
    return true; // async
  }

  if (message.type === "PUSH_SCREENER") {
    const n = message.payload?.rows?.length || 0;
    console.log("[background] received PUSH_SCREENER rows=", n);
    handlePushScreener(message.payload)
      .then((result) => {
        console.log("[background] screener accepted", result?.new_tickers);
        sendResponse({ ok: true, result });
      })
      .catch((err) => {
        console.error("[background] screener push failed:", err);
        sendResponse({ ok: false, error: String(err) });
      });
    return true;
  }

  if (message.type === "DUMP_DEBUG") {
    console.log("[background] received DOM debug dump");
    handleDebugDump(message.payload)
      .then((result) => sendResponse({ ok: true, result }))
      .catch((err) => sendResponse({ ok: false, error: String(err) }));
    return true;
  }

  if (message.type === "GET_STATUS") {
    sendResponse({
      backendUrl,
      version: "0.2.1",
    });
    return true;
  }

  if (message.type === "GET_SCREENER_CONFIG") {
    handleGetScreenerConfig()
      .then((config) => sendResponse({ ok: true, config }))
      .catch((err) => sendResponse({ ok: false, error: String(err) }));
    return true;
  }

  if (message.type === "PING") {
    sendResponse({ status: "ok", version: "0.2.1" });
    return true;
  }

  if (message.type === "REPORT_ICON_STATE") {
    const tabId = sender.tab?.id;
    if (tabId != null) {
      const enabled = !!message.enabled;
      const mode = message.mode || "chart";
      const armed = message.armed != null ? !!message.armed : enabled;
      applyIconState(tabId, enabled, mode, armed).catch(() => {});
    }
    sendResponse({ ok: true });
    return true;
  }

  if (message.type === "SET_TAB_ICON") {
    // Popup or other can force icon state for the *current active tab*
    const state = message.state; // "gray" | "blue" | "green"
    (async () => {
      try {
        const [active] = await chrome.tabs.query({ active: true, currentWindow: true });
        if (active?.id) {
          await setExtensionIcon(active.id, state);
        }
      } catch (e) {}
    })();
    sendResponse({ ok: true });
    return true;
  }
});

async function handlePushCandles(payload) {
  // Use /push to match the minimal receiver (receiver.py). It also accepts /api/candles as alias.
  const base = backendUrl.replace(/\/$/, "");
  let url = `${base}/push`;

  let resp = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!resp.ok && resp.status === 404) {
    // Fallback for old receiver or FastAPI skeleton
    url = `${base}/api/candles`;
    resp = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  }

  if (!resp.ok) {
    const text = await resp.text().catch(() => "");
    throw new Error(`Backend error ${resp.status}: ${text}`);
  }
  return resp.json();
}

async function handleGetScreenerConfig() {
  const base = backendUrl.replace(/\/$/, "");
  let url = `${base}/config/screeners`;
  let resp = await fetch(url);
  if (!resp.ok && resp.status === 404) {
    resp = await fetch(`${base}/api/config/screeners`);
  }
  if (!resp.ok) {
    const text = await resp.text().catch(() => "");
    throw new Error(`config error ${resp.status}: ${text}`);
  }
  return resp.json();
}

async function handlePushScreener(payload) {
  const base = backendUrl.replace(/\/$/, "");
  let url = `${base}/screener`;

  let resp = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!resp.ok && resp.status === 404) {
    url = `${base}/api/screener`;
    resp = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  }

  if (!resp.ok) {
    const text = await resp.text().catch(() => "");
    throw new Error(`Backend screener error ${resp.status}: ${text}`);
  }
  return resp.json();
}

async function handleDebugDump(payload) {
  const base = backendUrl.replace(/\/$/, "");
  const url = `${base}/debug/dom`;

  const resp = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!resp.ok) {
    const text = await resp.text().catch(() => "");
    throw new Error(`Debug backend error ${resp.status}: ${text}`);
  }
  return resp.json().catch(() => ({}));
}

// Optional: external message support (similar to metaia example)
chrome.runtime.onMessageExternal.addListener((message, sender, sendResponse) => {
  if (message.type === "PING") {
    sendResponse({ status: "ok", version: "0.2.1" });
  }
  return true;
});

// === Tab event listeners to keep icon in sync ===

chrome.tabs.onActivated.addListener(({ tabId }) => {
  updateIconForTab(tabId);
});

chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
  // URL change or load complete → re-evaluate (handles SPA navigation and new tabs)
  if (changeInfo.url || changeInfo.status === "complete") {
    updateIconForTab(tabId);
  }
});

chrome.tabs.onRemoved.addListener((tabId) => {
  tabCaptureState.delete(tabId);
});

// On extension load, try to set icon for the currently active tab
chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
  if (tabs[0]) {
    updateIconForTab(tabs[0].id);
  }
});
