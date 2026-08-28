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
NO_START=false
SETUP_AP=true
# Two-letter ISO 3166-1 code. Raspberry Pi OS keeps the WiFi radio
# rfkill-blocked until a regulatory country is set.
WIFI_COUNTRY="${LUMINA_WIFI_COUNTRY:-US}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Resolved after argument parsing, so an existing key can be reused.
SECRET_KEY="${LUMINA_SECRET_KEY:-}"
REPROVISION=false

usage() {
  cat <<EOF
Usage: sudo bash install_rpi.sh [options]

Options:
  --port <port>              App port (default: 8080)
  --install-dir <path>       Install directory (default: /opt/lumina-signage)
  --kiosk-user <username>    Install kiosk autostart desktop file for this user
  --non-interactive          Run without prompts (for automation / image build)
  --skip-apt                 Skip apt update/install (if already provisioned)
  --no-start                 Enable services but do not start them (image build)
  --no-setup-ap              Do not install the WiFi setup-hotspot fallback
  --reprovision              Rewrite service units, nginx config, and helpers
                             for an install whose code is already in place.
                             Preserves the database, uploads, and secret key.
                             Used by lumina-update.
  --wifi-country <cc>        Wireless regulatory country (default: US).
                             Required for WiFi to work at all; use "" to skip.
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
    --no-start)
      NO_START=true
      shift
      ;;
    --no-setup-ap)
      SETUP_AP=false
      shift
      ;;
    --reprovision)
      REPROVISION=true
      SKIP_APT=true
      NON_INTERACTIVE=true
      shift
      ;;
    --wifi-country)
      WIFI_COUNTRY="$2"
      shift 2
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

# shellcheck disable=SC1091  # /etc/os-release only exists on the target system
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

# --reprovision rewrites the unit files, nginx config, and helpers for an
# install whose code is already in place. The updater uses it, because those
# files are generated here and would otherwise never be refreshed by an
# update — a device could run new code under an old systemd unit.
if [[ "$REPROVISION" != true ]]; then
  rsync -a \
    --exclude '.git' \
    --exclude '__pycache__' \
    --exclude 'venv' \
    --exclude 'static/vendor' \
    --exclude 'lumina.db' \
    "$SCRIPT_DIR/" "$INSTALL_DIR/"

  python3 -m venv "$INSTALL_DIR/venv"
  "$INSTALL_DIR/venv/bin/pip" install --upgrade pip
  "$INSTALL_DIR/venv/bin/pip" install -r "$INSTALL_DIR/requirements.txt"
fi

# Reuse the existing key rather than minting a new one. Regenerating it logs
# every user out, and if only one of .env and the systemd unit were rewritten
# they would disagree about the key entirely.
if [[ -z "$SECRET_KEY" && -f "$INSTALL_DIR/.env" ]]; then
  SECRET_KEY="$(grep -m1 '^SECRET_KEY=' "$INSTALL_DIR/.env" | cut -d= -f2- || true)"
fi
if [[ -z "$SECRET_KEY" ]]; then
  SECRET_KEY="$(openssl rand -hex 32)"
fi

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

# Network management helper: the app's Network page calls this via sudo.
# The sudoers grant is limited to exactly this script.
if [[ -f "$INSTALL_DIR/scripts/lumina-net" ]]; then
  install -m 0755 "$INSTALL_DIR/scripts/lumina-net" /usr/local/sbin/lumina-net
  sed -i 's/\r$//' /usr/local/sbin/lumina-net
  cat > /etc/sudoers.d/lumina-net <<EOF
$APP_USER ALL=(root) NOPASSWD: /usr/local/sbin/lumina-net
EOF
  chmod 0440 /etc/sudoers.d/lumina-net
fi

# Device power control, invoked from the admin UI through its own scoped grant.
if [[ -f "$INSTALL_DIR/scripts/lumina-power" ]]; then
  install -m 0755 "$INSTALL_DIR/scripts/lumina-power" /usr/local/sbin/lumina-power
  sed -i 's/\r$//' /usr/local/sbin/lumina-power
  cat > /etc/sudoers.d/lumina-power <<EOF
$APP_USER ALL=(root) NOPASSWD: /usr/local/sbin/lumina-power
EOF
  chmod 0440 /etc/sudoers.d/lumina-power
fi

# Vendor PDF.js so PDF assets render with no internet at playback time.
# Downloaded here rather than committed to the repo; the player falls back to
# the CDN if this could not be fetched.
PDFJS_VERSION="3.11.174"
PDFJS_DIR="$INSTALL_DIR/static/vendor/pdfjs"
mkdir -p "$PDFJS_DIR"
for pdfjs_file in pdf.min.js pdf.worker.min.js; do
  [[ -s "$PDFJS_DIR/$pdfjs_file" ]] && continue
  curl -fsSL --max-time 60 -o "$PDFJS_DIR/$pdfjs_file" \
    "https://cdnjs.cloudflare.com/ajax/libs/pdf.js/${PDFJS_VERSION}/${pdfjs_file}" || true
done
if [[ ! -s "$PDFJS_DIR/pdf.min.js" ]]; then
  echo "Warning: could not download PDF.js. PDF assets will need internet at playback."
fi

# In-place updater, invoked from the admin UI through its own scoped grant.
if [[ -f "$INSTALL_DIR/scripts/lumina-update" ]]; then
  install -m 0755 "$INSTALL_DIR/scripts/lumina-update" /usr/local/sbin/lumina-update
  sed -i 's/\r$//' /usr/local/sbin/lumina-update
  cat > /etc/sudoers.d/lumina-update <<EOF
$APP_USER ALL=(root) NOPASSWD: /usr/local/sbin/lumina-update
EOF
  chmod 0440 /etc/sudoers.d/lumina-update
  mkdir -p /var/lib/lumina /var/backups/lumina
fi

# ImageMagick on Debian often blocks PDF by default.
for policy_file in /etc/ImageMagick-*/policy.xml; do
  [[ -f "$policy_file" ]] || continue
  sed -i 's|<policy domain="coder" rights="none" pattern="PDF" />|<policy domain="coder" rights="read|write" pattern="PDF" />|g' "$policy_file" || true
done

# Initialize DB only if missing.
if [[ "$REPROVISION" != true ]] && [[ ! -f "$INSTALL_DIR/lumina.db" ]]; then
  sudo -u "$APP_USER" "$INSTALL_DIR/venv/bin/python" -c "import sys; sys.path.insert(0, '$INSTALL_DIR'); from app import init_db; init_db()"
fi

if [[ -n "$KIOSK_USER" ]]; then
  install -m 0755 "$INSTALL_DIR/scripts/lumina-kiosk" /usr/local/bin/lumina-kiosk
  sed -i 's/\r$//' /usr/local/bin/lumina-kiosk

  # Two supported shapes:
  #   Appliance (Raspberry Pi OS Lite + cage) — a systemd unit owns the
  #     display. Deterministic ordering, restartable, no desktop session.
  #   Desktop (Raspberry Pi OS with desktop) — XDG autostart, because the
  #     session manager already owns the display.
  if command -v cage >/dev/null 2>&1 && ! systemctl is-enabled lightdm.service >/dev/null 2>&1; then
    for grp in video render input tty; do
      usermod -aG "$grp" "$KIOSK_USER" 2>/dev/null || true
    done

    cat > /etc/systemd/system/lumina-kiosk.service <<EOF
[Unit]
Description=LuminaShow Kiosk Display
After=lumina.service nginx.service systemd-user-sessions.service getty@tty1.service
Wants=lumina.service
# The console getty owns /dev/tty1. Without this the kiosk starts and keeps
# running, but never becomes the active virtual terminal — so the screen shows
# boot text while the player runs invisibly behind it, and "restart display"
# cannot recover it. Conflicts= makes systemd stop the getty automatically,
# which is what "systemctl stop getty@tty1" did by hand.
Conflicts=getty@tty1.service
# Stop retrying eventually, so a genuine failure surfaces in the Health panel
# instead of cycling forever.
StartLimitIntervalSec=90
StartLimitBurst=5

[Service]
Type=simple
User=$KIOSK_USER
PAMName=login
TTYPath=/dev/tty1
TTYReset=yes
TTYVHangup=yes
# tty-force takes the terminal; tty-fail politely declined and left the
# console in charge of the display.
StandardInput=tty-force
StandardOutput=journal
StandardError=journal
ExecStart=/usr/bin/cage -- /usr/local/bin/lumina-kiosk
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

    # Console blanking would black out the screen after ~10 minutes.
    for cmdline in /boot/firmware/cmdline.txt /boot/cmdline.txt; do
      [[ -f "$cmdline" ]] || continue
      grep -q 'consoleblank=0' "$cmdline" || sed -i '1 s/$/ consoleblank=0/' "$cmdline"
      break
    done
  else
    # No OnlyShowIn here: Raspberry Pi OS Bookworm sessions identify as
    # LXDE-pi-wayfire / wayfire / labwc, so an OnlyShowIn=LXDE entry never runs.
    mkdir -p /etc/xdg/autostart
    cat > /etc/xdg/autostart/lumina-player.desktop <<EOF
[Desktop Entry]
Type=Application
Name=LuminaShow Player
Exec=/usr/local/bin/lumina-kiosk
X-GNOME-Autostart-enabled=true
EOF

    if command -v raspi-config >/dev/null 2>&1; then
      raspi-config nonint do_blanking 1 || true
    fi

    if [[ -f /etc/lightdm/lightdm.conf ]]; then
      if grep -q '^autologin-user=' /etc/lightdm/lightdm.conf; then
        sed -i "s/^autologin-user=.*/autologin-user=$KIOSK_USER/" /etc/lightdm/lightdm.conf
      else
        printf "\n[Seat:*]\nautologin-user=%s\nautologin-user-timeout=0\n" "$KIOSK_USER" >> /etc/lightdm/lightdm.conf
      fi
    fi
  fi
fi

# Unblock the WiFi radio. Raspberry Pi OS ships it rfkill-blocked until a
# wireless regulatory country is set, which leaves the device with no
# scanning, no setup hotspot, and no WiFi at all — and nothing says why.
# Image builds set this through pi-gen's WPA_COUNTRY; this covers installs
# onto an existing system.
if [[ -n "$WIFI_COUNTRY" ]]; then
  if command -v raspi-config >/dev/null 2>&1; then
    raspi-config nonint do_wifi_country "$WIFI_COUNTRY" >/dev/null 2>&1 || true
  fi
  if command -v iw >/dev/null 2>&1; then
    iw reg set "$WIFI_COUNTRY" >/dev/null 2>&1 || true
  fi
  if command -v rfkill >/dev/null 2>&1; then
    rfkill unblock wifi >/dev/null 2>&1 || true
  fi
fi

# WiFi setup hotspot: lets a non-technical user move the device to a new
# network without a keyboard — see scripts/lumina-netwatch.
if [[ "$SETUP_AP" == true ]] && [[ -f "$INSTALL_DIR/scripts/lumina-netwatch" ]]; then
  install -m 0755 "$INSTALL_DIR/scripts/lumina-netwatch" /usr/local/sbin/lumina-netwatch
  sed -i 's/\r$//' /usr/local/sbin/lumina-netwatch
  mkdir -p /etc/lumina
  if [[ ! -f /etc/lumina/setup-ap.env ]]; then
    cat > /etc/lumina/setup-ap.env <<EOF
# Credentials for the fallback setup hotspot shown on the player screen.
LUMINA_AP_SSID=LuminaShow-Setup
LUMINA_AP_PASS=luminasetup
EOF
    chmod 0644 /etc/lumina/setup-ap.env
  fi

  cat > /etc/systemd/system/lumina-netwatch.service <<EOF
[Unit]
Description=LuminaShow WiFi setup hotspot fallback
After=NetworkManager.service
Wants=NetworkManager.service

[Service]
Type=simple
ExecStart=/usr/local/sbin/lumina-netwatch
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF
fi

# Enable a unit, falling back to manual symlinks when systemd is not
# reachable (image builds run inside a chroot).
enable_unit() {
  local unit="$1" target="${2:-multi-user.target}" path=""
  systemctl enable "$unit" >/dev/null 2>&1 && return 0
  for dir in /etc/systemd/system /lib/systemd/system /usr/lib/systemd/system; do
    if [[ -f "$dir/$unit" ]]; then
      path="$dir/$unit"
      break
    fi
  done
  [[ -n "$path" ]] || return 0
  mkdir -p "/etc/systemd/system/${target}.wants"
  ln -sf "$path" "/etc/systemd/system/${target}.wants/$unit"
}

UNITS=(lumina.service nginx.service)
[[ -f /etc/systemd/system/lumina-kiosk.service ]] && UNITS+=(lumina-kiosk.service)
[[ -f /etc/systemd/system/lumina-netwatch.service ]] && UNITS+=(lumina-netwatch.service)

if [[ "$NO_START" == true ]]; then
  for unit in "${UNITS[@]}"; do
    enable_unit "$unit"
  done
  echo ""
  echo "LuminaShow staged into the image (services enabled, not started)."
else
  systemctl daemon-reload
  for unit in "${UNITS[@]}"; do
    enable_unit "$unit"
    systemctl restart "$unit" || true
  done

  ip_addr="$(hostname -I | awk '{print $1}')"
  echo ""
  echo "LuminaShow installed for Raspberry Pi."
  echo "Open: http://${ip_addr:-localhost}"
  echo "Default login: admin / admin123"
fi
