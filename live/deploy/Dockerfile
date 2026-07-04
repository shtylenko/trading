# trading.live — image runs both the web control plane and the scheduler/engine.
# Built by CI, pushed to GHCR, pulled per env on the DigitalOcean droplet (DESIGN §18).
FROM python:3.11-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1

# deps first for layer caching
COPY trading/live/requirements.txt /app/trading/live/requirements.txt
RUN pip install --no-cache-dir -r /app/trading/live/requirements.txt

# the three subsystems live imports: marketdata (data layer) + lab (releases) + live
COPY trading/__init__.py /app/trading/__init__.py
COPY trading/marketdata /app/trading/marketdata
COPY trading/lab /app/trading/lab
COPY trading/live /app/trading/live

# NOTE: heavy research artifacts (lab DuckDB, 28GB bar cache) are NOT copied — each
# env warms its own live-scoped marketdata cache from providers (DESIGN §18).

# default: the web control plane (compose overrides command for the scheduler service)
CMD ["python", "-m", "trading.live.web.app"]
