#!/usr/bin/env bash
set -Eeuo pipefail

# Production deployment helper for /data/app on the Ubuntu server.
# It does not modify database volumes and never prints secret environment values.
APP_DIR="${APP_DIR:-/data/app}"
COMPOSE_DIR="$APP_DIR/backend"
BACKUP_DIR="${BACKUP_DIR:-$APP_DIR/backups/postgres}"
HEALTH_URL="${HEALTH_URL:-http://127.0.0.1:8090/health}"
ROOT_URL="${ROOT_URL:-http://127.0.0.1:8090/}"
HEALTH_RETRIES="${HEALTH_RETRIES:-30}"
HEALTH_DELAY="${HEALTH_DELAY:-2}"

COMPOSE=(docker compose)

print_failure_context() {
  echo "==> Deployment failed; existing containers and volumes were left in place."
  echo "==> Service status"
  "${COMPOSE[@]}" ps || true
  echo "==> Recent API logs"
  "${COMPOSE[@]}" logs --tail=80 api || true
}

trap print_failure_context ERR

wait_for_url() {
  local url="$1"
  local label="$2"
  local attempt

  for ((attempt = 1; attempt <= HEALTH_RETRIES; attempt++)); do
    if curl --fail --silent --show-error --connect-timeout 2 --max-time 5 "$url" >/dev/null 2>&1; then
      echo "    $label is healthy"
      return 0
    fi
    sleep "$HEALTH_DELAY"
  done

  echo "    $label did not become healthy: $url" >&2
  return 1
}

cd "$APP_DIR"
cd "$COMPOSE_DIR"
echo "==> Validating Compose configuration"
"${COMPOSE[@]}" config -q

echo "==> Starting database services for backup"
"${COMPOSE[@]}" up -d postgres redis

echo "==> Waiting for PostgreSQL"
"${COMPOSE[@]}" ps --wait postgres

mkdir -p "$BACKUP_DIR"
backup_file="$BACKUP_DIR/postgres-$(date +%Y%m%d-%H%M%S).sql.gz"
echo "==> Backing up PostgreSQL to $backup_file"
"${COMPOSE[@]}" exec -T postgres sh -c \
  'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --no-owner --no-privileges' \
  | gzip > "$backup_file"
test -s "$backup_file"

echo "==> Pulling dev branch"
cd "$APP_DIR"
git pull --ff-only origin dev

cd "$COMPOSE_DIR"
echo "==> Validating Compose configuration after update"
"${COMPOSE[@]}" config -q

echo "==> Building and recreating application services"
# browser-worker copies the application into its image instead of mounting
# ./app, so it must be rebuilt whenever browser task code changes.
"${COMPOSE[@]}" up -d --build api worker beat browser-worker frontend

echo "==> Applying database migrations"
"${COMPOSE[@]}" exec -T api alembic upgrade head

echo "==> Verifying database migration state"
"${COMPOSE[@]}" exec -T api alembic check
current_revision="$("${COMPOSE[@]}" exec -T api alembic current 2>/dev/null | tr -d '\r' | tail -n 1)"
echo "    Alembic current: ${current_revision:-unknown}"

# API recreation changes its Docker-internal IP. Recreate frontend so Nginx
# resolves the current api service address instead of a stale cached address.
echo "==> Recreating frontend Nginx"
"${COMPOSE[@]}" up -d --force-recreate frontend

echo "==> Service status"
"${COMPOSE[@]}" ps --wait

echo "==> Health checks"
wait_for_url "$HEALTH_URL" "API health endpoint"
wait_for_url "$ROOT_URL" "Frontend endpoint"
echo "==> Deployment version"
git rev-parse --short HEAD
git log -1 --format='%h %s'
echo "Deployment completed successfully."
