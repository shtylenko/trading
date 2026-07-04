from datetime import date

from trading.live.denylist import (Denylist, DenylistEntry, TradabilityInputs,
                                   buy_blocked_reason, load_platform_denylist, merge)

ASOF = date(2026, 6, 19)
OK = TradabilityInputs(tradable=True, halted=False, price=100.0, dollar_vol_20d=5e8)


def _dl(*entries, categories=None):
    return Denylist(entries=list(entries), categories=categories or {})


def test_denylist_blocks_buy():
    dl = _dl(DenylistEntry("GME", "meme"))
    assert buy_blocked_reason("GME", ASOF, dl, OK) == "denylist: meme"
    assert buy_blocked_reason("AAPL", ASOF, dl, OK) is None


def test_denylist_case_insensitive():
    dl = _dl(DenylistEntry("gme", "meme"))
    assert buy_blocked_reason("GME", ASOF, dl, OK) is not None


def test_expired_entry_ignored():
    dl = _dl(DenylistEntry("OLD", "x", expires=date(2026, 1, 1)))
    assert buy_blocked_reason("OLD", ASOF, dl, OK) is None


def test_halted_and_nontradable_blocked():
    dl = _dl()
    assert "halt" in buy_blocked_reason("AAPL", ASOF, dl, TradabilityInputs(True, True)).lower()
    assert buy_blocked_reason("AAPL", ASOF, dl, TradabilityInputs(False, False)) is not None


def test_category_rules():
    dl = _dl(categories={"block_leveraged_inverse": True, "min_price": 5.0})
    lev = TradabilityInputs(True, False, price=100.0, is_leveraged_inverse=True)
    assert "leveraged" in buy_blocked_reason("TQQQ", ASOF, dl, lev)
    cheap = TradabilityInputs(True, False, price=3.0)
    assert "price" in buy_blocked_reason("PENNY", ASOF, dl, cheap)


def test_merge_platform_and_portfolio():
    plat = _dl(DenylistEntry("AAA", "plat"))
    merged = merge(plat, [DenylistEntry("BBB", "pf", scope="pf1")])
    assert buy_blocked_reason("AAA", ASOF, merged, OK)
    assert buy_blocked_reason("BBB", ASOF, merged, OK)


def test_platform_baseline_loads():
    dl = load_platform_denylist()  # ships empty
    assert isinstance(dl.entries, list)
    assert "block_leveraged_inverse" in dl.categories
