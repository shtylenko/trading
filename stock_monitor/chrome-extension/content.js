// content.js — Injected into app.webull.com pages (isolated world)
// - Injects inject.js into the PAGE world (MAIN)
// - Page modes:
//     chart    (/stocks, /quote)  — Start Capture → closed candles → /push
//     screener (/screener)        — ingest ONLY when a configured My Screener is selected
//     other                       — idle
// - Receives data via window.postMessage from inject.js

console.log("[stock-monitor] content script loaded on", location.href);

let pageMode = "other"; // "chart" | "screener" | "other"

// Named screener config (from backend /config/screeners, with local fallback)
let screenerConfig = {
  require_my_screeners: true,
  screeners: [
    {
      key: "gap-n-go",
      name: "Gap'n'Go",
      name_match: ["Gap'n'Go", "gap'n'go", "gap n go", "gapngo", "gap-n-go"],
      name_match_normalized: ["gapngo", "gapngo", "gapngo", "gapngo", "gapngo"],
      webull_screener_id: null,
      enabled: true,
    },
  ],
};
let screenerConfigLoadedAt = 0;

// Arm state: only true when My Screeners + a configured screener is selected
let screenerUiRegion = "unknown"; // "stock" | "my" | "unknown"
let activeScreener = null; // { key, name, webull_screener_id } | null
let screenerArmed = false;
let screenerArmReason = "not on screener page";
let lastArmLog = "";

function detectPageMode(url = location.href) {
  try {
    const p = new URL(url).pathname.toLowerCase();
    if (p.includes("/screener")) return "screener";
    if (p.includes("/stocks") || p.includes("/quote")) return "chart";
    return "other";
  } catch {
    return "other";
  }
}

function refreshPageMode() {
  const next = detectPageMode();
  if (next !== pageMode) {
    console.log("[stock-monitor] pageMode", pageMode, "→", next, location.href);
    pageMode = next;
    // Icon: chart capture green handled separately; screener/chart-off → blue via REPORT
    if (pageMode === "screener") {
      refreshScreenerArm();
      safeSendMessage({
        type: "REPORT_ICON_STATE",
        enabled: screenerArmed,
        mode: "screener",
        armed: screenerArmed,
      });
    } else if (pageMode === "chart") {
      safeSendMessage({ type: "REPORT_ICON_STATE", enabled: captureEnabled, mode: "chart" });
      screenerArmed = false;
      activeScreener = null;
      screenerArmReason = "not on screener page";
    } else {
      safeSendMessage({ type: "REPORT_ICON_STATE", enabled: false, mode: "other" });
      screenerArmed = false;
      activeScreener = null;
      screenerArmReason = "not on screener page";
    }
  } else {
    pageMode = next;
  }
  return pageMode;
}

function normalizeScreenerName(s) {
  return String(s || "")
    .toLowerCase()
    .replace(/[''']/g, "")
    .replace(/[\s\-_]+/g, "")
    .trim();
}

function matchConfiguredScreener(visibleName) {
  const norm = normalizeScreenerName(visibleName);
  if (!norm) return null;
  for (const s of screenerConfig.screeners || []) {
    const candidates = [s.name, ...(s.name_match || [])];
    for (const c of candidates) {
      const cn = normalizeScreenerName(c);
      if (!cn) continue;
      if (cn === norm) return { key: s.key, name: s.name, webull_screener_id: s.webull_screener_id || null };
      if (cn.length >= 5 && norm.length >= 5 && (cn.includes(norm) || norm.includes(cn))) {
        return { key: s.key, name: s.name, webull_screener_id: s.webull_screener_id || null };
      }
    }
  }
  return null;
}

function matchConfiguredByWebullId(id) {
  if (id == null || id === "") return null;
  const wid = String(id);
  for (const s of screenerConfig.screeners || []) {
    if (s.webull_screener_id != null && String(s.webull_screener_id) === wid) {
      return { key: s.key, name: s.name, webull_screener_id: s.webull_screener_id };
    }
  }
  return null;
}

function elementClassString(el) {
  if (!el) return "";
  const c = el.className;
  if (typeof c === "string") return c.toLowerCase();
  if (c && typeof c.baseVal === "string") return c.baseVal.toLowerCase();
  return String(c || "").toLowerCase();
}

function isElementVisiblySelected(el) {
  if (!el) return false;
  // Walk self + ancestors — Webull often puts active state on a parent row
  let cur = el;
  for (let depth = 0; depth < 6 && cur && cur !== document.body; depth++) {
    const cls = elementClassString(cur);
    const aria = (cur.getAttribute("aria-selected") || "").toLowerCase();
    const pressed = (cur.getAttribute("aria-pressed") || "").toLowerCase();
    const current = (cur.getAttribute("aria-current") || "").toLowerCase();
    const dataActive = cur.getAttribute("data-active") || cur.getAttribute("data-selected");
    if (aria === "true" || pressed === "true") return true;
    if (current === "true" || current === "page") return true;
    if (dataActive === "true" || dataActive === "1") return true;
    if (
      cls.includes("active") ||
      cls.includes("selected") ||
      cls.includes("current") ||
      cls.includes("checked") ||
      cls.includes("is-active") ||
      cls.includes("isactive") ||
      cls.includes("choosed") ||
      cls.includes("choose")
    ) {
      // Avoid matching global "Stock Screener" tab chrome only by class name noise
      return true;
    }
    cur = cur.parentElement;
  }
  return false;
}

/** True if element text is essentially just the screener name (not a long paragraph containing it). */
function textIsPrimarilyScreenerName(txt, matchedName) {
  const t = normalizeScreenerName(txt);
  const n = normalizeScreenerName(matchedName);
  if (!t || !n) return false;
  if (t === n) return true;
  // Allow short suffix/prefix (icons, counts) but not multi-name blobs
  if (t.includes(n) && t.length <= n.length + 8) return true;
  return false;
}

// Manual arm override from popup (persists until page leave / disarm)
let manualArmOverride = null; // null | { key, name, webull_screener_id }
let lastArmDiagnostics = {
  nameFoundInPage: false,
  nameSelected: false,
  foundNames: [],
  selectedNames: [],
  region: "unknown",
  bodySnippet: "",
};

function detectScreenerUiRegion() {
  // Prefer explicit tab labels on the page
  const labels = [];
  const candidates = document.querySelectorAll(
    'button, [role="tab"], a, div, span, li'
  );
  let stockHit = null;
  let myHit = null;
  for (const el of candidates) {
    // Prefer direct text of leaf-ish nodes (avoid huge containers)
    const txt = (el.childElementCount === 0
      ? (el.textContent || "")
      : (el.getAttribute("aria-label") || el.getAttribute("title") || "")
    ).replace(/\s+/g, " ").trim();
    if (!txt || txt.length > 40) continue;
    const lower = txt.toLowerCase();
    if (lower === "stock screener" || lower === "stocks screener") {
      stockHit = el;
      labels.push({ kind: "stock", el, selected: isElementVisiblySelected(el) });
    } else if (lower === "my screeners" || lower === "my screener") {
      myHit = el;
      labels.push({ kind: "my", el, selected: isElementVisiblySelected(el) });
    }
  }
  const stockSelected = labels.some((l) => l.kind === "stock" && l.selected);
  const mySelected = labels.some((l) => l.kind === "my" && l.selected);
  if (mySelected && !stockSelected) return "my";
  if (stockSelected && !mySelected) return "stock";
  try {
    const u = location.href.toLowerCase();
    if (u.includes("myscreener") || u.includes("my-screener") || u.includes("my_screener")) return "my";
  } catch (_) {}
  if (myHit && !stockSelected) return "my";
  if (myHit && stockHit) return "unknown";
  if (stockHit && stockSelected) return "stock";
  return "unknown";
}

/**
 * Find configured screener name nodes. We ONLY arm when one is *selected*
 * (or is clearly the open-screener title), not merely listed under My Screeners.
 */
function findConfiguredScreenerNodes() {
  const hits = [];
  const leaves = document.querySelectorAll(
    "span, div, a, li, button, p, h1, h2, h3, label, td, th"
  );
  for (const el of leaves) {
    if (el.childElementCount > 4) continue;
    const txt = (el.textContent || "").replace(/\s+/g, " ").trim();
    if (!txt || txt.length > 48) continue;
    const m = matchConfiguredScreener(txt);
    if (!m) continue;
    // Require the element text is basically the name (not a long block that merely mentions it)
    const primary = [m.name, ...(screenerConfig.screeners || [])
      .filter((s) => s.key === m.key)
      .flatMap((s) => s.name_match || [])];
    if (!primary.some((p) => textIsPrimarilyScreenerName(txt, p))) continue;
    const selected = isElementVisiblySelected(el);
    const tag = (el.tagName || "").toLowerCase();
    const isTitle =
      tag === "h1" || tag === "h2" || tag === "h3" ||
      elementClassString(el).includes("title") ||
      elementClassString(el.parentElement).includes("title") ||
      elementClassString(el).includes("header") ||
      elementClassString(el.parentElement).includes("header");
    hits.push({
      key: m.key,
      name: m.name,
      webull_screener_id: m.webull_screener_id || null,
      matchedAs: txt,
      selected,
      isTitle,
      el,
    });
  }
  return hits;
}

/**
 * Detect the open My Screener from selection / title only.
 * Listing Gap'n'Go in the sidebar without selecting it must NOT arm.
 */
function detectSelectedConfiguredScreener() {
  const hits = findConfiguredScreenerNodes();
  const listed = [];
  const selected = [];
  const titles = [];
  for (const h of hits) {
    if (!listed.includes(h.name)) listed.push(h.name);
    if (h.selected) {
      selected.push(h);
    }
    if (h.isTitle) {
      titles.push(h);
    }
  }

  // Prefer an explicitly selected list/row match
  if (selected.length > 0) {
    // If multiple, pick first (usually the active row)
    return {
      match: selected[0],
      via: "selected",
      listed,
      selectedNames: selected.map((s) => s.name),
      titleNames: titles.map((t) => t.name),
    };
  }

  // Open-screener title/header (results view) counts as selected for that name
  if (titles.length > 0) {
    return {
      match: titles[0],
      via: "title",
      listed,
      selectedNames: [],
      titleNames: titles.map((t) => t.name),
    };
  }

  return {
    match: null,
    via: null,
    listed,
    selectedNames: [],
    titleNames: [],
  };
}

function refreshScreenerArm() {
  if (pageMode !== "screener") {
    screenerArmed = false;
    activeScreener = null;
    screenerUiRegion = "unknown";
    screenerArmReason = "not on screener page";
    manualArmOverride = null;
    lastArmDiagnostics = {
      nameFoundInPage: false,
      nameSelected: false,
      foundNames: [],
      selectedNames: [],
      region: "unknown",
      bodySnippet: "",
    };
    return screenerArmed;
  }

  // Manual override from popup wins
  if (manualArmOverride) {
    activeScreener = manualArmOverride;
    screenerArmed = true;
    screenerUiRegion = detectScreenerUiRegion();
    screenerArmReason = `armed manually: ${manualArmOverride.name}`;
    lastArmDiagnostics = {
      nameFoundInPage: true,
      nameSelected: true,
      foundNames: [manualArmOverride.name],
      selectedNames: [manualArmOverride.name],
      region: screenerUiRegion,
      manual: true,
    };
    return true;
  }

  screenerUiRegion = detectScreenerUiRegion();
  const det = detectSelectedConfiguredScreener();
  const foundNames = det.listed || [];
  lastArmDiagnostics = {
    nameFoundInPage: foundNames.length > 0,
    nameSelected: !!det.match,
    foundNames,
    selectedNames: det.selectedNames || [],
    titleNames: det.titleNames || [],
    via: det.via,
    region: screenerUiRegion,
    bodySnippet: ((document.body && document.body.innerText) || "").slice(0, 200).replace(/\s+/g, " "),
  };

  if (screenerUiRegion === "stock") {
    screenerArmed = false;
    activeScreener = null;
    screenerArmReason = "Stock Screener tab — not monitored";
  } else if (det.match) {
    // ONLY arm when Gap'n'Go (or other configured name) is selected / is the open title
    activeScreener = {
      key: det.match.key,
      name: det.match.name,
      webull_screener_id: det.match.webull_screener_id || null,
    };
    screenerArmed = true;
    screenerArmReason = `armed: ${det.match.name} (${det.via})`;
  } else {
    screenerArmed = false;
    activeScreener = null;
    if (foundNames.length > 0) {
      screenerArmReason =
        `My Screeners list shows ${foundNames.join(", ")} but none is selected — click Gap'n'Go`;
    } else if (screenerUiRegion === "my") {
      screenerArmReason = "My Screeners open — select Gap'n'Go";
    } else {
      screenerArmReason = "select My Screeners → Gap'n'Go (or use Arm in popup)";
    }
  }

  const logLine = `${screenerArmed}|${screenerUiRegion}|${activeScreener?.key || "-"}|${screenerArmReason}`;
  if (logLine !== lastArmLog) {
    lastArmLog = logLine;
    console.log("[stock-monitor] screener arm:", {
      armed: screenerArmed,
      region: screenerUiRegion,
      active: activeScreener,
      reason: screenerArmReason,
      diag: lastArmDiagnostics,
    });
    // Green when armed, blue when on screener but not armed
    safeSendMessage({
      type: "REPORT_ICON_STATE",
      enabled: screenerArmed,
      mode: "screener",
      armed: screenerArmed,
    });
  }
  return screenerArmed;
}

async function loadScreenerConfig() {
  try {
    if (!chrome.runtime?.id) return;
    const resp = await chrome.runtime.sendMessage({ type: "GET_SCREENER_CONFIG" });
    if (resp?.ok && resp.config) {
      screenerConfig = {
        require_my_screeners: resp.config.require_my_screeners !== false,
        screeners: resp.config.screeners || screenerConfig.screeners,
      };
      screenerConfigLoadedAt = Date.now();
      console.log("[stock-monitor] screener config loaded", screenerConfig.screeners.map((s) => s.name));
      refreshScreenerArm();
    }
  } catch (e) {
    console.warn("[stock-monitor] screener config load failed, using fallback", e);
  }
}

let currentSymbol = null;
let currentTimeframe = null;
let buffer = new Map(); // key: `${symbol}:${tf}` -> array of candles
const MAX_BUFFER_CANDLES_PER_SERIES = 2500;
const ENABLE_PERIODIC_DOM_DEBUG = false;

// Closed-candle tracking (user rule: only fully closed candles, never the forming one)
let lastMaxTs = new Map();           // per key: highest t ever observed (the current "forming" or latest bar)
let lastAckedClosedTs = new Map();   // per key: highest ts acknowledged by backend
let pendingClosedTs = new Map();     // per key: timestamps currently in-flight to backend

let lastPushByKey = new Map();
const PUSH_THROTTLE_MS = 2500;       // a bit tighter for closed-candle events

let captureEnabled = false;  // single "Start Capture" toggle — when true we auto-push closed candles
let previousKey = null;          // to detect symbol or tf switches on this tab
let lastDataTs = null;           // for popup to show recent activity
let lastPushedTs = null;         // timestamp when we last initiated a push to backend

// Unique id for this tab's content script instance (to track which tab recorded what)
let myTabId = 'tab-' + Date.now() + '-' + Math.random().toString(36).substr(2, 9);

// tickerId (numeric from kdata) -> nice symbol (e.g. "GOOG")
const tickerIdToSymbol = new Map();

// Screener mode state (only when armed on a configured My Screener)
const screenerSeenTickers = new Set(); // unique tickers observed while armed this page session
let screenerLastPushTs = null;
let screenerLastResult = null; // last backend response summary
let screenerLastRowCount = 0;
let screenerDroppedBatches = 0;
const SCREENER_PUSH_THROTTLE_MS = 1500;
let lastScreenerPushAt = 0;
let pendingScreenerRows = null;
let screenerPushTimer = null;
let pendingScreenerMeta = null; // { screener_key, screener_name } for pending batch

function injectPageScript() {
  try {
    if (!chrome.runtime?.id) return; // context may be invalid
    const script = document.createElement("script");
    script.src = chrome.runtime.getURL("inject.js");
    script.type = "module";
    (document.head || document.documentElement).appendChild(script);
    script.onload = () => script.remove();
  } catch (e) {
    // Extension context may have been invalidated (e.g. reload during dev)
  }
}

injectPageScript();
loadScreenerConfig();
// Refresh config periodically (config file edits)
setInterval(() => loadScreenerConfig(), 60000);

function safeSendMessage(msg) {
  try {
    if (!chrome.runtime?.id) return; // Extension context invalidated (e.g. after reload)
    chrome.runtime.sendMessage(msg).catch(() => {});
  } catch (e) {
    // Swallow "Extension context invalidated" and similar
    if (!e.message || !e.message.includes('Extension context invalidated')) {
      console.warn('[stock-monitor] sendMessage error:', e);
    }
  }
}

// Listen for data coming from page-world inject script
window.addEventListener("message", (event) => {
  if (event.source !== window) return;
  const data = event.data;
  if (!data || data.source !== "webull-monitor-inject") return;

  refreshPageMode();

  if (data.type === "CANDLES_DETECTED") {
    if (pageMode !== "chart") {
      // Ignore candle traffic on screener/other pages
      return;
    }
    console.log("[stock-monitor] CANDLES_DETECTED from inject", {
      source: data.payload?.source,
      sym: data.payload?.symbol,
      tf: data.payload?.timeframe,
      count: data.payload?.candles?.length
    });
    handleCandlesDetected(data.payload);
  }

  if (data.type === "SCREENER_ROWS") {
    if (pageMode !== "screener") {
      return;
    }
    // Never auto-arm from network alone — another My Screener can also emit rows.
    // Arm only when Gap'n'Go is selected in the UI (or manual arm).
    refreshScreenerArm();
    handleScreenerRows(data.payload);
  }

  if (data.type === "RAW_POTENTIAL") {
    console.log("[stock-monitor] RAW_POTENTIAL from inject (possible candle data)", data.payload);
    // Forward raw for inspection in debug files
    safeSendMessage({
      type: "DUMP_DEBUG",
      payload: {
        reason: "raw_potential",
        url: location.href,
        timestamp: Date.now(),
        detected: { symbol: currentSymbol, timeframe: currentTimeframe, mode: pageMode },
        raw_from_inject: data.payload,
      },
    });
  }

  if (data.type === "DEBUG_JSON") {
    // Dump every JSON response we see (debug mode)
    safeSendMessage({
      type: "DUMP_DEBUG",
      payload: {
        reason: "raw_json",
        url: location.href,
        timestamp: Date.now(),
        detected: { symbol: currentSymbol, timeframe: currentTimeframe, mode: pageMode },
        raw_json: data.payload,
      },
    });
  }

  if (data.type === "TICKER_INFO") {
    const info = data.payload;
    if (info && info.tickerId && info.symbol) {
      tickerIdToSymbol.set(String(info.tickerId), info.symbol);
      console.log("[stock-monitor] ticker map update:", info.tickerId, "→", info.symbol);
      // If we are currently using the numeric id, switch to nice symbol immediately
      if (currentSymbol === String(info.tickerId)) {
        currentSymbol = info.symbol;
      }
    }
  }

  if (data.type === "RAW_LOG") {
    console.log("[stock-monitor][raw]", data.payload);
  }
});

function handleScreenerRows(payload) {
  const rows = payload?.rows;
  if (!Array.isArray(rows) || rows.length === 0) return;

  // Optional: bind/confirm via webull id from the request that produced these rows
  const reqId =
    payload?.request_screener_id ||
    payload?.screenerId ||
    payload?.context?.screenerId ||
    null;
  if (reqId) {
    const byId = matchConfiguredByWebullId(reqId);
    if (byId) {
      activeScreener = byId;
      screenerArmed = true;
      screenerArmReason = `armed via webull id ${reqId} (${byId.name})`;
    }
  }

  // Drop list-of-screeners-style payloads (names only, few quote fields) when not armed
  // and always drop when not armed on a configured selection.
  refreshScreenerArm();
  if (!screenerArmed || !activeScreener) {
    screenerDroppedBatches += 1;
    if (screenerDroppedBatches <= 5 || screenerDroppedBatches % 20 === 0) {
      console.log("[stock-monitor] dropped screener batch (not armed)", {
        rows: rows.length,
        reason: screenerArmReason,
        region: screenerUiRegion,
        request_screener_id: reqId,
      });
    }
    return;
  }

  // If config has a bound webull id, require request to match when present
  const boundId = activeScreener.webull_screener_id;
  if (boundId && reqId && String(reqId) !== String(boundId)) {
    screenerDroppedBatches += 1;
    console.log("[stock-monitor] dropped batch: request id mismatch", {
      boundId,
      reqId,
    });
    return;
  }

  // Resolve numeric-only tickers via map when possible
  const normalized = [];
  const batchSeen = new Set();
  for (const r of rows) {
    if (!r || typeof r !== "object") continue;
    let ticker = (r.ticker || r.symbol || "").toString().toUpperCase().trim();
    if (!ticker) continue;
    if (/^\d+$/.test(ticker) && tickerIdToSymbol.has(ticker)) {
      ticker = tickerIdToSymbol.get(ticker).toUpperCase();
    }
    // Skip rows that look like screener definitions rather than stocks
    if (matchConfiguredScreener(ticker) || matchConfiguredScreener(r.name || "")) {
      // name equals a screener name — not a stock
      continue;
    }
    if (batchSeen.has(ticker)) continue;
    batchSeen.add(ticker);
    screenerSeenTickers.add(ticker);
    normalized.push({
      ticker,
      ticker_id: r.tickerId || r.ticker_id || null,
      name: r.name || null,
      fields: r.fields || {},
      raw: r.raw || r,
    });
  }
  if (normalized.length === 0) return;

  screenerLastRowCount = normalized.length;
  lastDataTs = Date.now();
  pendingScreenerMeta = {
    screener_key: activeScreener.key,
    screener_name: activeScreener.name,
  };

  // Merge into pending batch (last write wins per ticker)
  if (!pendingScreenerRows) pendingScreenerRows = new Map();
  for (const r of normalized) {
    pendingScreenerRows.set(r.ticker, r);
  }

  const now = Date.now();
  const wait = Math.max(0, SCREENER_PUSH_THROTTLE_MS - (now - lastScreenerPushAt));
  if (screenerPushTimer) return;
  screenerPushTimer = setTimeout(() => {
    screenerPushTimer = null;
    flushScreenerPush();
  }, wait);
}

async function flushScreenerPush() {
  if (!pendingScreenerRows || pendingScreenerRows.size === 0) return;
  refreshScreenerArm();
  if (pageMode !== "screener" || !screenerArmed || !activeScreener) {
    pendingScreenerRows = null;
    pendingScreenerMeta = null;
    return;
  }
  const rows = Array.from(pendingScreenerRows.values());
  const meta = pendingScreenerMeta || {
    screener_key: activeScreener.key,
    screener_name: activeScreener.name,
  };
  pendingScreenerRows = null;
  pendingScreenerMeta = null;
  lastScreenerPushAt = Date.now();

  const payload = {
    captured_at: new Date().toISOString(),
    source_url: location.href,
    tab_id: myTabId,
    screener_key: meta.screener_key,
    screener_name: meta.screener_name,
    rows,
  };

  try {
    if (!chrome.runtime?.id) return;
    const resp = await chrome.runtime.sendMessage({
      type: "PUSH_SCREENER",
      payload,
    });
    if (resp?.ok) {
      screenerLastPushTs = Date.now();
      lastPushedTs = screenerLastPushTs;
      screenerLastResult = resp.result || null;
      console.log("[stock-monitor] screener push ok", {
        screener: meta.screener_name,
        rows: rows.length,
        new: resp.result?.new_tickers,
        session: resp.result?.session_date,
      });
    } else {
      console.warn("[stock-monitor] screener push failed", resp);
    }
  } catch (e) {
    if (!e.message || !e.message.includes("Extension context invalidated")) {
      console.warn("[stock-monitor] screener push error", e);
    }
  }
}

async function handleCandlesDetected(payload) {
  const incomingCount = payload?.candles?.length || 0;
  console.log("[stock-monitor] handleCandlesDetected called. captureEnabled=", captureEnabled, "incoming=", incomingCount, "tickerId/tf=", payload?.tickerId, payload?.timeframe);
  if (!payload || !Array.isArray(payload.candles) || payload.candles.length === 0) {
    return;
  }

  const { symbol: hintedSymbol, tickerId, timeframe: hintedTf, candles } = payload;

  // Prefer the tickerId that came with *this specific data batch* (important for SPA ticker switches)
  let symbol;
  if (tickerId) {
    const mapped = tickerIdToSymbol.get(String(tickerId));
    symbol = mapped || String(tickerId);
  } else if (hintedSymbol) {
    symbol = hintedSymbol;
  } else {
    symbol = await detectSymbol() || currentSymbol || "UNKNOWN";
  }
  symbol = symbol.toUpperCase();

  // Final map resolution in case we have a better mapping now
  if (/^\d+$/.test(symbol) && tickerIdToSymbol.has(symbol)) {
    symbol = tickerIdToSymbol.get(symbol).toUpperCase();
  }

  const tf = normalizeTf(hintedTf || await detectTimeframe() || currentTimeframe || "unknown");

  const key = `${symbol}:${tf}`;

  // Reset trackers if user switched symbol or timeframe on this tab
  if (previousKey && previousKey !== key) {
    // Keep old buffer around (in case they switch back), but reset closed tracking for the new view
    lastMaxTs.delete(key);
    lastAckedClosedTs.delete(key);
    pendingClosedTs.delete(key);
  }
  previousKey = key;

  currentSymbol = symbol;
  currentTimeframe = tf;

  if (!buffer.has(key)) buffer.set(key, []);

  const existing = buffer.get(key);
  const merged = mergeCandles(existing, candles);
  buffer.set(key, trimBuffer(merged));

  console.log("[stock-monitor] merged buffer for", key, "size=", buffer.get(key).length);
  lastDataTs = Date.now();

  // === CLOSED CANDLE LOGIC (only push fully closed candles) ===
  // We treat everything except the last bar (highest t) as closed.
  // This catches closes even if Webull sends updates in various ways.
  if (merged.length === 0) return;

  const sorted = [...merged].sort((a, b) => a.t - b.t);

  // All but the presumed current forming bar (last one)
  const safeClosed = sorted.length > 1 ? sorted.slice(0, -1) : [];
  const batchMaxTs = sorted[sorted.length - 1].t;
  const prevMax = lastMaxTs.get(key) || -1;
  lastMaxTs.set(key, Math.max(prevMax, batchMaxTs));

  if (!captureEnabled) {
    console.log("[stock-monitor] buffered data while capture OFF for", key);
    return;
  }
  console.log("[stock-monitor] data received while capture ON for", currentSymbol, currentTimeframe);

  scheduleClosedPush(symbol, tf, safeClosed, "auto");
}

function scheduleClosedPush(symbol, tf, safeClosed, reason = "auto", { ignoreThrottle = false, includeAcked = false } = {}) {
  const key = `${symbol}:${tf}`;
  const prevAcked = includeAcked ? -1 : (lastAckedClosedTs.get(key) || -1);
  const pending = pendingClosedTs.get(key) || new Set();
  const toPush = safeClosed.filter(c => c.t > prevAcked && !pending.has(c.t));

  console.log("[stock-monitor] closed check:", {
    key,
    totalClosed: safeClosed.length,
    toPush: toPush.length,
    prevAcked,
    pending: pending.size,
    reason,
  });

  if (toPush.length === 0) return;

  const now = Date.now();
  const lastPush = lastPushByKey.get(key) || 0;
  if (!ignoreThrottle && now - lastPush <= PUSH_THROTTLE_MS) {
    console.log("[stock-monitor] newly closed found but throttled; will retry on next data/status event");
    return;
  }

  lastPushByKey.set(key, now);
  for (const c of toPush) pending.add(c.t);
  pendingClosedTs.set(key, pending);
  console.log(`[stock-monitor] pushing ${toPush.length} closed candle(s) for ${symbol} ${tf} (${reason})`);
  pushToBackend(symbol, tf, toPush);
}

function mergeCandles(existing, incoming) {
  const map = new Map(existing.map(c => [c.t, c]));
  for (const c of incoming) {
    if (!c || !Number.isFinite(Number(c.t))) continue;
    const t = Number(c.t);
    // Keep latest values for the current forming bar (we still buffer it so FORCE_PUSH or
    // future "include latest" can use it). We just never auto-push the highest-t bar.
    const prev = map.get(t);
    if (prev) {
      map.set(t, {
        t,
        o: prev.o,
        h: Math.max(prev.h, c.h || prev.h),
        l: Math.min(prev.l, c.l || prev.l),
        c: c.c ?? prev.c,
        v: c.v ?? prev.v,
      });
    } else {
      map.set(t, { ...c, t });
    }
  }
  return Array.from(map.values()).sort((a, b) => a.t - b.t);
}

function trimBuffer(candles) {
  if (candles.length <= MAX_BUFFER_CANDLES_PER_SERIES) return candles;
  return candles.slice(candles.length - MAX_BUFFER_CANDLES_PER_SERIES);
}

async function pushToBackend(symbol, timeframe, candles) {
  const key = `${symbol.toUpperCase()}:${timeframe}`;
  const payload = {
    symbol: symbol.toUpperCase(),
    timeframe,
    captured_at: new Date().toISOString(),
    candles,
    tab_id: myTabId,
  };

  try {
    if (!chrome.runtime?.id) return;
    const resp = await chrome.runtime.sendMessage({
      type: "PUSH_CANDLES",
      payload,
    });
    if (!resp?.ok) {
      console.warn("[stock-monitor] push to background failed", resp);
    } else {
      const maxTs = Math.max(...candles.map(c => c.t));
      const prevAcked = lastAckedClosedTs.get(key) || -1;
      lastAckedClosedTs.set(key, Math.max(prevAcked, maxTs));
      lastPushedTs = Date.now();
      console.log(`[stock-monitor] successfully sent ${candles.length} closed candle(s) for ${symbol} ${timeframe}`);
    }
  } catch (e) {
    if (!e.message || !e.message.includes('Extension context invalidated')) {
      console.warn("[stock-monitor] push error to background", e);
    }
  } finally {
    const pending = pendingClosedTs.get(key);
    if (pending) {
      for (const c of candles) pending.delete(c.t);
      if (pending.size === 0) pendingClosedTs.delete(key);
    }
  }
}

// --- DOM Debug Dumper (for verifying we are looking at the right page structure) ---

async function captureDomDebug(reason = "manual") {
  const debug = {
    reason,
    url: location.href,
    title: document.title,
    timestamp: Date.now(),
    detected: {
      symbol: currentSymbol,
      timeframe: currentTimeframe,
      captureEnabled,
    },
    interesting_elements: [],
    canvases: [],
    price_like_texts: [],
  };

  // Find likely chart containers and canvases
  const chartSelectors = [
    'canvas',
    '[class*="chart"]',
    '[class*="kline"]',
    '[class*="candle"]',
    '[id*="chart"]',
    '[class*="price"]',
    'div[style*="canvas"]',
  ];

  const seen = new Set();
  chartSelectors.forEach(sel => {
    try {
      document.querySelectorAll(sel).forEach(el => {
        if (seen.has(el)) return;
        seen.add(el);

        if (el.tagName === 'CANVAS') {
          debug.canvases.push({
            width: el.width,
            height: el.height,
            class: el.className,
            id: el.id,
            parent_class: el.parentElement?.className || '',
          });
        } else {
          const html = (el.outerHTML || '').substring(0, 600);
          debug.interesting_elements.push({
            selector: sel,
            tag: el.tagName,
            class: el.className,
            id: el.id,
            text: (el.textContent || '').trim().substring(0, 120),
            html_snippet: html,
          });
        }
      });
    } catch (e) {}
  });

  // Collect text nodes that look like prices or OHLC labels
  const priceRegex = /[\d,.]+\s*(O|H|L|C|Open|High|Low|Close|Vol)?/i;
  const allText = document.body ? document.body.innerText.split('\n') : [];
  allText.slice(0, 50).forEach(line => {
    const trimmed = line.trim();
    if (trimmed.length > 2 && trimmed.length < 80 && priceRegex.test(trimmed)) {
      debug.price_like_texts.push(trimmed);
    }
  });

  // Limit size
  if (debug.interesting_elements.length > 12) debug.interesting_elements.length = 12;
  if (debug.price_like_texts.length > 20) debug.price_like_texts.length = 20;

  console.log("[stock-monitor] DOM debug captured, sending...", { reason, canvases: debug.canvases.length, elements: debug.interesting_elements.length });

  try {
    if (!chrome.runtime?.id) return;
    await chrome.runtime.sendMessage({
      type: "DUMP_DEBUG",
      payload: debug,
    });
  } catch (e) {
    if (!e.message || !e.message.includes('Extension context invalidated')) {
      console.warn("[stock-monitor] DOM debug send failed", e);
    }
  }

  return debug;
}

// Periodic DOM debug when capture is active (helps user inspect real page structure)
let domDebugInterval = null;

function startPeriodicDomDebug() {
  if (!ENABLE_PERIODIC_DOM_DEBUG) return;
  if (domDebugInterval) clearInterval(domDebugInterval);
  domDebugInterval = setInterval(() => {
    if (captureEnabled) {
      captureDomDebug("periodic").catch(() => {});
    }
  }, 8000); // every 8 seconds while capture on
}

function stopPeriodicDomDebug() {
  if (domDebugInterval) {
    clearInterval(domDebugInterval);
    domDebugInterval = null;
  }
}

// --- Symbol / Timeframe detection (best-effort, will evolve) ---

async function detectSymbol() {
  // URL patterns (common for SPAs)
  const url = location.href;
  let m = url.match(/\/stocks\/([A-Z.]+)/i) || url.match(/\/quote\/([A-Z.]+)/i) || url.match(/[?&]symbol=([A-Z.]+)/i);
  if (m) return m[1].toUpperCase();

  // DOM fallbacks — tuned for Webull's UI (header, quote info, etc.)
  // Try more specific and common patterns first
  const candidates = document.querySelectorAll(
    '[class*="symbol"], [class*="ticker"], [data-symbol], [data-ticker], ' +
    'h1, .stock-name, [aria-label*="symbol"], [aria-label*="ticker"], ' +
    '[class*="header"] [class*="name"], [class*="quote"] [class*="symbol"], ' +
    'input[value*="-"]'  // sometimes ticker in inputs
  );
  for (const el of candidates) {
    const txt = (el.textContent || el.getAttribute("data-symbol") || el.getAttribute("data-ticker") || el.value || "").trim().toUpperCase();
    if (/^[A-Z]{1,6}(\.[A-Z]{1,2})?$/.test(txt) && txt.length >= 1) {
      return txt;
    }
  }

  // Last resort: scan for short uppercase tickers in common chart header areas
  const headerAreas = document.querySelectorAll('[class*="header"], [class*="info"], [class*="title"], [class*="quote"]');
  for (const area of headerAreas) {
    const matches = (area.textContent || "").match(/\b([A-Z]{1,5})\b/g);
    if (matches) {
      for (const t of matches) {
        if (/^[A-Z]{1,5}$/.test(t) && t.length >= 1 && t.length <= 5) {
          // Heuristic: avoid common words
          if (!['THE', 'AND', 'FOR', 'USD', 'NYSE', 'NASDAQ'].includes(t)) return t;
        }
      }
    }
  }
  return null;
}

async function detectTimeframe() {
  // Priority: elements that look explicitly selected/active for timeframes
  const selectors = [
    '[class*="active"]', '[aria-selected="true"]', '[class*="selected"]',
    'button[aria-pressed="true"]', '.active', '.selected'
  ];
  for (const sel of selectors) {
    const els = document.querySelectorAll(sel);
    for (const el of els) {
      const txt = (el.textContent || el.getAttribute('data-period') || '').trim();
      if (/^\d+[smhdw]$/i.test(txt) || /^1[dmh]$/i.test(txt) || /min|hour|day|week/i.test(txt)) {
        const norm = normalizeTf(txt);
        if (norm) return norm;
      }
    }
  }

  // Look inside common chart toolbar / period selector containers
  const containers = document.querySelectorAll(
    '[class*="toolbar"], [class*="period"], [class*="timeframe"], [class*="interval"], nav, header'
  );
  for (const cont of containers) {
    const buttons = cont.querySelectorAll('button, div[role="tab"], span, a');
    for (const b of buttons) {
      const t = (b.textContent || '').trim();
      if (/^\d+[smhdw]$/i.test(t) || /^1[dm]$/i.test(t) || t.toLowerCase() === "day") {
        return normalizeTf(t);
      }
    }
  }
  return null;
}

// Observe DOM for timeframe button changes (user clicks different TF)
function setupTimeframeObserver() {
  const observer = new MutationObserver(() => {
    // When DOM mutates in the toolbar area, re-evaluate current TF (cheap)
    // We don't auto-push here; next data batch will use the fresh tf.
    detectTimeframe().then(tf => {
      if (tf && tf !== currentTimeframe) {
        currentTimeframe = tf;
        // next incoming data will create the correct key
      }
    });
  });

  // Observe broadly but not too expensive
  observer.observe(document.documentElement || document.body, {
    childList: true,
    subtree: true,
    attributes: true,
    attributeFilter: ['class', 'aria-selected', 'aria-pressed']
  });
}

setupTimeframeObserver();

// Observe DOM for symbol/ticker changes when user switches tickers in the SPA UI without reload
function setupSymbolObserver() {
  const observer = new MutationObserver(() => {
    detectSymbol().then(sym => {
      if (sym && sym !== currentSymbol) {
        // Update immediately so next data batch or WS uses the correct one
        currentSymbol = sym;
        // Optional: log for debugging
        // console.log('[stock-monitor] DOM detected ticker switch to', sym);
      }
    });
  });

  // Watch for text/DOM changes in the header/quote area
  observer.observe(document.documentElement || document.body, {
    childList: true,
    subtree: true,
    characterData: true,
    attributes: true,
    attributeFilter: ['class', 'data-symbol', 'data-ticker']
  });
}

setupSymbolObserver();

// Track SPA navigations (Webull doesn't always reload)
refreshPageMode();
window.addEventListener("popstate", () => refreshPageMode());
// History pushState/replaceState patch for SPA URL changes
(function patchHistory() {
  const wrap = (fnName) => {
    const orig = history[fnName];
    if (typeof orig !== "function") return;
    history[fnName] = function () {
      const ret = orig.apply(this, arguments);
      try { refreshPageMode(); } catch (_) {}
      return ret;
    };
  };
  wrap("pushState");
  wrap("replaceState");
})();
// Periodic re-check (fallback for SPA) + re-arm when user selects a My Screener
setInterval(() => {
  refreshPageMode();
  if (pageMode === "screener") refreshScreenerArm();
}, 1500);

// DOM mutations often fire when selecting a My Screener
const armObserver = new MutationObserver(() => {
  if (pageMode === "screener") refreshScreenerArm();
});
try {
  armObserver.observe(document.documentElement || document.body, {
    childList: true,
    subtree: true,
    attributes: true,
    attributeFilter: ["class", "aria-selected", "aria-pressed"],
  });
} catch (_) {}

// Report initial state to background (usually capture off → blue icon on Webull)
setTimeout(() => {
  refreshPageMode();
  if (pageMode === "screener") {
    refreshScreenerArm();
    safeSendMessage({
      type: "REPORT_ICON_STATE",
      enabled: screenerArmed,
      mode: "screener",
      armed: screenerArmed,
    });
  } else {
    safeSendMessage({ type: "REPORT_ICON_STATE", enabled: captureEnabled, mode: pageMode });
  }
}, 800);

function normalizeTf(raw) {
  const s = raw.toLowerCase().replace(/\s+/g, "");
  if (s === "1m" || s === "1min" || s === "m1") return "1m";
  if (s === "5m" || s === "5min" || s === "m5") return "5m";
  if (s === "15m" || s === "15min") return "15m";
  if (s === "30m") return "30m";
  if (s === "1h" || s === "60m" || s === "h1") return "1h";
  if (s === "4h") return "4h";
  if (s === "1d" || s === "day" || s === "d") return "1d";
  if (s === "1w" || s === "week") return "1w";
  return raw;
}

// Status helper + control messages for popup
chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  try {
    if (!chrome.runtime?.id) {
      // Extension was reloaded; send minimal response to avoid "no response" in popup
      if (msg.type === "GET_CHART_STATUS" || msg.type === "GET_PAGE_STATUS") {
        sendResponse({
          mode: pageMode,
          symbol: currentSymbol,
          timeframe: currentTimeframe,
          enabled: false,
          error: "context invalidated"
        });
      }
      return;
    }
  } catch (e) {
    if (msg.type === "GET_CHART_STATUS" || msg.type === "GET_PAGE_STATUS") {
      sendResponse({ error: e.message });
    }
    return;
  }
  refreshPageMode();
  console.log("[stock-monitor] received message:", msg.type, "mode=", pageMode, "captureEnabled=", captureEnabled);

  if (msg.type === "GET_CHART_STATUS" || msg.type === "GET_PAGE_STATUS") {
    const key = currentSymbol ? `${currentSymbol}:${currentTimeframe || 'unknown'}` : null;
    const closedCount = key && buffer.has(key)
      ? Math.max(0, (buffer.get(key) || []).length - 1)
      : 0;

    const sampleTickers = Array.from(screenerSeenTickers).slice(0, 12);
    if (pageMode === "screener") refreshScreenerArm();

    sendResponse({
      mode: pageMode,
      url: location.href,
      symbol: currentSymbol,
      timeframe: currentTimeframe,
      // Chart: explicit toggle. Screener: "on" only when armed on configured My Screener.
      enabled: pageMode === "screener" ? screenerArmed : captureEnabled,
      captureEnabled,
      bufferedKeys: Array.from(buffer.keys()),
      bufferSizes: Object.fromEntries([...buffer].map(([k, v]) => [k, v.length])),
      approxClosed: closedCount,
      lastDataTs: lastDataTs,
      lastPushedTs: lastPushedTs,
      tabId: myTabId,
      // Screener fields
      screener: {
        auto: true,
        armed: screenerArmed,
        armReason: screenerArmReason,
        uiRegion: screenerUiRegion,
        activeScreener: activeScreener,
        manual: !!manualArmOverride,
        diagnostics: lastArmDiagnostics,
        configured: (screenerConfig.screeners || []).map((s) => ({
          key: s.key,
          name: s.name,
        })),
        uniqueTickers: screenerSeenTickers.size,
        lastRowCount: screenerLastRowCount,
        lastPushTs: screenerLastPushTs,
        lastResult: screenerLastResult,
        droppedBatches: screenerDroppedBatches,
        sampleTickers,
      },
    });
    return;
  }

  if (msg.type === "SET_SCREENER_ARM") {
    // Popup: manually arm/disarm a configured screener (escape hatch when DOM detect fails)
    if (pageMode !== "screener") {
      sendResponse({ ok: false, error: "not on screener page" });
      return;
    }
    if (msg.armed === false) {
      manualArmOverride = null;
      refreshScreenerArm();
      safeSendMessage({
        type: "REPORT_ICON_STATE",
        enabled: screenerArmed,
        mode: "screener",
        armed: screenerArmed,
      });
      sendResponse({ ok: true, armed: screenerArmed, activeScreener, armReason: screenerArmReason });
      return;
    }
    const key = msg.screener_key || "gap-n-go";
    const cfg = (screenerConfig.screeners || []).find((s) => s.key === key)
      || (screenerConfig.screeners || [])[0];
    if (!cfg) {
      sendResponse({ ok: false, error: "no configured screener" });
      return;
    }
    manualArmOverride = {
      key: cfg.key,
      name: cfg.name,
      webull_screener_id: cfg.webull_screener_id || null,
    };
    refreshScreenerArm();
    console.log("[stock-monitor] manual arm set", manualArmOverride);
    safeSendMessage({
      type: "REPORT_ICON_STATE",
      enabled: screenerArmed,
      mode: "screener",
      armed: screenerArmed,
    });
    sendResponse({ ok: true, armed: screenerArmed, activeScreener, armReason: screenerArmReason });
    return;
  }

  if (msg.type === "SET_MONITORING") {
    if (pageMode !== "chart") {
      sendResponse({ enabled: false, error: "capture only on chart tabs" });
      return;
    }
    captureEnabled = !!msg.enabled;
    console.log("[stock-monitor] SET_MONITORING → captureEnabled =", captureEnabled, "for", currentSymbol, currentTimeframe);

    // Tell background to update the extension icon (green when capturing)
    safeSendMessage({ type: "REPORT_ICON_STATE", enabled: captureEnabled, mode: "chart" });

    if (captureEnabled) {
      startPeriodicDomDebug();
      // Also do an immediate DOM dump so user can inspect right away
      captureDomDebug("on_enable_start").catch(() => {});
    } else {
      stopPeriodicDomDebug();
    }

    if (captureEnabled && currentSymbol) {
      const tf = normalizeTf(currentTimeframe || 'unknown');
      const key = `${currentSymbol}:${tf}`;
      const all = buffer.get(key) || [];
      if (all.length > 1) {
        const sorted = [...all].sort((a, b) => a.t - b.t);
        const closed = sorted.slice(0, -1);
        if (closed.length > 0) {
          scheduleClosedPush(currentSymbol, tf, closed, "enable", { ignoreThrottle: true });
          lastDataTs = Date.now();
        } else {
          console.log("[stock-monitor] capture enabled but no additional closed candles to push yet");
        }
      } else {
        console.log("[stock-monitor] capture enabled, waiting for more chart data");
      }
    }
    sendResponse({ enabled: captureEnabled });
    return;
  }

  if (msg.type === "FORCE_PUSH") {
    if (currentSymbol) {
      const tf = normalizeTf(currentTimeframe || 'unknown');
      const key = `${currentSymbol}:${tf}`;
      const all = buffer.get(key) || [];
      if (all.length > 0) {
        const sorted = [...all].sort((a, b) => a.t - b.t);
        const closed = sorted.length > 1 ? sorted.slice(0, -1) : [];
        if (closed.length > 0) {
          console.log("[stock-monitor] FORCE_PUSH sending", closed.length, "closed candles");
          scheduleClosedPush(currentSymbol, tf, closed, "force", { ignoreThrottle: true, includeAcked: true });
        } else {
          console.log("[stock-monitor] FORCE_PUSH: no closed candles yet");
        }
      }
    }
    sendResponse({ ok: true });
    return;
  }

  if (msg.type === "CLEAR_BUFFER") {
    buffer.clear();
    lastMaxTs.clear();
    lastAckedClosedTs.clear();
    pendingClosedTs.clear();
    lastPushByKey.clear();
    sendResponse({ ok: true });
  }

  if (msg.type === "DUMP_DEBUG") {
    captureDomDebug("manual").then(() => sendResponse({ ok: true })).catch(() => sendResponse({ ok: false }));
    return true;
  }
});
