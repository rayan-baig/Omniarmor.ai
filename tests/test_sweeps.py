"""The scheduled sweeps under load: the time-limit alerts, the daily job and
Autopilot never run twice at once, however long one takes, and a long daily
run never holds the minute alerts up. tools/load_test.py measures them at
scale (docs/LOAD-TEST.md); these tests pin the fixes it led to."""

import os
import sys
import tempfile
import threading
import time
import unittest
from datetime import timedelta
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from omniarmor_app import autopilot, jobs, reminders  # noqa: E402
from omniarmor_app.db import MIGRATIONS, SCHEMA_VERSION, connect, iso, migrate, utcnow  # noqa: E402
from test_webapp import AppTestCase  # noqa: E402


class TestMigrationFourteen(unittest.TestCase):
    def test_upgrading_a_populated_version_13_database(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = os.path.join(tmp.name, "v13.db")
        with mock.patch("omniarmor_app.db.MIGRATIONS", [m for m in MIGRATIONS if m[0] <= 13]):
            conn = connect(path)
            self.assertEqual(migrate(conn), 13)
        now = iso(utcnow())
        conn.execute("INSERT INTO orgs (id, name, created_at) VALUES (1, 'Acme', ?)", (now,))
        conn.execute("INSERT INTO job_runs (job, run_date, started_at) VALUES ('daily', '2026-11-03', ?)", (now,))
        conn.commit()
        self.assertEqual(migrate(conn), SCHEMA_VERSION)
        self.assertEqual([r[1] for r in conn.execute("PRAGMA table_info(job_locks)")],
                         ["name", "holder", "taken_at", "expires_at"])
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM job_runs").fetchone()[0], 1)
        self.assertEqual(conn.execute("SELECT name FROM orgs").fetchone()[0], "Acme")
        conn.close()


class SweepCase(AppTestCase):
    def setUp(self):
        super().setUp()
        self.cfg = dict(self.app.config, DAILY_JOB_HOUR_UTC=0)


class TestTheLock(SweepCase):
    def test_one_holder_at_a_time_and_free_again_after(self):
        with jobs.job_lock(self.cfg, "daily") as first:
            self.assertTrue(first)
            with jobs.job_lock(self.cfg, "daily") as second:
                self.assertFalse(second)
            with jobs.job_lock(self.cfg, "alerts") as other:
                self.assertTrue(other)   # each sweep has its own
        with jobs.job_lock(self.cfg, "daily") as again:
            self.assertTrue(again)
        with self.db() as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM job_locks").fetchone()[0], 0)

    def test_a_long_sweep_keeps_its_lock_and_a_dead_one_loses_it(self):
        with mock.patch.object(jobs, "LOCK_LEASE", timedelta(seconds=1)), \
                mock.patch.object(jobs, "LOCK_RENEW_SECONDS", 0.2):
            with jobs.job_lock(self.cfg, "daily") as mine:
                self.assertTrue(mine)
                time.sleep(2.5)   # well past the lease: renewed while it runs
                with jobs.job_lock(self.cfg, "daily") as other:
                    self.assertFalse(other)
            # A process that died holding it: its lease runs out.
            with self.db() as conn:
                conn.execute("INSERT INTO job_locks (name, holder, taken_at, expires_at) VALUES (?, ?, ?, ?)",
                             ("daily", "gone", iso(utcnow()), iso(utcnow() + timedelta(seconds=1))))
                conn.commit()
            with jobs.job_lock(self.cfg, "daily") as other:
                self.assertFalse(other)
            time.sleep(2.1)
            with jobs.job_lock(self.cfg, "daily") as other:
                self.assertTrue(other)


class TestSweepsNeverOverlap(SweepCase):
    def blocking(self, real):
        """Wraps a sender so its first call waits until released, like an
        email provider that takes its time."""
        inside, release = threading.Event(), threading.Event()
        calls = []

        def send(*args, **kwargs):
            calls.append(args)
            if len(calls) == 1:
                inside.set()
                release.wait(10)
            return real(*args, **kwargs)
        return send, inside, release, calls

    def test_a_daily_run_longer_than_an_hour_is_not_started_again_beside_it(self):
        """The day's claim went stale after an hour: with thousands of digests
        through a slow provider, a second server process claimed the day
        again while the first was still sending, and people got two digests."""
        self.signup(industries=(1,))
        self.change(1, "annual_mvr_review", date="2020-01-02")
        send, inside, release, calls = self.blocking(reminders.notify)
        with mock.patch.object(reminders, "notify", side_effect=send), \
                mock.patch.object(jobs, "STALE_AFTER", timedelta(seconds=-60)):   # every claim looks stale
            first = threading.Thread(target=jobs.run_daily, args=(self.cfg,))
            first.start()
            self.assertTrue(inside.wait(10))
            self.assertIsNone(jobs.run_daily(self.cfg))                 # the other process's timer
            self.assertEqual(jobs.run_daily(self.cfg, force=True), jobs.BUSY)   # run-daily --force by hand
            release.set()
            first.join(10)
        self.assertEqual(len(calls), 1)
        with self.db() as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM notifications WHERE kind = 'reminder'")
                             .fetchone()[0], 1)
            self.assertIsNotNone(conn.execute("SELECT finished_at FROM job_runs WHERE job = 'daily'").fetchone()[0])

    def test_an_autopilot_pass_that_runs_long_does_not_resend_the_same_email(self):
        """A pass re-sending failed emails to a provider that times out could
        run past its 10-minute slot; the next pass then re-sent the same
        failed emails beside it."""
        cfg = dict(self.cfg, SMTP_HOST="smtp.test")
        with self.db() as conn:
            conn.execute("INSERT INTO notifications (created_at, kind, recipient, subject, body, status, error)"
                         " VALUES (?, 'reminder', 'pat@example.com', 'Due soon', 'body', 'failed', 'timed out')",
                         (iso(utcnow() - timedelta(minutes=20)),))
            conn.commit()
        send, inside, release, calls = self.blocking(lambda *a, **k: ("sent", None))
        with mock.patch.object(autopilot, "send_email", side_effect=send), \
                mock.patch.object(autopilot.bugfinder, "self_test"):
            first = threading.Thread(target=autopilot.run, args=(cfg,))
            first.start()
            self.assertTrue(inside.wait(10))
            self.assertIsNone(autopilot.run(cfg, force=True))
            release.set()
            first.join(30)
        self.assertEqual([c[1] for c in calls if c[1] == "pat@example.com"], ["pat@example.com"])
        with self.db() as conn:
            self.assertEqual(conn.execute("SELECT status, attempts FROM notifications").fetchone()[:], ("sent", 2))

    def test_two_alert_sweeps_at_once_one_skips(self):
        with jobs.job_lock(self.cfg, "alerts"):
            self.assertTrue(jobs.run_alerts(self.cfg).get("busy"))
        self.assertNotIn("busy", jobs.run_alerts(self.cfg))


class TestTheTimer(SweepCase):
    def test_the_alerts_have_their_own_thread(self):
        """One thread used to run the alerts, the daily job and Autopilot in
        turn, so a daily run sending thousands of digests through a slow
        provider held the minute alerts (a 15-minute clock among them) up
        until it finished. The alerts now run every minute in a thread of
        their own; the daily job and Autopilot every 10 minutes in another."""
        started = []

        class Stop(Exception):
            pass

        class FakeThread:
            def __init__(self, target, name=None, **_):
                self.target, self.name = target, name

            def start(self):
                started.append(self)

        def sleeper(every, times):
            count = {"n": 0}

            def sleep(seconds):
                self.assertEqual(seconds, every)
                count["n"] += 1
                if count["n"] == times:
                    raise Stop
            return sleep

        with mock.patch.object(jobs, "run_alerts") as alerts, mock.patch.object(jobs, "run_daily") as daily, \
                mock.patch("omniarmor_app.autopilot.run") as pilot, \
                mock.patch.object(jobs.threading, "Thread", FakeThread):
            jobs.start_scheduler(self.cfg)
            self.assertEqual([t.name for t in started], ["omniarmor-alerts", "omniarmor-daily"])
            with mock.patch.object(jobs.time, "sleep", side_effect=sleeper(60, 25)), self.assertRaises(Stop):
                started[0].target()
            self.assertEqual((alerts.call_count, daily.call_count), (25, 0))
            with mock.patch.object(jobs.time, "sleep", side_effect=sleeper(600, 3)), self.assertRaises(Stop):
                started[1].target()
            self.assertEqual((alerts.call_count, daily.call_count, pilot.call_count), (25, 3, 3))


if __name__ == "__main__":
    unittest.main()
