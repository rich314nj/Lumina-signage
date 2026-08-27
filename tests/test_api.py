"""API behaviour: authentication, role enforcement, and error paths."""
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


# ── Endpoints the player relies on stay unauthenticated ───────────────────────

def test_current_playlist_is_reachable_without_login(client):
    # The kiosk browser has no session; this must not require one.
    assert client.get("/api/current-playlist").status_code == 200


def test_device_info_is_reachable_without_login(client):
    res = client.get("/api/device-info")
    assert res.status_code == 200
    assert "hostname" in res.get_json()


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
