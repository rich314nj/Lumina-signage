# LuminaShow — working notes

Self-hosted digital signage for Raspberry Pi 4/5. Positioned as a direct
replacement for Anthias/Screenly OSE, with the differentiator being **setup and
network management that a non-technical person can do without a keyboard**.

Repo: `rich314nj/Lumina-signage` · Current version: **1.11.0**

---

## Architecture

One device runs everything — there is no separate server.

```
Chromium (kiosk, under cage) ──┐
                               ├─► Nginx :80 ──► Gunicorn :8080 ──► Flask (app.py) ──► SQLite
Admin browser (any machine) ───┘                                                  └──► static/uploads/
```

| Piece | Where |
|---|---|
| Flask app, all REST API | `app.py` (single file) |
| Admin SPA | `templates/index.html` (vanilla JS, no build step) |
| Player | `templates/player.html` |
| Kiosk bootstrap page | `static/kiosk.html` (served by Nginx from disk) |
| Privileged helpers | `scripts/lumina-net`, `scripts/lumina-kiosk`, `scripts/lumina-netwatch` |
| Installers | `install_rpi.sh` (Pi), `install.sh` (Ubuntu), `uninstall.sh` |
| Image build | `image/pi-gen/` + `.github/workflows/pi-image-ci.yml` |

**systemd units**: `lumina` (app), `lumina-kiosk` (display), `lumina-netwatch`
(WiFi setup hotspot), `lumina-firstboot` (regenerates `SECRET_KEY` once).

---

## Conventions that matter

**Version lives in exactly one place** — `__version__` in `app.py`, surfaced to
templates as `{{ app_version }}` by a context processor. Never hardcode it in
the UI; it was stale at `v1.2` for four releases because of that.

**Privileged actions go through a helper, never direct sudo.** `scripts/lumina-net`
is the only thing the `lumina` user may run as root (single scoped sudoers
entry). Every argument is validated in the Flask endpoint *and* re-validated in
the helper. Secrets (WiFi passphrases) travel on stdin so they never appear in
the process list. Follow this pattern for any new privileged capability.

**Never interpolate untrusted values into HTML attributes.** Pass numeric ids or
array indices into `onclick` and look the object up from state — see
`state.usersById` and `openWifiConnect(idx)`. `esc()` escapes single quotes too.

**Shell scripts are LF-only** (enforced in `.gitattributes`) and installers
`sed -i 's/\r$//'` anything they install, because this repo is edited on Windows.

**The image must work with no internet.** The virtualenv and pip install happen
in the pi-gen chroot at build time. Anything that needs a network at first boot
is a bug — that failure mode silently produced a blank device once already.

---

## Local development

```bash
python app.py                 # http://localhost:8080, admin / admin123
```

```bash
pip install -r requirements-dev.txt
python -m pytest              # 106 tests; also runs in CI on 3.11 and 3.12
bash -n install_rpi.sh scripts/lumina-*    # CI also runs shellcheck
```

Tests live in `tests/`. `DATABASE_URL` points them at a scratch database, set in
`conftest.py` **before** importing `app` — the app configures itself at import
time, so that ordering matters.

For player/admin JS there is no test runner: extract the inline `<script>` block
and run `node --check`, then exercise behaviour in a browser against a local
server. Anything genuinely testable is better moved into Python.

**Images build only on native arm64** (`ubuntu-24.04-arm` in CI). Cross-building
under `qemu-user-static` segfaults configuring arm64 packages in the chroot —
do not try to "fix" it by reintroducing qemu.

---

## Landmines discovered the hard way

- **`OnlyShowIn=LXDE`** never matches Bookworm sessions (`LXDE-pi-wayfire`,
  `labwc`). Appliance installs now use a systemd unit instead of XDG autostart.
- **Chromium blocks autoplay with sound** without
  `--autoplay-policy=no-user-gesture-required`. Video simply never starts.
- **WiFi is rfkill-blocked** until a regulatory country is set — `WPA_COUNTRY`
  in the pi-gen config, `--wifi-country` in the installer. Without it there is
  no WiFi at all and nothing says why.
- **Duplicate DOM ids** silently break things: `getElementById` returns the
  first match. This shipped once (`userRole` badge vs select) and made every new
  user a Viewer. Worth grepping for on any UI change.
- **A white kiosk screen means Chromium is not showing our page** — the player
  body is `#000`. White is a browser error/blank page.
- **A *healthy* kiosk service does not mean a visible kiosk.** `cage` can run
  happily while the console `getty` owns the active VT, so the screen shows boot
  text and the journal shows nothing wrong. The unit needs
  `Conflicts=getty@tty1.service` and `StandardInput=tty-force`; `tty-fail` does
  not fail loudly, it just loses the display. Diagnose with
  `systemctl stop getty@tty1 && systemctl restart lumina-kiosk` — if that fixes
  it, it is VT contention.
- **Anything the installer *generates* is invisible to an update.** Unit files,
  the nginx config, helpers, and sudoers grants are written by
  `install_rpi.sh`, not shipped as files, so syncing new code does not refresh
  them — a device can run new code under an old unit and report the new
  version. `lumina-update` calls `install_rpi.sh --reprovision` for this.
  **When you change a generated file, check the update path carries it.**
- **pi-gen needs `DISABLE_FIRST_BOOT_USER_RENAME=1`.** Setting `FIRST_USER_NAME`
  alone is not enough: the first-boot user wizard still ships, and
  `userconfig.service` blocks on tty1 with no timeout waiting for input.
- **The Pi cannot scan for WiFi while acting as an access point.** One radio,
  and the driver will not do both. Anything needing a network list while the
  setup hotspot is up must scan and cache beforehand (see #38). A `Scan` that
  returns nothing while connected over the hotspot is this, not a bug.

---

## Roadmap — work through the tiers in order

Trust before features: the product's problem is reliability, not capability.

### Tier 0 — Blockers ✅ done in 1.7.0
- ~~#13 playlist restarted from item 1 every 5 minutes~~ — hardware-verified
- ~~#29 kiosk white screen with no recovery~~ — bootstrap page shipped (1.7.0);
  **actual root cause found and fixed in 1.9.2**, see Tier 2

### Tier 1 — Confirmed quick fixes ✅ done in 1.7.0 / 1.7.1, hardware-verified
- ~~#14 transient API failure blanked a working screen~~
- ~~#30 content changes took up to 5 minutes to appear~~
- ~~#26 user role never changed (duplicate `userRole` id)~~
- ~~#27 clicking the drop zone opened the picker but never uploaded~~
- ~~#31 thumbnails in the Add-from-Library picker~~

### UI polish backlog ✅ #40 done in 1.10.0, rest opportunistic
- ~~**#40 playlist editor is too narrow**~~ — fixed with a `@container` query on
  `.playlist-split` (the modal itself, `.modal-lg`, now sets
  `container-type: inline-size` via the base `.modal` rule) rather than another
  viewport breakpoint — the lesson that mattered: the constraint was the
  *modal's* width, not the *viewport's*, so a `@media` rule could never fire at
  the right size regardless of window width.
- #39 follow-up — the playlist editor's drag-to-reorder, the asset grid, and the
  schedule day picker have not been reviewed at phone width.

### Tier 2 — Make failures survivable ✅ done, hardware-verified
- ~~#32 reboot / shutdown / restart-display controls~~ — UI shipped 1.9.0, but the
  kiosk unit had a real bug the controls exposed: `StandardInput=tty-fail` does
  not fail when `getty@tty1` already owns the console — it starts anyway
  without becoming the active VT, so the screen showed boot text while the
  service reported healthy. Root cause found via
  `systemctl stop getty@tty1 && systemctl restart lumina-kiosk` (which is now
  what `Conflicts=getty@tty1.service` automates), fixed in **1.9.2**, all three
  controls confirmed working on hardware.
- ~~#10 health reporting + player heartbeat~~ — hardware-verified; heartbeat
  correctly showed the playing filename during the #32 diagnosis
- ~~#15 vendor PDF.js locally~~ — downloaded by the installers into
  `static/vendor/pdfjs/` (gitignored), player falls back to the CDN if absent
- ~~#28 remainder~~ — Network page explains a blocked radio and offers a
  country field; hardware-verified (WiFi scan, connect, and status all working)

### Tier 3 — Lock it in, then make it shippable ✅ done, hardware-verified
- ~~#22 test suite~~ — 125 tests in `tests/`, CI on 3.11 and 3.12
- ~~#9 update path~~ — `scripts/lumina-update` + the System page.
  **Confirmed on hardware twice**: 1.9.1→1.9.2 and 1.9.2→1.9.3. The second
  update caught a real gap (#41, fixed in 1.9.3): systemd units and nginx
  config are *generated* by `install_rpi.sh`, not shipped as files, so an
  update never refreshed them — a device could run new code under an old unit
  while reporting the new version. `install_rpi.sh --reprovision` fixes this;
  `lumina-update` calls it after sync and again on rollback. **Rule: anything
  the installer generates is invisible to updates — check the update path
  when changing a generated file.**

### Tier 4 — Hardening ✅ done in 1.11.0
- ~~#11 SD card wear~~ — the fix was logging, not polling frequency: nginx
  `access_log off` for the polling endpoints, gunicorn access log dropped
  entirely, journald capped (persistent, not volatile — `journalctl` on a
  past boot is this project's standard field-diagnosis tool), SQLite WAL +
  `synchronous=NORMAL`. 15s polling untouched. **Still open, deliberately
  deferred**: SSE as the real long-term fix (nginx already has
  `proxy_buffering off`; needs threaded gunicorn workers, not sync) — revisit
  if #11's logging fix ever proves insufficient in the field.
- ~~#12 per-device credentials~~ — random admin password generated per fresh
  install, shown once on the setup screen, deleted the moment any login
  succeeds (`/etc/lumina/first-boot-password`, same exposure pattern as the
  hotspot password); login throttled (10/5min per IP via `ProxyFix`);
  session cookie `HttpOnly`+`SameSite=Lax`; gunicorn bound to `127.0.0.1`
  instead of `0.0.0.0`. HTTPS deliberately out of scope (see the issue).
- ~~#23 backup/restore~~ — export/import on the System page, new
  `scripts/lumina-backup` helper using the same detach-via-`systemd-run`
  pattern as `lumina-update`, previous state backed up before any restore.
- ~~#24 storage hygiene~~ — orphan file detection (report-then-delete, two
  separate calls) correctly checks both `Asset.uri` *and* `Asset.thumbnail`;
  uploads refused with `507` below a free-space floor.
- **Bug found while building #23**: `/api/health`'s disk report and the new
  backup export both hardcoded `BASE_DIR / "lumina.db"` instead of reading
  `SQLALCHEMY_DATABASE_URI` back — harmless until `DATABASE_URL` is actually
  used to move the db off the SD card (which #11 introduced that var to
  support), at which point both would have silently operated on the wrong,
  empty file. Fixed via a shared `database_file_path()` helper. **Grep for
  `BASE_DIR / "lumina.db"` before adding a third call site.**

### Tier 5 — Features, in market-value order
- #17 rotation/portrait (biggest market unlock)
- **#38 zero-typing setup.** Item 1 (WiFi QR code) ✅ **done in 1.10.0** —
  server-side SVG via the `qrcode` lib (no Pillow), two unauthenticated
  endpoints (`/api/device-info/qr/wifi.svg`, `/api/device-info/qr/address.svg`)
  matching `/api/device-info`'s exposure, rendered beside the existing text
  instructions on both setup-screen states. **Remaining**: the captive portal
  (item 3) and the network-picker (item 4) — note the single-radio
  constraint documented there: the Pi cannot scan while acting as an access
  point, so any network list must be scanned and cached *before* the hotspot
  goes up.
- ~~#16 timezone UI~~ ✅ **done in 1.10.0** — Date & Time card on the System
  page, backed by a new `timezone` action in `scripts/lumina-net` (validates
  against `timedatectl list-timezones` on-device; the zone list itself comes
  from Python's stdlib `zoneinfo`, so it works even where `timedatectl` is
  absent for listing purposes). **1.10.1 extended the same card**: the Pi has
  no battery-backed RTC, so timezone alone doesn't fix a wrong clock — if NTP
  never syncs (offline first boot, isolated site), the underlying time can be
  wrong with no fix but SSH. Added a sync/not-synced badge, a manual
  date/time override (`clock-set` action: `set-ntp false` + `set-time`), and
  a resync button (`ntp-enable`). `GET /api/system/clock` needs no privilege
  (`timedatectl show` is world-readable); only the `POST` goes through the
  helper. **Landmine for later**: this was found by the user asking "how is
  the clock itself corrected" right after the timezone control shipped —
  worth remembering that a *timezone* fix and a *clock* fix are two different
  problems that look like one from the outside.
- #18 asset date ranges · #25 playlist preview · #21 volume and fit ·
  #19 display power (CEC)

### Pre-release polish — do last, once the UI has stopped moving
- **#43 in-app help** — a help icon opening built-in end-user documentation.
  Must be **bundled locally**, never an external link: the appliance is offline
  by design, and help is most needed exactly where there is no connectivity
  (same trap as #15). Source material already exists in the operator guide
  written during development.

### Tier 6 — Architecture
- #4 standalone player → #8 fleet management (v2.5), designed together ·
  #20 multi-zone layouts

### Needs hardware verification, then close
- ~~#3~~ hardware-verified and closed.
- #7 network management page — hostname/WiFi/status/scan all confirmed on
  hardware; only the Ethernet→WiFi live-swap case (unplug cable while running)
  is still untested. Keep open until that's exercised.
- #42 (schedule playlist not saving) fixed in code 2026-08-28, awaiting
  hardware confirmation like everything else in this list.

---

## Release checklist

1. Bump `__version__` in `app.py` (nothing else hardcodes it)
2. Add a `CHANGELOG.md` entry — severity tags and issue numbers
3. Update `README.md` and `docs/RASPBERRY_PI.md` if behaviour changed
4. Push to `main` — CI rebuilds the image automatically (~7 min, native arm64)
5. Comment on the issues fixed; leave them open until hardware-verified
