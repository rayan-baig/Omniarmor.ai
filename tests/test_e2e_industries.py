"""Every industry, end to end, the way a new customer meets it.

For each of the catalog's industries: open its public page, follow "Start
free", sign up from the real form, open the industry, save one check of each
kind of input it has (yes/no, number, date, date and time, business days,
months or years) through the form on the page, see the right state, then find
each check in the printable report and the CSV export.

The cases come from the catalog, so a new industry or a new kind of check is
covered without touching this file.
"""

import calendar
import html
import os
import re
import sys
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from e2e_helpers import csv_rows, flashes, forms, post_forms, table_rows  # noqa: E402
from test_webapp import PASSWORD, AppTestCase  # noqa: E402

from omniarmor_app.catalog import (INDUSTRIES, counts_first_day, counts_time, date_mode, date_unit,  # noqa: E402
                                   rules_for)

TZ = "America/New_York"
LABEL = {"BLOCKED": "Blocked", "WARNING": "Warning", "CLEARED": "Cleared"}


def input_kind(rule):
    """Which kind of box the industry page shows for a check."""
    if rule.kind in ("required", "forbidden"):
        return "yes/no"
    unit = date_unit(rule)
    if unit is None:
        return "number"
    if unit == "days":
        return f"date ({date_mode(rule)})"
    if counts_time(rule):
        return "date and time"
    if unit == "business days":
        return "business days"
    return "months or years"


def one_of_each_kind(industry_id):
    picked = {}
    for rule in rules_for(industry_id):
        picked.setdefault(input_kind(rule), rule)
    return picked


def expected_level(rule, value):
    """The three answers, worked out here from the rule's own numbers."""
    if rule.kind == "max":
        if value > rule.limit:
            return "BLOCKED"
        return "WARNING" if rule.warn is not None and value >= rule.warn else "CLEARED"
    if value < rule.limit:
        return "BLOCKED"
    return "WARNING" if rule.warn is not None and value <= rule.warn else "CLEARED"


def months_back(day, months):
    year, month = divmod(day.month - 1 - months, 12)
    year += day.year
    return date(year, month + 1, min(day.day, 28, calendar.monthrange(year, month + 1)[1]))


def plan(rule, kind, today, now):
    """What to type for a check, and what the page should then say:
    (form fields, expected level, expected due date as text or None)."""
    if kind == "yes/no":
        answer = "yes" if rule.kind == "required" else "no"     # the safe answer
        return {"answer": answer}, "CLEARED", None
    if kind == "number":
        if rule.warn is not None and rule.warn != rule.limit:
            return {"value": f"{rule.warn:g}"}, "WARNING", None                 # at the warning point
        step = max(1, abs(rule.limit))
        value = rule.limit + step if rule.kind == "max" else rule.limit - step  # past the limit
        return {"value": f"{value:g}"}, "BLOCKED", None
    if kind == "date (since)":
        days = int(rule.limit) + 3                                # three days overdue
        done = today - timedelta(days=days)
        first_day = counts_first_day(rule)
        value = days + 1 if first_day else days
        due = done + timedelta(days=int(rule.limit) - (1 if first_day else 0))
        return {"date": done.isoformat()}, expected_level(rule, value), due.isoformat()
    if kind == "date (until)":
        ahead = int(rule.warn if rule.warn is not None else rule.limit) + 10 if rule.kind == "min" else 5
        due_on = today + timedelta(days=ahead)
        return ({"date": due_on.isoformat()}, expected_level(rule, ahead),
                (due_on - timedelta(days=int(rule.limit))).isoformat())
    if kind == "date and time":
        per = 60 if date_unit(rule) == "hours" else 1
        started = now - timedelta(minutes=(rule.limit + 2) * per)   # two hours (or minutes) overdue
        return {"date": started.strftime("%Y-%m-%dT%H:%M")}, expected_level(rule, rule.limit + 2), None
    if kind == "business days":
        return {"date": today.isoformat()}, expected_level(rule, 0), None    # done today: nothing counted yet
    # Months or years: two months (or a year) past the limit.
    unit = date_unit(rule)
    if unit == "years":
        done, value = months_back(today, (int(rule.limit) + 1) * 12), rule.limit + 1
    else:
        done, value = months_back(today, int(rule.limit) + 2), rule.limit + 2
    return {"date": done.isoformat()}, expected_level(rule, value), None


BOX = {"date (since)": "date", "date (until)": "date", "business days": "date", "months or years": "date",
       "date and time": "datetime-local"}


class TestEveryIndustryEndToEnd(AppTestCase):
    def sign_up_from_the_brand_page(self, info):
        page = self.client.get(f"/industries/{info['brand'].lower()}")
        self.assertEqual(page.status_code, 200)
        text = page.data.decode()
        for rule in rules_for(info["id"]):
            self.assertIn(rule.title, html.unescape(text))
        start = re.search(r'href="(/signup\?industry=\d+)"', text).group(1)
        signup = self.client.get(start).data.decode()
        form = next(f for f in post_forms(signup) if f.action == "/signup")
        data = form.values()
        self.assertEqual(data.get("industries"), str(info["id"]), "the brand page's industry is picked")
        data.update(name="Pat Owner", email="owner@example.com", password=PASSWORD, org_name="Acme Works",
                    timezone=TZ)
        response = self.client.post("/signup", data=data)
        self.assertEqual(response.status_code, 302, flashes(response.data.decode()))
        overview = self.client.get("/app").data.decode()
        self.assertIn(f'href="/app/industry/{info["id"]}"', overview)

    def rule_form(self, page, rule):
        found = [f for f in post_forms(page) if f.section == f"rule-{rule.key}" and f.field("action") is None
                 and any(b.get("value") == "save" for b in f.buttons)]
        self.assertEqual(len(found), 1, rule.key)
        return found[0]

    def run_industry(self, industry_id):
        info = INDUSTRIES[industry_id]
        self.sign_up_from_the_brand_page(info)
        page = self.client.get(f"/app/industry/{industry_id}").data.decode()
        self.assertEqual(page.count('class="rule"'), len(rules_for(industry_id)))
        tz = ZoneInfo(TZ)
        now = datetime.now(tz)
        today = now.date()
        saved = []
        for kind, rule in one_of_each_kind(industry_id).items():
            with self.subTest(industry=info["brand"], kind=kind, rule=rule.key):
                form = self.rule_form(page, rule)
                # The page offers the right box for this kind of check.
                if kind == "yes/no":
                    self.assertEqual({i.get("value") for i in form.fields("radio")}, {"yes", "no"})
                else:
                    self.assertEqual(form.field("value").get("type"), "number")
                    box = form.field("date")
                    self.assertEqual(box.get("type") if box else None, BOX.get(kind), kind)
                fields, level, due = plan(rule, kind, today, now)
                data = form.values()
                data.update(fields, action="save")
                response = self.client.post(form.action, data=data)
                self.assertEqual(response.status_code, 302)
                self.assertTrue(response.headers["Location"].endswith(f"#rule-{rule.key}"))
                page = self.client.get(response.headers["Location"].split("#")[0]).data.decode()
                self.assertIn("Saved.", flashes(page), (kind, flashes(page)))
                shown = re.search(rf'<li class="rule" id="rule-{re.escape(rule.key)}" data-level="(\w+)"', page)
                self.assertEqual(shown.group(1), level, (kind, rule.key))
                # The form now shows what was saved.
                again = self.rule_form(page, rule).values()
                if kind == "yes/no":
                    self.assertEqual(again.get("answer"), fields["answer"])
                elif "date" in fields:
                    self.assertEqual(again.get("date"), fields["date"])
                else:
                    self.assertEqual(float(again.get("value")), float(fields["value"]))
                saved.append((rule, kind, level, due))

        report = self.client.get("/app/report")
        self.assertEqual(report.status_code, 200)
        rows = {r[0]: r for r in table_rows(report.data.decode()) if r}
        exported = self.client.get("/app/report.csv")
        self.assertEqual(exported.status_code, 200)
        self.assertIn("attachment", exported.headers["Content-Disposition"])
        lines = csv_rows(exported.data.decode("utf-8"))
        self.assertEqual(lines[0][:5], ["Industry", "Check", "Status", "Reading", "Due date"])
        exported_rows = {(r[0], r[1]): r for r in lines[1:]}
        self.assertEqual(len(lines) - 1, len(rules_for(industry_id)))
        for rule, kind, level, due in saved:
            with self.subTest(industry=info["brand"], kind=kind, rule=rule.key, where="report"):
                self.assertIn(rule.title, rows, "in the printable report")
                self.assertEqual(rows[rule.title][1], LABEL[level])
                self.assertNotEqual(rows[rule.title][2], "—", "the report shows the reading")
                row = exported_rows.get((info["brand"], rule.title))
                self.assertIsNotNone(row, "in the CSV export")
                self.assertEqual(row[2], LABEL[level])
                self.assertTrue(row[3], "the CSV has the reading")
                self.assertEqual(row[7], "Pat Owner")
                if due is not None:
                    self.assertEqual(row[4], due)
                    self.assertEqual(rows[rule.title][3], due)
                elif kind != "yes/no" and kind != "number":
                    self.assertTrue(row[4], "a date-counted check has a due date")
        # Each save is in the audit trail too.
        trail = self.client.get("/app/audit.csv").data.decode()
        for rule, *_ in saved:
            self.assertIn(rule.title, trail)


def _make(industry_id):
    def test(self):
        self.run_industry(industry_id)
    test.__doc__ = f"{INDUSTRIES[industry_id]['brand']}: sign up, save each kind of check, find it in the report"
    return test


for _id, _info in INDUSTRIES.items():
    setattr(TestEveryIndustryEndToEnd, f"test_{_id:02d}_{_info['brand'].lower()}", _make(_id))


class TestTheCasesCoverEveryKind(AppTestCase):
    def test_every_kind_of_input_is_exercised_somewhere(self):
        kinds = {input_kind(r) for i in INDUSTRIES for r in rules_for(i)}
        self.assertEqual(kinds, {"yes/no", "number", "date (since)", "date (until)", "date and time",
                                 "business days", "months or years"})

    def test_signed_out_people_cannot_open_an_industry(self):
        for industry_id in INDUSTRIES:
            response = self.client.get(f"/app/industry/{industry_id}")
            self.assertEqual(response.status_code, 302)
            self.assertIn("/login", response.headers["Location"])
        self.assertEqual(len(forms(self.client.get("/login").data.decode())), 1)
