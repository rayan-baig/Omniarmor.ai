import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from omniarmor_app import armo  # noqa: E402
from test_webapp import AppTestCase, first_rule  # noqa: E402


class TestPersonalities(unittest.TestCase):
    def test_every_personality_is_complete(self):
        self.assertIn(armo.DEFAULT_ADULT, armo.PERSONALITIES)
        self.assertIn(armo.DEFAULT_KID, armo.PERSONALITIES)
        self.assertNotIn(armo.HIDDEN, armo.PERSONALITIES)
        for p in armo.PERSONALITIES.values():
            self.assertGreaterEqual(len(p.idle), 6, p.key)
            self.assertTrue(p.clear and p.cheers and p.oops and p.win and p.retry and p.hello and p.fix, p.key)
            self.assertTrue(all("{title}" in line for line in p.alert), p.key)
            self.assertEqual(set(p.streaks), {3, 5, 8}, p.key)
            self.assertTrue(set(p.activities) <= {"mug", "book", "juggle", "zzz", "wave"}, p.key)

    def test_unknown_personality_falls_back(self):
        self.assertEqual(armo.personality("nope").key, armo.DEFAULT_ADULT)
        self.assertEqual(armo.voice("nope"), armo.voice(armo.DEFAULT_KID))


class TestCompanion(AppTestCase):
    def setUp(self):
        super().setUp()
        self.signup(industries=(1,))

    def block_a_rule(self):
        rule = first_rule(1, kind="max", mode=None)
        self.change(1, rule.key, value=str(rule.limit + 1))
        return rule

    def test_companion_sits_on_app_pages_but_not_the_academy(self):
        page = self.client.get("/app").data.decode()
        self.assertIn("data-companion", page)
        self.assertIn("armo.js", page)
        self.assertNotIn("data-companion", self.client.get("/app/academy").data.decode())
        self.assertNotIn("data-companion", self.client.get("/app/armo").data.decode())
        self.assertNotIn("data-companion", self.client.get("/login").data.decode())

    def test_status_reports_live_issues(self):
        status = self.client.get("/app/armo/status").get_json()
        self.assertEqual((status["needs"], status["urgent"], status["top"]), (0, 0, None))
        rule = self.block_a_rule()
        status = self.client.get("/app/armo/status").get_json()
        self.assertEqual(status["urgent"], 1)
        self.assertIn(rule.title, status["top"]["title"])
        self.assertIn(f"#rule-{rule.key}", status["top"]["url"])
        self.assertTrue(status["signature"])
        page = self.client.get("/app/armo").data.decode()
        self.assertIn(rule.title, page)
        self.assertIn("What to do", page)
        self.assertIn('data-needs="1"', self.client.get("/app").data.decode())

    def test_missing_readings_are_a_heads_up(self):
        page = self.client.get("/app/armo").data.decode()
        self.assertIn("with no reading yet", page)

    def test_failed_emails_show_up(self):
        with self.db() as conn:
            org_id = conn.execute("SELECT id FROM orgs").fetchone()[0]
            conn.execute("INSERT INTO notifications (org_id, created_at, kind, recipient, subject, body, status, error)"
                         " VALUES (?, datetime('now'), 'digest', 'a@b.c', 's', 'b', 'failed', 'boom')", (org_id,))
            conn.commit()
        status = self.client.get("/app/armo/status").get_json()
        self.assertEqual(status["needs"], 1)
        self.assertIn("failed to send", status["top"]["title"])

    def test_pick_and_hide_personality(self):
        self.assertIn("Chief", self.client.get("/app/settings").data.decode())
        self.post("/app/armo/personality", {"armo": "snarky"})
        page = self.client.get("/app").data.decode()
        self.assertIn("I&#39;d roll my eyes", page.replace("\\u0027", "&#39;"))
        self.post("/app/armo/personality", {"armo": "evil"})
        with self.db() as conn:
            self.assertEqual(conn.execute("SELECT armo FROM users").fetchone()[0], "snarky")
        self.post("/app/armo/personality", {"armo": "off"})
        self.assertNotIn("data-companion", self.client.get("/app").data.decode())
        self.assertEqual(self.client.get("/app/armo").status_code, 200)

    def test_status_needs_login(self):
        self.assertEqual(self.app.test_client().get("/app/armo/status").status_code, 302)

    def test_learner_picks_their_own_armo(self):
        self.post("/app/academy/learners", {"nickname": "Sam", "avatar": "rocket", "armo": "funny"})
        with self.db() as conn:
            lid, buddy = conn.execute("SELECT id, armo FROM learners").fetchone()
        self.assertEqual(buddy, "funny")
        self.assertIn("Jokester", self.client.get(f"/app/academy/{lid}").data.decode())
        level = self.client.get(f"/app/academy/{lid}/world/1/stage/1").data.decode()
        self.assertIn("data-voice=", level)
        self.assertIn("Nailed it!", level)
        self.post(f"/app/academy/{lid}/armo", {"armo": "sleepy"})
        self.post(f"/app/academy/{lid}/armo", {"armo": "nope"})
        with self.db() as conn:
            self.assertEqual(conn.execute("SELECT armo FROM learners").fetchone()[0], "sleepy")
        self.post("/app/academy/learners", {"nickname": "Bad", "avatar": "rocket", "armo": "nope"})
        with self.db() as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM learners").fetchone()[0], 1)


if __name__ == "__main__":
    unittest.main()
