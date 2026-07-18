# Maintaining trend_pullback skills

Same mechanics as `cup_handle` / warrior, scoped to this family:

```bash
python3 -m trading.llm_trader.batchsim current --strategy trend_pullback
python3 -m trading.llm_trader.batchsim new-version --strategy trend_pullback --from 0.1.0 --to 0.2.0
python3 -m trading.llm_trader.batchsim run --strategy trend_pullback --version 0.1.0 \
  --set trading/llm_trader/batch/trend_pullback/testset_smoke.json --tag tp-smoke
```

Never edit a sealed version in place.
