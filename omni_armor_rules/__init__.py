# -*- coding: utf-8 -*-
"""
OmniArmor rule catalog: ten costly compliance risks for each of the 50
industries, 500 rules in all. CATALOG maps industry id -> list of Rule.
"""

from omni_armor_rules.rule import (  # noqa: F401
    BLOCKED, CLEARED, KINDS, LEVELS, WARNING, Rule, evaluate, validate_rules,
)
from omni_armor_rules import (
    group_1, group_2, group_3, group_4, group_5,
    group_6, group_7, group_8, group_9, group_10,
)

INDUSTRY_COUNT = 50

CATALOG = {}
for _group in (group_1, group_2, group_3, group_4, group_5,
               group_6, group_7, group_8, group_9, group_10):
    overlap = CATALOG.keys() & _group.RULES.keys()
    if overlap:
        raise ValueError(f"{_group.__name__} redefines industries {sorted(overlap)}")
    CATALOG.update(_group.RULES)

validate_rules(CATALOG, range(1, INDUSTRY_COUNT + 1))


def get_rule(module_id, rule_key):
    for rule in CATALOG[module_id]:
        if rule.key == rule_key:
            return rule
    raise KeyError(f"Industry {module_id} has no rule {rule_key!r}")
