# llm_trader — SPEC

**Goal:** Replay historical market data and emit the *entries* Ross Cameron's
Warrior Trading momentum strategy (`library/analyst_warrior_trading_strategy.md`)
would have taken — gap-up, low-float, high-RVOL small caps breaking out in the
morning. Output is a **list of entry signals** (ticker, date, time, one-sentence
reason) to replay manually on TradingView. **No exit / P&L / success simulation.**

Market data comes from `trading.marketdata` (`fetch_bars`); the symbol universe
and float come from external APIs (Finnhub symbol list, yfinance float).

Status: **APPROVED — decisions in §7 resolved. Building.**

---

## 1. The strategy we encode (mechanical subset)

Screen each morning for stocks **gapping up > 5%**, **price $2–$20**,
**avg volume > 500K**, **relative volume > 2x (target 5x+)**, **float < 20M**.
From that watchlist take the **core entry**: the first 5-minute candle to make a
**new high out of a consolidation / opening range** (ACD / flat-top / ORB), inside
**07:00–12:00 ET** (best 07:00–10:00), with volume expansion and price above VWAP.
One primary entry per ticker per day.

## 2. Resolved scope decisions

| Decision | Resolution |
|---|---|
| **Window** | **2025-01-01 → 2026-06-30** (H1-2026). Current-snapshot float ≈ historical float over this span. Expand to earlier years later. |
| **Universe** | **Broad** — all US exchange-listed (NASDAQ/NYSE/AMEX) common stocks from Finnhub (~4,950, OTC excluded). Fetch intraday **on demand** for daily hits, even if not currently cached. |
| **Float** | **Hard filter, default < 20M** (Cameron "hot"). Source: yfinance `floatShares` (current snapshot, cached per ticker). Threshold configurable. |
| **News / catalyst** | **Dropped as a filter** — no historical source reachable (Finnhub free = recent only; Alpaca news = 401). A 5%+ gap on high RVOL is treated as the implicit catalyst; user eyeballs actual news on TradingView during replay. |
| **Patterns** | **Core ACD / ORB flat-top breakout** first. VWAP-bounce / micro-pullback deferred. |
| **Output** | **Entry scanner only.** SQLite table + text dump: `ticker, date, time_et, reason`. No exit/stat simulation. |
| **Account profile** | Default **small** ($2–$20). Configurable. |

### Data feasibility (verified 2026-06-30)
- marketdata daily (`1day`) 2007+, raw — fully fetchable on demand (daily backfill works for any ticker).
- Finnhub `/stock/symbol?exchange=US` (follow redirect) → 18,421 common; 4,952 exchange-listed (XNAS 3,172 / XNYS 1,554 / XASE 226).
- yfinance `.info["floatShares"]` returns current float (e.g. AAOI 76.3M).
- ❌ No working historical news source on current keys.

### ⚠️ On-demand INTRADAY fetch — provider-credential state (diagnosed 2026-06-30)
On-demand 5-min fetch for uncached days is **partially** available; the earlier
"fully blocked" reading was wrong. Two independent provider issues:

- **Alpaca key is dead** — HTTP 401 on every endpoint *including* `/v2/account`
  (paper and live). This is an **auth failure** (nginx-layer, before the data plane),
  i.e. the key is invalid/expired/revoked — *not* a data-plan limitation. The stored
  `ALPACA_API_KEY_ID` is also an odd length (26 ch) so it may be mangled. ⇒ the
  deep-history intraday provider is offline until the key is regenerated. A valid
  free "Basic" key restores historical SIP intraday back years.
- **MarketData.app token is valid** but on a **free/trial plan capped at 1 year of
  history** (`"Free/Trial users can only access up to 1 year of data."` → HTTP 402
  for older dates). Within the last ~12 months it serves intraday fine.

**Net effect on the scanner today:**
- Dates **within ~12 months** (≈2025-07 → present): intraday fetches on demand via
  MarketData (Alpaca's 401 is silently covered) — Stage B works across the broad
  universe.
- Dates **older than ~1 year**: only Alpaca could serve them, and it's down ⇒ Stage B
  yields no entry (logged, not errored) for uncached older gappers.

**Fix (highest leverage):** regenerate the Alpaca Basic (free) key into the root
`.env`. Until then, run with `--start` inside the last 12 months for full coverage.
The `gappers` vs `entries` counts in the run log reveal any intraday shortfall.

## 3. Pipeline

```
A0 — Symbol universe        (Finnhub symbol list, cached to data/universe_symbols.json)
   exchange-listed common stocks (XNAS/XNYS/XASE), refreshable.

A1 — Daily gap screen       (marketdata 1day, window)
   For each ticker, each trading day D:
     gap%   = (open_D - close_{D-1}) / close_{D-1}
     rvol   = volume_D / avg_volume(20d ending D-1)
     price  = open_D (or prior close) within [price_min, price_max]
   Keep (D, ticker) where gap% >= 5, price in band, avg_vol > 500K, rvol >= 2.
   -> candidate day-ticker pairs.

A2 — Float gate             (yfinance, cached to data/float_cache.json)
   For each candidate ticker (fetched once): drop if floatShares >= float_max (20M).

B  — Intraday entry detect  (marketdata 5min + 1min extended, 07:00-12:00 ET)
   Build session frame; compute VWAP + EMA9 + running session high.
   ACD/ORB trigger = first 5-min bar in window whose HIGH breaks the prior
   consolidation/running-session high after a pause of >=2 bars, with
   bar-volume expansion and close > VWAP. One entry per ticker/day.
   -> Entry {ticker, date, t_entry_et, px_entry, gap%, rvol, float, reason}.

OUTPUT — write entries to SQLite (data/entries.db, table `entries`) and a
         human-readable text/CSV dump.
```

Each stage is independently inspectable (CLI flags to dump A1 candidates, A2
survivors, B entries).

## 4. Config (defaults from the doc)

```yaml
start: 2025-01-01
end:   2026-06-30
account_profile: small        # small | main
price_min: 2.0                # small=2, main=5
price_max: 20.0               # small=20, main=50
gap_min_pct: 5.0
avg_vol_min: 500_000
rvol_min: 2.0
rvol_lookback: 20
float_max: 20_000_000         # Cameron "hot"; set null to disable
entry_window_et: ["07:00","12:00"]
consolidation_min_bars: 2     # bars of pause before a valid breakout
vol_expansion_mult: 1.5       # breakout bar volume vs rolling avg
require_above_vwap: true
exchanges: [XNAS, XNYS, XASE]
```

## 5. Output schema & uniqueness

**Idempotency requirement:** re-running the finder over the same (or overlapping)
date range must never create duplicate setups. A setup is uniquely identified by
**`(ticker, date, pattern)`** — there is at most one primary entry per ticker per
day per pattern, and its time/price are deterministic given the data.

Implementation:
- `entries` table has a composite **PRIMARY KEY (ticker, date, pattern)** (and a
  derived `setup_id = sha1("{ticker}|{date}|{pattern}")` column for joins/exports).
- Writes use **`INSERT … ON CONFLICT(ticker,date,pattern) DO UPDATE`** (upsert):
  a rerun refreshes the row in place (e.g. if config/data changed) but can never
  duplicate it. Re-running an identical scan is a no-op on row count.
- The CSV/text dump is regenerated from the table, so it inherits the uniqueness.

`entries` table / CSV columns:
| col | meaning |
|---|---|
| `ticker` | symbol |
| `date` | trade date (ET) |
| `time_et` | entry timestamp HH:MM ET |
| `pattern` | `acd_orb` |
| `entry_px` | breakout price |
| `gap_pct` | daily gap % |
| `rvol` | relative volume |
| `float_shares` | current float |
| `reason` | one-sentence English explanation |

Reason example:
> "ACD breakout: gapped +18.3% on 12.4× RVOL, float 8.2M; first 5-min new high at
> 09:35 ET cleared premarket consolidation high $4.12 on 3.1× bar-volume, close above VWAP."

## 6. Module layout

```
llm_trader/
  SPEC.md
  __init__.py
  config.py        params dataclass + YAML loader
  universe.py      A0 — Finnhub symbol list (cached)
  screen.py        A1 — daily gap screen
  floats.py        A2 — yfinance float gate (cached)
  patterns.py      B  — VWAP/EMA/ORB entry detector
  runner.py        orchestrate A0→A1→A2→B, write output
  cli.py           `python -m trading.llm_trader.runner ...`
  data/            outputs + caches (gitignored)
  tests/
```

## 7. Out of scope (v1)
- Exit / P&L / win-rate simulation (user replays on TradingView).
- News/catalyst filtering (no data); Level 2 / tape (no data); shorting.
- Point-in-time float (only current snapshot) → window limited to 2025–2026H1.
- VWAP-bounce / micro-pullback patterns (phase 2).
- Pre-2025 years (phase 2, once a point-in-time float source exists).
