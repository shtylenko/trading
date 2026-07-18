# Structural A/B — No Man's Land + portfolio limits

**Pre-reg:** `batch/admission/PREREG.md` (frozen before results).
**NML:** `nml_v0.1.0` lookback=24 mid=(0.3,0.7) upper≥0.7 breakout_close≥0.6
**Portfolio:** `port_v0.1.0` max_concurrent=3 max_per_day=5

Gates: pooled effR>0 and ≥2/4 years>0. Same sealed multi-year entries + path sim.

## Results

### micro_pullback

Sealed sims: **1102** · NML keep rate: **64.8%** (rejected 388)

| Variant | n | win% | effR | years+ | pass |
|---|---:|---:|---:|---:|:---:|
| `baseline` | 1102 | 46.2 | **+0.0292** | 4/4 | Y |
| `nml_only` | 714 | 43.6 | **+0.0056** | 3/4 | Y |
| `portfolio_only` | 972 | 46.5 | **+0.0315** | 4/4 | Y |
| `nml_plus_portfolio` | 652 | 44.3 | **+0.0094** | 3/4 | Y |

| Year | base n | base effR | nml n | nml effR |
|---|---:|---:|---:|---:|
| 2022 | 290 | +0.0396 | 196 | +0.0198 |
| 2023 | 294 | +0.0270 | 183 | +0.0123 |
| 2024 | 263 | +0.0332 | 180 | +0.0088 |
| 2025 | 255 | +0.0156 | 155 | -0.0240 |

### vwap_pullback

Sealed sims: **506** · NML keep rate: **18.0%** (rejected 415)

| Variant | n | win% | effR | years+ | pass |
|---|---:|---:|---:|---:|:---:|
| `baseline` | 506 | 46.8 | **+0.0236** | 3/4 | Y |
| `nml_only` | 91 | 34.1 | **-0.0381** | 1/4 | N |
| `portfolio_only` | 494 | 47.2 | **+0.0256** | 3/4 | Y |
| `nml_plus_portfolio` | 91 | 34.1 | **-0.0381** | 1/4 | N |

| Year | base n | base effR | nml n | nml effR |
|---|---:|---:|---:|---:|
| 2022 | 133 | +0.0343 | 22 | -0.0317 |
| 2023 | 139 | +0.0265 | 27 | -0.0812 |
| 2024 | 112 | -0.0041 | 20 | -0.0372 |
| 2025 | 122 | +0.0341 | 22 | +0.0077 |

## Verdict (vs pre-reg success criteria)

### No Man's Land (`nml_v0.1.0`)

| Family | Keep? | Why |
|---|---|---|
| `micro_pullback` | **No as default gate** | Still passes, but effR **+0.029 → +0.006** (Δ −0.024 ≫ 0.005 tolerance). Edge mostly destroyed while cutting ~35% of trades. |
| `vwap_pullback` | **Hard no** | **FAIL** gates (effR −0.038; 1/4 years). VWAP reclaim is often *structurally mid-range* — NML and the setup thesis conflict. |

**Interpretation:** Lance NML is real advice for discretionary range-chop, but as a mechanical filter on *these two* sealed short-holds it does not improve EV. Do **not** enable `nml_gate=True` on paper path for VWAP; optional research-only on micro is not recommended.

### Portfolio concurrency (`port_v0.1.0`)

| Family | Keep? | Why |
|---|---|---|
| `micro_pullback` | **Yes (packaging)** | n 1102→972; effR **+0.029 → +0.032**; still **4/4** pass. Harmless risk packaging. |
| `vwap_pullback` | **Yes (packaging)** | n 506→494; effR **+0.024 → +0.026**; still **3/4** pass. |

Portfolio limits do not create edge; they prevent unrealistic all-names concurrency. Use for any paper/live packaging of the research baselines.

### Combined

`nml_plus_portfolio` inherits NML damage (micro thin pass; VWAP fail). Prefer **`portfolio_only` packaging on ungated baseline**.

## What we will not do

- Retune `mid_lo` / `mid_hi` / `upper_edge_frac` on this result set
- Force NML onto VWAP because "Lance said so"
- Stack NML + detector retunes to recover effR

## Code

- `trading/llm_trader/admission/no_mans_land.py`
- `trading/llm_trader/admission/portfolio.py`
- `trading/llm_trader/admission/structural_ab.py`
- Optional `nml_gate` on micro/VWAP configs (default **False**)

