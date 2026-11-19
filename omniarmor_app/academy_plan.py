# -*- coding: utf-8 -*-
"""The workspace's subscription through Stripe: Pro, Plus, Plus for a Kitchen
Safety Bundle workspace, and the old Academy plan it grew from (the module
keeps its first name). What each plan gives, and the prices, are in plans.py.

Payments go through Stripe Checkout, with the workspace's location count as
the quantity, and Stripe tells the app about changes through a signed
webhook: which plan and whether it is paid monthly or yearly (both from the
subscription's price), its status, renewal and end. Changing plan, switching
between monthly and yearly, the card and cancelling all happen in Stripe's
customer portal. With no Stripe keys set, a plan can still be turned on by hand:
    flask --app wsgi plan <workspace id> plus [--yearly]
After the trial, the first three worlds of the Launchpad track stay free for
everyone; the rest of the Academy needs Plus.
"""

import hashlib
import hmac
import http.client
import json
import logging
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import datetime, timedelta, timezone

from .db import iso, record_audit, utcnow

log = logging.getLogger(__name__)

FREE_TRACK = "launchpad"
FREE_WORLDS = {1, 2, 3}
PAID_STATES = {"active", "trialing", "past_due"}  # past_due keeps access while Stripe retries the card
# A Stripe subscription in one of these can still charge: a plan isn't set by hand over it (the `plan` command).
RUNNING_STATES = PAID_STATES | {"unpaid", "incomplete"}
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
    if info["paid"] and not info["paused"] and plans.KINDS.get(info["kind"], (None, False, False))[2]:
        # (A paused plan gives none of it until it starts again: the free worlds then.)
        # A plan cancelled in Stripe's portal stays on until the paid period ends.
        return {"access": "paid", "state": state, "renews_at": info["renews_at"], "ends_at": info["ends_at"],
                "trial_days": 0, "plan_name": info["plan_name"]}
    if info["trial"] or info["pilot"]:
        # The free trial, or the classroom pilot (whichever lasts longer):
        # the whole Academy for a while, no card.
        from .classrooms import is_class_workspace
        pilot = info["pilot"] and (info["pilot_days"] >= info["trial_days"] or is_class_workspace(org))
        return {"access": "trial", "state": "trial", "renews_at": None, "ends_at": None,
                "trial_days": info["pilot_days"] if pilot else info["trial_days"], "plan_name": None,
                "pilot": pilot}
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
    if full_access(org):
        return True
    if track.key == FREE_TRACK:
        return world.number in FREE_WORLDS
    # The Classroom track's first worlds are free the same way, for a class
    # whose pilot or plan has ended.
    from .academy import CLASSROOM_KEY
    return track.key == CLASSROOM_KEY and world.number in track.topics[:len(FREE_WORLDS)]


def trial_end_for_new_workspace(days):
    """The free trial's end for a workspace signing up now."""
    return iso(utcnow() + timedelta(days=days))


def set_status(conn, org_id, state, renews_at=None, kind=None, interval=None, ends_at=None):
    """Sets the plan by hand (the `plan` command): its status and, with kind,
    which plan, paid monthly unless interval says yearly. ends_at (an ISO
    time) is when a plan set by hand stops, such as the end of a school year
    a school paid for by invoice; None runs until it is changed."""
    if kind is not None and interval is None:
        interval = "month"
    # A Stripe subscription that is over (cancelled, or never paid) has
    # nothing more to say about this workspace: its id is let go, so the plan
    # set by hand is read as one (its end date applies, and cancelling it
    # doesn't ask Stripe about the old subscription). The customer is kept.
    conn.execute("UPDATE orgs SET academy_status = ?, academy_renews_at = ?, academy_ends_at = ?,"
                 " plan = COALESCE(?, plan), plan_interval = COALESCE(?, plan_interval),"
                 " stripe_subscription_id = CASE WHEN academy_status IN ('canceled', 'incomplete_expired')"
                 " THEN NULL ELSE stripe_subscription_id END WHERE id = ?",
                 (state, renews_at, ends_at, kind, interval, org_id))


def subscribed(org):
    """Whether the workspace has a subscription that counts (paid, or past
    due while Stripe retries): checkout never starts a second one. A plan set
    by hand counts until its end date, and not after (plans.access)."""
    from . import plans
    return plans.access(org)["paid"]


# --- Stripe ---------------------------------------------------------------------

# The settings holding each plan's Stripe price id, and the plan (orgs.plan)
# and billing interval (orgs.plan_interval) it is.
PRICE_SETTINGS = {
    "PRO_STRIPE_PRICE": ("pro", "month"),
    "PRO_YEARLY_STRIPE_PRICE": ("pro", "year"),
    "PLUS_STRIPE_PRICE": ("plus", "month"),
    "PLUS_YEARLY_STRIPE_PRICE": ("plus", "year"),
    "PLUS_BUNDLE_UPGRADE_STRIPE_PRICE": ("plus_bundle", "month"),
    "PLUS_BUNDLE_UPGRADE_YEARLY_STRIPE_PRICE": ("plus_bundle", "year"),
    # Classroom plans (plans.py): yearly only.
    "CLASSROOM_YEARLY_STRIPE_PRICE": ("classroom", "year"),
    "SCHOOL_YEARLY_STRIPE_PRICE": ("school", "year"),
}
KINDS = ("pro", "plus", "plus_bundle", "academy", "classroom", "school")
INTERVALS = ("month", "year")


def stripe_ready(cfg, price=None):
    """Whether Stripe can take a payment: the secret key, and the price (or
    any plan's price, when none is named)."""
    if not cfg.get("STRIPE_SECRET_KEY"):
        return False
    return bool(price) if price is not None else any(cfg.get(name) for name in PRICE_SETTINGS)


def plan_for(cfg, obj):
    """The plan a Stripe subscription or checkout session is for, and whether
    it is paid monthly or yearly: (kind, interval).

    Both come from its price when that is one of ours, so a switch in
    Stripe's portal (Pro to Plus, monthly to yearly) arrives by itself.
    Otherwise the interval comes from the price's own recurring interval,
    and either from what the checkout wrote in its metadata. Each is None
    when nothing says (an old Academy plan's renewal, say): the workspace's
    plan or interval then stays as it is."""
    prices = {cfg.get(name): found for name, found in PRICE_SETTINGS.items() if cfg and cfg.get(name)}
    interval = None
    for item in ((obj.get("items") or {}).get("data") or []):
        if not isinstance(item, dict):
            continue
        price = item.get("price")
        price_id = price.get("id") if isinstance(price, dict) else price
        if price_id in prices:
            return prices[price_id]
        if interval is None and isinstance(price, dict):
            recurring = price.get("recurring")
            every = recurring.get("interval") if isinstance(recurring, dict) else None
            interval = every if every in INTERVALS else None
    meta = obj.get("metadata") or {}
    kind = meta.get("plan") if meta.get("plan") in KINDS else None
    if interval is None and meta.get("interval") in INTERVALS:
        interval = meta["interval"]
    return kind, interval


def kind_for(cfg, obj):
    """The plan alone (plan_for)."""
    return plan_for(cfg, obj)[0]


# Each call to Stripe waits this long at most for any step (connecting,
# sending, each read): a page that calls Stripe never hangs on it.
STRIPE_TIMEOUT = 20
# A call that fails before Stripe answers (connection refused or reset) or
# with a 5xx/429 is tried once more after this pause. A POST carries an
# Idempotency-Key, so Stripe does it once however many times it arrives; a
# call that timed out is not tried again (the page has waited long enough).
STRIPE_RETRY_PAUSE = 0.5


def _stripe(cfg, path, fields, method="POST"):
    data = urllib.parse.urlencode(fields).encode() if method == "POST" else None
    request = urllib.request.Request(f"{STRIPE_API}/{path}", data=data, method=method)
    request.add_header("Authorization", "Bearer " + cfg["STRIPE_SECRET_KEY"])
    if data is not None:
        request.add_header("Content-Type", "application/x-www-form-urlencoded")
        request.add_header("Idempotency-Key", uuid.uuid4().hex)
    for attempt in (1, 2):
        try:
            with urllib.request.urlopen(request, timeout=STRIPE_TIMEOUT) as response:
                return json.loads(response.read().decode())
        except urllib.error.HTTPError as exc:
            if attempt == 1 and (exc.code >= 500 or exc.code == 429):
                time.sleep(STRIPE_RETRY_PAUSE)
                continue
            try:
                message = json.loads(exc.read().decode())["error"]["message"]
            except Exception:
                message = f"HTTP {exc.code}"
            raise StripeError(message) from exc
        except (OSError, http.client.HTTPException, ValueError) as exc:
            # Every way the network can fail: refused, reset, cut off half
            # way, TLS, DNS, a timeout. Only HTTPError and URLError were
            # caught before, and a connection reset while reading the answer
            # showed the 500 page instead of "Stripe couldn't be reached".
            timed_out = isinstance(exc, TimeoutError) or isinstance(getattr(exc, "reason", None), TimeoutError)
            if attempt == 1 and not timed_out and not isinstance(exc, ValueError):
                time.sleep(STRIPE_RETRY_PAUSE)
                continue
            if timed_out:
                raise StripeError(f"Stripe didn't answer within {STRIPE_TIMEOUT} seconds.") from exc
            raise StripeError(str(exc) or type(exc).__name__) from exc


# Stripe Checkout takes a subscription's trial_end only at least 48 hours ahead; an hour more for clocks.
STRIPE_MIN_TRIAL_SECONDS = 49 * 3600


def card_after_invoice(org, now=None):
    """When a plan set by hand with an end date (an invoiced school year,
    say) ends, if this workspace is on one now: its card subscription can be
    set up already, its first charge that day (checkout_url's trial_end), so
    it is never paid for twice. None otherwise: no plan, a plan paid through
    Stripe, or one set by hand with no end date."""
    from . import plans
    now = now or utcnow()
    if org["stripe_subscription_id"] or not plans.access(org, now)["paid"]:
        return None
    ends = plans._parse(org["academy_ends_at"])
    return ends if ends is not None and ends > now else None


def first_charge_at(ends, now=None):
    """The card subscription's first charge, as a Unix time: the day the
    invoiced plan ends, or Stripe's earliest when that is under 48 hours away
    (then up to two days come free, never twice paid)."""
    now = now or utcnow()
    return max(int(ends.timestamp()), int(now.timestamp()) + STRIPE_MIN_TRIAL_SECONDS)


def checkout_url(cfg, org, email, success_url, cancel_url, price, kind, quantity, interval="month",
                 trial_end=None):
    """A Stripe Checkout page for one plan: its monthly or yearly price,
    `quantity` locations (plans.location_count), and the plan and interval
    written in the metadata of the session and of the subscription it makes.
    trial_end (a Unix time) puts off the first charge until then: a plan set
    by hand that is already paid for until that day (card_after_invoice)."""
    fields = {
        "mode": "subscription",
        "line_items[0][price]": price,
        "line_items[0][quantity]": str(int(quantity)),
        "success_url": success_url,
        "cancel_url": cancel_url,
        "client_reference_id": str(org["id"]),
        "metadata[org_id]": str(org["id"]),
        "metadata[plan]": kind,
        "metadata[interval]": interval,
        "subscription_data[metadata][org_id]": str(org["id"]),
        "subscription_data[metadata][plan]": kind,
        "subscription_data[metadata][interval]": interval,
        "allow_promotion_codes": "true",
    }
    if trial_end is not None:
        fields["subscription_data[trial_end]"] = str(int(trial_end))
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
    kind, interval = plan_for(cfg, obj)
    return _apply_checkout(conn, owner, obj, None, started=created, kind=kind, interval=interval) is not None


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
    duplicate checkout, say) don't change its plan. Which plan it is, and
    whether monthly or yearly, comes from the subscription's price (cfg names
    each plan's prices) or what the checkout wrote in its metadata; a plan or
    interval switched in Stripe's portal arrives this way."""
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
    plan_kind, interval = plan_for(cfg or {}, obj)
    if kind == "checkout.session.completed":
        return _apply_checkout(conn, org, obj, created, kind=plan_kind, interval=interval)
    if kind in SUBSCRIPTION_EVENTS:
        if paid and current_sub and obj.get("id") != current_sub:
            return None
        last = org["stripe_event_at"]
        if created is not None and last is not None and created < last:
            return None
        _flag_yearly_during_save_offer(conn, cfg or {}, org, interval, deleted=kind.endswith("deleted"))
        state = _apply_subscription(conn, org, obj, plan_kind, interval, deleted=kind.endswith("deleted"),
                                    paid=paid)
        if state is None:
            return None
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


def _flag_yearly_during_save_offer(conn, cfg, org, interval, deleted=False):
    """A switch to yearly in Stripe's customer portal while the save offer's
    discount runs. The app never offers it (plan_views.switch_offer), but the
    portal can, if it lists yearly prices: Stripe then took the discount off
    the year's charge, and that charge is already made when this webhook
    comes, so nothing here can undo it. It is written in the audit trail and
    the log for the operator to settle by hand (docs/OPERATIONS.md, "Stripe's
    customer portal")."""
    from . import plans
    if deleted or interval != "year" or org["plan_interval"] != "month" or not plans.save_offer_running(cfg, org):
        return
    log.warning("Workspace %s switched to yearly in Stripe's portal while its save offer discount ran;"
                " check the yearly charge in Stripe", org["id"])
    record_audit(conn, org["id"], None, "workspace",
                 "Switched to yearly in Stripe's portal while the save offer's discount ran: the discount may have"
                 " come off the yearly charge", actor="Stripe")


def _apply_subscription(conn, org, obj, plan_kind, interval, deleted=False, paid=None):
    """Writes a Stripe subscription onto its workspace: its status, renewal
    and end, its plan and interval, and its pause (pause_collection: Stripe
    has stopped charging until resumes_at; cleared when the pause is gone).
    Returns the status written, or None when it changes nothing (a late
    copy of the subscription's first event)."""
    if paid is None:
        paid = (org["academy_status"] or "none") in PAID_STATES
    state = "canceled" if deleted else obj.get("status", "none")
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
                 " plan = COALESCE(?, plan), plan_interval = COALESCE(?, plan_interval) WHERE id = ?",
                 (state, renews, ends_at, obj.get("id"), obj.get("customer"), plan_kind, interval, org["id"]))
    if "pause_collection" in obj:
        _apply_pause(conn, org, obj.get("pause_collection"), state)
    return state


def _apply_pause(conn, org, pause, state):
    """Mirrors Stripe's pause_collection: a pause with a resume date pauses
    the plan until then; one with no resume date (set in Stripe's dashboard)
    pauses it until Stripe resumes it (pause_open); none (or a subscription
    no longer paid) ends it."""
    resumes = pause.get("resumes_at") if isinstance(pause, dict) else None
    if isinstance(resumes, int) and state in PAID_STATES:
        until = iso(_from_timestamp(resumes))
        conn.execute("UPDATE orgs SET paused_until = ?, pause_open = 0, paused_at = COALESCE(paused_at, ?),"
                     " pause_reminded_at = CASE WHEN paused_until IS ? THEN pause_reminded_at END WHERE id = ?",
                     (until, iso(utcnow()), until, org["id"]))
    elif isinstance(pause, dict) and state in PAID_STATES:
        # Stripe has stopped charging and named no day to start again.
        conn.execute("UPDATE orgs SET paused_until = NULL, pause_open = 1, paused_at = COALESCE(paused_at, ?),"
                     " pause_reminded_at = NULL WHERE id = ?", (iso(utcnow()), org["id"]))
    else:
        clear_pause(conn, org["id"])


def clear_pause(conn, org_id):
    """Ends the workspace's pause, dated or open."""
    conn.execute("UPDATE orgs SET paused_until = NULL, pause_open = 0, paused_at = NULL, pause_reminded_at = NULL"
                 " WHERE id = ?", (org_id,))


# --- Changing the subscription from the app ----------------------------------------
# The cancel screen (pause, the save offer, cancel, keep), switching to yearly
# and upgrading to Plus. Each asks Stripe to change the subscription and
# writes Stripe's answer on the workspace at once; the webhook that follows
# says the same thing again.

def _subscription_path(org):
    sub = org["stripe_subscription_id"] or ""
    if not re.fullmatch(r"sub_[A-Za-z0-9_]{1,250}", sub):
        raise StripeError("This workspace has no Stripe subscription.")
    return f"subscriptions/{sub}"


def update_subscription(conn, cfg, org, fields):
    """Changes the workspace's Stripe subscription and writes the answer."""
    obj = _stripe(cfg, _subscription_path(org), fields)
    kind, interval = plan_for(cfg, obj)
    _apply_subscription(conn, org, obj, kind, interval)
    return obj


def pause_subscription(conn, cfg, org, resumes_at):
    """Stops Stripe charging until resumes_at (an aware datetime): invoices
    in between are voided, and Stripe starts charging again by itself then."""
    return update_subscription(conn, cfg, org, {"pause_collection[behavior]": "void",
                                                "pause_collection[resumes_at]": str(int(resumes_at.timestamp()))})


def resume_subscription(conn, cfg, org):
    """Ends a pause now (an empty pause_collection clears it). Returns True
    when billing starts again today.

    A pause voids each renewal inside it. When one was voided, the period
    running now was never paid for: billing restarts today, a new month from
    now with nothing prorated, or starting again just after a skipped
    renewal (and pausing again just before the next) would never pay.
    Inside the period paid for before the pause, nothing more is charged."""
    fields = {"pause_collection": ""}
    current = _stripe(cfg, _subscription_path(org), {}, method="GET")
    started = _period_start(current)
    paused_at = None
    if org["paused_at"]:
        try:
            paused_at = datetime.fromisoformat(str(org["paused_at"]).replace("Z", "+00:00"))
        except ValueError:
            paused_at = None
    if paused_at is not None and paused_at.tzinfo is None:
        paused_at = paused_at.replace(tzinfo=timezone.utc)
    restart = started is not None and paused_at is not None and started > paused_at.timestamp()
    if restart:
        fields.update({"billing_cycle_anchor": "now", "proration_behavior": "none"})
    update_subscription(conn, cfg, org, fields)
    return restart


def apply_coupon(conn, cfg, org, coupon):
    """Puts a coupon on the subscription (the save offer)."""
    return update_subscription(conn, cfg, org, {"discounts[0][coupon]": coupon})


def cancel_at_period_end(conn, cfg, org, cancel=True):
    """Cancels at the end of the time paid for (or, with cancel=False, takes
    a cancellation back before then)."""
    return update_subscription(conn, cfg, org, {"cancel_at_period_end": "true" if cancel else "false"})


def change_price(conn, cfg, org, price, kind, interval):
    """Moves the subscription to another of our prices (Pro to Plus, monthly
    to yearly). Stripe charges the difference now, taking off the unused part
    of the current period; if the card fails, nothing changes."""
    current = _stripe(cfg, _subscription_path(org), {}, method="GET")
    items = [i for i in ((current.get("items") or {}).get("data") or []) if isinstance(i, dict) and i.get("id")]
    if not items:
        raise StripeError("The subscription has no item to change.")
    return update_subscription(conn, cfg, org, {
        "items[0][id]": items[0]["id"], "items[0][price]": price,
        "items[0][quantity]": str(int(items[0].get("quantity") or 1)),
        "proration_behavior": "always_invoice", "payment_behavior": "error_if_incomplete",
        "metadata[plan]": kind, "metadata[interval]": interval,
    })


# Where a subscription can end up after its first payment. A checkout is
# that first payment, so it never moves a subscription back from one of these.
LATER_STATES = {"past_due", "unpaid", "canceled", "incomplete_expired"}


def _apply_checkout(conn, org, obj, created, started=None, kind=None, interval=None):
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
                 " plan = COALESCE(?, plan), plan_interval = COALESCE(?, plan_interval) WHERE id = ?",
                 (obj.get("customer"), subscription, subscription, kind, interval, org["id"]))
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


def _period_start(subscription):
    """When the subscription's current period began, as a Unix time, or None
    (on the subscription, or on its items in newer Stripe API versions)."""
    value = subscription.get("current_period_start")
    if not isinstance(value, int):
        items = (subscription.get("items") or {}).get("data") or []
        value = next((i.get("current_period_start") for i in items
                      if isinstance(i, dict) and isinstance(i.get("current_period_start"), int)), None)
    return value


def _from_timestamp(seconds):
    return datetime.fromtimestamp(seconds, tz=timezone.utc)
