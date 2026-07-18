# trend_pullback skill changelog

| version | date | decision | notes |
|---|---|---|---|
| 0.1.0 | 2026-07-18 | baseline | Causal EMA20 reclaim pullback; deterministic auto-arm; T1 prior high / T2 measured move. Smoke: too many setups (524/15 names), −0.4R on 8 trades — admission too loose. |
| 0.2.0 | 2026-07-18 | admission | True EMA tag (low≤EMA), require close≤EMA in window, depth 4–18%, max ext 4%, cooldown 12, SPY>SMA50. Same execution policy. n30 effR −0.19 — not edge. |
| 0.3.0 | 2026-07-18 | construction | Freeze 0.2.0 admission. Trigger = reclaim **close** (not high); T1/T2 = **1R/2R** from stop (not prior-high structure). **n30 result: worse than 0.2.0** (effR −0.29 vs −0.19, win% 36 vs 46). Hypothesis rejected; keep 0.2.0 as research baseline. |
| 0.4.0 | 2026-07-18 | orthogonal | SMA50 + 0.2 construction. n30 A/B positive (+0.09/+0.07). **Multi-year 2022–25 FAIL:** pooled effR −0.02; years −0.09/−0.17/+0.08/0.00. **Park family.** |
