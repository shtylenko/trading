// inject.js — Runs in the PAGE MAIN world on app.webull.com
// Purpose: Hook network activity (fetch, XHR, WebSocket) to discover candle data payloads.
// This file is listed in web_accessible_resources and injected by content.js.
//
// Heuristics will improve after we observe real traffic on a logged-in chart.
//
// Communication: window.postMessage({ source: "webull-monitor-inject", type: "...", payload })

(function () {
  const SOURCE = "webull-monitor-inject";

  // DEBUG: dump EVERY JSON response (only for initial discovery).
  // Set to false for normal operation (cleaner, less spam in debug folder).
  const DEBUG_ALL_RESPONSES = false;

  function post(type, payload) {
    try {
      window.postMessage({ source: SOURCE, type, payload }, "*");
    } catch (e) {
      // ignore
    }
  }

  // --- Utility: try to recognize candle-like data ---
  // Made much more permissive to catch Webull's actual payloads
  function looksLikeCandles(value) {
    if (!value) return false;

    let samples = [];
    if (Array.isArray(value)) {
      if (value.length === 0) return false;
      samples = value;
    } else if (typeof value === "object") {
      samples = [value];
    } else {
      return false;
    }

    const sample = samples.find(s => s && typeof s === "object") || samples[0];
    if (typeof sample !== "object" || sample === null) return false;

    const keys = Object.keys(sample).map(k => k.toLowerCase());

    // Count numeric-ish fields (common in kline data)
    const numericFields = keys.filter(k =>
      k.includes("open") || k.includes("high") || k.includes("low") || k.includes("close") ||
      k.includes("vol") || k.includes("amount") || k.includes("price") ||
      ["o","h","l","c","v","t"].includes(k)
    );

    const hasTimeField = keys.some(k =>
      k.includes("time") || k.includes("t") || k.includes("date") || k.includes("begin") ||
      k.includes("end") || k.includes("kline") || k.includes("bar")
    );

    // Accept if it has several price/volume fields + time indicator
    // This is looser to catch real Webull responses
    return numericFields.length >= 3 && hasTimeField;
  }

  function normalizeCandles(rawArray, context = {}) {
    return rawArray
      .map((item) => {
        // Support many possible shapes Webull or similar might use
        const t = item.timestamp ?? item.time ?? item.t ?? item.date ?? item.begin ?? item.startTime ?? item.openTime ?? item.klineTime;
        const o = item.open ?? item.o ?? item.openPrice ?? item.open_price;
        const h = item.high ?? item.h ?? item.highPrice ?? item.high_price;
        const l = item.low ?? item.l ?? item.lowPrice ?? item.low_price;
        const c = item.close ?? item.c ?? item.closePrice ?? item.close_price;
        const v = item.volume ?? item.v ?? item.vol ?? item.amount ?? item.turnover ?? 0;

        const ts = typeof t === "string" ? Date.parse(t) : Number(t);
        if (!ts || !isFinite(ts)) return null;

        return {
          t: ts,
          o: Number(o),
          h: Number(h),
          l: Number(l),
          c: Number(c),
          v: Number(v),
        };
      })
      .filter(Boolean);
  }

  function extractSymbolFromRequest(url, body) {
    try {
      const u = new URL(url, location.origin);
      // Common patterns
      const fromPath = u.pathname.match(/\/([A-Z.]{1,6})(\/|$|\?)/i);
      if (fromPath) return fromPath[1].toUpperCase();

      const q = u.searchParams.get("symbol") || u.searchParams.get("ticker") || u.searchParams.get("code") || u.searchParams.get("tickerIds");
      if (q) return q.toUpperCase().split(',')[0];  // take first tickerId

      // Body may be JSON
      if (body) {
        let parsed;
        try { parsed = typeof body === "string" ? JSON.parse(body) : body; } catch {}
        if (parsed?.symbol) return String(parsed.symbol).toUpperCase();
        if (parsed?.ticker) return String(parsed.ticker).toUpperCase();
        if (parsed?.code) return String(parsed.code).toUpperCase();
      }
    } catch {}
    return null;
  }

  function extractTimeframeFromRequest(url, body) {
    try {
      const u = new URL(url, location.origin);
      let tf =
        u.searchParams.get("period") ||
        u.searchParams.get("interval") ||
        u.searchParams.get("timeframe") ||
        u.searchParams.get("tf") ||
        u.searchParams.get("type");
      if (tf) return tf;

      if (body) {
        let p;
        try { p = typeof body === "string" ? JSON.parse(body) : body; } catch {}
        if (p?.period) return p.period;
        if (p?.interval) return p.interval;
        if (p?.timeframe) return p.timeframe;
      }
    } catch {}
    return null;
  }

  // Helper for debug dumps - never send huge payloads
  function makeDebugSample(json) {
    if (Array.isArray(json)) {
      return {
        type: "array",
        length: json.length,
        sample: json.slice(0, 3),
      };
    }
    if (json && typeof json === "object") {
      const keys = Object.keys(json);
      return {
        type: "object",
        keys: keys.slice(0, 20),
        sample: Object.fromEntries(
          keys.slice(0, 5).map(k => [k, json[k]])
        ),
      };
    }
    return json;
  }

  function maybeDebugDump(source, url, json, bodyForExtract) {
    if (!DEBUG_ALL_RESPONSES) return;
    try {
      const sym = extractSymbolFromRequest(url, bodyForExtract);
      const tf = extractTimeframeFromRequest(url, bodyForExtract);
      post("DEBUG_JSON", {
        source,
        url: url.substring(0, 400),
        symbol: sym,
        timeframe: tf,
        data_sample: makeDebugSample(json),
      });
    } catch (e) {}
  }

  // Always extract tickerId -> symbol mapping from quote responses (for nice symbols)
  function maybeExtractTickerInfo(url, json) {
    try {
      if (!json || !url) return;
      const isQuote = url.includes('realtime') || url.includes('getQuote') || url.includes('/quote/');
      if (!isQuote) return;

      let items = [];
      if (Array.isArray(json)) items = json;
      else if (Array.isArray(json.data)) items = json.data;
      else if (json.tickerId) items = [json];

      for (const item of items) {
        if (item && item.tickerId && (item.symbol || item.disSymbol)) {
          post("TICKER_INFO", {
            tickerId: String(item.tickerId),
            symbol: (item.symbol || item.disSymbol).toUpperCase(),
            name: item.name || null
          });
        }
      }
    } catch (e) {}
  }

  // Special parser for Webull kdata responses
  function parseKdataResponse(json, url) {
    try {
      let root = json;
      if (Array.isArray(json) && json.length > 0) {
        root = json[0];
      }
      if (!root || !Array.isArray(root.data)) return null;

      const candles = [];
      for (const line of root.data) {
        if (typeof line !== "string") continue;
        const parts = line.split(",");
        if (parts.length < 7) continue;
        const ts = parseInt(parts[0], 10) * 1000; // to ms
        const o = parseFloat(parts[1]);
        const h = parseFloat(parts[3]);
        const l = parseFloat(parts[4]);
        const c = parseFloat(parts[5]);
        const v = parseFloat(parts[6]);
        if (isFinite(ts) && isFinite(o)) {
          candles.push({ t: ts, o, h, l, c, v });
        }
      }
      if (candles.length === 0) return null;

      const u = new URL(url, location.origin);
      const tickerId = u.searchParams.get("tickerIds") || root.tickerId || "UNKNOWN";
      const tf = u.searchParams.get("type") || "unknown";
      return { tickerId: String(tickerId).split(",")[0], timeframe: tf, candles };
    } catch (e) { return null; }
  }

  // --- Hook fetch ---
  const origFetch = window.fetch;
  window.fetch = async function (input, init = {}) {
    const url = typeof input === "string" ? input : input?.url || String(input);
    const body = init?.body;

    const resp = await origFetch.apply(this, arguments);

    try {
      const clone = resp.clone();
      const contentType = clone.headers.get("content-type") || "";
      if (contentType.includes("application/json")) {
        const json = await clone.json().catch(() => null);
        if (json) {
          maybeDebugDump("fetch", url, json, body);
          maybeExtractTickerInfo(url, json);

          // Special handling for Webull kdata (kline) responses
          if (url.includes("kdata")) {
            const kparsed = parseKdataResponse(json, url);
            if (kparsed && kparsed.candles.length > 0) {
              console.log("[webull-monitor-inject] parsed kdata via fetch", { tickerId: kparsed.tickerId, tf: kparsed.timeframe, count: kparsed.candles.length });
              post("CANDLES_DETECTED", {
                source: "fetch",
                url: url.substring(0, 300),
                tickerId: kparsed.tickerId,
                timeframe: kparsed.timeframe,
                candles: kparsed.candles,
              });
            }
          }

          // Search recursively for arrays that look like candles
          const found = findCandleArrays(json);
          if (found.length > 0) {
            for (const arr of found) {
              const norm = normalizeCandles(arr);
              const sym = extractSymbolFromRequest(url, body);
              const tf = extractTimeframeFromRequest(url, body);
              if (norm.length > 0) {
                console.log("[webull-monitor-inject] found candles via fetch", { sym, tf, count: norm.length, sample: norm[0] });
                post("CANDLES_DETECTED", {
                  source: "fetch",
                  url: url.substring(0, 300),
                  symbol: sym,
                  timeframe: tf,
                  candles: norm,
                });
              } else {
                // Still send raw for debugging so we can see real Webull payload shape in debug files
                console.log("[webull-monitor-inject] fetch response had array but normalize failed. Raw sample keys:", Object.keys(arr[0] || {}));
                if (DEBUG_ALL_RESPONSES) {
                  post("RAW_POTENTIAL", {
                    source: "fetch",
                    url: url.substring(0, 300),
                    symbol: sym,
                    timeframe: tf,
                    raw_sample: arr.slice(0, 3),  // first few raw items
                  });
                }
              }
            }
          }
        }
      }
    } catch (e) {
      // never break the page
    }
    return resp;
  };

  // --- Hook XHR ---
  const OrigXHR = window.XMLHttpRequest;
  window.XMLHttpRequest = function () {
    const xhr = new OrigXHR();
    let _url = "";
    let _body = null;

    const origOpen = xhr.open;
    xhr.open = function (method, url) {
      _url = url;
      return origOpen.apply(this, arguments);
    };

    const origSend = xhr.send;
    xhr.send = function (body) {
      _body = body;
      return origSend.apply(this, arguments);
    };

    xhr.addEventListener("load", function () {
      try {
        const ct = xhr.getResponseHeader("content-type") || "";
        if (ct.includes("json") && xhr.responseText) {
          const json = JSON.parse(xhr.responseText);
          maybeDebugDump("xhr", _url, json, _body);
          maybeExtractTickerInfo(_url, json);

          if (_url.includes("kdata")) {
            const kparsed = parseKdataResponse(json, _url);
            if (kparsed && kparsed.candles.length > 0) {
              console.log("[webull-monitor-inject] parsed kdata via xhr", { tickerId: kparsed.tickerId, tf: kparsed.timeframe, count: kparsed.candles.length });
              post("CANDLES_DETECTED", {
                source: "xhr",
                url: String(_url).substring(0, 300),
                tickerId: kparsed.tickerId,
                timeframe: kparsed.timeframe,
                candles: kparsed.candles,
              });
            }
          }

          const found = findCandleArrays(json);
          if (found.length) {
            for (const arr of found) {
              const norm = normalizeCandles(arr);
              const sym = extractSymbolFromRequest(_url, _body);
              const tf = extractTimeframeFromRequest(_url, _body);
              if (norm.length) {
                console.log("[webull-monitor-inject] found candles via xhr", { sym, tf, count: norm.length });
                post("CANDLES_DETECTED", {
                  source: "xhr",
                  url: String(_url).substring(0, 300),
                  symbol: sym,
                  timeframe: tf,
                  candles: norm,
                });
              } else if (arr && arr.length) {
                console.log("[webull-monitor-inject] xhr had potential data but normalize failed. Keys:", Object.keys(arr[0] || {}));
                if (DEBUG_ALL_RESPONSES) {
                  post("RAW_POTENTIAL", {
                    source: "xhr",
                    url: String(_url).substring(0, 300),
                    symbol: sym,
                    timeframe: tf,
                    raw_sample: arr.slice(0, 3),
                  });
                }
              }
            }
          }
        }
      } catch {}
    });

    return xhr;
  };

  // --- Hook WebSocket (for live updates) ---
  const OrigWS = window.WebSocket;
  window.WebSocket = function (url, protocols) {
    const ws = new OrigWS(url, protocols);

    ws.addEventListener("message", (ev) => {
      try {
        let data = ev.data;
        if (typeof data === "string") {
          try { data = JSON.parse(data); } catch {}
        }
        if (data && typeof data === "object") {
          if (DEBUG_ALL_RESPONSES) {
            // For WS we are more conservative - only dump occasionally or key messages
            maybeDebugDump("ws", url, data, null);
          }
          const found = findCandleArrays(data);
          if (found.length) {
            for (const arr of found) {
              const norm = normalizeCandles(arr);
              if (norm.length) {
                console.log("[webull-monitor-inject] found candles via ws", { count: norm.length, sample: norm[0] });
                post("CANDLES_DETECTED", {
                  source: "ws",
                  url: String(url).substring(0, 200),
                  symbol: null,
                  timeframe: null,
                  candles: norm,
                });
              } else if (arr && arr.length > 0) {
                console.log("[webull-monitor-inject] ws had potential data but normalize failed");
                if (DEBUG_ALL_RESPONSES) {
                  post("RAW_POTENTIAL", {
                    source: "ws",
                    url: String(url).substring(0, 200),
                    symbol: null,
                    timeframe: null,
                    raw_sample: arr.slice(0, 3),
                  });
                }
              }
            }
          }
        }
      } catch {}
    });

    return ws;
  };

  // Recursive search for candle arrays (or single candle objects) inside unknown JSON structures
  function findCandleArrays(obj, depth = 0, maxDepth = 6) {
    if (depth > maxDepth || !obj || typeof obj !== "object") return [];
    const results = [];

    if (Array.isArray(obj)) {
      if (looksLikeCandles(obj)) {
        results.push(obj);
      }
      for (const item of obj) {
        results.push(...findCandleArrays(item, depth + 1, maxDepth));
      }
    } else {
      // Check if this object itself looks like a single candle
      if (looksLikeCandles(obj)) {
        results.push([obj]); // wrap as array for uniform handling
      }
      for (const k of Object.keys(obj)) {
        results.push(...findCandleArrays(obj[k], depth + 1, maxDepth));
      }
    }
    return results;
  }

  // Expose a manual trigger for debugging from console
  window.__webullMonitorCapture = () => {
    post("RAW_LOG", { msg: "manual capture requested (extend this)" });
  };

  console.log("[webull-monitor] page inject active — network hooks installed");
  if (DEBUG_ALL_RESPONSES) {
    console.log("[webull-monitor] !!! DEBUG MODE ACTIVE: dumping ALL JSON responses to backend debug/");
  }
})();
