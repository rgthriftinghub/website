#!/usr/bin/env bash
set -Eeuo pipefail

# Run on the production host after copying both archives into /root.
BACKEND_DIR=/var/www/backend
FRONTEND_DIR=/var/www/frontend-app
FRONTEND_OLD=/var/www/frontend-app.old
BACKEND_SERVICE=thrifthub
FRONTEND_SERVICE=thriftfront
BACKEND_ZIP=/root/backend-20261126-3.zip
FRONTEND_ZIP=/root/frontend-20261126-3.zip
MIGRATION_ID=d3f7a91c6b42
MIGRATION_FILE=${MIGRATION_ID}_expand_product_descriptions.py
STAMP=$(date +%Y%m%d-%H%M%S)
BACKUP_DIR=/root/deploy-3-backup-${STAMP}
STAGE_DIR=/var/www/.deploy-3-${STAMP}
BACKEND_CHANGED=0
FRONTEND_CHANGED=0

[[ "$BACKEND_DIR" == /var/www/backend && "$FRONTEND_DIR" == /var/www/frontend-app ]] || exit 2
[[ -f "$BACKEND_ZIP" && -f "$FRONTEND_ZIP" ]]
[[ ! -e "$FRONTEND_OLD" ]] || { echo "$FRONTEND_OLD already exists; move it aside before deploying." >&2; exit 2; }

mkdir -p "$BACKUP_DIR" "$STAGE_DIR/backend" "$STAGE_DIR/frontend"

rollback() {
  local status=$?
  trap - ERR
  set +e
  if (( FRONTEND_CHANGED )); then
    systemctl stop "$FRONTEND_SERVICE"
    rm -rf "$FRONTEND_DIR"
    mv "$FRONTEND_OLD" "$FRONTEND_DIR"
    systemctl restart "$FRONTEND_SERVICE"
  fi
  if (( BACKEND_CHANGED )); then
    rm -rf "$BACKEND_DIR/app"
    cp -a "$BACKUP_DIR/backend-app" "$BACKEND_DIR/app"
    systemctl restart "$BACKEND_SERVICE"
  fi
  echo "Deploy failed; application rollback attempted. Database migrations, if applied, remain applied." >&2
  exit "$status"
}
trap rollback ERR

unzip -q "$BACKEND_ZIP" -d "$STAGE_DIR/backend"
unzip -q "$FRONTEND_ZIP" -d "$STAGE_DIR/frontend"
test -f "$STAGE_DIR/backend/app/main.py"
test -f "$STAGE_DIR/backend/alembic/versions/$MIGRATION_FILE"
test -f "$STAGE_DIR/frontend/server.js"

# Back up and replace only the backend app directory. .env, venv, uploads, and
# all other backend files remain in place.
cp -a "$BACKEND_DIR/app" "$BACKUP_DIR/backend-app"
cp -a "$STAGE_DIR/backend/app" "$BACKEND_DIR/app.next"
BACKEND_CHANGED=1
rm -rf "$BACKEND_DIR/app"
mv "$BACKEND_DIR/app.next" "$BACKEND_DIR/app"

# Add the description column expansion only when the installed database needs it.
CURRENT_REVISION=$(cd "$BACKEND_DIR" && ./venv/bin/alembic current | awk -F': ' 'NF > 1 {print $NF; exit}')
if [[ "$CURRENT_REVISION" == a19f6b3d8c42 ]]; then
  if [[ ! -f "$BACKEND_DIR/alembic/versions/$MIGRATION_FILE" ]]; then
    cp "$STAGE_DIR/backend/alembic/versions/$MIGRATION_FILE" "$BACKEND_DIR/alembic/versions/$MIGRATION_FILE"
  fi
  (cd "$BACKEND_DIR" && ./venv/bin/alembic upgrade head)
elif [[ "$CURRENT_REVISION" != "$MIGRATION_ID" ]]; then
  echo "Unexpected Alembic revision: ${CURRENT_REVISION:-none}" >&2
  exit 1
fi

systemctl restart "$BACKEND_SERVICE"
for attempt in {1..30}; do
  if curl --connect-timeout 2 --max-time 5 --fail --silent http://127.0.0.1:8000/api/v1/health >/dev/null; then break; fi
  [[ "$attempt" -lt 30 ]] || { echo "Backend health check failed." >&2; exit 1; }
  sleep 2
done

# Retain the server's current public files without replacing files shipped in
# the archive, as requested.
mkdir -p "$STAGE_DIR/frontend/public"
if [[ -d "$FRONTEND_DIR/public" ]]; then
  cp -an "$FRONTEND_DIR/public/." "$STAGE_DIR/frontend/public/"
fi

FRONTEND_CHANGED=1
mv "$FRONTEND_DIR" "$FRONTEND_OLD"
mv "$STAGE_DIR/frontend" "$FRONTEND_DIR"
systemctl restart "$FRONTEND_SERVICE"
for attempt in {1..30}; do
  if curl --connect-timeout 3 --max-time 10 --fail --silent https://rgthriftinghub.com >/dev/null; then break; fi
  [[ "$attempt" -lt 30 ]] || { echo "Frontend health check failed." >&2; exit 1; }
  sleep 2
done

trap - ERR
echo "Deploy succeeded. Backend backup: $BACKUP_DIR/backend-app"
echo "Previous frontend retained at $FRONTEND_OLD"
echo "Backend .env, venv, and uploads were left in place."
