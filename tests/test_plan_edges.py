"""Edges of the plans found before launch (1.6.2): a pause in Stripe with no
end date, a switch to yearly in Stripe's portal while the save offer runs,
certificates on any track, the cap on classes, one free trial and one
classroom pilot per owner, a plan set by hand ending in the workspace's own
timezone and never set over a running Stripe subscription, paying by card
after an invoiced plan, and deleting one location of several.

Stripe is the same in-memory stand-in test_grow.py uses."""

import html
import os
import re
import sys
import time
import unittest
from contextlib import closing
from datetime import datetime, timedelta, timezone
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_grow import DAY, PRICES, GrowCase, StripeGrowCase  # noqa: E402
from test_schools import ClassCase  # noqa: E402

from omniarmor_app import academy, academy_plan, classrooms, plans  # noqa: E402
from omniarmor_app.db import iso, utcnow  # noqa: E402
from omniarmor_app.jobs import run_pause_sweep  # noqa: E402


def words(page):
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", page)).split())


# --- A pause with no end date ----------------------------------------------------------

class TestOpenEndedPause(StripeGrowCase):
    def pause_in_stripe(self, resumes_at=None, created=None):
        self.stripe.sub["pause_collection"] = {"behavior": "void", "resumes_at": resumes_at}
        self.webhook(f"evt_pause_{created}", "customer.subscription.updated", self.stripe.sub,
                     created or int(time.time()))

    def test_paused_until_stripe_resumes_it(self):
        self.pause_in_stripe()
        access = plans.access(self.org())
        self.assertTrue(access["paused"])
        self.assertTrue(access["read_only"])
        self.assertEqual(access["reason"], "paused")
        self.assertIsNone(access["resumes_at"])
        self.assertTrue(access["pause_open"])
        self.assertFalse(self.can_save(4))
        # Every screen says so, with no end date.
        for path in ("/app", "/app/plan", "/app/plan/cancel", "/app/settings", "/app/industry/18"):
            text = words(self.page(path))
            self.assertIn("no end date", text, path)
            self.assertNotRegex(text, r"\bNone\b(?! of)", path)   # no empty date
        # The daily sweep neither ends it nor emails about it.
        with closing(self.db()) as conn:
            summary = run_pause_sweep(conn, self.app.config, now=utcnow() + timedelta(days=400))
        self.assertEqual(summary, {"notices": 0, "ended": 0})
        self.assertTrue(plans.access(self.org(), now=utcnow() + timedelta(days=400))["paused"])
        # Stripe resumes it: on again.
        self.stripe.sub["pause_collection"] = None
        self.webhook("evt_resume", "customer.subscription.updated", self.stripe.sub, int(time.time()) + 5)
        access = plans.access(self.org())
        self.assertFalse(access["paused"])
        self.assertTrue(self.can_save(6))

    def test_start_again_now_ends_it(self):
        self.pause_in_stripe()
        self.assertTrue(plans.cancel_options(self.app.config, self.org())["can_resume"])
        self.post("/app/plan/resume")
        self.assertEqual(self.stripe.posts()[-1]["pause_collection"], "")
        self.assertFalse(plans.access(self.org())["paused"])

    def test_a_pause_with_a_date_after_an_open_one(self):
        self.pause_in_stripe()
        until = int(time.time()) + 20 * DAY
        self.pause_in_stripe(resumes_at=until, created=int(time.time()) + 3)
        access = plans.access(self.org())
        self.assertFalse(access["pause_open"])
        self.assertEqual(int(access["resumes_at"].timestamp()), until)

    def test_a_cancelled_plan_bought_again_isnt_paused(self):
        self.pause_in_stripe()
        self.webhook("evt_gone", "customer.subscription.deleted", dict(self.stripe.sub, status="canceled"),
                     int(time.time()) + 5)
        self.set_org(academy_status="active", stripe_subscription_id="sub_2")
        self.assertFalse(plans.access(self.org())["paused"])


# --- A switch to yearly in Stripe's portal while the save offer runs ---------------------

class TestPortalYearlyDuringSaveOffer(StripeGrowCase):
    def test_it_is_flagged_for_the_operator(self):
        self.post("/app/plan/save-offer")
        yearly = dict(self.stripe.sub, items={"data": [{"id": "si_1", "price": {"id": "price_pro_year"},
                                                         "quantity": 1}]})
        with self.assertLogs(self.app.logger, "WARNING") as logs:
            self.webhook("evt_portal_year", "customer.subscription.updated", yearly, int(time.time()))
        self.assertTrue(any("save offer" in line for line in logs.output))
        org = self.org()
        self.assertEqual(org["plan_interval"], "year")
        with closing(self.db()) as conn:
            audit = [r[0] for r in conn.execute("SELECT summary FROM audit ORDER BY id")]
        self.assertTrue(any("save offer" in s and "yearly" in s for s in audit), audit)

    def test_not_after_the_discount_ends(self):
        long_ago = plans.add_months(utcnow(), -self.app.config["SAVE_OFFER_MONTHS"]) - timedelta(days=1)
        self.set_org(save_offer_used_at=iso(long_ago))
        yearly = dict(self.stripe.sub, items={"data": [{"id": "si_1", "price": {"id": "price_pro_year"},
                                                         "quantity": 1}]})
        self.webhook("evt_portal_year", "customer.subscription.updated", yearly, int(time.time()))
        with closing(self.db()) as conn:
            audit = [r[0] for r in conn.execute("SELECT summary FROM audit")]
        self.assertFalse(any("save offer" in s for s in audit), audit)

    def test_the_portal_settings_are_written_down(self):
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        with open(os.path.join(root, "docs", "OPERATIONS.md"), encoding="utf-8") as f:
            ops = f.read()
        section = ops[ops.index("**Stripe's customer portal"):]
        section = section[:section.index("\n\n**", 10)]
        for needed in ("Classroom", "Whole school", "monthly", "yearly", "save offer"):
            self.assertIn(needed, section)


# --- Certificates on any track ------------------------------------------------------------

class TestCertificatesOnAnyTrack(ClassCase):
    def pass_final(self, learner_id, track_key):
        t = academy.TRACKS[track_key]
        with self.db() as conn:
            conn.execute("INSERT INTO learner_progress (learner_id, level, attempts, best_score, best_stars,"
                         " completed_at) VALUES (?, ?, 1, 5, 2, ?)",
                         (learner_id, academy.level_id(t, academy.FINAL_WORLD.number, 1), iso(utcnow())))
            conn.commit()

    def test_the_certificates_page_agrees_with_the_class_view(self):
        self.start_pilot()
        _, class_id = self.add_class()
        self.add_students(class_id, ["Sam", "Priya", "Jo"])
        kids = self.students(class_id)
        self.pass_final(kids["Sam"], "trailblazer")            # not the track Sam is on now
        self.pass_final(kids["Priya"], "launchpad")
        self.pass_final(kids["Priya"], "summit")
        with self.db() as conn:
            view = classrooms.class_progress(conn, classrooms.class_or_none(conn, 1, class_id))
        flagged = sorted(s["learner"]["nickname"] for s in view["students"] if s["certificate"])
        self.assertEqual(flagged, ["Priya", "Sam"])
        page = self.client.get(f"/app/academy/classes/{class_id}/certificates").data.decode()
        shown = re.findall(r'data-certificate="([^"]+)"', page)
        self.assertEqual(sorted(shown), ["Priya", "Priya", "Sam"])
        self.assertIn("Trailblazer", page)
        self.assertIn("Summit", page)
        self.assertNotIn('data-certificate="Jo"', page)


# --- At most 100 classes, and not too fast -------------------------------------------------

class TestClassCap(ClassCase):
    def setUp(self):
        super().setUp()
        result = self.app.test_cli_runner().invoke(args=["plan", "1", "school"])
        self.assertEqual(result.exit_code, 0, result.output)

    def test_at_most_a_hundred_classes(self):
        with self.db() as conn:
            conn.executemany("INSERT INTO classes (org_id, name, created_at) VALUES (1, ?, ?)",
                             [(f"Room {n}", iso(utcnow())) for n in range(classrooms.MAX_CLASSES)])
            conn.commit()
        response, class_id = self.add_class("One too many")
        self.assertIsNone(class_id)
        self.assertIn(f"up to {classrooms.MAX_CLASSES} classes", self.flashes(response))

    def test_adding_classes_is_rate_limited(self):
        for n in range(classrooms.CLASSES_PER_HOUR):
            self.assertIsNotNone(self.add_class(f"Room {n}")[1], n)
        response, class_id = self.add_class("Room fast")
        self.assertIsNone(class_id)
        self.assertIn("Too many classes added", self.flashes(response))


# --- One free trial and one classroom pilot per owner ------------------------------------

class TestOnePerOwner(ClassCase):
    def add_location(self, name):
        response = self.post("/app/settings/locations/add", {"name": name})
        self.assertEqual(response.status_code, 302)
        with self.db() as conn:
            return conn.execute("SELECT id FROM orgs WHERE name = ?", (name,)).fetchone()[0]

    def org_row(self, org_id):
        with self.db() as conn:
            return conn.execute("SELECT * FROM orgs WHERE id = ?", (org_id,)).fetchone()

    def test_an_extra_location_starts_without_a_trial(self):
        settings = words(self.client.get("/app/settings").data.decode())
        self.assertIn("no free trial", settings)
        second = self.add_location("Second Campus")
        access = plans.access(self.org_row(second))
        self.assertFalse(access["trial"])
        self.assertTrue(access["read_only"])
        self.assertFalse(access["academy"])
        self.assertEqual(access["reason"], "new_location")
        page = words(self.client.get("/app").data.decode())
        self.assertIn("This location has no plan yet", page)
        self.assertNotIn("Your free trial has ended", page)
        # The first workspace keeps its trial.
        self.assertTrue(plans.access(self.org_row(1))["trial"])

    def test_one_pilot_per_owner_even_after_a_delete(self):
        second = self.add_location("Second Campus")        # now working in it
        self.start_pilot()
        self.assertEqual(plans.pilot_status(self.org_row(second))["state"], "active")
        self.post("/app/settings/delete", {"confirm": "Second Campus"})
        third = self.add_location("Third Campus")
        response = self.start_pilot()
        self.assertIn("had its free pilot already", self.flashes(response))
        self.assertEqual(plans.pilot_status(self.org_row(third))["state"], "none")
        self.post("/app/settings/locations/1/switch")
        self.start_pilot()
        self.assertEqual(plans.pilot_status(self.org_row(1))["state"], "none")
        page = words(self.client.get("/app/academy/classes").data.decode())
        self.assertNotIn("Start the free pilot", page)


# --- Plans set by hand -----------------------------------------------------------------------

class TestPlanSetByHand(ClassCase):
    def run_plan(self, *args):
        return self.app.test_cli_runner().invoke(args=["plan", "1", *args])

    def test_until_ends_at_the_end_of_that_day_in_the_workspaces_timezone(self):
        result = self.run_plan("classroom", "--until", "2027-06-30")
        self.assertEqual(result.exit_code, 0, result.output)
        org = self.org()   # America/New_York: 23:59:59 there is 03:59:59 UTC the next day
        self.assertEqual(org["academy_ends_at"], "2027-07-01T03:59:59+00:00")
        self.assertTrue(plans.access(org, now=datetime(2027, 7, 1, 3, 0, tzinfo=timezone.utc))["paid"])
        self.assertFalse(plans.access(org, now=datetime(2027, 7, 1, 4, 0, tzinfo=timezone.utc))["paid"])

    def test_refused_over_a_running_stripe_subscription_without_force(self):
        with self.db() as conn:
            conn.execute("UPDATE orgs SET academy_status = 'active', plan = 'plus', stripe_customer_id = 'cus_1',"
                         " stripe_subscription_id = 'sub_live' WHERE id = 1")
            conn.commit()
        for args in (("school",), ("none",)):
            result = self.run_plan(*args)
            self.assertNotEqual(result.exit_code, 0, args)
            self.assertIn("Stripe subscription", result.output)
            self.assertIn("--force", result.output)
            self.assertEqual(self.org()["plan"], "plus")
        result = self.run_plan("school", "--force")
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertEqual(self.org()["plan"], "school")
        # The old command too.
        result = self.app.test_cli_runner().invoke(args=["academy-plan", "1", "canceled"])
        self.assertNotEqual(result.exit_code, 0)

    def test_a_cancelled_subscription_is_no_obstacle(self):
        with self.db() as conn:
            conn.execute("UPDATE orgs SET academy_status = 'canceled', stripe_subscription_id = 'sub_old' WHERE id = 1")
            conn.commit()
        self.assertEqual(self.run_plan("classroom").exit_code, 0)


# --- Paying by card after an invoiced plan --------------------------------------------------

class TestCardAfterInvoice(ClassCase):
    def setUp(self):
        super().setUp()
        self.app.config.update(STRIPE_SECRET_KEY="sk_test", CLASSROOM_YEARLY_STRIPE_PRICE="price_class",
                               SCHOOL_YEARLY_STRIPE_PRICE="price_school", **PRICES)
        self.ends = utcnow().replace(microsecond=0) + timedelta(days=60)
        with self.db() as conn:
            academy_plan.set_status(conn, 1, "active", kind="classroom", interval="year", ends_at=iso(self.ends))
            conn.commit()
        self.calls = []

    def fake_stripe(self, cfg, path, fields, method="POST"):
        self.calls.append((path, dict(fields)))
        return {"url": "https://checkout.stripe.test/s"}

    def checkout(self, path, data):
        with mock.patch.object(academy_plan, "_stripe", side_effect=self.fake_stripe):
            return self.post(path, data)

    def test_the_card_starts_the_day_the_invoiced_plan_ends(self):
        page = words(self.client.get("/app/academy/classes").data.decode())
        self.assertIn("Pay by card from", page)
        response = self.checkout("/app/academy/classes/checkout", {"plan": "classroom"})
        self.assertEqual(response.status_code, 303)
        [(path, fields)] = self.calls
        self.assertEqual(path, "checkout/sessions")
        self.assertEqual(fields["line_items[0][price]"], "price_class")
        self.assertEqual(int(fields["subscription_data[trial_end]"]), int(self.ends.timestamp()))
        # Stripe's webhook: the card subscription takes over from the invoice, with no gap.
        event = {"id": "evt_co", "type": "checkout.session.completed", "created": int(time.time()),
                 "data": {"object": {"id": "cs_1", "customer": "cus_9", "subscription": "sub_9",
                                     "client_reference_id": "1",
                                     "metadata": {"org_id": "1", "plan": "classroom", "interval": "year"}}}}
        with self.db() as conn:
            self.assertEqual(academy_plan.apply_event(conn, event, self.app.config), "active")
            conn.commit()
        org = self.org()
        self.assertEqual((org["stripe_subscription_id"], org["plan"]), ("sub_9", "classroom"))
        self.assertIsNone(org["academy_ends_at"])
        self.assertTrue(plans.access(org, now=self.ends + timedelta(days=1))["paid"])

    def test_only_the_same_plan(self):
        response = self.checkout("/app/academy/classes/checkout", {"plan": "school"})
        self.assertEqual(self.calls, [])
        text = self.flashes(response)
        self.assertIn("runs until", text)
        self.assertNotIn("Manage billing", text)

    def test_a_trial_end_too_soon_for_stripe_is_moved_to_its_minimum(self):
        soon = utcnow().replace(microsecond=0) + timedelta(hours=5)
        with self.db() as conn:
            conn.execute("UPDATE orgs SET academy_ends_at = ? WHERE id = 1", (iso(soon),))
            conn.commit()
        self.checkout("/app/academy/classes/checkout", {"plan": "classroom"})
        [(_, fields)] = self.calls
        trial_end = int(fields["subscription_data[trial_end]"])
        self.assertGreaterEqual(trial_end, int(time.time()) + academy_plan.STRIPE_MIN_TRIAL_SECONDS)
        self.assertLess(trial_end, int(time.time()) + academy_plan.STRIPE_MIN_TRIAL_SECONDS + 3600)

    def test_pro_set_by_hand_with_an_end_date_too(self):
        with self.db() as conn:
            academy_plan.set_status(conn, 1, "active", kind="pro", interval="month", ends_at=iso(self.ends))
            conn.commit()
        self.assertIn("Pay by card from", words(self.client.get("/app/plan").data.decode()))
        response = self.checkout("/app/plan/checkout", {"plan": "pro", "interval": "month"})
        self.assertEqual(response.status_code, 303)
        self.assertEqual(int(self.calls[0][1]["subscription_data[trial_end]"]), int(self.ends.timestamp()))

    def test_a_plan_set_by_hand_with_no_end_date_says_whom_to_ask(self):
        with self.db() as conn:
            academy_plan.set_status(conn, 1, "active", kind="classroom", interval="year")
            conn.commit()
        for path, data in (("/app/academy/classes/checkout", {"plan": "classroom"}),
                           ("/app/plan/checkout", {"plan": "pro", "interval": "month"})):
            text = self.flashes(self.checkout(path, data))
            self.assertNotIn("Manage billing", text, path)
            self.assertIn(classrooms.invoice_email(self.app.config), text, path)
        self.assertEqual(self.calls, [])


# --- Deleting one location of several ------------------------------------------------------

class TestDeletingOneLocation(GrowCase):
    def test_the_owner_stays_signed_in_in_another_location(self):
        self.post("/app/settings/locations/add", {"name": "Acme North"})
        response = self.post("/app/settings/delete", {"confirm": "Acme North"})
        self.assertEqual(response.status_code, 302)
        page = self.client.get("/app/settings")
        self.assertEqual(page.status_code, 200)
        self.assertIn("Acme Logistics", page.get_data(as_text=True).split("<h1>")[0])
        with closing(self.db()) as conn:
            self.assertEqual([r[0] for r in conn.execute("SELECT name FROM orgs")], ["Acme Logistics"])
        # The last one signs out, as before.
        self.post("/app/settings/delete", {"confirm": "Acme Logistics"})
        self.assertEqual(self.client.get("/app").status_code, 302)


class TestMigration22(unittest.TestCase):
    def test_pilots_already_started_count_for_their_owner(self):
        import tempfile
        from omniarmor_app import db as dbmod
        from omniarmor_app.db import connect, migrate
        with tempfile.TemporaryDirectory() as tmp:
            conn = connect(os.path.join(tmp, "old.db"))
            with mock.patch.object(dbmod, "MIGRATIONS", [m for m in dbmod.MIGRATIONS if m[0] <= 21]):
                self.assertEqual(migrate(conn), 21)
            now = "2026-11-01T00:00:00+00:00"
            conn.execute("INSERT INTO orgs (id, name, created_at, pilot_started_at, pilot_ends_at) VALUES"
                         " (1, 'School', ?, ?, ?), (2, 'Other', ?, NULL, NULL)", (now, now, now, now))
            conn.execute("INSERT INTO users (id, email, name, password_hash, created_at) VALUES"
                         " (1, 'a@example.com', 'A', 'x', ?), (2, 'b@example.com', 'B', 'x', ?)", (now, now))
            conn.execute("INSERT INTO memberships (user_id, org_id, role, created_at) VALUES"
                         " (1, 1, 'owner', ?), (2, 2, 'owner', ?)", (now, now))
            conn.commit()
            self.assertEqual(migrate(conn), dbmod.SCHEMA_VERSION)
            used = dict(conn.execute("SELECT id, pilot_used_at FROM users").fetchall())
            self.assertEqual(used, {1: now, 2: None})
            self.assertEqual(conn.execute("SELECT pause_open FROM orgs WHERE id = 1").fetchone()[0], 0)
            conn.close()


if __name__ == "__main__":
    unittest.main()
