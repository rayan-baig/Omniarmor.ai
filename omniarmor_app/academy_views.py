# -*- coding: utf-8 -*-
"""Pages for the Future Owner Academy: learner profiles, the world map, each
world's stages, playing a level, results and the certificate."""

import secrets
from datetime import timedelta

from flask import Blueprint, abort, flash, g, redirect, render_template, request, url_for

from . import academy, armo
from .catalog import INDUSTRIES
from .db import get_db, iso, now_iso, utcnow
from .security import clean_text, client_ip, flash_error, login_required, rate_limited, record_event
from .tracking import org_industry_ids, org_today

bp = Blueprint("academy", __name__, url_prefix="/app/academy")
FONT_URL = "https://fonts.googleapis.com/css2?family=Baloo+2:wght@600;700;800&display=swap"


def _learner_or_404(learner_id):
    row = get_db().execute("SELECT * FROM learners WHERE id = ? AND org_id = ?", (learner_id, g.org["id"])).fetchone()
    if row is None:
        abort(404)
    return row


def _progress(learner_id):
    rows = get_db().execute("SELECT * FROM learner_progress WHERE learner_id = ?", (learner_id,))
    return {r["level"]: r for r in rows}


def _passed(progress):
    return {lid for lid, r in progress.items() if r["best_stars"] >= 1}


def _summary(learner, progress=None):
    progress = _progress(learner["id"]) if progress is None else progress
    passed = _passed(progress)
    final_passed = academy.level_id(academy.FINAL_WORLD.number, 1) in passed
    return {
        "learner": learner,
        "stars": sum(r["best_stars"] for r in progress.values()),
        "done": len(passed),
        "rank": academy.rank_for(len(passed)),
        "certificate": academy.certificate_for(len(passed), final_passed),
        "total": academy.TOTAL_LEVELS,
    }


def _world_or_404(number):
    w = academy.world(number)
    if w is None:
        abort(404)
    return w


def _world_card(w, progress, passed):
    ids = [academy.level_id(w.number, s) for s in range(1, w.stages + 1)]
    done = sum(1 for lid in ids if lid in passed)
    stars = sum(progress[lid]["best_stars"] for lid in ids if lid in progress)
    next_stage = next((s for s, lid in enumerate(ids, start=1) if lid not in passed), None)
    return {"world": w, "done": done, "stars": stars, "open": academy.unlocked(w, 1, passed),
            "next": next_stage if next_stage and academy.unlocked(w, next_stage, passed) else None}


@bp.app_context_processor
def academy_context():
    return {"academy_font": FONT_URL}


@bp.route("")
@login_required
def home():
    learners = get_db().execute("SELECT * FROM learners WHERE org_id = ? ORDER BY created_at, id", (g.org["id"],)).fetchall()
    return render_template("academy/home.html", summaries=[_summary(l) for l in learners], avatars=academy.AVATARS,
                           max_learners=academy.MAX_LEARNERS, total=academy.TOTAL_LEVELS,
                           world_count=len(academy.ALL_WORLDS))


@bp.route("/learners", methods=["POST"])
@login_required
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
        conn.commit()
        flash(f"Welcome to the Academy, {nickname}!", "ok")
        return redirect(url_for("academy.level_map", learner_id=learner_id))
    return redirect(url_for("academy.home"))


@bp.route("/<int:learner_id>/armo", methods=["POST"])
@login_required
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


@bp.route("/<int:learner_id>/delete", methods=["POST"])
@login_required
def delete_learner(learner_id):
    learner = _learner_or_404(learner_id)
    conn = get_db()
    conn.execute("DELETE FROM learners WHERE id = ?", (learner_id,))
    conn.commit()
    flash(f"{learner['nickname']}'s profile and progress were removed.", "ok")
    return redirect(url_for("academy.home"))


@bp.route("/<int:learner_id>")
@login_required
def level_map(learner_id):
    learner = _learner_or_404(learner_id)
    progress = _progress(learner_id)
    passed = _passed(progress)
    family = set(org_industry_ids(get_db(), g.org["id"]))
    topics = [_world_card(w, progress, passed) for w in academy.TOPIC_WORLDS]
    final = _world_card(academy.FINAL_WORLD, progress, passed)
    industry_cards = [_world_card(w, progress, passed) for w in academy.INDUSTRY_WORLDS]
    mine = [c for c in industry_cards if c["world"].industry_id in family]
    explore = [c for c in industry_cards if c["world"].industry_id not in family]
    up_next = next((c for c in topics + [final] + mine if c["next"]), None)
    return render_template("academy/map.html", summary=_summary(learner, progress), topics=topics, final=final,
                           mine=mine, explore=explore, up_next=up_next, glossary=academy.GLOSSARY,
                           avatars=academy.AVATARS, industries=INDUSTRIES,
                           unlock_world=academy.world(academy.INDUSTRY_UNLOCK_WORLD))


@bp.route("/<int:learner_id>/world/<int:world_number>")
@login_required
def world_page(learner_id, world_number):
    learner = _learner_or_404(learner_id)
    w = _world_or_404(world_number)
    progress = _progress(learner_id)
    passed = _passed(progress)
    if not academy.unlocked(w, 1, passed):
        flash_error("This world is still locked. Keep playing to open it!")
        return redirect(url_for("academy.level_map", learner_id=learner_id))
    stages = []
    for s in range(1, w.stages + 1):
        row = progress.get(academy.level_id(w.number, s))
        stages.append({"stage": s, "stars": row["best_stars"] if row else 0, "open": academy.unlocked(w, s, passed)})
    current = next((st for st in stages if st["open"] and st["stars"] == 0), None)
    return render_template("academy/world.html", learner=learner, world=w, stages=stages, current=current,
                           card=_world_card(w, progress, passed), avatars=academy.AVATARS)


@bp.route("/<int:learner_id>/world/<int:world_number>/stage/<int:stage>", methods=["GET", "POST"])
@login_required
def play(learner_id, world_number, stage):
    learner = _learner_or_404(learner_id)
    w = _world_or_404(world_number)
    if not 1 <= stage <= w.stages:
        abort(404)
    progress = _progress(learner_id)
    if not academy.unlocked(w, stage, _passed(progress)):
        flash_error("Finish the stage before this one to unlock it.")
        return redirect(url_for("academy.world_page", learner_id=learner_id, world_number=world_number))
    company = g.org["name"]
    industry_ids = org_industry_ids(get_db(), g.org["id"])
    lid = academy.level_id(world_number, stage)
    row = progress.get(lid)
    attempt = (row["attempts"] if row else 0) + 1
    questions = academy.quiz(world_number, stage, company, industry_ids,
                             academy.attempt_seed(learner_id, world_number, stage, attempt))
    needed = academy.pass_mark(w, stage)

    if request.method == "GET":
        return render_template("academy/level.html", learner=learner, world=w, stage=stage, attempt=attempt,
                               cards=academy.story(world_number, stage, company, industry_ids),
                               questions=questions, needed=needed, avatars=academy.AVATARS)

    if request.form.get("attempt", type=int) != attempt:
        flash("That quiz was already checked. Here's a fresh one!", "ok")
        return redirect(url_for("academy.play", learner_id=learner_id, world_number=world_number, stage=stage))
    answers = []
    for i, q in enumerate(questions):
        chosen = request.form.get(f"q{i}", type=int)
        answers.append(chosen if chosen is not None and 0 <= chosen < len(q.options) else None)
    score, results = academy.grade(questions, answers)
    stars = academy.stars_for(score, len(questions), academy.pass_rate(w, stage))
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
    conn.commit()
    after = _summary(learner)
    passed = stars >= 1
    next_stage = stage + 1 if stage < w.stages else None
    return render_template(
        "academy/result.html", learner=learner, world=w, stage=stage, results=results, score=score,
        total=len(questions), earned_stars=stars, passed=passed, needed=needed, next_stage=next_stage,
        first_clear=passed and not was_passed, avatars=academy.AVATARS,
        new_rank=after["rank"] if after["rank"] != before["rank"] else None,
        new_certificate=after["certificate"] if after["certificate"] != before["certificate"] else None,
    )


@bp.route("/<int:learner_id>/certificate")
@login_required
def certificate(learner_id):
    learner = _learner_or_404(learner_id)
    progress = _progress(learner_id)
    summary = _summary(learner, progress)
    if not summary["certificate"]:
        flash_error("Pass stage 1 of the Owner's Challenge to earn the certificate.")
        return redirect(url_for("academy.level_map", learner_id=learner_id))
    first = progress[academy.level_id(academy.FINAL_WORLD.number, 1)]["completed_at"]
    return render_template("academy/certificate.html", summary=summary, earned=(first or "")[:10],
                           today=org_today(g.org), avatars=academy.AVATARS)


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
@login_required
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
@login_required
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
@login_required
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
@login_required
def remove_friend(learner_id, friend_id):
    _learner_or_404(learner_id)
    a, b = _pair(learner_id, friend_id)
    conn = get_db()
    conn.execute("DELETE FROM learner_friends WHERE learner_a = ? AND learner_b = ?", (a, b))
    conn.commit()
    flash("Friend removed.", "ok")
    return redirect(url_for("academy.friends", learner_id=learner_id))


@bp.route("/<int:learner_id>/duels", methods=["POST"])
@login_required
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
    stage = secrets.randbelow(academy.STAGES_PER_TOPIC) + 1
    duel_id = conn.execute(
        "INSERT INTO duels (challenger_id, opponent_id, world, stage, seed, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (learner_id, friend_id, world_number, stage, secrets.token_hex(16), now_iso())).lastrowid
    conn.commit()
    return redirect(url_for("academy.duel", learner_id=learner_id, duel_id=duel_id))


@bp.route("/<int:learner_id>/duels/<int:duel_id>", methods=["GET", "POST"])
@login_required
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
