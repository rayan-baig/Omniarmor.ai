# OmniArmor.ai: The Complete Handbook

*Catch the fine before it catches you.*

This handbook explains OmniArmor from top to bottom in plain language: what it is, who it's for, how every part works, how the code is laid out, how to run it, how it was built, where things stand today, and what is left to do. The appendices at the end list every one of the 500 compliance checks, every Academy world, every Armo personality, every web address the app answers, and every setting.

**If you are picking this project up in a new account:** this document is the project's memory. The code lives in the GitHub repository `rayan-baig/omniarmor.ai`. The latest work is on the branch `claude/wonderful-heisenberg-77tbq9`. Part 12 explains how to keep working on the project the same way it has been built so far.

---

## Contents

1. What OmniArmor is
2. The compliance service, step by step
3. Reminders, the daily job and the record
4. Armo, the helper
5. The Future Owner Academy
6. Autopilot and the bug finder
7. Security and privacy
8. How the code is built
9. Running, deploying and operating it
10. Design and writing style
11. How it was built: the history
12. Where things stand, what's next, and how to keep working
- Appendix A: All 50 industries and 500 checks
- Appendix B: Every Academy world, with its lesson cards
- Appendix C: Armo's 14 personalities
- Appendix D: Every web address the app answers
- Appendix E: Every setting
- Appendix F: Glossary

---

## 1. What OmniArmor is

### 1.1 The short version

OmniArmor.ai is a self-running compliance service for businesses in regulated industries. A company signs up, picks the industries it works in, and enters each date or reading once. From then on, OmniArmor counts the days by itself, warns the team by email before anything is due, shows what is blocked or close to a limit, and keeps a record of every change that an inspector, auditor or insurer can be shown.

It covers 50 industries. Each industry has ten checks: the compliance failures that cost businesses in that industry the most money through fines, shutdowns, lawsuits or lost revenue. That makes 500 checks in all. Every check names the rule it comes from, says what a miss costs, and says exactly what to do when it's broken.

Two extra parts sit on top of the compliance service:

- **Armo** is the app's mascot and helper: a small, friendly shield character who sits above the tab bar, keeps himself busy while things are calm, and jumps up the moment something needs attention. He has 14 personalities to choose from.
- **The Future Owner Academy** is a game-like course for the children of family businesses, the people who may run the company one day. It has four tracks of up to 15,700 levels across 43 worlds of business lessons, plus quizzes built from the family company's own rules.

Behind all of it, **Autopilot** keeps the service itself healthy. It fixes small problems on its own and emails the operator about big ones, including new bugs, which it finds by fingerprinting every crash and by running a full self-test every day.

### 1.2 The name and the language

- The product is **OmniArmor.ai**, often just **OmniArmor**.
- The slogan is **"Catch the fine before it catches you."**
- Each industry has an "Armor" brand name, for example **FleetArmor** for motor carriers, **RestoArmor** for restaurants, **HRArmor** for employers and **ShopArmor** for e-commerce. The full list is in Appendix A.
- The app's six main screens have short names, shown in a tab bar at the bottom of every page:
  - **HQ**: the overview of everything.
  - **Intel**: the compliance report.
  - **Vault**: the audit trail.
  - **Radar**: every reminder email, sent or saved.
  - **Academy**: the Future Owner Academy.
  - **Armory**: settings.

### 1.3 Who it's for

- **Owners and managers of small and mid-sized regulated businesses** who don't have a compliance department and can't afford to miss a deadline: trucking companies, restaurants, dental practices, construction firms, child care centers, pharmacies, bars, dealerships and dozens more.
- **Their teams**: each person who owns a duty gets the daily reminder and can update a reading from a phone.
- **Family businesses**, whose kids can learn how the company works in the Academy.
- **Whoever runs the service** (the operator), who should not have to watch it every day. Autopilot does that.

### 1.4 The three answers

Every check gives one of three answers, plus a fourth state for checks with no reading yet:

- **Cleared**: within the limit, or the control is in place. Nothing to do.
- **Warning**: close to the limit or the deadline. Plan it now, before it turns red.
- **Blocked**: over the limit, overdue, or a required control is missing. The check says what to do.
- **No reading**: nothing has been entered yet. Armo nudges the team to enter it once.

### 1.5 What it is not

OmniArmor is decision support, not legal advice. Each check names the rule it applies so that the company and its compliance professional can confirm the rule for their jurisdiction. The footer of every page says so: "Decision support, not legal advice. Each check names the rule it comes from."

The ten checks per industry are the costliest and most common failures, not every rule an industry has.

---

## 2. The compliance service, step by step

### 2.1 Signing up

A new customer opens the sign-up page and enters:

- their name and email address,
- a password of at least 10 characters,
- the company's name,
- the company's timezone (used to count days and hours correctly; the page fills in the device's own timezone, so most people never change it), and
- every industry that applies, ticked from the list of 50 (already ticked when they came from that industry's public page).

That creates a **workspace** for the company. The person who signs up is its **owner**. They land right away on the page of their first industry (the one whose public page they came from, if any), with its top 5 checks first, every check in place and waiting for a first reading. People who join by invitation land on HQ.

### 2.1.1 The top 5 checks of each industry

Each industry page starts with five checks, chosen by one rule from the catalog itself (`top_checks` in `omniarmor_app/catalog.py`):

1. What a miss can bring, read from the check's "What a miss costs" text: first the checks whose miss can stop the business or a person (a closure or shutdown, an out-of-service order, a license suspended or revoked, debarment, exclusion, a criminal charge), then those that bring fines or penalties, then the rest.
2. Within each, a check counted from a date (a deadline that runs out by itself) before one that is answered or measured.
3. Then the catalog's own order.

Each top check shows a "Why this matters" line: the first part of its "What a miss costs" sentence when that part is a whole clause and already names the serious consequence, otherwise the whole sentence. Nothing is added to it.

### 2.1.2 The first-day checklist

Until it is done, HQ shows a **First day** list: create your workspace; save your first check; fill in the top 5 checks (of each industry); give every check its first reading. Each step ticks itself from what is saved, not from what was clicked, shows how far along it is ("3 of 5") and links to the next check to fill in. When all four are done the list goes away. It comes back if an industry is added or a reading is cleared, since a step is then no longer true.

A person belongs to one workspace. Other people join by invitation (section 2.9).

### 2.2 What a check is

Every check is a small piece of data with these parts:

- **Title**: a short name, for example "11-hour driving limit" or "Cold holding at 41°F or below".
- **Kind**, one of four:
  - **Maximum**: the reading must not go over a limit. It warns once the reading reaches a warning point. Example: hours driven since the last 10 hours off duty, limit 11, warns from 10.
  - **Minimum**: the reading must not fall below a limit. It warns once the reading drops to a warning point. Example: days until a driver's medical certificate expires, minimum 0, warns at 30.
  - **Required**: a Yes-or-No control that must be in place. Example: "Is the driver logging hours of service on a registered electronic logging device (ELD)?"
  - **Forbidden**: a Yes-or-No condition that must never happen. Example: storing card security codes after a payment is authorized.
- **Input**: the question the business answers, written in plain words: everyday words over legal ones where they mean the same ("in a row", not "consecutive"; "such as", not "e.g."), and an abbreviation spelled out where the question uses it ("protected health information (PHI)"). The words that say how a check is counted ("Days since", "Days until", "Hours since", "Business days since", "counting that day as day 1") stay exactly so, because the app reads them (section 2.3), and a test pins how many checks count each way.
- **Unit**: for maximums and minimums, such as hours, days, °F, dollars, percent or "32nds of an inch".
- **Limit** and **warning point**.
- **Citation**: the regulation or standard, for example "49 CFR 395.3(a)(3)" or "GDPR Art. 33(1)".
- **Cost**: one sentence on how a miss costs money.
- **Action**: what to do when the check is broken.
- **Policy flag**: true when the limit is an industry standard or a common policy rather than a number fixed by law. Only these can be changed by a company (section 2.6).
- **Sample**: a realistic example reading, used in demos.

Across all 500 checks there are 208 maximums, 32 minimums, 201 required controls and 59 forbidden conditions.

### 2.3 Dates that count themselves

126 checks are counted in days. For these, a person can enter a date instead of a number, and OmniArmor recounts the days every morning:

- **Days since** (115 checks): the person enters the date something last happened, such as the last annual vehicle inspection. The reading is the number of days from that date to today. The due date is that date plus the limit. One of them, RestoArmor's ready-to-eat food 7-day limit, counts the day the food was prepared or opened as day 1, as the Food Code does: food made on a Monday is on day 7 on Sunday, its due date, and Blocked on the next Monday.
- **Days until** (11 checks): the person enters the date something expires, such as a medical certificate. The reading is the number of days from today to that date. The due date is the expiry date minus the limit.

19 more checks count **months or years since** something happened, such as "Months since the facility's last completed PREA audit" or "Years since this turnout gear was manufactured". They take a date the same way and count up by themselves:

- **Months** (15 checks) count from the date to the same day of the month: exactly 12 on the anniversary, a little over the day after. The due date is the anniversary.
- **Calendar months** (3 AeroArmor checks whose rule says "calendar months") count whole months only, as the FAA does: a check any day in June 2025 is good through June 30, 2026, which is the due date.
- **Years** (1 check) count like months, in years.

16 checks count **business, working or work days since** something happened, such as "Business days since the new hire's first day of work without a completed I-9 Section 2". They take a date too. Each of these days is Monday to Friday, not counting US federal holidays (a holiday that falls on a Saturday is kept the Friday before, one on a Sunday the Monday after). The start day itself is day 0, and the due date is the day the limit is reached: an I-9 for a Monday start is due Thursday. The deadline is missed once the due date has ended, so from the next day the check is Blocked and overdue, even when that day is a weekend or a holiday and the count hasn't grown: an I-9 due on a Friday is Blocked on the Saturday ("1 day overdue", "The 3 business days limit ended on" that Friday) on its page, the overview, the report and its CSV, in reminders and in Armo. The warning point is always a business day, so the weekend before it stays Cleared.

22 checks count **hours since** something happened, such as "Hours since becoming aware of a personal data breach not yet reported to the supervisory authority (the data protection regulator)" (72 hours) or "Hours since learning of a work-related fatality without reporting it to OSHA" (8 hours). They take the date **and time** the clock started, and count real hours from it to now, in whole minutes:

- The due time is the start plus the limit: a death learned of at 9:00 is due at 17:00. Up to and including 17:00 the check is at most a Warning ("8 h is close to the 8 h limit"); from 17:01 it is Blocked. It warns from the warning point the same way (6 hours here, so from 15:00).
- The industry page shows "Due in 5 h 20 min", "Due now" or "2 h 5 min overdue", with the due date and time, for example "2026-11-04 17:00 EST". Longer clocks read "Due in 2 days 23 h".
- The time entered is read in the company's timezone and shown back in it; it is stored in UTC, so moving the company to another timezone keeps the same moment. Across a change to or from daylight time the hours are real hours: 72 hours from noon on the Saturday before clocks go back end at 11:00 on the Tuesday. A time that happens twice the night clocks go back is taken the first time (the earlier moment); a time skipped the night clocks go forward, such as 2:30, is read as 3:30.
- One that ran out earlier today counts as overdue, not "due today", in reminders and in Armo's alerts.
- Besides the daily digest, each one gets an email when it reaches its warning point and another when it becomes overdue (section 3.3).

Two more count **minutes since** something happened: "Minutes since the last welfare check of the person in restrictive housing (segregation)" (30 minutes) and "Minutes since a reportable accident was known, without calling MSHA" (15 minutes). They work the same way, in minutes, and are what "hour checks" below means too.

"Hours driven since..." (the 11-hour driving limit) and "Hours in service since..." (the 100-hour aircraft inspection) count hours of driving or flying, not time passed, so they still take a typed number.

A number typed instead of a date stays as typed. The page sends a saved date or number back with every save: a number typed next to the unchanged saved date (or date and time) replaces it, a date picked next to the unchanged saved number replaces that, and a new number with a new date is refused with "Enter a number or a date, not both."

Days are counted in the company's own timezone, so a deadline flips at local midnight, not in London or California.

A date in the future is refused for "days since" checks, with the message "That date is in the future. Enter the date it last happened." A start time in the future is refused for hour checks ("That time is in the future. Enter when it started."), and so is a date without a time.

### 2.4 Done today

For "days since" checks (and the months and years ones), the industry page has a **Done today** button. Pressing it sets the date to today, which restarts the cycle. Hour checks have **Done now** instead, which starts their clock again at the current minute ("Marked done now; the next cycle has started"). When an hour check's report has been made and nothing new has started, **Clear** removes the reading. A yearly inspection that was just done goes back to Cleared and its next due date moves a year out. The audit trail records it as "Marked done today; the next cycle has started."

### 2.5 Entering and clearing readings

On each industry page, every check has its own small form:

- a number box with the unit next to it, for maximums and minimums;
- for date-counted checks, a date picker below it ("Or the date it last happened" or the expiry date); for hour checks, a date-and-time picker ("Or the date and time it started", with the company's timezone, such as EST);
- Yes and No buttons for required and forbidden checks;
- **Save**, and **Clear** to remove the reading.

Below the inputs, the page shows the limit and the warning point, for example "Limit 365 days · warns from 335 days". The app checks every input. A number that isn't a number, or that is infinite, is refused with a message that says what to enter.

**Several at once.** Each check also has a **Select** box. Tick several, then choose one change in "Update several at once" at the top of the page: **Mark done today** (duties that repeat), **Answer Yes** or **Answer No** (yes-or-no checks) or **Set the date** (date-counted checks; hour clocks still need their start time on their own). Each check goes through the same code as a single update, so it gets the same checks and its own audit row. It is all or nothing: if one ticked check can't take the change, or its date is refused, nothing is saved and the page says which check and why. Anyone on the team can use it, as with single updates; a kid's Academy device cannot.

### 2.6 A company's own limits

47 checks use a limit that comes from an industry standard or a common policy, not from law. On those, an owner can set the company's own limit and warning point. The app makes sure the warning point makes sense: for a maximum it must be at or below the limit, and for a minimum at or above it. "Reset" brings the default back. Every change of limit is written to the audit trail. A limit with a part in it, such as 365.5 days or 10.3 years, gives a due date that is the last day still within it and a first Warning day that has really reached the warning point. Limits set by law cannot be changed; the app answers "This limit comes from the rule itself and cannot be changed."

### 2.7 What each screen shows

**HQ (the overview).** The top line shows the company name and today's date in its timezone, then four counts: blocked, warnings, cleared and without a reading, with a thin colored bar showing the proportions. Below that:

- **First day**: the checklist of section 2.1.2, until it is done.
- **Needs attention**: every blocked and warning check across all of the company's industries, most urgent first, each with its message and a link to the check. With none, it says why and what to do next: no check has a reading yet (with a link to the first one to fill in), or how many checks still need one, or "Nice work" when every check has a reading.
- **Coming up**: date-tracked checks due within the next 60 days that aren't a problem yet. With none, it names the next deadline after that, or, before any date is in, a check counted from a date to start with.
- A summary per industry.

**Industry pages.** One page per industry the company tracks, with the industry's counts at the top and its ten checks below: problems first, then the top 5 (section 2.1.1), then the rest. With **Only problems** on and none to show, it says whether that is because nothing has a reading yet. Each check shows its status, its message, the due date and days left when it's date-tracked (for example "15 days overdue · 2026-10-10"), "Why it matters" (the cost and the citation), and its input form.

**Intel (the compliance report).** A table of every check: status, reading, due date, the rule citation, and who last updated it and when. It prints cleanly, and **Export CSV** downloads the same data. The CSV is formula-safe: a cell that starts with a character a spreadsheet could treat as a formula is escaped.

**Vault (the audit trail).** Every change in the workspace: readings, limits, invites and team changes, with the time (UTC), the person, the industry and a "before → after" description, for example "COBRA election notice sent: no reading → date 2026-10-05". It also exports to CSV.

**Radar (reminders).** Every reminder and account email OmniArmor has sent the team, newest first, with its status (sent, saved or failed) and the error for any failure. When email isn't set up, reminders are saved here instead, and a note says so.

**Armory (settings).**

- **Everyone:** their own reminder emails (the daily digest and the time-limit alerts, each on or off; the account with the operator's address also chooses whether to get the weekly Autopilot report), their Armo personality, the Academy plan's status (and that the compliance tracker is free), and About: the version number, and where to get help (the Help page, and the `SUPPORT_EMAIL` address when it is set).
- **Owners also:**
  - change the company name, timezone and industries;
  - invite people and remove members;
  - manage or cancel the Academy plan from its page;
  - delete the whole workspace, by typing the company name to confirm.
- **The operator** (the account with the `OPERATOR_EMAIL` address) also sees the usage counts of the last 30 days (section 6.7).

### 2.8 The public pages

Visitors who aren't signed in see:

- a landing page with the slogan, who it's for and, in the first screen, the price: the compliance tracker is free right now, and the Academy has a free trial (`ACADEMY_TRIAL_DAYS`) and then the Academy plan (`ACADEMY_PRICE_LABEL`, when set), with the first Launchpad worlds free. Every number on it is read from the code and settings;
- a list of all 50 industries;
- one public page per industry (for example `/industries/fleetarmor`) listing its ten checks, its top 5 first with "Why this matters", so a prospect can see their own risks before signing up;
- a sign-in page, a sign-up page, a forgot-password page, and a "Kids" page where a child enters a join code for the Academy;
- a Help page (`/help`) with 15 questions and answers: the free trial, prices, a card at sign-up, what a check is, the three lights, Done today, updating several checks, when reminder emails go out and how to choose them, the Autopilot, the Academy, a kid's progress report, downloading and deleting data, and getting help. Every number on it is read from the code and settings, like the plan page's, and `SUPPORT_EMAIL`, when set, adds an address to write to. It is linked from every page's footer, the landing page and Settings;
- the Terms (`/terms`) and Privacy (`/privacy`) pages, linked from every page's footer. They are written in plain words, and each line matches what the code does. The numbers they quote (trial length, how long links, codes, error reports and backups last) are read from the code and settings, so they stay true when those change. If you change what the app stores, who it shares with or how long it keeps things, update these pages and the date at the top (`RULES_UPDATED` in `omniarmor_app/__init__.py`).

The site also serves a `sitemap.xml` listing the public pages (home, the industry list and the 50 industry pages, sign up, sign in, Help, Terms and Privacy), and a `robots.txt` that keeps search engines out of the signed-in app (with the Academy and Settings), password reset and invite links, the kids' join page and the addresses only programs use. Every page that isn't public is also marked `noindex`, in the page and in an `X-Robots-Tag` header (which covers the CSV exports too); the list of public pages is `PUBLIC_PAGES` in `omniarmor_app/__init__.py`. The public pages carry share previews (Open Graph and Twitter card tags with a 1200 x 630 picture) and a canonical address. Icons: `favicon.ico` and `favicon.svg`, a 180 x 180 Apple touch icon, and 192 and 512 icons in the web app manifest. Missing pages and server errors get friendly pages in the site's look with a way home; a server error never shows what went wrong inside.

### 2.9 Team, invites and roles

There are two roles: **owner** and **member**.

- **Owners** can invite people, remove members, change company settings, and delete the workspace.
- **Members** can do everything else: enter readings, use Done today, view reports, and change their own reminder switch and Armo.

An invite is a one-time link valid for 7 days. Only a hash of the link is stored, so a stolen database can't be used to join. The invite is recorded in the Vault.

### 2.10 Signing in and staying safe

- **Sign-in** uses email and password. After 5 failed attempts for one email, or 20 from one network address, within 15 minutes, sign-in is paused: "Too many sign-in attempts. Wait 15 minutes, or reset your password."
- **Forgot password** sends a one-time reset link that lasts 1 hour. Requests are limited to 3 per hour per email and 20 per network address. Resetting the password signs the person out on every other device.
- **Sessions** last 14 days.

The full list of protections is in Part 7.

---

## 3. Reminders, the daily job and the record

### 3.1 The reminder windows

Every date-tracked check moves through windows as its deadline gets closer:

- **30 days out**: 8 to 30 days left.
- **7 days out**: 2 to 7 days left.
- **1 day out.**
- **Due today.**
- **Overdue**: the first day overdue, then once for each further week it stays overdue.

The first daily run that finds a check in a new window sends one reminder for it. The same window is never reminded twice for the same due date; this is tracked per company, industry, check, due date and window.

**Hour checks** use the same windows, by the date their due time falls on, and the email gives the due time: "Report a work fatality in 8 hours, 2 h 5 min overdue (2026-11-04 17:00 EST)". The digest goes out once a day, so a clock of a few hours can start and run out between two digests; that is what the time-limit alerts (section 3.3) are for. A clock that already had a time-limit alert the same day (in the company's timezone) is left out of that day's digest for the people who get the alerts (someone with alerts off still finds it there), and its window counts as reminded: an overdue window is left out after the overdue alert, a coming-due window after either alert. A digest on another day still lists it, so an overdue clock is reminded about again a week later, as any other check.

**Catch-up:** if the server was down on a given morning, the next run finds the check in its current window and sends it then.

**Retry:** a window only counts as reminded once at least one email went out, or was saved when email isn't set up. If every send failed, the next run tries again. Autopilot also re-sends individual failed emails (Part 6).

### 3.2 The digest email

Each person in the company who has the daily digest on (Settings, "Your reminder emails"; it starts on) gets one email per day at most: a digest of everything that entered a new window. It looks like this:

```
Subject: OmniArmor: 1 overdue, 3 coming due for Acme Logistics

Compliance reminders for Acme Logistics, 2026-10-25.

OVERDUE
- FleetArmor: Annual driving record review, 15 days overdue (2026-10-10). Order the driver's MVR from each state now, review it and file it in the qualification file.

COMING DUE
- FleetArmor: Driver medical certificate current, due in 12 days (2026-11-06). Pull the driver from duty until a certified medical examiner issues a new certificate.
...

Right now: 3 blocked, 5 warnings, 9 cleared, 3 without a reading.
Open your checks: https://your-domain/app

You get this email because the daily digest is on in your OmniArmor settings.

--
Choose which reminder emails you get: https://your-domain/app/settings#reminders
OmniArmor is a product of MTRX Horizyn.
```

### 3.3 Time-limit alerts

The 22 hour clocks and 2 minute clocks run out in as little as 15 minutes (MSHA's accident call), 1 hour (the pipeline call to the National Response Center, NERC CIP-008) or 2 hours (a nursing-home abuse report), too fast for a digest that goes out once a day. So the app's timer checks them **every minute** and emails at most twice per clock, each time it starts:

1. **Warning:** when it reaches its warning point (the rule's "warns from", or the company's own), for example 6 hours into the 8-hour OSHA fatality report.
2. **Overdue:** the minute after its due time, when it turns Blocked.

Each email is about one clock and goes to everyone in the company with time-limit alerts on (a choice of its own in Settings, next to the digest; it starts on). Times are in the company's timezone:

```
Subject: OmniArmor: Report a work fatality in 8 hours, due 2026-11-04 17:00 EST (Acme Logistics)

Time limit warning for Acme Logistics, 2026-11-04 15:00 EST.

- HRArmor: Report a work fatality in 8 hours, due in 2 h (2026-11-04 17:00 EST). Report the fatality to OSHA now by phone or in person, and preserve the scene.

Open it: https://your-domain/app/industry/30#rule-fatality_report_8h

You get this email because time-limit alerts are on in your OmniArmor settings.

--
Choose which reminder emails you get: https://your-domain/app/settings#reminders
OmniArmor is a product of MTRX Horizyn.
```

The overdue one reads "Time limit overdue", "1 min overdue" and, in the subject, "overdue, was due 2026-11-04 17:00 EST".

- **Once each:** each email is recorded in `reminder_marks` by the clock's due moment (in UTC) and its stage (`clock-warning` or `clock-overdue`), so neither is sent twice. Done now, or a new start time, gives the clock a new due moment, and both emails can go out again for it.
- **Only news:** only the stage the clock is in now is sent: a clock entered after it ran out gets the overdue email only. A stage reached more than 24 hours ago (the server was down, or the clock was entered days late) is left to the digest.
- **Retry:** as with the digest, an alert only counts as sent once at least one email went out (or was saved when email isn't set up). If every send failed, the next check, a minute later, tries again. A failed copy is sent again in place, so Radar keeps one copy per person with its number of attempts, and a copy Autopilot already got through is not sent again.
- **Several server processes:** only one process runs the alerts sweep at a time (it holds a lock in the database while it runs, section 3.5), and each alert is claimed in `reminder_marks` before it is sent, so only one process sends it.

### 3.4 How every email looks

Every email OmniArmor sends (the digest, the time-limit alerts, password reset links and Autopilot's emails to the operator) has two parts with the same words: plain text, as above, and HTML, one column 600 pixels wide in the site's colors, with the OmniArmor.ai name on black, the red-to-orange line under it, and a button for each "Open ...:" or "Set a new password:" link. Both are made from the one plain-text body (`omniarmor_app/notify.py`, `templates/email/message.html`), which is also the copy Radar keeps. Under a line, every email ends with "OmniArmor is a product of MTRX Horizyn."; reminders add the link to choose which reminder emails you get (and a `List-Unsubscribe` header pointing there), Autopilot's emails say Autopilot sent them, and the weekly report says where to turn it off. If the HTML part ever fails to draw, the email goes out as plain text rather than not at all. `tests/test_emails.py` makes the app send one of each and checks them all.

### 3.5 The daily job

A built-in timer runs inside the app; there is no separate cron or queue service. It has two threads: one sends any time-limit alerts that are due every minute (above), the other checks every 10 minutes whether the daily job is due and runs Autopilot. So a long daily run (thousands of digests through a slow email provider) never holds the minute alerts up. The job runs once a day, after the hour set by `DAILY_JOB_HOUR_UTC` (11:00 UTC by default). It does three things:

1. **Reminders** for every company, as above.
2. **Cleanup.** It deletes:
   - sign-in failure records older than a day;
   - used or expired password reset links;
   - invites that expired over 30 days ago;
   - expired Academy friend codes and join codes.
3. **Backup**, last, so the copy holds the day's reminders as sent and restoring it never sends them again. It takes a consistent copy of the database using SQLite's online backup, checks the copy (SQLite's quick check), names it `omniarmor-YYYYMMDD-HHMMSS-*.db` only then, as one file that needs nothing beside it to be restored, and keeps the newest 14 copies (`BACKUP_KEEP`). A copy that fails half-way (a full disk) is removed, so the retry makes a real one.

Several server processes can run at once safely. Each sweep (the alerts, the daily job, Autopilot) holds a lock in the database (`job_locks`) while it runs, renewed every 20 seconds, so no two processes run the same sweep at once however long it takes; a process that dies loses its lock within 2 minutes. Each day's run is also claimed in the database, so it happens only once. If a run crashes halfway (for example the server restarted), its claim goes stale after an hour and the next check can claim it again. If any step fails, the run releases its claim and tries again in about 10 minutes; reminders already sent are not repeated.

The job can be run by hand with `flask --app wsgi run-daily --force`; if the server is running it at that moment, the command says so and does nothing. How long the sweeps take with 100 to 2,000 companies is in `docs/LOAD-TEST.md`.

### 3.6 The record

Everything that changes a company's data writes an audit row: who, when, what kind of change, which industry and check, the value before and after, and a one-line summary. Reports and the audit trail can be printed or exported at any time.

---

## 4. Armo, the helper

### 4.1 Who Armo is

Armo is OmniArmor's mascot: a round, friendly shield with big sparkly eyes, a warm blush and little arms, drawn entirely in inline SVG. He has moods (happy, cheer, think, sleep and alert) and idle props (a coffee mug, a book, juggling balls, and "zzz" for a nap).

### 4.2 What he does on the business pages

- **Lives above the tab bar** on every signed-in page, with a badge showing how many things need attention.
- **Has a life of his own.** Every 20 to 40 seconds or so, he does something: drinks coffee, reads, juggles, naps or waves. Now and then he says something in his personality's voice.
- **Jumps up when something needs a person.** He watches for:
  - blocked checks and overdue deadlines (urgent);
  - warnings, deadlines due soon, and reminder emails that failed in the last 7 days (soon);
  - deadlines in the next 30 days, and checks with no reading (info).
- **Walks through every pressing issue.** He shows the most urgent issue with "What to do" (the check's action) and a **Fix it** link straight to the check, then **Next (1 of 8)** for the rest. He walks through up to 8 issues.
- **Checks for changes every minute** while the page is visible, by asking the app's status feed. When the list of issues changes, he jumps up again. When the last issue is fixed, he celebrates.
- **Remembers being dismissed.** Closing him saves which set of issues was dismissed, so he doesn't nag again until something changes.
- **Explains pages.** The first click on a page explains what the page is for. For example, on Intel: "This is Intel, your compliance report. Print it, or export the CSV for an inspector, auditor or insurer."
- **Shares real tips** from the company's own data, mixed into his chatter:
  - the next deadline;
  - how many checks have no reading yet, and where to start;
  - "You're the only one here", which suggests inviting the team;
  - a nudge when the person's email reminders are off, or when email isn't set up on the server;
  - pointers to the Academy, Intel and the Vault.
- **Has his own page** (`/app/armo`) that lists everything he found, each with "What to do" and a Fix it button, plus the personality picker.

### 4.3 Personalities

There are 14 personalities. Each one changes only Armo's words and outfit, never the facts. Each has 61 lines of its own across idle chatter, alerts, all-clear, fixed, poke replies, Academy greetings, cheers, streak shouts, wins and retries. Grown-ups pick one on the Armo page, or turn him off ("Hide Armo"). The default for grown-ups is **Chief** ("Calm and professional"), and for kids it's **Sweetie** ("Sweet and kind"). Each Academy learner picks their own Armo, which changes quiz cheers, streak messages and result lines. The full list is in Appendix C.

---

## 5. The Future Owner Academy

### 5.1 Why it exists

Family businesses are often handed down, but the next generation rarely learns how the business works before they have to run it. The Academy teaches them in small, game-like levels: business words, money, speaking professionally, leading a team, hiring, tough calls, customers, fair competition, negotiation, marketing, sales, operations, safety, ethics, contracts, taxes, cyber safety, planning, reading numbers, sustainability, a winning mindset, and the family company's own compliance rules.

### 5.2 Learners

A grown-up in the workspace adds a **learner** from the Academy home page. A learner is only a nickname and a picture; there is no email, password or birthday. There are 9 pictures to choose from: Rocket, Star, Bolt, Crown, Gem, Shield, Paw, Leaf and Planet. A workspace can have up to 12 learners. The add form also picks the track (5.3), Launchpad unless changed, and **Start the first lesson** opens stage 1 of the track's first world: from opening the Academy to the first results takes 13 steps (it took 15, with a track page and the map in between; `tests/test_first_lesson.py` walks it and counts). A kid who joins on their own device with nothing played yet lands on that first lesson too. Learners added before this pick their track on their first visit.

**Progress report.** For the grown-ups in the workspace, each learner has a progress report (linked from the Academy home and the learner's map): lessons passed, the average best score, the streak, questions waiting in practice, each track's levels, stars, rank and certificate, and every lesson played with its best score, stars, tries and the day it was passed. A kid's own device can't open it, and another workspace gets "not found".

### 5.3 The four tracks

Each track keeps its own progress, and a learner can switch at any time.

- **Launchpad (Basic), 1,350 levels.** "Blast off with the basics."
  - The 16 core worlds, 50 stages each.
  - The Owner's Challenge, 50 stages.
  - 50 Rule Quests (one per industry), 10 stages each.
  - 5 to 8 questions per level, passing at 60% to 80%.
- **Trailblazer (Intermediate), 2,700 levels.** "Every world of business."
  - All 43 worlds, 50 stages each.
  - The Owner's Challenge, 50 stages.
  - Rule Quests at 10 stages each.
  - Same question counts and pass marks as Launchpad.
- **Summit (Advanced), 5,400 levels.** "Twice the stages, tougher questions."
  - 43 worlds, 100 stages each.
  - The Owner's Challenge, 100 stages.
  - Rule Quests at 20 stages each.
  - 6 to 10 questions per level, passing at 70% to 85%.
- **Titan Mastery, 15,700 levels.** "The ultimate mastery program."
  - 43 worlds, 300 stages each.
  - The Owner's Challenge, 300 stages.
  - Rule Quests at 50 stages each.
  - 8 to 12 questions per level, passing at 75% to 90%.

### 5.4 Worlds and units

There are 43 topic worlds in 9 units, plus the Owner's Challenge (a boss world) and 50 Rule Quests.

- **Foundations** (8 worlds, on every track):
  - Meet Your Company
  - Business Words
  - Why Rules Matter
  - Stop, Careful, Go
  - Countdown Calendar
  - Money Smarts
  - Talk Like a Pro
  - Lead the Team

  Several of these use the family company's own name, industries and checks. "Stop, Careful, Go" teaches the Cleared, Warning and Blocked traffic lights with real rules.
- **Leadership** (8 worlds, on every track):
  - Own It
  - Never Give Up
  - Earn Instant Respect
  - Build Your Dream Team
  - Tough Calls
  - Win Customers
  - Beat the Competition
  - Pro Business Moves
- **Money and Finance:** Price It Right, Budget Boss, Save and Grow, Banks and Borrowing.
- **Growth:** Get the Word Out, Build a Brand, Sales Superstar, Business Online.
- **Operations:** Run the Machine, Stock Smart, Supply and Demand, Safety First.
- **Mindset:** Goal Getter, Master Your Time, Big Ideas, Cool Under Pressure.
- **Rules and Trust:** Do the Right Thing, Deals and Contracts, Taxes Explained, Cyber Shield.
- **The Big Picture:** Start a Business, Business Plans, Read the Numbers, Business Around the World, Grow Green.
- **Winning Mindset:** Champion Mindset and Habits of Winners.

The last seven units (27 worlds) are on Trailblazer, Summit and Titan Mastery.

**Rule Quests**: one per industry, built from that industry's ten checks. A family's own industries are listed first ("Acme Logistics's Rule Quests"); the rest can be explored. Rule Quests open after stage 1 of "Stop, Careful, Go".

**The Owner's Challenge** mixes questions from every world and is where certificates are earned.

### 5.5 How unlocking works

- Stage 1 of the first world is open from the start.
- Each later stage opens when the stage before it has at least one star.
- Each later world opens when stage 1 of the world before it in the track has a star.
- The Owner's Challenge opens when stage 1 of every topic world in the track has a star.
- Rule Quests open after stage 1 of world 4, "Stop, Careful, Go".

### 5.6 How a level works

- **Stage 1 of every world teaches.** It starts with 4 to 6 short lesson cards that Armo presents one at a time (Next and Back), then the quiz. Later stages go straight to the quiz.
- **Questions get harder as stages go on.**
  - The number of questions grows from the track's minimum to its maximum across the world.
  - Question banks are graded easy, medium and hard, and deeper stages draw more of the hard ones.
  - The pass mark rises: the track's lower pass rate for the first 20% of stages, the midpoint up to 60%, then the higher rate.
- **Review:** questions from earlier worlds are mixed in, one per level once a level has more than 5 questions.
- **Every tenth stage is a boss round**, with 2 extra questions and 3 review questions.
- **Stars:**
  - **3 stars** for a perfect score.
  - **2 stars** for at least 80% (or 10 points above the pass mark, whichever is higher).
  - **1 star** for passing.
- **Instant feedback** (when the page's script runs):
  - each answer is marked right or wrong at once, with the reason why;
  - Armo reacts, and a progress bar fills;
  - a streak counter rises, with a flame and a shimmering bar from 3 in a row;
  - a right answer throws a burst of sparks;
  - the first answer counts.
- **Grading happens on the server.** Each quiz is generated from a seed made of the learner, track, world, stage and attempt number. The server rebuilds the exact same questions to grade them. A new attempt gets a new seed and new questions. Nothing about a level is stored except the learner's best score and stars, which is why even 15,700 levels add almost nothing to the database.
- **The results page** shows:
  - the score counting up, and stars popping in;
  - a slow sunburst and confetti on a win;
  - Armo's reaction in the learner's personality;
  - what unlocked;
  - every question with the right answer and the reason.

### 5.7 Practice, goals, ranks and certificates

- **Practice my mistakes.** Every missed question is saved. Practice serves up to 8 at a time. A mistake answered right comes back after 1 day, then 3 days, then 7 days; after that it's mastered and removed. Only due mistakes are graded, and resubmitting an old practice page does nothing. Each question is one practice card, even one that can come with a different right answer (a family in two industries is asked "What kind of work does Acme do?" with either as the answer), so practice never asks the same question twice in a row.
- **Daily goal and streak.** The daily goal is 3 levels. Playing at least one level a day builds a streak.
- **Ranks**, which grow with the track's size:
  - Rookie (from 0 levels)
  - Apprentice (5)
  - Team Captain (15)
  - Manager (40)
  - Executive (100)
  - Future Owner (250)
  - Business Legend (600)
  - Tycoon (1,000)

  Each rank makes the learner's picture fancier, with rings, an aura and sparkles.
- **Certificates**, earned by passing the Owner's Challenge:
  - Future Owner (1 level)
  - Silver Future Owner (100)
  - Gold Future Owner (500)
  - Platinum Business Legend (every level)

  On tracks other than Launchpad the title includes the track, for example "Titan Mastery Platinum Business Legend". The certificate prints on one landscape page, A4 or US Letter, with nothing of the app around it (`certificate-print.css`, loaded only for printing).
- **Word Bank.** A glossary of 201 business words, each with a kid-friendly meaning, open from the map.

### 5.8 Friends and duels

- A parent makes a single-use friend code, valid for 7 days. Another family's parent enters it. Code guessing is rate limited, and the letters avoid look-alikes (no 0 and O, no 1 and I).
- A learner can have up to 30 friends.
- Friends see only a nickname, picture, rank and stars. There is no chat.
- **Duels:**
  - A learner challenges a friend to a 5-question duel in one of the general business worlds.
  - Both players get the same questions, and the winner shows when both have played.
  - Duels never use a company's name or rules.
  - A world that a player's family plan doesn't include can't be used for a duel, and an opponent without it sees a friendly message instead.

### 5.9 Kids' own devices

A grown-up can make a single-use **join code** for a learner, valid for 7 days. If two devices type the same code at once, only the one that uses it up gets in. On the kid's phone, tablet or computer, the kid opens the Kids page and types the code. That device gets an Academy-only session: no business pages, no email, no password, and only that one learner in that one family. "Sign out on every device" ends all of a learner's device sessions at once. A device can also leave on its own ("Leave the Academy on this device").

### 5.10 The Academy plan

The Academy has its own subscription, separate from the compliance service.

- **Free trial.** Every workspace gets a free trial of the whole Academy when it adds its first learner, 14 days by default (`ACADEMY_TRIAL_DAYS`). Workspaces that already had learners when the plan was introduced get the trial automatically.
- **After the trial**, the first three Launchpad worlds stay free, and everything else needs the plan.
- **The plan page** explains the compliance tracker, the free Academy and the Academy plan side by side in plain words. Every number and name on it comes from `plan_facts()` in `academy_views.py`, read from the settings and the code that enforces the plan, and a test checks that the template has no number typed into its words.
- **Finding the plan.** The Academy home always links to the plan page: to start it, to manage or cancel it once paid, or to update the card after a failed payment. Owners also find it in the Armory.
- **Payment** goes through **Stripe Checkout**, and the customer portal handles changes and cancellations. When a family comes back from paying, the plan page asks Stripe about that checkout and turns the plan on at once, without waiting for the webhook (and doesn't offer checkout again while the payment is being confirmed). A signed Stripe webhook keeps the plan's status current:
  - **Access:** active, trialing, and past due (which keeps access while Stripe retries the card).
  - **No access:** canceled, unpaid, incomplete or none.
  - **Cancelled in the portal:** Stripe keeps the plan on until the paid period ends. The plan page says "Cancelled · ends" with the date instead of a renewal date, and the workspace can be deleted right away, since nothing more will be charged.
  - **After the plan ends:** a workspace that has paid before keeps a "Past invoices and billing" link on the plan page, beside the button to start again, so the owner can still open Stripe's portal for receipts or to fix the card on an unpaid plan.
- **Webhook safety:**
  - Events are de-duplicated by event id, and events older than the last one applied are ignored.
  - Events about a different subscription than the active one are ignored, so a cancelled duplicate can't switch off a paid plan.
  - Checkout refuses to start a second subscription when the plan is already paid.
- **Without Stripe**, the plan can be switched by hand: `flask --app wsgi academy-plan <workspace id> active`.

### 5.11 The look

The Academy uses the same dark theme as the rest of the app, made playful for kids: a rounded display font (Baloo 2), big touch targets and bright accents. Each unit has its own color family, used only on badges, scenes and progress bars so pages stay calm:

- Foundations: blue
- Leadership: purple
- Money and Finance: green
- Growth: coral pink
- Operations: amber
- Mindset: teal
- Rules and Trust: indigo
- The Big Picture: ocean blue-green
- Winning Mindset: gold

**Sticker badges.** Worlds have badges in their unit's colors, with a gold check sticker when finished and a padlock when locked. Unit headers on the map show a little pile of the unit's world stickers and a progress bar.

**World scenes.** Each world page opens on a small scene in its colors:

- rolling hills, a glowing sun and drifting clouds;
- the world's sticker, with a light sweeping across it;
- three icons from that part of business floating around;
- Armo standing on the hill.

**Animations:**

- Map cards rise in, unit stickers float, badges wiggle on hover, and the world in progress shines.
- Lesson cards slide in, and Armo hops in with each one.
- A right answer throws sparks and its letter pops; a miss shakes.
- On a streak of 3 or more, the progress bar shimmers and a flame lights up.
- The current stage has a bouncing marker.
- Results count up under a sunburst.

Every animation switches off for people whose device asks for reduced motion.

### 5.12 Content quality

All Academy content is written, not generated on the fly, and checked by tests:

- **1,333** written questions and true-or-false facts in the question banks for the 27 newer worlds, each graded easy (1), medium (2) or hard (3), with lesson cards for each world.
- **255** leadership scenarios across nine pools: speaking like a pro, owning it, never giving up, respect, hiring, tough calls, customers, competition and pro moves.
- **201** words in the Word Bank.
- Questions built from the company's own name, industries and checks, and from the 500-rule catalog for Rule Quests. A Rule Quest's wrong answers never come from the same duty in another industry under another title (the DEA's biennial inventory is a check for drug makers and for pharmacies), and never read almost like the right answer, so each question has exactly one right answer.

The test rules for the question banks:

- Every world needs 4 to 6 lesson cards, at least 30 questions with at least 8 at each level, and at least 10 facts with at least 3 true and 3 false.
- Option text is limited to 120 characters, question text to 170 and explanations to 240.
- The text must be plain ASCII, with no braces, no curly quotes, no em dashes, and never "all of the above" or "none of the above".
- No question may repeat, and the three options must differ.
- The right answer may be the longest option in at most 40% of questions, so kids can't guess by length. After a rebalancing pass, most worlds sit near 25 to 33%, about what pure chance gives with three options.

`tests/test_quiz_fairness.py` checks the quizzes kids actually get, every track's topic worlds and the Owner's Challenge from many seeds, including the questions written into `academy.py` for the first worlds: every question has different options and one right answer; the right answer is the longest option in at most 45% of a world's worded questions and 33% overall; each slot of a three-option question holds at least 20% of the right answers; and true-or-false questions are true 30% to 70% of the time (bank worlds pick a true or a false fact at even odds, and the first worlds draw from mixed pools of facts).

---

## 6. Autopilot and the bug finder

### 6.1 Why

The goal is a service that runs without someone checking it every day. The daily job already handles reminders, backups and cleanup. Autopilot covers everything else: it looks the service over every 10 minutes, fixes small problems on its own, and emails the operator only about the big ones.

### 6.2 Small problems it fixes by itself

- **Failed emails.** It re-sends them, waiting longer after each try: 10 minutes after the first failure, then 1 hour, then 6 hours, within 2 days of the original email. A password reset email is not re-sent once the link inside has expired.
- **A missing backup.** Once the daily job has run at least once, if the newest backup is over 26 hours old, it makes one.
- **Safe data slips.** Once a day it removes leftover rows that point at deleted records (in tables where that is safe), corrects star counts outside 0 to 3, and moves learners with an unknown track back to Launchpad.
- **Tidying.** Once a day it:
  - deletes recorded server errors older than 30 days and its own log entries older than 180 days;
  - trims its own bookkeeping;
  - compacts the database's write-ahead log when it grows past 64 MB;
  - runs SQLite's optimizer.

Every fix is written to Autopilot's log.

### 6.3 Big problems it emails to the operator

- **A new bug** (6.4).
- **The daily self-test failing** at any step (6.5).
- **Broken Academy quizzes** found by the daily content check.
- **Database rows that don't add up** and aren't safe to fix automatically.
- **Emails still failing after every retry**, 3 or more in a day.
- **Email not set up** while running in production.
- **Backups failing**: no backup newer than about 27 hours even after Autopilot tried to make one.
- **The daily job** not finishing in 2 days.
- **Low disk space**: under 1 GB or under 5% free.
- **Database damage**, found by SQLite's quick check once a day.

Each problem is emailed once, with a title, the details and "What to do". While it lasts, Autopilot sends one reminder a day ("Still open: …"). When it clears up, it sends "Fixed: …", once. A problem that comes back within an hour of clearing up (free disk space hovering at the limit, say) is the same problem flapping: it is written to the log, not emailed again, and neither is its next "Fixed". A bug already emailed stays open while it keeps happening, even when five others happen more often. Whatever happens, Autopilot sends at most 10 emails an hour; past that, the messages go to the server log. On Mondays it sends a short weekly report, but only if anything happened that week (something fixed, or any alert); a quiet week sends nothing. If the operator's address has an OmniArmor account, its Settings page has a box to turn the weekly report off; problems are always emailed.

The emails go to `OPERATOR_EMAIL`. Without that setting, or without email set up, the same messages go to the server log.

### 6.4 The bug finder

- **Crash fingerprints.** Every server error (a page that fails with a 500) is recorded with the page address, the error, the full traceback, and a **fingerprint**: the kind of error plus the file and function in OmniArmor's own code where it happened. Line numbers are left out, so unrelated edits don't change it. A fingerprint seen for the first time is a new bug. Autopilot emails it with:
  - how many times it happened in the last day, and on which pages;
  - when it was first seen;
  - where in the code it happened;
  - the end of the traceback.

  It reports up to 5 bugs at a time, most frequent first, plus a note if there are more. A bug counts as fixed once it hasn't happened for a day.
- **The daily self-test.** Once a day, Autopilot starts a private copy of the app on an empty, throwaway database in a temporary folder, and clicks through the main paths:
  1. the home page, industries page and health check;
  2. signing up a test company;
  3. HQ, an industry page, the report and its CSV, the audit trail, Radar, settings and Armo's status feed;
  4. the Academy home, adding a learner, picking a track, the map and a world page;
  5. opening a level, finishing it with all answers right, and confirming it was saved with 3 stars;
  6. practice, friends, the plan page and signing out.

  Any page that crashes or answers with the wrong status fails the test at that step, and the email names the step. Real data is never touched.
- **The content check.** Once a day it generates quizzes across every track and world (the first stage, the last stage and a few random ones) and checks each makes sense:
  - the right number of questions;
  - a pass mark that can be reached;
  - a real right answer and different options for every question;
  - an explanation for every question.

### 6.5 Running it by hand

- `flask --app wsgi autopilot` runs every check now and prints what it fixed and what needs a person.
- `flask --app wsgi autopilot --log` shows what it fixed and reported in the last 30 days.

It is on by default (`AUTOPILOT_ENABLED`). Several server processes are safe: each 10-minute pass and each daily pass is claimed in the database first, and a pass holds the Autopilot lock while it runs, so a slow pass (failed emails re-sent to a provider that times out) never has a second one beside it re-sending the same emails. `flask --app wsgi autopilot` says so if the server is running a pass right then.

### 6.6 Error reports to one inbox

With `ERRORS_EMAIL` set, every page that fails with an unexpected error (a 500) also sends that address a short report straight away, beside Autopilot's own bug emails (which are unchanged). It says:

- the time (UTC) and the version;
- the request's method and path, with the query string removed;
- the kind of error, its message and its fingerprint (the same one the bug finder uses);
- the stack trace, with file paths relative to the project (`omniarmor_app/views.py`) or to the library folder (`flask/app.py`).

It carries no personal data. It is built only from the error and the request's method and path, never the request's body, form, cookies, headers or IP address, nor who was signed in. Anything in the path, the message or a code line that looks like an email address, an IP address, a token or a secret is replaced (`[email]`, `[ip]`, `[token]`, `[hidden]`), and reset and invite links are hidden as in the logs. A test sends a request with an email address in its query string, its form and a cookie, to a page whose error quotes all three, and checks none of them reaches the report.

The same error is emailed at most once an hour, and no more than 20 reports go out in any 24 hours. Both limits are counted from the reports in the database, inside one write, so a restart or a second server process doesn't reset them. The report goes through the outbox like every email: it is saved first and sent from a thread, so the error page isn't held up; if the send fails, or the server stops first, Autopilot's email retry sends it again. The copies are deleted after 30 days, like the app's own error records. Without `ERRORS_EMAIL` nothing is written or sent.

### 6.7 Usage counts

OmniArmor counts how often a few key features are used, as one total per feature per day (UTC): checks updated (one at a time and in bulk), bulk updates, lessons started (a lesson page opened) and passed, certificates earned, Help page views and sign-ups. A count adds one to the day's total; there is no row per use, no cookie, no account, workspace or learner id, no IP address and no outside service. The account with the `OPERATOR_EMAIL` address sees the last 30 days in Settings; MTRX Horizyn's console gets the same days from `/api/stats`, which answers only its `STATS_KEY`. Totals older than 400 days are deleted by the daily job. The Privacy page says so in one sentence.

---

## 7. Security and privacy

Every point below is in the code today.

### 7.1 Accounts and sign-in

- Passwords must be at least 10 characters (and at most 200). They are stored only as salted, deliberately slow hashes (Werkzeug's password hashing).
- **Sign-in rate limiting:** 5 failures per email or 20 per network address within 15 minutes pauses sign-in.
- **Password reset links** last 1 hour and work once. Reset requests are limited (3 per email and 20 per network address per hour). Only a hash of each link is stored.
- **Invite links** last 7 days, and only their hash is stored.
- **Sessions** are checked on every request against the person's identity: a session counter plus a key made from the person's id, email and creation time. Changing a password bumps the counter, which signs out every other device. A reused account id can't inherit an old session.
- **Redirects after sign-in** only go to pages on the same site; anything a browser could read as another site is refused.

### 7.2 Data and isolation

- Every company's data is looked up through the company in the signed-in session, never by an id the browser sends.
- Industry pages check that the industry belongs to the company and that the rule exists.
- Owner-only actions (invites, removing members, company settings, deleting the workspace) are enforced on the server.
- Every change is in the audit trail.
- Text inputs are cleaned: names with control characters (which could break emails and exports) are refused.
- CSV exports are formula-safe.
- Requests larger than 1 MB are refused.
- Deleting the workspace deletes its data.
- Usage counts (section 6.7) are daily totals only, with no id of any person, workspace or learner, and error reports to `ERRORS_EMAIL` (section 6.6) carry no request data beyond the method and the path without its query.

### 7.3 Web protections

- **CSRF:** every change carries a form token that must match the session.
- **Cookies** are HttpOnly and SameSite=Lax, and Secure in production (so production must use HTTPS). Sessions last 14 days.
- **Security headers on every response:**
  - a strict Content Security Policy that allows only the site's own scripts, plus fonts and styles from Google Fonts;
  - no framing (X-Frame-Options DENY and frame-ancestors none);
  - no MIME sniffing;
  - a same-origin referrer policy;
  - no camera, microphone or location access;
  - HSTS on HTTPS.
- **No caching** of signed-in and kid pages (`Cache-Control: no-store`).
- **Proxies:** behind a proxy, the app trusts only the configured number of proxy hops (`TRUSTED_PROXIES`) for the client address, so rate limits can't be dodged with a forged header.

### 7.4 Kids

- A learner is a nickname and a picture. No email, password, birthday or real name is asked for.
- **Kid devices:**
  - A kid device's session is bound to one learner, one family and a random device number.
  - A device left over from a deleted learner can't end up signed in as a different child, even if the database reuses the learner's id.
  - Ending all of a learner's device sessions is one click.
- **Friends and duels:**
  - Friend codes are single-use, expire in 7 days, and code guessing is rate limited.
  - Friends see only a nickname, picture, rank and stars.
  - There is no chat.
  - Duels use only general business worlds, never a company's name or rules.

### 7.5 Payments

- Card details never touch OmniArmor; Stripe Checkout and the Stripe customer portal handle them.
- **Webhooks:**
  - Each webhook is checked against Stripe's signature and must be no more than 5 minutes old.
  - Repeats are ignored, and so are events older than the last one applied.
  - Events about a different subscription than the active one are ignored.
  - A checkout never turns a plan back on once it has ended, or hides a failed payment: not a checkout event Stripe retries days later, and not the "thank you" page opened again from browser history.

### 7.6 Bugs fixed in a security review

An independent review of the Academy code found seven real bugs, and all were fixed with regression tests:

1. **Wrong child on a device.** A kid device could end up signed in as a different child, even in another family, after a learner was deleted and its id reused. Fixed with random device numbers and a family check; user sessions got the same protection.
2. **Paid worlds through duels.** Duels could open paid worlds without the plan. They now respect each player's plan.
3. **Duplicate subscriptions.** A cancelled duplicate subscription could switch off a paid plan, and checkout could create that duplicate. Both are fixed.
4. **Stripe events.** Late, repeated or out-of-order events could leave a plan in the wrong state. Events are now de-duplicated and ordered.
5. **Fake practice.** Practice could be "mastered" by resubmitting a page or repeating ids. Only due questions now count, once.
6. **Odd numbers in addresses.** Huge or non-ASCII numbers in web addresses or forms caused server errors. They now give a clean "not found".
7. **Lost access on deploy.** Workspaces that already had learners would have lost Academy access when the plan launched. They get the trial.

Kid pages are also no longer cached.

---

## 8. How the code is built

### 8.1 The big picture

OmniArmor is a single Python web app (Flask) with a SQLite database. It needs no separate database server, job queue, cache or image host. Pages are plain HTML forms that work without JavaScript; small scripts add Armo, the game feel of the Academy, and live updates. Everything visual (the logo, Armo, icons, avatars, emblems and world scenes) is inline SVG, so there are no image files to host.

```
Browser (HTML forms, no JavaScript needed)
   │  sign-in cookie + form token on every change
   ▼
omniarmor_app (Flask)
   ├── security.py     sign-in, form tokens, rate limits, security headers
   ├── auth.py         sign up, sign in, password reset, invites
   ├── views.py        HQ, industry checks, report, audit trail, Radar, settings
   ├── tracking.py     turns stored readings into today's status
   ├── catalog.py      the 50 industries and 500 rules, as the app uses them
   ├── reminders.py    daily digests per company, and time-limit alerts for the hour clocks
   ├── jobs.py         the timer: time-limit alerts each minute; reminders, cleanup, backup each day; sweep locks; CLI commands
   ├── notify.py       email, or the saved log when email isn't set up
   ├── armo.py         Armo's issue list, tips and page help
   ├── armo_lines.py   the 14 personalities and their lines
   ├── armo_views.py   the Armo page, status feed and personality picker
   ├── academy.py      the Academy engine: worlds, tracks, quizzes, ranks
   ├── academy_bank/   question banks for the 27 newer worlds
   ├── academy_views.py the Academy pages, kids' devices, friends, duels, practice, plan
   ├── academy_plan.py the Academy subscription and Stripe
   ├── autopilot.py    the 10-minute health pass: fixes and operator emails
   ├── bugfinder.py    crash fingerprints, daily self-test, content and data checks
   └── db.py           SQLite connection, schema migrations, audit writes
   ▼
SQLite database (one file on a persistent disk) + daily backups
```

### 8.2 The repository

- `omniarmor_app/`: the web app (modules above).
  - `templates/`: HTML pages, split into `app/` (business pages), `auth/` (sign-in pages), `academy/` (Academy pages) and `kids/` (the join page), plus `base.html`, `home.html`, the public industry pages and the error page.
  - `static/`:
    - `app.css` and `academy.css`, the styles;
    - `armo.js`, the companion;
    - `academy.js`, the lesson stepper, instant feedback, sparks and count-up;
    - `favicon.svg`, `favicon.ico`, `apple-touch-icon.png`, `icon-192.png`, `icon-512.png` and `manifest.webmanifest`, the icons;
    - `og-image.png`, the picture shown when a public page is shared.
- `omni_armor_rules/`: the 500 rules in ten files (`group_1.py` to `group_10.py`, five industries each), and `rule.py` with the `Rule` format and the single `evaluate` function every rule uses. The catalog is validated when it's imported.
- `omni_armor_platform.py`: the original engine. It holds the theme table of 50 industries with their colors, plus 25 detailed checks (one per original industry, such as an hours-of-service timer and a MARPOL discharge check), an audit log, and a console demo.
- `dashboard/`: a standalone demo page of all 500 checks (the "Risk Console"), built from the catalog by `build_dashboard.py` into `index.html`. Its JavaScript `evaluate` mirrors `rule.py`; a test proves they agree on 2,700 sample readings. Day checks take a date there too, and hour checks a date and time, counted in the browser's timezone.
- `tests/`: 623 tests in 37 files.
  - End to end, through the real pages and forms: `test_e2e_industries.py` (52: for every industry, sign up from its public page, save one check of each kind of input, see the right state and find it in the report and CSV; the cases come from the catalog), `test_e2e_accounts.py` (29: Stripe events sent again or late, a failed payment, deleting a workspace, removing a member, CSRF on every POST route and form, sign-in limits, reset links) and `test_e2e_academy.py` (18: one right answer per question across many seeds, practice, certificates, what a kid's device can reach, join codes) and `test_e2e_stripe.py` (3: the Academy plan's whole life against a fake Stripe server on this machine, which answers the app's Stripe calls over HTTP and sends signed webhooks: free trial, trial over, paid, a failed payment, cancelled and paid again, checking the plan, Settings, the plan page and the worlds at each step; Stripe down; a wrong key). `e2e_helpers.py` reads pages the way a browser does.
  - Launch polish: `test_launch.py` (19: the version and changelog, the 404 and 500 pages, every icon and manifest link, share previews, robots.txt, the sitemap and noindex), `test_emails.py` (4: every email the app sends, captured at a fake mail server, at 600 pixels with a text part and the footer) and `test_reminder_choices.py` (10: each person's reminder email choices, and the senders following them).
  - `test_user_flows.py` (75, bugs a person using the app would hit), `test_webapp.py` (50) and `test_academy.py` (50).
  - `test_omni_armor_platform.py` (29) and `test_rule_catalog.py` (23).
  - `test_rule_dates.py` (16: every check against the handbook's Appendix A and its example reading; every date-counted check's due date and warning day from month ends and leap days; every hour and minute clock at its warning and due minute) and `test_operations.py` (13: the backup restore drill and the restore rehearsal of docs/OPERATIONS.md, schema upgrades on real data, streamed exports, Autopilot's email limits, a byte-for-byte dashboard build).
  - `test_academy_fixes.py` (20), `test_autopilot.py` (20) and `test_armo.py` (14).
  - `test_quiz_checks.py` (17), `test_review_fixes.py` (8) and `test_stats.py` (3).
  - `test_academy_bank.py` (2, which check every bank entry).
  - Features added for launch: `test_bulk_entry.py` (15: several checks at once, all or nothing, with the same checks and audit rows as one), `test_help_page.py` (6), `test_plan_page.py` (5), `test_parent_view.py` (9: the progress report, and who can't open it), `test_first_lesson.py` (5: the steps to the first results), `test_certificate_print.py` (2) and `test_quiz_fairness.py` (5: no guessing by length, slot or "True").
  - `test_sweeps.py` (10: the sweep locks, a daily run or Autopilot pass that runs long never started twice, the alerts in their own thread, schema version 14, and the timer only in the server, never in a one-off command).
  - Version 1.1.0: `test_seed_demo.py` (16: the demo workspace's mix of checks, audit trail, Academy and Autopilot, signing in to it, every way it refuses to mix into real data, and backups kept apart from the live ones), `test_error_reports.py` (13: what an error report says, that a request with an email address in its query, form and cookie leaks none of them, the hourly and daily limits across a restart, and delivery through the outbox when mail is down) and `test_usage_counts.py` (13: schema version 15, each count, operator only, `/api/stats`, the Privacy page, and Settings showing the plan, the version and where to get help).
  - `test_parity.py` (1: dashboard against engine, run with Node).
  - `test_first_ten_minutes.py` (26: the landing page's audience, price and trial from the code, sign-up straight to the industry page, the top 5 checks and their why lines, the first-day checklist, the empty states, and the plain-words questions).
  - `test_shared_parent_domain.py` (11: on a subdomain of MTRX Horizyn's domain, the sign-in cookie never carries a `Domain`, no page or preflight grants another origin, framing stays refused, and the Terms, Privacy, footer and every email name MTRX Horizyn, and no page, email or file in the repository uses the company's old spelling).
  - `test_logs.py` (4: the main flows against gunicorn as the Docker image runs it and against the development server, then the daily job, the alerts, Autopilot and a crash, with every log line searched for passwords, tokens, cookies, keys and full email addresses) and `test_cookies_and_time.py` (7: the one cookie's flags and lifetime through every way in and out; dates shown in the workspace's time zone; no naive or local clock in the code).
- `docs/`:
  - `ARCHITECTURE.md`, `OPERATIONS.md` and `COSTS.md`;
  - `academy-preview/`, with 31 screenshots.
- Packaging and hosting:
  - `Dockerfile`;
  - `docker-compose.yml` with a `Caddyfile` for free automatic HTTPS;
  - `render.yaml` for one-click Render;
  - `.env.example`;
  - `wsgi.py`, the production entry point;
  - `requirements.txt`: flask 3.1.3, werkzeug 3.1.9, gunicorn 22.0.0 and tzdata.
- `.github/workflows/ci.yml`: on every push, installs the requirements, runs pyflakes, runs the tests and builds the Docker image.

### 8.3 The life of a reading

1. A person enters a reading on an industry page. The form posts to `/app/industry/<id>/rule/<key>` with its form token.
2. `security.py` checks the token and the sign-in. The route checks that the industry belongs to the company and the rule exists.
3. `tracking.apply_change` validates the input, writes the reading, and writes an audit row with who, when, before and after.
4. When any page loads, `tracking.states_for_org` reads the company's readings. For date-tracked rules it counts days from today in the company's timezone; hour clocks count the minutes from their stored UTC start to now. Then `omni_armor_rules.evaluate` gives Cleared, Warning or Blocked: the same answer the engine and the demo dashboard give.
5. Each morning, `jobs.run_daily` claims the day. `reminders.run_reminders` then finds deadlines at 30, 7, 1 and 0 days or overdue (an hour check past its due time is overdue), records each window so it's sent once, and emails each team member a digest. Every minute, `jobs.run_alerts` calls `reminders.run_clock_alerts`, which emails a clock's warning and overdue alerts as they come (section 3.3).

### 8.4 The data model

The database is one SQLite file in WAL mode with foreign keys on. The schema upgrades itself at start-up through numbered migrations (currently 1 to 15), under SQLite's write lock so several processes starting together don't race.

**Core:**

- `users`: email, name, password hash, reminder choices (the daily digest, the time-limit alerts, and the weekly Autopilot report for the operator's account), Armo personality, the day last seen, and a session counter.
- `orgs`: companies, with their name, timezone and Academy plan fields:
  - status, trial end, renewal date, and the end date of a cancelled plan;
  - Stripe customer and subscription ids;
  - the time of the last Stripe event applied.
- `memberships`: who belongs to which company, as owner or member.
- `org_industries`: which of the 50 industries each company tracks.
- `items`: one row per company and rule, holding the number, yes/no or date, any company limit and warning point, and who updated it when (the name is kept too).
- `audit`: every change, with person, time, action, industry, rule, before and after, and a summary. The person's name is stored on the row, so a removed team member's changes still show who made them.
- `notifications`: every email sent or saved, with status, error and number of attempts. It is the outbox: Autopilot sends failed ones again from here, error reports (section 6.6) included.
- `reminder_marks`: which reminder windows were already sent, for which due date, and which time-limit alerts, for which due moment.
- `invites` and `password_resets`: one-time links, stored as hashes.
- `login_failures`: recent failed sign-ins and reset requests, for rate limiting.
- `job_runs`: one row per run of the daily job and of Autopilot's passes, so each runs once.
- `job_locks`: the lock each sweep (alerts, daily job, Autopilot) holds while it runs, as a lease its holder renews.

**Academy:**

- `learners`: nickname, picture, Armo personality, track, whether the track was chosen, and a random device number.
- `learner_progress`: best score, best stars, attempts and completion time per level. A level's id is `track × 1,000,000 + world × 1,000 + stage`.
- `learner_days`: levels played per day, which drives the streak and the daily goal.
- `learner_mistakes`: missed questions, with the miss count, streak and when each is due again.
- `join_codes`: kid device codes.
- `friend_codes`, `learner_friends` and `duels`.

**Operations:**

- `autopilot_events`: Autopilot's log of fixes, alerts and resolutions.
- `app_errors`: recorded server errors, with page, error, fingerprint, code location and traceback.
- `stripe_events`: Stripe event ids already applied.
- `usage_counts`: one total per feature per day (section 6.7), with no user, workspace or learner id.

### 8.5 World numbering in the Academy

- **1 to 16:** the original worlds (Foundations and Leadership).
- **17:** the Owner's Challenge.
- **18 to 44:** the 27 question-bank worlds, in unit order: money, growth, operations, mindset, rules and trust, the big picture, then the Winning Mindset worlds at 43 and 44. (On the map, worlds are shown with a running count instead, so Champion Mindset appears as "World 42".)
- **101 to 150:** the 50 Rule Quests, numbered 100 plus the industry's number.

New worlds are always added at the end of the list, so existing progress keeps its level ids.

### 8.6 How quizzes are made

- **The original worlds** generate questions from code:
  - the company's own name, industries and rules;
  - business words from the glossary;
  - traffic-light questions from real rule thresholds;
  - calendar math with real weekdays;
  - money math;
  - professional speech;
  - leadership scenarios from the nine pools.
- **The bank worlds** draw graded questions and facts from `academy_bank/`. Easier ones come early in a world and harder ones later, following each track's difficulty mix.
- **Rule Quests** turn an industry's ten checks into questions about the rule, the limit and what to do.
- **The Owner's Challenge** mixes questions from all of these.
- A seed made of learner, track, world, stage and attempt makes every quiz repeatable, so the server can grade it without storing it.

---

## 9. Running, deploying and operating it

### 9.1 On a computer

```sh
python3 -m venv .venv && . .venv/bin/activate   # Python 3.11, as in the Dockerfile; 3.13 works too
pip install -r requirements.txt -c constraints.txt
flask --app wsgi run --port 8000          # development, at http://localhost:8000
python3 -m unittest discover -s tests     # 623 tests
python -m pyflakes omni_armor_platform.py omni_armor_rules/rule.py omniarmor_app dashboard/build_dashboard.py wsgi.py tools  # the lint CI runs
```

Command-line tools:

- `flask --app wsgi init-db`: create or upgrade the database.
- `flask --app wsgi run-daily [--force]`: send reminders, back up and clean up now.
- `flask --app wsgi backup`: back up the database now.
- `flask --app wsgi academy-plan <workspace id> active|none|canceled`: switch a workspace's Academy plan by hand.
- `flask --app wsgi autopilot [--log]`: run Autopilot's checks now, or show its log.
- `flask --app wsgi seed-demo [--force NEW_FILE] [--password ...]`: make the demo workspace for screenshots and sales calls (section 9.8).
- `python3 dashboard/build_dashboard.py`: rebuild the standalone Risk Console after changing a rule.
- `python3 tools/load_test.py http` and `python3 tools/load_test.py sweep`: the load test and the sweep timings, on a throwaway database (`docs/LOAD-TEST.md`).

### 9.2 Hosting options

OmniArmor is a product of MTRX Horizyn and has no domain of its own. MTRX Horizyn owns the one domain (its own site on the domain itself and `www`), and OmniArmor runs on the subdomain `omniarmor.<your domain>`, beside the company's other apps on theirs. A subdomain rather than a folder keeps each app its own origin: the sign-in cookie has no `Domain`, so it goes back only to OmniArmor's own address, and the app sends no CORS headers, so a sibling app's page can't read it. Setting it up: one DNS record for `omniarmor` (a `CNAME` to Render, or an `A` record to your server), the host's custom-domain step (Render's Custom Domains, or `DOMAIN` for Caddy), HTTPS (both get the certificate themselves), and `BASE_URL=https://omniarmor.<your domain>`. docs/OPERATIONS.md section 1 has the steps.

- **Render (easiest):** push the repository to GitHub, then choose New > Blueprint in Render. `render.yaml` creates the web service with a 1 GB persistent disk, a health check and a random `SECRET_KEY`. Set `BASE_URL`. It needs a paid plan because the app needs a persistent disk.
- **One small server (cheapest):**
  1. Create a free-tier or smallest VM with Docker.
  2. Add an A record named `omniarmor` on MTRX Horizyn's domain, pointing at it.
  3. Copy the repository, run `cp .env.example .env`, and set `SECRET_KEY`, `BASE_URL` and `DOMAIN`.
  4. Run `docker compose up -d`.

  Caddy gets and renews free HTTPS certificates and compresses responses.
- **Any Docker host:** build the image and run it with a volume at `/data` and a `SECRET_KEY`, behind HTTPS.

The Docker image:

- runs as a non-root user;
- keeps the database and backups in `/data`;
- has a built-in health check against `/healthz`;
- writes an access log with password-reset and invite tokens, and the Stripe Checkout id a payer comes back with, replaced by `[hidden]` (also when they sit percent-encoded inside another address, such as a sign-in page's `next`), so the hosting dashboard never holds a working link. Every other log line (the app's own, Autopilot's, a crash's traceback, and the development server's access log) goes through the same filter, which also shortens each email address to its first letter and domain (`p***@example.com`). Log times are UTC and say so.
- runs gunicorn with one process and 8 threads by default (`WEB_CONCURRENCY`, `WEB_THREADS`), which fits the smallest VMs. Its 60-second timeout restarts a worker that stopped responding or took that long to start; with threads it never cuts a page off. The slowest pages in a big workspace (all 50 industries, half a million audit rows) were measured: the audit CSV takes about 10 seconds and streams from the first moment, every page well under a second. Deep audit pages took about 1.5 seconds until an index holding the trail's whole sort order (schema version 12) made them about five times faster. Under load (`docs/LOAD-TEST.md`), one process serves about 90 to 100 requests a second; the first thing to give is response time, at a few hundred people clicking at once, with no errors or lost changes.

### 9.3 Email

Without email settings, reminders and password-reset links are saved on Radar instead of sent. To send real email, sign up with any SMTP provider, verify the sending domain, and set `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD` and `MAIL_FROM`. All of MTRX Horizyn's apps send from its one domain, so SPF, DKIM and DMARC are set up once on that domain; OmniArmor sends from its own address there, such as `OmniArmor <no-reply@omniarmor.<your domain>>`, and every email ends with "OmniArmor is a product of MTRX Horizyn." STARTTLS is on by default. Free sending tiers are usually enough, because each person gets at most one reminder email per company per day, plus two time-limit alerts each time an hour or minute clock runs (section 3.3).

### 9.4 Backups and restore

Backups are files named `omniarmor-YYYYMMDD-HHMMSS-*.db` in `BACKUP_DIR`. `flask --app wsgi backup` makes one now. Copy them off the server regularly, because a backup on the same disk doesn't survive losing the disk.

To restore, follow the 10-minute checklist in docs/OPERATIONS.md, section 4: copy the backup to a fresh file beside the database, check it, point `DATABASE_PATH` at it and restart, then check sign-in, the checks, the Academy and the Vault. The old database stays as it was, so going back is one setting. `tests/test_operations.py` rehearses it on every push.

### 9.5 Monitoring

- `GET /healthz` returns `{"status": "ok"}` with HTTP 200 when the app and database are working (and the schema is current), with the schema version and the release number (`omniarmor_app/version.py`, also shown in Settings under About) and nothing else. Point an uptime monitor at it.
- Set `OPERATOR_EMAIL` so Autopilot can email problems, and optionally `ERRORS_EMAIL` for a short report of each server error (section 6.6).
- The server log records each daily run, each Autopilot fix, and any failure.

### 9.6 Upgrades

Back up first, then deploy the new version. Raise the number in `omniarmor_app/version.py` and add its section at the top of `CHANGELOG.md` with each release (a test checks the two agree). The schema upgrades itself at start-up. Run the tests before every deploy; GitHub Actions does it on every push.

### 9.7 What it costs to run

- **Server:** a free-tier VM, or the smallest VPS plan.
- **Database:** included (SQLite on the server's disk).
- **Reminders and backups:** included, built into the app.
- **HTTPS:** free (Caddy and Let's Encrypt).
- **Email:** optional; a free sending tier, or a low per-email price.
- **Domain name:** nothing to buy: OmniArmor runs on a subdomain of MTRX Horizyn's domain.
- **Off-server backup copies:** recommended; a free object-storage tier.
- **Payments:** Stripe's per-payment fee, with no monthly fee.

What the app does to stay cheap:

- one process with threads, and SQLite;
- static files cached for a year, with links that change when the file changes;
- inline SVG instead of images;
- Academy levels generated, not stored;
- at most one reminder email per person per company per day, plus the time-limit alerts;
- daily cleanup of old records.


### 9.8 A demo workspace

`flask --app wsgi seed-demo --force demo.db` makes a believable workspace for screenshots and sales calls in a new database file, with made-up names: Juniper Lane Pharmacy, tracking PharmacyArmor and HRArmor, an owner and a pharmacist on the team, checks done, coming due and overdue (the dates are counted from the day it is seeded), a few weeks of audit trail, the morning's digest kept in Radar (never sent), two Academy learners partway through on the Academy plan (one with a certificate), and Autopilot's history with one real pass at the end. It prints the sign-in addresses (on the reserved `.example` domain) and the password. It refuses any database holding an account, a workspace or a learner, checks again inside the write, and in production never touches the app's own database, even an empty one. docs/OPERATIONS.md, section 6, has the steps.
---

## 10. Design and writing style

### 10.1 The look

The business app is dark: a warm near-black background (#0F0E0D), raised surfaces (#1A1816), warm off-white text (#E9E2D8), and muted text (#ABA297). The accent is an ember gradient from red through orange (#E5261C → #FF6A36 → #F59234). Status colors are red for Blocked (#F0301F) and orange for Warning (#F08A2E); Cleared is quiet grey.

Type:

- **Big Shoulders Display**, a tall condensed face in capitals, for page titles and the logo;
- **IBM Plex Sans** for text;
- **IBM Plex Mono** for labels, dates and citations;
- **Baloo 2**, a rounded face, for the Academy.

Controls are at least 44 pixels tall, text meets WCAG AA contrast, Warnings differ from Blocks by shape as well as color, and everything works without JavaScript. The bottom tab bar (HQ, Intel, Vault, Radar, Academy, Armory) appears on every signed-in page, on desktop and phone.

### 10.2 The writing

All of the app's words follow the same rules, and new work should too:

- Plain, direct sentences. Write the way a knowledgeable person talks.
- Name things by what people recognize (reminders, checks, the report), not how the system is built.
- Messages say what's wrong and what to do: "380 days is over the 365 days limit. Order the driver's MVR from each state now, review it and file it in the qualification file."
- Buttons say exactly what happens: "Done today", "Fix it", "Export CSV", "Make a join code".
- No em dashes or mannered phrasing in content; the Academy banks are plain ASCII.
- Kid-facing text is warm and encouraging and never mean: "Good try! Now you know."

---

## 11. How it was built: the history

The project was built in steps, each one a commit on GitHub:

1. **The platform script.** `omni_armor_platform.py`, with a parsing bug (a stray docstring delimiter) fixed.
2. **25 detailed industry checks** with cited rules and tests. Each check returns Cleared, Warning or Blocked with the rule it applies. Rule details were corrected along the way, for example:
   - FDA Food Code cold holding at 41°F;
   - the FAA 100-hour inspection by flight hours;
   - MARPOL distances by waste type;
   - California nurse ratios.
3. **The 500-rule catalog** for 50 industries (the original 25 plus 25 more), with one shared `evaluate`, and the interactive **Risk Console** dashboard built from the catalog.
4. **Risk Console upgrades.** The slogan, problems sorted first, date pickers on the 123 day-count rules, a copyable plain-text report, and search across all rules. Then a switch to one accessible dark theme, and a minimalist redesign.
5. **The OmniArmor web app.**
   - sign-up, workspaces, invites and password reset;
   - per-company tracking with timezones, Done today and policy limits;
   - the daily job with reminder digests, backups and cleanup;
   - the audit trail, the printable report and CSV exports;
   - public industry pages;
   - security: CSRF, rate limits, safe redirects, hashed tokens and security headers;
   - Docker, Render, CI and the docs.

   A review then fixed an open redirect, a header-injection crash, a migration race, lost reminders and more.
6. **The Future Owner Academy**, first version: 1,350 levels, with friends and duels, and the bottom tab bar.
7. **Lower running costs:**
   - one process with 8 threads;
   - year-long static caching;
   - the docker-compose plus Caddy setup;
   - the costs guide.
8. **Armo:**
   - redrawn as a friendlier shield, with moods and idle props;
   - six personalities, then 14, each with over 60 lines;
   - a live helper above the tabs;
   - the walkthrough of every issue, real tips from company data, and page help.
9. **Academy expansion:**
   - four tracks (first up to 15,100 levels);
   - 25 new worlds from the question banks;
   - spaced-repetition practice, daily streaks and goals, and boss rounds;
   - avatars that level up;
   - join codes for kids' own devices;
   - the Academy's own Stripe plan.
10. **Answer balance.** Wrong answers were rewritten across every pool and bank so the right answer is no longer usually the longest, and a test keeps it that way.
11. **The Winning Mindset unit:** Champion Mindset and Habits of Winners, adding 12 lesson cards, 79 questions and 28 facts. Totals became 43 worlds and up to 15,700 levels.
12. **Autopilot with the bug finder**, together with fixes for the seven bugs found in an independent review (section 7.6).
13. **Friendlier graphics:**
    - a color family for each unit;
    - sticker badges with check and padlock stickers;
    - unit headers with sticker piles;
    - lesson progress dots, and A/B/C answer letters;
    - a fix for Armo turning dark on every lesson card after the first.
14. **World scenes and game-like animations**, all switched off for reduced motion.
15. **Ready for launch (version 1.0.0, `CHANGELOG.md`):**
    - hour and minute clocks with time-limit alerts, and business-day clocks;
    - updating several checks at once (bulk entry);
    - each person's reminder email choices in Settings;
    - the Help page, the Academy plan page, and a progress report for each learner;
    - a shorter first lesson and certificates that print on one page;
    - one look for every email, friendly error pages, icons, share previews, the sitemap and robots.txt;
    - a version number in Settings and `/healthz`, and the changelog.
16. **Reliability (1.0.1):** a load test of 500 workspaces at once, the sweeps timed at up to 2,000 workspaces, a lock so no sweep runs twice at once, the alerts in a thread of their own, the daily backup taken after the reminders, and a rehearsed 10-minute restore checklist (`docs/LOAD-TEST.md`).
17. **For selling and running it (1.1.0):** a demo workspace in one command, error reports to one inbox with no personal data, privacy-friendly daily usage counts for the operator, and Settings showing the plan, the version and where to get help to everyone on the team.

Previews, the playable lesson pages and this handbook's companion brief were published as private pages in the original account.

---

## 12. Where things stand, what's next, and how to keep working

### 12.1 Where things stand

- **Repository:** `rayan-baig/omniarmor.ai` on GitHub.
- **Branch:** `claude/wonderful-heisenberg-77tbq9`, the live default branch. Everything above is on it.
- **Version** 1.1.1 (`omniarmor_app/version.py`, `CHANGELOG.md`).
- **Tests:** 623 tests pass, and pyflakes is clean. GitHub Actions runs both, an audit of the dependencies and a Docker build on every push.
- **Database schema** is at version 15.
- **Before the next deploy:**
  - **Set `OPERATOR_EMAIL`** and the SMTP settings so Autopilot can email problems, and `SUPPORT_EMAIL` for the Help page.
  - **Back up** the database first, as always.

### 12.2 Known gaps and good next steps

- **Billing for the compliance service** isn't built yet. The Academy plan already uses Stripe, and the same pattern (Checkout, portal, signed webhook) would work.
- **Integrations.** Readings are entered by hand. Pulling hours from ELDs, temperatures from sensors, or employee data from HR systems would cut data entry.
- **One workspace per person.** Consultants and multi-location owners would want several.
- **English only.**
- **Rule review.** A compliance professional should review the catalog before selling, especially rules marked as policy. Most rules are US federal, with some state and city rules (California, Illinois, New York City), the GDPR, PCI DSS and NFPA standards, and maritime conventions (MARPOL, SOLAS, STCW, MLC).
- **Business steps only the founders can take:**
  1. Incorporate (for example as a Delaware C corporation).
  2. Get an EIN, open a business bank account, and assign the code and name to the company.
  3. Have a lawyer review the Terms and Privacy pages and the catalog.
  4. Add the `omniarmor` subdomain on MTRX Horizyn's domain (docs/OPERATIONS.md, section 1).
- **Scale.** The app is built for one small server. `docs/LOAD-TEST.md` has the measured limits and when to grow: more processes (`WEB_CONCURRENCY`) and a bigger server first, then a different database (Postgres) at roughly a few thousand busy workspaces or several servers.

### 12.3 How to keep working on it

These are the habits the project was built with. Keep them:

- **Run the tests and the lint before every commit:** `python3 -m unittest discover -s tests` and the pyflakes line in `.github/workflows/ci.yml`. Add tests for every fix and feature, close to the files they cover.
- **Commit on the working branch** with clear messages. Each message has a short summary line and a body that says what changed and why. Push with `git push -u origin <branch>`. Don't open a pull request unless the owner asks.
- **New Academy worlds** go at the end of the world list, so existing progress keeps its level ids. Content must pass `tests/test_academy_bank.py`, including the answer-length balance.
- **Schema changes** are new numbered migrations at the end of `db.py`. Never edit one that has shipped.
- **Every company query** goes through the signed-in company. Never trust an id from the browser.
- **Pages must work without JavaScript**, with scripts as an extra layer. Keep motion purposeful and switched off for reduced motion.
- **Write the app's text** in the style of Part 10: plain, specific and kind.
- **Check the real app in a browser** after a visual change, on desktop and phone width, and look at the screenshots before calling it done.

---

---

## Appendix A: All 50 industries and 500 checks
Every check, as the app holds it. "Limit" is the line that makes a check Blocked; "warns from" is the point where it turns to Warning. "Policy" means the limit is an industry standard or common policy that a company can change. "Counts days since" and "counts days until" mark the 126 checks counted in days from a date; the 19 checks counted in months or years and the 16 counted in business, working or work days since a date (section 2.3) can be tracked from a date too.

### 1. FleetArmor (Logistics)

**1. 11-hour driving limit** (Maximum 11 h, warns from 10 h)

- Asks: Hours driven since the driver's last 10 hours in a row off duty
- Rule: 49 CFR 395.3(a)(3)
- What a miss costs: Out-of-service orders idle the truck and load, and HOS violations raise CSA scores and insurance costs.
- What to do when it's broken: Stop driving; 10 hours off duty in a row required.
- Example reading used in demos: 11.5 h

**2. Electronic logging device in use** (Must be in place, answered Yes or No)

- Asks: Is the driver logging hours of service on a registered electronic logging device (ELD), or covered by a listed exemption?
- Rule: 49 CFR 395.8(a); 49 CFR Part 395 Subpart B
- What a miss costs: Drivers without a required ELD are placed out of service, and missing records are cited in audits and raise CSA scores.
- What to do when it's broken: Do not dispatch; install a registered ELD or document the exemption that applies.
- Example reading used in demos: Yes

**3. Driver medical certificate current** (Minimum 0 days, warns from 30 days; counts days until a date)

- Asks: Days until the driver's medical card (medical examiner's certificate) expires
- Rule: 49 CFR 391.41(a); 49 CFR 391.45
- What a miss costs: A driver without a valid medical card is placed out of service, and using unqualified drivers draws audit penalties.
- What to do when it's broken: Pull the driver from duty until a certified medical examiner issues a new certificate.
- Example reading used in demos: 12 days

**4. Valid CDL for the vehicle** (Must be in place, answered Yes or No)

- Asks: Does the driver hold a valid commercial driver's license (CDL) with the class and endorsements this vehicle and load need?
- Rule: 49 CFR 383.23(a); 49 CFR 383.37
- What a miss costs: Letting a driver operate without a valid CDL of the right class draws civil penalties, out-of-service orders and crash liability.
- What to do when it's broken: Do not let this driver operate the vehicle; assign a properly licensed driver.
- Example reading used in demos: Yes

**5. Annual driving record review** (Maximum 365 days, warns from 335 days; counts days since a date)

- Asks: Days since the driver's driving record (MVR) was last pulled and reviewed for the yearly check
- Rule: 49 CFR 391.25
- What a miss costs: Missing annual reviews are cited in compliance reviews and weaken the carrier's defense in negligent-retention lawsuits.
- What to do when it's broken: Order the driver's MVR from each state now, review it and file it in the qualification file.
- Example reading used in demos: 380 days

**6. Pre-employment drug test** (Must be in place, answered Yes or No)

- Asks: Has this driver's drug test from before hiring come back as a verified negative?
- Rule: 49 CFR 382.301(a)
- What a miss costs: Using a driver before a negative drug result is an acute audit violation that can lead to penalties and an unsatisfactory rating.
- What to do when it's broken: Keep the driver off all safety-sensitive work until a verified negative result is on file.
- Example reading used in demos: No

**7. Annual Clearinghouse query** (Maximum 365 days, warns from 335 days; counts days since a date)

- Asks: Days since the last Drug and Alcohol Clearinghouse query on this driver
- Rule: 49 CFR 382.701(b)
- What a miss costs: Skipping required Drug and Alcohol Clearinghouse queries is cited in audits and can leave a prohibited driver on the road.
- What to do when it's broken: Run a Clearinghouse query on this driver today and keep the record.
- Example reading used in demos: 200 days

**8. Annual vehicle inspection** (Maximum 365 days, warns from 335 days; counts days since a date)

- Asks: Days since the vehicle's last annual (periodic) inspection
- Rule: 49 CFR 396.17
- What a miss costs: Vehicles without a current periodic inspection are cited at roadside and in audits, and raise vehicle maintenance CSA scores.
- What to do when it's broken: Take the vehicle out of service until a qualified inspector completes the annual inspection.
- Example reading used in demos: 345 days

**9. Steer tire tread depth** (Minimum 4 32nds of an inch, warns from 5 32nds of an inch)

- Asks: Shallowest tread depth on any steering-axle tire, in 32nds of an inch
- Rule: 49 CFR 393.75(b)
- What a miss costs: Worn steer tires are an out-of-service condition that idles the truck, and tire violations raise vehicle maintenance CSA scores.
- What to do when it's broken: Do not dispatch; replace the steer tire before the vehicle moves.
- Example reading used in demos: 6 32nds of an inch

**10. 70-hour/8-day on-duty limit** (Maximum 70 h, warns from 63 h)

- Asks: On-duty hours in the last 8 days in a row (for carriers on the 70-hour/8-day schedule)
- Rule: 49 CFR 395.3(b)(2) (60 h/7 days in 395.3(b)(1) if not operating every day)
- What a miss costs: Driving past the 60/70-hour limit brings out-of-service orders and is a frequently cited HOS violations in audits.
- What to do when it's broken: No more driving until on-duty hours fall under 70, or take a 34-hour restart.
- Example reading used in demos: 66 h

### 2. RestoArmor (Restaurants)

**1. Cold holding at 41°F or below** (Maximum 41°F, warns from 40°F)

- Asks: Current temperature of cold-held food that needs temperature control for safety (TCS food)
- Rule: FDA Food Code 3-501.16(A)(2)
- What a miss costs: Out-of-temperature food is discarded, is a priority violation at inspection and can cause outbreaks and lawsuits.
- What to do when it's broken: Hold the food; check how long it was above 41°F and discard it if safe time cannot be shown.
- Example reading used in demos: 43°F

**2. Hot holding at 135°F or above** (Minimum 135°F, warns from 140°F)

- Asks: Current temperature of hot-held food that needs temperature control for safety (TCS food)
- Rule: FDA Food Code 3-501.16(A)(1)
- What a miss costs: Food held below 135°F must be reheated or discarded, is a priority violation and can cause outbreaks.
- What to do when it's broken: Reheat the food to 165°F within 2 hours if allowed, or discard it; fix the holding unit.
- Example reading used in demos: 138°F

**3. Cooling 135°F to 70°F in 2 hours** (Maximum 2 h, warns from 1.5 h)

- Asks: Hours it took to cool cooked TCS food from 135°F to 70°F
- Rule: FDA Food Code 3-501.14(A)(1)
- What a miss costs: Improper cooling is a common cause of foodborne outbreaks and requires the batch to be reheated or thrown out.
- What to do when it's broken: Reheat to 165°F and restart cooling, or discard; use shallow pans or ice baths.
- Example reading used in demos: 1.25 h

**4. Ready-to-eat food 7-day limit** (Maximum 7 days, warns from 6 days; counts days since a date, the first day as day 1)

- Asks: Days since this ready-to-eat TCS food was prepared or opened and held at 41°F, counting that day as day 1
- Rule: FDA Food Code 3-501.17(A); 3-501.18
- What a miss costs: Food past its date mark must be thrown out and is cited at inspection; it raises Listeria risk.
- What to do when it's broken: Discard the food now and check date labels on the rest of the cooler.
- Example reading used in demos: 8 days

**5. No bare-hand contact with RTE food** (Must never happen, answered Yes or No)

- Asks: Did staff touch ready-to-eat food with bare hands?
- Rule: FDA Food Code 3-301.11(B)
- What a miss costs: Bare-hand contact with ready-to-eat food is a priority violation and a main route for norovirus outbreaks.
- What to do when it's broken: Discard the food touched, have staff wash hands and use gloves, tongs or deli tissue.
- Example reading used in demos: No

**6. Hand sinks accessible and stocked** (Must be in place, answered Yes or No)

- Asks: Is every handwashing sink clear, used only for handwashing and stocked with soap and paper towels?
- Rule: FDA Food Code 5-205.11; 6-301.11; 6-301.12
- What a miss costs: Blocked or unstocked hand sinks are frequently cited inspection items and lead to repeat inspections.
- What to do when it's broken: Clear the sink and restock soap and towels now.
- Example reading used in demos: Yes

**7. Sick employees kept off work** (Must never happen, answered Yes or No)

- Asks: Is any employee with vomiting or diarrhea working in the restaurant?
- Rule: FDA Food Code 2-201.11; 2-201.12(A)
- What a miss costs: Ill food workers cause outbreaks that bring closures, lawsuits and lost customers.
- What to do when it's broken: Send the employee home, clean and sanitize affected areas and log the exclusion.
- Example reading used in demos: No

**8. Premises free of pests** (Must never happen, answered Yes or No)

- Asks: Are there signs of rodents or insects (droppings, live or dead pests)?
- Rule: FDA Food Code 6-501.111
- What a miss costs: Evidence of rodents or insects can close the restaurant on the spot and forces food discards.
- What to do when it's broken: Call a licensed pest control operator, discard contaminated food and clean affected areas.
- Example reading used in demos: Yes

**9. Certified food protection manager** (Must be in place, answered Yes or No)

- Asks: Is at least one manager with authority over food prep a certified food protection manager?
- Rule: FDA Food Code 2-102.12(A) (as adopted by state or local code)
- What a miss costs: Having no certified food protection manager is cited at inspection and can hold up permits.
- What to do when it's broken: Enroll a manager in an accredited food protection manager exam now.
- Example reading used in demos: Yes

**10. Overtime paid over 40 hours** (Must be in place, answered Yes or No)

- Asks: Are employees who are owed overtime (nonexempt) paid 1.5 times their regular rate for hours over 40 in a workweek?
- Rule: Fair Labor Standards Act, 29 U.S.C. 207(a)(1)
- What a miss costs: Unpaid overtime leads to back wages, equal liquidated damages and class or collective lawsuits.
- What to do when it's broken: Correct the payroll and pay back overtime owed; review how the regular rate is figured for tipped staff.
- Example reading used in demos: No

### 3. YachtArmor (Superyachts)

**1. Untreated sewage 12 nm from land** (Minimum 12 nm, warns from 13 nm)

- Asks: Distance from the nearest land where untreated sewage is to be discharged
- Rule: MARPOL Annex IV reg. 11.1.1
- What a miss costs: Illegal sewage discharge draws Coast Guard and port state fines and can lead to detention of the yacht.
- What to do when it's broken: Do not discharge; hold sewage until the yacht is over 12 nm out and en route at 4 knots or more.
- Example reading used in demos: 8 nm

**2. Oily bilge discharge under 15 ppm** (Maximum 15 ppm, warns from 12 ppm)

- Asks: Oil content of the bilge water leaving the oily-water separator
- Rule: MARPOL Annex I reg. 15; 33 CFR 151.10
- What a miss costs: Oily discharges bring pollution fines, detention and criminal prosecution of the owner, operator and crew.
- What to do when it's broken: Stop the discharge and keep oily water on board for delivery ashore.
- Example reading used in demos: 9 ppm

**3. Oil Record Book kept complete** (Must be in place, answered Yes or No)

- Asks: Is every bilge, sludge and oily-waste operation entered accurately in the Oil Record Book?
- Rule: MARPOL Annex I reg. 17; 33 U.S.C. 1908 (Act to Prevent Pollution from Ships)
- What a miss costs: Missing or false Oil Record Book entries are a main basis for U.S. criminal pollution cases and port state detentions.
- What to do when it's broken: Bring the Oil Record Book up to date with accurate entries and receipts; never alter past entries.
- Example reading used in demos: Yes

**4. Officer STCW certificates valid** (Minimum 0 days, warns from 90 days; counts days until a date)

- Asks: Days until the officer's STCW certificate of competency or endorsement expires
- Rule: STCW Convention reg. I/2 and reg. I/11 (revalidation)
- What a miss costs: Expired certificates of competency are a common port state control deficiency and can detain the yacht until replaced.
- What to do when it's broken: Take the officer off watch in that role until the certificate is revalidated; arrange a qualified relief.
- Example reading used in demos: 150 days

**5. ECA fuel sulfur 0.10% or less** (Maximum 0.1%, warns from 0.09%)

- Asks: Sulfur content of the fuel burned inside an Emission Control Area (ECA), by weight
- Rule: MARPOL Annex VI reg. 14.4
- What a miss costs: Burning high-sulfur fuel in an Emission Control Area draws EPA and port state penalties and forced fuel changes.
- What to do when it's broken: Change over to compliant fuel now and log the changeover time and position.
- Example reading used in demos: 0.08%

**6. Crew rest 10 hours in 24** (Minimum 10 h, warns from 11 h)

- Asks: Hours of rest the crew member had in the last 24 hours
- Rule: MLC 2006 Standard A2.3.5(b); STCW Code A-VIII/1
- What a miss costs: Hours of rest breaches are a common port state control deficiency, can detain the yacht and create crew injury claims.
- What to do when it's broken: Relieve the crew member now and adjust the watch schedule; record rest hours accurately.
- Example reading used in demos: 9 h

**7. Crew medical certificate valid** (Minimum 0 days, warns from 30 days; counts days until a date)

- Asks: Days until the crew member's medical fitness certificate expires
- Rule: MLC 2006 Regulation 1.2; Standard A1.2
- What a miss costs: Crew without a valid medical certificate is a port state control deficiency that can delay departure.
- What to do when it's broken: Book a medical exam with a recognized practitioner before the crew member works again.
- Example reading used in demos: 20 days

**8. Monthly abandon-ship and fire drills** (Maximum 31 days, warns from 25 days; counts days since a date)

- Asks: Days since the crew's last abandon-ship drill and fire drill
- Rule: SOLAS Ch. III reg. 19.3 (every crew member, every month)
- What a miss costs: Missed drills are a frequent port state control deficiency and weaken the defense after a casualty.
- What to do when it's broken: Hold abandon-ship and fire drills before the next voyage and log them.
- Example reading used in demos: 27 days

**9. Liferaft annual service** (Maximum 365 days, warns from 335 days; counts days since a date)

- Asks: Days since each inflatable liferaft was last serviced at an approved station
- Rule: SOLAS Ch. III reg. 20.8 (12 months; flag state may extend to 17)
- What a miss costs: Overdue liferaft servicing is a port state control deficiency that can detain the yacht and void insurance cover.
- What to do when it's broken: Send the liferaft to an approved service station or fit a serviced replacement before sailing.
- Example reading used in demos: 400 days

**10. Garbage Record Book kept** (Must be in place, answered Yes or No)

- Asks: Is every garbage discharge, burning on board and delivery ashore entered in the Garbage Record Book, with receipts?
- Rule: MARPOL Annex V reg. 10.3 (400 GT and above, or certified for 15 or more persons)
- What a miss costs: Missing or incomplete Garbage Record Book entries are a frequent port state control deficiency and support pollution fines.
- What to do when it's broken: Bring the Garbage Record Book up to date and file shore reception receipts.
- Example reading used in demos: Yes

### 4. AeroArmor (Aviation)

**1. 100-hour inspection** (Maximum 100 h, warns from 90 h)

- Asks: Hours in service since the last 100-hour inspection
- Rule: 14 CFR 91.409(b); 14 CFR 135.411(a)(1)
- What a miss costs: Flying for hire past the 100-hour inspection grounds the aircraft and draws FAA civil penalties per flight.
- What to do when it's broken: Ground the aircraft for hire; complete the 100-hour inspection (up to 10 h over allowed only to reach it).
- Example reading used in demos: 94 h

**2. Single-pilot 8-hour flight time** (Maximum 8 h, warns from 7 h)

- Asks: Flight time assigned to a single-pilot crew in the last 24 hours
- Rule: 14 CFR 135.267(b)(1) (unscheduled one- and two-pilot crews)
- What a miss costs: Scheduling pilots past flight time limits draws FAA civil penalties and raises accident risk and liability.
- What to do when it's broken: Do not assign more flying; use a two-pilot crew or a rested pilot.
- Example reading used in demos: 6.5 h

**3. 10 hours rest before assignment** (Minimum 10 h, warns from 11 h)

- Asks: Hours of rest in a row during the 24 hours before the assignment is planned to end
- Rule: 14 CFR 135.267(d)
- What a miss costs: Assigning a pilot without required rest draws FAA civil penalties and fatigue-related accident liability.
- What to do when it's broken: Do not dispatch this pilot; reschedule so the pilot gets 10 hours of rest in a row.
- Example reading used in demos: 9 h

**4. Pilot competency check current** (Maximum 12 months, warns from 11 months)

- Asks: Calendar months since the pilot's last Part 135 competency check
- Rule: 14 CFR 135.293(b)
- What a miss costs: Using a pilot with a lapsed competency check draws FAA civil penalties and can put the certificate at risk.
- What to do when it's broken: Remove the pilot from Part 135 flights until a competency check is passed.
- Example reading used in demos: 11 months

**5. Pilot medical certificate current** (Must be in place, answered Yes or No)

- Asks: Does each pilot hold a current medical certificate of the class this flight requires?
- Rule: 14 CFR 61.3(c); 14 CFR 61.23
- What a miss costs: Flying with an expired or wrong-class medical is a certificate action for the pilot and a civil penalty for the operator.
- What to do when it's broken: Replace the pilot with one holding a current medical certificate of the required class.
- Example reading used in demos: Yes

**6. Drug and alcohol testing program** (Must be in place, answered Yes or No)

- Asks: Is every safety-sensitive employee in the FAA drug and alcohol testing program, with a pre-employment test on file?
- Rule: 14 CFR Part 120 (120.105, 120.215); 49 CFR Part 40
- What a miss costs: Gaps in the FAA drug and alcohol program are a common basis for FAA civil penalties against charter operators.
- What to do when it's broken: Keep untested employees off safety-sensitive work and enroll them in the program now.
- Example reading used in demos: No

**7. IFR proficiency check in 6 months** (Maximum 6 months, warns from 5 months)

- Asks: Calendar months since the pilot in command's last instrument proficiency check
- Rule: 14 CFR 135.297(a)
- What a miss costs: Using a pilot for IFR flights with a lapsed instrument check draws FAA civil penalties and increases liability after an incident.
- What to do when it's broken: Remove the pilot from IFR flights for hire until an instrument proficiency check is passed.
- Example reading used in demos: 7 months

**8. No overdue airworthiness directives** (Must never happen, answered Yes or No)

- Asks: Is any airworthiness directive (AD) that applies to this aircraft overdue?
- Rule: 14 CFR 39.7
- What a miss costs: Flying with an overdue airworthiness directive makes the aircraft unairworthy and draws FAA civil penalties.
- What to do when it's broken: Ground the aircraft until the directive is complied with and recorded.
- Example reading used in demos: No

**9. IFR fuel reserve 45 minutes** (Minimum 45 min, warns from 50 min)

- Asks: Minutes of fuel, at normal cruise, planned to be left after reaching the alternate airport on an IFR flight
- Rule: 14 CFR 135.223(a)(3) (airplanes)
- What a miss costs: Fuel planning violations draw FAA enforcement and fuel exhaustion accidents bring hull loss and liability.
- What to do when it's broken: Add fuel, reduce load or pick a closer alternate before departure.
- Example reading used in demos: 60 min

**10. Altimeter and static test (IFR)** (Maximum 24 months, warns from 22 months)

- Asks: Calendar months since the last altimeter and static system test
- Rule: 14 CFR 91.411(a)
- What a miss costs: Flying IFR with an overdue altimeter and static system test makes the flight illegal and draws FAA penalties.
- What to do when it's broken: Restrict the aircraft to VFR until the altimeter and static system test is done and logged.
- Example reading used in demos: 25 months

### 5. HospitalArmor (Hospitals)

**1. Med-surg nurse staffing ratio** (Maximum 5 patients per nurse, warns from 5 patients per nurse; policy, a company can set its own limit)

- Asks: Patients per licensed nurse on a medical-surgical unit
- Rule: Cal. Code Regs. tit. 22, 70217 (California 1:5 med-surg; policy elsewhere); 42 CFR 482.23(b)
- What a miss costs: Short staffing leads to survey citations, state penalties where ratios are law, and patient harm lawsuits.
- What to do when it's broken: Call in nursing staff or hold admissions until the ratio is back within limit.
- Example reading used in demos: 5.5 patients per nurse

**2. EMTALA medical screening exam** (Must be in place, answered Yes or No)

- Asks: Does every person who comes to the emergency department asking for care get a medical screening exam, not delayed by payment questions?
- Rule: 42 U.S.C. 1395dd(a); 42 CFR 489.24(a) and (d)(4)
- What a miss costs: EMTALA violations bring OIG civil penalties, possible loss of Medicare participation and patient lawsuits.
- What to do when it's broken: Screen the patient now and stop any payment or insurance questions that delay the exam.
- Example reading used in demos: Yes

**3. HIPAA breach notice within 60 days** (Maximum 60 days, warns from 45 days; counts days since a date)

- Asks: Days since a breach of unsecured protected health information (PHI) was discovered, with affected patients not yet notified
- Rule: 45 CFR 164.404(b)
- What a miss costs: Late breach notices draw OCR penalties and state attorney general actions, and add to class action exposure.
- What to do when it's broken: Send notices to affected patients now, without further delay, and prepare the HHS report.
- Example reading used in demos: 50 days

**4. HIPAA security risk analysis** (Must be in place, answered Yes or No)

- Asks: Is there a current risk analysis, for the whole organization, covering every system that holds electronic patient health information (ePHI)?
- Rule: 45 CFR 164.308(a)(1)(ii)(A)
- What a miss costs: A missing or outdated risk analysis is among the most common findings in OCR settlements and penalties.
- What to do when it's broken: Start an enterprise-wide security risk analysis and document the risk management plan.
- Example reading used in demos: No

**5. Patient records within 30 days** (Maximum 30 days, warns from 25 days; counts days since a date)

- Asks: Days since the patient's request for their records, with no extension notice sent
- Rule: 45 CFR 164.524(b)(2)
- What a miss costs: Slow responses to patient records requests have led to many OCR right-of-access settlements.
- What to do when it's broken: Provide the records now, or send the patient a written notice of the one 30-day extension allowed.
- Example reading used in demos: 12 days

**6. Violent restraint order 4 hours** (Maximum 4 h, warns from 3.5 h; counts hours since a date and time)

- Asks: Hours since the current restraint order for an adult's violent or self-destructive behavior was written
- Rule: 42 CFR 482.13(e)(8)(ii)(A) (adults 18 and older)
- What a miss costs: Restraint violations are cited in CMS surveys, can threaten Medicare participation and lead to injury lawsuits.
- What to do when it's broken: Have a physician or authorized practitioner assess the patient and renew or end the order now.
- Example reading used in demos: 4.5 h

**7. Informed consent before surgery** (Must be in place, answered Yes or No)

- Asks: Is a signed and completed informed consent form in the chart before this non-emergency procedure?
- Rule: 42 CFR 482.51(b)(2); 42 CFR 482.24(c)(4)(v)
- What a miss costs: Surgery without documented informed consent is cited in CMS surveys and is a common basis for malpractice claims.
- What to do when it's broken: Hold the procedure until informed consent is obtained and documented.
- Example reading used in demos: Yes

**8. Quarterly fire drill on every shift** (Must be in place, answered Yes or No)

- Asks: Has a fire drill been held on every shift in the current quarter?
- Rule: 42 CFR 482.41(b); NFPA 101 (2012) 18.7.1.6 / 19.7.1.6
- What a miss costs: Life safety deficiencies are frequently cited in CMS and accreditation surveys and require costly corrective plans.
- What to do when it's broken: Schedule and hold fire drills on each shift missing one this quarter and document them.
- Example reading used in demos: No

**9. Physician agreements signed and current** (Must be in place, answered Yes or No)

- Asks: Is every paid arrangement with a referring physician covered by a signed agreement still in effect (or in an allowed holdover period after it ended)?
- Rule: 42 U.S.C. 1395nn (Stark Law); 42 CFR 411.357
- What a miss costs: Expired or unsigned physician agreements can make Medicare claims false, leading to refunds and False Claims Act settlements.
- What to do when it's broken: Stop referral-linked billing under the lapsed arrangement and have counsel renew it and review past claims.
- Example reading used in demos: No

**10. Standard charges file updated yearly** (Maximum 365 days, warns from 335 days; counts days since a date)

- Asks: Days since the machine-readable standard charges file was last updated
- Rule: 45 CFR 180.50(e)
- What a miss costs: Hospitals without a current price transparency file face CMS warning notices, corrective action plans and daily civil penalties.
- What to do when it's broken: Update and repost the complete machine-readable standard charges file now.
- Example reading used in demos: 200 days

### 6. AIArmor (AI Platforms)

**1. Post-market drift monitoring** (Maximum 0.15, warns from 0.12; policy, a company can set its own limit)

- Asks: Current model drift score from monitoring after release
- Rule: EU AI Act Art. 15 (accuracy, robustness) and Art. 72 (post-market monitoring); threshold is your own policy
- What a miss costs: Unchecked drift in a high-risk AI system can lead to regulator orders to withdraw it from the market, fines and claims from people it harmed.
- What to do when it's broken: Pause the release and re-validate accuracy before redeploying.
- Example reading used in demos: 0.18

**2. Written consent for biometrics** (Must be in place, answered Yes or No)

- Asks: Before collecting face, voice, fingerprint or other biometric data from Illinois residents, is signed written consent on file?
- Rule: Illinois BIPA, 740 ILCS 14/15(a)-(b)
- What a miss costs: Collecting face, voice or fingerprint data in Illinois without written consent brings class actions with statutory damages per violation.
- What to do when it's broken: Stop collecting biometric data from that person until written consent is signed; publish a retention policy.
- Example reading used in demos: Yes

**3. Report data breach within 72 hours** (Maximum 72 h, warns from 48 h; counts hours since a date and time)

- Asks: Hours since becoming aware of a personal data breach not yet reported to the supervisory authority (the data protection regulator)
- Rule: GDPR Art. 33(1) (no later than 72 hours after becoming aware, unless the breach is unlikely to result in risk)
- What a miss costs: Late breach reports to the data protection authority are a common GDPR finding and bring fines on top of the breach costs.
- What to do when it's broken: Notify the supervisory authority now with what is known and send the rest in phases.
- Example reading used in demos: 60 h

**4. Answer data requests in a month** (Maximum 30 days, warns from 25 days; counts days since a date)

- Asks: Days since a person's request about their data (access, deletion, objection) was received without a reply
- Rule: GDPR Art. 12(3) (within one month; extendable by two months if the person is told); 30 days used here
- What a miss costs: Late or missing replies to access and deletion requests are among the most common GDPR complaints and lead to fines and orders.
- What to do when it's broken: Reply to the person today, or tell them of the extension and the reason if the request is complex.
- Example reading used in demos: 12 days

**5. DPIA before high-risk processing** (Must be in place, answered Yes or No)

- Asks: Was a data protection impact assessment completed before deploying AI that profiles, scores or monitors people?
- Rule: GDPR Art. 35(1) and 35(3)
- What a miss costs: Deploying AI that profiles or monitors people without a data protection impact assessment breaks GDPR and draws fines and stop orders.
- What to do when it's broken: Pause the deployment until the impact assessment is done and signed off by the data protection officer.
- Example reading used in demos: No

**6. Notify candidates of hiring AI** (Must be in place, answered Yes or No)

- Asks: Were NYC candidates told at least 10 business days before the automated hiring tool was used on them?
- Rule: NYC Admin. Code 20-871(b) (at least 10 business days before use); 6 RCNY 5-303
- What a miss costs: Using an automated hiring tool in NYC without advance candidate notice brings civil penalties for each violation.
- What to do when it's broken: Hold the tool for these candidates until 10 business days after notice is given.
- Example reading used in demos: Yes

**7. Data contract with each AI vendor** (Must be in place, answered Yes or No)

- Asks: Is a signed data processing agreement in place with every vendor that processes personal data for your AI system?
- Rule: GDPR Art. 28(3)
- What a miss costs: Sharing personal data with AI vendors or model hosts without a processor contract breaks GDPR and is a frequent audit finding.
- What to do when it's broken: Stop sending personal data to the vendor until a data processing agreement is signed.
- Example reading used in demos: Yes

**8. Annual bias audit for hiring AI** (Maximum 365 days, warns from 335 days; counts days since a date)

- Asks: Days since the last independent bias audit of the automated hiring tool
- Rule: NYC Admin. Code 20-871; 6 RCNY 5-300 et seq. (Local Law 144 of 2021)
- What a miss costs: Using an automated hiring tool in NYC without a current bias audit brings civil penalties for each day of use and each violation.
- What to do when it's broken: Stop using the tool for NYC candidates until a new independent bias audit is done and its summary is published.
- Example reading used in demos: 380 days

**9. Human review of automated decisions** (Must be in place, answered Yes or No)

- Asks: Can people who get a decision made only by automated means, with legal or similarly serious effects, ask for a human review and challenge it?
- Rule: GDPR Art. 22(3) (right to human intervention and to contest) and Art. 13(2)(f)
- What a miss costs: Solely automated decisions without safeguards break GDPR, bringing data protection fines, orders to stop processing and claims.
- What to do when it's broken: Route affected decisions to a human reviewer and tell people how to contest them before deciding more cases.
- Example reading used in demos: Yes

**10. No unproven AI marketing claims** (Must never happen, answered Yes or No)

- Asks: Do any marketing materials make claims about the AI's accuracy or abilities that you cannot back with testing evidence?
- Rule: FTC Act Section 5, 15 U.S.C. 45(a)
- What a miss costs: Unsupported claims about what an AI product can do are deceptive under the FTC Act, leading to FTC orders, redress and lawsuits.
- What to do when it's broken: Pull the unsupported claims from all marketing now and keep only claims backed by documented testing.
- Example reading used in demos: Yes

### 7. LibraryArmor (Libraries)

**1. CIPA internet filter active** (Must be in place, answered Yes or No)

- Asks: Is an internet filter (technology protection measure) active on every public computer and on public Wi-Fi?
- Rule: CIPA, 47 U.S.C. 254(h)(6); 47 CFR 54.520; 20 U.S.C. 9134(f) (LSTA)
- What a miss costs: Libraries without a working filter lose E-rate and LSTA internet funding and may have to repay funds already received.
- What to do when it's broken: Turn the filter back on for all public devices and Wi-Fi before patrons use them again.
- Example reading used in demos: Yes

**2. Internet safety policy adopted** (Must be in place, answered Yes or No)

- Asks: Has the board adopted an internet safety policy after public notice and at least one public hearing or meeting?
- Rule: CIPA, 47 U.S.C. 254(h)(6) and 254(l); 47 CFR 54.520
- What a miss costs: Without an internet safety policy adopted after public notice and a hearing, the library cannot certify CIPA and loses E-rate discounts.
- What to do when it's broken: Give public notice, hold a hearing and adopt the policy before certifying CIPA on the next E-rate form.
- Example reading used in demos: Yes

**3. Wait 28 days after Form 470** (Minimum 28 days, warns from 30 days)

- Asks: Days between posting FCC Form 470 and signing the service contract
- Rule: 47 CFR 54.503(c)(4) (wait at least 28 days after FCC Form 470 is posted)
- What a miss costs: Signing a service contract before the bidding window closes breaks E-rate competitive bidding rules, and USAC denies or recovers the funding.
- What to do when it's broken: Do not sign the contract; wait until 28 full days after the Form 470 posting and evaluate all bids received.
- Example reading used in demos: 21 days

**4. Keep E-rate records 10 years** (Must be in place, answered Yes or No)

- Asks: Are all E-rate bidding, contract, invoice and CIPA records kept for at least 10 years after the funding year?
- Rule: 47 CFR 54.516(a) (10 years after the last day of service or the service delivery deadline)
- What a miss costs: Missing E-rate records during an audit lets USAC recover funding the library already received.
- What to do when it's broken: Stop any disposal of E-rate files and gather the missing records from vendors and USAC now.
- Example reading used in demos: Yes

**5. File E-rate invoice on time** (Maximum 120 days, warns from 90 days; counts days since a date)

- Asks: Days since the last day to receive service, with the E-rate invoice (BEAR or SPI) not yet filed
- Rule: 47 CFR 54.514(a) (120 days after the last day to receive service, or later notice date)
- What a miss costs: Missing the invoice deadline forfeits E-rate discounts the library was already approved for.
- What to do when it's broken: File the BEAR form or confirm the vendor filed its SPI invoice today; request an extension if still allowed.
- Example reading used in demos: 100 days

**6. Exits unlocked and clear** (Must never happen, answered Yes or No)

- Asks: Is any exit door, exit path or exit sign blocked, locked or not working during open hours?
- Rule: NFPA 101 Life Safety Code or IFC Chapter 10, as adopted by the local fire code; adoption varies
- What a miss costs: Blocked or locked exits are among the most common fire inspection citations and bring fines and orders to close until fixed.
- What to do when it's broken: Clear or unlock the exit now and check every exit before opening.
- Example reading used in demos: No

**7. Copyright notice on copiers** (Must be in place, answered Yes or No)

- Asks: Is a copyright warning notice posted on every public copier, scanner and printer?
- Rule: 17 U.S.C. 108(f)(1)
- What a miss costs: Without the notice the library can lose its protection and be held liable for infringing copies patrons make.
- What to do when it's broken: Post the copyright warning notice on each unsupervised copying device today.
- Example reading used in demos: No

**8. License for public film showings** (Must never happen, answered Yes or No)

- Asks: Are films shown at public library programs without a public performance license?
- Rule: 17 U.S.C. 106(4) and 501; statutory damages under 17 U.S.C. 504(c)
- What a miss costs: Showing films at public programs without a license is copyright infringement and can bring statutory damages and legal fees.
- What to do when it's broken: Cancel the showing until a public performance license covers the title.
- Example reading used in demos: No

**9. Patron records kept confidential** (Must never happen, answered Yes or No)

- Asks: Were any patron circulation or use records released without the consent, subpoena or court order your state law requires?
- Rule: State library-records confidentiality law varies (e.g., N.Y. CPLR 4509, Cal. Gov. Code 7927.105)
- What a miss costs: Releasing patron records without the legal process state law requires brings lawsuits, penalties and loss of public trust.
- What to do when it's broken: Stop further release, send all requests to the director and legal counsel, and document what was disclosed.
- Example reading used in demos: No

**10. Annual fire extinguisher service** (Maximum 365 days, warns from 335 days; policy, a company can set its own limit; counts days since a date)

- Asks: Days since the last annual fire extinguisher maintenance
- Rule: NFPA 10 (annual maintenance) as adopted by the local fire code; adoption varies
- What a miss costs: Out-of-date extinguishers are a common fire inspection citation and can bring fines and orders to close rooms until fixed.
- What to do when it's broken: Book a licensed extinguisher service now and tag every unit after maintenance.
- Example reading used in demos: 350 days

### 8. SchoolArmor (Schools)

**1. FERPA consent before disclosure** (Must be in place, answered Yes or No)

- Asks: Is every release of student records covered by written consent or an exception in 34 CFR 99.31?
- Rule: FERPA, 20 U.S.C. 1232g; 34 CFR 99.30 and 99.31
- What a miss costs: Improper release of student records can end federal education funding and brings complaints, corrective orders and lawsuits under state law.
- What to do when it's broken: Withhold the records until written consent is on file or a 99.31 exception is documented.
- Example reading used in demos: No

**2. Give parents records in 45 days** (Maximum 45 days, warns from 35 days; counts days since a date)

- Asks: Days since a parent or eligible student asked to see the student's records
- Rule: FERPA, 34 CFR 99.10(b) (no more than 45 days after the request)
- What a miss costs: Missing the access deadline is a FERPA violation that leads to Department of Education complaints and corrective orders.
- What to do when it's broken: Schedule the records review with the parent immediately.
- Example reading used in demos: 38 days

**3. IDEA evaluation within 60 days** (Maximum 60 days, warns from 50 days; counts days since a date)

- Asks: Days since parent consent for an initial special education evaluation
- Rule: IDEA, 34 CFR 300.301(c)(1) (60 days from consent, or the state's own timeframe)
- What a miss costs: Late special education evaluations lead to due process claims, compensatory services, attorney fee awards and state findings.
- What to do when it's broken: Finish the evaluation now and hold the eligibility meeting; tell the parent of the delay in writing.
- Example reading used in demos: 64 days

**4. Review each IEP every year** (Maximum 365 days, warns from 335 days; counts days since a date)

- Asks: Days since the student's last IEP team review
- Rule: IDEA, 34 CFR 300.324(b)(1)(i) (at least annually)
- What a miss costs: Expired IEPs deny required services, leading to due process claims, compensatory education and state monitoring findings.
- What to do when it's broken: Schedule the IEP meeting with the parent now and keep providing current services.
- Example reading used in demos: 340 days

**5. Title IX coordinator named** (Must be in place, answered Yes or No)

- Asks: Is a Title IX coordinator designated, with contact details published to students, parents and staff?
- Rule: Title IX, 34 CFR 106.8(a)-(b)
- What a miss costs: No designated coordinator or notice of nondiscrimination is a Title IX violation that risks federal funding and lawsuits.
- What to do when it's broken: Designate a coordinator and publish their contact details in the nondiscrimination notice today.
- Example reading used in demos: Yes

**6. IDEA reevaluation every 3 years** (Maximum 1,095 days, warns from 1,005 days; counts days since a date)

- Asks: Days since the student's last special education evaluation
- Rule: IDEA, 34 CFR 300.303(b)(2) (at least once every three years unless parent and school agree it is unnecessary)
- What a miss costs: Overdue reevaluations are a common state monitoring finding and lead to due process claims and compensatory services.
- What to do when it's broken: Get parent consent and start the reevaluation now, or document the agreement that it is not needed.
- Example reading used in demos: 1,020 days

**7. Staff background checks cleared** (Must be in place, answered Yes or No)

- Asks: Has every employee, volunteer and contractor with student contact cleared the background check your state requires?
- Rule: State law varies (fingerprint-based state and FBI checks are common)
- What a miss costs: Hiring staff without the required checks exposes the district to negligent hiring lawsuits and state licensing penalties.
- What to do when it's broken: Remove the person from student contact until the background check clears.
- Example reading used in demos: Yes

**8. Ed-tech apps vetted for privacy** (Must be in place, answered Yes or No)

- Asks: Does every ed-tech tool that collects student data have school approval and a signed agreement limiting data use to school purposes?
- Rule: COPPA, 16 CFR Part 312; FERPA, 34 CFR 99.31(a)(1)(i)(B)
- What a miss costs: Apps that collect student data without proper authorization and limits bring FTC and state privacy actions and FERPA problems.
- What to do when it's broken: Stop student use of unapproved tools until the vendor signs a data agreement.
- Example reading used in demos: No

**9. AHERA asbestos reinspection** (Maximum 1,095 days, warns from 1,005 days; counts days since a date)

- Asks: Days since the last asbestos reinspection by an accredited AHERA inspector
- Rule: AHERA, 40 CFR 763.85(b) (reinspection at least once every three years)
- What a miss costs: Missed asbestos reinspections are a frequent EPA citation and bring civil penalties plus costly cleanup if materials are disturbed.
- What to do when it's broken: Hire an accredited inspector to reinspect now and update the management plan.
- Example reading used in demos: 1,050 days

**10. Two food safety inspections** (Must be in place, answered Yes or No)

- Asks: Has each school kitchen had two state or local food safety inspections this school year?
- Rule: 42 U.S.C. 1758(h); 7 CFR 210.13(b) (two inspections each school year)
- What a miss costs: Missing required inspections is a USDA review finding that can lead to corrective action and withheld meal reimbursements.
- What to do when it's broken: Request the missing inspection from the local health department and post the latest report.
- Example reading used in demos: Yes

### 9. PropArmor (Real Estate)

**1. Deposits in a separate account** (Must be in place, answered Yes or No)

- Asks: Are all tenant security deposits held in a separate trust or escrow account?
- Rule: State trust-account and security-deposit law varies (e.g., N.Y. Gen. Oblig. Law 7-103, Fla. Stat. 83.49)
- What a miss costs: Mixing tenant deposits with operating cash can forfeit the right to keep any deposit and brings damages, penalties and license action.
- What to do when it's broken: Move tenant deposits to the separate trust or escrow account now.
- Example reading used in demos: No

**2. Return deposit on time** (Maximum 21 days, warns from 17 days; policy, a company can set its own limit; counts days since a date)

- Asks: Days since move-out without returning the deposit or an itemized list of deductions
- Rule: State law varies (e.g., Cal. Civ. Code 1950.5(g): 21 days); set the limit to your state's deadline
- What a miss costs: Late deposit returns or missing itemized statements can forfeit deductions and bring statutory penalties and attorney fees.
- What to do when it's broken: Send the deposit balance and an itemized statement of deductions today.
- Example reading used in demos: 10 days

**3. Lead paint disclosure before lease** (Must be in place, answered Yes or No)

- Asks: For pre-1978 units, are the lead disclosure form and EPA lead pamphlet given and signed before the tenant is bound by the lease?
- Rule: 42 U.S.C. 4852d; 24 CFR 35.88-35.92; 40 CFR 745.107 and 745.113(b)
- What a miss costs: Missing lead disclosures for pre-1978 housing bring EPA and HUD civil penalties and damages lawsuits from tenants.
- What to do when it's broken: Do not sign or renew the lease until the tenant receives and signs the lead disclosure and pamphlet.
- Example reading used in demos: Yes

**4. Certified firm for paint work** (Must be in place, answered Yes or No)

- Asks: Is repair work that disturbs paint in pre-1978 units done by an EPA-certified firm using lead-safe practices?
- Rule: EPA Renovation, Repair and Painting Rule, 40 CFR 745.81, 745.85 and 745.89
- What a miss costs: Paint-disturbing work in pre-1978 housing by uncertified crews is a common EPA violation bringing civil penalties per violation.
- What to do when it's broken: Stop the work until an EPA-certified firm and renovator take over with lead-safe practices.
- Example reading used in demos: No

**5. No discriminatory ads** (Must never happen, answered Yes or No)

- Asks: Do any listings or ads state a preference or limit based on race, color, religion, sex, disability, familial status or national origin?
- Rule: Fair Housing Act, 42 U.S.C. 3604(c); 24 CFR 100.75
- What a miss costs: Ads showing a preference based on a protected class break the Fair Housing Act, bringing HUD charges, DOJ suits and damages.
- What to do when it's broken: Take down the listing and rewrite it to describe the unit, not the tenant.
- Example reading used in demos: No

**6. Answer accommodation requests** (Must be in place, answered Yes or No)

- Asks: Is every accommodation request, including for assistance animals, reviewed and answered without charging pet fees or deposits?
- Rule: Fair Housing Act, 42 U.S.C. 3604(f)(3)(B); 24 CFR 100.204
- What a miss costs: Denying or ignoring disability accommodation requests, including assistance animals, is a top source of fair housing complaints and damages.
- What to do when it's broken: Review the pending request now, refund any pet fee charged for an assistance animal and reply in writing.
- Example reading used in demos: No

**7. Adverse action notice to applicant** (Must be in place, answered Yes or No)

- Asks: Does every applicant denied or charged more because of a screening report get an adverse action notice?
- Rule: FCRA, 15 U.S.C. 1681m(a)
- What a miss costs: Denying an applicant based on a screening report without the required notice brings FCRA lawsuits, damages and CFPB or FTC action.
- What to do when it's broken: Send the adverse action notice with the screening company's details and dispute rights today.
- Example reading used in demos: Yes

**8. Security deposit within legal cap** (Maximum 1 months; policy, a company can set its own limit)

- Asks: Security deposit charged, as months of rent
- Rule: State law varies (e.g., Cal. Civ. Code 1950.5(c), N.Y. Gen. Oblig. Law 7-108(1-a)(a): one month); set to your state's cap
- What a miss costs: Charging more than the state deposit cap brings refunds, statutory penalties and tenant lawsuits.
- What to do when it's broken: Refund the amount over the cap to the tenant now and fix the lease template.
- Example reading used in demos: 1.5 months

**9. Working smoke and CO alarms** (Must be in place, answered Yes or No)

- Asks: Does every unit have working smoke alarms, and carbon monoxide alarms where fuel-burning appliances or attached garages exist?
- Rule: State law and locally adopted fire code vary (e.g., IFC Sections 907.2.11 and 915)
- What a miss costs: Missing or dead alarms are a common code citation and expose the owner to fines and injury or death lawsuits after a fire.
- What to do when it's broken: Install or replace the missing alarms today and test each one.
- Example reading used in demos: Yes

**10. No lockouts or utility shutoffs** (Must never happen, answered Yes or No)

- Asks: Has any tenant been locked out, had utilities shut off or had belongings removed without a court order?
- Rule: State landlord-tenant law varies (e.g., Cal. Civ. Code 789.3, Fla. Stat. 83.67)
- What a miss costs: Evicting without a court order through lockouts or shutoffs brings statutory damages, penalties and tenant lawsuits.
- What to do when it's broken: Restore access and utilities immediately and use the court eviction process instead.
- Example reading used in demos: No

### 10. AutoArmor (Dealerships)

**1. Buyers Guide on every used car** (Must be in place, answered Yes or No)

- Asks: Is a completed Buyers Guide posted on every used vehicle offered for sale?
- Rule: FTC Used Car Rule, 16 CFR 455.2
- What a miss costs: Missing Buyers Guides are a top FTC Used Car Rule citation and bring civil penalties per vehicle.
- What to do when it's broken: Hold the vehicle from sale and post a completed Buyers Guide before showing it.
- Example reading used in demos: No

**2. Multi-factor login for customer data** (Must be in place, answered Yes or No)

- Asks: Is multi-factor authentication required for everyone who accesses customer information systems?
- Rule: FTC Safeguards Rule, 16 CFR 314.4(c)(5)
- What a miss costs: Weak access controls on customer data break the FTC Safeguards Rule and invite FTC orders, breach costs and lawsuits.
- What to do when it's broken: Turn on multi-factor authentication for all DMS, CRM and email accounts before further access.
- Example reading used in demos: No

**3. Notify FTC of data breach** (Maximum 30 days, warns from 20 days; counts days since a date)

- Asks: Days since discovering a breach affecting 500 or more customers that is not yet reported to the FTC
- Rule: FTC Safeguards Rule, 16 CFR 314.4(j) (no later than 30 days after discovery)
- What a miss costs: Failing to report a breach of 500 or more customers breaks the Safeguards Rule and raises FTC enforcement risk.
- What to do when it's broken: File the notification through the FTC's online form today.
- Example reading used in demos: 24 days

**4. Identity theft program in place** (Must be in place, answered Yes or No)

- Asks: Does the dealership have a written, board-approved Identity Theft Prevention Program that staff follow on credit deals?
- Rule: FTC Red Flags Rule, 16 CFR 681.1(d)
- What a miss costs: Dealers that arrange financing without a written identity theft program break the Red Flags Rule and risk FTC penalties and fraud losses.
- What to do when it's broken: Adopt a written Red Flags program and train F&I staff before taking more credit applications.
- Example reading used in demos: Yes

**5. Odometer disclosure on transfer** (Must be in place, answered Yes or No)

- Asks: Is a signed odometer disclosure statement completed for every vehicle sale or transfer that isn't exempt?
- Rule: 49 U.S.C. 32705; 49 CFR 580.5 (see 580.17 for exempt vehicles)
- What a miss costs: Missing or false odometer statements bring federal civil penalties and damages suits from buyers.
- What to do when it's broken: Hold the title transfer until the odometer disclosure is completed and signed.
- Example reading used in demos: Yes

**6. File Form 8300 for cash over $10,000** (Maximum 15 days, warns from 10 days; counts days since a date)

- Asks: Days since receiving more than $10,000 in cash in one sale or related sales, with Form 8300 not yet filed
- Rule: 26 U.S.C. 6050I; 26 CFR 1.6050I-1 (file within 15 days of receiving more than $10,000 in cash)
- What a miss costs: Late or missing Form 8300 filings bring IRS penalties, and intentional disregard carries much larger penalties.
- What to do when it's broken: File Form 8300 today and send the buyer the required written statement by January 31.
- Example reading used in demos: 16 days

**7. Complete terms in credit ads** (Must never happen, answered Yes or No)

- Asks: Does any credit ad state a payment, down payment or number of payments without also stating the APR and repayment terms?
- Rule: TILA, Regulation Z, 12 CFR 1026.24(d)
- What a miss costs: Ads that give a payment or down payment without the APR and terms break Truth in Lending and bring CFPB, FTC and state action.
- What to do when it's broken: Pull the ad and add the down payment, repayment terms and APR before it runs again.
- Example reading used in demos: Yes

**8. TILA disclosures before signing** (Must be in place, answered Yes or No)

- Asks: Does every credit buyer get written APR, finance charge, amount financed and total of payments disclosures before signing?
- Rule: TILA, Regulation Z, 12 CFR 1026.17(b) and 1026.18
- What a miss costs: Missing or wrong credit disclosures bring TILA lawsuits, statutory damages, attorney fees and regulator action.
- What to do when it's broken: Stop the deal and give the buyer the correct TILA disclosures before they sign.
- Example reading used in demos: Yes

**9. No new car sold with open recall** (Must never happen, answered Yes or No)

- Asks: Is any new vehicle with an open safety recall being sold or delivered before the recall repair is done?
- Rule: 49 U.S.C. 30120(i)
- What a miss costs: Selling a new vehicle with an unrepaired safety recall breaks federal law, bringing NHTSA civil penalties and injury lawsuits.
- What to do when it's broken: Hold delivery until the recall repair is completed and documented.
- Example reading used in demos: No

**10. Annual penetration test** (Maximum 365 days, warns from 335 days; counts days since a date)

- Asks: Days since the last penetration test of customer information systems
- Rule: FTC Safeguards Rule, 16 CFR 314.4(d)(2)(i) (annual); 314.6 exempts institutions with under 5,000 consumers
- What a miss costs: Skipping required security testing breaks the FTC Safeguards Rule and leaves customer data open to costly breaches.
- What to do when it's broken: Book a qualified penetration test now and track fixes for every finding.
- Example reading used in demos: 400 days

### 11. LuxuryArmor (Luxury Brands)

**1. CITES permit for exotic materials** (Must be in place, answered Yes or No)

- Asks: If this shipment contains a CITES-listed species (such as crocodile, python, ostrich or coral), are the CITES permits and Form 3-177 on file? (Yes if none.)
- Rule: CITES; 50 CFR Parts 14 and 23 (CITES permits plus USFWS Form 3-177 declaration)
- What a miss costs: Wildlife inspectors seize shipments of listed-species goods without permits, and the goods can be forfeited with civil or criminal penalties.
- What to do when it's broken: Hold the shipment; do not import, export or sell it until valid CITES permits and the USFWS declaration are on file.
- Example reading used in demos: No

**2. Lacey Act plant declaration** (Must be in place, answered Yes or No)

- Asks: For imported goods with covered plant material (such as wood cases, handles or paper), was a Lacey Act declaration filed and legal harvest documented?
- Rule: Lacey Act, 16 U.S.C. 3372(a) and 3372(f) (plant product import declaration)
- What a miss costs: Goods made with illegally sourced wood or plants can be seized and forfeited even if the importer did not know, plus civil and criminal penalties.
- What to do when it's broken: Stop entry of the goods; file the plant declaration (PPQ 505 or electronic) and gather proof of species and country of harvest.
- Example reading used in demos: Yes

**3. Country-of-origin marking** (Must be in place, answered Yes or No)

- Asks: Is every imported article (or its container, where allowed) legibly and permanently marked in English with its country of origin?
- Rule: 19 U.S.C. 1304; 19 CFR Part 134
- What a miss costs: CBP holds unmarked imports until they are marked or exported and can assess additional marking duties and penalties.
- What to do when it's broken: Hold the goods; mark each article with its country of origin under CBP supervision before release or sale.
- Example reading used in demos: No

**4. Gold and silver quality marks** (Must never happen, answered Yes or No)

- Asks: Is any piece marked or described with a higher gold karat or silver fineness than assay testing shows?
- Rule: FTC Jewelry Guides, 16 CFR Part 23 (gold and silver sections); National Gold and Silver Stamping Act, 15 U.S.C. 291-300
- What a miss costs: Overstated karat or silver marks bring FTC deceptive-practice actions, Stamping Act penalties, refunds and consumer class actions.
- What to do when it's broken: Pull the pieces from sale; correct the stamps and descriptions to the tested fineness and review supplier assays.
- Example reading used in demos: No

**5. Lab-grown and treated stone disclosure** (Must be in place, answered Yes or No)

- Asks: Is every laboratory-grown or treated stone clearly and prominently disclosed as such in tags, listings and invoices?
- Rule: FTC Jewelry Guides, 16 CFR Part 23 (e.g. 23.12 on diamonds and the laboratory-created stone and treatment sections)
- What a miss costs: Selling lab-grown or treated stones as natural brings FTC actions, refunds, lost trade accounts and fraud claims.
- What to do when it's broken: Stop selling the item; add a clear lab-grown or treatment disclosure to tags, listings and invoices before relisting.
- Example reading used in demos: Yes

**6. Fur product labeling** (Must be in place, answered Yes or No)

- Asks: Does every fur or fur-trimmed product carry a label with the animal name, country of origin and any dyeing or other processing?
- Rule: Fur Products Labeling Act, 15 U.S.C. 69-69k; 16 CFR Part 301
- What a miss costs: Mislabeled or unlabeled fur brings FTC enforcement, civil penalties and retailer chargebacks or recalls from sale.
- What to do when it's broken: Pull unlabeled fur items from sale; attach compliant labels and fix any matching ads or invoices.
- Example reading used in demos: Yes

**7. AML program for dealers** (Must be in place, answered Yes or No)

- Asks: If you are a covered dealer, do you have a written anti-money-laundering (AML) program with a compliance officer, risk-based procedures, training and independent testing?
- Rule: Bank Secrecy Act; 31 CFR 1027.210 (dealers in precious metals, precious stones or jewels)
- What a miss costs: FinCEN civil money penalties apply to covered dealers that lack an AML program, and gaps invite criminal money-laundering exposure.
- What to do when it's broken: Adopt a written AML program now: name a compliance officer, set risk-based procedures, train staff and schedule independent testing.
- Example reading used in demos: No

**8. Form 8300 cash report filing** (Maximum 15 days, warns from 10 days; counts days since a date)

- Asks: Days since receiving over $10,000 in cash (in one sale or related sales) with Form 8300 not yet filed
- Rule: 26 U.S.C. 6050I; 31 U.S.C. 5331; 31 CFR 1010.330 (file within 15 days)
- What a miss costs: Late or missing Form 8300 filings bring IRS civil penalties per return, higher penalties for intentional disregard, and possible criminal charges.
- What to do when it's broken: File Form 8300 with the IRS/FinCEN today and send the buyer the required written notice by January 31.
- Example reading used in demos: 12 days

**9. California Prop 65 warning** (Must be in place, answered Yes or No)

- Asks: For products sold in California that expose buyers to a listed chemical (such as lead or DEHP) above safe-harbor levels, is a clear Prop 65 warning given?
- Rule: Cal. Health & Safety Code 25249.6; 27 CCR 25600 et seq. (businesses with 10 or more employees)
- What a miss costs: Private enforcers send 60-day notices and sue for civil penalties, attorney fees and forced relabeling of products sold in California.
- What to do when it's broken: Stop California sales of the product until a compliant Prop 65 warning is on the product, shelf or web listing.
- Example reading used in demos: Yes

**10. Forced labor supply-chain tracing** (Must be in place, answered Yes or No)

- Asks: Is supply-chain tracing on file showing no input (such as cotton, leather, gold or polysilicon) came from Xinjiang or a UFLPA Entity List supplier?
- Rule: Uyghur Forced Labor Prevention Act, Pub. L. 117-78; 19 U.S.C. 1307
- What a miss costs: CBP detains and excludes goods tied to Xinjiang or listed entities, stranding inventory and missing selling seasons.
- What to do when it's broken: Hold the shipment; assemble tracing documents back to raw materials and replace any Xinjiang or listed-entity source.
- Example reading used in demos: No

### 12. AgriArmor (Agriculture)

**1. Pesticide pre-harvest interval** (Must be in place, answered Yes or No)

- Asks: Has the full waiting time before harvest on the pesticide label (pre-harvest interval) passed since this crop was last treated?
- Rule: FIFRA 12(a)(2)(G), 7 U.S.C. 136j - use must follow the label, including its pre-harvest interval
- What a miss costs: Residues over tolerance lead to rejected loads, crop destruction, buyer delistings and FIFRA misuse penalties.
- What to do when it's broken: Do not harvest; wait until the label PHI has fully passed since the last application.
- Example reading used in demos: No

**2. Restricted-entry interval** (Must never happen, answered Yes or No)

- Asks: Did any worker enter a treated area during the label's no-entry period (restricted-entry interval) without an allowed early-entry exception and protective equipment (PPE)?
- Rule: EPA Worker Protection Standard, 40 CFR 170.405 and 170.407; FIFRA 12(a)(2)(G)
- What a miss costs: Worker poisonings bring WPS penalties, medical and workers' compensation costs, and lawsuits.
- What to do when it's broken: Remove workers from the treated area now, post or tell the REI, and provide decontamination and medical help if exposed.
- Example reading used in demos: No

**3. WPS pesticide safety training** (Maximum 365 days, warns from 335 days; counts days since a date)

- Asks: Days since this worker's or handler's last WPS pesticide safety training
- Rule: EPA Worker Protection Standard, 40 CFR 170.401 (workers) and 170.501 (handlers) - every 12 months
- What a miss costs: Untrained workers and handlers bring WPS violations counted per worker and higher risk of poisoning claims.
- What to do when it's broken: Keep this person out of treated areas and handling tasks until retrained, and record the training.
- Example reading used in demos: 350 days

**4. Restricted-use pesticide record** (Maximum 14 days, warns from 10 days; counts days since a date)

- Asks: Days since a restricted-use pesticide application that still has no application record
- Rule: 7 U.S.C. 136i-1; 7 CFR Part 110 (record within 14 days, keep 2 years; some states stricter)
- What a miss costs: Missing application records bring USDA and state civil penalties and weaken the farm's defense in drift or residue claims.
- What to do when it's broken: Write the application record now (product, EPA reg. no., amount, site, date, applicator) and file it for 2 years.
- Example reading used in demos: 20 days

**5. Certified applicator for RUPs** (Must be in place, answered Yes or No)

- Asks: Is every restricted-use pesticide applied by, or under the direct supervision of, a currently certified applicator?
- Rule: FIFRA 3(d), 7 U.S.C. 136a(d); 40 CFR Part 171
- What a miss costs: Applying restricted-use pesticides without certification brings FIFRA penalties, loss of dealer access and liability for any harm.
- What to do when it's broken: Stop the application; use a currently certified applicator or one supervising directly before continuing.
- Example reading used in demos: Yes

**6. Harvest and post-harvest water** (Maximum 0 CFU/100 mL)

- Asks: Generic E. coli found in water used for washing produce, contact surfaces or handwashing
- Rule: FSMA Produce Safety Rule, 21 CFR 112.44(a) - no detectable generic E. coli in 100 mL
- What a miss costs: Contaminated wash water can cause outbreaks, recalls, FDA warning letters and loss of buyer contracts.
- What to do when it's broken: Stop using this water for produce contact or handwashing; switch to a safe source or treat it and retest.
- Example reading used in demos: 0 CFU/100 mL

**7. Field toilets and handwashing** (Maximum 20 workers, warns from 18 workers)

- Asks: Field hand laborers per toilet and handwashing facility (within a quarter-mile walk)
- Rule: OSHA 29 CFR 1928.110(c)(2) - one toilet and handwashing facility per 20 workers (farms with 11+ hand laborers)
- What a miss costs: Missing field sanitation brings OSHA citations, worker illness and food-safety failures that buyers audit for.
- What to do when it's broken: Bring in more toilets and handwashing stations today so each serves 20 or fewer workers within a quarter-mile walk.
- Example reading used in demos: 22 workers

**8. H-2A required wage rate** (Must be in place, answered Yes or No)

- Asks: Are H-2A workers and workers in corresponding employment paid at least the highest of the adverse effect wage rate (AEWR), prevailing wage, agreed rate, or federal or state minimum wage?
- Rule: 20 CFR 655.120(a) and 655.122(l); 29 CFR Part 501
- What a miss costs: Underpaying H-2A or corresponding workers brings DOL back wages, civil money penalties and debarment from the H-2A program.
- What to do when it's broken: Raise pay to the highest required rate now and pay back wages owed for all hours already worked.
- Example reading used in demos: Yes

**9. Pesticide decontamination supplies** (Must be in place, answered Yes or No)

- Asks: Are water, soap and single-use towels in place within a quarter mile of workers in treated areas (plus eye-flush and clean clothes for handlers)?
- Rule: EPA Worker Protection Standard, 40 CFR 170.411 (workers) and 170.509 (handlers)
- What a miss costs: Missing wash water, soap and towels near treated areas bring WPS violations and worsen worker poisonings and injury claims.
- What to do when it's broken: Set out decontamination water, soap, towels and eye-flush supplies before workers or handlers continue.
- Example reading used in demos: Yes

**10. Farm labor contractor registration** (Must be in place, answered Yes or No)

- Asks: Have you checked that every farm labor contractor you use holds a valid DOL certificate covering the work they do for you?
- Rule: Migrant and Seasonal Agricultural Worker Protection Act, 29 U.S.C. 1842; 29 CFR Part 500
- What a miss costs: Using an unregistered labor contractor brings MSPA civil money penalties and joint liability for the crew's wages and housing.
- What to do when it's broken: Verify the contractor's DOL certificate before the crew works again; stop using any unregistered contractor.
- Example reading used in demos: No

### 13. CopArmor (Police Compliance)

**1. Evidence room inspection** (Maximum 183 days, warns from 153 days; policy, a company can set its own limit; counts days since a date)

- Asks: Days since the last property and evidence room inspection
- Rule: CALEA Standard 84.1.6 - semiannual property/evidence inspections (accredited agencies) or agency policy
- What a miss costs: Lost or tampered evidence breaks chain of custody, gets cases dismissed and can cost CALEA accreditation.
- What to do when it's broken: Inspect the evidence room now and reconcile records before releasing more evidence to court.
- Example reading used in demos: 160 days

**2. CJIS security awareness training** (Maximum 365 days, warns from 335 days; policy, a company can set its own limit; counts days since a date)

- Asks: Days since this person's last CJIS security awareness training
- Rule: FBI CJIS Security Policy, awareness and training (AT) controls - before access and annually (FBI policy, applied through state CSA agreements)
- What a miss costs: Failed CJIS audits can suspend the agency's access to NCIC and state criminal history systems.
- What to do when it's broken: Suspend this person's CJI access until they complete CJIS security awareness training.
- Example reading used in demos: 300 days

**3. Multi-factor login for CJI** (Must be in place, answered Yes or No)

- Asks: Is multi-factor authentication required for every login that can reach criminal justice information?
- Rule: FBI CJIS Security Policy, identification and authentication (IA) controls - multi-factor authentication
- What a miss costs: Weak authentication fails CJIS audits, risks losing NCIC access and exposes the agency to breach costs.
- What to do when it's broken: Turn on multi-factor authentication for all CJI systems, or block access from accounts and devices without it.
- Example reading used in demos: No

**4. Body-worn camera retention** (Must be in place, answered Yes or No; policy)

- Asks: Is body-worn camera footage kept for your state's required period, with longer holds for use of force, arrests, complaints and lawsuits?
- Rule: State law varies (state body-worn camera and records retention laws); agency retention policy
- What a miss costs: Deleted or missing footage leads to lost cases, adverse-inference rulings, public-records suits and settlements.
- What to do when it's broken: Place a hold on all footage at risk of deletion and fix retention settings to match state law and open cases.
- Example reading used in demos: Yes

**5. Use-of-force reporting and review** (Must be in place, answered Yes or No)

- Asks: Is every reportable use of force documented and reviewed by a supervisor as state law and agency policy require?
- Rule: State law and agency policy; CALEA standards, Chapter 4 (use of force reporting and review)
- What a miss costs: Unreported or unreviewed force drives civil rights verdicts, pattern-or-practice investigations and loss of state grants.
- What to do when it's broken: Get the officer's written report and a supervisor review completed now, and submit any report state law requires.
- Example reading used in demos: Yes

**6. Compensatory time 480-hour cap** (Maximum 480 h, warns from 440 h)

- Asks: Hours of comp time (compensatory time off) this officer has banked
- Rule: FLSA 7(o)(3)(A), 29 U.S.C. 207(o)(3)(A); 29 CFR 553.24 - 480 hours for law enforcement
- What a miss costs: Comp time banked over the cap must be paid as overtime, with FLSA back pay, equal liquidated damages and attorney fees.
- What to do when it's broken: Pay cash overtime for further overtime hours instead of adding comp time until the balance drops below 480.
- Example reading used in demos: 455 h

**7. Probable cause review within 48 hours** (Maximum 48 h, warns from 36 h; counts hours since a date and time)

- Asks: Hours since an arrest without a warrant, with no judge's probable cause finding yet
- Rule: County of Riverside v. McLaughlin, 500 U.S. 44 (1991); Gerstein v. Pugh, 420 U.S. 103 (1975); state rules may be shorter
- What a miss costs: Holding a warrantless arrestee past 48 hours without a judicial probable cause finding brings civil rights suits and release orders.
- What to do when it's broken: Get the arrestee before a judge for a probable cause determination now, or release them.
- Example reading used in demos: 20 h

**8. Firearms qualification** (Maximum 365 days, warns from 335 days; policy, a company can set its own limit; counts days since a date)

- Asks: Days since this officer last passed firearms qualification with the duty weapon
- Rule: State POST standards vary; annual qualification is common policy; City of Canton v. Harris, 489 U.S. 378 (1989)
- What a miss costs: Officers carrying without current qualification expose the agency to failure-to-train liability and breach state POST rules.
- What to do when it's broken: Remove the officer from armed duty until they pass firearms qualification with the duty weapon.
- Example reading used in demos: 400 days

**9. Police overtime (7(k) period)** (Maximum 171 h, warns from 160 h)

- Asks: Hours an officer has worked at straight-time pay in the current 28-day 7(k) work period
- Rule: FLSA 7(k), 29 U.S.C. 207(k); 29 CFR 553.230 - 171 hours per 28-day law enforcement work period
- What a miss costs: Unpaid overtime brings FLSA back pay, equal liquidated damages and attorney fees, often in group lawsuits.
- What to do when it's broken: Pay overtime (or allowed comp time) at time and a half for every hour over 171 in this 28-day period.
- Example reading used in demos: 165 h

**10. ADA communication with deaf people** (Must be in place, answered Yes or No)

- Asks: Are qualified interpreters or other communication aids provided to deaf or hard-of-hearing people in interviews, interrogations and arrests?
- Rule: ADA Title II, 42 U.S.C. 12132; 28 CFR 35.160 (effective communication)
- What a miss costs: Failing to provide interpreters brings DOJ settlements, damages suits and suppressed statements.
- What to do when it's broken: Get a qualified interpreter or other auxiliary aid before continuing the interview, and document it.
- Example reading used in demos: Yes

### 14. FireArmor (Fire Departments)

**1. SCBA inspected and charged** (Minimum 90%, warns from 92%)

- Asks: Air pack (SCBA) cylinder pressure as a percent of its rated full pressure at this shift's check
- Rule: OSHA 29 CFR 1910.134(h)(3) - SCBA checked before and after use and monthly; recharge below 90% of rated pressure
- What a miss costs: A low or unchecked SCBA can fail inside a fire, causing injury or death, OSHA citations and wrongful-death suits.
- What to do when it's broken: Take the SCBA out of service and recharge the cylinder before assigning it.
- Example reading used in demos: 88%

**2. Annual SCBA facepiece fit test** (Maximum 365 days, warns from 335 days; counts days since a date)

- Asks: Days since this firefighter's last SCBA facepiece fit test
- Rule: OSHA 29 CFR 1910.134(f)(2) - fit test before use and at least annually (public departments in OSHA State Plan states)
- What a miss costs: Untested facepieces let smoke in, leading to OSHA citations (in State Plan states) and exposure-related claims.
- What to do when it's broken: Keep the firefighter off respirator duty until fit tested with the facepiece model and size they use.
- Example reading used in demos: 200 days

**3. Annual firefighter medical exam** (Maximum 365 days, warns from 335 days; policy, a company can set its own limit; counts days since a date)

- Asks: Days since this firefighter's last occupational medical evaluation
- Rule: NFPA 1582 standard or its successor (annual medical evaluation); OSHA 29 CFR 1910.134(e) medical clearance for respirator use
- What a miss costs: Missed medicals raise line-of-duty cardiac risk, respirator-standard citations and costly workers' compensation claims.
- What to do when it's broken: Restrict the firefighter from fireground and respirator duty until the medical evaluation is done and cleared.
- Example reading used in demos: 340 days

**4. Turnout gear 10-year retirement** (Maximum 10 years, warns from 9 years; policy, a company can set its own limit)

- Asks: Years since this turnout gear was manufactured
- Rule: NFPA 1851 standard or its successor NFPA 1850 - retire structural ensembles 10 years after manufacture
- What a miss costs: Over-age gear may not protect against heat and flame, creating burn injury claims and failed audits or grant reviews.
- What to do when it's broken: Retire this gear from firefighting use now and issue a compliant replacement set.
- Example reading used in demos: 11 years

**5. Turnout gear advanced cleaning** (Maximum 365 days, warns from 335 days; policy, a company can set its own limit; counts days since a date)

- Asks: Days since this turnout gear's last advanced inspection and advanced cleaning
- Rule: NFPA 1851 standard or its successor NFPA 1850 - advanced inspection and advanced cleaning at least every 12 months
- What a miss costs: Contaminated or damaged gear raises cancer-exposure and burn risk and fails NFPA-based audits.
- What to do when it's broken: Pull the gear for advanced cleaning and inspection and issue a spare set meanwhile.
- Example reading used in demos: 150 days

**6. Annual fire hose service test** (Maximum 365 days, warns from 335 days; policy, a company can set its own limit; counts days since a date)

- Asks: Days since this hose length's last service test
- Rule: NFPA 1962 standard or its successor NFPA 1910 - in-service hose tested at least annually
- What a miss costs: A hose that bursts on the fireground endangers crews and property and weakens the department's liability defense.
- What to do when it's broken: Take the hose out of service until it passes a service pressure test.
- Example reading used in demos: 380 days

**7. Annual ground ladder test** (Maximum 365 days, warns from 335 days; policy, a company can set its own limit; counts days since a date)

- Asks: Days since this ground ladder's last service test
- Rule: NFPA 1932 standard or its successor NFPA 1910 - ground ladders service tested at least annually
- What a miss costs: Ladder failures cause falls, serious injury claims and OSHA or insurer findings.
- What to do when it's broken: Remove the ladder from the apparatus until it passes its service test.
- Example reading used in demos: 350 days

**8. Annual fire pump service test** (Maximum 365 days, warns from 335 days; policy, a company can set its own limit; counts days since a date)

- Asks: Days since this apparatus's last fire pump service test
- Rule: NFPA 1911 standard or its successor NFPA 1910 - apparatus fire pump service tested at least annually
- What a miss costs: A pump that fails to deliver rated flow can lose structures and lives and lower ISO ratings and insurance outcomes.
- What to do when it's broken: Schedule the pump service test now and put the apparatus in reserve if it cannot pass.
- Example reading used in demos: 100 days

**9. Two-in, two-out entry** (Must never happen, answered Yes or No)

- Asks: Did any crew go inside a burning structure, into air immediately dangerous to life or health (IDLH), without two properly equipped firefighters standing by outside?
- Rule: OSHA 29 CFR 1910.134(g)(4) - two in, two out for interior structural firefighting (known-rescue exception)
- What a miss costs: Entering without a standby team leaves no rescue option, causing line-of-duty deaths, OSHA citations and lawsuits.
- What to do when it's broken: Hold interior entry until two equipped firefighters are outside, and review the incident with the crews.
- Example reading used in demos: No

**10. Hepatitis B vaccine offered** (Maximum 10 working days, warns from 8 working days; counts business days since a date)

- Asks: Working days since this responder was assigned exposure duties without being offered the hepatitis B vaccine
- Rule: OSHA 29 CFR 1910.1030(f)(2) - offer within 10 working days of assignment (public departments in OSHA State Plan states)
- What a miss costs: Unvaccinated responders face infection risk, OSHA bloodborne pathogens citations and workers' compensation claims.
- What to do when it's broken: Offer the hepatitis B vaccine series at no cost now, or get a signed declination.
- Example reading used in demos: 3 working days

### 15. ParkArmor (Amusement Parks)

**1. Daily pre-opening ride inspection** (Must be in place, answered Yes or No)

- Asks: Has today's pre-opening inspection been completed and signed off for this ride?
- Rule: ASTM F770 - daily pre-opening inspection by the owner/operator; state ride laws adopt or add to it
- What a miss costs: Opening an uninspected ride risks rider injury, state shutdown orders and negligence lawsuits.
- What to do when it's broken: Keep the ride closed until today's pre-opening inspection is completed and signed.
- Example reading used in demos: Yes

**2. State ride permit current** (Minimum 0 days, warns from 30 days; policy, a company can set its own limit; counts days until a date)

- Asks: Days until this ride's state permit or inspection certificate expires (negative if expired)
- Rule: State amusement ride laws vary (permits and periodic state or third-party inspections)
- What a miss costs: Operating without a current state permit or inspection brings shutdown orders, fines and weaker insurance and legal defense.
- What to do when it's broken: Close the ride until the state inspection is passed and the permit is current and posted.
- Example reading used in demos: -5 days

**3. Ride incident reporting** (Must be in place, answered Yes or No; policy)

- Asks: Was every ride incident with serious injury reported to the state agency within its deadline, with the ride held as required?
- Rule: State amusement ride laws vary (reporting deadlines for serious injuries; ride held for inspection)
- What a miss costs: Late or missing incident reports bring state fines and shutdowns and undercut the park's position in injury lawsuits.
- What to do when it's broken: Report the incident to the state agency now and keep the ride closed and unaltered until it is released.
- Example reading used in demos: Yes

**4. Ride operator training** (Must be in place, answered Yes or No; policy)

- Asks: Has every operator completed and documented training for the specific ride they run, including its rider restrictions?
- Rule: ASTM F770 (operator training and training records); state ride laws
- What a miss costs: Untrained operators cause rider injuries and negligence verdicts, and training gaps are cited in state inspections.
- What to do when it's broken: Remove the operator from the ride until ride-specific training is completed and recorded.
- Example reading used in demos: Yes

**5. Lifeguard certification current** (Minimum 0 days, warns from 30 days; policy, a company can set its own limit; counts days until a date)

- Asks: Days until this lifeguard's certification expires (negative if already expired)
- Rule: State pool and bathing codes vary; CDC Model Aquatic Health Code (lifeguard qualification)
- What a miss costs: An uncertified lifeguard on duty can void insurance, bring health-department closure and weaken drowning-lawsuit defense.
- What to do when it's broken: Take the lifeguard off the stand until recertified; replace them with a certified guard.
- Example reading used in demos: 12 days

**6. Pool free chlorine level** (Minimum 1 ppm, warns from 1.5 ppm; policy, a company can set its own limit)

- Asks: Free chlorine level at the latest pool test
- Rule: State pool codes vary; CDC Model Aquatic Health Code minimum 1.0 ppm free chlorine (higher with stabilizer and in spas)
- What a miss costs: Low chlorine spreads waterborne illness, leading to health-department closure, outbreak lawsuits and lost admissions.
- What to do when it's broken: Clear the pool, raise free chlorine to the required level and retest before reopening.
- Example reading used in demos: 0.6 ppm

**7. VGB-compliant drain covers** (Must be in place, answered Yes or No)

- Asks: Does every pool and spa drain have a cover that meets the Virginia Graeme Baker Act (VGB) standard and is within its rated service life, plus required anti-entrapment systems?
- Rule: Virginia Graeme Baker Pool and Spa Safety Act, 15 U.S.C. 8003; 16 CFR Part 1450
- What a miss costs: Drain entrapment causes catastrophic injuries or death, CPSC enforcement and large lawsuits.
- What to do when it's broken: Close the pool or spa until noncompliant or expired drain covers are replaced and anti-entrapment protection is in place.
- Example reading used in demos: Yes

**8. Pool pH upper limit** (Maximum 7.8 pH, warns from 7.7 pH; policy, a company can set its own limit)

- Asks: pH at the latest pool water test
- Rule: State pool codes vary; CDC Model Aquatic Health Code pH range 7.2 to 7.8
- What a miss costs: High pH weakens chlorine, spreading waterborne illness and bringing health-department closures and lost admissions.
- What to do when it's broken: Adjust pH into range and retest before letting swimmers back in.
- Example reading used in demos: 7.5 pH

**9. Teen work hours (14-15)** (Maximum 18 h, warns from 16 h)

- Asks: Hours a 14- or 15-year-old employee worked this school week
- Rule: FLSA child labor rules, 29 CFR 570.35(a) - 18 hours in a school week for 14- and 15-year-olds
- What a miss costs: Child labor violations bring DOL civil money penalties per minor and bad publicity with families.
- What to do when it's broken: Take the minor off the schedule for the rest of the week and fix scheduling to FLSA hour limits.
- Example reading used in demos: 14 h

**10. Lockout/tagout for ride maintenance** (Must be in place, answered Yes or No)

- Asks: Are written lockout/tagout procedures used every time workers service or maintain ride machinery that could start or move?
- Rule: OSHA 29 CFR 1910.147 (control of hazardous energy)
- What a miss costs: Unexpected startup during maintenance causes amputations and deaths, OSHA citations and workers' compensation costs.
- What to do when it's broken: Stop the maintenance work; lock out all energy sources under written procedures before anyone resumes.
- Example reading used in demos: Yes

### 16. JailArmor (Prison Compliance)

**1. Restrictive housing welfare checks** (Maximum 30 min, warns from 24 min; policy, a company can set its own limit; counts minutes since a date and time)

- Asks: Minutes since the last welfare check of the person in restrictive housing (segregation)
- Rule: Corrections standards (e.g., ACA): checks at least every 30 minutes at irregular times; common policy, set to yours
- What a miss costs: Missed checks are central to in-custody death lawsuits and settlements, and can cost a facility its accreditation.
- What to do when it's broken: Check the cell now and log the time; use 15-minute or constant watch for anyone at risk of suicide.
- Example reading used in demos: 34 min

**2. PREA intake risk screening** (Maximum 72 h, warns from 60 h; counts hours since a date and time)

- Asks: Hours since the inmate arrived, still without a screening for risk of sexual victimization or abusiveness
- Rule: 28 CFR 115.41(a)-(b)
- What a miss costs: Unscreened housing assignments lead to sexual abuse, civil rights suits and failed PREA audits.
- What to do when it's broken: Complete the PREA risk screening now and review the housing assignment against the result.
- Example reading used in demos: 48 h

**3. PREA audit every three years** (Maximum 36 months, warns from 32 months)

- Asks: Months since the facility's last completed PREA audit
- Rule: 28 CFR 115.93; 28 CFR 115.401(a)-(b); 34 U.S.C. 30307(e)
- What a miss costs: States that cannot certify PREA compliance lose part of certain DOJ grant funds, and a lapsed audit weakens the defense in abuse suits.
- What to do when it's broken: Schedule a DOJ-certified PREA auditor now so the audit is completed within the current three-year cycle.
- Example reading used in demos: 33 months

**4. Annual staffing plan review** (Maximum 12 months, warns from 11 months)

- Asks: Months since the staffing and video monitoring plan was last assessed and documented
- Rule: 28 CFR 115.13(a), (d)
- What a miss costs: Documented understaffing is cited in consent decrees and abuse lawsuits against jails and prisons.
- What to do when it's broken: Assess the staffing plan now, document needed adjustments, and record any deviations from it.
- Example reading used in demos: 9 months

**5. Suicide risk screening at intake** (Must be in place, answered Yes or No)

- Asks: Was every person booked today screened for suicide risk by trained staff?
- Rule: Eighth and Fourteenth Amendments (deliberate indifference); Farmer v. Brennan, 511 U.S. 825 (1994); NCCHC and ACA standards
- What a miss costs: Suicides after missed screening bring deliberate indifference lawsuits, large settlements and federal oversight.
- What to do when it's broken: Screen the person now; place anyone who screens positive on observation and refer to mental health.
- Example reading used in demos: Yes

**6. Health requests reviewed in 24 hours** (Maximum 24 h, warns from 20 h; policy, a company can set its own limit; counts hours since a date and time)

- Asks: Hours since the oldest unreviewed health care request was submitted
- Rule: NCCHC standards (nonemergency requests reviewed within 24 hours; common policy); Estelle v. Gamble, 429 U.S. 97 (1976)
- What a miss costs: Delayed or denied medical care is a leading source of Eighth Amendment lawsuits and court-ordered monitoring.
- What to do when it's broken: Have qualified health staff triage all pending requests now and see urgent cases immediately.
- Example reading used in demos: 30 h

**7. PREA staff refresher training** (Maximum 24 months, warns from 22 months)

- Asks: Months since the staff member last completed PREA refresher training
- Rule: 28 CFR 115.31(a), (c) (refresher training every two years; refresher information in other years)
- What a miss costs: Training gaps are common PREA audit findings, can fail the audit and weaken the defense in sexual abuse lawsuits.
- What to do when it's broken: Schedule the staff member for PREA training now and keep the signed acknowledgment on file.
- Example reading used in demos: 26 months

**8. Interpreters for deaf inmates** (Must be in place, answered Yes or No)

- Asks: Was a qualified interpreter or other effective aid provided to deaf or hard of hearing inmates at every medical or disciplinary encounter?
- Rule: 28 CFR 35.160; 28 CFR 35.152; 42 U.S.C. 12132
- What a miss costs: Denying interpreters at medical, disciplinary and classification encounters is a common basis for ADA suits and DOJ settlements.
- What to do when it's broken: Postpone the encounter until a qualified interpreter (on-site or video) is provided, and log the request.
- Example reading used in demos: No

**9. Fire alarm system testing** (Maximum 365 days, warns from 330 days; policy, a company can set its own limit; counts days since a date)

- Asks: Days since the fire alarm and smoke detection system was last inspected and tested
- Rule: NFPA 72 annual inspection and testing; NFPA 101 Ch. 22-23; as adopted by state or local fire code (policy)
- What a miss costs: Failed fire inspections can force housing units closed, and fire deaths in locked units bring major liability.
- What to do when it's broken: Schedule a qualified inspection and test of the fire alarm system now and post a fire watch if any part is down.
- Example reading used in demos: 300 days

**10. Grievance response deadline** (Maximum 30 days, warns from 25 days; policy, a company can set its own limit; counts days since a date)

- Asks: Days since the oldest open inmate grievance was filed without a written response
- Rule: Facility grievance policy sets the deadline (common policy: 30 days); PLRA 42 U.S.C. 1997e(a); Ross v. Blake, 578 U.S. 632 (2016)
- What a miss costs: Unanswered grievances can make remedies unavailable under the PLRA, letting inmate lawsuits go forward.
- What to do when it's broken: Issue a written response to the grievance now and log the date it was delivered to the inmate.
- Example reading used in demos: 12 days

### 17. InsureArmor (Insurance)

**1. TCPA consent for marketing calls** (Must be in place, answered Yes or No)

- Asks: For autodialed or prerecorded marketing calls or texts, is prior express written consent on file?
- Rule: 47 U.S.C. 227(b)-(c); 47 CFR 64.1200(a)(2)-(3), (c)(1)-(2)
- What a miss costs: Each unlawful call or text carries statutory damages, and TCPA class actions against insurers and lead buyers settle for large sums.
- What to do when it's broken: Do not dial; get prior express written consent first and scrub the number against the Do Not Call Registry.
- Example reading used in demos: No

**2. Producer licensed and CE current** (Must be in place, answered Yes or No)

- Asks: Is every agent (producer) selling to this customer licensed in the customer's state for this line of insurance, with continuing education (CE) complete?
- Rule: State insurance producer licensing laws based on the NAIC Producer Licensing Model Act; state CE rules for renewal
- What a miss costs: Unlicensed sales bring state fines, license revocation and commission forfeiture, and can void coverage placed.
- What to do when it's broken: Stop the producer from selling in that state or line until the license is active and CE hours are complete.
- Example reading used in demos: Yes

**3. Claim acknowledged on time** (Maximum 15 days, warns from 12 days; policy, a company can set its own limit; counts days since a date)

- Asks: Days since notice of a claim was received, not yet acknowledged
- Rule: State unfair claims practices laws vary; NAIC model regulation and e.g. Cal. Code Regs. tit. 10, 2695.5(e) use 15 days
- What a miss costs: Late claim handling is a top finding in market conduct exams, leading to fines and bad-faith lawsuits.
- What to do when it's broken: Acknowledge the claim in writing now, tell the claimant what is needed, and begin the investigation.
- Example reading used in demos: 13 days

**4. Claim accepted or denied on time** (Maximum 40 days, warns from 32 days; policy, a company can set its own limit; counts days since a date)

- Asks: Days since proof of claim was received without accepting or denying the claim
- Rule: State law varies (e.g., 40 days after proof of claim, Cal. Code Regs. tit. 10, 2695.7(b)); set to your state
- What a miss costs: Slow claim decisions draw regulator fines, interest penalties and bad-faith verdicts that can exceed policy limits.
- What to do when it's broken: Accept or deny the claim in writing now; if more time is needed, give written notice of what is needed and why.
- Example reading used in demos: 45 days

**5. Cybersecurity event notice** (Maximum 72 h, warns from 48 h; policy, a company can set its own limit; counts hours since a date and time)

- Asks: Hours since the company decided a reportable cybersecurity event happened
- Rule: NAIC Insurance Data Security Model Law (#668) Sec. 6 as adopted by states; 23 NYCRR 500.17(a); state versions vary
- What a miss costs: Late notice of a data breach to the insurance regulator brings penalties, consent orders and costly remediation plans.
- What to do when it's broken: Notify the insurance commissioner now with the facts known, and update the notice as more is learned.
- Example reading used in demos: 20 h

**6. Multi-factor authentication** (Must be in place, answered Yes or No)

- Asks: Is multi-factor authentication required for all remote access and all access to systems holding customer data?
- Rule: 23 NYCRR 500.12 (NYDFS licensees); NAIC Insurance Data Security Model Law (#668) Sec. 4 as adopted by states
- What a miss costs: Missing MFA is a frequently cited failings in NYDFS cybersecurity consent orders and a common path to costly breaches.
- What to do when it's broken: Turn on multi-factor authentication for the account or system now, or disable remote access until it is on.
- Example reading used in demos: Yes

**7. Privacy notice to customers** (Must be in place, answered Yes or No)

- Asks: Was a privacy notice given to the customer when the customer relationship began?
- Rule: 15 U.S.C. 6803(a), 6805(a)(6); state insurance privacy rules based on NAIC Model Regulation #672
- What a miss costs: Missing privacy notices are cited in market conduct exams and lead to fines and required corrective mailings.
- What to do when it's broken: Deliver the privacy notice now, including opt-out rights, before sharing information with nonaffiliated parties.
- Example reading used in demos: Yes

**8. HIPAA breach notice to members** (Maximum 60 days, warns from 45 days; counts days since a date)

- Asks: Days since a breach of unsecured protected health information was discovered without notifying members
- Rule: 45 CFR 164.404(b)
- What a miss costs: Late breach notices bring HHS OCR civil money penalties, resolution agreements and class action lawsuits.
- What to do when it's broken: Send breach notices to affected individuals now, and notify HHS and media as 45 CFR 164.406-164.408 require.
- Example reading used in demos: 64 days

**9. OFAC sanctions screening** (Must be in place, answered Yes or No)

- Asks: Were the policyholder, insureds and claim payees checked against the OFAC sanctions list (SDN list)?
- Rule: 31 CFR Chapter V (OFAC regulations); blocked property reports, 31 CFR 501.603
- What a miss costs: OFAC penalties apply on a strict liability basis to policies issued or claims paid to sanctioned parties.
- What to do when it's broken: Hold the policy or payment and screen all parties now; block and report any confirmed match to OFAC.
- Example reading used in demos: Yes

**10. SAR filing for covered products** (Maximum 30 days, warns from 25 days; counts days since a date)

- Asks: Days since suspicious activity on a covered life or annuity product was first detected
- Rule: 31 CFR 1025.320(b)(3)
- What a miss costs: Late or missing SARs bring FinCEN civil money penalties and AML consent orders for life insurers.
- What to do when it's broken: File the SAR with FinCEN now and keep the supporting records for five years.
- Example reading used in demos: 27 days

### 18. BankArmor (Banking Compliance)

**1. Currency Transaction Report** (Maximum $10,000, warns from $9,000)

- Asks: Customer's total cash in or out today, all transactions added together
- Rule: 31 CFR 1010.311, 1010.313 (aggregation); filed within 15 days, 31 CFR 1010.306(a)(1); structuring, 31 U.S.C. 5324
- What a miss costs: Missed CTRs and ignored structuring bring FinCEN and bank regulator penalties and BSA consent orders.
- What to do when it's broken: File a FinCEN CTR within 15 calendar days; the transaction may proceed. Review recent activity for structuring.
- Example reading used in demos: $9,600

**2. SAR filed within 30 days** (Maximum 30 days, warns from 25 days; counts days since a date)

- Asks: Days since suspicious activity was first detected without a suspicious activity report (SAR) filed
- Rule: 31 CFR 1020.320(b)(3) (30 days; up to 60 if no suspect is identified)
- What a miss costs: Late or missing SARs are frequently cited BSA failures, leading to civil money penalties and consent orders.
- What to do when it's broken: File the SAR with FinCEN now; call law enforcement first if the activity needs immediate attention.
- Example reading used in demos: 34 days

**3. Customer identification (CIP)** (Must be in place, answered Yes or No)

- Asks: Were name, date of birth, address and ID number collected before the account was opened?
- Rule: 31 CFR 1020.220(a)(2)
- What a miss costs: CIP gaps are cited in BSA exams and lead to penalties, consent orders and limits on opening new accounts.
- What to do when it's broken: Restrict the account until the missing identity information is collected and verified.
- Example reading used in demos: Yes

**4. Beneficial owners identified** (Must be in place, answered Yes or No)

- Asks: For a business customer (legal entity), were its beneficial owners identified and verified when the account was opened?
- Rule: 31 CFR 1010.230(a)-(b)
- What a miss costs: Missing beneficial ownership records are a frequent BSA exam finding behind penalties and consent orders.
- What to do when it's broken: Collect the beneficial ownership certification and verify each owner's identity before further activity.
- Example reading used in demos: No

**5. OFAC sanctions screening** (Must be in place, answered Yes or No)

- Asks: Were all parties to the account or payment checked against the OFAC sanctions list (SDN list)?
- Rule: 31 CFR Chapter V (OFAC regulations); blocked property reports, 31 CFR 501.603
- What a miss costs: OFAC penalties apply on a strict liability basis to payments for sanctioned parties and can be very large.
- What to do when it's broken: Hold the transaction and screen all parties now; block and report any confirmed match to OFAC.
- Example reading used in demos: Yes

**6. Reg E error investigation** (Maximum 10 business days, warns from 8 business days; counts business days since a date)

- Asks: Business days since the customer reported an electronic transfer (EFT) error, with no decision or provisional credit yet
- Rule: 12 CFR 1005.11(c)(1)-(2)
- What a miss costs: Mishandled EFT disputes bring CFPB and regulator enforcement, required restitution and class actions.
- What to do when it's broken: Finish the investigation or give provisional credit now, and tell the customer the result in writing.
- Example reading used in demos: 7 business days

**7. Closing Disclosure 3 days early** (Minimum 3 business days, warns from 3 business days)

- Asks: Business days before the loan was signed (consummation) that the borrower received the Closing Disclosure
- Rule: 12 CFR 1026.19(f)(1)(ii)(A)
- What a miss costs: Late Closing Disclosures force closing delays, and TRID errors lead to restitution and TILA liability.
- What to do when it's broken: Reschedule consummation so the borrower has the Closing Disclosure at least 3 business days beforehand.
- Example reading used in demos: 2 business days

**8. Adverse action notice in 30 days** (Maximum 30 days, warns from 25 days; counts days since a date)

- Asks: Days since a completed credit application was received without a decision notice
- Rule: 12 CFR 1002.9(a)(1)(i)
- What a miss costs: Missing or late adverse action notices are common fair lending findings behind restitution and CFPB orders.
- What to do when it's broken: Send the decision now; if denied, give specific reasons or the right to request them, plus the ECOA notice.
- Example reading used in demos: 18 days

**9. Flood insurance at loan closing** (Must be in place, answered Yes or No)

- Asks: For a building in a special flood hazard area, is flood insurance in place at or before loan closing?
- Rule: 42 U.S.C. 4012a(b), (f); 12 CFR 339.3 (FDIC), 12 CFR 22.3 (OCC), 12 CFR 208.25 (Fed), 12 CFR 760.3 (NCUA)
- What a miss costs: Flood insurance violations carry mandatory civil money penalties per violation and are regularly cited in exams.
- What to do when it's broken: Do not close, extend or renew the loan until required flood insurance is in place.
- Example reading used in demos: Yes

**10. Billing error acknowledged in 30 days** (Maximum 30 days, warns from 25 days; counts days since a date)

- Asks: Days since a credit card billing error notice was received without a written acknowledgment or resolution
- Rule: 12 CFR 1026.13(c)(1) (resolve within two billing cycles, no later than 90 days, under 1026.13(c)(2))
- What a miss costs: Mishandled credit card billing disputes lead to CFPB enforcement, customer restitution and forfeited disputed amounts.
- What to do when it's broken: Send the written acknowledgment now and do not collect the disputed amount until the error is resolved.
- Example reading used in demos: 12 days

### 19. FintechArmor (Finance Compliance)

**1. Form ADV annual amendment** (Maximum 90 days, warns from 75 days; counts days since a date)

- Asks: Days since the adviser's fiscal year ended, with the annual Form ADV amendment not yet filed
- Rule: 17 CFR 275.204-1(a)(1) (within 90 days of fiscal year-end)
- What a miss costs: Late Form ADV filings draw SEC or state deficiency findings and fines, and a long lapse can end registration.
- What to do when it's broken: File the annual updating amendment on IARD now and deliver the brochure or summary of changes to clients.
- Example reading used in demos: 82 days

**2. Net performance in advertising** (Must never happen, answered Yes or No)

- Asks: Does any advertisement show gross performance without net performance shown with at least equal prominence?
- Rule: 17 CFR 275.206(4)-1(d)(1)
- What a miss costs: Marketing Rule violations are an SEC enforcement priority and lead to settled orders and civil penalties.
- What to do when it's broken: Pull the advertisement and reissue it with net performance for the same periods, shown as prominently.
- Example reading used in demos: Yes

**3. Private fund audit delivery** (Maximum 120 days, warns from 100 days; counts days since a date)

- Asks: Days since the private fund's fiscal year ended, with audited financial statements not yet delivered to investors
- Rule: 17 CFR 275.206(4)-2(b)(4) (120 days; 180 days for funds of funds)
- What a miss costs: Late fund audits break the custody rule, a frequent SEC exam finding that leads to settled orders and penalties.
- What to do when it's broken: Press the auditor to finish now and deliver the audited financials; report any delay on Form ADV as required.
- Example reading used in demos: 95 days

**4. Reg S-P customer breach notice** (Maximum 30 days, warns from 24 days; counts days since a date)

- Asks: Days since learning sensitive customer information was, or likely was, accessed without authorization
- Rule: 17 CFR 248.30(a)(4) (Reg S-P as amended in 2024)
- What a miss costs: Late breach notices bring SEC enforcement, customer lawsuits and loss of client trust and assets.
- What to do when it's broken: Send notices to affected customers now, as required by the incident response program.
- Example reading used in demos: 10 days

**5. Business texts captured and kept** (Must never happen, answered Yes or No)

- Asks: Do staff use personal texting or messaging apps for business that the firm does not capture and retain?
- Rule: 17 CFR 240.17a-4(b)(4) (broker-dealers); 17 CFR 275.204-2(a)(7) (advisers)
- What a miss costs: Unrecorded texting on personal devices has led to large SEC and CFTC recordkeeping penalties against firms.
- What to do when it's broken: Stop off-channel business messaging, move staff to an archived tool, and collect the messages that were missed.
- Example reading used in demos: Yes

**6. Form CRS delivered to retail clients** (Must be in place, answered Yes or No)

- Asks: Was Form CRS delivered to the retail investor before or at the first recommendation, order, account opening or advisory contract?
- Rule: 17 CFR 240.17a-14(c) (broker-dealers); 17 CFR 275.204-5(b) (advisers)
- What a miss costs: Missed Form CRS delivery is a common SEC and FINRA exam finding that leads to fines and required remediation.
- What to do when it's broken: Deliver the current Form CRS now and record the delivery date before taking further action on the account.
- Example reading used in demos: Yes

**7. Adverse action notice in 30 days** (Maximum 30 days, warns from 25 days; counts days since a date)

- Asks: Days since a completed credit application was received without a decision notice
- Rule: 12 CFR 1002.9(a)(1)(i)
- What a miss costs: Missing or late adverse action notices from fintech lenders lead to CFPB orders, restitution and penalties.
- What to do when it's broken: Send the decision now; if denied, give the specific principal reasons, not just model outputs.
- Example reading used in demos: 31 days

**8. Money transmitter licenses** (Must be in place, answered Yes or No)

- Asks: Is the company licensed, or exempt, as a money transmitter in every state where it serves customers?
- Rule: State money transmitter laws; 18 U.S.C. 1960; FinCEN MSB registration, 31 CFR 1022.380
- What a miss costs: Unlicensed money transmission brings state cease-and-desist orders and fines, and criminal exposure under federal law.
- What to do when it's broken: Stop onboarding customers in the unlicensed state until a license is obtained or an exemption is confirmed.
- Example reading used in demos: Yes

**9. SAR filed within 30 days** (Maximum 30 days, warns from 25 days; counts days since a date)

- Asks: Days since suspicious activity was first detected without a suspicious activity report (SAR) filed
- Rule: 31 CFR 1023.320(b)(3) (broker-dealers); 31 CFR 1022.320(b)(3) (money services businesses)
- What a miss costs: Late or missing SARs bring FinCEN, SEC and FINRA penalties and AML consent orders.
- What to do when it's broken: File the SAR with FinCEN now and keep the supporting documentation for five years.
- Example reading used in demos: 14 days

**10. Broker-dealer net capital** (Minimum 100%, warns from 120%)

- Asks: Net capital as a percent of the firm's required minimum
- Rule: 17 CFR 240.15c3-1; notice to regulators, 17 CFR 240.17a-11 (early warning at 120% of the minimum)
- What a miss costs: A broker-dealer below its net capital minimum must stop doing business, and violations bring SEC and FINRA fines.
- What to do when it's broken: Stop business that uses capital, notify the SEC and FINRA the same day, and add capital before resuming.
- Example reading used in demos: 115%

### 20. PetroArmor (Oil & Gas Production)

**1. Transmission valve inspection** (Maximum 15 months, warns from 13 months)

- Asks: Months since the transmission valve was last inspected and partially operated
- Rule: 49 CFR 192.745(a) (at least once each calendar year, not over 15 months apart)
- What a miss costs: Missed valve inspections are common PHMSA findings that lead to civil penalties and orders to fix or shut in lines.
- What to do when it's broken: Inspect and partially operate the valve now; if it does not work, fix it or designate an alternative valve.
- Example reading used in demos: 16 months

**2. Methane leak repair deadline** (Maximum 30 days, warns from 24 days; counts days since a date)

- Asks: Days since a gas leak (fugitive emissions) was found without a repair attempt
- Rule: 40 CFR 60.5397a(h) (OOOOa); 40 CFR 60.5397b(h) (OOOOb): first repair attempt within 30 days of detection
- What a miss costs: LDAR failures are a frequent EPA Clean Air Act case, leading to civil penalties and consent decrees.
- What to do when it's broken: Attempt the repair now, resurvey to confirm it holds, and record the repair and resurvey dates.
- Example reading used in demos: 12 days

**3. SPCC plan five-year review** (Maximum 60 months, warns from 54 months)

- Asks: Months since the oil spill prevention (SPCC) plan was last reviewed and evaluated
- Rule: 40 CFR 112.5(b)
- What a miss costs: Out-of-date SPCC plans are routine EPA inspection findings with civil penalties, and worsen spill liability.
- What to do when it's broken: Complete and document the SPCC plan review now, and amend the plan if technology or the facility has changed.
- Example reading used in demos: 58 months

**4. Process hazard analysis update** (Maximum 60 months, warns from 54 months)

- Asks: Months since the process hazard analysis was last updated and revalidated
- Rule: 29 CFR 1910.119(e)(6)
- What a miss costs: Out-of-date hazard analyses are frequently cited PSM items, bringing OSHA penalties and raising explosion risk.
- What to do when it's broken: Assemble a qualified team and update and revalidate the process hazard analysis now.
- Example reading used in demos: 40 months

**5. Hydrogen sulfide exposure** (Maximum 20 ppm, warns from 10 ppm)

- Asks: Highest hydrogen sulfide (H2S) level measured in the air the worker breathes
- Rule: 29 CFR 1910.1000 Table Z-2 (ceiling 20 ppm; 50 ppm peak up to 10 minutes once per shift if no other exposure)
- What a miss costs: H2S overexposure can kill workers within minutes, leading to OSHA citations, shutdowns and wrongful death suits.
- What to do when it's broken: Move workers upwind out of the area now; re-enter only with supplied-air respirators after the source is found.
- Example reading used in demos: 25 ppm

**6. Pipeline incident phone report** (Maximum 1 h, warns from 0.75 h; counts hours since a date and time)

- Asks: Hours since a reportable pipeline incident was confirmed without calling the National Response Center
- Rule: 49 CFR 191.5(a) (gas); 49 CFR 195.52(a) (hazardous liquid): no later than one hour after confirmed discovery
- What a miss costs: Late incident reports to the National Response Center draw PHMSA civil penalties and heavier scrutiny after an accident.
- What to do when it's broken: Call the National Response Center at 1-800-424-8802 now, then file the written report on time.
- Example reading used in demos: 0.5 h

**7. Operator qualification for tasks** (Must be in place, answered Yes or No)

- Asks: Is every person doing covered pipeline tasks today qualified under the written operator qualification (OQ) program?
- Rule: 49 CFR 192.805 (gas); 49 CFR 195.505 (hazardous liquid)
- What a miss costs: Unqualified workers on covered tasks are common PHMSA findings that lead to civil penalties and raise accident risk.
- What to do when it's broken: Stop the task until a qualified person performs it or directly observes and directs the unqualified worker.
- Example reading used in demos: No

**8. Offshore SEMS audit** (Maximum 36 months, warns from 32 months)

- Asks: Months since the last independent audit of the offshore facility's safety and environmental management system (SEMS)
- Rule: 30 CFR 250.1920(a)
- What a miss costs: Missed SEMS audits bring BSEE incidents of noncompliance, civil penalties and possible shut-in of operations.
- What to do when it's broken: Engage an accredited audit service provider now and submit the audit report to BSEE on time.
- Example reading used in demos: 30 months

**9. Cathodic protection annual survey** (Maximum 15 months, warns from 13 months)

- Asks: Months since cathodic protection test readings were last taken on the pipeline
- Rule: 49 CFR 192.465(a) (gas); 49 CFR 195.573(a)(1) (hazardous liquid): each calendar year, not over 15 months apart
- What a miss costs: Missed corrosion control tests are frequent PHMSA findings that lead to civil penalties and raise the risk of leaks and ruptures.
- What to do when it's broken: Take the cathodic protection readings now and correct any deficiency found.
- Example reading used in demos: 11 months

**10. Oil spill reported immediately** (Must be in place, answered Yes or No)

- Asks: Was every oil discharge that caused a sheen on water reported to the National Response Center immediately?
- Rule: 33 U.S.C. 1321(b)(5); 40 CFR 110.3, 110.6
- What a miss costs: Failing to report an oil discharge brings Clean Water Act civil and criminal penalties on top of cleanup costs.
- What to do when it's broken: Call the National Response Center at 1-800-424-8802 now and start containment and cleanup.
- Example reading used in demos: Yes

### 21. FactoryArmor (Manufacturing)

**1. Lockout/tagout before servicing** (Must be in place, answered Yes or No)

- Asks: Has it been checked that the equipment's energy is shut off and locked out, and has every worker on the job put on a personal lock?
- Rule: 29 CFR 1910.147(d)(6) and (f)(3)
- What a miss costs: Lockout/tagout is frequently cited by OSHA; failures bring citations, amputation and death lawsuits, and line shutdowns.
- What to do when it's broken: Stop servicing; verify isolation and have every worker apply a personal lock first.
- Example reading used in demos: Yes

**2. Hazard communication training** (Must be in place, answered Yes or No)

- Asks: Has every worker exposed to hazardous chemicals been trained on them before starting that work?
- Rule: 29 CFR 1910.1200(h)(1)
- What a miss costs: Hazard communication is frequently cited by OSHA, and untrained workers lead to citations, chemical injuries and claims.
- What to do when it's broken: Keep untrained workers away from the chemicals and train them on labels, SDSs and hazards now.
- Example reading used in demos: No

**3. Machine guards in place** (Must never happen, answered Yes or No)

- Asks: Is any machine running with its point-of-operation guard removed or bypassed?
- Rule: 29 CFR 1910.212(a)(1) and (a)(3)(ii)
- What a miss costs: Missing guards are frequently cited by OSHA and cause amputations, bringing penalties, lawsuits and lost production.
- What to do when it's broken: Stop the machine and lock it out until the guard is reinstalled and working.
- Example reading used in demos: Yes

**4. Forklift operator evaluation** (Maximum 1,095 days, warns from 1,000 days; counts days since a date)

- Asks: Days since the operator's last forklift performance evaluation
- Rule: 29 CFR 1910.178(l)(4)(iii)
- What a miss costs: Powered industrial truck violations are frequently cited by OSHA, and forklift crashes cause serious injuries, claims and damage.
- What to do when it's broken: Remove the operator from forklift duty until a performance evaluation is completed.
- Example reading used in demos: 1,040 days

**5. Respirator fit test** (Maximum 365 days, warns from 330 days; counts days since a date)

- Asks: Days since the worker was last fit tested on the respirator they wear
- Rule: 29 CFR 1910.134(f)(2)
- What a miss costs: Respiratory protection is frequently cited by OSHA, and poorly fitted respirators expose workers to illness claims.
- What to do when it's broken: Keep the worker out of areas needing a respirator until a new fit test is passed.
- Example reading used in demos: 400 days

**6. Fall protection at 4 feet** (Must never happen, answered Yes or No)

- Asks: Is any worker exposed to an unprotected side or edge 4 feet or more above a lower level?
- Rule: 29 CFR 1910.28(b)(1)(i)
- What a miss costs: Walking-working surface violations are commonly cited by OSHA, and falls cause serious injuries, penalties and lawsuits.
- What to do when it's broken: Move the worker back and install guardrails, a safety net or personal fall protection before work resumes.
- Example reading used in demos: No

**7. Clear space at electrical panels** (Must never happen, answered Yes or No)

- Asks: Is the working space in front of any electrical panel or equipment blocked or used for storage?
- Rule: 29 CFR 1910.303(g)(1)
- What a miss costs: Electrical violations are frequently cited by OSHA, and blocked panels delay shutoff and worsen shock and arc injuries.
- What to do when it's broken: Clear the working space in front of the panel now and mark it to keep it clear.
- Example reading used in demos: No

**8. Noise exposure limit** (Maximum 90 dBA, warns from 85 dBA)

- Asks: Worker's noise exposure, as an 8-hour average (time-weighted average)
- Rule: 29 CFR 1910.95(b)(1) and (c)(1)
- What a miss costs: Noise violations bring OSHA citations, and hearing loss is a common and costly workers' compensation claim.
- What to do when it's broken: Use engineering or administrative controls, require hearing protection and enroll workers in hearing conservation.
- Example reading used in demos: 87 dBA

**9. Severe injury report to OSHA** (Maximum 24 h, warns from 12 h; counts hours since a date and time)

- Asks: Hours since learning of a work-related hospitalization, amputation or eye loss, without reporting it to OSHA
- Rule: 29 CFR 1904.39(a)(2)
- What a miss costs: Late or missing reports bring OSHA penalties and often trigger a full inspection of the plant.
- What to do when it's broken: Report to OSHA now by phone or online. A work-related death must be reported within 8 hours.
- Example reading used in demos: 30 h

**10. Record injury on OSHA 300 log** (Maximum 7 days, warns from 5 days; counts days since a date)

- Asks: Calendar days since learning of a recordable injury or illness, without entering it on the OSHA 300 log
- Rule: 29 CFR 1904.29(b)(3)
- What a miss costs: Late or missing 300 log entries are commonly cited by OSHA and can add recordkeeping penalties to any inspection.
- What to do when it's broken: Enter the case on the OSHA 300 log and complete the 301 incident report now.
- Example reading used in demos: 9 days

### 22. PharmaArmor (Pharmaceuticals)

**1. Part 11 electronic signatures** (Must be in place, answered Yes or No)

- Asks: Does every electronic signature show the signer's name, date/time and meaning, and use two separate ID parts (such as an ID code and a password)?
- Rule: 21 CFR 11.50 and 11.200(a)(1)
- What a miss costs: Part 11 and data integrity gaps are common in FDA warning letters and can hold up batch release and product approvals.
- What to do when it's broken: Do not release the record; fix the signature so name, date/time and meaning show and two ID components are used.
- Example reading used in demos: No

**2. OOS results investigated** (Must be in place, answered Yes or No)

- Asks: Has every out-of-specification result or unexplained discrepancy been fully investigated and documented before batch release?
- Rule: 21 CFR 211.192
- What a miss costs: Inadequate OOS investigations are frequently cited in FDA 483s and warning letters and can lead to recalls.
- What to do when it's broken: Hold the batch; complete and document the investigation, extend it to related batches, and record conclusions.
- Example reading used in demos: Yes

**3. Lab data audit trail** (Must never happen, answered Yes or No)

- Asks: Can any user delete or overwrite laboratory or production data without an audit trail record?
- Rule: 21 CFR 11.10(e); 21 CFR 211.68(b) and 211.194(a)
- What a miss costs: Deleted or altered data is a frequent basis for FDA warning letters, import alerts and consent decrees.
- What to do when it's broken: Lock down user rights, turn on audit trails, and review affected data before relying on it.
- Example reading used in demos: Yes

**4. Instrument calibration due** (Minimum 0 days, warns from 14 days; counts days until a date)

- Asks: Days until the instrument's next calibration due date under the written program (negative if overdue)
- Rule: 21 CFR 211.68(a) and 211.160(b)(4)
- What a miss costs: Overdue calibration is a common FDA 483 finding and can put every result from the instrument, and the batches they released, in doubt.
- What to do when it's broken: Tag the instrument out of use, calibrate it, and assess results produced since the due date.
- Example reading used in demos: 7 days

**5. Equipment cleaning procedures** (Must be in place, answered Yes or No)

- Asks: Are written equipment cleaning procedures in place, followed, and recorded for each cleaning?
- Rule: 21 CFR 211.67(b) and 211.182
- What a miss costs: Cleaning failures cause cross-contamination, recalls and FDA warning letters.
- What to do when it's broken: Quarantine product made on the equipment and clean it under a written, recorded procedure.
- Example reading used in demos: Yes

**6. Annual product quality review** (Maximum 365 days, warns from 330 days; counts days since a date)

- Asks: Days since the last annual review of each product's quality records
- Rule: 21 CFR 211.180(e)
- What a miss costs: Skipped annual reviews are a routine FDA 483 finding and let quality trends go unnoticed until they cause recalls.
- What to do when it's broken: Complete the review of batches, complaints, recalls and investigations and record any corrective actions.
- Example reading used in demos: 345 days

**7. DSCSA illegitimate product notice** (Maximum 24 h, warns from 18 h; counts hours since a date and time)

- Asks: Hours since deciding a product is illegitimate (such as counterfeit or stolen), without notifying FDA and affected trading partners
- Rule: 21 U.S.C. 360eee-1(b)(4)(B) (FD&C Act 582(b)(4)(B))
- What a miss costs: Late notice of illegitimate product violates DSCSA, can bring FDA enforcement, and lets harmful product reach patients.
- What to do when it's broken: Notify FDA (Form 3911) and affected trading partners now, and quarantine the product.
- Example reading used in demos: 10 h

**8. 15-day adverse event report** (Maximum 15 days, warns from 10 days; counts days since a date)

- Asks: Calendar days since receiving a serious and unexpected adverse drug experience, without a report to FDA
- Rule: 21 CFR 314.80(c)(1)(i)
- What a miss costs: Late safety reports draw FDA warning letters and raise product liability exposure.
- What to do when it's broken: Submit the 15-day alert report to FDA now and document the follow-up investigation.
- Example reading used in demos: 12 days

**9. Field alert report** (Maximum 3 working days, warns from 2 working days; counts business days since a date)

- Asks: Working days since learning of a quality problem in a product already shipped (such as contamination or a label mix-up), without a field alert
- Rule: 21 CFR 314.81(b)(1)
- What a miss costs: Late field alerts draw FDA enforcement and let defective drugs stay on the market, raising recall and liability costs.
- What to do when it's broken: File the field alert report with the FDA district office now, even if the investigation is still open.
- Example reading used in demos: 4 working days

**10. DEA biennial inventory** (Maximum 730 days, warns from 670 days; counts days since a date)

- Asks: Days since the last complete controlled substance inventory
- Rule: 21 CFR 1304.11(c)
- What a miss costs: Controlled substance recordkeeping failures bring DEA civil penalties and can cost the company its registration.
- What to do when it's broken: Take a complete inventory of all controlled substances now and keep the record for DEA inspection.
- Example reading used in demos: 500 days

### 23. MineArmor (Mining & Minerals)

**1. New miner training** (Minimum 4 h, warns from 23 h)

- Asks: Hours of new-miner training completed (4 h before starting work, 24 h within 90 days)
- Rule: 30 CFR 46.5
- What a miss costs: Untrained miners draw MSHA citations and withdrawal orders that remove them from work, and raise accident risk.
- What to do when it's broken: Keep the miner off the job until 4 hours of training are done; finish all 24 hours within 90 days.
- Example reading used in demos: 2 h

**2. Annual refresher training** (Maximum 365 days, warns from 330 days; counts days since a date)

- Asks: Days since the miner's last 8-hour annual refresher training
- Rule: 30 CFR 46.8 (Part 48 mines: 30 CFR 48.8 and 48.28)
- What a miss costs: Missed refresher training brings MSHA citations and orders to withdraw the miner from the mine.
- What to do when it's broken: Remove the miner from work until the 8-hour refresher training is completed.
- Example reading used in demos: 380 days

**3. Workplace exam each shift** (Must be in place, answered Yes or No)

- Asks: Was each working place examined for hazards by a competent person before work began this shift?
- Rule: 30 CFR 56.18002(a)
- What a miss costs: Missed workplace exams are frequently cited by MSHA and let hazards go unfixed until someone is hurt.
- What to do when it's broken: Stop work in the area until a competent person examines it and records the exam.
- Example reading used in demos: Yes

**4. Call MSHA within 15 minutes** (Maximum 15 min, warns from 10 min; counts minutes since a date and time)

- Asks: Minutes since a reportable accident was known, without calling MSHA
- Rule: 30 CFR 50.10
- What a miss costs: Late accident notice brings MSHA penalties, and disturbing the scene before MSHA arrives can lead to further enforcement.
- What to do when it's broken: Call MSHA now at its toll-free accident number and preserve the scene.
- Example reading used in demos: 8 min

**5. Monthly fire extinguisher check** (Maximum 31 days, warns from 25 days; counts days since a date)

- Asks: Days since the fire extinguisher's last monthly visual inspection
- Rule: 30 CFR 56.4201(a)(1)
- What a miss costs: Uninspected extinguishers are a common MSHA citation and may fail when a mobile equipment or plant fire starts.
- What to do when it's broken: Inspect the extinguisher now; replace or recharge it if it is not fully charged and operable.
- Example reading used in demos: 20 days

**6. Noise exposure limit** (Maximum 90 dBA, warns from 85 dBA)

- Asks: Miner's noise exposure, as an 8-hour average (time-weighted average)
- Rule: 30 CFR 62.130 (action level 30 CFR 62.120)
- What a miss costs: Noise overexposure brings MSHA citations, and hearing loss leads to compensation claims.
- What to do when it's broken: Use engineering and administrative controls, provide hearing protection and enroll the miner in hearing conservation.
- Example reading used in demos: 92 dBA

**7. Moving machine parts guarded** (Must never happen, answered Yes or No)

- Asks: Is any exposed moving machine part that could injure a person missing its guard?
- Rule: 30 CFR 56.14107(a)
- What a miss costs: Guarding is frequently cited by MSHA, and unguarded conveyors and pulleys cause amputations and deaths.
- What to do when it's broken: Stop and lock out the machine until the guard is installed.
- Example reading used in demos: No

**8. Mobile equipment pre-shift check** (Must be in place, answered Yes or No)

- Asks: Was every piece of self-propelled mobile equipment checked for safety defects before use this shift?
- Rule: 30 CFR 56.14100(a)
- What a miss costs: Skipped pre-shift checks are frequently cited by MSHA, and defective haul trucks and loaders cause fatal accidents.
- What to do when it's broken: Park the equipment until the operator completes the check and any safety defects are fixed.
- Example reading used in demos: No

**9. Loose ground scaled or supported** (Must never happen, answered Yes or No)

- Asks: Is anyone working or traveling where hazardous loose or unstable ground has not been taken down or supported?
- Rule: 30 CFR 56.3200
- What a miss costs: Ground falls cause serious injuries and deaths, bringing MSHA orders that close the area and penalties.
- What to do when it's broken: Clear people from the area and post it until the ground is scaled or supported.
- Example reading used in demos: No

**10. Electrical grounding test** (Maximum 365 days, warns from 330 days; counts days since a date)

- Asks: Days since grounding systems were tested for continuity and resistance
- Rule: 30 CFR 56.12028
- What a miss costs: Untested grounding brings MSHA citations and can lead to fatal electrocutions.
- What to do when it's broken: Test grounding continuity and resistance now and record the results.
- Example reading used in demos: 340 days

### 24. PortArmor (Port Authorities)

**1. TWIC for secure areas** (Must be in place, answered Yes or No)

- Asks: Does every person entering a secure area hold a valid TWIC card, or have an escort who holds one?
- Rule: 33 CFR 101.514; 33 CFR 105.255
- What a miss costs: Access control failures draw Coast Guard civil penalties and can lead to orders suspending facility operations.
- What to do when it's broken: Stop the person at the gate; allow entry only with a valid TWIC or an escort who holds one.
- Example reading used in demos: No

**2. Quarterly security drill** (Maximum 3 months, warns from 2.5 months)

- Asks: Months since the last facility security drill
- Rule: 33 CFR 105.220(b)
- What a miss costs: Missed drills are a common Coast Guard deficiency that can bring penalties and operating restrictions.
- What to do when it's broken: Run and record a security drill now covering an element of the facility security plan.
- Example reading used in demos: 2 months

**3. Annual security exercise** (Maximum 18 months, warns from 15 months)

- Asks: Months since the last facility security exercise (at least once each calendar year, never more than 18 months apart)
- Rule: 33 CFR 105.220(c)
- What a miss costs: Missing exercises is a Coast Guard deficiency that can bring penalties and operating restrictions.
- What to do when it's broken: Schedule and hold a security exercise now and record it.
- Example reading used in demos: 16 months

**4. Facility security plan audit** (Maximum 365 days, warns from 330 days; counts days since a date)

- Asks: Days since the facility security plan was last audited
- Rule: 33 CFR 105.415(b)
- What a miss costs: An unaudited security plan draws Coast Guard enforcement and leaves gaps that can lead to breaches and suspended operations.
- What to do when it's broken: Have the facility security officer complete the audit and submit any needed plan amendments.
- Example reading used in demos: 200 days

**5. MARSEC level change measures** (Maximum 12 h, warns from 9 h; counts hours since a date and time)

- Asks: Hours since notice that the maritime security (MARSEC) level went up, without all of the new level's measures in place
- Rule: 33 CFR 105.230
- What a miss costs: Failing to raise security when MARSEC rises can bring Coast Guard penalties and orders to stop cargo or vessel operations.
- What to do when it's broken: Put the higher MARSEC measures in place now and report status to the Captain of the Port.
- Example reading used in demos: 4 h

**6. Declaration of Security** (Must be in place, answered Yes or No)

- Asks: When a Declaration of Security is required, was it signed before the ship and the facility began working together?
- Rule: 33 CFR 105.245
- What a miss costs: Missing Declarations of Security draw Coast Guard penalties and can delay vessel operations.
- What to do when it's broken: Hold cargo or passenger operations until the vessel and facility security officers sign the Declaration.
- Example reading used in demos: Yes

**7. Report security breaches** (Must be in place, answered Yes or No)

- Asks: Has every breach of security and suspicious activity been reported to the National Response Center without delay?
- Rule: 33 CFR 101.305
- What a miss costs: Unreported breaches and suspicious activity bring Coast Guard penalties and harm the facility's standing with regulators.
- What to do when it's broken: Call the National Response Center now and record the report.
- Example reading used in demos: No

**8. Declaration of Inspection** (Must be in place, answered Yes or No)

- Asks: Before this oil transfer with a vessel began, was a Declaration of Inspection completed and signed by both persons in charge?
- Rule: 33 CFR 156.150
- What a miss costs: Starting an oil transfer without a Declaration of Inspection brings Coast Guard penalties and raises spill cleanup and liability costs.
- What to do when it's broken: Stop or hold the transfer until both persons in charge complete and sign the Declaration of Inspection.
- Example reading used in demos: Yes

**9. Oil spill response plan** (Must be in place, answered Yes or No)

- Asks: Does the facility have a current oil spill response plan submitted to the Coast Guard and kept at the facility?
- Rule: 33 U.S.C. 1321(j)(5); 33 CFR Part 154, Subpart F
- What a miss costs: Handling oil without a response plan brings Coast Guard penalties and can stop transfers; spills add cleanup and liability costs.
- What to do when it's broken: Stop oil transfers until a compliant response plan is submitted and in place.
- Example reading used in demos: Yes

**10. Crane annual examination** (Maximum 365 days, warns from 330 days; counts days since a date)

- Asks: Days since the crane's last annual certification examination
- Rule: 29 CFR 1917.50
- What a miss costs: Uncertified cranes draw OSHA citations and cannot be used, delaying vessel work; crane failures cause injuries and damage.
- What to do when it's broken: Take the crane out of service until an accredited agency examines and certifies it.
- Example reading used in demos: 390 days

### 25. GeneArmor (Biotech & Genetics)

**1. IBC approval before research** (Must be in place, answered Yes or No)

- Asks: For work under NIH Guidelines Sections III-A to III-D, did the Institutional Biosafety Committee (IBC) approve it before it began?
- Rule: NIH Guidelines, Section III (III-A to III-D)
- What a miss costs: Noncompliance with the NIH Guidelines can lead NIH to suspend or end funding for the project or the whole institution.
- What to do when it's broken: Stop the experiment and submit it to the Institutional Biosafety Committee for approval.
- Example reading used in demos: No

**2. Select agent registration** (Must never happen, answered Yes or No)

- Asks: Is any select agent or toxin held, used or transferred outside a current registration?
- Rule: 42 CFR 73.7; 7 CFR 331.7; 9 CFR 121.7
- What a miss costs: Unregistered select agent work brings civil penalties, criminal charges and loss of the right to hold select agents.
- What to do when it's broken: Secure the material, stop work, and contact the Federal Select Agent Program right away.
- Example reading used in demos: No

**3. Select agent theft or loss** (Must be in place, answered Yes or No)

- Asks: Has every theft, loss or release of a select agent or toxin been reported to CDC or APHIS right away?
- Rule: 42 CFR 73.19; 7 CFR 331.19; 9 CFR 121.19
- What a miss costs: Unreported theft, loss or release brings penalties and can lead to suspension or revocation of registration.
- What to do when it's broken: Report to CDC or APHIS now, and to law enforcement for theft, then file the written report.
- Example reading used in demos: Yes

**4. Bloodborne pathogens training** (Maximum 365 days, warns from 330 days; counts days since a date)

- Asks: Days since the worker's last bloodborne pathogens training
- Rule: 29 CFR 1910.1030(g)(2)(ii)
- What a miss costs: Missed training is a frequently cited part of the bloodborne pathogens standard, and untrained staff raise exposure and claim costs.
- What to do when it's broken: Keep the worker from tasks with exposure risk until annual training is completed.
- Example reading used in demos: 150 days

**5. Bloodborne exposure control plan** (Maximum 365 days, warns from 330 days; counts days since a date)

- Asks: Days since the exposure control plan was reviewed and updated
- Rule: 29 CFR 1910.1030(c)(1)(iv)
- What a miss costs: Bloodborne pathogens is a frequently cited OSHA standard, and exposures lead to medical costs and claims.
- What to do when it's broken: Review and update the exposure control plan now, including safer sharps devices.
- Example reading used in demos: 350 days

**6. Chemical hygiene plan review** (Maximum 365 days, warns from 330 days; counts days since a date)

- Asks: Days since the chemical hygiene plan was reviewed
- Rule: 29 CFR 1910.1450(e)(4)
- What a miss costs: An outdated lab chemical hygiene plan draws OSHA citations and leaves staff exposed to chemical injuries.
- What to do when it's broken: Review the chemical hygiene plan's effectiveness now and update it as needed.
- Example reading used in demos: 120 days

**7. Biosafety cabinet certification** (Maximum 365 days, warns from 330 days; policy, a company can set its own limit; counts days since a date)

- Asks: Days since the biosafety cabinet was last certified on site
- Rule: NSF/ANSI 49 standard; CDC/NIH BMBL (annual field certification)
- What a miss costs: Uncertified cabinets can expose staff and ruin samples, putting at risk inspections, grants and select agent registration.
- What to do when it's broken: Stop work in the cabinet and have it field-certified before use.
- Example reading used in demos: 400 days

**8. Infectious substance packaging** (Must be in place, answered Yes or No)

- Asks: Is every infectious substance shipment in the required triple packaging and marked and labeled correctly?
- Rule: 49 CFR 173.196 (Category A); 49 CFR 173.199 (Category B)
- What a miss costs: Improper shipments bring DOT civil penalties, carrier refusals and lost samples.
- What to do when it's broken: Hold the shipment and repack it in compliant packaging with correct marks and labels.
- Example reading used in demos: Yes

**9. HIPAA risk analysis** (Must be in place, answered Yes or No)

- Asks: Has a current security risk analysis been done for systems holding patients' genetic and health data?
- Rule: 45 CFR 164.308(a)(1)(ii)(A)
- What a miss costs: Missing risk analyses are a frequent finding in HIPAA enforcement settlements, and genetic data breaches also bring lawsuits.
- What to do when it's broken: Complete a risk analysis of all systems with patient data and start fixing the risks it finds.
- Example reading used in demos: No

**10. IRB approval for human research** (Must be in place, answered Yes or No)

- Asks: Did an Institutional Review Board (IRB) approve this research with people before anyone was enrolled?
- Rule: 45 CFR 46.103 and 46.109
- What a miss costs: Research without IRB approval can lead to suspended federal funding, unusable data and lawsuits from participants.
- What to do when it's broken: Stop enrolling participants and submit the study to the IRB for review.
- Example reading used in demos: Yes

### 26. SeniorArmor (Nursing Homes & Assisted Living)

**1. Abuse allegation reported in 2 hours** (Maximum 2 h, warns from 1.5 h; counts hours since a date and time)

- Asks: Hours since staff learned of an allegation involving abuse or serious bodily injury, without reporting it to the administrator and state agency
- Rule: 42 CFR 483.12(c)(1); Elder Justice Act, 42 U.S.C. 1320b-25(b)
- What a miss costs: Late abuse reporting is cited as immediate jeopardy, bringing civil money penalties, payment denials and possible loss of Medicare certification.
- What to do when it's broken: Report now to the administrator and the state survey agency (and law enforcement if a crime is suspected); protect the resident.
- Example reading used in demos: 3 h

**2. Abuse investigation results filed** (Maximum 5 working days, warns from 4 working days; counts business days since a date)

- Asks: Working days since the incident without reporting investigation results to the administrator and state survey agency
- Rule: 42 CFR 483.12(c)(4)
- What a miss costs: Incomplete or late investigations are cited under abuse and neglect tags, which draw civil money penalties and lawsuits from families.
- What to do when it's broken: Finish the investigation and send the results to the administrator and state survey agency today.
- Example reading used in demos: 2 working days

**3. Fall prevention and supervision** (Must be in place, answered Yes or No)

- Asks: Does every resident assessed as a fall risk have care-planned interventions and supervision that staff are actually carrying out?
- Rule: 42 CFR 483.25(d)
- What a miss costs: Falls from missing supervision or devices are frequently cited deficiencies and a common cause of wrongful-death and injury lawsuits.
- What to do when it's broken: Reassess each fall-risk resident, update the care plan with supervision and devices, and brief every shift.
- Example reading used in demos: No

**4. Pressure injury prevention** (Must be in place, answered Yes or No)

- Asks: Is every resident at risk for pressure injuries on a documented skin-check and repositioning plan that staff follow?
- Rule: 42 CFR 483.25(b)(1)
- What a miss costs: Avoidable pressure injuries are cited as harm or immediate jeopardy and are a common basis for neglect lawsuits and penalties.
- What to do when it's broken: Assess skin for all at-risk residents now, start repositioning and support surfaces, and notify the physician of any wound.
- Example reading used in demos: Yes

**5. Infection preventionist on staff** (Must be in place, answered Yes or No)

- Asks: Is a specially trained infection preventionist designated and working at least part-time at the facility?
- Rule: 42 CFR 483.80(a)-(b)
- What a miss costs: Infection control is a frequently cited nursing home deficiencies and can lead to civil money penalties and outbreak lawsuits.
- What to do when it's broken: Designate a qualified infection preventionist who has completed specialized training, and document the assignment.
- Example reading used in demos: Yes

**6. PRN psychotropic 14-day limit** (Maximum 14 days, warns from 12 days; counts days since a date)

- Asks: Days since the as-needed (PRN) order for a psychotropic drug was written, without a renewal from the prescriber on record
- Rule: 42 CFR 483.45(e)(4)-(5)
- What a miss costs: Unnecessary or open-ended psychotropic orders are cited as chemical restraint and unnecessary drugs, drawing penalties and lawsuits.
- What to do when it's broken: Stop using the PRN order until the prescriber evaluates the resident and documents the rationale and duration.
- Example reading used in demos: 13 days

**7. RN on duty 8 hours every day** (Must be in place, answered Yes or No)

- Asks: Is a registered nurse on duty for at least 8 hours in a row today?
- Rule: 42 U.S.C. 1395i-3(b)(4)(C)(i); 42 CFR 483.35(b)
- What a miss costs: Missing RN coverage is cited as a staffing deficiency, can lower star ratings and draws civil money penalties.
- What to do when it's broken: Schedule or call in a registered nurse to cover at least 8 hours in a row today.
- Example reading used in demos: Yes

**8. Admission MDS within 14 days** (Maximum 14 days, warns from 12 days; counts days since a date)

- Asks: Calendar days since admission without a completed comprehensive admission assessment (MDS)
- Rule: 42 CFR 483.20(b)(2)(i)
- What a miss costs: Late MDS assessments are cited in surveys and can delay or reduce Medicare and Medicaid payment for the stay.
- What to do when it's broken: Complete and sign the comprehensive admission assessment today and transmit it as required.
- Example reading used in demos: 9 days

**9. Payroll-Based Journal submitted** (Maximum 45 days, warns from 35 days; counts days since a date)

- Asks: Days since the end of the quarter without submitting Payroll-Based Journal staffing data
- Rule: 42 CFR 483.70 (PBJ staffing data); CMS PBJ deadline 45 days after quarter end
- What a miss costs: Missing or late PBJ staffing data lowers the facility's Care Compare staffing rating, which cuts referrals, and can be cited.
- What to do when it's broken: Submit the quarter's payroll-based staffing data to CMS now and confirm it was accepted.
- Example reading used in demos: 38 days

**10. Emergency plan reviewed yearly** (Maximum 365 days, warns from 335 days; counts days since a date)

- Asks: Days since the emergency preparedness plan was last reviewed and updated
- Rule: 42 CFR 483.73(a)
- What a miss costs: An outdated emergency plan is cited in surveys, and poor disaster response can bring penalties, evacuations and lawsuits.
- What to do when it's broken: Review and update the emergency plan, risk assessment and communication plan now, and document the review.
- Example reading used in demos: 400 days

### 27. DentalArmor (Dental & Medical Practices)

**1. No false or unsupported claims** (Must never happen, answered Yes or No)

- Asks: Did a chart audit find claims billed at a higher code, or for services not provided or not documented?
- Rule: 31 U.S.C. 3729; 42 U.S.C. 1320a-7a
- What a miss costs: Billing for services not provided or not documented brings False Claims Act damages, penalties and exclusion from Medicare and Medicaid.
- What to do when it's broken: Stop billing the affected codes, correct the documentation process, and refund any overpayments.
- Example reading used in demos: No

**2. Overpayments returned in 60 days** (Maximum 60 days, warns from 45 days; counts days since a date)

- Asks: Days since an overpayment was identified without reporting and returning it
- Rule: 42 U.S.C. 1320a-7k(d); 42 CFR 401.305
- What a miss costs: Keeping an identified Medicare or Medicaid overpayment past the deadline turns it into a False Claims Act liability.
- What to do when it's broken: Report and return the overpayment to the payer now, with a written explanation of the reason.
- Example reading used in demos: 50 days

**3. HIPAA security risk analysis** (Must be in place, answered Yes or No)

- Asks: Has the practice completed and documented a current security risk analysis covering all systems with patient data?
- Rule: 45 CFR 164.308(a)(1)(ii)(A)
- What a miss costs: A missing risk analysis is the most common finding in HIPAA enforcement, leading to settlements, penalties and ransomware losses.
- What to do when it's broken: Complete a documented risk analysis of all electronic patient data and start a plan to fix the risks found.
- Example reading used in demos: No

**4. Breach notice within 60 days** (Maximum 60 days, warns from 45 days; counts days since a date)

- Asks: Calendar days since a breach of unsecured patient information was discovered without notifying affected patients
- Rule: 45 CFR 164.404(b)
- What a miss costs: Late breach notices draw HHS civil money penalties, state attorney general actions and patient lawsuits.
- What to do when it's broken: Send written notice to every affected patient now, and notify HHS (and media if 500+ in a state) as required.
- Example reading used in demos: 20 days

**5. Hepatitis B vaccine offered** (Maximum 10 working days, warns from 8 working days; counts business days since a date)

- Asks: Working days since a new employee with blood exposure was assigned without being offered the hepatitis B vaccine
- Rule: 29 CFR 1910.1030(f)(2)(i)
- What a miss costs: Not offering the vaccine is a frequently cited OSHA bloodborne pathogens violation and raises workers' compensation exposure.
- What to do when it's broken: Offer the hepatitis B vaccine series at no cost now, or get a signed declination form.
- Example reading used in demos: 4 working days

**6. Exposure control plan annual review** (Maximum 365 days, warns from 335 days; counts days since a date)

- Asks: Days since the written exposure control plan was last reviewed and updated
- Rule: 29 CFR 1910.1030(c)(1)(iv)
- What a miss costs: An outdated bloodborne pathogens exposure control plan is among the OSHA citations most often issued to dental and medical offices.
- What to do when it's broken: Review and update the exposure control plan now, including safer sharps devices and staff input.
- Example reading used in demos: 350 days

**7. Chemical hazard communication** (Must be in place, answered Yes or No)

- Asks: Is there a written hazard communication program, a safety data sheet for every chemical used, and trained staff?
- Rule: 29 CFR 1910.1200(e), (g), (h)
- What a miss costs: Missing safety data sheets or chemical training is frequently cited by OSHA and draws per-violation penalties.
- What to do when it's broken: Collect missing safety data sheets, update the written program and chemical list, and train staff.
- Example reading used in demos: Yes

**8. Weekly sterilizer spore test** (Maximum 7 days, warns from 6 days; policy, a company can set its own limit; counts days since a date)

- Asks: Days since each sterilizer last had a biological (spore) test
- Rule: CDC Guidelines for Infection Control in Dental Health-Care Settings (2003); common policy
- What a miss costs: A failed or untested sterilizer can force patient notification and testing, board discipline and infection lawsuits.
- What to do when it's broken: Run a spore test on the sterilizer today and hold instruments until results are negative.
- Example reading used in demos: 9 days

**9. DEA registration current** (Minimum 0 days, warns from 60 days; counts days until a date)

- Asks: Days until the practitioner's DEA registration for this location expires
- Rule: 21 U.S.C. 822; 21 CFR 1301.13
- What a miss costs: Prescribing or storing controlled substances without a valid DEA registration is unlawful and can bring DEA penalties and board discipline.
- What to do when it's broken: Stop prescribing controlled substances and renew the DEA registration online now.
- Example reading used in demos: 45 days

**10. Amalgam separator in use** (Must be in place, answered Yes or No)

- Asks: If the office places or removes amalgam, is an ISO 11143-compliant amalgam separator installed, maintained and on file?
- Rule: 40 CFR 441.30; 40 CFR 441.40; 40 CFR 441.50
- What a miss costs: Discharging amalgam without a compliant separator violates Clean Water Act pretreatment rules and can bring enforcement by the local sewer authority.
- What to do when it's broken: Install or repair a compliant amalgam separator, follow the best management practices, and file the compliance report.
- Example reading used in demos: Yes

### 28. PharmacyArmor (Pharmacies)

**1. Controlled Rx red flags resolved** (Must be in place, answered Yes or No)

- Asks: Are red flags on controlled-substance prescriptions resolved and documented before they are filled?
- Rule: 21 CFR 1306.04(a); 21 CFR 1306.06
- What a miss costs: Filling illegitimate controlled-substance prescriptions brings DEA registration loss, civil penalties and opioid lawsuits.
- What to do when it's broken: Do not dispense until the red flag is resolved with the prescriber and documented; refuse if it cannot be.
- Example reading used in demos: Yes

**2. Biennial controlled-drug inventory** (Maximum 730 days, warns from 670 days; counts days since a date)

- Asks: Days since the last complete controlled-substance inventory
- Rule: 21 CFR 1304.11(c)
- What a miss costs: Missing inventories are recordkeeping violations under the Controlled Substances Act and carry civil penalties per violation.
- What to do when it's broken: Take a complete inventory of all controlled substances now and keep it on file for DEA inspection.
- Example reading used in demos: 700 days

**3. Theft or loss reported to DEA** (Maximum 1 business days, warns from 1 business days; counts business days since a date)

- Asks: Business days since discovering a theft or significant loss of controlled substances without notifying DEA in writing
- Rule: 21 CFR 1301.76(b)
- What a miss costs: Unreported theft or significant loss of controlled substances draws DEA civil penalties and can put the pharmacy's registration at risk.
- What to do when it's broken: Notify the DEA field division in writing now, then complete DEA Form 106 and notify police as appropriate.
- Example reading used in demos: 2 business days

**4. Emergency C-II follow-up in 7 days** (Maximum 7 days, warns from 5 days; counts days since a date)

- Asks: Days since filling an emergency Schedule II prescription given by phone, without receiving the prescriber's follow-up prescription
- Rule: 21 CFR 1306.11(d)(4)
- What a miss costs: Dispensing an emergency oral Schedule II prescription without the follow-up prescription is a Controlled Substances Act violation.
- What to do when it's broken: Notify the nearest DEA Diversion office that the follow-up prescription was not received.
- Example reading used in demos: 3 days

**5. C-III/IV refill limit** (Maximum 5 refills, warns from 5 refills)

- Asks: Refill number about to be dispensed on this Schedule III or IV prescription (also must be within 6 months of issue)
- Rule: 21 CFR 1306.22(a)
- What a miss costs: Refilling Schedule III or IV prescriptions past legal limits is a Controlled Substances Act violation that draws DEA penalties.
- What to do when it's broken: Do not refill; get a new prescription from the prescriber.
- Example reading used in demos: 6 refills

**6. DSCSA supplier and product checks** (Must be in place, answered Yes or No)

- Asks: Does the pharmacy buy only from authorized trading partners, keep transaction data, and quarantine suspect product?
- Rule: 21 U.S.C. 360eee-1(d)
- What a miss costs: Buying from unauthorized sources or without transaction data violates the DSCSA and risks counterfeit drugs, FDA action and lawsuits.
- What to do when it's broken: Stop buying from the unverified source, quarantine the product, investigate, and notify FDA if it is illegitimate.
- Example reading used in demos: Yes

**7. Sterile compounding room certified** (Maximum 180 days, warns from 160 days; policy, a company can set its own limit; counts days since a date)

- Asks: Days since the sterile compounding hoods and cleanroom were last certified
- Rule: USP <797> (every 6 months); enforced through state boards, state law varies
- What a miss costs: Uncertified cleanrooms can lead to state board shutdown of compounding, FDA action and contamination lawsuits.
- What to do when it's broken: Stop sterile compounding in the affected area until it is recertified by a qualified certifier.
- Example reading used in demos: 150 days

**8. Staff checked for exclusion** (Maximum 31 days, warns from 25 days; policy, a company can set its own limit; counts days since a date)

- Asks: Days since all staff were last checked against the OIG exclusion list
- Rule: 42 U.S.C. 1320a-7a(a)(6); OIG guidance; monthly screening is common policy
- What a miss costs: Employing an excluded person makes claims they touch unpayable and brings OIG civil money penalties.
- What to do when it's broken: Screen all staff against the OIG exclusion list now and remove any excluded person from covered work.
- Example reading used in demos: 40 days

**9. Counseling offered to patients** (Must be in place, answered Yes or No)

- Asks: Is every patient offered pharmacist counseling on new prescriptions, with refusals documented?
- Rule: 42 U.S.C. 1396r-8(g)(2)(A)(ii); state law varies
- What a miss costs: Failing to offer counseling violates state pharmacy rules and Medicaid standards, and missed counseling is cited in malpractice claims.
- What to do when it's broken: Offer counseling at pickup for every new prescription and document the offer or refusal.
- Example reading used in demos: No

**10. Pharmacy staff licenses current** (Minimum 0 days, warns from 60 days; policy, a company can set its own limit; counts days until a date)

- Asks: Days until the earliest pharmacist, technician or pharmacy permit expiration
- Rule: State pharmacy practice acts; renewal cycles vary by state
- What a miss costs: Working with an expired pharmacist, technician or pharmacy license brings state board discipline and makes claims unpayable.
- What to do when it's broken: Remove the unlicensed person from duty or stop operating under the expired permit until it is renewed.
- Example reading used in demos: 90 days

### 29. BuildArmor (Construction)

**1. Fall protection at 6 feet** (Must be in place, answered Yes or No)

- Asks: Are all workers 6 feet or more above a lower level protected by guardrails, safety nets or personal fall arrest systems?
- Rule: 29 CFR 1926.501(b)(1)
- What a miss costs: Fall protection is frequently cited by OSHA, and falls lead to serious penalties, stop-work orders and injury lawsuits.
- What to do when it's broken: Stop work at height until guardrails, nets or personal fall arrest systems are in place.
- Example reading used in demos: No

**2. Trench protection at 5 feet** (Must be in place, answered Yes or No)

- Asks: Is every trench 5 feet or deeper that workers enter protected by sloping, shoring or a trench box (unless in stable rock)?
- Rule: 29 CFR 1926.652(a)(1)
- What a miss costs: Unprotected trenches cause fatal cave-ins and draw willful OSHA citations, possible criminal referral and wrongful-death suits.
- What to do when it's broken: Get everyone out of the trench now; do not re-enter until a protective system is installed.
- Example reading used in demos: Yes

**3. Daily trench inspection** (Must be in place, answered Yes or No)

- Asks: Did a competent person inspect each open excavation today before work and after any rain or other hazard-increasing event?
- Rule: 29 CFR 1926.651(k)(1)
- What a miss costs: Skipping competent-person inspections is a common OSHA excavation citation and leaves hazards unnoticed before cave-ins.
- What to do when it's broken: Keep workers out until a competent person inspects the excavation and protective system.
- Example reading used in demos: Yes

**4. Scaffold fall protection over 10 ft** (Must be in place, answered Yes or No)

- Asks: Are workers on scaffolds more than 10 feet above a lower level protected by guardrails or personal fall arrest systems?
- Rule: 29 CFR 1926.451(g)(1)
- What a miss costs: Scaffold violations are frequently cited by OSHA, and scaffold falls lead to penalties and injury lawsuits.
- What to do when it's broken: Clear the scaffold until guardrails or personal fall arrest systems are installed.
- Example reading used in demos: Yes

**5. Ladder extends 3 ft above landing** (Minimum 3 ft, warns from 3 ft)

- Asks: Feet the portable ladder's side rails extend above the upper landing (if no grab rail is provided)
- Rule: 29 CFR 1926.1053(b)(1)
- What a miss costs: Ladder violations are frequently cited by OSHA and a frequent cause of injury claims.
- What to do when it's broken: Reposition or replace the ladder so the rails extend 3 feet above the landing, or secure it and add a grab device.
- Example reading used in demos: 2 ft

**6. Silica exposure limit** (Maximum 50 µg/m³, warns from 25 µg/m³)

- Asks: Measured respirable crystalline silica exposure, 8-hour average (if not following Table 1 controls)
- Rule: 29 CFR 1926.1153(d) (PEL); action level 25 in 1926.1153(b)
- What a miss costs: Silica overexposure is a frequently cited OSHA health standard and leads to occupational disease claims.
- What to do when it's broken: Add dust controls such as water or vacuum, provide respirators, and restrict access until exposure is below the limit.
- Example reading used in demos: 30 µg/m³

**7. Crane operator certified** (Must be in place, answered Yes or No)

- Asks: Is every crane operator on site certified or qualified for the equipment type and evaluated by the employer?
- Rule: 29 CFR 1926.1427(a)
- What a miss costs: Uncertified operators draw OSHA citations, and crane incidents lead to deaths, property damage and very large lawsuits.
- What to do when it's broken: Do not operate the crane until a certified and evaluated operator is assigned.
- Example reading used in demos: Yes

**8. Davis-Bacon prevailing wages paid** (Must never happen, answered Yes or No)

- Asks: Is any worker on a federally funded job paid less than the prevailing wage and fringe benefits for their classification?
- Rule: 40 U.S.C. 3142; 29 CFR 5.5(a)(1)
- What a miss costs: Underpaying prevailing wages brings back-wage orders, withheld contract payments and possible debarment from federal work.
- What to do when it's broken: Pay back wages to affected workers now and correct their classification and rates on the next payroll.
- Example reading used in demos: No

**9. Weekly certified payroll** (Maximum 7 days, warns from 5 days; counts days since a date)

- Asks: Days since the regular pay date for a Davis-Bacon payroll week without submitting its certified payroll
- Rule: 29 CFR 5.5(a)(3)(ii); 29 CFR 3.4(a)
- What a miss costs: Late or missing certified payrolls let the agency withhold contract payments and can lead to debarment.
- What to do when it's broken: Submit the signed certified payroll and statement of compliance for the week now.
- Example reading used in demos: 6 days

**10. EPA lead-safe certification** (Must be in place, answered Yes or No)

- Asks: For work disturbing paint in pre-1978 homes or child-occupied facilities, is the firm EPA-certified with a certified renovator assigned?
- Rule: 40 CFR 745.81(a); 40 CFR 745.89
- What a miss costs: Disturbing paint in pre-1978 homes without RRP certification brings EPA civil penalties and lead-poisoning lawsuits.
- What to do when it's broken: Stop paint-disturbing work until the firm is certified and a certified renovator directs lead-safe practices.
- Example reading used in demos: Yes

### 30. HRArmor (Employers & HR)

**1. Overtime paid over 40 hours** (Must be in place, answered Yes or No)

- Asks: Is every employee who is owed overtime (non-exempt) paid 1.5 times the regular rate for all hours over 40 in a workweek?
- Rule: 29 U.S.C. 207(a)(1)
- What a miss costs: Unpaid overtime brings back wages plus equal liquidated damages, attorney fees and class or collective action lawsuits.
- What to do when it's broken: Pay the unpaid overtime on the next payroll and fix timekeeping so all hours over 40 are paid at 1.5x.
- Example reading used in demos: No

**2. Exempt salary threshold** (Minimum $684, warns from $720)

- Asks: Weekly salary paid to an employee classified as exempt (executive, administrative or professional)
- Rule: 29 CFR 541.600(a); higher state thresholds may apply
- What a miss costs: Misclassified exempt employees are owed back overtime plus liquidated damages and attorney fees.
- What to do when it's broken: Reclassify the employee as non-exempt and pay overtime, or raise the salary to at least the threshold.
- Example reading used in demos: $650

**3. Federal minimum wage paid** (Minimum $7.25, warns from $7.25)

- Asks: Lowest hourly rate paid to any non-exempt employee
- Rule: 29 U.S.C. 206(a)(1)(C); higher state or local minimums may apply
- What a miss costs: Minimum wage violations bring back wages plus equal liquidated damages and Department of Labor penalties for repeat violations.
- What to do when it's broken: Raise the rate to at least the federal minimum (or higher state or local rate) and pay the difference owed.
- Example reading used in demos: $12

**4. Form I-9 done within 3 business days** (Maximum 3 business days, warns from 2 business days; counts business days since a date)

- Asks: Business days since the new hire's first day of work without a completed I-9 Section 2
- Rule: 8 CFR 274a.2(b)(1)(ii)
- What a miss costs: Missing or late I-9s are the most common immigration audit finding and bring per-form civil penalties.
- What to do when it's broken: Examine the employee's documents and complete Section 2 of Form I-9 today.
- Example reading used in demos: 2 business days

**5. Hours worked records kept** (Must be in place, answered Yes or No)

- Asks: Are hours worked each day and each week recorded and kept for every non-exempt employee?
- Rule: 29 CFR 516.2(a)(7); 29 CFR 516.5-516.6
- What a miss costs: Without accurate time records, courts accept employee estimates of hours owed, making wage lawsuits hard to defend.
- What to do when it's broken: Start recording daily and weekly hours for every non-exempt employee and keep payroll records for 3 years.
- Example reading used in demos: Yes

**6. ACA coverage offer (50+ FTEs)** (Minimum 95%, warns from 97%)

- Asks: Percent of full-time employees (and dependents) offered minimum essential coverage this month
- Rule: 26 U.S.C. 4980H(a); 26 CFR 54.4980H-4(a)
- What a miss costs: Large employers that do not offer coverage to enough full-time employees owe IRS employer shared responsibility payments.
- What to do when it's broken: Offer coverage to uncovered full-time employees at the next enrollment opportunity and review full-time tracking.
- Example reading used in demos: 96%

**7. COBRA election notice sent** (Maximum 44 days, warns from 35 days; counts days since a date)

- Asks: Days since a qualifying event without sending the COBRA election notice (employer is plan administrator, 20+ employees)
- Rule: 29 CFR 2590.606-4(b)(2)
- What a miss costs: Late COBRA notices bring ERISA statutory penalties, liability for medical claims and lawsuits from former employees.
- What to do when it's broken: Send the COBRA election notice to the employee and dependents now by a trackable method.
- Example reading used in demos: 50 days

**8. FMLA notice within 5 business days** (Maximum 5 business days, warns from 4 business days; counts business days since a date)

- Asks: Business days since the employee requested leave or the employer learned of a possible FMLA reason, without a notice
- Rule: 29 CFR 825.300(b)(1), (c)
- What a miss costs: Late FMLA notices can be treated as interference, bringing lost wages, damages and attorney fees in employee lawsuits.
- What to do when it's broken: Send the eligibility notice and rights and responsibilities notice to the employee today.
- Example reading used in demos: 3 business days

**9. Report hospitalization in 24 hours** (Maximum 24 h, warns from 20 h; counts hours since a date and time)

- Asks: Hours since learning of a work-related in-patient hospitalization, amputation or eye loss without reporting to OSHA
- Rule: 29 CFR 1904.39(a)(2)
- What a miss costs: Failing to report a work-related hospitalization, amputation or eye loss to OSHA is cited and can trigger an inspection.
- What to do when it's broken: Report the incident to OSHA now by phone, in person or online.
- Example reading used in demos: 6 h

**10. Report a work fatality in 8 hours** (Maximum 8 h, warns from 6 h; counts hours since a date and time)

- Asks: Hours since learning of a work-related fatality without reporting it to OSHA
- Rule: 29 CFR 1904.39(a)(1)
- What a miss costs: Failing to report a work-related death to OSHA on time is cited, and the fatality inspection that follows can bring major penalties.
- What to do when it's broken: Report the fatality to OSHA now by phone or in person, and preserve the scene.
- Example reading used in demos: 2 h

### 31. PrivacyArmor (Data Privacy & SaaS)

**1. Breach notice to authority in 72 hours** (Maximum 72 h, warns from 48 h; counts hours since a date and time)

- Asks: Hours since becoming aware of a personal data breach, without notifying the supervisory authority (the data protection regulator)
- Rule: GDPR Art. 33(1)
- What a miss costs: Late breach notice draws GDPR fines from supervisory authorities on top of the breach costs and follow-on claims.
- What to do when it's broken: Notify the lead supervisory authority now; explain the reasons for any delay and send what facts you have.
- Example reading used in demos: 50 h

**2. Lawful basis for processing** (Must be in place, answered Yes or No)

- Asks: Is a lawful basis written down for every way you use personal data, with valid consent where consent is the basis?
- Rule: GDPR Art. 6(1); Art. 7
- What a miss costs: Processing without a valid legal basis, such as invalid consent for ads, is the ground for many of the largest GDPR fines and orders to stop processing.
- What to do when it's broken: Stop the processing that lacks a lawful basis until a valid basis is identified and documented.
- Example reading used in demos: Yes

**3. Lawful transfers outside the EEA** (Must be in place, answered Yes or No)

- Asks: Is every transfer of personal data out of the European Economic Area (EEA) covered by an adequacy decision, standard contractual clauses or another tool allowed under Chapter V?
- Rule: GDPR Chapter V (Art. 44-49)
- What a miss costs: Unlawful transfers of EU personal data can bring large GDPR fines and orders to suspend transfers that the product depends on.
- What to do when it's broken: Pause the uncovered transfer; put SCCs with a transfer risk assessment in place or use an adequacy-covered recipient.
- Example reading used in demos: No

**4. Answer data subject requests** (Maximum 30 days, warns from 21 days; counts days since a date)

- Asks: Days since a person's request about their data was received, with no response and no extension notice
- Rule: GDPR Art. 12(3) (one month, treated here as 30 days; extendable by two months with notice)
- What a miss costs: Ignored or late access and erasure requests are among the most common complaints to regulators and lead to orders, fines and damages claims.
- What to do when it's broken: Respond now, or tell the person within the month why you are extending and by how long.
- Example reading used in demos: 12 days

**5. Answer CCPA consumer requests** (Maximum 45 days, warns from 35 days; counts days since a date)

- Asks: Days since the verifiable consumer request was received, with no response and no extension notice
- Rule: Cal. Civ. Code 1798.130(a)(2)
- What a miss costs: Missed consumer request deadlines draw California enforcement with civil penalties per violation and injunctive terms.
- What to do when it's broken: Respond now; the 45 days may be extended once by 45 more only if the consumer was told within the first 45.
- Example reading used in demos: 38 days

**6. Do Not Sell or Share and GPC honored** (Must be in place, answered Yes or No)

- Asks: Does the site show a Do Not Sell or Share link and treat Global Privacy Control signals as opt-out requests?
- Rule: Cal. Civ. Code 1798.120, 1798.135; 11 CCR 7025
- What a miss costs: Failing to offer or honor opt-outs of sale or sharing, including Global Privacy Control signals, has led to California settlements and penalties.
- What to do when it's broken: Add the opt-out link and configure tags and ad tools to stop selling or sharing when a GPC signal is received.
- Example reading used in demos: No

**7. Parental consent for kids under 13** (Must be in place, answered Yes or No)

- Asks: For a service directed to children or with known users under 13, is verifiable parental consent obtained before collecting their data?
- Rule: 15 U.S.C. 6502; 16 CFR 312.5
- What a miss costs: Collecting children's data without verifiable parental consent brings FTC civil penalties per violation and data deletion orders.
- What to do when it's broken: Stop collecting data from users under 13 until verifiable parental consent is in place; delete data collected without it.
- Example reading used in demos: Yes

**8. Breach notice to affected residents** (Maximum 30 days, warns from 20 days; policy, a company can set its own limit; counts days since a date)

- Asks: Days since the breach was discovered, without notifying affected residents
- Rule: State breach laws vary (policy); 30 days is the shortest common deadline, e.g., Colo. Rev. Stat. 6-1-716, Fla. Stat. 501.171
- What a miss costs: Late notice to affected people draws state attorney general penalties and strengthens class action claims after a breach.
- What to do when it's broken: Send notices to affected residents now and file any required state attorney general notices.
- Example reading used in demos: 34 days

**9. HIPAA business associate agreements** (Must be in place, answered Yes or No)

- Asks: Is a signed business associate agreement in place with every client and subcontractor for which you handle protected health information (PHI)?
- Rule: 45 CFR 164.502(e), 164.504(e), 164.308(b)
- What a miss costs: Handling protected health information without a signed business associate agreement is a HIPAA violation cited in OCR settlements and lost contracts.
- What to do when it's broken: Stop receiving PHI from, or sending it to, any party without a signed business associate agreement.
- Example reading used in demos: Yes

**10. DPIA before high-risk processing** (Must be in place, answered Yes or No)

- Asks: Was a data protection impact assessment completed before starting any use of personal data likely to be high risk?
- Rule: GDPR Art. 35(1)
- What a miss costs: Launching high-risk processing without a data protection impact assessment draws GDPR fines and can force a product feature to be withdrawn.
- What to do when it's broken: Complete the DPIA before continuing; consult the supervisory authority if high risk remains after mitigation.
- Example reading used in demos: No

### 32. PayArmor (Payments & Merchants)

**1. No CVV or track data after auth** (Must never happen, answered Yes or No; policy)

- Asks: Are card security codes (CVV), full magnetic-stripe (track) data or PIN data stored anywhere after the payment is authorized?
- Rule: PCI DSS v4.0.1 Req. 3.3.1 (industry standard)
- What a miss costs: Storing sensitive authentication data turns a breach into card-brand assessments, forensic costs, higher fees and possible loss of card acceptance.
- What to do when it's broken: Find and securely delete the stored data, fix the capture flow, and report to your acquirer if a compromise is suspected.
- Example reading used in demos: No

**2. OFAC sanctions screening** (Must be in place, answered Yes or No)

- Asks: Are merchants, customers and payment parties checked against the OFAC sanctions list (SDN list) at onboarding and when the list changes?
- Rule: 31 CFR Part 501; 31 CFR Chapter V sanctions programs
- What a miss costs: Processing payments for sanctioned parties brings strict-liability OFAC civil penalties and bank de-risking of the business.
- What to do when it's broken: Hold transactions with unscreened parties; screen them now and block and report any match to OFAC.
- Example reading used in demos: Yes

**3. ACH unauthorized return rate** (Maximum 0.5%, warns from 0.4%; policy, a company can set its own limit)

- Asks: Unauthorized ACH debit return rate over the last 60 days
- Rule: Nacha Operating Rules Subsection 2.17.2 (unauthorized entry return rate, industry rule)
- What a miss costs: Exceeding the Nacha unauthorized return threshold leads to ODFI inquiries, fines under the Nacha rules and loss of ACH origination.
- What to do when it's broken: Stop origination for the high-return originators, fix authorization capture and give your ODFI a reduction plan.
- Example reading used in demos: 0.62%

**4. Chargeback ratio under program limit** (Maximum 1%, warns from 0.75%; policy, a company can set its own limit)

- Asks: Chargebacks as a percent of settled card transactions last month
- Rule: Card brand dispute monitoring programs (policy setting; set to your acquirer's current Visa and Mastercard thresholds)
- What a miss costs: Crossing card-brand dispute program thresholds brings monthly fines, higher processing costs and possible termination of the merchant account.
- What to do when it's broken: Tighten fraud screening, fix billing descriptors and refund policies, and contact your acquirer about a remediation plan.
- Example reading used in demos: 0.8%

**5. MFA for access into the CDE** (Must be in place, answered Yes or No; policy)

- Asks: Is multi-factor authentication required for all access into the systems that hold card data (cardholder data environment)?
- Rule: PCI DSS v4.0.1 Req. 8.4.2 (industry standard)
- What a miss costs: Password-only access to cardholder data systems is a common breach path that leads to card-brand assessments and failed PCI validation.
- What to do when it's broken: Turn on MFA for every account that can reach the cardholder data environment before further access.
- Example reading used in demos: No

**6. Quarterly external ASV scan** (Maximum 90 days, warns from 75 days; policy, a company can set its own limit; counts days since a date)

- Asks: Days since the last passing external vulnerability scan by an Approved Scanning Vendor
- Rule: PCI DSS v4.0.1 Req. 11.3.2 (industry standard; once every three months)
- What a miss costs: Missing passing ASV scans puts the business out of PCI compliance, raising non-compliance fees and breach liability.
- What to do when it's broken: Run an ASV scan now, fix failing findings and rescan until it passes.
- Example reading used in demos: 64 days

**7. Annual PCI validation (SAQ/ROC)** (Maximum 365 days, warns from 330 days; policy, a company can set its own limit; counts days since a date)

- Asks: Days since the last completed PCI self-assessment (SAQ) or Report on Compliance, with its Attestation of Compliance
- Rule: Card brand compliance programs (policy; annual SAQ or ROC with AOC)
- What a miss costs: Lapsed PCI validation brings monthly non-compliance fees from the acquirer and weakens the defense after a breach.
- What to do when it's broken: Complete the SAQ or ROC and submit the Attestation of Compliance to your acquirer.
- Example reading used in demos: 342 days

**8. Stored card numbers unreadable** (Must be in place, answered Yes or No; policy)

- Asks: Is every stored card number (PAN) made unreadable by encryption, tokenization, truncation or hashing?
- Rule: PCI DSS v4.0.1 Req. 3.5.1 (industry standard)
- What a miss costs: Stored card numbers in clear text make a breach far more costly through card-brand assessments, card reissue costs and lawsuits.
- What to do when it's broken: Encrypt or tokenize the stored card numbers now and delete any you do not need.
- Example reading used in demos: Yes

**9. Reg E error investigation timing** (Maximum 10 business days, warns from 8 business days; counts business days since a date)

- Asks: Business days since the consumer reported the error, without finishing the investigation or giving provisional credit
- Rule: 12 CFR 1005.11(c)
- What a miss costs: Slow handling of consumer disputes on transfers, prepaid or P2P accounts has led to CFPB consent orders with restitution and penalties.
- What to do when it's broken: Finish the investigation now or give provisional credit and notify the consumer.
- Example reading used in demos: 6 business days

**10. Credit card surcharge within cap** (Maximum 3%, warns from 2.75%; policy, a company can set its own limit)

- Asks: Surcharge charged on credit card transactions, as a percent of the sale
- Rule: Card brand surcharge rules (policy; Visa U.S. cap is 3%); state law varies; no surcharges on debit or prepaid cards
- What a miss costs: Surcharges over card-brand caps or in states that restrict them lead to card-brand fines, state enforcement and refund claims.
- What to do when it's broken: Lower the surcharge to the cap, confirm your state allows it, disclose it and stop surcharging debit cards.
- Example reading used in demos: 3.5%

### 33. CryptoArmor (Crypto & Money Services)

**1. Effective AML program** (Must be in place, answered Yes or No)

- Asks: Is there a written, risk-based anti-money-laundering (AML) program with a compliance officer, training and working transaction monitoring?
- Rule: 31 U.S.C. 5318(h); 31 CFR 1022.210
- What a miss costs: AML program failures are the basis of the largest FinCEN and DOJ crypto settlements, with monitorships and forced exits from the U.S. market.
- What to do when it's broken: Fix the program gaps now: name a qualified compliance officer, turn on monitoring and document the risk assessment.
- Example reading used in demos: Yes

**2. SAR filed within 30 days** (Maximum 30 days, warns from 20 days; counts days since a date)

- Asks: Days since first spotting facts that may require a suspicious activity report (SAR), with none filed
- Rule: 31 CFR 1022.320(a)(2), (b)(3) ($2,000 threshold)
- What a miss costs: Late or missing SARs are cited in almost every FinCEN enforcement action against money services businesses and draw civil penalties.
- What to do when it's broken: File the SAR with FinCEN now and document why it was late.
- Example reading used in demos: 33 days

**3. OFAC sanctions screening** (Must be in place, answered Yes or No)

- Asks: Are customers, IP locations and counterparty wallet addresses screened against OFAC sanctions lists?
- Rule: 31 CFR Part 501; 31 CFR Chapter V sanctions programs
- What a miss costs: Serving sanctioned users or wallets brings strict-liability OFAC civil penalties, often alongside AML enforcement.
- What to do when it's broken: Block activity for unscreened accounts, screen them now and report any blocked property to OFAC.
- Example reading used in demos: No

**4. State money transmitter licenses** (Must be in place, answered Yes or No; policy)

- Asks: Does the business hold a license, or a documented exemption, in every state where it serves customers?
- Rule: State money transmitter laws (policy; requirements vary by state); 18 U.S.C. 1960
- What a miss costs: Transmitting money without required state licenses brings cease-and-desist orders, state fines and federal criminal exposure under 18 U.S.C. 1960.
- What to do when it's broken: Stop onboarding customers in unlicensed states and apply for the license or confirm the exemption.
- Example reading used in demos: Yes

**5. FinCEN MSB registration current** (Must be in place, answered Yes or No)

- Asks: Is the business registered with FinCEN as a money services business (MSB), with renewal filed on its two-year cycle?
- Rule: 31 CFR 1022.380; 18 U.S.C. 1960
- What a miss costs: Operating as an unregistered MSB draws FinCEN civil penalties and is a federal crime.
- What to do when it's broken: File or renew the FinCEN MSB registration (Form 107) now.
- Example reading used in demos: Yes

**6. Customer identity verified** (Must be in place, answered Yes or No)

- Asks: Is each customer's identity verified under the AML program before the account can send or receive funds?
- Rule: 31 CFR 1022.210(d)(1)(i)(A)
- What a miss costs: Letting unverified customers transact is a core finding in crypto AML enforcement and leads to penalties and costly account lookbacks.
- What to do when it's broken: Restrict unverified accounts from transacting until identity verification is complete.
- Example reading used in demos: No

**7. Travel Rule for $3,000+ transmittals** (Must be in place, answered Yes or No)

- Asks: For transfers of $3,000 or more, is the required sender and recipient information recorded and passed to the next institution?
- Rule: 31 CFR 1010.410(e), (f)
- What a miss costs: Missing originator and beneficiary information on transmittals is a recurring FinCEN finding that draws civil penalties.
- What to do when it's broken: Hold qualifying transmittals until the required information is recorded and can be sent with the transfer.
- Example reading used in demos: Yes

**8. CTR for cash over $10,000** (Maximum 15 days, warns from 10 days; counts days since a date)

- Asks: Days since a cash transaction over $10,000 (or several on one day adding up to it), without filing a currency transaction report (CTR)
- Rule: 31 CFR 1022.310; 31 CFR 1010.311; 31 CFR 1010.306(a)(1)
- What a miss costs: Failing to file currency transaction reports draws FinCEN civil penalties and can support structuring charges.
- What to do when it's broken: File the CTR with FinCEN now.
- Example reading used in demos: 4 days

**9. Independent AML review** (Maximum 365 days, warns from 330 days; policy, a company can set its own limit; counts days since a date)

- Asks: Days since the last independent review of the AML program was completed
- Rule: 31 CFR 1022.210(d)(4) (frequency is risk-based; annual is a common policy setting)
- What a miss costs: A missing or stale independent review is a common exam finding that leads to FinCEN and state penalties and remediation orders.
- What to do when it's broken: Engage a qualified independent reviewer now and track the findings to closure.
- Example reading used in demos: 410 days

**10. BSA records kept five years** (Must be in place, answered Yes or No)

- Asks: Are BSA records (SARs, CTRs, transfer and identity records) kept for at least five years?
- Rule: 31 CFR 1010.430(d)
- What a miss costs: Destroyed or missing BSA records draw civil penalties and leave the business unable to defend itself in exams and investigations.
- What to do when it's broken: Stop any deletion of BSA records and set retention to at least five years.
- Example reading used in demos: Yes

### 34. MortgageArmor (Mortgage Lending)

**1. No unexplained lending disparities** (Must never happen, answered Yes or No)

- Asks: Has a fair lending review found pricing, underwriting or marketing disparities on a prohibited basis that remain unexplained?
- Rule: 15 U.S.C. 1691; 12 CFR 1002.4(a); Fair Housing Act 42 U.S.C. 3605
- What a miss costs: Pricing, underwriting or redlining disparities by race or other protected traits lead to DOJ and CFPB settlements with penalties and loan subsidy funds.
- What to do when it's broken: Investigate the disparity now, fix the policy causing it and review affected borrowers for remediation.
- Example reading used in demos: No

**2. No RESPA referral kickbacks** (Must never happen, answered Yes or No)

- Asks: Is anything of value given or received for referrals of settlement service business (including disguised marketing deals)?
- Rule: 12 U.S.C. 2607; 12 CFR 1024.14
- What a miss costs: Paying or taking anything of value for settlement service referrals brings CFPB penalties, disgorgement and class actions.
- What to do when it's broken: Stop the payments, end the arrangement and have counsel review any marketing services agreements.
- Example reading used in demos: No

**3. Loan Estimate in 3 business days** (Maximum 3 business days, warns from 2 business days; counts business days since a date)

- Asks: Business days since the application was received, without delivering or mailing the Loan Estimate
- Rule: 12 CFR 1026.19(e)(1)(iii)(A)
- What a miss costs: Late Loan Estimates are a leading exam finding and can force the lender to cover fee increases and pay borrower damages.
- What to do when it's broken: Deliver or mail the Loan Estimate today.
- Example reading used in demos: 2 business days

**4. Closing Disclosure 3 days before close** (Minimum 3 business days, warns from 3 business days)

- Asks: Business days between the consumer's receipt of the Closing Disclosure and the loan signing (consummation)
- Rule: 12 CFR 1026.19(f)(1)(ii)(A)
- What a miss costs: Closing before the waiting period ends is a TRID violation that forces delayed closings, cures and borrower damages.
- What to do when it's broken: Move the closing date so the consumer has the Closing Disclosure at least three business days before.
- Example reading used in demos: 2 business days

**5. No foreclosure before 120 days late** (Minimum 121 days, warns from 121 days)

- Asks: Days the loan will be delinquent on the date of the first foreclosure notice or filing (must be more than 120)
- Rule: 12 CFR 1024.41(f)(1)
- What a miss costs: Filing foreclosure too early violates Regulation X, bringing borrower lawsuits, CFPB penalties and wrongful foreclosure costs.
- What to do when it's broken: Do not file; wait until the loan is more than 120 days delinquent and check for pending loss mitigation.
- Example reading used in demos: 150 days

**6. Adverse action notice in 30 days** (Maximum 30 days, warns from 25 days; counts days since a date)

- Asks: Days since a completed application was denied or decided, without sending the adverse action notice
- Rule: 12 CFR 1002.9(a)(1)(i)
- What a miss costs: Missing or late adverse action notices are frequent exam findings and support ECOA lawsuits and CFPB enforcement.
- What to do when it's broken: Send the adverse action notice with the specific principal reasons now.
- Example reading used in demos: 31 days

**7. Loan originators licensed (NMLS)** (Must be in place, answered Yes or No)

- Asks: Is every loan originator state-licensed through NMLS, or federally registered, before taking applications?
- Rule: 12 U.S.C. 5103; 12 CFR Part 1007 and 1008
- What a miss costs: Unlicensed originators draw state fines and license actions, and loans they originate can face repurchase demands.
- What to do when it's broken: Stop the originator from taking applications until the license or registration is active in NMLS.
- Example reading used in demos: Yes

**8. Resolve notices of error** (Maximum 30 business days, warns from 25 business days; counts business days since a date)

- Asks: Business days since a notice of error was received, without correcting it or responding in writing
- Rule: 12 CFR 1024.35(e)(3)(i)(C) (30 business days for most errors; shorter for payoff and foreclosure errors)
- What a miss costs: Ignoring or slow-walking borrower error notices violates RESPA, bringing actual and statutory damages and CFPB enforcement.
- What to do when it's broken: Correct the error or send the written determination now.
- Example reading used in demos: 12 business days

**9. HMDA LAR filed by March 1** (Must be in place, answered Yes or No)

- Asks: Was last year's HMDA loan application register submitted accurately by March 1?
- Rule: 12 CFR 1003.5(a)(1)(i)
- What a miss costs: Late or inaccurate HMDA data draws civil money penalties and required resubmission.
- What to do when it's broken: Submit the LAR now and correct and resubmit any data errors.
- Example reading used in demos: Yes

**10. Flood insurance in flood zones** (Must be in place, answered Yes or No)

- Asks: For a property in a special flood hazard area, is required flood insurance in place at or before closing?
- Rule: 42 U.S.C. 4012a; 12 CFR 22.3 (OCC), 12 CFR 339.3 (FDIC), 12 CFR 208.25 (Fed)
- What a miss costs: Missing flood insurance on loans in special flood hazard areas brings civil money penalties per violation and uninsured flood losses.
- What to do when it's broken: Do not close until flood insurance is in place; send the borrower notice and force-place coverage if it lapses.
- Example reading used in demos: No

### 35. CollectArmor (Debt Collection)

**1. Consent for autodialed cell calls** (Must be in place, answered Yes or No)

- Asks: Is there prior express consent for every autodialed or prerecorded-voice call to a cell phone number?
- Rule: 47 U.S.C. 227(b)(1)(A)(iii); 47 CFR 64.1200(a)(1)
- What a miss costs: TCPA class actions carry statutory damages per call with no cap, so calls to cell phones without consent can bring very large judgments.
- What to do when it's broken: Stop autodialed and prerecorded calls to numbers without documented consent; dial them manually or not at all.
- Example reading used in demos: Yes

**2. Call frequency 7 in 7 days** (Maximum 7 calls, warns from 6 calls)

- Asks: Call attempts to the consumer about this debt in the last 7 days
- Rule: 12 CFR 1006.14(b)(2)(i)(A)
- What a miss costs: Calling more than the Reg F presumption allows supports FDCPA harassment claims, class actions and CFPB enforcement.
- What to do when it's broken: Stop calling on this debt until the 7-day window allows another attempt.
- Example reading used in demos: 6 calls

**3. Validation notice within 5 days** (Maximum 5 days, warns from 4 days; counts days since a date)

- Asks: Days since first contacting the consumer about the debt, without sending the validation notice
- Rule: 15 U.S.C. 1692g(a); 12 CFR 1006.34(a)(1)
- What a miss costs: A missing or late validation notice is a common FDCPA lawsuit claim and draws CFPB and state enforcement.
- What to do when it's broken: Send the validation notice now and pause collection until the validation period is set.
- Example reading used in demos: 7 days

**4. No calls before 8 a.m. or after 9 p.m.** (Must never happen, answered Yes or No)

- Asks: Were any calls placed before 8 a.m. or after 9 p.m. in the consumer's local time?
- Rule: 15 U.S.C. 1692c(a)(1); 12 CFR 1006.6(b)(1)(i)
- What a miss costs: Calls at inconvenient hours are an FDCPA violation that supports individual and class lawsuits.
- What to do when it's broken: Restrict the dialer to 8 a.m.-9 p.m. in the consumer's time zone, using all known time zones if unsure.
- Example reading used in demos: No

**5. No debt disclosure to third parties** (Must never happen, answered Yes or No)

- Asks: Was the debt discussed with anyone other than the consumer, their spouse or attorney, or another permitted party?
- Rule: 15 U.S.C. 1692c(b); 12 CFR 1006.6(d)(1)
- What a miss costs: Telling employers, family or others about a debt brings FDCPA lawsuits, privacy claims and regulator actions.
- What to do when it's broken: Stop the contact, retrain staff and review voicemail and letter templates that can reveal the debt.
- Example reading used in demos: Yes

**6. No suits on time-barred debt** (Must never happen, answered Yes or No)

- Asks: Has a lawsuit been filed, or threatened, on a debt past its statute of limitations?
- Rule: 12 CFR 1006.26(b)
- What a miss costs: Suing or threatening to sue on debt past the statute of limitations brings FDCPA liability, fee awards and enforcement.
- What to do when it's broken: Dismiss or withdraw the suit or threat, and flag the account as time-barred.
- Example reading used in demos: No

**7. Honor cease-communication requests** (Must never happen, answered Yes or No)

- Asks: Was the consumer contacted after a written cease-communication request, other than a permitted final notice?
- Rule: 15 U.S.C. 1692c(c); 12 CFR 1006.6(c)(1)
- What a miss costs: Contacting a consumer after a written request to stop is an FDCPA violation that supports lawsuits and enforcement.
- What to do when it's broken: Stop all contact on the account now except the notices the rule permits.
- Example reading used in demos: No

**8. Credit report disputes in 30 days** (Maximum 30 days, warns from 25 days; counts days since a date)

- Asks: Days since the credit reporting dispute was received, without completing the investigation
- Rule: 15 U.S.C. 1681s-2(b), 1681i(a)(1); 12 CFR 1022.43(e)
- What a miss costs: Failing to investigate credit reporting disputes brings FCRA lawsuits with actual, statutory and punitive damages and CFPB enforcement.
- What to do when it's broken: Finish the investigation now and correct or delete inaccurate data with every bureau it was reported to.
- Example reading used in demos: 26 days

**9. No credit reporting before contact** (Must never happen, answered Yes or No)

- Asks: Was the debt reported to a credit bureau before talking to the consumer, or before sending a notice and waiting to see if it came back undelivered?
- Rule: 12 CFR 1006.30(a)(1)
- What a miss costs: Reporting a debt before contacting the consumer (passive debt collection) violates Reg F and invites lawsuits and enforcement.
- What to do when it's broken: Pull the tradeline, contact the consumer, and wait a reasonable time (such as 14 days) for any undeliverable notice.
- Example reading used in demos: No

**10. State collection agency license** (Must be in place, answered Yes or No; policy)

- Asks: Does the agency hold a license, or a documented exemption, in every state where it collects from consumers?
- Rule: State collection agency licensing laws (policy; requirements vary by state)
- What a miss costs: Collecting without a required state license brings state fines, license denials and can void collections or support consumer suits.
- What to do when it's broken: Stop collecting from consumers in unlicensed states and apply for the license or confirm the exemption.
- Example reading used in demos: Yes

### 36. DefenseArmor (Defense Contractors)

**1. CUI safeguarded per NIST SP 800-171** (Must be in place, answered Yes or No)

- Asks: Do all company systems that process, store or send Controlled Unclassified Information (CUI) meet NIST SP 800-171, with any open gaps tracked in a current plan of action?
- Rule: DFARS 252.204-7012(b); NIST SP 800-171
- What a miss costs: Claiming cyber compliance that is not in place exposes the contractor to False Claims Act suits, lost awards and contract termination.
- What to do when it's broken: Stop representing full compliance; document gaps in a plan of action, fix them and correct any inaccurate SPRS score.
- Example reading used in demos: No

**2. Certified cost or pricing data** (Must be in place, answered Yes or No)

- Asks: For each negotiated contract or change over the TINA threshold, with no exception, was current, accurate and complete cost or pricing data submitted and certified?
- Rule: 10 U.S.C. 3702; FAR 15.403-4; FAR 52.215-10
- What a miss costs: Defective pricing data leads to government price reductions with interest, and knowing errors can bring False Claims Act liability.
- What to do when it's broken: Hold the price agreement; update the cost or pricing data to the agreed date and certify it before award.
- Example reading used in demos: Yes

**3. No ITAR export without authorization** (Must never happen, answered Yes or No)

- Asks: Has ITAR-controlled technical data or hardware been shared with a foreign person (including employees) without a DDTC license or exemption?
- Rule: 22 CFR 123.1; 22 CFR 125.2; 22 CFR 127.1
- What a miss costs: Unlicensed exports of defense articles or technical data draw civil penalties, consent agreements, debarment from exports and criminal charges.
- What to do when it's broken: Stop further access, preserve records and consider a voluntary disclosure to DDTC under 22 CFR 127.12 with export counsel.
- Example reading used in demos: No

**4. Mandatory disclosure made** (Must never happen, answered Yes or No)

- Asks: Is there credible evidence of contract-related fraud, bribery, conflict of interest, gratuity or False Claims Act violations not yet disclosed?
- Rule: FAR 52.203-13(b)(3)(i); FAR 9.406-2(b)(1)(vi)
- What a miss costs: Failing to disclose credible evidence of fraud or False Claims Act violations is a cause for suspension and debarment from federal contracts.
- What to do when it's broken: Disclose in writing to the agency Office of Inspector General now, with a copy to the contracting officer.
- Example reading used in demos: No

**5. CMMC level required by contract** (Must be in place, answered Yes or No)

- Asks: Does the company hold a current CMMC status, at the level the solicitation or contract requires, for each system handling federal contract information (FCI) or CUI?
- Rule: 32 CFR Part 170; DFARS 252.204-7021
- What a miss costs: Without the CMMC status the contract requires, the company is ineligible for award and can lose new work and options.
- What to do when it's broken: Do not bid or process FCI/CUI on the system; complete the required CMMC assessment and affirmation.
- Example reading used in demos: Yes

**6. SPRS assessment current** (Maximum 1,095 days, warns from 1,005 days; counts days since a date)

- Asks: Days since the NIST SP 800-171 assessment score was posted in SPRS
- Rule: DFARS 252.204-7019; DFARS 252.204-7020
- What a miss costs: Without a current NIST SP 800-171 assessment in SPRS, the contractor cannot be awarded contracts that require one.
- What to do when it's broken: Perform a new NIST SP 800-171 assessment and post the score and summary in SPRS now.
- Example reading used in demos: 1,030 days

**7. Cyber incident reported to DoD** (Maximum 72 h, warns from 48 h; counts hours since a date and time)

- Asks: Hours since the cyber incident affecting covered defense information was discovered, without reporting to DoD
- Rule: DFARS 252.204-7012(c)(1)
- What a miss costs: Late cyber incident reports breach DFARS clauses, can support termination or False Claims Act claims, and hurt past performance.
- What to do when it's broken: Report now at dibnet.dod.mil with a medium assurance certificate and preserve images of affected systems for 90 days.
- Example reading used in demos: 80 h

**8. No prohibited telecom equipment** (Must never happen, answered Yes or No)

- Asks: Is any covered telecommunications or video surveillance equipment or service used or provided by the company?
- Rule: FAR 52.204-25; FAR 52.204-24
- What a miss costs: Using or supplying covered Huawei, ZTE, Hytera, Hikvision or Dahua telecom or video gear breaches FAR clauses and risks contract loss.
- What to do when it's broken: Report it to the contracting officer within one business day and plan removal or replacement of the equipment.
- Example reading used in demos: No

**9. Counterfeit parts detection system** (Must be in place, answered Yes or No)

- Asks: Does the company run a counterfeit electronic part detection and avoidance system and buy parts from original makers or authorized sources?
- Rule: DFARS 252.246-7007; DFARS 252.246-7008; DFARS 231.205-71
- What a miss costs: Counterfeit electronic parts make rework and replacement costs unallowable and can lead to purchasing system disapproval and withholds.
- What to do when it's broken: Quarantine suspect parts, report them to the contracting officer and GIDEP, and fix sourcing and inspection procedures.
- Example reading used in demos: Yes

**10. DDTC ITAR registration current** (Minimum 0 days, warns from 60 days; counts days until a date)

- Asks: Days until the company's DDTC registration expires
- Rule: 22 CFR 122.1; 22 CFR 122.3
- What a miss costs: Manufacturing or exporting defense articles without a current DDTC registration is an ITAR violation and blocks license approvals.
- What to do when it's broken: Submit the registration renewal and fee in DECCS now; do not export until the registration is current.
- Example reading used in demos: 45 days

### 37. FoodArmor (Food Manufacturing)

**1. Environmental pathogen monitoring** (Must be in place, answered Yes or No)

- Asks: For ready-to-eat food exposed to the plant environment before packaging, is the environment tested for pathogens, with results recorded and acted on?
- Rule: 21 CFR 117.165(a)(3); 21 CFR 117.150
- What a miss costs: Listeria or Salmonella in ready-to-eat food leads to recalls, outbreak lawsuits, plant shutdowns and FDA warning letters.
- What to do when it's broken: Start swabbing food-contact and nearby zones now, hold affected product and document corrective actions.
- Example reading used in demos: Yes

**2. No undeclared major allergens** (Must never happen, answered Yes or No)

- Asks: Does any label omit a major allergen the product contains (milk, egg, fish, shellfish, tree nuts, peanuts, wheat, soy, sesame)?
- Rule: 21 U.S.C. 343(w) (FD&C Act 403(w), FALCPA and FASTER Act)
- What a miss costs: Undeclared allergens are a common cause of food recalls and bring lost product, retailer chargebacks and injury lawsuits.
- What to do when it's broken: Stop shipping, hold and relabel the product, and assess whether a recall and a Reportable Food Registry report are needed.
- Example reading used in demos: Yes

**3. Written food safety plan by a PCQI** (Must be in place, answered Yes or No)

- Asks: Does the facility have a written food safety plan prepared or overseen by a preventive controls qualified individual (PCQI)?
- Rule: 21 CFR 117.126; 21 CFR 117.180
- What a miss costs: Operating without a written food safety plan is a common FDA warning letter finding and can lead to registration suspension.
- What to do when it's broken: Have a PCQI prepare the hazard analysis and written food safety plan now and review production against it.
- Example reading used in demos: Yes

**4. Pests excluded from the plant** (Must never happen, answered Yes or No)

- Asks: Has pest activity been found in any food handling, processing or storage area and not yet corrected?
- Rule: 21 CFR 117.35(c); 21 U.S.C. 342(a)(4)
- What a miss costs: Pest activity makes food adulterated under insanitary conditions, bringing warning letters, product destruction and shutdowns.
- What to do when it's broken: Hold exposed product, call pest control, seal entry points and document cleaning and corrective action.
- Example reading used in demos: No

**5. Reportable food reported in 24 h** (Maximum 24 h, warns from 18 h; counts hours since a date and time)

- Asks: Hours since determining a food is a reportable food, without submitting a Reportable Food Registry report
- Rule: 21 U.S.C. 350f(d)(1) (FD&C Act 417)
- What a miss costs: Late Reportable Food Registry reports are a prohibited act under the FD&C Act and increase recall scope and outbreak liability.
- What to do when it's broken: Submit the report through the FDA Safety Reporting Portal now and investigate the cause.
- Example reading used in demos: 6 h

**6. Supplier verification in place** (Must be in place, answered Yes or No)

- Asks: For each ingredient whose hazard the supplier controls, is the supplier approved and verified (for example, audits, sampling, records review)?
- Rule: 21 CFR 117.410; 21 CFR 117.430
- What a miss costs: Using unverified suppliers for hazards they control is cited in FDA inspections and passes contaminated ingredients into product.
- What to do when it's broken: Hold the ingredient; approve the supplier and complete and document a verification activity before use.
- Example reading used in demos: No

**7. Food safety plan reanalysis** (Maximum 1,095 days, warns from 1,000 days; counts days since a date)

- Asks: Days since the last full reanalysis of the food safety plan
- Rule: 21 CFR 117.170(a)
- What a miss costs: An outdated food safety plan is cited in FDA inspections and leaves new hazards uncontrolled, raising recall risk.
- What to do when it's broken: Have a PCQI reanalyze the whole food safety plan now and document the result.
- Example reading used in demos: 1,150 days

**8. Written recall plan** (Must be in place, answered Yes or No)

- Asks: For food with a hazard requiring a preventive control, is there a written recall plan with steps and assigned responsibilities?
- Rule: 21 CFR 117.139
- What a miss costs: Without a recall plan, recalls are slower and wider, raising product losses, retailer costs and liability.
- What to do when it's broken: Write the recall plan now, covering notice to consignees, the public, effectiveness checks and disposal.
- Example reading used in demos: Yes

**9. Foreign supplier verification (FSVP)** (Must be in place, answered Yes or No)

- Asks: As the importer, does the company have a Foreign Supplier Verification Program (FSVP) for each imported food and foreign supplier?
- Rule: 21 CFR 1.502; 21 CFR Part 1 Subpart L
- What a miss costs: Importing without an FSVP draws FDA warning letters and import alerts that stop shipments at the border.
- What to do when it's broken: Do not import the food; develop the FSVP hazard analysis and supplier verification for it first.
- Example reading used in demos: Yes

**10. FDA facility registration renewed** (Must be in place, answered Yes or No)

- Asks: Was the FDA food facility registration renewed in the most recent October 1 to December 31 even-year renewal period?
- Rule: 21 CFR 1.230(b); 21 U.S.C. 350d
- What a miss costs: Food from a facility that failed to register or renew is a prohibited act, and imports from it are held at the port.
- What to do when it's broken: Renew or re-register the facility in FDA's FURLS system now.
- Example reading used in demos: Yes

### 38. DeviceArmor (Medical Devices)

**1. CAPA process working** (Must be in place, answered Yes or No)

- Asks: Are quality problems investigated to root cause, with corrective and preventive actions documented and verified as effective?
- Rule: 21 CFR 820.10 (ISO 13485:2016 clauses 8.5.2, 8.5.3)
- What a miss costs: CAPA failures are frequently cited FDA inspection findings and lead to warning letters, import holds and consent decrees.
- What to do when it's broken: Open CAPAs for the open quality problems, find root causes, fix them and verify effectiveness in writing.
- Example reading used in demos: No

**2. 510(k) or PMA before marketing** (Must never happen, answered Yes or No)

- Asks: Is any device, or significant change to a device, being sold without the FDA clearance or approval it needs (510(k), De Novo or PMA)?
- Rule: 21 U.S.C. 360(k); 21 CFR 807.81; 21 U.S.C. 360e; 21 CFR Part 814
- What a miss costs: Selling a device or changed device without required clearance or approval makes it adulterated and misbranded, risking seizure and recall.
- What to do when it's broken: Stop distributing the device and file the required submission; consult regulatory counsel on product in the field.
- Example reading used in demos: No

**3. Complaints handled and evaluated** (Must be in place, answered Yes or No)

- Asks: Is every complaint recorded, checked for whether it must be reported to FDA (MDR), and investigated where needed, with records kept?
- Rule: 21 CFR 820.10 (ISO 13485:2016 clause 8.2.2); 21 CFR 820.35(a)
- What a miss costs: Weak complaint handling is a top FDA inspection finding, hides reportable events and leads to warning letters and recalls.
- What to do when it's broken: Log and review all open complaints now, document the MDR decision for each and start needed investigations.
- Example reading used in demos: Yes

**4. MDR report within 30 days** (Maximum 30 days, warns from 25 days; counts days since a date)

- Asks: Calendar days since becoming aware of a reportable death, serious injury or malfunction, without filing a medical device report (MDR)
- Rule: 21 CFR 803.50(a)
- What a miss costs: Late or missing Medical Device Reports are cited in warning letters and can support civil money penalties and misbranding charges.
- What to do when it's broken: File the MDR (Form 3500A) through eMDR now and document why it was late.
- Example reading used in demos: 27 days

**5. Design controls followed** (Must be in place, answered Yes or No)

- Asks: For each device under design controls, are design inputs, verification, validation and risk management complete before transfer?
- Rule: 21 CFR 820.10 (ISO 13485:2016 clause 7.3)
- What a miss costs: Design control gaps lead to warning letters, field failures and recalls of devices already sold.
- What to do when it's broken: Hold design transfer until design verification, validation and risk analysis are complete and approved.
- Example reading used in demos: Yes

**6. Suppliers evaluated and controlled** (Must be in place, answered Yes or No)

- Asks: Are all suppliers of product and services evaluated, approved, monitored and bound by documented purchasing requirements?
- Rule: 21 CFR 820.10 (ISO 13485:2016 clause 7.4)
- What a miss costs: Uncontrolled suppliers let defective components into devices, leading to recalls, warning letters and production stops.
- What to do when it's broken: Hold incoming parts from unapproved suppliers; evaluate and approve them and document purchasing requirements.
- Example reading used in demos: No

**7. Correction or removal reported** (Maximum 10 working days, warns from 8 working days; counts business days since a date)

- Asks: Working days since starting a correction or removal to reduce a health risk, without reporting it to FDA
- Rule: 21 CFR 806.10(b)
- What a miss costs: Unreported corrections and removals to reduce health risk make devices misbranded and draw warning letters.
- What to do when it's broken: Submit the Part 806 correction or removal report to FDA now.
- Example reading used in demos: 3 working days

**8. 5-day MDR report** (Maximum 5 work days, warns from 4 work days; counts business days since a date)

- Asks: Work days since becoming aware of an event that needs action to prevent substantial harm (or of an FDA request for a 5-day report), without reporting
- Rule: 21 CFR 803.53
- What a miss costs: Missing a 5-day report on an event needing remedial action is cited in warning letters and can support civil money penalties.
- What to do when it's broken: File the 5-day MDR report through eMDR now.
- Example reading used in demos: 6 work days

**9. Annual registration and listing** (Must be in place, answered Yes or No)

- Asks: Was the FDA establishment registration renewed (with the user fee paid) and the device listing reviewed between October 1 and December 31 last year?
- Rule: 21 CFR 807.22(b); 21 U.S.C. 360
- What a miss costs: Devices from an unregistered or unlisted establishment are misbranded and can be refused at import or held from sale.
- What to do when it's broken: Pay the registration user fee and complete registration and listing in FURLS now.
- Example reading used in demos: Yes

**10. UDI on labels and in GUDID** (Must be in place, answered Yes or No)

- Asks: Does each device label and package carry a unique device identifier (UDI), with device data sent to FDA's GUDID database, unless an exception applies?
- Rule: 21 CFR 801.20; 21 CFR 830.300
- What a miss costs: Devices without a required UDI or GUDID record are misbranded and can be refused by hospitals, distributors and at import.
- What to do when it's broken: Stop shipping unlabeled units; apply UDIs and submit the GUDID records.
- Example reading used in demos: Yes

### 39. ChemArmor (Chemical Plants)

**1. No overdue equipment inspections** (Must never happen, answered Yes or No)

- Asks: Is any covered process equipment overdue for an inspection or test set by the manufacturer or good engineering practice?
- Rule: 29 CFR 1910.119(j)(4); 40 CFR 68.73
- What a miss costs: Mechanical integrity failures cause fires and explosions and are frequently cited PSM items, bringing OSHA and EPA penalties.
- What to do when it's broken: Perform the overdue inspections and tests now; correct deficiencies before further use or add interim safeguards.
- Example reading used in demos: Yes

**2. PHA revalidated every 5 years** (Maximum 1,825 days, warns from 1,640 days; counts days since a date)

- Asks: Days since the process hazard analysis for this process was last updated and revalidated
- Rule: 29 CFR 1910.119(e)(6); 40 CFR 68.67(f)
- What a miss costs: Out-of-date process hazard analyses are a frequent PSM and RMP citation and leave hazards unaddressed before incidents.
- What to do when it's broken: Schedule the PHA revalidation with a qualified team now and track recommendations to closure.
- Example reading used in demos: 1,700 days

**3. Management of change completed** (Must be in place, answered Yes or No)

- Asks: Was every change to process chemicals, technology, equipment or procedures reviewed under written management of change before startup?
- Rule: 29 CFR 1910.119(l); 40 CFR 68.75
- What a miss costs: Unreviewed process changes are a common cause of chemical incidents and draw PSM citations and incident liability.
- What to do when it's broken: Stop using the changed process until the MOC review, pre-startup safety review and training are complete.
- Example reading used in demos: No

**4. RMP updated every 5 years** (Maximum 1,825 days, warns from 1,640 days; counts days since a date)

- Asks: Days since the risk management plan was last updated and resubmitted to EPA
- Rule: 40 CFR 68.190(b)(1)
- What a miss costs: An outdated risk management plan is an EPA Clean Air Act violation that leads to civil penalties and consent agreements.
- What to do when it's broken: Update the RMP, including hazard review and emergency response data, and resubmit it through RMP*eSubmit now.
- Example reading used in demos: 900 days

**5. PSM compliance audit every 3 years** (Maximum 1,095 days, warns from 1,000 days; counts days since a date)

- Asks: Days since the last process safety management (PSM) compliance audit was certified
- Rule: 29 CFR 1910.119(o)(1); 40 CFR 68.79(a)
- What a miss costs: Missed compliance audits are cited by OSHA and EPA and let program gaps grow unnoticed until an incident.
- What to do when it's broken: Schedule and certify a PSM compliance audit now and respond to findings in writing.
- Example reading used in demos: 1,120 days

**6. SDS available for every chemical** (Must be in place, answered Yes or No)

- Asks: Is a current safety data sheet for every hazardous chemical readily accessible to employees in their work area on every shift?
- Rule: 29 CFR 1910.1200(g)(8)
- What a miss costs: Hazard communication is frequently cited by OSHA, and missing SDSs draw citations and worker injury claims.
- What to do when it's broken: Get missing SDSs from suppliers and place them where workers on every shift can reach them.
- Example reading used in demos: Yes

**7. Tier II report filed by March 1** (Must be in place, answered Yes or No)

- Asks: Was the Tier II chemical inventory for last year sent to the state and local emergency planning bodies (SERC and LEPC) and the local fire department by March 1?
- Rule: 40 CFR 370.45
- What a miss costs: Missing or late EPCRA Tier II reports draw EPA civil penalties and leave fire departments unaware of stored hazards.
- What to do when it's broken: File the Tier II report with the SERC, LEPC and fire department now.
- Example reading used in demos: Yes

**8. TRI Form R filed by July 1** (Must be in place, answered Yes or No)

- Asks: Was each required TRI Form R (or Form A) for last calendar year submitted to EPA by July 1?
- Rule: 40 CFR 372.30
- What a miss costs: Failing to file Toxics Release Inventory reports is an EPCRA violation that draws EPA civil penalties for each chemical and year.
- What to do when it's broken: Prepare and submit the missing TRI reports through TRI-MEweb now.
- Example reading used in demos: No

**9. SPCC plan 5-year review** (Maximum 1,825 days, warns from 1,640 days; counts days since a date)

- Asks: Days since the last documented review and evaluation of the SPCC plan
- Rule: 40 CFR 112.5(b)
- What a miss costs: An unreviewed spill prevention plan is a Clean Water Act violation cited by EPA and raises cleanup costs after a spill.
- What to do when it's broken: Complete and document the SPCC plan review now and amend the plan within 6 months if changes are needed.
- Example reading used in demos: 600 days

**10. DOT hazmat training every 3 years** (Maximum 1,095 days, warns from 1,000 days; counts days since a date)

- Asks: Days since the employee's last DOT hazmat training (general, function-specific, safety and security)
- Rule: 49 CFR 172.704(c)(2)
- What a miss costs: Untrained hazmat employees draw DOT civil penalties per violation and raise the risk of shipping incidents.
- What to do when it's broken: Keep the employee off hazmat work until recurrent training is completed and recorded.
- Example reading used in demos: 1,010 days

### 40. WasteArmor (Hazardous Waste)

**1. LQG 90-day accumulation limit** (Maximum 90 days, warns from 80 days; counts days since a date)

- Asks: Days since this hazardous waste began accumulating in the central accumulation area (the start date on its label)
- Rule: 40 CFR 262.17(a)
- What a miss costs: Holding waste past 90 days makes a large quantity generator an unpermitted storage facility, bringing large RCRA penalties.
- What to do when it's broken: Ship the waste to a permitted facility now, or request an extension from the regulator if allowed.
- Example reading used in demos: 95 days

**2. Hazardous waste determination made** (Must be in place, answered Yes or No)

- Asks: Has a hazardous waste determination been made and recorded for every solid waste the site generates?
- Rule: 40 CFR 262.11
- What a miss costs: Skipping waste determinations is a top RCRA citation and leads to illegal disposal, penalties and cleanup liability.
- What to do when it's broken: Characterize the waste now by knowledge or testing, record the result and manage it as hazardous until done.
- Example reading used in demos: No

**3. Manifested shipments only** (Must never happen, answered Yes or No)

- Asks: Has any hazardous waste left the site without a manifest, or with a transporter or facility lacking an EPA ID number?
- Rule: 40 CFR 262.20(a); 40 CFR 262.18(c)
- What a miss costs: Shipping waste without a manifest or to an unpermitted site brings RCRA penalties and cleanup liability for where it ends up.
- What to do when it's broken: Find the shipment, confirm where it went, and report to the regulator; use only manifests and EPA ID holders.
- Example reading used in demos: No

**4. Containers marked and dated** (Must be in place, answered Yes or No)

- Asks: Is every container in the central accumulation area marked 'Hazardous Waste', with its hazards and accumulation start date?
- Rule: 40 CFR 262.17(a)(5)
- What a miss costs: Unlabeled or undated containers are frequently cited RCRA violations and can cost the generator its accumulation exemption.
- What to do when it's broken: Label each container with 'Hazardous Waste', its hazards and the start date now.
- Example reading used in demos: Yes

**5. Weekly container area inspection** (Maximum 7 days, warns from 6 days; counts days since a date)

- Asks: Days since the last recorded inspection of the central accumulation area
- Rule: 40 CFR 262.17(a)(1)(v)
- What a miss costs: Missed weekly inspections are frequently cited in RCRA inspections and let leaks go unnoticed until cleanup is needed.
- What to do when it's broken: Inspect the area for leaks and deterioration today and record the inspection.
- Example reading used in demos: 9 days

**6. Satellite area 55-gallon limit** (Maximum 55 gal, warns from 50 gal)

- Asks: Gallons of non-acute hazardous waste at this satellite accumulation area
- Rule: 40 CFR 262.15(a)
- What a miss costs: Exceeding satellite limits is a common RCRA citation and turns the area into one that must meet full storage rules.
- What to do when it's broken: Date the excess and move it to the central accumulation area within 3 calendar days in a row.
- Example reading used in demos: 40 gal

**7. SQG 180-day accumulation limit** (Maximum 180 days, warns from 160 days; counts days since a date)

- Asks: Days since this hazardous waste began accumulating on site (180-day limit; 270 days only if the waste facility it goes to is over 200 miles away)
- Rule: 40 CFR 262.16(b)(1); 40 CFR 262.16(d)
- What a miss costs: Holding waste past the limit makes a small quantity generator an unpermitted storage facility subject to RCRA penalties.
- What to do when it's broken: Ship the waste to a permitted facility now, or request an extension from the regulator if allowed.
- Example reading used in demos: 165 days

**8. Annual RCRA training review** (Maximum 365 days, warns from 335 days; counts days since a date)

- Asks: Days since the employee's last annual review of hazardous waste training
- Rule: 40 CFR 262.17(a)(7)(iii)
- What a miss costs: Missing training records are a common RCRA citation and untrained staff mishandle waste, raising spill and penalty risk.
- What to do when it's broken: Complete the annual training review with the employee now and record it.
- Example reading used in demos: 200 days

**9. Manifest exception report** (Maximum 45 days, warns from 35 days; counts days since a date)

- Asks: Days since the first transporter took the waste, without getting back the signed manifest copy from the destination facility
- Rule: 40 CFR 262.42(a)
- What a miss costs: Not following up on unconfirmed shipments is a RCRA violation and leaves the generator liable if waste is misdelivered.
- What to do when it's broken: Contact the transporter and facility, and file an exception report with the EPA Region or state now.
- Example reading used in demos: 20 days

**10. Biennial report filed by March 1** (Must be in place, answered Yes or No)

- Asks: If the site was a large quantity generator in any month of the last odd year, was its biennial report filed by March 1?
- Rule: 40 CFR 262.41(a)
- What a miss costs: Missing biennial reports is a RCRA reporting violation that draws penalties and triggers closer inspection.
- What to do when it's broken: Prepare and file the biennial hazardous waste report through RCRAInfo now.
- Example reading used in demos: Yes

### 41. GridArmor (Electric Utilities)

**1. Security patch evaluation cycle** (Maximum 35 days, warns from 28 days; counts days since a date)

- Asks: Days since security patches were last checked for whether they apply
- Rule: NERC CIP-007 R2.2
- What a miss costs: Late patch evaluations are frequently cited CIP violations and draw NERC civil penalties and mitigation plans.
- What to do when it's broken: Evaluate all released security patches now and document the result for each applicable BES Cyber Asset.
- Example reading used in demos: 38 days

**2. Access removed after termination** (Maximum 24 h, warns from 16 h; counts hours since a date and time)

- Asks: Hours since a person was let go, without removing their unescorted physical access and Interactive Remote Access
- Rule: NERC CIP-004 R5.1
- What a miss costs: Former staff who keep unescorted physical or remote access are a frequent CIP finding that draws NERC penalties.
- What to do when it's broken: Remove the person's badge access and Interactive Remote Access now and record the time removed.
- Example reading used in demos: 6 h

**3. Vegetation inside clearance distance** (Must never happen, answered Yes or No)

- Asks: Has vegetation been found closer to a covered line than its Minimum Vegetation Clearance Distance?
- Rule: NERC FAC-003
- What a miss costs: Vegetation encroachment on covered transmission lines can cause outages and draws some of the largest NERC penalties.
- What to do when it's broken: Dispatch crews to clear the encroachment, notify the Reliability Coordinator if required, and log the event.
- Example reading used in demos: No

**4. 1-hour cyber incident notice** (Maximum 1 h, warns from 0.5 h; counts hours since a date and time)

- Asks: Hours since a Reportable Cyber Security Incident was determined, without notice to E-ISAC and CISA
- Rule: NERC CIP-008 R4.2
- What a miss costs: Missing the notice deadline for a reportable cyber incident is a CIP-008 violation that draws NERC penalties and scrutiny.
- What to do when it's broken: Send the initial notification to E-ISAC and CISA now with the attributes known so far.
- Example reading used in demos: 0.25 h

**5. Configuration baseline updated** (Maximum 30 days, warns from 21 days; counts days since a date)

- Asks: Days since a change that differs from the approved baseline configuration, without updating the baseline
- Rule: NERC CIP-010 R1.3
- What a miss costs: Out-of-date baselines are a common CIP-010 finding that leads to NERC penalties and costly re-baselining.
- What to do when it's broken: Update the baseline configuration for the changed asset and record the authorization for the change.
- Example reading used in demos: 24 days

**6. Protection system maintenance** (Must be in place, answered Yes or No)

- Asks: Is every Protection System component within its maximum maintenance interval in the PRC-005 tables?
- Rule: NERC PRC-005
- What a miss costs: Overdue relay, battery and communication tests are a frequent PRC-005 finding and can lead to misoperations and penalties.
- What to do when it's broken: Schedule the overdue component tests now and document completion against the program's interval tables.
- Example reading used in demos: No

**7. CIP security training current** (Maximum 15 months, warns from 13 months)

- Asks: Months since the person with authorized access last completed the cyber security training program
- Rule: NERC CIP-004 R2.3
- What a miss costs: Staff with authorized access and lapsed training are a common CIP-004 finding that draws NERC penalties.
- What to do when it's broken: Complete the training now or suspend the person's authorized access until it is done.
- Example reading used in demos: 14 months

**8. BES Cyber System review** (Maximum 15 months, warns from 13 months)

- Asks: Months since BES Cyber System identifications were reviewed and approved by the CIP Senior Manager
- Rule: NERC CIP-002 R2
- What a miss costs: A missed review of BES Cyber System identifications is a CIP-002 violation that can leave assets without required controls.
- What to do when it's broken: Review the impact ratings and have the CIP Senior Manager or delegate approve them now.
- Example reading used in demos: 9 months

**9. Cyber security policy approval** (Maximum 15 months, warns from 13 months)

- Asks: Months since the CIP Senior Manager last reviewed and approved the cyber security policies
- Rule: NERC CIP-003 R1
- What a miss costs: Policies not reviewed and approved on time are a CIP-003 violation that NERC auditors cite and penalize.
- What to do when it's broken: Have the CIP Senior Manager review and approve the documented cyber security policies now.
- Example reading used in demos: 16 months

**10. Reportable event filed in 24 h** (Maximum 24 h, warns from 18 h; counts hours since a date and time)

- Asks: Hours since recognizing an EOP-004 reportable event without submitting the report
- Rule: NERC EOP-004 R2 and Attachment 1
- What a miss costs: Late reports of reportable events such as physical attacks or load loss are an EOP-004 violation that draws penalties.
- What to do when it's broken: Submit the EOP-004 Attachment 2 or DOE OE-417 form to the required parties now.
- Example reading used in demos: 3 h

### 42. WaterArmor (Water Utilities)

**1. Lead 90th percentile action level** (Maximum 15 ppb, warns from 12 ppb)

- Asks: 90th percentile lead level from the latest round of tap samples
- Rule: 40 CFR 141.80(c) (current 15 ppb action level)
- What a miss costs: A lead action level exceedance triggers public education, treatment changes and lead service line replacement, plus lawsuits.
- What to do when it's broken: Notify the state, start public education within the required time, and begin the required treatment steps.
- Example reading used in demos: 13 ppb

**2. Tier 1 notice within 24 hours** (Maximum 24 h, warns from 12 h; counts hours since a date and time)

- Asks: Hours since learning of a Tier 1 violation or situation without issuing public notice
- Rule: 40 CFR 141.202(b)
- What a miss costs: Late notice of acute risks such as E. coli or a boil-water event brings state enforcement, penalties and liability suits.
- What to do when it's broken: Issue public notice now by broadcast or hand delivery and consult the state primacy agency.
- Example reading used in demos: 30 h

**3. Repeat samples after TC-positive** (Maximum 24 h, warns from 16 h; counts hours since a date and time)

- Asks: Hours since notice of a total coliform-positive routine sample without collecting the repeat samples
- Rule: 40 CFR 141.858(a)
- What a miss costs: Missing repeat samples after a total coliform-positive result is a violation that can trigger assessments and public notice.
- What to do when it's broken: Collect at least three repeat samples now at the required locations and have them tested.
- Example reading used in demos: 8 h

**4. Residual entering distribution** (Minimum 0.2 mg/L, warns from 0.3 mg/L)

- Asks: Lowest disinfectant level left (residual) in water entering the distribution system
- Rule: 40 CFR 141.72 (surface water systems)
- What a miss costs: Low disinfectant residual at the entry point is a treatment technique violation that requires public notice and enforcement.
- What to do when it's broken: Raise the disinfectant dose now; the residual may not stay below 0.2 mg/L for more than 4 hours. Notify the state.
- Example reading used in demos: 0.45 mg/L

**5. Filtered water turbidity** (Maximum 1 NTU, warns from 0.3 NTU)

- Asks: Highest cloudiness (turbidity) reading of the combined filtered water this month
- Rule: 40 CFR 141.173(a) (conventional or direct filtration)
- What a miss costs: A combined filter effluent turbidity spike is a treatment technique violation that can require public notice and a boil order.
- What to do when it's broken: Take the filter offline or adjust treatment now, consult the state, and prepare public notice.
- Example reading used in demos: 0.2 NTU

**6. NPDES permit effluent limit** (Maximum 100%, warns from 90%)

- Asks: Highest discharge result this period, as a percent of its NPDES permit limit
- Rule: 40 CFR 122.41(a); Clean Water Act 309
- What a miss costs: Discharges over permit limits bring Clean Water Act penalties, consent decrees and citizen suits.
- What to do when it's broken: Report the exceedance as the permit requires, find the cause, and adjust treatment before the next sample.
- Example reading used in demos: 104%

**7. Discharge Monitoring Report on time** (Must be in place, answered Yes or No)

- Asks: Were all Discharge Monitoring Reports for the last period submitted by the permit's due date?
- Rule: 40 CFR 122.41(l)(4); 40 CFR Part 127 (electronic reporting)
- What a miss costs: Late or missing DMRs are among the most common NPDES violations and lead to enforcement and penalties.
- What to do when it's broken: Submit the missing DMR electronically now and explain the delay to the permitting authority.
- Example reading used in demos: Yes

**8. Consumer Confidence Report by July 1** (Must be in place, answered Yes or No)

- Asks: Was this year's Consumer Confidence Report delivered to customers by July 1?
- Rule: 40 CFR 141.152(b)
- What a miss costs: A late or missing annual water quality report is a reporting violation that requires public notice and draws enforcement.
- What to do when it's broken: Deliver the report to customers now and send the state the certification of delivery.
- Example reading used in demos: No

**9. AWIA risk and resilience review** (Maximum 60 months, warns from 54 months)

- Asks: Months since the risk and resilience assessment was last reviewed and certified to EPA
- Rule: SDWA 1433(a) (42 U.S.C. 300i-2)
- What a miss costs: Systems serving over 3,300 people that miss the 5-year review and certification face EPA enforcement.
- What to do when it's broken: Complete the review, certify it to EPA, and update the emergency response plan within 6 months.
- Example reading used in demos: 56 months

**10. Certified operator in charge** (Must be in place, answered Yes or No; policy)

- Asks: Is the treatment plant and distribution system under an operator holding the certification grade the state requires?
- Rule: State operator certification rules under SDWA 1419 (42 U.S.C. 300g-8) (vary by state)
- What a miss costs: Running a plant without an operator of the required certification grade draws state penalties and weakens defense after incidents.
- What to do when it's broken: Assign a properly certified operator now and notify the state of the change.
- Example reading used in demos: Yes

### 43. LawArmor (Law Firms)

**1. Limitations deadlines docketed** (Must be in place, answered Yes or No; policy)

- Asks: Is every open matter's statute of limitations and court deadline entered in the firm's calendar (docket) with reminders?
- Rule: ABA Model Rule 1.3 (state versions vary); docketing is firm policy
- What a miss costs: Missed statutes of limitations and court deadlines are a common cause of malpractice claims and discipline.
- What to do when it's broken: Enter the missing deadlines now, have a second person verify them, and set advance reminders.
- Example reading used in demos: No

**2. Three-way trust reconciliation** (Maximum 31 days, warns from 25 days; policy, a company can set its own limit; counts days since a date)

- Asks: Days since the last three-way reconciliation of the client trust account (bank statement, trust ledger and client ledgers)
- Rule: ABA Model Rule 1.15 (state versions vary; monthly is common)
- What a miss costs: Unreconciled trust accounts hide shortfalls that lead to disbarment, restitution and client security fund claims.
- What to do when it's broken: Reconcile the bank statement, trust ledger and client ledgers now and fix any difference.
- Example reading used in demos: 27 days

**3. No commingling of client funds** (Must never happen, answered Yes or No; policy)

- Asks: Are any firm funds (beyond allowed bank fees) held in trust, or any client funds held in a firm account?
- Rule: ABA Model Rule 1.15(a) (state versions vary)
- What a miss costs: Mixing firm and client money is a common cause of lawyer discipline, including suspension and disbarment.
- What to do when it's broken: Move the funds to the correct account now and document each transfer in the ledger.
- Example reading used in demos: No

**4. Conflict check before engagement** (Must be in place, answered Yes or No; policy)

- Asks: Was a conflict check run on the client and all adverse parties before accepting the matter?
- Rule: ABA Model Rules 1.7, 1.9 and 1.10 (state versions vary)
- What a miss costs: Unchecked conflicts lead to disqualification, fee forfeiture and malpractice claims.
- What to do when it's broken: Stop work on the matter and run the conflict check before doing anything further.
- Example reading used in demos: Yes

**5. Conflict waiver confirmed in writing** (Must be in place, answered Yes or No; policy)

- Asks: For each waived conflict, is the client's informed consent confirmed in writing?
- Rule: ABA Model Rule 1.7(b)(4) (state versions vary)
- What a miss costs: A waiver not confirmed in writing may be unenforceable, risking disqualification and fee loss.
- What to do when it's broken: Send the client a written confirmation of the informed consent before continuing the representation.
- Example reading used in demos: Yes

**6. Signed contingency fee agreement** (Must be in place, answered Yes or No; policy)

- Asks: Does every contingency fee matter have a fee agreement signed by the client?
- Rule: ABA Model Rule 1.5(c) (state versions vary)
- What a miss costs: Without a signed writing, contingency fees can be reduced or forfeited and draw discipline.
- What to do when it's broken: Get the written fee agreement signed now, stating the percentage and how expenses are handled.
- Example reading used in demos: No

**7. Unearned fees refunded** (Must never happen, answered Yes or No; policy)

- Asks: Is the firm still holding unearned fees or client files for any representation that has ended?
- Rule: ABA Model Rule 1.16(d) (state versions vary)
- What a miss costs: Holding unearned fees after a representation ends is a frequent grievance that leads to discipline and fee disputes.
- What to do when it's broken: Refund the unearned fees and return the client's file promptly, and record the date.
- Example reading used in demos: No

**8. Client data security controls** (Must be in place, answered Yes or No; policy)

- Asks: Are email, document systems and remote access protected by multi-factor authentication and encryption?
- Rule: ABA Model Rule 1.6(c) (state versions vary); ABA Formal Opinion 477R
- What a miss costs: Breaches and wire fraud involving client data bring malpractice claims, discipline and breach-response costs.
- What to do when it's broken: Turn on multi-factor authentication for all users now and encrypt devices that hold client data.
- Example reading used in demos: Yes

**9. CLE hours by the deadline** (Minimum 0 days, warns from 60 days; policy, a company can set its own limit)

- Asks: Days left before the continuing legal education (CLE) deadline for any lawyer still short of required hours
- Rule: State CLE rules (vary by state)
- What a miss costs: Lawyers who miss CLE deadlines face late fees and administrative suspension, which stops billable work.
- What to do when it's broken: Enroll the lawyer in approved courses now or request an extension from the state bar.
- Example reading used in demos: 45 days

**10. Staff and vendor supervision** (Must be in place, answered Yes or No; policy)

- Asks: Have all non-lawyer staff and outside vendors been trained on confidentiality and trust handling this year?
- Rule: ABA Model Rule 5.3 (state versions vary)
- What a miss costs: Firms are responsible for staff and vendor errors with client funds and data, leading to discipline and malpractice claims.
- What to do when it's broken: Train the untrained staff now and restrict their access to client funds and data until done.
- Example reading used in demos: Yes

### 44. CampusArmor (Colleges & Universities)

**1. Return of Title IV funds in 45 days** (Maximum 45 days, warns from 35 days; counts days since a date)

- Asks: Days since the school determined that a student withdrew, without returning unearned federal student aid (Title IV) funds
- Rule: 34 CFR 668.22(j)(1)
- What a miss costs: Late returns of Title IV funds are a top program review finding, bringing liabilities, fines and risk to aid eligibility.
- What to do when it's broken: Return the unearned funds now and document the calculation and return date in the student file.
- Example reading used in demos: 48 days

**2. Annual Security Report by Oct 1** (Must be in place, answered Yes or No)

- Asks: Was this year's Annual Security Report published and distributed to students and staff by October 1?
- Rule: 34 CFR 668.41(e); 34 CFR 668.46(b)
- What a miss costs: A late or incomplete Annual Security Report brings Clery Act fines per violation and program review findings.
- What to do when it's broken: Publish and distribute the report now and notify prospective students and employees of it.
- Example reading used in demos: Yes

**3. Clery timely warnings issued** (Must be in place, answered Yes or No)

- Asks: Was a timely warning issued for every reported Clery crime considered a serious or continuing threat?
- Rule: 34 CFR 668.46(e)
- What a miss costs: Failing to warn the campus of a Clery crime that is a serious or continuing threat brings fines and lawsuits.
- What to do when it's broken: Issue the warning now and record who decided, when, and how it was distributed.
- Example reading used in demos: Yes

**4. Credit balance paid in 14 days** (Maximum 14 days, warns from 10 days; counts days since a date)

- Asks: Days since a Title IV credit balance occurred without paying it to the student or parent
- Rule: 34 CFR 668.164(h)(2)
- What a miss costs: Late Title IV credit balance payments are a common program review finding that leads to liabilities and fines.
- What to do when it's broken: Pay the credit balance to the student or parent now unless a valid written authorization to hold it is on file.
- Example reading used in demos: 12 days

**5. GLBA safeguards for aid data** (Must be in place, answered Yes or No)

- Asks: Is student financial data covered by a written security program, a qualified individual, a risk assessment, MFA and encryption?
- Rule: 16 CFR 314.4
- What a miss costs: Missing safeguards for student financial data can bring Federal Student Aid findings, breach costs and lawsuits.
- What to do when it's broken: Name a qualified individual, complete the risk assessment, and turn on MFA and encryption for aid systems now.
- Example reading used in demos: No

**6. FERPA consent before disclosure** (Must be in place, answered Yes or No)

- Asks: Is written consent or a documented FERPA exception on file before each disclosure of education records?
- Rule: 34 CFR 99.30; 34 CFR 99.31
- What a miss costs: Improper release of education records brings Department of Education investigations and can put federal funding at risk.
- What to do when it's broken: Stop the disclosure until signed consent or a documented exception is on file, and log the request.
- Example reading used in demos: Yes

**7. Title IX personnel trained** (Must be in place, answered Yes or No)

- Asks: Have the Title IX Coordinator, investigators, decision-makers and facilitators completed required training posted on the website?
- Rule: 34 CFR 106.45(b)(1)(iii); 34 CFR 106.45(b)(10)(i)(D)
- What a miss costs: Untrained Title IX staff lead to flawed grievance outcomes, OCR findings and lawsuits from both parties.
- What to do when it's broken: Train the staff before they handle any case and post the training materials on the institution's website.
- Example reading used in demos: Yes

**8. 90/10 federal revenue limit** (Maximum 90%, warns from 85%)

- Asks: Percent of revenue from federal education assistance funds this fiscal year (for-profit institutions)
- Rule: 34 CFR 668.28; HEA 487(a)(24)
- What a miss costs: A for-profit school over the limit two years in a row loses Title IV eligibility.
- What to do when it's broken: Notify the Department within the required time and plan to raise non-federal revenue before year end.
- Example reading used in demos: 87%

**9. Academic progress checked** (Must be in place, answered Yes or No)

- Asks: Was satisfactory academic progress evaluated at the policy's required interval before the next aid disbursement?
- Rule: 34 CFR 668.34
- What a miss costs: Paying aid to students not meeting academic progress rules creates repayment liabilities in program reviews.
- What to do when it's broken: Hold further disbursements until SAP is evaluated and warning or probation status is applied.
- Example reading used in demos: No

**10. Drug and alcohol biennial review** (Maximum 24 months, warns from 20 months)

- Asks: Months since the last biennial review of the drug and alcohol prevention program
- Rule: 34 CFR 86.100(b)
- What a miss costs: Missing the biennial review is a common finding that can lead to fines and risk to federal funding.
- What to do when it's broken: Complete and document the biennial review now and keep the report available on request.
- Example reading used in demos: 18 months

### 45. ChildArmor (Child Care)

**1. Background checks before access** (Must be in place, answered Yes or No; policy)

- Asks: Has every staff member cleared the required background checks before any unsupervised time with children?
- Rule: 45 CFR 98.43; state licensing rules
- What a miss costs: Staff working without cleared checks lead to license actions, loss of subsidy funding and abuse lawsuits.
- What to do when it's broken: Remove the staff member from unsupervised contact with children until all checks are cleared.
- Example reading used in demos: No

**2. Headcount at every transition** (Must be in place, answered Yes or No; policy)

- Asks: Was a name-to-face headcount recorded at every transition, outing and vehicle unload today?
- Rule: State child care licensing rules (vary by state)
- What a miss costs: Children left behind, wandering off or left in vehicles lead to lawsuits, license suspension and closure.
- What to do when it's broken: Do a headcount now against the sign-in sheet and check all rooms, outdoor areas and vehicles.
- Example reading used in demos: Yes

**3. Infants placed on backs to sleep** (Must never happen, answered Yes or No; policy)

- Asks: Was any infant placed to sleep on the stomach or side, or with soft bedding or objects in the crib?
- Rule: 45 CFR 98.41(a)(1)(ii)(B); state licensing rules
- What a miss costs: Unsafe sleep deaths bring wrongful death suits, license revocation and closure.
- What to do when it's broken: Place the infant on the back in a bare crib now and retrain the caregiver on safe sleep.
- Example reading used in demos: No

**4. Infant staff-to-child ratio** (Maximum 4 children per caregiver, warns from 4 children per caregiver; policy, a company can set its own limit)

- Asks: Infants per caregiver in the infant room right now
- Rule: State licensing rules (vary by state; 1:4 for infants is common)
- What a miss costs: Ratio violations are frequently cited licensing violations and lead to fines, probation and liability.
- What to do when it's broken: Bring in another qualified caregiver now or move children so the ratio is met.
- Example reading used in demos: 5 children per caregiver

**5. Suspected abuse reported** (Must be in place, answered Yes or No; policy)

- Asks: Has every suspected case of abuse or neglect been reported to the state hotline or police right away?
- Rule: State mandated reporter laws (vary by state); CAPTA (42 U.S.C. 5106a); 45 CFR 98.41
- What a miss costs: Failing to report suspected abuse is a crime for mandated reporters and leads to license revocation and lawsuits.
- What to do when it's broken: Call the state child abuse hotline now and document the report; do not investigate on your own.
- Example reading used in demos: Yes

**6. Pediatric CPR and first aid** (Must be in place, answered Yes or No; policy)

- Asks: Is at least one caregiver with current pediatric CPR and first aid on site with each group at all times?
- Rule: 45 CFR 98.41 (pediatric first aid and CPR); state licensing rules (vary)
- What a miss costs: Having no certified staff on site during an emergency brings licensing citations and liability suits.
- What to do when it's broken: Reassign certified staff now and schedule CPR and first aid courses for staff with lapsed cards.
- Example reading used in demos: Yes

**7. Signed medication authorization** (Must be in place, answered Yes or No; policy)

- Asks: Is signed parent authorization on file for every medication given to a child today?
- Rule: 45 CFR 98.41 (medication administration with parental consent); state licensing rules
- What a miss costs: Medication given without parent authorization or in error leads to licensing violations and injury claims.
- What to do when it's broken: Do not give the medication until the parent signs the authorization with drug, dose and times.
- Example reading used in demos: No

**8. Immunization records on file** (Must be in place, answered Yes or No; policy)

- Asks: Does every enrolled child have a current immunization record or valid exemption on file?
- Rule: 45 CFR 98.41(a)(1)(i); state licensing rules (vary)
- What a miss costs: Missing immunization records are a common licensing citation and increase outbreak liability.
- What to do when it's broken: Get the record or exemption from the parent by the state deadline or exclude the child as the state requires.
- Example reading used in demos: Yes

**9. Fire evacuation drill** (Maximum 31 days, warns from 25 days; policy, a company can set its own limit; counts days since a date)

- Asks: Days since the last fire evacuation drill
- Rule: State licensing rules and fire codes (vary by state; monthly is common)
- What a miss costs: Missed drills are a common licensing and fire inspection citation and raise liability if a fire occurs.
- What to do when it's broken: Hold a fire evacuation drill now and log the date, time, evacuation time and children present.
- Example reading used in demos: 26 days

**10. CACFP meal pattern met** (Must be in place, answered Yes or No)

- Asks: Did every meal claimed for CACFP reimbursement meet the required meal pattern components?
- Rule: 7 CFR 226.20
- What a miss costs: Meals that miss the meal pattern are disallowed, and repeat problems lead to serious deficiency and termination.
- What to do when it's broken: Do not claim the noncompliant meals; fix the menu and train kitchen staff on the meal pattern.
- Example reading used in demos: Yes

### 46. HotelArmor (Hotels & Lodging)

**1. Total price shown with all fees** (Must be in place, answered Yes or No)

- Asks: Does every rate you advertise or quote show the total price, including all mandatory fees, more prominently than other prices?
- Rule: FTC Rule on Unfair or Deceptive Fees, 16 CFR Part 464
- What a miss costs: Hidden resort and service fees draw FTC civil penalties and consumer class actions, and force refunds.
- What to do when it's broken: Fold every mandatory fee into the displayed rate on your site, OTAs and quotes before taking more bookings.
- Example reading used in demos: No

**2. Accessible rooms bookable online** (Must be in place, answered Yes or No)

- Asks: Can guests book accessible rooms the same way as other rooms, with the accessibility features described and the room held once booked?
- Rule: ADA, 28 CFR 36.302(e)(1)
- What a miss costs: Reservation systems that hide or release accessible rooms are a frequent basis for ADA lawsuits and DOJ settlements.
- What to do when it's broken: Update the booking engine to list accessible features, hold booked accessible rooms and block them from general sale.
- Example reading used in demos: Yes

**3. Pool and spa drain covers compliant** (Must be in place, answered Yes or No)

- Asks: Does every pool and spa drain have a cover certified to the current VGB standard, within its expiration date?
- Rule: Virginia Graeme Baker Pool and Spa Safety Act, 15 U.S.C. 8003; 16 CFR Part 1450
- What a miss costs: Non-compliant drain covers force pool closures and expose the property to entrapment injury lawsuits.
- What to do when it's broken: Close the pool or spa until the drain covers are replaced with certified ones.
- Example reading used in demos: Yes

**4. Pool free chlorine level** (Minimum 1 ppm, warns from 1.5 ppm; policy, a company can set its own limit)

- Asks: Latest free chlorine reading in the pool
- Rule: State pool codes vary; CDC Model Aquatic Health Code common minimum
- What a miss costs: Low disinfectant is a common health-inspection closure and a source of illness claims from guests.
- What to do when it's broken: Close the pool, raise free chlorine to at least the minimum and retest before reopening.
- Example reading used in demos: 0.8 ppm

**5. Fire alarm system tested yearly** (Maximum 365 days, warns from 335 days; policy, a company can set its own limit; counts days since a date)

- Asks: Days since the fire alarm system's last annual inspection and test
- Rule: NFPA 72 as adopted by the local fire code
- What a miss costs: An overdue fire alarm test is a fire-marshal citation and can void insurance coverage after a fire.
- What to do when it's broken: Book a licensed fire alarm contractor to inspect and test the system now.
- Example reading used in demos: 340 days

**6. Smoke alarm in every guest room** (Must be in place, answered Yes or No)

- Asks: Does every guest room have a working hard-wired smoke alarm, checked on the room inspection schedule?
- Rule: Hotel and Motel Fire Safety Act, 15 U.S.C. 2224(a); local fire code
- What a miss costs: Missing guest-room smoke detection loses federal travel business and is a fire code violation with high liability after a fire.
- What to do when it's broken: Take rooms without a working smoke alarm out of service until one is installed and tested.
- Example reading used in demos: Yes

**7. Carbon monoxide alarms installed** (Must be in place, answered Yes or No; policy)

- Asks: Are carbon monoxide alarms installed and working wherever your state requires them (rooms near fuel-burning appliances or garages)?
- Rule: State law varies; many states require CO alarms in lodging with fuel-burning appliances
- What a miss costs: Carbon monoxide incidents in guest rooms lead to wrongful-death lawsuits and state penalties where alarms are required.
- What to do when it's broken: Install and test CO alarms in every required area and move guests out of affected rooms until done.
- Example reading used in demos: Yes

**8. No card security codes stored** (Must never happen, answered Yes or No; policy)

- Asks: Are card security codes (CVV) or full magnetic-stripe data kept anywhere after authorization, including paper or email?
- Rule: PCI DSS v4.0 Requirement 3.3.1
- What a miss costs: Stored card data turns a breach into card-brand fines, forensic costs and loss of the ability to take cards.
- What to do when it's broken: Purge stored security codes and stripe data now and stop collecting cards by email or paper forms.
- Example reading used in demos: No

**9. Legionella water management plan** (Must be in place, answered Yes or No; policy)

- Asks: Is there a written water management plan for Legionella covering hot tubs, cooling towers and hot water, with logged checks?
- Rule: ANSI/ASHRAE Standard 188; CDC water management toolkit
- What a miss costs: Legionnaires' disease outbreaks traced to hotel water systems lead to closures and large injury and wrongful-death claims.
- What to do when it's broken: Adopt a water management plan, set temperature and disinfectant checks, and log them starting today.
- Example reading used in demos: No

**10. Housekeeping chemical training** (Must be in place, answered Yes or No)

- Asks: Has every housekeeping and maintenance worker been trained on the chemicals they use before first working with them?
- Rule: OSHA 29 CFR 1910.1200(h)
- What a miss costs: Hazard communication is frequently cited by OSHA and exposes the property to penalties and injury claims.
- What to do when it's broken: Train untrained staff on the safety data sheets and labels for their chemicals before their next shift.
- Example reading used in demos: Yes

### 47. BarArmor (Bars, Breweries & Liquor)

**1. No alcohol sold to minors** (Must never happen, answered Yes or No)

- Asks: Was alcohol sold or served to anyone under 21, including in a compliance check?
- Rule: State liquor law; minimum drinking age 21 under 23 U.S.C. 158
- What a miss costs: Sales to minors bring license suspension or revocation, fines, and dram shop liability if the minor causes harm.
- What to do when it's broken: Retrain every server and cashier on ID checks, scan IDs at the door and report the incident as your state requires.
- Example reading used in demos: No

**2. No service to intoxicated guests** (Must never happen, answered Yes or No; policy)

- Asks: Was alcohol served to a guest who was visibly intoxicated?
- Rule: State liquor and dram shop laws vary
- What a miss costs: Overserving is the core of dram shop lawsuits after drunk-driving crashes and can cost the liquor license.
- What to do when it's broken: Cut the guest off, arrange a safe ride, write an incident report and review the shift with staff.
- Example reading used in demos: No

**3. Liquor license renewed on time** (Minimum 0 days, warns from 45 days; policy, a company can set its own limit; counts days until a date)

- Asks: Days until the liquor license expires
- Rule: State liquor licensing law varies
- What a miss costs: Selling on an expired license means closing the bar or paying penalties, with lost revenue every night it lapses.
- What to do when it's broken: Stop alcohol sales until the license is renewed; file the renewal and fees with the state today.
- Example reading used in demos: 21 days

**4. Server alcohol training current** (Maximum 1,095 days, warns from 1,005 days; policy, a company can set its own limit; counts days since a date)

- Asks: Days since the oldest server certificate on staff was issued
- Rule: State responsible beverage service laws vary
- What a miss costs: Untrained servers raise dram shop exposure, can void liquor liability coverage and are cited in states that mandate training.
- What to do when it's broken: Schedule recertification for every server whose certificate is out of date before their next shift.
- Example reading used in demos: 400 days

**5. Alcohol sold only in legal hours** (Must never happen, answered Yes or No; policy)

- Asks: Was alcohol sold or served outside the legal hours of sale?
- Rule: State and local liquor law varies
- What a miss costs: After-hours sales are a common liquor-board citation leading to fines and license suspensions.
- What to do when it's broken: Lock the POS for alcohol at last call and brief closing staff.
- Example reading used in demos: No

**6. Managers kept out of the tip pool** (Must never happen, answered Yes or No)

- Asks: Did any owner, manager or supervisor keep part of employees' tips or the tip pool?
- Rule: FLSA, 29 U.S.C. 203(m)(2)(B); 29 CFR 531.54
- What a miss costs: Managers taking tips leads to back-wage and liquidated-damage lawsuits, often brought as collective actions.
- What to do when it's broken: Remove managers from the tip pool and repay the tips they received to the employees.
- Example reading used in demos: No

**7. Federal excise tax filed on time** (Must be in place, answered Yes or No)

- Asks: For breweries: are federal excise tax returns filed and paid by each due date?
- Rule: 26 U.S.C. 5051; 27 CFR Part 25 (brewers)
- What a miss costs: Late excise tax returns and payments bring TTB penalties and interest and can put a brewer's permit at risk.
- What to do when it's broken: File and pay the overdue excise tax return now and set reminders for each filing period.
- Example reading used in demos: Yes

**8. Label approval before interstate sale** (Must be in place, answered Yes or No)

- Asks: Does every label on product sold across state lines have an approved TTB Certificate of Label Approval (COLA)?
- Rule: FAA Act, 27 U.S.C. 205(e); 27 CFR Parts 4, 5 and 7
- What a miss costs: Products shipped across state lines without label approval can be held or pulled, costing inventory and distribution.
- What to do when it's broken: Hold out-of-state shipments of that product and submit the label to TTB for approval.
- Example reading used in demos: Yes

**9. Alcohol bought from licensed sources** (Must be in place, answered Yes or No; policy)

- Asks: Is every bottle, keg and case bought from a licensed wholesaler or distributor?
- Rule: State three-tier distribution laws vary
- What a miss costs: Buying from retail stores or unlicensed sellers breaks state three-tier rules and can lead to license loss.
- What to do when it's broken: Stop buying from unlicensed sources and pull any product bought outside licensed channels.
- Example reading used in demos: Yes

**10. No supplier inducements** (Must never happen, answered Yes or No)

- Asks: Did a supplier give the business free goods, equipment, services or payments in exchange for carrying or promoting its brands?
- Rule: FAA Act, 27 U.S.C. 205(b); 27 CFR Part 6; state tied-house laws
- What a miss costs: Taking free goods, equipment or cash from suppliers to push their brands violates trade practice rules for both sides.
- What to do when it's broken: Decline or return the inducement and document it; check your state's tied-house rules before accepting anything.
- Example reading used in demos: No

### 48. FirearmArmor (Firearms Dealers)

**1. Form 4473 fully completed** (Must be in place, answered Yes or No)

- Asks: Was the Form 4473 fully completed, checked against the buyer's ID and signed by the buyer and dealer before the transfer?
- Rule: 18 U.S.C. 923(g); 27 CFR 478.124(c)
- What a miss costs: Incomplete or wrong Forms 4473 are frequently cited at ATF inspections, and willful violations lead to license revocation.
- What to do when it's broken: Hold the transfer and have the buyer and dealer complete and correct the form before handing over the firearm.
- Example reading used in demos: No

**2. Background check before transfer** (Must never happen, answered Yes or No)

- Asks: Was a firearm transferred without a NICS 'proceed', without waiting the 3 business days after no response, or after a denial?
- Rule: Brady Act, 18 U.S.C. 922(t)(1)
- What a miss costs: Transferring without a NICS check or after a denial is a serious violation that can end in license revocation and prosecution.
- What to do when it's broken: Stop transfers without a proceed or elapsed wait, and report any transfer after a denial to ATF.
- Example reading used in demos: No

**3. Acquisition logged next business day** (Maximum 1 business days, warns from 1 business days; counts business days since a date)

- Asks: Business days since a firearm was received without an entry in the acquisition and disposition record
- Rule: 27 CFR 478.125(e)
- What a miss costs: Late or missing acquisition entries are frequently cited at ATF inspections and make firearms untraceable.
- What to do when it's broken: Enter every unrecorded firearm in the A&D record now.
- Example reading used in demos: 0 business days

**4. Disposition logged within 7 days** (Maximum 7 days, warns from 5 days; counts days since a date)

- Asks: Days since a firearm left inventory without a disposition entry
- Rule: 27 CFR 478.125(e)
- What a miss costs: Missing disposition entries are a common ATF finding and can support a revocation case when repeated.
- What to do when it's broken: Record the disposition today with the buyer's name and address or the Form 4473 serial number.
- Example reading used in demos: 9 days

**5. Multiple handgun sale reported** (Maximum 0 business days; counts business days since a date)

- Asks: Business days since a sale of two or more handguns to one buyer within five business days, without filing ATF Form 3310.4
- Rule: 18 U.S.C. 923(g)(3)(A); 27 CFR 478.126a
- What a miss costs: Unfiled multiple sales reports are a recurring ATF citation that counts toward willfulness in revocation cases.
- What to do when it's broken: File ATF Form 3310.4 with ATF and the chief local law enforcement officer today.
- Example reading used in demos: 0 business days

**6. Theft or loss reported in 48 hours** (Maximum 48 h, warns from 36 h; counts hours since a date and time)

- Asks: Hours since a firearm theft or loss was discovered, without reporting to ATF and local police
- Rule: 18 U.S.C. 923(g)(6); 27 CFR 478.39a
- What a miss costs: Late theft and loss reports are a violation ATF cites and delay recovery of guns that may be used in crimes.
- What to do when it's broken: Report the missing firearm to ATF (Form 3310.11) and local police now.
- Example reading used in demos: 12 h

**7. FFL renewed before it expires** (Minimum 0 days, warns from 60 days; counts days until a date)

- Asks: Days until the federal firearms license expires
- Rule: 18 U.S.C. 923; 27 CFR 478.45
- What a miss costs: Selling on an expired license is illegal and forces the shop to stop firearm sales until renewed.
- What to do when it's broken: Stop firearm sales until renewed; submit the renewal application to ATF now.
- Example reading used in demos: 45 days

**8. No sale to a prohibited person** (Must never happen, answered Yes or No)

- Asks: Did a buyer answer yes to a prohibited-person question, or show signs of a straw purchase, and still receive the firearm?
- Rule: 18 U.S.C. 922(d)
- What a miss costs: Selling to someone the dealer has reason to believe is prohibited is a felony and grounds for revocation and civil suits.
- What to do when it's broken: Refuse the sale, document the reasons, and contact ATF about a suspected straw purchase.
- Example reading used in demos: No

**9. Safety device with every handgun** (Must be in place, answered Yes or No)

- Asks: Does every handgun sale include a secure gun storage or safety device?
- Rule: 18 U.S.C. 922(z)(1)
- What a miss costs: Selling a handgun without a storage or safety device is a violation that can bring license suspension and civil penalties.
- What to do when it's broken: Provide a lock or storage device with the handgun before the buyer leaves.
- Example reading used in demos: Yes

**10. No handgun sales to other states** (Must never happen, answered Yes or No)

- Asks: Was a handgun sold directly to a resident of another state?
- Rule: 18 U.S.C. 922(b)(3)
- What a miss costs: Handgun sales to out-of-state residents are illegal and are treated as serious violations at inspection.
- What to do when it's broken: Stop the sale and ship the handgun to a licensed dealer in the buyer's state instead.
- Example reading used in demos: No

### 49. CasinoArmor (Casinos & Gaming)

**1. CTR filed within 15 days** (Maximum 15 days, warns from 12 days; counts days since a date)

- Asks: Days since a patron's cash in or cash out went over $10,000 in a gaming day, without filing a currency transaction report (CTR)
- Rule: 31 CFR 1021.311; 31 CFR 1010.306(a)(1)
- What a miss costs: Missed CTRs are a core BSA failure that brings FinCEN penalties and enforcement actions against casinos.
- What to do when it's broken: File the Currency Transaction Report with FinCEN now.
- Example reading used in demos: 3 days

**2. Cash totals added up per patron** (Must be in place, answered Yes or No)

- Asks: Are all cash transactions by the same patron in a gaming day added together (cage, pit, slots) to check the $10,000 threshold?
- Rule: 31 CFR 1021.313
- What a miss costs: Failing to aggregate a patron's cash transactions misses required CTRs and is a common finding in casino BSA exams.
- What to do when it's broken: Turn on adding up across departments (aggregation) in the casino management system and review today's gaming day.
- Example reading used in demos: Yes

**3. SAR filed within 30 days** (Maximum 30 days, warns from 25 days; counts days since a date)

- Asks: Days since suspicious activity of $5,000 or more was detected, without filing a suspicious activity report (SAR)
- Rule: 31 CFR 1021.320(a)(2), (b)(3)
- What a miss costs: Late or missing suspicious activity reports are a common basis for FinCEN civil money penalties against casinos.
- What to do when it's broken: File the SAR with FinCEN today and document why it was late.
- Example reading used in demos: 34 days

**4. Independent AML test** (Maximum 365 days, warns from 335 days; policy, a company can set its own limit; counts days since a date)

- Asks: Days since the last independent test of the AML program
- Rule: 31 CFR 1021.210(b)(2)(ii); frequency is risk-based, commonly yearly
- What a miss costs: An overdue independent test is a standard BSA exam finding and weakens the casino's defense in an enforcement action.
- What to do when it's broken: Engage an independent reviewer to test the AML program now.
- Example reading used in demos: 400 days

**5. BSA training for gaming staff** (Must be in place, answered Yes or No)

- Asks: Has every cage, pit, slot and host employee completed anti-money-laundering (BSA/AML) training?
- Rule: 31 CFR 1021.210(b)(2)(iii)
- What a miss costs: Untrained cage, pit and slot staff miss reportable activity, a frequent root cause cited in casino enforcement actions.
- What to do when it's broken: Train untrained employees before their next shift on the floor or cage.
- Example reading used in demos: Yes

**6. W-2G issued for reportable jackpots** (Must be in place, answered Yes or No)

- Asks: Is a Form W-2G issued for every slot, bingo, keno or other win at or above the current IRS reporting threshold?
- Rule: 26 U.S.C. 6041; 26 CFR 7.6041-1; IRS Instructions for Forms W-2G
- What a miss costs: Missing W-2G forms bring IRS penalties per form and can trigger IRS gaming compliance examinations.
- What to do when it's broken: Issue the missing W-2Gs and update payout procedures to the current IRS thresholds.
- Example reading used in demos: Yes

**7. Patrons screened against OFAC** (Must be in place, answered Yes or No)

- Asks: Are patrons screened against the OFAC sanctions list before large payouts, wires or markers?
- Rule: 31 CFR Part 501; OFAC sanctions regulations
- What a miss costs: Paying or extending credit to a sanctioned person brings OFAC penalties even without intent.
- What to do when it's broken: Screen the patron now and hold the payout if there is a possible match.
- Example reading used in demos: Yes

**8. Self-excluded patrons kept out** (Must never happen, answered Yes or No; policy)

- Asks: Did a self-excluded patron gamble, receive comps or get marketing?
- Rule: State gaming law and self-exclusion programs vary
- What a miss costs: Letting self-excluded patrons gamble or sending them marketing brings state gaming fines and patron lawsuits.
- What to do when it's broken: Remove the patron, forfeit winnings as state rules require, and purge them from marketing lists.
- Example reading used in demos: No

**9. No underage gambling** (Must never happen, answered Yes or No; policy)

- Asks: Was anyone under the legal gambling age allowed to gamble or receive a payout?
- Rule: State gaming law sets the minimum age
- What a miss costs: Underage gambling is a serious state gaming violation that brings fines and puts the gaming license at risk.
- What to do when it's broken: Remove the minor, withhold winnings as state rules require, report to the regulator and retrain security.
- Example reading used in demos: No

**10. BSA records kept five years** (Must be in place, answered Yes or No)

- Asks: Are CTRs, SARs, patron identification and required transaction records kept for at least five years?
- Rule: 31 CFR 1010.430(d); 31 CFR 1021.410
- What a miss costs: Missing records leave the casino unable to prove compliance during exams and can support penalties.
- What to do when it's broken: Restore or rebuild missing records and set a five-year retention hold.
- Example reading used in demos: Yes

### 50. ShopArmor (E-commerce)

**1. Ship on time or offer cancellation** (Maximum 30 days, warns from 25 days; counts days since a date)

- Asks: Days since a paid order with no promised ship date, without shipping it or sending a delay notice with a cancellation option
- Rule: FTC Mail, Internet, or Telephone Order Merchandise Rule, 16 CFR 435.2
- What a miss costs: Late shipments without notice break the FTC Mail Order Rule, leading to civil penalties, refunds and chargebacks.
- What to do when it's broken: Ship now or send a delay notice offering the right to cancel for a prompt refund.
- Example reading used in demos: 33 days

**2. Clear consent and easy cancel** (Must be in place, answered Yes or No)

- Asks: Do subscribers see all terms before paying, give express consent to recurring charges, and have a simple way to cancel?
- Rule: ROSCA, 15 U.S.C. 8403
- What a miss costs: Subscriptions without clear consent or easy cancellation bring FTC actions, refunds and chargebacks.
- What to do when it's broken: Add a clear recurring-charge disclosure and consent checkbox, and a one-step online cancel.
- Example reading used in demos: No

**3. No fake or suppressed reviews** (Must never happen, answered Yes or No)

- Asks: Does the store post fake reviews, pay only for positive reviews, or hide negative ones?
- Rule: FTC Rule on Consumer Reviews and Testimonials, 16 CFR Part 465
- What a miss costs: Fake, bought or suppressed reviews bring FTC civil penalties per violation and damage marketplace standing.
- What to do when it's broken: Remove fake or incentivized-positive reviews and publish all genuine reviews.
- Example reading used in demos: No

**4. Influencer ties disclosed** (Must be in place, answered Yes or No)

- Asks: Do all paid influencers and affiliates clearly disclose their connection to the brand in each post?
- Rule: FTC Endorsement Guides, 16 CFR 255.5
- What a miss costs: Undisclosed paid endorsements lead to FTC actions against both the brand and its influencers.
- What to do when it's broken: Require clear disclosures in every sponsored post and pause partners who do not comply.
- Example reading used in demos: Yes

**5. Children's products certified** (Must be in place, answered Yes or No)

- Asks: Does every children's product have a Children's Product Certificate based on testing by a CPSC-accepted lab?
- Rule: CPSIA; 15 U.S.C. 2063(a)(2); 16 CFR Parts 1107 and 1110
- What a miss costs: Selling children's products without third-party testing and certificates leads to CPSC penalties, recalls and delisting.
- What to do when it's broken: Stop selling uncertified children's products until they are tested and certified.
- Example reading used in demos: Yes

**6. Prop 65 warning for California** (Must be in place, answered Yes or No)

- Asks: Do products sold to California that expose buyers to listed chemicals show a Prop 65 warning on the product page and package?
- Rule: Cal. Health and Safety Code 25249.6; Cal. Code Regs. tit. 27, 25602
- What a miss costs: Missing Prop 65 warnings are a frequent target of private enforcement suits, with settlements and legal fees.
- What to do when it's broken: Add the required warning to the product page and packaging before more California sales.
- Example reading used in demos: Yes

**7. Sales tax registration by state** (Maximum 100%, warns from 85%; policy, a company can set its own limit)

- Asks: This year's sales into your largest unregistered state, as a percent of that state's economic nexus threshold
- Rule: South Dakota v. Wayfair (2018); state economic nexus thresholds vary
- What a miss costs: Crossing a state's economic nexus threshold without collecting tax leaves the seller owing back taxes, penalties and interest.
- What to do when it's broken: Register with the state and start collecting sales tax on orders shipped there.
- Example reading used in demos: 94%

**8. Unsubscribes honored in 10 days** (Maximum 10 business days, warns from 8 business days; counts business days since a date)

- Asks: Business days since an unsubscribe request while marketing emails are still being sent
- Rule: CAN-SPAM Act, 15 U.S.C. 7704(a)(4)
- What a miss costs: Emailing people after they unsubscribe brings FTC penalties per email under CAN-SPAM.
- What to do when it's broken: Suppress the address in every sending tool now.
- Example reading used in demos: 3 business days

**9. Made in USA claims backed up** (Must never happen, answered Yes or No)

- Asks: Is any product labeled Made in USA without all or virtually all of it made in the United States?
- Rule: FTC Made in USA Labeling Rule, 16 CFR Part 323
- What a miss costs: Unqualified Made in USA claims on imported goods bring FTC civil penalties and relabeling costs.
- What to do when it's broken: Remove or qualify the claim (for example, Assembled in USA) on labels and listings.
- Example reading used in demos: No

**10. Marketing texts only with consent** (Must be in place, answered Yes or No)

- Asks: Do marketing texts go only to people who gave prior express written consent, with opt-outs honored?
- Rule: TCPA, 47 U.S.C. 227; 47 CFR 64.1200(a)(2)
- What a miss costs: Texting without prior express written consent brings TCPA class actions with statutory damages per message.
- What to do when it's broken: Stop texting contacts without documented written consent and process all opt-outs.
- Example reading used in demos: Yes

---

## Appendix B: Every Academy world, with its lesson cards
Stage 1 of every world opens with these lesson cards. The cards of the first worlds use the family company's own name and industries; they are shown here for a sample company, Acme Logistics, that tracks FleetArmor and HRArmor.

### Foundations (8 worlds, on every track)

**World 1: Meet Your Company.** What the family business does.

- *Hi, I'm Armo!.* I'm a shield, and my job is helping Acme Logistics follow the rules that keep everyone safe.
- *Your family's company.* Acme Logistics works in logistics, employers & hr. Customers count on it to do that work safely and well.
- *What is a business?.* A business is a group of people who make something or do work that others pay for.
- *Your adventure.* Someday you might help lead Acme Logistics. Let's get you ready, one level at a time!

**World 2: Business Words.** The words grown-ups use at work.

- *Talk like a business person.* Every job has its own words. Learning them helps you understand meetings, emails and reports.
- *Revenue.* All the money customers pay the business.
- *Cost.* Money the business spends, like pay, supplies and rent.
- *Profit.* The money left over after paying all the costs.
- *Customer.* A person or company that buys from the business.
- *Employee.* A person the business pays to work there.
- *Invoice.* A bill that tells a customer how much they owe.
- *Your Word Bank.* You can find every word in the Word Bank on your level map anytime.

**World 3: Why Rules Matter.** Rules keep people safe.

- *Rules are like game rules.* Games are fair and fun because everyone follows the same rules. Businesses work the same way.
- *Who makes them?.* Governments write rules to keep workers, customers and neighbors safe. Inspectors check them.
- *A real one.* One of Acme Logistics's rules: "11-hour driving limit." OmniArmor keeps an eye on it every day.
- *Why it matters.* Breaking a rule can mean a fine (money paid as a penalty), losing customers, or someone getting hurt.

**World 4: Stop, Careful, Go.** Read the company's signals.

- *Three lights.* OmniArmor checks every rule and shows a light, just like a traffic light.
- *Green.* All good! The reading is safely inside the rule.
- *Yellow.* Careful! It's getting close to the limit. Time to plan a fix.
- *Red.* Stop! The rule is broken. Fix it right away to protect people and avoid a fine.

**World 5: Countdown Calendar.** Deadlines and reminders.

- *Jobs that repeat.* Lots of jobs must be done again and again, like checking safety gear every year.
- *A real example.* "Annual driving record review" has to be done at least every 365 days.
- *Counting days.* OmniArmor counts the days since a job was last done, so nobody has to remember.
- *Friendly reminders.* It sends reminders 30, 7 and 1 day before a deadline, so the team is never surprised.

**World 6: Money Smarts.** Revenue, costs and profit.

- *Revenue.* Revenue is all the money customers pay the business.
- *Costs.* Costs are what the business spends: pay for workers, supplies, rent and more.
- *Profit.* Profit is what's left: revenue minus costs. Healthy businesses make a profit.
- *Surprise costs.* Fines are costs nobody plans for. Following the rules protects the profit.

**World 7: Talk Like a Pro.** Speak and write professionally.

- *Speak like a pro.* How you talk at work shapes the company's reputation: what people think of it.
- *Be polite.* Say please, thank you and the person's name. Kind words open doors.
- *Listen first.* Let people finish. Then answer. Listening shows respect.
- *Be clear.* Say exactly what you'll do and when: "I'll send it by Friday."
- *Great emails.* Start with a greeting, make your point in a few sentences, say thank you, and sign your name.
- *Own mistakes.* Everyone makes mistakes. Saying "I'll fix it" earns trust.

**World 8: Lead the Team.** How good owners lead.

- *Owners lead people.* A business is its people. Leading Acme Logistics means helping the team do great work.
- *Listen.* Good leaders listen to workers and customers, especially when they raise a problem.
- *Keep records.* OmniArmor's audit trail remembers who changed what, and when. That keeps everyone honest.
- *Ask for help.* Great owners ask experts for advice: lawyers, accountants and experienced workers.

### Leadership (8 worlds, on every track)

**World 9: Own It.** Taking responsibility.

- *Own it.* Self-responsibility means doing what you said you'd do, without anyone reminding you.
- *Mistakes happen.* Everyone makes mistakes. Owners say "That's on me," fix it, and learn from it.
- *The owner's promise.* At Acme Logistics, the owner is responsible for everything, even jobs handed to others.

**World 10: Never Give Up.** Perseverance.

- *Never give up.* Perseverance means keeping going when things get hard.
- *Failing forward.* Many famous businesses failed many times before they succeeded. Each try taught them something.
- *Steady wins.* Owners who stay calm in hard times and keep improving are the ones still standing later.

**World 11: Earn Instant Respect.** Confidence people trust.

- *Instant respect.* People decide quickly whether to trust a leader. Stand tall, look people in the eye, and speak calmly and clearly.
- *Lasting respect.* The respect that lasts comes from keeping promises, being fair and treating everyone well.
- *Calm is powerful.* Leaders who stay calm when others panic are the ones people look to.
- *Prepare.* Confidence comes from preparation. Know your stuff before you walk into the room.

**World 12: Build Your Dream Team.** When and how to hire.

- *Growing the team.* When there's more steady work than the team can handle, it may be time to hire.
- *Pick well.* Look for honesty, a great attitude and the right skills. Skills can be taught; character is harder.
- *Be fair.* Ask every candidate the same job-related questions. Fair hiring is the law, and it finds the best people.
- *Welcome them.* Great training and a friendly welcome help new people succeed fast.

**World 13: Tough Calls.** When to let someone go.

- *Tough calls.* Sometimes a worker isn't doing the job. Good managers talk privately first and help them improve.
- *Warnings and records.* Clear feedback, written down, keeps things fair for everyone.
- *The last step.* If someone still can't or won't do the job, or breaks trust, letting them go may be the right call.
- *Do it right.* Do it privately, respectfully and legally, with advice from an expert.

**World 14: Win Customers.** Make people want to come back.

- *Customers are everything.* Without customers, there is no business. Every job at Acme Logistics serves them.
- *Keep them coming back.* Great quality, friendly service and kept promises turn customers into fans.
- *Complaints are gifts.* A complaint tells you how to get better. Fix it fast and say thank you.

**World 15: Beat the Competition.** Win your field, fair and square.

- *Rivals.* Other companies want the same customers. That's competition, and it pushes everyone to get better.
- *Win by being better.* The strongest move is to be the best choice: better quality, faster service, new ideas.
- *Find your edge.* Be the very best at something special. That's how small companies beat big ones.
- *Play fair.* Lying about rivals, stealing secrets or secretly fixing prices with them is against the law. Winners win fair.

**World 16: Pro Business Moves.** Negotiate, plan and decide.

- *Pro moves.* Smart owners negotiate politely, read every contract, and plan ahead.
- *Negotiate.* Know your budget, ask for a better deal, and be ready to walk away.
- *Rainy-day fund.* Saving money lets a business survive surprises.
- *Big decisions.* Gather facts, weigh the pros and cons, and ask trusted advisors before deciding.

### Money and Finance (4 worlds, on Trailblazer, Summit and Titan Mastery)

**World 17: Price It Right.** How businesses choose prices. 38 graded questions and 13 true-or-false facts.

- *Cost, price and profit.* Cost is what you spend to make something. Price is what a customer pays you. Profit is price minus cost. If the price is below the cost, you lose money on every sale.
- *Markup.* Markup is the amount you add on top of cost. A $2 cost with a 50% markup adds $1, so the price is $3. Your prices must also cover rent, wages and other bills.
- *Sales and discounts.* A discount lowers the price for a while. 25% off a $20 item saves $5, so it costs $15. Sales can bring in new customers, but too many sales shrink your profit.
- *Value and competitors.* Customers pay for value: quality, service and convenience. Check what other shops charge, but you do not have to be the cheapest if you give more value.
- *Raising prices fairly.* When costs go up, prices may need to rise. Tell customers early, explain why, and keep quality high. Honest pricing builds trust that lasts.

**World 18: Budget Boss.** Plan your money before you spend it. 36 graded questions and 13 true-or-false facts.

- *What a budget is.* A budget is a plan for your money. You list what comes in, then decide where it goes before you spend it. Planning first stops nasty surprises later.
- *Needs vs wants.* Needs keep you or your business going, like food, rent or supplies. Wants are nice extras, like a fancy sign. Pay for needs first, then wants.
- *Fixed and variable costs.* Fixed costs stay the same each month, like rent. Variable costs change with how much you make or sell, like flour for a bakery.
- *Emergency fund.* An emergency fund is money saved for surprises, like a broken oven. Many experts suggest saving enough to cover a few months of costs.
- *Track, then pause.* Write down every dollar you spend. Before an impulse buy, wait a day and ask: is this in my plan? Cash flow is money moving in and out over time.

**World 19: Save and Grow.** Saving, interest and investing. 36 graded questions and 13 true-or-false facts.

- *Pay yourself first.* Save a set amount as soon as money comes in, before you spend any. Even small amounts grow into big savings over time.
- *Simple interest.* Interest is money a bank pays you for keeping your savings there. At 5% a year, $100 earns $5 in one year.
- *Compound growth.* Compound growth means you earn interest on your interest, too. Over many years, money can grow like a snowball rolling downhill.
- *Risk and reward.* Investments that might grow more usually have a bigger risk of losing money. Spread money out so one loss does not sink you.
- *Spot the scams.* Anyone who promises big, fast, sure profits is a red flag. Real growth takes time. If it sounds too good to be true, it probably is.

**World 20: Banks and Borrowing.** Loans, interest and good credit. 36 graded questions and 12 true-or-false facts.

- *What banks do.* Banks keep people's savings safe and lend money to others. They pay savers a little interest and charge borrowers more. That difference helps the bank earn money.
- *Loans and interest.* A loan is borrowed money you must pay back. Interest is the extra cost of borrowing. Borrow $100 at 10% for a year and you pay back $110.
- *Credit scores.* A credit score is like a report card for borrowing. Paying on time helps it. A good score can mean easier loans and lower interest later.
- *Good debt and bad debt.* Good debt helps you earn more, like a loan for an oven that bakes more bread. Bad debt pays for things that lose value fast and do not earn money.
- *Read before you sign.* Always read the fine print: the interest rate, the fees and what happens if you pay late. Never borrow more than you can repay.

### Growth (4 worlds, on Trailblazer, Summit and Titan Mastery)

**World 21: Get the Word Out.** Marketing that people love. 39 graded questions and 12 true-or-false facts.

- *Know your customer.* Marketing starts with knowing who you help: what they need, where they shop and what they care about. Ask good questions and really listen.
- *Pick a target audience.* Your target audience is the group most likely to buy. A bike shop might focus on families and riders instead of trying to reach everyone.
- *Ads and word of mouth.* Ads are messages you pay for, like flyers, signs or posts. Word of mouth is free: happy customers telling friends. Great service powers both.
- *Keep ads honest.* Only promise what your product really does. Honest ads build trust, and in many places false ads are against the law.
- *Measure and budget.* Set a marketing budget and track results. If a $50 ad brings 10 customers, each customer cost $5. Keep what works and drop what doesn't.

**World 22: Build a Brand.** Names, logos and reputation. 38 graded questions and 12 true-or-false facts.

- *What is a brand?.* A brand is what people think and feel when they hear your business name. It comes from your name, look, products and how you treat people.
- *Logos and colors.* A logo is a simple symbol for your business. Using the same colors and style everywhere helps people spot you fast.
- *Your brand is a promise.* A brand tells customers what to expect, like fresh bread daily or fast bike repairs. Keep that promise every single time.
- *Reputation and reviews.* Your reputation is what people say about you. It takes years to build and moments to lose. Reviews share it with new customers.
- *Stand out and protect it.* Find what makes you special. In many places you can register a trademark, so others can't use a name or logo too close to yours.

**World 23: Sales Superstar.** Helping people say yes. 38 graded questions and 12 true-or-false facts.

- *Listen first.* Great salespeople listen more than they talk. Ask what the customer needs, then help them find the right fit.
- *Features vs benefits.* A feature is a fact about a product, like 21 gears. A benefit is how it helps you, like climbing hills easily. People buy benefits.
- *Handle no with grace.* When someone says no, thank them politely. A kind no today can become a happy yes later. Never push, pressure or argue.
- *Honest selling only.* Never lie or trick someone into buying. Only suggest extras that truly help, like a lock for a new bike. Trust brings people back.
- *Close and follow up.* Closing means asking for the sale clearly, like 'Would you like to take it today?' Checking in later shows you care.

**World 24: Business Online.** Websites, reviews and social media. 37 graded questions and 12 true-or-false facts.

- *Websites and online stores.* A website tells people what you sell, your hours and how to reach the business. An online store lets customers buy any time of day.
- *Social media for business.* Businesses post photos, news and tips to stay in touch. Post what is true, kind and useful. Kids should always post with a grown-up's OK.
- *Reviews and comments.* Online reviews shape your reputation. Thank people for kind ones and answer complaints politely. Never argue or post fake reviews.
- *Protect customer privacy.* Customers trust you with names, emails and card numbers. Keep them safe, collect only what you need and never share them without permission.
- *Email with permission.* Only send newsletters to people who signed up, and make it easy to unsubscribe. In many places this is the law, and it is always good manners.

### Operations (4 worlds, on Trailblazer, Summit and Titan Mastery)

**World 25: Run the Machine.** Processes, checklists and quality. 36 graded questions and 12 true-or-false facts.

- *What operations means.* Operations is how the work gets done every day: making, serving, shipping and cleaning up. Good operations means the same good result every time.
- *Processes and checklists.* A process is the set of steps for a job. A checklist lists those steps so nobody forgets one, even on a busy day. Experts like pilots and chefs use them too.
- *Quality control.* Quality control means checking work before it reaches the customer. Catch a burnt cookie in the kitchen, not at the counter.
- *Fix the cause.* When something goes wrong, keep asking why it happened. Fixing the real cause stops the problem from coming back. Blaming people rarely fixes anything.
- *Measure and write it down.* Count things like orders, mistakes and wait times to see what is improving. Write down how jobs are done so anyone can do them the right way.

**World 26: Stock Smart.** Keep the right things on the shelf. 39 graded questions and 12 true-or-false facts.

- *What inventory is.* Inventory is the stuff a business keeps to sell or use: flour in a bakery, tires in a bike shop, cups at a lemonade stand.
- *Not too little, not too much.* Run out and you lose sales. Buy too much and money sits on the shelf, takes space and may spoil. Aim for just right.
- *Reorder points.* A reorder point is the amount left when you order more. Daily sales times the days a delivery takes (the lead time) gives the number. Add a little extra for safety.
- *First in, first out.* Sell or use the oldest stock first. Put new items behind old ones and check expiration dates so nothing goes bad on the shelf.
- *Count and store it safely.* Count stock often so your records match the shelf. Store heavy items low, keep aisles clear, and keep cold food cold.

**World 27: Supply and Demand.** Why prices go up and down. 36 graded questions and 12 true-or-false facts.

- *Supply and demand.* Supply is how much of something is for sale. Demand is how much people want to buy. Together they help set prices.
- *Shortages.* A shortage happens when people want more than there is. Shelves empty and prices often rise, like snow shovels before a big storm.
- *Surpluses.* A surplus is more stuff than people want to buy. Sellers often lower prices to clear it, like winter coats on sale in spring.
- *Seasons and busy times.* Demand changes with seasons and events: sunscreen in summer, pumpkins in fall. Smart owners plan and stock up before the rush.
- *Competition and prices.* When many sellers offer the same thing, they compete. Buyers can choose, so prices tend to stay lower and quality goes up.

**World 28: Safety First.** Keep everyone safe at work. 38 graded questions and 12 true-or-false facts.

- *Why safety rules exist.* Safety rules come from lessons learned, often after someone got hurt. Following them keeps workers and customers safe every day.
- *Spot it, report it.* If you see a spill, a broken step or a frayed cord, tell a supervisor or adult right away. Never try to fix dangerous things yourself.
- *Protective gear.* Gloves, goggles, helmets and hairnets protect your body. Wear the right gear for the job every time, even for quick tasks.
- *Exits and drills.* Know where the exits are and keep them clear. Practice drills so everyone knows what to do and where to meet in an emergency.
- *Clean hands, safe lifts.* Scrub hands with soap for about 20 seconds before touching food. Lift with your legs, not your back, and ask an adult for help with heavy loads.

### Mindset (4 worlds, on Trailblazer, Summit and Titan Mastery)

**World 29: Goal Getter.** Set goals and crush them. 36 graded questions and 12 true-or-false facts.

- *Make it specific.* "Sell more" is a wish. "Sell 20 cupcakes by Saturday" is a goal. It says what, how much and by when, so you can plan for it and know when you hit it.
- *Give it a deadline.* A deadline turns "someday" into a plan. Pick a date that is a stretch but still doable, then work backward to see what must happen each week.
- *Small steps win.* Big goals can feel scary. Break them into small steps you can finish in a day or a week. Every step you finish is real progress you can see.
- *Track and adjust.* Check your progress often with a chart or list. If you fall behind, change the plan, not the dream: try a new step, add time or ask for help.
- *Celebrate milestones.* A milestone is a checkpoint on the way to a big goal. Celebrate small wins to stay motivated. Mix short-term goals (this week) with long-term ones (this year).

**World 30: Master Your Time.** Plan, prioritize and focus. 36 graded questions and 12 true-or-false facts.

- *Urgent vs important.* Urgent means it needs doing soon. Important means it really matters. Do what is both first, and plan time for important things before they turn urgent.
- *Make a to-do list.* Write every task down, then number them by priority. Crossing items off feels great and frees your brain to focus on one job at a time.
- *Beat procrastination.* Procrastinating means putting things off. Start with just 5 minutes, break the task into tiny steps and do the hardest part while you have the most energy.
- *Guard your focus.* Put the phone away, close extra tabs and work in short focused blocks. Switching between tasks feels fast but usually makes work slower and sloppier.
- *Plan, say no, rest.* Put tasks on a schedule with extra time for surprises. Say no politely when your plate is full. Breaks and sleep recharge your brain so you work better.

**World 31: Big Ideas.** Creativity and problem solving. 36 graded questions and 12 true-or-false facts.

- *Brainstorm without judging.* When brainstorming, list as many ideas as you can, even silly ones. Don't judge yet. Lots of ideas lead to good ideas, and wild ones can spark smart ones.
- *Find the real problem.* Before fixing, ask "why?" a few times. Sales are low. Why? People can't see the stand. Why? It's behind a tree. Now you know what to fix.
- *Ask your customers.* Customers know what they need. Ask open questions, listen more than you talk and watch what they actually buy. Their answers beat your guesses.
- *Test small, learn fast.* Try a new idea in a small, cheap way first, like selling a new flavor for one day. If it fails, you lose little and learn a lot. Improve it and try again.
- *Steps to solve problems.* 1. Name the problem. 2. Find the cause. 3. Brainstorm fixes. 4. Test one. 5. Check results. Teams solve better when everyone shares and builds on ideas.

**World 32: Cool Under Pressure.** Handle stress and big feelings. 36 graded questions and 12 true-or-false facts.

- *Big feelings are normal.* Everyone feels stressed, angry or nervous sometimes, even business owners. Feelings are not good or bad. What matters is what you choose to do next.
- *Breathe, then think.* When upset, pause. Breathe in slowly for 4 counts and out for 4. Your body calms down and your thinking brain catches up, so you can choose a smart reply.
- *Take feedback like a pro.* When someone points out a mistake, listen, stay calm and ask questions. Useful feedback helps you improve, and you can take time before you answer.
- *Empathy and asking for help.* Empathy means imagining how someone else feels. When things feel too big, talk to a trusted adult. Asking for help is a strength, not a weakness.
- *Confident, not arrogant.* Confidence is believing you can learn and do hard things. Arrogance is thinking you are always right. Sleep, good food, moving and breaks keep you steady.

### Rules and Trust (4 worlds, on Trailblazer, Summit and Titan Mastery)

**World 33: Do the Right Thing.** Honesty, fairness and integrity. 36 graded questions and 14 true-or-false facts.

- *Integrity.* Integrity means doing the right thing even when nobody is watching. Return extra change, fix hidden mistakes, and follow safety rules every time.
- *Keep Your Promises.* A promise is something people count on. If you cannot keep one, tell them early and offer a fair fix. Broken promises break trust.
- *Fair to Everyone.* Treat every customer and worker with respect. Pay the same for the same work, post clear prices, and choose people for skill, not friendship.
- *Conflicts of Interest.* A conflict of interest is when something personal, like family or a gift, could sway a business choice. Tell others about it and let fair rules decide.
- *Speak Up.* If you see cheating or danger, tell a trusted adult or the right person in charge. Owning up to your own mistakes fast is part of speaking up too.

**World 34: Deals and Contracts.** Promises in writing. 36 graded questions and 14 true-or-false facts.

- *What Is a Contract?.* A contract is an agreement the law can enforce. Both sides agree, and each gives something, like money for cupcakes. It can be spoken or written.
- *Read Before You Sign.* Never sign something you have not read and understood. Ask about any part that is unclear. A signature means you agree to all of it, even small print.
- *Clear Terms.* Good deals say what will be done, how much it costs, and when it is due. Clear terms stop arguments before they start.
- *Keep Your Side.* Once you agree, do what you promised, on time. If something goes wrong, talk early. Breaking a deal can mean paying for the harm it causes.
- *Get It in Writing.* Spoken deals can count, but memories fade. Writing it down gives proof of what you agreed. For big deals, ask a lawyer to check it first.

**World 35: Taxes Explained.** Why businesses pay taxes. 36 graded questions and 14 true-or-false facts.

- *What Are Taxes?.* Taxes are money people and businesses pay to the government. Taxes help pay for roads, schools, parks, firefighters and other things everyone shares.
- *Sales Tax.* In many places, a small extra amount is added when you buy things. The shop collects it from the customer and passes it on to the government.
- *Income Tax.* Businesses usually pay income tax on profit: the money left after costs. More profit usually means more tax. Never hide income.
- *Keep Good Records.* Save receipts and write down every sale and cost. Good records show what you earned and spent, and they make tax time much easier.
- *Pay on Time.* Taxes have due dates. Late or missing taxes can bring penalties and interest. An accountant can help you get it right and on time.

**World 36: Cyber Shield.** Keep the business safe online. 36 graded questions and 14 true-or-false facts.

- *Strong Passwords.* Use long passwords, like a passphrase of 4 random words. Use a different one for each account and never share them, even with friends.
- *Two-Step Login.* Two-step login asks for a second proof, like a code on your phone, after your password. Even if someone steals the password, they still cannot get in.
- *Spot Phishing.* Phishing messages pretend to be someone you trust to trick you into clicking or sharing secrets. Watch for rushing, scary warnings and odd links.
- *Update and Back Up.* Updates fix security holes, so install them soon. Backups are extra copies of files kept somewhere else, so you can recover if something breaks.
- *Protect and Report.* Keep customer data private and share it only with people who need it. If something looks strange, stop and tell an adult or your manager right away.

### The Big Picture (5 worlds, on Trailblazer, Summit and Titan Mastery)

**World 37: Start a Business.** From idea to open for business. 36 graded questions and 12 true-or-false facts.

- *Solve a real problem.* Great businesses start by fixing a problem people really have, like a busy street with no place to fix a flat bike tire.
- *Test it small first.* Before spending a lot, try a tiny version. Sell 20 cookies at a school fair and see if people come back for more.
- *Know your startup costs.* Startup costs are what you spend before you earn: tools, supplies, a sign, permits. List them all so there are no surprises.
- *Follow the rules.* In many places a business needs permits or licenses, and food sellers must follow safety rules. Ask the local town office what you need.
- *Listen to early customers.* Your first customers are your best teachers. Ask what they liked and what to fix, then improve a little every week.

**World 38: Business Plans.** Map out where you're going. 36 graded questions and 12 true-or-false facts.

- *What is a business plan?.* A business plan is a written map of your business: what you sell, who buys it, how you will make money and what your goals are.
- *Mission and vision.* Your mission says what you do and why, today. Your vision describes the bigger future you are working toward.
- *Know customers and rivals.* Describe who your customers are and what they need. Then study competitors so you know how to be different or better.
- *Costs, sales and goals.* Estimate what you will spend and sell each month. Set clear goals with numbers and dates, like 40 customers by June.
- *Keep the plan alive.* A plan is never really finished. Update it as you learn, and use it to explain your idea to a bank or a partner.

**World 39: Read the Numbers.** Charts, trends and smart decisions. 36 graded questions and 12 true-or-false facts.

- *Tables and charts.* A table lists numbers in rows and columns. A bar chart shows them as bars, so you can see at a glance which is biggest.
- *Spot the trend.* A trend is the direction numbers move over time. Sales of 40, 50 and 60 over three months show an upward trend.
- *Averages.* To find an average, add the numbers and divide by how many there are. Sales of 4, 6 and 8 cups have an average of 6.
- *Percentages.* Percent means 'out of 100.' If 25 of 100 visitors buy, that is 25 percent. Half is 50 percent, a quarter is 25 percent.
- *Data beats guesses.* Check the numbers before deciding. Watch key numbers like sales, costs and customers, and double-check anything that looks odd.

**World 40: Business Around the World.** Trade, currencies and cultures. 36 graded questions and 12 true-or-false facts.

- *Imports and exports.* An export is something a country sells to another country. An import is something it buys from another country.
- *Why countries trade.* Places are good at making different things because of weather, skills or resources. Trade lets everyone get more variety.
- *Money around the world.* Many countries use their own money, called currency. An exchange rate tells how much of one currency you get for another.
- *Shipping and time zones.* Goods sent overseas can take weeks to arrive. When it is morning for you, it may be night for a partner far away.
- *Respect every culture.* Customs differ around the world, like greetings, holidays and gifts. Learn and respect them to build trust with partners.

**World 41: Grow Green.** Business that cares for the planet. 36 graded questions and 12 true-or-false facts.

- *Waste less, save more.* Waste is money thrown away. Using only what you need, like ordering the right amount of fruit, cuts costs and helps the planet.
- *Reduce, reuse, recycle.* First use less. Then reuse what you can, like sturdy boxes. Recycle the rest, such as paper, cans and many plastics.
- *Save energy and water.* Turn off lights and machines when not in use, fix leaky taps and pick efficient equipment. Lower bills mean more profit.
- *Be a good neighbor.* Keep your area clean, keep noise down and help local causes. A business that cares about its community earns trust.
- *Honest green claims.* Only say your product is green if it truly is. Making false eco claims is called greenwashing, and it breaks customer trust.

### Winning Mindset (2 worlds, on Trailblazer, Summit and Titan Mastery)

**World 42: Champion Mindset.** Think like a winner. 39 graded questions and 14 true-or-false facts.

- *The power of yet.* Your brain gets better with effort and good strategies. When something is hard, add one word: "I can't do it yet." Selling, math and free throws all improve with smart practice.
- *Be your own coach.* Talk to yourself like a good coach would. Swap "I'm bad at this" for "What can I try next?" Honest, helpful self-talk keeps you going when things get tough.
- *Mistakes are data.* A loss or a mistake is information. Review what happened, pick one thing to fix, then go again. A bake sale that flopped can teach you more than one that went great.
- *Confidence is built.* Real confidence comes from preparation and practice, not luck or bragging. Rehearse your pitch and know your prices, and you will feel steady when it counts.
- *Race your past self.* Compare yourself to who you were last month, not to everyone else. A friend's success is not your failure. People who are ahead of you can be your best teachers.
- *Win with class.* Credit the team when you win. Shake hands and skip excuses when you lose. Big moments are a privilege you earned: breathe slowly, use your routine, and own your effort and attitude.

**World 43: Habits of Winners.** Daily moves that build champions. 40 graded questions and 14 true-or-false facts.

- *1% better adds up.* Get a little better each day and it grows, like interest on savings. Practice your bake sale pitch 10 minutes a day and in a month you have 300 minutes of practice most people never do.
- *Practice the hard part.* Deliberate practice means picking the part you are worst at, working on just that, getting feedback and trying again. Doing the easy part over and over feels good but teaches you less.
- *Systems beat motivation.* Motivation comes and goes like weather. A routine, like walking dogs at 4pm every school day, keeps you going when you do not feel like it. Start small so you keep your promise to yourself.
- *Focus and energy.* Do one thing at a time with your phone in another room. Sleep, real food, moving your body and short breaks are not lazy. They are how your brain and body do their best work.
- *Prepare, then reflect.* Before a big moment like a pitch, test or game, use a checklist and rehearse. At the end of the day ask: what went well and what can I improve? Write it down and track your streaks.
- *Your people and patience.* Spend time with people who lift you up, and be that person for your team. Sometimes skip a small reward now for a bigger one later, like saving profits to buy a better cart.

### The Owner's Challenge

The boss world. It mixes questions from every world on the learner's track (10 questions on Launchpad and Trailblazer, 12 on Summit, 15 on Titan Mastery) and is where certificates are earned.

### Rule Quests

One for each of the 50 industries in Appendix A. Each turns that industry's ten checks into questions about the rule, its limit and what to do. A family's own industries are listed first, and the rest can be explored. Each Rule Quest has 10 stages on Launchpad and Trailblazer, 20 on Summit and 50 on Titan Mastery.

### The Word Bank (201 words)

- **Revenue**: All the money customers pay the business.
- **Cost**: Money the business spends, like pay, supplies and rent.
- **Profit**: The money left over after paying all the costs.
- **Customer**: A person or company that buys from the business.
- **Employee**: A person the business pays to work there.
- **Invoice**: A bill that tells a customer how much they owe.
- **Budget**: A plan for how much money to spend on each thing.
- **Contract**: A written promise between two sides that both agree to.
- **Compliance**: Following the laws and rules that apply to the business.
- **Deadline**: The last day something must be done.
- **Inventory**: All the products and supplies the business has on hand.
- **Stakeholder**: Anyone who cares how the business does: owners, workers, customers and neighbors.
- **Inspector**: A person whose job is to check that rules are being followed.
- **Fine**: Money a business must pay as a penalty for breaking a rule.
- **Owner**: The person or family the business belongs to, who makes the big decisions.
- **Reputation**: What people think of the business, earned by how it acts.
- **Asset**: Something valuable the business owns, like a delivery van, an oven or cash in the bank.
- **Liability**: Something the business owes to others, like a loan or an unpaid bill.
- **Loan**: Money borrowed from a bank or person that must be paid back, usually with extra.
- **Interest**: The extra money you pay for borrowing, or earn for saving, on top of the amount.
- **Debt**: Money you owe and still need to pay back.
- **Credit**: Trust that lets you buy now and pay later, as long as you pay on time.
- **Credit score**: A number that shows how well someone pays back what they borrow.
- **Savings**: Money you set aside instead of spending it, so it's there when you need it.
- **Emergency fund**: Money saved just for surprises, like a broken freezer or a slow month.
- **Bank account**: A safe place at a bank that holds your money and keeps track of it.
- **Deposit**: Money you put into a bank account, or pay ahead to hold an order.
- **Withdrawal**: Money you take out of a bank account.
- **Capital**: The money and tools used to start or grow a business.
- **Investor**: A person who gives money to a business hoping to earn more back later.
- **Return on investment**: How much you earn back compared to what you put in.
- **Shareholder**: A person who owns a small piece, called a share, of a company.
- **Equity**: The part of a business that truly belongs to the owners after debts are paid.
- **Dividend**: A share of the profit that a company pays to its owners.
- **Collateral**: Something valuable you promise to give a lender if you can't pay back a loan.
- **Bankruptcy**: A legal process for a business that can't pay its debts.
- **Cash flow**: The money coming in and going out of a business over time.
- **Expense**: Money spent to run the business, like rent, flour or electricity.
- **Fixed cost**: A cost that stays the same each month, like rent, no matter how much you sell.
- **Variable cost**: A cost that goes up when you sell more, like cups for each lemonade.
- **Overhead**: The everyday costs of running a business, like rent, lights and insurance.
- **Break-even**: The point where money coming in equals costs, so you neither win nor lose money.
- **Gross**: The total amount before anything is taken away, like costs or taxes.
- **Net**: The amount left after costs or taxes are taken away.
- **Margin**: The part of a sale's price that is profit after paying for the item.
- **Markup**: The amount added to an item's cost to set the price you sell it for.
- **Price**: How much money a customer pays to buy something.
- **Unit price**: The price for one item, like one cupcake or one pound of apples.
- **Discount**: A lower price than usual, like 20% off.
- **Sales**: The things a business sells, or the money it gets from selling them.
- **Forecast**: A smart guess about the future, like how many pies you'll sell next month.
- **Quarter**: One fourth of a year, or three months. Businesses check results each quarter.
- **Fiscal year**: The 12 months a business uses for its money records, which may not start in January.
- **Tax**: Money people and businesses pay to the government for roads, schools and more.
- **Audit**: A careful check of a business's records to make sure they are correct and honest.
- **Bookkeeping**: Writing down every dollar that comes in and goes out of the business.
- **Accountant**: An expert who keeps track of a business's money and helps with taxes.
- **Balance sheet**: A report that lists what a business owns, what it owes, and what's left.
- **Income statement**: A report that shows sales, costs and profit over a period of time.
- **Accounts receivable**: Money that customers owe the business but haven't paid yet.
- **Accounts payable**: Money the business owes to suppliers but hasn't paid yet.
- **Payment terms**: The rules for when and how a bill must be paid, like within 30 days.
- **Late fee**: Extra money charged when a bill is paid after the due date.
- **Down payment**: Part of the price paid up front, with the rest paid later.
- **Depreciation**: How things like trucks and computers lose value as they get older.
- **Inflation**: When prices go up over time, so the same dollar buys a little less.
- **Economy**: All the buying, selling and working that happens in a town or country.
- **Recession**: A time when the economy shrinks, people buy less and jobs are harder to find.
- **Risk**: The chance that something could go wrong or that you could lose money.
- **Diversify**: To spread out your money or customers so one problem can't sink you.
- **Entrepreneur**: A person who starts a business and takes a risk to make an idea real.
- **Startup**: A brand-new business that is just getting going.
- **Partnership**: A business owned by two or more people who share the work and profits.
- **Partner**: A person who owns and runs a business together with you.
- **Sole proprietor**: A person who owns a business all alone.
- **Corporation**: A business that is its own legal thing, separate from the people who own it.
- **Nonprofit**: An organization that uses its money to help a cause, not to make owners rich.
- **Franchise**: A business that pays to use another company's name, recipes and way of working.
- **Merger**: When two companies join together to become one.
- **Family business**: A business owned and run by members of the same family.
- **Succession plan**: A plan for who will run the business when the current owner steps away.
- **Board of directors**: A group of people chosen to guide a company and check on its leaders.
- **CEO**: Chief Executive Officer: the top leader who runs a company day to day.
- **Manager**: A person who leads a team and makes sure work gets done well.
- **Supervisor**: A person who watches over workers during a shift and helps them.
- **Business plan**: A written plan that explains what a business will sell, to whom, and how it will make money.
- **Mission**: A short statement of what a business does and why it exists.
- **Vision**: A picture of what the business hopes to become in the future.
- **Strategy**: A big plan for how the business will reach its goals.
- **Goal**: Something specific you are working to achieve, like 50 sales by June.
- **Milestone**: An important step along the way to a bigger goal.
- **KPI**: Key Performance Indicator: a number you track to see if you're reaching a goal.
- **Benchmark**: A standard used to compare how well you're doing.
- **Prototype**: A first test version of a product, made to try out an idea.
- **Pilot**: A small test run of a new idea before doing it everywhere.
- **Innovation**: A new idea or better way of doing something.
- **Productivity**: How much good work gets done in a certain amount of time.
- **Efficiency**: Getting a job done well without wasting time, money or supplies.
- **Bottleneck**: One slow step that holds up everything else, like a single slow oven.
- **Quality control**: Checking products to make sure they meet the business's standards.
- **Safety**: Protecting workers and customers from getting hurt.
- **Regulation**: A rule made by the government that businesses must follow.
- **Permit**: Official permission to do something, like build a new sign or hold an event.
- **License**: An official paper that says a business or person is allowed to do certain work.
- **Insurance**: Paying a small amount regularly so you get help paying if something bad happens.
- **Liability insurance**: Insurance that helps pay if the business accidentally hurts someone or damages their stuff.
- **Lease**: A contract to rent a building or equipment for a set time.
- **Rent**: Money paid to use a building or space that belongs to someone else.
- **Landlord**: The person or company that owns a building and rents it out.
- **Utilities**: Services like water, electricity and heat that a building needs.
- **Agenda**: A list of topics to talk about in a meeting, in order.
- **Minutes**: Written notes of what was said and decided in a meeting.
- **Delegation**: Giving a task to someone else while still making sure it gets done right.
- **Accountability**: Being willing to answer for your actions and their results.
- **Ethics**: Ideas about what is right and fair, used to make good choices.
- **Integrity**: Being honest and doing the right thing, even when no one is watching.
- **Confidential**: Private information that should only be shared with people who need it.
- **Trade secret**: Private business know-how, like a secret recipe, that gives a company an edge.
- **Trademark**: A protected name, logo or symbol that only one business can use for its products.
- **Patent**: A legal right that lets only the inventor make and sell an invention for a time.
- **Copyright**: A legal right that protects things people create, like books, music and art.
- **Supplier**: A business that sells you the things you need, like flour for a bakery.
- **Vendor**: Someone who sells goods or services, often to other businesses.
- **Distributor**: A business that buys products in bulk and delivers them to stores.
- **Wholesale**: Selling large amounts to stores at a lower price per item.
- **Retail**: Selling items one at a time to everyday customers.
- **Bulk order**: Buying a large amount at once, often for a lower price per item.
- **Purchase order**: A written order a business sends to a supplier listing what it wants to buy.
- **Quote**: A written price a business offers for a job before the work starts.
- **Estimate**: A careful guess of how much a job will cost or how long it will take.
- **Bid**: An offer to do a job or buy something for a certain price.
- **Logistics**: Planning how to move and store products so they arrive in the right place on time.
- **Supply chain**: All the steps and businesses that help get a product from raw materials to the customer.
- **Shipment**: A group of goods sent from one place to another.
- **Lead time**: How long it takes from placing an order until it arrives.
- **Warehouse**: A large building where products are stored until they are sold.
- **Stockout**: When a business runs out of an item customers want to buy.
- **Barcode**: A pattern of lines a scanner reads to know what an item is and its price.
- **Point of sale**: The place and system where a customer pays, like a cash register.
- **Receipt**: A paper or email that proves what someone bought and how much they paid.
- **Refund**: Money given back to a customer who returns something.
- **Return policy**: The store's rules for bringing items back for a refund or exchange.
- **Warranty**: A promise to fix or replace a product if it breaks within a certain time.
- **Guarantee**: A promise that a product or service will work as described.
- **Recall**: When a company asks customers to return a product because it might be unsafe.
- **Demand**: How much of something people want to buy.
- **Supply**: How much of something is available to buy.
- **Exports**: Products a country sells to other countries.
- **Imports**: Products a country buys from other countries.
- **Brand**: The name, look and feeling people connect with a business.
- **Logo**: A small picture or symbol that stands for a business.
- **Slogan**: A short, catchy phrase that helps people remember a business.
- **Marketing**: Everything a business does to understand customers and get them interested.
- **Advertising**: Paying to tell people about your products, like with posters or online ads.
- **Promotion**: A move up to a bigger job with more responsibility, often with more pay.
- **Coupon**: A ticket or code that gives a customer money off a purchase.
- **Market research**: Studying customers and competitors to learn what people want.
- **Survey**: A short list of questions to learn what people think.
- **Target market**: The group of people a business most wants to sell to.
- **Niche**: A small, special group of customers a business focuses on serving very well.
- **Competitor**: Another business that sells similar things to the same customers.
- **Market share**: The part of all sales in a market that one business gets.
- **Monopoly**: When only one company sells something, so customers have no other choice.
- **Price fixing**: When rivals secretly agree on prices. It's illegal and hurts customers.
- **Customer service**: How a business helps and treats its customers before and after they buy.
- **Loyalty**: When customers keep choosing your business again and again.
- **Retention**: Keeping the customers or workers you already have.
- **Churn**: When customers stop buying or cancel, like leaving a subscription.
- **Repeat customer**: A customer who comes back to buy again.
- **Referral**: When someone sends a new customer or worker your way.
- **Testimonial**: A happy customer's words about the business, shared with permission.
- **Review**: A customer's opinion of a business, often posted online for others to read.
- **Complaint**: When a customer tells you something went wrong. It's a chance to fix it.
- **Upsell**: Suggesting a better or bigger item, like a large drink instead of a small one.
- **Subscription**: Paying regularly, like every month, to keep getting a product or service.
- **Pitch**: A short talk to convince someone to buy, invest or join.
- **Elevator pitch**: A super short pitch, about 30 seconds, that explains your idea.
- **Networking**: Meeting people and building friendly work connections.
- **Negotiation**: Talking with someone to reach a deal you both can agree on.
- **Compromise**: When each side gives up a little to reach an agreement.
- **Win-win**: A deal that is good for both sides.
- **Payroll**: The list of workers and how much each is paid, and the job of paying them.
- **Salary**: A set amount of pay for a year of work, paid in parts.
- **Wage**: Pay for each hour of work.
- **Minimum wage**: The lowest hourly pay the law allows a business to pay most workers.
- **Overtime**: Extra hours worked beyond the usual amount, often paid at a higher rate.
- **Benefits**: Extras a job offers besides pay, like health insurance or paid vacation days.
- **Raise**: An increase in a worker's pay.
- **Shift**: A block of time someone works, like 8 a.m. to noon.
- **Schedule**: A plan that shows who works when.
- **Job description**: A written list of a job's tasks, skills, hours and pay.
- **Resume**: A short document that lists a person's skills, schooling and work experience.
- **Interview**: A meeting where an employer asks questions to see if someone fits a job.
- **Reference**: A past boss or teacher who can tell an employer about how you work.
- **Onboarding**: Welcoming and training a new worker so they can do their job well.
- **Probation period**: The first weeks of a new job, when both sides see if it's a good fit.
- **Performance review**: A meeting to talk about how well someone is doing their job and how to grow.
- **Feedback**: Helpful comments about what's going well and what could be better.
- **Mentor**: An experienced person who gives advice and helps you grow.
- **Intern**: A student or beginner who works for a short time to learn a job.
- **Teamwork**: People working together and helping each other reach a shared goal.

---

## Appendix C: Armo's 14 personalities
Each personality changes only Armo's words and outfit. Chief is the default for grown-ups, Sweetie for kids. A sample of each one's lines:

### Chief: Calm and professional

- Idle: "All systems watched. Carry on."
- Alert: "Attention needed: {title}"
- All clear: "All clear. Nothing needs you right now."
- Fixed: "Resolved. Thank you."
- Academy cheer: "Correct."
- After a win: "Solid work. On to the next one."

### Sweetie: Sweet and kind

- Idle: "You're doing great today. Just wanted you to know."
- Alert: "Oh! Something needs a little love: {title}"
- All clear: "All clear! Go do something nice for yourself."
- Fixed: "You fixed it! I'm so proud of you!"
- Academy cheer: "Yay, you got it!"
- After a win: "You did it! I'm so proud of you!"

### Jokester: Never misses a joke

- Idle: "Why did the deadline break up with the calendar? It needed space."
- Alert: "Joke's on hold! {title}"
- All clear: "Nothing to fix. I'm basically unemployed. Love that for us."
- Fixed: "Fixed! You deserve a standing ovation. I'll stand. I'm always standing."
- Academy cheer: "Nailed it!"
- After a win: "You win! I'd high-five you, but I'm a shield."

### Snark: Sarcastic, but always on your side

- Idle: "Oh look, another day of me doing all the remembering."
- Alert: "Oh, would you look at that. {title}"
- All clear: "Nothing's on fire. Try to keep it that way."
- Fixed: "Look at you, fixing things. I'm almost impressed."
- Academy cheer: "Okay, I'm impressed. A little."
- After a win: "Not bad. Don't let it go to your head."

### Grumpy: Whiny, but gets it done

- Idle: "Ugh. Mondays. Also every other day."
- Alert: "Ugh, of course. {title}"
- All clear: "Nothing to do. Now I'm bored. Thanks a lot."
- Fixed: "Fixed? Huh. Okay. Thanks, I guess."
- Academy cheer: "Hmph. Correct."
- After a win: "You passed. I'm not crying, you're crying."

### Sleepy: Always tired, never misses a thing

- Idle: "*yawn* I'm awake. Mostly."
- Alert: "Huh?! I'm up! {title}"
- All clear: "All clear... perfect time for a nap."
- Fixed: "Fixed! Now we can both nap."
- Academy cheer: "Ooh, correct! *yawn*"
- After a win: "You did it! Now we both deserve a nap."

### Hype: Over-the-top excited about everything

- Idle: "LET'S GOOO! Another day of crushing it!"
- Alert: "TIME-OUT! Big play needed: {title}"
- All clear: "PERFECT GAME! Nothing to fix!"
- Fixed: "FIXED! Touchdown! Goal! Home run!"
- Academy cheer: "BOOM!"
- After a win: "HUGE WIN! That's how champions train!"

### Cap'n: A pirate with a heart of gold

- Idle: "Ahoy, matey! The seas be calm today."
- Alert: "Arr! Trouble on the horizon: {title}"
- All clear: "Calm seas, matey. Nothing to fix!"
- Fixed: "Arr! Ye fixed it! Have some treasure!"
- Academy cheer: "Aye, correct!"
- After a win: "Mission accomplished, Cap'n!"

### Your Majesty: Dramatic, fancy and very royal

- Idle: "One is watching the deadlines. One is magnificent."
- Alert: "Royal alarm! The kingdom needs you: {title}"
- All clear: "The kingdom is at peace. Splendid!"
- Fixed: "Splendid! You are hereby knighted!"
- Academy cheer: "Splendid!"
- After a win: "Victory! The kingdom celebrates you!"

### Robo: Beep boop, very logical

- Idle: "BEEP BOOP. ALL SYSTEMS NOMINAL."
- Alert: "ALERT. ALERT. {title}"
- All clear: "ALL CLEAR. Beep boop."
- Fixed: "Issue resolved. Excellent work, human."
- Academy cheer: "CORRECT. Beep!"
- After a win: "MISSION COMPLETE. Beep boop!"

### Chef: Cooks up everything with food puns

- Idle: "Bonjour! Today's special: a fresh plate of zero fines!"
- Alert: "Something's burning! {title}"
- All clear: "All clear! The kitchen is spotless."
- Fixed: "Chef's kiss! Fixed!"
- Academy cheer: "Delicious!"
- After a win: "Bon appetit! You passed!"

### Sleuth: A mystery-solving detective

- Idle: "The case of the missing deadline? Solved. It was in the calendar all along."
- Alert: "A new case has opened: {title}"
- All clear: "No cases today. Quiet in the city."
- Fixed: "Case closed! Brilliant work, partner."
- Academy cheer: "Elementary, my dear learner!"
- After a win: "Case closed! Brilliant work!"

### Zen: Calm, peaceful and wise

- Idle: "Breathe in. Breathe out. Your deadlines are safe."
- Alert: "A small wave on a calm sea: {title}"
- All clear: "All is calm. All is clear."
- Fixed: "Balance restored. Well done."
- Academy cheer: "Wise answer."
- After a win: "Well done. Your mind is strong."

### Professor: Curious and full of fun facts

- Idle: "Fun fact: some of the oldest written laws are almost 4,000 years old."
- Alert: "A matter worth studying right away: {title}"
- All clear: "Everything is in order. A+ work."
- Fixed: "Correct solution! Gold star."
- Academy cheer: "Precisely."
- After a win: "Splendid. You've mastered this one."

---

## Appendix D: Every web address the app answers

| Method | Address | What it is |
|---|---|---|
| GET | `/` | Landing page |
| GET | `/api/stats` | User counts and the last 30 days of usage counts for MTRX Horizyn's console (only with `STATS_KEY`, and only to that key) |
| GET | `/app` | HQ, the overview |
| GET | `/app/academy` | Academy home for grown-ups |
| GET | `/app/academy/<int:learner_id>` | A learner's map |
| POST | `/app/academy/<int:learner_id>/armo` | A learner's Armo personality |
| GET | `/app/academy/<int:learner_id>/certificate` | The learner's certificate |
| GET | `/app/academy/<int:learner_id>/progress` | A learner's progress report, for the workspace's grown-ups |
| POST | `/app/academy/<int:learner_id>/delete` | Remove a learner |
| POST | `/app/academy/<int:learner_id>/devices/sign-out` | Sign a learner out on every device |
| POST | `/app/academy/<int:learner_id>/duels` | Challenge a friend to a duel |
| GET, POST | `/app/academy/<int:learner_id>/duels/<int:duel_id>` | Play or view a duel |
| GET | `/app/academy/<int:learner_id>/friends` | Friends and duels |
| POST | `/app/academy/<int:learner_id>/friends/<int:friend_id>/remove` | Remove a friend |
| POST | `/app/academy/<int:learner_id>/friends/add` | Enter a friend code |
| POST | `/app/academy/<int:learner_id>/friends/code` | Make a friend code |
| POST | `/app/academy/<int:learner_id>/join-code` | Make a join code for a kid's device |
| GET, POST | `/app/academy/<int:learner_id>/practice` | Practice missed questions |
| GET, POST | `/app/academy/<int:learner_id>/track` | Pick or change a learner's track |
| GET | `/app/academy/<int:learner_id>/world/<int:world_number>` | A world's stages |
| GET, POST | `/app/academy/<int:learner_id>/world/<int:world_number>/stage/<int:stage>` | Play a level (lesson and quiz) and grade it |
| POST | `/app/academy/learners` | Add a learner |
| GET | `/app/academy/plan` | The Academy plan |
| POST | `/app/academy/plan/checkout` | Start Stripe Checkout |
| POST | `/app/academy/plan/manage` | Open the Stripe customer portal |
| GET | `/app/armo` | Armo's page: everything he found |
| POST | `/app/armo/personality` | Pick Armo's personality |
| GET | `/app/armo/status` | Armo's live status feed (JSON) |
| GET | `/app/audit` | Vault, the audit trail |
| GET | `/app/audit.csv` | The audit trail as CSV |
| GET | `/app/industry/<int:industry_id>` | One industry's ten checks |
| POST | `/app/industry/<int:industry_id>/bulk` | Update several checks at once: done today, Yes, No or one date |
| POST | `/app/industry/<int:industry_id>/rule/<rule_key>` | Save, clear, Done today or change a limit on one check |
| GET | `/app/notifications` | Radar, every reminder email |
| GET | `/app/report` | Intel, the compliance report |
| GET | `/app/report.csv` | The report as CSV |
| GET | `/app/settings` | Armory, settings |
| POST | `/app/settings/company` | Company name, timezone and industries (owners) |
| POST | `/app/settings/delete` | Delete the workspace (owners) |
| POST | `/app/settings/invite` | Invite a teammate (owners) |
| POST | `/app/settings/member/<int:user_id>/remove` | Remove a teammate (owners) |
| POST | `/app/settings/reminders` | Choose one's own reminder emails: daily digest, time-limit alerts (and the weekly Autopilot report, for the operator's account) |
| POST | `/billing/stripe/webhook` | Stripe webhook (signed) |
| GET | `/apple-touch-icon.png`, `/apple-touch-icon-precomposed.png` | The icon phones ask for at the root |
| GET | `/favicon.ico` | Favicon |
| GET, POST | `/forgot` | Ask for a password reset link |
| GET | `/healthz` | Health check for uptime monitors |
| GET | `/help` | Help: 15 questions and answers |
| GET | `/industries` | List of all 50 industries |
| GET | `/industries/<slug>` | Public page for one industry |
| GET, POST | `/kids` | A kid enters a join code |
| POST | `/kids/leave` | A kid device leaves the Academy |
| GET, POST | `/login` | Sign in |
| POST | `/logout` | Sign out |
| GET | `/privacy` | Privacy page: what is collected, who sees it, how long it is kept, how to delete it |
| GET, POST | `/reset/<token>` | Set a new password from a reset link |
| GET | `/robots.txt` | robots.txt |
| GET, POST | `/signup` | Sign up (or accept an invite) |
| GET | `/sitemap.xml` | sitemap.xml |
| GET | `/static/<path:filename>` | CSS, scripts and icons |
| GET | `/terms` | Terms page: the rules for using OmniArmor |

---

## Appendix E: Every setting

Settings are environment variables (copy `.env.example` to `.env`, or set them in the host's dashboard).

| Setting | Default | What it does |
|---|---|---|
| `SECRET_KEY` | random in development; required in production | Signs sessions. Generate with `python3 -c "import secrets; print(secrets.token_hex(32))"`. |
| `OMNIARMOR_ENV` | development | Set to `production` to require a secret key, mark cookies Secure and trust one proxy hop. |
| `BASE_URL` | http://localhost:8000 | The public address, used in emails and links: `https://omniarmor.<your domain>`, the subdomain on MTRX Horizyn's domain. |
| `DOMAIN` | (none) | For docker-compose only: the domain Caddy gets an HTTPS certificate for. |
| `DATABASE_PATH` | instance/omniarmor.db | Where the SQLite database lives. Use a persistent disk. |
| `BACKUP_DIR` | a `backups` folder next to the database | Where daily backups go. |
| `BACKUP_KEEP` | 14 | How many backups to keep. |
| `SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD` | empty, 587 | Email provider. Without SMTP_HOST, emails are saved in Radar instead of sent. |
| `SMTP_STARTTLS` | 1 | Use STARTTLS with the email provider. |
| `MAIL_FROM` | OmniArmor <no-reply@localhost> | The sender of every email. |
| `DAILY_JOB_HOUR_UTC` | 11 | The hour (UTC) after which the daily job runs. |
| `SCHEDULER_ENABLED` | 1 | Run the built-in timer inside the app: time-limit alerts, the daily job and Autopilot. It runs in the server only (gunicorn or `flask run`), never in a one-off `flask` command. |
| `AUTOPILOT_ENABLED` | 1 | Run Autopilot every 10 minutes. |
| `OPERATOR_EMAIL` | (none) | Where Autopilot emails big problems. Without it, they go to the server log. The account with this address also sees the usage counts in Settings. |
| `ERRORS_EMAIL` | (none) | One inbox for a short report of each server error, with no personal data: one per distinct error an hour, at most 20 a day (section 6.6). Without it, none are written or sent. |
| `SUPPORT_EMAIL` | (none) | An address people can write to for help, named in the Help page's last answer. Without it, the page points to the help inside the app. |
| `STATS_KEY` | (none) | Turns on `/api/stats` (user counts and daily usage counts, nothing about anyone) for the owner's MTRX Horizyn console. Set it to the same value as the console's `MTRX_STATS_KEY`, and point the console's `OMNIARMOR_STATS_URL` at `https://omniarmor.<your domain>/api/stats`. |
| `TRUSTED_PROXIES` | 1 in production, 0 otherwise | How many reverse proxies sit in front of the app, for the real client address. |
| `SESSION_COOKIE_SECURE` | on in production | Send the sign-in cookie only over HTTPS. |
| `WEB_CONCURRENCY, WEB_THREADS` | 1, 8 | Server processes and threads (Docker image). |
| `ACADEMY_TRIAL_DAYS` | 14 | Length of the Academy's free trial. |
| `ACADEMY_PRICE_LABEL` | (none) | The price shown on the Academy plan page, for example "$9 a month". |
| `ACADEMY_STRIPE_PRICE` | (none) | The Stripe price id for the Academy plan. |
| `STRIPE_SECRET_KEY` | (none) | Stripe secret key. Without it (and the price), the plan is switched by hand. |
| `STRIPE_WEBHOOK_SECRET` | (none) | Stripe webhook signing secret, for `/billing/stripe/webhook`. |

---

## Appendix F: Glossary

- **Check**: one of the 500 compliance rules a company tracks, for example "Annual vehicle inspection".
- **Reading**: what a company enters for a check: a number, Yes or No, or a date.
- **Cleared / Warning / Blocked**: the three answers a check gives. "No reading" means nothing has been entered.
- **Policy check**: a check whose limit comes from an industry standard or common policy rather than law; a company can set its own limit.
- **Days since / days until**: the two ways a date-tracked check counts.
- **Done today**: the button that restarts a recurring duty's cycle.
- **Window**: one of the reminder stages (30, 7 and 1 days out, due today, overdue each week).
- **Digest**: the daily reminder email.
- **Time-limit alert**: the email an hour or minute clock sends when it reaches its warning point, and when it becomes overdue.
- **Workspace**: one company's account, with its owners and members.
- **HQ, Intel, Vault, Radar, Academy, Armory**: the overview, report, audit trail, reminder log, Academy and settings.
- **Armo**: the shield mascot and helper.
- **Learner**: a child in the Academy (a nickname and a picture).
- **Track**: Launchpad, Trailblazer, Summit or Titan Mastery.
- **World, unit, stage, level**: a world is a topic; worlds are grouped in units; each world has stages; a level is one stage of one world on one track.
- **Boss round**: every tenth stage, with extra questions.
- **Rule Quest**: an Academy world built from one industry's ten checks.
- **Owner's Challenge**: the boss world where certificates are earned.
- **Join code**: a one-time code that puts the Academy on a kid's own device.
- **Friend code**: a one-time code that connects two learners from different families.
- **Autopilot**: the 10-minute health pass that fixes small problems and emails big ones.
- **Fingerprint**: how the bug finder tells one bug from another: the kind of error plus where in the code it happened.
- **Operator**: whoever runs the OmniArmor service (as opposed to a customer company).

