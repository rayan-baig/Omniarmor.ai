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
   `https://omniarmor.example.com/api/stats` (see `STATS_KEY`).

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

## 3. What runs by itself every day

After `DAILY_JOB_HOUR_UTC` (default 11:00 UTC), once per day:

1. **Reminders.** Each company's team gets one digest listing checks that are
   30, 7 or 1 day from due, due today, or overdue (the first day, then weekly).
   The same reminder is never sent twice for the same due date.
2. **Backup.** A consistent copy of the database goes to `BACKUP_DIR`; the
   newest `BACKUP_KEEP` copies are kept.
3. **Cleanup.** Old sign-in failures, used reset links and expired invites are
   removed.

Every minute, the same timer also sends **time-limit alerts** for the hour
and minute clocks (such as a 1-hour or 8-hour report deadline): one email when
a clock reaches its warning point and one when it becomes overdue.

Several server processes can run at once: each day's run, and each alert, is
claimed in the database first, so it only happens once. To run it by hand:
`flask --app wsgi run-daily --force`.

## 4. Backups and restore

Backups are files named `omniarmor-YYYYMMDD-HHMMSS-*.db` in `BACKUP_DIR`. Each one is checked
before it gets that name and is a single file, so it can be copied and restored on its own.
Copy them off the server regularly (for example, a nightly sync to cloud
storage), because a backup on the same disk doesn't survive losing the disk.

To restore: stop the app, copy the chosen backup over `DATABASE_PATH`, delete
any `omniarmor.db-wal` and `omniarmor.db-shm` files next to it, and start
the app again.

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

`GET /healthz` returns `{"status": "ok", "schema": ..., "version": "..."}`
with HTTP 200 when the app and database are working: the schema version and
the release (from `omniarmor_app/version.py`), and nothing else. Point an uptime monitor (UptimeRobot, Better Stack) at
it so you get a text or email if the site goes down. The server log records
each daily run and any failure.

## 6. Upgrades

Deploy the new version; the database schema upgrades itself at start-up.
Back up first. Run the tests before every deploy: `python3 -m unittest
discover -s tests` (GitHub Actions does this on every push).

## 7. Things only you can do

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
