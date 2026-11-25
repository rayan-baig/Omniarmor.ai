# -*- coding: utf-8 -*-
"""OmniArmor.ai web app. Catch the fine before it catches you.

create_app() builds the app; wsgi.py runs it in production.
"""

import hmac
import logging
import os
import sqlite3
import time
from datetime import timedelta

import click
from flask import (Blueprint, Flask, Response, abort, current_app, g, jsonify, redirect, render_template, request,
                   send_from_directory, url_for)
from markupsafe import escape
from werkzeug.exceptions import InternalServerError, ServiceUnavailable
from werkzeug.middleware.proxy_fix import ProxyFix

from . import (academy_views, armo_views, autopilot, auth, classroom_views, compress, connections, demo_mode,
               errormail, health, pilot, plan_views, usage, views)
from . import names
from .catalog import INDUSTRIES, industry_by_slug, rules_for, top_checks, why_line
from .config import SettingsError, load_config, support_email
from .db import SCHEMA_VERSION, close_db, connect, get_db, migrate, utcnow
from .jobs import register_cli, start_scheduler
from . import shots
from .redact import RedactingFilter, redact
from .security import check_csrf, csrf_token, home_url, load_user, old_host_redirect, security_headers
from .tracking import format_quantity, local_date
from .version import __version__
from .words import plural, plural_word

SLOGAN = "Catch the fine before it catches you."

public = Blueprint("public", __name__)


@public.route("/")
def home():
    if g.get("user") is not None:
        return redirect(home_url())
    if g.get("kid") is not None:
        return redirect(url_for("academy.level_map", learner_id=g.kid["id"]))
    from .trades import lead_trades
    return render_template("home.html", industries=INDUSTRIES, facts=_landing_facts(), lead=lead_trades())


# Industries named on the landing page as examples of who OmniArmor is for.
LANDING_EXAMPLES = (2, 1, 29, 45, 5, 28)


def _landing_facts():
    """Every number the landing page shows, read from the code that sets it:
    the catalog, the Academy's tracks and plan, and the settings."""
    from .academy import TRACK_LIST
    from .academy_plan import FREE_TRACK, FREE_WORLDS
    from .reminders import REMINDER_DAYS
    cfg = current_app.config
    return {
        "industries": len(INDUSTRIES),
        "checks": sum(len(rules_for(i)) for i in INDUSTRIES),
        "per_industry": len(rules_for(next(iter(INDUSTRIES)))),
        "examples": [INDUSTRIES[i]["sector"].lower() for i in LANDING_EXAMPLES],
        "reminder_days": REMINDER_DAYS,
        "trial_days": cfg["ACADEMY_TRIAL_DAYS"],
        "free_worlds": len(FREE_WORLDS),
        "free_track": next(t.name for t in TRACK_LIST if t.key == FREE_TRACK),
        "tracks": len(TRACK_LIST),
        "fewest_levels": min(t.lessons for t in TRACK_LIST),
        "most_levels": max(t.lessons for t in TRACK_LIST),
    }


@public.route("/industries")
def industries():
    from .trades import EXISTING, LEAD_TRADES, TRADES, lead_trades
    lead_slugs = {ref for _, kind, ref in LEAD_TRADES if kind == "trade"}
    lead_ids = {ref for _, kind, ref in LEAD_TRADES if kind == "industry"}
    return render_template("industries.html", industries=INDUSTRIES, lead=lead_trades(),
                           trades=[t for t in TRADES if t.slug not in lead_slugs],
                           existing=[(name, INDUSTRIES[i]) for name, i in EXISTING if i not in lead_ids])


@public.route("/industries/<slug>")
def industry_page(slug):
    """A landing page per industry, so each niche finds a page about its own risks."""
    match, old = industry_by_slug(slug)
    if match is None:
        abort(404)
    if old or slug != match["slug"]:
        # An address from 1.24.0 or 1.25.0 ("/industries/resto-aegizyn"), or in other letters: one address.
        return redirect(url_for("public.industry_page", slug=match["slug"]), code=301)
    top = top_checks(match["id"])
    rest = [r for r in rules_for(match["id"]) if r not in top]
    from .connections import TEMPERATURE_CHECKS
    return render_template("industry_public.html", info=match, top=top, rest=rest, why_line=why_line,
                           bundle_industry=any(i == match["id"] for i, _ in TEMPERATURE_CHECKS))


@public.route("/for/<slug>")
def trade_page(slug):
    """A page per trade without an industry of its own (trades.py): the
    checklists that fit it, honestly, and the price."""
    from . import trades
    trade = trades.BY_SLUG.get(slug.lower())
    if trade is None:
        abort(404)
    if slug != trade.slug:
        return redirect(url_for("public.trade_page", slug=trade.slug), code=301)
    from .demo_mode import TRADE_DEMO_FOR, TRADE_DEMOS
    # Each trade page's demo is that trade's own (a salon's opens a salon).
    demo_kind = TRADE_DEMO_FOR.get(trade.slug, "business")
    demo_name = TRADE_DEMOS[demo_kind][3].lower() if demo_kind in TRADE_DEMOS else "a restaurant"
    return render_template("trade.html", trade=trade, groups=trades.groups(trade), facts=trades.facts(trade),
                           sister_url=names.FRIDGE_URL, demo_kind=demo_kind, demo_name=demo_name)


@public.route("/classrooms")
def academy_schools():
    """The Future Owner Academy for schools and teachers: classes, the class
    progress view, certificates, the free pilot and the classroom prices."""
    from . import classrooms
    return render_template("academy_schools.html", facts=classrooms.public_facts(current_app.config))


@public.route("/classrooms/guide")
def class_guide():
    """The teacher guide, to read or print: what each world of the Classroom
    track teaches, how long it takes and questions to talk about."""
    from . import academy, classrooms
    return render_template("class_guide.html", guide=academy.class_guide(),
                           facts=classrooms.public_facts(current_app.config))


# The date the Terms and Privacy pages last changed. Update it with them.
RULES_UPDATED = "20 November 2026"
# The date the Security and your data page last changed (1.18.0).
SECURITY_UPDATED = "22 November 2026"


def _rules_facts():
    """The numbers the Terms and Privacy pages quote, read from the code that
    sets them, so the pages stay true when a setting changes."""
    from .academy import FRIEND_CODE_DAYS
    from .academy_plan import FREE_WORLDS
    from .academy_views import JOIN_CODE_DAYS, QUIZ_CHECK_DAYS
    from .autopilot import KEEP_ERRORS, MAX_EMAILS_PER_HOUR
    from .errormail import MAX_PER_DAY
    from .jobs import ALERTS_EVERY_SECONDS, offsite_ok
    from .auth import INVITE_DAYS, RESET_HOURS
    from .connections import SIGNATURE_MEMORY
    from .plans import PAUSE_MONTHS
    cfg = current_app.config
    return {
        "updated": RULES_UPDATED,
        "trial_days": cfg["ACADEMY_TRIAL_DAYS"],
        "free_worlds": len(FREE_WORLDS),
        "backup_keep": cfg["BACKUP_KEEP"],
        "offsite_backup": offsite_ok(cfg),
        "session_days": cfg["PERMANENT_SESSION_LIFETIME"].days,
        "reset_hours": RESET_HOURS,
        "invite_days": INVITE_DAYS,
        "join_code_days": JOIN_CODE_DAYS,
        "friend_code_days": FRIEND_CODE_DAYS,
        "quiz_check_days": QUIZ_CHECK_DAYS,
        "error_days": KEEP_ERRORS.days,
        "operator_emails_per_hour": MAX_EMAILS_PER_HOUR,
        "error_emails_per_day": MAX_PER_DAY,
        "alert_minutes": max(1, ALERTS_EVERY_SECONDS // 60),
        "signature_minutes": int(SIGNATURE_MEMORY.total_seconds() // 60),
        "pause_most": max(PAUSE_MONTHS),
        "support_email": support_email(cfg),
        "security_updated": SECURITY_UPDATED,
    }


@public.route("/privacy")
def privacy():
    return render_template("privacy.html", facts=_rules_facts())


@public.route("/security", endpoint="security")
def security_page():
    """Security and your data (1.18.0): where the data lives, backups, who can
    see a student's name, how to delete it and who to write to."""
    return render_template("security.html", facts=_rules_facts())


@public.route("/terms")
def terms():
    return render_template("terms.html", facts=_rules_facts())


def _help_facts():
    """The numbers and names the Help page quotes, read from the code and
    settings that decide them, like the plan page's."""
    from .academy_views import JOIN_CODE_DAYS
    from .auth import RESET_HOURS
    from .plan_views import plan_facts
    from .autopilot import SLOT_MINUTES
    from .catalog import TOP_COUNT
    from .jobs import ALERTS_EVERY_SECONDS, offsite_ok
    from .plans import PAUSE_MONTHS, RESUME_NOTICE
    from .reminders import REMINDER_DAYS
    cfg = current_app.config
    facts = plan_facts(cfg)
    facts.update({
        "per_industry": len(rules_for(next(iter(INDUSTRIES)))),
        "top_count": TOP_COUNT,
        "reminder_days": REMINDER_DAYS,
        "daily_hour_utc": cfg["DAILY_JOB_HOUR_UTC"],
        "alert_minutes": max(1, ALERTS_EVERY_SECONDS // 60),
        "autopilot_minutes": SLOT_MINUTES,
        "backup_keep": cfg["BACKUP_KEEP"],
        "offsite_backup": offsite_ok(cfg),
        "reset_hours": RESET_HOURS,
        "join_code_days": JOIN_CODE_DAYS,
        "support_email": support_email(cfg),
        "pause_months": PAUSE_MONTHS,
        "resume_notice_days": RESUME_NOTICE.days,
    })
    return facts


@public.route("/help", endpoint="help")
def help_page():
    usage.count(get_db(), "help_views")
    return render_template("help.html", facts=_help_facts())


@public.route("/pricing", endpoint="pricing")
def pricing():
    """The prices as a page of plan cards (1.23.0; 1.22.0 sent /pricing to Help's prices): the business plans, the
    Academy's free part and the school plans, every name and amount from plans.py (plan_facts, the same numbers
    Help, the landing page and the Plans page use), each with a way to start the free trial. Help's #prices stays."""
    from .classrooms import public_facts
    facts = _help_facts()
    return render_template("pricing.html", facts=facts, school=public_facts(current_app.config))


@public.route("/prices")
def prices():
    return redirect(url_for("public.pricing"), code=301)


# The pages anyone can open and search engines may list: the sitemap gives
# them, and they carry share previews (og: and twitter: tags) and a canonical
# address. Every other page is private: marked noindex, and the ones that
# hold a person's or a company's data are closed to crawlers in robots.txt.
PUBLIC_PAGES = {"public.home", "public.industries", "public.industry_page", "public.trade_page",
                "public.academy_schools", "public.class_guide", "public.terms", "public.privacy", "public.security", "public.help", "public.pricing", "auth.signup",
                "auth.login"}
# Addresses that are not pages: they get no noindex header.
NOT_PAGES = {"static", "public.robots", "public.sitemap", "public.favicon", "public.apple_touch_icon", "public.prices"}
# Closed to crawlers: the app (with the Academy and Settings), password reset
# and invite links, the kids' join page, the demos (each opening one counts
# toward its limit) and the addresses only programs use.
# ("/app$" and "/app/", not "/app", which would also close /apple-touch-icon.png.)
ROBOTS_DISALLOW = ("/app$", "/app/", "/reset/", "/signup?invite=", "/forgot", "/kids", "/logout", "/billing/", "/api/",
                   "/healthz", "/readyz", "/demo")


def public_page():
    """Whether the page being drawn is one of PUBLIC_PAGES, as a visitor sees
    it (a sign-up page opened from an invite link is private). None is on a
    copy that is not the live one (NOINDEX)."""
    if current_app.config.get("NOINDEX"):
        return False
    return request.endpoint in PUBLIC_PAGES and not request.args.get("invite")


def canonical_url():
    """This page's one full address, as the sitemap gives it."""
    args = dict(request.view_args or {})
    if request.endpoint == "public.industry_page":
        args["slug"] = args["slug"].lower()
    return current_app.config["BASE_URL"] + url_for(request.endpoint, **args)


def robots_header(response):
    """noindex on everything but the public pages, for crawlers that read
    the header (it also covers the CSV exports, which have no <meta>). With
    NOINDEX, on every address, files and robots.txt included."""
    if current_app.config.get("NOINDEX"):
        response.headers["X-Robots-Tag"] = "noindex, nofollow"
    elif request.endpoint not in NOT_PAGES and not (public_page() and response.status_code == 200):
        response.headers.setdefault("X-Robots-Tag", "noindex, nofollow")
    return response


@public.route("/robots.txt")
def robots():
    if current_app.config.get("NOINDEX"):
        return Response("User-agent: *\nDisallow: /\n", mimetype="text/plain")
    lines = ["User-agent: *", "Allow: /"] + [f"Disallow: {path}" for path in ROBOTS_DISALLOW]
    lines.append("Sitemap: " + current_app.config["BASE_URL"] + "/sitemap.xml")
    return Response("\n".join(lines) + "\n", mimetype="text/plain")


@public.route("/sitemap.xml")
def sitemap():
    base = current_app.config["BASE_URL"]
    paths = [url_for("public.home"), url_for("public.industries")]
    paths += [url_for("public.industry_page", slug=i["slug"]) for i in INDUSTRIES.values()]
    from .trades import TRADES
    paths += [url_for("public.trade_page", slug=t.slug) for t in TRADES]
    paths += [url_for("public.academy_schools"), url_for("public.class_guide")]
    paths += [url_for("public.pricing"), url_for("auth.signup"), url_for("auth.login"), url_for("public.help"),
              url_for("public.terms"),
              url_for("public.privacy"), url_for("public.security")]
    if current_app.config.get("NOINDEX"):
        paths = []
    xml = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    xml += [f"<url><loc>{escape(base + path)}</loc></url>" for path in paths] + ["</urlset>"]
    return Response("\n".join(xml), mimetype="application/xml")


# Browsers and phones ask for these at the site's root, whatever the page
# says. Their address never changes, so browsers keep them for a day, not a year.
@public.route("/favicon.ico")
def favicon():
    return send_from_directory(current_app.static_folder, "favicon.ico", max_age=ROOT_ICON_MAX_AGE)


@public.route("/apple-touch-icon.png")
@public.route("/apple-touch-icon-precomposed.png")
def apple_touch_icon():
    return send_from_directory(current_app.static_folder, "apple-touch-icon.png", max_age=ROOT_ICON_MAX_AGE)


ROOT_ICON_MAX_AGE = 24 * 3600


@public.route("/api/stats")
def stats():
    """User counts and daily feature use for the owner's company
    console, and nothing else.

    Off unless STATS_KEY is set, and answered only to that key. Counts only:
    no names, no companies, nothing about anyone in particular. `usage` is
    the last 30 days of usage.py's daily totals, newest day first.
    """
    key = current_app.config.get("STATS_KEY") or ""
    sent = request.headers.get("Authorization", "")
    if not key:
        abort(404)
    if not hmac.compare_digest(sent.encode(), f"Bearer {key}".encode()):
        return jsonify(error="unauthorized"), 401
    conn = get_db()
    since = (utcnow() - timedelta(days=30)).date().isoformat()
    users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    active = conn.execute("SELECT COUNT(*) FROM users WHERE last_seen_on >= ?", (since,)).fetchone()[0]
    return jsonify(users=users, active_users=active, usage=usage.last_days(conn))


@public.route("/healthz")
def healthz():
    try:
        version = get_db().execute("SELECT MAX(version) FROM schema_version").fetchone()[0]
        ok = version == SCHEMA_VERSION
    except Exception:  # report unhealthy rather than crash the health check
        ok, version = False, None
    # The release and the schema, and nothing else: this answers anyone.
    return jsonify(status="ok" if ok else "error", schema=version, version=__version__), (200 if ok else 503)


@public.route("/readyz")
def readyz():
    """Everything behind the pages, for an uptime monitor (health.py): 200
    when all is well, 503 when something needs a person. Only "ok", "fail"
    or "off" per check; `flask --app wsgi ready` on the server says more."""
    answer, status = health.readiness(current_app.config)
    response = jsonify(answer)
    response.headers["Cache-Control"] = "no-store"
    return response, status


# What each error page says: a title, and what to do about it.
ERROR_PAGES = {
    400: ("That request didn't work", "Go back, reload the page and try again."),
    403: ("You don't have access to that",
          "This page belongs to another account, or only the workspace owner can open it."),
    404: ("Page not found", "That page doesn't exist, or it has moved. Check the address, or start again from"
                            " the home page."),
    405: ("That action isn't allowed here", "Go back, reload the page and try again."),
    413: ("That upload is too large", "Try a smaller file."),
    500: ("Something went wrong on our side", "It's not something you did. We've noted it so it can be fixed."
                                               " Please try again in a minute."),
    503: ("That's unavailable for a moment", "Please try again in a minute."),
}

# The error page when even the error page can't be shown: no template, no
# database, nothing that can fail. It still matches the look (the same
# stylesheet) and leads home.
PLAIN_ERROR_PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex, nofollow"><title>{title} · OmniArmor.ai</title>
<link rel="icon" href="/static/favicon.svg" type="image/svg+xml"><link rel="stylesheet" href="/static/app.css"></head>
<body><main id="main"><div class="wrap"><div class="narrow error-page">
<p class="eyebrow">Error {code}</p><h1>{title}</h1><p class="sub">{description}</p>
<p class="cta"><a class="btn" href="/">Go to the home page</a></p>
</div></div></main></body></html>
"""


# What SQLite says when the database itself is out of reach, not when a query is wrong.
DATABASE_DOWN = ("unable to open", "database is locked", "disk i/o error", "database or disk is full",
                 "readonly database", "file is not a database", "malformed")


class OmniArmorFlask(Flask):
    def log_exception(self, exc_info):
        # Flask's own version writes the page address, which can hold a reset token.
        self.logger.error(f"Exception on {redact(request.path)} [{request.method}]", exc_info=exc_info)


def _set_up_logging():
    """The server log: times in UTC, said so on every line, and every line
    passed through redact_line() (reset, invite and payment links hidden,
    email addresses shortened), whoever wrote it."""
    handler = logging.StreamHandler()
    formatter = logging.Formatter("%(asctime)s UTC %(levelname)s %(name)s: %(message)s")
    formatter.converter = time.gmtime
    handler.setFormatter(formatter)
    logging.basicConfig(level=logging.INFO, handlers=[handler])  # only if nothing set the log up yet
    for each in logging.getLogger().handlers:
        if not any(isinstance(f, RedactingFilter) for f in each.filters):
            each.addFilter(RedactingFilter())


def percent(part, whole, least=0):
    """part of whole as a whole number from 0 to 100, for the .pct-N and
    .grow-N classes (app.css) that stand in for style attributes. Anything
    above nothing shows as at least `least`."""
    if not whole or not part:
        return 0
    return max(least, min(100, round(100 * part / whole)))


def create_app(**overrides):
    cfg = load_config(**overrides)
    app = OmniArmorFlask(__name__, instance_relative_config=False)
    app.config.update(cfg)
    if cfg["TRUSTED_PROXIES"] > 0:
        hops = cfg["TRUSTED_PROXIES"]
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=hops, x_proto=hops, x_host=hops)
    _set_up_logging()

    try:
        conn = connect(app.config["DATABASE"])
        try:
            migrate(conn, app.config["ACADEMY_TRIAL_DAYS"])
        finally:
            conn.close()
    except (sqlite3.Error, OSError) as exc:
        # Said plainly in the server log, rather than a traceback ending in
        # "unable to open database file".
        raise SettingsError(f"OmniArmor can't open its database at {app.config['DATABASE']} (DATABASE_PATH):"
                            f" {exc}. Check that the disk is attached, writable and not full.") from exc

    app.teardown_appcontext(close_db)
    app.before_request(old_host_redirect)
    app.before_request(load_user)
    app.before_request(check_csrf)
    app.before_request(demo_mode.guard)
    app.after_request(security_headers)
    app.after_request(robots_header)
    app.after_request(connections.api_headers)
    app.after_request(compress.gzip_response)
    app.jinja_env.globals.update(csrf_token=csrf_token, home_url=home_url, SLOGAN=SLOGAN, APP_VERSION=__version__,
                                COMPANY=names.COMPANY, ASSISTANT=names.ASSISTANT, NAMES=names.for_pages(),
                                public_page=public_page, canonical_url=canonical_url,
                                plan_facts=lambda: plan_views.plan_facts(current_app.config),
                                pilot_tag=pilot.pilot_tag, kid_footer=academy_views.kid_footer, lesson_view=academy_views.lesson_view, kid_exit_url=academy_views.kid_exit_url,
                                shot=shots.shot, shot_kind=shots.kind_for)
    app.jinja_env.filters["qty"] = lambda value, unit: format_quantity(value, unit)
    app.jinja_env.filters["pct"] = percent
    # "1 warning", "2 warnings" (words.py, 1.18.0): {{ n|plural('warning') }}.
    app.jinja_env.filters["plural"] = plural
    app.jinja_env.filters["plural_word"] = plural_word
    app.jinja_env.filters["local_date"] = lambda text: local_date(text, g.get("org"))

    # Browsers keep CSS, JS and images for a year, so repeat visits cost no
    # bandwidth. Each link carries the file's change time, so a deploy that
    # changes a file gives it a new address and browsers fetch the new one.
    if app.config.get("SEND_FILE_MAX_AGE_DEFAULT") is None:
        app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 365 * 24 * 3600
    static_versions = {}

    @app.url_defaults
    def static_version(endpoint, values):
        if endpoint == "static" and "filename" in values and "v" not in values:
            name = values["filename"]
            if name not in static_versions:
                try:
                    static_versions[name] = int(os.path.getmtime(os.path.join(app.static_folder, name)))
                except OSError:
                    static_versions[name] = 0
            values["v"] = static_versions[name]

    app.register_blueprint(public)
    app.register_blueprint(auth.bp)
    app.register_blueprint(views.bp)
    app.register_blueprint(academy_views.bp)
    app.register_blueprint(academy_views.kids)
    app.register_blueprint(classroom_views.bp)
    app.register_blueprint(plan_views.plan)
    app.register_blueprint(armo_views.bp)
    app.register_blueprint(connections.api)
    app.register_blueprint(demo_mode.bp)
    register_cli(app)

    @app.errorhandler(400)
    @app.errorhandler(403)
    @app.errorhandler(404)
    @app.errorhandler(405)
    @app.errorhandler(413)
    @app.errorhandler(500)
    @app.errorhandler(503)
    def error_page(err):
        code = getattr(err, "code", 500) or 500
        if code == 500:
            cause = getattr(err, "original_exception", None) or err
            autopilot.record_error(app.config, request.path, cause)
            errormail.report(app.config, cause, request.method, request.path)
        title, help_text = ERROR_PAGES.get(code, ERROR_PAGES[500])
        if connections.is_api_request():
            # A program called: it gets JSON, in the shape the API's own errors have.
            error = "payload_too_large" if code == 413 else f"http_{code}"
            return jsonify(ok=False, error=error, message=title), code
        # A message the app wrote for this case (an expired form, say) beats
        # the general one; Werkzeug's own wording, written for developers,
        # never shows. Nothing about a server error ever does.
        description = getattr(err, "description", None)
        if code == 500 or not description or description == getattr(type(err), "description", None):
            description = help_text
        try:
            return render_template("error.html", code=code, title=title, description=description, noindex=True), code
        except Exception:  # the page itself failed: answer with one that can't
            app.logger.exception("couldn't show the error page for %s", code)
            return Response(PLAIN_ERROR_PAGE.format(code=code, title=escape(title), description=escape(description)),
                            status=code, mimetype="text/html"), code

    @app.errorhandler(sqlite3.DatabaseError)
    def database_unavailable(err):
        """The database can't be reached right now (the disk gone, full or
        read-only, or locked past the 30-second wait): "try again in a
        minute", with a 503 a monitor understands, rather than "something
        went wrong". Any other database error is a bug: the 500 page."""
        if not any(sign in str(err).lower() for sign in DATABASE_DOWN):
            app.log_exception((type(err), err, err.__traceback__))   # as Flask does for any other bug
            return error_page(InternalServerError(original_exception=err))
        app.logger.error("database unavailable on %s [%s]: %s", redact(request.path), request.method, err)
        if "locked" in str(err).lower():
            # The database is there, only busy: Autopilot counts these.
            autopilot.record_error(app.config, request.path, err)
        response = app.make_response(error_page(ServiceUnavailable()))
        response.headers["Retry-After"] = "60"
        return response

    if app.config["TESTING"]:
        # A page that always fails, so tests can see the 500 page as a visitor
        # would. Only in tests: no running server has it.
        @app.route("/_test/server-error")
        def _test_server_error():
            raise RuntimeError("test failure at /srv/omniarmor/omniarmor_app/secret.py with SECRET_KEY")

        # One that quotes what the visitor sent in its message, as careless
        # code might, so tests can see none of it reaches an error report.
        @app.route("/_test/server-error-echo", methods=["GET", "POST"])
        def _test_server_error_echo():
            raise ValueError(f"bad input: {request.query_string.decode()} form={request.form.get('email')}"
                             f" cookie={request.cookies.get('note')}")

    # Start the daily timer once per server process (not in tests, not in the reloader's parent).
    if app.config["SCHEDULER_ENABLED"] and not app.config["TESTING"] and _serving() and \
            (not app.debug or os.environ.get("WERKZEUG_RUN_MAIN") == "true"):
        start_scheduler(dict(app.config))
    return app


def _serving():
    """Whether this process is here to serve pages: gunicorn (no Flask command
    line around it) or `flask run`. A one-off command (`flask --app wsgi
    backup`, `autopilot`, `seed-demo`...) loads the app too, and used to start
    the timer with it: its threads swept the live database beside the
    server's and were killed mid-sweep when the command ended, leaving an
    alert claimed and never sent, or a digest half sent."""
    ctx = click.get_current_context(silent=True)
    return ctx is None or ctx.info_name == "run"
