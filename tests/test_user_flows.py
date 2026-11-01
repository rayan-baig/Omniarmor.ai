"""Bugs a person using the app would hit, each one shown failing before it was fixed."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_webapp import AppTestCase  # noqa: E402


class TestDateCountedReadings(AppTestCase):
    """A date-counted check's form has a number box and a date box. Once a date
    is saved, the page fills the date box with it, so it comes back with every
    later save."""

    def setUp(self):
        super().setUp()
        self.signup(industries=(1,))
        self.change(1, "annual_mvr_review", date="2026-01-01")

    def reading(self):
        with self.db() as conn:
            return dict(conn.execute("SELECT value_num, value_date FROM items WHERE rule_key = 'annual_mvr_review'")
                        .fetchone())

    def test_a_typed_number_replaces_a_saved_date(self):
        # The page sends the saved date back alongside the number just typed.
        self.change(1, "annual_mvr_review", value="12", date="2026-01-01")
        self.assertEqual(self.reading(), {"value_num": 12.0, "value_date": None})

    def test_a_new_date_still_wins(self):
        self.change(1, "annual_mvr_review", value="", date="2026-02-01")
        self.assertEqual(self.reading(), {"value_num": None, "value_date": "2026-02-01"})

    def test_a_number_and_a_new_date_together_are_refused(self):
        response = self.change(1, "annual_mvr_review", value="12", date="2026-02-01")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.reading(), {"value_num": None, "value_date": "2026-01-01"})
        page = self.client.get("/app/industry/1").data.decode()
        self.assertIn("Enter a number or a date, not both", page)
