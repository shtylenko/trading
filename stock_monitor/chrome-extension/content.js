// content.js — Injected into app.webull.com pages (isolated world)
// - Injects inject.js into the PAGE world (MAIN)
// - Receives data via window.postMessage from inject.js
// - Detects symbol + active/open timeframe
// - When "Start Capture" is on for the tab: auto-pushes closed candles + immediate capture on enable
// - Only ever deals with fully closed candles (never the forming bar)

console.log("[stock-monitor] content script loaded on", location.href);
if (typeof DEBUG_ALL_RESPONSES !== "undefined" && DEBUG_ALL_RESPONSES) {
  console.log("[stock-monitor] !!! DEBUG_ALL_RESPONSES is enabled in inject.js - dumping every JSON");
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

  if (data.type === "CANDLES_DETECTED") {
    console.log("[stock-monitor] CANDLES_DETECTED from inject", {
      source: data.payload?.source,
      sym: data.payload?.symbol,
      tf: data.payload?.timeframe,
      count: data.payload?.candles?.length
    });
    handleCandlesDetected(data.payload);
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
        detected: { symbol: currentSymbol, timeframe: currentTimeframe },
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
        detected: { symbol: currentSymbol, timeframe: currentTimeframe },
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

// Report initial state to background (usually capture off → blue icon on Webull)
setTimeout(() => {
  safeSendMessage({ type: "REPORT_ICON_STATE", enabled: captureEnabled });
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
      if (msg.type === "GET_CHART_STATUS") {
        sendResponse({
          symbol: currentSymbol,
          timeframe: currentTimeframe,
          enabled: false,
          error: "context invalidated"
        });
      }
      return;
    }
  } catch (e) {
    if (msg.type === "GET_CHART_STATUS") {
      sendResponse({ error: e.message });
    }
    return;
  }
  console.log("[stock-monitor] received message:", msg.type, "captureEnabled=", captureEnabled);

  if (msg.type === "GET_CHART_STATUS") {
    const key = currentSymbol ? `${currentSymbol}:${currentTimeframe || 'unknown'}` : null;
    const closedCount = key && buffer.has(key)
      ? Math.max(0, (buffer.get(key) || []).length - 1)
      : 0;

    sendResponse({
      symbol: currentSymbol,
      timeframe: currentTimeframe,
      enabled: captureEnabled,
      bufferedKeys: Array.from(buffer.keys()),
      bufferSizes: Object.fromEntries([...buffer].map(([k, v]) => [k, v.length])),
      approxClosed: closedCount,
      lastDataTs: lastDataTs,
      lastPushedTs: lastPushedTs,
      tabId: myTabId,
    });
    return;
  }

  if (msg.type === "SET_MONITORING") {
    captureEnabled = !!msg.enabled;
    console.log("[stock-monitor] SET_MONITORING → captureEnabled =", captureEnabled, "for", currentSymbol, currentTimeframe);

    // Tell background to update the extension icon (green when capturing)
    safeSendMessage({ type: "REPORT_ICON_STATE", enabled: captureEnabled });

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
