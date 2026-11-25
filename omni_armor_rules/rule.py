# -*- coding: utf-8 -*-
"""
Rule format for the OmniArmor catalog.

Each industry has ten rules: the compliance failures that cost businesses in
that industry the most money through fines, shutdowns, lawsuits or lost
revenue. Every rule is data, checked by one engine (evaluate) so all 250
behave the same way.

Kinds:
    max       value must not exceed limit; WARNING once value >= warn
    min       value must not fall below limit; WARNING once value <= warn
    required  value must be True (a control that has to be in place)
    forbidden value must be False (a condition that must not happen)
"""

import math
import re
from dataclasses import dataclass
from typing import Optional, Union

CLEARED = "CLEARED"
WARNING = "WARNING"
BLOCKED = "BLOCKED"
LEVELS = (CLEARED, WARNING, BLOCKED)

KINDS = ("max", "min", "required", "forbidden")


@dataclass(frozen=True)
class Rule:
    key: str        # snake_case, unique within its industry
    title: str      # short name, at most 40 characters
    cost: str       # how breaking it costs money, one sentence
    citation: str   # the regulation or standard
    kind: str       # one of KINDS
    input: str      # what the business enters; a yes/no question for required/forbidden
    action: str     # what to do when the rule is broken
    unit: str = ""  # unit label for max/min, e.g. "days", "°F"
    limit: Optional[float] = None
    warn: Optional[float] = None
    policy: bool = False   # True when the limit is an industry standard or policy, not law
    sample: Union[float, bool, None] = None  # realistic example input for demos
    method: Optional[str] = None  # OmniArmorPortal method with a more detailed check, if any


def _fmt(value, unit):
    if unit == "$" and isinstance(value, float) and not value.is_integer():
        return f"${value:,.2f}"     # money keeps its cents: $15.50, not $15.5
    number = f"{value:,.2f}".rstrip("0").rstrip(".") if isinstance(value, float) else f"{value:,}"
    if not unit:
        return number
    if unit.startswith("°") or unit == "%":
        return f"{number}{unit}"
    if unit == "$":
        return f"${number}"
    return f"{number} {unit}"


# A time limit said as one word before "limit" or "minimum" (1.26.0): "the 7-day limit", "the 3-business-day
# limit", "the 2-hour limit", not "the 7 days limit". Other units keep their usual form ("the 41°F limit").
_LIMIT_UNITS = {"days": "day", "business days": "business-day", "working days": "working-day", "work days": "work-day",
                "months": "month", "years": "year", "weeks": "week", "h": "hour", "min": "minute"}


def limit_words(value, unit):
    """A limit as it is said before "limit" or "minimum": "7-day", "3-business-day", "41°F"."""
    word = _LIMIT_UNITS.get(unit)
    if word is None:
        return _fmt(value, unit)
    return f"{_fmt(value, '')}-{word}"


def evaluate(rule, value):
    """Returns (level, status, message) for one input value."""
    source = " (policy setting)" if rule.policy else ""
    if rule.kind in ("required", "forbidden"):
        if not isinstance(value, bool):
            raise TypeError(f"{rule.key} expects True or False, got {value!r}")
        broken = (not value) if rule.kind == "required" else value
        if broken:
            return BLOCKED, "VIOLATION", f"{rule.title}: {rule.action}"
        return CLEARED, "CLEARED", f"{rule.title}: in compliance{source}."

    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{rule.key} expects a number, got {value!r}")
    if not math.isfinite(value):
        raise ValueError(f"{rule.key} expects a finite number, got {value!r}")
    limit = limit_words(rule.limit, rule.unit)
    shown = _fmt(value, rule.unit)
    if rule.kind == "max":
        if value > rule.limit:
            return BLOCKED, "OVER LIMIT", f"{shown} is over the {limit} limit{source}. {rule.action}"
        if rule.warn is not None and value >= rule.warn:
            if value == rule.limit:
                return WARNING, "NEAR LIMIT", f"{shown} is close to the {limit} limit: it is at the limit now{source}."
            return WARNING, "NEAR LIMIT", f"{shown} is close to the {limit} limit{_warns(rule, 'from')}."
        return CLEARED, "CLEARED", f"{shown} is within the {limit} limit{source}."
    if value < rule.limit and rule.limit == 0 and _counts_down(rule):
        late = -value
        unit = rule.unit[:-1] if late == 1 and rule.unit.endswith("s") else rule.unit
        return BLOCKED, "BELOW MINIMUM", f"{_fmt(late, unit)} past the deadline{source}. {rule.action}"
    if value < rule.limit:
        return BLOCKED, "BELOW MINIMUM", f"{shown} is below the {limit} minimum{source}. {rule.action}"
    if rule.warn is not None and value <= rule.warn:
        if rule.limit == 0 and _counts_down(rule):
            # A countdown to a deadline (days left on a license): "41 days is
            # close to the 0 days minimum" read as nonsense.
            return WARNING, "NEAR MINIMUM", (f"{shown} left before the deadline: plan it now, as the warning starts at"
                                             f" {_fmt(rule.warn, rule.unit)} left{source}.")
        if value == rule.limit:
            return WARNING, "NEAR MINIMUM", f"{shown} is exactly the {limit} minimum, with no room to spare{source}."
        return WARNING, "NEAR MINIMUM", f"{shown} is close to the {limit} minimum{_warns(rule, 'at')}."
    if rule.limit == 0 and _counts_down(rule):
        return CLEARED, "CLEARED", f"{shown} left before the deadline{source}."
    return CLEARED, "CLEARED", f"{shown} meets the {limit} minimum{source}."


_TIME_UNITS = ("day", "days", "business days", "week", "weeks", "month", "months", "year", "years", "h", "min")


def _counts_down(rule):
    """Whether a minimum of 0 is a countdown: the time left before a deadline."""
    return rule.kind == "min" and rule.unit in _TIME_UNITS


def _warns(rule, word):
    """ (it warns from 6 days)": where the warning starts, when that isn't the
    limit itself, with "policy setting" in the same brackets for a policy limit."""
    policy = "policy setting" if rule.policy else ""
    if rule.warn is None or rule.warn == rule.limit:
        return f" ({policy})" if policy else ""
    more = "or more" if rule.kind == "max" else "or less"
    warns = f"it warns {word} {_fmt(rule.warn, rule.unit)}{' ' + more if word == 'at' else ''}"
    return f" ({warns}; {policy})" if policy else f" ({warns})"


_KEY = re.compile(r"^[a-z][a-z0-9_]*$")


def validate_rules(rules_by_industry, expected_ids):
    """Raises ValueError listing every problem in a group of industries."""
    problems = []
    if sorted(rules_by_industry) != sorted(expected_ids):
        problems.append(f"industry ids {sorted(rules_by_industry)} != expected {sorted(expected_ids)}")
    for industry_id, rules in rules_by_industry.items():
        where = f"industry {industry_id}"
        if len(rules) != 10:
            problems.append(f"{where}: {len(rules)} rules, expected 10")
        keys = [r.key for r in rules]
        if len(set(keys)) != len(keys):
            problems.append(f"{where}: duplicate keys")
        for r in rules:
            at = f"{where}/{r.key}"
            if not isinstance(r, Rule):
                problems.append(f"{at}: not a Rule")
                continue
            if not _KEY.match(r.key):
                problems.append(f"{at}: key must be snake_case")
            if r.kind not in KINDS:
                problems.append(f"{at}: kind {r.kind!r} not in {KINDS}")
            if len(r.title) > 40:
                problems.append(f"{at}: title over 40 characters")
            if not (r.cost and r.citation and r.input and r.action):
                problems.append(f"{at}: cost, citation, input and action are required")
            if len(r.cost) > 170:
                problems.append(f"{at}: cost over 170 characters")
            if len(r.action) > 150:
                problems.append(f"{at}: action over 150 characters")
            if r.kind in ("max", "min"):
                if not isinstance(r.limit, (int, float)) or isinstance(r.limit, bool):
                    problems.append(f"{at}: numeric limit required")
                elif r.warn is not None:
                    if r.kind == "max" and r.warn > r.limit:
                        problems.append(f"{at}: max rule warn must be <= limit")
                    if r.kind == "min" and r.warn < r.limit:
                        problems.append(f"{at}: min rule warn must be >= limit")
                if not isinstance(r.sample, (int, float)) or isinstance(r.sample, bool):
                    problems.append(f"{at}: numeric sample required")
            else:
                if r.limit is not None or r.warn is not None or r.unit:
                    problems.append(f"{at}: yes/no rules take no limit, warn or unit")
                if not isinstance(r.sample, bool):
                    problems.append(f"{at}: sample must be True or False")
    if problems:
        raise ValueError("Rule catalog problems:\n  " + "\n  ".join(problems))
