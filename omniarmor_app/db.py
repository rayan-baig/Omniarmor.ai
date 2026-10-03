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


def migrate(conn):
    """Brings the schema up to date. Takes SQLite's write lock first, so when
    several server processes start together only one of them applies changes."""
    previous = conn.isolation_level
    conn.isolation_level = None
    try:
        conn.execute("BEGIN IMMEDIATE")
        try:
            conn.execute("CREATE TABLE IF NOT EXISTS schema_version (version INTEGER NOT NULL)")
            current = conn.execute("SELECT COALESCE(MAX(version), 0) FROM schema_version").fetchone()[0]
            for version, sql in MIGRATIONS:
                if version > current:
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
        g.db = connect(current_app.config["DATABASE"])
    return g.db


def close_db(_exc=None):
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()


def record_audit(conn, org_id, user_id, action, summary, industry_id=None, rule_key=None, before=None, after=None):
    conn.execute(
        "INSERT INTO audit (org_id, user_id, at, action, industry_id, rule_key, before, after, summary)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (org_id, user_id, now_iso(), action, industry_id, rule_key, before, after, summary),
    )
