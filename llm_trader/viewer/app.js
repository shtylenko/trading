/* SPA Session Viewer
   - Default view = list of sessions (newest first)
   - Sidebar always visible
   - Click loads detail in main area
   - Cmd/Ctrl click opens in new tab
   - Live sessions use SSE + server-computed state (revealed data only)
   - Max ~720 bars planned
*/

const CSS = getComputedStyle(document.documentElement);
const col = (n) => CSS.getPropertyValue(n).trim();

let currentSessionId = null;
let currentChart = null;
let currentEventSource = null;
let pollFallbackTimer = null;
let activeTab = "sessions";       // "sessions" | "batches"
let currentBatchTag = null;
let batchRefreshTimer = null;

const fmtMoney = (n) => (n == null ? "—" : (n >= 0 ? "+$" : "-$") + Math.abs(n));

function statusBadge(status) {
  if (status === "complete") return { cls: "complete", label: "complete" };
  if (status === "stale") return { cls: "stale", label: "stale" };
  return { cls: "running", label: status || "running" };
}

function fail(msg) {
  const el = document.getElementById("error");
  el.textContent = "Viewer error:\n\n" + msg;
  el.classList.remove("hidden");
}

function qs(name) {
  return new URLSearchParams(location.search).get(name);
}

async function getJSON(url) {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`${url} → HTTP ${r.status}`);
  return r.json();
}

function chip(label, val) {
  if (val === null || val === undefined || val === "") return "";
  return `<span class="chip">${label} <b>${val}</b></span>`;
}

const fmtFloat = (f) => (f ? (f / 1e6).toFixed(1) + "M" : "n/a");

// ---------- LIST ----------

async function loadAndRenderList() {
  const listEl = document.getElementById("session-list");
  listEl.innerHTML = `<div class="muted" style="padding:8px">Loading sessions...</div>`;

  try {
    const data = await getJSON("/api/sessions");
    const sessions = data.sessions || [];

    document.getElementById("session-count").textContent = `(${sessions.length})`;

    if (!sessions.length) {
      listEl.innerHTML = `<div class="muted" style="padding:12px">No sessions yet.</div>`;
      return;
    }

    listEl.innerHTML = sessions.map(s => {
      const status = s.status || "running";
      const mode = s.mode || "simulated";
      const isLive = status !== "complete";
      // an idle "running" session (flagged stale by the server) gets its own badge
      // so it doesn't masquerade as live forever
      const isStale = isLive && s.stale;
      const badgeClass = !isLive ? "complete" : (isStale ? "stale" : "running");
      const badgeLabel = !isLive ? status : (isStale ? "stale" : status);

      let summary = "";
      if (s.result) {
        const r = s.result;
        summary = `${r.traded ? (r.realized_pnl >= 0 ? "+" : "") + "$" + r.realized_pnl + " · " + r.r_multiple + "R" : "no trade"}`;
      } else if (isStale) {
        summary = "idle — may be abandoned";
      } else if (isLive) {
        if (s.live_pnl) {
          const lp = s.live_pnl;
          summary = `realized $${lp.realized_pnl ?? 0}`;
          if (lp.unrealized != null) summary += ` · uPnL $${lp.unrealized}`;
        } else {
          summary = "in progress";
        }
      }

      const last = s.last_activity || s.real_run_ts || "";

      return `
        <div class="sess-card" data-id="${s.id}">
          <div class="sess-top">
            <span class="sess-ticker">${s.ticker || "?"}</span>
            <span class="badge ${badgeClass}">${mode} ${badgeLabel}</span>
          </div>
          <div class="sess-meta muted">${s.historical_date || ""} · ${last}</div>
          <div class="sess-summary">${summary}</div>
        </div>`;
    }).join("");

    // Bind clicks (regular = load here, meta = new tab)
    listEl.querySelectorAll(".sess-card").forEach(card => {
      const id = card.dataset.id;

      card.addEventListener("click", (e) => {
        if (e.metaKey || e.ctrlKey) {
          // Open in new tab
          window.open(`/viewer/index.html?session=${encodeURIComponent(id)}`, "_blank");
        } else {
          // Load in current view (SPA) - highlight immediately for responsiveness
          currentSessionId = id;
          highlightCurrentSession();
          loadSession(id, true);
          // update URL without reload
          history.replaceState(null, "", `?session=${encodeURIComponent(id)}`);
        }
      });

      // Also support middle click / auxclick for new tab
      card.addEventListener("auxclick", (e) => {
        if (e.button === 1) { // middle mouse
          window.open(`/viewer/index.html?session=${encodeURIComponent(id)}`, "_blank");
          e.preventDefault();
        }
      });
    });

    // Re-apply highlight after (re)rendering the list
    highlightCurrentSession();
  } catch (e) {
    listEl.innerHTML = `<div class="muted" style="padding:8px;color:#f88">Failed to load list: ${e}</div>`;
  }
}

// ---------- BATCHES ----------

function setTab(tab) {
  activeTab = tab;
  document.getElementById("tab-sessions").classList.toggle("active", tab === "sessions");
  document.getElementById("tab-batches").classList.toggle("active", tab === "batches");
  document.getElementById("session-list").classList.toggle("hidden", tab !== "sessions");
  document.getElementById("batch-list").classList.toggle("hidden", tab !== "batches");
  if (tab === "batches") loadAndRenderBatches();
  else loadAndRenderList();
}

function highlightCurrentBatch() {
  document.querySelectorAll("#batch-list .batch-card").forEach(c =>
    c.classList.toggle("selected", c.dataset.tag === currentBatchTag));
}

function renderBatchCard(b) {
  const sb = statusBadge(b.status);
  const pct = b.planned ? Math.round((100 * b.n_complete) / b.planned) : 0;
  const rep = (b.report && b.report[0]) || null;
  const summary = (rep && rep.n)
    ? `win ${rep.win_pct}% · ${fmtMoney(rep.pnl)} · ${rep.avg_r}R`
    : "no finalized trades yet";
  const voidTxt = b.n_void ? ` · ${b.n_void} void` : "";
  return `
    <div class="sess-card batch-card" data-tag="${escapeHtml(b.tag)}">
      <div class="sess-top">
        <span class="sess-ticker">${escapeHtml(b.tag)}</span>
        <span class="badge ${sb.cls}">${sb.label}</span>
      </div>
      <div class="batch-line">
        <span>${b.version ? "v" + escapeHtml(b.version) : "—"}</span>
        <span>${escapeHtml(b.model || "")}</span>
      </div>
      <div class="batch-prog">${b.n_complete}/${b.planned} done${voidTxt}</div>
      <div class="bar ${b.status === "complete" ? "done" : ""}"><span style="width:${pct}%"></span></div>
      <div class="sess-summary">${summary}</div>
      <div class="sess-meta muted">last ${b.last_activity || "—"}</div>
    </div>`;
}

async function loadAndRenderBatches() {
  const el = document.getElementById("batch-list");
  try {
    const data = await getJSON("/api/batches");
    const batches = data.batches || [];
    document.getElementById("batch-count").textContent = `(${batches.length})`;
    if (!batches.length) {
      el.innerHTML = `<div class="muted" style="padding:12px">No batches yet.<br>Run <code>batchsim run</code>.</div>`;
      return;
    }
    el.innerHTML = batches.map(renderBatchCard).join("");
    el.querySelectorAll(".batch-card").forEach(card => {
      card.addEventListener("click", () => openBatch(card.dataset.tag, true));
    });
    highlightCurrentBatch();
  } catch (e) {
    el.innerHTML = `<div class="muted" style="padding:8px;color:#f88">Failed to load batches: ${e}</div>`;
  }
}

function inferBatchStatus(v) {
  const ss = v.sessions || [];
  const meta = v.meta || {};
  if (meta.status === "complete") return "complete";
  const complete = ss.filter(s => s.status === "complete").length;
  const planned = meta.planned || ss.length;
  if (planned && ss.length >= planned && complete >= planned) return "complete";
  return "running";
}

async function openBatch(tag, updateUrl = false) {
  currentBatchTag = tag;
  // tear down any open session's live stream — we're leaving the session view
  if (currentEventSource) { currentEventSource.close(); currentEventSource = null; }
  if (pollFallbackTimer) { clearInterval(pollFallbackTimer); pollFallbackTimer = null; }
  currentSessionId = null;

  document.getElementById("no-session").classList.add("hidden");
  document.getElementById("session-detail").classList.add("hidden");
  document.getElementById("batch-detail").classList.remove("hidden");
  if (updateUrl) history.replaceState(null, "", `?batch=${encodeURIComponent(tag)}`);
  highlightCurrentBatch();

  try {
    const v = await getJSON(`/api/batch/${encodeURIComponent(tag)}`);
    renderBatchDetail(v);
    scheduleBatchRefresh(v);
  } catch (e) {
    document.getElementById("batch-detail").innerHTML =
      `<div class="muted" style="padding:16px;color:#f88">Could not load batch ${escapeHtml(tag)}: ${e}</div>`;
  }
}

function scheduleBatchRefresh(v) {
  if (batchRefreshTimer) { clearInterval(batchRefreshTimer); batchRefreshTimer = null; }
  if (inferBatchStatus(v) === "complete") return;   // nothing left to poll
  batchRefreshTimer = setInterval(async () => {
    if (!currentBatchTag) return;
    try {
      const nv = await getJSON(`/api/batch/${encodeURIComponent(currentBatchTag)}`);
      renderBatchDetail(nv);
      loadAndRenderBatches();                        // keep the sidebar progress fresh
      if (inferBatchStatus(nv) === "complete") {
        clearInterval(batchRefreshTimer);
        batchRefreshTimer = null;
      }
    } catch (_) { /* transient */ }
  }, 5000);
}

function closeBatch() {
  currentBatchTag = null;
  if (batchRefreshTimer) { clearInterval(batchRefreshTimer); batchRefreshTimer = null; }
  document.getElementById("batch-detail").classList.add("hidden");
  history.replaceState(null, "", location.pathname);
  if (!currentSessionId) document.getElementById("no-session").classList.remove("hidden");
  highlightCurrentBatch();
}

function renderBatchDetail(v) {
  const bd = document.getElementById("batch-detail");
  const meta = v.meta || {};
  const ss = v.sessions || [];
  const status = inferBatchStatus(v);
  const sb = statusBadge(status);
  const complete = ss.filter(s => s.status === "complete").length;
  const nvoid = ss.filter(s => s.void).length;
  const planned = meta.planned || ss.length;

  const metaBits = [
    meta.version ? `version <b>${escapeHtml(meta.version)}</b>` : null,
    meta.model ? `model ${escapeHtml(meta.model)}` : null,
    `${complete}/${planned} complete`,
    nvoid ? `${nvoid} void` : null,
    meta.started_ts ? `started ${meta.started_ts}` : null,
    meta.finished_ts ? `finished ${meta.finished_ts}` : null,
  ].filter(Boolean).join(" · ");

  const rep = v.report || [];
  const repRows = rep.length ? rep.map(r => `
    <tr>
      <td>${escapeHtml(r.version || "—")}</td>
      <td>${r.n}</td>
      <td>${r.win_pct}%</td>
      <td class="${r.pnl > 0 ? "pos" : r.pnl < 0 ? "neg" : ""}">${fmtMoney(r.pnl)}</td>
      <td>${r.avg_r}R</td>
      <td>${r.avg_capture != null ? r.avg_capture : "—"}</td>
      <td>${r.n_void || 0}</td>
    </tr>`).join("") : `<tr><td colspan="7" class="muted">no finalized trades yet</td></tr>`;

  const runRows = ss.length ? ss.map(s => {
    let res = "", cls = "";
    if (s.void) { res = "VOID: " + escapeHtml((s.void || "").slice(0, 60)); cls = "void"; }
    else if (s.result && s.result.traded) {
      res = `${fmtMoney(s.result.realized_pnl)} · ${s.result.r_multiple}R ${s.result.win ? "WIN" : "LOSS"}`;
      cls = s.result.realized_pnl > 0 ? "pos" : s.result.realized_pnl < 0 ? "neg" : "";
    } else if (s.status === "complete") { res = "no trade"; }
    else if (s.stale) { res = "idle — may be abandoned"; }
    else { res = s.live_pnl ? `running · realized ${fmtMoney(s.live_pnl.realized_pnl || 0)}` : "running"; }
    const stb = statusBadge(s.status === "complete" ? "complete" : (s.stale ? "stale" : "running"));
    const ver = s.skill_version || s.version || "—";
    const init = s.real_run_ts || "";
    const done = s.finalized_ts || (s.status === "complete" ? s.last_activity : "");
    return `<tr class="run" data-id="${escapeHtml(s.id)}">
      <td><b>${escapeHtml(s.ticker || "?")}</b></td>
      <td>${escapeHtml(s.historical_date || "")}</td>
      <td>${escapeHtml(ver)}</td>
      <td class="muted small">${escapeHtml(init)}</td>
      <td class="muted small">${escapeHtml(done)}</td>
      <td><span class="badge ${stb.cls}">${stb.label}</span></td>
      <td class="${cls}">${res}</td>
    </tr>`;
  }).join("") : `<tr><td colspan="7" class="muted">no runs yet</td></tr>`;

  bd.innerHTML = `
    <div class="bd-head">
      <span class="small-btn bd-back" id="bd-back">← back</span>
      <h2>${escapeHtml(v.tag)}</h2>
      <span class="badge ${sb.cls}">${sb.label}</span>
    </div>
    <div class="bd-meta">${metaBits}</div>
    <div class="bd-section">By skill version</div>
    <table class="bd-table">
      <thead><tr><th>version</th><th>n</th><th>win%</th><th>P&amp;L</th><th>avg R</th><th>capture</th><th>void</th></tr></thead>
      <tbody>${repRows}</tbody>
    </table>
    <div class="bd-section">Runs (${ss.length}) <span class="muted small">— click a row to open it</span></div>
    <table class="bd-table">
      <thead><tr><th>ticker</th><th>date</th><th>version</th><th>initiated</th><th>completed</th><th>status</th><th>result</th></tr></thead>
      <tbody>${runRows}</tbody>
    </table>`;

  bd.querySelectorAll("tr.run").forEach(tr => {
    tr.addEventListener("click", (e) => {
      const id = tr.dataset.id;
      if (e.metaKey || e.ctrlKey) {
        window.open(`/viewer/index.html?session=${encodeURIComponent(id)}`, "_blank");
      } else {
        loadSession(id, true);
      }
    });
  });
  const back = document.getElementById("bd-back");
  if (back) back.onclick = closeBatch;
}

// ---------- DETAIL RENDER ----------

function renderHeader(view) {
  const sess = view.session || {};
  const s = sess.setup || {};
  const pnl = view.pnl || {};

  document.getElementById("h-ticker").textContent = sess.ticker || "—";
  document.getElementById("h-date").textContent =
    `${sess.historical_date || ""} · run ${sess.real_run_ts || ""}`;

  const statusEl = document.getElementById("h-status");
  statusEl.textContent = `${sess.mode || "simulated"} ${sess.status || "running"}`;
  statusEl.className = `badge ${sess.status === "complete" ? "complete" : "running"}`;

  const badge = document.getElementById("h-pnl");
  badge.className = "badge";
  if (pnl && pnl.traded) {
    badge.textContent = `${pnl.realized_pnl >= 0 ? "+" : ""}$${pnl.realized_pnl}  ·  ${pnl.r_multiple}R  ·  ${pnl.win ? "WIN" : "LOSS"}`;
    badge.classList.add(pnl.win ? "win" : "loss");
  } else if (view.is_live) {
    badge.textContent = "running";
    badge.classList.add("flat");
  } else {
    badge.textContent = "no trade";
    badge.classList.add("flat");
  }

  document.getElementById("h-chips").innerHTML =
    chip("gap", s.gap_pct != null ? `+${s.gap_pct}%` : null) +
    chip("RVOL", s.rvol != null ? `${s.rvol}×` : null) +
    chip("float", s.float_shares != null ? fmtFloat(s.float_shares) : null) +
    chip("anchor(5m)", s.anchor_px != null ? `$${s.anchor_px}` : null) +
    chip("entry", pnl && pnl.entry_avg ? `$${pnl.entry_avg}` : null) +
    chip("MFE", pnl && pnl.mfe_pct != null ? `+${pnl.mfe_pct}%` : null);

  document.getElementById("h-levels").innerHTML =
    chip("prior close", s.prior_close) + chip("prior high", s.prior_high) +
    chip("prior low", s.prior_low) + chip("pm high", s.pm_high) +
    chip("pm low", s.pm_low);

  document.getElementById("h-reason").textContent = s.reason || "";

  // Live indicator
  const liveInd = document.getElementById("live-indicator");
  if (view.is_live) {
    liveInd.classList.remove("hidden");
  } else {
    liveInd.classList.add("hidden");
  }

  // Finalize button only makes sense for running (not-yet-complete) sessions
  const finBtn = document.getElementById("finalize-btn");
  if (finBtn) {
    finBtn.style.display = view.is_live ? "" : "none";
  }
}

function renderBlotter(actions) {
  const tb = document.querySelector("#blotter tbody");
  if (!actions || !actions.length) {
    tb.innerHTML = `<tr><td colspan="6" class="muted">no fills</td></tr>`;
    return;
  }
  tb.innerHTML = actions.map((a) => {
    const rc = a.realized_delta > 0 ? "pos" : a.realized_delta < 0 ? "neg" : "";
    return `<tr>
      <td>${a.time}</td>
      <td class="${a.side}">${a.side.toUpperCase()}</td>
      <td>${a.shares}</td>
      <td>$${a.price}</td>
      <td class="${rc}">${a.realized_delta ? (a.realized_delta > 0 ? "+" : "") + "$" + a.realized_delta : "—"}</td>
      <td class="muted">${escapeHtml((a.reason || "").slice(0, 80))}</td>
    </tr>`;
  }).join("");
}

function renderChart(bars, actions, sess, preserveView = false) {
  const el = document.getElementById("chart");

  // If asked to preserve the view (a live refresh), remember the user's current
  // zoom/scroll so a new bar arriving doesn't yank them back to fit-all.
  let prevRange = null;
  if (preserveView && currentChart && currentChart.timeScale) {
    try { prevRange = currentChart.timeScale().getVisibleLogicalRange(); } catch (_) {}
  }

  // Destroy previous chart if exists. Disconnect its ResizeObserver first —
  // otherwise each live re-render leaks an observer that keeps firing
  // applyOptions() on the disposed chart.
  if (currentChart && currentChart.remove) {
    try { if (currentChart._ro) currentChart._ro.disconnect(); } catch (_) {}
    try { currentChart.remove(); } catch (_) {}
    currentChart = null;
  }

  if (!bars || !bars.length) {
    el.innerHTML = `<div class="muted" style="padding:16px">no bars revealed yet</div>`;
    return null;
  }

  // Clear any leftover placeholder ("no bars revealed yet") before creating the
  // chart — createChart only *appends* its canvas, so a stale placeholder would
  // sit above it, steal vertical space, and hide the time axis / lower chart.
  el.innerHTML = "";

  const chart = LightweightCharts.createChart(el, {
    layout: { background: { color: col("--panel") }, textColor: col("--txt") },
    grid: { vertLines: { color: col("--line") }, horzLines: { color: col("--line") } },
    rightPriceScale: {
      visible: true,
      borderColor: col("--line"),
    },
    timeScale: { borderColor: col("--line"), timeVisible: true, secondsVisible: false },
    crosshair: { mode: LightweightCharts.CrosshairMode.Normal },
    width: el.clientWidth, height: el.clientHeight,
  });

  const candle = chart.addCandlestickSeries({
    upColor: col("--green"), downColor: col("--red"),
    borderUpColor: col("--green"), borderDownColor: col("--red"),
    wickUpColor: col("--green"), wickDownColor: col("--red"),
  });
  candle.setData(bars.map((b) => ({ time: b.t, open: b.o, high: b.h, low: b.l, close: b.c })));

  // Configure main price scale after main series to reserve space for subcharts below.
  // Main candles now take ~75% of height; MACD ~15%, volume ~10%.
  chart.priceScale('right').applyOptions({
    scaleMargins: { top: 0, bottom: 0.25 },
    visible: true,   // show Y-axis for candles so user can see and scale prices
  });

  // Overlays (VWAP/EMAs) belong on the main price scale (right)
  const vwapData = bars.filter((b) => b.vwap != null).map((b) => ({ time: b.t, value: b.vwap }));
  if (vwapData.length) {
    const vwap = chart.addLineSeries({
      color: col("--vwap"),
      lineWidth: 2,
      priceLineVisible: false,
      lastValueVisible: false,
    });
    vwap.setData(vwapData);
  }

  const emaData = bars.filter((b) => b.ema9 != null).map((b) => ({ time: b.t, value: b.ema9 }));
  if (emaData.length) {
    const ema = chart.addLineSeries({
      color: col("--ema"),
      lineWidth: 1,
      priceLineVisible: false,
      lastValueVisible: false,
    });
    ema.setData(emaData);
  }

  const ema20Data = bars.filter((b) => b.ema20 != null).map((b) => ({ time: b.t, value: b.ema20 }));
  if (ema20Data.length) {
    const ema20 = chart.addLineSeries({
      color: col("--ema2"),
      lineWidth: 1,
      priceLineVisible: false,
      lastValueVisible: false,
    });
    ema20.setData(ema20Data);
  }

  // Volume subchart (bottom pane)
  const vol = chart.addHistogramSeries({
    priceFormat: { type: "volume" },
    priceScaleId: "vol",
  });
  vol.setData(bars.map((b) => ({
    time: b.t, value: b.v,
    color: (b.c >= b.o) ? "rgba(38,166,154,.55)" : "rgba(239,83,80,.55)",
  })));
  chart.priceScale("vol").applyOptions({
    scaleMargins: { top: 0.90, bottom: 0 },
    visible: false,
  });

  // MACD histogram subchart (middle pane, above volume)
  const macdData = bars.filter((b) => b.macd_hist != null).map((b) => ({
    time: b.t, value: b.macd_hist,
    color: (b.macd_hist >= 0) ? "rgba(38,166,154,.65)" : "rgba(239,83,80,.65)",
  }));
  if (macdData.length) {
    const macd = chart.addHistogramSeries({
      priceScaleId: "macd",
      priceLineVisible: false,
      lastValueVisible: false,
    });
    macd.setData(macdData);
    chart.priceScale("macd").applyOptions({
      scaleMargins: { top: 0.75, bottom: 0.10 },
      visible: false,
    });
  }

  // levels from setup
  const setup = (sess && sess.setup) || {};
  const lvl = (price, color, title, style) =>
    price != null && candle.createPriceLine({
      price, color, lineWidth: 1, title,
      lineStyle: style ?? LightweightCharts.LineStyle.Dashed, axisLabelVisible: true,
    });

  lvl(setup.pm_high, col("--pm"), "pm high");
  lvl(setup.pm_low, col("--pm"), "pm low", LightweightCharts.LineStyle.Dotted);
  lvl(setup.prior_close, col("--muted"), "prior close", LightweightCharts.LineStyle.Dotted);

  const entry = (actions || []).find((a) => a.side === "buy");
  if (entry) lvl(entry.price, col("--entry"), "entry", LightweightCharts.LineStyle.Solid);

  // markers
  candle.setMarkers((actions || []).map((a) => ({
    time: a.t,
    position: a.side === "buy" ? "belowBar" : "aboveBar",
    color: a.side === "buy" ? col("--entry") : col("--stop"),
    shape: a.side === "buy" ? "arrowUp" : "arrowDown",
    text: `${a.side === "buy" ? "BUY" : "SELL"} ${a.shares}@${a.price}`,
  })));

  // Restore the prior zoom on a live refresh; otherwise fit the whole series.
  if (prevRange) {
    try { chart.timeScale().setVisibleLogicalRange(prevRange); }
    catch (_) { chart.timeScale().fitContent(); }
  } else {
    chart.timeScale().fitContent();
  }
  chart._candle = candle;   // referenced by the timeline for crosshair linking

  // Ensure proper size (important inside flex layouts)
  const resizeChart = () => {
    if (el.clientWidth > 0 && el.clientHeight > 0) {
      chart.applyOptions({ width: el.clientWidth, height: el.clientHeight });
    }
  };

  resizeChart();

  // resize observer (kept on the chart so the next render can disconnect it)
  const ro = new ResizeObserver(resizeChart);
  ro.observe(el);
  chart._ro = ro;

  // Store resize for external calls if needed
  chart._resize = resizeChart;

  currentChart = chart;
  return chart;
}

function renderTimeline(decisions, chart) {
  const wrap = document.getElementById("timeline");
  document.getElementById("t-count").textContent = decisions && decisions.length ? `(${decisions.length} turns)` : "";

  if (!decisions || !decisions.length) {
    wrap.innerHTML = `<div class="muted">no decisions logged yet</div>`;
    return;
  }

  wrap.innerHTML = decisions.map((d) => {
    const pos = d.position_shares
      ? `<span class="pos muted">${d.position_shares}sh @ $${d.avg_entry}</span>`
      : `<span class="pos muted">flat</span>`;
    const u = d.unrealized || 0;
    const ucls = u > 0 ? "pos-v" : u < 0 ? "neg-v" : "";
    const r = d.realized_to_date || 0;
    const rcls = r > 0 ? "pos-v" : r < 0 ? "neg-v" : "";
    const stop = d.stop != null ? ` · stop $${d.stop}` : "";
    return `<div class="turn" data-t="${d.t || ""}" data-c="${d.close != null ? d.close : ""}" data-i="${d.i}">
      <div class="top">
        <span class="time">${d.time}</span>
        <span class="act act-${d.action}">${d.action}</span>
        ${pos}
      </div>
      <div class="thought">${escapeHtml(d.thought || "")}</div>
      <div class="pnl muted">uPnL <span class="${ucls}">$${u}</span> · realized <span class="${rcls}">$${r}</span>${stop}</div>
    </div>`;
  }).join("");

  const turns = [...wrap.querySelectorAll(".turn")];

  const select = (t, scrollList) => {
    turns.forEach((el) => el.classList.toggle("sel", String(el.dataset.t) === String(t)));
    const sel = turns.find((el) => String(el.dataset.t) === String(t));
    if (chart && chart._candle && sel && chart.setCrosshairPosition) {
      const price = sel.dataset.c ? +sel.dataset.c : 0;
      chart.setCrosshairPosition(price, +t, chart._candle);
    }
    if (scrollList && sel) sel.scrollIntoView({ block: "nearest", behavior: "smooth" });
  };

  turns.forEach((el) => el.addEventListener("click", () => select(el.dataset.t, false)));

  // chart click → highlight the nearest decision at/just before the clicked bar
  if (chart && chart.subscribeClick) {
    chart.subscribeClick((p) => {
      if (!p || p.time == null) return;
      const ts = turns.map((el) => +el.dataset.t).filter((x) => x <= p.time);
      if (ts.length) select(Math.max(...ts), true);
    });
  }

  wrap._turns = turns;
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
}

function highlightCurrentSession() {
  const listEl = document.getElementById("session-list");
  if (!listEl) return;
  listEl.querySelectorAll(".sess-card").forEach(card => {
    card.classList.toggle("selected", card.dataset.id === currentSessionId);
  });
}

// ---------- Load session detail ----------

async function loadSession(sessionId, updateUrl = false) {
  const detail = document.getElementById("session-detail");
  const placeholder = document.getElementById("no-session");

  placeholder.classList.add("hidden");
  detail.classList.remove("hidden");

  // leaving any open batch view: hide it and stop its poll (but keep the tag
  // highlighted in the sidebar so the user can get back to it)
  document.getElementById("batch-detail").classList.add("hidden");
  if (batchRefreshTimer) { clearInterval(batchRefreshTimer); batchRefreshTimer = null; }

  currentSessionId = sessionId;

  // cleanup previous SSE
  if (currentEventSource) {
    currentEventSource.close();
    currentEventSource = null;
  }
  if (pollFallbackTimer) {
    clearInterval(pollFallbackTimer);
    pollFallbackTimer = null;
  }

  try {
    const view = await getJSON(`/api/session/${encodeURIComponent(sessionId)}/state`);

    // Render everything
    renderHeader(view);
    renderBlotter(view.actions || []);
    const chart = renderChart(view.bars || [], view.actions || [], view.session);
    renderTimeline(view.decisions || [], chart);

    if (chart) {
      currentChart = chart;
      // ensure sizing after DOM layout
      setTimeout(() => {
        if (chart._resize) chart._resize();
      }, 30);
    }

    // Setup live updates if needed
    if (view.is_live) {
      setupLiveUpdates(sessionId);
    }

    // Wire buttons (onclick will be attached even if hidden; harmless)
    wireDetailButtons(sessionId);

    // Highlight in sidebar
    highlightCurrentSession();

  } catch (e) {
    detail.classList.add("hidden");
    placeholder.classList.remove("hidden");
    fail(`Could not load session ${sessionId}: ${e}`);
  }
}

function setupLiveUpdates(sessionId) {
  // Prefer SSE
  try {
    const es = new EventSource(`/api/session/${encodeURIComponent(sessionId)}/events`);
    currentEventSource = es;

    es.onmessage = (ev) => {
      // Any message (including heartbeats or update) → refresh state
      if (currentSessionId === sessionId) {
        refreshCurrentSession();
      }
    };

    es.onerror = () => {
      // Fall back to light polling if SSE drops
      if (!pollFallbackTimer && currentSessionId === sessionId) {
        pollFallbackTimer = setInterval(() => {
          if (currentSessionId === sessionId) refreshCurrentSession();
        }, 2500);
      }
    };
  } catch (e) {
    // Very old browser or blocked — fallback polling
    pollFallbackTimer = setInterval(() => {
      if (currentSessionId === sessionId) refreshCurrentSession();
    }, 2000);
  }
}

async function refreshCurrentSession() {
  if (!currentSessionId) return;
  try {
    const view = await getJSON(`/api/session/${encodeURIComponent(currentSessionId)}/state`);

    // Update header + pnl
    renderHeader(view);

    // Incremental-friendly updates
    const blotter = document.querySelector("#blotter tbody");
    if (blotter) {
      // Simple approach: re-render blotter (small)
      renderBlotter(view.actions || []);
    }

    // For chart + timeline we do a light full re-render of data
    // (lightweight-charts is fast enough for 720 bars)
    const chartContainer = document.getElementById("chart");
    if (chartContainer && view.bars && view.bars.length) {
      // preserveView=true: keep the user's zoom/scroll as new live bars stream in
      const chart = renderChart(view.bars, view.actions || [], view.session, true);
      renderTimeline(view.decisions || [], chart);
    }

    // If the session has just finalized, tear down live updates and refresh the
    // sidebar so its badge flips running → complete automatically (no manual
    // refresh needed).
    if (!view.is_live) {
      if (currentEventSource) { currentEventSource.close(); currentEventSource = null; }
      if (pollFallbackTimer) { clearInterval(pollFallbackTimer); pollFallbackTimer = null; }
      loadAndRenderList();
    }
  } catch (e) {
    // silent fail on transient errors during live
  }
}

function wireDetailButtons(sessionId) {
  // Finalize
  const finBtn = document.getElementById("finalize-btn");
  if (finBtn) {
    finBtn.onclick = async () => {
      finBtn.disabled = true;
      finBtn.textContent = "Finalizing...";
      try {
        await fetch(`/api/session/${encodeURIComponent(sessionId)}/finalize`, { method: "POST" });
        // After finalize, reload the (now complete) view
        await loadSession(sessionId);
      } catch (e) {
        alert("Finalize failed: " + e);
      } finally {
        finBtn.disabled = false;
        finBtn.textContent = "Finalize";
      }
    };
  }

  // Small refresh
  const refBtn = document.getElementById("refresh-btn");
  if (refBtn) {
    refBtn.onclick = () => refreshCurrentSession();
  }
}

// ---------- Boot ----------

async function main() {
  const sessionFromUrl = qs("session");
  const batchFromUrl = qs("batch");

  // Always render fresh session list on startup
  await loadAndRenderList();

  // Wire sidebar tabs
  document.getElementById("tab-sessions").onclick = () => setTab("sessions");
  document.getElementById("tab-batches").onclick = () => setTab("batches");

  // Wire global refresh button — refreshes whichever tab is active
  const refreshList = document.getElementById("refresh-list-btn");
  if (refreshList) {
    refreshList.onclick = () =>
      activeTab === "batches" ? loadAndRenderBatches() : loadAndRenderList();
  }

  if (batchFromUrl) {
    setTab("batches");
    await openBatch(batchFromUrl);
  } else if (sessionFromUrl) {
    await loadSession(sessionFromUrl);
  } else {
    // Show list + placeholder (user can click)
    document.getElementById("no-session").classList.remove("hidden");
    document.getElementById("session-detail").classList.add("hidden");
  }

  // Light auto-refresh of the active sidebar list every 20s so new sessions /
  // batches appear and statuses stay current, even while a detail view is open.
  // (Immediate flips for the session/batch you're watching are handled by
  // refreshCurrentSession / scheduleBatchRefresh.)
  setInterval(
    () => (activeTab === "batches" ? loadAndRenderBatches() : loadAndRenderList()),
    20000
  );
}

main().catch((e) => fail(e.stack || String(e)));