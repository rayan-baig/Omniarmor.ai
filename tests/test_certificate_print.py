"""A certificate prints on one landscape page with none of the app around it.
The page itself was printed to PDF with a real browser (A4 and US Letter,
one page each); this keeps the pieces that make that work in place."""

import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_webapp import AppTestCase  # noqa: E402

from omniarmor_app import academy  # noqa: E402

STATIC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "omniarmor_app", "static")


class TestCertificatePrint(AppTestCase):
    def test_the_certificate_loads_the_print_stylesheet(self):
        self.signup()
        self.post("/app/academy/learners", {"nickname": "Sam", "avatar": "rocket", "track": "launchpad"})
        t = academy.TRACKS["launchpad"]
        with self.db() as conn:
            for level in [academy.level_id(t, w, 1) for w in t.topics] + [
                    academy.level_id(t, academy.FINAL_WORLD.number, 1)]:
                conn.execute("INSERT INTO learner_progress (learner_id, level, attempts, best_score, best_stars,"
                             " completed_at) VALUES (1, ?, 1, 5, 3, '2026-02-01T12:00:00+00:00')", (level,))
            conn.commit()
        page = self.client.get("/app/academy/1/certificate").data.decode()
        link = re.search(r'<link rel="stylesheet" href="(/static/certificate-print\.css\?v=\d+)" media="print">', page)
        self.assertIsNotNone(link)
        response = self.client.get(link.group(1))
        self.assertEqual(response.status_code, 200)
        response.close()
        # No inline styles or scripts: the CSP would block them.
        self.assertNotIn("<style", page)

    def test_one_landscape_page_without_the_app(self):
        with open(os.path.join(STATIC, "certificate-print.css")) as f:
            css = f.read()
        self.assertRegex(css, r"@page\{size:landscape;margin:10mm\}")
        for chrome in (".topbar", "footer.site", ".tabbar", ".companion", ".flashes", ".no-print"):
            self.assertIn(chrome, css.split("{display:none")[0])
        # The certificate's height fits the shorter of A4 and Letter in
        # landscape (210 mm and 215.9 mm tall) less both 10 mm margins, and
        # can't spill onto a second page.
        height = float(re.search(r"\.ac-cert\{[^}]*height:(\d+(?:\.\d+)?)mm", css).group(1))
        self.assertLessEqual(height, 210 - 2 * 10)
        block = re.search(r"\.ac-cert\{([^}]*)\}", css).group(1)
        self.assertIn("overflow:hidden", block)
        self.assertIn("break-inside:avoid", block)


if __name__ == "__main__":
    unittest.main()
