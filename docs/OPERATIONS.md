# Running OmniArmor

OmniArmor is built to run on its own. Once it's deployed, a built-in daily job
sends reminders, backs up the database and cleans up old data with no one
touching it. This guide covers the few things a person has to do once.

## 1. Launch (about 15 minutes)

**Render (easiest):** push this repo to GitHub, then in Render choose
New > Blueprint and pick the repo. `render.yaml` creates the web service, a
persistent disk for the database, and a random `SECRET_KEY`. Set `BASE_URL`
to your public address.

**Cheapest (one small server, even a free-tier VM):** set `SECRET_KEY`,
`BASE_URL` and `DOMAIN` in `.env`, point your domain at the server, and run
`docker compose up -d`. Caddy adds free HTTPS. See [COSTS.md](COSTS.md).

**Any server with Docker:**

```sh
docker build -t omniarmor .
docker run -d --name omniarmor -p 8000:8000 -v omniarmor-data:/data \
  -e SECRET_KEY="$(python3 -c 'import secrets; print(secrets.token_hex(32))')" \
  -e BASE_URL=https://app.example.com \
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

## 3. What runs by itself every day

After `DAILY_JOB_HOUR_UTC` (default 11:00 UTC), once per day:

1. **Reminders.** Each company's team gets one digest listing checks that are
   30, 7 or 1 day from due, due today, or overdue (the first day, then weekly).
   The same reminder is never sent twice for the same due date.
2. **Backup.** A consistent copy of the database goes to `BACKUP_DIR`; the
   newest `BACKUP_KEEP` copies are kept.
3. **Cleanup.** Old sign-in failures, used reset links and expired invites are
   removed.

Several server processes can run at once: each day's run is claimed in the
database first, so it only happens once. To run it by hand:
`flask --app wsgi run-daily --force`.

## 4. Backups and restore

Backups are files named `omniarmor-YYYYMMDD-HHMMSS-*.db` in `BACKUP_DIR`.
Copy them off the server regularly (for example, a nightly sync to cloud
storage), because a backup on the same disk doesn't survive losing the disk.

To restore: stop the app, copy the chosen backup over `DATABASE_PATH`, delete
any `omniarmor.db-wal` and `omniarmor.db-shm` files next to it, and start
the app again.

## 5. Monitoring

`GET /healthz` returns `{"status": "ok"}` with HTTP 200 when the app and
database are working. Point an uptime monitor (UptimeRobot, Better Stack) at
it so you get a text or email if the site goes down. The server log records
each daily run and any failure.

## 6. Upgrades

Deploy the new version; the database schema upgrades itself at start-up.
Back up first. Run the tests before every deploy: `python3 -m unittest
discover -s tests` (GitHub Actions does this on every push).

## 7. Things only you can do

- Form the company (see the README) and open a business bank account.
- Get a lawyer to write your Terms of Service and Privacy Policy, and to
  review the rule catalog before you sell to customers.
- Add payments: OmniArmor doesn't charge cards yet. Stripe Checkout and its
  customer portal are the usual next step.
- Buy your domain and point it at the app.
