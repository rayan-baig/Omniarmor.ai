# -*- coding: utf-8 -*-
"""Settings, read from environment variables. See .env.example and docs/OPERATIONS.md."""

import os
import secrets
from datetime import timedelta

from . import names


def _flag(name, default):
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in ("1", "true", "yes", "on")


# Where people write for help when SUPPORT_EMAIL isn't set: the company's
# help address (names.py), so no page ever ends without a way to reach a person.
DEFAULT_SUPPORT_EMAIL = names.HELP_EMAIL


def support_email(cfg):
    """The address pages give for help and for "contact us"."""
    return (cfg.get("SUPPORT_EMAIL") or "").strip() or DEFAULT_SUPPORT_EMAIL


def environment(env=None):
    """The environment, "production" or "development": OMNIARMOR_ENV. 1.26.0: AEGIZYN_ENV, which 1.24.0 and 1.25.0
    used, is still read when OMNIARMOR_ENV isn't set, so a server set up then keeps working."""
    env = os.environ if env is None else env
    return (env.get("OMNIARMOR_ENV") or env.get("AEGIZYN_ENV") or "development").strip()


def _hosts(value):
    return tuple(h.strip().lower() for h in (value or "").split(",") if h.strip())


class SettingsError(RuntimeError):
    """A setting is missing or wrong. The message says which and what to do,
    in plain words: it is what the server log shows when the app won't start."""


def _whole(env, name, default):
    value = env.get(name, default)
    try:
        return int(str(value).strip())
    except ValueError:
        raise SettingsError(f"{name} must be a whole number, like {default}. It is set to {value!r}.") from None


def load_config(**overrides):
    env = os.environ
    instance = os.path.join(os.getcwd(), "instance")
    database = env.get("DATABASE_PATH", os.path.join(instance, "omniarmor.db"))
    production = environment(env) == "production"
    cfg = {
        "ENV_NAME": "production" if production else "development",
        "SECRET_KEY": env.get("SECRET_KEY", ""),
        "DATABASE": database,
        "BACKUP_DIR": env.get("BACKUP_DIR", os.path.join(os.path.dirname(os.path.abspath(database)), "backups")),
        "BACKUP_KEEP": _whole(env, "BACKUP_KEEP", "14"),
        # 1.19.0: optional, off unless set. A command that sends each day's checked backup to a second storage
        # provider ({file} is the backup's path), e.g. "rclone copy {file} offsite:omniarmor-backups"
        # (docs/OPERATIONS.md, section 4). The security page says so only once a copy has gone through.
        "OFFSITE_BACKUP_COMMAND": env.get("OFFSITE_BACKUP_COMMAND", "").strip(),
        "BASE_URL": env.get("BASE_URL", "http://localhost:8000").rstrip("/"),
        "SMTP_HOST": env.get("SMTP_HOST", ""),
        "SMTP_PORT": _whole(env, "SMTP_PORT", "587"),
        "SMTP_USER": env.get("SMTP_USER", ""),
        "SMTP_PASSWORD": env.get("SMTP_PASSWORD", ""),
        "SMTP_STARTTLS": _flag("SMTP_STARTTLS", True),
        "MAIL_FROM": env.get("MAIL_FROM", names.MAIL_FROM_DEFAULT),
        "DAILY_JOB_HOUR_UTC": _whole(env, "DAILY_JOB_HOUR_UTC", "11"),
        "SCHEDULER_ENABLED": _flag("SCHEDULER_ENABLED", True),
        # Autopilot fixes small problems itself and emails big ones here.
        "AUTOPILOT_ENABLED": _flag("AUTOPILOT_ENABLED", True),
        "OPERATOR_EMAIL": env.get("OPERATOR_EMAIL", "").strip(),
        # One inbox that gets a short report of each server error (a 500),
        # with no personal data (errormail.py). Unset, none are sent.
        "ERRORS_EMAIL": env.get("ERRORS_EMAIL", "").strip(),
        # The private key the company's console sends to /api/stats (the same
        # value as its MTRX_STATS_KEY) for user counts and daily feature use.
        # Unset, that address does not exist.
        "STATS_KEY": env.get("STATS_KEY", "").strip(),
        # A copy that is not the live one (staging, a demo service) asks to be
        # left out of search results entirely: every address says noindex,
        # robots.txt closes the whole site and the sitemap is empty
        # (docs/STAGING.md). Unset on the live service.
        "NOINDEX": _flag("NOINDEX", False),
        # Where people can write for help, shown on the Help page. Unset, the
        # page names the help inside the app only.
        "SUPPORT_EMAIL": env.get("SUPPORT_EMAIL", "").strip(),
        # Plans (plans.py, where the prices live). The free trial's length, for
        # the whole app (it began as the Academy's trial, hence the name).
        "ACADEMY_TRIAL_DAYS": _whole(env, "ACADEMY_TRIAL_DAYS", "14"),
        # Stripe's price ids: Pro, Plus, and Plus for a Kitchen Safety Bundle
        # workspace (the difference between them), each monthly and yearly.
        # Each is a per-location price in Stripe; checkout sends the location
        # count as quantity. A yearly one left empty: that plan is monthly only.
        "PRO_STRIPE_PRICE": env.get("PRO_STRIPE_PRICE", "").strip(),
        "PLUS_STRIPE_PRICE": env.get("PLUS_STRIPE_PRICE", "").strip(),
        "PLUS_BUNDLE_UPGRADE_STRIPE_PRICE": env.get("PLUS_BUNDLE_UPGRADE_STRIPE_PRICE", "").strip(),
        "PRO_YEARLY_STRIPE_PRICE": env.get("PRO_YEARLY_STRIPE_PRICE", "").strip(),
        "PLUS_YEARLY_STRIPE_PRICE": env.get("PLUS_YEARLY_STRIPE_PRICE", "").strip(),
        "PLUS_BUNDLE_UPGRADE_YEARLY_STRIPE_PRICE": env.get("PLUS_BUNDLE_UPGRADE_YEARLY_STRIPE_PRICE", "").strip(),
        # Classroom plans (plans.py, classrooms.py): the Stripe ids of the
        # yearly Classroom and Whole school prices. Left empty, that plan is
        # offered by invoice only (set by hand: `flask --app wsgi plan`).
        "CLASSROOM_YEARLY_STRIPE_PRICE": env.get("CLASSROOM_YEARLY_STRIPE_PRICE", "").strip(),
        "SCHOOL_YEARLY_STRIPE_PRICE": env.get("SCHOOL_YEARLY_STRIPE_PRICE", "").strip(),
        # The free classroom pilot's length, in days (once per workspace, no card).
        "CLASSROOM_PILOT_DAYS": _whole(env, "CLASSROOM_PILOT_DAYS", "30"),
        # Where a school writes to pay by invoice. Unset, SUPPORT_EMAIL, and
        # without that the company's help address (names.py).
        "SCHOOL_INVOICE_EMAIL": env.get("SCHOOL_INVOICE_EMAIL", "").strip(),
        # The save offer on the cancel screen (plans.py): a Stripe coupon id,
        # and the amount the screen promises, which must match that coupon
        # (by default 25% off the next 2 months, a coupon with percent_off 25,
        # duration "repeating", duration_in_months 2). Each workspace can take
        # it once, ever. No coupon set: no save offer (pausing and cancelling
        # still work).
        "SAVE_OFFER_STRIPE_COUPON": env.get("SAVE_OFFER_STRIPE_COUPON", "").strip(),
        "SAVE_OFFER_PERCENT": _whole(env, "SAVE_OFFER_PERCENT", "25"),
        "SAVE_OFFER_MONTHS": _whole(env, "SAVE_OFFER_MONTHS", "2"),
        "STRIPE_SECRET_KEY": env.get("STRIPE_SECRET_KEY", ""),
        "STRIPE_WEBHOOK_SECRET": env.get("STRIPE_WEBHOOK_SECRET", ""),
        # The secret Kryozyn signs its daily reports with (the same value
        # on both apps). A validly signed report counts toward the Kitchen
        # Safety Bundle's included Pro; unset, reports are still taken but
        # none counts (connections.py).
        "KITCHEN_BUNDLE_SECRET": env.get("KITCHEN_BUNDLE_SECRET", "").strip(),
        # Number of reverse proxies in front of the app (Render, nginx, Caddy add one each).
        "TRUSTED_PROXIES": _whole(env, "TRUSTED_PROXIES", "1" if production else "0"),
        "TESTING": False,
        "SESSION_COOKIE_SECURE": _flag("SESSION_COOKIE_SECURE", production),
        "SESSION_COOKIE_HTTPONLY": True,
        # Lax on purpose: a link in a reminder email opens the app signed in,
        # while a form posted from another site arrives without the cookie
        # (and every form also needs its CSRF token).
        "SESSION_COOKIE_SAMESITE": "Lax",
        # Host-only: no Domain attribute, so the cookie goes back to this
        # exact host and nowhere else. OmniArmor runs on a subdomain of the
        # company's domain, beside its other apps; a cookie scoped to the
        # parent domain would carry an OmniArmor sign-in to every one of them.
        "SESSION_COOKIE_DOMAIN": None,
        "PERMANENT_SESSION_LIFETIME": timedelta(days=14),
        "MAX_CONTENT_LENGTH": 1024 * 1024,
        # 1.24.0: the app's old addresses (names.py, OLD_APP_HOSTS: aegizyn.<domain>, 1.26.0), comma-separated. A page
        # asked for there is sent on, with a permanent redirect, to the same path at BASE_URL's address. Stripe's
        # webhook, Kryozyn's daily report and the health checks are answered there as before, so nothing that
        # posts to the old address breaks (security.py, old_host_redirect). Set it to empty to turn this off.
        "OLD_HOSTS": _hosts(env.get("OLD_HOSTS", ",".join(names.OLD_APP_HOSTS))),
    }
    base_url_given = "BASE_URL" in env or "BASE_URL" in overrides
    cfg.update(overrides)
    if cfg["ENV_NAME"] == "production" and not cfg.get("TESTING"):
        _production_checks(cfg, base_url_given)
    if not cfg["SECRET_KEY"]:
        if cfg["ENV_NAME"] == "production":
            raise SettingsError("SECRET_KEY must be set when OMNIARMOR_ENV=production")
        cfg["SECRET_KEY"] = secrets.token_hex(32)  # development only: sessions reset on restart
    if not 0 <= cfg["DAILY_JOB_HOUR_UTC"] <= 23:
        raise SettingsError("DAILY_JOB_HOUR_UTC must be between 0 and 23")
    if not 1 <= cfg["SAVE_OFFER_PERCENT"] <= 100 or not 1 <= cfg["SAVE_OFFER_MONTHS"] <= 12:
        raise SettingsError("SAVE_OFFER_PERCENT must be 1 to 100 and SAVE_OFFER_MONTHS 1 to 12")
    if not 1 <= cfg["CLASSROOM_PILOT_DAYS"] <= 365:
        raise SettingsError("CLASSROOM_PILOT_DAYS must be between 1 and 365")
    return cfg


def _production_checks(cfg, base_url_given):
    """Settings that, missing or half set in production, would leave the app
    half working: it refuses to start instead, and says what to set. Email
    left out altogether is allowed (reminders are kept on the Reminders
    page; Autopilot and /readyz say so); half of it is not."""
    problems = []
    if not cfg["SECRET_KEY"]:
        problems.append("SECRET_KEY is not set. Set it to a long random value:"
                        " python3 -c \"import secrets; print(secrets.token_hex(32))\" (Render makes one itself).")
    if not base_url_given:
        problems.append("BASE_URL is not set. Set it to the site's address, like"
                        f" {names.APP_URL} (no slash at the end): every link in an email uses it.")
    elif not cfg["BASE_URL"].startswith(("https://", "http://")):
        problems.append(f"BASE_URL must be a full address starting with https://. It is set to {cfg['BASE_URL']!r}.")
    if cfg.get("SMTP_HOST") and "@localhost" in cfg.get("MAIL_FROM", ""):
        problems.append("SMTP_HOST is set but MAIL_FROM is not. Set MAIL_FROM to the address emails come from,"
                        f" like {names.MAIL_FROM_LIVE}.")
    if cfg.get("SMTP_HOST") and cfg.get("SMTP_USER") and not cfg.get("SMTP_PASSWORD"):
        problems.append("SMTP_USER is set but SMTP_PASSWORD is empty. Set the password your email provider gave.")
    if cfg.get("STRIPE_SECRET_KEY") and not cfg.get("STRIPE_WEBHOOK_SECRET"):
        problems.append("STRIPE_SECRET_KEY is set but STRIPE_WEBHOOK_SECRET is not: people could pay and never get"
                        " their plan. Set it to the webhook's signing secret from Stripe (docs/OPERATIONS.md, section 8).")
    if problems:
        raise SettingsError("OmniArmor can't start in production until these settings are fixed:\n- "
                            + "\n- ".join(problems))
