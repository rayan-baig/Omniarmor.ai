"""The Future Owner Academy, checked the way kids and parents meet it.

- Every quiz question has exactly one right answer and distinct options,
  across many seeds, tracks, worlds and families; questions with numbers are
  worked out again here, and no wrong option may be the true answer too.
- Practice never shows the same question twice in a row.
- A certificate can't be earned without passing the Owner's Challenge.
- A kid on their own device can't reach the parent's billing or settings.
- Kid join codes expire and work once.
"""

import difflib
import functools
import html
import json
import math
import os
import random
import re
import sys
import unittest
from datetime import timedelta
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from e2e_helpers import post_forms  # noqa: E402
from test_webapp import AppTestCase  # noqa: E402

from omniarmor_app import academy, academy_views  # noqa: E402
from omniarmor_app.catalog import INDUSTRIES  # noqa: E402
from omniarmor_app.db import iso, utcnow  # noqa: E402
from omniarmor_app.tracking import org_industry_ids  # noqa: E402
from omni_armor_rules import CATALOG, evaluate  # noqa: E402
from omni_armor_rules.rule import _fmt  # noqa: E402

BASIC = academy.TRACKS["launchpad"]


def _norm(text):
    return re.sub(r"[\W_]+", " ", text).strip().casefold()


def _num(text):
    return int(text.replace(",", "").lstrip("$"))


def _rules_titled(title, industry_id=None):
    return [r for i, rules in CATALOG.items() if industry_id in (None, i) for r in rules if r.title == title]


def _reading(text):
    return float(re.search(r"-?[\d,]*\.?\d+", text).group(0).replace(",", ""))


def _light_truth(q, industry_id=None):
    """The lights a reading really gets, from the rule named in the question
    (its copy in the industry when the quiz is about one industry). One rule
    title is in four industries, and CryptoArmor's copy warns earlier."""
    m = re.match(r"Rule: (.+?)\. The (limit|minimum) is (.+?)\. Today's reading is (.+?)\. Which light", q.prompt)
    if m:
        title, _, limit, reading = m.groups()
        rules = [r for r in _rules_titled(title, industry_id) if _fmt(r.limit, r.unit) == limit]
        value = _reading(reading)
        value = int(value) if value.is_integer() else value
        return {evaluate(r, value)[0] for r in rules}
    m = re.match(r'Rule: (.+?)\. OmniArmor asks: ".*" The answer is (Yes|No)\. Which light\?$', q.prompt, re.S)
    if m:
        return {evaluate(r, m.group(2) == "Yes")[0] for r in _rules_titled(m.group(1), industry_id)}
    return set()


def _words(text):
    return re.sub(r"[\W_]+", " ", text).casefold().split()


@functools.lru_cache(maxsize=None)
def _citation(rule):
    core = re.split(r" \(|;", rule.citation)[0].strip().casefold()
    return core if re.search(r"\d", core) else None


@functools.lru_cache(maxsize=None)
def _siblings(rule):
    """The same legal duty in other industries: same title, same key or the
    same provision cited ("21 CFR 1304.11(c)")."""
    return [(i, r) for i, rules in CATALOG.items() for r in rules
            if r.title == rule.title or r.key == rule.key or (_citation(r) and _citation(r) == _citation(rule))]


RULE_FACTS = [(r'^Why does "(.+)" matter\?$', "cost"), (r'^If "(.+)" is broken, what should the team do\?$', "action"),
              (r'^To check "(.+)", what does OmniArmor ask\?$', "input"),
              (r'^Which kind of business follows "(.+)"\?$', "sector")]


# Questions with numbers in them: (pattern, the true answer worked out from its numbers).
WORKED = [
    (r"must be done at least every (\d+) days\. It was last done (\d+) days ago\. How many days are left\?",
     lambda n, done: str(int(n) - int(done))),
    (r"must be done every (\d+) days\. It was last done (\d+) days ago\. Is it late\?",
     lambda n, ago: "Yes, it's overdue" if int(ago) > int(n) else "No, there's still time"),
    (r"Today is (\w+)\. A job is due in (\d+) days\. Which day is that\?",
     lambda day, n: academy.WEEKDAYS[(academy.WEEKDAYS.index(day) + int(n)) % 7]),
    (r"earned \$([\d,]+) this month and spent \$([\d,]+)\. What is the profit\?",
     lambda r, c: academy.money(_num(r) - _num(c))),
    (r"If the profit was \$([\d,]+) and the company paid a \$([\d,]+) fine, how much profit is left\?",
     lambda p, f: academy.money(_num(p) - _num(f))),
    (r"Each item costs \$(\d+) to make and sells for \$(\d+)\. What is the profit on (\d+) items\?",
     lambda c, p, n: f"${(int(p) - int(c)) * int(n)}"),
    (r"A \$(\d+) jacket is (\d+)% off\. What is the sale price\?",
     lambda p, off: f"${int(p) - int(p) * int(off) // 100}"),
    (r"buys a game for \$(\d+) and adds a (\d+)% markup\. What is the price\?",
     lambda c, up: f"${int(c) + int(c) * int(up) // 100}"),
    (r"budget is \$(\d+)\. You spent \$(\d+), \$(\d+) and \$(\d+)\. How much is left\?",
     lambda b, x, y, z: f"${int(b) - int(x) - int(y) - int(z)}"),
    (r"You save \$(\d+) every week\. How much do you have after (\d+) weeks\?",
     lambda w, k: f"${int(w) * int(k)}"),
    (r"pays (\d+)% interest a year\. How much interest does \$(\d+) earn in one year\?",
     lambda rate, amount: f"${int(amount) * int(rate) // 100}"),
    (r"A new machine costs \$(\d+)\. You earn \$(\d+) profit per item\.",
     lambda c, p: str(math.ceil(int(c) / int(p)))),
]


class TestEveryQuestionHasOneRightAnswer(unittest.TestCase):
    FAMILIES = [[1, 18], [7], [50], list(INDUSTRIES), [14, 22, 30]]

    def check(self, q, where, industry_id=None):
        where = (*where, q.prompt[:80])
        self.assertGreaterEqual(len(q.options), 2, where)
        self.assertTrue(0 <= q.answer < len(q.options), where)
        self.assertTrue(all(isinstance(o, str) and o.strip() for o in q.options), where)
        # Distinct, even ignoring case, spaces and punctuation.
        self.assertEqual(len({_norm(o) for o in q.options}), len(q.options), (where, q.options))
        self.assertTrue(q.prompt.strip() and q.explain.strip(), where)
        for text in [q.prompt, q.explain, *q.options]:
            self.assertNotRegex(text, r"[{}]|\$-|\bNone\b", where)
        if q.kind == "truefalse":
            self.assertEqual(q.options, ["True", "False"], where)
        right = q.options[q.answer]
        for pattern, truth in WORKED:
            m = re.search(pattern, q.prompt)
            if m:
                true = truth(*m.groups())
                self.assertEqual(right, true, (where, q.options))
                self.assertNotIn(true, [o for i, o in enumerate(q.options) if i != q.answer], where)
                self.worked += 1
        for pattern, field in RULE_FACTS:
            m = re.match(pattern, q.prompt)
            if m and industry_id is not None:
                rule = next(r for r in CATALOG[industry_id] if r.title == m.group(1))
                family = _siblings(rule)
                wrong = [o for i, o in enumerate(q.options) if i != q.answer]
                if field == "sector":
                    self.assertEqual(right, INDUSTRIES[industry_id]["sector"], where)
                    true = {INDUSTRIES[i]["sector"] for i, _ in family}
                else:
                    self.assertEqual(right, getattr(rule, field), where)
                    true = {getattr(r, field) for _, r in family}
                for option in wrong:
                    self.assertNotIn(option, true, (where, "the same rule in another industry"))
                    for t in true:
                        ratio = difflib.SequenceMatcher(None, _words(option), _words(t)).ratio()
                        self.assertLess(ratio, 0.85, (where, option, t))
                self.worked += 1
        if q.kind == "light":
            self.assertEqual(q.options, academy.LIGHTS, where)
            truths = _light_truth(q, industry_id)
            self.assertTrue(truths, where)
            if industry_id is not None:
                self.assertEqual(len(truths), 1, where)
            self.assertIn(q.answer, {academy.LIGHT_INDEX[t] for t in truths}, where)
            self.worked += 1

    def test_many_seeds_every_track_and_world(self):
        self.worked = 0
        rng = random.Random(2026)
        quizzes = 0
        for t in academy.TRACK_LIST:
            for w in t.worlds:
                n = t.stages(w)
                stages = {1, 2, min(10, n), n // 2 or 1, n} | {rng.randint(1, n) for _ in range(2)}
                for stage in sorted(stages):
                    for seed in range(4):
                        family = self.FAMILIES[(seed + stage) % len(self.FAMILIES)]
                        questions = academy.quiz(t, w.number, stage, "Acme Works", family,
                                                 academy.attempt_seed(rng.randint(1, 10 ** 6), t.key, w.number,
                                                                      stage, seed + 1))
                        quizzes += 1
                        self.assertEqual(len({q.prompt for q in questions}), len(questions), (t.key, w.key, stage))
                        for q in questions:
                            self.check(q, (t.key, w.key, stage, seed), w.industry_id or None)
        self.assertGreater(quizzes, 2000)
        self.assertGreater(self.worked, 3000, "the worked-out checks really ran")

    def test_duels_too(self):
        self.worked = 0
        for number in academy.DUEL_WORLDS:
            for stage in (1, 17, 50):
                for seed in ("a", "b", "c"):
                    questions = academy.duel_quiz(number, stage, f"{seed}-{number}-{stage}")
                    self.assertEqual(len(questions), academy.DUEL_QUESTIONS)
                    for q in questions:
                        self.check(q, ("duel", number, stage, seed))

    def test_a_question_asked_in_two_worlds_never_marks_the_others_answer_wrong(self):
        seen = {}
        pools = [(key, bank["questions"]) for key, bank in academy._BANK.items()]
        pools += [(name, getattr(academy, name)) for name in ("PRO_TALK", "OWN_IT", "GRIT", "RESPECT", "HIRING",
                                                              "TOUGH_CALLS", "CUSTOMERS", "COMPETE", "MOVES")]
        for where, items in pools:
            for item in items:
                seen.setdefault(_norm(item[0]), []).append((where, _norm(item[1]), {_norm(item[2]), _norm(item[3])}))
        for prompt, uses in seen.items():
            rights = {u[1] for u in uses}
            for where, _, wrongs in uses:
                self.assertFalse(rights & wrongs, (prompt, where))
        facts = {}
        for key, bank in academy._BANK.items():
            for statement, truth, _ in bank["facts"]:
                facts.setdefault(_norm(statement), set()).add(truth)
        self.assertEqual([s for s, truths in facts.items() if len(truths) > 1], [])


class AcademyCase(AppTestCase):
    def setUp(self):
        super().setUp()
        self.signup()   # Acme Logistics, in two industries
        self.post("/app/academy/learners", {"nickname": "Sam", "avatar": "rocket", "track": "launchpad"})
        with self.db() as conn:
            self.lid = conn.execute("SELECT id FROM learners").fetchone()[0]
            self.org_id = conn.execute("SELECT id FROM orgs").fetchone()[0]
            self.industries = org_industry_ids(conn, self.org_id)

    def questions(self, world, stage, attempt, track=BASIC):
        return academy.quiz(track, world, stage, "Acme Logistics", self.industries,
                            academy.attempt_seed(self.lid, track.key, world, stage, attempt))

    def play(self, world, stage, right, client=None):
        """Plays a level from its page. `right` is how many to answer right
        (True for all, False for none), or a function of a question that says
        whether to answer it right."""
        client = client or self.client
        page = client.get(f"/app/academy/{self.lid}/world/{world}/stage/{stage}").data.decode()
        form = next(f for f in post_forms(page) if f.field("attempt") is not None)
        attempt = int(form.field("attempt")["value"])
        questions = self.questions(world, stage, attempt)
        if not callable(right):
            count = len(questions) if right is True else 0 if right is False else right
            right = lambda q, count=count, order=[id(q) for q in questions]: order.index(id(q)) < count  # noqa: E731
        data = form.values()
        for i, q in enumerate(questions):
            data[f"q{i}"] = str(q.answer if right(q) else (q.answer + 1) % len(q.options))
        return client.post(f"/app/academy/{self.lid}/world/{world}/stage/{stage}", data=data), questions

    def mark_passed(self, *levels):
        with self.db() as conn:
            for world, stage in levels:
                conn.execute("INSERT OR REPLACE INTO learner_progress (learner_id, level, attempts, best_score,"
                             " best_stars, completed_at) VALUES (?, ?, 1, 5, 3, '2026-01-01T00:00:00')",
                             (self.lid, academy.level_id(BASIC, world, stage)))
            conn.commit()

    def practice_prompts(self, page):
        return [html.unescape(re.sub(r"<[^>]+>", "", m)).split(None, 1)[1].strip()
                for m in re.findall(r"<legend>(.*?)</legend>", page, re.S)]


class TestPracticeNeverRepeats(AcademyCase):
    """A family in two industries is asked "What kind of work does Acme
    Logistics do?" with either industry as the right answer. Missed once each
    way, the question went into the practice deck twice, and practice asked
    it twice."""

    def miss_world_one(self, attempts):
        for _ in range(attempts):
            self.play(1, 1, right=False)

    def test_a_question_missed_with_two_right_answers_is_one_practice_card(self):
        work = "What kind of work does Acme Logistics do?"
        answers = set()
        attempt = 0
        while len(answers) < 2:   # until both industries have been the right answer
            attempt += 1
            self.assertLess(attempt, 30)
            response, questions = self.play(1, 1, right=False)
            answers |= {q.options[q.answer] for q in questions if q.prompt == work}
        page = self.client.get(f"/app/academy/{self.lid}/practice").data.decode()
        prompts = self.practice_prompts(page)
        self.assertEqual(prompts.count(work), 1, prompts)
        for a, b in zip(prompts, prompts[1:]):
            self.assertNotEqual(a, b)

    def test_no_two_questions_in_a_row_are_the_same(self):
        self.miss_world_one(6)
        page = self.client.get(f"/app/academy/{self.lid}/practice").data.decode()
        prompts = self.practice_prompts(page)
        self.assertTrue(prompts)
        self.assertEqual(len(prompts), len(set(prompts)), prompts)

    def test_the_next_round_does_not_start_with_the_question_just_answered(self):
        self.miss_world_one(1)
        page = self.client.get(f"/app/academy/{self.lid}/practice").data.decode()
        form = next(f for f in post_forms(page) if f.field("deck") is not None)
        data = form.values()
        with self.db() as conn:
            rows = {r["id"]: json.loads(r["question"]) for r in conn.execute("SELECT * FROM learner_mistakes")}
        deck = [int(i) for i in data["deck"].split(",")]
        for i, mistake in enumerate(deck):   # the last one wrong, the rest right
            q = rows[mistake]
            data[f"q{i}"] = str(q["answer"] if i < len(deck) - 1 else (q["answer"] + 1) % len(q["options"]))
        result = self.client.post(f"/app/academy/{self.lid}/practice", data=data).data.decode()
        self.assertIn(f"{len(deck) - 1} of {len(deck)} fixed", result)
        last = self.practice_prompts(page)[-1]
        again = self.client.get(f"/app/academy/{self.lid}/practice").data.decode()
        self.assertNotIn(last, self.practice_prompts(again)[:1])

    def test_answering_it_right_with_the_other_answer_counts_as_practice(self):
        work = "What kind of work does Acme Logistics do?"
        _, questions = self.play(1, 1, right=False)
        first = next(q.options[q.answer] for q in questions if q.prompt == work)
        # Everything right, except that question while it still has the same right answer.
        for _ in range(30):
            _, questions = self.play(1, 1, right=lambda q: q.prompt != work or q.options[q.answer] != first)
            if any(q.prompt == work and q.options[q.answer] != first for q in questions):
                break
        else:
            self.fail("the other right answer never came up")
        with self.db() as conn:
            rows = conn.execute("SELECT question, streak FROM learner_mistakes").fetchall()
        work_rows = [r["streak"] for r in rows if json.loads(r["question"])["prompt"] == work]
        self.assertEqual(work_rows, [1], "one card, pushed out a day")


class TestCertificateNeedsAPass(AcademyCase):
    final = academy.FINAL_WORLD.number

    def certificate(self):
        return self.client.get(f"/app/academy/{self.lid}/certificate")

    def test_no_certificate_before_the_challenge_opens(self):
        self.assertEqual(self.certificate().status_code, 302)
        # The challenge is locked until stage 1 of every world is passed; a
        # perfect answer sheet sent to it anyway changes nothing.
        questions = self.questions(self.final, 1, 1)
        data = {"attempt": "1", **{f"q{i}": str(q.answer) for i, q in enumerate(questions)}}
        response = self.post(f"/app/academy/{self.lid}/world/{self.final}/stage/1", data)
        self.assertEqual(response.status_code, 302)
        with self.db() as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM learner_progress").fetchone()[0], 0)
        self.assertEqual(self.certificate().status_code, 302)
        self.assertNotIn("Future Owner of", self.client.get(f"/app/academy/{self.lid}").data.decode())

    def test_one_short_of_the_pass_mark_is_no_certificate_and_the_mark_is(self):
        self.mark_passed(*[(n, 1) for n in BASIC.topics])
        needed = academy.pass_mark(BASIC, academy.FINAL_WORLD, 1)
        page, questions = self.play(self.final, 1, right=needed - 1)
        self.assertNotIn("You earned the Future Owner certificate", page.data.decode())
        self.assertEqual(self.certificate().status_code, 302)
        with self.db() as conn:
            stars = conn.execute("SELECT best_stars FROM learner_progress WHERE level = ?",
                                 (academy.level_id(BASIC, self.final, 1),)).fetchone()[0]
        self.assertEqual(stars, 0)
        page, _ = self.play(self.final, 1, right=needed)
        self.assertIn("You earned the Future Owner certificate", page.data.decode())
        cert = self.certificate()
        self.assertEqual(cert.status_code, 200)
        self.assertIn("Future Owner of Acme Logistics", cert.data.decode())

    def test_checking_answers_one_at_a_time_cannot_be_used_to_retry(self):
        self.mark_passed(*[(n, 1) for n in BASIC.topics])
        questions = self.questions(self.final, 1, 1)
        url = f"/app/academy/{self.lid}/world/{self.final}/stage/1"
        for i, q in enumerate(questions):   # every first answer wrong, then the right one
            wrong = (q.answer + 1) % len(q.options)
            self.assertFalse(self.post(url, {"attempt": "1", "check": str(i), "choice": str(wrong)}).get_json()["right"])
            self.assertFalse(self.post(url, {"attempt": "1", "check": str(i), "choice": str(q.answer)}).get_json()["right"])
        data = {"attempt": "1", **{f"q{i}": str(q.answer) for i, q in enumerate(questions)}}
        self.post(url, data)
        self.assertEqual(self.certificate().status_code, 302)


class KidCase(AcademyCase):
    def setUp(self):
        super().setUp()
        self.kid = self.app.test_client()

    def join_code(self):
        self.post(f"/app/academy/{self.lid}/join-code")
        page = self.client.get(f"/app/academy/{self.lid}").data.decode()
        return re.search(r"KID-[A-Z2-9]{8}", page).group(0)

    def join(self, code, client=None):
        client = client or self.kid
        page = client.get("/kids").data.decode()
        form = next(f for f in post_forms(page) if f.field("code") is not None)
        data = form.values()
        data["code"] = code
        return client.post(form.action or "/kids", data=data)


class TestKidCannotReachTheGrownUps(KidCase):
    def snapshot(self):
        with self.db() as conn:
            return {t: conn.execute(f"SELECT * FROM {t} ORDER BY rowid").fetchall()
                    for t in ("orgs", "users", "memberships", "org_industries", "items", "invites", "learners",
                              "join_codes", "friend_codes")}

    def url_for_rule(self, rule):
        values = {"learner_id": self.lid, "industry_id": 1, "rule_key": "annual_mvr_review", "user_id": 1,
                  "world_number": 1, "stage": 1, "duel_id": 1, "friend_id": self.lid, "slug": "fleetarmor",
                  "token": "x", "filename": "app.css"}
        url = rule.rule
        for arg in rule.arguments:
            url = re.sub(rf"<(?:\w+:)?{arg}>", str(values[arg]), url)
        return url

    def test_every_grown_up_page_and_action_is_out_of_reach(self):
        self.assertEqual(self.join(self.join_code()).status_code, 302)
        self.assertEqual(self.kid.get(f"/app/academy/{self.lid}").status_code, 200)
        with self.kid.session_transaction() as s:
            token = s["_csrf"]
        # What a kid may use: their own Academy pages, and pages anyone can open.
        kid_ok = {"academy.level_map", "academy.change_armo", "academy.certificate", "academy.duel",
                  "academy.new_duel", "academy.friends", "academy.practice", "academy.choose_track",
                  "academy.world_page", "academy.play"}
        before = self.snapshot()
        checked = 0
        with mock.patch("omniarmor_app.academy_plan._stripe", side_effect=AssertionError("no Stripe call")):
            for rule in self.app.url_map.iter_rules():
                endpoint = rule.endpoint
                if endpoint in kid_ok or endpoint == "static" or endpoint.split(".")[0] in ("public", "auth", "kids"):
                    continue
                if endpoint == "plan.stripe_webhook":
                    continue    # signed by Stripe, not a person's page
                if endpoint.startswith("_test_"):
                    continue    # exists only in tests (it always fails, for the error page's test)
                url = self.url_for_rule(rule)
                for method in sorted(rule.methods - {"HEAD", "OPTIONS"}):
                    data = {"csrf_token": token, "confirm": "Acme Logistics", "name": "Kid Co", "timezone": "UTC",
                            "industries": "2", "nickname": "X", "avatar": "rocket", "personality": "chief",
                            "action": "save", "answer": "yes", "email_reminders": "on"}
                    response = self.kid.open(url, method=method, data=data if method == "POST" else None)
                    checked += 1
                    where = (method, url, response.status_code)
                    self.assertNotIn(response.status_code, (200, 201, 204), where)
                    if response.status_code in (301, 302, 303):
                        where = (*where, response.headers["Location"])
                        location = response.headers["Location"]
                        self.assertTrue("/login" in location or location.endswith(f"/app/academy/{self.lid}"),
                                        where)
                    else:
                        self.assertIn(response.status_code, (403, 404, 405), where)
                    # Still signed in as the kid, and only as the kid.
                    with self.kid.session_transaction() as s:
                        self.assertIsNone(s.get("user_id"), where)
                        self.assertEqual(s.get("kid"), self.lid, where)
        self.assertGreater(checked, 25)
        self.assertEqual(self.snapshot(), before)

    def test_billing_and_settings_pages_say_nothing_to_a_kid(self):
        self.app.config.update(STRIPE_SECRET_KEY="sk_test", ACADEMY_STRIPE_PRICE="price_1")
        with self.db() as conn:
            conn.execute("UPDATE orgs SET stripe_customer_id = 'cus_1', academy_status = 'past_due'")
            conn.commit()
        self.join(self.join_code())
        for path in ("/app/academy/plan", "/app/settings", "/app/report.csv", "/app/audit.csv", "/app/notifications"):
            response = self.kid.get(path, follow_redirects=True)
            page = response.data.decode()
            self.assertNotIn("owner@example.com", page, path)
            self.assertNotIn("Manage billing", page, path)
            self.assertNotIn("cus_1", page, path)
            self.assertNotIn("Delete workspace", page, path)
        self.assertNotIn("Update your card", self.kid.get(f"/app/academy/{self.lid}").data.decode())


class TestJoinCodes(KidCase):
    def test_a_code_works_on_one_device_once(self):
        code = self.join_code()
        self.assertTrue(self.join(code.lower()).headers["Location"].endswith(f"/app/academy/{self.lid}/world/1/stage/1"))
        second = self.app.test_client()
        response = self.join(code, client=second)
        self.assertEqual(response.status_code, 400)
        self.assertIn("didn&#39;t work", response.data.decode())
        self.assertEqual(second.get(f"/app/academy/{self.lid}").status_code, 302)
        # The used code is gone from the parent's page too.
        self.assertNotIn(code, self.client.get(f"/app/academy/{self.lid}").data.decode())

    def test_a_new_code_replaces_the_old_one(self):
        old = self.join_code()
        new = self.join_code()
        self.assertNotEqual(old, new)
        self.assertEqual(self.join(old).status_code, 400)
        self.assertEqual(self.join(new).status_code, 302)

    def test_codes_expire(self):
        from omniarmor_app.academy_views import JOIN_CODE_DAYS
        code = self.join_code()
        with self.db() as conn:
            expires = conn.execute("SELECT expires_at FROM join_codes").fetchone()[0]
        made = utcnow()
        self.assertAlmostEqual((academy_views.academy_plan._parse(expires) - made).total_seconds(),
                               timedelta(days=JOIN_CODE_DAYS).total_seconds(), delta=120)
        with self.db() as conn:
            conn.execute("UPDATE join_codes SET expires_at = ?", (iso(utcnow() - timedelta(seconds=1)),))
            conn.commit()
        self.assertEqual(self.join(code).status_code, 400)
        self.assertNotIn(code, self.client.get(f"/app/academy/{self.lid}").data.decode())

    def test_signing_the_kid_out_everywhere_kills_the_code_too(self):
        code = self.join_code()
        self.post(f"/app/academy/{self.lid}/devices/sign-out")
        self.assertEqual(self.join(code).status_code, 400)

    def test_a_removed_kids_code_does_not_work(self):
        code = self.join_code()
        self.post(f"/app/academy/{self.lid}/delete")
        self.assertEqual(self.join(code).status_code, 400)

    def test_two_devices_racing_with_one_code_only_one_gets_in(self):
        """Both devices look the code up before either uses it up: the second
        must not get in on a code that is already spent."""
        code = self.join_code()
        real = academy_views.get_db
        racer = self.app.test_client()

        class Racing:
            def __init__(self, conn):
                self.conn = conn

            def execute(self, sql, *args):
                result = self.conn.execute(sql, *args)
                if sql.startswith("SELECT learners.* FROM join_codes"):
                    row = result.fetchone()
                    # The other device finishes joining right now.
                    with mock.patch.object(academy_views, "get_db", real):
                        self.test.assertEqual(self.test.join(code, client=racer).status_code, 302)
                    return _One(row)
                return result

            def __getattr__(self, name):
                return getattr(self.conn, name)

        class _One:
            def __init__(self, row):
                self.row = row

            def fetchone(self):
                return self.row

        Racing.test = self
        self.kid.get("/kids")
        with mock.patch.object(academy_views, "get_db", lambda: Racing(real())):
            response = self.join(code)
        self.assertEqual(racer.get(f"/app/academy/{self.lid}").status_code, 200)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.kid.get(f"/app/academy/{self.lid}").status_code, 302)
