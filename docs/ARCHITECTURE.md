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
   ├── catalog.py    the 50 industries and 500 rules ───────────┤
   │                                                            ▼
   │                               omni_armor_rules (rule.py: one evaluate() for every rule)
   ├── reminders.py  daily digests per company
   ├── jobs.py       the daily timer: reminders, backup, cleanup
   ├── notify.py     email, or the saved log when email isn't set up
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

## Data model

| Table | Holds |
|---|---|
| `users` | People: email, name, password hash, reminder setting, a session counter that signs out old devices |
| `orgs` | Companies: name and timezone |
| `memberships` | Who belongs to which company, as owner or member |
| `org_industries` | Which of the 50 industries each company tracks |
| `items` | One row per company and rule: the number, yes/no or date, plus any policy-limit override |
| `audit` | Every change, with person, time, before and after |
| `notifications` | Every email sent or saved, with status and error |
| `reminder_marks` | Which reminders were already sent for which due date |
| `invites`, `password_resets` | One-time links, stored only as hashes |
| `login_failures` | Recent failed sign-ins, for rate limiting |
| `job_runs` | One row per day of the daily job, so it runs once |
| `learners`, `learner_progress` | Academy players (nickname and picture only) and their best score and stars per level |
| `friend_codes`, `learner_friends`, `duels` | Single-use friend codes, friendships across companies, and head-to-head duels |
| `join_codes`, `learner_days`, `learner_mistakes` | Kid device codes, daily streaks, and missed questions for spaced practice |

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
questions when grading, and a new attempt gets new questions.

Four tracks share the worlds but keep separate progress, stored as
`track index * 1,000,000 + world * 1000 + stage`:

| Track | Worlds x stages | Owner's Challenge | Rule Quests | Levels |
|---|---|---|---|---|
| Launchpad (Basic) | 16 x 50 | 50 | 50 x 10 | 1,350 |
| Trailblazer (Intermediate) | 43 x 50 | 50 | 50 x 10 | 2,700 |
| Summit (Advanced) | 43 x 100 | 100 | 50 x 20 | 5,400 |
| Titan Mastery | 43 x 300 | 300 | 50 x 50 | 15,700 |

Deeper stages ask more questions, draw harder ones from the banks, raise the
pass mark and mix in review from earlier worlds; every tenth stage is a boss
round. Missed questions go into `learner_mistakes` for spaced practice (they
come back after 1, 3 and 7 days until mastered), `learner_days` drives the
daily streak and goal, and ranks (scaled to the track's size) level up the
learner's picture.

A grown-up can make a single-use join code (`join_codes`) for a kid's own
device. The kid gets an Academy-only session (`g.kid`) limited to their own
profile; bumping `learners.device_epoch` signs them out everywhere.

The Academy plan (`academy_plan.py`) is separate from the compliance
service: a free trial when the first learner is added, then the first three
Launchpad worlds stay free. Stripe Checkout handles payment and a signed
webhook (`/billing/stripe/webhook`) keeps `orgs.academy_status` current.

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
