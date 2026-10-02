# -*- coding: utf-8 -*-
"""Sign up, sign in, sign out, password reset and team invites."""

import sqlite3
from datetime import timedelta
from zoneinfo import available_timezones

from flask import Blueprint, current_app, flash, g, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from .catalog import INDUSTRIES
from .db import get_db, iso, now_iso, record_audit, utcnow
from .notify import notify
from .security import (
    clean_text, clear_failures, client_ip, flash_error, hash_token, new_token, normalize_email, password_problem, rate_limited,
    record_event, record_failure,
    safe_next, start_session, too_many_failures, valid_email,
)

bp = Blueprint("auth", __name__)

COMMON_TIMEZONES = [
    "America/New_York", "America/Chicago", "America/Denver", "America/Phoenix", "America/Los_Angeles",
    "America/Anchorage", "Pacific/Honolulu", "America/Puerto_Rico", "America/Toronto", "America/Mexico_City",
    "Europe/London", "Europe/Berlin", "Europe/Paris", "Asia/Dubai", "Asia/Kolkata", "Asia/Singapore",
    "Asia/Tokyo", "Australia/Sydney", "UTC",
]
INVITE_DAYS = 7
RESET_HOURS = 1
GENERIC_LOGIN_ERROR = "That email and password don't match an account."


def valid_timezone(name):
    return name in available_timezones() or name == "UTC"


def _invite(conn, token):
    if not token:
        return None
    row = conn.execute(
        "SELECT invites.*, orgs.name AS org_name FROM invites JOIN orgs ON orgs.id = invites.org_id"
        " WHERE token_hash = ? AND used_at IS NULL AND expires_at > ?",
        (hash_token(token), now_iso()),
    ).fetchone()
    return row


@bp.route("/signup", methods=["GET", "POST"])
def signup():
    if g.get("user") is not None:
        return redirect(url_for("app.overview"))
    conn = get_db()
    token = request.values.get("invite", "")
    invite = _invite(conn, token)
    if token and invite is None:
        flash_error("That invite link has expired or was already used. Ask your team owner for a new one.")
    form = request.form
    if request.method == "POST":
        name = clean_text(form.get("name"), 100)
        email = normalize_email(form.get("email"))
        password = form.get("password", "")
        org_name = clean_text(form.get("org_name"), 120)
        tz = form.get("timezone", "UTC")
        picked = sorted({int(i) for i in form.getlist("industries") if i.isdigit() and int(i) in INDUSTRIES})
        errors = []
        if not name:
            errors.append("Enter your name.")
        if not valid_email(email):
            errors.append("Enter a valid email address.")
        problem = password_problem(password)
        if problem:
            errors.append(problem)
        if invite is None:
            if not org_name:
                errors.append("Enter your company name.")
            if not picked:
                errors.append("Pick at least one industry.")
            if not valid_timezone(tz):
                errors.append("Pick a valid timezone.")
        if not errors and conn.execute("SELECT 1 FROM users WHERE email = ?", (email,)).fetchone():
            errors.append("An account with that email already exists. Sign in instead.")
        if errors:
            for e in errors:
                flash_error(e)
            return render_template("auth/signup.html", invite=invite, token=token, industries=INDUSTRIES,
                                   timezones=COMMON_TIMEZONES, form=form, picked=set(picked)), 400
        now = now_iso()
        if invite is not None:
            claimed = conn.execute("UPDATE invites SET used_at = ? WHERE token_hash = ? AND used_at IS NULL AND expires_at > ?",
                                   (now, invite["token_hash"], now)).rowcount
            if claimed != 1:
                conn.rollback()
                flash_error("That invite link was just used. Ask your team owner for a new one.")
                return redirect(url_for("auth.signup"))
        try:
            user_id = conn.execute(
                "INSERT INTO users (email, name, password_hash, created_at) VALUES (?, ?, ?, ?)",
                (email, name, generate_password_hash(password), now),
            ).lastrowid
        except sqlite3.IntegrityError:
            conn.rollback()
            flash_error("An account with that email already exists. Sign in instead.")
            return render_template("auth/signup.html", invite=None if invite is None else _invite(conn, token), token=token,
                                   industries=INDUSTRIES, timezones=COMMON_TIMEZONES, form=form, picked=set(picked)), 400
        if invite is None:
            org_id = conn.execute("INSERT INTO orgs (name, timezone, created_at) VALUES (?, ?, ?)",
                                  (org_name, tz, now)).lastrowid
            conn.execute("INSERT INTO memberships (user_id, org_id, role, created_at) VALUES (?, ?, 'owner', ?)",
                         (user_id, org_id, now))
            conn.executemany("INSERT INTO org_industries (org_id, industry_id) VALUES (?, ?)",
                             [(org_id, i) for i in picked])
            record_audit(conn, org_id, user_id, "workspace", f"Workspace created with {len(picked)} industries")
        else:
            org_id = invite["org_id"]
            conn.execute("INSERT INTO memberships (user_id, org_id, role, created_at) VALUES (?, ?, 'member', ?)",
                         (user_id, org_id, now))
            record_audit(conn, org_id, user_id, "team", f"{name} joined the team")
        conn.commit()
        start_session(conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone())
        flash("Welcome to OmniArmor. Start by entering your first readings.", "ok")
        return redirect(url_for("app.overview"))
    preselect = request.args.get("industry", type=int)
    return render_template("auth/signup.html", invite=invite, token=token, industries=INDUSTRIES,
                           timezones=COMMON_TIMEZONES, form=form, picked={preselect} if preselect in INDUSTRIES else set())


@bp.route("/login", methods=["GET", "POST"])
def login():
    if g.get("user") is not None:
        return redirect(url_for("app.overview"))
    if request.method == "POST":
        email = normalize_email(request.form.get("email"))
        password = request.form.get("password", "")
        if too_many_failures(email):
            flash_error("Too many sign-in attempts. Wait 15 minutes, or reset your password.")
            return render_template("auth/login.html", email=email), 429
        conn = get_db()
        user = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        if user is None or not check_password_hash(user["password_hash"], password):
            record_failure(email)
            flash_error(GENERIC_LOGIN_ERROR)
            return render_template("auth/login.html", email=email), 401
        if not conn.execute("SELECT 1 FROM memberships WHERE user_id = ?", (user["id"],)).fetchone():
            flash_error("This account is no longer part of a workspace.")
            return render_template("auth/login.html", email=email), 403
        clear_failures(email)
        start_session(user)
        return redirect(safe_next(request.args.get("next")))
    return render_template("auth/login.html", email="")


@bp.route("/logout", methods=["POST"])
def logout():
    session.clear()
    flash("You're signed out.", "ok")
    return redirect(url_for("auth.login"))


@bp.route("/forgot", methods=["GET", "POST"])
def forgot():
    if request.method == "POST":
        email = normalize_email(request.form.get("email"))
        conn = get_db()
        user = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        reset_keys = [f"reset:{email}", f"reset-ip:{client_ip()}"]
        allowed = not rate_limited([(reset_keys[0], 3), (reset_keys[1], 20)], timedelta(hours=1))
        if allowed:
            record_event(reset_keys)
        if user is not None and allowed:
            token, token_hash = new_token()
            conn.execute("INSERT INTO password_resets (token_hash, user_id, created_at, expires_at) VALUES (?, ?, ?, ?)",
                         (token_hash, user["id"], now_iso(), iso(utcnow() + timedelta(hours=RESET_HOURS))))
            conn.commit()
            link = f"{current_app.config['BASE_URL']}{url_for('auth.reset', token=token)}"
            notify(conn, current_app.config, "password_reset", user["email"], "Reset your OmniArmor password",
                   f"Hi {user['name']},\n\nUse this link within {RESET_HOURS} hour to set a new password:\n{link}\n\n"
                   "If you didn't ask for this, you can ignore this email.", user_id=user["id"])
        flash("If that email has an account, a reset link is on its way.", "ok")
        return redirect(url_for("auth.login"))
    return render_template("auth/forgot.html")


@bp.route("/reset/<token>", methods=["GET", "POST"])
def reset(token):
    conn = get_db()
    row = conn.execute("SELECT * FROM password_resets WHERE token_hash = ? AND used_at IS NULL AND expires_at > ?",
                       (hash_token(token), now_iso())).fetchone()
    if row is None:
        flash_error("That reset link has expired or was already used. Request a new one.")
        return redirect(url_for("auth.forgot"))
    if request.method == "POST":
        password = request.form.get("password", "")
        problem = password_problem(password)
        if problem:
            flash_error(problem)
            return render_template("auth/reset.html", token=token), 400
        conn.execute("UPDATE users SET password_hash = ?, session_epoch = session_epoch + 1 WHERE id = ?",
                     (generate_password_hash(password), row["user_id"]))
        conn.execute("UPDATE password_resets SET used_at = ? WHERE user_id = ? AND used_at IS NULL",
                     (now_iso(), row["user_id"]))
        conn.commit()
        user = conn.execute("SELECT * FROM users WHERE id = ?", (row["user_id"],)).fetchone()
        clear_failures(user["email"])
        flash("Your password is changed. Every other device was signed out.", "ok")
        start_session(user)
        return redirect(url_for("app.overview"))
    return render_template("auth/reset.html", token=token)


def create_invite(conn, org_id, user_id):
    token, token_hash = new_token()
    conn.execute("INSERT INTO invites (token_hash, org_id, created_by, created_at, expires_at) VALUES (?, ?, ?, ?, ?)",
                 (token_hash, org_id, user_id, now_iso(), iso(utcnow() + timedelta(days=INVITE_DAYS))))
    record_audit(conn, org_id, user_id, "team", f"Invite link created (valid {INVITE_DAYS} days)")
    conn.commit()
    return f"{current_app.config['BASE_URL']}{url_for('auth.signup', invite=token)}"
