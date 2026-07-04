from __future__ import annotations

from datetime import datetime

import numpy as np
import pandas as pd

from .models import ExecutionConfig, Signal, SimulatedTrade


def _time_stop_triggered(
    signal: Signal,
    entry_price: float,
    bar_open: float,
    ts,
    direction: str = "long",
) -> bool:
    """Optional time stop: exit at the bar open once ``time_stop_at`` (NY,
    "HH:MM" in signal metadata) has passed and the unrealized R measured at
    the open is below ``time_stop_min_r``. Winners past the threshold keep
    running — this only cuts positions whose move never showed up.
    """
    at = signal.metadata.get("time_stop_at")
    if not at:
        return False
    ts_ny = ts.tz_convert("America/New_York") if getattr(ts, "tzinfo", None) else ts
    parts = str(at).split(":")
    if len(parts) != 2 or not all(p.isdigit() for p in parts):
        raise ValueError(
            f"time_stop_at must be 'HH:MM', got {at!r} for {signal.ticker}"
        )
    hh, mm = int(parts[0]), int(parts[1])
    if (ts_ny.hour, ts_ny.minute) < (hh, mm):
        return False
    min_r = float(signal.metadata.get("time_stop_min_r", 0.0))
    risk = abs(signal.entry_trigger - signal.stop_price)
    if risk <= 0:
        return False
    sign = -1.0 if direction == "short" else 1.0
    unrealized_r = sign * (bar_open - entry_price) / risk
    return unrealized_r < min_r


def simulate_long_breakout(
    bars_5m: pd.DataFrame,
    signal: Signal,
    cutoff: datetime,
    config: ExecutionConfig,
) -> SimulatedTrade | None:
    """Simulate a conservative long breakout trade on 5-minute OHLCV bars."""
    if bars_5m is None or bars_5m.empty:
        return None

    trigger = signal.entry_trigger
    stop = signal.stop_price
    target = signal.target_price
    risk = trigger - stop
    if risk <= 0:
        return None

    # Strict temporal alignment: never fill on the same bar used to define
    # the setup levels. This avoids the common opening-range look-ahead leak.
    active = bars_5m[(bars_5m.index > signal.signal_time) & (bars_5m.index <= cutoff)]
    if active.empty:
        return None

    entry_time = None
    entry_price = None
    mfe = None
    mae = None
    # Optional N-bar time-decay abort (spec §8.3): if set, a still-open
    # position is flattened at the open of the ``max_hold_bars``-th bar
    # after the entry bar. Absent metadata → no behaviour change.
    max_hold = signal.metadata.get("max_hold_bars")
    entry_pos = None
    pos = -1

    # Optional VWAP confluence gate: only take the breakout if it fills above
    # the session VWAP (institutional cost basis). Computed over the FULL
    # session frame (from the open), not just post-signal bars. Absent
    # metadata → vwap stays None → no behaviour change for other strategies.
    #
    # The VWAP is SHIFTED one bar so the gate at bar ``ts`` only sees the VWAP
    # through the previous completed bar. Including bar ts's own high/low/close
    # and volume would let the entry decision depend on information that only
    # prints once that bar closes (intrabar look-ahead). The first bar then has
    # NaN VWAP → no gate, consistent with the "no volume yet" case below.
    vwap = None
    if signal.metadata.get("require_above_vwap"):
        typ = (bars_5m["high"] + bars_5m["low"] + bars_5m["close"]) / 3.0
        cum_vol = bars_5m["volume"].cumsum()
        vwap = ((typ * bars_5m["volume"]).cumsum() / cum_vol.where(cum_vol > 0)).shift(1)

    for ts, bar in active.iterrows():
        pos += 1
        high = float(bar["high"])
        low = float(bar["low"])
        was_flat_at_open = entry_time is None
        if entry_time is None:
            if high < trigger:
                continue
            bar_open = float(bar["open"])
            if config.stop_limit_offset_dollars is not None:
                limit = trigger + config.stop_limit_offset_dollars
                if bar_open > limit and low > limit:
                    continue
                if bar_open > trigger:
                    if bar_open > limit:
                        fill_base = limit
                    else:
                        fill_base = bar_open
                else:
                    fill_base = trigger
            else:
                if bar_open > trigger:
                    fill_base = bar_open
                else:
                    fill_base = trigger

            prospective_entry = fill_base * (1 + config.entry_slippage_bps / 10_000)
            # VWAP gate: a breakout that triggers below the session VWAP is
            # buying into supply — reject the trade (strict: the first
            # breakout must clear VWAP). NaN VWAP (no volume yet) → no gate.
            if vwap is not None:
                v = vwap.get(ts)
                if v is not None and v == v and prospective_entry <= float(v):
                    break  # leave flat → falls through to NO_FILL

            entry_time = ts.to_pydatetime() if hasattr(ts, "to_pydatetime") else ts
            entry_price = prospective_entry
            entry_pos = pos
            # On the entry bar, part of the high/low range printed before
            # the fill — start MFE at 0 and only track MAE (conservative).
            mfe = 0.0
            mae = min(0.0, (low - entry_price) / entry_price * 100)
        elif entry_price is not None:
            # Time stop evaluates at the bar open (before intrabar action).
            if _time_stop_triggered(signal, entry_price, float(bar["open"]), ts):
                exit_price = float(bar["open"]) * (1 - config.exit_slippage_bps / 10_000)
                return _trade(signal, entry_time, entry_price, ts, exit_price,
                              "TIME_STOP", mfe, mae, config)
            # N-bar time-decay abort: exit at this bar's open once the
            # position has been held for ``max_hold`` bars without resolving.
            if max_hold and entry_pos is not None and (pos - entry_pos) >= int(max_hold):
                exit_price = float(bar["open"]) * (1 - config.exit_slippage_bps / 10_000)
                return _trade(signal, entry_time, entry_price, ts, exit_price,
                              "TIME_DECAY", mfe, mae, config)
            mfe = max(float(mfe or 0.0), (high - entry_price) / entry_price * 100)
            mae = min(float(mae or 0.0), (low - entry_price) / entry_price * 100)

        # Conservative same-bar ordering: if stop and target are both possible,
        # assume the stop was hit first. If the position was already held at
        # the bar open and the bar opened below the stop (gap through), the
        # stop order fills near the open, not at the stop price. On the
        # entry bar itself the open printed before the fill, so the stop
        # price stands.
        if low <= stop:
            exit_base = stop if was_flat_at_open else min(float(bar["open"]), stop)
            exit_price = exit_base * (1 - config.exit_slippage_bps / 10_000)
            if mae is not None:
                mae = min(mae, (exit_base - entry_price) / entry_price * 100)
            return _trade(signal, entry_time, entry_price, ts, exit_price, "STOP_LOSS", mfe, mae, config)
        if target is not None and high >= target:
            exit_price = target * (1 - config.exit_slippage_bps / 10_000)
            return _trade(signal, entry_time, entry_price, ts, exit_price, "TARGET", mfe, mae, config)

    if entry_time is None or entry_price is None:
        return SimulatedTrade(
            ticker=signal.ticker,
            setup_type=signal.setup_type,
            direction="long",
            entry_time=None,
            entry_price=None,
            exit_time=None,
            exit_price=None,
            exit_reason="NO_FILL",
            pnl_pct=0.0,
            gross_pnl_pct=0.0,
            realized_r=None,
            mfe_pct=None,
            mae_pct=None,
            fees_pct=0.0,
            slippage_pct=0.0,
            context={"signal": signal.metadata},
        )

    last = active.iloc[-1]
    exit_price = float(last["close"]) * (1 - config.exit_slippage_bps / 10_000)
    last_ts = active.index[-1]
    return _trade(signal, entry_time, entry_price, last_ts, exit_price, "TIME_EXIT", mfe, mae, config)


def simulate_short_breakout(
    bars_5m: pd.DataFrame,
    signal: Signal,
    cutoff: datetime,
    config: ExecutionConfig,
) -> SimulatedTrade | None:
    """Simulate a conservative short breakdown trade (mirror of the long).

    Sells when price trades down through ``entry_trigger``; stop above at
    ``stop_price`` (> trigger). Same conservatism as the long simulator:
    no same-bar setup fills, stop-first same-bar ordering, gap-through
    stops fill at the open.
    """
    if bars_5m is None or bars_5m.empty:
        return None

    trigger = signal.entry_trigger
    stop = signal.stop_price
    target = signal.target_price
    risk = stop - trigger
    if risk <= 0:
        return None

    active = bars_5m[(bars_5m.index > signal.signal_time) & (bars_5m.index <= cutoff)]
    if active.empty:
        return None

    entry_time = None
    entry_price = None
    mfe = None
    mae = None

    for ts, bar in active.iterrows():
        high = float(bar["high"])
        low = float(bar["low"])
        was_flat_at_open = entry_time is None
        if entry_time is None:
            if low > trigger:
                continue
            bar_open = float(bar["open"])
            if config.stop_limit_offset_dollars is not None:
                limit = trigger - config.stop_limit_offset_dollars
                if bar_open < limit and high < limit:
                    continue
                if bar_open < trigger:
                    fill_base = limit if bar_open < limit else bar_open
                else:
                    fill_base = trigger
            else:
                fill_base = bar_open if bar_open < trigger else trigger

            entry_time = ts.to_pydatetime() if hasattr(ts, "to_pydatetime") else ts
            entry_price = fill_base * (1 - config.entry_slippage_bps / 10_000)
            mfe = 0.0
            mae = min(0.0, (entry_price - high) / entry_price * 100)
        elif entry_price is not None:
            if _time_stop_triggered(signal, entry_price, float(bar["open"]), ts,
                                    direction="short"):
                exit_price = float(bar["open"]) * (1 + config.exit_slippage_bps / 10_000)
                return _trade(signal, entry_time, entry_price, ts, exit_price,
                              "TIME_STOP", mfe, mae, config, direction="short")
            mfe = max(float(mfe or 0.0), (entry_price - low) / entry_price * 100)
            mae = min(float(mae or 0.0), (entry_price - high) / entry_price * 100)

        if high >= stop:
            exit_base = stop if was_flat_at_open else max(float(bar["open"]), stop)
            exit_price = exit_base * (1 + config.exit_slippage_bps / 10_000)
            if mae is not None:
                mae = min(mae, (entry_price - exit_base) / entry_price * 100)
            return _trade(signal, entry_time, entry_price, ts, exit_price,
                          "STOP_LOSS", mfe, mae, config, direction="short")
        if target is not None and low <= target:
            exit_price = target * (1 + config.exit_slippage_bps / 10_000)
            return _trade(signal, entry_time, entry_price, ts, exit_price,
                          "TARGET", mfe, mae, config, direction="short")

    if entry_time is None or entry_price is None:
        return SimulatedTrade(
            ticker=signal.ticker,
            setup_type=signal.setup_type,
            direction="short",
            entry_time=None,
            entry_price=None,
            exit_time=None,
            exit_price=None,
            exit_reason="NO_FILL",
            pnl_pct=0.0,
            gross_pnl_pct=0.0,
            realized_r=None,
            mfe_pct=None,
            mae_pct=None,
            fees_pct=0.0,
            slippage_pct=0.0,
            context={"signal": signal.metadata},
        )

    last = active.iloc[-1]
    exit_price = float(last["close"]) * (1 + config.exit_slippage_bps / 10_000)
    last_ts = active.index[-1]
    return _trade(signal, entry_time, entry_price, last_ts, exit_price,
                  "TIME_EXIT", mfe, mae, config, direction="short")


def simulate_pullback_limit_long(
    bars: pd.DataFrame,
    signal: Signal,
    cutoff: datetime,
    config: ExecutionConfig,
) -> SimulatedTrade | None:
    """Simulate a passive pullback limit entry after an opening-range breach.

    Mechanics (Phase v2):
      - Watch for the first bar whose high trades above ``signal.entry_trigger``.
      - From the NEXT bar (order-latency conservative), a buy limit at
        ``signal.metadata['pullback_limit']`` is working for
        ``signal.metadata['pullback_ttl_min']`` minutes after the breach bar.
      - Strict through-the-limit fill: the bar low must trade strictly below
        the limit price; a touch (low == limit) does not fill.
      - If a bar collapses through the stop while the order is working, the
        fill is assumed at the limit with an immediate stop-out on that bar.
      - After the fill: stop-loss or time exit at ``cutoff`` close.
      - Maker entry: no entry slippage is applied; exits remain taker.

    Works on any bar resolution; 1-minute bars are strongly preferred for
    fill fidelity.
    """
    if bars is None or bars.empty:
        return None

    trigger = signal.entry_trigger
    stop = signal.stop_price
    limit = float(signal.metadata.get("pullback_limit", trigger))
    ttl_min = float(signal.metadata.get("pullback_ttl_min", 30))
    risk = trigger - stop
    if risk <= 0 or limit <= stop:
        return None

    active = bars[(bars.index > signal.signal_time) & (bars.index <= cutoff)]
    if active.empty:
        return None

    maker_config = ExecutionConfig(
        entry_slippage_bps=0.0,
        exit_slippage_bps=config.exit_slippage_bps,
        fees_bps_per_side=config.fees_bps_per_side,
        stop_limit_offset_dollars=config.stop_limit_offset_dollars,
    )

    breach_ts = None
    entry_time = None
    entry_price = None
    mfe = None
    mae = None

    for ts, bar in active.iterrows():
        high = float(bar["high"])
        low = float(bar["low"])
        bar_open = float(bar["open"])

        if breach_ts is None:
            if high > trigger:
                breach_ts = ts
            continue

        if entry_time is None:
            elapsed_min = (ts - breach_ts).total_seconds() / 60.0
            if elapsed_min > ttl_min:
                break  # order expired unfilled
            if low <= stop:
                # Collapse through the stop: conservative fill at the limit
                # with an immediate stop-out on the same bar. If the bar
                # OPENED at/below the stop (gap down through both levels),
                # the limit fills at the open and the stop exits at/below
                # the open — exiting at the stop price would book a phantom
                # profit on a catastrophic adverse gap.
                entry_time = ts.to_pydatetime() if hasattr(ts, "to_pydatetime") else ts
                entry_price = min(limit, bar_open)
                exit_base = min(bar_open, stop)
                exit_price = exit_base * (1 - config.exit_slippage_bps / 10_000)
                mae = (exit_base - entry_price) / entry_price * 100
                return _trade(signal, entry_time, entry_price, ts, exit_price, "STOP_LOSS", 0.0, mae, maker_config)
            if low < limit:
                entry_time = ts.to_pydatetime() if hasattr(ts, "to_pydatetime") else ts
                entry_price = min(limit, bar_open)
                mfe = (high - entry_price) / entry_price * 100
                mae = (low - entry_price) / entry_price * 100
            continue

        mfe = max(float(mfe or 0.0), (high - entry_price) / entry_price * 100)
        mae = min(float(mae or 0.0), (low - entry_price) / entry_price * 100)
        if low <= stop:
            # gap-through guard: a bar opening below the stop exits near
            # the open, not at the stop price
            exit_base = min(float(bar["open"]), stop)
            exit_price = exit_base * (1 - config.exit_slippage_bps / 10_000)
            return _trade(signal, entry_time, entry_price, ts, exit_price, "STOP_LOSS", mfe, mae, maker_config)

    if entry_time is None or entry_price is None:
        return SimulatedTrade(
            ticker=signal.ticker,
            setup_type=signal.setup_type,
            direction="long",
            entry_time=None,
            entry_price=None,
            exit_time=None,
            exit_price=None,
            exit_reason="NO_FILL",
            pnl_pct=0.0,
            gross_pnl_pct=0.0,
            realized_r=None,
            mfe_pct=None,
            mae_pct=None,
            fees_pct=0.0,
            slippage_pct=0.0,
            context={"signal": signal.metadata, "breached": breach_ts is not None},
        )

    last = active.iloc[-1]
    exit_price = float(last["close"]) * (1 - config.exit_slippage_bps / 10_000)
    last_ts = active.index[-1]
    return _trade(signal, entry_time, entry_price, last_ts, exit_price, "TIME_EXIT", mfe, mae, maker_config)


def _trade(
    signal: Signal,
    entry_time,
    entry_price: float,
    exit_time,
    exit_price: float,
    exit_reason: str,
    mfe: float | None,
    mae: float | None,
    config: ExecutionConfig,
    direction: str = "long",
) -> SimulatedTrade:
    sign = -1.0 if direction == "short" else 1.0
    gross = sign * (exit_price - entry_price) / entry_price * 100.0
    fees = config.fees_bps_per_side * 2 / 100.0
    slippage = (config.entry_slippage_bps + config.exit_slippage_bps) / 100.0
    pnl = gross - fees
    # R is measured against the *planned* risk (trigger − stop), not the
    # risk actually taken: pullback entries fill below the trigger and
    # breakout entries can fill above it. Position sizing is done on the
    # planned risk, so per-trade R stays comparable across entry styles.
    realized_r = sign * (exit_price - entry_price) / abs(signal.entry_trigger - signal.stop_price)
    return SimulatedTrade(
        ticker=signal.ticker,
        setup_type=signal.setup_type,
        direction=direction,
        entry_time=entry_time,
        entry_price=entry_price,
        exit_time=exit_time.to_pydatetime() if hasattr(exit_time, "to_pydatetime") else exit_time,
        exit_price=exit_price,
        exit_reason=exit_reason,
        pnl_pct=pnl,
        gross_pnl_pct=gross,
        realized_r=realized_r,
        mfe_pct=mfe,
        mae_pct=mae,
        fees_pct=fees,
        slippage_pct=slippage,
        context={"signal": signal.metadata},
    )


def simulate_daily_hold(
    daily_bars: pd.DataFrame,
    signal: Signal,
    entry_date,
    hold_days: int,
    config: ExecutionConfig,
    use_close_stop: bool = False,
    direction: str = "long",
) -> SimulatedTrade | None:
    """Simulate a multi-day SWING hold on DAILY bars (the additive path for
    cross-session strategies; the intraday ``simulate_long_breakout`` is unchanged).

    Enter at the close of ``entry_date`` and exit at the close ``hold_days`` trading
    days later (a pure time exit), or earlier if ``use_close_stop`` and a daily close
    breaches ``signal.stop_price``. Slippage is BAKED into the fill prices (long: pay
    up on entry, receive less on exit), consistent with the intraday simulator, so
    ``gross_pnl_pct`` is already net of slippage. ``daily_bars`` must be a date-indexed
    frame with a ``close`` column (``high``/``low`` optional, used for MFE/MAE) and
    must extend at least ``hold_days`` rows past ``entry_date``. Returns ``None`` if
    the entry date isn't present or there aren't enough forward bars.
    """
    if daily_bars is None or daily_bars.empty:
        return None
    idx = pd.DatetimeIndex(daily_bars.index).normalize()
    bars = daily_bars.copy()
    bars.index = idx
    ed = pd.Timestamp(entry_date).normalize()
    if ed not in idx:
        return None
    i = idx.get_loc(ed)
    if not isinstance(i, (int, np.integer)):  # non-unique index → slice/array; bail safely
        return None
    i = int(i)
    if i + hold_days >= len(bars):
        return None

    closes = bars["close"].astype(float).values
    highs = bars["high"].astype(float).values if "high" in bars.columns else closes
    lows = bars["low"].astype(float).values if "low" in bars.columns else closes

    entry_raw = closes[i]
    if not (entry_raw > 0):
        return None
    sign = -1.0 if direction == "short" else 1.0
    entry_slip = config.entry_slippage_bps / 10000.0
    exit_slip = config.exit_slippage_bps / 10000.0
    entry_price = entry_raw * (1.0 + sign * entry_slip)   # long pays up

    exit_j = i + hold_days
    reason = "TIME_EXIT"
    if use_close_stop and signal.stop_price:
        for j in range(i + 1, i + hold_days + 1):
            breached = closes[j] <= signal.stop_price if direction == "long" else closes[j] >= signal.stop_price
            if breached:
                exit_j, reason = j, "STOP_CLOSE"
                break

    exit_raw = closes[exit_j]
    exit_price = exit_raw * (1.0 - sign * exit_slip)       # long receives less

    hi = float(highs[i + 1:exit_j + 1].max()) if exit_j > i else entry_raw
    lo = float(lows[i + 1:exit_j + 1].min()) if exit_j > i else entry_raw
    mfe = sign * (hi - entry_price) / entry_price * 100.0 if direction == "long" else sign * (entry_price - lo) / entry_price * 100.0
    mae = sign * (lo - entry_price) / entry_price * 100.0 if direction == "long" else sign * (entry_price - hi) / entry_price * 100.0

    entry_ts = idx[i].to_pydatetime()
    exit_ts = idx[exit_j].to_pydatetime()
    return _trade(signal, entry_ts, entry_price, exit_ts, exit_price, reason, mfe, mae,
                  config, direction=direction)
