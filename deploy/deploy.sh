#!/bin/bash
set -euo pipefail

APP_DIR=/opt/bakecake
VENV="$APP_DIR/.venv"

cd "$APP_DIR"

if [ -f backend/db.sqlite3 ]; then
  BACKUP="/opt/backups/db-$(date +%F-%H%M%S).sqlite3"
  mkdir -p /opt/backups
  "$VENV/bin/python" - "$BACKUP" <<'PY'
import sqlite3
import sys

source = sqlite3.connect("/opt/bakecake/backend/db.sqlite3")
target = sqlite3.connect(sys.argv[1])
source.backup(target)
target.close()
source.close()
PY
  echo "backup: $BACKUP"
fi

echo "=== git pull ==="
git pull --ff-only origin main

echo "=== pip install ==="
"$VENV/bin/pip" install -q -r requirements-server.txt

cd "$APP_DIR/backend"
echo "=== collectstatic ==="
"$VENV/bin/python" manage.py collectstatic --noinput
echo "=== migrate ==="
"$VENV/bin/python" manage.py migrate --noinput
echo "=== seed_demo ==="
"$VENV/bin/python" ../scripts/seed_demo.py

echo "=== restart bakecake ==="
systemctl restart bakecake

echo "deploy OK: $(git -C "$APP_DIR" rev-parse --short HEAD)"
