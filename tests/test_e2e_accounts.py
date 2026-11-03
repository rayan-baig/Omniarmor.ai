"""Billing and accounts, end to end.

- A Stripe event sent again, late or out of order can't turn a plan back on.
- A failed payment says "Update your card" and keeps every learner's work.
- Deleting a workspace removes everything the Privacy page says it does.
- Removing a team member ends their session at once.
- Every POST route refuses a request without the form's CSRF token, and
  every POST form on every page carries it.
- Sign-in throttling and password reset links behave.
"""

import hashlib
import hmac
import json
import os
import re
import sys
import time
from datetime import timedelta
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from e2e_helpers import flashes, parse, post_forms  # noqa: E402
from test_webapp import PASSWORD, AppTestCase  # noqa: E402

from omniarmor_app import academy, academy_plan  # noqa: E402
from omniarmor_app.auth import RESET_HOURS  # noqa: E402
from omniarmor_app.catalog import rules_for  # noqa: E402
from omniarmor_app.db import iso, utcnow  # noqa: E402
from omniarmor_app.reminders import run_reminders  # noqa: E402
from omniarmor_app.security import FAILURE_WINDOW, MAX_FAILURES  # noqa: E402

BASIC = academy.TRACKS["launchpad"]


class StripeCase(AppTestCase):
    def setUp(self):
        super().setUp()
        self.signup()
        self.post("/app/academy/learners", {"nickname": "Sam", "avatar": "rocket"})
        self.app.config.update(STRIPE_WEBHOOK_SECRET="whsec_test", STRIPE_SECRET_KEY="sk_test",
                               ACADEMY_STRIPE_PRICE="price_1")
        with self.db() as conn:
            self.org_id = conn.execute("SELECT id FROM orgs").fetchone()[0]
            self.lid = conn.execute("SELECT id FROM learners").fetchone()[0]
            conn.execute("UPDATE orgs SET academy_trial_ends = '2000-01-01T00:00:00+00:00'")  # trial over
            conn.commit()
        self.hook = self.app.test_client()

    def send(self, event_id, kind, obj, created=None, stamp=None):
        event = {"id": event_id, "type": kind, "data": {"object": obj},
                 "created": int(time.time()) if created is None else created}
        payload = json.dumps(event).encode()
        stamp = int(time.time()) if stamp is None else stamp
        sig = hmac.new(b"whsec_test", f"{stamp}.".encode() + payload, hashlib.sha256).hexdigest()
        return self.hook.post("/billing/stripe/webhook", data=payload,
                              headers={"Stripe-Signature": f"t={stamp},v1={sig}"})

    def checkout_event(self, event_id="evt_checkout", sub="sub_1", created=None):
        return self.send(event_id, "checkout.session.completed",
                         {"id": "cs_test_1", "object": "checkout.session", "client_reference_id": str(self.org_id),
                          "metadata": {"org_id": str(self.org_id)}, "customer": "cus_1", "subscription": sub},
                         created)

    def subscription_event(self, event_id, kind, status, sub="sub_1", created=None, **extra):
        obj = {"id": sub, "object": "subscription", "customer": "cus_1", "status": status,
               "metadata": {"org_id": str(self.org_id)}, **extra}
        return self.send(event_id, f"customer.subscription.{kind}", obj, created)

    def org(self):
        with self.db() as conn:
            return conn.execute("SELECT * FROM orgs").fetchone()

    def paid_world_opens(self):
        """Whether a world outside the free ones opens for the learner."""
        with self.db() as conn:
            conn.execute("UPDATE learners SET track = 'trailblazer', track_chosen = 1")
            conn.commit()
        world = next(n for n in academy.TRACKS["trailblazer"].topics if n not in academy_plan.FREE_WORLDS)
        response = self.client.get(f"/app/academy/{self.lid}/world/{world}")
        return response.status_code == 200 or "/plan" not in response.headers.get("Location", "")


class TestStripeCannotDoubleActivate(StripeCase):
    def test_the_same_event_twice_counts_once(self):
        self.assertEqual(self.checkout_event().status_code, 200)
        self.assertEqual(self.org()["academy_status"], "active")
        self.assertEqual(self.subscription_event("evt_deleted", "deleted", "canceled").status_code, 200)
        self.assertEqual(self.org()["academy_status"], "canceled")
        # Stripe delivers the checkout event again, freshly signed.
        self.assertEqual(self.checkout_event().status_code, 200)
        self.assertEqual(self.org()["academy_status"], "canceled")
        with self.db() as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM stripe_events").fetchone()[0], 2)

    def test_an_old_signature_is_refused(self):
        response = self.checkout_event()
        self.assertEqual(response.status_code, 200)
        stale = int(time.time()) - academy_plan.WEBHOOK_TOLERANCE - 60
        response = self.send("evt_other", "checkout.session.completed",
                             {"client_reference_id": str(self.org_id), "customer": "cus_1", "subscription": "sub_9"},
                             stamp=stale)
        self.assertEqual(response.status_code, 400)

    def test_a_late_checkout_does_not_bring_a_cancelled_plan_back(self):
        """The first delivery of the checkout event failed (the server was
        restarting), so it was never recorded; the family came back from
        Stripe and the plan went on anyway. They cancelled. Stripe retries
        the old checkout event for days: it must not switch the plan on."""
        now = int(time.time())
        with mock.patch.object(academy_plan, "_stripe", return_value={
                "id": "cs_test_1", "mode": "subscription", "status": "complete", "payment_status": "paid",
                "client_reference_id": str(self.org_id), "metadata": {"org_id": str(self.org_id)},
                "customer": "cus_1", "subscription": "sub_1", "created": now - 120}):
            self.client.get("/app/academy/plan?welcome=1&session_id=cs_test_1")
        self.assertEqual(self.org()["academy_status"], "active")
        self.subscription_event("evt_deleted", "deleted", "canceled", created=now)
        self.assertEqual(self.org()["academy_status"], "canceled")
        self.checkout_event(created=now - 100)
        self.assertEqual(self.org()["academy_status"], "canceled")
        self.assertFalse(self.paid_world_opens())

    def test_the_old_thank_you_link_does_not_bring_a_cancelled_plan_back(self):
        """The page Stripe sends a family back to holds the checkout session.
        Opening it again after cancelling (history, a bookmark) asked Stripe
        about that session, saw it paid, and switched the plan on for free."""
        now = int(time.time())
        paid_session = {"id": "cs_test_1", "mode": "subscription", "status": "complete", "payment_status": "paid",
                        "client_reference_id": str(self.org_id), "metadata": {"org_id": str(self.org_id)},
                        "customer": "cus_1", "subscription": "sub_1", "created": now - 7200}
        self.checkout_event(created=now - 7100)
        self.subscription_event("evt_deleted", "deleted", "canceled", created=now - 60)
        self.assertEqual(self.org()["academy_status"], "canceled")
        with mock.patch.object(academy_plan, "_stripe", return_value=paid_session):
            page = self.client.get("/app/academy/plan?welcome=1&session_id=cs_test_1", follow_redirects=True)
        self.assertEqual(self.org()["academy_status"], "canceled")
        self.assertNotIn("Thank you! The Academy plan is on", page.data.decode())

    def test_an_old_session_from_an_earlier_plan_does_not_count_either(self):
        now = int(time.time())
        self.checkout_event("evt_c1", sub="sub_1", created=now - 9000)
        self.subscription_event("evt_d1", "deleted", "canceled", sub="sub_1", created=now - 8000)
        self.checkout_event("evt_c2", sub="sub_2", created=now - 7000)
        self.subscription_event("evt_d2", "deleted", "canceled", sub="sub_2", created=now - 60)
        old = {"id": "cs_old", "mode": "subscription", "status": "complete", "payment_status": "paid",
               "client_reference_id": str(self.org_id), "metadata": {"org_id": str(self.org_id)},
               "customer": "cus_1", "subscription": "sub_1", "created": now - 9100}
        with mock.patch.object(academy_plan, "_stripe", return_value=old):
            self.client.get("/app/academy/plan?welcome=1&session_id=cs_old")
        self.assertEqual(self.org()["academy_status"], "canceled")

    def test_a_new_checkout_after_cancelling_does_turn_it_on(self):
        now = int(time.time())
        self.checkout_event("evt_c1", sub="sub_1", created=now - 9000)
        self.subscription_event("evt_d1", "deleted", "canceled", sub="sub_1", created=now - 8000)
        self.checkout_event("evt_c2", sub="sub_2", created=now - 10)
        org = self.org()
        self.assertEqual((org["academy_status"], org["stripe_subscription_id"]), ("active", "sub_2"))
        # And coming back from that checkout works too.
        self.subscription_event("evt_d2", "deleted", "canceled", sub="sub_2", created=now - 5)
        fresh = {"id": "cs_new", "mode": "subscription", "status": "complete", "payment_status": "paid",
                 "client_reference_id": str(self.org_id), "metadata": {"org_id": str(self.org_id)},
                 "customer": "cus_1", "subscription": "sub_3", "created": now}
        with mock.patch.object(academy_plan, "_stripe", return_value=fresh):
            self.client.get("/app/academy/plan?welcome=1&session_id=cs_new")
        self.assertEqual(self.org()["academy_status"], "active")

    def test_webhook_and_return_page_together_make_one_plan(self):
        now = int(time.time())
        session = {"id": "cs_test_1", "mode": "subscription", "status": "complete", "payment_status": "paid",
                   "client_reference_id": str(self.org_id), "metadata": {"org_id": str(self.org_id)},
                   "customer": "cus_1", "subscription": "sub_1", "created": now - 30}
        with mock.patch.object(academy_plan, "_stripe", return_value=session):
            self.client.get("/app/academy/plan?welcome=1&session_id=cs_test_1")
        self.checkout_event(created=now - 5)
        self.subscription_event("evt_created", "created", "active", created=now - 4)
        org = self.org()
        self.assertEqual((org["academy_status"], org["stripe_subscription_id"], org["stripe_customer_id"]),
                         ("active", "sub_1", "cus_1"))
        # No second checkout is offered.
        page = self.client.get("/app/academy/plan").data.decode()
        self.assertNotIn("Start the Academy plan", page)
        with mock.patch.object(academy_plan, "checkout_url", side_effect=AssertionError("no second checkout")):
            self.post("/app/academy/plan/checkout")

    def test_a_late_checkout_does_not_hide_a_failed_payment(self):
        now = int(time.time())
        self.subscription_event("evt_created", "created", "active", created=now - 50)
        self.send("evt_failed", "invoice.payment_failed",
                  {"id": "in_1", "customer": "cus_1", "subscription": "sub_1",
                   "metadata": {"org_id": str(self.org_id)}}, created=now - 10)
        self.assertEqual(self.org()["academy_status"], "past_due")
        self.checkout_event(created=now - 60)
        self.assertEqual(self.org()["academy_status"], "past_due")


class TestFailedPayment(StripeCase):
    def setUp(self):
        super().setUp()
        self.checkout_event()
        self.subscription_event("evt_created", "created", "active", current_period_end=1893456000)
        # Sam has done some work.
        with self.db() as conn:
            conn.execute("UPDATE learners SET track_chosen = 1")
            conn.execute("INSERT INTO learner_progress (learner_id, level, attempts, best_score, best_stars,"
                         " completed_at) VALUES (?, ?, 1, 5, 3, '2026-01-01T00:00:00')",
                         (self.lid, academy.level_id(BASIC, 1, 1)))
            conn.commit()

    def fail_payment(self):
        response = self.send("evt_failed", "invoice.payment_failed",
                             {"id": "in_1", "object": "invoice", "customer": "cus_1", "subscription": "sub_1",
                              "metadata": {"org_id": str(self.org_id)}})
        self.assertEqual(response.status_code, 200)

    def test_it_says_update_your_card_everywhere_a_grown_up_looks(self):
        self.fail_payment()
        self.assertEqual(self.org()["academy_status"], "past_due")
        home = self.client.get("/app/academy").data.decode()
        self.assertIn("Update your card", home)
        self.assertRegex(home, r'payment didn.t go through\. <a href="/app/academy/plan">Update your card</a>')
        self.assertIn("Update your card", self.client.get("/app/settings").data.decode())
        plan = self.client.get("/app/academy/plan").data.decode()
        self.assertIn("Update your card", plan)
        # The owner can get to Stripe's billing page to change the card.
        manage = [f for f in post_forms(plan) if f.action == "/app/academy/plan/manage"]
        self.assertEqual(len(manage), 1)
        with mock.patch.object(academy_plan, "_stripe", return_value={"url": "https://billing.stripe.test/p"}):
            response = self.client.post(manage[0].action, data=manage[0].values())
        self.assertEqual(response.headers["Location"], "https://billing.stripe.test/p")

    def test_it_keeps_every_learner_and_their_progress(self):
        self.fail_payment()
        with self.db() as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM learners").fetchone()[0], 1)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM learner_progress").fetchone()[0], 1)
        self.assertTrue(self.paid_world_opens(), "access stays on while Stripe retries the card")
        page = self.client.get(f"/app/academy/{self.lid}").data.decode()
        self.assertIn("Sam", page)
        # Stripe gives up and cancels: the plan ends, the work stays.
        self.subscription_event("evt_gone", "deleted", "canceled", created=int(time.time()) + 1)
        with self.db() as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM learner_progress").fetchone()[0], 1)
        self.assertEqual(self.client.get(f"/app/academy/{self.lid}").status_code, 200)

    def test_paying_again_clears_the_warning(self):
        self.fail_payment()
        self.subscription_event("evt_paid", "updated", "active", created=int(time.time()) + 1,
                                current_period_end=1893456000)
        self.assertNotIn("Update your card", self.client.get("/app/academy").data.decode())
        self.assertNotIn("Update your card", self.client.get("/app/settings").data.decode())


class TestDeletingAWorkspace(AppTestCase):
    """The Privacy page: deleting "deletes the company, every reading, the
    audit trail, the reminder log, every kid's Academy profile and every team
    account that isn't in another workspace"."""

    # Tables that are not about any one workspace, and what the Privacy page says of them.
    NOT_WORKSPACE_DATA = {
        "schema_version": "the database's own version",
        "login_failures": "wrong password tries, resets, sign-ups and join code tries: deleted within 2 days",
        "job_runs": "when the daily job ran",
        "autopilot_events": "the operator's health checks",
        "app_errors": "error reports, kept 30 days",
        "stripe_events": "Stripe event ids already handled (no longer tied to the workspace)",
    }

    def fill_workspace(self):
        self.signup(industries=(1, 18))
        self.change(1, "annual_mvr_review", date="2026-01-01")
        self.change(1, "hos_11_hour", value="12")
        # A teammate, an open invite and a reset link.
        self.post("/app/settings/invite")
        token = re.search(r"invite=([\w-]+)", self.client.get("/app/settings").data.decode()).group(1)
        self.member = self.app.test_client()
        self.signup(email="member@example.com", client=self.member, invite=token, name="Sam Member")
        self.post("/app/settings/invite")
        self.post("/forgot", {"email": "member@example.com"}, client=self.app.test_client())
        # Reminder emails (the reminder log).
        with self.db() as conn:
            conn.execute("UPDATE items SET value_date = '2020-01-01' WHERE rule_key = 'annual_mvr_review'")
            conn.commit()
            run_reminders(conn, self.app.config)
        # Two kids, friends, a duel, practice, a join code and a friend code.
        for name in ("Ava", "Ben"):
            response = self.post("/app/academy/learners", {"nickname": name, "avatar": "rocket"})
            self.post(response.headers["Location"], {"track": "launchpad"})
        with self.db() as conn:
            ava, ben = [r[0] for r in conn.execute("SELECT id FROM learners ORDER BY id")]
        questions = academy.quiz(BASIC, 1, 1, "Acme Logistics", [1, 18], academy.attempt_seed(ava, "launchpad", 1, 1, 1))
        self.post(f"/app/academy/{ava}/world/1/stage/1", {"attempt": "1", "check": "0", "choice": "0"})
        self.post(f"/app/academy/{ava}/world/1/stage/1",
                  {"attempt": "1", **{f"q{i}": str((q.answer + 1) % len(q.options)) for i, q in enumerate(questions)}})
        self.post(f"/app/academy/{ben}/world/1/stage/1", {"attempt": "1", "check": "0", "choice": "0"})
        self.post(f"/app/academy/{ava}/friends/code")
        with self.db() as conn:
            code = conn.execute("SELECT code FROM friend_codes").fetchone()[0]
        self.post(f"/app/academy/{ben}/friends/add", {"code": code})
        self.post(f"/app/academy/{ava}/friends/code")
        self.post(f"/app/academy/{ava}/duels", {"friend": str(ben), "world": "2"})
        self.post(f"/app/academy/{ben}/join-code")
        self.kid = self.app.test_client()
        self.kid.get("/kids")
        with self.db() as conn:
            kid_code = conn.execute("SELECT code FROM join_codes").fetchone()[0]
        self.post("/kids", {"code": kid_code}, client=self.kid)
        self.post(f"/app/academy/{ben}/join-code")
        return ava, ben

    def counts(self):
        with self.db() as conn:
            tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'"
                                                 " AND name NOT LIKE 'sqlite_%'")]
            return {t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in tables}

    def test_everything_the_privacy_page_lists_is_gone(self):
        self.fill_workspace()
        before = self.counts()
        # The test really put something in each kind of data the page lists.
        for table in ("orgs", "users", "memberships", "org_industries", "items", "audit", "notifications",
                      "reminder_marks", "invites", "password_resets", "learners", "learner_progress",
                      "learner_mistakes", "learner_days", "learner_friends", "friend_codes", "join_codes", "duels",
                      "quiz_checks"):
            self.assertGreater(before.get(table, 0), 0, table)
        self.assertEqual(self.kid.get("/kids").status_code, 302)  # the kid's device is signed in
        page = self.client.get("/app/settings").data.decode()
        form = next(f for f in post_forms(page) if f.action == "/app/settings/delete")
        data = form.values()
        data["confirm"] = "Acme Logistics"
        response = self.client.post(form.action, data=data, follow_redirects=True)
        self.assertIn("Your workspace and its data were deleted.", flashes(response.data.decode()))
        after = self.counts()
        left = {t: n for t, n in after.items() if n and t not in self.NOT_WORKSPACE_DATA}
        self.assertEqual(left, {}, "every table about the workspace is empty")
        self.assertFalse(set(after) - set(before), "no new tables appeared")
        with self.db() as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM stripe_events WHERE org_id IS NOT NULL").fetchone()[0], 0)
        # Nobody is still signed in to it: the owner, the teammate or the kid.
        for client in (self.client, self.member):
            self.assertIn("/login", client.get("/app").headers["Location"])
        self.assertEqual(self.kid.get("/kids").status_code, 200)
        # The accounts are gone: signing in fails, signing up again works.
        response = self.post("/login", {"email": "member@example.com", "password": PASSWORD},
                             client=self.app.test_client())
        self.assertEqual(response.status_code, 401)

    def test_another_workspace_is_untouched(self):
        other = self.app.test_client()
        self.signup(email="other@example.com", client=other, industries=(2,))
        self.change(2, next(r.key for r in rules_for(2) if r.kind == "required"), client=other, answer="yes")
        self.fill_workspace()
        with self.db() as conn:
            mine = conn.execute("SELECT COUNT(*) FROM items WHERE org_id = (SELECT org_id FROM memberships"
                                " JOIN users ON users.id = memberships.user_id WHERE email = 'other@example.com')"
                                ).fetchone()[0]
        self.post("/app/settings/delete", {"confirm": "Acme Logistics"})
        self.assertEqual(other.get("/app").status_code, 200)
        with self.db() as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM orgs").fetchone()[0], 1)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM items").fetchone()[0], mine)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM users").fetchone()[0], 1)


class TestRemovingAMember(AppTestCase):
    def setUp(self):
        super().setUp()
        self.signup(industries=(1,))
        self.post("/app/settings/invite")
        token = re.search(r"invite=([\w-]+)", self.client.get("/app/settings").data.decode()).group(1)
        self.member = self.app.test_client()
        self.signup(email="member@example.com", client=self.member, invite=token, name="Sam Member")
        self.phone = self.app.test_client()   # the same person on a second device
        self.post("/login", {"email": "member@example.com", "password": PASSWORD}, client=self.phone)
        with self.db() as conn:
            self.member_id = conn.execute("SELECT id FROM users WHERE email = 'member@example.com'").fetchone()[0]

    def test_their_very_next_request_is_signed_out_on_every_device(self):
        page = self.member.get("/app/industry/1").data.decode()   # a form open in their browser
        form = next(f for f in post_forms(page) if f.section == "rule-annual_mvr_review" and f.field("value"))
        self.assertEqual(self.phone.get("/app").status_code, 200)
        settings = self.client.get("/app/settings").data.decode()
        remove = next(f for f in post_forms(settings) if f.action == f"/app/settings/member/{self.member_id}/remove")
        response = self.client.post(remove.action, data=remove.values(), follow_redirects=True)
        self.assertIn("Sam Member was removed and signed out.", flashes(response.data.decode()))
        for device in (self.member, self.phone):
            self.assertIn("/login", device.get("/app").headers["Location"])
            self.assertIn("/login", device.get("/app/report.csv").headers["Location"])
        # The form they had open saves nothing now.
        data = form.values()
        data.update(action="save", date="2026-01-01")
        response = self.member.post(form.action, data=data)
        self.assertNotEqual(response.status_code, 200)
        with self.db() as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM items").fetchone()[0], 0)
            self.assertIsNone(conn.execute("SELECT 1 FROM users WHERE id = ?", (self.member_id,)).fetchone())
        # And they can't sign back in.
        self.assertEqual(self.post("/login", {"email": "member@example.com", "password": PASSWORD},
                                   client=self.app.test_client()).status_code, 401)

    def test_a_member_cannot_remove_anyone(self):
        with self.db() as conn:
            owner_id = conn.execute("SELECT id FROM users WHERE email = 'owner@example.com'").fetchone()[0]
        self.assertEqual(self.post(f"/app/settings/member/{owner_id}/remove", client=self.member).status_code, 403)
        self.assertEqual(self.client.get("/app").status_code, 200)


class TestCsrfEverywhere(AppTestCase):
    def setUp(self):
        super().setUp()
        self.signup(industries=(1,))
        self.post("/app/academy/learners", {"nickname": "Sam", "avatar": "rocket", "track": "launchpad"})
        with self.db() as conn:
            self.lid = conn.execute("SELECT id FROM learners").fetchone()[0]
            self.uid = conn.execute("SELECT id FROM users").fetchone()[0]

    def snapshot(self):
        with self.db() as conn:
            tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'"
                                                 " AND name NOT LIKE 'sqlite_%' AND name != 'login_failures'")]
            return {t: conn.execute(f"SELECT * FROM {t} ORDER BY rowid").fetchall() for t in tables}

    def url(self, rule):
        values = {"learner_id": self.lid, "industry_id": 1, "rule_key": "annual_mvr_review", "user_id": self.uid,
                  "world_number": 1, "stage": 1, "duel_id": 1, "friend_id": self.lid, "token": "x"}
        url = rule.rule
        for arg in rule.arguments:
            url = re.sub(rf"<(?:\w+:)?{arg}>", str(values[arg]), url)
        return url

    def test_every_post_route_refuses_a_missing_or_wrong_token(self):
        before = self.snapshot()
        routes = [r for r in self.app.url_map.iter_rules() if "POST" in r.methods]
        self.assertGreater(len(routes), 25)
        tried = 0
        for rule in routes:
            if rule.endpoint == "plan.stripe_webhook":
                continue    # signed by Stripe instead; checked below
            url = self.url(rule)
            fields = {"action": "save", "date": "2026-01-01", "confirm": "Acme Logistics", "name": "Evil",
                      "timezone": "UTC", "industries": "2", "nickname": "Evil", "avatar": "rocket",
                      "email": "owner@example.com", "password": "a brand new password", "personality": "snark",
                      "code": "KID-ABCDEFGH", "track": "titan", "email_reminders": "on", "org_name": "Evil Co"}
            for token in (None, "", "wrong-token"):
                data = dict(fields)
                if token is not None:
                    data["csrf_token"] = token
                response = self.client.post(url, data=data)
                self.assertEqual(response.status_code, 400, (url, token))
                self.assertIn(b"This form expired", response.data, url)
                tried += 1
            # Another site's form, signed out: refused too.
            response = self.app.test_client().post(url, data=fields)
            self.assertEqual(response.status_code, 400, url)
        self.assertEqual(self.snapshot(), before, "no refused request changed anything")
        self.assertEqual(self.client.get("/app").status_code, 200, "still signed in")
        self.assertGreater(tried, 75)
        # The webhook takes no form token, only Stripe's signature.
        self.app.config["STRIPE_WEBHOOK_SECRET"] = "whsec_test"
        self.assertEqual(self.client.post("/billing/stripe/webhook", data=b"{}").status_code, 400)

    def test_every_post_form_on_every_page_carries_the_token(self):
        with self.client.session_transaction() as s:
            token = s["_csrf"]
        pages = ["/app", "/app/industry/1", "/app/settings", "/app/armo", "/app/audit", "/app/report",
                 "/app/notifications", "/app/academy", f"/app/academy/{self.lid}", f"/app/academy/{self.lid}/track",
                 f"/app/academy/{self.lid}/world/1/stage/1", f"/app/academy/{self.lid}/friends",
                 f"/app/academy/{self.lid}/practice", "/app/academy/plan"]
        found = 0
        for path in pages:
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200, path)
            for form in post_forms(response.data.decode()):
                self.assertEqual((form.field("csrf_token") or {}).get("value"), token, (path, form.action))
                found += 1
        anon = self.app.test_client()
        for path in ["/login", "/signup", "/forgot", "/kids"]:
            page = anon.get(path).data.decode()
            with anon.session_transaction() as s:
                anon_token = s["_csrf"]
            forms = post_forms(page)
            self.assertTrue(forms, path)
            for form in forms:
                self.assertEqual((form.field("csrf_token") or {}).get("value"), anon_token, (path, form.action))
                found += 1
        self.assertGreater(found, 30)
        # Every POST route has a form somewhere, or is driven by script with the token.
        actions = set()
        for path in pages:
            actions |= {re.sub(r"\d+", "N", f.action) for f in post_forms(self.client.get(path).data.decode())}
        self.assertIn("/app/industry/N/rule/annual_mvr_review", actions)
        self.assertIn("/app/settings/delete", actions)


class TestSignInThrottling(AppTestCase):
    def setUp(self):
        super().setUp()
        self.signup()
        self.post("/logout")

    def login(self, email="owner@example.com", password=PASSWORD, ip="198.51.100.1"):
        client = self.app.test_client()
        client.environ_base["REMOTE_ADDR"] = ip
        return self.post("/login", {"email": email, "password": password}, client=client)

    def test_five_wrong_tries_stop_that_place_even_with_the_right_password(self):
        for _ in range(MAX_FAILURES):
            self.assertEqual(self.login(password="wrong password").status_code, 401)
        response = self.login()
        self.assertEqual(response.status_code, 429)
        self.assertIn("Too many sign-in attempts", response.data.decode())
        # Shouting the address doesn't get around it.
        self.assertEqual(self.login(email="  OWNER@Example.com ").status_code, 429)
        # The owner, signing in from somewhere else, is not locked out by someone guessing.
        self.assertEqual(self.login(ip="203.0.113.9").status_code, 302)

    def test_a_right_password_resets_the_count(self):
        for _ in range(MAX_FAILURES - 1):
            self.login(password="wrong password")
        self.assertEqual(self.login().status_code, 302)
        for _ in range(MAX_FAILURES - 1):
            self.login(password="wrong password")
        self.assertEqual(self.login().status_code, 302)

    def test_one_place_guessing_many_addresses_is_stopped(self):
        for n in range(MAX_FAILURES * 4):
            self.login(email=f"guess{n}@example.com", password="wrong password")
        self.assertEqual(self.login().status_code, 429)
        self.assertEqual(self.login(ip="203.0.113.9").status_code, 302)

    def test_the_lock_lifts_after_the_window(self):
        for _ in range(MAX_FAILURES):
            self.login(password="wrong password")
        self.assertEqual(self.login().status_code, 429)
        with self.db() as conn:
            conn.execute("UPDATE login_failures SET at = ?", (iso(utcnow() - FAILURE_WINDOW - timedelta(seconds=5)),))
            conn.commit()
        self.assertEqual(self.login().status_code, 302)

    def test_the_answer_never_says_whether_an_address_has_an_account(self):
        wrong = self.login(password="wrong password").data.decode()
        nobody = self.login(email="nobody@example.com", password="wrong password").data.decode()
        self.assertIn("don&#39;t match an account", wrong)
        self.assertEqual(flashes(wrong), flashes(nobody))


class TestResetLinks(AppTestCase):
    def setUp(self):
        super().setUp()
        self.signup()
        self.anon = self.app.test_client()

    def request_link(self, email="owner@example.com"):
        self.post("/forgot", {"email": email}, client=self.anon)
        with self.db() as conn:
            row = conn.execute("SELECT body FROM notifications WHERE kind = 'password_reset' ORDER BY id DESC").fetchone()
        return re.search(r"https://omniarmor\.test(/reset/\S+)", row["body"]).group(1)

    def reset(self, link, password="a brand new password", client=None):
        client = client or self.app.test_client()
        page = client.get(link)
        if page.status_code != 200:
            return page
        form = next(f for f in post_forms(page.data.decode()) if f.field("password") is not None)
        data = form.values()
        data["password"] = password
        return client.post(form.action or link, data=data)

    def can_sign_in(self, password):
        return self.post("/login", {"email": "owner@example.com", "password": password},
                         client=self.app.test_client()).status_code == 302

    def test_a_link_works_once_and_signs_out_every_other_device(self):
        link = self.request_link()
        self.assertEqual(self.client.get("/app").status_code, 200)
        response = self.reset(link)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.headers["Location"].endswith("/app"))
        self.assertIn("/login", self.client.get("/app").headers["Location"])
        self.assertTrue(self.can_sign_in("a brand new password"))
        self.assertFalse(self.can_sign_in(PASSWORD))
        again = self.reset(link, password="yet another password")
        self.assertTrue(again.headers["Location"].endswith("/forgot"))
        self.assertTrue(self.can_sign_in("a brand new password"))

    def test_using_one_link_ends_the_others(self):
        first = self.request_link()
        second = self.request_link()
        self.assertNotEqual(first, second)
        self.assertEqual(self.reset(second).status_code, 302)
        self.assertTrue(self.reset(first, password="yet another password").headers["Location"].endswith("/forgot"))

    def test_a_link_expires(self):
        link = self.request_link()
        with self.db() as conn:
            row = conn.execute("SELECT created_at, expires_at FROM password_resets").fetchone()
            span = academy_plan._parse(row["expires_at"]) - academy_plan._parse(row["created_at"])
            self.assertEqual(span, timedelta(hours=RESET_HOURS))
            conn.execute("UPDATE password_resets SET expires_at = ?", (iso(utcnow() - timedelta(seconds=1)),))
            conn.commit()
        response = self.reset(link)
        self.assertTrue(response.headers["Location"].endswith("/forgot"))
        self.assertTrue(self.can_sign_in(PASSWORD))
        page = self.app.test_client().get(link, follow_redirects=True).data.decode()
        self.assertIn("That reset link has expired or was already used.", page)

    def test_a_made_up_link_does_nothing(self):
        self.request_link()
        response = self.reset("/reset/not-a-real-token")
        self.assertTrue(response.headers["Location"].endswith("/forgot"))
        self.assertTrue(self.can_sign_in(PASSWORD))

    def test_a_reset_lifts_a_lockout(self):
        for _ in range(MAX_FAILURES):
            self.post("/login", {"email": "owner@example.com", "password": "wrong password"}, client=self.anon)
        self.assertEqual(self.post("/login", {"email": "owner@example.com", "password": PASSWORD},
                                   client=self.anon).status_code, 429)
        link = self.request_link()
        self.assertEqual(self.reset(link, client=self.anon).status_code, 302)
        self.post("/logout", client=self.anon)
        self.assertEqual(self.post("/login", {"email": "owner@example.com", "password": "a brand new password"},
                                   client=self.anon).status_code, 302)

    def test_a_removed_members_link_stops_working(self):
        self.post("/app/settings/invite")
        token = re.search(r"invite=([\w-]+)", self.client.get("/app/settings").data.decode()).group(1)
        member = self.app.test_client()
        self.signup(email="member@example.com", client=member, invite=token, name="Sam Member")
        link = self.request_link("member@example.com")
        with self.db() as conn:
            member_id = conn.execute("SELECT id FROM users WHERE email = 'member@example.com'").fetchone()[0]
        self.post(f"/app/settings/member/{member_id}/remove")
        self.assertTrue(self.reset(link).headers["Location"].endswith("/forgot"))

    def test_the_forgot_page_answers_the_same_for_anyone(self):
        known = self.post("/forgot", {"email": "owner@example.com"}, client=self.anon, follow_redirects=True)
        unknown = self.post("/forgot", {"email": "nobody@example.com"}, client=self.app.test_client(),
                            follow_redirects=True)
        self.assertEqual(flashes(known.data.decode()), flashes(unknown.data.decode()))
        self.assertTrue(parse(known.data.decode()).forms)
