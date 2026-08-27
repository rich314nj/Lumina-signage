#!/usr/bin/env bash
set -euo pipefail

# Build a Raspberry Pi OS image with LuminaShow preinstalled.
# This script wraps pi-gen and injects a custom stage.

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
WORK_DIR="${ROOT_DIR}/.build/pi-gen"
PIGEN_DIR="${WORK_DIR}/pi-gen"
CUSTOM_STAGE_SRC="${ROOT_DIR}/image/pi-gen/stage-lumina"
CUSTOM_STAGE_DST="${PIGEN_DIR}/stage-lumina"
LUMINA_SRC_DIR="${ROOT_DIR}"

IMG_NAME="${IMG_NAME:-lumina-rpi}"
RELEASE="${RELEASE:-bookworm}"
# 64-bit images come from pi-gen's arm64 release branches (there is no ARCH
# config variable) — Pi 4/5 need arm64.
PIGEN_BRANCH="${PIGEN_BRANCH:-bookworm-arm64}"
DEPLOY_COMPRESSION="${DEPLOY_COMPRESSION:-zip}"
FIRST_USER_NAME="${FIRST_USER_NAME:-pi}"
FIRST_USER_PASS="${FIRST_USER_PASS:-lumina}"
ENABLE_SSH="${ENABLE_SSH:-1}"
TARGET_HOSTNAME="${TARGET_HOSTNAME:-lumina}"
# Raspberry Pi OS soft-blocks the WiFi radio until a wireless regulatory
# country is set. Without this the radio is rfkill-blocked on a fresh image:
# no scanning, no setup hotspot, and no WiFi at all. Two-letter ISO 3166-1
# code — override for builds outside the US.
WPA_COUNTRY="${WPA_COUNTRY:-US}"
TIMEZONE_DEFAULT="${TIMEZONE_DEFAULT:-America/New_York}"

if [[ "${EUID}" -eq 0 ]]; then
  echo "Run as a regular user with sudo access (not as root)."
  exit 1
fi

mkdir -p "$WORK_DIR"
if [[ ! -d "$PIGEN_DIR/.git" ]]; then
  git clone --branch "$PIGEN_BRANCH" --depth 1 https://github.com/RPi-Distro/pi-gen.git "$PIGEN_DIR"
fi

rm -rf "$CUSTOM_STAGE_DST"
cp -r "$CUSTOM_STAGE_SRC" "$CUSTOM_STAGE_DST"
# Stage scripts must be executable and LF-terminated for pi-gen to run them.
find "$CUSTOM_STAGE_DST" -name '*.sh' -exec sed -i 's/\r$//' {} \; -exec chmod +x {} \;

# Only export the final lumina image, not the intermediate Lite one.
touch "$PIGEN_DIR/stage2/SKIP_IMAGES" 2>/dev/null || true

# Package current repo snapshot for the custom stage.
mkdir -p "$CUSTOM_STAGE_DST/01-lumina/files"
tar -C "$LUMINA_SRC_DIR" \
  --exclude .git \
  --exclude .build \
  --exclude "__pycache__" \
  --exclude "venv" \
  -czf "$CUSTOM_STAGE_DST/01-lumina/files/lumina-signage.tar.gz" .

# Lite base (stage0-2). The signage appliance does not need a desktop: the
# custom stage adds Chromium plus cage, a single-application Wayland
# compositor, and a systemd unit owns the display. That keeps the image about
# half the size of a desktop build and removes the desktop session entirely.
cat > "$PIGEN_DIR/config" <<EOF
IMG_NAME='$IMG_NAME'
RELEASE='$RELEASE'
DEPLOY_COMPRESSION='$DEPLOY_COMPRESSION'
TARGET_HOSTNAME='$TARGET_HOSTNAME'
ENABLE_SSH=$ENABLE_SSH
FIRST_USER_NAME='$FIRST_USER_NAME'
FIRST_USER_PASS='$FIRST_USER_PASS'
WPA_COUNTRY='$WPA_COUNTRY'
TIMEZONE_DEFAULT='$TIMEZONE_DEFAULT'
STAGE_LIST="stage0 stage1 stage2 stage-lumina"
EOF

cat <<EOF
Starting pi-gen build with settings:
  IMG_NAME=$IMG_NAME
  RELEASE=$RELEASE
  PIGEN_BRANCH=$PIGEN_BRANCH
  TARGET_HOSTNAME=$TARGET_HOSTNAME
  FIRST_USER_NAME=$FIRST_USER_NAME
  WPA_COUNTRY=$WPA_COUNTRY
  TIMEZONE_DEFAULT=$TIMEZONE_DEFAULT
EOF

cd "$PIGEN_DIR"
sudo ./build.sh

echo ""
echo "Build complete. Artifacts are in:"
echo "  $PIGEN_DIR/deploy/"
