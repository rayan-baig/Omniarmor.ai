# -*- coding: utf-8 -*-
"""The signed-in app: overview, industry checks, audit trail, reports,
notifications and settings."""

import csv
import io

from flask import Blueprint, Response, abort, flash, g, redirect, render_template, request, session, url_for

from .auth import COMMON_TIMEZONES, create_invite, valid_timezone
from .catalog import INDUSTRIES, can_override, find_rule
from .db import get_db, now_iso, record_audit
from .security import clean_text, flash_error, login_required, owner_required
from .tracking import LEVEL_LABEL, ValidationError, apply_change, org_industry_ids, org_today, states_for_org, tally

bp = Blueprint("app", __name__, url_prefix="/app")
UPCOMING_DAYS = 60
AUDIT_PAGE = 100


def _industry_or_404(industry_id):
    if industry_id not in org_industry_ids(get_db(), g.org["id"]):
        abort(404)
    return INDUSTRIES[industry_id]


@bp.app_context_processor
def nav_context():
    if g.get("org") is None:
        return {}
    ids = org_industry_ids(get_db(), g.org["id"])
    return {"nav_industries": [INDUSTRIES[i] for i in ids]}


@bp.route("")
@login_required
def overview():
    conn = get_db()
    states = states_for_org(conn, g.org)
    today = org_today(g.org)
    problems = sorted([s for s in states if s.problem], key=lambda s: s.sort_key)
    upcoming = sorted([s for s in states if s.due_date and 0 <= s.days_left <= UPCOMING_DAYS and not s.problem],
                      key=lambda s: s.days_left)
    missing = [s for s in states if s.level == "NONE"]
    by_industry = []
    for i in org_industry_ids(conn, g.org["id"]):
        mine = [s for s in states if s.industry_id == i]
        by_industry.append({"industry": INDUSTRIES[i], "counts": tally(mine)})
    return render_template("app/overview.html", counts=tally(states), problems=problems, upcoming=upcoming,
                           missing=len(missing), by_industry=by_industry, today=today, total=len(states))


@bp.route("/industry/<int:industry_id>")
@login_required
def industry(industry_id):
    info = _industry_or_404(industry_id)
    states = sorted(states_for_org(get_db(), g.org, industry_ids=[industry_id]), key=lambda s: s.sort_key)
    only = request.args.get("only") == "problems"
    shown = [s for s in states if s.problem] if only else states
    return render_template("app/industry.html", info=info, states=shown, counts=tally(states), only=only,
                           can_override=can_override, today=org_today(g.org))


@bp.route("/industry/<int:industry_id>/rule/<rule_key>", methods=["POST"])
@login_required
def change(industry_id, rule_key):
    _industry_or_404(industry_id)
    if find_rule(industry_id, rule_key) is None:
        abort(404)
    action = request.form.get("action", "save")
    try:
        message = apply_change(get_db(), g.org, g.user["id"], industry_id, rule_key, action, request.form)
        flash(message, "ok")
    except ValidationError as exc:
        flash_error(str(exc))
    target = url_for("app.industry", industry_id=industry_id, only=request.form.get("only") or None)
    return redirect(f"{target}#rule-{rule_key}")


@bp.route("/audit")
@login_required
def audit():
    page = max(1, request.args.get("page", 1, type=int))
    rows = _audit_rows(limit=AUDIT_PAGE + 1, offset=(page - 1) * AUDIT_PAGE)
    return render_template("app/audit.html", rows=rows[:AUDIT_PAGE], page=page, more=len(rows) > AUDIT_PAGE)


def _audit_rows(limit=None, offset=0):
    sql = ("SELECT audit.*, users.name AS user_name FROM audit LEFT JOIN users ON users.id = audit.user_id"
           " WHERE audit.org_id = ? ORDER BY audit.at DESC, audit.id DESC")
    params = [g.org["id"]]
    if limit is not None:
        sql += " LIMIT ? OFFSET ?"
        params += [limit, offset]
    rows = []
    for r in get_db().execute(sql, params):
        rule = find_rule(r["industry_id"], r["rule_key"]) if r["industry_id"] else None
        rows.append({**dict(r), "industry": INDUSTRIES.get(r["industry_id"], {}).get("brand", ""),
                     "rule_title": rule.title if rule else ""})
    return rows


def _csv_cell(value):
    """Stops spreadsheet programs from running a cell as a formula."""
    text = "" if value is None else str(value)
    return "'" + text if text[:1] in ("=", "+", "-", "@", "\t", "\r") else text


def _csv_response(filename, header, rows):
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(header)
    for row in rows:
        writer.writerow([_csv_cell(v) for v in row])
    return Response(buf.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": f'attachment; filename="{filename}"'})


@bp.route("/audit.csv")
@login_required
def audit_csv():
    rows = _audit_rows()
    return _csv_response("omniarmor-audit-trail.csv",
                         ["Time (UTC)", "Person", "Action", "Industry", "Check", "Before", "After", "Summary"],
                         [[r["at"], r["user_name"] or "System", r["action"], r["industry"], r["rule_title"],
                           r["before"], r["after"], r["summary"]] for r in rows])


@bp.route("/report")
@login_required
def report():
    states = states_for_org(get_db(), g.org)
    groups = []
    for i in org_industry_ids(get_db(), g.org["id"]):
        mine = sorted([s for s in states if s.industry_id == i], key=lambda s: s.sort_key)
        groups.append({"industry": INDUSTRIES[i], "states": mine, "counts": tally(mine)})
    return render_template("app/report.html", groups=groups, counts=tally(states), today=org_today(g.org))


@bp.route("/report.csv")
@login_required
def report_csv():
    states = sorted(states_for_org(get_db(), g.org), key=lambda s: (s.industry_id, s.sort_key))
    return _csv_response("omniarmor-compliance-report.csv",
                         ["Industry", "Check", "Status", "Reading", "Due date", "Rule", "Last updated (UTC)", "Updated by"],
                         [[s.industry["brand"], s.rule.title, LEVEL_LABEL[s.level], s.shown_value,
                           s.due_date.isoformat() if s.due_date else "", s.rule.citation,
                           s.updated_at or "", s.updated_by or ""] for s in states])


@bp.route("/notifications")
@login_required
def notifications():
    rows = get_db().execute(
        "SELECT * FROM notifications WHERE org_id = ? OR (org_id IS NULL AND user_id = ?)"
        " ORDER BY created_at DESC, id DESC LIMIT 200",
        (g.org["id"], g.user["id"]),
    ).fetchall()
    return render_template("app/notifications.html", rows=rows)


@bp.route("/settings", methods=["GET"])
@login_required
def settings():
    conn = get_db()
    members = conn.execute(
        "SELECT users.id, users.name, users.email, memberships.role FROM memberships"
        " JOIN users ON users.id = memberships.user_id WHERE memberships.org_id = ? ORDER BY memberships.created_at",
        (g.org["id"],),
    ).fetchall()
    invites = conn.execute(
        "SELECT COUNT(*) FROM invites WHERE org_id = ? AND used_at IS NULL AND expires_at > ?",
        (g.org["id"], now_iso()),
    ).fetchone()[0]
    return render_template("app/settings.html", members=members, picked=set(org_industry_ids(conn, g.org["id"])),
                           industries=INDUSTRIES, timezones=COMMON_TIMEZONES, open_invites=invites)


@bp.route("/settings/reminders", methods=["POST"])
@login_required
def settings_reminders():
    on = request.form.get("email_reminders") == "on"
    conn = get_db()
    conn.execute("UPDATE users SET email_reminders = ? WHERE id = ?", (1 if on else 0, g.user["id"]))
    conn.commit()
    flash("Email reminders are " + ("on." if on else "off."), "ok")
    return redirect(url_for("app.settings"))


@bp.route("/settings/company", methods=["POST"])
@owner_required
def settings_company():
    name = clean_text(request.form.get("name"), 120)
    tz = request.form.get("timezone", "")
    picked = sorted({int(i) for i in request.form.getlist("industries") if i.isdigit() and int(i) in INDUSTRIES})
    if not name:
        flash_error("Enter your company name, without line breaks.")
    elif not valid_timezone(tz):
        flash_error("Pick a valid timezone.")
    elif not picked:
        flash_error("Keep at least one industry.")
    else:
        conn = get_db()
        before = set(org_industry_ids(conn, g.org["id"]))
        conn.execute("UPDATE orgs SET name = ?, timezone = ? WHERE id = ?", (name, tz, g.org["id"]))
        conn.execute("DELETE FROM org_industries WHERE org_id = ?", (g.org["id"],))
        conn.executemany("INSERT INTO org_industries (org_id, industry_id) VALUES (?, ?)",
                         [(g.org["id"], i) for i in picked])
        added = [INDUSTRIES[i]["brand"] for i in picked if i not in before]
        removed = [INDUSTRIES[i]["brand"] for i in before if i not in picked]
        detail = "; ".join(filter(None, [f"added {', '.join(added)}" if added else "",
                                         f"removed {', '.join(removed)}" if removed else ""]))
        record_audit(conn, g.org["id"], g.user["id"], "workspace",
                     f"Company settings updated{': ' + detail if detail else ''}")
        conn.commit()
        flash("Company settings saved. Readings for removed industries are kept in case you add them back.", "ok")
    return redirect(url_for("app.settings"))


@bp.route("/settings/invite", methods=["POST"])
@owner_required
def settings_invite():
    link = create_invite(get_db(), g.org["id"], g.user["id"])
    flash(f"Invite link (valid 7 days, works once): {link}", "invite")
    return redirect(url_for("app.settings"))


@bp.route("/settings/member/<int:user_id>/remove", methods=["POST"])
@owner_required
def remove_member(user_id):
    conn = get_db()
    if user_id == g.user["id"]:
        flash_error("You can't remove yourself. Delete the workspace instead.")
        return redirect(url_for("app.settings"))
    member = conn.execute("SELECT users.name FROM memberships JOIN users ON users.id = memberships.user_id"
                          " WHERE memberships.org_id = ? AND memberships.user_id = ?", (g.org["id"], user_id)).fetchone()
    if member is None:
        abort(404)
    conn.execute("DELETE FROM memberships WHERE org_id = ? AND user_id = ?", (g.org["id"], user_id))
    conn.execute("UPDATE users SET session_epoch = session_epoch + 1 WHERE id = ?", (user_id,))
    conn.execute("DELETE FROM users WHERE id = ? AND NOT EXISTS (SELECT 1 FROM memberships WHERE user_id = ?)",
                 (user_id, user_id))
    record_audit(conn, g.org["id"], g.user["id"], "team", f"{member['name']} was removed from the team")
    conn.commit()
    flash(f"{member['name']} was removed and signed out.", "ok")
    return redirect(url_for("app.settings"))


@bp.route("/settings/delete", methods=["POST"])
@owner_required
def delete_workspace():
    if request.form.get("confirm", "").strip() != g.org["name"]:
        flash_error("Type the company name exactly to delete the workspace.")
        return redirect(url_for("app.settings"))
    conn = get_db()
    org_id = g.org["id"]
    member_ids = [r["user_id"] for r in conn.execute("SELECT user_id FROM memberships WHERE org_id = ?", (org_id,))]
    conn.execute("DELETE FROM orgs WHERE id = ?", (org_id,))
    for uid in member_ids:
        conn.execute("DELETE FROM users WHERE id = ? AND NOT EXISTS (SELECT 1 FROM memberships WHERE user_id = ?)",
                     (uid, uid))
    conn.commit()
    session.clear()
    flash("Your workspace and its data were deleted.", "ok")
    return redirect(url_for("public.home"))
