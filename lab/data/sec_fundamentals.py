"""SEC EDGAR point-in-time fundamentals adapter.

The ONLY fundamentals source for strategy_lab. EDGAR's XBRL `companyfacts` API carries, for
every reported value, the **`filed` date** (when the filing became public) — the
point-in-time key that makes fundamentals momentum leak-safe: at a rebalance date `d` we may
only use facts with `filed <= d`. It is also survivorship-free (delisted companies' filings
persist) and free.

Design:
  - One `companyfacts/CIK##########.json` fetch per ticker returns ALL concepts; cached to
    disk so the universe is pulled once. Polite: a contact User-Agent (SEC requirement) and a
    global rate limiter (≤ ~8 req/s, under SEC's 10/s ceiling).
  - `pit_concept(facts, concept)` returns a tidy frame [filed, start, end, val, form, months]
    for one us-gaap concept across all of its unit entries, deduped (latest filing per period).
  - `asof_*` helpers read a value/series AS KNOWN at a date (filed <= asof), which is what the
    capture/triage scripts call. Period (flow) concepts also get a TTM helper that sums the
    last four distinct 3-month observations — avoids fiscal-quarter seasonality.

NOT a leak if used correctly: always filter `filed <= rebalance_date`. The fiscal period `end`
may be months before `filed`; that lag is the whole point (you learn Q-results only when filed).
"""
from __future__ import annotations

import json
import os
import time
import urllib.request
from pathlib import Path

import pandas as pd

# SEC requires a descriptive User-Agent with contact info or it returns 403.
SEC_UA = os.getenv("SEC_EDGAR_UA", "strategy_lab research (shtylenko@gmail.com)")
_CACHE = Path(os.getenv("STRATEGY_LAB_SEC_DIR") or (Path(__file__).resolve().parent / "_sec_cache"))
_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
_FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"

_MIN_INTERVAL = 0.13          # seconds between requests (~7.7/s, under SEC's 10/s)
_last_request = [0.0]


def _throttle() -> None:
    dt = time.monotonic() - _last_request[0]
    if dt < _MIN_INTERVAL:
        time.sleep(_MIN_INTERVAL - dt)
    _last_request[0] = time.monotonic()


def _get(url: str, retries: int = 3) -> bytes:
    """GET with polite throttle + retry on transient network errors (timeouts, 5xx, resets).

    HTTPError 404 is re-raised immediately (caller negative-caches it); everything else is
    retried with linear backoff so a single slow EDGAR response can't abort a universe pull.
    """
    last: Exception | None = None
    for attempt in range(retries):
        _throttle()
        req = urllib.request.Request(url, headers={"User-Agent": SEC_UA, "Accept-Encoding": "gzip, deflate"})
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                raw = resp.read()
                if resp.headers.get("Content-Encoding") == "gzip":
                    import gzip
                    raw = gzip.decompress(raw)
            return raw
        except urllib.error.HTTPError as e:
            if e.code == 404:
                raise
            last = e
        except Exception as e:                      # timeout, URLError, conn reset, incomplete read
            last = e
        time.sleep(1.0 + attempt)                    # linear backoff before retry
    raise last if last is not None else RuntimeError("unreachable")


def cik_map(force: bool = False) -> dict[str, str]:
    """ticker (UPPER) -> zero-padded 10-digit CIK string."""
    _CACHE.mkdir(parents=True, exist_ok=True)
    fp = _CACHE / "company_tickers.json"
    if force or not fp.exists():
        fp.write_bytes(_get(_TICKERS_URL))
    data = json.loads(fp.read_text())
    out: dict[str, str] = {}
    for row in data.values():
        out[str(row["ticker"]).upper()] = f"{int(row['cik_str']):010d}"
    return out


def fetch_company_facts(cik: str, force: bool = False) -> dict | None:
    """Cached companyfacts JSON for a 10-digit CIK. None if EDGAR has no facts (404)."""
    _CACHE.mkdir(parents=True, exist_ok=True)
    fp = _CACHE / f"facts_CIK{cik}.json"
    if not force and fp.exists():
        txt = fp.read_text()
        return json.loads(txt) if txt else None
    try:
        raw = _get(_FACTS_URL.format(cik=cik))
    except urllib.error.HTTPError as e:
        if e.code == 404:
            fp.write_text("")          # negative-cache: company has no XBRL facts
            return None
        raise
    except Exception:
        # transient failure after retries — skip this ticker (do NOT negative-cache, so a
        # later run retries it); the caller treats None as "no facts available this run".
        return None
    fp.write_bytes(raw)
    return json.loads(raw)


def pit_concept(facts: dict, concept: str, taxonomy: str = "us-gaap") -> pd.DataFrame:
    """Tidy frame for one concept: columns [filed, start, end, val, form, fy, fp, months].

    `months` = period length in months (NaN for instant/balance-sheet concepts). Deduped to the
    LATEST filing for each (start, end) period so each fiscal period appears once at its
    first-known value... no: we keep the latest `filed` per period (restatements use the
    as-filed-at-asof logic in the asof_* helpers, which slice by filed <= asof first).
    """
    try:
        units = facts["facts"][taxonomy][concept]["units"]
    except (KeyError, TypeError):
        return pd.DataFrame(columns=["filed", "start", "end", "val", "form", "fy", "fp", "months"])
    rows = []
    for unit_entries in units.values():
        for e in unit_entries:
            if "val" not in e or "end" not in e or "filed" not in e:
                continue
            start = e.get("start")
            end = e["end"]
            months = None
            if start:
                months = round((pd.Timestamp(end) - pd.Timestamp(start)).days / 30.4)
            rows.append({"filed": e["filed"], "start": start, "end": end, "val": e["val"],
                         "form": e.get("form"), "fy": e.get("fy"), "fp": e.get("fp"), "months": months})
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    for c in ("filed", "start", "end"):
        df[c] = pd.to_datetime(df[c], errors="coerce")
    return df.sort_values(["end", "filed"]).reset_index(drop=True)


def concept_union(facts: dict, concepts: list[str], taxonomies: tuple[str, ...] = ("us-gaap",)) -> pd.DataFrame:
    """Union of all tag variants for a logical concept, robust to XBRL tag drift.

    US-GAAP tags for the same economic quantity change over time and across filers (e.g.
    NVDA switched its revenue tag in 2022). Taking the FIRST tag with any data locks onto a
    deprecated series with stale values; instead we concatenate every variant and, for each
    (period-end, months) bucket, keep the LATEST-filed observation. This yields one continuous
    series spanning tag changes. The asof_* helpers then slice by filed <= asof.
    """
    parts = []
    for c in concepts:
        for tax in taxonomies:
            d = pit_concept(facts, c, taxonomy=tax)
            if not d.empty:
                d = d.copy(); d["concept"] = c
                parts.append(d)
    if not parts:
        return pd.DataFrame(columns=["filed", "start", "end", "val", "form", "fy", "fp", "months", "concept"])
    df = pd.concat(parts, ignore_index=True)
    # Keep EVERY (end, period-length, filing) observation — do NOT collapse to the latest
    # filing here: that would discard the originally-filed value that was known at an earlier
    # asof, breaking point-in-time. We only drop exact duplicates that arise when overlapping
    # tag variants report the identical fact. The asof_* helpers slice filed <= asof FIRST and
    # only THEN keep the latest filing per period (the correct as-known-then restatement view).
    df["_mb"] = pd.to_numeric(df["months"], errors="coerce").fillna(-1.0)
    df = df.drop_duplicates(["end", "_mb", "filed", "val"])
    return df.drop(columns="_mb").sort_values(["end", "filed"]).reset_index(drop=True)


# back-compat alias used by the __main__ smoke check
def _first_present(facts: dict, concepts: list[str]) -> pd.DataFrame:
    return concept_union(facts, concepts)


# Concept preference lists (US-GAAP tags drift over time / across filers).
ASSETS = ["Assets"]
REVENUES = ["RevenueFromContractWithCustomerExcludingAssessedTax", "Revenues",
            "SalesRevenueNet", "RevenueFromContractWithCustomerIncludingAssessedTax"]
COGS = ["CostOfGoodsAndServicesSold", "CostOfRevenue", "CostOfGoodsSold"]
EPS_DILUTED = ["EarningsPerShareDiluted"]
NET_INCOME = ["NetIncomeLoss"]
# Book equity (instant). StockholdersEquity = common equity; the IncludingNoncontrolling variant is
# a fallback for filers that only tag the broader line.
EQUITY = ["StockholdersEquity", "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"]
# Shares outstanding (instant). Prefer the DEI cover-page count (filed every 10-Q/K, PIT); fall back
# to the us-gaap balance-sheet count. Union across both taxonomies via shares_union().
SHARES_DEI = ["EntityCommonStockSharesOutstanding"]
SHARES_GAAP = ["CommonStockSharesOutstanding"]


def shares_union(facts: dict) -> pd.DataFrame:
    """Outstanding-shares series: DEI cover-page count unioned with the us-gaap balance-sheet count."""
    a = concept_union(facts, SHARES_DEI, taxonomies=("dei",))
    b = concept_union(facts, SHARES_GAAP, taxonomies=("us-gaap",))
    parts = [d for d in (a, b) if not d.empty]
    if not parts:
        return pd.DataFrame(columns=["filed", "start", "end", "val", "form", "fy", "fp", "months", "concept"])
    df = pd.concat(parts, ignore_index=True)
    df["_mb"] = pd.to_numeric(df["months"], errors="coerce").fillna(-1.0)
    df = df.drop_duplicates(["end", "_mb", "filed", "val"])
    return df.drop(columns="_mb").sort_values(["end", "filed"]).reset_index(drop=True)


def asof_instant(df: pd.DataFrame, asof: pd.Timestamp) -> float | None:
    """Latest balance-sheet (instant) value KNOWN at `asof` (filed <= asof, max end)."""
    if df.empty:
        return None
    k = df[df["filed"] <= asof]
    if k.empty:
        return None
    row = k.sort_values(["end", "filed"]).iloc[-1]
    return float(row["val"])


def _quarterly_asof(df: pd.DataFrame, asof: pd.Timestamp) -> pd.DataFrame:
    """Complete discrete-quarter series for a flow concept, KNOWN at asof.

    Many filers report income-statement flows only as fiscal-year-to-date CUMULATIVES
    (3/6/9/12-month, all sharing the fiscal-year start) — e.g. Apple omits a standalone
    3-month Q4 for net income (it lives only in the 12-month annual). Summing the raw
    "3-month" rows then leaves a 6-month gap where Q4 should be. We reconstruct the missing
    quarters by DIFFERENCING the YTD cumulatives within each fiscal year (Q4 = FY − 9mo YTD,
    Q3 = 9mo − 6mo, ...). Pure discrete-3-month filers fall out unchanged (each row is its own
    fiscal-year-start group of size 1). Returns columns [end, val] sorted by end, one row per
    quarter-end (latest fiscal-year reconstruction wins on overlap).
    """
    if df.empty:
        return pd.DataFrame(columns=["end", "val"])
    k = df[(df["filed"] <= asof) & df["start"].notna() & df["months"].notna()]
    k = k[(k["months"] >= 2) & (k["months"] <= 13)]
    if k.empty:
        return pd.DataFrame(columns=["end", "val"])
    # latest filing per (start, end) period — the as-known-then value
    k = k.sort_values(["start", "end", "filed"]).drop_duplicates(["start", "end"], keep="last")
    out = []
    for _start, g in k.groupby("start"):
        g = g.sort_values("end")
        vals = g["val"].to_numpy(dtype=float)
        disc = vals.copy()
        disc[1:] = vals[1:] - vals[:-1]        # YTD cumulatives → discrete quarters
        for end, d in zip(g["end"], disc):
            out.append((end, d))
    q = pd.DataFrame(out, columns=["end", "val"]).sort_values(["end"]).drop_duplicates("end", keep="last")
    return q.reset_index(drop=True)


def _contiguous_tail(q: pd.DataFrame, n: int) -> pd.DataFrame | None:
    """Last `n` quarters IF they are consecutive (~3 months apart); else None.

    Guards against gaps in the reported series (missing/late filings, tag changes) that would
    otherwise make a TTM/YoY window span the wrong periods and fabricate garbage growth rates.
    """
    if len(q) < n:
        return None
    tail = q.iloc[-n:]
    gaps = tail["end"].diff().dropna().dt.days
    if ((gaps < 80) | (gaps > 100)).any():
        return None
    return tail


def asof_ttm(df: pd.DataFrame, asof: pd.Timestamp) -> float | None:
    """Trailing-twelve-month sum of a flow concept, KNOWN at `asof`.

    Uses the four most recent CONSECUTIVE ~3-month observations; falls back to a single
    ~12-month (annual) observation if a clean quarterly TTM isn't available.
    """
    if df.empty:
        return None
    q = _quarterly_asof(df, asof)
    tail = _contiguous_tail(q, 4)
    if tail is not None:
        return float(tail["val"].sum())
    k = df[df["filed"] <= asof]
    a = k[(k["months"] >= 11) & (k["months"] <= 13)].sort_values(["end", "filed"])
    if not a.empty:
        return float(a.drop_duplicates("end", keep="last").iloc[-1]["val"])
    return None


def asof_ttm_growth(df: pd.DataFrame, asof: pd.Timestamp) -> float | None:
    """YoY growth of a TTM flow (split-safe earnings momentum when df = NetIncomeLoss).

    Needs 8 CONSECUTIVE quarters known at asof; compares latest TTM to the TTM a year earlier.
    Net-income TTM is split-insensitive (unlike per-share EPS).
    """
    if df.empty:
        return None
    q = _quarterly_asof(df, asof)
    tail = _contiguous_tail(q, 8)
    if tail is None:
        return None
    ttm_now = float(tail.iloc[-4:]["val"].sum())
    ttm_prior = float(tail.iloc[-8:-4]["val"].sum())
    if ttm_prior == 0:
        return None
    return (ttm_now - ttm_prior) / abs(ttm_prior)


if __name__ == "__main__":
    # quick PIT validation on a few names
    import sys
    tickers = sys.argv[1:] or ["AAPL", "MSFT", "XOM"]
    cmap = cik_map()
    asof = pd.Timestamp("2024-03-01")
    print(f"PIT fundamentals as known at {asof.date()} (UA={SEC_UA!r})\n")
    for t in tickers:
        cik = cmap.get(t.upper())
        if not cik:
            print(f"{t}: no CIK"); continue
        facts = fetch_company_facts(cik)
        if facts is None:
            print(f"{t}: no XBRL facts"); continue
        assets = concept_union(facts, ASSETS)
        rev = concept_union(facts, REVENUES)
        cogs = concept_union(facts, COGS)
        ni = concept_union(facts, NET_INCOME)
        A = asof_instant(assets, asof)
        R = asof_ttm(rev, asof)
        C = asof_ttm(cogs, asof)
        gp = (R - C) / A if (A and R is not None and C is not None and A != 0) else None
        em = asof_ttm_growth(ni, asof)
        last_filed = rev[rev["filed"] <= asof]["filed"].max() if not rev.empty else None
        gp_s = f"{gp:.3f}" if gp is not None else "None"
        em_s = f"{em:+.1%}" if em is not None else "None"
        rev_s = f"{R/1e9:.1f}B" if R is not None else "None"
        print(f"{t:6} CIK{cik}  assets={A/1e9 if A else None:.0f}B  ttm_rev={rev_s}  "
              f"GP/A={gp_s}  ni_ttm_yoy={em_s}  (latest rev known: "
              f"{last_filed.date() if last_filed is not None else None})")
