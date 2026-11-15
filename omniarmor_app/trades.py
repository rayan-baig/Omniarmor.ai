# -*- coding: utf-8 -*-
"""Pages for trades that don't have an industry of their own in the catalog
(/for/<slug>): salons and barbershops, tattoo and piercing studios, gyms and
fitness studios, and shops.

Each page is honest about what OmniArmor does for that trade today: which of
its industries' checklists fit, and which checks in them (named by their
catalog keys, so the titles, rules and limits are the catalog's own and a
test checks every key exists), which of those come with reminder emails, and
what the trade also keeps track of that OmniArmor doesn't cover. Prices come
from plans.py like every other page. No page promises compliance or gives
legal advice, and none quotes statistics, testimonials or other companies.

Trades that already have an industry page (restaurants, child care,
pharmacies, dental and medical practices, bars, hotels) are linked, not
repeated (EXISTING).
"""

from dataclasses import dataclass

from .catalog import INDUSTRIES, date_mode, find_rule
from .reminders import REMINDER_DAYS


@dataclass(frozen=True)
class Trade:
    slug: str
    name: str                 # "Salons and barbershops"
    one: str                  # "a salon or barbershop"
    title: str                # the page's <title>, before " · OmniArmor.ai"
    description: str          # its meta description
    intro: str
    groups: tuple             # ((industry id, (rule keys...), note or ""), ...)
    outside: str              # what OmniArmor doesn't cover for this trade


TRADES = (
    Trade(
        slug="salons-and-barbershops",
        name="Salons and barbershops",
        one="a salon or barbershop",
        title="Salon and barbershop checklists and reminders",
        description=("Checklists and reminders for salons and barbershops: paying your team right, new-hire"
                     " forms and safe card payments, with an email before anything is due."),
        intro=("Behind every chair there's paperwork: paying your team right, new-hire forms, and keeping card"
               " payments safe. OmniArmor keeps those checklists in one place and emails you before something"
               " is due, so it doesn't slip in a busy week."),
        groups=(
            (30, ("i9_section_2", "overtime_pay", "minimum_wage", "hours_records"),
             "For a shop with employees. Some checks in this checklist are for bigger employers (health plans,"
             " family leave); leave those blank if they don't apply to you."),
            (32, ("no_sad_storage", "pan_unreadable", "annual_pci_validation"), ""),
        ),
        outside=("Shop and stylist licenses, and the cleaning and disinfecting rules for your tools, come from"
                 " your state board. OmniArmor doesn't have a checklist for those yet, so keep them on your"
                 " own list."),
    ),
    Trade(
        slug="tattoo-and-piercing-studios",
        name="Tattoo and piercing studios",
        one="a tattoo or piercing studio",
        title="Tattoo and piercing studio checklists and reminders",
        description=("Checklists and reminders for tattoo and piercing studios: sterilizer tests, the exposure"
                     " control plan review, hepatitis B vaccine offers and card payments, with reminder emails."),
        intro=("Clean needles and a working sterilizer are the job. So is the paperwork that proves it: the"
               " sterilizer's spore tests, a yearly look at your plan for blood exposure, and the vaccine offer"
               " for new artists. OmniArmor counts the days for you and emails before each one is due."),
        groups=(
            (27, ("sterilizer_spore_test", "exposure_control_plan", "hepb_vaccine_offer", "hazard_communication"),
             "These come from the Dental & Medical Practices checklist and are for studios with employees. The"
             " sterilizer test's limit is a policy you can change to match your health department. That"
             " checklist also has billing and patient-record checks a studio can leave blank."),
            (30, ("i9_section_2", "overtime_pay", "hours_records"), "For a studio with employees."),
            (32, ("no_sad_storage", "annual_pci_validation"), ""),
        ),
        outside=("Studio and artist permits, and your health department's own rules, differ from city to city"
                 " and state to state. OmniArmor doesn't have a checklist for those yet, so keep them on your"
                 " own list."),
    ),
    Trade(
        slug="gyms-and-fitness-studios",
        name="Gyms and fitness studios",
        one="a gym or fitness studio",
        title="Gym and fitness studio checklists and reminders",
        description=("Checklists and reminders for gyms and fitness studios: staff pay, card payments,"
                     " memberships sold online with an easy way to cancel, and marketing emails and texts."),
        intro=("Memberships renew every month, and so does the paperwork: paying trainers and front-desk staff"
               " right, keeping card payments safe, and selling memberships online with clear terms and an easy"
               " way to cancel. OmniArmor keeps those checklists in one place and reminds you before something"
               " is due."),
        groups=(
            (30, ("i9_section_2", "overtime_pay", "minimum_wage", "hours_records", "hospitalization_report_24h"),
             "For a gym with employees. Leave blank the checks for bigger employers that don't apply to you."),
            (32, ("no_sad_storage", "pan_unreadable", "annual_pci_validation"), ""),
            (50, ("rosca_subscriptions", "email_optout_10_days", "sms_marketing_consent"),
             "For memberships sold online and for marketing emails and texts. The rest of the E-commerce"
             " checklist is about products, so a gym can leave it blank."),
        ),
        outside=("Pools and hot tubs, first-aid equipment and your own state's membership contract rules are set"
                 " where you are. OmniArmor doesn't have a checklist for those yet, so keep them on your own"
                 " list."),
    ),
    Trade(
        slug="shops-and-retail-stores",
        name="Shops and retail stores",
        one="a shop",
        title="Shop and retail store checklists and reminders",
        description=("Checklists and reminders for shops and retail stores: staff pay and new-hire forms, card"
                     " payments and surcharges, and orders, reviews and emails if you also sell online."),
        intro=("A shop has a till, a team and, more and more, a website. Each comes with a checklist: paying"
               " staff right, keeping card payments safe, and shipping online orders on time. OmniArmor keeps"
               " them in one place and emails you before something is due."),
        groups=(
            (30, ("i9_section_2", "overtime_pay", "minimum_wage", "hours_records"),
             "For a shop with employees. Leave blank the checks for bigger employers that don't apply to you."),
            (32, ("no_sad_storage", "pan_unreadable", "surcharge_cap", "annual_pci_validation"), ""),
            (50, ("ship_or_notify_30_days", "no_fake_reviews", "email_optout_10_days"),
             "If you also sell online."),
        ),
        outside=("Business licenses, sales tax for your shop's own state, and rules for what you sell (alcohol,"
                 " tobacco, food) are set where you are. OmniArmor has separate checklists for bars and liquor"
                 " and for firearms dealers; it doesn't cover the others yet."),
    ),
)
BY_SLUG = {t.slug: t for t in TRADES}

# Trades that already have an industry page of their own: (name, industry id).
EXISTING = (
    ("Restaurants", 2), ("Daycares and child care", 45), ("Pharmacies", 28), ("Dental and medical offices", 27),
    ("Bars, breweries and liquor stores", 47), ("Hotels and lodging", 46),
)


def describe(rule):
    """How OmniArmor keeps track of a check, in plain words."""
    mode = date_mode(rule)
    if mode is not None:
        return "dated", "Dated · reminder emails"
    if rule.kind in ("required", "forbidden"):
        return "answer", "Yes or no"
    return "reading", "A number with a limit"


def groups(trade):
    """The trade's checklists: each industry, its checks (catalog rules) and
    its note."""
    out = []
    for industry_id, keys, note in trade.groups:
        rules = [find_rule(industry_id, key) for key in keys]
        out.append({"industry": INDUSTRIES[industry_id], "note": note,
                    "checks": [{"rule": r, "how": describe(r)} for r in rules]})
    return out


def facts(trade):
    """What the page says about reminders, read from reminders.py."""
    dated = sum(1 for industry_id, keys, _ in trade.groups for key in keys
                if date_mode(find_rule(industry_id, key)) is not None)
    return {"reminder_days": REMINDER_DAYS, "dated": dated,
            "industry_ids": [i for i, _, _ in trade.groups]}
