"""1.15.0: what a strict fifth review found, fixed. Pictures of the app on the
public pages and a "How it works"; a Menu button and a real Start free
button on a phone; quizzes where the right answer's length gives nothing
away; Armo keeping clear of the page as Pilot does, and Pilot reachable
while he shows; Pilot on a teacher's class page, join codes and guide (with
students' names kept from it); a side bar on a computer and two columns on
the overview; a kid's lesson on a grown-up's device without the grown-up
tabs; and plainer words in five places."""

import collections
import html
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))
from test_classroom_review import SchoolCase, words  # noqa: E402
from test_demo_and_first_steps import DemoCase  # noqa: E402
from test_parent_view import ProgressCase  # noqa: E402
from test_webapp import AppTestCase  # noqa: E402

import quiz_truth_review  # noqa: E402
from omniarmor_app import academy, armo, pilot, shots  # noqa: E402
from omniarmor_app.catalog import INDUSTRIES  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATIC = os.path.join(ROOT, "omniarmor_app", "static")


def read(*parts):
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as f:
        return f.read()


# --- 1. Pictures of the app, How it works, the phone's menu -------------------------------------

PUBLIC = {"/": "biz", "/classrooms": "class", "/for/salons-and-barbershops": "salon",
          "/for/tattoo-and-piercing-studios": "tattoo", "/for/gyms-and-fitness-studios": "gym",
          "/for/shops-and-retail-stores": "shop", "/for/schools": "school"}


class TestPicturesOnThePublicPages(AppTestCase):
    def pictures(self, page):
        return re.findall(r'<img src="(/static/shots/[^"?]+)(?:\?[^"]*)?" width="(\d+)" height="(\d+)" alt="([^"]+)"', page)

    def test_each_public_page_shows_the_app_beside_its_headline_and_how_it_works(self):
        for path, kind in PUBLIC.items():
            page = self.client.get(path).data.decode()
            self.assertIn(f'data-hero-shot="{kind}"', page, path)
            self.assertIn(f'data-how-it-works="{kind}"', page, path)
            hero = page[page.index('<div class="hero-split">'):page.index('data-how-it-works')]
            self.assertLess(hero.index('<section class="hero">'), hero.index("data-hero-shot"), path)
            steps = page[page.index("data-how-it-works"):]
            steps = steps[:steps.index("</section>")]
            self.assertEqual(steps.count("<li>"), 3, path)
            self.assertEqual(len(self.pictures(steps)), 3, path)
            self.assertGreaterEqual(len(self.pictures(page)), 4, path)

    def test_the_pictures_are_small_webp_files_with_their_size_and_words(self):
        for path in PUBLIC:
            for src, width, height, alt in self.pictures(self.client.get(path).data.decode()):
                file = os.path.join(STATIC, src[len("/static/"):])
                self.assertTrue(os.path.exists(file), src)
                self.assertTrue(src.endswith(".webp"), src)
                self.assertLess(os.path.getsize(file), 64_000, src)   # 1.16.0: twice the size, still small
                self.assertEqual(shots._size(file), (int(width), int(height)), src)
                self.assertGreater(int(width), 300, src)
                self.assertGreater(len(alt), 30, src)
        # Every picture in the folder is used, and none is a mock-up: the demo's own pages.
        folder = sorted(os.listdir(os.path.join(STATIC, "shots")))
        used = {os.path.basename(src) for p in PUBLIC for src, *_ in self.pictures(self.client.get(p).data.decode())}
        self.assertEqual(set(folder), used)

    def test_a_trade_page_shows_its_own_demo(self):
        page = self.client.get("/for/gyms-and-fitness-studios").data.decode()
        self.assertIn("/static/shots/gym-overview.webp", page)
        self.assertNotIn("biz-overview", page)
        school = self.client.get("/for/schools").data.decode()
        self.assertIn("/static/shots/school-checklist.webp", school)   # 1.16.0: the school checklist itself
        self.assertNotIn("-overview.webp", school)

    def test_the_price_and_trial_stay_in_the_first_screen(self):
        page = self.client.get("/").data.decode()
        hero = page[page.index('<section class="hero">'):page.index("data-hero-shot=")]
        self.assertIn("free trial", hero)
        self.assertIn("$", hero)

    def test_the_pictures_keep_the_strict_policy(self):
        for name in ("_shots.html", "home.html", "trade.html", "academy_schools.html", "base.html"):
            self.assertNotRegex(read("omniarmor_app", "templates", name), r"\sstyle=|<script(?![^>]*\bsrc=)", name)


class TestThePhoneMenu(AppTestCase):
    def test_a_menu_button_and_a_real_start_free_button(self):
        page = self.client.get("/").data.decode()
        nav = page[page.index('<nav class="nav"'):page.index("</nav>")]
        self.assertIn('<a class="btn nav-cta" href="/signup" data-start-free>Start free</a>', nav)
        self.assertRegex(nav, r'<details class="nav-menu" data-nav-menu>\s*<summary aria-label="Menu">')
        drop = nav[nav.index('class="nav-drop"'):]
        for link in ("Businesses", "Schools", "Kids", "Sign in"):
            self.assertIn(f">{link}</a>", drop)
        css = read("omniarmor_app", "static", "app.css")
        self.assertIn(".nav a.btn{margin-left:6px;padding:0 18px;background:var(--blend)", css)
        phone = css[css.index("/* The top menu (1.15.0)"):]
        phone = phone[phone.index("@media (max-width:720px){"):]
        phone = phone[:phone.index("\n}\n")]
        self.assertIn(".nav-wide{display:none}", phone)
        self.assertIn(".nav-menu{display:block", phone)
        self.assertIn("min-height:44px", phone)

    def test_signed_in_the_menu_holds_the_checklists_and_sign_out(self):
        self.signup()
        page = self.client.get("/app").data.decode()
        drop = page[page.index('class="nav-drop"'):]
        drop = drop[:drop.index("</details>")]
        self.assertIn("Sign out", drop)
        self.assertNotIn("data-start-free", page)


# --- 2. Fair quizzes -----------------------------------------------------------------------------

class TestFairQuizzes(unittest.TestCase):
    def test_no_world_leans_on_the_longest_or_the_shortest_answer(self):
        flags = [f for f in quiz_truth_review.review() if f[0] == "shape"]
        self.assertEqual(flags, [], "\n".join(f"{w}: {p}" for _, w, p, _ in flags[:20]))

    def test_the_review_flags_the_shortest_answer_right_10_times_in_14(self):
        """The reviewer's own count: the shortest answer was right 10 of 14."""
        Q = academy.Question
        lopsided = [Q(f"Question {n}?", ["Yes, kindly", "No, never at all, not once", "Only on the quiet days"], 0, "x")
                    for n in range(10)]
        lopsided += [Q(f"Other {n}?", ["Ask a grown-up first", "Do it now", "Wait for the inspector"], 0, "x")
                     for n in range(4)]
        flags = quiz_truth_review.shape_flags("Test world", lopsided)
        self.assertEqual([f[0] for f in flags], ["shape"])
        self.assertIn("shortest option is right in 10 of 14", flags[0][2])
        self.assertEqual(quiz_truth_review.shape_flags("Fair world", lopsided[:3] + lopsided[10:]), [])
        # Amounts say nothing by their length, and true-or-false has two fixed words.
        money = [Q(f"Cost {n}?", ["$1", "$100", "$10,000"], 0, "x") for n in range(14)]
        self.assertEqual(quiz_truth_review.shape_flags("Math", money), [])

    def test_wrong_answers_are_about_as_long_as_the_right_one_and_take_turns(self):
        """The Rule Quests and Business Words pick wrong answers just shorter and
        just longer than the right one, so where the right one sits by length
        turns round: shortest, in between, longest."""
        places = collections.Counter()
        ratios = []
        for industry_id in list(INDUSTRIES)[:20]:
            for q in academy._industry_pool(industry_id):
                for question in q:
                    if question.kind != "choice" or quiz_truth_review._worded(question) is False:
                        continue
                    places[academy._length_place(question)] += 1
                    right = len(question.options[question.answer])
                    ratios += [len(o) / right for n, o in enumerate(question.options) if n != question.answer]
        total = sum(places.values())
        # In between also counts a tie for shortest or longest.
        for place, most in ((0, 0.4), (1, 0.5), (2, 0.4)):
            self.assertGreater(places[place] / total, 0.25, places)
            self.assertLess(places[place] / total, most, places)
        ratios.sort()
        self.assertGreater(ratios[len(ratios) // 2], 0.8)
        self.assertLess(ratios[len(ratios) // 2], 1.25)

    def test_the_right_answer_s_position_is_shuffled(self):
        t = academy.CLASSROOM
        slots = collections.Counter()
        for seed in range(30):
            for q in academy.quiz(t, t.topic_worlds[0].number, 1, "x", (), f"slot-{seed}"):
                if q.kind == "choice":
                    slots[q.answer] += 1
        self.assertEqual(set(slots), {0, 1, 2})
        self.assertGreater(min(slots.values()) / sum(slots.values()), 0.2)


# --- 3. Helpers on phones, Pilot's teacher pages and visitors' title ------------------------------

class TestArmoKeepsClear(AppTestCase):
    def test_armo_shrinks_into_his_corner_where_he_would_sit_on_the_page(self):
        js = read("omniarmor_app", "static", "armo.js")
        for said in ("function keepClear()", "elementsFromPoint", 'classList.toggle("armo-tucked", busy())',
                     '".tag, .top-n, .msg, .flash', 'addEventListener("scroll", keepClear'):
            self.assertIn(said, js)
        css = read("omniarmor_app", "static", "app.css")
        self.assertIn(".companion.armo-tucked .companion-armo svg{width:36px;height:36px}", css)
        # 1.16.0: on a phone he no longer takes room down the page's right; he has a reserved corner above
        # the tab bar, where he keeps his size (tests/test_round7_fixes.py).
        self.assertNotIn("main > .wrap{padding-right:max(42px", css)
        # 1.18.0: the corner's framed box is gone, so tucked he steps aside to the screen's edge instead.
        self.assertNotIn("body.has-tabs .companion.armo-tucked .companion-armo svg{width:52px;height:52px}", css)
        self.assertIn("body.has-tabs .companion.armo-tucked{right:max(3px,env(safe-area-inset-right))}", css)

    def test_ask_pilot_in_armo_s_bubble_where_the_page_has_pilot(self):
        self.signup()
        page = self.client.get("/app").data.decode()
        self.assertIn('data-ask-pilot>Ask Pilot</button>', page)
        js = read("omniarmor_app", "static", "armo.js")
        self.assertIn("window.Pilot.open()", js)
        # Academy pages have neither, and the Armo page has no Armo.
        self.assertNotIn("data-ask-pilot", self.client.get("/app/armo").data.decode())

    def test_blocked_and_overdue_are_said_plainly(self):
        self.signup()
        page = html.unescape(self.client.get("/app").data.decode())
        alert = re.search(r"data-alert='([^']*)'", page).group(1)
        self.assertEqual(alert, '["' + '", "'.join(armo.CALM_ALERT) + '"]')
        self.assertIn('data-fix="Open it"', page)
        for line in armo.CALM_ALERT:
            self.assertNotRegex(line, r"!|joke|comedy|ugh|beep|arr", line)


class TestPilotForTeachersAndVisitors(SchoolCase):
    def test_the_class_page_join_codes_and_guide_are_teacher_pages(self):
        for endpoint in ("classes.class_page", "classes.join_codes", "public.class_guide"):
            self.assertIn(endpoint, pilot.TEACHER_PAGES)

    def test_students_names_are_kept_from_pilot_on_those_pages(self):
        self.teacher_signup()
        class_id = self.add_class()
        self.add_students(class_id, ["Maya", "Leo"])
        page = self.client.get(f"/app/academy/classes/{class_id}").data.decode()
        self.assertIn('id="pilot-core"', page)
        self.assertIn('data-class-progress data-pilot-private', page)
        self.post(f"/app/academy/classes/{class_id}/join-codes", {"for": "missing"})
        codes = self.client.get(f"/app/academy/classes/{class_id}/join-codes").data.decode()
        self.assertIn('id="pilot-core"', codes)
        self.assertIn("data-join-codes data-pilot-private", codes)
        # Every place a name shows is inside something private (or a box Pilot never reads).
        for name in ("Maya", "Leo"):
            for at in [m.start() for m in re.finditer(name, codes)]:
                before = codes[:at]
                self.assertGreater(before.rfind("data-pilot-private"), before.rfind("</ul>"), name)

    def test_visitors_are_greeted_as_omniarmor_s_helper(self):
        js = read("omniarmor_app", "static", "pilot-omniarmor.js")
        self.assertEqual(js.count('tagline: "Your Aegizyn helper",'), 2)
        self.assertNotIn('visitor: {\n      tagline: "Your checklist helper"', js)


# --- 4. Pilot's window: icons and "AI key" ------------------------------------------------------

class TestAIKeyWords(unittest.TestCase):
    def test_app_text_says_ai_key(self):
        found = []
        for folder, _, files in os.walk(os.path.join(ROOT, "omniarmor_app")):
            if os.sep + "static" + os.sep + "pilot" in folder + os.sep or "__pycache__" in folder:
                continue
            for name in files:
                if name.endswith((".html", ".js")):
                    text = read(os.path.join(folder, name))
                    found += [f"{name}: {m}" for m in re.findall(r"[^.\n]{0,30}\b(?:API key|your own key|your key)\b",
                                                                  text, re.I)]
        self.assertEqual(found, [])

    def test_print_certificates_is_not_a_chart(self):
        js = read("omniarmor_app", "static", "pilot-omniarmor.js")
        # 1.17.0: a link to the class's certificates (core 1.4.0), still with the paper icon.
        self.assertIn('LINK("copy", "Print certificates"', js)
        self.assertIn('keyNoteShort: "AI keys are for grown-ups (18+).",', js)


# --- 5. A computer: a side bar, and two columns on the overview -----------------------------------

class TestComputerLayout(AppTestCase):
    def test_the_sections_are_a_side_bar_on_a_computer(self):
        css = read("omniarmor_app", "static", "app.css")
        wide = css[css.index("@media (min-width:1100px){\n  body.has-tabs"):]
        wide = wide[:wide.index("\n}\n")]
        self.assertIn("body.has-tabs:not(.lesson-view){padding-left:216px}", wide)
        self.assertIn(".tabbar{top:0;right:auto;width:216px;flex-direction:column", wide)
        self.assertIn(".pilot-root{--pilot-gap:16px}", wide)

    def test_needs_attention_and_coming_due_side_by_side(self):
        self.signup()
        page = self.client.get("/app").data.decode()
        cols = page[page.index('<div class="ov-cols">'):]
        self.assertLess(cols.index("data-needs-attention"), cols.index("data-coming-due"))
        self.assertLess(cols.index("data-coming-due"), cols.index("Your industries"))
        self.assertIn(".ov-cols{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr)",
                      read("omniarmor_app", "static", "app.css"))


# --- 6. A kid's lesson on a grown-up's device ------------------------------------------------------

class TestLessonsOnAGrownUpsDevice(ProgressCase):
    def test_a_lesson_has_only_back_to_map(self):
        for path in ("/app/academy/1/world/1", "/app/academy/1/world/1/stage/1", "/app/academy/1/practice"):
            page = self.client.get(path).data.decode()
            self.assertIn("data-lessonbar", page, path)
            self.assertIn('href="/app/academy/1"', page[page.index("data-lessonbar"):], path)
            self.assertIn("Back to map", page, path)
            tabs = page[page.index("data-lessonbar"):]
            tabs = tabs[:tabs.index("</nav>")]
            for grown_up in ("Report", "History", "Reminders", "Settings"):
                self.assertNotIn(f"<span>{grown_up}</span>", tabs, path)
            self.assertIn("lesson-view", page[:page.index("<a class=\"skip\"")], path)
        # The result of a lesson too.
        result = self.play(1, 1, right=5)
        result = self.client.get(result.headers["Location"]).data.decode() if result.status_code == 302 else \
            result.data.decode()
        self.assertNotIn("<span>Report</span>", result)

    def test_the_grown_up_s_own_pages_keep_their_tabs(self):
        # 1.18.0: the learner's map (/app/academy/1) is the kid's screen too (tests/test_round8_fixes.py).
        for path in ("/app", "/app/academy", "/app/academy/1/progress"):
            page = self.client.get(path).data.decode()
            self.assertNotIn("data-lessonbar", page, path)
            self.assertIn("<span>Report</span>", page, path)


# --- 7. Words -----------------------------------------------------------------------------------

class TestWords(SchoolCase):
    def setUp(self):
        super().setUp()
        self.teacher_signup()
        self.class_id = self.add_class()
        self.page_url = f"/app/academy/classes/{self.class_id}"

    def test_the_first_codes_don_t_speak_of_slips_already_handed_out(self):
        self.add_students(self.class_id, ["Ava", "Liam"])
        response = self.post(f"{self.page_url}/join-codes", {"for": "missing"}, follow_redirects=True)
        said = words(response.data.decode())
        self.assertIn("Made 2 codes for Ava and Liam. Print this page and cut it into slips.", said)
        self.assertNotIn("The slips you already handed out still work", said)
        self.add_students(self.class_id, ["Zoe"])
        later = words(self.post(f"{self.page_url}/join-codes", {"for": "missing"}, follow_redirects=True).data.decode())
        self.assertIn("Made a code for Zoe. The slips you already handed out still work.", later)

    def test_first_name_only_waits_until_the_teacher_decides(self):
        self.post(f"{self.page_url}/students", {"names": "Ava Thompson\nLiam"})
        self.assertEqual(set(self.students(self.class_id)), {"Liam"})
        # Leaving the page and coming back: still asked, nothing dropped.
        page = words(self.client.get(self.page_url).data.decode())
        self.assertIn("First name only?", page)
        self.assertIn("Ava Thompson", page)
        self.assertIn("it waits here until you do", page)
        # Another name to check joins it.
        self.post(f"{self.page_url}/students", {"names": "Noah Kim"})
        page = self.client.get(self.page_url).data.decode()
        self.assertIn("Ava Thompson", page)
        self.assertIn("Noah Kim", page)
        # The teacher decides: Ava T is added, Noah isn't, and the question is gone.
        self.post(f"{self.page_url}/students", {"confirmed": "1", "asked": "2", "pick-0": "Ava T", "pick-1": ""})
        self.assertEqual(set(self.students(self.class_id)), {"Liam", "Ava T"})
        self.assertNotIn("First name only?", self.client.get(self.page_url).data.decode())

    def test_dont_add_any_of_them(self):
        self.post(f"{self.page_url}/students", {"names": "Ava Thompson\nNoah Kim"})
        self.post(f"{self.page_url}/students", {"confirmed": "1", "asked": "2", "pick-0": "Ava T", "pick-1": "Noah K",
                                               "skip": "all"})
        self.assertEqual(self.students(self.class_id), {})
        self.assertNotIn("First name only?", self.client.get(self.page_url).data.decode())


class TestTheDemoStartsFolded(DemoCase):
    def test_update_several_at_once_starts_folded_in_the_demo(self):
        self.open_demo()
        page = self.client.get("/app/industry/2").data.decode()
        self.assertRegex(page, r'<details class="bulk no-print">\s*<summary class="bulk-title">Update several at once')


# --- Pilot core 1.3.0, the version and the changelog ---------------------------------------------

class TestCoreAndVersion(unittest.TestCase):
    def test_every_core_file_is_core_1_3_0_or_later(self):
        # 1.17.0 moved to core 1.4.0 (tests/test_core140.py checks it exactly).
        folder = os.path.join(STATIC, "pilot")
        names = sorted(n for n in os.listdir(folder) if n.endswith((".js", ".css")))
        self.assertEqual(len(names), 13)
        for name in names:
            with open(os.path.join(folder, name), encoding="utf-8") as f:
                self.assertRegex(f.readline(), r"^(//|/\*) Pilot core 1\.([3-9]|[1-9]\d)\.\d+ · ", name)

    def test_version_and_changelog(self):
        from omniarmor_app.version import __version__
        self.assertGreaterEqual(tuple(map(int, __version__.split("."))), (1, 15, 0))
        log = read("CHANGELOG.md")
        top = log[log.index("## 1.15.0"):log.index("## 1.14.1")]
        for said in ("Pilot core 1.3.0", "How it works", "Menu button", "Back to map", "Ask Pilot", "45%"):
            self.assertIn(said, top)


if __name__ == "__main__":
    unittest.main()
