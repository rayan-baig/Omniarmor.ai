# -*- coding: utf-8 -*-
"""Short offers to move up a plan, shown rarely and only when they fit.

Two kinds, both for a workspace's owner (the one person who can act on them):

- **academy**: a workspace on Pro (paid, or included with the Kitchen Safety
  Bundle) opens the Academy or taps a world outside the free ones. The offer
  is a peek at that world's first lesson and one line: Plus includes the
  Academy, at the price from plans.py.
- **second_location**: the owner has just added a second location (a second
  workspace they own, made in the last LOCATION_WINDOW). The offer is what
  paying yearly saves for their locations, when a yearly price is set up.

Rules, the same for both:

- At most one offer a week per person, of any kind (EVERY): the last time
  any offer was shown is remembered in the nudges table, per person and kind.
- An offer the person dismissed never comes back.
- Offers never go to team members, to a kid's device, or to a workspace whose
  plan is paused, past due or read-only.

Each offer shown and each upgrade started from one is counted in usage.py
(daily totals, nothing about who).
"""

from datetime import timedelta

from . import academy, academy_plan, plans, usage
from .db import iso, now_iso, utcnow

EVERY = timedelta(days=7)
LOCATION_WINDOW = timedelta(days=14)
KINDS = ("academy", "second_location")


def _recent(conn, user_id):
    """Whether this person was shown any offer in the last EVERY."""
    since = iso(utcnow() - EVERY)
    return conn.execute("SELECT 1 FROM nudges WHERE user_id = ? AND shown_at >= ?", (user_id, since)).fetchone() is not None


def _dismissed(conn, user_id, kind):
    row = conn.execute("SELECT dismissed_at FROM nudges WHERE user_id = ? AND kind = ?", (user_id, kind)).fetchone()
    return row is not None and row["dismissed_at"] is not None


def allowed(conn, user, kind):
    """Whether an offer of this kind may be shown to this person now."""
    if kind not in KINDS or user is None:
        return False
    return not _dismissed(conn, user["id"], kind) and not _recent(conn, user["id"])


def mark_shown(conn, user_id, kind):
    conn.execute("INSERT INTO nudges (user_id, kind, shown_at) VALUES (?, ?, ?)"
                 " ON CONFLICT (user_id, kind) DO UPDATE SET shown_at = excluded.shown_at",
                 (user_id, kind, now_iso()))
    conn.commit()
    usage.count(conn, "nudges_shown")


def dismiss(conn, user_id, kind):
    if kind not in KINDS:
        return False
    conn.execute("INSERT INTO nudges (user_id, kind, dismissed_at) VALUES (?, ?, ?)"
                 " ON CONFLICT (user_id, kind) DO UPDATE SET dismissed_at = excluded.dismissed_at",
                 (user_id, kind, now_iso()))
    conn.commit()
    return True


def on_pro(access):
    """Whether the workspace has the compliance tracker from Pro and not the
    Academy: Pro paid for, or Pro included with the Kitchen Safety Bundle."""
    if not access["tracker"] or access["academy"] or access["paused"]:
        return False
    if access["source"] == "plan":
        return access["kind"] == "pro" and access["state"] != "past_due"
    return access["source"] in ("bundle", "bundle_grace")


def academy_offer(cfg, org, access, industry_ids, world=None, t=None):
    """What the Academy offer shows: a peek at a world's first lesson (the
    world tapped, or the first one past the free worlds) and Plus's price for
    this workspace (the bundle's difference where that applies)."""
    t = t or academy.TRACKS[academy_plan.FREE_TRACK]
    if world is None or academy_plan.allows(org, t, world):
        number = next(n for n in t.topics if not academy_plan.allows(org, t, academy.world(n)))
        world = academy.world(number)
    cards = academy.story(t, world.number, 1, org["name"], list(industry_ids))[:2]
    kind, _, dollars = plans.checkout_choice(cfg, org, plans.PLUS.key, plans.MONTH)
    yearly_kind, yearly_price, yearly_dollars = plans.checkout_choice(cfg, org, plans.PLUS.key, plans.YEAR)
    return {"world": world, "track": t, "cards": cards,
            "price": plans.price_label(dollars), "bundle": kind == "plus_bundle",
            "yearly_price": plans.price_label(yearly_dollars, plans.YEAR) if yearly_price else None,
            "paid": access["paid"], "interval": access["interval"]}


def owned_workspaces(conn, user_id):
    return conn.execute("SELECT orgs.* FROM memberships JOIN orgs ON orgs.id = memberships.org_id"
                        " WHERE memberships.user_id = ? AND memberships.role = 'owner'"
                        " ORDER BY orgs.created_at, orgs.id", (user_id,)).fetchall()


def location_offer(conn, cfg, user):
    """The yearly saving for a person who just added their second location:
    None unless they own two or more workspaces, the newest made in the last
    LOCATION_WINDOW, and a yearly price is set up."""
    owned = owned_workspaces(conn, user["id"])
    if len(owned) < 2:
        return None
    newest = plans._parse(owned[-1]["created_at"])
    if newest is None or utcnow() - newest > LOCATION_WINDOW:
        return None
    offered = plans.yearly_offered(cfg)
    rows = []
    for p in (plans.PRO, plans.PLUS):
        if offered[p.key]:
            each = plans.yearly_saving(p.dollars)
            rows.append({"plan": p, "each": plans.price_label(each, plans.YEAR, per=False),
                         "all": plans.price_label(each * len(owned), plans.YEAR, per=False),
                         "yearly": p.yearly_price})
    if not rows:
        return None
    return {"locations": len(owned), "rows": rows, "free_label": plans.free_label()}
