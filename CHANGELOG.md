# LuminaShow â€” Changelog

All notable changes to this project are documented in this file.  
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [1.4.0] — 2026-03-25

### Added

- **Raspberry Pi installer** — Added `install_rpi.sh` for Raspberry Pi OS (Debian-based), with support for Pi 4 and Pi 5, non-interactive mode for automation, optional kiosk autostart setup, and service provisioning for `systemd` + `nginx`.
- **Raspberry Pi image build pipeline** — Added `image/pi-gen/build-image.sh` to build deployable SD-card images using `pi-gen`, including repository packaging and custom stage injection.
- **Custom pi-gen stage** — Added `image/pi-gen/stage-lumina/01-lumina/` stage files to preload Lumina assets and run first-boot installation automatically on provisioned images.
- **Raspberry Pi deployment docs** — Added `docs/RASPBERRY_PI.md` covering direct Pi installation, image build flow, and operational commands.
- **GitHub Actions image automation** — Added `.github/workflows/pi-image-ci.yml` with PR smoke checks (`bash -n`, `shellcheck`), full pi-gen image builds on `main`/weekly/manual runs, and artifact verification/upload.

### Changed

- **README Raspberry Pi guidance** — Added Raspberry Pi section in `README.md` pointing to dedicated Pi documentation.
- **Repository hygiene** — Added `.gitignore` entries for build artifacts and local runtime files (`.build/`, `venv/`, `__pycache__/`, `*.pyc`, `lumina.db`).

---

## [1.3.0] â€” 2026-03-25

### Changed

- **Deterministic schedule resolution** â€” `/api/current-playlist` now evaluates active schedules in a stable order and resolves matches deterministically.
- **Overnight schedule support** â€” Schedule windows that cross midnight (for example, `23:00` to `02:00`) are now handled correctly.
- **Schedule boundary clarification** â€” Schedule windows are now documented and enforced as start-inclusive and end-exclusive, with a special-case interpretation of `23:59` as end-of-day coverage.
- **Brand rename** â€” Application branding updated to `LuminaShow` across UI text and documentation.
- **README API auth clarification** â€” API docs now explicitly note that `GET /api/current-playlist` is intentionally unauthenticated for kiosk clients.
- **README changelog cleanup** â€” Removed stale embedded release notes from `README.md` and linked directly to `CHANGELOG.md` as the canonical release history.

### Fixed

- **[High] Schedule overlap ambiguity** â€” Active schedules are now validated to prevent overlapping day/time windows on create and update. API returns `409` on overlap conflicts.
- **[High] YouTube player invalid parameter failures** â€” Player-side YouTube ID extraction now supports `watch`, `youtu.be`, `embed`, `shorts`, `live`, and `/v/` URL formats, with invalid links safely skipped.
- **[Medium] YouTube thumbnail extraction gaps** â€” Backend `extract_youtube_id()` now supports the same URL formats as the player so thumbnail generation works consistently.
- **[Medium] Invalid JSON request crashes on write APIs** â€” Added shared JSON body validation for update/create endpoints so malformed or missing JSON now returns clean `400` responses instead of unhandled `500` errors.
- **[Medium] Duplicate email update could trigger server error** â€” `PUT /api/users/<id>` now validates email uniqueness (excluding the current user) and returns `409` conflict with a clear error message.
- **[Medium] YouTube links misclassified as generic URLs** â€” Asset type detection now uses the hardened YouTube ID parser, so valid YouTube variants (`watch`, `youtu.be`, `embed`, `shorts`, `live`, `/v/`) are correctly stored as `youtube`.
- **[Medium] Vimeo URL parsing in player was too narrow** â€” Player now supports multiple Vimeo URL formats (`vimeo.com/<id>`, `player.vimeo.com/video/<id>`, and nested path variants) and safely skips invalid Vimeo links.
- **[Medium] Vimeo links could be misclassified in backend** â€” Backend `extract_vimeo_id()` now supports player-style Vimeo URL variants, improving URL asset classification and thumbnail selection.
- **[Low] Invalid user role updates were silently ignored** â€” `PUT /api/users/<id>` now returns `400` when `role` is provided with an unsupported value instead of ignoring it.

---

## [1.2.0] â€” 2026-03-24

### Added

- **PDF asset support** â€” Upload `.pdf` files directly from the Assets page. PDFs are displayed page-by-page in the player with automatic page advancement. Total asset duration is divided evenly across all pages (minimum 2 seconds per page).
- **PDF thumbnails** â€” First page of each PDF is rendered as a thumbnail in the asset grid using ImageMagick. Supports both ImageMagick 7 (`magick`) and ImageMagick 6 (`convert`); falls back gracefully if neither is installed.
- **Dark / Light mode toggle** â€” Moon/sun button in the topbar and login page switches between dark and light themes. Preference is persisted in `localStorage` and shared between the admin UI and login page.
- **Ubuntu Desktop support** â€” Installer now handles Desktop-specific issues: waits for `unattended-upgrades` apt lock, detects and offers to stop Apache2 if it conflicts on port 80, and safely skips removing custom nginx sites.
- **Upgrade path in installer** â€” Re-running `install.sh` on an existing installation now offers Upgrade / Reinstall / Cancel. Upgrade mode patches application files while preserving the database, uploads, and `.env` config.
- **Kiosk launch commands** â€” Completion banner now shows `chromium-browser --kiosk` and `google-chrome --kiosk` commands for Ubuntu Desktop deployments.

### Changed

- `install.sh` installs `imagemagick` and `rsync` as new system dependencies.
- Installer automatically patches Ubuntu's ImageMagick `policy.xml` to enable PDF processing (Ubuntu ships with PDF disabled by default).
- Version badge bumped to `v1.2` in admin UI and login page footer.
- `typeBadge()` returns orange badge for PDF assets; `assetIcon()` returns ðŸ“„.
- Upload zone hint and file input `accept` attribute updated to include `.pdf`.

### Fixed

- **[Critical] Player black screen â€” all media types** â€” All media elements (`#videoEl`, `#imageEl`, `#iframeEl`, `#pdfCanvas`) have `display: none` in the stylesheet. The player was restoring them with `element.style.display = ''`, which clears the inline style but lets the stylesheet rule win, keeping everything hidden. Fixed by using `'block'` instead of `''` for all reveal operations.
- **[Critical] Paused state never reset on navigation** â€” `paused = true` was never cleared when moving to a new item via Prev/Next, auto-reload, or schedule change. The progress bar stayed frozen, the pause button stayed in the wrong state, and the player appeared stuck while silently advancing in the background. Fixed by resetting `paused = false` and restoring the â¸ icon at the start of `showItem()`.
- **[Medium] PDF page timer not cancelled on navigation** â€” `clearTimers()` did not cancel `pdfPageTimer`, so PDF pages kept flipping after pressing Prev/Next.
- **[Medium] PDF page badge visible during non-PDF items** â€” `hideAll()` did not hide `#pdfPageBadge`, so stale "Page X/Y" text appeared on hover during image and video items.
- **[Medium] PDF page advancement continued while paused** â€” `togglePause()` did not cancel `pdfPageTimer`. Pages continued auto-advancing even while the player was paused. Pause now snapshots remaining page time and resumes correctly.
- **[Minor] `nextItem()` did not update `currentIdx`** â€” Manual Next click called `showItem(currentIdx + 1)` without updating `currentIdx`, so the next auto-advance timer advanced to the wrong item.
- **[Minor] `videoEl.onended` never cleared** â€” `hideAll()` set `videoEl.src = ''` but left the old `onended` handler attached. Added explicit `videoEl.onended = null` to prevent stale handlers firing on edge cases.
- **[Minor] Previous video audio played through fade transition** â€” `hideAll()` (which clears `videoEl.src`) runs 500ms into the fade callback. For that half-second the prior video's audio was audible over a black screen. Fixed by calling `videoEl.pause()` and `videoEl.muted = true` immediately in `clearTimers()`, before the fade begins.
- **[Minor] `totalDuration` was dead code** â€” Variable was declared and written on every `showItem()` call but never read. Removed.
- **[Minor] Login page input fields invisible in light mode** â€” Input `background: rgba(255,255,255,0.04)` is effectively white-on-white in light mode. Changed to `var(--surface)` so inputs are visible in both themes.
- **[Minor] PDF thumbnail generation failed on Ubuntu 22.04+** â€” `generate_pdf_thumbnail()` only tried the `convert` binary (ImageMagick 6). Ubuntu 22.04+ ships ImageMagick 7 where the binary is `magick`. Function now tries `magick` first, falls back to `convert`.

---

## [1.1.0] â€” 2026-03-24

### Fixed

- **[Critical] TemplateNotFound on every page load** â€” HTML files (`index.html`, `login.html`, `player.html`) must reside in a `templates/` subdirectory. Flask's `render_template()` requires this structure; placing them in the project root caused the app to crash on startup. Added `templates/` to the project layout and documented the requirement.
- **[Critical] Video items skipped twice in player** â€” `player.html` had both `videoEl.onended` and a `setTimeout` calling `advance()` independently. When a video finished naturally, both fired and the player skipped an extra item. Fixed by introducing a `safeAdvance()` guard (`advanceLocked` flag) so only the first caller proceeds.
- **[Critical] Delete button always shown for own user account** â€” In the Users table, the self-check compared `u.username` against the un-evaluated string literal `'${state.user?.username}'` rather than the actual runtime value. As a result, admins could render a delete button for their own account. Fixed by comparing numeric user IDs: `u.id === state.user?.id`.
- **[Medium] Playlist `updated_at` timestamp never updated** â€” `api_update_playlist()` did not explicitly set `updated_at`. The SQLAlchemy `onupdate` hook is unreliable with SQLite and silently skipped. Fixed by adding `pl.updated_at = datetime.utcnow()` explicitly.
- **[Medium] XSS injection risk in User Management table** â€” User data was passed directly into `onclick` attributes via `JSON.stringify()`. A username or email containing `'`, `"`, or `</script>` could break out of the HTML attribute context. Fixed by storing users in `state.usersById` keyed by numeric ID, and passing only the safe integer ID into `onclick`. The `esc()` helper now also escapes single quotes.
- **[Minor] Unused imports in `app.py`** â€” Removed `hashlib`, `timedelta`, `flash`, `abort`, and `send_from_directory`.
- **[Minor] Pause/resume timer drift in player** â€” After pausing and resuming multiple times, `remaining` was calculated incorrectly, causing drift and negative values that made the timer fire instantly on resume. Replaced with `remainingMs` (snapshotted at each pause) and `progressStart` (reset at each resume).

---

## [1.0.0] â€” Initial release

- Flask application with SQLite database via SQLAlchemy
- Asset management â€” images, video, YouTube, Vimeo, and web URLs
- Playlist builder with drag-to-reorder and per-item duration override
- Schedule engine â€” day-of-week and time-range scheduling
- Full-screen player with fade transitions, progress bar, and keyboard shortcuts
- Role-based access control â€” Admin, Editor, and Viewer roles
- Nginx reverse proxy with 2GB upload support
- Systemd service with auto-restart
- REST API for all resources
- Ubuntu installer script (`install.sh`) and uninstaller (`uninstall.sh`)


