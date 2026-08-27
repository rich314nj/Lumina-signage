#!/bin/bash -e

# Stage the repository snapshot into the image. The actual install runs in
# the chroot (00-run-chroot.sh) so the finished image needs no network on
# first boot.
install -d "${ROOTFS_DIR}/opt/lumina-bootstrap"
install -m 0644 files/lumina-signage.tar.gz "${ROOTFS_DIR}/opt/lumina-bootstrap/lumina-signage.tar.gz"
