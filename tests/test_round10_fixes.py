"""1.21.0: what a strict tenth review asked for. The orange gradient where a
computer's side bar can see it, a class's growing picture with something new
at every rank and a bigger moment for clearing a world, lessons whose matching
game and questions teach different words (with short sentences and a picture
in each scene), Home's "Needs attention" by urgency with a line on early
policy warnings, and pop-ups and helpers that keep off the page's words.
Pilot's answers on every page are checked in Node
(tests/js/omniarmor-pilot.test.js, run by tests/test_pilot.py)."""

import html
import os
import re
import sys
import unittest
from datetime import date, timedelta
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))
from test_classroom_review import SchoolCase  # noqa: E402
from test_parent_view import ProgressCase  # noqa: E402
from test_webapp import AppTestCase  # noqa: E402

import quiz_truth_review  # noqa: E402
from omniarmor_app import academy, views  # noqa: E402
from omniarmor_app.academy_bank.word_use import WORD_SCENES, scene_picture  # noqa: E402
from omniarmor_app.version import __version__  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def read(*parts):
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as f:
        return f.read()


def words(page):
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", page)).split())


# --- 1. The gradient the side bar uses ------------------------------------------------------------------

class TestTheGradientIsAlwaysThere(AppTestCase):
    def test_its_own_svg_outside_anything_hidden(self):
        visitor = self.app.test_client()
        self.signup()
        for path in ("/app", "/app/report", "/"):
            page = (visitor if path == "/" else self.client).get(path).data.decode()
            self.assertEqual(page.count('id="blend"'), 1, path)
            # In its own small svg straight under <body>, before the top bar (hidden on a computer when signed in).
            body = page[page.index("<body"):]
            defs = body.index('id="blend"')
            self.assertLess(defs, body.index('<header class="topbar"'), path)
            svg = body[body.rindex("<svg", 0, defs):defs]
            self.assertIn('class="svg-defs"', svg, path)
            self.assertNotIn("hidden", svg.replace("aria-hidden", ""), path)
        css = read("omniarmor_app", "static", "app.css")
        rule = re.search(r"\.svg-defs\{[^}]*\}", css).group(0)
        self.assertNotIn("display:none", rule)
        self.assertIn("width:0", rule)
        # The logo in the top bar no longer carries it.
        base = read("omniarmor_app", "templates", "base.html")
        self.assertNotIn("logo_mark(defs", base)
        self.assertNotIn("logo_mark(false)", base)


# --- 3. A class's growing picture and clearing a world ------------------------------------------------------

class TestEveryRankAddsSomething(AppTestCase):
    def picture(self, tier):
        with self.app.test_request_context("/"):
            env = self.app.jinja_env
            macro = env.get_template("academy/_art.html").module.avatar
            return str(macro("rocket", academy.AVATARS, 56, tier))

    def test_each_rank_shows_a_new_thing(self):
        marks = {1: "avatar-badge", 2: "avatar-cap", 3: "avatar-bowtie", 4: "avatar-tophat", 5: "avatar-crown",
                 6: "avatar-wings", 7: "avatar-aura"}
        before = None
        for tier in range(len(academy.RANKS)):
            svg = self.picture(tier)
            found = {m for m in marks.values() if f'class="{m}"' in svg}
            if tier:
                self.assertIn(marks[tier], found, tier)
                self.assertIn('class="avatar-frame"', svg)
            # Each rank looks different from the one before it.
            self.assertNotEqual(found, before, tier)
            before = found
        self.assertNotIn("avatar-badge", self.picture(0))

    def test_the_classroom_track_reaches_the_new_looks(self):
        tiers = {academy.rank_tier(n, academy.CLASSROOM) for n in range(academy.CLASSROOM.total + 1)}
        self.assertEqual(tiers, set(range(len(academy.RANKS))))


class TestAClassClearsAWorld(SchoolCase):
    def setUp(self):
        super().setUp()
        self.teacher_signup()
        class_id = self.add_class()
        self.add_students(class_id, ["Maya"])
        self.maya = self.students(class_id)["Maya"]["id"]

    def play(self, world_number, stage):
        t = academy.CLASSROOM
        with self.db() as conn:
            row = conn.execute("SELECT attempts FROM learner_progress WHERE learner_id = ? AND level = ?",
                               (self.maya, academy.level_id(t, world_number, stage))).fetchone()
        attempt = (row["attempts"] if row else 0) + 1
        questions = academy.quiz(t, world_number, stage, academy.CLASS_BUSINESS, [],
                                 academy.attempt_seed(self.maya, t.key, world_number, stage, attempt))
        data = {"attempt": str(attempt)}
        for i, q in enumerate(questions):
            data[f"q{i}"] = str(q.answer)
        return self.post(f"/app/academy/{self.maya}/world/{world_number}/stage/{stage}", data).data.decode()

    def test_a_bigger_moment_with_the_worlds_cleared(self):
        t = academy.CLASSROOM
        first = academy.world(t.topics[0])
        for stage in range(1, t.stages(first)):
            self.assertNotIn("data-world-clear", self.play(first.number, stage))
        page = self.play(first.number, t.stages(first))
        self.assertIn("data-world-clear", page)
        self.assertIn('data-worlds-cleared="1"', page)
        self.assertIn(f"1 of {len(t.topic_worlds)} worlds cleared", words(page))
        self.assertEqual(page.count("<li class=\"done\""), 1)
        self.assertIn("data-just-cleared", page)
        # More sparks than a stage's own celebration.
        sparks = page[page.index("ac-celebrate-sparks"):]
        self.assertGreaterEqual(sparks[:sparks.index("</div>")].count("<i></i>"), 28)


class TestTheWorldClearShowsThePictureGrowing(ProgressCase):
    def test_before_and_after_when_the_clear_is_a_rank_up(self):
        page = read("omniarmor_app", "templates", "academy", "result.html")
        world = page[page.index("{% if world_clear %}"):page.index("{% else %}")]
        self.assertIn("ac-world-grew", world)
        self.assertIn("avatar(learner.avatar, avatars, 48, old_tier)", world)


# --- 4. Lessons --------------------------------------------------------------------------------------------

def lessons(t):
    for w in t.worlds:
        for stage in range(1, t.stages(w) + 1):
            yield w, stage


class TestTheMatchingGameTeachesItsOwnWords(unittest.TestCase):
    def test_no_word_of_the_game_is_asked_or_offered_again_in_its_lesson(self):
        checked = 0
        for t in academy.ALL_TRACKS:
            w = next(w for w in t.topic_worlds if w.key == "words")
            for stage in range(1, t.stages(w) + 1):
                for attempt in (1, 2, 3):
                    quiz = academy.quiz(t, w.number, stage, "Acme", (1, 18),
                                        academy.attempt_seed(5, t.key, w.number, stage, attempt))
                    games = [q for q in quiz if q.kind == "match"]
                    if not games:
                        continue
                    game = games[0]
                    shown = set(game.parts["left"]) | set(game.parts["pool"])
                    for q in quiz:
                        if q is not game:
                            self.assertFalse(shown & academy.words_in(q), (t.key, stage, q.prompt))
                    checked += 1
        self.assertGreater(checked, 20)

    def test_words_in_reads_every_kind_of_word_question(self):
        q = academy.Question('What does "Revenue" mean?', [academy.WORD_IDEAS["Revenue"], academy.WORD_IDEAS["Cost"],
                                                          academy.WORD_IDEAS["Budget"]], 0, "x")
        self.assertEqual(academy.words_in(q), {"Revenue", "Cost", "Budget"})
        scene = academy.Question("Which word fills the gap? ...", ["Fine", "Loan", "Logo"], 1, "x")
        self.assertEqual(academy.asked_word(scene), "Loan")
        self.assertEqual(academy.words_in(scene), {"Fine", "Loan", "Logo"})
        sentence = academy.Question('Which sentence uses "Logo" the right way?', ["a", "b", "c"], 0, "x")
        self.assertEqual(academy.words_in(sentence), {"Logo"})


class TestShortSentences(unittest.TestCase):
    def test_every_answer_to_which_sentence_is_90_characters_or_less(self):
        self.assertEqual(academy.SENTENCE_MOST, 90)
        seen = 0
        for t in academy.ALL_TRACKS:
            w = next(w for w in t.topic_worlds if w.key == "words")
            pool = academy.classroom_pool(w.number) if t.key == academy.CLASSROOM_KEY \
                else academy.family_pool(t, w.number, "Acme", (1, 18))
            for q in pool:
                if q.prompt.startswith("Which sentence uses"):
                    seen += 1
                    for option in q.options:
                        self.assertLessEqual(len(option), 90, option)
        self.assertGreater(seen, 10)

    def test_more_scenes_are_short_enough_to_ask_as_a_sentence(self):
        short = [w for w, s in WORD_SCENES.items() if len(academy._in_gap(s, w)) <= academy.SENTENCE_MOST]
        self.assertGreaterEqual(len(short), 75)


class TestAPictureInEachScene(unittest.TestCase):
    def test_every_scene_question_has_a_picture_that_is_not_its_word(self):
        t = academy.CLASSROOM
        w = next(w for w in t.topic_worlds if w.key == "words")
        scenes = [q for q in academy.classroom_pool(w.number) if q.prompt.startswith("Which word fills the gap?")]
        self.assertTrue(scenes)
        for q in scenes:
            self.assertEqual(q.parts["pic"], scene_picture(q.parts["scene"]))
            self.assertTrue(q.parts["pic"])
        self.assertEqual(scene_picture(WORD_SCENES["Cost"]), "🍋")
        self.assertEqual(scene_picture(WORD_SCENES["Interest"]), "🏦")
        self.assertEqual(scene_picture("Nothing to see here: the ___."), "💼")
        quiz = read("omniarmor_app", "templates", "academy", "_quiz.html")
        self.assertIn('<span class="ac-scene-pic" aria-hidden="true">{{ q.parts.pic }}</span>', quiz)


class TestTheCheckerEnforcesTheRules(unittest.TestCase):
    def test_no_flags_today(self):
        flags = [f for f in quiz_truth_review.review(quiz_truth_review.COMPANIES[:2])
                 if f[0] in ("repeat", "long-sentence")]
        self.assertEqual(flags, [])

    def test_it_flags_a_long_sentence(self):
        t = academy.TRACKS["launchpad"]
        with mock.patch.object(academy, "SENTENCE_MOST", 40):
            flags = quiz_truth_review.lesson_flags(t, "Acme", (1,))
        self.assertTrue([f for f in flags if f[0] == "long-sentence"])

    def test_it_flags_a_game_word_asked_again(self):
        t = academy.TRACKS["launchpad"]
        academy._family_pool.cache_clear()
        try:
            with mock.patch.object(academy, "_match_apart", lambda out, chunk, rng: None):
                flags = quiz_truth_review.lesson_flags(t, "Acme", (1,))
        finally:
            academy._family_pool.cache_clear()
        self.assertTrue([f for f in flags if f[0] == "repeat"])


# --- 5. Home's "Needs attention" ------------------------------------------------------------------------------

def state(level, days, policy=False, industry=1, title="x"):
    today = date(2026, 11, 22)
    return SimpleNamespace(level=level, days_left=days, industry_id=industry, rule=SimpleNamespace(title=title),
                           effective=SimpleNamespace(policy=policy), due_date=None if days is None else today + timedelta(days),
                           today=today)


class TestNeedsAttentionByUrgency(unittest.TestCase):
    def test_most_overdue_first_then_soonest(self):
        items = [state("WARNING", 41, title="licences"), state("BLOCKED", -3, title="cobra"), state("WARNING", 1, title="i9"),
                 state("BLOCKED", None, title="sick worker"), state("BLOCKED", -4, title="exclusion"),
                 state("WARNING", None, title="no date"), state("WARNING", 12, title="sterile")]
        order = [s.rule.title for s in sorted(items, key=views.urgency)]
        self.assertEqual(order, ["exclusion", "cobra", "sick worker", "i9", "sterile", "licences", "no date"])

    def test_an_early_policy_warning_is_explained(self):
        self.assertTrue(views.early_policy(state("WARNING", 41, policy=True)))
        self.assertFalse(views.early_policy(state("WARNING", 41, policy=False)))
        self.assertFalse(views.early_policy(state("WARNING", 3, policy=True)))
        self.assertFalse(views.early_policy(state("BLOCKED", 41, policy=True)))
        page = read("omniarmor_app", "templates", "app", "overview.html")
        self.assertIn("{% if early_policy(st) %}", page)   # 1.27.0: one row per tracked item (s, title, st)
        self.assertIn("this warning window is a policy setting (an industry standard, not a law)", page)


class TestHomeShowsTheOrder(AppTestCase):
    def test_rows_carry_their_days_in_order(self):
        client = self.app.test_client()
        client.get("/demo/business")
        page = client.get("/app").data.decode()
        block = page[page.index("data-needs-attention"):page.index("data-coming-due")]
        days = [int(d) for d in re.findall(r'data-days="(-?\d+)"', block)]
        self.assertTrue(days)
        self.assertEqual(days, sorted(days))


# --- 6. Overlaps ------------------------------------------------------------------------------------------------

class TestNothingCoversTheWords(AppTestCase):
    def test_the_quiz_pop_up_takes_the_score_line_s_place_in_the_bar(self):
        css = read("omniarmor_app", "static", "academy.css")
        toast = re.search(r"\.ac-toast\{position:absolute;[^}]*\}", css).group(0)
        self.assertNotIn("top:calc(100%", toast)
        self.assertIn("bottom:7px", toast)
        self.assertIn(".ac-hud.toasting .ac-hud-line{visibility:hidden}", css)
        js = read("omniarmor_app", "static", "academy.js")
        self.assertIn('hud.classList.add("toasting")', js)
        self.assertIn('hud.classList.remove("toasting")', js)

    def test_pilot_avoids_the_class_page_s_note_above_the_tab_bar(self):
        js = read("omniarmor_app", "static", "pilot-omniarmor.js")
        avoid = js[js.index("avoid: ["):js.index("gutter:")]
        self.assertIn('".hint"', avoid)

    def test_add_as_has_one_space(self):
        page = read("omniarmor_app", "templates", "academy", "class.html")
        self.assertIn("<span>Add as <strong>{{ short }}</strong></span>", page)

    def test_the_answer_review_card_has_no_empty_gap(self):
        css = read("omniarmor_app", "static", "academy.css")
        self.assertIn("/* The answer review (1.21.0)", css)


class TestVersion(unittest.TestCase):
    def test_version_and_changelog(self):
        self.assertGreaterEqual(tuple(map(int, __version__.split("."))), (1, 21, 0))
        log = read("CHANGELOG.md")
        top = log[log.index("## 1.21.0"):log.index("## 1.20.0")]
        for said in ("side bar", "every page", "not legal advice", "picture", "90 characters", "by days left"):
            self.assertIn(said, top)
        # The 1.20.0 line is corrected: those typed questions worked only where the page offered them.
        old = log[log.index("## 1.20.0"):log.index("## 1.19.0")]
        self.assertIn("on the pages that offer them", old)


if __name__ == "__main__":
    unittest.main()
