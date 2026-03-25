# LuminaCast — Changelog

All notable changes to this project are documented in this file.  
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [1.3.0] — 2026-03-25

### Changed

- **Deterministic schedule resolution** — `/api/current-playlist` now evaluates active schedules in a stable order and resolves matches deterministically.
- **Overnight schedule support** — Schedule windows that cross midnight (for example, `23:00` to `02:00`) are now handled correctly.

### Fixed

- **[High] Schedule overlap ambiguity** — Active schedules are now validated to prevent overlapping day/time windows on create and update. API returns `409` on overlap conflicts.
- **[High] YouTube player invalid parameter failures** — Player-side YouTube ID extraction now supports `watch`, `youtu.be`, `embed`, `shorts`, `live`, and `/v/` URL formats, with invalid links safely skipped.
- **[Medium] YouTube thumbnail extraction gaps** — Backend `extract_youtube_id()` now supports the same URL formats as the player so thumbnail generation works consistently.
- **[Medium] Invalid JSON request crashes on write APIs** — Added shared JSON body validation for update/create endpoints so malformed or missing JSON now returns clean `400` responses instead of unhandled `500` errors.

---

## [1.2.0] — 2026-03-24

### Added

- **PDF asset support** — Upload `.pdf` files directly from the Assets page. PDFs are displayed page-by-page in the player with automatic page advancement. Total asset duration is divided evenly across all pages (minimum 2 seconds per page).
- **PDF thumbnails** — First page of each PDF is rendered as a thumbnail in the asset grid using ImageMagick. Supports both ImageMagick 7 (`magick`) and ImageMagick 6 (`convert`); falls back gracefully if neither is installed.
- **Dark / Light mode toggle** — Moon/sun button in the topbar and login page switches between dark and light themes. Preference is persisted in `localStorage` and shared between the admin UI and login page.
- **Ubuntu Desktop support** — Installer now handles Desktop-specific issues: waits for `unattended-upgrades` apt lock, detects and offers to stop Apache2 if it conflicts on port 80, and safely skips removing custom nginx sites.
- **Upgrade path in installer** — Re-running `install.sh` on an existing installation now offers Upgrade / Reinstall / Cancel. Upgrade mode patches application files while preserving the database, uploads, and `.env` config.
- **Kiosk launch commands** — Completion banner now shows `chromium-browser --kiosk` and `google-chrome --kiosk` commands for Ubuntu Desktop deployments.

### Changed

- `install.sh` installs `imagemagick` and `rsync` as new system dependencies.
- Installer automatically patches Ubuntu's ImageMagick `policy.xml` to enable PDF processing (Ubuntu ships with PDF disabled by default).
- Version badge bumped to `v1.2` in admin UI and login page footer.
- `typeBadge()` returns orange badge for PDF assets; `assetIcon()` returns 📄.
- Upload zone hint and file input `accept` attribute updated to include `.pdf`.

### Fixed

- **[Critical] Player black screen — all media types** — All media elements (`#videoEl`, `#imageEl`, `#iframeEl`, `#pdfCanvas`) have `display: none` in the stylesheet. The player was restoring them with `element.style.display = ''`, which clears the inline style but lets the stylesheet rule win, keeping everything hidden. Fixed by using `'block'` instead of `''` for all reveal operations.
- **[Critical] Paused state never reset on navigation** — `paused = true` was never cleared when moving to a new item via Prev/Next, auto-reload, or schedule change. The progress bar stayed frozen, the pause button stayed in the wrong state, and the player appeared stuck while silently advancing in the background. Fixed by resetting `paused = false` and restoring the ⏸ icon at the start of `showItem()`.
- **[Medium] PDF page timer not cancelled on navigation** — `clearTimers()` did not cancel `pdfPageTimer`, so PDF pages kept flipping after pressing Prev/Next.
- **[Medium] PDF page badge visible during non-PDF items** — `hideAll()` did not hide `#pdfPageBadge`, so stale "Page X/Y" text appeared on hover during image and video items.
- **[Medium] PDF page advancement continued while paused** — `togglePause()` did not cancel `pdfPageTimer`. Pages continued auto-advancing even while the player was paused. Pause now snapshots remaining page time and resumes correctly.
- **[Minor] `nextItem()` did not update `currentIdx`** — Manual Next click called `showItem(currentIdx + 1)` without updating `currentIdx`, so the next auto-advance timer advanced to the wrong item.
- **[Minor] `videoEl.onended` never cleared** — `hideAll()` set `videoEl.src = ''` but left the old `onended` handler attached. Added explicit `videoEl.onended = null` to prevent stale handlers firing on edge cases.
- **[Minor] Previous video audio played through fade transition** — `hideAll()` (which clears `videoEl.src`) runs 500ms into the fade callback. For that half-second the prior video's audio was audible over a black screen. Fixed by calling `videoEl.pause()` and `videoEl.muted = true` immediately in `clearTimers()`, before the fade begins.
- **[Minor] `totalDuration` was dead code** — Variable was declared and written on every `showItem()` call but never read. Removed.
- **[Minor] Login page input fields invisible in light mode** — Input `background: rgba(255,255,255,0.04)` is effectively white-on-white in light mode. Changed to `var(--surface)` so inputs are visible in both themes.
- **[Minor] PDF thumbnail generation failed on Ubuntu 22.04+** — `generate_pdf_thumbnail()` only tried the `convert` binary (ImageMagick 6). Ubuntu 22.04+ ships ImageMagick 7 where the binary is `magick`. Function now tries `magick` first, falls back to `convert`.

---

## [1.1.0] — 2026-03-24

### Fixed

- **[Critical] TemplateNotFound on every page load** — HTML files (`index.html`, `login.html`, `player.html`) must reside in a `templates/` subdirectory. Flask's `render_template()` requires this structure; placing them in the project root caused the app to crash on startup. Added `templates/` to the project layout and documented the requirement.
- **[Critical] Video items skipped twice in player** — `player.html` had both `videoEl.onended` and a `setTimeout` calling `advance()` independently. When a video finished naturally, both fired and the player skipped an extra item. Fixed by introducing a `safeAdvance()` guard (`advanceLocked` flag) so only the first caller proceeds.
- **[Critical] Delete button always shown for own user account** — In the Users table, the self-check compared `u.username` against the un-evaluated string literal `'${state.user?.username}'` rather than the actual runtime value. As a result, admins could render a delete button for their own account. Fixed by comparing numeric user IDs: `u.id === state.user?.id`.
- **[Medium] Playlist `updated_at` timestamp never updated** — `api_update_playlist()` did not explicitly set `updated_at`. The SQLAlchemy `onupdate` hook is unreliable with SQLite and silently skipped. Fixed by adding `pl.updated_at = datetime.utcnow()` explicitly.
- **[Medium] XSS injection risk in User Management table** — User data was passed directly into `onclick` attributes via `JSON.stringify()`. A username or email containing `'`, `"`, or `</script>` could break out of the HTML attribute context. Fixed by storing users in `state.usersById` keyed by numeric ID, and passing only the safe integer ID into `onclick`. The `esc()` helper now also escapes single quotes.
- **[Minor] Unused imports in `app.py`** — Removed `hashlib`, `timedelta`, `flash`, `abort`, and `send_from_directory`.
- **[Minor] Pause/resume timer drift in player** — After pausing and resuming multiple times, `remaining` was calculated incorrectly, causing drift and negative values that made the timer fire instantly on resume. Replaced with `remainingMs` (snapshotted at each pause) and `progressStart` (reset at each resume).

---

## [1.0.0] — Initial release

- Flask application with SQLite database via SQLAlchemy
- Asset management — images, video, YouTube, Vimeo, and web URLs
- Playlist builder with drag-to-reorder and per-item duration override
- Schedule engine — day-of-week and time-range scheduling
- Full-screen player with fade transitions, progress bar, and keyboard shortcuts
- Role-based access control — Admin, Editor, and Viewer roles
- Nginx reverse proxy with 2GB upload support
- Systemd service with auto-restart
- REST API for all resources
- Ubuntu installer script (`install.sh`) and uninstaller (`uninstall.sh`)
