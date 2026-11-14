# -*- coding: utf-8 -*-
"""OmniArmor's plans, and what a workspace can use right now.

This is the one place the prices live. Every page that names a plan or a
price (the plan page, Help, Settings, the landing page and the industry
pages) reads it from here through plan_views.plan_facts(), and a test checks
that no template types a price.

The plans:

- **Free trial**: every new workspace gets everything in Plus for
  ACADEMY_TRIAL_DAYS days (the trial length the app already had), from the
  day it signs up. No card.
- **Pro**: the compliance tracker (checks, reminders, reports, bulk entry,
  Radar, Intel, the team), per location a month.
- **Plus**: everything in Pro and the whole Future Owner Academy.
- The Academy's first worlds (academy_plan.FREE_WORLDS) stay free for everyone.

A **location** is a workspace. One workspace holds one site: it has one
timezone, one reading per check, and CyberLogix sends one report per
workspace a day; a company with several sites makes a workspace for each.
So every subscription has a quantity of location_count(), which is 1.

Without a plan (the trial over, nothing paid, no Kitchen Safety Bundle), the
compliance tracker is read-only: every record can be seen, printed and
downloaded, nothing is deleted, but no check can be saved and reminders
pause. Export and deleting the workspace always work.

**The Kitchen Safety Bundle.** CyberLogix customers pay CyberLogix for the
bundle, and it includes Pro for that location. A workspace counts as covered
while it receives validly signed CyberLogix reports (connections.py): at
least one in the last BUNDLE_FRESH. When they stop, BUNDLE_GRACE more of Pro
follows, with a banner, and then the rules above. A covered workspace can
add the Academy (Plus) for the difference between Plus and Pro.

**The old Academy plan** (before 1.3.0) is kept as it was: a workspace that
paid for it keeps the whole Academy, and the compliance tracker it had for
free, at its old price, until it changes plan or the subscription ends.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

DEFAULT_TRIAL_DAYS = 14   # the ACADEMY_TRIAL_DAYS default in config.py
LOCATION = "location"


@dataclass(frozen=True)
class Plan:
    key: str
    name: str
    dollars: int            # a month, per location
    price_setting: str      # the setting that holds its Stripe price id
    tracker: bool           # the compliance tracker can be saved to and reminds
    academy: bool           # the whole Future Owner Academy

    @property
    def price(self):
        return price_label(self.dollars)


PRO = Plan("pro", "Pro", 50, "PRO_STRIPE_PRICE", tracker=True, academy=False)
PLUS = Plan("plus", "Plus", 80, "PLUS_STRIPE_PRICE", tracker=True, academy=True)
PLANS = {p.key: p for p in (PRO, PLUS)}

# What the workspace's subscription is for (orgs.plan), and what it gives
# while Stripe says it is paid (academy_plan.PAID_STATES):
#   (name shown, compliance tracker, whole Academy)
KINDS = {
    "pro": (PRO.name, True, False),
    "plus": (PLUS.name, True, True),
    # Plus for a Kitchen Safety Bundle workspace, billed only the difference:
    # the Academy comes from it, the tracker from the bundle.
    "plus_bundle": (PLUS.name, False, True),
    # The old standalone Academy plan: kept as it was (see above).
    "academy": ("Academy plan", True, True),
}

# --- The Kitchen Safety Bundle -------------------------------------------------
BUNDLE_NAME = "Kitchen Safety Bundle"
BUNDLE_DOLLARS = 29                     # what CyberLogix charges a month per location
BUNDLE_INCLUDES = PRO                   # what the bundle includes in OmniArmor
BUNDLE_UPGRADE_SETTING = "PLUS_BUNDLE_UPGRADE_STRIPE_PRICE"
BUNDLE_FRESH = timedelta(days=3)        # a signed report this recent: covered
BUNDLE_GRACE = timedelta(days=7)        # then this long more, with a banner


def price_label(dollars):
    return f"${dollars:,} a month per {LOCATION}"


def bundle_upgrade_dollars():
    """What a bundle workspace pays for Plus: only the difference."""
    return PLUS.dollars - BUNDLE_INCLUDES.dollars


def location_count(org):
    """How many locations a workspace is billed for. A workspace is one
    location (see above), so always 1; a company with several sites has a
    workspace, and a subscription, for each."""
    return 1


# --- Reading the workspace ------------------------------------------------------

def _get(org, key):
    try:
        return org[key]
    except (KeyError, IndexError):
        return None


def _parse(text):
    if not text:
        return None
    try:
        moment = datetime.fromisoformat(str(text).replace("Z", "+00:00"))
    except ValueError:
        return None
    return moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)


def _trial_days(days):
    if days is not None:
        return days
    try:
        from flask import current_app
        return current_app.config.get("ACADEMY_TRIAL_DAYS", DEFAULT_TRIAL_DAYS)
    except RuntimeError:     # no app here (a script, a scheduled sweep given no setting)
        return DEFAULT_TRIAL_DAYS


def trial_ends(org, trial_days=None):
    """When the workspace's free trial ends: the date sign-up set, or, for a
    workspace made some other way, its creation plus the trial length."""
    saved = _parse(_get(org, "academy_trial_ends"))
    if saved is not None:
        return saved
    made = _parse(_get(org, "created_at"))
    return made + timedelta(days=_trial_days(trial_days)) if made else None


def bundle_status(org, now=None):
    """The Kitchen Safety Bundle's cover from the last validly signed
    CyberLogix report: 'covered', 'grace', 'lapsed' or 'none', with the dates."""
    now = now or datetime.now(timezone.utc)
    last = _parse(_get(org, "bundle_report_at"))
    if last is None:
        return {"state": "none", "last": None, "covered_until": None, "grace_ends": None}
    covered_until = last + BUNDLE_FRESH
    grace_ends = covered_until + BUNDLE_GRACE
    state = "covered" if now <= covered_until else "grace" if now <= grace_ends else "lapsed"
    return {"state": state, "last": last, "covered_until": covered_until, "grace_ends": grace_ends}


def access(org, now=None, trial_days=None):
    """What the workspace can use right now, and why.

    tracker: checks can be saved and reminders go out (False: read-only).
    academy: the whole Academy (False: its free worlds only).
    """
    from .academy_plan import PAID_STATES
    now = now or datetime.now(timezone.utc)
    state = _get(org, "academy_status") or "none"
    kind = _get(org, "plan") or "none"
    paid = state in PAID_STATES
    if paid and kind not in KINDS:
        # A paid subscription that never said which plan it is began before
        # Pro and Plus (every checkout since names its plan): the old Academy plan.
        kind = "academy"
    name, sub_tracker, sub_academy = KINDS.get(kind, (None, False, False))
    if not paid:
        sub_tracker = sub_academy = False
    bundle = bundle_status(org, now)
    ends = trial_ends(org, trial_days)
    in_trial = ends is not None and ends > now
    trial_days_left = max(1, -(-int((ends - now).total_seconds()) // 86400)) if in_trial else 0
    if sub_tracker:
        source = "plan"
    elif bundle["state"] == "covered":
        source = "bundle"
    elif bundle["state"] == "grace":
        source = "bundle_grace"
    elif in_trial:
        source = "trial"
    else:
        source = None
    if source is None:
        reason = "bundle_ended" if bundle["state"] == "lapsed" else "plan_ended" if kind != "none" else "trial_ended"
    else:
        reason = None
    return {
        "tracker": source is not None,
        "academy": sub_academy or in_trial,
        "read_only": source is None,
        "reason": reason,              # why it is read-only
        "source": source,              # where the tracker comes from
        "kind": kind, "plan_name": name, "state": state, "paid": paid,
        "subscribed": paid,            # a subscription that counts: checkout won't start a second
        "trial": in_trial, "trial_days": trial_days_left, "trial_ends": ends,
        "bundle": bundle,
        "renews_at": None if _get(org, "academy_ends_at") else _get(org, "academy_renews_at"),
        "ends_at": _get(org, "academy_ends_at") if paid else None,
        "legacy": paid and kind == "academy",
    }


def checkout_choice(cfg, org, plan_key, now=None):
    """What checking out for a plan buys this workspace: (kind, Stripe price
    id, dollars). Plus for a workspace the Kitchen Safety Bundle covers is
    billed only the difference, when that price is set up; otherwise at its
    full price (the plan page says so)."""
    plan = PLANS[plan_key]
    if plan is PLUS and bundle_status(org, now)["state"] == "covered" and cfg.get(BUNDLE_UPGRADE_SETTING):
        return "plus_bundle", cfg[BUNDLE_UPGRADE_SETTING], bundle_upgrade_dollars()
    return plan.key, cfg.get(plan.price_setting) or "", plan.dollars
