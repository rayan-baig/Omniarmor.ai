"""The plans' whole life against a fake Stripe, end to end.

FakeStripe is a small web server on this machine that answers the three
Stripe API calls the app makes (create a Checkout session, read one back,
open the billing portal) the way Stripe's test mode does, and plays
Stripe's part when a family acts on Stripe's own pages: paying, a renewal
that fails, the subscription ending. Each of those sends the app the signed
webhook events Stripe would. The app talks to it over HTTP through its own
Stripe client (academy_plan._stripe), so the request it builds, its key and
its error handling are all exercised, and nothing is mocked inside the app.

The workspace goes: free trial -> trial over (read-only) -> Plus -> a failed
payment -> cancelled -> Plus again, and the app's state is checked at every
step: the workspace's plan in the database, what the owner reads on Settings
and the plan page, whether checks can be saved, and which worlds the learner
can open. Pro is bought and switched to Plus in Stripe's portal; a Kitchen
Safety Bundle workspace buys Plus at the difference. Plus is bought yearly,
switched to monthly and to Pro yearly in the portal, and cancelled to run to
the end of the paid year. Every checkout bills the workspace's location count.
"""

import hashlib
import hmac
import json
import os
import re
import sys
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest import mock
from urllib.parse import parse_qsl, urlsplit

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from e2e_helpers import flashes, post_forms  # noqa: E402
from test_webapp import AppTestCase, first_rule  # noqa: E402

from omniarmor_app import academy, academy_plan, connections, plans  # noqa: E402

SECRET_KEY = "sk_test_fake_omniarmor"
WEBHOOK_SECRET = "whsec_fake_omniarmor"
PRICE = "price_test_plus"
PRO_PRICE = "price_test_pro"
UPGRADE_PRICE = "price_test_plus_bundle"
PRO_YEARLY = "price_test_pro_year"
PLUS_YEARLY = "price_test_plus_year"
UPGRADE_YEARLY = "price_test_plus_bundle_year"
YEARLY = {PRO_YEARLY, PLUS_YEARLY, UPGRADE_YEARLY}
BUNDLE_SECRET = "kitchen-bundle-e2e"
DAY = 24 * 3600


class FakeStripe:
    """Stripe in test mode, on 127.0.0.1, holding its objects in memory."""

    def __init__(self, deliver):
        self.deliver_to = deliver          # posts one webhook to the app, returns the response
        self.sessions, self.customers, self.subscriptions = {}, {}, {}
        self.requests = []                 # (method, path, form fields, Authorization header)
        self.idempotency_keys = []         # each request's Idempotency-Key header (None on a GET)
        self.events = []
        self.down = False                  # answer every API call with a 500
        self.counter = 0
        self.clock = int(time.time()) - 3600
        fake = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_GET(self):
                fake.handle(self, "GET")

            def do_POST(self):
                fake.handle(self, "POST")

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}/v1"
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def stop(self):
        self.server.shutdown()
        self.server.server_close()

    def next_id(self, prefix):
        self.counter += 1
        return f"{prefix}_test_{self.counter}"

    def tick(self):
        """Stripe's clock: every object and event a second after the last."""
        self.clock += 1
        return self.clock

    # --- The API --------------------------------------------------------------------

    def handle(self, request, method):
        length = int(request.headers.get("Content-Length") or 0)
        fields = dict(parse_qsl(request.rfile.read(length).decode())) if length else {}
        path = urlsplit(request.path).path
        self.requests.append((method, path, fields, request.headers.get("Authorization")))
        self.idempotency_keys.append(request.headers.get("Idempotency-Key"))
        if self.down:
            return self.reply(request, 500, {"error": {"message": "Stripe is having trouble."}})
        if request.headers.get("Authorization") != f"Bearer {SECRET_KEY}":
            return self.reply(request, 401, {"error": {"message": "Invalid API Key provided."}})
        if method == "POST" and path == "/v1/checkout/sessions":
            return self.reply(request, 200, self.create_session(fields))
        found = re.fullmatch(r"/v1/checkout/sessions/(cs_[\w]+)", path)
        if method == "GET" and found and found.group(1) in self.sessions:
            return self.reply(request, 200, self.sessions[found.group(1)])
        if method == "POST" and path == "/v1/billing_portal/sessions":
            if fields.get("customer") not in self.customers:
                return self.reply(request, 400, {"error": {"message": "No such customer."}})
            return self.reply(request, 200, {"id": self.next_id("bps"), "object": "billing_portal.session",
                                             "url": f"https://billing.stripe.test/p/{fields['customer']}"})
        return self.reply(request, 404, {"error": {"message": f"Unrecognized request URL ({method}: {path})."}})

    def reply(self, request, status, body):
        data = json.dumps(body).encode()
        request.send_response(status)
        request.send_header("Content-Type", "application/json")
        request.send_header("Content-Length", str(len(data)))
        request.end_headers()
        request.wfile.write(data)

    def create_session(self, fields):
        assert fields.get("mode") == "subscription", fields
        assert fields.get("line_items[0][price]") in (PRICE, PRO_PRICE, UPGRADE_PRICE, *YEARLY), fields
        assert "{CHECKOUT_SESSION_ID}" in fields["success_url"], fields
        session_id = self.next_id("cs")
        session = {
            "id": session_id, "object": "checkout.session", "mode": "subscription", "status": "open",
            "payment_status": "unpaid", "client_reference_id": fields.get("client_reference_id"),
            "metadata": {"org_id": fields.get("metadata[org_id]")}, "customer": fields.get("customer"),
            "customer_email": fields.get("customer_email"), "subscription": None, "created": self.tick(),
            "success_url": fields["success_url"], "cancel_url": fields["cancel_url"],
            "subscription_metadata": {"org_id": fields.get("subscription_data[metadata][org_id]"),
                                      "plan": fields.get("subscription_data[metadata][plan]"),
                                      "interval": fields.get("subscription_data[metadata][interval]")},
            "metadata_plan": fields.get("metadata[plan]"),
            "metadata_interval": fields.get("metadata[interval]"),
            "price": fields.get("line_items[0][price]"), "quantity": int(fields.get("line_items[0][quantity]")),
            "url": f"https://checkout.stripe.test/c/pay/{session_id}",
        }
        session["metadata"]["plan"] = session.pop("metadata_plan")
        session["metadata"]["interval"] = session.pop("metadata_interval")
        self.sessions[session_id] = session
        return self.public(session)

    @staticmethod
    def price(price_id):
        """A price as Stripe shows it on a subscription item: yearly or monthly."""
        return {"id": price_id, "object": "price",
                "recurring": {"interval": "year" if price_id in YEARLY else "month", "interval_count": 1}}

    @staticmethod
    def public(session):
        return {k: v for k, v in session.items() if k not in ("subscription_metadata", "price", "quantity")}

    # --- What happens on Stripe's own pages, and the webhooks it sends ------------

    def send(self, kind, obj):
        # A copy of the object as it is now, as Stripe's event holds it.
        event = {"id": self.next_id("evt"), "object": "event", "type": kind, "created": self.tick(),
                 "data": {"object": json.loads(json.dumps(obj))}, "livemode": False}
        self.events.append(event)
        return self.deliver(event)

    def deliver(self, event):
        payload = json.dumps(event).encode()
        stamp = int(time.time())
        signature = hmac.new(WEBHOOK_SECRET.encode(), f"{stamp}.".encode() + payload, hashlib.sha256).hexdigest()
        return self.deliver_to(payload, f"t={stamp},v1={signature}")

    def pay(self, session_id):
        """The family pays on Stripe Checkout. Returns the page Stripe sends them back to."""
        session = self.sessions[session_id]
        customer = session["customer"]
        if customer is None:
            customer = self.next_id("cus")
            self.customers[customer] = {"id": customer, "email": session["customer_email"]}
        now = self.tick()
        period = 365 * DAY if session["price"] in YEARLY else 30 * DAY
        subscription = {"id": self.next_id("sub"), "object": "subscription", "customer": customer,
                        "status": "active", "created": now, "current_period_end": now + period,
                        "cancel_at_period_end": False, "metadata": session["subscription_metadata"],
                        "items": {"data": [{"price": self.price(session["price"]), "quantity": session["quantity"]}]}}
        self.subscriptions[subscription["id"]] = subscription
        session.update(status="complete", payment_status="paid", customer=customer,
                       subscription=subscription["id"])
        self.webhooks_for_payment = [("checkout.session.completed", self.public(session)),
                                     ("customer.subscription.created", subscription),
                                     ("invoice.paid", self.invoice(subscription, "paid"))]
        return session["success_url"].replace("{CHECKOUT_SESSION_ID}", session_id)

    def send_payment_webhooks(self):
        return [self.send(kind, obj) for kind, obj in self.webhooks_for_payment]

    def invoice(self, subscription, status):
        return {"id": self.next_id("in"), "object": "invoice", "customer": subscription["customer"],
                "subscription": subscription["id"], "status": status, "metadata": subscription["metadata"]}

    def fail_renewal(self, sub_id):
        """The card is declined at renewal: Stripe keeps retrying, the subscription is past due."""
        subscription = self.subscriptions[sub_id]
        subscription.update(status="past_due")
        return [self.send("invoice.payment_failed", self.invoice(subscription, "open")),
                self.send("customer.subscription.updated", subscription)]

    def switch(self, sub_id, price):
        """The owner changes plan in the customer portal: the subscription's
        price changes (Pro to Plus, monthly to yearly), and a switch of
        interval starts a new period."""
        subscription = self.subscriptions[sub_id]
        item = subscription["items"]["data"][0]
        before = item["price"]["recurring"]["interval"]
        item["price"] = self.price(price)
        if item["price"]["recurring"]["interval"] != before:
            subscription["current_period_end"] = self.tick() + (365 * DAY if price in YEARLY else 30 * DAY)
        return self.send("customer.subscription.updated", subscription)

    def cancel_at_period_end(self, sub_id):
        """The owner cancels in the customer portal: it stays on to the end of the paid period."""
        subscription = self.subscriptions[sub_id]
        subscription.update(cancel_at_period_end=True, cancel_at=subscription["current_period_end"])
        return self.send("customer.subscription.updated", subscription)

    def end(self, sub_id):
        """Stripe gives up on the card (or the family cancels at once): the subscription ends."""
        subscription = self.subscriptions[sub_id]
        subscription.update(status="canceled", ended_at=self.tick())
        return self.send("customer.subscription.deleted", subscription)


class TestPlansAgainstFakeStripe(AppTestCase):
    def setUp(self):
        super().setUp()
        self.app.config.update(STRIPE_SECRET_KEY=SECRET_KEY, STRIPE_WEBHOOK_SECRET=WEBHOOK_SECRET,
                               PLUS_STRIPE_PRICE=PRICE, PRO_STRIPE_PRICE=PRO_PRICE,
                               PLUS_BUNDLE_UPGRADE_STRIPE_PRICE=UPGRADE_PRICE, KITCHEN_BUNDLE_SECRET=BUNDLE_SECRET,
                               PRO_YEARLY_STRIPE_PRICE=PRO_YEARLY, PLUS_YEARLY_STRIPE_PRICE=PLUS_YEARLY,
                               PLUS_BUNDLE_UPGRADE_YEARLY_STRIPE_PRICE=UPGRADE_YEARLY)
        self.stripe = FakeStripe(self.webhook)
        self.addCleanup(self.stripe.stop)
        for patcher in (mock.patch.object(academy_plan, "STRIPE_API", self.stripe.url),
                        # The fake runs on this machine: never send its calls through a proxy.
                        mock.patch.dict(os.environ, {"no_proxy": "127.0.0.1,localhost",
                                                     "NO_PROXY": "127.0.0.1,localhost"})):
            patcher.start()
            self.addCleanup(patcher.stop)
        self.stripe_side = self.app.test_client()       # Stripe's own connection to the app
        self.signup()
        self.post("/app/academy/learners", {"nickname": "Sam", "avatar": "rocket", "track": "trailblazer"})
        with self.db() as conn:
            self.lid = conn.execute("SELECT id FROM learners").fetchone()[0]
            self.org_id = conn.execute("SELECT id FROM orgs").fetchone()[0]
        # Trailblazer's first world: open to play, and only free on the Launchpad track.
        self.paid_world = academy.TRACKS["trailblazer"].topics[0]
        self.check = first_rule(18, kind="max").key
        self.assertNotEqual(academy_plan.FREE_TRACK, "trailblazer")

    def webhook(self, payload, signature):
        response = self.stripe_side.post("/billing/stripe/webhook", data=payload,
                                         headers={"Stripe-Signature": signature, "Content-Type": "application/json"})
        self.assertEqual(response.status_code, 200, response.data)
        return response

    # --- What the app shows ---------------------------------------------------------

    def org(self):
        with self.db() as conn:
            return dict(conn.execute("SELECT academy_status, academy_renews_at, academy_ends_at, plan, plan_interval,"
                                     " stripe_customer_id, stripe_subscription_id FROM orgs").fetchone())

    def settings_line(self):
        page = self.client.get("/app/settings").get_data(as_text=True)
        line = re.search(r"<span data-plan-line>(.*?)</span>", page, re.S).group(1)
        return " ".join(re.sub(r"<[^>]+>", " ", line).split()).replace("&#39;", "'")

    def can_save(self, value):
        """Whether the owner can save a reading on a check (the tracker isn't read-only)."""
        self.change(18, self.check, value=str(value))
        with self.db() as conn:
            row = conn.execute("SELECT value_num FROM items WHERE rule_key = ?", (self.check,)).fetchone()
        return row is not None and row[0] == value

    def plan_page(self):
        return self.client.get("/app/plan").get_data(as_text=True)

    def paid_world_opens(self):
        """Whether the learner can open a world outside the free ones, or is
        sent to the plan page instead."""
        response = self.client.get(f"/app/academy/{self.lid}/world/{self.paid_world}")
        if response.status_code == 200:
            return True
        self.assertEqual(response.status_code, 302)
        # The plan page, or once a week for a workspace on Pro, a peek at the
        # world's first lesson with the offer to switch to Plus (nudges.py).
        location = response.headers["Location"]
        self.assertTrue(location.endswith("/app/plan")
                        or location.endswith(f"/app/academy/{self.lid}/world/{self.paid_world}/preview"), location)
        return False

    def free_world_opens(self):
        self.post(f"/app/academy/{self.lid}/track", {"track": "launchpad"})
        opens = self.client.get(f"/app/academy/{self.lid}/world/1").status_code == 200
        self.post(f"/app/academy/{self.lid}/track", {"track": "trailblazer"})
        return opens

    def checkout_form(self, plan, interval="month"):
        """The plan page's form for a plan, paid monthly or yearly."""
        [form] = [f for f in post_forms(self.plan_page())
                  if f.action == "/app/plan/checkout" and f.field("plan")["value"] == plan
                  and f.field("interval")["value"] == interval]
        return form

    def start_checkout(self, plan="plus", interval="month"):
        """The owner presses "Choose Plus" (or Pro, or "Choose Plus yearly") on the plan page."""
        form = self.checkout_form(plan, interval)
        response = self.client.post(form.action, data=form.values())
        self.assertEqual(response.status_code, 303)
        found = re.fullmatch(r"https://checkout\.stripe\.test/c/pay/(cs_test_\d+)", response.headers["Location"])
        self.assertIsNotNone(found, response.headers["Location"])
        return found.group(1)

    def come_back(self, url):
        """The browser follows Stripe back to the app."""
        parts = urlsplit(url)
        self.assertEqual(f"{parts.scheme}://{parts.netloc}", "http://localhost")   # the test client's own host
        response = self.client.get(f"{parts.path}?{parts.query}", follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        return response.get_data(as_text=True)

    # --- The whole life -------------------------------------------------------------

    def test_trial_paid_failed_payment_cancelled_and_back(self):
        # 1. The free trial: everything opens and saves, nothing has touched Stripe.
        self.assertEqual(self.org()["academy_status"], "none")
        self.assertRegex(self.settings_line(), r"^Free trial: 14 days left of everything in Plus\.")
        self.assertIn("Your free trial is on", self.plan_page())
        self.assertTrue(self.paid_world_opens())
        self.assertTrue(self.can_save(5))
        self.assertEqual(self.stripe.requests, [])

        # 2. The trial ends: read-only, and only the free worlds open.
        with self.db() as conn:
            conn.execute("UPDATE orgs SET academy_trial_ends = '2000-01-01T00:00:00+00:00'")
            conn.commit()
        self.assertRegex(self.settings_line(), r"^No plan: the compliance tracker is read-only")
        self.assertIn("Choose a plan", self.plan_page())
        self.assertFalse(self.paid_world_opens())
        self.assertTrue(self.free_world_opens())
        self.assertFalse(self.can_save(6))
        self.assertEqual(self.client.get("/app/report.csv").status_code, 200)

        # 3. Plus. The owner goes to Stripe Checkout and pays for one location;
        # Stripe sends them back before its webhooks arrive, and the plan is on at once.
        first = self.start_checkout("plus")
        method, path, fields, key = self.stripe.requests[-1]
        self.assertEqual((method, path, key), ("POST", "/v1/checkout/sessions", f"Bearer {SECRET_KEY}"))
        self.assertEqual(fields["client_reference_id"], str(self.org_id))
        self.assertEqual(fields["customer_email"], "owner@example.com")
        self.assertEqual((fields["line_items[0][price]"], fields["metadata[plan]"]), (PRICE, "plus"))
        self.assertEqual(fields["line_items[0][quantity]"], "1")
        self.assertNotIn("customer", fields)
        self.assertEqual(self.org()["academy_status"], "none", "nothing changes until Stripe says it's paid")
        page = self.come_back(self.stripe.pay(first))
        self.assertEqual(self.stripe.requests[-1][:2], ("GET", f"/v1/checkout/sessions/{first}"))
        self.assertIn("Thank you! Plus is on for Acme Logistics.", flashes(page))
        org = self.org()
        self.assertEqual((org["academy_status"], org["plan"], org["stripe_customer_id"], org["stripe_subscription_id"]),
                         ("active", "plus", "cus_test_2", "sub_test_3"))
        self.stripe.send_payment_webhooks()
        org = self.org()
        self.assertEqual((org["academy_status"], org["plan"], org["stripe_subscription_id"]), ("active", "plus", "sub_test_3"))
        self.assertIsNotNone(org["academy_renews_at"], "the subscription's period end")
        self.assertIsNone(org["academy_ends_at"])
        self.assertRegex(self.settings_line(), r"^You're on Plus, renews ")
        self.assertIn("You're on Plus", self.plan_page())
        self.assertNotIn("Choose Plus", self.plan_page())
        self.assertTrue(self.paid_world_opens())
        self.assertTrue(self.can_save(7))

        # 4. A renewal fails: the plan is past due, the owner is told to update
        # the card (Stripe's billing portal), and everything keeps working.
        self.stripe.fail_renewal("sub_test_3")
        self.assertEqual(self.org()["academy_status"], "past_due")
        self.assertRegex(self.settings_line(), r"^Your last payment for Plus didn't go through\. Update your card")
        self.assertIn("Update your card to keep it", self.plan_page().replace("&#39;", "'"))
        self.assertTrue(self.paid_world_opens())
        self.assertTrue(self.can_save(8))
        [manage] = [f for f in post_forms(self.plan_page()) if f.action == "/app/plan/manage"]
        response = self.client.post(manage.action, data=manage.values())
        self.assertEqual(response.headers["Location"], "https://billing.stripe.test/p/cus_test_2")
        self.assertEqual(self.stripe.requests[-1][2]["customer"], "cus_test_2")

        # 5. Stripe gives up and the subscription ends: read-only and the free
        # worlds, with every learner, their progress and every reading kept.
        self.post(f"/app/academy/{self.lid}/world/1/stage/1", {"attempt": "1", "check": "0", "choice": "0"})
        self.stripe.end("sub_test_3")
        org = self.org()
        self.assertEqual((org["academy_status"], org["academy_renews_at"]), ("canceled", None))
        self.assertRegex(self.settings_line(), r"^No plan: the compliance tracker is read-only")
        self.assertIn("Choose a plan", self.plan_page())
        self.assertIn("Past invoices and billing", self.plan_page())
        self.assertIn("Your plan has ended", self.client.get("/app").get_data(as_text=True))
        self.assertFalse(self.paid_world_opens())
        self.assertTrue(self.free_world_opens())
        self.assertFalse(self.can_save(9))
        with self.db() as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM learners").fetchone()[0], 1)
            self.assertEqual(conn.execute("SELECT value_num FROM items WHERE rule_key = ?", (self.check,)).fetchone()[0], 8)
        # Stripe retries the first payment's events: an ended plan stays ended.
        for event in self.stripe.events[:2]:
            self.stripe.deliver(event)
        self.assertEqual(self.org()["academy_status"], "canceled")
        self.assertFalse(self.paid_world_opens())

        # 6. Resubscribed: the same Stripe customer, a new subscription.
        second = self.start_checkout("plus")
        fields = self.stripe.requests[-1][2]
        self.assertEqual(fields["customer"], "cus_test_2")
        self.assertNotIn("customer_email", fields)
        self.stripe.pay(second)
        self.stripe.send_payment_webhooks()            # the webhooks first this time
        org = self.org()
        self.assertEqual((org["academy_status"], org["stripe_customer_id"], org["stripe_subscription_id"]),
                         ("active", "cus_test_2", self.stripe.sessions[second]["subscription"]))
        self.assertNotEqual(org["stripe_subscription_id"], "sub_test_3")
        self.assertIsNotNone(org["academy_renews_at"])
        page = self.come_back(self.stripe.sessions[second]["success_url"].replace("{CHECKOUT_SESSION_ID}", second))
        self.assertIn("Thank you! Plus is on for Acme Logistics.", flashes(page))
        self.assertRegex(self.settings_line(), r"^You're on Plus, renews ")
        self.assertTrue(self.paid_world_opens())
        # The old subscription's late "deleted" event doesn't end the new plan.
        self.stripe.deliver(next(e for e in self.stripe.events if e["type"] == "customer.subscription.deleted"))
        self.assertEqual(self.org()["academy_status"], "active")

    def end_trial(self):
        with self.db() as conn:
            conn.execute("UPDATE orgs SET academy_trial_ends = '2000-01-01T00:00:00+00:00'")
            conn.commit()

    def test_pro_then_plus_in_the_portal(self):
        self.end_trial()
        session = self.start_checkout("pro")
        fields = self.stripe.requests[-1][2]
        self.assertEqual((fields["line_items[0][price]"], fields["line_items[0][quantity]"], fields["metadata[plan]"]),
                         (PRO_PRICE, str(plans.location_count(None)), "pro"))
        self.stripe.pay(session)
        self.stripe.send_payment_webhooks()
        org = self.org()
        self.assertEqual((org["academy_status"], org["plan"]), ("active", "pro"))
        self.assertRegex(self.settings_line(), r"^You're on Pro, renews ")
        self.assertTrue(self.can_save(3))
        self.assertFalse(self.paid_world_opens(), "Pro doesn't include the whole Academy")
        self.assertTrue(self.free_world_opens())
        # Switched to Plus in Stripe's portal.
        sub = org["stripe_subscription_id"]
        self.stripe.switch(sub, PRICE)
        self.assertEqual(self.org()["plan"], "plus")
        self.assertTrue(self.paid_world_opens())
        # Stripe sends the switch again, then a late copy of the Pro subscription's
        # first event (an older event under a new id): neither moves it back.
        self.stripe.deliver(self.stripe.events[-1])
        created = next(e for e in self.stripe.events if e["type"] == "customer.subscription.created")
        late = json.loads(json.dumps(created))
        late["id"] = "evt_late_copy"
        late["data"]["object"]["items"] = {"data": [{"price": FakeStripe.price(PRO_PRICE), "quantity": 1}]}
        self.stripe.deliver(late)
        self.assertEqual(self.org()["plan"], "plus")
        self.assertTrue(self.paid_world_opens())

    def test_a_kitchen_safety_bundle_workspace_pays_the_difference(self):
        self.end_trial()
        self.change(18, self.check, value="1")       # nothing saved: read-only
        key = re.search(r'class="key mono">(clx_[A-Za-z0-9_-]+)<', self.post(
            "/app/settings/connections/cyberlogix/create").get_data(as_text=True)).group(1)
        body = json.dumps({"date": "2026-11-13", "site": None, "units_total": 2, "units_in_range_all_day": 2,
                           "breaches": [], "warmest_reading": 38, "unit_of_measure": "°F", "log_url": None}).encode()
        with mock.patch("omniarmor_app.connections.org_today",
                        return_value=__import__("datetime").date(2026, 11, 14)):
            answer = self.stripe_side.post("/api/connect/cyberlogix/daily", data=body,
                                           headers={"Authorization": f"Bearer {key}",
                                                    "Content-Type": "application/json",
                                                    connections.SIGNATURE_HEADER:
                                                        connections.sign(BUNDLE_SECRET, body, int(time.time()))}).get_json()
        self.assertEqual((answer["signature"], answer["bundle_counted"]), ("valid", True))
        settings = self.client.get("/app/settings").get_data(as_text=True)
        self.assertIn("Pro included with your Kitchen Safety Bundle", settings)
        self.assertTrue(self.can_save(4))
        self.assertFalse(self.paid_world_opens())
        page = self.plan_page()
        self.assertNotIn('value="pro"', page, "Pro is already included")
        session = self.start_checkout("plus")
        fields = self.stripe.requests[-1][2]
        self.assertEqual((fields["line_items[0][price]"], fields["line_items[0][quantity]"], fields["metadata[plan]"]),
                         (UPGRADE_PRICE, "1", "plus_bundle"))
        self.come_back(self.stripe.pay(session))
        self.stripe.send_payment_webhooks()
        org = self.org()
        self.assertEqual((org["academy_status"], org["plan"]), ("active", "plus_bundle"))
        self.assertTrue(self.paid_world_opens())
        self.assertTrue(self.can_save(5))
        self.assertRegex(self.settings_line(), r"^You're on Plus at the Kitchen Safety Bundle price")

    def test_yearly_plus_switched_in_the_portal_and_cancelled_to_the_end_of_the_year(self):
        self.end_trial()
        # The plan page offers both: the yearly switch, the yearly price and "2 months free".
        page = self.plan_page()
        self.assertIn("data-billing-toggle", page)
        self.assertIn(plans.PLUS.yearly_price, page)
        self.assertIn(plans.free_label(), page)
        # Plus, yearly: the yearly price, one location, and the interval in the metadata.
        session = self.start_checkout("plus", "year")
        fields = self.stripe.requests[-1][2]
        self.assertEqual((fields["line_items[0][price]"], fields["line_items[0][quantity]"], fields["metadata[plan]"],
                          fields["metadata[interval]"], fields["subscription_data[metadata][interval]"]),
                         (PLUS_YEARLY, str(plans.location_count(None)), "plus", "year", "year"))
        page = self.come_back(self.stripe.pay(session))
        self.assertIn("Thank you! Plus is on for Acme Logistics.", flashes(page))
        org = self.org()
        self.assertEqual((org["academy_status"], org["plan"], org["plan_interval"]), ("active", "plus", "year"))
        self.stripe.send_payment_webhooks()
        org = self.org()
        self.assertEqual((org["plan"], org["plan_interval"]), ("plus", "year"))
        sub = org["stripe_subscription_id"]
        renews = __import__("datetime").datetime.fromisoformat(org["academy_renews_at"]).timestamp()
        self.assertEqual(renews, self.stripe.subscriptions[sub]["current_period_end"])
        self.assertGreater(renews - time.time(), 360 * DAY, "a year away")
        self.assertRegex(self.settings_line(), r"^You're on Plus, billed yearly, renews ")
        self.assertRegex(self.plan_page(), r'id="billing-year" value="yearly" checked>')
        self.assertTrue(self.paid_world_opens())
        self.assertTrue(self.can_save(3))
        # In the portal: yearly to monthly, then to Pro yearly. The webhook reads both from the price.
        [manage] = [f for f in post_forms(self.plan_page()) if f.action == "/app/plan/manage"]
        self.assertEqual(self.client.post(manage.action, data=manage.values()).headers["Location"],
                         f"https://billing.stripe.test/p/{org['stripe_customer_id']}")
        self.stripe.switch(sub, PRICE)
        org = self.org()
        self.assertEqual((org["plan"], org["plan_interval"]), ("plus", "month"))
        self.assertRegex(self.settings_line(), r"^You're on Plus, renews ")
        self.stripe.switch(sub, PRO_YEARLY)
        org = self.org()
        self.assertEqual((org["plan"], org["plan_interval"]), ("pro", "year"))
        self.assertRegex(self.settings_line(), r"^You're on Pro, billed yearly, renews ")
        self.assertFalse(self.paid_world_opens(), "Pro doesn't include the whole Academy")
        self.stripe.switch(sub, PLUS_YEARLY)
        self.assertEqual((self.org()["plan"], self.org()["plan_interval"]), ("plus", "year"))
        # A late copy of the monthly switch doesn't move it back.
        self.stripe.deliver(next(e for e in self.stripe.events
                                 if e["type"] == "customer.subscription.updated"
                                 and e["data"]["object"]["items"]["data"][0]["price"]["id"] == PRICE))
        self.assertEqual(self.org()["plan_interval"], "year")
        # Cancelled in the portal: on until the end of the paid year, then read-only.
        self.stripe.cancel_at_period_end(sub)
        org = self.org()
        self.assertEqual(org["academy_status"], "active")
        ends = __import__("datetime").datetime.fromisoformat(org["academy_ends_at"]).timestamp()
        self.assertEqual(ends, self.stripe.subscriptions[sub]["current_period_end"])
        self.assertRegex(self.settings_line(), r"^Plus, paid yearly, is cancelled and ends .*the end of the year you "
                                               r"paid for\. A yearly plan isn't refunded")
        self.assertTrue(self.paid_world_opens())
        self.assertTrue(self.can_save(4))
        self.stripe.end(sub)
        self.assertEqual(self.org()["academy_status"], "canceled")
        self.assertRegex(self.settings_line(), r"^No plan: the compliance tracker is read-only")
        self.assertFalse(self.can_save(5))
        self.assertFalse(self.paid_world_opens())

    def test_a_bundle_workspace_pays_the_difference_yearly(self):
        self.end_trial()
        key = re.search(r'class="key mono">(clx_[A-Za-z0-9_-]+)<', self.post(
            "/app/settings/connections/cyberlogix/create").get_data(as_text=True)).group(1)
        body = json.dumps({"date": "2026-11-13", "site": None, "units_total": 2, "units_in_range_all_day": 2,
                           "breaches": [], "warmest_reading": 38, "unit_of_measure": "°F", "log_url": None}).encode()
        with mock.patch("omniarmor_app.connections.org_today",
                        return_value=__import__("datetime").date(2026, 11, 14)):
            self.stripe_side.post("/api/connect/cyberlogix/daily", data=body,
                                  headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json",
                                           connections.SIGNATURE_HEADER:
                                               connections.sign(BUNDLE_SECRET, body, int(time.time()))})
        session = self.start_checkout("plus", "year")
        fields = self.stripe.requests[-1][2]
        self.assertEqual((fields["line_items[0][price]"], fields["metadata[plan]"], fields["metadata[interval]"]),
                         (UPGRADE_YEARLY, "plus_bundle", "year"))
        self.come_back(self.stripe.pay(session))
        self.stripe.send_payment_webhooks()
        org = self.org()
        self.assertEqual((org["plan"], org["plan_interval"]), ("plus_bundle", "year"))
        self.assertRegex(self.settings_line(), r"^You're on Plus at the Kitchen Safety Bundle price, billed yearly")
        self.assertTrue(self.paid_world_opens())

    def test_when_stripe_is_down_nothing_changes(self):
        with self.db() as conn:
            conn.execute("UPDATE orgs SET academy_trial_ends = '2000-01-01T00:00:00+00:00'")
            conn.commit()
        self.stripe.down = True
        form = self.checkout_form("plus")
        with self.assertLogs("omniarmor_app", "WARNING"):
            response = self.client.post(form.action, data=form.values(), follow_redirects=True)
        self.assertIn("We couldn&#39;t open checkout just now. Please try again in a minute.",
                      flashes(response.get_data(as_text=True)))
        # A 500 is tried once more, with the same Idempotency-Key, so Stripe
        # would make one checkout however many of the two arrived.
        self.assertEqual(len(self.stripe.requests), 2)
        first, again = self.stripe.idempotency_keys
        self.assertTrue(first)
        self.assertEqual(first, again)
        self.assertEqual(self.org()["academy_status"], "none")
        self.assertFalse(self.paid_world_opens())

    def test_a_wrong_secret_key_is_refused_by_stripe(self):
        with self.db() as conn:
            conn.execute("UPDATE orgs SET academy_trial_ends = '2000-01-01T00:00:00+00:00'")
            conn.commit()
        self.app.config["STRIPE_SECRET_KEY"] = "sk_test_wrong"
        with self.assertLogs("omniarmor_app", "WARNING") as logged:
            self.post("/app/plan/checkout", {"plan": "plus"})
        self.assertTrue(any("Invalid API Key provided" in line for line in logged.output))
        self.assertNotIn("sk_test_wrong", " ".join(logged.output))
        self.assertEqual(self.org()["academy_status"], "none")


if __name__ == "__main__":
    unittest.main()
