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
_MINUTES_SINCE = re.compile(r"\bminutes? since\b", re.I)


def date_unit(rule):
    """What a date-tracked reading counts: 'days', 'months', 'calendar months'
    (whole months by the calendar, as in "the preceding 12 calendar months"),
    'years', 'business days' (Monday to Friday, not US federal holidays; the
    rules say "business days", "working days" or "work days"), 'hours' (real
    hours since a date and time, such as "Hours since becoming aware of a
    personal data breach") or 'minutes' (the same, in minutes). None when the
    reading is not tracked by date.

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
    if rule.unit == "min" and _MINUTES_SINCE.search(rule.input):
        return "minutes"
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
    day), not since a day: the hour and minute clocks."""
    return date_unit(rule) in ("hours", "minutes")


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


# ---------------------------------------------------------------------------
# The top checks of each industry
# ---------------------------------------------------------------------------
#
# Each industry page starts with its five most serious checks. They are chosen
# by one rule, from what the catalog itself says, in this order:
#
# 1. What a miss can bring, read from the check's "What a miss costs" text:
#    first the checks whose miss can stop the business or a person (a closure
#    or shutdown, an out-of-service order, a license suspended or revoked,
#    debarment, exclusion, a criminal charge); then those that bring fines or
#    penalties; then the rest (lawsuits, citations, lost work).
# 2. A check counted from a date (a deadline that runs out by itself) before
#    one that is answered or measured.
# 3. The catalog's own order.

TOP_COUNT = 5

STOPS_WORK = re.compile(
    r"out[- ]of[- ]service|(?<!window )\bclos(?:e|es|ed|ure|ures)\b|\bclosing (?:the|a|an|its|their)\b|\bshut|\bsuspen|"
    r"\brevo(?:ke|kes|ked|cation)|\bdisbar|\bdebar|\bcriminal|\bcrimes?\b|\bprison|\bjail|\bseiz|\bdetain|"
    r"\bdetention|\bgrounded|\bfelon|\bterminat|\bexclu(?:sion|ded) from|"
    r"\blos(?:s|e|es|ing) (?:of )?(?:the |its |their )?(?:\w+ )?(?:license|registration|permit|certification|"
    r"participation|access|accreditation)", re.I)
FINES = re.compile(r"\bfines?\b|\bpenalt|\bsanction|\bforfeit|\bcivil money|\bdisallow|\brefund|\brepay|\brestitution",
                   re.I)
SEVERITY_LABEL = {0: "Can stop the business", 1: "Fines or penalties", 2: "Other costs"}


def severity(rule):
    """0 when a miss can stop the business or a person, 1 when it brings fines
    or penalties, 2 otherwise: read from the rule's "What a miss costs" text."""
    if STOPS_WORK.search(rule.cost):
        return 0
    if FINES.search(rule.cost):
        return 1
    return 2


def _top_order(industry_id):
    rules = CATALOG[industry_id]
    return sorted(range(len(rules)), key=lambda n: (severity(rules[n]), date_mode(rules[n]) is None, n))


TOP_RANK = {(i, CATALOG[i][n].key): place
            for i in CATALOG for place, n in enumerate(_top_order(i)[:TOP_COUNT], 1)}


def top_checks(industry_id):
    """The industry's TOP_COUNT most serious rules, most serious first."""
    return [CATALOG[industry_id][n] for n in _top_order(industry_id)[:TOP_COUNT]]


def top_rank(industry_id, rule_key):
    """1 to TOP_COUNT for a top check, None for the others."""
    return TOP_RANK.get((industry_id, rule_key))


_CLAUSE = re.compile(r", and |; ")


def why_line(rule):
    """One line on why a check matters, cut from its own "What a miss costs"
    text and never added to: the first part of the sentence when that part
    is a whole clause of its own (no list running on past it) and already
    says what makes the check serious; otherwise the whole sentence."""
    cost = rule.cost.strip()
    first = _CLAUSE.split(cost, maxsplit=1)[0].rstrip(".")
    pattern = {0: STOPS_WORK, 1: FINES}.get(severity(rule))
    if (first != cost.rstrip(".") and "," not in first and pattern is not None and pattern.search(first)
            and len(first.split()) >= 4):
        return first + "."
    return cost
