"""Running it: backups and the restore drill, schema upgrades on real data,
long exports, Autopilot's emails and a reproducible dashboard build.

Each test here is a fix, shown failing before it was made."""

import glob
import hashlib
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest
from datetime import timedelta
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from omniarmor_app import autopilot, create_app, jobs, views  # noqa: E402
from omniarmor_app.autopilot import Finding  # noqa: E402
from omniarmor_app.db import MIGRATIONS, SCHEMA_VERSION, connect, iso, migrate, utcnow  # noqa: E402
from omniarmor_app.version import __version__  # noqa: E402
from test_webapp import PASSWORD, AppTestCase  # noqa: E402


# --- Backups and the restore drill ------------------------------------------------------

class TestBackupDrill(AppTestCase):
    def readings(self, path):
        conn = connect(path)
        try:
            return {r["rule_key"]: r["value_num"] for r in conn.execute("SELECT rule_key, value_num FROM items")}
        finally:
            conn.close()

    def test_the_daily_backup_restores_by_the_documented_steps(self):
        """docs/OPERATIONS.md, section 4: stop the app, copy the backup over
        DATABASE_PATH, delete the -wal and -shm files, start the app."""
        self.signup(industries=(1,))
        self.change(1, "annual_mvr_review", value="12")
        cfg = dict(self.app.config)
        result = jobs.run_daily(cfg, force=True)
        self.assertNotIn("failed", result)
        backups = [f for f in os.listdir(cfg["BACKUP_DIR"]) if f.startswith("omniarmor-") and f.endswith(".db")]
        self.assertEqual(len(backups), 1, os.listdir(cfg["BACKUP_DIR"]))
        backup = os.path.join(cfg["BACKUP_DIR"], backups[0])
        # The backup is one file, checked, with nothing beside it.
        self.assertEqual(sorted(os.listdir(cfg["BACKUP_DIR"])), backups)
        check = sqlite3.connect(backup)
        self.assertEqual(check.execute("PRAGMA quick_check").fetchone()[0], "ok")
        self.assertEqual(check.execute("PRAGMA journal_mode").fetchone()[0], "delete")
        check.close()

        # Work after the backup, which the restore will undo.
        self.change(1, "annual_mvr_review", value="200")
        self.assertEqual(self.readings(self.db_path)["annual_mvr_review"], 200)

        # 1. Stop the app (the test client holds no connection between requests).
        # 2. Copy the backup over the database. 3. Delete -wal and -shm.
        shutil.copyfile(backup, self.db_path)
        for side in ("-wal", "-shm"):
            if os.path.exists(self.db_path + side):
                os.remove(self.db_path + side)
        # 4. Start the app again.
        app = create_app(TESTING=True, DATABASE=self.db_path, SCHEDULER_ENABLED=False, BACKUP_DIR=cfg["BACKUP_DIR"])
        client = app.test_client()
        self.assertEqual(client.get("/healthz").get_json(),
                         {"status": "ok", "schema": SCHEMA_VERSION, "version": __version__})
        self.assertEqual(self.readings(self.db_path)["annual_mvr_review"], 12)
        with client.session_transaction() as s:
            s["_csrf"] = "t"
        signed_in = client.post("/login", data={"email": "owner@example.com", "password": PASSWORD, "csrf_token": "t"})
        self.assertEqual(signed_in.status_code, 302)
        page = client.get("/app/industry/1").data.decode()
        self.assertIn("12 days", page)
        conn = connect(self.db_path)
        self.assertEqual(conn.execute("PRAGMA integrity_check").fetchone()[0], "ok")
        conn.close()

    def test_a_backup_that_fails_half_way_is_not_kept_as_todays(self):
        """A copy that failed half-way (a full disk) stayed under the real name.
        Every later run that day took it for today's backup, Autopilot saw a
        fresh one, and a restore found a broken file."""
        self.signup(industries=(1,))
        cfg = dict(self.app.config)
        real_connect = sqlite3.connect

        class DiskFills:
            """The live database, whose copy runs out of room part-way."""
            def __init__(self, path):
                self.conn = real_connect(path)

            def backup(self, target):
                target.execute("CREATE TABLE half (x)")
                target.commit()
                raise sqlite3.OperationalError("database or disk is full")

            def close(self):
                self.conn.close()

        def connect_for_backup(path, *a, **kw):
            # The app's own connections (db.connect) pass a timeout; the backup's don't.
            return DiskFills(path) if path == cfg["DATABASE"] and not a and not kw else real_connect(path, *a, **kw)

        with mock.patch.object(jobs.sqlite3, "connect", side_effect=connect_for_backup):
            result = jobs.run_daily(cfg, force=True)
        self.assertIn("failed=backup", result)
        self.assertEqual(os.listdir(cfg["BACKUP_DIR"]), [])  # nothing half-made is left
        # The retry ten minutes later makes a real backup.
        result = jobs.run_daily(cfg, force=True)
        self.assertNotIn("failed", result)
        made = [f for f in os.listdir(cfg["BACKUP_DIR"]) if f.endswith(".db")]
        self.assertEqual(len(made), 1)
        check = sqlite3.connect(os.path.join(cfg["BACKUP_DIR"], made[0]))
        self.assertIsNotNone(check.execute("SELECT 1 FROM users").fetchone())
        check.close()

    def test_a_copy_left_by_a_server_that_stopped_mid_backup_is_cleared(self):
        cfg = dict(self.app.config)
        os.makedirs(cfg["BACKUP_DIR"], exist_ok=True)
        left = os.path.join(cfg["BACKUP_DIR"], "omniarmor-20260101-110000-000000.db" + jobs.PARTIAL)
        with open(left, "wb") as f:
            f.write(b"half")
        old = time.time() - 2 * 3600
        os.utime(left, (old, old))
        self.assertIsNotNone(jobs.backup_database(cfg, fresh=True))
        self.assertFalse(os.path.exists(left))
        self.assertFalse(autopilot.latest_backup(cfg).endswith(jobs.PARTIAL))


# --- Schema upgrades on a database with real data -----------------------------------------

class TestRestoreRehearsal(AppTestCase):
    """docs/OPERATIONS.md, section 4, the 10-minute checklist: a backup made
    with the app's own command, restored into a fresh copy, and the app
    started on it with sign-in, checks, the Academy and the audit trail all
    there. Then the daily job runs on the restored copy and sends nobody the
    day's digest a second time."""

    def test_backup_restore_and_the_app_works(self):
        self.signup(industries=(1,))
        self.change(1, "annual_mvr_review", date="2020-01-02")      # overdue: today's digest has it
        self.change(1, "eld_in_use", answer="yes")
        self.post("/app/academy/learners", {"nickname": "Sam", "avatar": "rocket", "track": "launchpad"})
        with self.db() as conn:
            lid = conn.execute("SELECT id FROM learners").fetchone()[0]
        page = self.client.get(f"/app/academy/{lid}/world/1/stage/1").data.decode()
        attempt = re.search(r'name="attempt" value="(\d+)"', page).group(1)
        answers = {q: "0" for q in set(re.findall(r'name="(q\d+)"', page))}
        self.assertEqual(self.post(f"/app/academy/{lid}/world/1/stage/1", dict(answers, attempt=attempt)).status_code,
                         200)
        cfg = dict(self.app.config, DAILY_JOB_HOUR_UTC=0)
        self.assertNotIn("failed", jobs.run_daily(cfg))               # today's digest, then the daily backup
        daily = sorted(glob.glob(os.path.join(cfg["BACKUP_DIR"], "omniarmor-*.db")))
        self.assertEqual(len(daily), 1)
        made = self.app.test_cli_runner().invoke(args=["backup"])     # and one by hand, the same way
        self.assertEqual(made.exit_code, 0, made.output)
        self.assertTrue(os.path.basename(made.output.strip()).startswith("omniarmor-"), made.output)
        # The daily one: the copy holds the day's claim, not yet finished.
        backup = daily[0]
        with self.db() as conn:
            audit_rows = conn.execute("SELECT COUNT(*) FROM audit").fetchone()[0]
            sent = conn.execute("SELECT COUNT(*) FROM notifications WHERE kind = 'reminder'").fetchone()[0]
        self.assertEqual(sent, 1)

        # Restore into a fresh copy, beside the old database, and start the app on it.
        restored = os.path.join(self.tmp.name, "restored", "omniarmor.db")
        os.makedirs(os.path.dirname(restored))
        shutil.copyfile(backup, restored)
        check = sqlite3.connect(restored)
        self.assertEqual(check.execute("PRAGMA integrity_check").fetchone()[0], "ok")
        # Taken while the daily job held its lock, the copy holds no lock.
        self.assertEqual(check.execute("SELECT COUNT(*) FROM job_locks").fetchone()[0], 0)
        check.close()
        app = create_app(TESTING=True, DATABASE=restored, SCHEDULER_ENABLED=False, BACKUP_DIR=cfg["BACKUP_DIR"])
        client = app.test_client()
        self.assertEqual(client.get("/healthz").get_json()["status"], "ok")
        with client.session_transaction() as s:
            s["_csrf"] = "t"
        signed_in = client.post("/login", data={"email": "owner@example.com", "password": PASSWORD, "csrf_token": "t"})
        self.assertEqual(signed_in.status_code, 302)
        industry = client.get("/app/industry/1").data.decode()
        self.assertIn("2020-01-02", industry)
        self.assertIn("Sam", client.get(f"/app/academy/{lid}/progress").data.decode())
        vault = client.get("/app/audit").data.decode()
        self.assertIn("Workspace created", vault)
        self.assertIn("Pat Owner", vault)
        conn = connect(restored)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM audit").fetchone()[0], audit_rows)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM learner_progress").fetchone()[0], 1)
        conn.close()

        # The restored copy's claim on today goes stale (here at once): the
        # daily job runs again, and today's digest is not sent twice.
        restored_cfg = dict(app.config, DAILY_JOB_HOUR_UTC=0)
        with mock.patch.object(jobs, "STALE_AFTER", timedelta(seconds=-60)):
            result = jobs.run_daily(restored_cfg)
        self.assertIn("digests=0", result)
        conn = connect(restored)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM notifications WHERE kind = 'reminder'").fetchone()[0], 1)
        conn.close()


class TestMigrationsTenAndEleven(unittest.TestCase):
    def test_upgrading_a_populated_version_9_database(self):
        """Migration 11 copies every person's name onto their audit rows and
        readings. Run on a copy of a database with data in it, from version 9."""
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = os.path.join(tmp.name, "v9.db")
        with mock.patch("omniarmor_app.db.MIGRATIONS", [m for m in MIGRATIONS if m[0] <= 9]):
            conn = connect(path)
            self.assertEqual(migrate(conn), 9)
        now = iso(utcnow())
        conn.executemany("INSERT INTO users (id, email, name, password_hash, created_at) VALUES (?, ?, ?, 'x', ?)",
                         [(i, f"u{i}@example.com", f"Person {i}", now) for i in range(1, 21)])
        conn.executemany("INSERT INTO orgs (id, name, created_at) VALUES (?, ?, ?)",
                         [(i, f"Company {i}", now) for i in range(1, 11)])
        conn.executemany("INSERT INTO items (org_id, industry_id, rule_key, value_num, updated_at, updated_by)"
                         " VALUES (?, 1, ?, 5, ?, ?)", [(o, f"k{k}", now, (o + k) % 20 + 1)
                                                         for o in range(1, 11) for k in range(30)])
        conn.executemany("INSERT INTO audit (org_id, user_id, at, action, summary) VALUES (?, ?, ?, 'reading', 's')",
                         [(n % 10 + 1, None if n % 97 == 0 else n % 20 + 1, now) for n in range(20000)])
        conn.commit()
        started = time.monotonic()
        self.assertEqual(migrate(conn), SCHEMA_VERSION)
        took = time.monotonic() - started
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM audit WHERE user_id IS NOT NULL AND user_name IS NULL")
                         .fetchone()[0], 0)
        self.assertEqual(conn.execute("SELECT user_name FROM audit WHERE user_id = 7 LIMIT 1").fetchone()[0], "Person 7")
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM audit WHERE user_id IS NULL AND user_name IS NOT NULL")
                         .fetchone()[0], 0)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM items WHERE updated_by_name IS NULL").fetchone()[0], 0)
        self.assertIn("academy_ends_at", [r[1] for r in conn.execute("PRAGMA table_info(orgs)")])
        self.assertEqual(conn.execute("PRAGMA integrity_check").fetchone()[0], "ok")
        # Start-up runs it before the server answers; it must stay far inside
        # gunicorn's 60-second start-up limit (1.1 million audit rows: about 2 s).
        self.assertLess(took, 20)
        conn.close()


class TestMigrationTwelve(unittest.TestCase):
    def test_the_audit_index_on_a_populated_version_11_database(self):
        """Deep audit pages took about 1.5 s at half a million rows: the only
        index had the time but not the id the trail is also sorted by, so each
        page sorted again and read every row it skipped from the table.
        Migration 12 adds an index holding the whole sort order. Run on a
        database with data in it, from version 11."""
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = os.path.join(tmp.name, "v11.db")
        with mock.patch("omniarmor_app.db.MIGRATIONS", [m for m in MIGRATIONS if m[0] <= 11]):
            conn = connect(path)
            self.assertEqual(migrate(conn), 11)
        self.addCleanup(conn.close)
        now = iso(utcnow())
        conn.executemany("INSERT INTO users (id, email, name, password_hash, created_at) VALUES (?, ?, ?, 'x', ?)",
                         [(i, f"u{i}@example.com", f"Person {i}", now) for i in range(1, 6)])
        conn.executemany("INSERT INTO orgs (id, name, created_at) VALUES (?, ?, ?)",
                         [(i, f"Company {i}", now) for i in (1, 2)])
        # Several rows a second, as a busy workspace writes them, so the id
        # decides the order within each second.
        conn.executemany("INSERT INTO audit (org_id, user_id, user_name, at, action, summary)"
                         " VALUES (?, ?, ?, ?, 'reading', ?)",
                         [(n % 2 + 1, n % 6 or None, f"Person {n % 6}" if n % 6 else None,
                           f"2026-01-01T00:{n // 600 % 60:02d}:{n // 10 % 60:02d}+00:00", f"row {n}")
                          for n in range(30000)])
        conn.commit()
        page = views.AUDIT_QUERY + " LIMIT ? OFFSET ?"
        before = [tuple(r) for r in conn.execute(page, (1, 101, 14000))]
        plan = " / ".join(r["detail"] for r in conn.execute("EXPLAIN QUERY PLAN " + page, (1, 101, 14000)))
        self.assertIn("TEMP B-TREE", plan)

        self.assertEqual(migrate(conn), SCHEMA_VERSION)
        indexes = {r["name"]: r["sql"] for r in conn.execute("SELECT name, sql FROM sqlite_master WHERE type = 'index'"
                                                              " AND tbl_name = 'audit'")}
        self.assertIn("audit_org_at_id", indexes)
        self.assertNotIn("audit_org_at", indexes)  # replaced; the new one starts with the same columns
        plan = [r["detail"] for r in conn.execute("EXPLAIN QUERY PLAN " + page, (1, 101, 14000))]
        self.assertTrue(any("audit USING INDEX audit_org_at_id (org_id=?)" in step for step in plan), plan)
        self.assertFalse(any("TEMP B-TREE" in step for step in plan), plan)
        # The full export walks the same index.
        plan = [r["detail"] for r in conn.execute("EXPLAIN QUERY PLAN " + views.AUDIT_QUERY, (1,))]
        self.assertFalse(any("TEMP B-TREE" in step for step in plan), plan)
        # Same rows, same order.
        self.assertEqual([tuple(r) for r in conn.execute(page, (1, 101, 14000))], before)
        self.assertEqual(len(before), 101)
        ids = [r["id"] for r in conn.execute(views.AUDIT_QUERY, (2,))]
        self.assertEqual(len(ids), 15000)
        ats = {r["id"]: r["at"] for r in conn.execute("SELECT id, at FROM audit WHERE org_id = 2")}
        self.assertEqual(ids, sorted(ids, key=lambda i: (ats[i], i), reverse=True))
        self.assertEqual(conn.execute("PRAGMA integrity_check").fetchone()[0], "ok")


# --- Long exports --------------------------------------------------------------------------

class TestCsvExportsStream(AppTestCase):
    def test_a_long_audit_trail_is_sent_as_it_is_written(self):
        """The whole CSV was built in memory first: half a million audit rows
        took one export to 830 MB, over the smallest plans' memory."""
        self.signup(industries=(1,))
        with self.db() as conn:
            org_id = conn.execute("SELECT id FROM orgs").fetchone()[0]
            conn.executemany("INSERT INTO audit (org_id, at, action, summary) VALUES (?, ?, 'reading', ?)",
                             [(org_id, f"2026-01-01T00:00:{n % 60:02d}+00:00", f"row {n}") for n in range(2500)])
            conn.commit()
        with mock.patch.object(views, "CSV_CHUNK_ROWS", 500):
            response = self.client.get("/app/audit.csv", buffered=False)
            self.assertTrue(response.is_streamed)
            chunks = [c for c in response.response if c]
            response.close()
        self.assertGreater(len(chunks), 4)
        text = b"".join(c if isinstance(c, bytes) else c.encode() for c in chunks).decode()
        lines = text.splitlines()
        self.assertEqual(lines[0], "Time (UTC),Person,Action,Industry,Check,Before,After,Summary")
        self.assertEqual(len(lines), 1 + 2500 + 1)  # header, the rows, "Workspace created"
        self.assertEqual(len(set(lines)), len(lines))
        # The report export still works the same way.
        report = self.client.get("/app/report.csv")
        self.assertEqual(report.status_code, 200)
        self.assertTrue(report.data.decode().startswith("Industry,Check,Status"))
        self.assertIn("attachment", report.headers["Content-Disposition"])


    def test_the_server_runs_pages_in_threads(self):
        """gunicorn's 60-second timeout suits the slowest page only because the
        pages run in threads (the gthread worker): there it restarts a stuck
        worker and never cuts a request off."""
        with open(os.path.join(ROOT, "Dockerfile"), encoding="utf-8") as f:
            dockerfile = f.read()
        self.assertIn("--threads ${WEB_THREADS}", dockerfile)
        self.assertIn("--timeout 60", dockerfile)
        threads = int(dockerfile.split("WEB_THREADS=")[1].split()[0])
        self.assertGreater(threads, 1)


# --- Autopilot never loops on the operator's inbox -----------------------------------------

class TestAutopilotEmails(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db_path = os.path.join(self.tmp.name, "test.db")
        app = create_app(TESTING=True, DATABASE=self.db_path, SCHEDULER_ENABLED=False,
                         BACKUP_DIR=os.path.join(self.tmp.name, "backups"), BASE_URL="https://omniarmor.test",
                         SMTP_HOST="smtp.test", OPERATOR_EMAIL="owner@omniarmor.test")
        self.cfg = dict(app.config)
        self.sent = []
        patcher = mock.patch("omniarmor_app.autopilot.send_email",
                             side_effect=lambda cfg, to, subject, body, kind=None: self.sent.append(subject) or ("sent", None))
        patcher.start()
        self.addCleanup(patcher.stop)
        self.conn = connect(self.db_path)
        self.addCleanup(self.conn.close)

    def crash(self, signature, times):
        self.conn.executemany("INSERT INTO app_errors (at, path, error, signature, location, trace) VALUES (?, '/x', ?, ?, 'here', '')",
                              [(iso(utcnow()), f"Error {signature}", signature)] * times)
        self.conn.commit()

    def test_a_reported_bug_pushed_out_of_the_top_five_is_not_called_fixed(self):
        for n, sig in enumerate("abcde"):
            self.crash(sig, 10 + n)
        autopilot.report(self.conn, self.cfg, autopilot.find_problems(self.conn, self.cfg))
        self.assertEqual(len(self.sent), 5)
        # A sixth bug overtakes "a"; "a" is still happening.
        self.crash("f", 40)
        autopilot.report(self.conn, self.cfg, autopilot.find_problems(self.conn, self.cfg))
        # "a" climbs back over another one, and so on, pass after pass.
        for _ in range(5):
            self.crash("a", 50)
            autopilot.report(self.conn, self.cfg, autopilot.find_problems(self.conn, self.cfg))
        self.assertEqual([s for s in self.sent if "Fixed" in s], [])
        self.assertEqual(len(self.sent), 6)  # the five, then the new one

    def test_a_problem_flapping_at_its_limit_is_not_emailed_every_pass(self):
        """Free disk space hovering at 1 GB was "low", "Fixed", "low" again, an
        email each 10 minutes."""
        low = [Finding("disk", "The server is running out of disk space", "0.9 GB free", "Make the disk bigger.")]
        for n in range(12):  # two hours of passes
            autopilot.report(self.conn, self.cfg, low if n % 2 == 0 else [])
        self.assertEqual(self.sent, ["[OmniArmor] The server is running out of disk space",
                                     "[OmniArmor] Fixed: The server is running out of disk space"])
        # Still on the record, every time.
        levels = [r[0] for r in self.conn.execute("SELECT level FROM autopilot_events WHERE check_key = 'disk' ORDER BY id")]
        self.assertEqual(levels, ["alert", "resolved"] * 6)
        # Clear for over an hour, then back: that is news again.
        self.conn.execute("UPDATE autopilot_events SET at = ?", (iso(utcnow() - timedelta(hours=2)),))
        self.conn.commit()
        autopilot.report(self.conn, self.cfg, low)
        self.assertEqual(self.sent[-1], "[OmniArmor] The server is running out of disk space")
        autopilot.report(self.conn, self.cfg, [])
        self.assertEqual(self.sent[-1], "[OmniArmor] Fixed: The server is running out of disk space")

    def test_never_more_than_ten_emails_an_hour(self):
        many = [Finding(f"bug:{n:04d}", f"Bug {n}") for n in range(25)]
        autopilot.report(self.conn, self.cfg, many)
        autopilot.report(self.conn, self.cfg, [])
        self.assertEqual(len(self.sent), autopilot.MAX_EMAILS_PER_HOUR)
        # Every one is still on the record.
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM autopilot_events").fetchone()[0], 50)


# --- The dashboard build ---------------------------------------------------------------------

class TestDashboardBuildIsReproducible(unittest.TestCase):
    def test_the_same_catalog_gives_the_same_bytes(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        digests = set()
        for seed in ("0", "1", "4242"):
            out = os.path.join(tmp.name, f"index-{seed}.html")
            env = dict(os.environ, PYTHONHASHSEED=seed)
            subprocess.run([sys.executable, "-c", "import sys; sys.path.insert(0, 'dashboard'); import build_dashboard;"
                            f" build_dashboard.build({out!r})"], cwd=ROOT, env=env, check=True)
            with open(out, "rb") as f:
                digests.add(hashlib.sha256(f.read()).hexdigest())
        with open(os.path.join(ROOT, "dashboard", "index.html"), "rb") as f:
            committed = f.read()
        self.assertEqual(digests, {hashlib.sha256(committed).hexdigest()})
        self.assertNotIn(b"\r", committed)

    def test_it_writes_plain_newlines_on_any_computer(self):
        """Text mode writes "\\r\\n" on Windows, so a build there differed from
        the committed file in every line."""
        sys.path.insert(0, os.path.join(ROOT, "dashboard"))
        import build_dashboard
        opened = []
        real_open = open

        def recording_open(*args, **kwargs):
            if "w" in (args[1:2] or (kwargs.get("mode", "r"),))[0]:
                opened.append(kwargs)
            return real_open(*args, **kwargs)

        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        with mock.patch("builtins.open", side_effect=recording_open):
            build_dashboard.build(os.path.join(tmp.name, "index.html"))
        self.assertEqual([kw.get("newline") for kw in opened], ["\n"])


if __name__ == "__main__":
    unittest.main()
