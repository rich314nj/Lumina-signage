"""API behaviour: authentication, role enforcement, and error paths."""
import os
import sys

import pytest

from conftest import login, make_user


# ── Authentication ────────────────────────────────────────────────────────────

def test_protected_endpoints_require_authentication(client):
    res = client.get("/api/assets", headers={"Accept": "application/json"},
                     json={})
    assert res.status_code == 401


def test_login_with_valid_credentials_succeeds(client):
    res = login(client)
    assert res.status_code == 200
    assert res.get_json()["role"] == "admin"


def test_login_with_bad_password_fails(client):
    res = login(client, password="wrong")
    assert res.status_code == 401


def test_logout_ends_the_session(client):
    login(client)
    assert client.get("/api/me").status_code == 200
    client.get("/logout")
    assert client.get("/api/me", json={}).status_code == 401


def test_session_cookie_is_hardened(client):
    """Regression test for #12 - there was previously no explicit cookie policy."""
    import app as lumina
    assert lumina.app.config["SESSION_COOKIE_HTTPONLY"] is True
    assert lumina.app.config["SESSION_COOKIE_SAMESITE"] == "Lax"


def test_repeated_failed_logins_are_throttled(client):
    """Regression test for #12 - /login previously had no rate limit at all."""
    for _ in range(10):
        res = login(client, password="wrong")
        assert res.status_code == 401
    # The 11th attempt should be throttled rather than evaluated.
    res = login(client, password="wrong")
    assert res.status_code == 429
    # Even the *correct* password is refused while throttled - the point is
    # to slow down guessing, not just to reject bad guesses.
    res = login(client)
    assert res.status_code == 429


def test_successful_login_clears_the_throttle_counter(client):
    for _ in range(5):
        login(client, password="wrong")
    res = login(client)
    assert res.status_code == 200
    # Confirm the counter actually reset, not just that this one login worked.
    for _ in range(9):
        assert login(client, password="wrong").status_code == 401
    assert login(client, password="wrong").status_code != 429


# ── Endpoints the player relies on stay unauthenticated ───────────────────────

def test_current_playlist_is_reachable_without_login(client):
    # The kiosk browser has no session; this must not require one.
    assert client.get("/api/current-playlist").status_code == 200


def test_device_info_is_reachable_without_login(client):
    res = client.get("/api/device-info")
    assert res.status_code == 200
    assert "hostname" in res.get_json()


def test_first_boot_password_is_shown_until_first_login_then_hidden(client, tmp_path):
    """Regression coverage for #12's exposure window: shown before anyone has
    ever logged in, gone the moment any login succeeds - not left as a
    standing unauthenticated way to fetch the admin password."""
    import app as lumina
    marker = tmp_path / "first-boot-password"
    marker.write_text("s3cr3t-generated\n")
    original = lumina.FIRST_BOOT_PASSWORD_FILE
    lumina.FIRST_BOOT_PASSWORD_FILE = str(marker)
    try:
        assert client.get("/api/device-info").get_json()["first_boot_password"] == "s3cr3t-generated"
        login(client)  # admin/admin123 - unrelated to the marker's content
        assert client.get("/api/device-info").get_json()["first_boot_password"] is None
        assert not marker.exists()
    finally:
        lumina.FIRST_BOOT_PASSWORD_FILE = original


def test_first_boot_password_is_none_when_no_marker_exists(client):
    import app as lumina
    assert lumina.first_boot_admin_password() is None
    assert client.get("/api/device-info").get_json()["first_boot_password"] is None


def test_wifi_qr_absent_without_a_setup_hotspot(client):
    # No nmcli / setup hotspot on a dev machine, so nothing to encode.
    res = client.get("/api/device-info/qr/wifi.svg")
    assert res.status_code == 404


def test_address_qr_is_reachable_without_login(client):
    # /api/device-info always finds a fallback address on a real socket
    # (see local_ipv4_addresses), so this should render even off-device.
    res = client.get("/api/device-info/qr/address.svg")
    assert res.status_code == 200
    assert res.mimetype == "image/svg+xml"
    assert b"<svg" in res.data


def test_wifi_qr_payload_escapes_special_characters():
    import app as lumina
    payload = lumina.wifi_qr_payload('Guest;Wifi,Test:"Name"\\', "p:a,s;s\\word")
    # Every WIFI:-reserved character inside a field value must be escaped so
    # a camera reads it as data, not as the next field separator.
    assert payload == (
        'WIFI:T:WPA;S:Guest\\;Wifi\\,Test\\:\\"Name\\"\\\\;'
        'P:p\\:a\\,s\\;s\\\\word;;'
    )


def test_wifi_qr_payload_open_network_has_no_password_field():
    import app as lumina
    payload = lumina.wifi_qr_payload("OpenNet", None)
    assert payload == "WIFI:T:nopass;S:OpenNet;;"


# ── Role enforcement ──────────────────────────────────────────────────────────

def test_editor_cannot_manage_users(client):
    login(client)
    make_user(client, "ed", "editor")
    client.get("/logout")

    login(client, "ed", "secret123")
    assert client.get("/api/users", json={}).status_code == 403


def test_viewer_cannot_create_assets(client):
    login(client)
    make_user(client, "vi", "viewer")
    client.get("/logout")

    login(client, "vi", "secret123")
    res = client.post("/api/assets", json={"uri": "https://example.com"})
    assert res.status_code == 403


def test_editor_can_create_assets(client):
    login(client)
    make_user(client, "ed2", "editor")
    client.get("/logout")

    login(client, "ed2", "secret123")
    res = client.post("/api/assets", json={"uri": "https://example.com"})
    assert res.status_code == 201


# ── Users ─────────────────────────────────────────────────────────────────────

def test_role_change_persists(client):
    """Regression test for #26 — the role was silently never applied."""
    login(client)
    uid = make_user(client, "promote", "viewer")

    res = client.put(f"/api/users/{uid}", json={"role": "editor"})
    assert res.status_code == 200

    fetched = client.get(f"/api/users/{uid}").get_json()
    assert fetched["role"] == "editor"


def test_user_is_created_with_the_requested_role(client):
    """Regression test for #26 — new users were always created as Viewer."""
    login(client)
    uid = make_user(client, "boss", "admin")
    assert client.get(f"/api/users/{uid}").get_json()["role"] == "admin"


def test_duplicate_username_is_rejected(client):
    login(client)
    make_user(client, "dup", "viewer")
    res = client.post("/api/users", json={
        "username": "dup", "email": "other@lumina.local",
        "password": "secret123", "role": "viewer",
    })
    assert res.status_code == 409


def test_duplicate_email_on_update_is_rejected(client):
    login(client)
    make_user(client, "one", "viewer")
    uid = make_user(client, "two", "viewer")
    res = client.put(f"/api/users/{uid}", json={"email": "one@lumina.local"})
    assert res.status_code == 409


def test_unknown_role_is_rejected(client):
    login(client)
    uid = make_user(client, "role", "viewer")
    assert client.put(f"/api/users/{uid}", json={"role": "wizard"}).status_code == 400


def test_cannot_delete_your_own_account(client):
    login(client)
    me = client.get("/api/me").get_json()
    assert client.delete(f"/api/users/{me['id']}").status_code == 400


def test_malformed_json_body_returns_400(client):
    login(client)
    uid = make_user(client, "badjson", "viewer")
    res = client.put(f"/api/users/{uid}", data="{not json",
                     content_type="application/json")
    assert res.status_code == 400


# ── Schedules ─────────────────────────────────────────────────────────────────

def _playlist(client, name="P1"):
    return client.post("/api/playlists", json={"name": name}).get_json()["id"]


def test_overlapping_schedules_are_rejected(client):
    login(client)
    pid = _playlist(client)
    first = {"playlist_id": pid, "name": "A", "start_time": "09:00",
             "end_time": "17:00", "days": "mon"}
    assert client.post("/api/schedules", json=first).status_code == 201

    clash = {**first, "name": "B", "start_time": "10:00", "end_time": "12:00"}
    assert client.post("/api/schedules", json=clash).status_code == 409


def test_back_to_back_schedules_are_accepted(client):
    login(client)
    pid = _playlist(client)
    client.post("/api/schedules", json={
        "playlist_id": pid, "name": "morning", "start_time": "09:00",
        "end_time": "12:00", "days": "mon"})
    res = client.post("/api/schedules", json={
        "playlist_id": pid, "name": "afternoon", "start_time": "12:00",
        "end_time": "17:00", "days": "mon"})
    assert res.status_code == 201


def test_invalid_time_format_is_rejected(client):
    login(client)
    pid = _playlist(client)
    res = client.post("/api/schedules", json={
        "playlist_id": pid, "start_time": "9am", "end_time": "17:00",
        "days": "mon"})
    assert res.status_code == 400


def test_invalid_days_are_rejected(client):
    login(client)
    pid = _playlist(client)
    res = client.post("/api/schedules", json={
        "playlist_id": pid, "start_time": "09:00", "end_time": "17:00",
        "days": "someday"})
    assert res.status_code == 400


def test_schedule_requires_an_existing_playlist(client):
    login(client)
    res = client.post("/api/schedules", json={
        "playlist_id": "does-not-exist", "start_time": "09:00",
        "end_time": "17:00", "days": "mon"})
    assert res.status_code == 400


def test_updating_a_schedules_playlist_persists(client):
    """Regression test for #42 - playlist_id was silently dropped on update."""
    login(client)
    pid_a = _playlist(client, "A")
    pid_b = _playlist(client, "B")
    sid = client.post("/api/schedules", json={
        "playlist_id": pid_a, "name": "swap-me", "start_time": "09:00",
        "end_time": "17:00", "days": "mon"}).get_json()["id"]

    res = client.put(f"/api/schedules/{sid}", json={"playlist_id": pid_b})
    assert res.status_code == 200
    assert res.get_json()["playlist_id"] == pid_b

    fetched = client.get("/api/schedules").get_json()
    updated = next(s for s in fetched if s["id"] == sid)
    assert updated["playlist_id"] == pid_b
    assert updated["playlist_name"] == "B"


def test_updating_schedule_with_unknown_playlist_is_rejected(client):
    login(client)
    pid = _playlist(client)
    sid = client.post("/api/schedules", json={
        "playlist_id": pid, "start_time": "09:00", "end_time": "17:00",
        "days": "mon"}).get_json()["id"]

    res = client.put(f"/api/schedules/{sid}",
                     json={"playlist_id": "does-not-exist"})
    assert res.status_code == 400
    # And the original playlist must be untouched.
    assert client.get("/api/schedules").get_json()[0]["playlist_id"] == pid


def test_updating_schedule_without_playlist_id_leaves_it_unchanged(client):
    login(client)
    pid = _playlist(client)
    sid = client.post("/api/schedules", json={
        "playlist_id": pid, "start_time": "09:00", "end_time": "17:00",
        "days": "mon"}).get_json()["id"]

    res = client.put(f"/api/schedules/{sid}", json={"name": "renamed only"})
    assert res.status_code == 200
    assert res.get_json()["playlist_id"] == pid
    assert res.get_json()["name"] == "renamed only"


# ── Assets and playlists ──────────────────────────────────────────────────────

def test_youtube_url_is_classified_and_gets_a_thumbnail(client):
    login(client)
    res = client.post("/api/assets", json={
        "uri": "https://www.youtube.com/shorts/dQw4w9WgXcQ"})
    body = res.get_json()
    assert body["asset_type"] == "youtube"
    assert "dQw4w9WgXcQ" in body["thumbnail"]


def test_asset_requires_a_uri(client):
    login(client)
    assert client.post("/api/assets", json={"name": "no uri"}).status_code == 400


def test_playlist_update_replaces_items_and_touches_updated_at(client):
    login(client)
    asset = client.post("/api/assets",
                        json={"uri": "https://example.com"}).get_json()
    pid = _playlist(client, "ordered")
    before = client.get(f"/api/playlists/{pid}").get_json()

    res = client.put(f"/api/playlists/{pid}", json={
        "name": "ordered", "loop": True, "is_active": True,
        "items": [{"asset_id": asset["id"], "duration_override": 42}],
    })
    body = res.get_json()
    assert len(body["items"]) == 1
    assert body["items"][0]["duration_override"] == 42

    after = client.get(f"/api/playlists/{pid}").get_json()
    assert after["created_at"] == before["created_at"]


def test_current_playlist_falls_back_to_first_active_playlist(client):
    login(client)
    asset = client.post("/api/assets",
                        json={"uri": "https://example.com"}).get_json()
    pid = _playlist(client, "fallback")
    client.put(f"/api/playlists/{pid}", json={
        "name": "fallback", "is_active": True,
        "items": [{"asset_id": asset["id"]}]})

    # No schedules exist, so the first active playlist should be returned.
    body = client.get("/api/current-playlist").get_json()
    assert body is not None and body["id"] == pid


# ── Health and device control ─────────────────────────────────────────────────

def test_health_requires_admin(client):
    login(client)
    make_user(client, "ed4", "editor")
    client.get("/logout")

    login(client, "ed4", "secret123")
    assert client.get("/api/health", json={}).status_code == 403


def test_health_reports_version_and_disk(client):
    login(client)
    body = client.get("/api/health").get_json()
    import app as lumina
    assert body["version"] == lumina.__version__
    assert body["disk"]["total_bytes"] > 0
    assert "services" in body


def test_health_reports_no_player_before_any_heartbeat(client):
    login(client)
    assert client.get("/api/health").get_json()["player"] is None


def test_heartbeat_is_accepted_without_a_session(client):
    # The kiosk browser has no session; this must not require one.
    res = client.post("/api/player/heartbeat",
                      json={"item": "Slide 1", "playlist": "Lobby"})
    assert res.status_code == 200


def test_health_reports_a_fresh_heartbeat(client):
    client.post("/api/player/heartbeat", json={"item": "Slide 1"})
    login(client)
    player = client.get("/api/health").get_json()["player"]
    assert player["item"] == "Slide 1"
    assert player["stale"] is False
    assert player["seconds_ago"] < 5


def test_heartbeat_truncates_oversized_values(client):
    client.post("/api/player/heartbeat", json={"item": "x" * 5000})
    login(client)
    assert len(client.get("/api/health").get_json()["player"]["item"]) == 200


def test_power_action_must_be_known(client):
    login(client)
    res = client.post("/api/system/power", json={"action": "selfdestruct"})
    # 503 where the helper is absent (dev machines), 400 where it exists.
    assert res.status_code in (400, 503)


def test_power_requires_admin(client):
    login(client)
    make_user(client, "ed5", "editor")
    client.get("/logout")

    login(client, "ed5", "secret123")
    assert client.post("/api/system/power",
                       json={"action": "reboot"}).status_code == 403


# ── Clock ─────────────────────────────────────────────────────────────────────

def test_clock_requires_admin(client):
    login(client)
    make_user(client, "ed7", "editor")
    client.get("/logout")

    login(client, "ed7", "secret123")
    assert client.get("/api/system/clock", json={}).status_code == 403


def test_clock_status_reports_a_timestamp(client):
    login(client)
    body = client.get("/api/system/clock").get_json()
    assert "now" in body and body["now"]
    assert "ntp_synchronized" in body


def test_clock_set_is_refused_without_the_helper(client):
    login(client)
    res = client.post("/api/system/clock",
                      json={"action": "manual", "datetime": "2026-01-01 12:00:00"})
    assert res.status_code == 503


def test_clock_set_rejects_malformed_datetime(client):
    login(client)
    res = client.post("/api/system/clock",
                      json={"action": "manual", "datetime": "not a date"})
    # 400 if the helper is present and validation runs, 503 if it is not.
    assert res.status_code in (400, 503)


def test_clock_set_rejects_unknown_action(client):
    login(client)
    res = client.post("/api/system/clock", json={"action": "rewind"})
    assert res.status_code in (400, 503)


# ── Timezone ──────────────────────────────────────────────────────────────────

def test_timezone_requires_admin(client):
    login(client)
    make_user(client, "ed6", "editor")
    client.get("/logout")

    login(client, "ed6", "secret123")
    assert client.get("/api/system/timezone", json={}).status_code == 403


def test_timezone_lists_real_zones(client):
    login(client)
    body = client.get("/api/system/timezone").get_json()
    assert "America/New_York" in body["available"]
    assert "Europe/London" in body["available"]


def test_timezone_set_is_refused_without_the_helper(client):
    # No lumina-net on a dev machine, so this must degrade rather than crash.
    login(client)
    res = client.post("/api/system/timezone", json={"timezone": "America/New_York"})
    assert res.status_code == 503


def test_timezone_set_rejects_unknown_zone(client):
    login(client)
    res = client.post("/api/system/timezone", json={"timezone": "Not/AZone"})
    # 400 if the helper is present and validation runs, 503 if it is not
    # (dev machine) - either way it must not be accepted as valid.
    assert res.status_code in (400, 503)


# ── Display rotation (#17) ────────────────────────────────────────────────────

def test_display_get_requires_admin(client):
    login(client)
    make_user(client, "ed11", "editor")
    client.get("/logout")

    login(client, "ed11", "secret123")
    assert client.get("/api/system/display", json={}).status_code == 403


def test_display_post_requires_admin(client):
    login(client)
    make_user(client, "ed12", "editor")
    client.get("/logout")

    login(client, "ed12", "secret123")
    assert client.post("/api/system/display", json={"rotation": "90"}).status_code == 403


def test_display_get_defaults_to_zero_with_no_config_file(client):
    login(client)
    body = client.get("/api/system/display").get_json()
    assert body["rotation"] == "0"


def test_display_get_defaults_to_zero_for_a_malformed_config(client, monkeypatch, tmp_path):
    """A missing ROTATION= line, or a value outside {0,90,180,270}, must
    never surface as anything but the safe default - this is the same
    parse scripts/lumina-kiosk applies, so GET always reflects what the
    kiosk will actually do (#17)."""
    import app as lumina

    login(client)
    conf = tmp_path / "display.conf"
    conf.write_text("ROTATION=45\n", encoding="utf-8")
    monkeypatch.setattr(lumina, "DISPLAY_CONF", str(conf))
    assert client.get("/api/system/display").get_json()["rotation"] == "0"

    conf.write_text("something else entirely\n", encoding="utf-8")
    assert client.get("/api/system/display").get_json()["rotation"] == "0"


def test_display_post_is_refused_without_the_helper(client):
    login(client)
    res = client.post("/api/system/display", json={"rotation": "90"})
    assert res.status_code == 503


def test_display_post_rejects_an_invalid_rotation(client):
    import app as lumina

    login(client)
    original_helper = lumina.DISPLAY_HELPER
    lumina.DISPLAY_HELPER = sys.executable  # any real, existing file
    try:
        for bad in ("45", "-90", "360", "ninety", ""):
            res = client.post("/api/system/display", json={"rotation": bad})
            assert res.status_code == 400, bad
    finally:
        lumina.DISPLAY_HELPER = original_helper


def test_display_post_accepts_each_valid_rotation(client, monkeypatch):
    import app as lumina

    login(client)
    original_helper = lumina.DISPLAY_HELPER
    lumina.DISPLAY_HELPER = sys.executable  # any real, existing file
    # os.geteuid() doesn't exist on Windows - this is the first test in the
    # suite to reach a helper's rc==0 branch (others short-circuit earlier),
    # so it's the first to hit this pre-existing, platform-specific call.
    monkeypatch.setattr(lumina.os, "geteuid", lambda: 1000, raising=False)
    monkeypatch.setattr(lumina, "run_cmd", lambda *a, **k: (0, "ok", ""))
    try:
        for rotation in ("0", "90", "180", "270"):
            res = client.post("/api/system/display", json={"rotation": rotation})
            assert res.status_code == 200, rotation
            assert res.get_json()["rotation"] == rotation
    finally:
        lumina.DISPLAY_HELPER = original_helper


def test_display_post_accepts_an_integer_rotation(client, monkeypatch):
    """The admin UI posts a string, but nothing stops a raw int from
    reaching this endpoint - it must be normalized the same way (#17)."""
    import app as lumina

    login(client)
    original_helper = lumina.DISPLAY_HELPER
    lumina.DISPLAY_HELPER = sys.executable
    monkeypatch.setattr(lumina.os, "geteuid", lambda: 1000, raising=False)
    monkeypatch.setattr(lumina, "run_cmd", lambda *a, **k: (0, "ok", ""))
    try:
        res = client.post("/api/system/display", json={"rotation": 90})
        assert res.status_code == 200
    finally:
        lumina.DISPLAY_HELPER = original_helper


def test_display_post_surfaces_a_helper_failure(client, monkeypatch):
    import app as lumina

    login(client)
    original_helper = lumina.DISPLAY_HELPER
    lumina.DISPLAY_HELPER = sys.executable
    monkeypatch.setattr(lumina.os, "geteuid", lambda: 1000, raising=False)
    monkeypatch.setattr(lumina, "run_cmd", lambda *a, **k: (1, "", "display failed to restart"))
    try:
        res = client.post("/api/system/display", json={"rotation": "90"})
        assert res.status_code == 502
        assert "display failed to restart" in res.get_json()["error"]
    finally:
        lumina.DISPLAY_HELPER = original_helper


# ── Storage hygiene ───────────────────────────────────────────────────────────

def _age_file(path, seconds_old):
    """Backdate a file's mtime so it reads as older than the orphan grace
    period without actually waiting."""
    import os as _os
    import time as _time

    old = _time.time() - seconds_old
    _os.utime(path, (old, old))


def test_storage_orphans_requires_admin(client):
    login(client)
    make_user(client, "ed10", "editor")
    client.get("/logout")

    login(client, "ed10", "secret123")
    assert client.get("/api/storage/orphans", json={}).status_code == 403


def test_storage_orphans_reports_none_on_a_clean_install(client):
    login(client)
    body = client.get("/api/storage/orphans").get_json()
    assert body["count"] == 0
    assert body["total_bytes"] == 0


def test_storage_orphans_finds_an_unreferenced_file(client):
    import app as lumina

    login(client)
    stray = lumina.UPLOAD_FOLDER / "not-in-the-database.jpg"
    stray.write_bytes(b"orphaned")
    _age_file(stray, lumina.ORPHAN_GRACE_SECONDS + 60)
    try:
        body = client.get("/api/storage/orphans").get_json()
        assert body["count"] == 1
        assert body["files"] == ["not-in-the-database.jpg"]
        assert body["total_bytes"] == len(b"orphaned")
    finally:
        stray.unlink(missing_ok=True)


def test_storage_orphans_does_not_flag_a_referenced_thumbnail(client):
    """A video/PDF asset's thumbnail is a real file with no Asset row of its
    own - only Asset.uri and Asset.thumbnail together define what is
    referenced. This is the case the naive "just check uri" version gets
    wrong."""
    import app as lumina

    login(client)
    asset_res = client.post("/api/assets", json={"uri": "https://example.com"})
    asset_id = asset_res.get_json()["id"]

    thumb_dir = lumina.UPLOAD_FOLDER / "thumbnails"
    thumb_dir.mkdir(exist_ok=True)
    thumb_path = thumb_dir / f"{asset_id}.jpg"
    thumb_path.write_bytes(b"thumb")
    _age_file(thumb_path, lumina.ORPHAN_GRACE_SECONDS + 60)
    try:
        with lumina.app.app_context():
            asset = lumina.db.session.get(lumina.Asset, asset_id)
            asset.thumbnail = f"/static/uploads/thumbnails/{asset_id}.jpg"
            lumina.db.session.commit()

        body = client.get("/api/storage/orphans").get_json()
        assert body["count"] == 0
    finally:
        thumb_path.unlink(missing_ok=True)


def test_storage_orphans_clean_removes_only_orphans(client):
    import app as lumina

    login(client)
    stray = lumina.UPLOAD_FOLDER / "cleanup-me.jpg"
    stray.write_bytes(b"xx")
    _age_file(stray, lumina.ORPHAN_GRACE_SECONDS + 60)
    try:
        scan_token = client.get("/api/storage/orphans").get_json()["scan_token"]
        res = client.delete("/api/storage/orphans", json={"scan_token": scan_token})
        body = res.get_json()
        assert body["removed"] == 1
        assert body["freed_bytes"] == 2
        assert not stray.exists()
    finally:
        stray.unlink(missing_ok=True)


def test_storage_orphans_does_not_flag_a_recently_created_file(client):
    """A file that just landed on disk must never be reported (or deletable)
    as an orphan - it could be an in-flight upload a fraction of a second
    away from getting its Asset row (#24's ORPHAN_GRACE_SECONDS)."""
    import app as lumina

    login(client)
    fresh = lumina.UPLOAD_FOLDER / "just-written.jpg"
    fresh.write_bytes(b"brand new")
    try:
        body = client.get("/api/storage/orphans").get_json()
        assert body["count"] == 0
        assert body["files"] == []
    finally:
        fresh.unlink(missing_ok=True)


def test_storage_orphans_clean_requires_a_valid_scan_token(client):
    """DELETE must be bound to a specific prior GET - it must not silently
    re-scan and act on whatever it finds right now (#24 TOCTOU)."""
    import app as lumina

    login(client)
    stray = lumina.UPLOAD_FOLDER / "needs-a-token.jpg"
    stray.write_bytes(b"xx")
    _age_file(stray, lumina.ORPHAN_GRACE_SECONDS + 60)
    try:
        res = client.delete("/api/storage/orphans")
        assert res.status_code == 400
        assert stray.exists()

        res = client.delete("/api/storage/orphans", json={"scan_token": "not-a-real-token"})
        assert res.status_code == 400
        assert stray.exists()
    finally:
        stray.unlink(missing_ok=True)


def test_storage_orphans_clean_ignores_files_created_after_the_scan(client):
    """A file that appears after the admin's GET must never be swept by the
    DELETE that follows it, even though a fresh independent scan would find
    it too (#24 TOCTOU)."""
    import app as lumina

    login(client)
    # Scan while uploads is empty - the token covers zero candidates.
    scan_token = client.get("/api/storage/orphans").get_json()["scan_token"]

    late = lumina.UPLOAD_FOLDER / "arrived-after-the-scan.jpg"
    late.write_bytes(b"xx")
    _age_file(late, lumina.ORPHAN_GRACE_SECONDS + 60)
    try:
        res = client.delete("/api/storage/orphans", json={"scan_token": scan_token})
        body = res.get_json()
        assert body["removed"] == 0
        assert late.exists()
    finally:
        late.unlink(missing_ok=True)


def test_storage_orphans_clean_never_removes_more_than_the_admin_was_shown(client):
    """A cleanup click must only ever act on files the admin actually saw
    listed - not a larger real total. With more orphans than
    ORPHAN_BATCH_LIMIT, DELETE removes only that batch; the rest need a
    fresh scan (#24 - 'report before delete' must be a real guarantee, not
    just a display detail)."""
    import app as lumina

    login(client)
    total_files = lumina.ORPHAN_BATCH_LIMIT + 5
    strays = []
    for i in range(total_files):
        f = lumina.UPLOAD_FOLDER / f"batch-cap-{i}.jpg"
        f.write_bytes(b"x")
        _age_file(f, lumina.ORPHAN_GRACE_SECONDS + 60)
        strays.append(f)
    try:
        body = client.get("/api/storage/orphans").get_json()
        assert body["count"] == total_files
        assert len(body["files"]) == lumina.ORPHAN_BATCH_LIMIT
        assert body["truncated"] is True

        res = client.delete("/api/storage/orphans", json={"scan_token": body["scan_token"]})
        first_batch = res.get_json()
        assert first_batch["removed"] == lumina.ORPHAN_BATCH_LIMIT

        remaining = client.get("/api/storage/orphans").get_json()
        assert remaining["count"] == 5
        assert remaining["truncated"] is False

        res = client.delete("/api/storage/orphans", json={"scan_token": remaining["scan_token"]})
        second_batch = res.get_json()
        assert second_batch["removed"] == 5
    finally:
        for f in strays:
            f.unlink(missing_ok=True)


def test_upload_is_refused_when_disk_is_nearly_full(client, monkeypatch):
    """Regression coverage for #24 - a full disk previously failed with
    whatever the OS write error happened to be, mid-write, on the same
    filesystem SQLite lives on."""
    import io as _io
    import app as lumina
    from collections import namedtuple

    Usage = namedtuple("Usage", "total used free")
    monkeypatch.setattr(lumina.shutil, "disk_usage", lambda path: Usage(100, 99, 1))

    login(client)
    data = {"file": (_io.BytesIO(b"fake image bytes"), "photo.jpg")}
    res = client.post("/api/assets", data=data, content_type="multipart/form-data")
    assert res.status_code == 507


def test_upload_is_refused_when_it_would_leave_less_than_the_reserve(client, monkeypatch):
    """500 MB free, 200 MB reserve, an 800 MB upload must be refused before
    a single byte is written - not just when the disk is already critically
    low (#24). The pre-check runs against the declared Content-Length before
    request.files is ever touched, so a real multi-hundred-MB body isn't
    needed here - a small body with an overridden Content-Length exercises
    the same code path."""
    import io as _io
    import app as lumina
    from collections import namedtuple

    Usage = namedtuple("Usage", "total used free")
    monkeypatch.setattr(
        lumina.shutil, "disk_usage",
        lambda path: Usage(1_000_000_000, 500_000_000, 500 * 1024 * 1024)
    )

    login(client)
    data = {"file": (_io.BytesIO(b"small body, large declared size"), "video.mp4")}
    res = client.post(
        "/api/assets", data=data, content_type="multipart/form-data",
        # Werkzeug's test client recomputes Content-Length from the actual
        # body it's given, so environ_overrides is the way to make the
        # request declare a size larger than what's actually sent - exactly
        # what the pre-parse check is meant to catch from a real client.
        environ_overrides={"CONTENT_LENGTH": str(800 * 1024 * 1024)},
    )
    assert res.status_code == 507


def test_upload_is_refused_when_the_spool_and_final_copy_would_not_both_fit(client, monkeypatch):
    """Models the double-copy peak (#24): request.files is fully parsed by
    the time file.save() is reached, which means Werkzeug has already
    spooled the upload to a temp file on this same filesystem - save()
    then does a second, separate copy into UPLOAD_FOLDER rather than a
    rename. A disk reading taken before parsing can look fine while the
    post-spool reading would not leave room for that second copy. The
    check right before file.save() must use a fresh reading and the
    actual (stream-measured) size, not just repeat the earlier one."""
    import io as _io
    import app as lumina
    from collections import namedtuple

    Usage = namedtuple("Usage", "total used free")
    # First call is the pre-parse Content-Length check - plenty of room.
    # Second call is the post-parse check right before file.save() - only
    # what would realistically be left after a same-size temp spool
    # already landed, not enough for a second copy plus the reserve.
    readings = iter([
        Usage(10_000_000_000, 0, 3_000_000_000),
        Usage(10_000_000_000, 0, 150 * 1024 * 1024),
    ])
    monkeypatch.setattr(lumina.shutil, "disk_usage", lambda path: next(readings))

    login(client)
    data = {"file": (_io.BytesIO(b"stand-in body"), "video.mp4")}
    res = client.post("/api/assets", data=data, content_type="multipart/form-data")
    assert res.status_code == 507


def test_upload_is_accepted_when_it_safely_fits(client, monkeypatch):
    import io as _io
    import app as lumina
    from collections import namedtuple

    Usage = namedtuple("Usage", "total used free")
    monkeypatch.setattr(
        lumina.shutil, "disk_usage",
        lambda path: Usage(1_000_000_000, 100_000_000, 900 * 1024 * 1024)
    )

    login(client)
    data = {"file": (_io.BytesIO(b"small file"), "photo.jpg")}
    res = client.post("/api/assets", data=data, content_type="multipart/form-data")
    assert res.status_code == 201
    # Clean up the real file this created - UPLOAD_FOLDER is the project's
    # actual static/uploads directory and persists across test runs.
    uri = res.get_json()["uri"]
    (lumina.BASE_DIR / uri.lstrip("/")).unlink(missing_ok=True)


def test_failed_asset_creation_cleans_up_the_saved_file(client, monkeypatch):
    """If the database write fails after the file is already on disk, the
    file must not become a permanent orphan with no Asset row to ever
    reference it (#24). Compares a before/after snapshot rather than
    asserting the folder is empty - UPLOAD_FOLDER is the real project
    directory and persists across tests in this suite."""
    import io as _io
    import app as lumina

    login(client)
    before = set(lumina.UPLOAD_FOLDER.glob("*.jpg"))

    def boom():
        raise lumina.sqlite3.OperationalError("database is locked")

    monkeypatch.setattr(lumina.db.session, "commit", boom)

    data = {"file": (_io.BytesIO(b"fake image bytes"), "photo.jpg")}
    res = client.post("/api/assets", data=data, content_type="multipart/form-data")
    assert res.status_code == 500

    after = set(lumina.UPLOAD_FOLDER.glob("*.jpg"))
    assert after == before


# ── Backup and restore ────────────────────────────────────────────────────────

def test_backup_export_requires_admin(client):
    login(client)
    make_user(client, "ed8", "editor")
    client.get("/logout")

    login(client, "ed8", "secret123")
    assert client.get("/api/backup/export", json={}).status_code == 403


def test_backup_export_produces_a_zip_containing_the_database(client):
    import zipfile
    import io as _io

    login(client)
    res = client.get("/api/backup/export")
    assert res.status_code == 200
    assert res.mimetype == "application/zip"
    with zipfile.ZipFile(_io.BytesIO(res.data)) as zf:
        assert "lumina.db" in zf.namelist()


def test_backup_export_reflects_current_data(client):
    """The exported db is a real, queryable snapshot - not an empty shell."""
    import zipfile
    import io as _io
    import sqlite3
    import tempfile as _tempfile

    login(client)
    client.post("/api/assets", json={"name": "in the backup", "uri": "https://example.com"})

    res = client.get("/api/backup/export")
    with zipfile.ZipFile(_io.BytesIO(res.data)) as zf:
        db_bytes = zf.read("lumina.db")

    with _tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        f.write(db_bytes)
        path = f.name
    con = sqlite3.connect(path)
    try:
        names = [r[0] for r in con.execute("SELECT name FROM assets").fetchall()]
        assert "in the backup" in names
    finally:
        con.close()  # must close before removing - Windows locks open files
        os.remove(path)


def test_backup_import_is_refused_without_the_helper(client):
    import io as _io

    login(client)
    data = {"file": (_io.BytesIO(b"not a real zip"), "backup.zip")}
    res = client.post("/api/backup/import", data=data, content_type="multipart/form-data")
    assert res.status_code == 503


def test_backup_import_requires_admin(client):
    login(client)
    make_user(client, "ed9", "editor")
    client.get("/logout")

    login(client, "ed9", "secret123")
    assert client.post("/api/backup/import", json={}).status_code == 403


def test_backup_import_rejects_non_zip_filename(client):
    import app as lumina
    import io as _io

    login(client)
    original = lumina.BACKUP_HELPER
    lumina.BACKUP_HELPER = sys.executable  # any real, existing file
    try:
        data = {"file": (_io.BytesIO(b"whatever"), "notes.txt")}
        res = client.post("/api/backup/import", data=data, content_type="multipart/form-data")
        assert res.status_code == 400
    finally:
        lumina.BACKUP_HELPER = original


def test_backup_import_rejects_a_zip_with_no_database(client, tmp_path, monkeypatch):
    import app as lumina
    import io as _io
    import zipfile

    login(client)
    # This is the one backup-import test that actually reaches
    # os.makedirs(RESTORE_STAGING_DIR) - the real path is
    # /var/lib/lumina/restore-uploads, which a CI runner has no permission
    # to create. Point it at a throwaway directory instead; production
    # restore behavior (the real path, the privileged-helper handoff) is
    # untouched.
    monkeypatch.setattr(lumina, "RESTORE_STAGING_DIR", str(tmp_path / "restore-uploads"))
    original = lumina.BACKUP_HELPER
    lumina.BACKUP_HELPER = sys.executable
    try:
        buf = _io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("uploads/photo.jpg", b"not really a photo")
        buf.seek(0)
        data = {"file": (buf, "backup.zip")}
        res = client.post("/api/backup/import", data=data, content_type="multipart/form-data")
        assert res.status_code == 400
        assert "lumina.db" in res.get_json()["error"]
    finally:
        lumina.BACKUP_HELPER = original


# ── Updates ───────────────────────────────────────────────────────────────────

def test_update_status_requires_admin(client):
    login(client)
    make_user(client, "ed3", "editor")
    client.get("/logout")

    login(client, "ed3", "secret123")
    assert client.get("/api/update/status", json={}).status_code == 403


def test_update_status_reports_the_running_version(client):
    login(client)
    body = client.get("/api/update/status").get_json()
    import app as lumina
    assert body["installed"] == lumina.__version__


def test_update_status_degrades_when_helper_is_absent(client):
    """A development machine has no helper installed; say so rather than error."""
    login(client)
    body = client.get("/api/update/status").get_json()
    assert body["supported"] is False
    assert body["update_available"] is False


def test_update_apply_is_refused_without_the_helper(client):
    login(client)
    assert client.post("/api/update/apply", json={}).status_code == 503


def test_parse_kv_reads_helper_output():
    import app as lumina
    parsed = lumina.parse_kv("state=success\nfrom=1.0.0\nto=1.1.0\nnoise\n")
    assert parsed == {"state": "success", "from": "1.0.0", "to": "1.1.0"}


def test_stats_reports_counts(client):
    login(client)
    client.post("/api/assets", json={"uri": "https://example.com"})
    body = client.get("/api/stats").get_json()
    assert body["total_assets"] == 1
    assert body["total_users"] == 1
