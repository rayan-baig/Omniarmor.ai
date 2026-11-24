"""Fast and solid (1.8.0): the readiness check, the timers' heartbeats and
watchdogs, timeouts and retries on outside calls, the pages that stay
friendly when the database or Stripe is down, start-up checks, gzip, the
masked form token and the new indexes."""

import gzip
import os
import re
import socket
import sys
import tempfile
import threading
import time
import unittest
from datetime import timedelta
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_webapp import AppTestCase  # noqa: E402

from omniarmor_app import academy_plan, autopilot, compress, create_app, health, jobs, notify  # noqa: E402
from omniarmor_app.config import SettingsError, load_config  # noqa: E402
from omniarmor_app.db import connect, iso, migrate, utcnow  # noqa: E402
from omniarmor_app.version import __version__  # noqa: E402

CHECKS = {"database", "settings", "alerts_timer", "daily_timer", "daily_job", "backup", "disk"}


def beat_at(path, name, when, started=None):
    conn = connect(path)
    try:
        conn.execute("INSERT INTO job_heartbeats (name, beat_at, started_at) VALUES (?, ?, ?)"
                     " ON CONFLICT (name) DO UPDATE SET beat_at = excluded.beat_at, started_at = excluded.started_at",
                     (name, iso(when), iso(started or when)))
        conn.commit()
    finally:
        conn.close()


class ReadyCase(AppTestCase):
    def setUp(self):
        super().setUp()
        self.app.config["SCHEDULER_ENABLED"] = True
        health.forget()
        self.addCleanup(health.forget)
        # As a server that has been up for an hour: no start-up grace.
        started = mock.patch.object(health, "_started", time.monotonic() - 3600)
        started.start()
        self.addCleanup(started.stop)

    def ready(self):
        health.forget()
        response = self.client.get("/readyz")
        return response.status_code, response.get_json()

    def fresh(self):
        now = utcnow()
        for name in ("alerts", "daily"):
            beat_at(self.db_path, name, now, now - timedelta(hours=1))


class TestReadyz(ReadyCase):
    def test_all_well_is_200_and_says_only_ok(self):
        self.fresh()
        status, body = self.ready()
        self.assertEqual(status, 200, body)
        self.assertEqual(body, {"status": "ok", "checks": {name: "ok" for name in CHECKS}})

    def test_it_never_leaks_settings_versions_paths_or_people(self):
        self.signup()
        self.app.config.update(SMTP_PASSWORD="smtp-secret-pw", STRIPE_SECRET_KEY="sk_live_secret",
                               OPERATOR_EMAIL="boss@example.com", ENV_NAME="production", SMTP_HOST="")
        status, _ = self.ready()
        text = self.client.get("/readyz").get_data(as_text=True)
        self.assertEqual(status, 503)
        for secret in (self.app.config["SECRET_KEY"], "smtp-secret-pw", "sk_live_secret", "boss@example.com",
                       "owner@example.com", self.tmp.name, __version__, "SMTP_HOST", "flask", "werkzeug", "sqlite"):
            self.assertNotIn(secret.lower(), text.lower(), secret)
        self.assertEqual(set(self.client.get("/readyz").get_json()["checks"]), CHECKS)
        self.assertEqual(self.client.get("/readyz").headers["Cache-Control"], "no-store")

    def test_a_stopped_minute_timer_fails_it(self):
        self.fresh()
        beat_at(self.db_path, "alerts", utcnow() - timedelta(minutes=6), utcnow() - timedelta(hours=1))
        status, body = self.ready()
        self.assertEqual((status, body["status"], body["checks"]["alerts_timer"]), (503, "fail", "fail"))
        self.assertEqual(body["checks"]["daily_timer"], "ok")

    def test_a_stopped_daily_timer_fails_it(self):
        self.fresh()
        beat_at(self.db_path, "daily", utcnow() - timedelta(minutes=31), utcnow() - timedelta(hours=1))
        status, body = self.ready()
        self.assertEqual((status, body["checks"]["daily_timer"]), (503, "fail"))

    def test_a_long_daily_run_holding_its_lock_counts_as_running(self):
        self.fresh()
        beat_at(self.db_path, "daily", utcnow() - timedelta(minutes=50), utcnow() - timedelta(hours=1))
        conn = connect(self.db_path)
        conn.execute("INSERT INTO job_locks (name, holder, taken_at, expires_at) VALUES ('daily', 'x', ?, ?)",
                     (iso(utcnow()), iso(utcnow() + timedelta(minutes=2))))
        conn.commit()
        conn.close()
        self.assertEqual(self.ready()[1]["checks"]["daily_timer"], "ok")

    def test_timers_that_never_ran_fail_after_the_start_up_grace(self):
        self.assertEqual(self.ready()[1]["checks"]["alerts_timer"], "fail")
        with mock.patch.object(health, "_started", time.monotonic()):
            self.assertEqual(self.ready()[1]["checks"]["alerts_timer"], "ok")

    def test_timers_turned_off_with_none_running_say_off(self):
        self.app.config["SCHEDULER_ENABLED"] = False
        status, body = self.ready()
        self.assertEqual(status, 200, body)
        self.assertEqual((body["checks"]["alerts_timer"], body["checks"]["daily_timer"],
                          body["checks"]["daily_job"]), ("off", "off", "off"))

    def test_a_daily_job_that_hasnt_finished_in_two_days_fails_it(self):
        self.fresh()
        conn = connect(self.db_path)
        conn.execute("INSERT INTO job_runs (job, run_date, started_at, finished_at, result) VALUES"
                     " ('daily', '2000-01-01', ?, ?, 'ok')", (iso(utcnow() - timedelta(hours=51)),) * 2)
        conn.commit()
        conn.close()
        self.assertEqual(self.ready(), (503, {"status": "fail", "checks": dict(
            {n: "ok" for n in CHECKS}, daily_job="fail")}))

    def test_a_new_database_whose_daily_job_never_finished_fails_after_two_days(self):
        now = utcnow()
        beat_at(self.db_path, "alerts", now, now - timedelta(hours=60))
        beat_at(self.db_path, "daily", now, now - timedelta(hours=60))
        body = self.ready()[1]
        self.assertEqual((body["checks"]["daily_job"], body["checks"]["backup"]), ("fail", "fail"))

    def test_an_old_backup_fails_it(self):
        self.fresh()
        os.makedirs(self.app.config["BACKUP_DIR"])
        path = os.path.join(self.app.config["BACKUP_DIR"], "omniarmor-20000101-000000-000000.db")
        open(path, "w").close()
        old = time.time() - 51 * 3600
        os.utime(path, (old, old))
        self.assertEqual(self.ready()[1]["checks"]["backup"], "fail")

    def test_an_unreachable_database_fails_it(self):
        self.fresh()
        self.app.config["DATABASE"] = self.tmp.name   # a folder: SQLite can't open it
        status, body = self.ready()
        self.assertEqual((status, body["checks"]["database"]), (503, "fail"))

    def test_it_never_makes_an_empty_database_where_the_real_one_should_be(self):
        missing = os.path.join(self.tmp.name, "not-attached", "omniarmor.db")
        self.app.config["DATABASE"] = missing
        status, body = self.ready()
        self.assertEqual((status, body["checks"]["database"]), (503, "fail"))
        self.assertFalse(os.path.exists(missing))

    def test_production_without_email_fails_settings(self):
        self.fresh()
        self.app.config.update(ENV_NAME="production", SMTP_HOST="")
        self.assertEqual(self.ready()[1]["checks"]["settings"], "fail")
        self.app.config.update(SMTP_HOST="smtp.example.com")
        self.assertEqual(self.ready()[1]["checks"]["settings"], "ok")

    def test_the_answer_is_kept_ten_seconds_so_it_stays_cheap(self):
        self.fresh()
        health.forget()
        with mock.patch.object(health, "checks", wraps=health.checks) as checked:
            for _ in range(20):
                self.assertEqual(self.client.get("/readyz").status_code, 200)
        self.assertEqual(checked.call_count, 1)

    def test_closed_to_crawlers(self):
        self.assertIn("Disallow: /readyz", self.client.get("/robots.txt").get_data(as_text=True))


class TestReadyCommand(ReadyCase):
    def test_it_names_what_is_wrong_and_what_to_do(self):
        self.fresh()
        self.app.config.update(ENV_NAME="production", SMTP_HOST="")
        result = self.app.test_cli_runner().invoke(args=["ready"])
        self.assertEqual(result.exit_code, 1, result.output)
        self.assertIn("FAIL  settings", result.output)
        self.assertIn("SMTP_HOST is empty", result.output)
        self.assertIn("What to do:", result.output)

    def test_all_clear(self):
        self.fresh()
        result = self.app.test_cli_runner().invoke(args=["ready"])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("All clear.", result.output)


class TestHeartbeatsAndWatchdogs(ReadyCase):
    def test_the_timers_beat_every_round(self):
        cfg = dict(self.app.config)
        rounds = {"n": 0}

        def one_round_then_stop(_seconds):
            rounds["n"] += 1
            raise SystemExit   # ends the timer's thread after its first round

        with mock.patch.object(jobs, "run_alerts"), mock.patch.object(jobs, "run_daily"), \
                mock.patch.object(autopilot, "run"), mock.patch.object(jobs.time, "sleep", one_round_then_stop):
            for thread in jobs.start_scheduler(cfg):
                thread.join(10)
        conn = connect(self.db_path)
        beats = {r["name"]: r["beat_at"] for r in conn.execute("SELECT * FROM job_heartbeats")}
        conn.close()
        self.assertEqual(set(beats), {"alerts", "daily"})
        self.assertEqual(rounds["n"], 2)

    def test_a_beat_that_cant_be_written_never_stops_the_timer(self):
        cfg = dict(self.app.config, DATABASE=self.tmp.name)
        with self.assertLogs("omniarmor.health", "ERROR"):
            health.beat(cfg, "alerts")

    def test_autopilot_reports_a_stopped_minute_timer(self):
        self.fresh()
        conn = connect(self.db_path)
        self.assertNotIn("timer-alerts", [f.key for f in autopilot.find_problems(conn, dict(self.app.config))])
        beat_at(self.db_path, "alerts", utcnow() - timedelta(minutes=20))
        found = {f.key: f for f in autopilot.find_problems(conn, dict(self.app.config))}
        conn.close()
        self.assertIn("timer-alerts", found)
        self.assertIn("Restart the app", found["timer-alerts"].action)

    def test_the_minute_timer_emails_once_when_the_daily_timer_stops(self):
        cfg = dict(self.app.config, OPERATOR_EMAIL="ops@example.com", SMTP_HOST="smtp.example.com")
        self.fresh()
        with mock.patch.object(autopilot, "send_email", return_value=("sent", None)) as sent:
            self.assertFalse(autopilot.watch_daily_timer(cfg))
            beat_at(self.db_path, "daily", utcnow() - timedelta(minutes=45))
            for _ in range(5):   # every minute
                self.assertTrue(autopilot.watch_daily_timer(cfg))
            self.assertEqual(sent.call_count, 1)
            self.assertIn("every-10-minutes timer has stopped", sent.call_args[0][2])
            # A day later, one reminder.
            self.assertTrue(autopilot.watch_daily_timer(cfg, now=utcnow() + timedelta(hours=25)))
            self.assertEqual(sent.call_count, 2)
            self.assertTrue(sent.call_args[0][2].startswith("[Aegizyn] Still open:"))
            # Running again: Autopilot's own pass says it's fixed.
            self.fresh()
            autopilot.run(cfg, force=True)
        subjects = [c[0][2] for c in sent.call_args_list]
        self.assertIn("[Aegizyn] Fixed: The every-10-minutes timer has stopped", subjects)

    def test_no_heartbeat_yet_means_nothing_to_watch(self):
        cfg = dict(self.app.config, OPERATOR_EMAIL="ops@example.com", SMTP_HOST="smtp.example.com")
        with mock.patch.object(autopilot, "send_email") as sent:
            self.assertFalse(autopilot.watch_daily_timer(cfg))
        sent.assert_not_called()


class _Silent:
    """A server on this machine that takes connections and never answers."""

    def __init__(self, close_after_request=False):
        self.sock = socket.socket()
        self.sock.bind(("127.0.0.1", 0))
        self.sock.listen(8)
        self.port = self.sock.getsockname()[1]
        self.close_after_request = close_after_request
        self.held, self.accepted = [], 0
        threading.Thread(target=self.serve, daemon=True).start()

    def serve(self):
        while True:
            try:
                conn, _ = self.sock.accept()
            except OSError:
                return
            self.accepted += 1
            if self.close_after_request:
                conn.recv(65536)
                conn.close()   # the connection is cut before any answer
            else:
                self.held.append(conn)

    def close(self):
        self.sock.close()
        for conn in self.held:
            conn.close()


class TestTimeoutsAndRetries(unittest.TestCase):
    CFG = {"STRIPE_SECRET_KEY": "sk_test_x"}

    def test_stripe_cut_off_mid_answer_is_a_stripe_error_not_a_crash(self):
        server = _Silent(close_after_request=True)
        self.addCleanup(server.close)
        with mock.patch.object(academy_plan, "STRIPE_API", f"http://127.0.0.1:{server.port}/v1"), \
                mock.patch.object(academy_plan, "STRIPE_RETRY_PAUSE", 0):
            with self.assertRaises(academy_plan.StripeError):
                academy_plan._stripe(self.CFG, "checkout/sessions", {"a": "b"})
        self.assertEqual(server.accepted, 2)   # tried once more: the POST carries an Idempotency-Key

    def test_stripe_that_never_answers_gives_up_at_the_timeout_without_retrying(self):
        server = _Silent()
        self.addCleanup(server.close)
        with mock.patch.object(academy_plan, "STRIPE_API", f"http://127.0.0.1:{server.port}/v1"), \
                mock.patch.object(academy_plan, "STRIPE_TIMEOUT", 0.5):
            started = time.monotonic()
            with self.assertRaises(academy_plan.StripeError) as caught:
                academy_plan._stripe(self.CFG, "checkout/sessions/cs_1", {}, method="GET")
        self.assertLess(time.monotonic() - started, 3)
        self.assertIn("didn't answer", str(caught.exception))
        self.assertEqual(server.accepted, 1)

    def test_stripe_refusing_connections_is_tried_twice(self):
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            port = s.getsockname()[1]   # closed again: nothing listens there
        calls = []
        real = academy_plan.urllib.request.urlopen
        with mock.patch.object(academy_plan, "STRIPE_API", f"http://127.0.0.1:{port}/v1"), \
                mock.patch.object(academy_plan, "STRIPE_RETRY_PAUSE", 0), \
                mock.patch.object(academy_plan.urllib.request, "urlopen",
                                  side_effect=lambda *a, **k: calls.append(1) or real(*a, **k)):
            with self.assertRaises(academy_plan.StripeError):
                academy_plan._stripe(self.CFG, "checkout/sessions/cs_1", {}, method="GET")
        self.assertEqual(len(calls), 2)

    def test_every_stripe_call_has_a_timeout(self):
        with mock.patch.object(academy_plan.urllib.request, "urlopen") as opened:
            opened.return_value.__enter__.return_value.read.return_value = b"{}"
            academy_plan._stripe(self.CFG, "x", {})
        self.assertEqual(opened.call_args.kwargs["timeout"], academy_plan.STRIPE_TIMEOUT)

    def test_an_email_server_that_never_answers_fails_the_send_at_the_timeout(self):
        server = _Silent()
        self.addCleanup(server.close)
        cfg = {"SMTP_HOST": "127.0.0.1", "SMTP_PORT": server.port, "SMTP_STARTTLS": False, "MAIL_FROM": "a@b.test",
               "BASE_URL": "https://omniarmor.test"}
        with mock.patch.object(notify, "SMTP_TIMEOUT", 0.5):
            started = time.monotonic()
            status, error = notify.send_email(cfg, "x@example.com", "Hi", "Body")
        self.assertLess(time.monotonic() - started, 3)
        self.assertEqual(status, "failed")
        self.assertIn("timed out", error.lower())


class TestFailSoftPages(AppTestCase):
    def test_database_out_of_reach_gives_the_friendly_503(self):
        self.app.config["DATABASE"] = self.tmp.name   # a folder: "unable to open database file"
        with self.assertLogs(self.app.logger, "ERROR"):
            response = self.client.get("/help")
        page = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.headers["Retry-After"], "60")
        self.assertIn("That&#39;s unavailable for a moment", page)
        for leak in ("Traceback", "sqlite", "OperationalError", self.tmp.name):
            self.assertNotIn(leak, page)

    def test_a_wrong_query_is_still_a_bug_page(self):
        import sqlite3
        with mock.patch("omniarmor_app._help_facts", side_effect=sqlite3.OperationalError("no such column: nope")), \
                self.assertLogs(self.app.logger, "ERROR") as logged:
            response = self.client.get("/help")
        self.assertIn("Traceback", logged.output[0])
        self.assertEqual(response.status_code, 500)
        self.assertIn("Something went wrong on our side", response.get_data(as_text=True))


class TestStartUpChecks(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        clean = {k: v for k, v in os.environ.items()
                 if not k.startswith(("OMNIARMOR_", "SMTP_", "STRIPE_", "MAIL_", "BASE_URL", "SECRET_KEY"))}
        patcher = mock.patch.dict(os.environ, clean, clear=True)
        patcher.start()
        self.addCleanup(patcher.stop)

    def production(self, **env):
        os.environ.update({"OMNIARMOR_ENV": "production", "SECRET_KEY": "s" * 64,
                           "BASE_URL": "https://omniarmor.test", **env})
        return load_config()

    def test_production_needs_base_url(self):
        os.environ.update(OMNIARMOR_ENV="production", SECRET_KEY="s" * 64)
        with self.assertRaises(SettingsError) as caught:
            load_config()
        self.assertIn("BASE_URL is not set", str(caught.exception))

    def test_all_problems_are_listed_at_once(self):
        os.environ.update(OMNIARMOR_ENV="production", STRIPE_SECRET_KEY="sk_live_x", SMTP_HOST="smtp.example.com")
        with self.assertRaises(SettingsError) as caught:
            load_config()
        text = str(caught.exception)
        for name in ("SECRET_KEY", "BASE_URL", "MAIL_FROM", "STRIPE_WEBHOOK_SECRET"):
            self.assertIn(name, text)
        self.assertNotIn("sk_live_x", text)

    def test_half_set_email_is_refused(self):
        with self.assertRaises(SettingsError) as caught:
            self.production(SMTP_HOST="smtp.example.com", MAIL_FROM="Aegizyn <no-reply@omniarmor.test>",
                            SMTP_USER="apikey")
        self.assertIn("SMTP_PASSWORD is empty", str(caught.exception))

    def test_a_complete_production_setup_starts(self):
        cfg = self.production(SMTP_HOST="smtp.example.com", MAIL_FROM="Aegizyn <no-reply@omniarmor.test>",
                              STRIPE_SECRET_KEY="sk_test_x", STRIPE_WEBHOOK_SECRET="whsec_x")
        self.assertEqual(cfg["ENV_NAME"], "production")

    def test_production_without_email_still_starts(self):
        self.assertEqual(self.production()["SMTP_HOST"], "")

    def test_a_bad_number_is_said_plainly(self):
        os.environ["SMTP_PORT"] = "five-eight-seven"
        with self.assertRaises(SettingsError) as caught:
            load_config()
        self.assertIn("SMTP_PORT must be a whole number", str(caught.exception))

    def test_a_database_that_cant_be_opened_is_said_plainly(self):
        with self.assertRaises(SettingsError) as caught:
            create_app(DATABASE=self.tmp.name, SCHEDULER_ENABLED=False)
        self.assertIn("can't open its database", str(caught.exception))
        self.assertIn("DATABASE_PATH", str(caught.exception))


class TestCompression(AppTestCase):
    GZ = {"Accept-Encoding": "gzip, deflate, br"}

    def test_pages_are_gzipped_when_the_browser_takes_it(self):
        plain = self.client.get("/")
        packed = self.client.get("/", headers=self.GZ)
        self.assertEqual(packed.headers["Content-Encoding"], "gzip")
        self.assertIn("Accept-Encoding", packed.headers["Vary"])
        self.assertLess(len(packed.data) * 2.5, len(plain.data))
        self.assertEqual(gzip.decompress(packed.data), plain.data)
        self.assertEqual(int(packed.headers["Content-Length"]), len(packed.data))

    def test_not_without_asking_nor_when_refused(self):
        self.assertNotIn("Content-Encoding", self.client.get("/").headers)
        self.assertNotIn("Content-Encoding", self.client.get("/", headers={"Accept-Encoding": "gzip;q=0"}).headers)
        self.assertIn("Accept-Encoding", self.client.get("/").headers["Vary"])

    def test_small_answers_and_redirects_are_left_alone(self):
        self.assertNotIn("Content-Encoding", self.client.get("/healthz", headers=self.GZ).headers)
        self.assertNotIn("Content-Encoding", self.client.get("/app", headers=self.GZ).headers)

    def test_static_files_are_gzipped_and_still_revalidate(self):
        page = self.client.get("/login").get_data(as_text=True)
        url = re.search(r'href="(/static/app\.css\?v=\d+)"', page).group(1)
        packed = self.client.get(url, headers=self.GZ)
        with open(os.path.join(self.app.static_folder, "app.css"), "rb") as f:
            self.assertEqual(gzip.decompress(packed.data), f.read())
        self.assertEqual(packed.headers["Content-Encoding"], "gzip")
        self.assertIn("max-age=31536000", packed.headers["Cache-Control"])
        etag = packed.headers["ETag"]
        self.assertTrue(etag.startswith('W/"'))
        again = self.client.get(url, headers=dict(self.GZ, **{"If-None-Match": etag}))
        self.assertEqual(again.status_code, 304)
        again.close()
        packed.close()

    def test_streamed_exports_are_not_held_back(self):
        self.signup()
        response = self.client.get("/app/audit.csv", headers=self.GZ)
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("Content-Encoding", response.headers)
        response.close()

    def test_static_copies_are_made_once_per_file_version(self):
        path = os.path.join(self.app.static_folder, "app.css")
        with mock.patch.object(compress.gzip, "compress", wraps=gzip.compress) as packed:
            compress._static.pop(path, None)
            for _ in range(3):
                self.client.get("/static/app.css", headers=self.GZ).close()
        self.assertEqual(packed.call_count, 1)


class TestMaskedFormToken(AppTestCase):
    def tokens(self, html):
        return re.findall(r'name="csrf_token" value="([^"]+)"', html)

    def test_the_token_differs_on_every_page_and_each_works(self):
        first = self.tokens(self.client.get("/signup").get_data(as_text=True))[0]
        second = self.tokens(self.client.get("/signup").get_data(as_text=True))[0]
        self.assertNotEqual(first, second)
        with self.client.session_transaction() as s:
            raw = s["_csrf"]
        self.assertNotIn(raw, first + second)
        for token in (first, second, raw):
            response = self.client.post("/login", data={"csrf_token": token, "email": "x@example.com",
                                                        "password": "wrong password!"})
            self.assertNotEqual(response.status_code, 400, token)

    def test_a_changed_token_is_refused(self):
        token = self.tokens(self.client.get("/signup").get_data(as_text=True))[0]
        broken = ("A" if token[0] != "A" else "B") + token[1:]
        for bad in (broken, "", "not-a-token", token[:-4], "\u20ac" * 10, "\u00e9" + token):
            response = self.client.post("/login", data={"csrf_token": bad, "email": "x@example.com",
                                                        "password": "wrong password!"})
            self.assertEqual(response.status_code, 400, bad)


class TestIndexes(unittest.TestCase):
    def test_the_queries_that_read_whole_tables_use_an_index_now(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        conn = connect(os.path.join(tmp.name, "t.db"))
        migrate(conn)
        plans = {
            "notifications_user": "SELECT * FROM notifications WHERE org_id = 1 OR (org_id IS NULL AND user_id = 2)"
                                  " ORDER BY created_at DESC, id DESC LIMIT 100",
            "memberships_org": "SELECT user_id FROM memberships WHERE org_id = 1 AND role = 'owner'",
            "notifications_status": "SELECT COUNT(*) FROM notifications WHERE status = 'failed' AND attempts > 3"
                                    " AND created_at >= '2026-01-01'",
        }
        for index, sql in plans.items():
            plan = " ".join(r[3] for r in conn.execute("EXPLAIN QUERY PLAN " + sql))
            self.assertIn(index, plan, sql)
        conn.close()


if __name__ == "__main__":
    unittest.main()
