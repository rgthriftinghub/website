#!/usr/bin/env bash
set -Eeuo pipefail

# Run as root on the server after both archives have been copied to /root.
# Override the service names if this host uses different systemd unit names.
BACKEND_SERVICE="${BACKEND_SERVICE:-rgthriftinghub-backend}"
FRONTEND_SERVICE="${FRONTEND_SERVICE:-rgthriftinghub-frontend}"
BACKEND_DIR="/var/www/backend"
FRONTEND_DIR="/var/www/frontend"
BACKUP_DIR="/root/thrifthub-backup-$(date +%Y%m%d-%H%M%S)"
RELEASE_DIR="/var/www/.thrifthub-release-$(date +%Y%m%d-%H%M%S)"
BACKEND_ZIP="/root/backend-20261126-2.zip"
FRONTEND_ZIP="/root/frontend-20261126-2.zip"
BACKEND_SHA256="E6840EF7BBBFF71874B5B04C5AD9352F6EC8F416F38668B3AFEFC7E4CA1FBD8B"
FRONTEND_SHA256="750E3CF2444D3722A3DEC3455836244C4FDF969EE9B8A4A5F53BD8F828A278A5"
MIGRATION_ID="d3f7a91c6b42"
MIGRATION_FILE="${MIGRATION_ID}_expand_product_descriptions.py"
BACKEND_SWAPPED=0
FRONTEND_SWAPPED=0

rollback_apps() {
  local failed=0
  set +e
  if (( FRONTEND_SWAPPED )); then
    systemctl stop "$FRONTEND_SERVICE"
    rm -rf "$FRONTEND_DIR"
    mv "$RELEASE_DIR/previous-frontend" "$FRONTEND_DIR"
    systemctl restart "$FRONTEND_SERVICE" || failed=1
  fi
  if (( BACKEND_SWAPPED )); then
    systemctl stop "$BACKEND_SERVICE"
    rm -rf "$BACKEND_DIR"
    mv "$RELEASE_DIR/previous-backend" "$BACKEND_DIR"
    systemctl restart "$BACKEND_SERVICE" || failed=1
  fi
  if (( failed )); then
    echo "Automatic application rollback was attempted; inspect systemd status." >&2
  fi
}

on_error() {
  local status=$?
  trap - ERR
  echo "Deployment failed (exit $status). Restoring application folders; database migration remains applied." >&2
  rollback_apps
  exit "$status"
}
trap on_error ERR

cd "$BACKEND_DIR"
printf '%s\n' "alembic current"
CURRENT_REVISION="$(./venv/bin/alembic current)"
printf '%s\n' "$CURRENT_REVISION"
CURRENT_IDS="$(printf '%s\n' "$CURRENT_REVISION" | awk 'NF {print $1}')"
case "$CURRENT_IDS" in
  a19f6b3d8c42) MIGRATION_NEEDED=1 ;;
  d3f7a91c6b42) MIGRATION_NEEDED=0 ;;
  *) echo "Expected a19f6b3d8c42 or d3f7a91c6b42; refusing deployment." >&2; exit 1 ;;
esac
command -v systemctl >/dev/null
systemctl cat "$BACKEND_SERVICE" >/dev/null
systemctl cat "$FRONTEND_SERVICE" >/dev/null

command -v unzip >/dev/null
command -v sha256sum >/dev/null
command -v curl >/dev/null
test -f "$BACKEND_ZIP"
test -f "$FRONTEND_ZIP"
printf '%s\n' "Checking deployment archives"
printf '%s  %s\n' "$BACKEND_SHA256" "$BACKEND_ZIP" | sha256sum --check
printf '%s  %s\n' "$FRONTEND_SHA256" "$FRONTEND_ZIP" | sha256sum --check

mkdir -p "$BACKUP_DIR" "$RELEASE_DIR"
mkdir "$RELEASE_DIR/backend-stage" "$RELEASE_DIR/frontend-stage"
unzip -q "$BACKEND_ZIP" -d "$RELEASE_DIR/backend-stage"
unzip -q "$FRONTEND_ZIP" -d "$RELEASE_DIR/frontend-stage"
test -f "$RELEASE_DIR/backend-stage/app/main.py"
test -f "$RELEASE_DIR/frontend-stage/server.js"
test -f "$RELEASE_DIR/backend-stage/alembic/versions/$MIGRATION_FILE"

# Save the database before changing its schema. The invoking root shell writes
# the redirect, so postgres never needs permission on the root-owned folder.
sudo -u postgres pg_dump --format=custom --dbname=thrifthub > "$BACKUP_DIR/thrifthub.dump"
test -s "$BACKUP_DIR/thrifthub.dump"

# Apply the schema change while the old backend is still serving traffic. If
# Alembic is already at the new revision, keep it there and resume the app swap.
if (( MIGRATION_NEEDED )); then
  install -m 0644 "$RELEASE_DIR/backend-stage/alembic/versions/$MIGRATION_FILE" \
    "$BACKEND_DIR/alembic/versions/$MIGRATION_FILE"
  ./venv/bin/alembic upgrade head
fi
printf '%s\n' "alembic current"
CURRENT_REVISION="$(./venv/bin/alembic current)"
printf '%s\n' "$CURRENT_REVISION"
CURRENT_IDS="$(printf '%s\n' "$CURRENT_REVISION" | awk 'NF {print $1}')"
if [[ "$CURRENT_IDS" != "$MIGRATION_ID" ]]; then
  echo "Expected exactly $MIGRATION_ID after upgrade; refusing app swap." >&2
  exit 1
fi

health_check() {
  local url="$1"
  local attempt
  for attempt in {1..30}; do
    if curl --connect-timeout 2 --max-time 5 --fail --silent --show-error "$url" >/dev/null; then
      return 0
    fi
    sleep 2
  done
  echo "Health check failed: $url" >&2
  return 1
}

mv "$BACKEND_DIR" "$RELEASE_DIR/previous-backend"
BACKEND_SWAPPED=1
mv "$RELEASE_DIR/backend-stage" "$BACKEND_DIR"
ln -s "$RELEASE_DIR/previous-backend/venv" "$BACKEND_DIR/venv"
systemctl restart "$BACKEND_SERVICE"
health_check "http://127.0.0.1:8000/api/v1/health"

mv "$FRONTEND_DIR" "$RELEASE_DIR/previous-frontend"
FRONTEND_SWAPPED=1
mv "$RELEASE_DIR/frontend-stage" "$FRONTEND_DIR"
systemctl restart "$FRONTEND_SERVICE"
health_check "http://127.0.0.1:3000/api/health"

trap - ERR
echo "Deployment succeeded. Database backup: $BACKUP_DIR/thrifthub.dump"
echo "Previous application folders retained under $RELEASE_DIR. The migration was not downgraded."
