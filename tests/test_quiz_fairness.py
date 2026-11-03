"""The Academy's quizzes can't be passed by guessing from their shape.

tests/test_academy_bank.py checks each written question bank on its own.
This checks the quizzes kids actually get, every track and topic world and
the Owner's Challenge, built from many seeds, including the questions
written straight into academy.py:

- every question has two or more different options and one right answer;
- the right answer isn't usually the longest option;
- the right answer moves around: no slot of a three-option question gets
  most of the right answers;
- true-or-false questions are true about as often as they are false.

The right answers still never reach the page (tests/test_quiz_checks.py).
"""

import collections
import functools
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from omniarmor_app import academy  # noqa: E402

SEEDS = 24
MAX_LONGEST_WORLD = 0.45    # chance with three options is about 1 in 3
MAX_LONGEST_OVERALL = 0.33
MIN_SLOT_SHARE = 0.2        # each of three slots gets at least this share of the right answers
TRUE_SHARE = (0.3, 0.7)


def _numbers_only(q):
    """Options that are all amounts or counts: their length says nothing."""
    return all(any(ch.isdigit() for ch in option) for option in q.options)


@functools.lru_cache(maxsize=None)
def generated():
    """{world key: [questions]} from every track's topic worlds and the
    Owner's Challenge, at five depths of each world and SEEDS seeds."""
    found = collections.defaultdict(list)
    for t in academy.TRACK_LIST:
        for w in t.topic_worlds + [academy.FINAL_WORLD]:
            n = t.stages(w)
            for stage in sorted({1, n // 4, n // 2, 3 * n // 4, n}):
                for seed in range(SEEDS):
                    found[w.key] += academy.quiz(t, w.number, stage, "Acme Logistics", [1, 18], f"fair-{seed}")
    return found


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

    def test_the_right_answer_is_not_usually_the_longest(self):
        problems, longest, total = [], 0, 0
        for key, questions in generated().items():
            worded = [q for q in questions if q.kind == "choice" and not _numbers_only(q)]
            hits = sum(1 for q in worded if len(q.options[q.answer]) > max(
                len(o) for i, o in enumerate(q.options) if i != q.answer))
            longest, total = longest + hits, total + len(worded)
            if worded and hits / len(worded) > MAX_LONGEST_WORLD:
                problems.append(f"{key}: the right answer is the longest option in {hits / len(worded):.0%}")
        self.assertEqual(problems, [], "\n".join(problems))
        self.assertLessEqual(longest / total, MAX_LONGEST_OVERALL)

    def test_the_right_answer_moves_between_slots(self):
        problems = []
        for key, questions in generated().items():
            slots = collections.Counter(q.answer for q in questions if len(q.options) == 3)
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
