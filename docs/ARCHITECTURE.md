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

## Rules of the road

- Every company's data is looked up by the company in the signed-in session,
  never by an id from the browser.
- Only rules marked policy (no single legal number) accept a company's own
  limit.
- The dashboard's JavaScript `evaluate` mirrors `rule.py`; a test fails if
  they disagree on 2,700 sample readings.
