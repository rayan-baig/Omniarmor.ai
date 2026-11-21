# -*- coding: utf-8 -*-
"""Pages for the Academy in classrooms (classrooms.py): the classes page with
the free trial and the classroom plans, a class's progress view, adding
students by first name or nickname, join codes for the class, printable
certificates, the trial report, and a student's own class page with the
class leaderboard.

Everything but the student's class page is for the workspace's grown-ups
(grown_ups_only); starting the pilot and paying are for its owner."""

from datetime import timedelta

from flask import Blueprint, abort, current_app, flash, g, redirect, render_template, request, url_for

from . import academy, academy_plan, armo, classrooms, plans, usage
from .academy_views import (JOIN_CODE_DAYS, _learner_or_404, _progress, _summary, academy_access,
                            grown_ups_only)
from .db import get_db, iso, now_iso, record_audit, utcnow
from .security import clean_text, flash_error, new_device_epoch, rate_limited, record_event
from .tracking import local_date, org_today

bp = Blueprint("classes", __name__)


def _class_or_404(class_id):
    if not 0 < class_id < 2 ** 63:
        abort(404)
    row = classrooms.class_or_none(get_db(), g.org["id"], class_id)
    if row is None:
        abort(404)
    return row


def _back(class_id=None):
    if class_id is None:
        return redirect(url_for("classes.index"))
    return redirect(url_for("classes.class_page", class_id=class_id))


def _owner_only():
    if g.role != "owner":
        flash_error("Only the workspace owner can do that.")
        return True
    return False


# --- The classes page ------------------------------------------------------------------

@bp.route("/app/academy/classes")
@grown_ups_only
def index():
    cfg = current_app.config
    conn = get_db()
    can_add, why = classrooms.can_add_class(conn, g.org)
    rows = classrooms.classes(conn, g.org["id"])
    limits = plans.class_limits(g.org)
    return render_template("academy/classes.html", classes=rows, limits=limits, access=plans.access(g.org),
                           steps=classrooms.getting_started(conn, g.org, limits, rows),
                           facts=classrooms.public_facts(cfg), can_add=can_add, why=why,
                           pilot_available=classrooms.pilot_available(conn, g.org),
                           card_from=_card_from(g.org))


@bp.route("/app/academy/classes/pilot", methods=["POST"])
@grown_ups_only
def start_pilot():
    if _owner_only():
        return _back()
    conn = get_db()
    days = current_app.config["CLASSROOM_PILOT_DAYS"]
    if not classrooms.start_pilot(conn, g.org, days):
        flash_error("This workspace has had its free trial already (the free trial is one per owner, in any of your"
                    " locations). Choose a classroom plan to keep going.")
        return _back()
    record_audit(conn, g.org["id"], g.user["id"], "workspace", f"Free classroom trial started ({days} days)")
    conn.commit()
    usage.count(conn, "classroom_pilots")
    org = conn.execute("SELECT * FROM orgs WHERE id = ?", (g.org["id"],)).fetchone()
    flash(f"Your free {days}-day trial is on, until {local_date(org['pilot_ends_at'], org)}. Add your class and"
          " your students next.", "ok")
    return _back()


@bp.route("/app/academy/classes", methods=["POST"])
@grown_ups_only
def add_class():
    conn = get_db()
    name = clean_text(request.form.get("name"), classrooms.MAX_CLASS_NAME)
    if name is None:
        flash_error(f"Give the class a name up to {classrooms.MAX_CLASS_NAME} characters, like Room 12.")
        return _back()
    allowed, why = classrooms.can_add_class(conn, g.org)
    if not allowed:
        flash_error(why)
        return _back()
    key = f"class-add:{g.org['id']}"
    if rate_limited([(key, classrooms.CLASSES_PER_HOUR)], timedelta(hours=1)):
        flash_error(f"Too many classes added in the last hour (up to {classrooms.CLASSES_PER_HOUR}). Please wait a"
                    " little and try again.")
        return _back()
    record_event([key])
    # A new class starts with its leaderboard off (1.11.0); the teacher can turn it on.
    class_id = conn.execute("INSERT INTO classes (org_id, name, leaderboard, created_by, created_at)"
                            " VALUES (?, ?, 0, ?, ?)",
                            (g.org["id"], name, g.user["id"], now_iso())).lastrowid
    record_audit(conn, g.org["id"], g.user["id"], "workspace", f"Class added: {name}")
    conn.commit()
    flash(f"{name} is ready. Add your students by first name or nickname.", "ok")
    return _back(class_id)


@bp.route("/app/academy/classes/checkout", methods=["POST"])
@grown_ups_only
def checkout():
    """Pays for Classroom or Whole school through Stripe Checkout, yearly.
    Without its Stripe price, the page offers an invoice instead."""
    if _owner_only():
        return _back()
    cfg = current_app.config
    key = request.form.get("plan", "")
    if key not in plans.CLASSROOM_PLANS:
        flash_error("Pick Classroom or Whole school.")
        return _back()
    plan = plans.CLASSROOM_PLANS[key]
    kind, price, _ = plans.classroom_checkout(cfg, key)
    trial_end = None
    if academy_plan.subscribed(g.org):
        from .plan_views import already_paid
        refused = already_paid(cfg, g.org, plans.access(g.org), kind)
        if refused:
            flash_error(refused)
            return _back()
        # The invoiced plan runs on to its end date; the card's first charge is that day.
        trial_end = academy_plan.first_charge_at(academy_plan.card_after_invoice(g.org))
    if not academy_plan.stripe_ready(cfg, price):
        flash_error(f"{plan.name} can't be paid online yet. Write to {classrooms.invoice_email(cfg)} for an"
                    " invoice.")
        return _back()
    try:
        url = academy_plan.checkout_url(cfg, g.org, g.user["email"],
                                        url_for("plan.plan_page", welcome=1, _external=True)
                                        + "&session_id={CHECKOUT_SESSION_ID}",
                                        url_for("classes.index", _external=True),
                                        price=price, kind=kind, quantity=1, interval=plans.YEAR,
                                        trial_end=trial_end)
    except academy_plan.StripeError as exc:
        current_app.logger.warning("Stripe classroom checkout failed: %s", exc)
        flash_error("We couldn't open checkout just now. Please try again in a minute.")
        return _back()
    return redirect(url, code=303)


def _card_from(org):
    """The day an invoiced classroom plan ends, when its card subscription
    can be set up now (academy_plan.card_after_invoice), else None."""
    ends = academy_plan.card_after_invoice(org)
    return ends if ends is not None and org["plan"] in plans.CLASSROOM_PLANS else None


# --- One class ------------------------------------------------------------------------

@bp.route("/app/academy/classes/<int:class_id>")
@grown_ups_only
def class_page(class_id):
    """The teacher's class view: lessons done per student and the class total."""
    return _class_view(_class_or_404(class_id))


@bp.route("/app/academy/classes/<int:class_id>/students", methods=["POST"])
@grown_ups_only
def add_students(class_id):
    """Adds the students a teacher typed, one per line. Every name that can be
    added is; the ones that can't are listed with the reason and put back in
    the box to fix, so nothing typed is lost."""
    row = _class_or_404(class_id)
    conn = get_db()
    confirmed = request.form.get("confirmed") == "1"
    if confirmed:
        # The answers to "Is this a first and last name?": only what the
        # teacher picked for each is added; "Don't add" leaves it out.
        count = min(request.form.get("asked", 0, type=int), classrooms.MAX_ADD_AT_ONCE)
        picked = [(request.form.get(f"pick-{n}") or "").strip() for n in range(max(count, 0))]
        names = [(classrooms.clean_student_name(p), p) for p in picked if p]
        if not names:
            flash("Nothing was added.", "ok")
            return _back(class_id)
    else:
        names = classrooms.parse_names(request.form.get("names"))
    if not names:
        flash_error("Type each student's first name or nickname, one on each line.")
        return _back(class_id)
    room = classrooms.room_for_students(conn, g.org, row)
    if room == 0:
        limits = plans.class_limits(g.org)
        flash_error(f"This class is full ({limits['class_size']} students)." if limits["active"] else
                    "Start the free trial or choose a classroom plan to add students.")
        return _class_view(row, [(typed, None) for _, typed in names], 400)
    taken = {k["nickname"].lower() for k in classrooms.students(conn, class_id)}
    wanted, rejected, ask = classrooms.sort_names(names, taken, room, confirmed=confirmed)
    pictures = list(academy.AVATARS)
    start = conn.execute("SELECT COUNT(*) FROM learners WHERE class_id = ?", (class_id,)).fetchone()[0]
    for n, name in enumerate(wanted):
        conn.execute(
            "INSERT INTO learners (org_id, class_id, nickname, avatar, armo, track, track_chosen, created_by,"
            " created_at, device_epoch) VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?, ?)",
            (g.org["id"], class_id, name, pictures[(start + n) % len(pictures)], armo.DEFAULT_KID,
             academy.CLASSROOM.key, g.user["id"], now_iso(), new_device_epoch()))
    conn.commit()
    if wanted:
        usage.count(conn, "class_students", len(wanted))
        flash(f"Added {len(wanted)} student{'s' if len(wanted) != 1 else ''} to {row['name']}.", "ok")
    if not rejected and not ask:
        return _back(class_id)
    if ask:
        many = len(ask)
        flash(f"{many} name{'s' if many != 1 else ''} look{'s' if many == 1 else ''} like a first and last name, so"
              f" {'they weren' if many != 1 else 'it wasn'}'t added yet. Students need only a first name: choose"
              " below.", "ok")
    if rejected:
        many = len(rejected)
        flash_error(f"{many} name{'s' if many != 1 else ''} {'weren' if many != 1 else 'wasn'}'t added. "
                    f"{'They are' if many != 1 else 'It is'} listed below the box, with the reason, and back in the"
                    " box to fix.")
    return _class_view(conn.execute("SELECT * FROM classes WHERE id = ?", (class_id,)).fetchone(), rejected,
                       200 if wanted or ask else 400, ask=ask)


def _class_view(row, rejected=(), status=200, ask=()):
    """The class page; rejected is [(what was typed, why it wasn't added)]
    after adding students, shown under the box and put back in it; ask is
    the names that look like a first and last name, each asked about with a
    shorter one suggested ("Ava Thompson": add as Ava T?)."""
    conn = get_db()
    return render_template("academy/class.html", cls=row, view=classrooms.class_progress(conn, row),
                           room=classrooms.room_for_students(conn, g.org, row), limits=plans.class_limits(g.org),
                           avatars=academy.AVATARS, max_name=classrooms.MAX_NAME,
                           codes=_active_codes(conn, row), rejected=list(rejected),
                           names_back="\n".join(typed for typed, _ in rejected),
                           ask=[(name, classrooms.suggest_short_name(name)) for name in ask]), status


@bp.route("/app/academy/classes/<int:class_id>/students/<int:learner_id>/remove", methods=["POST"])
@grown_ups_only
def remove_student(class_id, learner_id):
    row = _class_or_404(class_id)
    learner = _learner_or_404(learner_id)
    if learner["class_id"] != row["id"]:
        abort(404)
    conn = get_db()
    conn.execute("DELETE FROM learners WHERE id = ?", (learner_id,))
    conn.commit()
    flash(f"{learner['nickname']} and their progress were removed from {row['name']}.", "ok")
    return _back(class_id)


@bp.route("/app/academy/classes/<int:class_id>/leaderboard", methods=["POST"])
@grown_ups_only
def leaderboard_setting(class_id):
    row = _class_or_404(class_id)
    on = request.form.get("leaderboard") == "on"
    conn = get_db()
    conn.execute("UPDATE classes SET leaderboard = ? WHERE id = ?", (1 if on else 0, class_id))
    conn.commit()
    flash(f"The class leaderboard is {'on' if on else 'off'} for {row['name']}.", "ok")
    return _back(class_id)


@bp.route("/app/academy/classes/<int:class_id>/rename", methods=["POST"])
@grown_ups_only
def rename_class(class_id):
    _class_or_404(class_id)
    name = clean_text(request.form.get("name"), classrooms.MAX_CLASS_NAME)
    if name is None:
        flash_error(f"Give the class a name up to {classrooms.MAX_CLASS_NAME} characters.")
        return _back(class_id)
    conn = get_db()
    conn.execute("UPDATE classes SET name = ? WHERE id = ?", (name, class_id))
    conn.commit()
    flash(f"The class is now called {name}.", "ok")
    return _back(class_id)


@bp.route("/app/academy/classes/<int:class_id>/delete", methods=["POST"])
@grown_ups_only
def delete_class(class_id):
    row = _class_or_404(class_id)
    if request.form.get("confirm", "").strip() != row["name"]:
        flash_error("Type the class name to delete it.")
        return _back(class_id)
    conn = get_db()
    conn.execute("DELETE FROM learners WHERE class_id = ?", (class_id,))
    conn.execute("DELETE FROM classes WHERE id = ?", (class_id,))
    record_audit(conn, g.org["id"], g.user["id"], "workspace", f"Class deleted: {row['name']}")
    conn.commit()
    flash(f"{row['name']}, its students and their progress were deleted.", "ok")
    return _back()


# --- Join codes for the whole class ---------------------------------------------------------

def _active_codes(conn, row):
    return conn.execute("SELECT learners.nickname, join_codes.code, join_codes.expires_at FROM join_codes"
                        " JOIN learners ON learners.id = join_codes.learner_id"
                        " WHERE learners.class_id = ? AND join_codes.expires_at > ?"
                        " ORDER BY learners.nickname COLLATE NOCASE", (row["id"], now_iso())).fetchall()


@bp.route("/app/academy/classes/<int:class_id>/join-codes", methods=["GET", "POST"])
@grown_ups_only
def join_codes(class_id):
    """One join code per student, to hand out on paper: each student types
    theirs once on a school device. A new set replaces the old one."""
    row = _class_or_404(class_id)
    conn = get_db()
    if request.method == "POST":
        expires = iso(utcnow() + timedelta(days=JOIN_CODE_DAYS))
        for kid in classrooms.students(conn, class_id):
            for _ in range(5):
                code = academy.new_join_code()
                if conn.execute("SELECT 1 FROM join_codes WHERE code = ?", (code,)).fetchone() is None:
                    break
            conn.execute("INSERT INTO join_codes (learner_id, code, expires_at) VALUES (?, ?, ?)"
                         " ON CONFLICT (learner_id) DO UPDATE SET code = excluded.code,"
                         " expires_at = excluded.expires_at", (kid["id"], code, expires))
        conn.commit()
        return redirect(url_for("classes.join_codes", class_id=class_id))
    return render_template("academy/class_codes.html", cls=row, codes=_active_codes(conn, row),
                           has_students=bool(classrooms.students(conn, class_id)),
                           days=JOIN_CODE_DAYS, join_url=url_for("kids.join", _external=True))


# --- Certificates and the trial report ---------------------------------------------------

@bp.route("/app/academy/classes/<int:class_id>/certificates")
@grown_ups_only
def certificates(class_id):
    """Every certificate the class has earned, on every track, one to a
    printed page, each with the student's first name or nickname. The same
    certificates the class view counts (classrooms.class_progress): a
    student who earned one on a track and then changed track keeps it."""
    row = _class_or_404(class_id)
    conn = get_db()
    earned = []
    for kid in classrooms.students(conn, class_id):
        for t in academy.ALL_TRACKS:
            progress = _progress(kid["id"], t)
            final = progress.get(academy.level_id(t, academy.FINAL_WORLD.number, 1))
            if final is None or final["best_stars"] < 1:
                continue
            summary = _summary(kid, progress, t)
            if summary["certificate"]:
                earned.append((summary, local_date(final["completed_at"], g.org)))
    return render_template("academy/class_certificates.html", cls=row, earned=earned, avatars=academy.AVATARS,
                           today=org_today(g.org))


@bp.route("/app/academy/classes/<int:class_id>/report")
@grown_ups_only
def report(class_id):
    """The trial report: one page of totals for the school office."""
    row = _class_or_404(class_id)
    conn = get_db()
    usage.count(conn, "pilot_reports")
    return render_template("academy/class_report.html", r=classrooms.report(conn, g.org, row),
                           today=org_today(g.org), facts=classrooms.public_facts(current_app.config))


# --- A student's own class ------------------------------------------------------------------

@bp.route("/app/academy/<int:learner_id>/class")
@academy_access
def my_class(learner_id):
    """A student's class: its name and, when the teacher leaves it on, the
    leaderboard of that one class. Never another class."""
    learner = _learner_or_404(learner_id)
    if learner["class_id"] is None:
        abort(404)
    conn = get_db()
    row = classrooms.class_or_none(conn, g.org["id"], learner["class_id"])
    if row is None:
        abort(404)
    board = classrooms.leaderboard(conn, row) if row["leaderboard"] else None
    return render_template("academy/my_class.html", learner=learner, cls=row, board=board,
                           avatars=academy.AVATARS)
