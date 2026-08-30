#!/bin/sh
# docker/start.sh — container entrypoint for the production single-container image.
#
# Render (and other PaaS platforms) inject a PORT environment variable.
# nginx must listen on that port; we use envsubst to substitute $PORT into
# the nginx config before starting supervisord.
#
# Default PORT=10000 matches Render's default when no explicit port is set.

set -e

PORT="${PORT:-10000}"
export PORT

echo "[start.sh] Substituting PORT=${PORT} into nginx config..."

# Write the rendered nginx config (envsubst replaces ${PORT} only)
envsubst '${PORT}' < /etc/nginx/conf.d/default.conf.template \
    > /etc/nginx/conf.d/default.conf

echo "[start.sh] nginx config written. Starting supervisord..."

exec /usr/bin/supervisord -c /etc/supervisor/conf.d/supervisord.conf
