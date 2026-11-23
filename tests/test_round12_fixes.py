"""1.23.0: what a strict twelfth review asked for.

One counting rule on Home, the Report and the summary (and food batches in Home's "Coming due"), a summary that
prints on one page, Pilot's own answers for the header button's words and the top Help how-tos, History in the
workspace's own time, family ranks spread evenly with the certificates in order, a real /pricing page, and
polish (three pictures a row, the robot on screen, "Which sentence uses" wrong answers, one "Don't add")."""

import html
import os
import re
import sys
import unittest
from datetime import timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_classroom_review import SchoolCase  # noqa: E402
from test_webapp import AppTestCase  # noqa: E402

from omniarmor_app.version import __version__  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESTO = 2


def read(*parts):
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as f:
        return f.read()


def words(page):
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", page)).split())


# --- 1. One counting rule ----------------------------------------------------------------------------------------

class TestOneCountingRule(AppTestCase):
    """The reviewer's Sams Taqueria: two food batches (one 9 days old, one due in 4 days) and two coolers (one at
    44°F, one at 38°F) on RestoArmor's 10 checks. Home said 10 checks, the summary 12, and Home's "Coming due"
    left out the batch due in 4 days."""

    def setUp(self):
        super().setUp()
        self.signup(industries=(RESTO,))
        with self.db() as conn:
            org = conn.execute("SELECT * FROM orgs").fetchone()
        from omniarmor_app.tracking import org_today
        today = org_today(org)
        url = f"/app/industry/{RESTO}/rule/%s/entries"
        self.post(url % "date_marking", {"action": "add", "label": "Pico de gallo",
                                         "date": (today - timedelta(days=8)).isoformat()})
        self.post(url % "date_marking", {"action": "add", "label": "Chicken tinga",
                                         "date": (today - timedelta(days=2)).isoformat()})
        self.post(url % "cold_holding", {"action": "add", "label": "Prep line cooler", "value": "44"})
        self.post(url % "cold_holding", {"action": "add", "label": "Walk-in", "value": "38"})

    def test_home_report_and_summary_agree(self):
        home = words(self.client.get("/app").data.decode())
        report = words(self.client.get("/app/report").data.decode())
        summary = words(self.client.get("/app/report/summary").data.decode())
        rule = "10 checks, 4 tracked items (food batches and fridges)."
        for name, text in (("home", home), ("report", report), ("summary", summary)):
            self.assertIn(rule, text, name)
        for text in (home, report):
            self.assertIn("2 blocked 0 warnings 0 cleared 8 without a reading", text)
        self.assertIn("0 of 10 checks current · 2 overdue or out of limits · 8 not recorded yet.", summary)
        self.assertIn("The 4 tracked items: 2 current · 2 overdue or out of limits.", summary)
        self.assertIn("0 current · 0 due soon · 2 overdue · 8 not recorded", summary)
        self.assertIn("2 checks (4 tracked items), most recently", summary)
        self.assertNotIn("of 12 checks", summary)

    def test_a_batch_due_soon_is_coming_due_on_home_too(self):
        page = self.client.get("/app").data.decode()
        block = words(page[page.index('id="coming-due"'):page.index("Your industries")])
        self.assertIn("Ready-to-eat food 7-day limit · Chicken tinga · RestoArmor Due in 4 days", block)
        summary = words(self.client.get("/app/report/summary").data.decode())
        self.assertIn("Ready-to-eat food 7-day limit · Chicken tinga · RestoArmor Due in 4 days", summary)

    def test_adding_a_batch_says_its_own_reminder_not_the_worst_one_s(self):
        from omniarmor_app.tracking import org_today
        with self.db() as conn:
            org = conn.execute("SELECT * FROM orgs").fetchone()
        today = org_today(org)
        got = self.post(f"/app/industry/{RESTO}/rule/date_marking/entries",
                        {"action": "add", "label": "Rice", "date": today.isoformat()}, follow_redirects=True)
        text = words(got.data.decode())
        self.assertIn("Rice added.", text)
        self.assertNotIn("It's overdue", text[text.index("Rice added."):])
        self.assertIn("Reminder set", text)

    def test_no_items_no_extra_line(self):
        client = self.app.test_client()
        self.signup(email="two@example.com", industries=(1,), client=client)
        self.assertNotIn("data-count-rule", client.get("/app").data.decode())
        self.assertNotIn("data-count-rule", client.get("/app/report/summary").data.decode())


# --- 2. The summary on one page --------------------------------------------------------------------------------

class TestSummaryPrintsOnOnePage(AppTestCase):
    def test_print_css_two_columns_and_no_room_for_the_tab_bar(self):
        css = read("omniarmor_app", "static", "app.css")
        block = css[css.index("/* 1.23.0: the summary prints on one Letter or A4 page"):]
        block = block[:block.index("/* Auth and public pages */")]
        self.assertIn(".sum-cols{columns:2", block)
        self.assertIn("@page{margin:12mm}", block)
        main = css[css.index(".topbar,.no-print,footer.site,.flashes,.tabbar,.companion"):]
        main = main[:main.index("\n}")]
        self.assertIn(".pilot-root", main)
        self.assertIn("padding-bottom:0!important", main)
        page = read("omniarmor_app", "templates", "app", "report_summary.html")
        self.assertIn('<div class="sum-cols">', page)

    def test_last_checks_capped_and_deadlines_say_days_left(self):
        client = self.app.test_client()
        client.get("/demo/business")
        page = client.get("/app/report/summary").data.decode()
        last = page[page.index("data-summary-last"):page.index("data-summary-who")]
        self.assertLessEqual(last.count("<li>"), 6)
        text = words(page)
        self.assertNotRegex(text, r"last reading \d+ (business )?days")

    def test_reading_words(self):
        import dataclasses
        from omniarmor_app.tracking import states_for_org
        self.signup(industries=(1, 2, 18, 28))
        with self.db() as conn:
            org = conn.execute("SELECT * FROM orgs").fetchone()
            states = states_for_org(conn, org)
        until = next(s for s in states if s.mode == "until")
        since = next(s for s in states if s.mode == "since" and s.rule.unit == "days")
        self.assertEqual(dataclasses.replace(until, value=41).reading_line, "41 days left")
        self.assertEqual(dataclasses.replace(until, value=-3).reading_line, "")
        self.assertEqual(dataclasses.replace(until, value=-3).reading_text, "3 days past due")
        self.assertEqual(dataclasses.replace(since, value=35).reading_line, "last done 35 days ago")
        self.assertEqual(dataclasses.replace(since, value=35).reading_text, "35 days ago")
        plain = next(s for s in states if s.mode is None and s.rule.unit == "°F")
        self.assertEqual(dataclasses.replace(plain, value=44).reading_line, "last reading 44°F")


# --- 4. History in the workspace's own time ---------------------------------------------------------------------

class TestHistoryInLocalTime(AppTestCase):
    def test_page_and_csv(self):
        from omniarmor_app import views
        self.signup()
        with self.db() as conn:
            conn.execute("UPDATE orgs SET timezone = 'America/Chicago'")
            conn.execute("UPDATE audit SET at = '2026-11-20T16:07:31+00:00'")
            conn.commit()
        page = self.client.get("/app/audit").data.decode()
        self.assertIn("When (Chicago time)", page)
        self.assertIn("data-audit-zone", page)
        self.assertIn("America/Chicago", page)
        self.assertIn('<span class="at-long">2026-11-20 10:07</span>', page)
        self.assertIn('<span class="at-short">20 Nov 10:07</span>', page)
        self.assertNotIn("UTC", words(page[page.index("data-audit-zone"):page.index("</table>")]))
        csv = self.client.get("/app/audit.csv").data.decode().splitlines()
        self.assertEqual(csv[0], "Time (America/Chicago),Person,Action,Industry,Check,Before,After,Summary")
        self.assertTrue(csv[1].startswith("2026-11-20T10:07:31-06:00,"), csv[1])
        self.assertEqual(views._short_moment("2026-11-20T16:07:31+00:00"), "20 Nov 16:07")
        summary = self.client.get("/app/report/summary").data.decode()
        self.assertRegex(words(summary), r"Made by OmniArmor on \d{4}-\d\d-\d\d \d\d:\d\d C[SD]T")


# --- 5. A family's ranks, and the certificates in order ---------------------------------------------------------

class TestRanksAndCertificates(unittest.TestCase):
    def test_family_ranks_are_evenly_spaced(self):
        from omniarmor_app import academy
        for t in academy.TRACK_LIST:
            for quests in (None, 1, 2, 5):
                ladder = academy.rank_ladder(t, quests)
                goals = [g for g, _ in ladder]
                total = t.reachable(quests)
                self.assertEqual(goals[0], 0)
                self.assertEqual(goals[-1], total)
                gaps = [b - a for a, b in zip(goals, goals[1:])]
                self.assertLessEqual(max(gaps) - min(gaps), 1, (t.key, quests, goals))
        self.assertEqual([g for g, _ in academy.rank_ladder(academy.TRACKS["launchpad"], 1)],
                         [0, 14, 29, 43, 57, 71, 86, 100])
        # The Classroom track keeps 1.19.0's ladder.
        self.assertEqual([g for g, _ in academy.rank_ladder(academy.CLASSROOM)], [0, 1, 3, 7, 17, 42, 102, 107])

    def test_future_owner_always_comes_first(self):
        from omniarmor_app import academy
        for t in academy.TRACK_LIST + [academy.CLASSROOM]:
            for quests in (None, 1, 3):
                goals = academy.certificate_goals(t, quests)
                top = t.reachable(quests)
                for done in range(0, top + 1):
                    got = academy.certificates_for(done, True, t, quests)
                    self.assertTrue(got, (t.key, done))
                    self.assertTrue(got[0].endswith("Future Owner") and "Silver" not in got[0], got)
                    self.assertEqual(got, [c for c in got if c in got][:len(got)])
                    self.assertEqual(academy.certificate_for(done, True, t, quests), got[-1])
                    order = [g[1] for g in goals][:len(got)]
                    self.assertEqual([c.replace(f"{t.name} ", "") if t.key != academy.DEFAULT_TRACK else c for c in got], order)
                self.assertEqual(academy.certificates_for(top, False, t, quests), [])
        # Passing the Challenge late, past Silver's goal, earns Future Owner and Silver at once, in that order.
        t = academy.TRACKS["launchpad"]
        silver = academy.certificate_goals(t, 1)[1][0]
        self.assertEqual(academy.certificates_for(silver, True, t, 1), ["Future Owner", "Silver Future Owner"])

    def test_the_result_page_shows_each_new_certificate_in_order(self):
        page = read("omniarmor_app", "templates", "academy", "result.html")
        self.assertIn("{% for c in new_certificates or [new_certificate] %}", page)
        self.assertIn("'You earned the' if loop.first else 'And the'", page)
        views = read("omniarmor_app", "academy_views.py")
        self.assertIn('new_certificates=[c for c in after["certificates"] if c not in before["certificates"]]', views)


# --- 6. /pricing ------------------------------------------------------------------------------------------------

class TestPricingPage(AppTestCase):
    def test_a_page_of_plan_cards_from_the_plan_data(self):
        from omniarmor_app import plans
        visitor = self.app.test_client()
        got = visitor.get("/pricing")
        self.assertEqual(got.status_code, 200)
        page = got.data.decode()
        text = words(page)
        for p in (plans.PRO, plans.PLUS):
            self.assertIn(f'data-plan="{p.key}"', page)
            self.assertIn(p.price, text)
        for p in plans.CLASSROOM_PLANS.values():
            self.assertIn(p.yearly_price, text)
        self.assertGreaterEqual(page.count("data-start-trial"), 4)
        self.assertIn('href="/signup"', page)
        self.assertIn('href="/signup?then=classes"', page)
        self.assertIn('href="/help#prices"', page)
        self.assertIn("Plans and prices", text)
        self.assertNotIn("<script>", page)
        self.assertNotIn("style=", page)
        # Help's prices stay, /prices comes here, the menu and the sitemap name it.
        self.assertIn('id="prices"', visitor.get("/help").data.decode())
        self.assertTrue(visitor.get("/prices").headers["Location"].endswith("/pricing"))
        self.assertIn('href="/pricing"', visitor.get("/").data.decode())
        self.assertIn("/pricing</loc>", visitor.get("/sitemap.xml").data.decode())


# --- 7. Polish ----------------------------------------------------------------------------------------------------

class TestPolish(SchoolCase):
    def test_three_pictures_a_row(self):
        css = read("omniarmor_app", "static", "academy.css")
        self.assertIn(".ac-avatars-big{display:grid;grid-template-columns:repeat(3,minmax(0,1fr))", css)
        self.assertIn(".ac-avatars-big .ac-avatar-pick svg{max-width:100%;height:auto}", css)

    def test_the_robot_s_corner_stays_free_on_a_computer(self):
        css = read("omniarmor_app", "static", "app.css")
        wide = css[css.index("@media (min-width:1100px){"):]
        self.assertIn(":root.pilot-on body.has-tabs:not(.lesson-view):has(> .pilot-root) main > .wrap{", wide)
        self.assertIn("padding-right:max(32px,calc(136px - max(0px,(100vw - 1396px) / 2)))", wide)

    def test_one_dont_add_per_name(self):
        self.teacher_signup()
        class_id = self.add_class()
        url = f"/app/academy/classes/{class_id}"
        for names, many in (("Ava Thompson", False), ("Ava Thompson\nNoah Kim", True)):
            self.post(f"{url}/students", {"names": names})
            page = self.client.get(url).data.decode()
            card = page[page.index("data-confirm-names"):]
            card = card[:card.index("</form>")]
            self.assertEqual(card.count("Don't add") + card.count("Don&#39;t add"), card.count("data-ask"), names)
            self.assertNotIn("data-skip-names", card)
            self.assertIn("Save my choices" if many else "Save my choice", card)
            self.post(f"{url}/students", {"confirmed": "1", "asked": "2" if many else "1", "pick-0": "", "pick-1": ""})
        self.assertEqual(self.students(class_id), {})


class TestSentenceWrongAnswersRead(unittest.TestCase):
    def test_wrong_answers_only_from_a_noun_s_place(self):
        from omniarmor_app import academy
        self.assertTrue(academy.noun_slot("Leo sent Mrs. Kim the ___, listing the fence work."))
        self.assertTrue(academy.noun_slot("The shop pays $900 rent every month: its biggest ___."))
        self.assertTrue(academy.noun_slot("Each of them is called the market's ___."))
        self.assertFalse(academy.noun_slot("Following every rule like that is ___."))
        self.assertFalse(academy.noun_slot("Sam paid on time, so the bank saw a high ___."))
        self.assertFalse(academy.noun_slot("The store went to court: ___."))
        seen = 0
        for t in (academy.TRACKS["launchpad"], academy.TRACKS["trailblazer"], academy.CLASSROOM):
            for w in t.worlds:
                for stage in range(1, t.stages(w) + 1):
                    for q in academy.quiz(t, w.number, stage, "Sams Taqueria", (2,), "review"):
                        if not q.prompt.startswith("Which sentence uses"):
                            continue
                        word = academy.asked_word(q)
                        scenes = {academy._in_gap(sc, word): sc for sc in academy.WORD_SCENES.values()}
                        for n, option in enumerate(q.options):
                            if n != q.answer:
                                self.assertTrue(academy.noun_slot(scenes[option]), (q.prompt, option))
                                seen += 1
        self.assertGreater(seen, 10)

    def test_the_checker_flags_a_bare_gap(self):
        sys.path.insert(0, os.path.join(ROOT, "tools"))
        import quiz_truth_review
        from omniarmor_app import academy
        q = academy.Question('Which sentence uses "Invoice" the right way?',
                             ["Leo sent Mrs. Kim the invoice, listing the fence work and the $50 she owed.",
                              academy._in_gap(academy.WORD_SCENES["Compliance"], "Invoice"),
                              academy._in_gap(academy.WORD_SCENES["Revenue"], "Invoice")], 0, "Invoice: ...", "choice")
        self.assertFalse(quiz_truth_review.sentence_reads(q, q.options[1]))
        self.assertTrue(quiz_truth_review.sentence_reads(q, q.options[2]))


class TestVersion(unittest.TestCase):
    def test_version_and_changelog(self):
        self.assertGreaterEqual(tuple(map(int, __version__.split("."))), (1, 23, 0))
        log = read("CHANGELOG.md")
        top = log[log.index("## 1.23.0"):log.index("## 1.22.0")]
        for said in ("tracked items", "one page", "No, we don't sell your data.", "time zone", "spaced evenly",
                     "Future Owner certificate always comes first", "/pricing", "three a row", "Don't add", "no Pilot"):
            self.assertIn(said, top)
        self.assertIn("**1.23.0** adds to `GLOBAL`", read("docs", "PILOT.md"))


if __name__ == "__main__":
    unittest.main()
