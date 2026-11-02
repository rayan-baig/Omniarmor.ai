"""The rule catalog against the handbook, and every date-counted rule at its edges.

1. docs/HANDBOOK.md, Appendix A, lists every check with its limit, warning
   point, way of counting and the example reading used in demos. Each entry
   must say what the catalog holds, and each example reading must come out
   the way those numbers say: typed in, and for a date-counted check entered
   as the date that gives the same reading.
2. Every check counted from a date is checked at its due date and its warning
   point, from starts at month ends and on leap days (31 January plus a
   month, 29 February plus a year): the due date is the last day before
   Blocked and the warning day is the first day of Warning. The same for a
   company's own limits with a part of a day, month or year in them.
3. The hour and minute clocks turn to Warning at their warning minute and to
   Blocked the minute after their due minute.
"""

import os
import re
import sys
import unittest
from dataclasses import replace
from datetime import date, datetime, timedelta, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from omni_armor_platform import MoonstoneThemeColors  # noqa: E402
from omni_armor_rules import CATALOG, evaluate  # noqa: E402
from omni_armor_rules.rule import _fmt  # noqa: E402
from omniarmor_app.catalog import can_override, counts_first_day, counts_time, date_mode, date_unit  # noqa: E402
from omniarmor_app.tracking import compute_state, federal_holidays  # noqa: E402

HANDBOOK = os.path.join(ROOT, "docs", "HANDBOOK.md")

# Month ends, leap days and the turn of the year.
STARTS = [date(2024, 1, 31), date(2024, 2, 29), date(2023, 2, 28), date(2024, 2, 28), date(2023, 1, 29),
          date(2024, 3, 31), date(2023, 8, 31), date(2024, 4, 30), date(2023, 12, 31), date(2025, 1, 31),
          date(2027, 12, 31), date(2023, 1, 1)]


def row(value_date=None, value_num=None, limit=None, warn=None):
    return {"value_bool": None, "value_date": value_date, "value_num": value_num, "limit_override": limit,
            "warn_override": warn, "updated_at": None, "updated_by_name": None}


def date_rules():
    for industry_id, rules in sorted(CATALOG.items()):
        for rule in rules:
            if date_mode(rule) and not counts_time(rule):
                yield industry_id, rule


def is_business_day(day):
    return day.weekday() < 5 and day not in federal_holidays(day.year)


# --- 1. The handbook's Appendix A -------------------------------------------------------

def _header(rule):
    """The words in brackets after a check's title in Appendix A."""
    if rule.kind in ("required", "forbidden"):
        text = ("Must be in place" if rule.kind == "required" else "Must never happen") + ", answered Yes or No"
        return text + ("; policy" if rule.policy else "")
    text = ("Maximum " if rule.kind == "max" else "Minimum ") + _fmt(rule.limit, rule.unit)
    if rule.warn is not None:
        text += ", warns from " + _fmt(rule.warn, rule.unit)
    if rule.policy:
        text += "; policy, a company can set its own limit"
    unit, mode = date_unit(rule), date_mode(rule)
    if unit == "days":
        text += f"; counts days {mode} a date" + (", the first day as day 1" if counts_first_day(rule) else "")
    elif unit == "business days":
        text += "; counts business days since a date"
    elif unit in ("hours", "minutes"):
        text += f"; counts {unit} since a date and time"
    return text


def _shown(value, unit):
    return ("Yes" if value else "No") if isinstance(value, bool) else _fmt(value, unit)


def appendix_entries():
    """{(industry id, position): {"title", "header", "Asks", "Rule", ..., "industry"}} from Appendix A."""
    with open(HANDBOOK, encoding="utf-8") as f:
        text = f.read()
    start = text.index("## Appendix A")
    part = text[start:text.index("\n## ", start + 1)]
    entries, industry, current = {}, None, None
    for line in part.splitlines():
        m = re.match(r"^### (\d+)\. (.+)$", line)
        if m:
            industry = (int(m.group(1)), m.group(2))
            continue
        m = re.match(r"^\*\*(\d+)\. (.+?)\*\* \((.+)\)$", line)
        if m:
            current = entries.setdefault((industry[0], int(m.group(1))), {
                "industry": industry[1], "title": m.group(2), "header": m.group(3)})
            continue
        m = re.match(r"^- ([^:]+): (.*)$", line)
        if m and current is not None:
            current[m.group(1)] = m.group(2)
    return entries


def _parse_reading(text, rule):
    """The example reading as the handbook writes it, back to a value."""
    if rule.kind in ("required", "forbidden"):
        return {"Yes": True, "No": False}[text]
    number = re.search(r"-?[\d,]+(?:\.\d+)?", text.replace("$", "")).group(0).replace(",", "")
    return float(number) if "." in number else int(number)


class TestHandbookAppendix(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.entries = appendix_entries()

    def test_every_check_is_listed_once(self):
        self.assertEqual(sorted(self.entries), [(i, n) for i in sorted(CATALOG) for n in range(1, 11)])

    def test_each_entry_says_what_the_catalog_holds(self):
        for (industry_id, n), entry in self.entries.items():
            rule = CATALOG[industry_id][n - 1]
            where = f"Appendix A, {industry_id}.{n} ({rule.key})"
            self.assertEqual(entry["industry"], MoonstoneThemeColors.INDUSTRIES[industry_id]["name"], where)
            self.assertEqual(entry["title"], rule.title, where)
            self.assertEqual(entry["header"], _header(rule), where)
            self.assertEqual(entry["Asks"], rule.input, where)
            self.assertEqual(entry["Rule"], rule.citation, where)
            self.assertEqual(entry["What a miss costs"], rule.cost, where)
            self.assertEqual(entry["What to do when it's broken"], rule.action, where)
            self.assertEqual(entry["Example reading used in demos"], _shown(rule.sample, rule.unit), where)

    def test_each_example_reading_comes_out_as_the_handbook_says(self):
        """The outcome follows from the limit and warning point the handbook
        states: read them back from its words and check the example with them."""
        outcomes = {"BLOCKED": 0, "WARNING": 0, "CLEARED": 0}
        for (industry_id, n), entry in self.entries.items():
            rule = CATALOG[industry_id][n - 1]
            m = re.match(r"(Maximum|Minimum) (.+?)(?:,? warns from (.+?))?(?:;|$)", entry["header"])
            stated = rule
            if m:
                stated = replace(rule, kind="max" if m.group(1) == "Maximum" else "min",
                                 limit=_parse_reading(m.group(2), rule),
                                 warn=None if m.group(3) is None else _parse_reading(m.group(3), rule))
            elif entry["header"].startswith("Must never happen"):
                stated = replace(rule, kind="forbidden")
            else:
                stated = replace(rule, kind="required")
            reading = _parse_reading(entry["Example reading used in demos"], rule)
            expected = evaluate(stated, reading)[0]
            self.assertEqual(evaluate(rule, rule.sample)[0], expected, f"{industry_id}.{n} {rule.key}")
            outcomes[expected] += 1
        # The demos show all three answers.
        self.assertTrue(all(outcomes.values()), outcomes)

    def test_a_date_that_gives_the_example_reading_gives_the_same_answer(self):
        """In the app a date-counted check is usually entered as a date. A date
        that counts to the example reading must give the example's answer."""
        today = date(2026, 11, 2)
        checked = 0
        for industry_id, rule in date_rules():
            if rule.sample != int(rule.sample):
                continue
            unit, mode, n = date_unit(rule), date_mode(rule), int(rule.sample)
            if unit == "days":
                shift = n - 1 if counts_first_day(rule) else n
                picked = today - timedelta(days=shift) if mode == "since" else today + timedelta(days=n)
            elif unit == "business days":
                picked = today
                while compute_state(industry_id, rule, row(picked.isoformat()), today).value < n:
                    picked -= timedelta(days=1)
            else:
                months = n * (12 if unit == "years" else 1)
                year, month = divmod(today.month - 1 - months, 12)
                picked = today.replace(year=today.year + year, month=month + 1)
            state = compute_state(industry_id, rule, row(picked.isoformat()), today)
            where = f"{industry_id} {rule.key} from {picked}"
            self.assertEqual(state.value, n, where)
            self.assertEqual(state.level, evaluate(rule, rule.sample)[0], where)
            checked += 1
        self.assertGreater(checked, 150)


# --- 2. Due dates and warning days at month ends and leap days ----------------------------

class TestDateCountedEdges(unittest.TestCase):
    def check_edges(self, industry_id, rule, start, override=None):
        """The due date is the last day before Blocked (for a business-day check,
        the last business day: the weekend or holiday after it still counts the
        same), and the warning day is the first day of Warning."""
        stored = row(start.isoformat(), **(override or {}))
        level = lambda day: compute_state(industry_id, rule, stored, day).level  # noqa: E731
        state = compute_state(industry_id, rule, stored, start)
        eff = state.effective
        where = f"{industry_id} {rule.key} from {start} limit {eff.limit} warn {eff.warn}"
        due = state.due_date
        self.assertNotEqual(level(due), "BLOCKED", f"{where}: Blocked on its due date {due}")
        after = due + timedelta(days=1)
        if date_unit(rule) == "business days":
            while not is_business_day(after):
                self.assertNotEqual(level(after), "BLOCKED", f"{where}: {after}")
                after += timedelta(days=1)
        self.assertEqual(level(after), "BLOCKED", f"{where}: not Blocked on {after}, after the due date {due}")
        if eff.warn is not None and eff.warn != eff.limit:
            warn = state.warn_date
            self.assertEqual(level(warn), "WARNING", f"{where}: not a Warning on its warning day {warn}")
            if date_unit(rule) != "business days" or is_business_day(warn - timedelta(days=1)):
                self.assertEqual(level(warn - timedelta(days=1)), "CLEARED", f"{where}: a Warning before {warn}")

    def test_every_date_counted_rule_from_month_ends_and_leap_days(self):
        for industry_id, rule in date_rules():
            for start in STARTS:
                if date_mode(rule) == "until":
                    start += timedelta(days=400)  # an expiry date ahead
                with self.subTest(rule=rule.key, start=start):
                    self.check_edges(industry_id, rule, start)

    def test_a_companys_own_limits_with_part_of_a_day_month_or_year(self):
        """A company can set 10.3 years or 365.5 days. Rounding the part to the
        nearest day put a due date on a day that was already Blocked, and a
        warning day on a day that was still Cleared."""
        for industry_id, rule in date_rules():
            if not can_override(rule):
                continue
            if rule.kind == "max":
                settings = [(rule.limit + 0.3, rule.limit * 0.83), (rule.limit + 0.5, rule.limit - 0.5)]
            else:
                settings = [(rule.limit + 0.5, rule.warn + 0.5), (rule.limit + 0.3, rule.warn + 2.7)]
            for limit, warn in settings:
                for start in STARTS:
                    if date_mode(rule) == "until":
                        start += timedelta(days=400)
                    with self.subTest(rule=rule.key, limit=limit, warn=warn, start=start):
                        self.check_edges(industry_id, rule, start, {"limit": limit, "warn": warn})

    def test_fire_gear_retired_at_ten_point_three_years(self):
        rule = next(r for r in CATALOG[14] if r.key == "gear_retirement")
        state = compute_state(14, rule, row("2023-01-31", limit=10.3), date(2033, 5, 19))
        self.assertEqual(state.level, "BLOCKED")
        self.assertEqual(state.due_date, date(2033, 5, 18))

    def test_a_month_from_the_31st_and_a_year_from_29_february(self):
        rule = next(r for r in CATALOG[24] if r.key == "security_drill")  # a months check
        month = replace(rule, limit=1, warn=None)
        for start, due in (("2024-01-31", date(2024, 2, 29)), ("2023-01-31", date(2023, 2, 28)),
                           ("2024-03-31", date(2024, 4, 30)), ("2023-12-31", date(2024, 1, 31))):
            s = compute_state(24, month, row(start), due)
            self.assertEqual((s.value, s.level, s.due_date), (1, "CLEARED", due), start)
            s = compute_state(24, month, row(start), due + timedelta(days=1))
            self.assertEqual(s.level, "BLOCKED", start)
            self.assertGreater(s.value, 1)
        year = replace(rule, limit=12, warn=None)
        for today, level in ((date(2025, 2, 28), "CLEARED"), (date(2025, 3, 1), "BLOCKED")):
            s = compute_state(24, year, row("2024-02-29"), today)
            self.assertEqual((s.level, s.due_date), (level, date(2025, 2, 28)), today)
        four = replace(rule, limit=48, warn=None)
        self.assertEqual(compute_state(24, four, row("2024-02-29"), date(2028, 2, 29)).value, 48)
        self.assertEqual(compute_state(24, four, row("2024-02-29"), date(2028, 2, 29)).due_date, date(2028, 2, 29))

    def test_the_quarterly_drill_warns_from_two_and_a_half_months(self):
        # Two and a half months from 31 January 2023 (29 days from 28 February
        # to 31 March) falls in the middle of 14 April.
        rule = next(r for r in CATALOG[24] if r.key == "security_drill")
        s = compute_state(24, rule, row("2023-01-31"), date(2023, 4, 14))
        self.assertEqual(s.warn_date, date(2023, 4, 15))
        self.assertEqual(s.level, "CLEARED")
        self.assertEqual(compute_state(24, rule, row("2023-01-31"), date(2023, 4, 15)).level, "WARNING")

    def test_calendar_months_warn_from_the_first_of_the_month(self):
        rule = next(r for r in CATALOG[4] if r.key == "pilot_competency_check")  # 12 calendar months, warns from 11
        s = compute_state(4, rule, row("2025-06-10"), date(2026, 5, 1))
        self.assertEqual((s.level, s.warn_date, s.due_date), ("WARNING", date(2026, 5, 1), date(2026, 6, 30)))
        self.assertEqual(compute_state(4, rule, row("2025-06-10"), date(2026, 4, 30)).level, "CLEARED")


# --- 3. The hour and minute clocks at their warning and due minutes -----------------------

class TestClockEdges(unittest.TestCase):
    def test_every_clock_warns_and_blocks_on_the_minute(self):
        starts = [datetime(2024, 2, 28, 23, 30, tzinfo=timezone.utc), datetime(2023, 12, 31, 22, 0, tzinfo=timezone.utc),
                  datetime(2024, 1, 31, 23, 59, tzinfo=timezone.utc), datetime(2023, 2, 28, 12, 0, tzinfo=timezone.utc)]
        minute = timedelta(minutes=1)
        for industry_id, rules in sorted(CATALOG.items()):
            for rule in rules:
                if not counts_time(rule):
                    continue
                for start in starts:
                    stored = row(start.isoformat())
                    at = lambda now: compute_state(industry_id, rule, stored, now.date(), now, timezone.utc)  # noqa: E731
                    s = at(start)
                    where = f"{industry_id} {rule.key} from {start}"
                    self.assertEqual(at(s.due_at).level, "WARNING" if rule.warn is not None else "CLEARED", where)
                    self.assertEqual(at(s.due_at + minute).level, "BLOCKED", where)
                    per = 60 if date_unit(rule) == "hours" else 1
                    self.assertEqual(s.due_at - start, timedelta(minutes=rule.limit * per), where)
                    if rule.warn is not None and rule.warn < rule.limit:
                        self.assertEqual(s.warn_at - start, timedelta(minutes=rule.warn * per), where)
                        self.assertEqual(at(s.warn_at).level, "WARNING", where)
                        self.assertEqual(at(s.warn_at - minute).level, "CLEARED", where)


if __name__ == "__main__":
    unittest.main()
