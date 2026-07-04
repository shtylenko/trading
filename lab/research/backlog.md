# Research / Meta Tools — Backlog

Updated 2026-06-12.

## g01 — Genetic Algorithm Parameter Optimizer

**Status:** Proposed. Not a strategy — a research tool.

**Research basis (Moon Dev):**
Genetic algorithms inspired by Darwinian evolution — population of candidate
strategy parameter sets, tournament selection, crossover (combine params from
two fit parents), mutation (random param tweaks), iterate for N generations.
19K chars of transcribed deep-dive. Moon Dev used this to find strategy
parameters that grid search and coordinate ascent would miss.

**What it replaces:**
- Coordinated-ascent sweeps (`--sweep`) which are greedy along one axis.
- Grid sweeps (`--grid-sweep`) which are exponential in N parameters.

**Implementation sketch (`research/genetic_optimizer.py`):**

```
generation 0: random_init(population=100)
for gen in 1..N:
    fitness = [backtest(strategy, params).sharpe for params in population]
    selected = tournament_select(population, fitness, top_k=20)
    offspring = crossover(selected) + mutate(selected)
    population = offspring
return best_params(population, fitness)
```

Search space: SMA period [5..50], deviation [0.005..0.05], stop_mult [0..3],
entry_window ['intraday', 'close'] → ~6D space that grid search cannot
exhaustively cover. GA finds good regions in ~50 generations × 100 pop = 5,000
backtests (same budget as a coarse grid).

**Impact: medium-high.** Accelerates all strategy development. The GA can find
parameter combos that greedy search misses.

**Cost: moderate.** ~150 LOC for the optimizer. Needs a wrapper that calls the
existing backtest pipeline per individual. Requires careful fitness function
(multiple objectives: Sharpe, CAGR, maxDD, trade count).

**Pitfalls:**
- Overfitting risk: GA can over-optimize to noise if the fitness function is
  not regularized. Must use out-of-sample validation.
- Fitness function needs to balance return (Sharpe) with robustness (trade count,
  consistency across regimes).
- Caching: consecutive generations share many individuals; implement a backtest
  cache to avoid redundant work.

## Sequencing (new families)

1. **m01** — highest priority new strategy.
2. **g01** — implement after m01 is running. Will accelerate all subsequent
   strategy parameterization.
3. **l01** — lowest priority among the three.
