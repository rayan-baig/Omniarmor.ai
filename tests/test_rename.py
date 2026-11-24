"""1.24.0: the rename. OmniArmor is now Aegizyn, CyberLogix is now Kryozyn, and the names that may still change
(the company, its domain, the assistant, the other apps) are typed in one place, omniarmor_app/names.json.

No old name on anything a person sees (pages, Pilot's files, emails, the public pictures' sources); the company's
name comes from names.py; the old address and the old checklist addresses redirect; what posts to the old address
(Stripe, Kryozyn, health checks) is answered there; Kryozyn's old address and header still work; the old setting
name still works; and what the app wrote under the old names shows the new ones."""

import json
import os
import re
import sqlite3
import sys
import time
import unittest
from contextlib import closing
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_kryozyn import BundleCase  # noqa: E402
from test_webapp import AppTestCase  # noqa: E402

from omniarmor_app import config, connections, create_app, db, names, notify  # noqa: E402
from omniarmor_app.catalog import INDUSTRIES, OLD_SLUGS  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP = os.path.join(ROOT, "omniarmor_app")
OLD = re.compile(r"OmniArmor|Omni Armor|OMNIARMOR|CyberLogix|CYBERLOGIX|[A-Z][A-Za-z]*Armor\b|[A-Z]+ARMOR\b")
# The shared Pilot core is copied byte for byte from the company's site and never edited here.
CORE = os.path.join(APP, "static", "pilot")


def app_files(*exts):
    for folder, dirs, files in os.walk(APP):
        if folder.startswith(CORE) or "__pycache__" in folder:
            continue
        for name in files:
            if name.endswith(exts):
                yield os.path.join(folder, name)


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def strings(path):
    """The string literals in a Python file (what can reach a page, an email or a log), not its comments."""
    import ast
    import tokenize
    out = []
    with open(path, "rb") as f:
        for tok in tokenize.tokenize(f.readline):
            if tok.type == tokenize.STRING:
                try:
                    value = ast.literal_eval(tok.string)
                except (ValueError, SyntaxError):
                    value = tok.string   # an f-string: its text as written
                if isinstance(value, str):
                    out.append(value)
    return out


class TestNoOldNamesInWhatPeopleSee(unittest.TestCase):
    def test_templates_and_the_apps_own_scripts_and_styles(self):
        for path in app_files(".html", ".js", ".css", ".webmanifest", ".svg", ".txt"):
            found = OLD.findall(read(path))
            self.assertEqual(found, [], os.path.relpath(path, ROOT))

    def test_python_strings(self):
        allowed = {"OmniArmor is a product of MTRX Horizyn.",   # notify.OLD_SIGNATURES: taken off old stored emails
                   "CyberLogix", "X-CyberLogix-Signature"}      # connections.OLD_NAMES and OLD_SIGNATURE_HEADER
        for path in app_files(".py"):
            for value in strings(path):
                if value in allowed or "OMNIARMOR_ENV" in value or path.endswith("db.py") and "CyberLogix" in value:
                    continue   # migration 28's statements, which rename the old values
                self.assertIsNone(OLD.search(value), f"{os.path.relpath(path, ROOT)}: {value[:120]!r}")

    def test_the_rule_catalog_and_checklist_names(self):
        for info in INDUSTRIES.values():
            self.assertTrue(info["brand"].endswith(" Aegizyn"), info["brand"])
            self.assertNotIn("Armor", info["brand"] + info["sector"])
            self.assertEqual(info["slug"], info["brand"].lower().replace(" ", "-"))
        self.assertEqual(INDUSTRIES[2]["brand"], "Resto Aegizyn")
        self.assertEqual(INDUSTRIES[51]["brand"], "School Safety Aegizyn")
        self.assertEqual(INDUSTRIES[30]["brand"], "HR Aegizyn")


class TestTheCompanyNameIsTypedOnce(unittest.TestCase):
    """The company's name and domain appear in names.json only (and in the old signature notify strips)."""

    def test_only_names_json_holds_them(self):
        for path in app_files(".html", ".js", ".css", ".py", ".txt", ".webmanifest"):
            text = read(path)
            if path.endswith("notify.py"):
                text = text.replace('"OmniArmor is a product of MTRX Horizyn."', "")
            if path.endswith("config.py"):
                text = text.replace("MTRX_STATS_KEY", "")   # the company console's own setting's name
            for word in (names.COMPANY, names.DOMAIN, "MTRX"):
                self.assertNotIn(word, text, f"{os.path.relpath(path, ROOT)} types {word!r}")
        self.assertIn(names.COMPANY, read(os.path.join(APP, "names.json")))

    def test_the_other_apps_and_the_assistant_are_there(self):
        raw = json.loads(read(os.path.join(APP, "names.json")))
        self.assertEqual(set(raw["other_apps"]), {"RankUp", "Genesis", "Orbyt"})
        self.assertEqual((raw["app"], raw["fridge_app"], raw["assistant"], raw["assistant_next"]),
                         ("Aegizyn", "Kryozyn", "Pilot", "Astroxy"))
        self.assertEqual(names.APP_HOST, "aegizyn.mtrxhorizyn.com")
        self.assertEqual(names.FRIDGE_URL, "https://kryozyn.mtrxhorizyn.com")
        self.assertEqual(names.HELP_EMAIL, "help@mtrxhorizyn.com")
        self.assertEqual(names.OLD_APP_HOSTS, ("omniarmor.mtrxhorizyn.com",))
        self.assertEqual(names.OTHER_APPS["RankUp"], "https://rankup.mtrxhorizyn.com")

    def test_a_new_company_name_shows_everywhere(self):
        with mock.patch.object(names, "COMPANY", "Test Company"), \
                mock.patch.object(names, "SIGNATURE", "Aegizyn is a product of Test Company."), \
                mock.patch.object(notify, "SIGNATURE", "Aegizyn is a product of Test Company."):
            case = AppTestCase()
            case.setUp()
            try:
                for path in ("/", "/terms", "/privacy", "/security"):
                    page = case.client.get(path).get_data(as_text=True)
                    self.assertIn("Test Company", page, path)
                    self.assertNotIn("MTRX", page, path)
                self.assertTrue(notify.signed("Hi").rstrip().endswith("Aegizyn is a product of Test Company."))
            finally:
                case.tearDown()


class TestPagesAndEmails(AppTestCase):
    PAGES = ["/", "/industries", "/industries/resto-aegizyn", "/industries/school-safety-aegizyn",
             "/for/salons-and-barbershops", "/for/schools", "/classrooms", "/classrooms/guide", "/help", "/pricing",
             "/terms", "/privacy", "/security", "/login", "/signup", "/demo", "/sitemap.xml", "/robots.txt"]

    def test_public_pages(self):
        for path in self.PAGES:
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200, path)
            page = response.get_data(as_text=True)
            self.assertEqual(OLD.findall(page), [], path)
            self.assertNotRegex(page, r"\bomniarmor\.mtrx|cyberlogix\.mtrx", path)

    def test_signed_in_pages_and_the_demo(self):
        self.signup(industries=(2, 30, 52))
        for path in ("/app", "/app/industry/2", "/app/industry/52", "/app/report", "/app/report/summary",
                     "/app/audit", "/app/notifications", "/app/settings", "/app/plan", "/app/armo",
                     "/app/report.csv", "/app/audit.csv"):
            response = self.client.get(path)
            self.assertIn(response.status_code, (200, 302), path)
            self.assertEqual(OLD.findall(response.get_data(as_text=True)), [], path)
        self.assertIn("aegizyn-compliance-report.csv", self.client.get("/app/report.csv").headers["Content-Disposition"])
        demo = self.app.test_client()
        demo.get("/demo/business")
        self.assertEqual(OLD.findall(demo.get("/app").get_data(as_text=True)), [])

    def test_emails_say_aegizyn(self):
        self.signup(industries=(2,))
        self.app.test_client().post("/forgot", data={"email": "owner@example.com", "csrf_token": "t"})
        anon = self.app.test_client()
        self.post("/forgot", {"email": "owner@example.com"}, client=anon)
        with closing(self.db()) as conn:
            rows = [dict(r) for r in conn.execute("SELECT subject, body FROM notifications")]
        self.assertTrue(rows, "the password reset email was kept")
        bodies = [r["subject"] + "\n" + r["body"] for r in rows]
        for body in bodies:
            self.assertEqual(OLD.findall(notify.signed(body, self.app.config)), [])
        mail = notify.signed("Your checks.", self.app.config, kind="autopilot")
        self.assertIn("Sent by Aegizyn Autopilot", mail)
        self.assertTrue(mail.rstrip().endswith(names.SIGNATURE))
        # A copy stored before the rename loses its old footer, so it isn't signed twice.
        old = "Hello\n\n--\nOmniArmor is a product of MTRX Horizyn.\n"
        self.assertEqual(notify.signed(old).count("product of"), 1)
        self.assertNotIn("OmniArmor", notify.signed(old))
        self.assertEqual(self.app.config["MAIL_FROM"], "Aegizyn <no-reply@localhost>")

    def test_pilots_script_tag_carries_the_names(self):
        page = self.client.get("/").get_data(as_text=True)
        match = re.search(r"data-facts='([^']*)'", page)
        self.assertIsNotNone(match)
        import html
        facts = json.loads(html.unescape(match.group(1)))
        self.assertEqual(facts["names"]["company"], names.COMPANY)
        self.assertEqual(facts["names"]["assistant"], names.ASSISTANT)
        self.assertEqual(facts["names"]["fridge_url"], names.FRIDGE_URL)


class TestOldAddresses(AppTestCase):
    OLD_HOST = "omniarmor.mtrxhorizyn.com"

    def setUp(self):
        super().setUp()
        self.app.config["BASE_URL"] = "https://aegizyn.mtrxhorizyn.com"

    def test_pages_at_the_old_host_redirect_to_the_same_page(self):
        response = self.client.get("/industries?x=1", headers={"Host": self.OLD_HOST})
        self.assertEqual(response.status_code, 301)
        self.assertEqual(response.headers["Location"], "https://aegizyn.mtrxhorizyn.com/industries?x=1")
        self.assertEqual(self.client.get("/", headers={"Host": "aegizyn.mtrxhorizyn.com"}).status_code, 200)

    def test_what_posts_there_is_answered_there(self):
        self.assertEqual(self.client.get("/healthz", headers={"Host": self.OLD_HOST}).status_code, 200)
        response = self.client.post("/billing/stripe/webhook", data="{}", headers={"Host": self.OLD_HOST})
        self.assertNotIn(response.status_code, (301, 302, 308))
        response = self.client.post("/api/connect/cyberlogix/daily", data="{}", content_type="application/json",
                                    headers={"Host": self.OLD_HOST})
        self.assertEqual(response.status_code, 401)

    def test_old_hosts_can_be_turned_off(self):
        self.app.config["OLD_HOSTS"] = ()
        self.assertEqual(self.client.get("/", headers={"Host": self.OLD_HOST}).status_code, 200)

    def test_the_setting(self):
        with mock.patch.dict(os.environ, {"OLD_HOSTS": "a.example.com, B.example.com"}):
            self.assertEqual(config.load_config(TESTING=True)["OLD_HOSTS"], ("a.example.com", "b.example.com"))
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("OLD_HOSTS", None)
            self.assertEqual(config.load_config(TESTING=True)["OLD_HOSTS"], names.OLD_APP_HOSTS)

    def test_old_checklist_addresses_redirect(self):
        for old, new in (("restoarmor", "resto-aegizyn"), ("schoolsafetyarmor", "school-safety-aegizyn"),
                         ("ShopArmor", "shop-aegizyn"), ("hrarmor", "hr-aegizyn"), ("Resto-Aegizyn", "resto-aegizyn")):
            response = self.client.get(f"/industries/{old}")
            self.assertEqual(response.status_code, 301, old)
            self.assertTrue(response.headers["Location"].endswith(f"/industries/{new}"), old)
        self.assertEqual(len(OLD_SLUGS), len(INDUSTRIES))
        self.assertEqual(self.client.get("/industries/nosucharmor").status_code, 404)


class TestTheEnvironmentSetting(unittest.TestCase):
    def test_new_name_wins_and_the_old_still_works(self):
        self.assertEqual(config.environment({"OMNIARMOR_ENV": "production"}), "production")
        self.assertEqual(config.environment({"AEGIZYN_ENV": "production"}), "production")
        self.assertEqual(config.environment({"AEGIZYN_ENV": "development", "OMNIARMOR_ENV": "production"}),
                         "development")
        self.assertEqual(config.environment({}), "development")


class TestKryozynsOldAddressAndHeader(BundleCase):
    def test_both_addresses(self):
        key = self.create_key()
        for url in ("/api/connect/kryozyn/daily", "/api/connect/cyberlogix/daily"):
            response = self.client.post(url, data=json.dumps(self.report()), content_type="application/json",
                                        headers={"Authorization": f"Bearer {key}"})
            self.assertEqual(response.status_code, 200, url)

    def test_the_old_signature_header_still_counts(self):
        self.app.config["KITCHEN_BUNDLE_SECRET"] = "s" * 64
        key = self.create_key()
        raw = json.dumps(self.report()).encode()
        header = connections.sign("s" * 64, raw, int(time.time()))
        response = self.client.post("/api/connect/kryozyn/daily", data=raw, content_type="application/json",
                                    headers={"Authorization": f"Bearer {key}", "X-CyberLogix-Signature": header})
        self.assertEqual(response.get_json()["signature"], "valid")

    def test_what_kryozyn_fills_in_says_kryozyn(self):
        key = self.create_key()
        self.client.post("/api/connect/kryozyn/daily", data=json.dumps(self.report()), content_type="application/json",
                         headers={"Authorization": f"Bearer {key}"})
        self.assertEqual(self.item()["updated_by_name"], "Kryozyn")
        self.assertTrue(any(a["summary"].startswith("From Kryozyn") for a in self.audit()))


class TestMigration28(unittest.TestCase):
    """What the app wrote under the old names before 1.24.0 shows the new ones."""

    def test_old_rows_renamed(self):
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        with mock.patch.object(db, "MIGRATIONS", db.MIGRATIONS[:-1]):
            db.migrate(conn)
        conn.execute("INSERT INTO orgs (id, name, timezone, created_at) VALUES (1, 'Kitchen', 'UTC', '2026-01-01')")
        conn.execute("INSERT INTO audit (org_id, user_id, user_name, at, action, summary) VALUES"
                     " (1, NULL, 'CyberLogix', '2026-01-01', 'connection', 'From CyberLogix: 7 of 7 units in range')")
        conn.execute("INSERT INTO audit (org_id, user_id, user_name, at, action, summary) VALUES"
                     " (1, NULL, 'Pat', '2026-01-01', 'settings', 'Industries added: RestoArmor, SchoolSafetyArmor')")
        conn.execute("INSERT INTO items (org_id, industry_id, rule_key, value_num, updated_at, updated_by_name)"
                     " VALUES (1, 2, 'cold_holding', 38, '2026-01-01', 'CyberLogix')")
        conn.commit()
        self.assertEqual(db.migrate(conn), db.SCHEMA_VERSION)
        rows = [dict(r) for r in conn.execute("SELECT user_name, summary FROM audit ORDER BY id")]
        self.assertEqual(rows[0], {"user_name": "Kryozyn", "summary": "From Kryozyn: 7 of 7 units in range"})
        self.assertEqual(rows[1]["summary"], "Industries added: Resto Aegizyn, School Safety Aegizyn")
        self.assertEqual(conn.execute("SELECT updated_by_name FROM items").fetchone()[0], "Kryozyn")


class TestDocs(unittest.TestCase):
    def test_owner_steps_and_names_are_documented(self):
        ops = read(os.path.join(ROOT, "docs", "OPERATIONS.md"))
        self.assertIn("Upgrading to 1.24.0", ops)
        for step in ("Custom Domains", "BASE_URL=https://aegizyn.mtrxhorizyn.com", "MAIL_FROM=Aegizyn",
                     "/billing/stripe/webhook", "/api/connect/kryozyn/daily", "names.json"):
            self.assertIn(step, ops)
        self.assertIn("names.json", read(os.path.join(ROOT, "README.md")))
        self.assertIn("X-CyberLogix-Signature", read(os.path.join(ROOT, "docs", "KRYOZYN-CONNECTION.md")))


if __name__ == "__main__":
    unittest.main()
