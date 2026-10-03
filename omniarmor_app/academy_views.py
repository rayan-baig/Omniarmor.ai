# -*- coding: utf-8 -*-
"""Pages for the Future Owner Academy: learner profiles, choosing a track, the
world map, each world's stages, playing a level, results, practicing past
mistakes, the certificate, join codes for a kid's own device, and the
Academy's own plan.

Grown-ups use the Academy inside their account. A kid who joined with a join
code has an Academy-only session (g.kid) that can open their own profile and
nothing else."""

import hashlib
import json
import secrets
from datetime import timedelta
from functools import wraps

from flask import (Blueprint, abort, current_app, flash, g, jsonify, redirect, render_template, request,
                   url_for)

from . import academy, academy_plan, armo
from .catalog import INDUSTRIES
from .db import get_db, iso, now_iso, utcnow
from .security import (clean_text, client_ip, flash_error, owner_required, rate_limited, record_event,
                       start_kid_session)
from .tracking import org_industry_ids, org_today

bp = Blueprint("academy", __name__, url_prefix="/app/academy")
kids = Blueprint("kids", __name__, url_prefix="/kids")
plan = Blueprint("plan", __name__)
FONT_URL = "https://fonts.googleapis.com/css2?family=Baloo+2:wght@600;700;800&display=swap"
JOIN_CODE_DAYS = 7
DAILY_GOAL = 3          # levels a day for the daily goal
PRACTICE_SIZE = 8       # mistakes per practice round
REVIEW_DAYS = [1, 3, 7]  # spaced repetition: days until a fixed mistake comes back


# --- Who may see what ----------------------------------------------------------

def academy_access(view):
    """A grown-up in the workspace, or a kid on their own device (only their own profile)."""
    @wraps(view)
    def wrapped(*args, **kwargs):
        if g.get("user") is None and g.get("kid") is None:
            return redirect(url_for("auth.login", next=request.full_path if request.method == "GET" else None))
        learner_id = kwargs.get("learner_id")
        if g.get("kid") is not None and learner_id is not None and learner_id != g.kid["id"]:
            abort(404)
        return view(*args, **kwargs)
    return wrapped


def grown_ups_only(view):
    """Things only a grown-up can do: add or remove kids, friends, join codes and the plan."""
    @wraps(view)
    def wrapped(*args, **kwargs):
        if g.get("kid") is not None:
            if request.method == "GET":
                return redirect(url_for("academy.level_map", learner_id=g.kid["id"]))
            abort(403)
        if g.get("user") is None:
            return redirect(url_for("auth.login", next=request.full_path if request.method == "GET" else None))
        return view(*args, **kwargs)
    return wrapped


# --- Progress --------------------------------------------------------------------

def _learner_or_404(learner_id):
    row = get_db().execute("SELECT * FROM learners WHERE id = ? AND org_id = ?", (learner_id, g.org["id"])).fetchone()
    if row is None:
        abort(404)
    return row


def _track(learner):
    return academy.track(learner["track"])


def _progress(learner_id, t):
    low = t.index * 1_000_000
    rows = get_db().execute("SELECT * FROM learner_progress WHERE learner_id = ? AND level >= ? AND level < ?",
                            (learner_id, low, low + 1_000_000))
    return {r["level"]: r for r in rows}


def _passed(progress):
    return {lid for lid, r in progress.items() if r["best_stars"] >= 1}


def _streak(learner_id, today):
    """Days in a row with at least one level played, counting today or yesterday."""
    days = {r["day"] for r in get_db().execute("SELECT day FROM learner_days WHERE learner_id = ?", (learner_id,))}
    day = today if today.isoformat() in days else today - timedelta(days=1)
    streak = 0
    while day.isoformat() in days:
        streak += 1
        day -= timedelta(days=1)
    return streak


def _today_levels(learner_id, today):
    row = get_db().execute("SELECT levels FROM learner_days WHERE learner_id = ? AND day = ?",
                           (learner_id, today.isoformat())).fetchone()
    return row["levels"] if row else 0


def _summary(learner, progress=None):
    t = _track(learner)
    progress = _progress(learner["id"], t) if progress is None else progress
    passed = _passed(progress)
    final_passed = academy.level_id(t, academy.FINAL_WORLD.number, 1) in passed
    done = len(passed)
    today = org_today(g.org)
    return {
        "learner": learner,
        "track": t,
        "stars": sum(r["best_stars"] for r in progress.values()),
        "done": done,
        "rank": academy.rank_for(done, t),
        "tier": academy.rank_tier(done, t),
        "next_rank": academy.next_rank(done, t),
        "certificate": academy.certificate_for(done, final_passed, t),
        "total": t.total,
        "streak": _streak(learner["id"], today),
        "today": _today_levels(learner["id"], today),
    }


def _world_or_404(number, t):
    w = academy.world(number)
    if w is None or not t.has(w):
        abort(404)
    return w


def _world_card(t, w, progress, passed):
    stages = t.stages(w)
    ids = [academy.level_id(t, w.number, s) for s in range(1, stages + 1)]
    done = sum(1 for lid in ids if lid in passed)
    stars = sum(progress[lid]["best_stars"] for lid in ids if lid in progress)
    next_stage = next((s for s, lid in enumerate(ids, start=1) if lid not in passed), None)
    return {"world": w, "stages": stages, "done": done, "stars": stars,
            "open": academy.unlocked(t, w, 1, passed),
            "paid": not academy_plan.allows(g.org, t, w),
            "next": next_stage if next_stage and academy.unlocked(t, w, next_stage, passed) else None}


def _mistakes_due(learner_id):
    return get_db().execute("SELECT COUNT(*) FROM learner_mistakes WHERE learner_id = ? AND due_at <= ?",
                            (learner_id, now_iso())).fetchone()[0]


def _qkey(q):
    return hashlib.sha1(f"{q.prompt}\x00{q.options[q.answer]}".encode()).hexdigest()[:20]


def _remember(conn, learner_id, results):
    """Spaced repetition: a missed question goes into the learner's practice
    deck; answering it right later pushes it further out until it's mastered."""
    now = utcnow()
    for r in results:
        q = r["question"]
        key = _qkey(q)
        if not r["right"]:
            data = json.dumps({"prompt": q.prompt, "options": q.options, "answer": q.answer,
                               "explain": q.explain, "kind": q.kind})
            conn.execute("INSERT INTO learner_mistakes (learner_id, qkey, question, misses, streak, due_at)"
                         " VALUES (?, ?, ?, 1, 0, ?) ON CONFLICT (learner_id, qkey) DO UPDATE SET"
                         " misses = misses + 1, streak = 0, due_at = excluded.due_at",
                         (learner_id, key, data, iso(now)))
        else:
            _reviewed(conn, learner_id, key, now)


def _reviewed(conn, learner_id, key, now):
    row = conn.execute("SELECT id, streak FROM learner_mistakes WHERE learner_id = ? AND qkey = ?",
                       (learner_id, key)).fetchone()
    if row is None:
        return
    streak = row["streak"] + 1
    if streak > len(REVIEW_DAYS):
        conn.execute("DELETE FROM learner_mistakes WHERE id = ?", (row["id"],))
    else:
        conn.execute("UPDATE learner_mistakes SET streak = ?, due_at = ? WHERE id = ?",
                     (streak, iso(now + timedelta(days=REVIEW_DAYS[streak - 1])), row["id"]))


def _log_day(conn, learner_id):
    conn.execute("INSERT INTO learner_days (learner_id, day, levels) VALUES (?, ?, 1)"
                 " ON CONFLICT (learner_id, day) DO UPDATE SET levels = levels + 1",
                 (learner_id, org_today(g.org).isoformat()))


@bp.app_context_processor
def academy_context():
    return {"academy_font": FONT_URL, "academy_tracks": academy.TRACK_LIST}


# --- Learners --------------------------------------------------------------------

@bp.route("")
@grown_ups_only
def home():
    learners = get_db().execute("SELECT * FROM learners WHERE org_id = ? ORDER BY created_at, id", (g.org["id"],)).fetchall()
    return render_template("academy/home.html", summaries=[_summary(l) for l in learners], avatars=academy.AVATARS,
                           max_learners=academy.MAX_LEARNERS, tracks=academy.TRACK_LIST,
                           world_count=len(academy.TOPIC_WORLDS), plan=academy_plan.plan_status(g.org))


@bp.route("/learners", methods=["POST"])
@grown_ups_only
def add_learner():
    conn = get_db()
    nickname = clean_text(request.form.get("nickname"), 30)
    avatar = request.form.get("avatar", "")
    buddy = request.form.get("armo", armo.DEFAULT_KID)
    count = conn.execute("SELECT COUNT(*) FROM learners WHERE org_id = ?", (g.org["id"],)).fetchone()[0]
    if nickname is None:
        flash_error("Pick a nickname up to 30 characters.")
    elif avatar not in academy.AVATARS:
        flash_error("Pick a picture.")
    elif buddy not in armo.PERSONALITIES:
        flash_error("Pick an Armo for your learner.")
    elif count >= academy.MAX_LEARNERS:
        flash_error(f"A workspace can have up to {academy.MAX_LEARNERS} learners.")
    else:
        learner_id = conn.execute(
            "INSERT INTO learners (org_id, nickname, avatar, armo, created_by, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (g.org["id"], nickname, avatar, buddy, g.user["id"], now_iso()),
        ).lastrowid
        academy_plan.start_trial(conn, g.org["id"], current_app.config["ACADEMY_TRIAL_DAYS"])
        conn.commit()
        flash(f"Welcome to the Academy, {nickname}! Pick your track to begin.", "ok")
        return redirect(url_for("academy.choose_track", learner_id=learner_id))
    return redirect(url_for("academy.home"))


@bp.route("/<int:learner_id>/armo", methods=["POST"])
@academy_access
def change_armo(learner_id):
    learner = _learner_or_404(learner_id)
    buddy = request.form.get("armo", "")
    if buddy not in armo.PERSONALITIES:
        flash_error("Pick one of Armo's personalities.")
    else:
        conn = get_db()
        conn.execute("UPDATE learners SET armo = ? WHERE id = ?", (buddy, learner_id))
        conn.commit()
        flash(f"{learner['nickname']} is now learning with {armo.PERSONALITIES[buddy].name} Armo!", "ok")
    return redirect(url_for("academy.level_map", learner_id=learner_id))


@bp.route("/<int:learner_id>/track", methods=["GET", "POST"])
@academy_access
def choose_track(learner_id):
    learner = _learner_or_404(learner_id)
    if request.method == "POST":
        key = request.form.get("track", "")
        if key not in academy.TRACKS:
            flash_error("Pick a track.")
            return redirect(url_for("academy.choose_track", learner_id=learner_id))
        conn = get_db()
        conn.execute("UPDATE learners SET track = ?, track_chosen = 1 WHERE id = ?", (key, learner_id))
        conn.commit()
        t = academy.TRACKS[key]
        flash(f"{t.name} it is: {t.total:,} levels to explore. Let's go!", "ok")
        return redirect(url_for("academy.level_map", learner_id=learner_id))
    done = {t.key: len(_passed(_progress(learner_id, t))) for t in academy.TRACK_LIST}
    return render_template("academy/track.html", learner=learner, tracks=academy.TRACK_LIST, done=done,
                           avatars=academy.AVATARS, plan=academy_plan.plan_status(g.org),
                           first_time=not learner["track_chosen"])


@bp.route("/<int:learner_id>/delete", methods=["POST"])
@grown_ups_only
def delete_learner(learner_id):
    learner = _learner_or_404(learner_id)
    conn = get_db()
    conn.execute("DELETE FROM learners WHERE id = ?", (learner_id,))
    conn.commit()
    flash(f"{learner['nickname']}'s profile and progress were removed.", "ok")
    return redirect(url_for("academy.home"))


# --- The map, worlds and levels --------------------------------------------------

@bp.route("/<int:learner_id>")
@academy_access
def level_map(learner_id):
    learner = _learner_or_404(learner_id)
    if not learner["track_chosen"]:
        return redirect(url_for("academy.choose_track", learner_id=learner_id))
    t = _track(learner)
    progress = _progress(learner_id, t)
    passed = _passed(progress)
    family = set(org_industry_ids(get_db(), g.org["id"]))
    topics = [_world_card(t, w, progress, passed) for w in t.topic_worlds]
    units = []
    for key, name in academy.UNITS:
        cards = [c for c in topics if c["world"].unit == key]
        if cards:
            units.append({"key": key, "name": name, "cards": cards,
                          "done": sum(c["done"] for c in cards), "stages": sum(c["stages"] for c in cards)})
    final = _world_card(t, academy.FINAL_WORLD, progress, passed)
    industry_cards = [_world_card(t, w, progress, passed) for w in academy.INDUSTRY_WORLDS]
    mine = [c for c in industry_cards if c["world"].industry_id in family]
    explore = [c for c in industry_cards if c["world"].industry_id not in family]
    up_next = next((c for c in topics + [final] + mine if c["next"] and not c["paid"]), None)
    join = get_db().execute("SELECT * FROM join_codes WHERE learner_id = ? AND expires_at > ?",
                            (learner_id, now_iso())).fetchone() if g.get("kid") is None else None
    return render_template("academy/map.html", summary=_summary(learner, progress), units=units, final=final,
                           mine=mine, explore=explore, up_next=up_next, glossary=academy.GLOSSARY,
                           avatars=academy.AVATARS, industries=INDUSTRIES, track=t,
                           unlock_world=academy.world(academy.INDUSTRY_UNLOCK_WORLD),
                           mistakes=_mistakes_due(learner_id), daily_goal=DAILY_GOAL, join=join,
                           plan=academy_plan.plan_status(g.org))


def _plan_blocks(t, w, learner_id):
    if academy_plan.allows(g.org, t, w):
        return None
    flash_error("This world is part of the Academy plan. "
                + ("Ask a grown-up to unlock it!" if g.get("kid") is not None else "Start the plan to unlock it."))
    if g.get("kid") is not None:
        return redirect(url_for("academy.level_map", learner_id=learner_id))
    return redirect(url_for("academy.plan_page"))


@bp.route("/<int:learner_id>/world/<int:world_number>")
@academy_access
def world_page(learner_id, world_number):
    learner = _learner_or_404(learner_id)
    t = _track(learner)
    w = _world_or_404(world_number, t)
    blocked = _plan_blocks(t, w, learner_id)
    if blocked:
        return blocked
    progress = _progress(learner_id, t)
    passed = _passed(progress)
    if not academy.unlocked(t, w, 1, passed):
        flash_error("This world is still locked. Keep playing to open it!")
        return redirect(url_for("academy.level_map", learner_id=learner_id))
    total = t.stages(w)
    stages = []
    for s in range(1, total + 1):
        row = progress.get(academy.level_id(t, w.number, s))
        stages.append({"stage": s, "stars": row["best_stars"] if row else 0,
                       "open": academy.unlocked(t, w, s, passed), "boss": academy.is_boss(w, s)})
    current = next((st for st in stages if st["open"] and st["stars"] == 0), None)
    chapters = [stages[i:i + 50] for i in range(0, total, 50)]
    chapter = request.args.get("chapter", type=int)
    if chapter is None or not 1 <= chapter <= len(chapters):
        chapter = ((current["stage"] - 1) // 50 + 1) if current else 1
    return render_template("academy/world.html", learner=learner, world=w, stages=chapters[chapter - 1],
                           chapter=chapter, chapters=len(chapters), current=current, track=t,
                           card=_world_card(t, w, progress, passed), avatars=academy.AVATARS)


@bp.route("/<int:learner_id>/world/<int:world_number>/stage/<int:stage>", methods=["GET", "POST"])
@academy_access
def play(learner_id, world_number, stage):
    learner = _learner_or_404(learner_id)
    t = _track(learner)
    w = _world_or_404(world_number, t)
    if not 1 <= stage <= t.stages(w):
        abort(404)
    blocked = _plan_blocks(t, w, learner_id)
    if blocked:
        return blocked
    progress = _progress(learner_id, t)
    if not academy.unlocked(t, w, stage, _passed(progress)):
        flash_error("Finish the stage before this one to unlock it.")
        return redirect(url_for("academy.world_page", learner_id=learner_id, world_number=world_number))
    company = g.org["name"]
    industry_ids = org_industry_ids(get_db(), g.org["id"])
    lid = academy.level_id(t, world_number, stage)
    row = progress.get(lid)
    attempt = (row["attempts"] if row else 0) + 1
    questions = academy.quiz(t, world_number, stage, company, industry_ids,
                             academy.attempt_seed(learner_id, t.key, world_number, stage, attempt))
    needed = academy.pass_mark(t, w, stage)

    if request.method == "GET":
        return render_template("academy/level.html", learner=learner, world=w, stage=stage, attempt=attempt,
                               cards=academy.story(t, world_number, stage, company, industry_ids), track=t,
                               stage_count=t.stages(w), boss=academy.is_boss(w, stage),
                               questions=questions, needed=needed, avatars=academy.AVATARS)

    if request.form.get("attempt", type=int) != attempt:
        flash("That quiz was already checked. Here's a fresh one!", "ok")
        return redirect(url_for("academy.play", learner_id=learner_id, world_number=world_number, stage=stage))
    answers = []
    for i, q in enumerate(questions):
        chosen = request.form.get(f"q{i}", type=int)
        answers.append(chosen if chosen is not None and 0 <= chosen < len(q.options) else None)
    score, results = academy.grade(questions, answers)
    stars = academy.stars_for(score, len(questions), academy.pass_rate(t, w, stage))
    was_passed = row is not None and row["best_stars"] >= 1
    before = _summary(learner, progress)
    conn = get_db()
    conn.execute(
        "INSERT INTO learner_progress (learner_id, level, attempts, best_score, best_stars, completed_at)"
        " VALUES (?, ?, 1, ?, ?, ?) ON CONFLICT (learner_id, level) DO UPDATE SET"
        " attempts = attempts + 1, best_score = MAX(best_score, excluded.best_score),"
        " best_stars = MAX(best_stars, excluded.best_stars),"
        " completed_at = COALESCE(completed_at, excluded.completed_at)",
        (learner_id, lid, score, stars, now_iso() if stars >= 1 else None),
    )
    _remember(conn, learner_id, results)
    _log_day(conn, learner_id)
    conn.commit()
    after = _summary(learner)
    passed = stars >= 1
    next_stage = stage + 1 if stage < t.stages(w) else None
    return render_template(
        "academy/result.html", learner=learner, world=w, stage=stage, results=results, score=score,
        total=len(questions), earned_stars=stars, passed=passed, needed=needed, next_stage=next_stage,
        first_clear=passed and not was_passed, avatars=academy.AVATARS, summary=after,
        new_rank=after["rank"] if after["rank"] != before["rank"] else None,
        new_certificate=after["certificate"] if after["certificate"] != before["certificate"] else None,
        goal_hit=before["today"] < DAILY_GOAL <= after["today"], daily_goal=DAILY_GOAL,
        missed=sum(1 for r in results if not r["right"]),
    )


# --- Practice my mistakes (spaced repetition) ---------------------------------------

@bp.route("/<int:learner_id>/practice", methods=["GET", "POST"])
@academy_access
def practice(learner_id):
    learner = _learner_or_404(learner_id)
    conn = get_db()
    if request.method == "POST":
        ids = [int(i) for i in request.form.get("deck", "").split(",") if i.isdigit()][:PRACTICE_SIZE]
        rows = {r["id"]: r for r in conn.execute(
            f"SELECT * FROM learner_mistakes WHERE learner_id = ? AND id IN ({','.join('?' * len(ids)) or 'NULL'})",
            (learner_id, *ids))}
        deck = [rows[i] for i in ids if i in rows]
        if not deck:
            flash("Those practice questions were already checked.", "ok")
            return redirect(url_for("academy.practice", learner_id=learner_id))
        questions = [_stored_question(r) for r in deck]
        answers = []
        for i, q in enumerate(questions):
            chosen = request.form.get(f"q{i}", type=int)
            answers.append(chosen if chosen is not None and 0 <= chosen < len(q.options) else None)
        score, results = academy.grade(questions, answers)
        now = utcnow()
        for r, result in zip(deck, results):
            if result["right"]:
                _reviewed(conn, learner_id, r["qkey"], now)
            else:
                conn.execute("UPDATE learner_mistakes SET misses = misses + 1, streak = 0, due_at = ? WHERE id = ?",
                             (iso(now + timedelta(hours=1)), r["id"]))
        _log_day(conn, learner_id)
        conn.commit()
        return render_template("academy/practice.html", learner=learner, results=results, score=score,
                               total=len(questions), left=_mistakes_due(learner_id), avatars=academy.AVATARS)
    deck = conn.execute("SELECT * FROM learner_mistakes WHERE learner_id = ? AND due_at <= ? ORDER BY due_at LIMIT ?",
                        (learner_id, now_iso(), PRACTICE_SIZE)).fetchall()
    upcoming = conn.execute("SELECT COUNT(*) FROM learner_mistakes WHERE learner_id = ?", (learner_id,)).fetchone()[0]
    return render_template("academy/practice.html", learner=learner, questions=[_stored_question(r) for r in deck],
                           deck=",".join(str(r["id"]) for r in deck), upcoming=upcoming, avatars=academy.AVATARS)


def _stored_question(row):
    data = json.loads(row["question"])
    return academy.Question(data["prompt"], data["options"], data["answer"], data["explain"], data.get("kind", "choice"))


@bp.route("/<int:learner_id>/certificate")
@academy_access
def certificate(learner_id):
    learner = _learner_or_404(learner_id)
    t = _track(learner)
    progress = _progress(learner_id, t)
    summary = _summary(learner, progress)
    if not summary["certificate"]:
        flash_error("Pass stage 1 of the Owner's Challenge to earn the certificate.")
        return redirect(url_for("academy.level_map", learner_id=learner_id))
    first = progress[academy.level_id(t, academy.FINAL_WORLD.number, 1)]["completed_at"]
    return render_template("academy/certificate.html", summary=summary, earned=(first or "")[:10],
                           today=org_today(g.org), avatars=academy.AVATARS)


# --- A kid's own device: join codes ------------------------------------------------

@bp.route("/<int:learner_id>/join-code", methods=["POST"])
@grown_ups_only
def join_code(learner_id):
    learner = _learner_or_404(learner_id)
    conn = get_db()
    for _ in range(5):
        code = academy.new_join_code()
        if conn.execute("SELECT 1 FROM join_codes WHERE code = ?", (code,)).fetchone() is None:
            break
    conn.execute("INSERT INTO join_codes (learner_id, code, expires_at) VALUES (?, ?, ?)"
                 " ON CONFLICT (learner_id) DO UPDATE SET code = excluded.code, expires_at = excluded.expires_at",
                 (learner_id, code, iso(utcnow() + timedelta(days=JOIN_CODE_DAYS))))
    conn.commit()
    flash(f"Join code ready. On {learner['nickname']}'s device, open {url_for('kids.join', _external=True)} "
          "and type the code.", "ok")
    return redirect(url_for("academy.level_map", learner_id=learner_id) + "#grown-ups")


@bp.route("/<int:learner_id>/devices/sign-out", methods=["POST"])
@grown_ups_only
def sign_out_devices(learner_id):
    learner = _learner_or_404(learner_id)
    conn = get_db()
    conn.execute("UPDATE learners SET device_epoch = device_epoch + 1 WHERE id = ?", (learner_id,))
    conn.execute("DELETE FROM join_codes WHERE learner_id = ?", (learner_id,))
    conn.commit()
    flash(f"{learner['nickname']} was signed out on every device.", "ok")
    return redirect(url_for("academy.level_map", learner_id=learner_id) + "#grown-ups")


@kids.route("", methods=["GET", "POST"])
def join():
    if g.get("kid") is not None:
        return redirect(url_for("academy.level_map", learner_id=g.kid["id"]))
    if request.method == "POST":
        key = f"join-ip:{client_ip()}"
        if rate_limited([(key, 20)], timedelta(hours=1)):
            flash_error("Too many tries. Ask a grown-up and try again later.")
            return render_template("kids/join.html"), 429
        code = academy.clean_join_code(request.form.get("code"))
        conn = get_db()
        row = conn.execute("SELECT learners.* FROM join_codes JOIN learners ON learners.id = join_codes.learner_id"
                           " WHERE join_codes.code = ? AND join_codes.expires_at > ?",
                           (code, now_iso())).fetchone() if code else None
        if row is None:
            record_event([key])
            flash_error("That code didn't work. Check it with a grown-up and try again.")
            return render_template("kids/join.html"), 400
        conn.execute("DELETE FROM join_codes WHERE learner_id = ?", (row["id"],))  # one use per code
        conn.commit()
        start_kid_session(row)
        flash(f"Welcome, {row['nickname']}! This device is ready for the Academy.", "ok")
        return redirect(url_for("academy.level_map", learner_id=row["id"]))
    return render_template("kids/join.html")


@kids.route("/leave", methods=["POST"])
def leave():
    from flask import session
    session.clear()
    flash("You left the Academy on this device. A grown-up can make a new join code anytime.", "ok")
    return redirect(url_for("kids.join"))


# --- The Academy plan --------------------------------------------------------------

@bp.route("/plan")
@grown_ups_only
def plan_page():
    cfg = current_app.config
    return render_template("academy/plan.html", plan=academy_plan.plan_status(g.org),
                           stripe=academy_plan.stripe_ready(cfg), price=cfg.get("ACADEMY_PRICE_LABEL", ""),
                           free_worlds=[academy.world(n) for n in sorted(academy_plan.FREE_WORLDS)],
                           tracks=academy.TRACK_LIST, trial_days=cfg["ACADEMY_TRIAL_DAYS"],
                           has_customer=bool(g.org["stripe_customer_id"]))


@bp.route("/plan/checkout", methods=["POST"])
@owner_required
def plan_checkout():
    cfg = current_app.config
    if not academy_plan.stripe_ready(cfg):
        flash_error("Online payment isn't set up yet. Please contact us to start the Academy plan.")
        return redirect(url_for("academy.plan_page"))
    try:
        url = academy_plan.checkout_url(cfg, g.org, g.user["email"],
                                        url_for("academy.plan_page", welcome=1, _external=True),
                                        url_for("academy.plan_page", _external=True))
    except academy_plan.StripeError as exc:
        current_app.logger.warning("Stripe checkout failed: %s", exc)
        flash_error("We couldn't open checkout just now. Please try again in a minute.")
        return redirect(url_for("academy.plan_page"))
    return redirect(url, code=303)


@bp.route("/plan/manage", methods=["POST"])
@owner_required
def plan_manage():
    cfg = current_app.config
    if not (cfg.get("STRIPE_SECRET_KEY") and g.org["stripe_customer_id"]):
        flash_error("There's no subscription to manage yet.")
        return redirect(url_for("academy.plan_page"))
    try:
        url = academy_plan.portal_url(cfg, g.org, url_for("academy.plan_page", _external=True))
    except academy_plan.StripeError as exc:
        current_app.logger.warning("Stripe portal failed: %s", exc)
        flash_error("We couldn't open the billing page just now. Please try again in a minute.")
        return redirect(url_for("academy.plan_page"))
    return redirect(url, code=303)


@plan.route("/billing/stripe/webhook", methods=["POST"])
def stripe_webhook():
    payload = request.get_data()
    if not academy_plan.verify_webhook(payload, request.headers.get("Stripe-Signature", ""),
                                       current_app.config.get("STRIPE_WEBHOOK_SECRET", "")):
        abort(400)
    try:
        event = json.loads(payload)
    except ValueError:
        abort(400)
    conn = get_db()
    change = academy_plan.apply_event(conn, event)
    conn.commit()
    if change:
        current_app.logger.info("Academy plan %s for event %s", change, event.get("id"))
    return jsonify(received=True)


# --- Friends and duels -------------------------------------------------------
# A parent shares a friend code with another family; their parent enters it.
# Friends see only each other's nickname, picture, rank and stars, and can
# challenge each other to duels: both play the same five questions.

def _pair(a, b):
    return (a, b) if a < b else (b, a)


def _are_friends(a, b):
    x, y = _pair(a, b)
    return get_db().execute("SELECT 1 FROM learner_friends WHERE learner_a = ? AND learner_b = ?", (x, y)).fetchone() is not None


def _friends(learner_id):
    return get_db().execute(
        "SELECT l.* FROM learner_friends f JOIN learners l"
        " ON l.id = CASE WHEN f.learner_a = ? THEN f.learner_b ELSE f.learner_a END"
        " WHERE f.learner_a = ? OR f.learner_b = ? ORDER BY l.nickname COLLATE NOCASE",
        (learner_id, learner_id, learner_id)).fetchall()


def _friend_count(learner_id):
    return get_db().execute("SELECT COUNT(*) FROM learner_friends WHERE learner_a = ? OR learner_b = ?",
                            (learner_id, learner_id)).fetchone()[0]


def _duel_view(duel, learner_id):
    mine = duel["challenger_id"] == learner_id
    other_id = duel["opponent_id"] if mine else duel["challenger_id"]
    other = get_db().execute("SELECT id, nickname, avatar FROM learners WHERE id = ?", (other_id,)).fetchone()
    me = duel["challenger_score"] if mine else duel["opponent_score"]
    them = duel["opponent_score"] if mine else duel["challenger_score"]
    if me is None:
        status = "your-turn"
    elif them is None:
        status = "waiting"
    else:
        status = "won" if me > them else ("lost" if me < them else "tie")
    return {"duel": duel, "other": other, "me": me, "them": them, "status": status,
            "world": academy.world(duel["world"]), "challenger": mine}


def _duels(learner_id, limit=20):
    rows = get_db().execute(
        "SELECT * FROM duels WHERE challenger_id = ? OR opponent_id = ? ORDER BY id DESC LIMIT ?",
        (learner_id, learner_id, limit)).fetchall()
    return [_duel_view(d, learner_id) for d in rows]


def _turns_waiting(learner_id):
    return get_db().execute(
        "SELECT COUNT(*) FROM duels WHERE (challenger_id = ? AND challenger_score IS NULL)"
        " OR (opponent_id = ? AND opponent_score IS NULL)", (learner_id, learner_id)).fetchone()[0]


@bp.app_template_global()
def academy_turns(learner_id):
    return _turns_waiting(learner_id)


@bp.route("/<int:learner_id>/friends")
@academy_access
def friends(learner_id):
    learner = _learner_or_404(learner_id)
    code = get_db().execute("SELECT * FROM friend_codes WHERE learner_id = ? AND expires_at > ?",
                            (learner_id, now_iso())).fetchone()
    board = sorted([_summary(learner)] + [_summary(f) for f in _friends(learner_id)],
                   key=lambda s: (-s["done"], -s["stars"], s["learner"]["nickname"].lower()))
    return render_template("academy/friends.html", learner=learner, code=code, board=board,
                           duels=_duels(learner_id), duel_worlds=[academy.world(n) for n in academy.DUEL_WORLDS],
                           avatars=academy.AVATARS, max_friends=academy.MAX_FRIENDS,
                           friend_count=len(board) - 1, code_days=academy.FRIEND_CODE_DAYS)


@bp.route("/<int:learner_id>/friends/code", methods=["POST"])
@grown_ups_only
def friend_code(learner_id):
    _learner_or_404(learner_id)
    conn = get_db()
    expires = iso(utcnow() + timedelta(days=academy.FRIEND_CODE_DAYS))
    for _ in range(5):
        code = academy.new_friend_code()
        if conn.execute("SELECT 1 FROM friend_codes WHERE code = ?", (code,)).fetchone() is None:
            break
    conn.execute("INSERT INTO friend_codes (learner_id, code, expires_at) VALUES (?, ?, ?)"
                 " ON CONFLICT (learner_id) DO UPDATE SET code = excluded.code, expires_at = excluded.expires_at",
                 (learner_id, code, expires))
    conn.commit()
    flash("New friend code ready. Share it with the other family's grown-up.", "ok")
    return redirect(url_for("academy.friends", learner_id=learner_id))


@bp.route("/<int:learner_id>/friends/add", methods=["POST"])
@grown_ups_only
def add_friend(learner_id):
    learner = _learner_or_404(learner_id)
    back = redirect(url_for("academy.friends", learner_id=learner_id))
    keys = [f"friend-org:{g.org['id']}", f"friend-ip:{client_ip()}"]
    if rate_limited([(keys[0], 10), (keys[1], 30)], timedelta(hours=1)):
        flash_error("Too many tries. Please wait an hour and try again.")
        return back
    conn = get_db()
    code = academy.clean_friend_code(request.form.get("code"))
    row = conn.execute("SELECT * FROM friend_codes WHERE code = ? AND expires_at > ?",
                       (code, now_iso())).fetchone() if code else None
    if row is None:
        record_event(keys)
        flash_error("That friend code didn't work. Check it, or ask for a new one.")
        return back
    friend_id = row["learner_id"]
    if friend_id == learner_id:
        flash_error("That's your own friend code. Share it with a friend instead!")
    elif _are_friends(learner_id, friend_id):
        flash_error("You're already friends.")
    elif _friend_count(learner_id) >= academy.MAX_FRIENDS or _friend_count(friend_id) >= academy.MAX_FRIENDS:
        flash_error(f"Each learner can have up to {academy.MAX_FRIENDS} friends.")
    else:
        a, b = _pair(learner_id, friend_id)
        conn.execute("INSERT INTO learner_friends (learner_a, learner_b, created_at) VALUES (?, ?, ?)", (a, b, now_iso()))
        conn.execute("DELETE FROM friend_codes WHERE learner_id = ?", (friend_id,))  # one use per code
        conn.commit()
        friend = conn.execute("SELECT nickname FROM learners WHERE id = ?", (friend_id,)).fetchone()
        flash(f"{learner['nickname']} and {friend['nickname']} are now friends!", "ok")
    return back


@bp.route("/<int:learner_id>/friends/<int:friend_id>/remove", methods=["POST"])
@grown_ups_only
def remove_friend(learner_id, friend_id):
    _learner_or_404(learner_id)
    a, b = _pair(learner_id, friend_id)
    conn = get_db()
    conn.execute("DELETE FROM learner_friends WHERE learner_a = ? AND learner_b = ?", (a, b))
    conn.commit()
    flash("Friend removed.", "ok")
    return redirect(url_for("academy.friends", learner_id=learner_id))


@bp.route("/<int:learner_id>/duels", methods=["POST"])
@academy_access
def new_duel(learner_id):
    _learner_or_404(learner_id)
    friend_id = request.form.get("friend", type=int)
    world_number = request.form.get("world", type=int)
    back = redirect(url_for("academy.friends", learner_id=learner_id))
    if friend_id is None or not _are_friends(learner_id, friend_id):
        flash_error("You can only challenge your friends.")
        return back
    if world_number not in academy.DUEL_WORLDS:
        flash_error("Pick a world for the duel.")
        return back
    conn = get_db()
    open_duels = conn.execute("SELECT COUNT(*) FROM duels WHERE challenger_id = ? AND opponent_score IS NULL",
                              (learner_id,)).fetchone()[0]
    if open_duels >= 10:
        flash_error("You have 10 duels waiting for friends to play. Wait for some to finish first.")
        return back
    stage = secrets.randbelow(50) + 1
    duel_id = conn.execute(
        "INSERT INTO duels (challenger_id, opponent_id, world, stage, seed, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (learner_id, friend_id, world_number, stage, secrets.token_hex(16), now_iso())).lastrowid
    conn.commit()
    return redirect(url_for("academy.duel", learner_id=learner_id, duel_id=duel_id))


@bp.route("/<int:learner_id>/duels/<int:duel_id>", methods=["GET", "POST"])
@academy_access
def duel(learner_id, duel_id):
    learner = _learner_or_404(learner_id)
    conn = get_db()
    row = conn.execute("SELECT * FROM duels WHERE id = ? AND (challenger_id = ? OR opponent_id = ?)",
                       (duel_id, learner_id, learner_id)).fetchone()
    if row is None:
        abort(404)
    view = _duel_view(row, learner_id)
    questions = academy.duel_quiz(row["world"], row["stage"], row["seed"])
    results = None
    if request.method == "POST" and view["me"] is None:
        answers = []
        for i, q in enumerate(questions):
            chosen = request.form.get(f"q{i}", type=int)
            answers.append(chosen if chosen is not None and 0 <= chosen < len(q.options) else None)
        score, results = academy.grade(questions, answers)
        column = "challenger_score" if view["challenger"] else "opponent_score"
        conn.execute(f"UPDATE duels SET {column} = ? WHERE id = ? AND {column} IS NULL", (score, duel_id))
        conn.commit()
        view = _duel_view(conn.execute("SELECT * FROM duels WHERE id = ?", (duel_id,)).fetchone(), learner_id)
    elif request.method == "POST":
        flash("You already played this duel.", "ok")
        return redirect(url_for("academy.duel", learner_id=learner_id, duel_id=duel_id))
    return render_template("academy/duel.html", learner=learner, view=view, questions=questions, results=results,
                           avatars=academy.AVATARS, total=len(questions))
