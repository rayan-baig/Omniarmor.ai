"""Launch polish: the version and changelog, error pages, icons and share
previews, robots.txt and the sitemap."""

import json
import os
import re
import struct
import sys
import unittest
from html.parser import HTMLParser
from urllib.parse import urlsplit
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


class Head(HTMLParser):
    """The <link> and <meta> tags of a page."""

    def __init__(self, page):
        super().__init__(convert_charrefs=True)
        self.links, self.meta = [], {}
        self.feed(page)

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "link":
            self.links.append(a)
        elif tag == "meta" and ("property" in a or "name" in a):
            self.meta[a.get("property") or a.get("name")] = a.get("content")


def png_size(data):
    """(width, height) from a PNG's header."""
    assert data[:8] == b"\x89PNG\r\n\x1a\n", "not a PNG"
    return struct.unpack(">II", data[16:24])


PUBLIC = ["/", "/industries", "/industries/fleetarmor", "/industries/casinoarmor", "/terms", "/privacy", "/signup",
          "/login"]
BASE = "https://omniarmor.test"


class TestIconsAndSharePreviews(AppTestCase):
    def fetch(self, url):
        """Fetches one of this site's addresses, full or relative, the way a browser would."""
        parts = urlsplit(url)
        if parts.netloc:
            self.assertEqual(f"{parts.scheme}://{parts.netloc}", BASE, url)
        response = self.client.get(parts.path + (f"?{parts.query}" if parts.query else ""))
        self.assertEqual(response.status_code, 200, url)
        response.get_data()     # read it all, then let go of the file
        response.close()
        return response

    def test_every_icon_and_manifest_link_resolves(self):
        checked = set()

        def check(path):
            head = Head(self.client.get(path).get_data(as_text=True))
            icons = [link for link in head.links
                     if set(link.get("rel", "").split()) & {"icon", "apple-touch-icon", "manifest"}]
            self.assertEqual({link["rel"] for link in icons}, {"icon", "apple-touch-icon", "manifest"}, path)
            for link in icons:
                if link["href"] in checked:
                    continue
                checked.add(link["href"])
                response = self.fetch(link["href"])
                if link["rel"] == "manifest":
                    self.assertEqual(response.mimetype, "application/manifest+json")
                    self.check_manifest(json.loads(response.data))
                elif link.get("type"):
                    self.assertEqual(response.mimetype, link["type"], link)
                else:
                    self.assertTrue(response.mimetype.startswith("image/"), link)
                if link["rel"] == "apple-touch-icon":
                    self.assertEqual(png_size(response.data), (180, 180))

        for path in PUBLIC + ["/login", "/kids", "/forgot", "/no-such-page"]:
            check(path)
        self.signup()
        for path in ["/app", "/app/settings", "/app/academy", "/app/no-such-page"]:
            check(path)
        self.assertGreaterEqual(len(checked), 4)

    def check_manifest(self, manifest):
        self.assertEqual(manifest["start_url"], "/")
        sizes = set()
        for icon in manifest["icons"]:
            response = self.fetch(icon["src"])
            self.assertEqual(response.mimetype, icon["type"], icon)
            if icon["type"] == "image/png":
                w, h = png_size(response.data)
                self.assertEqual(icon["sizes"], f"{w}x{h}", icon)
                sizes.add(w)
        self.assertTrue({192, 512} <= sizes, "phones need a 192 and a 512 icon")

    def test_the_icons_browsers_ask_for_at_the_root(self):
        ico = self.client.get("/favicon.ico")
        ico.get_data()
        ico.close()
        self.assertEqual((ico.status_code, ico.mimetype), (200, "image/vnd.microsoft.icon"))
        self.assertEqual(ico.data[:4], b"\x00\x00\x01\x00")      # an icon file, not a redirect
        for path in ("/apple-touch-icon.png", "/apple-touch-icon-precomposed.png"):
            touch = self.client.get(path)
            touch.get_data()
            touch.close()
            self.assertEqual((touch.status_code, png_size(touch.data)), (200, (180, 180)), path)

    def test_share_previews_on_every_public_page(self):
        sitemap = self.client.get("/sitemap.xml").get_data(as_text=True)
        for path in PUBLIC:
            page = self.client.get(path).get_data(as_text=True)
            head = Head(page)
            meta = head.meta
            title = re.search(r"<title>(.*?)</title>", page).group(1)
            self.assertEqual(meta["og:title"], title.replace("&amp;", "&"), path)
            self.assertEqual(meta["twitter:title"], meta["og:title"])
            self.assertEqual(meta["og:description"], meta["description"], path)
            self.assertEqual(meta["twitter:description"], meta["description"])
            self.assertTrue(meta["og:description"].strip(), path)
            self.assertEqual(meta["og:type"], "website")
            self.assertEqual(meta["twitter:card"], "summary_large_image")
            # One address per page, the one the sitemap lists.
            canonical = [link["href"] for link in head.links if link.get("rel") == "canonical"]
            self.assertEqual(canonical, [meta["og:url"]], path)
            self.assertIn(f"<loc>{meta['og:url']}</loc>", sitemap, path)
            # The picture is a full address that resolves, at the size the tags say.
            for key in ("og:image", "twitter:image"):
                self.assertTrue(meta[key].startswith(BASE + "/static/"), meta[key])
                image = self.fetch(meta[key])
                self.assertEqual(image.mimetype, "image/png")
                self.assertEqual(png_size(image.data), (int(meta["og:image:width"]), int(meta["og:image:height"])))
            self.assertEqual(png_size(image.data), (1200, 630))
            self.assertTrue(meta["og:image:alt"])
        upper = Head(self.client.get("/industries/FleetArmor").get_data(as_text=True))
        self.assertEqual(upper.meta["og:url"], BASE + "/industries/fleetarmor")

    def test_private_pages_have_no_share_preview(self):
        self.signup()
        for path in ["/app", "/app/settings", "/app/academy", "/app/report"]:
            head = Head(self.client.get(path).get_data(as_text=True))
            self.assertFalse([k for k in head.meta if k.startswith(("og:", "twitter:"))], path)
            self.assertFalse([link for link in head.links if link.get("rel") == "canonical"], path)


def disallowed(robots, path):
    """Whether robots.txt closes this path, the way search engines read it
    (prefixes, and "$" for the end of the address)."""
    for line in robots.splitlines():
        if line.startswith("Disallow:"):
            rule = line.split(":", 1)[1].strip()
            if rule.endswith("$") and path == rule[:-1]:
                return True
            if not rule.endswith("$") and rule and path.startswith(rule):
                return True
    return False


NOINDEX = '<meta name="robots" content="noindex, nofollow">'


class TestRobotsAndSitemap(AppTestCase):
    def setUp(self):
        super().setUp()
        self.robots = self.client.get("/robots.txt").get_data(as_text=True)
        self.sitemap = self.client.get("/sitemap.xml").get_data(as_text=True)
        self.listed = re.findall(r"<loc>(.*?)</loc>", self.sitemap)

    def private_paths(self):
        """One address of each private kind, signed in, with real tokens."""
        from omniarmor_app.db import iso, now_iso, utcnow
        from omniarmor_app.security import new_token
        from datetime import timedelta
        self.signup()
        self.post("/app/academy/learners", {"nickname": "Sam", "avatar": "rocket"})
        reset, reset_hash = new_token()
        invite, invite_hash = new_token()
        later = iso(utcnow() + timedelta(hours=1))
        with self.db() as conn:
            lid = conn.execute("SELECT id FROM learners").fetchone()[0]
            conn.execute("INSERT INTO password_resets (token_hash, user_id, created_at, expires_at)"
                         " VALUES (?, 1, ?, ?)", (reset_hash, now_iso(), later))
            conn.execute("INSERT INTO invites (token_hash, org_id, created_by, created_at, expires_at)"
                         " VALUES (?, 1, 1, ?, ?)", (invite_hash, now_iso(), later))
            conn.commit()
        return {
            "signed in": ["/app", "/app/settings", "/app/academy", "/app/academy/plan", f"/app/academy/{lid}/track",
                          f"/app/academy/{lid}/friends", "/app/industry/1", "/app/report", "/app/audit",
                          "/app/notifications", "/app/armo", "/app/report.csv", "/app/audit.csv"],
            "signed out": [f"/reset/{reset}", f"/signup?invite={invite}", "/kids", "/forgot"],
        }

    def test_robots_closes_every_private_kind_and_names_the_sitemap(self):
        self.assertIn("User-agent: *", self.robots)
        self.assertIn("Sitemap: https://omniarmor.test/sitemap.xml", self.robots)
        for path in ("/app", "/app/academy", "/app/settings", "/app/academy/1/world/2", "/reset/abc",
                     "/signup?invite=abc", "/kids", "/forgot", "/billing/stripe/webhook", "/api/stats"):
            self.assertTrue(disallowed(self.robots, path), path)

    def test_the_sitemap_lists_the_public_pages_and_robots_lets_them_in(self):
        self.assertEqual(self.listed.count("https://omniarmor.test/"), 1)
        for path in PUBLIC:
            self.assertIn("https://omniarmor.test" + path, self.listed)
        self.assertEqual(len([u for u in self.listed if "/industries/" in u]), 50)
        self.assertEqual(len(self.listed), len(set(self.listed)))
        for url in self.listed:
            path = urlsplit(url).path
            self.assertFalse(disallowed(self.robots, path), path)
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200, path)
            self.assertNotIn("X-Robots-Tag", response.headers, path)
            self.assertNotIn(NOINDEX, response.get_data(as_text=True), path)
        self.assertFalse(disallowed(self.robots, "/apple-touch-icon.png"))
        self.assertFalse(disallowed(self.robots, "/static/og-image.png"))

    def test_private_pages_are_never_listed_and_say_noindex(self):
        for url in self.listed:
            for word in ("/app", "/academy", "/settings", "/reset", "invite", "/kids", "/forgot"):
                self.assertNotIn(word, url)
        groups = self.private_paths()
        for path in groups["signed in"]:
            self.check_private(path)
        self.post("/logout")
        for path in groups["signed out"]:
            self.check_private(path)

    def check_private(self, path):
        response = self.client.get(path)
        self.assertEqual(response.status_code, 200, path)
        self.assertEqual(response.headers.get("X-Robots-Tag"), "noindex, nofollow", path)
        if response.mimetype == "text/html":
            self.assertIn(NOINDEX, response.get_data(as_text=True), path)
        self.assertTrue(disallowed(self.robots, path), path)
        self.assertNotIn("https://omniarmor.test" + path, self.listed)

    def test_every_other_address_says_noindex(self):
        """Every GET address in the app, filled in with something, either is a
        public page or answers noindex, whatever it answers."""
        from omniarmor_app import NOT_PAGES, PUBLIC_PAGES
        self.signup()
        for rule in self.app.url_map.iter_rules():
            if "GET" not in rule.methods or rule.endpoint in PUBLIC_PAGES | NOT_PAGES:
                continue
            if rule.endpoint.startswith("_test_"):
                continue    # the page that always fails, for the error page's test
            path = re.sub(r"<int:[^>]+>", "1", re.sub(r"<(?:path:|string:)?[a-z_]+>", "x", rule.rule))
            response = self.client.get(path)
            response.close()
            self.assertEqual(response.headers.get("X-Robots-Tag"), "noindex, nofollow", (path, response.status_code))
        # A public page that isn't there (a 404) is not listed either.
        self.post("/logout")
        missing = self.client.get("/industries/notreal")
        self.assertEqual(missing.headers.get("X-Robots-Tag"), "noindex, nofollow")
        self.assertIn(NOINDEX, missing.get_data(as_text=True))
        self.assertNotIn("og:title", missing.get_data(as_text=True))


if __name__ == "__main__":
    unittest.main()
