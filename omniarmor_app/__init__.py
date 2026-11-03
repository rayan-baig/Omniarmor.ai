# -*- coding: utf-8 -*-
"""OmniArmor.ai web app. Catch the fine before it catches you.

create_app() builds the app; wsgi.py runs it in production.
"""

import hmac
import logging
import os
import time
from datetime import timedelta

from flask import (Blueprint, Flask, Response, abort, current_app, g, jsonify, redirect, render_template, request,
                   send_from_directory, url_for)
from markupsafe import escape
from werkzeug.middleware.proxy_fix import ProxyFix

from . import academy_views, armo_views, autopilot, auth, views
from .catalog import INDUSTRIES, rules_for, top_checks, why_line
from .config import load_config
from .db import SCHEMA_VERSION, close_db, connect, get_db, migrate, utcnow
from .jobs import register_cli, start_scheduler
from .redact import RedactingFilter, redact
from .security import check_csrf, csrf_token, load_user, security_headers
from .tracking import format_quantity, local_date
from .version import __version__

SLOGAN = "Catch the fine before it catches you."

public = Blueprint("public", __name__)


@public.route("/")
def home():
    if g.get("user") is not None:
        return redirect(url_for("app.overview"))
    if g.get("kid") is not None:
        return redirect(url_for("academy.level_map", learner_id=g.kid["id"]))
    return render_template("home.html", industries=INDUSTRIES, facts=_landing_facts())


# Industries named on the landing page as examples of who OmniArmor is for.
LANDING_EXAMPLES = (2, 1, 29, 45, 5, 28)


def _landing_facts():
    """Every number the landing page shows, read from the code that sets it:
    the catalog, the Academy's tracks and plan, and the settings."""
    from .academy import TRACK_LIST
    from .academy_plan import FREE_TRACK, FREE_WORLDS
    cfg = current_app.config
    return {
        "industries": len(INDUSTRIES),
        "checks": sum(len(rules_for(i)) for i in INDUSTRIES),
        "per_industry": len(rules_for(next(iter(INDUSTRIES)))),
        "examples": [INDUSTRIES[i]["sector"].lower() for i in LANDING_EXAMPLES],
        "trial_days": cfg["ACADEMY_TRIAL_DAYS"],
        "price": cfg.get("ACADEMY_PRICE_LABEL", "").strip(),
        "free_worlds": len(FREE_WORLDS),
        "free_track": next(t.name for t in TRACK_LIST if t.key == FREE_TRACK),
        "tracks": len(TRACK_LIST),
        "fewest_levels": min(t.total for t in TRACK_LIST),
        "most_levels": max(t.total for t in TRACK_LIST),
    }


@public.route("/industries")
def industries():
    return render_template("industries.html", industries=INDUSTRIES)


@public.route("/industries/<slug>")
def industry_page(slug):
    """A landing page per industry, so each niche finds a page about its own risks."""
    match = next((i for i in INDUSTRIES.values() if i["brand"].lower() == slug.lower()), None)
    if match is None:
        abort(404)
    top = top_checks(match["id"])
    rest = [r for r in rules_for(match["id"]) if r not in top]
    return render_template("industry_public.html", info=match, top=top, rest=rest, why_line=why_line)


# The date the Terms and Privacy pages last changed. Update it with them.
RULES_UPDATED = "3 November 2026"


def _rules_facts():
    """The numbers the Terms and Privacy pages quote, read from the code that
    sets them, so the pages stay true when a setting changes."""
    from .academy import FRIEND_CODE_DAYS
    from .academy_plan import FREE_WORLDS
    from .academy_views import JOIN_CODE_DAYS, QUIZ_CHECK_DAYS
    from .autopilot import KEEP_ERRORS, MAX_EMAILS_PER_HOUR
    from .jobs import ALERTS_EVERY_SECONDS
    from .auth import INVITE_DAYS, RESET_HOURS
    cfg = current_app.config
    return {
        "updated": RULES_UPDATED,
        "trial_days": cfg["ACADEMY_TRIAL_DAYS"],
        "free_worlds": len(FREE_WORLDS),
        "backup_keep": cfg["BACKUP_KEEP"],
        "session_days": cfg["PERMANENT_SESSION_LIFETIME"].days,
        "reset_hours": RESET_HOURS,
        "invite_days": INVITE_DAYS,
        "join_code_days": JOIN_CODE_DAYS,
        "friend_code_days": FRIEND_CODE_DAYS,
        "quiz_check_days": QUIZ_CHECK_DAYS,
        "error_days": KEEP_ERRORS.days,
        "operator_emails_per_hour": MAX_EMAILS_PER_HOUR,
        "alert_minutes": max(1, ALERTS_EVERY_SECONDS // 60),
    }


@public.route("/privacy")
def privacy():
    return render_template("privacy.html", facts=_rules_facts())


@public.route("/terms")
def terms():
    return render_template("terms.html", facts=_rules_facts())


# The pages anyone can open and search engines may list: the sitemap gives
# them, and they carry share previews (og: and twitter: tags) and a canonical
# address. Every other page is private: marked noindex, and the ones that
# hold a person's or a company's data are closed to crawlers in robots.txt.
PUBLIC_PAGES = {"public.home", "public.industries", "public.industry_page", "public.terms", "public.privacy",
                "auth.signup", "auth.login"}
# Addresses that are not pages: they get no noindex header.
NOT_PAGES = {"static", "public.robots", "public.sitemap", "public.favicon", "public.apple_touch_icon"}
# Closed to crawlers: the app (with the Academy and Settings), password reset
# and invite links, the kids' join page, and the addresses only programs use.
# ("/app$" and "/app/", not "/app", which would also close /apple-touch-icon.png.)
ROBOTS_DISALLOW = ("/app$", "/app/", "/reset/", "/signup?invite=", "/forgot", "/kids", "/logout", "/billing/", "/api/",
                   "/healthz")


def public_page():
    """Whether the page being drawn is one of PUBLIC_PAGES, as a visitor sees
    it (a sign-up page opened from an invite link is private)."""
    return request.endpoint in PUBLIC_PAGES and not request.args.get("invite")


def canonical_url():
    """This page's one full address, as the sitemap gives it."""
    args = dict(request.view_args or {})
    if request.endpoint == "public.industry_page":
        args["slug"] = args["slug"].lower()
    return current_app.config["BASE_URL"] + url_for(request.endpoint, **args)


def robots_header(response):
    """noindex on everything but the public pages, for crawlers that read
    the header (it also covers the CSV exports, which have no <meta>)."""
    if request.endpoint not in NOT_PAGES and not (public_page() and response.status_code == 200):
        response.headers.setdefault("X-Robots-Tag", "noindex, nofollow")
    return response


@public.route("/robots.txt")
def robots():
    lines = ["User-agent: *", "Allow: /"] + [f"Disallow: {path}" for path in ROBOTS_DISALLOW]
    lines.append("Sitemap: " + current_app.config["BASE_URL"] + "/sitemap.xml")
    return Response("\n".join(lines) + "\n", mimetype="text/plain")


@public.route("/sitemap.xml")
def sitemap():
    base = current_app.config["BASE_URL"]
    paths = [url_for("public.home"), url_for("public.industries")]
    paths += [url_for("public.industry_page", slug=i["brand"].lower()) for i in INDUSTRIES.values()]
    paths += [url_for("auth.signup"), url_for("auth.login"), url_for("public.terms"), url_for("public.privacy")]
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
    """User counts for the owner's MTRX Horizyn console, and nothing else.

    Off unless STATS_KEY is set, and answered only to that key. Counts only:
    no names, no companies, nothing about anyone in particular.
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
    return jsonify(users=users, active_users=active)


@public.route("/healthz")
def healthz():
    try:
        version = get_db().execute("SELECT MAX(version) FROM schema_version").fetchone()[0]
        ok = version == SCHEMA_VERSION
    except Exception:  # report unhealthy rather than crash the health check
        ok, version = False, None
    # The release and the schema, and nothing else: this answers anyone.
    return jsonify(status="ok" if ok else "error", schema=version, version=__version__), (200 if ok else 503)


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


def create_app(**overrides):
    cfg = load_config(**overrides)
    app = OmniArmorFlask(__name__, instance_relative_config=False)
    app.config.update(cfg)
    if cfg["TRUSTED_PROXIES"] > 0:
        hops = cfg["TRUSTED_PROXIES"]
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=hops, x_proto=hops, x_host=hops)
    _set_up_logging()

    conn = connect(app.config["DATABASE"])
    migrate(conn)
    conn.close()

    app.teardown_appcontext(close_db)
    app.before_request(load_user)
    app.before_request(check_csrf)
    app.after_request(security_headers)
    app.after_request(robots_header)
    app.jinja_env.globals.update(csrf_token=csrf_token, SLOGAN=SLOGAN, APP_VERSION=__version__,
                                public_page=public_page, canonical_url=canonical_url)
    app.jinja_env.filters["qty"] = lambda value, unit: format_quantity(value, unit)
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
    app.register_blueprint(academy_views.plan)
    app.register_blueprint(armo_views.bp)
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
        title, help_text = ERROR_PAGES.get(code, ERROR_PAGES[500])
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

    if app.config["TESTING"]:
        # A page that always fails, so tests can see the 500 page as a visitor
        # would. Only in tests: no running server has it.
        @app.route("/_test/server-error")
        def _test_server_error():
            raise RuntimeError("test failure at /srv/omniarmor/omniarmor_app/secret.py with SECRET_KEY")

    # Start the daily timer once per server process (not in tests, not in the reloader's parent).
    if app.config["SCHEDULER_ENABLED"] and not app.config["TESTING"] and \
            (not app.debug or os.environ.get("WERKZEUG_RUN_MAIN") == "true"):
        start_scheduler(dict(app.config))
    return app
