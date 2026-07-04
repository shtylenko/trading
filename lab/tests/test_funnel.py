from __future__ import annotations

from trading.lab.storage.duckdb import connect, init_db
from trading.lab.storage.lifecycle import (
    get_lifecycle,
    list_lifecycle,
    upsert_lifecycle,
)
from trading.lab.validation import funnel
from trading.lab.validation.funnel import (
    GateInput,
    Verdict,
    rung_for_testset,
)


# --- gate predicates -------------------------------------------------------

def test_smoke_gate_passes_zero_trades_when_clean():
    # 0 trades on a quiet smoke day is NOT a kill — it's normal.
    assert funnel.gate_smoke(GateInput(trade_count=0)).verdict is Verdict.PASS
    assert funnel.gate_smoke(GateInput(trade_count=3)).verdict is Verdict.PASS


def test_smoke_gate_kills_dirty_run_and_integrity():
    assert funnel.gate_smoke(GateInput(trade_count=3, ran_clean=False)).verdict is Verdict.KILL
    assert funnel.gate_smoke(GateInput(trade_count=3, integrity_ok=False)).verdict is Verdict.KILL


def test_screen_gate_matches_existing_rule():
    # too few trades
    assert funnel.gate_screen(GateInput(sum_r=5, trade_count=10, p_value=0.1)).verdict is Verdict.KILL
    # negative sum R
    assert funnel.gate_screen(GateInput(sum_r=-1, trade_count=50, p_value=0.1)).verdict is Verdict.KILL
    # high p
    assert funnel.gate_screen(GateInput(sum_r=5, trade_count=50, p_value=0.6)).verdict is Verdict.KILL
    # survivor
    assert funnel.gate_screen(GateInput(sum_r=5, trade_count=50, p_value=0.1)).verdict is Verdict.PASS


def test_broad_is_gate_grades_weak_and_one_bucket_carry():
    base = dict(sum_r=10, trade_count=200, trades_per_quarter=40, worst_bucket_r=1.0)
    # clean pass
    assert funnel.gate_broad_is(GateInput(p_value=0.01, **base)).verdict is Verdict.PASS
    # positive but weak p -> review
    assert funnel.gate_broad_is(GateInput(p_value=0.2, **base)).verdict is Verdict.REVIEW
    # one-bucket carry -> review even at strong p
    carry = dict(base, worst_bucket_r=-9.0)
    assert funnel.gate_broad_is(GateInput(p_value=0.01, **carry)).verdict is Verdict.REVIEW
    # too few trades/quarter -> kill
    thin = dict(base, trades_per_quarter=5)
    assert funnel.gate_broad_is(GateInput(p_value=0.01, **thin)).verdict is Verdict.KILL


def test_oos_gate_flags_artifact_when_far_above_in_sample():
    # OOS far above in-sample -> review (artifact smell), not pass
    g = GateInput(sum_r=50, trade_count=200, p_value=0.01, is_sum_r=10)
    assert funnel.gate_oos(g).verdict is Verdict.REVIEW
    # OOS in line with in-sample -> pass
    g2 = GateInput(sum_r=12, trade_count=200, p_value=0.01, is_sum_r=10)
    assert funnel.gate_oos(g2).verdict is Verdict.PASS
    # OOS negative -> kill
    assert funnel.gate_oos(GateInput(sum_r=-3, p_value=0.01)).verdict is Verdict.KILL


def test_fuzzy_rungs_return_review():
    assert funnel.gate_robustness(GateInput()).verdict is Verdict.REVIEW
    assert funnel.gate_tradeability(GateInput()).verdict is Verdict.REVIEW
    assert funnel.gate_portfolio(GateInput()).verdict is Verdict.REVIEW


# --- ladder wiring ---------------------------------------------------------

def test_rung_for_testset_maps_canonical_and_ignores_adhoc():
    assert rung_for_testset("screen_2022_2026_sampled").name == "screen"
    assert rung_for_testset("eval_2025_broad").name == "oos"
    assert rung_for_testset("eval_2024_h1_broad").name == "broad_is"
    assert rung_for_testset("smoke_april_2024_sample").name == "smoke"
    assert rung_for_testset("some_adhoc_testset") is None
    assert rung_for_testset(None) is None


def test_oos_rung_has_prereq_and_flag():
    oos = rung_for_testset("eval_2025_broad")
    assert oos.is_oos is True
    assert oos.prereq_stage == 2


# --- ledger round-trip -----------------------------------------------------

def test_lifecycle_default_is_stage0_active(tmp_path):
    db = tmp_path / "lc.duckdb"
    init_db(db)
    with connect(db) as conn:
        row = get_lifecycle(conn, "o01")
    assert row["stage"] == 0
    assert row["disposition"] == "active"
    assert row["killed_stage"] is None


def test_lifecycle_upsert_and_list(tmp_path):
    db = tmp_path / "lc.duckdb"
    init_db(db)
    with connect(db) as conn:
        upsert_lifecycle(
            conn, "o03", stage=2, disposition="killed",
            killed_stage=3, reason="universe artifact", decided_by_run="run_x",
        )
        row = get_lifecycle(conn, "o03")
        assert row["stage"] == 2
        assert row["disposition"] == "killed"
        assert row["killed_stage"] == 3
        assert row["reason"] == "universe artifact"
        assert row["decided_by_run"] == "run_x"

        # replace, not duplicate
        upsert_lifecycle(conn, "o03", stage=2, disposition="archived", reason="superseded")
        listed = list_lifecycle(conn)
        assert set(listed) == {"o03"}
        assert listed["o03"]["disposition"] == "archived"
        assert listed["o03"]["killed_stage"] is None
