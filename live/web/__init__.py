"""trading.live web control plane (separate app from the lab dashboard).

P0: read-only overview of the latest target book + denylist + kill-switch state,
served by FastAPI + Jinja/HTMX. Control actions (approve/pause/kill/onboard) and
the broker arrive in P1+. Bind to localhost in dev; Tailscale-only ingress in
testing/prod (DESIGN §17).
"""
