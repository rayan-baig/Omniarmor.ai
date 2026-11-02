# -*- coding: utf-8 -*-
"""OmniArmor.ai web app. Catch the fine before it catches you.

create_app() builds the app; wsgi.py runs it in production.
"""

import hmac
import logging
import os
import time
from datetime import timedelta

from flask import Blueprint, Flask, Response, abort, current_app, g, jsonify, redirect, render_template, request, url_for
from werkzeug.middleware.proxy_fix import ProxyFix

from . import academy_views, armo_views, autopilot, auth, views
from .catalog import INDUSTRIES, rules_for, top_checks, why_line
from .config import load_config
from .db import SCHEMA_VERSION, close_db, connect, get_db, migrate, utcnow
from .jobs import register_cli, start_scheduler
from .redact import RedactingFilter, redact
from .security import check_csrf, csrf_token, load_user, security_headers
from .tracking import format_quantity, local_date

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
RULES_UPDATED = "2 November 2026"


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


@public.route("/robots.txt")
def robots():
    body = "User-agent: *\nAllow: /\nDisallow: /app\nSitemap: " + current_app.config["BASE_URL"] + "/sitemap.xml\n"
    return Response(body, mimetype="text/plain")


@public.route("/sitemap.xml")
def sitemap():
    base = current_app.config["BASE_URL"]
    urls = [base + "/", base + "/industries", base + "/terms", base + "/privacy"] + [f"{base}/industries/{i['brand'].lower()}" for i in INDUSTRIES.values()]
    xml = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    xml += [f"<url><loc>{u}</loc></url>" for u in urls] + ["</urlset>"]
    return Response("\n".join(xml), mimetype="application/xml")


@public.route("/favicon.ico")
def favicon():
    return redirect(url_for("static", filename="favicon.svg"), code=301)


@public.route("/api/stats")
def stats():
    """User counts for the owner's MTRX Horizon console, and nothing else.

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
    return jsonify(status="ok" if ok else "error", schema=version), (200 if ok else 503)


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
    app.jinja_env.globals.update(csrf_token=csrf_token, SLOGAN=SLOGAN)
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
        titles = {400: "That request didn't work", 403: "You don't have access to that",
                  404: "Page not found", 405: "That action isn't allowed here",
                  413: "That upload is too large", 500: "Something went wrong on our side",
                  503: "That's unavailable for a moment"}
        description = getattr(err, "description", None) if code != 500 else None
        if code == 500:
            cause = getattr(err, "original_exception", None) or err
            autopilot.record_error(app.config, request.path, cause)
        return render_template("error.html", code=code, title=titles.get(code, "Error"),
                               description=description), code

    # Start the daily timer once per server process (not in tests, not in the reloader's parent).
    if app.config["SCHEDULER_ENABLED"] and not app.config["TESTING"] and \
            (not app.debug or os.environ.get("WERKZEUG_RUN_MAIN") == "true"):
        start_scheduler(dict(app.config))
    return app
