# Self-review — swing engine path (Claude, Opus 4.8)

My own adversarial read of the code I just wrote, to sit alongside the other models'.
Ordered by how much I'd want a second opinion.

## Things I believe are correct (but want confirmed)

- **No selection leak.** `_run_swing_session` builds `ctx_daily` as `b[b.index <= rebal_ts]`,
  and `build_candidates`/`build_signal` read only `context.daily`. The forward bars live
  only in `bars` (passed to `simulate_daily_hold` to realize the hold). I can't find a
  path where future data reaches ranking or entry. The momentum index
  `c.iloc[-22]/c.iloc[-253]` on a `<= d` slice = `close[d-21]/close[d-252]` — correct.
- **Additivity.** The intraday engine is untouched: new `simulate_daily_hold`, a new
  `SwingStrategyRelease` subclass (no edit to `StrategyRelease`), a new runner module,
  one CLI branch keyed on `is_swing`. 306 tests pass. Low blast radius.
- **Already hardened one latent bug:** `idx.get_loc` returns a Python `int` on the
  (deduped, unique) index, but I widened the guard to accept `np.integer` too — a
  wrong-type rejection there would have silently produced ZERO trades. Worth a look.

## Real concerns I have (rank-ordered)

1. **Cost-model mismatch — the #1 comparison hazard.** The offline result (+3.98%/period
   net) charged a flat **10 bps round-trip**. The engine default `ExecutionConfig` is
   2+2 bps slippage + 0.5 bps/side fees ≈ **5 bps round-trip**, baked into fills. So the
   engine will print a HIGHER net return than the offline — and if I'm not careful I
   could misread that as "didn't reproduce" or, worse, as confirmation when the real
   issue is just different costs. **Fix before running:** set the engine cost to match
   the offline 10 bps (e.g. slippage 4+4 + fees ~1/side, or compare engine GROSS to the
   offline gross). I should run BOTH (matched-cost and gross) and compare like-for-like.

2. **Same-bar decide-and-execute (MOC optimism).** Entry uses `close(d)` — the same close
   that determines eligibility and (via the −252..−21 window) the rank. Realistic only if
   you can place a market-on-close order using close-time information, which you can't
   perfectly. It's consistent with the offline rule (so the cross-check is fair), but it's
   an optimism baked into BOTH; neither catches it. Worth stating as a known limitation,
   not a divergence.

3. **End-of-range silent drops.** Late-2025 rebalances without a full 20-day forward
   window return `None` and vanish with no session/trade row. Not a leak, but it (a) makes
   the trade count quietly smaller than expected and (b) could bias if the dropped tail is
   non-random (it's just "latest periods"). Should at least log how many were dropped.

4. **Phase/universe differences vs the offline.** Offline used `all_days[::20]` over the
   eligible-name-day grid; engine uses `trading_days[::cadence]` per range with PIT
   membership per rebalance date. Different phase + slightly different universe handling →
   I expect a few-percent difference in the aggregate even with matched costs, like the
   d-family's ~12% ledger-vs-engine gap. I should NOT expect bit-identity and should set
   that expectation before reading the result (so I don't rationalize either way).

5. **`realized_r` is nominal.** The 10%-below-entry stop is arbitrary (R-scaling only;
   `use_close_stop=False` so it never triggers). Fine for this strategy since pnl_pct is
   the metric, but anyone reading `realized_r` on these trades should know it's not a real
   risk unit. Documented in x01, but easy to misuse downstream (funnel R-based gates).

6. **Auto-lifecycle on a swing run.** I call `_auto_evaluate_lifecycle` after the swing
   run. The funnel thresholds were tuned for intraday R; a swing release landing in the
   funnel could get a misleading disposition. Low stakes for a one-off cross-check, but
   flag it.

## My recommendation

Do NOT run 2025 until the **cost model is matched** (concern #1) — otherwise the headline
comparison is apples-to-oranges. Once matched: run it, expect direction + magnitude
agreement (net positive, Sharpe ≈ 0.9–1.1, premium ≈ +2–3%), NOT bit-identity, and read a
few-percent gap as phase/universe/cost-granularity, not a bug. If the engine result is
NEGATIVE or the premium vanishes, that's a real divergence to hunt (most likely suspect:
a universe/PIT mismatch or an entry-date off-by-one in `simulate_daily_hold`). I consider
the leak surface clean but explicitly want the other models to attack concern #1, the
`<= rebal_ts` slice, and the `simulate_daily_hold` indexing.
