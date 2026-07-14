from __future__ import annotations

from importlib import import_module

RELEASES = {
    "o01": "trading.lab.strategies.stocks_in_play_orb.o01:Release",
    "o02": "trading.lab.strategies.stocks_in_play_orb.o02:Release",
    "o03": "trading.lab.strategies.stocks_in_play_orb.o03:Release",
    "o04": "trading.lab.strategies.stocks_in_play_orb.o04:Release",
    "o05": "trading.lab.strategies.stocks_in_play_orb.o05:Release",
    "o06": "trading.lab.strategies.stocks_in_play_orb.o06:Release",
    "o07": "trading.lab.strategies.stocks_in_play_orb.o07:Release",
    "o08": "trading.lab.strategies.stocks_in_play_orb.o08:Release",
    "o09": "trading.lab.strategies.stocks_in_play_orb.o09:Release",
    "o10": "trading.lab.strategies.stocks_in_play_orb.o10:Release",
    "o11": "trading.lab.strategies.stocks_in_play_orb.o11:Release",
    "d01": "trading.lab.strategies.post_gap_opening_drive.d01:Release",
    "d02": "trading.lab.strategies.post_gap_opening_drive.d02:Release",
    "d03": "trading.lab.strategies.post_gap_opening_drive.d03:Release",
    "d04": "trading.lab.strategies.post_gap_opening_drive.d04:Release",
    "d05": "trading.lab.strategies.post_gap_opening_drive.d05:Release",
    "d06": "trading.lab.strategies.post_gap_opening_drive.d06:Release",
    "d07": "trading.lab.strategies.post_gap_opening_drive.d07:Release",
    "d08": "trading.lab.strategies.post_gap_opening_drive.d08:Release",
    "d09": "trading.lab.strategies.post_gap_opening_drive.d09:Release",
    "d10": "trading.lab.strategies.post_gap_opening_drive.d10:Release",
    "d11": "trading.lab.strategies.post_gap_opening_drive.d11:Release",
    "d12": "trading.lab.strategies.post_gap_opening_drive.d12:Release",
    "d13": "trading.lab.strategies.post_gap_opening_drive.d13:Release",
    "d14": "trading.lab.strategies.post_gap_opening_drive.d14:Release",
    "d15": "trading.lab.strategies.post_gap_opening_drive.d15:Release",
    "f01": "trading.lab.strategies.dominance_flip_reversal.f01:Release",
    "f02": "trading.lab.strategies.dominance_flip_reversal.f02:Release",
    "f03": "trading.lab.strategies.dominance_flip_reversal.f03:Release",
    "f04": "trading.lab.strategies.dominance_flip_reversal.f04:Release",
    "f05": "trading.lab.strategies.dominance_flip_reversal.f05:Release",
    "f06": "trading.lab.strategies.dominance_flip_reversal.f06:Release",
    "f07": "trading.lab.strategies.dominance_flip_reversal.f07:Release",
    "s01": "trading.lab.strategies.smma_atr_breakout.s01:Release",
    "m01": "trading.lab.strategies.intraday_momentum.m01:Release",
    "m02": "trading.lab.strategies.intraday_momentum.m02:Release",
    "m03": "trading.lab.strategies.intraday_momentum.m03:Release",
    "b01": "trading.lab.strategies.momentum_burst.b01:Release",
    "b02": "trading.lab.strategies.momentum_burst.b02:Release",
    "x01": "trading.lab.strategies.xsec_momentum.x01:Release",
    "x03": "trading.lab.strategies.xsec_momentum.x03:Release",
    "x04": "trading.lab.strategies.xsec_momentum.x04:Release",
    # Research-only, non-shippable capture variants (prefix "capture_"): used by
    # the offline feature search (validation/feature_search_spec.md), never
    # promoted through the funnel.
    "capture_d_features": "trading.lab.strategies.post_gap_opening_drive.capture:Release",
}


def get_release_class(release_id: str):
    try:
        path = RELEASES[release_id]
    except KeyError as exc:
        raise KeyError(f"Unknown strategy_lab release: {release_id}") from exc
    module_name, class_name = path.split(":")
    module = import_module(module_name)
    return getattr(module, class_name)


def list_releases() -> list[str]:
    return sorted(RELEASES)
