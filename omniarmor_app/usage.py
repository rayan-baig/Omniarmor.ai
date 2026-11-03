# -*- coding: utf-8 -*-
"""How often a few key features are used, counted the privacy-friendly way.

One number per feature per day, and nothing else: no cookie, no user,
workspace or learner id, no IP address, and no outside analytics service.
Counting a use adds one to that day's total (UTC) in usage_counts; there is
no row per use to trace back to anyone.

Only the operator sees the totals: the last 30 days are on the Settings page
of the operator's account (auth.is_operator), and in /api/stats, which only
answers MTRX Horizyn's console with STATS_KEY. Totals older than KEEP_DAYS
are deleted by the daily job.
"""

import logging
from datetime import timedelta

from .db import utcnow

log = logging.getLogger("omniarmor.usage")

# What is counted, as (key, what the operator sees), in the order shown.
EVENTS = (
    ("checks_updated", "Checks updated"),
    ("bulk_updates", "Bulk updates"),
    ("lessons_started", "Lessons started"),
    ("lessons_passed", "Lessons passed"),
    ("certificates", "Certificates earned"),
    ("help_views", "Help page views"),
    ("signups", "Sign-ups"),
)
EVENT_NAMES = dict(EVENTS)
SHOW_DAYS = 30
KEEP_DAYS = 400


def count(conn, event, n=1):
    """Adds n to today's total for one feature. Never fails the page that
    called it: a counting problem is logged and the page goes on."""
    if event not in EVENT_NAMES:
        raise ValueError(f"unknown usage event {event!r}")
    if n <= 0:
        return
    try:
        conn.execute("INSERT INTO usage_counts (day, event, count) VALUES (?, ?, ?)"
                     " ON CONFLICT (day, event) DO UPDATE SET count = count + excluded.count",
                     (utcnow().date().isoformat(), event, n))
        conn.commit()
    except Exception:
        log.exception("couldn't count a use of %s", event)


def last_days(conn, days=SHOW_DAYS):
    """The last `days` days, newest first, every day and feature present
    (0 when nothing happened): {"days": [{"day": ..., <event>: n, ...}],
    "totals": {<event>: n}}."""
    today = utcnow().date()
    first = today - timedelta(days=days - 1)
    rows = conn.execute("SELECT day, event, count FROM usage_counts WHERE day >= ?", (first.isoformat(),))
    found = {(r["day"], r["event"]): r["count"] for r in rows}
    table = []
    for back in range(days):
        day = (today - timedelta(days=back)).isoformat()
        table.append({"day": day, **{key: found.get((day, key), 0) for key, _ in EVENTS}})
    totals = {key: sum(row[key] for row in table) for key, _ in EVENTS}
    return {"days": table, "totals": totals}


def trim(conn):
    """Deletes totals older than KEEP_DAYS (the daily job's cleanup)."""
    conn.execute("DELETE FROM usage_counts WHERE day < ?", ((utcnow() - timedelta(days=KEEP_DAYS)).date().isoformat(),))

