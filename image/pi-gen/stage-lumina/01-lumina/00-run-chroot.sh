#!/bin/bash -e

# Install LuminaShow into the image at build time. Doing the virtualenv and
# pip install here (rather than on first boot) means a flashed device comes
# up playing content with no internet connection at all — the previous
# first-boot installer aborted silently whenever the network was missing.

mkdir -p /opt/lumina-src
tar -xzf /opt/lumina-bootstrap/lumina-signage.tar.gz -C /opt/lumina-src

cd /opt/lumina-src
chmod +x install_rpi.sh
bash ./install_rpi.sh \
  --non-interactive \
  --skip-apt \
  --no-start \
  --kiosk-user "${FIRST_USER_NAME:-pi}"

# The session signing key is baked in at build time, so every device flashed
# from this image would share it. Replace it once, on first boot.
cat > /usr/local/sbin/lumina-firstboot.sh <<'FIRSTBOOT'
#!/usr/bin/env bash
set -euo pipefail

if [ -f /etc/lumina-firstboot.done ]; then
  exit 0
fi

KEY="$(openssl rand -hex 32)"
if [ -f /opt/lumina-signage/.env ]; then
  sed -i "s|^SECRET_KEY=.*|SECRET_KEY=${KEY}|" /opt/lumina-signage/.env
fi
if [ -f /etc/systemd/system/lumina.service ]; then
  sed -i "s|^Environment=SECRET_KEY=.*|Environment=SECRET_KEY=${KEY}|" /etc/systemd/system/lumina.service
  systemctl daemon-reload
fi

touch /etc/lumina-firstboot.done
FIRSTBOOT
chmod 0755 /usr/local/sbin/lumina-firstboot.sh

cat > /etc/systemd/system/lumina-firstboot.service <<'UNIT'
[Unit]
Description=LuminaShow first boot setup
Before=lumina.service
ConditionPathExists=!/etc/lumina-firstboot.done

[Service]
Type=oneshot
ExecStart=/usr/local/sbin/lumina-firstboot.sh
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
UNIT

install -d /etc/systemd/system/multi-user.target.wants
ln -sf /etc/systemd/system/lumina-firstboot.service \
  /etc/systemd/system/multi-user.target.wants/lumina-firstboot.service

rm -rf /opt/lumina-src /opt/lumina-bootstrap
