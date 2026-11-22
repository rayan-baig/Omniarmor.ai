"""1.16.0: what a strict sixth review found, fixed. Sharper pictures of the app,
with the headline's one right under its buttons on a phone; one grown-up look
for the teacher's and parent's Academy pages, the OmniArmor name at the top of
the computer's side bar, and a reserved corner for the helpers on a phone
instead of a gutter down the right of every page; lessons that hint instead of
listing the answers, a celebration when a stage is passed, and a picture that
grows on the map; kids' screens with no way out to the grown-up pages; and
smaller polish (the school checklist's own picture, a different third picture
for classrooms, the phone menu closing, a Print button, the CyberLogix offer
off the first checklist, Pilot off the Select boxes and the teacher guide)."""

import html
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_classroom_review import SchoolCase  # noqa: E402
from test_parent_view import ProgressCase  # noqa: E402
from test_webapp import AppTestCase  # noqa: E402

from omniarmor_app import academy, shots  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATIC = os.path.join(ROOT, "omniarmor_app", "static")


def read(*parts):
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as f:
        return f.read()


PUBLIC = {"/": "biz", "/classrooms": "class", "/for/salons-and-barbershops": "salon",
          "/for/tattoo-and-piercing-studios": "tattoo", "/for/gyms-and-fitness-studios": "gym",
          "/for/shops-and-retail-stores": "shop", "/for/schools": "school"}
IMG = r'<img src="(/static/shots/[^"?]+)(?:\?[^"]*)?" width="(\d+)" height="(\d+)"'


# --- 1. Pictures ------------------------------------------------------------------------------

class TestPicturesOnAPhone(AppTestCase):
    def test_the_headline_s_picture_sits_right_under_its_buttons_before_the_prices(self):
        for path, kind in PUBLIC.items():
            page = self.client.get(path).data.decode()
            hero = page[page.index('<section class="hero">'):page.index("</section>", page.index('<section class="hero">'))]
            self.assertIn(f'data-hero-shot-phone="{kind}"', hero, path)
            phone = hero.index("data-hero-shot-phone")
            cta = hero.index('<div class="cta">')
            self.assertLess(cta, phone, path)
            # Nothing but the buttons between them: no prices, no hint.
            between = hero[hero.index("</div>", cta):phone]
            self.assertNotIn("plans", between, path)
            self.assertNotIn("data-demo-hint", between, path)
            if 'class="plans' in hero:
                self.assertLess(phone, hero.index('class="plans'), path)
            # The same file as the one beside the headline on a computer: fetched once.
            side = page[page.index("data-hero-shot="):]
            self.assertEqual(re.search(IMG, hero[phone:]).group(1), re.search(IMG, side).group(1), path)

    def test_a_phone_shows_one_of_the_two_and_a_computer_the_other(self):
        css = read("omniarmor_app", "static", "app.css")
        self.assertIn(".hero-shot-phone{display:none}", css)
        rule = css[css.index("@media (max-width:959px)", css.index(".hero-shot-phone{display:none}")):]
        self.assertIn(".hero-shot-side{display:none}", rule[:rule.index("\n}")])

    def test_every_picture_is_taken_at_twice_its_phone_size_and_stays_small(self):
        folder = sorted(os.listdir(os.path.join(STATIC, "shots")))
        self.assertGreaterEqual(len(folder), 25)
        for name in folder:
            file = os.path.join(STATIC, "shots", name)
            width, height = shots._size(file)
            self.assertGreaterEqual(width, 880, name)
            self.assertLessEqual(width, 1000, name)
            self.assertLess(os.path.getsize(file), 64_000, name)
            if not name.endswith(("-overview.webp", "class-progress.webp", "school-checklist.webp")):
                self.assertLessEqual(height, round(width * 1.25) + 1, name)   # steps show 4:5 at most

    def test_the_schools_page_shows_the_school_checklist_and_classrooms_a_third_picture_of_its_own(self):
        school = self.client.get("/for/schools").data.decode()
        hero = school[school.index('data-hero-shot="school"'):]
        self.assertEqual(re.search(IMG, hero).group(1), "/static/shots/school-checklist.webp")
        self.assertNotIn("class-progress", school)
        classrooms = self.client.get("/classrooms").data.decode()
        steps = classrooms[classrooms.index("data-how-it-works"):]
        steps = [m.group(1) for m in re.finditer(IMG, steps[:steps.index("</section>")])]
        hero = re.search(IMG, classrooms[classrooms.index('data-hero-shot="class"'):]).group(1)
        self.assertEqual(len(set(steps)), 3)
        self.assertNotIn(hero, steps)
        self.assertIn("/static/shots/class-report.webp", steps)
        self.assertEqual(shots.kind_for("schools", True), "school")


# --- 2. One grown-up look, the side bar's logo, the helpers' corner --------------------------------

class TestOneGrownUpLook(SchoolCase):
    def setUp(self):
        super().setUp()
        self.teacher_signup()
        self.class_id = self.add_class()
        self.add_students(self.class_id, ["Maya", "Leo"])

    def test_the_teacher_s_pages_wear_the_business_look(self):
        base = f"/app/academy/classes/{self.class_id}"
        for path in ("/app/academy/classes", base, base + "/join-codes", base + "/certificates", base + "/report"):
            page = self.client.get(path).data.decode()
            self.assertIn('class="ac ac-grown', page, path)

    def test_the_kid_s_own_screens_keep_the_game_look(self):
        maya = self.students(self.class_id)["Maya"]["id"]
        for path in (f"/app/academy/{maya}", f"/app/academy/{maya}/world/{academy.CLASSROOM.topic_worlds[0].number}/stage/1"):
            page = self.client.get(path).data.decode()
            self.assertNotIn('class="ac ac-grown', page, path)

    def test_the_grown_up_look_uses_the_business_type_buttons_and_cards(self):
        css = read("omniarmor_app", "static", "academy.css")
        grown = css[css.index(".ac.ac-grown{"):]
        self.assertIn("--kid:var(--sans)", grown)
        self.assertIn(".ac-grown .ac-title{font-family:var(--display)", grown)
        self.assertIn("text-transform:uppercase", grown)
        self.assertIn(".ac-grown .ac-btn{font-size:15px;font-weight:600;min-height:44px;padding:0 18px;border-radius:8px}", grown)


class TestTheBusinessAcademyPage(ProgressCase):
    def test_the_academy_page_and_a_progress_report_wear_the_business_look(self):
        for path in ("/app/academy", self.url):
            self.assertIn('class="ac ac-grown', self.client.get(path).data.decode(), path)
        self.assertNotIn('class="ac ac-grown', self.client.get(f"/app/academy/{self.lid}").data.decode())


class TestTheSideBarAndTheHelpersCorner(AppTestCase):
    def test_the_side_bar_has_the_omniarmor_name_at_its_top(self):
        self.signup()
        page = self.client.get("/app").data.decode()
        bar = page[page.index('<nav class="tabbar'):]
        bar = bar[:bar.index("</nav>")]
        self.assertLess(bar.index("data-side-logo"), bar.index('class="tab"'))
        self.assertIn('aria-label="OmniArmor.ai home"', bar)
        self.assertEqual(page.count('id="blend"'), 1)   # the gradient is defined once
        css = read("omniarmor_app", "static", "app.css")
        wide = css[css.index(".tab-logo{display:none}"):]
        wide = wide[:wide.index("\n}\n") + 3]
        self.assertIn("body.has-tabs:not(.lesson-view) .tab-logo{display:inline-flex", wide)
        self.assertIn("body.has-tabs:not(.lesson-view) .topbar .lockup{display:none}", wide)

    def test_no_gutter_down_the_right_for_armo_but_a_reserved_corner(self):
        css = read("omniarmor_app", "static", "app.css")
        self.assertNotIn("padding-right:max(42px", css)
        # 1.18.0: the corner's framed box covered the page's last lines, so it is gone (tests/test_round8_fixes.py).
        self.assertNotIn("::after{\n    content:\"\";position:fixed;z-index:51", css)
        self.assertIn("/* The helpers' corner on a phone.", css)
        # Pilot's side room is left out on signed-in pages, kept on public ones.
        config = read("omniarmor_app", "static", "pilot-omniarmor.js")
        self.assertIn('gutter: document.body && document.body.classList.contains("has-tabs") ? false : ["main > .wrap"],', config)


# --- 3. Lessons, the celebration, the growing picture -----------------------------------------------

class TestLessonsHintNotAnswer(unittest.TestCase):
    def test_no_lesson_lists_the_answers_before_the_quiz(self):
        company, ids = "Juniper Lane", [2, 30]
        hinted = 0
        for t in list(academy.TRACK_LIST) + [academy.CLASSROOM]:
            for w in t.topic_worlds + [academy.FINAL_WORLD]:
                cards = academy.story(t, w.number, 1, company, ids)
                text = " ".join(f"{a} {b}" for a, b in cards)
                self.assertNotIn("Before the quiz", text, (t.name, w.title))
                if f"{academy.QUIZ_HINT}:" in cards[-1][1]:
                    hinted += 1
                    hint = cards[-1][1].split(f"{academy.QUIZ_HINT}:")[1].lower()
                    self.assertEqual(hint.strip(), academy.quiz_hint().lower())
                    for q in academy.quiz(t, w.number, 1, company, ids, "x"):
                        answer = str(q.options[q.answer]).lower().strip(' ."')
                        if len(answer) > 12:
                            self.assertNotIn(answer, hint, (t.name, w.title, q.prompt))
                        self.assertNotIn(q.explain.lower().strip(" ."), hint)
        self.assertGreater(hinted, 0)

    def test_the_class_stand_s_first_lesson_ends_with_the_hint_and_stays_short(self):
        w = academy.CLASSROOM.topic_worlds[0]
        cards = academy.story(academy.CLASSROOM, w.number, 1, "x", [])
        self.assertEqual(len(cards), 5)   # no card added: the first lesson stays short
        self.assertEqual(cards[-1], ("Your adventure", "Each short lesson has five questions. Get most of them right to"
                                     f" unlock the next one! Quiz hint: {academy.quiz_hint()}"))


class TestTheCelebrationAndTheGrowingPicture(ProgressCase):
    def result(self, right):
        response = self.play(1, 1, right=right)
        return html.unescape(response.data.decode())

    def test_passing_a_stage_opens_a_celebration(self):
        page = self.result(5)
        self.assertIn("data-celebrate", page)
        party = page[page.index("data-celebrate"):page.index('<section class="ac-result')]
        self.assertIn("Perfect!", party)
        self.assertIn('class="avatar', party)
        self.assertIn('tabindex="-1" hidden>', party)   # shown by academy.js, gone after "Keep going"
        self.assertIn("data-celebrate-close>Keep going", party)
        self.assertIn('data-sound aria-pressed="false">Sound: off', party)
        self.assertNotIn("Your picture grew", party)   # 1 lesson: still a Rookie

    def test_a_rank_up_says_the_picture_grew(self):
        for stage in range(1, 5):
            self.play(1, stage, right=5)
        page = self.result_of(1, 5)
        party = page[page.index("data-celebrate"):page.index('<section class="ac-result')]
        self.assertIn("Your picture grew: you're now an Apprentice!", party)
        self.assertIn('ac-celebrate-pic grew', party)

    def result_of(self, world, stage):
        return html.unescape(self.play(world, stage, right=5).data.decode())

    def test_a_failed_try_has_no_celebration(self):
        self.assertNotIn("data-celebrate", self.result(1))

    def test_the_celebration_respects_less_motion_and_sound_starts_off(self):
        css = read("omniarmor_app", "static", "academy.css")
        reduce = css[css.index("@media (prefers-reduced-motion:reduce){\n  .ac-celebrate-rays"):]
        self.assertIn("animation:none", reduce[:reduce.index("\n}")])
        js = read("omniarmor_app", "static", "academy.js")
        self.assertIn('var SOUND_KEY = "omniarmor-academy-sound";', js)
        self.assertIn('soundOn = window.localStorage.getItem(SOUND_KEY) === "on"', js)
        self.assertIn("if (!on || chimed) return;", js)
        self.assertNotIn("<audio", read("omniarmor_app", "templates", "academy", "result.html"))

    def test_the_picture_grows_on_the_map(self):
        before = self.client.get(f"/app/academy/{self.lid}").data.decode()
        self.assertIn('data-picture-tier="0"', before)
        self.assertEqual(before.count('<li class="later"'), len(academy.RANKS) - 1)
        self.assertIn('class="ac-grow ac-grow-0"', before)
        for stage in range(1, 6):
            self.play(1, stage, right=5)
        after = self.client.get(f"/app/academy/{self.lid}").data.decode()
        self.assertIn('data-picture-tier="1"', after)
        self.assertIn('class="ac-grow ac-grow-1"', after)
        self.assertIn('aria-current="step"', after)
        # Pinned on the world played next.
        here = after[after.index("data-you-are-here"):]
        self.assertIn("ac-here-pin", here[:here.index("</li>")])
        css = read("omniarmor_app", "static", "academy.css")
        self.assertIn(".ac-grow-7{--s:128px}", css)
        self.assertEqual(len(academy.rank_ladder(academy.CLASSROOM)), len(academy.RANKS))


# --- 4. Kids' screens stay closed --------------------------------------------------------------------

class TestNoWayOutOfAKidsScreen(ProgressCase):
    def test_a_lesson_on_a_grown_up_s_device_has_no_menu_link_or_footer(self):
        for path in ("/app/academy/1/world/1", "/app/academy/1/world/1/stage/1", "/app/academy/1/practice"):
            page = self.client.get(path).data.decode()
            top = page[page.index('<header class="topbar">'):page.index("</header>")]
            self.assertIn("data-lockup-still", top, path)
            self.assertNotIn("<a ", top, path)
            self.assertNotIn("Sign out", top, path)
            self.assertNotIn("data-nav-menu", top, path)
            self.assertNotIn('<footer class="site">', page, path)
            self.assertNotIn("RestoArmor", page, path)
            self.assertIn("Back to map", page, path)
        result = self.play(1, 1, right=5).data.decode()
        self.assertNotIn("Sign out", result[result.index('<header class="topbar">'):result.index("</header>")])

    def test_the_grown_up_s_own_pages_keep_the_menu(self):
        # 1.18.0: the learner's map is the kid's screen (no menu); the progress report is the grown-up's.
        page = self.client.get("/app/academy/1/progress").data.decode()
        self.assertIn("data-nav-menu", page)
        self.assertIn("Sign out", page)
        self.assertNotIn("data-lockup-still", page)


class TestAJoinedStudentGoesToTheirMap(AppTestCase):
    def setUp(self):
        super().setUp()
        self.signup()
        self.post("/app/academy/learners", {"nickname": "Sam", "avatar": "rocket", "track": "launchpad"})
        self.post("/app/academy/1/join-code")
        with self.db() as conn:
            code = conn.execute("SELECT code FROM join_codes").fetchone()[0]
        self.kid = self.app.test_client()
        self.kid.get("/kids")
        self.post("/kids", {"code": code}, client=self.kid)

    def test_any_grown_up_page_sends_them_to_their_own_map_not_the_sign_in(self):
        for path in ("/app", "/app/report", "/app/settings", "/app/audit", "/app/notifications", "/app/industry/1",
                     "/app/academy/classes"):
            response = self.kid.get(path)
            self.assertEqual(response.status_code, 302, path)
            self.assertTrue(response.headers["Location"].endswith("/app/academy/1"), (path, response.headers["Location"]))
        # A sent form still does nothing: it goes to the sign-in, as before.
        response = self.post("/app/settings/reminders", {}, client=self.kid)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login", response.headers["Location"])

    def test_someone_with_no_session_still_gets_the_sign_in(self):
        response = self.app.test_client().get("/app")
        self.assertIn("/login", response.headers["Location"])


# --- 5. Polish -----------------------------------------------------------------------------------------

class TestPolish(AppTestCase):
    def test_the_phone_menu_closes_with_escape_or_a_tap_outside(self):
        page = self.client.get("/").data.decode()
        self.assertIn('<script src="/static/page.js', page)
        js = read("omniarmor_app", "static", "page.js")
        self.assertIn('e.key === "Escape" && menu.open', js)
        self.assertIn('addEventListener("pointerdown"', js)
        self.assertIn("!menu.contains(e.target)", js)

    def test_the_report_has_a_print_button(self):
        self.signup()
        page = self.client.get("/app/report").data.decode()
        self.assertIn('<button class="btn" type="button" data-print hidden>Print</button>', page)
        self.assertIn("window.print()", read("omniarmor_app", "static", "page.js"))

    def test_the_cyberlogix_offer_is_in_settings_not_on_the_first_checklist(self):
        self.signup(industries=(2,))
        first = self.client.get("/app/industry/2").data.decode()
        self.assertNotIn("Let CyberLogix fill this in", first)
        self.assertNotIn("data-bundle>", first)
        self.assertIn("Let CyberLogix fill this in automatically", self.client.get("/app/settings").data.decode())

    def test_pilot_keeps_off_the_select_boxes_and_the_teacher_guide(self):
        config = read("omniarmor_app", "static", "pilot-omniarmor.js")
        avoid = config[config.index("avoid: ["):]
        avoid = avoid[:avoid.index("],")]
        for sel in ('".pick"', '"[data-teacher-guide] p"', '"[data-teacher-guide] li"', '"[data-teacher-guide] h3"'):
            self.assertIn(sel, avoid)
        guide = self.client.get("/classrooms/guide").data.decode()
        self.assertIn("data-teacher-guide", guide)


class TestVersion(unittest.TestCase):
    def test_version_and_changelog(self):
        from omniarmor_app.version import __version__
        self.assertGreaterEqual(tuple(map(int, __version__.split("."))), (1, 16, 0))
        log = read("CHANGELOG.md")
        top = log[log.index("## 1.16.0"):log.index("## 1.15.0")]
        for said in ("first screen of a phone", "One look for grown-ups", "hints, not answers", "celebration",
                     "grows on the map", "No way out", "Print button"):
            self.assertIn(said, top)


if __name__ == "__main__":
    unittest.main()
