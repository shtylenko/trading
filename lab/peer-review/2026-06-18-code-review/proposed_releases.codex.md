# Proposed New Releases From 2026-06-18 Codex Audit

Release files are immutable, so these are successor-release proposals rather than in-place edits.

## `o12` or later: ML artifact date-gated ORB
- Supersedes risky `o03`/`o10` ML behavior.
- Require model artifact metadata: `train_start`, `train_end`, feature schema hash, policy name.
- For `trade_date <= train_end`, fail closed or use a clearly signed RV fallback with per-candidate `ranking_mode`.
- Include artifact bytes and metadata in `signature_inputs()`.

## `d16`: strict PIT sector-gated post-gap drive
- Supersedes `d12` sector fallback behavior.
- Vendor or reference a frozen, effective-dated sector map artifact.
- Include map bytes in `signature_inputs()`.
- If a ticker is mapped to a sector ETF but the ETF history is missing/short, skip/log the ticker instead of falling back to SPY.
- SPY fallback is allowed only for explicitly unmapped tickers and should be recorded in candidate features.

## `x04`: residual momentum with verified formation window
- Supersedes `x03` if `x03` is intended to reproduce the pre-registered offline residual-momentum result.
- Match the offline window exactly or document the changed definition and rerun validation from scratch.
- Declare `spy_daily_lookback_days` explicitly even though the swing runner now hydrates SPY using the larger daily lookback.

## `f08`: context-only dominance flip uptrend gate
- Supersedes old `f02`/variant paths that fetch SPY directly or silently degrade on missing warm-start data.
- Read only `context.spy_daily` and declare the required lookback.
- For warm-start releases, fail closed when `historical_5m` is missing/short and add a split-scale guard before concatenating raw historical and current 5m bars.

## `s02`: split-guarded SMMA/ATR breakout
- Supersedes `s01` for cross-day raw historical seed usage.
- Reject split/glitch windows with `has_split_like_jump(..., open_price=first_open)` before computing SMMA/ATR on raw data, or switch the cross-day seed path to split-continuous inputs consistently.
