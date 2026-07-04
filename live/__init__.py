"""Live (paper-first) execution for funnel-validated swing releases.

See DESIGN.md. The single non-negotiable principle: the live trade list is produced
by the SAME ``Release.build_candidates`` code and the SAME ``data/market_data.py``
loader the backtest used — never a re-implementation. Nothing here submits a real
order yet (``broker.submit_orders`` raises until deliberately wired + reviewed).
"""
