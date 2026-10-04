# -*- coding: utf-8 -*-
"""Question banks for the Future Owner Academy's newer worlds.

Each module defines WORLDS, a list of dicts:
    key, title, tagline, icon   how the world appears on the map
    cards       [(title, text)] lesson cards shown on stage 1
    questions   [(question, best, wrong, wrong, why, level)] with level 1 (easy) to 3 (hard)
    facts       [(statement, is_true, why)] true-or-false questions

expansions.py adds more words, pro-talk situations and scenarios to the
original worlds. tests/test_academy_bank.py checks every entry.
"""

import importlib

UNIT_MODULES = ["money", "growth", "operations", "mindset", "trust", "bigpicture", "champion"]


def load_worlds():
    worlds = []
    for name in UNIT_MODULES:
        try:
            module = importlib.import_module(f"{__name__}.{name}")
        except ModuleNotFoundError:
            continue
        for w in module.WORLDS:
            worlds.append(dict(w, unit=name))
    return worlds


def load_expansions():
    try:
        return importlib.import_module(f"{__name__}.expansions")
    except ModuleNotFoundError:
        return None
