"""Equity-snapshot chart + position current-value (web detail page)."""
from datetime import date

from trading.live import ledger
from trading.live.broker import FakeBroker, Position
from trading.live.engine import refresh_market_state


def _seed_position(env, pf="pf", ticker="AAA", qty=10.0, price=100.0):
    ledger.init_db(env)
    coid = "co_seed"
    ledger.record_intent(coid, run_id="r1", portfolio_id=pf, ticker=ticker, side="buy",
                         qty=qty, env=env)
    ledger.record_fill(coid, portfolio_id=pf, ticker=ticker, side="buy", qty=qty,
                       price=price, env=env)


def test_update_position_prices_and_value(env):
    _seed_position(env, qty=10.0, price=100.0)
    n = ledger.update_position_prices("pf", {"AAA": 110.0}, env=env)
    assert n == 1
    pos = ledger.get_positions("pf", env=env)["AAA"]
    assert pos["last_price"] == 110.0 and pos["last_price_at"] is not None
    # value/unrealized math (mirrors _positions_view): 10*110 = 1100, cost 1000 → +100 / +10%
    value = pos["qty"] * pos["last_price"]
    upnl = value - pos["qty"] * pos["avg_entry_price"]
    assert value == 1100.0 and upnl == 100.0


def test_update_position_prices_ignores_unknown_and_nonpositive(env):
    _seed_position(env)
    assert ledger.update_position_prices("pf", {"ZZZ": 50.0}, env=env) == 0   # not held
    assert ledger.update_position_prices("pf", {"AAA": 0.0}, env=env) == 0     # bad price
    assert ledger.get_positions("pf", env=env)["AAA"]["last_price"] is None


def test_equity_snapshot_series_ordered_and_idempotent(env):
    ledger.init_db(env)
    ledger.record_equity_snapshot("pf", equity=1000.0, source="manual", ts="2026-06-22T10:00:00",
                                  env=env)
    ledger.record_equity_snapshot("pf", equity=1010.0, source="manual", ts="2026-06-23T10:00:00",
                                  env=env)
    ledger.record_equity_snapshot("pf", equity=999.0, source="dup", ts="2026-06-22T10:00:00",
                                  env=env)   # same ts → ignored
    series = ledger.equity_series("pf", env=env)
    assert [r["equity"] for r in series] == [1000.0, 1010.0]   # oldest→newest, dedup'd


def test_refresh_market_state_writes_prices_and_snapshot(env):
    _seed_position(env, qty=10.0, price=100.0)
    broker = FakeBroker(equity=1100.0,
                        positions={"AAA": Position("AAA", 10.0, 100.0, 110.0, "2026-06-01")})
    rep = refresh_market_state("pf", broker, source="manual", env=env)
    assert rep["prices_updated"] == 1
    assert rep["positions_value"] == 1100.0 and rep["equity"] == 1100.0
    assert ledger.get_positions("pf", env=env)["AAA"]["last_price"] == 110.0
    assert ledger.equity_series("pf", env=env)[-1]["equity"] == 1100.0


def test_refresh_backfills_hourly_equity_history(env):
    _seed_position(env, qty=10.0, price=100.0)
    # three hourly broker NAV points (unix seconds, one hour apart)
    base = 1_782_220_000
    hist = [(base, 1000.0), (base + 3600, 1050.0), (base + 7200, 1100.0)]
    broker = FakeBroker(equity=1100.0,
                        positions={"AAA": Position("AAA", 10.0, 100.0, 110.0, "2026-06-01")},
                        equity_history=hist)
    rep = refresh_market_state("pf", broker, source="manual", env=env)
    assert rep["history_points"] == 3
    series = ledger.equity_series("pf", env=env)
    eqs = [r["equity"] for r in series]
    # the 3 hourly points are present and chronologically ordered
    assert 1000.0 in eqs and 1050.0 in eqs and 1100.0 in eqs
    assert eqs == sorted(eqs) or series == sorted(series, key=lambda r: r["ts"])
    # a second refresh is idempotent on the hourly timestamps (no duplicate rows)
    before = len(series)
    refresh_market_state("pf", broker, source="manual", env=env)
    assert len(ledger.equity_series("pf", env=env)) <= before + 1   # at most the new 'now' pt


def test_load_env_file_parses_exports(tmp_path):
    from trading.live.secrets import load_env_file, ensure_broker_env
    f = tmp_path / "alpaca.env"
    f.write_text('# creds\nexport ALPACA_API_KEY_ID="PKABC"\nALPACA_SECRET_KEY=secret123\n\n')
    vals = load_env_file(f)
    assert vals["ALPACA_API_KEY_ID"] == "PKABC" and vals["ALPACA_SECRET_KEY"] == "secret123"
    assert load_env_file(tmp_path / "missing.env") == {}


def test_ensure_broker_env_loads_when_absent(tmp_path, monkeypatch):
    from trading.live.secrets import ensure_broker_env
    monkeypatch.delenv("ALPACA_API_KEY_ID", raising=False)
    monkeypatch.delenv("ALPACA_SECRET_KEY", raising=False)
    (tmp_path / "alpaca.env").write_text(
        'export ALPACA_API_KEY_ID="PKX"\nexport ALPACA_SECRET_KEY="sx"\n')
    assert ensure_broker_env(tmp_path) is True
    import os
    assert os.environ["ALPACA_API_KEY_ID"] == "PKX"


def test_compute_performance_today_matches_broker_today():
    """Today = live equity / last_equity - 1 (the broker app's number), not the last
    completed session. Catches the off-by-one-day bug."""
    from trading.live.engine import compute_performance
    import datetime as dt
    base = 1_782_000_000
    # completed daily closes; last completed close (last_equity) = 1020. Live equity = 1010.
    daily_eq = [(base, 980.0), (base + 86400, 1000.0), (base + 2 * 86400, 1020.0)]
    d0 = dt.datetime.fromtimestamp(base, tz=dt.timezone.utc).date()
    spy = [(d0, 400.0), (d0 + dt.timedelta(days=1), 404.0), (d0 + dt.timedelta(days=2), 408.0)]
    out = compute_performance(1010.0, 1020.0, 1000.0, daily_eq, spy,
                              spy_now=410.0, spy_prior=408.0)
    assert round(out["port_daily_pct"], 2) == round((1010.0 / 1020.0 - 1) * 100, 2)  # live, not 1020/1000
    assert round(out["port_total_pct"], 2) == 1.0           # 1010/1000-1
    assert round(out["spy_daily_pct"], 2) == round((410.0 / 408.0 - 1) * 100, 2)     # live SPY vs prior close
    assert round(out["spy_total_pct"], 2) == round((410.0 / 400.0 - 1) * 100, 2)     # live vs inception


def test_compute_performance_30d_window():
    from trading.live.engine import compute_performance
    import datetime as dt
    base = 1_782_000_000
    daily_eq = [(base + i * 86400, 1000.0 + i * 10) for i in range(30)]  # 30 completed closes
    d0 = dt.datetime.fromtimestamp(base, tz=dt.timezone.utc).date()
    spy = [(d0 + dt.timedelta(days=i), 400.0 + i) for i in range(30)]
    out = compute_performance(1310.0, 1300.0, 1000.0, daily_eq, spy, spy_now=432.0, spy_prior=430.0)
    # 30-session anchor = series[-30] = first point: equity 1000 -> live 1310; spy 400 -> live 432
    assert round(out["port_30d_pct"], 2) == round((1310.0 / 1000.0 - 1) * 100, 2)
    assert round(out["spy_30d_pct"], 2) == round((432.0 / 400.0 - 1) * 100, 2)


def test_compute_performance_handles_missing():
    from trading.live.engine import compute_performance
    out = compute_performance(None, None, None, [], [])
    assert out == {"port_total_pct": None, "port_daily_pct": None, "port_30d_pct": None,
                   "spy_total_pct": None, "spy_daily_pct": None, "spy_30d_pct": None}


def test_performance_snapshot_record_and_latest(env):
    ledger.init_db(env)
    ledger.record_performance("pf", base_value=5000, port_total_pct=-1.6, port_daily_pct=0.4,
                              spy_total_pct=-0.8, spy_daily_pct=0.2, env=env)
    row = ledger.latest_performance("pf", env=env)
    assert row["port_total_pct"] == -1.6 and row["spy_daily_pct"] == 0.2
    assert ledger.latest_performance("none", env=env) is None


def test_compute_daily_breakdown_caps_at_inception():
    from trading.live.engine import compute_daily_breakdown
    import datetime as dt
    base = 1_782_000_000  # 3 daily NAV points => 2 day-return rows (capped at portfolio age)
    daily_eq = [(base, 1000.0), (base + 86400, 1010.0), (base + 2 * 86400, 1005.0)]
    d0 = dt.datetime.fromtimestamp(base, tz=dt.timezone.utc).date()
    spy = [(d0, 400.0), (d0 + dt.timedelta(days=1), 404.0), (d0 + dt.timedelta(days=2), 400.0)]
    rows = compute_daily_breakdown(daily_eq, spy)
    assert len(rows) == 2                                   # never more than portfolio duration
    assert rows[0]["date"] == (d0 + dt.timedelta(days=2)).isoformat()   # newest first
    assert round(rows[1]["port_pct"], 2) == 1.0            # 1010/1000-1
    assert round(rows[1]["spy_pct"], 2) == 1.0             # 404/400-1
    assert round(rows[1]["excess"], 2) == 0.0
    assert round(rows[0]["port_pct"], 2) == round((1005 / 1010 - 1) * 100, 2)


def test_compute_daily_breakdown_missing_spy_day():
    from trading.live.engine import compute_daily_breakdown
    import datetime as dt
    base = 1_782_000_000
    daily_eq = [(base, 1000.0), (base + 86400, 1020.0)]
    rows = compute_daily_breakdown(daily_eq, [])            # no SPY data
    assert len(rows) == 1 and rows[0]["spy_pct"] is None and rows[0]["excess"] is None
    assert round(rows[0]["port_pct"], 2) == 2.0


def test_equity_chart_points_regular_hourly_grid():
    from trading.live.web.app import _equity_chart_points
    # mix: regular hourly 'history' + ad-hoc 'web'/'manual' refresh points at odd minutes
    series = [
        {"ts": "2026-06-23T13:30:00+00:00", "equity": 100.0, "source": "history"},
        {"ts": "2026-06-23T14:30:00+00:00", "equity": 101.0, "source": "history"},
        {"ts": "2026-06-23T14:47:11+00:00", "equity": 101.5, "source": "web"},     # noise
        {"ts": "2026-06-23T15:30:00+00:00", "equity": 102.0, "source": "history"},
    ]
    pts = _equity_chart_points(series)
    times = [p["time"] for p in pts]
    # history-only, floored to the hour → exactly 3600s apart, ad-hoc point dropped
    assert len(pts) == 3
    assert times == sorted(times)
    assert all(times[i + 1] - times[i] == 3600 for i in range(len(times) - 1))
    assert all(t % 3600 == 0 for t in times)


def test_equity_chart_points_fallback_without_history():
    from trading.live.web.app import _equity_chart_points
    series = [{"ts": "2026-06-23T14:47:11+00:00", "equity": 100.0, "source": "web"},
              {"ts": "2026-06-23T15:10:00+00:00", "equity": 101.0, "source": "manual"}]
    pts = _equity_chart_points(series)        # no history → bucket what exists, hourly
    assert len(pts) == 2 and all(p["time"] % 3600 == 0 for p in pts)


def test_prepend_live_today_row():
    from trading.live.engine import prepend_live_today
    completed = [{"date": "2026-06-24", "port_pct": -3.32, "spy_pct": 0.3, "excess": -3.62}]
    # live session: equity 4855 vs last close 4910 -> ~-1.12%; spy 410 vs prior 408
    out = prepend_live_today(completed, equity=4855.0, last_equity=4910.0,
                             spy_now=410.0, spy_prior=408.0, date_iso="2026-06-25")
    assert len(out) == 2 and out[0]["live"] is True and out[0]["date"] == "2026-06-25"
    assert round(out[0]["port_pct"], 2) == round((4855.0 / 4910.0 - 1) * 100, 2)
    assert out[1]["date"] == "2026-06-24"                  # completed day still below


def test_prepend_live_today_skips_when_flat_or_duplicate():
    from trading.live.engine import prepend_live_today
    completed = [{"date": "2026-06-24", "port_pct": -3.32}]
    # flat (equity == last_equity) → no live row (weekend / no movement)
    assert prepend_live_today(completed, equity=4910.0, last_equity=4910.0,
                              spy_now=1, spy_prior=1, date_iso="2026-06-25") == completed
    # today already the newest completed row → no duplicate
    assert prepend_live_today(completed, equity=5000.0, last_equity=4910.0,
                              spy_now=1, spy_prior=1, date_iso="2026-06-24") == completed


def test_session_align_daily_shifts_alpaca_labels_back():
    """Alpaca daily bars at 00:00 UTC of day D hold session D-1's close → remap to the
    latest SPY trading day strictly before D (handles the Juneteenth holiday + weekend)."""
    import datetime as dt
    from trading.live.engine import _session_align_daily
    def u(d): return int(dt.datetime.combine(d, dt.time(), tzinfo=dt.timezone.utc).timestamp())
    # SPY calendar: 6/18 trades, 6/19 Juneteenth (no SPY), weekend, 6/22, 6/23, 6/24
    spy = [(dt.date(2026,6,18),1),(dt.date(2026,6,22),1),(dt.date(2026,6,23),1),(dt.date(2026,6,24),1)]
    daily = [(u(dt.date(2026,6,19)),5000.0),   # bar 6/19 → session 6/18 (funding)
             (u(dt.date(2026,6,23)),5078.5),    # bar 6/23 → session 6/22 (launch day)
             (u(dt.date(2026,6,24)),4909.91)]   # bar 6/24 → session 6/23
    out = _session_align_daily(daily, spy)
    got = [dt.datetime.fromtimestamp(ts, tz=dt.timezone.utc).date().isoformat() for ts,_ in out]
    assert got == ["2026-06-18", "2026-06-22", "2026-06-23"]
