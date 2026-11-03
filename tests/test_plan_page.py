"""The Academy plan page explains each plan from the code's real limits and
prices: nothing on it is a number typed by hand."""

import html
import os
import re
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_webapp import AppTestCase  # noqa: E402

from omniarmor_app import academy, academy_plan  # noqa: E402
from omniarmor_app.academy_views import plan_facts  # noqa: E402
from omniarmor_app.catalog import INDUSTRIES, rules_for  # noqa: E402

TEMPLATES = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "omniarmor_app", "templates")


def words(page):
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", page)).split())


class TestPlanPage(AppTestCase):
    def setUp(self):
        super().setUp()
        self.signup()

    def page(self):
        response = self.client.get("/app/academy/plan")
        self.assertEqual(response.status_code, 200)
        return words(response.data.decode())

    def test_every_fact_comes_from_the_code(self):
        text = self.page()
        free_track = academy.TRACKS[academy_plan.FREE_TRACK]
        free_worlds = [academy.world(n) for n in sorted(academy_plan.FREE_WORLDS)]
        expected = [
            f"up to {academy.MAX_LEARNERS} kids",
            f"Up to {academy.MAX_LEARNERS} learners",
            f"{self.app.config['ACADEMY_TRIAL_DAYS']}-day free trial",
            f"All {sum(len(rules_for(i)) for i in INDUSTRIES)} checks across {len(INDUSTRIES)} industries",
            f"{free_track.name} track: its first {len(free_worlds)} worlds, "
            + ", ".join(w.title for w in free_worlds)
            + f", with all {'{:,}'.format(len(free_worlds) * free_track.topic_stages)} of their levels",
            f"Up to {academy.MAX_FRIENDS} friends each",
            f"All {len(academy.TOPIC_WORLDS)} business worlds",
            f"{len(academy.INDUSTRY_WORLDS)} industry Rule Quests",
            f"Duels in all {len(academy.DUEL_WORLDS)} duel worlds",
            "Price shown at checkout",
        ]
        expected += [f"{t.name} ({t.level}): {'{:,}'.format(t.total)} levels" for t in academy.TRACK_LIST]
        for fact in expected:
            self.assertIn(fact, text)

    def test_a_changed_setting_changes_the_page(self):
        self.app.config.update(ACADEMY_TRIAL_DAYS=30, ACADEMY_PRICE_LABEL="$7 a month")
        with mock.patch.object(academy, "MAX_LEARNERS", 5), mock.patch.object(academy, "MAX_FRIENDS", 9):
            text = self.page()
        for fact in ("30-day free trial", "$7 a month", "up to 5 kids", "Up to 5 learners", "Up to 9 friends each"):
            self.assertIn(fact, text)
        self.assertNotIn("Price shown at checkout", text)
        self.assertNotIn("14-day", text)

    def test_the_facts_match_what_the_plan_allows(self):
        with self.app.app_context():
            facts = plan_facts(self.app.config)
        free_org = {"academy_status": "none", "academy_trial_ends": None, "academy_ends_at": None,
                    "academy_renews_at": None}
        free_track = facts["free_track"]
        for w in free_track.worlds:
            self.assertEqual(academy_plan.allows(free_org, free_track, w), w in facts["free_worlds"], w.title)
        for t in facts["tracks"]:
            if t.key != free_track.key:
                self.assertFalse(any(academy_plan.allows(free_org, t, w) for w in t.worlds), t.name)
        self.assertEqual(facts["free_levels"], sum(free_track.stages(w) for w in facts["free_worlds"]))

    def test_no_number_is_typed_into_the_page(self):
        for name in ("academy/plan.html",):
            with open(os.path.join(TEMPLATES, name)) as f:
                source = f.read()
            text = re.sub(r"\{\{.*?\}\}|\{%.*?%\}|\{#.*?#\}", "", source, flags=re.S)
            text = re.sub(r"<[^>]*>", " ", text)    # the words a person reads, not the tags
            self.assertIsNone(re.search(r"\d", text), re.search(r".{0,30}\d.{0,30}", text) and re.search(r".{0,30}\d.{0,30}", text).group(0))

    def test_the_academy_pages_say_the_free_part_from_the_code(self):
        self.post("/app/academy/learners", {"nickname": "Sam", "avatar": "rocket"})
        with self.db() as conn:
            conn.execute("UPDATE orgs SET academy_trial_ends = '2000-01-01T00:00:00+00:00'")
            conn.commit()
        free = f"the first {len(academy_plan.FREE_WORLDS)} worlds of {academy.TRACKS[academy_plan.FREE_TRACK].name}"
        self.assertIn(free, words(self.client.get("/app/academy").data.decode()))
        with mock.patch.object(academy_plan, "FREE_WORLDS", {1, 2}):
            self.assertIn("the first 2 worlds of", words(self.client.get("/app/academy").data.decode()))
            self.assertIn("the first 2 Launchpad worlds", words(self.client.get("/app/academy/1").data.decode()))


if __name__ == "__main__":
    unittest.main()
