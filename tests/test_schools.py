"""OmniArmor for schools: the SchoolSafetyArmor checklist and the /for/schools page,
and the Future Owner Academy for classrooms (classes added by a teacher with
first names or nicknames only, the class progress view, certificates, the
leaderboard, the free trial and its report, and the classroom plans)."""

import html
import os
import re
import sys
import unittest
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_webapp import AppTestCase  # noqa: E402

from omni_armor_rules import CATALOG, validate_rules  # noqa: E402
from omniarmor_app import academy, academy_plan, classrooms, plans, trades  # noqa: E402
from omniarmor_app.catalog import INDUSTRIES, date_mode  # noqa: E402
from omniarmor_app.db import iso  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCHOOL = trades.SCHOOL_INDUSTRY
BASIC = academy.TRACKS["launchpad"]


def words(page):
    return " ".join(re.sub(r"<[^>]+>", " ", html.unescape(page)).split())


# --- The school checklist ------------------------------------------------------------------

class TestSchoolChecklist(unittest.TestCase):
    def test_schools_are_an_industry_of_their_own(self):
        self.assertEqual(INDUSTRIES[SCHOOL]["brand"], "SchoolSafetyArmor")
        self.assertEqual(INDUSTRIES[SCHOOL]["sector"], "School Safety & Operations")
        self.assertEqual(INDUSTRIES[8]["brand"], "SchoolArmor")   # the legal duties, beside it
        validate_rules({SCHOOL: CATALOG[SCHOOL]}, [SCHOOL])

    def test_it_covers_what_a_school_runs_into(self):
        keys = [r.key for r in CATALOG[SCHOOL]]
        self.assertEqual(keys, ["drills_logged", "aed_first_aid_check", "play_equipment_check",
                                "nurse_log_and_fridge", "cafeteria_food_safety", "bus_pretrip_review",
                                "athletics_safety", "visitor_log_review", "lab_chemical_storage",
                                "background_check_renewals"])
        text = " ".join(f"{r.title} {r.input}" for r in CATALOG[SCHOOL]).lower()
        for topic in ("fire", "lockdown", "aed", "first-aid", "playground", "gym", "medication", "fridge",
                      "cafeteria", "food-safety", "bus", "van", "pre-trip", "concussion", "heat", "visitor",
                      "sign-in", "chemical", "background"):
            self.assertIn(topic, text)

    def test_each_check_is_a_reminder_with_a_sensible_frequency(self):
        """Nine are counted from a date, so they come with reminder emails,
        and every limit is a policy a school can set to its own state's."""
        rules = {r.key: r for r in CATALOG[SCHOOL]}
        dated = [r for r in rules.values() if date_mode(r)]
        self.assertEqual(len(dated), 9)
        self.assertTrue(all(r.policy for r in rules.values()))
        self.assertEqual(rules["drills_logged"].limit, 30)
        self.assertEqual(rules["aed_first_aid_check"].limit, 30)
        self.assertEqual(rules["play_equipment_check"].limit, 30)
        for weekly in ("nurse_log_and_fridge", "cafeteria_food_safety", "bus_pretrip_review", "visitor_log_review"):
            self.assertEqual(rules[weekly].limit, 7, weekly)
        self.assertEqual(rules["lab_chemical_storage"].limit, 90)
        self.assertEqual(date_mode(rules["background_check_renewals"]), "until")
        self.assertEqual(rules["athletics_safety"].kind, "required")
        for r in dated:
            self.assertLess(r.warn if r.kind == "max" else -r.warn, r.limit if r.kind == "max" else -r.limit + 1)

    def test_it_never_promises_compliance(self):
        for r in CATALOG[SCHOOL]:
            for text in (r.title, r.cost, r.input, r.action, r.citation):
                self.assertNotRegex(text.lower(), r"guarantee|ensures? compliance|fully compliant", r.key)

    def test_the_schools_trade_names_real_checks(self):
        trade = trades.BY_SLUG["schools"]
        self.assertEqual(trade.own, (SCHOOL, 8))
        for group in trades.groups(trade):
            for check in group["checks"]:
                self.assertIsNotNone(check["rule"])


class TestSchoolPages(AppTestCase):
    def test_the_schools_page_renders(self):
        response = self.client.get("/for/schools")
        self.assertEqual(response.status_code, 200)
        page = words(response.data.decode())
        self.assertIn("Schools", page)
        for rule in CATALOG[SCHOOL]:
            self.assertIn(rule.title, page)
        self.assertIn("OmniArmor has checklists made for schools: SchoolSafetyArmor", page)
        self.assertIn("It doesn't guarantee compliance", page)
        self.assertNotRegex(page.lower(), r"(?<!doesn't )guarantees? (your )?compliance|we ensure")
        self.assertIn("CyberLogix AI", page)
        self.assertIn("watched 24/7", page)
        self.assertIn('href="https://cyberlogix.mtrxhorizyn.com"', response.data.decode())
        self.assertIn('href="/classrooms"', response.data.decode())
        # A school signs up as a school, and sees the classroom demo and prices.
        self.assertIn("/signup?then=classes", response.data.decode())
        self.assertIn('href="/demo/classroom"', response.data.decode())
        self.assertNotIn('href="/demo/business"', response.data.decode())
        self.assertIn(plans.SCHOOL.yearly_price, page)
        self.assertNotIn(plans.PRO.price, page)

    def test_schools_are_in_the_sitemap_and_the_trade_list(self):
        sitemap = self.client.get("/sitemap.xml").data.decode()
        self.assertIn("<loc>https://omniarmor.test/for/schools</loc>", sitemap)
        self.assertIn("<loc>https://omniarmor.test/classrooms</loc>", sitemap)
        self.assertIn("<loc>https://omniarmor.test/industries/schoolsafetyarmor</loc>", sitemap)
        trades_list = self.client.get("/industries").data.decode()
        by_trade = trades_list[trades_list.index('data-trades'):trades_list.index("data-all-industries")]
        self.assertIn('href="/for/schools"', by_trade)

    def test_the_academy_for_schools_page(self):
        response = self.client.get("/classrooms")
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("noindex", response.headers.get("X-Robots-Tag", ""))
        page = words(response.data.decode())
        self.assertIn("For schools and teachers", page)
        self.assertIn("first name or nickname only", page)
        self.assertIn("No student email, no birthdate, no photos", page)
        self.assertIn(f"{plans.DEFAULT_PILOT_DAYS} days free", page)
        self.assertIn(f"{plans.CLASSROOM.name} {plans.CLASSROOM.yearly_price}", page)
        self.assertIn(f"{plans.SCHOOL.name} {plans.SCHOOL.yearly_price}", page)
        self.assertIn("help@mtrxhorizyn.com", page)
        home = self.client.get("/").data.decode()
        self.assertIn('href="/classrooms"', home)

    def test_no_inline_script_or_style(self):
        for path in ("/for/schools", "/classrooms"):
            page = self.client.get(path).data.decode()
            self.assertNotIn(" style=", page, path)
            self.assertNotRegex(page, r"<script(?![^>]*\bsrc=)", path)
            self.assertNotIn("<style", page, path)


# --- Classes ------------------------------------------------------------------------------

class ClassCase(AppTestCase):
    def setUp(self):
        super().setUp()
        self.signup(industries=(SCHOOL,))

    def org(self):
        with self.db() as conn:
            return conn.execute("SELECT * FROM orgs WHERE id = 1").fetchone()

    def start_pilot(self):
        return self.post("/app/academy/classes/pilot")

    def add_class(self, name="Room 12"):
        response = self.post("/app/academy/classes", {"name": name})
        with self.db() as conn:
            row = conn.execute("SELECT id FROM classes WHERE name = ?", (name,)).fetchone()
        return response, (row["id"] if row else None)

    def add_students(self, class_id, names):
        return self.post(f"/app/academy/classes/{class_id}/students", {"names": "\n".join(names)})

    def students(self, class_id):
        with self.db() as conn:
            return {r["nickname"]: r["id"] for r in conn.execute(
                "SELECT id, nickname FROM learners WHERE class_id = ?", (class_id,))}

    def pass_levels(self, learner_id, worlds, when=None, t=BASIC):
        """Marks stage 1 of each world passed for a learner."""
        when = when or datetime.now(timezone.utc)
        with self.db() as conn:
            for number in worlds:
                conn.execute("INSERT INTO learner_progress (learner_id, level, attempts, best_score, best_stars,"
                             " completed_at) VALUES (?, ?, 1, 5, 2, ?)",
                             (learner_id, academy.level_id(t, number, 1), iso(when)))
            conn.commit()

    def flashes(self, response):
        """What the page after a form says: the page it redirects to, or the
        page it answered with (adding students that weren't all added)."""
        if response.status_code in (301, 302, 303):
            return words(self.client.get(response.headers["Location"]).data.decode())
        return words(response.data.decode())

    def kid_client(self, learner_id):
        code = academy.new_join_code()
        with self.db() as conn:
            conn.execute("INSERT INTO join_codes (learner_id, code, expires_at) VALUES (?, ?, ?)",
                         (learner_id, code, iso(datetime.now(timezone.utc) + timedelta(days=1))))
            conn.commit()
        kid = self.app.test_client()
        response = self.post("/kids", {"code": code}, client=kid)
        self.assertEqual(response.status_code, 302)
        return kid


class TestTeacherAddsStudents(ClassCase):
    def test_a_class_needs_the_pilot_or_a_plan(self):
        response, class_id = self.add_class()
        self.assertIsNone(class_id)
        self.assertIn("Start the free trial", self.flashes(response))

    def test_students_are_added_by_first_name_only(self):
        self.start_pilot()
        _, class_id = self.add_class()
        page = self.client.get(f"/app/academy/classes/{class_id}").data.decode()
        form = page[page.index('action="/app/academy/classes/%d/students"' % class_id):]
        form = form[:form.index("</form>")]
        self.assertNotRegex(form, r'type="(email|date|file)"')
        self.assertEqual(re.findall(r'name="([a-z_]+)"', form), ["csrf_token", "names"])
        self.add_students(class_id, ["Sam", "Priya", "Jo B"])
        self.assertEqual(sorted(self.students(class_id)), ["Jo B", "Priya", "Sam"])
        with self.db() as conn:
            columns = {r["name"] for r in conn.execute("PRAGMA table_info(learners)")}
            self.assertFalse(columns & {"email", "birthdate", "birthday", "photo", "last_name", "age"})
            for row in conn.execute("SELECT * FROM learners WHERE class_id = ?", (class_id,)):
                self.assertIn(row["avatar"], academy.AVATARS)

    def test_an_email_is_never_taken_as_a_name(self):
        self.start_pilot()
        _, class_id = self.add_class()
        response = self.add_students(class_id, ["Sam", "sam.smith@example.com"])
        page = self.flashes(response)
        self.assertIn("sam.smith@example.com: looks like an email address", page)
        self.assertEqual(list(self.students(class_id)), ["Sam"])
        for bad in ("kid@school", "x" * 31, "Ana\x07"):
            self.assertIsNone(classrooms.clean_student_name(bad))
        self.assertEqual(classrooms.clean_student_name("  Jo   B "), "Jo B")

    def test_the_same_name_twice_is_refused(self):
        self.start_pilot()
        _, class_id = self.add_class()
        self.add_students(class_id, ["Sam"])
        response = self.add_students(class_id, ["sam"])
        self.assertIn("already in this class", self.flashes(response))
        self.assertEqual(list(self.students(class_id)), ["Sam"])

    def test_family_learners_and_students_are_counted_apart(self):
        self.start_pilot()
        _, class_id = self.add_class()
        self.add_students(class_id, [f"Kid {n}" for n in range(academy.MAX_LEARNERS + 1)])
        response = self.post("/app/academy/learners", {"nickname": "Max", "avatar": "rocket", "track": "launchpad"})
        self.assertEqual(response.status_code, 302)
        with self.db() as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM learners WHERE class_id IS NULL").fetchone()[0], 1)
        home = words(self.client.get("/app/academy").data.decode())
        self.assertIn("Max", home)
        self.assertNotIn("Kid 3", home)

    def test_join_codes_for_the_whole_class(self):
        self.start_pilot()
        _, class_id = self.add_class()
        self.add_students(class_id, ["Sam", "Priya"])
        self.post(f"/app/academy/classes/{class_id}/join-codes")
        page = self.client.get(f"/app/academy/classes/{class_id}/join-codes").data.decode()
        self.assertEqual(len(re.findall(r"KID-[A-Z0-9]{8}", page)), 2)


class TestClassProgress(ClassCase):
    def test_lessons_per_student_and_the_class_total(self):
        self.start_pilot()
        _, class_id = self.add_class()
        self.add_students(class_id, ["Sam", "Priya", "Jo"])
        kids = self.students(class_id)
        self.pass_levels(kids["Sam"], [1, 2, 3])
        self.pass_levels(kids["Priya"], [1])
        page = self.client.get(f"/app/academy/classes/{class_id}").data.decode()
        rows = dict(re.findall(r'data-student="([^"]+)">.*?<td data-lessons>(\d+)</td>', page, re.S))
        self.assertEqual(rows, {"Jo": "0", "Priya": "1", "Sam": "3"})
        self.assertRegex(page, r'data-total="students">3<')
        self.assertRegex(page, r'data-total="lessons">4<')
        self.assertRegex(page, r"data-class-total>4<")

    def test_only_this_workspace_sees_a_class(self):
        self.start_pilot()
        _, class_id = self.add_class()
        other = self.app.test_client()
        self.signup(email="other@example.com", client=other)
        self.assertEqual(other.get(f"/app/academy/classes/{class_id}").status_code, 404)
        self.assertEqual(other.get(f"/app/academy/classes/{class_id}/report").status_code, 404)
        self.assertEqual(self.post(f"/app/academy/classes/{class_id}/students", {"names": "Eve"},
                                   client=other).status_code, 404)

    def test_certificates_carry_the_first_name(self):
        self.start_pilot()
        _, class_id = self.add_class()
        self.add_students(class_id, ["Sam", "Priya"])
        kids = self.students(class_id)
        self.pass_levels(kids["Sam"], list(academy.CLASSROOM.topics) + [academy.FINAL_WORLD.number],
                         t=academy.CLASSROOM)
        page = self.client.get(f"/app/academy/classes/{class_id}/certificates").data.decode()
        self.assertEqual(re.findall(r'data-certificate="([^"]+)"', page), ["Sam"])
        self.assertIn("Certificate of Completion", page)
        self.assertIn("Room 12", page)
        one = self.client.get(f"/app/academy/{kids['Sam']}/certificate").data.decode()
        self.assertIn("Certificate of Completion", one)
        self.assertIn(">Sam<", one)


class TestPilot(ClassCase):
    def test_the_pilot_lasts_the_setting_and_needs_no_card(self):
        self.assertEqual(self.app.config["CLASSROOM_PILOT_DAYS"], 30)
        before = datetime.now(timezone.utc)
        self.start_pilot()
        org = self.org()
        start = datetime.fromisoformat(org["pilot_started_at"])
        ends = datetime.fromisoformat(org["pilot_ends_at"])
        self.assertEqual(ends - start, timedelta(days=30))
        self.assertLessEqual(abs((start - before).total_seconds()), 5)
        self.assertIsNone(org["stripe_customer_id"])
        self.assertEqual(plans.pilot_status(org)["state"], "active")
        self.assertEqual(plans.pilot_status(org)["days_left"], 30)
        self.assertTrue(plans.access(org, now=ends - timedelta(minutes=1), trial_days=0)["academy"])

    def test_the_setting_changes_the_length(self):
        app = self.app
        app.config["CLASSROOM_PILOT_DAYS"] = 45
        self.start_pilot()
        org = self.org()
        self.assertEqual(datetime.fromisoformat(org["pilot_ends_at"]) - datetime.fromisoformat(org["pilot_started_at"]),
                         timedelta(days=45))

    def test_one_pilot_per_workspace(self):
        self.start_pilot()
        first = self.org()["pilot_ends_at"]
        response = self.start_pilot()
        self.assertIn("had its free trial already", self.flashes(response))
        self.assertEqual(self.org()["pilot_ends_at"], first)

    def test_only_the_owner_starts_it_and_any_teacher_runs_a_class(self):
        self.post("/app/settings/invite")
        link = re.search(r"signup\?invite=([\w-]+)", self.client.get("/app/settings").data.decode()).group(1)
        teacher = self.app.test_client()
        self.signup(email="teacher@example.com", client=teacher, invite=link, name="Example Teacher")
        self.post("/app/academy/classes/pilot", client=teacher)
        self.assertIsNone(self.org()["pilot_started_at"])
        self.start_pilot()
        self.post("/app/academy/classes", {"name": "Club"}, client=teacher)
        with self.db() as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM classes").fetchone()[0], 1)

    def test_after_the_pilot_classes_are_kept_but_closed(self):
        self.start_pilot()
        _, class_id = self.add_class()
        self.add_students(class_id, ["Sam"])
        with self.db() as conn:
            past = iso(datetime.now(timezone.utc) - timedelta(days=1))
            conn.execute("UPDATE orgs SET pilot_ends_at = ?, academy_trial_ends = ?", (past, past))
            conn.commit()
        org = self.org()
        self.assertEqual(plans.pilot_status(org)["state"], "ended")
        self.assertFalse(plans.access(org)["academy"])
        self.assertFalse(plans.class_limits(org)["active"])
        response = self.add_students(class_id, ["Priya"])
        self.assertIn("Start the free trial or choose a classroom plan", self.flashes(response))
        self.assertEqual(list(self.students(class_id)), ["Sam"])
        self.assertEqual(self.client.get(f"/app/academy/classes/{class_id}").status_code, 200)
        self.assertEqual(self.client.get(f"/app/academy/classes/{class_id}/report").status_code, 200)

    def test_the_pilot_report_has_totals_only(self):
        self.start_pilot()
        _, class_id = self.add_class()
        self.add_students(class_id, ["Sam", "Priya", "Jo"])
        kids = self.students(class_id)
        # A pilot that ran from 40 to 10 days ago.
        start = datetime.now(timezone.utc) - timedelta(days=40)
        with self.db() as conn:
            conn.execute("UPDATE orgs SET pilot_started_at = ?, pilot_ends_at = ?",
                         (iso(start), iso(start + timedelta(days=30))))
            conn.commit()
        self.pass_levels(kids["Sam"], [1, 2, 6], when=start + timedelta(days=2))
        self.pass_levels(kids["Priya"], [1], when=start + timedelta(days=3))
        # A lesson finished after the pilot ended doesn't count in its report.
        self.pass_levels(kids["Jo"], [1], when=start + timedelta(days=31))
        report = classrooms.report(self.db(), self.org(), {"id": class_id, "name": "Room 12"})
        self.assertEqual(report["students"], 3)
        self.assertEqual(report["playing"], 2)
        self.assertEqual(report["lessons"], 4)
        self.assertTrue(report["finished"])
        self.assertEqual([(t["world"].title, t["lessons"]) for t in report["topics"]],
                         [("Meet Your Company", 2), ("Business Words", 1), ("Money Smarts", 1)])
        page = self.client.get(f"/app/academy/classes/{class_id}/report").data.decode()
        self.assertIn("Trial report", page)
        self.assertRegex(page, r'data-report="students">3<')
        self.assertRegex(page, r'data-report="lessons">4<')
        self.assertIn("Meet Your Company", page)
        main = page[page.index("data-pilot-report"):]
        for name in kids:
            self.assertNotIn(f">{name}<", main)
            self.assertNotRegex(words(main), rf"\b{name}\b")


class TestClassroomPlans(ClassCase):
    def set_plan(self, *args):
        result = self.app.test_cli_runner().invoke(args=["plan", "1", *args])
        self.assertEqual(result.exit_code, 0, result.output)
        return result.output

    def test_the_prices_fit_the_other_plans(self):
        plus_academy = plans.yearly_dollars(plans.PLUS.dollars - plans.PRO.dollars)
        # Classroom is never dearer than adding the Academy to Pro, and has no
        # tracker, so it's never a cheap way into the tracker.
        self.assertLessEqual(plans.CLASSROOM.yearly_dollars, plus_academy)
        self.assertGreater(plans.CLASSROOM.yearly_dollars, plus_academy * 0.9)
        self.assertFalse(plans.CLASSROOM.tracker)
        self.assertEqual(plans.KINDS["classroom"], ("Classroom", False, True))
        # Whole school includes the tracker and costs more than a year of Plus,
        # and between four and five Classrooms.
        self.assertTrue(plans.SCHOOL.tracker)
        self.assertGreater(plans.SCHOOL.yearly_dollars, plans.PLUS.yearly_dollars)
        self.assertGreater(plans.SCHOOL.yearly_dollars, 4 * plans.CLASSROOM.yearly_dollars)
        self.assertLess(plans.SCHOOL.yearly_dollars, 5 * plans.CLASSROOM.yearly_dollars)
        self.assertEqual(plans.CLASSROOM.yearly_price, "$299 a year")
        self.assertEqual(plans.SCHOOL.yearly_price, "$1,490 a year")

    def test_stripe_price_ids_come_from_the_settings(self):
        self.assertEqual(plans.classroom_checkout({}, "classroom"), ("classroom", "", 299))
        cfg = {"CLASSROOM_YEARLY_STRIPE_PRICE": "price_class", "SCHOOL_YEARLY_STRIPE_PRICE": "price_school"}
        self.assertEqual(plans.classroom_checkout(cfg, "school")[1], "price_school")
        sub = {"items": {"data": [{"price": {"id": "price_class"}}]}}
        self.assertEqual(academy_plan.plan_for(cfg, sub), ("classroom", "year"))

    def test_without_stripe_the_school_gets_an_invoice(self):
        page = words(self.client.get("/app/academy/classes").data.decode())
        self.assertIn("Does your school want an invoice?", page)
        self.assertNotIn("by card", page)
        response = self.post("/app/academy/classes/checkout", {"plan": "classroom"})
        self.assertIn("for an invoice", self.flashes(response))

    def test_classroom_is_one_class_of_up_to_35(self):
        self.assertIn("Classroom on, yearly", self.set_plan("classroom"))
        org = self.org()
        a = plans.access(org)
        self.assertTrue(a["academy"])
        self.assertFalse(a["tracker"] and a["source"] == "plan")
        self.assertEqual(plans.class_limits(org)["max_classes"], 1)
        _, class_id = self.add_class()
        response, second = self.add_class("Room 13")
        self.assertIsNone(second)
        self.assertIn("Classroom is for 1 class", self.flashes(response))
        self.add_students(class_id, [f"Kid {n}" for n in range(plans.CLASS_SIZE)])
        self.assertEqual(len(self.students(class_id)), 35)
        response = self.add_students(class_id, ["One More"])
        self.assertIn("full (35 students)", self.flashes(response))
        self.assertEqual(len(self.students(class_id)), 35)

    def test_classroom_alone_keeps_the_checklist_read_only(self):
        self.set_plan("classroom")
        with self.db() as conn:
            conn.execute("UPDATE orgs SET academy_trial_ends = ?",
                         (iso(datetime.now(timezone.utc) - timedelta(days=1)),))
            conn.commit()
        a = plans.access(self.org())
        self.assertTrue(a["academy"])
        self.assertFalse(a["tracker"])
        self.assertEqual(a["reason"], "academy_only")
        page = self.client.get("/app").data.decode()
        self.assertIn("Your Classroom plan covers the Academy for your class", page)
        self.assertNotIn("data-readonly-banner", self.client.get("/app/academy/classes").data.decode())

    def test_too_many_at_once_adds_the_ones_that_fit(self):
        self.set_plan("classroom")
        _, class_id = self.add_class()
        response = self.add_students(class_id, [f"Kid {n}" for n in range(plans.CLASS_SIZE + 1)])
        self.assertIn(f"Kid {plans.CLASS_SIZE}: didn't fit: the class is full", self.flashes(response))
        self.assertEqual(len(self.students(class_id)), plans.CLASS_SIZE)

    def test_the_pilot_is_one_class(self):
        self.start_pilot()
        self.add_class()
        _, second = self.add_class("Room 13")
        self.assertIsNone(second)

    def test_whole_school_has_any_number_of_classes_and_the_tracker(self):
        self.set_plan("school")
        org = self.org()
        self.assertIsNone(plans.class_limits(org)["max_classes"])
        self.assertEqual(plans.access(org)["source"], "plan")
        ids = [self.add_class(f"Room {n}")[1] for n in range(1, 5)]
        self.assertTrue(all(ids))

    def test_an_invoiced_plan_stops_on_its_last_day(self):
        self.assertIn("until 2027-06-30", self.set_plan("classroom", "--until", "2027-06-30"))
        org = self.org()
        self.assertEqual(org["plan"], "classroom")
        self.assertEqual(org["plan_interval"], "year")
        last = datetime(2027, 6, 30, 12, tzinfo=timezone.utc)
        self.assertTrue(plans.access(org, now=last)["paid"])
        self.assertTrue(plans.class_limits(org, now=last)["active"])
        # The end of that day in the workspace's timezone (New York): 03:59:59 UTC on 1 July.
        self.assertTrue(plans.access(org, now=datetime(2027, 7, 1, 3, tzinfo=timezone.utc))["paid"])
        after = datetime(2027, 7, 1, 4, 1, tzinfo=timezone.utc)
        self.assertFalse(plans.access(org, now=after)["paid"])
        self.assertFalse(plans.class_limits(org, now=after)["active"])

    def test_an_invoiced_plan_stops_even_after_an_old_card_subscription(self):
        """A school that paid by card one year and by invoice the next: the
        old Stripe subscription's id stayed on the workspace, so the end date
        set by hand was never applied and the plan ran on for free."""
        with self.db() as conn:
            conn.execute("UPDATE orgs SET academy_status = 'canceled', plan = 'classroom',"
                         " stripe_customer_id = 'cus_old', stripe_subscription_id = 'sub_old' WHERE id = 1")
            conn.commit()
        self.set_plan("classroom", "--until", "2027-06-30")
        org = self.org()
        self.assertIsNone(org["stripe_subscription_id"])
        self.assertEqual(org["stripe_customer_id"], "cus_old")      # the card and invoices stay findable
        self.assertTrue(plans.access(org, now=datetime(2027, 6, 30, 12, tzinfo=timezone.utc))["paid"])
        after = datetime(2027, 7, 1, 4, 1, tzinfo=timezone.utc)   # past 23:59:59 that day in New York
        self.assertFalse(plans.access(org, now=after)["paid"])
        self.assertFalse(plans.class_limits(org, now=after)["active"])
        # Cancelling it in the app ends it here, without asking Stripe about the old subscription.
        self.assertFalse(plans.cancel_options(self.app.config, org)["online"])

    def test_a_plan_set_by_hand_leaves_a_running_card_subscription_alone(self):
        with self.db() as conn:
            conn.execute("UPDATE orgs SET academy_status = 'active', stripe_customer_id = 'cus_1',"
                         " stripe_subscription_id = 'sub_live' WHERE id = 1")
            conn.commit()
        self.set_plan("school", "--force")      # refused without it (test_plan_edges)
        self.assertEqual(self.org()["stripe_subscription_id"], "sub_live")

    def test_a_bad_date_is_refused(self):
        result = self.app.test_cli_runner().invoke(args=["plan", "1", "school", "--until", "June"])
        self.assertNotEqual(result.exit_code, 0)


class TestStudentsSeeOnlyTheirClass(ClassCase):
    def setUp(self):
        super().setUp()
        self.set_school()
        _, self.a = self.add_class("Room A")
        _, self.b = self.add_class("Room B")
        self.add_students(self.a, ["Sam", "Priya"])
        self.add_students(self.b, ["Zed", "Yara"])
        self.kids_a, self.kids_b = self.students(self.a), self.students(self.b)
        self.pass_levels(self.kids_a["Priya"], [1, 2])
        # A new class starts with the leaderboard off; Room A's teacher turns it on.
        self.post(f"/app/academy/classes/{self.a}/leaderboard", {"leaderboard": "on"})

    def set_school(self):
        result = self.app.test_cli_runner().invoke(args=["plan", "1", "school"])
        self.assertEqual(result.exit_code, 0, result.output)

    def test_a_new_class_starts_with_the_leaderboard_off_and_old_ones_keep_theirs(self):
        with self.db() as conn:
            boards = dict(conn.execute("SELECT name, leaderboard FROM classes").fetchall())
            self.assertEqual(boards, {"Room A": 1, "Room B": 0})
            # A class made before 1.11.0 kept the old default (on), and keeps it.
            conn.execute("INSERT INTO classes (org_id, name, created_at) VALUES (1, 'Old room', '2026-01-01')")
            conn.commit()
            self.assertEqual(conn.execute("SELECT leaderboard FROM classes WHERE name = 'Old room'").fetchone()[0], 1)
        kid = self.kid_client(self.kids_b["Zed"])
        page = kid.get(f"/app/academy/{self.kids_b['Zed']}/class").data.decode()
        self.assertIn("data-board-off", page)
        self.assertNotIn("Yara", re.findall(r'class="ac-board-name">([^<(]+)', page))

    def test_a_student_sees_their_class_board_only(self):
        kid = self.kid_client(self.kids_a["Sam"])
        page = kid.get(f"/app/academy/{self.kids_a['Sam']}/class").data.decode()
        board = re.findall(r'class="ac-board-name">([^<(]+)', page)
        self.assertEqual([b.strip() for b in board], ["Priya", "Sam"])
        self.assertNotIn("Zed", page)
        self.assertNotIn("Room B", page)

    def test_another_classs_pages_are_closed_to_a_student(self):
        kid = self.kid_client(self.kids_a["Sam"])
        self.assertEqual(kid.get(f"/app/academy/{self.kids_b['Zed']}/class").status_code, 404)
        self.assertEqual(kid.get(f"/app/academy/{self.kids_b['Zed']}").status_code, 404)
        for path in (f"/app/academy/classes/{self.b}", f"/app/academy/classes/{self.a}",
                     f"/app/academy/classes/{self.a}/report", "/app/academy/classes"):
            response = kid.get(path)
            self.assertEqual(response.status_code, 302, path)
            self.assertTrue(response.headers["Location"].endswith(f"/app/academy/{self.kids_a['Sam']}"), path)
        self.assertEqual(self.post(f"/app/academy/classes/{self.a}/leaderboard", {"leaderboard": "off"},
                                   client=kid).status_code, 403)

    def test_the_teacher_can_switch_the_board_off(self):
        self.post(f"/app/academy/classes/{self.a}/leaderboard", {"leaderboard": "off"})
        kid = self.kid_client(self.kids_a["Sam"])
        page = kid.get(f"/app/academy/{self.kids_a['Sam']}/class").data.decode()
        self.assertIn("data-board-off", page)
        self.assertNotIn("Priya", page)
        self.post(f"/app/academy/classes/{self.a}/leaderboard", {"leaderboard": "on"})
        self.assertIn("Priya", kid.get(f"/app/academy/{self.kids_a['Sam']}/class").data.decode())

    def test_no_friends_or_duels_in_a_class(self):
        kid = self.kid_client(self.kids_a["Sam"])
        response = kid.get(f"/app/academy/{self.kids_a['Sam']}/friends")
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.headers["Location"].endswith("/class"))
        self.post(f"/app/academy/{self.kids_a['Sam']}/friends/code")
        with self.db() as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM friend_codes").fetchone()[0], 0)
        map_page = kid.get(f"/app/academy/{self.kids_a['Sam']}").data.decode()
        self.assertIn("My class", map_page)
        self.assertNotIn("Friends &amp; duels", map_page)


class TestTheDocs(unittest.TestCase):
    SETTINGS = ("CLASSROOM_YEARLY_STRIPE_PRICE", "SCHOOL_YEARLY_STRIPE_PRICE", "CLASSROOM_PILOT_DAYS",
                "SCHOOL_INVOICE_EMAIL")

    def read(self, *parts):
        with open(os.path.join(ROOT, *parts), encoding="utf-8") as f:
            return f.read()

    def test_the_new_settings_are_documented(self):
        for name in self.SETTINGS:
            for doc in ((".env.example",), ("render.yaml",), ("docs", "OPERATIONS.md"), ("docs", "HANDBOOK.md")):
                self.assertIn(name, self.read(*doc), f"{name} in {'/'.join(doc)}")
            self.assertRegex(self.read("render.yaml"), rf"- key: {name}\n")

    def test_no_real_school_is_named(self):
        """Examples use made-up names only."""
        for parts in (("omniarmor_app", "classrooms.py"), ("omniarmor_app", "classroom_views.py"),
                      ("omniarmor_app", "templates", "academy_schools.html"), ("tests", "test_schools.py")):
            text = self.read(*parts)
            self.assertNotRegex(text, r"\b(St\.|Saint) [A-Z][a-z]+'?s?\b|[A-Z][a-z]+ (Elementary|Middle|High) School")


if __name__ == "__main__":
    unittest.main()
