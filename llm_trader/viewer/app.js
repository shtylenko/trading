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
// The sidebar only lists top-level (batch/live-day) cards, never individual
// ticker leaves — so highlighting has to track "which top card is this leaf
// under," separately from currentSessionId (the exact thing being viewed).
let currentTopSessionId = null;
let currentChart = null;
let currentEventSource = null;
let pollFallbackTimer = null;
let tickersRefreshTimer = null;   // live re-poll of the tickers table while a batch runs
// Full /api/sessions payload for the sidebar. When a session is open we filter
// the sidebar to the same strategy family only.
let allSidebarSessions = [];
let sidebarStrategy = null;  // e.g. "cup_handle" | "warrior" | null (show all)

// Show exactly one main-area pane. Single helper replacing the classList +
// style.display toggles that used to be duplicated at every call site.
function showPane(name) {
  ["no-session", "session-tickers", "session-detail"].forEach((id) => {
    const el = document.getElementById(id);
    if (!el) return;
    const on = id === name;
    el.classList.toggle("hidden", !on);
    el.style.display = on ? "" : "none";
  });
}

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
  if (!r.ok) {
    let msg = `${url} → HTTP ${r.status}`;
    try {
      const body = await r.json();
      if (body && body.error) msg += ` - ${body.error}`;
    } catch {}
    throw new Error(msg);
  }
  return r.json();
}

function chip(label, val) {
  if (val === null || val === undefined || val === "") return "";
  return `<span class="chip">${label} <b>${val}</b></span>`;
}

const fmtFloat = (f) => (f ? (f / 1e6).toFixed(1) + "M" : "n/a");

// ---------- LIST ----------

function setSidebarStrategy(strategy) {
  /** Restrict the left sidebar to one strategy family (or null = show all). */
  const next = strategy || null;
  if (next === sidebarStrategy) {
    highlightCurrentSession();
    return;
  }
  sidebarStrategy = next;
  renderSidebarList();
}

function sessionsForSidebar() {
  if (!sidebarStrategy) return allSidebarSessions;
  return allSidebarSessions.filter(
    (s) => (s.strategy || "warrior") === sidebarStrategy
  );
}

function renderSidebarList() {
  const listEl = document.getElementById("session-list");
  if (!listEl) return;
  listEl.style.display = "block";
  listEl.classList.remove("hidden");

  const sessions = sessionsForSidebar();
  const total = allSidebarSessions.length;
  const countEl = document.getElementById("session-count");
  if (countEl) {
    countEl.textContent = sidebarStrategy
      ? `(${sessions.length}/${total} · ${sidebarStrategy})`
      : `(${total})`;
  }

  // Filter chip under the Sessions header when scoped to a strategy
  let filterBar = document.getElementById("sidebar-strategy-filter");
  if (!filterBar) {
    const header = document.querySelector(".sidebar-header");
    if (header) {
      filterBar = document.createElement("div");
      filterBar.id = "sidebar-strategy-filter";
      filterBar.className = "sidebar-strategy-filter muted small";
      header.insertAdjacentElement("afterend", filterBar);
    }
  }
  if (filterBar) {
    if (sidebarStrategy) {
      filterBar.innerHTML =
        `Showing <b class="strat-${escapeHtml(sidebarStrategy)}">${escapeHtml(sidebarStrategy)}</b> only` +
        ` · <a href="#" id="sidebar-show-all">show all</a>`;
      filterBar.classList.remove("hidden");
      const showAll = document.getElementById("sidebar-show-all");
      if (showAll) {
        showAll.onclick = (e) => {
          e.preventDefault();
          setSidebarStrategy(null);
        };
      }
    } else {
      filterBar.innerHTML = "";
      filterBar.classList.add("hidden");
    }
  }

  if (!sessions.length) {
    listEl.innerHTML = sidebarStrategy
      ? `<div class="muted" style="padding:12px">No ${escapeHtml(sidebarStrategy)} sessions.</div>`
      : `<div class="muted" style="padding:12px">No sessions yet.</div>`;
    return sessions;
  }

  listEl.innerHTML = sessions.map((s) => {
    const type = s.type || "simulated";
    const isLive = type === "live";
    const pnlStr = s.pnl != null ? fmtMoney(s.pnl) : "—";
    const wr = s.win_rate != null ? `${s.win_rate}%` : "—";
    const badgeClass = isLive ? "live" : "sim";
    const badgeLabel = isLive ? "live" : "sim";
    const strat = s.strategy || "warrior";

    const displayId = s.name && s.name !== s.id
      ? `${escapeHtml(s.name)} (${escapeHtml(s.id)})`
      : escapeHtml(s.id);
    return `
      <div class="sess-card" data-id="${escapeHtml(s.id)}" data-type="top-session"
           data-strategy="${escapeHtml(strat)}">
        <div class="sess-top">
          <span class="sess-ticker">${displayId}</span>
          <span class="badge ${badgeClass}">${badgeLabel}</span>
          <span class="badge strategy strat-${escapeHtml(strat)}">${escapeHtml(strat)}</span>
        </div>
        <div class="sess-meta muted">${pnlStr} · ${s.n_tickers} tickers · ${s.n_trades} trades</div>
        <div class="sess-summary">win ${wr}</div>
        <div class="sess-meta muted">last ${s.last_activity || "—"}</div>
      </div>`;
  }).join("");

  listEl.querySelectorAll(".sess-card").forEach((card) => {
    const id = card.dataset.id;
    const isTop = card.dataset.type === "top-session";
    card.addEventListener("click", (e) => {
      if (e.metaKey || e.ctrlKey) {
        window.open(`/viewer/index.html?session=${encodeURIComponent(id)}`, "_blank");
      } else {
        currentSessionId = id;
        currentTopSessionId = id;
        // Scope sidebar to this card's strategy immediately
        setSidebarStrategy(card.dataset.strategy || "warrior");
        highlightCurrentSession();
        if (isTop) {
          loadSessionTickers(id, true);
        } else {
          loadSession(id, true);
        }
        history.replaceState(null, "", `?session=${encodeURIComponent(id)}`);
      }
    });
    card.addEventListener("auxclick", (e) => {
      if (e.button === 1) {
        window.open(`/viewer/index.html?session=${encodeURIComponent(id)}`, "_blank");
      }
    });
  });

  highlightCurrentSession();
  return sessions;
}

async function loadAndRenderList() {
  const listEl = document.getElementById("session-list");
  listEl.style.display = "block";
  listEl.classList.remove("hidden");
  // Do not touch main-pane visibility here (no-session / tickers / detail).
  listEl.innerHTML = `<div class="muted" style="padding:8px">Loading sessions...</div>`;

  try {
    const data = await getJSON("/api/sessions");
    allSidebarSessions = data.sessions || [];
    console.log("Sessions from API:", allSidebarSessions.length, "filter=", sidebarStrategy);
    return renderSidebarList();
  } catch (e) {
    listEl.innerHTML = `<div class="muted" style="padding:8px;color:#f88">Failed to load list: ${e}</div>`;
    console.error("Failed to load sessions list", e);
    return [];
  }
}

// (Batches view removed — everything is grouped under Sessions now.)

// ---------- FULL-PAGE TABLE (default view, no session selected) ----------

// Columns shown in the full-width session table. `num` drives right-alignment
// and numeric sorting.
const TABLE_COLS = [
  { key: "name",          label: "Session",       num: false },
  { key: "type",          label: "Type",          num: false },
  { key: "strategy",      label: "Strategy",      num: false },
  { key: "status",        label: "Status",        num: false },
  { key: "version",       label: "Version",       num: false },
  { key: "model",         label: "Model",         num: false },
  { key: "last_activity", label: "Last activity", num: false },
  { key: "n_tickers",     label: "Tickers",       num: true  },
  { key: "n_trades",      label: "Trades",        num: true  },
  { key: "n_fills",       label: "Fills",         num: true  },
  { key: "win_rate",      label: "Win %",         num: true  },
  { key: "expectancy_r",  label: "Exp R",         num: true  },
  { key: "effective_r",   label: "Eff R",         num: true  },
  { key: "avg_win_r",     label: "Avg Win R",     num: true  },
  { key: "avg_loss_r",    label: "Avg Loss R",    num: true  },
  { key: "profit_factor_r", label: "PF",          num: true  },
  { key: "n_void",        label: "Void",          num: true  },
  { key: "pnl",           label: "P&L",           num: true  },
];

// Sort comparator for a column. Nulls always sort last regardless of direction.
function sessionCmp(key, dir) {
  const mult = dir === "asc" ? 1 : -1;
  const val = (s) => (key === "name" ? (s.name || s.id) : s[key]);
  return (a, b) => {
    const va = val(a), vb = val(b);
    const na = va == null || va === "";
    const nb = vb == null || vb === "";
    if (na && nb) return 0;
    if (na) return 1;
    if (nb) return -1;
    if (typeof va === "number" && typeof vb === "number") return (va - vb) * mult;
    return String(va).localeCompare(String(vb)) * mult;
  };
}

// Full unfiltered session list for the table view. The dropdown filters re-render
// the table from this without re-fetching.
let allSessions = [];

// Dropdown filters shown above the session table. `norm` maps a session row to the
// value the dropdown filters on (and shows as its option label); nulls collapse to "—".
const TABLE_FILTERS = [
  { key: "strategy", label: "Strategy", norm: (s) => s.strategy || "warrior" },
  { key: "type",     label: "Type",     norm: (s) => s.type || "simulated" },
  { key: "version",  label: "Version",  norm: (s) => s.version || "—" },
  { key: "model",    label: "Model",    norm: (s) => s.model || "—" },
];

// Distinct filter values present across all sessions, sorted for a stable dropdown.
const distinctFilterVals = (norm) =>
  [...new Set(allSessions.map(norm))].sort((a, b) => String(a).localeCompare(String(b)));

// Predicate combining every active (non-"All") dropdown. Selections live in the URL
// so a sort-reload preserves them and the view is deep-linkable.
function sessionFilterFn() {
  const active = TABLE_FILTERS
    .map((f) => ({ f, val: qs(f.key) }))
    .filter((x) => x.val && x.val !== "All");
  return (s) => active.every((x) => x.f.norm(s) === x.val);
}

function sessionHeadHtml(sortKey, sortDir) {
  return TABLE_COLS.map((c) => {
    const cls = [c.num ? "num" : "", c.key === sortKey ? `sorted-${sortDir}` : ""].filter(Boolean).join(" ");
    return `<th data-key="${c.key}"${cls ? ` class="${cls}"` : ""}>${c.label}</th>`;
  }).join("");
}

function sessionRowHtml(s) {
  const type = s.type || "simulated";
  const isLive = type === "live";
  const display = escapeHtml(s.name || s.id);
  // Compact timestamp: YYYYMMDDHHMM (strip separators, drop seconds).
  const lastAct = s.last_activity ? s.last_activity.replace(/\D/g, "").slice(0, 12) : "—";
  const pnlCls = s.pnl > 0 ? "pos" : s.pnl < 0 ? "neg" : "";
  const wr = s.win_rate != null ? `${s.win_rate}%` : "—";
  const rCls = (v) => (v > 0 ? "pos" : v < 0 ? "neg" : "");
  // Expectancy cell: clean expectancy (= mean R) with std dispersion appended.
  const expCell = s.expectancy_r != null
    ? `${s.expectancy_r.toFixed(2)}${s.std_r != null ? ` <span class="muted small">±${s.std_r.toFixed(2)}</span>` : ""}`
    : "—";
  const effCell = s.effective_r != null ? s.effective_r.toFixed(2) : "—";
  const avgWinCell = s.avg_win_r != null ? s.avg_win_r.toFixed(2) : "—";
  const avgLossCell = s.avg_loss_r != null ? s.avg_loss_r.toFixed(2) : "—";
  const pfCell = s.profit_factor_r != null ? s.profit_factor_r.toFixed(2) : "—";
  const voidCell = s.n_void != null
    ? (s.n_void > 0 ? `<span class="neg">${s.n_void}</span>` : "0")
    : "—";
  // ongoing vs completed; while running, show finalized/planned progress
  const running = s.status === "running";
  const prog = (s.planned && s.n_complete != null && s.n_complete < s.planned)
    ? ` ${Math.round((s.n_complete / s.planned) * 100)}%` : "";
  const ooc = s.n_out_of_credits > 0
    ? ` <span class="badge out-of-credits" title="${s.n_out_of_credits} run(s) out of API credits (HTTP 402) — excluded from stats, not void">⚠ ${s.n_out_of_credits} no credits</span>`
    : "";
  const tout = s.n_timed_out > 0
    ? ` <span class="badge timeout" title="${s.n_timed_out} run(s) killed after the per-setup timeout (retries exhausted) — a failure, excluded from stats, not complete; re-run with --resume">⚠ ${s.n_timed_out} timed out</span>`
    : "";
  const statusCell = (running
    ? `<span class="badge running">● running${prog}</span>`
    : `<span class="badge complete">done</span>`) + ooc + tout;
  // Row tint by rule-set lifecycle: base=green, candidate=blue, rejected=red.
  const vrowCls = s.version_status ? ` vrow-${s.version_status}` : "";
  const strat = s.strategy || "warrior";
  return `<tr class="srow${vrowCls}" data-id="${escapeHtml(s.id)}">
      <td>${display}</td>
      <td><span class="badge ${isLive ? "live" : "sim"}">${isLive ? "live" : "sim"}</span></td>
      <td><span class="badge strategy strat-${escapeHtml(strat)}">${escapeHtml(strat)}</span></td>
      <td>${statusCell}</td>
      <td>${s.version ? escapeHtml(s.version) : "—"}</td>
      <td>${s.model ? escapeHtml(s.model) : "—"}</td>
      <td>${lastAct}</td>
      <td class="num">${s.n_tickers}</td>
      <td class="num">${s.n_trades}</td>
      <td class="num">${s.n_fills != null ? s.n_fills : "—"}</td>
      <td class="num">${wr}</td>
      <td class="num ${rCls(s.expectancy_r)}">${expCell}</td>
      <td class="num ${rCls(s.effective_r)}">${effCell}</td>
      <td class="num pos">${avgWinCell}</td>
      <td class="num neg">${avgLossCell}</td>
      <td class="num">${pfCell}</td>
      <td class="num">${voidCell}</td>
      <td class="num ${pnlCls}">${s.pnl != null ? fmtMoney(s.pnl) : "—"}</td>
    </tr>`;
}

// Render the default full-page session view: a Type / Version / Model dropdown filter
// bar above a sortable table. Selecting a dropdown re-renders the table client-side
// (no reload, no button); header click re-sorts via URL + reload (filters persist in
// the URL). Row click navigates to ?session=<id>; Cmd/Ctrl/middle-click = new tab.
async function renderSessionTable() {
  document.getElementById("app").classList.add("table-view");

  const host = document.getElementById("no-session");
  host.classList.add("session-table-mode");
  host.classList.remove("hidden");
  host.style.display = "";
  host.innerHTML = `<div class="muted" style="padding:8px">Loading sessions…</div>`;

  try {
    const data = await getJSON("/api/sessions");
    allSessions = data.sessions || [];
  } catch (e) {
    host.innerHTML = `<div class="muted" style="padding:12px;color:#f88">Failed to load sessions: ${escapeHtml(String(e))}</div>`;
    return;
  }

  if (!allSessions.length) {
    host.innerHTML = `<div class="muted" style="padding:12px">No sessions yet.</div>`;
    return;
  }

  // Build the filter bar once. Each dropdown = "All" + the distinct values present,
  // preselected from the URL so a sort-reload keeps the current filter.
  const bar = TABLE_FILTERS.map((f) => {
    const cur = qs(f.key) || "All";
    const opts = ["All", ...distinctFilterVals(f.norm)]
      .map((o) => `<option value="${escapeHtml(o)}"${o === cur ? " selected" : ""}>${escapeHtml(o)}</option>`)
      .join("");
    return `<label class="tf"><span class="muted small">${f.label}</span>
      <select data-key="${f.key}">${opts}</select></label>`;
  }).join("");

  host.innerHTML = `
    <div class="table-filters">${bar}<span id="tf-count" class="muted small"></span></div>
    <div id="session-table-host"></div>`;

  // Dropdown change → persist to URL (no reload) and re-render the table immediately.
  host.querySelectorAll(".table-filters select").forEach((sel) => {
    sel.addEventListener("change", () => {
      const p = new URLSearchParams(location.search);
      if (sel.value === "All") p.delete(sel.dataset.key);
      else p.set(sel.dataset.key, sel.value);
      history.replaceState(null, "", location.pathname + (p.toString() ? `?${p}` : ""));
      applySessionFilters();
    });
  });

  applySessionFilters();
}

// Filter `allSessions` by the active dropdowns + current sort, then (re)render the
// table into #session-table-host and rebind header-sort and row-click handlers.
function applySessionFilters() {
  const tableHost = document.getElementById("session-table-host");
  if (!tableHost) return;

  // Sort state lives in the URL so it survives a full-page reload and is deep-linkable.
  const sortKey = TABLE_COLS.some((c) => c.key === qs("sort")) ? qs("sort") : "last_activity";
  const sortDir = qs("dir") === "asc" ? "asc" : "desc";
  const rowsData = allSessions.filter(sessionFilterFn()).sort(sessionCmp(sortKey, sortDir));

  const countEl = document.getElementById("tf-count");
  if (countEl) countEl.textContent = `${rowsData.length} / ${allSessions.length}`;

  if (!rowsData.length) {
    tableHost.innerHTML = `<div class="muted" style="padding:12px">No sessions match the current filters.</div>`;
    return;
  }

  tableHost.innerHTML = `<table class="session-table">
    <thead><tr>${sessionHeadHtml(sortKey, sortDir)}</tr></thead>
    <tbody>${rowsData.map(sessionRowHtml).join("")}</tbody>
  </table>`;

  // Header click → re-sort by that column via URL params + full reload.
  // Same column toggles asc/desc; a new column starts descending.
  tableHost.querySelectorAll("th[data-key]").forEach((th) => {
    th.addEventListener("click", () => {
      const key = th.dataset.key;
      const dir = key === sortKey && sortDir === "desc" ? "asc" : "desc";
      const p = new URLSearchParams(location.search);
      p.set("sort", key);
      p.set("dir", dir);
      location.search = p.toString();  // triggers a full page reload
    });
  });

  // Row click → navigate (full page load) to the session detail view.
  const open = (id, newTab) => {
    const url = `/viewer/index.html?session=${encodeURIComponent(id)}`;
    if (newTab) window.open(url, "_blank");
    else window.location.href = url;
  };
  tableHost.querySelectorAll("tr[data-id]").forEach((tr) => {
    const id = tr.dataset.id;
    tr.addEventListener("click", (e) => open(id, e.metaKey || e.ctrlKey));
    tr.addEventListener("auxclick", (e) => { if (e.button === 1) open(id, true); });
  });
}

async function loadSessionTickers(sessionId, updateUrl = false) {
  const tickersEl = document.getElementById("session-tickers");

  currentTopSessionId = sessionId;
  highlightCurrentSession();

  // Any prior live re-poll is stale now (re-armed below only if still running).
  clearInterval(tickersRefreshTimer);
  tickersRefreshTimer = null;

  // Ensure only the tickers list is visible in the main area (no leftover detail chart).
  // Skip on a background live refresh so we don't yank focus if the user navigated away.
  const isBackgroundRefresh = arguments[2] === true;
  if (!isBackgroundRefresh) {
    showPane("session-tickers");
    tickersEl.innerHTML = `<div class="muted" style="padding:16px">Loading tickers for ${escapeHtml(sessionId)}...</div>`;
  }

  try {
    const v = await getJSON(`/api/session/${encodeURIComponent(sessionId)}`);
    // If the user navigated into a leaf while this was in flight, drop the result.
    if (isBackgroundRefresh && document.getElementById("session-tickers").classList.contains("hidden")) {
      return;
    }
    renderSessionTickers(v);
    // Scope the left sidebar to this batch's strategy only.
    if (!isBackgroundRefresh) {
      setSidebarStrategy(v.strategy || (v.meta && v.meta.strategy) || "warrior");
    }
    // While the batch is still producing / finalizing sessions, re-poll so tickers flip
    // running → complete live. Passes the background flag so it won't grab focus.
    if (v.is_running) {
      tickersRefreshTimer = setInterval(() => loadSessionTickers(sessionId, false, true), 7000);
    }
  } catch (e) {
    if (!isBackgroundRefresh) {
      tickersEl.innerHTML = `<div class="muted" style="padding:16px;color:#f88">Failed to load session: ${e}</div>`;
    }
  }

  if (updateUrl) {
    history.replaceState(null, "", `?session=${encodeURIComponent(sessionId)}`);
  }
}

function renderSessionTickers(v) {
  const bd = document.getElementById("session-tickers");
  const tickers = v.tickers || [];
  const meta = v.meta || {};
  const type = v.type || "simulated";

  const strat = v.strategy || meta.strategy || "warrior";
  let html = `
    <div class="bd-head">
      <span class="small-btn bd-back" id="bd-back">← back to sessions</span>
      <h2>${escapeHtml(v.name || v.id)}</h2>
      <span class="badge ${type === "live" ? "live" : "sim"}">${type}</span>
      <span class="badge strategy strat-${escapeHtml(strat)}">${escapeHtml(strat)}</span>
      <button class="small-btn bd-archive" id="bd-archive" title="Archive this session — hides it from the sessions list and sidebar">Archive</button>
    </div>
    <div class="bd-meta">${meta.model ? `model ${escapeHtml(meta.model)}` : ""} ${meta.version ? `v${escapeHtml(meta.version)}` : ""}</div>`;
  const m = v.metrics || {};
  if (m.clean_expectancy_r != null || m.effective_expectancy_r != null || m.profit_factor_r != null) {
    html += `<div class="bd-metrics" style="font-size:12px; margin:4px 0; padding:4px; background:#222; border-radius:3px;">`;
    if (m.clean_expectancy_r != null) html += `Clean Exp: <b>${m.clean_expectancy_r}R</b> `;
    if (m.effective_expectancy_r != null) html += `Eff Exp: <b>${m.effective_expectancy_r}R</b> `;
    if (m.profit_factor_r != null) html += `PF: <b>${m.profit_factor_r}</b> `;
    if (m.n_planned != null) html += `N=${m.n_planned} (traded ${m.n_traded||0}, void ${m.n_void||0}) `;
    if (m.sequence_drawdown_r != null) html += `SeqDD: <b>${m.sequence_drawdown_r}R</b>`;
    if (m.r_distribution) {
      const d = m.r_distribution;
      html += ` | meanR:${d.mean} med:${d.median} std:${d.std}`;
    }
    html += `</div>`;
  }
  // Progress line: how many tickers have finalized vs are still running.
  if (v.n_tickers != null) {
    const running = v.n_running || 0;
    const complete = v.n_complete || 0;
    html += `<div class="bd-progress">` +
      `progress <b>${complete}/${v.n_tickers}</b> complete` +
      (running ? ` · <b>${running}</b> running` : "") +
      (v.is_running ? ` <span class="badge running">● live</span>` : ` <span class="badge complete">done</span>`) +
      `</div>`;
  }

  html += `<div class="bd-section">Tickers (${tickers.length})</div>
<table class="bd-table">
  <thead><tr><th>ticker</th><th>trades</th><th>R</th><th>P&amp;L</th><th>win %</th><th>status</th></tr></thead>
  <tbody>`;

  if (tickers.length) {
    html += tickers.map(t => {
      const pnlCls = t.pnl > 0 ? "pos" : t.pnl < 0 ? "neg" : "";
      const wr = t.win_rate != null ? `${t.win_rate}%` : "—";
      const rStr = t.r != null ? t.r.toFixed(2) + "R" : "—";
      const st = t.status || "complete";
      const voided = t.n_void > 0;
      const outOfCredits = st === "out_of_credits";
      const timedOut = st === "timeout";
      const rep = t.n_leaves > 1 ? ` ${t.n_complete}/${t.n_leaves}` : "";
      let statusCell;
      if (st === "running") {
        statusCell = `<span class="badge running">running${rep}</span>`;
      } else if (st === "stale") {
        statusCell = `<span class="badge stale">stale</span>`;
      } else if (st === "out_of_credits") {
        statusCell = `<span class="badge out-of-credits" title="agent hit HTTP 402 (out of API credits) — excluded from stats, not a void">out of credits${t.n_out_of_credits > 1 ? ` ×${t.n_out_of_credits}` : ""}</span>`;
      } else if (st === "timeout") {
        statusCell = `<span class="badge timeout" title="run killed after exceeding the per-setup timeout (retries exhausted) — a failure, excluded from stats, not complete; re-run with --resume">timed out${t.n_timed_out > 1 ? ` ×${t.n_timed_out}` : ""}</span>`;
      } else if (voided) {
        statusCell = `<span class="void-badge" title="${escapeHtml(t.void_reason || "voided")}">VOID${t.n_void > 1 ? ` ×${t.n_void}` : ""}</span>`;
      } else {
        statusCell = `<span class="badge complete">complete</span>`;
      }
      // dim finalized-and-voided rows; out-of-credits / timed-out rows dim too (no result)
      const dim = (voided || outOfCredits || timedOut) && st !== "running" ? " voided" : "";
      return `<tr class="run${dim}" data-leaf="${escapeHtml(t.leaf_id)}" data-ticker="${escapeHtml(t.ticker)}">
        <td><b>${escapeHtml(t.ticker)}</b></td>
        <td>${t.n_trades}</td>
        <td>${rStr}</td>
        <td class="${pnlCls}">${fmtMoney(t.pnl)}</td>
        <td>${wr}</td>
        <td>${statusCell}</td>
      </tr>`;
    }).join("");
  } else {
    html += `<tr><td colspan="6" class="muted">no tickers</td></tr>`;
  }

  html += `</tbody></table>`;

  bd.innerHTML = html;

  // back button → return to the full-page session table (top-level view)
  const back = bd.querySelector("#bd-back");
  if (back) back.addEventListener("click", () => {
    window.location.href = "/viewer/index.html";
  });

  // archive button → hide this whole session (all its leaves) from the lists
  const arc = bd.querySelector("#bd-archive");
  if (arc) arc.addEventListener("click", () => archiveSession(v.id, arc));

  // click ticker row -> load detail
  bd.querySelectorAll("tr.run").forEach(tr => {
    tr.addEventListener("click", (e) => {
      const leaf = tr.dataset.leaf;
      const ticker = tr.dataset.ticker;
      if (leaf) {
        loadSession(leaf, true);
      }
    });
  });
}  // close renderSessionTickers

// ---------- DETAIL RENDER ----------

function sessionStrategy(sess) {
  return (
    sess.strategy
    || (sess.config && sess.config.strategy)
    || (sess.skill && sess.skill.strategy)
    || (sess.setup && sess.setup.strategy)
    || "warrior"
  );
}

function isMultiDaySession(sess, bars) {
  const strat = sessionStrategy(sess);
  if (strat && strat !== "warrior") return true;
  const hz = (sess.config && sess.config.horizon) || (sess.skill && sess.skill.horizon);
  if (hz === "multi_day") return true;
  const res = (sess.config && sess.config.bar_resolution) || (sess.skill && sess.skill.bar_resolution);
  if (res === "1day" || res === "daily") return true;
  // Infer from bar payload (SMA present, no VWAP)
  if (bars && bars.length && bars.some((b) => b.sma50 != null) && !bars.some((b) => b.vwap != null)) {
    return true;
  }
  return false;
}

function renderHeader(view) {
  const sess = view.session || {};
  const s = sess.setup || {};
  const pnl = view.pnl || {};
  const strat = sessionStrategy(sess);
  const multiDay = isMultiDaySession(sess, view.bars);

  document.getElementById("h-ticker").textContent = sess.ticker || "—";
  document.getElementById("h-date").textContent =
    `${sess.historical_date || ""} · run ${sess.real_run_ts || ""}`;

  // An out-of-credits run finalized as an empty stand-down (status "complete"), but it
  // never actually ran — the API hit HTTP 402. Show that plainly instead of "complete /
  // no trade", which would misrepresent an infra failure as a disciplined result.
  const outOfCredits = !!sess.out_of_credits;

  const statusEl = document.getElementById("h-status");
  if (outOfCredits) {
    statusEl.textContent = `${sess.mode || "simulated"} · out of credits`;
    statusEl.className = "badge out-of-credits";
    statusEl.title = "agent hit HTTP 402 (out of API credits) — never ran; excluded from stats, not a void";
  } else {
    statusEl.textContent = `${sess.mode || "simulated"} ${sess.status || "running"}`;
    statusEl.className = `badge ${sess.status === "complete" ? "complete" : "running"}`;
    statusEl.title = "";
  }

  const badge = document.getElementById("h-pnl");
  badge.className = "badge";
  if (outOfCredits) {
    badge.textContent = "out of credits";
    badge.classList.add("out-of-credits");
  } else if (pnl && pnl.traded) {
    let txt = `${pnl.realized_pnl >= 0 ? "+" : ""}$${pnl.realized_pnl}  ·  ${pnl.r_multiple}R  ·  ${pnl.win ? "WIN" : "LOSS"}`;
    if (pnl.mae_per_share != null) txt += `  ·  MAE -${pnl.mae_per_share}`;
    badge.textContent = txt;
    badge.classList.add(pnl.win ? "win" : "loss");
  } else if (view.is_live) {
    badge.textContent = "running";
    badge.classList.add("flat");
  } else {
    badge.textContent = "no trade";
    badge.classList.add("flat");
  }

  // Strategy-aware chips
  let chips = chip("strategy", strat);
  if (multiDay) {
    chips +=
      chip("pattern", s.pattern || null) +
      chip("handle", s.handle_high != null ? `$${s.handle_high}` : null) +
      chip("ATR", s.atr != null ? `$${s.atr}` : null) +
      chip("stop", s.stop_px != null ? `$${s.stop_px}` : null) +
      chip("T1", s.target1_px != null ? `$${s.target1_px}` : null) +
      chip("T2", s.target2_px != null ? `$${s.target2_px}` : null) +
      chip("cup depth", s.cup_depth_pct != null ? `${s.cup_depth_pct}%` : null) +
      chip("entry", pnl && pnl.entry_avg ? `$${pnl.entry_avg}` : (s.entry_px != null ? `$${s.entry_px}` : null)) +
      chip("MFE", pnl && pnl.mfe_pct != null ? `+${pnl.mfe_pct}%` : null) +
      chip("MAE", pnl && pnl.mae_pct != null ? `-${pnl.mae_pct}%` : null);
  } else {
    chips +=
      chip("gap", s.gap_pct != null ? `+${s.gap_pct}%` : null) +
      chip("RVOL", s.rvol != null ? `${s.rvol}×` : null) +
      chip("float", s.float_shares != null ? fmtFloat(s.float_shares) : null) +
      chip("anchor(5m)", s.anchor_px != null ? `$${s.anchor_px}` : null) +
      chip("entry", pnl && pnl.entry_avg ? `$${pnl.entry_avg}` : null) +
      chip("MFE", pnl && pnl.mfe_pct != null ? `+${pnl.mfe_pct}%` : null) +
      chip("MAE", pnl && pnl.mae_pct != null ? `-${pnl.mae_pct}%` : null);
  }
  document.getElementById("h-chips").innerHTML = chips;

  if (multiDay) {
    document.getElementById("h-levels").innerHTML =
      chip("entry plan", s.entry_px) +
      chip("stop plan", s.stop_px) +
      chip("T1 plan", s.target1_px) +
      chip("T2 plan", s.target2_px);
  } else {
    document.getElementById("h-levels").innerHTML =
      chip("prior close", s.prior_close) + chip("prior high", s.prior_high) +
      chip("prior low", s.prior_low) + chip("pm high", s.pm_high) +
      chip("pm low", s.pm_low);
  }

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

  // Legend adapts to bar family
  updateLegend(multiDay, view.bars);
}

function updateLegend(multiDay, bars) {
  const el = document.getElementById("legend");
  if (!el) return;
  const has = (k) => bars && bars.some((b) => b[k] != null);
  if (multiDay) {
    el.innerHTML = [
      `<span class="lg lg-c">candles</span>`,
      has("sma20") ? `<span class="lg lg-sma20">SMA20</span>` : "",
      has("sma50") ? `<span class="lg lg-sma50">SMA50</span>` : "",
      has("sma200") ? `<span class="lg lg-sma200">SMA200</span>` : "",
      has("atr14") ? `<span class="lg lg-atr">ATR</span>` : "",
      `<span class="lg lg-entry">entry</span>`,
      `<span class="lg lg-stop">exit / stop</span>`,
      `<span class="lg lg-plan">plan levels</span>`,
    ].filter(Boolean).join(" ");
  } else {
    el.innerHTML = [
      `<span class="lg lg-c">candles</span>`,
      has("vwap") ? `<span class="lg lg-vwap">VWAP</span>` : "",
      has("ema9") ? `<span class="lg lg-ema">EMA9</span>` : "",
      has("ema20") ? `<span class="lg lg-ema2">EMA20</span>` : "",
      has("macd_hist") ? `<span class="lg lg-macd">MACD hist</span>` : "",
      `<span class="lg lg-entry">entry</span>`,
      `<span class="lg lg-stop">exit</span>`,
      `<span class="lg lg-pm">pm/levels</span>`,
    ].filter(Boolean).join(" ");
  }
}

function fmtWhen(row, multiDay) {
  /** Display clock for blotter / timeline: date+time on multi-day, time only intraday. */
  if (!row) return "—";
  const time = row.time || "";
  const date = row.date || "";
  if (multiDay && date) {
    const md = date.length >= 10 ? date.slice(5) : date; // YYYY-MM-DD → MM-DD
    // Daily bars are all "16:00"; date alone is clearer than "06-20 16:00".
    if (time === "16:00" || !time) return md;
    return `${md} ${time}`.trim();
  }
  return time || date || "—";
}

function renderBlotter(actions, multiDay = false, bars = null) {
  const tb = document.querySelector("#blotter tbody");
  const head = document.querySelector("#blotter thead tr");
  if (head) {
    head.innerHTML = multiDay
      ? `<th>when</th><th>side</th><th>shares</th><th>price</th><th>realized</th><th>reason</th>`
      : `<th>time</th><th>side</th><th>shares</th><th>price</th><th>realized</th><th>reason</th>`;
  }
  if (!actions || !actions.length) {
    tb.innerHTML = `<tr><td colspan="6" class="muted">no fills</td></tr>`;
    return;
  }
  // Old artifacts may lack action.date; recover from the bar at the same index.
  const barDateByI = {};
  (bars || []).forEach((b) => {
    if (b && b.i != null && b.date) barDateByI[b.i] = b.date;
  });
  tb.innerHTML = actions.map((a) => {
    const rc = a.realized_delta > 0 ? "pos" : a.realized_delta < 0 ? "neg" : "";
    const whenRow = {
      time: a.time,
      date: a.date || barDateByI[a.i] || "",
    };
    return `<tr>
      <td>${escapeHtml(fmtWhen(whenRow, multiDay))}</td>
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

  if (preserveView && currentChart && currentChart._series) {
    const s = currentChart._series;
    if (s.candle) {
      s.candle.setData(bars.map((b) => ({ time: b.t, open: b.o, high: b.h, low: b.l, close: b.c })));
    }
    if (s.vwap) {
      s.vwap.setData(bars.filter((b) => b.vwap != null).map((b) => ({ time: b.t, value: b.vwap })));
    }
    if (s.ema) {
      s.ema.setData(bars.filter((b) => b.ema9 != null).map((b) => ({ time: b.t, value: b.ema9 })));
    }
    if (s.ema20) {
      s.ema20.setData(bars.filter((b) => b.ema20 != null).map((b) => ({ time: b.t, value: b.ema20 })));
    }
    if (s.vol) {
      s.vol.setData(bars.map((b) => ({
        time: b.t, value: b.v,
        color: (b.c >= b.o) ? "rgba(38,166,154,.55)" : "rgba(239,83,80,.55)",
      })));
    }
    if (s.macd) {
      s.macd.setData(bars.filter((b) => b.macd_hist != null).map((b) => ({
        time: b.t, value: b.macd_hist,
        color: (b.macd_hist >= 0) ? "rgba(38,166,154,.65)" : "rgba(239,83,80,.65)",
      })));
    }
    if (s.candle) {
      s.candle.setMarkers((actions || []).map((a) => ({
        time: a.t,
        position: a.side === "buy" ? "belowBar" : "aboveBar",
        color: a.side === "buy" ? col("--entry") : col("--stop"),
        shape: a.side === "buy" ? "arrowUp" : "arrowDown",
        text: `${a.side === "buy" ? "BUY" : "SELL"} ${a.shares}@${a.price}`,
      })));
    }
    if (s.buyDots) {
      s.buyDots.setData((actions || []).filter((a) => a.side === "buy").map((a) => ({ time: a.t, value: a.price })));
    }
    if (s.sellDots) {
      s.sellDots.setData((actions || []).filter((a) => a.side === "sell").map((a) => ({ time: a.t, value: a.price })));
    }
    currentChart._bars = bars || [];
    // keep cached sorted times in sync for zoom
    const bt = (bars || []).map((b) => b.t).filter((t) => typeof t === "number").sort((a, b) => a - b);
    currentChart._barTimes = bt;
    return currentChart;
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

  let vwapSeries = null, emaSeries = null, ema20Series = null, macdSeries = null;
  let sma20Series = null, sma50Series = null, sma200Series = null;
  const multiDay = isMultiDaySession(sess || {}, bars);

  const addLine = (key, color, width = 1) => {
    const data = bars.filter((b) => b[key] != null).map((b) => ({ time: b.t, value: b[key] }));
    if (!data.length) return null;
    const series = chart.addLineSeries({
      color, lineWidth: width, priceLineVisible: false, lastValueVisible: false,
    });
    series.setData(data);
    return series;
  };

  if (multiDay) {
    sma20Series = addLine("sma20", col("--sma20") || "#7dd3fc", 1);
    sma50Series = addLine("sma50", col("--sma50") || "#c084fc", 1);
    sma200Series = addLine("sma200", col("--sma200") || "#fbbf24", 2);
  } else {
    // Overlays (VWAP/EMAs) belong on the main price scale (right)
    vwapSeries = addLine("vwap", col("--vwap"), 2);
    emaSeries = addLine("ema9", col("--ema"), 1);
    ema20Series = addLine("ema20", col("--ema2"), 1);
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

  // MACD histogram subchart (middle pane, above volume) — day-trade only
  if (!multiDay) {
    const macdData = bars.filter((b) => b.macd_hist != null).map((b) => ({
      time: b.t, value: b.macd_hist,
      color: (b.macd_hist >= 0) ? "rgba(38,166,154,.65)" : "rgba(239,83,80,.65)",
    }));
    if (macdData.length) {
      macdSeries = chart.addHistogramSeries({
        priceScaleId: "macd",
        priceLineVisible: false,
        lastValueVisible: false,
      });
      macdSeries.setData(macdData);
      chart.priceScale("macd").applyOptions({
        scaleMargins: { top: 0.75, bottom: 0.10 },
        visible: false,
      });
    }
  }

  // levels from setup
  const setup = (sess && sess.setup) || {};
  const lvl = (price, color, title, style) =>
    price != null && candle.createPriceLine({
      price, color, lineWidth: 1, title,
      lineStyle: style ?? LightweightCharts.LineStyle.Dashed, axisLabelVisible: true,
    });

  if (multiDay) {
    // Plan bracket: entry / stop / dual targets
    lvl(setup.entry_px || setup.handle_high, col("--plan") || "#94a3b8", "handle/entry", LightweightCharts.LineStyle.Dashed);
    lvl(setup.stop_px, col("--stop"), "plan stop", LightweightCharts.LineStyle.Dashed);
    lvl(setup.target1_px, col("--t1") || "#34d399", "T1", LightweightCharts.LineStyle.Dotted);
    lvl(setup.target2_px, col("--t2") || "#60a5fa", "T2", LightweightCharts.LineStyle.Dotted);
  } else {
    lvl(setup.pm_high, col("--pm"), "pm high");
    lvl(setup.pm_low, col("--pm"), "pm low", LightweightCharts.LineStyle.Dotted);
    lvl(setup.prior_close, col("--muted"), "prior close", LightweightCharts.LineStyle.Dotted);
  }

  const entry = (actions || []).find((a) => a.side === "buy");
  if (entry) lvl(entry.price, col("--entry"), "entry", LightweightCharts.LineStyle.Solid);

  // exit levels — one horizontal price line per distinct sell fill, same style as
  // entry: scale-outs (partial) and the final flatten (full) both count as exits.
  const seenExit = new Set();
  (actions || []).filter((a) => a.side === "sell").forEach((a) => {
    if (seenExit.has(a.price)) return;
    seenExit.add(a.price);
    lvl(a.price, col("--stop"), a.action === "SCALE" ? "scale" : "exit", LightweightCharts.LineStyle.Solid);
  });

  // Align fill markers to the candle's time at the same bar index when possible
  // (actions.t can be stale on old artifacts; bars[i].t is authoritative).
  const barTByI = {};
  const barDateByI = {};
  (bars || []).forEach((b) => {
    if (b && b.i != null) {
      if (b.t != null) barTByI[b.i] = b.t;
      if (b.date) barDateByI[b.i] = b.date;
    }
  });
  const actionTime = (a) => (a.i != null && barTByI[a.i] != null ? barTByI[a.i] : a.t);
  const actionDate = (a) => a.date || barDateByI[a.i] || "";

  // markers
  candle.setMarkers((actions || []).map((a) => {
    const d = actionDate(a);
    const when = multiDay && d ? d.slice(5) + " " : "";
    return {
      time: actionTime(a),
      position: a.side === "buy" ? "belowBar" : "aboveBar",
      color: a.side === "buy" ? col("--entry") : col("--stop"),
      shape: a.side === "buy" ? "arrowUp" : "arrowDown",
      text: `${when}${a.side === "buy" ? "BUY" : "SELL"} ${a.shares}@${a.price}`,
    };
  }).filter((m) => m.time != null));

  // fill dots — a point plotted at the exact (time, price) of each fill, i.e. the
  // intersection of the entry/exit price line with the bar the fill happened on.
  const buyDots = chart.addLineSeries({
    lineVisible: false, pointMarkersVisible: true, pointMarkersRadius: 5,
    color: col("--entry"), priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false,
  });
  buyDots.setData((actions || []).filter((a) => a.side === "buy" && actionTime(a) != null)
    .map((a) => ({ time: actionTime(a), value: a.price })));

  const sellDots = chart.addLineSeries({
    lineVisible: false, pointMarkersVisible: true, pointMarkersRadius: 5,
    color: col("--stop"), priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false,
  });
  sellDots.setData((actions || []).filter((a) => a.side === "sell" && actionTime(a) != null)
    .map((a) => ({ time: actionTime(a), value: a.price })));

  // Restore the prior zoom on a live refresh; otherwise fit the whole series.
  if (prevRange) {
    try { chart.timeScale().setVisibleLogicalRange(prevRange); }
    catch (_) { chart.timeScale().fitContent(); }
  } else {
    chart.timeScale().fitContent();
  }
  chart._candle = candle;   // referenced by the timeline for crosshair linking
  chart._bars = bars || []; // for timeline clicks to zoom 2h window around a decision

  // Precompute sorted numeric times for fast zoom without re-sorting on every click
  const barTimes = (bars || [])
    .map((b) => b.t)
    .filter((t) => typeof t === "number")
    .sort((a, b) => a - b);
  chart._barTimes = barTimes;

  chart._series = {
    candle: candle, vwap: vwapSeries, ema: emaSeries,
    ema20: ema20Series, vol: vol, macd: macdSeries,
    sma20: sma20Series, sma50: sma50Series, sma200: sma200Series,
    buyDots: buyDots, sellDots: sellDots,
  };


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

function renderTimeline(decisions, chart, multiDay = false) {
  const wrap = document.getElementById("timeline");
  document.getElementById("t-count").textContent = decisions && decisions.length ? `(${decisions.length} turns)` : "";

  if (!decisions || !decisions.length) {
    wrap.innerHTML = `<div class="muted">no decisions logged yet</div>`;
    return;
  }

  // Prefer bar timestamp by index when chart has bars (fixes old artifacts).
  const barTByI = {};
  const barDateByI = {};
  ((chart && chart._bars) || []).forEach((b) => {
    if (b && b.i != null) {
      if (b.t != null) barTByI[b.i] = b.t;
      if (b.date) barDateByI[b.i] = b.date;
    }
  });

  wrap.innerHTML = decisions.map((d) => {
    const pos = d.position_shares
      ? `<span class="pos muted">${d.position_shares}sh @ $${d.avg_entry}</span>`
      : `<span class="pos muted">flat</span>`;
    const u = d.unrealized || 0;
    const ucls = u > 0 ? "pos-v" : u < 0 ? "neg-v" : "";
    const r = d.realized_to_date || 0;
    const rcls = r > 0 ? "pos-v" : r < 0 ? "neg-v" : "";
    const stop = d.stop != null ? ` · stop $${d.stop}` : "";
    const whenRow = {
      time: d.time,
      date: d.date || barDateByI[d.i] || "",
    };
    const tStamp = (d.i != null && barTByI[d.i] != null) ? barTByI[d.i] : d.t;
    return `<div class="turn" data-t="${tStamp || ""}" data-c="${d.close != null ? d.close : ""}" data-i="${d.i}">
      <div class="top">
        <span class="time">${escapeHtml(fmtWhen(whenRow, multiDay))}</span>
        <span class="act act-${d.action}">${d.action}</span>
        ${pos}
      </div>
      <div class="thought">${escapeHtml(d.thought || "")}</div>
      <div class="pnl muted">uPnL <span class="${ucls}">$${u}</span> · realized <span class="${rcls}">$${r}</span>${stop}</div>
    </div>`;
  }).join("");

  const turns = [...wrap.querySelectorAll(".turn")];

  // Zoom helper: intraday ~2h window; multi-day ~10 calendar days around the click.
  // Uses pre-cached sorted times from renderChart for speed and consistency.
  const ONE_HOUR = 3600;
  const ONE_DAY = 86400;
  const START_TOL = multiDay ? ONE_DAY : 120;
  const TARGET_SPAN = multiDay ? 10 * ONE_DAY : 2 * ONE_HOUR;

  function zoomToDecision(time) {
    if (!chart || !chart.timeScale || !chart._barTimes || !time) return;
    const barTimes = chart._barTimes;
    if (!barTimes.length) return;

    const dataMin = barTimes[0];
    const dataMax = barTimes[barTimes.length - 1];

    let from = time - ONE_HOUR;
    let to = time + ONE_HOUR;

    // Clamp to data we actually have
    from = Math.max(from, dataMin);
    to = Math.min(to, dataMax);

    // If the window ended up smaller than ~2h because we couldn't go before the target
    // (e.g. start of day / first decision at 9:30 with no prior data), expand forward
    // to give essentially a full 2h view (9:30-11:30 style).
    let span = to - from;
    if (span < TARGET_SPAN && from <= dataMin + START_TOL) {
      to = Math.min(from + TARGET_SPAN, dataMax);
    }

    // Symmetric handling near the end of data: ensure ~2h if possible
    span = to - from;
    if (span < TARGET_SPAN && to >= dataMax - START_TOL) {
      from = Math.max(to - TARGET_SPAN, dataMin);
    }

    // Final safety: if still inverted or zero span, fall back to full data
    if (from >= to) {
      from = dataMin;
      to = dataMax;
    }

    try {
      chart.timeScale().setVisibleRange({ from, to });
    } catch (_) {}
  }

  const select = (t, scrollList) => {
    // Zoom first so the time is in view, then position crosshair etc.
    if (t != null) zoomToDecision(+t);

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
  return String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

function highlightCurrentSession() {
  const listEl = document.getElementById("session-list");
  if (!listEl) return;
  listEl.querySelectorAll(".sess-card").forEach(card => {
    card.classList.toggle("selected", card.dataset.id === currentTopSessionId);
  });
}

// ---------- Load session detail ----------

async function loadSession(sessionId, updateUrl = false) {
  // Show only the per-ticker detail; hide tickers list and placeholder
  showPane("session-detail");

  currentSessionId = sessionId;

  // stop the tickers-view live re-poll so it can't yank us back here
  if (tickersRefreshTimer) {
    clearInterval(tickersRefreshTimer);
    tickersRefreshTimer = null;
  }

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
    const multiDay = isMultiDaySession(view.session || {}, view.bars);
    renderHeader(view);
    renderBlotter(view.actions || [], multiDay, view.bars || []);
    const chart = renderChart(view.bars || [], view.actions || [], view.session);
    renderTimeline(view.decisions || [], chart, multiDay);

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

    // The sidebar only lists top-level (batch/live-day) cards, not individual
    // ticker leaves — resolve this leaf's parent (same fallback chain the
    // server uses to group sessions: session tag → batch tag → id) so the
    // right card stays highlighted while viewing one of its tickers.
    const s = view.session || {};
    currentTopSessionId = s.session || s.batch || s.id || sessionId;
    // Scope sidebar to this leaf's strategy family.
    setSidebarStrategy(sessionStrategy(s));
    highlightCurrentSession();

    if (updateUrl) {
      history.replaceState(null, "", `?session=${encodeURIComponent(sessionId)}`);
    }

  } catch (e) {
    showPane("no-session");
    fail(`Could not load session ${sessionId}: ${e}`);
  }
}

function setupLiveUpdates(sessionId) {
  // Prefer SSE
  try {
    const es = new EventSource(`/api/session/${encodeURIComponent(sessionId)}/events`);
    currentEventSource = es;

    es.onmessage = (ev) => {
      if (pollFallbackTimer) {
        clearInterval(pollFallbackTimer);
        pollFallbackTimer = null;
      }
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
    const multiDay = isMultiDaySession(view.session || {}, view.bars);
    renderHeader(view);

    // Incremental-friendly updates
    const blotter = document.querySelector("#blotter tbody");
    if (blotter) {
      // Simple approach: re-render blotter (small)
      renderBlotter(view.actions || [], multiDay, view.bars || []);
    }

    // For chart + timeline we do a light full re-render of data
    // (lightweight-charts is fast enough for 720 bars)
    const chartContainer = document.getElementById("chart");
    if (chartContainer && view.bars && view.bars.length) {
      // preserveView=true: keep the user's zoom/scroll as new live bars stream in
      const chart = renderChart(view.bars, view.actions || [], view.session, true);
      renderTimeline(view.decisions || [], chart, multiDay);
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

  // Archive this run → hide it from the lists, then return to the sessions list.
  const arcBtn = document.getElementById("archive-btn");
  if (arcBtn) {
    arcBtn.onclick = () => archiveSession(sessionId, arcBtn);
  }
}

// POST an archive for a session (leaf or top-level id); on success go back to the
// sessions list (which now excludes it). Shared by the detail + tickers views.
async function archiveSession(id, btn) {
  if (!id) return;
  const label = btn ? btn.textContent : null;
  if (btn) { btn.disabled = true; btn.textContent = "Archiving…"; }
  try {
    const r = await fetch(`/api/session/${encodeURIComponent(id)}/archive`, { method: "POST" });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    window.location.href = "/viewer/index.html";
  } catch (e) {
    if (btn) { btn.disabled = false; btn.textContent = label; }
    fail(`Could not archive ${id}: ${e}`);
  }
}

// ---------- Boot ----------

async function main() {
  const sessionFromUrl = qs("session");

  // Default view (no session selected): full-page, sortable session table with
  // no sidebar. Selecting a row fully navigates to ?session=<id>, which drops
  // into the sidebar + detail layout below.
  if (!sessionFromUrl) {
    await renderSessionTable();
    return;
  }

  // A session is selected → sidebar + detail layout.
  document.getElementById("app").classList.remove("table-view");

  // Mark the selected session up front so the sidebar highlights it on first
  // render (loadAndRenderList applies the highlight from currentTopSessionId).
  // If sessionFromUrl turns out to be a leaf (not a top-level id), loadSession
  // below re-resolves this to the leaf's parent batch.
  currentSessionId = sessionFromUrl;
  currentTopSessionId = sessionFromUrl;

  // Load full session list first (unfiltered), then scope after we know strategy.
  await loadAndRenderList();
  // Prefer matching the URL session against the full list so strategy filter
  // doesn't hide the target before we set it.
  const topIds = new Set(allSidebarSessions.map((s) => s.id));
  const matched = allSidebarSessions.find((s) => s.id === sessionFromUrl);
  if (matched) {
    setSidebarStrategy(matched.strategy || "warrior");
  }
  const topSessions = sessionsForSidebar();

  // If the selected session is a top-level card, scroll it into view on first
  // load — the sidebar sorts newest-first and can run long, so a session from
  // a few pages back would otherwise render off-screen with no visual cue.
  if (topIds.has(sessionFromUrl)) {
    const cards = document.querySelectorAll("#session-list .sess-card");
    const selectedCard = Array.from(cards).find((c) => c.dataset.id === sessionFromUrl);
    if (selectedCard) selectedCard.scrollIntoView({ block: "nearest" });
  }

  // "Sessions" header chip is a same-origin link to /viewer/index.html
  // (relative — works on whatever host:port the server is using).

  // Wire global refresh button
  const refreshList = document.getElementById("refresh-list-btn");
  if (refreshList) {
    refreshList.onclick = () => loadAndRenderList();
  }

  if (topIds.has(sessionFromUrl)) {
    // This id came from the sessions list (a batch, live day, or singleton group).
    // Show the tickers sub-list (even if 1 item).
    await loadSessionTickers(sessionFromUrl);
  } else {
    // Not a known top-level id → treat as a specific leaf session.
    await loadSession(sessionFromUrl);
  }

  // Light auto-refresh of the sidebar list
  setInterval(loadAndRenderList, 20000);
}

main().catch((e) => fail(e.stack || String(e)));