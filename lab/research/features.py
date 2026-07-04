"""Reusable, family-agnostic candidate-feature library.

Every function here computes a LEAK-FREE feature from primitives any same-day
long strategy already has by 09:35 ET: the first regular 5-minute candle, the
ticker's prior daily bars, and (optionally) prior SPY/sector-ETF series. Daily
inputs are always sliced strictly before ``trade_date`` so nothing can read the
current session's later bars. The only intraday input is the *first* 5m candle,
which is fully closed at the entry-admission moment.

Design:
    - Pure functions over primitives (not over StrategyContext), so they unit-
      test without constructing a context and any family can call subsets.
    - ``compute_candidate_features`` returns a FLAT dict with a STABLE key set
      (value ``None`` when an input is missing), so a capture run produces a
      rectangular ledger across tickers/days.
    - ``features_from_context`` is the thin adapter that pulls the primitives
      out of a ``StrategyContext`` for a given ticker.

This is the "capture broad" half of validation/feature_search_spec.md: record
everything cheap and leak-free; the locked search grid selects a narrow subset.
"""
from __future__ import annotations

import math
from datetime import date

import numpy as np
import pandas as pd

from trading.lab.research.filters import (
    daily_atr_14,
    first_regular_5m_candle,
    has_split_like_jump,
)

# Stable, ordered feature key set — the capture ledger's columns. Grouped by the
# spec's categories (A gap / B first-candle / C volume / D own-trend / E rel-
# strength / F calendar). Keep in sync with compute_candidate_features().
FEATURE_NAMES: tuple[str, ...] = (
    # A — gap / overnight structure
    "gap_pct_vs_prior_high", "gap_pct_vs_prior_close", "gap_atr",
    "gap_vs_20d_high_pct", "prior_day_return", "prior_day_close_pos",
    "consecutive_up_days",
    # B — first-candle (opening-range) microstructure
    "first_open", "first_close_pos", "first_range_pct", "first_range_atr_frac",
    "first_body_frac", "first_upper_wick_frac", "first_lower_wick_frac",
    "first_return", "breakout_distance", "open_pos_in_first",
    # C — volume / participation
    "first_volume", "first_dollar_volume", "first_vol_frac_of_prior_day",
    "opening_rv", "rvol_20d", "avg_daily_volume",
    # D — stock's own trend / volatility
    "close_vs_own_50d_sma", "close_vs_own_200d_sma", "stock_above_own_50d",
    "adr_pct", "dist_from_20d_high_pct", "realized_vol_20d",
    # E — relative strength / market & sector
    "rel_spy_gap", "stock_5d_ret_minus_spy", "stock_20d_ret_minus_spy",
    "rel_sector_momentum_20d", "spy_first_return", "spy_first_close_pos",
    "beta_60d", "spy_below_50d_sma", "sector_below_50d_sma",
    # F — calendar / seasonality
    "day_of_week", "month", "is_month_end", "is_quarter_end_month", "is_opex",
    # ── peer-review additions (2026-06-14: codex / gemini / smartypants) ──
    # A2 — prior-day full intraday structure (via the prior RTH session)
    "prior_close_vs_vwap_pct", "prior_pm_am_range_ratio", "prior_first_hour_vol_frac",
    "prior_late_volume_share", "prior_afternoon_return_pct", "prior_opening_30m_range_frac",
    # A3 — prior-day daily-only structure
    "prior_open_to_close_conviction", "prior_gap_fill_fraction",
    # B2 — trend / momentum
    "close_channel_pos_20d", "sma20_vs_sma50_pct", "sma50_vs_sma200_pct", "adx14",
    "trend_efficiency_20d", "roc_5d", "roc_20d", "consecutive_down_days",
    # C2 — volatility regime
    "vol_ratio_5d_20d", "realized_vol_percentile_252", "prior_range_expansion_14d",
    "spy_realized_vol_20d", "spy_20d_return",
    # D2 — sector / market context
    "stock_sector_corr_60d", "beta_to_sector_60d", "sector_20d_return",
    "sector_20d_ret_minus_spy",
    # E2 — overnight structure
    "gap_range_frac", "consecutive_gap_up_days", "gap_vs_spy_gap_diff",
    # F2 — liquidity / participation
    "opening_volume_zscore_20d", "prior_volume_ratio_20d", "dollar_volume_trend_5_20",
    # G2 — calendar
    "is_first_trading_day_of_month", "days_since_opex",
    # H2 — statistical
    "gap_zscore_60d", "prior_return_zscore_60d", "first_range_zscore_20d",
    "excess_return_information_ratio_60d", "max_drawdown_20d",
    # ── advanced vol / microstructure (2026-06-14: deep-research) ──
    # I — range-based volatility estimators (prior daily OHLC) + inferred liquidity
    "parkinson_vol_20d", "garman_klass_vol_20d", "yang_zhang_vol_20d",
    "yang_zhang_to_cc_ratio_20d", "roll_spread_pct", "prior_intraday_autocorr_5m",
)


# ── primitive helpers ────────────────────────────────────────────────────────

def _prior(daily: pd.DataFrame | None, trade_date: date) -> pd.DataFrame | None:
    """Daily bars strictly before *trade_date* (the leak-free history)."""
    if daily is None or daily.empty:
        return None
    df = daily[daily.index.date < trade_date]
    return df if not df.empty else None


def _ret_pct(close: pd.Series, n: int) -> float | None:
    """Percent return over the last *n* steps of a close series."""
    if len(close) < n + 1:
        return None
    past = float(close.iloc[-(n + 1)])
    if past <= 0:
        return None
    return (float(close.iloc[-1]) / past - 1.0) * 100.0


def _sma_dist_pct(close: pd.Series, n: int) -> float | None:
    if len(close) < n:
        return None
    sma = float(close.tail(n).mean())
    if sma <= 0:
        return None
    return (float(close.iloc[-1]) - sma) / sma * 100.0


def _below_sma(daily: pd.DataFrame | None, trade_date: date, period: int = 50) -> bool | None:
    """True when prior close < trailing N-day SMA. None if too short/missing."""
    pdf = _prior(daily, trade_date)
    if pdf is None or "close" not in pdf:
        return None
    closes = pdf["close"].astype(float)
    if len(closes) < period:
        return None
    sma = float(closes.tail(period).mean())
    if sma <= 0:
        return None
    return float(closes.iloc[-1]) < sma


def _ny(df: pd.DataFrame) -> pd.DataFrame:
    return df.tz_convert("America/New_York") if df.index.tz is not None else df


def _before(df: pd.DataFrame | None, trade_date: date | None) -> pd.DataFrame | None:
    """Rows strictly before trade_date (leak-free boundary enforced here, not
    trusted from the caller's hydration)."""
    if df is None or df.empty:
        return None
    h = _ny(df)
    if trade_date is not None:
        h = h[h.index.date < trade_date]
    return h if not h.empty else None


def _opening_bar_volumes(hist_5m: pd.DataFrame | None,
                         trade_date: date | None = None) -> pd.Series | None:
    """Per-day volume of the 09:30–09:35 opening bar, from prior 5m sessions."""
    h = _before(hist_5m, trade_date)
    if h is None or "volume" not in h:
        return None
    opening = h.between_time("09:30", "09:35", inclusive="both")
    if opening.empty:
        return None
    return opening.groupby(opening.index.date)["volume"].first()


def _opening_bar_ranges_pct(hist_5m: pd.DataFrame | None,
                            trade_date: date | None = None) -> pd.Series | None:
    """Per-day opening-bar range % ((high-low)/close*100) from prior sessions."""
    h = _before(hist_5m, trade_date)
    if h is None:
        return None
    op = h.between_time("09:30", "09:35", inclusive="both")
    if op.empty:
        return None
    first = op.groupby(op.index.date).first()
    rng = (first["high"] - first["low"]) / first["close"] * 100.0
    return rng.dropna()


def _prior_session_5m(hist_5m: pd.DataFrame | None,
                      trade_date: date | None) -> pd.DataFrame | None:
    """The most recent prior RTH session's 5m bars (date strictly < trade_date)."""
    h = _before(hist_5m, trade_date)
    if h is None:
        return None
    last = max(h.index.date)
    p = h[h.index.date == last]
    return p if not p.empty else None


def _session_vwap(bars: pd.DataFrame | None) -> float | None:
    if bars is None or bars.empty or "volume" not in bars:
        return None
    typ = (bars["high"].astype(float) + bars["low"].astype(float)
           + bars["close"].astype(float)) / 3.0
    vol = bars["volume"].astype(float)
    # Use only rows with finite typical price AND positive finite volume in BOTH
    # numerator and denominator, so a NaN-price row can't misweight the result.
    mask = np.isfinite(typ) & np.isfinite(vol) & (vol > 0)
    if not mask.any():
        return None
    denom = float(vol[mask].sum())
    if denom <= 0:
        return None
    val = float((typ[mask] * vol[mask]).sum()) / denom
    return val if math.isfinite(val) else None


def _wilder_smooth_avg(x: np.ndarray, period: int) -> np.ndarray:
    """Wilder's smoothed *average* (RMA): seed = mean of first `period` values,
    then ``avg_t = (avg_{t-1}·(period-1) + x_t)/period``. (The earlier ADX bug was
    using the *sum* form for the final DX, which inflated ADX by a factor of 14.)"""
    out = np.full(len(x), np.nan)
    if len(x) < period:
        return out
    out[period - 1] = x[:period].mean()
    for i in range(period, len(x)):
        out[i] = (out[i - 1] * (period - 1) + x[i]) / period
    return out


def _adx14(pdf: pd.DataFrame | None, period: int = 14) -> float | None:
    """Wilder ADX(14) on prior daily bars (range 0–100); None if < ~2*period
    valid bars or a degenerate (flat) series."""
    if pdf is None or len(pdf) < 2 * period + 2:
        return None
    h = pdf["high"].astype(float); l = pdf["low"].astype(float); c = pdf["close"].astype(float)
    pc = c.shift(1); ph = h.shift(1); pl = l.shift(1)
    tr = pd.concat([h - l, (h - pc).abs(), (l - pc).abs()], axis=1).max(axis=1)
    up = h - ph; dn = pl - l
    plus = np.where((up > dn) & (up > 0), up, 0.0)
    minus = np.where((dn > up) & (dn > 0), dn, 0.0)
    df = pd.DataFrame({"tr": tr, "plus": plus, "minus": minus}).dropna()
    if len(df) < 2 * period:
        return None
    atr = _wilder_smooth_avg(df["tr"].values, period)
    with np.errstate(divide="ignore", invalid="ignore"):
        pdi = 100 * _wilder_smooth_avg(df["plus"].values, period) / atr
        mdi = 100 * _wilder_smooth_avg(df["minus"].values, period) / atr
        dx = 100 * np.abs(pdi - mdi) / (pdi + mdi)
    dx = dx[np.isfinite(dx)]
    if len(dx) < period:
        return None
    adx = _wilder_smooth_avg(dx, period)[-1]
    return float(adx) if np.isfinite(adx) else None


def _third_friday(year: int, month: int) -> date:
    import calendar as _cal
    fridays = [wk[_cal.FRIDAY] for wk in _cal.monthcalendar(year, month)
               if wk[_cal.FRIDAY] != 0]
    return date(year, month, fridays[2])


def _spy_gap_pct(spy_5m: pd.DataFrame | None, spy_daily: pd.DataFrame | None,
                 trade_date: date) -> float | None:
    """SPY's own gap %: first-bar open vs SPY prior daily high (mirrors d08)."""
    first = first_regular_5m_candle(spy_5m)
    pdf = _prior(spy_daily, trade_date)
    if first is None or pdf is None:
        return None
    ph = float(pdf.iloc[-1]["high"])
    if ph <= 0:
        return None
    return (float(first["open"]) - ph) / ph * 100.0


# ── the aggregator ───────────────────────────────────────────────────────────

def compute_candidate_features(
    *,
    trade_date: date,
    first_bar: pd.Series | None,
    daily: pd.DataFrame | None,
    hist_5m: pd.DataFrame | None = None,
    spy_daily: pd.DataFrame | None = None,
    spy_5m: pd.DataFrame | None = None,
    sector_daily: pd.DataFrame | None = None,
) -> dict[str, float | None]:
    """All leak-free candidate features as a flat dict (stable key set).

    Any feature whose inputs are missing/insufficient is ``None``. ``first_bar``
    is the first regular 5m candle (Series with open/high/low/close/volume);
    ``daily`` is the ticker's daily bars (sliced internally to < trade_date);
    ``sector_daily`` is the candidate's matched sector-ETF daily series.
    """
    f: dict[str, float | None] = {k: None for k in FEATURE_NAMES}

    # F — calendar (always available)
    f["day_of_week"] = float(trade_date.weekday())
    f["month"] = float(trade_date.month)
    f["is_month_end"] = float(trade_date.day >= 25)
    f["is_quarter_end_month"] = float(trade_date.month in (3, 6, 9, 12))
    f["is_opex"] = float(trade_date.weekday() == 4 and 15 <= trade_date.day <= 21)

    pdf = _prior(daily, trade_date)
    atr = daily_atr_14(daily, 14, trade_date) if daily is not None else None
    ob_vols = _opening_bar_volumes(hist_5m, trade_date)  # computed once, reused

    # B — first-candle microstructure
    if first_bar is not None:
        o = float(first_bar["open"]); h = float(first_bar["high"])
        lo = float(first_bar["low"]); c = float(first_bar["close"])
        v = float(first_bar.get("volume", 0.0))
        rng = h - lo
        f["first_open"] = o
        f["first_volume"] = v
        f["first_dollar_volume"] = v * c
        if c > 0:
            f["first_range_pct"] = rng / c * 100.0
        if o > 0:
            f["first_return"] = (c - o) / o * 100.0
            f["breakout_distance"] = (h - o) / o * 100.0
        if rng > 0:
            f["first_close_pos"] = (c - lo) / rng
            f["first_body_frac"] = abs(c - o) / rng
            f["first_upper_wick_frac"] = (h - max(o, c)) / rng
            f["first_lower_wick_frac"] = (min(o, c) - lo) / rng
            f["open_pos_in_first"] = (o - lo) / rng
        if atr and atr > 0:
            f["first_range_atr_frac"] = rng / atr

    # A — gap / overnight structure (needs prior daily + first open)
    if pdf is not None and first_bar is not None:
        prior = pdf.iloc[-1]
        prior_high = float(prior["high"]); prior_close = float(prior["close"])
        prior_low = float(prior["low"])
        o = float(first_bar["open"])
        if prior_high > 0:
            f["gap_pct_vs_prior_high"] = (o - prior_high) / prior_high * 100.0
        if prior_close > 0:
            f["gap_pct_vs_prior_close"] = (o - prior_close) / prior_close * 100.0
        if atr and atr > 0:
            f["gap_atr"] = (o - prior_close) / atr
        high20 = float(pdf["high"].tail(20).max())
        if high20 > 0:
            f["gap_vs_20d_high_pct"] = (o - high20) / high20 * 100.0
        if len(pdf) >= 2:
            prev_close = float(pdf["close"].iloc[-2])
            if prev_close > 0:
                f["prior_day_return"] = (prior_close - prev_close) / prev_close * 100.0
        prng = prior_high - prior_low
        if prng > 0:
            f["prior_day_close_pos"] = (prior_close - prior_low) / prng
        # consecutive up-days into the gap (trailing close>prev-close streak)
        closes = pdf["close"].astype(float).values
        streak = 0
        for i in range(len(closes) - 1, 0, -1):
            if closes[i] > closes[i - 1]:
                streak += 1
            else:
                break
        f["consecutive_up_days"] = float(streak)

    # C — volume / participation
    if pdf is not None and first_bar is not None:
        prior_vol = float(pdf.iloc[-1].get("volume", 0.0))
        v = float(first_bar.get("volume", 0.0))
        if prior_vol > 0:
            f["first_vol_frac_of_prior_day"] = v / prior_vol
        if ob_vols is not None and len(ob_vols) >= 10:
            mean_all = float(ob_vols.mean())
            if mean_all > 0:
                f["opening_rv"] = v / mean_all
            mean_20 = float(ob_vols.tail(20).mean())
            if mean_20 > 0:
                f["rvol_20d"] = v / mean_20
    if pdf is not None and "volume" in pdf:
        f["avg_daily_volume"] = float(pdf["volume"].tail(14).mean())

    # D — stock's own trend / volatility
    if pdf is not None and "close" in pdf:
        closes = pdf["close"].astype(float)
        prior_close = float(closes.iloc[-1])
        f["close_vs_own_50d_sma"] = _sma_dist_pct(closes, 50)
        f["close_vs_own_200d_sma"] = _sma_dist_pct(closes, 200)
        if len(closes) >= 50:
            f["stock_above_own_50d"] = float(prior_close > float(closes.tail(50).mean()))
        if atr and atr > 0 and prior_close > 0:
            f["adr_pct"] = atr / prior_close * 100.0
        if len(closes) >= 20:
            high20 = float(pdf["high"].tail(20).max())
            if high20 > 0:
                f["dist_from_20d_high_pct"] = (prior_close - high20) / high20 * 100.0
            rets = closes.pct_change().dropna().tail(20)
            if len(rets) >= 2:
                f["realized_vol_20d"] = float(rets.std()) * 100.0

    # E — relative strength / market & sector
    spy_pdf = _prior(spy_daily, trade_date)
    if pdf is not None and spy_pdf is not None and "close" in pdf and "close" in spy_pdf:
        sc = pdf["close"].astype(float); spc = spy_pdf["close"].astype(float)
        for n, key in ((5, "stock_5d_ret_minus_spy"), (20, "stock_20d_ret_minus_spy")):
            sr, mr = _ret_pct(sc, n), _ret_pct(spc, n)
            if sr is not None and mr is not None:
                f[key] = sr - mr
        # 60d beta of stock daily returns to SPY daily returns
        sr = sc.pct_change().dropna().tail(60)
        mr = spc.pct_change().dropna().tail(60)
        joined = pd.concat([sr, mr], axis=1, join="inner").dropna()
        if len(joined) >= 30:
            var = float(joined.iloc[:, 1].var())
            if var > 0:
                f["beta_60d"] = float(joined.cov().iloc[0, 1]) / var
    sec_pdf = _prior(sector_daily, trade_date)
    if pdf is not None and sec_pdf is not None and "close" in pdf and "close" in sec_pdf:
        sr = _ret_pct(pdf["close"].astype(float), 20)
        kr = _ret_pct(sec_pdf["close"].astype(float), 20)
        if sr is not None and kr is not None:
            f["rel_sector_momentum_20d"] = sr - kr

    gap_high = f["gap_pct_vs_prior_high"]
    spy_gap = _spy_gap_pct(spy_5m, spy_daily, trade_date)
    if gap_high is not None and spy_gap is not None and abs(spy_gap) > 1e-9:
        f["rel_spy_gap"] = gap_high / spy_gap

    spy_first = first_regular_5m_candle(spy_5m)
    if spy_first is not None:
        so = float(spy_first["open"]); sh = float(spy_first["high"])
        sl = float(spy_first["low"]); scl = float(spy_first["close"])
        if so > 0:
            f["spy_first_return"] = (scl - so) / so * 100.0
        if sh - sl > 0:
            f["spy_first_close_pos"] = (scl - sl) / (sh - sl)

    below_spy = _below_sma(spy_daily, trade_date, 50)
    if below_spy is not None:
        f["spy_below_50d_sma"] = float(below_spy)
    below_sec = _below_sma(sector_daily, trade_date, 50)
    if below_sec is not None:
        f["sector_below_50d_sma"] = float(below_sec)

    # ===== peer-review additions (2026-06-14) =====
    closes_p = pdf["close"].astype(float) if (pdf is not None and "close" in pdf) else None
    # Trailing raw-price stats are corrupted if the window spans a split; null
    # them when a split-like jump (>40% close-to-close, OR today's open vs prior
    # close) appears in the matched window. Passing the open catches a reverse
    # split that happened overnight (today's open on a different price scale).
    _fo = float(first_bar["open"]) if first_bar is not None else None
    split_21 = has_split_like_jump(daily, trade_date, lookback=21, open_price=_fo) if daily is not None else False
    split_63 = has_split_like_jump(daily, trade_date, lookback=63, open_price=_fo) if daily is not None else False
    # 252-pctile consumes 252 rolling-20d windows ≈ 272 closes — guard that span.
    split_252 = has_split_like_jump(daily, trade_date, lookback=272, open_price=_fo) if daily is not None else False

    # A2 — prior-day full intraday structure
    psess = _prior_session_5m(hist_5m, trade_date)
    if psess is not None and not psess.empty:
        last_close = float(psess["close"].iloc[-1])
        vwap = _session_vwap(psess)
        if vwap and vwap > 0:
            f["prior_close_vs_vwap_pct"] = (last_close - vwap) / vwap * 100.0
        am = psess.between_time("09:30", "12:00", inclusive="left")
        pm = psess.between_time("12:00", "16:00", inclusive="both")
        if not am.empty and not pm.empty:
            am_rng = float(am["high"].max() - am["low"].min())
            pm_rng = float(pm["high"].max() - pm["low"].min())
            if am_rng > 0:
                f["prior_pm_am_range_ratio"] = pm_rng / am_rng
        tot_v = float(psess["volume"].sum())
        if tot_v > 0:
            # left-inclusive = a true 60-minute window (09:30–10:25 bars), since
            # 5m bars are left-labeled (the 10:30 bar would be 10:30–10:35).
            fh = psess.between_time("09:30", "10:30", inclusive="left")
            f["prior_first_hour_vol_frac"] = float(fh["volume"].sum()) / tot_v
            late = psess.between_time("14:00", "16:00", inclusive="both")
            f["prior_late_volume_share"] = float(late["volume"].sum()) / tot_v
        aft = psess.between_time("13:00", "16:00", inclusive="both")
        if not aft.empty:
            a_open = float(aft["open"].iloc[0])
            if a_open > 0:
                f["prior_afternoon_return_pct"] = (last_close - a_open) / a_open * 100.0
        op30 = psess.between_time("09:30", "10:00", inclusive="left")
        full_rng = float(psess["high"].max() - psess["low"].min())
        if not op30.empty and full_rng > 0:
            f["prior_opening_30m_range_frac"] = (
                float(op30["high"].max() - op30["low"].min()) / full_rng)

    # A3 — prior-day daily-only
    if pdf is not None and len(pdf) >= 1:
        prow = pdf.iloc[-1]
        po = float(prow["open"]); pc = float(prow["close"])
        ph = float(prow["high"]); pl = float(prow["low"])
        if ph - pl > 0:
            f["prior_open_to_close_conviction"] = abs(pc - po) / (ph - pl)
        if len(pdf) >= 2:
            ptp_close = float(pdf["close"].iloc[-2])
            gap = po - ptp_close
            if gap > 0:
                f["prior_gap_fill_fraction"] = float(min(1.0, max(0.0, (po - pl) / gap)))

    # B2 — trend / momentum (split-gated by matched window: ~20d→split_21,
    # 50d→split_63, 200d→split_252; ADX over ~30d→split_63)
    if closes_p is not None:
        if pdf is not None and len(pdf) >= 20 and not split_21:
            low20 = float(pdf["low"].tail(20).min()); high20 = float(pdf["high"].tail(20).max())
            if high20 > low20:
                f["close_channel_pos_20d"] = (float(closes_p.iloc[-1]) - low20) / (high20 - low20)
        if len(closes_p) >= 50 and not split_63:
            s20 = float(closes_p.tail(20).mean()); s50 = float(closes_p.tail(50).mean())
            if s50 > 0:
                f["sma20_vs_sma50_pct"] = (s20 / s50 - 1.0) * 100.0
        if len(closes_p) >= 200 and not split_252:
            s50 = float(closes_p.tail(50).mean()); s200 = float(closes_p.tail(200).mean())
            if s200 > 0:
                f["sma50_vs_sma200_pct"] = (s50 / s200 - 1.0) * 100.0
        f["adx14"] = None if split_63 else _adx14(pdf)
        if len(closes_p) >= 21 and not split_21:
            net = float(closes_p.iloc[-1] - closes_p.iloc[-21])
            path = float(closes_p.tail(21).diff().abs().sum())
            if path > 0:
                f["trend_efficiency_20d"] = net / path
        if not split_21:
            f["roc_5d"] = _ret_pct(closes_p, 5)
            f["roc_20d"] = _ret_pct(closes_p, 20)
        cl = closes_p.values
        streak = 0
        for i in range(len(cl) - 1, 0, -1):
            if cl[i] < cl[i - 1]:
                streak += 1
            else:
                break
        f["consecutive_down_days"] = float(streak)

    # C2 — volatility regime
    if closes_p is not None:
        rets = closes_p.pct_change().dropna()
        if len(rets) >= 20 and not split_21:
            v5 = float(rets.tail(5).std()); v20 = float(rets.tail(20).std())
            if v20 > 0:
                f["vol_ratio_5d_20d"] = v5 / v20
        if len(rets) >= 272 and not split_252:
            roll = rets.rolling(20).std().dropna().tail(252)
            if len(roll) >= 50:
                f["realized_vol_percentile_252"] = float((roll <= float(roll.iloc[-1])).mean())
    if pdf is not None and len(pdf) >= 15 and not split_21:
        rng = pdf["high"].astype(float) - pdf["low"].astype(float)
        baseline = float(rng.iloc[-15:-1].mean())
        if baseline > 0:
            f["prior_range_expansion_14d"] = float(rng.iloc[-1]) / baseline

    # SPY momentum / vol regime
    if spy_pdf is not None and "close" in spy_pdf:
        spc_series = spy_pdf["close"].astype(float)
        f["spy_20d_return"] = _ret_pct(spc_series, 20)
        sret = spc_series.pct_change().dropna()
        if len(sret) >= 20:
            f["spy_realized_vol_20d"] = float(sret.tail(20).std()) * (252 ** 0.5) * 100.0

    # D2 — sector / market context
    if closes_p is not None and sec_pdf is not None and "close" in sec_pdf:
        if not split_63:
            sr = closes_p.pct_change().dropna().tail(60)
            kr = sec_pdf["close"].astype(float).pct_change().dropna().tail(60)
            j = pd.concat([sr, kr], axis=1, join="inner").dropna()
            if len(j) >= 30:
                corr = float(j.iloc[:, 0].corr(j.iloc[:, 1]))  # NaN if a leg is constant
                if math.isfinite(corr):
                    f["stock_sector_corr_60d"] = corr
                vark = float(j.iloc[:, 1].var())
                if vark > 0:
                    f["beta_to_sector_60d"] = float(j.cov().iloc[0, 1]) / vark
        f["sector_20d_return"] = _ret_pct(sec_pdf["close"].astype(float), 20)
        if spy_pdf is not None and "close" in spy_pdf:
            sec20 = _ret_pct(sec_pdf["close"].astype(float), 20)
            spy20 = _ret_pct(spy_pdf["close"].astype(float), 20)
            if sec20 is not None and spy20 is not None:
                f["sector_20d_ret_minus_spy"] = sec20 - spy20

    # E2 — overnight structure
    if pdf is not None and first_bar is not None:
        prow = pdf.iloc[-1]
        ph = float(prow["high"]); pl = float(prow["low"]); pc = float(prow["close"])
        o = float(first_bar["open"])
        if ph - pl > 0:
            f["gap_range_frac"] = (o - pc) / (ph - pl)
        if len(pdf) >= 2 and "open" in pdf and "high" in pdf:
            # "gap up" = open above the PRIOR HIGH, matching gap_pct_vs_prior_high
            # and d-family admission (not merely open > prior close).
            opens = pdf["open"].astype(float).values
            highs = pdf["high"].astype(float).values
            streak = 0
            if o > ph:
                streak = 1
                for i in range(len(highs) - 1, 0, -1):
                    if opens[i] > highs[i - 1]:
                        streak += 1
                    else:
                        break
            f["consecutive_gap_up_days"] = float(streak)
        if spy_pdf is not None and spy_5m is not None and "close" in spy_pdf and pc > 0:
            sfirst = first_regular_5m_candle(spy_5m)
            spc = float(spy_pdf["close"].iloc[-1])
            if sfirst is not None and spc > 0:
                spy_gap_c = (float(sfirst["open"]) - spc) / spc * 100.0
                f["gap_vs_spy_gap_diff"] = (o - pc) / pc * 100.0 - spy_gap_c

    # F2 — liquidity / participation
    if first_bar is not None and ob_vols is not None and len(ob_vols) >= 20:
        l20 = ob_vols.tail(20); mu = float(l20.mean()); sd = float(l20.std())
        if sd > 0:
            f["opening_volume_zscore_20d"] = (float(first_bar.get("volume", 0.0)) - mu) / sd
    if pdf is not None and "volume" in pdf and len(pdf) >= 21 and not split_21:
        prior_vol = float(pdf["volume"].iloc[-1])
        base = float(pdf["volume"].iloc[-21:-1].mean())
        if base > 0:
            f["prior_volume_ratio_20d"] = prior_vol / base
    if pdf is not None and "volume" in pdf and "close" in pdf and len(pdf) >= 20 and not split_21:
        dv = pdf["close"].astype(float) * pdf["volume"].astype(float)
        d20 = float(dv.tail(20).mean())
        if d20 > 0:
            f["dollar_volume_trend_5_20"] = float(dv.tail(5).mean()) / d20

    # G2 — calendar
    if pdf is not None and len(pdf) >= 1:
        last_dt = pdf.index[-1]
        f["is_first_trading_day_of_month"] = float(
            last_dt.month != trade_date.month or last_dt.year != trade_date.year)
    tf_this = _third_friday(trade_date.year, trade_date.month)
    if trade_date >= tf_this:  # on opex day itself, days_since_opex = 0
        ref = tf_this
    else:
        py, pm_ = ((trade_date.year - 1, 12) if trade_date.month == 1
                   else (trade_date.year, trade_date.month - 1))
        ref = _third_friday(py, pm_)
    f["days_since_opex"] = float((trade_date - ref).days)

    # H2 — statistical
    if (pdf is not None and "open" in pdf and "high" in pdf and first_bar is not None
            and not split_63 and f["gap_pct_vs_prior_high"] is not None):
        ph_series = pdf["high"].astype(float)
        hist_gap = ((pdf["open"].astype(float) - ph_series.shift(1))
                    / ph_series.shift(1) * 100.0).dropna().tail(60)
        if len(hist_gap) >= 30 and float(hist_gap.std()) > 0:
            f["gap_zscore_60d"] = (
                (f["gap_pct_vs_prior_high"] - float(hist_gap.mean())) / float(hist_gap.std()))
    if closes_p is not None and f["prior_day_return"] is not None and not split_63:
        rr = closes_p.pct_change().dropna() * 100.0
        if len(rr) >= 61:
            ref_r = rr.tail(61).iloc[:-1]  # exclude the latest (the value being scored)
            if float(ref_r.std()) > 0:
                f["prior_return_zscore_60d"] = (
                    (f["prior_day_return"] - float(ref_r.mean())) / float(ref_r.std()))
    if first_bar is not None and f["first_range_pct"] is not None:
        orp = _opening_bar_ranges_pct(hist_5m, trade_date)
        if orp is not None and len(orp) >= 20:
            l20 = orp.tail(20); sd = float(l20.std())
            if sd > 0:
                f["first_range_zscore_20d"] = (f["first_range_pct"] - float(l20.mean())) / sd
    if closes_p is not None and spy_pdf is not None and "close" in spy_pdf and not split_63:
        sr = closes_p.pct_change().dropna().tail(60)
        mr = spy_pdf["close"].astype(float).pct_change().dropna().tail(60)
        j = pd.concat([sr, mr], axis=1, join="inner").dropna()
        if len(j) >= 30:
            ex = j.iloc[:, 0] - j.iloc[:, 1]
            if float(ex.std()) > 0:
                f["excess_return_information_ratio_60d"] = float((252 ** 0.5) * ex.mean() / ex.std())
    if closes_p is not None and len(closes_p) >= 20 and not split_21:
        w = closes_p.tail(20); peak = w.cummax()
        f["max_drawdown_20d"] = float(((w - peak) / peak).min()) * 100.0

    # I — advanced range-based volatility (prior daily OHLC) + microstructure.
    # Range estimators use intraday extremes → far more efficient than close-to-
    # close; Yang-Zhang additionally captures the overnight gap variance, which is
    # the relevant component for a gap strategy. All annualized %, 20-day window.
    if (pdf is not None and len(pdf) >= 21 and not split_21
            and {"open", "high", "low", "close"} <= set(pdf.columns)):
        wd = pdf.tail(21)
        o_ = wd["open"].astype(float).values; h_ = wd["high"].astype(float).values
        l_ = wd["low"].astype(float).values; c_ = wd["close"].astype(float).values
        ann = (252 ** 0.5) * 100.0
        with np.errstate(invalid="ignore", divide="ignore"):
            hl = np.log(h_[1:] / l_[1:])          # 20 within-bar log ranges
            co = np.log(c_[1:] / o_[1:])          # 20 open→close log returns
            park = np.sqrt(np.nanmean(hl ** 2) / (4 * np.log(2)))
            gk = np.sqrt(np.nanmean(0.5 * hl ** 2 - (2 * np.log(2) - 1) * co ** 2))
        if np.isfinite(park):
            f["parkinson_vol_20d"] = float(park) * ann
        if np.isfinite(gk):
            f["garman_klass_vol_20d"] = float(gk) * ann
        with np.errstate(invalid="ignore", divide="ignore"):
            on = np.log(o_[1:] / c_[:-1])         # overnight log returns (needs prior close)
            rs = (np.log(h_[1:] / c_[1:]) * np.log(h_[1:] / o_[1:])
                  + np.log(l_[1:] / c_[1:]) * np.log(l_[1:] / o_[1:]))  # Rogers-Satchell
        n = len(on)
        if n >= 2:
            var_o = float(np.nanvar(on, ddof=1)); var_c = float(np.nanvar(co, ddof=1))
            var_rs = float(np.nanmean(rs))
            k = 0.34 / (1.34 + (n + 1) / (n - 1))
            yz2 = var_o + k * var_c + (1 - k) * var_rs
            if np.isfinite(yz2) and yz2 > 0:
                yz = float(np.sqrt(yz2)) * ann
                f["yang_zhang_vol_20d"] = yz
                cc = float(np.nanstd(np.diff(np.log(c_)), ddof=1)) * ann
                if cc > 0:
                    f["yang_zhang_to_cc_ratio_20d"] = yz / cc

    # Inferred liquidity (Roll spread) and microstructure regime (autocorrelation)
    # from the prior session's 5m bars — no Level-2/NBBO data needed.
    if psess is not None and "close" in psess and len(psess) >= 11:
        pc_close = psess["close"].astype(float)
        dp = pc_close.diff().dropna().values
        mean_px = float(pc_close.mean())
        if len(dp) >= 5 and mean_px > 0:
            cov = float(np.cov(dp[1:], dp[:-1])[0, 1])
            # Roll: bid-ask bounce induces negative serial covariance of price
            # changes; spread = 2*sqrt(-cov). Non-negative cov → 0 (no inference).
            f["roll_spread_pct"] = (2.0 * np.sqrt(-cov) / mean_px * 100.0) if cov < 0 else 0.0
        rets = pc_close.pct_change().dropna().values
        if len(rets) >= 10 and float(np.nanstd(rets)) > 0:
            ac = float(np.corrcoef(rets[1:], rets[:-1])[0, 1])
            if np.isfinite(ac):
                f["prior_intraday_autocorr_5m"] = ac

    # Final integrity pass: never emit a non-finite float (NaN/±inf from a
    # constant series, zero variance, etc.) — coerce to None so the ledger stays
    # rectangular and JSON/parquet-safe.
    for k, v in f.items():
        if isinstance(v, float) and not math.isfinite(v):
            f[k] = None

    return f


def features_from_context(context, ticker: str, first_bar: pd.Series | None = None,
                          sector_symbol: str | None = None) -> dict[str, float | None]:
    """Adapter: pull primitives for *ticker* out of a StrategyContext.

    ``first_bar`` defaults to the ticker's first regular 5m candle; pass it in
    if the caller already computed it. ``sector_symbol`` selects the matched
    sector-ETF daily series from ``context.extra_daily``.
    """
    if first_bar is None:
        first_bar = first_regular_5m_candle(context.bars_5m.get(ticker))
    sector_daily = context.extra_daily.get(sector_symbol) if sector_symbol else None
    return compute_candidate_features(
        trade_date=context.trade_date,
        first_bar=first_bar,
        daily=context.daily.get(ticker),
        hist_5m=context.historical_5m.get(ticker),
        spy_daily=context.spy_daily,
        spy_5m=context.spy_5m,
        sector_daily=sector_daily,
    )
