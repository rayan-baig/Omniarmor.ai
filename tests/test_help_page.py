"""The Help page: real questions, answers that match the code, and the same
public-page handling as the Terms and Privacy pages (listed, in the sitemap,
open to search engines, linked from the landing page and the app)."""

import html
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_webapp import AppTestCase  # noqa: E402

from omniarmor_app import PUBLIC_PAGES, academy, academy_plan  # noqa: E402
from omniarmor_app.academy_views import JOIN_CODE_DAYS  # noqa: E402
from omniarmor_app.auth import RESET_HOURS  # noqa: E402
from omniarmor_app.autopilot import SLOT_MINUTES  # noqa: E402
from omniarmor_app.catalog import INDUSTRIES, TOP_COUNT, rules_for  # noqa: E402
from omniarmor_app.reminders import REMINDER_DAYS, reminder_window  # noqa: E402
from omniarmor_app.tracking import BULK_ACTIONS, LEVEL_LABEL  # noqa: E402

TEMPLATES = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "omniarmor_app", "templates")
TOPICS = ["trial", "prices", "check", "autopilot", "reminders", "choose", "academy", "download", "delete", "help"]


def words(page):
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", page)).split())


class TestHelpPage(AppTestCase):
    def page(self):
        response = self.client.get("/help")
        self.assertEqual(response.status_code, 200)
        return response.get_data(as_text=True)

    def test_twelve_to_fifteen_questions_with_a_list_of_them(self):
        page = self.page()
        questions = re.findall(r'<h2 id="([a-z-]+)">(.*?)</h2>', page)
        self.assertTrue(12 <= len(questions) <= 15, len(questions))
        for anchor, question in questions:
            self.assertTrue(question.endswith("?"), question)
            self.assertIn(f'<a href="#{anchor}">{question}</a>', page)
        for topic in TOPICS:
            self.assertIn(topic, [a for a, _ in questions])

    def test_the_answers_match_the_code(self):
        text = words(self.page())
        cfg = self.app.config
        free_track = academy.TRACKS[academy_plan.FREE_TRACK]
        expected = [
            f"{cfg['ACADEMY_TRIAL_DAYS']}-day free trial",
            f"the {free_track.name} track's first {len(academy_plan.FREE_WORLDS)} worlds stay free",
            f"all {sum(len(rules_for(i)) for i in INDUSTRIES)} checks across {len(INDUSTRIES)} industries",
            f"up to {academy.MAX_LEARNERS}, on all {len(academy.TRACK_LIST)} tracks",
            f"Each industry has {len(rules_for(1))} checks",
            f"Start with the top {TOP_COUNT}",
            f"after {cfg['DAILY_JOB_HOUR_UTC']:02d}:00 UTC",
            f"{', '.join(str(d) for d in REMINDER_DAYS[:-1])} or {REMINDER_DAYS[-1]} day",
            f"Every {SLOT_MINUTES} minutes it checks OmniArmor over",
            f"works once, for {JOIN_CODE_DAYS} days",
            f"for {RESET_HOURS} hour",
            f"about {cfg['BACKUP_KEEP']} days",
            f"{len(academy.TOPIC_WORLDS)} business worlds",
            f"{len(academy.INDUSTRY_WORLDS)} industry Rule Quests",
            "{:,} to {:,} levels".format(min(t.total for t in academy.TRACK_LIST),
                                         max(t.total for t in academy.TRACK_LIST)),
            "the price is shown at checkout",
        ]
        expected += [LEVEL_LABEL[level] for level in ("CLEARED", "WARNING", "BLOCKED", "NONE")]
        expected += list(BULK_ACTIONS.values())
        for fact in expected:
            self.assertIn(fact, text)
        # The reminder days are the ones the reminders really use.
        for day in REMINDER_DAYS:
            self.assertEqual(reminder_window(day), f"due-in-{day}")
            self.assertNotEqual(reminder_window(day + 1), f"due-in-{day}")
        self.assertIsNone(reminder_window(max(REMINDER_DAYS) + 1))
        self.assertEqual(reminder_window(0), "due-today")
        self.assertEqual(reminder_window(-1), reminder_window(-7))
        self.assertNotEqual(reminder_window(-7), reminder_window(-8))   # weekly while overdue

    def test_changed_settings_change_the_answers(self):
        self.app.config.update(ACADEMY_TRIAL_DAYS=21, ACADEMY_PRICE_LABEL="$6 a month", DAILY_JOB_HOUR_UTC=7,
                               BACKUP_KEEP=30)
        text = words(self.page())
        for fact in ("21-day free trial", "Academy plan: $6 a month.", "after 07:00 UTC", "about 30 days"):
            self.assertIn(fact, text)
        self.assertNotIn("Write to us", text)
        self.app.config["SUPPORT_EMAIL"] = "help@example.com"
        self.assertIn('href="mailto:help@example.com"', self.page())

    def test_no_number_is_typed_into_the_page(self):
        with open(os.path.join(TEMPLATES, "help.html")) as f:
            source = f.read()
        text = re.sub(r"\{\{.*?\}\}|\{%.*?%\}|\{#.*?#\}", "", source, flags=re.S)
        text = re.sub(r"<[^>]*>", " ", text)
        found = re.search(r".{0,30}\d.{0,30}", text)
        self.assertIsNone(found, found and found.group(0))

    def test_a_public_page_like_terms_and_privacy(self):
        self.assertIn("public.help", PUBLIC_PAGES)
        response = self.client.get("/help")
        self.assertNotIn("X-Robots-Tag", response.headers)
        page = response.get_data(as_text=True)
        self.assertNotIn('name="robots"', page)
        self.assertIn('<link rel="canonical" href="https://omniarmor.test/help">', page)
        self.assertIn('<meta property="og:title" content="Help and questions · OmniArmor.ai">', page)
        self.assertIn("<loc>https://omniarmor.test/help</loc>", self.client.get("/sitemap.xml").get_data(as_text=True))
        robots = self.client.get("/robots.txt").get_data(as_text=True)
        self.assertFalse(any(line.startswith("Disallow: /help") for line in robots.splitlines()))

    def test_linked_from_the_landing_page_and_the_app(self):
        self.assertIn('href="/help"', self.client.get("/").get_data(as_text=True))
        self.signup()
        for path in ("/app", "/app/settings", "/app/industry/1", "/app/academy"):
            self.assertIn('href="/help"', self.client.get(path).get_data(as_text=True), path)
        # Signed in, it is still the same page, with the app around it.
        self.assertIn("Questions and answers", self.page())


if __name__ == "__main__":
    unittest.main()
