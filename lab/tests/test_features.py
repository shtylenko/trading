"""Tests for research/features.py — the reusable candidate-feature library.

Covers: stable key set, individual computations against hand-figured values,
graceful degradation on missing inputs, and the leak-free guarantee (current-
and future-dated daily rows must never affect a feature)."""

from __future__ import annotations

import math
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from trading.lab.research.features import (
    FEATURE_NAMES,
    compute_candidate_features,
    features_from_context,
)
from trading.lab.core.models import StrategyContext

NY = ZoneInfo("America/New_York")
TRADE_DATE = date(2024, 4, 1)


def _first_bar(o, h, l, c, v=5e5):
    return pd.Series({"open": o, "high": h, "low": l, "close": c, "volume": v})


def _daily(n=260, last_close=100.0, step=0.0, prior_high=None, prior_vol=2e6, end=None):
    """Daily bars ending the trading day before TRADE_DATE."""
    end = end or (TRADE_DATE - timedelta(days=1))
    idx = pd.date_range(end=end, periods=n, freq="D", tz=NY)
    closes = np.linspace(last_close - step * (n - 1), last_close, n)
    df = pd.DataFrame({
        "open": closes, "high": closes + 1.0, "low": closes - 1.0,
        "close": closes, "volume": np.full(n, prior_vol),
    }, index=idx)
    if prior_high is not None:
        df.iloc[-1, df.columns.get_loc("high")] = prior_high
    return df


def test_stable_key_set():
    f = compute_candidate_features(trade_date=TRADE_DATE, first_bar=None, daily=None)
    assert tuple(f.keys()) == FEATURE_NAMES
    # only calendar features are non-null with no market inputs
    nonnull = {k for k, v in f.items() if v is not None}
    # calendar-only features need no market inputs (incl. days_since_opex)
    assert nonnull == {"day_of_week", "month", "is_month_end",
                       "is_quarter_end_month", "is_opex", "days_since_opex"}


def test_calendar_features():
    f = compute_candidate_features(trade_date=date(2024, 4, 1), first_bar=None, daily=None)
    assert f["day_of_week"] == 0.0  # Monday
    assert f["month"] == 4.0
    assert f["is_month_end"] == 0.0
    assert f["is_quarter_end_month"] == 0.0
    # 2024-06-21 is the third Friday of June (opex + quarter-end month)
    g = compute_candidate_features(trade_date=date(2024, 6, 21), first_bar=None, daily=None)
    assert g["is_opex"] == 1.0
    assert g["is_quarter_end_month"] == 1.0


def test_first_candle_microstructure():
    # open 104, high 104.6, low 103.9, close 104.2  -> range 0.7
    f = compute_candidate_features(
        trade_date=TRADE_DATE, first_bar=_first_bar(104.0, 104.6, 103.9, 104.2),
        daily=None)
    assert abs(f["first_close_pos"] - (104.2 - 103.9) / 0.7) < 1e-9
    assert abs(f["first_body_frac"] - 0.2 / 0.7) < 1e-9
    assert abs(f["first_upper_wick_frac"] - (104.6 - 104.2) / 0.7) < 1e-9
    assert abs(f["first_lower_wick_frac"] - (104.0 - 103.9) / 0.7) < 1e-9
    assert abs(f["open_pos_in_first"] - (104.0 - 103.9) / 0.7) < 1e-9
    assert f["first_dollar_volume"] == 104.2 * 5e5
    assert f["first_return"] > 0  # green


def test_gap_features_against_prior_daily():
    daily = _daily(prior_high=102.0)  # prior close ~100, prior high forced 102
    f = compute_candidate_features(
        trade_date=TRADE_DATE, first_bar=_first_bar(104.0, 104.6, 103.9, 104.5),
        daily=daily)
    assert abs(f["gap_pct_vs_prior_high"] - (104.0 - 102.0) / 102.0 * 100) < 1e-6
    assert abs(f["gap_pct_vs_prior_close"] - (104.0 - 100.0) / 100.0 * 100) < 1e-6
    assert f["gap_atr"] is not None
    assert f["avg_daily_volume"] == 2e6


def test_consecutive_up_days():
    # strictly increasing closes -> long up streak
    up = _daily(n=10, last_close=110.0, step=1.0)
    f = compute_candidate_features(trade_date=TRADE_DATE,
                                   first_bar=_first_bar(111, 112, 110, 111), daily=up)
    assert f["consecutive_up_days"] == 9.0


def test_relative_strength_needs_spy():
    daily = _daily(prior_high=102.0)
    f_no_spy = compute_candidate_features(
        trade_date=TRADE_DATE, first_bar=_first_bar(104, 104.6, 103.9, 104.5), daily=daily)
    assert f_no_spy["rel_spy_gap"] is None
    assert f_no_spy["stock_20d_ret_minus_spy"] is None
    spy_daily = _daily(prior_high=99.5)  # SPY prior high 99.5 -> small +gap, divisible
    spy_5m = pd.DataFrame(
        {"open": [100.0], "high": [100.5], "low": [99.5], "close": [100.2], "volume": [1e6]},
        index=pd.date_range(datetime(2024, 4, 1, 9, 30, tzinfo=NY), periods=1, freq="5min", tz=NY))
    f = compute_candidate_features(
        trade_date=TRADE_DATE, first_bar=_first_bar(104, 104.6, 103.9, 104.5),
        daily=daily, spy_daily=spy_daily, spy_5m=spy_5m)
    assert f["rel_spy_gap"] is not None
    assert f["spy_first_return"] is not None
    assert f["stock_20d_ret_minus_spy"] is not None


def test_leak_free_future_rows_ignored():
    """Daily rows on/after trade_date must not change any feature."""
    daily = _daily(prior_high=102.0)
    base = compute_candidate_features(
        trade_date=TRADE_DATE, first_bar=_first_bar(104, 104.6, 103.9, 104.5), daily=daily)
    # append a wild current-day + future row that, if used, would move everything
    poison = daily.copy()
    extra = pd.DataFrame({"open": [999.0, 999.0], "high": [9999.0, 9999.0],
                          "low": [1.0, 1.0], "close": [999.0, 999.0], "volume": [9e9, 9e9]},
                         index=pd.to_datetime([datetime(2024, 4, 1, tzinfo=NY),
                                               datetime(2024, 4, 2, tzinfo=NY)]))
    poison = pd.concat([poison, extra])
    after = compute_candidate_features(
        trade_date=TRADE_DATE, first_bar=_first_bar(104, 104.6, 103.9, 104.5), daily=poison)
    assert base == after


def _daily_noisy(n=300, start=80.0, seed=0, end=None):
    """Daily bars with real volatility (random walk) so vol/beta/zscore features
    are non-degenerate. Calendar-day index ending the day before TRADE_DATE."""
    end = end or (TRADE_DATE - timedelta(days=1))
    idx = pd.date_range(end=end, periods=n, freq="D", tz=NY)
    rng = np.random.default_rng(seed)
    close = start * np.exp(np.cumsum(rng.normal(0.001, 0.02, n)))
    high = close * (1 + np.abs(rng.normal(0, 0.01, n)))
    low = close * (1 - np.abs(rng.normal(0, 0.01, n)))
    openp = close * (1 + rng.normal(0, 0.005, n))
    return pd.DataFrame({"open": openp, "high": high, "low": low, "close": close,
                         "volume": rng.uniform(1e6, 5e6, n)}, index=idx)


def _hist_5m(days=25, base=100.0, seed=7):
    """`days` prior RTH sessions of 5m bars (78 bars 09:30–15:55 each), with
    per-day variation so opening volume/range distributions are non-degenerate."""
    rng = np.random.default_rng(seed)
    frames = []
    for d in pd.bdate_range(end=TRADE_DATE - timedelta(days=1), periods=days):
        idx = pd.date_range(datetime(d.year, d.month, d.day, 9, 30, tzinfo=NY),
                            periods=78, freq="5min", tz=NY)
        lvl = base * (1 + rng.normal(0, 0.02))
        wob = abs(rng.normal(0.3, 0.1))  # varying opening-bar width
        closes = lvl + np.linspace(0, 1, 78)
        vol = rng.uniform(8e4, 3e5, 78)  # varying volume (opening bar included)
        frames.append(pd.DataFrame(
            {"open": closes, "high": closes + wob, "low": closes - wob,
             "close": closes, "volume": vol}, index=idx))
    return pd.concat(frames)


# New peer-review features that always compute given rich inputs (the only
# input-conditional one is prior_gap_fill_fraction — needs the prior day to gap up).
_NEW_FEATURES = [
    "prior_close_vs_vwap_pct", "prior_pm_am_range_ratio", "prior_first_hour_vol_frac",
    "prior_late_volume_share", "prior_afternoon_return_pct", "prior_opening_30m_range_frac",
    "prior_open_to_close_conviction", "close_channel_pos_20d", "sma20_vs_sma50_pct",
    "sma50_vs_sma200_pct", "adx14", "trend_efficiency_20d", "roc_5d", "roc_20d",
    "consecutive_down_days", "vol_ratio_5d_20d", "realized_vol_percentile_252",
    "prior_range_expansion_14d", "spy_realized_vol_20d", "spy_20d_return",
    "stock_sector_corr_60d", "beta_to_sector_60d", "sector_20d_return",
    "sector_20d_ret_minus_spy", "gap_range_frac", "consecutive_gap_up_days",
    "gap_vs_spy_gap_diff", "opening_volume_zscore_20d", "prior_volume_ratio_20d",
    "dollar_volume_trend_5_20", "is_first_trading_day_of_month", "days_since_opex",
    "gap_zscore_60d", "prior_return_zscore_60d", "first_range_zscore_20d",
    "excess_return_information_ratio_60d", "max_drawdown_20d",
    "parkinson_vol_20d", "garman_klass_vol_20d", "yang_zhang_vol_20d",
    "yang_zhang_to_cc_ratio_20d", "roll_spread_pct", "prior_intraday_autocorr_5m",
]


def _spy_5m_bar():
    return pd.DataFrame(
        {"open": [100.0], "high": [100.5], "low": [99.5], "close": [100.2], "volume": [1e6]},
        index=pd.date_range(datetime(2024, 4, 1, 9, 30, tzinfo=NY), periods=1, freq="5min", tz=NY))


def _gap_first_bar(daily, gap=1.02):
    """A first 5m candle a few % above the daily's last close — a realistic gap
    that won't trip the >40% open-vs-prior-close split guard."""
    o = float(daily["close"].iloc[-1]) * gap
    return _first_bar(o, o * 1.006, o * 0.999, o * 1.004)


def test_new_features_coverage_rich_inputs():
    daily = _daily_noisy(seed=1)
    f = compute_candidate_features(
        trade_date=TRADE_DATE, first_bar=_gap_first_bar(daily),
        daily=daily, hist_5m=_hist_5m(25),
        spy_daily=_daily_noisy(seed=2), spy_5m=_spy_5m_bar(),
        sector_daily=_daily_noisy(seed=3))
    for k in _NEW_FEATURES:
        assert f[k] is not None, f"{k} unexpectedly null with rich inputs"
    assert "prior_gap_fill_fraction" in f  # conditional, key must still exist
    # days_since_opex: 2024-04-01 precedes Apr opex (19th) -> ref = Mar 15 (3rd Fri)
    assert f["days_since_opex"] == float((date(2024, 4, 1) - date(2024, 3, 15)).days)


def test_new_features_leak_free_hist_5m():
    """A poison 5m bar dated on/after trade_date must not change prior-session feats."""
    hist = _hist_5m(25)
    base = compute_candidate_features(
        trade_date=TRADE_DATE, first_bar=_first_bar(104, 104.6, 103.9, 104.5),
        daily=_daily_noisy(seed=1), hist_5m=hist)
    poison = pd.concat([hist, pd.DataFrame(
        {"open": [9999.0], "high": [9999.0], "low": [9999.0], "close": [9999.0], "volume": [9e9]},
        index=pd.date_range(datetime(2024, 4, 1, 9, 30, tzinfo=NY), periods=1, freq="5min", tz=NY))])
    after = compute_candidate_features(
        trade_date=TRADE_DATE, first_bar=_first_bar(104, 104.6, 103.9, 104.5),
        daily=_daily_noisy(seed=1), hist_5m=poison)
    for k in ("prior_close_vs_vwap_pct", "prior_first_hour_vol_frac",
              "opening_volume_zscore_20d", "first_range_zscore_20d"):
        assert base[k] == after[k], k


def test_adx14_bounds_and_flat_series():
    daily = _daily_noisy(seed=5)
    f = compute_candidate_features(
        trade_date=TRADE_DATE, first_bar=_gap_first_bar(daily), daily=daily)
    assert f["adx14"] is not None and 0.0 <= f["adx14"] <= 100.0  # was 14x (>100) before fix
    # flat (zero-range-movement) series → degenerate → None, not a number
    flat = _daily(n=60)  # constant closes
    g = compute_candidate_features(
        trade_date=TRADE_DATE, first_bar=_first_bar(100, 100.5, 99.5, 100.2), daily=flat)
    assert g["adx14"] is None


def test_days_since_opex_boundaries():
    def dso(d):
        return compute_candidate_features(trade_date=d, first_bar=None, daily=None)["days_since_opex"]
    assert dso(date(2024, 6, 21)) == 0.0   # 3rd Friday (opex day itself) → 0, not 35
    assert dso(date(2024, 6, 24)) == 3.0   # Monday after June opex
    assert dso(date(2024, 6, 20)) == float((date(2024, 6, 20) - date(2024, 5, 17)).days)  # before → May opex
    assert dso(date(2024, 1, 2)) == float((date(2024, 1, 2) - date(2023, 12, 15)).days)   # Jan → Dec opex


def test_consecutive_gap_up_uses_prior_high():
    idx = pd.date_range(end=TRADE_DATE - timedelta(days=1), periods=5, freq="D", tz=NY)
    daily = pd.DataFrame({"open": [100.0] * 5, "high": [105.0] * 5, "low": [95.0] * 5,
                          "close": [100.0] * 5, "volume": [1e6] * 5}, index=idx)
    # open 103 > prior close 100 but < prior high 105 → NOT a gap-up by family def
    f = compute_candidate_features(
        trade_date=TRADE_DATE, first_bar=_first_bar(103, 103.5, 102.5, 103.2), daily=daily)
    assert f["consecutive_gap_up_days"] == 0.0
    # open 106 > prior high 105 → gap-up
    g = compute_candidate_features(
        trade_date=TRADE_DATE, first_bar=_first_bar(106, 106.5, 105.5, 106.2), daily=daily)
    assert g["consecutive_gap_up_days"] >= 1.0


def test_split_gate_nulls_trailing_features():
    daily = _daily_noisy(seed=1).copy()
    daily.iloc[-5:, daily.columns.get_loc("close")] *= 0.5  # ~50% jump in trailing window
    f = compute_candidate_features(
        trade_date=TRADE_DATE, first_bar=_gap_first_bar(daily), daily=daily)
    assert f["vol_ratio_5d_20d"] is None
    assert f["sma20_vs_sma50_pct"] is None
    assert f["adx14"] is None


def test_no_non_finite_values_on_degenerate_inputs():
    flat = _daily(n=260)  # constant closes → zero variance everywhere
    f = compute_candidate_features(
        trade_date=TRADE_DATE, first_bar=_first_bar(100, 100.5, 99.5, 100.2),
        daily=flat, spy_daily=_daily(n=260), sector_daily=_daily(n=260))
    for k, v in f.items():
        assert v is None or (isinstance(v, float) and math.isfinite(v)), k


def test_features_from_context_adapter():
    daily = _daily(prior_high=102.0)
    bars_5m = pd.DataFrame(
        {"open": [104.0], "high": [104.6], "low": [103.9], "close": [104.5], "volume": [5e5]},
        index=pd.date_range(datetime(2024, 4, 1, 9, 30, tzinfo=NY), periods=1, freq="5min", tz=NY))
    ctx = StrategyContext(
        trade_date=TRADE_DATE, release_id="capture", testset="unit",
        bars_5m={"AAPL": bars_5m}, daily={"AAPL": daily})
    f = features_from_context(ctx, "AAPL")
    assert f["gap_pct_vs_prior_high"] is not None
    assert abs(f["first_open"] - 104.0) < 1e-9
