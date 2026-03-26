#!/bin/bash -e

install -d "${ROOTFS_DIR}/opt/lumina-bootstrap"
install -m 0644 files/lumina-signage.tar.gz "${ROOTFS_DIR}/opt/lumina-bootstrap/lumina-signage.tar.gz"

cat > "${ROOTFS_DIR}/usr/local/sbin/lumina-firstboot-install.sh" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

if [[ -f /etc/lumina-firstboot.done ]]; then
  exit 0
fi

mkdir -p /opt/lumina-src
tar -xzf /opt/lumina-bootstrap/lumina-signage.tar.gz -C /opt/lumina-src

cd /opt/lumina-src
chmod +x install_rpi.sh
bash ./install_rpi.sh --non-interactive --skip-apt --kiosk-user pi

touch /etc/lumina-firstboot.done
rm -rf /opt/lumina-src
EOF

chmod 0755 "${ROOTFS_DIR}/usr/local/sbin/lumina-firstboot-install.sh"

cat > "${ROOTFS_DIR}/etc/systemd/system/lumina-firstboot.service" <<'EOF'
[Unit]
Description=LuminaShow first boot install
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
ExecStart=/usr/local/sbin/lumina-firstboot-install.sh
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
EOF

install -d "${ROOTFS_DIR}/etc/systemd/system/multi-user.target.wants"
ln -sf /etc/systemd/system/lumina-firstboot.service "${ROOTFS_DIR}/etc/systemd/system/multi-user.target.wants/lumina-firstboot.service"
