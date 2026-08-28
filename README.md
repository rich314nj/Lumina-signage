# LuminaShow â€” Digital Signage Platform for Raspberry Pi OS

> A self-hosted, open-source digital signage solution for Raspberry Pi OS â€” inspired by [Anthias/Screenly](https://github.com/Screenly/Anthias). Manage playlists, schedule content, and display media across screens from a sleek web interface.

---

## Table of Contents

- [Features](#features)
- [Supported Media](#supported-media)
- [Requirements](#requirements)
- [Quick Install](#quick-install)
- [Manual Installation](#manual-installation)
- [Project Structure](#project-structure)
- [First Login](#first-login)
- [User Management](#user-management)
- [Managing Assets](#managing-assets)
- [Creating Playlists](#creating-playlists)
- [Scheduling](#scheduling)
- [The Player](#the-player)
- [Upgrading](#upgrading)
- [Uninstalling](#uninstalling)
- [API Reference](#api-reference)
- [Troubleshooting](#troubleshooting)
- [Architecture](#architecture)
- [Changelog](#changelog)
- [License](#license)

---

## Features

- **Drag-and-drop asset management** â€” upload files directly from your browser
- **Rich media support** â€” images, videos, web URLs, YouTube, and Vimeo
- **Playlist builder** â€” drag to reorder, per-item duration override
- **Schedule engine** â€” set playlists to play on specific days and time ranges
- **Full-screen player** â€” smooth fade transitions, keyboard shortcuts, auto-advance
- **Role-based access control** â€” Admin, Editor, and Viewer roles
- **Network management** â€” change hostname, join WiFi, and set DHCP/static IP from the admin UI (Admin only, requires NetworkManager)
- **Zero-keyboard setup** â€” the appliance image falls back to its own `LuminaShow-Setup` WiFi hotspot when it has no network, and the screen itself shows the steps to get connected
- **Nginx reverse proxy** â€” production-ready setup out of the box
- **Systemd service** â€” auto-starts on boot, auto-restarts on failure
- **REST API** â€” full API for automation and custom integrations
- **No cloud required** â€” 100% self-hosted

---

## Supported Media

| Category | Formats |
|----------|---------|
| **Images** | JPG, JPEG, PNG, PNM, GIF, BMP, WEBP |
| **Videos** | AVI, MKV, MOV, MPG, MPEG, MP4, TS, FLV |
| **Streaming** | YouTube URLs, Vimeo URLs |
| **Web** | Any HTTP/HTTPS URL (rendered in iframe) |
| **Documents** | PDF (page-by-page auto-advance) |

> **Video thumbnails** are automatically generated using FFmpeg.
> **YouTube thumbnails** are fetched from YouTube's CDN.
> **Vimeo thumbnails** are fetched via Vumbnail.
> **PDF thumbnails** are generated from the first page using ImageMagick (`sudo apt install imagemagick`).

---

## Requirements

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| OS | Raspberry Pi OS Bookworm (64-bit) | Raspberry Pi OS Bookworm (64-bit) |
| CPU | 1 core | 2+ cores |
| RAM | 512 MB | 2 GB+ |
| Disk | 10 GB | 50 GB+ (for media storage) |
| Python | 3.8 | 3.11+ |
| Network | LAN access | Internet for YouTube/Vimeo |

---

## Quick Install

```bash
# 1. Clone or download
git clone https://github.com/rich314nj/LuminaShow_RPi.git
cd LuminaShow_RPi

# 2. Run installer as root
sudo bash install_rpi.sh
```

The installer will:
- Install all system dependencies (Python 3, FFmpeg, Nginx)
- Create an isolated Python virtualenv
- Create a `lumina` system user
- Configure and start a systemd service
- Set up Nginx as a reverse proxy
- Initialize the database with a default admin account

---

## Manual Installation

Use this if you prefer full control or are running in a container.

### 1. Install system dependencies

```bash
sudo apt update
sudo apt install -y python3 python3-pip python3-venv ffmpeg nginx
```

### 2. Create a virtual environment

```bash
cd /opt/lumina-signage
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Initialize the database

```bash
python app.py  # First run creates DB and default admin
```

### 4. Run with Gunicorn

```bash
venv/bin/gunicorn --bind 0.0.0.0:8080 --workers 2 app:app
```

### 5. Set environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `SECRET_KEY` | Random | Flask session secret â€” **change in production** |
| `PORT` | `8080` | Port to listen on |
| `DEBUG` | `false` | Enable Flask debug mode |

---

## Project Structure

```
lumina-signage/
â”œâ”€â”€ app.py                  # Flask application and REST API (version lives here)
â”œâ”€â”€ requirements.txt        # Python dependencies
â”œâ”€â”€ lumina.service          # Systemd service unit
â”œâ”€â”€ install_rpi.sh          # Raspberry Pi installer script
â”œâ”€â”€ install.sh              # Ubuntu installer script
â”œâ”€â”€ uninstall.sh            # Uninstaller script
â”œâ”€â”€ CLAUDE.md               # Architecture, conventions, roadmap
â”œâ”€â”€ scripts/                # Privileged helpers invoked via a scoped sudoers grant
â”‚   â”œâ”€â”€ lumina-net          # Hostname / WiFi / IP changes
â”‚   â”œâ”€â”€ lumina-kiosk        # Launches the browser for the display
â”‚   â””â”€â”€ lumina-netwatch     # WiFi setup hotspot fallback
â”œâ”€â”€ image/pi-gen/           # SD-card image build (custom pi-gen stage)
â”œâ”€â”€ docs/RASPBERRY_PI.md    # Pi setup and image build documentation
â”œâ”€â”€ templates/              # Flask HTML templates (must be this folder name)
â”‚   â”œâ”€â”€ index.html          # Admin dashboard SPA
â”‚   â”œâ”€â”€ login.html          # Login page
â”‚   â””â”€â”€ player.html         # Full-screen kiosk player
â””â”€â”€ static/
    â”œâ”€â”€ kiosk.html          # Bootstrap page the display loads first
    â””â”€â”€ uploads/            # Uploaded media files (auto-created)
        â””â”€â”€ thumbnails/     # Auto-generated thumbnails
```

> **Important:** The `templates/` directory is required by Flask. The HTML files (`index.html`, `login.html`, `player.html`) must live inside `templates/` â€” not in the project root â€” or the application will fail to start with a `TemplateNotFound` error.

---

## First Login

After installation, open your browser and navigate to:

```
http://<your-server-ip>
```

**Credentials:**

| Field | Value |
|-------|-------|
| Username | `admin` |
| Password | A random password generated for this device during install |

The password is shown once, unauthenticated, on the setup screen (`/player`) and printed at the end of the installer — it stops being shown anywhere the moment you first log in. If you missed it: `sudo cat /etc/lumina/first-boot-password` (only present until first login). Manual local development (`python app.py` without the installer) falls back to `admin123`.

> ⚠️ **Change the password to something memorable** after your first login if you'd like.
> Go to **Users** → click the edit icon next to admin → set a new password.

---

## User Management

LuminaShow has three user roles:

| Role | Permissions |
|------|-------------|
| **Admin** | Full access â€” users, assets, playlists, schedules |
| **Editor** | Manage assets, playlists, and schedules (no user management) |
| **Viewer** | Read-only access â€” view dashboard and player |

### Adding a user

1. Navigate to **Users** (Admin only)
2. Click **+ Add User**
3. Fill in username, email, password, and role
4. Click **Save User**

### Editing a user

Click the **âœŽ** edit icon next to any user. You can change their email, role, active status, and password.

### Disabling a user

Toggle the "Account Active" switch when editing a user. Disabled users cannot log in.

---

## Managing Assets

### Uploading Files

1. Go to **Assets**
2. Click **â†‘ Upload File** or drag files directly onto the upload zone
3. Multiple files can be dropped at once

### Adding URLs / YouTube / Vimeo

1. Click **+ Add URL**
2. Paste any URL:
   - `https://example.com/page` â€” web page
   - `https://www.youtube.com/watch?v=...` â€” YouTube video
   - `https://vimeo.com/123456789` â€” Vimeo video
3. Set a display duration (seconds)
4. Click **Add Asset**

### Editing Assets

Click **âœŽ** on any asset card to rename it or adjust its default duration.

### Deleting Assets

Click **âœ•** on any asset card. Files are permanently deleted from disk.

---

## Creating Playlists

1. Go to **Playlists** â†’ **+ New Playlist**
2. Enter a name and click OK
3. In the editor:
   - **Add assets** from the right panel by clicking **+**
   - **Reorder** items by dragging the â ¿ handle
   - **Override duration** per item using the numeric input
   - Toggle **Loop** to repeat the playlist continuously
   - Toggle **Active** to enable/disable the playlist
4. Click **Save Playlist**

---

## Scheduling

Schedules control which playlist plays at what time.

1. Go to **Schedules** â†’ **+ New Schedule**
2. Configure:
   - **Name** â€” e.g., "Morning Lobby Loop"
   - **Playlist** â€” which playlist to play
   - **Start/End Time** â€” time range (24-hour format)
   - **Days** â€” select active days of the week
3. Click **Save Schedule**

### How scheduling works

- The player checks active schedules every 5 minutes
- The first schedule matching the current day and time wins
- If no schedule matches, the first active playlist plays as a fallback
- Multiple schedules can run different playlists throughout the day

---

## The Player

Access the full-screen player at `http://<server>/player`

### Keyboard shortcuts

| Key | Action |
|-----|--------|
| `â†’` | Next item |
| `â†` | Previous item |
| `Space` | Pause / Resume |
| `F` | Toggle fullscreen |

### Opening a specific playlist

```
http://<server>/player?playlist=<playlist-id>
```

The playlist ID is visible in the API response or URL when editing.

### Kiosk / Display setup

For a dedicated display, configure your browser to:
1. Open `http://<server>/player` on startup
2. Enable kiosk mode with autoplay allowed (e.g., `chromium-browser --kiosk --autoplay-policy=no-user-gesture-required http://...`)

> **Note:** `--autoplay-policy=no-user-gesture-required` is required — without it Chromium blocks autoplay with sound, so video and YouTube items will not start on their own.

On Raspberry Pi, `install_rpi.sh --kiosk-user <user>` sets this up automatically: it installs a `/usr/local/bin/lumina-kiosk` launcher that waits for the server to come up, starts Chromium in kiosk mode with autoplay enabled, and disables screen blanking. Manual autostart example:
```bash
# /etc/xdg/autostart/lumina-player.desktop
[Desktop Entry]
Type=Application
Name=LuminaShow Player
Exec=chromium-browser --kiosk --noerrdialogs --autoplay-policy=no-user-gesture-required http://localhost/player
```

---

## Upgrading

**From the admin UI (recommended):** go to **System**. It shows the installed
version, checks for a newer one, and installs it with one click.

Your database, uploads, and configuration are preserved. The previous version is
backed up to `/var/backups/lumina/` first, and the new version is health checked
after starting — if it fails to install, start, or respond, the update rolls back
automatically.

**From the command line:**

```bash
sudo lumina-update check    # what is installed, and what is available
sudo lumina-update apply    # install the latest version
sudo lumina-update status   # how the last attempt went
```

---

## Uninstalling

```bash
sudo bash uninstall.sh
```

You'll be asked whether to delete uploaded media files.

---

## API Reference

All API endpoints require authentication (session cookie from login).

### Authentication

```bash
curl -c cookies.txt -X POST http://localhost/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}'
```

### Assets

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/assets` | List all assets |
| POST | `/api/assets` | Upload file (multipart) or add URL (JSON) |
| GET | `/api/assets/<id>` | Get single asset |
| PUT | `/api/assets/<id>` | Update asset |
| DELETE | `/api/assets/<id>` | Delete asset |

**Upload a file:**
```bash
curl -b cookies.txt -X POST http://localhost/api/assets \
  -F "file=@/path/to/video.mp4"
```

**Add a URL:**
```bash
curl -b cookies.txt -X POST http://localhost/api/assets \
  -H "Content-Type: application/json" \
  -d '{"name":"My Page","uri":"https://example.com","duration":30}'
```

### Playlists

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/playlists` | List all playlists |
| POST | `/api/playlists` | Create playlist |
| GET | `/api/playlists/<id>` | Get playlist with items |
| PUT | `/api/playlists/<id>` | Update playlist and items |
| DELETE | `/api/playlists/<id>` | Delete playlist |

**Create and populate a playlist:**
```bash
# Create
curl -b cookies.txt -X POST http://localhost/api/playlists \
  -H "Content-Type: application/json" \
  -d '{"name":"My Playlist"}'

# Update with items
curl -b cookies.txt -X PUT http://localhost/api/playlists/<id> \
  -H "Content-Type: application/json" \
  -d '{
    "name": "My Playlist",
    "loop": true,
    "is_active": true,
    "items": [
      {"asset_id": "<asset-id>", "duration_override": 15},
      {"asset_id": "<asset-id-2>"}
    ]
  }'
```

### Schedules

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/schedules` | List all schedules |
| POST | `/api/schedules` | Create schedule |
| PUT | `/api/schedules/<id>` | Update schedule |
| DELETE | `/api/schedules/<id>` | Delete schedule |

### Users (Admin only)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/users` | List all users |
| POST | `/api/users` | Create user |
| GET | `/api/users/<id>` | Get user |
| PUT | `/api/users/<id>` | Update user |
| DELETE | `/api/users/<id>` | Delete user |

### Stats & System

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/stats` | Dashboard statistics |
| GET | `/api/me` | Current user info |
| GET | `/api/current-playlist` | Currently scheduled playlist |

### System (Admin only)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/update/status` | Installed version, latest available, last update result |
| POST | `/api/update/apply` | Start an update (returns immediately; poll status) |
| GET | `/api/health` | Services, disk, CPU temperature, undervoltage, player heartbeat |
| POST | `/api/system/power` | `{"action": "restart-display" \| "reboot" \| "shutdown"}` |
| GET | `/api/system/timezone` | Current timezone and the full IANA zone list |
| POST | `/api/system/timezone` | `{"timezone": "America/New_York"}` |
| GET | `/api/system/clock` | Current time and whether it's synced via NTP |
| POST | `/api/system/clock` | `{"action": "sync"}` or `{"action": "manual", "datetime": "YYYY-MM-DD HH:MM:SS"}` |
| POST | `/api/player/heartbeat` | Reported by the player; unauthenticated like `/api/current-playlist` |
| GET | `/api/device-info/qr/wifi.svg` | QR code for the setup hotspot; unauthenticated, `404` when no hotspot is active |
| GET | `/api/device-info/qr/address.svg` | QR code for the device's admin address; unauthenticated |
| GET | `/api/backup/export` | Downloads a zip: database snapshot + all uploaded assets |
| POST | `/api/backup/import` | Restore from a backup zip (multipart `file`) — replaces current content |
| GET | `/api/storage/orphans` | Lists uploaded files no asset references |
| DELETE | `/api/storage/orphans` | Deletes the files `GET` reported |

### Network (Admin only, requires NetworkManager)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/network/status` | Hostname + per-interface IP/gateway/DNS/method |
| POST | `/api/network/wifi/scan` | Rescan and list nearby WiFi networks |
| POST | `/api/network/wifi/connect` | Join a WiFi network (`{"ssid","password"}`) |
| POST | `/api/network/ip` | Set DHCP or static IPv4 (`{"device","method","address","gateway","dns"}`) |
| POST | `/api/network/hostname` | Change device hostname (`{"hostname"}`) |

> Privileged changes are executed through `/usr/local/sbin/lumina-net`, a validated helper the installer provisions with a sudoers entry scoped to exactly that script. On systems without `nmcli` these endpoints return `503` and the Network page shows a notice.

---

## Troubleshooting

### Service won't start
```bash
sudo journalctl -u lumina -n 50 --no-pager
```

### Nginx errors
```bash
sudo nginx -t
sudo journalctl -u nginx -n 20
```

### Upload fails
- Check disk space: `df -h`
- Check permissions: `ls -la /opt/lumina-signage/static/uploads/`
- Check Nginx `client_max_body_size` in `/etc/nginx/sites-available/lumina`

### Video thumbnails not generating
- Verify FFmpeg: `ffmpeg -version`
- Check logs for ffprobe errors: `sudo journalctl -u lumina -f`

### PDF thumbnails not generating
- Install ImageMagick: `sudo apt install imagemagick`
- Raspberry Pi OS (Bookworm) may ship with PDF processing disabled in ImageMagick's policy. The installer fixes this automatically, but if installing manually run:
```bash
sudo sed -i 's|<policy domain="coder" rights="none" pattern="PDF" />|<policy domain="coder" rights="read|write" pattern="PDF" />|g' /etc/ImageMagick-*/policy.xml
```
- Verify ImageMagick is working: `magick --version` (IM7) or `convert --version` (IM6)

### PDF not displaying in player
- The PDF renderer is vendored locally at `static/vendor/pdfjs/` by the installer, so PDFs work offline. Check those files exist:
```bash
ls -la /opt/lumina-signage/static/vendor/pdfjs/
```
- If they are missing, the installer could not download them. Re-run the installer with an internet connection, or the player will fall back to loading the renderer from `cdnjs.cloudflare.com` — which needs internet at playback time.

### Player shows "No content scheduled"
- Ensure at least one playlist is marked **Active**
- Check that the playlist has assets
- If using schedules, verify the current time/day matches a schedule

### TemplateNotFound error on startup
- Ensure `index.html`, `login.html`, and `player.html` are inside a `templates/` subdirectory, not the project root
- Flask requires this folder name exactly: `templates/`

### Permission denied errors
```bash
sudo chown -R lumina:lumina /opt/lumina-signage
sudo systemctl restart lumina
```

### Reset admin password
```bash
cd /opt/lumina-signage
sudo -u lumina venv/bin/python - << 'EOF'
from app import app, db, User
with app.app_context():
    u = User.query.filter_by(username='admin').first()
    u.set_password('newpassword123')
    db.session.commit()
    print('Password reset!')
EOF
```

---

## Architecture

```
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚                  Browser                   â”‚
â”‚  Admin UI (SPA)    â”‚    Player (fullscreen) â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
           â”‚ HTTP                â”‚ HTTP
           â–¼                     â–¼
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚            Nginx (Port 80)                 â”‚
â”‚  â€¢ Reverse proxy to Gunicorn               â”‚
â”‚  â€¢ Serves /static/ directly                â”‚
â”‚  â€¢ 2GB upload support                      â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
                   â”‚
                   â–¼
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚    Gunicorn (127.0.0.1:8080)               â”‚
â”‚    Flask Application (app.py)              â”‚
â”‚  â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”   â”‚
â”‚  â”‚  Routes: /, /login, /player         â”‚   â”‚
â”‚  â”‚  API: /api/assets /api/playlists    â”‚   â”‚
â”‚  â”‚        /api/schedules /api/users    â”‚   â”‚
â”‚  â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜   â”‚
â”‚  â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”  â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”  â”‚
â”‚  â”‚  SQLite DB   â”‚  â”‚  FFmpeg / FFprobe  â”‚  â”‚
â”‚  â”‚  lumina.db   â”‚  â”‚  (thumbnails)      â”‚  â”‚
â”‚  â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜  â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜  â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
           â”‚
           â–¼
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚       /opt/lumina-signage/static/uploads/  â”‚
â”‚       (Images, Videos, Thumbnails)         â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
```

### Components

| Component | Purpose |
|-----------|---------|
| **Flask** | Web framework, routing, API |
| **SQLAlchemy** | ORM for SQLite database |
| **Gunicorn** | Production WSGI server |
| **Nginx** | Reverse proxy, static file serving |
| **FFmpeg** | Video thumbnail generation, duration detection |
| **Systemd** | Process management, auto-restart |

---

## Changelog

Full release history, including every fix with its severity and issue number, is in [`CHANGELOG.md`](CHANGELOG.md).

Architecture notes, project conventions, and the tiered roadmap are in [`CLAUDE.md`](CLAUDE.md).


## License

MIT License â€” see `LICENSE` for details.

---

*LuminaShow is inspired by [Anthias (Screenly)](https://github.com/Screenly/Anthias) â€” an excellent open-source digital signage project.*


## Raspberry Pi 4/5

LuminaShow ships as a signage **appliance image** built from Raspberry Pi OS Lite — no desktop, with the player running under `cage` and managed by `lumina-kiosk.service`.

Flash it, plug in HDMI and power, and the screen displays its own setup instructions: either the address to open (`http://<ip>`), or — when it has no network — how to join its fallback `LuminaShow-Setup` hotspot to configure WiFi from a phone. Moving a screen to a new site needs no keyboard, monitor, or SSH.

Full instructions, installer flags, and image-build steps: [`docs/RASPBERRY_PI.md`](docs/RASPBERRY_PI.md).


