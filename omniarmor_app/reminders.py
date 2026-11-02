# -*- coding: utf-8 -*-
"""Daily reminder digests, and time-limit alerts for the hour and minute clocks.

Every date-tracked check falls into a window as its deadline gets closer:
30 days out, 7 days out, 1 day out, due today, and then each week it stays
overdue. The first daily run that finds a check in a new window sends one
reminder for it, so a missed day is caught up the next morning. A window only
counts as reminded once at least one email went out (or was saved, when email
isn't set up); if every send fails, the next run tries again.

A clock of a few hours can start and run out between two daily digests, so the
hour and minute clocks also get alerts, checked every minute (jobs.py): one
email when a clock reaches its warning point and one when it becomes overdue,
each once per start of the clock. They follow the same rule for failed sends,
and the digest leaves out a clock already alerted about the same day.
"""

import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from .db import iso, now_iso, utcnow
from .notify import notify, send_email
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
    when = f"{state.overdue_by} overdue" if state.overdue else f"due {state.due_in}"
    return f"- {state.industry['brand']}: {state.rule.title}, {when} ({state.due_label}). {state.rule.action}"


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


def _recipients(conn, org_id):
    """Everyone in the company who has reminder emails on."""
    return conn.execute(
        "SELECT users.* FROM users JOIN memberships ON memberships.user_id = users.id"
        " WHERE memberships.org_id = ? AND users.email_reminders = 1",
        (org_id,),
    ).fetchall()


def _already_reminded(conn, org_id, state, window):
    return conn.execute(
        "SELECT 1 FROM reminder_marks WHERE org_id = ? AND industry_id = ? AND rule_key = ? AND due_date = ? AND threshold = ?",
        (org_id, state.industry_id, state.rule.key, state.due_date.isoformat(), window),
    ).fetchone() is not None


def _mark_windows(conn, org_id, pending):
    conn.executemany(
        "INSERT OR IGNORE INTO reminder_marks (org_id, industry_id, rule_key, due_date, threshold, sent_at)"
        " VALUES (?, ?, ?, ?, ?, ?)",
        [(org_id, s.industry_id, s.rule.key, s.due_date.isoformat(), w, now_iso()) for s, w in pending],
    )
    conn.commit()


def _remind_org(conn, cfg, org, today):
    states = states_for_org(conn, org, today=today)
    pending = []
    for s in states:
        window = reminder_window(s.days_left)
        if window is not None and not _already_reminded(conn, org["id"], s, window):
            pending.append((s, window))
    # A clock alerted about earlier today would only be the same news again:
    # its window counts as reminded and it stays out of today's digest.
    covered = [(s, w) for s, w in pending if _alerted_today(conn, org, s, w, today)]
    if covered:
        _mark_windows(conn, org["id"], covered)
        pending = [p for p in pending if p not in covered]
    if not pending:
        return 0, 0
    recipients = _recipients(conn, org["id"])
    delivered = 0
    if recipients:
        subject, body = build_digest(org, [s for s, _ in pending], states, cfg["BASE_URL"], today)
        for user in recipients:
            status = notify(conn, cfg, "reminder", user["email"], subject, body, org_id=org["id"], user_id=user["id"])
            delivered += status in ("sent", "logged")
    if delivered or not recipients:
        _mark_windows(conn, org["id"], pending)
        return len(pending), delivered
    return 0, 0


# --- Time-limit alerts: the hour and minute clocks ---------------------------

CLOCK_WARNING = "clock-warning"
CLOCK_OVERDUE = "clock-overdue"
# A stage reached longer ago than this is not news any more (a clock entered
# days after it ran out, or a server that was down): the digest covers it.
CLOCK_ALERT_WITHIN = timedelta(hours=24)


def clock_stage(state, now):
    """(stage, the moment the clock got there) for an hour or minute clock at
    `now`: CLOCK_OVERDUE from the minute after its due time, CLOCK_WARNING while
    it is a Warning (from its warning point up to and including the due minute).
    None for any other check, a clock before its warning point, or a stage
    reached over CLOCK_ALERT_WITHIN ago."""
    if state.due_at is None or state.minutes_left is None:
        return None
    if state.minutes_left < 0:
        stage, reached = CLOCK_OVERDUE, state.due_at + timedelta(minutes=1)
    elif state.level == "WARNING":
        stage, reached = CLOCK_WARNING, min(state.warn_at or state.due_at, state.due_at)
    else:
        return None
    if now - reached > CLOCK_ALERT_WITHIN:
        return None
    return stage, reached


def _clock_key(state):
    """What a clock's alerts are kept under: its due moment in UTC, so a clock
    started again (Done now, or a new time entered) is alerted about again."""
    return iso(state.due_at)


def _alerted_today(conn, org, state, window, today):
    """Whether a time-limit alert about the same news went out on `today`
    (the company's date): the overdue alert for an overdue window, either
    alert for a coming-due one."""
    if state.due_at is None:
        return False
    stages = (CLOCK_OVERDUE,) if window.startswith("overdue") else (CLOCK_WARNING, CLOCK_OVERDUE)
    tz = ZoneInfo(org["timezone"])
    rows = conn.execute(
        f"SELECT sent_at FROM reminder_marks WHERE org_id = ? AND industry_id = ? AND rule_key = ? AND due_date = ?"
        f" AND threshold IN ({', '.join('?' * len(stages))})",
        (org["id"], state.industry_id, state.rule.key, _clock_key(state), *stages),
    ).fetchall()
    return any(datetime.fromisoformat(r["sent_at"]).astimezone(tz).date() == today for r in rows)


def build_clock_alert(org, state, stage, base_url, now):
    """One short email about one clock: it reached its warning point, or it is overdue."""
    overdue = stage == CLOCK_OVERDUE
    if overdue:
        subject = f"OmniArmor: {state.rule.title}, overdue, was due {state.due_label} ({org['name']})"
    else:
        subject = f"OmniArmor: {state.rule.title}, due {state.due_label} ({org['name']})"
    local = now.astimezone(ZoneInfo(org["timezone"]))
    lines = [
        f"Time limit {'overdue' if overdue else 'warning'} for {org['name']}, {local.strftime('%Y-%m-%d %H:%M %Z').strip()}.",
        "",
        _line(state),
        "",
        f"Open it: {base_url}/app/industry/{state.industry_id}#rule-{state.rule.key}",
        "",
        "You get this email because reminders are on in your OmniArmor settings.",
    ]
    return subject, "\n".join(lines)


def _send_alert(conn, cfg, org, user, subject, body, since):
    """Sends one alert to one person. A copy that failed on an earlier run is
    sent again in place, so a long email outage leaves one row per person on
    Radar, not one per run for Autopilot to re-send later; a copy Autopilot
    already got through counts as delivered."""
    row = conn.execute(
        "SELECT id, status FROM notifications WHERE org_id = ? AND user_id = ? AND kind = 'reminder' AND subject = ?"
        " AND created_at >= ? ORDER BY id DESC LIMIT 1",
        (org["id"], user["id"], subject, iso(since)),
    ).fetchone()
    if row is None:
        return notify(conn, cfg, "reminder", user["email"], subject, body, org_id=org["id"], user_id=user["id"])
    if row["status"] != "failed":
        return row["status"]
    status, error = send_email(cfg, user["email"], subject, body)
    conn.execute("UPDATE notifications SET status = ?, error = ?, body = ?, attempts = attempts + 1 WHERE id = ?",
                 (status, error, body, row["id"]))
    conn.commit()
    return status


def _alert_org(conn, cfg, org, now):
    local_now = now.astimezone(ZoneInfo(org["timezone"]))
    recipients = None
    alerts = emails = 0
    for s in states_for_org(conn, org, now=local_now):
        found = clock_stage(s, now)
        if found is None:
            continue
        stage, reached = found
        mark = (org["id"], s.industry_id, s.rule.key, _clock_key(s), stage)
        # The mark is written first: it claims the alert, so two server
        # processes checking at once never both send it.
        claimed = conn.execute(
            "INSERT OR IGNORE INTO reminder_marks (org_id, industry_id, rule_key, due_date, threshold, sent_at)"
            " VALUES (?, ?, ?, ?, ?, ?)", (*mark, iso(now))).rowcount == 1
        conn.commit()
        if not claimed:
            continue
        delivered = 0
        try:
            if recipients is None:
                recipients = _recipients(conn, org["id"])
            subject, body = build_clock_alert(org, s, stage, cfg["BASE_URL"], now)
            for user in recipients:
                delivered += _send_alert(conn, cfg, org, user, subject, body, reached) in ("sent", "logged")
        finally:
            if recipients is None or (recipients and not delivered):
                # Nothing went out: let the next run try again.
                conn.rollback()
                conn.execute("DELETE FROM reminder_marks WHERE org_id = ? AND industry_id = ? AND rule_key = ?"
                             " AND due_date = ? AND threshold = ?", mark)
                conn.commit()
        if delivered or not recipients:
            alerts += 1
            emails += delivered
    return alerts, emails


def run_clock_alerts(conn, cfg, now=None):
    """Sends the time-limit alerts due now (an aware datetime; the current
    moment by default). Only companies with an hour or minute clock running are
    looked at. One company's failure is logged and never stops the others."""
    now = now or utcnow()
    summary = {"orgs": 0, "alerts": 0, "emails": 0, "errors": 0}
    # Only the hour and minute clocks store a time ("...T14:30:00+00:00").
    orgs = conn.execute("SELECT * FROM orgs WHERE id IN (SELECT org_id FROM items WHERE value_date LIKE '%T%')"
                        " ORDER BY id").fetchall()
    for org in orgs:
        summary["orgs"] += 1
        try:
            alerts, emails = _alert_org(conn, cfg, org, now)
            summary["alerts"] += alerts
            summary["emails"] += emails
        except Exception:
            conn.rollback()
            summary["errors"] += 1
            log.exception("time-limit alerts failed for org %s", org["id"])
    return summary


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
