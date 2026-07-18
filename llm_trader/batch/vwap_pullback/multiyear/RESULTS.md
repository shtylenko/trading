# VWAP pullback short-hold multi-year (v0.1.0)

**Universe:** 60 liquid large-caps. **Window:** 2022–2025.  
**Method:** 5m RTH path sim (entry next open after reclaim; stop / 1R-half / 2R / EOD).  
**Costs:** 1 bps fee + 2 bps slip each way.

## Gates (same bar as swing families)

| Gate | Result |
|---|---|
| Pooled effR > 0 | **PASS** (+0.024) |
| ≥2 of 4 years > 0 | **PASS** (3 of 4) |
| **Overall** | **PASS (thin edge)** |

**Pooled:** n=506 · win% 46.8 · **effR +0.0236** · pnl +$1,194  
**Exits:** STOP 266 · TARGET2 216 · EOD 24 (T1 is scale-half, not full exit)

| Year | n | win% | effR | pnl |
|---|---:|---:|---:|---:|
| 2022 | 133 | 45.9 | **+0.034** | +$456 |
| 2023 | 139 | 50.4 | **+0.027** | +$368 |
| 2024 | 112 | 42.9 | **−0.004** | −$46 |
| 2025 | 122 | 47.5 | **+0.034** | +$416 |

## Caveats

- Edge is **small** (~2–3¢ per $1 risk). Sensitive to costs/slippage.
- Offline 5m sim ≠ sealed 1m LLM batch path (not yet wired).
- Liquid large-caps only; no portfolio concurrency.
- Survived 2022 (unlike multi-day TA scanners) — interesting.

## Cost stress (same 506 entries)

See `COST_STRESS.md`. Summary:

| Scenario | slip | effR | pass |
|---|---:|---:|:---:|
| baseline (1f+2s) | 2 | **+0.024** | Y |
| 2× slip | 4 | **+0.004** | Y (barely) |
| 3× slip | 6 | **−0.016** | N |
| fee2+slip4 | 4 | **−0.006** | N |

**Verdict:** multi-year gate passes at baseline; **cost-fragile**. Survives 2× slip only marginally; fails 3× and modest fee+slip. **Do not promote to live size.** Research-only / paper-optional.

## Next (short-hold track)

1. Keep VWAP as **research baseline**, not production  
2. Build second short-hold (`bb_squeeze_long` or warrior micro-pullback) for diversification of *ideas*, not stacking capital on VWAP  
3. Only wire sealed paper path if something clears cost stress with margin
