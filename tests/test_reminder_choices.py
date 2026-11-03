"""Each person chooses which reminder emails they get (Settings, "Your
reminder emails"): the daily digest, the time-limit alerts and, for the
account that gets Autopilot's emails, the weekly Autopilot report. The
senders respect each choice."""

import os
import re
import sqlite3
import sys
import unittest
from datetime import date, datetime
from unittest import mock
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from e2e_helpers import flashes, post_forms  # noqa: E402
from test_webapp import AppTestCase  # noqa: E402

from omniarmor_app import autopilot  # noqa: E402
from omniarmor_app.db import MIGRATIONS, SCHEMA_VERSION, connect, migrate  # noqa: E402
from omniarmor_app.reminders import run_clock_alerts, run_reminders  # noqa: E402

NY = ZoneInfo("America/New_York")


class ChoicesCase(AppTestCase):
    def setUp(self):
        super().setUp()
        self.signup(industries=(30, 23))
        self.post("/app/settings/invite")
        token = re.search(r"invite=([\w-]+)", self.client.get("/app/settings").data.decode()).group(1)
        self.member = self.app.test_client()
        self.signup(email="member@example.com", client=self.member, invite=token, name="Sam Member")
        with self.db() as conn:
            self.org_id = conn.execute("SELECT id FROM orgs").fetchone()[0]

    def choose(self, client, **choices):
        """Ticks the boxes named (digest, alerts, weekly) on the real Settings
        form, unticks the others, and saves it as a browser would."""
        page = client.get("/app/settings").get_data(as_text=True)
        [form] = [f for f in post_forms(page) if f.action == "/app/settings/reminders"]
        data = {k: v for k, v in form.values().items() if not k.startswith("email_")}
        names = {"digest": "email_reminders", "alerts": "email_alerts", "weekly": "email_weekly"}
        for key, on in choices.items():
            if on:
                self.assertIsNotNone(form.field(names[key]), key)
                data[names[key]] = "on"
        return client.post(form.action, data=data, follow_redirects=True)

    def user(self, email):
        with self.db() as conn:
            return dict(conn.execute("SELECT email_reminders, email_alerts, email_weekly FROM users WHERE email = ?",
                                     (email,)).fetchone())

    def sent_to(self):
        """(recipient, first line of the body) for each reminder email so far."""
        with self.db() as conn:
            return [(r["recipient"], r["body"].splitlines()[0]) for r in conn.execute(
                "SELECT recipient, body FROM notifications WHERE kind = 'reminder' ORDER BY id")]

    def start_clock(self, industry_id, key, started):
        with self.db() as conn:
            conn.execute("INSERT OR REPLACE INTO items (org_id, industry_id, rule_key, value_date) VALUES (?, ?, ?, ?)",
                         (self.org_id, industry_id, key, started))
            conn.commit()

    def alerts_at(self, wall):
        with self.db() as conn:
            return run_clock_alerts(conn, dict(self.app.config), now=datetime.fromisoformat(wall).replace(tzinfo=NY))

    def digest_on(self, day):
        with self.db() as conn:
            return run_reminders(conn, dict(self.app.config), today_for=lambda org: day)


class TestTheSettingsPage(ChoicesCase):
    def test_everyone_on_the_team_chooses_their_own(self):
        for client, email in ((self.client, "owner@example.com"), (self.member, "member@example.com")):
            page = client.get("/app/settings").get_data(as_text=True)
            self.assertIn('id="reminders"', page)
            self.assertIn("Daily digest", page)
            self.assertIn("Time-limit alerts", page)
            self.assertNotIn("Weekly Autopilot report", page)   # neither is the operator
            self.assertEqual(self.user(email), {"email_reminders": 1, "email_alerts": 1, "email_weekly": 1})
        response = self.choose(self.member, alerts=True)
        self.assertEqual(flashes(response.get_data(as_text=True)),
                         ["Saved: Daily digest off, time-limit alerts on."])
        self.assertEqual(self.user("member@example.com")["email_reminders"], 0)
        self.assertEqual(self.user("member@example.com")["email_alerts"], 1)
        self.assertEqual(self.user("owner@example.com")["email_reminders"], 1, "only their own")
        page = self.member.get("/app/settings").get_data(as_text=True)
        self.assertRegex(page, r'name="email_reminders"\s*>')
        self.assertRegex(page, r'name="email_alerts"\s+checked')

    def test_only_the_operator_sees_and_sets_the_weekly_report(self):
        self.app.config["OPERATOR_EMAIL"] = "Owner@Example.com"
        page = self.client.get("/app/settings").get_data(as_text=True)
        self.assertIn("Weekly Autopilot report", page)
        self.assertNotIn("Weekly Autopilot report", self.member.get("/app/settings").get_data(as_text=True))
        response = self.choose(self.client, digest=True, alerts=True)
        self.assertEqual(flashes(response.get_data(as_text=True)),
                         ["Saved: Daily digest on, time-limit alerts on, weekly Autopilot report off."])
        self.assertEqual(self.user("owner@example.com")["email_weekly"], 0)
        # Anyone else's form leaves it alone, even with the field sent by hand.
        self.post("/app/settings/reminders", {"email_weekly": "on"}, client=self.member)
        self.post("/app/settings/reminders", {}, client=self.member)
        self.assertEqual(self.user("member@example.com")["email_weekly"], 1)

    def test_the_form_needs_its_token(self):
        response = self.member.post("/app/settings/reminders", data={"email_alerts": "on"})
        self.assertEqual(response.status_code, 400)


class TestTheSendersRespectThem(ChoicesCase):
    def test_the_digest_goes_only_to_those_who_chose_it(self):
        self.choose(self.member, alerts=True)                          # alerts only
        with self.db() as conn:                                         # 31 days, so due in 5
            conn.execute("INSERT INTO items (org_id, industry_id, rule_key, value_date) VALUES (?, 23, ?, ?)",
                         (self.org_id, "fire_extinguisher_inspection", "2026-10-09"))
            conn.commit()
        summary = self.digest_on(date(2026, 11, 4))
        self.assertEqual(summary["digests"], 1)
        self.assertEqual([to for to, _ in self.sent_to()], ["owner@example.com"])

    def test_the_alerts_go_only_to_those_who_chose_them(self):
        self.choose(self.client, digest=True)                           # digest only
        self.start_clock(30, "fatality_report_8h", "2026-11-04T14:00:00+00:00")
        self.assertEqual(self.alerts_at("2026-11-04T15:00")["alerts"], 1)
        self.assertEqual(self.sent_to(), [("member@example.com",
                                           "Time limit warning for Acme Logistics, 2026-11-04 15:00 EST.")])

    def test_no_one_left_for_either(self):
        self.choose(self.client)
        self.choose(self.member)
        self.start_clock(30, "fatality_report_8h", "2026-11-04T08:00:00+00:00")
        self.assertEqual(self.alerts_at("2026-11-04T11:01")["emails"], 0)
        self.assertEqual(self.digest_on(date(2026, 11, 4))["digests"], 0)
        self.assertEqual(self.sent_to(), [])

    def test_a_clock_already_alerted_still_reaches_those_without_alerts(self):
        """The digest leaves out a clock alerted about the same day, but only
        for the people who got that alert."""
        self.choose(self.member, digest=True)                           # digest only
        self.start_clock(30, "fatality_report_8h", "2026-11-04T08:00:00+00:00")   # due 11:00
        self.alerts_at("2026-11-04T11:01")
        self.assertEqual([to for to, _ in self.sent_to()], ["owner@example.com"])
        summary = self.digest_on(date(2026, 11, 4))
        self.assertEqual((summary["digests"], summary["reminders"]), (1, 1))
        to, first = self.sent_to()[-1]
        self.assertEqual(to, "member@example.com")
        self.assertTrue(first.startswith("Compliance reminders for Acme Logistics"))
        # Counted as reminded: neither gets it again tomorrow.
        self.assertEqual(self.digest_on(date(2026, 11, 5))["digests"], 0)

    def test_the_operator_can_turn_off_the_weekly_report(self):
        self.app.config["OPERATOR_EMAIL"] = "owner@example.com"
        cfg = dict(self.app.config, SMTP_HOST="smtp.example.com")
        with self.db() as conn:
            autopilot.record(conn, "fix", "fixed", "Re-sent 1 email that failed the first time.")
        sent = []
        with mock.patch.object(autopilot, "send_email", lambda cfg, to, subject, body, **kw:
                               sent.append((to, subject)) or ("sent", None)):
            with self.db() as conn:
                self.assertTrue(autopilot.weekly_summary(conn, cfg))
            self.choose(self.client, digest=True, alerts=True)            # weekly unticked
            with self.db() as conn, self.assertLogs("omniarmor.autopilot", "INFO"):
                self.assertFalse(autopilot.weekly_summary(conn, cfg))
            # Problems still reach the operator: only the weekly note is optional.
            with self.db() as conn:
                autopilot.report(conn, cfg, [autopilot.Finding("disk", "Disk almost full", "1 GB left", "Free space")])
        self.assertEqual(sent, [("owner@example.com", "[OmniArmor] Weekly Autopilot report"),
                                ("owner@example.com", "[OmniArmor] Disk almost full")])

    def test_an_operator_without_an_account_still_gets_it(self):
        cfg = dict(self.app.config, OPERATOR_EMAIL="ops@example.com")
        with self.db() as conn:
            self.assertTrue(autopilot.operator_wants_weekly(conn, cfg))
            self.assertTrue(autopilot.operator_wants_weekly(conn, dict(cfg, OPERATOR_EMAIL="")))


class TestTheUpgrade(unittest.TestCase):
    def test_a_person_who_had_reminders_off_keeps_both_off(self):
        import tempfile
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = os.path.join(tmp.name, "old.db")
        conn = sqlite3.connect(path)
        conn.execute("CREATE TABLE schema_version (version INTEGER NOT NULL)")
        for version, sql in MIGRATIONS[:12]:
            conn.executescript(sql)
            conn.execute("INSERT INTO schema_version VALUES (?)", (version,))
        conn.execute("INSERT INTO users (email, name, password_hash, email_reminders, created_at)"
                     " VALUES ('on@example.com', 'On', 'x', 1, '2026-01-01'), ('off@example.com', 'Off', 'x', 0, '2026-01-01')")
        conn.commit()
        conn.close()
        conn = connect(path)
        self.assertEqual(migrate(conn), SCHEMA_VERSION)
        rows = {r["email"]: (r["email_reminders"], r["email_alerts"], r["email_weekly"])
                for r in conn.execute("SELECT * FROM users")}
        conn.close()
        self.assertEqual(rows, {"on@example.com": (1, 1, 1), "off@example.com": (0, 0, 1)})


if __name__ == "__main__":
    unittest.main()
