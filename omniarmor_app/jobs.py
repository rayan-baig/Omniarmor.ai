# -*- coding: utf-8 -*-
"""The work that runs by itself every day: reminders, a database backup and
cleanup. Autopilot (autopilot.py) rides on the same timer every 10 minutes. A built-in timer runs it once a day; several server processes can run
the timer safely because each day's run is claimed in the database first."""

import glob
import logging
import os
import sqlite3
import threading
import time
from datetime import timedelta

import click

from .db import connect, iso, migrate, now_iso, utcnow
from .reminders import run_reminders

log = logging.getLogger("omniarmor.jobs")
CHECK_EVERY_SECONDS = 600
STALE_AFTER = timedelta(hours=1)


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


def backup_database(cfg):
    """Copies the live database safely (SQLite online backup) and keeps the newest BACKUP_KEEP copies."""
    if cfg["DATABASE"] == ":memory:":
        return None
    os.makedirs(cfg["BACKUP_DIR"], exist_ok=True)
    dest = os.path.join(cfg["BACKUP_DIR"], f"omniarmor-{utcnow().strftime('%Y%m%d-%H%M%S-%f')}.db")
    src = sqlite3.connect(cfg["DATABASE"])
    dst = sqlite3.connect(dest)
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()
    copies = sorted(glob.glob(os.path.join(cfg["BACKUP_DIR"], "omniarmor-*.db")))
    for old in copies[:-cfg["BACKUP_KEEP"]] if cfg["BACKUP_KEEP"] > 0 else []:
        os.remove(old)
    return dest


def cleanup(conn):
    cutoff = iso(utcnow() - timedelta(days=1))
    conn.execute("DELETE FROM login_failures WHERE at < ?", (cutoff,))
    conn.execute("DELETE FROM password_resets WHERE expires_at < ? OR used_at IS NOT NULL", (cutoff,))
    conn.execute("DELETE FROM invites WHERE expires_at < ?", (iso(utcnow() - timedelta(days=30)),))
    conn.execute("DELETE FROM friend_codes WHERE expires_at < ?", (iso(utcnow()),))
    conn.execute("DELETE FROM join_codes WHERE expires_at < ?", (iso(utcnow()),))
    conn.commit()


def run_daily(cfg, force=False):
    """Runs the daily job if it is due and no other process has claimed today."""
    now = utcnow()
    if not force and now.hour < cfg["DAILY_JOB_HOUR_UTC"]:
        return None
    run_date = now.date().isoformat()
    conn = connect(cfg["DATABASE"])
    try:
        migrate(conn)
        claimed = claim_run(conn, "daily", run_date)
        if not claimed and not force:
            return None
        failures = []
        backup = None
        try:
            backup = backup_database(cfg)
        except Exception:
            failures.append("backup")
            log.exception("daily backup failed")
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


def start_scheduler(cfg):
    from . import autopilot

    def loop():
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
    thread = threading.Thread(target=loop, name="omniarmor-daily", daemon=True)
    thread.start()
    return thread


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
        click.echo(backup_database(dict(app.config)) or "Nothing to back up.")
