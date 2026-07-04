#!/usr/bin/env python3
"""
Analyst Radar — Web UI.

Usage:
    python3 -m trading.analyst_radar.web [--port 8082] [--db <path>]

Then open http://localhost:8082

Routes:
  /                   Dashboard
  /analysts           Analyst directory
  /analyst/<id>       Analyst detail
  /tickers            Ticker directory
  /ticker/<id>        Ticker detail
  /interviews         Interview log
  /interview/<id>     Interview detail
  /predictions        All predictions (filterable)
  /pipeline           Pipeline run log
"""

import html as html_mod
import http.server
import os
import sqlite3
import sys
import urllib.parse
from pathlib import Path
from http.server import ThreadingHTTPServer

BASE_DIR  = Path(__file__).resolve().parent
_DB_PATH  = os.environ.get("ANALYST_RADAR_DB") or str(BASE_DIR / "data" / "analyst_radar.db")
_DEFAULT_PORT = 8082

# ── DB helpers ────────────────────────────────────────────────────────────────

def _conn():
    c = sqlite3.connect(_DB_PATH)
    c.row_factory = sqlite3.Row
    return c

def _q(sql, params=()):
    c = _conn()
    cur = c.execute(sql, params)
    rows = cur.fetchall()
    cols = [d[0] for d in cur.description]
    c.close()
    return [dict(zip(cols, r)) for r in rows]

def _q1(sql, params=()):
    rows = _q(sql, params)
    return rows[0] if rows else None

# ── HTML helpers ──────────────────────────────────────────────────────────────

CSS = """
* { margin:0; padding:0; box-sizing:border-box; }
body { font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;
       background:#0d1117; color:#c9d1d9; font-size:14px; }
a { color:#58a6ff; text-decoration:none; }
a:hover { text-decoration:underline; }
nav { background:#161b22; padding:8px 20px; border-bottom:1px solid #30363d;
      display:flex; gap:6px; align-items:center; flex-wrap:wrap; }
nav .brand { font-weight:700; font-size:15px; color:#f0f6fc; margin-right:12px; }
nav a { color:#8b949e; font-size:13px; padding:4px 10px; border-radius:4px; }
nav a:hover { color:#f0f6fc; background:#1f2937; text-decoration:none; }
nav a.active { color:#f0f6fc; background:#1f2937; }
.container { max-width:1400px; margin:0 auto; padding:20px; }
h1 { font-size:20px; color:#f0f6fc; margin-bottom:4px; }
h2 { font-size:15px; color:#f0f6fc; }
.card { background:#161b22; border:1px solid #30363d; border-radius:8px;
        padding:16px; margin-bottom:16px; }
.card h2 { margin-bottom:12px; }
table { width:100%; border-collapse:collapse; font-size:13px; }
th { background:#1f2937; color:#8b949e; font-weight:600; text-align:left;
     padding:8px 10px; border-bottom:1px solid #30363d; white-space:nowrap; }
td { padding:6px 10px; border-bottom:1px solid #21262d;
     overflow:hidden; text-overflow:ellipsis; white-space:nowrap; max-width:320px; }
tr:hover td { background:#1c2333; }
tr.click { cursor:pointer; }
.stats { display:grid; grid-template-columns:repeat(auto-fill,minmax(140px,1fr)); gap:10px; margin-bottom:16px; }
.stat { background:#161b22; border:1px solid #30363d; border-radius:8px; padding:14px; text-align:center; }
.stat .n { font-size:26px; font-weight:700; color:#f0f6fc; }
.stat .l { font-size:11px; color:#8b949e; margin-top:2px; }
.badge { display:inline-block; padding:2px 7px; border-radius:4px; font-size:11px; font-weight:600; white-space:nowrap; }
.b-bullish  { background:#1a3b2a; color:#3fb950; }
.b-bearish  { background:#3b1a1a; color:#f85149; }
.b-neutral  { background:#1f2937; color:#8b949e; }
.b-high     { background:#1a3b2a; color:#3fb950; }
.b-medium   { background:#3b2a1a; color:#d29922; }
.b-low      { background:#3b1a1a; color:#f85149; }
.b-type     { background:#1a2b3b; color:#58a6ff; }
.b-ok       { background:#1a3b2a; color:#3fb950; }
.b-fail     { background:#3b1a1a; color:#f85149; }
.b-run      { background:#1f2937; color:#c9d1d9; }
.bb-bar { display:inline-flex; align-items:center; gap:6px; }
.bb-score { font-weight:700; font-size:13px; min-width:36px; text-align:right; }
.bb-track { width:80px; height:6px; background:#21262d; border-radius:3px; overflow:hidden; position:relative; }
.bb-fill  { height:100%; border-radius:3px; position:absolute; top:0; }
.tag { display:inline-block; background:#1f2937; color:#8b949e; padding:1px 6px;
       border-radius:3px; font-size:11px; margin:1px; }
.back { display:inline-block; color:#8b949e; margin-bottom:12px; font-size:13px; }
.back::before { content:'← '; }
.back:hover { color:#58a6ff; }
.sub { color:#8b949e; font-size:13px; margin-bottom:16px; }
.filters { background:#161b22; border:1px solid #30363d; border-radius:8px;
           padding:12px 16px; margin-bottom:14px; display:flex; flex-wrap:wrap; gap:10px; align-items:flex-end; }
.filters label { font-size:11px; color:#8b949e; display:block; margin-bottom:3px; }
.filters select, .filters input { background:#0d1117; color:#c9d1d9;
    border:1px solid #30363d; border-radius:4px; padding:5px 8px; font-size:12px; }
.filters button { background:#238636; color:#fff; border:none; border-radius:4px;
    padding:5px 14px; font-size:12px; cursor:pointer; font-weight:600; }
.filters a.reset { color:#8b949e; font-size:12px; align-self:center; }
details summary { cursor:pointer; color:#58a6ff; font-size:13px; }
pre { white-space:pre-wrap; word-break:break-word; }
.transcript { background:#0d1117; padding:14px; border-radius:6px;
              font-size:12px; line-height:1.7; color:#8b949e; margin-top:8px; }
"""

def _esc(s):
    return html_mod.escape(str(s or ""))

def _page(title, body, active=""):
    pending_candidates = _q1(
        "SELECT COUNT(*) c FROM analyst_candidates WHERE status='pending'"
    )["c"]
    candidate_label = f"Candidates ({pending_candidates})" if pending_candidates else "Candidates"

    nav_items = [
        ("", "Dashboard"),
        ("analysts", "Analysts"),
        ("tickers", "Tickers"),
        ("interviews", "Interviews"),
        ("predictions", "Predictions"),
        ("channels", "Channels"),
        ("pipeline", "Pipeline"),
        ("candidates", candidate_label),
    ]
    nav_html = '<span class="brand">Analyst Radar</span>'
    for path, label in nav_items:
        cls = ' class="active"' if active == path else ""
        nav_html += f'<a href="/{path}"{cls}>{label}</a>'

    return f"""<!DOCTYPE html><html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{_esc(title)} — Analyst Radar</title>
<style>{CSS}</style>
</head><body>
<nav>{nav_html}</nav>
<div class="container">{body}</div>
</body></html>"""

def _badge_direction(d):
    d = (d or "neutral").lower()
    return f'<span class="badge b-{d}">{_esc(d)}</span>'

def _badge_confidence(c):
    if not c: return "—"
    return f'<span class="badge b-{c.lower()}">{_esc(c)}</span>'

def _badge_type(t):
    return f'<span class="badge b-type">{_esc(t or "other")}</span>'

def _badge_status(s):
    cls = "ok" if s == "completed" else ("fail" if s == "failed" else "run")
    return f'<span class="badge b-{cls}">{_esc(s)}</span>'

def _ticker_tags(tickers_str):
    if not tickers_str: return "—"
    return "".join(
        f'<a href="/ticker/{_esc(t.strip())}" class="tag">{_esc(t.strip())}</a>'
        for t in tickers_str.split(",") if t.strip()
    )

def _bull_bear_widget(score, updated_at=None, compact=False):
    """Render a -10..+10 sentiment indicator as a colored score + bar."""
    if score is None:
        return '<span style="color:#8b949e;font-size:12px">—</span>'
    score = float(score)
    if score >= 3:
        color = "#3fb950"
    elif score <= -3:
        color = "#f85149"
    else:
        color = "#d29922"
    label = f"{score:+.1f}"
    # bar: 0 is center; fill starts from center toward left (bear) or right (bull)
    pct = abs(score) / 10 * 50  # max 50% of track width
    if score >= 0:
        left = 50
        fill_style = f"left:{left}%;width:{pct}%;background:{color}"
    else:
        left = 50 - pct
        fill_style = f"left:{left}%;width:{pct}%;background:{color}"
    bar = (f'<div class="bb-track">'
           f'<div style="width:1px;height:100%;background:#30363d;position:absolute;left:50%;top:0"></div>'
           f'<div class="bb-fill" style="{fill_style}"></div>'
           f'</div>')
    ts = f'<span style="color:#8b949e;font-size:11px">{(updated_at or "")[:10]}</span>' if updated_at and not compact else ""
    return (f'<span class="bb-bar">'
            f'<span class="bb-score" style="color:{color}">{label}</span>'
            f'{bar}{ts}'
            f'</span>')


# ── Pages ─────────────────────────────────────────────────────────────────────

def page_dashboard():
    total_analysts = _q1("SELECT COUNT(*) c FROM analysts WHERE is_active=1")["c"]
    interviews_week = _q1(
        "SELECT COUNT(*) c FROM interviews WHERE published_date >= date('now','-7 days')"
    )["c"]
    predictions_week = _q1(
        "SELECT COUNT(*) c FROM predictions WHERE created_at >= date('now','-7 days')"
    )["c"]
    total_tickers = _q1("SELECT COUNT(*) c FROM tickers")["c"]
    total_predictions = _q1("SELECT COUNT(*) c FROM predictions")["c"]
    pending_transcripts = _q1(
        "SELECT COUNT(*) c FROM interviews WHERE transcript_text IS NULL"
    )["c"]

    h = [
        '<h1>Dashboard</h1>',
        '<p class="sub">Market analyst interview prediction tracker</p>',
        '<div class="stats">',
        f'<div class="stat"><div class="n">{total_analysts}</div><div class="l">Analysts tracked</div></div>',
        f'<div class="stat"><div class="n">{interviews_week}</div><div class="l">Interviews this week</div></div>',
        f'<div class="stat"><div class="n">{predictions_week}</div><div class="l">Predictions this week</div></div>',
        f'<div class="stat"><div class="n">{total_tickers}</div><div class="l">Tickers mentioned</div></div>',
        f'<div class="stat"><div class="n">{total_predictions}</div><div class="l">Total predictions</div></div>',
        f'<div class="stat"><div class="n">{pending_transcripts}</div><div class="l">Awaiting transcript</div></div>',
        '</div>',
    ]

    recent = _q("""
        SELECT p.id, p.prediction_text, p.direction, p.prediction_type, p.time_horizon,
               a.name analyst_name, a.firm,
               i.title interview_title, i.youtube_url, i.published_date,
               GROUP_CONCAT(t.ticker, ', ') tickers
          FROM predictions p
          JOIN analysts a   ON p.analyst_id   = a.id
          JOIN interviews i ON p.interview_id = i.id
     LEFT JOIN prediction_tickers pt ON pt.prediction_id = p.id
     LEFT JOIN tickers t ON pt.ticker_id = t.id
         GROUP BY p.id
         ORDER BY p.created_at DESC
         LIMIT 20
    """)

    h.append('<div class="card"><h2>Latest Predictions</h2>')
    if not recent:
        h.append('<p class="sub">No predictions yet. Run the pipeline to get started.</p>')
    else:
        h.append('<table><thead><tr>'
                 '<th>Date</th><th>Analyst</th><th>Prediction</th>'
                 '<th>Direction</th><th>Type</th><th>Horizon</th><th>Tickers</th><th>Source</th>'
                 '</tr></thead><tbody>')
        for r in recent:
            h.append(f'<tr class="click" onclick="window.location=\'/interview/{r["id"]}\'">')
            h.append(f'<td style="white-space:nowrap">{r["published_date"][:10]}</td>')
            h.append(f'<td><a href="/analyst/{r["analyst_name"]}">{_esc(r["analyst_name"])}</a></td>')
            h.append(f'<td style="max-width:360px" title="{_esc(r["prediction_text"])}">{_esc(r["prediction_text"][:90])}</td>')
            h.append(f'<td>{_badge_direction(r["direction"])}</td>')
            h.append(f'<td>{_badge_type(r["prediction_type"])}</td>')
            h.append(f'<td style="color:#8b949e">{_esc(r["time_horizon"] or "—")}</td>')
            h.append(f'<td style="white-space:normal">{_ticker_tags(r["tickers"])}</td>')
            h.append(f'<td><a href="{_esc(r["youtube_url"])}" target="_blank" style="color:#8b949e;font-size:11px;">↗</a></td>')
            h.append('</tr>')
        h.append('</tbody></table>')
    h.append('</div>')

    return _page("Dashboard", "\n".join(h), "")


def page_analysts():
    rows = _q("""
        SELECT a.id, a.name, a.firm, a.role, a.is_active,
               COUNT(DISTINCT i.id) interview_count,
               COUNT(DISTINCT p.id) prediction_count,
               MAX(i.published_date) last_interview
          FROM analysts a
     LEFT JOIN predictions p ON p.analyst_id = a.id
     LEFT JOIN interviews  i ON i.id = p.interview_id
         GROUP BY a.id
         ORDER BY a.is_active DESC, interview_count DESC
    """)
    h = ['<h1>Analysts</h1>', f'<p class="sub">{len(rows)} analysts tracked</p>']
    h.append('<div class="card"><table><thead><tr>'
             '<th>Name</th><th>Firm</th><th>Role</th>'
             '<th>Interviews</th><th>Predictions</th><th>Last Interview</th><th>Status</th>'
             '</tr></thead><tbody>')
    for r in rows:
        active_badge = ('<span class="badge b-ok">active</span>' if r["is_active"]
                        else '<span class="badge b-neutral">paused</span>')
        h.append(f'<tr class="click" onclick="window.location=\'/analyst/{r["id"]}\'">')
        h.append(f'<td><a href="/analyst/{r["id"]}">{_esc(r["name"])}</a></td>')
        h.append(f'<td>{_esc(r["firm"])}</td>')
        h.append(f'<td style="color:#8b949e">{_esc(r["role"])}</td>')
        h.append(f'<td>{r["interview_count"]}</td>')
        h.append(f'<td>{r["prediction_count"]}</td>')
        h.append(f'<td style="color:#8b949e">{r["last_interview"] or "—"}</td>')
        h.append(f'<td>{active_badge}</td>')
        h.append('</tr>')
    h.append('</tbody></table></div>')
    return _page("Analysts", "\n".join(h), "analysts")


def page_analyst(analyst_id):
    # Accept both numeric id and name slug
    try:
        a = _q1("SELECT * FROM analysts WHERE id=?", (int(analyst_id),))
    except ValueError:
        a = _q1("SELECT * FROM analysts WHERE name=?", (analyst_id,))
    if not a:
        return _page("Not Found", "<p>Analyst not found.</p>", "analysts")

    interviews = _q("""
        SELECT DISTINCT i.id, i.title, i.youtube_url, i.channel_name,
               i.published_date, i.transcript_text IS NOT NULL has_transcript,
               COUNT(p.id) pred_count
          FROM interviews i
          JOIN predictions p ON p.interview_id = i.id
         WHERE p.analyst_id = ?
         GROUP BY i.id
         ORDER BY i.published_date DESC
         LIMIT 50
    """, (a["id"],))

    predictions = _q("""
        SELECT p.id, p.prediction_text, p.direction, p.prediction_type,
               p.confidence, p.time_horizon, p.created_at,
               i.published_date, i.youtube_url,
               GROUP_CONCAT(t.ticker, ', ') tickers
          FROM predictions p
          JOIN interviews i ON p.interview_id = i.id
     LEFT JOIN prediction_tickers pt ON pt.prediction_id = p.id
     LEFT JOIN tickers t ON pt.ticker_id = t.id
         WHERE p.analyst_id = ?
         GROUP BY p.id
         ORDER BY i.published_date DESC
         LIMIT 100
    """, (a["id"],))

    h = [f'<a class="back" href="/analysts">Analysts</a>']
    h.append(f'<h1>{_esc(a["name"])}</h1>')
    h.append(f'<p class="sub">{_esc(a["firm"])} · {_esc(a["role"])}</p>')
    if a["bio"]:
        h.append(f'<p style="font-size:13px;color:#8b949e;margin-bottom:16px">{_esc(a["bio"])}</p>')

    h.append(f'<div class="card"><h2>Recent Interviews ({len(interviews)})</h2>')
    if not interviews:
        h.append('<p class="sub">No interviews found yet.</p>')
    else:
        h.append('<table><thead><tr><th>Date</th><th>Title</th><th>Channel</th><th>Transcript</th><th>Predictions</th></tr></thead><tbody>')
        for i in interviews:
            t_badge = '<span class="badge b-ok">✓</span>' if i["has_transcript"] else '<span class="badge b-neutral">—</span>'
            h.append(f'<tr class="click" onclick="window.location=\'/interview/{i["id"]}\'">')
            h.append(f'<td style="white-space:nowrap">{i["published_date"]}</td>')
            h.append(f'<td><a href="/interview/{i["id"]}">{_esc(i["title"][:80])}</a></td>')
            h.append(f'<td style="color:#8b949e">{_esc(i["channel_name"])}</td>')
            h.append(f'<td>{t_badge}</td>')
            h.append(f'<td>{i["pred_count"]}</td>')
            h.append('</tr>')
        h.append('</tbody></table>')
    h.append('</div>')

    h.append(f'<div class="card"><h2>Predictions ({len(predictions)})</h2>')
    if not predictions:
        h.append('<p class="sub">No predictions extracted yet.</p>')
    else:
        h.append('<table><thead><tr>'
                 '<th>Date</th><th>Prediction</th><th>Direction</th>'
                 '<th>Type</th><th>Confidence</th><th>Horizon</th><th>Tickers</th>'
                 '</tr></thead><tbody>')
        for p in predictions:
            h.append('<tr>')
            h.append(f'<td style="white-space:nowrap">{p["published_date"][:10]}</td>')
            h.append(f'<td style="max-width:400px" title="{_esc(p["prediction_text"])}">{_esc(p["prediction_text"][:100])}</td>')
            h.append(f'<td>{_badge_direction(p["direction"])}</td>')
            h.append(f'<td>{_badge_type(p["prediction_type"])}</td>')
            h.append(f'<td>{_badge_confidence(p["confidence"])}</td>')
            h.append(f'<td style="color:#8b949e">{_esc(p["time_horizon"] or "—")}</td>')
            h.append(f'<td style="white-space:normal">{_ticker_tags(p["tickers"])}</td>')
            h.append('</tr>')
        h.append('</tbody></table>')
    h.append('</div>')

    return _page(a["name"], "\n".join(h), "analysts")


def page_tickers():
    rows = _q("""
        SELECT t.id, t.ticker, t.company_name, t.sector,
               t.bull_bear_indicator, t.bull_bear_updated_at,
               COUNT(pt.prediction_id) pred_count,
               MAX(p.created_at) latest
          FROM tickers t
     LEFT JOIN prediction_tickers pt ON pt.ticker_id = t.id
     LEFT JOIN predictions p ON p.id = pt.prediction_id
         GROUP BY t.id
         ORDER BY t.bull_bear_indicator DESC NULLS LAST, pred_count DESC
    """)
    h = ['<h1>Tickers</h1>', f'<p class="sub">{len(rows)} tickers mentioned in predictions</p>']
    h.append('<div class="card"><table><thead><tr>'
             '<th>Ticker</th><th>Company</th><th>Sector</th>'
             '<th>Sentiment</th><th>Predictions</th><th>Latest</th>'
             '</tr></thead><tbody>')
    for r in rows:
        h.append(f'<tr class="click" onclick="window.location=\'/ticker/{r["id"]}\'">')
        h.append(f'<td><a href="/ticker/{r["id"]}" style="font-weight:600">{_esc(r["ticker"])}</a></td>')
        h.append(f'<td>{_esc(r["company_name"] or "—")}</td>')
        h.append(f'<td style="color:#8b949e">{_esc(r["sector"] or "—")}</td>')
        h.append(f'<td>{_bull_bear_widget(r["bull_bear_indicator"], r["bull_bear_updated_at"], compact=True)}</td>')
        h.append(f'<td>{r["pred_count"]}</td>')
        h.append(f'<td style="color:#8b949e">{(r["latest"] or "—")[:10]}</td>')
        h.append('</tr>')
    h.append('</tbody></table></div>')
    return _page("Tickers", "\n".join(h), "tickers")


def page_ticker(ticker_id):
    try:
        t = _q1("SELECT * FROM tickers WHERE id=?", (int(ticker_id),))
    except ValueError:
        t = _q1("SELECT * FROM tickers WHERE ticker=?", (ticker_id.upper(),))
    if not t:
        return _page("Not Found", "<p>Ticker not found.</p>", "tickers")

    predictions = _q("""
        SELECT p.id, p.prediction_text, p.direction, p.prediction_type,
               p.confidence, p.time_horizon, p.created_at,
               a.name analyst_name, a.firm,
               i.published_date, i.youtube_url, i.title interview_title
          FROM prediction_tickers pt
          JOIN predictions p ON pt.prediction_id = p.id
          JOIN analysts a    ON p.analyst_id = a.id
          JOIN interviews i  ON p.interview_id = i.id
         WHERE pt.ticker_id = ?
         ORDER BY i.published_date DESC
         LIMIT 100
    """, (t["id"],))

    bullish  = sum(1 for p in predictions if p["direction"] == "bullish")
    bearish  = sum(1 for p in predictions if p["direction"] == "bearish")
    neutral  = sum(1 for p in predictions if p["direction"] == "neutral")

    h = [f'<a class="back" href="/tickers">Tickers</a>']
    h.append(f'<h1>{_esc(t["ticker"])}</h1>')
    sub_parts = []
    if t["company_name"]: sub_parts.append(t["company_name"])
    if t["sector"]:        sub_parts.append(t["sector"])
    h.append(f'<p class="sub">{_esc(" · ".join(sub_parts)) if sub_parts else "No metadata"}</p>')

    # Bull/Bear indicator
    if t.get("bull_bear_indicator") is not None:
        h.append('<div class="card" style="margin-bottom:16px">')
        h.append('<div style="display:flex;align-items:center;gap:24px;flex-wrap:wrap">')
        h.append('<div>')
        h.append('<div style="font-size:11px;color:#8b949e;margin-bottom:4px">ANALYST SENTIMENT</div>')
        h.append(f'<div style="font-size:36px;font-weight:700">{_bull_bear_widget(t["bull_bear_indicator"])}</div>')
        if t.get("bull_bear_updated_at"):
            h.append(f'<div style="font-size:11px;color:#8b949e;margin-top:4px">Updated {(t["bull_bear_updated_at"] or "")[:10]}</div>')
        h.append('</div>')
        # Scale legend
        h.append('<div style="font-size:11px;color:#8b949e;line-height:1.8">'
                 '<div><span style="color:#f85149">−10</span> Strongly bearish</div>'
                 '<div><span style="color:#d29922"> 0 </span> Neutral</div>'
                 '<div><span style="color:#3fb950">+10</span> Strongly bullish</div>'
                 '</div>')
        h.append('</div>')
        if t.get("bull_bear_summary"):
            h.append(f'<details style="margin-top:14px"><summary style="cursor:pointer;color:#58a6ff;font-size:13px">Full analysis ({len(t["bull_bear_summary"])} chars)</summary>')
            h.append(f'<div style="margin-top:12px;font-size:13px;line-height:1.8;color:#c9d1d9;white-space:pre-wrap">{_esc(t["bull_bear_summary"])}</div>')
            h.append('</details>')
        h.append('</div>')

    # Prediction breakdown
    total = len(predictions)
    if total:
        h.append('<div style="display:flex;gap:20px;margin-bottom:16px;">')
        for label, count, cls in [("Bullish", bullish, "b-bullish"), ("Bearish", bearish, "b-bearish"), ("Neutral", neutral, "b-neutral")]:
            pct = int(count / total * 100) if total else 0
            h.append(f'<div style="text-align:center"><div style="font-size:22px;font-weight:700;color:#f0f6fc">{count}</div>'
                     f'<div><span class="badge {cls}">{label}</span></div>'
                     f'<div style="font-size:11px;color:#8b949e">{pct}%</div></div>')
        h.append('</div>')

    h.append(f'<div class="card"><h2>Predictions ({total})</h2>')
    if not predictions:
        h.append('<p class="sub">No predictions for this ticker yet.</p>')
    else:
        h.append('<table><thead><tr>'
                 '<th>Date</th><th>Analyst</th><th>Prediction</th>'
                 '<th>Direction</th><th>Type</th><th>Horizon</th><th>Source</th>'
                 '</tr></thead><tbody>')
        for p in predictions:
            h.append('<tr>')
            h.append(f'<td style="white-space:nowrap">{p["published_date"][:10]}</td>')
            h.append(f'<td><a href="/analyst/{p["analyst_name"]}">{_esc(p["analyst_name"])}</a>'
                     f'<br><span style="font-size:11px;color:#8b949e">{_esc(p["firm"])}</span></td>')
            h.append(f'<td style="max-width:380px" title="{_esc(p["prediction_text"])}">{_esc(p["prediction_text"][:100])}</td>')
            h.append(f'<td>{_badge_direction(p["direction"])}</td>')
            h.append(f'<td>{_badge_type(p["prediction_type"])}</td>')
            h.append(f'<td style="color:#8b949e">{_esc(p["time_horizon"] or "—")}</td>')
            h.append(f'<td><a href="{_esc(p["youtube_url"])}" target="_blank" style="color:#8b949e;font-size:11px;">↗</a></td>')
            h.append('</tr>')
        h.append('</tbody></table>')
    h.append('</div>')
    return _page(t["ticker"], "\n".join(h), "tickers")


def page_interviews(page_num=1):
    per_page = 50
    offset   = (page_num - 1) * per_page
    total    = _q1("SELECT COUNT(*) c FROM interviews")["c"]

    rows = _q("""
        SELECT i.id, i.title, i.channel_name, i.published_date,
               i.youtube_url,
               i.transcript_text IS NOT NULL has_transcript,
               COUNT(DISTINCT p.id) pred_count,
               GROUP_CONCAT(DISTINCT a.name) analysts
          FROM interviews i
     LEFT JOIN predictions p ON p.interview_id = i.id
     LEFT JOIN analysts a    ON p.analyst_id = a.id
         GROUP BY i.id
         ORDER BY i.published_date DESC
         LIMIT ? OFFSET ?
    """, (per_page, offset))

    h = ['<h1>Interviews</h1>', f'<p class="sub">{total} interviews collected</p>']

    h.append('<div class="card"><table><thead><tr>'
             '<th>Date</th><th>Title</th><th>Channel</th>'
             '<th>Analyst</th><th>Transcript</th><th>Predictions</th>'
             '</tr></thead><tbody>')
    for r in rows:
        t_badge = '<span class="badge b-ok">✓</span>' if r["has_transcript"] else '<span class="badge b-neutral">—</span>'
        h.append(f'<tr class="click" onclick="window.location=\'/interview/{r["id"]}\'">')
        h.append(f'<td style="white-space:nowrap">{r["published_date"]}</td>')
        h.append(f'<td><a href="/interview/{r["id"]}">{_esc(r["title"][:80])}</a></td>')
        h.append(f'<td style="color:#8b949e">{_esc(r["channel_name"])}</td>')
        h.append(f'<td style="color:#8b949e">{_esc(r["analysts"] or "—")}</td>')
        h.append(f'<td>{t_badge}</td>')
        h.append(f'<td>{r["pred_count"]}</td>')
        h.append('</tr>')
    h.append('</tbody></table>')

    # Pagination
    total_pages = (total + per_page - 1) // per_page
    if total_pages > 1:
        h.append('<div style="margin-top:12px;display:flex;gap:8px;align-items:center;font-size:13px;">')
        if page_num > 1:
            h.append(f'<a href="/interviews?page={page_num-1}">← Prev</a>')
        h.append(f'<span style="color:#8b949e">Page {page_num} / {total_pages}</span>')
        if page_num < total_pages:
            h.append(f'<a href="/interviews?page={page_num+1}">Next →</a>')
        h.append('</div>')
    h.append('</div>')

    return _page("Interviews", "\n".join(h), "interviews")


def page_interview(interview_id):
    i = _q1("SELECT * FROM interviews WHERE id=?", (interview_id,))
    if not i:
        return _page("Not Found", "<p>Interview not found.</p>", "interviews")

    predictions = _q("""
        SELECT p.id, p.prediction_text, p.direction, p.prediction_type,
               p.confidence, p.time_horizon, p.raw_quote,
               a.name analyst_name,
               GROUP_CONCAT(t.ticker, ', ') tickers
          FROM predictions p
          JOIN analysts a ON p.analyst_id = a.id
     LEFT JOIN prediction_tickers pt ON pt.prediction_id = p.id
     LEFT JOIN tickers t ON pt.ticker_id = t.id
         WHERE p.interview_id = ?
         GROUP BY p.id
    """, (interview_id,))

    h = [f'<a class="back" href="/interviews">Interviews</a>']
    h.append(f'<h1 style="margin-bottom:8px">{_esc(i["title"])}</h1>')
    h.append(f'<p class="sub">{_esc(i["channel_name"])} · {i["published_date"]} · '
             f'<a href="{_esc(i["youtube_url"])}" target="_blank">Watch on YouTube ↗</a></p>')

    # YouTube embed
    h.append(f'<div style="margin-bottom:16px">'
             f'<iframe width="560" height="315" '
             f'src="https://www.youtube.com/embed/{_esc(i["youtube_id"])}" '
             f'frameborder="0" allowfullscreen style="border-radius:8px;max-width:100%"></iframe></div>')

    h.append(f'<div class="card"><h2>Predictions Extracted ({len(predictions)})</h2>')
    if not predictions:
        h.append('<p class="sub">No predictions extracted from this interview yet.</p>')
    else:
        h.append('<table><thead><tr>'
                 '<th>Analyst</th><th>Prediction</th><th>Direction</th>'
                 '<th>Type</th><th>Confidence</th><th>Horizon</th><th>Tickers</th>'
                 '</tr></thead><tbody>')
        for p in predictions:
            quote_tip = f' title="{_esc(p["raw_quote"])}"' if p["raw_quote"] else ""
            h.append(f'<tr{quote_tip}>')
            h.append(f'<td><a href="/analyst/{p["analyst_name"]}">{_esc(p["analyst_name"])}</a></td>')
            h.append(f'<td style="max-width:400px;white-space:normal">{_esc(p["prediction_text"])}</td>')
            h.append(f'<td>{_badge_direction(p["direction"])}</td>')
            h.append(f'<td>{_badge_type(p["prediction_type"])}</td>')
            h.append(f'<td>{_badge_confidence(p["confidence"])}</td>')
            h.append(f'<td style="color:#8b949e">{_esc(p["time_horizon"] or "—")}</td>')
            h.append(f'<td style="white-space:normal">{_ticker_tags(p["tickers"])}</td>')
            h.append('</tr>')
        h.append('</tbody></table>')
    h.append('</div>')

    if i["transcript_text"]:
        h.append('<div class="card"><details><summary>Full Transcript</summary>')
        h.append(f'<div class="transcript">{_esc(i["transcript_text"])}</div>')
        h.append('</details></div>')
    else:
        h.append('<p style="color:#8b949e;font-size:13px">No transcript available for this interview.</p>')

    return _page(i["title"][:60], "\n".join(h), "interviews")


def page_predictions(params):
    direction  = params.get("direction", [""])[0]
    pred_type  = params.get("type",      [""])[0]
    analyst_id = params.get("analyst",   [""])[0]
    ticker     = params.get("ticker",    [""])[0]
    date_from  = params.get("from",      [""])[0]

    analysts = _q("SELECT id, name FROM analysts WHERE is_active=1 ORDER BY name")
    tickers  = _q("SELECT ticker FROM tickers ORDER BY ticker")

    # Build filter form
    analyst_opts = '<option value="">All Analysts</option>' + "".join(
        f'<option value="{r["id"]}"{" selected" if str(r["id"]) == analyst_id else ""}>{_esc(r["name"])}</option>'
        for r in analysts
    )
    ticker_opts = '<option value="">All Tickers</option>' + "".join(
        f'<option value="{r["ticker"]}"{" selected" if r["ticker"] == ticker else ""}>{_esc(r["ticker"])}</option>'
        for r in tickers
    )
    dir_opts = "".join(
        f'<option value="{v}"{" selected" if v == direction else ""}>{l}</option>'
        for v, l in [("", "All Directions"), ("bullish", "Bullish"), ("bearish", "Bearish"), ("neutral", "Neutral")]
    )
    type_opts = "".join(
        f'<option value="{v}"{" selected" if v == pred_type else ""}>{l}</option>'
        for v, l in [
            ("", "All Types"), ("price_target", "Price Target"), ("sector_call", "Sector Call"),
            ("macro_call", "Macro Call"), ("direction_call", "Direction Call"),
            ("earnings_call", "Earnings Call"), ("other", "Other"),
        ]
    )

    h = ['<h1>Predictions</h1>',
         f'<form method="get" action="/predictions" class="filters">',
         f'<div><label>Direction</label><select name="direction">{dir_opts}</select></div>',
         f'<div><label>Type</label><select name="type">{type_opts}</select></div>',
         f'<div><label>Analyst</label><select name="analyst">{analyst_opts}</select></div>',
         f'<div><label>Ticker</label><select name="ticker">{ticker_opts}</select></div>',
         f'<div><label>From date</label><input type="date" name="from" value="{_esc(date_from)}"></div>',
         '<button type="submit">Filter</button>',
         '<a class="reset" href="/predictions">Reset</a>',
         '</form>']

    # Build query
    wheres, p_args = [], []
    if direction:
        wheres.append("p.direction = ?"); p_args.append(direction)
    if pred_type:
        wheres.append("p.prediction_type = ?"); p_args.append(pred_type)
    if analyst_id:
        wheres.append("p.analyst_id = ?"); p_args.append(analyst_id)
    if ticker:
        wheres.append("EXISTS (SELECT 1 FROM prediction_tickers pt2 JOIN tickers t2 ON pt2.ticker_id=t2.id WHERE pt2.prediction_id=p.id AND t2.ticker=?)"); p_args.append(ticker)
    if date_from:
        wheres.append("i.published_date >= ?"); p_args.append(date_from)

    where_sql = ("WHERE " + " AND ".join(wheres)) if wheres else ""

    rows = _q(f"""
        SELECT p.id, p.prediction_text, p.direction, p.prediction_type,
               p.confidence, p.time_horizon, p.created_at,
               a.name analyst_name,
               i.published_date, i.youtube_url,
               GROUP_CONCAT(t.ticker, ', ') tickers
          FROM predictions p
          JOIN analysts a   ON p.analyst_id   = a.id
          JOIN interviews i ON p.interview_id = i.id
     LEFT JOIN prediction_tickers pt ON pt.prediction_id = p.id
     LEFT JOIN tickers t ON pt.ticker_id = t.id
         {where_sql}
         GROUP BY p.id
         ORDER BY i.published_date DESC
         LIMIT 200
    """, p_args)

    h.append(f'<div class="card"><h2>{len(rows)} predictions</h2>')
    if not rows:
        h.append('<p class="sub">No predictions match the current filters.</p>')
    else:
        h.append('<table><thead><tr>'
                 '<th>Date</th><th>Analyst</th><th>Prediction</th>'
                 '<th>Direction</th><th>Type</th><th>Confidence</th><th>Horizon</th>'
                 '<th>Tickers</th><th>Source</th>'
                 '</tr></thead><tbody>')
        for r in rows:
            h.append('<tr>')
            h.append(f'<td style="white-space:nowrap">{r["published_date"][:10]}</td>')
            h.append(f'<td><a href="/analyst/{r["analyst_name"]}">{_esc(r["analyst_name"])}</a></td>')
            h.append(f'<td style="max-width:380px" title="{_esc(r["prediction_text"])}">{_esc(r["prediction_text"][:100])}</td>')
            h.append(f'<td>{_badge_direction(r["direction"])}</td>')
            h.append(f'<td>{_badge_type(r["prediction_type"])}</td>')
            h.append(f'<td>{_badge_confidence(r["confidence"])}</td>')
            h.append(f'<td style="color:#8b949e">{_esc(r["time_horizon"] or "—")}</td>')
            h.append(f'<td style="white-space:normal">{_ticker_tags(r["tickers"])}</td>')
            h.append(f'<td><a href="{_esc(r["youtube_url"])}" target="_blank" style="color:#8b949e;font-size:11px;">↗</a></td>')
            h.append('</tr>')
        h.append('</tbody></table>')
    h.append('</div>')

    return _page("Predictions", "\n".join(h), "predictions")


def page_candidates():
    rows = _q("""
        SELECT id, name, firm, role, bio, source_youtube_url,
               source_interview_title, discovered_at, status, reviewed_at, notes
          FROM analyst_candidates
         ORDER BY CASE status WHEN 'pending' THEN 0 WHEN 'approved' THEN 1 ELSE 2 END,
                  discovered_at DESC
    """)
    pending = [r for r in rows if r["status"] == "pending"]
    reviewed = [r for r in rows if r["status"] != "pending"]

    h = ['<h1>Analyst Candidates</h1>',
         f'<p class="sub">{len(pending)} pending review · {len(reviewed)} reviewed</p>']

    if pending:
        h.append('<div class="card"><h2>Pending Review</h2>')
        h.append('<table><thead><tr>'
                 '<th>Discovered</th><th>Name</th><th>Firm / Role</th>'
                 '<th>Source Interview</th><th>Actions</th>'
                 '</tr></thead><tbody>')
        for r in pending:
            h.append('<tr>')
            h.append(f'<td style="white-space:nowrap;font-size:12px">{(r["discovered_at"] or "")[:10]}</td>')
            h.append(f'<td style="font-weight:600">{_esc(r["name"])}</td>')
            h.append(f'<td style="color:#8b949e">{_esc(r["firm"] or "—")}'
                     f'{"<br>" + _esc(r["role"]) if r["role"] else ""}</td>')
            if r["source_youtube_url"]:
                h.append(f'<td><a href="{_esc(r["source_youtube_url"])}" target="_blank">'
                         f'{_esc((r["source_interview_title"] or r["source_youtube_url"])[:60])} ↗</a></td>')
            else:
                h.append(f'<td style="color:#8b949e">{_esc(r["source_interview_title"] or "—")}</td>')
            h.append(f'<td style="white-space:nowrap">'
                     f'<form method="post" action="/candidates/approve" style="display:inline;margin:0;padding:0;">'
                     f'<input type="hidden" name="id" value="{r["id"]}">'
                     f'<button style="background:#238636;color:#fff;border:none;border-radius:4px;'
                     f'padding:3px 10px;font-size:12px;cursor:pointer;margin-right:4px;">✓ Approve</button>'
                     f'</form>'
                     f'<form method="post" action="/candidates/reject" style="display:inline;margin:0;padding:0;">'
                     f'<input type="hidden" name="id" value="{r["id"]}">'
                     f'<button style="background:#3b1a1a;color:#f85149;border:none;border-radius:4px;'
                     f'padding:3px 10px;font-size:12px;cursor:pointer;">✕ Reject</button>'
                     f'</form>'
                     f'</td>')
            h.append('</tr>')
        h.append('</tbody></table></div>')
    else:
        h.append('<div class="card"><p class="sub">No candidates pending review.</p></div>')

    if reviewed:
        h.append('<div class="card"><h2>Reviewed</h2>')
        h.append('<table><thead><tr><th>Name</th><th>Firm</th><th>Status</th><th>Reviewed</th><th>Notes</th></tr></thead><tbody>')
        for r in reviewed:
            cls = "b-ok" if r["status"] == "approved" else "b-neutral"
            h.append(f'<tr>'
                     f'<td>{_esc(r["name"])}</td>'
                     f'<td style="color:#8b949e">{_esc(r["firm"] or "—")}</td>'
                     f'<td><span class="badge {cls}">{_esc(r["status"])}</span></td>'
                     f'<td style="font-size:12px;color:#8b949e">{(r["reviewed_at"] or "")[:10]}</td>'
                     f'<td style="color:#8b949e;font-size:12px">{_esc(r["notes"] or "")}</td>'
                     f'</tr>')
        h.append('</tbody></table></div>')

    return _page("Candidates", "\n".join(h), "candidates")


def handle_candidate_action(form, action):
    """POST handler for approve/reject. Returns redirect path."""
    from .db import get_db, approve_candidate, reject_candidate
    cid = int(form.get("id", ["0"])[0])
    conn = get_db()
    if action == "approve":
        approve_candidate(conn, cid)
    else:
        reject_candidate(conn, cid, notes=form.get("notes", [""])[0])
    conn.close()
    return "/candidates"


def page_pipeline():
    rows = _q("""
        SELECT id, phase, started_at, finished_at,
               interviews_found, interviews_new, predictions_found,
               status, error_message,
               ROUND((JULIANDAY(COALESCE(finished_at, datetime('now'))) - JULIANDAY(started_at)) * 86400) seconds
          FROM pipeline_runs
         ORDER BY started_at DESC
         LIMIT 100
    """)

def page_channels():
    """List tracked YouTube channels and their scan status."""
    rows = _q("""
        SELECT c.id, c.name, c.youtube_channel_id, c.youtube_handle, c.description,
               c.last_scanned_at, c.is_active,
               (SELECT COUNT(*) FROM interviews WHERE channel_name = c.name) as total_interviews,
               (SELECT COUNT(*) FROM interviews i 
                JOIN predictions p ON p.interview_id = i.id 
                WHERE i.channel_name = c.name) as with_preds
        FROM channels c
        ORDER BY c.name
    """)
    h = ['<h1>Tracked Channels</h1>',
         f'<p class="sub">{len(rows)} channels — pipeline scans these for new videos daily</p>']
    h.append('<div class="card"><table><thead><tr>'
             '<th>Channel</th><th>YouTube ID</th><th>Handle</th><th>Interviews</th>'
             '<th>Processed</th><th>Hit Rate</th><th>Last Scanned</th><th>Status</th>'
             '</tr></thead><tbody>')
    for r in rows:
        active = r['is_active']
        total = r['total_interviews'] or 0
        preds = r['with_preds'] or 0
        hit = f"{preds/total*100:.0f}%" if total > 0 else "—"
        status = '<span class="badge b-ok">Active</span>' if active else '<span class="badge b-fail">Inactive</span>'
        scanned = r['last_scanned_at'][:16] if r['last_scanned_at'] else "never"
        h.append(f'<tr><td>{_esc(r["name"])}</td><td><code>{_esc(r["youtube_channel_id"])}</code></td>'
                 f'<td><code>{_esc(r["youtube_handle"] or "")}</code></td>'
                 f'<td>{total}</td><td>{preds}</td><td>{hit}</td><td>{scanned}</td><td>{status}</td></tr>')
    h.append('</tbody></table></div>')
    return _page("Channels", "\n".join(h))
    h = ['<h1>Pipeline Runs</h1>', f'<p class="sub">{len(rows)} runs recorded</p>']
    h.append('<div class="card"><table><thead><tr>'
             '<th>Started</th><th>Phase</th><th>Duration</th>'
             '<th>Found</th><th>New</th><th>Predictions</th><th>Status</th><th>Error</th>'
             '</tr></thead><tbody>')
    for r in rows:
        dur = f'{int(r["seconds"])}s' if r["seconds"] is not None else "—"
        err = _esc((r["error_message"] or "")[:60])
        h.append('<tr>')
        h.append(f'<td style="white-space:nowrap;font-size:12px">{(r["started_at"] or "")[:19]}</td>')
        h.append(f'<td style="color:#8b949e">{_esc(r["phase"] or "—")}</td>')
        h.append(f'<td style="color:#8b949e">{dur}</td>')
        h.append(f'<td>{r["interviews_found"]}</td>')
        h.append(f'<td>{r["interviews_new"]}</td>')
        h.append(f'<td>{r["predictions_found"]}</td>')
        h.append(f'<td>{_badge_status(r["status"])}</td>')
        h.append(f'<td style="color:#f85149;font-size:11px">{err}</td>')
        h.append('</tr>')
    h.append('</tbody></table></div>')
    return _page("Pipeline", "\n".join(h), "pipeline")


# ── HTTP handler ─────────────────────────────────────────────────────────────

class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass  # silence request log noise

    def _send(self, body, code=200):
        enc = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(enc)))
        self.end_headers()
        self.wfile.write(enc)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path   = parsed.path.rstrip("/") or "/"
        params = urllib.parse.parse_qs(parsed.query)

        try:
            if path == "/" or path == "":
                self._send(page_dashboard())
            elif path == "/analysts":
                self._send(page_analysts())
            elif path.startswith("/analyst/"):
                self._send(page_analyst(path[len("/analyst/"):]))
            elif path == "/tickers":
                self._send(page_tickers())
            elif path.startswith("/ticker/"):
                self._send(page_ticker(path[len("/ticker/"):]))
            elif path == "/interviews":
                pg = int(params.get("page", ["1"])[0])
                self._send(page_interviews(pg))
            elif path.startswith("/interview/"):
                self._send(page_interview(int(path[len("/interview/"):])))
            elif path == "/predictions":
                self._send(page_predictions(params))
            elif path == "/pipeline":
                self._send(page_pipeline())
            elif path == "/channels":
                self._send(page_channels())
            elif path == "/candidates":
                self._send(page_candidates())
            else:
                self._send("<p>Not found.</p>", 404)
        except Exception as e:
            self._send(f"<pre>Error: {_esc(str(e))}</pre>", 500)

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body   = self.rfile.read(length).decode("utf-8")
        form   = urllib.parse.parse_qs(body)
        path   = self.path.rstrip("/")

        try:
            if path in ("/candidates/approve", "/candidates/reject"):
                action = "approve" if path.endswith("approve") else "reject"
                redirect = handle_candidate_action(form, action)
                self.send_response(303)
                self.send_header("Location", redirect)
                self.end_headers()
            else:
                self._send("<p>Not found.</p>", 404)
        except Exception as e:
            self._send(f"<pre>Error: {_esc(str(e))}</pre>", 500)


# ── Entry point ───────────────────────────────────────────────────────────────

def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=_DEFAULT_PORT)
    ap.add_argument("--db",   type=str, default=None)
    args = ap.parse_args(argv)

    global _DB_PATH
    if args.db:
        _DB_PATH = args.db

    if not os.path.exists(_DB_PATH):
        print(f"DB not found at {_DB_PATH}. Run --init first.", file=sys.stderr)
        return 1

    server = ThreadingHTTPServer(("", args.port), Handler)
    print(f"Analyst Radar UI → http://localhost:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
