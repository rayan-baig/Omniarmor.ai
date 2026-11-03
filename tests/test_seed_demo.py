"""The demo workspace (flask --app wsgi seed-demo): made-up, realistic, and
never mixed into a database that holds anything."""

import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from omniarmor_app import create_app, demo  # noqa: E402
from omniarmor_app.db import connect  # noqa: E402
from omniarmor_app.jobs import backup_database  # noqa: E402
from omniarmor_app.tracking import states_for_org  # noqa: E402
from test_webapp import AppTestCase  # noqa: E402


class SeedCase(AppTestCase):
    def seed(self, *args):
        return self.app.test_cli_runner().invoke(args=["seed-demo", *args])

    def counts(self, path):
        conn = connect(path)
        try:
            return {t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in ("users", "orgs", "learners")}
        finally:
            conn.close()


class TestSeedDemo(SeedCase):
    """One seeded database, looked at from every side."""

    @classmethod
    def setUpClass(cls):
        import tempfile
        cls.shared = tempfile.TemporaryDirectory()
        cls.path = os.path.join(cls.shared.name, "demo.db")
        app = create_app(TESTING=True, DATABASE=os.path.join(cls.shared.name, "app.db"), SCHEDULER_ENABLED=False,
                         BASE_URL="https://omniarmor.test")
        cls.result = app.test_cli_runner().invoke(args=["seed-demo", "--force", cls.path])

    @classmethod
    def tearDownClass(cls):
        cls.shared.cleanup()

    def demo_client(self):
        app = create_app(TESTING=True, DATABASE=self.path, SCHEDULER_ENABLED=False,
                         BACKUP_DIR=os.path.join(self.shared.name, "demo-backups"), BASE_URL="https://omniarmor.test")
        return app.test_client()

    def password(self):
        return re.search(r"Password for both: (\S+)", self.result.output).group(1)

    def sign_in(self, email=demo.OWNER[1]):
        client = self.demo_client()
        with client.session_transaction() as s:
            s["_csrf"] = "t"
        response = client.post("/login", data={"email": email, "password": self.password(), "csrf_token": "t"})
        self.assertEqual(response.status_code, 302, response.get_data(as_text=True)[:300])
        return client

    def test_it_prints_the_sign_in_details(self):
        self.assertEqual(self.result.exit_code, 0, self.result.output)
        out = self.result.output
        self.assertIn("Juniper Lane Pharmacy", out)
        self.assertIn("https://omniarmor.test/login", out)
        self.assertIn(demo.OWNER[1], out)
        self.assertIn(demo.PHARMACIST[1], out)
        self.assertRegex(out, r"Password for both: \S{8,}")
        self.assertIn(f"DATABASE_PATH={self.path}", out)
        self.assertIn(f"BACKUP_DIR={os.path.join(self.shared.name, 'demo-backups')}", out)

    def test_made_up_names_on_a_reserved_domain(self):
        conn = connect(self.path)
        emails = [r[0] for r in conn.execute("SELECT email FROM users")]
        conn.close()
        self.assertEqual(len(emails), 2)
        self.assertTrue(all(e.endswith("@juniperlane.example") for e in emails), emails)

    def test_two_industries_with_done_due_soon_and_overdue_checks(self):
        conn = connect(self.path)
        org = conn.execute("SELECT * FROM orgs").fetchone()
        industries = [r[0] for r in conn.execute("SELECT industry_id FROM org_industries ORDER BY industry_id")]
        self.assertEqual(industries, [demo.PHARMACY, demo.EMPLOYER])
        states = states_for_org(conn, org)
        conn.close()
        for industry_id in industries:
            levels = [s.level for s in states if s.industry_id == industry_id]
            self.assertGreaterEqual(levels.count("CLEARED"), 4, (industry_id, levels))
            self.assertGreaterEqual(levels.count("WARNING"), 1, (industry_id, levels))
            self.assertGreaterEqual(levels.count("BLOCKED"), 1, (industry_id, levels))
            self.assertGreaterEqual(levels.count("NONE"), 1, (industry_id, levels))

    def test_audit_history_over_weeks_by_both_people(self):
        conn = connect(self.path)
        rows = conn.execute("SELECT at, user_name, action FROM audit ORDER BY at").fetchall()
        conn.close()
        self.assertGreaterEqual(len(rows), 20)
        self.assertEqual({r["user_name"] for r in rows}, {demo.OWNER[0], demo.PHARMACIST[0]})
        self.assertIn("done", {r["action"] for r in rows})
        self.assertLess(rows[0]["at"][:10], rows[-1]["at"][:10])

    def test_academy_two_learners_partway_one_certificate(self):
        out = self.result.output
        self.assertRegex(out, r"Academy: Pip, \d+ levels passed, certificate: Future Owner")
        self.assertRegex(out, r"Academy: Maple, \d+ levels passed\n")
        client = self.sign_in()
        conn = connect(self.path)
        kids = {r["nickname"]: r["id"] for r in conn.execute("SELECT id, nickname FROM learners")}
        conn.close()
        self.assertEqual(set(kids), {"Pip", "Maple"})
        page = client.get(f"/app/academy/{kids['Pip']}/certificate")
        self.assertEqual(page.status_code, 200)
        self.assertIn("Future Owner of Juniper Lane Pharmacy", page.get_data(as_text=True))
        self.assertEqual(client.get(f"/app/academy/{kids['Maple']}/certificate").status_code, 302)
        progress = client.get(f"/app/academy/{kids['Maple']}/progress")
        self.assertEqual(progress.status_code, 200)

    def test_a_running_autopilot(self):
        self.assertRegex(self.result.output, r"Autopilot: ran once now\. Made a missing backup")
        conn = connect(self.path)
        fixed = conn.execute("SELECT COUNT(*) FROM autopilot_events WHERE level = 'fixed'").fetchone()[0]
        runs = conn.execute("SELECT COUNT(*) FROM job_runs WHERE job = 'daily' AND finished_at IS NOT NULL").fetchone()[0]
        slot = conn.execute("SELECT COUNT(*) FROM job_runs WHERE job = 'autopilot' AND finished_at IS NOT NULL").fetchone()[0]
        conn.close()
        self.assertGreaterEqual(fixed, 3)
        self.assertGreaterEqual(runs, 7)
        self.assertEqual(slot, 1)
        self.assertTrue(os.listdir(os.path.join(self.shared.name, "demo-backups")))

    def test_the_morning_digest_is_kept_not_sent(self):
        conn = connect(self.path)
        rows = conn.execute("SELECT status FROM notifications WHERE kind = 'reminder'").fetchall()
        conn.close()
        self.assertEqual({r["status"] for r in rows}, {"logged"})
        self.assertEqual(len(rows), 2)

    def test_both_people_can_sign_in_and_the_pages_work(self):
        for email in (demo.OWNER[1], demo.PHARMACIST[1]):
            client = self.sign_in(email)
            for path in ("/app", f"/app/industry/{demo.PHARMACY}", f"/app/industry/{demo.EMPLOYER}", "/app/audit",
                         "/app/notifications", "/app/academy", "/app/settings"):
                self.assertEqual(client.get(path).status_code, 200, (email, path))

    def test_seeding_the_same_file_again_is_refused(self):
        result = self.seed("--force", self.path)
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("already holds accounts", result.output)
        self.assertEqual(self.counts(self.path), {"users": 2, "orgs": 1, "learners": 2})


class TestRefusals(SeedCase):
    def test_refuses_a_database_with_a_customer_in_it(self):
        self.signup()
        before = self.counts(self.db_path)
        result = self.seed()
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("would mix into real data", result.output)
        self.assertEqual(self.counts(self.db_path), before)

    def test_force_must_name_a_new_database(self):
        self.signup()
        result = self.seed("--force", self.db_path)
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("must name a new database file", result.output)
        self.assertEqual(self.counts(self.db_path)["orgs"], 1)

    def test_never_into_the_live_database_in_production(self):
        app = create_app(TESTING=True, DATABASE=os.path.join(self.tmp.name, "prod.db"), SCHEDULER_ENABLED=False,
                         ENV_NAME="production", SECRET_KEY="x" * 32)
        result = app.test_cli_runner().invoke(args=["seed-demo"])
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("This is production", result.output)
        self.assertEqual(self.counts(os.path.join(self.tmp.name, "prod.db")), {"users": 0, "orgs": 0, "learners": 0})

    def test_the_check_is_made_again_inside_the_write(self):
        # demo.seed itself refuses, whatever the command checked before it.
        conn = connect(self.db_path)
        conn.execute("INSERT INTO orgs (name, created_at) VALUES ('Real Customer', '2026-11-01T00:00:00+00:00')")
        conn.commit()
        conn.close()
        with self.assertRaises(demo.NotEmpty):
            demo.seed(dict(self.app.config))
        self.assertEqual(self.counts(self.db_path), {"users": 0, "orgs": 1, "learners": 0})

    def test_a_short_password_is_refused(self):
        path = os.path.join(self.tmp.name, "new.db")
        result = self.seed("--force", path, "--password", "short")
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("at least", result.output)
        self.assertFalse(os.path.exists(path))

    def test_the_demo_never_backs_up_into_the_live_backups(self):
        # The demo file beside the app's own database, as OPERATIONS.md says
        # for production (/data/omniarmor.db and /data/omniarmor-demo.db): the
        # demo's backup used to land in the live backup folder, where the
        # live daily job took it for today's backup and made none of its own,
        # and the newest copy to restore was the demo.
        live_backups = self.app.config["BACKUP_DIR"]
        self.assertEqual(os.path.dirname(live_backups), os.path.dirname(self.db_path))
        self.signup()
        result = self.seed("--force", os.path.join(self.tmp.name, "omniarmor-demo.db"))
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertEqual(os.listdir(live_backups) if os.path.isdir(live_backups) else [], [])
        copy = backup_database(dict(self.app.config))
        conn = connect(copy)
        try:
            self.assertEqual([r[0] for r in conn.execute("SELECT name FROM orgs")], ["Acme Logistics"])
        finally:
            conn.close()

    def test_is_empty_never_creates_a_file(self):
        path = os.path.join(self.tmp.name, "nothing-here.db")
        self.assertTrue(demo.is_empty(path))
        self.assertFalse(os.path.exists(path))


if __name__ == "__main__":
    unittest.main()
