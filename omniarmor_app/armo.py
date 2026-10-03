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
MAX_WALKTHROUGH = 8  # issues Armo walks through one by one


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
            urgent.append({"level": "urgent", "kind": "blocked", "title": title, "where": where, "detail": s.message,
                           "action": s.rule.action, "cost": s.rule.cost, "url": link})
        elif s.level == "WARNING":
            if s.days_left is not None and s.days_left >= 0:
                title = f"{s.rule.title}: due {'today' if s.days_left == 0 else 'in ' + _plural(s.days_left, 'day')}"
            else:
                title = f"{s.rule.title} is close to the limit"
            soon.append({"level": "soon", "kind": "warning", "title": title, "where": where, "detail": s.message,
                         "action": s.rule.action, "cost": s.rule.cost, "url": link})
        elif s.due_date is not None and s.days_left is not None and 0 <= s.days_left <= UPCOMING_DAYS:
            info.append({"level": "info", "kind": "upcoming", "title": f"{s.rule.title}: due in {_plural(s.days_left, 'day')}",
                         "where": where, "detail": f"Due {s.due_date.isoformat()}.",
                         "action": "Plan it now so it doesn't become urgent.", "cost": "", "url": link})

    since = iso(utcnow() - timedelta(days=FAILED_EMAIL_DAYS))
    failed = conn.execute("SELECT COUNT(*) FROM notifications WHERE org_id = ? AND status = 'failed' AND created_at >= ?",
                          (org["id"], since)).fetchone()[0]
    if failed:
        soon.insert(0, {"level": "soon", "kind": "email", "title": f"{_plural(failed, 'email')} failed to send this week",
                        "where": "Reminders", "detail": "Someone on your team may have missed a reminder.",
                        "action": "Open Radar to see the error, then check your email settings.", "cost": "",
                        "url": url_for("app.notifications")})

    missing = [s for s in states if s.level == "NONE"]
    if missing:
        first = missing[0]
        info.append({"level": "info", "kind": "missing", "title": f"{_plural(len(missing), 'check')} with no reading yet",
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
            "pressing": [{k: i[k] for k in ("title", "url", "action", "where")} for i in pressing[:MAX_WALKTHROUGH]],
            "mood": "alert" if urgent else ("think" if needs else "happy")}


# What each page is for, so Armo can explain wherever you are.
PAGE_HELP = {
    "app.overview": "This is HQ. Anything blocked or close to a limit is listed first. Click a check to fix it.",
    "app.industry": "Enter each check's date or reading once and I'll track it. When a recurring task is done, "
                    "press Done today and I'll restart the countdown.",
    "app.report": "This is Intel, your compliance report. Print it, or export the CSV for an inspector, auditor or insurer.",
    "app.audit": "This is the Vault. It records every change: what changed, who changed it and when.",
    "app.notifications": "This is Radar. It lists every reminder email I've sent or saved, and why any failed.",
    "app.settings": "This is the Armory. Invite your team, choose your industries, set your timezone "
                    "and turn email reminders on or off.",
}


def page_help(endpoint):
    return PAGE_HELP.get(endpoint or "", "")


def tips(conn, org, user, state, mail_ready):
    """Short, useful suggestions built from the company's real data, each
    with a link to where to act. Armo mixes these into his chatter."""
    found = []
    upcoming = [i for i in state["issues"] if i.get("kind") == "upcoming"]
    if upcoming:
        found.append({"text": f"Next deadline: {upcoming[0]['title']}. Plan it now and it never becomes urgent.",
                      "url": upcoming[0]["url"]})
    missing = [i for i in state["issues"] if i.get("kind") == "missing"]
    if missing:
        found.append({"text": f"{missing[0]['title']}. Start with {missing[0]['where']}. Enter each one once, "
                              "and I'll track it from then on.", "url": missing[0]["url"]})
    members = conn.execute("SELECT COUNT(*) FROM memberships WHERE org_id = ?", (org["id"],)).fetchone()[0]
    if members == 1:
        found.append({"text": "You're the only one here. Invite your team in the Armory so reminders reach everyone.",
                      "url": url_for("app.settings")})
    if not user["email_reminders"]:
        found.append({"text": "Your email reminders are off. Turn them on in the Armory so a deadline never "
                              "sneaks up on you.", "url": url_for("app.settings")})
    if not mail_ready:
        found.append({"text": "Email isn't set up yet, so reminders are saved in Radar instead of sent.",
                      "url": url_for("app.notifications")})
    learners = conn.execute("SELECT COUNT(*) FROM learners WHERE org_id = ?", (org["id"],)).fetchone()[0]
    if not learners:
        found.append({"text": "Got future owners at home? The Academy teaches kids the business in 1,350 game levels.",
                      "url": url_for("academy.home")})
    found.append({"text": "Need proof for an inspector? Intel prints a full compliance report.",
                  "url": url_for("app.report")})
    found.append({"text": "Every change is saved in the Vault, with who made it and when.", "url": url_for("app.audit")})
    return found
