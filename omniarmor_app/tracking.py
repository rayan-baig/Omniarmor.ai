# -*- coding: utf-8 -*-
"""Current status of every rule for a company, and the changes people make to it.

Readings are stored once and recomputed every day:
    - date-tracked rules store a date ("last done" or "due on"); the day count
      is worked out from today's date in the company's timezone
    - hour clocks store the moment they started, in UTC; the hours are counted
      from it to now, and shown in the company's timezone
    - other number rules store a number; yes/no rules store a yes or no
Every change is written to the audit trail with who made it and when.
"""

import calendar
import json
import math
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from omni_armor_rules import evaluate
from omni_armor_rules.rule import _fmt as format_quantity

from .catalog import (INDUSTRIES, can_override, counts_first_day, counts_time, date_mode, date_unit, effective_rule,
                      find_rule, rules_for)
from .db import iso, now_iso, record_audit, user_name, utcnow

LEVEL_ORDER = {"BLOCKED": 0, "WARNING": 1, "NONE": 2, "CLEARED": 3}
LEVEL_LABEL = {"BLOCKED": "Blocked", "WARNING": "Warning", "CLEARED": "Cleared", "NONE": "No reading"}
EARLIEST_DATE = date(1950, 1, 1)
LATEST_DATE = date(2150, 12, 31)


class ValidationError(ValueError):
    """A reading or setting a person entered that cannot be saved; the message says why."""


def org_today(org):
    return datetime.now(ZoneInfo(org["timezone"])).date()


def org_now(org):
    return datetime.now(ZoneInfo(org["timezone"]))


def _duration(minutes):
    """A span of whole minutes in words: "45 min", "5 h 20 min", "3 days 2 h"."""
    if minutes < 60:
        return f"{minutes} min"
    if minutes < 48 * 60:
        hours, rest = divmod(minutes, 60)
        return f"{hours} h" + (f" {rest} min" if rest else "")
    days, rest = divmod(minutes, 24 * 60)
    return f"{days} days" + (f" {rest // 60} h" if rest // 60 else "")


def _plural_days(n):
    return f"{n} day{'s' if n != 1 else ''}"


@dataclass
class ItemState:
    industry_id: int
    rule: object
    effective: object
    mode: object
    value: object
    level: str
    status: str
    message: str
    value_date: object
    due_date: object
    warn_date: object
    today: date
    updated_at: object
    updated_by: object
    # Hour and minute clocks only: when the clock started, when it is due and
    # when it warns (in the company's timezone), and whole minutes left
    # (negative once overdue).
    value_at: object = None
    due_at: object = None
    warn_at: object = None
    minutes_left: object = None

    @property
    def key(self):
        return self.rule.key

    @property
    def industry(self):
        return INDUSTRIES[self.industry_id]

    @property
    def label(self):
        return LEVEL_LABEL[self.level]

    @property
    def days_left(self):
        """Days from today to the due date. An hour clock that ran out earlier
        today is already overdue, so it counts as -1, not "due today"."""
        if self.due_date is None:
            return None
        days = (self.due_date - self.today).days
        return min(days, -1) if self.minutes_left is not None and self.minutes_left < 0 else days

    @property
    def overdue(self):
        return self.days_left is not None and self.days_left < 0

    @property
    def overdue_by(self):
        """How far past due, in words: "3 days", or "2 h 5 min" for an hour clock."""
        if not self.overdue:
            return None
        return _duration(-self.minutes_left) if self.minutes_left is not None else _plural_days(-self.days_left)

    @property
    def due_in(self):
        """When it is due, in words: "today", "in 3 days", or "in 5 h 20 min" for an hour clock."""
        if self.due_date is None or self.overdue:
            return None
        if self.minutes_left is not None:
            return "now" if self.minutes_left == 0 else f"in {_duration(self.minutes_left)}"
        return "today" if self.days_left == 0 else f"in {_plural_days(self.days_left)}"

    @property
    def due_text(self):
        """The due line on the industry page: "3 days overdue", "Due today", "Due in 5 h 20 min"."""
        if self.due_date is None:
            return ""
        return f"{self.overdue_by} overdue" if self.overdue else f"Due {self.due_in}"

    @property
    def due_label(self):
        """The due date, or for an hour clock the due date and time in the company's timezone."""
        if self.due_at is not None:
            return _moment_text(self.due_at)
        return self.due_date.isoformat() if self.due_date else ""

    @property
    def overridden(self):
        return self.effective is not self.rule

    @property
    def problem(self):
        return self.level in ("BLOCKED", "WARNING")

    @property
    def shown_value(self):
        if self.value is None:
            return ""
        if isinstance(self.value, bool):
            return "Yes" if self.value else "No"
        return format_quantity(self.value, self.rule.unit)

    @property
    def sort_key(self):
        return (LEVEL_ORDER[self.level], self.days_left if self.days_left is not None else 10 ** 6, self.industry_id, self.rule.title)


# A hundred years. Dates past this, either way, are not a schedule anybody
# keeps, and Python's dates stop at the year 9999: an override of three million
# days used to raise OverflowError on every page that showed the rule.
MAX_DAYS = 36500


def _whole_days(value):
    return max(-MAX_DAYS, min(MAX_DAYS, int(math.floor(value))))


def _shifted(day, days):
    """`day` moved by `days`, or None past the calendar's end. One stored row
    must never take down every page that lists its company's rules."""
    try:
        return day + timedelta(days=days)
    except OverflowError:
        return None


# The longest limit a company can set, per unit a date-tracked check counts.
MAX_SPAN = {"days": MAX_DAYS, "months": 1200, "calendar months": 1200, "years": 100, "business days": 26000,
            "hours": MAX_DAYS * 24, "minutes": MAX_DAYS * 24 * 60}


# --- Hour and minute clocks: real time since a moment, in whole minutes -----

def _moment_text(moment):
    """A moment as the company reads it, e.g. "2026-11-02 14:30 EST"."""
    return moment.strftime("%Y-%m-%d %H:%M %Z").strip()


def _stored_moment(text, tz):
    """The start of an hour clock from the database, in the company's timezone.
    Stored as UTC; a bare date (none are written, but never crash) is local midnight."""
    try:
        moment = datetime.fromisoformat(text)
    except ValueError:
        return None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=tz) if "T" in text or " " in text else datetime.combine(moment.date(), time(0), tz)
    return moment.astimezone(tz)


def _moment_on(today, tz):
    """The moment a day is checked at: now when it is today there, otherwise
    noon that day (reminder runs and tests can ask about another day)."""
    now = datetime.now(tz)
    return now if now.date() == today else datetime.combine(today, time(12), tz)


def _whole_minutes(amount, unit):
    """A limit in hours or minutes as whole minutes. Floored, so the due minute
    is the last one still within the limit."""
    per = 60 if unit == "hours" else 1
    return max(0, min(MAX_SPAN["minutes"], math.floor(amount * per + 1e-9)))


def _time_since(start, now, unit):
    """Hours (or minutes) from start to now, counted in whole minutes: exactly
    72 hours for the whole 72nd-hour minute, a little over from the next
    minute. Returns the reading and the minutes. Real time: worked out in UTC,
    as Python counts by the wall clock within one timezone (a night when
    clocks go back would lose an hour)."""
    minutes = math.floor((now.astimezone(timezone.utc) - start.astimezone(timezone.utc)).total_seconds() / 60)
    if unit == "minutes":
        return minutes, minutes
    return minutes // 60 if minutes % 60 == 0 else minutes / 60, minutes


# --- Business days: Monday to Friday, not counting US federal holidays -------

def _nth_weekday(year, month, weekday, n):
    """The nth `weekday` (0 = Monday) of a month; n = -1 for the last one."""
    if n > 0:
        first = date(year, month, 1)
        return first + timedelta(days=(weekday - first.weekday()) % 7 + 7 * (n - 1))
    last = date(year, month, calendar.monthrange(year, month)[1])
    return last - timedelta(days=(last.weekday() - weekday) % 7)


def _observed(day):
    """A holiday on a Saturday is kept the Friday before; on a Sunday, the Monday after."""
    return day - timedelta(days=1) if day.weekday() == 5 else day + timedelta(days=1) if day.weekday() == 6 else day


_HOLIDAYS = {}


def federal_holidays(year):
    """The days US federal offices are closed for a holiday in `year` (5 U.S.C. 6103)."""
    if year not in _HOLIDAYS:
        days = set()
        for y in (year, year + 1):  # 1 January on a Saturday is kept on 31 December
            fixed = [date(y, 1, 1), date(y, 7, 4), date(y, 11, 11), date(y, 12, 25)]
            if y >= 2021:
                fixed.append(date(y, 6, 19))
            days |= {_observed(d) for d in fixed}
            days |= {_nth_weekday(y, 2, 0, 3), _nth_weekday(y, 5, 0, -1), _nth_weekday(y, 9, 0, 1),
                     _nth_weekday(y, 10, 0, 2), _nth_weekday(y, 11, 3, 4)}
            if y >= 1986:
                days.add(_nth_weekday(y, 1, 0, 3))
        _HOLIDAYS[year] = frozenset(d for d in days if d.year == year)
    return _HOLIDAYS[year]


def _business_days(start, end):
    """Business days after `start`, up to and including `end` (end >= start)."""
    total = end.toordinal() - start.toordinal()
    count = total // 7 * 5
    for n in range(total % 7):
        if (start.weekday() + 1 + n) % 7 < 5:
            count += 1
    for year in range(start.year, end.year + 1):
        count -= sum(1 for h in federal_holidays(year) if start < h <= end and h.weekday() < 5)
    return count


def _add_business_days(day, count):
    """The day `count` business days after `day` (`day` itself when count is 0)."""
    end = day + timedelta(days=count // 5 * 7 + 7)  # past the answer, before holidays
    while _business_days(day, end) < count:
        end += timedelta(days=7)
    while end > day and _business_days(day, end - timedelta(days=1)) >= count:
        end -= timedelta(days=1)
    return end


def _add_months(day, months):
    """The same day `months` whole months later (or earlier), kept inside short months."""
    year, month = divmod(day.month - 1 + months, 12)
    year += day.year
    return date(year, month + 1, min(day.day, calendar.monthrange(year, month + 1)[1]))


def _months_between(start, end):
    """Months from start to end (end >= start): whole months up to the last
    monthly anniversary, plus the share of the month since then. Exactly 12 on
    the yearly anniversary, a little over 12 the day after."""
    whole = (end.year - start.year) * 12 + end.month - start.month
    if _add_months(start, whole) > end:
        whole -= 1
    begins, ends = _add_months(start, whole), _add_months(start, whole + 1)
    return whole + (end - begins).days / (ends - begins).days


def _elapsed(start, end, unit):
    """The time from start to end in the unit a check counts; negative when end is earlier."""
    if unit == "days":
        return (end - start).days
    if end < start:
        return -_elapsed(end, start, unit)
    if unit == "business days":
        return _business_days(start, end)
    if unit == "calendar months":
        # "Within the preceding 12 calendar months": a check any day in June
        # 2025 is good through June 30, 2026, so only the months are counted.
        return (end.year - start.year) * 12 + end.month - start.month
    months = _months_between(start, end)
    return months / 12 if unit == "years" else months


def _whole(amount, up):
    """`amount` rounded to a whole number, up or down, ignoring float dust
    (0.1 * 30 is 3.0000000000000004, which is still 3)."""
    return math.ceil(amount - 1e-9) if up else math.floor(amount + 1e-9)


def _deadline(day, amount, unit, sign, reached=False):
    """The last day a reading counted from `day` stays within `amount` units
    (the due date), or with `reached`, the first day the reading gets to
    `amount` (the day a check turns to Warning at its warning point).

    Either one rounds a part of a day the safe way: a due date never falls on
    a day that is already Blocked, and the warning day is never a day that is
    still Cleared. Counting up (since), the due date rounds down and the
    warning day up; counting down (until), the other way round."""
    up = reached == (sign > 0)
    if unit == "days":
        return _shifted(day, sign * max(-MAX_DAYS, min(MAX_DAYS, _whole(amount, up))))
    if unit == "business days":
        if sign < 0:
            return None  # no check counts business days until a date
        try:
            return _add_business_days(day, max(0, min(MAX_SPAN[unit], _whole(amount, up))))
        except (OverflowError, ValueError):
            return None
    amount = max(-MAX_SPAN[unit], min(MAX_SPAN[unit], amount)) * (12 if unit == "years" else 1)
    try:
        if unit == "calendar months" and sign > 0:
            first = day.replace(day=1)
            if reached:
                # The count is whole months, so it gets there on the 1st.
                return _add_months(first, _whole(amount, True))
            # Good through the end of the last month counted.
            return _add_months(first, _whole(amount, False) + 1) - timedelta(days=1)
        whole = math.floor(sign * amount + 1e-9)
        begins, ends = _add_months(day, whole), _add_months(day, whole + 1)
        return begins + timedelta(days=_whole((sign * amount - whole) * (ends - begins).days, up))
    except (OverflowError, ValueError):
        return None


def _past_due(rule, due_date):
    """Blocked the day after the due date. A business-day count stands still
    on a weekend or holiday, but "within 3 business days" is missed once the
    third one has ended: a check due on a Friday is overdue on the Saturday,
    not on the Monday."""
    source = " (policy setting)" if rule.policy else ""
    limit = format_quantity(rule.limit, rule.unit)
    return "BLOCKED", "OVER LIMIT", f"The {limit} limit ended on {due_date.isoformat()}{source}. {rule.action}"


def compute_state(industry_id, rule, row, today, now=None, tz=None):
    """The state of one check on `today`. Hour clocks count to `now` (an aware
    datetime; by default the current moment, or noon on a day other than
    today) and show their times in `tz` (the company's timezone, UTC if None)."""
    mode = date_mode(rule)
    unit = date_unit(rule)
    eff = effective_rule(rule, row)
    value = None
    value_date = origin = value_at = elapsed = None
    if row is not None:
        if rule.kind in ("required", "forbidden"):
            value = None if row["value_bool"] is None else bool(row["value_bool"])
        elif mode and row["value_date"] and counts_time(rule):
            tz = tz or timezone.utc
            value_at = _stored_moment(row["value_date"], tz)
            if value_at is not None:
                now = (now or _moment_on(today, tz)).astimezone(tz)
                value, elapsed = _time_since(value_at, now, unit)
                value_date = value_at.date()
        elif mode and row["value_date"]:
            value_date = date.fromisoformat(row["value_date"][:10])
            # A check that counts its first day as day 1 counts from the day before.
            origin = value_date - timedelta(days=1) if counts_first_day(rule) else value_date
            value = _elapsed(origin, today, unit) if mode == "since" else _elapsed(today, value_date, unit)
        elif row["value_num"] is not None:
            value = row["value_num"]
            if isinstance(value, float) and value.is_integer():
                value = int(value)
    if value is None:
        level, status, message = "NONE", "NO READING", "No reading yet."
    else:
        level, status, message = evaluate(eff, value)

    due_date = warn_date = due_at = warn_at = minutes_left = None
    if value_at is not None:
        start = value_at.astimezone(timezone.utc)  # real time, see _time_since
        limit_minutes = _whole_minutes(eff.limit, unit)
        due_at = (start + timedelta(minutes=limit_minutes)).astimezone(tz)
        due_date, minutes_left = due_at.date(), limit_minutes - elapsed
        if eff.warn is not None:
            warn_at = (start + timedelta(minutes=_whole_minutes(eff.warn, unit))).astimezone(tz)
            warn_date = warn_at.date()
    elif value_date is not None:
        sign = 1 if mode == "since" else -1
        due_date = _deadline(origin, eff.limit, unit, sign)
        if eff.warn is not None:
            warn_date = _deadline(origin, eff.warn, unit, sign, reached=True)
        if unit == "business days" and level != "BLOCKED" and due_date is not None and today > due_date:
            level, status, message = _past_due(eff, due_date)
    return ItemState(
        industry_id=industry_id, rule=rule, effective=eff, mode=mode, value=value, level=level,
        status=status, message=message, value_date=value_date, due_date=due_date, warn_date=warn_date,
        today=today,
        updated_at=row["updated_at"] if row is not None else None,
        updated_by=row["updated_by_name"] if row is not None else None,
        value_at=value_at, due_at=due_at, warn_at=warn_at, minutes_left=minutes_left,
    )


def org_industry_ids(conn, org_id):
    rows = conn.execute("SELECT industry_id FROM org_industries WHERE org_id = ? ORDER BY industry_id", (org_id,))
    return [r["industry_id"] for r in rows if r["industry_id"] in INDUSTRIES]


def _load_rows(conn, org_id):
    rows = conn.execute(
        "SELECT items.*, COALESCE(users.name, items.updated_by_name) AS updated_by_name FROM items"
        " LEFT JOIN users ON users.id = items.updated_by WHERE items.org_id = ?",
        (org_id,),
    )
    return {(r["industry_id"], r["rule_key"]): r for r in rows}


def states_for_org(conn, org, industry_ids=None, today=None, now=None):
    tz = ZoneInfo(org["timezone"])
    if today is None:
        now = now or datetime.now(tz)
        today = now.astimezone(tz).date()
    now = now or _moment_on(today, tz)
    ids = org_industry_ids(conn, org["id"]) if industry_ids is None else industry_ids
    rows = _load_rows(conn, org["id"])
    return [compute_state(i, rule, rows.get((i, rule.key)), today, now, tz) for i in ids for rule in rules_for(i)]


def tally(states):
    counts = {level: 0 for level in LEVEL_LABEL}
    for s in states:
        counts[s.level] += 1
    return counts


# ---------------------------------------------------------------------------
# Changes
# ---------------------------------------------------------------------------

def _describe(rule, row, tz=None):
    if row is None:
        return "no reading"
    if rule.kind in ("required", "forbidden"):
        return "no reading" if row["value_bool"] is None else ("Yes" if row["value_bool"] else "No")
    if row["value_date"] and counts_time(rule):
        started = _stored_moment(row["value_date"], tz or timezone.utc)
        return f"started {_moment_text(started)}" if started else f"started {row['value_date']}"
    if row["value_date"]:
        return f"date {row['value_date']}"
    if row["value_num"] is not None:
        n = row["value_num"]
        return format_quantity(int(n) if float(n).is_integer() else n, rule.unit)
    return "no reading"


def _parse_number(text):
    text = (text or "").strip().replace(",", "")
    if not text:
        return None
    try:
        n = float(text)
    except ValueError:
        raise ValidationError("Enter a number, for example 12 or 4.5.")
    if not math.isfinite(n):
        raise ValidationError("Enter a real number.")
    if abs(n) > 1e12:
        raise ValidationError("That number is too large.")
    return n


def _parse_date(text):
    text = (text or "").strip()
    if not text:
        return None
    try:
        d = date.fromisoformat(text)
    except ValueError:
        raise ValidationError("Enter a date as YYYY-MM-DD.")
    if not EARLIEST_DATE <= d <= LATEST_DATE:
        raise ValidationError("That date is out of range.")
    return d


def _parse_moment(text, tz):
    """A date and time typed or picked on the page, read in the company's
    timezone. Returns (the moment in UTC, to the minute; the same wall-clock
    time as "YYYY-MM-DDTHH:MM"), or None when the box is empty.

    A time that happens twice, when clocks go back, is taken the first time
    (the earlier moment, so the clock never runs short). A time skipped when
    clocks go forward is read with the offset before the change, so 2:30 on
    that night is 3:30."""
    text = (text or "").strip()
    if not text:
        return None
    try:
        moment = datetime.fromisoformat(text)
    except ValueError:
        moment = None
    if moment is None or len(text) <= 10:
        raise ValidationError("Enter the date and the time it started, for example 2026-11-02 14:30.")
    if not EARLIEST_DATE <= moment.date() <= LATEST_DATE:
        raise ValidationError("That date is out of range.")
    if moment.tzinfo is not None:
        moment = moment.astimezone(tz).replace(tzinfo=None)
    moment = moment.replace(second=0, microsecond=0)
    utc = moment.replace(tzinfo=tz, fold=0).astimezone(timezone.utc)
    return utc, moment.strftime("%Y-%m-%dT%H:%M")


def _same_as_saved(rule, picked, saved, tz):
    """Whether the date box came back holding the saved date unchanged. An hour
    clock compares the wall-clock time the page showed, so a time that happens
    twice when clocks go back still matches the one that was saved."""
    if not saved:
        return False
    if counts_time(rule):
        moment = _stored_moment(saved, tz)
        return moment is not None and moment.strftime("%Y-%m-%dT%H:%M") == picked[1]
    return picked.isoformat() == saved


def _get_row(conn, org_id, industry_id, rule_key):
    return conn.execute(
        "SELECT * FROM items WHERE org_id = ? AND industry_id = ? AND rule_key = ?",
        (org_id, industry_id, rule_key),
    ).fetchone()


def _write(conn, org_id, industry_id, rule_key, user_id, **fields):
    names = ["value_num", "value_bool", "value_date", "limit_override", "warn_override"]
    existing = _get_row(conn, org_id, industry_id, rule_key)
    values = {n: (existing[n] if existing is not None else None) for n in names}
    values.update(fields)
    conn.execute(
        "INSERT INTO items (org_id, industry_id, rule_key, value_num, value_bool, value_date, limit_override,"
        " warn_override, updated_at, updated_by, updated_by_name) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
        " ON CONFLICT (org_id, industry_id, rule_key) DO UPDATE SET value_num = excluded.value_num,"
        " value_bool = excluded.value_bool, value_date = excluded.value_date,"
        " limit_override = excluded.limit_override, warn_override = excluded.warn_override,"
        " updated_at = excluded.updated_at, updated_by = excluded.updated_by,"
        " updated_by_name = excluded.updated_by_name",
        (org_id, industry_id, rule_key, values["value_num"], values["value_bool"], values["value_date"],
         values["limit_override"], values["warn_override"], now_iso(), user_id, user_name(conn, user_id)),
    )
    return _get_row(conn, org_id, industry_id, rule_key)


def apply_change(conn, org, user_id, industry_id, rule_key, action, form):
    """Applies one change from the industry page. Returns a confirmation message;
    raises ValidationError with a message for the person when the input is invalid."""
    rule = find_rule(industry_id, rule_key)
    if rule is None:
        raise LookupError(rule_key)
    org_id = org["id"]
    tz = ZoneInfo(org["timezone"])
    today = org_today(org)
    mode = date_mode(rule)
    timed = counts_time(rule)
    before = _get_row(conn, org_id, industry_id, rule_key)
    before_text = _describe(rule, before, tz)

    if action == "save":
        if rule.kind in ("required", "forbidden"):
            answer = form.get("answer")
            if answer not in ("yes", "no"):
                raise ValidationError("Choose Yes or No.")
            after = _write(conn, org_id, industry_id, rule_key, user_id, value_bool=1 if answer == "yes" else 0)
        else:
            # An hour clock's date box holds a date and a time ("when it started").
            picked = None if not mode else _parse_moment(form.get("date"), tz) if timed else _parse_date(form.get("date"))
            typed = (form.get("value") or "").strip()
            if picked is not None and typed:
                # The page fills the date box with the saved date, so it comes
                # back with every save. A number typed next to that unchanged
                # date is the new reading; it used to be dropped for the old date.
                saved = before["value_date"] if before is not None else None
                saved_num = before["value_num"] if before is not None else None
                if _same_as_saved(rule, picked, saved, tz):
                    picked = None
                elif saved_num is None or _parse_number(typed) != saved_num:
                    # The number box comes back filled with a saved number
                    # too; a date picked next to it, unchanged, is the new
                    # reading. Only a new number and a new date clash.
                    raise ValidationError("Enter a number or a date, not both.")
            if picked is not None and timed:
                if picked[0] > utcnow():
                    raise ValidationError("That time is in the future. Enter when it started.")
                after = _write(conn, org_id, industry_id, rule_key, user_id, value_date=iso(picked[0]), value_num=None)
            elif picked is not None:
                if mode == "since" and picked > today:
                    raise ValidationError("That date is in the future. Enter the date it last happened.")
                after = _write(conn, org_id, industry_id, rule_key, user_id, value_date=picked.isoformat(), value_num=None)
            else:
                number = _parse_number(form.get("value"))
                if number is None:
                    raise ValidationError("Enter a reading" + (" or pick when it started." if timed else
                                                               " or pick a date." if mode else "."))
                after = _write(conn, org_id, industry_id, rule_key, user_id, value_num=number, value_date=None)
        action_name, verb = "reading", "Saved"
    elif action == "done_today":
        if mode != "since":
            raise ValidationError("This check is not tracked by the date it was last done.")
        if timed:
            # An hour clock starts again now, to the minute.
            started = iso(utcnow().replace(second=0, microsecond=0))
            after = _write(conn, org_id, industry_id, rule_key, user_id, value_date=started, value_num=None)
            action_name, verb = "done", "Marked done now; the next cycle has started"
        else:
            after = _write(conn, org_id, industry_id, rule_key, user_id, value_date=today.isoformat(), value_num=None)
            action_name, verb = "done", "Marked done today; the next cycle has started"
    elif action == "clear":
        after = _write(conn, org_id, industry_id, rule_key, user_id, value_num=None, value_bool=None, value_date=None)
        action_name, verb = "cleared", "Reading cleared"
    elif action in ("override", "reset_override"):
        if not can_override(rule):
            raise ValidationError("This limit comes from the rule itself and cannot be changed.")
        if action == "reset_override":
            limit = warn = None
        else:
            limit = _parse_number(form.get("limit"))
            warn = _parse_number(form.get("warn"))
            if limit is None:
                raise ValidationError("Enter your limit.")
            if mode:
                # A limit counted from a date: kept to a real calendar. One that
                # ran past the year 9999 broke the company's pages and the
                # daily job (see MAX_DAYS).
                unit = date_unit(rule)
                for amount in (limit, warn):
                    if amount is not None and not 0 <= amount <= MAX_SPAN[unit]:
                        raise ValidationError(f"Enter a number of {unit.split()[-1]} between 0 and {MAX_SPAN[unit]}.")
            final_warn = rule.warn if warn is None else warn
            if final_warn is not None:
                if rule.kind == "max" and final_warn > limit:
                    raise ValidationError("The warning point must be at or below the limit.")
                if rule.kind == "min" and final_warn < limit:
                    raise ValidationError("The warning point must be at or above the minimum.")
        after = _write(conn, org_id, industry_id, rule_key, user_id, limit_override=limit, warn_override=warn)
        summary_before = _limits_text(rule, before)
        summary_after = _limits_text(rule, after)
        record_audit(conn, org_id, user_id, "limit", f"{rule.title}: limit {summary_before} → {summary_after}",
                     industry_id, rule_key, summary_before, summary_after)
        conn.commit()
        return "Your limit was saved." if action == "override" else "The default limit is back."
    else:
        raise ValidationError("Unknown action.")

    after_text = _describe(rule, after, tz)
    record_audit(conn, org_id, user_id, action_name, f"{rule.title}: {before_text} → {after_text}",
                 industry_id, rule_key, before_text, after_text)
    conn.commit()
    return f"{verb}."


def _limits_text(rule, row):
    eff = effective_rule(rule, row)
    warn = "" if eff.warn is None else f", warns at {format_quantity(eff.warn, rule.unit)}"
    return f"{format_quantity(eff.limit, rule.unit)}{warn}"


def to_json(states):
    """Plain data for exports and tests."""
    return json.dumps([{
        "industry": s.industry["brand"], "rule": s.rule.key, "level": s.level,
        "value": s.value, "due_date": s.due_date.isoformat() if s.due_date else None,
    } for s in states])
