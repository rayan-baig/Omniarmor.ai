import os
import re
import sys
import tempfile
import unittest
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from omniarmor_app import create_app  # noqa: E402
from omniarmor_app.catalog import date_mode, find_rule, rules_for  # noqa: E402
from omniarmor_app.db import MIGRATIONS, connect, migrate  # noqa: E402
from omniarmor_app.jobs import backup_database, claim_run, release_run, run_daily  # noqa: E402
from omniarmor_app.reminders import reminder_window, run_reminders  # noqa: E402
from omniarmor_app.tracking import compute_state, org_today  # noqa: E402

PASSWORD = "correct horse battery"


def first_rule(industry_id, mode=None, kind=None, policy=None):
    for r in rules_for(industry_id):
        if mode is not None and date_mode(r) != mode:
            continue
        if kind is not None and r.kind != kind:
            continue
        if policy is not None and r.policy != policy:
            continue
        return r
    raise LookupError("no matching rule")


class AppTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.tmp.name, "test.db")
        self.app = create_app(TESTING=True, DATABASE=self.db_path, SCHEDULER_ENABLED=False,
                              BACKUP_DIR=os.path.join(self.tmp.name, "backups"), BASE_URL="https://omniarmor.test")
        self.client = self.app.test_client()

    def tearDown(self):
        self.tmp.cleanup()

    # --- helpers -----------------------------------------------------------
    def csrf(self, client=None):
        client = client or self.client
        with client.session_transaction() as s:
            s.setdefault("_csrf", "test-token")
            return s["_csrf"]

    def post(self, path, data=None, client=None, **kw):
        client = client or self.client
        data = dict(data or {})
        data.setdefault("csrf_token", self.csrf(client))
        return client.post(path, data=data, **kw)

    def signup(self, email="owner@example.com", industries=(1, 18), client=None, invite=None, name="Pat Owner"):
        data = {"name": name, "email": email, "password": PASSWORD}
        if invite:
            data["invite"] = invite
        else:
            data.update({"org_name": "Acme Logistics", "timezone": "America/New_York",
                         "industries": [str(i) for i in industries]})
        return self.post("/signup", data, client=client)

    def db(self):
        return connect(self.db_path)

    def change(self, industry_id, key, action="save", client=None, **fields):
        return self.post(f"/app/industry/{industry_id}/rule/{key}", {"action": action, **fields}, client=client)


class TestPublicPages(AppTestCase):
    def test_pages_render(self):
        for path in ["/", "/industries", "/industries/fleetarmor", "/industries/ShopArmor", "/login", "/signup",
                     "/forgot", "/robots.txt", "/sitemap.xml"]:
            self.assertEqual(self.client.get(path).status_code, 200, path)

    def test_static_files_are_cached_and_versioned(self):
        page = self.client.get("/login").data.decode()
        match = re.search(r'href="(/static/app\.css\?v=\d+)"', page)
        self.assertIsNotNone(match)
        response = self.client.get(match.group(1))
        self.assertEqual(response.status_code, 200)
        self.assertIn("max-age=31536000", response.headers.get("Cache-Control", ""))
        response.close()

    def test_slogan_and_every_industry_page(self):
        self.assertIn(b"before it catches you", self.client.get("/").data)
        sitemap = self.client.get("/sitemap.xml").data.decode()
        self.assertEqual(sitemap.count("/industries/"), 50)

    def test_signup_from_industry_page_preselects_it(self):
        page = self.client.get("/signup?industry=2").data.decode()
        self.assertRegex(page, r'value="2"\s+checked')
        self.assertEqual(self.client.get("/signup?industry=999").status_code, 200)
        self.assertEqual(self.client.get("/signup?industry=abc").status_code, 200)

    def test_every_industry_page_and_its_signup_link(self):
        for slug in ["fleetarmor", "restoarmor", "shoparmor", "casinoarmor"]:
            page = self.client.get(f"/industries/{slug}").data.decode()
            link = re.search(r'href="(/signup\?industry=\d+)"', page).group(1)
            self.assertEqual(self.client.get(link).status_code, 200, link)

    def test_unknown_industry_page_404(self):
        self.assertEqual(self.client.get("/industries/notreal").status_code, 404)

    def test_health(self):
        r = self.client.get("/healthz")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json()["status"], "ok")

    def test_security_headers(self):
        r = self.client.get("/")
        self.assertIn("frame-ancestors 'none'", r.headers["Content-Security-Policy"])
        self.assertEqual(r.headers["X-Content-Type-Options"], "nosniff")
        self.assertEqual(r.headers["X-Frame-Options"], "DENY")

    def test_app_requires_sign_in(self):
        r = self.client.get("/app")
        self.assertEqual(r.status_code, 302)
        self.assertIn("/login", r.headers["Location"])


class TestAccounts(AppTestCase):
    def test_signup_creates_workspace(self):
        r = self.signup()
        self.assertEqual(r.status_code, 302)
        page = self.client.get("/app").data.decode()
        self.assertIn("Acme Logistics", page)
        self.assertIn("FleetArmor", page)
        with self.db() as conn:
            self.assertEqual(conn.execute("SELECT role FROM memberships").fetchone()[0], "owner")
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM org_industries").fetchone()[0], 2)

    def test_signup_validation(self):
        r = self.post("/signup", {"name": "", "email": "bad", "password": "short", "org_name": "", "timezone": "Mars/Base"})
        self.assertEqual(r.status_code, 400)
        page = r.data.decode()
        for text in ["Enter your name", "valid email", "at least 10 characters", "company name", "at least one industry",
                     "valid timezone"]:
            self.assertIn(text, page)

    def test_duplicate_email_rejected(self):
        self.signup()
        other = self.app.test_client()
        r = self.signup(email="OWNER@example.com", client=other)
        self.assertEqual(r.status_code, 400)
        self.assertIn(b"already exists", r.data)

    def test_password_is_hashed(self):
        self.signup()
        with self.db() as conn:
            stored = conn.execute("SELECT password_hash FROM users").fetchone()[0]
        self.assertNotIn(PASSWORD, stored)

    def test_login_logout(self):
        self.signup()
        self.post("/logout")
        self.assertEqual(self.client.get("/app").status_code, 302)
        r = self.post("/login", {"email": "owner@example.com", "password": PASSWORD})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(self.client.get("/app").status_code, 200)

    def test_invite_count_ignores_expired(self):
        self.signup()
        with self.db() as conn:
            org_id = conn.execute("SELECT id FROM orgs").fetchone()[0]
            conn.execute("INSERT INTO invites (token_hash, org_id, created_at, expires_at) VALUES ('h', ?, ?, ?)",
                         (org_id, "2020-01-01T00:00:00+00:00", "2020-01-02T00:00:00+00:00"))
            conn.commit()
        self.assertNotIn(b"unused invite link", self.client.get("/app/settings").data)

    def test_wrong_password_and_rate_limit(self):
        self.signup()
        self.post("/logout")
        for _ in range(5):
            self.assertEqual(self.post("/login", {"email": "owner@example.com", "password": "nope"}).status_code, 401)
        r = self.post("/login", {"email": "owner@example.com", "password": PASSWORD})
        self.assertEqual(r.status_code, 429)

    def test_login_redirect_is_safe(self):
        self.signup()
        for bad in ["//evil.example/x", "/%09/evil.example", "/\\evil.example", "https://evil.example", "/%0d%0a/x"]:
            self.post("/logout")
            r = self.post(f"/login?next={bad}", {"email": "owner@example.com", "password": PASSWORD})
            self.assertTrue(r.headers["Location"].endswith("/app"), bad)
        self.post("/logout")
        r = self.post("/login?next=/app/report", {"email": "owner@example.com", "password": PASSWORD})
        self.assertTrue(r.headers["Location"].endswith("/app/report"))

    def test_control_characters_in_names_rejected(self):
        r = self.post("/signup", {"name": "Pat", "email": "p@example.com", "password": PASSWORD,
                                  "org_name": "Acme\r\nBcc: x@y.com", "timezone": "UTC", "industries": ["1"]})
        self.assertEqual(r.status_code, 400)
        self.signup()
        self.post("/app/settings/company", {"name": "Bad\nName", "timezone": "UTC", "industries": ["1"]})
        with self.db() as conn:
            self.assertEqual(conn.execute("SELECT name FROM orgs").fetchone()[0], "Acme Logistics")

    def test_reset_requests_do_not_lock_the_account(self):
        self.signup()
        self.post("/logout")
        anon = self.app.test_client()
        for _ in range(6):
            self.post("/forgot", {"email": "owner@example.com"}, client=anon)
        r = self.post("/login", {"email": "owner@example.com", "password": PASSWORD})
        self.assertEqual(r.status_code, 302)
        with self.db() as conn:
            sent = conn.execute("SELECT COUNT(*) FROM notifications WHERE kind = 'password_reset'").fetchone()[0]
        self.assertEqual(sent, 3)  # capped per hour

    def test_locked_out_user_can_still_reset(self):
        self.signup()
        self.post("/logout")
        for _ in range(5):
            self.post("/login", {"email": "owner@example.com", "password": "nope"})
        self.post("/forgot", {"email": "owner@example.com"})
        with self.db() as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM notifications WHERE kind = 'password_reset'").fetchone()[0], 1)

    def test_proxy_client_address_used(self):
        app = create_app(TESTING=True, DATABASE=self.db_path, SCHEDULER_ENABLED=False, TRUSTED_PROXIES=1)
        client = app.test_client()
        with client.session_transaction() as s:
            s["_csrf"] = "t"
        for i in range(5):
            client.post("/login", data={"csrf_token": "t", "email": f"u{i}@example.com", "password": "x"},
                        headers={"X-Forwarded-For": f"203.0.113.{i}"})
        with self.db() as conn:
            keys = {r[0] for r in conn.execute("SELECT key FROM login_failures WHERE key LIKE 'ip:%'")}
        self.assertEqual(len(keys), 5)

    def test_csrf_required(self):
        self.signup()
        r = self.client.post("/app/settings/reminders", data={"email_reminders": "on"})
        self.assertEqual(r.status_code, 400)
        r = self.client.post("/app/settings/reminders", data={"csrf_token": "wrong"})
        self.assertEqual(r.status_code, 400)

    def test_password_reset_flow(self):
        self.signup()
        other_device = self.app.test_client()
        self.post("/login", {"email": "owner@example.com", "password": PASSWORD}, client=other_device)
        self.assertEqual(other_device.get("/app").status_code, 200)
        anon = self.app.test_client()
        self.post("/forgot", {"email": "owner@example.com"}, client=anon)
        self.post("/forgot", {"email": "nobody@example.com"}, client=anon)  # same response, no email
        with self.db() as conn:
            rows = conn.execute("SELECT body FROM notifications WHERE kind = 'password_reset'").fetchall()
        self.assertEqual(len(rows), 1)
        token = re.search(r"/reset/(\S+)", rows[0]["body"]).group(1)
        self.assertEqual(self.post(f"/reset/{token}", {"password": "short"}, client=anon).status_code, 400)
        r = self.post(f"/reset/{token}", {"password": "a brand new password"}, client=anon)
        self.assertEqual(r.status_code, 302)
        self.assertEqual(other_device.get("/app").status_code, 302)  # old sessions signed out
        self.assertEqual(self.post(f"/reset/{token}", {"password": "another new password"}, client=anon).status_code, 302)
        self.post("/logout", client=anon)
        r = self.post("/login", {"email": "owner@example.com", "password": "a brand new password"}, client=anon)
        self.assertEqual(r.status_code, 302)


class TestTracking(AppTestCase):
    def setUp(self):
        super().setUp()
        self.signup()

    def test_number_reading_and_audit(self):
        rule = first_rule(1, kind="max", mode=None)
        self.change(1, rule.key, value=str(rule.limit + 1))
        page = self.client.get("/app/industry/1").data.decode()
        self.assertIn("BLOCKED", page.upper())
        with self.db() as conn:
            row = conn.execute("SELECT * FROM audit WHERE rule_key = ?", (rule.key,)).fetchone()
        self.assertIn("no reading", row["summary"])
        self.assertEqual(row["action"], "reading")

    def test_invalid_number(self):
        rule = first_rule(1, kind="max", mode=None)
        self.change(1, rule.key, value="abc")
        self.assertIn(b"Enter a number", self.client.get("/app/industry/1").data)
        self.change(1, rule.key, value="inf")
        self.assertIn(b"real number", self.client.get("/app/industry/1").data)

    def test_yes_no(self):
        rule = first_rule(1, kind="required")
        self.change(1, rule.key, answer="no")
        with self.db() as conn:
            self.assertEqual(conn.execute("SELECT value_bool FROM items WHERE rule_key = ?", (rule.key,)).fetchone()[0], 0)
        self.change(1, rule.key, answer="maybe")
        self.assertIn(b"Choose Yes or No", self.client.get("/app/industry/1").data)

    def test_date_tracking_and_done_today(self):
        rule = first_rule(1, mode="since")
        with self.db() as conn:
            org = conn.execute("SELECT * FROM orgs").fetchone()
        today = org_today(org)
        overdue = today - timedelta(days=int(rule.limit) + 5)
        self.change(1, rule.key, date=overdue.isoformat())
        with self.db() as conn:
            row = conn.execute("SELECT * FROM items WHERE rule_key = ?", (rule.key,)).fetchone()
            row = dict(row, updated_by_name="x")
        state = compute_state(1, rule, row, today)
        self.assertEqual(state.level, "BLOCKED")
        self.assertEqual(state.days_left, -5)
        self.change(1, rule.key, action="done_today")
        with self.db() as conn:
            row = dict(conn.execute("SELECT * FROM items WHERE rule_key = ?", (rule.key,)).fetchone(), updated_by_name="x")
            actions = [r[0] for r in conn.execute("SELECT action FROM audit WHERE rule_key = ? ORDER BY id", (rule.key,))]
        state = compute_state(1, rule, row, today)
        self.assertEqual(state.level, "CLEARED")
        self.assertEqual(state.due_date, today + timedelta(days=int(rule.limit)))
        self.assertEqual(actions, ["reading", "done"])

    def test_future_since_date_rejected(self):
        rule = first_rule(1, mode="since")
        self.change(1, rule.key, date=(date.today() + timedelta(days=30)).isoformat())
        self.assertIn(b"in the future", self.client.get("/app/industry/1").data)

    def test_until_mode(self):
        for iid in range(1, 51):
            try:
                rule = first_rule(iid, mode="until")
                break
            except LookupError:
                continue
        else:
            self.skipTest("no countdown rule in catalog")
        today = date(2026, 6, 1)
        row = {"value_num": None, "value_bool": None, "value_date": (today - timedelta(days=3)).isoformat(),
               "limit_override": None, "warn_override": None, "updated_at": None, "updated_by_name": None}
        state = compute_state(iid, rule, row, today)
        self.assertEqual(state.level, "BLOCKED")
        self.assertLess(state.days_left, 0)

    def test_policy_override(self):
        iid, rule = next((i, r) for i in range(1, 51) for r in rules_for(i) if r.policy and r.kind == "max")
        self.post("/app/settings/company", {"name": "Acme Logistics", "timezone": "America/New_York",
                                            "industries": ["1", "18", str(iid)]})
        self.change(iid, rule.key, action="override", limit=str(rule.limit * 2), warn=str(rule.limit))
        with self.db() as conn:
            row = conn.execute("SELECT limit_override FROM items WHERE industry_id = ? AND rule_key = ?", (iid, rule.key)).fetchone()
        self.assertEqual(row[0], rule.limit * 2)
        self.change(iid, rule.key, action="override", limit="1", warn="5")
        self.assertIn(b"warning point", self.client.get(f"/app/industry/{iid}").data)

    def test_non_policy_override_rejected(self):
        rule = first_rule(1, kind="max", policy=False)
        self.change(1, rule.key, action="override", limit="99")
        self.assertIn(b"cannot be changed", self.client.get("/app/industry/1").data)

    def test_industry_not_in_workspace(self):
        self.assertEqual(self.client.get("/app/industry/30").status_code, 404)
        self.assertEqual(self.change(30, rules_for(30)[0].key, value="1").status_code, 404)
        self.assertEqual(self.change(1, "not_a_rule", value="1").status_code, 404)

    def test_workspaces_are_private(self):
        rule = first_rule(1, kind="max", mode=None)
        self.change(1, rule.key, value="999")
        other = self.app.test_client()
        self.signup(email="rival@example.com", industries=(1,), client=other)
        page = other.get("/app/industry/1").data.decode()
        self.assertNotIn('value="999"', page)
        self.assertNotIn(rule.title, other.get("/app/audit").data.decode())
        with self.db() as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM items").fetchone()[0], 1)
        self.assertEqual(other.get("/app/audit.csv").data.decode().count("999"), 0)

    def test_reports_and_csv(self):
        rule = first_rule(1, kind="max", mode=None)
        self.change(1, rule.key, value="=HYPERLINK(1)")  # invalid number, rejected
        self.change(1, rule.key, value="3")
        self.assertEqual(self.client.get("/app/report").status_code, 200)
        csv_text = self.client.get("/app/report.csv").data.decode()
        self.assertIn(rule.title, csv_text)
        self.assertEqual(len(csv_text.strip().splitlines()), 21)  # header + 20 checks
        audit_csv = self.client.get("/app/audit.csv")
        self.assertEqual(audit_csv.mimetype, "text/csv")


class TestTeam(AppTestCase):
    def test_invite_member_and_permissions(self):
        self.signup()
        self.post("/app/settings/invite")
        page = self.client.get("/app/settings").data.decode()
        link = re.search(r"https://omniarmor\.test/signup\?invite=([\w-]+)", page)
        self.assertIsNotNone(link)
        member = self.app.test_client()
        self.assertIn(b"Join your team", member.get(f"/signup?invite={link.group(1)}").data)
        self.signup(email="member@example.com", client=member, invite=link.group(1), name="Sam Member")
        self.assertIn(b"Acme Logistics", member.get("/app").data)
        self.assertEqual(self.post("/app/settings/invite", client=member).status_code, 403)
        self.assertEqual(self.post("/app/settings/delete", {"confirm": "Acme Logistics"}, client=member).status_code, 403)
        third = self.app.test_client()
        r = self.signup(email="late@example.com", client=third, invite=link.group(1))
        self.assertIn(r.status_code, (302, 400))
        with self.db() as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM memberships").fetchone()[0], 2)  # used once only
            self.assertIsNone(conn.execute("SELECT 1 FROM users WHERE email = 'late@example.com'").fetchone())

        with self.db() as conn:
            member_id = conn.execute("SELECT id FROM users WHERE email = 'member@example.com'").fetchone()[0]
        self.post(f"/app/settings/member/{member_id}/remove")
        self.assertEqual(member.get("/app").status_code, 302)

    def test_delete_workspace(self):
        self.signup()
        self.post("/app/settings/delete", {"confirm": "wrong"})
        self.assertEqual(self.client.get("/app").status_code, 200)
        self.post("/app/settings/delete", {"confirm": "Acme Logistics"})
        self.assertEqual(self.client.get("/app").status_code, 302)
        with self.db() as conn:
            for table in ("orgs", "users", "items", "audit", "memberships"):
                self.assertEqual(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0], 0, table)


class TestReminders(AppTestCase):
    def test_windows(self):
        self.assertIsNone(reminder_window(31))
        self.assertIsNone(reminder_window(None))
        self.assertEqual(reminder_window(30), "due-in-30")
        self.assertEqual(reminder_window(8), "due-in-30")
        self.assertEqual(reminder_window(7), "due-in-7")
        self.assertEqual(reminder_window(2), "due-in-7")
        self.assertEqual(reminder_window(1), "due-in-1")
        self.assertEqual(reminder_window(0), "due-today")
        self.assertEqual(reminder_window(-1), "overdue-week-0")
        self.assertEqual(reminder_window(-7), "overdue-week-0")
        self.assertEqual(reminder_window(-8), "overdue-week-1")

    def _seed_due_in(self, days, rule=None):
        rule = rule or first_rule(1, mode="since")
        today = date(2026, 6, 1)
        with self.db() as conn:
            org_id = conn.execute("SELECT id FROM orgs").fetchone()[0]
            conn.execute("INSERT OR REPLACE INTO items (org_id, industry_id, rule_key, value_date) VALUES (?, 1, ?, ?)",
                         (org_id, rule.key, (today - timedelta(days=int(rule.limit) - days)).isoformat()))
            conn.commit()
        return rule, today

    def test_missed_day_is_caught_up(self):
        self.signup()
        rule, today = self._seed_due_in(5)  # the 7-day morning was missed; 5 days left is still in that window
        with self.db() as conn:
            summary = run_reminders(conn, dict(self.app.config), today_for=lambda org: today)
        self.assertEqual(summary["reminders"], 1)

    def test_failed_email_is_retried(self):
        self.signup()
        rule, today = self._seed_due_in(7)
        broken = dict(self.app.config, SMTP_HOST="127.0.0.1", SMTP_PORT=1)
        with self.db() as conn:
            failed = run_reminders(conn, broken, today_for=lambda org: today)
            retried = run_reminders(conn, dict(self.app.config), today_for=lambda org: today)
            statuses = [r[0] for r in conn.execute("SELECT status FROM notifications WHERE kind = 'reminder' ORDER BY id")]
        self.assertEqual(failed["reminders"], 0)
        self.assertEqual(retried["reminders"], 1)
        self.assertEqual(statuses, ["failed", "logged"])

    def test_bad_company_name_cannot_break_reminders(self):
        self.signup()
        with self.db() as conn:
            conn.execute("UPDATE orgs SET name = ?", ("Acme\r\nBcc: attacker@example.com",))
            conn.commit()
        rule, today = self._seed_due_in(7)
        cfg = dict(self.app.config, SMTP_HOST="127.0.0.1", SMTP_PORT=1)
        with self.db() as conn:
            summary = run_reminders(conn, cfg, today_for=lambda org: today)
        self.assertEqual(summary["errors"], 0)

    def test_digest_sent_once(self):
        self.signup()
        rule = first_rule(1, mode="since")
        today = date(2026, 6, 1)
        last_done = today - timedelta(days=int(rule.limit) - 7)  # due in 7 days
        with self.db() as conn:
            org_id = conn.execute("SELECT id FROM orgs").fetchone()[0]
            conn.execute("INSERT INTO items (org_id, industry_id, rule_key, value_date) VALUES (?, 1, ?, ?)",
                         (org_id, rule.key, last_done.isoformat()))
            conn.commit()
            cfg = dict(self.app.config)
            first = run_reminders(conn, cfg, today_for=lambda org: today)
            second = run_reminders(conn, cfg, today_for=lambda org: today)
            next_day = run_reminders(conn, cfg, today_for=lambda org: today + timedelta(days=1))
            notes = conn.execute("SELECT * FROM notifications WHERE kind = 'reminder'").fetchall()
        self.assertEqual(first["reminders"], 1)
        self.assertEqual(second["reminders"], 0)
        self.assertEqual(next_day["reminders"], 0)  # 6 days left: same window, already reminded
        self.assertEqual(len(notes), 1)
        self.assertEqual(notes[0]["status"], "logged")
        self.assertIn("due in 7 days", notes[0]["body"])
        self.assertIn(rule.title, notes[0]["body"])

    def test_reminders_respect_opt_out(self):
        self.signup()
        self.post("/app/settings/reminders", {})
        rule = first_rule(1, mode="since")
        today = date(2026, 6, 1)
        with self.db() as conn:
            org_id = conn.execute("SELECT id FROM orgs").fetchone()[0]
            conn.execute("INSERT INTO items (org_id, industry_id, rule_key, value_date) VALUES (?, 1, ?, ?)",
                         (org_id, rule.key, (today - timedelta(days=int(rule.limit))).isoformat()))
            conn.commit()
            summary = run_reminders(conn, dict(self.app.config), today_for=lambda org: today)
        self.assertEqual(summary["reminders"], 1)
        self.assertEqual(summary["digests"], 0)


class TestJobs(AppTestCase):
    def test_daily_claim_is_once_per_day(self):
        with self.db() as conn:
            self.assertTrue(claim_run(conn, "daily", "2026-06-01"))
            self.assertFalse(claim_run(conn, "daily", "2026-06-01"))
            release_run(conn, "daily", "2026-06-01")
            self.assertTrue(claim_run(conn, "daily", "2026-06-01"))

    def test_stale_claim_can_be_retaken(self):
        with self.db() as conn:
            conn.execute("INSERT INTO job_runs (job, run_date, started_at) VALUES ('daily', '2026-06-02', '2026-06-02T00:00:00+00:00')")
            conn.commit()
            self.assertTrue(claim_run(conn, "daily", "2026-06-02"))

    def test_concurrent_migrations(self):
        path = os.path.join(self.tmp.name, "fresh.db")
        a, b = connect(path), connect(path)
        self.assertEqual(migrate(a), migrate(b))
        self.assertEqual(b.execute("SELECT COUNT(*) FROM schema_version").fetchone()[0], len(MIGRATIONS))

    def test_run_daily_force_and_backup_pruning(self):
        cfg = dict(self.app.config, BACKUP_KEEP=2)
        made = [backup_database(cfg) for _ in range(3)]
        self.assertEqual(len(set(made)), 3)
        self.assertEqual(sorted(os.listdir(cfg["BACKUP_DIR"])), sorted(os.path.basename(m) for m in made[1:]))
        result = run_daily(cfg, force=True)
        self.assertIn("backup=omniarmor-", result)

    def test_find_rule(self):
        self.assertIsNone(find_rule(99, "x"))
        self.assertIsNone(find_rule(1, "x"))
        self.assertIsNotNone(find_rule(1, rules_for(1)[0].key))


if __name__ == "__main__":
    unittest.main()
