"""Privacy-friendly usage counts: one total per feature per day, no ids, no
cookies, no third parties, shown to the operator only. And the basics every
Settings page shows: the plan, the version and how to get help."""

import os
import sys
import tempfile
import unittest
from datetime import timedelta
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from omniarmor_app import academy, usage  # noqa: E402
from omniarmor_app.catalog import rules_for  # noqa: E402
from omniarmor_app.db import MIGRATIONS, SCHEMA_VERSION, connect, iso, migrate, utcnow  # noqa: E402
from omniarmor_app.jobs import cleanup  # noqa: E402
from omniarmor_app.version import __version__  # noqa: E402
import test_academy  # noqa: E402
from test_webapp import AppTestCase, first_rule  # noqa: E402

STATS_KEY = "s3cret-stats-key"


def totals(case):
    with case.db() as conn:
        return {r["event"]: r["count"] for r in conn.execute("SELECT event, SUM(count) AS count FROM usage_counts"
                                                              " GROUP BY event")}


class TestMigrationFifteen(unittest.TestCase):
    def test_upgrading_a_populated_version_14_database(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = os.path.join(tmp.name, "v14.db")
        with mock.patch("omniarmor_app.db.MIGRATIONS", [m for m in MIGRATIONS if m[0] <= 14]):
            conn = connect(path)
            self.assertEqual(migrate(conn), 14)
        conn.execute("INSERT INTO orgs (id, name, created_at) VALUES (1, 'Acme', ?)", (iso(utcnow()),))
        conn.commit()
        self.assertGreaterEqual(SCHEMA_VERSION, 15)
        self.assertEqual(migrate(conn), SCHEMA_VERSION)
        # Only a day, a feature and a number: nothing that could say who.
        self.assertEqual([r[1] for r in conn.execute("PRAGMA table_info(usage_counts)")], ["day", "event", "count"])
        self.assertIn("notifications_kind", [r[1] for r in conn.execute("PRAGMA index_list(notifications)")])
        self.assertEqual(conn.execute("SELECT name FROM orgs").fetchone()[0], "Acme")
        self.assertEqual(migrate(conn), SCHEMA_VERSION)   # running it again changes nothing
        conn.close()


class TestCounting(AppTestCase):
    def test_signups_check_updates_bulk_updates_and_help_views(self):
        self.signup()
        self.signup(email="second@example.com", client=self.app.test_client())
        rule = first_rule(1, mode="since")
        self.change(1, rule.key, action="done_today")
        self.change(1, rule.key, action="done_today")
        yes_no = [r.key for r in rules_for(18) if r.kind == "required"][:3]
        self.post("/app/industry/18/bulk", {"bulk_action": "yes", "keys": yes_no})
        self.post("/app/industry/18/bulk", {"bulk_action": "date", "keys": yes_no, "date": "2026-01-01"})  # refused
        self.change(1, rule.key, action="save", date="not a date")                                         # refused
        self.client.get("/help")
        self.app.test_client().get("/help")
        self.assertEqual(totals(self), {"signups": 2, "checks_updated": 2 + len(yes_no), "bulk_updates": 1,
                                        "help_views": 2})

    def test_one_row_per_day_and_feature_however_many_uses(self):
        for _ in range(3):
            self.client.get("/help")
        with self.db() as conn:
            rows = conn.execute("SELECT * FROM usage_counts").fetchall()
        self.assertEqual([tuple(r) for r in rows], [(utcnow().date().isoformat(), "help_views", 3)])

    def test_no_cookie_is_set_for_counting(self):
        response = self.client.get("/help")
        self.assertNotIn("Set-Cookie", response.headers)

    def test_a_counting_problem_never_breaks_the_page(self):
        with mock.patch.object(usage, "utcnow", side_effect=RuntimeError("clock broke")), \
                self.assertLogs("omniarmor.usage", "ERROR"):
            self.assertEqual(self.client.get("/help").status_code, 200)

    def test_old_totals_are_trimmed_by_the_daily_job(self):
        with self.db() as conn:
            old = (utcnow() - timedelta(days=usage.KEEP_DAYS + 1)).date().isoformat()
            conn.execute("INSERT INTO usage_counts (day, event, count) VALUES (?, 'help_views', 5)", (old,))
            conn.execute("INSERT INTO usage_counts (day, event, count) VALUES (?, 'help_views', 1)",
                         (utcnow().date().isoformat(),))
            conn.commit()
            cleanup(conn)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM usage_counts").fetchone()[0], 1)


class TestLessonsAndCertificates(AppTestCase):
    # The Academy tests' own helpers, without running their tests again here.
    add = test_academy.TestAcademyPages.add
    learner_id = test_academy.TestAcademyPages.learner_id
    org = test_academy.TestAcademyPages.org
    mark_passed = test_academy.TestAcademyPages.mark_passed
    answer = test_academy.TestAcademyPages.answer

    def setUp(self):
        super().setUp()
        self.signup()

    def test_lessons_started_passed_and_certificates(self):
        self.add()
        lid = self.learner_id()
        self.client.get(f"/app/academy/{lid}/world/1/stage/1")
        self.answer(lid, 1, 1, right=False)
        self.answer(lid, 1, 1, right=True, attempt=2)
        self.mark_passed(lid, *[(n, 1) for n in test_academy.BASIC.topics])
        self.answer(lid, academy.FINAL_WORLD.number, 1)
        self.answer(lid, academy.FINAL_WORLD.number, 2)    # passed, but no new certificate
        counted = totals(self)
        self.assertEqual(counted["lessons_started"], 1)
        self.assertEqual(counted["lessons_passed"], 3)
        self.assertEqual(counted["certificates"], 1)


class TestOperatorOnly(AppTestCase):
    def setUp(self):
        super().setUp()
        self.app.config["OPERATOR_EMAIL"] = "owner@example.com"
        self.signup()
        self.make_operator()
        self.client.get("/help")

    def test_the_operator_sees_the_last_30_days_in_settings(self):
        page = self.client.get("/app/settings").get_data(as_text=True)
        self.assertIn("Usage, last 30 days", page)
        for _, name in usage.EVENTS:
            self.assertIn(name, page)
        self.assertEqual(page.count('<td class="num mono">'), 30)   # one row a day

    def test_nobody_else_does(self):
        other = self.app.test_client()
        self.signup(email="someone@example.com", client=other)
        self.assertNotIn("Usage, last", other.get("/app/settings").get_data(as_text=True))
        self.app.config["OPERATOR_EMAIL"] = ""
        self.assertNotIn("Usage, last", self.client.get("/app/settings").get_data(as_text=True))

    def test_in_the_stats_for_mtrx_horizyn_behind_its_key(self):
        self.app.config["STATS_KEY"] = ""
        self.assertEqual(self.app.test_client().get("/api/stats").status_code, 404)
        self.app.config["STATS_KEY"] = STATS_KEY
        self.assertEqual(self.app.test_client().get("/api/stats").status_code, 401)
        body = self.app.test_client().get("/api/stats", headers={"Authorization": f"Bearer {STATS_KEY}"}).get_json()
        self.assertEqual(set(body), {"users", "active_users", "usage"})
        self.assertEqual(len(body["usage"]["days"]), 30)
        today = body["usage"]["days"][0]
        self.assertEqual(set(today), {"day"} | {key for key, _ in usage.EVENTS})
        self.assertEqual((today["signups"], today["help_views"]), (1, 1))
        self.assertEqual(body["usage"]["totals"]["help_views"], 1)


class TestPrivacyPage(AppTestCase):
    def test_says_so_in_one_plain_sentence(self):
        page = " ".join(self.client.get("/privacy").get_data(as_text=True).split())
        self.assertIn("we keep one total a day for each of a few things", page)
        self.assertIn("with no cookie and nothing that says who or which workspace", page)
        self.assertIn("at most 20 a day", page)


class TestSettingsBasics(AppTestCase):
    """Settings shows the plan, the version and how to get help, to everyone on the team."""

    def setUp(self):
        super().setUp()
        self.signup()
        with self.app.test_request_context():
            from omniarmor_app.auth import create_invite
            with self.db() as conn:
                link = create_invite(conn, conn.execute("SELECT id FROM orgs").fetchone()[0], 1)
        token = link.split("invite=")[1]
        self.member = self.app.test_client()
        self.signup(email="member@example.com", client=self.member, invite=token)

    def page(self, client):
        return " ".join(client.get("/app/settings").get_data(as_text=True).split())

    def test_owner_and_member_see_the_plan_version_and_help(self):
        for client in (self.client, self.member):
            page = self.page(client)
            self.assertIn("<h2>Academy plan</h2>", page)
            self.assertIn("The compliance tracker is free.", page)
            self.assertIn('href="/app/academy/plan"', page)
            self.assertIn(f"data-version>{__version__}</span>", page)
            self.assertIn('Need help? The <a href="/help">Help page</a>', page)
        self.assertIn("only the workspace owner can change it", self.page(self.member))
        self.assertNotIn("only the workspace owner can change it", self.page(self.client))

    def test_support_email_only_when_set(self):
        self.assertNotIn("mailto:", self.page(self.client))
        self.app.config["SUPPORT_EMAIL"] = "help@omniarmor.test"
        page = self.page(self.member)
        self.assertIn('write to <a href="mailto:help@omniarmor.test">help@omniarmor.test</a>', page)


if __name__ == "__main__":
    unittest.main()
