#!/usr/bin/env bash
# LuminaShow Uninstaller
set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RESET='\033[0m'

if [[ $EUID -ne 0 ]]; then
  echo -e "${RED}Run as root: sudo bash uninstall.sh${RESET}"; exit 1
fi

echo -e "${YELLOW}This will remove LuminaShow and all its data.${RESET}"
read -rp "Are you sure? Type 'yes' to confirm: " CONFIRM
if [[ "$CONFIRM" != "yes" ]]; then echo "Cancelled."; exit 0; fi

echo -e "${YELLOW}WARNING: This will delete all uploaded assets!${RESET}"
read -rp "Also delete uploaded files? [y/N]: " DEL_DATA
DEL_DATA="${DEL_DATA:-N}"

systemctl stop lumina.service 2>/dev/null || true
systemctl disable lumina.service 2>/dev/null || true
rm -f /etc/systemd/system/lumina.service
systemctl daemon-reload
echo -e "${GREEN}✓${RESET} Systemd service removed"

rm -f /etc/nginx/sites-enabled/lumina
rm -f /etc/nginx/sites-available/lumina
systemctl reload nginx 2>/dev/null || true
echo -e "${GREEN}✓${RESET} Nginx site removed"

if [[ "$DEL_DATA" =~ ^[Yy]$ ]]; then
  rm -rf /opt/lumina-signage
  rm -rf /var/log/lumina
  echo -e "${GREEN}✓${RESET} Application and data removed"
else
  # Keep uploads, remove only app code
  find /opt/lumina-signage -maxdepth 1 -not -name 'static' -not -path '/opt/lumina-signage' -exec rm -rf {} + 2>/dev/null || true
  echo -e "${GREEN}✓${RESET} Application removed (uploads preserved at /opt/lumina-signage/static/uploads/)"
fi

rm -f /usr/local/sbin/lumina-net /usr/local/sbin/lumina-update
rm -f /usr/local/sbin/lumina-power /usr/local/sbin/lumina-netwatch
rm -f /usr/local/sbin/lumina-backup /usr/local/sbin/lumina-display
rm -f /usr/local/bin/lumina-kiosk
rm -f /etc/sudoers.d/lumina-net /etc/sudoers.d/lumina-update
rm -f /etc/sudoers.d/lumina-power /etc/sudoers.d/lumina-backup /etc/sudoers.d/lumina-display
rm -rf /var/lib/lumina
rm -rf /etc/lumina
rm -f /etc/systemd/journald.conf.d/lumina.conf
systemctl restart systemd-journald 2>/dev/null || true
echo -e "${GREEN}✓${RESET} Helper scripts removed"

userdel lumina 2>/dev/null || true
echo -e "${GREEN}✓${RESET} System user removed"

echo -e "\n${GREEN}LuminaShow uninstalled successfully.${RESET}"
