# A staging copy

A second, separate copy of OmniArmor on Render, at
`staging.omniarmor.example.com` (where `example.com` stands for MTRX
Horizyn's domain, as in [OPERATIONS.md](OPERATIONS.md)). You try a change
there first, with made-up data and test credentials, and only then put it on
the live copy.

The rule for everything below: **staging shares nothing with live.** Not the
database, not the disk, not a key, not a mail account, not a Stripe account
in live mode. If staging could reach a real person (a customer, a parent, a
child learner), sooner or later it will.

## Why it is not in render.yaml

`render.yaml` is the live copy's Blueprint. A staging service added to it
would be created and changed every time the live Blueprint is synced, and
one careless edit to the shared file could touch the live service. So
staging is set up once, by hand, in Render's dashboard, with the settings
below. It costs about the same as the live copy (a starter instance and a
small disk).

Never put any of these in `render.yaml`:

- the staging service, its disk or its branch;
- `NOINDEX` (on live it would take every public page out of search results);
- any staging value: its `SECRET_KEY`, `BASE_URL`, `STATS_KEY`, test-mode
  Stripe keys, or a test inbox's SMTP settings. Secrets are typed into the
  service's Environment page, never committed.

## 1. The service

Render → New → Web Service → this repository.

| Setting | Value |
|---|---|
| Name | `omniarmor-staging` |
| Runtime | Docker (the same `Dockerfile`) |
| Branch | `staging` (make it once from the live branch) |
| Instance type | Starter, not Free (Free has no disk and sleeps) |
| Instances | 1 |
| Health check path | `/healthz` |
| Auto-deploy | On: a push to `staging` deploys it |
| Disk | Its own, new disk: name `omniarmor-staging-data`, mount path `/data`, 1 GB |

The image already sets `OMNIARMOR_ENV=production`,
`DATABASE_PATH=/data/omniarmor.db` and `BACKUP_DIR=/data/backups`, so on its
own disk staging behaves exactly like live. Never attach the live disk
(`omniarmor-data`), and never copy the live database or a live backup onto
staging: they hold real people's names and email addresses, and children's
Academy progress.

## 2. The address

1. Where the domain's DNS is managed, add a `CNAME` named
   `staging.omniarmor` pointing at the staging service's `onrender.com`
   address.
2. Render: the staging service → Settings → Custom Domains → add
   `staging.omniarmor.example.com`, and wait for the certificate.

It is a host of its own, so the sign-in cookie (host-only, no `Domain`) never
travels between staging and live.

## 3. The settings

Set these on the staging service (Environment). Generate new secrets; never
paste in the live ones.

| Setting | Staging value | Why |
|---|---|---|
| `SECRET_KEY` | a new one: `python3 -c "import secrets; print(secrets.token_hex(32))"` | Live's would let a staging cookie sign in to live |
| `BASE_URL` | `https://staging.omniarmor.example.com` | Every link in an email, reset and invite comes back here, not to live |
| `NOINDEX` | `1` | Every address says noindex, robots.txt closes the site, the sitemap is empty (section 5) |
| `STATS_KEY` | empty | MTRX Horizyn's console must not count staging's test accounts. To test the console against staging, a new key that only a staging console has |
| `OPERATOR_EMAIL` | empty, or your own | Autopilot's problem emails (section 4 says where they go) |
| `ERRORS_EMAIL` | empty, or your own | Error reports |
| `SUPPORT_EMAIL` | empty | Nobody should write to staging for help |
| `SMTP_HOST` and the rest | empty, or a test inbox | Section 4 |
| `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, `ACADEMY_STRIPE_PRICE` | empty, or test mode | Section 4 |
| `DAILY_JOB_HOUR_UTC` | as on live | So reminders, backups and Autopilot behave the same |

Leave `DATABASE_PATH` and `BACKUP_DIR` to the image (both on staging's own
`/data`) until you seed it (section 6).

## 4. Nothing reaches a real person

### Mail

**Leave `SMTP_HOST` empty.** Then nothing is sent: every reminder,
password-reset link, invite and Autopilot message is kept on the app's
Reminders page (and Autopilot's go to the server log) instead. That is a
built-in sink: you can read exactly what would have gone out. Autopilot will
report "Email is not set up"; on staging that is expected.

To see mail as it would arrive, use a test inbox service that accepts SMTP
and delivers nothing, and put its settings in `SMTP_HOST`, `SMTP_PORT`,
`SMTP_USER` and `SMTP_PASSWORD`. Never the live mail account. Set
`MAIL_FROM` to a staging address, such as
`OmniArmor staging <no-reply@staging.omniarmor.example.com>`.

### Payments: Stripe in test mode

Without Stripe settings the Academy plan is switched on by hand
(`flask --app wsgi academy-plan <workspace id> active`), which is enough for
most tests. To test paying, switch the Stripe dashboard to **test mode** and,
there:

1. Make a test-mode price for the Academy plan; its id goes in
   `ACADEMY_STRIPE_PRICE`.
2. Developers → API keys: the test secret key (it starts `sk_test_`) goes in
   `STRIPE_SECRET_KEY`.
3. Developers → Webhooks → add endpoint
   `https://staging.omniarmor.example.com/billing/stripe/webhook`, with the
   same events as live (OPERATIONS.md, section 8). Its signing secret (the
   test one) goes in `STRIPE_WEBHOOK_SECRET`.

Pay with Stripe's test card `4242 4242 4242 4242`, any future date and any
CVC. Nothing is charged. Never put a live-mode key (`sk_live_`), price or
webhook secret on staging, and never point live's webhook at staging.

## 5. Out of search engines

`NOINDEX=1` (added in 1.1.3) makes the copy unlisted everywhere: every
response, public pages, files and robots.txt included, carries
`X-Robots-Tag: noindex, nofollow`; every page has the noindex `<meta>` and
no share previews or canonical address; `/robots.txt` is
`Disallow: /`; `/sitemap.xml` lists nothing. Otherwise a parent searching for
the Academy could find staging's sign-up page and sign a child up on a copy
that emails nobody.

Check it after each deploy:

```sh
curl -sI https://staging.omniarmor.example.com/ | grep -i x-robots-tag
curl -s https://staging.omniarmor.example.com/robots.txt
```

Leave `NOINDEX` unset on live.

## 6. Something to look at: the demo workspace

Staging starts empty. Fill it with the made-up pharmacy from
OPERATIONS.md, section 6. Open the staging service's Shell in Render and seed
a **new** file beside the empty database (in production the command refuses
the app's own database, even an empty one):

```sh
flask --app wsgi seed-demo --force /data/omniarmor-demo.db
```

It prints the owner's and a pharmacist's sign-in (on the reserved `.example`
domain, which never receives email) and a random password. Its first backup
goes to a folder of its own, `/data/omniarmor-demo-backups`. Then point
staging at it, under Environment, and save (it redeploys):

| Setting | Value |
|---|---|
| `DATABASE_PATH` | `/data/omniarmor-demo.db` |
| `BACKUP_DIR` | `/data/omniarmor-demo-backups` |

Set both: with `BACKUP_DIR` left at `/data/backups`, the demo's daily
backups would mix with the empty database's. The dates are counted from the
day it is seeded, so for a fresh demo, seed a new file (a new name, such as
`/data/omniarmor-demo-2.db` with `/data/omniarmor-demo-2-backups`) and point
both settings at it.

To try the operator's view, set `OPERATOR_EMAIL` to the owner's demo address
and run `flask --app wsgi make-operator <that address>` in the Shell.

## 7. From staging to live, a checklist

- [ ] Push the change to the `staging` branch. Staging deploys it.
- [ ] `curl -s https://staging.omniarmor.example.com/healthz` answers
      `"status": "ok"` with the new version from
      `omniarmor_app/version.py`.
- [ ] `python -m pytest -q` passes, and GitHub Actions is green for that
      commit.
- [ ] Walk the change by hand on staging. For anything that emails, read
      what would have gone out on the Reminders page (or the test inbox).
      For the Academy plan, pay with the test card.
- [ ] `flask --app wsgi autopilot` in staging's Shell shows nothing new that
      is broken (beyond "Email is not set up" when SMTP is empty).
- [ ] If the change needs a new setting, add it to live by hand now, with
      live's own value. Settings do not travel with a commit.
- [ ] Back up live first: `flask --app wsgi backup` in live's Shell. A
      schema upgrade runs as the new version starts.
- [ ] Merge the **same commit** into the live branch (the one the live
      service deploys) as a fast-forward: `git checkout <live branch> &&
      git merge --ff-only staging && git push`. Do not re-type the change:
      the commit that was tested is the commit that ships.
- [ ] Live deploys on the push (if auto-deploy is off: the service → Manual
      Deploy → Deploy latest commit). Check
      `https://omniarmor.example.com/healthz` shows the same version, and
      that `curl -sI https://omniarmor.example.com/` has **no**
      `X-Robots-Tag`.
- [ ] If the CHANGELOG says there is a step after upgrading, do it on live.

## 8. Keeping them apart, a checklist

- [ ] Staging has its own disk; the live disk is attached to live only.
- [ ] `BASE_URL` on staging is the staging address.
- [ ] `NOINDEX=1` on staging, and unset on live.
- [ ] Every secret on staging (`SECRET_KEY`, `STATS_KEY`, Stripe) was made
      for staging.
- [ ] SMTP on staging is empty or a test inbox.
- [ ] Stripe on staging is test mode only, and live's webhook points at live.
- [ ] `STATS_KEY` on staging is empty or matches only a staging console.
- [ ] The demo's `BACKUP_DIR` is its own folder.
- [ ] No copy of the live database or a live backup has ever been put on
      staging.
- [ ] Nothing about staging is in `render.yaml`.
