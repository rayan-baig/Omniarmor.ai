"""1.14.0: Pilot core 1.2.0 on OmniArmor. Pilot's welcome is OmniArmor's own
and fits who is there (a business owner's checklist questions, a teacher's
class questions, a visitor's for the side of the site they are on); the
tucked-away robot shrinks into its corner with the core's keepInViewport
instead of the app's own tuck workarounds; and the phone rules of 1.13.0
stay: one helper in one corner, Armo first while his badge has a count,
nothing while typing. Pilot is still never on a student's page.

The welcome itself is checked in Node (tests/js/omniarmor-pilot.test.js,
run by tests/test_pilot.py); this file checks the stylesheet, the config
and the pages."""

import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_pilot import PilotCase, tag  # noqa: E402

from omniarmor_app.version import __version__  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATIC = os.path.join(ROOT, "omniarmor_app", "static")


def read(*parts):
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as f:
        return f.read()


def phone_block(css):
    block = css[css.index("/* One helper, one corner"):]
    return block[:block.index("\n}\n") + 3]


class TestTheConfig(unittest.TestCase):
    def setUp(self):
        self.config = read("omniarmor_app", "static", "pilot-omniarmor.js")

    def test_the_welcome_is_omniarmor_s_own_for_each_audience(self):
        for line in ('tagline: welcome.tagline,', 'welcomePills: welcome.pills,', 'tagline: "Your checklist helper",',
                     'tagline: "Your classroom helper",', 'P("key", "Add my AI key", "settings")',
                     'hideKeySections: ["image", "video"],', "keepInViewport: true,"):
            self.assertIn(line, self.config)
        # Chosen by who is there, which the server puts on Pilot's tag.
        self.assertIn('const welcome = who === "business" ? WELCOME.business : who === "teacher" ? WELCOME.teacher', self.config)
        # The design's own tagline is no longer forced over the welcome.
        self.assertNotIn('tagline: "Your AI copilot. Powered by you."', self.config)

    def test_the_column_keeps_the_core_s_side_room_for_the_small_robot(self):
        self.assertIn('gutter: ["main > .wrap"],', self.config)
        self.assertNotIn("gutter: false", self.config)
        self.assertIn('<main id="main" tabindex="-1">\n  <div class="wrap">', read("omniarmor_app", "templates", "base.html"))


class TestTheStylesheet(unittest.TestCase):
    def setUp(self):
        self.css = read("omniarmor_app", "static", "app.css")

    def test_the_app_s_tuck_workarounds_are_gone(self):
        # Core 1.2.0's keepInViewport shrinks the robot into its corner, so the app no longer counts the
        # core's off-the-edge tuck from its own corners, or holds the robot whole on a phone.
        self.assertNotIn("--pilot-tuck", self.css)
        self.assertNotIn("transform:none;opacity:1", self.css)

    def test_on_a_phone_it_shrinks_in_the_one_corner(self):
        block = phone_block(self.css)
        rule = ("html body .pilot-root.pilot-keep-in.pilot-peek:is(.pilot-at-br,.pilot-at-bl,.pilot-at-tr,.pilot-at-tl) "
                ".pilot-launcher,")
        self.assertIn(rule, block)
        self.assertIn("html body .pilot-root.pilot-keep-in:is(.pilot-at-bl,.pilot-at-tr,.pilot-at-tl):not(.pilot-hello) "
                      ".pilot-launcher{", block)
        self.assertIn("transform-origin:100% 100%;transform:translate(calc(12px - var(--pilot-keep-margin)),"
                      "calc(12px - var(--pilot-keep-margin))) scale(var(--pilot-peek-scale))}", block)

    def test_the_1_13_phone_rules_stay(self):
        block = phone_block(self.css)
        self.assertIn("body:has(.companion-badge:not([hidden])) .pilot-root:not(.pilot-open),"
                      "body .pilot-root.pilot-typing:not(.pilot-open){display:none}", block)
        self.assertIn(".companion:not(:has(.companion-badge:not([hidden]))):not(:has(.companion-bubble:not([hidden]))){display:none}",
                      block)
        self.assertIn("top:auto;left:auto;right:max(12px,env(safe-area-inset-right));bottom:calc(12px + env(safe-area-inset-bottom))",
                      block)

    def test_on_a_computer_the_right_hand_corners_shrink_on_screen(self):
        # The core moves the small robot by --pilot-gap (80px above the tab bar) less its margin; the
        # right-hand corners sit 16px in, so across they count from there, never off the screen.
        wide = re.search(r"@media \(min-width:721px\)\{\n  body\.has-tabs \.pilot-at-br \.pilot-panel[^@]*", self.css).group(0)
        self.assertIn("html body.has-tabs .pilot-root.pilot-keep-in.pilot-peek.pilot-at-br .pilot-launcher,", wide)
        self.assertIn("transform:translate(calc(16px - var(--pilot-keep-margin)),var(--pilot-keep-d)) scale(var(--pilot-peek-scale))", wide)
        self.assertIn("transform:translate(calc(16px - var(--pilot-keep-margin)),calc(-1 * var(--pilot-keep-d))) "
                      "scale(var(--pilot-peek-scale))", wide)
        self.assertIn("body.has-tabs .pilot-root.pilot-at-br,body.has-tabs .pilot-root.pilot-at-tr{right:16px}", self.css)

    def test_the_core_has_what_the_app_relies_on(self):
        core = read("omniarmor_app", "static", "pilot", "pilot.css")
        self.assertIn(".pilot-root.pilot-keep-in { --pilot-keep-d: calc(var(--pilot-gap) - var(--pilot-keep-margin)); }", core)
        self.assertIn(":root.pilot-on.pilot-keep-in { --pilot-side: 30px; }", core)
        self.assertIn('if (config.keepInViewport) for (const n of [rootEl, document.documentElement]) n.classList.add("pilot-keep-in");',
                      read("omniarmor_app", "static", "pilot", "pilot.js"))


class TestThePages(PilotCase):
    """The welcome is chosen in the browser from `data-who` on Pilot's tag (student pages never have
    the tag at all: tests/test_pilot.py TestWherePilotIs)."""

    def test_the_tag_says_who_is_there(self):
        for path in ("/", "/classrooms"):
            self.assertIn('data-who="visitor"', tag(self.page(path)), path)
        self.teacher_signup()
        self.assertIn('data-who="teacher"', tag(self.page("/app/academy/classes")))


class TestVersion(unittest.TestCase):
    def test_version_and_changelog(self):
        self.assertEqual(__version__, "1.14.0")
        log = read("CHANGELOG.md")
        self.assertIn("## 1.14.0", log)
        self.assertIn("Pilot core 1.2.0", log[:log.index("## 1.13.0")])


if __name__ == "__main__":
    unittest.main()
