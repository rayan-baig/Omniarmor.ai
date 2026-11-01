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


class TestCancelledPlan(AppTestCase):
    """Stripe's portal cancels at the end of the paid period: the subscription
    stays active until then, with cancel_at_period_end set."""

    def setUp(self):
        super().setUp()
        self.signup()
        self.post("/app/academy/learners", {"nickname": "Sam", "avatar": "rocket"})
        with self.db() as conn:
            self.org_id = conn.execute("SELECT id FROM orgs").fetchone()[0]
            conn.execute("UPDATE orgs SET academy_status = 'active', stripe_customer_id = 'cus_1',"
                         " stripe_subscription_id = 'sub_1'")
            conn.commit()
        self.app.config["STRIPE_WEBHOOK_SECRET"] = "whsec_test"
        self.period_end = 1893456000  # 2030-01-01

    def send(self, event_id, obj):
        import hashlib
        import hmac
        import json
        import time
        event = {"id": event_id, "type": "customer.subscription.updated", "created": int(time.time()),
                 "data": {"object": obj}}
        payload = json.dumps(event).encode()
        stamp = int(time.time())
        sig = hmac.new(b"whsec_test", f"{stamp}.".encode() + payload, hashlib.sha256).hexdigest()
        response = self.app.test_client().post("/billing/stripe/webhook", data=payload,
                                               headers={"Stripe-Signature": f"t={stamp},v1={sig}"})
        self.assertEqual(response.status_code, 200)

    def subscription(self, **extra):
        obj = {"id": "sub_1", "customer": "cus_1", "status": "active", "current_period_end": self.period_end,
               "cancel_at_period_end": False, "cancel_at": None, "metadata": {"org_id": str(self.org_id)}}
        obj.update(extra)
        return obj

    def test_a_cancelled_plan_says_when_it_ends_not_that_it_renews(self):
        self.send("evt_cancel", self.subscription(cancel_at_period_end=True, cancel_at=self.period_end))
        page = self.client.get("/app/academy/plan").data.decode()
        self.assertIn("ends 2030-01-01", page)
        self.assertNotIn("renews", page)

    def test_a_cancelled_plan_no_longer_blocks_deleting_the_workspace(self):
        self.send("evt_cancel", self.subscription(cancel_at_period_end=True, cancel_at=self.period_end))
        self.post("/app/settings/delete", {"confirm": "Acme Logistics"})
        with self.db() as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM orgs").fetchone()[0], 0)

    def test_resuming_the_plan_blocks_deleting_again(self):
        self.send("evt_cancel", self.subscription(cancel_at_period_end=True, cancel_at=self.period_end))
        self.send("evt_resume", self.subscription())
        self.assertIn("renews 2030-01-01", self.client.get("/app/academy/plan").data.decode())
        self.post("/app/settings/delete", {"confirm": "Acme Logistics"})
        with self.db() as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM orgs").fetchone()[0], 1)

    def test_renewal_date_from_newer_stripe_versions(self):
        # Newer Stripe API versions put the period end on the subscription's items.
        obj = self.subscription(items={"data": [{"current_period_end": self.period_end}]})
        del obj["current_period_end"]
        self.send("evt_new_api", obj)
        self.assertIn("renews 2030-01-01", self.client.get("/app/academy/plan").data.decode())


class TestRecordKeepsWhoAfterRemoval(AppTestCase):
    """The Vault is the record an inspector sees: who changed what, and when.
    Removing a team member deletes their account, and their changes used to
    turn into "System" changes."""

    def setUp(self):
        import re
        super().setUp()
        self.signup(industries=(1,))
        self.post("/app/settings/invite")
        page = self.client.get("/app/settings").data.decode()
        token = re.search(r"https://omniarmor\.test/signup\?invite=([\w-]+)", page).group(1)
        self.member = self.app.test_client()
        self.signup(email="member@example.com", client=self.member, invite=token, name="Sam Member")
        self.change(1, "annual_mvr_review", client=self.member, date="2026-01-01")
        with self.db() as conn:
            member_id = conn.execute("SELECT id FROM users WHERE email = 'member@example.com'").fetchone()[0]
        self.post(f"/app/settings/member/{member_id}/remove")

    def test_the_audit_trail_still_names_them(self):
        csv = self.client.get("/app/audit.csv").data.decode()
        self.assertIn("Sam Member", [line for line in csv.splitlines() if "Annual driving record review" in line][0])

    def test_the_report_still_names_them(self):
        csv = self.client.get("/app/report.csv").data.decode()
        self.assertIn("Sam Member", [line for line in csv.splitlines() if "Annual driving record review" in line][0])


class TestInviteForAnExistingAccount(AppTestCase):
    def test_the_message_does_not_send_them_to_sign_in(self):
        import re
        self.signup(industries=(1,))
        self.post("/app/settings/invite")
        token = re.search(r"https://omniarmor\.test/signup\?invite=([\w-]+)",
                          self.client.get("/app/settings").data.decode()).group(1)
        other = self.app.test_client()
        self.post("/signup", {"name": "Lee", "email": "lee@example.com", "password": "correct horse battery",
                              "org_name": "Lee Co", "timezone": "UTC", "industries": ["2"]}, client=other)
        self.post("/logout", client=other)
        response = self.signup(email="lee@example.com", client=other, invite=token, name="Lee")
        page = response.data.decode()
        self.assertEqual(response.status_code, 400)
        # Signing in would only open their own workspace, never this one.
        self.assertNotIn("Sign in instead", page)
        self.assertIn("already has an OmniArmor account", page)
        self.assertIn("Join your team", page)  # the invite is still on the page to try another email


class TestMonthCountedChecks(AppTestCase):
    """Nineteen checks count months or years since something happened. They took
    only a typed number, which never grew: a yearly review entered as
    "3 months" stayed Cleared forever, and no reminder ever went out."""

    def state(self, industry_id, key, value_date, today):
        from datetime import date
        from omniarmor_app.catalog import find_rule
        from omniarmor_app.tracking import compute_state
        row = {"value_num": None, "value_bool": None, "value_date": value_date, "limit_override": None,
               "warn_override": None, "updated_at": None, "updated_by_name": None}
        return compute_state(industry_id, find_rule(industry_id, key), row, date.fromisoformat(today))

    def test_every_month_and_year_check_takes_a_date(self):
        from omni_armor_rules import CATALOG
        from omniarmor_app.catalog import date_mode
        counted = [r.key for rules in CATALOG.values() for r in rules
                   if r.unit in ("months", "years") and " since " in f" {r.input.lower()} "]
        self.assertEqual(len(counted), 19)
        for rules in CATALOG.values():
            for r in rules:
                if r.key in counted:
                    self.assertEqual(date_mode(r), "since", r.key)

    def test_months_count_up_by_themselves(self):
        # The staffing plan must be reviewed every 12 months (warns from 11).
        cases = {"2026-03-14": ("CLEARED", "2026-06-15"), "2026-05-15": ("WARNING", "2026-06-15"),
                 "2026-06-15": ("WARNING", "2026-06-15"), "2026-06-16": ("BLOCKED", "2026-06-15")}
        for today, (level, due) in cases.items():
            s = self.state(16, "prea_staffing_plan_review", "2025-06-15", today)
            self.assertEqual((s.level, s.due_date.isoformat()), (level, due), today)

    def test_calendar_months_run_to_the_end_of_the_month(self):
        # 14 CFR 135.293: a check in June 2025 is good through June 30, 2026.
        s = self.state(4, "pilot_competency_check", "2025-06-10", "2026-06-30")
        self.assertEqual((s.level, s.due_date.isoformat(), s.value), ("WARNING", "2026-06-30", 12))
        self.assertEqual(self.state(4, "pilot_competency_check", "2025-06-10", "2026-07-01").level, "BLOCKED")
        self.assertEqual(self.state(4, "pilot_competency_check", "2025-06-10", "2026-04-30").level, "CLEARED")

    def test_years_count_up_by_themselves(self):
        # Turnout gear retires 10 years after it was made.
        self.assertEqual(self.state(14, "gear_retirement", "2016-11-01", "2026-11-01").level, "WARNING")
        self.assertEqual(self.state(14, "gear_retirement", "2016-11-01", "2026-11-02").level, "BLOCKED")
        self.assertEqual(self.state(14, "gear_retirement", "2020-01-01", "2026-11-01").level, "CLEARED")

    def test_through_the_app_with_done_today_and_a_reminder(self):
        from omniarmor_app.reminders import run_reminders
        self.signup(industries=(24,))
        page = self.client.get("/app/industry/24").data.decode()
        self.assertIn('id="f-security_drill-d"', page)  # the date box
        self.change(24, "security_drill", date="2020-01-01")
        self.assertIn("Blocked", self.client.get("/app/industry/24?only=problems").data.decode())
        with self.db() as conn:
            summary = run_reminders(conn, self.app.config)
        self.assertGreaterEqual(summary["reminders"], 1)
        self.change(24, "security_drill", action="done_today")
        page = self.client.get("/app/industry/24?only=problems").data.decode()
        self.assertNotIn('id="rule-security_drill"', page)

    def test_a_month_limit_is_kept_to_a_real_calendar(self):
        self.signup(industries=(14,))
        self.change(14, "gear_retirement", action="override", limit="5000")
        self.assertIn("between 0 and 100", self.client.get("/app/industry/14").data.decode())


class TestOddAddresses(AppTestCase):
    def test_a_huge_audit_page_number_is_not_a_server_error(self):
        self.signup()
        self.app.config["PROPAGATE_EXCEPTIONS"] = False
        response = self.client.get("/app/audit?page=99999999999999999999")
        self.assertEqual(response.status_code, 200)

    def test_removing_a_huge_member_id_is_not_found(self):
        self.signup()
        self.app.config["PROPAGATE_EXCEPTIONS"] = False
        response = self.post("/app/settings/member/99999999999999999999/remove")
        self.assertEqual(response.status_code, 404)


class TestClocksThatRunFromAStartDate(AppTestCase):
    """The 90- and 180-day hazardous waste accumulation limits and the 14-day
    PRN psychotropic order limit count days from a start date, but their
    questions weren't worded as "days since", so they only took a typed
    number that never grew."""

    def test_they_take_a_date_and_count_up(self):
        from omniarmor_app.catalog import date_mode, find_rule
        for industry_id, key in ((40, "lqg_90_day_limit"), (40, "sqg_180_day_limit"),
                                 (26, "prn_psychotropic_14_days")):
            self.assertEqual(date_mode(find_rule(industry_id, key)), "since", key)
        self.signup(industries=(40,))
        self.change(40, "lqg_90_day_limit", date="2020-01-01")
        page = self.client.get("/app/industry/40?only=problems").data.decode()
        self.assertIn('id="rule-lqg_90_day_limit"', page)
        self.assertIn("days overdue", page)


class TestPracticeGradesTheRightQuestion(AppTestCase):
    """A practice page numbers its answers q0, q1... in the order it was sent.
    If one of its questions stopped being due before the page was handed in
    (answered right in a level meanwhile), the rest shifted up one place and
    each was graded against the answer to the question before it."""

    def test_answers_stay_with_their_questions(self):
        import json
        self.signup()
        response = self.post("/app/academy/learners", {"nickname": "Sam", "avatar": "rocket"})
        self.post(response.headers["Location"], {"track": "launchpad"})
        with self.db() as conn:
            sam = conn.execute("SELECT id FROM learners").fetchone()[0]
            ids = []
            for n, answer in enumerate((0, 1)):
                question = json.dumps({"prompt": f"P{n}?", "options": ["a", "b"], "answer": answer, "explain": "e",
                                       "kind": "choice"})
                ids.append(conn.execute("INSERT INTO learner_mistakes (learner_id, qkey, question, due_at)"
                                        " VALUES (?, ?, ?, '2000-01-01T00:00:00+00:00')",
                                        (sam, f"k{n}", question)).lastrowid)
            # The first one was answered right somewhere else and isn't due any more.
            conn.execute("UPDATE learner_mistakes SET due_at = '2999-01-01T00:00:00+00:00', streak = 1 WHERE id = ?",
                         (ids[0],))
            conn.commit()
        # The page still had both: q0 for the first (answer a), q1 for the second (answer b).
        self.post(f"/app/academy/{sam}/practice", {"deck": f"{ids[0]},{ids[1]}", "q0": "0", "q1": "1"})
        with self.db() as conn:
            streak = conn.execute("SELECT streak FROM learner_mistakes WHERE id = ?", (ids[1],)).fetchone()[0]
        self.assertEqual(streak, 1)  # answered right


class TestSwitchingANumberToADate(AppTestCase):
    """The page fills the number box with a saved typed number, so it comes
    back with every later save. Picking a date next to that unchanged number
    was refused as "a number and a date", so a check saved as a number (every
    month and year check, and the waste and PRN clocks, took only numbers
    until today) could not be switched to a date without emptying the box."""

    def setUp(self):
        super().setUp()
        self.signup(industries=(1,))
        self.change(1, "annual_mvr_review", value="12")

    def reading(self):
        with self.db() as conn:
            return dict(conn.execute("SELECT value_num, value_date FROM items WHERE rule_key = 'annual_mvr_review'")
                        .fetchone())

    def test_a_date_next_to_the_saved_number_is_saved(self):
        self.change(1, "annual_mvr_review", value="12", date="2026-02-01")
        self.assertEqual(self.reading(), {"value_num": None, "value_date": "2026-02-01"})

    def test_a_new_number_and_a_date_together_are_still_refused(self):
        self.change(1, "annual_mvr_review", value="13", date="2026-02-01")
        self.assertEqual(self.reading(), {"value_num": 12.0, "value_date": None})
