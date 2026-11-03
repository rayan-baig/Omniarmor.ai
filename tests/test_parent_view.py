"""The grown-ups' progress report for one learner: lessons done, quiz scores
and certificates, and nobody outside the learner's own workspace sees it."""

import html
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_webapp import AppTestCase  # noqa: E402

from omniarmor_app import academy  # noqa: E402

BASIC = academy.TRACKS["launchpad"]


def words(page):
    """The page's text without its tags, as one line."""
    return " ".join(re.sub(r"<[^>]+>", " ", page).split())


class ProgressCase(AppTestCase):
    def setUp(self):
        super().setUp()
        self.signup()
        self.post("/app/academy/learners", {"nickname": "Sam", "avatar": "rocket", "track": "launchpad"})
        self.lid = 1
        self.url = f"/app/academy/{self.lid}/progress"

    def play(self, world_number, stage, right, client=None):
        """Plays a level with this many right answers."""
        questions = academy.quiz(BASIC, world_number, stage, "Acme Logistics", [1, 18],
                                 academy.attempt_seed(self.lid, "launchpad", world_number, stage, self.attempt(
                                     world_number, stage)))
        data = {"attempt": str(self.attempt(world_number, stage))}
        for i, q in enumerate(questions):
            data[f"q{i}"] = str(q.answer if i < right else (q.answer + 1) % len(q.options))
        return self.post(f"/app/academy/{self.lid}/world/{world_number}/stage/{stage}", data, client=client)

    def attempt(self, world_number, stage):
        with self.db() as conn:
            row = conn.execute("SELECT attempts FROM learner_progress WHERE learner_id = ? AND level = ?",
                               (self.lid, academy.level_id(BASIC, world_number, stage))).fetchone()
        return (row["attempts"] if row else 0) + 1

    def page(self, client=None):
        response = (client or self.client).get(self.url)
        self.assertEqual(response.status_code, 200)
        return html.unescape(response.data.decode())


class TestProgressReport(ProgressCase):
    def test_nothing_played_yet(self):
        page = self.page()
        self.assertIn("Sam's progress", page)
        self.assertIn("No lessons played yet", page)
        self.assertIn("0 of 1,350", page)
        self.assertIn("Not yet: pass stage 1 of the Owner's Challenge", page)

    def test_lessons_scores_and_tries(self):
        self.play(1, 1, right=5)            # 5 of 5: passed
        self.play(1, 2, right=1)            # 1 of 5: not passed
        self.play(1, 2, right=4)            # 4 of 5 on the second try: passed
        page = self.page()
        self.assertIn("Meet Your Company, stage 1", page)
        self.assertIn("Meet Your Company, stage 2", page)
        self.assertIn("5 of 5", page)
        self.assertIn("4 of 5", page)       # the best try, not the last or the first
        self.assertNotIn("1 of 5", page)
        self.assertIn("2 of 1,350", page)
        self.assertIn("2 lessons passed", words(page))
        self.assertIn("90%", page)          # (5/5 + 4/5) / 2
        rows = [r for r in page.split("<tr>") if "Meet Your Company, stage 2" in r]
        self.assertIn("<td>2</td>", rows[0])   # two tries

    def test_a_level_never_passed_says_so(self):
        self.play(1, 1, right=0)
        page = self.page()
        self.assertIn("0 of 5", page)
        self.assertIn("Not passed yet", page)
        self.assertIn("0 lessons passed", words(page))

    def test_certificates_on_every_track(self):
        with self.db() as conn:
            for track, n in ((BASIC, 1), (academy.TRACKS["summit"], 1)):
                levels = [academy.level_id(track, w, 1) for w in track.topics]
                levels.append(academy.level_id(track, academy.FINAL_WORLD.number, 1))
                conn.executemany("INSERT INTO learner_progress (learner_id, level, attempts, best_score, best_stars,"
                                 " completed_at) VALUES (?, ?, 1, 5, 3, '2026-02-01T12:00:00+00:00')",
                                 [(self.lid, level) for level in levels])
            conn.commit()
        page = self.page()
        self.assertIn("Future Owner", page)
        self.assertIn("Summit Future Owner", page)
        self.assertIn(f'href="/app/academy/{self.lid}/certificate"', page)   # the current track's
        self.assertIn("2026-02-01", page)

    def test_linked_from_the_academy_and_the_map(self):
        self.assertIn(f'href="{self.url}"', self.client.get("/app/academy").data.decode())
        self.assertIn(f'href="{self.url}"', self.client.get(f"/app/academy/{self.lid}").data.decode())

    def test_a_team_member_is_a_grown_up_too(self):
        self.post("/app/settings/invite")
        flash = self.client.get("/app/settings").data.decode()
        token = flash.split("invite=")[1].split()[0].split("<")[0]
        member = self.app.test_client()
        self.signup(email="member@example.com", client=member, invite=token, name="Sam Member")
        self.assertIn("Sam's progress", self.page(client=member))


class TestOnlyTheKidsOwnWorkspace(ProgressCase):
    def test_another_workspace_is_refused(self):
        self.play(1, 1, right=5)
        other = self.app.test_client()
        self.signup(email="other@example.com", client=other)
        self.post("/app/academy/learners", {"nickname": "Riley", "avatar": "star"}, client=other)
        response = other.get(self.url)
        self.assertEqual(response.status_code, 404)
        self.assertNotIn(b"Sam", response.data)
        self.assertNotIn(b"Meet Your Company", response.data)
        # Their own learner's report works, and says nothing about Sam.
        own = other.get("/app/academy/2/progress")
        self.assertEqual(own.status_code, 200)
        self.assertNotIn(b"Sam", own.data)
        # And the owner here can't open theirs.
        self.assertEqual(self.client.get("/app/academy/2/progress").status_code, 404)

    def test_signed_out_and_impossible_ids(self):
        response = self.app.test_client().get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login", response.headers["Location"])
        self.assertEqual(self.client.get("/app/academy/999/progress").status_code, 404)
        self.assertEqual(self.client.get(f"/app/academy/{2 ** 64}/progress").status_code, 404)

    def test_the_kid_cannot_open_it_on_their_own_device(self):
        self.post(f"/app/academy/{self.lid}/join-code")
        with self.db() as conn:
            code = conn.execute("SELECT code FROM join_codes").fetchone()["code"]
        kid = self.app.test_client()
        self.post("/kids", {"code": code}, client=kid)
        response = kid.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.headers["Location"].endswith(f"/app/academy/{self.lid}"))
        self.assertNotIn(self.url.encode(), kid.get(f"/app/academy/{self.lid}").data)


if __name__ == "__main__":
    unittest.main()
