# LuminaShow — working notes

Self-hosted digital signage for Raspberry Pi 4/5. Positioned as a direct
replacement for Anthias/Screenly OSE, with the differentiator being **setup and
network management that a non-technical person can do without a keyboard**.

Repo: `rich314nj/Lumina-signage` · Current version: **1.7.0**

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

Verification used in place of a test suite (see #22 — there is no test suite yet):

```bash
python -c "import ast; ast.parse(open('app.py', encoding='utf-8').read())"
bash -n install_rpi.sh scripts/lumina-*    # CI also runs shellcheck
```

For player/admin JS, extract the inline `<script>` block and run `node --check`.

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

---

## Roadmap — work through the tiers in order

Trust before features: the product's problem is reliability, not capability.

### Tier 0 — Blockers ✅ done in 1.7.0
- ~~#13 playlist restarted from item 1 every 5 minutes~~
- ~~#29 kiosk white screen with no recovery~~ (bootstrap page; **root cause still
  unconfirmed — needs `journalctl -u lumina-kiosk` from the affected device**)

### Tier 1 — Confirmed quick fixes ✅ mostly done in 1.7.0
- ~~#14 transient API failure blanked a working screen~~
- ~~#30 content changes took up to 5 minutes to appear~~
- #26 user role never changes (duplicate `userRole` id) — **next**
- #27 clicking the drop zone opens the picker but never uploads — **next**
- #31 thumbnails in the Add-from-Library picker — **next**

### Tier 2 — Make failures survivable
- #32 reboot / shutdown / restart-display controls
- #10 health reporting, especially a player heartbeat
- #15 vendor PDF.js locally (PDFs currently need internet)
- #28 remainder — Network page should explain a blocked WiFi radio

### Tier 3 — Lock it in, then make it shippable
- #22 test suite — schedule resolution and URL parsers first
- #9 update path — **required before deploying anywhere you cannot walk to**
  (also fixes version reporting end to end)

### Tier 4 — Hardening
- #11 SD card wear · #12 per-device credentials · #23 backup/restore ·
  #24 storage hygiene

### Tier 5 — Features, in market-value order
- #17 rotation/portrait (biggest market unlock) · #16 timezone UI ·
  #18 asset date ranges · #25 playlist preview · #21 volume and fit ·
  #19 display power (CEC)

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
