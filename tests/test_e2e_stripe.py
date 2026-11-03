"""The Academy plan's whole life against a fake Stripe, end to end.

FakeStripe is a small web server on this machine that answers the three
Stripe API calls the app makes (create a Checkout session, read one back,
open the billing portal) the way Stripe's test mode does, and plays
Stripe's part when a family acts on Stripe's own pages: paying, a renewal
that fails, the subscription ending. Each of those sends the app the signed
webhook events Stripe would. The app talks to it over HTTP through its own
Stripe client (academy_plan._stripe), so the request it builds, its key and
its error handling are all exercised, and nothing is mocked inside the app.

The family goes: free trial -> trial over -> paid -> a failed payment ->
cancelled -> paid again, and the app's state is checked at every step: the
workspace's plan in the database, what the owner reads on Settings and the
plan page, and which worlds the learner can open.
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
from test_webapp import AppTestCase  # noqa: E402

from omniarmor_app import academy, academy_plan  # noqa: E402

SECRET_KEY = "sk_test_fake_omniarmor"
WEBHOOK_SECRET = "whsec_fake_omniarmor"
PRICE = "price_test_academy"
DAY = 24 * 3600


class FakeStripe:
    """Stripe in test mode, on 127.0.0.1, holding its objects in memory."""

    def __init__(self, deliver):
        self.deliver_to = deliver          # posts one webhook to the app, returns the response
        self.sessions, self.customers, self.subscriptions = {}, {}, {}
        self.requests = []                 # (method, path, form fields, Authorization header)
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
        assert fields.get("line_items[0][price]") == PRICE, fields
        assert "{CHECKOUT_SESSION_ID}" in fields["success_url"], fields
        session_id = self.next_id("cs")
        session = {
            "id": session_id, "object": "checkout.session", "mode": "subscription", "status": "open",
            "payment_status": "unpaid", "client_reference_id": fields.get("client_reference_id"),
            "metadata": {"org_id": fields.get("metadata[org_id]")}, "customer": fields.get("customer"),
            "customer_email": fields.get("customer_email"), "subscription": None, "created": self.tick(),
            "success_url": fields["success_url"], "cancel_url": fields["cancel_url"],
            "subscription_metadata": {"org_id": fields.get("subscription_data[metadata][org_id]")},
            "url": f"https://checkout.stripe.test/c/pay/{session_id}",
        }
        self.sessions[session_id] = session
        return {k: v for k, v in session.items() if k != "subscription_metadata"}

    # --- What happens on Stripe's own pages, and the webhooks it sends ------------

    def send(self, kind, obj):
        event = {"id": self.next_id("evt"), "object": "event", "type": kind, "created": self.tick(),
                 "data": {"object": dict(obj)}, "livemode": False}
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
        subscription = {"id": self.next_id("sub"), "object": "subscription", "customer": customer,
                        "status": "active", "created": now, "current_period_end": now + 30 * DAY,
                        "cancel_at_period_end": False, "metadata": session["subscription_metadata"]}
        self.subscriptions[subscription["id"]] = subscription
        session.update(status="complete", payment_status="paid", customer=customer,
                       subscription=subscription["id"])
        self.webhooks_for_payment = [("checkout.session.completed", {k: v for k, v in session.items()
                                                                     if k != "subscription_metadata"}),
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

    def end(self, sub_id):
        """Stripe gives up on the card (or the family cancels at once): the subscription ends."""
        subscription = self.subscriptions[sub_id]
        subscription.update(status="canceled", ended_at=self.tick())
        return self.send("customer.subscription.deleted", subscription)


class TestAcademyPlanAgainstFakeStripe(AppTestCase):
    def setUp(self):
        super().setUp()
        self.app.config.update(STRIPE_SECRET_KEY=SECRET_KEY, STRIPE_WEBHOOK_SECRET=WEBHOOK_SECRET,
                               ACADEMY_STRIPE_PRICE=PRICE, ACADEMY_PRICE_LABEL="$9 a month")
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
        response = self.post("/app/academy/learners", {"nickname": "Sam", "avatar": "rocket"})
        self.post(response.headers["Location"], {"track": "trailblazer"})
        with self.db() as conn:
            self.lid = conn.execute("SELECT id FROM learners").fetchone()[0]
            self.org_id = conn.execute("SELECT id FROM orgs").fetchone()[0]
        # Trailblazer's first world: open to play, and only free on the Launchpad track.
        self.paid_world = academy.TRACKS["trailblazer"].topics[0]
        self.assertNotEqual(academy_plan.FREE_TRACK, "trailblazer")

    def webhook(self, payload, signature):
        response = self.stripe_side.post("/billing/stripe/webhook", data=payload,
                                         headers={"Stripe-Signature": signature, "Content-Type": "application/json"})
        self.assertEqual(response.status_code, 200, response.data)
        return response

    # --- What the app shows ---------------------------------------------------------

    def org(self):
        with self.db() as conn:
            return dict(conn.execute("SELECT academy_status, academy_renews_at, academy_ends_at,"
                                     " stripe_customer_id, stripe_subscription_id FROM orgs").fetchone())

    def settings_line(self):
        page = self.client.get("/app/settings").get_data(as_text=True)
        section = page[page.index("<h2>Academy plan</h2>") + len("<h2>Academy plan</h2>"):]
        return " ".join(re.sub(r"<[^>]+>", " ", section[:section.index("</p>")]).split()).replace("&#39;", "'")

    def plan_page(self):
        return self.client.get("/app/academy/plan").get_data(as_text=True)

    def paid_world_opens(self):
        """Whether the learner can open a world outside the free ones, or is
        sent to the plan page instead."""
        response = self.client.get(f"/app/academy/{self.lid}/world/{self.paid_world}")
        if response.status_code == 200:
            return True
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.headers["Location"].endswith("/app/academy/plan"), response.headers["Location"])
        return False

    def free_world_opens(self):
        self.post(f"/app/academy/{self.lid}/track", {"track": "launchpad"})
        opens = self.client.get(f"/app/academy/{self.lid}/world/1").status_code == 200
        self.post(f"/app/academy/{self.lid}/track", {"track": "trailblazer"})
        return opens

    def start_checkout(self):
        """The owner presses "Start the Academy plan" on the plan page."""
        [form] = [f for f in post_forms(self.plan_page()) if f.action == "/app/academy/plan/checkout"]
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
        # 1. The free trial: everything opens, nothing has touched Stripe.
        self.assertEqual(self.org()["academy_status"], "none")
        self.assertRegex(self.settings_line(), r"^Free Academy trial: 14 days left\.")
        self.assertIn("Your free trial is on", self.plan_page())
        self.assertTrue(self.paid_world_opens())
        self.assertEqual(self.stripe.requests, [])

        # 2. The trial ends: only the free worlds open.
        with self.db() as conn:
            conn.execute("UPDATE orgs SET academy_trial_ends = '2000-01-01T00:00:00+00:00'")
            conn.commit()
        self.assertRegex(self.settings_line(), r"^You're on the free Academy\.")
        self.assertIn("Unlock the whole Academy", self.plan_page())
        self.assertFalse(self.paid_world_opens())
        self.assertTrue(self.free_world_opens())

        # 3. Paid. The owner goes to Stripe Checkout and pays; Stripe sends them
        # back before its webhooks arrive, and the plan is on at once.
        first = self.start_checkout()
        method, path, fields, key = self.stripe.requests[-1]
        self.assertEqual((method, path, key), ("POST", "/v1/checkout/sessions", f"Bearer {SECRET_KEY}"))
        self.assertEqual(fields["client_reference_id"], str(self.org_id))
        self.assertEqual(fields["customer_email"], "owner@example.com")
        self.assertNotIn("customer", fields)
        self.assertEqual(self.org()["academy_status"], "none", "nothing changes until Stripe says it's paid")
        page = self.come_back(self.stripe.pay(first))
        self.assertEqual(self.stripe.requests[-1][:2], ("GET", f"/v1/checkout/sessions/{first}"))
        self.assertIn("Thank you! The Academy plan is on for every learner.", flashes(page))
        org = self.org()
        self.assertEqual((org["academy_status"], org["stripe_customer_id"], org["stripe_subscription_id"]),
                         ("active", "cus_test_2", "sub_test_3"))
        self.stripe.send_payment_webhooks()
        org = self.org()
        self.assertEqual((org["academy_status"], org["stripe_subscription_id"]), ("active", "sub_test_3"))
        self.assertIsNotNone(org["academy_renews_at"], "the subscription's period end")
        self.assertIsNone(org["academy_ends_at"])
        self.assertRegex(self.settings_line(), r"^The Academy plan is on and renews ")
        self.assertIn("You have the Academy plan", self.plan_page())
        self.assertNotIn("Start the Academy plan", self.plan_page())
        self.assertTrue(self.paid_world_opens())

        # 4. A renewal fails: the plan is past due, the owner is told to update
        # the card (Stripe's billing portal), and the kids keep everything.
        self.stripe.fail_renewal("sub_test_3")
        self.assertEqual(self.org()["academy_status"], "past_due")
        self.assertRegex(self.settings_line(), r"^Your last Academy payment didn't go through\. Update your card")
        self.assertIn("Update your card to keep access", self.plan_page())
        self.assertTrue(self.paid_world_opens())
        [manage] = [f for f in post_forms(self.plan_page()) if f.action == "/app/academy/plan/manage"]
        response = self.client.post(manage.action, data=manage.values())
        self.assertEqual(response.headers["Location"], "https://billing.stripe.test/p/cus_test_2")
        self.assertEqual(self.stripe.requests[-1][2]["customer"], "cus_test_2")

        # 5. Stripe gives up and the subscription ends: back to the free worlds,
        # with every learner and their progress kept.
        self.post(f"/app/academy/{self.lid}/world/1/stage/1", {"attempt": "1", "check": "0", "choice": "0"})
        self.stripe.end("sub_test_3")
        org = self.org()
        self.assertEqual((org["academy_status"], org["academy_renews_at"]), ("canceled", None))
        self.assertRegex(self.settings_line(), r"^You're on the free Academy\.")
        self.assertIn("Unlock the whole Academy", self.plan_page())
        self.assertIn("Past invoices and billing", self.plan_page())
        self.assertFalse(self.paid_world_opens())
        self.assertTrue(self.free_world_opens())
        with self.db() as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM learners").fetchone()[0], 1)
        # Stripe retries the first payment's events: an ended plan stays ended.
        for event in self.stripe.events[:2]:
            self.stripe.deliver(event)
        self.assertEqual(self.org()["academy_status"], "canceled")
        self.assertFalse(self.paid_world_opens())

        # 6. Resubscribed: the same Stripe customer, a new subscription.
        second = self.start_checkout()
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
        self.assertIn("Thank you! The Academy plan is on for every learner.", flashes(page))
        self.assertRegex(self.settings_line(), r"^The Academy plan is on and renews ")
        self.assertTrue(self.paid_world_opens())
        # The old subscription's late "deleted" event doesn't end the new plan.
        self.stripe.deliver(next(e for e in self.stripe.events if e["type"] == "customer.subscription.deleted"))
        self.assertEqual(self.org()["academy_status"], "active")

    def test_when_stripe_is_down_nothing_changes(self):
        with self.db() as conn:
            conn.execute("UPDATE orgs SET academy_trial_ends = '2000-01-01T00:00:00+00:00'")
            conn.commit()
        self.stripe.down = True
        [form] = [f for f in post_forms(self.plan_page()) if f.action == "/app/academy/plan/checkout"]
        with self.assertLogs("omniarmor_app", "WARNING"):
            response = self.client.post(form.action, data=form.values(), follow_redirects=True)
        self.assertIn("We couldn&#39;t open checkout just now. Please try again in a minute.",
                      flashes(response.get_data(as_text=True)))
        self.assertEqual(len(self.stripe.requests), 1)
        self.assertEqual(self.org()["academy_status"], "none")
        self.assertFalse(self.paid_world_opens())

    def test_a_wrong_secret_key_is_refused_by_stripe(self):
        with self.db() as conn:
            conn.execute("UPDATE orgs SET academy_trial_ends = '2000-01-01T00:00:00+00:00'")
            conn.commit()
        self.app.config["STRIPE_SECRET_KEY"] = "sk_test_wrong"
        with self.assertLogs("omniarmor_app", "WARNING") as logged:
            self.post("/app/academy/plan/checkout")
        self.assertTrue(any("Invalid API Key provided" in line for line in logged.output))
        self.assertNotIn("sk_test_wrong", " ".join(logged.output))
        self.assertEqual(self.org()["academy_status"], "none")


if __name__ == "__main__":
    unittest.main()
