"""1.27.0: what a strict fifteenth review asked for.

Change password on a phone: the result showed at the top of Settings, far above "Your password" where the page opens,
so it now shows under that heading. Home's "Needs attention" lists each tracked item that needs it, as the summary
does (a food batch on its last day was in neither list while another batch was over the limit), in the summary's
words ("4 days overdue · last done 35 days ago"). Pilot's answers with no key are in tests/js."""

import html
import json
import os
import re
import sys
import unittest
from datetime import timedelta

from markupsafe import escape

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_webapp import PASSWORD, AppTestCase  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESTO, PHARMACY = 2, 28


def words(page):
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", page)).split())


def between(page, start, end):
    begin = page.index(start)
    return page[begin:page.index(end, begin)]


class TodayCase(AppTestCase):
    def today(self):
        from omniarmor_app.tracking import org_today
        with self.db() as conn:
            return org_today(conn.execute("SELECT * FROM orgs").fetchone())


# --- 1. Change password: the notice under "Your password" ------------------------------------------------------

class TestPasswordNoticeInItsSection(AppTestCase):
    NEW = "a brand new password"

    def setUp(self):
        super().setUp()
        self.signup()
        self.client.get("/app")    # the welcome notice is read here, so Settings starts with none

    def change_pw(self, current, new):
        got = self.post("/app/settings/password", {"current_password": current, "new_password": new})
        self.assertTrue(got.headers["Location"].endswith("/app/settings#password"), got.headers["Location"])
        return self.client.get("/app/settings").data.decode()

    def assert_in_section(self, page, notice, kind):
        top = page[:page.index('<div class="page-head">')]
        section = between(page, '<h2 id="password">', "</form>")
        self.assertNotIn(notice, words(top), "not at the top of the page, out of sight on a phone")
        self.assertIn("data-password-note", section)
        self.assertIn(f'<li class="flash {kind}">{escape(notice)}</li>', section)
        self.assertEqual(words(page).count(notice), 1, "said once")

    def test_a_wrong_current_password_says_so_under_your_password(self):
        self.assert_in_section(self.change_pw("not my password", self.NEW),
                               "That isn't your current password. Nothing was changed.", "error")

    def test_a_short_new_password_says_so_there_too(self):
        self.assert_in_section(self.change_pw(PASSWORD, "short"), "Use at least 10 characters for your password.", "error")

    def test_a_changed_password_says_so_there_too(self):
        self.assert_in_section(self.change_pw(PASSWORD, self.NEW),
                               "Your password is changed. Every other device was signed out.", "ok")

    def test_the_notice_is_shown_once(self):
        self.change_pw("not my password", self.NEW)
        self.assertNotIn("That isn't your current password", self.client.get("/app/settings").data.decode())

    def test_other_notices_stay_at_the_top(self):
        self.post("/app/settings/reminders", {"email_reminders": "on"})
        page = self.client.get("/app/settings").data.decode()
        self.assertNotIn("data-password-note", page)
        self.assertIn('<ul class="flashes" role="status">', page[:page.index('<div class="page-head">')])


# --- 2. and 3. Home's "Needs attention": each item, in the summary's words -------------------------------------

class TestHomeListsEachItemThatNeedsIt(TodayCase):
    """The reviewer's kitchen: opened ham over the 7-day limit, chicken salad on its last day (day 7)."""

    def setUp(self):
        super().setUp()
        self.signup(industries=(RESTO,))
        today = self.today()
        for label, days in (("Opened ham", 9), ("Chicken salad", 6), ("Soup base", 1)):
            self.post(f"/app/industry/{RESTO}/rule/date_marking/entries",
                      {"action": "add", "label": label, "date": (today - timedelta(days=days)).isoformat()})
        from omniarmor_app.catalog import find_rule
        self.title = find_rule(RESTO, "date_marking").title

    def test_the_last_day_batch_is_on_home(self):
        page = self.client.get("/app").data.decode()
        attention = words(between(page, "data-needs-attention", "data-coming-due"))
        coming = words(page[page.index("data-coming-due"):])
        self.assertIn(f"{self.title} · Opened ham", attention)
        self.assertIn(f"{self.title} · Chicken salad", attention, "a warning item shows even when another item is blocked")
        self.assertIn("Due today · made or opened 6 days ago (day 7)", attention)
        self.assertIn(f"{self.title} · Soup base", coming)
        self.assertNotIn("Chicken salad", coming, "once, in the list it belongs to")

    def test_home_and_the_summary_list_the_same_items(self):
        page = self.client.get("/app").data.decode()
        home = re.findall(r'<span class="title">([^<]+)</span>', between(page, "data-needs-attention", "data-coming-due"))
        summary = self.client.get("/app/report/summary").data.decode()
        listed = re.findall(r"<strong>([^<]+)</strong>", between(summary, "data-summary-action", "data-summary-soon"))
        self.assertEqual(sorted(html.unescape(t) for t in home), sorted(html.unescape(t) for t in listed))
        self.assertEqual(len(home), 2)

    def test_pilot_s_list_has_each_item_with_its_days_and_date(self):
        page = self.client.get("/app/audit").data.decode()
        due = json.loads(html.unescape(re.search(r"data-due='([^']*)'", page).group(1)))
        salad = next(i for i in due if "Chicken salad" in i["title"])
        self.assertEqual(salad["title"], f"{self.title} · Chicken salad: due today")
        self.assertEqual((salad["level"], salad["days"], salad["due"]), ("soon", 0, self.today().isoformat()))
        ham = next(i for i in due if "Opened ham" in i["title"])
        self.assertEqual((ham["level"], ham["days"]), ("urgent", -3))
        soup = next(i for i in due if "Soup base" in i["title"])
        self.assertEqual((soup["level"], soup["days"]), ("info", 5))

    def test_most_urgent_first(self):
        page = self.client.get("/app").data.decode()
        days = [int(d) for d in re.findall(r'data-days="(-?\d+)"', between(page, "data-needs-attention", "data-coming-due"))]
        self.assertEqual(days, [-3, 0])   # the ham is on day 10, the salad on day 7


class TestHomeSaysItInTheSummarysWords(TodayCase):
    """Home said "35 days is over the 31-day limit"; the summary "4 days overdue · last done 35 days ago"."""

    def setUp(self):
        super().setUp()
        self.signup(industries=(PHARMACY,))
        self.change(PHARMACY, "exclusion_screening", date=(self.today() - timedelta(days=35)).isoformat())

    def test_home_uses_the_summary_line(self):
        page = self.client.get("/app").data.decode()
        attention = words(between(page, "data-needs-attention", "data-coming-due"))
        self.assertIn("4 days overdue · last done 35 days ago", attention)
        self.assertNotIn("35 days is over the 31-day limit", attention)
        summary = words(self.client.get("/app/report/summary").data.decode())
        self.assertIn("4 days overdue · last done 35 days ago", summary)

    def test_every_row_is_the_summary_s_own_line(self):
        client = self.app.test_client()
        client.get("/demo/business")
        page = client.get("/app").data.decode()
        home = re.findall(r"<span class=\"meta\" data-attention-detail>([^<]*)</span>", page)
        summary = client.get("/app/report/summary").data.decode()
        lines = re.findall(r'<span class="sum-detail">([^<]*)</span>', between(summary, "data-summary-action", "data-summary-soon"))
        self.assertTrue(home)
        self.assertEqual(sorted(home), sorted(lines))

    def test_the_template_reuses_the_summary_helper(self):
        with open(os.path.join(ROOT, "omniarmor_app", "templates", "app", "overview.html"), encoding="utf-8") as f:
            template = f.read()
        self.assertIn("{{ st.summary_detail }}", template)
        self.assertNotIn("{{ s.message }}", template)


# --- 5. First run ----------------------------------------------------------------------------------------------

class TestFirstRun(TodayCase):
    def test_the_welcome_links_to_the_time_zone_in_settings(self):
        page = self.signup() and self.client.get("/app/industry/1").data.decode()
        self.assertIn('Not where you are? <a href="/app/settings#workspace">Change it in Settings</a>.', page)

    def test_the_step_says_what_it_checks(self):
        self.signup(industries=(RESTO,))
        page = words(self.client.get("/app").data.decode())
        self.assertIn("Enter your first date : not done yet", page)
        self.assertNotIn("Set your first reminder", page)
        self.post(f"/app/industry/{RESTO}/rule/date_marking/entries",
                  {"action": "add", "label": "Soup base", "date": self.today().isoformat()})
        self.assertIn("Enter your first date : done", words(self.client.get("/app").data.decode()))


class TestVersion(unittest.TestCase):
    def test_version_and_changelog(self):
        from omniarmor_app.version import __version__
        self.assertEqual(__version__, "1.27.0")
        with open(os.path.join(ROOT, "CHANGELOG.md"), encoding="utf-8") as f:
            log = f.read()
        section = log[log.index("## 1.27.0"):log.index("## 1.26.0")]
        for said in ("Your password", "Needs attention", "4 days overdue · last done 35 days ago", "yearly", "this week",
                     "do first", "cookies", "Enter your first date", "Change it in Settings"):
            self.assertIn(said, section)
        with open(os.path.join(ROOT, "docs", "PILOT.md"), encoding="utf-8") as f:
            self.assertIn("**1.27.0**", f.read())


if __name__ == "__main__":
    unittest.main()
