#!/usr/bin/env python3
"""
Lumina Signage - Digital Signage Platform for Ubuntu
Similar to Anthias/Screenly
"""

import os
import re
import json
import uuid
import secrets
import subprocess
import mimetypes
from datetime import datetime
from functools import wraps
from pathlib import Path
from urllib.parse import urlparse, parse_qs

from flask import (
    Flask, render_template, request, jsonify, redirect,
    url_for, session
)
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash

# ── App Configuration ──────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent
UPLOAD_FOLDER = BASE_DIR / "static" / "uploads"
UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)

ALLOWED_IMAGE_EXT = {"jpg", "jpeg", "png", "pnm", "gif", "bmp", "webp"}
ALLOWED_VIDEO_EXT = {"avi", "mkv", "mov", "mpg", "mpeg", "mp4", "ts", "flv"}
ALLOWED_DOC_EXT   = {"pdf"}
ALLOWED_EXTENSIONS = ALLOWED_IMAGE_EXT | ALLOWED_VIDEO_EXT | ALLOWED_DOC_EXT

MAX_CONTENT_LENGTH = 2 * 1024 * 1024 * 1024  # 2 GB

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", secrets.token_hex(32))
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{BASE_DIR / 'lumina.db'}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["UPLOAD_FOLDER"] = str(UPLOAD_FOLDER)
app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH

db = SQLAlchemy(app)

# ── Models ─────────────────────────────────────────────────────────────────────

class User(db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), default="viewer")  # admin, editor, viewer
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def to_dict(self):
        return {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "role": self.role,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat(),
            "last_login": self.last_login.isoformat() if self.last_login else None,
        }


class Asset(db.Model):
    __tablename__ = "assets"
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = db.Column(db.String(255), nullable=False)
    asset_type = db.Column(db.String(20), nullable=False)  # image, video, url, youtube, vimeo
    uri = db.Column(db.String(1024), nullable=False)
    duration = db.Column(db.Integer, default=10)  # seconds
    mimetype = db.Column(db.String(100))
    filesize = db.Column(db.BigInteger, default=0)
    thumbnail = db.Column(db.String(512))
    is_active = db.Column(db.Boolean, default=True)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "asset_type": self.asset_type,
            "uri": self.uri,
            "duration": self.duration,
            "mimetype": self.mimetype,
            "filesize": self.filesize,
            "thumbnail": self.thumbnail,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


class Playlist(db.Model):
    __tablename__ = "playlists"
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True)
    loop = db.Column(db.Boolean, default=True)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)
    items = db.relationship("PlaylistItem", backref="playlist", cascade="all, delete-orphan",
                            order_by="PlaylistItem.position")

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "is_active": self.is_active,
            "loop": self.loop,
            "created_at": self.created_at.isoformat(),
            "items": [i.to_dict() for i in self.items],
        }


class PlaylistItem(db.Model):
    __tablename__ = "playlist_items"
    id = db.Column(db.Integer, primary_key=True)
    playlist_id = db.Column(db.String(36), db.ForeignKey("playlists.id"), nullable=False)
    asset_id = db.Column(db.String(36), db.ForeignKey("assets.id"), nullable=False)
    position = db.Column(db.Integer, default=0)
    duration_override = db.Column(db.Integer)  # override asset duration
    asset = db.relationship("Asset")

    def to_dict(self):
        return {
            "id": self.id,
            "asset": self.asset.to_dict() if self.asset else None,
            "position": self.position,
            "duration_override": self.duration_override,
        }


class Schedule(db.Model):
    __tablename__ = "schedules"
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    playlist_id = db.Column(db.String(36), db.ForeignKey("playlists.id"), nullable=False)
    name = db.Column(db.String(255))
    start_time = db.Column(db.String(5))   # HH:MM
    end_time = db.Column(db.String(5))     # HH:MM
    days = db.Column(db.String(50), default="mon,tue,wed,thu,fri,sat,sun")
    is_active = db.Column(db.Boolean, default=True)
    playlist = db.relationship("Playlist")

    def to_dict(self):
        return {
            "id": self.id,
            "playlist_id": self.playlist_id,
            "playlist_name": self.playlist.name if self.playlist else None,
            "name": self.name,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "days": self.days,
            "is_active": self.is_active,
        }


# ── Auth Helpers ───────────────────────────────────────────────────────────────

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            if request.is_json:
                return jsonify({"error": "Authentication required"}), 401
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated


def role_required(*roles):
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if "user_id" not in session:
                return jsonify({"error": "Authentication required"}), 401
            user = db.session.get(User, session["user_id"])
            if not user or user.role not in roles:
                return jsonify({"error": "Insufficient permissions"}), 403
            return f(*args, **kwargs)
        return decorated
    return decorator


def current_user():
    if "user_id" in session:
        return db.session.get(User, session["user_id"])
    return None


# ── Utility Functions ──────────────────────────────────────────────────────────

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def get_asset_type(filename_or_url):
    if re.match(r"https?://(www\.)?(youtube\.com|youtu\.be)/", filename_or_url):
        return "youtube"
    if re.match(r"https?://(www\.)?vimeo\.com/", filename_or_url):
        return "vimeo"
    if filename_or_url.startswith(("http://", "https://")):
        return "url"
    ext = filename_or_url.rsplit(".", 1)[-1].lower() if "." in filename_or_url else ""
    if ext in ALLOWED_IMAGE_EXT:
        return "image"
    if ext in ALLOWED_VIDEO_EXT:
        return "video"
    if ext in ALLOWED_DOC_EXT:
        return "pdf"
    return "url"


def get_video_duration(filepath):
    """Use ffprobe to get video duration in seconds."""
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "quiet", "-print_format", "json",
             "-show_format", str(filepath)],
            capture_output=True, text=True, timeout=30
        )
        data = json.loads(result.stdout)
        return int(float(data["format"].get("duration", 10)))
    except Exception:
        return 10


def generate_thumbnail(filepath, asset_id):
    """Generate thumbnail for video using ffmpeg."""
    thumb_dir = UPLOAD_FOLDER / "thumbnails"
    thumb_dir.mkdir(exist_ok=True)
    thumb_path = thumb_dir / f"{asset_id}.jpg"
    try:
        subprocess.run(
            ["ffmpeg", "-i", str(filepath), "-ss", "00:00:01",
             "-vframes", "1", "-q:v", "2", str(thumb_path), "-y"],
            capture_output=True, timeout=30
        )
        if thumb_path.exists():
            return f"/static/uploads/thumbnails/{asset_id}.jpg"
    except Exception:
        pass
    return None

def generate_pdf_thumbnail(filepath, asset_id):
    """Generate thumbnail for PDF first page using ImageMagick.
    Tries 'magick' (ImageMagick 7, Ubuntu 22.04+) then 'convert' (ImageMagick 6).
    Falls back gracefully if neither is installed.
    Note: If ImageMagick is installed but PDF conversion fails, check
    /etc/ImageMagick-*/policy.xml and ensure the PDF policy is not set to 'none'.
    Install with: sudo apt install imagemagick
    """
    thumb_dir = UPLOAD_FOLDER / "thumbnails"
    thumb_dir.mkdir(exist_ok=True)
    thumb_path = thumb_dir / f"{asset_id}.jpg"
    im_args = [
        "-density", "150", f"{filepath}[0]",
        "-resize", "400x300", "-background", "white",
        "-flatten", str(thumb_path)
    ]
    # Try ImageMagick 7 binary first, fall back to ImageMagick 6
    for binary in ("magick", "convert"):
        try:
            cmd = [binary] + (["convert"] if binary == "magick" else []) + im_args
            result = subprocess.run(cmd, capture_output=True, timeout=30)
            if result.returncode == 0 and thumb_path.exists():
                return f"/static/uploads/thumbnails/{asset_id}.jpg"
        except FileNotFoundError:
            continue
        except Exception:
            break
    return None


def extract_youtube_id(url):
    if not isinstance(url, str) or not url:
        return None

    try:
        parsed = urlparse(url)
        host = parsed.hostname.lower() if parsed.hostname else ""
        path = parsed.path or ""

        # youtu.be/<id>
        if host in ("youtu.be", "www.youtu.be"):
            candidate = path.strip("/").split("/")[0] if path.strip("/") else ""
            if re.fullmatch(r"[a-zA-Z0-9_-]{11}", candidate):
                return candidate

        # youtube.com/watch?...&v=<id>
        if host in ("youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com"):
            v = parse_qs(parsed.query).get("v", [None])[0]
            if v and re.fullmatch(r"[a-zA-Z0-9_-]{11}", v):
                return v

            # /embed/<id>, /shorts/<id>, /live/<id>, /v/<id>
            parts = [p for p in path.split("/") if p]
            if len(parts) >= 2 and parts[0] in ("embed", "shorts", "live", "v"):
                candidate = parts[1]
                if re.fullmatch(r"[a-zA-Z0-9_-]{11}", candidate):
                    return candidate
    except Exception:
        pass

    # Fallback for malformed URLs or plain text.
    m = re.search(
        r"(?:youtube\.com/(?:watch\?.*?[?&]v=|embed/|shorts/|live/|v/)|youtu\.be/)([a-zA-Z0-9_-]{11})",
        str(url),
    )
    if m:
        return m.group(1)
    return None


def extract_vimeo_id(url):
    m = re.search(r"vimeo\.com/(\d+)", url)
    return m.group(1) if m else None


# ── Page Routes ────────────────────────────────────────────────────────────────

DAY_ORDER = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
DAY_TO_INDEX = {d: i for i, d in enumerate(DAY_ORDER)}


def parse_hhmm_to_min(hhmm):
    if not isinstance(hhmm, str) or not re.fullmatch(r"\d{2}:\d{2}", hhmm):
        return None
    h, m = hhmm.split(":")
    h_i, m_i = int(h), int(m)
    if not (0 <= h_i <= 23 and 0 <= m_i <= 59):
        return None
    return h_i * 60 + m_i


def normalize_days(days_csv):
    if not isinstance(days_csv, str):
        return None
    parts = [p.strip().lower() for p in days_csv.split(",") if p.strip()]
    if not parts:
        return None
    uniq = []
    seen = set()
    for p in parts:
        if p not in DAY_TO_INDEX:
            return None
        if p not in seen:
            uniq.append(p)
            seen.add(p)
    return ",".join(uniq)


def schedule_to_day_intervals(start_min, end_min, days_csv):
    """Return normalized day intervals as (day_idx, start_min, end_min_exclusive)."""
    days = normalize_days(days_csv)
    if days is None:
        return None
    out = []
    for day in days.split(","):
        day_idx = DAY_TO_INDEX[day]
        if start_min == end_min:
            # start == end means full-day coverage for that day.
            out.append((day_idx, 0, 1440))
        elif start_min < end_min:
            out.append((day_idx, start_min, end_min))
        else:
            # Overnight split (e.g. 23:00-02:00) across day boundary.
            out.append((day_idx, start_min, 1440))
            out.append(((day_idx + 1) % 7, 0, end_min))
    return out


def intervals_overlap(a_start, a_end, b_start, b_end):
    # Half-open intervals allow touching boundaries (e.g. 10:00-12:00 and 12:00-14:00).
    return max(a_start, b_start) < min(a_end, b_end)


def find_overlapping_schedule(candidate_intervals, schedules):
    for s in schedules:
        s_start = parse_hhmm_to_min(s.start_time)
        s_end = parse_hhmm_to_min(s.end_time)
        if s_start is None or s_end is None:
            continue
        existing_intervals = schedule_to_day_intervals(s_start, s_end, s.days)
        if existing_intervals is None:
            continue
        for c_day, c_start, c_end in candidate_intervals:
            for e_day, e_start, e_end in existing_intervals:
                if c_day == e_day and intervals_overlap(c_start, c_end, e_start, e_end):
                    return s
    return None


def schedule_match_interval_for_now(schedule, now_day_idx, now_min):
    s_start = parse_hhmm_to_min(schedule.start_time)
    s_end = parse_hhmm_to_min(schedule.end_time)
    if s_start is None or s_end is None:
        return None
    intervals = schedule_to_day_intervals(s_start, s_end, schedule.days)
    if intervals is None:
        return None
    for day_idx, i_start, i_end in intervals:
        if day_idx == now_day_idx and i_start <= now_min < i_end:
            return i_start, i_end
    return None


@app.route("/")
def index():
    if "user_id" not in session:
        return redirect(url_for("login"))
    return render_template("index.html", user=current_user())


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        data = request.get_json() or request.form
        username = data.get("username", "").strip()
        password = data.get("password", "")
        user = User.query.filter_by(username=username, is_active=True).first()
        if user and user.check_password(password):
            session["user_id"] = user.id
            session["username"] = user.username
            session["role"] = user.role
            user.last_login = datetime.utcnow()
            db.session.commit()
            if request.is_json:
                return jsonify({"success": True, "role": user.role})
            return redirect(url_for("index"))
        if request.is_json:
            return jsonify({"error": "Invalid credentials"}), 401
        return render_template("login.html", error="Invalid credentials")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/player")
def player():
    """Full-screen player view."""
    playlist_id = request.args.get("playlist")
    return render_template("player.html", playlist_id=playlist_id)


# ── API: Auth ──────────────────────────────────────────────────────────────────

@app.route("/api/me")
@login_required
def api_me():
    user = current_user()
    return jsonify(user.to_dict())


# ── API: Users ─────────────────────────────────────────────────────────────────

@app.route("/api/users", methods=["GET"])
@login_required
@role_required("admin")
def api_users():
    users = User.query.order_by(User.created_at).all()
    return jsonify([u.to_dict() for u in users])


@app.route("/api/users", methods=["POST"])
@login_required
@role_required("admin")
def api_create_user():
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data"}), 400
    username = data.get("username", "").strip()
    email = data.get("email", "").strip()
    password = data.get("password", "")
    role = data.get("role", "viewer")
    if not username or not email or not password:
        return jsonify({"error": "username, email, and password are required"}), 400
    if role not in ("admin", "editor", "viewer"):
        return jsonify({"error": "Invalid role"}), 400
    if User.query.filter_by(username=username).first():
        return jsonify({"error": "Username already exists"}), 409
    if User.query.filter_by(email=email).first():
        return jsonify({"error": "Email already exists"}), 409
    user = User(username=username, email=email, role=role)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    return jsonify(user.to_dict()), 201


@app.route("/api/users/<int:uid>", methods=["GET"])
@login_required
@role_required("admin")
def api_get_user(uid):
    user = db.session.get(User, uid)
    if not user:
        return jsonify({"error": "User not found"}), 404
    return jsonify(user.to_dict())


@app.route("/api/users/<int:uid>", methods=["PUT"])
@login_required
@role_required("admin")
def api_update_user(uid):
    user = db.session.get(User, uid)
    if not user:
        return jsonify({"error": "User not found"}), 404
    data = request.get_json()
    if "email" in data:
        user.email = data["email"]
    if "role" in data and data["role"] in ("admin", "editor", "viewer"):
        user.role = data["role"]
    if "is_active" in data:
        user.is_active = bool(data["is_active"])
    if "password" in data and data["password"]:
        user.set_password(data["password"])
    db.session.commit()
    return jsonify(user.to_dict())


@app.route("/api/users/<int:uid>", methods=["DELETE"])
@login_required
@role_required("admin")
def api_delete_user(uid):
    if uid == session.get("user_id"):
        return jsonify({"error": "Cannot delete yourself"}), 400
    user = db.session.get(User, uid)
    if not user:
        return jsonify({"error": "User not found"}), 404
    db.session.delete(user)
    db.session.commit()
    return jsonify({"success": True})


# ── API: Assets ────────────────────────────────────────────────────────────────

@app.route("/api/assets", methods=["GET"])
@login_required
def api_assets():
    assets = Asset.query.order_by(Asset.created_at.desc()).all()
    return jsonify([a.to_dict() for a in assets])


@app.route("/api/assets", methods=["POST"])
@login_required
@role_required("admin", "editor")
def api_create_asset():
    # URL asset
    if request.is_json:
        data = request.get_json()
        uri = data.get("uri", "").strip()
        if not uri:
            return jsonify({"error": "URI required"}), 400
        atype = get_asset_type(uri)
        name = data.get("name", uri[:80])
        duration = int(data.get("duration", 30 if atype in ("url", "youtube", "vimeo") else 10))
        thumbnail = None
        if atype == "youtube":
            vid = extract_youtube_id(uri)
            if vid:
                thumbnail = f"https://img.youtube.com/vi/{vid}/hqdefault.jpg"
        elif atype == "vimeo":
            vid = extract_vimeo_id(uri)
            if vid:
                thumbnail = f"https://vumbnail.com/{vid}.jpg"
        asset = Asset(
            name=name, asset_type=atype, uri=uri, duration=duration,
            thumbnail=thumbnail, created_by=session["user_id"]
        )
        db.session.add(asset)
        db.session.commit()
        return jsonify(asset.to_dict()), 201

    # File upload
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400
    file = request.files["file"]
    if not file.filename or not allowed_file(file.filename):
        return jsonify({"error": "Invalid file type"}), 400

    filename = secure_filename(file.filename)
    asset_id = str(uuid.uuid4())
    ext = filename.rsplit(".", 1)[1].lower()
    stored_name = f"{asset_id}.{ext}"
    save_path = UPLOAD_FOLDER / stored_name
    file.save(str(save_path))

    atype = get_asset_type(filename)
    mimetype = mimetypes.guess_type(filename)[0] or "application/octet-stream"
    filesize = save_path.stat().st_size
    duration = 10
    thumbnail = None

    if atype == "video":
        duration = get_video_duration(save_path)
        thumbnail = generate_thumbnail(save_path, asset_id)
    elif atype == "image":
        thumbnail = f"/static/uploads/{stored_name}"
    elif atype == "pdf":
        duration = 30  # default total duration; player spreads it evenly across pages
        thumbnail = generate_pdf_thumbnail(save_path, asset_id)

    name = request.form.get("name", filename)
    asset = Asset(
        id=asset_id, name=name, asset_type=atype,
        uri=f"/static/uploads/{stored_name}",
        duration=duration, mimetype=mimetype, filesize=filesize,
        thumbnail=thumbnail, created_by=session["user_id"]
    )
    db.session.add(asset)
    db.session.commit()
    return jsonify(asset.to_dict()), 201


@app.route("/api/assets/<asset_id>", methods=["GET"])
@login_required
def api_get_asset(asset_id):
    asset = db.session.get(Asset, asset_id)
    if not asset:
        return jsonify({"error": "Not found"}), 404
    return jsonify(asset.to_dict())


@app.route("/api/assets/<asset_id>", methods=["PUT"])
@login_required
@role_required("admin", "editor")
def api_update_asset(asset_id):
    asset = db.session.get(Asset, asset_id)
    if not asset:
        return jsonify({"error": "Not found"}), 404
    data = request.get_json()
    if "name" in data:
        asset.name = data["name"]
    if "duration" in data:
        asset.duration = int(data["duration"])
    if "is_active" in data:
        asset.is_active = bool(data["is_active"])
    asset.updated_at = datetime.utcnow()
    db.session.commit()
    return jsonify(asset.to_dict())


@app.route("/api/assets/<asset_id>", methods=["DELETE"])
@login_required
@role_required("admin", "editor")
def api_delete_asset(asset_id):
    asset = db.session.get(Asset, asset_id)
    if not asset:
        return jsonify({"error": "Not found"}), 404
    # Remove physical file if local
    if asset.uri.startswith("/static/uploads/"):
        filepath = BASE_DIR / asset.uri.lstrip("/")
        if filepath.exists():
            filepath.unlink(missing_ok=True)
        # Remove thumbnail
        if asset.thumbnail and asset.thumbnail.startswith("/static/"):
            tpath = BASE_DIR / asset.thumbnail.lstrip("/")
            tpath.unlink(missing_ok=True)
    db.session.delete(asset)
    db.session.commit()
    return jsonify({"success": True})


# ── API: Playlists ─────────────────────────────────────────────────────────────

@app.route("/api/playlists", methods=["GET"])
@login_required
def api_playlists():
    playlists = Playlist.query.order_by(Playlist.created_at.desc()).all()
    return jsonify([p.to_dict() for p in playlists])


@app.route("/api/playlists", methods=["POST"])
@login_required
@role_required("admin", "editor")
def api_create_playlist():
    data = request.get_json()
    name = data.get("name", "New Playlist").strip()
    playlist = Playlist(
        name=name,
        description=data.get("description", ""),
        loop=data.get("loop", True),
        created_by=session["user_id"]
    )
    db.session.add(playlist)
    db.session.commit()
    return jsonify(playlist.to_dict()), 201


@app.route("/api/playlists/<pl_id>", methods=["GET"])
@login_required
def api_get_playlist(pl_id):
    pl = db.session.get(Playlist, pl_id)
    if not pl:
        return jsonify({"error": "Not found"}), 404
    return jsonify(pl.to_dict())


@app.route("/api/playlists/<pl_id>", methods=["PUT"])
@login_required
@role_required("admin", "editor")
def api_update_playlist(pl_id):
    pl = db.session.get(Playlist, pl_id)
    if not pl:
        return jsonify({"error": "Not found"}), 404
    data = request.get_json()
    if "name" in data:
        pl.name = data["name"]
    if "description" in data:
        pl.description = data["description"]
    if "is_active" in data:
        pl.is_active = bool(data["is_active"])
    if "loop" in data:
        pl.loop = bool(data["loop"])
    if "items" in data:
        # Replace all items
        PlaylistItem.query.filter_by(playlist_id=pl_id).delete()
        for i, item in enumerate(data["items"]):
            pi = PlaylistItem(
                playlist_id=pl_id,
                asset_id=item["asset_id"],
                position=i,
                duration_override=item.get("duration_override")
            )
            db.session.add(pi)
    # FIX #5: explicitly set updated_at — SQLite onupdate hook is unreliable
    pl.updated_at = datetime.utcnow()
    db.session.commit()
    return jsonify(pl.to_dict())


@app.route("/api/playlists/<pl_id>", methods=["DELETE"])
@login_required
@role_required("admin", "editor")
def api_delete_playlist(pl_id):
    pl = db.session.get(Playlist, pl_id)
    if not pl:
        return jsonify({"error": "Not found"}), 404
    db.session.delete(pl)
    db.session.commit()
    return jsonify({"success": True})


# ── API: Schedules ─────────────────────────────────────────────────────────────

@app.route("/api/schedules", methods=["GET"])
@login_required
def api_schedules():
    schedules = Schedule.query.order_by(Schedule.start_time).all()
    return jsonify([s.to_dict() for s in schedules])


@app.route("/api/schedules", methods=["POST"])
@login_required
@role_required("admin", "editor")
def api_create_schedule():
    data = request.get_json()
    pl_id = data.get("playlist_id")
    if not pl_id or not db.session.get(Playlist, pl_id):
        return jsonify({"error": "Valid playlist_id required"}), 400
    start_time = data.get("start_time", "00:00")
    end_time = data.get("end_time", "23:59")
    days = data.get("days", "mon,tue,wed,thu,fri,sat,sun")
    start_min = parse_hhmm_to_min(start_time)
    end_min = parse_hhmm_to_min(end_time)
    if start_min is None or end_min is None:
        return jsonify({"error": "start_time and end_time must be HH:MM (24-hour)"}), 400
    days_norm = normalize_days(days)
    if days_norm is None:
        return jsonify({"error": "days must be comma-separated mon,tue,wed,thu,fri,sat,sun"}), 400

    # Overlap policy: active schedules must not overlap.
    candidate_intervals = schedule_to_day_intervals(start_min, end_min, days_norm)
    active_schedules = Schedule.query.filter_by(is_active=True).all()
    overlapping = find_overlapping_schedule(candidate_intervals, active_schedules)
    if overlapping:
        return jsonify({
            "error": (
                f"Schedule overlaps with existing active schedule '{overlapping.name or overlapping.id}'"
            )
        }), 409

    s = Schedule(
        playlist_id=pl_id,
        name=data.get("name", "Schedule"),
        start_time=start_time,
        end_time=end_time,
        days=days_norm,
    )
    db.session.add(s)
    db.session.commit()
    return jsonify(s.to_dict()), 201


@app.route("/api/schedules/<sch_id>", methods=["PUT"])
@login_required
@role_required("admin", "editor")
def api_update_schedule(sch_id):
    s = db.session.get(Schedule, sch_id)
    if not s:
        return jsonify({"error": "Not found"}), 404
    data = request.get_json()
    new_name = data.get("name", s.name)
    new_start_time = data.get("start_time", s.start_time)
    new_end_time = data.get("end_time", s.end_time)
    new_days = data.get("days", s.days)
    new_is_active = bool(data["is_active"]) if "is_active" in data else s.is_active

    new_start_min = parse_hhmm_to_min(new_start_time)
    new_end_min = parse_hhmm_to_min(new_end_time)
    if new_start_min is None or new_end_min is None:
        return jsonify({"error": "start_time and end_time must be HH:MM (24-hour)"}), 400

    new_days_norm = normalize_days(new_days)
    if new_days_norm is None:
        return jsonify({"error": "days must be comma-separated mon,tue,wed,thu,fri,sat,sun"}), 400

    if new_is_active:
        candidate_intervals = schedule_to_day_intervals(new_start_min, new_end_min, new_days_norm)
        active_schedules = Schedule.query.filter(
            Schedule.is_active.is_(True),
            Schedule.id != sch_id,
        ).all()
        overlapping = find_overlapping_schedule(candidate_intervals, active_schedules)
        if overlapping:
            return jsonify({
                "error": (
                    f"Schedule overlaps with existing active schedule '{overlapping.name or overlapping.id}'"
                )
            }), 409

    s.name = new_name
    s.start_time = new_start_time
    s.end_time = new_end_time
    s.days = new_days_norm
    if "is_active" in data:
        s.is_active = new_is_active
    db.session.commit()
    return jsonify(s.to_dict())


@app.route("/api/schedules/<sch_id>", methods=["DELETE"])
@login_required
@role_required("admin", "editor")
def api_delete_schedule(sch_id):
    s = db.session.get(Schedule, sch_id)
    if not s:
        return jsonify({"error": "Not found"}), 404
    db.session.delete(s)
    db.session.commit()
    return jsonify({"success": True})


# ── API: Stats ─────────────────────────────────────────────────────────────────

@app.route("/api/stats")
@login_required
def api_stats():
    total_assets = Asset.query.count()
    total_playlists = Playlist.query.count()
    total_schedules = Schedule.query.count()
    active_schedules = Schedule.query.filter_by(is_active=True).count()
    total_users = User.query.count()
    # disk usage
    total_size = sum(f.stat().st_size for f in UPLOAD_FOLDER.rglob("*") if f.is_file())
    return jsonify({
        "total_assets": total_assets,
        "total_playlists": total_playlists,
        "total_schedules": total_schedules,
        "active_schedules": active_schedules,
        "total_users": total_users,
        "disk_used_bytes": total_size,
    })


# ── API: Current Playlist (for player) ────────────────────────────────────────

@app.route("/api/current-playlist")
def api_current_playlist():
    """Return the currently scheduled playlist or the first active one."""
    now = datetime.now()
    now_day_idx = now.weekday()
    now_min = now.hour * 60 + now.minute

    # Deterministic scheduler:
    # 1) Sort by start_time asc, then id asc for stable ordering.
    # 2) Match using normalized day intervals with overnight support.
    # 3) Explicit overlap fallback for legacy data: latest interval start wins.
    schedules = (
        Schedule.query
        .filter_by(is_active=True)
        .order_by(Schedule.start_time.asc(), Schedule.id.asc())
        .all()
    )

    matches = []
    for s in schedules:
        interval = schedule_match_interval_for_now(s, now_day_idx, now_min)
        if interval is None:
            continue
        pl = db.session.get(Playlist, s.playlist_id)
        if pl and pl.is_active:
            matches.append((s, pl, interval))

    if matches:
        matches.sort(key=lambda t: (-t[2][0], t[0].id))
        return jsonify(matches[0][1].to_dict())

    # Fallback: first active playlist
    pl = (
        Playlist.query
        .filter_by(is_active=True)
        .order_by(Playlist.created_at.asc(), Playlist.id.asc())
        .first()
    )
    if pl:
        return jsonify(pl.to_dict())
    return jsonify(None)


# ── Init DB ────────────────────────────────────────────────────────────────────

def init_db():
    with app.app_context():
        db.create_all()
        if not User.query.filter_by(username="admin").first():
            admin = User(username="admin", email="admin@lumina.local", role="admin")
            admin.set_password("admin123")
            db.session.add(admin)
            db.session.commit()
            print("✓ Created default admin user: admin / admin123")


if __name__ == "__main__":
    init_db()
    port = int(os.environ.get("PORT", 8080))
    debug = os.environ.get("DEBUG", "false").lower() == "true"
    app.run(host="0.0.0.0", port=port, debug=debug)
