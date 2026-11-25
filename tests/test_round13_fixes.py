"""1.25.0: what a strict thirteenth review asked for.

The summary says each reading in its own kind's words (an event, a hire, a batch made, a duty last done) and labels
the day a check was recorded; the full report prints with every name whole on Letter and A4; Pilot answers "what's
due this week", a forgotten password and "export my data", and is on the pricing, Help and security pages; one set
of status words on Home, the Report and the summary, and the Report's CSV in the workspace's time zone; copy (a
student's footer, a refund answer that starts with the answer, the Kitchen Safety Bundle in one line, "Download the
report and History first") and backups named aegizyn-*.db (old omniarmor-*.db ones still count)."""

import csv
import glob
import html
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_pilot import PilotCase, has_pilot  # noqa: E402
from test_webapp import AppTestCase  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATIC = os.path.join(ROOT, "omniarmor_app", "static")
PHARMACY, HR = 28, 30


def read(*parts):
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as f:
        return f.read()


def words(page):
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", page)).split())


def between(page, start, end):
    begin = page.index(start)
    return page[begin:page.index(end, begin)]


class PharmacyCase(AppTestCase):
    """The reviewer's Juniper Lane Pharmacy, near enough: a new hire's I-9, a COBRA qualifying event 47 days ago, the
    exclusion check last done 35 days ago and staff licences 41 days from expiring."""

    LONG_NAME = "Alexandra Montgomery-Whitfield"

    def setUp(self):
        super().setUp()
        self.signup(industries=(PHARMACY, HR), name=self.LONG_NAME)
        from omniarmor_app.tracking import org_today
        with self.db() as conn:
            self.today = org_today(conn.execute("SELECT * FROM orgs").fetchone())
        day = lambda n: (self.today - timedelta(days=n)).isoformat()  # noqa: E731
        self.change(HR, "i9_section_2", date=day(1))
        self.change(HR, "cobra_election_notice", date=day(47))
        self.change(PHARMACY, "exclusion_screening", date=day(35))
        self.change(PHARMACY, "license_current", date=(self.today + timedelta(days=41)).isoformat())
        self.change(HR, "hours_records", answer="yes")

    def state(self, industry_id, key):
        from omniarmor_app.tracking import states_for_org
        with self.db() as conn:
            org = conn.execute("SELECT * FROM orgs").fetchone()
            return next(s for s in states_for_org(conn, org) if s.industry_id == industry_id and s.key == key)


# --- 1. The summary's words, by the kind of check ---------------------------------------------------------------

class TestSummaryWordsByKind(PharmacyCase):
    def test_event_hire_and_last_done(self):
        page = self.client.get("/app/report/summary").data.decode()
        action = words(between(page, "data-summary-action", "data-summary-soon"))
        self.assertIn("COBRA election notice sent", action)
        self.assertIn("3 days overdue · qualifying event 47 days ago", action)
        self.assertIn("4 days overdue · last done 35 days ago", action)
        self.assertNotIn("last done 47 days ago", action)
        # A deadline says its days once: "Due in 41 days", not "Due in 41 days · 41 days left".
        self.assertIn("Pharmacy staff licenses current · PharmacyArmor Due in 41 days", action)
        self.assertNotIn("41 days left", action)
        i9 = self.state(HR, "i9_section_2")
        text = words(page)
        self.assertIn(f"hired {i9.reading_text}", text.lower())
        self.assertRegex(i9.reading_text, r"^\d+ business days? ago$")
        self.assertNotRegex(text, r"last done \d+ business days? ago")

    def test_last_checks_label_the_day_recorded(self):
        page = self.client.get("/app/report/summary").data.decode()
        last = words(between(page, "data-summary-last", "data-summary-who"))
        today = self.today.isoformat()
        self.assertIn(f"Qualifying event 47 days ago · recorded {today} · {self.LONG_NAME}", last)
        self.assertIn(f"Last done 35 days ago · recorded {today}", last)
        self.assertIn(f"41 days left · recorded {today}", last)
        self.assertIn(f"Yes · recorded {today}", last)
        self.assertRegex(last, r"Hired \d+ business days? ago · recorded ")
        self.assertNotRegex(last, r"ago · \d{4}-\d\d-\d\d")      # the old, unlabelled date

    def test_the_industry_page_asks_for_the_right_date(self):
        page = words(self.client.get(f"/app/industry/{HR}").data.decode())
        self.assertIn("Or the date it happened", page)
        page = words(self.client.get(f"/app/industry/{PHARMACY}").data.decode())
        self.assertIn("Or the date it was last done", page)
        self.assertNotIn("Or the date it last happened", page)


class TestSinceWords(unittest.TestCase):
    def test_every_check_counted_from_a_date_has_words_and_a_waiting_one_is_never_last_done(self):
        from omniarmor_app.catalog import INDUSTRIES, date_mode, rules_for, since_word
        seen = 0
        for i in INDUSTRIES:
            for rule in rules_for(i):
                word = since_word(i, rule)
                if date_mode(rule) != "since":
                    self.assertIsNone(word, rule.key)
                    continue
                seen += 1
                self.assertTrue(word, rule.key)
                if re.search(r"\bwithout\b|\bnot yet\b", rule.input):
                    self.assertNotEqual(word, "last done", (i, rule.key, rule.input))
        self.assertGreater(seen, 150)
        rule = lambda i, key: next(r for r in rules_for(i) if r.key == key)  # noqa: E731
        self.assertEqual(since_word(30, rule(30, "i9_section_2")), "hired")
        self.assertEqual(since_word(30, rule(30, "cobra_election_notice")), "qualifying event")
        self.assertEqual(since_word(2, rule(2, "date_marking")), "made or opened")
        self.assertEqual(since_word(28, rule(28, "exclusion_screening")), "last done")
        self.assertEqual(since_word(28, rule(28, "theft_loss_report")), "event")
        self.assertEqual(since_word(28, rule(28, "biennial_inventory")), "last done")

    def test_a_food_batch_says_made_or_opened(self):
        import dataclasses
        from omniarmor_app.catalog import rules_for
        from omniarmor_app.tracking import compute_state
        from datetime import date
        rule = next(r for r in rules_for(2) if r.key == "date_marking")
        st = dataclasses.replace(compute_state(2, rule, None, date(2026, 11, 24)), value=9)
        # 1.26.0: day 9 of the 7-day rule is 8 days after the day it was made (the make day is day 1).
        self.assertEqual(st.reading_line, "made or opened 8 days ago (day 9)")
        self.assertEqual(st.recorded_line, "Made or opened 8 days ago (day 9)")


# --- 2. The full report prints with every name whole -------------------------------------------------------------

def find_chrome():
    """(path, flags) of a headless browser: the CHROME setting, Chrome's own headless shell, or Chrome or Chromium
    (CI's runners have Google Chrome); None when there is none."""
    if os.environ.get("CHROME") and shutil.which(os.environ["CHROME"]):
        return shutil.which(os.environ["CHROME"]), ["--headless=new"]
    shell = shutil.which("chrome-headless-shell") or next(iter(sorted(glob.glob(
        "/opt/pw-browsers/chromium_headless_shell-*/chrome-headless-shell-linux64/chrome-headless-shell"), reverse=True)), None)
    if shell:
        return shell, []
    for name in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser"):
        if shutil.which(name):
            return shutil.which(name), ["--headless=new"]
    return None


# Letter and A4 less the 12 mm margins app.css gives the page (@page), in CSS pixels (96 a inch).
PAPER_WIDTHS = {"Letter": round(8.5 * 96 - 2 * 12 / 25.4 * 96), "A4": round(210 / 25.4 * 96 - 2 * 12 / 25.4 * 96)}
MEASURE = """<script>
addEventListener("load", () => {
  const out = [];
  const page = document.documentElement.clientWidth;
  for (const cell of document.querySelectorAll("table.report-cards td.upd")) {
    const r = cell.getBoundingClientRect();
    const by = cell.querySelector(".upd-by");
    const b = by ? by.getBoundingClientRect() : r;
    out.push({ text: cell.innerText, clipped: cell.scrollWidth > cell.clientWidth + 1 || r.right > page + 1 || b.right > r.right + 1,
      lines: by ? Math.round((b.top - r.top) / 4) : 0 });
  }
  const tables = [...document.querySelectorAll("table.report-cards")].map((t) => t.getBoundingClientRect().right);
  document.body.setAttribute("data-measured", JSON.stringify({ page, cells: out, right: Math.max(0, ...tables) }));
});
</script>"""


class TestReportPrintsWholeNames(PharmacyCase):
    def print_html(self, folder):
        """The report as the browser prints it: its print rules turned on for the screen (@media print to @media
        all), the fonts from the static folder and no scripts but the measuring one."""
        page = self.client.get("/app/report").data.decode()
        css = read("omniarmor_app", "static", "app.css").replace("@media print{", "@media all{")
        css = css.replace("url(fonts/", "url(file://" + os.path.join(STATIC, "fonts") + "/")
        with open(os.path.join(folder, "print.css"), "w", encoding="utf-8") as f:
            f.write(css)
        page = re.sub(r"<script\b.*?</script>", "", page, flags=re.S)
        page = re.sub(r'<link rel="stylesheet" href="[^"]*app\.css[^"]*">', '<link rel="stylesheet" href="print.css">', page)
        page = page.replace("</body>", MEASURE + "</body>")
        path = os.path.join(folder, "report.html")
        with open(path, "w", encoding="utf-8") as f:
            f.write(page)
        return path

    def test_the_print_rules(self):
        css = read("omniarmor_app", "static", "app.css")
        block = css[css.index("/* 1.25.0: the full report on Letter or A4."):]
        block = block[:block.index("\n}")]
        for rule in (".table-wrap{overflow:visible", "table.report-cards{table-layout:fixed", "white-space:normal",
                     ".upd-by{display:block}", ".upd-sep{display:none}"):
            self.assertIn(rule, block)
        widths = [float(w) for w in re.findall(r"\.c-\w+\{width:(\d+)%\}", block)]
        self.assertEqual(len(widths), 6)
        self.assertEqual(sum(widths), 100)
        page = self.client.get("/app/report").data.decode()
        self.assertIn('<col class="c-upd">', page)
        self.assertIn(f'<span class="upd-by" data-pilot-private><span class="upd-sep"> · </span>{self.LONG_NAME}</span>', page)

    def test_letter_and_a4_in_a_real_browser(self):
        found = find_chrome()
        if not found:
            self.skipTest("no Chrome or Chromium here")
        chrome, mode = found
        base = [chrome, *mode, "--no-sandbox", "--disable-gpu", "--no-first-run", "--disable-background-networking",
                "--disable-component-update", "--allow-file-access-from-files"]
        with tempfile.TemporaryDirectory() as folder:
            path = self.print_html(folder)
            for paper, width in PAPER_WIDTHS.items():
                done = subprocess.run([*base, "--hide-scrollbars", f"--user-data-dir={folder}/profile-{paper}",
                                       f"--window-size={width},1200", "--dump-dom", "file://" + path],
                                      capture_output=True, text=True, timeout=90)
                found = re.search(r'data-measured="([^"]*)"', done.stdout)
                self.assertTrue(found, (paper, done.stderr[-800:]))
                measured = json.loads(html.unescape(found.group(1)))
                cells = measured["cells"]
                self.assertGreater(len(cells), 5, paper)
                self.assertLessEqual(measured["right"], measured["page"] + 1, paper)
                # (A long name may wrap inside its own column: compared without the line breaks and spaces.)
                whole = re.sub(r"\s", "", self.LONG_NAME)
                named = [c for c in cells if whole in re.sub(r"\s", "", c["text"])]
                self.assertGreaterEqual(len(named), 4, paper)
                for c in cells:
                    self.assertFalse(c["clipped"], (paper, c))
                # The name has a line of its own, under the date.
                self.assertTrue(all(c["lines"] >= 1 for c in named), (paper, named))
            # And the PDF itself, where a reader for it is installed: every name whole.
            if shutil.which("pdftotext"):
                pdf = os.path.join(folder, "report.pdf")
                subprocess.run([*base, f"--user-data-dir={folder}/profile-pdf", "--no-pdf-header-footer",
                                f"--print-to-pdf={pdf}", "file://" + path], capture_output=True, timeout=90)
                text = subprocess.run(["pdftotext", pdf, "-"], capture_output=True, text=True).stdout
                for part in re.split(r"[\s-]+", self.LONG_NAME):     # it may wrap in its column, but all of it is there
                    self.assertGreaterEqual(text.count(part), 4, part)


# --- 3. Pilot ---------------------------------------------------------------------------------------------------

class TestPilotOnPricingHelpSecurity(PilotCase):
    def test_a_visitor_gets_it_and_a_kid_never_does(self):
        from omniarmor_app import pilot
        for path in ("/pricing", "/help", "/security"):
            page = self.page(path)
            self.assertTrue(has_pilot(page), path)
            self.assertIn('data-who="visitor"', page)
        self.assertTrue({"public.pricing", "public.help", "public.security"} <= pilot.PUBLIC_PAGES)
        _, maya = self.class_with_maya()
        kid = self.kid_client(maya["id"])
        for path in ("/pricing", "/help", "/security"):
            self.assertFalse(has_pilot(kid.get(path).data.decode()), path)

    def test_the_tag_says_how_long_a_reset_link_works(self):
        from omniarmor_app.auth import RESET_HOURS
        page = self.page("/help")
        facts = json.loads(html.unescape(re.search(r"data-facts='([^']*)'", page).group(1)))
        self.assertEqual(facts["reset_hours"], RESET_HOURS)

    def test_the_config(self):
        src = read("omniarmor_app", "static", "pilot-omniarmor.js")
        self.assertIn('"due", "week", "soon", "coming", "next", "month", "tomorrow"', src)
        self.assertIn('{ label: "How do I change my password?"', src)
        self.assertNotIn("(/help#prices)", src)
        self.assertIn('if (path === "/pricing")', src)


# --- 4. One set of status words; the Report's CSV in local time ---------------------------------------------------

class TestOneSetOfStatusWords(PharmacyCase):
    def test_home_report_and_summary(self):
        home = words(self.client.get("/app").data.decode())
        report = words(self.client.get("/app/report").data.decode())
        page = self.client.get("/app/report/summary").data.decode()
        summary = words(page)
        for text in (home, report):
            self.assertRegex(text, r"\d+ blocked \d+ warnings? \d+ cleared \d+ without a reading")
        self.assertRegex(summary, r"20 checks: \d+ blocked · \d+ warnings? · \d+ cleared · \d+ without a reading\.")
        key = words(between(page, "data-status-key", "</p>"))
        for pair in ("Blocked: overdue or out of limits", "Warning: due soon or near a limit", "Cleared: current",
                     "Without a reading: not recorded yet"):
            self.assertIn(pair, key)
        groups = words(between(page, "data-summary-groups", "</ul>"))
        self.assertRegex(groups, r"PharmacyArmor · Pharmacies \d+ blocked · \d+ warnings? · \d+ cleared")
        for old in ("checks current", " due soon · ", " not recorded"):
            self.assertNotIn(old, groups)
        self.assertNotIn("checks current", summary)

    def test_report_csv_in_the_workspace_time_zone(self):
        with self.db() as conn:
            conn.execute("UPDATE orgs SET timezone = 'America/Chicago'")
            conn.execute("UPDATE items SET updated_at = '2026-11-20T16:07:31+00:00'")
            conn.commit()
        rows = list(csv.reader(io.StringIO(self.client.get("/app/report.csv").data.decode())))
        self.assertEqual(rows[0][6], "Last updated (America/Chicago)")
        dated = [r for r in rows[1:] if r[6]]
        self.assertTrue(dated)
        for r in dated:
            self.assertEqual(r[6], "2026-11-20T10:07:31-06:00")


# --- 5. Copy ----------------------------------------------------------------------------------------------------

class TestStudentFooter(PilotCase):
    def test_kid_pages_get_their_own_footer(self):
        class_id, maya = self.class_with_maya()
        maya = maya["id"]
        kid = self.kid_client(maya)
        for path in (f"/app/academy/{maya}", "/kids"):
            for client in (kid,):
                page = client.get(path, follow_redirects=True).data.decode()
                foot = words(page[page.index('<footer class="site">'):page.index("</footer>")])
                self.assertIn("OmniArmor Academy · Learn how a business works, one lesson at a time", foot, path)
                self.assertNotIn("Catch the fine", foot, path)
                self.assertNotIn("legal advice", foot, path)
                self.assertFalse(has_pilot(page), path)
                self.assertNotIn("data-companion", page, path)
        # The grown-ups' pages keep theirs, their Academy pages too.
        for path in ("/", "/app/academy/classes", f"/app/academy/classes/{class_id}"):
            page = self.client.get(path, follow_redirects=True).data.decode()
            foot = words(page[page.index('<footer class="site">'):page.index("</footer>")])
            self.assertIn("Decision support, not legal advice", foot, path)


class TestCopy(AppTestCase):
    def test_pricing_explains_the_bundle_in_one_line(self):
        from omniarmor_app import names, plans
        page = words(self.client.get("/pricing").data.decode())
        self.assertIn(f"{names.FRIDGE_APP} Kitchen Safety Bundle: for kitchens on {names.FRIDGE_APP}, "
                      f"{names.COMPANY}'s fridge and freezer alarm app.", page)
        self.assertIn(f"{plans.price_label(plans.BUNDLE_DOLLARS)} paid to {names.FRIDGE_APP} includes OmniArmor Pro", page)

    def test_download_the_report_and_history_first(self):
        for name in ("help.html", "security.html", "privacy.html"):
            page = read("omniarmor_app", "templates", name)
            self.assertIn("Download the report and History first if you need them.", page, name)
            self.assertNotIn("audit trail first", page, name)
        self.assertIn("**Download the report and History first** if you need them.",
                      read("omniarmor_app", "static", "pilot-omniarmor.js"))


class TestBackupNames(AppTestCase):
    def setUp(self):
        super().setUp()
        self.folder = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.folder, True)
        self.cfg = {**self.app.config, "DATABASE": self.db_path, "BACKUP_DIR": self.folder, "BACKUP_KEEP": 3,
                    "OFFSITE_BACKUP_COMMAND": ""}

    def plant(self, name):
        with open(os.path.join(self.folder, name), "wb") as f:
            f.write(b"old")

    def test_new_backups_and_old_ones_both_count(self):
        # 1.26.0: back to the name OmniArmor, new copies are omniarmor-*.db and 1.25.0's aegizyn-*.db ones count.
        from omniarmor_app import autopilot, jobs
        from omniarmor_app.db import utcnow
        for day in ("20200101", "20200102", "20200103"):
            self.plant(f"aegizyn-{day}-000000-000000.db")
        self.assertTrue(autopilot.latest_backup(self.cfg).endswith("aegizyn-20200103-000000-000000.db"))
        made = jobs.backup_database(self.cfg)
        self.assertRegex(os.path.basename(made), r"^omniarmor-\d{8}-\d{6}-\d{6}\.db$")
        left = sorted(os.listdir(self.folder))
        # Pruned by date across both names: the oldest old one went, the newest copy is the new one.
        self.assertEqual(left, ["aegizyn-20200102-000000-000000.db", "aegizyn-20200103-000000-000000.db",
                                "omniarmor-" + os.path.basename(made).split("-", 1)[1]])
        self.assertEqual(autopilot.latest_backup(self.cfg), made)
        # An old-named copy made today is today's copy: no second one.
        for name in os.listdir(self.folder):
            os.remove(os.path.join(self.folder, name))
        today = f"aegizyn-{utcnow().strftime('%Y%m%d')}-000000-000000.db"
        self.plant(today)
        self.assertEqual(os.path.basename(jobs.backup_database(self.cfg)), today)
        self.assertEqual(os.listdir(self.folder), [today])

    def test_autopilot_says_the_new_name(self):
        from omniarmor_app import jobs
        src = read("omniarmor_app", "autopilot.py")
        self.assertIn("Made a missing backup: {os.path.basename(made)}.", src)
        self.assertEqual(jobs.BACKUP_PREFIX, "omniarmor")
        self.assertEqual(jobs.OLD_BACKUP_PREFIXES, ("aegizyn",))


class TestVersion(unittest.TestCase):
    def test_version_and_changelog(self):
        from omniarmor_app.version import __version__
        self.assertGreaterEqual(tuple(map(int, __version__.split("."))), (1, 25, 0))
        log = read("CHANGELOG.md")
        section = log[log.index("## 1.25.0"):log.index("## 1.24.0")]
        for said in ("hired", "recorded", "Letter and A4", "password", "/pricing", "time zone", "footer", "refund",
                     "Kitchen Safety Bundle", "aegizyn-"):
            self.assertIn(said, section)


if __name__ == "__main__":
    unittest.main()
