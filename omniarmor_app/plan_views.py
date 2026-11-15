# -*- coding: utf-8 -*-
"""The plan page (Pro, Plus, the free trial, the Kitchen Safety Bundle and the
free Academy), Stripe Checkout and the customer portal, and Stripe's webhook.

What each plan gives and what it costs live in plans.py; the Stripe side is
academy_plan.py. plan_facts() is what every page says about the plans."""

import json

from flask import Blueprint, abort, current_app, flash, g, jsonify, redirect, render_template, request, url_for

from . import academy, academy_plan, plans, usage
from .academy_views import grown_ups_only
from .db import get_db, iso, record_audit, utcnow
from .security import flash_error, owner_required
from .tracking import local_date

plan = Blueprint("plan", __name__)


def plan_facts(cfg):
    """Everything the plan page, Help, Settings, the landing page and the
    industry pages say about the plans, read from the code and settings that
    decide them (plans.py, academy_plan.py, academy.py), so no page types a
    number or a price."""
    from .catalog import INDUSTRIES, rules_for
    free_track = academy.TRACKS[academy_plan.FREE_TRACK]
    free_worlds = [academy.world(n) for n in sorted(academy_plan.FREE_WORLDS)]
    offered = [plans.PRO, plans.PLUS]
    return {
        "plans": offered,
        "pro": plans.PRO,
        "plus": plans.PLUS,
        "location": plans.LOCATION,
        "trial_days": cfg["ACADEMY_TRIAL_DAYS"],
        # Monthly or yearly: which plans can be paid yearly (their yearly
        # Stripe price is set), and what a year gives free.
        "yearly": plans.yearly_offered(cfg),
        "free_months": plans.free_months(),
        "free_label": plans.free_label(),
        "months_paid": plans.MONTHS_PAID_YEARLY,
        "months_in_year": plans.MONTHS_IN_YEAR,
        "bundle": {
            "name": plans.BUNDLE_NAME,
            "price": plans.price_label(plans.BUNDLE_DOLLARS),
            "includes": plans.BUNDLE_INCLUDES,
            "upgrade_price": plans.price_label(plans.bundle_upgrade_dollars()),
            "upgrade_yearly_price": plans.price_label(plans.bundle_upgrade_dollars(plans.YEAR), plans.YEAR),
            "upgrade_yearly_short": plans.price_label(plans.bundle_upgrade_dollars(plans.YEAR), plans.YEAR, per=False),
            "upgrade_ready": bool(cfg.get(plans.BUNDLE_UPGRADE_SETTING)),
            "fresh_days": plans.BUNDLE_FRESH.days,
            "grace_days": plans.BUNDLE_GRACE.days,
        },
        "max_learners": academy.MAX_LEARNERS,
        "max_friends": academy.MAX_FRIENDS,
        "free_track": free_track,
        "free_worlds": free_worlds,
        "free_levels": sum(free_track.stages(w) for w in free_worlds),
        "free_duel_worlds": [w for w in free_worlds if w.number in academy.DUEL_WORLDS],
        "duel_worlds": len(academy.DUEL_WORLDS),
        "tracks": academy.TRACK_LIST,
        "topic_worlds": len(academy.TOPIC_WORLDS),
        "rule_quests": len(academy.INDUSTRY_WORLDS),
        "industries": len(INDUSTRIES),
        "checks": sum(len(rules_for(i)) for i in INDUSTRIES),
    }


@plan.route("/app/plan")
@grown_ups_only
def plan_page():
    cfg = current_app.config
    welcome = request.args.get("welcome") == "1"
    session_id = request.args.get("session_id")
    if session_id is not None:
        # Back from Stripe Checkout: settle the payment now, not when the webhook comes.
        if not academy_plan.subscribed(g.org):
            conn = get_db()
            try:
                if academy_plan.confirm_checkout(conn, cfg, g.org, session_id):
                    conn.commit()
            except academy_plan.StripeError as exc:
                current_app.logger.warning("Stripe checkout check failed: %s", exc)
        return redirect(url_for("plan.plan_page", welcome=1 if welcome else None))
    access = plans.access(g.org)
    if welcome and access["paid"]:
        flash(f"Thank you! {access['plan_name']} is on for {g.org['name']}.", "ok")
        return redirect(url_for("plan.plan_page"))
    facts = plan_facts(cfg)
    offers = _offers(cfg, g.org)
    # The yearly toggle shows when any plan this workspace can buy is offered
    # yearly; ?billing=yearly opens the page with it on.
    yearly_toggle = any(o[plans.YEAR]["offered"] for o in offers.values())
    return render_template("app/plan.html", access=access, confirming=welcome, facts=facts, offers=offers,
                           ready={key: o[plans.MONTH]["ready"] for key, o in offers.items()},
                           yearly_toggle=yearly_toggle,
                           start_yearly=yearly_toggle and (request.args.get("billing") == "yearly"
                                                           or (access["paid"] and access["yearly"])),
                           has_customer=bool(g.org["stripe_customer_id"]),
                           switch_yearly=switch_offer(cfg, g.org, access, plans.YEAR),
                           switch_plus=switch_offer(cfg, g.org, access, plans.MONTH, to_plus=True))


def switch_offer(cfg, org, access, interval, to_plus=False):
    """What switching a paid subscription offers: to yearly (a monthly Pro,
    Plus or bundle Plus whose yearly price is set up: "2 months free"), or to
    Plus (a paid Pro, on the interval it pays now). None when it doesn't apply.
    The switch itself happens in Stripe (academy_plan.change_price)."""
    if not (access["paid"] and org["stripe_subscription_id"] and cfg.get("STRIPE_SECRET_KEY")):
        return None
    if access["state"] == "past_due" or access["paused"] or access["ends_at"]:
        return None
    if to_plus:
        if access["kind"] != plans.PRO.key:
            return None
        interval = access["interval"]
        target = plans.PLUS.key
    else:
        if access["interval"] != plans.MONTH or access["kind"] not in ("pro", "plus", "plus_bundle"):
            return None
        target = plans.PLUS.key if access["kind"] == "plus_bundle" else access["kind"]
    kind, price, dollars = plans.checkout_choice(cfg, org, target, interval)
    if not price or (not to_plus and kind != access["kind"]):
        return None
    monthly = plans.monthly_dollars(access["kind"]) or 0
    return {"plan": target, "interval": interval, "kind": kind, "name": plans.KINDS[kind][0],
            "price": plans.price_label(dollars, interval, per=False),
            # What twelve months cost paid monthly, and what yearly saves on that.
            "twelve_months": plans.price_label(monthly * plans.MONTHS_IN_YEAR, plans.YEAR, per=False),
            "saving": plans.price_label(plans.yearly_saving(monthly), plans.YEAR, per=False),
            "free_label": plans.free_label()}


def _offers(cfg, org):
    """For each plan and interval, what the plan page offers this workspace:
    whether that price is set up at all (offered), whether checkout can take
    it now (ready), and whether it is Plus at the Kitchen Safety Bundle price
    (upgrade)."""
    out = {}
    for key in plans.PLANS:
        out[key] = {}
        for interval in plans.INTERVALS:
            kind, price, _ = plans.checkout_choice(cfg, org, key, interval)
            out[key][interval] = {"offered": bool(price), "ready": academy_plan.stripe_ready(cfg, price),
                                  "upgrade": kind == "plus_bundle"}
    return out


@plan.route("/app/plan/checkout", methods=["POST"])
@owner_required
def checkout():
    cfg = current_app.config
    key = request.form.get("plan", "")
    interval = request.form.get("interval") or plans.MONTH
    if key not in plans.PLANS or interval not in plans.INTERVALS:
        flash_error("Pick Pro or Plus.")
        return redirect(url_for("plan.plan_page"))
    access = plans.access(g.org)
    if academy_plan.subscribed(g.org):
        flash_error(f"You already have {access['plan_name'] or 'a plan'}. Use Manage billing to change it.")
        return redirect(url_for("plan.plan_page"))
    if key == plans.BUNDLE_INCLUDES.key and access["bundle"]["state"] == "covered":
        flash_error(f"{plans.BUNDLE_INCLUDES.name} is already included with your {plans.BUNDLE_NAME}.")
        return redirect(url_for("plan.plan_page"))
    kind, price, _ = plans.checkout_choice(cfg, g.org, key, interval)
    if not price and interval == plans.YEAR:
        flash_error(f"{plans.PLANS[key].name} can't be paid yearly yet. Choose monthly instead.")
        return redirect(url_for("plan.plan_page"))
    if not academy_plan.stripe_ready(cfg, price):
        flash_error(f"Online payment isn't set up yet. Please contact us to start {plans.PLANS[key].name}.")
        return redirect(url_for("plan.plan_page"))
    try:
        # Stripe fills in {CHECKOUT_SESSION_ID}, so the plan page can confirm the payment on return.
        url = academy_plan.checkout_url(cfg, g.org, g.user["email"],
                                        url_for("plan.plan_page", welcome=1, _external=True)
                                        + "&session_id={CHECKOUT_SESSION_ID}",
                                        url_for("plan.plan_page", _external=True),
                                        price=price, kind=kind, quantity=plans.location_count(g.org),
                                        interval=interval)
    except academy_plan.StripeError as exc:
        current_app.logger.warning("Stripe checkout failed: %s", exc)
        flash_error("We couldn't open checkout just now. Please try again in a minute.")
        return redirect(url_for("plan.plan_page"))
    return redirect(url, code=303)


@plan.route("/app/plan/manage", methods=["POST"])
@owner_required
def manage():
    cfg = current_app.config
    if not (cfg.get("STRIPE_SECRET_KEY") and g.org["stripe_customer_id"]):
        flash_error("There's no subscription to manage yet.")
        return redirect(url_for("plan.plan_page"))
    try:
        url = academy_plan.portal_url(cfg, g.org, url_for("plan.plan_page", _external=True))
    except academy_plan.StripeError as exc:
        current_app.logger.warning("Stripe portal failed: %s", exc)
        flash_error("We couldn't open the billing page just now. Please try again in a minute.")
        return redirect(url_for("plan.plan_page"))
    return redirect(url, code=303)


def upgrade_action(cfg, org, access):
    """How an upgrade offer's button moves this workspace to Plus: 'switch'
    (a paid Pro subscription, switched in Stripe at once), 'checkout' (Pro
    from the Kitchen Safety Bundle buys Plus at the difference through
    Stripe Checkout) or 'page' (the plan page, when neither is set up)."""
    if switch_offer(cfg, org, access, plans.MONTH, to_plus=True):
        return "switch"
    if not access["paid"]:
        _, price, _ = plans.checkout_choice(cfg, org, plans.PLUS.key, plans.MONTH)
        if academy_plan.stripe_ready(cfg, price):
            return "checkout"
    return "page"


# --- Cancel, pause, the save offer, and switching -------------------------------------

def _back_to_cancel():
    return redirect(url_for("plan.cancel_page"))


def _stripe_failed(exc, what):
    current_app.logger.warning("Stripe %s failed: %s", what, exc)
    flash_error(f"We couldn't {what} just now, so nothing changed. Please try again in a minute.")


@plan.route("/app/plan/cancel")
@owner_required
def cancel_page():
    """Cancelling, with two offers beside it: pause for 1, 2 or 3 months, and
    (once per workspace) a discount. Cancelling stays one click."""
    cfg = current_app.config
    options = plans.cancel_options(cfg, g.org)
    if not options["access"]["paid"]:
        flash_error("There's no plan to cancel.")
        return redirect(url_for("plan.plan_page"))
    now = utcnow()
    resume_dates = {m: plans.add_months(now, m) for m in plans.PAUSE_MONTHS}
    return render_template("app/cancel.html", o=options, a=options["access"], facts=plan_facts(cfg),
                           resume_dates=resume_dates, notice_days=plans.RESUME_NOTICE.days)


@plan.route("/app/plan/pause", methods=["POST"])
@owner_required
def pause():
    cfg = current_app.config
    months = request.form.get("months", type=int)
    options = plans.cancel_options(cfg, g.org)
    if months not in plans.PAUSE_MONTHS or not options["can_pause"]:
        flash_error("This plan can't be paused right now.")
        return _back_to_cancel()
    now = utcnow()
    until = plans.add_months(now, months)
    conn = get_db()
    try:
        if options["online"]:
            academy_plan.pause_subscription(conn, cfg, g.org, until)
    except academy_plan.StripeError as exc:
        conn.rollback()
        _stripe_failed(exc, "pause your plan")
        return _back_to_cancel()
    conn.execute("UPDATE orgs SET paused_until = ?, paused_at = ?, pause_reminded_at = NULL WHERE id = ?",
                 (iso(until), iso(now), g.org["id"]))
    record_audit(conn, g.org["id"], g.user["id"], "workspace",
                 f"Plan paused for {months} month{'s' if months != 1 else ''}, until {until.date().isoformat()}")
    conn.commit()
    usage.count(conn, "plan_pauses")
    flash(f"Your plan is paused until {local_date(iso(until), g.org)}. You won't be charged, reminders are off and"
          " the workspace is read-only until then. Everything is kept, and it starts again by itself.", "ok")
    return redirect(url_for("plan.plan_page"))


@plan.route("/app/plan/resume", methods=["POST"])
@owner_required
def resume():
    cfg = current_app.config
    options = plans.cancel_options(cfg, g.org)
    if not options["can_resume"]:
        flash_error("This plan isn't paused.")
        return redirect(url_for("plan.plan_page"))
    conn = get_db()
    try:
        if options["online"]:
            academy_plan.resume_subscription(conn, cfg, g.org)
    except academy_plan.StripeError as exc:
        conn.rollback()
        _stripe_failed(exc, "start your plan again")
        return redirect(url_for("plan.plan_page"))
    conn.execute("UPDATE orgs SET paused_until = NULL, paused_at = NULL, pause_reminded_at = NULL WHERE id = ?",
                 (g.org["id"],))
    record_audit(conn, g.org["id"], g.user["id"], "workspace", "Plan started again before the end of its pause")
    conn.commit()
    flash("Welcome back! Your plan is on again: checks can be saved and reminders are back on.", "ok")
    return redirect(url_for("plan.plan_page"))


@plan.route("/app/plan/save-offer", methods=["POST"])
@owner_required
def save_offer():
    cfg = current_app.config
    options = plans.cancel_options(cfg, g.org)
    if not options["can_save"]:
        flash_error("That offer isn't available for this workspace." if options["save_used"]
                    else "That offer isn't available right now.")
        return _back_to_cancel()
    conn = get_db()
    # Claimed first, so two clicks (or two tabs) can't take it twice.
    claimed = conn.execute("UPDATE orgs SET save_offer_used_at = ? WHERE id = ? AND save_offer_used_at IS NULL",
                           (iso(utcnow()), g.org["id"])).rowcount
    if claimed != 1:
        conn.rollback()
        flash_error("That offer isn't available for this workspace.")
        return _back_to_cancel()
    try:
        academy_plan.apply_coupon(conn, cfg, g.org, cfg["SAVE_OFFER_STRIPE_COUPON"])
    except academy_plan.StripeError as exc:
        conn.rollback()
        _stripe_failed(exc, "add the discount")
        return _back_to_cancel()
    percent, months = options["save_percent"], options["save_months"]
    record_audit(conn, g.org["id"], g.user["id"], "workspace",
                 f"Save offer taken: {percent}% off the next {months} month{'s' if months != 1 else ''}")
    conn.commit()
    usage.count(conn, "save_offers")
    flash(f"Done: {percent}% off your next {months} month{'s' if months != 1 else ''}. Your plan stays on as it is."
          " Thank you for staying!", "ok")
    return redirect(url_for("plan.plan_page"))


@plan.route("/app/plan/cancel", methods=["POST"])
@owner_required
def cancel():
    """One click: the plan is cancelled and stays on until the end of the
    time paid for. A plan set by hand (no Stripe subscription) ends at its
    renewal date if it has one, otherwise now."""
    cfg = current_app.config
    options = plans.cancel_options(cfg, g.org)
    if not options["can_cancel"]:
        flash_error("There's no plan to cancel." if not options["access"]["paid"] else
                    "This plan is already cancelled." if options["access"]["ends_at"] else
                    "Online billing isn't set up, so the plan can't be cancelled here. Please contact us.")
        return redirect(url_for("plan.plan_page"))
    conn = get_db()
    try:
        if options["online"]:
            academy_plan.cancel_at_period_end(conn, cfg, g.org)
        elif g.org["academy_renews_at"]:
            conn.execute("UPDATE orgs SET academy_ends_at = academy_renews_at WHERE id = ?", (g.org["id"],))
        else:
            conn.execute("UPDATE orgs SET academy_status = 'canceled', paused_until = NULL WHERE id = ?",
                         (g.org["id"],))
    except academy_plan.StripeError as exc:
        conn.rollback()
        _stripe_failed(exc, "cancel your plan")
        return _back_to_cancel()
    record_audit(conn, g.org["id"], g.user["id"], "workspace", "Plan cancelled")
    conn.commit()
    usage.count(conn, "plan_cancels")
    org = conn.execute("SELECT * FROM orgs WHERE id = ?", (g.org["id"],)).fetchone()
    after = plans.access(org)
    if after["paid"] and after["ends_at"]:
        flash(f"Your plan is cancelled. It stays on until {local_date(after['ends_at'], org)}, and you won't be"
              " charged again. Your records are kept either way.", "ok")
    else:
        flash("Your plan is cancelled. Your records are kept: you can still see, print and download them.", "ok")
    return redirect(url_for("plan.plan_page"))


@plan.route("/app/plan/keep", methods=["POST"])
@owner_required
def keep():
    """Takes a cancellation back before the plan ends."""
    cfg = current_app.config
    options = plans.cancel_options(cfg, g.org)
    if not options["can_keep"]:
        flash_error("There's no cancellation to take back.")
        return redirect(url_for("plan.plan_page"))
    conn = get_db()
    try:
        academy_plan.cancel_at_period_end(conn, cfg, g.org, cancel=False)
    except academy_plan.StripeError as exc:
        conn.rollback()
        _stripe_failed(exc, "keep your plan")
        return redirect(url_for("plan.plan_page"))
    record_audit(conn, g.org["id"], g.user["id"], "workspace", "Cancellation taken back: the plan renews as before")
    conn.commit()
    flash("Your plan is no longer cancelled. It renews as before.", "ok")
    return redirect(url_for("plan.plan_page"))


@plan.route("/app/plan/switch", methods=["POST"])
@owner_required
def switch():
    """A paid subscription moves to Plus or to yearly, at our Stripe prices.
    Stripe charges the difference now, taking off the unused part of the
    current period; if the card is declined, nothing changes."""
    cfg = current_app.config
    access = plans.access(g.org)
    to = request.form.get("to", "")
    offer = (switch_offer(cfg, g.org, access, plans.YEAR) if to == "yearly"
             else switch_offer(cfg, g.org, access, plans.MONTH, to_plus=True) if to == "plus" else None)
    if offer is None:
        flash_error("That switch isn't available for this plan. Manage billing has every option.")
        return redirect(url_for("plan.plan_page"))
    kind, price, _ = plans.checkout_choice(cfg, g.org, offer["plan"], offer["interval"])
    conn = get_db()
    try:
        academy_plan.change_price(conn, cfg, g.org, price, kind, offer["interval"])
    except academy_plan.StripeError as exc:
        conn.rollback()
        current_app.logger.warning("Stripe plan switch failed: %s", exc)
        flash_error("Stripe couldn't make that switch, so nothing changed. If your card was declined, update it in"
                    " Manage billing and try again.")
        return redirect(url_for("plan.plan_page"))
    record_audit(conn, g.org["id"], g.user["id"], "workspace",
                 f"Plan switched to {offer['name']}, paid {'yearly' if offer['interval'] == plans.YEAR else 'monthly'}")
    conn.commit()
    usage.count(conn, "plan_switches")
    flash(f"Done: you're on {offer['name']}, {offer['price']}. Stripe sends the receipt.", "ok")
    return redirect(url_for("plan.plan_page"))


@plan.route("/app/nudges/<kind>/dismiss", methods=["POST"])
def dismiss_nudge(kind):
    """Hides an upgrade offer for good, for the person who dismissed it."""
    from . import nudges
    from .security import safe_next
    if g.get("user") is None:
        abort(403)
    if not nudges.dismiss(get_db(), g.user["id"], kind):
        abort(404)
    flash("Got it. We won't show that offer again.", "ok")
    return redirect(safe_next(request.form.get("next")))


@plan.route("/billing/stripe/webhook", methods=["POST"])
def stripe_webhook():
    payload = request.get_data()
    if not academy_plan.verify_webhook(payload, request.headers.get("Stripe-Signature", ""),
                                       current_app.config.get("STRIPE_WEBHOOK_SECRET", "")):
        abort(400)
    try:
        event = json.loads(payload)
    except ValueError:
        abort(400)
    conn = get_db()
    change = academy_plan.apply_event(conn, event, current_app.config)
    conn.commit()
    if change:
        current_app.logger.info("Plan %s for event %s", change, event.get("id"))
    return jsonify(received=True)
