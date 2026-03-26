# Raspberry Pi 4/5 Support

This project now includes Raspberry Pi-specific install and image build tooling.

## Supported targets

- Raspberry Pi 4 (2GB+ recommended)
- Raspberry Pi 5 (4GB+ recommended)
- Raspberry Pi OS Bookworm (64-bit recommended)

## Option 1: Install on an existing Pi

```bash
git clone https://github.com/rich314nj/Lumina-signage.git
cd Lumina-signage
sudo bash install_rpi.sh --kiosk-user pi
```

What this does:

- Installs runtime dependencies (Python, FFmpeg, Nginx, ImageMagick)
- Installs Lumina at `/opt/lumina-signage`
- Creates and enables `lumina.service`
- Configures Nginx reverse proxy on port `80`
- Optionally sets desktop kiosk autostart for Chromium

Open `http://<pi-ip>/` and log in with `admin / admin123`.

## Option 2: Build a preinstalled SD-card image

This uses `pi-gen` and a custom stage included in this repo.

### Build prerequisites (on Linux host)

- Docker installed
- sudo access
- 30GB+ free disk space

### Build command

```bash
cd image/pi-gen
./build-image.sh
```

Artifacts are created in:

```text
.build/pi-gen/pi-gen/deploy/
```

The generated image will:

- boot Raspberry Pi OS
- run a first-boot installer to install Lumina
- enable Lumina and Nginx services
- configure kiosk launch for user `pi`

## CI automation

GitHub Actions workflow: `.github/workflows/pi-image-ci.yml`

- Pull requests: shell syntax + `shellcheck` smoke tests for Pi scripts
- Push to `main`: smoke tests + full `pi-gen` image build
- Weekly schedule: full `pi-gen` image build
- Manual trigger (`workflow_dispatch`): optional full build toggle

## Useful service commands

```bash
sudo systemctl status lumina
sudo journalctl -u lumina -f
sudo systemctl restart lumina
```
