"""Launch polish: the version and changelog, error pages, icons and share
previews, robots.txt and the sitemap."""

import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_webapp import AppTestCase  # noqa: E402

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


if __name__ == "__main__":
    unittest.main()
