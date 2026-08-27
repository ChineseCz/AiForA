#!/usr/bin/env bash
set -Eeuo pipefail

# Production deployment helper for /data/app on the Ubuntu server.
# It does not modify database volumes and never prints secret environment values.
APP_DIR="${APP_DIR:-/data/app}"
COMPOSE_DIR="$APP_DIR/backend"

cd "$APP_DIR"
echo "==> Pulling dev branch"
git pull --ff-only origin dev

cd "$COMPOSE_DIR"
echo "==> Validating Compose configuration"
docker compose config -q

echo "==> Building and recreating application services"
# browser-worker copies the application into its image instead of mounting
# ./app, so it must be rebuilt whenever browser task code changes.
docker compose up -d --build api worker beat browser-worker frontend

echo "==> Applying database migrations"
docker compose exec -T api alembic upgrade head

# API recreation changes its Docker-internal IP. Recreate frontend so Nginx
# resolves the current api service address instead of a stale cached address.
echo "==> Recreating frontend Nginx"
docker compose up -d --force-recreate frontend

echo "==> Service status"
docker compose ps

echo "==> Health checks"
curl --fail --silent --show-error http://127.0.0.1:8090/health >/dev/null
curl --fail --silent --show-error http://127.0.0.1:8090/ >/dev/null
echo "Deployment completed successfully."
