# -*- coding: utf-8 -*-
"""The Future Owner Academy for classrooms: a school or a teacher runs the
Academy for a whole class or an entrepreneurship club.

Safe by design for kids' privacy:

- A teacher adds students by first name or nickname only. There is no field
  for a student's email, birthdate, photo or anything else, and a name that
  looks like an email address is refused. Each student gets one of the
  Academy's drawn pictures, never a photo.
- Students never type anything that is shown to anyone: they pick answers.
- A student sees only their own lessons and, when the teacher leaves it on,
  their own class's leaderboard (first names or nicknames and lessons done).
  Never another class. Academy friends and duels, which can reach other
  families, are off for students in a class.
- The teacher's class view and the trial report are for the workspace's
  grown-ups only. The trial report shows totals only, no student names, so
  it can go to the school office.

Plans, limits and the pilot are in plans.py (class_limits, pilot_status).
"""

import re
from datetime import timedelta

from . import academy, plans
from .db import iso, now_iso, utcnow
from .trades import SCHOOL_INDUSTRY

MAX_NAME = 30               # a student's first name or nickname
MAX_CLASS_NAME = 40         # "Room 12", "Entrepreneurship Club"
MAX_ADD_AT_ONCE = plans.CLASS_SIZE
MAX_CLASSES = 100           # classes in one workspace, on any plan (Whole school's "any number")
CLASSES_PER_HOUR = 20       # classes one workspace can add in an hour
_LOOKS_LIKE_EMAIL = re.compile(r"@|\.(com|org|net|edu)\b", re.I)


SCHOOL_KIND = "school"     # orgs.kind for a school's workspace (a teacher's)


def is_class_workspace(org):
    """Whether this is a school's workspace, made for running the Academy in
    classes (orgs.kind, set by the teacher sign-up): its menus, plan page and
    lessons are a classroom's, not a business's."""
    try:
        return org is not None and org["kind"] == SCHOOL_KIND
    except (KeyError, IndexError):
        return False


def on_whole_school(org, access=None):
    """Whether a school's workspace pays for Whole school, the plan that
    includes the school safety checklist. Without it a teacher's menus leave
    the checklist out (base.html) and its first steps aren't offered."""
    access = access or plans.access(org)
    return access["paid"] and access["kind"] == plans.SCHOOL.key and not access["paused"]


def school_checklist_hidden(org, access=None):
    """Whether this workspace must not show the school safety checklist: a
    school's workspace on the free trial or Classroom. Armo, Reminders, the
    Report and the menus leave it out, and its page sends the teacher back to
    their classes (views.industry)."""
    return is_class_workspace(org) and not on_whole_school(org, access)


def invoice_email(cfg):
    """Where a school writes to pay by invoice."""
    from .config import support_email
    return cfg.get("SCHOOL_INVOICE_EMAIL") or support_email(cfg)


def public_facts(cfg):
    """What the Academy for schools page and the classes page say about the
    plans and the pilot, read from plans.py and the settings."""
    plus_academy = plans.yearly_dollars(plans.PLUS.dollars - plans.PRO.dollars)
    return {
        "class_size": plans.CLASS_SIZE,
        "pilot_days": cfg["CLASSROOM_PILOT_DAYS"],
        "pilot_classes": plans.PILOT_CLASSES,
        "classroom": plans.CLASSROOM,
        "school": plans.SCHOOL,
        "plans": list(plans.CLASSROOM_PLANS.values()),
        "plus": plans.PLUS,
        "plus_academy_yearly": plans.price_label(plus_academy, plans.YEAR, per=False),
        "online": {key: bool(cfg.get(p.price_setting) and cfg.get("STRIPE_SECRET_KEY"))
                   for key, p in plans.CLASSROOM_PLANS.items()},
        "invoice_email": invoice_email(cfg),
        # The Classroom track, which every student in a class learns on.
        "track": academy.CLASSROOM,
        "class_worlds": len(academy.CLASSROOM.topics),
        "class_lessons": academy.CLASSROOM.total,
        "lesson_questions": academy.LESSON_QUESTIONS,
        "lesson_minutes": academy.LESSON_MINUTES,
        "class_business": academy.CLASS_BUSINESS,
        "grades": academy.CLASS_GRADES,
        "ages": academy.CLASS_AGES,
        "first_lessons": len(academy.CLASSROOM.topics),
        "school_industry": SCHOOL_INDUSTRY,
    }


# --- Names ---------------------------------------------------------------------------

def clean_student_name(text):
    """A first name or nickname, or None: plain text up to MAX_NAME
    characters, and nothing that looks like an email address."""
    value = (text or "").strip()
    value = re.sub(r"\s+", " ", value)
    if not value or len(value) > MAX_NAME or any(ord(c) < 32 or ord(c) == 127 for c in value):
        return None
    if _LOOKS_LIKE_EMAIL.search(value):
        return None
    return value


def parse_names(text):
    """The names a teacher typed, one per line (or separated by commas): a
    list of (name or None, what was typed), empty lines left out."""
    parts = re.split(r"[\n,;]", text or "")
    return [(clean_student_name(p), p.strip()) for p in parts if p.strip()]


def why_not_a_name(typed):
    """Why clean_student_name refused what was typed, in plain words."""
    value = re.sub(r"\s+", " ", (typed or "").strip())
    if _LOOKS_LIKE_EMAIL.search(value):
        return "looks like an email address: first names or nicknames only"
    if len(value) > MAX_NAME:
        return f"is longer than {MAX_NAME} characters: try a shorter name or nickname"
    return "has characters that can't be used in a name"


def looks_like_full_name(name):
    """Whether a name looks like a first and last name ("Ava Thompson"):
    two or more words, the last longer than an initial. "Noah K" and "Jo B."
    are fine; "Mary Jane" is asked about, as it may be one first name."""
    words = (name or "").split()
    last = words[-1].rstrip(".") if words else ""
    return len(words) >= 2 and len(last) >= 2 and last.isalpha()


def suggest_short_name(name):
    """A first name and last initial for a name that looks like a full name:
    "Ava Thompson" becomes "Ava T"."""
    words = name.split()
    return f"{words[0]} {words[-1][0].upper()}"


def sort_names(parsed, taken, room, confirmed=False):
    """Which of the names a teacher typed (parse_names) can be added to a
    class that already has the names in `taken` (lowercase) and room for
    `room` more: (names to add, [(what was typed, why it wasn't added)],
    [names to ask about]). A name that looks like a first and last name is
    not added: the teacher is asked first (looks_like_full_name), unless the
    names come from that question (confirmed). One name that can't be added
    never stops the others."""
    added, rejected, ask, seen = [], [], [], set()
    for name, typed in parsed:
        if name is None:
            rejected.append((typed, why_not_a_name(typed)))
            continue
        if not confirmed and looks_like_full_name(name):
            ask.append(name)
            continue
        key = name.lower()
        if key in taken:
            rejected.append((typed, f"is already in this class: add a last initial to tell them apart, like"
                                    f" {name} B"))
        elif key in seen:
            rejected.append((typed, f"was typed twice: add a last initial to tell them apart, like {name} B"))
        elif len(added) >= room:
            rejected.append((typed, "didn't fit: the class is full"))
        else:
            seen.add(key)
            added.append(name)
    return added, rejected, ask


# --- Reading classes -------------------------------------------------------------------

def classes(conn, org_id):
    """The workspace's classes, oldest first, with their student counts."""
    return conn.execute(
        "SELECT classes.*, (SELECT COUNT(*) FROM learners WHERE learners.class_id = classes.id) AS students"
        " FROM classes WHERE org_id = ? ORDER BY created_at, id", (org_id,)).fetchall()


def class_or_none(conn, org_id, class_id):
    return conn.execute("SELECT * FROM classes WHERE id = ? AND org_id = ?", (class_id, org_id)).fetchone()


def students(conn, class_id):
    return conn.execute("SELECT * FROM learners WHERE class_id = ? ORDER BY nickname COLLATE NOCASE, id",
                        (class_id,)).fetchall()


def students_without_code(conn, class_id):
    """The class's students who have no way in yet: no join code that still
    works, and not joined on a device (learners.joined_at). A student added
    after the slips were printed is one of them; a student whose slip is
    still waiting, or who already joined, is not."""
    return conn.execute(
        "SELECT * FROM learners WHERE class_id = ? AND joined_at IS NULL AND id NOT IN"
        " (SELECT learner_id FROM join_codes WHERE expires_at > ?) ORDER BY nickname COLLATE NOCASE, id",
        (class_id, now_iso())).fetchall()


def getting_started(conn, org, limits, class_rows):
    """A teacher's first steps, for the classes page: start the pilot (or a
    plan), create a class, add students, share the join codes, and a
    student's first lesson. Each is ticked from what is saved; None once
    every step is done, so the list disappears."""
    in_class = "SELECT id FROM learners WHERE org_id = ? AND class_id IS NOT NULL"
    students_in = conn.execute(f"SELECT COUNT(*) FROM ({in_class})", (org["id"],)).fetchone()[0]
    codes = conn.execute(f"SELECT 1 FROM join_codes WHERE learner_id IN ({in_class}) LIMIT 1",
                         (org["id"],)).fetchone() is not None
    played = conn.execute(f"SELECT 1 FROM learner_progress WHERE learner_id IN ({in_class}) LIMIT 1",
                          (org["id"],)).fetchone() is not None
    lesson = conn.execute(f"SELECT 1 FROM learner_progress WHERE learner_id IN ({in_class}) AND best_stars >= 1"
                          " LIMIT 1", (org["id"],)).fetchone() is not None
    first = class_rows[0] if class_rows else None
    can_pilot = pilot_available(conn, org)
    items = [
        {"key": "pilot", "label": ("Start the free trial" if can_pilot or limits["pilot"]["state"] != "none"
                                   else "Choose a classroom plan"),
         "done": bool(limits["active"] or limits["pilot"]["state"] != "none"),
         "anchor": "#pilot" if can_pilot else "#plans"},
        {"key": "class", "label": "Create a class", "done": first is not None, "anchor": "#add-class"},
        {"key": "students", "label": "Add your students by first name or nickname", "done": students_in > 0,
         "class_page": first, "anchor": "#add-students"},
        {"key": "codes", "label": "Print and share the join codes", "done": codes or played,
         "codes_page": first if students_in else None},
        {"key": "lesson", "label": "A student finishes a first lesson", "done": lesson,
         "class_page": first if students_in else None,
         "detail": "Students type their code once on a school device, then start with lesson one."},
    ]
    if all(item["done"] for item in items):
        return None
    return {"items": items, "done": sum(item["done"] for item in items), "total": len(items)}


def _passed_rows(conn, learner_ids, since=None, until=None):
    if not learner_ids:
        return []
    marks = ",".join("?" * len(learner_ids))
    sql = (f"SELECT learner_id, level, best_stars, completed_at FROM learner_progress"
           f" WHERE learner_id IN ({marks}) AND best_stars >= 1")
    args = list(learner_ids)
    if since is not None:
        sql += " AND completed_at >= ?"
        args.append(iso(since))
    if until is not None:
        sql += " AND completed_at <= ?"
        args.append(iso(until))
    return conn.execute(sql, args).fetchall()


def _world_of(level):
    return academy.world((level % 1_000_000) // 1000)


def _has_certificate(rows_for_learner):
    """Whether a student has a certificate on any track: passed stage 1 of
    the Owner's Challenge (academy.certificate_for)."""
    for t in academy.ALL_TRACKS:
        if any(r["level"] == academy.level_id(t, academy.FINAL_WORLD.number, 1) for r in rows_for_learner):
            return True
    return False


def class_progress(conn, class_row):
    """The teacher's class view: each student's lessons done, stars, last day
    played and certificate, and the class totals."""
    kids = students(conn, class_row["id"])
    rows = _passed_rows(conn, [k["id"] for k in kids])
    by_kid = {}
    for r in rows:
        by_kid.setdefault(r["learner_id"], []).append(r)
    last_days = {}
    if kids:
        marks = ",".join("?" * len(kids))
        last_days = {r["learner_id"]: r["day"] for r in conn.execute(
            f"SELECT learner_id, MAX(day) AS day FROM learner_days WHERE learner_id IN ({marks})"
            " GROUP BY learner_id", [k["id"] for k in kids])}
    out = []
    for k in kids:
        mine = by_kid.get(k["id"], [])
        out.append({"learner": k, "lessons": len(mine), "stars": sum(r["best_stars"] for r in mine),
                    "last_day": last_days.get(k["id"]), "certificate": _has_certificate(mine)})
    total = sum(s["lessons"] for s in out)
    return {
        "students": out,
        "count": len(out),
        "lessons": total,
        "average": round(total / len(out), 1) if out else 0,
        "certificates": sum(1 for s in out if s["certificate"]),
        "playing": sum(1 for s in out if s["lessons"]),
    }


def leaderboard(conn, class_row):
    """A class's leaderboard for its students: first name or nickname,
    picture and lessons done, most first. Nothing else about anyone."""
    view = class_progress(conn, class_row)
    board = sorted(view["students"], key=lambda s: (-s["lessons"], -s["stars"], s["learner"]["nickname"].lower()))
    return [{"id": s["learner"]["id"], "nickname": s["learner"]["nickname"], "avatar": s["learner"]["avatar"],
             "lessons": s["lessons"]} for s in board]


def report(conn, org, class_row, now=None):
    """The trial report for one class: totals only, never a student's name.
    During or after the workspace's pilot it counts the lessons finished in
    the pilot's dates; without a pilot, every lesson so far."""
    now = now or utcnow()
    pilot = plans.pilot_status(org, now)
    since = until = None
    if pilot["state"] != "none":
        since, until = pilot["started"], min(pilot["ends"], now)
    kids = students(conn, class_row["id"])
    rows = _passed_rows(conn, [k["id"] for k in kids], since, until)
    topics = {}
    for r in rows:
        w = _world_of(r["level"])
        if w is None:
            continue
        topics[w.number] = topics.get(w.number, 0) + 1
    order = {w.number: n for n, w in enumerate(academy.ALL_WORLDS)}
    covered = [{"world": academy.world(n), "lessons": count,
                "unit": academy.UNIT_NAMES.get(academy.world(n).unit, "")}
               for n, count in sorted(topics.items(), key=lambda item: order.get(item[0], 0))]
    by_kid = {}
    for r in rows:
        by_kid.setdefault(r["learner_id"], []).append(r)
    return {
        "class": class_row,
        "pilot": pilot,
        "since": since,
        "until": until,
        "finished": pilot["state"] == "ended",
        "students": len(kids),
        "playing": len(by_kid),
        "lessons": len(rows),
        "topics": covered,
        "certificates": sum(1 for rs in by_kid.values() if _has_certificate(rs)),
    }


# --- Limits ------------------------------------------------------------------------------

def can_add_class(conn, org, now=None):
    """(True, None) when the workspace may add a class now, otherwise
    (False, why) in plain words."""
    limits = plans.class_limits(org, now)
    if not limits["active"]:
        return False, "Start the free trial or choose a classroom plan to add a class."
    count = conn.execute("SELECT COUNT(*) FROM classes WHERE org_id = ?", (org["id"],)).fetchone()[0]
    if count >= MAX_CLASSES:
        return False, (f"A workspace can have up to {MAX_CLASSES} classes. Delete a class you no longer use,"
                       " or write to us for more.")
    if limits["max_classes"] is not None and count >= limits["max_classes"]:
        many = limits["max_classes"]
        return False, (f"{limits['name']} is for {many} class{'es' if many != 1 else ''}. "
                       f"Whole school has as many classes as you like.")
    return True, None


def room_for_students(conn, org, class_row, now=None):
    """How many more students this class can take now (0 when none)."""
    limits = plans.class_limits(org, now)
    if not limits["active"]:
        return 0
    count = conn.execute("SELECT COUNT(*) FROM learners WHERE class_id = ?", (class_row["id"],)).fetchone()[0]
    return max(0, limits["class_size"] - count)


def _owner_ids(conn, org_id):
    return [r[0] for r in conn.execute("SELECT user_id FROM memberships WHERE org_id = ? AND role = 'owner'",
                                       (org_id,))]


def pilot_available(conn, org):
    """Whether this workspace can still start the free trial. It is one per
    owner, whichever of their locations it was in (users.pilot_used_at, kept
    when that location is deleted), and one per workspace."""
    if org["pilot_started_at"]:
        return False
    owners = _owner_ids(conn, org["id"])
    if not owners:
        return False
    marks = ",".join("?" * len(owners))
    return conn.execute(f"SELECT 1 FROM users WHERE id IN ({marks}) AND pilot_used_at IS NOT NULL",
                        owners).fetchone() is None


def start_pilot(conn, org, days, now=None):
    """Starts the free classroom trial, one per owner (pilot_available).
    Returns False when the workspace or its owner has had one already. The
    owner is claimed first, in the same transaction, so two locations
    started at once can't both get one."""
    now = now or utcnow()
    owners = _owner_ids(conn, org["id"])
    if not owners:
        return False
    marks = ",".join("?" * len(owners))
    claimed = conn.execute(f"UPDATE users SET pilot_used_at = ? WHERE id IN ({marks}) AND pilot_used_at IS NULL",
                           [iso(now), *owners]).rowcount
    if claimed != len(owners):
        conn.rollback()
        return False
    if conn.execute("UPDATE orgs SET pilot_started_at = ?, pilot_ends_at = ? WHERE id = ?"
                    " AND pilot_started_at IS NULL",
                    (iso(now), iso(now + timedelta(days=days)), org["id"])).rowcount != 1:
        conn.rollback()
        return False
    return True
