// background.js — Webull Stock Monitor (MV3 service worker)
// Responsibilities:
// - Receive messages from content.js
// - Proxy HTTP POSTs to local backend (avoids https->http mixed content)
// - Health checks / config
// - Future: alarms for periodic tasks

const DEFAULT_BACKEND = "http://127.0.0.1:8787";

let backendUrl = DEFAULT_BACKEND;

// === Dynamic action icon states ===
// gray = not on Webull, blue = on Webull (capture off), green = capture active
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
    if (!tab || !tab.url || !tab.url.includes("app.webull.com/stocks")) {
      await setExtensionIcon(tabId, "gray");
      return;
    }

    // On a Webull stocks page — ask the content script for capture state
    chrome.tabs.sendMessage(tabId, { type: "GET_CHART_STATUS" }, (resp) => {
      if (chrome.runtime.lastError || !resp) {
        // Content not ready or chart not loaded yet → blue (we are on webull)
        setExtensionIcon(tabId, "blue").catch(() => {});
        return;
      }
      const state = resp.enabled ? "green" : "blue";
      setExtensionIcon(tabId, state).catch(() => {});
    });
  } catch (e) {
    setExtensionIcon(tabId, "gray").catch(() => {});
  }
}

// Track last known states (helpful for quick decisions)
const tabCaptureState = new Map(); // tabId -> true/false

async function applyIconState(tabId, enabled) {
  if (!tabId) return;
  tabCaptureState.set(tabId, !!enabled);
  const state = enabled ? "green" : "blue";
  await setExtensionIcon(tabId, state);
}

chrome.runtime.onInstalled.addListener(() => {
  console.log("[stock-monitor] Extension installed/updated");
  // Load saved config if any
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
      version: "0.1.0",
    });
    return true;
  }

  if (message.type === "PING") {
    sendResponse({ status: "ok", version: "0.1.0" });
    return true;
  }

  if (message.type === "REPORT_ICON_STATE") {
    // Content script is telling us the capture state changed
    const tabId = sender.tab?.id;
    if (tabId != null) {
      const enabled = !!message.enabled;
      applyIconState(tabId, enabled).catch(() => {});
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
    sendResponse({ status: "ok", version: "0.1.0" });
  }
  return true;
});

// === Tab event listeners to keep icon in sync ===

chrome.tabs.onActivated.addListener(({ tabId }) => {
  // When user switches to a tab, immediately reflect correct icon
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
