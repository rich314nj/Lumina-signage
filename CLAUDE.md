# LuminaShow — working notes

Self-hosted digital signage for Raspberry Pi 4/5. Positioned as a direct
replacement for Anthias/Screenly OSE, with the differentiator being **setup and
network management that a non-technical person can do without a keyboard**.

Repo: `rich314nj/Lumina-signage` · Current version: **1.9.0**

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
- **The Pi cannot scan for WiFi while acting as an access point.** One radio,
  and the driver will not do both. Anything needing a network list while the
  setup hotspot is up must scan and cache beforehand (see #38). A `Scan` that
  returns nothing while connected over the hotspot is this, not a bug.

---

## Roadmap — work through the tiers in order

Trust before features: the product's problem is reliability, not capability.

### Tier 0 — Blockers ✅ done in 1.7.0
- ~~#13 playlist restarted from item 1 every 5 minutes~~
- ~~#29 kiosk white screen with no recovery~~ (bootstrap page; **root cause still
  unconfirmed — needs `journalctl -u lumina-kiosk` from the affected device**)

### Tier 1 — Confirmed quick fixes ✅ done in 1.7.0 / 1.7.1
- ~~#14 transient API failure blanked a working screen~~
- ~~#30 content changes took up to 5 minutes to appear~~
- ~~#26 user role never changed (duplicate `userRole` id)~~
- ~~#27 clicking the drop zone opened the picker but never uploaded~~
- ~~#31 thumbnails in the Add-from-Library picker~~

### Tier 2 — Make failures survivable ✅ done in 1.9.0
- ~~#32 reboot / shutdown / restart-display controls~~ — on the System page
- ~~#10 health reporting + player heartbeat~~
- ~~#15 vendor PDF.js locally~~ — downloaded by the installers into
  `static/vendor/pdfjs/` (gitignored), player falls back to the CDN if absent
- ~~#28 remainder~~ — Network page explains a blocked radio and offers a
  country field

### Tier 3 — Lock it in, then make it shippable ✅ done in 1.8.0
- ~~#22 test suite~~ — 106 tests in `tests/`, CI on 3.11 and 3.12
- ~~#9 update path~~ — `scripts/lumina-update` + the System page. **Untested on
  real hardware**: the first genuine test is updating a device from 1.8.0 to
  whatever ships next. Until that has happened once, treat it as unproven.

### Tier 4 — Hardening
- #11 SD card wear · #12 per-device credentials · #23 backup/restore ·
  #24 storage hygiene

### Tier 5 — Features, in market-value order
- #17 rotation/portrait (biggest market unlock)
- **#38 zero-typing setup — WiFi QR code and captive portal.** Deepens the main
  differentiator against Anthias. Start with the QR code: small, self-contained,
  and most of the benefit. Note the single-radio constraint documented there —
  the Pi cannot scan while acting as an access point, so any network list must
  be scanned and cached *before* the hotspot goes up.
- #16 timezone UI · #18 asset date ranges · #25 playlist preview ·
  #21 volume and fit · #19 display power (CEC)

### Tier 6 — Architecture
- #4 standalone player → #8 fleet management (v2.5), designed together ·
  #20 multi-zone layouts

### Needs hardware verification, then close
- #3 kiosk on boot and #7 network management page — both predate the v1.6
  appliance rework, so re-verify on a current image rather than assuming.

---

## Release checklist

1. Bump `__version__` in `app.py` (nothing else hardcodes it)
2. Add a `CHANGELOG.md` entry — severity tags and issue numbers
3. Update `README.md` and `docs/RASPBERRY_PI.md` if behaviour changed
4. Push to `main` — CI rebuilds the image automatically (~7 min, native arm64)
5. Comment on the issues fixed; leave them open until hardware-verified
