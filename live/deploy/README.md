# Deploying trading.live (DigitalOcean droplet + Tailscale)

One Ubuntu droplet runs **two fully isolated compose stacks** — `testing` and `prod`
(DESIGN §18). Ingress is **Tailscale-only**; no public ports.

## Droplet one-time setup
1. Create an Ubuntu droplet (NYC region — close to the exchanges/broker).
2. Install Docker + Compose plugin, and **Tailscale** (`tailscale up`). Note its IP
   (`tailscale ip -4`).
3. Create per-env dirs: `/srv/tl-testing`, `/srv/tl-prod`, each with `.env.<env>` and a
   secrets file.

## Env files (per stack)
`.env.testing` / `.env.prod`:
```
TRADING_ENV=testing            # or prod
IMAGE=ghcr.io/shtylenko/trading-live:<tag>
TAILSCALE_IP=100.x.y.z         # from `tailscale ip -4`
WEB_PORT=8810                  # testing 8810, prod 8820
TRADING_LIVE_WEB_TOKEN=<long-random>   # required to take control actions
SECRETS_FILE=/srv/tl-prod/secrets.env  # per-portfolio broker keys (PROD ONLY)
```
`secrets.env` (prod only — real broker keys live ONLY here, never in the repo):
```
ALPACA_PF1_KEY=...
ALPACA_PF1_SECRET=...
```

## Bring up
```bash
cd /srv/tl-testing && docker compose --project-name tl-testing --env-file .env.testing up -d
cd /srv/tl-prod    && docker compose --project-name tl-prod    --env-file .env.prod    up -d
```
Reach the UI from your laptop/phone (both on the tailnet): `http://<TAILSCALE_IP>:8810`
(testing) / `:8820` (prod). It is dark to the public internet.

## CI/CD (GitHub Actions)
- merge to `main` → build image, run `pytest trading/lab/tests trading/live/tests`, push to
  GHCR, SSH to the droplet, pull + recreate the **testing** stack.
- release tag `live-vX.Y.Z` → manual-approval gate → recreate the **prod** stack. Roll back
  by redeploying the previous tag. Promotion is **code only**; state stays on the droplet.

## Safety
- `live` mode is refused unless `TRADING_ENV=prod` (config hard-lock).
- Control actions require `TRADING_LIVE_WEB_TOKEN`; UI bound to the Tailscale IP only.
- A deploy never resets a tripped kill switch (state volume persists across recreates).
