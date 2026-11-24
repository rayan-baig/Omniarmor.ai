"""1.20.0: Pilot core 1.4.2 on Aegizyn.

The thirteen core files are MTRX Horizyn's core 1.4.2 (a1c9253), unchanged
(tests/test_core140.py checks every header). Aegizyn's own config uses what
1.4.2 adds: `match` words so a typed question with no key finds the app's own
answer, its own "Explain this page" in place of the AI-only "Summarise this"
(screenChip), and the core's handle; it drops the 1.4.1 workaround
(hideWhenCrowded: false on tab-bar pages), and app.css moves the computer's
tucked robot by --pilot-keep-dy. The behaviour is tested in Node
(tests/js/omniarmor-pilot.test.js and tests/js/pilot.test.js, run by
tests/test_pilot.py). Students' pages still have no Pilot and no Armo."""

import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_classroom_review import SchoolCase  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def read(*parts):
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as f:
        return f.read()


class TestTheConfig(unittest.TestCase):
    config = read("omniarmor_app", "static", "pilot-omniarmor.js")

    def test_the_1_4_1_workaround_is_gone(self):
        self.assertNotIn("hideWhenCrowded", self.config)
        self.assertNotIn("handle: false", self.config)
        self.assertNotIn("matchTyped: false", self.config)

    def test_the_screen_chip_is_the_app_s_own_answer(self):
        self.assertIn('screenChip: { label: "Explain this page", answer: explainPageAnswer },', self.config)

    def test_pills_and_suggestions_carry_match_words(self):
        block = self.config[self.config.index("const MATCH = {"):self.config.index("const withMatch")]
        for label in ("What's due or overdue?", "Add students", "Which checklist fits me?", "Is it safe for students?",
                      "See the prices", "Explain this page"):
            self.assertIn(f'"{label}": [', block)
        self.assertIn("welcome.pills = welcome.pills.map(withMatch);", self.config)
        self.assertIn("const list = pageChips().map(withMatch);", self.config)

    def test_the_computer_rule_uses_the_core_s_own_room(self):
        css = read("omniarmor_app", "static", "app.css")
        self.assertNotIn("var(--pilot-keep-d))", css)
        self.assertEqual(len(re.findall(r"var\(--pilot-keep-dy\)", css)), 2)


class TestStudentsStillHaveNoHelpers(SchoolCase):
    def test_a_student_s_pages_have_no_pilot_and_no_armo(self):
        # Even on the teacher's own signed-in device (1.19.0 showed Armo on the kids' join page there).
        self.teacher_signup()
        class_id = self.add_class()
        self.add_students(class_id, ["Maya"])
        maya = self.students(class_id)["Maya"]
        for path in (f"/app/academy/{maya['id']}", f"/app/academy/{maya['id']}/class", "/kids"):
            page = self.client.get(path, follow_redirects=True).data.decode()
            for never in ('id="pilot-core"', "pilot-omniarmor.js", "pilot/pilot.js", "armo.js", 'class="companion'):
                self.assertNotIn(never, page, f"{path}: {never}")


class TestVersion(unittest.TestCase):
    def test_version_and_changelog(self):
        from omniarmor_app.version import __version__
        self.assertGreaterEqual(tuple(map(int, __version__.split("."))), (1, 20, 0))
        log = read("CHANGELOG.md")
        top = log[log.index("## 1.20.0"):log.index("## 1.19.0")]
        for said in ("core 1.4.2", "no key needed", "Explain this page", "above the tab bar", "no Pilot"):
            self.assertIn(said, top)


if __name__ == "__main__":
    unittest.main()
