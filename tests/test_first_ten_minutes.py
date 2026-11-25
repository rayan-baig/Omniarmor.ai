"""A new workspace's first ten minutes: the landing page, sign-up, the top
checks of each industry, the first-day checklist and the empty states."""

import os
from datetime import date, timedelta
import re
import sys
import tempfile
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_webapp import PASSWORD, AppTestCase  # noqa: E402

from omniarmor_app import create_app, plans  # noqa: E402
from omniarmor_app.academy import TRACK_LIST  # noqa: E402
from omniarmor_app.academy_plan import FREE_WORLDS  # noqa: E402
from omniarmor_app.catalog import (CATALOG, INDUSTRIES, TOP_COUNT, date_mode, rules_for, severity,  # noqa: E402
                                   top_checks, top_rank, why_line)


def text(response):
    return " ".join(re.sub(r"<[^>]+>", " ", response.data.decode()).split())


def hero(response):
    page = response.data.decode()
    return " ".join(re.sub(r"<[^>]+>", " ", page[page.index('<section class="hero">'):page.index("</section>")]).split())


class TestLandingPage(AppTestCase):
    def test_who_price_and_trial_are_in_the_first_screen_from_the_code(self):
        top = hero(self.client.get("/"))
        checks = sum(len(rules_for(i)) for i in INDUSTRIES)
        self.assertIn(f"{len(INDUSTRIES)} industries · {checks} checks", top)
        # Small businesses first, the rest as starter lists.
        self.assertIn("For small businesses like restaurants, bars, salons, child care, dental offices,"
                      f" construction and shops, with starter lists for {len(INDUSTRIES)} industries in all", top)
        self.assertIn(f"{self.app.config['ACADEMY_TRIAL_DAYS']}-day free trial of everything in {plans.PLUS.name}", top)
        self.assertIn(f"The first {len(FREE_WORLDS)} Launchpad worlds are free for everyone", top)
        # The prices are the code's, and only those: Pro and Plus. The Kitchen Safety
        # Bundle is on the restaurant page, and the classroom plans on the schools page.
        self.assertIn(f"{plans.PRO.name} · compliance tracker {plans.PRO.price}", top)
        self.assertIn(f"{plans.PLUS.name} · tracker and Academy {plans.PLUS.price}", top)
        self.assertEqual(set(re.findall(r"\$\d+", top)), {f"${d}" for d in (plans.PRO.dollars, plans.PLUS.dollars)})
        self.assertNotIn(plans.BUNDLE_NAME, top)
        self.assertIn('href="/classrooms"', self.client.get("/").data.decode())

    def test_the_numbers_follow_the_settings(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        app = create_app(TESTING=True, DATABASE=os.path.join(tmp.name, "t.db"), SCHEDULER_ENABLED=False,
                         ACADEMY_TRIAL_DAYS=30)
        with mock.patch.object(plans, "PRO", plans.Plan("pro", "Pro", 45, "PRO_STRIPE_PRICE", True, False)):
            top = hero(app.test_client().get("/"))
        self.assertIn("30-day free trial", top)
        self.assertIn("$45 a month per location", top)
        self.assertNotIn("$50", top)

    def test_the_landing_page_agrees_with_the_terms(self):
        terms = text(self.client.get("/terms"))
        self.assertIn(f"free {self.app.config['ACADEMY_TRIAL_DAYS']}-day trial of everything in {plans.PLUS.name},"
                      " from the day it signs up", terms)
        self.assertIn(f"{plans.PRO.name} , {plans.PRO.price}", terms)
        self.assertIn(f"{plans.PLUS.name} , {plans.PLUS.price}", terms)
        self.assertIn(f"The first {len(FREE_WORLDS)} worlds of the Launchpad track stay free for everyone", terms)
        self.assertIn("Without a plan, the compliance tracker is read-only", terms)

    def test_academy_level_counts_come_from_the_tracks(self):
        page = text(self.client.get("/help"))
        low, high = min(t.lessons for t in TRACK_LIST), max(t.lessons for t in TRACK_LIST)
        self.assertIn(f"{len(TRACK_LIST)} tracks, from {low:,} to {high:,} business lessons", page)


class TestTopChecks(AppTestCase):
    def test_five_per_industry_by_the_stated_rule(self):
        for industry_id, rules in CATALOG.items():
            top = top_checks(industry_id)
            self.assertEqual(len(top), TOP_COUNT)
            keys = [(severity(r), date_mode(r) is None, rules.index(r)) for r in top]
            self.assertEqual(keys, sorted(keys), industry_id)
            # Nothing left out ranks above the last one in.
            worst = keys[-1]
            for r in rules:
                if r not in top:
                    self.assertGreater((severity(r), date_mode(r) is None, rules.index(r)), worst)
            for place, r in enumerate(top, 1):
                self.assertEqual(top_rank(industry_id, r.key), place)

    def test_severity_reads_the_cost_text(self):
        def rule(i, key):
            return next(r for r in CATALOG[i] if r.key == key)
        self.assertEqual(severity(rule(2, "no_pests")), 0)            # "can close the restaurant"
        self.assertEqual(severity(rule(1, "hos_11_hour")), 0)         # out-of-service orders
        self.assertEqual(severity(rule(30, "i9_section_2")), 1)       # civil penalties
        self.assertEqual(severity(rule(2, "cold_holding")), 2)        # discards, citations, lawsuits
        # "Before the bidding window closes" is not a closure.
        self.assertEqual(severity(rule(7, "erate_form470_wait")), 2)
        # "determinations" is not a termination.
        self.assertNotEqual(severity(rule(40, "waste_determination")), 0)

    def test_why_lines_are_cut_from_the_cost_text_never_added_to(self):
        for industry_id in CATALOG:
            for r in top_checks(industry_id):
                line = why_line(r)
                self.assertTrue(line.endswith("."), r.key)
                self.assertTrue(r.cost.startswith(line[:-1]), (r.key, line))
                self.assertLessEqual(len(line), len(r.cost))
        medical = next(r for r in CATALOG[1] if r.key == "medical_certificate")
        self.assertEqual(why_line(medical), "A driver without a valid medical card is placed out of service.")
        # A list is never cut short.
        minors = next(r for r in CATALOG[47] if r.key == "no_sales_under_21")
        self.assertEqual(why_line(minors), minors.cost)

    def test_public_page_lists_the_top_five_first_with_why(self):
        page = text(self.client.get("/industries/restoarmor"))
        top = top_checks(2)
        self.assertIn(f"Start with these {TOP_COUNT}", page)
        positions = [page.index(r.title) for r in top]
        self.assertEqual(positions, sorted(positions))
        rest_heading = page.index("The other 5")
        self.assertLess(positions[-1], rest_heading)
        for r in top:
            self.assertIn(f"Why this matters: {why_line(r)}", page)
        for r in rules_for(2):
            if r not in top:
                self.assertGreater(page.index(r.title), rest_heading)

    def test_app_page_shows_top_five_first_then_problems_on_top(self):
        self.signup(industries=(2,))
        page = text(self.client.get("/app/industry/2"))
        top = top_checks(2)
        positions = [page.index(f"{r.title} No reading") for r in top]
        others = [page.index(f"{r.title} No reading") for r in rules_for(2) if r not in top]
        self.assertEqual(positions, sorted(positions))
        self.assertLess(max(positions), min(others))
        self.assertIn(f"Top {TOP_COUNT} · #1 Why this matters: {why_line(top[0])}", page)
        # A blocked check that isn't a top one still comes first.
        self.change(2, "overtime_pay", answer="no")
        page = text(self.client.get("/app/industry/2"))
        self.assertLess(page.index("Overtime paid over 40 hours Blocked"), page.index(top[0].title))


class TestSignUp(AppTestCase):
    def form(self, **extra):
        data = {"name": "Pat", "email": "pat@example.com", "password": PASSWORD, "org_name": "Pat's Diner",
                "timezone": "America/Los_Angeles", "industries": ["1", "2"]}
        data.update(extra)
        return data

    def test_a_new_workspace_opens_on_its_industry_page(self):
        r = self.post("/signup", self.form())
        self.assertEqual(r.status_code, 302)
        self.assertTrue(r.headers["Location"].endswith("/app/industry/1"))
        page = text(self.client.get(r.headers["Location"]))
        self.assertIn(f"Start with the top {TOP_COUNT} checks below", page)

    def test_from_an_industry_page_it_opens_that_industry(self):
        page = self.client.get("/signup?industry=2").data.decode()
        self.assertIn('name="start" value="2"', page)
        self.assertIn('value="2" checked', page)
        r = self.post("/signup", self.form(start="2"))
        self.assertTrue(r.headers["Location"].endswith("/app/industry/2"))

    def test_a_start_industry_not_picked_is_ignored(self):
        r = self.post("/signup", self.form(start="7"))
        self.assertTrue(r.headers["Location"].endswith("/app/industry/1"))
        self.post("/logout")
        r = self.post("/signup", self.form(email="b@example.com", start="99999999999999999999"))
        self.assertTrue(r.headers["Location"].endswith("/app/industry/1"))

    def test_a_failed_sign_up_keeps_the_start_industry(self):
        r = self.post("/signup", self.form(start="2", password="short"))
        self.assertEqual(r.status_code, 400)
        self.assertIn('name="start" value="2"', r.data.decode())

    def test_timezone_comes_from_the_browser_until_the_person_picks_one(self):
        page = self.client.get("/signup").data.decode()
        self.assertIn("data-auto-timezone", page)
        self.assertIn("/static/signup.js", page)
        # Re-shown after an error, the person's own choice stays.
        r = self.post("/signup", self.form(password="short"))
        self.assertNotIn("data-auto-timezone", r.data.decode())
        # A zone the browser names but the list lacks is accepted.
        r = self.post("/signup", self.form(timezone="America/Boise"))
        self.assertEqual(r.status_code, 302)

    def test_invited_people_still_land_on_the_overview(self):
        from omniarmor_app.auth import create_invite
        self.signup()
        with self.app.test_request_context():
            from omniarmor_app.db import get_db
            link = create_invite(get_db(), 1, 1)
        self.post("/logout")
        r = self.signup(email="mate@example.com", invite=link.rsplit("invite=", 1)[1], name="Mate")
        self.assertTrue(r.headers["Location"].endswith("/app"))


class TestGettingStarted(AppTestCase):
    """The overview's getting-started list: pick the checklists, complete the
    first check, set the first reminder, then invite a teammate or choose the
    reminder emails. Ticked from what is saved; gone once all four are done."""

    def overview(self):
        return text(self.client.get("/app"))

    def test_it_ticks_itself_from_what_is_saved_and_goes_away(self):
        self.signup(industries=(2,))
        page = self.overview()
        self.assertIn("Getting started · 1 of 4 done", page)
        self.assertIn("Pick your checklists : done · RestoArmor", page)
        self.assertIn("Complete your first check : not done yet", page)
        self.assertIn(f"Open {top_checks(2)[0].title}", page)
        self.change(2, "overtime_pay", answer="yes")
        page = self.overview()
        self.assertIn("Getting started · 2 of 4 done", page)
        self.assertIn("Complete your first check : done", page)
        self.assertIn("Set your first reminder : not done yet", page)
        r = self.change(2, "date_marking", date=(date.today() - timedelta(days=2)).isoformat())
        self.assertEqual(r.status_code, 302)
        self.assertIn("Getting started · 3 of 4 done", self.overview())
        self.post("/app/settings/reminders", {"email_reminders": "on", "email_alerts": "on"})
        self.assertNotIn("Getting started", self.overview())
        # Clearing the only reading brings its steps back: the list follows what is saved.
        self.change(2, "overtime_pay", action="clear")
        self.change(2, "date_marking", action="clear")
        self.assertIn("Getting started · 2 of 4 done", self.overview())

    def test_an_invite_link_ticks_the_last_step(self):
        self.signup(industries=(2,))
        self.assertIn("Invite a teammate or choose your reminder emails : not done yet", self.overview())
        self.post("/app/settings/invite")
        self.assertIn("Invite a teammate or choose your reminder emails : done", self.overview())


class TestEmptyStates(AppTestCase):
    def test_overview_points_to_the_next_check(self):
        self.signup(industries=(2,))
        page = text(self.client.get("/app"))
        first = top_checks(2)[0]
        self.assertIn("Checks that are overdue or close to a limit will show here. None of your checks has a reading"
                      f" yet, so start with {first.title} in RestoArmor. Open {first.title}", page)
        self.assertNotIn("Nice work", page)
        dated = next(r for r in sorted(rules_for(2), key=lambda r: top_rank(2, r.key) or 99) if date_mode(r))
        self.assertIn("Deadlines in the next 60 days will show here once a check counted from a date has its date,"
                      f" such as {dated.title} in RestoArmor. Open {dated.title}", page)
        self.change(2, "overtime_pay", answer="yes")
        page = text(self.client.get("/app"))
        self.assertIn("Nothing blocked or close to a limit in the 1 check with a reading. 9 still need one;"
                      f" next up: {first.title} in RestoArmor", page)

    def test_a_deadline_past_sixty_days_is_named(self):
        self.signup(industries=(1,))
        self.change(1, "annual_mvr_review", action="done_today")
        page = text(self.client.get("/app"))
        self.assertIn("No tracked deadlines in the next 60 days. The next one is Annual driving record review in"
                      " FleetArmor, due", page)

    def test_only_problems_with_nothing_entered_says_why(self):
        self.signup(industries=(2,))
        page = text(self.client.get("/app/industry/2?only=problems"))
        self.assertIn("Checks that are overdue or close to a limit will show here. No RestoArmor check has a reading"
                      f" yet: start with the top {TOP_COUNT}. Show all checks", page)
        self.change(2, "overtime_pay", answer="yes")
        page = text(self.client.get("/app/industry/2?only=problems"))
        self.assertIn("No problems in RestoArmor right now. 9 checks still need a first reading: Show all checks",
                      page)

    def test_radar_points_to_a_dated_check(self):
        self.signup(industries=(2,))
        page = text(self.client.get("/app/notifications"))
        self.assertIn("Every reminder email sent to your team will show here. They start once a check counted from a"
                      " date has its date, such as", page)

    def test_the_trial_starts_with_the_workspace_not_the_first_learner(self):
        self.signup(industries=(2,))
        page = text(self.client.get("/app/academy"))
        self.assertIn(f"Free trial: {self.app.config['ACADEMY_TRIAL_DAYS']} days of the full Academy left", page)
        self.assertNotIn("The first one starts your free", page)


class TestPlainQuestions(AppTestCase):
    """Every check's question and what-to-do text in plain words. The words
    changed; the way each check is counted, its limits and its citation did
    not (test_rule_dates checks those against the handbook)."""

    LEGALESE = re.compile(r"\be\.g\.|\bi\.e\.|prior to|utiliz|consecutive|\bensure\b|commenc|pursuant|in accordance"
                          r"|aggregated|effluent|thereof|herein|\bshall\b|\bvia\b|properly executed|rendered", re.I)

    def test_no_legalese_in_questions_or_actions(self):
        for industry_id, rules in CATALOG.items():
            for r in rules:
                for field in ("input", "action"):
                    self.assertIsNone(self.LEGALESE.search(getattr(r, field)), (industry_id, r.key, field))

    def test_yes_no_checks_ask_a_question(self):
        for rules in CATALOG.values():
            for r in rules:
                if r.kind in ("required", "forbidden"):
                    self.assertIn("?", r.input, r.key)

    def test_every_way_of_counting_is_kept(self):
        from collections import Counter
        from omniarmor_app.catalog import counts_first_day, date_unit
        counted = Counter((date_unit(r), date_mode(r)) for rules in CATALOG.values() for r in rules)
        self.assertEqual(counted, Counter({(None, None): 333, ("days", "since"): 134, ("hours", "since"): 22,
                                           ("business days", "since"): 16, ("months", "since"): 15,
                                           ("days", "until"): 14, ("calendar months", "since"): 3,
                                           ("minutes", "since"): 2, ("years", "since"): 1}))
        self.assertEqual(sum(counts_first_day(r) for rules in CATALOG.values() for r in rules), 1)

    def test_abbreviations_are_spelled_out_where_they_are_asked(self):
        def asks(i, key):
            return next(r for r in CATALOG[i] if r.key == key).input
        self.assertIn("temperature control for safety (TCS food)", asks(2, "cold_holding"))
        self.assertIn("protected health information (PHI)", asks(5, "breach_notification_60_days"))
        self.assertIn("suspicious activity report (SAR)", asks(18, "sar_filing_deadline"))
        self.assertIn("10 hours in a row off duty", asks(1, "hos_11_hour"))
