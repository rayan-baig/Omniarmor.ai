# -*- coding: utf-8 -*-
"""OmniArmor.ai web app. Catch the fine before it catches you.

create_app() builds the app; wsgi.py runs it in production.
"""

import logging
import os

from flask import Blueprint, Flask, Response, abort, current_app, g, jsonify, redirect, render_template, request, url_for
from werkzeug.middleware.proxy_fix import ProxyFix

from . import academy_views, armo_views, autopilot, auth, views
from .catalog import INDUSTRIES, rules_for
from .config import load_config
from .db import SCHEMA_VERSION, close_db, connect, get_db, migrate
from .jobs import register_cli, start_scheduler
from .security import check_csrf, csrf_token, load_user, security_headers
from .tracking import format_quantity

SLOGAN = "Catch the fine before it catches you."

public = Blueprint("public", __name__)


@public.route("/")
def home():
    if g.get("user") is not None:
        return redirect(url_for("app.overview"))
    if g.get("kid") is not None:
        return redirect(url_for("academy.level_map", learner_id=g.kid["id"]))
    return render_template("home.html", industries=INDUSTRIES)


@public.route("/industries")
def industries():
    return render_template("industries.html", industries=INDUSTRIES)


@public.route("/industries/<slug>")
def industry_page(slug):
    """A landing page per industry, so each niche finds a page about its own risks."""
    match = next((i for i in INDUSTRIES.values() if i["brand"].lower() == slug.lower()), None)
    if match is None:
        abort(404)
    return render_template("industry_public.html", info=match, rules=rules_for(match["id"]))


@public.route("/robots.txt")
def robots():
    body = "User-agent: *\nAllow: /\nDisallow: /app\nSitemap: " + current_app.config["BASE_URL"] + "/sitemap.xml\n"
    return Response(body, mimetype="text/plain")


@public.route("/sitemap.xml")
def sitemap():
    base = current_app.config["BASE_URL"]
    urls = [base + "/", base + "/industries"] + [f"{base}/industries/{i['brand'].lower()}" for i in INDUSTRIES.values()]
    xml = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    xml += [f"<url><loc>{u}</loc></url>" for u in urls] + ["</urlset>"]
    return Response("\n".join(xml), mimetype="application/xml")


@public.route("/favicon.ico")
def favicon():
    return redirect(url_for("static", filename="favicon.svg"), code=301)


@public.route("/healthz")
def healthz():
    try:
        version = get_db().execute("SELECT MAX(version) FROM schema_version").fetchone()[0]
        ok = version == SCHEMA_VERSION
    except Exception:  # report unhealthy rather than crash the health check
        ok, version = False, None
    return jsonify(status="ok" if ok else "error", schema=version), (200 if ok else 503)


def create_app(**overrides):
    cfg = load_config(**overrides)
    app = Flask(__name__, instance_relative_config=False)
    app.config.update(cfg)
    if cfg["TRUSTED_PROXIES"] > 0:
        hops = cfg["TRUSTED_PROXIES"]
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=hops, x_proto=hops, x_host=hops)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    conn = connect(app.config["DATABASE"])
    migrate(conn)
    conn.close()

    app.teardown_appcontext(close_db)
    app.before_request(load_user)
    app.before_request(check_csrf)
    app.after_request(security_headers)
    app.jinja_env.globals.update(csrf_token=csrf_token, SLOGAN=SLOGAN)
    app.jinja_env.filters["qty"] = lambda value, unit: format_quantity(value, unit)

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
