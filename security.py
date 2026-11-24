"""Security helpers: auth state, RBAC, CSRF, upload validation, rate limiting."""
import os
import time
import secrets
import functools

from flask import session, redirect, url_for, flash, request, abort, g
from werkzeug.utils import secure_filename

from models import User


# ----------------------------------------------------------------------------
# Current user
# ----------------------------------------------------------------------------
def current_user():
    """Return the logged-in User (cached per request) or None."""
    if "user" in g:
        return g.user
    uid = session.get("uid")
    g.user = User.query.get(uid) if uid else None
    return g.user


def login_user(user):
    session.clear()
    session["uid"] = user.id
    session.permanent = True
    # Rotate CSRF token on privilege change to prevent fixation.
    session["csrf"] = secrets.token_urlsafe(32)


def logout_user():
    session.clear()


# ----------------------------------------------------------------------------
# Access control decorators
# ----------------------------------------------------------------------------
def login_required(view):
    @functools.wraps(view)
    def wrapped(*args, **kwargs):
        if current_user() is None:
            flash("Please sign in to continue.", "warning")
            return redirect(url_for("auth.login", next=request.path))
        return view(*args, **kwargs)
    return wrapped


def roles_required(*roles):
    """Allow only the given roles to reach the view."""
    def decorator(view):
        @functools.wraps(view)
        def wrapped(*args, **kwargs):
            user = current_user()
            if user is None:
                return redirect(url_for("auth.login", next=request.path))
            if user.role not in roles:
                abort(403)
            return view(*args, **kwargs)
        return wrapped
    return decorator


# ----------------------------------------------------------------------------
# CSRF protection (double-submit token held in the session)
# ----------------------------------------------------------------------------
def get_csrf_token():
    token = session.get("csrf")
    if not token:
        token = secrets.token_urlsafe(32)
        session["csrf"] = token
    return token


def verify_csrf():
    """Validate CSRF token on every state-changing request."""
    if request.method in ("POST", "PUT", "PATCH", "DELETE"):
        sent = request.form.get("csrf_token") or request.headers.get("X-CSRF-Token")
        if not sent or not secrets.compare_digest(sent, session.get("csrf", "")):
            abort(400, description="Invalid or missing CSRF token.")


# ----------------------------------------------------------------------------
# File uploads
# ----------------------------------------------------------------------------
def save_profile_picture(file_storage, allowed_ext, upload_folder):
    """Validate and store an uploaded profile picture. Returns filename or None."""
    if not file_storage or file_storage.filename == "":
        return None
    name = secure_filename(file_storage.filename)
    if "." not in name:
        return None
    ext = name.rsplit(".", 1)[1].lower()
    if ext not in allowed_ext:
        raise ValueError("Unsupported image type. Use PNG, JPG, GIF or WEBP.")
    unique = f"{secrets.token_hex(8)}.{ext}"
    os.makedirs(upload_folder, exist_ok=True)
    file_storage.save(os.path.join(upload_folder, unique))
    return unique


def save_recording(file_storage, folder):
    """Store an interview audio/video recording blob. Returns filename or None."""
    if not file_storage or file_storage.filename == "":
        return None
    name = secure_filename(file_storage.filename) or "rec.webm"
    ext = name.rsplit(".", 1)[1].lower() if "." in name else "webm"
    if ext not in {"webm", "ogg", "mp4", "wav", "m4a"}:
        ext = "webm"
    unique = f"{secrets.token_hex(8)}.{ext}"
    os.makedirs(folder, exist_ok=True)
    file_storage.save(os.path.join(folder, unique))
    return unique


def generate_otp():
    """A 4-digit numeric OTP."""
    return f"{secrets.randbelow(10000):04d}"


# ----------------------------------------------------------------------------
# Simple in-memory login rate limiting (per username+IP)
# ----------------------------------------------------------------------------
_attempts = {}          # key -> [timestamps]
_WINDOW = 300           # 5 minutes
_MAX_ATTEMPTS = 8


def rate_limited(key):
    now = time.time()
    hits = [t for t in _attempts.get(key, []) if now - t < _WINDOW]
    _attempts[key] = hits
    return len(hits) >= _MAX_ATTEMPTS


def record_attempt(key):
    _attempts.setdefault(key, []).append(time.time())


def clear_attempts(key):
    _attempts.pop(key, None)
