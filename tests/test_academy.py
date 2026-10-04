import hashlib
import hmac
import json
import os
import random
import sys
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from omniarmor_app import academy, academy_plan  # noqa: E402
from omniarmor_app.catalog import INDUSTRIES  # noqa: E402
from omniarmor_app.tracking import org_industry_ids  # noqa: E402
from test_webapp import AppTestCase  # noqa: E402

BASIC = academy.TRACKS["launchpad"]


class TestCourseContent(unittest.TestCase):
    def test_track_sizes(self):
        self.assertEqual({t.key: t.total for t in academy.TRACK_LIST},
                         {"launchpad": 1350, "trailblazer": 2700, "summit": 5400, "titan": 15700})
        self.assertEqual(academy.TOTAL_LEVELS, 1350)
        self.assertEqual(len(academy.TOPIC_WORLDS), 43)
        for t in academy.TRACK_LIST:
            ids = {academy.level_id(t, w.number, s) for w in t.worlds for s in range(1, t.stages(w) + 1)}
            self.assertEqual(len(ids), t.total, t.key)
        # Each track's levels have their own ids, and the basic track keeps the original ones.
        self.assertEqual(academy.level_id(BASIC, 1, 1), 1001)
        self.assertNotEqual(academy.level_id(academy.TRACKS["titan"], 1, 1), 1001)

    def check_quiz(self, questions, wanted, where):
        self.assertEqual(len(questions), wanted, where)
        self.assertEqual(len({q.prompt for q in questions}), len(questions), where)
        for q in questions:
            self.assertGreaterEqual(len(q.options), 2, where)
            self.assertEqual(len(set(q.options)), len(q.options), (where, q.prompt))
            self.assertTrue(0 <= q.answer < len(q.options), where)
            self.assertTrue(q.prompt and q.explain, where)

    def check_level(self, t, w, stage, industry_ids):
        where = (t.key, w.key, stage, industry_ids[:3])
        questions = academy.quiz(t, w.number, stage, "Acme", industry_ids, f"seed-{w.number}-{stage}")
        self.check_quiz(questions, academy.question_count(t, w, stage), where)
        self.assertTrue(academy.story(t, w.number, stage, "Acme", industry_ids), where)
        self.assertLessEqual(academy.pass_mark(t, w, stage), len(questions), where)

    def test_every_basic_and_intermediate_level(self):
        for t in (academy.TRACKS["launchpad"], academy.TRACKS["trailblazer"]):
            for industry_ids in ([1, 18], list(INDUSTRIES)):
                for w in t.worlds:
                    for stage in range(1, t.stages(w) + 1):
                        self.check_level(t, w, stage, industry_ids)

    def test_advanced_and_mastery_levels(self):
        rng = random.Random(7)
        for t in (academy.TRACKS["summit"], academy.TRACKS["titan"]):
            for w in t.worlds:
                n = t.stages(w)
                for stage in {1, 10, n // 2, n} | {rng.randint(1, n) for _ in range(3)}:
                    self.check_level(t, w, stage, [7])

    def test_same_seed_same_quiz(self):
        for t in academy.TRACK_LIST:
            a = academy.quiz(t, 6, 23, "Acme", [1], "x")
            b = academy.quiz(t, 6, 23, "Acme", [1], "x")
            self.assertEqual([(q.prompt, q.options, q.answer) for q in a], [(q.prompt, q.options, q.answer) for q in b])

    def test_harder_stages_and_bigger_tracks(self):
        w = academy.world(9)
        self.assertEqual(academy.question_count(BASIC, w, 1), 5)
        self.assertEqual(academy.question_count(BASIC, w, 49), 8)
        self.assertEqual(academy.question_count(BASIC, w, 50), 10)  # boss round
        self.assertLess(academy.pass_rate(BASIC, w, 1), academy.pass_rate(BASIC, w, 50))
        titan = academy.TRACKS["titan"]
        self.assertGreater(academy.question_count(titan, w, 299), academy.question_count(BASIC, w, 49))
        self.assertGreater(academy.pass_rate(titan, w, 300), academy.pass_rate(BASIC, w, 50))

    def test_question_banks_get_harder(self):
        t = academy.TRACKS["trailblazer"]
        bank = academy.BANK_WORLDS[0]
        levels = {q[0]: q[5] for q in academy._BANK[bank.key]["questions"]}

        def average(stage):
            found = []
            for seed in range(30):
                for q in academy.quiz(t, bank.number, stage, "Acme", [1], f"s{seed}"):
                    if q.prompt in levels:
                        found.append(levels[q.prompt])
            return sum(found) / len(found)
        self.assertLess(average(1), average(49))

    def test_stars(self):
        self.assertEqual(academy.stars_for(5, 5), 3)
        self.assertEqual(academy.stars_for(4, 5), 2)
        self.assertEqual(academy.stars_for(3, 5), 1)
        self.assertEqual(academy.stars_for(2, 5), 0)
        self.assertEqual(academy.stars_for(0, 0), 0)

    def test_unlocking(self):
        topic2, final, industry = academy.world(2), academy.FINAL_WORLD, academy.INDUSTRY_WORLDS[0]
        lid = lambda w, s: academy.level_id(BASIC, w, s)  # noqa: E731
        self.assertTrue(academy.unlocked(BASIC, academy.world(1), 1, set()))
        self.assertFalse(academy.unlocked(BASIC, topic2, 1, set()))
        self.assertTrue(academy.unlocked(BASIC, topic2, 1, {lid(1, 1)}))
        self.assertFalse(academy.unlocked(BASIC, topic2, 2, {lid(1, 1)}))
        self.assertFalse(academy.unlocked(BASIC, topic2, 51, set()))
        self.assertFalse(academy.unlocked(BASIC, industry, 1, set()))
        self.assertTrue(academy.unlocked(BASIC, industry, 1, {lid(academy.INDUSTRY_UNLOCK_WORLD, 1)}))
        all_firsts = {lid(n, 1) for n in BASIC.topics}
        self.assertFalse(academy.unlocked(BASIC, final, 1, all_firsts - {lid(16, 1)}))
        self.assertTrue(academy.unlocked(BASIC, final, 1, all_firsts))
        # New worlds aren't part of the basic track; on the others they follow world 16.
        bank = academy.BANK_WORLDS[0]
        self.assertFalse(academy.unlocked(BASIC, bank, 1, all_firsts))
        trail = academy.TRACKS["trailblazer"]
        self.assertTrue(academy.unlocked(trail, bank, 1, {academy.level_id(trail, 16, 1)}))
        # Progress on one track doesn't open levels on another.
        self.assertFalse(academy.unlocked(trail, topic2, 1, {lid(1, 1)}))

    def test_ranks_avatars_and_certificates(self):
        self.assertEqual(academy.rank_for(0), "Rookie")
        self.assertEqual(academy.rank_for(1000), "Tycoon")
        self.assertEqual(academy.rank_tier(0), 0)
        self.assertEqual(academy.rank_tier(1000), 7)
        titan = academy.TRACKS["titan"]
        self.assertEqual(academy.rank_for(1000, titan), "Manager")  # bigger tracks need more levels
        self.assertEqual(academy.next_rank(0), (5, "Apprentice"))
        self.assertIsNone(academy.certificate_for(1349, False))
        self.assertEqual(academy.certificate_for(1, True), "Future Owner")
        self.assertEqual(academy.certificate_for(120, True), "Silver Future Owner")
        self.assertEqual(academy.certificate_for(1350, True), "Platinum Business Legend")
        self.assertEqual(academy.certificate_for(15700, True, titan), "Titan Mastery Platinum Business Legend")

    def test_money_math_is_exact(self):
        for seed in range(300):
            q = academy._money_math(random.Random(seed), seed / 300)
            self.assertEqual(len(set(q.options)), 3, q.prompt)

    def test_join_codes(self):
        code = academy.new_join_code()
        self.assertRegex(code, r"^KID-[A-Z2-9]{8}$")
        self.assertEqual(academy.clean_join_code(code.lower().replace("-", " ")), code)
        self.assertIsNone(academy.clean_join_code("KID-0000"))


class TestAcademyPages(AppTestCase):
    def setUp(self):
        super().setUp()
        self.signup()

    def add(self, nickname="Sam", avatar="rocket", client=None, track="launchpad"):
        response = self.post("/app/academy/learners", {"nickname": nickname, "avatar": avatar}, client=client)
        if track and response.headers.get("Location", "").endswith("/track"):
            self.post(response.headers["Location"], {"track": track}, client=client)
        return response

    def learner_id(self, nickname="Sam"):
        with self.db() as conn:
            return conn.execute("SELECT id FROM learners WHERE nickname = ?", (nickname,)).fetchone()[0]

    def org(self):
        with self.db() as conn:
            org_id = conn.execute("SELECT id FROM orgs").fetchone()[0]
            return org_id, org_industry_ids(conn, org_id)

    def mark_passed(self, learner_id, *levels, track=BASIC):
        with self.db() as conn:
            for world_number, stage in levels:
                conn.execute("INSERT OR REPLACE INTO learner_progress (learner_id, level, attempts, best_score, best_stars,"
                             " completed_at) VALUES (?, ?, 1, 5, 3, '2026-01-01T00:00:00')",
                             (learner_id, academy.level_id(track, world_number, stage)))
            conn.commit()

    def answer(self, learner_id, world_number, stage, right=True, attempt=1, track=BASIC, client=None):
        _, industry_ids = self.org()
        questions = academy.quiz(track, world_number, stage, "Acme Logistics", industry_ids,
                                 academy.attempt_seed(learner_id, track.key, world_number, stage, attempt))
        data = {"attempt": str(attempt)}
        for i, q in enumerate(questions):
            data[f"q{i}"] = str(q.answer if right else (q.answer + 1) % len(q.options))
        return self.post(f"/app/academy/{learner_id}/world/{world_number}/stage/{stage}", data, client=client)

    def end_trial(self):
        with self.db() as conn:
            conn.execute("UPDATE orgs SET academy_trial_ends = '2000-01-01T00:00:00+00:00', academy_status = 'none'")
            conn.commit()

    def test_home_and_add_learner(self):
        page = self.client.get("/app/academy")
        self.assertEqual(page.status_code, 200)
        self.assertIn(b"15,700", page.data)
        response = self.add(track=None)
        lid = self.learner_id()
        self.assertTrue(response.headers["Location"].endswith(f"/app/academy/{lid}/track"))
        # The first visit asks for a track.
        self.assertTrue(self.client.get(f"/app/academy/{lid}").headers["Location"].endswith("/track"))
        picker = self.client.get(f"/app/academy/{lid}/track").data.decode()
        for name in ("Launchpad", "Trailblazer", "Summit", "Titan Mastery", "1,350", "2,700", "5,400", "15,700"):
            self.assertIn(name, picker)
        self.post(f"/app/academy/{lid}/track", {"track": "summit"})
        page = self.client.get(f"/app/academy/{lid}").data.decode()
        self.assertIn("adventure", page)
        self.assertIn("Summit", page)
        self.assertIn("Meet Your Company", page)
        self.assertIn("Cyber Shield", page)   # a new world
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
                     f"/app/academy/{lid}/certificate", f"/app/academy/{lid}/practice", f"/app/academy/{lid}/track"]:
            self.assertEqual(other.get(path).status_code, 404, path)
        self.assertEqual(self.post(f"/app/academy/{lid}/delete", client=other).status_code, 404)
        self.assertEqual(self.post(f"/app/academy/{lid}/join-code", client=other).status_code, 404)

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
        # New worlds aren't on the basic track.
        self.assertEqual(self.client.get(f"/app/academy/{lid}/world/{academy.BANK_WORLDS[0].number}").status_code, 404)

    def test_mastery_track_has_chapters(self):
        self.add(track="titan")
        lid = self.learner_id()
        titan = academy.TRACKS["titan"]
        page = self.client.get(f"/app/academy/{lid}/world/1").data.decode()
        self.assertIn("251-300", page)
        self.assertEqual(self.client.get(f"/app/academy/{lid}/world/1/stage/300").status_code, 302)  # locked
        self.assertIn("Stage 2 unlocked", self.answer(lid, 1, 1, track=titan).data.decode())
        with self.db() as conn:
            level = conn.execute("SELECT level FROM learner_progress").fetchone()[0]
        self.assertEqual(level, academy.level_id(titan, 1, 1))

    def test_switching_tracks_keeps_progress_separate(self):
        self.add()
        lid = self.learner_id()
        self.answer(lid, 1, 1)
        self.post(f"/app/academy/{lid}/track", {"track": "trailblazer"})
        self.assertEqual(self.client.get(f"/app/academy/{lid}/world/1/stage/2").status_code, 302)
        self.post(f"/app/academy/{lid}/track", {"track": "launchpad"})
        self.assertEqual(self.client.get(f"/app/academy/{lid}/world/1/stage/2").status_code, 200)
        self.post(f"/app/academy/{lid}/track", {"track": "nope"})
        with self.db() as conn:
            self.assertEqual(conn.execute("SELECT track FROM learners").fetchone()[0], "launchpad")

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

    def test_mistakes_come_back_for_practice(self):
        self.add()
        lid = self.learner_id()
        self.assertIn("No mistakes to practice", self.client.get(f"/app/academy/{lid}/practice").data.decode())
        self.answer(lid, 1, 1, right=False)
        with self.db() as conn:
            missed = conn.execute("SELECT COUNT(*) FROM learner_mistakes").fetchone()[0]
        self.assertEqual(missed, 5)
        page = self.client.get(f"/app/academy/{lid}/practice").data.decode()
        self.assertIn("Quiz time", page)
        with self.db() as conn:
            deck = conn.execute("SELECT id, question FROM learner_mistakes ORDER BY due_at, id").fetchall()
        data = {"deck": ",".join(str(r["id"]) for r in deck)}
        for i, r in enumerate(deck):
            data[f"q{i}"] = str(json.loads(r["question"])["answer"])
        result = self.post(f"/app/academy/{lid}/practice", data).data.decode()
        self.assertIn("5 of 5 fixed", result)
        with self.db() as conn:
            rows = conn.execute("SELECT streak, due_at FROM learner_mistakes").fetchall()
        self.assertTrue(all(r["streak"] == 1 for r in rows))       # back in a day
        self.assertIn("scheduled for later", self.client.get(f"/app/academy/{lid}/practice").data.decode())
        # Someone else's deck can't be graded.
        self.assertEqual(self.client.post(f"/app/academy/{lid + 99}/practice", data=data).status_code, 400)

    def test_streak_and_daily_goal(self):
        self.add()
        lid = self.learner_id()
        for attempt in (1, 2):
            self.answer(lid, 1, 1, attempt=attempt)
        page = self.answer(lid, 1, 2).data.decode()
        self.assertIn("Daily goal reached", page)
        page = self.client.get(f"/app/academy/{lid}").data.decode()
        self.assertIn("day streak", page)
        with self.db() as conn:
            self.assertEqual(conn.execute("SELECT levels FROM learner_days").fetchone()[0], 3)

    def test_rank_up(self):
        self.add()
        lid = self.learner_id()
        self.mark_passed(lid, (1, 1), (1, 2), (1, 3), (1, 4))
        page = self.answer(lid, 1, 5).data.decode()
        self.assertIn("Rank up! You're now an Apprentice", page)
        self.assertIn("avatar-tier-1", page)

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
        self.mark_passed(lid, *[(n, 1) for n in BASIC.topics[:-1]])
        self.assertEqual(self.client.get(f"/app/academy/{lid}/world/17").status_code, 302)
        self.answer(lid, BASIC.topics[-1], 1)
        page = self.answer(lid, academy.FINAL_WORLD.number, 1).data.decode()
        self.assertIn("You earned the Future Owner certificate", page)
        cert = self.client.get(f"/app/academy/{lid}/certificate")
        self.assertEqual(cert.status_code, 200)
        self.assertIn(b"Future Owner of Acme Logistics", cert.data)
        self.assertIn(b"Future Owner", self.client.get("/app/academy").data)


class TestAcademyPlan(AppTestCase):
    def setUp(self):
        super().setUp()
        self.signup()
        response = self.post("/app/academy/learners", {"nickname": "Sam", "avatar": "rocket"})
        self.post(response.headers["Location"], {"track": "trailblazer"})
        with self.db() as conn:
            self.lid = conn.execute("SELECT id FROM learners").fetchone()[0]
            self.org_id = conn.execute("SELECT id FROM orgs").fetchone()[0]

    def set_org(self, **fields):
        with self.db() as conn:
            for key, value in fields.items():
                conn.execute(f"UPDATE orgs SET {key} = ?", (value,))
            conn.commit()

    def test_trial_starts_with_first_learner(self):
        with self.db() as conn:
            org = conn.execute("SELECT * FROM orgs").fetchone()
        self.assertEqual(academy_plan.plan_status(org)["access"], "trial")
        self.assertIn(b"Free trial", self.client.get("/app/academy").data)

    def test_after_trial_only_free_worlds(self):
        self.set_org(academy_trial_ends="2000-01-01T00:00:00+00:00")
        response = self.client.get(f"/app/academy/{self.lid}/world/1")
        self.assertTrue(response.headers["Location"].endswith("/app/academy/plan"))
        self.post(f"/app/academy/{self.lid}/track", {"track": "launchpad"})
        self.assertEqual(self.client.get(f"/app/academy/{self.lid}/world/1").status_code, 200)
        self.assertIn(b"Academy plan", self.client.get(f"/app/academy/{self.lid}").data)
        self.set_org(academy_status="active")
        self.post(f"/app/academy/{self.lid}/track", {"track": "titan"})
        self.assertEqual(self.client.get(f"/app/academy/{self.lid}/world/1").status_code, 200)

    def test_plan_page_without_stripe(self):
        page = self.client.get("/app/academy/plan").data.decode()
        self.assertIn("Unlock the whole Academy", page.replace("Your free trial is on", "Unlock the whole Academy"))
        self.assertIn("separate subscription", page)
        response = self.post("/app/academy/plan/checkout")
        self.assertEqual(response.status_code, 302)

    def signed(self, event, secret="whsec_test", stamp=None):
        payload = json.dumps(event).encode()
        stamp = stamp or int(time.time())
        sig = hmac.new(secret.encode(), f"{stamp}.".encode() + payload, hashlib.sha256).hexdigest()
        return payload, f"t={stamp},v1={sig}"

    def test_stripe_webhook_turns_plan_on_and_off(self):
        self.app.config["STRIPE_WEBHOOK_SECRET"] = "whsec_test"
        hook = self.app.test_client()
        event = {"id": "evt_1", "type": "checkout.session.completed",
                 "data": {"object": {"client_reference_id": str(self.org_id), "customer": "cus_1", "subscription": "sub_1"}}}
        payload, sig = self.signed(event)
        self.assertEqual(hook.post("/billing/stripe/webhook", data=payload, headers={"Stripe-Signature": sig}).status_code, 200)
        with self.db() as conn:
            org = conn.execute("SELECT * FROM orgs").fetchone()
        self.assertEqual((org["academy_status"], org["stripe_customer_id"]), ("active", "cus_1"))
        gone = {"id": "evt_2", "type": "customer.subscription.deleted",
                "data": {"object": {"id": "sub_1", "customer": "cus_1", "status": "canceled"}}}
        payload, sig = self.signed(gone)
        hook.post("/billing/stripe/webhook", data=payload, headers={"Stripe-Signature": sig})
        with self.db() as conn:
            self.assertEqual(conn.execute("SELECT academy_status FROM orgs").fetchone()[0], "canceled")

    def test_stripe_webhook_rejects_bad_signatures(self):
        self.app.config["STRIPE_WEBHOOK_SECRET"] = "whsec_test"
        hook = self.app.test_client()
        event = {"type": "checkout.session.completed", "data": {"object": {"client_reference_id": str(self.org_id)}}}
        payload, sig = self.signed(event, secret="wrong")
        self.assertEqual(hook.post("/billing/stripe/webhook", data=payload, headers={"Stripe-Signature": sig}).status_code, 400)
        payload, sig = self.signed(event, stamp=int(time.time()) - 3600)
        self.assertEqual(hook.post("/billing/stripe/webhook", data=payload, headers={"Stripe-Signature": sig}).status_code, 400)
        self.assertEqual(hook.post("/billing/stripe/webhook", data=b"{}").status_code, 400)
        with self.db() as conn:
            self.assertEqual(conn.execute("SELECT academy_status FROM orgs").fetchone()[0], "none")

    def test_turn_plan_on_by_hand(self):
        runner = self.app.test_cli_runner()
        result = runner.invoke(args=["academy-plan", str(self.org_id), "active"])
        self.assertIn("Academy plan active", result.output)
        with self.db() as conn:
            self.assertEqual(conn.execute("SELECT academy_status FROM orgs").fetchone()[0], "active")
        self.assertNotEqual(runner.invoke(args=["academy-plan", "999", "active"]).exit_code, 0)

    def test_only_owner_buys(self):
        anon = self.app.test_client()
        self.assertTrue(self.post("/app/academy/plan/checkout", client=anon).headers["Location"].startswith("/login"))
        with self.db() as conn:
            conn.execute("UPDATE memberships SET role = 'member'")
            conn.commit()
        self.assertEqual(self.post("/app/academy/plan/checkout").status_code, 403)


class TestKidDevices(AppTestCase):
    def setUp(self):
        super().setUp()
        self.signup()
        response = self.post("/app/academy/learners", {"nickname": "Sam", "avatar": "rocket"})
        self.post(response.headers["Location"], {"track": "launchpad"})
        self.post("/app/academy/learners", {"nickname": "Ava", "avatar": "star"})
        with self.db() as conn:
            ids = dict(conn.execute("SELECT nickname, id FROM learners").fetchall())
        self.sam, self.ava = ids["Sam"], ids["Ava"]
        self.kid = self.app.test_client()

    def code(self):
        self.post(f"/app/academy/{self.sam}/join-code")
        with self.db() as conn:
            return conn.execute("SELECT code FROM join_codes").fetchone()[0]

    def join(self, code):
        self.kid.get("/kids")
        return self.post("/kids", {"code": code}, client=self.kid)

    def test_kid_joins_and_only_sees_the_academy(self):
        code = self.code()
        self.assertIn(code, self.client.get(f"/app/academy/{self.sam}").data.decode())
        response = self.join(code.lower())
        self.assertTrue(response.headers["Location"].endswith(f"/app/academy/{self.sam}"))
        page = self.kid.get(f"/app/academy/{self.sam}").data.decode()
        self.assertIn("Sam&#39;s Academy", page.replace("Sam's Academy", "Sam&#39;s Academy"))
        self.assertNotIn("tabbar", page)
        self.assertNotIn("For grown-ups", page)
        self.assertEqual(self.kid.get(f"/app/academy/{self.sam}/world/1/stage/1").status_code, 200)
        # Nothing else: not a sibling, not the business, not grown-up actions.
        self.assertEqual(self.kid.get(f"/app/academy/{self.ava}").status_code, 404)
        self.assertEqual(self.kid.get("/app").status_code, 302)
        self.assertEqual(self.kid.get("/app/settings").status_code, 302)
        self.assertEqual(self.kid.get("/app/armo/status").status_code, 302)
        self.assertTrue(self.kid.get("/app/academy").headers["Location"].endswith(f"/app/academy/{self.sam}"))
        self.assertEqual(self.post("/app/academy/learners", {"nickname": "X", "avatar": "rocket"}, client=self.kid).status_code, 403)
        self.assertEqual(self.post(f"/app/academy/{self.sam}/join-code", client=self.kid).status_code, 403)
        self.assertEqual(self.post(f"/app/academy/{self.sam}/friends/code", client=self.kid).status_code, 403)
        self.assertTrue(self.kid.get("/").headers["Location"].endswith(f"/app/academy/{self.sam}"))

    def test_codes_work_once_and_expire(self):
        code = self.code()
        self.join(code)
        other = self.app.test_client()
        other.get("/kids")
        self.assertEqual(self.post("/kids", {"code": code}, client=other).status_code, 400)
        code = self.code()
        with self.db() as conn:
            conn.execute("UPDATE join_codes SET expires_at = '2000-01-01T00:00:00+00:00'")
            conn.commit()
        self.assertEqual(self.post("/kids", {"code": code}, client=other).status_code, 400)

    def test_grown_up_signs_kid_out_everywhere(self):
        self.join(self.code())
        self.assertEqual(self.kid.get(f"/app/academy/{self.sam}").status_code, 200)
        self.post(f"/app/academy/{self.sam}/devices/sign-out")
        self.assertEqual(self.kid.get(f"/app/academy/{self.sam}").status_code, 302)

    def test_kid_can_leave(self):
        self.join(self.code())
        self.post("/kids/leave", client=self.kid)
        self.assertEqual(self.kid.get(f"/app/academy/{self.sam}").status_code, 302)

    def test_guessing_codes_is_rate_limited(self):
        guesser = self.app.test_client()
        guesser.get("/kids")
        for _ in range(20):
            self.post("/kids", {"code": "KID-ZZZZZZZZ"}, client=guesser)
        self.assertEqual(self.post("/kids", {"code": self.code()}, client=guesser).status_code, 429)


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
            conn.execute("UPDATE learners SET track_chosen = 1")
            conn.commit()
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
