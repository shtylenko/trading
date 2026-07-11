# Trading Skill Profitability & Fidelity Analysis

## Bottom line

Yes—the v3.0.0 implementation is materially different from Ross Cameron’s documented process. It captures parts of his risk management and ACD vocabulary, but it does not reproduce his stock selection, information set, trading hours, entry timing, scaling, market-regime adaptation, or day-level position sizing.

The biggest issue is not a bad MACD threshold or an imperfect candle rule. It is that the simulator is evaluating a simplified, regular-hours, partially hindsight-selected version of the strategy. Fix data validity and strategy fidelity before optimizing more thresholds.

The intended control should be v3.0.0, but the repository is inconsistent: unpinned runs still resolve to v2.4.1 in `skills/skill_versions.json`. Until reconciled, unpinned runs can silently test the obsolete frictionless model.

## What v3.0.0 actually achieved

For batch `3.0.0-20260710201028`, using 100 unique regular-hours setups:

| Metric | Result |
|---|---:|
| Presented setups | 100 |
| Trades | 93 |
| Win rate | 37.6% |
| Net P&L | $988.08 |
| Effective expectancy | +0.247R/setup |
| Average winner | +$44.59 |
| Average loser | -$9.87 |
| Winner/loser ratio | 4.5:1 |

This is profitable, but its statistical signature is unlike the Ross corpus: approximately 1:1 average winner/loser and >50% accuracy. That difference is strong evidence that this is a different strategy, not merely a weaker implementation of the same one.

A second run of the identical version/model/set produced $751.42 and +0.188R. Comparing the two identical-version runs gave -0.059R mean difference, with several large stochastic divergences. The LLM is still a major uncontrolled strategy variable.

Execution costs explain a large part of the apparent gap:

| Execution assumptions | Win rate | Effective R | P&L |
|---|---:|---:|---:|
| Recorded v3 assumptions | 37.6% | +0.247 | $988 |
| No commission | 37.6% | +0.294 | $1,178 |
| No slippage | 45.2% | +0.325 | $1,300 |
| Fully frictionless | 65.2% | +0.468 | $1,854 |

The model currently charges 10 bps each way, $0.005/share each way, rounds buys adversely up to the next cent, and limits participation to 10% of bar volume. Those assumptions may be reasonable or excessive depending on the actual broker, order type, spread, and liquidity; calibrate them from real fills.

Warrior Trading’s own disclaimer says Ross’s results are not typical and that some published gross figures can exclude commissions and other costs. Matching headline dollars is therefore not a defensible acceptance criterion. Compare net expectancy and drawdown under the same capital, broker, hours, and execution assumptions.

## Major differences from Ross’s documented strategy

| Area | Ross corpus | Current v3 behavior | Assessment |
|---|---|---|---|
| Catalyst | Required pillar | No news filter; gap/RVOL used as proxy | Major missing edge |
| Trading hours | 7:00–9:30 described as best | Backtest builder defaults to >=09:30 | Major mismatch |
| Entry chart | 5-minute primary | LLM decides mainly on 1-minute bars | Different strategy dialect |
| Entry timing | Buy immediately over trigger | Often enters at a confirmed 1-minute close | Later, more expensive |
| Stop | Low of actual pullback/consolidation | `min(trigger low, prior low) - $0.01` | Approximation, often different |
| Market regime | Hot/cold drives selection and size | No market-regime state | Missing |
| Scaling in | Central edge; starter then adds | Initial entry uses full risk; only 2/93 trades added | Essentially absent |
| Icebreaker | Begin at 25% size, increase after profits | Every setup independently risks $40 | Missing |
| Daily controls | Daily stop, giveback limit, consecutive-loss rules | No multi-trade daily portfolio | Missing |
| Level II/tape | Used to assess support/resistance and break quality | OHLCV only | Missing information |
| Setup families | ACD, micro-pullback, VWAP, washout, short squeeze, news | Scanner produces one ACD/ORB setup/day | Narrow subset |
| Re-entry | Permitted on a fresh second setup | Control batch used `reentry: false` | Disabled |
| Execution | Direct/marketable orders, broker-specific fills | Deterministic adverse OHLC model | Different assumptions |

## Critical validity problems

These should be resolved before trusting further profitability tuning.

### 1. Daily RVOL uses future volume

The scanner calculates `rvol = full trading-day volume / prior 20-day average`. A 09:35 trade is selected using volume accumulated after 09:35, possibly through 16:00.

**Mitigation:** calculate as-of RVOL using cumulative volume through the signal time divided by the historical expected cumulative-volume curve for that time of day.

### 2. Premarket selection uses the later regular-session open

Gap and price filters use the daily bar’s open, normally the 09:30 open. But 428 of the 567 database setups occur before 09:30. Those trades are being selected using a future price.

**Mitigation:** use the current premarket price at each evaluation timestamp versus the prior close.

### 3. The 5-minute qualifying bar leaks into the beginning of its replay

The scanner determines that a complete 5-minute bar broke out, closed green, had sufficient volume, and closed above VWAP. Replay then starts at that bar’s timestamp, and metadata already describes the successful 5-minute bar.

If a 09:35 bar represents 09:35–09:39, the agent at 09:35 has been told facts from the next four minutes.

**Mitigation:** reveal 10–20 minutes of pre-signal context and detect the breakout online. Either act on the intrabar trigger or wait until the 5-minute close and timestamp the decision at 09:40.

### 4. Scanner and replay use different sessions

The scanner analyzes extended-hours bars. JSON replay filters to regular hours before calculating VWAP, MACD, and session highs. Premarket structure therefore affects scanner selection but disappears from the trading indicators.

**Mitigation:** define one session policy and use identical causal indicators in scanner, backtest, and live execution.

### 5. Current float and universe create historical bias

Historical setups use today’s float and today’s listed-symbol universe. Offerings, reverse splits, dilution, delistings, and bankruptcies can materially change both.

**Mitigation:** use a point-in-time security master and point-in-time shares/float. Until then, label results “recent-snapshot research,” not historical validation.

These leaks mostly make results look better, not worse. Fixing them may initially reduce reported profitability, but it establishes a baseline worth improving.

## Highest-priority profitability mitigations

### 1. Add real catalyst selection

Ross’s canon says news is required, while the current skill scores only four measurable pillars.

Build a timestamped catalyst layer:

- Historical headlines available before the entry.
- Catalyst category and novelty.
- Offering/dilution, reverse-split and going-concern exclusions.
- Recent IPO, short interest and borrow/squeeze context.
- LLM used only to classify the headline—not to select prices or manage bars.

This is probably the highest-alpha missing feature.

### 2. Test the actual premarket strategy

The database contains 428 premarket setups and 139 regular-hours setups, but the batch builder excludes anything before 09:30 by default. Ross’s corpus calls 07:00–09:30 the best period.

Create a separate premarket cohort with realistic:

- Premarket spreads and depth.
- Lower liquidity/participation limits.
- Halt and gap-through-stop behavior.
- Extended-hours VWAP and volume profiles.

Do not simply merge premarket with RTH; the microstructure is different.

### 3. Add hot/neutral/cold market state

The skill says B setups can be traded, but it has no way to determine whether the tape is hot. In the control, 65 setups were B-grade and 60 were traded.

Compute each morning:

- Number of stocks +20%, +50%, and +100%.
- Median follow-through of recent gappers.
- Breakout success rate over the prior 5–20 sessions.
- Aggregate small-cap dollar volume.
- Breadth and volatility regime.

Then apply Ross-like behavior: A-only and reduced risk in cold markets; broader selection and scaling in hot markets.

### 4. Rebuild entry logic around the 5-minute setup

The current skill starts at the known breakout and often enters at a close. Ross watches the base form and arms the break.

Use a deterministic state machine:

1. Detect pullback/consolidation on completed 5-minute bars.
2. Identify the exact trigger and structural pullback low.
3. Submit a next-tick or next-bar buy-stop.
4. Use 1-minute/tick data only for execution refinement.
5. Reject a chase when slippage-adjusted reward to resistance is inadequate.

In the control, close entries returned +0.289R versus +0.145R for armed entries, even though Ross prefers immediate break entries. That likely says the current arming architecture is poor—not that buying breakouts is inferior.

### 5. Implement scaling as an actual position plan

Ross describes scaling into winners as a central edge. The engine initially consumes the full risk budget, despite the skill calling it a one-third starter. Only two control sessions added, and both lost.

Implement:

- Initial starter using roughly one-third of permitted risk/size.
- Add #2 only after the break holds.
- Add #3 only on renewed acceleration.
- Total worst-case open risk capped throughout.
- Hot-market and liquidity gates for pyramiding.

Separately, 30 of 56 scale intents in v3.0 were submitted only after the target had traded. The one-intent-per-bar design forces the agent to choose between moving its stop and placing a scale order. The fixed +1R/+2R bracket in v3.1 was tested and rejected, so do not retry it unchanged. Instead allow compound management intents—e.g. update stop and maintain independent resistance-based orders simultaneously.

### 6. Calibrate execution from the actual broker

Do not make the simulator frictionless just to improve results. Collect actual fills and fit:

- Slippage versus spread, price, time, order size and bar participation.
- Fill probability for ask-offset limit orders.
- Partial fills.
- Premarket versus RTH behavior.
- Halt reopen gaps.
- Actual commissions, regulatory fees and routing rebates.

The current execution assumptions consume roughly half the simulated edge. FINRA notes that “commission-free” does not mean cost-free and that volatile market orders can execute materially away from quotes.

### 7. Replace LLM bar-by-bar discretion with deterministic rules

Two identical v3.0 batches differed by -0.059R, and a few setups drove much of the change. Use code for:

- Entry predicates.
- Stop placement.
- Order lifecycle.
- Scaling.
- Exit priority.
- Daily risk state.

Reserve the LLM for catalyst interpretation, unusual filings, and post-trade explanation. This should reduce cost, variance, and prompt-induced behavioral drift.

## Additional fixes

- Redefine MFE capture over periods when the strategy was actually in the position. Current MFE scans every later bar through session end; 86 of 93 trades had a higher post-exit peak, and full-day MFE was a median 3.45x the in-trade MFE. This makes management look worse than it was and encourages overholding.
- Treat `EXIT_CLOSE` as a persistent liquidation order until flat. It currently sells only up to that bar’s participation capacity.
- Add halt/LULD behavior, spreads and NBBO data; OHLC alone is especially weak for low-float momentum names.
- Test washout/VWAP-reclaim, micro-pullback, flat-top, and short-squeeze families separately.
- Add a full daily portfolio simulation: icebreaker sizing, compounding, daily max loss, three-loss stop, profit giveback, and daily goal.
- Keep the tentative `<$3` and post-11:00 exclusions as research strata, not promoted rules. Both were negative in two v3 control replays, but v3.2’s hard filter was rejected: -0.069R paired delta and 31 stand-downs versus 7.

## Recommended experiment order

1. Make v3.0.0 the explicitly pinned control everywhere; reconcile the stale base pointer and experiment log.
2. Build an event-time-clean dataset with causal gap/RVOL, correct signal timestamps, pre-roll, and identical scanner/replay indicators.
3. Establish walk-forward periods and a locked unseen holdout. Cluster inference by trading day and ticker.
4. Calibrate execution against real broker fills.
5. Add catalyst filtering.
6. Add premarket as a separate strategy cohort.
7. Add market-regime and daily portfolio state.
8. Test 5-minute armed entry versus confirmed-close entry.
9. Test starter/add scaling using compound order intents.
10. Only then optimize secondary candle, MACD, price-band, and late-time thresholds.

For every change, report net expectancy per opportunity and per day, drawdown, profit factor, average winner/loser, fill rate, turnover, cost sensitivity, stood-down rate, and risk of ruin—not merely win rate or total P&L.

The package is technically healthy—143 tests pass—but those tests verify that the implemented mechanics behave as coded. They do not establish point-in-time validity or Ross-strategy fidelity.

## External sources

- [Warrior Trading verified earnings and disclaimer](https://www.warriortrading.com/verified-earnings-2026/)
- [SEC: Day Trading—Your Dollars at Risk](https://www.sec.gov/about/reports-publications/investorpubsdaytipshtm)
- [FINRA: Questions about online trading](https://www.finra.org/investors/insights/questions-about-online-trading)
