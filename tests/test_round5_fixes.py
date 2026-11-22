"""1.13.0: what a strict fourth review found, fixed. Join codes for students
added after the slips were printed (and the slips already handed out keep
working); a teacher's Settings without the business checklist; one lesson
count per track everywhere, with the Rule Quests shown apart; one helper in
one corner on a phone; the report as cards on a phone; one notice after
adding students; a compact demo bar; the shop demo led by ShopArmor; the
daily goal counting passes only; the demo's words naming the page's own
checklist; and a finished retry heading."""

import html
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_classroom_review import SchoolCase, words  # noqa: E402
from test_demo_and_first_steps import DemoCase, text  # noqa: E402
from test_parent_view import ProgressCase  # noqa: E402
from test_webapp import AppTestCase  # noqa: E402

from omniarmor_app import academy, demo_mode  # noqa: E402
from omniarmor_app.academy_views import result_band  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATIC = os.path.join(ROOT, "omniarmor_app", "static")
CODE = re.compile(r"KID-[A-Z0-9]{8}")


def read(*parts):
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as f:
        return f.read()


# --- 1. Students added after the codes were printed get a code -----------------------------------

class TestJoinCodesForNewStudents(SchoolCase):
    def setUp(self):
        super().setUp()
        self.teacher_signup()
        self.class_id = self.add_class()
        self.url = f"/app/academy/classes/{self.class_id}/join-codes"
        self.add_students(self.class_id, ["Ava", "Liam"])

    def codes(self):
        with self.db() as conn:
            return {r["nickname"]: r["code"] for r in conn.execute(
                "SELECT learners.nickname, join_codes.code FROM join_codes JOIN learners"
                " ON learners.id = join_codes.learner_id")}

    def test_new_students_get_codes_and_the_old_slips_keep_working(self):
        self.post(self.url, {"for": "missing"})
        printed = self.codes()
        self.assertEqual(set(printed), {"Ava", "Liam"})
        self.add_students(self.class_id, ["Zoe", "Max"])
        page = words(self.client.get(self.url).data.decode())
        self.assertIn("2 students have no code yet", page)
        self.assertIn("Make codes for them", page)
        self.assertIn("Make new codes for everyone", page)     # still there, apart and explained
        self.assertIn("the old slips stop working", page)
        class_page = words(self.client.get(f"/app/academy/classes/{self.class_id}").data.decode())
        self.assertIn("2 students have no code yet", class_page)
        self.post(self.url, {"for": "missing"})
        now = self.codes()
        self.assertEqual(set(now), {"Ava", "Liam", "Zoe", "Max"})
        for name, code in printed.items():
            self.assertEqual(now[name], code, name)            # the slips already handed out still work
        self.assertNotIn("no code yet", words(self.client.get(self.url).data.decode()))

    def test_a_form_without_a_choice_keeps_the_old_slips(self):
        self.post(self.url, {"for": "missing"})
        printed = self.codes()
        self.post(self.url)
        self.assertEqual(self.codes(), printed)

    def test_new_codes_for_everyone_replace_every_slip(self):
        self.post(self.url, {"for": "missing"})
        printed = self.codes()
        self.post(self.url, {"for": "everyone"})
        now = self.codes()
        self.assertEqual(set(now), set(printed))
        self.assertTrue(all(now[n] != printed[n] for n in now))

    def test_a_student_who_joined_needs_no_code_until_signed_out(self):
        self.post(self.url, {"for": "missing"})
        kid = self.app.test_client()
        self.post("/kids", {"code": self.codes()["Ava"]}, client=kid)
        self.add_students(self.class_id, ["Zoe"])
        page = words(self.client.get(self.url).data.decode())
        self.assertIn("1 student has no code yet (Zoe)", page)
        self.assertIn("Make codes for Zoe", page)
        ava = self.students(self.class_id)["Ava"]
        self.assertIsNotNone(ava["joined_at"])
        self.post(f"/app/academy/{ava['id']}/devices/sign-out")
        self.assertIn("2 students have no code yet", words(self.client.get(self.url).data.decode()))

    def test_first_time_offers_a_code_for_every_student(self):
        page = words(self.client.get(self.url).data.decode())
        self.assertIn("Make a code for every student", page)
        self.assertNotIn("Make new codes for everyone", page)


# --- 1b. One notice after adding students --------------------------------------------------------

class TestOneNoticeAfterAddingStudents(SchoolCase):
    def test_added_check_and_not_added_are_one_notice(self):
        self.teacher_signup()
        class_id = self.add_class()
        self.client.get(f"/app/academy/classes/{class_id}")      # the sign-up's and the class's own notices
        page = html.unescape(self.add_students(class_id, ["Liam", "Noah K", "Ava Thompson", "bob@example.com"])
                             .data.decode())
        notices = re.findall(r'<li class="flash (\w+)">([^<]*)</li>', page)
        self.assertEqual(len(notices), 1, notices)
        kind, said = notices[0]
        self.assertEqual(kind, "ok")
        self.assertIn("Added 2 students to Room 12.", said)
        self.assertIn("looks like a first and last name", said)
        self.assertIn("wasn't added", said)


# --- 2. A teacher's Settings -------------------------------------------------------------------

class TestTeacherSettings(SchoolCase):
    def setUp(self):
        super().setUp()
        self.teacher_signup()

    def page(self):
        return words(self.client.get("/app/settings").data.decode())

    def test_trial_and_classroom_hide_industries_locations_and_check_reminders(self):
        for plan in (None, "classroom"):
            if plan:
                self.app.test_cli_runner().invoke(args=["plan", "1", plan])
            raw = self.client.get("/app/settings").data.decode()
            page = words(raw)
            self.assertIn("School name", page)
            self.assertIn("Save school settings", page)
            self.assertNotIn("Company", page)
            self.assertNotIn('name="industries"', raw)
            self.assertNotIn("RestoArmor", page)
            self.assertNotIn("Locations", page)
            self.assertNotIn("data-add-location", raw)
            self.assertNotIn("Daily digest", page)
            self.assertNotIn("Time-limit alerts", page)
            self.assertIn("comes with Whole school", page)

    def test_saving_the_school_keeps_its_checklist(self):
        self.post("/app/settings/company", {"name": "Maple Elementary", "timezone": "America/Chicago"})
        with self.db() as conn:
            row = conn.execute("SELECT name FROM orgs WHERE id = 1").fetchone()
            ids = [r[0] for r in conn.execute("SELECT industry_id FROM org_industries WHERE org_id = 1")]
        self.assertEqual(row["name"], "Maple Elementary")
        self.assertEqual(ids, [51])

    def test_a_school_cannot_add_a_location(self):
        self.post("/app/settings/locations/add", {"name": "Second campus"})
        with self.db() as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM orgs").fetchone()[0], 1)

    def test_whole_school_shows_the_school_checklists_and_the_digest_only(self):
        self.app.test_cli_runner().invoke(args=["plan", "1", "school"])
        raw = self.client.get("/app/settings").data.decode()
        page = words(raw)
        self.assertEqual(sorted(re.findall(r'name="industries" value="(\d+)"', raw)), ["51", "8"])
        self.assertIn("Your school checklists", page)
        self.assertIn("Daily digest: school checklist checks", page)
        self.assertNotIn("Time-limit alerts", page)        # no school check counts hours or minutes
        self.assertNotIn("Locations", page)
        self.assertIn("School", page)

    def test_a_business_still_sees_everything(self):
        other = self.app.test_client()
        self.signup(email="biz@example.com", industries=(2,), client=other)
        raw = other.get("/app/settings").data.decode()
        page = words(raw)
        self.assertIn("Company name", page)
        self.assertGreater(len(re.findall(r'name="industries"', raw)), 50)
        self.assertIn("Locations", page)
        self.assertIn("Daily digest", page)
        self.assertIn("Time-limit alerts", page)


# --- 3. One lesson count per track --------------------------------------------------------------

class TestOneLessonCount(AppTestCase):
    def test_every_surface_shows_the_same_count_and_the_rule_quests_apart(self):
        self.signup(industries=(2,))
        self.post("/app/academy/learners", {"nickname": "Mia", "avatar": "rocket", "track": "launchpad"})
        with self.db() as conn:
            learner = conn.execute("SELECT id FROM learners").fetchone()["id"]
        launchpad = academy.TRACKS["launchpad"]
        counts = {}
        home = self.client.get("/app/academy").data.decode()
        picker = self.client.get(f"/app/academy/{learner}/track").data.decode()
        lmap = self.client.get(f"/app/academy/{learner}").data.decode()
        for name, page in (("home", home), ("picker", picker), ("map", lmap)):
            counts[name] = set(re.findall(r'data-lesson-count="(\d+)"', page))
        # Each track's one count, the same on the home, the picker and its detail.
        for t in academy.TRACK_LIST:
            self.assertIn(str(t.lessons), counts["home"], t.key)
            self.assertIn(str(t.lessons), counts["picker"], t.key)
            self.assertEqual(len(re.findall(rf'data-lesson-count="{t.lessons}"', picker)), 2, t.key)
            self.assertNotIn(f"{t.topic_lessons} lessons", words(picker))
        self.assertEqual(counts["map"], {str(launchpad.lessons)})
        # Nothing else is counted as lessons on these pages.
        allowed = {str(t.lessons) for t in academy.TRACK_LIST}
        for name in counts:
            self.assertLessEqual(counts[name], allowed, name)
        self.assertIn(f"0 / {launchpad.lessons} lessons · +1 Rule Quest", words(lmap))
        self.assertIn(f"0/{launchpad.lessons} lessons · +1 Rule Quest", words(home))
        self.assertIn("+1 Rule Quest", words(picker))
        progress = words(self.client.get(f"/app/academy/{learner}/progress").data.decode())
        self.assertIn(f"0 of {launchpad.lessons}", progress)

    def test_a_rule_quest_lesson_is_not_counted_as_a_business_lesson(self):
        t = academy.TRACKS["launchpad"]
        passed = {academy.level_id(t, t.topics[0], 1), academy.level_id(t, academy.INDUSTRY_WORLD_BASE + 2, 1)}
        self.assertEqual(t.lessons_done(passed), 1)


# --- 4. Phones: one helper, one corner; the report as cards; a compact demo bar ------------------

class TestPhoneLayout(unittest.TestCase):
    def test_one_helper_in_one_corner_on_a_phone(self):
        css = read("omniarmor_app", "static", "app.css")
        block = css[css.index("/* One helper, one corner"):]
        block = block[:block.index("\n}\n") + 3]
        # Pilot steps back entirely while Armo's badge has a count; Armo steps back without one.
        self.assertIn("body:has(.companion-badge:not([hidden])) .pilot-root:not(.pilot-open)", block)
        self.assertIn(".companion:not(:has(.companion-badge:not([hidden])))", block)
        # Both in the bottom-right corner, with a margin, never off the screen. 1.14.0: tucked away, the
        # robot shrinks into that corner with the core's keepInViewport (tests/test_pilot_welcome.py).
        self.assertIn("right:max(12px,env(safe-area-inset-right))", block)
        self.assertIn(".pilot-root.pilot-keep-in.pilot-peek:is(", block)
        self.assertIn(".companion{left:auto;right:max(12px", block)
        config = read("omniarmor_app", "static", "pilot-omniarmor.js")
        self.assertIn("keepInViewport: true,", config)
        # 1.15.0: Armo shrinks into the same corner when he would sit on the page (armo-tucked), never off it.
        self.assertNotIn("translateX", read("omniarmor_app", "static", "armo.js"))
        # Pilot's core is untouched.
        for name in os.listdir(os.path.join(STATIC, "pilot")):
            if name.endswith((".js", ".css")):
                with open(os.path.join(STATIC, "pilot", name), encoding="utf-8") as f:
                    self.assertRegex(f.readline(), r"^(//|/\*) Pilot core 1\.3\.0 · ", name)

    def test_the_report_turns_into_cards_on_a_phone(self):
        css = read("omniarmor_app", "static", "app.css")
        self.assertIn("@media screen and (max-width:640px){\n  table.report-cards thead{display:none}", css)
        self.assertIn('td[data-label]::before{content:attr(data-label) ": "', css)

    def test_the_demo_bar_folds_on_a_phone(self):
        bar = read("omniarmor_app", "templates", "demo", "_bar.html")
        self.assertIn('<details class="demo-more" data-demo-more>', bar)
        self.assertNotIn("<details class=\"demo-more\" data-demo-more open", bar)
        css = read("omniarmor_app", "static", "app.css")
        self.assertIn(".demo-more::details-content{content-visibility:visible;display:contents}", css)


class TestReportCards(AppTestCase):
    def test_each_cell_is_labelled(self):
        self.signup(industries=(2,))
        page = self.client.get("/app/report").data.decode()
        self.assertIn('class="report-cards"', page)
        for label in ("Reading", "Due", "Rule", "Last updated"):
            self.assertIn(f'data-label="{label}"', page)


# --- 5. Copy and trust ---------------------------------------------------------------------------

class TestShopDemo(DemoCase):
    def test_the_shop_demo_leads_with_shoparmor(self):
        self.assertEqual(demo_mode.TRADE_DEMOS["shop"][0][0], 50)
        self.open_demo("shop")
        page = text(self.client.get("/app"))
        nav = page[:page.index("Demo Step 1")]
        self.assertLess(nav.index("ShopArmor"), nav.index("PayArmor"))
        self.assertIn('href="/app/industry/50"', self.client.get("/app").data.decode().split("data-demo-next")[0][-80:])
        shop = text(self.client.get("/app/industry/50"))
        self.assertIn("ShopArmor: each check says what to do", shop)

    def test_the_demo_names_the_page_s_own_checklist(self):
        self.open_demo("salon")
        page = text(self.client.get("/app/industry/30"))
        self.assertIn("HRArmor: each check says what to do", page)
        self.assertIn("The HRArmor checklist", page)
        self.assertNotIn("SalonArmor: each check", page)
        own = text(self.client.get("/app/industry/52"))
        self.assertIn("SalonArmor: each check says what to do", own)


class TestDailyGoalCountsPasses(ProgressCase):
    def test_a_failed_try_never_reaches_the_daily_goal(self):
        self.play(1, 1, right=5)
        self.play(1, 2, right=5)
        failed = self.play(1, 3, right=0).data.decode()
        self.assertNotIn("Daily goal reached", failed)
        self.assertIn("Not this time. Read the cards again, then try again", words(failed))
        passed = self.play(1, 3, right=5).data.decode()
        self.assertIn("Daily goal reached: 3 lessons passed today!", passed)
        with self.db() as conn:
            row = conn.execute("SELECT levels, passed FROM learner_days").fetchone()
        self.assertEqual((row["levels"], row["passed"]), (4, 3))   # every try for the streak, passes for the goal

    def test_the_retry_heading_is_finished(self):
        self.assertEqual(result_band(0, 5, 4, 0), "Not this time. Read the cards again, then try again")


if __name__ == "__main__":
    unittest.main()
