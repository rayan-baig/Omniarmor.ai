"""Bulk entry: several checks of one industry updated at once, with the same
sign-in, workspace, CSRF and audit rules as a single update, all or nothing."""

import html
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from e2e_helpers import flashes, forms  # noqa: E402
from test_webapp import AppTestCase  # noqa: E402

from omniarmor_app.tracking import org_today  # noqa: E402

# Industry 1 (FleetArmor): duties that repeat, yes-or-no questions and a due date.
REPEATING = ["annual_mvr_review", "clearinghouse_annual_query", "annual_vehicle_inspection"]
YES_NO = ["eld_in_use", "cdl_valid", "pre_employment_drug_test"]
DUE_DATE = "medical_certificate"
NUMBER = "steer_tire_tread"


class BulkCase(AppTestCase):
    def setUp(self):
        super().setUp()
        self.signup()

    def bulk(self, keys, action, client=None, industry=1, **fields):
        return self.post(f"/app/industry/{industry}/bulk", {"keys": list(keys), "bulk_action": action, **fields},
                         client=client)

    def items(self, org_id=1):
        with self.db() as conn:
            return {r["rule_key"]: dict(r) for r in conn.execute(
                "SELECT * FROM items WHERE org_id = ? AND industry_id = 1", (org_id,))}

    def audit(self, org_id=1):
        with self.db() as conn:
            return conn.execute("SELECT * FROM audit WHERE org_id = ? AND rule_key IS NOT NULL ORDER BY id",
                                (org_id,)).fetchall()

    def today(self):
        with self.db() as conn:
            return org_today(conn.execute("SELECT * FROM orgs WHERE id = 1").fetchone()).isoformat()

    def page_flashes(self, response):
        return [html.unescape(m) for m in flashes(self.client.get(response.headers["Location"]).data.decode())]


class TestBulkUpdates(BulkCase):
    def test_the_page_has_the_form_and_a_select_box_per_check(self):
        page = self.client.get("/app/industry/1").data.decode()
        bulk = next(f for f in forms(page) if f.action == "/app/industry/1/bulk")
        self.assertEqual(bulk.method, "post")
        self.assertIsNotNone(bulk.field("csrf_token"))
        self.assertIsNotNone(bulk.field("bulk_action"))
        self.assertIsNotNone(bulk.field("date"))
        # The boxes sit beside each check and belong to the bulk form.
        self.assertEqual(page.count('name="keys"'), 10)
        self.assertEqual(page.count('form="bulk"'), 10)

    def test_done_today_on_several_repeating_duties(self):
        response = self.bulk(REPEATING, "done")
        self.assertEqual(response.status_code, 302)
        items = self.items()
        for key in REPEATING:
            self.assertEqual(items[key]["value_date"], self.today(), key)
            self.assertEqual(items[key]["updated_by_name"], "Pat Owner")
        self.assertIn("Updated 3 checks: mark done today.", self.page_flashes(response))
        # One audit row per check, the same as three single updates.
        rows = self.audit()
        self.assertEqual([r["rule_key"] for r in rows], REPEATING)
        self.assertTrue(all(r["action"] == "done" and r["user_name"] == "Pat Owner" for r in rows))
        self.assertTrue(all(r["after"] == f"date {self.today()}" for r in rows))

    def test_yes_and_no_on_several_questions(self):
        self.bulk(YES_NO, "yes")
        self.assertEqual({k: self.items()[k]["value_bool"] for k in YES_NO}, dict.fromkeys(YES_NO, 1))
        self.bulk(YES_NO[:2], "no")
        self.assertEqual({k: self.items()[k]["value_bool"] for k in YES_NO}, {YES_NO[0]: 0, YES_NO[1]: 0, YES_NO[2]: 1})
        rows = self.audit()
        self.assertEqual(len(rows), 5)
        self.assertEqual([(r["before"], r["after"]) for r in rows[3:]], [("Yes", "No"), ("Yes", "No")])

    def test_one_date_on_several_dated_checks(self):
        keys = REPEATING[:2] + [DUE_DATE]
        response = self.bulk(keys, "date", date="2026-01-15")
        items = self.items()
        self.assertEqual({k: items[k]["value_date"] for k in keys}, dict.fromkeys(keys, "2026-01-15"))
        self.assertIn("Updated 3 checks: set the date to 2026-01-15.", self.page_flashes(response))
        self.assertEqual(len(self.audit()), 3)

    def test_the_same_box_twice_counts_once(self):
        self.bulk([YES_NO[0], YES_NO[0]], "yes")
        self.assertEqual(len(self.audit()), 1)

    def test_it_returns_to_the_problems_view_it_came_from(self):
        response = self.bulk([YES_NO[0]], "no", only="problems")
        self.assertTrue(response.headers["Location"].endswith("/app/industry/1?only=problems"))

    def test_a_team_member_can_use_it_like_a_single_update(self):
        self.post("/app/settings/invite")
        link = next(f for f in flashes(self.client.get("/app/settings").data.decode()) if "/signup?invite=" in f)
        token = link.split("invite=")[1].split()[0]
        member = self.app.test_client()
        self.signup(email="member@example.com", client=member, invite=token, name="Sam Member")
        self.assertEqual(self.bulk([YES_NO[0]], "yes", client=member).status_code, 302)
        self.assertEqual(self.items()[YES_NO[0]]["updated_by_name"], "Sam Member")


class TestBulkRefusals(BulkCase):
    def assert_nothing_saved(self):
        self.assertEqual(self.items(), {})
        self.assertEqual(self.audit(), [])

    def test_a_check_the_action_does_not_fit_refuses_the_whole_batch(self):
        response = self.bulk(REPEATING[:2] + [YES_NO[0]], "done")
        self.assert_nothing_saved()
        said = self.page_flashes(response)
        self.assertTrue(any("can't be marked done" in m and "Nothing was changed." in m for m in said), said)
        self.bulk([YES_NO[0], REPEATING[0]], "yes")
        self.bulk([NUMBER], "date", date="2026-01-15")
        self.assert_nothing_saved()

    def test_a_later_check_failing_undoes_the_earlier_ones(self):
        # The first passes the up-front checks and is written, then the
        # second's future date is refused: the first must not stay saved.
        response = self.bulk([DUE_DATE, REPEATING[0]], "date", date="2150-12-31")
        self.assert_nothing_saved()
        said = self.page_flashes(response)
        self.assertTrue(any("in the future" in m for m in said), said)

    def test_bad_values(self):
        cases = [
            ({"keys": [REPEATING[0]], "bulk_action": "explode"}, "Pick what to do"),
            ({"keys": [REPEATING[0]], "bulk_action": ""}, "Pick what to do"),
            ({"keys": [], "bulk_action": "done"}, "Tick at least one check"),
            ({"keys": ["no_such_check"], "bulk_action": "done"}, "isn't on this page"),
            ({"keys": [REPEATING[0], "x" * 5000], "bulk_action": "done"}, "isn't on this page"),
            ({"keys": [REPEATING[0]], "bulk_action": "date", "date": ""}, "Pick the date"),
            ({"keys": [REPEATING[0]], "bulk_action": "date", "date": "15/01/2026"}, "YYYY-MM-DD"),
            ({"keys": [REPEATING[0]], "bulk_action": "date", "date": "1066-10-14"}, "out of range"),
        ]
        for data, message in cases:
            response = self.post("/app/industry/1/bulk", data)
            self.assertEqual(response.status_code, 302, data)
            said = self.page_flashes(response)
            self.assertTrue(any(message in m and "Nothing was changed." in m for m in said), (data, said))
        self.assert_nothing_saved()

    def test_an_hour_clock_is_refused_a_plain_date(self):
        other = self.app.test_client()
        self.signup(email="hospital@example.com", industries=(5,), client=other)
        response = self.bulk(["restraint_order_4_hours"], "date", client=other, industry=5, date="2026-01-15")
        said = flashes(other.get(response.headers["Location"]).data.decode())
        self.assertTrue(any("counts hours" in m for m in said), said)

    def test_signed_out(self):
        response = self.bulk(REPEATING, "done", client=self.app.test_client())
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login", response.headers["Location"])
        self.assert_nothing_saved()

    def test_without_the_form_token(self):
        response = self.client.post("/app/industry/1/bulk", data={"keys": REPEATING, "bulk_action": "done"})
        self.assertEqual(response.status_code, 400)
        response = self.client.post("/app/industry/1/bulk", data={"keys": REPEATING, "bulk_action": "done",
                                                                  "csrf_token": "forged"})
        self.assertEqual(response.status_code, 400)
        self.assert_nothing_saved()

    def test_a_kid_on_their_own_device_only_sees_the_academy(self):
        """There is no read-only "viewer" team role; the one session that may
        see the workspace but never change a check is a kid's Academy device."""
        self.post("/app/academy/learners", {"nickname": "Kiddo", "avatar": "rocket", "armo": "sweet"})
        self.post("/app/academy/1/join-code")
        with self.db() as conn:
            code = conn.execute("SELECT code FROM join_codes").fetchone()["code"]
        kid = self.app.test_client()
        self.post("/kids", {"code": code}, client=kid)
        with kid.session_transaction() as s:
            self.assertEqual(s.get("kid"), 1)
        response = self.bulk(REPEATING, "done", client=kid)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login", response.headers["Location"])
        self.assert_nothing_saved()

    def test_another_workspaces_checks(self):
        # Another company, in FleetArmor too, with its own reading.
        other = self.app.test_client()
        self.signup(email="rival@example.com", industries=(1, 2), client=other)
        self.bulk([YES_NO[0]], "yes", client=other)
        self.assertEqual(self.items(org_id=2)[YES_NO[0]]["value_bool"], 1)
        # This company can't reach an industry it doesn't have, even one the other company has...
        response = self.bulk(["hos_11_hour"], "yes", industry=2)
        self.assertEqual(response.status_code, 404)
        # ...and the same check in a shared industry is only ever its own.
        self.bulk([YES_NO[0]], "no")
        self.assertEqual(self.items(org_id=2)[YES_NO[0]]["value_bool"], 1)
        self.assertEqual(self.items(org_id=1)[YES_NO[0]]["value_bool"], 0)
        self.assertEqual(len(self.audit(org_id=2)), 1)
        # An industry number that doesn't exist at all.
        self.assertEqual(self.bulk([YES_NO[0]], "yes", industry=999).status_code, 404)


if __name__ == "__main__":
    unittest.main()
