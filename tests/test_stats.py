"""The owner's console (MTRX Horizyn) asks each app how many people use it.

Counts only, behind a private key, and switched off unless that key is set.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from test_webapp import AppTestCase  # noqa: E402


class TestStats(AppTestCase):
    def test_off_unless_a_key_is_set(self):
        self.app.config["STATS_KEY"] = ""
        self.assertEqual(self.app.test_client().get("/api/stats").status_code, 404)

    def test_refuses_without_the_key(self):
        self.app.config["STATS_KEY"] = "s3cret-stats-key"
        anon = self.app.test_client()
        self.assertEqual(anon.get("/api/stats").status_code, 401)
        self.assertEqual(anon.get("/api/stats", headers={"Authorization": "Bearer wrong"}).status_code, 401)

    def test_counts_people_and_who_used_it_lately(self):
        self.signup()
        self.client.get("/app")                 # using the app is what counts
        other = self.app.test_client()
        self.signup(email="second@example.com", client=other)
        with self.db() as conn:
            conn.execute("UPDATE users SET last_seen_on = '2000-01-01' WHERE email = 'second@example.com'")
            conn.commit()
        self.app.config["STATS_KEY"] = "s3cret-stats-key"
        body = self.app.test_client().get("/api/stats", headers={"Authorization": "Bearer s3cret-stats-key"}).get_json()
        self.assertEqual(body, {"users": 2, "active_users": 1})
        # Using the app again counts them as active again (once a day).
        other.get("/app")
        body = self.app.test_client().get("/api/stats", headers={"Authorization": "Bearer s3cret-stats-key"}).get_json()
        self.assertEqual(body["active_users"], 2)
