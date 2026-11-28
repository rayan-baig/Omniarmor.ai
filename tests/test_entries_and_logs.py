"""1.11.0: checks with one entry per item, the illness log, and the starter
lists for salons, tattoo studios and gyms.

- A check like the 7-day date marking holds one entry per food batch, and
  cold holding one reading per fridge: each entry has its own value and
  deadline, and the check's status is the worst of them.
- The migration keeps every value: one saved before becomes the first entry.
- "Sick employees kept off work" keeps its Yes-is-bad answer and gains a
  dated log, by first name or initials only.
- SalonArmor, InkArmor and GymArmor each cite a real, general source, say
  where rules vary, and are what their trade pages lead with.
"""

import os
import re
import sys
import tempfile
import unittest
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from omni_armor_rules import CATALOG  # noqa: E402
from omniarmor_app import trades  # noqa: E402
from omniarmor_app.catalog import FIRST_ENTRY, INDUSTRIES, MULTI_CHECKS, find_rule  # noqa: E402
from omniarmor_app.db import MIGRATIONS, connect, migrate  # noqa: E402
from omniarmor_app.tracking import clean_person  # noqa: E402
from test_webapp import AppTestCase  # noqa: E402

RESTO = 2


class EntryCase(AppTestCase):
    def setUp(self):
        super().setUp()
        self.signup(industries=(RESTO,))
        with self.db() as conn:
            self.org = conn.execute("SELECT * FROM orgs").fetchone()

    def entry(self, key, action="add", **fields):
        return self.post(f"/app/industry/{RESTO}/rule/{key}/entries", {"action": action, **fields})

    def state(self, key):
        from omniarmor_app.tracking import states_for_org
        with self.db() as conn:
            return next(s for s in states_for_org(conn, self.org, industry_ids=[RESTO]) if s.key == key)

    def today(self):
        from omniarmor_app.tracking import org_today
        return org_today(self.org)


class TestOneEntryPerItem(EntryCase):
    def test_each_batch_has_its_own_deadline_and_the_check_is_the_worst(self):
        today = self.today()
        self.entry("date_marking", label="Chicken salad", date=today.isoformat())
        self.entry("date_marking", label="Cut melon", date=(today - timedelta(days=5)).isoformat())
        self.entry("date_marking", label="Opened ham", date=(today - timedelta(days=8)).isoformat())
        s = self.state("date_marking")
        self.assertEqual([e["label"] for e in s.entries], ["Opened ham", "Cut melon", "Chicken salad"])
        self.assertEqual([e["state"].level for e in s.entries], ["BLOCKED", "WARNING", "CLEARED"])
        dues = {e["label"]: e["state"].due_date for e in s.entries}
        self.assertEqual(dues["Chicken salad"], today + timedelta(days=6))   # made today is day 1 of 7
        self.assertEqual(dues["Cut melon"], today + timedelta(days=1))
        self.assertEqual(s.level, "BLOCKED")
        self.assertIn("Opened ham", s.message)
        page = self.client.get(f"/app/industry/{RESTO}").data.decode()
        self.assertIn('data-entries="3"', page)
        self.assertIn("Add a food batch or container", page)
        # Throwing out the old ham clears the problem; the check is now the melon's warning.
        ham = next(e for e in s.entries if e["label"] == "Opened ham")
        self.entry("date_marking", "remove", entry_id=str(ham["id"]))
        self.assertEqual(self.state("date_marking").level, "WARNING")

    def test_one_reading_per_fridge(self):
        self.entry("cold_holding", label="Walk-in cooler", value="38")
        self.entry("cold_holding", label="Prep fridge", value="40.5")
        s = self.state("cold_holding")
        self.assertEqual(s.level, "WARNING")
        self.assertEqual(len(s.entries), 2)
        prep = next(e for e in s.entries if e["label"] == "Prep fridge")
        self.entry("cold_holding", "save", entry_id=str(prep["id"]), value="44")
        self.assertEqual(self.state("cold_holding").level, "BLOCKED")
        with self.db() as conn:
            trail = [r[0] for r in conn.execute("SELECT summary FROM audit WHERE rule_key = 'cold_holding'")]
        self.assertTrue(any("Prep fridge: 40.5°F → 44°F" in t for t in trail), trail)
        # The first entry is the check's own value, as before (a connected app writes it too).
        with self.db() as conn:
            item = conn.execute("SELECT value_num, label FROM items WHERE rule_key = 'cold_holding'").fetchone()
        self.assertEqual((item["value_num"], item["label"]), (38, "Walk-in cooler"))

    def test_removing_the_first_entry_moves_the_next_one_up(self):
        self.entry("cold_holding", label="Walk-in cooler", value="38")
        self.entry("cold_holding", label="Bar fridge", value="39")
        self.entry("cold_holding", "remove", entry_id="main")
        s = self.state("cold_holding")
        self.assertEqual([(e["id"], e["label"], e["state"].value) for e in s.entries], [("main", "Bar fridge", 39)])
        self.entry("cold_holding", "remove", entry_id="main")
        self.assertEqual(self.state("cold_holding").level, "NONE")

    def test_a_bulk_update_leaves_entry_checks_alone(self):
        self.entry("date_marking", label="Soup", date=self.today().isoformat())
        response = self.post(f"/app/industry/{RESTO}/bulk", {"bulk_action": "done", "keys": ["date_marking"]})
        self.assertEqual(response.status_code, 302)
        page = self.client.get(f"/app/industry/{RESTO}").data.decode()
        self.assertIn("has one entry per food batch or container", page)

    def test_an_entry_needs_a_name_and_a_value(self):
        self.entry("cold_holding", label="", value="38")
        self.entry("cold_holding", label="Walk-in", value="")
        self.entry("date_marking", label="Soup", date=(self.today() + timedelta(days=2)).isoformat())
        self.assertEqual(self.state("cold_holding").entries, [])
        self.assertEqual(self.state("date_marking").entries, [])

    def test_a_check_with_one_value_stays_the_same(self):
        self.change(RESTO, "certified_food_manager", answer="yes")
        self.assertEqual(self.state("certified_food_manager").entries, [])
        self.assertEqual(self.post(f"/app/industry/{RESTO}/rule/certified_food_manager/entries",
                                   {"action": "add", "label": "x"}).status_code, 404)


class TestTheMigrationKeepsEveryValue(unittest.TestCase):
    def test_a_saved_value_becomes_the_first_entry(self):
        path = os.path.join(tempfile.mkdtemp(), "old.db")
        conn = connect(path)
        conn.execute("CREATE TABLE schema_version (version INTEGER NOT NULL)")
        for version, sql in MIGRATIONS:
            if version > 25:
                break
            for statement in sql.replace("{TRIAL_DAYS}", "14").split(";"):
                if statement.strip():
                    conn.execute(statement)
            conn.execute("INSERT INTO schema_version (version) VALUES (?)", (version,))
        conn.execute("INSERT INTO orgs (id, name, timezone, created_at) VALUES (1, 'Diner', 'UTC', '2026-01-01')")
        conn.executemany("INSERT INTO items (org_id, industry_id, rule_key, value_num, value_date, updated_at)"
                         " VALUES (1, 2, ?, ?, ?, '2026-11-01')",
                         [("cold_holding", 39, None), ("date_marking", None, "2026-11-18"),
                          ("hot_holding", None, None), ("certified_food_manager", None, None)])
        conn.commit()
        self.assertEqual(migrate(conn), MIGRATIONS[-1][0])
        rows = {r["rule_key"]: r for r in conn.execute("SELECT * FROM items")}
        self.assertEqual((rows["cold_holding"]["value_num"], rows["cold_holding"]["label"]), (39, "Fridge 1"))
        self.assertEqual((rows["date_marking"]["value_date"], rows["date_marking"]["label"]),
                         ("2026-11-18", "Food batch 1"))
        self.assertIsNone(rows["hot_holding"]["label"])            # nothing saved, nothing named
        self.assertIsNone(rows["certified_food_manager"]["label"])
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM check_entries").fetchone()[0], 0)
        from omniarmor_app.tracking import states_for_org
        org = conn.execute("SELECT * FROM orgs").fetchone()
        conn.execute("INSERT INTO org_industries VALUES (1, 2)")
        cold = next(s for s in states_for_org(conn, org, today=date(2026, 11, 20)) if s.key == "cold_holding")
        self.assertEqual([(e["label"], e["state"].value) for e in cold.entries], [("Fridge 1", 39)])
        self.assertEqual(cold.level, "CLEARED")   # 39°F is inside the 41°F limit
        conn.close()

    def test_first_entry_names_match_the_migration(self):
        sql = dict(MIGRATIONS)[26]
        for (industry_id, key), name in FIRST_ENTRY.items():
            if industry_id == RESTO:
                self.assertIn(f"'{name}'", sql, key)


class TestIllnessLog(EntryCase):
    KEY = "sick_employee_excluded"

    def log(self, **fields):
        data = {"reported_on": self.today().isoformat(), "person": "Sam", "reported": "vomiting",
                "did": "sent_home"}
        data.update(fields)
        return self.post(f"/app/industry/{RESTO}/rule/{self.KEY}/illness", data)

    def rows(self):
        with self.db() as conn:
            return conn.execute("SELECT * FROM illness_log").fetchall()

    def test_first_names_or_initials_only(self):
        for name in ("Sam", "S.L.", "Ana-Lu", "Zoë"):
            self.assertEqual(clean_person(name), name)
        for name in ("Sam Lopez", "sam@example.com", "S4m", "", "A" * 21):
            self.assertIsNone(clean_person(name), name)
        self.log(person="Sam Lopez")
        self.assertEqual(self.rows(), [])
        self.log(person="S.L.")
        self.assertEqual([r["person"] for r in self.rows()], ["S.L."])
        page = self.client.get(f"/app/industry/{RESTO}").data.decode()
        self.assertIn("First name or initials only", page)
        self.assertIn('data-illness-log="1"', page)

    def test_a_report_that_means_going_home_cant_be_marked_restricted(self):
        self.log(reported="diarrhea", did="restricted")
        self.assertEqual(self.rows(), [])
        self.log(reported="sore_throat_fever", did="restricted")
        self.assertEqual(len(self.rows()), 1)

    def test_the_audit_trail_says_when_not_who_or_what(self):
        self.log(person="Priya", reported="jaundice")
        with self.db() as conn:
            trail = " ".join(r[0] for r in conn.execute("SELECT summary FROM audit"))
        self.assertIn("illness log", trail)
        self.assertNotIn("Priya", trail)
        self.assertNotIn("aundice", trail)
        row = self.rows()[0]
        self.post(f"/app/industry/{RESTO}/rule/{self.KEY}/illness", {"action": "remove", "entry_id": str(row["id"])})
        self.assertEqual(self.rows(), [])

    def test_yes_is_still_the_bad_answer(self):
        self.change(RESTO, self.KEY, answer="yes")
        self.assertEqual(self.state(self.KEY).level, "BLOCKED")
        self.change(RESTO, self.KEY, answer="no")
        response = self.post(f"/app/industry/{RESTO}/bulk", {"bulk_action": "yes", "keys": [self.KEY]})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.state(self.KEY).level, "CLEARED")
        self.log()   # a log entry never changes the answer
        self.assertEqual(self.state(self.KEY).level, "CLEARED")

    def test_only_the_workspace_sees_its_log(self):
        self.log(person="Kai")
        other = self.app.test_client()
        self.signup(email="other@example.com", industries=(RESTO,), client=other)
        page = other.get(f"/app/industry/{RESTO}").data.decode()
        # As a whole word: the page's random CSRF token can contain the letters "Kai".
        self.assertNotRegex(page, r"\bKai\b")


class TestTradeStarterLists(unittest.TestCase):
    NEW = {52: "salons-and-barbershops", 53: "tattoo-and-piercing-studios", 54: "gyms-and-fitness-studios"}

    def test_each_new_industry_has_ten_checks_with_a_source(self):
        for industry_id in self.NEW:
            rules = CATALOG[industry_id]
            self.assertEqual(len(rules), 10)
            for r in rules:
                self.assertTrue(r.citation.strip(), r.key)
                # Each names its rule: a federal rule by number, or the kind of local rule and that it varies,
                # or says it is good practice.
                self.assertRegex(r.citation, r"CFR \d|vary|varies|good practice|maker|insurer|label", r.key)
                if not re.search(r"CFR \d", r.citation):
                    self.assertTrue(r.policy, f"{r.key}: a local rule is a setting the business can change")

    def test_the_trade_pages_lead_with_their_own_list(self):
        for industry_id, slug in self.NEW.items():
            trade = trades.BY_SLUG[slug]
            self.assertEqual(trade.own, (industry_id,))
            self.assertEqual(trade.groups[0][0], industry_id)
            self.assertIn("check your local rules", trade.groups[0][2])
            for key in trade.groups[0][1]:
                self.assertIsNotNone(find_rule(industry_id, key), key)
        self.assertIn(INDUSTRIES[52]["brand"], "SalonArmor")

    def test_entry_checks_exist(self):
        for industry_id, key in MULTI_CHECKS:
            self.assertIsNotNone(find_rule(industry_id, key), key)


class TestTradePages(AppTestCase):
    def test_the_pages_render_with_the_new_lists(self):
        for slug in TestTradeStarterLists.NEW.values():
            page = self.client.get(f"/for/{slug}").data.decode()
            self.assertIn("check your local rules", page)
        for brand in ("salonarmor", "inkarmor", "gymarmor"):
            self.assertEqual(self.client.get(f"/industries/{brand}").status_code, 200)


if __name__ == "__main__":
    unittest.main()
