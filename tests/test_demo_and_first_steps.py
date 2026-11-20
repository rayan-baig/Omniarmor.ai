"""The first five minutes: the demos (business and classroom), the
getting-started lists for an owner and for a teacher, and the empty screens.

The demos must send nothing, keep nothing and be rate limited."""

import os
import re
import sys
import time
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_webapp import PASSWORD, AppTestCase  # noqa: E402

from omniarmor_app import academy, demo_mode  # noqa: E402
from omniarmor_app.db import connect  # noqa: E402


def text(response):
    return " ".join(re.sub(r"<[^>]+>", " ", response.data.decode()).split())


def flashes(response):
    return re.findall(r'<li class="flash [a-z]+">(.*?)</li>', response.data.decode(), re.S)


class DemoCase(AppTestCase):
    def setUp(self):
        super().setUp()
        self.app.config["SMTP_HOST"] = "smtp.test"     # a mail server is set up: the demo must still send nothing
        self.smtp = mock.patch("smtplib.SMTP", side_effect=AssertionError("the demo sent an email")).start()
        self.addCleanup(mock.patch.stopall)

    def open_demo(self, kind="business", client=None):
        r = (client or self.client).get(f"/demo/{kind}")
        self.assertEqual(r.status_code, 302, r.data[:300])
        return r

    def facts(self, kind):
        with self.app.app_context():
            return demo_mode.facts()[kind]

    def real_rows(self, table):
        conn = self.db()
        try:
            return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        finally:
            conn.close()


class TestBusinessDemo(DemoCase):
    def test_it_opens_a_labelled_workspace_with_pretend_data(self):
        r = self.open_demo()
        self.assertTrue(r.headers["Location"].endswith("/app"))
        page = text(self.client.get("/app"))
        self.assertIn("Demo Pretend data. Nothing you do here is saved, and no emails or reminders go out.", page)
        self.assertIn("Step 1 of 4: Dashboard.", page)
        self.assertIn(demo_mode.BUSINESS, page)
        self.assertIn("Next: A checklist", page)
        self.assertIn("Start your free trial", page)
        # A few checks done, exactly one overdue, one coming due.
        self.assertRegex(page, r"1 blocked 1 warning \d+ cleared")
        self.assertIn("Ready-to-eat food 7-day limit", page)

    def test_every_tour_page_works_and_the_last_ends_with_the_trial(self):
        self.open_demo()
        for path in ("/app", "/app/industry/2", "/app/industry/30", "/app/notifications", "/app/report",
                     "/app/audit", "/app/settings", "/app/academy", "/app/armo", "/app/plan", "/app/report.csv",
                     "/app/audit.csv"):
            r = self.client.get(path)
            self.assertEqual(r.status_code, 200, path)
            r.close()
        page = self.client.get("/app/report").data.decode()
        self.assertIn('data-demo-step="4"', page)
        self.assertNotIn("data-demo-next", page)
        self.assertIn('href="/signup?industry=2" data-demo-signup>Start your free trial', page)
        # This morning's reminder is in Radar, kept and never sent.
        radar = text(self.client.get("/app/notifications"))
        self.assertIn("1 overdue", radar)
        self.assertIn("Saved (email not set up)", radar)
        self.smtp.assert_not_called()

    def test_it_sends_nothing(self):
        self.open_demo()
        for path in ("/app", "/app/notifications", "/app/settings"):
            self.client.get(path)
        csrf = self.csrf()
        for path, data in (("/app/settings/invite", {}), ("/app/settings/reminders", {"email_reminders": "on"}),
                           ("/app/industry/30/rule/i9_section_2", {"action": "done_today"})):
            self.client.post(path, data={"csrf_token": csrf, **data})
        # And notify() itself refuses inside a demo, whatever calls it.
        from omniarmor_app.db import get_db
        from omniarmor_app.notify import notify
        with self.app.test_request_context("/app"):
            from flask import g
            g.demo = "business"
            status = notify(get_db(), self.app.config, "reminder", "someone@example.com", "Hi", "Body")
        self.assertEqual(status, "logged")
        self.smtp.assert_not_called()
        # Nothing reached the real database: no people, workspaces or emails.
        for table in ("users", "orgs", "notifications", "items", "invites", "audit"):
            self.assertEqual(self.real_rows(table), 0, table)

    def test_nothing_can_be_changed(self):
        self.open_demo()
        before = self.client.get("/app/industry/2").data.decode()
        self.assertIn('value="38"', before)
        r = self.change(2, "cold_holding", value="55")
        self.assertEqual(r.status_code, 303)
        self.assertTrue(r.headers["Location"].endswith("/app"))
        page = self.client.get("/app/industry/2")
        self.assertIn(demo_mode.REFUSED.replace("'", "&#39;"), " ".join(flashes(page)))
        self.assertIn('value="38"', page.data.decode())
        for path, data in (("/app/settings/company", {"name": "Mine", "timezone": "UTC", "industries": "2"}),
                           ("/app/settings/delete", {"confirm": demo_mode.BUSINESS}),
                           ("/app/industry/2/bulk", {"bulk_action": "done_today", "keys": "date_marking"}),
                           ("/app/armo/personality", {"personality": "grumpy"})):
            self.assertEqual(self.post(path, data).status_code, 303, path)
        page = text(self.client.get("/app/settings"))
        self.assertIn(demo_mode.BUSINESS, page)
        self.assertIn("1 blocked", text(self.client.get("/app")))

    def test_each_page_starts_from_a_fresh_copy(self):
        """Even what a page writes for itself (the copy is per request) is gone on the next one."""
        with self.app.test_request_context("/app"):
            from flask import g
            g.demo = "business"
            first = demo_mode.sandbox()
            first.execute("DELETE FROM items")
            first.commit()
            second = demo_mode.sandbox()
            self.assertGreater(second.execute("SELECT COUNT(*) FROM items").fetchone()[0], 0)
            first.close()
            second.close()

    def test_the_demo_resets_on_a_schedule(self):
        self.open_demo()
        self.client.get("/app")
        built = self.app.extensions["omniarmor_demo"][1]["built"]
        with mock.patch.object(demo_mode, "REBUILD_EVERY", demo_mode.timedelta(0)):
            self.client.get("/app")
        self.assertGreater(self.app.extensions["omniarmor_demo"][1]["built"], built)

    def test_opening_it_is_rate_limited(self):
        for n in range(demo_mode.STARTS_PER_HOUR):
            self.assertEqual(self.app.test_client().get("/demo/business").status_code, 302, n)
        r = self.app.test_client().get("/demo/classroom")
        self.assertEqual(r.status_code, 429)
        self.assertIn("Please try again later", r.data.decode())
        # Reopening a demo you're already in doesn't count.
        client = self.app.test_client()
        with client.session_transaction() as s:
            s["demo"], s["demo_until"] = "business", int(time.time()) + 60
        self.assertEqual(client.get("/demo/business").status_code, 302)

    def test_the_pass_runs_out(self):
        self.open_demo()
        with self.client.session_transaction() as s:
            s["demo_until"] = int(time.time()) - 1
        r = self.client.get("/app")
        self.assertTrue(r.headers["Location"].endswith("/demo"))
        self.assertIn(f"The demo ends after {demo_mode.PASS_MINUTES} minutes", " ".join(flashes(self.client.get("/demo"))))
        self.assertTrue(self.client.get("/app").headers["Location"].startswith("/login"))

    def test_leaving_and_signing_up_use_the_real_app(self):
        self.open_demo()
        page = self.client.get("/").data.decode()
        self.assertIn("See a demo", page)     # outside the app's pages, a visitor as before
        r = self.signup(industries=(2,))
        self.assertEqual(r.status_code, 302)
        self.assertEqual(self.real_rows("users"), 1)
        self.assertNotIn("data-demo-bar", self.client.get("/app/industry/2").data.decode())
        client = self.app.test_client()
        self.open_demo(client=client)
        r = self.post("/demo/leave", client=client)
        self.assertEqual(r.status_code, 302)
        self.assertTrue(client.get("/app").headers["Location"].startswith("/login"))

    def test_a_signed_in_owner_keeps_their_own_workspace(self):
        self.signup()
        r = self.client.get("/demo/business")
        self.assertTrue(r.headers["Location"].endswith("/app"))
        self.assertNotIn("data-demo-bar", self.client.get("/app").data.decode())

    def test_links_from_the_landing_trade_and_classroom_pages(self):
        self.assertIn('href="/demo/business"', self.client.get("/").data.decode())
        # A school's pages lead to the classroom demo, never the pretend restaurant.
        schools = self.client.get("/for/schools").data.decode()
        self.assertIn('href="/demo/classroom"', schools)
        self.assertNotIn('href="/demo/business"', schools)
        self.assertIn('href="/demo/business"', self.client.get("/for/salons-and-barbershops").data.decode())
        self.assertIn('href="/demo/classroom"', self.client.get("/classrooms").data.decode())
        robots = self.client.get("/robots.txt").data.decode()
        self.assertIn("Disallow: /demo", robots)

    def test_strict_csp_and_no_inline_styles(self):
        self.open_demo()
        r = self.client.get("/app")
        self.assertNotIn("unsafe-inline", r.headers["Content-Security-Policy"])
        for path in ("/app", "/app/industry/2", "/app/report", "/demo"):
            page = self.client.get(path).data.decode()
            self.assertNotIn(" style=", page, path)
            self.assertNotRegex(page, r"<script(?![^>]*\bsrc=)", path)


class TestClassroomDemo(DemoCase):
    def test_a_teacher_can_click_through_the_class(self):
        r = self.open_demo("classroom")
        self.assertTrue(r.headers["Location"].endswith("/app/academy/classes"))
        page = text(self.client.get("/app/academy/classes"))
        self.assertIn("Step 1 of 5: Classes.", page)
        self.assertIn(demo_mode.CLASS_NAME, page)
        self.assertIn("Free classroom trial", page)
        facts = self.facts("classroom")
        cls = text(self.client.get(f"/app/academy/classes/{facts['class']}"))
        for name, *_ in demo_mode.STUDENTS:
            self.assertIn(name, cls)
        codes = text(self.client.get(f"/app/academy/classes/{facts['class']}/join-codes"))
        self.assertIn("KID-DEMO0001", codes)
        progress = text(self.client.get(f"/app/academy/{facts['showcase']}/progress"))
        self.assertIn(f"{demo_mode.SHOWCASE_STUDENT}'s progress", progress)
        first = academy.CLASSROOM.topic_worlds[0].number
        lesson = self.client.get(f"/app/academy/{facts['sample']}/world/{first}/stage/1")
        self.assertEqual(lesson.status_code, 200)
        self.assertIn("Step 5 of 5: A sample lesson.", text(lesson))
        self.assertIn(academy.CLASS_BUSINESS, text(lesson))
        self.assertIn('href="/signup?then=classes" data-demo-signup>Start your free trial',
                      lesson.data.decode())

    def test_the_sample_lesson_can_be_played_and_nothing_is_kept(self):
        self.open_demo("classroom")
        facts = self.facts("classroom")
        t = academy.CLASSROOM
        first = t.topic_worlds[0].number
        url = f"/app/academy/{facts['sample']}/world/{first}/stage/1"
        self.client.get(url)
        questions = academy.quiz(t, first, 1, academy.CLASS_BUSINESS, [],
                                 academy.attempt_seed(facts["sample"], t.key, first, 1, 1))
        data = {"attempt": "1", **{f"q{i}": str(q.answer) for i, q in enumerate(questions)}}
        r = self.post(url, data)
        self.assertEqual(r.status_code, 200)
        self.assertIn("Perfect score!", text(r))
        # The next page is the demo as it was: the lesson is not passed.
        progress = text(self.client.get(f"/app/academy/{facts['sample']}/progress"))
        self.assertIn("No lessons played yet", progress)
        self.assertEqual(self.real_rows("learner_progress"), 0)

    def test_forms_are_refused(self):
        self.open_demo("classroom")
        facts = self.facts("classroom")
        r = self.post(f"/app/academy/classes/{facts['class']}/students", {"names": "Zed"})
        self.assertEqual(r.status_code, 303)
        self.assertNotIn("Zed", text(self.client.get(f"/app/academy/classes/{facts['class']}")))

    def test_the_demo_join_codes_work_nowhere(self):
        self.open_demo("classroom")
        self.client.get("/app/academy/classes")
        self.assertIsNone(academy.clean_join_code("KID-DEMO0001"))
        kid = self.app.test_client()
        r = self.post("/kids", {"code": "KID-DEMO0001"}, client=kid)
        self.assertEqual(r.status_code, 400)

    def test_every_name_is_pretend_and_every_address_reserved(self):
        conn, facts = demo_mode.build(self.app.config)
        try:
            emails = [r[0] for r in conn.execute("SELECT email FROM users")]
            self.assertTrue(emails)
            self.assertTrue(all(e.endswith("@demo.example") for e in emails), emails)
            names = [r[0] for r in conn.execute("SELECT name FROM orgs")]
            self.assertTrue(all("(demo)" in n for n in names), names)
            sent = [r[0] for r in conn.execute("SELECT status FROM notifications")]
            self.assertTrue(sent)
            self.assertEqual(set(sent), {"logged"})
        finally:
            conn.close()


class TestOwnerGettingStarted(AppTestCase):
    def test_a_member_has_their_own_last_step(self):
        from omniarmor_app.auth import create_invite
        self.signup(industries=(2,))
        with self.app.test_request_context():
            from omniarmor_app.db import get_db
            link = create_invite(get_db(), 1, 1)
        mate = self.app.test_client()
        self.signup(email="mate@example.com", invite=link.rsplit("invite=", 1)[1], name="Mate", client=mate)
        page = text(mate.get("/app"))
        self.assertIn("Choose your reminder emails : not done yet", page)
        self.post("/app/settings/reminders", {"email_reminders": "on"}, client=mate)
        self.assertIn("Choose your reminder emails : done", text(mate.get("/app")))

    def test_saving_a_dated_check_says_when_the_reminder_goes_out(self):
        self.signup(industries=(1,))
        r = self.change(1, "annual_mvr_review", action="done_today")
        page = self.client.get(r.headers["Location"])
        said = " ".join(flashes(page))
        self.assertIn("Marked done today", said)
        self.assertIn("Reminder set: the team gets an email 30, 7 and 1 day before it&#39;s due on", said)

    def test_accounts_from_before_skip_the_new_last_step(self):
        import tempfile
        from omniarmor_app import db as dbmod
        from omniarmor_app.db import migrate
        with tempfile.TemporaryDirectory() as tmp:
            conn = connect(os.path.join(tmp, "old.db"))
            with mock.patch.object(dbmod, "MIGRATIONS", [m for m in dbmod.MIGRATIONS if m[0] <= 22]):
                migrate(conn)
            conn.execute("INSERT INTO users (email, name, password_hash, created_at) VALUES"
                         " ('a@example.com', 'A', 'x', '2026-01-01T00:00:00+00:00')")
            conn.commit()
            self.assertEqual(migrate(conn), dbmod.SCHEMA_VERSION)
            self.assertEqual(conn.execute("SELECT reminders_chosen_at FROM users").fetchone()[0],
                             "2026-01-01T00:00:00+00:00")
            conn.close()


class TestTeacherGettingStarted(AppTestCase):
    def steps(self):
        return text(self.client.get("/app/academy/classes"))

    def test_from_the_schools_page_a_teacher_lands_on_classes_and_the_list_ticks_itself(self):
        page = self.client.get("/classrooms").data.decode()
        self.assertIn("/signup?then=classes", page)
        form = self.client.get("/signup?industry=51&then=classes").data.decode()
        self.assertIn('name="then" value="classes"', form)
        r = self.post("/signup", {"name": "Sam", "email": "sam@example.com", "password": PASSWORD,
                                  "org_name": "Test School", "timezone": "UTC", "then": "classes"})
        self.assertTrue(r.headers["Location"].endswith("/app/academy/classes"))
        # The teacher sign-up starts the free class pilot: the first step is done.
        self.assertIn("Getting started · 1 of 5 done", self.steps())
        r = self.post("/app/academy/classes", {"name": "Room 4"})
        class_id = int(r.headers["Location"].rsplit("/", 1)[1])
        self.assertIn("Getting started · 2 of 5 done", self.steps())
        self.post(f"/app/academy/classes/{class_id}/students", {"names": "Ana\nBo"})
        page = self.steps()
        self.assertIn("Getting started · 3 of 5 done", page)
        self.assertIn("Open the join codes", page)
        self.post(f"/app/academy/classes/{class_id}/join-codes")
        self.assertIn("Getting started · 4 of 5 done", self.steps())
        conn = self.db()
        learner = conn.execute("SELECT id FROM learners WHERE class_id = ?", (class_id,)).fetchone()[0]
        conn.execute("INSERT INTO learner_progress (learner_id, level, attempts, best_score, best_stars,"
                     " completed_at) VALUES (?, ?, 1, 5, 2, '2026-11-17T10:00:00+00:00')",
                     (learner, academy.level_id(academy.CLASSROOM, academy.CLASSROOM.topics[0], 1)))
        conn.commit()
        conn.close()
        self.assertNotIn("Getting started", self.steps())


class TestEmptyScreens(AppTestCase):
    """Every screen a new workspace or class can open empty says what will
    show there, in one sentence, with a button for the next step."""

    def empty(self, path, key, button=True):
        page = self.client.get(path).data.decode()
        match = re.search(rf'<div class="empty-state" data-empty="{key}">\s*<p>([^<]+)</p>\s*(<a class="btn[^"]*"'
                          r' href="[^"]+">[^<]+</a>)?', page)
        self.assertIsNotNone(match, (path, key))
        self.assertIn("will show here", match.group(1), path)
        if button:
            self.assertIsNotNone(match.group(2), (path, key))
        return match

    def test_a_new_workspace(self):
        self.signup(industries=(2,))
        self.empty("/app", "attention")
        self.empty("/app", "coming-due")
        self.empty("/app/industry/2?only=problems", "problems")
        self.empty("/app/notifications", "reminders")
        self.empty("/app/report", "report")
        self.empty("/app/settings", "team", button=False)
        self.empty("/app/academy", "learners")
        self.empty("/app/academy/classes", "classes")
        # Once there is something, the empty screen goes.
        self.change(2, "date_marking", action="done_today")
        self.assertNotIn('data-empty="report"', self.client.get("/app/report").data.decode())
        self.assertNotIn('data-empty="coming-due"', self.client.get("/app").data.decode())

    def test_a_new_class(self):
        self.signup(industries=(51,))
        self.post("/app/academy/classes/pilot")
        r = self.post("/app/academy/classes", {"name": "Room 4"})
        class_id = int(r.headers["Location"].rsplit("/", 1)[1])
        self.empty(f"/app/academy/classes/{class_id}", "students")
        self.empty(f"/app/academy/classes/{class_id}/join-codes", "codes")
        self.empty(f"/app/academy/classes/{class_id}/certificates", "certificates")
        self.empty(f"/app/academy/classes/{class_id}/report", "report")
        self.post(f"/app/academy/classes/{class_id}/students", {"names": "Ana"})
        self.empty(f"/app/academy/classes/{class_id}/join-codes", "codes", button=False)
        self.assertIn("Make a code for every student",
                      self.client.get(f"/app/academy/classes/{class_id}/join-codes").data.decode())
        conn = self.db()
        learner = conn.execute("SELECT id FROM learners").fetchone()[0]
        conn.close()
        self.empty(f"/app/academy/{learner}/progress", "lessons")


if __name__ == "__main__":
    unittest.main()
