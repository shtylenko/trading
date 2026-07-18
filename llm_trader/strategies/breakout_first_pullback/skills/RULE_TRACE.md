# breakout_first_pullback RULE_TRACE

| rule id | location | source | type | since |
|---|---|---|---|---|
| entry.base_breakout | patterns | Lance swing #2 | operationalization | 0.1.0 |
| entry.first_retest | patterns | Lance "buy first pullback" | operationalization | 0.1.0 |
| stop.pullback_low | features.stop_px | structure invalidation | operationalization | 0.1.0 |
| target.swing_measured | T1/T2 | prior swing + base height | operationalization | 0.1.0 |
| arm.causal_only | skill | platform contract | sim-constraint | 0.1.0 |
| entry.trigger_breakout_level | entry_trigger_mode | less chase vs 0.1.0 | structural | 0.2.0 |
| filter.sma200_name_spy | require_above_sma200 + spy | cut 2022 false breaks | structural | 0.2.0 |
| filter.stronger_breakout | vol 1.5 + clear 0.30 | quality BO | structural | 0.2.0 |
| filter.pullback_vol_dry | tag vol < BO vol | quieter retest | structural | 0.2.0 |
