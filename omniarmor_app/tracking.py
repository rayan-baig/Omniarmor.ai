# -*- coding: utf-8 -*-
"""Current status of every rule for a company, and the changes people make to it.

Readings are stored once and recomputed every day:
    - date-tracked rules store a date ("last done" or "due on"); the day count
      is worked out from today's date in the company's timezone
    - other number rules store a number; yes/no rules store a yes or no
Every change is written to the audit trail with who made it and when.
"""

import json
import math
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from omni_armor_rules import evaluate
from omni_armor_rules.rule import _fmt as format_quantity

from .catalog import INDUSTRIES, can_override, date_mode, effective_rule, find_rule, rules_for
from .db import now_iso, record_audit

LEVEL_ORDER = {"BLOCKED": 0, "WARNING": 1, "NONE": 2, "CLEARED": 3}
LEVEL_LABEL = {"BLOCKED": "Blocked", "WARNING": "Warning", "CLEARED": "Cleared", "NONE": "No reading"}
EARLIEST_DATE = date(1950, 1, 1)
LATEST_DATE = date(2150, 12, 31)


class ValidationError(ValueError):
    """A reading or setting a person entered that cannot be saved; the message says why."""


def org_today(org):
    return datetime.now(ZoneInfo(org["timezone"])).date()


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
        return None if self.due_date is None else (self.due_date - self.today).days

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


def _whole_days(value):
    return int(math.floor(value))


def compute_state(industry_id, rule, row, today):
    mode = date_mode(rule)
    eff = effective_rule(rule, row)
    value = None
    value_date = None
    if row is not None:
        if rule.kind in ("required", "forbidden"):
            value = None if row["value_bool"] is None else bool(row["value_bool"])
        elif mode and row["value_date"]:
            value_date = date.fromisoformat(row["value_date"])
            value = (today - value_date).days if mode == "since" else (value_date - today).days
        elif row["value_num"] is not None:
            value = row["value_num"]
            if isinstance(value, float) and value.is_integer():
                value = int(value)
    if value is None:
        level, status, message = "NONE", "NO READING", "No reading yet."
    else:
        level, status, message = evaluate(eff, value)

    due_date = warn_date = None
    if value_date is not None:
        if mode == "since":
            due_date = value_date + timedelta(days=_whole_days(eff.limit))
            if eff.warn is not None:
                warn_date = value_date + timedelta(days=_whole_days(eff.warn))
        else:
            due_date = value_date - timedelta(days=_whole_days(eff.limit))
            if eff.warn is not None:
                warn_date = value_date - timedelta(days=_whole_days(eff.warn))
    return ItemState(
        industry_id=industry_id, rule=rule, effective=eff, mode=mode, value=value, level=level,
        status=status, message=message, value_date=value_date, due_date=due_date, warn_date=warn_date,
        today=today,
        updated_at=row["updated_at"] if row is not None else None,
        updated_by=row["updated_by_name"] if row is not None else None,
    )


def org_industry_ids(conn, org_id):
    rows = conn.execute("SELECT industry_id FROM org_industries WHERE org_id = ? ORDER BY industry_id", (org_id,))
    return [r["industry_id"] for r in rows if r["industry_id"] in INDUSTRIES]


def _load_rows(conn, org_id):
    rows = conn.execute(
        "SELECT items.*, users.name AS updated_by_name FROM items"
        " LEFT JOIN users ON users.id = items.updated_by WHERE items.org_id = ?",
        (org_id,),
    )
    return {(r["industry_id"], r["rule_key"]): r for r in rows}


def states_for_org(conn, org, industry_ids=None, today=None):
    today = today or org_today(org)
    ids = org_industry_ids(conn, org["id"]) if industry_ids is None else industry_ids
    rows = _load_rows(conn, org["id"])
    return [compute_state(i, rule, rows.get((i, rule.key)), today) for i in ids for rule in rules_for(i)]


def tally(states):
    counts = {level: 0 for level in LEVEL_LABEL}
    for s in states:
        counts[s.level] += 1
    return counts


# ---------------------------------------------------------------------------
# Changes
# ---------------------------------------------------------------------------

def _describe(rule, row):
    if row is None:
        return "no reading"
    if rule.kind in ("required", "forbidden"):
        return "no reading" if row["value_bool"] is None else ("Yes" if row["value_bool"] else "No")
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
        " warn_override, updated_at, updated_by) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
        " ON CONFLICT (org_id, industry_id, rule_key) DO UPDATE SET value_num = excluded.value_num,"
        " value_bool = excluded.value_bool, value_date = excluded.value_date,"
        " limit_override = excluded.limit_override, warn_override = excluded.warn_override,"
        " updated_at = excluded.updated_at, updated_by = excluded.updated_by",
        (org_id, industry_id, rule_key, values["value_num"], values["value_bool"], values["value_date"],
         values["limit_override"], values["warn_override"], now_iso(), user_id),
    )
    return _get_row(conn, org_id, industry_id, rule_key)


def apply_change(conn, org, user_id, industry_id, rule_key, action, form):
    """Applies one change from the industry page. Returns a confirmation message;
    raises ValidationError with a message for the person when the input is invalid."""
    rule = find_rule(industry_id, rule_key)
    if rule is None:
        raise LookupError(rule_key)
    org_id = org["id"]
    today = org_today(org)
    mode = date_mode(rule)
    before = _get_row(conn, org_id, industry_id, rule_key)
    before_text = _describe(rule, before)

    if action == "save":
        if rule.kind in ("required", "forbidden"):
            answer = form.get("answer")
            if answer not in ("yes", "no"):
                raise ValidationError("Choose Yes or No.")
            after = _write(conn, org_id, industry_id, rule_key, user_id, value_bool=1 if answer == "yes" else 0)
        else:
            picked = _parse_date(form.get("date")) if mode else None
            if picked is not None:
                if mode == "since" and picked > today:
                    raise ValidationError("That date is in the future. Enter the date it last happened.")
                after = _write(conn, org_id, industry_id, rule_key, user_id, value_date=picked.isoformat(), value_num=None)
            else:
                number = _parse_number(form.get("value"))
                if number is None:
                    raise ValidationError("Enter a reading" + (" or pick a date." if mode else "."))
                after = _write(conn, org_id, industry_id, rule_key, user_id, value_num=number, value_date=None)
        action_name, verb = "reading", "Saved"
    elif action == "done_today":
        if mode != "since":
            raise ValidationError("This check is not tracked by the date it was last done.")
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

    after_text = _describe(rule, after)
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
