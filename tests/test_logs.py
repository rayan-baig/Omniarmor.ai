"""No secret reaches a log line.

The main flows run against the real servers, exactly as they are started:
gunicorn with the Dockerfile's flags (production), and the development
server from the README. Then the daily job, the time-limit alerts and an
Autopilot pass that has to fall back to the log run in this process, and a
page crashes. Everything the server printed is searched for every secret
the flows used: passwords, reset and invite tokens, a kid's join code,
cookies and form tokens, the secret keys, a Stripe Checkout id, and every
full email address.
"""

import http.cookiejar
import io
import logging
import os
import re
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.error
import urllib.parse
import urllib.request
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from e2e_helpers import post_forms  # noqa: E402
from test_webapp import first_rule  # noqa: E402

from omniarmor_app import create_app  # noqa: E402
from omniarmor_app.redact import redact_line  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OWNER = "pat.owner@example.com"
MEMBER = "sam.member@example.org"
OPERATOR = "ops.person@example.net"
CUSTOMER = "lee.customer@example.com"
PASSWORDS = ["first secret password 1", "second secret password 2", "member secret password 3"]
SECRET_KEY = "log-test-secret-key-" + "k" * 40
STATS_KEY = "log-test-stats-key-" + "s" * 30
CHECKOUT = "cs_test_LogTestCheckoutId123"


def _free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


class Browser:
    """A browser over real HTTP: its own cookies; follows redirects itself."""

    def __init__(self, base, seen):
        self.base = base
        self.seen = seen  # every cookie value and form token, to look for in the log
        self.jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar), _NoRedirect)
        self.url = base + "/"
        self._token = ""

    def open(self, path, data=None, headers=None):
        url = urllib.parse.urljoin(self.url, path)
        for _ in range(10):
            body = urllib.parse.urlencode(data, doseq=True).encode() if data is not None else None
            request = urllib.request.Request(url, data=body, headers=headers or {})
            try:
                response = self.opener.open(request, timeout=20)
                status, text, location = response.status, response.read().decode("utf-8", "replace"), None
            except urllib.error.HTTPError as err:
                status, text, location = err.code, err.read().decode("utf-8", "replace"), err.headers.get("Location")
            for cookie in self.jar:
                self.seen.add(cookie.value)
            for token in re.findall(r'name="csrf_token" value="([^"]+)"', text):
                self.seen.add(token)
                self._token = token
            self.url = url
            if status in (301, 302, 303) and location:
                url, data = urllib.parse.urljoin(url, location), None
                continue
            return status, text
        raise AssertionError("too many redirects")

    def post(self, path, **fields):
        """A form post with the form token from the last page."""
        return self.open(path, {"csrf_token": self.token, **fields})

    @property
    def token(self):
        return self._token

    def submit(self, page, where, **fields):
        """Fills the first POST form whose action contains `where` ("" for the first form)."""
        found = [f for f in post_forms(page) if where in (f.action or self.url)]
        assert found, (where, [f.action for f in post_forms(page)])
        data = found[0].values()
        data.update(fields)
        return self.open(found[0].action or self.url, data)


class Server:
    def __init__(self, command, env, log_path):
        self.port = _free_port()
        self.base = f"http://127.0.0.1:{self.port}"
        self.log_path = log_path
        self.log = open(log_path, "w")
        command = [c.replace("{port}", str(self.port)) for c in command]
        self.proc = subprocess.Popen(command, cwd=ROOT, env={**env, "BASE_URL": self.base},
                                     stdout=self.log, stderr=subprocess.STDOUT)
        deadline = time.monotonic() + 30
        while True:
            try:
                urllib.request.urlopen(self.base + "/healthz", timeout=2).read()
                return
            except (OSError, urllib.error.URLError):
                if self.proc.poll() is not None or time.monotonic() > deadline:
                    self.stop()
                    raise AssertionError("the server did not start:\n" + self.text())
                time.sleep(0.1)

    def stop(self):
        if self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=15)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait()
        self.log.close()

    def text(self):
        with open(self.log_path, encoding="utf-8", errors="replace") as f:
            return f.read()


def _base_env(tmp):
    env = {k: v for k, v in os.environ.items()
           if not k.startswith(("SMTP_", "STRIPE_", "OMNIARMOR_", "SESSION_COOKIE_", "DATABASE_", "BACKUP_"))}
    env.update(SECRET_KEY=SECRET_KEY, STATS_KEY=STATS_KEY, DATABASE_PATH=os.path.join(tmp, "omniarmor.db"),
               BACKUP_DIR=os.path.join(tmp, "backups"), SCHEDULER_ENABLED="0", OPERATOR_EMAIL=OPERATOR,
               PYTHONUNBUFFERED="1")
    return env


def run_main_flows(base, db_path):
    """Sign up, invite and add a member, a reading, a wrong and a right
    password, a password reset, a kid's join code, the stats address, the
    return from Stripe signed out, a missing page, and signing out. Returns
    every secret used on the way."""
    seen = set()
    owner = Browser(base, seen)
    status, page = owner.open("/signup")
    assert status == 200, page
    status, page = owner.submit(page, "/signup", name="Pat Owner", email=OWNER, password=PASSWORDS[0],
                                org_name="Acme Logistics", timezone="America/New_York", industries=["1", "18"])
    assert status == 200 and "/app" in owner.url, (status, owner.url)

    rule = first_rule(1, kind="max", mode=None)
    status, page = owner.open("/app/industry/1")
    status, _ = owner.submit(page, f"/rule/{rule.key}", value=str(rule.limit + 1), action="save")
    assert status == 200

    status, page = owner.open("/app/settings")
    status, page = owner.submit(page, "/settings/invite")
    invite = re.search(r"invite=([A-Za-z0-9_\-]+)", page).group(1)
    member = Browser(base, seen)
    status, page = member.open(f"/signup?invite={invite}")
    assert status == 200, page
    status, page = member.submit(page, "/signup", name="Sam Member", email=MEMBER, password=PASSWORDS[2])
    assert status == 200 and "/app" in member.url, (status, member.url)

    # A kid's own device, with a join code.
    status, page = owner.open("/app/academy")
    status, page = owner.submit(page, "/learners", nickname="Rocket", avatar="rocket")
    with sqlite3.connect(db_path) as conn:
        learner = conn.execute("SELECT id FROM learners").fetchone()[0]
    owner.post(f"/app/academy/{learner}/join-code")
    with sqlite3.connect(db_path) as conn:
        code = conn.execute("SELECT code FROM join_codes").fetchone()[0]
    kid = Browser(base, seen)
    status, page = kid.open("/kids")
    status, page = kid.submit(page, "", code=code)
    assert status == 200 and f"/app/academy/{learner}" in kid.url, (status, kid.url)

    # Signed out: a wrong password, then a reset.
    owner.submit(owner.open("/app")[1], "/logout")
    stranger = Browser(base, seen)
    status, page = stranger.open("/login")
    status, _ = stranger.submit(page, "", email=OWNER, password="not the password at all")
    assert status == 401
    status, page = stranger.open("/forgot")
    stranger.submit(page, "", email=OWNER)
    with sqlite3.connect(db_path) as conn:
        body = conn.execute("SELECT body FROM notifications WHERE kind = 'password_reset'").fetchone()[0]
    reset = re.search(r"/reset/([A-Za-z0-9_\-]+)", body).group(1)
    status, page = stranger.open(f"/reset/{reset}")
    assert status == 200, page
    status, page = stranger.submit(page, "", password=PASSWORDS[1])
    assert status == 200 and "/app" in stranger.url, (status, stranger.url)
    status, page = owner.submit(owner.open("/login")[1], "", email=OWNER, password=PASSWORDS[1])
    assert status == 200 and "/app" in owner.url, (status, owner.url)

    # The stats address, Stripe's return when signed out, a page that isn't there.
    request = urllib.request.Request(base + "/api/stats", headers={"Authorization": f"Bearer {STATS_KEY}"})
    assert urllib.request.urlopen(request, timeout=10).status == 200
    Browser(base, seen).open(f"/app/academy/plan?welcome=1&session_id={CHECKOUT}",
                             headers={"Referer": f"https://checkout.stripe.com/c/pay/{CHECKOUT}"})
    Browser(base, seen).open("/no-such-page?email=" + OWNER.replace("@", "%40"))
    owner.submit(owner.open("/app")[1], "/logout")
    return seen | {invite, code, reset}


EMAILS = [OWNER, MEMBER, OPERATOR, CUSTOMER]
SECRETS = [*EMAILS, *(e.replace("@", "%40") for e in EMAILS), SECRET_KEY, STATS_KEY, CHECKOUT, *PASSWORDS]


class LogCase(unittest.TestCase):
    def assertNoSecrets(self, log, secrets):
        self.assertGreater(len(secrets), 8)
        for secret in secrets:
            self.assertTrue(secret)
            self.assertNotIn(secret, log, f"{secret!r} is in the log")


class TestTheServersLogNoSecrets(LogCase):
    def flow_against(self, command, extra_env):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        env = {**_base_env(tmp.name), **extra_env}
        server = Server(command, env, os.path.join(tmp.name, "server.log"))
        try:
            used = run_main_flows(server.base, env["DATABASE_PATH"])
        finally:
            server.stop()
        log = server.text()
        self.assertIn("GET /app/settings", log)  # the access log was on
        self.assertIn("/reset/[hidden]", log)
        # The address in the missing page's link, shortened (gunicorn logs it
        # as sent, the development server decoded).
        self.assertRegex(log, r"email=p\*\*\*(@|%40)example\.com")
        self.assertNoSecrets(log, SECRETS + sorted(used))
        return log

    def test_gunicorn_as_the_dockerfile_runs_it(self):
        with open(os.path.join(ROOT, "Dockerfile")) as f:
            cmd = re.search(r'CMD \["sh", "-c", "exec (gunicorn .*?)"\]', f.read()).group(1)
        cmd = (cmd.replace("${WEB_CONCURRENCY}", "1").replace("${WEB_THREADS}", "4")
               .replace("0.0.0.0:${PORT}", "127.0.0.1:{port}"))
        self.assertIn("--logger-class omniarmor_app.access_log.RedactingLogger", cmd)
        # Production, as in the image; cookies allowed over plain http for this test only.
        log = self.flow_against([sys.executable, "-m", *cmd.split()],
                                {"OMNIARMOR_ENV": "production", "SESSION_COOKIE_SECURE": "0", "TRUSTED_PROXIES": "0"})
        self.assertIn('"GET /app/academy/plan?welcome=1&session_id=[hidden] HTTP/1.1"', log)

    def test_the_development_server_from_the_readme(self):
        # README: flask --app wsgi run --port 8000
        self.flow_against([sys.executable, "-m", "flask", "--app", "wsgi", "run", "--port", "{port}"], {})


class TestJobsAndCrashesLogNoSecrets(LogCase):
    """What OmniArmor itself writes: the daily job, the time-limit alerts,
    Autopilot falling back to the log, and a page that crashes."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.app = create_app(DATABASE=os.path.join(self.tmp.name, "t.db"), SCHEDULER_ENABLED=False,
                              BACKUP_DIR=os.path.join(self.tmp.name, "b"), SECRET_KEY=SECRET_KEY,
                              OPERATOR_EMAIL=OPERATOR, STATS_KEY=STATS_KEY, BASE_URL="https://omniarmor.test",
                              # Email "set up" on a port nobody answers: every email fails.
                              SMTP_HOST="127.0.0.1", SMTP_PORT=_free_port(), SMTP_PASSWORD="smtp-secret-pw-77")
        # What the server log's own handlers print, filters and all.
        self.buf = io.StringIO()
        for handler in logging.getLogger().handlers:
            old = handler.setStream(self.buf) if isinstance(handler, logging.StreamHandler) else None
            if old is not None:
                self.addCleanup(handler.setStream, old)

    def test_daily_job_alerts_autopilot_and_a_crash(self):
        from omniarmor_app import autopilot, jobs
        cfg = dict(self.app.config)
        client = self.app.test_client()
        client.get("/signup")
        with client.session_transaction() as s:
            csrf = s["_csrf"]
        client.post("/signup", data={"csrf_token": csrf, "name": "Pat Owner", "email": OWNER,
                                     "password": PASSWORDS[0], "org_name": "Acme", "timezone": "UTC",
                                     "industries": ["1"]})
        with sqlite3.connect(cfg["DATABASE"]) as conn:
            # An email that failed after every retry, its error quoting the address.
            now = time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime())
            conn.executemany(
                "INSERT INTO notifications (org_id, user_id, created_at, kind, recipient, subject, body, status,"
                " error, attempts) VALUES (1, 1, ?, 'reminder', ?, 'Due', 'x', 'failed', ?, 9)",
                [(now, CUSTOMER, f"SMTPRecipientsRefused: {{'{CUSTOMER}': (550, b'no such user')}}")] * 3)
        jobs.run_daily(cfg, force=True)
        jobs.run_alerts(cfg)
        autopilot.run(cfg, force=True)

        # A page crashes on a reset link, with an address in what went wrong.
        crash_app = self.app
        crash_app.config["PROPAGATE_EXCEPTIONS"] = False
        with mock.patch("omniarmor_app.auth.hash_token",
                        side_effect=RuntimeError(f"no reset for {OWNER} with {CHECKOUT}")):
            self.assertEqual(crash_app.test_client().get("/reset/SECRETRESETTOKEN42").status_code, 500)
        autopilot.run(cfg, force=True)  # and Autopilot reports the new bug

        log = self.buf.getvalue()
        self.assertIn("AUTOPILOT", log)
        self.assertIn("Exception on /reset/[hidden]", log)
        self.assertIn("o***@example.net", log)  # the operator's address, shortened
        self.assertIn("l***@example.com", log)
        self.assertIn(" UTC ", log)
        self.assertNoSecrets(log, SECRETS + ["SECRETRESETTOKEN42", "smtp-secret-pw-77"])


class TestRedactLine(unittest.TestCase):
    def test_emails_and_checkout_ids(self):
        self.assertEqual(redact_line("to pat.owner@example.com, failed"), "to p***@example.com, failed")
        self.assertEqual(redact_line("GET /reset/abc HTTP/1.1"), "GET /reset/[hidden] HTTP/1.1")
        self.assertEqual(redact_line("No such checkout.session: cs_live_a1B2"), "No such checkout.session: cs_[hidden]")
        self.assertEqual(redact_line("version 1.2.3, 2026-11-02 10:00"), "version 1.2.3, 2026-11-02 10:00")


if __name__ == "__main__":
    unittest.main()
