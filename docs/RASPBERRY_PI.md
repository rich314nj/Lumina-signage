# Raspberry Pi 4/5 Support

LuminaShow ships as a signage **appliance image**: flash it, plug it in, and the
screen tells you what to do next. No keyboard, monitor, or SSH required for
normal setup.

## Supported targets

- Raspberry Pi 4 (2GB+ recommended)
- Raspberry Pi 5 (4GB+ recommended)
- Raspberry Pi OS Bookworm, 64-bit

The image is built from Raspberry Pi OS **Lite** — there is no desktop. The
player runs under `cage`, a single-application Wayland compositor, started by
`lumina-kiosk.service`.

---

## Setting up a screen (the normal path)

1. **Flash the image** to an 8GB+ card with Raspberry Pi Imager (Choose OS →
   Use custom) or balenaEtcher.
2. **Plug in HDMI and power.** Ethernet is optional.
3. **Wait for the setup screen.** The TV shows large numbered instructions.

What it shows depends on how the device is connected:

**If it has a network** (Ethernet, or WiFi it already knows) it displays its
address, e.g. `http://192.168.1.42`. Open that from any computer or phone on
the same network, sign in, and start adding content.

**If it has no network and no Ethernet cable** it starts its own WiFi hotspot
and tells you:

| | |
|---|---|
| WiFi network | `LuminaShow-Setup` |
| Password | `luminasetup` |
| Then open | `http://10.42.0.1` |

Connect a phone or laptop to that hotspot, open the address, sign in, go to
**Network**, and pick your WiFi network. The device joins it, the hotspot
disappears, and the screen updates with its new address.

> The hotspot is strictly a fallback for wireless-only sites. If an Ethernet
> cable is plugged in, it never appears — even while the wired connection is
> still waiting for a DHCP address — and plugging a cable in later shuts it
> down. Disable it entirely with `--no-setup-ap` at install time.

> Default web login is `admin` / `admin123`. Change it under **Users** right
> after the first sign-in.

### Moving a screen to a different network

Take the device to the new site and power it on. When it cannot find its old
network it falls back to the `LuminaShow-Setup` hotspot automatically, so you
repeat the steps above from a phone. This is the workflow that comparable
projects require a keyboard and monitor for.

You can also change WiFi, switch between DHCP and a static IP, or rename the
device from **Network** in the admin UI at any time while it is reachable.

---

## Option 2: Install on an existing Raspberry Pi OS

Works on both Lite and Desktop installs; the installer detects which and sets
up the kiosk accordingly.

```bash
git clone https://github.com/rich314nj/Lumina-signage.git
cd Lumina-signage
sudo bash install_rpi.sh --kiosk-user pi
```

What this does:

- Installs runtime dependencies (Python, FFmpeg, Nginx, ImageMagick, Chromium)
- Installs Lumina at `/opt/lumina-signage`
- Creates and enables `lumina.service` and the Nginx reverse proxy on port `80`
- Sets up the kiosk display and the WiFi setup hotspot fallback

Useful flags:

| Flag | Effect |
|------|--------|
| `--kiosk-user <name>` | Install the kiosk display for this user |
| `--no-setup-ap` | Skip the WiFi setup hotspot |
| `--non-interactive` | No prompts (automation) |
| `--no-start` | Enable services without starting them (image builds) |
| `--port <n>` | App port (default 8080, behind Nginx on 80) |

---

## Option 3: Build the SD-card image yourself

Uses `pi-gen` with the custom stage in this repo. The install happens inside
the build chroot, which is why the finished image needs no network on first
boot.

### Prerequisites

- An **arm64 Linux host** (a Pi itself, or an arm64 VM/runner). Cross-building
  under qemu is not supported — `qemu-user-static` segfaults configuring arm64
  packages in the chroot.
- sudo access and 30GB+ free disk space

### Build

```bash
cd image/pi-gen
./build-image.sh
```

Artifacts land in `.build/pi-gen/pi-gen/deploy/`.

---

## CI automation

GitHub Actions workflow: `.github/workflows/pi-image-ci.yml`

- Pull requests: shell syntax + `shellcheck` smoke tests
- Push to `main`: smoke tests + full `pi-gen` image build on a native arm64
  runner (~10 minutes)
- Weekly schedule and manual `workflow_dispatch` runs

Download the finished image from the run's **Artifacts** section. It is a zip
containing pi-gen's deploy zip — extract both to reach the `.img`.

---

## Service commands

```bash
sudo systemctl status lumina           # web app
sudo systemctl status lumina-kiosk     # on-screen player
sudo systemctl status lumina-netwatch  # WiFi setup hotspot
sudo journalctl -u lumina -f
```

### The screen is blank or stuck

```bash
sudo systemctl restart lumina-kiosk
```

### Change the setup hotspot name or password

Edit `/etc/lumina/setup-ap.env`, then:

```bash
sudo nmcli connection delete lumina-setup-ap
sudo systemctl restart lumina-netwatch
```
