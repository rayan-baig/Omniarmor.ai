"""1.9.0: what an honest product review found, fixed. Classroom lessons
through a pretend class business, a school's own plan page and sign-up, two
audiences kept apart, small businesses first in the industry lists, no dead
end without online payment, adding students that keeps what was typed, an
honest Classroom track with a teacher guide, plain menu labels, smaller
fixes, and fonts served from the app itself."""

import html
import os
import re
import sqlite3
import sys
import unittest
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_webapp import PASSWORD, AppTestCase  # noqa: E402

from omni_armor_rules import CATALOG  # noqa: E402
from omniarmor_app import academy, classrooms, plans, trades  # noqa: E402
from omniarmor_app.catalog import INDUSTRIES  # noqa: E402
from omniarmor_app.db import MIGRATIONS, migrate  # noqa: E402
from omniarmor_app.security import CSP  # noqa: E402
from omniarmor_app.tracking import format_quantity  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATIC = os.path.join(ROOT, "omniarmor_app", "static")
SCHOOL_NAME = "Test Middle School"
SCHOOL = trades.SCHOOL_INDUSTRY
OLD_LABELS = ("HQ", "Intel", "Vault", "Radar", "Armory")


def words(page):
    return " ".join(re.sub(r"<[^>]+>", " ", html.unescape(page)).split())


class SchoolCase(AppTestCase):
    """A teacher who signed up through the teacher sign-up, with a class."""

    def teacher_signup(self, client=None, email="teacher@example.com"):
        return self.post("/signup", {"name": "Jordan Teacher", "email": email, "password": PASSWORD,
                                     "org_name": SCHOOL_NAME, "timezone": "America/Chicago", "then": "classes"},
                         client=client)

    def org(self):
        with self.db() as conn:
            return conn.execute("SELECT * FROM orgs ORDER BY id LIMIT 1").fetchone()

    def add_class(self, name="Room 12"):
        response = self.post("/app/academy/classes", {"name": name})
        return int(response.headers["Location"].rsplit("/", 1)[1])

    def add_students(self, class_id, names):
        return self.post(f"/app/academy/classes/{class_id}/students", {"names": "\n".join(names)})

    def students(self, class_id):
        with self.db() as conn:
            return {r["nickname"]: r for r in conn.execute("SELECT * FROM learners WHERE class_id = ?", (class_id,))}


# --- 1. The Academy in a classroom ---------------------------------------------------------

class TestClassroomFraming(SchoolCase):
    def setUp(self):
        super().setUp()
        self.teacher_signup()
        self.class_id = self.add_class()
        self.add_students(self.class_id, ["Maya"])
        self.maya = self.students(self.class_id)["Maya"]

    def test_a_student_learns_through_the_class_business_never_a_family_company(self):
        self.assertEqual(self.maya["track"], academy.CLASSROOM.key)
        first = academy.CLASSROOM.topics[0]
        page = words(self.client.get(f"/app/academy/{self.maya['id']}/world/{first}/stage/1").data.decode())
        self.assertIn(academy.CLASS_BUSINESS, page)
        self.assertNotIn("family", page.lower())
        self.assertNotIn(f"help lead {SCHOOL_NAME}", page)
        self.assertNotIn(f"Your family's company is {SCHOOL_NAME}", page)

    def test_no_lesson_of_the_track_treats_a_school_as_a_wrong_answer_or_names_the_school(self):
        t = academy.CLASSROOM
        for w in t.topic_worlds + [academy.FINAL_WORLD]:
            for stage in range(1, t.stages(w) + 1):
                questions = academy.quiz(t, w.number, stage, SCHOOL_NAME, [SCHOOL], f"s-{w.number}-{stage}")
                cards = academy.story(t, w.number, stage, SCHOOL_NAME, [SCHOOL])
                text = " ".join([c for card in cards for c in card]
                                + [q.prompt + " " + " ".join(q.options) + " " + q.explain for q in questions])
                self.assertNotIn(SCHOOL_NAME, text, w.title)
                self.assertNotRegex(text, r"(?i)your family|family's company|omniarmor", w.title)
                for q in questions:
                    wrong = [o for n, o in enumerate(q.options) if n != q.answer]
                    self.assertFalse(any(re.search(r"(?i)\bschool\b|kids go to learn", o) for o in wrong),
                                     q.prompt)

    def test_the_family_version_stays_for_a_business(self):
        questions = academy.family_pool(academy.TRACKS["launchpad"], 1, "Acme Bakery", [2])
        prompts = [q.prompt for q in questions]
        self.assertIn("What is the name of your family's company?", prompts)
        for q in questions:
            self.assertNotIn("A building where kids go to learn to read and write", q.options)
        cards = academy.story(academy.TRACKS["launchpad"], 1, 1, "Acme Bakery", [2])
        self.assertIn("Someday you might help lead Acme Bakery.", " ".join(text for _, text in cards))

    def test_a_school_workspace_has_no_family_learners_page(self):
        response = self.client.get("/app/academy")
        self.assertTrue(response.headers["Location"].endswith("/app/academy/classes"))

    def test_a_student_cant_switch_to_a_family_track(self):
        self.post(f"/app/academy/{self.maya['id']}/track", {"track": "titan"})
        self.assertEqual(self.students(self.class_id)["Maya"]["track"], academy.CLASSROOM.key)


# --- 2. and 3. A teacher's sign-up and plan page --------------------------------------------

class TestTeacherSignupAndPlans(SchoolCase):
    def test_the_teacher_signup_is_its_own(self):
        page = self.client.get("/signup?industry=51&then=classes").data.decode()
        text = words(page)
        self.assertNotIn('name="industries"', page)
        self.assertNotIn("Your industries", text)
        for label in ("Your name", "School email", "Password", "School name"):
            self.assertIn(label, text)
        self.assertIn(f"{self.app.config['CLASSROOM_PILOT_DAYS']}-day free trial", text)
        self.assertNotIn("Free for 14 days", text)
        self.assertNotIn("days, no card needed. Pick your industries", text)

    def test_signing_up_makes_a_school_workspace_with_the_pilot_on(self):
        response = self.teacher_signup()
        self.assertTrue(response.headers["Location"].endswith("/app/academy/classes"))
        org = self.org()
        self.assertEqual(org["kind"], "school")
        self.assertTrue(classrooms.is_class_workspace(org))
        self.assertEqual(plans.pilot_status(org)["state"], "active")
        with self.db() as conn:
            self.assertEqual([r[0] for r in conn.execute("SELECT industry_id FROM org_industries")], [SCHOOL])
        # One countdown: the free time ends with the pilot.
        self.assertEqual(org["academy_trial_ends"], org["pilot_ends_at"])

    def test_a_teacher_sees_only_the_classroom_plans_with_one_pilot_countdown(self):
        self.teacher_signup()
        text = words(self.client.get("/app/plan").data.decode())
        self.assertIn(f"{plans.CLASSROOM.name} {plans.CLASSROOM.yearly_price}", text)
        self.assertIn(f"{plans.SCHOOL.name} {plans.SCHOOL.yearly_price}", text)
        days = self.app.config["CLASSROOM_PILOT_DAYS"]
        self.assertIn(f"Free trial: {days} days left", text)
        for business in (plans.PRO.price, plans.PLUS.price, plans.BUNDLE_NAME, "Pro", "Plus", "14 days"):
            self.assertNotIn(business, text)
        settings = words(self.client.get("/app/settings").data.decode())
        self.assertIn(f"Free trial: {days} days left", settings)
        self.assertNotIn("everything in Plus", settings)

    def test_without_online_payment_the_school_plan_page_says_who_to_write_to(self):
        self.teacher_signup()
        page = self.client.get("/app/plan").data.decode()
        self.assertIn('href="mailto:help@mtrxhorizyn.com?subject=Classroom%20for%20', page)


# --- 4. Two audiences -------------------------------------------------------------------------

class TestTwoAudiences(AppTestCase):
    def test_schools_have_their_own_menu_entry_and_demo(self):
        home = self.client.get("/").data.decode()
        self.assertRegex(home, r'<a href="/classrooms"[^>]*>Schools</a>')
        schools = self.client.get("/for/schools").data.decode()
        self.assertIn('href="/demo/classroom"', schools)
        self.assertNotIn('href="/demo/business"', schools)
        self.assertNotIn("pretend restaurant", schools)

    def test_the_bundle_only_where_it_fits(self):
        self.assertNotIn(plans.BUNDLE_NAME, words(self.client.get("/").data.decode()))
        self.assertNotIn(plans.BUNDLE_NAME, words(self.client.get("/for/salons-and-barbershops").data.decode()))
        self.assertIn(plans.BUNDLE_NAME, words(self.client.get("/industries/restoarmor").data.decode()))

    def test_the_landing_page_has_fewer_prices(self):
        page = self.client.get("/").data.decode()
        self.assertEqual(sorted(set(re.findall(r"\$\d[\d,]*", words(page)))),
                         sorted({f"${plans.PRO.dollars}", f"${plans.PLUS.dollars}"}))
        self.assertLess(page.count('class="row"'), 10)   # not the 51 industries any more


# --- 5. Small businesses first ----------------------------------------------------------------

class TestIndustryLists(AppTestCase):
    def test_the_industries_page_leads_with_small_businesses_and_keeps_every_industry(self):
        page = self.client.get("/industries").data.decode()
        lead = page[page.index("data-lead-trades"):page.index("More industries (starter lists)")]
        names = re.findall(r'<span class="title">([^<]+)</span>', html.unescape(lead))
        self.assertEqual(names, [name for name, _, _ in trades.LEAD_TRADES])
        self.assertTrue(6 <= len(names) <= 8)
        for info in INDUSTRIES.values():
            self.assertIn(f'href="/industries/{info["slug"]}"', page)
        self.assertEqual(len(INDUSTRIES), 54)
        self.assertEqual(sum(len(rules) for rules in CATALOG.values()), 540)

    def test_the_signup_lists_the_lead_trades_first_and_folds_the_rest(self):
        page = self.client.get("/signup").data.decode()
        lead = page[page.index("data-lead-industries"):page.index("data-more-industries")]
        self.assertEqual([int(v) for v in re.findall(r'name="industries" value="(\d+)"', lead)],
                         [i for i, _ in trades.SIGNUP_LEAD])
        self.assertIn("More industries (starter lists)", page)
        self.assertEqual(len(set(re.findall(r'name="industries" value="(\d+)"', page))), len(INDUSTRIES))


# --- 6. No dead end without online payment ----------------------------------------------------

class TestContactUs(AppTestCase):
    def test_contact_us_is_a_link_to_the_support_email(self):
        self.signup()
        page = self.client.get("/app/plan").data.decode()
        self.assertIn('<a href="mailto:help@mtrxhorizyn.com?subject=Start%20Pro">Contact us</a>', page)
        self.app.config["SUPPORT_EMAIL"] = "support@omniarmor.test"
        page = self.client.get("/app/plan").data.decode()
        self.assertIn('<a href="mailto:support@omniarmor.test?subject=Start%20Pro">Contact us</a>', page)
        self.assertIn('href="mailto:support@omniarmor.test"', self.client.get("/help").data.decode())

    def test_help_always_ends_with_a_contact(self):
        self.app.config["SUPPORT_EMAIL"] = ""
        self.assertIn('data-support-email>help@mtrxhorizyn.com</a>', self.client.get("/help").data.decode())


# --- 7. Adding students keeps what was typed ---------------------------------------------------

class TestAddingStudents(SchoolCase):
    def setUp(self):
        super().setUp()
        self.teacher_signup()
        self.class_id = self.add_class()

    def test_the_good_names_are_added_and_the_rest_come_back_with_the_reason(self):
        long_name = "Alexandria-Rose Featherstonehaugh"
        self.add_students(self.class_id, ["Maya"])
        response = self.add_students(self.class_id, ["Sam", long_name, "Maya", "Priya", "Priya", "jo@example.com"])
        # 1.28.0: back to the class page (post-redirect-get), with what wasn't added kept for it.
        self.assertEqual(response.status_code, 302)
        self.assertEqual(sorted(self.students(self.class_id)), ["Maya", "Priya", "Sam"])
        page = self.client.get(response.headers["Location"]).data.decode()
        text = words(page)
        self.assertIn("Added 2 students to Room 12.", text)
        self.assertIn(f"{long_name}: is longer than {classrooms.MAX_NAME} characters", text)
        self.assertIn("Maya: is already in this class", text)
        self.assertIn("Priya: was typed twice", text)
        self.assertIn("jo@example.com: looks like an email address", text)
        box = re.search(r'<textarea name="names"[^>]*>(.*?)</textarea>', page, re.S).group(1)
        self.assertEqual(html.unescape(box).split("\n"), [long_name, "Maya", "Priya", "jo@example.com"])

    def test_a_name_typed_twice_isnt_called_already_in_the_class(self):
        response = self.add_students(self.class_id, ["Maya", "maya"])
        text = words(self.client.get(response.headers["Location"]).data.decode())   # 1.28.0: post-redirect-get
        self.assertIn("maya: was typed twice", text)
        self.assertNotIn("already in this class", text)
        self.assertEqual(list(self.students(self.class_id)), ["Maya"])

    def test_sorting_names(self):
        parsed = classrooms.parse_names("Ana\nana\nBo\n" + "x" * 31)
        added, rejected, _ = classrooms.sort_names(parsed, {"bo"}, 5)
        self.assertEqual(added, ["Ana"])
        self.assertEqual([typed for typed, _ in rejected], ["ana", "Bo", "x" * 31])
        added, rejected, _ = classrooms.sort_names(classrooms.parse_names("A\nB\nC"), set(), 2)
        self.assertEqual(added, ["A", "B"])
        self.assertEqual(rejected, [("C", "didn't fit: the class is full")])


# --- 8. An honest Classroom track and the teacher guide -----------------------------------------

class TestClassroomTrack(AppTestCase):
    def setUp(self):
        super().setUp()
        self.t = academy.CLASSROOM

    def test_no_rule_quests_and_no_app_questions(self):
        self.assertFalse(self.t.rule_quests)
        self.assertFalse(any(self.t.has(w) for w in academy.INDUSTRY_WORLDS))
        self.assertNotIn(4, self.t.topics)   # the app's own lights ("Which light should OmniArmor show?")
        self.assertNotIn(5, self.t.topics)   # the app's reminders
        self.assertNotIn(1, self.t.topics)   # "your family's company"
        for n in self.t.topics:
            for q in academy.classroom_pool(n):
                self.assertNotRegex(q.prompt + " ".join(q.options) + q.explain, r"(?i)omniarmor|which light")

    def test_no_question_comes_back_in_a_later_lesson_of_the_same_world(self):
        for w in self.t.topic_worlds:
            seen = set()
            for stage in range(1, self.t.stages(w) + 1):
                for q in academy.quiz(self.t, w.number, stage, "x", [], f"seed-{stage}"):
                    self.assertNotIn(q.prompt, seen, (w.title, stage))
                    seen.add(q.prompt)
            self.assertEqual(len(seen), self.t.stages(w) * academy.LESSON_QUESTIONS)

    def test_the_level_count_is_what_a_student_plays(self):
        lessons = sum(len(academy.classroom_pool(n)) // academy.LESSON_QUESTIONS for n in self.t.topics)
        self.assertEqual(self.t.total, lessons + 1)
        self.assertLess(self.t.total, 200)
        for w in self.t.topic_worlds:
            self.assertLessEqual(self.t.stages(w), academy.CLASS_MAX_STAGES)
            self.assertGreaterEqual(self.t.stages(w), 3)

    def test_profit_is_only_ever_the_pretend_business_s(self):
        for n in self.t.topics:
            for q in academy.classroom_pool(n):
                text = q.prompt + " " + " ".join(q.options)
                if "profit" in text.lower():
                    self.assertNotRegex(text, r"(?i)\bschool\b", q.prompt)

    def test_the_teacher_guide(self):
        response = self.client.get("/classrooms/guide")
        self.assertEqual(response.status_code, 200)
        text = words(response.data.decode())
        self.assertIn("Teacher guide", text)
        for item in academy.class_guide():
            self.assertIn(item["world"].title, text)
            self.assertIn(f"{item['lessons']} lessons · about {item['minutes']} minutes", text)
            for question in item["talk"]:
                self.assertIn(question, text)
        self.assertIn('href="/classrooms/guide"', self.client.get("/classrooms").data.decode())
        self.assertIn("<loc>https://omniarmor.test/classrooms/guide</loc>", self.client.get("/sitemap.xml").data.decode())


class TestStudentMap(SchoolCase):
    def test_the_map_has_no_rule_quests_and_counts_honestly(self):
        self.teacher_signup()
        class_id = self.add_class()
        self.add_students(class_id, ["Maya"])
        maya = self.students(class_id)["Maya"]
        text = words(self.client.get(f"/app/academy/{maya['id']}").data.decode())
        self.assertNotIn("Rule Quest", text)
        self.assertIn(f"0 / {academy.CLASSROOM.total} lessons", text)
        self.assertIn("The Class Challenge", text)
        self.assertNotIn("change", re.sub(r"(?i)challenge", "", text.split(" lessons ")[0]))


# --- 9. Plain menu labels -------------------------------------------------------------------------

class TestMenuLabels(SchoolCase):
    def tab_labels(self, page):
        bar = page[page.index('class="tabbar'):]
        return re.findall(r"<span>([^<]+)</span>\s*</a>", bar)

    def test_a_business_sees_plain_labels(self):
        self.signup()
        page = self.client.get("/app").data.decode()
        self.assertEqual(self.tab_labels(page), ["Home", "Report", "History", "Reminders", "Academy", "Settings"])
        for old in OLD_LABELS:
            self.assertNotRegex(words(page), rf"\b{old}\b")

    def test_a_teacher_sees_the_school_name_not_a_checklist_brand(self):
        self.teacher_signup()
        page = self.client.get("/app/academy/classes").data.decode()
        top = page[page.index('<nav class="nav"'):page.index("</nav>")]
        self.assertIn(SCHOOL_NAME, top)
        self.assertNotIn("SchoolSafetyArmor", top)
        self.assertNotIn("RestoArmor", top)
        # The school checklist comes with Whole school: until then, no Checklist tab and no first
        # steps for it (the cafeteria check was one).
        self.assertEqual(self.tab_labels(page), ["Home", "Reminders", "History", "Settings"])
        self.assertIn('class="tab" href="/app/academy/classes"', page)
        overview = self.client.get("/app")
        self.assertTrue(overview.headers["Location"].endswith("/app/academy/classes"))
        classes = self.client.get("/app/academy/classes").data.decode()
        self.assertNotIn("Cafeteria", classes)
        result = self.app.test_cli_runner().invoke(args=["plan", "1", "school"])
        self.assertEqual(result.exit_code, 0, result.output)
        page = self.client.get("/app/academy/classes").data.decode()
        self.assertEqual(self.tab_labels(page), ["Home", "Checklist", "Reminders", "History", "Settings"])
        self.assertIn("Getting started", self.client.get("/app").data.decode())
        # Signing in lands a teacher on the classes page.
        self.post("/logout")
        response = self.post("/login", {"email": "teacher@example.com", "password": PASSWORD})
        self.assertTrue(response.headers["Location"].endswith("/app/academy/classes"))


# --- 10. Smaller fixes ------------------------------------------------------------------------------

class TestSmallerFixes(AppTestCase):
    def test_money_keeps_its_cents(self):
        self.assertEqual(format_quantity(15.5, "$"), "$15.50")
        self.assertEqual(format_quantity(15.0, "$"), "$15")
        self.assertEqual(format_quantity(10000.5, "$"), "$10,000.50")
        self.assertEqual(format_quantity(2.5, "h"), "2.5 h")

    def test_the_second_fold_out_is_rule_and_source(self):
        self.signup(industries=(2,))
        page = self.client.get("/app/industry/2").data.decode()
        self.assertIn("<summary>Rule and source</summary>", page)
        self.assertNotIn("<summary>Why it matters</summary>", page)

    def test_done_today_on_a_7_day_clock_promises_no_30_day_email(self):
        self.signup(industries=(SCHOOL,))
        response = self.post(f"/app/industry/{SCHOOL}/rule/cafeteria_food_safety", {"action": "done_today"})
        text = words(self.client.get(response.headers["Location"]).data.decode())
        self.assertIn("Reminder set: the team gets an email 7 and 1 day before it's due", text)
        self.assertNotIn("30, 7 and 1", text)

    def test_answer_yes_for_several_skips_nothing_where_yes_is_bad(self):
        self.signup(industries=(2,))
        response = self.post("/app/industry/2/bulk", {"bulk_action": "yes",
                                                     "keys": ["handwashing_sink", "sick_employee_excluded"]})
        text = words(self.client.get(response.headers["Location"]).data.decode())
        self.assertIn("Yes would mean a problem", text)
        self.assertIn("Nothing was changed", text)
        with self.db() as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM items").fetchone()[0], 0)
        response = self.post("/app/industry/2/bulk", {"bulk_action": "yes",
                                                     "keys": ["handwashing_sink", "certified_food_manager"]})
        self.assertIn("Updated 2 checks", words(self.client.get(response.headers["Location"]).data.decode()))

    def test_the_join_page_speaks_to_teachers_too(self):
        text = words(self.client.get("/kids").data.decode())
        self.assertIn("Ask your teacher or a grown-up for your code", text)
        self.assertIn("Teachers: print your class's join codes from the class page", text)

    def test_the_score_is_never_shown_counting_up_from_zero(self):
        with open(os.path.join(ROOT, "omniarmor_app", "templates", "academy", "result.html")) as f:
            self.assertNotIn("data-countup", f.read())
        with open(os.path.join(STATIC, "academy.js")) as f:
            self.assertNotIn('el.textContent = "0"', f.read())

    def test_armo_keeps_off_the_cards_on_a_phone(self):
        with open(os.path.join(STATIC, "app.css")) as f:
            css = f.read()
        phone = re.search(r"@media \(max-width:560px\)\{\.companion-armo svg\{[^@]*", css).group(0)
        self.assertIn("width:52px", phone)
        # 1.13.0: on a phone he no longer tucks at the edge; he shares one corner with Pilot, and only one of
        # them shows (tests/test_round5_fixes.py). 1.15.0: where he would sit on the page he shrinks into
        # that corner (armo-tucked), never off the edge (tests/test_round6_fixes.py).
        with open(os.path.join(STATIC, "armo.js")) as f:
            self.assertNotIn("translateX", f.read())


# --- 11. Fonts from the app itself -------------------------------------------------------------------

class TestSelfHostedFonts(SchoolCase):
    FILES = ["big-shoulders-display-700", "big-shoulders-display-800", "ibm-plex-sans-400", "ibm-plex-sans-500",
             "ibm-plex-sans-600", "ibm-plex-mono-400", "ibm-plex-mono-500", "baloo-2-600", "baloo-2-700",
             "baloo-2-800"]

    def test_no_page_loads_anything_from_google(self):
        self.teacher_signup()
        class_id = self.add_class()
        self.add_students(class_id, ["Maya"])
        maya = self.students(class_id)["Maya"]
        for path in ("/app/academy/classes", f"/app/academy/{maya['id']}",
                     f"/app/academy/{maya['id']}/world/{academy.CLASSROOM.topics[0]}/stage/1", "/kids"):
            response = self.client.get(path)
            page = response.data.decode()
            self.assertNotRegex(page, r"googleapis|gstatic", path)
            self.assertIn("font-src 'self'", response.headers["Content-Security-Policy"])
        anon = self.app.test_client()
        self.assertNotRegex(anon.get("/").data.decode(), r"googleapis|gstatic")
        # No Google fonts or pictures: the only Google address in the policy is the Gemini API in connect-src, for
        # Pilot with a visitor's own key (pilot.py), reached only when they chose Gemini.
        self.assertNotRegex(CSP, r"fonts\.googleapis|gstatic")
        self.assertEqual(re.findall(r"[\w.-]*google[\w.-]*", CSP), ["generativelanguage.googleapis.com"])
        self.assertIn("generativelanguage.googleapis.com", CSP.split("connect-src", 1)[1].split(";", 1)[0])

    def test_the_font_files_are_small_woff2_and_each_one_is_used(self):
        with open(os.path.join(STATIC, "app.css")) as f:
            app_css = f.read()
        with open(os.path.join(STATIC, "academy.css")) as f:
            academy_css = f.read()
        total = 0
        for name in self.FILES:
            path = os.path.join(STATIC, "fonts", f"{name}.woff2")
            with open(path, "rb") as f:
                self.assertEqual(f.read(4), b"wOF2", name)
            size = os.path.getsize(path)
            self.assertLess(size, 30_000, name)
            total += size
            self.assertIn(f"url(fonts/{name}.woff2)", academy_css if name.startswith("baloo") else app_css)
        self.assertLess(total, 220_000)
        self.assertEqual(sorted(f[:-6] for f in os.listdir(os.path.join(STATIC, "fonts")) if f.endswith(".woff2")),
                         sorted(self.FILES))
        self.assertTrue(os.path.exists(os.path.join(STATIC, "fonts", "LICENSE.txt")))
        response = self.client.get("/static/fonts/ibm-plex-sans-400.woff2")
        self.assertEqual(response.mimetype, "font/woff2")
        self.assertNotIn("Content-Encoding", response.headers)    # already compressed


# --- The upgrade -------------------------------------------------------------------------------------

class TestMigration(unittest.TestCase):
    def test_schools_already_here_become_school_workspaces_and_their_students_move_track(self):
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        previous = [m for m in MIGRATIONS if m[0] < 25]
        conn.execute("CREATE TABLE schema_version (version INTEGER NOT NULL)")
        for version, sql in previous:
            for statement in sql.replace("{TRIAL_DAYS}", "14").split(";"):
                if statement.strip():
                    conn.execute(statement)
            conn.execute("INSERT INTO schema_version (version) VALUES (?)", (version,))
        now = datetime.now(timezone.utc).isoformat()
        for org_id, industries in ((1, (51,)), (2, (2, 51)), (3, (2,))):
            conn.execute("INSERT INTO orgs (id, name, created_at) VALUES (?, ?, ?)", (org_id, f"Org {org_id}", now))
            for i in industries:
                conn.execute("INSERT INTO org_industries VALUES (?, ?)", (org_id, i))
            conn.execute("INSERT INTO classes (id, org_id, name, created_at) VALUES (?, ?, 'Room', ?)",
                         (org_id, org_id, now))
            conn.execute("INSERT INTO learners (org_id, nickname, avatar, created_at, class_id) VALUES (?, 'Kid',"
                         " 'star', ?, ?)", (org_id, now, org_id))
        conn.execute("INSERT INTO learners (org_id, nickname, avatar, created_at) VALUES (3, 'Fam', 'star', ?)",
                     (now,))
        conn.execute("UPDATE orgs SET pilot_started_at = ? WHERE id = 1", (now,))
        conn.commit()
        migrate(conn)
        kinds = {r["id"]: r["kind"] for r in conn.execute("SELECT id, kind FROM orgs")}
        self.assertEqual(kinds, {1: "school", 2: "business", 3: "business"})
        tracks = {r["nickname"] + str(r["org_id"]): r["track"] for r in conn.execute("SELECT * FROM learners")}
        self.assertEqual(tracks, {"Kid1": "classroom", "Kid2": "classroom", "Kid3": "classroom", "Fam3": "launchpad"})
        conn.close()


class TestSchoolTrialEndsWithThePilot(SchoolCase):
    def test_after_the_pilot_a_school_sees_the_school_wording(self):
        self.teacher_signup()
        past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat(timespec="seconds")
        with self.db() as conn:
            conn.execute("UPDATE orgs SET pilot_ends_at = ?, academy_trial_ends = ?", (past, past))
            conn.commit()
        # 1.12.0: the checklist page itself sends a teacher without Whole
        # school back to their classes, with a plain note.
        page = words(self.client.get("/app/industry/51", follow_redirects=True).data.decode())
        self.assertIn("The school safety checklist comes with the Whole school plan", page)
        self.assertNotIn("choose Pro or Plus", page)
        plan = words(self.client.get("/app/plan").data.decode())
        self.assertIn("Your free trial has ended", plan)


# --- 1.11.0: a strict re-review ---------------------------------------------------------------------

class TestSecondReviewFixes(SchoolCase):
    def test_the_grade_band_is_on_the_schools_page_the_guide_and_the_classroom_demo(self):
        for path in ("/classrooms", "/classrooms/guide", "/demo"):
            self.assertIn(academy.CLASS_GRADES, html.unescape(self.client.get(path).data.decode()), path)
        self.client.get("/demo/classroom")
        page = html.unescape(self.client.get("/app/academy/classes").data.decode())
        self.assertIn(f"written for {academy.CLASS_GRADES}", page)

    def test_a_class_student_s_progress_says_class_challenge(self):
        self.teacher_signup()
        class_id = self.add_class()
        self.add_students(class_id, ["Maya"])
        maya = self.students(class_id)["Maya"]
        page = html.unescape(self.client.get(f"/app/academy/{maya['id']}/progress").data.decode())
        self.assertIn("pass stage 1 of the Class Challenge", page)
        self.assertNotIn("Owner's Challenge", page)

    def test_pilot_means_only_the_robot(self):
        self.teacher_signup()
        for path in ("/app/academy/classes", "/app/plan", "/classrooms", "/help", "/signup?then=classes"):
            text = words(self.client.get(path).data.decode())
            self.assertNotRegex(text, r"(?i)\b(free|class|classroom) pilot\b|\bpilot report\b", path)

    def test_armo_and_pilot_keep_apart_without_touching_pilot_s_core(self):
        """1.11.1: Pilot core 1.1.0 (now 1.4.0) gives Armo room itself (yieldTo), so the
        armo-talking stopgap is gone. Armo stays bottom-left, and the core's
        files stay the shared core's, unchanged."""
        with open(os.path.join(STATIC, "app.css"), encoding="utf-8") as f:
            css = f.read()
        self.assertNotIn("armo-talking", css)
        self.assertRegex(css, r"\.companion\{position:fixed;left:")
        with open(os.path.join(STATIC, "armo.js"), encoding="utf-8") as f:
            self.assertNotIn("armo-talking", f.read())
        with open(os.path.join(STATIC, "pilot-omniarmor.js"), encoding="utf-8") as f:
            config = f.read()
        self.assertIn('yieldTo: [".companion"],', config)
        self.assertRegex(config, r'avoid: \[".tag", ".top-n", ".bundle", ".msg",')
        self.assertIn('".companion-bubble", ".companion-fix", ".companion-badge"', config)
        for name in os.listdir(os.path.join(STATIC, "pilot")):
            if name.endswith((".js", ".css")):
                with open(os.path.join(STATIC, "pilot", name), encoding="utf-8") as f:
                    self.assertRegex(f.readline(), r"^(//|/\*) Pilot core 1\.4\.3 · ", name)


if __name__ == "__main__":
    unittest.main()
