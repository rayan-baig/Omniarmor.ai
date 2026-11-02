# -*- coding: utf-8 -*-
"""The 50 industries and 500 rules, as the web app uses them."""

import re
from dataclasses import replace

from omni_armor_platform import MoonstoneThemeColors
from omni_armor_rules import CATALOG, get_rule

INDUSTRIES = {}
for _id, _info in sorted(MoonstoneThemeColors.INDUSTRIES.items()):
    _brand, _, _sector = _info["name"].partition(" (")
    INDUSTRIES[_id] = {"id": _id, "brand": _brand, "sector": _sector.rstrip(")")}

_SINCE = re.compile(r"\bdays? since\b", re.I)
_UNTIL = re.compile(r"\bdays? until\b", re.I)
_MONTHS_SINCE = re.compile(r"\bmonths? since\b", re.I)
_YEARS_SINCE = re.compile(r"\byears? since\b", re.I)
_HOURS_SINCE = re.compile(r"\bhours? since\b", re.I)


def date_unit(rule):
    """What a date-tracked reading counts: 'days', 'months', 'calendar months'
    (whole months by the calendar, as in "the preceding 12 calendar months"),
    'years', 'business days' (Monday to Friday, not US federal holidays; the
    rules say "business days", "working days" or "work days") or 'hours'
    (real hours since a date and time, such as "Hours since becoming aware of
    a personal data breach"). None when the reading is not tracked by date.

    Only "hours since" counts by the clock: "Hours driven since..." or "Hours
    in service since..." are hours of driving or flying, not time passed."""
    if rule.kind not in ("max", "min"):
        return None
    if rule.unit in ("days", "calendar days"):
        return "days" if _SINCE.search(rule.input) or _UNTIL.search(rule.input) else None
    if rule.unit == "months" and _MONTHS_SINCE.search(rule.input):
        return "calendar months" if re.search(r"\bcalendar months? since\b", rule.input, re.I) else "months"
    if rule.unit == "years" and _YEARS_SINCE.search(rule.input):
        return "years"
    if rule.unit in ("business days", "working days", "work days") and \
            re.search(r"\b(business|working|work) days? since\b", rule.input, re.I):
        return "business days"
    if rule.unit == "h" and _HOURS_SINCE.search(rule.input):
        return "hours"
    return None


def date_mode(rule):
    """'since' when the reading counts the time since an event, 'until' when it
    counts days until a due date, None when the reading is not tracked by date.

    Months and years count too: a reading typed as "3 months" never grew, so a
    yearly review stayed Cleared forever. A date counts up by itself."""
    unit = date_unit(rule)
    if unit is None:
        return None
    if unit == "days" and not _SINCE.search(rule.input):
        return "until"
    return "since"


_DAY_ONE = re.compile(r"\bas day 1\b", re.I)


def counts_first_day(rule):
    """Whether a days-since check counts the starting day itself as day 1, as
    the Food Code's 7-day date marking does (3-501.17(A)): food made on Monday
    is on day 7 on Sunday, the last day it may be kept."""
    return date_mode(rule) == "since" and date_unit(rule) == "days" and bool(_DAY_ONE.search(rule.input))


def counts_time(rule):
    """Whether a check counts the time since a moment (a date and a time of
    day), not since a day: the hour clocks."""
    return date_unit(rule) == "hours"


def rules_for(industry_id):
    return CATALOG[industry_id]


def find_rule(industry_id, rule_key):
    """Returns the rule or None, so routes can answer 404 instead of crashing."""
    if industry_id not in CATALOG:
        return None
    try:
        return get_rule(industry_id, rule_key)
    except KeyError:
        return None


def can_override(rule):
    """Only policy limits (no single legal number) can be changed per company."""
    return rule.policy and rule.kind in ("max", "min")


def effective_rule(rule, row):
    if row is None or not can_override(rule):
        return rule
    limit, warn = row["limit_override"], row["warn_override"]
    if limit is None and warn is None:
        return rule
    return replace(rule, limit=rule.limit if limit is None else limit, warn=rule.warn if warn is None else warn)
