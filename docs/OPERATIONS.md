# Running OmniArmor

OmniArmor is built to run on its own. Once it's deployed, a built-in daily job
sends reminders, backs up the database and cleans up old data with no one
touching it. This guide covers the few things a person has to do once.

## 1. Launch (about 15 minutes)

**The address.** OmniArmor is a product of MTRX Horizyn, and MTRX Horizyn owns
the one domain: its own site is on the domain itself (and `www`), and each
product gets a subdomain. OmniArmor lives at `omniarmor.<your domain>`, beside
`cyberlogix.<your domain>` and `rankup.<your domain>`. Below, `example.com`
stands for that domain. There is no domain to buy for OmniArmor.

A subdomain, not a folder (`example.com/omniarmor`), on purpose: each
subdomain is its own origin, so OmniArmor's sign-in cookie, the browser's
storage for it and anything it installs stay with OmniArmor and never reach
the other apps. The app keeps it that way: its cookie has no `Domain`, so it
goes back only to `omniarmor.example.com`, and it sends no CORS headers, so no
other site (a sibling app included) can read its pages from a browser.

1. **DNS:** where the domain's DNS is managed, add one record for the
   subdomain. On Render, a `CNAME` named `omniarmor` pointing at the service's
   `onrender.com` address; on your own server, an `A` record named
   `omniarmor` pointing at its IP address.
2. **The host:** Render: the service, then Settings > Custom Domains, add
   `omniarmor.example.com` and wait for it to verify. Your own server: set
   `DOMAIN=omniarmor.example.com` in `.env` for Caddy.
3. **HTTPS:** Render and Caddy both get the certificate themselves once DNS
   answers. Check `https://omniarmor.example.com` opens before going on: the
   sign-in cookie is marked secure in production and needs it.
4. **The app:** set `BASE_URL=https://omniarmor.example.com` (no slash at the
   end). Every link in an email is built from it.
5. **MTRX Horizyn:** in MTRX Horizyn's settings, OmniArmor's address is
   `https://omniarmor.example.com` and its stats address is
   `https://omniarmor.example.com/api/stats` (see `STATS_KEY`). It answers
   only a request carrying that key (`Authorization: Bearer <STATS_KEY>`),
   and doesn't exist without it: the number of accounts, how many were used
   in the last 30 days, and the daily usage counts (section 5).

**Render (easiest):** push this repo to GitHub, then in Render choose
New > Blueprint and pick the repo. `render.yaml` creates the web service, a
persistent disk for the database, and a random `SECRET_KEY`. Then add the
custom domain and set `BASE_URL` as above.

**Cheapest (one small server, even a free-tier VM):** set `SECRET_KEY`,
`BASE_URL` and `DOMAIN` in `.env`, add the subdomain's DNS record, and run
`docker compose up -d`. Caddy adds free HTTPS. See [COSTS.md](COSTS.md).

**Any server with Docker:**

```sh
docker build -t omniarmor .
docker run -d --name omniarmor -p 8000:8000 -v omniarmor-data:/data \
  -e SECRET_KEY="$(python3 -c 'import secrets; print(secrets.token_hex(32))')" \
  -e BASE_URL=https://omniarmor.example.com \
  --restart unless-stopped omniarmor
```

Put it behind HTTPS (Render does this for you; on your own server use Caddy or
nginx with Let's Encrypt). Sign-in cookies are marked secure in production, so
the app must be served over HTTPS.

## 2. Turn on email

Without email settings, reminders and password-reset links are saved on the
app's Reminders page instead of sent. To send real email, sign up with any
SMTP provider (Postmark, SendGrid, Amazon SES, Mailgun), verify your sending
domain, and set `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD` and
`MAIL_FROM`. Failed sends are logged on the Reminders page with the reason.

All of MTRX Horizyn's apps send from its one domain, so the records that keep
mail out of spam are set up once, on that domain, by whoever runs it: **SPF**
(which servers may send for it), **DKIM** (a signature on each message) and
**DMARC** (what to do with mail that fails those two). The email provider
gives the exact values. OmniArmor then sends from an address of its own, such
as `MAIL_FROM=OmniArmor <no-reply@omniarmor.example.com>`, so people can tell
the apps apart. A sending subdomain like `omniarmor.example.com` must be
verified with the provider too (it adds a DKIM record for it); the parent
domain's DMARC covers it. Check the records with any free DMARC checker before
real customers depend on reminders. Every email ends with "OmniArmor is a
product of MTRX Horizyn."

The public Help page (`/help`) answers common questions. Set `SUPPORT_EMAIL`
to an address people can write to, and its last answer names it; without it,
the page points only to the help inside the app.

## 3. What runs by itself every day

After `DAILY_JOB_HOUR_UTC` (default 11:00 UTC), once per day:

1. **Reminders.** Each company's team gets one digest listing checks that are
   30, 7 or 1 day from due, due today, or overdue (the first day, then weekly).
   The same reminder is never sent twice for the same due date.
2. **Cleanup.** Old sign-in failures, used reset links and expired invites are
   removed.
3. **Backup.** A consistent copy of the database goes to `BACKUP_DIR`; the
   newest `BACKUP_KEEP` copies are kept. It is taken last, so it holds the
   day's reminders as sent, and restoring it never sends them again.

Every minute, the same timer also sends **time-limit alerts** for the hour
and minute clocks (such as a 1-hour or 8-hour report deadline): one email when
a clock reaches its warning point and one when it becomes overdue. The alerts
run in a thread of their own, so a long daily run never holds them up.

Several server processes can run at once: each sweep (the alerts, the daily
job, Autopilot) holds a lock in the database while it runs, so no two
processes run the same one at once however long it takes, and each day's run
and each alert is claimed in the database too, so it only happens once. To
run it by hand: `flask --app wsgi run-daily --force` (it says so and does
nothing if the server is running it right then). How long the sweeps take
with many companies: [LOAD-TEST.md](LOAD-TEST.md).

## 4. Backups and restore

Backups are files named `omniarmor-YYYYMMDD-HHMMSS-*.db` (the time in UTC) in
`BACKUP_DIR`, `/data/backups` in the Docker image. Each one is checked before
it gets that name and is a single file, so it can be copied and restored on
its own. To make one now: `flask --app wsgi backup` (on Docker,
`docker compose exec app flask --app wsgi backup`; on Render, in the
service's Shell tab). Copy them off the server regularly (for example, a
nightly sync to cloud storage), because a backup on the same disk doesn't
survive losing the disk.

### Restore checklist (about 10 minutes)

The backup goes into a fresh file beside the current database, and the app is
pointed at it. The current database is left as it is, so going back is one
setting. Rehearsed end to end in [LOAD-TEST.md](LOAD-TEST.md), section 3, and
by `tests/test_operations.py` (`TestRestoreRehearsal`).

Below, `run` means the command on the server: `docker compose exec app ...`
with Docker Compose, the Shell tab on Render, or a shell on any other host.

1. **Pick the backup (1 min).** `run ls -l /data/backups`. Take the newest
   one from before the problem started. Everything after it is lost.
2. **Copy it to a fresh file (1 min).** With today's date in the name:
   `run cp /data/backups/omniarmor-20261103-110012-123456.db /data/omniarmor-restored-20261103.db`.
   Never copy over the database the app is using while it runs.
3. **Check the copy (1 min).**
   `run python -c "import sqlite3; print(sqlite3.connect('/data/omniarmor-restored-20261103.db').execute('PRAGMA integrity_check').fetchone()[0])"`
   must print `ok`. Anything else: pick an older backup and go back to step 2.
4. **Point the app at it (2 min).** Set `DATABASE_PATH=/data/omniarmor-restored-20261103.db`:
   in `.env`, then `docker compose up -d` (it restarts the app with the new
   setting); on Render, under Environment, then save (it redeploys). Leave
   `BACKUP_DIR` as it is. The app upgrades an older backup's schema by
   itself as it starts.
5. **Check it works (3 min).** `/healthz` answers `"status": "ok"`. Sign in
   (passwords and sessions are as they were at the backup). Open an industry
   page and see its readings, the Vault (the audit trail ends at the backup's
   time), and the Academy with each learner's progress.
6. **Tell the customers (2 min)** what was lost: every change made after the
   backup's time has to be entered again. Reminders already sent are not
   sent again.
7. **Afterwards.** Keep the old database file for a week, in case something
   in it is needed, then delete it. To go back to it, set `DATABASE_PATH` back.

Restoring over the same file instead (stop the app, copy the backup over
`DATABASE_PATH`) also works, but delete the `-wal` and `-shm` files next to
the database **before** starting the app again, or SQLite replays the old
database's last changes onto the restored copy. With Docker, the volume can
only be reached through a container, so the fresh-file way above is simpler.

## 5. Monitoring

**Autopilot** watches the service for you, so you don't have to check it every
day. Set `OPERATOR_EMAIL` (and email, section 2) and it runs every 10 minutes:

| It fixes by itself | It emails you |
|---|---|
| Re-sends emails that failed (after 10 minutes, 1 hour, 6 hours) | Emails still failing after every retry |
| Makes a backup if the newest one is over a day old | Backups failing even after it tried |
| Trims old logs and compacts the database file | The daily job hasn't finished in 2 days |
| | 5 or more server errors in an hour |
| | Under 1 GB (or 5%) disk space left |
| | Database damage (checked daily) |
| | Email not set up in production |

Each big problem is emailed once, with what to do. While it lasts you get one
reminder a day, and a "Fixed" email when it clears up. One that comes back
within the hour is not emailed again, and Autopilot never sends more than 10
emails an hour. On Mondays you get a
short report of what it fixed, only if it fixed something. To stop the
weekly report, sign up (or sign in) with the `OPERATOR_EMAIL` address and
untick it under Settings, "Your reminder emails"; problems are still emailed. Without
`OPERATOR_EMAIL`, the same messages go to the server log.

- `flask --app wsgi autopilot` runs the checks now and prints what it found.
- `flask --app wsgi autopilot --log` shows what it fixed and reported in the last 30 days.

**Error reports to one inbox (optional).** Set `ERRORS_EMAIL` to an address
and every page that fails with an unexpected error (a 500) sends it a short
report straight away: the time (UTC), the version, the request's method and
path with the query string removed, the kind of error, its message and the
stack trace, with file paths relative to the project (`omniarmor_app/views.py`,
`flask/app.py`). It carries no personal data: never the request's body,
form, cookies, headers or IP address, nor who was signed in, and anything in
the path or message that looks like an email address, an IP address, a token
or a secret is replaced (`[email]`, `[ip]`, `[token]`, `[hidden]`).

- **Limits:** one email per distinct error an hour (the same fingerprint
  Autopilot uses) and at most 20 in any 24 hours. They are kept in the
  database, so a restart or a second server process doesn't reset them.
- **Delivery:** like every email, through the outbox (the notifications
  table). It is sent from a thread, so the error page isn't held up; if the
  send fails, or the server stops first, Autopilot sends it again (after 10
  minutes, 1 hour, 6 hours). Without email set up (section 2) the reports
  are kept in the database, not sent. Copies are deleted after 30 days, like
  Autopilot's own error records.
- **Off when unset:** without `ERRORS_EMAIL` nothing is written or sent.
- It adds to Autopilot, it doesn't replace it: every crash is still
  recorded and Autopilot still emails `OPERATOR_EMAIL` about new bugs. The
  two can be the same address.

**Usage counts.** OmniArmor counts how often a few features are used, one
total per feature per day (UTC): checks updated (one at a time or in bulk),
bulk updates, lessons started (a lesson page opened) and passed,
certificates earned, Help page views and sign-ups. Nothing else is kept: no
cookie, no account, workspace or learner id, no IP address, and no outside
analytics service. The last 30 days are on the Settings page of the account
signed in with the `OPERATOR_EMAIL` address (nobody else sees them), and in
`/api/stats` under `usage`. Totals older than 400 days are deleted by the
daily job.

`GET /healthz` returns `{"status": "ok", "schema": ..., "version": "..."}`
with HTTP 200 when the app and database are working: the schema version and
the release (from `omniarmor_app/version.py`), and nothing else. Point an uptime monitor (UptimeRobot, Better Stack) at
it so you get a text or email if the site goes down. The server log records
each daily run and any failure.

## 6. A demo workspace

For screenshots and sales calls, one command makes a believable workspace
with made-up names: Juniper Lane Pharmacy, tracking Pharmacies and Employers
& HR, with an owner and a pharmacist on the team, checks done, coming due and
overdue, a few weeks of audit trail, the morning's reminder digest in Radar
(kept, never sent), an Academy with two learners partway through (one with a
certificate) on the Academy plan, and Autopilot's history with one real pass
run at the end (which makes the first backup).

```sh
flask --app wsgi seed-demo --force demo/omniarmor-demo.db     # a new file of its own
DATABASE_PATH=demo/omniarmor-demo.db flask --app wsgi run --port 8000
```

It prints the two sign-in addresses (on the reserved `.example` domain,
which never receives email) and a random password for both; `--password`
sets your own. It never mixes into real data:

- Without `--force` it seeds the app's own database only if that holds no
  accounts, workspaces or learners at all, and checks again inside the
  write, so a sign-up at the same moment is never mixed in.
- `--force` must name a new or empty file, never the database the app uses.
- In production (`OMNIARMOR_ENV=production`) it refuses the app's own
  database even when it is empty, since a new deployment's empty database is
  about to become the real one. Seed a separate file there, such as
  `--force /data/omniarmor-demo.db`, and run a separate service on it.

The dates are counted from the day it is seeded, so seed a fresh file before
each demo.

## 7. Upgrades

Deploy the new version; the database schema upgrades itself at start-up.
Back up first. Run the tests before every deploy: `python3 -m unittest
discover -s tests` (GitHub Actions does this on every push).

## 8. Things only you can do

- Form the company, MTRX Horizyn (see the README), and open a business bank
  account.
- Get a lawyer to write your Terms of Service and Privacy Policy, and to
  review the rule catalog before you sell to customers.
- Payments: the Academy plan already takes cards through Stripe (set the
  Stripe settings, and in Stripe add the webhook
  `https://omniarmor.<your domain>/billing/stripe/webhook` with the events
  `checkout.session.completed`, `customer.subscription.created`,
  `customer.subscription.updated`, `customer.subscription.deleted` and
  `invoice.payment_failed`). Charging for the compliance service itself is
  not built yet.
- Add the `omniarmor` subdomain on MTRX Horizyn's domain and point it at the
  app (section 1). OmniArmor has no domain of its own.
