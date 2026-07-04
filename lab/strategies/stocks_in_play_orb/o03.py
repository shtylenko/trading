"""o03 — Stocks-in-Play Opening Range Breakout Phase v2 (ML + pullback entry).

Strategy identity:
    Name: Stocks-in-Play Opening Range Breakout
    Alias: stocks_in_play_orb
    Letter: o
    Release: o03

Research thesis (Phase v2, see designs/mlspec.md):
    The v1 stop-order breakout entry loses ~-0.35R per trade to whipsaw and
    spread-crossing costs. Replacing it with a passive pullback limit order
    placed 0.02 x ATR14 below the opening-range high after the breach flips
    expectancy positive: the stop sits only ~0.8R below the fill while the
    winners (earnings-day momentum runners held to EOD) are unchanged.
    A LightGBM classifier trained on 2024 walk-forward data ranks candidates;
    the top 10 by predicted P(hit +2R before stop) are traded. When the model
    artifact is unavailable the release degrades to relative-volume ranking,
    which performed comparably in the 2024 study.

Entry rules:
    - All v1 (o02) Stocks-in-Play filters: price > $5, 14-day avg volume
      >= 1M, 14-day ATR > $0.50, green first 5-minute candle, RV >= 2.0.
    - Candidates ranked by ML probability (fallback: RV); top 10 selected.
    - Trigger: 1-minute close above the first 5-minute candle high H.
    - Entry: buy limit at H - 0.02 x ATR14, working for 30 minutes after the
      trigger breach (strict through-the-limit fills; maker execution).

Exit and risk rules:
    - Stop at H - 0.10 x ATR14 (the original SSRN risk unit R).
    - 1% account risk per trade on the full R distance, 4x leverage cap.
    - No profit target: exit any open position at 15:59 New York time.
"""

from __future__ import annotations

import hashlib
import logging
import os
import pickle
from pathlib import Path

import numpy as np

from trading.lab.strategies.base import StrategyRelease
from trading.lab.core.models import Candidate, Signal, StrategyContext
from trading.lab.core.time_utils import ny_dt
from trading.lab.research.filters import first_regular_5m_bar, first_regular_5m_candle
from trading.lab.strategies.stocks_in_play_orb.common import build_sip_base

logger = logging.getLogger("strategy_lab.strategies.o03")

MODEL_PATH = Path(__file__).parent / "research" / "artifacts" / "lgbm_orb_v2.pkl"

TOP_N = 10
PULLBACK_OFFSET_ATR = 0.02
STOP_OFFSET_ATR = 0.10
PULLBACK_TTL_MIN = 30


def _load_model():
    """Load the LightGBM artifact; return None when unavailable."""
    if not MODEL_PATH.exists():
        logger.warning("o03 model artifact missing at %s; falling back to RV ranking", MODEL_PATH)
        return None
    try:
        with open(MODEL_PATH, "rb") as f:
            payload = pickle.load(f)
        return payload  # {"model": LGBMClassifier, "features": [...]}
    except Exception as exc:  # lightgbm missing, version skew, corrupt file
        logger.warning("o03 model artifact could not be loaded (%s); falling back to RV ranking", exc)
        return None


class Release(StrategyRelease):
    release_id = "o03"
    strategy_letter = "o"
    strategy_alias = "stocks_in_play_orb"
    strategy_name = "Stocks-in-Play Opening Range Breakout v2 (ML + pullback limit)"
    description = (
        "Phase v2: v1 SIP filters, LightGBM candidate ranking (top 10, RV fallback), "
        "passive pullback limit entry at H - 0.02 ATR after 1m breach (30m TTL, strict fills), "
        "stop at H - 0.10 ATR, 1% risk, 4x leverage cap, MOC close at 15:59."
    )
    historical_5m_lookback_days = 14
    requires_rth_1m = True
    requires_spy_daily = True
    entry_style = "pullback_limit"

    _model_payload = None
    _model_loaded = False

    @classmethod
    def model_payload(cls):
        # The artifact was trained on 2024 data, so evals on earlier years
        # must disable it to avoid look-ahead; RV ranking is used instead.
        if os.environ.get("O03_DISABLE_ML", "").lower() in ("1", "true", "yes"):
            return None
        if not cls._model_loaded:
            cls._model_payload = _load_model()
            cls._model_loaded = True
        return cls._model_payload

    @classmethod
    def signature_inputs(cls):
        """Fold the active ranking mode into the run signature.

        The model pickle is gitignored, so a clone without it (or with
        ``O03_DISABLE_ML=1``) silently ranks by relative volume instead of the
        ML model — a materially different strategy. Hashing the artifact bytes
        (or a fixed RV sentinel) ensures those runs get distinct signatures
        rather than masquerading as the same experiment.
        """
        payload = cls.model_payload()
        if payload is None:
            return [("o03_ranking", b"RV_FALLBACK")]
        try:
            sha = hashlib.sha256(MODEL_PATH.read_bytes()).hexdigest()
        except OSError:
            sha = "unreadable"
        feats = ",".join(payload.get("features", []))
        return [("o03_model_sha", sha.encode()), ("o03_features", feats.encode())]

    def _spy_features(self, context: StrategyContext) -> dict[str, float]:
        out = {"spy_gap": 0.0, "spy_ret_5m": 0.0, "spy_vwap_dist": 0.0, "spy_vr": 1.0}
        spy_5m = context.spy_5m
        spy_daily = context.spy_daily
        prior_close = None
        if spy_daily is not None and not spy_daily.empty:
            hist = spy_daily[spy_daily.index.date < context.trade_date]
            if not hist.empty:
                prior_close = float(hist["close"].iloc[-1])
                tr = np.maximum(
                    hist["high"] - hist["low"],
                    np.maximum(
                        (hist["high"] - hist["close"].shift(1)).abs(),
                        (hist["low"] - hist["close"].shift(1)).abs(),
                    ),
                )
                atr5 = tr.rolling(5).mean().iloc[-1]
                atr20 = tr.rolling(20).mean().iloc[-1]
                if np.isfinite(atr5) and np.isfinite(atr20) and atr20 > 0:
                    out["spy_vr"] = float(atr5 / atr20)
        first = first_regular_5m_candle(spy_5m)
        if first is not None:
            o = float(first["open"])
            c = float(first["close"])
            h = float(first["high"])
            l = float(first["low"])
            out["spy_ret_5m"] = (c - o) / o
            # VWAP distance: prefer the 1-minute cumulative VWAP over the
            # first five minutes (matches how the model feature was built in
            # training); fall back to the 5m bar typical-price approximation.
            vwap = None
            spy_1m = context.bars_1m.get("SPY")
            if spy_1m is not None and not spy_1m.empty:
                first5 = spy_1m.between_time("09:30", "09:34", inclusive="both")
                if not first5.empty and float(first5["volume"].sum()) > 0:
                    tp1 = (first5["high"] + first5["low"] + first5["close"]) / 3.0
                    vwap = float((tp1 * first5["volume"]).sum() / first5["volume"].sum())
            if vwap is None:
                vwap = (h + l + c) / 3.0
            out["spy_vwap_dist"] = (c - vwap) / vwap if vwap > 0 else 0.0
            if prior_close:
                out["spy_gap"] = (o - prior_close) / prior_close
        return out

    def build_candidates(self, context: StrategyContext) -> list[Candidate]:
        spy_feats = self._spy_features(context)
        rows: list[Candidate] = []
        for ticker, bars in context.bars_5m.items():
            base = build_sip_base(
                ticker,
                bars,
                context.daily.get(ticker),
                context.historical_5m.get(ticker),
                context.trade_date,
            )
            if base is None:
                continue

            atr = base.daily_atr_14
            f_open, f_high = base.first_open, base.first_high
            f_low, f_close = base.first_low, base.first_close

            features = {
                "rv": base.rv,
                "gap_pct": base.gap_pct,
                "gap_abs": abs(base.gap_pct),
                "atr_pct": atr / base.prior_close,
                "range_width_atr": (f_high - f_low) / atr,
                "or_close_pos": (f_close - f_low) / (f_high - f_low) if f_high > f_low else 0.5,
                "f5_body_ratio": (f_close - f_open) / (f_high - f_low) if f_high > f_low else 0.0,
                "f5_ret": (f_close - f_open) / f_open,
                "log_dollar_vol": float(np.log10(max(base.avg_vol_14 * base.prior_close, 1.0))),
                "vol_concentration": base.first_volume / max(base.avg_vol_14, 1.0),
                "prior_day_ret": base.prior_day_ret,
                "or_vol_ratio": base.rv,
                "dow": float(context.trade_date.weekday()),
                **spy_feats,
                "window": 5.0,
            }

            rows.append(
                Candidate(
                    ticker=ticker,
                    score=base.rv,
                    reason="stocks_in_play_v2",
                    features={
                        **features,
                        "daily_atr_14": atr,
                        "mean_opening_volume": base.mean_opening_volume,
                        "first_open": f_open,
                        "first_high": f_high,
                        "first_low": f_low,
                        "first_close": f_close,
                        "first_volume": base.first_volume,
                        "or_start_minute": base.or_start_minute,
                    },
                )
            )

        payload = self.model_payload()
        if payload is not None and rows:
            import pandas as pd

            feature_names = payload["features"]
            try:
                # A missing/renamed/non-finite feature (model-artifact skew)
                # must NOT crash the whole backtest. Fall back to the RV
                # ranking already set on Candidate.score.
                X = pd.DataFrame(
                    [[float(c.features[name]) for name in feature_names] for c in rows],
                    columns=feature_names,
                )
                if not np.all(np.isfinite(X.to_numpy())):
                    raise ValueError("non-finite feature value")
                probs = payload["model"].predict_proba(X)[:, 1]
            except (KeyError, ValueError, TypeError) as exc:
                logger.warning(
                    "o03 ML scoring failed (%s); falling back to RV ranking for %s",
                    exc, context.trade_date,
                )
            else:
                for c, p in zip(rows, probs):
                    c.score = float(p)
                    c.features["probability_score"] = float(p)
                    c.reason = "stocks_in_play_v2_ml"

        rows.sort(key=lambda c: c.score or 0.0, reverse=True)
        rows = rows[:TOP_N]
        for idx, row in enumerate(rows, start=1):
            row.rank = idx
        return rows

    def build_signal(self, context: StrategyContext, candidate: Candidate) -> Signal | None:
        bars = context.bars_5m.get(candidate.ticker)
        first_bar = first_regular_5m_bar(bars)
        if first_bar is None:
            return None
        first_ts, first = first_bar
        high = float(first["high"])
        atr = candidate.features["daily_atr_14"]

        entry_trigger = high
        stop_price = entry_trigger - STOP_OFFSET_ATR * atr
        pullback_limit = entry_trigger - PULLBACK_OFFSET_ATR * atr

        risk_per_share = entry_trigger - stop_price
        if risk_per_share <= 0:
            return None

        # Position sizing: 1% risk of account capital on the full R distance
        account_capital = 100_000.0
        risk_budget = account_capital * 0.01
        qty = risk_budget / risk_per_share

        # Enforce hard 4x leverage cap
        max_capital = account_capital * 4.0
        required_capital = qty * pullback_limit
        if required_capital > max_capital:
            qty = max_capital / pullback_limit
        qty = max(1, int(qty))  # floor so the leverage cap is never exceeded

        metadata = {
            **candidate.features,
            "release": self.release_id,
            "account_capital": account_capital,
            "risk_per_share": risk_per_share,
            "shares": qty,
            "leverage": (qty * pullback_limit) / account_capital,
            "pullback_limit": pullback_limit,
            "pullback_ttl_min": PULLBACK_TTL_MIN,
            "ml_model_version": "lgbm_orb_v2" if self.model_payload() is not None else None,
        }

        return Signal(
            ticker=candidate.ticker,
            setup_type="orb_pullback_limit_v2",
            signal_time=first_ts.to_pydatetime() if hasattr(first_ts, "to_pydatetime") else first_ts,
            entry_trigger=entry_trigger,
            stop_price=stop_price,
            target_price=None,  # No target (EOD close only)
            metadata=metadata,
        )

    def exit_cutoff(self, context: StrategyContext):
        # Flatten exactly at 15:59 New York time (strict EOD close)
        return ny_dt(context.trade_date, 15, 59)
