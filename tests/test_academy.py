import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from omniarmor_app import academy  # noqa: E402
from omniarmor_app.catalog import INDUSTRIES  # noqa: E402
from omniarmor_app.tracking import org_industry_ids  # noqa: E402
from test_webapp import AppTestCase  # noqa: E402


class TestCourseContent(unittest.TestCase):
    def test_level_count(self):
        self.assertEqual(academy.TOTAL_LEVELS, 1350)
        self.assertEqual(len(academy.ALL_WORLDS), 16 + 1 + 50)
        self.assertEqual(len({academy.level_id(w.number, s) for w in academy.ALL_WORLDS
                              for s in range(1, w.stages + 1)}), academy.TOTAL_LEVELS)

    def check_quiz(self, questions, wanted, where):
        self.assertEqual(len(questions), wanted, where)
        self.assertEqual(len({q.prompt for q in questions}), len(questions), where)
        for q in questions:
            self.assertGreaterEqual(len(q.options), 2, where)
            self.assertEqual(len(set(q.options)), len(q.options), (where, q.prompt))
            self.assertTrue(0 <= q.answer < len(q.options), where)
            self.assertTrue(q.prompt and q.explain, where)

    def test_every_level_makes_a_good_quiz(self):
        for industry_ids in ([1, 18], [7], list(INDUSTRIES)):
            for w in academy.ALL_WORLDS:
                for stage in range(1, w.stages + 1):
                    where = (industry_ids[:3], w.number, stage)
                    questions = academy.quiz(w.number, stage, "Acme", industry_ids, f"seed-{w.number}-{stage}")
                    self.check_quiz(questions, academy.question_count(w, stage), where)
                    self.assertTrue(academy.story(w.number, stage, "Acme", industry_ids), where)
                    self.assertLessEqual(academy.pass_mark(w, stage), len(questions), where)

    def test_same_seed_same_quiz(self):
        a = academy.quiz(6, 23, "Acme", [1], "x")
        b = academy.quiz(6, 23, "Acme", [1], "x")
        self.assertEqual([(q.prompt, q.options, q.answer) for q in a], [(q.prompt, q.options, q.answer) for q in b])

    def test_harder_stages(self):
        w = academy.world(9)
        self.assertEqual(academy.question_count(w, 1), 5)
        self.assertEqual(academy.question_count(w, 50), 8)
        self.assertLess(academy.pass_rate(w, 1), academy.pass_rate(w, 50))

    def test_stars(self):
        self.assertEqual(academy.stars_for(5, 5), 3)
        self.assertEqual(academy.stars_for(4, 5), 2)
        self.assertEqual(academy.stars_for(3, 5), 1)
        self.assertEqual(academy.stars_for(2, 5), 0)
        self.assertEqual(academy.stars_for(0, 0), 0)

    def test_unlocking(self):
        topic2, final, industry = academy.world(2), academy.FINAL_WORLD, academy.INDUSTRY_WORLDS[0]
        self.assertTrue(academy.unlocked(academy.world(1), 1, set()))
        self.assertFalse(academy.unlocked(topic2, 1, set()))
        self.assertTrue(academy.unlocked(topic2, 1, {academy.level_id(1, 1)}))
        self.assertFalse(academy.unlocked(topic2, 2, {academy.level_id(1, 1)}))
        self.assertFalse(academy.unlocked(topic2, 51, set()))
        self.assertFalse(academy.unlocked(industry, 1, set()))
        self.assertTrue(academy.unlocked(industry, 1, {academy.level_id(academy.INDUSTRY_UNLOCK_WORLD, 1)}))
        all_firsts = {academy.level_id(t.number, 1) for t in academy.TOPIC_WORLDS}
        self.assertFalse(academy.unlocked(final, 1, all_firsts - {academy.level_id(16, 1)}))
        self.assertTrue(academy.unlocked(final, 1, all_firsts))

    def test_ranks_and_certificates(self):
        self.assertEqual(academy.rank_for(0), "Rookie")
        self.assertEqual(academy.rank_for(1000), "Tycoon")
        self.assertIsNone(academy.certificate_for(1349, False))
        self.assertEqual(academy.certificate_for(1, True), "Future Owner")
        self.assertEqual(academy.certificate_for(120, True), "Silver Future Owner")
        self.assertEqual(academy.certificate_for(1350, True), "Platinum Business Legend")


class TestAcademyPages(AppTestCase):
    def setUp(self):
        super().setUp()
        self.signup()

    def add(self, nickname="Sam", avatar="rocket", client=None):
        return self.post("/app/academy/learners", {"nickname": nickname, "avatar": avatar}, client=client)

    def learner_id(self, nickname="Sam"):
        with self.db() as conn:
            return conn.execute("SELECT id FROM learners WHERE nickname = ?", (nickname,)).fetchone()[0]

    def org(self):
        with self.db() as conn:
            org_id = conn.execute("SELECT id FROM orgs").fetchone()[0]
            return org_id, org_industry_ids(conn, org_id)

    def mark_passed(self, learner_id, *levels):
        with self.db() as conn:
            for world_number, stage in levels:
                conn.execute("INSERT OR REPLACE INTO learner_progress (learner_id, level, attempts, best_score, best_stars,"
                             " completed_at) VALUES (?, ?, 1, 5, 3, '2026-01-01T00:00:00')",
                             (learner_id, academy.level_id(world_number, stage)))
            conn.commit()

    def answer(self, learner_id, world_number, stage, right=True, attempt=1):
        _, industry_ids = self.org()
        questions = academy.quiz(world_number, stage, "Acme Logistics", industry_ids,
                                 academy.attempt_seed(learner_id, world_number, stage, attempt))
        data = {"attempt": str(attempt)}
        for i, q in enumerate(questions):
            data[f"q{i}"] = str(q.answer if right else (q.answer + 1) % len(q.options))
        return self.post(f"/app/academy/{learner_id}/world/{world_number}/stage/{stage}", data)

    def test_home_and_add_learner(self):
        page = self.client.get("/app/academy")
        self.assertEqual(page.status_code, 200)
        self.assertIn(b"1,350", page.data)
        response = self.add()
        lid = self.learner_id()
        self.assertTrue(response.headers["Location"].endswith(f"/app/academy/{lid}"))
        page = self.client.get(f"/app/academy/{lid}").data.decode()
        self.assertIn("adventure", page)
        self.assertIn("Sam", page)
        self.assertIn("Meet Your Company", page)
        self.assertIn("Owner&#39;s Challenge", page)

    def test_learner_validation_and_limit(self):
        self.add(nickname="")
        self.add(avatar="dragon")
        with self.db() as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM learners").fetchone()[0], 0)
        for i in range(academy.MAX_LEARNERS + 2):
            self.add(nickname=f"Kid {i}")
        with self.db() as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM learners").fetchone()[0], academy.MAX_LEARNERS)

    def test_delete_removes_progress(self):
        self.add()
        lid = self.learner_id()
        self.mark_passed(lid, (1, 1))
        self.post(f"/app/academy/{lid}/delete")
        with self.db() as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM learners").fetchone()[0], 0)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM learner_progress").fetchone()[0], 0)

    def test_other_workspace_cannot_see_learner(self):
        self.add()
        lid = self.learner_id()
        other = self.app.test_client()
        self.signup(email="rival@example.com", client=other)
        for path in [f"/app/academy/{lid}", f"/app/academy/{lid}/world/1", f"/app/academy/{lid}/world/1/stage/1",
                     f"/app/academy/{lid}/certificate"]:
            self.assertEqual(other.get(path).status_code, 404, path)
        self.assertEqual(self.post(f"/app/academy/{lid}/delete", client=other).status_code, 404)

    def test_requires_login(self):
        anon = self.app.test_client()
        self.assertEqual(anon.get("/app/academy").status_code, 302)

    def test_world_and_stage_pages(self):
        self.add()
        lid = self.learner_id()
        world = self.client.get(f"/app/academy/{lid}/world/1")
        self.assertEqual(world.status_code, 200)
        self.assertIn(b"Stages", world.data)
        level = self.client.get(f"/app/academy/{lid}/world/1/stage/1")
        self.assertEqual(level.status_code, 200)
        self.assertIn(b"Quiz time", level.data)
        self.assertEqual(self.client.get(f"/app/academy/{lid}/world/999").status_code, 404)
        self.assertEqual(self.client.get(f"/app/academy/{lid}/world/1/stage/51").status_code, 404)
        self.assertEqual(self.client.get(f"/app/academy/{lid}/world/1/stage/0").status_code, 404)

    def test_locked_pages_redirect(self):
        self.add()
        lid = self.learner_id()
        self.assertEqual(self.client.get(f"/app/academy/{lid}/world/2").status_code, 302)
        self.assertEqual(self.client.get(f"/app/academy/{lid}/world/1/stage/2").status_code, 302)
        self.assertEqual(self.client.get(f"/app/academy/{lid}/world/17").status_code, 302)
        self.assertEqual(self.client.get(f"/app/academy/{lid}/world/101").status_code, 302)
        self.assertEqual(self.answer(lid, 1, 2).status_code, 302)

    def test_pass_unlocks_next_stage_and_world(self):
        self.add()
        lid = self.learner_id()
        page = self.answer(lid, 1, 1).data.decode()
        self.assertIn("Perfect score", page)
        self.assertIn("Stage 2 unlocked", page)
        self.assertEqual(self.client.get(f"/app/academy/{lid}/world/1/stage/2").status_code, 200)
        self.assertEqual(self.client.get(f"/app/academy/{lid}/world/2").status_code, 200)
        with self.db() as conn:
            row = conn.execute("SELECT * FROM learner_progress WHERE learner_id = ?", (lid,)).fetchone()
        self.assertEqual((row["level"], row["best_stars"], row["attempts"]), (1001, 3, 1))

    def test_fail_keeps_next_stage_locked_and_best_score_stays(self):
        self.add()
        lid = self.learner_id()
        page = self.answer(lid, 1, 1, right=False).data.decode()
        self.assertIn("So close", page)
        self.assertEqual(self.client.get(f"/app/academy/{lid}/world/1/stage/2").status_code, 302)
        self.answer(lid, 1, 1, attempt=2)
        self.answer(lid, 1, 1, right=False, attempt=3)
        with self.db() as conn:
            row = conn.execute("SELECT * FROM learner_progress WHERE learner_id = ?", (lid,)).fetchone()
        self.assertEqual((row["attempts"], row["best_stars"]), (3, 3))

    def test_rank_up(self):
        self.add()
        lid = self.learner_id()
        self.mark_passed(lid, (1, 1), (1, 2), (1, 3), (1, 4))
        self.assertIn("Rank up! You're now an Apprentice",
                      self.answer(lid, 1, 5).data.decode())

    def test_stale_attempt_is_not_graded(self):
        self.add()
        lid = self.learner_id()
        self.answer(lid, 1, 1)
        response = self.answer(lid, 1, 1, attempt=1)
        self.assertEqual(response.status_code, 302)
        with self.db() as conn:
            self.assertEqual(conn.execute("SELECT attempts FROM learner_progress").fetchone()[0], 1)

    def test_industry_quest_for_the_family_business(self):
        self.add()
        lid = self.learner_id()
        self.mark_passed(lid, (academy.INDUSTRY_UNLOCK_WORLD, 1))
        page = self.client.get(f"/app/academy/{lid}").data.decode()
        self.assertIn("Rule Quests", page)
        quest = academy.INDUSTRY_WORLD_BASE + 1
        self.assertEqual(self.client.get(f"/app/academy/{lid}/world/{quest}/stage/1").status_code, 200)
        self.assertIn("Stage 2 unlocked", self.answer(lid, quest, 1).data.decode())

    def test_certificate(self):
        self.add()
        lid = self.learner_id()
        self.assertEqual(self.client.get(f"/app/academy/{lid}/certificate").status_code, 302)
        self.mark_passed(lid, *[(t.number, 1) for t in academy.TOPIC_WORLDS[:-1]])
        self.assertEqual(self.client.get(f"/app/academy/{lid}/world/17").status_code, 302)
        self.answer(lid, academy.TOPIC_WORLDS[-1].number, 1)
        page = self.answer(lid, academy.FINAL_WORLD.number, 1).data.decode()
        self.assertIn("You earned the Future Owner certificate", page)
        cert = self.client.get(f"/app/academy/{lid}/certificate")
        self.assertEqual(cert.status_code, 200)
        self.assertIn(b"Future Owner of Acme Logistics", cert.data)
        self.assertIn(b"Future Owner", self.client.get("/app/academy").data)


class TestFriendsAndDuels(AppTestCase):
    """Two families, each with a kid, become friends and duel."""

    def setUp(self):
        super().setUp()
        self.signup()
        self.post("/app/academy/learners", {"nickname": "Sam", "avatar": "rocket"})
        self.other = self.app.test_client()
        self.signup(email="friend@example.com", client=self.other)
        self.post("/app/academy/learners", {"nickname": "Riley", "avatar": "star"}, client=self.other)
        with self.db() as conn:
            ids = dict(conn.execute("SELECT nickname, id FROM learners").fetchall())
        self.sam, self.riley = ids["Sam"], ids["Riley"]

    def code_for(self, learner_id, client=None):
        self.post(f"/app/academy/{learner_id}/friends/code", client=client)
        with self.db() as conn:
            return conn.execute("SELECT code FROM friend_codes WHERE learner_id = ?", (learner_id,)).fetchone()[0]

    def befriend(self):
        code = self.code_for(self.sam)
        return self.post(f"/app/academy/{self.riley}/friends/add", {"code": code.lower().replace("-", " ")},
                         client=self.other)

    def friend_rows(self):
        with self.db() as conn:
            return conn.execute("SELECT COUNT(*) FROM learner_friends").fetchone()[0]

    def test_friend_code_links_two_families_once(self):
        code = self.code_for(self.sam)
        self.assertRegex(code, r"^ARMO-[A-Z2-9]{8}$")
        self.assertIn(code, self.client.get(f"/app/academy/{self.sam}/friends").data.decode())
        self.befriend()
        self.assertEqual(self.friend_rows(), 1)
        page = self.other.get(f"/app/academy/{self.riley}/friends").data.decode()
        self.assertIn("Sam", page)
        self.assertNotIn("Acme Logistics", page.split("</header>", 1)[1])
        # The code was used up.
        self.assertEqual(self.post(f"/app/academy/{self.riley}/friends/add", {"code": code}, client=self.other).status_code, 302)
        self.assertEqual(self.friend_rows(), 1)

    def test_bad_own_and_expired_codes(self):
        self.post(f"/app/academy/{self.riley}/friends/add", {"code": "ARMO-ZZZZZZZZ"}, client=self.other)
        code = self.code_for(self.sam)
        self.post(f"/app/academy/{self.sam}/friends/add", {"code": code})
        with self.db() as conn:
            conn.execute("UPDATE friend_codes SET expires_at = '2000-01-01T00:00:00+00:00'")
            conn.commit()
        self.post(f"/app/academy/{self.riley}/friends/add", {"code": code}, client=self.other)
        self.assertEqual(self.friend_rows(), 0)

    def test_guessing_codes_is_rate_limited(self):
        for _ in range(10):
            self.post(f"/app/academy/{self.riley}/friends/add", {"code": "ARMO-ZZZZZZZZ"}, client=self.other)
        code = self.code_for(self.sam)
        self.post(f"/app/academy/{self.riley}/friends/add", {"code": code}, client=self.other)
        self.assertEqual(self.friend_rows(), 0)

    def test_parent_cannot_act_for_other_familys_kid(self):
        self.befriend()
        self.assertEqual(self.client.get(f"/app/academy/{self.riley}/friends").status_code, 404)
        self.assertEqual(self.post(f"/app/academy/{self.riley}/friends/code").status_code, 404)
        self.assertEqual(self.post(f"/app/academy/{self.riley}/duels", {"friend": self.sam, "world": 2}).status_code, 404)

    def test_only_friends_can_duel(self):
        self.post(f"/app/academy/{self.sam}/duels", {"friend": self.riley, "world": 2})
        with self.db() as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM duels").fetchone()[0], 0)

    def play(self, learner_id, duel_id, right, client=None):
        with self.db() as conn:
            d = conn.execute("SELECT * FROM duels WHERE id = ?", (duel_id,)).fetchone()
        questions = academy.duel_quiz(d["world"], d["stage"], d["seed"])
        data = {f"q{i}": str(q.answer if i < right else (q.answer + 1) % len(q.options)) for i, q in enumerate(questions)}
        return self.post(f"/app/academy/{learner_id}/duels/{duel_id}", data, client=client)

    def test_duel_from_challenge_to_winner(self):
        self.befriend()
        self.post(f"/app/academy/{self.sam}/duels", {"friend": self.riley, "world": 99})
        response = self.post(f"/app/academy/{self.sam}/duels", {"friend": self.riley, "world": 15})
        duel_id = int(response.headers["Location"].rsplit("/", 1)[1])
        self.assertIn(b"Quiz time", self.client.get(response.headers["Location"]).data)
        self.assertIn("Riley's turn", self.play(self.sam, duel_id, 4).data.decode())
        # Replaying doesn't change the score.
        self.play(self.sam, duel_id, 5)
        self.assertIn(b"Friends &amp; duels <span class=\"ac-dot\">1</span>", self.other.get(f"/app/academy/{self.riley}").data)
        self.assertIn("Sam won this one", self.play(self.riley, duel_id, 2, client=self.other).data.decode())
        self.assertIn(b"You won the duel", self.client.get(f"/app/academy/{self.sam}/duels/{duel_id}").data)
        with self.db() as conn:
            d = conn.execute("SELECT challenger_score, opponent_score FROM duels").fetchone()
        self.assertEqual(tuple(d), (4, 2))
        # Nobody else can see the duel.
        third = self.app.test_client()
        self.signup(email="third@example.com", client=third)
        self.assertEqual(third.get(f"/app/academy/{self.sam}/duels/{duel_id}").status_code, 404)

    def test_remove_friend_and_delete_learner(self):
        self.befriend()
        self.post(f"/app/academy/{self.riley}/friends/{self.sam}/remove", client=self.other)
        self.assertEqual(self.friend_rows(), 0)
        self.befriend()
        self.post(f"/app/academy/{self.sam}/delete")
        self.assertEqual(self.friend_rows(), 0)


if __name__ == "__main__":
    unittest.main()
