"""Tests for CLI argument parsing and config construction."""

from __future__ import annotations

from datetime import date

import pytest

from trading.llm_trader.cli import build_parser, config_from_args
from trading.llm_trader.config import ScanConfig


def test_defaults():
    parser = build_parser()
    args = parser.parse_args([])
    cfg = config_from_args(args)
    assert cfg.start == date(2025, 1, 1)
    assert cfg.end == date(2026, 6, 30)
    assert cfg.account_profile == "small"
    assert cfg.price_min == 2.0
    assert cfg.float_max == 20_000_000


def test_profile_main_adjusts_bands():
    parser = build_parser()
    args = parser.parse_args(["--profile", "main"])
    cfg = config_from_args(args)
    assert cfg.price_min == 5.0
    assert cfg.price_max == 50.0


def test_explicit_overrides_after_profile():
    parser = build_parser()
    args = parser.parse_args(["--profile", "main", "--price-min", "3", "--float-max", "0"])
    cfg = config_from_args(args)
    assert cfg.price_min == 3.0  # explicit wins
    assert cfg.float_max is None  # 0 disables


def test_symbols_and_max_symbols_pass_through():
    # These are handled in runner, but parser accepts them
    parser = build_parser()
    args = parser.parse_args(["--max-symbols", "10", "--symbols", "AAOI", "STEM"])
    assert args.max_symbols == 10
    assert args.symbols == ["AAOI", "STEM"]


def test_gap_rvol_overrides():
    parser = build_parser()
    args = parser.parse_args(["--gap-min", "7.5", "--rvol-min", "3.0"])
    cfg = config_from_args(args)
    assert cfg.gap_min_pct == 7.5
    assert cfg.rvol_min == 3.0
