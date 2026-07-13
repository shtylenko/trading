"""Persist screen outputs."""

from __future__ import annotations

from pathlib import Path

import pandas as pd


def write_candidates(df: pd.DataFrame, out_dir: str | Path, stem: str) -> Path:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"{stem}.parquet"
    df.to_parquet(path, index=False)
    # Small CSV sample for eyeballing (cap rows)
    csv_path = out / f"{stem}.csv"
    df.head(50_000).to_csv(csv_path, index=False)
    return path


def write_summary(df: pd.DataFrame, out_dir: str | Path, stem: str) -> Path | None:
    if df is None or df.empty:
        return None
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    tmp = df.copy()
    tmp["year"] = pd.to_datetime(tmp["asof_date"]).dt.year
    summary = (
        tmp.groupby(["year", "variant"], as_index=False)
        .agg(
            n_hits=("ticker", "size"),
            n_tickers=("ticker", "nunique"),
            n_days=("asof_date", "nunique"),
            median_rsi2=("rsi2", "median"),
            median_rsi14=("rsi14", "median"),
        )
        .sort_values(["year", "variant"])
    )
    path = out / f"{stem}.parquet"
    summary.to_parquet(path, index=False)
    summary.to_csv(out / f"{stem}.csv", index=False)
    return path
