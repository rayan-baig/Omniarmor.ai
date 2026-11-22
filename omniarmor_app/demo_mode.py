# -*- coding: utf-8 -*-
"""Try OmniArmor without signing up: a business demo and a classroom demo,
both with pretend data.

    /demo/business     a restaurant: a few checks done, one overdue, this
                       morning's reminder in Radar and a report ready
    /demo/classroom    a teacher's class: pretend first names, the class
                       progress view, join codes and a sample lesson
    /demo/salon, /demo/tattoo, /demo/gym, /demo/shop
                       a salon, a tattoo studio, a gym and a shop, each with
                       its own checklist (SalonArmor, InkArmor, GymArmor; a
                       shop's card payments and online sales) and an
                       employer's: one check overdue, one due soon, a few
                       done, so each trade page's demo matches the trade

How it stays safe:

- Opening a demo puts a demo pass in the visitor's session, and nothing else:
  no account, no workspace. A pass lasts PASS_MINUTES. Opening a demo is
  limited to STARTS_PER_HOUR from one address (security.rate_limited).
- On the app's own pages (DEMO_BLUEPRINTS) a visitor with a pass sees the
  demo's pretend owner and workspace. Every request works on its own fresh
  copy of the demo database, made in memory from a template, and the copy is
  thrown away when the request ends. Nothing a page writes reaches the real
  database, and the next page starts from the demo as it was.
- Forms are refused with a plain message ("nothing is saved in the demo"),
  except the Academy quiz (POST_ALLOWED), whose answers are graded in the
  throwaway copy so a teacher can try a lesson to the end.
- Nothing is sent. The pretend people have .example addresses, which never
  receive email; notify.notify() refuses to send inside a demo; and the
  daily jobs only ever open the real database, which holds no demo.
- The template is rebuilt from today's date every REBUILD_EVERY, so the
  dates stay true ("overdue by 2 days") however long the server runs.

Every name in the demo is invented. The schools and businesses are not
real ones.
"""

import random
import sqlite3
import threading
import time
from datetime import datetime, time as clock, timedelta
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

from flask import (Blueprint, abort, current_app, flash, g, redirect, render_template, request, session,
                   url_for)

from . import academy, armo, demo, usage
from .words import plural
from .catalog import INDUSTRIES, counts_time, date_mode, find_rule, rules_for
from .db import iso, migrate, utcnow
from .security import client_ip, new_device_epoch, rate_limited, record_event
from .tracking import _describe

bp = Blueprint("demo", __name__)

KINDS = ("business", "classroom", "salon", "tattoo", "gym", "shop")
PASS_MINUTES = 30
STARTS_PER_HOUR = 20
REBUILD_EVERY = timedelta(hours=1)
# The app's pages a demo pass opens. Everything else (sign-up, sign-in, the
# public pages, the kids' join page, the API) sees an ordinary visitor.
DEMO_BLUEPRINTS = {"app", "academy", "classes", "armo", "plan"}
# The only forms that work in a demo: the Academy's quiz and practice,
# graded in the request's own throwaway copy.
POST_ALLOWED = {"academy.play", "academy.practice"}
REFUSED = ("This is the demo, with pretend data, so nothing is saved and no emails go out."
           " Start your free trial to save your own.")

TIMEZONE = "America/New_York"
DOMAIN = "demo.example"          # .example is reserved: never a real address
BUSINESS = "Sample Kitchen (demo)"
OWNER = ("Casey Marlowe", f"casey@{DOMAIN}")
COOK = ("Jules Okafor", f"jules@{DOMAIN}")
SCHOOL = "Sample School (demo)"
TEACHER = ("Taylor Brooks", f"taylor@{DOMAIN}")
CLASS_NAME = "Room 12"
RESTAURANT, EMPLOYER = 2, 30     # RestoArmor, HRArmor
SCHOOL_INDUSTRY = 51             # SchoolSafetyArmor
WORKSPACE_AGE_DAYS = 6
# The trade demos: kind -> (the trade's industries, its own first; the
# workspace's name; the owner; what the demo page calls it; its trade page).
# Each also has HRArmor, as a shop with staff does; the readings of its own
# checklist are planned by _trade_plan.
TRADE_DEMOS = {
    "salon": ((52, EMPLOYER), "Sample Salon (demo)", ("Robin Vale", f"robin@{DOMAIN}"), "A salon",
              "salons-and-barbershops"),
    "tattoo": ((53, EMPLOYER), "Sample Tattoo Studio (demo)", ("Morgan Reyes", f"morgan@{DOMAIN}"),
               "A tattoo studio", "tattoo-and-piercing-studios"),
    "gym": ((54, EMPLOYER), "Sample Gym (demo)", ("Jordan Hale", f"jordan@{DOMAIN}"), "A gym",
            "gyms-and-fitness-studios"),
    "shop": ((50, EMPLOYER, 32), "Sample Shop (demo)", ("Sam Ortiz", f"sam@{DOMAIN}"), "A shop",
             "shops-and-retail-stores"),
}
TRADE_DEMO_FOR = {slug: kind for kind, (_, _, _, _, slug) in TRADE_DEMOS.items()}

# The restaurant's readings (demo.reading_for explains the shapes): a few
# checks done, one overdue (the 7-day date marking, last done 9 days ago),
# an I-9 due tomorrow, and the rest still waiting for a first reading.
READINGS = {
    RESTAURANT: {
        "cold_holding": ("number", 38),
        "hot_holding": ("number", 141),
        "date_marking": ("ago", 9, "BLOCKED"),
        "handwashing_sink": ("answer", "yes"),
        "certified_food_manager": ("answer", "yes"),
        "overtime_pay": ("answer", "yes"),
    },
    EMPLOYER: {
        "i9_section_2": ("ago", 1, "WARNING"),
        "cobra_election_notice": ("ago", 10, "CLEARED"),
        "minimum_wage": ("number", 15.5),
        "hours_records": ("answer", "yes"),
    },
}

# The restaurant's checks with one entry per item (catalog.MULTI_CHECKS): the
# first entry's name, and more entries as (check, name, reading, days ago).
ENTRY_NAMES = {"cold_holding": "Walk-in cooler", "hot_holding": "Soup well", "date_marking": "Opened ham"}
MORE_ENTRIES = (
    ("cold_holding", "Prep fridge", 39, None),
    ("cold_holding", "Bar fridge", 37, None),
    ("date_marking", "Chicken salad", None, 2),
    ("date_marking", "Cut melon", None, 5),
)

# The class: pretend first names, and the lessons each one has passed in each
# world of the Classroom track (world number: lessons). One student hasn't
# started, so the sample lesson is a real first lesson.
STUDENTS = [
    ("Ava", "rocket", {60: 4, 2: 4, 61: 3, 62: 2, 7: 2, 63: 1}, 5),
    ("Ben", "star", {60: 4, 2: 2, 61: 1}, 3),
    ("Chloe", "bolt", {60: 4, 2: 3, 61: 2, 62: 1}, 4),
    ("Dev", "crown", {60: 2, 2: 1}, 1),
    ("Ella", "gem", {60: 3, 2: 2, 61: 1}, 2),
    ("Finn", "shield", {60: 1}, 1),
    ("Grace", "paw", {60: 4, 2: 3, 61: 2, 62: 1, 7: 1}, 3),
    ("Hugo", "leaf", {}, 0),
]
SAMPLE_STUDENT = "Hugo"
SHOWCASE_STUDENT = "Ava"

_lock = threading.Lock()


# --- The demo database ---------------------------------------------------------------

def _at(day, hour, minute=0):
    return iso(datetime.combine(day, clock(hour, minute), tzinfo=ZoneInfo(TIMEZONE)))


def _user(conn, person, created, armo_key="chief"):
    # No password: the demo's people only exist in the demo database, which
    # sign-in never reads, and nobody can sign in as them.
    return conn.execute(
        "INSERT INTO users (email, name, password_hash, created_at, last_seen_on, armo, email_reminders)"
        " VALUES (?, ?, '!', ?, ?, ?, 1)", (person[1], person[0], created, created[:10], armo_key)).lastrowid


def _org(conn, name, created, trial_ends):
    return conn.execute("INSERT INTO orgs (name, timezone, created_at, academy_trial_ends) VALUES (?, ?, ?, ?)",
                        (name, TIMEZONE, created, trial_ends)).lastrowid


def _audit(conn, org_id, user_id, name, at, action, summary, industry_id=None, key=None, before=None, after=None):
    conn.execute("INSERT INTO audit (org_id, user_id, user_name, at, action, industry_id, rule_key, before, after,"
                 " summary) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                 (org_id, user_id, name, at, action, industry_id, key, before, after, summary))


def _fill_business(conn, cfg, now, rng):
    today = now.astimezone(ZoneInfo(TIMEZONE)).date()
    opened = today - timedelta(days=WORKSPACE_AGE_DAYS)
    created = _at(opened, 9, 5)
    trial_ends = iso(now + timedelta(days=max(1, cfg["ACADEMY_TRIAL_DAYS"] - WORKSPACE_AGE_DAYS)))
    owner = _user(conn, OWNER, created)
    org = _org(conn, BUSINESS, created, trial_ends)
    conn.execute("INSERT INTO memberships (user_id, org_id, role, created_at) VALUES (?, ?, 'owner', ?)",
                 (owner, org, created))
    conn.executemany("INSERT INTO org_industries (org_id, industry_id) VALUES (?, ?)",
                     [(org, RESTAURANT), (org, EMPLOYER)])
    joined = _at(opened + timedelta(days=1), 8, 40)
    cook = _user(conn, COOK, joined, "funny")
    conn.execute("INSERT INTO memberships (user_id, org_id, role, created_at) VALUES (?, ?, 'member', ?)",
                 (cook, org, joined))
    people = {owner: OWNER[0], cook: COOK[0]}
    _audit(conn, org, owner, OWNER[0], created, "workspace", f"Workspace created with {plural(2, 'industry')}")
    _audit(conn, org, owner, OWNER[0], _at(opened, 9, 30), "team", "Invite link created (valid 7 days)")
    _audit(conn, org, cook, COOK[0], joined, "team", f"{COOK[0]} joined the team")
    for industry_id, plan in READINGS.items():
        for n, (key, spec) in enumerate(plan.items()):
            rule = find_rule(industry_id, key)
            row = demo.reading_for(industry_id, rule, spec, today)
            who = owner if industry_id == EMPLOYER or n % 2 == 0 else cook
            at = _at(opened + timedelta(days=rng.randint(0, WORKSPACE_AGE_DAYS - 1)), rng.randint(9, 16),
                     rng.randint(0, 59))
            conn.execute(
                "INSERT INTO items (org_id, industry_id, rule_key, value_num, value_bool, value_date, updated_at,"
                " updated_by, updated_by_name) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (org, industry_id, key, row["value_num"], row["value_bool"], row["value_date"], at, who,
                 people[who]))
            after = _describe(rule, row)
            _audit(conn, org, who, people[who], at, "reading", f"{rule.title}: no reading → {after}", industry_id,
                   key, "no reading", after)
    # Checks with one entry per item: the first entry's name, and a few more.
    for key, label in ENTRY_NAMES.items():
        conn.execute("UPDATE items SET label = ? WHERE org_id = ? AND industry_id = ? AND rule_key = ?",
                     (label, org, RESTAURANT, key))
    stamp = _at(today, 8, 15)
    for key, label, value_num, days_ago in MORE_ENTRIES:
        value_date = None if days_ago is None else (today - timedelta(days=days_ago)).isoformat()
        conn.execute("INSERT INTO check_entries (org_id, industry_id, rule_key, label, value_num, value_date,"
                     " created_at, updated_at, updated_by, updated_by_name) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                     (org, RESTAURANT, key, label, value_num, value_date, stamp, stamp, cook, people[cook]))
    conn.execute("INSERT INTO illness_log (org_id, industry_id, rule_key, person, reported, action, reported_on,"
                 " created_at, created_by, created_by_name) VALUES (?, ?, 'sick_employee_excluded', 'J.R.',"
                 " 'vomiting', 'sent_home', ?, ?, ?, ?)",
                 (org, RESTAURANT, (today - timedelta(days=3)).isoformat(), stamp, owner, people[owner]))
    conn.commit()
    return {"user": owner, "org": org}


def _trade_plan(industry_id, today, levels=("BLOCKED", "WARNING", "CLEARED", "CLEARED")):
    """A trade demo's readings for its own checklist: the first dated check
    overdue, the next due soon, two more done, the first two yes-or-no
    checks answered well, and the rest waiting for a first reading. Each
    reading is found by trying it (demo.reading_for), so it always shows the
    level it is meant to."""
    plan = {}
    # Tasks counted from the day they were done come first: an overdue
    # cleaning log shows the idea better than an expired license.
    dated = sorted((r for r in rules_for(industry_id) if date_mode(r) and not counts_time(r)),
                   key=lambda r: date_mode(r) != "since")
    for rule, level in zip(dated, levels):
        kind = "ago" if date_mode(rule) == "since" else "in"
        start = 1 if level == "CLEARED" else int(rule.limit or 0)
        try:
            demo.reading_for(industry_id, rule, (kind, start, level), today)
        except ValueError:
            continue
        plan[rule.key] = (kind, start, level)
    yes_no = [r for r in rules_for(industry_id) if r.kind in ("required", "forbidden")][:2]
    for rule in yes_no:
        plan[rule.key] = ("answer", "yes" if rule.kind == "required" else "no")
    return plan


def _fill_trade(conn, cfg, now, rng, kind):
    """A trade demo's workspace: its own checklist and an employer's, with
    a few checks done (_trade_plan), one overdue and one due soon."""
    industries, name, person, _, _ = TRADE_DEMOS[kind]
    industry_id = industries[0]
    today = now.astimezone(ZoneInfo(TIMEZONE)).date()
    opened = today - timedelta(days=WORKSPACE_AGE_DAYS)
    created = _at(opened, 9, 5)
    trial_ends = iso(now + timedelta(days=max(1, cfg["ACADEMY_TRIAL_DAYS"] - WORKSPACE_AGE_DAYS)))
    owner = _user(conn, person, created)
    org = _org(conn, name, created, trial_ends)
    conn.execute("INSERT INTO memberships (user_id, org_id, role, created_at) VALUES (?, ?, 'owner', ?)",
                 (owner, org, created))
    conn.executemany("INSERT INTO org_industries (org_id, industry_id) VALUES (?, ?)",
                     [(org, i) for i in industries])
    _audit(conn, org, owner, person[0], created, "workspace", f"Workspace created with {plural(len(industries), 'industry')}")
    own = [i for i in industries if i != EMPLOYER]
    plans = {i: _trade_plan(i, today) if n == 0 else _trade_plan(i, today, ("CLEARED", "CLEARED"))
             for n, i in enumerate(own)}
    plans[EMPLOYER] = {"i9_section_2": ("ago", 1, "WARNING"), "hours_records": ("answer", "yes"),
                       **({"overtime_pay": ("answer", "yes")} if industry_id == EMPLOYER else {})}
    for ind, plan in plans.items():
        for key, spec in plan.items():
            rule = find_rule(ind, key)
            row = demo.reading_for(ind, rule, spec, today)
            at = _at(opened + timedelta(days=rng.randint(0, WORKSPACE_AGE_DAYS - 1)), rng.randint(9, 16),
                     rng.randint(0, 59))
            conn.execute(
                "INSERT INTO items (org_id, industry_id, rule_key, value_num, value_bool, value_date, updated_at,"
                " updated_by, updated_by_name) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (org, ind, key, row["value_num"], row["value_bool"], row["value_date"], at, owner, person[0]))
            after = _describe(rule, row)
            _audit(conn, org, owner, person[0], at, "reading", f"{rule.title}: no reading → {after}", ind, key,
                   "no reading", after)
    conn.commit()
    return {"user": owner, "org": org, "industry": industry_id}


def _fill_classroom(conn, cfg, now, rng):
    today = now.astimezone(ZoneInfo(TIMEZONE)).date()
    opened = today - timedelta(days=12)
    created = _at(opened, 15, 10)
    teacher = _user(conn, TEACHER, created, "sweet")
    org = _org(conn, SCHOOL, created, iso(now + timedelta(days=2)))
    conn.execute("UPDATE orgs SET kind = 'school' WHERE id = ?", (org,))
    conn.execute("INSERT INTO memberships (user_id, org_id, role, created_at) VALUES (?, ?, 'owner', ?)",
                 (teacher, org, created))
    conn.execute("INSERT INTO org_industries (org_id, industry_id) VALUES (?, ?)", (org, SCHOOL_INDUSTRY))
    pilot_start = _at(opened, 15, 20)
    conn.execute("UPDATE orgs SET pilot_started_at = ?, pilot_ends_at = ? WHERE id = ?",
                 (pilot_start, iso(datetime.fromisoformat(pilot_start)
                                   + timedelta(days=cfg["CLASSROOM_PILOT_DAYS"])), org))
    conn.execute("UPDATE users SET pilot_used_at = ? WHERE id = ?", (pilot_start, teacher))
    class_id = conn.execute("INSERT INTO classes (org_id, name, leaderboard, created_by, created_at)"
                            " VALUES (?, ?, 1, ?, ?)", (org, CLASS_NAME, teacher, _at(opened, 15, 25))).lastrowid
    _audit(conn, org, teacher, TEACHER[0], created, "workspace", f"Workspace created with {plural(1, 'industry')}")
    _audit(conn, org, teacher, TEACHER[0], pilot_start, "workspace",
           f"Free classroom trial started ({cfg['CLASSROOM_PILOT_DAYS']} days)")
    _audit(conn, org, teacher, TEACHER[0], _at(opened, 15, 25), "workspace", f"Class added: {CLASS_NAME}")
    ids = {}
    expires = iso(now + timedelta(days=5))
    for n, (name, picture, stages, streak) in enumerate(STUDENTS, 1):
        if stages:
            spec = {"nickname": name, "avatar": picture, "armo": armo.DEFAULT_KID, "certificate": False,
                    "streak": streak, "stages": stages}
            learner = demo._learner(conn, org, teacher, spec, today, rng, academy.CLASSROOM)["id"]
        else:
            learner = conn.execute(
                "INSERT INTO learners (org_id, nickname, avatar, armo, track, track_chosen, created_by, created_at,"
                " device_epoch) VALUES (?, ?, ?, ?, ?, 1, ?, ?, ?)",
                (org, name, picture, armo.DEFAULT_KID, academy.CLASSROOM.key, teacher, _at(opened, 15, 30),
                 new_device_epoch())).lastrowid
        conn.execute("UPDATE learners SET class_id = ? WHERE id = ?", (class_id, learner))
        # Join codes that can't work anywhere: real ones never hold an O or a 0.
        conn.execute("INSERT INTO join_codes (learner_id, code, expires_at) VALUES (?, ?, ?)",
                     (learner, f"KID-DEMO{n:04d}", expires))
        ids[name] = learner
    conn.commit()
    return {"user": teacher, "org": org, "class": class_id, "sample": ids[SAMPLE_STUDENT],
            "showcase": ids[SHOWCASE_STUDENT]}


def build(cfg, now=None):
    """A new demo database, in memory, as of now. Returns (connection, facts)."""
    now = now or utcnow()
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    migrate(conn, cfg["ACADEMY_TRIAL_DAYS"])
    rng = random.Random(2026)
    facts = {"business": _fill_business(conn, cfg, now, rng), "classroom": _fill_classroom(conn, cfg, now, rng),
             "built": now}
    for kind in TRADE_DEMOS:
        facts[kind] = _fill_trade(conn, cfg, now, rng, kind)
    conn.commit()
    # This morning's reminder digests, through the real reminder code, kept in
    # Reminders and never sent (no mail server, .example addresses).
    from .reminders import run_reminders
    run_reminders(conn, dict(cfg, SMTP_HOST=""))
    return conn, facts


def _template(app):
    """The app's demo template, rebuilt when it is REBUILD_EVERY old. Call with _lock held."""
    held = app.extensions.get("omniarmor_demo")
    if held is None or utcnow() - held[1]["built"] >= REBUILD_EVERY:
        if held is not None:
            held[0].close()
        held = build(app.config)
        app.extensions["omniarmor_demo"] = held
    return held


def facts():
    with _lock:
        return _template(current_app._get_current_object())[1]


def sandbox():
    """This request's own copy of the demo database, thrown away when the
    request ends (db.close_db closes it, and an in-memory database is gone
    once closed)."""
    copy = sqlite3.connect(":memory:")
    with _lock:
        _template(current_app._get_current_object())[0].backup(copy)
    copy.row_factory = sqlite3.Row
    copy.execute("PRAGMA foreign_keys = ON")
    return copy


# --- The demo pass ------------------------------------------------------------------

def _pass():
    """The session's demo kind while its pass is good, else None."""
    kind = session.get("demo")
    until = session.get("demo_until")
    if kind not in KINDS or not isinstance(until, int) or until < time.time():
        return None
    return kind


def _in_scope():
    return (request.blueprint or "") in DEMO_BLUEPRINTS


def load():
    """security.load_user's demo branch: on the app's pages, a visitor with a
    good pass is the demo's pretend owner. Returns True when it set g.user."""
    if not _in_scope():
        return False
    kind = _pass()
    if kind is None:
        session.pop("demo", None)
        session.pop("demo_until", None)
        g.demo_ended = True
        return False
    g.demo = kind
    from .db import get_db
    conn = get_db()
    ids = facts()[kind]
    g.user = conn.execute("SELECT * FROM users WHERE id = ?", (ids["user"],)).fetchone()
    g.org = conn.execute("SELECT orgs.*, 'owner' AS role FROM orgs WHERE id = ?", (ids["org"],)).fetchone()
    g.role = "owner"
    return True


def _back():
    """Where a refused form goes: the page it came from, on this site."""
    ref = urlsplit(request.referrer or "")
    if ref.netloc == request.host and ref.path.startswith("/app"):
        return ref.path + (f"?{ref.query}" if ref.query else "")
    return url_for("app.overview")


def guard():
    """Runs before every view, after the CSRF check: refuses a demo's forms,
    and sends a visitor whose pass ran out to the demo page."""
    if g.get("demo_ended"):
        flash(f"The demo ends after {PASS_MINUTES} minutes. Open it again, or start your free trial.", "ok")
        return redirect(url_for("demo.index"))
    if g.get("demo") is None:
        return None
    if request.method == "POST" and request.endpoint not in POST_ALLOWED:
        flash(REFUSED, "error")
        return redirect(_back(), code=303)
    if request.endpoint == "plan.plan_page" and request.args:
        return redirect(url_for("plan.plan_page"))
    return None


def active():
    """Whether this request is inside a demo (for notify and the templates)."""
    try:
        return g.get("demo") is not None
    except RuntimeError:     # no request or app context: a job, never a demo
        return False


# --- The tour ------------------------------------------------------------------------

def tour(kind):
    """The demo's pages in order: (endpoint, url, title, what it shows)."""
    ids = facts()[kind]
    if kind in TRADE_DEMOS:
        industry = next((i for i in TRADE_DEMOS[kind][0] if i != EMPLOYER), TRADE_DEMOS[kind][0][0])
        return [
            ("app.overview", url_for("app.overview"), "Dashboard",
             "What needs attention, what's coming due and what to do next, on one page."),
            ("app.industry", url_for("app.industry", industry_id=industry), "Your trade's checklist",
             f"{INDUSTRIES[industry]['brand']}: each check says what to do and which rule it comes from. Enter a"
             " date or an answer once and OmniArmor counts the days."),
            ("app.notifications", url_for("app.notifications"), "Reminders",
             "This morning's reminder email. In the demo it is kept here and never sent."),
            ("app.report", url_for("app.report"), "Report",
             "Every check's status in one report, to print or download for an inspector."),
        ]
    if kind == "business":
        return [
            ("app.overview", url_for("app.overview"), "Dashboard",
             "What needs attention, what's coming due and what to do next, on one page."),
            ("app.industry", url_for("app.industry", industry_id=RESTAURANT), "A checklist",
             "Each check says what to do and which rule it comes from. Enter a date or an answer once and"
             " OmniArmor counts the days."),
            ("app.notifications", url_for("app.notifications"), "Reminders",
             "This morning's reminder email. In the demo it is kept here and never sent."),
            ("app.report", url_for("app.report"), "Report",
             "Every check's status in one report, to print or download for an inspector."),
        ]
    first = academy.CLASSROOM.topic_worlds[0].number
    return [
        ("classes.index", url_for("classes.index"), "Classes",
         f"Your classes and the free {current_app.config['CLASSROOM_PILOT_DAYS']} days. The lessons are written"
         f" for {academy.CLASS_GRADES} ({academy.CLASS_AGES})."),
        ("classes.class_page", url_for("classes.class_page", class_id=ids["class"]), "Class progress",
         "Lessons done by each student, and the class total. Students are added by first name or nickname only."),
        ("classes.join_codes", url_for("classes.join_codes", class_id=ids["class"]), "Join codes",
         "One code per student, to print and hand out. Students don't need an email or a password."),
        ("academy.progress_report", url_for("academy.progress_report", learner_id=ids["showcase"]),
         "One student", "One student's lessons and quiz scores."),
        ("academy.play", url_for("academy.play", learner_id=ids["sample"], world_number=first, stage=1),
         "A sample lesson", "A real lesson: read the short cards, then try the quiz. Nothing is saved."),
    ]


def signup_url(kind):
    if kind == "classroom":
        return url_for("auth.signup", then="classes")
    if kind in TRADE_DEMOS:
        return url_for("auth.signup", industry=list(TRADE_DEMOS[kind][0]))
    return url_for("auth.signup", industry=RESTAURANT)


@bp.app_context_processor
def demo_context():
    kind = g.get("demo")
    if kind is None:
        return {}
    steps = tour(kind)
    here = next((n for n, step in enumerate(steps) if step[0] == request.endpoint), None)
    text = None if here is None else steps[here][3]
    title = None if here is None else steps[here][2]
    shown = (request.view_args or {}).get("industry_id")
    if (here is not None and request.endpoint == "app.industry" and shown in INDUSTRIES
            and steps[here][1] != url_for("app.industry", industry_id=shown)):
        # Another of the workspace's checklists (HRArmor in a salon): the
        # step's words name the page's own checklist, not the trade's.
        text = (f"{INDUSTRIES[shown]['brand']}: each check says what to do and which rule it comes from. Enter a"
                " date or an answer once and OmniArmor counts the days.")
        title = f"The {INDUSTRIES[shown]['brand']} checklist"
    return {"demo_bar": {
        "kind": kind,
        "steps": [{"url": url, "title": title, "current": n == here} for n, (_, url, title, _) in enumerate(steps)],
        "here": None if here is None else {"number": here + 1, "title": title, "text": text},
        "next": None if here is None or here + 1 >= len(steps) else {"url": steps[here + 1][1],
                                                                     "title": steps[here + 1][2]},
        "total": len(steps),
        "signup": signup_url(kind),
    }}


# --- Pages ----------------------------------------------------------------------------

@bp.route("/demo")
def index():
    if g.get("kid") is not None:
        return redirect(url_for("academy.level_map", learner_id=g.kid["id"]))
    return render_template("demo/index.html", minutes=PASS_MINUTES, limited=False, class_grades=academy.CLASS_GRADES,
                           trades=TRADE_DEMOS)


@bp.route("/demo/<kind>")
def start(kind):
    """Opens a demo: a pass in the session, then the tour's first page."""
    if kind not in KINDS:
        abort(404)
    if g.get("user") is not None or g.get("kid") is not None:
        flash("You're signed in, so this is your own workspace. Sign out to see the demo.", "ok")
        return redirect(url_for("app.overview") if g.get("user") is not None else url_for("public.home"))
    first = url_for("classes.index") if kind == "classroom" else url_for("app.overview")
    if _pass() == kind:
        return redirect(first)
    key = f"demo-ip:{client_ip()}"
    if rate_limited([(key, STARTS_PER_HOUR)], timedelta(hours=1)):
        flash(f"The demo was opened {STARTS_PER_HOUR} times from here in the last hour. Please try again later,"
              " or start your free trial.", "error")
        return render_template("demo/index.html", minutes=PASS_MINUTES, limited=True,
                               class_grades=academy.CLASS_GRADES, trades=TRADE_DEMOS), 429
    record_event([key])
    from .db import get_db
    usage.count(get_db(), "demos_opened")
    keep = session.get("_csrf")
    session.clear()
    if keep:
        session["_csrf"] = keep
    session["demo"] = kind
    session["demo_until"] = int(time.time()) + PASS_MINUTES * 60
    return redirect(first)


@bp.route("/demo/leave", methods=["POST"])
def leave():
    if g.get("kid") is not None:
        return redirect(url_for("academy.level_map", learner_id=g.kid["id"]))
    if g.get("user") is not None:
        return redirect(url_for("app.overview"))
    session.pop("demo", None)
    session.pop("demo_until", None)
    flash("You've left the demo. Nothing from it was kept.", "ok")
    return redirect(url_for("public.home"))

