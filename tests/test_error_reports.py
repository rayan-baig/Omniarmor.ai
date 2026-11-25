"""Error reports to one inbox (ERRORS_EMAIL): a short email per server
error, with no personal data, rate limited in the database, delivered
through the outbox."""

import os
import sys
import unittest
from datetime import timedelta
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from omniarmor_app import autopilot, create_app, errormail  # noqa: E402
from omniarmor_app.db import iso, utcnow  # noqa: E402
from omniarmor_app.version import __version__  # noqa: E402
from test_webapp import AppTestCase  # noqa: E402

INBOX = "errors@omniarmor.test"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class ErrorCase(AppTestCase):
    def setUp(self):
        super().setUp()
        self.app.config["PROPAGATE_EXCEPTIONS"] = False   # answer as a running server does
        self.app.config["ERRORS_EMAIL"] = INBOX

    def fail(self, path="/_test/server-error", client=None, **kw):
        client = client or self.client
        with self.assertLogs("omniarmor_app", "ERROR"):
            response = client.get(path, **kw)
        self.assertEqual(response.status_code, 500)
        return response

    def reports(self):
        with self.db() as conn:
            return conn.execute("SELECT * FROM notifications WHERE kind = 'error_report' ORDER BY id").fetchall()


class TestTheReport(ErrorCase):
    def test_off_when_errors_email_is_unset(self):
        self.app.config["ERRORS_EMAIL"] = ""
        self.fail()
        self.assertEqual(self.reports(), [])
        with self.db() as conn:   # Autopilot's own record is kept as before
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM app_errors").fetchone()[0], 1)

    def test_what_it_says(self):
        self.fail("/_test/server-error?page=2")
        [row] = self.reports()
        body = row["body"]
        self.assertEqual(row["recipient"], INBOX)
        self.assertEqual(row["status"], "logged")       # no SMTP in tests: kept, like every email
        self.assertRegex(row["subject"], r"^\[OmniArmor\] Server error: RuntimeError \[[0-9a-f]{12}\]$")
        self.assertRegex(body, r"Time: \d{4}-\d\d-\d\d \d\d:\d\d:\d\d UTC")
        self.assertIn(f"Version: {__version__}", body)
        self.assertIn("Request: GET /_test/server-error\n", body)   # no query string
        self.assertNotIn("page=2", body)
        self.assertIn("Error: RuntimeError", body)
        self.assertIn("Stack trace, most recent call last:", body)
        self.assertIn("omniarmor_app/__init__.py:", body)        # relative to the project
        self.assertNotIn(ROOT, body)
        self.assertNotIn("/srv/", body)                          # the message's own path, too
        self.assertIn("flask/app.py:", body)                     # a library's, relative to site-packages
        self.assertNotIn("site-packages", body)
        # Autopilot's fault record is made as before, with the same fingerprint.
        with self.db() as conn:
            signature = conn.execute("SELECT signature FROM app_errors").fetchone()[0]
        self.assertIn(f"[{signature}]", row["subject"])

    def test_nothing_personal_from_query_form_or_cookie(self):
        self.signup(email="pat.owner@family.example", name="Pat Ownerly")
        query, form, cookie = "kid.query@leak-one.example", "grownup.form@leak-two.example", "cookie.person@leak-three.example"
        self.client.set_cookie("note", cookie)
        with self.assertLogs("omniarmor_app", "ERROR"):
            response = self.post("/_test/server-error-echo?q=" + query.replace("@", "%40") + "&token=abcdef0123456789xyz",
                                 {"email": form, "name": "Robin Secretname"})
        self.assertEqual(response.status_code, 500)
        [row] = self.reports()
        text = row["subject"] + "\n" + row["body"]
        self.assertIn("Error: ValueError", text)
        self.assertIn("Message: bad input: q=[email]&token=[hidden] form=[email] cookie=[hidden]", text)
        for email in (query, form, cookie, "pat.owner@family.example"):
            local, domain = email.split("@")
            for piece in (email, email.replace("@", "%40"), local, domain):
                self.assertNotIn(piece, text)
        for other in ("Pat Ownerly", "Robin Secretname", "abcdef0123456789xyz", "127.0.0.1", "csrf", "Cookie",
                      "User-Agent", "session"):
            self.assertNotIn(other, text)
        self.assertIn("Request: POST /_test/server-error-echo\n", text)

    def test_scrubbing(self):
        self.assertEqual(errormail.scrub("mail a.b+c@x.example or a%40x.example"), "mail [email] or [email]")
        self.assertEqual(errormail.scrub("password=hunter22 Bearer abc.def"), "password=[hidden] Bearer [hidden]")
        self.assertEqual(errormail.scrub("/reset/Zx9yQ2wE7rT5"), "/reset/[hidden]")
        self.assertEqual(errormail.scrub("id cs_live_a1B2c3D4e5F6g7H8"), "id [token]")
        self.assertEqual(errormail.scrub("from 203.0.113.9 or 2001:db8:0:1::1 at 12:30:45"),
                         "from [ip] or [ip] at 12:30:45")
        self.assertEqual(errormail.scrub(f"in {ROOT}/omniarmor_app/views.py"), "in omniarmor_app/views.py")
        self.assertEqual(errormail.relative("/usr/lib/python3/dist-packages/werkzeug/serving.py"),
                         "werkzeug/serving.py")
        self.assertEqual(errormail.relative(os.path.join(ROOT, "omniarmor_app", "views.py")),
                         os.path.join("omniarmor_app", "views.py"))

    def test_a_report_that_cannot_be_written_never_breaks_the_error_page(self):
        with mock.patch.object(errormail, "_claim", side_effect=RuntimeError("database gone")), \
                self.assertLogs("omniarmor", "ERROR"):
            response = self.client.get("/_test/server-error")
        self.assertEqual(response.status_code, 500)
        self.assertIn("Something went wrong on our side", response.get_data(as_text=True))


class TestRateLimits(ErrorCase):
    def test_one_email_per_distinct_error_an_hour(self):
        self.fail()
        self.fail()
        self.fail("/_test/server-error-echo")      # a different error
        self.assertEqual(len(self.reports()), 2)
        with self.db() as conn:   # every one is still on Autopilot's record
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM app_errors").fetchone()[0], 3)
        # An hour later, the same error is emailed again.
        with self.db() as conn:
            conn.execute("UPDATE notifications SET created_at = ?", (iso(utcnow() - timedelta(minutes=61)),))
            conn.commit()
        self.fail()
        self.assertEqual(len(self.reports()), 3)

    def test_at_most_twenty_a_day(self):
        with self.db() as conn:
            for i in range(errormail.MAX_PER_DAY):
                conn.execute("INSERT INTO notifications (created_at, kind, recipient, subject, body, status)"
                             " VALUES (?, 'error_report', ?, ?, '', 'sent')",
                             (iso(utcnow() - timedelta(hours=2)), INBOX, f"[OmniArmor] Server error: X [{i:012x}]"))
            conn.commit()
        with self.assertLogs("omniarmor.errormail", "WARNING"):
            self.fail()
        self.assertEqual(len(self.reports()), errormail.MAX_PER_DAY)
        with self.db() as conn:   # a day later there is room again
            conn.execute("UPDATE notifications SET created_at = ?", (iso(utcnow() - timedelta(hours=25)),))
            conn.commit()
        self.fail()
        self.assertEqual(len(self.reports()), errormail.MAX_PER_DAY + 1)

    def test_the_limits_survive_a_restart(self):
        self.fail()
        restarted = create_app(TESTING=True, DATABASE=self.db_path, SCHEDULER_ENABLED=False,
                               PROPAGATE_EXCEPTIONS=False, ERRORS_EMAIL=INBOX)
        self.fail(client=restarted.test_client())
        self.assertEqual(len(self.reports()), 1)


class TestDelivery(ErrorCase):
    def setUp(self):
        super().setUp()
        self.app.config.update(SMTP_HOST="smtp.omniarmor.test", OPERATOR_EMAIL="")
        self.started = []
        patcher = mock.patch.object(errormail, "_start", side_effect=lambda target, *args: self.started.append(
            (target, args)))
        patcher.start()
        self.addCleanup(patcher.stop)

    def run_started(self):
        for target, args in self.started:
            target(*args)
        self.started.clear()

    def test_sent_from_the_outbox(self):
        self.fail()
        [row] = self.reports()
        self.assertEqual((row["status"], row["attempts"]), ("failed", 0))   # queued, not lost
        with mock.patch.object(errormail, "send_email", return_value=("sent", None)) as sent:
            self.run_started()
        sent.assert_called_once()
        self.assertEqual(sent.call_args.args[1], INBOX)
        [row] = self.reports()
        self.assertEqual((row["status"], row["attempts"]), ("sent", 1))

    def test_mail_down_is_retried_by_autopilot(self):
        self.fail()
        with mock.patch.object(errormail, "send_email", return_value=("failed", "OSError: connection refused")):
            self.run_started()
        [row] = self.reports()
        self.assertEqual((row["status"], row["attempts"], row["error"]), ("failed", 1, "OSError: connection refused"))
        with self.db() as conn:
            conn.execute("UPDATE notifications SET created_at = ?", (iso(utcnow() - timedelta(minutes=11)),))
            conn.commit()
            with mock.patch.object(autopilot, "send_email", return_value=("sent", None)) as resent:
                self.assertEqual(autopilot.retry_failed_emails(conn, dict(self.app.config)), 1)
        self.assertEqual(resent.call_args.kwargs["kind"], "error_report")
        [row] = self.reports()
        self.assertEqual((row["status"], row["attempts"]), ("sent", 2))

    def test_a_server_that_stops_before_sending_leaves_it_for_autopilot(self):
        self.fail()
        self.started.clear()      # the process stopped: the thread never ran
        with self.db() as conn, mock.patch.object(autopilot, "send_email", return_value=("sent", None)) as resent:
            self.assertEqual(autopilot.retry_failed_emails(conn, dict(self.app.config)), 0)   # not before the grace
            conn.execute("UPDATE notifications SET created_at = ?", (iso(utcnow() - timedelta(minutes=3)),))
            conn.commit()
            self.assertEqual(autopilot.retry_failed_emails(conn, dict(self.app.config)), 1)
        resent.assert_called_once()
        # The first try, if it starts after all, finds it taken and sends nothing.
        with self.db() as conn:
            row_id = conn.execute("SELECT id FROM notifications").fetchone()[0]
        with mock.patch.object(errormail, "send_email") as late:
            self.assertIsNone(errormail.deliver(dict(self.app.config), row_id))
        late.assert_not_called()

    def test_the_footer_says_where_it_came_from(self):
        from omniarmor_app.notify import signed
        text = signed("Body", {"BASE_URL": "https://omniarmor.test"}, kind="error_report")
        self.assertIn("ERRORS_EMAIL", text)
        self.assertTrue(text.rstrip().endswith("OmniArmor is a product of MTRX Horizyn."))


class TestKeptLikeErrorReports(ErrorCase):
    def test_trimmed_with_autopilots_error_reports(self):
        self.fail()
        with self.db() as conn:
            conn.execute("UPDATE notifications SET created_at = ?", (iso(utcnow() - timedelta(days=31)),))
            conn.commit()
            autopilot.tidy(conn, dict(self.app.config))
        self.assertEqual(self.reports(), [])


if __name__ == "__main__":
    unittest.main()
