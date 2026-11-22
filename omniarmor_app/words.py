# -*- coding: utf-8 -*-
"""Plain words for counts: "1 warning", "2 warnings", "1 day", "3 days".

Every page, email and generated lesson that puts a number before a word uses
plural() (templates: the `plural` filter), so a count of one never reads
"1 warnings" or "at 1 lessons" (1.18.0).
"""

# Words whose plural isn't the word plus "s".
_IRREGULAR = {
    "class": "classes", "entry": "entries", "breach": "breaches", "person": "people", "child": "children",
    "activity": "activities", "box": "boxes", "match": "matches", "story": "stories", "copy": "copies",
    "category": "categories", "industry": "industries", "inquiry": "inquiries",
}


def plural_word(n, one, many=None):
    """The word alone, as the count n needs it: plural_word(1, "day") is "day"."""
    if n == 1 or n == -1:
        return one
    if many:
        return many
    return _IRREGULAR.get(one, f"{one}s")


def plural(n, one, many=None):
    """A count and its word: plural(1, "warning") is "1 warning", plural(2,
    "warning") "2 warnings". A whole number at or over 1,000 gets commas."""
    shown = f"{n:,}" if isinstance(n, int) and abs(n) >= 1000 else str(n)
    return f"{shown} {plural_word(n, one, many)}"
