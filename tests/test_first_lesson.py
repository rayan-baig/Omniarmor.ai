"""A brand-new kid's first lesson, walked end to end the way a family meets
it, counting every step a person takes: each link or button pressed, each
box typed in, each lesson card moved past and each answer picked.

From a grown-up's first sign-in to the first lesson's results it used to take
15 steps: open the Academy, type a nickname, Start learning, a track page
(Let's go!), the map (Continue), 4 lesson cards, 5 answers, Check my answers.
Picking the track now sits on the add form, already set to Launchpad, and
Start learning opens the first lesson itself: 13 steps. A kid joining on
their own device lands on their first lesson too.
"""

import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from e2e_helpers import parse, post_forms  # noqa: E402
from test_webapp import AppTestCase  # noqa: E402

from omniarmor_app import academy  # noqa: E402

STEPS_BEFORE = 15
MOST_STEPS = 13


class Walk:
    """A person going through the app: every action they take is one step."""

    def __init__(self, case, client):
        self.case, self.client, self.steps, self.log = case, client, 0, []

    def step(self, what):
        self.steps += 1
        self.log.append(what)

    def open(self, url):
        response = self.client.get(url)
        while response.status_code in (301, 302, 303):
            response = self.client.get(response.headers["Location"])
        self.case.assertEqual(response.status_code, 200, url)
        self.url, self.page = url, response.data.decode()
        return self.page

    def click(self, pattern, what):
        href = next((h for h in parse(self.page).links if re.fullmatch(pattern, h)), None)
        self.case.assertIsNotNone(href, f"no link for {what} on {self.url}")
        self.step(what)
        return self.open(href)

    def submit(self, form, data, what):
        self.step(what)
        response = self.client.post(form.action or self.url, data=data)
        self.case.assertIn(response.status_code, (200, 302, 303), what)
        if response.status_code == 200:
            self.page = response.data.decode()
            return self.page
        return self.open(response.headers["Location"])


class TestFirstLesson(AppTestCase):
    def test_a_new_kids_first_lesson_is_short(self):
        self.signup()
        walk = Walk(self, self.client)
        walk.open("/app")
        walk.click(r"/app/academy", "open the Academy")

        add = next(f for f in post_forms(walk.page) if f.field("nickname") is not None)
        data = add.values()
        self.assertEqual(data.get("track"), "launchpad", "the track is chosen for them unless they change it")
        walk.step("type a nickname")
        data["nickname"] = "Captain Sam"
        walk.submit(add, data, "Start learning")

        # Steps the walk takes only if the app still puts them in the way.
        if "/track" in walk.url:
            track = post_forms(walk.page)[-1]
            walk.submit(track, track.values(), "Let's go! on the track page")
        if re.fullmatch(r"/app/academy/\d+", walk.url):
            walk.click(r"/app/academy/\d+/world/\d+/stage/1", "Continue on the map")
        if re.fullmatch(r"/app/academy/\d+/world/\d+", walk.url):
            walk.click(r"/app/academy/\d+/world/\d+/stage/1", "Start on the world page")

        match = re.fullmatch(r"/app/academy/(\d+)/world/(\d+)/stage/1", walk.url)
        self.assertIsNotNone(match, f"not on a first lesson: {walk.url}")
        learner_id, world_number = int(match.group(1)), int(match.group(2))
        self.assertEqual(world_number, academy.TRACKS["launchpad"].topic_worlds[0].number)
        cards = walk.page.count("data-card>")
        self.assertGreaterEqual(cards, 3, "the lesson still teaches")
        for n in range(cards):
            walk.step("Next" if n < cards - 1 else "Start the quiz!")

        # The answers, worked out here from the same seed the server uses.
        quiz = next(f for f in post_forms(walk.page) if f.field("attempt") is not None)
        questions = academy.quiz(academy.TRACKS["launchpad"], world_number, 1, "Acme Logistics", [1, 18],
                                 academy.attempt_seed(learner_id, "launchpad", world_number, 1, 1))
        data = quiz.values()
        for i, q in enumerate(questions):
            walk.step(f"answer question {i + 1}")
            data[f"q{i}"] = str(q.answer)
        walk.submit(quiz, data, "Check my answers")
        self.assertIn("Stage complete!", walk.page.replace("Perfect score!", "Stage complete!"))

        print(f"\nFirst lesson: {walk.steps} steps (was {STEPS_BEFORE}): " + ", ".join(walk.log), file=sys.stderr)
        self.assertLessEqual(walk.steps, MOST_STEPS, walk.log)

    def test_a_kid_joining_on_their_own_device_starts_with_the_lesson(self):
        self.signup()
        self.post("/app/academy/learners", {"nickname": "Kiddo", "avatar": "rocket", "armo": "sweet",
                                            "track": "launchpad"})
        self.post("/app/academy/1/join-code")
        with self.db() as conn:
            code = conn.execute("SELECT code FROM join_codes").fetchone()["code"]
        kid = self.app.test_client()
        response = self.post("/kids", {"code": code}, client=kid)
        first = academy.TRACKS["launchpad"].topic_worlds[0].number
        self.assertTrue(response.headers["Location"].endswith(f"/app/academy/1/world/{first}/stage/1"))
        self.assertEqual(kid.get(response.headers["Location"]).status_code, 200)

    def test_a_kid_with_progress_joins_to_their_map(self):
        self.signup()
        self.post("/app/academy/learners", {"nickname": "Kiddo", "avatar": "rocket", "armo": "sweet"})
        with self.db() as conn:
            conn.execute("INSERT INTO learner_progress (learner_id, level, attempts, best_score, best_stars)"
                         " VALUES (1, ?, 1, 5, 3)", (academy.level_id(academy.TRACKS["launchpad"], 1, 1),))
            conn.commit()
        self.post("/app/academy/1/join-code")
        with self.db() as conn:
            code = conn.execute("SELECT code FROM join_codes").fetchone()["code"]
        response = self.post("/kids", {"code": code}, client=self.app.test_client())
        self.assertTrue(response.headers["Location"].endswith("/app/academy/1"))

    def test_the_add_form_can_pick_another_track(self):
        self.signup()
        response = self.post("/app/academy/learners", {"nickname": "Kiddo", "avatar": "rocket", "armo": "sweet",
                                                       "track": "summit"})
        first = academy.TRACKS["summit"].topic_worlds[0].number
        self.assertTrue(response.headers["Location"].endswith(f"/app/academy/1/world/{first}/stage/1"))
        with self.db() as conn:
            row = conn.execute("SELECT track, track_chosen FROM learners").fetchone()
        self.assertEqual((row["track"], row["track_chosen"]), ("summit", 1))

    def test_a_bad_track_adds_nobody(self):
        self.signup()
        self.post("/app/academy/learners", {"nickname": "Kiddo", "avatar": "rocket", "armo": "sweet",
                                            "track": "moon"})
        with self.db() as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM learners").fetchone()[0], 0)


if __name__ == "__main__":
    unittest.main()
