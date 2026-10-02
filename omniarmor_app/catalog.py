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


def date_mode(rule):
    """'since' when the reading counts days since an event, 'until' when it counts
    days until a due date, None when the reading is not tracked by date."""
    if rule.kind not in ("max", "min") or rule.unit not in ("days", "calendar days"):
        return None
    if _SINCE.search(rule.input):
        return "since"
    if _UNTIL.search(rule.input):
        return "until"
    return None


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
