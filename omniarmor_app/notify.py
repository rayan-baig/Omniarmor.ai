# -*- coding: utf-8 -*-
"""Email delivery. Without SMTP settings, messages are kept in the app's
notification log instead of being sent, so nothing is lost."""

import smtplib
import ssl
from email.message import EmailMessage

from .db import now_iso


def send_email(cfg, to, subject, body):
    """Returns (status, error) where status is 'sent', 'logged' or 'failed'."""
    if not cfg.get("SMTP_HOST"):
        return "logged", None
    try:
        msg = EmailMessage()
        msg["From"] = cfg["MAIL_FROM"]
        msg["To"] = to
        msg["Subject"] = " ".join(subject.split())
        msg.set_content(body)
        with smtplib.SMTP(cfg["SMTP_HOST"], cfg["SMTP_PORT"], timeout=20) as smtp:
            if cfg.get("SMTP_STARTTLS", True):
                smtp.starttls(context=ssl.create_default_context())
            if cfg.get("SMTP_USER"):
                smtp.login(cfg["SMTP_USER"], cfg["SMTP_PASSWORD"])
            smtp.send_message(msg)
        return "sent", None
    except (OSError, smtplib.SMTPException, ValueError) as exc:
        return "failed", f"{type(exc).__name__}: {exc}"[:300]


def notify(conn, cfg, kind, recipient, subject, body, org_id=None, user_id=None):
    status, error = send_email(cfg, recipient, subject, body)
    conn.execute(
        "INSERT INTO notifications (org_id, user_id, created_at, kind, recipient, subject, body, status, error)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (org_id, user_id, now_iso(), kind, recipient, subject, body, status, error),
    )
    conn.commit()
    return status
