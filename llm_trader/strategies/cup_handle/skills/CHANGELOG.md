# cup_handle skill changelog

| version | date | decision | notes |
|---|---|---|---|
| 0.1.0 | 2026-07-15 | baseline | Initial plan-first multi-day skill: ATR 1.5× stop, dual cup-depth targets, ARM_BUY_STOP at handle high. |
| 0.2.0 | 2026-07-16 | process | From BNY pilot: (1) scanner date is not wait-to-arm — arm when checklist passes mid-lookback; (2) ARM fills only on later bars — if close already > handle high use ENTER_CLOSE; (3) SMA200 soft when null; (4) handle length guidance; (5) no re-entry after engine stop. |
| 0.3.0 | 2026-07-16 | process | Never abandon live ARM/in-position: keep step next until flat / STAND_DOWN / STATUS end; place T1 after fill. Harness flags agent_abandoned for resume. |
| 0.4.0 | 2026-07-16 | edge | SPEC-aligned breakout quality: ENTER_CLOSE only if green close above handle high and rvol≥1.3 when present; hard handle 3–15 sessions; prefer ARM_BUY_STOP. Paired with batch auto-lookback OBSERVE + slim runtime prompt. |
| 0.5.0 | 2026-07-16 | safety rebaseline | Base for causal paper simulation: scanner date is the completed-handle plan date; do not arm before it and prohibit daily same-bar `ENTER_CLOSE`. Adds enforced plan binding, gap guard, arm expiry, and fail-closed daily-indicator completeness. It has no profitability claim; require a fresh causal walk-forward cohort before live consideration. |
