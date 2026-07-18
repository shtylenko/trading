# VWAP pullback — short-hold SPEC (v0.1.0)

**Mandate:** same-day long only; flat by close.

## Thesis

On a strength day (gap + RVOL), price holds above session VWAP in the morning,
pulls back to VWAP midday, and reclaims — institutional VWAP support.

## Rules

1. Daily screen: gap ≥ 0.5%, RVOL ≥ 1.2, price $10–1000, ADV ≥ 1M  
2. 5m RTH: ≥3 bars above VWAP by 10:30  
3. First VWAP touch+green reclaim in 10:00–14:00  
4. Entry: next 5m open after reclaim  
5. Stop: VWAP − 0.15%  
6. T1/T2: 1R / 2R; EOD 15:55  

**Validation:** offline 5m path sim (not LLM batch). Multi-year gate same as swings.

## Paper packaging

| Control | Default | Notes |
|---|---|---|
| NML gate | **OFF** | A/B hard-fail on VWAP |
| Portfolio | **ON** | max concurrent 3, max 5/day |
| Build | `python -m trading.llm_trader.strategies.vwap_pullback.paper` | `batch/vwap_pullback/paper/` |

Promotion: research / paper-optional only. More cost-fragile than micro_pullback.
