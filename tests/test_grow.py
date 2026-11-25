"""Keeping customers and growing: pause instead of cancel, the one-time save
offer, cancelling in one click, upgrade offers (the Academy for Pro, the
yearly saving for a second location) with their weekly limit and "No
thanks", switching to yearly or to Plus, locations, and the trade pages.

Stripe is a small in-memory stand-in for the subscription calls the app
makes (read, update), patched in at academy_plan._stripe."""

import hashlib
import hmac
import html
import json
import os
import re
import sys
import tempfile
import time
import unittest
from contextlib import closing
from datetime import datetime, timedelta
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from e2e_helpers import flashes, post_forms  # noqa: E402
from test_webapp import AppTestCase, first_rule  # noqa: E402

from omniarmor_app import academy, academy_plan, nudges, plans, trades, usage  # noqa: E402
from omniarmor_app import db as dbmod  # noqa: E402
from omniarmor_app.catalog import INDUSTRIES, find_rule  # noqa: E402
from omniarmor_app.db import connect, iso, migrate, utcnow  # noqa: E402
from omniarmor_app.jobs import run_pause_sweep  # noqa: E402
from omniarmor_app.reminders import run_clock_alerts, run_reminders  # noqa: E402

WEBHOOK_SECRET = "whsec_grow_test"
PRICES = {"PRO_STRIPE_PRICE": "price_pro", "PLUS_STRIPE_PRICE": "price_plus",
          "PLUS_BUNDLE_UPGRADE_STRIPE_PRICE": "price_plus_bundle",
          "PRO_YEARLY_STRIPE_PRICE": "price_pro_year", "PLUS_YEARLY_STRIPE_PRICE": "price_plus_year"}
COUPON = "save25x2"
DAY = 86400


def words(page):
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", page)).split())


class GrowCase(AppTestCase):
    """A signed-up workspace (Logistics and Banking), its owner signed in."""

    def setUp(self):
        super().setUp()
        self.signup()
        with closing(self.db()) as conn:
            self.org_id = conn.execute("SELECT id FROM orgs").fetchone()[0]
        self.check = first_rule(18, kind="max").key

    def set_org(self, **fields):
        with closing(self.db()) as conn:
            conn.execute(f"UPDATE orgs SET {', '.join(f'{k} = ?' for k in fields)} WHERE id = ?",
                         (*fields.values(), self.org_id))
            conn.commit()

    def org(self):
        with closing(self.db()) as conn:
            return conn.execute("SELECT * FROM orgs WHERE id = ?", (self.org_id,)).fetchone()

    def on_plan(self, kind="pro", interval="month", renews_days=20, **more):
        """The trial over and a paid plan, as Stripe's webhook would leave it."""
        fields = {"academy_trial_ends": "2000-01-01T00:00:00+00:00", "academy_status": "active", "plan": kind,
                  "plan_interval": interval, "academy_renews_at": iso(utcnow() + timedelta(days=renews_days)),
                  "academy_ends_at": None}
        fields.update(more)
        self.set_org(**fields)

    def page(self, path, client=None):
        response = (client or self.client).get(path)
        self.assertEqual(response.status_code, 200, path)
        return response.get_data(as_text=True)

    def can_save(self, value):
        self.change(18, self.check, value=str(value))
        with closing(self.db()) as conn:
            row = conn.execute("SELECT value_num FROM items WHERE rule_key = ?", (self.check,)).fetchone()
        return row is not None and row[0] == value

    def usage_today(self, event):
        with closing(self.db()) as conn:
            return usage.last_days(conn)["days"][0][event]


class FakeSubscriptions:
    """Stripe's subscription calls, in memory: read one, update one."""

    def __init__(self, test, sub_id="sub_1", price="price_pro"):
        self.test = test
        self.calls = []
        self.fail = False
        now = int(time.time())
        self.sub = {"id": sub_id, "object": "subscription", "customer": "cus_1", "status": "active",
                    "created": now, "current_period_end": now + 20 * DAY, "cancel_at_period_end": False,
                    "pause_collection": None, "discounts": [], "metadata": {"org_id": str(test.org_id)},
                    "items": {"data": [{"id": "si_1", "price": {"id": price}, "quantity": 1}]}}

    def __call__(self, cfg, path, fields, method="POST"):
        self.calls.append((method, path, dict(fields)))
        if self.fail:
            raise academy_plan.StripeError("Your card was declined.")
        if path != f"subscriptions/{self.sub['id']}":
            raise AssertionError(path)
        if method == "GET":
            return json.loads(json.dumps(self.sub))
        if "pause_collection[resumes_at]" in fields:
            self.sub["pause_collection"] = {"behavior": fields["pause_collection[behavior]"],
                                            "resumes_at": int(fields["pause_collection[resumes_at]"])}
        if fields.get("pause_collection") == "":
            self.sub["pause_collection"] = None
        if "cancel_at_period_end" in fields:
            on = fields["cancel_at_period_end"] == "true"
            self.sub["cancel_at_period_end"] = on
            self.sub["cancel_at"] = self.sub["current_period_end"] if on else None
        if "discounts[0][coupon]" in fields:
            self.sub["discounts"] = [{"coupon": {"id": fields["discounts[0][coupon]"]}}]
        if "items[0][price]" in fields:
            assert fields["items[0][id]"] == "si_1"
            self.sub["items"]["data"][0]["price"] = {"id": fields["items[0][price]"]}
            if fields["items[0][price]"].endswith("_year"):
                self.sub["current_period_end"] = int(time.time()) + 365 * DAY
        return json.loads(json.dumps(self.sub))

    def posts(self):
        return [fields for method, _, fields in self.calls if method == "POST"]


class StripeGrowCase(GrowCase):
    """A Pro subscription paid monthly through Stripe."""

    def setUp(self):
        super().setUp()
        self.app.config.update(STRIPE_SECRET_KEY="sk_test_grow", STRIPE_WEBHOOK_SECRET=WEBHOOK_SECRET,
                               SAVE_OFFER_STRIPE_COUPON=COUPON, **PRICES)
        self.on_plan("pro", stripe_customer_id="cus_1", stripe_subscription_id="sub_1")
        self.stripe = FakeSubscriptions(self)
        patcher = mock.patch.object(academy_plan, "_stripe", side_effect=self.stripe)
        patcher.start()
        self.addCleanup(patcher.stop)

    def webhook(self, event_id, kind, obj, created):
        payload = json.dumps({"id": event_id, "type": kind, "created": created, "data": {"object": obj}}).encode()
        stamp = int(time.time())
        sig = hmac.new(WEBHOOK_SECRET.encode(), f"{stamp}.".encode() + payload, hashlib.sha256).hexdigest()
        response = self.app.test_client().post("/billing/stripe/webhook", data=payload,
                                               headers={"Stripe-Signature": f"t={stamp},v1={sig}"})
        self.assertEqual(response.status_code, 200)


# --- Pause instead of cancel -------------------------------------------------------

class TestPause(GrowCase):
    def test_the_cancel_screen_offers_a_pause_and_keeps_cancel_one_click(self):
        self.on_plan("pro")
        page = self.page("/app/plan/cancel")
        forms = post_forms(page)
        months = sorted(int(f.field("months")["value"]) for f in forms if f.action == "/app/plan/pause")
        self.assertEqual(months, [1, 2, 3])
        # Cancel is a button on the same screen, not behind the offers.
        self.assertEqual([f.action for f in forms if f.action == "/app/plan/cancel"], ["/app/plan/cancel"])
        self.assertIn("Cancel my plan", page)
        text = words(page)
        self.assertIn("You aren't charged.", text)
        self.assertIn("Reminder emails and alerts stop.", text)
        self.assertIn("Your records are kept", text)
        self.assertIn(f"We email you {plans.RESUME_NOTICE.days} days before", text)
        # The plan page links to it.
        self.assertIn('href="/app/plan/cancel"', self.page("/app/plan"))

    def test_a_pause_stops_reminders_and_saving_and_keeps_the_data(self):
        self.on_plan("pro")
        self.assertTrue(self.can_save(5))
        response = self.post("/app/plan/pause", {"months": "2"})
        self.assertEqual(response.status_code, 302)
        org = self.org()
        until = datetime.fromisoformat(org["paused_until"])
        expected = plans.add_months(utcnow(), 2)
        self.assertLess(abs((until - expected).total_seconds()), 60)
        access = plans.access(org)
        self.assertTrue(access["paused"])
        self.assertTrue(access["read_only"])
        self.assertEqual(access["reason"], "paused")
        self.assertFalse(access["academy"])
        # Read-only: no new reading, the old one kept.
        self.assertFalse(self.can_save(9))
        with closing(self.db()) as conn:
            self.assertEqual(conn.execute("SELECT value_num FROM items WHERE rule_key = ?",
                                          (self.check,)).fetchone()[0], 5)
            # Reminders and time-limit alerts skip it.
            summary = run_reminders(conn, self.app.config)
            self.assertEqual((summary["orgs"], summary["paused"]), (0, 1))
            conn.execute("UPDATE items SET value_date = '2026-01-01T10:00:00+00:00' WHERE org_id = ?", (self.org_id,))
            conn.commit()
            self.assertEqual(run_clock_alerts(conn, self.app.config)["paused"], 1)
        # Every screen says so.
        overview = words(self.page("/app"))
        self.assertIn("Paused until", overview)
        self.assertIn("no reminder emails or alerts go out", overview)
        self.assertIn("data-paused-banner", self.page("/app"))
        self.assertIn("Off while your plan is paused", words(self.page("/app/settings")))
        self.assertIn("is paused until", words(self.page("/app/plan")))
        # The report and its download still work.
        self.assertEqual(self.client.get("/app/report.csv").status_code, 200)
        self.assertEqual(self.usage_today("plan_pauses"), 1)

    def test_it_starts_again_on_the_chosen_day_with_an_email_three_days_before(self):
        self.on_plan("pro")
        self.post("/app/plan/pause", {"months": "1"})
        org = self.org()
        until = datetime.fromisoformat(org["paused_until"])
        with closing(self.db()) as conn:
            # Long before the end: no email.
            self.assertEqual(run_pause_sweep(conn, self.app.config, now=until - timedelta(days=10))["notices"], 0)
            # Three days before: one email to the owner, once.
            self.assertEqual(run_pause_sweep(conn, self.app.config, now=until - timedelta(days=3))["notices"], 1)
            self.assertEqual(run_pause_sweep(conn, self.app.config, now=until - timedelta(days=2))["notices"], 0)
            sent = conn.execute("SELECT * FROM notifications WHERE kind = 'plan'").fetchall()
            self.assertEqual(len(sent), 1)
            self.assertEqual(sent[0]["recipient"], "owner@example.com")
            self.assertIn("starts again", sent[0]["subject"])
            self.assertIn("/app/plan/cancel", sent[0]["body"])
            # Still paused a minute before; on again a minute after, without anyone doing anything.
            self.assertTrue(plans.access(org, now=until - timedelta(minutes=1))["paused"])
            after = plans.access(org, now=until + timedelta(minutes=1))
            self.assertFalse(after["paused"])
            self.assertTrue(after["tracker"])
            # The sweep then tidies the pause away, and reminders go out again.
            self.assertEqual(run_pause_sweep(conn, self.app.config, now=until + timedelta(minutes=1))["ended"], 1)
            self.assertIsNone(conn.execute("SELECT paused_until FROM orgs").fetchone()[0])
            self.assertEqual(run_reminders(conn, self.app.config)["paused"], 0)
        self.assertTrue(self.can_save(7))

    def test_start_again_now(self):
        self.on_plan("plus")
        self.post("/app/plan/pause", {"months": "3"})
        self.assertTrue(plans.access(self.org())["paused"])
        self.post("/app/plan/resume")
        self.assertFalse(plans.access(self.org())["paused"])
        self.assertTrue(self.can_save(3))

    def test_what_cannot_be_paused(self):
        # A yearly plan is paid for the year; a cancelled plan, one past due, an unknown length: refused.
        for kind, interval, extra in (("pro", "year", {}), ("pro", "month", {"academy_ends_at": iso(utcnow())}),
                                      ("pro", "month", {"academy_status": "past_due"})):
            self.on_plan(kind, interval, **extra)
            self.post("/app/plan/pause", {"months": "1"})
            self.assertIsNone(self.org()["paused_until"], (kind, interval, extra))
        self.on_plan("pro")
        self.post("/app/plan/pause", {"months": "6"})
        self.assertIsNone(self.org()["paused_until"])
        # Without a plan there is nothing to cancel or pause.
        self.set_org(academy_status="none", plan="none")
        self.assertEqual(self.client.get("/app/plan/cancel").status_code, 302)

    def test_only_the_owner(self):
        self.on_plan("pro")
        link = re.search(r"(https://\S+/signup\?invite=[\w-]+)", " ".join(
            flashes(self.client.post("/app/settings/invite", data={"csrf_token": self.csrf()},
                                     follow_redirects=True).get_data(as_text=True)))).group(1)
        member = self.app.test_client()
        self.signup("member@example.com", client=member, invite=link.split("invite=")[1], name="Max Member")
        self.assertEqual(member.get("/app/plan/cancel").status_code, 403)
        for path in ("/app/plan/pause", "/app/plan/cancel", "/app/plan/save-offer", "/app/plan/switch"):
            self.assertEqual(self.post(path, {"months": "1"}, client=member).status_code, 403, path)
        self.assertIsNone(self.org()["paused_until"])


class TestPauseWithStripe(StripeGrowCase):
    def test_billing_stops_through_stripe_and_the_webhook_agrees(self):
        self.post("/app/plan/pause", {"months": "2"})
        [fields] = self.stripe.posts()
        self.assertEqual(fields["pause_collection[behavior]"], "void")
        resumes = int(fields["pause_collection[resumes_at]"])
        self.assertLess(abs(resumes - plans.add_months(utcnow(), 2).timestamp()), 60)
        org = self.org()
        self.assertEqual(datetime.fromisoformat(org["paused_until"]).timestamp(), resumes)
        self.assertTrue(plans.access(org)["paused"])
        # Stripe's webhook for the pause, then for its end (Stripe resumes by itself at resumes_at).
        now = int(time.time())
        self.webhook("evt_1", "customer.subscription.updated", self.stripe.sub, now)
        self.assertTrue(plans.access(self.org())["paused"])
        resumed = dict(self.stripe.sub, pause_collection=None)
        self.webhook("evt_2", "customer.subscription.updated", resumed, now + 5)
        self.assertIsNone(self.org()["paused_until"])
        self.assertFalse(plans.access(self.org())["paused"])

    def test_a_stripe_failure_changes_nothing(self):
        self.stripe.fail = True
        response = self.post("/app/plan/pause", {"months": "1"}, follow_redirects=True)
        self.assertIn("nothing changed", words(response.get_data(as_text=True)))
        self.assertIsNone(self.org()["paused_until"])

    def test_resume_now_clears_the_pause_in_stripe(self):
        self.post("/app/plan/pause", {"months": "1"})
        self.post("/app/plan/resume")
        self.assertEqual(self.stripe.posts()[-1], {"pause_collection": ""})
        self.assertIsNone(self.org()["paused_until"])


# --- The save offer -----------------------------------------------------------------

class TestSaveOffer(StripeGrowCase):
    def test_once_per_workspace_ever(self):
        page = self.page("/app/plan/cancel")
        self.assertIn("data-save-offer", page)
        text = words(page)
        self.assertIn("25% off your next 2 months", text)
        price = plans.price_label(plans.discounted(plans.PRO.dollars, 25), per=False)
        self.assertIn(f"{price} instead of {plans.price_label(plans.PRO.dollars, per=False)}", text)
        self.post("/app/plan/save-offer")
        self.assertEqual(self.stripe.posts(), [{"discounts[0][coupon]": COUPON}])
        self.assertIsNotNone(self.org()["save_offer_used_at"])
        self.assertEqual(self.usage_today("save_offers"), 1)
        # Never again: not offered, and a second try reaches no Stripe call.
        self.assertNotIn("data-save-offer", self.page("/app/plan/cancel"))
        response = self.post("/app/plan/save-offer", follow_redirects=True)
        self.assertIn("isn't available for this workspace", words(response.get_data(as_text=True)))
        self.assertEqual(len(self.stripe.posts()), 1)
        # Not even after a cancel and a new subscription.
        self.set_org(stripe_subscription_id="sub_2")
        self.stripe.sub["id"] = "sub_2"
        self.assertNotIn("data-save-offer", self.page("/app/plan/cancel"))
        self.assertEqual(self.usage_today("save_offers"), 1)

    def test_the_amount_comes_from_the_settings(self):
        self.app.config.update(SAVE_OFFER_PERCENT=40, SAVE_OFFER_MONTHS=3)
        self.assertIn("40% off your next 3 months", words(self.page("/app/plan/cancel")))

    def test_no_coupon_no_offer_and_not_for_yearly(self):
        self.app.config["SAVE_OFFER_STRIPE_COUPON"] = ""
        self.assertNotIn("data-save-offer", self.page("/app/plan/cancel"))
        self.post("/app/plan/save-offer")
        self.assertEqual(self.stripe.posts(), [])
        self.app.config["SAVE_OFFER_STRIPE_COUPON"] = COUPON
        self.set_org(plan_interval="year")
        self.assertNotIn("data-save-offer", self.page("/app/plan/cancel"))

    def test_a_failed_coupon_leaves_the_offer_unused(self):
        self.stripe.fail = True
        self.post("/app/plan/save-offer")
        self.assertIsNone(self.org()["save_offer_used_at"])


# --- Cancelling ---------------------------------------------------------------------

class TestCancel(StripeGrowCase):
    def test_cancel_in_one_click_stays_on_to_the_end_of_the_paid_time(self):
        page = self.page("/app/plan/cancel")
        [form] = [f for f in post_forms(page) if f.action == "/app/plan/cancel"]
        response = self.client.post(form.action, data=form.values(), follow_redirects=True)
        self.assertEqual(self.stripe.posts(), [{"cancel_at_period_end": "true"}])
        org = self.org()
        self.assertIsNotNone(org["academy_ends_at"])
        access = plans.access(org)
        self.assertTrue(access["paid"])
        self.assertTrue(access["tracker"])
        self.assertIn("Your plan is cancelled. It stays on until", words(response.get_data(as_text=True)))
        self.assertEqual(self.usage_today("plan_cancels"), 1)
        # Taken back before it ends.
        self.assertIn("Keep my plan", self.page("/app/plan/cancel"))
        self.post("/app/plan/keep")
        self.assertEqual(self.stripe.posts()[-1], {"cancel_at_period_end": "false"})
        self.assertIsNone(self.org()["academy_ends_at"])

    def test_cancel_still_works_while_paused_and_after_the_save_offer(self):
        self.post("/app/plan/save-offer")
        self.post("/app/plan/pause", {"months": "1"})
        page = self.page("/app/plan/cancel")
        self.assertTrue([f for f in post_forms(page) if f.action == "/app/plan/cancel"])
        self.post("/app/plan/cancel")
        self.assertEqual(self.stripe.posts()[-1], {"cancel_at_period_end": "true"})
        self.assertIsNotNone(self.org()["academy_ends_at"])

    def test_the_portal_still_cancels_too(self):
        self.assertIn("Manage billing", self.page("/app/plan"))

    def test_the_operator_sees_pauses_saves_and_cancels(self):
        self.app.config["OPERATOR_EMAIL"] = "owner@example.com"
        self.make_operator()
        self.post("/app/plan/save-offer")
        self.post("/app/plan/pause", {"months": "1"})
        self.post("/app/plan/cancel")
        page = words(self.page("/app/settings"))
        for name in ("Plans paused 1 1 1", "Save offers taken 1 1 1", "Plans cancelled 1 1 1"):
            self.assertIn(name, page)


class TestCancelByHand(GrowCase):
    def test_a_plan_set_by_hand_ends_at_its_renewal(self):
        self.on_plan("pro")
        self.post("/app/plan/cancel")
        org = self.org()
        self.assertEqual(org["academy_ends_at"], org["academy_renews_at"])
        self.set_org(academy_renews_at=None, academy_ends_at=None)
        self.post("/app/plan/cancel")
        self.assertEqual(self.org()["academy_status"], "canceled")
        self.assertTrue(plans.access(self.org())["read_only"])


# --- Switching: to yearly, to Plus ---------------------------------------------------

class TestSwitch(StripeGrowCase):
    def test_switch_to_yearly_two_months_free(self):
        page = self.page("/app/plan")
        self.assertIn("data-yearly-offer", page)
        text = words(page)
        self.assertIn(f"Switch to yearly, {plans.free_label()}", text)
        self.assertIn(f"you save {plans.price_label(plans.yearly_saving(plans.PRO.dollars), plans.YEAR, per=False)}",
                      text)
        self.assertIn("data-yearly-switch-link", self.page("/app/settings"))
        self.post("/app/plan/switch", {"to": "yearly"})
        fields = self.stripe.posts()[-1]
        self.assertEqual((fields["items[0][price]"], fields["proration_behavior"], fields["payment_behavior"]),
                         ("price_pro_year", "always_invoice", "error_if_incomplete"))
        org = self.org()
        self.assertEqual((org["plan"], org["plan_interval"]), ("pro", "year"))
        self.assertNotIn("data-yearly-offer", self.page("/app/plan"))
        self.assertEqual(self.usage_today("plan_switches"), 1)

    def test_no_yearly_offer_without_a_yearly_price(self):
        self.app.config["PRO_YEARLY_STRIPE_PRICE"] = ""
        self.assertNotIn("data-yearly-offer", self.page("/app/plan"))
        self.post("/app/plan/switch", {"to": "yearly"})
        self.assertEqual(self.stripe.posts(), [])

    def test_upgrade_to_plus_uses_the_plus_price(self):
        self.post("/app/plan/switch", {"to": "plus"})
        self.assertEqual(self.stripe.posts()[-1]["items[0][price]"], "price_plus")
        self.assertEqual(self.org()["plan"], "plus")
        self.assertTrue(plans.access(self.org())["academy"])

    def test_a_declined_card_changes_nothing(self):
        self.stripe.fail = True
        self.post("/app/plan/switch", {"to": "yearly"})
        self.assertEqual(self.org()["plan_interval"], "month")


class TestReviewFixes(StripeGrowCase):
    """Found in the pre-launch review: ways a plan could be used without
    paying for it, or paid for and then not bought again."""

    def test_starting_again_after_a_skipped_renewal_bills_from_today(self):
        """A pause voids the renewals that fall inside it. Starting again by
        hand after one of them used to run free to the next renewal, and
        pausing again just before it made every month free."""
        self.post("/app/plan/pause", {"months": "1"})
        paused_at = datetime.fromisoformat(self.org()["paused_at"]).timestamp()
        # A renewal falls inside the pause: Stripe voids its invoice and starts a new period.
        self.stripe.sub["current_period_start"] = int(paused_at) + 2 * DAY
        self.post("/app/plan/resume")
        fields = self.stripe.posts()[-1]
        self.assertEqual(fields["pause_collection"], "")
        self.assertEqual((fields.get("billing_cycle_anchor"), fields.get("proration_behavior")), ("now", "none"))
        self.assertFalse(plans.access(self.org())["paused"])

    def test_starting_again_inside_the_period_paid_for_bills_nothing_extra(self):
        self.stripe.sub["current_period_start"] = int(time.time()) - 5 * DAY
        self.post("/app/plan/pause", {"months": "1"})
        self.post("/app/plan/resume")
        self.assertEqual(self.stripe.posts()[-1], {"pause_collection": ""})

    def test_no_yearly_switch_while_the_save_offer_discount_runs(self):
        """The save offer's coupon is on the subscription for its months, and
        Stripe takes it off every invoice then, a year's switch charge too."""
        self.post("/app/plan/save-offer")
        self.assertNotIn("data-yearly-offer", self.page("/app/plan"))
        self.post("/app/plan/switch", {"to": "yearly"})
        self.assertEqual([f for f in self.stripe.posts() if "items[0][price]" in f], [])
        self.assertEqual(self.org()["plan_interval"], "month")
        # Once its months are over, the yearly switch is back.
        months = self.app.config["SAVE_OFFER_MONTHS"]
        long_ago = plans.add_months(utcnow(), -months) - timedelta(days=1)
        self.set_org(save_offer_used_at=iso(long_ago))
        self.assertIn("data-yearly-offer", self.page("/app/plan"))
        # Moving up to Plus, monthly, is still fine: the offer was for the coming months.
        self.set_org(save_offer_used_at=iso(utcnow()))
        self.post("/app/plan/switch", {"to": "plus"})
        self.assertEqual(self.stripe.posts()[-1]["items[0][price]"], "price_plus")


class TestPausedAcademy(GrowCase):
    def test_a_paused_plan_doesnt_say_every_world_is_open(self):
        """While paused the Academy's paid worlds are locked, but its pages
        still said "You have Plus: every track and every world"."""
        self.on_plan("plus")
        self.post("/app/plan/pause", {"months": "1"})
        status = academy_plan.plan_status(self.org())
        self.assertNotEqual(status["access"], "paid")
        self.assertFalse(plans.access(self.org())["academy"])
        self.assertNotIn("every track and every world", words(self.page("/app/academy")))


class TestBuyingAfterAPlanSetByHand(GrowCase):
    def setUp(self):
        super().setUp()
        self.app.config.update(STRIPE_SECRET_KEY="sk_test_grow", **PRICES)

    def test_checkout_opens_once_a_plan_set_by_hand_has_ended(self):
        """A plan set by hand ends on its date, but its status stays 'active':
        checkout said "You already have a plan" for good."""
        self.on_plan("pro", academy_ends_at=iso(utcnow() - timedelta(days=1)))
        self.assertFalse(plans.access(self.org())["paid"])
        with mock.patch.object(academy_plan, "_stripe", return_value={"url": "https://checkout.stripe.test/x"}):
            response = self.post("/app/plan/checkout", {"plan": "pro", "interval": "month"})
        self.assertEqual(response.status_code, 303)
        self.assertEqual(response.headers["Location"], "https://checkout.stripe.test/x")

    def test_while_it_runs_the_card_starts_the_day_it_ends(self):
        ends = utcnow().replace(microsecond=0) + timedelta(days=5)
        self.on_plan("pro", academy_ends_at=iso(ends))
        with mock.patch.object(academy_plan, "_stripe", return_value={"url": "https://checkout.stripe.test/x"}) as stripe:
            response = self.post("/app/plan/checkout", {"plan": "pro", "interval": "month"})
            self.assertEqual(response.status_code, 303)
            fields = stripe.call_args[0][2]
        self.assertEqual(int(fields["subscription_data[trial_end]"]), int(ends.timestamp()))
        # Another plan isn't bought that way while it runs.
        with mock.patch.object(academy_plan, "_stripe") as stripe:
            response = self.post("/app/plan/checkout", {"plan": "plus", "interval": "month"})
        self.assertEqual(response.status_code, 302)
        stripe.assert_not_called()


# --- Upgrade offers: weekly at most, never after "No thanks" ---------------------------

class TestAcademyNudge(StripeGrowCase):
    def setUp(self):
        super().setUp()
        self.post("/app/academy/learners", {"nickname": "Sam", "avatar": "rocket", "track": "launchpad"})
        with closing(self.db()) as conn:
            self.lid = conn.execute("SELECT id FROM learners").fetchone()[0]
        self.locked = next(n for n in academy.TRACKS["launchpad"].topics if n not in academy_plan.FREE_WORLDS)

    def age_offers(self, days):
        with closing(self.db()) as conn:
            conn.execute("UPDATE nudges SET shown_at = ?", (iso(utcnow() - timedelta(days=days)),))
            conn.commit()

    def test_opening_the_academy_shows_a_lesson_preview_once_a_week(self):
        page = self.page("/app/academy")
        self.assertIn("data-academy-offer", page)
        text = words(page)
        self.assertIn("Plus includes the Academy", text)
        self.assertIn("Lesson preview", text)
        self.assertIn(plans.PLUS.price, text)
        self.assertIn("No thanks, don't show this again", text)
        # The button switches this Pro subscription to Plus.
        self.assertTrue([f for f in post_forms(page) if f.action == "/app/plan/switch"])
        # Not again this week, anywhere.
        self.assertNotIn("data-academy-offer", self.page("/app/academy"))
        response = self.client.get(f"/app/academy/{self.lid}/world/{self.locked}")
        self.assertTrue(response.headers["Location"].endswith("/app/plan"))
        self.age_offers(6)
        self.assertNotIn("data-academy-offer", self.page("/app/academy"))
        # A week later, once more.
        self.age_offers(8)
        self.assertIn("data-academy-offer", self.page("/app/academy"))
        self.assertEqual(self.usage_today("nudges_shown"), 2)

    def test_tapping_a_locked_world_previews_its_first_lesson(self):
        response = self.client.get(f"/app/academy/{self.lid}/world/{self.locked}")
        self.assertTrue(response.headers["Location"].endswith(f"/world/{self.locked}/preview"))
        page = self.page(response.headers["Location"])
        world = academy.world(self.locked)
        self.assertIn(world.title, page)
        first_card = academy.story(academy.TRACKS["launchpad"], self.locked, 1, "Acme Logistics", [1, 18])[0][0]
        self.assertIn(html.escape(first_card, quote=True), page)
        self.assertIn("Plus includes the Academy", words(page))
        # The next tap this week goes to the plan page, as before.
        response = self.client.get(f"/app/academy/{self.lid}/world/{self.locked}")
        self.assertTrue(response.headers["Location"].endswith("/app/plan"))

    def test_no_thanks_is_for_good(self):
        page = self.page("/app/academy")
        [form] = [f for f in post_forms(page) if f.action == "/app/nudges/academy/dismiss"]
        self.client.post(form.action, data=form.values())
        self.age_offers(30)
        self.assertNotIn("data-academy-offer", self.page("/app/academy"))
        response = self.client.get(f"/app/academy/{self.lid}/world/{self.locked}")
        self.assertTrue(response.headers["Location"].endswith("/app/plan"))
        self.assertEqual(self.post("/app/nudges/nonsense/dismiss").status_code, 404)

    def test_not_for_plus_trial_paused_or_team_members(self):
        self.set_org(plan="plus")
        self.assertNotIn("data-academy-offer", self.page("/app/academy"))
        self.set_org(plan="pro", academy_status="none", academy_trial_ends=iso(utcnow() + timedelta(days=5)))
        self.assertNotIn("data-academy-offer", self.page("/app/academy"))
        self.on_plan("pro", stripe_subscription_id="sub_1", paused_until=iso(utcnow() + timedelta(days=9)))
        self.assertNotIn("data-academy-offer", self.page("/app/academy"))
        self.set_org(paused_until=None)
        with closing(self.db()) as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM nudges").fetchone()[0], 0)
        self.set_org(stripe_subscription_id="sub_1")
        with closing(self.db()) as conn:
            conn.execute("UPDATE memberships SET role = 'member'")
            conn.commit()
        self.assertNotIn("data-academy-offer", self.page("/app/academy"))

    def test_the_bundle_offers_plus_at_the_difference(self):
        self.set_org(academy_status="none", plan="none", stripe_subscription_id=None,
                     bundle_report_at=iso(utcnow()))
        page = self.page("/app/academy")
        self.assertIn(plans.price_label(plans.bundle_upgrade_dollars()), words(page))
        [form] = [f for f in post_forms(page) if f.action == "/app/plan/checkout"]
        self.assertEqual(form.field("plan")["value"], "plus")


class TestLocations(GrowCase):
    def setUp(self):
        super().setUp()
        self.app.config.update(**PRICES)

    def test_adding_a_second_location_shows_the_yearly_saving_once(self):
        response = self.post("/app/settings/locations/add", {"name": "Acme North"})
        self.assertEqual(response.status_code, 302)
        with closing(self.db()) as conn:
            orgs = conn.execute("SELECT * FROM orgs ORDER BY id").fetchall()
            self.assertEqual(len(orgs), 2)
            self.assertEqual(conn.execute("SELECT role FROM memberships WHERE org_id = ?",
                                          (orgs[1]["id"],)).fetchone()[0], "owner")
            self.assertEqual([r[0] for r in conn.execute("SELECT industry_id FROM org_industries WHERE org_id = ?"
                                                         " ORDER BY industry_id", (orgs[1]["id"],))], [1, 18])
        page = self.page("/app")
        self.assertIn("Acme North", page)
        self.assertIn("data-location-offer", page)
        each = plans.price_label(plans.yearly_saving(plans.PRO.dollars), plans.YEAR, per=False)
        both = plans.price_label(plans.yearly_saving(plans.PRO.dollars) * 2, plans.YEAR, per=False)
        self.assertIn(f"saves {each} per location, {both} for your 2 locations", words(page))
        self.assertNotIn("data-location-offer", self.page("/app"))
        self.assertEqual(self.usage_today("locations_added"), 1)

    def test_switching_locations(self):
        self.post("/app/settings/locations/add", {"name": "Acme North"})
        with closing(self.db()) as conn:
            first, second = [r[0] for r in conn.execute("SELECT id FROM orgs ORDER BY id")]
        self.assertIn("Acme North", self.page("/app/settings"))
        self.post(f"/app/settings/locations/{first}/switch")
        self.assertIn("Acme Logistics", self.page("/app/settings").split("<h1>")[0])
        # Another business's workspace can't be switched to.
        other = self.app.test_client()
        self.signup("someone@example.org", client=other)
        with closing(self.db()) as conn:
            stranger = conn.execute("SELECT MAX(id) FROM orgs").fetchone()[0]
        self.assertEqual(self.post(f"/app/settings/locations/{stranger}/switch").status_code, 404)
        self.assertEqual(self.post(f"/app/settings/locations/{second}/switch", client=other).status_code, 404)

    def test_no_saving_shown_without_yearly_prices_or_after_no_thanks(self):
        self.app.config.update(PRO_YEARLY_STRIPE_PRICE="", PLUS_YEARLY_STRIPE_PRICE="")
        self.post("/app/settings/locations/add", {"name": "Acme North"})
        self.assertNotIn("data-location-offer", self.page("/app"))
        self.app.config.update(**PRICES)
        with closing(self.db()) as conn:
            user = conn.execute("SELECT * FROM users").fetchone()
            nudges.dismiss(conn, user["id"], "second_location")
        self.assertNotIn("data-location-offer", self.page("/app"))

    def test_one_offer_a_week_across_kinds(self):
        with closing(self.db()) as conn:
            user = conn.execute("SELECT * FROM users").fetchone()
            nudges.mark_shown(conn, user["id"], "academy")
        self.post("/app/settings/locations/add", {"name": "Acme North"})
        self.assertNotIn("data-location-offer", self.page("/app"))


# --- Trade pages ----------------------------------------------------------------------

class TestTradePages(AppTestCase):
    def test_each_page_renders_with_its_checklists_and_price(self):
        for t in trades.TRADES:
            response = self.client.get(f"/for/{t.slug}")
            self.assertEqual(response.status_code, 200, t.slug)
            page = response.get_data(as_text=True)
            text = words(page)
            self.assertIn(f"<title>{html.escape(t.title, quote=True)} · OmniArmor.ai</title>", page)
            self.assertIn(f'<meta name="description" content="{html.escape(t.description, quote=True)}">', page)
            self.assertIn(f'<link rel="canonical" href="https://omniarmor.test/for/{t.slug}">', page)
            if t.academy:
                # A school's page has the school's prices, not a business's.
                self.assertNotIn(plans.PRO.price, text)
                self.assertIn(plans.CLASSROOM.yearly_price, text)
                self.assertIn(plans.SCHOOL.yearly_price, text)
            else:
                self.assertIn(plans.PRO.price, text)
                self.assertIn(plans.PLUS.price, text)
            self.assertIn("helps you stay on top of your checklists", text)
            self.assertIn("doesn't guarantee compliance and it isn't legal advice", text)
            for industry_id, keys, _ in t.groups:
                for key in keys:
                    rule = find_rule(industry_id, key)
                    self.assertIsNotNone(rule, (t.slug, industry_id, key))
                    self.assertIn(html.escape(rule.title, quote=True), page)
            if t.academy:
                self.assertIn("/signup?then=classes", page)
                continue
            # Sign-up from the page picks its checklists.
            ids = [i for i, _, _ in t.groups]
            self.assertIn("/signup?" + "&amp;".join(f"industry={i}" for i in ids), page)
            signup = self.client.get("/signup?" + "&".join(f"industry={i}" for i in ids)).get_data(as_text=True)
            for i in ids:
                self.assertIn(f'value="{i}" checked', signup)

    def test_they_are_in_the_sitemap_and_the_index(self):
        sitemap = self.client.get("/sitemap.xml").get_data(as_text=True)
        index = self.client.get("/industries").get_data(as_text=True)
        for t in trades.TRADES:
            self.assertIn(f"<loc>https://omniarmor.test/for/{t.slug}</loc>", sitemap)
            self.assertIn(f'href="/for/{t.slug}"', index)
        self.app.config["NOINDEX"] = True
        self.assertNotIn("/for/", self.client.get("/sitemap.xml").get_data(as_text=True))

    def test_honest_words_only(self):
        for t in trades.TRADES:
            text = words(self.client.get(f"/for/{t.slug}").get_data(as_text=True)).lower()
            self.assertNotIn("guaranteed", text)
            self.assertNotIn("we guarantee", text)
            self.assertNotIn("testimonial", text)
            self.assertIsNone(re.search(r"\d+ ?%", text), t.slug)   # no statistics
            self.assertNotIn("cannabis", text)

    def test_no_trade_repeats_an_industry_page_and_unknown_ones_404(self):
        sectors = {i["sector"].lower() for i in INDUSTRIES.values()}
        for t in trades.TRADES:
            if t.own:
                # A trade with checklists made for it (schools) brings them
                # together on one page, beside the Academy for classrooms.
                self.assertTrue(all(i in INDUSTRIES for i in t.own))
                continue
            self.assertNotIn(t.name.lower(), sectors)
        self.assertEqual(self.client.get("/for/nothing-here").status_code, 404)
        self.assertEqual(self.client.get("/for/Salons-And-Barbershops").status_code, 301)


# --- The schema -------------------------------------------------------------------------

class TestMigration20(unittest.TestCase):
    def test_upgrade_keeps_plans_and_adds_the_new_columns(self):
        with tempfile.TemporaryDirectory() as tmp:
            conn = connect(os.path.join(tmp, "old.db"))
            with mock.patch.object(dbmod, "MIGRATIONS", [m for m in dbmod.MIGRATIONS if m[0] <= 19]):
                self.assertEqual(migrate(conn), 19)
            conn.execute("INSERT INTO orgs (id, name, created_at, academy_status, plan) VALUES"
                         " (1, 'Paid', '2026-01-01T00:00:00+00:00', 'active', 'pro')")
            conn.commit()
            self.assertEqual(migrate(conn), dbmod.SCHEMA_VERSION)
            row = conn.execute("SELECT * FROM orgs").fetchone()
            self.assertEqual((row["plan"], row["paused_until"], row["save_offer_used_at"]), ("pro", None, None))
            self.assertFalse(plans.access(row)["paused"])
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM nudges").fetchone()[0], 0)
            conn.close()


if __name__ == "__main__":
    unittest.main()
