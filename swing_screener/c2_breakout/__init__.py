"""C2_BREAKOUT — 52-week high base breakout screening and simulation."""

from .rules import C2Config, load_config
from .screen import run_screen

__all__ = ["C2Config", "load_config", "run_screen"]
