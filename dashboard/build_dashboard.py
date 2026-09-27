# -*- coding: utf-8 -*-
"""Builds dashboard/index.html from template.html and the rule catalog.

Run after changing any rule:  python3 dashboard/build_dashboard.py
"""

import json
import os
import sys
from dataclasses import asdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from omni_armor_platform import MoonstoneThemeColors  # noqa: E402
from omni_armor_rules import CATALOG  # noqa: E402

PLACEHOLDER = "/*__CATALOG__*/[]"
TEMPLATE = os.path.join(HERE, "template.html")
OUTPUT = os.path.join(HERE, "index.html")


def catalog_data():
    industries = []
    for module_id, info in sorted(MoonstoneThemeColors.INDUSTRIES.items()):
        brand, _, sector = info["name"].partition(" (")
        industries.append({
            "id": module_id,
            "brand": brand,
            "sector": sector.rstrip(")"),
            "color": info["color"],
            "hex": info["hex"],
            "rules": [asdict(r) for r in CATALOG[module_id]],
        })
    return industries


def render():
    with open(TEMPLATE, encoding="utf-8") as f:
        template = f.read()
    if template.count(PLACEHOLDER) != 1:
        raise ValueError(f"{TEMPLATE} must contain {PLACEHOLDER} exactly once")
    # "</" inside the JSON would end the <script> element early.
    data = json.dumps(catalog_data(), ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    return template.replace(PLACEHOLDER, data)


def build():
    with open(OUTPUT, "w", encoding="utf-8") as f:
        f.write(render())
    return OUTPUT


if __name__ == "__main__":
    print(f"Wrote {build()}")
