# Running OmniArmor

OmniArmor is built to run on its own. Once it's deployed, a built-in daily job
sends reminders, backs up the database and cleans up old data with no one
touching it. This guide covers the few things a person has to do once.

## 1. Launch (about 15 minutes)

**The address.** OmniArmor is a product of MTRX Horizyn, and MTRX Horizyn owns
the one domain: its own site is on the domain itself (and `www`), and each
product gets a subdomain. The domain is `mtrxhorizyn.com`, and OmniArmor lives
at `omniarmor.mtrxhorizyn.com`, beside `cyberlogix.mtrxhorizyn.com` and
`rankup.mtrxhorizyn.com`. There is no domain to buy for OmniArmor.

A subdomain, not a folder (`mtrxhorizyn.com/omniarmor`), on purpose: each
subdomain is its own origin, so OmniArmor's sign-in cookie, the browser's
storage for it and anything it installs stay with OmniArmor and never reach
the other apps. The app keeps it that way: its cookie has no `Domain`, so it
goes back only to `omniarmor.mtrxhorizyn.com`, and it sends no CORS headers, so no
other site (a sibling app included) can read its pages from a browser.

1. **DNS:** where the domain's DNS is managed, add one record for the
   subdomain. On Render, a `CNAME` named `omniarmor` pointing at the service's
   `onrender.com` address; on your own server, an `A` record named
   `omniarmor` pointing at its IP address.
2. **The host:** Render: the service, then Settings > Custom Domains, add
   `omniarmor.mtrxhorizyn.com` and wait for it to verify. Your own server: set
   `DOMAIN=omniarmor.mtrxhorizyn.com` in `.env` for Caddy.
3. **HTTPS:** Render and Caddy both get the certificate themselves once DNS
   answers. Check `https://omniarmor.mtrxhorizyn.com` opens before going on: the
   sign-in cookie is marked secure in production and needs it.
4. **The app:** set `BASE_URL=https://omniarmor.mtrxhorizyn.com` (no slash at the
   end). Every link in an email is built from it.
5. **MTRX Horizyn:** in MTRX Horizyn's settings, OmniArmor's address is
   `https://omniarmor.mtrxhorizyn.com` and its stats address is
   `https://omniarmor.mtrxhorizyn.com/api/stats` (see `STATS_KEY`). It answers
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
  -e BASE_URL=https://omniarmor.mtrxhorizyn.com \
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
as `MAIL_FROM=OmniArmor <no-reply@omniarmor.mtrxhorizyn.com>`, so people can tell
the apps apart. A sending subdomain like `omniarmor.mtrxhorizyn.com` must be
verified with the provider too (it adds a DKIM record for it); the parent
domain's DMARC covers it. Check the records with any free DMARC checker before
real customers depend on reminders. Every email ends with "OmniArmor is a
product of MTRX Horizyn."

The public Help page (`/help`) answers common questions. Set `SUPPORT_EMAIL`
to an address people can write to (live: `help@omniarmor.mtrxhorizyn.com`),
and its last answer names it; without it,
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
weekly report, untick it in the operator's account (below) under Settings,
"Your reminder emails"; problems are still emailed. Without
`OPERATOR_EMAIL`, the same messages go to the server log.

- `flask --app wsgi autopilot` runs the checks now and prints what it found.
- `flask --app wsgi autopilot --log` shows what it fixed and reported in the last 30 days.

Autopilot's emails about a bug carry the error's message and the end of its
traceback, scrubbed the same way as the error reports below: anything that
looks like an email address, an IP address, a token, a secret or a reset or
invite link is replaced, and file paths are relative.

**The operator's account.** One OmniArmor account can be the operator's: its
Settings page shows the usage counts (below) and the switch for the weekly
Autopilot report. Having the `OPERATOR_EMAIL` address is not enough to get
it, because sign-up doesn't check that an address is yours, and a stranger
could register it before you do. You give it on the server, once:

1. Sign up (or sign in) with the `OPERATOR_EMAIL` address.
2. On the server run `flask --app wsgi make-operator you@example.com` with
   that address (on Docker, `docker compose exec app flask --app wsgi
   make-operator you@example.com`; on Render, in the service's Shell tab).

It refuses any other address. It prints when the account was made, its name
and its workspace: if that isn't yours, someone signed up with your address
first. Run it again with `--revoke`, then use "Forgot your password?" with
the address (the link comes to your inbox) and check the account before
giving it again. `--revoke` takes the status away at any time, and if
`OPERATOR_EMAIL` changes, the old account stops counting as the operator
until you run the command for the new address. Emails to `OPERATOR_EMAIL`
(problems, the weekly report) go to that inbox either way: they need no
account.

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
analytics service. The last 30 days are on the Settings page of the
operator's account (above; nobody else sees them), and in
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
run at the end (which makes the first backup, in a folder of its own beside
the demo file: `omniarmor-demo-backups` for `omniarmor-demo.db`, never the
live backups).

```sh
flask --app wsgi seed-demo --force demo/omniarmor-demo.db     # a new file of its own
DATABASE_PATH=demo/omniarmor-demo.db BACKUP_DIR=demo/omniarmor-demo-backups flask --app wsgi run --port 8000
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

A staging copy to try changes on before live, with the demo in it:
[STAGING.md](STAGING.md).

## 7. Upgrades

Deploy the new version; the database schema upgrades itself at start-up.
Back up first. Run the tests before every deploy: `python3 -m unittest
discover -s tests` (GitHub Actions does this on every push).

**Upgrading from 1.1.1 or earlier: one step.** Until 1.1.2 any account with
the `OPERATOR_EMAIL` address was the operator's. After the upgrade no account
is, not even yours, so the usage counts and the weekly report's switch are
gone from Settings (the weekly report itself still goes out). Once the new
version is running, run `flask --app wsgi make-operator you@example.com`
with the `OPERATOR_EMAIL` address (section 5, "The operator's account") and
check that the account it prints is yours.

**Upgrading to 1.2.0:** nothing to do. Schema version 17 adds the tables for
the Kitchen Safety Bundle; CyberLogix reports start once a workspace owner
creates a connection key in Settings, Connections. CyberLogix calls
`https://omniarmor.mtrxhorizyn.com/api/connect/cyberlogix/daily`
([CYBERLOGIX-CONNECTION.md](CYBERLOGIX-CONNECTION.md)); if a firewall or proxy
sits in front of the app, let POSTs to that address through.

**Upgrading to 1.3.0 (Pro and Plus):** schema version 18 runs by itself on
start. What changes for workspaces already there:

- A workspace paying for the old Academy plan keeps it, at its old price,
  with the compliance tracker it had for free, until it changes plan or the
  subscription ends.
- Every other workspace gets the free trial (`ACADEMY_TRIAL_DAYS`, from the
  moment of the upgrade; a later Academy trial end is kept). When it ends
  without a plan, the tracker turns read-only and reminders pause. Tell your
  customers before you deploy.

Before deploying, in Stripe (test mode first, on staging):

1. Make two products, **Pro** and **Plus**, each with a monthly price **per
   unit** (the unit is a location) matching `omniarmor_app/plans.py`, and a
   third price on Plus for **Kitchen Safety Bundle** workspaces: the
   difference between Plus and Pro. Put their ids in `PRO_STRIPE_PRICE`,
   `PLUS_STRIPE_PRICE` and `PLUS_BUNDLE_UPGRADE_STRIPE_PRICE`. Without the
   last one, bundle workspaces are offered Plus at its full price, with a note.
2. In the customer portal settings, allow switching between the Pro and Plus
   monthly prices (and cancelling at the end of the period): "Stripe's
   customer portal" below has every setting. The webhook reads the new price
   and moves the workspace.
3. Keep the webhook's events as they are (section 8).
4. Remove `ACADEMY_PRICE_LABEL` and `ACADEMY_STRIPE_PRICE`: nothing reads
   them now. The old Academy plan's subscriptions keep renewing as they are.

For the Kitchen Safety Bundle, generate `KITCHEN_BUNDLE_SECRET`
(`python3 -c "import secrets; print(secrets.token_hex(32))"`) and set the
same value on CyberLogix. CyberLogix signs the reports of bundle sites with
it ([CYBERLOGIX-CONNECTION.md](CYBERLOGIX-CONNECTION.md), section 3.5); a
workspace whose signed reports arrive gets Pro at no charge. Unset, reports
still fill in the checks and nobody gets the bundle's Pro. To change the
secret, set the new value on both apps at once: reports signed with the old
one stop counting (the 7-day grace period covers a short gap).

By hand, without Stripe: `flask --app wsgi plan <workspace id> pro`, `plus`,
`classroom`, `school` or `none` (the old `academy-plan <id> active` now means
Plus); add `--yearly` for a plan paid yearly (classroom plans always are),
and `--until YYYY-MM-DD` for a plan that stops at the end of that day in the
workspace's timezone, such as a school year paid by invoice. It refuses over
a Stripe subscription that is still running unless you add `--force`.

**Upgrading to 1.4.0 (yearly plans):** schema version 19 runs by itself on
start and marks every subscription already there as monthly. Nothing changes
for anyone until you set the yearly prices; each one left empty keeps that
plan monthly only, and the plan page shows no yearly option for it.

Yearly plans are "pay for 10 months, get 12": the prices are worked out in
`omniarmor_app/plans.py` (10 × the monthly price), so the pages always agree
with the code. In Stripe (test mode first, on staging):

1. **Create 3 yearly prices**, each **per unit** (the unit is a location),
   billed **every year**, in USD:
   - on the **Pro** product: **$500 a year** → its id goes in
     `PRO_YEARLY_STRIPE_PRICE`;
   - on the **Plus** product: **$800 a year** → `PLUS_YEARLY_STRIPE_PRICE`;
   - on the **Plus** product, beside the monthly bundle price: **$300 a
     year**, for Kitchen Safety Bundle workspaces →
     `PLUS_BUNDLE_UPGRADE_YEARLY_STRIPE_PRICE`.
   Check each amount against `plans.py` before saving: Stripe charges what
   the price says, whatever the page shows.
2. Put the three ids in the dashboard settings (`render.yaml` lists them with
   `sync: false`) and redeploy. The plan page, Settings, Help, the landing
   and industry pages then show a Monthly / Yearly switch and the yearly
   prices with "2 months free".
3. **Don't** add the yearly prices to the customer portal's plan switching
   (changed in 1.6.2): the app's plan page switches a monthly plan to yearly
   itself, and refuses while the save offer's discount runs. See "Stripe's
   customer portal" below for the exact portal settings. The webhook reads
   the price either way and sets both the plan and the interval.
4. Keep cancellations **at the end of the billing period**, with **no
   proration on cancel**: a yearly plan stays on to the end of the year paid
   for, with no partial refund, which is what the Help page and Terms say.
   For switches, Stripe's default proration (credit for the unused part of
   the old price on the next invoice) is fine.
5. Keep the webhook's events as they are (section 8).

**Stripe's customer portal (1.6.2):** set it once, in Stripe's dashboard
(Settings → Billing → Customer portal), the same in test mode and live:

- **Payment methods** and **invoice history**: on.
- **Cancel subscriptions**: on, **at the end of the billing period**, with
  **no proration** on cancel (a yearly plan stays on to the end of the year
  paid for, with no partial refund, as Help and the Terms say).
- **Pause subscriptions**: off, if your account shows the option. The app
  pauses a monthly plan itself, for 1, 2 or 3 months.
- **Switch plans**: on, between **Pro and Plus, monthly prices only**: on
  the Pro product only `PRO_STRIPE_PRICE`, on the Plus product only
  `PLUS_STRIPE_PRICE`. Proration on, invoiced at once (the app's own switch
  does the same, `always_invoice`). Do **not** list:
  - the **yearly** prices (`PRO_YEARLY_STRIPE_PRICE`,
    `PLUS_YEARLY_STRIPE_PRICE`, `PLUS_BUNDLE_UPGRADE_YEARLY_STRIPE_PRICE`):
    the plan page switches to yearly itself and refuses while the save
    offer's discount runs, because Stripe takes that discount off every
    invoice in its months, a year's charge too;
  - the **Kitchen Safety Bundle** prices (`PLUS_BUNDLE_UPGRADE_STRIPE_PRICE`
    and its yearly one): only checkout gives them, to a workspace the bundle
    covers;
  - **Classroom** and **Whole school** (`CLASSROOM_YEARLY_STRIPE_PRICE`,
    `SCHOOL_YEARLY_STRIPE_PRICE`): leave their products out of plan
    switching altogether. A school changes between them by writing to
    `SCHOOL_INVOICE_EMAIL`; their subscribers can still update the card,
    see invoices and cancel in the portal.
- A yearly subscriber who picks a monthly price there gets Stripe's credit
  for the unused part of the year on their Stripe balance (credit for later
  invoices, not money back). If you'd rather not allow that, turn **Switch
  plans** off altogether: the plan page still switches Pro to Plus and
  monthly to yearly.

If a switch the app wouldn't allow still arrives (the portal set up
differently, say, and a monthly plan moved to yearly while the save offer's
discount ran), the webhook applies the new plan as Stripe has it, and since
the yearly charge is already made with the discount, nothing in the app can
take it back. Instead it writes "Switched to yearly in Stripe's portal while
the save offer's discount ran" in the workspace's audit trail and a warning
in the log. Settle it in Stripe by hand (an invoice item for the difference,
or leave it as goodwill).

**Upgrading to 1.5.0 (pause, the save offer, upgrade offers, locations,
trade pages):** schema version 20 runs by itself on start: it adds the pause
and save-offer dates to each workspace and the table that remembers which
offers each person was shown. Nothing changes for anyone's plan.

1. **Pausing needs nothing new.** The cancel screen (Plans page, "Cancel or
   pause your plan") pauses a monthly plan through Stripe's
   `pause_collection` (invoices in the pause are voided; Stripe starts
   charging again by itself on the date chosen). The webhook you already
   have (`customer.subscription.updated`) keeps the app in step. Leave
   pausing **off** in Stripe's customer portal: the app does it. A pause
   with no end date (from Stripe's dashboard) is understood since 1.6.2: the
   workspace is paused, read-only, with no end date, until it is lifted.
2. **The save offer:** in Stripe, create a coupon, **25% off**, duration
   **repeating**, **2 months** (Products → Coupons), and put its id in
   `SAVE_OFFER_STRIPE_COUPON`. `SAVE_OFFER_PERCENT` (25) and
   `SAVE_OFFER_MONTHS` (2) are what the screen promises: if you make a
   different coupon, set them to match it. Without a coupon id, the screen
   offers no discount. Each workspace can take it once, ever.
3. **Switching to yearly or to Plus** from the app uses the yearly and Plus
   prices you already set ("Upgrading to 1.4.0"): Stripe charges the
   difference at once, taking off the unused part of the current period
   (`proration_behavior=always_invoice`), and a declined card changes
   nothing (`payment_behavior=error_if_incomplete`).
4. **Cancelling** from the app cancels at the end of the period paid for,
   like the portal; the portal's own cancel button keeps working.
5. The daily job emails each owner 3 days before a pause ends (kind `plan`
   in Radar) and tidies ended pauses. The operator's Settings shows the new
   usage counts: plans paused, save offers taken, plans cancelled, upgrade
   offers shown, plan switches and locations added.

**Upgrading to 1.6.0 (schools):** schema version 21 runs by itself on start:
it adds the `classes` table, `learners.class_id` and each workspace's pilot
dates. Nothing changes for anyone's plan. What's new:

- **SchoolArmor**, industry 51, a checklist for K-12 schools, and the trade
  page `/for/schools`. Nothing to set up.
- **The Academy for classrooms**: a teacher adds a class in the Academy
  (Classes) and students by first name or nickname only. A free pilot of
  `CLASSROOM_PILOT_DAYS` (30) days, once per workspace, no card.
- **Two classroom plans, yearly only**, priced in `omniarmor_app/plans.py`:
  **Classroom, $299 a year** (the whole Academy for one class of up to 35
  students, no tracker) and **Whole school, $1,490 a year** (every class, and
  the tracker for the school).

In Stripe (test mode first, on staging):

1. **Create two products**, **Classroom** and **Whole school**, each with one
   price billed **every year**, in USD, **not per unit** (quantity 1):
   **$299 a year** → its id goes in `CLASSROOM_YEARLY_STRIPE_PRICE`;
   **$1,490 a year** → `SCHOOL_YEARLY_STRIPE_PRICE`. Check each amount
   against `plans.py` before saving.
2. Put the ids in the dashboard settings (`render.yaml` lists them with
   `sync: false`) and redeploy. The classes page then offers "Pay by card".
   Leave one empty and that plan is sold by invoice only.
3. Keep the webhook's events as they are: the webhook reads the plan from
   the price.

**A school that wants an invoice:** it writes to `SCHOOL_INVOICE_EMAIL`
(unset: `SUPPORT_EMAIL`, then help@mtrxhorizyn.com) with the school's name,
the plan and the workspace's name. Send the invoice from your own billing
tool (Stripe Invoicing works too), and once it's paid, on the server:

    flask --app wsgi plan <workspace id> classroom --until 2027-06-30

(`school` for Whole school). The workspace id is in the operator's Settings
or the database. The plan stops by itself at 23:59:59 that day **in the
workspace's own timezone** (1.6.2; it was UTC before); run the command again
with a new date for the next school year. If the school paid by card before,
cancel that Stripe subscription first: a cancelled one is let go when the
plan is set by hand (1.6.1), but over one still running (active, trialing,
past due, unpaid or incomplete) the command refuses and says so, because
Stripe would go on charging and its next update would replace the plan set
by hand. `--force` sets it anyway; the same goes for `academy-plan`.

**From invoice to card:** while an invoiced plan runs, the owner sees "Pay
by card from <its last day>" on the classes page (or the plan page for Pro
and Plus) for the **same** plan. Checkout then starts the card subscription
with Stripe's `trial_end` at the invoiced plan's end, so the first charge is
that day and the school never pays twice (Stripe needs a trial to end at
least 48 hours ahead: an invoiced plan ending sooner gets up to two free
days). Another plan isn't bought that way while the invoiced one runs: the
school writes to `SCHOOL_INVOICE_EMAIL`.

**Upgrading to 1.6.2:** schema version 22 runs by itself on start: it adds
`orgs.pause_open` (a pause in Stripe with no end date) and
`users.pilot_used_at` (the classroom pilot is one per owner), filled in from
the pilots already started. In Stripe, set the customer portal as in
"Stripe's customer portal" above. Nothing else to do. From now on a location
added in Settings starts without a free trial (one per owner), at most 100
classes fit in a workspace, and `plan` refuses over a running Stripe
subscription unless `--force`.

## 8. Things only you can do

- Make your account the operator's, once, on the server: sign up with the
  `OPERATOR_EMAIL` address, then `flask --app wsgi make-operator
  you@example.com` (section 5, "The operator's account"). After an upgrade
  from 1.1.1 or earlier, run it once even if you did nothing before (section 7).
- Form the company, MTRX Horizyn (see the README), and open a business bank
  account.
- Get a lawyer to write your Terms of Service and Privacy Policy, and to
  review the rule catalog before you sell to customers.
- Payments: Pro and Plus take cards through Stripe. Set `STRIPE_SECRET_KEY`,
  `STRIPE_WEBHOOK_SECRET`, `PRO_STRIPE_PRICE`, `PLUS_STRIPE_PRICE` and
  `PLUS_BUNDLE_UPGRADE_STRIPE_PRICE` (section 7, "Upgrading to 1.3.0"), and
  for yearly billing `PRO_YEARLY_STRIPE_PRICE`, `PLUS_YEARLY_STRIPE_PRICE` and
  `PLUS_BUNDLE_UPGRADE_YEARLY_STRIPE_PRICE` ("Upgrading to 1.4.0"), for the
  cancel screen's one-time discount create the coupon and set
  `SAVE_OFFER_STRIPE_COUPON` ("Upgrading to 1.5.0"), for classroom plans
  create the two yearly prices and set `CLASSROOM_YEARLY_STRIPE_PRICE` and
  `SCHOOL_YEARLY_STRIPE_PRICE` ("Upgrading to 1.6.0"; a school can also pay
  by invoice: `SCHOOL_INVOICE_EMAIL`), and
  in Stripe add the webhook
  `https://omniarmor.mtrxhorizyn.com/billing/stripe/webhook` with the events
  `checkout.session.completed`, `customer.subscription.created`,
  `customer.subscription.updated`, `customer.subscription.deleted` and
  `invoice.payment_failed`. The prices people see are in
  `omniarmor_app/plans.py`: change them there and in Stripe together.
- The Kitchen Safety Bundle: set `KITCHEN_BUNDLE_SECRET` to the same value
  as on CyberLogix.
- Add the `omniarmor` subdomain on MTRX Horizyn's domain and point it at the
  app (section 1). OmniArmor has no domain of its own.
