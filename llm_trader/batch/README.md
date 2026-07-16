# Batch holdouts (per strategy)

Each strategy family keeps its own testsets:

```text
batch/
  warrior/       # Ross Cameron day-trade holdouts
  cup_handle/    # cup-and-handle swing holdouts
```

```bash
# build default testset.json for a family
python3 -m trading.llm_trader.batchsim build-set --strategy warrior --n 30
python3 -m trading.llm_trader.batchsim build-set --strategy cup_handle --n 30 --unique-ticker

# run against an explicit set
python3 -m trading.llm_trader.batchsim run \
  --strategy cup_handle --version 0.1.0 \
  --set trading/llm_trader/batch/cup_handle/testset_30.json \
  --model <model>
```

Do not mix warrior and cup_handle setups in one file or one batch compare.
