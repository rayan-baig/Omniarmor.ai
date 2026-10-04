# -*- coding: utf-8 -*-
"""The Academy's own subscription, separate from the compliance service.

Every workspace gets a free trial of the whole Academy when it adds its first
learner. After the trial, the first three worlds of the Launchpad track stay
free; everything else needs the Academy plan. Payments go through Stripe
Checkout, and Stripe tells the app about changes through a signed webhook. With
no Stripe keys set, the plan can still be turned on by hand:
    flask --app wsgi academy-plan <workspace id> active
"""

import hashlib
import hmac
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

from .db import iso, utcnow

FREE_TRACK = "launchpad"
FREE_WORLDS = {1, 2, 3}
PAID_STATES = {"active", "trialing", "past_due"}  # past_due keeps access while Stripe retries the card
STRIPE_API = "https://api.stripe.com/v1"
WEBHOOK_TOLERANCE = 300  # seconds


class StripeError(Exception):
    pass


def plan_status(org, now=None):
    """What the workspace can use right now: 'paid', 'trial' or 'free', with details."""
    now = now or utcnow()
    state = org["academy_status"] or "none"
    if state in PAID_STATES:
        return {"access": "paid", "state": state, "renews_at": org["academy_renews_at"], "trial_days": 0}
    ends = org["academy_trial_ends"]
    if ends and ends > iso(now):
        days = max(1, -(-(_parse(ends) - now).total_seconds() // 86400))
        return {"access": "trial", "state": "trial", "renews_at": None, "trial_days": int(days)}
    return {"access": "free", "state": state, "renews_at": None, "trial_days": 0}


def _parse(text):
    return datetime.fromisoformat(text)


def full_access(org):
    return plan_status(org)["access"] in ("paid", "trial")


def allows(org, track, world):
    """Whether this workspace's plan includes a world on a track."""
    return full_access(org) or (track.key == FREE_TRACK and world.number in FREE_WORLDS)


def start_trial(conn, org_id, days):
    """Starts the free trial the first time a workspace uses the Academy."""
    conn.execute("UPDATE orgs SET academy_trial_ends = ? WHERE id = ? AND academy_trial_ends IS NULL"
                 " AND academy_status = 'none'", (iso(utcnow() + timedelta(days=days)), org_id))


def set_status(conn, org_id, state, renews_at=None):
    conn.execute("UPDATE orgs SET academy_status = ?, academy_renews_at = ? WHERE id = ?",
                 (state, renews_at, org_id))


# --- Stripe ---------------------------------------------------------------------

def stripe_ready(cfg):
    return bool(cfg.get("STRIPE_SECRET_KEY") and cfg.get("ACADEMY_STRIPE_PRICE"))


def _stripe(cfg, path, fields):
    data = urllib.parse.urlencode(fields).encode()
    request = urllib.request.Request(f"{STRIPE_API}/{path}", data=data, method="POST")
    request.add_header("Authorization", "Bearer " + cfg["STRIPE_SECRET_KEY"])
    request.add_header("Content-Type", "application/x-www-form-urlencoded")
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return json.loads(response.read().decode())
    except urllib.error.HTTPError as exc:
        try:
            message = json.loads(exc.read().decode())["error"]["message"]
        except Exception:
            message = f"HTTP {exc.code}"
        raise StripeError(message) from exc
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        raise StripeError(str(exc)) from exc


def checkout_url(cfg, org, email, success_url, cancel_url):
    fields = {
        "mode": "subscription",
        "line_items[0][price]": cfg["ACADEMY_STRIPE_PRICE"],
        "line_items[0][quantity]": "1",
        "success_url": success_url,
        "cancel_url": cancel_url,
        "client_reference_id": str(org["id"]),
        "metadata[org_id]": str(org["id"]),
        "subscription_data[metadata][org_id]": str(org["id"]),
        "allow_promotion_codes": "true",
    }
    if org["stripe_customer_id"]:
        fields["customer"] = org["stripe_customer_id"]
    else:
        fields["customer_email"] = email
    return _stripe(cfg, "checkout/sessions", fields)["url"]


def portal_url(cfg, org, return_url):
    return _stripe(cfg, "billing_portal/sessions",
                   {"customer": org["stripe_customer_id"], "return_url": return_url})["url"]


def verify_webhook(payload, header, secret, now=None):
    """Checks Stripe's signature: an HMAC of "timestamp.payload" with the
    webhook secret, sent recently enough that it can't be an old replay."""
    if not secret or not header:
        return False
    parts = {}
    for item in header.split(","):
        key, _, value = item.partition("=")
        parts.setdefault(key.strip(), []).append(value.strip())
    try:
        stamp = int(parts.get("t", [""])[0])
    except ValueError:
        return False
    if abs((now or time.time()) - stamp) > WEBHOOK_TOLERANCE:
        return False
    expected = hmac.new(secret.encode(), f"{stamp}.".encode() + payload, hashlib.sha256).hexdigest()
    return any(hmac.compare_digest(expected, sig) for sig in parts.get("v1", []))


def _org_for(conn, obj):
    meta = obj.get("metadata") or {}
    org_id = meta.get("org_id") or obj.get("client_reference_id")
    if org_id and str(org_id).isdigit():
        row = conn.execute("SELECT * FROM orgs WHERE id = ?", (int(org_id),)).fetchone()
        if row is not None:
            return row
    customer = obj.get("customer")
    if customer:
        return conn.execute("SELECT * FROM orgs WHERE stripe_customer_id = ?", (customer,)).fetchone()
    return None


SUBSCRIPTION_EVENTS = ("customer.subscription.created", "customer.subscription.updated",
                       "customer.subscription.deleted")


def _seen(conn, event, org_id):
    """Records a Stripe event id; True if it was already processed (Stripe
    retries deliveries, and a signed event can be sent again)."""
    event_id = event.get("id")
    if not isinstance(event_id, str) or not event_id:
        return False
    if conn.execute("SELECT 1 FROM stripe_events WHERE id = ?", (event_id,)).fetchone() is not None:
        return True
    created = event.get("created") if isinstance(event.get("created"), int) else None
    conn.execute("INSERT INTO stripe_events (id, org_id, type, created, received_at) VALUES (?, ?, ?, ?, ?)",
                 (event_id, org_id, str(event.get("type", ""))[:100], created, iso(utcnow())))
    return False


def _mark_applied(conn, org_id, created):
    if created is not None:
        conn.execute("UPDATE orgs SET stripe_event_at = MAX(COALESCE(stripe_event_at, 0), ?) WHERE id = ?",
                     (created, org_id))


def apply_event(conn, event):
    """Updates a workspace's Academy plan from a Stripe event. Returns a short
    description of what changed, or None if the event wasn't relevant.

    Stripe may deliver events more than once and in any order, so repeats are
    ignored, a subscription event older than the last one applied is ignored,
    and while a workspace is paid, events about some other subscription (a
    duplicate checkout, say) don't change its plan."""
    kind = event.get("type", "")
    obj = (event.get("data") or {}).get("object") or {}
    org = _org_for(conn, obj)
    if org is None:
        return None
    if _seen(conn, event, org["id"]):
        return None
    created = event.get("created") if isinstance(event.get("created"), int) else None
    paid = (org["academy_status"] or "none") in PAID_STATES
    current_sub = org["stripe_subscription_id"]
    if kind == "checkout.session.completed":
        subscription = obj.get("subscription")
        if paid and current_sub and subscription != current_sub:
            # A second checkout while already paid: keep following the first subscription.
            conn.execute("UPDATE orgs SET stripe_customer_id = COALESCE(stripe_customer_id, ?) WHERE id = ?",
                         (obj.get("customer"), org["id"]))
            return None
        conn.execute("UPDATE orgs SET stripe_customer_id = ?, stripe_subscription_id = ?, academy_status = 'active'"
                     " WHERE id = ?", (obj.get("customer"), subscription, org["id"]))
        _mark_applied(conn, org["id"], created)
        return "active"
    if kind in SUBSCRIPTION_EVENTS:
        if paid and current_sub and obj.get("id") != current_sub:
            return None
        last = org["stripe_event_at"]
        if created is not None and last is not None and created < last:
            return None
        state = "canceled" if kind.endswith("deleted") else obj.get("status", "none")
        if state not in PAID_STATES | {"canceled", "unpaid", "incomplete", "incomplete_expired"}:
            state = "none"
        if state == "incomplete" and paid:
            # A subscription never goes back to incomplete once paid; this is a late copy of its first event.
            return None
        ends = obj.get("current_period_end")
        renews = iso(_from_timestamp(ends)) if isinstance(ends, int) and state in PAID_STATES else None
        conn.execute("UPDATE orgs SET academy_status = ?, academy_renews_at = ?, stripe_subscription_id = ?,"
                     " stripe_customer_id = COALESCE(stripe_customer_id, ?) WHERE id = ?",
                     (state, renews, obj.get("id"), obj.get("customer"), org["id"]))
        _mark_applied(conn, org["id"], created)
        return state
    if kind == "invoice.payment_failed":
        subscription = obj.get("subscription")
        if current_sub and subscription and subscription != current_sub:
            return None
        conn.execute("UPDATE orgs SET academy_status = 'past_due' WHERE id = ? AND academy_status = 'active'",
                     (org["id"],))
        return "past_due"
    return None


def _from_timestamp(seconds):
    return datetime.fromtimestamp(seconds, tz=timezone.utc)
