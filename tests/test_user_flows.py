"""Bugs a person using the app would hit, each one shown failing before it was fixed."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_webapp import AppTestCase  # noqa: E402


class TestDateCountedReadings(AppTestCase):
    """A date-counted check's form has a number box and a date box. Once a date
    is saved, the page fills the date box with it, so it comes back with every
    later save."""

    def setUp(self):
        super().setUp()
        self.signup(industries=(1,))
        self.change(1, "annual_mvr_review", date="2026-01-01")

    def reading(self):
        with self.db() as conn:
            return dict(conn.execute("SELECT value_num, value_date FROM items WHERE rule_key = 'annual_mvr_review'")
                        .fetchone())

    def test_a_typed_number_replaces_a_saved_date(self):
        # The page sends the saved date back alongside the number just typed.
        self.change(1, "annual_mvr_review", value="12", date="2026-01-01")
        self.assertEqual(self.reading(), {"value_num": 12.0, "value_date": None})

    def test_a_new_date_still_wins(self):
        self.change(1, "annual_mvr_review", value="", date="2026-02-01")
        self.assertEqual(self.reading(), {"value_num": None, "value_date": "2026-02-01"})

    def test_a_number_and_a_new_date_together_are_refused(self):
        response = self.change(1, "annual_mvr_review", value="12", date="2026-02-01")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.reading(), {"value_num": None, "value_date": "2026-01-01"})
        page = self.client.get("/app/industry/1").data.decode()
        self.assertIn("Enter a number or a date, not both", page)


class TestBackFromCheckout(AppTestCase):
    """Stripe sends the family back to the plan page the moment they pay. Its
    webhook can arrive seconds later, or never when it isn't set up right."""

    def setUp(self):
        super().setUp()
        self.signup()
        self.post("/app/academy/learners", {"nickname": "Sam", "avatar": "rocket"})
        self.app.config.update(STRIPE_SECRET_KEY="sk_test", ACADEMY_STRIPE_PRICE="price_1")
        with self.db() as conn:
            self.org_id = conn.execute("SELECT id FROM orgs").fetchone()[0]
            conn.execute("UPDATE orgs SET academy_trial_ends = '2000-01-01T00:00:00+00:00'")  # trial over
            conn.commit()

    def stripe_session(self, org_id=None, **extra):
        session = {"id": "cs_test_1", "object": "checkout.session", "mode": "subscription", "status": "complete",
                   "payment_status": "paid", "client_reference_id": str(org_id or self.org_id),
                   "metadata": {"org_id": str(org_id or self.org_id)}, "customer": "cus_1", "subscription": "sub_1"}
        session.update(extra)
        return session

    def org(self):
        with self.db() as conn:
            return conn.execute("SELECT * FROM orgs").fetchone()

    def test_checkout_asks_stripe_to_send_the_session_back(self):
        from unittest import mock
        from omniarmor_app import academy_plan
        with mock.patch.object(academy_plan, "_stripe", return_value={"url": "https://checkout.stripe.test/x"}) as call:
            response = self.post("/app/academy/plan/checkout")
        self.assertEqual(response.headers["Location"], "https://checkout.stripe.test/x")
        fields = call.call_args[0][2]
        self.assertIn("session_id={CHECKOUT_SESSION_ID}", fields["success_url"])

    def test_paying_turns_the_plan_on_before_the_webhook_arrives(self):
        from unittest import mock
        from omniarmor_app import academy_plan
        with mock.patch.object(academy_plan, "_stripe", return_value=self.stripe_session()) as call:
            response = self.client.get("/app/academy/plan?welcome=1&session_id=cs_test_1", follow_redirects=True)
        self.assertEqual(call.call_args[0][1], "checkout/sessions/cs_test_1")
        org = self.org()
        self.assertEqual((org["academy_status"], org["stripe_customer_id"], org["stripe_subscription_id"]),
                         ("active", "cus_1", "sub_1"))
        page = response.data.decode()
        self.assertIn("You have the Academy plan", page)
        self.assertNotIn("Start the Academy plan", page)

    def test_while_payment_is_being_confirmed_there_is_no_second_checkout_button(self):
        from unittest import mock
        from omniarmor_app import academy_plan
        pending = self.stripe_session(payment_status="unpaid")
        with mock.patch.object(academy_plan, "_stripe", return_value=pending):
            page = self.client.get("/app/academy/plan?welcome=1&session_id=cs_test_1",
                                   follow_redirects=True).data.decode()
        self.assertEqual(self.org()["academy_status"], "none")
        self.assertIn("confirming your payment", page)
        self.assertNotIn("Start the Academy plan", page)

    def test_another_workspaces_checkout_does_not_count(self):
        from unittest import mock
        from omniarmor_app import academy_plan
        with mock.patch.object(academy_plan, "_stripe", return_value=self.stripe_session(org_id=self.org_id + 1)):
            self.client.get("/app/academy/plan?welcome=1&session_id=cs_test_1")
        self.assertEqual(self.org()["academy_status"], "none")

    def test_an_odd_session_id_is_never_sent_to_stripe(self):
        from unittest import mock
        from omniarmor_app import academy_plan
        with mock.patch.object(academy_plan, "_stripe", side_effect=AssertionError("no call")):
            response = self.client.get("/app/academy/plan?welcome=1&session_id=../customers/cus_1",
                                       follow_redirects=True)
        self.assertEqual(response.status_code, 200)


class TestPaidFamiliesCanFindTheirPlan(AppTestCase):
    """Once a family pays, the only links to the plan page (the trial and
    free-plan banners) disappeared, leaving no way to manage or cancel."""

    def setUp(self):
        super().setUp()
        self.signup()
        self.post("/app/academy/learners", {"nickname": "Sam", "avatar": "rocket"})
        with self.db() as conn:
            conn.execute("UPDATE orgs SET academy_status = 'active', stripe_customer_id = 'cus_1',"
                         " stripe_subscription_id = 'sub_1'")
            conn.commit()

    def test_academy_home_links_to_the_plan(self):
        page = self.client.get("/app/academy").data.decode()
        self.assertIn('href="/app/academy/plan"', page)

    def test_settings_links_to_the_plan(self):
        page = self.client.get("/app/settings").data.decode()
        self.assertIn('href="/app/academy/plan"', page)

    def test_a_failed_payment_is_flagged_on_academy_home(self):
        with self.db() as conn:
            conn.execute("UPDATE orgs SET academy_status = 'past_due'")
            conn.commit()
        page = self.client.get("/app/academy").data.decode()
        self.assertIn("last Academy payment didn't go through", page)
