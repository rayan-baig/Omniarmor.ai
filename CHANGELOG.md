# Changelog

What changed in OmniArmor, in plain words, newest first. The version number
lives in `omniarmor_app/version.py`; the Settings page and `/healthz` show it.

## 1.0.0 (3 November 2026)

The first release for launch. It gathers the work of the last few days.

### Teams, families and answers

- Update several checks at once: tick Select on an industry page's checks,
  then mark them done today, answer Yes or No, or set one date. Each check
  gets the same checks and its own audit row as a single update, and if one
  can't take the change, nothing is saved.
- A kid's first lesson is shorter: the track is picked on the add form and
  Start the first lesson opens it, 13 steps from opening the Academy to the
  first results instead of 15. A kid joining on their own device with
  nothing played yet lands on the first lesson too.
- A progress report for the family's grown-ups: lessons played, best quiz
  scores, tries, stars and certificates on every track. A kid's device and
  other workspaces can't open it.
- Certificates print on one landscape page (A4 or US Letter) with nothing of
  the app around them.
- The quizzes can't be guessed from their shape: the right answer is no
  longer usually the longest option in the first worlds, true-or-false
  questions are true about half the time, and a test checks every track.
- The Academy plan page explains the compliance tracker, the free Academy
  and the Academy plan side by side, every number read from the code.
- A Help page (`/help`) with 15 questions, from the free trial and prices
  to reminder emails, the Autopilot, the Academy and your data. Every
  number on it comes from the code; an optional `SUPPORT_EMAIL` adds an
  address to write to. It is in the sitemap and linked from every footer,
  the landing page and Settings.

### Launch polish

- One version number, shown in Settings under About and in `/healthz`, and
  this changelog.
- Friendly "page not found" and "something went wrong" pages in the same look
  as the rest of the site, with a way back home. A server error never shows
  what went wrong inside; it is recorded for Autopilot instead, and if even
  the error page fails, a plain one takes its place.
- Icons for every browser and phone (a real `favicon.ico`, an Apple touch
  icon, and 192 and 512 icons in the app manifest), and share previews on the
  public pages: title, description and a picture when a link is shared.
- The sitemap lists every public page, sign up and sign in included.
  robots.txt keeps search engines out of the app, the Academy, Settings,
  password reset and invite links and the kids' join page, and every page
  that isn't public says `noindex`.
- Each person chooses their own reminder emails in Settings: the daily
  digest, the time-limit alerts, both or neither (people who had reminders
  off keep both off). The account that gets Autopilot's emails can also turn
  off the weekly Autopilot report. A clock already alerted about still
  reaches, in the digest, someone who turned the alerts off.
- Every email has one look: a 600-pixel column in the site's colors, beside
  a plain-text part with the same words, ending with "OmniArmor is a product
  of MTRX Horizyn." Reminders link to the page where you choose which
  reminder emails you get, and the password reset email has a clear button.
- An end-to-end test of the Academy plan against a fake Stripe server: free
  trial, trial over, paid, a failed payment, cancelled and paid again, with
  what the family sees checked at every step.

### Deadlines and clocks

- Business-day and working-day checks count business days from a date, and
  are overdue the day after the due date.
- "Hours since" and "minutes since" checks count from a date and time, both
  in the same way, and their emails go out when they reach the warning point
  and again when they are overdue.
- Checks that count months or years since a date, the 7-day ready-to-eat food
  limit (prep day is day 1), the FDA 5-day report, the waste accumulation
  clock and the PRN order clock all count from a date.
- A check saved as a number can switch to a date, and a typed number is kept
  on a check that already has a date.
- Every check's question is written in plain words, and every check is
  tested against the handbook, including its date edges.

### Accounts, teams and sign-in

- The first ten minutes: the price is up front, the top five checks for your
  industry come first, and there is a list for the first day.
- People invited with an email that already has an account are told what to
  do.
- The record keeps the name of whoever made a change, even after they leave
  the team.
- A password reset link that has expired is never sent again.
- Very large page numbers and member numbers get a page, not an error.

### Future Owner Academy

- The Academy plan turns on as soon as a family pays, shows as cancelled when
  it is cancelled, and keeps the way to past invoices after it ends.
- A checkout never brings an ended plan back, and a late checkout never hides
  a failed payment.
- Every question has one right answer and its own practice card, each
  practice answer is graded against its own question, money questions have no
  negative or impossible answers, and rule quizzes never mark a right industry
  as wrong.

### Running the service

- Autopilot checks backups, streams exports, stays quiet about problems that
  come and go, sends the Monday report once, and does not call a daily finding
  fixed ten minutes later.
- The audit trail has an index for its whole sort order (schema version 12).
- Logs hold no secrets and no full email addresses; Stripe checkout ids are
  hidden too, even when percent-encoded. Dates show in the workspace's time
  zone.
- OmniArmor runs on its own subdomain of MTRX Horizyn's domain and shares no
  cookies with the other apps there.
- User counts (numbers only) for the company's console.

### Security and upkeep

- Fixes from a security review, an upgrade of Flask past a published
  security hole, and quiz answers and one-time links kept where they belong.
- Every package is pinned and audited in CI; secrets and junk files are
  ignored by git. A newer push cancels the CI run it replaces, and every CI
  job has a time limit.
- The container starts on a host disk owned by root.

### Pages and documents

- Terms and Privacy pages in plain words that match what the code does,
  including logs, alerts, backups and clocks.
- The company is spelled MTRX Horizyn everywhere.
- The handbook and README carry the current test counts and the hour clocks.
