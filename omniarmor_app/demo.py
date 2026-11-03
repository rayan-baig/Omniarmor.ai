# -*- coding: utf-8 -*-
"""A demo workspace for screenshots and sales calls.

    flask --app wsgi seed-demo                      into the app's database, if it is empty
    flask --app wsgi seed-demo --force demo.db      into a new database file of its own

It makes a made-up community pharmacy, Juniper Lane Pharmacy, with two
industries (Pharmacies, and Employers & HR), an owner and a pharmacist on the
team, a realistic mix of checks done, coming due and overdue, a few weeks of
audit trail, the morning's reminder digest in Radar, an Academy with two
learners partway through (one with a certificate), and Autopilot's history
with one real pass run at the end. Every name in it is invented, and every
address is on the reserved .example domain, which never receives email.

It never mixes into real data. It refuses unless the database has no
accounts, workspaces or learners at all, checked again inside the write
transaction that seeds it. In production it also refuses the app's own
database, empty or not, since a new deployment's empty database is about to
become the real one: there, --force must name a separate, new file.
"""

import os
import random
import secrets
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from werkzeug.security import generate_password_hash

from . import academy
from .auth import INVITE_DAYS
from .catalog import INDUSTRIES, find_rule
from .db import connect, iso, migrate, utcnow
from .security import new_device_epoch, password_problem
from .tracking import _describe, compute_state

BUSINESS = "Juniper Lane Pharmacy"
TIMEZONE = "America/Chicago"
DOMAIN = "juniperlane.example"   # .example is reserved: never a real address
OWNER = ("Avery Quill", f"avery@{DOMAIN}")
PHARMACIST = ("Jules Marrow", f"jules@{DOMAIN}")
PHARMACY, EMPLOYER = 28, 30      # PharmacyArmor, HRArmor
WORKSPACE_AGE_DAYS = 62

# Each check's reading, as the level it should show today:
#   ("answer", "yes")            a yes-or-no check
#   ("number", 3)                a reading
#   ("ago", days, level)         a date that many days back (a duty last done)
#   ("in", days, level)          a date that many days ahead (an expiry)
# The date is moved a day at a time from `days` until the check shows
# `level` today, so the mix holds on any day it is seeded. Checks left out
# have no reading yet, as in a real workspace a few weeks in.
READINGS = {
    PHARMACY: {
        "corresponding_responsibility": ("answer", "yes"),
        "biennial_inventory": ("ago", 260, "CLEARED"),
        "emergency_cii_7_days": ("ago", 2, "CLEARED"),
        "ciii_iv_refill_limit": ("number", 2),
        "dscsa_trading_partners": ("answer", "yes"),
        "sterile_compounding_cert": ("ago", 168, "WARNING"),     # due in about two weeks
        "exclusion_screening": ("ago", 35, "BLOCKED"),           # the monthly check is a few days late
        "patient_counseling_offer": ("answer", "yes"),
        "license_current": ("in", 41, "WARNING"),                # a license renewal coming up
    },
    EMPLOYER: {
        "overtime_pay": ("answer", "yes"),
        "exempt_salary_level": ("number", 910),
        "minimum_wage": ("number", 15.5),
        "i9_section_2": ("ago", 1, "WARNING"),                   # a new hire's I-9, due tomorrow
        "hours_records": ("answer", "yes"),
        "aca_coverage_offer": ("number", 100),
        "cobra_election_notice": ("ago", 47, "BLOCKED"),         # a notice that went out late
    },
}

# The Academy: two learners on the Launchpad track, each with the stages
# passed in each world (world number: stages), and the days they played.
LEARNERS = [
    {"nickname": "Pip", "avatar": "rocket", "armo": "hype", "certificate": True, "streak": 6,
     "stages": {1: 14, 2: 9, 3: 6, 4: 5, 5: 4, 6: 3, 7: 3, 8: 2, 9: 2, 10: 2, 11: 1, 12: 1, 13: 1, 14: 1, 15: 1,
                16: 1}},
    {"nickname": "Maple", "avatar": "leaf", "armo": "sweet", "certificate": False, "streak": 2,
     "stages": {1: 7, 2: 3, 3: 1}},
]

# Autopilot's own record of the last weeks: what it fixed, days ago.
AUTOPILOT_FIXES = [
    (19, "Re-sent 1 email that failed the first time."),
    (11, "Compacted the database log (71 MB)."),
    (4, "Re-sent 2 emails that failed the first time."),
]


class NotEmpty(Exception):
    """The database already holds accounts, workspaces or learners."""


def is_empty(path):
    """Whether a database file has no accounts, workspaces or learners (or
    doesn't exist yet). Never creates the file."""
    if path != ":memory:" and not os.path.exists(path):
        return True
    conn = connect(path)
    try:
        return _empty(conn)
    finally:
        conn.close()


def _empty(conn):
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    return all(conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] == 0
               for t in ("users", "orgs", "learners") if t in tables)


def _at(day, hour, minute=0, tz=ZoneInfo(TIMEZONE)):
    """A moment on a local day, as stored (UTC)."""
    return iso(datetime.combine(day, time(hour, minute), tzinfo=tz))


def _blank_row(**fields):
    row = {"value_num": None, "value_bool": None, "value_date": None, "limit_override": None,
           "warn_override": None, "updated_at": None, "updated_by_name": None}
    row.update(fields)
    return row


def reading_for(industry_id, rule, spec, today):
    """The stored fields for one check's planned reading."""
    kind = spec[0]
    if kind == "answer":
        return _blank_row(value_bool=1 if spec[1] == "yes" else 0)
    if kind == "number":
        return _blank_row(value_num=float(spec[1]))
    days, level = spec[1], spec[2]
    sign = -1 if kind == "ago" else 1
    for step in range(0, 400):
        for shift in ((0,) if step == 0 else (step, -step)):
            offset = days + shift
            if kind == "ago" and offset < 0:
                continue
            row = _blank_row(value_date=(today + timedelta(days=sign * offset)).isoformat())
            if compute_state(industry_id, rule, row, today).level == level:
                return row
    raise ValueError(f"no date gives {rule.key} the level {level}")


def seed(cfg, password=None, rng=None):
    """Seeds the demo into cfg["DATABASE"]. Raises NotEmpty if the database
    holds anything. Returns what to print: names, addresses and the password."""
    rng = rng or random.Random(2026)
    password = password or secrets.token_urlsafe(9)
    problem = password_problem(password)
    if problem:
        raise ValueError(problem)
    conn = connect(cfg["DATABASE"])
    try:
        migrate(conn)
        conn.isolation_level = None
        conn.execute("BEGIN IMMEDIATE")
        try:
            if not _empty(conn):
                raise NotEmpty(cfg["DATABASE"])
            facts = _fill(conn, password, rng)
            conn.execute("COMMIT")
        except BaseException:
            conn.execute("ROLLBACK")
            raise
        conn.isolation_level = ""
        facts["digests"] = _morning_digest(conn, cfg)
    finally:
        conn.close()
    facts["autopilot"] = _autopilot_pass(cfg)
    facts["password"] = password
    return facts


def _fill(conn, password, rng):
    tz = ZoneInfo(TIMEZONE)
    now = utcnow()
    today = now.astimezone(tz).date()
    opened = today - timedelta(days=WORKSPACE_AGE_DAYS)

    # The workspace and its team.
    owner_id = conn.execute(
        "INSERT INTO users (email, name, password_hash, created_at, last_seen_on, armo) VALUES (?, ?, ?, ?, ?, ?)",
        (OWNER[1], OWNER[0], generate_password_hash(password), _at(opened, 9, 12), today.isoformat(), "chief"),
    ).lastrowid
    org_id = conn.execute("INSERT INTO orgs (name, timezone, created_at) VALUES (?, ?, ?)",
                          (BUSINESS, TIMEZONE, _at(opened, 9, 12))).lastrowid
    conn.execute("INSERT INTO memberships (user_id, org_id, role, created_at) VALUES (?, ?, 'owner', ?)",
                 (owner_id, org_id, _at(opened, 9, 12)))
    conn.executemany("INSERT INTO org_industries (org_id, industry_id) VALUES (?, ?)",
                     [(org_id, PHARMACY), (org_id, EMPLOYER)])
    joined = opened + timedelta(days=1)
    member_id = conn.execute(
        "INSERT INTO users (email, name, password_hash, created_at, last_seen_on, armo) VALUES (?, ?, ?, ?, ?, ?)",
        (PHARMACIST[1], PHARMACIST[0], generate_password_hash(password), _at(joined, 8, 40),
         (today - timedelta(days=1)).isoformat(), "funny"),
    ).lastrowid
    conn.execute("INSERT INTO memberships (user_id, org_id, role, created_at) VALUES (?, ?, 'member', ?)",
                 (member_id, org_id, _at(joined, 8, 40)))
    people = {owner_id: OWNER[0], member_id: PHARMACIST[0]}
    audit = [
        (_at(opened, 9, 12), owner_id, "workspace", "Workspace created with 2 industries", None, None, None, None),
        (_at(opened, 9, 30), owner_id, "team", f"Invite link created (valid {INVITE_DAYS} days)", None, None, None, None),
        (_at(joined, 8, 40), member_id, "team", f"{PHARMACIST[0]} joined the team", None, None, None, None),
    ]

    # The checks, entered over the first days, and the duties done since.
    counts = {"done": 0, "soon": 0, "overdue": 0, "empty": 0}
    for industry_id, plan in READINGS.items():
        for key, spec in plan.items():
            rule = find_rule(industry_id, key)
            row = reading_for(industry_id, rule, spec, today)
            who = owner_id if industry_id == EMPLOYER or rng.random() < 0.4 else member_id
            first_day = opened + timedelta(days=rng.randint(0, 3))
            entered = _at(first_day, rng.randint(9, 16), rng.randint(0, 59))
            final = row["value_date"]
            history = []
            if final and spec[0] == "ago" and date_of(final) > first_day:
                # A repeating duty done since sign-up: entered with the time
                # before, then marked done on the day it happened.
                earlier = _blank_row(value_date=(first_day - timedelta(days=max(1, spec[1] // 3))).isoformat())
                history.append((entered, "reading", None, earlier))
                history.append((_at(date_of(final), rng.randint(9, 17), rng.randint(0, 59)), "done", earlier, row))
            else:
                history.append((entered, "reading", None, row))
            before_text = None
            for at, action, before, after in history:
                before_text = _describe(rule, before)
                after_text = _describe(rule, after)
                audit.append((at, who, action, f"{rule.title}: {before_text} → {after_text}", industry_id, key,
                              before_text, after_text))
            last_at = history[-1][0]
            conn.execute(
                "INSERT INTO items (org_id, industry_id, rule_key, value_num, value_bool, value_date, updated_at,"
                " updated_by, updated_by_name) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (org_id, industry_id, key, row["value_num"], row["value_bool"], row["value_date"], last_at, who,
                 people[who]))
            level = compute_state(industry_id, rule, row, today).level
            due = compute_state(industry_id, rule, row, today).days_left
            if level == "BLOCKED":
                counts["overdue"] += 1
            elif level == "WARNING" or (due is not None and 0 <= due <= 30):
                counts["soon"] += 1
            else:
                counts["done"] += 1
        counts["empty"] += sum(1 for r in _rules(industry_id) if r.key not in plan)
    conn.executemany(
        "INSERT INTO audit (org_id, user_id, user_name, at, action, industry_id, rule_key, before, after, summary)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [(org_id, who, people[who], at, action, ind, key, before, after, summary)
         for at, who, action, summary, ind, key, before, after in sorted(audit, key=lambda a: a[0])])

    # The Academy, on the Academy plan.
    conn.execute("UPDATE orgs SET academy_status = 'active', academy_renews_at = ? WHERE id = ?",
                 (iso(now + timedelta(days=23)), org_id))
    kids = []
    for spec in LEARNERS:
        kids.append(_learner(conn, org_id, owner_id, spec, today, rng))
    a, b = sorted(k["id"] for k in kids)
    conn.execute("INSERT INTO learner_friends (learner_a, learner_b, created_at) VALUES (?, ?, ?)",
                 (a, b, _at(today - timedelta(days=9), 17, 5)))

    # Autopilot's record: the daily job each morning, and the small things it fixed.
    for back in range(14, 0, -1):
        day = (now - timedelta(days=back)).date()
        start = datetime.combine(day, time(11, 0, 3), tzinfo=timezone.utc)
        conn.execute("INSERT INTO job_runs (job, run_date, started_at, finished_at, result) VALUES (?, ?, ?, ?, ?)",
                     ("daily", day.isoformat(), iso(start), iso(start + timedelta(seconds=4)),
                      f"reminders={rng.randint(0, 3)} digests={rng.randint(0, 2)} orgs=1 backup=none"))
        conn.execute("INSERT INTO job_runs (job, run_date, started_at, finished_at, result) VALUES (?, ?, ?, ?, ?)",
                     ("autopilot-daily", day.isoformat(), iso(start - timedelta(hours=10)),
                      iso(start - timedelta(hours=10) + timedelta(seconds=6)), "open=0"))
    for back, title in AUTOPILOT_FIXES:
        conn.execute("INSERT INTO autopilot_events (at, check_key, level, title) VALUES (?, 'fix', 'fixed', ?)",
                     (iso(now - timedelta(days=back, hours=rng.randint(0, 9))), title))
    return {"business": BUSINESS, "industries": [INDUSTRIES[i]["brand"] for i in READINGS],
            "owner": OWNER, "member": PHARMACIST, "checks": counts,
            "learners": kids, "audit_rows": len(audit)}


def date_of(text):
    return datetime.fromisoformat(text[:10]).date()


def _rules(industry_id):
    from .catalog import rules_for
    return rules_for(industry_id)


def _learner(conn, org_id, owner_id, spec, today, rng):
    t = academy.TRACKS[academy.DEFAULT_TRACK]
    added = today - timedelta(days=40)
    learner_id = conn.execute(
        "INSERT INTO learners (org_id, nickname, avatar, armo, track, track_chosen, created_by, created_at,"
        " device_epoch) VALUES (?, ?, ?, ?, ?, 1, ?, ?, ?)",
        (org_id, spec["nickname"], spec["avatar"], spec["armo"], t.key, owner_id, _at(added, 18, 0),
         new_device_epoch())).lastrowid
    levels = [(n, stage) for n, top in sorted(spec["stages"].items()) for stage in range(1, top + 1)]
    levels.sort(key=lambda ws: (ws[1] > 1, ws[0], ws[1]))   # each world's first stage, then deeper ones
    if spec["certificate"]:
        levels.append((academy.FINAL_WORLD.number, 1))
    # Spread over the days played: a streak ending today, and some earlier days.
    days = [today - timedelta(days=d) for d in range(spec["streak"])]
    days += [today - timedelta(days=d) for d in sorted(rng.sample(range(spec["streak"] + 1, 38), 8))]
    days.sort()
    per_day = {}
    for i, (number, stage) in enumerate(levels):
        day = days[min(len(days) - 1, i * len(days) // len(levels))]
        w = academy.world(number)
        total = academy.question_count(t, w, stage)
        score = rng.randint(academy.pass_mark(t, w, stage), total)
        stars = academy.stars_for(score, total, academy.pass_rate(t, w, stage))
        conn.execute("INSERT INTO learner_progress (learner_id, level, attempts, best_score, best_stars, completed_at)"
                     " VALUES (?, ?, ?, ?, ?, ?)",
                     (learner_id, academy.level_id(t, number, stage), rng.choice((1, 1, 1, 2)), score, stars,
                      _at(day, 16 + i % 4, (i * 7) % 60)))
        per_day[day] = per_day.get(day, 0) + 1
    conn.executemany("INSERT INTO learner_days (learner_id, day, levels) VALUES (?, ?, ?)",
                     [(learner_id, day.isoformat(), n) for day, n in per_day.items()])
    # One stage tried and not passed yet, where they are now.
    number, top = max(spec["stages"].items(), key=lambda item: item[1])
    w = academy.world(number)
    conn.execute("INSERT INTO learner_progress (learner_id, level, attempts, best_score, best_stars) VALUES (?, ?, 1, ?, 0)",
                 (learner_id, academy.level_id(t, number, top + 1), academy.pass_mark(t, w, top + 1) - 1))
    done = len(levels)
    return {"id": learner_id, "nickname": spec["nickname"], "levels": done,
            "certificate": academy.certificate_for(done, spec["certificate"], t)}


def _morning_digest(conn, cfg):
    """Today's reminder digest, through the real reminder code, kept in Radar
    and never sent: the addresses are made up."""
    from .reminders import run_reminders
    return run_reminders(conn, dict(cfg, SMTP_HOST=""))["digests"]


def _autopilot_pass(cfg):
    """One real Autopilot pass, as the server runs every 10 minutes: it makes
    the first backup and checks everything over. Its emails go to
    OPERATOR_EMAIL as usual (or the server log)."""
    from . import autopilot
    result = autopilot.run(dict(cfg), force=True)
    if result is None:
        return "Autopilot is running in the server right now."
    fixed = " ".join(result["fixed"]) or "nothing to fix."
    problems = len(result["problems"])
    return f"ran once now. {fixed} {problems} problem{'s' if problems != 1 else ''} for a person"
