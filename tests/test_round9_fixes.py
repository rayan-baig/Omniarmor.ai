"""1.19.0: what a strict ninth review asked for. The matching game's answers
read right and show the true pairs, the quiz's pop-up keeps off the score, one
helper per grown-up page, counts and rank goals that read right, Business
Words asked in scenes and sentences (and matching games in more worlds), the
map's road behind its worlds and the learner's own picture on a passed stage,
Pilot's "What's due or overdue?" with the real items on every page (and no
sign-in links for visitors), and an honest, optional second backup."""

import html
import os
import random
import re
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))
from test_parent_view import BASIC, ProgressCase  # noqa: E402
from test_webapp import AppTestCase  # noqa: E402

import quiz_truth_review  # noqa: E402
from omniarmor_app import academy, jobs  # noqa: E402
from omniarmor_app.academy_bank.word_ideas import WORD_IDEAS  # noqa: E402
from omniarmor_app.academy_bank.word_use import CLASHES, GAP, WORD_SCENES  # noqa: E402
from omniarmor_app.version import __version__  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def read(*parts):
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as f:
        return f.read()


def words(page):
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", page)).split())


# --- 1 and 2. The matching game and the quiz bar ----------------------------------------------------

class TestTheMatchingGame(unittest.TestCase):
    def test_each_chip_keeps_its_words_apart_from_its_number(self):
        quiz = read("omniarmor_app", "templates", "academy", "_quiz.html")
        self.assertIn('<span class="ac-chip-text">{{ idea }}</span>', quiz)
        self.assertIn('<span class="ac-nb">{{ part }}</span>', quiz)
        js = read("omniarmor_app", "static", "academy.js")
        # The answer says the idea's own words: no "goes with: 3The latest date".
        self.assertIn('"goes with: " + ideaText(ideas[truth[i]])', js)
        self.assertNotIn('"goes with: " + ideas[truth[i]].textContent', js)
        # After checking, each idea wears the colour and number of the word it really goes with.
        self.assertIn('idea.className = "ac-chip paired pair-" + owner + " answer"', js)

    def test_words_break_only_between_words(self):
        css = read("omniarmor_app", "static", "academy.css")
        self.assertNotIn(".ac-chip > span:last-of-type{min-width:0;overflow-wrap:anywhere}", css)
        self.assertIn(".ac-chip-word .ac-chip-text{overflow-wrap:normal", css)
        self.assertIn(".ac-nb{white-space:nowrap}", css)
        self.assertIn("grid-template-columns:minmax(min-content,1fr) minmax(0,1.35fr)", css)


class TestTheQuizBar(unittest.TestCase):
    def test_the_pop_up_sits_below_the_bar_not_over_the_score(self):
        css = read("omniarmor_app", "static", "academy.css")
        toast = re.search(r"\.ac-toast\{position:absolute;[^}]*\}", css).group(0)
        self.assertIn("top:calc(100% + 6px)", toast)
        self.assertNotIn("top:50%", toast)

    def test_check_is_greyed_out_until_every_piece_has_a_place(self):
        self.assertIn(".ac-game-check:disabled{opacity:.45;filter:grayscale(1)",
                      read("omniarmor_app", "static", "academy.css"))


# --- 3. One helper per page -------------------------------------------------------------------------

class TestOneHelper(unittest.TestCase):
    def test_pilot_alone_on_a_wide_screen_and_armo_off_the_side_bar(self):
        css = read("omniarmor_app", "static", "app.css")
        block = css[css.index("/* One helper per page (1.19.0)."):]
        self.assertIn("@media (min-width:721px){\n  body:has(#pilot-core) > .companion{display:none}", block)
        self.assertIn("body.has-tabs:not(.lesson-view) .companion{left:auto;right:", block)
        # The tablet's room for Armo goes when Pilot is the helper.
        self.assertIn("body:not(:has(#pilot-core)):has(> .companion .companion-badge:not([hidden])) main > .wrap", css)


# --- 4. Words, rank goals and explanations ---------------------------------------------------------

class TestCountsReadRight(AppTestCase):
    def test_a_new_workspace_with_one_industry(self):
        self.signup(industries=(1,))
        with self.db() as conn:
            said = [r[0] for r in conn.execute("SELECT summary FROM audit WHERE action = 'workspace'")]
        self.assertIn("Workspace created with 1 industry", said)
        self.assertIn("Workspace created with 1 industry", words(self.client.get("/app/audit").data.decode()))

    def test_the_demos_history_reads_right(self):
        for demo in ("business", "classroom", "salon"):
            client = self.app.test_client()
            client.get(f"/demo/{demo}")
            page = words(client.get("/app/audit").data.decode())
            self.assertIn("Workspace created with", page, demo)
            self.assertNotRegex(page, r"\b1 (industries|days|warnings|lessons|checks)\b", demo)

    def test_the_words_say_1_industry(self):
        self.assertIn("plural(len(picked), 'industry')", read("omniarmor_app", "auth.py"))
        self.assertNotIn('"Workspace created with 1 industries"', read("omniarmor_app", "demo_mode.py"))


class TestRankGoals(unittest.TestCase):
    def test_no_track_has_a_goal_past_its_last_level(self):
        for t in academy.ALL_TRACKS:
            ladder = academy.rank_ladder(t)
            goals = [g for g, _ in ladder]
            self.assertEqual(len(ladder), len(academy.RANKS), t.key)
            self.assertLessEqual(goals[-1], t.total, t.key)
            self.assertEqual(goals, sorted(set(goals)), t.key)
            self.assertEqual(academy.rank_for(t.total, t), "Tycoon", t.key)
        classroom = academy.rank_ladder(academy.CLASSROOM)
        self.assertEqual(classroom[-1], (academy.CLASSROOM.total, "Tycoon"))
        self.assertEqual(academy.CLASSROOM.total, academy.CLASSROOM.lessons)
        # Goals that were already in reach stay where they were.
        self.assertEqual(academy.rank_ladder(BASIC)[:7], [(0, "Rookie"), (5, "Apprentice"), (15, "Team Captain"),
                                                         (40, "Manager"), (100, "Executive"), (250, "Future Owner"),
                                                         (600, "Business Legend")])


class TestExplanations(unittest.TestCase):
    def test_a_fine_is_explained_without_a_tip(self):
        fine = next(q for q in academy._STAND_RULES if q[0] == "What is a fine?")
        self.assertNotIn("tip", fine[4])
        self.assertIn("penalty", fine[4])

    def test_the_checker_flags_a_line_that_doesnt_tie_back(self):
        old = academy.Question("What is a fine?", ["Money paid as a penalty for breaking a rule",
                                                   "Money paid to the town for a permit",
                                                   "Money a customer adds as a thank-you"], 0,
                               "A fine costs money that could have gone to growing the business. A thank-you is a tip.")
        self.assertEqual(quiz_truth_review.stray_lines(old), ["A thank-you is a tip."])
        fixed = academy.Question(old.prompt, old.options, 0, fine_explain())
        self.assertEqual(quiz_truth_review.stray_lines(fixed), [])

    def test_every_quiz_passes_the_checker(self):
        self.assertEqual(quiz_truth_review.review(), [])


def fine_explain():
    return next(q for q in academy._STAND_RULES if q[0] == "What is a fine?")[4]


# --- 5. Business Words in scenes and sentences; more matching games ---------------------------------------

class TestBusinessWordsVariety(unittest.TestCase):
    def words_world(self, t):
        return next(w for w in t.topic_worlds if w.key == "words")

    def pools(self):
        for t in academy.ALL_TRACKS:
            w = self.words_world(t)
            pool = academy.classroom_pool(w.number) if t.key == academy.CLASSROOM_KEY \
                else academy.family_pool(t, w.number, "Acme", (1, 18))
            size = academy.LESSON_QUESTIONS if t.key == academy.CLASSROOM_KEY else t.min_questions
            yield t, pool, size

    def test_every_word_has_one_scene_with_a_plain_gap(self):
        self.assertEqual(set(WORD_SCENES), set(WORD_IDEAS))
        for word, scene in WORD_SCENES.items():
            self.assertEqual(scene.count(GAP), 1, word)
            self.assertNotRegex(scene, r"\ban? " + re.escape(GAP), word)   # "an ___" would give the answer away
            self.assertIsNone(re.search(rf"\b{re.escape(word.lower())}\b", scene.lower()), word)

    def test_no_lesson_is_five_what_does_it_mean_in_a_row(self):
        for t, pool, size in self.pools():
            kinds = set()
            for n in range(len(pool) // size):
                lesson = pool[n * size:(n + 1) * size]
                asks = sum(q.prompt.startswith("What does") for q in lesson)
                self.assertLessEqual(asks, max(2, size // 3), f"{t.key} lesson {n + 1}")
                kinds.update(q.prompt.split(" ", 2)[1] if q.kind == "choice" else q.kind for q in lesson)
            self.assertTrue({"does", "word", "sentence", "match"} <= kinds, (t.key, kinds))

    def test_a_scene_and_a_sentence_have_one_right_answer(self):
        for t, pool, _ in self.pools():
            for q in pool:
                if q.prompt.startswith("Which word fills the gap?"):
                    word = q.options[q.answer]
                    self.assertEqual(q.parts["scene"], WORD_SCENES[word])
                    self.assertEqual(q.look, "scenario")
                    for other in q.options:
                        if other != word:
                            self.assertFalse(academy._clash(word, other), (word, other))
                elif q.prompt.startswith("Which sentence uses"):
                    word = re.match(r'Which sentence uses "(.+)" the right way\?', q.prompt).group(1)
                    self.assertEqual(q.options[q.answer], academy._in_gap(WORD_SCENES[word], word))
                    for n, option in enumerate(q.options):
                        if n == q.answer:
                            continue
                        owner = next(w for w, s in WORD_SCENES.items() if academy._in_gap(s, word) == option)
                        self.assertFalse(academy._clash(word, owner), (word, owner))
                        self.assertFalse(academy._names(WORD_SCENES[owner], word), (word, owner))

    def test_clashing_words_are_real_words(self):
        for group in CLASHES:
            self.assertTrue(group <= set(WORD_IDEAS), group)

    def test_the_scene_shows_under_the_question_and_keeps_its_look(self):
        t = academy.CLASSROOM
        w = self.words_world(t)
        q = next(q for q in academy.classroom_pool(w.number) if q.prompt.startswith("Which word fills"))
        fresh = academy._fresh(q, random.Random(3))
        self.assertEqual(fresh.parts, q.parts)
        self.assertEqual(fresh.look, "scenario")
        self.assertIn('<p class="ac-word-scene">{{ q.parts.scene }}</p>', read("omniarmor_app", "templates", "academy", "_quiz.html"))

    def test_the_match_words_change_between_attempts(self):
        t = academy.TRACKS["launchpad"]
        w = self.words_world(t)
        seen = set()
        for attempt in range(1, 9):
            quiz = academy.quiz(t, w.number, 2, "Acme", (1,), academy.attempt_seed(7, t.key, w.number, 2, attempt))
            match = next(q for q in quiz if q.kind == "match")
            left = match.parts["left"]
            seen.add(tuple(left))
            # Still one right way to pair them, and it is the one the server grades.
            truth = ",".join(str(match.parts["right"].index(WORD_IDEAS[x])) for x in left)
            self.assertEqual(match.parts["codes"][match.answer], truth)
            self.assertEqual(len({x for x in left}), 3)
            for a in left:
                for b in left:
                    self.assertFalse(a != b and academy._clash(a, b), (a, b))
        self.assertGreater(len(seen), 2)
        # The first word stays the lesson's own.
        self.assertEqual(len({s[0] for s in seen}), 1)

    def test_more_worlds_have_a_matching_game(self):
        for key in academy.TERM_MATCH_WORLDS:
            for t in (academy.TRACKS["trailblazer"], academy.CLASSROOM):
                w = next((w for w in t.topic_worlds if w.key == key), None)
                if w is None:
                    continue
                pool = academy.classroom_pool(w.number) if t.key == academy.CLASSROOM_KEY \
                    else academy.family_pool(t, w.number, "Acme", (1, 18))
                games = [q for q in pool if q.kind == "match"]
                self.assertTrue(games, (t.key, key))
                for q in games:
                    self.assertEqual(q.parts["title"], "Match each term to what it means.")
                    self.assertEqual(len(q.options), 6)

    def test_lesson_counts_stay(self):
        self.assertEqual([t.lessons for t in academy.ALL_TRACKS], [90, 350, 296, 224, 107])


# --- 6. The map and a passed stage --------------------------------------------------------------------

class TestTheMapRoad(unittest.TestCase):
    def test_the_road_goes_behind_a_locked_world(self):
        css = read("omniarmor_app", "static", "academy.css")
        block = css[css.index("/* The map's road goes behind the worlds (1.19.0)"):]
        self.assertIn(".ac-path .ac-world.locked > span,.ac-path .ac-world.paid > a{opacity:1}", block)
        self.assertIn(".ac-path .ac-world.locked .ac-world-card{opacity:.55}", block)
        self.assertIn(".ac-path .ac-world-node{z-index:2}", block)
        self.assertIn("@media (min-width:900px){\n  .ac-path{--road:220px", block)


class TestMyPictureOnAPassedStage(ProgressCase):
    def test_a_passed_stage_shows_the_learner_s_picture(self):
        page = self.play(1, 1, right=5).data.decode()
        result = page[page.index('<section class="ac-result'):]
        self.assertIn("data-my-picture", result)
        self.assertIn('class="ac-result-armo"', result)
        self.assertNotIn("ac-grew-from", page)

    def test_when_the_picture_grows_the_one_before_shows_beside_it(self):
        for stage in range(1, 5):
            self.play(1, stage, right=5)
        page = self.play(1, 5, right=5).data.decode()      # the fifth lesson: Apprentice
        self.assertIn("you're now an Apprentice", page)
        self.assertIn('data-grew-from="0"', page)
        self.assertIn("ac-grew-arrow", page)
        self.assertIn("ac-result-me grew", page)

    def test_a_retry_shows_armo_thinking(self):
        page = self.play(1, 1, right=0).data.decode()
        result = page[page.index('<section class="ac-result'):]
        self.assertNotIn("data-my-picture", result)


# --- 7. Pilot's due list on every page -----------------------------------------------------------------

class TestPilotDueList(AppTestCase):
    def due(self, path):
        body = self.client.get(path).data.decode()
        found = re.search(r"data-due='([^']*)'", body)
        return None if found is None else __import__("json").loads(html.unescape(found.group(1)))

    def test_every_business_page_carries_what_needs_attention(self):
        self.signup()
        for path in ("/app", "/app/report", "/app/audit", "/app/notifications", "/app/settings"):
            due = self.due(path)
            self.assertIsInstance(due, list, path)
            self.assertTrue(due, path)
            for item in due:
                self.assertEqual(set(item), {"level", "title", "where", "url"})
                self.assertTrue(item["url"].startswith("/app/"), item)

    def test_a_visitor_gets_no_workspace_list(self):
        self.assertEqual(self.due("/"), [])


# --- 8. An honest, optional second backup ------------------------------------------------------------------

class TestSecondBackup(AppTestCase):
    def test_off_by_default_and_the_page_says_same_hosting_company(self):
        self.assertEqual(self.app.config["OFFSITE_BACKUP_COMMAND"], "")
        page = words(self.client.get("/security").data.decode())
        self.assertIn("kept by the same hosting company", page)
        self.assertNotIn("second, separate storage company", page)

    def test_once_a_copy_has_gone_through_the_pages_say_so(self):
        with tempfile.TemporaryDirectory() as folder:
            source = os.path.join(folder, "omniarmor.db")
            import sqlite3
            sqlite3.connect(source).close()
            target = os.path.join(folder, "offsite")
            os.makedirs(target)
            cfg = {"DATABASE": source, "BACKUP_DIR": os.path.join(folder, "backups"), "BACKUP_KEEP": 3,
                   "OFFSITE_BACKUP_COMMAND": f"cp {{file}} {target}"}
            made = jobs.backup_database(cfg)
            self.assertTrue(os.path.exists(os.path.join(target, os.path.basename(made))))
            self.assertTrue(jobs.offsite_ok(cfg))
            self.app.config.update(OFFSITE_BACKUP_COMMAND=cfg["OFFSITE_BACKUP_COMMAND"], BACKUP_DIR=cfg["BACKUP_DIR"])
            page = words(self.client.get("/security").data.decode())
            self.assertIn("second, separate storage company", page)
            self.assertIn("second storage company", words(self.client.get("/privacy").data.decode()))

    def test_a_failing_command_is_logged_never_claimed(self):
        with tempfile.TemporaryDirectory() as folder:
            source = os.path.join(folder, "omniarmor.db")
            import sqlite3
            sqlite3.connect(source).close()
            cfg = {"DATABASE": source, "BACKUP_DIR": os.path.join(folder, "backups"), "BACKUP_KEEP": 3,
                   "OFFSITE_BACKUP_COMMAND": "false"}
            with self.assertLogs("omniarmor.jobs", "ERROR"):
                made = jobs.backup_database(cfg)
            self.assertTrue(os.path.exists(made))       # the local backup still counts
            self.assertFalse(jobs.offsite_ok(cfg))
            self.app.config.update(OFFSITE_BACKUP_COMMAND="false", BACKUP_DIR=cfg["BACKUP_DIR"])
            self.assertNotIn("second, separate storage company", words(self.client.get("/security").data.decode()))

    def test_no_shell_runs_it(self):
        with mock.patch("subprocess.run") as run:
            run.return_value = mock.Mock(returncode=0)
            with tempfile.TemporaryDirectory() as folder:
                jobs.send_offsite({"OFFSITE_BACKUP_COMMAND": "rclone copy {file} offsite:b; rm -rf /",
                                   "BACKUP_DIR": folder}, "/x/omniarmor-1.db")
        argv = run.call_args.args[0]
        self.assertEqual(argv[:3], ["rclone", "copy", "/x/omniarmor-1.db"])
        self.assertNotIn("shell", run.call_args.kwargs)

    def test_documented_for_the_owner(self):
        ops = read("docs", "OPERATIONS.md")
        self.assertIn("OFFSITE_BACKUP_COMMAND", ops)
        self.assertIn("off by default", ops)


class TestVersion(unittest.TestCase):
    def test_version(self):
        self.assertEqual(__version__, "1.19.0")
        self.assertIn("## 1.19.0", read("CHANGELOG.md"))
