# -*- coding: utf-8 -*-
"""Armo, OmniArmor's mascot and helper.

Armo has personalities people can choose: each one changes how Armo talks and
what it wears, never the facts. Outside the Academy, Armo watches a company's
checks and points at whatever needs attention right now.
"""

import hashlib
from dataclasses import dataclass, field
from datetime import timedelta

from flask import url_for

from .db import iso, utcnow
from .tracking import states_for_org

UPCOMING_DAYS = 30
FAILED_EMAIL_DAYS = 7


@dataclass(frozen=True)
class Personality:
    key: str
    name: str
    tagline: str
    accessory: str
    activities: list      # what Armo does while idle: mug, book, juggle, zzz, wave
    idle: list            # things Armo says while idle
    alert: list           # how Armo announces an issue; "{title}" is the issue
    clear: list           # nothing needs attention
    fix: str              # label for the fix link
    hello: str            # Academy greeting
    cheers: list = field(default_factory=list)
    oops: list = field(default_factory=list)
    streaks: dict = field(default_factory=dict)
    win: str = ""
    retry: str = ""


PERSONALITIES = {p.key: p for p in [
    Personality(
        "chief", "Chief", "Calm and professional", "bowtie", ["book", "mug", "wave"],
        idle=["All systems watched. Carry on.",
              "Tip: enter each date once, and I'll track it from there.",
              "Reminders go out every morning. You can relax.",
              "Every change is recorded in the Vault.",
              "Quiet day. That's the goal.",
              "A minute now beats a fine later.",
              "Need something for an inspector? Intel has the report.",
              "I re-check everything daily. Nothing slips."],
        alert=["Attention needed: {title}", "Priority item: {title}"],
        clear=["All clear. Nothing needs you right now.", "Everything is in order."],
        fix="Fix it",
        hello="Let's get to work.",
        cheers=["Correct.", "Right.", "Well judged.", "Exactly."],
        oops=["Not quite. Read the note.", "Close. See why below."],
        streaks={3: "3 in a row.", 5: "5 in a row. Strong.", 8: "8 in a row. Excellent."},
        win="Solid work. On to the next one.",
        retry="Not this time. Review the notes and go again.",
    ),
    Personality(
        "sweet", "Sweetie", "Sweet and kind", "flower", ["wave", "book", "mug"],
        idle=["You're doing great today. Just wanted you to know.",
              "Remember to drink some water!",
              "I'm so proud of this team.",
              "Sending you a tiny shield hug.",
              "Every check you finish keeps someone safe. That's lovely.",
              "If today feels hard, that's okay. One thing at a time.",
              "I tidied up your deadlines. They look so neat now.",
              "You make this look easy, you know."],
        alert=["Oh! Something needs a little love: {title}", "Sorry to bother you! {title}"],
        clear=["All clear! Go do something nice for yourself.", "Nothing to fix. You're amazing."],
        fix="Let's fix it together",
        hello="Hi friend! I'm so happy you're here!",
        cheers=["Yay, you got it!", "So smart!", "That's right, sweetie!", "Wonderful!"],
        oops=["That's okay! Read the tip.", "Mistakes help us grow!"],
        streaks={3: "3 in a row! I'm so proud!", 5: "5 in a row! You're shining!", 8: "8 in a row! Superstar!"},
        win="You did it! I'm so proud of you!",
        retry="So close! I believe in you. Let's try again.",
    ),
    Personality(
        "funny", "Jokester", "Never misses a joke", "partyhat", ["juggle", "wave", "mug"],
        idle=["Why did the deadline break up with the calendar? It needed space.",
              "I'd tell you a compliance joke, but it hasn't been approved yet.",
              "I'm not saying I'm a superhero. But nobody's seen me and a fine in the same room.",
              "My favorite workout? Checking boxes.",
              "I'm reading a book about anti-gravity. Can't put it down.",
              "Knock knock. Who's there? Audit. Audit who? Audit-n't be scary if you're ready!",
              "I'm 100% shield, 0% sword. Very peaceful guy.",
              "I tried to juggle deadlines once. Now I just juggle balls. Much safer."],
        alert=["Joke's on hold! {title}", "Plot twist: {title}"],
        clear=["Nothing to fix. I'm basically unemployed. Love that for us.",
               "All clear! Time for my stand-up set."],
        fix="Fix it (no joke)",
        hello="Ready to learn? I promise most of my jokes are educational.",
        cheers=["Nailed it!", "You're on a roll! Like a burrito!", "Ding ding ding!", "Big brain move!"],
        oops=["Whoops! Even I trip over my own shield.", "Wrong, but in a fun way!"],
        streaks={3: "3 in a row! Somebody call the fire department!",
                 5: "5 in a row! Are you secretly a genius?", 8: "8 in a row! I'm writing you a song!"},
        win="You win! I'd high-five you, but I'm a shield.",
        retry="That one got away. Let's go get it back!",
    ),
    Personality(
        "snarky", "Snark", "Sarcastic, but always on your side", "sunglasses", ["mug", "book"],
        idle=["Oh look, another day of me doing all the remembering.",
              "I love deadlines. Said no one ever. Except me.",
              "I'd roll my eyes, but I'm a shield.",
              "Sure, ignore me. I'm only saving you money.",
              "Fines don't care about excuses. I do, a little.",
              "I'm not bossy. I just know what you should be doing.",
              "Another flawless day, thanks to me. You're welcome.",
              "Wow, you clicked something. Groundbreaking."],
        alert=["Oh, would you look at that. {title}", "Not to be dramatic, but {title}"],
        clear=["Nothing's on fire. Try to keep it that way.", "All clear. I'll pretend that was your doing."],
        fix="Fine, I'll show you",
        hello="Oh good, you're here. Let's make you smart.",
        cheers=["Okay, I'm impressed. A little.", "Look at you, being right.", "Fine. That was good.", "Correct. Shocking."],
        oops=["Bold choice. Wrong, but bold.", "Yeah, no. Read the tip."],
        streaks={3: "3 in a row? Who are you?", 5: "5 in a row. Okay, show-off.", 8: "8 in a row. Fine, you're a genius."},
        win="Not bad. Don't let it go to your head.",
        retry="Well, that happened. Try again, champ.",
    ),
    Personality(
        "grumpy", "Grumpy", "Whiny, but gets it done", "cloud", ["mug", "book"],
        idle=["Ugh. Mondays. Also every other day.",
              "Why am I always the one who remembers everything?",
              "My arms are too short for this.",
              "I asked for one day off. ONE.",
              "Nobody ever asks how the shield is doing.",
              "I'll just keep watching your deadlines. Forever. Alone.",
              "Is it lunch yet? It feels like it should be lunch.",
              "Fine. I'm guarding. Happy now?"],
        alert=["Ugh, of course. {title}", "Great. Just great. {title}"],
        clear=["Nothing to do. Now I'm bored. Thanks a lot.", "All clear. Don't get used to it."],
        fix="Ugh, fine, fix it",
        hello="Ugh, school. Fine. Let's learn stuff.",
        cheers=["Hmph. Correct.", "Okay, that was right. Happy?", "Fine. Good job.", "Yeah, yeah, you got it."],
        oops=["Ugh, wrong. Read the tip.", "Nope. Story of my life."],
        streaks={3: "3 in a row. I guess that's cool.", 5: "5 in a row. Ugh, fine, you're good.",
                 8: "8 in a row! Okay, I'm actually smiling. Don't tell anyone."},
        win="You passed. I'm not crying, you're crying.",
        retry="Ugh, so close. Again. Come on.",
    ),
    Personality(
        "sleepy", "Sleepy", "Always tired, never misses a thing", "nightcap", ["zzz", "mug"],
        idle=["*yawn* I'm awake. Mostly.",
              "Five more minutes... of guarding.",
              "I dreamed about due dates again.",
              "Is it nap time? It feels like nap time.",
              "Zzz... Oh! Still watching, I promise.",
              "Coffee number four. Don't judge.",
              "I'm resting my eyes, not my brain.",
              "Night shift, day shift. Every shift is my shift."],
        alert=["Huh?! I'm up! {title}", "*wakes up* Wait... {title}"],
        clear=["All clear... perfect time for a nap.", "Nothing to do. Zzz..."],
        fix="Okay, okay, I'm up",
        hello="*yawn* Hi. Let's learn something before my nap.",
        cheers=["Ooh, correct! *yawn*", "Nice... very nice...", "You woke me up with that one!", "Right on."],
        oops=["Mm, not quite. Read the tip.", "Oops. I need more coffee too."],
        streaks={3: "3 in a row! I'm awake now!", 5: "5 in a row! Okay, I'm WIDE awake!", 8: "8 in a row! Who needs naps?!"},
        win="You did it! Now we both deserve a nap.",
        retry="Almost... let's try once more. Then a nap.",
    ),
]}
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
