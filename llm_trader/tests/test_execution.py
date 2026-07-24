"""Focused tests for the deterministic v3 OHLC execution contract."""

from __future__ import annotations

import json
from datetime import datetime

import pytest

from trading.llm_trader import recorder
from trading.llm_trader.execution import EXECUTION_MODEL, ExecutionConfig, ExecutionEngine


def _bar(i, o, h, l, c, v=10_000):
    return {"i": i, "time": f"10:{20 + i:02d}", "o": o, "h": h, "l": l, "c": c, "v": v}


def _config(**overrides):
    values = {
        "risk_budget": 100.0,
        "buying_power": 10_000.0,
        "entry_slippage_bps": 0.0,
        "exit_slippage_bps": 0.0,
        "commission_per_share": 0.0,
        "max_participation_rate": 1.0,
        "tick_size": 0.01,
    }
    values.update(overrides)
    return ExecutionConfig(**values)


def test_stop_gap_uses_open_and_can_exceed_planned_risk():
    engine = ExecutionEngine(_config())
    actions, _, pnl = engine.run(
        [_bar(0, 10, 10.2, 9.8, 10), _bar(1, 8, 8.5, 7.5, 8)],
        [{"i": 0, "time": "10:20", "action": "ENTER_CLOSE", "stop": 9.0}],
        force_close=False,
    )
    assert [(a["action"], a["price"], a["shares"]) for a in actions] == [
        ("ENTER", 10.0, 100), ("EXIT", 8.0, 100)
    ]
    assert pnl["initial_risk"] == 100.0
    assert pnl["realized_pnl"] == -200.0  # $2 gap through a planned $1 stop


def test_next_open_entry_never_fills_at_the_confirmation_close():
    engine = ExecutionEngine(_config())
    actions, _, pnl = engine.run(
        [
            _bar(0, 10.0, 10.4, 9.8, 10.3),
            _bar(1, 10.6, 10.8, 10.4, 10.7),
        ],
        [{"i": 0, "time": "10:20", "action": "ENTER_NEXT_OPEN", "stop": 9.8}],
        force_close=False,
    )
    assert [(a["action"], a["i"], a["price"]) for a in actions] == [("ENTER", 1, 10.6)]
    assert pnl["entry_index"] == 1
    assert pnl["entry_avg"] == 10.6


def test_next_open_entry_cancels_if_open_is_at_or_below_structural_stop():
    engine = ExecutionEngine(_config())
    actions, _, pnl = engine.run(
        [_bar(0, 10.0, 10.4, 9.8, 10.3), _bar(1, 9.7, 10.0, 9.5, 9.8)],
        [{"i": 0, "time": "10:20", "action": "ENTER_NEXT_OPEN", "stop": 9.8}],
        force_close=False,
    )
    assert actions == []
    assert pnl["traded"] is False
    assert engine.order_events == [{
        "i": 1,
        "action": "CANCEL_ENTRY",
        "reason": "next-open entry opened at or below its protective stop",
    }]


def test_armed_entry_and_stop_same_bar_use_adverse_path():
    engine = ExecutionEngine(_config())
    actions, _, pnl = engine.run(
        [_bar(0, 9.5, 9.8, 9.3, 9.6), _bar(1, 9.5, 10.5, 8.0, 9.2)],
        [{"i": 0, "time": "10:20", "action": "ARM_BUY_STOP", "trigger": 10.0, "stop": 9.0}],
        force_close=False,
    )
    assert [(a["action"], a["price"], a["shares"]) for a in actions] == [
        ("ENTER", 10.0, 100), ("EXIT", 9.0, 100)
    ]
    assert pnl["realized_pnl"] == -100.0


def test_armed_entry_gap_guard_cancels_before_a_chased_fill():
    engine = ExecutionEngine(_config())
    actions, _, pnl = engine.run(
        [_bar(0, 9.5, 9.8, 9.3, 9.6), _bar(1, 10.8, 11.2, 10.7, 11.0)],
        [{
            "i": 0, "time": "10:20", "action": "ARM_BUY_STOP",
            "trigger": 10.0, "stop": 9.0, "atr": 1.0,
            "max_entry_gap_atr": 0.5,
        }],
        force_close=False,
    )
    assert actions == []
    assert pnl["traded"] is False
    assert engine.order_events == [{
        "i": 1,
        "action": "CANCEL_ENTRY",
        "reason": "entry gap $0.8000 exceeded 0.50×ATR",
    }]


def test_armed_entry_expiry_cancels_before_a_late_breakout():
    engine = ExecutionEngine(_config())
    actions, _, pnl = engine.run(
        [
            _bar(0, 9.5, 9.8, 9.3, 9.6),
            _bar(1, 9.6, 9.9, 9.4, 9.7),
            _bar(2, 9.7, 9.95, 9.5, 9.8),
            # The order was eligible on bars 1 and 2.  It must expire before
            # evaluating this late trigger on the third later bar.
            _bar(3, 9.9, 10.4, 9.8, 10.2),
        ],
        [{
            "i": 0, "time": "10:20", "action": "ARM_BUY_STOP",
            "trigger": 10.0, "stop": 9.0, "expiry_bars": 2,
        }],
        force_close=False,
    )
    assert actions == []
    assert pnl["traded"] is False
    assert engine.order_events == [{
        "i": 3,
        "action": "CANCEL_ENTRY",
        "reason": "armed entry expired after 2 bar(s)",
    }]


def test_stop_wins_when_ohlc_hits_target_and_stop():
    engine = ExecutionEngine(_config())
    actions, _, _ = engine.run(
        [
            _bar(0, 10, 10.2, 9.8, 10),
            _bar(1, 10, 10.5, 9.5, 10),
            _bar(2, 10, 12, 8, 9),
        ],
        [
            {"i": 0, "time": "10:20", "action": "ENTER_CLOSE", "stop": 9.0},
            {"i": 1, "time": "10:21", "action": "SCALE_LIMIT", "target": 11.0, "fraction": 0.5},
        ],
        force_close=False,
    )
    assert [a["action"] for a in actions] == ["ENTER", "EXIT"]
    assert actions[-1]["price"] == 9.0


def test_entry_bracket_derives_fixed_r_targets_from_actual_fill():
    engine = ExecutionEngine(_config())
    actions, _, _ = engine.run(
        [
            _bar(0, 10, 10.2, 9.8, 10),
            _bar(1, 10, 10.8, 9.7, 10.5),
            _bar(2, 10.5, 11.1, 10.2, 11.0),
            _bar(3, 11.0, 12.1, 10.8, 12.0),
        ],
        [{
            "i": 0, "time": "10:20", "action": "ENTER_CLOSE", "stop": 9.0,
            "bracket": {"scales": [
                {"r_multiple": 1.0, "fraction": 0.333},
                {"r_multiple": 2.0, "fraction": 0.333},
            ]},
        }],
        force_close=False,
    )
    assert [(a["action"], a["price"], a["shares"]) for a in actions] == [
        ("ENTER", 10.0, 100), ("SCALE", 11.0, 33), ("SCALE", 12.0, 33),
    ]
    assert "+1.00R" in actions[1]["reason"]
    assert "+2.00R" in actions[2]["reason"]


def test_entry_bracket_never_retroactively_fills_or_beats_stop_first():
    engine = ExecutionEngine(_config())
    actions, _, _ = engine.run(
        [
            _bar(0, 10, 10.2, 9.8, 10),
            # The +1R target is touched only after the entry, so the next bar
            # is eligible; its stop touch remains the adverse OHLC outcome.
            _bar(1, 10, 11.2, 8.5, 9.0),
        ],
        [{
            "i": 0, "time": "10:20", "action": "ENTER_CLOSE", "stop": 9.0,
            "bracket": {"scales": [{"r_multiple": 1.0, "fraction": 0.333}]},
        }],
        force_close=False,
    )
    assert [(a["action"], a["price"], a["shares"]) for a in actions] == [
        ("ENTER", 10.0, 100), ("EXIT", 9.0, 100),
    ]


def test_armed_entry_bracket_waits_until_the_bar_after_its_fill():
    engine = ExecutionEngine(_config())
    actions, _, _ = engine.run(
        [
            _bar(0, 9.5, 9.8, 9.3, 9.6),
            # This bar triggers the entry and touches +1R, but an entry-attached
            # bracket is deliberately ineligible until the following bar.
            _bar(1, 9.8, 11.2, 9.5, 10.7),
            _bar(2, 10.7, 11.2, 10.4, 11.0),
        ],
        [{
            "i": 0, "time": "10:20", "action": "ARM_BUY_STOP", "trigger": 10.0, "stop": 9.0,
            "bracket": {"scales": [{"r_multiple": 1.0, "fraction": 0.5}]},
        }],
        force_close=False,
    )
    assert [(a["action"], a["i"], a["shares"]) for a in actions] == [
        ("ENTER", 1, 100), ("SCALE", 2, 50),
    ]


def test_armed_scanner_targets_are_fixed_from_the_actual_entry_fill():
    engine = ExecutionEngine(_config())
    actions, _, _ = engine.run(
        [
            _bar(0, 9.5, 9.8, 9.3, 9.6),
            _bar(1, 9.8, 10.2, 9.7, 10.0),  # entry; targets are not eligible yet
            _bar(2, 10.2, 11.2, 10.1, 11.0),  # T1
            _bar(3, 11.0, 12.2, 10.8, 12.0),  # T2 remainder
        ],
        [{
            "i": 0, "time": "10:20", "action": "ARM_BUY_STOP", "trigger": 10.0,
            "stop": 9.0, "engine_targets": {"target1": 11.0, "target2": 12.0},
        }],
        force_close=False,
    )
    assert [(a["action"], a["i"], a["price"], a["shares"]) for a in actions] == [
        ("ENTER", 1, 10.0, 100), ("SCALE", 2, 11.0, 50), ("SCALE", 3, 12.0, 50),
    ]
    assert engine.stop == 10.0
    assert engine.order_events == [{
        "i": 2,
        "action": "SET_STOP",
        "reason": "engine moved stop to breakeven after scanner target1",
    }]


def test_engine_rejects_an_agent_scale_when_scanner_targets_are_active():
    engine = ExecutionEngine(_config())
    with pytest.raises(ValueError, match="engine-owned scanner targets"):
        engine.run(
            [_bar(0, 9.5, 9.8, 9.3, 9.6), _bar(1, 9.8, 10.2, 9.7, 10.0)],
            [
                {"i": 0, "time": "10:20", "action": "ARM_BUY_STOP", "trigger": 10.0,
                 "stop": 9.0, "engine_targets": {"target1": 11.0, "target2": 12.0}},
                {"i": 1, "time": "10:21", "action": "SCALE_LIMIT", "target": 11.0,
                 "fraction": 0.5},
            ],
            force_close=False,
        )


def test_scanner_target_already_reached_by_entry_gap_cancels_without_filling():
    engine = ExecutionEngine(_config())
    actions, _, pnl = engine.run(
        [_bar(0, 9.5, 9.8, 9.3, 9.6), _bar(1, 10.2, 10.4, 10.1, 10.3)],
        [{
            "i": 0, "time": "10:20", "action": "ARM_BUY_STOP", "trigger": 10.0,
            "stop": 9.0, "engine_targets": {"target1": 10.1, "target2": 11.0},
        }],
        force_close=False,
    )
    assert actions == []
    assert pnl["traded"] is False
    assert engine.order_events == [{
        "i": 1,
        "action": "CANCEL_ENTRY",
        "reason": "entry price reached scanner target1 before fill",
    }]


def test_armed_trigger_with_zero_resolved_size_records_an_explicit_cancel():
    # Buying power below one share's price forces a zero-share fill on a real
    # trigger touch. The arm must clear with a traceable order event (not vanish
    # as if it were never triggered) and leave no phantom stop behind.
    engine = ExecutionEngine(_config(buying_power=5.0))
    actions, _, pnl = engine.run(
        [_bar(0, 9.5, 9.8, 9.3, 9.6), _bar(1, 10.0, 10.4, 9.9, 10.2)],
        [{"i": 0, "time": "10:20", "action": "ARM_BUY_STOP", "trigger": 10.0, "stop": 9.0}],
        force_close=False,
    )
    assert actions == []
    assert pnl["traded"] is False
    assert engine.armed is None
    assert engine.stop is None
    assert engine.order_events == [{
        "i": 1,
        "action": "CANCEL_ENTRY",
        "reason": "armed trigger reached but resolved order size was zero "
                  "(capacity/buying-power/stop-distance)",
    }]


def test_scanner_ladder_with_a_single_share_places_only_the_t2_tranche():
    # A one-share position cannot be split half/half, so the engine stages only
    # the T2 tranche and never moves the stop to breakeven (there is no T1 leg).
    engine = ExecutionEngine(_config(risk_budget=1.0))
    actions, _, _ = engine.run(
        [
            _bar(0, 9.5, 9.8, 9.3, 9.6),
            _bar(1, 9.8, 10.2, 9.7, 10.0),    # entry: 1 share
            _bar(2, 10.2, 11.2, 10.1, 11.0),  # T1 price reached, but no T1 tranche exists
            _bar(3, 11.0, 12.2, 10.8, 12.0),  # T2
        ],
        [{
            "i": 0, "time": "10:20", "action": "ARM_BUY_STOP", "trigger": 10.0,
            "stop": 9.0, "engine_targets": {"target1": 11.0, "target2": 12.0},
        }],
        force_close=False,
    )
    assert [(a["action"], a["i"], a["shares"]) for a in actions] == [
        ("ENTER", 1, 1), ("SCALE", 3, 1),
    ]
    assert engine.order_events == []


def test_scanner_ladder_splits_odd_totals_floor_then_remainder():
    engine = ExecutionEngine(_config(risk_budget=101.0))
    actions, _, _ = engine.run(
        [
            _bar(0, 9.5, 9.8, 9.3, 9.6),
            _bar(1, 9.8, 10.2, 9.7, 10.0),    # entry: 101 shares
            _bar(2, 10.2, 11.2, 10.1, 11.0),  # T1: 101 // 2 = 50
            _bar(3, 11.0, 12.2, 10.8, 12.0),  # T2 remainder: 51
        ],
        [{
            "i": 0, "time": "10:20", "action": "ARM_BUY_STOP", "trigger": 10.0,
            "stop": 9.0, "engine_targets": {"target1": 11.0, "target2": 12.0},
        }],
        force_close=False,
    )
    assert [(a["action"], a["i"], a["shares"]) for a in actions] == [
        ("ENTER", 1, 101), ("SCALE", 2, 50), ("SCALE", 3, 51),
    ]
    assert engine.stop == 10.0  # breakeven after the complete T1 tranche


def test_partial_t1_fill_defers_breakeven_until_the_full_tranche_completes():
    # The participation cap makes the 50-share T1 tranche fill across two bars.
    # The stop must move to breakeven only once the whole tranche is done.
    engine = ExecutionEngine(_config())  # risk_budget 100 → 100 shares
    actions, _, _ = engine.run(
        [
            _bar(0, 9.5, 9.8, 9.3, 9.6, v=10_000),
            _bar(1, 9.8, 10.2, 9.7, 10.0, v=10_000),  # entry: 100
            _bar(2, 10.2, 11.2, 10.1, 11.0, v=30),    # T1 partial: 30 of 50
            _bar(3, 11.0, 11.4, 10.8, 11.2, v=30),    # T1 completes: 20 → breakeven
        ],
        [{
            "i": 0, "time": "10:20", "action": "ARM_BUY_STOP", "trigger": 10.0,
            "stop": 9.0, "engine_targets": {"target1": 11.0, "target2": 12.0},
        }],
        force_close=False,
    )
    assert [(a["action"], a["i"], a["shares"]) for a in actions] == [
        ("ENTER", 1, 100), ("SCALE", 2, 30), ("SCALE", 3, 20),
    ]
    assert engine.order_events == [{
        "i": 3, "action": "SET_STOP",
        "reason": "engine moved stop to breakeven after scanner target1",
    }]
    assert engine.stop == 10.0


def test_engine_pyramid_uses_starter_then_adds_only_after_strength_with_risk_cap():
    engine = ExecutionEngine(_config())
    bars = [
        _bar(0, 10, 10.2, 9.8, 10),
        _bar(1, 10, 10.6, 9.9, 10.5),
        _bar(2, 11, 11.4, 10.8, 11.2),
        _bar(3, 12, 12.4, 11.8, 12.2),
    ]
    bars[2].update({"new_high": True, "rvol_bar": None, "macd_hist": 0.1})
    actions, _, _ = engine.run(
        bars,
        [{
            "i": 0, "time": "10:20", "action": "ENTER_CLOSE", "stop": 9.0,
            "pyramid": {"starter_fraction": 0.333, "max_adds": 2},
        }],
        force_close=False,
    )
    assert [(a["action"], a["i"], a["shares"], a["price"]) for a in actions] == [
        ("ENTER", 0, 33, 10.0), ("ADD", 2, 33, 11.0), ("ADD", 3, 33, 12.0),
    ]
    assert engine.shares == 99
    assert engine.stop == 9.99
    assert engine._open_risk() <= 100.0
    assert engine.snapshot(3)["pyramid"]["stage"] == 2


def test_engine_pyramid_cancels_a_queued_add_that_would_average_down():
    engine = ExecutionEngine(_config())
    actions, _, _ = engine.run(
        [
            _bar(0, 10, 10.2, 9.8, 10),
            _bar(1, 10, 10.6, 9.9, 10.5),  # queues add #1
            _bar(2, 9.5, 10.0, 9.2, 9.8),  # next open is below average entry
        ],
        [{
            "i": 0, "time": "10:20", "action": "ENTER_CLOSE", "stop": 9.0,
            "pyramid": {"starter_fraction": 0.333, "max_adds": 2},
        }],
        force_close=False,
    )
    assert [(a["action"], a["shares"]) for a in actions] == [("ENTER", 33)]
    assert engine.snapshot(2)["pyramid"]["queued"] is None


def test_sizing_enforces_buying_power_and_volume_cap():
    engine = ExecutionEngine(_config(buying_power=50.0, max_participation_rate=0.2))
    actions, _, pnl = engine.run(
        [_bar(0, 10, 10.2, 9.8, 10, v=50)],
        [{"i": 0, "time": "10:20", "action": "ENTER_CLOSE", "stop": 9.0}],
        force_close=False,
    )
    # Risk permits 100 shares; 20% of volume permits 10; $50 buying power permits 5.
    assert actions[0]["shares"] == 5
    assert pnl["initial_risk"] == 5.0


def _stream(path):
    lines = [
        {"type": "meta", "ticker": "TEST", "date": "2025-03-10", "entry_time": "10:20", "entry_px": 10.0},
        {"type": "tick", "i": 0, "time": "10:20", "o": 10.0, "h": 10.2, "l": 9.8, "c": 10.0, "v": 10_000},
        {"type": "tick", "i": 1, "time": "10:21", "o": 10.0, "h": 10.4, "l": 9.7, "c": 10.2, "v": 10_000},
        {"type": "end", "bars": 2, "close": 10.2},
    ]
    path.write_text("\n".join(json.dumps(x) for x in lines) + "\n")


def test_recorder_requires_revealed_intents_and_derives_fills(tmp_path):
    sdir = recorder.init("TEST", "2025-03-10", root=tmp_path, now=datetime(2026, 7, 10, 10, 0, 0))
    session_path = sdir / "session.json"
    session = json.loads(session_path.read_text())
    session["config"]["execution_model"] = EXECUTION_MODEL
    session["config"]["risk_budget"] = 100.0
    session["config"]["buying_power"] = 10_000.0
    session["config"]["execution"] = {
        "entry_slippage_bps": 0.0, "exit_slippage_bps": 0.0,
        "commission_per_share": 0.0, "max_participation_rate": 1.0,
    }
    session_path.write_text(json.dumps(session))
    _stream(sdir / "stream.jsonl")

    with pytest.raises(ValueError, match="derives fills"):
        recorder.log(sdir, {
            "i": 0, "time": "10:20", "action": "ENTER_CLOSE", "stop": 9.0,
            "fill_px": 10.0,
        })
    with pytest.raises(ValueError, match="does not match"):
        recorder.log(sdir, {"i": 0, "time": "10:21", "action": "ENTER_CLOSE", "stop": 9.0})

    assert recorder.resolve(sdir, 0)["position_shares"] == 0
    recorder.log(sdir, {"i": 0, "time": "10:20", "action": "ENTER_CLOSE", "stop": 9.0})
    resolved = recorder.resolve(sdir, 1)
    assert resolved["position_shares"] == 100
    assert resolved["avg_entry"] == 10.0

    finalized = recorder.finalize(sdir, full_day=False)
    assert finalized["result"]["execution_model"] == EXECUTION_MODEL
    actions = json.loads((sdir / "actions.json").read_text())
    assert [(a["side"], a["shares"]) for a in actions] == [("buy", 100), ("sell", 100)]


def test_recorder_enforces_causal_daily_arm_contract(tmp_path):
    sdir = recorder.init("TEST", "2025-03-10", root=tmp_path, now=datetime(2026, 7, 10, 10, 0, 0))
    session_path = sdir / "session.json"
    session = json.loads(session_path.read_text())
    session["config"]["execution_model"] = EXECUTION_MODEL
    session["skill"].update({
        "daily_enter_close_prohibited": True,
        "armed_entry_gap_guard_required": True,
        "armed_entry_expiry_required": True,
        "arm_on_scanner_plan_required": True,
    })
    session_path.write_text(json.dumps(session))
    _stream(sdir / "stream.jsonl")

    stream = [json.loads(line) for line in (sdir / "stream.jsonl").read_text().splitlines()]
    # A causal arm is valid only on its one, explicitly revealed setup bar.  Keep
    # this fixture structurally complete so the assertions below exercise the
    # decision-level contract rather than the stream-integrity preflight.
    stream[1]["is_setup_day"] = True
    stream[1]["scanner_plan"] = {
        "signal_as_of": "2025-03-10", "trigger": 10.1, "stop": 9.0,
        "target1": 11.0, "target2": 12.0, "atr": 1.0,
        "cup_depth_px": 2.0, "max_entry_gap_atr": 0.5,
        "arm_expiry_bars": 5,
    }
    (sdir / "stream.jsonl").write_text("\n".join(json.dumps(row) for row in stream) + "\n")

    with pytest.raises(ValueError, match="prohibits ENTER_CLOSE"):
        recorder.log(sdir, {"i": 0, "time": "10:20", "action": "ENTER_CLOSE", "stop": 9.0})
    with pytest.raises(ValueError, match="requires max_entry_gap_atr"):
        recorder.log(sdir, {
            "i": 0, "time": "10:20", "action": "ARM_BUY_STOP",
            "trigger": 10.1, "stop": 9.0,
        })
    with pytest.raises(ValueError, match="requires expiry_bars"):
        recorder.log(sdir, {
            "i": 0, "time": "10:20", "action": "ARM_BUY_STOP",
            "trigger": 10.1, "stop": 9.0, "atr": 1.0,
            "max_entry_gap_atr": 0.5,
        })
    with pytest.raises(ValueError, match="only on the revealed scanner plan bar"):
        recorder.log(sdir, {
            "i": 1, "time": "10:21", "action": "ARM_BUY_STOP",
            "trigger": 10.1, "stop": 9.0, "atr": 1.0,
            "max_entry_gap_atr": 0.5, "expiry_bars": 5,
        })
    with pytest.raises(ValueError, match="trigger must match"):
        recorder.log(sdir, {
            "i": 0, "time": "10:20", "action": "ARM_BUY_STOP",
            "trigger": 10.2, "stop": 9.0, "atr": 1.0,
            "max_entry_gap_atr": 0.5, "expiry_bars": 5,
        })

    recorder.log(sdir, {
        "i": 0, "time": "10:20", "action": "ARM_BUY_STOP",
        "trigger": 10.1, "stop": 9.0, "atr": 1.0,
        "max_entry_gap_atr": 0.5, "expiry_bars": 5,
    })


def test_recorder_locks_scanner_targets_and_rejects_agent_scales(tmp_path):
    sdir = recorder.init("TEST", "2025-03-10", root=tmp_path, now=datetime(2026, 7, 10, 10, 0, 0))
    session_path = sdir / "session.json"
    session = json.loads(session_path.read_text())
    session["config"]["execution_model"] = EXECUTION_MODEL
    session["skill"].update({
        "arm_on_scanner_plan_required": True,
        "scanner_plan_targets_engine_owned": True,
        "armed_entry_gap_guard_required": True,
        "armed_entry_expiry_required": True,
    })
    session_path.write_text(json.dumps(session))
    _stream(sdir / "stream.jsonl")
    stream = [json.loads(line) for line in (sdir / "stream.jsonl").read_text().splitlines()]
    stream[1]["is_setup_day"] = True
    stream[1]["scanner_plan"] = {
        "signal_as_of": "2025-03-10", "trigger": 10.1, "stop": 9.0,
        "target1": 11.0, "target2": 12.0, "atr": 1.0,
        "cup_depth_px": 2.0, "max_entry_gap_atr": 0.5, "arm_expiry_bars": 5,
    }
    (sdir / "stream.jsonl").write_text("\n".join(json.dumps(row) for row in stream) + "\n")

    recorder.log(sdir, {
        "i": 0, "time": "10:20", "action": "ARM_BUY_STOP", "trigger": 10.1,
        "stop": 9.0, "atr": 1.0, "max_entry_gap_atr": 0.5, "expiry_bars": 5,
    })
    decision = json.loads((sdir / "decisions.jsonl").read_text())
    assert decision["engine_targets"] == {"target1": 11.0, "target2": 12.0}
    with pytest.raises(ValueError, match="scanner targets are engine-owned"):
        recorder.log(sdir, {
            "i": 1, "time": "10:21", "action": "SCALE_LIMIT", "target": 11.0,
            "fraction": 0.5,
        })


def test_batch_integrity_revalidates_persisted_decisions_against_the_plan(tmp_path):
    # recorder.log enforces the causal-arm contract at write time, but a batch
    # agent has a writable staging dir. A decision appended directly to
    # decisions.jsonl (bypassing log) must still be caught at audit time.
    sdir = recorder.init("TEST", "2025-03-10", root=tmp_path, now=datetime(2026, 7, 10, 10, 0, 0))
    session_path = sdir / "session.json"
    session = json.loads(session_path.read_text())
    session["config"]["execution_model"] = EXECUTION_MODEL
    session["skill"].update({
        "arm_on_scanner_plan_required": True,
        "scanner_plan_targets_engine_owned": True,
        "armed_entry_gap_guard_required": True,
        "armed_entry_expiry_required": True,
        "daily_enter_close_prohibited": True,
        "horizon": "multi_day",
        "bar_resolution": "1day",
    })
    session["config"]["horizon"] = "multi_day"
    session["config"]["bar_resolution"] = "1day"
    session_path.write_text(json.dumps(session))

    # A structurally complete daily stream: one revealed setup bar carrying the
    # scanner plan, plus all required daily indicators so stream integrity passes.
    ind = {
        "sma20": 9.0, "sma50": 8.0, "sma200": 7.0, "atr14": 1.0, "rvol": 1.2,
        "above_sma20": True, "above_sma50": True, "above_sma200": True,
        "sma50_rising": True,
    }
    plan = {
        "signal_as_of": "2025-03-10", "trigger": 10.1, "stop": 9.0,
        "target1": 11.0, "target2": 12.0, "atr": 1.0,
        "cup_depth_px": 2.0, "max_entry_gap_atr": 0.5, "arm_expiry_bars": 5,
    }
    stream = [
        {"type": "meta", "ticker": "TEST", "date": "2025-03-10", "strategy": "cup_handle",
         "horizon": "multi_day", "bar_resolution": "1day"},
        {"type": "tick", "i": 0, "time": "16:00", "date": "2025-03-10",
         "o": 10.0, "h": 10.2, "l": 9.8, "c": 10.0, "v": 10_000,
         "is_setup_day": True, "scanner_plan": plan, **ind},
        {"type": "tick", "i": 1, "time": "16:00", "date": "2025-03-11",
         "o": 10.0, "h": 10.4, "l": 9.7, "c": 10.2, "v": 10_000, **ind},
        {"type": "end", "bars": 2, "close": 10.2},
    ]
    (sdir / "stream.jsonl").write_text("\n".join(json.dumps(r) for r in stream) + "\n")

    recorder.log(sdir, {
        "i": 0, "time": "16:00", "action": "ARM_BUY_STOP", "trigger": 10.1,
        "stop": 9.0, "atr": 1.0, "max_entry_gap_atr": 0.5, "expiry_bars": 5,
    })
    recorder.log(sdir, {"i": 1, "time": "16:00", "action": "OBSERVE"})
    recorder.finalize(sdir)

    # The clean, log-written session passes the re-validation.
    assert recorder.batch_integrity_errors(sdir) == []

    decisions = [json.loads(l) for l in (sdir / "decisions.jsonl").read_text().splitlines() if l.strip()]

    # 1. Off-plan trigger forged directly into the file (still intent-valid).
    forged = [dict(d) for d in decisions]
    forged[0]["trigger"] = 10.9
    (sdir / "decisions.jsonl").write_text("\n".join(json.dumps(r) for r in forged) + "\n")
    errors = recorder.batch_integrity_errors(sdir)
    assert any("does not match the revealed scanner plan" in e for e in errors)

    # 2. Engine-owned targets stripped from the persisted arm.
    stripped = [dict(d) for d in decisions]
    stripped[0].pop("engine_targets", None)
    (sdir / "decisions.jsonl").write_text("\n".join(json.dumps(r) for r in stripped) + "\n")
    errors = recorder.batch_integrity_errors(sdir)
    assert any("engine_targets is missing" in e for e in errors)

    # 3. A forbidden agent SCALE_LIMIT appended after the arm.
    with_scale = [dict(d) for d in decisions] + [
        {"i": 2, "time": "16:00", "action": "SCALE_LIMIT", "target": 11.0, "fraction": 0.5}
    ]
    (sdir / "decisions.jsonl").write_text("\n".join(json.dumps(r) for r in with_scale) + "\n")
    errors = recorder.batch_integrity_errors(sdir)
    assert any("SCALE_LIMIT is not permitted" in e for e in errors)


def test_recorder_allows_causal_lookback_before_setup_but_not_through_it(tmp_path):
    sdir = recorder.init(
        "TEST", "2025-03-11", strategy="cup_handle", root=tmp_path,
        now=datetime(2026, 7, 10, 10, 0, 0),
    )
    session_path = sdir / "session.json"
    session = json.loads(session_path.read_text())
    session["config"]["execution_model"] = EXECUTION_MODEL
    session["skill"]["arm_on_scanner_plan_required"] = True
    session_path.write_text(json.dumps(session))
    daily = {
        "sma20": 10.0, "sma50": 10.0, "sma200": 10.0, "atr14": 1.0,
        "rvol": 1.0, "above_sma20": True, "above_sma50": True,
        "above_sma200": True, "sma50_rising": True,
    }
    rows = [
        {"type": "meta", "ticker": "TEST", "date": "2025-03-11",
         "strategy": "cup_handle", "horizon": "multi_day", "bar_resolution": "1day"},
        {"type": "tick", "i": 0, "date": "2025-03-10", "time": "16:00", **daily},
    ]
    stream_path = sdir / "stream.jsonl"
    stream_path.write_text("\n".join(json.dumps(row) for row in rows) + "\n")

    # The harness must be able to auto-observe this pre-setup lookback bar.
    recorder.log(sdir, {"i": 0, "time": "16:00", "action": "OBSERVE"})

    # When the planned date is revealed, a missing setup marker/plan is not deferred.
    rows.append({"type": "tick", "i": 1, "date": "2025-03-11", "time": "16:00", **daily})
    stream_path.write_text("\n".join(json.dumps(row) for row in rows) + "\n")
    with pytest.raises(ValueError, match="causal scanner plan requires exactly one setup bar; found 0"):
        recorder.log(sdir, {"i": 1, "time": "16:00", "action": "OBSERVE"})


def test_recorder_rejects_a_daily_stream_with_missing_indicators(tmp_path):
    sdir = recorder.init(
        "TEST", "2025-03-10", strategy="cup_handle", root=tmp_path,
        now=datetime(2026, 7, 10, 10, 0, 0),
    )
    (sdir / "stream.jsonl").write_text("\n".join(json.dumps(row) for row in [
        {
            "type": "meta", "ticker": "TEST", "date": "2025-03-10",
            "strategy": "cup_handle", "horizon": "multi_day", "bar_resolution": "1day",
        },
        {
            "type": "tick", "i": 0, "date": "2025-03-10", "time": "16:00",
            "o": 10.0, "h": 10.2, "l": 9.8, "c": 10.0, "v": 10_000,
            "sma20": 10.0, "sma50": 10.0, "sma200": None, "atr14": 0.5,
            "rvol": 1.0, "above_sma20": True, "above_sma50": True,
            "above_sma200": None, "sma50_rising": True,
        },
    ]) + "\n")

    with pytest.raises(ValueError, match="daily stream data-integrity failure.*sma200"):
        recorder.log(sdir, {"i": 0, "time": "16:00", "action": "OBSERVE"})
    with pytest.raises(ValueError, match="daily stream data-integrity failure.*sma200"):
        recorder.finalize(sdir)


def test_recorder_validates_entry_bracket_shape(tmp_path):
    sdir = recorder.init("TEST", "2025-03-10", root=tmp_path, now=datetime(2026, 7, 10, 10, 0, 0))
    session_path = sdir / "session.json"
    session = json.loads(session_path.read_text())
    session["config"]["execution_model"] = EXECUTION_MODEL
    session["skill"]["entry_bracket_required"] = "true"
    session_path.write_text(json.dumps(session))
    _stream(sdir / "stream.jsonl")

    with pytest.raises(ValueError, match="requires an entry bracket"):
        recorder.log(sdir, {
            "i": 0, "time": "10:20", "action": "ENTER_CLOSE", "stop": 9.0,
        })
    with pytest.raises(ValueError, match="strictly increasing"):
        recorder.log(sdir, {
            "i": 0, "time": "10:20", "action": "ENTER_CLOSE", "stop": 9.0,
            "bracket": {"scales": [
                {"r_multiple": 1.0, "fraction": 0.5},
                {"r_multiple": 1.0, "fraction": 0.5},
            ]},
        })


def test_recorder_validates_entry_pyramid_shape(tmp_path):
    sdir = recorder.init("TEST", "2025-03-10", root=tmp_path, now=datetime(2026, 7, 10, 10, 0, 0))
    session_path = sdir / "session.json"
    session = json.loads(session_path.read_text())
    session["config"]["execution_model"] = EXECUTION_MODEL
    session["skill"]["entry_pyramid_required"] = "true"
    session_path.write_text(json.dumps(session))
    _stream(sdir / "stream.jsonl")

    with pytest.raises(ValueError, match="requires an entry pyramid"):
        recorder.log(sdir, {
            "i": 0, "time": "10:20", "action": "ENTER_CLOSE", "stop": 9.0,
        })
    with pytest.raises(ValueError, match="max_adds"):
        recorder.log(sdir, {
            "i": 0, "time": "10:20", "action": "ENTER_CLOSE", "stop": 9.0,
            "pyramid": {"starter_fraction": 0.333, "max_adds": 3},
        })
def test_recorder_replays_a_valid_entry_bracket(tmp_path):
    sdir = recorder.init("TEST", "2025-03-10", root=tmp_path, now=datetime(2026, 7, 10, 10, 0, 0))
    session_path = sdir / "session.json"
    session = json.loads(session_path.read_text())
    session["config"].update({
        "execution_model": EXECUTION_MODEL,
        "risk_budget": 100.0,
        "buying_power": 10_000.0,
        "execution": {
            "risk_budget": 100.0, "buying_power": 10_000.0,
            "entry_slippage_bps": 0.0, "exit_slippage_bps": 0.0,
            "commission_per_share": 0.0, "max_participation_rate": 1.0,
            "tick_size": 0.01,
        },
    })
    session["skill"]["entry_bracket_required"] = "true"
    session_path.write_text(json.dumps(session))
    lines = [
        {"type": "meta", "ticker": "TEST", "date": "2025-03-10", "entry_time": "10:20", "entry_px": 10.0},
        {"type": "tick", "i": 0, "time": "10:20", "o": 10.0, "h": 10.2, "l": 9.8, "c": 10.0, "v": 10_000},
        {"type": "tick", "i": 1, "time": "10:21", "o": 10.0, "h": 11.1, "l": 10.0, "c": 11.0, "v": 10_000},
        {"type": "end", "bars": 2, "close": 11.0},
    ]
    (sdir / "stream.jsonl").write_text("\n".join(json.dumps(x) for x in lines) + "\n")
    recorder.log(sdir, {
        "i": 0, "time": "10:20", "action": "ENTER_CLOSE", "stop": 9.0,
        "bracket": {"scales": [{"r_multiple": 1.0, "fraction": 0.333}]},
    })

    resolved = recorder.resolve(sdir, 1)
    assert resolved["position_shares"] == 67
    assert [(fill["action"], fill["shares"]) for fill in resolved["fills"]] == [("SCALE", 33)]


def test_init_freezes_deterministic_execution_assumptions(tmp_path):
    skill = tmp_path / "candidate.md"
    skill.write_text(
        "---\nname: trade-simulator\nversion: 3.0.0\n"
        "execution_model: deterministic_ohlc_v1\nentry_bracket_required: true\n"
        "entry_pyramid_required: true\nscanner_plan_targets_engine_owned: true\n---\n# candidate\n"
    )
    runner_contract = {"harness_version": "test", "prompt_hash": "sha256:p"}
    sdir = recorder.init("TEST", "2025-03-10", root=tmp_path, skill=skill,
                         risk_budget=75.0, buying_power=5_000.0,
                         runner_contract=runner_contract,
                         now=datetime(2026, 7, 10, 10, 0, 0))
    runner_contract["prompt_hash"] = "mutated-after-init"
    config = json.loads((sdir / "session.json").read_text())["config"]
    assert config["execution_model"] == EXECUTION_MODEL
    assert config["execution"]["risk_budget"] == 75.0
    assert config["execution"]["buying_power"] == 5_000.0
    assert config["execution"]["max_participation_rate"] == 0.10
    session = json.loads((sdir / "session.json").read_text())
    assert session["runner_contract"]["prompt_hash"] == "sha256:p"
    assert session["skill"]["entry_bracket_required"] == "true"
    assert session["skill"]["entry_pyramid_required"] == "true"
    assert session["skill"]["scanner_plan_targets_engine_owned"] == "true"


def _attribution_stream(path):
    lines = [
        {"type": "meta", "ticker": "TEST", "date": "2025-03-10", "entry_time": "10:20", "entry_px": 10.0},
        {"type": "tick", "i": 0, "time": "10:20", "o": 10.0, "h": 10.1, "l": 9.9, "c": 10.0, "v": 100},
        {"type": "tick", "i": 1, "time": "10:21", "o": 10.0, "h": 12.1, "l": 10.0, "c": 12.0, "v": 100},
        {"type": "end", "bars": 2, "close": 12.0},
    ]
    path.write_text("\n".join(json.dumps(x) for x in lines) + "\n")


def _attribution_session(tmp_path, *, batch, ticker, trade):
    sdir = recorder.init(
        ticker, "2025-03-10", root=tmp_path, batch=batch,
        now=datetime(2026, 7, 10, 10, 0, 0),
    )
    session_path = sdir / "session.json"
    session = json.loads(session_path.read_text())
    session["config"].update({
        "execution_model": EXECUTION_MODEL,
        "risk_budget": 100.0,
        "buying_power": 10_000.0,
        "execution": {
            "risk_budget": 100.0,
            "buying_power": 10_000.0,
            "entry_slippage_bps": 100.0,
            "exit_slippage_bps": 100.0,
            "commission_per_share": 0.01,
            "max_participation_rate": 0.10,
            "tick_size": 0.01,
        },
    })
    session_path.write_text(json.dumps(session))
    _attribution_stream(sdir / "stream.jsonl")
    if trade:
        recorder.log(sdir, {"i": 0, "time": "10:20", "action": "ENTER_CLOSE", "stop": 9.0})
        recorder.log(sdir, {"i": 1, "time": "10:21", "action": "EXIT_CLOSE"})
    else:
        recorder.log(sdir, {"i": 0, "time": "10:20", "action": "STAND_DOWN"})
    recorder.finalize(sdir, full_day=False)
    return sdir


def test_execution_attribution_replays_intents_without_writing(tmp_path, monkeypatch):
    batch = "attribution-test"
    traded = _attribution_session(tmp_path, batch=batch, ticker="TRADE", trade=True)
    _attribution_session(tmp_path, batch=batch, ticker="PASS", trade=False)
    original_actions = (traded / "actions.json").read_text()

    monkeypatch.setattr(recorder, "SIM_ROOT", tmp_path)
    report = recorder.execution_attribution(batch)

    assert report["n_eligible"] == 2
    assert report["n_skipped"] == 0
    assert report["verification"]["recorded_mismatches"] == []
    rows = {row["profile"]: row for row in report["profiles"]}
    assert rows["recorded"]["n"] == 2
    assert rows["recorded"]["trades"] == 1
    assert rows["recorded"]["stood_down"] == 1
    assert rows["no_commission"]["pnl"] > rows["recorded"]["pnl"]
    assert rows["no_slippage"]["pnl"] > rows["recorded"]["pnl"]
    assert rows["no_participation_cap"]["pnl"] > rows["recorded"]["pnl"]
    assert rows["frictionless"]["pnl"] > rows["no_participation_cap"]["pnl"]
    assert rows["frictionless"]["fees"] == 0.0
    # Attribution only replays raw inputs in memory; it never rewrites sealed artifacts.
    assert (traded / "actions.json").read_text() == original_actions


def test_execution_attribution_rejects_legacy_only_batch(tmp_path, monkeypatch):
    sdir = tmp_path / "legacy"
    sdir.mkdir()
    (sdir / "session.json").write_text(json.dumps({
        "status": "complete", "batch": "legacy-batch", "ticker": "OLD",
        "historical_date": "2025-03-10", "config": {"execution_model": "reported_fill_v1"},
    }))
    monkeypatch.setattr(recorder, "SIM_ROOT", tmp_path)

    with pytest.raises(ValueError, match="no completed deterministic_ohlc_v1 sessions"):
        recorder.execution_attribution("legacy-batch")
