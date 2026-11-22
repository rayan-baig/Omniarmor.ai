# Changelog

What changed in OmniArmor, in plain words, newest first. The version number
lives in `omniarmor_app/version.py`; the Settings page and `/healthz` show it.

## 1.14.1 (22 November 2026)

- **Pilot core 1.2.1**, the same files as the MTRX Horizyn site. Opening
  Pilot in the first few seconds of a visit, while the robot is being
  shown off, no longer pulls the robot out of its corner. On a phone
  OmniArmor's own rule for that moment now uses the core's new name for
  it, so it still holds the robot whole there. Nothing else changes.

## 1.14.0 (21 November 2026)

Pilot core 1.2.0, and a Pilot welcome made for OmniArmor.

- **Pilot greets you with your own questions.** A business owner sees
  "Your checklist helper" and five buttons: What's due or overdue?,
  Explain this check, Summarise my report, What does this colour mean?
  and Add my AI key. A teacher sees "Your classroom helper" with Add
  students, How do join codes work?, Plan a week of lessons, Print
  certificates and Add my AI key. Visitors get the questions for the side
  of the site they are looking at: running a business, or schools.
- **Nothing you ask is lost before there is an AI key.** A question
  typed or pressed with no key yet stays in the box, the key settings
  open, and it is sent the moment a key is saved.
- **No buttons twice.** The page's suggestions under the welcome leave out
  any that asks what a button already asks; they all come back once you
  are chatting.
- **No picture or video key settings.** Pilot here answers in words and
  works your checklist, so only chat keys are offered.
- **The robot never hangs off the screen.** When it steps aside for the
  page, it shrinks into its corner, fully on the screen. On a phone it
  stays in its one corner, 3 pixels from the edge and above the tab bar,
  and the page's text leaves room beside it. On the first page of a visit
  it shows whole for a few seconds so you notice it.
- **The phone rules stay:** one helper in one corner, Armo first while his
  badge has a count, nothing while you type, and Pilot is never on a page
  a student uses.

## 1.13.0 (21 November 2026)

Fixes from a strict fourth review: codes for students added later, a
teacher's Settings without the business checklist, one lesson count, one
helper on a phone, and smaller things.

- **Students added after the codes were printed get a code.** The join
  codes page and the class page say "2 students have no code yet" with
  **Make codes for them**, which makes codes only for those students: the
  slips already handed out keep working. **Make new codes for everyone**
  is still there, apart, and says plainly that the old slips stop working.
  A student who has joined on a device doesn't need a code again.
- **One notice after adding students**, not three: what was added, what to
  check below and what wasn't added.
- **A teacher's Settings is a school's.** It says "School", not "Company",
  and has no Locations. On the free trial or Classroom it doesn't list the
  54 industries or reminder emails about checks and clocks (those come
  with Whole school, and saving keeps the school's checklist as it is). On
  Whole school it shows the school's own two checklists and the daily
  digest.
- **One lesson count per track.** The Academy home, the track picker, its
  detail, the learner's map and the progress report all count the business
  lessons only (Launchpad 90, Trailblazer 350), and show the workspace's
  Rule Quests apart as "+1 Rule Quest".
- **One helper in one corner on a phone.** Armo shows while his badge has a
  count (something needs doing, and he goes straight to it); Pilot shows
  the rest of the time. Either one sits whole in the bottom-right corner,
  above the tab bar, never half off the screen, and neither shows while
  you type. Pilot's own files are unchanged.
- **The report fits a phone:** each check is a card, with its status on
  top and every column labelled, the Due date among them.
- **A compact demo bar on a phone:** the step and the next page on one
  line, the rest folded under "About this demo".
- **The shop demo leads with ShopArmor**, in its menu and its tour, with
  PayArmor after it. On another checklist's page (HRArmor in the salon
  demo) the demo bar names that page's own checklist.
- **The daily goal counts passes only.** A failed try never says "Daily goal
  reached", and the result says "Not this time. Read the cards again, then
  try again".

## 1.12.0 (21 November 2026)

Fixes from a strict third review: the school checklist stays out of a
teacher's pages until Whole school, the helpers keep off the content, honest
Academy counts, full names checked with the teacher, and many smaller things.

- **A teacher on the free trial or Classroom no longer sees the school
  checklist anywhere.** Armo doesn't count its checks or offer "Fix it" for
  them, Reminders doesn't point at them, the Report isn't the school's
  compliance report, and Pilot doesn't know the checklist. Opening the
  checklist's page goes back to the classes, with a plain note that it comes
  with Whole school. On Whole school it all comes back, with any readings.
- **Armo talks like a teacher's helper on a teacher's pages:** add students,
  print the join codes, the teacher guide and the trial report.
- **Armo keeps out of the way.** His bubble opens when you tap him. By
  itself it opens at most once a day, and only on a screen wide enough for
  it to sit beside the page, never over it, so most days you see just his
  badge. A tap anywhere else closes it. On a phone he waits tucked at the
  left edge with his badge showing, and comes out when tapped.
- **Pilot's robot keeps clear of more.** It never sits on a status tag (No
  reading, Blocked and the rest), a Top 5 badge, the Kitchen Safety Bundle
  note, a check's message, a notice at the top, Armo's badge or bubble, or
  the "First name only?" card: it moves to a free corner or tucks half away
  until tapped. Pilot now uses Pilot core 1.1.1: it keeps off the page's
  words and buttons wherever you scroll, and off a box you're typing in. On
  a phone, when there's no free corner, it tucks away at the edge with a
  slice showing, and the page keeps a little room at the sides for it, so
  it no longer covers text on the home page or the "No reading" tags. Its
  18+ note now sits above the message box, so a phone's keyboard never
  hides it.
- **Pilot's own suggestions.** Once you're chatting, OmniArmor's own
  suggestions come first, on every page Pilot is on: for a teacher "Add
  students", "How do join codes work?" and "What's overdue?" (or "Plan a
  week" without the school checklist); for a business "What's overdue?" and
  the page's own. The window keeps the design's five buttons.
  Pilot's key settings now say in one sentence what an AI key is and where a
  grown-up gets one.
- **Honest Academy counts.** Each track leads with its business lessons:
  Launchpad 90, Trailblazer 350, Summit 296, Titan Mastery 224, and the
  Academy home says "Up to 350". A learner's count adds the Rule Quests of
  the workspace's own industries only; the other industries' Rule Quests are
  optional extras on the map, and aren't counted.
- **Every lesson teaches what it asks.** A lesson after the first starts with
  a short card for each of its questions, before the quiz, instead of one
  recap card. The first lesson stays short: anything its cards didn't cover
  is added to its last card.
- **No true "wrong" answers.** Rules nearly every business follows (keeping
  hours records, fire extinguisher checks, card payments, personal data) are
  never offered as the wrong answer to "which is your company's rule?", and
  "Who has to follow ...?" says "Any business with employees" for an
  employer's rule. A new script, tools/quiz_truth_review.py, checks every
  lesson for these patterns, and a test runs it.
- **Honest result headings.** "So close!" only when you were one short of a
  pass. Below that: "Good start", "Keep going" or "Not this time", and Armo
  doesn't say "so close" either.
- **Full names are checked with the teacher.** A name like "Ava Thompson"
  isn't added straight away: the class page asks "First name only?",
  suggests "Ava T", and keeps only what the teacher picks ("it's all first
  name", like Mary Jane, is there too, and so is "Don't add").
- **A demo for each trade.** "See a demo" on the salon, tattoo studio, gym
  and shop pages opens a pretend salon, studio, gym or shop with its own
  checklist, not the restaurant.
- **The right words on entries.** A food batch says "Made or opened", a
  pedicure tub "Cleaned", a sterilizer "Tested", an AED "Checked". Adding an
  entry with a name already in the list is refused with a friendly message.
- **Who each email went to.** Reminders shows "To you (the owner)" or "To a
  team member" beside each email, never an address.
- **Plain words for countdowns.** A license with 41 days left says "41 days
  left before the deadline", not "close to the 0 days minimum", and a late
  one "3 days past the deadline". Other warnings say where the warning
  starts.
- **Error reports read right with a virtual environment inside the project
  folder:** a library's file is still shown from the library, not as a
  project path.

## 1.11.1 (21 November 2026)

- **Pilot updated to the newest version: smaller on phones, steps aside for
  Armo, and comes to life with small moves.** Pilot's robot now uses Pilot
  core 1.1.0. It is smaller on phones. While Armo is talking, the robot moves
  to a free corner by itself, and it never sits on a Blocked status or
  Armo's "Fix it" bubble. Now and then it blinks, waves or takes a short walk
  near its corner, and it keeps still while its window is open. If your
  device is set to reduce motion, it stays still. It is still never on a
  page a student uses.

## 1.11.0 (20 November 2026)

Fixes from a strict second review: honest Academy lessons, harder quizzes,
deeper business checklists, three new trade starter lists, and a tidier
teacher side.

- **Every Academy world asks each question once.** The family tracks now work
  like the Classroom track: each world is a fixed set of questions cut into
  lessons, and no question comes back in a later lesson of that world. A
  retry asks the same lesson's questions with the answers in a new order.
  Fourteen lessons used to ask 16 different questions between them; now
  they ask 70.
- **Honest level counts.** A track's count is its real lessons: Launchpad
  630, Trailblazer 890, Summit 836 and Titan Mastery 764 (they used to say
  1,360 to 15,750, with the same few questions over and over). Summit and
  Titan have longer lessons, the hard questions first and higher pass marks,
  so they have fewer, bigger lessons. Each Rule Quest has one lesson per real
  rule, and the last lesson of a world is its boss round. Stages a world no
  longer has stay in the database but don't count.
- **New questions where a world was thin.** Meet Your Company, Why Rules
  Matter, Countdown Calendar, Money Smarts and Lead the Team got about 70 new
  business-basics questions and facts.
- **Quizzes that can't be guessed.** The wrong answers in the Classroom and
  family lessons were rewritten to be believable (no more "Inside a closet
  nobody opens"), answer lengths were balanced, and a new test checks across
  every question that the longest (or shortest) answer is right only as often
  as chance, and that always picking it passes no more lessons than guessing.
- **A grade band for classrooms.** The Classroom track says who it is written
  for, Grades 4–6 (ages 9 to 12), on /classrooms, in the teacher guide and in
  the classroom demo.
- **Checks with one entry per item.** The 7-day date marking holds one entry
  per food batch or container, and cold and hot holding one reading per unit,
  each with its own value and deadline; the check shows the worst one, and
  the report lists each entry. A value saved before stays, as the first
  entry ("Fridge 1").
- **An illness log.** "Sick employees kept off work" keeps its Yes-or-No
  answer (Yes is still the bad one, and a bulk update never answers Yes) and
  gains a dated log of who reported what and what was done, by first name or
  initials only. A report that means going home (vomiting, diarrhea,
  jaundice or a diagnosis) can't be marked "restricted".
- **Starter lists for salons, tattoo studios and gyms.** SalonArmor, InkArmor
  and GymArmor, ten checks each (licenses and permits, disinfecting and
  sterilizer logs, sharps, chemical safety, AEDs, pool chlorine and more),
  each citing its source and saying where local rules vary. Their trade
  pages lead with them. 54 industries and 540 checks in all.
- **Teacher side.** The Checklist tab and the school checklist's first steps
  (the cafeteria check among them) show only on Whole school. "Pilot" now
  means only the robot assistant: the classroom offer is the "free trial"
  everywhere, and its report the "Trial report". A classroom student's
  progress says "Class Challenge", never "Owner's Challenge". A new class
  starts with its leaderboard off; classes already made keep theirs.
- **Armo and Pilot keep apart.** Armo moved to the bottom-left corner, the
  page keeps room at the bottom for both helpers, and while Armo is talking
  Pilot's robot steps aside, so only one helper shows at a time.
- **Where student names go.** Before the Allow card for adding students,
  Pilot says the names go to the teacher's own AI provider, with a "Type them
  myself instead" link to the class page.

## 1.10.1 (20 November 2026)

- **Pilot core 1.0.1.** The shared core no longer writes the word "null" under Pilot's buttons
  once a key is set, so OmniArmor's own tidy-up for it is removed.

## 1.10.0 (20 November 2026)

Pilot, the MTRX Horizyn assistant, comes to OmniArmor. It runs on your own
AI key.

- **Pilot, for grown-ups.** The round robot in the corner opens Pilot's
  window, the same as on the MTRX Horizyn site: "Your AI copilot. Powered by
  you." It is on the public pages (the landing page, industries, the trade
  pages, the Academy for schools, the teacher guide and the demos), on a
  business's Home, Report, History, Reminders and Settings, and on a
  teacher's Home, Checklist, Reminders, History and Settings. It is never on
  a page a student uses: not the lessons, the map, the results or the kids'
  join page, and never on a kid's device.
- **Your own key, from your browser.** Add a key from Anthropic, OpenAI,
  Google Gemini or a compatible service under the gear. It stays in your
  browser and goes only to that company; OmniArmor never sees it or the
  chat, and your AI company bills your key. AI keys are for grown-ups.
- **It knows OmniArmor.** Ask how checks and reminders work, what each
  status and colour means, what a check's "Rule and source" says, what the
  plans include (with the app's real prices), or how a teacher signs up, adds
  students and runs the pilot. It says OmniArmor is decision support, not
  legal advice, and can say honestly what OmniArmor does well.
- **It can help, and asks first.** Signed in, it can tell you what's due or
  overdue, explain a check and its rule, and summarise your report. After you
  press Allow, it can mark a check done today, update a check, set a reminder
  date, answer several yes-or-no checks at once (never Yes where Yes means a
  problem) and, for a teacher, add students by first name. It never changes a
  plan, deletes anything, invites or removes people, or touches a student's
  account.
- **Privacy.** Pilot never reads people's names from your team list or the
  audit trail, and forgets the chat when someone else signs in or out in the
  tab. The privacy page and the terms describe Pilot.
- **Still nothing from other companies.** The fonts stay on OmniArmor's own
  server. The security policy adds only the AI companies' addresses, for the
  browser to reach the one you chose.

## 1.9.0 (19 November 2026)

Fixes from an honest product review: OmniArmor for a classroom feels made
for a classroom, and a small business finds its own trade first.

- **Lessons made for a class.** Students in a class learn on a new
  Classroom track, through a pretend class business, a lemonade stand
  called Sunny Cup Lemonade. They are never asked about "your family's
  company", a school is never a wrong answer, and nothing is about the app
  itself or a school's profit. The track leaves out the family worlds, the
  app's lights and reminders, hiring and firing, taxes, loans and the
  industry Rule Quests. Each world is a fixed set of questions in lessons of
  five, so no question comes back in a later lesson: 16 worlds and 107
  lessons, counted honestly. Families keep their own tracks as they were.
  Students already in a class move to the Classroom track; what they
  finished still counts in the class view and the pilot report.
- **A teacher guide** at /classrooms/guide, to read or print: what each
  world teaches, how long it takes, and questions to talk about.
- **A teacher's own sign-up.** Name, school email, password and school
  name: no list of industries. It says "30-day free pilot" and starts the
  pilot straight away, so there is one countdown.
- **A school's own workspace.** The top bar shows the school's name, not
  "SchoolSafetyArmor". The plan page shows only Classroom and Whole school
  with the pilot's days left, never Pro, Plus or the Kitchen Safety Bundle.
  Signing in lands on the classes page.
- **Two audiences kept apart.** "Schools" in the top menu leads to the
  Academy for schools, and the schools page leads to the classroom demo,
  with the school's own prices. The Kitchen Safety Bundle shows only on the
  restaurant pages and for workspaces CyberLogix can help. The landing
  page shows two prices instead of four.
- **Small businesses first.** The industries page and the sign-up start
  with restaurants, bars, salons, child care, dental offices, construction
  and shops; every other industry is still there, under "More industries
  (starter lists)".
- **No dead end without online payment.** "Contact us" is now an email
  link, to SUPPORT_EMAIL or help@mtrxhorizyn.com when it isn't set, and
  Help and Settings always give an address.
- **Adding students keeps what you typed.** The names that can be added
  are added; the others are listed with the reason and put back in the box.
  A name typed twice no longer says it is "already in this class".
- **Plain menu names:** Home, Report, History, Reminders, Academy and
  Settings (they were HQ, Intel, Vault, Radar and Armory).
- **Smaller fixes.** "Why it matters" appeared twice on a check: the
  second is now "Rule and source". Money shows its cents ($15.50, not
  $15.5). After "Done today" on a 7-day check, the message no longer
  promises a 30-day reminder. "Answer Yes" for several checks at once no
  longer gives Yes to a check where Yes is a problem (a sick employee
  working, signs of pests). The join page speaks to teachers too. The
  result screen no longer shows "0 of 5 right" while counting up. On a
  phone, Armo is smaller and slides out of the way while you scroll.
- **Students' privacy: fonts from our own server.** The pages no longer
  load fonts from Google, so no outside company sees a student's or anyone
  else's visit. Ten small font files (196 KB in all, only the weights the
  pages use; a browser loads only what a page needs), and the security
  policy now allows fonts from this site only.

## 1.8.0 (19 November 2026)

Fast and solid: lighter pages, and the app says quickly when something
stops working.

- **Smaller pages.** Pages, stylesheets and scripts are sent compressed:
  the landing page's first visit goes from 60 KB to 15 KB and the Academy
  map from 227 KB to 36 KB (4.5 seconds to 0.7 on a slow phone
  connection; docs/PERFORMANCE.md). The forms' hidden token now changes on
  every page, so compressed pages give nothing away.
- **Faster as it grows.** Three new indexes for queries that read whole
  tables: Radar (35 ms to 0.2 ms on a year of emails), Autopilot's check of
  failed emails and a workspace's team.
- **A readiness check, `/readyz`.** Besides `/healthz` (the site is up),
  it checks the database, the settings production needs, the two
  background timers, the last daily job, the newest backup and the disk,
  and answers 200 or 503 with only "ok" or "fail" per check.
  `flask --app wsgi ready` on the server says what's wrong and what to do.
- **Watchdogs for the timers.** Each timer writes "last ran at" every
  round. Autopilot emails the owner if the every-minute timer stops, and
  the every-minute timer emails if the 10-minute one (which runs
  Autopilot) stops.
- **Fail soft.** When the database can't be reached, pages say "That's
  unavailable for a moment" (a 503 that asks to retry in a minute) instead
  of "something went wrong". A connection to Stripe cut off half way now
  says "try again in a minute" instead of showing the error page, and a
  Stripe call that fails before Stripe answers is tried once more, safely
  (each one carries an idempotency key). Stripe and email each wait at most
  20 seconds.
- **Start-up checks.** In production the app refuses to start with
  `SECRET_KEY` or `BASE_URL` missing, or email or Stripe half set up, and
  the log lists each setting with what to put in it. A setting that should
  be a number, or a database that can't be opened, is said plainly too.
- **"If the app is down"** in docs/OPERATIONS.md: the two addresses to give
  a free uptime monitor, and what each alert means, step by step.

## 1.7.0 (17 November 2026)

The first five minutes, for a small business owner and for a teacher.

- **See a demo, no sign-up.** "See a demo" on the landing page and the
  trade pages opens a pretend restaurant: a few checks done, one overdue,
  this morning's reminder in Radar and a report ready to print. The
  Academy for schools page opens a classroom demo: a sample class with
  pretend first names, the class progress view, join codes and a sample
  lesson to try. A bar on every demo page says it is pretend data, walks
  through the pages in order and ends with "Start your free trial".
- **The demo keeps nothing and sends nothing.** Each page of a demo works
  on its own fresh copy of the demo data, made in memory and thrown away
  afterwards, so nothing reaches the real database. Forms say "nothing is
  saved in the demo" instead of saving (the sample lesson's quiz still
  gives its result). No email or reminder is ever sent from a demo. A demo
  lasts 30 minutes, its data is rebuilt every hour from today's date, and
  one address can open it 20 times an hour.
- **Getting started on HQ.** A short list replaces the first-day list:
  pick your checklists, complete your first check, set your first
  reminder, then invite a teammate or choose your reminder emails. Each
  step ticks itself from what is saved, has a button for the next action,
  and the list goes away when all four are done. Accounts made before this
  version don't get the last step back.
- **"Reminder set".** Saving a date on a check now says when the reminder
  emails go out (30, 7 and 1 day before the due date, and on the day), or
  that an overdue check is in the weekly reminder.
- **Getting started for teachers.** The classes page has its own list:
  start the free pilot, create a class, add students, share the join
  codes, and a student's first lesson. Signing up from the Academy for
  schools page now lands on the classes page, not the school checklist.
- **Sign-up is clearer.** "Business or school name" instead of "Company
  name", the free trial and "no card needed" said up front, a box to find
  your industry among the 51 by typing, and the industries you came with
  listed first. On a brand-new industry page, "Update several at once" is
  folded away and one line says where to start.
- **No blank screens.** Every screen a new workspace or class can open
  empty (HQ, Only problems, Radar, the report, the team, the Academy,
  classes, a class, join codes, certificates, the class report and a
  learner's progress) says in one sentence what will show there, with a
  button for the next step.
- **Phones.** A long reminder subject in Radar no longer pushes the page
  sideways, the first lesson's card no longer makes the page wider while it
  slides in, and the demo bar is shorter on a phone.
- **A stricter Content Security Policy.** The progress bars and meters now
  get their widths from classes, not style attributes, so the policy no
  longer allows any inline style.

## 1.6.2 (17 November 2026)

More from the pre-launch review: plans, pauses, locations and classrooms.

- **A pause with no end date.** A pause set in Stripe's dashboard without a
  day to start again used to leave the workspace fully on while nothing was
  charged. Now it is paused like any pause (read-only, no reminders) until
  the pause is lifted, and every screen says "paused, with no end date".
  Start again now still works.
- **Stripe's customer portal.** OPERATIONS.md now lists the exact portal
  settings: switching only between Pro and Plus monthly, never to yearly
  (the plan page does that, and refuses while the save offer's discount
  runs), never the bundle prices, Classroom or Whole school. If a switch to
  yearly still comes in from the portal while the discount runs, the yearly
  charge has already been made with it and the app can't take it back, so
  it writes it in the audit trail and the log for the operator to settle.
- **Certificates agree.** A class's certificates page shows every
  certificate each student has earned, on any track, the same ones the
  class view counts. A student who changed track no longer loses one.
- **At most 100 classes in a workspace**, and up to 20 added an hour.
- **One free trial and one classroom pilot per owner.** A location added in
  Settings starts without a trial: the owner chooses a plan for it, and the
  Add a location box says so. The pilot can be started once, in any one of
  the owner's locations, and deleting that location and adding another
  doesn't bring it back.
- **A plan set by hand with `--until` ends at 23:59:59 that day in the
  workspace's own timezone**, not in UTC (which ended a New York school's
  plan at 8 pm).
- **No plan set by hand over a running Stripe subscription.** The `plan`
  command (and the old `academy-plan`) refuses with a clear message unless
  `--force` is given: Stripe would go on charging, and its next update would
  replace the plan set by hand.
- **From invoice to card.** A school on an invoiced plan can set up its card
  for the same plan before the plan ends ("Pay by card from ..."): the first
  card charge is the day the invoiced plan ends, so it never pays twice. The
  old "Use Manage billing" message, which led nowhere for an invoiced plan,
  now says whom to write to.
- **Deleting one location keeps you signed in**, in another of your
  locations. Deleting your last one signs you out, as before.

## 1.6.1 (17 November 2026)

Fixes from a review of the plans, the pause, the save offer and the
classroom plans before launch.

- **Starting a paused plan again early now bills from that day when a
  renewal was skipped.** A pause cancels the renewals that fall inside it.
  Starting again by hand right after one of them used to run free until the
  next renewal, and pausing again just before it made every month free.
  Now, when a renewal fell inside the pause, starting again starts a new
  month of billing that day (nothing prorated). Starting again inside the
  month paid for before the pause still charges nothing extra.
- **No switch to yearly while the save offer's discount runs.** The discount
  is on the subscription for its months, and Stripe takes it off every
  invoice then, so switching to yearly took it off a whole year's charge.
  The yearly offer comes back when the discount's months are over. Moving
  up to Plus is unchanged.
- **Buying a plan after a plan set by hand has ended.** A plan set by hand
  stops on its end date (`--until`, or cancelled to its renewal date), but
  checkout still said "You already have a plan" for good. It now opens once
  the plan has ended, for Pro, Plus and the classroom plans.
- **A plan set by hand with an end date stops on that date even after an
  old card subscription.** A school that paid by card one year and by
  invoice the next kept the old, cancelled Stripe subscription's id, so the
  end date was never applied and the plan ran on. Setting a plan by hand
  now lets go of a subscription that is over (the Stripe customer is kept);
  a subscription still running is left alone.
- **A paused plan no longer tells the Academy "every track and every
  world".** Its paid worlds are locked while paused; the Academy now shows
  its free worlds, as without a plan.

## 1.6.0 (16 November 2026)

OmniArmor for schools: a school safety checklist, and the Academy for classrooms.

- **SchoolSafetyArmor**, industry 51: ten checks for a K-12 school's routines,
  each a reminder to do something and write it down: fire and lockdown drills
  (every 30 days), AED and first-aid kits (30), playground and gym equipment
  (30), the nurse's medication log and fridge (7), the cafeteria's
  food-safety check (7), bus and van pre-trip sheets (7), concussion forms and
  heat checks (yes or no, each season), the visitor sign-in log (7), science
  lab chemical storage (90) and staff background-check renewals (days until
  due, warning from 45). Every limit is a policy a school can set to its
  state's. It sits beside SchoolArmor (industry 8), a school's legal duties.
  51 industries and 510 checks now; the Academy gains a Rule Quest for it
  (Launchpad 1,360 levels, Trailblazer 2,710, Summit 5,420, Titan 15,750).
- **The Schools page** at `/for/schools`: both school checklists and the HR
  basics, which come with reminders, what OmniArmor doesn't cover, that
  CyberLogix AI can watch the nurse's office and cafeteria fridges 24/7, and
  the Academy for classrooms. It helps a school stay on top of its
  checklists; it doesn't promise compliance. In the sitemap and the "By
  trade" list.
- **The Academy for classrooms.** A teacher adds a class and its students by
  first name or nickname only: no email, birthdate or photo, and a name that
  looks like an email is refused. The class view shows each student's
  lessons done and the class total; one button makes join codes for the
  whole class to print. Students in a class have no friends or duels; they
  see their own class's leaderboard, which the teacher can switch off, and
  never another class.
- **Certificates of completion** with the student's first name or nickname,
  the class and the school, one or the whole class at once, each on its own
  landscape page.
- **A free 30-day classroom pilot**, once per workspace, no card
  (`CLASSROOM_PILOT_DAYS`), and a one-page **pilot report** for the school
  office: students, lessons finished and topics covered, totals only.
- **Classroom plans**, yearly: **Classroom, $299 a year** (one class of up to
  35 students, the whole Academy) and **Whole school, $1,490 a year** (every
  class, and the compliance tracker for the school). Classroom is the
  Academy's share of Plus for a year ($300), a dollar under, with no
  tracker; Whole school costs more than a year of Plus and less than five
  Classrooms. By card (`CLASSROOM_YEARLY_STRIPE_PRICE`,
  `SCHOOL_YEARLY_STRIPE_PRICE`) or by invoice (`SCHOOL_INVOICE_EMAIL`): the
  `plan` command takes `classroom` and `school`, and `--until` for the last
  day of a school year. A plan set by hand with an end date now stops on it.
- **The Academy for schools and teachers** at `/classrooms`, linked from the
  home page and the Schools page. Help has a short answer on classes.
- **Privacy:** two plain sentences on what a class keeps and who sees the
  class leaderboard (last changed 16 November 2026). Terms say 51 industries.
- **Usage counts** for the operator: classroom pilots started, students added
  to classes and pilot reports opened.
- **Schema version 21** adds the `classes` table, `learners.class_id`, and
  `orgs.pilot_started_at` and `pilot_ends_at`.
- **Set-up:** `.env.example`, `render.yaml`, the README, the handbook and
  OPERATIONS.md, section 7, "Upgrading to 1.6.0": create the two yearly
  prices in Stripe, or sell by invoice.

## 1.5.0 (15 November 2026)

Pause instead of cancel, upgrade offers, locations and trade pages.

- **Pause instead of cancel.** The plan page's "Cancel or pause your plan"
  opens a cancel screen for the owner. A plan paid monthly can be paused for
  1, 2 or 3 months, for a slow season or a renovation: Stripe stops charging
  (`pause_collection`, invoices voided until the chosen day), reminders and
  alerts stop, and the workspace is read-only like the no-plan mode, with
  everything kept. Every page, Settings (beside the reminder choices) and the
  plan page say so, with the date. It starts again by itself on that day;
  the daily job emails each owner 3 days before, and "Start again now" ends
  it early. Stripe's webhook keeps the pause in step both ways.
- **A one-time save offer** on the same screen: 25% off the next 2 months by
  default, at most once per workspace, ever. The coupon is a setting,
  `SAVE_OFFER_STRIPE_COUPON`, and the amount the screen promises is
  `SAVE_OFFER_PERCENT` and `SAVE_OFFER_MONTHS`; no coupon, no offer.
- **Cancel stays one click** ("Cancel my plan", in the same row as the
  offers): it cancels at the end of the time paid for, and "Keep my plan"
  takes it back before then. Stripe's portal still cancels too.
- **Switch to yearly, 2 months free:** monthly payers see the offer on the
  plan page (and a link in Settings) with what they save. A paid Pro can
  switch to Plus there too. Both use the existing Stripe prices; Stripe
  charges the difference at once and a declined card changes nothing.
- **Upgrade offers** (`nudges.py`), for owners only, at most one a week per
  person, and "No thanks" is for good: a workspace on Pro opening the
  Academy sees a peek at a lesson and "Plus includes the Academy", and
  tapping a locked world shows that world's first lesson; an owner who adds a
  second location sees what paying yearly saves for all their locations.
- **Locations:** an owner adds a location in Settings (a new workspace with
  the same industries and timezone, its own team, plan and trial) and
  switches between locations there.
- **Trade pages** at `/for/<trade>`: salons and barbershops, tattoo and
  piercing studios, gyms and fitness studios, and shops. Each names the
  OmniArmor checklists that fit, which checks have reminder emails, what
  OmniArmor doesn't cover for that trade, and the price, with a title and
  meta description, in the sitemap and on the industries page. Sign-up from a
  trade page picks its checklists.
- **Usage counts** for the operator: plans paused, save offers taken, plans
  cancelled, upgrade offers shown, plan switches and locations added.
- **Terms:** one sentence, a monthly plan can be paused for up to 3 months
  (last changed 15 November 2026). Privacy and Help say what pausing and the
  offers keep and do.
- **Schema version 20** adds `orgs.paused_until`, `paused_at`,
  `pause_reminded_at` and `save_offer_used_at`, and the `nudges` table.
- **Set-up:** `.env.example`, `render.yaml`, the README, the handbook, the
  staging guide and OPERATIONS.md, section 7, "Upgrading to 1.5.0": create
  the coupon in Stripe and set `SAVE_OFFER_STRIPE_COUPON`.

## 1.4.0 (14 November 2026)

Yearly plans: pay for 10 months, get 12.

- **The yearly prices** are worked out in `omniarmor_app/plans.py` from the
  monthly ones, `MONTHS_PAID_YEARLY` (10) months for a year: **Pro, $500 a
  year per location**; **Plus, $800 a year per location**; and Plus for a
  Kitchen Safety Bundle workspace, **$300 a year**, ten months of the
  difference. The pages call it "2 months free" (`free_label()`). Nothing
  types a yearly price: the plan page, Settings, Help, the Terms, the
  landing page and the industry pages read them from `plan_facts()`, and the
  test that bans typed prices still passes.
- **A Monthly / Yearly switch** on the plan page and on the landing and
  industry pages' plan summary: two radio buttons and CSS, no script, so the
  strict CSP is unchanged. `/app/plan?billing=yearly` opens it on Yearly, and
  so does the plan page of a workspace already paying yearly. Each card's
  button ("Choose Plus yearly") sends the interval to checkout.
- **Stripe:** three new settings, `PRO_YEARLY_STRIPE_PRICE`,
  `PLUS_YEARLY_STRIPE_PRICE` and `PLUS_BUNDLE_UPGRADE_YEARLY_STRIPE_PRICE`.
  Checkout sends the yearly price with the location count and writes the
  interval in the metadata beside the plan. The webhook works out the plan
  *and* the interval from the subscription's price (`academy_plan.plan_for`),
  else from the price's recurring interval or the metadata, so switching
  between monthly and yearly (or Pro and Plus) in Stripe's portal arrives by
  itself. A yearly setting left empty hides the yearly option for that plan;
  with none set, no page mentions yearly. A bundle workspace whose yearly
  upgrade price isn't set is offered Plus at the full yearly price, with a
  note.
- **Cancelling:** Stripe's portal handles it, as before. Help (under "What
  does it cost?") and the Terms say it plainly: a yearly plan stays on to
  the end of the year paid for, with no partial refund. Settings and the
  plan page say "billed yearly", and a cancelled yearly plan says when its
  year ends. When the plan ends, the compliance tracker is read-only as
  before.
- **Schema version 19** adds `orgs.plan_interval` (`month` or `year`); every
  subscription already there is monthly. `flask --app wsgi plan <id> plus
  --yearly` sets a yearly plan by hand.
- **Set-up:** `.env.example`, `render.yaml` (`sync: false`), the README,
  the handbook, the staging guide and OPERATIONS.md, section 7, "Upgrading to
  1.4.0": create 3 yearly prices in Stripe, put their ids in the settings,
  and let the customer portal switch between the monthly and yearly prices.

## 1.3.1 (14 November 2026)

- **The real address, omniarmor.mtrxhorizyn.com.** The README, the operations,
  staging, costs and CyberLogix connection guides, the handbook's sample emails,
  `.env.example` (`BASE_URL`, `DOMAIN`, `MAIL_FROM`) and the comments in
  `render.yaml` name it instead of a placeholder, with
  `help@omniarmor.mtrxhorizyn.com` suggested for `SUPPORT_EMAIL` and
  `no-reply@omniarmor.mtrxhorizyn.com` for sending. The app still reads every
  address from its settings; `BASE_URL` and `MAIL_FROM` stay dashboard settings
  in `render.yaml`, so a staging copy never inherits live's address.

## 1.3.0 (14 November 2026)

Paid plans: a free trial, then Pro or Plus per location, with the Kitchen
Safety Bundle's Pro included for CyberLogix customers.

- **The plans** (`omniarmor_app/plans.py`, the one place prices live):
  a free trial of everything in Plus for `ACADEMY_TRIAL_DAYS` days (14 by
  default) from sign-up, no card; **Pro, $50 a month per location**, the
  compliance tracker; **Plus, $80 a month per location**, everything in Pro
  and the whole Future Owner Academy. The Academy's first worlds stay free
  for everyone. The plan page (now `/app/plan`; the old address redirects),
  Help, Settings, the landing page, the industry pages and the Terms all
  read them from `plan_facts()`, and a test fails if any template types a
  price.
- **A location is a workspace.** A workspace holds one site (one timezone,
  one reading per check, one CyberLogix report a day), so each subscription
  bills `location_count()`, 1, as its quantity. A company with several sites
  makes a workspace for each.
- **Stripe:** the Academy plan's checkout, webhook, portal, past-due handling
  and replay guards now serve every plan. Checkout sends the plan's price
  (`PRO_STRIPE_PRICE`, `PLUS_STRIPE_PRICE`) with the location count, and
  writes the plan in the metadata. The webhook sets the workspace's plan from
  the subscription's price, so a switch between Pro and Plus in Stripe's
  portal arrives by itself; repeated and older events are still ignored.
  `ACADEMY_PRICE_LABEL` and `ACADEMY_STRIPE_PRICE` are no longer read.
- **Without a plan, read-only.** When the trial ends with no plan, every
  record can still be seen, printed and downloaded and nothing is deleted,
  but checks can't be saved (single, bulk, limits) and the industry pages
  show no Save buttons. Reminder digests and time-limit alerts pause; nothing
  is marked reminded, so they pick up when a plan starts. A banner on every
  page says why and links to the plans. Exporting and deleting the workspace
  always work. CyberLogix reports are still taken.
- **The Kitchen Safety Bundle includes Pro.** A workspace that received a
  validly signed CyberLogix report in the last 3 days gets Pro at no charge,
  and Settings says "Pro included with your Kitchen Safety Bundle". When the
  signed reports stop, a 7-day grace period follows with a banner, then the
  trial-ended rules. A covered workspace can add Plus for the difference,
  $30 a month per location (`PLUS_BUNDLE_UPGRADE_STRIPE_PRICE`); without
  that price set it is offered Plus at full price, with a note.
- **The signature:** CyberLogix signs bundle reports with
  `X-CyberLogix-Signature: t=<unix seconds>,v1=<hex HMAC-SHA256(secret,
  "<t>." + raw body)>` and the shared `KITCHEN_BUNDLE_SECRET`. OmniArmor
  checks it over the raw body bytes in constant time, refuses a `t` more than
  300 seconds off, and remembers each accepted signature for 10 minutes so a
  replay doesn't count. An unsigned, wrong, stale or replayed report, or any
  report while the secret is unset, is processed exactly as before and just
  doesn't count. The answer says which (`signature`, `bundle_counted`).
  docs/CYBERLOGIX-CONNECTION.md, section 3.5, is the spec.
- **The old Academy plan** is kept as it was: a workspace paying for it
  keeps the whole Academy and the compliance tracker at its old price until
  it changes plan or the subscription ends.
- **Schema version 18:** `orgs.plan` and `orgs.bundle_report_at`, and the
  `bundle_signatures` table. Workspaces paying for the Academy are marked as
  on the old plan; every other workspace gets the trial from the day of the
  upgrade (a later Academy trial end is kept). docs/OPERATIONS.md, section 7,
  lists the Stripe set-up to do before deploying.
- `flask --app wsgi plan <workspace id> pro|plus|none` sets a plan by hand;
  `academy-plan <id> active` now means Plus.
- The Privacy and Terms pages say how the plans, the read-only state and the
  bundle work, in plain words.

## 1.2.0 (13 November 2026)

The Kitchen Safety Bundle: CyberLogix, MTRX Horizyn's fridge and freezer
alarm app, fills in OmniArmor's temperature checks from its own readings.

- **Settings, Connections:** the workspace owner creates a CyberLogix
  connection key, shown once and stored only as a hash (like invite links),
  and can regenerate or revoke it. One active key per workspace. Everyone on
  the team sees the status; only the owner changes the key.
- **`POST /api/connect/cyberlogix/daily`:** CyberLogix sends each day's
  summary with the key as a Bearer token. Every field is checked, and
  breaches carry roles ("on-call staff"), never names. Rate-limited per key
  and per address, and wrong keys are limited harder. It is exempt from the
  form token only because the key, not the cookie, signs it in.
- **A clean day ticks the check:** every unit in range all day saves the
  day's warmest reading on the workspace's temperature-log check (RestoArmor's
  "Cold holding at 41°F or below") through the same code as a person's Save,
  shown in the audit trail as "From CyberLogix: 7 of 7 units in range all
  day". **A breach ticks nothing:** it adds a note to the check, such as
  "CyberLogix: 1 breach on Walk-in freezer, 02:10–02:45, peak 41°F",
  until someone marks it reviewed.
- Sending the same day twice changes nothing. A corrected report replaces
  the note, and never takes away or overwrites a reading someone on the team
  saved that day or later. A workspace with no temperature check gets
  `matched_checks: 0` and a hint.
- The temperature checks and Settings show "Kitchen Safety Bundle: let
  CyberLogix fill this in automatically" until connected, then "Connected to
  CyberLogix · last report <date>".
- **docs/CYBERLOGIX-CONNECTION.md:** the contract the CyberLogix side builds
  against: the key, the body with examples, responses and error codes,
  idempotency, rate limits, and what ticks versus what adds a note.
- Schema version 17 adds `connection_keys` and `connection_reports`. The
  upgrade needs no step.
- The Privacy page says what a connection sends: temperature summaries,
  unit names and roles, no names.

## 1.1.3 (3 November 2026)

A staging copy, and a setting that keeps it out of search results.

- **docs/STAGING.md:** how to run a second copy on Render at
  `staging.omniarmor.<domain>`, with its own disk, database and secrets, mail
  that reaches nobody, Stripe in test mode, the demo workspace seeded with
  its backups in a folder of its own, and a checklist for taking a tested
  commit to live. It is set up by hand, not in `render.yaml`, so syncing the
  live Blueprint never touches it.
- **`NOINDEX=1`**, for a copy that is not the live one: every address
  (public pages, files and robots.txt included) says
  `X-Robots-Tag: noindex, nofollow`, every page has the noindex tag and no
  share previews, robots.txt closes the whole site and the sitemap is empty.
  Unset, nothing changes. Leave it unset on live.
- A test of the workspace's dates failed on 3 November 2026 (UTC): the date
  fields' `max` is today, which matched the UTC date it checks is absent. It
  ignores that attribute now.

## 1.1.2 (3 November 2026)

A security fix: operator status comes from the server, not from an email
address.

- The operator's account (the one that sees the usage counts and the weekly
  Autopilot report's switch in Settings) was any account with the
  `OPERATOR_EMAIL` address. Sign-up doesn't verify addresses, so a stranger
  who registered that address first, say on a new deployment before the
  owner signed up, got the operator's view and could turn the weekly report
  off. Now it is a flag on the account that only
  `flask --app wsgi make-operator EMAIL` sets, run on the server. It refuses
  any address but `OPERATOR_EMAIL`, prints the account's creation date, name
  and workspace so the owner can check it is theirs, keeps one operator at a
  time, and `--revoke` takes it away. The flag counts only while the
  account's address is still `OPERATOR_EMAIL`.
- **One step after upgrading:** the upgrade (schema version 16) gives nobody
  the flag, not even an account that already has the operator's address,
  because the database can't tell who made it. Run
  `flask --app wsgi make-operator <the OPERATOR_EMAIL address>` once
  (docs/OPERATIONS.md, sections 5 and 7). Until then the usage counts and
  the weekly report's switch are hidden, and the weekly report goes out.
- Emails to `OPERATOR_EMAIL` (problems, the weekly report) go to that inbox
  as before: they need no account.
- Autopilot's "Bug:" emails carried the error's message and traceback as
  they were. They are now scrubbed like the error reports to `ERRORS_EMAIL`:
  email addresses, IP addresses, tokens, secrets and reset or invite links
  are replaced, and file paths are relative.

## 1.1.1 (3 November 2026)

Two fixes from a review of the last day's changes.

- The demo workspace keeps its backups in a folder of its own beside the
  demo file. Seeded next to the live database, as for production
  (`--force /data/omniarmor-demo.db`), its backup went into the live backup
  folder, where the live daily job took it for that day's backup and made
  none of its own, and the newest copy to restore was the demo.
- The built-in timer runs only in the server (gunicorn or `flask run`), never
  in a one-off command such as `flask --app wsgi backup`, `autopilot` or
  `seed-demo`. Those started it too, against the live database, and ended
  with its sweeps half done: a time-limit alert claimed and never sent, or a
  digest half sent and sent again later.
- A test of the workspace's dates used a join code that expired at a fixed
  moment (3 November 2026, 02:30 UTC) and failed from then on; it uses a
  code that is still valid.

## 1.1.0 (3 November 2026)

For selling it and running it: a demo workspace, error reports to one inbox,
privacy-friendly usage counts, and Settings that answer the basics.

- A demo workspace in one command: `flask --app wsgi seed-demo`. A made-up
  community pharmacy tracking Pharmacies and Employers & HR, with checks
  done, coming due and overdue, weeks of audit trail, two Academy learners
  partway through (one with a certificate) and a running Autopilot. It
  prints the sign-in details, and it refuses any database that holds an
  account, a workspace or a learner, and in production the app's own
  database altogether: `--force` names a new file instead.
- Error reports to one inbox: set `ERRORS_EMAIL` and each server error
  sends a short report (time, version, method, path without its query,
  error and a stack trace with relative paths) with no personal data, at
  most once an hour per error and 20 a day. It goes through the outbox, so
  Autopilot retries it when mail is down. Autopilot's own bug emails are
  unchanged.
- Usage counts: one total a day for checks updated, bulk updates, lessons
  started and passed, certificates, Help page views and sign-ups, with no
  cookie, no ids and no outside service. The operator sees the last 30 days
  in Settings, and MTRX Horizyn's console in `/api/stats` (schema version
  15). The Privacy page says so.
- Settings shows the Academy plan to everyone on the team, not only the
  owner, says the compliance tracker is free, and under About says where to
  get help: the Help page, and `SUPPORT_EMAIL` when it is set.

## 1.0.1 (3 November 2026)

Reliability under load. Measured in `docs/LOAD-TEST.md`.

- A load test (`tools/load_test.py`) of 500 workspaces using the app at once,
  against gunicorn as the Docker image runs it, and timings of the scheduled
  sweeps at 100, 500 and 2,000 workspaces. No errors, no lost changes and no
  locked database; one server process slows down past about 100 requests a
  second.
- No sweep runs twice at once. A daily run that took over an hour, or an
  Autopilot pass that ran past its 10 minutes, could be started again by a
  second server process beside it and send the same emails twice. Each sweep
  now holds a lock in the database while it runs (schema version 14).
- The time-limit alerts have a thread of their own, so a long daily run never
  holds up a 15-minute clock's alert.
- The daily backup is taken after the day's reminders. Restoring the morning's
  backup used to send everyone that day's digest again.
- A 10-minute restore checklist in docs/OPERATIONS.md, rehearsed end to end
  and by a test.
- The handbook is current: bulk entry, the Help page, the progress report,
  reminder choices, the plan page, `SUPPORT_EMAIL` and every web address.

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
