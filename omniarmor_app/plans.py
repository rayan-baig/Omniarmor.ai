# -*- coding: utf-8 -*-
"""Aegizyn's plans, and what a workspace can use right now.

This is the one place the prices live. Every page that names a plan or a
price (the plan page, Help, Settings, the landing page and the industry
pages) reads it from here through plan_views.plan_facts(), and a test checks
that no template types a price.

The plans:

- **Free trial**: every sign-up's workspace gets everything in Plus for
  ACADEMY_TRIAL_DAYS days (the trial length the app already had), from the
  day it signs up. No card.
- **Pro**: the compliance tracker (checks, reminders, reports, bulk entry,
  the reminders and report pages, the team), per location a month.
- **Plus**: everything in Pro and the whole Future Owner Academy.
- The Academy's first worlds (academy_plan.FREE_WORLDS) stay free for everyone.

**Monthly or yearly.** Pro, Plus and the bundle's Plus can each be paid
monthly or yearly. A year costs MONTHS_PAID_YEARLY months' price for
MONTHS_IN_YEAR months ("2 months free"): the yearly prices are worked out
here from the monthly ones, never typed. Each has its own Stripe price
setting; a yearly setting left empty means that plan is offered monthly
only. A yearly plan cancelled in Stripe's portal stays on to the end of the
year paid for, with no partial refund; then the rules below apply.

A **location** is a workspace. One workspace holds one site: it has one
timezone, one reading per check, and Kryozyn sends one report per
workspace a day; a company with several sites makes a workspace for each.
So every subscription has a quantity of location_count(), which is 1.

Without a plan (the trial over, nothing paid, no Kitchen Safety Bundle), the
compliance tracker is read-only: every record can be seen, printed and
downloaded, nothing is deleted, but no check can be saved and reminders
pause. Export and deleting the workspace always work.

**The Kitchen Safety Bundle.** Kryozyn customers pay Kryozyn for the
bundle, and it includes Pro for that location. A workspace counts as covered
while it receives validly signed Kryozyn reports (connections.py): at
least one in the last BUNDLE_FRESH. When they stop, BUNDLE_GRACE more of Pro
follows, with a banner, and then the rules above. A covered workspace can
add the Academy (Plus) for the difference between Plus and Pro.

**The old Academy plan** (before 1.3.0) is kept as it was: a workspace that
paid for it keeps the whole Academy, and the compliance tracker it had for
free, at its old price, until it changes plan or the subscription ends.

**Pausing.** A plan paid monthly can be paused for PAUSE_MONTHS (1, 2 or 3
months) instead of cancelled: Stripe stops charging (pause_collection), the
workspace is read-only exactly as without a plan (reminders stop, nothing is
deleted), and it starts again by itself on the date chosen (orgs.paused_until).
A pause set in Stripe's dashboard with no end date (orgs.pause_open) is the
same, with no end date, until Stripe resumes it.
A yearly plan is already paid for the year, so it isn't paused.

**Classroom plans** (classrooms.py). A school or a teacher can run the
Future Owner Academy for a whole class. Two plans, paid yearly only (a school
pays for a school year, often by invoice):

- **Classroom**: the whole Academy for one class of up to CLASS_SIZE
  students. No compliance tracker. Its price is the Academy's share of Plus
  for a year (Plus less Pro, MONTHS_PAID_YEARLY months: $300), a dollar under,
  so it is never dearer than adding the Academy, and never a cheaper way for
  a business to get the tracker (it has none).
- **Whole school**: the whole Academy for any number of classes, and the
  compliance tracker (School Aegizyn's checklist) for the school. It costs
  between four and five Classrooms, so it pays from the fifth class, and
  more than a year of Plus, which it includes.

Each has a Stripe price setting for checkout; a school that wants an invoice
gets the plan set by hand instead (`flask --app wsgi plan <id> classroom
--until <date>`), the same mechanism as every plan set by hand. A plan set
by hand with an end date stops at 23:59:59 that day in the workspace's
timezone. A school on such a plan can set up its card subscription before
then: its first charge is that day (Stripe's trial_end), so it never pays
twice (academy_plan.card_after_invoice).

**The free trial and the pilot are one per owner.** A location added later
(views.add_location) starts without a trial, and the pilot can be started
once, in whichever of the owner's locations (users.pilot_used_at, kept when
that location is deleted).

**The classroom pilot.** Once per owner, a free trial of PILOT_DAYS
(the CLASSROOM_PILOT_DAYS setting): one class of up to CLASS_SIZE students and
the whole Academy, no card. It ends by itself; the classes, their progress
and the trial report are kept.

**The save offer.** Once per workspace, ever, a monthly payer about to cancel
can take SAVE_OFFER_PERCENT off the next SAVE_OFFER_MONTHS months, through the
Stripe coupon named in SAVE_OFFER_STRIPE_COUPON (the settings decide the
amount; the coupon must match them). No coupon set: no offer.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

DEFAULT_TRIAL_DAYS = 14   # the ACADEMY_TRIAL_DAYS default in config.py
LOCATION = "location"

# Billing intervals, as Stripe names them (a price's recurring.interval), and
# what orgs.plan_interval holds.
MONTH = "month"
YEAR = "year"
INTERVALS = (MONTH, YEAR)
MONTHS_IN_YEAR = 12
MONTHS_PAID_YEARLY = 10     # a yearly plan costs ten months: two months free


def yearly_dollars(monthly):
    """A year's price from a month's: MONTHS_PAID_YEARLY months."""
    return monthly * MONTHS_PAID_YEARLY


def free_months():
    """How many months a yearly plan gives free."""
    return MONTHS_IN_YEAR - MONTHS_PAID_YEARLY


def free_label():
    """What the pages call it: "2 months free"."""
    months = free_months()
    return f"{months} month{'s' if months != 1 else ''} free"


@dataclass(frozen=True)
class Plan:
    key: str
    name: str
    dollars: int            # a month, per location
    price_setting: str      # the setting that holds its monthly Stripe price id
    tracker: bool           # the compliance tracker can be saved to and reminds
    academy: bool           # the whole Future Owner Academy
    yearly_price_setting: str = ""   # the setting that holds its yearly Stripe price id

    @property
    def price(self):
        return price_label(self.dollars)

    @property
    def yearly_dollars(self):
        return yearly_dollars(self.dollars)

    @property
    def yearly_price(self):
        return price_label(self.yearly_dollars, YEAR)

    @property
    def yearly_short(self):
        """The yearly price without "per location", for "or $500 a year"."""
        return price_label(self.yearly_dollars, YEAR, per=False)

    def dollars_for(self, interval):
        return self.yearly_dollars if interval == YEAR else self.dollars

    def setting(self, interval):
        """The setting holding this plan's Stripe price id for an interval."""
        return self.yearly_price_setting if interval == YEAR else self.price_setting


@dataclass(frozen=True)
class ClassroomPlan:
    """A plan for running the Academy in a school (see above): a year's price,
    the Stripe price setting, how many classes (None: no limit) and whether
    the compliance tracker comes with it."""
    key: str
    name: str
    yearly_dollars: int
    price_setting: str
    max_classes: object      # int, or None for no limit
    tracker: bool
    summary: str

    @property
    def yearly_price(self):
        return price_label(self.yearly_dollars, YEAR, per=False)


PRO = Plan("pro", "Pro", 50, "PRO_STRIPE_PRICE", tracker=True, academy=False,
           yearly_price_setting="PRO_YEARLY_STRIPE_PRICE")
PLUS = Plan("plus", "Plus", 80, "PLUS_STRIPE_PRICE", tracker=True, academy=True,
            yearly_price_setting="PLUS_YEARLY_STRIPE_PRICE")
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
    # Classroom plans (see above): the Academy for one class, or for every
    # class and the tracker for the school.
    "classroom": ("Classroom", False, True),
    "school": ("Whole school", True, True),
}

# --- Classroom plans ---------------------------------------------------------------
CLASS_SIZE = 35                 # students in one class, on every classroom plan and the pilot
DEFAULT_PILOT_DAYS = 30         # the CLASSROOM_PILOT_DAYS default in config.py
PILOT_CLASSES = 1
CLASSROOM = ClassroomPlan("classroom", "Classroom", 299, "CLASSROOM_YEARLY_STRIPE_PRICE", 1, tracker=False,
                          summary=f"The whole Academy for one class of up to {CLASS_SIZE} students.")
SCHOOL = ClassroomPlan("school", "Whole school", 1490, "SCHOOL_YEARLY_STRIPE_PRICE", None, tracker=True,
                       summary=(f"The whole Academy for every class (up to {CLASS_SIZE} students each), and the"
                                " school safety checklist with reminders for the school."))
CLASSROOM_PLANS = {p.key: p for p in (CLASSROOM, SCHOOL)}

# --- The Kitchen Safety Bundle -------------------------------------------------
BUNDLE_NAME = "Kitchen Safety Bundle"
BUNDLE_DOLLARS = 29                     # what Kryozyn charges a month per location
BUNDLE_INCLUDES = PRO                   # what the bundle includes in Aegizyn
BUNDLE_UPGRADE_SETTING = "PLUS_BUNDLE_UPGRADE_STRIPE_PRICE"
BUNDLE_UPGRADE_YEARLY_SETTING = "PLUS_BUNDLE_UPGRADE_YEARLY_STRIPE_PRICE"
BUNDLE_FRESH = timedelta(days=3)        # a signed report this recent: covered
BUNDLE_GRACE = timedelta(days=7)        # then this long more, with a banner


def price_label(dollars, interval=MONTH, per=True):
    whole = float(dollars).is_integer()
    amount = f"${int(dollars):,}" if whole else f"${dollars:,.2f}"
    return f"{amount} a {interval}" + (f" per {LOCATION}" if per else "")


def yearly_saving(monthly):
    """What paying yearly saves in a year, per location: twelve months'
    price less the yearly price ($100 for Pro)."""
    return monthly * MONTHS_IN_YEAR - yearly_dollars(monthly)


# --- Pausing and the save offer ----------------------------------------------------

PAUSE_MONTHS = (1, 2, 3)
RESUME_NOTICE = timedelta(days=3)      # the "starts again soon" email, this long before
PAUSABLE_KINDS = ("pro", "plus", "academy")


def add_months(moment, months):
    """The same day and time `months` calendar months later (the last day of
    a shorter month: 31 January plus one month is 28 or 29 February)."""
    import calendar
    month = moment.month - 1 + months
    year, month = moment.year + month // 12, month % 12 + 1
    day = min(moment.day, calendar.monthrange(year, month)[1])
    return moment.replace(year=year, month=month, day=day)


def save_offer_terms(cfg):
    """The save offer's amount from the settings: (percent, months), or None
    when there is no coupon set (no offer at all)."""
    if not cfg.get("SAVE_OFFER_STRIPE_COUPON"):
        return None
    return int(cfg.get("SAVE_OFFER_PERCENT") or 0), int(cfg.get("SAVE_OFFER_MONTHS") or 0)


def save_offer_running(cfg, org, now=None):
    """Whether the save offer's discount is still on the subscription: taken
    less than SAVE_OFFER_MONTHS months ago. Stripe takes it off every invoice
    in those months, so no yearly switch is offered then (a year's charge
    would get it too)."""
    taken = _parse(_get(org, "save_offer_used_at"))
    if taken is None:
        return False
    months = int(cfg.get("SAVE_OFFER_MONTHS") or 0)
    return add_months(taken, max(months, 1)) > (now or datetime.now(timezone.utc))


def discounted(dollars, percent):
    """A monthly price with percent off, to the cent."""
    return round(dollars * (100 - percent) / 100, 2)


def bundle_upgrade_dollars(interval=MONTH):
    """What a bundle workspace pays for Plus: only the difference (a year
    of it costs MONTHS_PAID_YEARLY months, like every yearly price)."""
    monthly = PLUS.dollars - BUNDLE_INCLUDES.dollars
    return yearly_dollars(monthly) if interval == YEAR else monthly


def bundle_upgrade_setting(interval=MONTH):
    return BUNDLE_UPGRADE_YEARLY_SETTING if interval == YEAR else BUNDLE_UPGRADE_SETTING


def current_plans():
    """The plans by key, as they are now (PLANS is fixed at import)."""
    return {p.key: p for p in (PRO, PLUS)}


def yearly_offered(cfg):
    """Which plans can be paid yearly: those whose yearly Stripe price is set."""
    offered = {p.key: bool(p.yearly_price_setting and cfg.get(p.yearly_price_setting))
               for p in (PRO, PLUS)}
    offered["bundle_upgrade"] = bool(cfg.get(BUNDLE_UPGRADE_YEARLY_SETTING))
    offered["any"] = any(offered.values())
    return offered


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
    Kryozyn report: 'covered', 'grace', 'lapsed' or 'none', with the dates."""
    now = now or datetime.now(timezone.utc)
    last = _parse(_get(org, "bundle_report_at"))
    if last is None:
        return {"state": "none", "last": None, "covered_until": None, "grace_ends": None}
    covered_until = last + BUNDLE_FRESH
    grace_ends = covered_until + BUNDLE_GRACE
    state = "covered" if now <= covered_until else "grace" if now <= grace_ends else "lapsed"
    return {"state": state, "last": last, "covered_until": covered_until, "grace_ends": grace_ends}


def _days_left(ends, now):
    return max(1, -(-int((ends - now).total_seconds()) // 86400))


def pilot_status(org, now=None):
    """The workspace's classroom pilot: 'none' (never started), 'active' or
    'ended', with its dates and the days left."""
    now = now or datetime.now(timezone.utc)
    started = _parse(_get(org, "pilot_started_at"))
    ends = _parse(_get(org, "pilot_ends_at"))
    if started is None or ends is None:
        return {"state": "none", "started": None, "ends": None, "days_left": 0}
    if ends > now:
        return {"state": "active", "started": started, "ends": ends, "days_left": _days_left(ends, now)}
    return {"state": "ended", "started": started, "ends": ends, "days_left": 0}


def class_limits(org, now=None):
    """What the workspace can do with classes right now: the plan it comes
    from ('school', 'classroom', 'pilot' or None), how many classes
    (max_classes, None for no limit) and how many students in each."""
    a = access(org, now)
    if a["classroom"]:
        plan = CLASSROOM_PLANS[a["kind"]]
        return {"source": plan.key, "name": plan.name, "max_classes": plan.max_classes, "class_size": CLASS_SIZE,
                "active": True, "pilot": pilot_status(org, now)}
    pilot = pilot_status(org, now)
    if pilot["state"] == "active" and not a["paused"]:
        return {"source": "pilot", "name": "Free classroom trial", "max_classes": PILOT_CLASSES,
                "class_size": CLASS_SIZE, "active": True, "pilot": pilot}
    return {"source": None, "name": None, "max_classes": 0, "class_size": CLASS_SIZE, "active": False,
            "pilot": pilot}


def classroom_checkout(cfg, plan_key):
    """A classroom plan's checkout: (kind, Stripe price id, dollars). An
    empty price id means it can't be bought online (an invoice instead)."""
    plan = CLASSROOM_PLANS[plan_key]
    return plan.key, cfg.get(plan.price_setting) or "", plan.yearly_dollars


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
    hand_end = _parse(_get(org, "academy_ends_at"))
    if paid and not _get(org, "stripe_subscription_id") and hand_end is not None and hand_end <= now:
        # A plan set by hand with an end date (an invoiced school year, or a
        # hand plan cancelled to its renewal date) is over on that date.
        paid, state = False, "canceled"
    resumes = _parse(_get(org, "paused_until"))
    # Paused with no end date in Stripe (pause_open): paused until Stripe resumes it.
    pause_open = bool(_get(org, "pause_open")) and resumes is None
    paused = paid and (pause_open or (resumes is not None and resumes > now))
    if paid and kind not in KINDS:
        # A paid subscription that never said which plan it is began before
        # Pro and Plus (every checkout since names its plan): the old Academy plan.
        kind = "academy"
    name, sub_tracker, sub_academy = KINDS.get(kind, (None, False, False))
    if not paid or paused:
        # A paused plan gives nothing until it starts again, like no plan.
        sub_tracker = sub_academy = False
    bundle = bundle_status(org, now)
    ends = trial_ends(org, trial_days)
    in_trial = ends is not None and ends > now and not paused
    interval = _get(org, "plan_interval")
    trial_days_left = max(1, -(-int((ends - now).total_seconds()) // 86400)) if in_trial else 0
    pilot = pilot_status(org, now)
    in_pilot = pilot["state"] == "active" and not paused
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
    if source is None and paused:
        reason = "paused"
    elif source is None and paid and kind in CLASSROOM_PLANS:
        reason = "academy_only"        # Classroom: the Academy for a class, not the tracker
    elif source is None:
        reason = "bundle_ended" if bundle["state"] == "lapsed" else "plan_ended" if kind != "none" else "trial_ended"
        if reason == "trial_ended" and _get(org, "created_at") and _get(org, "academy_trial_ends") == _get(
                org, "created_at"):
            # A location added later: its trial ended the moment it was made
            # (the trial is one per owner, views.add_location), so no plan yet.
            reason = "new_location"
    else:
        reason = None
    return {
        "tracker": source is not None,
        "academy": sub_academy or in_trial or in_pilot,
        "read_only": source is None,
        "reason": reason,              # why it is read-only (academy_only: a Classroom plan)
        "source": source,              # where the tracker comes from
        "kind": kind, "plan_name": name, "state": state, "paid": paid,
        "interval": interval if interval in INTERVALS else MONTH,
        "yearly": paid and interval == YEAR,
        "subscribed": paid,            # a subscription that counts: checkout won't start a second
        "trial": in_trial, "trial_days": trial_days_left, "trial_ends": ends,
        "bundle": bundle,
        "renews_at": None if _get(org, "academy_ends_at") else _get(org, "academy_renews_at"),
        "ends_at": _get(org, "academy_ends_at") if paid else None,
        "legacy": paid and kind == "academy",
        "paused": paused,              # paused: no charge, read-only, until resumes_at
        "resumes_at": resumes if paused and not pause_open else None,
        "pause_open": paused and pause_open,   # paused in Stripe with no end date
        "paused_at": _get(org, "paused_at") if paused else None,
        "pilot": in_pilot,             # the free classroom trial gives the whole Academy
        "pilot_ends": pilot["ends"],
        "pilot_days": pilot["days_left"] if in_pilot else 0,
        "classroom": kind in CLASSROOM_PLANS and paid and not paused,
    }


def checkout_choice(cfg, org, plan_key, interval=MONTH, now=None):
    """What checking out for a plan, paid monthly or yearly, buys this
    workspace: (kind, Stripe price id, dollars). Plus for a workspace the
    Kitchen Safety Bundle covers is billed only the difference, when that
    interval's price is set up; otherwise at its full price (the plan page
    says so). An empty price id means that plan isn't offered that way."""
    plan = current_plans()[plan_key]
    upgrade = bundle_upgrade_setting(interval)
    if plan is PLUS and bundle_status(org, now)["state"] == "covered" and cfg.get(upgrade):
        return "plus_bundle", cfg[upgrade], bundle_upgrade_dollars(interval)
    return plan.key, cfg.get(plan.setting(interval)) or "", plan.dollars_for(interval)


def monthly_dollars(kind):
    """What a plan kind costs a month, or None for the old Academy plan
    (its old price lives only in Stripe)."""
    if kind in PLANS:
        return current_plans()[kind].dollars
    if kind == "plus_bundle":
        return bundle_upgrade_dollars()
    return None


def cancel_options(cfg, org, now=None):
    """What the cancel screen offers this workspace: pausing (a monthly plan,
    not past due, not already cancelled or paused), the one-time save offer
    (the same, with a Stripe subscription, a coupon set and the offer never
    taken), and cancelling (any paid plan not already cancelled)."""
    a = access(org, now)
    online = bool(_get(org, "stripe_subscription_id"))
    stripe_ok = not online or bool(cfg.get("STRIPE_SECRET_KEY"))
    going = a["paid"] and a["state"] != "past_due" and not a["ends_at"]
    monthly = a["interval"] == MONTH
    terms = save_offer_terms(cfg)
    dollars = monthly_dollars(a["kind"])
    can_save = bool(going and monthly and not a["paused"] and online and stripe_ok and terms
                    and terms[0] > 0 and terms[1] > 0 and not _get(org, "save_offer_used_at"))
    return {
        "access": a,
        "can_pause": bool(going and monthly and not a["paused"] and a["kind"] in PAUSABLE_KINDS and stripe_ok),
        "pause_months": PAUSE_MONTHS,
        "can_resume": a["paused"] and stripe_ok,
        "can_save": can_save,
        "save_used": bool(_get(org, "save_offer_used_at")),
        "save_percent": terms[0] if terms else None,
        "save_months": terms[1] if terms else None,
        "price_now": price_label(dollars, per=False) if dollars else None,
        "price_saved": price_label(discounted(dollars, terms[0]), per=False) if dollars and terms else None,
        "can_cancel": a["paid"] and not a["ends_at"] and stripe_ok,
        "can_keep": a["paid"] and bool(a["ends_at"]) and online and stripe_ok,
        "online": online,
    }
