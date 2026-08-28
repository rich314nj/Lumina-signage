# LuminaShow â€” Changelog

All notable changes to this project are documented in this file.  
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [1.11.1] — 2026-08-28

Bugfix: the #12 hardening (random per-device admin password instead of a
fixed default) shipped without any way to actually discover that password.
The login page still hardcoded "Default credentials: admin / admin123",
and the setup screen never surfaced the random password at all — so a
freshly-flashed device was unloggable-into from the UI.

- `templates/login.html` no longer shows a hardcoded default. It fetches
  `/api/device-info` and shows the real first-boot password when one is
  still active, and shows nothing once it has been consumed.
- `templates/player.html`'s "Ready for content" setup screen now shows
  the first-boot admin username/password inline, the same way it already
  showed the setup-hotspot WiFi password.

## [1.11.0] — 2026-08-28

Tier 4 of the roadmap in `CLAUDE.md`: hardening. All four issues — #11, #12,
#23, #24.

### Added

- **Per-device admin password** (#12) — every install previously shared the same `admin` / `admin123`. A fresh install (not a reprovision or reinstall — an existing password is never touched) now generates a random one and shows it exactly once, unauthenticated, on the setup screen (`GET /api/device-info`) — the same place the WiFi hotspot credentials already appear. The exposure window is deliberately short: the marker file is deleted the moment *any* login succeeds, so it can't be fetched from the LAN indefinitely.
- **Login throttling** (#12) — `/login` previously had no rate limit at all. Ten failed attempts per five minutes per client IP, then a `429` until the window clears; a successful login resets the counter. Correctly attributes attempts to the real client (`ProxyFix`), not `127.0.0.1` for everyone — nginx sits in front of every real deployment.
- **Session cookie hardening** (#12) — `HttpOnly` and `SameSite=Lax` set explicitly. Not `Secure`: the device is plain HTTP by design (building a TLS stack for a LAN appliance is explicitly out of scope for this issue), and `Secure` on an HTTP-only cookie would make the browser silently withhold it, breaking every login.
- **Gunicorn now binds to `127.0.0.1`, not `0.0.0.0`** (#12) — the app port was directly reachable on the LAN in addition to going through nginx's reverse proxy. nginx already proxies to `127.0.0.1`, so nothing else changes.
- **Backup and restore** (#23) — a **Backup & Restore** card on the System page. Export downloads a single zip with a WAL-consistent database snapshot plus every uploaded asset, deliberately excluding `.env`/`SECRET_KEY` so restoring onto a different device doesn't clone its session-signing key. Restore validates the archive (must contain `lumina.db`) before doing anything, then hands off to a new `scripts/lumina-backup` helper that backs up the current state first, swaps in the new one, and restarts the service — following the same "detach into a transient systemd unit" pattern as the updater, since restarting `lumina.service` would otherwise kill the request that asked for it.
- **Storage hygiene** (#24) — a **Check for unused files** control on the System page finds files under `static/uploads/` that no asset references (an interrupted upload, a failed delete, a restored database from before they existed) and reports them before offering to remove them; correctly treats both an asset's file *and* its generated thumbnail as "referenced," so video/PDF thumbnails are never flagged. Uploads are now refused with a clear `507` when free disk space is critically low, rather than letting a write fail partway through on the same filesystem the database lives on.

### Fixed

- **[High] Continuous SD card writes from polling — the classic Pi signage failure at 12–24 months** (#11) — the kiosk polls `/api/current-playlist` and `/api/device-info` every 15 seconds and posts a heartbeat on every item change, and both nginx and gunicorn logged every one of those requests. On a real device that's roughly 29,000 log lines a day, around the clock, whether or not anything changed. As diagnosed on the issue, responsiveness and card life were never actually in tension — the polling itself writes nothing; the *logging of it* does. Fixed without touching the polling interval at all:
  - Access logging is now off for the polling endpoints specifically (`nginx` regex location for `/api/current-playlist`, `/api/device-info` (and its QR sub-paths), and `/api/player/heartbeat`), in both installers.
  - `gunicorn` no longer writes an access log at all (`--access-logfile` dropped); the error log is unaffected, so real problems still show up in `/var/log/lumina/error.log`.
  - The systemd journal is now capped (`SystemMaxUse=50M`, `RuntimeMaxUse=16M` via a drop-in) rather than left to grow without bound — kept persistent, not volatile, since `journalctl` on a past boot has been this project's standard field-diagnosis tool throughout development.
  - SQLite now runs in **WAL mode** with `synchronous=NORMAL`: each write appends to a separate log instead of rewriting the whole database file, and skips an `fsync` per transaction. Signage configuration is not financial data — losing the last few seconds of an in-flight write to a power loss is an acceptable trade for materially fewer disk writes on every save.
- **[Medium] Two places read the database at the wrong path when `DATABASE_URL` was customized** — `/api/health`'s disk-usage report and the new backup export both hardcoded `BASE_DIR / "lumina.db"` instead of respecting the configured database URI. Harmless while `DATABASE_URL` went unused, but either would have silently operated on an empty, freshly-created file at the wrong path the moment anyone actually moved the database off the SD card — the exact scenario #11 introduced that variable to support. Both now resolve the real path from `SQLALCHEMY_DATABASE_URI`.

---

## [1.10.1] — 2026-08-28

### Added

- **Clock status and manual override on the System page** — 1.10.0 added a timezone control, but that only fixes how the clock is *interpreted*, not whether it's *correct*. The Pi has no battery-backed real-time clock: it relies entirely on reaching the internet at boot to learn the actual time via NTP. On a device that never gets that chance — an offline first boot, or a signage screen deliberately on an isolated network — the clock could be wrong with no way to fix it except SSH. The Date & Time card now shows the device's current time with a synced/not-synced badge; when not synced, a clear warning explains why and a manual date/time field appears (`timedatectl set-ntp false` + `set-time`, via a new `clock-set` action in `scripts/lumina-net`), plus a one-click "try automatic sync again" button (`ntp-enable`) for once real connectivity exists. `GET /api/system/clock` needs no special privilege — reading `timedatectl show` requires none — only the `POST` goes through the helper.

---

## [1.10.0] — 2026-08-28

Morning quick-wins batch: the four items queued from the previous session's
agenda, all confirmed or diagnosed on hardware.

### Fixed

- **[High] Changing a schedule's playlist did not save** (#42) — `api_update_schedule` handled name, start/end time, days, and active state, but never read `playlist_id` at all. The API returned `200` and the UI reported success, so the schedule silently kept whichever playlist it was created with — reported from the field as the dropdown "reverting to the 1st playlist." Fixed to mirror `api_create_schedule`: an unknown playlist is rejected with `400`, an absent field leaves the existing playlist untouched, and a valid change now persists. Regression tests added.
- **[Medium] The playlist editor was too narrow for its own content** (#40) — the **Add from Library** panel was clipped at the modal's edge, reachable only by an awkward horizontal scrollbar. The modal was `700px` wide but its two-column grid needed roughly `800px` at minimum, and the existing responsive rule watched the *viewport*, which never matched the actual constraint — the *modal* — regardless of window size. The playlist editor is now a `.modal-lg` (`min(1040px, 94vw)`, resizable via the corner handle) with `minmax(0, 1fr)` on the left column so it can actually shrink, and a `@container` query that stacks the two columns based on the modal's own width rather than the viewport.

### Added

- **WiFi QR code on the setup screen** (#38) — the on-screen setup instructions now include a scannable QR code alongside the existing text: a standard `WIFI:` payload for the setup hotspot, and the device address for the "ready for content" screen. Either state degrades cleanly — the code disappears rather than showing a broken image if it can't be generated. Rendered server-side as SVG via the `qrcode` library (no Pillow, no client-side dependency, ~5 KB), served from two small unauthenticated endpoints matching `/api/device-info`'s existing exposure. Item 1 only, as scoped in the issue — the captive portal remains for later.
- **Timezone control on the System page** (#16) — devices previously had no way to change the timezone without SSH; the image default fixed in 1.6.1 covered new installs but nothing let an admin correct it afterward. A new **Date & Time** card lists every IANA zone (via Python's stdlib `zoneinfo`) and applies the change through the existing `lumina-net` helper (`timezone` action, validated against `timedatectl list-timezones` on the device before being applied). Degrades to a clear "not available" notice where the helper is absent, matching every other System-page control.

---

## [1.9.3] — 2026-08-27

The update path was confirmed working on hardware (1.9.1 → 1.9.2), which
immediately exposed a gap in what an update actually replaces.

### Fixed

- **[Critical] Updates did not refresh service units or the nginx config** (#41) — those files are *generated* by the installer rather than shipped in the repository, so copying new code never touched them. A device could therefore run new code under an old systemd unit and report the new version while behaving like the old one. The 1.9.2 kiosk fix was entirely contained in the `lumina-kiosk.service` unit, so a device updated from 1.9.1 to 1.9.2 would have reported 1.9.2 while still failing exactly as before — a silent, and very misleading, no-op.
  - `install_rpi.sh` gains `--reprovision`, which rewrites the unit files, nginx config, helpers, and sudoers grants for an install whose code is already in place, leaving the database, uploads, and secret key untouched.
  - `lumina-update` calls it after syncing, and again on rollback so a reverted device gets its previous units back.
- **[High] Re-running the installer rotated the secret key** — `SECRET_KEY` was regenerated unconditionally, logging every user out on a reinstall. Worse, since the key is written into both `.env` and the systemd unit, refreshing only one of them would leave the two disagreeing. The existing key is now reused when present.
- `install_rpi.sh` also excludes `static/vendor` when syncing, matching the updater, so a reinstall no longer discards the vendored PDF.js.

---

## [1.9.2] — 2026-08-27

### Fixed

- **[Critical] The kiosk ran invisibly behind the console, and "Restart display" could not recover it** (#32) — `lumina-kiosk.service` claimed `/dev/tty1` with `StandardInput=tty-fail`, which does not fail loudly when the console `getty` already owns the terminal; it simply starts anyway without becoming the active virtual terminal. The service reported healthy and `cage` kept running, while the screen showed boot text. **Restart display and Reboot both appeared to hang** because neither addressed the actual contention, and the journal showed no errors at all — the service log looked perfectly normal throughout.
  - `Conflicts=getty@tty1.service` now makes systemd stop the console getty when the kiosk starts. This is precisely what `systemctl stop getty@tty1` did by hand during diagnosis.
  - `StandardInput=tty-force` takes the terminal rather than deferring to it.
  - `StartLimitIntervalSec`/`StartLimitBurst` added so a genuine failure stops cleanly and surfaces in the Health panel instead of retrying forever.
- **[High] The first-boot user wizard blocked the image indefinitely** — the pi-gen config set `FIRST_USER_NAME`/`FIRST_USER_PASS` but not `DISABLE_FIRST_BOOT_USER_RENAME`, so images shipped with Raspberry Pi OS's user-setup wizard enabled. `userconfig.service` ran on `tty1` and blocked with *no timeout*, waiting for keyboard input a signage device will never receive — a second competitor for the display, and the reason SSH greeted every login with a warning that no valid user had been set up. Now disabled by default, overridable at build time.

---

## [1.9.1] — 2026-08-27

### Fixed

- **[High] The navigation menu was invisible on phones** (#39) — the mobile rule hid `.nav-item span`, which matched the icon as well as the label, so every navigation item rendered completely empty. The sidebar collapsed to a bare strip with nothing in it and no way to tell one item from another; reaching **Network** required rotating the phone to landscape. This mattered more than a normal layout bug because the setup screen instructs people to configure the device from a phone, and Network is the first page they need — so the documented first-run path led straight into an unusable menu.
  - Below 900px only the label is hidden, so the icon rail works as intended.
  - Below 640px the sidebar becomes a horizontally scrollable row of **labelled** chips rather than bare icons, because someone hunting for "Network" should not have to guess at a glyph.
- **Cramped two-column layouts on small screens** — the dashboard's Recent Playlists / Active Schedules pair was a hardcoded inline two-column grid, and `.form-row` (used by Add User, the static IP dialog, and others) was fixed at two columns. Both now collapse to a single column below 900px.
- Phone-sized refinements: tighter page and modal padding, stacked page headers, and wrapping header actions.

---

## [1.9.0] — 2026-08-27

Tier 2 of the roadmap in `CLAUDE.md`: make failures survivable and visible
rather than silent and fatal.

### Added

- **Device controls** (#32) — **Restart display**, **Reboot**, and **Shut down**
  on the System page (Admin only), via a new `scripts/lumina-power` helper with
  its own scoped sudoers grant. *Restart display* restarts only the kiosk
  browser: it is the least disruptive fix for a wedged screen and would have
  recovered the white-screen failure without pulling the power.
- **Health reporting** (#10) — a Health panel on the System page and
  `GET /api/health` (Admin only) reporting service states, disk usage and
  database size, CPU temperature, uptime, and **Raspberry Pi undervoltage and
  throttling flags**, which are a common and easily missed cause of instability.
- **Player heartbeat** (#10) — the player now reports what it is displaying to
  `POST /api/player/heartbeat`, and Health shows either the item on screen or
  how long it has been silent. This closes the gap where every service looked
  healthy while the screen showed nothing — the exact situation that made the
  white screen hard to diagnose. Held in memory deliberately: it describes the
  current moment, and a restart should forget it rather than report stale data.
- **WiFi is explained when it is switched off** (#28) — the Network page now
  detects an rfkill-blocked radio and, instead of an empty scan list with no
  explanation, says WiFi is off because no wireless region is set and offers a
  country field to turn it on. Backed by `POST /api/network/wifi/country` and a
  new `wifi-country` action in the network helper.

### Fixed

- **[Medium] PDFs required an internet connection** (#15) — PDF.js was loaded
  from a CDN, so PDF assets silently failed to render on an offline device,
  contradicting the offline-first design of the appliance image. The installers
  now vendor it into `static/vendor/pdfjs/` at install time, and the player
  loads it locally, falling back to the CDN only if the download was
  unavailable. A PDF that cannot be rendered at all now reports why and skips
  instead of showing a blank screen for its full duration.

### Changed

- `uninstall.sh` now also removes the power helper and its sudoers entry.

---

## [1.8.0] — 2026-08-27

Tier 3 of the roadmap in `CLAUDE.md`: lock the behaviour in with tests, then
make fixes deliverable to devices in the field.

### Added

- **Automated test suite** (#22) — 106 tests covering the areas most likely to
  break silently, run on every push and pull request across Python 3.11 and 3.12
  via a new `Tests` workflow.
  - **Schedule resolution** — half-open interval boundaries, windows crossing
    midnight, the `23:59` end-of-day special case, full-day windows, overlap
    detection including the back-to-back case that must *not* count as a clash.
  - **URL parsing** — every supported YouTube and Vimeo form plus malformed and
    non-string input, and the asset-type detection that depends on both.
  - **API behaviour** — authentication, role enforcement, the `400`/`409` error
    paths, and that `/api/current-playlist` and `/api/device-info` stay reachable
    without a session, which the kiosk depends on.
  - **Regression tests for #26**, so a role change persists and a new user gets
    the role that was requested.
- **In-place updates** (#9) — a new **System** page (Admin only) shows the
  installed version, checks GitHub for a newer one, and installs it with one
  click. The work is done by `scripts/lumina-update`, invoked through its own
  narrowly scoped sudoers grant:
  - The database, uploads, and `.env` are preserved.
  - The database, config, **and the previous code tree** are backed up to
    `/var/backups/lumina/<timestamp>` before anything is replaced.
  - The new version is **health checked after starting**; if it fails to install
    dependencies, fails to start, or does not respond, the update **rolls back
    automatically** to the previous version.
  - The update runs in its own transient systemd unit, so restarting the
    application does not kill the update that requested it.
  - Progress and the outcome of the last attempt are reported in the UI.
- `GET /api/update/status` and `POST /api/update/apply` (Admin only). Both
  degrade gracefully where the helper is not installed, rather than erroring.

### Changed

- `DATABASE_URL` now overrides the database location. Tests use it for a scratch
  database, and it allows moving the database off the SD card onto external
  storage (relevant to #11).
- The image-build workflow now shellchecks `install.sh` and `uninstall.sh` too,
  not just the Pi scripts.
- `uninstall.sh` removes all four helper scripts and both sudoers entries; it
  previously left `lumina-kiosk` and `lumina-netwatch` behind.

---

## [1.7.1] — 2026-08-27

Tier 1 of the roadmap in `CLAUDE.md`: the confirmed defects from hardware testing.

### Fixed

- **[High] Changing a user's role had no effect, and every new user was created as a Viewer** (#26) — `templates/index.html` defined `userRole` twice: the role badge in the topbar and the role dropdown in the user modal. `getElementById` returns the first match, so all role handling was reading and writing the *badge*. The role was read as `undefined`, `JSON.stringify` omits undefined keys, and the API therefore never received a role at all — leaving it unchanged on update and falling back to `viewer` on create, regardless of what was selected. The dropdown is now `userRoleSelect`. All templates were swept for other duplicate ids; there are none.
- **[Medium] Clicking the drop zone opened the file picker but never uploaded** (#27) — the click triggered the upload modal's file input, which only uploads when the modal's own Upload button is pressed. With the modal closed, the chosen file sat in a hidden input and nothing happened, with no error. The drop zone now has its own dedicated input that uploads immediately, matching the drag-and-drop path.
- Upload results are now reported accurately. The drag-and-drop path previously announced success unconditionally, even when every file had failed; both paths now share one helper that counts successes and failures and reports each.

### Added

- **Thumbnails in the Add from Library picker** (#31) — the playlist editor's asset picker showed only a generic type icon and filename, which made picking the right image difficult in a library of any size. It now shows the real thumbnail where one exists, falling back to the type icon, consistent with the Assets grid and the playlist rows.

---

## [1.7.0] — 2026-08-27

Tier 0 of the roadmap in `CLAUDE.md`: the defects that made a deployed screen
show the wrong thing, or nothing at all.

### Fixed

- **[Critical] The player restarted the playlist from item 1 every 5 minutes** (#13) — The reload that picks up schedule changes called `showItem(0)` on every poll regardless of whether anything had changed. Any playlist whose content ran longer than five minutes **never reached its later items**, and whatever was playing at the five-minute mark was cut off mid-item. Reported from the field as "the schedule is ignoring additional assets", which is exactly what it looked like. `loadPlaylist()` now fingerprints the playlist (id, loop flag, and each item's asset, URI, duration, and override) and only restarts playback when that fingerprint actually changes.
- **[High] A transient API failure blanked a working screen** (#14) — Any momentary fetch failure — a service restart, an nginx reload, a network blip — replaced playing content with the setup screen. The player now keeps showing its current playlist and retries on the next poll, falling back to the setup screen only when there is genuinely nothing to display.
- **[High] The kiosk could show a white screen forever** (#29) — Chromium was pointed straight at `/player`. If that request failed at the moment the browser launched, Chromium sat on an error page indefinitely; it will not retry on its own, so the only recovery was a power cycle. The browser now loads `static/kiosk.html`, a self-contained bootstrap page Nginx serves **from disk** — so it loads even while the application is starting or down — which polls the app and hands over to the player once it answers. *Note: this makes the failure recoverable but the original root cause is still unconfirmed; `journalctl -u lumina-kiosk` from an affected device is needed.*

### Changed

- **Content changes now reach the screen in seconds** (#30) — the player polls every 15 seconds instead of every 5 minutes. Safe to do frequently now that a poll no longer restarts playback. Previously an edit could take five minutes to appear with no feedback, which read as the product being broken.
- **The version is defined in one place** — `__version__` in `app.py`, exposed to templates as `{{ app_version }}`. The admin badge and login footer had been hardcoded to `v1.2` since v1.3; both now track the real version. Groundwork for the update path in #9.

### Added

- **`CLAUDE.md`** — architecture, conventions, the landmines found during hardware testing, and the tiered roadmap, so work can continue a tier at a time across sessions.

---

## [1.6.1] — 2026-08-27

### Fixed

- **[High] WiFi was completely unusable on the appliance image** (#28) — Raspberry Pi OS keeps the WiFi radio rfkill-blocked until a wireless regulatory country is set, and the pi-gen config never set one. The radio was blocked on every flashed device, which meant no WiFi scanning, no setup hotspot on a device with no cable, and a Network page that could not offer WiFi at all — with nothing anywhere explaining why. Image builds now set `WPA_COUNTRY` (default `US`, override with the environment variable for other regions), and `install_rpi.sh` gained `--wifi-country` (default `US`) which sets the country and unblocks the radio for installs onto an existing system. `rfkill`, `iw`, and `wireless-regdb` are now installed on the image.
- **Device timezone defaulted to UTC** (part of #16) — the same pi-gen config block never set `TIMEZONE_DEFAULT`, so schedules ran on UTC and fired at the wrong local hour. Images now default to `America/New_York`, overridable at build time. The admin-facing timezone control tracked in #16 is still outstanding.

---

## [1.6.0] — 2026-08-27

### Changed

- **Appliance image — Raspberry Pi OS Lite base** — The SD-card image no longer builds the full desktop. It now uses the Lite stages plus Chromium and `cage` (a single-application Wayland compositor), roughly halving the image and removing the desktop session, file manager, and panel that signage never used.
- **Kiosk is a systemd service, not a desktop autostart entry** — `lumina-kiosk.service` runs the browser under `cage` with explicit ordering after `lumina.service`. This removes the first-boot race where the autostart entry was written *after* the desktop session had already read `/etc/xdg/autostart`, so the player never appeared until a manual reboot. On a full desktop install the installer still uses XDG autostart, detected automatically.
- **The image installs at build time, not first boot** — the virtualenv and `pip install` now run inside the pi-gen chroot. A flashed device comes up playing content with **no internet connection required**. Previously a missing network made `pip` fail, which aborted the entire first-boot installer under `set -e` and silently left a stock desktop with no Lumina. First boot now only regenerates the session signing key so devices flashed from one image do not share it.
- **Console blanking disabled** on appliance installs via `consoleblank=0`.

### Added

- **WiFi setup hotspot** (`lumina-netwatch`) — a **last resort for wireless-only sites**. It broadcasts a WPA2 access point (`LuminaShow-Setup` / `luminasetup`) only when the device has no active connection *and* no Ethernet cable attached. A connected cable suppresses it entirely — link state is read from the interface carrier, so slow or failed DHCP on a wired screen never triggers WiFi instructions — and plugging a cable in later takes the hotspot down. Where it does apply, connect a phone or laptop, open `http://10.42.0.1`, and use the Network page to join the real network. This closes the chicken-and-egg gap where the network admin UI was unreachable precisely when it was needed: moving a wireless screen to a new site no longer needs a keyboard, monitor, or SSH.
- **On-screen setup guide** — with no content, the player now shows large, room-readable numbered instructions instead of a near-black "No content scheduled" message: either how to join the setup hotspot, or the device's IP/hostname and the steps to add content. It refreshes every 15 seconds, so the screen updates itself as the device joins a network or receives its first playlist.
- **`GET /api/device-info`** — unauthenticated endpoint (like `/api/current-playlist`) returning hostname, IPv4 addresses, and setup-hotspot state for the player's setup screen.

---

## [1.5.0] — 2026-08-27

### Added

- **Network management in the admin UI** (#7) — New Admin-only **Network** page:
  - **Hostname** — view and change the device hostname (updates `/etc/hosts` too; device stays reachable as `http://<hostname>.local`).
  - **Interfaces** — per-interface status cards (IP, gateway, DNS, DHCP/Static badge, WiFi SSID + signal) with a **Configure IP** dialog to switch between DHCP and static IPv4 (address/prefix, gateway, DNS), including a warning + confirmation since IP changes can drop the admin session.
  - **WiFi** — scan for nearby networks (signal strength, security), join a network with a passphrase, see the currently connected SSID.
  - Backend: `/api/network/*` endpoints validate every input (hostname/device regexes, `ipaddress`-parsed CIDR/gateway/DNS, SSID/passphrase length + control-character checks) and delegate privileged changes to a new `scripts/lumina-net` helper invoked via `sudo -n`. The helper re-validates all arguments and reads the WiFi passphrase from stdin so it never appears in the process list. Installers provision `/usr/local/sbin/lumina-net` plus a sudoers entry scoped to exactly that script; the uninstaller removes both.
  - On systems without NetworkManager (`nmcli`) the page shows a clear "not available" notice and the endpoints return 503.

---

## [1.4.1] — 2026-08-27

### Fixed

- **[High] Kiosk autostart never ran on Raspberry Pi OS Bookworm** (#3) — The autostart desktop entry declared `OnlyShowIn=LXDE;`, but Bookworm sessions identify as `LXDE-pi-wayfire` / `wayfire` / `labwc`, so the player never launched on boot. The restriction has been removed.
- **[High] Videos did not autoplay in kiosk mode** (#3) — Chromium blocks autoplay with sound without a user gesture, so video and YouTube items never started on their own. Kiosk launch now passes `--autoplay-policy=no-user-gesture-required`; installer banners and README examples updated to match.
- **[Medium] Kiosk browser could race the server on boot** (#3) — Chromium could start before nginx/gunicorn were ready, leaving a permanent "connection refused" page. The new `/usr/local/bin/lumina-kiosk` launcher waits for `http://localhost/player` to respond before starting the browser.
- **[Medium] Display blanked after 10 minutes on kiosk installs** (#3) — `install_rpi.sh --kiosk-user` now disables screen blanking via `raspi-config nonint do_blanking 1`.
- **[Medium] Pi Image CI never passed** — Every scheduled run failed on an info-level shellcheck finding (`SC1091` for `source /etc/os-release`), and GitHub then auto-disabled the workflow for inactivity. Suppressed the false positive and re-enabled the workflow.
- **[High] YouTube embed errors froze the player** (#6) — When YouTube refused playback (embedding disabled, deleted video, ended live stream — reported as `api.invalidparam`), the player sat on YouTube's error screen for the item's full duration. The embed now loads with `enablejsapi=1` and an `origin` parameter, and the player listens for the embed's `onError` events via the widget postMessage protocol: broken videos display a brief reason (e.g., "embedding disabled — skipping") and advance to the next item after 1.5 seconds. Also added `playsinline=1` for reliable inline playback on kiosk browsers.

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


