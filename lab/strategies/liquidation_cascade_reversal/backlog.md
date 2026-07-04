# l01 — Liquidation Cascade Reversal

**Status:** Proposed. Medium priority.

**Research thesis (Moon Dev):**
"Liquidations drive the market. Price moves between liquidation levels." Moon Dev
tracked 5,000 whale wallets on Hyperliquid and found 75% of the biggest traders
eventually blow up. After a large liquidation cluster, price tends to reverse or
cascade further. For stocks, the equivalent is **extreme volume + wide-range bars**
that signal capitulation.

**Entry rules:**
- Detect bars where volume Z-score > 2.0 AND range (high−low)/ATR14 > 1.5
  (capitulation / exhaustion proxy).
- Entry in the opposite direction of the move that triggered the bar.
- VIX spike filter: only trade when VIX > 20 (elevated volatility regime).

**Exit rules:**
- Target: SMA(20) for the reversal target (mean reversion target).
- Stop: beyond the extreme bar's high/low + 0.5 × ATR14 buffer.
- Time exit: 15:55.

**Impact: medium.** Partially overlaps with f01 (dominance flip) which already
detects capitulation via SMA stretch. l01 is a simpler, volume-based alternative
without the RSI divergence requirement.

**Cost: low.** Uses existing bars. Volume Z-score is a one-line calculation.

**Pitfalls:**
- High overlap with f01 — may not add independent edge.
- Without per-wallet liquidation data (crypto-specific), the stock version is a
  proxy, not the real thing.

## Sequencing (new families)

1. **m01** — highest priority, fill the mean-reversion gap immediately after
   the o03 trust phase (A1–A3) completes. The data exists, the code is simple,
   and the regime complementarity with ORB is compelling.
3. **l01** — lowest priority among the three. Test as a fast ablation (2-hour
   script) to measure overlap with f01 before committing to a full release.
