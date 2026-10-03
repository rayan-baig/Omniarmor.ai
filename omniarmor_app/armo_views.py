# -*- coding: utf-8 -*-
"""Armo outside the Academy: the companion that sits above the tab bar, its
status feed for live updates, and the page where people pick a personality."""

from flask import Blueprint, abort, current_app, flash, g, jsonify, redirect, render_template, request, url_for

from . import armo
from .db import get_db
from .security import flash_error, login_required

bp = Blueprint("armo", __name__, url_prefix="/app/armo")


def current_state():
    """Armo's view of the signed-in company, worked out once per request."""
    if "armo_state" not in g:
        try:
            g.armo_state = armo.summary(get_db(), g.org) if g.get("org") is not None else None
        except Exception:  # never let the helper break a page, including error pages
            current_app.logger.exception("Armo could not check this workspace")
            g.armo_state = None
    return g.armo_state


@bp.app_context_processor
def armo_context():
    return {"armo_state": current_state, "armo_personality": armo.personality,
            "armo_personalities": armo.PERSONALITIES, "armo_voice": armo.voice}


@bp.route("")
@login_required
def page():
    if current_state() is None:
        abort(503)
    return render_template("app/armo.html", state=current_state(), hidden=g.user["armo"] == armo.HIDDEN,
                           me=armo.personality(g.user["armo"]))


@bp.route("/status")
@login_required
def status():
    state = current_state()
    if state is None:
        return jsonify(error="unavailable"), 503
    top = state["top"]
    return jsonify(needs=state["needs"], urgent=state["urgent"], signature=state["signature"], mood=state["mood"],
                   top={"title": top["title"], "url": top["url"]} if top else None)


@bp.route("/personality", methods=["POST"])
@login_required
def choose():
    key = request.form.get("armo", "")
    if key != armo.HIDDEN and key not in armo.PERSONALITIES:
        flash_error("Pick one of Armo's personalities.")
    else:
        conn = get_db()
        conn.execute("UPDATE users SET armo = ? WHERE id = ?", (key, g.user["id"]))
        conn.commit()
        if key == armo.HIDDEN:
            flash("Armo is hidden. You can bring him back here anytime.", "ok")
        else:
            flash(f"Say hi to {armo.PERSONALITIES[key].name} Armo!", "ok")
    return redirect(url_for("armo.page"))
