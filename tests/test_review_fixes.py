"""Fixes from a security review, each kept as a test so it stays fixed."""

import glob
import os

from omniarmor_app.tracking import MAX_DAYS, _shifted, _whole_days


def test_a_huge_day_limit_cannot_reach_past_the_calendar():
    import datetime
    # Clamped, and even an edge date plus the clamp is answered, not raised.
    assert _whole_days(3_000_000) == MAX_DAYS
    assert _shifted(datetime.date(9999, 12, 1), MAX_DAYS) is None
    assert _shifted(datetime.date(2026, 1, 1), 30) == datetime.date(2026, 1, 31)


def test_a_failing_daily_job_does_not_churn_away_older_backups(tmp_path):
    """Each retry took another backup and pruned by count, so a job that kept
    failing pushed every earlier day's copy out."""
    import sqlite3
    from omniarmor_app.jobs import backup_database

    db = tmp_path / "live.db"
    sqlite3.connect(db).close()
    backups = tmp_path / "backups"
    backups.mkdir()
    for day in ("20260101", "20260102", "20260103"):
        (backups / f"omniarmor-{day}-000000-000000.db").write_bytes(b"old")
    cfg = {"DATABASE": str(db), "BACKUP_DIR": str(backups), "BACKUP_KEEP": 4}
    first = backup_database(cfg)
    for _ in range(5):
        assert backup_database(cfg) == first
    names = sorted(os.path.basename(p) for p in glob.glob(str(backups / "*.db")))
    assert len(names) == 4 and names[0].startswith("omniarmor-20260101")


def test_a_deleted_workspaces_subscription_does_not_land_on_a_stranger():
    """Workspace ids are reused, and a renewal for a deleted workspace used to
    make the stranger who got its id paid, with the original card behind it."""
    import sqlite3
    from omniarmor_app.academy_plan import _org_for

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE orgs (id INTEGER PRIMARY KEY, stripe_customer_id TEXT, created_at TEXT)")
    # The stranger's workspace, made today with the deleted one's id.
    conn.execute("INSERT INTO orgs (id, stripe_customer_id, created_at) "
                 "VALUES (2, NULL, '2026-10-31T10:00:00+00:00')")
    # A subscription from last year, renewing.
    renewal = {"id": "sub_B", "customer": "cus_B", "created": 1735689600, "metadata": {"org_id": "2"}}
    assert _org_for(conn, renewal, "customer.subscription.updated") is None
    # Its own checkout still finds it.
    checkout = {"client_reference_id": "2", "customer": "cus_new"}
    assert _org_for(conn, checkout, "checkout.session.completed")["id"] == 2
    # And a workspace with a customer only answers to that customer.
    conn.execute("UPDATE orgs SET stripe_customer_id = 'cus_new' WHERE id = 2")
    assert _org_for(conn, {"customer": "cus_other", "metadata": {"org_id": "2"}},
                    "customer.subscription.updated") is None
    assert _org_for(conn, {"customer": "cus_new", "metadata": {"org_id": "2"}},
                    "customer.subscription.updated")["id"] == 2


# ---- through the app --------------------------------------------------------

import sys  # noqa: E402
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_webapp import PASSWORD, AppTestCase  # noqa: E402


class TestThroughTheApp(AppTestCase):
    def test_signing_out_ends_the_session_not_just_this_browsers_copy(self):
        self.signup()
        with self.client.session_transaction() as s:
            copied = dict(s)
        self.assertEqual(self.client.get("/app").status_code, 200)
        self.post("/logout")
        thief = self.app.test_client()
        with thief.session_transaction() as s:
            s.update(copied)
        self.assertNotEqual(thief.get("/app").status_code, 200)

    def test_a_paid_workspace_is_not_deleted_out_from_under_its_plan(self):
        self.signup()
        with self.db() as conn:
            conn.execute("UPDATE orgs SET academy_status = 'active', stripe_subscription_id = 'sub_1',"
                         " stripe_customer_id = 'cus_1'")
            conn.commit()
            name = conn.execute("SELECT name FROM orgs").fetchone()[0]
        self.post("/app/settings/delete", {"confirm": name})
        with self.db() as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM orgs").fetchone()[0], 1)
        # The message names the page where the plan is really cancelled.
        self.assertIn("Academy plan page, Manage or cancel", self.client.get("/app/settings").data.decode())

    def test_a_day_limit_past_a_hundred_years_is_refused(self):
        self.signup(industries=(7,))
        self.change(7, "fire_extinguisher_service", action="save", date="2026-01-01")
        self.change(7, "fire_extinguisher_service", action="override", limit="3000000")
        for path in ("/app", "/app/industry/7", "/app/report"):
            self.assertEqual(self.client.get(path).status_code, 200, path)


class TestLimits(AppTestCase):
    def test_a_stranger_cannot_lock_somebody_out_of_signing_in(self):
        self.signup()
        self.post("/logout")
        attacker = self.app.test_client()
        for _ in range(6):
            self.post("/login", {"email": "owner@example.com", "password": "wrong-password-1"},
                      client=attacker, environ_base={"REMOTE_ADDR": "203.0.113.9"})
        ok = self.post("/login", {"email": "owner@example.com", "password": PASSWORD},
                       environ_base={"REMOTE_ADDR": "198.51.100.4"})
        self.assertEqual(ok.status_code, 302)

    def test_sign_ups_from_one_place_are_limited(self):
        codes = []
        for n in range(12):
            client = self.app.test_client()
            codes.append(self.signup(email=f"farm{n}@example.com", client=client).status_code)
        self.assertEqual(codes[:10], [302] * 10)
        self.assertEqual(codes[10:], [400, 400])
