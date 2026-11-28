"""1.29.0: what a strict seventeenth review asked for.

Home said "No tracked deadlines" in the next 60 days beside a warning due tomorrow; now nothing *else* comes due, as
the summary says. On a phone a signed-in page keeps Pilot a tap away in the menu, and Armo's count shows on the Menu
button while he steps away from the page's words; he comes back out only once the page is still. Pilot's tag carries
the workspace's own trial days left and where a school pays by invoice. History names the zone once, a teacher's
welcome says nothing about due dates, a yes-or-no check's line under Needs attention doesn't repeat its title, the
trade demos finish Getting started, and the home pictures keep their 4:5 on a phone. Pilot's answers with no key are
in tests/js (tests/test_pilot.py runs them)."""

import html
import json
import os
import re
import sys
import unittest
from datetime import timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_classroom_review import SchoolCase  # noqa: E402
from test_webapp import AppTestCase  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESTO = 2


def words(page):
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", page)).split())


def read(*parts):
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as f:
        return f.read()


def section(page, marker):
    start = page.index(marker)
    return page[start:page.index("</section>", start)]


def pilot_facts(page):
    tag = re.search(r'<script[^>]*id="pilot-core"[^>]*>', page, re.S).group(0)
    return json.loads(html.unescape(re.search(r"data-facts='([^']*)'", tag).group(1)))


# --- 2. Home: nothing else comes due --------------------------------------------------------------------------------

class TestHomeSaysNothingElseComesDue(AppTestCase):
    def setUp(self):
        super().setUp()
        self.signup(industries=(RESTO,))

    def today(self):
        from omniarmor_app.tracking import org_today
        with self.db() as conn:
            return org_today(conn.execute("SELECT * FROM orgs").fetchone())

    def test_with_a_dated_item_under_needs_attention_it_says_nothing_else(self):
        # A food batch on its last day: a warning, due today, under Needs attention; nothing else has a date.
        self.post(f"/app/industry/{RESTO}/rule/date_marking/entries",
                  {"action": "add", "label": "Soup base", "date": (self.today() - timedelta(days=6)).isoformat()})
        page = self.client.get("/app").data.decode()
        attention = section(page, "data-needs-attention")
        self.assertRegex(attention, r'data-level="WARNING" data-days="0"')
        coming = words(section(page, "data-coming-due"))
        self.assertIn("Nothing else comes due in the next 60 days.", coming)
        self.assertNotIn("No tracked deadlines", coming)

    def test_the_template_keeps_no_tracked_deadlines_only_where_nothing_is_dated(self):
        page = read("omniarmor_app", "templates", "app", "overview.html")
        self.assertIn("selectattr('days_left', 'ne', none)", page)
        self.assertIn("{{ 'Nothing else comes due' if dated_now else 'No tracked deadlines' }} in the next 60 days.", page)
        self.assertIn('<p class="empty" data-nothing-else>Nothing else comes due in the next 60 days.</p>', page)
        # A fresh workspace still invites its first date.
        self.assertNotIn("Nothing else comes due", words(self.client.get("/app").data.decode()))

    def test_pilot_s_home_answer_says_the_same(self):
        js = read("omniarmor_app", "static", "pilot-omniarmor.js")
        self.assertIn('(rows.length ? "Nothing else comes due in the next 60 days." : "Nothing is coming due in the next 60 days.")', js)


# --- 3. On a phone: Pilot in the menu, Armo's count on the Menu button --------------------------------------------

class TestPilotAndArmoOnAPhone(AppTestCase):
    def test_ask_pilot_is_in_the_menu_on_a_signed_in_page(self):
        self.signup(industries=(RESTO,))
        page = self.client.get("/app").data.decode()
        drop = page[page.index('<div class="nav-drop">'):]
        drop = drop[:drop.index("</div>")]
        self.assertIn('<button type="button" class="nav-pilot" data-nav-pilot hidden>Ask Pilot</button>', drop)
        self.assertIn('data-armo-menu-link hidden', drop)
        self.assertIn('<b class="menu-count" data-armo-menu-count hidden></b>', page)
        # Only in the phone's menu, not in the computer's links (nav-wide).
        wide = page[page.index('<div class="nav-wide">'):page.index('<details class="nav-menu"')]
        self.assertNotIn("data-nav-pilot", wide)
        # Where there is no Pilot (Armo's own page) there is no button for it; a visitor has neither.
        self.assertNotIn("data-nav-pilot", self.client.get("/app/armo").data.decode())
        visitor = self.app.test_client().get("/").data.decode()
        self.assertIsNone(re.search(r"\bdata-nav-pilot\b|\bdata-armo-menu-count\b", visitor))

    def test_the_menu_button_opens_pilot_and_armo_s_count_follows_him(self):
        js = read("omniarmor_app", "static", "page.js")
        self.assertIn('menu.querySelector("[data-nav-pilot]")', js)
        self.assertIn("window.Pilot.open();", js)
        armo = read("omniarmor_app", "static", "armo.js")
        sync = armo[armo.index("function syncMenu()"):armo.index("// Click Armo")]
        self.assertIn('var away = root.classList.contains("armo-away") && state.needs > 0;', sync)
        self.assertIn("menuCount.hidden = !away;", sync)
        self.assertIn("menuLink.hidden = !away;", sync)
        self.assertIn("syncMenu();", armo[armo.index("function keepClear("):armo.index('window.addEventListener("resize"')])
        css = read("omniarmor_app", "static", "app.css")
        self.assertIn(".menu-count{position:absolute;top:-8px;right:-8px;", css)
        self.assertIn(".menu-count[hidden]{display:none}", css)

    def test_armo_comes_back_out_only_once_the_page_is_still(self):
        js = read("omniarmor_app", "static", "armo.js")
        clear = js[js.index("function keepClear("):js.index('window.addEventListener("resize"')]
        self.assertIn("var CALM_MS = 450;", js)
        self.assertIn('window.addEventListener("scroll", function () { lastScroll = Date.now(); }, { passive: true });', clear)
        self.assertIn("if (PLACES.indexOf(place()) < PLACES.indexOf(was) && still < CALM_MS) {", clear)
        self.assertIn("calmTimer = setTimeout(keepClear, CALM_MS - still + 20);", clear)
        # Stepping away is still at once, from his full size.
        self.assertIn('root.classList.remove("armo-tucked", "armo-away");', clear)
        self.assertIn('if (root.classList.contains("armo-tucked") && busy()) root.classList.add("armo-away");', clear)


# --- 4. Pilot's facts: trial days left, the invoice address, the trades -------------------------------------------

class TestPilotFacts(SchoolCase):
    def test_a_business_tag_has_its_trial_days_left_and_the_trades(self):
        self.signup(industries=(RESTO,))
        facts = pilot_facts(self.client.get("/app").data.decode())
        self.assertEqual(facts["trial_days_left"], self.app.config["ACADEMY_TRIAL_DAYS"])
        self.assertEqual(facts["plan_name"], "")
        self.assertIn({"name": "Salons and barbershops", "path": "/for/salons-and-barbershops"}, facts["trades"])
        self.assertIn("@", facts["invoice_email"])

    def test_a_paid_plan_is_named_and_a_visitor_has_no_days_of_their_own(self):
        self.signup(industries=(RESTO,))
        with self.db() as conn:
            conn.execute("UPDATE orgs SET academy_status = 'active', plan = 'pro', academy_trial_ends = created_at")
            conn.commit()
        facts = pilot_facts(self.client.get("/app").data.decode())
        self.assertEqual((facts["trial_days_left"], facts["plan_name"]), (0, "Pro"))
        visitor = pilot_facts(self.app.test_client().get("/").data.decode())
        self.assertNotIn("trial_days_left", visitor)

    def test_a_teacher_s_days_are_the_class_trial_s(self):
        self.teacher_signup()
        facts = pilot_facts(self.client.get("/app/academy/classes").data.decode())
        self.assertEqual(facts["trial_days_left"], self.app.config["CLASSROOM_PILOT_DAYS"])


# --- 5. Polish ---------------------------------------------------------------------------------------------------

class TestHistoryNamesTheZoneOnce(AppTestCase):
    def test_utc_is_said_once(self):
        self.signup(industries=(RESTO,))
        with self.db() as conn:
            conn.execute("UPDATE orgs SET timezone = 'UTC'")
            conn.commit()
        page = words(self.client.get("/app/audit").data.decode())
        self.assertIn("Times are UTC, this workspace's time zone.", page)
        self.assertNotIn("UTC (UTC)", page)

    def test_a_named_zone_still_gives_its_name(self):
        self.signup(industries=(RESTO,))
        page = words(self.client.get("/app/audit").data.decode())
        self.assertRegex(page, r"Times are New York time \(America/New_York, E[SD]T now\), this workspace's time zone\.")


class TestTeacherWelcome(SchoolCase):
    def test_no_line_about_due_dates_for_a_teacher(self):
        self.teacher_signup()
        page = words(self.client.get("/app/academy/classes").data.decode())
        self.assertIn("Welcome to OmniArmor. Your free", page)
        self.assertNotIn("roll over at midnight", page)

    def test_a_business_still_hears_about_its_time_zone(self):
        self.signup(industries=(RESTO,))
        page = words(self.client.get(f"/app/industry/{RESTO}").data.decode())
        self.assertIn("Due dates roll over at midnight New York time (America/New_York).", page)


class TestNeedsAttentionSaysTheTitleOnce(AppTestCase):
    def test_a_yes_or_no_check_s_line_doesn_t_repeat_its_title(self):
        from omniarmor_app.catalog import find_rule
        self.signup(industries=(RESTO,))
        rule = find_rule(RESTO, "no_pests")
        self.change(RESTO, "no_pests", answer="yes")
        page = self.client.get("/app").data.decode()
        row = re.search(r'<a class="row" data-level="BLOCKED"[^>]*#rule-no_pests">.*?</a>', page, re.S).group(0)
        detail = words(re.search(r"<span class=\"meta\" data-attention-detail>(.*?)</span>", row, re.S).group(1))
        self.assertEqual(detail, f"{rule.action} · last reading Yes")
        self.assertNotIn(f"{rule.title}:", detail)
        self.assertIn(rule.title, words(row), "the title still heads the row")


class TestTradeDemosFinishGettingStarted(AppTestCase):
    def test_every_trade_demo_opens_without_getting_started(self):
        from omniarmor_app.demo_mode import TRADE_DEMOS
        for kind in list(TRADE_DEMOS) + ["business"]:
            client = self.app.test_client()
            self.assertEqual(client.get(f"/demo/{kind}").status_code, 302, kind)
            page = client.get("/app").data.decode()
            self.assertNotIn("data-getting-started", page, kind)
            self.assertNotIn("Getting started", words(page), kind)

    def test_the_owner_s_reminder_emails_are_chosen(self):
        src = read("omniarmor_app", "demo_mode.py")
        fill = src[src.index("def _fill_trade("):src.index("def _fill_classroom(")]
        self.assertIn('conn.execute("UPDATE users SET reminders_chosen_at = ? WHERE id = ?", (created, owner))', fill)


class TestHomePicturesOnAPhone(unittest.TestCase):
    def test_the_steps_keep_4_by_5(self):
        css = read("omniarmor_app", "static", "app.css")
        self.assertIn(".how-steps .shot img{aspect-ratio:4/5;object-fit:cover;object-position:top}", css)
        self.assertNotIn(".how-steps .shot img{aspect-ratio:1/1}", css)

    def test_the_report_picture_is_the_current_one(self):
        from omniarmor_app.shots import _size
        path = os.path.join(ROOT, "omniarmor_app", "static", "shots", "biz-report.webp")
        self.assertEqual(_size(path), (960, 1200))
        with open(path, "rb") as f:
            self.assertEqual(f.read(4), b"RIFF")


class TestVersion(unittest.TestCase):
    def test_version_and_changelog(self):
        from omniarmor_app.version import __version__
        self.assertEqual(__version__, "1.29.0")
        log = read("CHANGELOG.md")
        self.assertIn("## 1.29.0 (28 November 2026)", log)
        self.assertLess(log.index("## 1.29.0"), log.index("## 1.28.0"))


if __name__ == "__main__":
    unittest.main()
