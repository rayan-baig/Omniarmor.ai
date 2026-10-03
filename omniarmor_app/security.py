# -*- coding: utf-8 -*-
"""Sign-in, form protection, login rate limits and security headers."""

import hashlib
import hmac
import re
import secrets
from datetime import timedelta
from functools import wraps
from urllib.parse import urlsplit

from flask import abort, flash, g, redirect, request, session, url_for

from .db import get_db, iso, utcnow

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
MIN_PASSWORD = 10
MAX_FAILURES = 5
FAILURE_WINDOW = timedelta(minutes=15)


def hash_token(token):
    return hashlib.sha256(token.encode()).hexdigest()


def new_token():
    token = secrets.token_urlsafe(32)
    return token, hash_token(token)


def normalize_email(email):
    return (email or "").strip().lower()


def valid_email(email):
    return bool(EMAIL_RE.match(email)) and len(email) <= 254


def clean_text(value, max_len):
    """Trims a name and returns None if it is empty, too long or has control
    characters (which could break emails and exports)."""
    value = (value or "").strip()
    if not value or len(value) > max_len or any(ord(c) < 32 or ord(c) == 127 for c in value):
        return None
    return value


def password_problem(password):
    if len(password or "") < MIN_PASSWORD:
        return f"Use at least {MIN_PASSWORD} characters for your password."
    if len(password) > 200:
        return "That password is too long."
    return None


# --- Forms ---------------------------------------------------------------

def csrf_token():
    if "_csrf" not in session:
        session["_csrf"] = secrets.token_urlsafe(32)
    return session["_csrf"]


CSRF_EXEMPT = {"plan.stripe_webhook"}  # signed by Stripe instead


def check_csrf():
    if request.method != "POST" or request.endpoint in CSRF_EXEMPT:
        return
    sent = request.form.get("csrf_token", "")
    expected = session.get("_csrf", "")
    if not expected or not hmac.compare_digest(sent, expected):
        abort(400, description="This form expired. Go back, reload the page and try again.")


# --- Sessions ------------------------------------------------------------

def start_session(user):
    session.clear()
    session.permanent = True
    session["user_id"] = user["id"]
    session["epoch"] = user["session_epoch"]
    csrf_token()


def load_user():
    """Sets g.user, g.org and g.role from the session, or leaves them None.
    A kid who joined with a join code gets g.kid (their learner) and g.org
    instead, and can only use the Academy."""
    g.user = g.org = g.role = g.kid = None
    user_id = session.get("user_id")
    if user_id is None:
        if session.get("kid") is not None:
            load_kid()
        return
    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if user is None or user["session_epoch"] != session.get("epoch"):
        session.clear()
        return
    membership = conn.execute(
        "SELECT orgs.*, memberships.role FROM memberships JOIN orgs ON orgs.id = memberships.org_id"
        " WHERE memberships.user_id = ? ORDER BY memberships.created_at LIMIT 1",
        (user_id,),
    ).fetchone()
    if membership is None:
        session.clear()
        return
    g.user, g.org, g.role = user, membership, membership["role"]


def load_kid():
    conn = get_db()
    kid = conn.execute("SELECT * FROM learners WHERE id = ?", (session.get("kid"),)).fetchone()
    if kid is None or kid["device_epoch"] != session.get("kid_epoch"):
        session.clear()
        return
    g.kid = kid
    g.org = conn.execute("SELECT * FROM orgs WHERE id = ?", (kid["org_id"],)).fetchone()


def start_kid_session(learner):
    session.clear()
    session.permanent = True
    session["kid"] = learner["id"]
    session["kid_epoch"] = learner["device_epoch"]
    csrf_token()


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if g.get("user") is None:
            return redirect(url_for("auth.login", next=request.full_path if request.method == "GET" else None))
        return view(*args, **kwargs)
    return wrapped


def owner_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if g.get("user") is None:
            return redirect(url_for("auth.login"))
        if g.role != "owner":
            abort(403)
        return view(*args, **kwargs)
    return wrapped


def safe_next(target):
    """Only allow redirects back into this site after sign-in. Rejects anything a
    browser could read as another site, including tricks with tabs or backslashes."""
    if not target or any(ord(c) < 33 or ord(c) == 127 or c == "\\" for c in target):
        return url_for("app.overview")
    parts = urlsplit(target)
    if parts.scheme or parts.netloc or not target.startswith("/") or target.startswith("//"):
        return url_for("app.overview")
    return target


# --- Login rate limiting -------------------------------------------------

def client_ip():
    return request.remote_addr or "unknown"


def rate_limited(limits, window):
    """limits is a list of (key, max events) pairs; True if any key reached its max within window."""
    conn = get_db()
    since = iso(utcnow() - window)
    for key, most in limits:
        count = conn.execute("SELECT COUNT(*) FROM login_failures WHERE key = ? AND at >= ?", (key, since)).fetchone()[0]
        if count >= most:
            return True
    return False


def record_event(keys):
    conn = get_db()
    now = iso(utcnow())
    conn.executemany("INSERT INTO login_failures (key, at) VALUES (?, ?)", [(k, now) for k in keys])
    conn.commit()


def _failure_keys(email):
    return [f"email:{normalize_email(email)}", f"ip:{client_ip()}"]


def too_many_failures(email):
    email_key, ip_key = _failure_keys(email)
    return rate_limited([(email_key, MAX_FAILURES), (ip_key, MAX_FAILURES * 4)], FAILURE_WINDOW)


def record_failure(email):
    record_event(_failure_keys(email))


def clear_failures(email):
    conn = get_db()
    conn.execute("DELETE FROM login_failures WHERE key = ?", (f"email:{normalize_email(email)}",))
    conn.commit()


# --- Headers -------------------------------------------------------------

CSP = (
    "default-src 'self'; style-src 'self' https://fonts.googleapis.com; style-src-attr 'unsafe-inline';"
    " font-src https://fonts.gstatic.com;"
    " img-src 'self' data:; script-src 'self'; form-action 'self'; frame-ancestors 'none'; base-uri 'self';"
    " object-src 'none'"
)


def security_headers(response):
    response.headers.setdefault("Content-Security-Policy", CSP)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "same-origin")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    if request.is_secure:
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    if g.get("user") is not None:
        response.headers.setdefault("Cache-Control", "no-store")
    return response


def flash_error(message):
    flash(message, "error")
