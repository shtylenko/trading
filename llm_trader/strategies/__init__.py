"""Strategy family registry for llm_trader.

Each family owns its scan config, screen/pattern pipeline, skill tree, risk
defaults, and horizon. The platform (recorder, step, execution, batchsim)
is strategy-aware via :func:`get_strategy`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .base import StrategySpec

_REGISTRY: dict[str, "StrategySpec"] | None = None


def _build_registry() -> dict[str, "StrategySpec"]:
    from .bb_squeeze_long import BbSqueezeLongStrategy
    from .breakout_first_pullback import BreakoutFirstPullbackStrategy
    from .cup_handle import CupHandleStrategy
    from .inplay_continuation import InplayContinuationStrategy
    from .micro_pullback import MicroPullbackStrategy
    from .right_side_v import RightSideVStrategy
    from .trend_pullback import TrendPullbackStrategy
    from .vwap_pullback import VwapPullbackStrategy
    from .warrior import WarriorStrategy

    specs = [
        WarriorStrategy(),
        CupHandleStrategy(),
        TrendPullbackStrategy(),
        BreakoutFirstPullbackStrategy(),
        RightSideVStrategy(),
        VwapPullbackStrategy(),
        BbSqueezeLongStrategy(),
        MicroPullbackStrategy(),
        InplayContinuationStrategy(),
    ]
    return {s.id: s for s in specs}


def get_strategy(strategy_id: str) -> "StrategySpec":
    """Return the registered strategy or raise ``KeyError``."""
    global _REGISTRY
    if _REGISTRY is None:
        _REGISTRY = _build_registry()
    sid = (strategy_id or "warrior").strip().lower().replace("-", "_")
    if sid not in _REGISTRY:
        known = ", ".join(sorted(_REGISTRY))
        raise KeyError(f"unknown strategy {strategy_id!r}; known: {known}")
    return _REGISTRY[sid]


def list_strategies() -> list[str]:
    global _REGISTRY
    if _REGISTRY is None:
        _REGISTRY = _build_registry()
    return sorted(_REGISTRY)


def default_strategy_id() -> str:
    return "warrior"
