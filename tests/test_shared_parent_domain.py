"""OmniArmor on a subdomain of MTRX Horizyn's domain, beside its siblings.

MTRX Horizyn owns the one domain. OmniArmor, CyberLogix and RankUp are its
products, each on its own subdomain (omniarmor.<domain> and so on), and the
company's site is on the apex. Each subdomain is its own origin, so one
app's sign-in, storage and service worker never reach another.

Two things would undo that: a session cookie scoped to the parent domain,
which every sibling would receive, and CORS headers that let a sibling's
page read OmniArmor's answers. Neither happens. And every page and email
says whose product OmniArmor is.
"""

import os
import re
import smtplib
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_webapp import PASSWORD, AppTestCase  # noqa: E402

from omniarmor_app import notify  # noqa: E402

OTHER_ORIGINS = (
    "https://example.com",
    "https://www.example.com",
    "https://rankup.example.com",
    "https://cyberlogix.example.com",
    "https://evil.example",
)


class TestCookiesStayOnThisHost(AppTestCase):
    def test_the_session_cookie_has_no_domain(self):
        self.assertIsNone(self.app.config["SESSION_COOKIE_DOMAIN"])
        self.assertIsNone(self.app.session_interface.get_cookie_domain(self.app))

    def test_naming_the_host_does_not_widen_it_to_the_parent(self):
        """SERVER_NAME once made Flask scope the cookie to it and its subdomains."""
        self.app.config["SERVER_NAME"] = "omniarmor.example.com"
        self.assertIsNone(self.app.session_interface.get_cookie_domain(self.app))

    def test_signing_up_and_in_sets_only_host_only_cookies(self):
        headers = self.client.get("/login").headers.getlist("Set-Cookie")
        headers += self.signup().headers.getlist("Set-Cookie")
        headers += self.post("/logout").headers.getlist("Set-Cookie")
        headers += self.post("/login", {"email": "owner@example.com",
                                        "password": PASSWORD}).headers.getlist("Set-Cookie")
        self.assertTrue(headers)
        for header in headers:
            self.assertIsNone(re.search(r";\s*domain\s*=", header, re.I), header)


class TestNoSiblingMayRead(AppTestCase):
    PATHS = ("/", "/login", "/terms", "/privacy", "/healthz", "/api/stats")

    def test_no_page_grants_another_origin(self):
        self.app.config["STATS_KEY"] = "k" * 32
        for origin in OTHER_ORIGINS:
            for path in self.PATHS:
                response = self.client.get(path, headers={"Origin": origin})
                self.assertNotIn("Access-Control-Allow-Origin", response.headers, (origin, path))
                self.assertNotIn("Access-Control-Allow-Credentials", response.headers, (origin, path))

    def test_a_preflight_from_a_sibling_is_not_granted(self):
        for origin in OTHER_ORIGINS:
            response = self.client.options("/login", headers={
                "Origin": origin, "Access-Control-Request-Method": "POST"})
            self.assertNotIn("Access-Control-Allow-Origin", response.headers, origin)

    def test_pages_still_refuse_to_be_framed(self):
        headers = self.client.get("/login").headers
        self.assertEqual(headers["X-Frame-Options"], "DENY")
        self.assertIn("frame-ancestors 'none'", headers["Content-Security-Policy"])


class TestWhoIsBehindIt(AppTestCase):
    def test_terms_and_privacy_name_mtrx_horizon(self):
        for path in ("/terms", "/privacy"):
            text = " ".join(self.client.get(path).get_data(as_text=True).split())
            self.assertIn("OmniArmor is a product of MTRX Horizyn", text, path)

    def test_every_page_footer_names_it(self):
        self.assertIn(b"A product of MTRX Horizyn", self.client.get("/").data)

    def test_every_email_says_whose_product_it_is(self):
        sent = []

        class FakeSMTP:
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
                sent.append(msg)

        cfg = {"SMTP_HOST": "smtp.example.com", "SMTP_PORT": 587, "SMTP_STARTTLS": True,
               "MAIL_FROM": "OmniArmor <no-reply@omniarmor.example.com>"}
        with mock.patch.object(smtplib, "SMTP", FakeSMTP):
            self.assertEqual(notify.send_email(cfg, "pat@example.com", "Hi", "Body."), ("sent", None))
            # A retried email whose stored body already carries it gets it once.
            notify.send_email(cfg, "pat@example.com", "Hi", notify.signed("Body."))
        for msg in sent:
            body = msg.get_body(("plain",)).get_content()
            self.assertEqual(body.count("OmniArmor is a product of MTRX Horizyn."), 1, body)


# The company's earlier spelling, built in pieces so this file never holds it.
OLD_NAME = re.compile("MTRX" + r"\s+(?:#\s*)?" + "Hori" + "zon", re.I)
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class TestTheCompanyIsSpelledHorizyn(AppTestCase):
    def test_no_page_or_email_uses_the_old_spelling(self):
        pages = ["/", "/industries", "/industries/restoarmor", "/terms", "/privacy", "/signup", "/login", "/forgot",
                 "/kids"]
        for path in pages:
            self.assertIsNone(OLD_NAME.search(self.client.get(path).get_data(as_text=True)), path)
        self.signup()
        for path in ["/app", "/app/industry/1", "/app/report", "/app/audit", "/app/notifications", "/app/settings",
                     "/app/academy", "/app/armo", "/terms", "/privacy"]:
            page = self.client.get(path).get_data(as_text=True)
            self.assertIsNone(OLD_NAME.search(page), path)
        self.assertIn("MTRX Horizyn", notify.SIGNATURE)
        self.assertIn("MTRX Horizyn", notify.signed("Hi."))

    def test_no_file_in_the_repository_uses_the_old_spelling(self):
        found = []
        for folder, dirs, files in os.walk(ROOT):
            dirs[:] = [d for d in dirs if d not in (".git", "__pycache__", "instance", ".venv", "node_modules")]
            for name in files:
                if not name.endswith((".py", ".html", ".md", ".js", ".css", ".yml", ".yaml", ".txt", ".example",
                                      ".json", ".webmanifest", ".svg", ".sh")) and name not in (
                                          "Dockerfile", "Caddyfile", ".env.example"):
                    continue
                path = os.path.join(folder, name)
                with open(path, encoding="utf-8", errors="replace") as f:
                    if OLD_NAME.search(f.read()):
                        found.append(os.path.relpath(path, ROOT))
        self.assertEqual(found, [])


if __name__ == "__main__":
    unittest.main()
