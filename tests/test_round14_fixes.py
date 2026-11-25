"""1.26.0: what a strict fourteenth review asked for.

A food batch's "made or opened N days ago" counted the make day twice (the 7-day rule counts it as day 1): it now
says the days since and the day it is on, everywhere it shows. "Is my data safe?" starts with "Yes." The sign-up's
time zone (from the device) is named in the welcome and explained in Settings. Settings has Change password. The
full report and its CSV say each reading in the summary's words. Copy: "the 7-day limit", the plan page says the
plan once, the summary says a reading once, and Pilot answers "free plan?" and "yearly discount?" (tests/js)."""

import csv
import html
import io
import os
import re
import sys
import unittest
from datetime import timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_webapp import PASSWORD, AppTestCase  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESTO, PHARMACY, HR = 2, 28, 30


def read(*parts):
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as f:
        return f.read()


def words(page):
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", page)).split())


def between(page, start, end):
    begin = page.index(start)
    return page[begin:page.index(end, begin)]


class TodayCase(AppTestCase):
    def today(self):
        from omniarmor_app.tracking import org_today
        with self.db() as conn:
            return org_today(conn.execute("SELECT * FROM orgs").fetchone())

    def csv_rows(self):
        return list(csv.reader(io.StringIO(self.client.get("/app/report.csv").data.decode("utf-8-sig"))))


# --- 1. A food batch's days ------------------------------------------------------------------------------------

class TestBatchMadeEightDaysAgo(TodayCase):
    """The reviewer's batch: made exactly 8 days ago, so on day 9 of the 7-day rule (it said "made or opened 9 days
    ago")."""

    def setUp(self):
        super().setUp()
        self.signup(industries=(RESTO,))
        self.made = self.today() - timedelta(days=8)
        self.post(f"/app/industry/{RESTO}/rule/date_marking/entries",
                  {"action": "add", "label": "Pico de gallo", "date": self.made.isoformat()})

    def test_summary_says_8_days_ago_and_day_9(self):
        summary = words(self.client.get("/app/report/summary").data.decode())
        self.assertIn("made or opened 8 days ago (day 9)", summary)
        self.assertNotIn("9 days ago", summary)
        self.assertIn("Made or opened 8 days ago (day 9) · recorded", summary)

    def test_home_and_the_check_say_day_9_and_the_date(self):
        said = f"Day 9 (made or opened {self.made.isoformat()}) is over the 7-day limit."
        self.assertIn(said, words(self.client.get("/app").data.decode()))
        self.assertIn(said, words(self.client.get(f"/app/industry/{RESTO}").data.decode()))
        self.assertNotIn("9 days is over", words(self.client.get("/app").data.decode()))

    def test_report_and_csv(self):
        report = words(self.client.get("/app/report").data.decode())
        self.assertIn("Made or opened 8 days ago (day 9)", report)
        rows = [r for r in self.csv_rows() if r[1].startswith("Ready-to-eat food 7-day limit")]
        self.assertTrue(rows)
        for row in rows:
            self.assertEqual(row[3], "Made or opened 8 days ago (day 9)", row)

    def test_made_today_is_day_1_and_its_last_day_is_day_7(self):
        from omniarmor_app.catalog import find_rule
        from omniarmor_app.tracking import compute_state
        today = self.today()
        rule = find_rule(RESTO, "date_marking")
        row = lambda n: {"value_bool": None, "value_num": None, "value_date": (today - timedelta(days=n)).isoformat(),  # noqa: E731
                         "updated_at": None, "updated_by_name": None, "limit_override": None, "warn_override": None}
        fresh = compute_state(RESTO, rule, row(0), today)
        self.assertEqual(fresh.reading_line, "made or opened today (day 1)")
        self.assertEqual(fresh.limits_text, "7-day limit · warns from day 6")
        last = compute_state(RESTO, rule, row(6), today)
        self.assertEqual(last.reading_line, "made or opened 6 days ago (day 7)")
        self.assertIn("is the last day of the 7-day limit", last.message)
        warn = compute_state(RESTO, rule, row(5), today)
        self.assertIn("(it warns from day 6)", warn.message)
        self.assertEqual(compute_state(RESTO, rule, row(1), today).reading_line, "made or opened 1 day ago (day 2)")


# --- 2, 6. Pilot's words (the answers themselves are tested in tests/js/omniarmor-pilot.test.js) -----------------

class TestPilotWords(unittest.TestCase):
    def test_safety_lead_free_plan_and_yearly_answers_are_there(self):
        config = read("omniarmor_app", "static", "pilot-omniarmor.js")
        for said in ('"Yes. We don\'t sell your data', '"No, we don\'t sell your data.', '"No tracking cookies',
                     'label: "Is there a free plan?"', 'label: "Is there a yearly discount?"', "/app/settings#password",
                     "**Change password**"):
            self.assertIn(said, config)
        self.assertNotIn("We keep it safe, and no", config)

    def test_knowledge_and_help_say_where_to_change_a_password(self):
        self.assertIn("your password (the current one and a new one", read("omniarmor_app", "static", "pilot-omniarmor-pack.js"))
        self.assertIn("Change it in Settings, under Your password.", read("omniarmor_app", "templates", "help.html"))


# --- 3. The time zone ------------------------------------------------------------------------------------------

class TestTimeZone(AppTestCase):
    def signup_in(self, zone, client=None):
        client = client or self.client
        data = {"name": "Sam Rivera", "email": f"{zone.replace('/', '-').lower()}@example.com", "password": PASSWORD,
                "org_name": "Sams Taqueria", "timezone": zone, "industries": [str(RESTO)]}
        return self.post("/signup", data, client=client, follow_redirects=True)

    def test_the_welcome_names_the_device_s_time_zone(self):
        page = words(self.signup_in("America/Chicago").data.decode())
        self.assertIn("Due dates roll over at midnight Chicago time (America/Chicago). Not where you are? Change it in"
                      " Settings.", page)
        with self.db() as conn:
            self.assertEqual(conn.execute("SELECT timezone FROM orgs").fetchone()[0], "America/Chicago")

    def test_utc_is_said_plainly(self):
        page = words(self.signup_in("UTC").data.decode())
        self.assertIn("Due dates roll over at midnight UTC. Not where you are?", page)

    def test_a_teacher_s_welcome_names_it_too(self):
        data = {"name": "Ms Park", "email": "park@school.example", "password": PASSWORD, "org_name": "Lincoln School",
                "timezone": "America/Denver", "then": "classes"}
        page = words(self.post("/signup?then=classes", data, follow_redirects=True).data.decode())
        self.assertIn("Due dates roll over at midnight Denver time (America/Denver).", page)

    def test_settings_explains_it_and_history_says_when_it_changes(self):
        self.signup_in("UTC")
        page = self.client.get("/app/settings").data.decode()
        self.assertIn("<span>Time zone</span>", page)
        self.assertIn('<option value="UTC" selected>', page)
        self.assertIn("data-tz-hint", page)
        self.post("/app/settings/company", {"name": "Sams Taqueria", "timezone": "America/Chicago", "industries": [str(RESTO)]})
        with self.db() as conn:
            self.assertEqual(conn.execute("SELECT timezone FROM orgs").fetchone()[0], "America/Chicago")
            summary = conn.execute("SELECT summary FROM audit ORDER BY id DESC").fetchone()[0]
        self.assertIn("time zone UTC to America/Chicago", summary)

    def test_an_existing_utc_workspace_is_left_alone(self):
        self.signup_in("UTC")
        self.post("/app/settings/company", {"name": "Renamed", "timezone": "UTC", "industries": [str(RESTO)]})
        with self.db() as conn:
            self.assertEqual(conn.execute("SELECT timezone FROM orgs").fetchone()[0], "UTC")
            self.assertNotIn("time zone", conn.execute("SELECT summary FROM audit ORDER BY id DESC").fetchone()[0])

    def test_the_sign_up_box_says_settings_can_change_it(self):
        page = self.client.get("/signup").data.decode()
        self.assertIn("<span>Time zone</span>", page)
        self.assertIn("you can change it later in Settings", page)


# --- 4. Change password ----------------------------------------------------------------------------------------

class TestChangePassword(AppTestCase):
    NEW = "a brand new password"

    def setUp(self):
        super().setUp()
        self.signup()
        self.other = self.app.test_client()
        self.post("/login", {"email": "owner@example.com", "password": PASSWORD}, client=self.other)

    def change_pw(self, current, new, client=None):
        return self.post("/app/settings/password", {"current_password": current, "new_password": new}, client=client,
                         follow_redirects=True)

    def hash(self):
        with self.db() as conn:
            return conn.execute("SELECT password_hash FROM users").fetchone()[0]

    def test_settings_has_the_form(self):
        page = self.client.get("/app/settings").data.decode()
        form = between(page, "data-change-password", "</form>")
        self.assertIn('id="password"', page)
        self.assertIn('name="current_password" autocomplete="current-password"', form)
        self.assertIn('name="new_password" autocomplete="new-password" required minlength="10"', form)
        self.assertIn("Change password", form)

    def test_a_teammate_has_it_too(self):
        self.post("/app/settings/invite")
        token = re.search(r"/signup\?invite=([\w-]+)", self.client.get("/app/settings").data.decode()).group(1)
        mate = self.app.test_client()
        self.signup(email="mate@example.com", invite=token, client=mate)
        self.assertIn("data-change-password", mate.get("/app/settings").data.decode())

    def test_it_changes_the_password_and_signs_out_every_other_device(self):
        before = self.hash()
        page = words(self.change_pw(PASSWORD, self.NEW).data.decode())
        self.assertIn("Your password is changed. Every other device was signed out.", page)
        self.assertNotEqual(self.hash(), before)
        self.assertEqual(self.client.get("/app/settings").status_code, 200, "this device stays signed in")
        self.assertEqual(self.other.get("/app").status_code, 302, "the other device is signed out")
        anon = self.app.test_client()
        self.assertEqual(self.post("/login", {"email": "owner@example.com", "password": PASSWORD}, client=anon).status_code, 401)
        self.assertEqual(self.post("/login", {"email": "owner@example.com", "password": self.NEW}, client=anon).status_code, 302)

    def test_it_is_in_history_and_emailed(self):
        self.change_pw(PASSWORD, self.NEW)
        with self.db() as conn:
            audit = [r[0] for r in conn.execute("SELECT summary FROM audit WHERE action = 'team'")]
            mail = conn.execute("SELECT recipient, subject, body FROM notifications WHERE kind = 'password_changed'").fetchall()
        self.assertIn("Pat Owner changed their password", audit)
        self.assertEqual(len(mail), 1)
        self.assertEqual(mail[0]["recipient"], "owner@example.com")
        self.assertIn("If it wasn't, reset your password now: https://omniarmor.test/forgot", mail[0]["body"])
        self.assertNotIn(self.NEW, mail[0]["body"])
        self.assertIn("changed their password", words(self.client.get("/app/audit").data.decode()))

    def test_an_open_reset_link_stops_working(self):
        self.post("/forgot", {"email": "owner@example.com"}, client=self.app.test_client())
        with self.db() as conn:
            token = re.search(r"/reset/(\S+)", conn.execute("SELECT body FROM notifications WHERE kind = 'password_reset'")
                              .fetchone()[0]).group(1)
        self.change_pw(PASSWORD, self.NEW)
        anon = self.app.test_client()
        self.assertIn("/forgot", anon.get(f"/reset/{token}").headers["Location"])

    def test_wrong_current_password_changes_nothing(self):
        before = self.hash()
        page = words(self.change_pw("not my password", self.NEW).data.decode())
        self.assertIn("That isn't your current password. Nothing was changed.", page)
        self.assertEqual(self.hash(), before)
        self.assertEqual(self.other.get("/app").status_code, 200)

    def test_same_strength_rule_as_reset(self):
        before = self.hash()
        self.assertIn("Use at least 10 characters for your password.", words(self.change_pw(PASSWORD, "short").data.decode()))
        self.assertIn("That password is too long.", words(self.change_pw(PASSWORD, "x" * 201).data.decode()))
        self.assertIn("That's the password you have now.", words(self.change_pw(PASSWORD, PASSWORD).data.decode()))
        self.assertEqual(self.hash(), before)

    def test_three_tries_an_hour_like_reset(self):
        for _ in range(3):
            self.change_pw("wrong guess here", self.NEW)
        before = self.hash()
        page = words(self.change_pw(PASSWORD, self.NEW).data.decode())
        self.assertIn("Too many tries in the last hour.", page)
        self.assertEqual(self.hash(), before)

    def test_signed_out_and_without_a_form_token_it_does_nothing(self):
        anon = self.app.test_client()
        got = self.post("/app/settings/password", {"current_password": PASSWORD, "new_password": self.NEW}, client=anon)
        self.assertEqual(got.status_code, 302)
        self.assertIn("/login", got.headers["Location"])
        before = self.hash()
        self.assertEqual(self.client.post("/app/settings/password", data={"current_password": PASSWORD,
                                                                          "new_password": self.NEW}).status_code, 400)
        self.assertEqual(self.hash(), before)


# --- 5. The report's and the CSV's Reading ---------------------------------------------------------------------

class TestReportReadingWords(TodayCase):
    def setUp(self):
        super().setUp()
        self.signup(industries=(RESTO, PHARMACY, HR))
        today = self.today()
        self.change(PHARMACY, "exclusion_screening", date=(today - timedelta(days=35)).isoformat())
        self.change(PHARMACY, "license_current", date=(today + timedelta(days=41)).isoformat())
        self.change(HR, "cobra_election_notice", date=(today - timedelta(days=47)).isoformat())
        self.change(HR, "hours_records", answer="yes")
        self.post(f"/app/industry/{RESTO}/rule/cold_holding/entries", {"action": "add", "label": "Prep line cooler", "value": "44"})

    def test_report(self):
        page = self.client.get("/app/report").data.decode()
        cells = [words(c) for c in re.findall(r'<td class="num reading" data-label="Reading">(.*?)</td>', page)]
        for said in ("Last done 35 days ago", "41 days left", "Qualifying event 47 days ago", "Yes", "44°F"):
            self.assertIn(said, cells)
        self.assertNotIn("35 days", cells)
        self.assertNotIn("41 days", cells)

    def test_csv(self):
        readings = {r[1]: r[3] for r in self.csv_rows()[1:]}
        self.assertIn("Last done 35 days ago", readings.values())
        self.assertIn("41 days left", readings.values())
        self.assertIn("Qualifying event 47 days ago", readings.values())
        self.assertNotIn("35 days", readings.values())

    def test_summary_says_a_reading_once(self):
        summary = words(self.client.get("/app/report/summary").data.decode())
        action = between(summary, "Needs action", "Due in the next")
        self.assertIn("44°F is over the 41°F limit", action)
        self.assertNotIn("last reading 44°F", action)
        self.assertEqual(action.count("44°F"), 1)

    def test_a_deadline_says_due_by_its_date(self):
        page = words(self.client.get(f"/app/industry/{PHARMACY}").data.decode())
        self.assertNotIn("Minimum 0 days", page)
        self.assertRegex(page, r"Due by its date · warns from \d+ days left")


# --- 6. Copy ---------------------------------------------------------------------------------------------------

class TestCopy(TodayCase):
    def test_n_day_limits_have_a_hyphen(self):
        from omni_armor_rules import evaluate
        from omniarmor_app.catalog import find_rule
        self.assertIn("is over the 7-day limit", evaluate(find_rule(RESTO, "date_marking"), 9)[2])
        self.assertIn("close to the 3-business-day limit", evaluate(find_rule(HR, "i9_section_2"), 2)[2])
        self.assertIn("the 2-hour limit", evaluate(find_rule(RESTO, "cooling_first_stage"), 3)[2])
        self.assertIn("the 41°F limit", evaluate(find_rule(RESTO, "cold_holding"), 44)[2])
        self.signup(industries=(RESTO, HR))
        self.change(HR, "i9_section_2", date=(self.today() - timedelta(days=10)).isoformat())
        home = words(self.client.get("/app").data.decode())
        self.assertNotRegex(home, r"\d days limit|business days limit")
        self.assertIn("is over the 3-business-day limit", home)
        page = words(self.client.get(f"/app/industry/{HR}").data.decode())
        self.assertNotRegex(page, r"Limit \d")

    def test_the_plan_page_says_the_plan_once(self):
        from omniarmor_app import academy_plan
        self.signup()
        trial = words(between(self.client.get("/app/plan").data.decode(), '<div class="page-head">', "</div>\n</div>"))
        self.assertIn("Your free trial is on 14 days left of everything in Plus.", trial)
        self.assertEqual(trial.lower().count("free trial"), 1, trial)
        with self.db() as conn:
            academy_plan.set_status(conn, 1, "active", renews_at="2026-12-24T00:00:00+00:00", kind="plus", interval="month")
            conn.commit()
        page = self.client.get("/app/plan").data.decode()
        head = words(between(page, '<div class="page-head">', "</div>\n</div>"))
        self.assertIn("You're on Plus", head)
        self.assertEqual(head.count("You're on"), 1, head)
        self.assertIn("Billed monthly, renews", head)
        settings = words(self.client.get("/app/settings").data.decode())
        self.assertIn("You're on Plus, renews", settings, "Settings, with no heading saying it, still does")

    def test_version_and_changelog(self):
        from omniarmor_app.version import __version__
        self.assertEqual(__version__, "1.26.0")
        log = read("CHANGELOG.md")
        section = log[log.index("## 1.26.0"):log.index("## 1.25.0")]
        for said in ("Back to the name OmniArmor", "day 9", "Yes.", "Time zone", "Change password", "Last done 35 days",
                     "7-day limit", "free plan", "yearly discount"):
            self.assertIn(said, section)
        self.assertIn("**1.26.0**", read("docs", "PILOT.md"))


if __name__ == "__main__":
    unittest.main()
