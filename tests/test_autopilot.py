"""Autopilot: fixes small problems by itself and emails the operator about big ones."""
import os
import sys
import tempfile
import unittest
from datetime import timedelta
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from omniarmor_app import academy, autopilot, bugfinder, create_app  # noqa: E402
from omniarmor_app.db import connect, iso, migrate, utcnow  # noqa: E402
from omniarmor_app.jobs import run_daily  # noqa: E402


class AutopilotTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.tmp.name, "test.db")
        self.app = create_app(TESTING=True, DATABASE=self.db_path, SCHEDULER_ENABLED=False,
                              BACKUP_DIR=os.path.join(self.tmp.name, "backups"), BASE_URL="https://omniarmor.test",
                              SMTP_HOST="smtp.test", OPERATOR_EMAIL="owner@omniarmor.test")
        self.cfg = dict(self.app.config)
        self.sent = []
        patcher = mock.patch("omniarmor_app.autopilot.send_email", side_effect=self.fake_send)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.smtp_works = True

    def tearDown(self):
        self.tmp.cleanup()

    def fake_send(self, cfg, to, subject, body):
        if not self.smtp_works:
            return "failed", "SMTPAuthenticationError: bad password"
        self.sent.append((to, subject, body))
        return "sent", None

    def db(self):
        conn = connect(self.db_path)
        migrate(conn)
        self.addCleanup(conn.close)
        return conn

    def failed_email(self, conn, minutes_ago, attempts=1):
        conn.execute("INSERT INTO notifications (created_at, kind, recipient, subject, body, status, error, attempts)"
                     " VALUES (?, 'digest', 'team@example.com', 'Due soon', 'Body', 'failed', 'timeout', ?)",
                     (iso(utcnow() - timedelta(minutes=minutes_ago)), attempts))
        conn.commit()

    def operator_mail(self):
        return [s for s in self.sent if s[0] == "owner@omniarmor.test"]

    def test_all_clear_sends_nothing(self):
        result = autopilot.run(self.cfg, force=True)
        self.assertEqual(result["problems"], [])
        self.assertEqual(self.operator_mail(), [])

    def test_failed_email_is_resent_after_backoff(self):
        conn = self.db()
        self.failed_email(conn, minutes_ago=2)     # too soon to retry
        self.failed_email(conn, minutes_ago=15)    # due for its first retry
        result = autopilot.run(self.cfg, force=True)
        self.assertEqual(result["fixed"], ["Re-sent 1 email that failed the first time."])
        statuses = [r["status"] for r in conn.execute("SELECT status FROM notifications ORDER BY id")]
        self.assertEqual(statuses, ["failed", "sent"])
        logged = conn.execute("SELECT level, title FROM autopilot_events WHERE level = 'fixed'").fetchall()
        self.assertEqual(len(logged), 1)

    def test_email_that_keeps_failing_is_reported_once(self):
        conn = self.db()
        self.smtp_works = False
        for _ in range(3):
            self.failed_email(conn, minutes_ago=60 * 10, attempts=4)   # out of retries
        result = autopilot.run(self.cfg, force=True)
        self.assertEqual([f.key for f in result["problems"]], ["email"])
        # SMTP is down, so the alert can't be emailed; it is still recorded (and logged).
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM autopilot_events WHERE level = 'alert'").fetchone()[0], 1)

    def crash(self, path="/app/report", which=0):
        """Records a real server error, raised from one of two places in the code."""
        def first_place():
            return {}["missing"]

        def second_place():
            return 1 / 0
        try:
            (first_place, second_place)[which]()
        except Exception as exc:
            autopilot.record_error(self.cfg, path, exc)

    def test_new_bug_emailed_once_reminded_daily_and_cleared(self):
        conn = self.db()
        for i in range(6):
            self.crash(f"/app/page{i}")
        autopilot.run(self.cfg, force=True)
        autopilot.run(self.cfg, force=True)
        mail = self.operator_mail()
        self.assertEqual(len(mail), 1)
        self.assertIn("Bug: KeyError: 'missing'", mail[0][1])
        self.assertIn("Happened 6 times in the last day", mail[0][2])
        self.assertIn("test_autopilot.py", mail[0][2])  # where it happened
        self.assertIn("What to do:", mail[0][2])
        # A day later and still happening: one reminder.
        conn.execute("UPDATE autopilot_events SET at = ?", (iso(utcnow() - timedelta(hours=25)),))
        conn.commit()
        self.crash()
        autopilot.run(self.cfg, force=True)
        self.assertTrue(self.operator_mail()[-1][1].startswith("[OmniArmor] Still open: Bug:"))
        # It stops happening for a day: a "Fixed" email, then silence.
        conn.execute("UPDATE app_errors SET at = ?", (iso(utcnow() - timedelta(hours=25)),))
        conn.commit()
        autopilot.run(self.cfg, force=True)
        autopilot.run(self.cfg, force=True)
        mail = self.operator_mail()
        self.assertEqual(len(mail), 3)
        self.assertTrue(mail[-1][1].startswith("[OmniArmor] Fixed: Bug:"))
        self.assertIn("hasn't happened for a day", mail[-1][2])

    def test_each_bug_gets_its_own_fingerprint(self):
        self.crash(which=0)
        self.crash(which=0)
        self.crash(which=1)
        rows = self.db().execute("SELECT signature, location FROM app_errors ORDER BY id").fetchall()
        self.assertEqual(rows[0]["signature"], rows[1]["signature"])
        self.assertNotEqual(rows[0]["signature"], rows[2]["signature"])
        self.assertIn("in first_place", rows[0]["location"])
        result = autopilot.run(self.cfg, force=True)
        self.assertEqual(len([f for f in result["problems"] if f.key.startswith("bug:")]), 2)

    def test_server_errors_are_recorded(self):
        app = create_app(TESTING=False, DATABASE=self.db_path, SCHEDULER_ENABLED=False, PROPAGATE_EXCEPTIONS=False)

        @app.route("/boom")
        def boom():
            raise RuntimeError("kaboom")
        self.assertEqual(app.test_client().get("/boom").status_code, 500)
        row = self.db().execute("SELECT path, error, location, trace FROM app_errors").fetchone()
        self.assertEqual((row["path"], row["error"]), ("/boom", "RuntimeError: kaboom"))
        self.assertIn("in boom", row["location"])
        self.assertIn("Traceback", row["trace"])

    def test_self_test_passes_on_a_healthy_app(self):
        passed = bugfinder.self_test()
        self.assertIn("Sign up", passed)
        self.assertIn("Level saved with 3 stars", passed)
        self.assertEqual(self.db().execute("SELECT COUNT(*) FROM users").fetchone()[0], 0)  # real data untouched

    def test_self_test_catches_a_broken_page(self):
        with mock.patch("omniarmor_app.views.render_template", side_effect=RuntimeError("template exploded")):
            with self.assertRaises(bugfinder.SelfTestFailure) as caught:
                bugfinder.self_test()
        self.assertEqual(caught.exception.step, "HQ overview")
        self.assertIn("crashed with RuntimeError: template exploded", caught.exception.detail)

    def test_daily_run_reports_a_failed_self_test(self):
        failure = bugfinder.SelfTestFailure("Finish a level", "POST answered 500")
        with mock.patch("omniarmor_app.bugfinder.self_test", side_effect=failure):
            result = autopilot.run(self.cfg, force=True)
        self.assertEqual([f.title for f in result["problems"]], ["Daily self-test failed at: Finish a level"])

    def test_content_check(self):
        self.assertEqual(bugfinder.check_content(samples=1, seed=3), [])
        broken = [academy.Question("Q?", ["A", "A"], 5, "why")]
        with mock.patch("omniarmor_app.academy.quiz", return_value=broken):
            problems = bugfinder.check_content(samples=0, seed=3)
        self.assertTrue(problems)
        self.assertIn("broken question", " ".join(problems))

    def test_safe_data_slips_are_repaired(self):
        conn = self.db()
        conn.execute("INSERT INTO orgs (name, created_at) VALUES ('Acme', '2026-01-01T00:00:00+00:00')")
        conn.execute("INSERT INTO learners (org_id, nickname, avatar, created_at, track) VALUES (1, 'Sam', 'rocket',"
                     " '2026-01-01T00:00:00+00:00', 'warp-speed')")
        conn.execute("INSERT INTO learner_progress (learner_id, level, best_stars) VALUES (1, 1001, 7)")
        conn.commit()
        fixed = autopilot.run(self.cfg, force=True)["fixed"]
        self.assertIn("Corrected 1 star count that was outside 0 to 3.", fixed)
        self.assertTrue(any("unknown track" in line for line in fixed))
        self.assertEqual(conn.execute("SELECT best_stars FROM learner_progress").fetchone()[0], 3)
        self.assertEqual(conn.execute("SELECT track FROM learners").fetchone()[0], "launchpad")

    def test_missing_backup_is_made(self):
        run_daily(self.cfg, force=True)
        for f in os.listdir(self.cfg["BACKUP_DIR"]):
            os.remove(os.path.join(self.cfg["BACKUP_DIR"], f))
        result = autopilot.run(self.cfg, force=True)
        self.assertTrue(any(line.startswith("Made a missing backup") for line in result["fixed"]))
        self.assertEqual(result["problems"], [])

    def test_failing_backup_is_reported(self):
        run_daily(self.cfg, force=True)
        with mock.patch("omniarmor_app.jobs.backup_database", side_effect=OSError("disk full")), \
                mock.patch("omniarmor_app.autopilot.backup_age", return_value=3 * 86400):
            result = autopilot.run(self.cfg, force=True)
        self.assertEqual([f.key for f in result["problems"]], ["backup"])
        self.assertIn("Backups are failing", self.operator_mail()[0][1])

    def test_low_disk_and_production_without_email(self):
        cfg = dict(self.cfg, ENV_NAME="production", SMTP_HOST="")
        usage = mock.Mock(total=50 * 1024 ** 3, free=200 * 1024 ** 2)
        with mock.patch("omniarmor_app.autopilot.shutil.disk_usage", return_value=usage):
            keys = {f.key for f in autopilot.find_problems(self.db(), cfg)}
        self.assertEqual(keys, {"disk", "email-off"})

    def test_one_pass_per_slot_across_processes(self):
        self.assertIsNotNone(autopilot.run(self.cfg))
        self.assertIsNone(autopilot.run(self.cfg))   # another process in the same 10 minutes skips

    def test_weekly_summary_only_when_something_happened(self):
        conn = self.db()
        self.assertFalse(autopilot.weekly_summary(conn, self.cfg))
        autopilot.record(conn, "fix", "fixed", "Re-sent 2 emails that failed the first time.")
        self.assertTrue(autopilot.weekly_summary(conn, self.cfg))
        self.assertIn("fixed 1 small thing", self.operator_mail()[0][2])

    def test_cli(self):
        runner = self.app.test_cli_runner()
        out = runner.invoke(args=["autopilot"]).output
        self.assertIn("All clear", out)
        self.assertIn("Nothing in the last 30 days", runner.invoke(args=["autopilot", "--log"]).output)


if __name__ == "__main__":
    unittest.main()
