from datetime import date

from trading.live.denylist import Denylist, DenylistEntry, TradabilityInputs
from trading.live.planner import build_target_book

ASOF = date(2026, 6, 19)


def test_top_n_cut(fake_release):
    book = build_target_book(fake_release, context=None, denylist=Denylist(), asof=ASOF)
    assert book.tickers == ["AAA", "BBB", "CCC"]   # top_n = 3
    assert book.ranked_count == 4
    assert book.blocked == []


def test_denylisted_name_blocked_and_filled_in(fake_release):
    dl = Denylist(entries=[DenylistEntry("BBB", "blocked")])
    book = build_target_book(fake_release, context=None, denylist=dl, asof=ASOF)
    # BBB denied → DDD fills the freed slot, book stays at top_n=3
    assert book.tickers == ["AAA", "CCC", "DDD"]
    assert [b.ticker for b in book.blocked] == ["BBB"]
    assert "blocked" in book.blocked[0].reason


def test_halted_name_blocked_via_tradability(fake_release):
    trad = {"AAA": TradabilityInputs(tradable=True, halted=True, price=100.0)}
    book = build_target_book(fake_release, context=None, denylist=Denylist(),
                             asof=ASOF, tradability=trad)
    assert "AAA" not in book.tickers
    assert book.tickers == ["BBB", "CCC", "DDD"]


def test_book_carries_score_and_close(fake_release):
    book = build_target_book(fake_release, context=None, denylist=Denylist(), asof=ASOF)
    top = book.entries[0]
    assert top.ticker == "AAA" and top.score == 0.9 and top.close == 100.0
