# How OmniArmor fits together

```
Browser (HTML forms, no JavaScript needed)
   │  sign-in cookie + form token on every change
   ▼
omniarmor_app (Flask)
   ├── security.py   sign-in, form tokens, rate limits, security headers
   ├── auth.py       sign up, sign in, password reset, invites
   ├── views.py      overview, industry checks, report, audit trail, settings
   ├── tracking.py   turns stored readings into today's status ─┐
   │                                                            │ uses
   ├── catalog.py    the 54 industries and 540 rules ───────────┤
   │                                                            ▼
   │                               omni_armor_rules (rule.py: one evaluate() for every rule)
   ├── reminders.py  daily digests per company
   ├── jobs.py       the timer: alerts each minute; reminders, cleanup, backup daily
   ├── notify.py     email, or the saved log when email isn't set up
   ├── connections.py CyberLogix's daily report fills in the temperature checks
   └── db.py         SQLite, schema migrations, audit writes
   ▼
SQLite database (one file on a persistent disk) + daily backups
```

## The life of a reading

1. A person enters a reading on an industry page: a number, Yes or No, or a
   date ("last done" or "expires on"). The form posts to
   `/app/industry/<id>/rule/<key>` with a form token.
2. `security.py` checks the token and the sign-in. The route checks that the
   industry belongs to the person's company and that the rule exists.
3. `tracking.apply_change` validates the input, writes the `items` row, and
   writes an `audit` row with who, when, before and after.
4. When any page loads, `tracking.states_for_org` reads the company's rows and,
   for date-tracked rules, counts days from today's date in the company's
   timezone. `omni_armor_rules.evaluate` gives Cleared, Warning or Blocked, the
   same answer the Python engine and the demo dashboard give.
5. Each morning `jobs.run_daily` claims the day, then `reminders.run_reminders`
   finds deadlines at 30/7/1/0 days or overdue, records each one in
   `reminder_marks` so it's sent once, and emails each team member a digest.

A reading can also come from CyberLogix, MTRX Horizyn's fridge and freezer
alarm app (the Kitchen Safety Bundle). Its daily report to
`/api/connect/cyberlogix/daily` is signed in by the workspace's connection
key instead of a cookie and form token; `connections.py` checks it, and a
clean day goes through the same `tracking.apply_change` as step 3, with
CyberLogix as who made the change. The contract is
[CYBERLOGIX-CONNECTION.md](CYBERLOGIX-CONNECTION.md).

## Data model

| Table | Holds |
|---|---|
| `users` | People: email, name, password hash, reminder settings (and when they last saved them), a session counter that signs out old devices |
| `orgs` | Companies: name and timezone |
| `memberships` | Who belongs to which company, as owner or member |
| `org_industries` | Which of the 54 industries each company tracks |
| `items` | One row per company and rule: the number, yes/no or date, plus any policy-limit override |
| `audit` | Every change, with person, time, before and after |
| `notifications` | Every email sent or saved, with status and error: the outbox, which Autopilot retries from (error reports to `ERRORS_EMAIL` included) |
| `reminder_marks` | Which reminders were already sent for which due date |
| `invites`, `password_resets` | One-time links, stored only as hashes |
| `login_failures` | Recent failed sign-ins, sign-ups and demos opened, for rate limiting |
| `job_runs` | One row per day of the daily job, so it runs once |
| `job_locks` | The lock each sweep (alerts, daily job, Autopilot) holds while it runs, so two server processes never run the same one at once |
| `usage_counts` | One total per feature per day (checks updated, lessons passed, Help page views...), with no user, workspace or learner id |
| `learners`, `learner_progress` | Academy players (nickname and picture only; a student in a class has its `class_id`) and their best score and stars per level |
| `classes` | A school's classes for the Academy: the name the teacher picks and whether the class leaderboard is on |
| `friend_codes`, `learner_friends`, `duels` | Single-use friend codes, friendships across companies, and head-to-head duels |
| `join_codes`, `learner_days`, `learner_mistakes` | Kid device codes, daily streaks, and missed questions for spaced practice |

## The demos

`demo_mode.py` lets a visitor try OmniArmor without an account: `/demo/business`
(a pretend restaurant) and `/demo/classroom` (a teacher's class). Opening one
puts a demo pass in the session (rate limited per address, 30 minutes). On the
app's own pages, `security.load_user` then signs the visitor in as the demo's
pretend owner, and `db.get_db` hands that request its own copy of the demo
database: an in-memory SQLite database copied with the backup API from a
template built from today's date (rebuilt every hour). The copy is closed, and
so gone, when the request ends, so nothing a page writes outlives it and the
real database is never opened for demo data. `demo_mode.guard` refuses every
form but the Academy quiz, and `notify.notify` never sends from inside a demo.
Every other page (sign-up, sign-in, the public pages) sees an ordinary visitor
on the real database.

## Armo, the helper

`armo.py` turns a company's current state into a short, prioritized list:
blocked checks and overdue deadlines first, then warnings and failed emails,
then upcoming deadlines and checks with no reading. The companion in
`base.html` shows the count. `static/armo.js` asks `/app/armo/status` for
changes every minute while the page is visible, and Armo jumps up when the
list changes. A personality only changes Armo's words and outfit, never the
facts. People pick one on the Armo page (`users.armo`; `off` hides him), and
each Academy learner picks their own (`learners.armo`).

## The Future Owner Academy

`academy.py` holds the course engine and `academy_bank/` holds the question
banks for the 25 newer worlds (questions graded easy to hard, true-or-false
facts and lesson cards), checked entry by entry by `tests/test_academy_bank.py`.
Nothing about a level is stored: each quiz is generated from a seed (learner,
track, world, stage and attempt), so the server can rebuild the exact
questions when grading, and a new attempt asks the same lesson in a new order.

Four tracks share the worlds but keep separate progress, stored as
`track index * 1,000,000 + world * 1000 + stage`:

| Track | World lessons | Lesson size | Owner's Challenge | Rule Quests | Levels |
|---|---|---|---|---|---|
| Launchpad (Basic) | 16 worlds, 87 | 5 | 3 | 54 x 10 | 630 |
| Trailblazer (Intermediate) | 43 worlds, 345 | 5 | 5 | 54 x 10 | 890 |
| Summit (Advanced) | 43 worlds, 291 | 6 | 5 | 54 x 10 | 836 |
| Titan Mastery | 43 worlds, 219 | 8 | 5 | 54 x 10 | 764 |

Each world is a fixed list of questions per track and company
(`academy.family_pool`), cut into lessons, so no question repeats within a
world and the level count is the real number of lessons. Summit and Titan
put the hard questions first and raise the pass mark; a world's last lesson
is its boss round. Missed questions go into `learner_mistakes` for spaced practice (they
come back after 1, 3 and 7 days until mastered), `learner_days` drives the
daily streak and goal, and ranks (scaled to the track's size) level up the
learner's picture.

A grown-up can make a single-use join code (`join_codes`) for a kid's own
device. The kid gets an Academy-only session (`g.kid`) limited to their own
profile; bumping `learners.device_epoch` signs them out everywhere.

Plans (`plans.py`, where the prices live): a free trial from sign-up, then
Pro (the compliance tracker) or Plus (Pro and the whole Academy), per
location a month; a location is a workspace. `plans.access()` says what a
workspace can use: without a plan the tracker is read-only and reminders
pause; a validly signed CyberLogix report in the last 3 days gives the
Kitchen Safety Bundle's Pro, then a 7-day grace period. Stripe Checkout
handles payment (`academy_plan.py`, `plan_views.py`) and a signed webhook
(`/billing/stripe/webhook`) keeps `orgs.plan` and `orgs.academy_status`
current.

Friends come from different companies, so duels never use a company's name or
rules. They draw only from the general business worlds, and both players get
the same seed. Parents add friends with a single-use code that expires after
7 days, and guessing codes is rate limited. Friends see only a nickname,
picture, rank and stars.

## Rules of the road

- Every company's data is looked up by the company in the signed-in session,
  never by an id from the browser.
- Only rules marked policy (no single legal number) accept a company's own
  limit.
- The dashboard's JavaScript `evaluate` mirrors `rule.py`; a test fails if
  they disagree on 2,700 sample readings.
