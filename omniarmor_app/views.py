# -*- coding: utf-8 -*-
"""The signed-in app: overview, industry checks, audit trail, reports,
notifications and settings."""

import csv
import io

from flask import (Blueprint, Response, abort, current_app, flash, g, redirect, render_template, request, session,
                   stream_with_context, url_for)

from . import usage
from .academy_plan import charges_again, plan_status
from .auth import COMMON_TIMEZONES, create_invite, valid_timezone
from .catalog import INDUSTRIES, TOP_COUNT, can_override, counts_time, find_rule, top_rank, why_line
from .db import get_db, now_iso, record_audit
from .security import clean_text, flash_error, login_required, owner_required
from .tracking import (BULK_ACTIONS, LEVEL_LABEL, ValidationError, apply_bulk, apply_change, org_industry_ids,
                       org_now, org_today, states_for_org, tally)

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
    ids = org_industry_ids(conn, g.org["id"])
    problems = sorted([s for s in states if s.problem], key=lambda s: s.sort_key)
    upcoming = sorted([s for s in states if s.due_date and 0 <= s.days_left <= UPCOMING_DAYS and not s.problem],
                      key=lambda s: s.days_left)
    later = sorted([s for s in states if s.due_date and s.days_left > UPCOMING_DAYS and not s.problem],
                   key=lambda s: s.days_left)
    missing = [s for s in states if s.level == "NONE"]
    by_industry = []
    for i in ids:
        mine = [s for s in states if s.industry_id == i]
        by_industry.append({"industry": INDUSTRIES[i], "counts": tally(mine)})
    return render_template("app/overview.html", counts=tally(states), problems=problems, upcoming=upcoming,
                           missing=len(missing), by_industry=by_industry, today=today, total=len(states),
                           checklist=first_day_checklist(states, ids), next_up=next_reading(states, ids),
                           next_dated=next_reading(states, ids, dated=True), later=later[0] if later else None,
                           top_count=TOP_COUNT)


def _in_page_order(states, ids):
    """States industry by industry, each industry in its page's order."""
    for i in ids:
        yield from sorted((s for s in states if s.industry_id == i), key=page_order)


def next_reading(states, ids, dated=False):
    """The check to fill in next: the first one without a reading, top checks
    first, industry by industry. With dated, only checks counted from a date."""
    return next((s for s in _in_page_order(states, ids) if s.level == "NONE" and (s.mode or not dated)), None)


def first_day_checklist(states, ids):
    """The new workspace's first steps, each ticked from what is saved, not
    from what was clicked. None once every step is done, so it disappears."""
    tops = [s for s in states if top_rank(s.industry_id, s.key) is not None]
    first_top = next((s for s in _in_page_order(tops, ids) if s.level == "NONE"), None)
    first_any = next_reading(states, ids)
    read = [s for s in states if s.level != "NONE"]
    top_read = [s for s in tops if s.level != "NONE"]
    items = [
        {"label": "Create your workspace", "done": True},
        {"label": "Save your first check", "done": bool(read), "next": first_any},
        {"label": f"Fill in the top {TOP_COUNT} checks" + (" of each industry" if len(ids) > 1 else ""),
         "done": len(top_read) == len(tops), "progress": f"{len(top_read)} of {len(tops)}", "next": first_top},
        {"label": "Give every check its first reading", "done": len(read) == len(states),
         "progress": f"{len(read)} of {len(states)}", "next": first_any},
    ]
    if all(item["done"] for item in items):
        return None
    return {"items": items, "done": sum(item["done"] for item in items), "total": len(items)}


@bp.route("/industry/<int:industry_id>")
@login_required
def industry(industry_id):
    info = _industry_or_404(industry_id)
    now = org_now(g.org)
    states = sorted(states_for_org(get_db(), g.org, industry_ids=[industry_id], now=now), key=page_order)
    only = request.args.get("only") == "problems"
    shown = [s for s in states if s.problem] if only else states
    return render_template("app/industry.html", info=info, states=shown, counts=tally(states), only=only,
                           can_override=can_override, today=now.date(), now=now, counts_time=counts_time,
                           top_rank=top_rank, why_line=why_line, top_count=TOP_COUNT, bulk_actions=BULK_ACTIONS)


def page_order(state):
    """An industry page's order: problems first (blocked, then warnings, the
    most urgent first), then the industry's top checks in their own order
    (catalog.top_checks), then the rest."""
    if state.problem:
        return (0, state.sort_key)
    rank = top_rank(state.industry_id, state.key)
    if rank is not None:
        return (1, (rank,))
    return (2, state.sort_key)


@bp.route("/industry/<int:industry_id>/rule/<rule_key>", methods=["POST"])
@login_required
def change(industry_id, rule_key):
    _industry_or_404(industry_id)
    if find_rule(industry_id, rule_key) is None:
        abort(404)
    action = request.form.get("action", "save")
    try:
        message = apply_change(get_db(), g.org, g.user["id"], industry_id, rule_key, action, request.form)
        usage.count(get_db(), "checks_updated")
        flash(message, "ok")
    except ValidationError as exc:
        flash_error(str(exc))
    target = url_for("app.industry", industry_id=industry_id, only=request.form.get("only") or None)
    return redirect(f"{target}#rule-{rule_key}")


@bp.route("/industry/<int:industry_id>/bulk", methods=["POST"])
@login_required
def bulk_change(industry_id):
    """Several checks of one industry at once: done today, Yes, No or one date.
    The same sign-in, workspace and CSRF checks as a single update, and every
    check gets its own audit row. All or nothing."""
    _industry_or_404(industry_id)
    action = request.form.get("bulk_action", "")
    try:
        count = apply_bulk(get_db(), g.org, g.user["id"], industry_id, request.form.getlist("keys"), action,
                           request.form.get("date"))
        usage.count(get_db(), "bulk_updates")
        usage.count(get_db(), "checks_updated", count)
        flash(f"Updated {count} check{'s' if count != 1 else ''}: {BULK_ACTIONS[action].lower()}"
              + (f" to {request.form.get('date').strip()}." if action == "date" else "."), "ok")
    except ValidationError as exc:
        flash_error(f"{exc} Nothing was changed.")
    return redirect(url_for("app.industry", industry_id=industry_id, only=request.form.get("only") or None))


@bp.route("/audit")
@login_required
def audit():
    # Past SQLite's integer range a page number crashed the query; no trail is that long.
    page = min(max(1, request.args.get("page", 1, type=int)), 10 ** 9)
    rows = list(_audit_rows(limit=AUDIT_PAGE + 1, offset=(page - 1) * AUDIT_PAGE))
    return render_template("app/audit.html", rows=rows[:AUDIT_PAGE], page=page, more=len(rows) > AUDIT_PAGE)


# Newest first. The index audit_org_at_id (migration 12) holds this order.
AUDIT_QUERY = ("SELECT audit.*, COALESCE(users.name, audit.user_name) AS user_name FROM audit"
               " LEFT JOIN users ON users.id = audit.user_id"
               " WHERE audit.org_id = ? ORDER BY audit.at DESC, audit.id DESC")


def _audit_rows(limit=None, offset=0):
    """The company's audit rows, newest first, one at a time (a long trail is
    never held in memory all at once)."""
    sql = AUDIT_QUERY
    params = [g.org["id"]]
    if limit is not None:
        sql += " LIMIT ? OFFSET ?"
        params += [limit, offset]
    for r in get_db().execute(sql, params):
        rule = find_rule(r["industry_id"], r["rule_key"]) if r["industry_id"] else None
        yield {**dict(r), "industry": INDUSTRIES.get(r["industry_id"], {}).get("brand", ""),
               "rule_title": rule.title if rule else ""}


def _csv_cell(value):
    """Stops spreadsheet programs from running a cell as a formula."""
    text = "" if value is None else str(value)
    return "'" + text if text[:1] in ("=", "+", "-", "@", "\t", "\r") else text


CSV_CHUNK_ROWS = 1000


def _csv_response(filename, header, rows):
    """Sends a CSV as it is written, CSV_CHUNK_ROWS rows at a time. The whole
    file used to be built in memory first: a workspace with half a million
    audit rows took the server to 830 MB for one export (over the smallest
    hosting plans' memory) and sent nothing for 10 seconds or more."""
    def chunks():
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(header)
        for n, row in enumerate(rows, 1):
            writer.writerow([_csv_cell(v) for v in row])
            if n % CSV_CHUNK_ROWS == 0:
                yield buf.getvalue()
                buf.seek(0)
                buf.truncate()
        yield buf.getvalue()
    return Response(stream_with_context(chunks()), mimetype="text/csv",
                    headers={"Content-Disposition": f'attachment; filename="{filename}"'})


@bp.route("/audit.csv")
@login_required
def audit_csv():
    return _csv_response("omniarmor-audit-trail.csv",
                         ["Time (UTC)", "Person", "Action", "Industry", "Check", "Before", "After", "Summary"],
                         ([r["at"], r["user_name"] or "System", r["action"], r["industry"], r["rule_title"],
                           r["before"], r["after"], r["summary"]] for r in _audit_rows()))


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
                           s.due_label, s.rule.citation,
                           s.updated_at or "", s.updated_by or ""] for s in states])


@bp.route("/notifications")
@login_required
def notifications():
    rows = get_db().execute(
        "SELECT * FROM notifications WHERE org_id = ? OR (org_id IS NULL AND user_id = ?)"
        " ORDER BY created_at DESC, id DESC LIMIT 200",
        (g.org["id"], g.user["id"]),
    ).fetchall()
    next_dated = None
    if not rows:
        conn = get_db()
        next_dated = next_reading(states_for_org(conn, g.org), org_industry_ids(conn, g.org["id"]), dated=True)
    return render_template("app/notifications.html", rows=rows, next_dated=next_dated)


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
                           industries=INDUSTRIES, timezones=COMMON_TIMEZONES, open_invites=invites,
                           plan=plan_status(g.org), operator=is_operator(g.user),
                           usage=usage.last_days(conn) if is_operator(g.user) else None, usage_events=usage.EVENTS,
                           support_email=current_app.config.get("SUPPORT_EMAIL", ""))


def is_operator(user):
    """Whether this account has the address Autopilot emails (OPERATOR_EMAIL):
    only that person gets the weekly Autopilot report, so only they see its choice."""
    to = (current_app.config.get("OPERATOR_EMAIL") or "").strip().lower()
    return bool(to) and user["email"].lower() == to


# The reminder emails a person can choose, as (form field and users column, name).
EMAIL_CHOICES = [("email_reminders", "daily digest"), ("email_alerts", "time-limit alerts")]


@bp.route("/settings/reminders", methods=["POST"])
@login_required
def settings_reminders():
    choices = EMAIL_CHOICES + ([("email_weekly", "weekly Autopilot report")] if is_operator(g.user) else [])
    picked = {field: request.form.get(field) == "on" for field, _ in choices}
    conn = get_db()
    conn.execute(f"UPDATE users SET {', '.join(f'{field} = ?' for field in picked)} WHERE id = ?",
                 (*(int(on) for on in picked.values()), g.user["id"]))
    conn.commit()
    said = ", ".join(f"{name} {'on' if picked[field] else 'off'}" for field, name in choices)
    flash(f"Saved: {said[0].upper()}{said[1:]}.", "ok")
    return redirect(url_for("app.settings", _anchor="reminders"))


@bp.route("/settings/company", methods=["POST"])
@owner_required
def settings_company():
    name = clean_text(request.form.get("name"), 120)
    tz = request.form.get("timezone", "")
    picked = sorted({int(i) for i in request.form.getlist("industries") if i.isascii() and i.isdigit() and len(i) < 6 and int(i) in INDUSTRIES})
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
    if user_id > 2 ** 63 - 1:
        abort(404)  # past SQLite's integer range: no such person, and the query would crash
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
    # A workspace being paid for is not deleted out from under its plan: the
    # subscription would go on charging with no workspace to cancel it from.
    # Once it's cancelled (it runs to the end of the paid period), deleting is fine.
    plan = conn.execute("SELECT * FROM orgs WHERE id = ?", (org_id,)).fetchone()
    if plan and charges_again(plan):
        flash_error("Cancel your Academy plan first (Academy plan page, Manage or cancel), then delete the workspace.")
        return redirect(url_for("app.settings"))
    member_ids = [r["user_id"] for r in conn.execute("SELECT user_id FROM memberships WHERE org_id = ?", (org_id,))]
    conn.execute("DELETE FROM orgs WHERE id = ?", (org_id,))
    for uid in member_ids:
        conn.execute("DELETE FROM users WHERE id = ? AND NOT EXISTS (SELECT 1 FROM memberships WHERE user_id = ?)",
                     (uid, uid))
    conn.commit()
    session.clear()
    flash("Your workspace and its data were deleted.", "ok")
    return redirect(url_for("public.home"))
