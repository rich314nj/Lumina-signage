#!/usr/bin/env bash
# =============================================================================
#  LuminaShow Digital Signage — Installer for Ubuntu 20.04 / 22.04 / 24.04
# =============================================================================
set -euo pipefail

# ── Colors ────────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; RESET='\033[0m'

ok()    { echo -e "${GREEN}  ✓${RESET} $*"; }
info()  { echo -e "${CYAN}  ▷${RESET} $*"; }
warn()  { echo -e "${YELLOW}  ⚠${RESET} $*"; }
error() { echo -e "${RED}  ✕${RESET} $*"; exit 1; }
header(){ echo -e "\n${BOLD}${CYAN}── $* ──${RESET}"; }

# Wait for apt lock (common on Ubuntu Desktop due to unattended-upgrades)
wait_for_apt() {
  local waited=0
  while fuser /var/lib/dpkg/lock-frontend /var/lib/apt/lists/lock /var/cache/apt/archives/lock \
        >/dev/null 2>&1; do
    if [ $waited -eq 0 ]; then
      info "Waiting for apt lock (unattended-upgrades may be running)…"
    fi
    sleep 3
    waited=$((waited + 3))
    if [ $waited -ge 120 ]; then
      error "apt lock held for >2 minutes. Run: sudo systemctl stop unattended-upgrades"
    fi
  done
}

# ── Banner ────────────────────────────────────────────────────────────────────
cat << 'EOF'

  ╔══════════════════════════════════════════════════════╗
  ║                                                      ║
  ║   ██╗     ██╗   ██╗███╗   ███╗██╗███╗   ██╗ █████╗  ║
  ║   ██║     ██║   ██║████╗ ████║██║████╗  ██║██╔══██╗ ║
  ║   ██║     ██║   ██║██╔████╔██║██║██╔██╗ ██║███████║ ║
  ║   ██║     ██║   ██║██║╚██╔╝██║██║██║╚██╗██║██╔══██║ ║
  ║   ███████╗╚██████╔╝██║ ╚═╝ ██║██║██║ ╚████║██║  ██║ ║
  ║   ╚══════╝ ╚═════╝ ╚═╝     ╚═╝╚═╝╚═╝  ╚═══╝╚═╝  ╚═╝ ║
  ║                                                      ║
  ║          C A S T   ·   Digital Signage               ║
  ║             Ubuntu Installer  v1.2                   ║
  ╚══════════════════════════════════════════════════════╝

EOF

# ── Checks ────────────────────────────────────────────────────────────────────
header "Pre-flight checks"

if [[ $EUID -ne 0 ]]; then
  error "Run as root: sudo bash install.sh"
fi

# Detect Ubuntu
if ! grep -qi ubuntu /etc/os-release 2>/dev/null; then
  warn "This script targets Ubuntu. Proceeding anyway…"
fi

UBUNTU_VER=$(lsb_release -rs 2>/dev/null || echo "unknown")
ok "Detected Ubuntu $UBUNTU_VER"

# ── Variables ─────────────────────────────────────────────────────────────────
INSTALL_DIR="/opt/lumina-signage"
APP_USER="lumina"
APP_PORT="${LUMINA_PORT:-8080}"
SECRET_KEY=$(openssl rand -hex 32)
LOG_DIR="/var/log/lumina"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo ""
echo -e "  Install directory : ${BOLD}${INSTALL_DIR}${RESET}"
echo -e "  Application user  : ${BOLD}${APP_USER}${RESET}"
echo -e "  Port              : ${BOLD}${APP_PORT}${RESET}"
echo ""

# Confirm
read -rp "  Proceed with installation? [Y/n]: " CONFIRM
CONFIRM="${CONFIRM:-Y}"
if [[ ! "$CONFIRM" =~ ^[Yy]$ ]]; then
  echo "Installation cancelled."
  exit 0
fi

# ── Upgrade detection ─────────────────────────────────────────────────────────
UPGRADE=false
if [ -f "$INSTALL_DIR/app.py" ]; then
  warn "Existing LuminaShow installation detected at $INSTALL_DIR"
  echo ""
  echo -e "  ${BOLD}Options:${RESET}"
  echo -e "    [U] Upgrade  — patch application files, keep database and uploads"
  echo -e "    [R] Reinstall — full clean install (database and uploads will be wiped)"
  echo -e "    [C] Cancel"
  echo ""
  read -rp "  Choice [U/r/c]: " INSTALL_MODE
  INSTALL_MODE="${INSTALL_MODE:-U}"
  case "${INSTALL_MODE^^}" in
    U) UPGRADE=true; info "Upgrade mode — preserving database and uploads" ;;
    R) warn "Reinstall mode — all existing data will be replaced" ;;
    *) echo "Installation cancelled."; exit 0 ;;
  esac
fi

# ── System packages ───────────────────────────────────────────────────────────
header "Updating system packages"
wait_for_apt
apt-get update -qq
ok "Package lists updated"

header "Installing system dependencies"

PACKAGES=(
  python3
  python3-pip
  python3-venv
  python3-dev
  build-essential
  ffmpeg
  nginx
  curl
  wget
  git
  rsync
  openssl
  libssl-dev
  libjpeg-dev
  libpng-dev
  libwebp-dev
  imagemagick
)

wait_for_apt
apt-get install -y -qq "${PACKAGES[@]}" > /dev/null 2>&1
ok "System packages installed"

# Verify ffmpeg
if command -v ffmpeg &>/dev/null; then
  FFMPEG_VER=$(ffmpeg -version 2>&1 | head -1 | awk '{print $3}')
  ok "FFmpeg $FFMPEG_VER installed"
else
  warn "FFmpeg not found — video thumbnail generation will be disabled"
fi

# Verify ImageMagick and fix PDF policy (Ubuntu ships with PDF disabled by default)
IM_BIN=""
if command -v magick &>/dev/null; then
  IM_BIN="magick"
  ok "ImageMagick 7 (magick) installed — PDF thumbnails enabled"
elif command -v convert &>/dev/null; then
  IM_BIN="convert"
  ok "ImageMagick 6 (convert) installed — PDF thumbnails enabled"
else
  warn "ImageMagick not found — PDF thumbnails will be disabled (install with: sudo apt install imagemagick)"
fi

# Ubuntu's ImageMagick policy.xml disables PDF by default — fix it
for policy_file in /etc/ImageMagick-*/policy.xml; do
  if [ -f "$policy_file" ]; then
    # Change policy for PDF from "none" to "read|write"
    if grep -q 'pattern="PDF"' "$policy_file"; then
      sed -i 's|<policy domain="coder" rights="none" pattern="PDF" />|<policy domain="coder" rights="read|write" pattern="PDF" />|g' "$policy_file" 2>/dev/null || true
      ok "ImageMagick PDF policy enabled ($policy_file)"
    fi
  fi
done

# ── Create user ───────────────────────────────────────────────────────────────
header "Creating application user"

if ! id "$APP_USER" &>/dev/null; then
  useradd --system --no-create-home --shell /bin/false "$APP_USER"
  ok "Created system user: $APP_USER"
else
  ok "User $APP_USER already exists"
fi

# ── Install application ───────────────────────────────────────────────────────
header "Installing LuminaShow application"

# Create directories
mkdir -p "$INSTALL_DIR"
mkdir -p "$INSTALL_DIR/static/uploads/thumbnails"
mkdir -p "$LOG_DIR"
ok "Created directories"

# Copy application files
if [ -d "$SCRIPT_DIR" ] && [ -f "$SCRIPT_DIR/app.py" ]; then
  if [ "$UPGRADE" = true ]; then
    # Upgrade: copy everything EXCEPT the database and uploads
    info "Patching application files (preserving database and uploads)…"
    # Stop service before patching
    systemctl stop lumina.service 2>/dev/null || true
    rsync -a --exclude='lumina.db' \
              --exclude='static/uploads' \
              --exclude='.env' \
              --exclude='venv' \
              "$SCRIPT_DIR/" "$INSTALL_DIR/"
    ok "Application files patched"
  else
    cp -r "$SCRIPT_DIR/." "$INSTALL_DIR/"
    ok "Copied application files"
  fi
else
  error "Cannot find application files. Run install.sh from the lumina-signage directory."
fi

# Create Python virtual environment
info "Creating Python virtual environment…"
python3 -m venv "$INSTALL_DIR/venv"
ok "Virtual environment created"

# Install Python dependencies
info "Installing Python packages…"
"$INSTALL_DIR/venv/bin/pip" install --quiet --upgrade pip
"$INSTALL_DIR/venv/bin/pip" install --quiet -r "$INSTALL_DIR/requirements.txt"
ok "Python packages installed"

# ── Configure ─────────────────────────────────────────────────────────────────
header "Configuring application"

# Write environment file
cat > "$INSTALL_DIR/.env" << ENV
SECRET_KEY=${SECRET_KEY}
PORT=${APP_PORT}
DEBUG=false
ENV
chmod 600 "$INSTALL_DIR/.env"
ok "Environment file created"

# Update service file with correct port
cp "$INSTALL_DIR/lumina.service" /etc/systemd/system/lumina.service
sed -i "s|Environment=SECRET_KEY=CHANGE_ME_IN_PRODUCTION|Environment=SECRET_KEY=${SECRET_KEY}|g" /etc/systemd/system/lumina.service
sed -i "s|Environment=PORT=8080|Environment=PORT=${APP_PORT}|g" /etc/systemd/system/lumina.service
sed -i "s|--bind 0.0.0.0:8080|--bind 0.0.0.0:${APP_PORT}|g" /etc/systemd/system/lumina.service
ok "Systemd service configured"

# ── Nginx ─────────────────────────────────────────────────────────────────────
header "Configuring Nginx reverse proxy"

# Check for port 80 conflicts (Apache2 common on Ubuntu Desktop)
if systemctl is-active --quiet apache2 2>/dev/null; then
  warn "Apache2 is running and using port 80."
  read -rp "  Stop and disable Apache2 to free port 80? [Y/n]: " STOP_APACHE
  STOP_APACHE="${STOP_APACHE:-Y}"
  if [[ "$STOP_APACHE" =~ ^[Yy]$ ]]; then
    systemctl stop apache2
    systemctl disable apache2
    ok "Apache2 stopped and disabled"
  else
    warn "Leaving Apache2 running — Nginx may fail to bind port 80. You can change the port later."
  fi
fi

cat > /etc/nginx/sites-available/lumina << NGINX
server {
    listen 80;
    server_name _;

    # Max upload size (2GB for large video files)
    client_max_body_size 2048M;
    proxy_read_timeout 300;
    proxy_connect_timeout 300;
    proxy_send_timeout 300;

    location /static/ {
        alias ${INSTALL_DIR}/static/;
        expires 7d;
        add_header Cache-Control "public, immutable";
    }

    location / {
        proxy_pass http://127.0.0.1:${APP_PORT};
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_buffering off;
    }
}
NGINX

# Enable site
ln -sf /etc/nginx/sites-available/lumina /etc/nginx/sites-enabled/lumina

# Remove default nginx site only if it exists and points to the default nginx page
if [ -L /etc/nginx/sites-enabled/default ]; then
  DEFAULT_TARGET=$(readlink /etc/nginx/sites-enabled/default)
  if echo "$DEFAULT_TARGET" | grep -q "default$"; then
    rm -f /etc/nginx/sites-enabled/default
    ok "Removed nginx default site"
  else
    warn "Skipped removing nginx default site — it points to a custom config ($DEFAULT_TARGET)"
  fi
fi

# Test nginx config
if nginx -t -q 2>/dev/null; then
  ok "Nginx configuration valid"
else
  warn "Nginx configuration test failed — check /etc/nginx/sites-available/lumina"
fi

# ── Permissions ───────────────────────────────────────────────────────────────
header "Setting permissions"

chown -R "$APP_USER:$APP_USER" "$INSTALL_DIR"
chown -R "$APP_USER:$APP_USER" "$LOG_DIR"
chmod +x "$INSTALL_DIR/app.py"
ok "Permissions set"

# ── Initialize database ───────────────────────────────────────────────────────
header "Initializing database"

if [ "$UPGRADE" = true ] && [ -f "$INSTALL_DIR/lumina.db" ]; then
  ok "Existing database preserved — skipping initialization"
else
  cd "$INSTALL_DIR"
  sudo -u "$APP_USER" "$INSTALL_DIR/venv/bin/python" -c "
import sys; sys.path.insert(0, '${INSTALL_DIR}')
from app import init_db
init_db()
print('Database initialized')
"
  ok "Database created with default admin user"
fi

# ── Start services ─────────────────────────────────────────────────────────────
header "Starting services"

systemctl daemon-reload
systemctl enable lumina.service
systemctl start lumina.service
sleep 2

if systemctl is-active --quiet lumina.service; then
  ok "LuminaShow service started"
else
  warn "LuminaShow service failed to start. Check: journalctl -u lumina"
fi

systemctl enable nginx
systemctl restart nginx

if systemctl is-active --quiet nginx; then
  ok "Nginx started"
else
  warn "Nginx failed to start. Check: journalctl -u nginx"
fi

# ── Firewall ──────────────────────────────────────────────────────────────────
header "Configuring firewall"

if command -v ufw &>/dev/null; then
  ufw allow 80/tcp > /dev/null 2>&1 || true
  ufw allow 443/tcp > /dev/null 2>&1 || true
  ok "UFW rules added (port 80, 443)"
else
  info "UFW not found — configure your firewall manually to allow port 80"
fi

# ── Get server IP ──────────────────────────────────────────────────────────────
SERVER_IP=$(hostname -I | awk '{print $1}')

# ── Done ───────────────────────────────────────────────────────────────────────
if [ "$UPGRADE" = true ]; then
cat << DONE

  ${GREEN}${BOLD}╔══════════════════════════════════════════════════════╗
  ║       Upgrade to v1.2 Complete! 🎉                   ║
  ╚══════════════════════════════════════════════════════╝${RESET}

  ${BOLD}What's new in v1.2:${RESET}
    • PDF support — upload and display PDFs page-by-page
    • Dark / Light mode toggle — persists across sessions
    • ImageMagick PDF thumbnail generation

  ${BOLD}Access LuminaShow:${RESET}
  ┌──────────────────────────────────────────────────┐
  │  URL      →  http://${SERVER_IP}
  └──────────────────────────────────────────────────┘

  ${BOLD}Useful commands:${RESET}
    Status   : sudo systemctl status lumina
    Logs     : sudo journalctl -u lumina -f
    Restart  : sudo systemctl restart lumina

  ${BOLD}Ubuntu Desktop — open player in kiosk mode:${RESET}
    chromium-browser --kiosk http://localhost/player
    google-chrome    --kiosk http://localhost/player

DONE
else
cat << DONE

  ${GREEN}${BOLD}╔══════════════════════════════════════════════════════╗
  ║          Installation Complete! 🎉                   ║
  ╚══════════════════════════════════════════════════════╝${RESET}

  ${BOLD}Access LuminaShow:${RESET}
  ┌──────────────────────────────────────────────────┐
  │  URL      →  http://${SERVER_IP}
  │  Username →  admin
  │  Password →  admin123
  └──────────────────────────────────────────────────┘

  ${YELLOW}⚠  Change the default password immediately after login!${RESET}

  ${BOLD}Useful commands:${RESET}
    Status   : sudo systemctl status lumina
    Logs     : sudo journalctl -u lumina -f
    Restart  : sudo systemctl restart lumina
    Stop     : sudo systemctl stop lumina

  ${BOLD}File locations:${RESET}
    App      : ${INSTALL_DIR}
    Uploads  : ${INSTALL_DIR}/static/uploads/
    Logs     : ${LOG_DIR}/
    Config   : ${INSTALL_DIR}/.env

  ${BOLD}Ubuntu Desktop — open player in kiosk mode:${RESET}
    chromium-browser --kiosk http://localhost/player
    google-chrome    --kiosk http://localhost/player

DONE
fi
