"""1.22.0: what a strict eleventh review asked for, and Pilot core 1.4.3.

History as cards on a phone, a family's rank ladder and certificates scaled on
the lessons its workspace really has (and a sixth rank whose name isn't the
certificate's), a class's students picking their own starting picture, an
inspection-ready summary from the Report, /pricing, "Due in" on Home, one
definition per Business Words term (a quiz checker rule), and the core 1.4.3
pins. Pilot's own answers (the no-key reply, typed button words, the school
cancel answer, the new match words) are checked in Node
(tests/js/omniarmor-pilot.test.js, run by tests/test_pilot.py)."""

import html
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))
from test_classroom_review import SchoolCase  # noqa: E402
from test_webapp import AppTestCase  # noqa: E402

import quiz_truth_review  # noqa: E402
from omniarmor_app import academy, views  # noqa: E402
from omniarmor_app.version import __version__  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def read(*parts):
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as f:
        return f.read()


def words(page):
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", page)).split())


# --- 0. Pilot core 1.4.3 -------------------------------------------------------------------------------------

class TestCore143(unittest.TestCase):
    def test_every_core_file_is_1_4_3(self):
        folder = os.path.join(ROOT, "omniarmor_app", "static", "pilot")
        names = sorted(n for n in os.listdir(folder) if n.endswith((".js", ".css")))
        self.assertEqual(len(names), 13)
        for name in names:
            self.assertRegex(read("omniarmor_app", "static", "pilot", name).splitlines()[0], r"Pilot core 1\.4\.3 · ", name)
        self.assertIn("function noKeyItems(", read("omniarmor_app", "static", "pilot", "pilot-panel.js"))

    def test_the_config_uses_the_core_s_no_key_reply_and_drops_1_20_0_s_workaround(self):
        config = read("omniarmor_app", "static", "pilot-omniarmor.js")
        self.assertNotIn("noKeyReply", config)
        self.assertNotIn("shownChips(keyed)", config)
        # The answers on every page stay: 1.4.3 has no way to give the core answers that are never buttons.
        self.assertIn("function globalFor(", config)
        for said in ('"sell"', '"refund"', '"privacy"', "LEGAL_WORDS"):
            self.assertIn(said, config)


# --- 1. History on a phone ----------------------------------------------------------------------------------

class TestHistoryCards(AppTestCase):
    def test_the_short_time(self):
        self.assertEqual(views._short_moment("2026-11-20T16:07:31+00:00"), "20 Nov 16:07")
        self.assertEqual(views._short_moment("2026-01-05T09:03:00+00:00"), "5 Jan 09:03")
        self.assertEqual(views._short_moment("not a time"), "not a time")

    def test_each_entry_is_a_card_on_a_phone_and_the_csv_is_unchanged(self):
        self.signup()
        page = self.client.get("/app/audit").data.decode()
        self.assertIn('class="audit-cards"', page)
        self.assertIn('class="at-short"', page)
        self.assertIn("<td data-pilot-private>Pat Owner</td>", page)
        self.assertRegex(page, r'<span class="at-short">\d{1,2} [A-Z][a-z]{2} \d\d:\d\d</span>')
        css = read("omniarmor_app", "static", "app.css")
        phone = css[css.index("/* History on a phone (1.22.0)"):]
        phone = phone[:phone.index("/* Auth and public pages */")]
        self.assertIn("@media screen and (max-width:640px)", phone)
        self.assertIn("table.audit-cards thead{display:none}", phone)
        self.assertIn("table.audit-cards .audit-change{order:4;flex-basis:100%", phone)
        csv = self.client.get("/app/audit.csv").data.decode().splitlines()[0]
        self.assertEqual(csv, "Time (America/New_York),Person,Action,Industry,Check,Before,After,Summary")  # 1.23.0: local


# --- 2. A family's ranks ---------------------------------------------------------------------------------------

class TestRanksOnWhatTheWorkspaceHas(unittest.TestCase):
    def test_no_rank_or_certificate_past_the_levels_a_workspace_has(self):
        for t in academy.TRACK_LIST:
            for quests in (None, 0, 1, 2, 3, 5):
                top = t.reachable(quests)
                self.assertEqual(top, t.lessons + (quests or 0) * t.industry_stages, t.key)
                ladder = academy.rank_ladder(t, quests)
                goals = [g for g, _ in ladder]
                self.assertEqual(goals, sorted(set(goals)), (t.key, quests))
                self.assertEqual(ladder[-1], (top, "Tycoon"), (t.key, quests))
                self.assertEqual(academy.rank_for(top, t, quests), "Tycoon")
                certificates = academy.certificate_goals(t, quests)
                self.assertLessEqual(max(g for g, _ in certificates), top)
                # Passing the Challenge (the first lesson of every world, and itself) earns the first one, not Silver.
                self.assertEqual(academy.certificate_for(len(t.topics) + 1, True, t, quests).split()[-2:], ["Future", "Owner"])
                self.assertGreater(certificates[1][0], len(t.topics) + 1, (t.key, quests))
                self.assertTrue(academy.certificate_for(top, True, t, quests).endswith("Platinum Future Owner"))
        # 1.21.0's Launchpad ladder went on to 630 levels; a workspace with one industry has 100.
        self.assertEqual(academy.TRACKS["launchpad"].reachable(1), 100)
        self.assertEqual(academy.rank_ladder(academy.TRACKS["launchpad"], 1)[-1], (100, "Tycoon"))

    def test_the_classroom_ladder_is_the_one_1_19_0_gave_it(self):
        self.assertEqual([g for g, _ in academy.rank_ladder(academy.CLASSROOM)], [0, 1, 3, 7, 17, 42, 102, 107])
        self.assertEqual(academy.rank_ladder(academy.CLASSROOM, 3), academy.rank_ladder(academy.CLASSROOM))

    def test_rank_and_certificate_names_never_clash(self):
        ranks = [title for _, title in academy.RANKS]
        certificates = [title for _, title in academy.CERTIFICATES]
        self.assertIn("Chief Executive", ranks)
        self.assertNotIn("Future Owner", ranks)
        for c in certificates:
            for r in ranks:
                self.assertNotIn(r, c, (r, c))


class TestTheMapListsOnlyReachableRanks(AppTestCase):
    def test_a_family_s_map(self):
        self.signup(industries=(2,))
        self.post("/app/academy/learners", {"nickname": "Sam", "avatar": "rocket", "armo": "sweet"})
        with self.db() as conn:
            lid = conn.execute("SELECT id FROM learners").fetchone()[0]
        page = self.client.get(f"/app/academy/{lid}").data.decode()
        t = academy.TRACKS[academy.DEFAULT_TRACK]
        goals = [int(n.replace(",", "")) for n in re.findall(r"at ([\d,]+) lessons?</span>", page)]
        self.assertTrue(goals)
        self.assertLessEqual(max(goals), t.reachable(1))
        self.assertIn(f"Tycoon, at {t.reachable(1)} lessons", page)


# --- 3. A student's own picture --------------------------------------------------------------------------------

class TestAStudentPicksTheirPicture(SchoolCase):
    def setUp(self):
        super().setUp()
        self.teacher_signup()
        self.class_id = self.add_class()
        self.add_students(self.class_id, ["Maya"])
        self.maya = self.students(self.class_id)["Maya"]
        with self.db() as conn:
            conn.execute("INSERT INTO join_codes (learner_id, code, expires_at) VALUES (?, 'KID-ABCD2345', '2999-01-01T00:00:00+00:00')",
                         (self.maya["id"],))
            conn.commit()
        self.kid = self.app.test_client()

    def join(self):
        self.kid.get("/kids")
        return self.post("/kids", {"code": "KID-ABCD2345"}, client=self.kid)

    def test_joining_opens_the_picture_choice_first(self):
        joined = self.join()
        self.assertEqual(joined.status_code, 302)
        self.assertTrue(joined.headers["Location"].endswith("/kids/picture"))
        page = self.kid.get("/kids/picture").data.decode()
        self.assertEqual(page.count('type="radio" name="avatar"'), len(academy.AVATARS))
        self.assertIn(f'value="{self.maya["avatar"]}" checked', page)
        self.assertNotIn('type="file"', page)
        self.assertNotIn("photo", page.lower().replace("never a photo", ""))
        for never in ('id="pilot-core"', "pilot-omniarmor.js", "armo.js", 'class="companion'):
            self.assertNotIn(never, page)

    def test_the_pick_is_kept_and_only_preset_pictures(self):
        self.join()
        bad = self.post("/kids/picture", {"avatar": "https://example.com/me.png"}, client=self.kid)
        self.assertEqual(bad.status_code, 400)
        done = self.post("/kids/picture", {"avatar": "planet"}, client=self.kid)
        self.assertEqual(done.status_code, 302)
        with self.db() as conn:
            self.assertEqual(conn.execute("SELECT avatar FROM learners WHERE id = ?", (self.maya["id"],)).fetchone()[0], "planet")
        # Their class page offers the choice again; the teacher's view of it doesn't.
        mine = self.kid.get(f"/app/academy/{self.maya['id']}/class").data.decode()
        self.assertIn("data-change-picture", mine)
        teacher = self.client.get(f"/app/academy/{self.maya['id']}/class").data.decode()
        self.assertNotIn("data-change-picture", teacher)

    def test_no_kid_no_picture_page(self):
        self.assertTrue(self.app.test_client().get("/kids/picture").headers["Location"].endswith("/kids"))
        self.assertEqual(self.post("/kids/picture", {"avatar": "planet"}).status_code, 302)
        with self.db() as conn:
            self.assertEqual(conn.execute("SELECT avatar FROM learners WHERE id = ?", (self.maya["id"],)).fetchone()[0],
                             self.maya["avatar"])

    def test_the_ladder_s_pictures_are_big_enough_to_see(self):
        page = read("omniarmor_app", "templates", "academy", "map.html")
        self.assertIn("avatar(summary.learner.avatar, avatars, 54, loop.index0)", page)
        css = read("omniarmor_app", "static", "academy.css")
        self.assertIn(".ac-evolve{list-style:none;display:grid;grid-template-columns:repeat(8,minmax(0,54px))", css)
        self.assertIn("@media (max-width:479px){.ac-evolve{grid-template-columns:repeat(4,minmax(0,54px))", css)


# --- 4. The inspection-ready summary --------------------------------------------------------------------------

class TestInspectionSummary(AppTestCase):
    def test_one_page_from_the_records(self):
        client = self.app.test_client()
        client.get("/demo/business")
        report = client.get("/app/report").data.decode()
        self.assertIn('href="/app/report/summary"', report)
        page = client.get("/app/report/summary").data.decode()
        text = words(page)
        for said in ("Inspection-ready summary", "Where things stand", "Needs action", "Due in the next 30 days",
                     "Last checks recorded", "Who recorded the current readings", "Reviewed by:",
                     "not an inspection result, a certificate or legal advice"):
            self.assertIn(said, text)
        for section in ("data-summary-now", "data-summary-action", "data-summary-soon", "data-summary-last",
                        "data-summary-who", "data-print"):
            self.assertIn(section, page)
        for claim in ("compliant", "passed inspection", "guarantee", "certifies"):
            self.assertNotIn(claim, text.lower())
        # The totals are the report's own.
        cleared = re.search(r"<b>(\d+)</b>cleared", report)
        self.assertIsNotNone(cleared)
        self.assertRegex(text, r"\d+ of \d+ checks current")
        # The names of who recorded are marked private for Pilot.
        self.assertIn('<ul class="sum-list" data-pilot-private>', page)
        self.assertIn("ep in ('app.report', 'app.report_summary')", read("omniarmor_app", "templates", "base.html"))

    def test_signed_out_goes_to_sign_in(self):
        self.assertEqual(self.app.test_client().get("/app/report/summary").status_code, 302)


# --- 5. Small things ---------------------------------------------------------------------------------------------

class TestSmallThings(AppTestCase):
    def test_pricing_goes_to_the_prices(self):
        visitor = self.app.test_client()
        # 1.23.0: /pricing is a page of its own (tests/test_round12_fixes.py); /prices goes there.
        self.assertEqual(visitor.get("/pricing").status_code, 200)
        got = visitor.get("/prices")
        self.assertEqual(got.status_code, 301)
        self.assertTrue(got.headers["Location"].endswith("/pricing"))
        self.assertIn('id="prices"', visitor.get("/help").data.decode())

    def test_home_says_due_not_a_second_in(self):
        page = read("omniarmor_app", "templates", "app", "overview.html")
        self.assertIn("<span class=\"meta mono\" data-due-when>{{ st.due_text }} · {{ st.due_label }}</span>", page)
        self.assertNotIn("{{ s.due_in }} · {{ s.due_label }}", page)
        client = self.app.test_client()
        client.get("/demo/business")
        home = client.get("/app").data.decode()
        block = home[home.index('id="coming-due"'):]
        for when in re.findall(r"data-due-when>([^<·]+)·", block):
            self.assertTrue(when.strip().startswith(("Due ", "due ")) or "overdue" in when, when)


class TestOneDefinitionPerWord(unittest.TestCase):
    def test_the_checker_finds_nothing_today(self):
        self.assertEqual([f for f in quiz_truth_review.review(quiz_truth_review.COMPANIES[:1]) if f[0] == "definition"], [])

    def test_it_flags_a_card_in_other_words(self):
        ok = quiz_truth_review._defined_as_the_word_bank
        self.assertFalse(ok("Profit", "Profit is what's left: revenue minus costs. Healthy businesses make a profit."))
        self.assertTrue(ok("Profit", "Profit is the money left over after paying all the costs: revenue minus costs."))
        self.assertTrue(ok("Profit", "The money left over after paying all the costs."))
        self.assertFalse(ok("Promotion", "A promotion is a special deal that gives people a reason to try you now."))
        self.assertTrue(ok("Budget", "A budget is a plan for how much money to spend on each thing, made before you buy."))

    def test_the_cards_say_the_word_bank_s_words(self):
        glossary = dict(academy.GLOSSARY)
        for t in (academy.TRACKS["trailblazer"], academy.CLASSROOM):
            for w in t.worlds:
                if w.kind == "industry":
                    continue
                for title, body in academy.story(t, w.number, 1, "Sams Taqueria", (2,)):
                    if title in glossary:
                        self.assertTrue(quiz_truth_review._defined_as_the_word_bank(title, body), (w.key, title, body))


class TestVersion(unittest.TestCase):
    def test_version_and_changelog(self):
        self.assertGreaterEqual(tuple(map(int, __version__.split("."))), (1, 22, 0))
        log = read("CHANGELOG.md")
        top = log[log.index("## 1.22.0"):log.index("## 1.21.0")]
        for said in ("core 1.4.3", "History", "Chief Executive", "picture", "Inspection-ready summary", "/pricing",
                     "Due in", "Word Bank", "no Pilot"):
            self.assertIn(said, top)


if __name__ == "__main__":
    unittest.main()
