"""Paid plans: the free trial, Pro and Plus per location, read-only without a
plan, the Kitchen Safety Bundle's included Pro from signed CyberLogix
reports, and the old Academy plan.

Every price on every page comes from plans.py; checkout bills the location
count; Stripe's webhook moves the plan and ignores replayed and late events;
a workspace without a plan can read, download and delete everything but
save nothing; and only a validly signed CyberLogix report counts toward the
bundle."""

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
from datetime import datetime, timedelta, timezone
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_cyberlogix import COLD, RESTO, URL, BundleCase  # noqa: E402
from test_webapp import AppTestCase  # noqa: E402

from omniarmor_app import academy, academy_plan, connections, plans  # noqa: E402
from omniarmor_app import db as dbmod  # noqa: E402
from omniarmor_app.db import connect, iso, migrate, utcnow  # noqa: E402
from omniarmor_app.reminders import run_clock_alerts, run_reminders  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATES = os.path.join(ROOT, "omniarmor_app", "templates")
EXPIRED = "2000-01-01T00:00:00+00:00"
WEBHOOK_SECRET = "whsec_plans_test"
BUNDLE_SECRET = "kitchen-bundle-test-secret"
PRICES = {"PRO_STRIPE_PRICE": "price_pro", "PLUS_STRIPE_PRICE": "price_plus",
          "PLUS_BUNDLE_UPGRADE_STRIPE_PRICE": "price_plus_bundle"}
YEARLY_PRICES = {"PRO_YEARLY_STRIPE_PRICE": "price_pro_year", "PLUS_YEARLY_STRIPE_PRICE": "price_plus_year",
                 "PLUS_BUNDLE_UPGRADE_YEARLY_STRIPE_PRICE": "price_plus_bundle_year"}


def words(page):
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", page)).split())


class PlanCase(AppTestCase):
    def setUp(self):
        super().setUp()
        self.signup(industries=(RESTO, 1))
        with closing(self.db()) as conn:
            self.org_id = conn.execute("SELECT id FROM orgs").fetchone()[0]

    def set_org(self, **fields):
        with closing(self.db()) as conn:
            conn.execute(f"UPDATE orgs SET {', '.join(f'{k} = ?' for k in fields)} WHERE id = ?",
                         (*fields.values(), self.org_id))
            conn.commit()

    def org(self):
        with closing(self.db()) as conn:
            return conn.execute("SELECT * FROM orgs WHERE id = ?", (self.org_id,)).fetchone()

    def end_trial(self):
        self.set_org(academy_trial_ends=EXPIRED)

    def page(self, path):
        # The public pages as a visitor sees them (a signed-in person is sent from / to HQ).
        client = self.client if path.startswith("/app") else self.app.test_client()
        response = client.get(path)
        self.assertEqual(response.status_code, 200, path)
        return response.get_data(as_text=True)

    def item(self, key=COLD):
        with closing(self.db()) as conn:
            return conn.execute("SELECT * FROM items WHERE org_id = ? AND rule_key = ?", (self.org_id, key)).fetchone()


# --- Prices: one place, every page -------------------------------------------------

class TestPricesComeFromTheCode(PlanCase):
    PAGES = ["/", "/help", "/terms", "/industries/restoarmor", "/app/plan", "/app/settings"]

    def test_every_page_shows_the_plans_from_plans_py(self):
        for path in self.PAGES:
            text = words(self.page(path))
            self.assertIn(plans.PRO.price, text, path)
            self.assertIn(plans.PLUS.price, text, path)

    def test_changed_prices_change_every_page(self):
        pro = plans.Plan("pro", "Pro", 55, "PRO_STRIPE_PRICE", True, False)
        plus = plans.Plan("plus", "Plus", 95, "PLUS_STRIPE_PRICE", True, True)
        with mock.patch.object(plans, "PRO", pro), mock.patch.object(plans, "PLUS", plus), \
                mock.patch.object(plans, "BUNDLE_INCLUDES", pro):
            for path in self.PAGES:
                text = words(self.page(path))
                self.assertIn("$55 a month per location", text, path)
                self.assertIn("$95 a month per location", text, path)
                self.assertNotIn("$50 a month", text, path)
                self.assertNotIn("$80 a month", text, path)
            self.assertIn("$40 a month per location", words(self.page("/help")), "the bundle's difference")

    def test_the_bundle_difference_is_plus_minus_pro(self):
        self.assertEqual(plans.bundle_upgrade_dollars(), plans.PLUS.dollars - plans.PRO.dollars)
        self.assertEqual((plans.PRO.dollars, plans.PLUS.dollars, plans.BUNDLE_DOLLARS), (50, 80, 29))
        self.assertEqual(plans.PRO.price, "$50 a month per location")

    def test_no_template_types_a_price(self):
        for folder, _, files in os.walk(TEMPLATES):
            for name in files:
                with open(os.path.join(folder, name), encoding="utf-8") as f:
                    source = f.read()
                found = re.search(r".{0,30}\$\s*\d.{0,30}", source)
                self.assertIsNone(found, f"{name}: {found and found.group(0)}")

    def test_the_plan_pages_type_no_number(self):
        for name in ("app/plan.html", "app/_plan_status.html", "_plan_summary.html"):
            with open(os.path.join(TEMPLATES, name), encoding="utf-8") as f:
                source = f.read()
            text = re.sub(r"\{\{.*?\}\}|\{%.*?%\}|\{#.*?#\}", "", source, flags=re.S)
            text = re.sub(r"<[^>]*>", " ", text)
            found = re.search(r".{0,30}\d.{0,30}", text)
            self.assertIsNone(found, f"{name}: {found and found.group(0)}")

    def test_a_location_is_a_workspace(self):
        self.assertEqual(plans.location_count(self.org()), 1)
        self.assertIn("A location is one workspace", words(self.page("/help")))


# --- Checkout, the webhook, the portal ------------------------------------------------

class StripeCase(PlanCase):
    def setUp(self):
        super().setUp()
        self.app.config.update(STRIPE_SECRET_KEY="sk_test_plans", STRIPE_WEBHOOK_SECRET=WEBHOOK_SECRET, **PRICES)
        self.calls = []
        patcher = mock.patch.object(academy_plan, "_stripe", side_effect=self.fake_stripe)
        patcher.start()
        self.addCleanup(patcher.stop)

    def fake_stripe(self, cfg, path, fields, method="POST"):
        self.calls.append((method, path, dict(fields)))
        if path == "checkout/sessions":
            return {"id": "cs_test_1", "url": "https://checkout.stripe.test/c/pay/cs_test_1"}
        if path == "billing_portal/sessions":
            return {"url": f"https://billing.stripe.test/p/{fields['customer']}"}
        raise AssertionError(path)

    def checkout(self, plan):
        return self.post("/app/plan/checkout", {"plan": plan})

    def webhook(self, event):
        payload = json.dumps(event).encode()
        stamp = int(time.time())
        sig = hmac.new(WEBHOOK_SECRET.encode(), f"{stamp}.".encode() + payload, hashlib.sha256).hexdigest()
        response = self.app.test_client().post("/billing/stripe/webhook", data=payload,
                                               headers={"Stripe-Signature": f"t={stamp},v1={sig}"})
        self.assertEqual(response.status_code, 200)

    def event(self, event_id, kind, obj, created):
        return {"id": event_id, "type": kind, "created": created, "data": {"object": obj}}

    def subscription(self, price, status="active", sub="sub_1"):
        return {"id": sub, "object": "subscription", "customer": "cus_1", "status": status,
                "created": int(time.time()), "current_period_end": int(time.time()) + 30 * 86400,
                "metadata": {"org_id": str(self.org_id)},
                "items": {"data": [{"price": {"id": price}, "quantity": 1}]}}


class TestCheckout(StripeCase):
    def test_pro_and_plus_bill_the_location_count(self):
        for plan, price in (("pro", "price_pro"), ("plus", "price_plus")):
            self.calls.clear()
            response = self.checkout(plan)
            self.assertEqual(response.status_code, 303)
            self.assertEqual(response.headers["Location"], "https://checkout.stripe.test/c/pay/cs_test_1")
            [(method, path, fields)] = self.calls
            self.assertEqual((method, path), ("POST", "checkout/sessions"))
            self.assertEqual(fields["line_items[0][price]"], price)
            self.assertEqual(fields["line_items[0][quantity]"], str(plans.location_count(self.org())))
            self.assertEqual(fields["metadata[plan]"], plan)
            self.assertEqual(fields["subscription_data[metadata][plan]"], plan)
            self.assertEqual(fields["client_reference_id"], str(self.org_id))

    def test_the_quantity_follows_location_count(self):
        with mock.patch.object(plans, "location_count", return_value=3):
            self.checkout("plus")
        self.assertEqual(self.calls[-1][2]["line_items[0][quantity]"], "3")

    def test_the_plan_page_offers_both_and_a_second_subscription_is_refused(self):
        page = self.page("/app/plan")
        self.assertIn('value="pro"', page)
        self.assertIn('value="plus"', page)
        self.set_org(academy_status="active", plan="pro", stripe_customer_id="cus_1", stripe_subscription_id="sub_1")
        response = self.checkout("plus")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.calls, [])
        self.assertIn("Use Manage billing to change it", words(self.page("/app/plan")))
        self.assertIn("Manage billing", self.page("/app/plan"))

    def test_an_unknown_plan_or_a_missing_price_is_refused(self):
        self.assertEqual(self.checkout("gold").status_code, 302)
        self.app.config["PRO_STRIPE_PRICE"] = ""
        self.checkout("pro")
        self.assertEqual(self.calls, [])
        self.assertIn("Online sign-up is coming soon. Contact us to start Pro.", words(self.page("/app/plan")))

    def test_only_the_owner_checks_out(self):
        self.post("/app/settings/invite")
        with closing(self.db()) as conn:
            conn.execute("INSERT INTO users (email, name, password_hash, created_at) VALUES ('m@example.com', 'M', 'x', ?)",
                         (iso(utcnow()),))
            uid = conn.execute("SELECT id FROM users WHERE email = 'm@example.com'").fetchone()[0]
            conn.execute("INSERT INTO memberships VALUES (?, ?, 'member', ?)", (uid, self.org_id, iso(utcnow())))
            conn.commit()
        member = self.app.test_client()
        with member.session_transaction() as s:
            s["user_id"] = uid
        anon = self.app.test_client()
        self.assertTrue(self.post("/app/plan/checkout", {"plan": "pro"}, client=anon).headers["Location"]
                        .startswith("/login"))
        self.assertEqual(self.calls, [])

    def test_old_plan_address_redirects(self):
        response = self.client.get("/app/academy/plan?welcome=1")
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.headers["Location"].startswith("/app/plan"))


class TestTheWebhook(StripeCase):
    def test_checkout_then_a_portal_switch_moves_the_plan(self):
        base = int(time.time())
        session = {"id": "cs_1", "object": "checkout.session", "customer": "cus_1", "subscription": "sub_1",
                   "client_reference_id": str(self.org_id),
                   "metadata": {"org_id": str(self.org_id), "plan": "pro"}}
        self.webhook(self.event("evt_1", "checkout.session.completed", session, base))
        org = self.org()
        self.assertEqual((org["plan"], org["academy_status"]), ("pro", "active"))
        self.assertTrue(plans.access(org)["tracker"])
        # Switched to Plus in Stripe's portal: the price says so.
        self.webhook(self.event("evt_2", "customer.subscription.updated", self.subscription("price_plus"), base + 10))
        self.assertEqual(self.org()["plan"], "plus")
        # A replay of the old event, and a late one about the earlier price, change nothing.
        self.webhook(self.event("evt_1", "checkout.session.completed", session, base))
        self.webhook(self.event("evt_0", "customer.subscription.updated", self.subscription("price_pro"), base + 5))
        self.assertEqual(self.org()["plan"], "plus")
        self.webhook(self.event("evt_2", "customer.subscription.updated", self.subscription("price_pro"), base + 10))
        self.assertEqual(self.org()["plan"], "plus", "a replayed event id is ignored")
        # Cancelled: the plan ends and the trial is long over, so read-only.
        self.end_trial()
        self.webhook(self.event("evt_3", "customer.subscription.deleted",
                                self.subscription("price_plus", status="canceled"), base + 20))
        org = self.org()
        self.assertEqual(org["academy_status"], "canceled")
        self.assertEqual(plans.access(org)["reason"], "plan_ended")
        self.assertTrue(plans.access(org)["read_only"])
        # A late renewal of the ended subscription doesn't bring it back.
        self.webhook(self.event("evt_4", "customer.subscription.updated", self.subscription("price_plus"), base + 15))
        self.assertEqual(self.org()["academy_status"], "canceled")

    def test_past_due_keeps_access_until_stripe_gives_up(self):
        base = int(time.time())
        self.end_trial()
        self.webhook(self.event("evt_1", "customer.subscription.created", self.subscription("price_pro"), base))
        self.webhook(self.event("evt_2", "invoice.payment_failed",
                                {"id": "in_1", "customer": "cus_1", "subscription": "sub_1",
                                 "metadata": {"org_id": str(self.org_id)}}, base + 1))
        org = self.org()
        self.assertEqual((org["plan"], org["academy_status"]), ("pro", "past_due"))
        self.assertTrue(plans.access(org)["tracker"])
        self.assertIn("didn't go through", words(self.page("/app/settings")))

    def test_an_unknown_price_keeps_the_plan(self):
        self.set_org(plan="academy", academy_status="active", stripe_customer_id="cus_1", stripe_subscription_id="sub_1")
        old = self.subscription("price_old_academy")
        old["metadata"] = {"org_id": str(self.org_id)}
        self.webhook(self.event("evt_1", "customer.subscription.updated", old, int(time.time())))
        self.assertEqual(self.org()["plan"], "academy")

    def test_coming_back_from_checkout_settles_the_plan(self):
        session = {"id": "cs_test_9", "object": "checkout.session", "mode": "subscription", "status": "complete",
                   "payment_status": "paid", "customer": "cus_9", "subscription": "sub_9",
                   "client_reference_id": str(self.org_id), "created": int(time.time()),
                   "metadata": {"org_id": str(self.org_id), "plan": "plus"}}
        with mock.patch.object(academy_plan, "_stripe", return_value=session):
            response = self.client.get("/app/plan?welcome=1&session_id=cs_test_9", follow_redirects=True)
        self.assertIn("Thank you! Plus is on for Acme Logistics.", words(response.get_data(as_text=True)))
        self.assertEqual((self.org()["plan"], self.org()["academy_status"]), ("plus", "active"))


# --- Without a plan: read-only, and nothing held back ----------------------------------

class TestReadOnlyAfterTheTrial(PlanCase):
    def setUp(self):
        super().setUp()
        self.change(RESTO, COLD, value="38")
        self.end_trial()

    def test_new_workspaces_start_a_trial_from_sign_up(self):
        with closing(self.db()) as conn:
            conn.execute("UPDATE orgs SET academy_trial_ends = NULL")
            conn.commit()
        org = self.org()
        self.assertTrue(plans.access(org)["trial"], "a workspace made without one gets its creation + the length")
        other = self.app.test_client()
        self.signup(email="second@example.com", client=other)
        with closing(self.db()) as conn:
            ends = conn.execute("SELECT academy_trial_ends FROM orgs WHERE id != ?", (self.org_id,)).fetchone()[0]
        days = (datetime.fromisoformat(ends) - datetime.now(timezone.utc)).total_seconds() / 86400
        self.assertAlmostEqual(days, self.app.config["ACADEMY_TRIAL_DAYS"], delta=0.01)

    def test_saving_is_refused_and_nothing_changes(self):
        response = self.post(f"/app/industry/{RESTO}/rule/{COLD}", {"action": "save", "value": "45"},
                             follow_redirects=True)
        text = words(response.get_data(as_text=True))
        self.assertIn("Your free trial has ended, so the compliance tracker is read-only. Nothing was saved.", text)
        self.assertEqual(self.item()["value_num"], 38)
        for action in ("done_today", "clear", "override"):
            self.change(RESTO, COLD, action=action, limit="40")
        self.assertEqual(self.item()["value_num"], 38)
        self.assertIsNone(self.item()["limit_override"])
        rule = next(r for r in __import__("omniarmor_app.catalog", fromlist=["rules_for"]).rules_for(1)
                    if r.kind in ("required", "forbidden"))
        self.post("/app/industry/1/bulk", {"bulk_action": "yes", "keys": [rule.key]})
        self.assertIsNone(self.item(rule.key))
        with closing(self.db()) as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM audit WHERE action = 'reading'").fetchone()[0], 1)

    def test_the_pages_say_read_only_and_offer_no_save(self):
        page = self.page(f"/app/industry/{RESTO}")
        self.assertIn("data-readonly-banner", page)
        self.assertIn("Reminders are paused".lower(), words(page).lower().replace("reminders are paused", "reminders are paused"))
        self.assertNotIn('value="save"', page)
        self.assertNotIn('id="bulk"', page)
        self.assertIn("data-read-only", page)
        self.assertIn("Your records are safe", words(page))
        self.assertIn("data-readonly-banner", self.page("/app"))
        self.assertIn("No plan: the compliance tracker is read-only and reminders are paused",
                      words(self.page("/app/settings")))

    def test_records_can_be_seen_downloaded_and_deleted(self):
        self.assertIn("38", words(self.page("/app/report")))
        report = self.client.get("/app/report.csv")
        self.assertEqual(report.status_code, 200)
        self.assertIn("38", report.get_data(as_text=True))
        audit = self.client.get("/app/audit.csv")
        self.assertEqual(audit.status_code, 200)
        self.assertIn("Cold holding", audit.get_data(as_text=True))
        self.page("/app/audit")
        self.page("/app/notifications")
        response = self.post("/app/settings/delete", {"confirm": "Acme Logistics"})
        self.assertEqual(response.status_code, 302)
        with closing(self.db()) as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM orgs").fetchone()[0], 0)

    def test_nothing_is_deleted_when_the_trial_ends(self):
        with closing(self.db()) as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM items").fetchone()[0], 1)

    def test_reminders_pause_and_pick_up_with_a_plan(self):
        rule = next(r for r in __import__("omniarmor_app.catalog", fromlist=["rules_for"]).rules_for(1)
                    if r.input.startswith("Days since") and not r.unit.startswith("hour"))
        with closing(self.db()) as conn:
            conn.execute("INSERT INTO items (org_id, industry_id, rule_key, value_date, updated_at) VALUES (?, 1, ?, ?, ?)",
                         (self.org_id, rule.key, "2000-01-01", iso(utcnow())))
            conn.commit()
            summary = run_reminders(conn, self.app.config)
            self.assertEqual((summary["paused"], summary["digests"]), (1, 0))
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM notifications WHERE kind = 'reminder'").fetchone()[0], 0)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM reminder_marks").fetchone()[0], 0)
            self.assertEqual(run_clock_alerts(conn, self.app.config)["alerts"], 0)
        self.set_org(academy_status="active", plan="pro")
        with closing(self.db()) as conn:
            summary = run_reminders(conn, self.app.config)
        self.assertEqual((summary["paused"], summary["digests"]), (0, 1))

    def test_the_academy_keeps_its_free_worlds(self):
        self.post("/app/academy/learners", {"nickname": "Sam", "avatar": "rocket", "track": "launchpad"})
        with closing(self.db()) as conn:
            lid = conn.execute("SELECT id FROM learners").fetchone()[0]
        self.assertEqual(self.client.get(f"/app/academy/{lid}/world/1").status_code, 200)
        self.assertFalse(plans.access(self.org())["academy"])


# --- Plus unlocks the Academy; Pro doesn't ----------------------------------------------

class TestWhatEachPlanUnlocks(PlanCase):
    def setUp(self):
        super().setUp()
        self.end_trial()
        self.post("/app/academy/learners", {"nickname": "Sam", "avatar": "rocket", "track": "trailblazer"})
        with closing(self.db()) as conn:
            self.lid = conn.execute("SELECT id FROM learners").fetchone()[0]
        self.paid_world = academy.TRACKS["trailblazer"].topics[0]

    def opens(self):
        return self.client.get(f"/app/academy/{self.lid}/world/{self.paid_world}").status_code == 200

    def test_plus_unlocks_the_whole_academy_and_pro_does_not(self):
        self.assertFalse(self.opens())
        self.set_org(academy_status="active", plan="pro")
        self.assertFalse(self.opens())
        self.assertTrue(plans.access(self.org())["tracker"])
        self.assertEqual(self.change(RESTO, COLD, value="39").status_code, 302)
        self.assertEqual(self.item()["value_num"], 39)
        self.set_org(plan="plus")
        self.assertTrue(self.opens())
        self.assertIn("You have Plus", words(self.page("/app/academy")))

    def test_the_trial_unlocks_everything(self):
        self.set_org(academy_trial_ends=iso(utcnow() + timedelta(days=3)))
        self.assertTrue(self.opens())
        self.assertTrue(plans.access(self.org())["tracker"])


# --- The Kitchen Safety Bundle ----------------------------------------------------------

class SignedCase(BundleCase):
    def setUp(self):
        super().setUp()
        self.app.config["KITCHEN_BUNDLE_SECRET"] = BUNDLE_SECRET
        self.key = self.create_key()
        with closing(self.db()) as conn:
            conn.execute("UPDATE orgs SET academy_trial_ends = ?", (EXPIRED,))
            conn.commit()

    def send_signed(self, body=None, stamp=None, secret=BUNDLE_SECRET, header=None):
        raw = json.dumps(self.report() if body is None else body).encode()
        stamp = int(time.time()) if stamp is None else stamp
        if header is None:
            header = connections.sign(secret, raw, stamp)
        return self.client.post(URL, data=raw, content_type="application/json",
                                headers={"Authorization": f"Bearer {self.key}", connections.SIGNATURE_HEADER: header})

    def access(self):
        return plans.access(self.org_row())


class TestTheSignature(SignedCase):
    def test_a_valid_signature_grants_pro(self):
        self.assertTrue(self.access()["read_only"])
        response = self.send_signed()
        self.assertEqual(response.status_code, 200)
        answer = response.get_json()
        self.assertEqual((answer["signature"], answer["bundle_counted"], answer["ticked"]), ("valid", True, 1))
        access = self.access()
        self.assertEqual((access["source"], access["tracker"], access["academy"]), ("bundle", True, False))
        settings = words(self.client.get("/app/settings").get_data(as_text=True))
        self.assertIn("Pro included with your Kitchen Safety Bundle", settings)
        self.assertEqual(self.change(RESTO, COLD, value="37").status_code, 302)
        self.assertEqual(self.item()["value_num"], 37)

    def test_the_signature_is_the_documented_hmac(self):
        raw = b'{"a": 1}'
        expected = hmac.new(BUNDLE_SECRET.encode(), b"1700000000." + raw, hashlib.sha256).hexdigest()
        self.assertEqual(connections.sign(BUNDLE_SECRET, raw, 1700000000), f"t=1700000000,v1={expected}")
        self.assertEqual(connections.check_signature(raw, f"t=1700000000,v1={expected}", BUNDLE_SECRET,
                                                     now=1700000000), ("valid", expected))
        self.assertEqual(connections.check_signature(raw + b" ", f"t=1700000000,v1={expected}", BUNDLE_SECRET,
                                                     now=1700000000)[0], "invalid", "the raw bytes, exactly")

    def assert_processed_without_waiver(self, response, status):
        self.assertEqual(response.status_code, 200, response.data)
        answer = response.get_json()
        self.assertEqual((answer["signature"], answer["bundle_counted"]), (status, False))
        self.assertEqual(answer["matched_checks"], 1)
        self.assertTrue(self.access()["read_only"], "no waiver")
        self.assertIsNone(self.org_row()["bundle_report_at"])

    def test_a_wrong_signature_is_processed_without_the_waiver(self):
        response = self.send_signed(secret="not-the-secret")
        self.assert_processed_without_waiver(response, "invalid")
        self.assertEqual(self.item()["value_num"], 38, "ticked exactly as today")

    def test_a_malformed_header_is_invalid(self):
        for header in ("garbage", "t=abc,v1=00", f"t={int(time.time())}", f"t={int(time.time())},v1=xyz",
                       "t=1,t=2,v1=" + "0" * 64):
            self.assertEqual(connections.check_signature(b"{}", header, BUNDLE_SECRET)[0], "invalid", header)
        self.assert_processed_without_waiver(self.send_signed(header=f"t={int(time.time())},v1=zz"), "invalid")

    def test_a_stale_t_is_refused_either_way(self):
        tolerance = connections.SIGNATURE_TOLERANCE
        self.assert_processed_without_waiver(self.send_signed(stamp=int(time.time()) - tolerance - 5), "stale")
        self.assert_processed_without_waiver(self.send_signed(
            body=self.report(warmest_reading=37), stamp=int(time.time()) + tolerance + 5), "stale")
        self.assertEqual(self.send_signed(body=self.report(warmest_reading=36),
                                          stamp=int(time.time()) - tolerance + 5).get_json()["signature"], "valid")

    def test_a_replay_does_not_count_twice(self):
        raw = json.dumps(self.report()).encode()
        header = connections.sign(BUNDLE_SECRET, raw, int(time.time()))
        send = lambda: self.client.post(URL, data=raw, content_type="application/json",  # noqa: E731
                                        headers={"Authorization": f"Bearer {self.key}",
                                                 connections.SIGNATURE_HEADER: header})
        first = send().get_json()
        self.assertEqual((first["signature"], first["bundle_counted"]), ("valid", True))
        with closing(self.db()) as conn:
            counted_at = conn.execute("SELECT bundle_report_at FROM orgs").fetchone()[0]
            conn.execute("UPDATE orgs SET bundle_report_at = ?", (iso(utcnow() - timedelta(days=2)),))
            conn.commit()
        again = send()
        self.assertEqual(again.status_code, 200)
        self.assertEqual((again.get_json()["signature"], again.get_json()["bundle_counted"]), ("replayed", False))
        self.assertEqual(again.get_json()["unchanged"], 1, "the report itself is processed as today")
        self.assertNotEqual(self.org_row()["bundle_report_at"], counted_at, "a replay doesn't renew the cover")

    def test_a_signature_is_forgotten_after_its_window(self):
        raw = json.dumps(self.report()).encode()
        stamp = int(time.time())
        header = connections.sign(BUNDLE_SECRET, raw, stamp)
        self.send_signed(header=header)
        with closing(self.db()) as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM bundle_signatures").fetchone()[0], 1)
            conn.execute("UPDATE bundle_signatures SET seen_at = ?", (iso(utcnow() - timedelta(minutes=11)),))
            conn.commit()
        # By then the same t is stale anyway, so it still can't count.
        with mock.patch("omniarmor_app.connections.time.time", return_value=stamp + 11 * 60):
            self.assertEqual(self.send_signed(header=header).get_json()["signature"], "stale")
        # The next signature that counts clears the old ones away (and so does the daily clean-up).
        self.assertTrue(self.send_signed(body=self.report(warmest_reading=37)).get_json()["bundle_counted"])
        with closing(self.db()) as conn:
            kept = [r[0] for r in conn.execute("SELECT signature FROM bundle_signatures")]
        self.assertEqual(len(kept), 1)
        self.assertNotIn(header.split("v1=")[1], kept)

    def test_an_unset_secret_counts_nothing(self):
        self.app.config["KITCHEN_BUNDLE_SECRET"] = ""
        self.assert_processed_without_waiver(self.send_signed(), "not_configured")

    def test_an_unsigned_report_is_processed_but_grants_nothing(self):
        response = self.send(self.key)
        self.assert_processed_without_waiver(response, "missing")
        self.assertEqual(self.item()["value_num"], 38)

    def test_a_signed_report_that_fails_validation_counts_nothing(self):
        response = self.send_signed(body=self.report(units_total=0))
        self.assertEqual(response.status_code, 422)
        self.assertIsNone(self.org_row()["bundle_report_at"])

    def test_a_signature_from_one_workspace_cant_be_reused_by_another(self):
        raw = json.dumps(self.report()).encode()
        header = connections.sign(BUNDLE_SECRET, raw, int(time.time()))
        self.send_signed(header=header)
        other = self.app.test_client()
        self.signup(email="other@example.com", industries=(RESTO,), client=other)
        key = re.search(r'class="key mono">(clx_[A-Za-z0-9_-]+)<', self.post(
            "/app/settings/connections/cyberlogix/create", client=other).get_data(as_text=True)).group(1)
        answer = self.client.post(URL, data=raw, content_type="application/json",
                                  headers={"Authorization": f"Bearer {key}",
                                           connections.SIGNATURE_HEADER: header}).get_json()
        self.assertEqual(answer["signature"], "replayed")


class TestTheCoverRunsOut(SignedCase):
    def at(self, days):
        with closing(self.db()) as conn:
            conn.execute("UPDATE orgs SET bundle_report_at = ?", (iso(utcnow() - timedelta(days=days)),))
            conn.commit()
        return self.access()

    def test_covered_then_grace_then_read_only(self):
        self.send_signed()
        fresh, grace = plans.BUNDLE_FRESH.days, plans.BUNDLE_GRACE.days
        self.assertEqual(self.at(fresh - 0.5)["source"], "bundle")
        page = self.client.get("/app").get_data(as_text=True)
        self.assertNotIn("data-grace-banner", page)
        access = self.at(fresh + 0.5)
        self.assertEqual((access["source"], access["tracker"]), ("bundle_grace", True))
        page = self.client.get("/app").get_data(as_text=True)
        self.assertIn("data-grace-banner", page)
        self.assertIn("CyberLogix hasn't sent a signed report since", words(page))
        self.assertNotIn("Pro included with your Kitchen Safety Bundle",
                         words(self.client.get("/app/settings").get_data(as_text=True)))
        self.assertEqual(self.change(RESTO, COLD, value="36").status_code, 302)
        self.assertEqual(self.item()["value_num"], 36, "still Pro during the grace period")
        access = self.at(fresh + grace + 0.5)
        self.assertEqual((access["read_only"], access["reason"]), (True, "bundle_ended"))
        page = self.client.get("/app").get_data(as_text=True)
        self.assertIn("data-readonly-banner", page)
        self.assertIn("CyberLogix stopped sending signed reports", words(page))
        self.change(RESTO, COLD, value="35")
        self.assertEqual(self.item()["value_num"], 36)
        # A new signed report brings it back.
        self.send_signed(body=self.report(warmest_reading=34))
        self.assertEqual(self.access()["source"], "bundle")

    def test_still_in_the_trial_after_the_bundle_lapses(self):
        with closing(self.db()) as conn:
            conn.execute("UPDATE orgs SET academy_trial_ends = ?", (iso(utcnow() + timedelta(days=5)),))
            conn.commit()
        access = self.at(30)
        self.assertEqual((access["source"], access["tracker"]), ("trial", True))


class BundleUpgradeCase(SignedCase):
    def setUp(self):
        super().setUp()
        self.app.config.update(STRIPE_SECRET_KEY="sk_test_plans", **PRICES)
        self.calls = []
        patcher = mock.patch.object(academy_plan, "_stripe", side_effect=self.fake)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.send_signed()

    def fake(self, cfg, path, fields, method="POST"):
        self.calls.append(dict(fields))
        return {"id": "cs_test_1", "url": "https://checkout.stripe.test/c/pay/cs_test_1"}


class TestTheBundleUpgrade(BundleUpgradeCase):
    def test_plus_costs_only_the_difference(self):
        page = words(self.client.get("/app/plan").get_data(as_text=True))
        self.assertIn(f"{plans.price_label(plans.bundle_upgrade_dollars())} with your Kitchen Safety Bundle", page)
        self.assertIn("Add the Academy with Plus", page)
        self.assertNotIn("Choose Pro", page)
        response = self.post("/app/plan/checkout", {"plan": "plus"})
        self.assertEqual(response.status_code, 303)
        fields = self.calls[-1]
        self.assertEqual(fields["line_items[0][price]"], "price_plus_bundle")
        self.assertEqual(fields["line_items[0][quantity]"], "1")
        self.assertEqual(fields["metadata[plan]"], "plus_bundle")

    def test_pro_is_not_sold_to_a_covered_workspace(self):
        self.post("/app/plan/checkout", {"plan": "pro"})
        self.assertEqual(self.calls, [])

    def test_without_the_upgrade_price_plus_is_full_price_with_a_note(self):
        self.app.config["PLUS_BUNDLE_UPGRADE_STRIPE_PRICE"] = ""
        page = self.client.get("/app/plan").get_data(as_text=True)
        self.assertIn("data-bundle-full-price", page)
        self.post("/app/plan/checkout", {"plan": "plus"})
        self.assertEqual((self.calls[-1]["line_items[0][price]"], self.calls[-1]["metadata[plan]"]),
                         ("price_plus", "plus"))

    def test_the_upgrade_gives_the_academy_and_the_bundle_the_tracker(self):
        with closing(self.db()) as conn:
            conn.execute("UPDATE orgs SET plan = 'plus_bundle', academy_status = 'active'")
            conn.commit()
        access = self.access()
        self.assertEqual((access["academy"], access["tracker"], access["source"]), (True, True, "bundle"))
        settings = words(self.client.get("/app/settings").get_data(as_text=True))
        self.assertIn("Pro included with your Kitchen Safety Bundle", settings)
        self.assertIn("You're on Plus at the Kitchen Safety Bundle price", settings)
        with closing(self.db()) as conn:
            conn.execute("UPDATE orgs SET bundle_report_at = ?", (iso(utcnow() - timedelta(days=30)),))
            conn.commit()
        access = self.access()
        self.assertEqual((access["academy"], access["tracker"], access["reason"]), (True, False, "bundle_ended"))
        self.assertIn("data-bundle-ended", self.client.get("/app/plan").get_data(as_text=True))


# --- Monthly or yearly: pay for ten months, get twelve -----------------------------------

def card(page, key):
    """One plan's card on the plan page."""
    return re.search(rf'<section class="plan-card[^"]*" data-plan="{key}">(.*?)</section>', page, re.S).group(1)


class YearlyCase(StripeCase):
    def setUp(self):
        super().setUp()
        self.app.config.update(**YEARLY_PRICES)
        self.end_trial()


class TestYearlyPrices(YearlyCase):
    PAGES = TestPricesComeFromTheCode.PAGES

    def test_a_year_costs_ten_months(self):
        self.assertEqual((plans.MONTHS_PAID_YEARLY, plans.MONTHS_IN_YEAR, plans.free_months()), (10, 12, 2))
        for plan in (plans.PRO, plans.PLUS):
            self.assertEqual(plan.yearly_dollars, 10 * plan.dollars, plan.name)
        self.assertEqual(plans.bundle_upgrade_dollars(plans.YEAR), 10 * plans.bundle_upgrade_dollars())
        self.assertEqual((plans.PRO.yearly_dollars, plans.PLUS.yearly_dollars, plans.bundle_upgrade_dollars(plans.YEAR)),
                         (500, 800, 300))
        self.assertEqual(plans.PRO.yearly_price, "$500 a year per location")
        self.assertEqual(plans.PLUS.yearly_price, "$800 a year per location")
        self.assertEqual(plans.free_label(), "2 months free")

    def test_every_page_shows_the_yearly_prices_from_plans_py(self):
        for path in self.PAGES:
            text = words(self.page(path))
            self.assertIn(plans.PRO.yearly_short, text, path)
            self.assertIn(plans.PLUS.yearly_short, text, path)
            self.assertIn(plans.free_label(), text, path)
            self.assertIn(plans.PRO.price, text, path)
        for path in ("/", "/industries/restoarmor", "/app/plan"):
            self.assertIn("data-billing-toggle", self.page(path), path)
        self.assertIn("$300 a year", words(self.page("/help")), "the bundle's difference, yearly")
        self.assertIn("$300 a year", words(self.page("/")))

    def test_changed_prices_change_the_yearly_prices(self):
        pro = plans.Plan("pro", "Pro", 55, "PRO_STRIPE_PRICE", True, False, "PRO_YEARLY_STRIPE_PRICE")
        plus = plans.Plan("plus", "Plus", 95, "PLUS_STRIPE_PRICE", True, True, "PLUS_YEARLY_STRIPE_PRICE")
        with mock.patch.object(plans, "PRO", pro), mock.patch.object(plans, "PLUS", plus), \
                mock.patch.object(plans, "BUNDLE_INCLUDES", pro), mock.patch.object(plans, "MONTHS_PAID_YEARLY", 11):
            for path in self.PAGES:
                text = words(self.page(path))
                self.assertIn("$605 a year", text, path)
                self.assertIn("$1,045 a year", text, path)
                self.assertIn("1 month free", text, path)
                self.assertNotIn("$500 a year", text, path)
                self.assertNotIn("2 months free", text, path)
            self.assertIn("$440 a year", words(self.page("/help")), "the bundle's difference")

    def test_an_empty_yearly_setting_hides_that_option(self):
        self.app.config["PRO_YEARLY_STRIPE_PRICE"] = ""
        page = self.page("/app/plan")
        self.assertIn("data-billing-toggle", page)
        pro, plus = card(page, "pro"), card(page, "plus")
        self.assertNotIn("data-price-yearly", pro)
        self.assertNotIn('name="interval" value="year"', pro)
        self.assertIn("Billed monthly only for now.", words(pro))
        self.assertIn('name="interval" value="month"', pro)
        self.assertIn('name="interval" value="year"', plus)
        for path in self.PAGES:
            text = words(self.page(path))
            self.assertNotIn(plans.PRO.yearly_short, text, path)
            self.assertIn(plans.PLUS.yearly_short, text, path)
        response = self.post("/app/plan/checkout", {"plan": "pro", "interval": "year"}, follow_redirects=True)
        self.assertIn("Pro can't be paid yearly yet. Choose monthly instead.", words(response.get_data(as_text=True)))
        self.assertEqual(self.calls, [])
        # None set: no toggle, no yearly price anywhere, and monthly works as before.
        self.app.config.update({name: "" for name in YEARLY_PRICES})
        for path in self.PAGES:
            page = self.page(path)
            self.assertNotIn("data-billing-toggle", page, path)
            self.assertNotIn("a year per location", words(page), path)
            self.assertNotIn(plans.free_label(), words(page), path)
        self.assertNotIn('value="year"', self.page("/app/plan"))
        self.assertEqual(self.post("/app/plan/checkout", {"plan": "pro"}).status_code, 303)
        self.assertEqual(self.calls[-1][2]["line_items[0][price]"], "price_pro")


class TestYearlyCheckout(YearlyCase):
    def test_yearly_uses_the_yearly_price_and_the_location_count(self):
        for plan, price in (("pro", "price_pro_year"), ("plus", "price_plus_year")):
            self.calls.clear()
            response = self.post("/app/plan/checkout", {"plan": plan, "interval": "year"})
            self.assertEqual(response.status_code, 303)
            [(method, path, fields)] = self.calls
            self.assertEqual((method, path), ("POST", "checkout/sessions"))
            self.assertEqual(fields["line_items[0][price]"], price)
            self.assertEqual(fields["line_items[0][quantity]"], str(plans.location_count(self.org())))
            self.assertEqual((fields["metadata[plan]"], fields["metadata[interval]"]), (plan, "year"))
            self.assertEqual((fields["subscription_data[metadata][plan]"],
                              fields["subscription_data[metadata][interval]"]), (plan, "year"))
        with mock.patch.object(plans, "location_count", return_value=4):
            self.post("/app/plan/checkout", {"plan": "plus", "interval": "year"})
        self.assertEqual(self.calls[-1][2]["line_items[0][quantity]"], "4")

    def test_monthly_is_the_default_and_an_unknown_interval_is_refused(self):
        self.post("/app/plan/checkout", {"plan": "pro"})
        self.assertEqual((self.calls[-1][2]["line_items[0][price]"], self.calls[-1][2]["metadata[interval]"]),
                         ("price_pro", "month"))
        self.post("/app/plan/checkout", {"plan": "plus", "interval": "month"})
        self.assertEqual(self.calls[-1][2]["line_items[0][price]"], "price_plus")
        self.calls.clear()
        self.assertEqual(self.post("/app/plan/checkout", {"plan": "pro", "interval": "week"}).status_code, 302)
        self.assertEqual(self.calls, [])

    def test_the_plan_page_offers_monthly_and_yearly(self):
        page = self.page("/app/plan")
        self.assertEqual(page.count('name="interval" value="year"'), 2)
        self.assertEqual(page.count('name="interval" value="month"'), 2)
        self.assertRegex(page, r'id="billing-month" value="monthly" checked>')
        text = words(page)
        self.assertIn(f"{plans.PLUS.yearly_price} {plans.free_label()}", text)
        self.assertIn("Choose Plus yearly", text)
        self.assertIn("Yearly: pay for 10 months and get 12", text)
        self.assertIn("with no refund for the part of the year left", text)
        self.assertRegex(self.page("/app/plan?billing=yearly"), r'id="billing-year" value="yearly" checked>')
        self.assertIn("see yearly prices", words(self.page("/app/settings")))


class TestYearlyWebhook(YearlyCase):
    def test_each_price_says_its_plan_and_interval(self):
        cfg = self.app.config
        for price, expected in (("price_pro", ("pro", "month")), ("price_pro_year", ("pro", "year")),
                                ("price_plus", ("plus", "month")), ("price_plus_year", ("plus", "year")),
                                ("price_plus_bundle", ("plus_bundle", "month")),
                                ("price_plus_bundle_year", ("plus_bundle", "year"))):
            self.assertEqual(academy_plan.plan_for(cfg, self.subscription(price)), expected, price)
        # A price that isn't one of ours: its own recurring interval, and the plan from the metadata.
        other = self.subscription("price_someone_else")
        other["items"]["data"][0]["price"]["recurring"] = {"interval": "year"}
        self.assertEqual(academy_plan.plan_for(cfg, other), (None, "year"))
        session = {"metadata": {"plan": "plus", "interval": "year"}}
        self.assertEqual(academy_plan.plan_for(cfg, session), ("plus", "year"))
        self.assertEqual(academy_plan.plan_for(cfg, {"metadata": {"interval": "fortnight"}}), (None, None))

    def yearly_subscription(self, price, **extra):
        sub = self.subscription(price)
        sub["current_period_end"] = int(time.time()) + 365 * 86400
        sub.update(extra)
        return sub

    def test_checkout_yearly_then_switches_in_the_portal(self):
        base = int(time.time())
        session = {"id": "cs_1", "object": "checkout.session", "customer": "cus_1", "subscription": "sub_1",
                   "client_reference_id": str(self.org_id),
                   "metadata": {"org_id": str(self.org_id), "plan": "plus", "interval": "year"}}
        self.webhook(self.event("evt_1", "checkout.session.completed", session, base))
        org = self.org()
        self.assertEqual((org["plan"], org["plan_interval"], org["academy_status"]), ("plus", "year", "active"))
        self.webhook(self.event("evt_2", "customer.subscription.created", self.yearly_subscription("price_plus_year"),
                                base + 1))
        access = plans.access(self.org())
        self.assertEqual((access["tracker"], access["academy"], access["yearly"]), (True, True, True))
        self.assertIn("You're on Plus, billed yearly, renews", words(self.page("/app/settings")))
        self.assertRegex(self.page("/app/plan"), r'id="billing-year" value="yearly" checked>')
        # The portal: yearly to monthly, then to Pro yearly.
        self.webhook(self.event("evt_3", "customer.subscription.updated", self.subscription("price_plus"), base + 10))
        self.assertEqual((self.org()["plan"], self.org()["plan_interval"]), ("plus", "month"))
        settings = words(self.page("/app/settings"))
        self.assertIn("You're on Plus, renews", settings)
        self.assertNotIn("billed yearly", settings)
        self.webhook(self.event("evt_4", "customer.subscription.updated", self.yearly_subscription("price_pro_year"),
                                base + 20))
        self.assertEqual((self.org()["plan"], self.org()["plan_interval"]), ("pro", "year"))
        # A late event about the monthly price changes nothing.
        self.webhook(self.event("evt_5", "customer.subscription.updated", self.subscription("price_plus"), base + 15))
        self.assertEqual((self.org()["plan"], self.org()["plan_interval"]), ("pro", "year"))
        # Manage billing opens the portal, where the switch happens.
        page = self.page("/app/plan")
        self.assertIn("switch between monthly and yearly", page)
        self.assertEqual(self.post("/app/plan/manage").headers["Location"], "https://billing.stripe.test/p/cus_1")

    def test_a_cancelled_yearly_plan_runs_to_the_end_of_the_paid_year(self):
        base = int(time.time())
        year_end = base + 300 * 86400
        self.webhook(self.event("evt_1", "customer.subscription.updated",
                                self.yearly_subscription("price_plus_year", cancel_at_period_end=True,
                                                         current_period_end=year_end), base))
        org = self.org()
        access = plans.access(org)
        self.assertEqual((access["paid"], access["tracker"], access["academy"], access["yearly"]), (True, True, True, True))
        self.assertEqual(datetime.fromisoformat(org["academy_ends_at"]).timestamp(), year_end)
        self.assertEqual(self.change(RESTO, COLD, value="39").status_code, 302)
        self.assertEqual(self.item()["value_num"], 39, "still on until the end of the year")
        settings = words(self.page("/app/settings"))
        self.assertIn("Plus, paid yearly, is cancelled and ends", settings)
        self.assertIn("A yearly plan isn't refunded for the part of the year left", settings)
        # At the end of the year Stripe deletes it: read-only, records kept.
        self.webhook(self.event("evt_2", "customer.subscription.deleted",
                                self.yearly_subscription("price_plus_year", status="canceled"), base + 10))
        access = plans.access(self.org())
        self.assertEqual((access["read_only"], access["reason"]), (True, "plan_ended"))
        self.change(RESTO, COLD, value="40")
        self.assertEqual(self.item()["value_num"], 39)

    def test_the_help_page_says_the_cancellation_rule(self):
        text = words(self.page("/help"))
        self.assertIn("A yearly plan stays on until the end of the year you paid for, and is not charged again. "
                      "There is no partial refund for the months left in that year.", text)
        self.assertIn("A monthly plan stays on until the end of the month you paid for", text)
        self.assertIn("When the plan ends , nothing is deleted: you can still see, print and download every record", text)
        self.assertIn("Paying yearly costs 10 months' price for 12 months of service: 2 months free.", text)

    def test_the_plan_command_sets_yearly(self):
        result = self.app.test_cli_runner().invoke(args=["plan", str(self.org_id), "plus", "--yearly"])
        self.assertIn("Plus on, yearly.", result.output)
        self.assertEqual((self.org()["plan"], self.org()["plan_interval"]), ("plus", "year"))
        self.app.test_cli_runner().invoke(args=["plan", str(self.org_id), "pro"])
        self.assertEqual((self.org()["plan"], self.org()["plan_interval"]), ("pro", "month"))


class TestTheYearlyBundleUpgrade(BundleUpgradeCase):
    def setUp(self):
        super().setUp()
        self.app.config.update(**YEARLY_PRICES)

    def test_plus_yearly_costs_ten_months_of_the_difference(self):
        page = self.client.get("/app/plan").get_data(as_text=True)
        plus = words(card(page, "plus"))
        self.assertIn(f"{plans.price_label(plans.bundle_upgrade_dollars(plans.YEAR), plans.YEAR)} with your "
                      f"Kitchen Safety Bundle ({plans.PLUS.yearly_price} without)", plus)
        self.assertIn("Add the Academy with Plus yearly", plus)
        response = self.post("/app/plan/checkout", {"plan": "plus", "interval": "year"})
        self.assertEqual(response.status_code, 303)
        fields = self.calls[-1]
        self.assertEqual((fields["line_items[0][price]"], fields["line_items[0][quantity]"], fields["metadata[plan]"],
                          fields["metadata[interval]"]), ("price_plus_bundle_year", "1", "plus_bundle", "year"))
        self.assertEqual(academy_plan.plan_for(self.app.config, {"items": {"data": [
            {"price": {"id": "price_plus_bundle_year"}}]}}), ("plus_bundle", "year"))
        self.post("/app/plan/checkout", {"plan": "pro", "interval": "year"})
        self.assertEqual(len(self.calls), 1, "Pro is already included, yearly too")

    def test_without_the_yearly_upgrade_price_yearly_plus_is_full_price(self):
        self.app.config["PLUS_BUNDLE_UPGRADE_YEARLY_STRIPE_PRICE"] = ""
        page = self.client.get("/app/plan").get_data(as_text=True)
        self.assertIn("isn't set up for yearly billing, so it is billed at its full price", words(page))
        self.post("/app/plan/checkout", {"plan": "plus", "interval": "year"})
        self.assertEqual((self.calls[-1]["line_items[0][price]"], self.calls[-1]["metadata[plan]"]),
                         ("price_plus_year", "plus"))
        self.post("/app/plan/checkout", {"plan": "plus", "interval": "month"})
        self.assertEqual(self.calls[-1]["line_items[0][price]"], "price_plus_bundle", "monthly keeps the difference")

    def test_a_yearly_bundle_plus_says_so(self):
        with closing(self.db()) as conn:
            conn.execute("UPDATE orgs SET plan = 'plus_bundle', plan_interval = 'year', academy_status = 'active'")
            conn.commit()
        settings = words(self.client.get("/app/settings").get_data(as_text=True))
        self.assertIn("You're on Plus at the Kitchen Safety Bundle price, billed yearly", settings)


# --- The old Academy plan ---------------------------------------------------------------

class TestTheOldAcademyPlan(PlanCase):
    def test_a_paying_workspace_keeps_the_academy_and_the_tracker(self):
        self.end_trial()
        self.set_org(academy_status="active", plan="academy", academy_renews_at=iso(utcnow() + timedelta(days=9)))
        access = plans.access(self.org())
        self.assertEqual((access["tracker"], access["academy"], access["legacy"]), (True, True, True))
        self.assertIn("You're on the Academy plan from before Pro and Plus", words(self.page("/app/settings")))
        self.assertEqual(self.change(RESTO, COLD, value="39").status_code, 302)
        self.assertEqual(self.item()["value_num"], 39)

    def test_once_it_ends_the_usual_rules_apply(self):
        self.end_trial()
        self.set_org(academy_status="canceled", plan="academy")
        access = plans.access(self.org())
        self.assertEqual((access["tracker"], access["academy"], access["reason"]), (False, False, "plan_ended"))
        self.assertIn("Your plan has ended", words(self.page("/app")))

    def test_the_old_command_puts_a_workspace_on_plus(self):
        result = self.app.test_cli_runner().invoke(args=["academy-plan", str(self.org_id), "active"])
        self.assertIn("Academy plan active (Plus)", result.output)
        self.assertEqual((self.org()["plan"], self.org()["academy_status"]), ("plus", "active"))
        result = self.app.test_cli_runner().invoke(args=["plan", str(self.org_id), "pro"])
        self.assertIn("Pro on", result.output)
        self.assertEqual(self.org()["plan"], "pro")
        self.app.test_cli_runner().invoke(args=["plan", str(self.org_id), "none"])
        self.assertEqual(self.org()["academy_status"], "none")


class TestMigration18(unittest.TestCase):
    """A filled version-17 database: the old Academy plan's payers keep it,
    everyone else gets the new trial from the day of the upgrade, and
    nothing is lost."""

    def test_upgrade(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "old.db")
            conn = connect(path)
            with mock.patch.object(dbmod, "MIGRATIONS", [m for m in dbmod.MIGRATIONS if m[0] <= 17]):
                self.assertEqual(migrate(conn), 17)
            later_migrations = mock.patch.object(dbmod, "MIGRATIONS", [m for m in dbmod.MIGRATIONS if m[0] <= 18])
            later_migrations.start()
            self.addCleanup(later_migrations.stop)
            made = "2026-01-01T00:00:00+00:00"
            later = iso(utcnow() + timedelta(days=60))
            rows = [(1, "active", None, "sub_1"), (2, "past_due", None, "sub_2"), (3, "canceled", EXPIRED, "sub_3"),
                    (4, "none", None, None), (5, "none", EXPIRED, None), (6, "none", later, None)]
            for org_id, status, trial, sub in rows:
                conn.execute("INSERT INTO orgs (id, name, created_at, academy_status, academy_trial_ends,"
                             " stripe_subscription_id) VALUES (?, ?, ?, ?, ?, ?)",
                             (org_id, f"Org {org_id}", made, status, trial, sub))
                conn.execute("INSERT INTO items (org_id, industry_id, rule_key, value_num, updated_at)"
                             " VALUES (?, 2, 'cold_holding', 38, ?)", (org_id, made))
                conn.execute("INSERT INTO audit (org_id, at, action, summary) VALUES (?, ?, 'reading', 'x')",
                             (org_id, made))
            conn.execute("INSERT INTO learners (org_id, nickname, avatar, created_at) VALUES (1, 'Kid', 'rocket', ?)",
                         (made,))
            conn.commit()
            self.assertEqual(migrate(conn, trial_days=21), 18)
            orgs = {r["id"]: dict(r) for r in conn.execute("SELECT * FROM orgs")}
            counts = [conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in ("items", "audit", "learners")]
            tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
            conn.close()
        self.assertEqual(counts, [6, 6, 1])
        self.assertIn("bundle_signatures", tables)
        self.assertEqual({i: o["plan"] for i, o in orgs.items()},
                         {1: "academy", 2: "academy", 3: "none", 4: "none", 5: "none", 6: "none"})
        self.assertIsNone(orgs[1]["academy_trial_ends"])
        for i in (3, 4, 5):
            ends = datetime.fromisoformat(orgs[i]["academy_trial_ends"])
            self.assertAlmostEqual((ends - datetime.now(timezone.utc)).total_seconds() / 86400, 21, delta=0.01)
        self.assertEqual(orgs[6]["academy_trial_ends"], later, "a later trial end is kept")
        self.assertTrue(all(o["bundle_report_at"] is None for o in orgs.values()))
        for i in (1, 2):
            access = plans.access(orgs[i], trial_days=21)
            self.assertEqual((access["tracker"], access["academy"], access["legacy"]), (True, True, True))
        for i in (3, 4, 5, 6):
            access = plans.access(orgs[i], trial_days=21)
            self.assertEqual((access["source"], access["academy"]), ("trial", True))


class TestMigration19(unittest.TestCase):
    """Every subscription before yearly billing was monthly."""

    def test_upgrade(self):
        with tempfile.TemporaryDirectory() as tmp:
            conn = connect(os.path.join(tmp, "old.db"))
            with mock.patch.object(dbmod, "MIGRATIONS", [m for m in dbmod.MIGRATIONS if m[0] <= 18]):
                self.assertEqual(migrate(conn), 18)
            conn.execute("INSERT INTO orgs (id, name, created_at, academy_status, plan) VALUES"
                         " (1, 'Paid', '2026-01-01T00:00:00+00:00', 'active', 'plus'),"
                         " (2, 'Trial', '2026-01-01T00:00:00+00:00', 'none', 'none')")
            conn.commit()
            self.assertEqual(migrate(conn), 19)
            rows = [tuple(r) for r in conn.execute("SELECT plan, plan_interval FROM orgs ORDER BY id")]
            conn.close()
        self.assertEqual(rows, [("plus", "month"), ("none", "month")])


class TestTheDocs(unittest.TestCase):
    def read(self, *parts):
        with open(os.path.join(ROOT, *parts), encoding="utf-8") as f:
            return f.read()

    def test_the_settings_are_documented(self):
        names = ("PRO_STRIPE_PRICE", "PLUS_STRIPE_PRICE", "PLUS_BUNDLE_UPGRADE_STRIPE_PRICE", "KITCHEN_BUNDLE_SECRET",
                 *YEARLY_PRICES)
        for name in names:
            for doc in ((".env.example",), ("render.yaml",), ("docs", "OPERATIONS.md"), ("docs", "HANDBOOK.md")):
                self.assertIn(name, self.read(*doc), f"{name} in {'/'.join(doc)}")
        for name in YEARLY_PRICES:
            self.assertIn(name, self.read("README.md"))
        render = self.read("render.yaml")
        for name in names:
            self.assertRegex(render, rf"- key: {name}\n\s+sync: false")
        for gone in ("ACADEMY_PRICE_LABEL", "ACADEMY_STRIPE_PRICE"):
            self.assertNotIn(gone, self.read(".env.example"))
            self.assertNotIn(gone, render)

    def test_the_contract_has_the_header(self):
        doc = self.read("docs", "CYBERLOGIX-CONNECTION.md")
        self.assertIn('X-CyberLogix-Signature: t=<unix seconds>,v1=<hex HMAC-SHA256(secret, f"{t}.{raw_request_body_bytes}")>',
                      doc)
        self.assertIn("KITCHEN_BUNDLE_SECRET", doc)
        self.assertIn(f"{connections.SIGNATURE_TOLERANCE} seconds", doc)
        self.assertIn(f"{int(connections.SIGNATURE_MEMORY.total_seconds() // 60)} minutes", doc)
        for status in ("valid", "missing", "invalid", "stale", "replayed", "not_configured"):
            self.assertIn(f"`{status}`", doc)


if __name__ == "__main__":
    unittest.main()
