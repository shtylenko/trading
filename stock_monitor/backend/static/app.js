/* Stock Monitor session UI — talks to same-origin receiver API */

const $ = (id) => document.getElementById(id);

let sessions = [];
let selectedDate = null;
let tickers = [];
let sessionMeta = null;
let watchlistSyncByTicker = {};
let membershipByTicker = {};
let liveWatchlist = null;

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

    if (sessions.length === 0) {
      selectedDate = null;
      tickers = [];
      sessionMeta = null;
      membershipByTicker = {};
      liveWatchlist = null;
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

async function loadWatchlistStatus(date) {
  watchlistSyncByTicker = {};
  membershipByTicker = {};
  liveWatchlist = null;
  try {
    const data = await fetchJson(`/watchlist/status?date=${encodeURIComponent(date)}`);
    for (const row of data.sync || []) {
      if (row.ticker) watchlistSyncByTicker[row.ticker.toUpperCase()] = row;
    }
    membershipByTicker = data.membership || {};
    liveWatchlist = data.live || null;
    return data;
  } catch {
    return null;
  }
}

function formatPushAge(sec) {
  if (sec == null || Number.isNaN(sec)) return "—";
  const s = Math.max(0, Math.floor(sec));
  if (s < 60) return `${s}s ago`;
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
  return `${Math.floor(s / 86400)}d ago`;
}

function updatePushStatus(session) {
  const el = $("push-status");
  if (!el) return;

  const lastPush = session?.last_push_at || session?.updated_at;
  const hasTickers = Array.isArray(session?.tickers) && session.tickers.length > 0;
  if (!session || (session.exists === false && !lastPush && !hasTickers)) {
    el.textContent = "no data";
    el.className = "pill push-idle";
    el.title = "No screener data for this session";
    return;
  }

  // Prefer server-provided fields; fall back to client-side age from last_push_at
  let status = session.push_status;
  let age = session.last_push_age_sec;

  if ((age == null || age === undefined) && lastPush) {
    const ts = Date.parse(lastPush);
    if (!Number.isNaN(ts)) {
      age = Math.max(0, Math.floor((Date.now() - ts) / 1000));
    }
  }
  if (!status && age != null) {
    if (age <= 45) status = "live";
    else if (age <= 300) status = "recent";
    else status = "idle";
  }
  status = status || "unknown";

  const ageText = formatPushAge(age);
  if (status === "live") {
    el.textContent = `LIVE · last push ${ageText}`;
    el.className = "pill push-live";
    el.title = `Screener data is actively arriving (last push ${ageText})`;
  } else if (status === "recent") {
    el.textContent = `recent · ${ageText}`;
    el.className = "pill push-recent";
    el.title = `Last screener push ${ageText} — not currently streaming`;
  } else if (status === "idle") {
    el.textContent = `idle · ${ageText}`;
    el.className = "pill push-idle";
    el.title = `No recent screener pushes (last ${ageText})`;
  } else {
    el.textContent = "unknown";
    el.className = "pill push-idle";
    el.title = "No push timestamp available";
  }
}

function membershipLight(ticker) {
  const m = membershipByTicker[(ticker || "").toUpperCase()];
  const status = m?.status || "off";
  // green = currently on watchlist; yellow = left or not on list
  if (status === "on") {
    return {
      status: "on",
      title: m?.label || "On watchlist",
      html: `<span class="wl-light green" title="On watchlist"></span><span class="wl-light-label on">on</span>`,
    };
  }
  if (status === "left") {
    return {
      status: "left",
      title: m?.label || "Left watchlist",
      html: `<span class="wl-light yellow" title="Left watchlist"></span><span class="wl-light-label left">left</span>`,
    };
  }
  return {
    status: "off",
    title: m?.label || "Not on watchlist",
    html: `<span class="wl-light yellow dim" title="Not on watchlist"></span><span class="wl-light-label off">off</span>`,
  };
}

async function loadSession(date) {
  selectedDate = date;
  renderSessions();

  $("detail-title").textContent = date;
  $("detail-meta").textContent = "Loading…";
  $("ticker-count").textContent = "…";
  const pushEl = $("push-status");
  if (pushEl) {
    pushEl.textContent = "…";
    pushEl.className = "pill push-idle";
  }

  try {
    const data = await fetchJson(`/session?date=${encodeURIComponent(date)}`);
    sessionMeta = data;
    tickers = Array.isArray(data.tickers) ? data.tickers : [];
    updatePushStatus(data);

    const wl = await loadWatchlistStatus(date);
    const label = formatDateLabel(date);
    const exists = data.exists !== false;
    let meta = exists
      ? `${label} · last push ${formatWhen(data.last_push_at || data.updated_at)}`
      : `${label} · empty session`;

    const onCount = Object.values(membershipByTicker).filter((m) => m.status === "on").length;
    const leftCount = Object.values(membershipByTicker).filter((m) => m.status === "left").length;
    const wlName = wl?.config?.watchlist_name || liveWatchlist?.watchlist_name || "Gap'n'Go";
    if (liveWatchlist?.ok) {
      meta += ` · “${wlName}”: ${onCount} on · ${leftCount} left · live ${liveWatchlist.count ?? 0}`;
    } else if (wl?.error || liveWatchlist?.error) {
      meta += ` · watchlist unavailable (${wl?.error || liveWatchlist?.error || "error"})`;
    } else if (wl?.config?.watchlist_name) {
      meta += ` · watchlist “${wl.config.watchlist_name}”`;
    }

    $("detail-meta").textContent = meta;
    $("ticker-count").textContent = `${tickers.length} ticker${tickers.length === 1 ? "" : "s"}`;
    renderTickers();
  } catch (e) {
    $("detail-meta").textContent = `Error: ${e.message}`;
    tickers = [];
    if (pushEl) {
      pushEl.textContent = "error";
      pushEl.className = "pill push-idle";
    }
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
    body.innerHTML = `<tr class="empty-row"><td colspan="7">Select a session to view tickers</td></tr>`;
    return;
  }
  if (!rows.length) {
    body.innerHTML = `<tr class="empty-row"><td colspan="7">${
      tickers.length ? "No tickers match filter" : "No tickers in this session"
    }</td></tr>`;
    return;
  }

  body.innerHTML = rows
    .map((t) => {
      const screener = t.screener_name || t.screener_key || "—";
      const light = membershipLight(t.ticker);
      const sync = watchlistSyncByTicker[(t.ticker || "").toUpperCase()];
      const syncNote = sync?.status && sync.status !== "synced"
        ? `<span class="sync-mini">${escapeHtml(sync.status)}</span>`
        : "";
      return `<tr>
        <td class="col-sym">${escapeHtml(t.ticker || "—")}</td>
        <td class="col-name">${escapeHtml(t.name || "—")}</td>
        <td class="col-scr">${escapeHtml(screener)}</td>
        <td class="col-light" title="${escapeHtml(light.title)}">
          <div class="wl-light-cell">${light.html}${syncNote}</div>
        </td>
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
  // Light poll so new screener hits + watchlist membership stay fresh
  setInterval(async () => {
    if (document.hidden || !selectedDate) return;
    try {
      const data = await fetchJson("/sessions?limit=90");
      sessions = data.sessions || [];
      $("session-count").textContent = `${sessions.length}`;
      renderSessions();
      await loadSession(selectedDate);
    } catch (_) {}
  }, 8000);
});
