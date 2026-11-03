# -*- coding: utf-8 -*-
"""The work that runs by itself: every day reminders, a database backup and
cleanup; every minute the time-limit alerts for the hour and minute clocks.
Autopilot (autopilot.py) runs every 10 minutes beside the daily job. A
built-in timer runs it all, in two threads: one for the minute alerts, one for
the daily job and Autopilot, so a long daily run (thousands of digests through
a slow email provider) never holds the alerts up.

Several server processes can run the timer safely. Each sweep holds a lock in
the database while it runs (job_lock), so no two processes run the same sweep
at once however long it takes; each day's run is also claimed in the
database, and each alert is claimed before it is sent."""

import glob
import logging
import os
import sqlite3
import threading
import time
import uuid
from contextlib import contextmanager
from datetime import timedelta

import click

from . import usage
from .db import connect, iso, migrate, now_iso, utcnow
from .reminders import run_clock_alerts, run_reminders

log = logging.getLogger("omniarmor.jobs")
CHECK_EVERY_SECONDS = 600   # the daily job's check and Autopilot
ALERTS_EVERY_SECONDS = 60   # the time-limit alerts: the shortest clock is 15 minutes, due to the minute
STALE_AFTER = timedelta(hours=1)
# A sweep's lock (job_lock) is a lease this long, renewed every
# LOCK_RENEW_SECONDS while the sweep runs: a process that dies mid-sweep
# loses it within LOCK_LEASE, and another process takes the work over.
LOCK_LEASE = timedelta(minutes=2)
LOCK_RENEW_SECONDS = 20


def _take_lock(conn, name, holder):
    now = utcnow()
    cur = conn.execute(
        "INSERT INTO job_locks (name, holder, taken_at, expires_at) VALUES (?, ?, ?, ?)"
        " ON CONFLICT (name) DO UPDATE SET holder = excluded.holder, taken_at = excluded.taken_at,"
        " expires_at = excluded.expires_at WHERE job_locks.expires_at < ?",
        (name, holder, iso(now), iso(now + LOCK_LEASE), iso(now)),
    )
    conn.commit()
    return cur.rowcount == 1


@contextmanager
def job_lock(cfg, name):
    """Holds the database lock for one sweep while the block runs. Yields
    True when this process has it, False when another process is running the
    same sweep right now (the caller then skips it).

    A day's run used to be claimed with a time stamp that went stale after an
    hour, and an Autopilot pass per 10-minute slot: a daily run that took
    longer than an hour (thousands of digests through a slow email provider),
    or a pass that took longer than 10 minutes (failed emails re-sent to a
    provider that times out), let a second process start the same work beside
    it and send the same emails again. The lock is renewed for as long as the
    sweep runs, by a thread of its own, and let go at the end."""
    if cfg["DATABASE"] == ":memory:":
        yield True
        return
    holder = uuid.uuid4().hex
    conn = connect(cfg["DATABASE"])
    try:
        migrate(conn)   # the lock's table, on a database no app has opened yet
        if not _take_lock(conn, name, holder):
            yield False
            return
        stop = threading.Event()

        def renew():
            keeper = connect(cfg["DATABASE"])
            try:
                while not stop.wait(LOCK_RENEW_SECONDS):
                    try:
                        keeper.execute("UPDATE job_locks SET expires_at = ? WHERE name = ? AND holder = ?",
                                       (iso(utcnow() + LOCK_LEASE), name, holder))
                        keeper.commit()
                    except Exception:  # try again at the next renewal; the lease has room for it
                        log.exception("couldn't renew the %s lock", name)
            finally:
                keeper.close()

        renewer = threading.Thread(target=renew, name=f"omniarmor-lock-{name}", daemon=True)
        renewer.start()
        try:
            yield True
        finally:
            stop.set()
            renewer.join()
            conn.execute("DELETE FROM job_locks WHERE name = ? AND holder = ?", (name, holder))
            conn.commit()
    finally:
        conn.close()


def claim_run(conn, job, run_date):
    """Claims today's run. A run that started over an hour ago and never finished
    (the server restarted mid-run) can be claimed again."""
    cur = conn.execute(
        "INSERT OR IGNORE INTO job_runs (job, run_date, started_at) VALUES (?, ?, ?)",
        (job, run_date, now_iso()),
    )
    if cur.rowcount != 1:
        cur = conn.execute(
            "UPDATE job_runs SET started_at = ? WHERE job = ? AND run_date = ? AND finished_at IS NULL AND started_at < ?",
            (now_iso(), job, run_date, iso(utcnow() - STALE_AFTER)),
        )
    conn.commit()
    return cur.rowcount == 1


def release_run(conn, job, run_date):
    conn.execute("DELETE FROM job_runs WHERE job = ? AND run_date = ? AND finished_at IS NULL", (job, run_date))
    conn.commit()


def finish_run(conn, job, run_date, result):
    conn.execute("UPDATE job_runs SET finished_at = ?, result = ? WHERE job = ? AND run_date = ?",
                 (now_iso(), result[:500], job, run_date))
    conn.commit()


def backup_database(cfg, fresh=False):
    """Copies the live database safely (SQLite online backup) and keeps the newest BACKUP_KEEP copies.

    The automatic runs keep one copy a day (see below); `fresh` makes a new
    one regardless, for somebody asking for a backup by hand."""
    if cfg["DATABASE"] == ":memory:":
        return None
    os.makedirs(cfg["BACKUP_DIR"], exist_ok=True)
    # One backup a day. When the daily job fails part-way it runs again ten
    # minutes later, and every run used to take another backup and prune by
    # count, so a job failing all afternoon pushed every earlier day's copy
    # out: one company whose reminders kept failing wiped the restore history
    # of every customer. Today's copy is kept once made.
    today = utcnow().strftime("%Y%m%d")
    existing = sorted(glob.glob(os.path.join(cfg["BACKUP_DIR"], f"omniarmor-{today}-*.db")))
    if existing and not fresh:
        return existing[-1]
    _remove_stale_partials(cfg["BACKUP_DIR"])
    dest = os.path.join(cfg["BACKUP_DIR"], f"omniarmor-{utcnow().strftime('%Y%m%d-%H%M%S-%f')}.db")
    # Written under another name and only named omniarmor-*.db once it is
    # complete and checked. A copy that failed half-way (a full disk) used to
    # stay under the real name: every later run that day took it for today's
    # backup, Autopilot saw a fresh backup, and the restore drill found a
    # broken file.
    partial = dest + PARTIAL
    try:
        _copy_checked(cfg["DATABASE"], partial)
    except BaseException:
        _remove(partial)
        raise
    os.replace(partial, dest)
    copies = sorted(glob.glob(os.path.join(cfg["BACKUP_DIR"], "omniarmor-*.db")))
    for old in copies[:-cfg["BACKUP_KEEP"]] if cfg["BACKUP_KEEP"] > 0 else []:
        os.remove(old)
    return dest


PARTIAL = ".partial"


def _copy_checked(source, target):
    """Copies the database with SQLite's online backup, checks the copy, and
    leaves it as one file that needs nothing beside it to be restored."""
    src = sqlite3.connect(source)
    try:
        dst = sqlite3.connect(target)
        try:
            src.backup(dst)
            # The sweeps' locks belong to the processes running now, not to a
            # restored copy: the daily backup is taken while the daily job
            # holds its lock, and a restored copy kept it for minutes.
            if dst.execute("SELECT 1 FROM sqlite_master WHERE name = 'job_locks'").fetchone():
                dst.execute("DELETE FROM job_locks")
                dst.commit()
            result = dst.execute("PRAGMA quick_check").fetchone()[0]
            if result != "ok":
                raise sqlite3.DatabaseError(f"the backup copy failed its check: {result[:200]}")
            dst.execute("PRAGMA journal_mode = DELETE")
        finally:
            dst.close()
    finally:
        src.close()


def _remove(path):
    for name in (path, path + "-journal", path + "-wal", path + "-shm"):
        try:
            os.remove(name)
        except FileNotFoundError:
            pass


def _remove_stale_partials(folder):
    """Copies left half-made by a server that stopped mid-backup."""
    cutoff = time.time() - STALE_AFTER.total_seconds()
    for path in glob.glob(os.path.join(folder, "omniarmor-*.db" + PARTIAL)):
        if os.path.getmtime(path) < cutoff:
            _remove(path)


def cleanup(conn):
    cutoff = iso(utcnow() - timedelta(days=1))
    conn.execute("DELETE FROM login_failures WHERE at < ?", (cutoff,))
    conn.execute("DELETE FROM password_resets WHERE expires_at < ? OR used_at IS NOT NULL", (cutoff,))
    conn.execute("DELETE FROM invites WHERE expires_at < ?", (iso(utcnow() - timedelta(days=30)),))
    conn.execute("DELETE FROM friend_codes WHERE expires_at < ?", (iso(utcnow()),))
    conn.execute("DELETE FROM join_codes WHERE expires_at < ?", (iso(utcnow()),))
    # Answers kept from a quiz nobody finished (academy_views.QUIZ_CHECK_DAYS).
    conn.execute("DELETE FROM quiz_checks WHERE at < ?", (iso(utcnow() - timedelta(days=30)),))
    usage.trim(conn)
    conn.commit()


def run_daily(cfg, force=False):
    """Runs the daily job if it is due and no other process has claimed today."""
    now = utcnow()
    if not force and now.hour < cfg["DAILY_JOB_HOUR_UTC"]:
        return None
    run_date = now.date().isoformat()
    with job_lock(cfg, "daily") as mine:
        if not mine:
            return BUSY if force else None
        return _run_daily(cfg, run_date, force)


BUSY = "Another server process is running it right now; nothing was done. Try again when it finishes."


def _run_daily(cfg, run_date, force):
    conn = connect(cfg["DATABASE"])
    try:
        migrate(conn)
        claimed = claim_run(conn, "daily", run_date)
        if not claimed and not force:
            return None
        failures = []
        summary = {"reminders": 0, "digests": 0, "orgs": 0, "errors": 0}
        try:
            summary = run_reminders(conn, cfg)
        except Exception:
            failures.append("reminders")
            log.exception("daily reminders failed")
        try:
            cleanup(conn)
        except Exception:
            failures.append("cleanup")
            log.exception("daily cleanup failed")
        # The backup comes last, so it holds today's reminders as sent. Taken
        # first, it had none of them: restoring that morning's copy (the
        # restore rehearsal in docs/LOAD-TEST.md) sent everyone the same
        # digest again an hour later, when the copied claim on the day went stale.
        backup = None
        try:
            backup = backup_database(cfg)
        except Exception:
            failures.append("backup")
            log.exception("daily backup failed")
        if summary["errors"]:
            failures.append(f"reminders for {summary['errors']} companies")
        result = (f"reminders={summary['reminders']} digests={summary['digests']} orgs={summary['orgs']}"
                  f" backup={os.path.basename(backup) if backup else 'none'}")
        if failures:
            # Let the next check (in about 10 minutes) try again; reminders already sent are not repeated.
            release_run(conn, "daily", run_date)
            log.error("daily job had failures (%s); it will retry: %s", ", ".join(failures), result)
            return result + " failed=" + ",".join(failures)
        finish_run(conn, "daily", run_date, result)
        log.info("daily job finished: %s", result)
        return result
    finally:
        conn.close()


def run_alerts(cfg, now=None):
    """Sends the time-limit alerts due now (reminders.run_clock_alerts)."""
    conn = connect(cfg["DATABASE"])
    try:
        migrate(conn)
        with job_lock(cfg, "alerts") as mine:
            if not mine:
                return {"orgs": 0, "alerts": 0, "emails": 0, "errors": 0, "busy": True}
            summary = run_clock_alerts(conn, cfg, now=now)
        if summary["alerts"] or summary["errors"]:
            log.info("time-limit alerts: %s", summary)
        return summary
    finally:
        conn.close()


def start_scheduler(cfg):
    """Starts the timer: the time-limit alerts every minute in one thread, the
    daily job and Autopilot every 10 minutes in another."""
    from . import autopilot
    first_alerts = threading.Event()

    def alerts_loop():
        while True:
            try:
                run_alerts(cfg)
            except Exception:
                log.exception("time-limit alerts failed")
            first_alerts.set()
            time.sleep(ALERTS_EVERY_SECONDS)

    def daily_loop():
        # After the first alerts pass, so a clock that just ran out is
        # alerted about before today's digest is put together.
        first_alerts.wait(ALERTS_EVERY_SECONDS)
        while True:
            try:
                run_daily(cfg)
            except Exception:  # keep the timer alive; the failure is logged above
                pass
            if cfg.get("AUTOPILOT_ENABLED", True):
                try:
                    autopilot.run(cfg)
                except Exception:
                    log.exception("autopilot pass failed")
            time.sleep(CHECK_EVERY_SECONDS)

    threads = [threading.Thread(target=alerts_loop, name="omniarmor-alerts", daemon=True),
               threading.Thread(target=daily_loop, name="omniarmor-daily", daemon=True)]
    for thread in threads:
        thread.start()
    return threads


def register_cli(app):
    @app.cli.command("init-db")
    def init_db():
        """Create or upgrade the database."""
        conn = connect(app.config["DATABASE"])
        click.echo(f"Database at schema version {migrate(conn)}: {app.config['DATABASE']}")
        conn.close()

    @app.cli.command("run-daily")
    @click.option("--force", is_flag=True, help="Run now even if today's run already happened.")
    def run_daily_command(force):
        """Send reminders, back up the database and clean up."""
        click.echo(run_daily(dict(app.config), force=force) or "Not due yet, or already done today.")

    @app.cli.command("academy-plan")
    @click.argument("org_id", type=int)
    @click.argument("status", type=click.Choice(["active", "none", "canceled"]))
    def academy_plan_command(org_id, status):
        """Turn a workspace's Academy plan on or off by hand (no Stripe needed)."""
        from .academy_plan import set_status
        conn = connect(app.config["DATABASE"])
        if conn.execute("SELECT 1 FROM orgs WHERE id = ?", (org_id,)).fetchone() is None:
            raise click.ClickException(f"No workspace with id {org_id}.")
        set_status(conn, org_id, status)
        conn.commit()
        conn.close()
        click.echo(f"Workspace {org_id}: Academy plan {status}.")

    @app.cli.command("autopilot")
    @click.option("--log", "show_log", is_flag=True, help="Show what Autopilot fixed and reported in the last 30 days.")
    def autopilot_command(show_log):
        """Check the service now: fix small problems, report big ones."""
        from . import autopilot
        cfg = dict(app.config)
        if show_log:
            conn = connect(cfg["DATABASE"])
            migrate(conn)
            rows = conn.execute("SELECT * FROM autopilot_events WHERE at >= ? ORDER BY id DESC LIMIT 100",
                                (iso(utcnow() - timedelta(days=30)),)).fetchall()
            conn.close()
            for r in rows:
                click.echo(f"{r['at']}  {r['level']:<8}  {r['title']}{'  (emailed)' if r['emailed'] else ''}")
            click.echo("" if rows else "Nothing in the last 30 days.")
            return
        result = autopilot.run(cfg, force=True)
        if result is None:
            click.echo("Autopilot is running in the server right now. Try again in a minute.")
            return
        for line in result["fixed"]:
            click.echo(f"Fixed: {line}")
        for f in result["problems"]:
            click.echo(f"NEEDS YOU: {f.title}\n  {f.detail}\n  What to do: {f.action}")
        if not result["fixed"] and not result["problems"]:
            click.echo("All clear. Nothing to fix and nothing needs you.")
        if result["problems"] and not cfg.get("OPERATOR_EMAIL"):
            click.echo("Tip: set OPERATOR_EMAIL so Autopilot can email you about these.")

    @app.cli.command("backup")
    def backup_command():
        """Back up the database now."""
        click.echo(backup_database(dict(app.config), fresh=True) or "Nothing to back up.")

    @app.cli.command("seed-demo")
    @click.option("--force", "fresh_path", metavar="NEW_DATABASE",
                  help="Seed this new, empty database file instead of the app's own (DATABASE_PATH).")
    @click.option("--password", help="The demo accounts' password (default: a random one, printed at the end).")
    def seed_demo_command(fresh_path, password):
        """Make a demo workspace for screenshots and sales calls (made-up names).

        Refuses unless the database is empty. In production, only into a
        separate new file: --force /data/omniarmor-demo.db"""
        from . import demo
        cfg = dict(app.config)
        live = os.path.abspath(cfg["DATABASE"])
        if fresh_path:
            path = os.path.abspath(fresh_path)
            if path == live:
                raise click.ClickException("--force must name a new database file, not the one the app uses. "
                                           "To seed the app's own empty database, leave --force out.")
            if not demo.is_empty(path):
                raise click.ClickException(f"{path} already holds accounts or workspaces. Name a new file.")
            cfg.update(DATABASE=path, BACKUP_DIR=os.path.join(os.path.dirname(path), "backups"))
        elif cfg["ENV_NAME"] == "production":
            raise click.ClickException("This is production: the demo never goes into the app's own database, even "
                                       "an empty one. Use a separate new file: flask --app wsgi seed-demo --force "
                                       "/data/omniarmor-demo.db")
        elif not demo.is_empty(cfg["DATABASE"]):
            raise click.ClickException(f"{cfg['DATABASE']} already holds accounts or workspaces, so the demo would "
                                       "mix into real data. Nothing was changed. Use a new file: --force demo.db")
        try:
            facts = demo.seed(cfg, password=password)
        except demo.NotEmpty:
            raise click.ClickException("Someone signed up while the demo was being made. Nothing was changed.")
        except ValueError as exc:
            raise click.ClickException(str(exc))
        checks = facts["checks"]
        click.echo(f"Demo workspace ready: {facts['business']} ({' and '.join(facts['industries'])}), all made up.")
        click.echo(f"  Database: {cfg['DATABASE']}")
        click.echo(f"  Checks: {checks['done']} done, {checks['soon']} coming due, {checks['overdue']} overdue,"
                   f" {checks['empty']} without a reading. Audit trail: {facts['audit_rows']} entries.")
        for kid in facts["learners"]:
            cert = f", certificate: {kid['certificate']}" if kid["certificate"] else ""
            click.echo(f"  Academy: {kid['nickname']}, {kid['levels']} levels passed{cert}")
        click.echo(f"  Reminder digests kept in Radar (not sent): {facts['digests']}")
        click.echo(f"  Autopilot: {facts['autopilot']}")
        click.echo("")
        click.echo(f"Sign in at {cfg['BASE_URL']}/login")
        click.echo(f"  Owner:      {facts['owner'][1]}  ({facts['owner'][0]})")
        click.echo(f"  Pharmacist: {facts['member'][1]}  ({facts['member'][0]}, a team member)")
        click.echo(f"  Password for both: {facts['password']}")
        if fresh_path:
            click.echo("")
            click.echo(f"Start the app on it: DATABASE_PATH={cfg['DATABASE']} flask --app wsgi run --port 8000")
