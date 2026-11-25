"""1.12.0: what a strict third review found, fixed. The school checklist
stays out of a teacher's Armo, Reminders and Report until Whole school; the
helpers keep off the content; honest Academy level counts with the Rule
Quests counted apart; full names checked with the teacher; Pilot's own
suggestions and a plain word on AI keys; a demo per trade; lessons that
teach what they ask; no true "wrong" answers; honest result headings; the
right date label for an entry and no duplicate names; who each email went
to; plain words for a countdown; and error reports that read right with a
virtual environment inside the project."""

import json
import os
import re
import subprocess
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_classroom_review import SCHOOL, SchoolCase, words  # noqa: E402
from test_webapp import AppTestCase  # noqa: E402

from omni_armor_rules import CATALOG, evaluate  # noqa: E402
from omniarmor_app import academy, armo, classrooms, demo_mode, errormail  # noqa: E402
from omniarmor_app.academy_views import result_band, retry_lines  # noqa: E402
from omniarmor_app.catalog import find_rule  # noqa: E402
from omniarmor_app.db import now_iso  # noqa: E402
from omniarmor_app.tracking import checklist_ids, org_today, states_for_org  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATIC = os.path.join(ROOT, "omniarmor_app", "static")
sys.path.insert(0, os.path.join(ROOT, "tools"))
import quiz_truth_review  # noqa: E402


def read(*parts):
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as f:
        return f.read()


# --- 1. The school checklist stays out of a free-trial teacher's pages --------------------------

class TestSchoolChecklistOnlyOnWholeSchool(SchoolCase):
    def setUp(self):
        super().setUp()
        self.teacher_signup()
        self.class_id = self.add_class()

    def whole_school(self):
        result = self.app.test_cli_runner().invoke(args=["plan", "1", "school"])
        self.assertEqual(result.exit_code, 0, result.output)

    def test_the_trial_workspace_has_no_school_checklist(self):
        with self.db() as conn:
            org = self.org()
            self.assertNotIn(SCHOOL, checklist_ids(conn, org))
            self.assertFalse([s for s in states_for_org(conn, org) if s.industry_id == SCHOOL])

    def test_armo_shows_no_school_check_and_no_fix_it_link_to_it(self):
        page = self.client.get("/app/armo").data.decode()
        self.assertNotIn("/app/industry/51", page)
        self.assertNotIn("without a reading", page)
        self.assertNotIn("with no reading", words(page))
        status = self.client.get("/app/armo/status").get_json()
        self.assertEqual(status["needs"], 0)
        self.assertEqual(status["issues"], [])
        self.assertFalse(any("/app/industry/" in t["url"] for t in status["tips"]))

    def test_armo_gives_teacher_tips_on_the_class_page(self):
        page = self.client.get(f"/app/academy/classes/{self.class_id}").data.decode()
        tips = json.loads(re.search(r"data-tips='([^']*)'", page).group(1).replace("&#34;", '"'))
        text = " ".join(t["text"] for t in tips)
        self.assertIn("Room 12 has no students yet", text)
        self.assertNotRegex(text, r"(?i)inspector|compliance|invite your team|Report prints")
        idle = re.search(r"data-idle='([^']*)'", page).group(1)
        self.assertNotRegex(idle, r"(?i)inspection|compliance|audit trail")
        self.assertIn("This is your class", page)

    def test_the_checklist_page_sends_the_teacher_back_to_the_classes(self):
        response = self.client.get("/app/industry/51")
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.headers["Location"].endswith("/app/academy/classes"))
        page = self.client.get(response.headers["Location"]).data.decode()
        self.assertIn("The school safety checklist comes with the Whole school plan.", words(page))
        # A save to it goes the same way, and nothing is written.
        response = self.change(51, "cafeteria_food_safety", value="3")
        self.assertTrue(response.headers["Location"].endswith("/app/academy/classes"))
        with self.db() as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM items WHERE industry_id = 51").fetchone()[0], 0)

    def test_reminders_never_point_at_a_school_check(self):
        page = words(self.client.get("/app/notifications").data.decode())
        self.assertNotIn("Cafeteria", page)
        self.assertNotIn("Open ", page.split("Reminders", 1)[1][:400])
        self.assertIn("Reminder emails for the school safety checklist come with the Whole school plan", page)

    def test_the_report_is_not_the_school_checklist(self):
        response = self.client.get("/app/report")
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.headers["Location"].endswith("/app/academy/classes"))
        response = self.client.get("/app/report.csv")
        self.assertEqual(response.status_code, 302)
        self.assertNotIn(b"School Safety Aegizyn", response.data)

    def test_pilot_knows_no_school_checklist_on_the_trial(self):
        page = self.client.get("/app/academy/classes").data.decode()
        self.assertIn("data-checklists='[]'", page)

    def test_whole_school_brings_it_all_back(self):
        self.whole_school()
        self.assertEqual(self.client.get("/app/industry/51").status_code, 200)
        self.assertIn("/app/industry/51", self.client.get("/app/armo").data.decode())
        report = words(self.client.get("/app/report").data.decode())
        self.assertIn("Cafeteria food-safety check done", report)
        with self.db() as conn:
            self.assertIn(SCHOOL, checklist_ids(conn, self.org()))


# --- 2. The helpers keep off the content --------------------------------------------------------

class TestHelpersKeepOffTheContent(unittest.TestCase):
    def test_armo_opens_by_himself_at_most_once_a_day_and_only_beside_the_column(self):
        js = read("omniarmor_app", "static", "armo.js")
        self.assertIn('remember("armo-bubble-day")', js)
        self.assertIn("roomBeside() >= BUBBLE_ROOM", js)
        self.assertIn("openByItself(soundTheAlarm)", js)
        # No greeting on the first page, and idle life never opens the bubble.
        self.assertNotIn("armo-greeted", js)
        self.assertNotIn("setTimeout(soundTheAlarm", js)
        idle = js[js.index("function idleTick"):js.index("// Live updates")]
        self.assertNotIn("say(", idle)
        self.assertNotIn("giveTip(", idle)

    def test_pilot_keeps_clear_of_tags_badges_and_notes(self):
        config = read("omniarmor_app", "static", "pilot-omniarmor.js")
        avoid = re.search(r"avoid: \[(.*?)\],\n", config, re.S).group(1)
        for sel in (".tag", ".top-n", ".bundle", ".msg", ".companion-bubble", ".companion-badge", ".topbar .nav",
                    ".flash"):
            self.assertIn(f'"{sel}"', avoid)
        self.assertIn('yieldTo: [".companion"]', config)


# --- 3. Honest Academy level counts --------------------------------------------------------------

class TestAcademyCounts(AppTestCase):
    def test_a_track_leads_with_its_business_lessons(self):
        for t in academy.TRACK_LIST:
            self.assertEqual(t.lessons, t.topic_lessons + t.final_stages)
            self.assertEqual(t.quests_for([2]), 1)
            self.assertEqual(t.quests_for([2, 30, 9999]), 2)
            self.assertLess(t.lessons, t.total)
        self.assertEqual(academy.CLASSROOM.lessons, academy.CLASSROOM.total)

    def test_the_academy_home_uses_the_biggest_track_and_counts_rule_quests_apart(self):
        self.signup(industries=(2,))
        page = words(self.client.get("/app/academy").data.decode())
        most = max(t.lessons for t in academy.TRACK_LIST)
        self.assertIn(f"Up to {most:,} business lessons in", page)
        self.assertNotIn(f"Up to {academy.TRACK_LIST[-1].total:,} levels", page)
        self.assertIn("a Rule Quest for each of", page)
        launchpad = academy.TRACKS["launchpad"]
        self.assertIn(f"{launchpad.lessons:,} lessons", page)
        self.assertNotIn(f"{launchpad.total:,}", page)

    def test_a_learner_counts_only_their_own_industries_rule_quests(self):
        self.signup(industries=(2,))
        self.post("/app/academy/learners", {"nickname": "Mia", "avatar": "rocket"})
        with self.db() as conn:
            learner = conn.execute("SELECT id FROM learners").fetchone()["id"]
        self.post(f"/app/academy/{learner}/track", {"track": "launchpad"})
        page = words(self.client.get(f"/app/academy/{learner}").data.decode())
        t = academy.TRACKS["launchpad"]
        # 1.13.0: the business lessons only, with the workspace's Rule Quest shown apart.
        self.assertIn(f"0 / {t.lessons:,} lessons · +1 Rule Quest", page)
        self.assertIn("Extra: explore other industries", page)
        self.assertIn("optional", page)


# --- 4. Full names are checked with the teacher -------------------------------------------------

class TestFullNamesAreConfirmed(SchoolCase):
    def setUp(self):
        super().setUp()
        self.teacher_signup()
        self.class_id = self.add_class()

    def test_a_two_word_name_is_not_added_until_the_teacher_chooses(self):
        response = self.add_students(self.class_id, ["Ava Thompson", "Liam", "Noah K", "Jo B."])
        self.assertEqual(sorted(self.students(self.class_id)), ["Jo B.", "Liam", "Noah K"])
        page = response.data.decode()
        self.assertIn("data-confirm-names", page)
        self.assertIn('value="Ava T" checked', page)
        self.assertIn("looks like a first and last name", words(page))

    def test_only_what_is_confirmed_is_kept(self):
        self.add_students(self.class_id, ["Ava Thompson", "Mary Jane", "Leo Martinez"])
        self.assertEqual(self.students(self.class_id), {})
        self.post(f"/app/academy/classes/{self.class_id}/students",
                  {"confirmed": "1", "asked": "3", "pick-0": "Ava T", "pick-1": "Mary Jane", "pick-2": ""})
        self.assertEqual(sorted(self.students(self.class_id)), ["Ava T", "Mary Jane"])

    def test_the_rules_for_a_full_name(self):
        for name in ("Ava Thompson", "Mary Jane", "Leo De La Cruz"):
            self.assertTrue(classrooms.looks_like_full_name(name), name)
        for name in ("Ava", "Noah K", "Jo B.", "Mary-Jane"):
            self.assertFalse(classrooms.looks_like_full_name(name), name)
        self.assertEqual(classrooms.suggest_short_name("Ava Thompson"), "Ava T")
        self.assertEqual(classrooms.suggest_short_name("Leo De La Cruz"), "Leo C")


# --- 5. Pilot's window ----------------------------------------------------------------------------

class TestPilotWords(unittest.TestCase):
    def test_omniarmor_s_own_suggestions_on_a_teacher_s_pages(self):
        config = read("omniarmor_app", "static", "pilot-omniarmor.js")
        for chip in ('C("Add students"', 'C("How do join codes work?"', 'C("What\'s overdue?"'):
            self.assertIn(chip, config)
        self.assertIn(r"/^\/app\/academy\/classes\/\d+(\/join-codes)?$/.test(path)", config)

    def test_a_plain_sentence_about_ai_keys(self):
        config = read("omniarmor_app", "static", "pilot-omniarmor.js")
        self.assertIn("An AI key is a private code from an AI company", config)
        self.assertIn("a grown-up gets one by signing up on that company's website", config)


# --- 6. Smaller things ---------------------------------------------------------------------------

class TestTradeDemos(AppTestCase):
    def test_each_trade_page_opens_its_own_demo(self):
        for slug, kind, brand in (("salons-and-barbershops", "salon", "Salon Aegizyn"),
                                  ("tattoo-and-piercing-studios", "tattoo", "Ink Aegizyn"),
                                  ("gyms-and-fitness-studios", "gym", "Gym Aegizyn")):
            page = self.client.get(f"/for/{slug}").data.decode()
            self.assertIn(f'href="/demo/{kind}"', page, slug)
            self.assertNotIn("pretend restaurant", page, slug)
            client = self.app.test_client()
            response = client.get(f"/demo/{kind}")
            self.assertEqual(response.status_code, 302)
            home = words(client.get("/app").data.decode())
            self.assertIn(brand, home, slug)
            self.assertNotIn("Resto Aegizyn", home, slug)
            industry = TRADE_INDUSTRY[kind]
            levels = {s.level for s in self._states(kind)}
            self.assertTrue({"BLOCKED", "WARNING", "CLEARED"} <= levels, (kind, levels))
            self.assertEqual(client.get(f"/app/industry/{industry}").status_code, 200)

    def _states(self, kind):
        with self.app.app_context():
            conn = demo_mode.sandbox()
            org = conn.execute("SELECT * FROM orgs WHERE id = ?", (demo_mode.facts()[kind]["org"],)).fetchone()
            return [s for s in states_for_org(conn, org) if s.industry_id == TRADE_INDUSTRY[kind]]


TRADE_INDUSTRY = {"salon": 52, "tattoo": 53, "gym": 54}


class TestLessonsTeachWhatTheyAsk(unittest.TestCase):
    def test_every_question_is_taught_in_its_own_lesson(self):
        company, ids = "Juniper Lane", [2, 30]
        for t in list(academy.TRACK_LIST) + [academy.CLASSROOM]:
            for w in t.topic_worlds + [academy.FINAL_WORLD]:
                for stage in range(1, t.stages(w) + 1):
                    cards = academy.story(t, w.number, stage, company, ids)
                    said = " ".join(f"{a} {b}" for a, b in cards).lower()
                    # 1.16.0: a first lesson no longer lists its quiz's answers before it starts. What
                    # its cards don't teach in so many words, its last card hints at instead (and the
                    # fact shows the moment the question is answered): tests/test_round7_fixes.py.
                    if stage == 1 and f"{academy.QUIZ_HINT.lower()}:" in said:
                        continue
                    for q in academy.quiz(t, w.number, stage, company, ids, "x"):
                        if q.kind == "match" and q.parts.get("pool"):
                            # 1.19.0: a matching game's words change each attempt: each one's meaning is taught.
                            for word in q.parts["left"]:
                                self.assertIn(f"{word} {dict(academy.GLOSSARY)[word]}".lower(), said, q.prompt)
                            continue
                        explain = q.explain.lower().strip(" .")
                        head, _, rest = q.explain.partition(": ")
                        self.assertTrue(explain in said or rest.lower().strip(" .") in said
                                        or academy._taught(q, said),
                                        f"{t.name} · {w.title} · stage {stage}: {q.prompt}")

    def test_a_later_stage_is_more_than_one_recap_card(self):
        t = academy.TRACKS["launchpad"]
        cards = academy.story(t, 2, 2, "Juniper Lane", [2])
        self.assertGreaterEqual(len(cards), 1 + academy.LESSON_QUESTIONS)
        self.assertNotIn("remember", cards[0][0])


class TestNoTrueWrongAnswers(unittest.TestCase):
    def test_the_review_script_finds_nothing(self):
        self.assertEqual(quiz_truth_review.review(), [])

    def test_rules_every_business_follows_are_never_a_wrong_answer_about_the_company(self):
        titles = {r.title for r in academy._unrelated_rules((2,))}
        for known in ("Hours worked records kept", "Fire extinguishers checked monthly", "Safety data sheets and training"):
            self.assertNotIn(known, titles)
        for i in academy.UNIVERSAL_INDUSTRIES:
            self.assertFalse(titles & {r.title for r in CATALOG[i]})

    def test_who_follows_an_employer_s_rule(self):
        import random
        q = academy._who_follows(random.Random(1), 30, CATALOG[30][0], "Employers & HR", academy._sharing(30, 1))
        self.assertEqual(q.options[q.answer], "Any business with employees")
        self.assertTrue(all(o.startswith("Only ") for n, o in enumerate(q.options) if n != q.answer))

    def test_the_script_flags_the_known_patterns(self):
        flags = quiz_truth_review.review([("Sams Taqueria", (2,))], [academy.TRACKS["launchpad"]])
        self.assertEqual(flags, [])
        original = academy.is_universal
        saved = academy.UNIVERSAL_INDUSTRIES
        caches = (academy._family_pool, academy._final_pool, academy._industry_pool)
        try:
            # The old generator, which let "Hours worked records kept" be a wrong answer.
            academy.is_universal = lambda i, r: False
            academy.UNIVERSAL_INDUSTRIES = frozenset()
            for cache in caches:
                cache.cache_clear()
            flags = quiz_truth_review.review([("Sams Taqueria", (2,))], [academy.TRACKS["launchpad"]])
        finally:
            academy.is_universal = original
            academy.UNIVERSAL_INDUSTRIES = saved
            for cache in caches:
                cache.cache_clear()
        kinds = {f[0] for f in flags}
        self.assertIn("universal", kinds)
        self.assertIn("only-one", kinds)


class TestHonestResults(unittest.TestCase):
    def test_so_close_only_when_it_was(self):
        self.assertEqual(result_band(3, 5, 4, 0), "So close! Try again")
        self.assertNotIn("close", result_band(0, 5, 4, 0).lower())
        self.assertNotIn("close", result_band(1, 5, 4, 0).lower())
        self.assertEqual(result_band(5, 5, 4, 3), "Perfect score!")
        self.assertEqual(result_band(4, 5, 4, 2), "Stage complete!")
        for p in armo.PERSONALITIES.values():
            for line in retry_lines(p, 0, 4):
                self.assertNotRegex(line, r"(?i)\b(so close|almost)\b", p.name)


class TestEntriesAndEmails(AppTestCase):
    def setUp(self):
        super().setUp()
        self.signup(industries=(2,))

    def today(self):
        # The workspace's own today, not this machine's: just after midnight UTC
        # it is still yesterday in the workspace's time zone, and its "today"
        # would be a date in the future.
        with self.db() as conn:
            return org_today(conn.execute("SELECT * FROM orgs WHERE id = 1").fetchone()).isoformat()

    def add(self, label, day):
        return self.post("/app/industry/2/rule/date_marking/entries", {"action": "add", "label": label, "date": day})

    def test_a_food_batch_says_made_or_opened_not_last_done(self):
        self.add("Pico de gallo", self.today())
        page = self.client.get("/app/industry/2").data.decode()
        self.assertIn("Made or opened ", page)
        self.assertNotIn("Last done ", page)
        self.assertIn("The date it was made or opened", page)

    def test_a_duplicate_name_is_refused_kindly(self):
        self.add("Pico de gallo", self.today())
        self.add("Pico de gallo", self.today())
        self.add("pico de GALLO", self.today())
        with self.db() as conn:
            count = conn.execute("SELECT COUNT(*) FROM check_entries WHERE rule_key = 'date_marking'").fetchone()[0]
            first = conn.execute("SELECT label FROM items WHERE rule_key = 'date_marking'").fetchone()["label"]
        self.assertEqual((first, count), ("Pico de gallo", 0))
        page = words(self.client.get("/app/industry/2").data.decode())
        self.assertIn("There's already a food batch or container called pico de GALLO", page)

    def test_each_email_says_who_it_went_to_by_role(self):
        with self.db() as conn:
            owner = conn.execute("SELECT id FROM users").fetchone()["id"]
            member = conn.execute("INSERT INTO users (email, name, password_hash, created_at) VALUES"
                                  " ('cook@example.com', 'Jo Cook', '!', ?)", (now_iso(),)).lastrowid
            conn.execute("INSERT INTO memberships (user_id, org_id, role, created_at) VALUES (?, 1, 'member', ?)",
                         (member, now_iso()))
            for uid, address in ((owner, "owner@example.com"), (member, "cook@example.com")):
                conn.execute("INSERT INTO notifications (org_id, user_id, created_at, kind, recipient, subject, body,"
                             " status) VALUES (1, ?, ?, 'reminder', ?, 'Aegizyn: 1 overdue', 'x', 'logged')",
                             (uid, now_iso(), address))
            conn.commit()
        page = self.client.get("/app/notifications").data.decode()
        self.assertIn("To you (the owner)", page)
        self.assertIn("To a team member", page)
        self.assertNotIn("cook@example.com", page)


class TestCountdownWords(unittest.TestCase):
    def test_a_license_countdown_reads_plainly(self):
        rule = find_rule(28, "license_current")
        message = evaluate(rule, 41.0)[2]
        self.assertNotIn("0 days minimum", message)
        self.assertIn("41 days left before the deadline", message)
        self.assertIn("1 day past the deadline", evaluate(rule, -1.0)[2])
        self.assertIn("left before the deadline", evaluate(rule, 120.0)[2])

    def test_other_minimums_and_limits(self):
        self.assertIn("close to the 135°F minimum (it warns at 140°F or less)",
                      evaluate(find_rule(2, "hot_holding"), 138.0)[2])
        self.assertIn("exactly the 135°F minimum", evaluate(find_rule(2, "hot_holding"), 135.0)[2])
        self.assertIn("close to the 7-day limit (it warns from 6 days)", evaluate(find_rule(2, "date_marking"), 6.0)[2])


class TestErrorReportPaths(unittest.TestCase):
    def test_a_virtual_environment_inside_the_project_is_still_a_library(self):
        inside = os.path.join(errormail.ROOT, ".venv", "lib", "python3.11", "site-packages", "flask", "app.py")
        self.assertEqual(errormail.relative(inside), os.path.join("flask", "app.py"))
        own = os.path.join(errormail.ROOT, "omniarmor_app", "views.py")
        self.assertEqual(errormail.relative(own), os.path.join("omniarmor_app", "views.py"))
        text = errormail.scrub(f'File "{inside}", line 3')
        self.assertNotIn("site-packages", text)
        self.assertNotIn(".venv", text)


class TestNoInlineCode(unittest.TestCase):
    def test_the_new_templates_keep_the_strict_policy(self):
        for name in ("academy/class.html", "app/notifications.html", "app/_entries.html", "demo/index.html",
                     "trade.html"):
            text = read("omniarmor_app", "templates", name)
            self.assertNotRegex(text, r"\sstyle=|<script(?![^>]*\bsrc=)", name)

    def test_the_review_script_runs_on_its_own(self):
        result = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "quiz_truth_review.py"), "--quick"],
                                capture_output=True, text=True, timeout=120)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("0 flags.", result.stdout)


if __name__ == "__main__":
    unittest.main()
