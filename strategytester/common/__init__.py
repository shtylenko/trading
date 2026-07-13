"""strategytester.common — shared research engine for short-hold strategy tests.

Self-contained (depends only on ``trading.marketdata``): vectorized daily
indicators, a cached daily panel loader, one shared trade simulator that
enforces the short-hold (<=3 session) mandate, and a metrics module used to
rank strategies on risk-adjusted profitability.
"""

__all__ = ["__version__"]
__version__ = "0.1.0"
