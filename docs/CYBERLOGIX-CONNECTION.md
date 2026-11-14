# The CyberLogix connection: contract

**Kitchen Safety Bundle.** CyberLogix (MTRX Horizyn's fridge and freezer alarm
app) sends OmniArmor one summary per workspace per day. OmniArmor uses it to
fill in its temperature-log checks. This page is the contract the CyberLogix
side builds against. The OmniArmor side is `omniarmor_app/connections.py`,
tested by `tests/test_cyberlogix.py`, and the two must change together.

Examples use `omniarmor.example.com`. In production OmniArmor runs on its own
subdomain of MTRX Horizyn's domain (docs/OPERATIONS.md, section 1).

## 1. In one paragraph

The workspace owner creates a **connection key** in OmniArmor (Settings,
Connections) and pastes it into CyberLogix. Once a day, after the site's day
ends, CyberLogix sends `POST /api/connect/cyberlogix/daily` with that key and
a JSON summary of the day. If every unit stayed in range all day, OmniArmor
saves the day's warmest reading on its temperature check(s) and the check is
ticked, with "From CyberLogix: 7 of 7 units in range all day" in the audit
trail. If anything went out of range, nothing is ticked: the check gets a
note for a person to review. Sending the same day again changes nothing.

For sites on the **Kitchen Safety Bundle**, CyberLogix also **signs** each
report with a secret both apps share (section 3.5). While a workspace
receives validly signed reports it gets OmniArmor **Pro at no charge**: the
bundle includes it. An unsigned report does everything else the same.

## 2. The connection key

- Made by the workspace **owner** only, in Settings, Connections: **Create
  CyberLogix connection key**. It looks like `clx_` followed by 43 URL-safe
  characters (`A-Z a-z 0-9 - _`), 47 characters in all.
- Shown **once**, on the page right after it is made. OmniArmor stores only a
  SHA-256 hash of it (as it does for invite and password reset links), so it
  can never show it again. The page shows its last 4 characters afterwards.
- **One active key per workspace.** **Regenerate key** makes a new one and
  the old one stops working at once. **Revoke key** stops it with no
  replacement. Either way, requests with the old key get `401`.
- The key identifies the workspace. CyberLogix sends no workspace id: a
  report always goes to the workspace that owns the key.
- Store it as a secret on the CyberLogix side (encrypted at rest, never in
  logs, never in a URL).

## 3. The request

```
POST /api/connect/cyberlogix/daily
Host: omniarmor.example.com
Authorization: Bearer clx_...the key...
Content-Type: application/json
X-CyberLogix-Signature: t=1763110800,v1=5f8a...64 hex characters...
```

The `X-CyberLogix-Signature` header is only for sites on the Kitchen Safety
Bundle (section 3.5). Leave it out for every other site.

- HTTPS only. JSON only (`Content-Type: application/json`, UTF-8).
- The body is at most **32 KB**.
- No cookie and no CSRF token: the key in the `Authorization` header is the
  only authentication. (The signature of section 3.5 is not authentication:
  it only decides whether the report counts toward the bundle.) This address is the only one in OmniArmor, beside
  Stripe's signed webhook, that takes a POST without a form token.
- Send one report per day, after the site's local day has ended (a few
  minutes after midnight at the site is good). Resending is safe (section 6).

### 3.1 The body

| Field | Type | Required | Rules |
|---|---|---|---|
| `date` | string | yes | The site's local day the report covers, `YYYY-MM-DD`. From 31 days before today to tomorrow, by the workspace's timezone in OmniArmor. |
| `site` | string or null | no | A short name for the site, such as `"Main kitchen"`. 1 to 60 characters, no line breaks. |
| `units_total` | integer | yes | How many fridges and freezers CyberLogix watches at the site. 1 to 500. |
| `units_in_range_all_day` | integer | yes | How many of them stayed in range the whole day. 0 to `units_total`. |
| `breaches` | array | yes | Every time a unit went out of range that day; `[]` when there were none. At most 50. See 3.2. |
| `warmest_reading` | number | on a clean day | The warmest temperature any unit read that day, while in range. **Required when every unit stayed in range** (`breaches` is `[]` and `units_in_range_all_day` equals `units_total`): it is the reading the temperature check gets. Optional otherwise. -100 to 250. |
| `unit_of_measure` | string | with `warmest_reading` | `"°F"` or `"°C"` (`"F"` and `"C"` are accepted). Required whenever `warmest_reading` is sent. |
| `log_url` | string or null | no | An `https://` link to the day's log in CyberLogix, for an inspector. At most 500 characters, no spaces, and no user name or password in it. OmniArmor shows it as a link and never fetches it. |

**Consistency rules.** With one or more breaches, `units_in_range_all_day`
must be less than `units_total`, and the number of different units named in
`breaches` can't be more than `units_total - units_in_range_all_day`.

Unknown fields are ignored and not stored. Leave them out.

### 3.2 A breach

| Field | Type | Required | Rules |
|---|---|---|---|
| `unit` | string | yes | The unit's name in CyberLogix, such as `"Walk-in freezer"`. 1 to 60 characters, no line breaks. Name units by what they are, never after a person. |
| `started_at` | string | yes | When it went out of range: ISO 8601 date and time **with its UTC offset**, in the site's local time, such as `"2026-11-12T02:10:00-05:00"` (`Z` for UTC works too). Its date must be the report's `date`, or a day either side. |
| `ended_at` | string or null | yes (may be null) | When it came back in range, in the same form. `null` if it was still out of range when the report was sent. At or after `started_at`, and at most 48 hours later. |
| `peak` | number | yes | The worst temperature reached during the breach. -100 to 250. |
| `limit` | number | yes | The unit's limit in CyberLogix that it went past. -100 to 250. |
| `unit_of_measure` | string | yes | `"°F"` or `"°C"` (`"F"` and `"C"` are accepted), for `peak` and `limit`. |
| `acknowledged_by_role` | string or null | yes (may be null) | Who acknowledged the alarm, as a **role, never a name**. `null` if nobody has. One of the list below. |
| `action` | string or null | yes (may be null) | What was done, as one code from the list below. `null` if nothing is recorded. |

**Roles** (`acknowledged_by_role`), exactly as written: `owner`, `manager`,
`chef`, `shift lead`, `on-call staff`, `kitchen staff`, `maintenance`,
`technician`.

**Actions** (`action`), and the words OmniArmor's note uses for them:

| Code | In the note |
|---|---|
| `moved_food` | food moved to another unit |
| `discarded_food` | food discarded |
| `checked_food` | food temperature checked |
| `closed_door` | door closed |
| `adjusted_unit` | unit settings adjusted |
| `called_technician` | technician called |
| `defrost_cycle` | defrost cycle, no action needed |
| `monitoring` | being monitored |
| `none` | no action yet |

Any other role or action is refused with `422`. This is how OmniArmor keeps
names out: a report carries temperatures, unit names and roles only.

### 3.3 Example: a clean day

```json
{
  "date": "2026-11-12",
  "site": "Main kitchen",
  "units_total": 7,
  "units_in_range_all_day": 7,
  "breaches": [],
  "warmest_reading": 38.5,
  "unit_of_measure": "°F",
  "log_url": "https://cyberlogix.example.com/logs/2026-11-12"
}
```

### 3.4 Example: a day with a breach

```
{
  "date": "2026-11-12",
  "site": "Main kitchen",
  "units_total": 7,
  "units_in_range_all_day": 6,
  "breaches": [
    {
      "unit": "Walk-in freezer",
      "started_at": "2026-11-12T02:10:00-05:00",
      "ended_at": "2026-11-12T02:45:00-05:00",
      "peak": 41,
      "limit": 0,
      "unit_of_measure": "°F",
      "acknowledged_by_role": "on-call staff",
      "action": "checked_food"
    }
  ],
  "warmest_reading": 38.5,
  "unit_of_measure": "°F",
  "log_url": "https://cyberlogix.example.com/logs/2026-11-12"
}
```

### 3.5 The signature (Kitchen Safety Bundle)

CyberLogix customers pay CyberLogix for the Kitchen Safety Bundle, and it
includes OmniArmor Pro for that location. A signed report is CyberLogix's
statement that the site is on the bundle. **Sign only the reports of sites
on the bundle**, and stop signing the day a site leaves it.

**The secret.** One value, `KITCHEN_BUNDLE_SECRET`, set on both apps (the
same value; at least 32 random bytes, for example
`python3 -c "import secrets; print(secrets.token_hex(32))"`). It is not the
connection key: the key says which workspace, the secret proves the report
came from CyberLogix's own servers. Keep it on the server side only.

**The header**, exactly:

```
X-CyberLogix-Signature: t=<unix seconds>,v1=<hex HMAC-SHA256(secret, f"{t}.{raw_request_body_bytes}")>
```

- `t` is the time of signing, in whole Unix seconds (UTC), in plain digits.
- The signed message is the bytes of `t` as written in the header, a dot
  (`.`), then **the raw request body, byte for byte as sent**: sign the exact
  bytes you put on the wire, after serializing the JSON, never a re-encoded
  copy. In Python:

  ```python
  body = json.dumps(report).encode("utf-8")
  t = int(time.time())
  v1 = hmac.new(secret.encode(), str(t).encode() + b"." + body, hashlib.sha256).hexdigest()
  headers["X-CyberLogix-Signature"] = f"t={t},v1={v1}"
  # then send `body` itself as the request body
  ```

- `v1` is the HMAC-SHA256 as 64 lowercase hex characters.
- Sign each request when you send it, retries included: a retry gets a new
  `t` and a new `v1`.

**What OmniArmor checks** (`check_signature` in `omniarmor_app/connections.py`):

1. `KITCHEN_BUNDLE_SECRET` is set. Unset, no report counts.
2. The header is there, with one `t` and a `v1`.
3. `t` is within **300 seconds** of OmniArmor's clock, either way. Keep the
   server clock right (NTP).
4. `v1` matches the HMAC of `t` and the raw body bytes it received, compared
   in constant time.
5. **Replays.** A signature accepted once is remembered for **10 minutes**
   (longer than the 300-second window on both sides), across all workspaces;
   the same signature again does not count. After that its `t` is stale. The
   report's own per-date idempotency (section 6) would already make a
   replayed report change no readings, but it would still renew the bundle,
   so OmniArmor keeps the signatures too.

Only a report that passes all five, and is accepted (`200`), counts. Counting
records the time it arrived.

**A report without a valid signature is still processed exactly as before**:
no header, a wrong or malformed `v1`, a stale `t`, a replayed signature, or
the secret unset on OmniArmor's side. Clean days still tick and breaches
still leave notes. It just doesn't count toward the bundle. The signature
never turns a request into an error: the answer says what OmniArmor made of
it (section 5.1, `signature`).

**The bundle's cover**, from the arrival time of the last report that counted:

| Since the last signed report | The workspace gets |
|---|---|
| 3 days or less | Pro, at no charge ("Pro included with your Kitchen Safety Bundle" in Settings) |
| 3 to 10 days | Pro still, for a 7-day grace period, with a banner on every page |
| more than 10 days | the usual rules: its trial, its own plan, or read-only |

A covered workspace can add the Academy with OmniArmor's Plus, paying only
the difference between Plus and Pro.

## 4. What a report does

OmniArmor looks for the workspace's **temperature-log checks**: the checks
about fridge, freezer and cold-holding temperatures, in the industries the
workspace tracks. Today there is one in the catalog:

| Industry | Check | Limit |
|---|---|---|
| RestoArmor (Restaurants) | Cold holding at 41°F or below (`cold_holding`, FDA Food Code 3-501.16(A)(2)) | 41°F, warns from 40°F |

Then, for each one:

**A clean day ticks the check.** Every unit stayed in range all day
(`breaches` is `[]` and `units_in_range_all_day` equals `units_total`). The
check's reading becomes `warmest_reading` (converted to °F if sent in °C,
to one decimal), saved through the same code as a person's Save on the
industry page. The audit trail shows it from "CyberLogix", for example
"From CyberLogix: 7 of 7 units in range all day on 2026-11-12; Cold holding
at 41°F or below set to the warmest reading, 38.5°F". The check itself shows
"Connected to CyberLogix · last report 2026-11-12" and "From CyberLogix: 7
of 7 units in range all day on 2026-11-12; warmest 38.5°F". OmniArmor judges that reading against its own limit, so a warmest
reading of 40°F shows as a Warning and one over 41°F as Blocked, whatever
the unit's limit in CyberLogix is.

A clean day **does not** change the reading, and is recorded as confirming
the day instead (result `confirmed`), when:

- someone on the team saved a reading on that check on the report's date or
  later (by the workspace's timezone): a person's reading stands; or
- a report for a later date has already arrived for that check: an older day
  never overwrites a newer one.

**A day with a breach adds a note and ticks nothing.** Any breach, or fewer
units in range all day than `units_total` (even with no breach details),
leaves the reading as it was and puts a note on the check for a person to
review, for example:

> CyberLogix: 1 breach on Walk-in freezer, 02:10–02:45, peak 41°F (limit
> 0°F); acknowledged by on-call staff; food temperature checked. 6 of 7
> units in range all day.

Times are shown in the offset CyberLogix sent (the site's clock). The note
shows on the check with the report's date, the site and the `log_url` link,
until someone presses **Mark reviewed**. The audit trail records the same
note, with the report's date, from "CyberLogix", and who reviewed it.

**The status.** Once a report arrives, the temperature checks and Settings
show "Connected to CyberLogix · last report 2026-11-12" (the newest `date`
received). Before that they show "Kitchen Safety Bundle: let CyberLogix fill
this in automatically", with a link to Connections.

## 5. Responses

Every answer is JSON, with `Cache-Control: no-store`.

### 5.1 `200 OK`

```
{
  "ok": true,
  "date": "2026-11-12",
  "matched_checks": 1,
  "ticked": 1,
  "noted": 0,
  "unchanged": 0,
  "checks": [
    {"industry": "RestoArmor", "check": "cold_holding",
     "title": "Cold holding at 41°F or below", "result": "ticked"}
  ],
  "signature": "valid",
  "bundle_counted": true
}
```

`signature` says what OmniArmor made of `X-CyberLogix-Signature`, and
`bundle_counted` whether this report renewed the Kitchen Safety Bundle's
cover (section 3.5):

| `signature` | Meaning | `bundle_counted` |
|---|---|---|
| `valid` | Signed correctly, first time seen. | `true` |
| `missing` | No header. Right for a site not on the bundle. | `false` |
| `invalid` | Malformed, or `v1` doesn't match the body: check the secret, and that you sign the exact bytes you send. | `false` |
| `stale` | `t` is more than 300 seconds from OmniArmor's clock. Check the clock, and sign at send time. | `false` |
| `replayed` | This exact signature was already accepted. Sign each retry afresh. | `false` |
| `not_configured` | OmniArmor has no `KITCHEN_BUNDLE_SECRET` yet. | `false` |

Log anything but `valid` and `missing` for a bundle site and alert the
CyberLogix team: the site's included Pro depends on it.

`result` for each check is one of:

| `result` | Meaning |
|---|---|
| `ticked` | Clean day: the reading was saved (or was already this report's reading). |
| `confirmed` | Clean day, but a person's reading or a later day's report stands (section 4). |
| `note` | Breach or units not confirmed: a note was added or replaced; nothing ticked. |
| `unchanged` | This exact report was already received for this date: nothing changed. |

**No temperature check.** When the workspace tracks no industry with a
temperature-log check, the report is still accepted (and the status shows it
arrived), and the answer is:

```
{"ok": true, "date": "2026-11-12", "matched_checks": 0, "ticked": 0, "noted": 0,
 "unchanged": 0, "checks": [],
 "hint": "This workspace tracks no temperature-log check, so nothing was filled in. ..."}
```

Treat `matched_checks: 0` as success, not an error. Show the `hint` to the
CyberLogix user if you like; don't retry.

### 5.2 Errors

Every error has the same shape. Nothing is changed by a request that gets an
error.

```
{"ok": false, "error": "invalid_payload", "message": "Some fields are missing or out of range; nothing was changed.",
 "errors": [{"field": "breaches[0].acknowledged_by_role", "problem": "null or one of: owner, manager, ..."}]}
```

| Status | `error` | When | What CyberLogix should do |
|---|---|---|---|
| `400` | `invalid_json` | The body isn't valid JSON (UTF-8). | Fix the request. Don't retry as is. |
| `401` | `unauthorized` | No `Authorization: Bearer` header, or the key is wrong, revoked or replaced. Comes with `WWW-Authenticate: Bearer`. | Stop sending. Ask the user for a new key from OmniArmor (Settings, Connections). |
| `405` | `http_405` | Not a POST. | Fix the request. |
| `413` | `payload_too_large` | The body is over 32 KB. | Fix the request. |
| `415` | `unsupported_media_type` | `Content-Type` isn't `application/json`. | Fix the request. |
| `422` | `invalid_payload` | A field is missing, the wrong type or out of range, or the counts don't add up. `errors` lists every problem, with `field` (like `date` or `breaches[0].peak`) and `problem`. | Fix the data. Don't retry as is. |
| `429` | `rate_limited` | Too many requests (section 7). Comes with `Retry-After` in seconds. | Wait at least `Retry-After`, then retry. |
| `500` | `http_500` | Something broke in OmniArmor. | Retry later with backoff (section 6 makes it safe). |
| `503` | `http_503` | OmniArmor is briefly unavailable. | Retry later with backoff. |

## 6. Idempotency and corrections

A report is kept **per workspace, check and date**.

- **The same report again changes nothing**: no reading, no note, no audit
  row; every check answers `unchanged`. Retrying after a timeout or a `5xx`
  is always safe.
- **A corrected report for the same date** (anything in it different)
  replaces the earlier one:
  - its note replaces the earlier note, and a changed note needs a new review;
  - a corrected clean day after a breach day ticks the check and clears the
    note, unless a person's reading stands (section 4);
  - a corrected report **never takes a reading away**, and never overwrites a
    reading someone on the team saved that day or later. A correction from
    clean to breach leaves the reading in place and adds the note for a
    person to review.
- Reports for **different dates** are separate. An older date never
  overwrites the reading a newer date set.
- Two copies of one report arriving at the same moment are applied once.
- One report per workspace per day: a workspace with several sites should
  send one combined report a day (or each site connects its own workspace).
  A second, different report for the same date counts as a correction.

## 7. Rate limits

| Limit | Applies to | Over it |
|---|---|---|
| 60 requests an hour | each connection key | `429`, `Retry-After: 3600` |
| 120 requests an hour | each IP address, all requests | `429`, `Retry-After: 3600` |
| 10 wrong or revoked keys in 15 minutes | each IP address | `429`, `Retry-After: 900`, for every request from that address, even with the right key |

One report a day, plus retries, is far inside these. The counts are deleted
within 2 days.

## 8. Privacy

- A report carries temperatures, unit and site names, times and roles. Never
  send a person's name, email or phone number, in any field. Roles and
  actions come from fixed lists, so names can't arrive there; keep unit and
  site names free of names too.
- OmniArmor keeps each report's result (the reading, the note, the site and
  the log link) in the workspace until the workspace is deleted. Unknown
  fields are dropped.
- For rate limiting, OmniArmor notes the IP address a request came from, and
  deletes it within 2 days, as for sign-in attempts.
- OmniArmor's Privacy page (`/privacy`) says this in one line.

## 9. Checklist for the CyberLogix side

1. A place for the user to paste the OmniArmor connection key, stored as a
   secret, with a way to replace and remove it.
2. A daily job per connected site, after the site's local midnight: build the
   body of section 3, send it, and log the `result` per check (not the key).
3. On `401`: stop and tell the user to make a new key. On `422`: log the
   `errors` and alert the CyberLogix team; it is a bug. On `429`, `5xx` or a
   network error: retry with backoff; it is safe.
4. Map CyberLogix's people to the roles in 3.2 and its actions to the codes;
   never send names.
5. Test against a staging copy of OmniArmor (docs/STAGING.md) with a
   workspace that tracks RestoArmor.
6. For sites on the Kitchen Safety Bundle: sign every report (section 3.5)
   with `KITCHEN_BUNDLE_SECRET`, at send time, over the exact body bytes;
   expect `"signature": "valid"` and `"bundle_counted": true`, and alert on
   anything else. Stop signing when a site leaves the bundle.
