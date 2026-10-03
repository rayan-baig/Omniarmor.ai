# Running OmniArmor for little to no money

OmniArmor is built so the monthly bill can be close to zero. There is no paid
database, no job-queue service, no image hosting and no paid add-ons. Everything
runs in one small process on one small server.

Prices and free-tier limits change often, so check each provider's current
pricing page before you pick one.

## Where money can go

| Item | Needed? | Cheapest option |
|---|---|---|
| Server | Yes | A free-tier VM (for example, Oracle Cloud Always Free or Google Cloud's free e2-micro), or the smallest plan at any VPS host |
| Database | Included | SQLite on the server's disk. No database bill. |
| Daily reminders and backups | Included | Built into the app. No cron or queue service. |
| HTTPS certificate | Free | Caddy gets and renews Let's Encrypt certificates automatically |
| Email | Optional | A free sending tier (Brevo, Mailjet, SMTP2GO, Resend and others have one), or Amazon SES's low per-email price. Without email, reminders show in the app. |
| Domain name | Recommended | The one yearly cost most setups can't avoid |
| Off-server backup copies | Recommended | A free object-storage tier (Cloudflare R2 and Backblaze B2 have one) |
| Taking payments | When you charge | Payment processors such as Stripe charge per payment, with no monthly fee |

## The near-zero setup (about 20 minutes)

1. Create a free-tier Linux VM and install Docker.
2. Point your domain's A record at the VM's IP address.
3. Copy the repo to the VM, then `cp .env.example .env` and set `SECRET_KEY`,
   `BASE_URL` and `DOMAIN`.
4. Run `docker compose up -d`.

That's it. `docker-compose.yml` runs the app and Caddy, Caddy handles HTTPS,
and the app does its own daily reminders, backups and cleanup.

Render (`render.yaml`) is the easiest hands-off option, but it uses a paid
plan, because the app needs a persistent disk for its database. Free web
services that sleep or lose their disk aren't suitable.

## What the app does to stay cheap

- **One process, many threads.** `WEB_CONCURRENCY=1` and `WEB_THREADS=8` fit a
  tiny VM's memory. Raise `WEB_CONCURRENCY` only if one process can't keep up.
- **SQLite.** No separate database server to pay for. WAL mode lets reads and
  writes happen together, and the daily backup takes a consistent copy.
- **Long browser caching.** CSS and JS are cached for a year, and each file's
  link changes when the file changes, so repeat visits use almost no bandwidth.
  Caddy also compresses every response.
- **No image files.** Logos, the Academy mascot, icons and avatars are inline
  SVG.
- **Generated, not stored, lessons.** The Academy's 1,350 levels are generated
  from code on demand. Only each learner's progress is saved.
- **One email per company per day at most.** Reminders go out as a daily digest
  and are never repeated for the same due date. That keeps volume inside free
  email tiers for a long time.
- **Automatic cleanup.** Old sign-in records, used reset links, expired invites
  and expired friend codes are deleted daily, so the database stays small.

## When to spend more

Upgrade the server when pages slow down at busy times, and the email plan when
you near its free sending limit. Both are settings changes, not code changes.
