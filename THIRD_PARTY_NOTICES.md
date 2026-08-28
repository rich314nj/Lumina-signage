# Third-Party Notices

LuminaShow is written by **Richard Rivera** and licensed under the MIT
License (see [`LICENSE`](LICENSE)). It stands on a stack of open-source
software this document exists to credit. None of the projects below are
authored by, affiliated with, or endorse LuminaShow.

---

## Vendored — bundled directly in this repository/image

| Project | License | Where it lives here |
|---|---|---|
| [PDF.js](https://github.com/mozilla/pdf.js) — Mozilla | **Apache License 2.0** | Downloaded by the installers into `static/vendor/pdfjs/` at install time so PDF assets render with no internet connection. Not committed to the repo (see `.gitignore`); fetched fresh from `cdnjs.cloudflare.com` under its original Apache 2.0 terms. |

## Python dependencies (`requirements.txt`)

| Project | License |
|---|---|
| [Flask](https://flask.palletsprojects.com/) | BSD-3-Clause |
| [Flask-SQLAlchemy](https://flask-sqlalchemy.palletsprojects.com/) | BSD-3-Clause |
| [Werkzeug](https://werkzeug.palletsprojects.com/) | BSD-3-Clause |
| [Gunicorn](https://gunicorn.org/) | MIT |
| [qrcode](https://github.com/lincolnloop/python-qrcode) | BSD-3-Clause |

## System software the installer configures LuminaShow to use

These are installed via the OS package manager (`apt`) by `install.sh` /
`install_rpi.sh` — LuminaShow does not bundle or redistribute their binaries,
it depends on them being present on the host. **GNU-licensed components are
marked explicitly**, per request.

| Project | License | Role |
|---|---|---|
| **NetworkManager** | **GNU GPL v2 or later** | Backs the entire Network page — WiFi scan/connect, hostname, DHCP/static IP, the setup hotspot (`nmcli`). |
| **systemd** | **GNU LGPL v2.1 or later** | Process supervision for every LuminaShow service (`lumina.service`, `lumina-kiosk.service`, `lumina-netwatch.service`, the updater's transient units), plus `journald` and `timedatectl`. |
| **FFmpeg** | **GNU LGPL v2.1+ / GPL v2+** (license depends on how your distribution's package was built) | Video thumbnail generation and duration detection. |
| [nginx](https://nginx.org/) | BSD-2-Clause (nginx's own license, permissive) | Reverse proxy, static file serving, upload size handling. |
| [ImageMagick](https://imagemagick.org/) | Apache License 2.0 (ImageMagick License) | PDF thumbnail generation. |
| [cage](https://github.com/cage-kiosk/cage) | MIT | The Wayland kiosk compositor the appliance image runs the player under. |
| [Chromium](https://www.chromium.org/) | BSD-style, with bundled components under their own licenses | The kiosk browser rendering the player. |
| [Raspberry Pi OS](https://www.raspberrypi.com/software/) and [pi-gen](https://github.com/RPi-Distro/pi-gen) | Various (pi-gen itself: BSD-3-Clause) | The base OS and the image-build tooling used to produce the flashable appliance image. Used at build time only — not shipped as part of this repository. |

## Full license texts

This file summarizes; it is not a substitute for each project's own license.
Every project listed publishes its full license text in its own repository —
follow the links above. Where a project's PyPI/OS package includes a bundled
license file, that file governs.

## Inspiration

LuminaShow's feature set was inspired by
[Anthias (formerly Screenly)](https://github.com/Screenly/Anthias), an
excellent open-source digital signage project. No code is shared between the
two; this is a credit, not a license obligation.
