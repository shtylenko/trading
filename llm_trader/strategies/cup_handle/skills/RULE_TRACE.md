# RULE_TRACE — cup_handle family

| rule id | skill location | type | note | since |
|---|---|---|---|---|
| plan.uptrend_sma_stack | ENTRY checklist §1 | operationalization | close > SMA20/50; SMA200 preferred if present, soft-skip if null; SMA50 rising | 0.1.0 / 0.2.0 soft-200 |
| plan.cup_geometry | ENTRY checklist §2 | operationalization | depth 12–35%, multi-bar trough, lips within 5% | 0.1.0 |
| plan.handle_tight | ENTRY checklist §3 | operationalization | short shallow handle under lip (~3–15 sessions preferred), light volume | 0.1.0 / 0.2.0 |
| plan.room_to_run | ENTRY checklist §4 | operationalization | no stacked supply just above handle high | 0.1.0 |
| plan.arm_when_ready | scanner date vs arm | process | arm mid-lookback when checklist passes; scanner date is not wait-to-arm | 0.2.0 |
| entry.break_handle_high | ARM_BUY_STOP | direct | buy when price breaks handle high on a *later* bar | 0.1.0 |
| entry.already_broken | ENTER_CLOSE | process | if close already > handle high on plan bar, ENTER_CLOSE not ARM | 0.2.0 |
| stop.atr_1_5 | plan numbers | direct | stop = entry − 1.5×ATR(14) (“Baby Bear”) | 0.1.0 |
| target.dual_cup_depth | T1/T2 | operationalization | T1=50% measured move half-off; T2=80% | 0.1.0 |
| size.dollar_risk | engine | sim-constraint | shares from risk_budget / stop_distance | 0.1.0 |
| manage.no_reentry_after_stop | MANAGE §1 | process | engine stop → flat; no re-entry same setup | 0.2.0 |
| manage.never_abandon | MANAGE loop | process | keep reveal/resolve/log while armed or in position until flat/STAND_DOWN/STATUS end | 0.3.0 |
| entry.breakout_quality | ENTER_CLOSE gate | direct | green close above handle high AND (rvol null or ≥1.3); else OBSERVE/ARM only | 0.4.0 |
| plan.handle_length_hard | ENTRY checklist §3 | operationalization | handle 3–15 sessions hard fail | 0.4.0 |
