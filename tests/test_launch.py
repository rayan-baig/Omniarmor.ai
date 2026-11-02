"""Launch polish: the version and changelog, error pages, icons and share
previews, robots.txt and the sitemap."""

import os
import re
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_webapp import AppTestCase  # noqa: E402

from omniarmor_app import create_app  # noqa: E402
from omniarmor_app.version import __version__  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class TestVersion(AppTestCase):
    def test_one_version_number(self):
        self.assertRegex(__version__, r"^\d+\.\d+\.\d+$")
        # Set in one place only: no other file in the app spells it out.
        found = []
        for folder, dirs, files in os.walk(os.path.join(ROOT, "omniarmor_app")):
            dirs[:] = [d for d in dirs if d != "__pycache__"]
            for name in files:
                if name.endswith((".py", ".html", ".js", ".webmanifest")) and name != "version.py":
                    with open(os.path.join(folder, name), encoding="utf-8") as f:
                        if re.search(r"__version__\s*=", f.read()):
                            found.append(name)
        self.assertEqual(found, [])

    def test_the_changelog_has_this_version(self):
        with open(os.path.join(ROOT, "CHANGELOG.md"), encoding="utf-8") as f:
            text = f.read()
        self.assertIn(f"## {__version__} (", text)
        first = re.search(r"^## (\S+) ", text, re.M).group(1)
        self.assertEqual(first, __version__, "the newest section comes first")

    def test_healthz_gives_the_version_and_nothing_sensitive(self):
        data = self.client.get("/healthz").get_json()
        self.assertEqual(set(data), {"status", "schema", "version"})
        self.assertEqual(data["version"], __version__)

    def test_settings_show_the_version(self):
        self.signup()
        page = self.client.get("/app/settings").get_data(as_text=True)
        self.assertRegex(page, r'id="about"')
        self.assertIn(f"<span class=\"mono\" data-version>{__version__}</span>", page)


# Things a server error must never show a visitor.
LEAKS = ("Traceback", "RuntimeError", "secret.py", "SECRET_KEY", "/srv/", "werkzeug", "Werkzeug",
         "The requested URL", "File \"")


class TestErrorPages(AppTestCase):
    def assert_friendly(self, response, code, title, home="/"):
        self.assertEqual(response.status_code, code)
        page = response.get_data(as_text=True)
        self.assertEqual(response.mimetype, "text/html")
        self.assertIn(f"<h1>{title}</h1>", page.replace("&#39;", "'"))
        self.assertIn(f'<a class="btn" href="{home}"', page)
        self.assertIn('/static/app.css', page)              # the same look as every page
        self.assertIn('<meta name="robots" content="noindex, nofollow">', page)
        for leak in LEAKS:
            self.assertNotIn(leak, page)
        return page

    def test_a_missing_page(self):
        page = self.assert_friendly(self.client.get("/no-such-page"), 404, "Page not found")
        self.assertIn("A product of MTRX Horizyn", page)
        self.assertIn('href="/industries"', page)
        self.assert_friendly(self.client.get("/industries/notreal"), 404, "Page not found")

    def test_a_missing_page_when_signed_in_leads_back_to_the_checks(self):
        self.signup()
        self.assert_friendly(self.client.get("/app/industry/999"), 404, "Page not found", home="/app")

    def test_a_server_error(self):
        self.app.config["PROPAGATE_EXCEPTIONS"] = False   # answer as a running server does
        with self.assertLogs("omniarmor_app", "ERROR"):
            response = self.client.get("/_test/server-error")
        page = self.assert_friendly(response, 500, "Something went wrong on our side")
        self.assertIn("try again in a minute", page)
        with self.db() as conn:
            row = conn.execute("SELECT path, error FROM app_errors").fetchone()
        self.assertEqual(row["path"], "/_test/server-error")      # recorded for Autopilot, not shown
        self.assertIn("RuntimeError", row["error"])

    def test_a_server_error_while_signed_in(self):
        self.signup()
        self.app.config["PROPAGATE_EXCEPTIONS"] = False
        with self.assertLogs("omniarmor_app", "ERROR"):
            response = self.client.get("/_test/server-error")
        self.assert_friendly(response, 500, "Something went wrong on our side",
                             home="/app")

    def test_when_even_the_error_page_fails(self):
        self.app.config["PROPAGATE_EXCEPTIONS"] = False
        import omniarmor_app
        with mock.patch.object(omniarmor_app, "render_template", side_effect=RuntimeError("template broke")), \
                self.assertLogs("omniarmor_app", "ERROR") as logged:
            response = self.client.get("/_test/server-error")
            page = self.assert_friendly(response, 500, "Something went wrong on our side")
            self.assertNotIn("template broke", page)
            self.assert_friendly(self.client.get("/nope"), 404, "Page not found")
        self.assertTrue(any("couldn't show the error page" in line for line in logged.output))

    def test_an_expired_form_keeps_its_own_message(self):
        response = self.client.post("/login", data={"email": "a@example.com", "password": "x"})
        self.assertEqual(response.status_code, 400)
        self.assertIn("This form expired", response.get_data(as_text=True))

    def test_the_failing_page_exists_only_in_tests(self):
        app = create_app(DATABASE=os.path.join(self.tmp.name, "live.db"), SCHEDULER_ENABLED=False)
        self.assertFalse(app.config["TESTING"])
        self.assertNotIn("/_test/server-error", [r.rule for r in app.url_map.iter_rules()])
        self.assertEqual(app.test_client().get("/_test/server-error").status_code, 404)


if __name__ == "__main__":
    unittest.main()
