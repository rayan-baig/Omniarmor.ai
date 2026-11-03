# -*- coding: utf-8 -*-
"""Email delivery. Without SMTP settings, messages are kept in the app's
notification log instead of being sent, so nothing is lost.

Every email goes out the same way: a plain-text part and an HTML part, both
made from the one plain-text body the sender wrote (the copy Radar keeps),
with the same footer: the MTRX Horizyn line, and on a reminder a link to
choose which reminder emails you get. The HTML part is one 600-pixel column
in OmniArmor's colors (templates/email/message.html). Its building blocks
come from the body's shape:

    a line in capitals ("OVERDUE")       a heading
    lines starting "- "                  a list
    a line "Label: https://..."          a button
    anything else                        a paragraph, with its links
"""

import logging
import os
import re
import smtplib
import ssl
from email.message import EmailMessage

from jinja2 import Environment, FileSystemLoader, StrictUndefined
from markupsafe import Markup, escape

from .db import now_iso

log = logging.getLogger("omniarmor.notify")

# Every MTRX Horizyn app sends from the one company domain. The From line
# names the product; this line, at the foot of every email, names the
# company behind it.
SIGNATURE = "OmniArmor is a product of MTRX Horizyn."
# Where a person chooses which reminder emails they get.
MANAGE_PATH = "/app/settings#reminders"
REMINDER_KINDS = {"reminder"}
WIDTH = 600

_templates = Environment(loader=FileSystemLoader(os.path.join(os.path.dirname(__file__), "templates", "email")),
                         autoescape=True, undefined=StrictUndefined, trim_blocks=True, lstrip_blocks=True)


def footer_lines(cfg, kind=None):
    """The lines under every email of this kind, the MTRX Horizyn line last."""
    base = (cfg or {}).get("BASE_URL", "").rstrip("/")
    lines = []
    if kind in REMINDER_KINDS:
        lines.append(f"Choose which reminder emails you get: {base}{MANAGE_PATH}")
    elif kind in ("autopilot", "autopilot_weekly"):
        lines.append(f"Sent by OmniArmor Autopilot at {base}. It fixes small problems by itself and only emails"
                     " you about these.")
        if kind == "autopilot_weekly":
            lines.append(f"Turn this weekly report off (signed in with this address): {base}{MANAGE_PATH}")
    lines.append(SIGNATURE)
    return lines


def _unsigned(body):
    """The body without a footer a stored copy may already carry."""
    body = body.rstrip()
    if body.endswith(SIGNATURE) and "\n--\n" in body:
        body = body[:body.rindex("\n--\n")].rstrip()
    elif body.endswith(SIGNATURE):
        body = body[:-len(SIGNATURE)].rstrip()
    return body


def signed(body, cfg=None, kind=None):
    """The plain-text email as it is sent: the body, then its footer, once."""
    return _unsigned(body) + "\n\n--\n" + "\n".join(footer_lines(cfg, kind)) + "\n"


# --- The HTML part ---------------------------------------------------------------

_URL = re.compile(r"https?://[^\s<>\"']+")
_BUTTON = re.compile(r"([A-Z][^:]{0,48}): (https?://\S+)")
_HEADING = re.compile(r"[A-Z][A-Z0-9 ,'&-]{1,40}")
LINK_STYLE = "color:#B4321F;text-decoration:underline;word-break:break-all;"


def linkify(text, style=LINK_STYLE):
    """Text as HTML, its web addresses as links. Everything else is escaped."""
    out, last = [], 0
    for m in _URL.finditer(text):
        url = m.group(0).rstrip(".,;:)")
        end = m.start() + len(url)
        out.append(escape(text[last:m.start()]))
        out.append(Markup('<a href="{0}" style="{1}">{0}</a>').format(url, style))
        last = end
    out.append(escape(text[last:]))
    return Markup("").join(out)


def blocks(body):
    """The body's paragraphs, as the building blocks the template draws, in order."""
    found = []
    for para in re.split(r"\n\s*\n", _unsigned(body).strip()):
        lines = [line.strip() for line in para.splitlines() if line.strip()]
        text, items = [], None

        def end_text():
            if text:
                found.append({"kind": "para", "lines": [linkify(t) for t in text]})
                text.clear()

        for line in lines:
            if line.startswith("- "):
                end_text()
                if items is None:
                    items = []
                    found.append({"kind": "list", "items": items})
                items.append(linkify(line[2:]))
                continue
            items = None
            button = _BUTTON.fullmatch(line)
            if button:
                end_text()
                found.append({"kind": "button", "label": button.group(1), "url": button.group(2)})
            elif len(lines) > 1 and _HEADING.fullmatch(line) and line.upper() == line:
                end_text()
                found.append({"kind": "heading", "text": line})
            else:
                text.append(line)
        end_text()
    return found


def render_email(cfg, subject, body, kind=None):
    """(plain text, HTML) for one email."""
    text = signed(body, cfg, kind)
    first = next((line.strip() for line in _unsigned(body).splitlines() if line.strip()), "")
    html = _templates.get_template("message.html").render(
        subject=" ".join(subject.split()), preheader=first, blocks=blocks(body), width=WIDTH,
        footer=[_footer_line(line) for line in footer_lines(cfg, kind)])
    return text, html


FOOTER_LINK_STYLE = "color:#6B635A;text-decoration:underline;"


def _footer_line(line):
    """A footer line as HTML: "Label: https://..." becomes the label as a link."""
    labelled = re.fullmatch(r"([A-Z][^:]{0,90}): (https?://\S+)", line)
    if labelled:
        return Markup('<a href="{1}" style="{2}">{0}</a>').format(*labelled.groups(), FOOTER_LINK_STYLE)
    return linkify(line, FOOTER_LINK_STYLE + "word-break:break-all;")


def send_email(cfg, to, subject, body, kind=None):
    """Returns (status, error) where status is 'sent', 'logged' or 'failed'."""
    if not cfg.get("SMTP_HOST"):
        return "logged", None
    try:
        text, html = render_email(cfg, subject, body, kind)
    except Exception:  # never lose an email over its looks: send the text alone
        log.exception("couldn't draw the HTML part of %r", subject)
        text, html = signed(body, cfg, kind), None
    try:
        msg = EmailMessage()
        msg["From"] = cfg["MAIL_FROM"]
        msg["To"] = to
        msg["Subject"] = " ".join(subject.split())
        if kind in REMINDER_KINDS:
            msg["List-Unsubscribe"] = f"<{cfg['BASE_URL'].rstrip('/')}{MANAGE_PATH}>"
        msg.set_content(text)
        if html is not None:
            msg.add_alternative(html, subtype="html")
        with smtplib.SMTP(cfg["SMTP_HOST"], cfg["SMTP_PORT"], timeout=20) as smtp:
            if cfg.get("SMTP_STARTTLS", True):
                smtp.starttls(context=ssl.create_default_context())
            if cfg.get("SMTP_USER"):
                smtp.login(cfg["SMTP_USER"], cfg["SMTP_PASSWORD"])
            smtp.send_message(msg)
        return "sent", None
    except (OSError, smtplib.SMTPException, ValueError) as exc:
        return "failed", f"{type(exc).__name__}: {exc}"[:300]


def notify(conn, cfg, kind, recipient, subject, body, org_id=None, user_id=None):
    status, error = send_email(cfg, recipient, subject, body, kind=kind)
    conn.execute(
        "INSERT INTO notifications (org_id, user_id, created_at, kind, recipient, subject, body, status, error)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (org_id, user_id, now_iso(), kind, recipient, subject, body, status, error),
    )
    conn.commit()
    return status
