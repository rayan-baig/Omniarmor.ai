"""Operator status: only `flask --app wsgi make-operator`, run on the server,
gives it, and only to the account with the OPERATOR_EMAIL address.

Sign-up doesn't prove an address is yours, so having the operator's address
is not enough: a stranger who registers it first (before the owner signs up
on a new deployment) sees no usage counts and has no say over the weekly
Autopilot report. And Autopilot's own "Bug:" emails are scrubbed like the
error reports (errormail.scrub)."""
import os
import sys
import tempfile
import unittest
from contextlib import closing
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from test_webapp import PASSWORD, AppTestCase  # noqa: E402

from omniarmor_app import autopilot, create_app  # noqa: E402
from omniarmor_app.db import MIGRATIONS, SCHEMA_VERSION, connect, migrate  # noqa: E402

OPERATOR = "ops@example.com"
OPERATOR_ONLY = ("Usage, last", "Weekly Autopilot report", 'name="email_weekly"')


class OperatorCase(AppTestCase):
    def setUp(self):
        super().setUp()
        self.app.config["OPERATOR_EMAIL"] = OPERATOR

    def settings(self, client=None):
        return (client or self.client).get("/app/settings").get_data(as_text=True)

    def flag(self, email):
        with closing(self.db()) as conn:
            return conn.execute("SELECT is_operator FROM users WHERE email = ?", (email,)).fetchone()[0]

    def weekly(self, email):
        with closing(self.db()) as conn:
            return conn.execute("SELECT email_weekly FROM users WHERE email = ?", (email,)).fetchone()[0]

    def wants_weekly(self):
        with closing(self.db()) as conn:
            return autopilot.operator_wants_weekly(conn, dict(self.app.config))

    def cli(self, *args):
        return self.app.test_cli_runner().invoke(args=["make-operator", *args])


class TestAStrangerWithTheOperatorsAddress(OperatorCase):
    """Someone signs up with OPERATOR_EMAIL before the owner does."""

    def setUp(self):
        super().setUp()
        self.signup(email=OPERATOR, name="Not The Owner")

    def test_sees_no_operator_data(self):
        self.client.get("/help")      # something to count
        page = self.settings()
        for text in OPERATOR_ONLY:
            self.assertNotIn(text, page)
        self.assertNotIn("Help page views", page)
        self.assertEqual(self.flag(OPERATOR), 0)

    def test_cannot_turn_off_the_weekly_report(self):
        # The form sent by hand without the box ticked, which used to turn it off.
        self.post("/app/settings/reminders", {"email_reminders": "on", "email_alerts": "on"})
        self.assertEqual(self.weekly(OPERATOR), 1)
        # Even a 0 already in the row (say, from before the upgrade) has no say.
        with closing(self.db()) as conn:
            conn.execute("UPDATE users SET email_weekly = 0 WHERE email = ?", (OPERATOR,))
            conn.commit()
        self.assertTrue(self.wants_weekly())
        cfg = dict(self.app.config, SMTP_HOST="smtp.example.com")
        sent = []
        with closing(self.db()) as conn:
            autopilot.record(conn, "fix", "fixed", "Re-sent 1 email that failed the first time.")
            with mock.patch.object(autopilot, "send_email",
                                   lambda cfg, to, subject, body, **kw: sent.append((to, subject)) or ("sent", None)):
                self.assertTrue(autopilot.weekly_summary(conn, cfg))
        self.assertEqual(sent, [(OPERATOR, "[OmniArmor] Weekly Autopilot report")])

    def test_case_and_spaces_in_the_address_change_nothing(self):
        other = self.app.test_client()
        self.signup(email="  OPS@Example.COM ", client=other)    # taken: the same account
        self.app.config["OPERATOR_EMAIL"] = "OPS@EXAMPLE.COM"
        for text in OPERATOR_ONLY:
            self.assertNotIn(text, self.settings())


class TestTheCommand(OperatorCase):
    def setUp(self):
        super().setUp()
        self.signup(email=OPERATOR, name="Pat Owner")
        self.member = self.app.test_client()

    def test_grants_it(self):
        result = self.cli(OPERATOR.upper())
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn(f"{OPERATOR} is now the operator.", result.output)
        # Enough to tell whether the account is really the owner's.
        self.assertIn("Account created 20", result.output)
        self.assertIn("'Pat Owner'", result.output)
        self.assertIn("workspace: Acme Logistics", result.output)
        self.assertIn("--revoke", result.output)
        self.assertEqual(self.flag(OPERATOR), 1)
        page = self.settings()
        for text in OPERATOR_ONLY:
            self.assertIn(text, page)
        # And now the weekly report's switch is theirs.
        self.post("/app/settings/reminders", {"email_reminders": "on", "email_alerts": "on"})
        self.assertEqual(self.weekly(OPERATOR), 0)
        self.assertFalse(self.wants_weekly())

    def test_revokes_it(self):
        self.make_operator(OPERATOR)
        result = self.cli(OPERATOR, "--revoke")
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn(f"{OPERATOR} is not the operator any more.", result.output)
        self.assertEqual(self.flag(OPERATOR), 0)
        page = self.settings()
        for text in OPERATOR_ONLY:
            self.assertNotIn(text, page)

    def test_refuses_an_address_that_is_not_operator_email(self):
        self.signup(email="someone@example.com", client=self.member)
        result = self.cli("someone@example.com")
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("not OPERATOR_EMAIL", result.output)
        self.assertIn("Nothing was changed", result.output)
        self.assertEqual(self.flag("someone@example.com"), 0)
        for text in OPERATOR_ONLY:
            self.assertNotIn(text, self.settings(self.member))

    def test_refuses_without_operator_email_or_without_an_account(self):
        self.app.config["OPERATOR_EMAIL"] = ""
        result = self.cli(OPERATOR)
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("OPERATOR_EMAIL is not set", result.output)
        self.app.config["OPERATOR_EMAIL"] = "nobody-yet@example.com"
        result = self.cli("nobody-yet@example.com")
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("No account has that address", result.output)
        self.assertEqual(self.flag(OPERATOR), 0)

    def test_one_operator_and_only_while_the_address_matches(self):
        self.make_operator(OPERATOR)
        # OPERATOR_EMAIL moves to another address: the old flag stops counting.
        self.app.config["OPERATOR_EMAIL"] = "new-ops@example.com"
        self.assertNotIn("Usage, last", self.settings())
        self.signup(email="new-ops@example.com", client=self.member)
        self.assertNotIn("Usage, last", self.settings(self.member))
        self.make_operator("new-ops@example.com")
        self.assertIn("Usage, last", self.settings(self.member))
        # Granting it took it from the old account, so moving back needs the command again.
        self.assertEqual(self.flag(OPERATOR), 0)
        self.app.config["OPERATOR_EMAIL"] = OPERATOR
        self.assertNotIn("Usage, last", self.settings())


class TestTheUpgrade(OperatorCase):
    """A filled version-15 database: the account with the operator's address
    had operator powers by its address alone. After the upgrade it has none
    until the owner runs make-operator once."""

    def setUp(self):
        with mock.patch("omniarmor_app.db.MIGRATIONS", [m for m in MIGRATIONS if m[0] <= 15]):
            super().setUp()
            self.signup(email=OPERATOR)
            self.signup(email="member@example.com", client=self.app.test_client())
            self.client.get("/help")
            with closing(self.db()) as conn:
                self.assertEqual(conn.execute("SELECT MAX(version) FROM schema_version").fetchone()[0], 15)
                conn.execute("UPDATE users SET email_weekly = 0 WHERE email = ?", (OPERATOR,))   # turned off in 1.1
                conn.commit()

    def test_the_operator_address_keeps_nothing_until_the_command(self):
        self.assertGreaterEqual(SCHEMA_VERSION, 16)
        # The new version starts on the same database file, as a deploy does.
        self.app = create_app(TESTING=True, DATABASE=self.db_path, SCHEDULER_ENABLED=False,
                              BACKUP_DIR=os.path.join(self.tmp.name, "backups"), BASE_URL="https://omniarmor.test",
                              OPERATOR_EMAIL=OPERATOR)
        with closing(self.db()) as conn:
            self.assertEqual(migrate(conn), SCHEMA_VERSION)
            users = {r["email"]: dict(r) for r in conn.execute("SELECT * FROM users")}
            self.assertEqual(conn.execute("SELECT SUM(count) FROM usage_counts WHERE event = 'help_views'")
                             .fetchone()[0], 1)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM orgs").fetchone()[0], 2)
        self.assertEqual(set(users), {OPERATOR, "member@example.com"})
        self.assertEqual({e: u["is_operator"] for e, u in users.items()}, {OPERATOR: 0, "member@example.com": 0})
        self.assertEqual(users[OPERATOR]["email_weekly"], 0, "the old choice is kept")
        self.client = self.app.test_client()
        response = self.post("/login", {"email": OPERATOR, "password": PASSWORD})
        self.assertEqual(response.status_code, 302)
        for text in OPERATOR_ONLY:
            self.assertNotIn(text, self.settings())
        self.assertTrue(self.wants_weekly(), "an unflagged account has no say over the weekly report")
        # The one step: the owner runs the command on the server.
        self.make_operator(OPERATOR)
        for text in OPERATOR_ONLY:
            self.assertIn(text, self.settings())
        self.assertFalse(self.wants_weekly(), "and then their old choice counts again")


class TestBugEmailsAreScrubbed(unittest.TestCase):
    """Autopilot's "Bug:" emails carried the error's message and traceback as
    they were. They now go through errormail.scrub, like the error reports."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.app = create_app(TESTING=True, DATABASE=os.path.join(self.tmp.name, "test.db"), SCHEDULER_ENABLED=False,
                              BACKUP_DIR=os.path.join(self.tmp.name, "backups"), BASE_URL="https://omniarmor.test",
                              SMTP_HOST="smtp.test", OPERATOR_EMAIL=OPERATOR)
        self.cfg = dict(self.app.config)
        self.sent = []
        patcher = mock.patch.object(autopilot, "send_email", lambda cfg, to, subject, body, **kw:
                                    self.sent.append((to, subject, body)) or ("sent", None))
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_no_email_address_token_or_link_in_the_bug_email(self):
        secrets = ("pat.person@example.org", "Zq81mXv0Lw3pT7cR9yKe", "https://omniarmor.test/reset/Ab12Cd34Ef56Gh78Ij90",
                   "s3cr3t-pass", "10.20.30.40", "Qw12Er34Ty56Ui78Op90")
        try:
            raise ValueError(f"no account for {secrets[0]}, token={secrets[1]}, link {secrets[2]},"
                             f" password: {secrets[3]} from {secrets[4]}, ref {secrets[5]}")
        except ValueError as exc:
            for _ in range(2):
                autopilot.record_error(self.cfg, "/app/settings?next=pat.person%40example.org", exc)
        result = autopilot.run(self.cfg, force=True)
        self.assertEqual([f.key[:4] for f in result["problems"]], ["bug:"])
        [(to, subject, body)] = [m for m in self.sent if "Bug:" in m[1]]
        self.assertEqual(to, OPERATOR)
        self.assertTrue(subject.startswith("[OmniArmor] Bug: ValueError: no account for [email]"), subject)
        for secret in secrets:
            self.assertNotIn(secret, subject)
            self.assertNotIn(secret, body)
        self.assertNotIn("pat.person", body)
        self.assertIn("[email]", body)
        self.assertIn("[token]", body)
        self.assertIn("[hidden]", body)
        self.assertIn("[ip]", body)
        # Still useful: where it happened, how often, and the traceback's shape.
        self.assertIn("Happened 2 times", body)
        self.assertIn("test_operator.py", body)
        self.assertIn("Traceback (end):", body)
        self.assertNotIn(os.path.dirname(os.path.abspath(__file__)), body, "paths are relative")
        # The record Autopilot keeps (autopilot --log) is the scrubbed one.
        with closing(connect(self.cfg["DATABASE"])) as conn:
            kept = " ".join(r["title"] + r["detail"] for r in conn.execute("SELECT * FROM autopilot_events"))
        for secret in secrets:
            self.assertNotIn(secret, kept)


if __name__ == "__main__":
    unittest.main()
