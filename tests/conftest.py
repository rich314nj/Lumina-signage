"""Shared test fixtures.

The application configures itself at import time, so the scratch database and
secret key must be in the environment before `app` is imported.
"""
import os
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

_db_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_db_file.close()
os.environ["DATABASE_URL"] = f"sqlite:///{_db_file.name}"
os.environ.setdefault("SECRET_KEY", "test-secret-key")

import app as lumina  # noqa: E402


@pytest.fixture()
def client():
    """A test client backed by a freshly created database with one admin."""
    with lumina.app.app_context():
        lumina.db.drop_all()
        lumina.db.create_all()
        admin = lumina.User(
            username="admin", email="admin@lumina.local", role="admin"
        )
        admin.set_password("admin123")
        lumina.db.session.add(admin)
        lumina.db.session.commit()

    lumina.app.config["TESTING"] = True
    with lumina.app.test_client() as test_client:
        yield test_client


def login(client, username="admin", password="admin123"):
    return client.post(
        "/login", json={"username": username, "password": password}
    )


def make_user(client, username, role, password="secret123"):
    """Create a user through the API and return its id."""
    res = client.post(
        "/api/users",
        json={
            "username": username,
            "email": f"{username}@lumina.local",
            "password": password,
            "role": role,
        },
    )
    assert res.status_code == 201, res.get_json()
    return res.get_json()["id"]
