# LuminaShow — Digital Signage Platform for Ubuntu

> A self-hosted, open-source digital signage solution for Ubuntu — inspired by [Anthias/Screenly](https://github.com/Screenly/Anthias) and others. Manage playlists, schedule content, and display media across screens from a sleek web interface.

## Latest Release (v1.3.0)

- Deterministic schedule resolution with overnight schedule support
- Active schedule overlap prevention on create/update
- Hardened YouTube parsing in player and backend thumbnail extraction

See full details in the [v1.3.0 changelog](./CHANGELOG.md#130--2026-03-25).

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

- **Drag-and-drop asset management** — upload files directly from your browser
- **Rich media support** — images, videos, web URLs, YouTube, and Vimeo
- **Playlist builder** — drag to reorder, per-item duration override
- **Schedule engine** — set playlists to play on specific days and time ranges
- **Full-screen player** — smooth fade transitions, keyboard shortcuts, auto-advance
- **Role-based access control** — Admin, Editor, and Viewer roles
- **Nginx reverse proxy** — production-ready setup out of the box
- **Systemd service** — auto-starts on boot, auto-restarts on failure
- **REST API** — full API for automation and custom integrations
- **No cloud required** — 100% self-hosted

---

## Supported Media

| Category | Formats |
|----------|---------|
| **Images** | JPG, JPEG, PNG, GIF, BMP, WEBP |
| **Videos** | AVI, MKV, MOV, MPG, MPEG, MP4, TS |
| **Streaming** | YouTube URLs, Vimeo URLs |
| **Web** | Any HTTP/HTTPS URL (rendered in iframe) |
| **Documents** | PDF |

> **Video thumbnails** are automatically generated using FFmpeg.
> **YouTube thumbnails** are fetched from YouTube's CDN.
> **Vimeo thumbnails** are fetched via Vumbnail.

---

## Requirements

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| OS | Ubuntu 20.04 LTS | Ubuntu 22.04 / 24.04 LTS |
| CPU | 1 core | 2+ cores |
| RAM | 512 MB | 2 GB+ |
| Disk | 10 GB | 50 GB+ (for media storage) |
| Python | 3.8 | 3.11+ |
| Network | LAN access | Internet for YouTube/Vimeo |

---

## Quick Install

```bash
# 1. Clone or download
git clone https://github.com/yourorg/lumina-signage.git
cd lumina-signage

# 2. Run installer as root
sudo bash install.sh
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
| `SECRET_KEY` | Random | Flask session secret — **change in production** |
| `PORT` | `8080` | Port to listen on |
| `DEBUG` | `false` | Enable Flask debug mode |

---

## Project Structure

```
lumina-signage/
├── app.py                  # Flask application and REST API
├── requirements.txt        # Python dependencies
├── lumina.service          # Systemd service unit
├── install.sh              # Ubuntu installer script
├── uninstall.sh            # Uninstaller script
├── templates/              # Flask HTML templates (must be this folder name)
│   ├── index.html          # Admin dashboard SPA
│   ├── login.html          # Login page
│   └── player.html         # Full-screen kiosk player
└── static/
    └── uploads/            # Uploaded media files (auto-created)
        └── thumbnails/     # Auto-generated video thumbnails
```

> **Important:** The `templates/` directory is required by Flask. The HTML files (`index.html`, `login.html`, `player.html`) must live inside `templates/` — not in the project root — or the application will fail to start with a `TemplateNotFound` error.

---

## First Login

After installation, open your browser and navigate to:

```
http://<your-server-ip>
```

**Default credentials:**

| Field | Value |
|-------|-------|
| Username | `admin` |
| Password | `admin123` |

> ⚠️ **Change the default password immediately** after your first login.
> Go to **Users** → click the edit icon next to admin → set a new password.

---

## User Management

LuminaShow has three user roles:

| Role | Permissions |
|------|-------------|
| **Admin** | Full access — users, assets, playlists, schedules |
| **Editor** | Manage assets, playlists, and schedules (no user management) |
| **Viewer** | Read-only access — view dashboard and player |

### Adding a user

1. Navigate to **Users** (Admin only)
2. Click **+ Add User**
3. Fill in username, email, password, and role
4. Click **Save User**

### Editing a user

Click the **✎** edit icon next to any user. You can change their email, role, active status, and password.

### Disabling a user

Toggle the "Account Active" switch when editing a user. Disabled users cannot log in.

---

## Managing Assets

### Uploading Files

1. Go to **Assets**
2. Click **↑ Upload File** or drag files directly onto the upload zone
3. Multiple files can be dropped at once

### Adding URLs / YouTube / Vimeo

1. Click **+ Add URL**
2. Paste any URL:
   - `https://example.com/page` — web page
   - `https://www.youtube.com/watch?v=...` — YouTube video
   - `https://vimeo.com/123456789` — Vimeo video
3. Set a display duration (seconds)
4. Click **Add Asset**

### Editing Assets

Click **✎** on any asset card to rename it or adjust its default duration.

### Deleting Assets

Click **✕** on any asset card. Files are permanently deleted from disk.

---

## Creating Playlists

1. Go to **Playlists** → **+ New Playlist**
2. Enter a name and click OK
3. In the editor:
   - **Add assets** from the right panel by clicking **+**
   - **Reorder** items by dragging the ⠿ handle
   - **Override duration** per item using the numeric input
   - Toggle **Loop** to repeat the playlist continuously
   - Toggle **Active** to enable/disable the playlist
4. Click **Save Playlist**

---

## Scheduling

Schedules control which playlist plays at what time.

1. Go to **Schedules** → **+ New Schedule**
2. Configure:
   - **Name** — e.g., "Morning Lobby Loop"
   - **Playlist** — which playlist to play
   - **Start/End Time** — time range (24-hour format)
   - **Days** — select active days of the week
3. Click **Save Schedule**

### How scheduling works

- The player checks active schedules every 5 minutes
- The first schedule matching the current day and time wins
- Time windows are interpreted as **start-inclusive, end-exclusive** (for example, `08:00` to `12:00` runs up to but not including `12:00`)
- Use `23:59` as end time to run through the end of day
- If no schedule matches, the first active playlist plays as a fallback
- Multiple schedules can run different playlists throughout the day

---

## The Player

Access the full-screen player at `http://<server>/player`

### Keyboard shortcuts

| Key | Action |
|-----|--------|
| `→` | Next item |
| `←` | Previous item |
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
2. Enable kiosk mode (e.g., `chromium-browser --kiosk http://...`)

Example autostart for Raspberry Pi / Ubuntu kiosk:
```bash
# /etc/xdg/autostart/lumina-player.desktop
[Desktop Entry]
Type=Application
Name=LuminaShow Player
Exec=chromium-browser --kiosk --noerrdialogs --disable-infobars http://localhost/player
```

---

## Upgrading

```bash
cd /path/to/lumina-signage
git pull
sudo cp -r . /opt/lumina-signage/
sudo /opt/lumina-signage/venv/bin/pip install -r requirements.txt
sudo systemctl restart lumina
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
┌────────────────────────────────────────────┐
│                  Browser                   │
│  Admin UI (SPA)    │    Player (fullscreen) │
└──────────┬─────────────────────┬───────────┘
           │ HTTP                │ HTTP
           ▼                     ▼
┌────────────────────────────────────────────┐
│            Nginx (Port 80)                 │
│  • Reverse proxy to Gunicorn               │
│  • Serves /static/ directly                │
│  • 2GB upload support                      │
└──────────────────┬─────────────────────────┘
                   │
                   ▼
┌────────────────────────────────────────────┐
│    Gunicorn (127.0.0.1:8080)               │
│    Flask Application (app.py)              │
│  ┌─────────────────────────────────────┐   │
│  │  Routes: /, /login, /player         │   │
│  │  API: /api/assets /api/playlists    │   │
│  │        /api/schedules /api/users    │   │
│  └─────────────────────────────────────┘   │
│  ┌──────────────┐  ┌────────────────────┐  │
│  │  SQLite DB   │  │  FFmpeg / FFprobe  │  │
│  │  lumina.db   │  │  (thumbnails)      │  │
│  └──────────────┘  └────────────────────┘  │
└────────────────────────────────────────────┘
           │
           ▼
┌────────────────────────────────────────────┐
│       /opt/lumina-signage/static/uploads/  │
│       (Images, Videos, Thumbnails)         │
└────────────────────────────────────────────┘
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

### v1.1.0

**Bug Fixes**

- **[Critical] TemplateNotFound on every page load** — HTML files (`index.html`, `login.html`, `player.html`) must reside in a `templates/` subdirectory. Flask's `render_template()` requires this structure; placing them in the project root caused the app to crash on startup. Added `templates/` to the project layout and documented the requirement.

- **[Critical] Video items skipped twice in player** — `player.html` had both `videoEl.onended` and a `setTimeout` calling `advance()` independently. When a video finished naturally, both fired and the player skipped an extra item. Fixed by introducing a `safeAdvance()` guard (`advanceLocked` flag) so only the first caller proceeds.

- **[Critical] Delete button always shown for own user account** — In the Users table, the self-check compared `u.username` against the un-evaluated string literal `'${state.user?.username}'` rather than the actual runtime value. As a result, admins could render a delete button for their own account. Fixed by comparing numeric user IDs: `u.id === state.user?.id`.

- **[Medium] Playlist `updated_at` timestamp never updated** — `api_update_playlist()` did not explicitly set `updated_at`. The SQLAlchemy `onupdate` hook is unreliable with SQLite and silently skipped. Fixed by adding `pl.updated_at = datetime.utcnow()` explicitly, consistent with how `api_update_asset()` already handled it.

- **[Medium] XSS injection risk in User Management table** — User data (including email and username) was passed directly into `onclick` attributes via `JSON.stringify()`. A username or email containing `'`, `"`, or `</script>` could break out of the HTML attribute context. Fixed by storing users in `state.usersById` (keyed by numeric ID) and passing only the safe integer ID into `onclick`. The `esc()` helper now also escapes single quotes (`'` → `&#39;`).

- **[Minor] Unused imports in `app.py`** — Removed `hashlib`, `timedelta`, `flash`, `abort`, and `send_from_directory`, none of which were referenced anywhere in the application.

- **[Minor] Pause/resume timer drift in player** — After pausing and resuming multiple times, `remaining` was calculated by subtracting elapsed time from the original `progressStart`, causing drift and negative values that made the timer fire instantly on resume. Replaced with `remainingMs` (snapshotted at each pause) and `progressStart` (reset at each resume) for correct remaining-time tracking across any number of pause cycles.

---

## License

MIT License — see `LICENSE` for details.

---

*LuminaShow is inspired by [Anthias (Screenly)](https://github.com/Screenly/Anthias) — an excellent open-source digital signage project.*
