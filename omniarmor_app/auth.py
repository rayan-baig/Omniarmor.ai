# -*- coding: utf-8 -*-
"""Sign up, sign in, sign out, password reset and team invites."""

import sqlite3
from datetime import timedelta
from zoneinfo import available_timezones

from flask import Blueprint, current_app, flash, g, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from . import usage
from .catalog import INDUSTRIES, TOP_COUNT
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
SIGNUPS_PER_HOUR = 10
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


def _taken_message(invite):
    if invite is None:
        return "An account with that email already exists. Sign in instead."
    # Signing in would only open that account's own workspace: a person
    # belongs to one workspace, so the invite needs a different email.
    return ("That email already has an OmniArmor account, and an account belongs to one workspace."
            f" To join {invite['org_name']}, use a different email address.")


def _start_industry(form):
    """The industry whose page the sign-up came from, if any."""
    start = form.get("start", type=int)
    return start if start in INDUSTRIES else None


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
        picked = sorted({int(i) for i in form.getlist("industries") if i.isascii() and i.isdigit() and len(i) < 6 and int(i) in INDUSTRIES})
        errors = []
        # Sign-ups from one place are limited: each costs a password hash, and
        # an unlimited form could tie the server up or fill the database.
        signup_key = f"signup-ip:{client_ip()}"
        if rate_limited([(signup_key, SIGNUPS_PER_HOUR)], timedelta(hours=1)):
            errors.append("Too many sign-ups from here in the last hour. Try again later.")
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
            errors.append(_taken_message(invite))
        if errors:
            for e in errors:
                flash_error(e)
            return render_template("auth/signup.html", invite=invite, token=token, industries=INDUSTRIES,
                                   timezones=COMMON_TIMEZONES, form=form, picked=set(picked),
                                   start_industry=_start_industry(form)), 400
        record_event([signup_key])
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
            flash_error(_taken_message(invite))
            return render_template("auth/signup.html", invite=None if invite is None else _invite(conn, token), token=token,
                                   industries=INDUSTRIES, timezones=COMMON_TIMEZONES, form=form, picked=set(picked),
                                   start_industry=_start_industry(form)), 400
        if invite is None:
            org_id = conn.execute("INSERT INTO orgs (name, timezone, created_at) VALUES (?, ?, ?)",
                                  (org_name, tz, now)).lastrowid
            conn.execute("INSERT INTO memberships (user_id, org_id, role, created_at) VALUES (?, ?, 'owner', ?)",
                         (user_id, org_id, now))
            conn.executemany("INSERT INTO org_industries (org_id, industry_id) VALUES (?, ?)",
                             [(org_id, i) for i in picked])
            record_audit(conn, org_id, user_id, "workspace", f"Workspace created with {len(picked)} industries")
            start = _start_industry(form) if _start_industry(form) in picked else picked[0]
        else:
            org_id = invite["org_id"]
            conn.execute("INSERT INTO memberships (user_id, org_id, role, created_at) VALUES (?, ?, 'member', ?)",
                         (user_id, org_id, now))
            record_audit(conn, org_id, user_id, "team", f"{name} joined the team")
        conn.commit()
        usage.count(conn, "signups")
        start_session(conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone())
        if invite is not None:
            flash(f"Welcome to {invite['org_name']} on OmniArmor.", "ok")
            return redirect(url_for("app.overview"))
        # A new workspace opens on an industry page, where the first check is
        # saved, not on an overview of empty totals one click further away.
        flash(f"Welcome to OmniArmor. Start with the top {TOP_COUNT} checks below: enter each date"
              " or answer once and OmniArmor keeps count from there.", "ok")
        return redirect(url_for("app.industry", industry_id=start))
    preselect = request.args.get("industry", type=int)
    preselect = preselect if preselect in INDUSTRIES else None
    return render_template("auth/signup.html", invite=invite, token=token, industries=INDUSTRIES,
                           timezones=COMMON_TIMEZONES, form=form, picked={preselect} if preselect else set(),
                           start_industry=preselect)


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
    # Ends the session on the server too. Sessions are signed cookies that
    # last fourteen days, and clearing only this browser's copy left a copied
    # or forgotten cookie working after "sign out". Moving the epoch on ends
    # every session this person has, which is what signing out should mean.
    user_id = session.get("user_id")
    if user_id:
        conn = get_db()
        conn.execute("UPDATE users SET session_epoch = session_epoch + 1 WHERE id = ?", (user_id,))
        conn.commit()
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
                   reset_email(user["name"], link), user_id=user["id"])
        flash("If that email has an account, a reset link is on its way.", "ok")
        return redirect(url_for("auth.login"))
    return render_template("auth/forgot.html")


def reset_email(name, link):
    """The password reset email's body."""
    hours = f"{RESET_HOURS} hour{'s' if RESET_HOURS != 1 else ''}"
    return (f"Hi {name},\n\nSomeone, we hope you, asked to reset your OmniArmor password. The link works for {hours},"
            f" once.\n\nSet a new password: {link}\n\n"
            "If you didn't ask for this, you can ignore this email. Your password stays as it is.")


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


# --- Operator status ---------------------------------------------------------------
#
# The operator's account sees the usage counts and the weekly Autopilot
# report's switch in Settings. Signing up with the OPERATOR_EMAIL address is
# not enough to get it: sign-up doesn't prove an address is yours, so a
# stranger could register it before the owner does. Only the make-operator
# command, run on the server, sets the flag, and the account must still have
# the OPERATOR_EMAIL address for the flag to count.

def is_operator(user, cfg):
    """Whether this account is the operator's: flagged by make-operator, and
    its address is still OPERATOR_EMAIL."""
    to = normalize_email(cfg.get("OPERATOR_EMAIL"))
    return bool(to) and user is not None and bool(user["is_operator"]) and normalize_email(user["email"]) == to


class OperatorRefused(Exception):
    """make-operator said no; the message says why."""


def set_operator(conn, cfg, email, on=True):
    """Gives operator status to the account with this address (on=True), or
    takes it away (on=False). Giving it needs the OPERATOR_EMAIL address and
    takes it from any other account, so there is one operator at a time.
    Returns the account's row; raises OperatorRefused."""
    email = normalize_email(email)
    to = normalize_email(cfg.get("OPERATOR_EMAIL"))
    if on and not to:
        raise OperatorRefused("OPERATOR_EMAIL is not set. Set it, restart the app, then run this again.")
    if on and email != to:
        raise OperatorRefused("That address is not OPERATOR_EMAIL. Only the account with the OPERATOR_EMAIL "
                              "address can be the operator. Nothing was changed.")
    user = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    if user is None:
        raise OperatorRefused("No account has that address. Sign up with it first (or, to take the status "
                              "away, check the spelling). Nothing was changed.")
    if on:
        conn.execute("UPDATE users SET is_operator = (id = ?) WHERE is_operator = 1 OR id = ?",
                     (user["id"], user["id"]))
    else:
        conn.execute("UPDATE users SET is_operator = 0 WHERE id = ?", (user["id"],))
    conn.commit()
    return conn.execute("SELECT * FROM users WHERE id = ?", (user["id"],)).fetchone()
