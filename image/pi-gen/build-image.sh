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
ARCH="${ARCH:-arm64}"
DEPLOY_ZIP="${DEPLOY_ZIP:-1}"
FIRST_USER_NAME="${FIRST_USER_NAME:-pi}"
FIRST_USER_PASS="${FIRST_USER_PASS:-lumina}"
ENABLE_SSH="${ENABLE_SSH:-1}"
TARGET_HOSTNAME="${TARGET_HOSTNAME:-lumina}"

if [[ "${EUID}" -eq 0 ]]; then
  echo "Run as a regular user with sudo access (not as root)."
  exit 1
fi

mkdir -p "$WORK_DIR"
if [[ ! -d "$PIGEN_DIR/.git" ]]; then
  git clone https://github.com/RPi-Distro/pi-gen.git "$PIGEN_DIR"
fi

rm -rf "$CUSTOM_STAGE_DST"
cp -r "$CUSTOM_STAGE_SRC" "$CUSTOM_STAGE_DST"

# Package current repo snapshot for the custom stage.
mkdir -p "$CUSTOM_STAGE_DST/01-lumina/files"
tar -C "$LUMINA_SRC_DIR" \
  --exclude .git \
  --exclude .build \
  --exclude "__pycache__" \
  --exclude "venv" \
  -czf "$CUSTOM_STAGE_DST/01-lumina/files/lumina-signage.tar.gz" .

cat > "$PIGEN_DIR/config" <<EOF
IMG_NAME='$IMG_NAME'
RELEASE='$RELEASE'
ARCH='$ARCH'
DEPLOY_ZIP=$DEPLOY_ZIP
TARGET_HOSTNAME='$TARGET_HOSTNAME'
ENABLE_SSH=$ENABLE_SSH
FIRST_USER_NAME='$FIRST_USER_NAME'
FIRST_USER_PASS='$FIRST_USER_PASS'
STAGE_LIST="stage0 stage1 stage2 stage-lumina"
EOF

cat <<EOF
Starting pi-gen build with settings:
  IMG_NAME=$IMG_NAME
  RELEASE=$RELEASE
  ARCH=$ARCH
  TARGET_HOSTNAME=$TARGET_HOSTNAME
  FIRST_USER_NAME=$FIRST_USER_NAME
EOF

cd "$PIGEN_DIR"
sudo ./build.sh

echo ""
echo "Build complete. Artifacts are in:"
echo "  $PIGEN_DIR/deploy/"
