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

from . import plans, usage
from .db import connect, iso, migrate, now_iso, utcnow
from .notify import notify
from .reminders import run_clock_alerts, run_reminders
from .tracking import local_date
from .words import plural

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
        migrate(conn, cfg.get("ACADEMY_TRIAL_DAYS", 14))   # the lock's table, on a database no app has opened yet
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
    # CyberLogix signatures past their replay window (connections.SIGNATURE_MEMORY).
    conn.execute("DELETE FROM bundle_signatures WHERE seen_at < ?", (iso(utcnow() - timedelta(minutes=10)),))
    usage.trim(conn)
    conn.commit()


def run_pause_sweep(conn, cfg, now=None):
    """Paused plans (plans.py): emails each owner RESUME_NOTICE before a
    pause ends ("your plan starts again on ..."), once per pause, and tidies
    pauses that have ended. Ending needs nothing from here: plans.access
    reads paused_until, so a plan is on again the moment its pause ends, and
    Stripe starts charging by itself at resumes_at."""
    now = now or utcnow()
    summary = {"notices": 0, "ended": 0}
    soon = iso(now + plans.RESUME_NOTICE)
    rows = conn.execute("SELECT * FROM orgs WHERE paused_until IS NOT NULL AND pause_reminded_at IS NULL"
                        " AND paused_until > ? AND paused_until <= ?", (iso(now), soon)).fetchall()
    base = cfg.get("BASE_URL", "").rstrip("/")
    for org in rows:
        if not plans.access(org, now)["paused"]:
            continue
        day = local_date(org["paused_until"], org)
        owners = conn.execute("SELECT users.* FROM users JOIN memberships ON memberships.user_id = users.id"
                              " WHERE memberships.org_id = ? AND memberships.role = 'owner' ORDER BY users.id",
                              (org["id"],)).fetchall()
        for user in owners:
            body = (f"Hi {user['name']},\n\n"
                    f"The plan for {org['name']} is paused, and it starts again by itself on {day}.\n\n"
                    "From then on:\n"
                    "- Billing starts again, as before.\n"
                    "- Checks can be saved again, and reminder emails come back on.\n\n"
                    "Nothing to do if that suits you. To pause longer or cancel instead:\n\n"
                    f"Open your plan: {base}/app/plan/cancel")
            notify(conn, cfg, "plan", user["email"], f"Your OmniArmor plan starts again on {day}", body,
                   org_id=org["id"], user_id=user["id"])
        conn.execute("UPDATE orgs SET pause_reminded_at = ? WHERE id = ?", (iso(now), org["id"]))
        conn.commit()
        summary["notices"] += 1
    ended = conn.execute("UPDATE orgs SET paused_until = NULL, paused_at = NULL, pause_reminded_at = NULL"
                         " WHERE paused_until IS NOT NULL AND paused_until <= ?", (iso(now),)).rowcount
    conn.commit()
    summary["ended"] = ended
    return summary


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
        migrate(conn, cfg.get("ACADEMY_TRIAL_DAYS", 14))
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
            run_pause_sweep(conn, cfg)
        except Exception:
            failures.append("pauses")
            log.exception("daily pause sweep failed")
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
        migrate(conn, cfg.get("ACADEMY_TRIAL_DAYS", 14))
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
    from .health import beat
    first_alerts = threading.Event()

    def alerts_loop():
        while True:
            try:
                run_alerts(cfg)
            except Exception:
                log.exception("time-limit alerts failed")
            # "Last ran at", for /readyz and Autopilot (health.py): a loop
            # that stops beating has stopped, whatever the reason.
            beat(cfg, "alerts")
            try:
                autopilot.watch_daily_timer(cfg)
            except Exception:
                log.exception("the daily timer's watchdog failed")
            first_alerts.set()
            time.sleep(ALERTS_EVERY_SECONDS)

    def daily_loop():
        # After the first alerts pass, so a clock that just ran out is
        # alerted about before today's digest is put together.
        first_alerts.wait(ALERTS_EVERY_SECONDS)
        while True:
            beat(cfg, "daily")
            try:
                run_daily(cfg)
            except Exception:  # keep the timer alive; the failure is logged above
                pass
            if cfg.get("AUTOPILOT_ENABLED", True):
                try:
                    autopilot.run(cfg)
                except Exception:
                    log.exception("autopilot pass failed")
            beat(cfg, "daily")
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
        click.echo(f"Database at schema version {migrate(conn, app.config['ACADEMY_TRIAL_DAYS'])}: {app.config['DATABASE']}")
        conn.close()

    @app.cli.command("run-daily")
    @click.option("--force", is_flag=True, help="Run now even if today's run already happened.")
    def run_daily_command(force):
        """Send reminders, back up the database and clean up."""
        click.echo(run_daily(dict(app.config), force=force) or "Not due yet, or already done today.")

    def _set_plan(org_id, state, kind, interval=None, ends_at=None, force=False, until=None):
        """Sets the plan by hand. Refused over a Stripe subscription that is
        still running, unless force: it would go on charging, and Stripe's
        next update would replace what was set here. until (a date) ends the
        plan at 23:59:59 that day in the workspace's own timezone."""
        from .academy_plan import RUNNING_STATES, set_status
        conn = connect(app.config["DATABASE"])
        try:
            org = conn.execute("SELECT * FROM orgs WHERE id = ?", (org_id,)).fetchone()
            if org is None:
                raise click.ClickException(f"No workspace with id {org_id}.")
            if org["stripe_subscription_id"] and org["academy_status"] in RUNNING_STATES and not force:
                raise click.ClickException(
                    f"Workspace {org_id} pays through the Stripe subscription {org['stripe_subscription_id']}"
                    f" ({org['academy_status']}). Cancel it in Stripe first, or run this again with --force: Stripe"
                    " would go on charging, and its next update would replace the plan set here.")
            if until is not None:
                from datetime import datetime as _dt, time as _time, timezone as _tz
                from zoneinfo import ZoneInfo
                zone = ZoneInfo(org["timezone"]) if org["timezone"] else _tz.utc
                ends_at = iso(_dt.combine(until, _time(23, 59, 59), tzinfo=zone).astimezone(_tz.utc))
            set_status(conn, org_id, state, kind=kind, interval=interval, ends_at=ends_at)
            conn.commit()
        finally:
            conn.close()

    @app.cli.command("plan")
    @click.argument("org_id", type=int)
    @click.argument("plan", type=click.Choice(["pro", "plus", "classroom", "school", "none"]))
    @click.option("--yearly", is_flag=True, help="Paid yearly rather than monthly (classroom plans always are).")
    @click.option("--until", "until", metavar="YYYY-MM-DD",
                  help="The last day of the plan (to 23:59:59 in the workspace's timezone), such as the end of"
                       " a school year paid by invoice.")
    @click.option("--force", is_flag=True,
                  help="Set it even over a Stripe subscription that is still running.")
    def plan_command(org_id, plan, yearly, until, force):
        """Put a workspace on Pro, Plus, Classroom or Whole school by hand, or take its plan away
        (no Stripe needed: a school that pays by invoice, say)."""
        from datetime import date
        from .plans import CLASSROOM_PLANS
        last = None
        if until:
            try:
                last = date.fromisoformat(until)
            except ValueError:
                raise click.ClickException("--until takes a date: YYYY-MM-DD.")
        yearly = yearly or plan in CLASSROOM_PLANS
        _set_plan(org_id, "none" if plan == "none" else "active", None if plan == "none" else plan,
                  None if plan == "none" else ("year" if yearly else "month"), force=force, until=last)
        name = CLASSROOM_PLANS[plan].name if plan in CLASSROOM_PLANS else plan.title()
        click.echo(f"Workspace {org_id}: " + ("no plan." if plan == "none"
                                              else f"{name} on" + (", yearly" if yearly else "")
                                              + (f", until {until}." if until else ".")))

    @app.cli.command("academy-plan")
    @click.argument("org_id", type=int)
    @click.argument("status", type=click.Choice(["active", "none", "canceled"]))
    @click.option("--force", is_flag=True, help="Set it even over a Stripe subscription that is still running.")
    def academy_plan_command(org_id, status, force):
        """The old command, kept for scripts: "active" now puts the workspace on Plus (the plan the
        Academy plan became). Prefer `plan`."""
        _set_plan(org_id, status, "plus" if status == "active" else None, force=force)
        click.echo(f"Workspace {org_id}: Academy plan {status}" + (" (Plus)." if status == "active" else "."))

    @app.cli.command("make-operator")
    @click.argument("email")
    @click.option("--revoke", is_flag=True, help="Take operator status away from this account instead.")
    def make_operator_command(email, revoke):
        """Make the account with the OPERATOR_EMAIL address the operator.

        The operator's account sees the usage counts and the weekly Autopilot
        report's switch in Settings. Signing up with the address is not
        enough: only this command, run on the server, gives it. --revoke
        takes it away."""
        from .auth import OperatorRefused, set_operator
        conn = connect(app.config["DATABASE"])
        try:
            migrate(conn, app.config["ACADEMY_TRIAL_DAYS"])
            user = set_operator(conn, app.config, email, on=not revoke)
            orgs = [r[0] for r in conn.execute("SELECT orgs.name FROM memberships JOIN orgs ON orgs.id ="
                                               " memberships.org_id WHERE memberships.user_id = ?", (user["id"],))]
        except OperatorRefused as exc:
            raise click.ClickException(str(exc))
        finally:
            conn.close()
        if revoke:
            click.echo(f"{user['email']} is not the operator any more.")
            return
        click.echo(f"{user['email']} is now the operator.")
        click.echo(f"  Account created {user['created_at']}, name {user['name']!r},"
                   f" workspace: {', '.join(orgs) or '(none)'}.")
        click.echo("  If you didn't make this account yourself, run this again with --revoke, then use"
                   " 'Forgot your password?' with this address: the link comes to your inbox.")

    @app.cli.command("autopilot")
    @click.option("--log", "show_log", is_flag=True, help="Show what Autopilot fixed and reported in the last 30 days.")
    def autopilot_command(show_log):
        """Check the service now: fix small problems, report big ones."""
        from . import autopilot
        cfg = dict(app.config)
        if show_log:
            conn = connect(cfg["DATABASE"])
            migrate(conn, cfg.get('ACADEMY_TRIAL_DAYS', 14))
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

    @app.cli.command("ready")
    def ready_command():
        """Say what /readyz checks, each with what's wrong and what to do (exit code 1 if something failed)."""
        from . import health
        cfg = dict(app.config)
        found = health.checks(cfg, grace=False)
        for name, state in found.items():
            click.echo(f"{state.upper():<5} {name}")
            if state == "fail":
                problem, action = health.EXPLAIN[name]
                click.echo(f"      {problem}")
                for line in (health.settings_problems(cfg) if name == "settings" else []):
                    click.echo(f"      - {line}")
                click.echo(f"      What to do: {action}")
        failed = [n for n, s in found.items() if s == "fail"]
        click.echo("All clear." if not failed else f"{len(failed)} check(s) need you.")
        if failed:
            raise SystemExit(1)

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
            # Its backups get a folder of their own: "backups" beside it is the
            # live database's folder when the two files sit together (/data in
            # production), and the live daily job took the demo's copy there
            # for its own backup of the day.
            cfg.update(DATABASE=path, BACKUP_DIR=os.path.splitext(path)[0] + "-backups")
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
                   f" {checks['empty']} without a reading. Audit trail: {plural(facts['audit_rows'], 'entry')}.")
        for kid in facts["learners"]:
            cert = f", certificate: {kid['certificate']}" if kid["certificate"] else ""
            click.echo(f"  Academy: {kid['nickname']}, {plural(kid['levels'], 'level')} passed{cert}")
        click.echo(f"  Reminder digests kept in Reminders (not sent): {facts['digests']}")
        click.echo(f"  Autopilot: {facts['autopilot']}")
        click.echo("")
        click.echo(f"Sign in at {cfg['BASE_URL']}/login")
        click.echo(f"  Owner:      {facts['owner'][1]}  ({facts['owner'][0]})")
        click.echo(f"  Pharmacist: {facts['member'][1]}  ({facts['member'][0]}, a team member)")
        click.echo(f"  Password for both: {facts['password']}")
        if fresh_path:
            click.echo("")
            click.echo(f"Start the app on it: DATABASE_PATH={cfg['DATABASE']} BACKUP_DIR={cfg['BACKUP_DIR']}"
                       " flask --app wsgi run --port 8000")
