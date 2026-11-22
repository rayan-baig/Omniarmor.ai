"""1.18.0: what a strict eighth review asked for. Every Pilot welcome button
answers with no AI key, and Pilot wears OmniArmor's colours with nothing framed
behind the tucked robot; the Academy mixes its lesson formats (scenarios,
matching, sorting, true or false), asks the idea in other words instead of
copying its card, draws the map as a path and makes clearing a world (and a
boss round) a moment of its own; a child's map on a parent's device is the
kid's screen with "Grown-up? Hold to exit"; a shorter first screen on a phone;
counts that read right ("1 warning", "at 1 lesson"); and a "Security and your
data" page."""

import html
import json
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))
from test_classroom_review import SchoolCase  # noqa: E402
from test_parent_view import BASIC, ProgressCase  # noqa: E402
from test_webapp import AppTestCase  # noqa: E402

import quiz_truth_review  # noqa: E402
from omniarmor_app import academy, plans  # noqa: E402
from omniarmor_app.academy_bank.sorting import SORT_SETS  # noqa: E402
from omniarmor_app.academy_bank.word_ideas import KINDRED_WORDS, WORD_IDEAS  # noqa: E402
from omniarmor_app.reminders import build_digest  # noqa: E402
from omniarmor_app.version import __version__  # noqa: E402
from omniarmor_app.words import plural  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def read(*parts):
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as f:
        return f.read()


def words(page):
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", page)).split())


# --- 6. Counts that read right ------------------------------------------------------------------

class TestCounts(AppTestCase):
    def test_the_helper(self):
        self.assertEqual(plural(1, "warning"), "1 warning")
        self.assertEqual(plural(0, "warning"), "0 warnings")
        self.assertEqual(plural(2, "class"), "2 classes")
        self.assertEqual(plural(1, "entry"), "1 entry")
        self.assertEqual(plural(3, "entry"), "3 entries")
        self.assertEqual(plural(1200, "lesson"), "1,200 lessons")
        self.assertEqual(plural(2, "person", "people"), "2 people")

    def test_the_reminder_digest_says_1_warning(self):
        class State:
            def __init__(self, level):
                self.level = level
        org = {"name": "Acme"}
        everything = [State("BLOCKED"), State("WARNING"), State("CLEARED"), State("NONE")]
        _, body = build_digest(org, [], everything, "https://x.example", __import__("datetime").date(2026, 11, 22))
        self.assertIn("1 blocked, 1 warning, 1 cleared, 1 without a reading", body)
        self.assertNotIn("1 warnings", body)

    def test_the_overview_says_without_a_reading_not_unread(self):
        self.signup()
        page = self.client.get("/app").data.decode()
        self.assertNotIn("unread", page)
        self.assertRegex(words(page), r"\d+ blocked · \d+ warnings? · \d+ without a reading")

    def test_templates_use_the_filter(self):
        self.assertIn("{{ goal|plural('lesson') }}", read("omniarmor_app", "templates", "academy", "map.html"))
        self.assertNotIn("at {{ goal }} lessons", read("omniarmor_app", "templates", "academy", "map.html"))
        self.assertIn("counts.WARNING|plural('warning')", read("omniarmor_app", "templates", "app", "_totals.html"))
        self.assertIn("plural(", read("omniarmor_app", "reminders.py"))

    def test_a_lesson_never_says_1_days(self):
        for t in academy.ALL_TRACKS:
            for w in t.topic_worlds:
                for q in academy.family_pool(t, w.number, "Acme", (1, 18)) if t.key != academy.CLASSROOM_KEY else ():
                    self.assertNotRegex(q.prompt + " " + q.explain, r"\b1 days\b", q.prompt)


# --- 1. Pilot answers with no key --------------------------------------------------------------

class TestPilotFacts(AppTestCase):
    def facts(self, page, client=None):
        body = (client or self.client).get(page).data.decode()
        return json.loads(html.unescape(re.search(r"data-facts='([^']*)'", body).group(1)))

    def test_a_visitor_gets_the_trades_and_the_plans_words(self):
        facts = self.facts("/industries")
        paths = [t["path"] for t in facts["trades"]]
        self.assertIn("/for/salons-and-barbershops", paths)
        self.assertIn("/for/tattoo-and-piercing-studios", paths)
        self.assertTrue(all(p.startswith("/") for p in paths))
        self.assertEqual(len(paths), len(set(paths)))
        self.assertIn("compliance tracker", facts["pro_summary"])
        self.assertIn("Academy", facts["plus_summary"])
        self.assertEqual(facts["security_path"], "/security")
        self.assertEqual(facts["classroom_price"], plans.CLASSROOM.yearly_price)

    def test_the_schools_pages_get_the_week_plan(self):
        facts = self.facts("/classrooms")
        guide = academy.class_guide()
        self.assertEqual([w["title"] for w in facts["class_plan"]], [g["world"].title for g in guide])
        self.assertEqual(facts["class_plan"][0]["lessons"], guide[0]["lessons"])
        self.assertNotIn("class_plan", self.facts("/"))

    def test_report_rows_link_to_their_check(self):
        self.signup()
        page = self.client.get("/app/report").data.decode()
        self.assertRegex(page, r'<tr data-check="/app/industry/\d+#rule-[\w-]+"')

    def test_the_config_answers_every_welcome_button(self):
        js = read("omniarmor_app", "static", "pilot-omniarmor.js")
        for answer in ('ANSWER("bars", "Summarise my report", reportAnswer)', 'ANSWER("chat", "Add students", addStudentsAnswer)',
                       'ANSWER("spark", "Plan a week of lessons"', 'ANSWER("bars", "Explain this page", explainPageAnswer)',
                       'ANSWER("help", "Which checklist fits me?"', 'C("Which plan fits me?", A(planFitAnswer))'):
            self.assertIn(answer, js)
        self.assertNotIn('"explain-screen"', js)
        self.assertNotIn("_price)} a year", js)
        self.assertIn('themeClass: "omni-pilot"', js)


class TestPilotLooksLikeOmniArmor(unittest.TestCase):
    def test_the_theme_is_the_app_s_own_css(self):
        css = read("omniarmor_app", "static", "app.css")
        self.assertIn(".pilot-root.omni-pilot{--pilot-blue:#F7743A", css)
        self.assertIn(".pilot-root.omni-pilot .pilot-from-user{background:var(--blend)", css)

    def test_no_framed_box_behind_the_tucked_robot(self):
        css = read("omniarmor_app", "static", "app.css")
        self.assertNotIn("::after{\n    content:\"\";position:fixed;z-index:51", css)
        self.assertNotIn("width:72px;height:74px;border:1px solid var(--line)", css)
        corner = css[css.index("/* The helpers' corner on a phone."):]
        corner = corner[:corner.index("\n}\n")]
        self.assertIn("translate(calc(12px + var(--pilot-size) * .7 - var(--omni-slice))", corner)
        self.assertIn('".hero-shot", "details > summary"', read("omniarmor_app", "static", "pilot-omniarmor.js"))


# --- 2. Academy depth ------------------------------------------------------------------------------

class TestLessonFormats(unittest.TestCase):
    def kinds(self, t):
        found = set()
        for w in t.topic_worlds:
            for stage in range(1, t.stages(w) + 1):
                for q in academy.quiz(t, w.number, stage, "Acme", (1, 18), "x"):
                    found.add(q.look or q.kind)
        return found

    def test_every_track_mixes_its_formats(self):
        for t in academy.ALL_TRACKS:
            self.assertTrue({"choice", "scenario", "truefalse", "match", "sort"} <= self.kinds(t), t.name)

    def test_the_level_counts_stay(self):
        self.assertEqual([t.total for t in academy.ALL_TRACKS], [630, 890, 836, 764, 107])

    def test_a_match_is_one_question_with_one_right_code(self):
        t = academy.TRACKS["launchpad"]
        matches = [q for q in academy.family_pool(t, 2, "Acme", (1,)) if q.kind == "match"]
        self.assertGreaterEqual(len(matches), 4)
        for q in matches:
            self.assertEqual(len(q.options), 6)
            self.assertEqual(len(q.parts["codes"]), 6)
            code = [int(c) for c in q.parts["codes"][q.answer].split(",")]
            for word, idea in zip(q.parts["left"], code):
                self.assertEqual(WORD_IDEAS[word], q.parts["right"][idea])
            self.assertEqual(len(set(q.parts["left"])), 3)

    def test_a_sort_puts_each_item_in_its_bin(self):
        t = academy.CLASSROOM
        sorts = [q for n in (61, 34, 37) for q in academy.classroom_pool(n) if q.kind == "sort"]
        self.assertGreaterEqual(len(sorts), 6)
        truth = {text: b for _, _, _, items in SORT_SETS.values() for text, b, _ in items}
        for q in sorts:
            code = [int(c) for c in q.parts["codes"][q.answer].split(",")]
            self.assertEqual([truth[i] for i in q.parts["items"]], code)
            self.assertEqual(len(set(code)), 2, "never all in one bin")
            self.assertEqual(len(q.options), 8)
        self.assertEqual(t.key, "classroom")

    def test_the_sorting_facts_never_repeat_their_items(self):
        for key, (_, _, _, items) in SORT_SETS.items():
            self.assertGreaterEqual(len(items), 15, key)
            self.assertEqual(len({t for t, _, _ in items}), len(items), key)
            for text, b, why in items:
                self.assertIn(b, (0, 1))
                self.assertNotIn(text.lower(), why.lower(), text)

    def test_word_ideas_are_never_the_card_s_words(self):
        meanings = dict(academy.GLOSSARY)
        self.assertGreaterEqual(len(WORD_IDEAS), 100)
        for word, idea in WORD_IDEAS.items():
            self.assertIn(word, meanings, word)
            self.assertNotIn(quiz_truth_review._plain(idea), quiz_truth_review._plain(meanings[word]), word)
        for group in KINDRED_WORDS:
            self.assertTrue(group <= set(WORD_IDEAS), group)

    def test_the_words_quiz_asks_the_idea_in_other_words(self):
        t = academy.TRACKS["launchpad"]
        for q in academy.family_pool(t, 2, "Acme", (1,)):
            # 1.19.0: the words asked in a scene or a sentence are tested in test_round9_fixes.
            if q.kind == "choice" and q.prompt.startswith("What does"):
                word = re.match(r'What does "(.+)" mean\?', q.prompt).group(1)
                self.assertEqual(q.options[q.answer], WORD_IDEAS[word])
                self.assertIn(dict(academy.GLOSSARY)[word], q.explain)

    def test_scenarios_have_their_look(self):
        q = academy.Question("A customer pays you too much. What should you do?", ["a", "b", "c"], 0, "x")
        self.assertEqual(q.look, "scenario")
        self.assertEqual(academy.Question("What is revenue?", ["a", "b", "c"], 0, "x").look, "")

    def test_the_checker_flags_an_answer_copied_from_its_card(self):
        self.assertEqual(quiz_truth_review.review([("Sams Taqueria", (2,))], [academy.TRACKS["launchpad"]]), [])
        real = academy.story
        try:
            academy.story = lambda t, n, s, c, i: [("Card", " ".join(q.options[q.answer] for q in academy.quiz(t, n, s, c, i, "review")))]
            flags = quiz_truth_review.word_for_word_flags(academy.TRACKS["launchpad"], "Sams Taqueria", (2,))
        finally:
            academy.story = real
        self.assertTrue(flags)
        self.assertEqual({f[0] for f in flags}, {"word-for-word"})


class TestGamesOnThePage(ProgressCase):
    def test_the_quiz_draws_a_match_and_keeps_its_radio_codes(self):
        self.play(1, 1, right=5)
        self.play(2, 1, right=5)
        page = self.client.get("/app/academy/1/world/2/stage/2").data.decode()
        self.assertIn('data-game="match"', page)
        self.assertIn("data-match hidden", page)
        self.assertRegex(page, r'data-code="\d,\d,\d"')
        self.assertIn("Match each word to its idea.", page)
        js = read("omniarmor_app", "static", "academy.js")
        for said in ("function setupGame(q)", "function revealGame(q, verdict)", 'radio.dispatchEvent(new Event("change"'):
            self.assertIn(said, js)

    def test_a_game_is_graded_and_practised_like_any_question(self):
        self.play(1, 1, right=5)
        self.play(2, 1, right=5)
        result = self.play(2, 2, right=0)
        self.assertEqual(result.status_code, 200)
        with self.db() as conn:
            rows = [json.loads(r["question"]) for r in conn.execute("SELECT question FROM learner_mistakes")]
        games = [r for r in rows if r["kind"] == "match"]
        self.assertTrue(games)
        self.assertEqual(len(games[0]["parts"]["codes"]), 6)
        practice = self.client.get("/app/academy/1/practice").data.decode()
        self.assertIn('data-game="match"', practice)


class TestTheMapIsAPath(ProgressCase):
    def test_nodes_on_a_road(self):
        page = self.client.get("/app/academy/1").data.decode()
        self.assertIn('class="ac-worlds ac-path"', page)
        self.assertIn('<svg class="ac-road"', page)
        self.assertRegex(page, r'class="ac-world [^"]* p-[0-3]')
        self.assertIn("ac-world-node", page)
        css = read("omniarmor_app", "static", "academy.css")
        self.assertIn(".ac-road path{fill:none;stroke:var(--field)", css)
        self.assertIn("vector-effect:non-scaling-stroke", css)


class TestClearingAWorld(ProgressCase):
    def test_the_last_stage_clears_the_world_with_a_trophy_and_the_world_s_stars(self):
        stages = BASIC.stages(academy.world(1))
        for stage in range(1, stages):
            self.play(1, stage, right=5)
        page = self.play(1, stages, right=5).data.decode()
        self.assertIn("data-world-clear", page)
        self.assertIn("ac-trophy", page)
        self.assertIn("Boss beaten!", page)
        self.assertIn(f'data-world-stars="{stages * 3}"', page)
        self.assertIn(f"of {stages * 3} stars in Meet Your Company", words(page))
        self.assertIn("Next up: Business Words", words(page))
        # Playing it again is a normal stage.
        again = self.play(1, stages, right=5).data.decode()
        self.assertNotIn("data-world-clear", again)

    def test_a_normal_stage_has_the_normal_celebration(self):
        page = self.play(1, 1, right=5).data.decode()
        self.assertIn("data-celebrate", page)
        self.assertNotIn("data-world-clear", page)


# --- 4. A child's map on a parent's device ---------------------------------------------------

class TestTheChildsMapOnAParentsDevice(ProgressCase):
    def test_no_grown_up_tabs_menu_or_trial_banner(self):
        page = self.client.get("/app/academy/1").data.decode()
        self.assertIn("lesson-view", page[:page.index('<a class="skip"')])
        self.assertNotIn("data-nav-menu", page)
        self.assertNotIn("<span>Report</span>", page)
        self.assertNotIn("Free trial:", page)
        self.assertNotIn("All learners", page)
        self.assertIn("data-hold-exit", page)
        bar = page[page.index("data-lessonbar"):]
        bar = bar[:bar.index("</nav>")]
        self.assertIn('href="/app/academy"', bar)
        self.assertIn("Grown-up? Hold to exit", bar)
        # The grown-ups' part is folded away, there all the same.
        self.assertIn('<details class="ac-card ac-grownups" id="grown-ups"', page)

    def test_the_kid_s_other_pages_go_back_to_the_map(self):
        for path in ("/app/academy/1/friends", "/app/academy/1/track"):
            page = self.client.get(path).data.decode()
            self.assertIn("data-lessonbar", page, path)
            self.assertIn("Back to map", page, path)
            self.assertNotIn("data-nav-menu", page, path)

    def test_holding_is_needed(self):
        js = read("omniarmor_app", "static", "academy.js")
        self.assertIn("var HOLD_MS = 1500;", js)
        self.assertIn('exit.addEventListener("click", function (e) { e.preventDefault(); });', js)
        self.assertIn(".lessonbar .tab-hold.holding::after{transform:scaleX(1);transition:transform 1.5s linear}",
                      read("omniarmor_app", "static", "app.css"))


class TestAStudentsMapOnTheTeachersDevice(SchoolCase):
    def test_hold_to_exit_goes_back_to_the_class(self):
        self.teacher_signup()
        class_id = self.add_class()
        self.add_students(class_id, ["Ava"])
        with self.db() as conn:
            lid = conn.execute("SELECT id FROM learners WHERE class_id = ?", (class_id,)).fetchone()["id"]
        page = self.client.get(f"/app/academy/{lid}").data.decode()
        bar = page[page.index("data-lessonbar"):]
        self.assertIn(f'href="/app/academy/classes/{class_id}"', bar[:bar.index("</nav>")])


# --- 5. The first screen on a phone ---------------------------------------------------------

class TestTheFirstScreen(AppTestCase):
    def test_the_lead_is_one_short_line_and_the_rest_waits(self):
        page = self.client.get("/").data.decode()
        lead = re.search(r'<p class="lead">([^<]+)</p>', page).group(1)
        self.assertLessEqual(len(lead), 110, lead)
        self.assertIn("data-lead-more", page)
        css = read("omniarmor_app", "static", "app.css")
        self.assertIn(".hero .lead-more{order:2}", css)
        self.assertIn(".hero .cta-more{display:none}", css)


# --- 7. Security and your data ---------------------------------------------------------------

class TestSecurityPage(AppTestCase):
    def test_the_page_answers_the_trust_questions_from_the_settings(self):
        response = self.client.get("/security")
        self.assertEqual(response.status_code, 200)
        page = words(response.data.decode())
        for heading in ("Where your data lives", "Backups", "Who can see a student's name", "How to delete it",
                        "Questions, or something looks wrong"):
            self.assertIn(heading, page)
        self.assertIn(f"the newest {self.app.config['BACKUP_KEEP']} copies are kept", page)
        self.assertIn("first name or nickname only", page)
        self.assertIn("help@mtrxhorizyn.com", page)
        self.assertNotRegex(page, r"(?i)encrypted at rest|ISO 27001|SOC 2|HIPAA compliant")

    def test_it_is_linked_from_the_footer_privacy_sitemap_and_pilot(self):
        for path in ("/", "/help", "/privacy"):
            self.assertIn('href="/security"', self.client.get(path).data.decode(), path)
        self.assertIn("/security</loc>", self.client.get("/sitemap.xml").data.decode())
        self.assertIn("[Security and your data](/security)", read("omniarmor_app", "static", "pilot-omniarmor.js"))


class TestCore141(AppTestCase):
    def test_the_thirteen_core_files_are_1_4_1_and_the_robot_comes_crisp(self):
        folder = os.path.join(ROOT, "omniarmor_app", "static", "pilot")
        names = [n for n in os.listdir(folder) if n.endswith((".js", ".css"))]
        self.assertEqual(len(names), 13)
        for name in names:
            self.assertRegex(read("omniarmor_app", "static", "pilot", name).splitlines()[0], r"Pilot core 1\.4\.2 · ", name)
        for picture in ("pilot-robot-112.webp", "pilot-robot-168.webp", "pilot-robot-176.webp", "pilot-rest-body-112.webp",
                        "pilot-rest-head-168.webp", "pilot-rest-eyes-112.webp"):
            self.assertTrue(os.path.getsize(os.path.join(folder, picture)) > 500, picture)
        page = self.client.get("/").data.decode()
        self.assertRegex(page, r'data-robot-set="/static/pilot/pilot-robot-112\.webp\?v=\d+ 112w, ')
        for layer in ("body", "head", "eyes"):
            self.assertIn(f'data-rest-{layer}-set="/static/pilot/pilot-rest-{layer}-112.webp', page)
        panel = read("omniarmor_app", "static", "pilot", "pilot-panel.js")
        self.assertIn("pilot-pills-row", panel)   # the welcome's pills come back under an answer
        self.assertIn("LOCAL_STANDIN", read("omniarmor_app", "static", "pilot", "pilot-engine.js"))


class TestVersion(unittest.TestCase):
    def test_version(self):
        self.assertGreaterEqual(tuple(map(int, __version__.split("."))), (1, 18, 0))
        self.assertIn("## 1.18.0", read("CHANGELOG.md"))


if __name__ == "__main__":
    unittest.main()
