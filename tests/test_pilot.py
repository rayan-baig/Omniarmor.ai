"""1.10.0: Pilot, the MTRX Horizyn assistant, on Aegizyn (pilot.py,
static/pilot/, docs/PILOT.md).

These check the promises Pilot makes here: it is on the public pages for
grown-ups and on a business's and a teacher's own pages, and on no page a
student uses; the security policy lets the browser reach exactly the AI
providers' addresses and nothing else; the chat window's code loads only
when it is opened; keys and AI calls never touch this server; the tag
carries no one's personal details; the core files are the shared core; no
model name is written anywhere; and the privacy page says what Pilot does.
The core's own tests and Aegizyn's tools (confirm first, the forbidden
actions, the bulk-answer rule, first names only) run in Node:
tests/js/pilot.test.js and tests/js/omniarmor-pilot.test.js.
"""

import json
import os
import re
import shutil
import subprocess
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_classroom_review import SchoolCase, words  # noqa: E402

from omniarmor_app import academy, pilot, plans  # noqa: E402
from omniarmor_app.catalog import rules_for  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATIC = os.path.join(ROOT, "omniarmor_app", "static")
CORE = ("pilot.js", "pilot-store.js", "pilot-mascot.js", "pilot-engine.js", "pilot-providers.js", "pilot-media.js",
        "pilot-render.js", "pilot-panel.js", "pilot.css", "pilot-panel.css", "pilot-motion.js", "pilot-actor.js",
        "pilot-actor.css")
# The moving robot (core 1.1.0 and later): fetched once the page is idle, never under reduce motion.
MOTION = ("pilot-motion.js", "pilot-actor.js", "pilot-actor.css", "pilot-rest-body.webp", "pilot-rest-head.webp",
          "pilot-rest-eyes.webp")
LAZY = ("pilot-panel.js", "pilot-engine.js", "pilot-providers.js", "pilot-media.js", "pilot-render.js", "pilot-panel.css",
        "pilot-omniarmor-pack.js")
PUBLIC = ("/", "/industries", "/industries/resto-aegizyn", "/for/salons-and-barbershops", "/for/schools", "/classrooms",
          "/classrooms/guide", "/demo")
BUSINESS = ("/app", "/app/industry/1", "/app/report", "/app/audit", "/app/notifications", "/app/settings", "/app/plan")
# ("/app" sends a teacher without Whole school to the classes page: 1.11.0.)
# A teacher on the free trial: the school checklist and its report send them
# back to their classes (1.12.0), so they aren't Pilot pages of their own.
TEACHER = ("/app/academy/classes", "/app/notifications", "/app/audit", "/app/settings", "/app/plan")
MODEL_NAMES = re.compile(r"claude-|gpt-?\d|gemini-\d|\bo[1-9]-|sonnet|opus|haiku|llama|dall-?e|\bsora\b|whisper|imagen|\bveo\b",
                         re.IGNORECASE)


def has_pilot(page):
    return 'id="pilot-core"' in page or "pilot/pilot.js" in page


def tag(page):
    return re.search(r'<script src="[^"]*pilot/pilot\.js[^"]*"[^>]*></script>', page, re.S).group(0)


class PilotCase(SchoolCase):
    def page(self, path, client=None):
        response = (client or self.client).get(path)
        self.assertEqual(response.status_code, 200, path)
        return response.data.decode()

    def class_with_maya(self):
        self.teacher_signup()
        class_id = self.add_class()
        self.add_students(class_id, ["Maya"])
        return class_id, self.students(class_id)["Maya"]

    def kid_client(self, learner_id):
        self.post(f"/app/academy/{learner_id}/join-code")
        with self.db() as conn:
            code = conn.execute("SELECT code FROM join_codes WHERE learner_id = ?", (learner_id,)).fetchone()[0]
        kid = self.app.test_client()
        kid.get("/kids")
        response = self.post("/kids", {"code": code}, client=kid)
        self.assertEqual(response.status_code, 302)
        return kid


# --- Where Pilot is, and where it never is ----------------------------------------------------

class TestWherePilotIs(PilotCase):
    def test_on_every_public_page_for_grown_ups(self):
        for path in PUBLIC:
            page = self.page(path)
            self.assertTrue(has_pilot(page), path)
            self.assertIn('data-who="visitor"', page, path)

    def test_not_on_sign_in_password_legal_or_error_pages(self):
        # 1.25.0: Help, pricing and security have Pilot now (test_round13_fixes); the sign-in and legal pages don't.
        for path in ("/login", "/signup", "/forgot", "/privacy", "/terms", "/kids"):
            self.assertFalse(has_pilot(self.page(path)), path)
        self.assertFalse(has_pilot(self.client.get("/no-such-page").data.decode()))

    def test_on_a_business_s_pages(self):
        self.signup()
        for path in BUSINESS:
            page = self.page(path)
            self.assertTrue(has_pilot(page), path)
            self.assertIn('data-who="business"', page, path)
        # The family Academy and Armo's own page are not on the list.
        for path in ("/app/academy", "/app/armo"):
            self.assertFalse(has_pilot(self.page(path)), path)
        self.assertFalse(has_pilot(self.client.get("/app/industry/9999").data.decode()), "not on an error page")

    def test_on_a_teacher_s_pages_but_not_the_class_pages_with_names(self):
        class_id, _ = self.class_with_maya()
        for path in TEACHER:
            page = self.page(path)
            self.assertTrue(has_pilot(page), path)
            self.assertIn('data-who="teacher"', page, path)
        # 1.15.0 (the owner's call): the class page, its join codes and the teacher guide have Pilot too,
        # with every student's name marked private, so "Explain this page" never sends one
        # (tests/test_round6_fixes.py). The certificates and the report still have none.
        for path in (f"/app/academy/classes/{class_id}", f"/app/academy/classes/{class_id}/join-codes",
                     "/classrooms/guide"):
            page = self.client.get(path).data.decode()
            self.assertTrue(has_pilot(page), path)
            self.assertIn('data-who="teacher"', page, path)
        for path in (f"/app/academy/classes/{class_id}/certificates", f"/app/academy/classes/{class_id}/report"):
            self.assertFalse(has_pilot(self.client.get(path).data.decode()), path)

    def test_never_on_a_page_a_student_uses(self):
        """Students are children: no Pilot on their lessons, map, results or
        join page, whether the teacher opens them or the student does."""
        _, maya = self.class_with_maya()
        sid = maya["id"]
        world = academy.CLASSROOM.topics[0]
        student_pages = [f"/app/academy/{sid}", f"/app/academy/{sid}/world/{world}", f"/app/academy/{sid}/world/{world}/stage/1",
                         f"/app/academy/{sid}/practice", f"/app/academy/{sid}/progress", f"/app/academy/{sid}/certificate",
                         f"/app/academy/{sid}/track", f"/app/academy/{sid}/class", f"/app/academy/{sid}/friends",
                         f"/app/academy/{sid}/world/{world}/preview"]
        kid = self.kid_client(sid)
        for client, who in ((self.client, "teacher"), (kid, "student")):
            for path in student_pages:
                response = client.get(path, follow_redirects=True)
                self.assertFalse(has_pilot(response.data.decode()), (who, path, response.status_code))
            # A finished lesson: the results page.
            data = {"attempt": "1", **{f"q{i}": "0" for i in range(academy.LESSON_QUESTIONS)}}
            result = self.post(f"/app/academy/{sid}/world/{world}/stage/1", data, client=client, follow_redirects=True)
            self.assertFalse(has_pilot(result.data.decode()), (who, "result"))
        # A kid's device never gets Pilot, even on a public page or the join page.
        for path in ("/", "/kids", "/classrooms", "/industries"):
            self.assertFalse(has_pilot(kid.get(path, follow_redirects=True).data.decode()), ("kid device", path))

    def test_no_student_page_is_on_any_list(self):
        student = [r.endpoint for r in self.app.url_map.iter_rules()
                   if r.endpoint.startswith(pilot.STUDENT_BLUEPRINTS) or r.endpoint == "classes.my_class"]
        self.assertGreater(len(student), 15)
        for endpoint in student:
            self.assertNotIn(endpoint, pilot.PUBLIC_PAGES | pilot.BUSINESS_PAGES | pilot.TEACHER_PAGES, endpoint)
        for endpoint in pilot.PUBLIC_PAGES | pilot.BUSINESS_PAGES | pilot.TEACHER_PAGES:
            self.assertIn(endpoint, {r.endpoint for r in self.app.url_map.iter_rules()}, endpoint)
        # And the config refuses to start on a student's address even if a page ever carried the tag.
        with open(os.path.join(STATIC, "pilot-omniarmor.js")) as f:
            config = f.read()
        self.assertIn(r"const studentPath = /^\/kids(\/|$)|^\/app\/academy\/\d+(\/|$)/.test(path);", config)
        self.assertIn('const kidView = () => studentPath || !["visitor", "business", "teacher"].includes(who);', config)

    def test_the_demos_have_it_but_not_the_sample_lesson(self):
        page = self.client.get("/demo/business", follow_redirects=True).data.decode()
        self.assertTrue(has_pilot(page))
        self.assertIn('data-demo="on"', page)
        page = self.client.get("/demo/classroom", follow_redirects=True).data.decode()
        self.assertIn('data-who="teacher"', page)
        lesson = re.search(r'href="(/app/academy/\d+/world/\d+/stage/1)"', page) or re.search(
            r'href="(/app/academy/\d+)"', self.client.get(re.search(r'href="(/app/academy/classes/\d+)"', page).group(1)).data.decode())
        self.assertFalse(has_pilot(self.client.get(lesson.group(1), follow_redirects=True).data.decode()))


# --- The tag ---------------------------------------------------------------------------------

class TestThePilotTag(PilotCase):
    def test_one_small_script_and_the_window_only_when_opened(self):
        anon = self.app.test_client()
        self.signup()
        for path in ("/", "/app", "/app/report"):
            page = self.page(path, client=anon if path == "/" else None)
            scripts = re.findall(r'<script src="([^"]+)"', page)
            mine = [s for s in scripts if "pilot" in s]
            self.assertEqual(len(mine), 1, path)
            self.assertRegex(mine[0], r"^/static/pilot/pilot\.js\?v=\d+$")
            for name in ("pilot/pilot-store.js", "pilot/pilot-mascot.js", "pilot-omniarmor.js", "pilot/pilot.css",
                         "pilot/pilot-robot-128.webp", "pilot/pilot-robot-256.webp") + tuple(
                    n if n.startswith("pilot-omniarmor") else f"pilot/{n}" for n in LAZY):
                self.assertRegex(page, rf'data-[a-z0-9-]+="/static/{re.escape(name)}\?v=\d+"', (path, name))
            for name in MOTION:
                self.assertRegex(page, rf'data-[a-z0-9-]+="/static/pilot/{re.escape(name)}\?v=\d+"', (path, name))
            for name in LAZY + MOTION:
                self.assertNotRegex(page, rf'(?:src|href)="[^"]*{re.escape(name)}', (path, name))
            self.assertNotRegex(page, r"<script(?![^>]*\bsrc=)[^>]*>", path)
            self.assertNotIn('style="', page, path)
        with open(os.path.join(STATIC, "pilot", "pilot.js")) as f:
            self.assertIn('window.addEventListener("load", () => setTimeout(boot, 0), { once: true });', f.read())

    def test_it_carries_real_prices_and_no_one_s_details(self):
        self.signup()
        page = self.page("/app")
        t = tag(page)
        facts = json.loads(re.search(r"data-facts='([^']*)'", t).group(1))
        self.assertEqual((facts["pro_price"], facts["plus_price"]), (plans.PRO.price, plans.PLUS.price))
        self.assertEqual((facts["classroom_price"], facts["school_price"]), (plans.CLASSROOM.yearly_price, plans.SCHOOL.yearly_price))
        for private in ("Pat Owner", "owner@example.com", "Acme Logistics"):
            self.assertNotIn(private, t)
        account = re.search(r'data-account="([^"]*)"', t).group(1)
        self.assertRegex(account, r"^[0-9a-f]{16}$")
        self.assertIn('data-account=""', tag(self.page("/", client=self.app.test_client())))
        checklists = json.loads(re.search(r"data-checklists='([^']*)'", t).group(1))
        self.assertEqual([c["id"] for c in checklists], [1, 18])

    def test_a_teacher_s_tag_has_no_student_names(self):
        self.class_with_maya()
        for path in TEACHER:
            self.assertNotIn("Maya", tag(self.page(path)), path)

    def test_people_and_names_are_never_read_from_the_screen(self):
        """"Analyze & explain" skips anything marked data-pilot-private: the
        team list, who changed what, and email addresses."""
        self.signup()
        self.change(1, next(r.key for r in rules_for(1) if r.kind in ("required", "forbidden")), answer="no")
        self.assertRegex(self.page("/app/settings"), r'<ul class="list" data-pilot-private>\s*<li class="row">\s*<span><span class="title">Pat Owner')
        self.assertIn("<td data-pilot-private>Pat Owner</td>", self.page("/app/audit"))
        self.assertIn('<span class="upd-by" data-pilot-private><span class="upd-sep"> · </span>Pat Owner</span>', self.page("/app/report"))

    def test_the_tools_read_the_app_s_own_pages(self):
        """The hooks the tools read: each check's kind and how it counts, and the list of classes."""
        self.signup()
        page = self.page("/app/industry/1")
        self.assertRegex(page, r'<li class="rule" id="rule-[a-z0-9_]+" data-level="[A-Z]+" data-kind="(max|min|required|forbidden)" data-mode="(since|due|)"')
        self.assertIn("<summary>Rule and source</summary>", page)


# --- Security --------------------------------------------------------------------------------

class TestPilotSecurity(PilotCase):
    def test_the_policy_adds_exactly_the_provider_hosts(self):
        csp = self.client.get("/").headers["Content-Security-Policy"]
        rules = dict(rule.strip().split(" ", 1) for rule in csp.split(";"))
        connect = rules["connect-src"].split()
        self.assertEqual(connect, ["'self'", "https://api.anthropic.com", "https://api.openai.com",
                                   "https://generativelanguage.googleapis.com", "https://openrouter.ai", "https://api.groq.com",
                                   "https://api.mistral.ai", "https://api.deepseek.com", "https://api.together.xyz",
                                   "https://api.fireworks.ai", "https://api.x.ai", "http://localhost:*", "http://127.0.0.1:*"])
        for host in connect:
            self.assertNotIn("*.", host)
            self.assertNotIn(host, ("https:", "http:", "*", "data:", "blob:"))
        self.assertEqual(rules["media-src"], "'self' blob:")
        # Nothing else was widened: scripts, styles, fonts, pictures, frames and forms stay this site's own.
        self.assertEqual((rules["default-src"], rules["script-src"], rules["style-src"], rules["font-src"]),
                         ("'self'", "'self'", "'self'", "'self'"))
        self.assertEqual((rules["img-src"], rules["frame-ancestors"], rules["form-action"], rules["object-src"]),
                         ("'self' data:", "'none'", "'self'", "'none'"))
        self.assertNotIn("unsafe", csp)
        policy = self.client.get("/").headers["Permissions-Policy"]
        self.assertIn("microphone=(self)", policy)
        self.assertIn("camera=()", policy)
        page = self.page("/")
        self.assertEqual(re.search(r'data-hosts="([^"]*)"', page).group(1).split(),
                         list(pilot.COMPATIBLE_HOSTS + pilot.LOCAL_HOSTS))

    def test_no_third_party_request_but_the_chosen_provider(self):
        """Fonts and pictures stay self-hosted: a page names no other site at all."""
        anon = self.app.test_client()
        self.signup()
        for path in ("/", "/app", "/classrooms"):
            page = self.page(path, client=anon if path != "/app" else None)
            self.assertNotRegex(page, r'<(?:script|img|link rel="(?:stylesheet|preload|icon|manifest)")[^>]*(?:src|href)="(?:https?:)?//', path)
            self.assertNotRegex(page, r"googleapis|gstatic", path)
        for name in CORE + ("pilot-omniarmor.js", "pilot-omniarmor-pack.js"):
            folder = "pilot" if name in CORE else ""
            with open(os.path.join(STATIC, folder, name)) as f:
                text = f.read()
            self.assertNotRegex(text, r"fonts\.googleapis|gstatic|@import|cdn\.", name)

    def test_keys_and_ai_calls_never_touch_this_server(self):
        for name in CORE + ("pilot-omniarmor.js", "pilot-omniarmor-pack.js"):
            with open(os.path.join(STATIC, "pilot" if name in CORE else "", name)) as f:
                text = f.read()
            for unsafe in (".innerHTML", "insertAdjacentHTML", "document.write", "eval(", "new Function"):
                self.assertNotIn(unsafe, text, (name, unsafe))
            self.assertNotIn("/api/", text, name)
        for rule in self.app.url_map.iter_rules():
            self.assertNotIn("pilot", rule.rule.replace("/classes/pilot", ""), rule.rule)
        with open(os.path.join(STATIC, "pilot", "pilot-providers.js")) as f:
            providers = f.read()
        self.assertIn('"anthropic-dangerous-direct-browser-access": "true"', providers)
        self.assertIn('credentials: "omit"', providers)

    def test_the_pose_pictures_are_listed_and_a_new_one_is_picked_up(self):
        page = self.page("/", client=self.app.test_client())
        poses = dict(pair.split("=", 1) for pair in re.search(r'data-poses="([^"]*)"', tag(page)).group(1).split())
        on_disk = sorted(n[:-5] for n in os.listdir(os.path.join(STATIC, "pilot", "poses")) if n.endswith(".webp"))
        self.assertEqual(sorted(poses), on_disk)
        self.assertGreaterEqual(len(poses), 18)
        for pose, url in poses.items():
            self.assertIn(pose, pilot.POSES)
            self.assertRegex(url, rf"^/static/pilot/poses/{re.escape(pose)}\.webp\?v=\d+$")
        folder = os.path.join(self.tmp.name, "poses")
        os.mkdir(folder)
        for name in ("wave.png", "wave.webp", "kick.png", "dance.webp", "notes.txt"):
            open(os.path.join(folder, name), "wb").close()
        with self.app.app_context():
            self.assertEqual(pilot.pose_files(folder), {"kick": "kick.png", "wave": "wave.webp"})
            self.assertEqual(pilot.pose_files(os.path.join(folder, "missing")), {})

    def test_the_moving_robot_comes_late_and_never_under_reduce_motion(self):
        with open(os.path.join(STATIC, "pilot", "pilot.js"), encoding="utf-8") as f:
            loader = f.read()
        self.assertIn('window.matchMedia("(prefers-reduced-motion: reduce)").matches;', loader)
        self.assertIn("if (still || !assets.motion || !assets.actor || !assets.restBody) return;", loader)
        self.assertIn("setTimeout(() => soon(go, { timeout: 4000 }), 1500);", loader)
        for name in MOTION[3:]:
            with open(os.path.join(STATIC, "pilot", name), "rb") as f:
                self.assertLess(len(f.read()), 12_000, name)
        # The same limits as the MTRX Horizyn site: each pose fetched only when a move first needs it.
        total = 0
        for name in os.listdir(os.path.join(STATIC, "pilot", "poses")):
            with open(os.path.join(STATIC, "pilot", "poses", name), "rb") as f:
                data = f.read()
            self.assertTrue(data[:4] == b"RIFF" and data[8:12] == b"WEBP" and len(data) < 25_000, name)
            total += len(data)
        self.assertLess(total, 420_000)

    def test_the_robot_keeps_clear_of_armo_the_tab_bar_and_blocked_checks(self):
        with open(os.path.join(STATIC, "pilot-omniarmor.js"), encoding="utf-8") as f:
            config = f.read()
        self.assertIn('yieldTo: [".companion"],', config)
        # 1.12.0: every status tag, badge and note, not just a Blocked status.
        self.assertRegex(config, r'avoid: \[".tag", ".top-n", ".bundle", ".msg",')
        self.assertIn('".companion-bubble", ".companion-fix", ".companion-badge"', config)
        self.assertIn('".topbar .nav", ".lockup",', config)   # 1.15.0: and the Aegizyn name
        self.assertIn('".pick", "[data-teacher-guide] p"', config)   # 1.16.0: the Select boxes, the teacher guide
        with open(os.path.join(STATIC, "app.css"), encoding="utf-8") as f:
            css = f.read()
        # Above the tab bar, and measured there by the core: --pilot-gap is a plain length.
        self.assertIn("body.has-tabs .pilot-root{--pilot-gap:80px}", css)
        self.assertIn("body.has-tabs .pilot-root{--pilot-gap:76px}", css)
        # The core's own gutter keeps the last lines clear.
        self.assertIn("var(--pilot-gutter)", css)
        self.assertNotIn("armo-talking", css)


# --- The files -------------------------------------------------------------------------------

class TestPilotFiles(unittest.TestCase):
    def test_every_core_file_is_the_shared_core(self):
        versions = set()
        for name in CORE:
            with open(os.path.join(STATIC, "pilot", name)) as f:
                text = f.read()
            first = text.splitlines()[0]
            match = re.fullmatch(r"(?://|/\*) Pilot core (\d+\.\d+\.\d+) · " + re.escape(name), first)
            self.assertTrue(match, (name, first))
            versions.add(match.group(1))
            if name.endswith(".js"):
                self.assertIn(f'const VERSION = "{match.group(1)}";', text, name)
        self.assertEqual(len(versions), 1, versions)
        with open(os.path.join(ROOT, "docs", "PILOT.md")) as f:
            self.assertIn(f"core {versions.pop()}", f.read())

    def test_the_robot_is_the_owner_s_picture_small_enough(self):
        for size, most in ((128, 15_000), (256, 40_000)):
            with open(os.path.join(STATIC, "pilot", f"pilot-robot-{size}.webp"), "rb") as f:
                data = f.read()
            self.assertTrue(data[:4] == b"RIFF" and data[8:12] == b"WEBP" and len(data) < most, size)
            self.assertTrue(data[12:16] == b"VP8X" and data[20] & 0x10, f"{size}: no transparency")

    def test_pilot_s_fonts_are_this_site_s_own_and_the_page_s_styles_stay_out(self):
        with open(os.path.join(STATIC, "app.css")) as f:
            css = f.read()
        fonts = re.findall(r"url\(fonts/pilot/([a-z-]+\.woff2)\)", css)
        self.assertEqual(sorted(fonts), ["inter-latin-ext.woff2", "inter-latin.woff2", "montserrat-latin-ext.woff2",
                                         "montserrat-latin.woff2"])
        for name in fonts:
            with open(os.path.join(STATIC, "fonts", "pilot", name), "rb") as f:
                self.assertEqual(f.read(4), b"wOF2", name)
        for name in ("OFL-Inter.txt", "OFL-Montserrat.txt"):
            self.assertTrue(os.path.exists(os.path.join(STATIC, "fonts", "pilot", name)), name)
        # The page's own form, link and focus styles never reach into Pilot's window.
        for rule in ("textarea:where(:not(.pilot-root *)){", "a:where(:not(.pilot-root *)){",
                     ":where(:not(.pilot-root *)):focus-visible{", "label:where(:not(.pilot-root *)){"):
            self.assertIn(rule, css)

    def test_no_model_name_is_written_anywhere(self):
        files = [os.path.join(STATIC, "pilot", n) for n in CORE] + [
            os.path.join(STATIC, n) for n in ("pilot-omniarmor.js", "pilot-omniarmor-pack.js")] + [
            os.path.join(ROOT, p) for p in ("docs/PILOT.md", "omniarmor_app/templates/_pilot.html", "omniarmor_app/pilot.py",
                                            "tests/js/pilot.test.js", "tests/js/omniarmor-pilot.test.js", "CHANGELOG.md",
                                            "omniarmor_app/templates/privacy.html")]
        for path in files:
            with open(path, encoding="utf-8") as f:
                hits = MODEL_NAMES.findall(f.read())
            self.assertFalse(hits, (path, hits))

    def test_the_window_matches_the_design_words(self):
        with open(os.path.join(STATIC, "pilot", "pilot-panel.js")) as f:
            panel = f.read()
        with open(os.path.join(STATIC, "pilot-omniarmor.js")) as f:
            panel += f.read()
        for text in ("Your AI copilot. Powered by you.", "Hello! I'm Pilot.", "How can I help you today?", "Ask anything…",
                     "Get things done…", "Help with code…", "Analyze & explain…", "Customize with your API key", "Type a message…",
                     "Bring Your Own API Key", "AI keys are for grown-ups (the AI companies require 18+)."):
            self.assertIn(text, panel)

    def test_the_core_and_omniarmor_s_tools_in_node(self):
        node = shutil.which("node")
        if node is None:
            self.skipTest("Node is not installed here (CI has it)")
        for name in CORE:
            if name.endswith(".js"):
                subprocess.run([node, "--check", os.path.join(STATIC, "pilot", name)], check=True)
        for name in ("pilot-omniarmor.js", "pilot-omniarmor-pack.js"):
            subprocess.run([node, "--check", os.path.join(STATIC, name)], check=True)
        for test in ("pilot.test.js", "omniarmor-pilot.test.js"):
            result = subprocess.run([node, "--test", "--test-reporter=tap", os.path.join(ROOT, "tests", "js", test)],
                                    capture_output=True, text=True, timeout=120)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("# fail 0", result.stdout)


class TestPilotPrivacyPage(PilotCase):
    def test_the_privacy_page_says_what_pilot_sends_and_to_whom(self):
        text = words(self.page("/privacy"))
        for said in ("Pilot", "your own AI key", "never sees your AI key", "never on a page a student uses",
                     "only to the AI company you chose", "AI keys are for grown-ups"):
            self.assertIn(said, text)

    def test_robot_pictures_are_served_as_webp(self):
        response = self.client.get("/static/pilot/pilot-robot-128.webp")
        self.assertEqual(response.mimetype, "image/webp")
        response.close()


if __name__ == "__main__":
    unittest.main()
