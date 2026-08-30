#!/bin/sh
# docker/start.sh — container entrypoint for the production single-container image.
#
# Render injects PORT (default 10000). nginx must listen on that port.
# We use envsubst to substitute ${PORT} into the nginx config template
# before starting supervisord, which runs nginx + uvicorn together.

set -e

PORT="${PORT:-10000}"
export PORT

echo "[start.sh] PORT=${PORT}"
echo "[start.sh] Substituting \${PORT} into nginx config template..."

# Substitute only ${PORT}; leave all other nginx $variables untouched
envsubst '${PORT}' \
    < /etc/nginx/conf.d/default.conf.template \
    > /etc/nginx/conf.d/default.conf

echo "[start.sh] Rendered nginx config:"
cat /etc/nginx/conf.d/default.conf

echo "[start.sh] Testing nginx config..."
nginx -t

echo "[start.sh] Starting supervisord (nginx + uvicorn)..."
exec /usr/bin/supervisord -c /etc/supervisor/conf.d/supervisord.conf
