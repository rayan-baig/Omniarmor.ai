# -*- coding: utf-8 -*-
"""Looks through the Academy's quizzes for wrong answers that are true.

A quiz option marked wrong must really be wrong for the learner's company.
This script builds every lesson of every track for a few sample companies
and flags the patterns that have slipped through before:

- own-rule      a wrong answer to a question about the company is one of its
                own rules (its title, cost, fix or question), so it is true
- universal     a wrong answer to "which is your company's rule?" is a rule
                nearly every business follows ("Hours worked records kept",
                fire extinguisher checks: academy.is_universal)
- only-one      "Which kind of business follows ...?" asked about a rule
                nearly every business follows, with one trade as the answer
- both-ways     the same question has an answer marked right in one place
                and wrong in another

Run it from the project folder:

    python tools/quiz_truth_review.py            # every track, the sample companies
    python tools/quiz_truth_review.py --quick    # one company, for a fast look

It prints each flag and exits 1 when there are any (tests/test_quiz_truth.py
runs it too). A flag is either a generator bug to fix in academy.py or a
written row to fix in academy_bank.
"""

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from omniarmor_app import academy  # noqa: E402
from omni_armor_rules import CATALOG  # noqa: E402

# (company name, its industries): a restaurant with staff, a salon, a
# pharmacy with an employer's checklist, and a school.
COMPANIES = [
    ("Sams Taqueria", (2,)),
    ("Juniper Lane", (2, 30)),
    ("Bright Salon", (52,)),
    ("Corner Pharmacy", (28, 30)),
    ("Maple School", (8, 51)),
]

_FOLLOWS = "Which kind of business follows \""
_YOURS = ("really follows?", "own checklist?")


def _norm(text):
    return " ".join(str(text).lower().split()).strip(" .\"")


def _own_texts(ids):
    texts = set()
    for i in ids:
        for r in CATALOG.get(i, ()):
            texts.update(_norm(t) for t in (r.title, r.cost, r.action, r.input))
    return texts


# Known to be true for nearly any business, checked on their own here (not
# through academy.is_universal, so a change there can't hide a flag): an
# employer's, card payments' and personal data's rules, and the checks many
# trades share.
ANY_BUSINESS_INDUSTRIES = {30, 31, 32}
ANY_BUSINESS = re.compile(
    r"fire extinguisher|safety data sheet|hazard communication|osha 300|injury report|overtime paid|hours worked"
    r"|minimum wage|card (data|security)|first.aid kit|sales tax|i-9", re.I)


def _universal_titles():
    return {_norm(r.title) for i, rules in CATALOG.items() for r in rules
            if i in ANY_BUSINESS_INDUSTRIES or ANY_BUSINESS.search(r.title)}


def _lessons(t, company, ids):
    """(where, question) for every lesson of track t for this company."""
    for w in t.worlds:
        for stage in range(1, t.stages(w) + 1):
            for q in academy.quiz(t, w.number, stage, company, ids, "review"):
                yield f"{t.name} · {w.title} · stage {stage}", q


def review(companies=None, tracks=None):
    """Every flag, as (pattern, where, question prompt, the option)."""
    flags = []
    universal = _universal_titles()
    # Titles also in an employer's, a payments or a privacy checklist.
    shared_universal = {_norm(r.title) for i in ANY_BUSINESS_INDUSTRIES for r in CATALOG[i]}
    tracks = tracks or (list(academy.TRACK_LIST) + [academy.CLASSROOM])
    for company, ids in companies or COMPANIES:
        own = _own_texts(ids)
        right_for = {}
        wrong_for = {}
        for t in tracks:
            for where, q in _lessons(t, company, ids):
                right = q.options[q.answer]
                right_for.setdefault(_norm(q.prompt), set()).add(_norm(right))
                for n, option in enumerate(q.options):
                    if n == q.answer or q.kind == "truefalse":
                        continue
                    wrong_for.setdefault(_norm(q.prompt), {})[_norm(option)] = (where, option)
                    if _norm(option) in own and company in q.prompt:
                        flags.append(("own-rule", f"{company}: {where}", q.prompt, option))
                    if q.prompt.endswith(_YOURS) and _norm(option) in universal:
                        flags.append(("universal", f"{company}: {where}", q.prompt, option))
                if q.prompt.startswith(_FOLLOWS):
                    title = q.prompt[len(_FOLLOWS):].rstrip("?\"")
                    if _norm(title) in universal or _norm(title) in shared_universal:
                        flags.append(("only-one", f"{company}: {where}", q.prompt, right))
        for prompt, wrongs in wrong_for.items():
            for option, (where, shown) in wrongs.items():
                if option in right_for.get(prompt, ()):
                    flags.append(("both-ways", f"{company}: {where}", prompt, shown))
    return flags


def main(argv):
    quick = "--quick" in argv
    flags = review(COMPANIES[:1] if quick else None)
    for pattern, where, prompt, option in flags:
        print(f"[{pattern}] {where}\n    Q: {prompt}\n    marked wrong: {option}")
    print(f"{len(flags)} flag{'s' if len(flags) != 1 else ''}.")
    return 1 if flags else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
