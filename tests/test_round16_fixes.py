"""1.28.0: what a strict sixteenth review asked for.

Settings: saving the reminder emails (and Connections' and Locations' notices) said how it went at the top of the
page, out of sight on a phone where the page opens at that section; now each shows under its own heading. Reminders,
empty, says when the first digest goes out once a check counted from a date has its date. Adding students goes back
to the class page (post-redirect-get). A learner who hasn't played yet is welcomed, not welcomed back. The public home's
feature cards say what How it works doesn't, and the pricing page says "monthly or yearly" only where yearly is
offered. Armo steps away where even tucked he would cover the page's words. Pilot's answers with no key are in
tests/js (tests/test_pilot.py runs them)."""

import html
import os
import re
import sys
import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from markupsafe import escape

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_classroom_review import SchoolCase  # noqa: E402
from test_webapp import AppTestCase  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESTO = 2


def words(page):
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", page)).split())


def between(page, start, end):
    begin = page.index(start)
    return page[begin:page.index(end, begin)]


def read(*parts):
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as f:
        return f.read()


def top_of(page):
    return page[:page.index('<div class="page-head">')]


# --- 1. Settings: each section's notice under its own heading ---------------------------------------------------

class TestSettingsNoticesInTheirSections(AppTestCase):
    def setUp(self):
        super().setUp()
        self.signup(industries=(RESTO,))
        self.client.get("/app")    # the welcome notice is read here, so Settings starts with none

    def settings(self):
        return self.client.get("/app/settings").data.decode()

    def assert_under(self, page, section, heading_id, notice, kind):
        self.assertNotIn(notice, words(top_of(page)), "not at the top of the page, out of sight on a phone")
        part = page[page.index(f'<h2 id="{heading_id}">'):]
        part = part[:part.index("<h2", 4)]
        self.assertIn(f"data-{section}-note", part)
        self.assertIn(f'<li class="flash {kind}">{escape(notice)}</li>', part)
        self.assertEqual(words(page).count(notice), 1, "said once")

    def test_saving_reminder_emails_says_so_under_your_reminder_emails(self):
        got = self.post("/app/settings/reminders", {"email_reminders": "on"})
        self.assertTrue(got.headers["Location"].endswith("/app/settings#reminders"))
        self.assert_under(self.settings(), "reminders", "reminders", "Saved: Daily digest on, time-limit alerts off.", "ok")
        self.assertNotIn("data-reminders-note", self.settings(), "shown once")

    def test_connections_notices_show_under_connections(self):
        got = self.post("/app/settings/connections/cyberlogix/revoke")
        self.assertTrue(got.headers["Location"].endswith("/app/settings#connections"))
        self.assert_under(self.settings(), "connections", "connections",
                          "There is no active Kryozyn connection key to revoke.", "error")
        self.post("/app/settings/connections/cyberlogix/create")
        self.post("/app/settings/connections/cyberlogix/create")
        self.assert_under(self.settings(), "connections", "connections",
                          "This workspace already has a Kryozyn connection key. Regenerate it to get a new one.", "error")
        self.post("/app/settings/connections/cyberlogix/revoke")
        self.assert_under(self.settings(), "connections", "connections", "The Kryozyn connection key was revoked."
                          " Kryozyn can't send reports until you create a new one.", "ok")

    def test_a_location_notice_shows_under_locations(self):
        got = self.post("/app/settings/locations/add", {"name": "   "})
        self.assertTrue(got.headers["Location"].endswith("/app/settings#locations"))
        self.assert_under(self.settings(), "locations", "locations", "Enter the new location's name, without line breaks.",
                          "error")

    def test_a_section_the_page_doesnt_show_leaves_its_notice_at_the_top(self):
        # No temperature check, no bundle: no Connections section, so its notice can't be lost.
        self.post("/app/settings/company", {"name": "Acme Logistics", "timezone": "America/New_York", "industries": ["1"]})
        self.client.get("/app/settings")
        self.post("/app/settings/connections/cyberlogix/revoke")
        page = self.settings()
        self.assertNotIn('<h2 id="connections">', page)
        self.assertIn("There is no active Kryozyn connection key to revoke.", words(top_of(page)))

    def test_the_password_notice_still_shows_under_your_password(self):
        self.post("/app/settings/password", {"current_password": "not my password", "new_password": "a brand new one"})
        self.assert_under(self.settings(), "password", "password", "That isn't your current password. Nothing was changed.",
                          "error")


# --- 5a. Reminders, empty: when the first digest goes out ------------------------------------------------------

class TestFirstDigest(AppTestCase):
    def setUp(self):
        super().setUp()
        self.signup(industries=(RESTO,))
        from omniarmor_app.catalog import find_rule
        self.food = find_rule(RESTO, "date_marking").title

    def today(self):
        from omniarmor_app.tracking import org_today
        with self.db() as conn:
            return org_today(conn.execute("SELECT * FROM orgs").fetchone())

    def first(self, now, ran=False):
        from omniarmor_app.reminders import first_digest
        from omniarmor_app.tracking import states_for_org
        with self.db() as conn:
            org = conn.execute("SELECT * FROM orgs").fetchone()
            if ran:
                conn.execute("INSERT INTO job_runs (job, run_date, started_at) VALUES ('daily', ?, ?)",
                             (now.date().isoformat(), now.isoformat()))
                conn.commit()
            # 1.29.0: at the moment asked for (it used the clock, so this failed after the daily job's hour).
            return first_digest(conn, self.app.config, org, states_for_org(conn, org), now=now)

    def test_before_any_date_it_says_they_start_once_one_has_its_date(self):
        page = words(self.client.get("/app/notifications").data.decode())
        self.assertIn("They start once a check counted from a date has its date", page)
        self.assertIsNone(self.first(datetime.now(timezone.utc)))

    def test_with_a_date_it_says_when_the_first_digest_goes_out(self):
        self.post(f"/app/industry/{RESTO}/rule/date_marking/entries",
                  {"action": "add", "label": "Soup base", "date": self.today().isoformat()})
        page = words(self.client.get("/app/notifications").data.decode())
        self.assertNotIn("They start once", page)
        self.assertIn("The first daily digest goes out on", page)
        self.assertIn(f"for {self.food} in RestoArmor, due ", page)
        self.assertIn("to everyone on the team with the daily digest on.", page)
        at, state = self.first(datetime.now(timezone.utc))
        self.assertIn(f"goes out on {at:%Y-%m-%d} at about {at:%H:%M} (America/New York)", page)
        self.assertEqual(state.rule.key, "date_marking")

    def test_it_matches_the_daily_job_s_schedule(self):
        hour = self.app.config["DAILY_JOB_HOUR_UTC"]
        self.post(f"/app/industry/{RESTO}/rule/date_marking/entries",
                  {"action": "add", "label": "Soup base", "date": self.today().isoformat()})
        # Due within 30 days: the next run. Before the hour, today's; after it, if today's has run, tomorrow's.
        early = datetime.now(timezone.utc).replace(hour=max(hour - 2, 0), minute=5, second=0, microsecond=0)
        at, _ = self.first(early)
        if hour >= 2:
            self.assertEqual(at.astimezone(timezone.utc), early.replace(hour=hour, minute=0))
        late = early.replace(hour=min(hour + 2, 23))
        at, _ = self.first(late, ran=True)
        self.assertEqual(at.astimezone(timezone.utc), (late + timedelta(days=1)).replace(hour=hour, minute=0))
        # Due in more than 30 days: the run on the morning it is 30 days from due, in the workspace's time zone.
        from omniarmor_app.reminders import first_digest
        with self.db() as conn:
            org = conn.execute("SELECT * FROM orgs").fetchone()
            far = [SimpleNamespace(mode="since", days_left=45, due_date=self.today() + timedelta(days=45))]
            at, _ = first_digest(conn, self.app.config, org, far, now=late)
        self.assertEqual(at.date(), self.today() + timedelta(days=15))
        self.assertEqual(at.astimezone(timezone.utc).hour, hour)

    def test_paused_it_says_so(self):
        self.post(f"/app/industry/{RESTO}/rule/date_marking/entries",
                  {"action": "add", "label": "Soup base", "date": self.today().isoformat()})
        with self.db() as conn:
            conn.execute("UPDATE orgs SET academy_trial_ends = ?", ("2020-01-01T00:00:00+00:00",))
            conn.commit()
        page = words(self.client.get("/app/notifications").data.decode())
        self.assertIn("Reminder emails are paused while this workspace has no plan.", page)
        self.assertNotIn("The first daily digest goes out on", page)


# --- 5c. and 5d. The public home's cards and the pricing page ---------------------------------------------------

class TestPublicCopy(AppTestCase):
    def test_the_feature_cards_dont_repeat_how_it_works(self):
        page = self.client.get("/").data.decode()
        steps = words(between(page, 'data-how-it-works="biz"', "</section>"))
        cards = words(between(page, '<section class="features"', "</section>"))
        self.assertNotIn("Deadlines that count themselves", cards)
        self.assertNotIn("Reminders before it's late", cards)
        self.assertNotIn("30, 7 and 1 day", cards)
        self.assertIn("30, 7 and 1 day", steps)
        self.assertIn("Days, business days or hours", cards)
        self.assertIn("Form I-9 in 3 business days", cards)
        self.assertIn("Everyone picks their emails", cards)
        self.assertEqual(page.count('<section class="features"'), 1)
        self.assertEqual(len(re.findall(r"<h3>", between(page, '<section class="features"', "</section>"))), 5)

    def test_the_pricing_page_says_yearly_only_where_it_is_offered(self):
        for key in ("PRO_YEARLY_STRIPE_PRICE", "PLUS_YEARLY_STRIPE_PRICE", "PLUS_BUNDLE_UPGRADE_YEARLY_STRIPE_PRICE"):
            self.app.config[key] = ""
        page = words(self.client.get("/pricing").data.decode())
        self.assertIn("Every detail (the trial, monthly billing, pausing and cancelling) is in Help", page)
        self.assertNotIn("monthly or yearly", page)
        self.app.config["PRO_YEARLY_STRIPE_PRICE"] = "price_test_pro_year"
        page = words(self.client.get("/pricing").data.decode())
        self.assertIn("Every detail (the trial, monthly or yearly billing, pausing and cancelling) is in Help", page)


# --- 5e. and 5f. Adding students, and a new learner's first map --------------------------------------------------

class TestAddingStudentsGoesBackToTheClassPage(SchoolCase):
    def setUp(self):
        super().setUp()
        self.teacher_signup()
        self.class_id = self.add_class()
        self.page_url = f"/app/academy/classes/{self.class_id}"

    def test_after_adding_the_address_is_the_class_page(self):
        got = self.add_students(self.class_id, ["Ava Thompson", "Liam"])
        self.assertIn(got.status_code, (302, 303))
        self.assertTrue(got.headers["Location"].endswith(self.page_url), got.headers["Location"])
        page = self.client.get(self.page_url).data.decode()
        self.assertIn("data-confirm-names", page, "the name to check waits on the class page, kept in the session")
        self.assertIn("Added 1 student to Room 12.", words(page))
        again = self.client.get(self.page_url)      # a reload
        self.assertEqual(again.status_code, 200)
        self.assertIn("data-confirm-names", again.data.decode(), "it waits until the teacher chooses")
        self.assertNotIn("Added 1 student", words(again.data.decode()))

    def test_what_wasnt_added_comes_back_once(self):
        got = self.add_students(self.class_id, ["Maya", "maya", "jo@example.com"])
        self.assertTrue(got.headers["Location"].endswith(self.page_url))
        page = self.client.get(self.page_url).data.decode()
        self.assertIn("maya: was typed twice", words(page))
        self.assertIn("jo@example.com: looks like an email address", words(page))
        box = re.search(r'<textarea name="names"[^>]*>(.*?)</textarea>', page, re.S).group(1)
        self.assertEqual(html.unescape(box).split("\n"), ["maya", "jo@example.com"])
        later = self.client.get(self.page_url).data.decode()
        self.assertNotIn("data-rejected", later)
        self.assertIsNone(re.search(r"\bmaya\b", re.search(r'<textarea name="names"[^>]*>(.*?)</textarea>', later, re.S).group(1)))

    def test_a_very_long_paste_is_shown_in_place(self):
        junk = ["x" * 200 + str(n) for n in range(10)]
        got = self.add_students(self.class_id, junk)
        self.assertEqual(got.status_code, 400)
        self.assertIn("is longer than", words(got.data.decode()))


class TestANewLearnerIsWelcomed(SchoolCase):
    def setUp(self):
        super().setUp()
        self.teacher_signup()
        class_id = self.add_class()
        self.add_students(class_id, ["Maya"])
        self.maya = self.students(class_id)["Maya"]

    def speech(self):
        page = self.client.get(f"/app/academy/{self.maya['id']}").data.decode()
        return words(between(page, '<div class="ac-speech">', "</div>"))

    def test_no_plays_yet_is_welcome_not_welcome_back(self):
        for _ in range(10):     # the greeting was picked at random
            said = self.speech()
            self.assertTrue(said.startswith("Welcome! Up next:"), said)
            self.assertIsNone(re.search(r"\bback\b", said))

    def test_after_a_play_armo_says_his_own_hello(self):
        from omniarmor_app import armo_lines
        with self.db() as conn:
            conn.execute("INSERT INTO learner_days (learner_id, day, levels, passed) VALUES (?, '2026-11-01', 1, 0)",
                         (self.maya["id"],))
            conn.commit()
        said = self.speech()
        hellos = [line for p in armo_lines.PERSONALITIES.values() for line in p.hello]
        self.assertTrue(any(said.startswith(f"{line} Up next:") for line in hellos), said)


# --- 3. Armo steps away where even tucked he would cover the page's words ---------------------------------------

class TestArmoStepsAway(unittest.TestCase):
    def test_tucked_and_still_over_words_he_steps_away(self):
        js = read("omniarmor_app", "static", "armo.js")
        self.assertIn('root.classList.remove("armo-tucked", "armo-away");', js)
        self.assertIn('classList.toggle("armo-tucked", busy())', js)
        self.assertIn('if (root.classList.contains("armo-tucked") && busy()) root.classList.add("armo-away");', js)
        # His bubble always shows him; when it closes he looks again.
        say = js[js.index("function say("):js.index("function hide(")]
        self.assertIn('root.classList.remove("armo-away")', say)
        self.assertIn("keepClear();", js[js.index("function hide("):js.index("function hide(") + 120])
        self.assertIn(".companion.armo-away{visibility:hidden}", read("omniarmor_app", "static", "app.css"))


# --- 5b. The pictures on the public pages ------------------------------------------------------------------------

class TestPictures(AppTestCase):
    def test_the_home_pictures_are_there_with_their_sizes(self):
        page = self.client.get("/").data.decode()
        for name in ("biz-overview", "biz-reminder"):
            m = re.search(rf'src="/static/shots/{name}\.webp[^"]*" width="(\d+)" height="(\d+)"', page)
            self.assertIsNotNone(m, name)
            self.assertGreater(int(m.group(1)), 400)
            self.assertGreater(int(m.group(2)), 400)


class TestVersion(unittest.TestCase):
    def test_version_and_changelog(self):
        from omniarmor_app.version import __version__
        self.assertGreaterEqual(tuple(map(int, __version__.split("."))), (1, 28, 0))
        log = read("CHANGELOG.md")
        section = log[log.index("## 1.28.0"):log.index("## 1.27.0")]
        for said in ("Your reminder emails", "Connections", "Locations", "yearly plan", "trial ends", "do first",
                     "Armo", "Needs attention", "first daily digest", "monthly or yearly", "Welcome"):
            self.assertIn(said, section)
        self.assertIn("**1.28.0**", read("docs", "PILOT.md"))


if __name__ == "__main__":
    unittest.main()
