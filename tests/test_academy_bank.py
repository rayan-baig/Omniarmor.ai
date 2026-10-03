"""Checks every entry in the Academy's question banks."""
import importlib
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from omniarmor_app.academy_bank import UNIT_MODULES  # noqa: E402

ICONS = {"tag", "piggy", "bank", "card", "megaphone", "badge", "handshake", "wifi", "gear", "box", "chart",
         "hardhat", "target", "clock", "bulb", "brain", "compass", "scroll", "receipt", "lock", "flag", "map",
         "graph", "globe", "leaf", "calculator"}
ORIGINAL_KEYS = {"company", "words", "rules", "lights", "calendar", "money", "talk", "team", "ownit", "grit",
                 "respect", "hiring", "toughcalls", "customers", "compete", "moves", "final"}
BANNED = ["{", "}", "“", "”", "‘", "’", "—", "all of the above", "none of the above"]


def text_problems(value, limit, where):
    problems = []
    if not isinstance(value, str) or not value.strip():
        return [f"{where}: empty"]
    if value != value.strip():
        problems.append(f"{where}: extra spaces")
    if len(value) > limit:
        problems.append(f"{where}: {len(value)} chars (max {limit})")
    for bad in BANNED:
        if bad in value.lower():
            problems.append(f"{where}: contains {bad!r}")
    try:
        value.encode("ascii")
    except UnicodeEncodeError:
        problems.append(f"{where}: non-ASCII character")
    return problems


def check_scenario(item, where, with_level=True):
    problems = []
    size = 6 if with_level else 5
    if not isinstance(item, tuple) or len(item) != size:
        return [f"{where}: needs a {size}-tuple"]
    q, best, w1, w2, why = item[:5]
    problems += text_problems(q, 170, f"{where} question")
    for i, option in enumerate((best, w1, w2)):
        problems += text_problems(option, 120, f"{where} option {i}")
    problems += text_problems(why, 240, f"{where} why")
    if len({str(x).strip().lower() for x in (best, w1, w2)}) != 3:
        problems.append(f"{where}: options must all be different")
    if with_level and item[5] not in (1, 2, 3):
        problems.append(f"{where}: level must be 1, 2 or 3")
    return problems


class TestWorldBanks(unittest.TestCase):
    def test_every_world(self):
        seen_keys, problems, total = set(), [], 0
        for name in UNIT_MODULES:
            try:
                module = importlib.import_module(f"omniarmor_app.academy_bank.{name}")
            except ModuleNotFoundError:
                continue
            for w in module.WORLDS:
                key = w.get("key", "?")
                where = f"{name}.{key}"
                total += 1
                if key in seen_keys or key in ORIGINAL_KEYS:
                    problems.append(f"{where}: key already used")
                seen_keys.add(key)
                for field in ("title", "tagline"):
                    problems += text_problems(w.get(field, ""), 40, f"{where} {field}")
                if w.get("icon") not in ICONS:
                    problems.append(f"{where}: icon {w.get('icon')!r} not allowed")
                cards = w.get("cards", [])
                if not 4 <= len(cards) <= 6:
                    problems.append(f"{where}: needs 4 to 6 cards")
                for i, card in enumerate(cards):
                    problems += text_problems(card[0], 32, f"{where} card {i} title")
                    problems += text_problems(card[1], 240, f"{where} card {i} text")
                questions = w.get("questions", [])
                if len(questions) < 30:
                    problems.append(f"{where}: {len(questions)} questions (need 30+)")
                for i, item in enumerate(questions):
                    problems += check_scenario(item, f"{where} q{i}")
                levels = [q[5] for q in questions if isinstance(q, tuple) and len(q) == 6]
                for level in (1, 2, 3):
                    if levels.count(level) < 8:
                        problems.append(f"{where}: needs 8+ level-{level} questions")
                prompts = [q[0].lower() for q in questions if isinstance(q, tuple)]
                if len(set(prompts)) != len(prompts):
                    problems.append(f"{where}: repeated question")
                facts = w.get("facts", [])
                if len(facts) < 10:
                    problems.append(f"{where}: {len(facts)} facts (need 10+)")
                for i, fact in enumerate(facts):
                    if not isinstance(fact, tuple) or len(fact) != 3 or not isinstance(fact[1], bool):
                        problems.append(f"{where} fact {i}: needs (statement, True/False, why)")
                        continue
                    problems += text_problems(fact[0], 170, f"{where} fact {i}")
                    problems += text_problems(fact[2], 240, f"{where} fact {i} why")
                truths = [f[1] for f in facts if isinstance(f, tuple) and len(f) == 3]
                if truths.count(True) < 3 or truths.count(False) < 3:
                    problems.append(f"{where}: needs 3+ true and 3+ false facts")
        self.assertEqual(problems, [], "\n".join(problems[:60]))


class TestExpansions(unittest.TestCase):
    def test_expansions(self):
        try:
            ex = importlib.import_module("omniarmor_app.academy_bank.expansions")
        except ModuleNotFoundError:
            self.skipTest("no expansions yet")
        from omniarmor_app import academy

        def original(merged, more):
            """academy.py appends the expansions to its own lists; compare against the originals."""
            more = list(more)
            return merged[:len(merged) - len(more)] if more and merged[-len(more):] == more else merged
        problems = []
        words = [w.lower() for w, _ in original(academy.GLOSSARY, ex.GLOSSARY_MORE)] + [w.lower() for w, _ in ex.GLOSSARY_MORE]
        if len(ex.GLOSSARY_MORE) < 130:
            problems.append(f"GLOSSARY_MORE has {len(ex.GLOSSARY_MORE)} (need 130+)")
        if len(set(words)) != len(words):
            problems.append("GLOSSARY_MORE repeats a word")
        for i, (word, meaning) in enumerate(ex.GLOSSARY_MORE):
            problems += text_problems(word, 30, f"glossary {i} word")
            problems += text_problems(meaning, 140, f"glossary {i} meaning")
        pools = {"PRO_TALK_MORE": (original(academy.PRO_TALK, getattr(ex, "PRO_TALK_MORE", [])), 30)}
        for name in ("OWN_IT", "GRIT", "RESPECT", "HIRING", "TOUGH_CALLS", "CUSTOMERS", "COMPETE", "MOVES"):
            pools[f"{name}_MORE"] = (original(getattr(academy, name), getattr(ex, f"{name}_MORE", [])), 19)
        for name, (original, need) in pools.items():
            items = getattr(ex, name, [])
            if len(items) < need:
                problems.append(f"{name} has {len(items)} (need {need}+)")
            for i, item in enumerate(items):
                problems += check_scenario(item, f"{name}[{i}]", with_level=False)
            prompts = [o[0].lower() for o in original] + [o[0].lower() for o in items if isinstance(o, tuple)]
            if len(set(prompts)) != len(prompts):
                problems.append(f"{name}: repeats a situation")
        self.assertEqual(problems, [], "\n".join(problems[:60]))


if __name__ == "__main__":
    unittest.main()
