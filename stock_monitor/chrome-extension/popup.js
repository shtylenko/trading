// popup.js — Mode-aware UI for chart + screener tabs

const $ = (id) => document.getElementById(id);

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

function isMonitorUrl(url) {
  return detectModeFromUrl(url) !== "other";
}

async function getTargetTab() {
  let [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (tab?.url && isMonitorUrl(tab.url)) {
    return tab;
  }
  return null;
}

function agoText(ts) {
  if (!ts) return "—";
  const ago = Math.round((Date.now() - ts) / 1000);
  return `${ago}s ago`;
}

function showOtherUI() {
  $("backend-status").style.display = "none";
  $("chart-data").style.display = "none";
  $("screener-data").style.display = "none";
  $("capture-section").style.display = "none";
  $("screener-hint").style.display = "none";
  $("webull-required").style.display = "";
  $("mode-badge").style.display = "none";

  const connEl = $("conn");
  if (connEl) {
    connEl.textContent = "—";
    connEl.className = "status";
  }
  try { chrome.runtime.sendMessage({ type: "SET_TAB_ICON", state: "gray" }); } catch (e) {}
}

function setModeBadge(mode) {
  const el = $("mode-badge");
  if (!mode || mode === "other") {
    el.style.display = "none";
    return;
  }
  el.style.display = "";
  el.textContent = mode === "screener" ? "screener" : "chart";
  el.style.background = mode === "screener" ? "#312e81" : "#1e3a5f";
  el.style.color = mode === "screener" ? "#c4b5fd" : "#93c5fd";
}

async function checkBackend(backendUrl) {
  try {
    const base = backendUrl.replace(/\/$/, "");
    let r = await fetch(`${base}/health`).catch(() => null);
    if (!r || !r.ok) r = await fetch(`${base}/api/health`).catch(() => null);
    const j = r ? await r.json().catch(() => ({})) : {};
    const el = $("conn");
    if (r && r.ok && (j.status === "ok" || j.ok)) {
      el.textContent = "connected";
      el.className = "status ok";
      return { ok: true, base, health: j };
    }
    el.textContent = "backend issue";
    el.className = "status warn";
    return { ok: false, base };
  } catch (e) {
    const el = $("conn");
    el.textContent = "offline";
    el.className = "status err";
    return { ok: false };
  }
}

async function fetchSessionToday(base) {
  try {
    const r = await fetch(`${base}/session/today`);
    if (!r.ok) return null;
    return await r.json();
  } catch {
    return null;
  }
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

async function refresh() {
  const tab = await getTargetTab();
  if (!tab?.id) {
    showOtherUI();
    return;
  }

  const urlMode = detectModeFromUrl(tab.url);

  let backendUrl = "http://127.0.0.1:8787";
  try {
    const status = await chrome.runtime.sendMessage({ type: "GET_STATUS" });
    backendUrl = status?.backendUrl || backendUrl;
    $("backend").textContent = backendUrl;
  } catch (e) {
    $("backend").textContent = "—";
  }

  $("backend-status").style.display = "";
  $("webull-required").style.display = "none";

  const backend = await checkBackend(backendUrl);

  chrome.tabs.sendMessage(tab.id, { type: "GET_PAGE_STATUS" }, async (resp) => {
    if (chrome.runtime.lastError || !resp) {
      console.log("[popup] GET_PAGE_STATUS failed:", chrome.runtime.lastError);
      const err = chrome.runtime.lastError ? chrome.runtime.lastError.message : "";
      // Fall back to URL-based mode shell
      if (urlMode === "screener") {
        showScreenerShell(null, backend);
      } else if (urlMode === "chart") {
        showChartShell(null, err);
      } else {
        showOtherUI();
      }
      try { chrome.runtime.sendMessage({ type: "SET_TAB_ICON", state: "blue" }); } catch (e) {}
      return;
    }

    const mode = resp.mode || urlMode;
    setModeBadge(mode);

    if (mode === "screener") {
      await showScreenerShell(resp, backend);
      const armed = !!(resp.screener?.armed);
      try {
        chrome.runtime.sendMessage({ type: "SET_TAB_ICON", state: armed ? "green" : "blue" });
      } catch (e) {}
    } else if (mode === "chart") {
      showChartShell(resp, null);
      const capturing = !!(resp.captureEnabled ?? resp.enabled);
      updateCaptureUI(capturing);
      const iconState = capturing ? "green" : "blue";
      try { chrome.runtime.sendMessage({ type: "SET_TAB_ICON", state: iconState }); } catch (e) {}
    } else {
      showOtherUI();
    }
  });
}

function showChartShell(resp, err) {
  $("chart-data").style.display = "";
  $("screener-data").style.display = "none";
  $("capture-section").style.display = "";
  $("screener-hint").style.display = "none";
  setModeBadge("chart");

  if (!resp) {
    $("symbol").textContent = err && (err.includes("invalidated") || err.includes("context"))
      ? "reload the webull tab"
      : "no response (is the chart loaded?)";
    $("tf").textContent = "—";
    $("buf").textContent = "—";
    $("last-received").textContent = "—";
    $("last-pushed").textContent = "—";
    $("tab-id").textContent = "—";
    updateCaptureUI(false);
    return;
  }

  $("symbol").textContent = resp.symbol || "—";
  $("tf").textContent = resp.timeframe || "—";

  const sizes = resp.bufferSizes || {};
  const totalBars = Object.values(sizes).reduce((a, b) => a + b, 0);
  const numSeries = Object.keys(sizes).length;
  $("buf").textContent = `${totalBars} bars / ${numSeries} series`;
  $("last-received").textContent = agoText(resp.lastDataTs);
  $("last-pushed").textContent = agoText(resp.lastPushedTs);
  $("tab-id").textContent = resp.tabId || "—";
}

async function showScreenerShell(resp, backend) {
  $("chart-data").style.display = "none";
  $("screener-data").style.display = "";
  $("capture-section").style.display = "none";
  $("screener-hint").style.display = "";
  setModeBadge("screener");

  const s = resp?.screener || {};
  const armed = !!s.armed;
  const stateEl = $("screener-state");
  if (armed) {
    stateEl.textContent = "YES — ingesting";
    stateEl.style.color = "#86efac";
  } else {
    stateEl.textContent = "NO — waiting";
    stateEl.style.color = "#fdba74";
  }

  $("screener-region").textContent = s.uiRegion || "—";
  $("screener-active").textContent = s.activeScreener?.name || "—";
  const configured = (s.configured || []).map((c) => c.name).join(", ");
  $("screener-configured").textContent = configured || "Gap'n'Go";
  $("screener-reason").textContent = s.armReason || "—";

  const diag = s.diagnostics || {};
  const diagParts = [
    diag.nameSelected
      ? `selected: ${(diag.selectedNames || diag.foundNames || []).join(", ") || "yes"}`
      : "selected: no",
    diag.nameFoundInPage
      ? `listed: ${(diag.foundNames || []).join(", ") || "?"}`
      : "listed: no",
    `region: ${diag.region || s.uiRegion || "?"}`,
    s.manual ? "manual arm" : "auto (select only)",
    s.droppedBatches != null ? `dropped: ${s.droppedBatches}` : null,
  ].filter(Boolean);
  $("screener-diag").textContent = diagParts.join(" · ");

  const armBtn = $("toggle-arm");
  if (armBtn) {
    if (armed) {
      armBtn.textContent = s.manual ? "Disarm" : "Disarm (override)";
      armBtn.style.background = "#450a0a";
      armBtn.style.borderColor = "#7f1d1d";
    } else {
      armBtn.textContent = "Arm Gap'n'Go";
      armBtn.style.background = "#1e3a5f";
      armBtn.style.borderColor = "#1d4ed8";
    }
  }

  $("screener-unique").textContent = s.uniqueTickers != null ? String(s.uniqueTickers) : "—";
  $("screener-batch").textContent = s.lastRowCount != null ? String(s.lastRowCount) : "—";
  $("screener-pushed").textContent = agoText(s.lastPushTs || resp?.lastPushedTs);

  const newTickers = s.lastResult?.new_tickers;
  $("screener-new").textContent = Array.isArray(newTickers)
    ? (newTickers.length ? newTickers.join(", ") : "none")
    : "—";

  const sample = s.sampleTickers || [];
  if (!armed) {
    $("screener-sample").textContent = "Open Gap'n'Go, or click Arm Gap'n'Go below";
  } else {
    $("screener-sample").textContent = sample.length
      ? sample.join(" · ")
      : "armed — waiting for result rows…";
  }

  // Session from last result or backend
  let sessionDate = s.lastResult?.session_date || "—";
  let sessionCount = "—";
  if (backend?.ok && backend.base) {
    const sess = await fetchSessionToday(backend.base);
    if (sess) {
      if (sess.session_date) sessionDate = sess.session_date;
      if (sess.ticker_count != null) sessionCount = String(sess.ticker_count);
      else if (Array.isArray(sess.tickers)) sessionCount = String(sess.tickers.length);
    }
  }
  $("session-date").textContent = sessionDate;
  $("session-count").textContent = sessionCount;
}

async function toggleArm() {
  const tab = await getTargetTab();
  if (!tab?.id || detectModeFromUrl(tab.url) !== "screener") return;

  // Read current button to decide arm vs disarm
  const btn = $("toggle-arm");
  const currentlyArmed = btn && btn.textContent.toLowerCase().includes("disarm");
  const payload = currentlyArmed
    ? { type: "SET_SCREENER_ARM", armed: false }
    : { type: "SET_SCREENER_ARM", armed: true, screener_key: "gap-n-go" };

  chrome.tabs.sendMessage(tab.id, payload, (resp) => {
    if (chrome.runtime.lastError) {
      console.error("[popup] SET_SCREENER_ARM error:", chrome.runtime.lastError.message);
      return;
    }
    console.log("[popup] arm response", resp);
    refresh();
  });
}

async function toggleCapture() {
  console.log("[popup] Start/Stop Capture button clicked");

  const tab = await getTargetTab();
  if (!tab?.id || detectModeFromUrl(tab.url) !== "chart") {
    showOtherUI();
    return;
  }

  const currentlyOn = $("toggle-capture").textContent.includes("Stop");
  const newEnabled = !currentlyOn;

  updateCaptureUI(newEnabled);
  const targetIcon = newEnabled ? "green" : "blue";
  try { chrome.runtime.sendMessage({ type: "SET_TAB_ICON", state: targetIcon }); } catch (e) {}

  chrome.tabs.sendMessage(tab.id, { type: "SET_MONITORING", enabled: newEnabled }, (resp) => {
    if (chrome.runtime.lastError) {
      console.error("[popup] SET_MONITORING error:", chrome.runtime.lastError.message);
      updateCaptureUI(!newEnabled);
      return;
    }
    if (newEnabled) {
      chrome.tabs.sendMessage(tab.id, { type: "FORCE_PUSH" }, () => {
        if (chrome.runtime.lastError) {
          console.warn("[popup] FORCE_PUSH error:", chrome.runtime.lastError.message);
        }
      });
    }
    refresh();
  });
}

function goToWebull() {
  chrome.tabs.create({ url: "https://app.webull.com/stocks" });
  window.close();
}

function goToScreener() {
  chrome.tabs.create({ url: "https://app.webull.com/screener" });
  window.close();
}

document.addEventListener("DOMContentLoaded", async () => {
  console.log("[popup] popup loaded");
  $("toggle-capture").addEventListener("click", toggleCapture);
  const armBtn = $("toggle-arm");
  if (armBtn) armBtn.addEventListener("click", toggleArm);

  const goBtn = $("go-to-webull");
  if (goBtn) goBtn.addEventListener("click", goToWebull);
  const goScr = $("go-to-screener");
  if (goScr) goScr.addEventListener("click", goToScreener);

  const initialTab = await getTargetTab();
  await refresh();

  if (initialTab?.id && isMonitorUrl(initialTab.url)) {
    setInterval(refresh, 1500);
  }
});
