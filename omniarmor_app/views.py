# -*- coding: utf-8 -*-
"""The signed-in app: overview, industry checks, audit trail, reports,
notifications and settings."""

import csv
import io

from flask import (Blueprint, Response, abort, current_app, flash, g, redirect, render_template, request, session,
                   stream_with_context, url_for)

from . import connections, nudges, plans, usage
from .academy_plan import charges_again
from .auth import COMMON_TIMEZONES, create_invite, is_operator, valid_timezone
from .config import support_email
from .catalog import (ILLNESS_LOG_CHECKS, INDUSTRIES, TOP_COUNT, can_override, counts_time, find_rule, multi_check,
                      top_rank, why_line)
from .db import get_db, now_iso, record_audit
from .security import clean_text, flash_error, home_url, login_required, owner_required
from .tracking import (BULK_ACTIONS, ILLNESS_ACTIONS, ILLNESS_REPORTED, LEVEL_LABEL, ValidationError, add_illness,
                       apply_bulk, apply_change, apply_entry, illness_log, local_date, org_industry_ids, org_now,
                       org_today, remove_illness, states_for_org, tally)

bp = Blueprint("app", __name__, url_prefix="/app")
UPCOMING_DAYS = 60
AUDIT_PAGE = 100
MAX_LOCATIONS = 25      # workspaces one person can own (each is a location, billed on its own)


def _industry_or_404(industry_id):
    if industry_id not in org_industry_ids(get_db(), g.org["id"]):
        abort(404)
    return INDUSTRIES[industry_id]


@bp.app_context_processor
def nav_context():
    if g.get("org") is None:
        return {}
    from .classrooms import is_class_workspace, on_whole_school
    ids = org_industry_ids(get_db(), g.org["id"])
    access = plans.access(g.org)
    # What the workspace's plan allows: base.html's read-only and grace banners, and the industry pages.
    # class_workspace: a school's, whose menus are a classroom's (base.html); school_checklist: whether
    # its menus show the school safety checklist, which comes with Whole school.
    class_workspace = is_class_workspace(g.org)
    return {"nav_industries": [INDUSTRIES[i] for i in ids], "plan_access": access,
            "class_workspace": class_workspace,
            "school_checklist": class_workspace and on_whole_school(g.org, access)}


@bp.route("")
@login_required
def overview():
    from .classrooms import is_class_workspace, on_whole_school
    if is_class_workspace(g.org) and not on_whole_school(g.org):
        # A teacher without Whole school has no school checklist to start on:
        # their home is the classes page (the checklist pages stay readable).
        return redirect(url_for("classes.index"))
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
                           checklist=getting_started(conn, states, ids), next_up=next_reading(states, ids),
                           next_dated=next_reading(states, ids, dated=True), later=later[0] if later else None,
                           top_count=TOP_COUNT, location_nudge=_location_nudge(conn),
                           any_dated=any(s.mode and s.due_date is not None for s in states))


def _location_nudge(conn):
    """The yearly saving, once, for an owner who just added a second
    location (nudges.py: at most one offer a week, never after a dismiss)."""
    if g.role != "owner" or not nudges.allowed(conn, g.user, "second_location"):
        return None
    offer = nudges.location_offer(conn, current_app.config, g.user)
    if offer is not None:
        nudges.mark_shown(conn, g.user["id"], "second_location")
    return offer


def _in_page_order(states, ids):
    """States industry by industry, each industry in its page's order."""
    for i in ids:
        yield from sorted((s for s in states if s.industry_id == i), key=page_order)


def next_reading(states, ids, dated=False):
    """The check to fill in next: the first one without a reading, top checks
    first, industry by industry. With dated, only checks counted from a date."""
    return next((s for s in _in_page_order(states, ids) if s.level == "NONE" and (s.mode or not dated)), None)


def getting_started(conn, states, ids):
    """A new workspace's first steps: pick the checklists, complete the first
    check, set the first reminder, then invite a teammate or choose your
    reminder emails. Each is ticked from what is saved, not from what was
    clicked, and the list is None once every step is done, so it disappears.
    (A school's workspace sees it only with Whole school: see overview.)"""
    read = [s for s in states if s.level != "NONE"]
    dated = [s for s in states if s.mode and s.due_date is not None]
    owner = g.role == "owner"
    teammate = conn.execute("SELECT COUNT(*) FROM memberships WHERE org_id = ?", (g.org["id"],)).fetchone()[0] > 1
    invited = conn.execute("SELECT 1 FROM invites WHERE org_id = ? LIMIT 1", (g.org["id"],)).fetchone() is not None
    chose = bool(g.user["reminders_chosen_at"])
    first_top = next((s for s in _in_page_order(states, ids)
                      if s.level == "NONE" and top_rank(s.industry_id, s.key) is not None), None)
    items = [
        {"key": "checklists", "label": "Pick your checklists", "done": bool(ids),
         "detail": ", ".join(INDUSTRIES[i]["brand"] for i in ids),
         "link": (url_for("app.settings"), "Change them in Settings") if owner else None},
        {"key": "first_check", "label": "Complete your first check", "done": bool(read),
         "next": first_top or next_reading(states, ids),
         "detail": "Answer it or enter its date, then press Save."},
        {"key": "first_reminder", "label": "Set your first reminder", "done": bool(dated),
         "next": next_reading(states, ids, dated=True),
         "detail": "Enter the date of a check that is counted from a date. OmniArmor emails you before it's due."},
        {"key": "team", "label": "Invite a teammate or choose your reminder emails" if owner
         else "Choose your reminder emails", "done": chose or (owner and (teammate or invited)),
         "link": (url_for("app.settings", _anchor="team" if owner else "reminders"),
                  "Open Settings")},
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
    logs = {key: illness_log(get_db(), g.org["id"], i, key) for i, key in ILLNESS_LOG_CHECKS if i == industry_id}
    return render_template("app/industry.html", info=info, states=shown, counts=tally(states), only=only,
                           can_override=can_override, today=now.date(), now=now, counts_time=counts_time,
                           top_rank=top_rank, why_line=why_line, top_count=TOP_COUNT, bulk_actions=BULK_ACTIONS,
                           bundle=_bundle(industry_id), multi_check=multi_check, logs=logs,
                           illness_reported=ILLNESS_REPORTED, illness_actions=ILLNESS_ACTIONS)


def _bundle(industry_id):
    """The Kitchen Safety Bundle on an industry page: the connection's status
    and, per temperature check on the page, its open CyberLogix notes. None
    when the page has no temperature check."""
    keys = [key for i, key in connections.TEMPERATURE_CHECKS if i == industry_id]
    if not keys:
        return None
    conn = get_db()
    info = connections.status(conn, g.org)
    info["notes"] = {key: connections.open_notes(conn, g.org["id"], industry_id, key) for key in keys}
    info["latest"] = {key: connections.latest_report(conn, g.org["id"], industry_id, key) for key in keys}
    info["page_keys"] = set(keys)
    return info


@bp.route("/connections/cyberlogix/review", methods=["POST"])
@login_required
def review_note():
    """Anyone on the team marks a CyberLogix note on a temperature check
    reviewed. The workspace comes from the session; the check must be one
    CyberLogix fills in, in an industry the workspace tracks."""
    industry_id = request.form.get("industry_id", type=int)
    rule_key = request.form.get("rule_key", "")
    day = request.form.get("date", "")
    if (industry_id, rule_key) not in connections.TEMPERATURE_CHECKS:
        abort(404)
    _industry_or_404(industry_id)
    if connections.mark_reviewed(get_db(), g.org["id"], g.user["id"], industry_id, rule_key, day[:10]):
        flash("Note marked reviewed. It stays in the audit trail.", "ok")
    else:
        flash_error("That note was already reviewed or replaced. Reload the page to see the latest.")
    return redirect(url_for("app.industry", industry_id=industry_id, _anchor=f"rule-{rule_key}"))


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


def read_only_message(access):
    """Why nothing can be saved, and what still works."""
    if access["reason"] == "paused" and access["pause_open"]:
        return ("Your plan is paused, with no end date, so the compliance tracker is read-only. Nothing was saved."
                " Your records are safe, and saving comes back when the plan starts again (or start it again now"
                " on the Plans page).")
    if access["reason"] == "paused":
        return (f"Your plan is paused until {local_date(access['resumes_at'], g.org)}, so the compliance tracker is"
                " read-only. Nothing was saved. Your records are safe, and saving comes back when the plan starts"
                " again (or start it again now on the Plans page).")
    why = {"bundle_ended": f"CyberLogix stopped sending signed reports, so the Pro your {plans.BUNDLE_NAME} included"
                           " has ended",
           "plan_ended": "Your plan has ended",
           "new_location": "This location has no plan yet (the free trial is one per owner, and was used in your"
                           " first location)",
           "academy_only": "Your Classroom plan covers the Academy for your class, not the school checklist"
           }.get(access["reason"], "Your free trial has ended")
    from .classrooms import is_class_workspace
    if is_class_workspace(g.org):
        return ("The school safety checklist comes with Whole school, so it is read-only. Nothing was saved. Your"
                " records are safe: you can still see, print and download them. See the classroom plans on the"
                " Plans page.")
    return (f"{why}, so the compliance tracker is read-only. Nothing was saved. Your records are safe: you can"
            " still see, print and download them. Choose Pro or Plus to save new checks.")


def _refuse_if_read_only(industry_id, anchor=None):
    """Without a plan the tracker is read-only (plans.py): a save is refused,
    and nothing else is touched."""
    access = plans.access(g.org)
    if access["tracker"]:
        return None
    flash_error(read_only_message(access))
    target = url_for("app.industry", industry_id=industry_id, only=request.form.get("only") or None)
    return redirect(f"{target}#{anchor}" if anchor else target)


@bp.route("/industry/<int:industry_id>/rule/<rule_key>", methods=["POST"])
@login_required
def change(industry_id, rule_key):
    _industry_or_404(industry_id)
    if find_rule(industry_id, rule_key) is None:
        abort(404)
    refused = _refuse_if_read_only(industry_id, f"rule-{rule_key}")
    if refused:
        return refused
    action = request.form.get("action", "save")
    try:
        message = apply_change(get_db(), g.org, g.user["id"], industry_id, rule_key, action, request.form)
        usage.count(get_db(), "checks_updated")
        flash(message, "ok")
        if action in ("save", "done_today"):
            line = reminder_line(industry_id, rule_key)
            if line:
                flash(line, "ok")
    except ValidationError as exc:
        flash_error(str(exc))
    target = url_for("app.industry", industry_id=industry_id, only=request.form.get("only") or None)
    return redirect(f"{target}#rule-{rule_key}")


@bp.route("/industry/<int:industry_id>/rule/<rule_key>/entries", methods=["POST"])
@login_required
def entry_change(industry_id, rule_key):
    """One entry of a check with one entry per item: add, save, done today or
    remove. The same sign-in, workspace, plan and CSRF checks as a check."""
    _industry_or_404(industry_id)
    if multi_check(industry_id, rule_key) is None:
        abort(404)
    refused = _refuse_if_read_only(industry_id, f"rule-{rule_key}")
    if refused:
        return refused
    action = request.form.get("action", "save")
    try:
        flash(apply_entry(get_db(), g.org, g.user["id"], industry_id, rule_key, action, request.form), "ok")
        usage.count(get_db(), "checks_updated")
        if action in ("add", "save", "done_today"):
            line = reminder_line(industry_id, rule_key)
            if line:
                flash(line, "ok")
    except ValidationError as exc:
        flash_error(str(exc))
    target = url_for("app.industry", industry_id=industry_id, only=request.form.get("only") or None)
    return redirect(f"{target}#rule-{rule_key}")


@bp.route("/industry/<int:industry_id>/rule/<rule_key>/illness", methods=["POST"])
@login_required
def illness_change(industry_id, rule_key):
    """Adds a report to the illness log, or removes one."""
    _industry_or_404(industry_id)
    if (industry_id, rule_key) not in ILLNESS_LOG_CHECKS:
        abort(404)
    refused = _refuse_if_read_only(industry_id, f"rule-{rule_key}")
    if refused:
        return refused
    try:
        if request.form.get("action") == "remove":
            message = remove_illness(get_db(), g.org, g.user["id"], industry_id, rule_key,
                                     request.form.get("entry_id", type=int))
        else:
            message = add_illness(get_db(), g.org, g.user["id"], industry_id, rule_key, request.form)
        flash(message, "ok")
    except ValidationError as exc:
        flash_error(str(exc))
    return redirect(url_for("app.industry", industry_id=industry_id) + f"#rule-{rule_key}")


def reminder_line(industry_id, rule_key):
    """After a save: when the reminder emails for this check go out, for a
    check counted in days from a date. Empty for the others."""
    from .reminders import REMINDER_DAYS
    state = next((s for s in states_for_org(get_db(), g.org, industry_ids=[industry_id]) if s.key == rule_key), None)
    if state is None or not state.mode or state.due_date is None or state.minutes_left is not None:
        return ""
    if not g.user["email_reminders"]:
        return "Your daily reminder emails are off; turn them on in Settings to get one before it's due."
    if state.overdue:
        return "It's overdue, so the team's reminder email lists it each week until it's done."
    if state.days_left == 0:
        return "It's due today, so today's reminder email lists it."
    # Only the reminders still ahead: a 7-day clock started today gets no "30 days before".
    ahead = [d for d in REMINDER_DAYS if d <= state.days_left]
    if not ahead:
        return f"Reminder set: the team gets an email on the day it's due, {state.due_label}."
    days = ", ".join(str(d) for d in ahead[:-1]) + (" and " if len(ahead) > 1 else "") + str(ahead[-1])
    return (f"Reminder set: the team gets an email {days} day{'s' if ahead[-1] != 1 else ''} before it's due"
            f" on {state.due_label}, and on the day.")


@bp.route("/industry/<int:industry_id>/bulk", methods=["POST"])
@login_required
def bulk_change(industry_id):
    """Several checks of one industry at once: done today, Yes, No or one date.
    The same sign-in, workspace and CSRF checks as a single update, and every
    check gets its own audit row. All or nothing."""
    _industry_or_404(industry_id)
    refused = _refuse_if_read_only(industry_id)
    if refused:
        return refused
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
    next_up = None
    if not rows:
        conn = get_db()
        next_up = next_reading(states_for_org(conn, g.org), org_industry_ids(conn, g.org["id"]))
    return render_template("app/audit.html", rows=rows[:AUDIT_PAGE], page=page, more=len(rows) > AUDIT_PAGE,
                           next_up=next_up)


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
    return render_template("app/report.html", groups=groups, counts=tally(states), today=org_today(g.org),
                           next_up=next_reading(states, org_industry_ids(get_db(), g.org["id"])))


@bp.route("/report.csv")
@login_required
def report_csv():
    states = sorted(states_for_org(get_db(), g.org), key=lambda s: (s.industry_id, s.sort_key))
    return _csv_response("omniarmor-compliance-report.csv",
                         ["Industry", "Check", "Status", "Reading", "Due date", "Rule", "Last updated (UTC)", "Updated by"],
                         _report_rows(states))


def _report_rows(states):
    """The report's rows: one per check, then, for a check with several
    entries, one per entry ("Cold holding · Walk-in cooler")."""
    for s in states:
        yield [s.industry["brand"], s.rule.title, LEVEL_LABEL[s.level], s.shown_value, s.due_label,
               s.rule.citation, s.updated_at or "", s.updated_by or ""]
        if len(s.entries) > 1:
            for e in s.entries:
                es = e["state"]
                yield [s.industry["brand"], f"{s.rule.title} · {e['label']}", LEVEL_LABEL[es.level], es.shown_value,
                       es.due_label, s.rule.citation, es.updated_at or "", es.updated_by or ""]


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
    return _settings_page()


def _settings_page(new_key=None):
    """The Settings page. new_key is a connection key just made, shown on
    this one page and never again (only its hash is kept)."""
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
    # Only the account make-operator flagged (auth.is_operator), never just
    # anyone who signed up with the OPERATOR_EMAIL address.
    operator = is_operator(g.user, current_app.config)
    locations = conn.execute(
        "SELECT orgs.id, orgs.name, memberships.role FROM memberships JOIN orgs ON orgs.id = memberships.org_id"
        " WHERE memberships.user_id = ? ORDER BY memberships.created_at, orgs.id", (g.user["id"],)).fetchall()
    from .plan_views import switch_offer
    access = plans.access(g.org)
    return render_template("app/settings.html", members=members, locations=locations,
                           switch_yearly=switch_offer(current_app.config, g.org, access, plans.YEAR),
                           can_add_location=sum(1 for l in locations if l["role"] == "owner") < MAX_LOCATIONS, picked=set(org_industry_ids(conn, g.org["id"])),
                           industries=INDUSTRIES, timezones=COMMON_TIMEZONES, open_invites=invites,
                           access=access, operator=operator, class_limits=plans.class_limits(g.org),
                           usage=usage.last_days(conn) if operator else None, usage_events=usage.EVENTS,
                           support_email=support_email(current_app.config),
                           connection=connections.status(conn, g.org), new_key=new_key,
                           all_temperature_checks=[(INDUSTRIES[i], find_rule(i, key))
                                                   for i, key in connections.TEMPERATURE_CHECKS])


@bp.route("/settings/connections/cyberlogix/create", methods=["POST"])
@owner_required
def connection_create():
    key = connections.create_key(get_db(), g.org["id"], g.user["id"])
    if key is None:
        flash_error("This workspace already has a CyberLogix connection key. Regenerate it to get a new one.")
        return redirect(url_for("app.settings", _anchor="connections"))
    return _settings_page(new_key=key)


@bp.route("/settings/connections/cyberlogix/regenerate", methods=["POST"])
@owner_required
def connection_regenerate():
    return _settings_page(new_key=connections.create_key(get_db(), g.org["id"], g.user["id"], replace=True))


@bp.route("/settings/connections/cyberlogix/revoke", methods=["POST"])
@owner_required
def connection_revoke():
    if connections.revoke_key(get_db(), g.org["id"], g.user["id"]):
        flash("The CyberLogix connection key was revoked. CyberLogix can't send reports until you create a new one.",
              "ok")
    else:
        flash_error("There is no active CyberLogix connection key to revoke.")
    return redirect(url_for("app.settings", _anchor="connections"))


# The reminder emails a person can choose, as (form field and users column, name).
EMAIL_CHOICES = [("email_reminders", "daily digest"), ("email_alerts", "time-limit alerts")]


@bp.route("/settings/reminders", methods=["POST"])
@login_required
def settings_reminders():
    weekly = [("email_weekly", "weekly Autopilot report")] if is_operator(g.user, current_app.config) else []
    choices = EMAIL_CHOICES + weekly
    picked = {field: request.form.get(field) == "on" for field, _ in choices}
    conn = get_db()
    conn.execute(f"UPDATE users SET {', '.join(f'{field} = ?' for field in picked)}, reminders_chosen_at = ?"
                 " WHERE id = ?", (*(int(on) for on in picked.values()), now_iso(), g.user["id"]))
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


@bp.route("/settings/locations/add", methods=["POST"])
@owner_required
def add_location():
    """Another location for the same business: a new workspace the owner
    owns, with this one's timezone and industries (both can be changed in
    its Settings). Each location is billed on its own (plans.location_count).
    The free trial is one per owner, used by the workspace they signed up
    with: a location added later starts without one (its trial ends the
    moment it is made), so the owner chooses a plan for it. Deleting a
    location and adding it again doesn't give a new one either."""
    conn = get_db()
    name = clean_text(request.form.get("name"), 120)
    owned = conn.execute("SELECT COUNT(*) FROM memberships WHERE user_id = ? AND role = 'owner'",
                         (g.user["id"],)).fetchone()[0]
    if not name:
        flash_error("Enter the new location's name, without line breaks.")
        return redirect(url_for("app.settings", _anchor="locations"))
    if owned >= MAX_LOCATIONS:
        flash_error(f"One account can own up to {MAX_LOCATIONS} locations. Please contact us for more.")
        return redirect(url_for("app.settings", _anchor="locations"))
    now = now_iso()
    industries = org_industry_ids(conn, g.org["id"])
    org_id = conn.execute("INSERT INTO orgs (name, timezone, created_at, academy_trial_ends) VALUES (?, ?, ?, ?)",
                          (name, g.org["timezone"], now, now)).lastrowid
    conn.execute("INSERT INTO memberships (user_id, org_id, role, created_at) VALUES (?, ?, 'owner', ?)",
                 (g.user["id"], org_id, now))
    conn.executemany("INSERT INTO org_industries (org_id, industry_id) VALUES (?, ?)", [(org_id, i) for i in industries])
    record_audit(conn, org_id, g.user["id"], "workspace",
                 f"Location created from {g.org['name']} with {len(industries)} industries")
    conn.commit()
    usage.count(conn, "locations_added")
    session["org_id"] = org_id
    flash(f"{name} is ready, with the same industries as {g.org['name']}. You're working in it now; switch"
          " locations in Settings. It has no free trial (that's one per owner): choose a plan for it on the Plans"
          " page.", "ok")
    return redirect(url_for("app.overview"))


@bp.route("/settings/locations/<int:org_id>/switch", methods=["POST"])
@login_required
def switch_location(org_id):
    if not 0 < org_id < 2 ** 63:
        abort(404)
    row = get_db().execute("SELECT orgs.name FROM memberships JOIN orgs ON orgs.id = memberships.org_id"
                           " WHERE memberships.user_id = ? AND memberships.org_id = ?", (g.user["id"], org_id)).fetchone()
    if row is None:
        abort(404)
    session["org_id"] = org_id
    flash(f"You're working in {row['name']} now.", "ok")
    return redirect(home_url())


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
        flash_error("Cancel your plan first (Plan page, Manage billing), then delete the workspace. Once it's"
                    " cancelled you can delete right away, even before the paid time runs out.")
        return redirect(url_for("app.settings"))
    member_ids = [r["user_id"] for r in conn.execute("SELECT user_id FROM memberships WHERE org_id = ?", (org_id,))]
    name = g.org["name"]
    conn.execute("DELETE FROM orgs WHERE id = ?", (org_id,))
    for uid in member_ids:
        conn.execute("DELETE FROM users WHERE id = ? AND NOT EXISTS (SELECT 1 FROM memberships WHERE user_id = ?)",
                     (uid, uid))
    conn.commit()
    # One location of several: the owner stays signed in, in another of
    # their locations. Their last one: signed out, as the account is gone.
    other = conn.execute("SELECT orgs.id, orgs.name FROM memberships JOIN orgs ON orgs.id = memberships.org_id"
                         " WHERE memberships.user_id = ? ORDER BY memberships.role = 'owner' DESC,"
                         " memberships.created_at, orgs.id LIMIT 1", (g.user["id"],)).fetchone()
    if other is not None:
        session["org_id"] = other["id"]
        flash(f"{name} and its data were deleted. You're working in {other['name']} now.", "ok")
        return redirect(home_url())
    session.clear()
    flash("Your workspace and its data were deleted.", "ok")
    return redirect(url_for("public.home"))
