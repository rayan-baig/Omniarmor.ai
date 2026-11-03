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
        # 2030-01-01 00:00 UTC, which is 7 pm on 31 December in New York, the
        # workspace's time zone: pages show the workspace's date.
        self.period_end = 1893456000

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
        self.assertIn("ends 2029-12-31", page)
        self.assertNotIn("renews", page)

    def test_a_cancelled_plan_no_longer_blocks_deleting_the_workspace(self):
        self.send("evt_cancel", self.subscription(cancel_at_period_end=True, cancel_at=self.period_end))
        self.post("/app/settings/delete", {"confirm": "Acme Logistics"})
        with self.db() as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM orgs").fetchone()[0], 0)

    def test_resuming_the_plan_blocks_deleting_again(self):
        self.send("evt_cancel", self.subscription(cancel_at_period_end=True, cancel_at=self.period_end))
        self.send("evt_resume", self.subscription())
        self.assertIn("renews 2029-12-31", self.client.get("/app/academy/plan").data.decode())
        self.post("/app/settings/delete", {"confirm": "Acme Logistics"})
        with self.db() as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM orgs").fetchone()[0], 1)

    def test_renewal_date_from_newer_stripe_versions(self):
        # Newer Stripe API versions put the period end on the subscription's items.
        obj = self.subscription(items={"data": [{"current_period_end": self.period_end}]})
        del obj["current_period_end"]
        self.send("evt_new_api", obj)
        self.assertIn("renews 2029-12-31", self.client.get("/app/academy/plan").data.decode())


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
        self.post("/app/academy/learners", {"nickname": "Sam", "avatar": "rocket", "track": "launchpad"})
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


class TestReadyToEatFoodSevenDays(AppTestCase):
    """FDA Food Code 3-501.17(A): ready-to-eat TCS food held cold may be kept
    at most 7 days, counting the day it was prepared or opened as day 1. The
    check took only a typed number that never grew, so food entered on day 2
    stayed Cleared all week and past it."""

    def state(self, value_date, today):
        from datetime import date
        from omniarmor_app.catalog import find_rule
        from omniarmor_app.tracking import compute_state
        row = {"value_num": None, "value_bool": None, "value_date": value_date, "limit_override": None,
               "warn_override": None, "updated_at": None, "updated_by_name": None}
        return compute_state(2, find_rule(2, "date_marking"), row, date.fromisoformat(today))

    def test_it_takes_a_date(self):
        from omniarmor_app.catalog import date_mode, find_rule
        self.assertEqual(date_mode(find_rule(2, "date_marking")), "since")

    def test_the_prep_day_is_day_one(self):
        # Prepared on Monday 2 November: day 1. Day 7 is Sunday 8 November, the last day.
        cases = {"2026-11-02": (1, "CLEARED"), "2026-11-06": (5, "CLEARED"), "2026-11-07": (6, "WARNING"),
                 "2026-11-08": (7, "WARNING"), "2026-11-09": (8, "BLOCKED")}
        for today, (day, level) in cases.items():
            s = self.state("2026-11-02", today)
            self.assertEqual((s.value, s.level), (day, level), today)
            self.assertEqual(s.due_date.isoformat(), "2026-11-08")
            self.assertEqual(s.warn_date.isoformat(), "2026-11-07")

    def test_through_the_app(self):
        from datetime import timedelta
        from omniarmor_app.tracking import org_today
        self.signup(industries=(2,))
        with self.db() as conn:
            today = org_today(conn.execute("SELECT * FROM orgs").fetchone())
        self.change(2, "date_marking", date=(today - timedelta(days=6)).isoformat())  # today is day 7
        page = self.client.get("/app/industry/2").data.decode()
        self.assertIn("Due today", page)
        self.change(2, "date_marking", date=(today - timedelta(days=7)).isoformat())  # today is day 8
        page = self.client.get("/app/industry/2?only=problems").data.decode()
        self.assertIn('id="rule-date_marking"', page)
        self.assertIn("1 day overdue", page)


class TestBillingHistoryAfterThePlanEnds(AppTestCase):
    """Once a cancelled plan ran out, the plan page offered only a new
    checkout: the owner had no way back to Stripe's billing page for past
    invoices and receipts, or to fix the card on a plan Stripe gave up on."""

    def setUp(self):
        super().setUp()
        self.signup()
        self.post("/app/academy/learners", {"nickname": "Sam", "avatar": "rocket"})
        self.app.config.update(STRIPE_SECRET_KEY="sk_test", ACADEMY_STRIPE_PRICE="price_1")
        with self.db() as conn:
            conn.execute("UPDATE orgs SET academy_status = 'canceled', stripe_customer_id = 'cus_1',"
                         " stripe_subscription_id = 'sub_1', academy_trial_ends = '2000-01-01T00:00:00+00:00'")
            conn.commit()

    def test_the_owner_can_open_billing_history(self):
        from unittest import mock
        from omniarmor_app import academy_plan
        page = self.client.get("/app/academy/plan").data.decode()
        self.assertIn('action="/app/academy/plan/manage"', page)
        self.assertIn('action="/app/academy/plan/checkout"', page)  # and can start again
        with mock.patch.object(academy_plan, "_stripe", return_value={"url": "https://billing.stripe.test/p"}):
            response = self.post("/app/academy/plan/manage")
        self.assertEqual(response.headers["Location"], "https://billing.stripe.test/p")

    def test_no_billing_button_without_a_stripe_customer(self):
        with self.db() as conn:
            conn.execute("UPDATE orgs SET stripe_customer_id = NULL")
            conn.commit()
        self.assertNotIn('action="/app/academy/plan/manage"', self.client.get("/app/academy/plan").data.decode())


class TestBusinessDayClocks(AppTestCase):
    """Ten checks count business days since something happened (the I-9's
    three business days, Reg E's ten, CAN-SPAM's ten...). They took only a
    typed number that never grew: an I-9 entered as "1" stayed Cleared for good."""

    def state(self, industry_id, key, value_date, today):
        from datetime import date
        from omniarmor_app.catalog import find_rule
        from omniarmor_app.tracking import compute_state
        row = {"value_num": None, "value_bool": None, "value_date": value_date, "limit_override": None,
               "warn_override": None, "updated_at": None, "updated_by_name": None}
        return compute_state(industry_id, find_rule(industry_id, key), row, date.fromisoformat(today))

    def test_every_business_day_clock_takes_a_date(self):
        from omni_armor_rules import CATALOG
        from omniarmor_app.catalog import date_mode
        counted = [r for rules in CATALOG.values() for r in rules
                   if r.unit == "business days" and "business days since" in r.input.lower()]
        self.assertEqual(len(counted), 10)
        for r in counted:
            self.assertEqual(date_mode(r), "since", r.key)

    def test_weekdays_count_and_weekends_do_not(self):
        # I-9 Section 2 within 3 business days of a Monday start: due Thursday.
        cases = {"2026-11-02": (0, "CLEARED"), "2026-11-04": (2, "WARNING"), "2026-11-05": (3, "WARNING"),
                 "2026-11-06": (4, "BLOCKED"), "2026-11-07": (4, "BLOCKED")}
        for today, (count, level) in cases.items():
            s = self.state(30, "i9_section_2", "2026-11-02", today)
            self.assertEqual((s.value, s.level, s.due_date.isoformat()), (count, level, "2026-11-05"), today)
        # A Friday start: the weekend doesn't count, nor Veterans Day (Wednesday 11 November).
        s = self.state(30, "i9_section_2", "2026-11-06", "2026-11-11")
        self.assertEqual((s.value, s.due_date.isoformat()), (2, "2026-11-12"))

    def test_holidays_observed_on_a_weekday(self):
        # 4 July 2026 is a Saturday, so the holiday is Friday 3 July.
        self.assertEqual(self.state(30, "i9_section_2", "2026-07-02", "2026-07-05").value, 0)
        self.assertEqual(self.state(30, "i9_section_2", "2026-07-02", "2026-07-06").value, 1)
        # Thanksgiving, the fourth Thursday of November, and New Year's Day.
        self.assertEqual(self.state(30, "i9_section_2", "2026-11-25", "2026-11-27").value, 1)
        self.assertEqual(self.state(30, "i9_section_2", "2026-12-31", "2027-01-04").value, 1)

    def test_same_business_day_rule(self):
        # ATF Form 3310.4 is due the day of the multiple handgun sale.
        s = self.state(48, "multiple_handgun_report", "2026-11-02", "2026-11-02")
        self.assertEqual((s.level, s.due_date.isoformat()), ("CLEARED", "2026-11-02"))
        self.assertEqual(self.state(48, "multiple_handgun_report", "2026-11-02", "2026-11-03").level, "BLOCKED")

    def test_through_the_app(self):
        self.signup(industries=(30,))
        self.assertIn('id="f-i9_section_2-d"', self.client.get("/app/industry/30").data.decode())
        self.change(30, "i9_section_2", date="2026-01-05")
        page = self.client.get("/app/industry/30?only=problems").data.decode()
        self.assertIn('id="rule-i9_section_2"', page)
        self.assertIn("days overdue", page)


class TestBusinessDayDeadlinesOverAWeekend(AppTestCase):
    """An I-9 due on a Friday stayed a Warning on Saturday and Sunday (the
    business-day count doesn't grow on those days) while its due line read
    "1 day overdue". Every place now says overdue the day after the due date."""

    def at(self, day):
        """Runs the app as if it were 10:00 on `day` in the company's timezone (New York)."""
        from datetime import datetime
        from unittest import mock
        from zoneinfo import ZoneInfo

        moment = datetime.fromisoformat(f"{day}T10:00").replace(tzinfo=ZoneInfo("America/New_York"))

        class Frozen(datetime):
            @classmethod
            def now(cls, tz=None):
                return moment.astimezone(tz) if tz else moment.replace(tzinfo=None)

        return mock.patch("omniarmor_app.tracking.datetime", Frozen)

    def test_due_friday_is_overdue_on_saturday_everywhere(self):
        from omniarmor_app.reminders import run_reminders
        self.signup(industries=(30,))
        with self.at("2026-11-04"):
            self.change(30, "i9_section_2", date="2026-11-03")  # a Tuesday start: due Friday 6 November
        with self.at("2026-11-06"):
            page = self.client.get("/app/industry/30").data.decode()
            self.assertIn("Due today", page)
            self.assertIn("3 business days is close to the 3 business days limit", page)
        for day, overdue in (("2026-11-07", "1 day"), ("2026-11-08", "2 days")):
            with self.subTest(day=day), self.at(day):
                page = self.client.get("/app/industry/30?only=problems").data.decode()
                self.assertIn('id="rule-i9_section_2"', page)
                self.assertIn(f"{overdue} overdue", page)
                self.assertIn("limit ended on 2026-11-06", page)
                self.assertNotIn("close to the 3 business days limit", page)
                overview = self.client.get("/app").data.decode()
                self.assertIn("limit ended on 2026-11-06", overview)
                self.assertIn('class="tag BLOCKED">Blocked', overview)
                report = self.client.get("/app/report").data.decode()
                row = report.split("<td>Form I-9 done within 3 business days</td>")[1].split("</tr>")[0]
                self.assertIn('class="tag BLOCKED">Blocked', row)
                self.assertIn("2026-11-06", row)
                csv = self.client.get("/app/report.csv").data.decode()
                line = next(row for row in csv.splitlines() if row.startswith("HRArmor") and "I-9" in row)
                self.assertIn(",Blocked,3 business days,2026-11-06,", line)
                issues = self.client.get("/app/armo/status").get_json()["issues"]
                self.assertTrue(any(i["title"] == f"Form I-9 done within 3 business days: overdue by {overdue}"
                                    for i in issues), issues)
        with self.at("2026-11-07"), self.db() as conn:
            run_reminders(conn, self.app.config)
            body = conn.execute("SELECT body FROM notifications WHERE kind = 'reminder'"
                                " ORDER BY id DESC").fetchone()["body"]
        overdue_part = body.split("OVERDUE")[1].split("COMING DUE")[0]
        self.assertIn("Form I-9 done within 3 business days", overdue_part)
        self.assertIn("1 day overdue", overdue_part)
        self.assertIn("Right now: 1 blocked, 0 warnings", body)


class TestWorkingDayClocks(AppTestCase):
    """Six checks count working days. Five took only a typed number that never
    grew; the FDA field alert (3 working days) counted calendar days, so a
    problem found on a Friday showed Blocked on Tuesday, a day before it was due."""

    def test_every_working_day_clock_counts_working_days(self):
        from omni_armor_rules import CATALOG
        from omniarmor_app.catalog import date_mode, date_unit
        counted = [r for rules in CATALOG.values() for r in rules
                   if "working days since" in r.input.lower() or "work days since" in r.input.lower()]
        self.assertEqual(len(counted), 6)  # and the FDA 5-day MDR report's "work days"
        for r in counted:
            self.assertEqual((date_mode(r), date_unit(r)), ("since", "business days"), r.key)

    def test_field_alert_skips_the_weekend(self):
        from datetime import date
        from omniarmor_app.catalog import find_rule
        from omniarmor_app.tracking import compute_state
        row = {"value_num": None, "value_bool": None, "value_date": "2026-11-06", "limit_override": None,
               "warn_override": None, "updated_at": None, "updated_by_name": None}
        rule = find_rule(22, "field_alert_report")
        s = compute_state(22, rule, row, date.fromisoformat("2026-11-10"))  # Friday to Tuesday
        self.assertEqual((s.value, s.level), (2, "WARNING"))
        self.assertEqual(s.due_date.isoformat(), "2026-11-12")  # Wednesday 11 November is a holiday
        self.assertEqual(rule.unit, "working days")


class ClockTestCase(AppTestCase):
    """Helpers for the checks that count time since a date and time."""

    NY = "America/New_York"

    def state(self, industry_id, key, started, now, tz=NY, **row):
        """`started` is stored UTC; `now` is a wall-clock time in `tz`."""
        from datetime import datetime
        from zoneinfo import ZoneInfo
        from omniarmor_app.catalog import find_rule
        from omniarmor_app.tracking import compute_state
        zone = ZoneInfo(tz)
        moment = datetime.fromisoformat(now).replace(tzinfo=zone)
        base = {"value_num": None, "value_bool": None, "value_date": started, "limit_override": None,
                "warn_override": None, "updated_at": None, "updated_by_name": None}
        base.update(row)
        return compute_state(industry_id, find_rule(industry_id, key), base, moment.date(), moment, zone)

    def reading(self, key):
        with self.db() as conn:
            return dict(conn.execute("SELECT value_num, value_date FROM items WHERE rule_key = ?", (key,)).fetchone())

    def org_now(self):
        from omniarmor_app.tracking import org_now
        with self.db() as conn:
            return org_now(conn.execute("SELECT * FROM orgs").fetchone())


class TestHourClocks(ClockTestCase):
    """Twenty-two checks are asked as "Hours since ..." (a breach reported in
    72 hours, a work death reported to OSHA in 8...). They took only a typed
    number, which never grew: a breach saved as "10 hours" stayed Cleared
    forever, with no due time, no reminder and never Blocked. They now take
    the date and time the clock started and count real hours from it."""

    def test_every_hours_since_check_takes_a_date_and_time(self):
        from omni_armor_rules import CATALOG
        from omniarmor_app.catalog import counts_time, date_mode, date_unit, find_rule
        counted = [r for rules in CATALOG.values() for r in rules if r.input.lower().startswith("hours since ")]
        self.assertEqual(len(counted), 22)
        for r in counted:
            self.assertEqual((date_mode(r), date_unit(r), counts_time(r)), ("since", "hours", True), r.key)
            self.assertEqual(r.unit, "h", r.key)
        # Hours of driving or flying are not time passed: they stay typed numbers.
        for industry_id, key in ((1, "hos_11_hour"), (4, "inspection_100_hour"), (1, "hos_70_hour_8_day")):
            self.assertIsNone(date_mode(find_rule(industry_id, key)), key)

    def test_exactly_at_the_limit_and_one_minute_past(self):
        # OSHA 29 CFR 1904.39: a work death reported within 8 hours (warns from 6).
        start = "2026-11-04T14:00:00+00:00"  # 09:00 in New York
        cases = {"2026-11-04T14:59": (5.98, "CLEARED", "Due in 2 h 1 min"),
                 "2026-11-04T15:00": (6, "WARNING", "Due in 2 h"),
                 "2026-11-04T16:59": (7.98, "WARNING", "Due in 1 min"),
                 "2026-11-04T17:00": (8, "WARNING", "Due now"),
                 "2026-11-04T17:00:59": (8, "WARNING", "Due now"),
                 "2026-11-04T17:01": (8.02, "BLOCKED", "1 min overdue"),
                 "2026-11-04T19:30": (10.5, "BLOCKED", "2 h 30 min overdue")}
        for now, (hours, level, due) in cases.items():
            s = self.state(30, "fatality_report_8h", start, now)
            self.assertEqual((round(s.value, 2), s.level, s.due_text), (hours, level, due), now)
            self.assertEqual(s.due_label, "2026-11-04 17:00 EST")
            self.assertEqual(s.warn_at.strftime("%H:%M"), "15:00")
        self.assertIn("8 h is close to the 8 h limit", self.state(30, "fatality_report_8h", start, "2026-11-04T17:00").message)
        self.assertIn("is over the 8 h limit", self.state(30, "fatality_report_8h", start, "2026-11-04T17:01").message)

    def test_one_hour_and_shorter_limits(self):
        # 49 CFR 191.5: call the National Response Center within 1 hour (warns from 45 minutes).
        start = "2026-11-04T14:00:00+00:00"
        self.assertEqual(self.state(20, "pipeline_incident_call", start, "2026-11-04T09:44").level, "CLEARED")
        self.assertEqual(self.state(20, "pipeline_incident_call", start, "2026-11-04T09:45").level, "WARNING")
        s = self.state(20, "pipeline_incident_call", start, "2026-11-04T10:00")
        self.assertEqual((s.value, s.level, s.due_text), (1, "WARNING", "Due now"))
        self.assertEqual(self.state(20, "pipeline_incident_call", start, "2026-11-04T10:01").level, "BLOCKED")

    def test_across_midnight(self):
        # Started at 8 p.m.: the 8 hours run out at 4 a.m. the next day.
        start = "2026-11-05T01:00:00+00:00"  # 20:00 on 4 November in New York
        s = self.state(30, "fatality_report_8h", start, "2026-11-04T23:59")
        self.assertEqual((round(s.value, 2), s.level, s.due_label), (3.98, "CLEARED", "2026-11-05 04:00 EST"))
        self.assertEqual((s.due_date.isoformat(), s.days_left, s.due_in), ("2026-11-05", 1, "in 4 h 1 min"))
        s = self.state(30, "fatality_report_8h", start, "2026-11-05T00:00")
        self.assertEqual((s.value, s.days_left), (4, 0))
        s = self.state(30, "fatality_report_8h", start, "2026-11-05T04:01")
        # Past due earlier the same day: overdue, never "due today".
        self.assertEqual((s.level, s.days_left, s.overdue, s.due_text), ("BLOCKED", -1, True, "1 min overdue"))
        # A 72-hour clock counts days and hours.
        s = self.state(6, "gdpr_breach_72h", "2026-11-04T14:00:00+00:00", "2026-11-04T10:00")
        self.assertEqual((s.value, s.due_text), (1, "Due in 2 days 23 h"))

    def test_across_the_change_back_from_daylight_time(self):
        # Clocks went back an hour at 2 a.m. on Sunday 1 November 2026 in New York.
        # 72 real hours from noon on Saturday 31 October run out at 11 a.m. on Tuesday.
        start = "2026-10-31T16:00:00+00:00"  # 12:00 EDT
        s = self.state(6, "gdpr_breach_72h", start, "2026-11-03T11:00")
        self.assertEqual((s.value, s.level, s.due_label), (72, "WARNING", "2026-11-03 11:00 EST"))
        self.assertEqual(self.state(6, "gdpr_breach_72h", start, "2026-11-03T11:01").level, "BLOCKED")
        self.assertEqual(self.state(6, "gdpr_breach_72h", start, "2026-11-03T12:00").value, 73)
        # Across the night itself: 00:30 EDT to 01:30 EST is two hours.
        s = self.state(6, "gdpr_breach_72h", "2026-11-01T04:30:00+00:00", "2026-11-01T01:30")
        self.assertEqual(s.value, 1)  # 01:30 with fold 0 is still EDT
        from datetime import datetime, timezone
        from zoneinfo import ZoneInfo
        from omniarmor_app.catalog import find_rule
        from omniarmor_app.tracking import compute_state
        later = datetime(2026, 11, 1, 6, 30, tzinfo=timezone.utc)  # 01:30 EST, the second time
        row = {"value_num": None, "value_bool": None, "value_date": "2026-11-01T04:30:00+00:00", "limit_override": None,
               "warn_override": None, "updated_at": None, "updated_by_name": None}
        s = compute_state(6, find_rule(6, "gdpr_breach_72h"), row, later.date(), later, ZoneInfo(self.NY))
        self.assertEqual(s.value, 2)

    def test_across_the_change_to_daylight_time(self):
        # Clocks went forward at 2 a.m. on Sunday 8 March 2026: 24 real hours from
        # noon on Saturday end at 1 p.m. on Sunday.
        start = "2026-03-07T17:00:00+00:00"  # 12:00 EST
        s = self.state(30, "hospitalization_report_24h", start, "2026-03-08T12:00")
        self.assertEqual((s.value, s.level, s.due_label, s.due_text), (23, "WARNING", "2026-03-08 13:00 EDT", "Due in 1 h"))
        self.assertEqual(self.state(30, "hospitalization_report_24h", start, "2026-03-08T13:00").level, "WARNING")
        self.assertEqual(self.state(30, "hospitalization_report_24h", start, "2026-03-08T13:01").level, "BLOCKED")

    def test_times_that_happen_twice_or_never(self):
        from zoneinfo import ZoneInfo
        from omniarmor_app.tracking import ValidationError, _parse_moment
        ny = ZoneInfo(self.NY)
        # 01:30 on 1 November 2026 happens twice: the first (earlier) one is taken.
        self.assertEqual(_parse_moment("2026-11-01T01:30", ny)[0].isoformat(), "2026-11-01T05:30:00+00:00")
        # 02:30 on 8 March 2026 never happens: read as 03:30 EDT.
        self.assertEqual(_parse_moment("2026-03-08T02:30", ny)[0].isoformat(), "2026-03-08T07:30:00+00:00")
        # Typed by hand with a space, or with seconds (dropped).
        self.assertEqual(_parse_moment("2026-06-01 09:15:42", ny)[0].isoformat(), "2026-06-01T13:15:00+00:00")
        for bad in ("2026-06-01", "yesterday", "2026-13-01T10:00", "1900-01-01T10:00"):
            with self.assertRaises(ValidationError, msg=bad):
                _parse_moment(bad, ny)

    def test_the_entered_time_is_read_in_the_workspace_timezone(self):
        self.signup(industries=(30,))
        with self.db() as conn:
            conn.execute("UPDATE orgs SET timezone = 'Asia/Tokyo'")
            conn.commit()
        page = self.client.get("/app/industry/30").data.decode()
        self.assertIn('type="datetime-local" id="f-fatality_report_8h-d"', page)
        self.assertIn("Or the date and time it started (JST)", page)
        self.change(30, "fatality_report_8h", date="2026-01-10T09:00")
        self.assertEqual(self.reading("fatality_report_8h"), {"value_num": None, "value_date": "2026-01-10T00:00:00+00:00"})
        page = self.client.get("/app/industry/30?only=problems").data.decode()
        self.assertIn('value="2026-01-10T09:00"', page)  # shown back in Tokyo time
        self.assertIn("overdue · 2026-01-10 17:00 JST", page)
        with self.db() as conn:
            summary = conn.execute("SELECT summary FROM audit WHERE rule_key = 'fatality_report_8h'").fetchone()[0]
        self.assertIn("started 2026-01-10 09:00 JST", summary)
        # The same moment reads back in the new zone when the workspace moves.
        with self.db() as conn:
            conn.execute("UPDATE orgs SET timezone = 'America/New_York'")
            conn.commit()
        page = self.client.get("/app/industry/30?only=problems").data.decode()
        self.assertIn('value="2026-01-09T19:00"', page)
        self.assertIn("2026-01-10 03:00 EST", page)

    def test_it_counts_up_through_the_app(self):
        import re
        from datetime import timedelta
        self.signup(industries=(30,))
        an_hour_ago = (self.org_now() - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M")
        self.change(30, "fatality_report_8h", date=an_hour_ago)
        page = self.client.get("/app/industry/30").data.decode()
        self.assertRegex(page, r"Due in (7 h|6 h 59 min) · \d{4}-\d\d-\d\d \d\d:\d\d E[SD]T")
        self.assertIn(f'value="{an_hour_ago}"', page)
        self.assertIn(">Done now</button>", page)
        overview = self.client.get("/app").data.decode()
        self.assertRegex(overview, r"in (7 h|6 h 59 min) · \d{4}-\d\d-\d\d \d\d:\d\d E[SD]T")
        csv = self.client.get("/app/report.csv").data.decode()
        self.assertTrue(re.search(r"Report a work fatality in 8 hours,Cleared,[\d.]+ h,\d{4}-\d\d-\d\d \d\d:\d\d E[SD]T", csv))

    def test_a_future_time_or_a_date_alone_is_refused(self):
        from datetime import timedelta
        self.signup(industries=(30,))
        later = (self.org_now() + timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M")
        self.change(30, "fatality_report_8h", date=later)
        self.assertIn("That time is in the future", self.client.get("/app/industry/30").data.decode())
        self.change(30, "fatality_report_8h", date="2026-01-10")
        self.assertIn("Enter the date and the time it started", self.client.get("/app/industry/30").data.decode())
        with self.db() as conn:
            self.assertIsNone(conn.execute("SELECT 1 FROM items WHERE rule_key = 'fatality_report_8h'").fetchone())

    def test_a_typed_number_still_works_and_stays_as_typed(self):
        self.signup(industries=(30,))
        self.change(30, "fatality_report_8h", value="5")
        self.assertEqual(self.reading("fatality_report_8h"), {"value_num": 5.0, "value_date": None})
        s = self.state(30, "fatality_report_8h", None, "2030-01-01T00:00", value_num=5.0)
        self.assertEqual((s.value, s.level, s.due_date), (5, "CLEARED", None))

    def test_switching_between_a_number_and_a_time(self):
        # The same rules as the date checks: the page sends back whatever is saved.
        self.signup(industries=(30,))
        self.change(30, "fatality_report_8h", value="5")
        self.change(30, "fatality_report_8h", value="6", date="2026-01-10T09:00")  # new number, new time
        self.assertIn("Enter a number or a date, not both", self.client.get("/app/industry/30").data.decode())
        self.assertEqual(self.reading("fatality_report_8h"), {"value_num": 5.0, "value_date": None})
        self.change(30, "fatality_report_8h", value="5", date="2026-01-10T09:00")  # saved number, new time
        self.assertEqual(self.reading("fatality_report_8h"), {"value_num": None, "value_date": "2026-01-10T14:00:00+00:00"})
        self.change(30, "fatality_report_8h", value="3", date="2026-01-10T09:00")  # new number, saved time
        self.assertEqual(self.reading("fatality_report_8h"), {"value_num": 3.0, "value_date": None})

    def test_a_saved_time_from_the_second_one_thirty_comes_back_unchanged(self):
        # 01:30 EST on 1 November 2026 shows as "2026-11-01T01:30", which also
        # names 01:30 EDT an hour earlier. Sent back with a new number, it is the
        # saved time unchanged, not a clashing new one.
        self.signup(industries=(30,))
        with self.db() as conn:
            org_id = conn.execute("SELECT id FROM orgs").fetchone()[0]
            conn.execute("INSERT INTO items (org_id, industry_id, rule_key, value_date) VALUES (?, 30, ?, ?)",
                         (org_id, "fatality_report_8h", "2026-11-01T06:30:00+00:00"))
            conn.commit()
        self.assertIn('value="2026-11-01T01:30"', self.client.get("/app/industry/30").data.decode())
        self.change(30, "fatality_report_8h", value="4", date="2026-11-01T01:30")
        self.assertEqual(self.reading("fatality_report_8h"), {"value_num": 4.0, "value_date": None})

    def test_done_now_starts_the_clock_again(self):
        from datetime import datetime, timezone
        self.signup(industries=(30,))
        self.change(30, "fatality_report_8h", date="2026-01-10T09:00")
        self.assertIn('id="rule-fatality_report_8h"', self.client.get("/app/industry/30?only=problems").data.decode())
        before = datetime.now(timezone.utc).replace(second=0, microsecond=0)
        self.change(30, "fatality_report_8h", action="done_today")
        started = datetime.fromisoformat(self.reading("fatality_report_8h")["value_date"])
        self.assertLessEqual(before, started)
        self.assertEqual((started.second, started.utcoffset().total_seconds()), (0, 0))
        page = self.client.get("/app/industry/30").data.decode()
        self.assertIn("Marked done now", page)
        self.assertNotIn('id="rule-fatality_report_8h"', self.client.get("/app/industry/30?only=problems").data.decode())

    def test_an_overdue_clock_gets_a_reminder_with_its_due_time(self):
        from omniarmor_app.reminders import run_reminders
        self.signup(industries=(30,))
        self.change(30, "fatality_report_8h", date="2026-01-10T09:00")
        with self.db() as conn:
            summary = run_reminders(conn, self.app.config)
            body = conn.execute("SELECT body FROM notifications WHERE kind = 'reminder'").fetchone()[0]
        self.assertGreaterEqual(summary["reminders"], 1)
        self.assertIn("OVERDUE", body)
        self.assertRegex(body, r"Report a work fatality in 8 hours, \d+ days( \d+ h)? overdue \(2026-01-10 17:00 EST\)")

    def test_a_reminder_run_for_another_day_counts_to_noon_that_day(self):
        from datetime import date
        from omniarmor_app.tracking import states_for_org
        self.signup(industries=(30,))
        self.change(30, "fatality_report_8h", date="2026-01-10T09:00")
        with self.db() as conn:
            org = conn.execute("SELECT * FROM orgs").fetchone()
            s = next(s for s in states_for_org(conn, org, today=date(2026, 1, 10)) if s.key == "fatality_report_8h")
        self.assertEqual((s.value, s.level, s.days_left), (3, "CLEARED", 0))

    def test_a_policy_limit_counts_in_hours(self):
        # Sick call triage in 24 hours is common policy, so a jail can set its own.
        self.signup(industries=(16,))
        self.change(16, "sick_call_triage", action="override", limit="5000000")
        self.assertIn("Enter a number of hours between 0 and 876000", self.client.get("/app/industry/16").data.decode())
        s = self.state(16, "sick_call_triage", "2026-11-04T14:00:00+00:00", "2026-11-04T20:00",
                       limit_override=12, warn_override=10)
        self.assertEqual((s.value, s.level, s.due_label), (11, "WARNING", "2026-11-04 21:00 EST"))

    def test_a_stored_value_of_the_other_kind_never_breaks_a_page(self):
        # A bare date on an hour clock counts from local midnight; a moment on a
        # day clock counts from its day.
        s = self.state(30, "fatality_report_8h", "2026-11-04", "2026-11-04T07:00")
        self.assertEqual((s.value, s.level), (7, "WARNING"))
        self.assertEqual(self.state(30, "fatality_report_8h", "not a date", "2026-11-04T07:00").level, "NONE")
        from datetime import date
        from omniarmor_app.catalog import find_rule
        from omniarmor_app.tracking import compute_state
        row = {"value_num": None, "value_bool": None, "value_date": "2026-01-01T10:00:00+00:00", "limit_override": None,
               "warn_override": None, "updated_at": None, "updated_by_name": None}
        self.assertEqual(compute_state(1, find_rule(1, "annual_mvr_review"), row, date(2026, 1, 11)).value, 10)


class TestMinuteClocks(ClockTestCase):
    """Two more clocks are asked as "Minutes since ...": the restrictive housing
    welfare check (every 30 minutes) and MSHA's 15-minute accident call. They
    had the same typed number that never grew, and count like the hour clocks."""

    def test_both_take_a_date_and_time(self):
        from omni_armor_rules import CATALOG
        from omniarmor_app.catalog import counts_time, date_mode, date_unit
        counted = [r for rules in CATALOG.values() for r in rules if r.input.lower().startswith("minutes since ")]
        self.assertEqual(sorted(r.key for r in counted), ["accident_notice", "welfare_check_interval"])
        for r in counted:
            self.assertEqual((date_mode(r), date_unit(r), counts_time(r)), ("since", "minutes", True), r.key)

    def test_minutes_count_to_the_limit(self):
        # 30 CFR 50.10: call MSHA within 15 minutes (warns from 10).
        start = "2026-11-04T14:00:00+00:00"  # 09:00 in New York
        cases = {"2026-11-04T09:09:59": (9, "CLEARED", "Due in 6 min"), "2026-11-04T09:10": (10, "WARNING", "Due in 5 min"),
                 "2026-11-04T09:15:30": (15, "WARNING", "Due now"), "2026-11-04T09:16": (16, "BLOCKED", "1 min overdue"),
                 "2026-11-04T11:16": (136, "BLOCKED", "2 h 1 min overdue")}
        for now, (minutes, level, due) in cases.items():
            s = self.state(23, "accident_notice", start, now)
            self.assertEqual((s.value, s.level, s.due_text, s.due_label), (minutes, level, due, "2026-11-04 09:15 EST"), now)
        self.assertIn("16 min is over the 15 min limit", self.state(23, "accident_notice", start, "2026-11-04T09:16").message)

    def test_a_welfare_check_round_through_the_app(self):
        from datetime import timedelta
        self.signup(industries=(16,))
        page = self.client.get("/app/industry/16").data.decode()
        self.assertIn('type="datetime-local" id="f-welfare_check_interval-d"', page)
        started = (self.org_now() - timedelta(minutes=40)).strftime("%Y-%m-%dT%H:%M")
        self.change(16, "welfare_check_interval", date=started)
        page = self.client.get("/app/industry/16?only=problems").data.decode()
        self.assertRegex(page, r"1[01] min overdue")
        self.change(16, "welfare_check_interval", action="done_today")  # a check was just made
        self.assertNotIn('id="rule-welfare_check_interval"', self.client.get("/app/industry/16?only=problems").data.decode())
        # A facility on 15-minute watch sets its own limit, in minutes.
        self.change(16, "welfare_check_interval", action="override", limit="15", warn="12")
        s = self.state(16, "welfare_check_interval", "2026-11-04T14:00:00+00:00", "2026-11-04T09:13",
                       limit_override=15, warn_override=12)
        self.assertEqual((s.value, s.level, s.due_label), (13, "WARNING", "2026-11-04 09:15 EST"))


class TestTimeLimitAlerts(ClockTestCase):
    """Reminder digests go out once a day, so a clock of a few hours (the NRC
    call in 1 hour, an abuse report in 2, an OSHA fatality report in 8) could
    start and run out between two digests with no email at all. Every minute,
    each hour or minute clock now gets one email when it reaches its warning
    point and one when it becomes overdue."""

    def setUp(self):
        super().setUp()
        self.signup(industries=(30, 23))
        with self.db() as conn:
            self.org_id = conn.execute("SELECT id FROM orgs").fetchone()[0]

    def start(self, industry_id, key, started):
        """Starts a clock at `started`, a UTC moment ("2026-11-04T14:00:00+00:00")."""
        with self.db() as conn:
            conn.execute("INSERT OR REPLACE INTO items (org_id, industry_id, rule_key, value_date) VALUES (?, ?, ?, ?)",
                         (self.org_id, industry_id, key, started))
            conn.commit()

    def run_at(self, now, tz=ClockTestCase.NY, cfg=None):
        """Runs the alerts at `now`, a wall-clock time in `tz` (or an aware datetime)."""
        from datetime import datetime
        from zoneinfo import ZoneInfo
        from omniarmor_app.reminders import run_clock_alerts
        if isinstance(now, str):
            now = datetime.fromisoformat(now).replace(tzinfo=ZoneInfo(tz))
        with self.db() as conn:
            return run_clock_alerts(conn, cfg or dict(self.app.config), now=now)

    def notes(self):
        with self.db() as conn:
            return [dict(r) for r in conn.execute(
                "SELECT subject, body, status, attempts FROM notifications WHERE kind = 'reminder' ORDER BY id")]

    def marks(self):
        with self.db() as conn:
            return [tuple(r) for r in conn.execute(
                "SELECT rule_key, due_date, threshold FROM reminder_marks ORDER BY rowid")]

    def test_an_email_when_the_clock_reaches_its_warning_point(self):
        # OSHA: a work death reported within 8 hours, warns from 6. Learned of at 9:00.
        self.start(30, "fatality_report_8h", "2026-11-04T14:00:00+00:00")
        self.assertEqual(self.run_at("2026-11-04T14:59")["alerts"], 0)
        self.assertEqual(self.notes(), [])
        self.assertEqual(self.run_at("2026-11-04T15:00")["alerts"], 1)
        [note] = self.notes()
        self.assertEqual(note["subject"],
                         "OmniArmor: Report a work fatality in 8 hours, due 2026-11-04 17:00 EST (Acme Logistics)")
        self.assertEqual(note["status"], "logged")
        lines = note["body"].splitlines()
        self.assertEqual(lines[0], "Time limit warning for Acme Logistics, 2026-11-04 15:00 EST.")
        self.assertTrue(lines[2].startswith(
            "- HRArmor: Report a work fatality in 8 hours, due in 2 h (2026-11-04 17:00 EST). "), lines[2])
        self.assertIn("Open it: https://omniarmor.test/app/industry/30#rule-fatality_report_8h", note["body"])
        self.assertIn("time-limit alerts are on in your OmniArmor settings", note["body"])
        self.assertEqual(self.marks(), [("fatality_report_8h", "2026-11-04T22:00:00+00:00", "clock-warning")])

    def test_an_email_when_it_becomes_overdue(self):
        self.start(30, "fatality_report_8h", "2026-11-04T14:00:00+00:00")
        self.run_at("2026-11-04T15:00")
        self.assertEqual(self.run_at("2026-11-04T17:00")["alerts"], 0)  # the due minute is still a Warning
        self.assertEqual(self.run_at("2026-11-04T17:01")["alerts"], 1)
        notes = self.notes()
        self.assertEqual(len(notes), 2)
        self.assertEqual(notes[1]["subject"], "OmniArmor: Report a work fatality in 8 hours, overdue,"
                                              " was due 2026-11-04 17:00 EST (Acme Logistics)")
        self.assertTrue(notes[1]["body"].startswith("Time limit overdue for Acme Logistics, 2026-11-04 17:01 EST."))
        self.assertIn("- HRArmor: Report a work fatality in 8 hours, 1 min overdue (2026-11-04 17:00 EST).",
                      notes[1]["body"])
        self.assertEqual([m[2] for m in self.marks()], ["clock-warning", "clock-overdue"])

    def test_each_stage_is_sent_once(self):
        self.start(30, "fatality_report_8h", "2026-11-04T14:00:00+00:00")
        for now in ("2026-11-04T15:00", "2026-11-04T15:00", "2026-11-04T15:30", "2026-11-04T16:59",
                    "2026-11-04T17:01", "2026-11-04T17:02", "2026-11-04T23:00", "2026-11-05T10:00"):
            self.run_at(now)
        self.assertEqual(len(self.notes()), 2)

    def test_a_stage_already_passed_or_long_gone_is_not_sent(self):
        # Entered after it ran out: only the overdue email, no warning.
        self.start(30, "fatality_report_8h", "2026-11-04T14:00:00+00:00")
        self.assertEqual(self.run_at("2026-11-04T19:30")["alerts"], 1)
        self.assertEqual([m[2] for m in self.marks()], ["clock-overdue"])
        # Overdue for more than a day is not news any more; the daily digest covers it.
        self.start(23, "accident_notice", "2026-11-02T14:00:00+00:00")
        self.assertEqual(self.run_at("2026-11-04T19:31")["alerts"], 0)
        # Day checks never get these emails.
        with self.db() as conn:
            conn.execute("INSERT INTO items (org_id, industry_id, rule_key, value_date) VALUES (?, 30, ?, ?)",
                         (self.org_id, "cobra_election_notice", "2026-11-01"))
            conn.commit()
        self.assertEqual(self.run_at("2026-11-04T19:32")["alerts"], 0)

    def test_starting_the_clock_again_re_arms_both_emails(self):
        from datetime import datetime, timedelta, timezone
        from omniarmor_app.db import iso
        now = datetime.now(timezone.utc).replace(second=0, microsecond=0)
        self.start(30, "fatality_report_8h", iso(now - timedelta(hours=8, minutes=5)))
        self.assertEqual(self.run_at(now)["alerts"], 1)  # overdue
        self.change(30, "fatality_report_8h", action="done_today")  # Done now: the clock starts again
        started = datetime.fromisoformat(self.reading("fatality_report_8h")["value_date"])
        self.assertEqual(self.run_at(started + timedelta(hours=5))["alerts"], 0)
        self.assertEqual(self.run_at(started + timedelta(hours=6))["alerts"], 1)
        self.assertEqual(self.run_at(started + timedelta(hours=8, minutes=1))["alerts"], 1)
        self.assertEqual([m[2] for m in self.marks()], ["clock-overdue", "clock-warning", "clock-overdue"])
        self.assertEqual(len({m[1] for m in self.marks()}), 2)  # kept by each start's due moment
        self.assertEqual(len(self.notes()), 3)

    def test_a_failed_send_is_tried_again_on_the_next_run(self):
        from datetime import datetime, timedelta, timezone
        from omniarmor_app.db import iso
        broken = dict(self.app.config, SMTP_HOST="127.0.0.1", SMTP_PORT=1)
        now = datetime.now(timezone.utc).replace(second=0, microsecond=0)
        self.start(30, "fatality_report_8h", iso(now - timedelta(hours=6, minutes=5)))
        self.assertEqual(self.run_at(now, cfg=broken)["alerts"], 0)
        self.assertEqual(self.marks(), [])
        self.assertEqual(self.run_at(now + timedelta(minutes=1), cfg=broken)["alerts"], 0)
        self.assertEqual(self.run_at(now + timedelta(minutes=2))["alerts"], 1)
        # Sent again in place: one row on Radar, not one per run for Autopilot to re-send.
        [note] = self.notes()
        self.assertEqual((note["status"], note["attempts"]), ("logged", 3))
        self.assertIn("due in 1 h 53 min", note["body"])  # the email says how long is left now
        self.assertEqual(self.run_at(now + timedelta(minutes=3))["alerts"], 0)
        self.assertEqual(len(self.notes()), 1)

    def test_a_copy_autopilot_got_through_is_not_sent_again(self):
        from datetime import datetime, timedelta, timezone
        from omniarmor_app.db import iso
        broken = dict(self.app.config, SMTP_HOST="127.0.0.1", SMTP_PORT=1)
        now = datetime.now(timezone.utc).replace(second=0, microsecond=0)
        self.start(30, "fatality_report_8h", iso(now - timedelta(hours=6, minutes=5)))
        self.run_at(now, cfg=broken)
        with self.db() as conn:
            conn.execute("UPDATE notifications SET status = 'sent', attempts = 2")  # Autopilot's retry worked
            conn.commit()
        self.assertEqual(self.run_at(now + timedelta(minutes=1), cfg=broken)["alerts"], 1)
        self.assertEqual([n["status"] for n in self.notes()], ["sent"])

    def test_no_one_with_reminders_on(self):
        self.post("/app/settings/reminders", {})
        self.start(30, "fatality_report_8h", "2026-11-04T14:00:00+00:00")
        self.assertEqual(self.run_at("2026-11-04T15:00"), {"orgs": 1, "alerts": 1, "emails": 0, "errors": 0})
        self.assertEqual(self.notes(), [])
        self.assertEqual(self.run_at("2026-11-04T15:01")["alerts"], 0)

    def test_minute_clocks(self):
        # 30 CFR 50.10: call MSHA within 15 minutes, warns from 10.
        from datetime import datetime
        from zoneinfo import ZoneInfo
        from omniarmor_app.jobs import run_alerts
        self.start(23, "accident_notice", "2026-11-04T14:00:00+00:00")
        at = lambda wall: datetime.fromisoformat(wall).replace(tzinfo=ZoneInfo(self.NY))  # noqa: E731
        cfg = dict(self.app.config)
        self.assertEqual(run_alerts(cfg, now=at("2026-11-04T09:09"))["alerts"], 0)
        self.assertEqual(run_alerts(cfg, now=at("2026-11-04T09:10"))["alerts"], 1)
        self.assertEqual(run_alerts(cfg, now=at("2026-11-04T09:15"))["alerts"], 0)
        self.assertEqual(run_alerts(cfg, now=at("2026-11-04T09:16"))["alerts"], 1)
        warning, overdue = self.notes()
        self.assertIn("- MineArmor: Call MSHA within 15 minutes, due in 5 min (2026-11-04 09:15 EST).", warning["body"])
        self.assertIn("- MineArmor: Call MSHA within 15 minutes, 1 min overdue (2026-11-04 09:15 EST).", overdue["body"])

    def test_a_workspace_in_another_timezone(self):
        with self.db() as conn:
            conn.execute("UPDATE orgs SET timezone = 'Asia/Tokyo'")
            conn.commit()
        self.start(30, "fatality_report_8h", "2026-01-10T00:00:00+00:00")  # 09:00 in Tokyo
        self.assertEqual(self.run_at("2026-01-10T14:59", tz="Asia/Tokyo")["alerts"], 0)
        self.assertEqual(self.run_at("2026-01-10T15:00", tz="Asia/Tokyo")["alerts"], 1)
        self.assertEqual(self.run_at("2026-01-10T17:01", tz="Asia/Tokyo")["alerts"], 1)
        warning, overdue = self.notes()
        self.assertEqual(warning["subject"],
                         "OmniArmor: Report a work fatality in 8 hours, due 2026-01-10 17:00 JST (Acme Logistics)")
        self.assertTrue(warning["body"].startswith("Time limit warning for Acme Logistics, 2026-01-10 15:00 JST."))
        self.assertIn("1 min overdue (2026-01-10 17:00 JST)", overdue["body"])
        self.assertEqual(self.marks()[0][1], "2026-01-10T08:00:00+00:00")

    def test_the_digest_leaves_out_a_clock_alerted_about_the_same_day(self):
        from datetime import date
        from omniarmor_app.reminders import run_reminders
        # Due 11:00 on 4 November, alerted at 11:01; the digest that day (counted at noon) leaves it out.
        self.start(30, "fatality_report_8h", "2026-11-04T08:00:00+00:00")
        self.run_at("2026-11-04T11:01")
        # Due 23:15 on 3 November and alerted then: the next day's digest still lists it.
        self.start(23, "accident_notice", "2026-11-04T04:00:00+00:00")
        self.run_at("2026-11-03T23:16")
        self.assertEqual(len(self.notes()), 2)
        with self.db() as conn:
            summary = run_reminders(conn, dict(self.app.config), today_for=lambda org: date(2026, 11, 4))
            again = run_reminders(conn, dict(self.app.config), today_for=lambda org: date(2026, 11, 5))
        self.assertEqual((summary["reminders"], again["reminders"]), (1, 0))
        digest = self.notes()[2]
        self.assertIn("Call MSHA within 15 minutes", digest["body"])
        self.assertNotIn("Report a work fatality", digest["body"])
        self.assertIn(("fatality_report_8h", "2026-11-04", "overdue-week-0"), self.marks())  # counted as reminded

    def test_the_timer_checks_every_minute(self):
        from unittest import mock
        from omniarmor_app import jobs

        class Stop(Exception):
            pass

        ticks = {"n": 0}

        def sleep(seconds):
            self.assertEqual(seconds, 60)
            ticks["n"] += 1
            if ticks["n"] == 25:
                raise Stop

        class InlineThread:
            def __init__(self, target, **_):
                self.target = target

            def start(self):
                try:
                    self.target()
                except Stop:
                    pass

        clock = iter(range(0, 10 ** 6, 60))
        with mock.patch.object(jobs, "run_alerts") as alerts, mock.patch.object(jobs, "run_daily") as daily, \
                mock.patch("omniarmor_app.autopilot.run") as autopilot, \
                mock.patch.object(jobs.time, "sleep", side_effect=sleep), \
                mock.patch.object(jobs.time, "monotonic", side_effect=lambda: next(clock)), \
                mock.patch.object(jobs.threading, "Thread", InlineThread):
            jobs.start_scheduler(dict(self.app.config))
        self.assertEqual(alerts.call_count, 25)
        self.assertEqual(daily.call_count, 3)  # minutes 0, 10 and 20
        self.assertEqual(autopilot.call_count, 3)

