# -*- coding: utf-8 -*-
"""Pilot, the MTRX Horizyn assistant, on OmniArmor (docs/PILOT.md).

Pilot runs in the visitor's browser on their own AI key and talks to the AI
provider they chose, straight from the browser: this server never sees the
key or the conversation, and has no Pilot address of its own. This module
says only three things:

- which addresses the browser may reach for it (the security policy's
  connect-src, in security.py), exactly the MTRX Horizyn site's list;
- which pages carry it: the public pages for grown-ups, a business's pages
  and a teacher's pages. Never a page a student uses (the Academy's
  lessons, map, results and the kids' join page): students are children,
  and Pilot is for the adults who run the workspace;
- the plain facts its knowledge pack may quote (prices and numbers read
  from plans.py and the settings, so Pilot never invents one).
"""

import hashlib
import hmac
import os

from flask import current_app, g, request, url_for

PROVIDER_HOSTS = ("api.anthropic.com", "api.openai.com", "generativelanguage.googleapis.com")
COMPATIBLE_HOSTS = ("openrouter.ai", "api.groq.com", "api.mistral.ai", "api.deepseek.com", "api.together.xyz",
                    "api.fireworks.ai", "api.x.ai")
LOCAL_HOSTS = ("localhost", "127.0.0.1")
CONNECT = " ".join([f"https://{h}" for h in PROVIDER_HOSTS + COMPATIBLE_HOSTS] + [f"http://{h}:*" for h in LOCAL_HOSTS])

# The pages Pilot is on, by endpoint. Anything not listed here has no Pilot.
PUBLIC_PAGES = frozenset({"public.home", "public.industries", "public.industry_page", "public.trade_page",
                          "public.academy_schools", "public.class_guide", "demo.index"})
BUSINESS_PAGES = frozenset({"app.overview", "app.industry", "app.report", "app.audit", "app.notifications",
                            "app.settings", "plan.plan_page"})
# A teacher's: their classes, one class's page and its join codes, the teacher
# guide, and the school checklist's pages.
TEACHER_PAGES = frozenset({"classes.index", "classes.class_page", "classes.join_codes", "public.class_guide",
                           "app.overview", "app.industry", "app.report", "app.notifications", "app.audit",
                           "app.settings", "plan.plan_page"})
# Never, whoever is signed in: every page a student uses, and the kids' join page.
STUDENT_BLUEPRINTS = ("academy.", "kids.")


# The moving robot's pose pictures (core 1.1.0): every <pose>.webp or .png in
# static/pilot/poses/ whose name is one of these, so a new pose is added just
# by putting its picture there. The same list as the MTRX Horizyn site's.
POSES = ("standing", "sitting", "wave", "walk1", "walk2", "run1", "run2", "fly", "climb1", "climb2", "flip",
         "throw", "kick", "tennis", "celebrate", "slide", "point", "power", "dash", "love", "land", "arms-crossed")


def pose_files(folder=None):
    """{pose: file name} for the pose pictures there are (WebP wins over PNG)."""
    found = {}
    try:
        names = sorted(os.listdir(folder or os.path.join(current_app.static_folder, "pilot", "poses")))
    except OSError:
        return found
    for name in names:
        stem, _, ext = name.partition(".")
        if stem in POSES and ext in ("webp", "png") and (stem not in found or ext == "webp"):
            found[stem] = name
    return found


def poses():
    """The pose pictures, as "name=address name=address" for the tag's
    data-poses. The browser fetches one only when a move first needs it."""
    return " ".join(f"{pose}={url_for('static', filename='pilot/poses/' + name)}"
                    for pose, name in pose_files().items())


def audience():
    """Who Pilot would be talking to on this page: "visitor", "business" or
    "teacher", or None where Pilot never goes (a student's page, a kid's
    device, an error page, or a page not listed above)."""
    endpoint = request.endpoint or ""
    if g.get("kid") is not None or endpoint.startswith(STUDENT_BLUEPRINTS) or endpoint == "classes.my_class":
        return None
    if g.get("user") is not None and g.get("org") is not None:
        from .classrooms import is_class_workspace
        if is_class_workspace(g.org):
            return "teacher" if endpoint in TEACHER_PAGES else None
        return "business" if endpoint in BUSINESS_PAGES else None
    if endpoint in PUBLIC_PAGES:
        return "visitor"
    return None


def account_marker():
    """An opaque mark for who is signed in, so Pilot can forget a chat when
    the account changes in a tab (someone signs out, or a kid uses the
    device next). It is a keyed hash: it says nothing about the account."""
    user, org = g.get("user"), g.get("org")
    if user is None or org is None:
        return ""
    raw = f"{'demo' if g.get('demo') else 'live'}:{user['id']}:{org['id']}".encode()
    return hmac.new(current_app.config["SECRET_KEY"].encode(), raw, hashlib.sha256).hexdigest()[:16]


def facts(who):
    """What Pilot's script tag tells the config and the knowledge pack:
    the audience, and the plans' real names and prices. Nothing about any
    person or any record."""
    from . import classrooms, plans
    from .academy_views import JOIN_CODE_DAYS
    from .catalog import TOP_COUNT
    from .plan_views import plan_facts
    from .reminders import REMINDER_DAYS
    cfg = current_app.config
    pf = plan_facts(cfg)
    cf = classrooms.public_facts(cfg)
    access = plans.access(g.org) if g.get("org") is not None else None
    data = {
        "trial_days": pf["trial_days"],
        "pro": pf["pro"].name, "pro_price": pf["pro"].price,
        "plus": pf["plus"].name, "plus_price": pf["plus"].price,
        "pro_yearly": pf["pro"].yearly_short if pf["yearly"]["pro"] else "",
        "plus_yearly": pf["plus"].yearly_short if pf["yearly"]["plus"] else "",
        "free_label": pf["free_label"],
        # The bundle's prices, not its name: pages name the bundle only where it fits (restaurants).
        "bundle_price": pf["bundle"]["price"],
        "bundle_upgrade": pf["bundle"]["upgrade_price"],
        "classroom": cf["classroom"].name, "classroom_price": cf["classroom"].yearly_price,
        "classroom_summary": cf["classroom"].summary,
        "school": cf["school"].name, "school_price": cf["school"].yearly_price,
        "school_summary": cf["school"].summary,
        "pilot_days": cf["pilot_days"], "class_size": cf["class_size"],
        "class_worlds": cf["class_worlds"], "class_lessons": cf["class_lessons"],
        "lesson_questions": cf["lesson_questions"], "lesson_minutes": cf["lesson_minutes"],
        "class_business": cf["class_business"],
        "industries": pf["industries"], "checks": pf["checks"], "top_count": TOP_COUNT,
        "reminder_days": list(REMINDER_DAYS), "max_learners": pf["max_learners"],
        "support": pf["support_email"],
        # 1.17.0: for the answers Pilot gives with no AI key (join codes).
        "join_code_days": JOIN_CODE_DAYS, "join_path": url_for("kids.join"),
        # 1.18.0: also "Which plan fits me?" (the plans' own words) ...
        "pro_summary": "the compliance tracker: every check, reminder emails, reports and exports, and your whole team",
        "plus_summary": "everything in Pro, and the whole Future Owner Academy for your kids at no extra cost",
        "security_path": url_for("public.security"),
    }
    # ... "Which checklist fits me?" (the trades the industry list leads with,
    # each with its page, then the other trade pages) ...
    if who == "visitor":
        from .trades import TRADES, lead_trades
        listed = [{"name": name, "path": url_for(endpoint, **args)} for name, endpoint, args, _ in lead_trades()]
        paths = {t["path"] for t in listed}
        listed += [{"name": t.name, "path": url_for("public.trade_page", slug=t.slug)} for t in TRADES
                   if url_for("public.trade_page", slug=t.slug) not in paths]
        data["trades"] = listed
    # ... and "Plan a week of lessons": the Classroom track's worlds in order,
    # with their lessons and a question to talk about (the teacher guide's).
    if who == "teacher" or (who == "visitor" and (request.endpoint or "").startswith(("public.academy_schools",
                                                                                     "public.class_guide"))):
        from .academy import LESSON_MINUTES, class_guide
        data["class_plan"] = [{"title": item["world"].title, "lessons": item["lessons"], "talk": item["talk"][0]}
                              for item in class_guide()]
        data["lesson_minutes"] = LESSON_MINUTES
    # The checklists this workspace keeps (names and page numbers only), for
    # the tools that read its own pages. Never sent to the AI by itself.
    checklists = []
    if g.get("org") is not None and who in ("business", "teacher"):
        from .catalog import INDUSTRIES
        from .db import get_db
        from .tracking import checklist_ids
        # A teacher without Whole school has no school checklist (checklist_ids).
        checklists = [{"id": i, "name": INDUSTRIES[i]["brand"]} for i in checklist_ids(get_db(), g.org)]
    # A teacher's classes (names and page numbers only, never a student), so
    # "Print certificates" and "How do join codes work?" can go straight to a
    # class's own page with no AI key (1.17.0).
    classes = []
    if who == "teacher":
        data["school_checklist"] = bool(checklists)
        from .db import get_db
        classes = [{"id": c["id"], "name": c["name"]} for c in classrooms.classes(get_db(), g.org["id"])]
    return {
        "who": who,
        "checklists": checklists,
        "classes": classes,
        "demo": "on" if g.get("demo") else "off",
        "readonly": "on" if access is not None and access["read_only"] else "off",
        "account": account_marker(),
        "hosts": " ".join(COMPATIBLE_HOSTS + LOCAL_HOSTS),
        "poses": poses(),
        "facts": data,
    }


def pilot_tag():
    """The facts for templates/_pilot.html, or None where Pilot isn't shown
    (worked out once a request: Armo's bubble asks too, for "Ask Pilot")."""
    if "pilot_tag" not in g:
        who = audience()
        g.pilot_tag = facts(who) if who else None
    return g.pilot_tag
