"""Every email OmniArmor sends, captured as it leaves for the mail server:
one look (a 600-pixel column in the site's colors), a plain-text part beside
every HTML part with the same words, the MTRX Horizyn line at the foot, a
link to choose your reminder emails on every reminder, and no placeholder
left unfilled."""

import html
import os
import re
import smtplib
import sys
import unittest
from datetime import date, datetime, timedelta
from html.parser import HTMLParser
from unittest import mock
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_webapp import AppTestCase  # noqa: E402

from omniarmor_app import autopilot, notify  # noqa: E402
from omniarmor_app.autopilot import Finding  # noqa: E402
from omniarmor_app.db import iso, utcnow  # noqa: E402
from omniarmor_app.reminders import run_clock_alerts, run_reminders  # noqa: E402

BASE = "https://omniarmor.test"
MANAGE = BASE + "/app/settings#reminders"
VOID = {"meta", "br", "img", "hr", "input", "link"}


class FakeSMTP:
    sent = []

    def __init__(self, *a, **k):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def starttls(self, **k):
        pass

    def login(self, *a):
        pass

    def send_message(self, msg):
        FakeSMTP.sent.append(msg)


class Page(HTMLParser):
    """An email's HTML: its words, its links, its widths, and whether every
    tag that was opened was closed."""

    def __init__(self, text):
        super().__init__(convert_charrefs=True)
        self.words, self.links, self.stack, self.widths, self.problems = [], [], [], [], []
        self.feed(text)
        self.close()
        if self.stack:
            self.problems.append(f"never closed: {self.stack}")
        self.text = " ".join(" ".join(self.words).split())

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag not in VOID:
            self.stack.append(tag)
        if tag == "a":
            self.links.append(a.get("href", ""))
        if "width" in a:
            self.widths.append(a["width"])
        for value in re.findall(r"(?<![-\w])(?:max-)?width:\s*([\d.]+)px", a.get("style", "")):
            self.widths.append(value)

    def handle_endtag(self, tag):
        if tag in VOID:
            return
        if not self.stack or self.stack[-1] != tag:
            self.problems.append(f"</{tag}> closes {self.stack[-1:] or 'nothing'}")
            return
        self.stack.pop()

    def handle_data(self, data):
        if self.stack and self.stack[-1] in ("title", "style"):
            return
        self.words.append(data)


def parts(msg):
    """(plain text, HTML) of a sent message, which must hold exactly those two."""
    assert msg.get_content_type() == "multipart/alternative", msg.get_content_type()
    kinds = [p.get_content_type() for p in msg.iter_parts()]
    assert kinds == ["text/plain", "text/html"], kinds
    return msg.get_body(("plain",)).get_content(), msg.get_body(("html",)).get_content()


class TestEveryEmail(AppTestCase):
    def setUp(self):
        super().setUp()
        FakeSMTP.sent = []
        patcher = mock.patch.object(smtplib, "SMTP", FakeSMTP)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.app.config.update(SMTP_HOST="smtp.example.com", OPERATOR_EMAIL="ops@example.com",
                               MAIL_FROM="OmniArmor <no-reply@omniarmor.example.com>")
        self.cfg = dict(self.app.config)

    def send_every_email(self):
        """Makes the app send one of each email it can send. Returns {name: message}."""
        got = {}

        def take(name):
            self.assertTrue(FakeSMTP.sent, name)
            got[name] = FakeSMTP.sent[-1]
            FakeSMTP.sent.clear()

        # Accounts: a password reset link.
        self.signup(industries=(30, 23))
        self.post("/forgot", {"email": "owner@example.com"}, client=self.app.test_client())
        take("password reset")
        # Reminders: a daily digest, and a time-limit warning and overdue alert.
        with self.db() as conn:
            org = conn.execute("SELECT id FROM orgs").fetchone()[0]
            conn.execute("INSERT INTO items (org_id, industry_id, rule_key, value_date) VALUES (?, 23, ?, ?)",
                         (org, "fire_extinguisher_inspection", "2026-10-09"))
            conn.commit()
            run_reminders(conn, self.cfg, today_for=lambda o: date(2026, 11, 4))
            take("daily digest")
            conn.execute("INSERT INTO items (org_id, industry_id, rule_key, value_date) VALUES (?, 30, ?, ?)",
                         (org, "fatality_report_8h", "2026-11-04T14:00:00+00:00"))
            conn.commit()
            ny = ZoneInfo("America/New_York")
            run_clock_alerts(conn, self.cfg, now=datetime(2026, 11, 4, 15, 0, tzinfo=ny))
            take("time-limit warning")
            run_clock_alerts(conn, self.cfg, now=datetime(2026, 11, 4, 17, 1, tzinfo=ny))
            take("time-limit overdue")
            # A reminder that failed and Autopilot sends again.
            conn.execute("UPDATE notifications SET status = 'failed', created_at = ? WHERE id = (SELECT MAX(id)"
                         " FROM notifications)", (iso(utcnow() - timedelta(hours=1)),))
            conn.commit()
            self.assertEqual(autopilot.retry_failed_emails(conn, self.cfg), 1)
            take("reminder sent again")
            # Autopilot, to the operator: a problem, a reminder about it, its fix, the weekly report.
            problem = Finding("disk", "Disk almost full", "Only 0.4 GB of 20 GB is free.", "Free up space.")
            autopilot.report(conn, self.cfg, [problem])
            take("Autopilot problem")
            conn.execute("UPDATE autopilot_events SET at = ?", (iso(utcnow() - timedelta(days=2)),))
            conn.commit()
            autopilot.report(conn, self.cfg, [problem])
            take("Autopilot still open")
            conn.execute("UPDATE autopilot_events SET at = ?", (iso(utcnow() - timedelta(hours=2)),))
            conn.commit()
            autopilot.report(conn, self.cfg, [])
            take("Autopilot fixed")
            autopilot.record(conn, "fix", "fixed", "Re-sent 1 email that failed the first time.")
            autopilot.weekly_summary(conn, self.cfg)
            take("weekly Autopilot report")
        return got

    def test_every_email_at_600_pixels_with_a_text_part_and_the_footer(self):
        emails = self.send_every_email()
        self.assertEqual(len(emails), 9)
        for name, msg in emails.items():
            with self.subTest(name):
                self.check(name, msg)

    def check(self, name, msg):
        text, page = parts(msg)
        reminder = name.startswith(("daily", "time-limit", "reminder"))
        # No placeholder left unfilled, in either part or the subject.
        for part in (text, page, msg["Subject"]):
            for leftover in ("{{", "}}", "{%", "%}", "{base", "None", "Undefined", "{0}", "{1}", "%s", "\x00"):
                self.assertNotIn(leftover, part, name)
        self.assertNotRegex(text, r"[{}]", name)
        # The plain-text part: the body, then the footer, the company line last and once.
        self.assertEqual(text.count(notify.SIGNATURE), 1, name)
        self.assertTrue(text.rstrip().endswith("\n" + notify.SIGNATURE), name)
        self.assertEqual(text.count("\n--\n"), 1, name)
        # Reminders say where to choose them; so does the weekly report, which can be turned off.
        self.assertEqual(MANAGE in text, reminder or name == "weekly Autopilot report", name)
        self.assertEqual(msg["List-Unsubscribe"] == f"<{MANAGE}>", reminder, name)
        # The HTML part: one column at most 600 pixels wide, whole, in the site's colors.
        doc = Page(page)
        self.assertEqual(doc.problems, [], name)
        self.assertIn('width="600"', page)
        self.assertIn("max-width:600px", page)
        for width in doc.widths:
            self.assertTrue(width == "100%" or float(width) <= 600, (name, width))
        self.assertIn("#0F0E0D", page)                  # the site's black
        self.assertIn(notify.SIGNATURE, doc.text, name)
        self.assertIn(f"<title>{html.escape(msg['Subject'], quote=False)}</title>", page)
        # The same words in both parts, and every address in the text is a link in the HTML.
        for url in re.findall(r"https?://\S+", text):
            self.assertIn(url.rstrip(".,"), doc.links, (name, url))
        for link in doc.links:
            self.assertTrue(link.startswith(BASE + "/") or link == BASE, (name, link))
        for line in text.split("\n--\n")[0].splitlines():
            words = re.sub(r"https?://\S+", "", line).strip().lstrip("- ").rstrip(":").strip()
            if words:
                self.assertIn(" ".join(words.split()), doc.text, (name, line))

    def test_what_each_email_says(self):
        emails = {name: parts(msg)[0] for name, msg in self.send_every_email().items()}
        self.assertRegex(emails["password reset"], r"Set a new password: https://omniarmor\.test/reset/\S+\n")
        self.assertIn("The link works for 1 hour, once.", emails["password reset"])
        self.assertIn("Open your checks: https://omniarmor.test/app\n", emails["daily digest"])
        self.assertIn("because the daily digest is on", emails["daily digest"])
        self.assertIn("because time-limit alerts are on", emails["time-limit warning"])
        self.assertIn("Choose which reminder emails you get: " + MANAGE, emails["reminder sent again"])
        self.assertIn("Sent by OmniArmor Autopilot at https://omniarmor.test.", emails["Autopilot problem"])
        self.assertIn("What to do: Free up space.", emails["Autopilot problem"])
        self.assertIn("Turn this weekly report off", emails["weekly Autopilot report"])
        self.assertNotIn("Turn this weekly report off", emails["Autopilot fixed"])

    def test_a_digest_draws_its_headings_lists_and_button(self):
        text, page = notify.render_email(self.cfg, "OmniArmor: 1 overdue for Acme", "\n".join([
            "Compliance reminders for Acme <Sons> & Co, 2026-11-04.", "",
            "OVERDUE", "- FleetArmor: Annual review, 3 days overdue (2026-11-01). Do it now.", "",
            "COMING DUE", "- One", "- Two", "", "Right now: 1 blocked.", "Open your checks: https://omniarmor.test/app",
        ]), kind="reminder")
        self.assertIn("Acme &lt;Sons&gt; &amp; Co", page)           # a company's name is never markup
        self.assertNotIn("<Sons>", page)
        self.assertEqual(len(re.findall(r"<ul ", page)), 2)
        self.assertEqual(len(re.findall(r"<li ", page)), 3)
        self.assertRegex(page, r">OVERDUE</p>")
        self.assertRegex(page, r'<a href="https://omniarmor.test/app" style="[^"]+">Open your checks</a>')
        self.assertRegex(page, rf'<a href="{re.escape(MANAGE)}" style="[^"]+">Choose which reminder emails you get</a>')
        self.assertIn("Acme <Sons> & Co", text)

    def test_an_email_still_goes_when_its_html_cannot_be_drawn(self):
        with mock.patch.object(notify, "render_email", side_effect=RuntimeError("template broke")), \
                self.assertLogs("omniarmor.notify", "ERROR"):
            self.assertEqual(notify.send_email(self.cfg, "pat@example.com", "Hi", "Body.", kind="reminder"),
                             ("sent", None))
        msg = FakeSMTP.sent[-1]
        self.assertEqual(msg.get_content_type(), "text/plain")
        self.assertTrue(msg.get_content().rstrip().endswith(notify.SIGNATURE))


if __name__ == "__main__":
    unittest.main()
