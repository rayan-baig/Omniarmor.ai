"""The Academy's quizzes can't be passed by guessing from their shape, and a
world never asks the same question twice.

tests/test_academy_bank.py checks each written question bank on its own.
This checks the lessons kids actually get, on every track (the families'
four and the Classroom track), every world, the Owner's Challenge and the
Rule Quests:

- every world is a fixed set of questions: no question comes back in a later
  lesson of the same world, and the level count is the real number of
  lessons, the same for every company;
- every question has two or more different options and one right answer;
- the right answer is the longest option, or the shortest, about as often as
  chance would make it, tested statistically across every question;
- always picking the longest (or shortest) answer passes no more lessons
  than guessing at random would;
- the right answer moves around between slots, and true-or-false questions
  are true about as often as they are false.

The right answers still never reach the page (tests/test_quiz_checks.py).
"""

import collections
import functools
import math
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from omniarmor_app import academy  # noqa: E402
from omniarmor_app.catalog import INDUSTRIES  # noqa: E402

COMPANY = ("Acme Logistics", (1, 18))
SEEDS = 6
MAX_Z = 2.0                 # how far above chance a shape rule may be, in standard deviations
MAX_WORLD_SHARE = 0.5       # in any one world with enough questions
MIN_WORLD_QUESTIONS = 12
MIN_SLOT_SHARE = 0.2        # each of three slots gets at least this share of the right answers
TRUE_SHARE = (0.3, 0.7)


def _numbers_only(q):
    """Options that are all amounts or counts: their length says nothing."""
    return all(any(ch.isdigit() for ch in option) for option in q.options)


def _pool(t, w):
    if t.key == academy.CLASSROOM_KEY:
        return academy.classroom_pool(w.number)
    return academy.family_pool(t, w.number, *COMPANY)


def _lesson(t, w, stage):
    """A lesson's questions, in their fixed order (no shuffle)."""
    if t.key == academy.CLASSROOM_KEY:
        size = academy.LESSON_QUESTIONS
        return academy.classroom_pool(w.number)[(stage - 1) * size:stage * size]
    if w.kind == "industry":
        return academy._industry_lesson(t, w.industry_id, stage)
    if w.kind == "final":
        size = t.final_questions
        return academy._final_pool(t.key, *COMPANY)[(stage - 1) * size:stage * size]
    size = t.min_questions
    return academy.family_pool(t, w.number, *COMPANY)[(stage - 1) * size:stage * size]


def _lessons(t):
    for w in t.worlds:
        if t.key == academy.CLASSROOM_KEY and w.kind == "final":
            continue  # the Class Challenge draws from the whole track each time
        for stage in range(1, t.stages(w) + 1):
            yield w, stage


@functools.lru_cache(maxsize=None)
def distinct_questions():
    """{(track kind, world key, prompt): question} for every written-out
    choice question a lesson can ask, the Classroom's and the families'."""
    found = {}
    for t in academy.ALL_TRACKS:
        side = "class" if t.key == academy.CLASSROOM_KEY else "family"
        for w, stage in _lessons(t):
            for q in _lesson(t, w, stage):
                found[(side, w.key, q.prompt)] = q
    return found


@functools.lru_cache(maxsize=None)
def generated():
    """{world key: [questions]}: every lesson of every track and world, as
    quizzes shuffled from SEEDS seeds."""
    found = collections.defaultdict(list)
    for t in academy.ALL_TRACKS:
        for w, stage in _lessons(t):
            for seed in range(SEEDS):
                found[w.key] += academy.quiz(t, w.number, stage, COMPANY[0], COMPANY[1], f"fair-{seed}")
    return found


def _shape_hits(questions, pick):
    """(hits, expected by chance, variance): how often the option `pick`
    (max or min) by length is the right one, over worded choice questions."""
    hits = expected = variance = 0
    for q in questions:
        if q.kind != "choice" or _numbers_only(q):
            continue
        lengths = [len(o) for o in q.options]
        target = pick(lengths)
        hits += lengths[q.answer] == target and lengths.count(target) == 1
        p = 1 / len(q.options)
        expected += p
        variance += p * (1 - p)
    return hits, expected, variance


def _strategy_score(q, pick):
    lengths = [len(o) for o in q.options]
    target = pick(lengths)
    return int(lengths.count(target) == 1 and lengths[q.answer] == target)


def _guess_pass_chance(questions, needed):
    """The exact chance of passing by picking at random: P(right >= needed)."""
    dist = [1.0]
    for q in questions:
        p = 1 / len(q.options)
        nxt = [0.0] * (len(dist) + 1)
        for right, chance in enumerate(dist):
            nxt[right] += chance * (1 - p)
            nxt[right + 1] += chance * p
        dist = nxt
    return sum(dist[needed:])


class TestNoRepeatsAndHonestCounts(unittest.TestCase):
    def test_no_question_comes_back_within_a_world(self):
        problems = []
        for t in academy.ALL_TRACKS:
            for w in t.topic_worlds:
                prompts = [q.prompt for q in _pool(t, w)]
                repeats = [p for p, n in collections.Counter(prompts).items() if n > 1]
                if repeats:
                    problems.append(f"{t.name}, {w.title}: {repeats[:2]}")
            for w in academy.INDUSTRY_WORLDS if t.rule_quests else ():
                prompts = [q.prompt for s in range(1, t.stages(w) + 1) for q in _lesson(t, w, s)]
                if len(set(prompts)) != len(prompts):
                    problems.append(f"{t.name}, {w.title}: a question in two lessons")
            if t.key != academy.CLASSROOM_KEY:
                final = [q.prompt for q in academy._final_pool(t.key, *COMPANY)]
                if len(set(final)) != len(final):
                    problems.append(f"{t.name}, the Owner's Challenge repeats a question")
        self.assertEqual(problems, [], "\n".join(problems[:20]))

    def test_every_lesson_asks_its_own_questions(self):
        """Fourteen lessons used to ask 16 different questions between them."""
        for t in academy.TRACK_LIST:
            w = academy.world(1)
            seen = collections.Counter()
            for stage in range(1, t.stages(w) + 1):
                for q in academy.quiz(t, 1, stage, *COMPANY, seed=f"repeat-{stage}"):
                    seen[q.prompt] += 1
            self.assertEqual(max(seen.values()), 1, t.name)
            self.assertEqual(sum(seen.values()), t.stages(w) * t.min_questions)

    def test_level_counts_are_the_real_lessons(self):
        for t in academy.TRACK_LIST:
            lessons = 0
            for w in t.topic_worlds:
                pool = academy.family_pool(t, w.number, *COMPANY)
                self.assertEqual(len(pool) % t.min_questions, 0, (t.name, w.title))
                self.assertEqual(t.stages(w), len(pool) // t.min_questions, (t.name, w.title))
                self.assertGreaterEqual(t.stages(w), 2, (t.name, w.title, "a world needs at least two lessons"))
                lessons += t.stages(w)
            rule_lessons = sum(len(academy.CATALOG[w.industry_id]) for w in academy.INDUSTRY_WORLDS)
            self.assertEqual(t.total, lessons + t.final_stages + rule_lessons, t.name)
            self.assertLess(t.total, 2000, t.name)
            final = academy._final_pool(t.key, *COMPANY)
            self.assertEqual(len(final), t.final_stages * t.final_questions, t.name)

    def test_every_company_gets_the_same_level_counts(self):
        """Worlds built from the company's own rules have as many questions
        for every industry, so the pages' level counts are true for all."""
        problems = []
        for t in academy.TRACK_LIST:
            for number in (1, 3, 4, 5, 6):
                for industry_id in INDUSTRIES:
                    pool = academy.family_pool(t, number, "Sample Shop", (industry_id,))
                    if len(pool) // t.min_questions != t.stages(academy.world(number)):
                        problems.append(f"{t.name}, world {number}, industry {industry_id}: {len(pool)} questions")
                    if len({q.prompt for q in pool}) != len(pool):
                        problems.append(f"{t.name}, world {number}, industry {industry_id}: a repeat")
        self.assertEqual(problems, [], "\n".join(problems[:20]))

    def test_a_retry_shuffles_the_same_questions(self):
        t = academy.TRACKS["trailblazer"]
        first = academy.quiz(t, 18, 2, *COMPANY, seed="a")
        again = academy.quiz(t, 18, 2, *COMPANY, seed="b")
        self.assertEqual(sorted(q.prompt for q in first), sorted(q.prompt for q in again))
        self.assertNotEqual([q.options for q in first], [q.options for q in again])


class TestQuizzesCannotBeGuessed(unittest.TestCase):
    def test_every_question_is_well_formed(self):
        problems = []
        for key, questions in generated().items():
            for q in questions:
                options = [o.strip().lower() for o in q.options]
                if len(options) < 2:
                    problems.append(f"{key}: fewer than two options: {q.prompt}")
                if len(set(options)) != len(options):
                    problems.append(f"{key}: the same option twice: {q.prompt} {q.options}")
                if not 0 <= q.answer < len(q.options):
                    problems.append(f"{key}: no right answer: {q.prompt}")
                if not q.explain.strip():
                    problems.append(f"{key}: nothing explains the answer: {q.prompt}")
        self.assertEqual(problems, [], "\n".join(problems[:20]))

    def test_the_longest_and_shortest_answers_are_right_only_by_chance(self):
        """Across every distinct question, the right answer is the longest
        (or the shortest) option no more often than chance, within MAX_Z
        standard deviations; and no world with enough questions leans on it."""
        questions = distinct_questions()
        for pick in (max, min):
            hits, expected, variance = _shape_hits(questions.values(), pick)
            z = (hits - expected) / math.sqrt(variance)
            self.assertLess(z, MAX_Z, f"{pick.__name__}: right {hits} times, chance says about {expected:.0f}")
            for side in ("class", "family"):
                mine = [q for (s, _, _), q in questions.items() if s == side]
                hits, expected, variance = _shape_hits(mine, pick)
                self.assertLess((hits - expected) / math.sqrt(variance), MAX_Z, (side, pick.__name__))
            by_world = collections.defaultdict(list)
            for (side, key, _), q in questions.items():
                by_world[(side, key)].append(q)
            problems = []
            for where, mine in by_world.items():
                hits, expected, _ = _shape_hits(mine, pick)
                worded = sum(1 for q in mine if q.kind == "choice" and not _numbers_only(q))
                if worded >= MIN_WORLD_QUESTIONS and hits / worded > MAX_WORLD_SHARE:
                    problems.append(f"{where}: the {pick.__name__} option is right in {hits}/{worded}")
            self.assertEqual(problems, [], "\n".join(problems))

    def test_picking_by_length_passes_no_more_than_guessing(self):
        for t in academy.ALL_TRACKS:
            for pick in (max, min):
                passed = chance = variance = 0
                for w, stage in _lessons(t):
                    questions = _lesson(t, w, stage)
                    needed = academy.pass_mark(t, w, stage)
                    passed += sum(_strategy_score(q, pick) for q in questions) >= needed
                    p = _guess_pass_chance(questions, needed)
                    chance += p
                    variance += p * (1 - p)
                self.assertLess((passed - chance) / math.sqrt(variance), MAX_Z,
                                f"{t.name}: always picking the {pick.__name__} answer passed {passed} lessons,"
                                f" guessing would pass about {chance:.0f}")

    def test_the_right_answer_moves_between_slots(self):
        problems = []
        for key, questions in generated().items():
            slots = collections.Counter(q.answer for q in questions if len(q.options) == 3 and q.kind == "choice")
            count = sum(slots.values())
            if count < 60:
                continue
            for slot in range(3):
                if slots[slot] / count < MIN_SLOT_SHARE:
                    problems.append(f"{key}: option {'ABC'[slot]} is right in only {slots[slot] / count:.0%}")
        self.assertEqual(problems, [], "\n".join(problems))

    def test_true_or_false_is_not_a_safe_guess(self):
        problems = []
        for key, questions in generated().items():
            answers = [q.answer for q in questions if q.kind == "truefalse"]
            if len(answers) < 30:
                continue
            share = answers.count(0) / len(answers)
            if not TRUE_SHARE[0] <= share <= TRUE_SHARE[1]:
                problems.append(f"{key}: true in {share:.0%} of its true-or-false questions")
        self.assertEqual(problems, [], "\n".join(problems))

    def test_the_first_worlds_facts_are_true_and_false(self):
        for name in ("COMPANY_FACTS", "RULE_FACTS", "TEAM_FACTS"):
            facts = getattr(academy, name)
            truths = [truth for _, truth, _ in facts]
            self.assertGreaterEqual(truths.count(True), 2, name)
            self.assertGreaterEqual(truths.count(False), 2, name)
            self.assertEqual(len({s for s, _, _ in facts}), len(facts), name)


if __name__ == "__main__":
    unittest.main()
