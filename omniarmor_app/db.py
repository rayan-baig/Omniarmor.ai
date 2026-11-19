# -*- coding: utf-8 -*-
"""SQLite storage: one connection per request, versioned schema migrations."""

import os
import sqlite3
from datetime import datetime, timezone

from flask import current_app, g

MIGRATIONS = [
    (1, """
    CREATE TABLE users (
        id INTEGER PRIMARY KEY,
        email TEXT NOT NULL UNIQUE COLLATE NOCASE,
        name TEXT NOT NULL,
        password_hash TEXT NOT NULL,
        session_epoch INTEGER NOT NULL DEFAULT 0,
        email_reminders INTEGER NOT NULL DEFAULT 1,
        created_at TEXT NOT NULL
    );
    CREATE TABLE orgs (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        timezone TEXT NOT NULL DEFAULT 'UTC',
        created_at TEXT NOT NULL
    );
    CREATE TABLE memberships (
        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        org_id INTEGER NOT NULL REFERENCES orgs(id) ON DELETE CASCADE,
        role TEXT NOT NULL CHECK (role IN ('owner', 'member')),
        created_at TEXT NOT NULL,
        PRIMARY KEY (user_id, org_id)
    );
    CREATE TABLE org_industries (
        org_id INTEGER NOT NULL REFERENCES orgs(id) ON DELETE CASCADE,
        industry_id INTEGER NOT NULL,
        PRIMARY KEY (org_id, industry_id)
    );
    CREATE TABLE items (
        org_id INTEGER NOT NULL REFERENCES orgs(id) ON DELETE CASCADE,
        industry_id INTEGER NOT NULL,
        rule_key TEXT NOT NULL,
        value_num REAL,
        value_bool INTEGER,
        value_date TEXT,
        limit_override REAL,
        warn_override REAL,
        updated_at TEXT,
        updated_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
        PRIMARY KEY (org_id, industry_id, rule_key)
    );
    CREATE TABLE audit (
        id INTEGER PRIMARY KEY,
        org_id INTEGER NOT NULL REFERENCES orgs(id) ON DELETE CASCADE,
        user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
        at TEXT NOT NULL,
        action TEXT NOT NULL,
        industry_id INTEGER,
        rule_key TEXT,
        before TEXT,
        after TEXT,
        summary TEXT NOT NULL
    );
    CREATE INDEX audit_org_at ON audit (org_id, at DESC);
    CREATE TABLE notifications (
        id INTEGER PRIMARY KEY,
        org_id INTEGER REFERENCES orgs(id) ON DELETE CASCADE,
        user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
        created_at TEXT NOT NULL,
        kind TEXT NOT NULL,
        recipient TEXT NOT NULL,
        subject TEXT NOT NULL,
        body TEXT NOT NULL,
        status TEXT NOT NULL CHECK (status IN ('sent', 'logged', 'failed')),
        error TEXT
    );
    CREATE INDEX notifications_org ON notifications (org_id, created_at DESC);
    CREATE TABLE reminder_marks (
        org_id INTEGER NOT NULL REFERENCES orgs(id) ON DELETE CASCADE,
        industry_id INTEGER NOT NULL,
        rule_key TEXT NOT NULL,
        due_date TEXT NOT NULL,
        threshold TEXT NOT NULL,
        sent_at TEXT NOT NULL,
        PRIMARY KEY (org_id, industry_id, rule_key, due_date, threshold)
    );
    CREATE TABLE invites (
        token_hash TEXT PRIMARY KEY,
        org_id INTEGER NOT NULL REFERENCES orgs(id) ON DELETE CASCADE,
        created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
        created_at TEXT NOT NULL,
        expires_at TEXT NOT NULL,
        used_at TEXT
    );
    CREATE TABLE password_resets (
        token_hash TEXT PRIMARY KEY,
        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        created_at TEXT NOT NULL,
        expires_at TEXT NOT NULL,
        used_at TEXT
    );
    CREATE TABLE login_failures (
        key TEXT NOT NULL,
        at TEXT NOT NULL
    );
    CREATE INDEX login_failures_key ON login_failures (key, at);
    CREATE TABLE job_runs (
        job TEXT NOT NULL,
        run_date TEXT NOT NULL,
        started_at TEXT NOT NULL,
        finished_at TEXT,
        result TEXT,
        PRIMARY KEY (job, run_date)
    );
    """),
    (2, """
    CREATE TABLE learners (
        id INTEGER PRIMARY KEY,
        org_id INTEGER NOT NULL REFERENCES orgs(id) ON DELETE CASCADE,
        nickname TEXT NOT NULL,
        avatar TEXT NOT NULL,
        created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
        created_at TEXT NOT NULL
    );
    CREATE INDEX learners_org ON learners (org_id);
    CREATE TABLE learner_progress (
        learner_id INTEGER NOT NULL REFERENCES learners(id) ON DELETE CASCADE,
        level INTEGER NOT NULL,
        attempts INTEGER NOT NULL DEFAULT 0,
        best_score INTEGER NOT NULL DEFAULT 0,
        best_stars INTEGER NOT NULL DEFAULT 0,
        completed_at TEXT,
        PRIMARY KEY (learner_id, level)
    );
    """),
    (3, """
    CREATE TABLE friend_codes (
        learner_id INTEGER PRIMARY KEY REFERENCES learners(id) ON DELETE CASCADE,
        code TEXT NOT NULL UNIQUE,
        expires_at TEXT NOT NULL
    );
    CREATE TABLE learner_friends (
        learner_a INTEGER NOT NULL REFERENCES learners(id) ON DELETE CASCADE,
        learner_b INTEGER NOT NULL REFERENCES learners(id) ON DELETE CASCADE,
        created_at TEXT NOT NULL,
        PRIMARY KEY (learner_a, learner_b),
        CHECK (learner_a < learner_b)
    );
    CREATE INDEX learner_friends_b ON learner_friends (learner_b);
    CREATE TABLE duels (
        id INTEGER PRIMARY KEY,
        challenger_id INTEGER NOT NULL REFERENCES learners(id) ON DELETE CASCADE,
        opponent_id INTEGER NOT NULL REFERENCES learners(id) ON DELETE CASCADE,
        world INTEGER NOT NULL,
        stage INTEGER NOT NULL,
        seed TEXT NOT NULL,
        challenger_score INTEGER,
        opponent_score INTEGER,
        created_at TEXT NOT NULL
    );
    CREATE INDEX duels_challenger ON duels (challenger_id);
    CREATE INDEX duels_opponent ON duels (opponent_id);
    """),
    (4, """
    ALTER TABLE users ADD COLUMN armo TEXT NOT NULL DEFAULT 'chief';
    ALTER TABLE learners ADD COLUMN armo TEXT NOT NULL DEFAULT 'sweet';
    """),
    (5, """
    ALTER TABLE learners ADD COLUMN track TEXT NOT NULL DEFAULT 'launchpad';
    ALTER TABLE learners ADD COLUMN track_chosen INTEGER NOT NULL DEFAULT 0;
    ALTER TABLE learners ADD COLUMN device_epoch INTEGER NOT NULL DEFAULT 0;
    CREATE TABLE join_codes (
        learner_id INTEGER PRIMARY KEY REFERENCES learners(id) ON DELETE CASCADE,
        code TEXT NOT NULL UNIQUE,
        expires_at TEXT NOT NULL
    );
    CREATE TABLE learner_days (
        learner_id INTEGER NOT NULL REFERENCES learners(id) ON DELETE CASCADE,
        day TEXT NOT NULL,
        levels INTEGER NOT NULL DEFAULT 0,
        PRIMARY KEY (learner_id, day)
    );
    CREATE TABLE learner_mistakes (
        id INTEGER PRIMARY KEY,
        learner_id INTEGER NOT NULL REFERENCES learners(id) ON DELETE CASCADE,
        qkey TEXT NOT NULL,
        question TEXT NOT NULL,
        misses INTEGER NOT NULL DEFAULT 1,
        streak INTEGER NOT NULL DEFAULT 0,
        due_at TEXT NOT NULL,
        UNIQUE (learner_id, qkey)
    );
    CREATE INDEX learner_mistakes_due ON learner_mistakes (learner_id, due_at);
    ALTER TABLE orgs ADD COLUMN academy_status TEXT NOT NULL DEFAULT 'none';
    ALTER TABLE orgs ADD COLUMN academy_trial_ends TEXT;
    ALTER TABLE orgs ADD COLUMN academy_renews_at TEXT;
    ALTER TABLE orgs ADD COLUMN stripe_customer_id TEXT;
    ALTER TABLE orgs ADD COLUMN stripe_subscription_id TEXT;
    """),
    (6, """
    CREATE TABLE autopilot_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        at TEXT NOT NULL,
        check_key TEXT NOT NULL,
        level TEXT NOT NULL CHECK (level IN ('fixed', 'alert', 'resolved')),
        title TEXT NOT NULL,
        detail TEXT NOT NULL DEFAULT '',
        emailed INTEGER NOT NULL DEFAULT 0
    );
    CREATE INDEX autopilot_events_key ON autopilot_events (check_key, at DESC);
    CREATE TABLE app_errors (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        at TEXT NOT NULL,
        path TEXT NOT NULL,
        error TEXT NOT NULL,
        signature TEXT NOT NULL DEFAULT '',
        location TEXT NOT NULL DEFAULT '',
        trace TEXT NOT NULL DEFAULT ''
    );
    CREATE INDEX app_errors_at ON app_errors (at);
    CREATE INDEX app_errors_signature ON app_errors (signature, at);
    ALTER TABLE notifications ADD COLUMN attempts INTEGER NOT NULL DEFAULT 1;
    """),
    (7, """
    UPDATE learners SET device_epoch = (random() & 4611686018427387903) + 1;
    CREATE TABLE stripe_events (
        id TEXT PRIMARY KEY,
        org_id INTEGER REFERENCES orgs(id) ON DELETE SET NULL,
        type TEXT NOT NULL,
        created INTEGER,
        received_at TEXT NOT NULL
    );
    ALTER TABLE orgs ADD COLUMN stripe_event_at INTEGER;
    UPDATE orgs SET academy_trial_ends = strftime('%Y-%m-%dT%H:%M:%S+00:00', 'now', '+14 days')
        WHERE academy_trial_ends IS NULL AND academy_status = 'none'
        AND EXISTS (SELECT 1 FROM learners WHERE learners.org_id = orgs.id);
    """),
    (8, """
    CREATE TABLE quiz_checks (
        learner_id INTEGER NOT NULL REFERENCES learners(id) ON DELETE CASCADE,
        qkey TEXT NOT NULL,
        choice INTEGER NOT NULL,
        at TEXT NOT NULL,
        PRIMARY KEY (learner_id, qkey)
    );
    CREATE INDEX quiz_checks_at ON quiz_checks (at);
    """),
    (9, """
    ALTER TABLE users ADD COLUMN last_seen_on TEXT;
    """),
    (10, """
    ALTER TABLE orgs ADD COLUMN academy_ends_at TEXT;
    """),
    (11, """
    ALTER TABLE audit ADD COLUMN user_name TEXT;
    UPDATE audit SET user_name = (SELECT name FROM users WHERE users.id = audit.user_id);
    ALTER TABLE items ADD COLUMN updated_by_name TEXT;
    UPDATE items SET updated_by_name = (SELECT name FROM users WHERE users.id = items.updated_by);
    """),
    # The audit trail pages are sorted by time and then id, newest first. The
    # old index had only the time, so every page sorted each second's rows
    # again, and a deep page read every row it skipped from the table. This
    # one holds the whole sort order and the person's id (all the skipped rows
    # need for the join), and replaces the old one, which it starts with.
    (12, """
    CREATE INDEX audit_org_at_id ON audit (org_id, at DESC, id DESC, user_id);
    DROP INDEX audit_org_at;
    """),
    # Each person chooses which reminder emails they get. email_reminders,
    # which used to turn every reminder email on or off, now means the daily
    # digest; the time-limit alerts get their own choice, which starts the
    # way the old one was set; and the operator's account can turn off the
    # weekly Autopilot report.
    (13, """
    ALTER TABLE users ADD COLUMN email_alerts INTEGER NOT NULL DEFAULT 1;
    UPDATE users SET email_alerts = email_reminders;
    ALTER TABLE users ADD COLUMN email_weekly INTEGER NOT NULL DEFAULT 1;
    """),
    # A lock per scheduled sweep (the time-limit alerts, the daily job,
    # Autopilot), held while it runs, so two server processes never run the
    # same sweep at once however long it takes (jobs.job_lock). It is a lease:
    # the holder renews expires_at while it works, so a process that died
    # loses it within minutes.
    (14, """
    CREATE TABLE job_locks (
        name TEXT PRIMARY KEY,
        holder TEXT NOT NULL,
        taken_at TEXT NOT NULL,
        expires_at TEXT NOT NULL
    );
    """),
    # How often a few features are used, as one total per day and feature
    # (usage.py). Nothing in it says who: no user, workspace or learner id.
    # And an index for the error reports' limits (errormail.py), which count
    # the reports already in the outbox by kind and time.
    (15, """
    CREATE TABLE usage_counts (
        day TEXT NOT NULL,
        event TEXT NOT NULL,
        count INTEGER NOT NULL DEFAULT 0,
        PRIMARY KEY (day, event)
    );
    CREATE INDEX notifications_kind ON notifications (kind, created_at);
    """),
    # Operator status (the usage counts and the weekly Autopilot report's
    # switch in Settings) is a flag that only `flask --app wsgi make-operator`
    # sets, on the server. Having the OPERATOR_EMAIL address used to be
    # enough, but sign-up doesn't prove an address is yours, so a stranger
    # could register it first. Nobody starts with the flag, not even an
    # account that already has the address: the owner runs the command once.
    (16, """
    ALTER TABLE users ADD COLUMN is_operator INTEGER NOT NULL DEFAULT 0;
    """),
    # The Kitchen Safety Bundle (connections.py): a workspace's connection key
    # for CyberLogix, MTRX Horizyn's fridge and freezer alarm app, stored as a
    # hash like invite links, at most one active per workspace and app; and
    # the daily reports it sent, one row per workspace, check and day, which
    # is what makes sending the same day twice change nothing. A report holds
    # temperatures, unit names and roles, never a person's name.
    (17, """
    CREATE TABLE connection_keys (
        id INTEGER PRIMARY KEY,
        org_id INTEGER NOT NULL REFERENCES orgs(id) ON DELETE CASCADE,
        service TEXT NOT NULL,
        key_hash TEXT NOT NULL UNIQUE,
        hint TEXT NOT NULL,
        created_at TEXT NOT NULL,
        created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
        revoked_at TEXT,
        last_used_at TEXT,
        last_report_date TEXT
    );
    CREATE UNIQUE INDEX connection_keys_one_active ON connection_keys (org_id, service) WHERE revoked_at IS NULL;
    CREATE TABLE connection_reports (
        org_id INTEGER NOT NULL REFERENCES orgs(id) ON DELETE CASCADE,
        service TEXT NOT NULL,
        industry_id INTEGER NOT NULL,
        rule_key TEXT NOT NULL,
        report_date TEXT NOT NULL,
        fingerprint TEXT NOT NULL,
        outcome TEXT NOT NULL CHECK (outcome IN ('ticked', 'confirmed', 'note')),
        reading REAL,
        summary TEXT NOT NULL,
        note TEXT,
        site TEXT,
        log_url TEXT,
        received_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        reviewed_at TEXT,
        PRIMARY KEY (org_id, service, industry_id, rule_key, report_date)
    );
    """),
    # Paid plans (plans.py). orgs.plan says what the workspace's subscription
    # is for: 'pro', 'plus', 'plus_bundle' (Plus for a Kitchen Safety Bundle
    # workspace, billed the difference), 'academy' (the old standalone
    # Academy plan, kept as it was) or 'none'. academy_status, academy_renews_at
    # and academy_ends_at keep their first names but now hold that
    # subscription's status and dates, whichever plan it is, and
    # academy_trial_ends is the one free trial of the whole app. A workspace
    # paying for the Academy now is on the old plan. Every other workspace
    # had the tracker free until today, so it gets the new trial from today
    # (or keeps a later Academy trial end), as migration 7 did for the
    # Academy. {TRIAL_DAYS} is the ACADEMY_TRIAL_DAYS setting.
    # bundle_report_at is when the last validly signed CyberLogix report
    # arrived (the Kitchen Safety Bundle's cover), and bundle_signatures
    # remembers each accepted signature for 10 minutes, so the same signed
    # request sent again doesn't count twice (connections.py).
    (18, """
    ALTER TABLE orgs ADD COLUMN plan TEXT NOT NULL DEFAULT 'none';
    ALTER TABLE orgs ADD COLUMN bundle_report_at TEXT;
    UPDATE orgs SET plan = 'academy' WHERE academy_status IN ('active', 'trialing', 'past_due');
    UPDATE orgs SET academy_trial_ends = MAX(COALESCE(academy_trial_ends, ''),
        strftime('%Y-%m-%dT%H:%M:%S+00:00', 'now', '+{TRIAL_DAYS} days')) WHERE plan = 'none';
    CREATE TABLE bundle_signatures (
        signature TEXT PRIMARY KEY,
        stamp INTEGER NOT NULL,
        org_id INTEGER REFERENCES orgs(id) ON DELETE CASCADE,
        seen_at TEXT NOT NULL
    );
    CREATE INDEX bundle_signatures_seen ON bundle_signatures (seen_at);
    """),
    # Monthly or yearly (plans.py): whether the workspace's subscription is
    # paid each month or each year, 'month' or 'year', read from the
    # subscription's price by Stripe's webhook. Every subscription before
    # this one was monthly.
    (19, """
    ALTER TABLE orgs ADD COLUMN plan_interval TEXT NOT NULL DEFAULT 'month';
    """),
    # Pause instead of cancel, the one-time save offer and upgrade offers
    # (plans.py, nudges.py). paused_until is when a paused plan starts again
    # by itself (billing, reminders and saving checks come back then);
    # paused_at when the pause began; pause_reminded_at when the "starts again
    # in 3 days" email went out. save_offer_used_at is when the workspace took
    # the save offer, which it can do once, ever. nudges remembers, per person
    # and kind of offer, when it was last shown and whether they dismissed
    # it, so no one sees more than one offer a week, or one they said no to.
    (20, """
    ALTER TABLE orgs ADD COLUMN paused_until TEXT;
    ALTER TABLE orgs ADD COLUMN paused_at TEXT;
    ALTER TABLE orgs ADD COLUMN pause_reminded_at TEXT;
    ALTER TABLE orgs ADD COLUMN save_offer_used_at TEXT;
    CREATE TABLE nudges (
        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        kind TEXT NOT NULL,
        shown_at TEXT,
        dismissed_at TEXT,
        PRIMARY KEY (user_id, kind)
    );
    CREATE INDEX nudges_shown ON nudges (user_id, shown_at);
    """),
    # The Academy for classrooms (classrooms.py). A class belongs to a
    # workspace and has a name the teacher picks; `leaderboard` is whether its
    # students see the class leaderboard (the teacher can turn it off). A
    # learner in a class has class_id set (a family's own learners have
    # none); deleting a class deletes its students and their progress.
    # pilot_started_at and pilot_ends_at are the workspace's one free
    # classroom pilot (plans.py).
    (21, """
    CREATE TABLE classes (
        id INTEGER PRIMARY KEY,
        org_id INTEGER NOT NULL REFERENCES orgs(id) ON DELETE CASCADE,
        name TEXT NOT NULL,
        leaderboard INTEGER NOT NULL DEFAULT 1,
        created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
        created_at TEXT NOT NULL
    );
    CREATE INDEX classes_org ON classes (org_id);
    ALTER TABLE learners ADD COLUMN class_id INTEGER REFERENCES classes(id) ON DELETE CASCADE;
    CREATE INDEX learners_class ON learners (class_id);
    ALTER TABLE orgs ADD COLUMN pilot_started_at TEXT;
    ALTER TABLE orgs ADD COLUMN pilot_ends_at TEXT;
    """),
    # 1.6.2. pause_open: Stripe has paused the plan with no end date (a
    # pause_collection without resumes_at, set in Stripe's dashboard): the
    # workspace is paused until Stripe resumes it. users.pilot_used_at: when
    # this owner started the free classroom pilot, which is one per owner,
    # whichever of their locations it was in (and kept when that location is
    # deleted). Filled in from the pilots already started.
    (22, """
    ALTER TABLE orgs ADD COLUMN pause_open INTEGER NOT NULL DEFAULT 0;
    ALTER TABLE users ADD COLUMN pilot_used_at TEXT;
    UPDATE users SET pilot_used_at = (
        SELECT MIN(orgs.pilot_started_at) FROM memberships JOIN orgs ON orgs.id = memberships.org_id
        WHERE memberships.user_id = users.id AND memberships.role = 'owner' AND orgs.pilot_started_at IS NOT NULL);
    """),
    # 1.7.0. users.reminders_chosen_at: when this person last saved their
    # reminder email choices in Settings, which ticks the last step of the
    # overview's getting-started list (views.getting_started). Filled in for
    # the accounts already here, so the new list doesn't come back to
    # workspaces long past their first days.
    (23, """
    ALTER TABLE users ADD COLUMN reminders_chosen_at TEXT;
    UPDATE users SET reminders_chosen_at = created_at;
    """),
    # 1.8.0. job_heartbeats: the background timers' "last ran at" (health.py),
    # one row per timer, read by /readyz and Autopilot to notice a timer that
    # stopped. started_at is when the timer first ran on this database.
    # Indexes for queries that read whole tables as they grew: a workspace's
    # team (memberships by workspace), Radar's emails sent to one person, and
    # Autopilot's failed emails, every 10 minutes.
    (24, """
    CREATE TABLE job_heartbeats (
        name TEXT PRIMARY KEY,
        beat_at TEXT NOT NULL,
        started_at TEXT NOT NULL
    );
    CREATE INDEX memberships_org ON memberships (org_id, role);
    CREATE INDEX notifications_user ON notifications (user_id, created_at);
    CREATE INDEX notifications_status ON notifications (status, created_at);
    """),
    # 1.9.0. orgs.kind: 'business' or 'school'. A school workspace (a
    # teacher's, from the teacher sign-up) runs the Academy for classes: its
    # menus, plan page and lessons are made for a classroom (classrooms.py).
    # Workspaces already here that use the classroom plans, the pilot or
    # classes, and track no checklist but the school ones (SchoolArmor 8 and
    # SchoolSafetyArmor 51), are schools. And students already in a class
    # move to the Classroom track, made for a class (academy.py); what they
    # finished before still counts in the class view and the pilot report.
    (25, """
    ALTER TABLE orgs ADD COLUMN kind TEXT NOT NULL DEFAULT 'business';
    UPDATE orgs SET kind = 'school' WHERE (plan IN ('classroom', 'school') OR pilot_started_at IS NOT NULL
        OR EXISTS (SELECT 1 FROM classes WHERE classes.org_id = orgs.id))
        AND NOT EXISTS (SELECT 1 FROM org_industries WHERE org_industries.org_id = orgs.id
                        AND org_industries.industry_id NOT IN (8, 51));
    UPDATE learners SET track = 'classroom', track_chosen = 1 WHERE class_id IS NOT NULL;
    """),
]

SCHEMA_VERSION = MIGRATIONS[-1][0]


def utcnow():
    return datetime.now(timezone.utc)


def iso(dt):
    return dt.astimezone(timezone.utc).isoformat(timespec="seconds")


def now_iso():
    return iso(utcnow())


def connect(path):
    if path != ":memory:":
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    conn = sqlite3.connect(path, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 30000")
    if path != ":memory:":
        conn.execute("PRAGMA journal_mode = WAL")
    return conn


def migrate(conn, trial_days=14):
    """Brings the schema up to date. Takes SQLite's write lock first, so when
    several server processes start together only one of them applies changes.
    trial_days is the free trial's length (ACADEMY_TRIAL_DAYS), for the
    migration that gives workspaces already there the new trial."""
    previous = conn.isolation_level
    conn.isolation_level = None
    try:
        conn.execute("BEGIN IMMEDIATE")
        try:
            conn.execute("CREATE TABLE IF NOT EXISTS schema_version (version INTEGER NOT NULL)")
            current = conn.execute("SELECT COALESCE(MAX(version), 0) FROM schema_version").fetchone()[0]
            for version, sql in MIGRATIONS:
                if version > current:
                    sql = sql.replace("{TRIAL_DAYS}", str(int(trial_days)))
                    for statement in sql.split(";"):
                        if statement.strip():
                            conn.execute(statement)
                    conn.execute("INSERT INTO schema_version (version) VALUES (?)", (version,))
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise
    finally:
        conn.isolation_level = previous
    return conn.execute("SELECT MAX(version) FROM schema_version").fetchone()[0]


def get_db():
    if "db" not in g:
        if g.get("demo") is not None:
            # Inside a demo, this request's own throwaway copy of the demo
            # database (demo_mode.py), never the real one.
            from .demo_mode import sandbox
            g.db = sandbox()
        else:
            g.db = connect(current_app.config["DATABASE"])
    return g.db


def close_db(_exc=None):
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()


def user_name(conn, user_id):
    """The person's name, kept on audit rows and readings so the record still
    says who made a change after that person is removed from the team."""
    if user_id is None:
        return None
    row = conn.execute("SELECT name FROM users WHERE id = ?", (user_id,)).fetchone()
    return row["name"] if row else None


def record_audit(conn, org_id, user_id, action, summary, industry_id=None, rule_key=None, before=None, after=None,
                 actor=None):
    """One row of the audit trail. `actor` names who made a change that no
    person made (an app sending a report, such as "CyberLogix"); it is used
    only when user_id is None."""
    name = user_name(conn, user_id) if user_id is not None else actor
    conn.execute(
        "INSERT INTO audit (org_id, user_id, user_name, at, action, industry_id, rule_key, before, after, summary)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (org_id, user_id, name, now_iso(), action, industry_id, rule_key, before, after, summary),
    )
