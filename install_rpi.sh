#!/usr/bin/env bash
set -euo pipefail

# Raspberry Pi OS installer for LuminaShow
# Supports manual install on Pi 4/5 and non-interactive image builds.

INSTALL_DIR="${LUMINA_INSTALL_DIR:-/opt/lumina-signage}"
APP_USER="${LUMINA_APP_USER:-lumina}"
APP_PORT="${LUMINA_PORT:-8080}"
KIOSK_USER=""
NON_INTERACTIVE=false
SKIP_APT=false
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SECRET_KEY="${LUMINA_SECRET_KEY:-$(openssl rand -hex 32)}"

usage() {
  cat <<EOF
Usage: sudo bash install_rpi.sh [options]

Options:
  --port <port>              App port (default: 8080)
  --install-dir <path>       Install directory (default: /opt/lumina-signage)
  --kiosk-user <username>    Install kiosk autostart desktop file for this user
  --non-interactive          Run without prompts (for automation / image build)
  --skip-apt                 Skip apt update/install (if already provisioned)
  -h, --help                 Show this help
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --port)
      APP_PORT="$2"
      shift 2
      ;;
    --install-dir)
      INSTALL_DIR="$2"
      shift 2
      ;;
    --kiosk-user)
      KIOSK_USER="$2"
      shift 2
      ;;
    --non-interactive)
      NON_INTERACTIVE=true
      shift
      ;;
    --skip-apt)
      SKIP_APT=true
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1"
      usage
      exit 1
      ;;
  esac
done

if [[ "${EUID}" -ne 0 ]]; then
  echo "Run as root: sudo bash install_rpi.sh"
  exit 1
fi

if [[ ! -f /etc/os-release ]]; then
  echo "Cannot detect operating system."
  exit 1
fi

source /etc/os-release
if [[ "${ID:-}" != "raspbian" && "${ID:-}" != "debian" ]]; then
  echo "Warning: this installer is tested on Raspberry Pi OS (Debian-based)."
fi

if [[ -f /proc/device-tree/model ]]; then
  model="$(tr -d '\0' < /proc/device-tree/model || true)"
  if [[ "$model" != *"Raspberry Pi 4"* && "$model" != *"Raspberry Pi 5"* ]]; then
    echo "Warning: detected hardware '$model'. This script is tuned for Pi 4/5."
  fi
fi

if [[ "$NON_INTERACTIVE" != true ]]; then
  echo "Install dir : $INSTALL_DIR"
  echo "App user    : $APP_USER"
  echo "Port        : $APP_PORT"
  if [[ -n "$KIOSK_USER" ]]; then
    echo "Kiosk user  : $KIOSK_USER"
  fi
  read -r -p "Proceed with installation? [Y/n]: " confirm
  confirm="${confirm:-Y}"
  if [[ ! "$confirm" =~ ^[Yy]$ ]]; then
    echo "Cancelled."
    exit 0
  fi
fi

wait_for_apt_lock() {
  while fuser /var/lib/dpkg/lock-frontend /var/lib/apt/lists/lock /var/cache/apt/archives/lock >/dev/null 2>&1; do
    sleep 2
  done
}

if [[ "$SKIP_APT" != true ]]; then
  wait_for_apt_lock
  apt-get update -y
  wait_for_apt_lock
  DEBIAN_FRONTEND=noninteractive apt-get install -y \
    python3 python3-pip python3-venv python3-dev \
    build-essential ffmpeg nginx imagemagick \
    curl wget git rsync openssl \
    libssl-dev libjpeg-dev libpng-dev libwebp-dev
fi

if ! id "$APP_USER" >/dev/null 2>&1; then
  useradd --system --no-create-home --shell /usr/sbin/nologin "$APP_USER"
fi

mkdir -p "$INSTALL_DIR"
mkdir -p "$INSTALL_DIR/static/uploads/thumbnails"
mkdir -p /var/log/lumina

rsync -a \
  --exclude '.git' \
  --exclude '__pycache__' \
  --exclude 'venv' \
  --exclude 'lumina.db' \
  "$SCRIPT_DIR/" "$INSTALL_DIR/"

python3 -m venv "$INSTALL_DIR/venv"
"$INSTALL_DIR/venv/bin/pip" install --upgrade pip
"$INSTALL_DIR/venv/bin/pip" install -r "$INSTALL_DIR/requirements.txt"

cat > "$INSTALL_DIR/.env" <<EOF
SECRET_KEY=$SECRET_KEY
PORT=$APP_PORT
DEBUG=false
EOF
chmod 600 "$INSTALL_DIR/.env"

cat > /etc/systemd/system/lumina.service <<EOF
[Unit]
Description=LuminaShow Digital Signage
After=network.target

[Service]
Type=simple
User=$APP_USER
WorkingDirectory=$INSTALL_DIR
Environment=PORT=$APP_PORT
Environment=SECRET_KEY=$SECRET_KEY
ExecStart=$INSTALL_DIR/venv/bin/gunicorn --bind 0.0.0.0:$APP_PORT --workers 2 --timeout 120 --access-logfile /var/log/lumina/access.log --error-logfile /var/log/lumina/error.log app:app
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

cat > /etc/nginx/sites-available/lumina <<EOF
server {
    listen 80;
    server_name _;

    client_max_body_size 2048M;
    proxy_read_timeout 300;
    proxy_connect_timeout 300;
    proxy_send_timeout 300;

    location /static/ {
        alias $INSTALL_DIR/static/;
        expires 7d;
        add_header Cache-Control "public, immutable";
    }

    location / {
        proxy_pass http://127.0.0.1:$APP_PORT;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_buffering off;
    }
}
EOF

ln -sf /etc/nginx/sites-available/lumina /etc/nginx/sites-enabled/lumina
rm -f /etc/nginx/sites-enabled/default

chown -R "$APP_USER:$APP_USER" "$INSTALL_DIR"
chown -R "$APP_USER:$APP_USER" /var/log/lumina

# ImageMagick on Debian often blocks PDF by default.
for policy_file in /etc/ImageMagick-*/policy.xml; do
  [[ -f "$policy_file" ]] || continue
  sed -i 's|<policy domain="coder" rights="none" pattern="PDF" />|<policy domain="coder" rights="read|write" pattern="PDF" />|g' "$policy_file" || true
done

# Initialize DB only if missing.
if [[ ! -f "$INSTALL_DIR/lumina.db" ]]; then
  sudo -u "$APP_USER" "$INSTALL_DIR/venv/bin/python" -c "import sys; sys.path.insert(0, '$INSTALL_DIR'); from app import init_db; init_db()"
fi

if [[ -n "$KIOSK_USER" ]]; then
  mkdir -p /etc/xdg/autostart
  cat > /etc/xdg/autostart/lumina-player.desktop <<EOF
[Desktop Entry]
Type=Application
Name=LuminaShow Player
Exec=sh -c '(command -v chromium-browser >/dev/null && chromium-browser --kiosk --incognito --noerrdialogs --disable-session-crashed-bubble http://localhost/player) || (command -v chromium >/dev/null && chromium --kiosk --incognito --noerrdialogs --disable-session-crashed-bubble http://localhost/player)'
X-GNOME-Autostart-enabled=true
OnlyShowIn=LXDE;
EOF

  # Ensure kiosk user can auto-login in Raspberry Pi OS Desktop.
  if [[ -f /etc/lightdm/lightdm.conf ]]; then
    if grep -q '^autologin-user=' /etc/lightdm/lightdm.conf; then
      sed -i "s/^autologin-user=.*/autologin-user=$KIOSK_USER/" /etc/lightdm/lightdm.conf
    else
      printf "\n[Seat:*]\nautologin-user=%s\nautologin-user-timeout=0\n" "$KIOSK_USER" >> /etc/lightdm/lightdm.conf
    fi
  fi
fi

systemctl daemon-reload
systemctl enable lumina.service
systemctl restart lumina.service
systemctl enable nginx
systemctl restart nginx

ip_addr="$(hostname -I | awk '{print $1}')"
echo ""
echo "LuminaShow installed for Raspberry Pi."
echo "Open: http://${ip_addr:-localhost}"
echo "Default login: admin / admin123"
