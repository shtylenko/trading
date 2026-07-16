# cup_handle skill changelog

| version | date | decision | notes |
|---|---|---|---|
| 0.1.0 | 2026-07-15 | baseline | Initial plan-first multi-day skill: ATR 1.5× stop, dual cup-depth targets, ARM_BUY_STOP at handle high. |
| 0.2.0 | 2026-07-16 | process | From BNY pilot: (1) scanner date is not wait-to-arm — arm when checklist passes mid-lookback; (2) ARM fills only on later bars — if close already > handle high use ENTER_CLOSE; (3) SMA200 soft when null; (4) handle length guidance; (5) no re-entry after engine stop. |
