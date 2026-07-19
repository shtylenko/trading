# In-play continuation — SPEC v0.1.0 (Opp C)

**Thesis:** Gap / in-play names; opening impulse → shallow VWAP-held pullback → green break.  
**Broker:** WeBull long equity ($0 commission; sell regulatory; **slip 15 bps** baseline).  
**Pre-reg:** `batch/inplay_continuation/PREREG_v010.md`

## Rules

See PREREG. Causal prior-day RVOL. Window ~12m only (float caveat).

## Run

```bash
python3 -m trading.llm_trader.strategies.inplay_continuation.runner \
  --start 2025-07-01 --end 2026-06-30
```
