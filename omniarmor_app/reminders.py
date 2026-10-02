# -*- coding: utf-8 -*-
"""Daily reminder digests.

Every date-tracked check falls into a window as its deadline gets closer:
30 days out, 7 days out, 1 day out, due today, and then each week it stays
overdue. The first daily run that finds a check in a new window sends one
reminder for it, so a missed day is caught up the next morning. A window only
counts as reminded once at least one email went out (or was saved, when email
isn't set up); if every send fails, the next run tries again.
"""

import logging

from .db import now_iso
from .notify import notify
from .tracking import org_today, states_for_org, tally

log = logging.getLogger("omniarmor.reminders")


def reminder_window(days_left):
    """The reminder window a deadline is in today, or None when it's more than 30 days out."""
    if days_left is None or days_left > 30:
        return None
    if days_left >= 8:
        return "due-in-30"
    if days_left >= 2:
        return "due-in-7"
    if days_left == 1:
        return "due-in-1"
    if days_left == 0:
        return "due-today"
    weeks_overdue = (-days_left - 1) // 7
    return f"overdue-week-{weeks_overdue}"


def _line(state):
    d = state.days_left
    if d < 0:
        when = f"{-d} day{'s' if d != -1 else ''} overdue"
    elif d == 0:
        when = "due today"
    else:
        when = f"due in {d} day{'s' if d != 1 else ''}"
    return f"- {state.industry['brand']}: {state.rule.title}, {when} ({state.due_date.isoformat()}). {state.rule.action}"


def build_digest(org, triggered, all_states, base_url, today):
    overdue = [s for s in triggered if s.days_left < 0]
    soon = [s for s in triggered if s.days_left >= 0]
    counts = tally(all_states)
    parts = []
    if overdue:
        parts.append(f"{len(overdue)} overdue")
    if soon:
        parts.append(f"{len(soon)} coming due")
    subject = f"OmniArmor: {', '.join(parts)} for {org['name']}"
    lines = [f"Compliance reminders for {org['name']}, {today.isoformat()}.", ""]
    if overdue:
        lines += ["OVERDUE"] + [_line(s) for s in sorted(overdue, key=lambda s: s.days_left)] + [""]
    if soon:
        lines += ["COMING DUE"] + [_line(s) for s in sorted(soon, key=lambda s: s.days_left)] + [""]
    lines += [
        f"Right now: {counts['BLOCKED']} blocked, {counts['WARNING']} warnings, {counts['CLEARED']} cleared,"
        f" {counts['NONE']} without a reading.",
        f"Open your checks: {base_url}/app",
        "",
        "You get this email because reminders are on in your OmniArmor settings.",
    ]
    return subject, "\n".join(lines)


def _already_reminded(conn, org_id, state, window):
    return conn.execute(
        "SELECT 1 FROM reminder_marks WHERE org_id = ? AND industry_id = ? AND rule_key = ? AND due_date = ? AND threshold = ?",
        (org_id, state.industry_id, state.rule.key, state.due_date.isoformat(), window),
    ).fetchone() is not None


def _remind_org(conn, cfg, org, today):
    states = states_for_org(conn, org, today=today)
    pending = []
    for s in states:
        window = reminder_window(s.days_left)
        if window is not None and not _already_reminded(conn, org["id"], s, window):
            pending.append((s, window))
    if not pending:
        return 0, 0
    recipients = conn.execute(
        "SELECT users.* FROM users JOIN memberships ON memberships.user_id = users.id"
        " WHERE memberships.org_id = ? AND users.email_reminders = 1",
        (org["id"],),
    ).fetchall()
    delivered = 0
    if recipients:
        subject, body = build_digest(org, [s for s, _ in pending], states, cfg["BASE_URL"], today)
        for user in recipients:
            status = notify(conn, cfg, "reminder", user["email"], subject, body, org_id=org["id"], user_id=user["id"])
            delivered += status in ("sent", "logged")
    if delivered or not recipients:
        conn.executemany(
            "INSERT OR IGNORE INTO reminder_marks (org_id, industry_id, rule_key, due_date, threshold, sent_at)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            [(org["id"], s.industry_id, s.rule.key, s.due_date.isoformat(), w, now_iso()) for s, w in pending],
        )
        conn.commit()
        return len(pending), delivered
    return 0, 0


def run_reminders(conn, cfg, today_for=None):
    """Sends today's digests. today_for(org) can override the date (for tests).
    One company's failure is logged and never stops the others."""
    summary = {"orgs": 0, "digests": 0, "reminders": 0, "errors": 0}
    for org in conn.execute("SELECT * FROM orgs ORDER BY id").fetchall():
        summary["orgs"] += 1
        try:
            today = today_for(org) if today_for else org_today(org)
            reminders, digests = _remind_org(conn, cfg, org, today)
            summary["reminders"] += reminders
            summary["digests"] += digests
        except Exception:
            conn.rollback()
            summary["errors"] += 1
            log.exception("reminders failed for org %s", org["id"])
    return summary
