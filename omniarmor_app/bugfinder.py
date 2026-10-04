# -*- coding: utf-8 -*-
"""Autopilot's bug finder. It looks for bugs three ways:

1. Every crash is fingerprinted: the kind of error plus the place in our code
   where it happened. A fingerprint seen for the first time is a new bug, and
   Autopilot emails it with the page, the code location and the traceback.
2. Once a day it runs a self-test: it starts a private copy of the app on an
   empty, throwaway database and clicks through the main paths (sign up,
   compliance pages, reports, the Academy: add a kid, play a level). Real
   data is never touched.
3. Once a day it checks the Academy's generated quizzes and the database for
   things that should never happen. Data slips it can repair safely (a stray
   row, a star count out of range) it repairs; anything else is reported.
"""

import hashlib
import os
import random
import tempfile
import traceback

APP_DIR = os.path.dirname(os.path.abspath(__file__))


# --- 1. Crash fingerprints ---------------------------------------------------------------

def fingerprint(exc):
    """(signature, location, trace) for an exception. The signature stays the
    same when the bug happens again, even after unrelated edits move line numbers."""
    frames = traceback.extract_tb(exc.__traceback__) if exc.__traceback__ else []
    ours = [f for f in frames if os.path.abspath(f.filename).startswith(APP_DIR)]
    frame = (ours or frames or [None])[-1]
    kind = type(exc).__name__
    if frame is None:
        location, place = "unknown", "unknown"
    else:
        name = os.path.relpath(frame.filename, os.path.dirname(APP_DIR)) if ours else os.path.basename(frame.filename)
        location = f"{name}:{frame.lineno} in {frame.name}"
        place = f"{name}:{frame.name}"
    signature = hashlib.sha1(f"{kind}|{place}".encode()).hexdigest()[:12]
    trace = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    return signature, location, trace[-3000:]


def new_bugs(conn, since, limit=5):
    """Crash fingerprints seen since a time: [(signature, count, location, error, paths, trace, first_seen)]."""
    rows = conn.execute(
        "SELECT signature, COUNT(*) AS n, MAX(id) AS last_id FROM app_errors WHERE at >= ? AND signature != ''"
        " GROUP BY signature ORDER BY n DESC", (since,)).fetchall()
    found = []
    for r in rows:
        last = conn.execute("SELECT * FROM app_errors WHERE id = ?", (r["last_id"],)).fetchone()
        paths = [p[0] for p in conn.execute("SELECT DISTINCT path FROM app_errors WHERE signature = ? AND at >= ? LIMIT 5",
                                            (r["signature"], since))]
        first = conn.execute("SELECT MIN(at) FROM app_errors WHERE signature = ?", (r["signature"],)).fetchone()[0]
        found.append((r["signature"], r["n"], last["location"], last["error"], paths, last["trace"], first))
    return found[:limit], max(0, len(found) - limit)


# --- 2. Self-test --------------------------------------------------------------------------

class SelfTestFailure(Exception):
    def __init__(self, step, detail):
        super().__init__(f"{step}: {detail}")
        self.step, self.detail = step, detail


def self_test():
    """Clicks through the main paths on a throwaway copy of the app. Returns the
    list of steps it passed; raises SelfTestFailure on the first broken one."""
    from . import academy, create_app
    from .db import connect
    from .tracking import org_industry_ids

    passed = []
    with tempfile.TemporaryDirectory(prefix="omniarmor-selftest-") as tmp:
        db_path = os.path.join(tmp, "selftest.db")
        app = create_app(TESTING=True, DATABASE=db_path, SCHEDULER_ENABLED=False, AUTOPILOT_ENABLED=False,
                         BACKUP_DIR=os.path.join(tmp, "backups"), SMTP_HOST="", STRIPE_SECRET_KEY="",
                         ENV_NAME="development", SECRET_KEY="selftest-" + os.urandom(8).hex())
        client = app.test_client()

        def token():
            # Signing in starts a fresh session, so read the form token each time.
            with client.session_transaction() as s:
                return s.setdefault("_csrf", "selftest-" + os.urandom(8).hex())

        def step(name, method, path, expect=(200,), data=None):
            try:
                if method == "GET":
                    response = client.get(path)
                else:
                    response = client.post(path, data=dict(data or {}, csrf_token=token()))
            except Exception as exc:  # the page crashed
                _, location, _ = fingerprint(exc)
                raise SelfTestFailure(name, f"{method} {path} crashed with {type(exc).__name__}: {exc} ({location})")
            if response.status_code not in expect:
                raise SelfTestFailure(name, f"{method} {path} answered {response.status_code}, expected {expect}")
            passed.append(name)
            return response

        step("Home page", "GET", "/")
        step("Industry pages", "GET", "/industries")
        step("Health check", "GET", "/healthz")
        step("Sign up", "POST", "/signup", (302,), {
            "name": "Self Test", "email": "selftest@example.com", "password": "selftest password 123",
            "org_name": "Selftest Co", "timezone": "UTC", "industries": ["1", "18"]})
        step("HQ overview", "GET", "/app")
        step("An industry's checks", "GET", "/app/industry/1")
        step("Compliance report", "GET", "/app/report")
        step("Report CSV", "GET", "/app/report.csv")
        step("Audit log", "GET", "/app/audit")
        step("Reminders log", "GET", "/app/notifications")
        step("Settings", "GET", "/app/settings")
        step("Armo status", "GET", "/app/armo/status")
        step("Academy home", "GET", "/app/academy")
        added = step("Add a learner", "POST", "/app/academy/learners", (302,), {"nickname": "Tester", "avatar": "rocket"})
        conn = connect(db_path)
        try:
            learner = conn.execute("SELECT id, org_id FROM learners").fetchone()
            industry_ids = org_industry_ids(conn, learner["org_id"])
        finally:
            conn.close()
        lid = learner["id"]
        if added.headers.get("Location", "").endswith("/track"):
            step("Pick a track", "POST", f"/app/academy/{lid}/track", (302,), {"track": "launchpad"})
        step("Level map", "GET", f"/app/academy/{lid}")
        step("World page", "GET", f"/app/academy/{lid}/world/1")
        step("Open a level", "GET", f"/app/academy/{lid}/world/1/stage/1")
        t = academy.TRACKS["launchpad"]
        questions = academy.quiz(t, 1, 1, "Selftest Co", industry_ids, academy.attempt_seed(lid, t.key, 1, 1, 1))
        answers = {f"q{i}": str(q.answer) for i, q in enumerate(questions)}
        step("Finish a level", "POST", f"/app/academy/{lid}/world/1/stage/1", (200, 302), dict(answers, attempt="1"))
        conn = connect(db_path)
        try:
            stars = conn.execute("SELECT best_stars FROM learner_progress WHERE learner_id = ? AND level = ?",
                                 (lid, academy.level_id(t, 1, 1))).fetchone()
        finally:
            conn.close()
        if not stars or stars[0] != 3:
            raise SelfTestFailure("Finish a level", "all answers were right but the level wasn't saved with 3 stars")
        passed.append("Level saved with 3 stars")
        step("Practice", "GET", f"/app/academy/{lid}/practice")
        step("Friends", "GET", f"/app/academy/{lid}/friends")
        step("Academy plan", "GET", "/app/academy/plan")
        step("Sign out", "POST", "/logout", (302,))
    return passed


# --- 3. Content and data checks ----------------------------------------------------------

def check_content(samples=3, seed=None):
    """Generates quizzes across every track and world and checks each one makes
    sense: a real right answer, different options, a reachable pass mark."""
    from . import academy
    rng = random.Random(seed)
    problems = []
    for t in academy.TRACK_LIST:
        for w in t.worlds:
            n = t.stages(w)
            for stage in {1, n} | {rng.randint(1, n) for _ in range(samples)}:
                where = f"{t.name}, {w.title}, stage {stage}"
                try:
                    qs = academy.quiz(t, w.number, stage, "Acme", [1, 18], f"check-{rng.random()}")
                except Exception as exc:
                    problems.append(f"{where}: quiz crashed ({type(exc).__name__}: {exc})")
                    continue
                if len(qs) != academy.question_count(t, w, stage):
                    problems.append(f"{where}: {len(qs)} questions, expected {academy.question_count(t, w, stage)}")
                if academy.pass_mark(t, w, stage) > len(qs):
                    problems.append(f"{where}: pass mark is higher than the number of questions")
                for q in qs:
                    if not (q.prompt and q.explain) or not 0 <= q.answer < len(q.options) \
                            or len(set(q.options)) != len(q.options):
                        problems.append(f"{where}: broken question {q.prompt[:60]!r}")
    return problems


def repair_data(conn):
    """Fixes data slips that are safe to fix. Returns a list of what it fixed."""
    from . import academy
    fixed = []
    orphans = conn.execute("PRAGMA foreign_key_check").fetchall()
    removable = {"learner_progress", "learner_days", "learner_mistakes", "learner_friends", "join_codes",
                 "friend_codes", "reminder_marks", "memberships", "org_industries", "items"}
    by_table = {}
    for table, rowid, _parent, _fk in orphans:
        if table in removable and rowid is not None:
            conn.execute(f"DELETE FROM {table} WHERE rowid = ?", (rowid,))
            by_table[table] = by_table.get(table, 0) + 1
    for table, n in by_table.items():
        fixed.append(f"Removed {n} leftover row{'s' if n != 1 else ''} in {table} that pointed at deleted records.")
    n = conn.execute("UPDATE learner_progress SET best_stars = MIN(MAX(best_stars, 0), 3)"
                     " WHERE best_stars NOT BETWEEN 0 AND 3").rowcount
    if n:
        fixed.append(f"Corrected {n} star count{'s that were' if n != 1 else ' that was'} outside 0 to 3.")
    tracks = tuple(academy.TRACKS)
    n = conn.execute(f"UPDATE learners SET track = ? WHERE track NOT IN ({','.join('?' * len(tracks))})",
                     (academy.DEFAULT_TRACK, *tracks)).rowcount
    if n:
        fixed.append(f"Moved {n} learner{'s' if n != 1 else ''} with an unknown track back to {academy.TRACKS[academy.DEFAULT_TRACK].name}.")
    conn.commit()
    return fixed


def data_problems(conn):
    """Things in the database a person should look at (not safe to fix automatically)."""
    leftover = [r for r in conn.execute("PRAGMA foreign_key_check").fetchall()]
    problems = []
    if leftover:
        tables = sorted({r[0] for r in leftover})
        problems.append(f"{len(leftover)} rows point at records that no longer exist (tables: {', '.join(tables)}).")
    return problems
