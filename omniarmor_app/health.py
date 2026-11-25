# -*- coding: utf-8 -*-
"""Is OmniArmor working? Two answers, for an uptime monitor.

- /healthz: the server answers and its database opens (cheap: one query).
- /readyz: everything behind the pages works too: the database, the
  settings production needs, the two background timers (the minute alerts,
  and the daily job with Autopilot) still running, the last daily job, the
  newest backup and the disk. 200 when all is well, 503 when something
  needs a person.

Both answer anyone, so they say only "ok" or "fail" per check: never a
setting's value, a version of anything, a file path or anyone's data. The
details are for the owner, on the server: `flask --app wsgi ready`.

The timers write their "last ran at" here (beat) every time they run, in the
database, so any server process can tell whether some process is running
them. A timer that stops (its thread stuck, the process unable to write)
stops beating, and /readyz fails within minutes.
"""

import os
import shutil
import sqlite3
import threading
import time
import urllib.parse
from datetime import datetime, timedelta

from .db import SCHEMA_VERSION, connect, iso, utcnow

# How old a timer's last beat may be before it counts as stopped: a few of
# its rounds (the alerts run every minute, the daily timer every 10 minutes).
STALE = {"alerts": timedelta(minutes=5), "daily": timedelta(minutes=30)}
# A process that has just started hasn't run its timers yet.
STARTING = timedelta(minutes=3)
# The readiness answer is kept this long, so a monitor (or anyone) asking
# often costs a few queries at most every few seconds.
CACHE_SECONDS = 10

# What each check means, and what to do, for `flask --app wsgi ready` and the docs.
EXPLAIN = {
    "database": ("The database can't be read, or its schema is not this version's.",
                 "Check the disk is attached and not full, then restart the app. Section 4 of"
                 " docs/OPERATIONS.md restores a backup if the file is damaged."),
    "settings": ("A setting production needs is missing.",
                 "Run `flask --app wsgi ready` on the server: it names the setting. See docs/OPERATIONS.md."),
    "alerts_timer": ("The every-minute timer (time-limit alerts) hasn't run in over 5 minutes.",
                     "Restart the app. If it stops again, look in the server log for 'time-limit alerts failed'."),
    "daily_timer": ("The every-10-minutes timer (the daily job and Autopilot) hasn't run in over 30 minutes.",
                    "Restart the app. If it stops again, look in the server log for 'daily job' or 'autopilot'."),
    "daily_job": ("The daily job (reminders, cleanup, backup) hasn't finished in over 2 days.",
                  "Look in the server log for 'daily job had failures', then run"
                  " `flask --app wsgi run-daily --force`."),
    "backup": ("The newest backup is over 2 days old.",
               "Run `flask --app wsgi backup` and read what it says (often: the disk is full)."),
    "disk": ("The server is almost out of disk space.",
             "Make the disk bigger, or lower BACKUP_KEEP so fewer old backups are kept."),
}

_started = time.monotonic()
_cache = {"at": None, "answer": None}
_cache_lock = threading.Lock()


def beat(cfg, name, now=None):
    """Records that the timer `name` ran just now. Never raises: a timer
    must keep running even if this one write fails (it then looks stopped,
    which is the truth worth telling)."""
    if cfg["DATABASE"] == ":memory:":
        return
    stamp = iso(now or utcnow())
    try:
        conn = connect(cfg["DATABASE"])
        try:
            conn.execute("INSERT INTO job_heartbeats (name, beat_at, started_at) VALUES (?, ?, ?)"
                         " ON CONFLICT (name) DO UPDATE SET beat_at = excluded.beat_at", (name, stamp, stamp))
            conn.commit()
        finally:
            conn.close()
    except Exception:
        import logging
        logging.getLogger("omniarmor.health").exception("couldn't record the %s timer's heartbeat", name)


def _parse(text):
    return datetime.fromisoformat(text) if text else None


def timer_state(conn, cfg, name, now=None, grace=True):
    """'ok', 'fail' or 'off' for one background timer. A sweep holding its
    lock counts as running (a long daily run beats only between rounds).
    grace: a server process that started minutes ago hasn't run it yet."""
    now = now or utcnow()
    row = conn.execute("SELECT beat_at FROM job_heartbeats WHERE name = ?", (name,)).fetchone()
    last = _parse(row[0]) if row else None
    if last is not None and now - last <= STALE[name]:
        return "ok"
    locks = ("alerts",) if name == "alerts" else ("daily", "autopilot")
    held = conn.execute(f"SELECT COUNT(*) FROM job_locks WHERE name IN ({','.join('?' * len(locks))})"
                        " AND expires_at >= ?", (*locks, iso(now))).fetchone()[0]
    if held:
        return "ok"
    if last is None and not cfg.get("SCHEDULER_ENABLED", True):
        return "off"    # turned off on purpose, and no other process runs it either
    if grace and time.monotonic() - _started < STARTING.total_seconds():
        return "ok"     # just started: its first round is on its way
    return "fail"


def _read_only(path):
    """A connection that only reads: a check must never make an empty
    database where the real one should be (a disk that didn't attach)."""
    if path == ":memory:":
        return connect(path)
    conn = sqlite3.connect(f"file:{urllib.parse.quote(os.path.abspath(path))}?mode=ro", uri=True, timeout=5)
    conn.row_factory = sqlite3.Row
    return conn


def settings_problems(cfg):
    """The settings production needs that are missing, in plain words. Only
    for the owner (`flask --app wsgi ready`), never for the public page."""
    if cfg.get("ENV_NAME") != "production":
        return []
    problems = []
    if not cfg.get("SMTP_HOST"):
        problems.append("SMTP_HOST is empty: reminders and password resets are saved, not emailed"
                        " (docs/OPERATIONS.md, section 2).")
    if "localhost" in (cfg.get("BASE_URL") or "") or "127.0.0.1" in (cfg.get("BASE_URL") or ""):
        problems.append("BASE_URL points at this computer: links in emails won't open for anyone"
                        " (docs/OPERATIONS.md, section 1).")
    return problems


def checks(cfg, now=None, grace=True):
    """Every check, each 'ok', 'fail' or 'off'. Fast: a handful of small
    queries, a directory listing and a disk-space call."""
    from . import autopilot
    now = now or utcnow()
    found = {name: "ok" for name in EXPLAIN}
    timer_since = None
    found["settings"] = "fail" if settings_problems(cfg) else "ok"
    try:
        conn = _read_only(cfg["DATABASE"])
    except Exception:
        return dict(found, database="fail", alerts_timer="fail", daily_timer="fail", daily_job="fail")
    try:
        version = conn.execute("SELECT MAX(version) FROM schema_version").fetchone()[0]
        found["database"] = "ok" if version == SCHEMA_VERSION else "fail"
        for name in ("alerts", "daily"):
            found[f"{name}_timer"] = timer_state(conn, cfg, name, now, grace)
        last = conn.execute("SELECT MAX(finished_at) FROM job_runs WHERE job = 'daily'").fetchone()[0]
        started = conn.execute("SELECT started_at FROM job_heartbeats WHERE name = 'daily'").fetchone()
        # Since the last finished run, or since the daily timer first ran on
        # a new database that has never finished one.
        timer_since = _parse(started[0]) if started else None
        since = _parse(last) or timer_since
        if since is not None and now - since > autopilot.DAILY_JOB_MAX_AGE:
            found["daily_job"] = "fail"
        elif found["daily_timer"] == "off" and last is None:
            found["daily_job"] = "off"
    except Exception:
        found.update(database="fail", alerts_timer="fail", daily_timer="fail", daily_job="fail")
    finally:
        conn.close()
    if cfg["DATABASE"] != ":memory:":
        try:
            age = autopilot.backup_age(cfg)
            limit = autopilot.DAILY_JOB_MAX_AGE
            # None yet is fine until the daily timer has had 2 days to make the first one.
            if (age is None and timer_since is not None and now - timer_since > limit) or \
                    (age is not None and age > limit.total_seconds()):
                found["backup"] = "fail"
        except OSError:
            found["backup"] = "fail"
        try:
            usage = shutil.disk_usage(os.path.dirname(os.path.abspath(cfg["DATABASE"])))
            if usage.free < autopilot.DISK_MIN_FREE or usage.free < usage.total * autopilot.DISK_MIN_SHARE:
                found["disk"] = "fail"
        except OSError:
            found["disk"] = "fail"
    else:
        found["backup"] = found["disk"] = "off"
    return found


def readiness(cfg):
    """(answer, HTTP status) for /readyz, kept CACHE_SECONDS."""
    with _cache_lock:
        if _cache["at"] is not None and time.monotonic() - _cache["at"] < CACHE_SECONDS:
            return _cache["answer"]
        found = checks(cfg)
        ok = "fail" not in found.values()
        answer = ({"status": "ok" if ok else "fail", "checks": found}, 200 if ok else 503)
        _cache.update(at=time.monotonic(), answer=answer)
        return answer


def forget():
    """Drops the kept answer (tests, and `flask --app wsgi ready`)."""
    with _cache_lock:
        _cache.update(at=None, answer=None)
