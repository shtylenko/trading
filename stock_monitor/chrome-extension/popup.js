// popup.js — UI for the monitor extension

const $ = (id) => document.getElementById(id);

async function refresh() {
  const tab = await getTargetTab();
  if (!tab?.id || !tab.url || !tab.url.includes("app.webull.com/stocks")) {
    showNoWebullUI();
    return; // EARLY EXIT: literally no backend pings, no GET_STATUS, no health checks, no chart messaging
  }

  // === ONLY on valid app.webull.com/stocks tab from here on ===
  let backendUrl = "http://127.0.0.1:8787";
  try {
    const status = await chrome.runtime.sendMessage({ type: "GET_STATUS" });
    backendUrl = status?.backendUrl || backendUrl;
    $("backend").textContent = backendUrl;
  } catch (e) {
    $("backend").textContent = "—";
  }

  // Reveal webull-specific UI (including backend status)
  document.getElementById("backend-status").style.display = "";
  document.getElementById("webull-data").style.display = "";
  document.getElementById("webull-required").style.display = "none";
  document.getElementById("capture-section").style.display = "";

  chrome.tabs.sendMessage(tab.id, { type: "GET_CHART_STATUS" }, (resp) => {
    if (chrome.runtime.lastError || !resp) {
      console.log("[popup] GET_CHART_STATUS failed:", chrome.runtime.lastError);
      const err = chrome.runtime.lastError ? chrome.runtime.lastError.message : "";
      if (err.includes("invalidated") || err.includes("context")) {
        $("symbol").textContent = "reload the webull tab";
      } else {
        $("symbol").textContent = "no response (is the chart loaded?)";
      }
      $("tf").textContent = "—";
      $("buf").textContent = "—";
      $("last-received").textContent = "—";
      $("last-pushed").textContent = "—";
      $("tab-id").textContent = "—";
      updateCaptureUI(false);

      // We reached a webull tab but content didn't respond → treat as "on webull" (blue)
      try { chrome.runtime.sendMessage({ type: "SET_TAB_ICON", state: "blue" }); } catch (e) {}
      return;
    }

    $("symbol").textContent = resp.symbol || "—";
    $("tf").textContent = resp.timeframe || "—";

    const sizes = resp.bufferSizes || {};
    const totalBars = Object.values(sizes).reduce((a, b) => a + b, 0);
    const numSeries = Object.keys(sizes).length;
    $("buf").textContent = `${totalBars} bars / ${numSeries} series`;

    const now = Date.now();
    if (resp.lastDataTs) {
      const ago = Math.round((now - resp.lastDataTs) / 1000);
      $("last-received").textContent = `${ago}s ago`;
    } else {
      $("last-received").textContent = "—";
    }

    if (resp.lastPushedTs) {
      const ago = Math.round((now - resp.lastPushedTs) / 1000);
      $("last-pushed").textContent = `${ago}s ago`;
    } else {
      $("last-pushed").textContent = "—";
    }

    if (resp.tabId) {
      $("tab-id").textContent = resp.tabId;
    } else {
      $("tab-id").textContent = "—";
    }

    updateCaptureUI(!!resp.enabled);

    // Keep the toolbar icon in sync (blue = on webull, green = actively capturing)
    const iconState = resp.enabled ? "green" : "blue";
    try { chrome.runtime.sendMessage({ type: "SET_TAB_ICON", state: iconState }); } catch (e) {}
  });

  // Health check ONLY when we have a real Webull tab (status section is visible)
  try {
    const base = backendUrl.replace(/\/$/, "");
    let r = await fetch(`${base}/health`).catch(() => null);
    if (!r || !r.ok) r = await fetch(`${base}/api/health`).catch(() => null);
    const j = r ? await r.json().catch(() => ({})) : {};
    const el = $("conn");
    if (r && r.ok && (j.status === "ok" || j.ok)) {
      el.textContent = "connected";
      el.className = "status ok";
    } else {
      el.textContent = "backend issue";
      el.className = "status warn";
    }
  } catch (e) {
    const el = $("conn");
    el.textContent = "offline";
    el.className = "status err";
  }
}

function showNoWebullUI() {
  // Hide everything except the "Go to Webull" prompt. Zero status scanning / pings.
  document.getElementById("backend-status").style.display = "none";
  document.getElementById("webull-data").style.display = "none";
  document.getElementById("capture-section").style.display = "none";
  document.getElementById("webull-required").style.display = "";

  // Clear data fields (defensive)
  $("symbol").textContent = "—";
  $("tf").textContent = "—";
  $("buf").textContent = "—";
  $("last-received").textContent = "—";
  $("last-pushed").textContent = "—";
  $("tab-id").textContent = "—";

  // Reset conn indicator so it doesn't show stale "checking..." when re-opened elsewhere
  const connEl = $("conn");
  if (connEl) {
    connEl.textContent = "—";
    connEl.className = "status";
  }

  // Make sure the toolbar icon reflects "not on webull"
  try { chrome.runtime.sendMessage({ type: "SET_TAB_ICON", state: "gray" }); } catch (e) {}
}

function goToWebull() {
  chrome.tabs.create({ url: "https://app.webull.com/stocks" });
  window.close(); // close the popup
}

async function getTargetTab() {
  // Strictly use only the currently active tab.
  // If the active tab is not on app.webull.com/stocks, return null
  // so the popup shows the "Go to Webull" button instead of the capture UI.
  let [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (tab?.url && tab.url.includes("app.webull.com/stocks")) {
    return tab;
  }
  return null;
}

function updateCaptureUI(isEnabled) {
  const btn = $("toggle-capture");
  const state = $("capture-state");

  if (isEnabled) {
    btn.textContent = "Stop Capture";
    btn.style.background = "#450a0a";
    btn.style.borderColor = "#7f1d1d";
    state.textContent = "Capture active — closed candles sent automatically";
    state.style.color = "#86efac";
  } else {
    btn.textContent = "Start Capture";
    btn.style.background = "#14532d";
    btn.style.borderColor = "#166534";
    state.textContent = "Capture is OFF for this tab";
    state.style.color = "#888";
  }
}

async function toggleCapture() {
  console.log("[popup] Start/Stop Capture button clicked");

  const tab = await getTargetTab();
  if (!tab?.id || !tab.url || !tab.url.includes("app.webull.com/stocks")) {
    showNoWebullUI();
    return;
  }

  console.log("[popup] Targeting tab", tab.id, tab.url);

  // Determine desired state from current button text
  const currentlyOn = $("toggle-capture").textContent.includes("Stop");
  const newEnabled = !currentlyOn;

  // Optimistically update UI immediately
  updateCaptureUI(newEnabled);

  // Optimistically update the toolbar icon right away
  const targetIcon = newEnabled ? "green" : "blue";
  try { chrome.runtime.sendMessage({ type: "SET_TAB_ICON", state: targetIcon }); } catch (e) {}

  chrome.tabs.sendMessage(tab.id, { type: "SET_MONITORING", enabled: newEnabled }, (resp) => {
    if (chrome.runtime.lastError) {
      console.error("[popup] SET_MONITORING error:", chrome.runtime.lastError.message);
      updateCaptureUI(!newEnabled); // revert on error
      return;
    }
    console.log("[popup] SET_MONITORING response:", resp);

    if (newEnabled) {
      chrome.tabs.sendMessage(tab.id, { type: "FORCE_PUSH" }, (fpResp) => {
        if (chrome.runtime.lastError) {
          console.warn("[popup] FORCE_PUSH error:", chrome.runtime.lastError.message);
        } else {
          console.log("[popup] FORCE_PUSH done");
        }
      });
    }
    refresh(); // sync with actual state from content
  });
}



document.addEventListener("DOMContentLoaded", async () => {
  console.log("[popup] popup loaded");
  $("toggle-capture").addEventListener("click", toggleCapture);

  const goBtn = document.getElementById("go-to-webull");
  if (goBtn) {
    goBtn.addEventListener("click", goToWebull);
  }

  // Initial determination + paint (cheap early exit if not on stocks)
  const initialTab = await getTargetTab();
  await refresh();

  // Only start periodic refresh polling if we are currently on a webull stocks tab.
  // On any other page: no timers, no pings, almost no activity after the first check.
  if (initialTab?.id && initialTab.url && initialTab.url.includes("app.webull.com/stocks")) {
    setInterval(refresh, 1500);
  }
});
