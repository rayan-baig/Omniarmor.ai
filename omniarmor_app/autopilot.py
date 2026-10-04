# -*- coding: utf-8 -*-
"""Autopilot: keeps OmniArmor running without someone checking it every day.

Every 10 minutes it looks the service over. Small problems it fixes on its own
and writes down: failed emails are sent again, a missed backup is made, old
logs are trimmed. Big problems, the ones a person has to decide on, are
emailed to the operator (OPERATOR_EMAIL) once, with what is wrong and what to
do. While a big problem lasts it sends one reminder a day, and when it clears
up it says so. Once a week it sends a short report, but only
if something happened.

It is also a bug finder (bugfinder.py): every crash is fingerprinted and a new
one is emailed the first time it happens, and once a day it runs a self-test of
the whole app on a throwaway database and checks the Academy's quizzes and the
data for things that should never happen.

    flask --app wsgi autopilot          run the checks now and print what it found
    flask --app wsgi autopilot --log    show what it fixed and reported lately
"""

import glob
import logging
import os
import shutil
from dataclasses import dataclass
from datetime import timedelta

from . import bugfinder
from .db import connect, iso, migrate, now_iso, utcnow
from .notify import send_email

log = logging.getLogger("omniarmor.autopilot")

EMAIL_RETRY_AFTER = [timedelta(minutes=10), timedelta(hours=1), timedelta(hours=6)]  # after attempt 1, 2, 3
EMAIL_RETRY_WINDOW = timedelta(days=2)
EMAIL_FAILURES_ALERT = 3        # emails still failing after every retry, in a day
BUG_WINDOW = timedelta(hours=24)  # a bug counts as fixed once it hasn't happened for this long
BACKUP_MAX_AGE = timedelta(hours=26)
DAILY_JOB_MAX_AGE = timedelta(hours=50)
DISK_MIN_FREE = 1024 ** 3       # 1 GB
DISK_MIN_SHARE = 0.05
WAL_CHECKPOINT_BYTES = 64 * 1024 ** 2
REMIND_AFTER = timedelta(hours=24)
KEEP_ERRORS = timedelta(days=30)
KEEP_EVENTS = timedelta(days=180)
SLOT_MINUTES = 10


@dataclass
class Finding:
    key: str            # one per kind of problem, so it is reported once, not every 10 minutes
    title: str
    detail: str = ""
    action: str = ""    # what the operator should do


# --- Small problems: fixed automatically ---------------------------------------------

def retry_failed_emails(conn, cfg):
    """Sends failed emails again, waiting longer after each try. Returns how many went out."""
    if not cfg.get("SMTP_HOST"):
        return 0
    now = utcnow()
    rows = conn.execute("SELECT * FROM notifications WHERE status = 'failed' AND attempts <= ? AND created_at >= ?",
                        (len(EMAIL_RETRY_AFTER), iso(now - EMAIL_RETRY_WINDOW))).fetchall()
    sent = 0
    for row in rows:
        due = _parse(row["created_at"]) + sum(EMAIL_RETRY_AFTER[:row["attempts"]], timedelta())
        if due > now:
            continue
        status, error = send_email(cfg, row["recipient"], row["subject"], row["body"])
        conn.execute("UPDATE notifications SET status = ?, error = ?, attempts = attempts + 1 WHERE id = ?",
                     (status if status != "logged" else "failed", error or row["error"], row["id"]))
        conn.commit()
        sent += status == "sent"
    return sent


def latest_backup(cfg):
    copies = sorted(glob.glob(os.path.join(cfg["BACKUP_DIR"], "omniarmor-*.db")))
    return copies[-1] if copies else None


def backup_age(cfg):
    newest = latest_backup(cfg)
    if newest is None:
        return None
    return utcnow().timestamp() - os.path.getmtime(newest)


def make_missing_backup(cfg):
    """Makes a backup if the newest one is too old. Returns the new file, or None if none was needed."""
    from .jobs import backup_database
    if cfg["DATABASE"] == ":memory:" or not _has_daily_history(cfg):
        return None
    age = backup_age(cfg)
    if age is not None and age < BACKUP_MAX_AGE.total_seconds():
        return None
    return backup_database(cfg)


def tidy(conn, cfg):
    """Trims old logs and keeps the database file compact. Returns what it did, or ''."""
    conn.execute("DELETE FROM app_errors WHERE at < ?", (iso(utcnow() - KEEP_ERRORS),))
    conn.execute("DELETE FROM autopilot_events WHERE at < ?", (iso(utcnow() - KEEP_EVENTS),))
    conn.execute("DELETE FROM job_runs WHERE job = 'autopilot' AND run_date < ?",
                 (iso(utcnow() - timedelta(days=2)),))
    conn.commit()
    done = ""
    wal = cfg["DATABASE"] + "-wal"
    if cfg["DATABASE"] != ":memory:" and os.path.exists(wal) and os.path.getsize(wal) > WAL_CHECKPOINT_BYTES:
        size = os.path.getsize(wal)
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        done = f"Compacted the database log ({size // 1024 ** 2} MB)."
    conn.execute("PRAGMA optimize")
    return done


# --- Big problems: sent to the operator ------------------------------------------------

def find_problems(conn, cfg, deep=False):
    """Everything that needs a person right now. deep=True adds the slower daily checks."""
    found = []
    now = utcnow()

    if cfg["DATABASE"] != ":memory:" and _has_daily_history(cfg):
        age = backup_age(cfg)
        if age is None or age > BACKUP_MAX_AGE.total_seconds() + 3600:
            when = "no backup exists yet" if age is None else f"the newest is {int(age // 3600)} hours old"
            found.append(Finding("backup", "Backups are failing",
                                 f"Autopilot tried to make one and couldn't: {when}. Backup folder: {cfg['BACKUP_DIR']}.",
                                 "Check that the backup folder exists, is writable and has free space. "
                                 "Run: flask --app wsgi backup"))

    last = conn.execute("SELECT MAX(finished_at) FROM job_runs WHERE job = 'daily'").fetchone()[0]
    if last and _parse(last) < now - DAILY_JOB_MAX_AGE:
        found.append(Finding("daily-job", "The daily job hasn't finished in 2 days",
                             f"Last finished {last}. Reminders and backups may not be going out.",
                             "Check the server log for 'daily job had failures', then run: "
                             "flask --app wsgi run-daily --force"))

    stuck = conn.execute("SELECT COUNT(*), MAX(error) FROM notifications WHERE status = 'failed' AND attempts > ?"
                         " AND created_at >= ?", (len(EMAIL_RETRY_AFTER), iso(now - timedelta(days=1)))).fetchone()
    if stuck[0] >= EMAIL_FAILURES_ALERT:
        found.append(Finding("email", f"{stuck[0]} emails failed even after {len(EMAIL_RETRY_AFTER)} retries",
                             f"Last error: {stuck[1] or 'unknown'}. Customers may be missing reminders.",
                             "Check the SMTP settings and your email provider's dashboard (sending limits, "
                             "a changed password, an unverified sender)."))
    if cfg.get("ENV_NAME") == "production" and not cfg.get("SMTP_HOST"):
        found.append(Finding("email-off", "Email is not set up",
                             "Reminders and password resets are being saved, not sent.",
                             "Set SMTP_HOST, SMTP_USER and SMTP_PASSWORD (see docs/OPERATIONS.md, section 2)."))

    bugs, more = bugfinder.new_bugs(conn, iso(now - BUG_WINDOW))
    for signature, count, location, error, paths, trace, first in bugs:
        times = "once" if count == 1 else f"{count} times"
        found.append(Finding(f"bug:{signature}", f"Bug: {error[:90]}",
                             f"Happened {times} in the last day, on {', '.join(paths)}. First seen {first}.\n"
                             f"Where: {location}\n\nTraceback (end):\n{_tail(trace, 14)}",
                             f"Fix the code at {location} and deploy. You'll get a 'Fixed' email once it "
                             f"hasn't happened for a day."))
    if more:
        found.append(Finding("bugs-more", f"{more} more bugs happened today",
                             "Run: flask --app wsgi autopilot --log to see the server errors.",
                             "Fix the ones above first; these are less frequent."))

    if cfg["DATABASE"] != ":memory:":
        usage = shutil.disk_usage(os.path.dirname(os.path.abspath(cfg["DATABASE"])))
        if usage.free < DISK_MIN_FREE or usage.free < usage.total * DISK_MIN_SHARE:
            found.append(Finding("disk", "The server is running out of disk space",
                                 f"{usage.free / 1024 ** 3:.1f} GB free of {usage.total / 1024 ** 3:.0f} GB.",
                                 "Make the disk bigger, or lower BACKUP_KEEP so fewer old backups are kept."))

    if deep:
        try:
            bugfinder.self_test()
        except bugfinder.SelfTestFailure as failure:
            found.append(Finding("selftest", f"Daily self-test failed at: {failure.step}", failure.detail,
                                 "Something people use every day is broken. Try it yourself, check the latest "
                                 "deploy and roll it back if needed."))
        except Exception as exc:
            _, location, _ = bugfinder.fingerprint(exc)
            found.append(Finding("selftest", "The daily self-test itself crashed",
                                 f"{type(exc).__name__}: {exc} ({location})", "Look at the server log."))
        content = bugfinder.check_content()
        if content:
            found.append(Finding("content", f"{len(content)} broken Academy quiz{'zes' if len(content) != 1 else ''}",
                                 "\n".join(content[:10]), "Fix the question bank or quiz code, then run the tests."))
        data = bugfinder.data_problems(conn)
        if data:
            found.append(Finding("data", "The database has records that don't add up", "\n".join(data),
                                 "Look at these rows before they cause errors on a page."))
        result = conn.execute("PRAGMA quick_check").fetchone()[0]
        if result != "ok":
            found.append(Finding("database", "The database reports damage",
                                 f"SQLite quick_check said: {result[:300]}",
                                 "Stop the app and restore the newest good backup (docs/OPERATIONS.md, section 4)."))
    return found


# --- Bookkeeping and email -------------------------------------------------------------

def _tail(text, lines):
    return "\n".join((text or "").strip().splitlines()[-lines:])


def _parse(text):
    from datetime import datetime
    return datetime.fromisoformat(text)


def _has_daily_history(cfg):
    """Backups are only expected once the daily job has run at least once."""
    conn = connect(cfg["DATABASE"])
    try:
        return conn.execute("SELECT 1 FROM job_runs WHERE job = 'daily' AND finished_at IS NOT NULL LIMIT 1").fetchone() is not None
    finally:
        conn.close()


def record(conn, key, level, title, detail="", emailed=False):
    conn.execute("INSERT INTO autopilot_events (at, check_key, level, title, detail, emailed) VALUES (?, ?, ?, ?, ?, ?)",
                 (now_iso(), key, level, title, detail, int(emailed)))
    conn.commit()


def open_alerts(conn):
    """Problems reported and not cleared yet: key -> the latest alert row."""
    rows = conn.execute("SELECT e.* FROM autopilot_events e JOIN (SELECT check_key, MAX(id) AS id FROM autopilot_events"
                        " WHERE level IN ('alert', 'resolved') GROUP BY check_key) last ON last.id = e.id"
                        " WHERE e.level = 'alert'").fetchall()
    return {r["check_key"]: r for r in rows}


def tell_operator(cfg, subject, body):
    """Emails the operator. Without OPERATOR_EMAIL (or SMTP) it goes to the server log instead."""
    to = cfg.get("OPERATOR_EMAIL")
    if not to or not cfg.get("SMTP_HOST"):
        log.error("AUTOPILOT: %s\n%s", subject, body)
        return False
    status, error = send_email(cfg, to, f"[OmniArmor] {subject}", body + _FOOTER.format(base=cfg["BASE_URL"]))
    if status != "sent":
        log.error("AUTOPILOT: couldn't email %s (%s): %s\n%s", to, error, subject, body)
    return status == "sent"


_FOOTER = "\n\n--\nSent by OmniArmor Autopilot at {base}. It fixes small problems by itself and only emails you about these."


def _alert_body(f):
    return f"{f.title}\n\n{f.detail}\n\nWhat to do: {f.action}"


def report(conn, cfg, found):
    """Emails new problems, reminds about old ones once a day, and announces fixes."""
    now = utcnow()
    current = {f.key: f for f in found}
    already = open_alerts(conn)
    for key, f in current.items():
        previous = already.get(key)
        if previous is None:
            emailed = tell_operator(cfg, f.title, _alert_body(f))
            record(conn, key, "alert", f.title, _alert_body(f), emailed)
        elif _parse(previous["at"]) < now - REMIND_AFTER:
            emailed = tell_operator(cfg, "Still open: " + f.title, _alert_body(f))
            record(conn, key, "alert", f.title, _alert_body(f), emailed)
    for key, previous in already.items():
        if key not in current:
            title = "Fixed: " + previous["title"]
            emailed = tell_operator(cfg, title, "This has cleared up" + (" (it hasn't happened for a day)"
                                    if key.startswith("bug:") else "") + ". Nothing more to do.")
            record(conn, key, "resolved", title, "", emailed)


def weekly_summary(conn, cfg):
    """A short Monday note, only when Autopilot did something that week."""
    since = iso(utcnow() - timedelta(days=7))
    rows = conn.execute("SELECT level, title FROM autopilot_events WHERE at >= ? ORDER BY id", (since,)).fetchall()
    if not rows:
        return False
    fixed = [r["title"] for r in rows if r["level"] == "fixed"]
    alerts = open_alerts(conn)
    lines = [f"This week Autopilot fixed {len(fixed)} small thing{'s' if len(fixed) != 1 else ''} on its own."]
    lines += [f"  - {t}" for t in fixed[:15]]
    if len(fixed) > 15:
        lines.append(f"  ...and {len(fixed) - 15} more.")
    lines.append("")
    lines.append("Open problems: none. Everything is running." if not alerts else
                 "Still needs you:\n" + "\n".join(f"  - {a['title']}" for a in alerts.values()))
    return tell_operator(cfg, "Weekly Autopilot report", "\n".join(lines))


# --- The run --------------------------------------------------------------------------

def run(cfg, force=False):
    """One Autopilot pass. Several server processes can call this; only one runs per 10-minute slot."""
    from .jobs import claim_run, finish_run
    now = utcnow()
    slot = now.replace(minute=now.minute - now.minute % SLOT_MINUTES, second=0, microsecond=0)
    conn = connect(cfg["DATABASE"])
    try:
        migrate(conn)
        if not claim_run(conn, "autopilot", iso(slot)) and not force:
            return None
        fixed = []
        sent = _safely("email retry", retry_failed_emails, conn, cfg)
        if sent:
            fixed.append(f"Re-sent {sent} email{'s' if sent != 1 else ''} that failed the first time.")
        made = _safely("backup", make_missing_backup, cfg)  # if it fails, the backup check below reports it
        if made:
            fixed.append(f"Made a missing backup: {os.path.basename(made)}.")
        daily = claim_run(conn, "autopilot-daily", now.date().isoformat()) or force
        if daily:
            done = _safely("tidy", tidy, conn, cfg)
            if done:
                fixed.append(done)
            fixed += _safely("data repair", bugfinder.repair_data, conn) or []
        for title in fixed:
            record(conn, "fix", "fixed", title)
            log.info("autopilot fixed: %s", title)
        found = find_problems(conn, cfg, deep=daily)
        report(conn, cfg, found)
        if daily and now.weekday() == 0:
            weekly_summary(conn, cfg)
        if daily:
            finish_run(conn, "autopilot-daily", now.date().isoformat(), f"open={len(found)}")
        result = f"fixed={len(fixed)} open={len(found)}"
        finish_run(conn, "autopilot", iso(slot), result)
        return {"fixed": fixed, "problems": found}
    finally:
        conn.close()


def _safely(name, step, *args):
    """Runs one step; a failing step is logged and the rest of the pass still runs."""
    try:
        return step(*args)
    except Exception:
        log.exception("autopilot step %r failed", name)
        return None


def record_error(cfg, path, exc):
    """Called when a page fails with a server error. Each one is fingerprinted so
    Autopilot can tell a new bug from one it already reported."""
    try:
        signature, location, trace = bugfinder.fingerprint(exc)
        conn = connect(cfg["DATABASE"])
        try:
            conn.execute("INSERT INTO app_errors (at, path, error, signature, location, trace) VALUES (?, ?, ?, ?, ?, ?)",
                         (now_iso(), path[:200], f"{type(exc).__name__}: {exc}"[:300], signature, location, trace))
            conn.commit()
        finally:
            conn.close()
    except Exception:  # never let error bookkeeping cause another error
        log.exception("couldn't record a server error")
