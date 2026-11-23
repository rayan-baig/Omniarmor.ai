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
- shape         in one world, the right answer is the longest option, or the
                shortest, in more than MAX_SHAPE_SHARE of its worded
                questions, so a kid could pass by picking on length alone
                (chance, with three options, is one in three)
- word-for-word a question's right answer (four words or more, not a
                number) is written word for word on its own lesson's cards,
                so the quiz asks the kid to spot a sentence, not to use the
                idea (1.18.0). Naming the company's own checks is the point
                of those questions, so they are left out.
- stray-line    an explanation has a short "X is a Y." line about one of the
                wrong answers that shares no word with the question or its
                right answer ("What is a fine?" ... "A thank-you is a tip."),
                so it reads as a line from somewhere else (1.19.0). Say how it
                ties back ("..., not a product.") or leave it out.
- repeat        a word a lesson's matching game can show is asked again, or
                offered, in another question of the same lesson (1.21.0): the
                game and the questions should teach different words
- long-sentence an answer to "Which sentence uses ...?" is longer than
                academy.SENTENCE_MOST characters (1.21.0), too long to read
                three of at a glance on a phone

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


# The shape rule: in a world with at least MIN_SHAPE_QUESTIONS worded
# questions, the right answer may be the longest option, or the shortest, in
# at most this share of them. A reviewer once found the shortest answer right
# 10 times in 14.
MAX_SHAPE_SHARE = 0.45
MIN_SHAPE_QUESTIONS = 10


def _worded(q):
    """A choice question whose options are words, not amounts or counts."""
    return q.kind == "choice" and not all(any(ch.isdigit() for ch in o) for o in q.options)


def shape_counts(questions):
    """(worded questions, right is the longest, right is the shortest), each
    counted only where that option is the one longest or shortest."""
    worded = longest = shortest = 0
    for q in questions:
        if not _worded(q):
            continue
        lengths = [len(o) for o in q.options]
        mine = lengths[q.answer]
        worded += 1
        longest += mine == max(lengths) and lengths.count(mine) == 1
        shortest += mine == min(lengths) and lengths.count(mine) == 1
    return worded, longest, shortest


def shape_flags(where, questions):
    """The shape flags for one world's questions (each prompt once)."""
    worded, longest, shortest = shape_counts(questions)
    flags = []
    if worded >= MIN_SHAPE_QUESTIONS:
        for name, hits in (("longest", longest), ("shortest", shortest)):
            if hits / worded > MAX_SHAPE_SHARE:
                flags.append(("shape", where, f"the {name} option is right in {hits} of {worded} questions",
                              f"at most {MAX_SHAPE_SHARE:.0%}"))
    return flags


_NAMING = ("own checklist?", "really follows?")


def _plain(text):
    return " ".join(re.sub(r"[^a-z0-9$% ]", " ", str(text).lower()).split())


def word_for_word_flags(t, company, ids):
    """Questions whose right answer is copied from their own lesson's cards."""
    flags = []
    for w in t.worlds:
        if w.kind == "industry":
            continue
        for stage in range(1, t.stages(w) + 1):
            said = _plain(" ".join(f"{a} {b}" for a, b in academy.story(t, w.number, stage, company, ids)))
            for q in academy.quiz(t, w.number, stage, company, ids, "review"):
                if q.kind != "choice" or q.prompt.endswith(_NAMING):
                    continue
                right = _plain(q.options[q.answer])
                if len(right.split()) >= 4 and not any(ch.isdigit() for ch in right) and right in said:
                    flags.append(("word-for-word", f"{company}: {t.name} · {w.title} · stage {stage}", q.prompt,
                                  q.options[q.answer]))
    return flags


# Words too common to tie two sentences together.
_COMMON = set(
    "a an the and or but if then so to of in on at by for with from as is are was were be been it its this that these"
    " those there their they them you your we our he she his her not no do does did can could would should will may"
    " might must have has had what which who when where why how all any each every some more most much many one than"
    " too very just only also into out up about after before own same other such".split())


def _stem(word):
    word = word.lower().strip("'")
    for end in ("ing", "ed", "es", "s"):
        if len(word) > 4 and word.endswith(end):
            return word[:-len(end)]
    return word


def _content(text):
    return {_stem(w) for w in re.findall(r"[A-Za-z][A-Za-z'-]*", str(text)) if w.lower() not in _COMMON and len(w) > 2}


_DEFINES = re.compile(r"^[A-Za-z][\w' -]* (is|are) (a|an) [\w' -]+\.$")


def stray_lines(q):
    """The explanation's short "X is a Y." lines about a wrong answer that share
    no word with the question or its right answer."""
    if q.kind != "choice":
        return []
    lines = [x for x in re.split(r"(?<=[.!?])\s+", q.explain.strip()) if x]
    if len(lines) < 2:
        return []
    ties = _content(q.prompt) | _content(q.options[q.answer])
    wrong = _content(" ".join(o for n, o in enumerate(q.options) if n != q.answer))
    return [x for x in lines if len(x.split()) <= 8 and _DEFINES.match(x) and _content(x) & wrong
            and not _content(x) & ties]


def lesson_flags(t, company, ids):
    """The repeat and long-sentence flags for every lesson of track t."""
    flags = []
    for w in t.worlds:
        for stage in range(1, t.stages(w) + 1):
            where = f"{company}: {t.name} · {w.title} · stage {stage}"
            questions = academy.quiz(t, w.number, stage, company, ids, "review")
            for n, q in enumerate(questions):
                if q.prompt.startswith("Which sentence uses"):
                    for option in q.options:
                        if len(option) > academy.SENTENCE_MOST:
                            flags.append(("long-sentence", where, q.prompt, option))
                if q.kind != "match":
                    continue
                shown = set((q.parts or {}).get("pool") or []) | set((q.parts or {}).get("left") or [])
                for m, other in enumerate(questions):
                    if m != n:
                        for word in sorted(shown & academy.words_in(other)):
                            flags.append(("repeat", where, other.prompt, word))
    return flags


def review(companies=None, tracks=None):
    """Every flag, as (pattern, where, question prompt, the option); for a
    shape flag, (pattern, where, what was found, the limit)."""
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
            by_world = {}
            for where, q in _lessons(t, company, ids):
                by_world.setdefault(where.rsplit(" · stage ", 1)[0], {})[q.prompt] = q
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
                for line in stray_lines(q):
                    flags.append(("stray-line", f"{company}: {where}", q.prompt, line))
                if q.prompt.startswith(_FOLLOWS):
                    title = q.prompt[len(_FOLLOWS):].rstrip("?\"")
                    if _norm(title) in universal or _norm(title) in shared_universal:
                        flags.append(("only-one", f"{company}: {where}", q.prompt, right))
            for world, questions in by_world.items():
                flags += shape_flags(f"{company}: {world}", questions.values())
            flags += word_for_word_flags(t, company, ids)
            flags += lesson_flags(t, company, ids)
        for prompt, wrongs in wrong_for.items():
            for option, (where, shown) in wrongs.items():
                if option in right_for.get(prompt, ()):
                    flags.append(("both-ways", f"{company}: {where}", prompt, shown))
    return flags


def main(argv):
    quick = "--quick" in argv
    flags = review(COMPANIES[:1] if quick else None)
    for pattern, where, prompt, option in flags:
        if pattern == "word-for-word":
            print(f"[{pattern}] {where}\n    Q: {prompt}\n    right answer copied from its card: {option}")
        elif pattern == "stray-line":
            print(f"[stray-line] {where}\n    Q: {prompt}\n    a line that doesn't tie back to it: {option}")
        elif pattern == "repeat":
            print(f"[repeat] {where}\n    Q: {prompt}\n    asks a word the lesson's matching game shows: {option}")
        elif pattern == "long-sentence":
            print(f"[long-sentence] {where}\n    Q: {prompt}\n    {len(option)} characters: {option}")
        elif pattern == "shape":
            print(f"[shape] {where}\n    {prompt} ({option})")
        else:
            print(f"[{pattern}] {where}\n    Q: {prompt}\n    marked wrong: {option}")
    print(f"{len(flags)} flag{'s' if len(flags) != 1 else ''}.")
    return 1 if flags else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
