"""The Kitchen Safety Bundle: CyberLogix fills in the temperature checks.

The owner makes a connection key in Settings, Connections (shown once,
stored as a hash, one active per workspace). CyberLogix sends each day's
summary to POST /api/connect/cyberlogix/daily with it. A clean day saves the
check's reading through apply_change, as a person's Save does; a day with a
breach leaves a note instead. docs/CYBERLOGIX-CONNECTION.md is the contract."""
import json
import os
import re
import sys
import unittest
from contextlib import closing
from datetime import timedelta
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from test_webapp import AppTestCase  # noqa: E402

from omniarmor_app import connections, create_app  # noqa: E402
from omniarmor_app.catalog import find_rule  # noqa: E402
from omniarmor_app.db import MIGRATIONS, SCHEMA_VERSION, migrate  # noqa: E402
from omniarmor_app.security import hash_token  # noqa: E402
from omniarmor_app.tracking import org_today  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
URL = "/api/connect/cyberlogix/daily"
RESTO = 2
COLD = "cold_holding"


def text(page):
    """A page's words, without its tags."""
    return re.sub(r"<[^>]+>", "", page)


def breach(**changes):
    b = {"unit": "Walk-in freezer", "started_at": "{day}T02:10:00-05:00", "ended_at": "{day}T02:45:00-05:00",
         "peak": 41, "limit": 0, "unit_of_measure": "°F", "acknowledged_by_role": "on-call staff",
         "action": "checked_food"}
    b.update(changes)
    return b


class BundleCase(AppTestCase):
    def setUp(self):
        super().setUp()
        self.signup(industries=(RESTO, 1))
        self.org = self.org_row()
        self.day = (org_today(self.org) - timedelta(days=1)).isoformat()

    def org_row(self, name="Acme Logistics"):
        with closing(self.db()) as conn:
            return conn.execute("SELECT * FROM orgs WHERE name = ?", (name,)).fetchone()

    def create_key(self, client=None):
        response = self.post("/app/settings/connections/cyberlogix/create", client=client)
        self.assertEqual(response.status_code, 200)
        page = response.get_data(as_text=True)
        match = re.search(r'<p class="key mono">(clx_[A-Za-z0-9_-]+)</p>', page)
        self.assertIsNotNone(match, "the new key is on the page")
        return match.group(1)

    def report(self, **changes):
        body = {"date": self.day, "site": "Main kitchen", "units_total": 7, "units_in_range_all_day": 7,
                "breaches": [], "warmest_reading": 38, "unit_of_measure": "°F",
                "log_url": "https://cyberlogix.example.com/log/abc123"}
        body.update(changes)
        text = json.dumps(body).replace("{day}", body["date"] if isinstance(body.get("date"), str) else self.day)
        return json.loads(text)

    def send(self, key, body=None, **headers):
        headers.setdefault("Authorization", f"Bearer {key}")
        return self.client.post(URL, data=json.dumps(self.report() if body is None else body),
                                content_type="application/json", headers=headers)

    def item(self, org_id=None, key=COLD):
        with closing(self.db()) as conn:
            return conn.execute("SELECT * FROM items WHERE org_id = ? AND industry_id = ? AND rule_key = ?",
                                (org_id or self.org["id"], RESTO, key)).fetchone()

    def audit(self, org_id=None):
        with closing(self.db()) as conn:
            return [dict(r) for r in conn.execute("SELECT * FROM audit WHERE org_id = ? ORDER BY id",
                                                  (org_id or self.org["id"],))]

    def reports(self):
        with closing(self.db()) as conn:
            return [dict(r) for r in conn.execute("SELECT * FROM connection_reports ORDER BY report_date")]


class TestTheCatalogsTemperatureChecks(unittest.TestCase):
    def test_each_check_is_a_fahrenheit_maximum(self):
        self.assertEqual(connections.TEMPERATURE_CHECKS, ((RESTO, COLD),))
        for industry_id, key in connections.TEMPERATURE_CHECKS:
            rule = find_rule(industry_id, key)
            self.assertIsNotNone(rule, key)
            self.assertEqual((rule.kind, rule.unit), ("max", "°F"))


class TestTheKey(BundleCase):
    def test_created_shown_once_and_stored_hashed(self):
        page = self.client.get("/app/settings").get_data(as_text=True)
        self.assertIn('id="connections"', page)
        self.assertIn("Kitchen Safety Bundle", page)
        self.assertIn("Let CyberLogix fill this in automatically", page)
        key = self.create_key()
        with closing(self.db()) as conn:
            row = conn.execute("SELECT * FROM connection_keys").fetchone()
            dump = "\n".join(conn.iterdump())
        self.assertEqual(row["key_hash"], hash_token(key))
        self.assertNotIn(key, dump, "only the hash is stored")
        self.assertEqual(row["hint"], key[-4:])
        again = self.client.get("/app/settings").get_data(as_text=True)
        self.assertNotIn(key, again, "shown only once")
        self.assertIn(f"…{key[-4:]}", again)
        self.assertIn("waiting for the first report", again)
        self.assertIn("connection key created", self.audit()[-1]["summary"])

    def test_one_active_key_and_regenerate_replaces_it(self):
        first = self.create_key()
        response = self.post("/app/settings/connections/cyberlogix/create")
        self.assertEqual(response.status_code, 302)
        self.assertNotIn("clx_", self.client.get("/app/settings").get_data(as_text=True))
        response = self.post("/app/settings/connections/cyberlogix/regenerate")
        second = re.search(r'<p class="key mono">(clx_[A-Za-z0-9_-]+)</p>', response.get_data(as_text=True)).group(1)
        self.assertNotEqual(first, second)
        with closing(self.db()) as conn:
            active = conn.execute("SELECT COUNT(*) FROM connection_keys WHERE revoked_at IS NULL").fetchone()[0]
        self.assertEqual(active, 1)
        self.assertEqual(self.send(first).status_code, 401, "the old key stopped working")
        self.assertEqual(self.send(second).status_code, 200)

    def test_the_database_refuses_a_second_active_key(self):
        self.create_key()
        with closing(self.db()) as conn, self.assertRaises(Exception):
            conn.execute("INSERT INTO connection_keys (org_id, service, key_hash, hint, created_at)"
                         " VALUES (?, 'cyberlogix', 'x', 'abcd', '2026-01-01')", (self.org["id"],))

    def test_revoke(self):
        key = self.create_key()
        response = self.post("/app/settings/connections/cyberlogix/revoke")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.send(key).status_code, 401)
        page = self.client.get("/app/settings").get_data(as_text=True)
        self.assertIn("Create CyberLogix connection key", page)
        self.assertIn("connection key revoked", self.audit()[-1]["summary"])

    def test_owner_only(self):
        invite = self.post("/app/settings/invite")
        self.assertEqual(invite.status_code, 302)
        with self.client.session_transaction() as s:
            link = [m for c, m in s["_flashes"] if c == "invite"][0]
        token = link.rsplit("invite=", 1)[1]
        member = self.app.test_client()
        self.signup(email="member@example.com", invite=token, client=member, name="Sam Member")
        page = member.get("/app/settings").get_data(as_text=True)
        self.assertIn('id="connections"', page)
        self.assertNotIn("Create CyberLogix connection key", page)
        for action in ("create", "regenerate", "revoke"):
            response = self.post(f"/app/settings/connections/cyberlogix/{action}", client=member)
            self.assertEqual(response.status_code, 403, action)
        with closing(self.db()) as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM connection_keys").fetchone()[0], 0)

    def test_signed_out_gets_sign_in(self):
        self.post("/logout")
        response = self.post("/app/settings/connections/cyberlogix/create")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login", response.headers["Location"])


class TestAuthentication(BundleCase):
    def test_wrong_missing_or_revoked_key_is_401(self):
        key = self.create_key()
        for headers in ({"Authorization": "Bearer clx_wrong"}, {"Authorization": ""}, {"Authorization": f"Basic {key}"},
                        {"Authorization": "Bearer " + "x" * 300}):
            response = self.send(key, **headers)
            self.assertEqual(response.status_code, 401, headers)
            self.assertEqual(response.get_json()["error"], "unauthorized")
            self.assertIn("Bearer", response.headers["WWW-Authenticate"])
        self.post("/app/settings/connections/cyberlogix/revoke")
        self.assertEqual(self.send(key).status_code, 401)
        self.assertIsNone(self.item())

    def test_a_signed_in_cookie_is_not_a_key(self):
        """The CSRF exemption is safe because the session is never used."""
        self.create_key()
        response = self.client.post(URL, data=json.dumps(self.report()), content_type="application/json")
        self.assertEqual(response.status_code, 401)
        self.assertIsNone(self.item())

    def test_another_workspaces_checks_are_never_touched(self):
        key = self.create_key()
        other = self.app.test_client()
        self.post("/signup", {"name": "Other Owner", "email": "other@example.com", "password": "correct horse battery",
                              "org_name": "Other Diner", "timezone": "America/New_York", "industries": [str(RESTO)]},
                  client=other)
        other_org = self.org_row("Other Diner")
        self.change(RESTO, COLD, client=other, value="39")
        before = dict(self.item(other_org["id"]))
        self.assertEqual(self.send(key).status_code, 200)
        self.assertEqual(dict(self.item(other_org["id"])), before)
        self.assertFalse(any("CyberLogix" in a["summary"] for a in self.audit(other_org["id"])))
        self.assertEqual(self.item()["value_num"], 38)
        with closing(self.db()) as conn:
            self.assertEqual({r[0] for r in conn.execute("SELECT org_id FROM connection_reports")}, {self.org["id"]})

    def test_get_is_refused_in_json(self):
        response = self.client.get(URL)
        self.assertEqual(response.status_code, 405)
        self.assertEqual(response.get_json()["error"], "http_405")


class TestACleanDay(BundleCase):
    def test_ticks_the_temperature_check_through_apply_change(self):
        key = self.create_key()
        with mock.patch("omniarmor_app.connections.apply_change", wraps=connections.apply_change) as spy:
            response = self.send(key)
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual((data["ok"], data["matched_checks"], data["ticked"], data["noted"]), (True, 1, 1, 0))
        self.assertEqual(data["checks"][0]["check"], COLD)
        self.assertEqual(spy.call_count, 1)
        self.assertEqual(spy.call_args.args[5], "save")
        item = self.item()
        self.assertEqual(item["value_num"], 38)
        self.assertIsNone(item["updated_by"])
        self.assertEqual(item["updated_by_name"], "CyberLogix")
        last = self.audit()[-1]
        self.assertTrue(last["summary"].startswith("From CyberLogix: 7 of 7 units in range all day"), last["summary"])
        self.assertEqual((last["user_name"], last["action"], last["rule_key"]), ("CyberLogix", "reading", COLD))
        self.assertEqual(last["after"], "38°F")
        page = self.client.get(f"/app/industry/{RESTO}").get_data(as_text=True)
        self.assertIn(f"Connected to CyberLogix · last report {self.day}", text(page))
        self.assertIn("Cleared", page)
        audit = self.client.get("/app/audit").get_data(as_text=True)
        self.assertIn("From CyberLogix: 7 of 7 units in range all day", audit)
        settings = self.client.get("/app/settings").get_data(as_text=True)
        self.assertIn(f"Connected to CyberLogix · last report {self.day}", text(settings))

    def test_celsius_is_converted(self):
        key = self.create_key()
        self.send(key, self.report(warmest_reading=3.5, unit_of_measure="°C"))
        self.assertEqual(self.item()["value_num"], 38.3)

    def test_same_date_twice_changes_nothing(self):
        key = self.create_key()
        self.send(key)
        item, audit = dict(self.item()), self.audit()
        response = self.send(key)
        self.assertEqual(response.get_json()["unchanged"], 1)
        self.assertEqual(response.get_json()["ticked"], 0)
        self.assertEqual(dict(self.item()), item)
        self.assertEqual(self.audit(), audit)
        self.assertEqual(len(self.reports()), 1)

    def test_a_persons_reading_that_day_stands(self):
        key = self.create_key()
        self.day = org_today(self.org).isoformat()
        self.change(RESTO, COLD, value="39")
        response = self.send(key)
        self.assertEqual(response.get_json()["checks"][0]["result"], "confirmed")
        item = self.item()
        self.assertEqual((item["value_num"], item["updated_by_name"]), (39, "Pat Owner"))
        self.assertIn("the team's reading stands", self.audit()[-1]["summary"])

    def test_an_older_day_never_overwrites_a_newer_report(self):
        key = self.create_key()
        today = org_today(self.org)
        self.send(key, self.report(date=today.isoformat(), warmest_reading=37))
        self.send(key, self.report(date=(today - timedelta(days=2)).isoformat(), warmest_reading=39))
        self.assertEqual(self.item()["value_num"], 37)

    def test_a_new_day_updates_its_own_reading(self):
        key = self.create_key()
        self.send(key)
        self.day = org_today(self.org).isoformat()
        self.send(key, self.report(warmest_reading=36.5))
        self.assertEqual(self.item()["value_num"], 36.5)


class TestADayWithABreach(BundleCase):
    def test_adds_a_note_and_does_not_tick(self):
        key = self.create_key()
        response = self.send(key, self.report(units_in_range_all_day=6, breaches=[breach()]))
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual((data["matched_checks"], data["ticked"], data["noted"]), (1, 0, 1))
        self.assertIsNone(self.item())
        note = self.reports()[0]["note"]
        self.assertTrue(note.startswith("CyberLogix: 1 breach on Walk-in freezer, 02:10–02:45, peak 41°F"), note)
        self.assertIn("acknowledged by on-call staff", note)
        self.assertIn("6 of 7 units in range all day", note)
        self.assertIn("left for review", self.audit()[-1]["summary"])
        page = self.client.get(f"/app/industry/{RESTO}").get_data(as_text=True)
        self.assertIn("Needs review", page)
        self.assertIn("CyberLogix: 1 breach on Walk-in freezer, 02:10–02:45, peak 41°F", page)
        self.assertIn("No reading", page)

    def test_a_person_marks_it_reviewed(self):
        key = self.create_key()
        self.send(key, self.report(units_in_range_all_day=6, breaches=[breach()]))
        response = self.post("/app/connections/cyberlogix/review",
                             {"industry_id": str(RESTO), "rule_key": COLD, "date": self.day})
        self.assertEqual(response.status_code, 302)
        self.assertIsNotNone(self.reports()[0]["reviewed_at"])
        self.assertNotIn("Needs review", self.client.get(f"/app/industry/{RESTO}").get_data(as_text=True))
        self.assertIn("note for", self.audit()[-1]["summary"])
        self.assertEqual(self.audit()[-1]["user_name"], "Pat Owner")
        # A check CyberLogix doesn't fill in is not a note to review.
        self.assertEqual(self.post("/app/connections/cyberlogix/review",
                                   {"industry_id": "1", "rule_key": "eld_in_use", "date": self.day}).status_code, 404)

    def test_units_not_confirmed_without_breach_details_add_a_note(self):
        key = self.create_key()
        data = self.send(key, self.report(units_in_range_all_day=5)).get_json()
        self.assertEqual(data["noted"], 1)
        self.assertIsNone(self.item())
        self.assertIn("2 of 7 units not confirmed in range", self.reports()[0]["note"])

    def test_same_breach_report_twice_changes_nothing(self):
        key = self.create_key()
        body = self.report(units_in_range_all_day=6, breaches=[breach()])
        self.send(key, body)
        audit = self.audit()
        self.assertEqual(self.send(key, body).get_json()["unchanged"], 1)
        self.assertEqual(self.audit(), audit)

    def test_a_corrected_report_replaces_the_note(self):
        key = self.create_key()
        self.send(key, self.report(units_in_range_all_day=6, breaches=[breach()]))
        self.post("/app/connections/cyberlogix/review", {"industry_id": str(RESTO), "rule_key": COLD, "date": self.day})
        self.send(key, self.report(units_in_range_all_day=6, breaches=[breach(peak=44, acknowledged_by_role="manager")]))
        rows = self.reports()
        self.assertEqual(len(rows), 1)
        self.assertIn("peak 44°F", rows[0]["note"])
        self.assertIn("acknowledged by manager", rows[0]["note"])
        self.assertIsNone(rows[0]["reviewed_at"], "a changed note needs a new review")
        self.assertIn("A corrected report.", self.audit()[-1]["summary"])

    def test_a_corrected_report_never_unticks_a_persons_tick(self):
        key = self.create_key()
        self.day = org_today(self.org).isoformat()
        self.send(key)                                   # clean: ticked
        self.change(RESTO, COLD, value="39")             # a person saves their own reading
        self.send(key, self.report(units_in_range_all_day=6, breaches=[breach()]))   # corrected: a breach
        item = self.item()
        self.assertEqual((item["value_num"], item["updated_by_name"]), (39, "Pat Owner"))
        self.assertEqual(self.reports()[0]["outcome"], "note")
        self.send(key, self.report(warmest_reading=35))  # corrected again: clean
        item = self.item()
        self.assertEqual((item["value_num"], item["updated_by_name"]), (39, "Pat Owner"))
        self.assertIsNone(self.reports()[0]["note"], "the note is replaced")

    def test_a_corrected_clean_report_ticks_after_a_breach(self):
        key = self.create_key()
        self.send(key, self.report(units_in_range_all_day=6, breaches=[breach()]))
        self.assertIsNone(self.item())
        self.assertEqual(self.send(key).get_json()["ticked"], 1)
        self.assertEqual(self.item()["value_num"], 38)
        self.assertNotIn("Needs review", self.client.get(f"/app/industry/{RESTO}").get_data(as_text=True))

    def test_several_breaches_and_an_open_one(self):
        key = self.create_key()
        second = breach(unit="Prep fridge", started_at="{day}T23:50:00-05:00", ended_at=None, peak=46, limit=41,
                        acknowledged_by_role=None, action=None)
        self.send(key, self.report(units_in_range_all_day=5, breaches=[breach(), second]))
        note = self.reports()[0]["note"]
        self.assertIn("CyberLogix: 2 breaches.", note)
        self.assertIn("Prep fridge, from 23:50, still out of range when reported", note)
        self.assertIn("not acknowledged", note)


class TestBadPayloads(BundleCase):
    def assert_refused(self, key, body, field, status=422):
        response = self.send(key, body)
        self.assertEqual(response.status_code, status, (field, response.get_json()))
        if field:
            self.assertIn(field, [e["field"] for e in response.get_json()["errors"]])

    def test_each_field_is_checked(self):
        key = self.create_key()
        today = org_today(self.org)
        cases = [
            ({"date": "12/11/2026"}, "date"),
            ({"date": "2026-02-30"}, "date"),
            ({"date": (today + timedelta(days=3)).isoformat()}, "date"),
            ({"date": (today - timedelta(days=60)).isoformat()}, "date"),
            ({"site": "x" * 61}, "site"),
            ({"site": "line\nbreak"}, "site"),
            ({"units_total": 0}, "units_total"),
            ({"units_total": "7"}, "units_total"),
            ({"units_total": True}, "units_total"),
            ({"units_in_range_all_day": 8}, "units_in_range_all_day"),
            ({"breaches": None}, "breaches"),
            ({"breaches": [breach()] * 51, "units_in_range_all_day": 0}, "breaches"),
            ({"breaches": [breach()]}, "units_in_range_all_day"),
            ({"breaches": ["text"], "units_in_range_all_day": 6}, "breaches[0]"),
            ({"breaches": [breach(unit="")], "units_in_range_all_day": 6}, "breaches[0].unit"),
            ({"breaches": [breach(started_at="02:10")], "units_in_range_all_day": 6}, "breaches[0].started_at"),
            ({"breaches": [breach(started_at="{day}T02:10:00")], "units_in_range_all_day": 6},
             "breaches[0].started_at"),
            ({"breaches": [breach(ended_at="{day}T01:00:00-05:00")], "units_in_range_all_day": 6},
             "breaches[0].ended_at"),
            ({"breaches": [breach(peak="hot")], "units_in_range_all_day": 6}, "breaches[0].peak"),
            ({"breaches": [breach(peak=1e9)], "units_in_range_all_day": 6}, "breaches[0].peak"),
            ({"breaches": [breach(unit_of_measure="K")], "units_in_range_all_day": 6},
             "breaches[0].unit_of_measure"),
            ({"breaches": [breach(acknowledged_by_role="Jane Smith")], "units_in_range_all_day": 6},
             "breaches[0].acknowledged_by_role"),
            ({"breaches": [breach(action="call Jane")], "units_in_range_all_day": 6}, "breaches[0].action"),
            ({"breaches": [breach(), breach(unit="Prep fridge")], "units_in_range_all_day": 6}, "breaches"),
            ({"warmest_reading": None, "unit_of_measure": None}, "warmest_reading"),
            ({"warmest_reading": "cold"}, "warmest_reading"),
            ({"unit_of_measure": "kelvin"}, "unit_of_measure"),
            ({"log_url": "http://cyberlogix.example.com/log"}, "log_url"),
            ({"log_url": "https://user:pw@cyberlogix.example.com/log"}, "log_url"),
            ({"log_url": "javascript:alert(1)"}, "log_url"),
            ({"log_url": "https://cyberlogix.example.com/" + "a" * 600}, "log_url"),
        ]
        for changes, field in cases:
            self.assert_refused(key, self.report(**changes), field)
        self.assert_refused(key, ["not", "an", "object"], "body")
        self.assertIsNone(self.item())
        self.assertEqual(self.reports(), [])

    def test_not_json(self):
        key = self.create_key()
        response = self.client.post(URL, data="{not json", content_type="application/json",
                                    headers={"Authorization": f"Bearer {key}"})
        self.assertEqual((response.status_code, response.get_json()["error"]), (400, "invalid_json"))
        response = self.client.post(URL, data=json.dumps(self.report()), content_type="text/plain",
                                    headers={"Authorization": f"Bearer {key}"})
        self.assertEqual((response.status_code, response.get_json()["error"]), (415, "unsupported_media_type"))
        big = self.report(site=None, breaches=[], padding="x" * (connections.MAX_BODY + 10))
        response = self.send(key, big)
        self.assertEqual((response.status_code, response.get_json()["error"]), (413, "payload_too_large"))

    def test_unknown_fields_are_ignored_and_not_stored(self):
        key = self.create_key()
        response = self.send(key, self.report(staff_name="Jane Smith"))
        self.assertEqual(response.status_code, 200)
        with closing(self.db()) as conn:
            self.assertNotIn("Jane Smith", "\n".join(conn.iterdump()))


class TestRateLimits(BundleCase):
    def test_wrong_keys_are_limited_by_address(self):
        key = self.create_key()
        for _ in range(connections.BAD_KEYS[0]):
            self.assertEqual(self.send("clx_guess").status_code, 401)
        response = self.send("clx_guess")
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.get_json()["error"], "rate_limited")
        self.assertIn("Retry-After", response.headers)
        self.assertEqual(self.send(key).status_code, 429, "the right key from that address waits too")

    def test_a_key_is_limited(self):
        key = self.create_key()
        with mock.patch.object(connections, "PER_KEY", (3, timedelta(hours=1))):
            for _ in range(3):
                self.assertEqual(self.send(key).status_code, 200)
            self.assertEqual(self.send(key).status_code, 429)


class TestNoTemperatureCheck(AppTestCase):
    def test_matched_checks_0_with_a_hint(self):
        self.signup(industries=(1, 18))
        response = self.post("/app/settings/connections/cyberlogix/create")
        key = re.search(r'<p class="key mono">(clx_[A-Za-z0-9_-]+)</p>', response.get_data(as_text=True)).group(1)
        self.assertIn("None of your industries has a temperature-log check yet", response.get_data(as_text=True))
        body = {"date": (org_today({"timezone": "America/New_York"}) - timedelta(days=1)).isoformat(),
                "units_total": 3, "units_in_range_all_day": 3, "breaches": [], "warmest_reading": 37,
                "unit_of_measure": "°F"}
        response = self.client.post(URL, data=json.dumps(body), content_type="application/json",
                                    headers={"Authorization": f"Bearer {key}"})
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual((data["ok"], data["matched_checks"]), (True, 0))
        self.assertIn("RestoArmor", data["hint"])
        # Still a report: Settings says it arrived.
        self.assertIn(f"last report {body['date']}", text(self.client.get("/app/settings").get_data(as_text=True)))


class TestTheBundleNoteOnTheCheck(BundleCase):
    def test_before_connecting_it_links_to_connections(self):
        page = self.client.get(f"/app/industry/{RESTO}").get_data(as_text=True)
        self.assertIn("Kitchen Safety Bundle", page)
        self.assertIn("Let CyberLogix fill this in automatically", page)
        self.assertIn('href="/app/settings#connections"', page)
        self.assertEqual(page.count("data-bundle>"), 1, "only on the temperature check")
        self.assertNotIn("Kitchen Safety Bundle", self.client.get("/app/industry/1").get_data(as_text=True))


class TestTheUpgrade(AppTestCase):
    """A filled version-16 database gets the connection tables, and keeps everything."""

    def setUp(self):
        with mock.patch("omniarmor_app.db.MIGRATIONS", [m for m in MIGRATIONS if m[0] <= 16]):
            super().setUp()
            self.signup(industries=(RESTO,))
            self.change(RESTO, COLD, value="39")
            with closing(self.db()) as conn:
                self.assertEqual(conn.execute("SELECT MAX(version) FROM schema_version").fetchone()[0], 16)
                tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
                self.assertNotIn("connection_keys", tables)

    def test_upgrades_and_the_connection_works(self):
        self.assertGreaterEqual(SCHEMA_VERSION, 17)
        self.app = create_app(TESTING=True, DATABASE=self.db_path, SCHEDULER_ENABLED=False,
                              BACKUP_DIR=os.path.join(self.tmp.name, "backups"), BASE_URL="https://omniarmor.test")
        with closing(self.db()) as conn:
            self.assertEqual(migrate(conn), SCHEMA_VERSION)
            self.assertEqual(conn.execute("SELECT value_num FROM items WHERE rule_key = ?", (COLD,)).fetchone()[0], 39)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM connection_keys").fetchone()[0], 0)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM audit").fetchone()[0], 2)
        self.client = self.app.test_client()
        self.post("/login", {"email": "owner@example.com", "password": "correct horse battery"})
        response = self.post("/app/settings/connections/cyberlogix/create")
        self.assertEqual(response.status_code, 200)
        self.assertIn('class="key mono">clx_', response.get_data(as_text=True))


class TestThePrivacyPage(AppTestCase):
    def test_says_what_a_connection_sends(self):
        page = " ".join(self.client.get("/privacy").get_data(as_text=True).split())
        self.assertIn("When you connect CyberLogix", page)
        self.assertIn("never anyone's name", page.replace("&#39;", "'"))


class TestTheContract(unittest.TestCase):
    """docs/CYBERLOGIX-CONNECTION.md names what the code does."""

    def setUp(self):
        with open(os.path.join(ROOT, "docs", "CYBERLOGIX-CONNECTION.md"), encoding="utf-8") as f:
            self.doc = f.read()

    def test_the_doc_lists_the_codes_roles_and_limits(self):
        for text in [URL, "Authorization: Bearer", "422", "401", "429", "413", "415", "400", "invalid_payload",
                     "matched_checks", "warmest_reading", str(connections.MAX_BREACHES),
                     str(connections.PER_KEY[0]), str(connections.BAD_KEYS[0]), str(connections.OLDEST_DAYS)]:
            self.assertIn(text, self.doc, text)
        for role in connections.ROLES:
            self.assertIn(f"`{role}`", self.doc, role)
        for action in connections.ACTIONS:
            self.assertIn(f"`{action}`", self.doc, action)

    def test_the_example_in_the_doc_is_accepted(self):
        block = re.search(r"```json\n(\{\n  \"date\".*?)\n```", self.doc, re.S).group(1)
        body = json.loads(block)
        from datetime import date
        report = connections.validate(body, date.fromisoformat(body["date"]))
        self.assertEqual(report["units_total"], body["units_total"])


if __name__ == "__main__":
    unittest.main()
