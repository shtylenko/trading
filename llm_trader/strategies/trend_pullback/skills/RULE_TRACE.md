# trend_pullback RULE_TRACE

| rule id | skill / scanner | source | type | since |
|---|---|---|---|---|
| entry.reclaim_ema20 | patterns + scanner_plan | Lance swing #1 / Qullamaggie MA pullback | direct operationalization | 0.1.0 |
| entry.true_tag_ema | touch_tol_pct=0 | 0.1.0 smoke: wick tags too noisy | empirical guardrail | 0.2.0 |
| entry.body_dip | require_close_below_ema | avoid wick-only dips | empirical guardrail | 0.2.0 |
| entry.depth_band_4_18 | pullback_depth_* | 0.1.0 2–25% too shallow/noisy | empirical guardrail | 0.2.0 |
| entry.spy_sma50 | require_spy_above_sma50 | single regime lever | operationalization | 0.2.0 |
| entry.cooldown_12 | min_bars_between_arms | cut multi-arm spam per name | empirical guardrail | 0.2.0 |
| stop.pullback_low | features.stop_px | Lance: invalidation under pullback | operationalization | 0.1.0 |
| target.prior_high_measured | T1/T2 | Lance measured move / prior high | operationalization | 0.1.0 |
| arm.causal_only | skill frontmatter | cup_handle platform contract | sim-constraint | 0.1.0 |
| entry.trigger_reclaim_close | entry_trigger_mode | 0.2.0 chase at high hurt fills | empirical construction | 0.3.0 |
| exit.risk_rr_1_2 | target1_mode=risk_r | fixed RR vs structure targets | empirical construction | 0.3.0 |
| entry.pullback_sma50 | pullback_ma=sma50 | last orthogonal level vs crowded EMA20 | direct Lance swing | 0.4.0 |
