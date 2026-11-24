# -*- coding: utf-8 -*-
"""Sign-in, form protection, login rate limits and security headers."""

import base64
import hashlib
import hmac
import re
import secrets
from datetime import timedelta
from functools import wraps
from urllib.parse import urlsplit

from flask import abort, flash, g, redirect, request, session, url_for

from .db import get_db, iso, utcnow
from .pilot import CONNECT as PILOT_CONNECT

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

def _session_csrf():
    if "_csrf" not in session:
        session["_csrf"] = secrets.token_urlsafe(32)
    return session["_csrf"]


def csrf_token():
    """The form token, masked differently on every page: random bytes, then
    the session's token XORed with them. Pages are sent compressed
    (compress.py), and a secret that stays the same on every page could be
    guessed from compressed sizes (the BREACH attack); this one never repeats."""
    raw = _session_csrf().encode()
    pad = secrets.token_bytes(len(raw))
    return base64.urlsafe_b64encode(pad + bytes(a ^ b for a, b in zip(pad, raw))).decode()


def _unmask(sent):
    """The session token inside a masked one, as bytes, or None if `sent`
    isn't one (a page drawn before masking, or a test, posts the session's
    token itself)."""
    try:
        packed = base64.urlsafe_b64decode(sent.encode("ascii"))
    except (ValueError, UnicodeEncodeError):
        return None
    if not packed or len(packed) % 2:
        return None
    half = len(packed) // 2
    return bytes(a ^ b for a, b in zip(packed[:half], packed[half:]))


# Signed by Stripe instead; and Kryozyn's daily report, which carries the
# workspace's connection key in its Authorization header and never reads the
# session cookie, so a form posted from another site has nothing to borrow.
CSRF_EXEMPT = {"plan.stripe_webhook", "connect.cyberlogix_daily"}


# 1.24.0: the app's old addresses (OLD_HOSTS, names.py) send pages on to the
# new one. These are answered at the old address as they are: Stripe and
# Kryozyn post there until their settings change (a redirect would lose the
# POST), and an uptime monitor may still check the health pages there.
OLD_HOST_SERVED = {"plan.stripe_webhook", "connect.cyberlogix_daily", "public.healthz", "public.readyz",
                   "public.stats"}


def old_host_redirect():
    """A request for one of the app's old addresses, sent on (301) to the same
    path and query at BASE_URL's address."""
    from flask import current_app
    old = current_app.config.get("OLD_HOSTS") or ()
    host = (request.host or "").split(":")[0].lower()
    if host not in old or request.endpoint in OLD_HOST_SERVED:
        return None
    base = current_app.config.get("BASE_URL", "").rstrip("/")
    if not base or urlsplit(base).hostname == host:
        return None
    query = request.query_string.decode("latin-1")
    return redirect(base + request.path + (f"?{query}" if query else ""), code=301)


def check_csrf():
    if request.method != "POST" or request.endpoint in CSRF_EXEMPT:
        return
    sent = request.form.get("csrf_token", "")
    expected = session.get("_csrf", "")
    unmasked = _unmask(sent)
    if not expected or not (hmac.compare_digest(sent.encode("utf-8", "replace"), expected.encode())
                            or (unmasked is not None and hmac.compare_digest(unmasked, expected.encode()))):
        abort(400, description="This form expired. Go back, reload the page and try again.")


# --- Sessions ------------------------------------------------------------

def _user_key(user):
    """Ties a session to this exact account, not just its row id: SQLite can
    reuse the id of a removed user for a new one, whose session_epoch also
    starts at 0, so the id and epoch alone could match an old cookie."""
    return hashlib.sha256(f"{user['id']}:{user['email'].lower()}:{user['created_at']}".encode()).hexdigest()[:32]


def start_session(user):
    session.clear()
    session.permanent = True
    session["user_id"] = user["id"]
    session["epoch"] = user["session_epoch"]
    session["ukey"] = _user_key(user)
    _session_csrf()


def load_user():
    """Sets g.user, g.org and g.role from the session, or leaves them None.
    A kid who joined with a join code gets g.kid (their learner) and g.org
    instead, and can only use the Academy."""
    g.user = g.org = g.role = g.kid = None
    if session.get("demo") is not None and session.get("user_id") is None:
        # A demo pass (demo_mode.py): the demo's pretend owner, on the app's
        # pages only, in a throwaway copy of the demo database.
        from . import demo_mode
        if demo_mode.load():
            return
    user_id = session.get("user_id")
    if user_id is None:
        if session.get("kid") is not None:
            load_kid()
        return
    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if (user is None or user["session_epoch"] != session.get("epoch")
            or not hmac.compare_digest(str(session.get("ukey", "")), _user_key(user))):
        session.clear()
        return
    # The workspace (location) this person is working in: the one they last
    # switched to (session "org_id"), if they still belong to it, else their first.
    chosen = session.get("org_id")
    membership = None
    if isinstance(chosen, int) and 0 < chosen < 2 ** 63:
        membership = conn.execute(
            "SELECT orgs.*, memberships.role FROM memberships JOIN orgs ON orgs.id = memberships.org_id"
            " WHERE memberships.user_id = ? AND memberships.org_id = ?", (user_id, chosen)).fetchone()
    if membership is None:
        membership = conn.execute(
            "SELECT orgs.*, memberships.role FROM memberships JOIN orgs ON orgs.id = memberships.org_id"
            " WHERE memberships.user_id = ? ORDER BY memberships.created_at, orgs.id LIMIT 1",
            (user_id,),
        ).fetchone()
    if membership is None:
        session.clear()
        return
    g.user, g.org, g.role = user, membership, membership["role"]
    # The day this person last used the app, written at most once a day: it
    # is what "active users" counts, and it is a date, not a trail.
    today = utcnow().date().isoformat()
    if user["last_seen_on"] != today:
        conn.execute("UPDATE users SET last_seen_on = ? WHERE id = ?", (today, user_id))
        conn.commit()


def new_device_epoch():
    """A random starting point for a learner's device epoch, so a device
    cookie left over from a removed learner can't match a new learner who
    gets the same row id. Signing out adds one, so stay well below 2**63."""
    return secrets.randbelow(2 ** 62) + 1


def load_kid():
    conn = get_db()
    kid_id, org_id = session.get("kid"), session.get("kid_org")
    if not isinstance(kid_id, int) or not isinstance(org_id, int) or not 0 < kid_id < 2 ** 63:
        session.clear()
        return
    kid = conn.execute("SELECT * FROM learners WHERE id = ? AND org_id = ?", (kid_id, org_id)).fetchone()
    if kid is None or kid["device_epoch"] != session.get("kid_epoch"):
        session.clear()
        return
    g.kid = kid
    g.org = conn.execute("SELECT * FROM orgs WHERE id = ?", (kid["org_id"],)).fetchone()
    if g.org is None:
        g.kid = None
        session.clear()


def start_kid_session(learner):
    session.clear()
    session.permanent = True
    session["kid"] = learner["id"]
    session["kid_org"] = learner["org_id"]
    session["kid_epoch"] = learner["device_epoch"]
    _session_csrf()


def _kid_home():
    """A student who joined on this device (g.kid) opening a grown-up's page
    goes back to their own map, never to the business sign-in (1.16.0)."""
    if g.get("kid") is not None and request.method == "GET":
        return redirect(url_for("academy.level_map", learner_id=g.kid["id"]))
    return None


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if g.get("user") is None:
            back = _kid_home()
            if back is not None:
                return back
            return redirect(url_for("auth.login", next=request.full_path if request.method == "GET" else None))
        return view(*args, **kwargs)
    return wrapped


def owner_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if g.get("user") is None:
            return _kid_home() or redirect(url_for("auth.login"))
        if g.role != "owner":
            abort(403)
        return view(*args, **kwargs)
    return wrapped


def home_url():
    """A signed-in person's home page: the classes page in a school's
    workspace (classrooms.is_class_workspace), the overview in a business's.
    Right after sign-in g.org isn't loaded yet, so it is read from the session."""
    from .classrooms import is_class_workspace
    org = g.get("org")
    if org is None and session.get("user_id") is not None:
        chosen = session.get("org_id")
        rows = get_db().execute(
            "SELECT orgs.* FROM memberships JOIN orgs ON orgs.id = memberships.org_id WHERE memberships.user_id = ?"
            " ORDER BY memberships.created_at, orgs.id", (session["user_id"],)).fetchall()
        org = next((r for r in rows if r["id"] == chosen), rows[0] if rows else None)
    return url_for("classes.index") if is_class_workspace(org) else url_for("app.overview")


def safe_next(target):
    """Only allow redirects back into this site after sign-in. Rejects anything a
    browser could read as another site, including tricks with tabs or backslashes."""
    if not target or any(ord(c) < 33 or ord(c) == 127 or c == "\\" for c in target):
        return home_url()
    parts = urlsplit(target)
    if parts.scheme or parts.netloc or not target.startswith("/") or target.startswith("//"):
        return home_url()
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
    address = normalize_email(email)
    return [f"email-ip:{address}|{client_ip()}", f"email:{address}", f"ip:{client_ip()}"]


def too_many_failures(email):
    """Five wrong tries from one place, for one address, stops that place.

    The limit used to be five per address from anywhere, so anybody who knew
    an email could keep its owner out with five wrong passwords every fifteen
    minutes. Now the five are per address and place; an address being guessed
    at from many places at once still stops at fifty, and a place guessing at
    many addresses stops at twenty.
    """
    pair_key, email_key, ip_key = _failure_keys(email)
    return rate_limited([(pair_key, MAX_FAILURES), (email_key, MAX_FAILURES * 10),
                         (ip_key, MAX_FAILURES * 4)], FAILURE_WINDOW)


def record_failure(email):
    record_event(_failure_keys(email))


def clear_failures(email):
    pair_key, email_key, _ = _failure_keys(email)
    conn = get_db()
    conn.execute("DELETE FROM login_failures WHERE key IN (?, ?)", (pair_key, email_key))
    conn.commit()


# --- Headers -------------------------------------------------------------

CSP = (
    # Fonts come from this site too (static/fonts): no outside company sees a visit.
    "default-src 'self'; style-src 'self';"
    " font-src 'self';"
    " img-src 'self' data:; script-src 'self'; form-action 'self'; frame-ancestors 'none'; base-uri 'self';"
    " object-src 'none';"
    # Pilot (pilot.py, docs/PILOT.md) calls the AI provider the person chose,
    # from their browser with their own key: exactly these addresses, and
    # nothing else. blob: is only for a video Pilot made with their own video
    # key, shown from memory in their own browser.
    f" connect-src 'self' {PILOT_CONNECT}; media-src 'self' blob:"
)


def security_headers(response):
    response.headers.setdefault("Content-Security-Policy", CSP)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "same-origin")
    # The microphone only for this site's own pages: Pilot's optional voice
    # input, used only when its button is pressed.
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(self), geolocation=()")
    if request.is_secure:
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    if g.get("user") is not None or g.get("kid") is not None:
        response.headers.setdefault("Cache-Control", "no-store")
    return response


def flash_error(message):
    flash(message, "error")
