"""1.17.0: Pilot core 1.4.0 on OmniArmor, useful before an AI key.

The thirteen core files are the MTRX Horizyn site's core 1.4.0, unchanged.
The welcome buttons and page suggestions that need no AI now answer at once,
from what the page shows and the plain facts on Pilot's script tag, or go
straight to a page: what's due or overdue, explaining a check, what a colour
means, how join codes work, printing certificates, what OmniArmor does and
its prices. Answers never name a student (a class is counted), and a
student's page still has no Pilot. The answers themselves are checked in
Node (tests/js/omniarmor-pilot.test.js, run by tests/test_pilot.py).

Also: the business Academy page's headline speaks to the grown-up."""

import html
import json
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_classroom_review import SchoolCase  # noqa: E402
from test_webapp import AppTestCase  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATIC = os.path.join(ROOT, "omniarmor_app", "static")
CORE = ("pilot-actor.css", "pilot-actor.js", "pilot-engine.js", "pilot-mascot.js", "pilot-media.js", "pilot-motion.js",
        "pilot-panel.css", "pilot-panel.js", "pilot-providers.js", "pilot-render.js", "pilot-store.js", "pilot.css",
        "pilot.js")


def read(*parts):
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as f:
        return f.read()


def pilot_data(page):
    """The data-* attributes on Pilot's script tag, or None when there is no Pilot."""
    m = re.search(r'<script src="[^"]*pilot/pilot\.js[^"]*" defer id="pilot-core"(.*?)></script>', page, re.S)
    if not m:
        return None
    return {k: html.unescape(a or b) for k, a, b in re.findall(r'data-([\w-]+)=(?:"([^"]*)"|\'([^\']*)\')', m.group(1))}


class TestCoreFiles(unittest.TestCase):
    def test_all_thirteen_core_files_are_core_1_4_0(self):
        folder = os.path.join(STATIC, "pilot")
        self.assertEqual(sorted(n for n in os.listdir(folder) if n.endswith((".js", ".css"))), sorted(CORE))
        for name in CORE:
            text = read("omniarmor_app", "static", "pilot", name)
            self.assertRegex(text.splitlines()[0], r"^(//|/\*) Pilot core 1\.4\.0 · " + re.escape(name), name)
            version = re.search(r'const VERSION = "([\d.]+)"', text)
            if version:
                self.assertEqual(version.group(1), "1.4.0", name)

    def test_the_core_knows_links_and_answers(self):
        panel = read("omniarmor_app", "static", "pilot", "pilot-panel.js")
        for said in ("function siteLink(", "function noAi(", "async function answerWith(", "DEFAULT_MORE"):
            self.assertIn(said, panel)
        self.assertIn("function cornerPasses(", read("omniarmor_app", "static", "pilot", "pilot-mascot.js"))


class TestTheConfigUsesThem(unittest.TestCase):
    config = read("omniarmor_app", "static", "pilot-omniarmor.js")

    def test_the_welcome_pills_that_need_no_ai_are_answers_or_links(self):
        for pill in ('ANSWER("bolt", "What\'s due or overdue?", dueAnswer)', 'ANSWER("help", "Explain this check", explainAnswer)',
                     'ANSWER("spark", "What does this colour mean?", colourAnswer)', 'ANSWER("help", "How do join codes work?"',
                     'LINK("copy", "Print certificates", certificatesLink())', 'ANSWER("chat", "What does OmniArmor do?"',
                     'LINK("bolt", "See the prices", "/help#prices")', 'ANSWER("help", "Is it safe for students?", SAFE)',
                     'ANSWER("bolt", "How does the free trial work?"'):
            self.assertIn(pill, self.config)
        self.assertIn('answerMore: "Want more? Add your AI key to ask anything.",', self.config)

    def test_answers_never_read_what_is_marked_private_and_never_go_to_the_network(self):
        self.assertIn('copy.querySelectorAll("[data-pilot-private]")', self.config)
        self.assertNotIn("fetch(", self.config)
        self.assertNotIn("XMLHttpRequest", self.config)
        # A class is counted, never listed: the class page's student table is never read.
        for private in ("data-class-progress", "data-join-codes", "data-student", "ac-code-name"):
            self.assertNotIn(private, self.config)


class TestTheFactsOnTheTag(SchoolCase):
    def test_a_teacher_s_tag_has_the_join_code_facts_and_class_names_only(self):
        self.teacher_signup()
        class_id = self.add_class("Room 12")
        self.add_students(class_id, ["Maya", "Leo"])
        data = pilot_data(self.client.get(f"/app/academy/classes/{class_id}").data.decode())
        self.assertIsNotNone(data)
        self.assertEqual(data["who"], "teacher")
        self.assertEqual(json.loads(data["classes"]), [{"id": class_id, "name": "Room 12"}])
        facts = json.loads(data["facts"])
        self.assertEqual(facts["join_code_days"], 7)
        self.assertEqual(facts["join_path"], "/kids")
        tag = self.client.get(f"/app/academy/classes/{class_id}").data.decode()
        tag = tag[tag.index('id="pilot-core"'):tag.index("</script>", tag.index('id="pilot-core"'))]
        for name in ("Maya", "Leo"):
            self.assertNotIn(name, tag)

    def test_a_student_s_pages_still_have_no_pilot(self):
        self.teacher_signup()
        class_id = self.add_class()
        self.add_students(class_id, ["Maya"])
        maya = self.students(class_id)["Maya"]
        for path in (f"/app/academy/{maya['id']}", "/kids"):
            page = self.client.get(path, follow_redirects=True).data.decode()
            self.assertIsNone(pilot_data(page), path)
            self.assertNotIn("pilot-omniarmor.js", page, path)


class TestABusinessTag(AppTestCase):
    def test_a_business_has_no_classes_on_its_tag(self):
        self.signup()
        data = pilot_data(self.client.get("/app").data.decode())
        self.assertEqual(data["who"], "business")
        self.assertEqual(json.loads(data["classes"]), [])

    def test_a_visitor_gets_the_page_s_pilot_and_the_prices_page_exists(self):
        data = pilot_data(self.client.get("/").data.decode())
        self.assertEqual(data["who"], "visitor")
        self.assertEqual(json.loads(data["classes"]), [])
        # The links the answers use are real pages.
        page = self.client.get("/help").data.decode()
        for anchor in ('id="prices"', 'id="lights"', 'id="check"', 'id="reminders"'):
            self.assertIn(anchor, page)
        self.assertIn('id="price"', self.client.get("/classrooms").data.decode())
        for path in ("/demo", "/industries", "/privacy", "/classrooms/guide", "/signup"):
            self.assertEqual(self.client.get(path).status_code, 200, path)


class TestTheAcademyPageSpeaksToTheGrownUp(AppTestCase):
    def test_the_headline_is_not_in_a_kid_s_voice(self):
        self.signup()
        page = self.client.get("/app/academy").data.decode()
        self.assertIn('<h1 class="ac-title">Teach your kids the family business</h1>', page)
        self.assertNotIn("Learn the family business!", page)
        self.assertNotIn("level up your picture", page)


class TestVersion(unittest.TestCase):
    def test_version_and_changelog(self):
        from omniarmor_app.version import __version__
        self.assertEqual(__version__, "1.17.0")
        log = read("CHANGELOG.md")
        top = log[log.index("## 1.17.0"):log.index("## 1.16.0")]
        for said in ("Pilot core 1.4.0", "without an AI key", "join codes", "certificates", "never names a student",
                     "Teach your kids the family business"):
            self.assertIn(said, top)


if __name__ == "__main__":
    unittest.main()
