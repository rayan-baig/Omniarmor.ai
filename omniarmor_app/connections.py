# -*- coding: utf-8 -*-
"""The Kitchen Safety Bundle: CyberLogix fills in OmniArmor's temperature checks.

CyberLogix is MTRX Horizyn's fridge and freezer alarm app. A workspace owner
creates a connection key in Settings, Connections (shown once, stored as a
hash like invite links, one active key per workspace) and pastes it into
CyberLogix. Each day CyberLogix sends that day's summary to
POST /api/connect/cyberlogix/daily with the key as a Bearer token. The
contract the CyberLogix side builds against is docs/CYBERLOGIX-CONNECTION.md:
change one, change the other.

What a report does to each of the workspace's temperature-log checks
(TEMPERATURE_CHECKS, in the industries it tracks):

- every unit in range all day: the check gets the day's warmest reading
  through tracking.apply_change, the same code a person's Save goes through,
  with "From CyberLogix: 7 of 7 units in range all day" in the audit trail;
- a breach, or a unit not confirmed in range: no reading is saved. The check
  gets a note for a person to review instead.

One report per workspace, check and day (connection_reports). The same report
again changes nothing; a corrected one replaces the note, and never takes
away or overwrites a reading someone on the team saved that day or later.
A report carries temperatures, unit names and roles ("on-call staff"), never
a person's name: the roles and actions are fixed lists.
"""

import hashlib
import json
import math
import re
import secrets
from datetime import date, datetime, timedelta
from urllib.parse import urlsplit

from flask import Blueprint, current_app, jsonify, request

from .catalog import INDUSTRIES, find_rule
from .db import get_db, now_iso, record_audit
from .security import client_ip, hash_token, rate_limited, record_event
from .tracking import _get_row, apply_change, format_quantity, local_date, org_industry_ids, org_today

SERVICE = "cyberlogix"
NAME = "CyberLogix"
BUNDLE = "Kitchen Safety Bundle"

# The checks CyberLogix fills in: the catalog's fridge, freezer and cold
# holding temperature checks, as (industry id, rule key). Each one is a
# maximum in °F, which tests check.
TEMPERATURE_CHECKS = (
    (2, "cold_holding"),   # RestoArmor: Cold holding at 41°F or below (FDA Food Code 3-501.16(A)(2))
)

KEY_PREFIX = "clx_"

# --- Request limits ------------------------------------------------------------
MAX_BODY = 32 * 1024           # bytes
MAX_BREACHES = 50
MAX_UNITS = 500
MAX_TEXT = 60                  # a unit's or site's name
MAX_URL = 500
LOWEST_TEMP, HIGHEST_TEMP = -100, 250  # in the unit sent, °F or °C
OLDEST_DAYS = 31               # how far back a report's date may be
LONGEST_BREACH = timedelta(hours=48)
# Requests per window: (key prefix, most, window).
PER_KEY = (60, timedelta(hours=1))         # a workspace's key, whatever it sends
PER_IP = (120, timedelta(hours=1))         # every request from one address
BAD_KEYS = (10, timedelta(minutes=15))     # wrong or revoked keys from one address

UNITS_OF_MEASURE = {"°F": "°F", "F": "°F", "°C": "°C", "C": "°C"}
# Who acknowledged a breach: a role, never a name.
ROLES = ("owner", "manager", "chef", "shift lead", "on-call staff", "kitchen staff", "maintenance", "technician")
# What was done about it, as a code and the words the note uses.
ACTIONS = {
    "moved_food": "food moved to another unit",
    "discarded_food": "food discarded",
    "checked_food": "food temperature checked",
    "closed_door": "door closed",
    "adjusted_unit": "unit settings adjusted",
    "called_technician": "technician called",
    "defrost_cycle": "defrost cycle, no action needed",
    "monitoring": "being monitored",
    "none": "no action yet",
}

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

api = Blueprint("connect", __name__, url_prefix="/api/connect")


# --- Keys ------------------------------------------------------------------------

def new_key():
    """A new connection key and its hash. Only the hash is stored."""
    key = KEY_PREFIX + secrets.token_urlsafe(32)
    return key, hash_token(key)


def active_key(conn, org_id):
    return conn.execute("SELECT * FROM connection_keys WHERE org_id = ? AND service = ? AND revoked_at IS NULL",
                        (org_id, SERVICE)).fetchone()


def create_key(conn, org_id, user_id, replace=False):
    """Makes the workspace's key and returns it, the only time it is ever
    seen. With replace, revokes the active one first (Regenerate); without,
    returns None when one is already active."""
    current = active_key(conn, org_id)
    if current is not None and not replace:
        return None
    if current is not None:
        conn.execute("UPDATE connection_keys SET revoked_at = ? WHERE id = ?", (now_iso(), current["id"]))
    key, digest = new_key()
    conn.execute("INSERT INTO connection_keys (org_id, service, key_hash, hint, created_at, created_by)"
                 " VALUES (?, ?, ?, ?, ?, ?)", (org_id, SERVICE, digest, key[-4:], now_iso(), user_id))
    what = "regenerated; the old key stopped working" if current is not None else "created"
    record_audit(conn, org_id, user_id, "connection", f"{NAME} connection key {what}")
    conn.commit()
    return key


def revoke_key(conn, org_id, user_id):
    """Revokes the active key. Returns whether there was one."""
    current = active_key(conn, org_id)
    if current is None:
        return False
    conn.execute("UPDATE connection_keys SET revoked_at = ? WHERE id = ?", (now_iso(), current["id"]))
    record_audit(conn, org_id, user_id, "connection", f"{NAME} connection key revoked")
    conn.commit()
    return True


def temperature_checks(conn, org_id):
    """The workspace's temperature-log checks: [(industry id, rule)] in the
    industries it tracks."""
    picked = set(org_industry_ids(conn, org_id))
    return [(i, find_rule(i, key)) for i, key in TEMPERATURE_CHECKS if i in picked]


def status(conn, org):
    """What Settings and the temperature checks show about the connection."""
    key = active_key(conn, org["id"])
    last = conn.execute("SELECT MAX(last_report_date) FROM connection_keys WHERE org_id = ? AND service = ?",
                        (org["id"], SERVICE)).fetchone()[0]
    checks = temperature_checks(conn, org["id"])
    return {"connected": key is not None, "key": key, "last_report": last if key is not None else None,
            "checks": checks, "keys": {(i, rule.key) for i, rule in checks}}


def open_notes(conn, org_id, industry_id, rule_key, limit=5):
    """The check's notes nobody has marked reviewed yet, newest day first."""
    return conn.execute(
        "SELECT * FROM connection_reports WHERE org_id = ? AND service = ? AND industry_id = ? AND rule_key = ?"
        " AND note IS NOT NULL AND reviewed_at IS NULL ORDER BY report_date DESC LIMIT ?",
        (org_id, SERVICE, industry_id, rule_key, limit)).fetchall()


def latest_report(conn, org_id, industry_id, rule_key):
    return conn.execute(
        "SELECT * FROM connection_reports WHERE org_id = ? AND service = ? AND industry_id = ? AND rule_key = ?"
        " ORDER BY report_date DESC LIMIT 1", (org_id, SERVICE, industry_id, rule_key)).fetchone()


def mark_reviewed(conn, org_id, user_id, industry_id, rule_key, day):
    """A person marks a check's note for a day reviewed. Returns whether
    there was an open one."""
    row = conn.execute(
        "SELECT * FROM connection_reports WHERE org_id = ? AND service = ? AND industry_id = ? AND rule_key = ?"
        " AND report_date = ? AND note IS NOT NULL AND reviewed_at IS NULL",
        (org_id, SERVICE, industry_id, rule_key, day)).fetchone()
    if row is None:
        return False
    conn.execute("UPDATE connection_reports SET reviewed_at = ? WHERE org_id = ? AND service = ? AND industry_id = ?"
                 " AND rule_key = ? AND report_date = ?", (now_iso(), org_id, SERVICE, industry_id, rule_key, day))
    rule = find_rule(industry_id, rule_key)
    record_audit(conn, org_id, user_id, "connection", f"{rule.title}: {NAME} note for {day} reviewed",
                 industry_id, rule_key)
    conn.commit()
    return True


# --- The report: checking what was sent -------------------------------------------

class PayloadError(ValueError):
    def __init__(self, problems):
        super().__init__("; ".join(f"{f}: {p}" for f, p in problems))
        self.problems = problems


def _is_int(value):
    return isinstance(value, int) and not isinstance(value, bool)


def _is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _text(value, field, problems, required=True):
    if value is None and not required:
        return None
    if not isinstance(value, str) or not value.strip():
        problems.append((field, "required text" if required else "text or null"))
        return None
    value = value.strip()
    if len(value) > MAX_TEXT:
        problems.append((field, f"at most {MAX_TEXT} characters"))
    elif any(ord(c) < 32 or ord(c) == 127 for c in value):
        problems.append((field, "no line breaks or control characters"))
    return value


def _temperature(value, field, problems):
    if not _is_number(value):
        problems.append((field, "a number"))
        return None
    if not LOWEST_TEMP <= value <= HIGHEST_TEMP:
        problems.append((field, f"between {LOWEST_TEMP} and {HIGHEST_TEMP}"))
        return None
    return round(float(value), 1)


def _uom(value, field, problems):
    if value not in UNITS_OF_MEASURE:
        problems.append((field, 'one of "°F", "°C", "F" or "C"'))
        return None
    return UNITS_OF_MEASURE[value]


def _moment(value, field, problems, required=True):
    if value is None and not required:
        return None
    try:
        moment = datetime.fromisoformat(value) if isinstance(value, str) and len(value) <= 40 else None
    except ValueError:
        moment = None
    if moment is None or "T" not in value or moment.tzinfo is None:
        problems.append((field, "a date and time with its UTC offset, like 2026-11-12T02:10:00-05:00"))
        return None
    return moment


def _log_url(value, problems):
    if value is None:
        return None
    if not isinstance(value, str) or len(value) > MAX_URL or any(ord(c) <= 32 or ord(c) == 127 for c in value):
        problems.append(("log_url", f"an https link of at most {MAX_URL} characters, or null"))
        return None
    parts = urlsplit(value)
    if parts.scheme != "https" or not parts.hostname or "@" in parts.netloc:
        problems.append(("log_url", "an https link, with no user name or password in it"))
        return None
    return value


def validate(body, today):
    """The report, checked and tidied, or PayloadError listing every problem.
    `today` is the workspace's date, for the range of dates accepted."""
    if not isinstance(body, dict):
        raise PayloadError([("body", "a JSON object")])
    problems = []
    day = body.get("date")
    if not isinstance(day, str) or not DATE_RE.match(day):
        problems.append(("date", "required, as YYYY-MM-DD"))
        day = None
    else:
        try:
            parsed = date.fromisoformat(day)
        except ValueError:
            parsed = None
            problems.append(("date", "not a real date"))
        if parsed is not None and not today - timedelta(days=OLDEST_DAYS) <= parsed <= today + timedelta(days=1):
            problems.append(("date", f"from {OLDEST_DAYS} days ago to tomorrow, in the workspace's timezone"))
    site = _text(body.get("site"), "site", problems, required=False)

    total, in_range = body.get("units_total"), body.get("units_in_range_all_day")
    if not _is_int(total) or not 1 <= total <= MAX_UNITS:
        problems.append(("units_total", f"a whole number from 1 to {MAX_UNITS}"))
        total = None
    if not _is_int(in_range) or in_range < 0 or (total is not None and in_range > total):
        problems.append(("units_in_range_all_day", "a whole number from 0 to units_total"))
        in_range = None

    breaches_in = body.get("breaches")
    breaches = []
    if not isinstance(breaches_in, list):
        problems.append(("breaches", "a list (empty when there were none)"))
        breaches_in = []
    elif len(breaches_in) > MAX_BREACHES:
        problems.append(("breaches", f"at most {MAX_BREACHES}"))
        breaches_in = []
    for n, b in enumerate(breaches_in):
        at = f"breaches[{n}]"
        if not isinstance(b, dict):
            problems.append((at, "an object"))
            continue
        before = len(problems)
        unit = _text(b.get("unit"), f"{at}.unit", problems)
        started = _moment(b.get("started_at"), f"{at}.started_at", problems)
        ended = _moment(b.get("ended_at"), f"{at}.ended_at", problems, required=False)
        peak = _temperature(b.get("peak"), f"{at}.peak", problems)
        limit = _temperature(b.get("limit"), f"{at}.limit", problems)
        uom = _uom(b.get("unit_of_measure"), f"{at}.unit_of_measure", problems)
        role = b.get("acknowledged_by_role")
        if role is not None and role not in ROLES:
            problems.append((f"{at}.acknowledged_by_role", "null or one of: " + ", ".join(ROLES)))
        action = b.get("action")
        if action is not None and action not in ACTIONS:
            problems.append((f"{at}.action", "null or one of: " + ", ".join(ACTIONS)))
        if started is not None and day is not None and len(problems) == before:
            try:
                start_day = started.date()
                report_day = date.fromisoformat(day)
            except ValueError:
                start_day = report_day = None
            if report_day and not report_day - timedelta(days=1) <= start_day <= report_day + timedelta(days=1):
                problems.append((f"{at}.started_at", "on the report's date (a day either side at most)"))
            if ended is not None and not timedelta(0) <= ended - started <= LONGEST_BREACH:
                problems.append((f"{at}.ended_at", "after started_at, and at most 48 hours later"))
        if len(problems) == before:
            breaches.append({"unit": unit, "started_at": started.isoformat(),
                             "ended_at": ended.isoformat() if ended else None, "peak": peak, "limit": limit,
                             "unit_of_measure": uom, "acknowledged_by_role": role, "action": action})

    warmest, warmest_uom = body.get("warmest_reading"), body.get("unit_of_measure")
    clean = not breaches_in and total is not None and in_range == total
    if warmest is None and warmest_uom is None:
        if clean:
            problems.append(("warmest_reading", "required when every unit stayed in range all day (it is the reading"
                                                " the temperature check gets)"))
    else:
        warmest = _temperature(warmest, "warmest_reading", problems)
        warmest_uom = _uom(warmest_uom, "unit_of_measure", problems)
    if breaches_in and total is not None and in_range is not None:
        if in_range == total:
            problems.append(("units_in_range_all_day", "less than units_total when there are breaches"))
        elif len({b["unit"].casefold() for b in breaches}) > total - in_range:
            problems.append(("breaches", "more units with breaches than units out of range"))

    log_url = _log_url(body.get("log_url"), problems)
    if problems:
        raise PayloadError(problems)
    return {"date": day, "site": site, "units_total": total, "units_in_range_all_day": in_range,
            "breaches": breaches, "warmest_reading": warmest, "unit_of_measure": warmest_uom, "log_url": log_url}


# --- The report: what it does -------------------------------------------------------

def _fahrenheit(value, uom):
    return value if uom == "°F" else round(value * 9 / 5 + 32, 1)


def _span(b):
    """"02:10–02:45" in the site's own clock (the offset CyberLogix sent)."""
    start = datetime.fromisoformat(b["started_at"])
    if b["ended_at"] is None:
        return f"from {start:%H:%M}, still out of range when reported"
    end = datetime.fromisoformat(b["ended_at"])
    later = " the next day" if end.date() > start.date() else ""
    return f"{start:%H:%M}–{end:%H:%M}{later}"


def _breach_text(b):
    peak = format_quantity(_tidy(b["peak"]), b["unit_of_measure"])
    limit = format_quantity(_tidy(b["limit"]), b["unit_of_measure"])
    text = f"{b['unit']}, {_span(b)}, peak {peak} (limit {limit})"
    text += f"; acknowledged by {b['acknowledged_by_role']}" if b["acknowledged_by_role"] else "; not acknowledged"
    if b["action"]:
        text += f"; {ACTIONS[b['action']]}"
    return text


def _tidy(value):
    return int(value) if float(value).is_integer() else value


def note_for(report):
    """The note a report that doesn't tick leaves on the check."""
    breaches = report["breaches"]
    total, in_range = report["units_total"], report["units_in_range_all_day"]
    if len(breaches) == 1:
        text = f"{NAME}: 1 breach on {_breach_text(breaches[0])}"
    elif breaches:
        text = f"{NAME}: {len(breaches)} breaches. " + ". ".join(_breach_text(b) for b in breaches)
    else:
        text = f"{NAME}: {total - in_range} of {total} units not confirmed in range all day, with no breach details"
    text += f". {in_range} of {total} units in range all day."
    return text


def fingerprint(report):
    return hashlib.sha256(json.dumps(report, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def _by_a_person(item):
    """Whether the check's reading was last changed by someone on the team
    (a removed member's change keeps their name and loses the id)."""
    return item is not None and (item["updated_by"] is not None or item["updated_by_name"] not in (None, NAME))


def _apply_to_check(conn, org, industry_id, rule, report, digest):
    """One report on one check. Returns what happened: "ticked", "confirmed",
    "note" or "unchanged"."""
    org_id, day = org["id"], report["date"]
    key = (org_id, SERVICE, industry_id, rule.key, day)
    before = conn.execute("SELECT * FROM connection_reports WHERE org_id = ? AND service = ? AND industry_id = ?"
                          " AND rule_key = ? AND report_date = ?", key).fetchone()
    if before is not None and before["fingerprint"] == digest:
        return "unchanged"
    clean = not report["breaches"] and report["units_in_range_all_day"] == report["units_total"]
    counts = f"{report['units_in_range_all_day']} of {report['units_total']} units in range all day"
    reading = note = None
    reviewed_at = before["reviewed_at"] if before is not None else None
    if clean:
        reading = _fahrenheit(report["warmest_reading"], report["unit_of_measure"])
        item = _get_row(conn, org_id, industry_id, rule.key)
        later = conn.execute("SELECT 1 FROM connection_reports WHERE org_id = ? AND service = ? AND industry_id = ?"
                             " AND rule_key = ? AND report_date > ?", key).fetchone()
        theirs = _by_a_person(item) and local_date(item["updated_at"], org) >= day
        shown = format_quantity(_tidy(reading), rule.unit)
        summary = f"From {NAME}: {counts} on {day}; warmest {shown}"
        if theirs or later:
            outcome = "confirmed"
            why = "the team's reading stands" if theirs else "a later day's report set the reading"
            summary = f"From {NAME}: {counts} on {day}; {why}"
            if before is None or before["outcome"] != "confirmed":
                record_audit(conn, org_id, None, "connection", f"From {NAME}: {counts} on {day}; {rule.title}: {why}",
                             industry_id, rule.key, actor=NAME)
        else:
            outcome = "ticked"
            if before is None or before["outcome"] != "ticked" or before["reading"] != reading:
                apply_change(conn, org, None, industry_id, rule.key, "save", {"value": str(reading)}, commit=False,
                             actor=NAME, summary=f"From {NAME}: {counts} on {day}; {rule.title} set to the warmest"
                                                 f" reading, {shown}")
    else:
        outcome, note = "note", note_for(report)
        summary = f"{note} Report for {day}, left for review."
        if before is None or before["note"] != note:
            reviewed_at = None
            corrected = " A corrected report." if before is not None else ""
            record_audit(conn, org_id, None, "connection", f"{rule.title}: {summary}{corrected}", industry_id,
                         rule.key, actor=NAME)
    now = now_iso()
    conn.execute(
        "INSERT INTO connection_reports (org_id, service, industry_id, rule_key, report_date, fingerprint, outcome,"
        " reading, summary, note, site, log_url, received_at, updated_at, reviewed_at)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
        " ON CONFLICT (org_id, service, industry_id, rule_key, report_date) DO UPDATE SET"
        " fingerprint = excluded.fingerprint, outcome = excluded.outcome, reading = excluded.reading,"
        " summary = excluded.summary, note = excluded.note, site = excluded.site, log_url = excluded.log_url,"
        " updated_at = excluded.updated_at, reviewed_at = excluded.reviewed_at",
        (*key, digest, outcome, reading, summary, note, report["site"], report["log_url"], now, now, reviewed_at))
    return outcome


def receive(conn, org, key_row, report):
    """Applies a checked report to the workspace's temperature checks, all
    in one transaction. Returns the JSON answer."""
    digest = fingerprint(report)
    if conn.in_transaction:
        conn.commit()
    conn.execute("BEGIN IMMEDIATE")   # two copies of one report sent at once apply once
    try:
        checks = temperature_checks(conn, org["id"])
        results = [(i, rule, _apply_to_check(conn, org, i, rule, report, digest)) for i, rule in checks]
        conn.execute("UPDATE connection_keys SET last_used_at = ?,"
                     " last_report_date = MAX(COALESCE(last_report_date, ''), ?) WHERE id = ?",
                     (now_iso(), report["date"], key_row["id"]))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    answer = {"ok": True, "date": report["date"], "matched_checks": len(results),
              "ticked": sum(r == "ticked" for _, _, r in results),
              "noted": sum(r == "note" for _, _, r in results),
              "unchanged": sum(r == "unchanged" for _, _, r in results),
              "checks": [{"industry": INDUSTRIES[i]["brand"], "check": rule.key, "title": rule.title, "result": r}
                         for i, rule, r in results]}
    if not results:
        answer["hint"] = ("This workspace tracks no temperature-log check, so nothing was filled in. In OmniArmor,"
                          " the owner can add RestoArmor (Restaurants) in Settings, Company, to track cold holding.")
    return answer


# --- The address CyberLogix calls -------------------------------------------------------

def _error(status_code, code, message, **extra):
    response = jsonify(ok=False, error=code, message=message, **extra)
    response.status_code = status_code
    if status_code == 401:
        response.headers["WWW-Authenticate"] = 'Bearer realm="omniarmor"'
    return response


def _too_many(window):
    response = _error(429, "rate_limited", "Too many requests. Wait and try again.")
    response.headers["Retry-After"] = str(int(window.total_seconds()))
    return response


def _bearer():
    header = request.headers.get("Authorization", "")
    scheme, _, token = header.partition(" ")
    token = token.strip()
    if scheme.lower() != "bearer" or not token or len(token) > 200:
        return None
    return token


@api.route("/cyberlogix/daily", methods=["POST"])
def cyberlogix_daily():
    """CyberLogix's daily report. Answered in JSON only, authenticated by the
    workspace's connection key and nothing else (no cookie), so it is the one
    form-free POST outside Stripe's webhook that skips the CSRF token."""
    conn = get_db()
    ip = client_ip()
    if rate_limited([(f"cyberlogix-bad:{ip}", BAD_KEYS[0])], BAD_KEYS[1]):
        return _too_many(BAD_KEYS[1])
    if rate_limited([(f"cyberlogix-ip:{ip}", PER_IP[0])], PER_IP[1]):
        return _too_many(PER_IP[1])
    record_event([f"cyberlogix-ip:{ip}"])
    token = _bearer()
    key_row = None
    if token is not None:
        key_row = conn.execute("SELECT * FROM connection_keys WHERE key_hash = ? AND service = ? AND revoked_at IS NULL",
                               (hash_token(token), SERVICE)).fetchone()
    if key_row is None:
        record_event([f"cyberlogix-bad:{ip}"])
        return _error(401, "unauthorized", "Send the workspace's CyberLogix connection key as"
                                           " 'Authorization: Bearer <key>'. A revoked key stops working.")
    if rate_limited([(f"cyberlogix-key:{key_row['id']}", PER_KEY[0])], PER_KEY[1]):
        return _too_many(PER_KEY[1])
    record_event([f"cyberlogix-key:{key_row['id']}"])
    org = conn.execute("SELECT * FROM orgs WHERE id = ?", (key_row["org_id"],)).fetchone()
    raw = request.get_data(cache=False)
    if len(raw) > MAX_BODY:
        return _error(413, "payload_too_large", f"The report is over {MAX_BODY // 1024} KB.")
    if request.mimetype != "application/json":
        return _error(415, "unsupported_media_type", "Send the report as JSON, with Content-Type: application/json.")
    try:
        body = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return _error(400, "invalid_json", "The body is not valid JSON.")
    try:
        report = validate(body, org_today(org))
    except PayloadError as exc:
        return _error(422, "invalid_payload", "Some fields are missing or out of range; nothing was changed.",
                      errors=[{"field": f, "problem": p} for f, p in exc.problems])
    answer = receive(conn, org, key_row, report)
    current_app.logger.info("cyberlogix report for workspace %s, %s: %s matched, %s ticked, %s noted", org["id"],
                            report["date"], answer["matched_checks"], answer["ticked"], answer["noted"])
    return jsonify(answer)


def api_headers(response):
    """Nothing the API answers is kept by a browser or a proxy."""
    if request.blueprint == api.name:
        response.headers["Cache-Control"] = "no-store"
    return response


def is_api_request():
    return request.path.startswith(api.url_prefix + "/")
