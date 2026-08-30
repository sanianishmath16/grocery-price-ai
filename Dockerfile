# ─────────────────────────────────────────────────────────────────────────────
# Dockerfile — GroceryAI
#
# LOCAL (docker-compose):
#   Two separate containers — `api` (this image, FastAPI only) and
#   `frontend` (nginx:alpine, static files).  nginx proxies /api → api:8000.
#
# PRODUCTION SINGLE-CONTAINER (Fly.io / Render / Railway):
#   Set BUILD_TARGET=prod to get a single image that runs BOTH nginx and
#   uvicorn via supervisord.  The entrypoint (docker/start.sh) substitutes
#   the $PORT env var (injected by Render, default 10000) into the nginx
#   config at startup so Render's router can reach nginx.
#
#   docker build --build-arg BUILD_TARGET=prod -t groceryai .
#
# Default build (no arg) produces the API-only image used by docker-compose.
# ─────────────────────────────────────────────────────────────────────────────

ARG BUILD_TARGET=dev

# ── Stage 1: Python deps ──────────────────────────────────────────────────────
FROM python:3.11-slim AS python-deps

WORKDIR /app
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ── Stage 2: API-only (used by docker-compose 'api' service) ─────────────────
FROM python:3.11-slim AS dev

# Install tesseract for free local OCR image recognition
RUN apt-get update && apt-get install -y --no-install-recommends \
        tesseract-ocr \
        tesseract-ocr-eng \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY --from=python-deps /install /usr/local
COPY backend/ ./
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]

# ── Stage 3: Production single-container (nginx + uvicorn + supervisord) ──────
FROM python:3.11-slim AS prod

# Install nginx, supervisord, gettext (envsubst) and tesseract for OCR
RUN apt-get update && apt-get install -y --no-install-recommends \
        nginx \
        supervisor \
        gettext-base \
        tesseract-ocr \
        tesseract-ocr-eng \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Python packages
COPY --from=python-deps /install /usr/local

# FastAPI backend
COPY backend/ ./

# Frontend static files
COPY frontend/ /usr/share/nginx/html/

# Store nginx config as a template; start.sh will run envsubst at runtime
# to substitute $PORT (injected by Render/PaaS) before nginx starts.
COPY nginx-prod.conf /etc/nginx/conf.d/default.conf.template
RUN rm -f /etc/nginx/sites-enabled/default

# supervisord config — starts nginx and uvicorn together
RUN mkdir -p /var/log/supervisor
COPY docker/supervisord.conf /etc/supervisor/conf.d/supervisord.conf

# Startup script: substitutes $PORT in nginx config then exec supervisord
COPY docker/start.sh /start.sh
RUN chmod +x /start.sh

# Render default PORT is 10000; expose it so `docker run -P` works locally too
EXPOSE 10000

CMD ["/start.sh"]

# ── Final: select the right stage based on BUILD_TARGET ──────────────────────
FROM ${BUILD_TARGET}
