"""Regression tests for Academy fixes: kid device sessions, duel plan checks,
Stripe webhook ordering and duplicates, practice replays, huge ids and the
trial for workspaces that already had learners."""

import hashlib
import hmac
import json
import os
import sys
import time
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from omniarmor_app import academy, academy_plan, db as dbmod  # noqa: E402
from omniarmor_app.db import connect, migrate  # noqa: E402
from test_webapp import AppTestCase  # noqa: E402

EXPIRED = "2000-01-01T00:00:00+00:00"
BIG = "9" * 30


class TestKidSessions(AppTestCase):
    def setUp(self):
        super().setUp()
        self.signup()
        response = self.post("/app/academy/learners", {"nickname": "Sam", "avatar": "rocket"})
        self.post(response.headers["Location"], {"track": "launchpad"})
        with self.db() as conn:
            self.sam = conn.execute("SELECT id FROM learners").fetchone()[0]
        self.kid = self.app.test_client()

    def join(self, learner_id):
        self.post(f"/app/academy/{learner_id}/join-code")
        with self.db() as conn:
            code = conn.execute("SELECT code FROM join_codes WHERE learner_id = ?", (learner_id,)).fetchone()[0]
        self.kid.get("/kids")
        return self.post("/kids", {"code": code}, client=self.kid)

    def test_new_learners_get_random_device_epochs(self):
        self.post("/app/academy/learners", {"nickname": "Ava", "avatar": "star"})
        with self.db() as conn:
            epochs = [r[0] for r in conn.execute("SELECT device_epoch FROM learners")]
        self.assertNotIn(0, epochs)
        self.assertEqual(len(set(epochs)), 2)

    def test_old_device_cannot_open_another_familys_learner_with_reused_id(self):
        self.join(self.sam)
        self.assertEqual(self.kid.get(f"/app/academy/{self.sam}").status_code, 200)
        self.post(f"/app/academy/{self.sam}/delete")
        other = self.app.test_client()
        self.signup(email="b@example.com", client=other)
        self.post("/app/academy/learners", {"nickname": "Zed", "avatar": "star"}, client=other)
        with self.db() as conn:
            zed = conn.execute("SELECT id FROM learners WHERE nickname = 'Zed'").fetchone()[0]
        self.assertEqual(zed, self.sam)  # SQLite reused the id
        response = self.kid.get(f"/app/academy/{zed}/track")
        self.assertEqual(response.status_code, 302)
        self.assertNotIn(b"Zed", response.data)

    def test_same_epoch_in_another_org_is_rejected(self):
        self.join(self.sam)
        other = self.app.test_client()
        self.signup(email="b@example.com", client=other)
        with self.db() as conn:
            other_org = conn.execute("SELECT id FROM orgs WHERE id != (SELECT org_id FROM learners)").fetchone()[0]
            conn.execute("UPDATE learners SET org_id = ?", (other_org,))
            conn.commit()
        self.assertEqual(self.kid.get(f"/app/academy/{self.sam}").status_code, 302)

    def test_kid_cookie_without_org_is_signed_out(self):
        self.join(self.sam)
        with self.kid.session_transaction() as s:
            s.pop("kid_org")
        self.assertEqual(self.kid.get(f"/app/academy/{self.sam}").status_code, 302)

    def test_kid_pages_are_not_cached(self):
        self.join(self.sam)
        response = self.kid.get(f"/app/academy/{self.sam}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get("Cache-Control"), "no-store")

    def test_removed_user_session_does_not_carry_to_reused_id(self):
        second = self.app.test_client()
        self.signup(email="second@example.com", client=second)
        self.assertEqual(second.get("/app").status_code, 200)
        with self.db() as conn:
            uid = conn.execute("SELECT id FROM users WHERE email = 'second@example.com'").fetchone()[0]
            conn.execute("DELETE FROM users WHERE id = ?", (uid,))
            conn.commit()
        third = self.app.test_client()
        self.signup(email="third@example.com", client=third)
        with self.db() as conn:
            self.assertEqual(conn.execute("SELECT id FROM users WHERE email = 'third@example.com'").fetchone()[0], uid)
        self.assertEqual(second.get("/app").status_code, 302)
        self.assertEqual(third.get("/app").status_code, 200)


class TestDuelPlan(AppTestCase):
    def setUp(self):
        super().setUp()
        self.signup()
        self.post("/app/academy/learners", {"nickname": "Sam", "avatar": "rocket"})
        self.other = self.app.test_client()
        self.signup(email="friend@example.com", client=self.other)
        self.post("/app/academy/learners", {"nickname": "Riley", "avatar": "star"}, client=self.other)
        with self.db() as conn:
            ids = dict(conn.execute("SELECT nickname, id FROM learners").fetchall())
            orgs = dict(conn.execute("SELECT nickname, org_id FROM learners").fetchall())
            conn.execute("UPDATE learners SET track_chosen = 1")
            conn.commit()
        self.sam, self.riley = ids["Sam"], ids["Riley"]
        self.sam_org, self.riley_org = orgs["Sam"], orgs["Riley"]
        self.post(f"/app/academy/{self.sam}/friends/code")
        with self.db() as conn:
            code = conn.execute("SELECT code FROM friend_codes").fetchone()[0]
        self.post(f"/app/academy/{self.riley}/friends/add", {"code": code}, client=self.other)

    def set_plan(self, org_id, **fields):
        with self.db() as conn:
            for key, value in fields.items():
                conn.execute(f"UPDATE orgs SET {key} = ? WHERE id = ?", (value, org_id))
            conn.commit()

    def duel_count(self):
        with self.db() as conn:
            return conn.execute("SELECT COUNT(*) FROM duels").fetchone()[0]

    def test_free_workspace_cannot_start_paid_world_duel(self):
        self.set_plan(self.sam_org, academy_trial_ends=EXPIRED)
        response = self.post(f"/app/academy/{self.sam}/duels", {"friend": self.riley, "world": 15})
        self.assertTrue(response.headers["Location"].endswith(f"/app/academy/{self.sam}/friends"))
        if academy.BANK_WORLDS:
            self.post(f"/app/academy/{self.sam}/duels", {"friend": self.riley, "world": academy.BANK_WORLDS[0].number})
        self.assertEqual(self.duel_count(), 0)
        # World 2 is free on Launchpad, so that duel is fine.
        response = self.post(f"/app/academy/{self.sam}/duels", {"friend": self.riley, "world": 2})
        self.assertIn("/duels/", response.headers["Location"])
        self.assertEqual(self.duel_count(), 1)

    def test_friends_page_only_offers_included_worlds(self):
        self.set_plan(self.sam_org, academy_trial_ends=EXPIRED)
        page = self.client.get(f"/app/academy/{self.sam}/friends").data.decode()
        self.assertIn('<option value="2">', page)
        self.assertNotIn('<option value="15">', page)

    def test_opponent_without_plan_sees_note_not_quiz(self):
        self.set_plan(self.sam_org, academy_status="active")
        self.set_plan(self.riley_org, academy_trial_ends=EXPIRED)
        response = self.post(f"/app/academy/{self.sam}/duels", {"friend": self.riley, "world": 15})
        duel_id = int(response.headers["Location"].rsplit("/", 1)[1])
        page = self.other.get(f"/app/academy/{self.riley}/duels/{duel_id}")
        self.assertEqual(page.status_code, 200)
        self.assertIn(b"part of the Academy plan", page.data)
        self.assertNotIn(b'name="q0"', page.data)
        self.post(f"/app/academy/{self.riley}/duels/{duel_id}", {"q0": "0", "q1": "0"}, client=self.other)
        with self.db() as conn:
            self.assertIsNone(conn.execute("SELECT opponent_score FROM duels").fetchone()[0])
        # The challenger, whose plan includes it, still gets the quiz.
        self.assertIn(b'name="q0"', self.client.get(f"/app/academy/{self.sam}/duels/{duel_id}").data)


class TestStripeEvents(AppTestCase):
    def setUp(self):
        super().setUp()
        self.signup()
        self.post("/app/academy/learners", {"nickname": "Sam", "avatar": "rocket"})
        with self.db() as conn:
            self.org_id = conn.execute("SELECT id FROM orgs").fetchone()[0]
        self.app.config["STRIPE_WEBHOOK_SECRET"] = "whsec_test"
        self.hook = self.app.test_client()

    def send(self, event_id, kind, obj, created=None):
        event = {"id": event_id, "type": kind, "data": {"object": obj}}
        if created is not None:
            event["created"] = created
        payload = json.dumps(event).encode()
        stamp = int(time.time())
        sig = hmac.new(b"whsec_test", f"{stamp}.".encode() + payload, hashlib.sha256).hexdigest()
        response = self.hook.post("/billing/stripe/webhook", data=payload, headers={"Stripe-Signature": f"t={stamp},v1={sig}"})
        self.assertEqual(response.status_code, 200)

    def org(self):
        with self.db() as conn:
            return conn.execute("SELECT * FROM orgs").fetchone()

    def checkout(self, created=None, sub="sub_1", event_id="evt_checkout"):
        self.send(event_id, "checkout.session.completed",
                  {"client_reference_id": str(self.org_id), "customer": "cus_1", "subscription": sub}, created)

    def sub(self, event_id, kind, sub_id, status, created=None):
        self.send(event_id, f"customer.subscription.{kind}",
                  {"id": sub_id, "customer": "cus_1", "status": status, "metadata": {"org_id": str(self.org_id)}}, created)

    def test_cancelled_duplicate_subscription_keeps_plan(self):
        self.checkout()
        self.sub("evt_dup_created", "created", "sub_2", "active")
        self.sub("evt_dup_deleted", "deleted", "sub_2", "canceled")
        org = self.org()
        self.assertEqual((org["academy_status"], org["stripe_subscription_id"]), ("active", "sub_1"))
        # A second checkout while paid doesn't take over either.
        self.checkout(sub="sub_3", event_id="evt_checkout_2")
        self.assertEqual(self.org()["stripe_subscription_id"], "sub_1")
        # The real subscription still controls the plan.
        self.sub("evt_real_deleted", "deleted", "sub_1", "canceled")
        self.assertEqual(self.org()["academy_status"], "canceled")

    def test_checkout_refused_when_already_paid(self):
        self.app.config.update(STRIPE_SECRET_KEY="sk_test", ACADEMY_STRIPE_PRICE="price_1")
        with self.db() as conn:
            conn.execute("UPDATE orgs SET academy_status = 'active'")
            conn.commit()
        with mock.patch.object(academy_plan, "checkout_url", side_effect=AssertionError("no checkout")):
            response = self.post("/app/academy/plan/checkout")
        self.assertTrue(response.headers["Location"].endswith("/app/academy/plan"))
        self.assertIn(b"already on", self.client.get("/app/academy/plan").data)

    def test_replayed_event_is_ignored(self):
        self.sub("evt_a", "updated", "sub_1", "active")
        self.sub("evt_b", "deleted", "sub_1", "canceled")
        self.sub("evt_a", "updated", "sub_1", "active")
        self.assertEqual(self.org()["academy_status"], "canceled")
        with self.db() as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM stripe_events").fetchone()[0], 2)

    def test_older_subscription_event_is_ignored(self):
        now = int(time.time())
        self.sub("evt_new", "updated", "sub_1", "past_due", created=now)
        self.sub("evt_old", "updated", "sub_1", "unpaid", created=now - 60)
        self.assertEqual(self.org()["academy_status"], "past_due")
        self.assertEqual(self.org()["stripe_event_at"], now)

    def test_late_incomplete_created_does_not_revoke(self):
        now = int(time.time())
        self.checkout(created=now)
        self.sub("evt_created", "created", "sub_1", "incomplete", created=now - 5)
        self.assertEqual(self.org()["academy_status"], "active")
        # Even arriving with the same timestamp, incomplete can't undo a completed checkout.
        self.sub("evt_created_2", "created", "sub_1", "incomplete", created=now)
        self.assertEqual(self.org()["academy_status"], "active")
        self.sub("evt_updated", "updated", "sub_1", "active", created=now + 1)
        self.assertEqual(self.org()["academy_status"], "active")


class TestPracticeAndIds(AppTestCase):
    def setUp(self):
        super().setUp()
        self.signup()
        response = self.post("/app/academy/learners", {"nickname": "Sam", "avatar": "rocket"})
        self.post(response.headers["Location"], {"track": "launchpad"})
        with self.db() as conn:
            self.sam = conn.execute("SELECT id FROM learners").fetchone()[0]
            question = json.dumps({"prompt": "P?", "options": ["a", "b"], "answer": 0, "explain": "e", "kind": "choice"})
            self.mid = conn.execute("INSERT INTO learner_mistakes (learner_id, qkey, question, due_at)"
                                    " VALUES (?, 'k', ?, ?)", (self.sam, question, EXPIRED)).lastrowid
            conn.commit()

    def mistakes(self):
        with self.db() as conn:
            return [tuple(r) for r in conn.execute("SELECT streak FROM learner_mistakes")]

    def test_duplicate_deck_ids_count_once(self):
        deck = ",".join([str(self.mid)] * 4)
        response = self.post(f"/app/academy/{self.sam}/practice", {"deck": deck, "q0": "0", "q1": "0", "q2": "0", "q3": "0"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.mistakes(), [(1,)])

    def test_resubmitting_stale_form_does_nothing(self):
        for _ in range(4):
            self.post(f"/app/academy/{self.sam}/practice", {"deck": str(self.mid), "q0": "0"})
        self.assertEqual(self.mistakes(), [(1,)])

    def test_huge_and_odd_ids_are_not_errors(self):
        practice = f"/app/academy/{self.sam}/practice"
        self.assertEqual(self.post(practice, {"deck": BIG}).status_code, 302)
        self.assertEqual(self.post(practice, {"deck": "\u00b2"}).status_code, 302)
        self.assertEqual(self.post(practice, {"deck": "\u0663"}).status_code, 302)
        self.assertEqual(self.post(f"/app/academy/{self.sam}/duels", {"friend": BIG, "world": "2"}).status_code, 302)
        self.assertEqual(self.post(f"/app/academy/{self.sam}/duels", {"friend": "1", "world": BIG}).status_code, 302)
        self.assertEqual(self.client.get(f"/app/academy/{BIG}").status_code, 404)
        self.assertEqual(self.client.get(f"/app/academy/{self.sam}/duels/{BIG}").status_code, 404)
        self.assertEqual(self.client.get(f"/app/academy/{self.sam}/world/{BIG}").status_code, 404)
        self.assertEqual(self.client.get(f"/app/academy/{self.sam}/world/1/stage/{BIG}").status_code, 404)
        self.assertEqual(self.post(f"/app/academy/{self.sam}/friends/{BIG}/remove").status_code, 404)
        self.assertEqual(self.post(f"/app/academy/{BIG}/delete").status_code, 404)
        self.assertEqual(self.mistakes(), [(0,)])


class TestTrialForExistingWorkspaces(AppTestCase):
    def test_trial_starts_lazily_on_academy_home(self):
        self.signup()
        self.post("/app/academy/learners", {"nickname": "Sam", "avatar": "rocket"})
        with self.db() as conn:
            conn.execute("UPDATE orgs SET academy_trial_ends = NULL")
            conn.commit()
        page = self.client.get("/app/academy")
        self.assertIn(b"Free trial", page.data)
        with self.db() as conn:
            org = conn.execute("SELECT * FROM orgs").fetchone()
        self.assertEqual(academy_plan.plan_status(org)["access"], "trial")

    def test_no_trial_without_learners(self):
        self.signup()
        self.client.get("/app/academy")
        with self.db() as conn:
            self.assertIsNone(conn.execute("SELECT academy_trial_ends FROM orgs").fetchone()[0])


class TestMigration7(unittest.TestCase):
    def test_backfills_trials_and_randomizes_device_epochs(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            conn = connect(os.path.join(tmp, "old.db"))
            with mock.patch.object(dbmod, "MIGRATIONS", [m for m in dbmod.MIGRATIONS if m[0] < 7]):
                migrate(conn)
            now = "2026-01-01T00:00:00+00:00"
            for org_id, status, trial in [(1, "none", None), (2, "none", None), (3, "active", None), (4, "none", EXPIRED)]:
                conn.execute("INSERT INTO orgs (id, name, created_at, academy_status, academy_trial_ends)"
                             " VALUES (?, 'Org', ?, ?, ?)", (org_id, now, status, trial))
            for org_id in (1, 3, 4):
                conn.execute("INSERT INTO learners (org_id, nickname, avatar, created_at) VALUES (?, 'Kid', 'rocket', ?)",
                             (org_id, now))
            conn.commit()
            migrate(conn)
            trials = dict(conn.execute("SELECT id, academy_trial_ends FROM orgs").fetchall())
            epochs = [r[0] for r in conn.execute("SELECT device_epoch FROM learners")]
            conn.close()
        self.assertRegex(trials[1], r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\+00:00$")
        self.assertGreater(trials[1], dbmod.now_iso())
        self.assertIsNone(trials[2])
        self.assertIsNone(trials[3])
        self.assertEqual(trials[4], EXPIRED)
        self.assertNotIn(0, epochs)
        self.assertTrue(all(0 < e < 2 ** 63 for e in epochs))


if __name__ == "__main__":
    unittest.main()
