"""Cookies, and the times people see.

- The one cookie, through every way in and out: https only outside
  development, out of the page's reach, sent from other sites only on a
  plain link, and kept for the session or 14 days of use, never longer.
  Its value never shows up in a page, and nothing secret is inside it.
- The server keeps every time in UTC. A date shown to people is the
  workspace's own date, or the column says UTC.
"""

import os
import re
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from http.cookies import SimpleCookie
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from e2e_helpers import table_rows  # noqa: E402
from test_webapp import PASSWORD, AppTestCase, first_rule  # noqa: E402

from omniarmor_app import create_app  # noqa: E402
from omniarmor_app.tracking import local_date  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


class TestTheOneCookie(unittest.TestCase):
    def app_for(self, env):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        clean = {k: v for k, v in os.environ.items() if not k.startswith(("OMNIARMOR_", "SESSION_COOKIE_"))}
        with mock.patch.dict(os.environ, {**clean, **env}, clear=True):
            return create_app(DATABASE=os.path.join(tmp.name, "t.db"), SCHEDULER_ENABLED=False,
                              BACKUP_DIR=os.path.join(tmp.name, "b"), BASE_URL="https://omniarmor.test")

    @staticmethod
    def https_client(app):
        client = app.test_client()
        client.environ_base["wsgi.url_scheme"] = "https"
        return client

    def walk(self, app):
        """Every way in and out. Returns [(step, signed_in, Set-Cookie header)] and every page."""
        seen, pages = [], []
        client = self.https_client(app)

        def go(step, signed_in, response):
            assert response.status_code < 500, (step, response.status_code)
            pages.append(response.get_data(as_text=True))
            seen.extend((step, signed_in, h) for h in response.headers.getlist("Set-Cookie"))
            return response

        def csrf(c):
            with c.session_transaction() as s:
                return s.get("_csrf", "")

        go("sign-in page", False, client.get("/login"))
        go("sign up", True, client.post("/signup", data={
            "csrf_token": csrf(client), "name": "Pat", "email": "pat@example.com", "password": PASSWORD,
            "org_name": "Acme", "timezone": "UTC", "industries": ["1"]}))
        go("overview", True, client.get("/app"))
        go("invite", True, client.post("/app/settings/invite", data={"csrf_token": csrf(client)}))
        go("settings", True, client.get("/app/settings"))
        go("add a kid", True, client.post("/app/academy/learners", data={
            "csrf_token": csrf(client), "nickname": "Rocket", "avatar": "rocket"}))
        go("join code", True, client.post("/app/academy/1/join-code", data={"csrf_token": csrf(client)}))
        go("sign out", False, client.post("/logout", data={"csrf_token": csrf(client)}))
        go("sign-in page again", False, client.get("/login"))
        go("wrong password", False, client.post("/login", data={
            "csrf_token": csrf(client), "email": "pat@example.com", "password": "wrong password!"}))
        go("forgot page", False, client.get("/forgot"))
        go("forgot", False, client.post("/forgot", data={"csrf_token": csrf(client), "email": "pat@example.com"}))
        go("sign-in page", False, client.get("/login"))
        go("sign in", True, client.post("/login", data={
            "csrf_token": csrf(client), "email": "pat@example.com", "password": PASSWORD}))
        with app.app_context():
            from omniarmor_app.db import get_db
            code = get_db().execute("SELECT code FROM join_codes").fetchone()[0]
        kid = self.https_client(app)
        go("kid join page", False, kid.get("/kids"))
        go("kid joins", True, kid.post("/kids", data={"csrf_token": csrf(kid), "code": code}))
        go("kid map", True, kid.get("/app/academy/1"))
        go("kid leaves", False, kid.post("/kids/leave", data={"csrf_token": csrf(kid)}))
        return seen, pages

    def check(self, app, secure):
        seen, pages = self.walk(app)
        steps = {step for step, _, _ in seen}
        self.assertTrue({"sign-in page", "sign up", "sign out", "sign in", "kid joins", "kid leaves"} <= steps, steps)
        reader = app.session_interface.get_signing_serializer(app)
        now = datetime.now(timezone.utc)
        for step, signed_in, header in seen:
            jar = SimpleCookie()
            jar.load(header)
            (name, morsel), = jar.items()
            self.assertEqual(name, "session", header)  # the one cookie
            self.assertTrue(morsel["httponly"], header)
            self.assertEqual(bool(morsel["secure"]), secure, header)
            # Lax, on purpose: a link in a reminder email opens the app signed
            # in, while a form posted from another site arrives without it.
            self.assertEqual(morsel["samesite"], "Lax", header)
            self.assertEqual(morsel["path"], "/", header)
            # Host-only: MTRX Horizon's other apps, on sibling subdomains of
            # the same parent domain, never receive it.
            self.assertFalse(morsel["domain"], header)
            if not morsel.value:  # deleted
                self.assertLess(parsedate_to_datetime(morsel["expires"]), now, header)
                continue
            for page in pages:
                self.assertNotIn(morsel.value, page, step)
            payload = reader.loads(morsel.value)
            self.assertFalse(set(payload) - {"_csrf", "_flashes", "user_id", "epoch", "ukey", "kid", "kid_org",
                                             "kid_epoch", "_permanent"}, (step, payload))
            self.assertNotIn(PASSWORD, str(payload))
            if signed_in:
                expires = parsedate_to_datetime(morsel["expires"])
                self.assertTrue(now + timedelta(days=13, hours=23) < expires <= now + timedelta(days=14, minutes=1),
                                (step, header))
            else:
                # Signed out it is only a form token: gone when the browser closes.
                self.assertFalse(morsel["expires"] or morsel["max-age"], (step, header))
                self.assertFalse({"user_id", "kid"} & set(payload), (step, payload))

    def test_in_production(self):
        self.check(self.app_for({"OMNIARMOR_ENV": "production", "SECRET_KEY": "s" * 64}), secure=True)

    def test_in_development_it_works_over_plain_http_on_this_computer(self):
        self.check(self.app_for({}), secure=False)


class TestDatesAreTheWorkspaces(AppTestCase):
    """A change made at 18:30 on 2 November in Los Angeles is 02:30 on
    3 November in UTC. Pages printed the UTC date, a day late."""

    EVENING = "2026-11-03T02:30:00+00:00"

    def setUp(self):
        super().setUp()
        self.signup()
        self.rule = first_rule(1, kind="max", mode=None)
        self.change(1, self.rule.key, value=str(self.rule.limit - 1))
        self.post("/app/academy/learners", {"nickname": "Rocket", "avatar": "rocket"})
        self.post("/app/academy/1/join-code")
        with self.db() as conn:
            conn.execute("UPDATE orgs SET timezone = 'America/Los_Angeles', academy_status = 'active',"
                         " academy_renews_at = ?", (self.EVENING,))
            conn.execute("UPDATE items SET updated_at = ?", (self.EVENING,))
            conn.execute("UPDATE join_codes SET expires_at = ?", (self.EVENING,))
            conn.commit()

    def test_report_and_check_pages(self):
        rows = table_rows(self.client.get("/app/report").get_data(as_text=True))
        row = next(r for r in rows if r and r[0].startswith(self.rule.title))
        self.assertTrue(row[-1].startswith("2026-11-02"), row)
        page = self.client.get("/app/industry/1").get_data(as_text=True)
        self.assertIn("Last updated 2026-11-02", page)
        self.assertNotIn("2026-11-03", page)

    def test_plan_and_join_code_dates(self):
        self.assertIn("renews 2026-11-02", self.client.get("/app/settings").get_data(as_text=True))
        self.assertIn("renews 2026-11-02", self.client.get("/app/academy/plan").get_data(as_text=True))
        with self.db() as conn:
            conn.execute("UPDATE learners SET track = 'launchpad', track_chosen = 1")
            conn.commit()
        self.assertIn("Works once, until 2026-11-02", self.client.get("/app/academy/1").get_data(as_text=True))

    def test_utc_only_where_it_says_so(self):
        audit = self.client.get("/app/audit").get_data(as_text=True)
        self.assertIn("When (UTC)", audit)
        head = self.client.get("/app/report.csv").get_data(as_text=True).splitlines()[0]
        self.assertIn("Last updated (UTC)", head)

    def test_local_date(self):
        tokyo, la = {"timezone": "Asia/Tokyo"}, {"timezone": "America/Los_Angeles"}
        self.assertEqual(local_date("2026-11-02T16:00:00+00:00", tokyo), "2026-11-03")
        self.assertEqual(local_date("2026-11-02T16:00:00+00:00", la), "2026-11-02")
        self.assertEqual(local_date("2026-11-03T02:30:00", la), "2026-11-02")  # no offset: stored as UTC
        self.assertEqual(local_date(self.EVENING, None), "2026-11-03")
        self.assertEqual(local_date(None, la), "")
        self.assertEqual(local_date("2026-11-03", la), "2026-11-02")  # a bare day is midnight UTC


class TestTheServerKeepsUTC(unittest.TestCase):
    def test_no_local_or_naive_clock_in_the_code(self):
        """Every "now" is utcnow() (aware, UTC) or a named zone's now. A naive
        or local one would make a comparison depend on the server's own time
        zone, or fail comparing with an aware time."""
        naive = re.compile(r"datetime\.now\(\s*\)|datetime\.utcnow\(|date\.today\(|\butcfromtimestamp\("
                           r"|fromtimestamp\((?![^)]*tz)|time\.(localtime|mktime|ctime)\(")
        files = [ROOT / "omni_armor_platform.py", *sorted((ROOT / "omniarmor_app").glob("*.py")),
                 *sorted((ROOT / "omni_armor_rules").glob("*.py"))]
        for file in files:
            for n, line in enumerate(file.read_text().splitlines(), 1):
                self.assertIsNone(naive.search(line), f"{file.name}:{n}: {line.strip()}")


if __name__ == "__main__":
    unittest.main()
