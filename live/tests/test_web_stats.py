from trading.live.web import stats as S

SMAP = {"NVDA": "XLK", "AMD": "XLK", "JPM": "XLF", "XOM": "XLE"}


def _row(ticker, side="buy", qty=10, price=100.0, rank=1, score=0.5, reason="new position",
         held_qty=0):
    return {"ticker": ticker, "side": side, "qty": qty, "price": price,
            "notional": qty * price, "rank": rank, "score": score, "reason": reason,
            "held_qty": held_qty}


def test_empty():
    assert S.compute([], capital=100_000)["n"] == 0


def test_sector_distribution():
    rows = [_row("NVDA"), _row("AMD"), _row("JPM"), _row("XOM")]
    st = S.compute(rows, capital=100_000, sector_map=SMAP)
    by = {s["sector"]: s for s in st["sectors"]}
    assert by["Technology"]["count"] == 2          # NVDA + AMD
    assert by["Financials"]["count"] == 1
    # notional shares: tech 2/4 of equal-notional rows = 50%
    assert round(by["Technology"]["pct"]) == 50


def test_unmapped_bucket():
    st = S.compute([_row("ZZZZ")], capital=100_000, sector_map=SMAP)
    assert st["sectors"][0]["sector"] == "Unmapped"


def test_capital_and_concentration():
    rows = [_row("NVDA", qty=10, price=100), _row("AMD", qty=5, price=100),
            _row("OLD", side="sell", qty=3, price=100)]
    st = S.compute(rows, capital=10_000, sector_map=SMAP)
    assert st["capital"]["buy_notional"] == 1500     # 1000 + 500
    assert st["capital"]["sell_notional"] == 300
    assert st["capital"]["net_notional"] == 1200
    assert round(st["capital"]["buy_pct_of_capital"]) == 15
    assert st["capital"]["n_buys"] == 2 and st["capital"]["n_sells"] == 1
    # concentration over buys: NVDA 1000/1500 = 66.7%
    assert round(st["concentration"]["max_weight_pct"]) == 67


def test_conviction_and_composition():
    rows = [_row("NVDA", rank=1, score=0.9, held_qty=0),
            _row("AMD", rank=8, score=0.3, held_qty=5, reason="add within band")]
    st = S.compute(rows, capital=100_000, sector_map=SMAP)
    assert st["conviction"]["rank_min"] == 1 and st["conviction"]["rank_max"] == 8
    assert st["conviction"]["score_max"] == 0.9
    assert st["composition"]["new_positions"] == 1     # NVDA
    assert st["composition"]["adds"] == 1              # AMD (held)
