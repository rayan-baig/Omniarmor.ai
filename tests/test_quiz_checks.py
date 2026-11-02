"""The right answers stay on the server, and one-time links stay out of logs.

Quizzes used to carry each right answer in the page (data-answer) for the
instant feedback, so a player could read them in the page source before
answering, including in a duel against a friend. Now the page asks the server
about each first answer, the server keeps that first answer, and the final
score uses the kept answers.
"""
import json
import os
import sys
import unittest
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from omniarmor_app import academy  # noqa: E402
from omniarmor_app.redact import redact  # noqa: E402
import test_academy as ta  # noqa: E402
from test_webapp import AppTestCase  # noqa: E402

BASIC = ta.BASIC


class AcademyHelpers(AppTestCase):
    """The helpers from test_academy, without running its tests a second time."""
    add = ta.TestAcademyPages.add
    learner_id = ta.TestAcademyPages.learner_id
    org = ta.TestAcademyPages.org
    answer = ta.TestAcademyPages.answer

    def setUp(self):
        super().setUp()
        self.signup()


class DuelHelpers(AppTestCase):
    def setUp(self):
        super().setUp()
        self.signup()
        self.post("/app/academy/learners", {"nickname": "Sam", "avatar": "rocket"})
        self.other = self.app.test_client()
        self.signup(email="friend@example.com", client=self.other)
        self.post("/app/academy/learners", {"nickname": "Riley", "avatar": "star"}, client=self.other)
        with self.db() as conn:
            ids = dict(conn.execute("SELECT nickname, id FROM learners").fetchall())
            conn.execute("UPDATE learners SET track_chosen = 1")
            conn.commit()
        self.sam, self.riley = ids["Sam"], ids["Riley"]

    code_for = ta.TestFriendsAndDuels.code_for
    befriend = ta.TestFriendsAndDuels.befriend
    play = ta.TestFriendsAndDuels.play


class TestLevelAnswersStayOnTheServer(AcademyHelpers):
    def questions(self, lid, world_number=1, stage=1, attempt=1):
        _, industry_ids = self.org()
        return academy.quiz(BASIC, world_number, stage, "Acme Logistics", industry_ids,
                            academy.attempt_seed(lid, BASIC.key, world_number, stage, attempt))

    def check(self, lid, i, choice, attempt=1, client=None):
        return self.post(f"/app/academy/{lid}/world/1/stage/1",
                         {"attempt": str(attempt), "check": str(i), "choice": str(choice)}, client=client)

    def test_the_page_does_not_hold_the_answers(self):
        self.add()
        lid = self.learner_id()
        page = self.client.get(f"/app/academy/{lid}/world/1/stage/1").data.decode()
        self.assertIn("Quiz time", page)
        self.assertNotIn("data-answer", page)
        form = page.split('<form class="ac-quiz"', 1)[1].split("</form>", 1)[0]
        for q in self.questions(lid):
            self.assertNotIn(q.explain, form)       # the explanation often names the answer

    def test_a_check_says_right_or_wrong_and_explains(self):
        self.add()
        lid = self.learner_id()
        q = self.questions(lid)[0]
        right = self.check(lid, 0, q.answer).get_json()
        self.assertEqual(right, {"right": True, "chosen": q.answer, "answer": q.answer, "explain": q.explain})
        q1 = self.questions(lid)[1]
        wrong = self.check(lid, 1, (q1.answer + 1) % len(q1.options)).get_json()
        self.assertFalse(wrong["right"])
        self.assertEqual(wrong["answer"], q1.answer)

    def test_the_first_answer_is_kept(self):
        self.add()
        lid = self.learner_id()
        questions = self.questions(lid)
        wrong = (questions[0].answer + 1) % len(questions[0].options)
        self.assertFalse(self.check(lid, 0, wrong).get_json()["right"])
        # Trying the right one afterwards doesn't change the verdict...
        again = self.check(lid, 0, questions[0].answer).get_json()
        self.assertFalse(again["right"])
        self.assertEqual(again["chosen"], wrong)
        # ...and handing in the right answer for it doesn't either.
        page = self.answer(lid, 1, 1).data.decode()
        self.assertNotIn("Perfect score", page)
        with self.db() as conn:
            self.assertEqual(conn.execute("SELECT best_score FROM learner_progress").fetchone()[0], len(questions) - 1)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM quiz_checks").fetchone()[0], 0)   # cleared once graded

    def test_unchecked_questions_still_use_the_form(self):
        self.add()
        lid = self.learner_id()
        q = self.questions(lid)[2]
        self.check(lid, 2, q.answer)
        self.assertIn("Perfect score", self.answer(lid, 1, 1).data.decode())

    def test_the_next_attempt_cannot_be_peeked_at(self):
        self.add()
        lid = self.learner_id()
        self.assertEqual(self.check(lid, 0, 0, attempt=2).status_code, 409)
        with self.db() as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM quiz_checks").fetchone()[0], 0)

    def test_bad_checks_and_other_families(self):
        self.add()
        lid = self.learner_id()
        self.assertEqual(self.check(lid, 99, 0).status_code, 400)
        self.assertEqual(self.check(lid, 0, 99).status_code, 400)
        self.assertEqual(self.check(lid, -1, 0).status_code, 400)
        self.assertEqual(self.post(f"/app/academy/{lid}/world/1/stage/1",
                                   {"attempt": "1", "check": "0", "choice": "x"}).status_code, 400)
        other = self.app.test_client()
        self.signup(email="rival@example.com", client=other)
        self.assertEqual(self.check(lid, 0, 0, client=other).status_code, 404)
        # Without the form's token it isn't accepted at all.
        self.assertEqual(self.client.post(f"/app/academy/{lid}/world/1/stage/1",
                                          data={"attempt": "1", "check": "0", "choice": "0"}).status_code, 400)

    def test_locked_stage_cannot_be_checked(self):
        self.add()
        lid = self.learner_id()
        response = self.post(f"/app/academy/{lid}/world/1/stage/2", {"attempt": "1", "check": "0", "choice": "0"})
        self.assertEqual(response.status_code, 302)
        with self.db() as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM quiz_checks").fetchone()[0], 0)

    def test_practice_uses_kept_answers(self):
        self.add()
        lid = self.learner_id()
        self.answer(lid, 1, 1, right=False)
        page = self.client.get(f"/app/academy/{lid}/practice").data.decode()
        self.assertNotIn("data-answer", page)
        with self.db() as conn:
            deck = conn.execute("SELECT id, question FROM learner_mistakes ORDER BY due_at, id").fetchall()
        answers = [json.loads(r["question"])["answer"] for r in deck]
        options = [len(json.loads(r["question"])["options"]) for r in deck]
        data = {"deck": ",".join(str(r["id"]) for r in deck)}
        first = self.post(f"/app/academy/{lid}/practice",
                          dict(data, check="0", choice=str((answers[0] + 1) % options[0]))).get_json()
        self.assertFalse(first["right"])
        self.assertEqual(first["answer"], answers[0])
        for i, a in enumerate(answers):
            data[f"q{i}"] = str(a)
        self.assertIn(f"{len(deck) - 1} of {len(deck)} fixed", self.post(f"/app/academy/{lid}/practice", data).data.decode())
        # A deck that was already checked can't be probed.
        stale = self.post(f"/app/academy/{lid}/practice", dict(data, check="0", choice="0"))
        self.assertEqual(stale.status_code, 409)


class TestDuelAnswersStayOnTheServer(DuelHelpers):
    def test_duel_page_has_no_answers_and_kept_answers_count(self):
        self.befriend()
        response = self.post(f"/app/academy/{self.sam}/duels", {"friend": self.riley, "world": 15})
        duel_id = int(response.headers["Location"].rsplit("/", 1)[1])
        page = self.client.get(response.headers["Location"]).data.decode()
        self.assertIn("Quiz time", page)
        self.assertNotIn("data-answer", page)
        with self.db() as conn:
            d = conn.execute("SELECT * FROM duels WHERE id = ?", (duel_id,)).fetchone()
        questions = academy.duel_quiz(d["world"], d["stage"], d["seed"])
        q = questions[0]
        url = f"/app/academy/{self.sam}/duels/{duel_id}"
        self.assertFalse(self.post(url, {"check": "0", "choice": str((q.answer + 1) % len(q.options))}).get_json()["right"])
        # Riley's own check of the same question is separate from Sam's.
        self.assertTrue(self.post(f"/app/academy/{self.riley}/duels/{duel_id}", {"check": "0", "choice": str(q.answer)},
                                  client=self.other).get_json()["right"])
        self.play(self.sam, duel_id, len(questions))
        with self.db() as conn:
            self.assertEqual(conn.execute("SELECT challenger_score FROM duels").fetchone()[0], len(questions) - 1)
        # After playing, checks are refused.
        self.assertEqual(self.post(url, {"check": "1", "choice": "0"}).status_code, 409)


class TestTokensStayOutOfLogs(unittest.TestCase):
    def test_redact(self):
        self.assertEqual(redact("GET /reset/abcDEF_123-x HTTP/1.1"), "GET /reset/[hidden] HTTP/1.1")
        self.assertEqual(redact("/signup?invite=tok123&x=1"), "/signup?invite=[hidden]&x=1")
        self.assertEqual(redact("https://a.example/signup?a=1&invite=tok"), "https://a.example/signup?a=1&invite=[hidden]")
        self.assertEqual(redact("/app/overview?next=/x"), "/app/overview?next=/x")
        self.assertIsNone(redact(None))

    def test_access_log_line(self):
        from omniarmor_app.access_log import RedactingLogger

        logger = RedactingLogger(SimpleNamespace(
            errorlog="-", loglevel="info", accesslog=None, syslog=False, capture_output=False, logconfig=None,
            logconfig_dict={}, logconfig_json=None, disable_redirect_access_to_syslog=False, user=0, group=0,
            umask=0, access_log_format="", syslog_addr=None, syslog_prefix=None, syslog_facility="user",
            logger_class=None, statsd_host=None, dogstatsd_tags="", statsd_prefix="", raw_env=[]))
        environ = {"REQUEST_METHOD": "GET", "RAW_URI": "/reset/SECRETTOKEN", "SERVER_PROTOCOL": "HTTP/1.1",
                   "PATH_INFO": "/reset/SECRETTOKEN", "QUERY_STRING": "invite=SECRET2",
                   "HTTP_REFERER": "https://x.example/reset/SECRETTOKEN", "REMOTE_ADDR": "1.2.3.4"}
        resp = SimpleNamespace(status="200 OK", headers=[], sent=10)
        req = SimpleNamespace(headers=[("REFERER", "https://x.example/signup?invite=SECRET2")])
        from datetime import timedelta
        atoms = logger.atoms(resp, req, environ, timedelta(seconds=0))
        line = " ".join(str(v) for v in atoms.values())
        self.assertNotIn("SECRETTOKEN", line)
        self.assertNotIn("SECRET2", line)
        self.assertIn("/reset/[hidden]", atoms["r"])

    def test_stripe_checkout_return_is_hidden(self):
        """Stripe sends the payer back to /app/academy/plan?welcome=1&session_id=cs_...
        and the plan page settles the payment with that id. The access log wrote
        it out in full, and percent-encoded inside /login?next=... when the
        payer came back signed out."""
        line = "GET /app/academy/plan?welcome=1&session_id=cs_live_a1B2c3 HTTP/1.1"
        self.assertEqual(redact(line), "GET /app/academy/plan?welcome=1&session_id=[hidden] HTTP/1.1")
        self.assertEqual(redact("session_id=cs_live_a1B2c3"), "session_id=[hidden]")  # gunicorn's query atom
        encoded = "/login?next=%2Fapp%2Facademy%2Fplan%3Fwelcome%3D1%26session_id%3Dcs_live_a1B2c3"
        self.assertNotIn("cs_live_a1B2c3", redact(encoded))
        self.assertTrue(redact(encoded).startswith("/login?next=%2Fapp%2Facademy%2Fplan%3Fwelcome%3D1%26session_id%3D"))
        self.assertNotIn("SECRET", redact("/login?next=%2Fsignup%3Finvite%3DSECRET"))
        self.assertNotIn("SECRET", redact("https://x.example/login?next=%2Freset%2FSECRET"))
        # Nothing else is touched.
        self.assertEqual(redact("/app/report?only=problems&page=2"), "/app/report?only=problems&page=2")

    def test_the_signed_out_return_from_stripe_keeps_the_id_out_of_the_log(self):
        from omniarmor_app.access_log import RedactingLogger
        from omniarmor_app import create_app
        import tempfile
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        app = create_app(TESTING=True, DATABASE=os.path.join(tmp.name, "t.db"), SCHEDULER_ENABLED=False,
                         SECRET_KEY="x" * 32, BACKUP_DIR=os.path.join(tmp.name, "b"))
        response = app.test_client().get("/app/academy/plan?welcome=1&session_id=cs_live_SECRET1")
        self.assertEqual(response.status_code, 302)
        target = response.headers["Location"]
        self.assertIn("SECRET1", target)  # the sign-in page carries it on, encoded
        logger = RedactingLogger(SimpleNamespace(
            errorlog="-", loglevel="info", accesslog=None, syslog=False, capture_output=False, logconfig=None,
            logconfig_dict={}, logconfig_json=None, disable_redirect_access_to_syslog=False, user=0, group=0,
            umask=0, access_log_format="", syslog_addr=None, syslog_prefix=None, syslog_facility="user",
            logger_class=None, statsd_host=None, dogstatsd_tags="", statsd_prefix="", raw_env=[]))
        path, _, query = target.partition("?")
        from datetime import timedelta
        for raw in ("/app/academy/plan?welcome=1&session_id=cs_live_SECRET1", f"{path}?{query}"):
            p, _, q = raw.partition("?")
            environ = {"REQUEST_METHOD": "GET", "RAW_URI": raw, "SERVER_PROTOCOL": "HTTP/1.1",
                       "PATH_INFO": p, "QUERY_STRING": q, "REMOTE_ADDR": "1.2.3.4"}
            atoms = logger.atoms(SimpleNamespace(status="302 FOUND", headers=[], sent=10),
                                 SimpleNamespace(headers=[("REFERER", "https://checkout.stripe.com/")]),
                                 environ, timedelta(seconds=0))
            self.assertNotIn("SECRET1", " ".join(str(v) for v in atoms.values()), raw)

    def test_every_query_value_a_route_reads_is_known(self):
        """A new route reading a secret from its query string has to be added
        to SECRET_PARAMS (or here, when the value is harmless)."""
        import re
        from omniarmor_app.redact import SECRET_PARAMS
        harmless = {"chapter", "welcome", "industry", "next", "only", "page"}
        app_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "omniarmor_app")
        names = set()
        for name in os.listdir(app_dir):
            if name.endswith(".py"):
                with open(os.path.join(app_dir, name), encoding="utf-8") as f:
                    names |= set(re.findall(r"request\.(?:args|values)\.get(?:list)?\(\s*[\"'](\w+)[\"']", f.read()))
        self.assertTrue({"invite", "session_id"} <= names)
        self.assertEqual(names - harmless - set(SECRET_PARAMS), set())
        for name in names & set(SECRET_PARAMS):
            self.assertEqual(redact(f"/x?{name}=SECRET"), f"/x?{name}=[hidden]")

    def test_every_address_with_a_token_in_its_path_is_hidden(self):
        """Path parts named like a secret (/reset/<token>) are hidden; any new
        one would show up here."""
        from omniarmor_app import create_app
        import tempfile
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        app = create_app(TESTING=True, DATABASE=os.path.join(tmp.name, "t.db"), SCHEDULER_ENABLED=False,
                         SECRET_KEY="x" * 32, BACKUP_DIR=os.path.join(tmp.name, "b"))
        secret_parts = [rule.rule for rule in app.url_map.iter_rules()
                        if any(arg in ("token", "code", "invite", "session_id", "key", "secret")
                               for arg in rule.arguments)]
        self.assertEqual(secret_parts, ["/reset/<token>"])
        for rule in secret_parts:
            self.assertNotIn("SECRET", redact(rule.replace("<token>", "SECRET")))

    def test_dockerfile_uses_it(self):
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        with open(os.path.join(root, "Dockerfile")) as f:
            self.assertIn("--logger-class omniarmor_app.access_log.RedactingLogger", f.read())


class TestErrorsDoNotKeepTokens(AcademyHelpers):
    def test_crash_on_reset_page_records_a_hidden_path(self):
        from omniarmor_app import auth

        original = auth.render_template

        def boom(*a, **kw):
            raise RuntimeError("boom")

        with self.db() as conn:
            user_id = conn.execute("SELECT id FROM users").fetchone()[0]
        token, token_hash = auth.new_token()
        with self.db() as conn:
            conn.execute("INSERT INTO password_resets (token_hash, user_id, created_at, expires_at)"
                         " VALUES (?, ?, '2026-01-01T00:00:00+00:00', '2999-01-01T00:00:00+00:00')", (token_hash, user_id))
            conn.commit()
        self.app.config["PROPAGATE_EXCEPTIONS"] = False
        auth.render_template = boom
        try:
            with self.assertLogs(self.app.logger, "ERROR") as logs:
                self.assertEqual(self.app.test_client().get(f"/reset/{token}").status_code, 500)
        finally:
            auth.render_template = original
        self.assertNotIn(token, "\n".join(logs.output))
        with self.db() as conn:
            path = conn.execute("SELECT path FROM app_errors").fetchone()[0]
        self.assertEqual(path, "/reset/[hidden]")


if __name__ == "__main__":
    unittest.main()
