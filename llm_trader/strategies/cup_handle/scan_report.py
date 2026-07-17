"""Render an as-of cup-and-handle scan as a self-contained HTML chart page.

For every armed ticker in an :class:`AsofScanResult` this builds a candlestick
chart overlaid with exactly the inputs the detector used to justify the plan —
SMA20/50/200 (the trend gate), the cup geometry (left lip, cup low, right lip,
handle high), and the resulting plan levels (trigger, stop, T1, T2) — plus the
cup depth and arm-expiry labels.

The output is one **self-contained** HTML file: the charting library and all
data are inlined, so it opens straight from ``file://`` with no server and no
network (it works offline, which matters on a slow connection).  It only ever
reads bars dated on or before the scan day, so the picture is point-in-time.
"""

from __future__ import annotations

import html
import json
from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

import pandas as pd

from trading.marketdata import fetch_bars

from .config import CupHandleConfig
from .patterns import _prep_daily

_ASSET = Path(__file__).resolve().parent / "assets" / "lightweight-charts.standalone.production.js"

# Overlay colours (kept in one place so the legend and series agree).
_SMA_COLORS = {"sma20": "#f5a623", "sma50": "#4a90e2", "sma200": "#9013fe"}
_PLAN_COLORS = {
    "trigger": "#2962ff",
    "stop": "#e5484d",
    "target1": "#30a46c",
    "target2": "#1a7a4c",
    "handle_high": "#8b8b8b",
}


def _prepared_frame(ticker: str, cfg: CupHandleConfig) -> Optional[pd.DataFrame]:
    """Re-derive the enriched frame the detector saw, as of ``cfg.end``.

    Mirrors ``detect_ticker``'s fetch window so the geometry indices stored in
    ``formation_key`` line up with this frame's rows.  Never fetches past
    ``cfg.end``.
    """
    warmup = max(220, cfg.cup_max_bars + cfg.handle_max_bars + cfg.atr_period + 40)
    start = datetime.combine(cfg.start, datetime.min.time(), tzinfo=timezone.utc) - timedelta(
        days=int(warmup * 1.7)
    )
    end = datetime.combine(cfg.end, datetime.max.time(), tzinfo=timezone.utc)
    df = fetch_bars(ticker, "1day", start=start, end=end, adjustment="raw")
    if df is None or df.empty:
        return None
    return _prep_daily(df, cfg)


def _iso(ts) -> str:
    return (ts.date() if hasattr(ts, "date") else pd.Timestamp(ts).date()).isoformat()


def _line_series(frame: pd.DataFrame, col: str) -> list[dict]:
    out = []
    for ts, val in frame[col].items():
        if pd.notna(val):
            out.append({"time": _iso(ts), "value": round(float(val), 4)})
    return out


def _ticker_payload(entry, cfg: CupHandleConfig) -> Optional[dict]:
    frame = _prepared_frame(entry.ticker, cfg)
    if frame is None or frame.empty:
        return None
    f = entry.features
    try:
        left_i, low_i, right_i = (int(x) for x in str(f.get("formation_key", "")).split("|"))
    except (ValueError, TypeError):
        return None
    n = len(frame)
    if not (0 <= left_i <= low_i <= right_i < n):
        return None

    w0 = max(0, left_i - 15)
    window = frame.iloc[w0:]

    bars, volume = [], []
    for ts, row in window.iterrows():
        t = _iso(ts)
        bars.append(
            {
                "time": t,
                "open": round(float(row["open"]), 4),
                "high": round(float(row["high"]), 4),
                "low": round(float(row["low"]), 4),
                "close": round(float(row["close"]), 4),
            }
        )
        up = float(row["close"]) >= float(row["open"])
        volume.append(
            {"time": t, "value": float(row["volume"]), "color": "#26a69a80" if up else "#ef535080"}
        )

    def mark(i, position, shape, text):
        return {
            "time": _iso(frame.index[i]),
            "position": position,
            "color": "#c026d3",
            "shape": shape,
            "text": text,
        }

    markers = [
        mark(left_i, "aboveBar", "circle", f"L lip {f.get('left_lip_px')}"),
        mark(low_i, "belowBar", "circle", f"cup low {f.get('cup_low_px')}"),
        mark(right_i, "aboveBar", "circle", f"R lip {f.get('right_lip_px')}"),
        {
            "time": entry.day.isoformat(),
            "position": "belowBar",
            "color": _PLAN_COLORS["trigger"],
            "shape": "arrowUp",
            "text": "ARM",
        },
    ]

    price_lines = [
        {"price": float(f["entry_trigger"]), "title": "trigger", "color": _PLAN_COLORS["trigger"]},
        {"price": float(f["stop_px"]), "title": "stop", "color": _PLAN_COLORS["stop"]},
        {"price": float(f["target1_px"]), "title": "T1", "color": _PLAN_COLORS["target1"]},
        {"price": float(f["target2_px"]), "title": "T2", "color": _PLAN_COLORS["target2"]},
        {"price": float(f["handle_high"]), "title": "handle high", "color": _PLAN_COLORS["handle_high"]},
    ]

    return {
        "ticker": entry.ticker,
        "as_of": entry.day.isoformat(),
        "bar_close": entry.bar_close,
        "cup_depth_pct": f.get("cup_depth_pct"),
        "cup_depth_px": f.get("cup_depth_px"),
        "arm_expiry_bars": f.get("arm_expiry_bars"),
        "max_entry_gap_atr": f.get("max_entry_gap_atr"),
        "atr": f.get("atr"),
        "trigger": f.get("entry_trigger"),
        "stop": f.get("stop_px"),
        "target1": f.get("target1_px"),
        "target2": f.get("target2_px"),
        "bars": bars,
        "volume": volume,
        "sma20": _line_series(window, "sma20"),
        "sma50": _line_series(window, "sma50"),
        "sma200": _line_series(window, "sma200"),
        "markers": markers,
        "priceLines": price_lines,
    }


def build_report(result, cfg: CupHandleConfig) -> dict:
    """Build the chart payload for every armed ticker in ``result``."""
    scan_cfg = replace(cfg, start=result.day, end=result.day)
    tickers = []
    for entry in result.arms:
        payload = _ticker_payload(entry, scan_cfg)
        if payload is not None:
            tickers.append(payload)
    return {
        "as_of": result.day.isoformat(),
        "strategy": "cup_handle",
        "symbols_scanned": len(result.symbols_scanned),
        "symbols_failed": result.symbols_failed,
        "tickers": tickers,
    }


def render_html(report: dict) -> str:
    lib = _ASSET.read_text(encoding="utf-8")
    data = json.dumps(report, separators=(",", ":"))
    title = f"cup_handle arms — {html.escape(report['as_of'])}"
    return _TEMPLATE.replace("/*__LIB__*/", lib).replace('"__REPORT__"', data).replace(
        "__TITLE__", title
    )


def write_report(result, cfg: CupHandleConfig, path: str | Path) -> Path:
    """Render the report for ``result`` to ``path`` and return the path."""
    report = build_report(result, cfg)
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render_html(report), encoding="utf-8")
    return out


_TEMPLATE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<style>
  :root { color-scheme: light dark; }
  * { box-sizing: border-box; }
  body { margin: 0; font: 13px -apple-system, system-ui, sans-serif;
         display: flex; height: 100vh; background: #fff; color: #111; }
  @media (prefers-color-scheme: dark) { body { background: #16181d; color: #e6e6e6; } }
  #side { width: 230px; flex: none; overflow-y: auto; border-right: 1px solid #8883;
          padding: 8px; }
  #side h1 { font-size: 13px; margin: 4px 6px 10px; opacity: .7; font-weight: 600; }
  .item { padding: 8px 10px; border-radius: 8px; cursor: pointer; margin-bottom: 2px; }
  .item:hover { background: #8881; }
  .item.sel { background: #2962ff22; }
  .item b { display: block; font-size: 14px; }
  .item small { opacity: .65; }
  #main { flex: 1; display: flex; flex-direction: column; min-width: 0; }
  #info { padding: 10px 14px; border-bottom: 1px solid #8883; }
  #info h2 { margin: 0 0 6px; font-size: 18px; }
  .chips { display: flex; flex-wrap: wrap; gap: 6px; }
  .chip { padding: 3px 9px; border-radius: 999px; background: #8881; font-size: 12px; }
  .chip.k { font-weight: 600; }
  #chart { flex: 1; min-height: 0; }
  #empty { margin: auto; opacity: .6; }
  .legend { display:flex; gap:12px; padding:6px 14px; font-size:11px; opacity:.8; flex-wrap:wrap;}
  .legend span::before { content:"● "; }
</style></head>
<body>
  <div id="side"><h1>arms <span id="count"></span></h1><div id="list"></div></div>
  <div id="main">
    <div id="info"></div>
    <div class="legend">
      <span style="color:#f5a623">SMA20</span>
      <span style="color:#4a90e2">SMA50</span>
      <span style="color:#9013fe">SMA200</span>
      <span style="color:#2962ff">trigger</span>
      <span style="color:#e5484d">stop</span>
      <span style="color:#30a46c">T1/T2</span>
      <span style="color:#c026d3">cup lips / low</span>
    </div>
    <div id="chart"></div>
  </div>
<script>/*__LIB__*/</script>
<script>
const REPORT = "__REPORT__";
const LWC = window.LightweightCharts;
const listEl = document.getElementById("list");
const infoEl = document.getElementById("info");
const chartEl = document.getElementById("chart");
document.getElementById("count").textContent = "(" + REPORT.tickers.length + ")";
let chart = null;

function fmt(v){ return (v===null||v===undefined) ? "–" : v; }

function draw(p){
  infoEl.innerHTML =
    "<h2>" + p.ticker + " <small style='opacity:.5;font-size:13px'>as of " + p.as_of + "</small></h2>" +
    "<div class='chips'>" +
      "<span class='chip k'>cup_depth " + fmt(p.cup_depth_pct) + "%</span>" +
      "<span class='chip k'>arm_expiry_bars " + fmt(p.arm_expiry_bars) + "</span>" +
      "<span class='chip'>ATR " + fmt(p.atr) + "</span>" +
      "<span class='chip'>trigger " + fmt(p.trigger) + "</span>" +
      "<span class='chip'>stop " + fmt(p.stop) + "</span>" +
      "<span class='chip'>T1 " + fmt(p.target1) + "</span>" +
      "<span class='chip'>T2 " + fmt(p.target2) + "</span>" +
      "<span class='chip'>max_gap " + fmt(p.max_entry_gap_atr) + "×ATR</span>" +
    "</div>";
  chartEl.innerHTML = "";
  const dark = matchMedia("(prefers-color-scheme: dark)").matches;
  chart = LWC.createChart(chartEl, {
    layout: { background: { color: "transparent" }, textColor: dark ? "#bbb" : "#333" },
    grid: { vertLines: { color: "#8882" }, horzLines: { color: "#8882" } },
    rightPriceScale: { borderColor: "#8883" },
    timeScale: { borderColor: "#8883", timeVisible: false },
    crosshair: { mode: 0 },
    autoSize: true,
  });
  const candle = chart.addCandlestickSeries({
    upColor:"#26a69a", downColor:"#ef5350", borderVisible:false,
    wickUpColor:"#26a69a", wickDownColor:"#ef5350",
  });
  candle.setData(p.bars);
  candle.setMarkers(p.markers);
  p.priceLines.forEach(function(pl){
    candle.createPriceLine({ price: pl.price, color: pl.color, title: pl.title,
      lineWidth: 1, lineStyle: 2, axisLabelVisible: true });
  });
  function line(data, color){
    if(!data.length) return;
    const s = chart.addLineSeries({ color: color, lineWidth: 1,
      priceLineVisible:false, lastValueVisible:false, crosshairMarkerVisible:false });
    s.setData(data);
  }
  line(p.sma20, "#f5a623"); line(p.sma50, "#4a90e2"); line(p.sma200, "#9013fe");
  const vol = chart.addHistogramSeries({ priceFormat:{type:"volume"}, priceScaleId:"vol" });
  vol.priceScale().applyOptions({ scaleMargins:{ top:0.82, bottom:0 } });
  vol.setData(p.volume);
  chart.timeScale().fitContent();
}

function select(el){
  Array.from(listEl.children).forEach(c=>c.classList.remove("sel"));
  el.classList.add("sel");
}

if(!REPORT.tickers.length){
  infoEl.innerHTML = "<div id='empty'>No arms on " + REPORT.as_of + ".</div>";
} else {
  REPORT.tickers.forEach(function(p, i){
    const el = document.createElement("div");
    el.className = "item";
    el.innerHTML = "<b>" + p.ticker + "</b><small>cup " + fmt(p.cup_depth_pct) +
      "% · expiry " + fmt(p.arm_expiry_bars) + "b</small>";
    el.onclick = function(){ select(el); draw(p); };
    listEl.appendChild(el);
    if(i === 0){ select(el); draw(p); }
  });
}
</script>
</body></html>
"""
