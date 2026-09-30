#!/bin/bash
set -euo pipefail

APP_DIR=/opt/bakecake
REPO=https://github.com/skislyakow/BakeCake.git
DOMAIN=bakecake.kislyakov.pro
NGINX_SITE=/etc/nginx/sites-available/$DOMAIN

echo "=== 1. системные пакеты ==="
missing=0
for pkg in nginx python3-venv python3-pip certbot python3-certbot-nginx; do
  if ! dpkg -s "$pkg" >/dev/null 2>&1; then
    echo "  installing $pkg"
    missing=1
  fi
done
if [ "$missing" -eq 1 ]; then
  apt-get update -qq
  DEBIAN_FRONTEND=noninteractive apt-get install -y -qq \
    nginx python3-venv python3-pip certbot python3-certbot-nginx
fi

echo "=== 2. каталоги ==="
mkdir -p /var/log/bakecake /opt/backups

echo "=== 3. репозиторий ==="
if [ -d "$APP_DIR/.git" ]; then
  git -C "$APP_DIR" pull --ff-only origin main
else
  git clone "$REPO" "$APP_DIR"
fi

echo "=== 4. venv и зависимости ==="
python3 -m venv "$APP_DIR/.venv"
"$APP_DIR/.venv/bin/pip" install -q --upgrade pip
"$APP_DIR/.venv/bin/pip" install -q -r "$APP_DIR/requirements-server.txt"

echo "=== 5. .env ==="
if [ ! -f "$APP_DIR/.env" ]; then
  SECRET_KEY=$("$APP_DIR/.venv/bin/python" -c \
    "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())")
  cat > "$APP_DIR/.env" <<EOF
SECRET_KEY="$SECRET_KEY"
DEBUG=0
ALLOWED_HOSTS=$DOMAIN
SHOP_PHONE="8 (495) 000-00-00"
YOO_SHOP_ID=
YOO_SECRET_KEY=
JIVO_SITE_ID=
EOF
  chmod 600 "$APP_DIR/.env"
  echo "  created with fresh SECRET_KEY"
else
  echo "  exists, left untouched"
fi

echo "=== 6. systemd-юниты ==="
install -m 644 "$APP_DIR/deploy/bakecake.service" /etc/systemd/system/bakecake.service
install -m 644 "$APP_DIR/deploy/bakecake-autodeploy.service" /etc/systemd/system/bakecake-autodeploy.service
install -m 644 "$APP_DIR/deploy/bakecake-autodeploy.timer" /etc/systemd/system/bakecake-autodeploy.timer
chmod +x "$APP_DIR/deploy/deploy.sh" "$APP_DIR/deploy/auto-deploy.sh"
systemctl daemon-reload

echo "=== 7. первый деплой приложения ==="
"$APP_DIR/deploy/deploy.sh"
systemctl enable --now bakecake.service
sleep 2
systemctl is-active bakecake.service

echo "=== 8. nginx ==="
install -m 644 "$APP_DIR/deploy/nginx.conf" "$NGINX_SITE"
ln -sfn "$NGINX_SITE" /etc/nginx/sites-enabled/$DOMAIN
nginx -t
systemctl reload nginx

echo "=== 9. TLS ==="
if [ -d "/etc/letsencrypt/live/$DOMAIN" ]; then
  echo "  certificate already issued, renewing"
  certbot renew --cert-name "$DOMAIN" --quiet || true
else
  certbot --nginx -d "$DOMAIN" --non-interactive --agree-tos
fi

echo "=== 10. таймер автодеплоя ==="
systemctl enable --now bakecake-autodeploy.timer

echo
echo "=== ИТОГ ==="
systemctl is-active bakecake.service
systemctl is-active bakecake-autodeploy.timer
systemctl list-timers --no-pager bakecake-autodeploy.timer
echo "https://$DOMAIN/"
