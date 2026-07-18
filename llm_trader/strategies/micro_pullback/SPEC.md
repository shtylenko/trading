# Micro-pullback — short-hold SPEC (v0.1.0)

**Thesis (Ross / warrior phase-2):** Fast runners often give only a 1–2 bar shallow
pullback. Long the first green that breaks the micro-pullback high; stop under the
pullback low. Never chase a vertical without a pause.

**Horizon:** same-day 5m RTH; flat EOD.

**Universe for multi-year gate:** liquid large-caps (same cohort as VWAP/BB), not
warrior penny gappers — tests the *structure* under the established short-hold gate.

## Rules

1. Daily: liquid + gap ≥ 0.5% + RVOL ≥ 1.2  
2. Impulse: ≥2 up bars, open→high ≥ 0.35%, hold above session VWAP  
3. Micro-pullback: 1–3 bars, no new impulse high, depth ≤ 55% of impulse range, lows ≥ VWAP  
4. Signal: green bar breaks pullback high (close > pb high), still above VWAP  
5. Entry: next bar open; stop under pb low − buffer; 1R half / 2R / EOD 15:55  

## Entry window

09:45–14:00 ET.

## Paper packaging

| Control | Default | Notes |
|---|---|---|
| NML gate | **OFF** | A/B: hurts this family |
| Portfolio | **ON** | max concurrent 3, max 5/day |
| Build | `python -m trading.llm_trader.strategies.micro_pullback.paper` | writes `batch/micro_pullback/paper/` |

Promotion: research / paper-optional only. Not live-sized.

## Warrior-universe probe (optional)

```bash
python3 -m trading.llm_trader.strategies.micro_pullback.probe_warrior \
  --start 2025-01-01 --end 2026-06-30
```

Uses Ross small-account gap screen + current-snapshot float (<20M). **Not** multi-year
sealed (no PIT float). Writes `batch/micro_pullback/warrior_probe/`. 2025–H1'26 probe
**FAIL** years+ gate — liquid paper book remains primary.
