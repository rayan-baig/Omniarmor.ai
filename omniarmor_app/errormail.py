# -*- coding: utf-8 -*-
"""Error reports to one inbox: a short email for each server error (a 500).

Optional. With ERRORS_EMAIL set, a page that fails with an unexpected error
sends that address a short report: the time, the version, the request's
method and path (never its query string), the kind of error, its message and
the stack trace with file paths relative to the project. Off when it is not
set: nothing is written and nothing is sent.

It sits beside Autopilot, it doesn't replace it. autopilot.record_error()
still fingerprints every crash into app_errors, and Autopilot still emails
the operator a summary of new bugs every 10 minutes. This is the immediate
copy, for whoever reads errors, and it uses the same fingerprint
(bugfinder.fingerprint), so one bug is one "distinct error" in both.

No personal data. The report is built only from the exception and the
request's method and path: never the request body, form, cookies, headers,
IP address or the person signed in. The path and the error message are
scrubbed of anything that looks like an email address, an IP address, a
token or a secret, and of reset and invite links (redact.redact).

Rate limited, in the database, so a restart forgets nothing: one email per
distinct error per hour (SAME_ERROR_EVERY), and at most MAX_PER_DAY in any
24 hours. The check and the claim are one write transaction, so several
server processes failing at once still send one email.

Delivered through the outbox like every other email: the report is written
to the notifications table first, then sent from a thread so the error page
isn't held up by the mail server. If the send fails, or the process stops
before it, Autopilot's email retry sends it again later (10 minutes, 1 hour,
6 hours), so mail being down doesn't lose it.
"""

import logging
import os
import re
import threading
import traceback
from datetime import timedelta

from . import bugfinder
from .db import connect, iso, utcnow
from .notify import send_email
from .redact import redact
from .version import __version__

log = logging.getLogger("omniarmor.errormail")

KIND = "error_report"
SAME_ERROR_EVERY = timedelta(hours=1)
MAX_PER_DAY = 20
DAY = timedelta(hours=24)
MAX_FRAMES = 25
# What a queued report says until its first try is done.
WAITING = "Waiting to be sent."

ROOT = os.path.dirname(bugfinder.APP_DIR)

# --- Scrubbing ---------------------------------------------------------------------

_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+(?:@|%40)[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}", re.IGNORECASE)
# "password=...", "token: ...", "Bearer ...": the value goes, the name stays.
_SECRET_VALUE = re.compile(r"\b(token|secret|password|passwd|api[_-]?key|key|session(?:_id)?|cookie|auth\w*)"
                           r"(\s*[:=]\s*)([^\s,;&'\"]+)|\b(bearer)(\s+)(\S+)", re.IGNORECASE)
# A long run of letters and digits with at least one of each: a reset or
# invite token, a session id, a Stripe id, an API key.
_TOKEN = re.compile(r"(?<![A-Za-z0-9_\-])(?=[A-Za-z0-9_\-]*\d)(?=[A-Za-z0-9_\-]*[A-Za-z])[A-Za-z0-9_\-]{16,}"
                    r"(?![A-Za-z0-9_\-])")
_IPV4 = re.compile(r"(?<![\d.])(?:\d{1,3}\.){3}\d{1,3}(?![\d.])")
_IPV6 = re.compile(r"(?<![0-9A-Fa-f:])(?:(?:[0-9A-Fa-f]{1,4}:){3,7}[0-9A-Fa-f]{1,4}|(?:[0-9A-Fa-f]{1,4}:){1,6}:"
                   r"[0-9A-Fa-f]{1,4})(?![0-9A-Fa-f:])")
_SITE_PACKAGES = re.compile(r"(?:[A-Za-z]:)?[\\/][^\s'\"]*?[\\/](?:site|dist)-packages[\\/]")
# Any other absolute path to a Python file, down to the file's name.
_ABSOLUTE_PY = re.compile(r"(?<![\w.])(?:[A-Za-z]:)?(?:[\\/][\w.-]+)*[\\/](?=[\w.-]+\.py\b)")


def scrub(text):
    """Text with anything that looks like an email address, a token, a secret
    or an IP address replaced, and the project's own folder made relative."""
    if not text:
        return ""
    text = redact(str(text))
    text = text.replace(ROOT + os.sep, "")
    text = _SITE_PACKAGES.sub("", text)
    text = _ABSOLUTE_PY.sub("", text)
    text = _EMAIL.sub("[email]", text)
    text = _SECRET_VALUE.sub(lambda m: (m.group(1) or m.group(4)) + (m.group(2) or m.group(5)) + "[hidden]", text)
    text = _TOKEN.sub("[token]", text)
    text = _IPV4.sub("[ip]", text)
    return _IPV6.sub("[ip]", text)


def relative(filename):
    """A stack frame's file, relative: to the project for OmniArmor's own
    code, to site-packages for a library's, the file name alone otherwise."""
    path = os.path.abspath(filename)
    if path.startswith(ROOT + os.sep):
        return os.path.relpath(path, ROOT)
    parts = re.split(r"[\\/](?:site|dist)-packages[\\/]", path, maxsplit=1)
    if len(parts) == 2:
        return parts[1]
    return os.path.basename(path)


# --- The report --------------------------------------------------------------------

def build(exc, method, path, signature, now=None):
    """(subject, body) of the report for one error."""
    now = now or utcnow()
    kind = type(exc).__name__
    message = scrub(str(exc)).strip()[:300] or "(no message)"
    frames = traceback.extract_tb(exc.__traceback__) if exc.__traceback__ else []
    trace = []
    if len(frames) > MAX_FRAMES:
        trace.append(f"  ... {len(frames) - MAX_FRAMES} earlier frames left out")
    for frame in frames[-MAX_FRAMES:]:
        trace.append(f"  {relative(frame.filename)}:{frame.lineno} in {frame.name}")
        if frame.line:
            trace.append(f"    {scrub(frame.line.strip())[:160]}")
    clean_path = scrub(path.split("?", 1)[0])[:200] or "/"
    body = "\n".join([
        "A page failed with a server error.",
        "",
        f"Time: {now.strftime('%Y-%m-%d %H:%M:%S')} UTC",
        f"Version: {__version__}",
        f"Request: {method} {clean_path}",
        f"Error: {kind}",
        f"Message: {message}",
        f"Fingerprint: {signature}",
        "",
        "Stack trace, most recent call last:",
        *(trace or ["  (none)"]),
        "",
        f"The same error is emailed at most once an hour, and no more than {MAX_PER_DAY} errors a day. "
        "Autopilot also lists it with the others: flask --app wsgi autopilot --log",
    ])
    return f"[OmniArmor] Server error: {kind} [{signature}]", body


def _claim(cfg, to, subject, body, signature, now):
    """Writes the report to the outbox if the limits allow it. Returns
    (written, the row id to send now or None). Not written when the same
    error was reported within the hour or the day's limit is reached. One
    write transaction, so two processes can't both claim the same slot."""
    conn = connect(cfg["DATABASE"])
    conn.isolation_level = None
    try:
        conn.execute("BEGIN IMMEDIATE")
        try:
            same = conn.execute("SELECT 1 FROM notifications WHERE kind = ? AND created_at >= ? AND subject LIKE ?"
                                " LIMIT 1", (KIND, iso(now - SAME_ERROR_EVERY), f"%[{signature}]")).fetchone()
            today = conn.execute("SELECT COUNT(*) FROM notifications WHERE kind = ? AND created_at >= ?",
                                 (KIND, iso(now - DAY))).fetchone()[0]
            if same or today >= MAX_PER_DAY:
                conn.execute("ROLLBACK")
                if not same:
                    log.warning("error report not emailed: %d already in the last 24 hours", today)
                return False, None
            # Without SMTP it is kept, like every other email ('logged').
            # With it, it waits as a failed first try (attempts 0) until the
            # thread below sends it, so a stop in between leaves it for
            # Autopilot's retry, not lost.
            queued = bool(cfg.get("SMTP_HOST"))
            row_id = conn.execute(
                "INSERT INTO notifications (org_id, user_id, created_at, kind, recipient, subject, body, status, error,"
                " attempts) VALUES (NULL, NULL, ?, ?, ?, ?, ?, ?, ?, ?)",
                (iso(now), KIND, to, subject, body, "failed" if queued else "logged", WAITING if queued else None,
                 0 if queued else 1)).lastrowid
            conn.execute("COMMIT")
            return True, (row_id if queued else None)
        except Exception:
            conn.execute("ROLLBACK")
            raise
    finally:
        conn.close()


def deliver(cfg, row_id):
    """The first try at sending a queued report. Marks the try before it
    sends, so Autopilot's retry and this never send the same report twice."""
    conn = connect(cfg["DATABASE"])
    try:
        if conn.execute("UPDATE notifications SET attempts = 1 WHERE id = ? AND attempts = 0 AND status = 'failed'",
                        (row_id,)).rowcount != 1:
            conn.commit()
            return None
        conn.commit()
        row = conn.execute("SELECT recipient, subject, body FROM notifications WHERE id = ?", (row_id,)).fetchone()
        status, error = send_email(cfg, row["recipient"], row["subject"], row["body"], kind=KIND)
        conn.execute("UPDATE notifications SET status = ?, error = ? WHERE id = ?",
                     ("sent" if status == "sent" else "failed", error or (None if status == "sent" else WAITING),
                      row_id))
        conn.commit()
        return status
    finally:
        conn.close()


def _start(target, *args):
    """Runs the send beside the request, so a slow mail server never holds up
    the error page. Tests replace this to run it in place."""
    threading.Thread(target=target, args=args, name="omniarmor-error-report", daemon=True).start()


def _deliver_safely(cfg, row_id):
    try:
        deliver(cfg, row_id)
    except Exception:  # Autopilot's retry picks it up
        log.exception("couldn't send an error report")


def report(cfg, exc, method, path):
    """Called for each server error. Returns whether a report was written.
    Does nothing unless ERRORS_EMAIL is set, and never raises: reporting an
    error must not cause another."""
    to = (cfg.get("ERRORS_EMAIL") or "").strip()
    if not to:
        return False
    try:
        signature, _, _ = bugfinder.fingerprint(exc)
        now = utcnow()
        subject, body = build(exc, method, path, signature, now)
        written, row_id = _claim(cfg, to, subject, body, signature, now)
        if row_id is not None:
            _start(_deliver_safely, dict(cfg), row_id)
        return written
    except Exception:
        log.exception("couldn't write an error report")
        return False
