# OmniArmor.ai

**Catch the fine before it catches you.**

OmniArmor is a product of MTRX Horizyn. In production it runs on its own
subdomain of MTRX Horizyn's domain, `omniarmor.mtrxhorizyn.com`
([docs/OPERATIONS.md](docs/OPERATIONS.md), section 1).

A self-running compliance service for 54 regulated industries, K-12 schools among them. Each industry
has ten checks covering the compliance failures that cost businesses in that
industry the most: common, expensive when missed, and cheap to prevent with a
deadline, a threshold or a checklist. That is 540 checks in all.

Companies sign up, pick their industries and enter each date or reading once.
From then on OmniArmor:

- **Can be tried without signing up:** "See a demo" opens a pretend restaurant (a few checks done, one overdue, a reminder and a report), and the Academy for schools page opens a pretend class with its progress view, join codes and a sample lesson. Nothing in a demo is saved and nothing is sent (`omniarmor_app/demo_mode.py`).
- **Tracks deadlines by itself:** it counts the days from each saved date, every day, in the company's timezone, and the hours from each saved start time for the checks that run in hours.
- **Sends reminders:** one email per team member when something is 30, 7 or 1 day from due, due today, or overdue (weekly). Missed days catch up, and failed emails are retried. Hour and minute clocks also email when they reach their warning point and when they become overdue, checked every minute. Each person chooses in Settings whether they get the daily digest, the time-limit alerts, both or neither.
- **Restarts recurring duties:** pressing Done today starts the next cycle.
- **Keeps the record:** every change is in the audit trail with who and when. Printable reports and CSV exports are ready for inspectors.
- **Backs itself up:** daily database backups, with old copies pruned.
- **Fills in the fridge checks itself (Kitchen Safety Bundle):** connected to CyberLogix, MTRX Horizyn's fridge and freezer alarm app, a restaurant's cold holding check ticks itself from CyberLogix's daily readings, and a breach leaves a note for someone to review. The owner makes the connection key in Settings, Connections; the contract CyberLogix builds against is [docs/CYBERLOGIX-CONNECTION.md](docs/CYBERLOGIX-CONNECTION.md). A connection sends temperature summaries and roles, never names.
- **Has Pilot, the MTRX Horizyn AI assistant (1.10.0):** a robot in the corner of the public pages and of a business's and a teacher's own pages, running on the person's own AI key from their browser (OmniArmor never sees the key or the chat). It explains checks, reminders, statuses, rules and plans, and, after the person presses Allow, can mark a check done, update a check, set a reminder date, answer several checks (never Yes where Yes means a problem) or add students by first name. Never on a page a student uses. [docs/PILOT.md](docs/PILOT.md).
- **Has a helper, Armo:** a small shield character sits above the tab bar, does his own thing, and jumps up the moment something is blocked, overdue, due soon or a reminder email failed. Each alert has a one-click fix link. Pick one of 14 personalities (Chief, Sweetie, Jokester, Snark, Grumpy, Sleepy, Hype, Cap'n, Your Majesty, Robo, Chef, Sleuth, Zen or Professor), each with its own outfit and over 60 lines, or hide him.
- **Made for schools too:** SchoolSafetyArmor holds a school's safety routines (drills, AED and first-aid kits, playground and gym checks, the nurse's medication log and fridge, the cafeteria, bus and van pre-trip checks, concussion forms and heat checks, visitor sign-in, lab chemicals and background-check renewals), beside SchoolArmor's legal duties, on one page at `/for/schools`. A teacher signs up as a school and runs the Academy for a whole class (`/classrooms`), on the Classroom track: a pretend class lemonade stand, 16 worlds and 107 short lessons with no repeats, and a printable teacher guide (`/classrooms/guide`): students added by first name or nickname only, a class progress view, printable certificates, a leaderboard the teacher can switch off, and a one-page pilot report with totals only.
- **Prepares the next generation:** the Future Owner Academy teaches kids who may inherit the business, in four tracks: Launchpad (630 levels), Trailblazer (890), Summit (836) and Titan Mastery (764), each level a different lesson. It has 43 worlds, from money, marketing, sales, hiring, safety, ethics, taxes and cyber safety to a winning mindset and the habits of champions, plus the family company's own rules, with over 1,200 written questions and facts. It also has spaced-repetition practice, daily streaks, boss rounds, avatars that level up, friends and duels, and join codes so a kid can use the Academy on their own device. Plus includes all of it; its first worlds are free for everyone.

## Plans

The prices live in one place, `omniarmor_app/plans.py`; every page reads them
from there.

- **Free trial:** everything in Plus for `ACADEMY_TRIAL_DAYS` days (14 by
  default) from sign-up. No card.
- **Pro, $50 a month per location:** the compliance tracker: checks,
  reminders, reports, bulk entry, the reminder log and the team.
- **Plus, $80 a month per location:** everything in Pro and the whole Future
  Owner Academy at no extra cost. The Academy's first worlds stay free for
  everyone.
- **A location is a workspace:** a workspace holds one site, so each
  subscription bills a quantity of 1; a company with several sites makes a
  workspace for each.
- **Without a plan** the tracker is read-only: every record can be seen and
  downloaded and nothing is deleted, but no check can be saved and reminders
  pause, with a banner. Export and delete always work.
- **Kitchen Safety Bundle:** CyberLogix customers on the bundle get Pro
  included while their workspace receives signed CyberLogix reports (one in
  the last 3 days, then a 7-day grace period), and Plus for the difference.
  The signature is in [docs/CYBERLOGIX-CONNECTION.md](docs/CYBERLOGIX-CONNECTION.md), section 3.5.
- **Monthly or yearly:** every plan can be paid yearly for ten months' price,
  "2 months free": Pro $500, Plus $800 and the bundle's Plus $300 a year per
  location, worked out in `plans.py` from the monthly prices. A cancelled
  yearly plan stays on to the end of the year paid for, with no partial refund.
- Payments go through Stripe (`PRO_STRIPE_PRICE`, `PLUS_STRIPE_PRICE`,
  `PLUS_BUNDLE_UPGRADE_STRIPE_PRICE`, and yearly `PRO_YEARLY_STRIPE_PRICE`,
  `PLUS_YEARLY_STRIPE_PRICE`, `PLUS_BUNDLE_UPGRADE_YEARLY_STRIPE_PRICE`; a
  yearly one left empty means that plan is monthly only); set-up is in
  [docs/OPERATIONS.md](docs/OPERATIONS.md), section 7. A workspace on the old
  Academy plan keeps it as it was until it changes plan.
- **Pause instead of cancel:** the owner's cancel screen offers a pause of 1,
  2 or 3 months for a monthly plan (Stripe stops charging, reminders stop,
  the workspace is read-only, and it starts again by itself, with an email 3
  days before), a one-time discount (`SAVE_OFFER_STRIPE_COUPON`,
  `SAVE_OFFER_PERCENT`, `SAVE_OFFER_MONTHS`: 25% off the next 2 months by
  default) and cancelling, one click. Monthly payers are offered "Switch to
  yearly, 2 months free" on the plan page.
- **Upgrade offers:** an owner on Pro sees a peek at an Academy lesson and
  "Plus includes the Academy" when opening the Academy, and an owner who adds
  a second location sees the yearly saving; at most one offer a week per
  person, and "No thanks" is for good. Owners add and switch locations in
  Settings.
- **Trade pages** at `/for/<trade>` (salons and barbershops, tattoo and
  piercing studios, gyms and fitness studios, shops, schools) name the
  OmniArmor checklists that fit each trade, and what they don't cover.
- **Classroom plans for schools**, yearly only: **Classroom, $299 a year**
  (the whole Academy for one class of up to 35 students) and **Whole school,
  $1,490 a year** (every class, and the school's checklist). A free 30-day
  classroom pilot, no card (`CLASSROOM_PILOT_DAYS`). By card
  (`CLASSROOM_YEARLY_STRIPE_PRICE`, `SCHOOL_YEARLY_STRIPE_PRICE`) or by
  invoice (`SCHOOL_INVOICE_EMAIL`; set by hand with
  `flask --app wsgi plan <id> classroom --until <date>`).

Every check answers **Cleared**, **Warning** or **Blocked** and names the rule
it applies. This is decision support, not legal advice: confirm each rule with
a compliance professional for your jurisdiction.

## Run it

```sh
python3 -m venv .venv && . .venv/bin/activate   # Python 3.11, as in the Dockerfile; 3.13 works too
pip install -r requirements.txt -c constraints.txt
flask --app wsgi run --port 8000          # development, at http://localhost:8000
python3 -m unittest discover -s tests     # 955 tests
flask --app wsgi seed-demo --force demo.db   # a made-up demo workspace (docs/OPERATIONS.md, section 6)
```

A virtual environment is needed on most systems: Ubuntu 24.04, Debian 12 and
Homebrew's Python refuse a plain `pip install`. The first start creates the
database in `instance/`.

Everything about OmniArmor in plain language, from every feature to all 540 checks: [docs/HANDBOOK.md](docs/HANDBOOK.md).

Production: see [docs/OPERATIONS.md](docs/OPERATIONS.md) (Render one-click
blueprint, Docker, or `docker compose up -d` on one small server with free
HTTPS; email setup, backups, monitoring). To run it for close to nothing:
[docs/COSTS.md](docs/COSTS.md). How much it handles and when to grow:
[docs/LOAD-TEST.md](docs/LOAD-TEST.md). How the pieces fit:
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md). A staging copy to try a change
on first: [docs/STAGING.md](docs/STAGING.md).

## Layout

| Path | What it is |
|---|---|
| `omniarmor_app/` | The web app: accounts, workspaces, tracking, reminders, reports, daily jobs |
| `omniarmor_app/plans.py` | The plans and their prices, the free trial, read-only without a plan, and the Kitchen Safety Bundle's cover |
| `omniarmor_app/demo_mode.py` | The demos anyone can open without an account, each page on a throwaway in-memory copy of pretend data |
| `omniarmor_app/connections.py` | The Kitchen Safety Bundle: CyberLogix's connection key, daily report and signature ([docs/CYBERLOGIX-CONNECTION.md](docs/CYBERLOGIX-CONNECTION.md)) |
| `omniarmor_app/academy.py` | The Future Owner Academy: worlds, lessons and quiz generation (see `docs/academy-preview/`) |
| `omni_armor_rules/` | The 540 rules (`group_1.py` … `group_12.py`) and the one `evaluate` every rule uses |
| `omni_armor_platform.py` | The original engine: 25 detailed checks and the console demo |
| `dashboard/` | A standalone demo page of all 540 checks, built from the catalog |
| `tools/load_test.py` | The load test and the timing of the scheduled sweeps ([docs/LOAD-TEST.md](docs/LOAD-TEST.md)) |
| `tests/` | Tests for the engine, the catalog, the web app and the dashboard |
| `Dockerfile`, `docker-compose.yml`, `Caddyfile`, `render.yaml`, `.github/workflows/ci.yml` | Packaging, hosting and automatic test runs |

## Forming the company

OmniArmor is not a company of its own: it is a product of MTRX Horizyn, and
MTRX Horizyn is the company to form. That's a legal filing only the founders
can make. The usual path for a software startup:

1. **Incorporate in Delaware** as a C corporation, directly with the Delaware
   Division of Corporations or through a service such as Stripe Atlas or Clerky.
   You'll need a registered agent in Delaware.
2. **Get an EIN** from the IRS (free, online, at irs.gov).
3. **Register to do business** in the state where you operate (a "foreign
   qualification"), if that isn't Delaware.
4. **Issue founder stock** and file an **83(b) election** with the IRS within
   30 days of receiving it.
5. **Adopt bylaws**, open a business bank account, and assign the code and the
   OmniArmor name to MTRX Horizyn.

A startup lawyer and an accountant should review each step. Have the lawyer
review the Terms (`/terms`) and Privacy (`/privacy`) pages too.
