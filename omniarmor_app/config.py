# -*- coding: utf-8 -*-
"""Settings, read from environment variables. See .env.example and docs/OPERATIONS.md."""

import os
import secrets
from datetime import timedelta


def _flag(name, default):
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in ("1", "true", "yes", "on")


def load_config(**overrides):
    env = os.environ
    instance = os.path.join(os.getcwd(), "instance")
    database = env.get("DATABASE_PATH", os.path.join(instance, "omniarmor.db"))
    production = env.get("OMNIARMOR_ENV", "development") == "production"
    cfg = {
        "ENV_NAME": "production" if production else "development",
        "SECRET_KEY": env.get("SECRET_KEY", ""),
        "DATABASE": database,
        "BACKUP_DIR": env.get("BACKUP_DIR", os.path.join(os.path.dirname(os.path.abspath(database)), "backups")),
        "BACKUP_KEEP": int(env.get("BACKUP_KEEP", "14")),
        "BASE_URL": env.get("BASE_URL", "http://localhost:8000").rstrip("/"),
        "SMTP_HOST": env.get("SMTP_HOST", ""),
        "SMTP_PORT": int(env.get("SMTP_PORT", "587")),
        "SMTP_USER": env.get("SMTP_USER", ""),
        "SMTP_PASSWORD": env.get("SMTP_PASSWORD", ""),
        "SMTP_STARTTLS": _flag("SMTP_STARTTLS", True),
        "MAIL_FROM": env.get("MAIL_FROM", "OmniArmor <no-reply@localhost>"),
        "DAILY_JOB_HOUR_UTC": int(env.get("DAILY_JOB_HOUR_UTC", "11")),
        "SCHEDULER_ENABLED": _flag("SCHEDULER_ENABLED", True),
        # Autopilot fixes small problems itself and emails big ones here.
        "AUTOPILOT_ENABLED": _flag("AUTOPILOT_ENABLED", True),
        "OPERATOR_EMAIL": env.get("OPERATOR_EMAIL", "").strip(),
        # The Academy's own subscription (separate from the compliance service).
        "ACADEMY_TRIAL_DAYS": int(env.get("ACADEMY_TRIAL_DAYS", "14")),
        "ACADEMY_PRICE_LABEL": env.get("ACADEMY_PRICE_LABEL", ""),
        "ACADEMY_STRIPE_PRICE": env.get("ACADEMY_STRIPE_PRICE", ""),
        "STRIPE_SECRET_KEY": env.get("STRIPE_SECRET_KEY", ""),
        "STRIPE_WEBHOOK_SECRET": env.get("STRIPE_WEBHOOK_SECRET", ""),
        # Number of reverse proxies in front of the app (Render, nginx, Caddy add one each).
        "TRUSTED_PROXIES": int(env.get("TRUSTED_PROXIES", "1" if production else "0")),
        "TESTING": False,
        "SESSION_COOKIE_SECURE": _flag("SESSION_COOKIE_SECURE", production),
        "SESSION_COOKIE_HTTPONLY": True,
        "SESSION_COOKIE_SAMESITE": "Lax",
        "PERMANENT_SESSION_LIFETIME": timedelta(days=14),
        "MAX_CONTENT_LENGTH": 1024 * 1024,
    }
    cfg.update(overrides)
    if not cfg["SECRET_KEY"]:
        if cfg["ENV_NAME"] == "production":
            raise RuntimeError("SECRET_KEY must be set when OMNIARMOR_ENV=production")
        cfg["SECRET_KEY"] = secrets.token_hex(32)  # development only: sessions reset on restart
    if not 0 <= cfg["DAILY_JOB_HOUR_UTC"] <= 23:
        raise RuntimeError("DAILY_JOB_HOUR_UTC must be between 0 and 23")
    return cfg
