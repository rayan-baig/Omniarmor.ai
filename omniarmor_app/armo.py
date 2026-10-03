# -*- coding: utf-8 -*-
"""Armo, OmniArmor's mascot and helper.

Armo has personalities people can choose: each one changes how Armo talks and
what it wears, never the facts. Outside the Academy, Armo watches a company's
checks and points at whatever needs attention right now.
"""

import hashlib
from datetime import timedelta

from flask import url_for

from .armo_lines import PERSONALITIES
from .db import iso, utcnow
from .tracking import states_for_org

UPCOMING_DAYS = 30
FAILED_EMAIL_DAYS = 7


DEFAULT_ADULT = "chief"
DEFAULT_KID = "sweet"
HIDDEN = "off"


def personality(key, default=DEFAULT_ADULT):
    return PERSONALITIES.get(key) or PERSONALITIES[default]


def voice(key):
    """The quiz lines for the browser script."""
    p = personality(key, DEFAULT_KID)
    return {"cheers": p.cheers, "oops": p.oops, "streaks": {str(k): v for k, v in p.streaks.items()}}


def _plural(n, word):
    return f"{n} {word}" if n == 1 else f"{n} {word}s"


def live_issues(conn, org):
    """What needs attention right now, most urgent first. Each issue has a
    level (urgent, soon or info), a title, details, what to do and a link."""
    states = states_for_org(conn, org)
    urgent, soon, info = [], [], []
    for s in sorted(states, key=lambda s: s.sort_key):
        link = url_for("app.industry", industry_id=s.industry_id) + f"#rule-{s.key}"
        where = s.industry["brand"]
        if s.level == "BLOCKED":
            if s.days_left is not None and s.days_left < 0:
                title = f"{s.rule.title}: overdue by {_plural(-s.days_left, 'day')}"
            else:
                title = f"{s.rule.title} is blocked"
            urgent.append({"level": "urgent", "title": title, "where": where, "detail": s.message,
                           "action": s.rule.action, "cost": s.rule.cost, "url": link})
        elif s.level == "WARNING":
            if s.days_left is not None and s.days_left >= 0:
                title = f"{s.rule.title}: due {'today' if s.days_left == 0 else 'in ' + _plural(s.days_left, 'day')}"
            else:
                title = f"{s.rule.title} is close to the limit"
            soon.append({"level": "soon", "title": title, "where": where, "detail": s.message,
                         "action": s.rule.action, "cost": s.rule.cost, "url": link})
        elif s.due_date is not None and s.days_left is not None and 0 <= s.days_left <= UPCOMING_DAYS:
            info.append({"level": "info", "title": f"{s.rule.title}: due in {_plural(s.days_left, 'day')}",
                         "where": where, "detail": f"Due {s.due_date.isoformat()}.",
                         "action": "Plan it now so it doesn't become urgent.", "cost": "", "url": link})

    since = iso(utcnow() - timedelta(days=FAILED_EMAIL_DAYS))
    failed = conn.execute("SELECT COUNT(*) FROM notifications WHERE org_id = ? AND status = 'failed' AND created_at >= ?",
                          (org["id"], since)).fetchone()[0]
    if failed:
        soon.insert(0, {"level": "soon", "title": f"{_plural(failed, 'email')} failed to send this week",
                        "where": "Reminders", "detail": "Someone on your team may have missed a reminder.",
                        "action": "Open Radar to see the error, then check your email settings.", "cost": "",
                        "url": url_for("app.notifications")})

    missing = [s for s in states if s.level == "NONE"]
    if missing:
        first = missing[0]
        info.append({"level": "info", "title": f"{_plural(len(missing), 'check')} with no reading yet",
                     "where": first.industry["brand"],
                     "detail": "Armo can't warn you about a check until it has a date or reading.",
                     "action": "Enter each one once. Armo tracks it from then on.", "cost": "",
                     "url": url_for("app.industry", industry_id=first.industry_id) + f"#rule-{first.key}"})
    return urgent + soon + info[:6]


def summary(conn, org):
    issues = live_issues(conn, org)
    needs = sum(1 for i in issues if i["level"] in ("urgent", "soon"))
    urgent = sum(1 for i in issues if i["level"] == "urgent")
    pressing = [i for i in issues if i["level"] in ("urgent", "soon")]
    signature = hashlib.sha1("|".join(i["title"] for i in pressing).encode()).hexdigest()[:12] if pressing else ""
    return {"issues": issues, "needs": needs, "urgent": urgent, "signature": signature,
            "top": pressing[0] if pressing else None,
            "mood": "alert" if urgent else ("think" if needs else "happy")}
