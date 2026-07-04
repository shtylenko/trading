from trading.live.parity import DriftBands, evaluate, signal_match, slippage_bps


def test_signal_match_full_and_partial():
    assert signal_match(["A", "B", "C"], ["A", "B", "C"]) == 1.0
    assert signal_match(["A", "B", "C", "D"], ["A", "B"]) == 0.5
    assert signal_match([], []) == 1.0


def test_slippage_sign_and_weight():
    # bought AAA at 101 vs expected 100 → +100 bps (cost); sold BBB at 49 vs 50 → +200 bps
    fills = [{"ticker": "AAA", "side": "buy", "qty": 10, "price": 101.0},
             {"ticker": "BBB", "side": "sell", "qty": 10, "price": 49.0}]
    exp = {"AAA": 100.0, "BBB": 50.0}
    bps = slippage_bps(fills, exp)
    assert bps is not None and bps > 0           # both adverse


def test_no_slippage_when_at_expected():
    fills = [{"ticker": "AAA", "side": "buy", "qty": 5, "price": 100.0}]
    assert abs(slippage_bps(fills, {"AAA": 100.0})) < 1e-9


def test_evaluate_flags_signal_drift():
    res = evaluate(["A", "B", "C", "D"], ["A"], fills=[], expected_prices={},
                   bands=DriftBands(min_signal_match_pct=0.9))
    assert res.drift and res.signal_match_pct == 0.25
    assert "B" in res.detail["missing"]


def test_evaluate_flags_slippage_drift():
    fills = [{"ticker": "AAA", "side": "buy", "qty": 10, "price": 110.0}]
    res = evaluate(["AAA"], ["AAA"], fills=fills, expected_prices={"AAA": 100.0},
                   bands=DriftBands(max_slippage_bps=50.0))
    assert res.drift and res.slippage_bps > 50


def test_evaluate_clean_no_drift():
    res = evaluate(["A", "B"], ["A", "B"], fills=[], expected_prices={})
    assert not res.drift
