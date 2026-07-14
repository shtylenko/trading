/* Stock Monitor session UI — talks to same-origin receiver API */

const $ = (id) => document.getElementById(id);

let sessions = [];
let selectedDate = null;
let tickers = [];
let sessionMeta = null;

function formatWhen(iso) {
  if (!iso) return "—";
  try {
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return String(iso).slice(0, 19);
    return d.toLocaleString(undefined, {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });
  } catch {
    return String(iso).slice(0, 19);
  }
}

function formatDateLabel(dateStr) {
  if (!dateStr) return "—";
  try {
    // Parse as local calendar date (YYYY-MM-DD)
    const [y, m, d] = dateStr.split("-").map(Number);
    const dt = new Date(y, m - 1, d);
    return dt.toLocaleDateString(undefined, {
      weekday: "short",
      year: "numeric",
      month: "short",
      day: "numeric",
    });
  } catch {
    return dateStr;
  }
}

async function fetchJson(path) {
  const r = await fetch(path, { cache: "no-store" });
  if (!r.ok) throw new Error(`${path} → ${r.status}`);
  return r.json();
}

async function checkHealth() {
  const el = $("conn");
  try {
    const h = await fetchJson("/health");
    if (h.status === "ok") {
      el.textContent = "connected";
      el.className = "pill ok";
      return true;
    }
    el.textContent = "issue";
    el.className = "pill warn";
    return false;
  } catch {
    el.textContent = "offline";
    el.className = "pill err";
    return false;
  }
}

async function loadSessions() {
  const listEl = $("sessions-list");
  try {
    const data = await fetchJson("/sessions?limit=90");
    sessions = data.sessions || [];
    $("session-count").textContent = `${sessions.length}`;
    renderSessions();

    // Auto-select today if present, else first session, else keep selection
    if (sessions.length === 0) {
      selectedDate = null;
      tickers = [];
      sessionMeta = null;
      renderTickers();
      return;
    }
    const dates = new Set(sessions.map((s) => s.session_date));
    if (selectedDate && dates.has(selectedDate)) {
      await loadSession(selectedDate);
    } else {
      await loadSession(sessions[0].session_date);
    }
  } catch (e) {
    listEl.innerHTML = `<div class="empty">Failed to load sessions: ${escapeHtml(e.message)}</div>`;
  }
}

function renderSessions() {
  const listEl = $("sessions-list");
  if (!sessions.length) {
    listEl.innerHTML = `<div class="empty">No sessions yet.<br>Arm Gap'n'Go on the screener to start collecting.</div>`;
    return;
  }

  listEl.innerHTML = "";
  for (const s of sessions) {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "session-item" + (s.session_date === selectedDate ? " active" : "");
    btn.dataset.date = s.session_date;
    btn.innerHTML = `
      <div>
        <div class="date">${escapeHtml(s.session_date)}</div>
        <div class="meta">${escapeHtml(formatDateLabel(s.session_date))}</div>
      </div>
      <div class="count">${Number(s.ticker_count) || 0}</div>
    `;
    btn.addEventListener("click", () => loadSession(s.session_date));
    listEl.appendChild(btn);
  }
}

let watchlistSyncByTicker = {};

async function loadWatchlistStatus(date) {
  watchlistSyncByTicker = {};
  try {
    const data = await fetchJson(`/watchlist/status?date=${encodeURIComponent(date)}`);
    for (const row of data.sync || []) {
      if (row.ticker) watchlistSyncByTicker[row.ticker.toUpperCase()] = row;
    }
    return data;
  } catch {
    return null;
  }
}

async function loadSession(date) {
  selectedDate = date;
  renderSessions(); // update active highlight

  $("detail-title").textContent = date;
  $("detail-meta").textContent = "Loading…";
  $("ticker-count").textContent = "…";

  try {
    const data = await fetchJson(`/session?date=${encodeURIComponent(date)}`);
    sessionMeta = data;
    tickers = Array.isArray(data.tickers) ? data.tickers : [];
    const wl = await loadWatchlistStatus(date);
    const label = formatDateLabel(date);
    const exists = data.exists !== false;
    let meta = exists
      ? `${label} · updated ${formatWhen(data.updated_at)}`
      : `${label} · empty session`;
    if (wl?.config?.watchlist_name) {
      const synced = (wl.sync || []).filter((r) => r.status === "synced" || r.status === "dry_run").length;
      meta += ` · watchlist “${wl.config.watchlist_name}”: ${synced} synced`;
      if (!wl.config.has_credentials) meta += " (dry-run — no API creds)";
    }
    $("detail-meta").textContent = meta;
    $("ticker-count").textContent = `${tickers.length} ticker${tickers.length === 1 ? "" : "s"}`;
    renderTickers();
  } catch (e) {
    $("detail-meta").textContent = `Error: ${e.message}`;
    tickers = [];
    renderTickers();
  }
}

function renderTickers() {
  const body = $("tickers-body");
  const q = ($("filter").value || "").trim().toLowerCase();

  let rows = tickers;
  if (q) {
    rows = tickers.filter((t) => {
      const sym = (t.ticker || "").toLowerCase();
      const name = (t.name || "").toLowerCase();
      const scr = (t.screener_name || t.screener_key || "").toLowerCase();
      return sym.includes(q) || name.includes(q) || scr.includes(q);
    });
  }

  if (!selectedDate) {
    body.innerHTML = `<tr class="empty-row"><td colspan="6">Select a session to view tickers</td></tr>`;
    return;
  }
  if (!rows.length) {
    body.innerHTML = `<tr class="empty-row"><td colspan="6">${
      tickers.length ? "No tickers match filter" : "No tickers in this session"
    }</td></tr>`;
    return;
  }

  body.innerHTML = rows
    .map((t) => {
      const screener = t.screener_name || t.screener_key || "—";
      const sync = watchlistSyncByTicker[(t.ticker || "").toUpperCase()];
      const wlStatus = sync
        ? `<span class="sync-pill sync-${escapeHtml(sync.status)}">${escapeHtml(sync.status)}</span>`
        : `<span class="sync-pill sync-none">—</span>`;
      return `<tr>
        <td class="col-sym">${escapeHtml(t.ticker || "—")}</td>
        <td class="col-name">${escapeHtml(t.name || "—")}</td>
        <td class="col-scr">${escapeHtml(screener)}</td>
        <td class="col-wl">${wlStatus}</td>
        <td class="col-time">${escapeHtml(formatWhen(t.first_seen_at))}</td>
        <td class="col-time">${escapeHtml(formatWhen(t.last_seen_at))}</td>
      </tr>`;
    })
    .join("");
}

function escapeHtml(s) {
  return String(s ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

async function refreshAll() {
  await checkHealth();
  await loadSessions();
}

document.addEventListener("DOMContentLoaded", () => {
  $("btn-refresh").addEventListener("click", refreshAll);
  $("filter").addEventListener("input", renderTickers);
  refreshAll();
  // Light poll so new screener hits appear while the page is open
  setInterval(async () => {
    if (document.hidden) return;
    await checkHealth();
    if (selectedDate) {
      // Refresh list counts + current session tickers without clobbering filter focus
      try {
        const data = await fetchJson("/sessions?limit=90");
        sessions = data.sessions || [];
        $("session-count").textContent = `${sessions.length}`;
        renderSessions();
        const sess = await fetchJson(`/session?date=${encodeURIComponent(selectedDate)}`);
        sessionMeta = sess;
        tickers = Array.isArray(sess.tickers) ? sess.tickers : [];
        $("ticker-count").textContent = `${tickers.length} ticker${tickers.length === 1 ? "" : "s"}`;
        $("detail-meta").textContent = `${formatDateLabel(selectedDate)} · updated ${formatWhen(sess.updated_at)}`;
        renderTickers();
      } catch (_) {}
    }
  }, 8000);
});
