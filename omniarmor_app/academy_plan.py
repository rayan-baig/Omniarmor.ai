# -*- coding: utf-8 -*-
"""The workspace's subscription through Stripe: Pro, Plus, Plus for a Kitchen
Safety Bundle workspace, and the old Academy plan it grew from (the module
keeps its first name). What each plan gives, and the prices, are in plans.py.

Payments go through Stripe Checkout, with the workspace's location count as
the quantity, and Stripe tells the app about changes through a signed
webhook: which plan (from the subscription's price), its status, renewal and
end. Changing plan or the card happens in Stripe's customer portal. With no
Stripe keys set, a plan can still be turned on by hand:
    flask --app wsgi plan <workspace id> plus
After the trial, the first three worlds of the Launchpad track stay free for
everyone; the rest of the Academy needs Plus.
"""

import hashlib
import hmac
import json
import re
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
    """What the Academy pages say about the workspace's Academy: 'paid' (a
    plan that includes the whole Academy: Plus, or the old Academy plan),
    'trial' or 'free' (its free worlds only), with details."""
    from . import plans
    info = plans.access(org, now)
    state = info["state"]
    if info["paid"] and plans.KINDS.get(info["kind"], (None, False, False))[2]:
        # A plan cancelled in Stripe's portal stays on until the paid period ends.
        return {"access": "paid", "state": state, "renews_at": info["renews_at"], "ends_at": info["ends_at"],
                "trial_days": 0, "plan_name": info["plan_name"]}
    if info["trial"]:
        return {"access": "trial", "state": "trial", "renews_at": None, "ends_at": None,
                "trial_days": info["trial_days"], "plan_name": None}
    return {"access": "free", "state": state, "renews_at": None, "ends_at": None, "trial_days": 0,
            "plan_name": None}


def charges_again(org):
    """Whether Stripe will go on charging for this workspace's plan: it is paid
    through a subscription that hasn't been cancelled."""
    return bool(org["stripe_subscription_id"] and (org["academy_status"] or "none") in PAID_STATES
                and not org["academy_ends_at"])


def full_access(org):
    from . import plans
    return plans.access(org)["academy"]


def allows(org, track, world):
    """Whether this workspace's plan includes a world on a track."""
    return full_access(org) or (track.key == FREE_TRACK and world.number in FREE_WORLDS)


def trial_end_for_new_workspace(days):
    """The free trial's end for a workspace signing up now."""
    return iso(utcnow() + timedelta(days=days))


def set_status(conn, org_id, state, renews_at=None, kind=None):
    """Sets the plan by hand (the `plan` command): its status and, with kind, which plan."""
    conn.execute("UPDATE orgs SET academy_status = ?, academy_renews_at = ?, academy_ends_at = NULL,"
                 " plan = COALESCE(?, plan) WHERE id = ?", (state, renews_at, kind, org_id))


def subscribed(org):
    """Whether the workspace has a subscription that counts (paid, or past
    due while Stripe retries): checkout never starts a second one."""
    return (org["academy_status"] or "none") in PAID_STATES


# --- Stripe ---------------------------------------------------------------------

# The settings holding each plan's Stripe price id, and the plan (orgs.plan) it is.
PRICE_SETTINGS = {"PRO_STRIPE_PRICE": "pro", "PLUS_STRIPE_PRICE": "plus",
                  "PLUS_BUNDLE_UPGRADE_STRIPE_PRICE": "plus_bundle"}
KINDS = ("pro", "plus", "plus_bundle", "academy")


def stripe_ready(cfg, price=None):
    """Whether Stripe can take a payment: the secret key, and the price (or
    any plan's price, when none is named)."""
    if not cfg.get("STRIPE_SECRET_KEY"):
        return False
    return bool(price) if price is not None else any(cfg.get(name) for name in PRICE_SETTINGS)


def kind_for(cfg, obj):
    """The plan a Stripe subscription or checkout session is for: from its
    price when that is one of ours, else from the plan the checkout wrote in
    its metadata. None when it says neither (an old Academy plan's renewal,
    say): the workspace's plan then stays as it is."""
    prices = {cfg.get(name): kind for name, kind in PRICE_SETTINGS.items() if cfg and cfg.get(name)}
    for item in ((obj.get("items") or {}).get("data") or []):
        if not isinstance(item, dict):
            continue
        price = item.get("price")
        price = price.get("id") if isinstance(price, dict) else price
        if price in prices:
            return prices[price]
    meta = (obj.get("metadata") or {}).get("plan")
    return meta if meta in KINDS else None


def _stripe(cfg, path, fields, method="POST"):
    data = urllib.parse.urlencode(fields).encode() if method == "POST" else None
    request = urllib.request.Request(f"{STRIPE_API}/{path}", data=data, method=method)
    request.add_header("Authorization", "Bearer " + cfg["STRIPE_SECRET_KEY"])
    if data is not None:
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


def checkout_url(cfg, org, email, success_url, cancel_url, price, kind, quantity):
    """A Stripe Checkout page for one plan: its price, `quantity` locations
    (plans.location_count), and the plan written in the metadata of the
    session and of the subscription it makes."""
    fields = {
        "mode": "subscription",
        "line_items[0][price]": price,
        "line_items[0][quantity]": str(int(quantity)),
        "success_url": success_url,
        "cancel_url": cancel_url,
        "client_reference_id": str(org["id"]),
        "metadata[org_id]": str(org["id"]),
        "metadata[plan]": kind,
        "subscription_data[metadata][org_id]": str(org["id"]),
        "subscription_data[metadata][plan]": kind,
        "allow_promotion_codes": "true",
    }
    if org["stripe_customer_id"]:
        fields["customer"] = org["stripe_customer_id"]
    else:
        fields["customer_email"] = email
    return _stripe(cfg, "checkout/sessions", fields)["url"]


# Stripe's checkout session ids, and nothing that could reach another API path.
_SESSION_ID = re.compile(r"cs_[A-Za-z0-9_]{1,250}")


def confirm_checkout(conn, cfg, org, session_id):
    """Turns the plan on as soon as the family comes back from paying.

    Stripe sends them back the moment the payment goes through; its webhook
    can come seconds later, or not at all when it isn't set up right. Until
    then the plan page offered checkout again, inviting a second payment.
    Asking Stripe about the session they came back with settles it at once.
    Returns True when the plan is now on."""
    if not stripe_ready(cfg) or not _SESSION_ID.fullmatch(session_id or ""):
        return False
    obj = _stripe(cfg, f"checkout/sessions/{session_id}", {}, method="GET")
    if (obj.get("mode") != "subscription" or obj.get("status") != "complete"
            or obj.get("payment_status") not in ("paid", "no_payment_required")):
        return False
    if str(obj.get("client_reference_id")) != str(org["id"]):
        return False
    owner = _org_for(conn, obj, "checkout.session.completed")
    if owner is None or owner["id"] != org["id"]:
        return False
    created = obj.get("created") if isinstance(obj.get("created"), int) else None
    return _apply_checkout(conn, owner, obj, None, started=created, kind=kind_for(cfg, obj)) is not None


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


def _older_than(obj, org):
    """Whether a Stripe object was created before this workspace was.

    Stripe always says when a subscription was created. One older than the
    workspace (allowing a minute for clocks) cannot be this workspace's.
    """
    created = obj.get("created")
    if not isinstance(created, int) or not org["created_at"]:
        return False
    try:
        from datetime import datetime, timezone
        made = datetime.fromisoformat(str(org["created_at"]).replace("Z", "+00:00"))
        if made.tzinfo is None:
            made = made.replace(tzinfo=timezone.utc)
        return created < made.timestamp() - 60
    except ValueError:
        return False


def _org_for(conn, obj, kind=""):
    """The workspace a Stripe object is about, or None.

    The workspace id in the metadata is believed only when it agrees with the
    Stripe customer. Workspace ids are reused after a deletion, so a deleted
    workspace's subscription, renewing later, named a stranger's new
    workspace: that workspace became paid, and its owner could open the
    billing portal on the original customer's card and invoices. Now a
    workspace that has a customer must match it, and one without a customer
    is not matched by a subscription created before the workspace existed.
    """
    meta = obj.get("metadata") or {}
    org_id = meta.get("org_id") or obj.get("client_reference_id")
    customer = obj.get("customer")
    if org_id and str(org_id).isdigit():
        row = conn.execute("SELECT * FROM orgs WHERE id = ?", (int(org_id),)).fetchone()
        if row is not None:
            if row["stripe_customer_id"]:
                if not customer or customer == row["stripe_customer_id"]:
                    return row
            elif kind == "checkout.session.completed" or not _older_than(obj, row):
                return row
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


def apply_event(conn, event, cfg=None):
    """Updates a workspace's plan from a Stripe event. Returns a short
    description of what changed, or None if the event wasn't relevant.

    Stripe may deliver events more than once and in any order, so repeats are
    ignored, a subscription event older than the last one applied is ignored,
    and while a workspace is paid, events about some other subscription (a
    duplicate checkout, say) don't change its plan. Which plan it is comes
    from the subscription's price (cfg names each plan's price) or the plan
    the checkout wrote in its metadata; a plan switched in Stripe's portal
    arrives this way."""
    kind = event.get("type", "")
    obj = (event.get("data") or {}).get("object") or {}
    org = _org_for(conn, obj, kind)
    if org is None:
        return None
    if _seen(conn, event, org["id"]):
        return None
    created = event.get("created") if isinstance(event.get("created"), int) else None
    paid = (org["academy_status"] or "none") in PAID_STATES
    current_sub = org["stripe_subscription_id"]
    plan_kind = kind_for(cfg or {}, obj)
    if kind == "checkout.session.completed":
        return _apply_checkout(conn, org, obj, created, kind=plan_kind)
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
        period_end = _period_end(obj)
        renews = iso(_from_timestamp(period_end)) if period_end and state in PAID_STATES else None
        # Cancelled in the portal: still paid for until the period ends, then Stripe deletes it.
        cancel_at = obj.get("cancel_at") if isinstance(obj.get("cancel_at"), int) else (
            period_end if obj.get("cancel_at_period_end") else None)
        ends_at = iso(_from_timestamp(cancel_at)) if cancel_at and state in PAID_STATES else None
        conn.execute("UPDATE orgs SET academy_status = ?, academy_renews_at = ?, academy_ends_at = ?,"
                     " stripe_subscription_id = ?, stripe_customer_id = COALESCE(stripe_customer_id, ?),"
                     " plan = COALESCE(?, plan) WHERE id = ?",
                     (state, renews, ends_at, obj.get("id"), obj.get("customer"), plan_kind, org["id"]))
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


# Where a subscription can end up after its first payment. A checkout is
# that first payment, so it never moves a subscription back from one of these.
LATER_STATES = {"past_due", "unpaid", "canceled", "incomplete_expired"}


def _apply_checkout(conn, org, obj, created, started=None, kind=None):
    """A completed checkout turns the plan on, unless the workspace is already
    paid through another subscription (a duplicate checkout).

    Nor does it turn a plan back on that has since ended, or hide a failed
    payment: Stripe retries an undelivered checkout event for days, and the
    page Stripe sends a family back to can be opened again from history long
    after they cancel. `created` is when the event happened; `started` is when
    the checkout began, for the return page, which has no event."""
    subscription = obj.get("subscription")
    current_sub = org["stripe_subscription_id"]
    state = org["academy_status"] or "none"
    when = created if created is not None else started
    last = org["stripe_event_at"]
    if state in LATER_STATES and (subscription == current_sub
                                  or (when is not None and last is not None and when < last)):
        return None
    if state in PAID_STATES and current_sub and subscription != current_sub:
        # A second checkout while already paid: keep following the first subscription.
        conn.execute("UPDATE orgs SET stripe_customer_id = COALESCE(stripe_customer_id, ?) WHERE id = ?",
                     (obj.get("customer"), org["id"]))
        return None
    conn.execute("UPDATE orgs SET stripe_customer_id = ?, stripe_subscription_id = ?, academy_status = 'active',"
                 " academy_ends_at = CASE WHEN stripe_subscription_id IS ? THEN academy_ends_at END,"
                 " plan = COALESCE(?, plan) WHERE id = ?",
                 (obj.get("customer"), subscription, subscription, kind, org["id"]))
    _mark_applied(conn, org["id"], created)
    return "active"


def _period_end(subscription):
    """When the subscription's current period ends, as a Unix time, or None.
    Newer Stripe API versions keep it on the subscription's items."""
    value = subscription.get("current_period_end")
    if not isinstance(value, int):
        items = (subscription.get("items") or {}).get("data") or []
        value = next((i.get("current_period_end") for i in items
                      if isinstance(i, dict) and isinstance(i.get("current_period_end"), int)), None)
    return value


def _from_timestamp(seconds):
    return datetime.fromtimestamp(seconds, tz=timezone.utc)
