"""trading — research + execution monorepo.

Three subsystems:
  - ``trading.marketdata`` — the finance data layer (the only market-data source).
  - ``trading.lab``        — strategy research/discovery harness (was ``strategy_lab``).
  - ``trading.live``       — live (paper-first) execution of funnel-validated releases.

Dependency direction: marketdata ← lab ← live. ``lab`` and ``live`` both read the same
``marketdata`` layer, which is what enforces backtest/live parity.
"""
