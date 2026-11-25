# -*- coding: utf-8 -*-
"""Names that may still change, in one place (1.24.0).

The values live in names.json beside this file, so the JavaScript tests read
the same ones; this module works out every address from them. The company's
name and domain, the help address, the sister apps' names and addresses and
the assistant's name are never typed anywhere else in the app: templates get
them as globals (COMPANY, NAMES), emails and settings import them from here,
and Pilot's config and knowledge pack get them on Pilot's script tag
(pilot.py, facts["names"]).

To rename the company, change "company" and "domain" in names.json. The help
address and every app's address follow the domain; the old addresses of this
app (OLD_APP_HOSTS) keep working as redirects to the new one (security.py).

The assistant: "assistant" is the name every page shows, the same as the
shared Pilot core's own words (static/pilot/, which this app never edits).
"""

import json
import os

with open(os.path.join(os.path.dirname(__file__), "names.json"), encoding="utf-8") as _f:
    RAW = json.load(_f)

COMPANY = RAW["company"]
DOMAIN = RAW["domain"]
HELP_EMAIL = f"{RAW['help_mailbox']}@{DOMAIN}"
COMPANY_URL = f"https://{DOMAIN}"

APP_NAME = RAW["app"]
APP_HOST = f"{RAW['app_subdomain']}.{DOMAIN}"
APP_URL = f"https://{APP_HOST}"
STAGING_HOST = f"staging.{APP_HOST}"
# Where this app used to live: requests that still arrive there are sent on to APP_HOST.
OLD_APP_HOSTS = tuple(f"{sub}.{DOMAIN}" for sub in RAW["old_app_subdomains"])

FRIDGE_APP = RAW["fridge_app"]
FRIDGE_HOST = f"{RAW['fridge_subdomain']}.{DOMAIN}"
FRIDGE_URL = f"https://{FRIDGE_HOST}"

ASSISTANT = RAW["assistant"]

# The company's other apps: {name: address}.
OTHER_APPS = {name: f"https://{sub}.{DOMAIN}" for name, sub in RAW["other_apps"].items()}

MAIL_FROM_DEFAULT = f"{APP_NAME} <no-reply@localhost>"
MAIL_FROM_LIVE = f"{APP_NAME} <no-reply@{APP_HOST}>"
SIGNATURE = f"{APP_NAME} is a product of {COMPANY}."


def for_pages():
    """The names as one small dict, for templates (NAMES) and Pilot's script tag."""
    return {"company": COMPANY, "domain": DOMAIN, "help_email": HELP_EMAIL, "company_url": COMPANY_URL,
            "app": APP_NAME, "app_url": APP_URL, "fridge_app": FRIDGE_APP, "fridge_url": FRIDGE_URL,
            "assistant": ASSISTANT, "other_apps": dict(OTHER_APPS)}
