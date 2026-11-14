# -*- coding: utf-8 -*-
"""The plan page (Pro, Plus, the free trial, the Kitchen Safety Bundle and the
free Academy), Stripe Checkout and the customer portal, and Stripe's webhook.

What each plan gives and what it costs live in plans.py; the Stripe side is
academy_plan.py. plan_facts() is what every page says about the plans."""

import json

from flask import Blueprint, abort, current_app, flash, g, jsonify, redirect, render_template, request, url_for

from . import academy, academy_plan, plans
from .academy_views import grown_ups_only
from .db import get_db
from .security import flash_error, owner_required

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
        "bundle": {
            "name": plans.BUNDLE_NAME,
            "price": plans.price_label(plans.BUNDLE_DOLLARS),
            "includes": plans.BUNDLE_INCLUDES,
            "upgrade_price": plans.price_label(plans.bundle_upgrade_dollars()),
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
    choices = {key: plans.checkout_choice(cfg, g.org, key) for key in plans.PLANS}
    return render_template("app/plan.html", access=access, confirming=welcome, facts=facts,
                           ready={key: academy_plan.stripe_ready(cfg, price) for key, (_, price, _) in choices.items()},
                           upgrade=choices["plus"][0] == "plus_bundle",
                           has_customer=bool(g.org["stripe_customer_id"]))


@plan.route("/app/plan/checkout", methods=["POST"])
@owner_required
def checkout():
    cfg = current_app.config
    key = request.form.get("plan", "")
    if key not in plans.PLANS:
        flash_error("Pick Pro or Plus.")
        return redirect(url_for("plan.plan_page"))
    access = plans.access(g.org)
    if academy_plan.subscribed(g.org):
        flash_error(f"You already have {access['plan_name'] or 'a plan'}. Use Manage billing to change it.")
        return redirect(url_for("plan.plan_page"))
    if key == plans.BUNDLE_INCLUDES.key and access["bundle"]["state"] == "covered":
        flash_error(f"{plans.BUNDLE_INCLUDES.name} is already included with your {plans.BUNDLE_NAME}.")
        return redirect(url_for("plan.plan_page"))
    kind, price, _ = plans.checkout_choice(cfg, g.org, key)
    if not academy_plan.stripe_ready(cfg, price):
        flash_error(f"Online payment isn't set up yet. Please contact us to start {plans.PLANS[key].name}.")
        return redirect(url_for("plan.plan_page"))
    try:
        # Stripe fills in {CHECKOUT_SESSION_ID}, so the plan page can confirm the payment on return.
        url = academy_plan.checkout_url(cfg, g.org, g.user["email"],
                                        url_for("plan.plan_page", welcome=1, _external=True)
                                        + "&session_id={CHECKOUT_SESSION_ID}",
                                        url_for("plan.plan_page", _external=True),
                                        price=price, kind=kind, quantity=plans.location_count(g.org))
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
