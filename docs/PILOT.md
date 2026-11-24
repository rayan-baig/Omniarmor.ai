# Pilot on Aegizyn

Pilot is the MTRX Horizyn AI assistant. It runs on **the person's own AI key**, from their browser:
Aegizyn never sees the key or the conversation, has no Pilot address on its server, and pays
nothing for the AI. The shared core (**Pilot core 1.4.3**, since Aegizyn 1.22.0; 1.4.2 since 1.20.0, 1.4.1 since 1.18.0, 1.4.0 since 1.17.0) is the same in every MTRX Horizyn app and is
described in full in the MTRX Horizyn site's `docs/PILOT.md`: the robot and the window, keys and
providers, what is sent and to whom, confirm cards and plans, voice, memory, the moving robot, and the
security rules. This page covers only what is Aegizyn's own.

## Who gets Pilot, and where

Pilot is for grown-ups: business owners and their teams, and teachers. `omniarmor_app/pilot.py`
lists its pages, by endpoint; anything not listed has no Pilot.

| Who | Pages |
|---|---|
| Visitors | the landing page, Industries and each industry page, `/for/*`, `/classrooms`, the teacher guide, the demos page, and (1.25.0) Pricing, Help and Security |
| A business | Home (with each industry page), Report, History, Reminders, Settings (with Plans) |
| A teacher (a school's workspace) | Home (classes), each class's page and its join codes, the teacher guide (1.15.0), Checklist (with each industry page and the report), Reminders, History, Settings (with Plans) |

**Never** on a page a student uses: the Academy's lessons, map, results, practice, certificates and
class page, and the kids' join page (every `academy.*` and `kids.*` endpoint and `classes.my_class`),
whoever is signed in, and never on a kid's device, even on a public page. The config
(`static/pilot-omniarmor.js`) is a second lock: its `kidView()` is true on any `/kids` or
`/app/academy/<student>` address, or whenever it can't tell who is there, and then Pilot doesn't start.
Pilot is also left off sign-in, password, the terms and privacy pages, error pages, and a class's certificates and report.
On a teacher's class page and join codes (1.15.0) every student's name (the progress table, the codes,
the "First name only?" card, the names not added, the Manage list and the teacher's notices) is marked
`data-pilot-private`, so "Analyze & explain" and "Summarise" never send one.

When the account in a tab changes (someone signs out, or a kid uses the device next), the config
forgets the last person's chat and any key kept for that tab only.

## The files

| File | What it is |
|---|---|
| `static/pilot/` | the core 1.4.0, copied unchanged from the MTRX Horizyn site: 13 files, the two robot pictures, the robot's three layers (`pilot-rest-body/head/eyes.webp`) and the `poses/` folder |
| `templates/_pilot.html` | the one script tag (included by `base.html`, left out by `error.html`), with the server's facts |
| `pilot.py` | the provider hosts for the security policy, the page lists, the facts on the tag, and the pose pictures (`POSES`, `poses()`) |
| `static/pilot-omniarmor.js` | the config: Aegizyn's own welcome for each audience (`tagline`, `welcomePills`, and since 1.17.0 the answers and links that need no AI key, `answerMore`), screens, suggestions, the AI key and 18+ note, `hideKeySections`, `kidView()`, `avoid`, `yieldTo`, `keepInViewport` and `gutter` |
| `static/pilot-omniarmor-pack.js` | the knowledge pack, the "why it's better" list and Aegizyn's tools, loaded on first open |

The tag carries: who is there (`visitor`, `business` or `teacher`), whether it's the demo or a
read-only workspace, an opaque account mark (a keyed hash), the workspace's checklists (ids and
names, for the tools), a teacher's classes (ids and names only, 1.17.0, for the join codes answer and
the certificates link), the join code's days and the join page's address, the compatible hosts, the plans' names and prices from `plans.py`, and the
moving robot's files (`data-motion`, `data-actor`, `data-actor-css`, `data-rest-body`, `data-rest-head`,
`data-rest-eyes`) with `data-poses`, the pose pictures in `static/pilot/poses/` (`pilot.poses()`, so a new
pose is added by putting its picture there). Never a
person's name, an email, a business record or a student. The pack never types a price.

## The robot on Aegizyn

The core robot is smaller on phones (56 px), and once the page is idle it comes to life: it
breathes and blinks, and now and then waves, does a small trick or strolls near its corner and back.
It keeps still while its window is open, and under `prefers-reduced-motion` the moving robot isn't
even fetched (`pilot.js` checks before loading `pilot-motion.js` and `pilot-actor.js`). Like Pilot
itself, it is never on a page a student uses.

Since core 1.1.1 (Aegizyn 1.12.0) the robot keeps off the page's own words and buttons wherever the
page is scrolled to, and off a box being typed in. While the page scrolls it only checks its own spot
(and tucks away there if words are under it); once scrolling stops it may move to a free corner. With no
free corner it tucks away until tapped. Since core 1.2.0 (Aegizyn 1.14.0, `keepInViewport: true`) tucked
away means shrunk into its corner (to 0.42 of its size on a phone, 0.5 on a computer), fully on the
screen, never hanging off the edge. On the first page of a visit it shows whole for 4 seconds, so people
notice it, then steps aside as usual.

Armo lives in the bottom-left corner and the robot in the bottom-right on a wider screen. The config tells the core:

- `yieldTo: [".companion"]`: Armo, with his bubble. While Armo's bubble reaches the robot's corner, the
  robot moves to the first free corner, or tucks away. Armo's bubble opens only when tapped (or by
  itself at most once a day, and only beside the content column: see the handbook), so this is rare.
- `avoid: [".tag", ".top-n", ".bundle", ".msg", ".entry-top", ".flash", ".plan-banner", ".ac-badge",
  ".companion-bubble", ".companion-fix", ".companion-badge", "[data-confirm-names]", ".topbar .nav"]`:
  every status tag (No reading, Blocked and the rest), a Top 5 badge, the Kitchen Safety Bundle note, a
  check's message, an entry's name and tag, a flash or banner, a learner's badge, Armo's bubble, "Fix
  it" and badge, the "First name only?" card and the menu at the top (with Sign out) are never covered.
  1.16.0 adds `".lockup"`, a check's "Select" box (`".pick"`) and the teacher guide's lines, headings and list
  items (`"[data-teacher-guide] p"`, `li`, `h2`, `h3`), which the robot still touched.
- `gutter: ["main > .wrap"]` (1.14.0): on a phone the page's column keeps the core's side room (30 px,
  for the small tucked-away robot), so line ends stop before it. `main` itself has no side padding; its
  `.wrap` does, so that is the column. (1.13.0 had `gutter: false`, when the robot never tucked on a phone.)
  1.16.0: on a signed-in page (a tab bar) it is `false` again, because the robot has its own reserved
  corner above the tab bar there (app.css), so the column keeps its own even room.
- No `modals`: Aegizyn has no pop-ups that aren't marked as dialogs (Armo's bubble is a helper's, and is
  in `yieldTo`), and the core already steps back for any page-covering layer.

**One helper, one corner on a phone** (1.13.0, `app.css` only; the core is unchanged). At 720 px or
narrower only one helper shows, always in the bottom-right corner, 12 px in from the edge and above the
tab bar, all of it on the screen:

- **Armo, while his badge has a count.** Something on the checklist needs doing and he goes straight to
  it, so Pilot steps back entirely (`display: none`; a window already open stays open).
- **Pilot, the rest of the time.** Armo with nothing to report steps back (his page is a tap away in
  Settings), unless his bubble is open.
- **Neither while a box of the page is being typed in**, so the keyboard and the box stay clear.

This is the least intrusive of the choices: two helpers at both edges covered line ends on both sides,
and a robot tucked half off the screen (at the top, over the menu, on the returning Home) looked broken.
The core still picks a corner and decides when to tuck; on a phone `app.css` keeps the robot in the one
corner. Tucked away (1.14.0, the core's `keepInViewport`) it shrinks there: 24 px, 3 px from the screen's
edge and just above the tab bar. When the core would move it to another corner (this one is busy) it
shrinks in this one too, rather than sitting whole on the page's words (not during its first look). The
page's bottom room lets its last lines scroll clear of that corner, and its side room keeps line ends
clear of the small robot.

On signed-in pages the tab bar runs along the bottom. `app.css` sets the core's `--pilot-gap` there to
the tab bar's height plus the usual gap (80 px, 76 px on a phone), so the robot sits above the tab bar
and the core measures each corner above the tab bar. The right-hand corners sit 16 px from the edge
(12 px on a phone), so the core's check of an untucked right-hand corner is 64 px to the left of the
robot, which only ever makes it tuck sooner. The core moves the small tucked-away robot by `--pilot-gap`
less its margin; for the right-hand corners on a computer `app.css` counts across from their own 16 px
instead (1.14.0; 1.13.0 did the same for the old tuck with `--pilot-tuck`), so the small robot sits at the
empty right end of the tab bar, 8 px from the edges, exactly where the core checks it.
(The tab bar is always there, so it isn't in `avoid`: the core would count every bottom corner as taken
and send the robot to the top.) The window opens beside the robot, above the tab bar.

**Aegizyn's own welcome** (1.14.0, core 1.2.0's `tagline` and `welcomePills`; the owner approved
app-specific pills on websites). The config picks it from who is there (`data-who` on Pilot's tag):

| Who | Tagline | Pills |
|---|---|---|
| A business | Your checklist helper | What's due or overdue?, Explain this check, Summarise my report, What does this colour mean?, Add my AI key |
| A teacher | Your classroom helper | Add students, How do join codes work?, Plan a week of lessons, Print certificates, Add my AI key |
| A visitor on `/classrooms` or the teacher guide | Your Aegizyn helper (1.15.0) | Is it safe for students?, How does the free trial work?, Plan a week of lessons, Explain this page, Add my AI key |
| Any other visitor | Your Aegizyn helper (1.15.0) | What does Aegizyn do?, Which checklist fits me?, See the prices (1.17.0), Explain this page, Add my AI key |

Print certificates has the paper icon (`copy`), not a chart (1.15.0). Core 1.3.0: the "Add my AI key"
pill is the welcome's one ask for a key (no key card beside it), the key settings say "AI key", and the
welcome's note is one line, `keyNoteShort` "AI keys are for grown-ups (18+)." (the full `keyNote` stays
beside the key settings and in help).

**Core 1.4.1** (Aegizyn 1.18.0, MTRX Horizyn f221ffc, the thirteen files byte for byte): the welcome's pills
come back as a compact row under an answer of the app's own; long answers open at their start; an app's own answer
is never sent to the AI provider (a stand-in keeps the turns); on a phone the robot fades out (`.pilot-away`) rather
than cover a link, a button, a bar that stays put or something in `avoid`, and keeps one bottom corner while the
page is scrolled. Pilot's tag also gives the robot's pictures at the sizes they are drawn (`data-robot-set`,
`data-rest-body-set`, `data-rest-head-set`, `data-rest-eyes-set`; `pilot-robot-112/168/176.webp`,
`pilot-rest-*-112/168.webp`), so it is crisp on phones.

**Core 1.4.2** (Aegizyn 1.20.0, MTRX Horizyn a1c9253, the thirteen files byte for byte, no new pictures). A corner
raised above the tab bar is measured where it is, so signed-in pages drop 1.19.0's `hideWhenCrowded: false` and use
the core's "hide rather than cover" everywhere; `app.css`'s computer rule moves the tucked robot up or down by
`var(--pilot-keep-dy)` (the core's own room), not `var(--pilot-keep-d)`, so it is drawn just above the tab bar,
where it is measured. Hidden with the page still, the core's **handle** (a 44 px slice of the robot at the screen's
edge, only where it covers no link, button, box, bar or anything in `avoid`) opens Pilot; it is on (no `handle`
setting). The suggestion after the page's own is `screenChip: {label: "Explain this page", answer}`: Aegizyn's
built-in look at the page (its headings, what it is for, its counts), with or without a key, instead of the core's
"Summarise this", which needs the AI. **Typed questions with no key**: each pill and suggestion that answers with
no AI has `match` words (`MATCH` in `pilot-omniarmor.js`), so "What needs attention?", "What does red mean?",
"How do I add students?", "Is my data safe?" or "How much does it cost?" get the app's own answer at once, under
"Here's what I can tell you without an AI key:", nothing sent; anything else waits for a key as before. With no
key, a suggestion that asks what a pill asks stayed out even once a chat had started (until 1.22.0, below).

**Core 1.4.3** (Aegizyn 1.22.0, MTRX Horizyn ea7498b, the thirteen files byte for byte, no new pictures). With
no key, a typed question none of Aegizyn's answers fits stays in the chat (the core's `noKeyReply`, in its own
words: "I need an AI key to answer that one. Here's what I can help with right now:"), with this page's
suggestions and the welcome's pills that answer with no key, then "Add my AI key", and the words waiting in the
box. Typing a button's own words always gets its answer. A pill and a suggestion that ask one thing in their own
words share one answer function (`WEEK`, `JOIN`, `dueAnswer` and the rest), so 1.4.3 counts them as one item
(`sameItem`): once chatting, every suggestion is back with or without a key, in the pill's words, and 1.20.0's
no-key workaround is gone. The answers on every grown-up page (`GLOBAL`: is my data safe, what does it cost, is
this legal advice, how do I cancel, how do I export) stay as `chips()` hands them to the core's typed matching
only as a question is sent (`globalFor`): 1.4.3 has no setting for answers that are never buttons. 1.22.0 adds
words to them ("sell", "share", "stored", "cookies"; "refund", "money", "close", "account"; "compliant",
"guarantee", "fined"; "billing"); the core reads at most 20 per item. On the schools pages the cancel answer is
about the school plans only. The phone's side gutter is the core's 34 px.

**1.23.0** adds to `GLOBAL`: "Explain this page" (the header button's own words, typed, get its answer: the core's
typed matching doesn't look at the `screenChip`), and Help's top how-tos: "How do I add a teammate?", "How do
reminder emails work?", "How do I add an industry?" and "How do I delete my workspace?" ("close" and "account" move
there from cancelling: deleting the workspace closes the account, which isn't cancelling the plan, and the answer
says so). "Is my data safe?" starts "No, we don't sell your data." and says where the data is stored, from the
Security page's facts on the script tag (`offsite_backup`, `backup_keep`; `invite_days` for the teammate answer).
On a computer the page's column keeps the robot's corner free (`app.css`), so it shows whole instead of tucking.

**1.25.0**: Pilot is on `/pricing` (Which plan fits me?, What's the Kitchen Safety Bundle?, How do I cancel?), `/help`
(a teammate, the password, reminder emails) and `/security` (is my data safe, deleting the workspace, exporting),
with the visitor's welcome. A page suggestion in the words of a `GLOBAL` answer takes that answer's `match` words
(`withMatch`), so "Can I get a refund?" on the pricing page still finds How do I cancel?. New: "How do I change my
password?" in `GLOBAL` (the emailed reset link; `reset_hours` on the tag); "What's due or overdue?" also matches
"due", "week", "soon", "coming", "next", "month" and "tomorrow"; the export answer also matches "data" and
"records" (two words then beat the safety and delete answers' one). The cancel answer reads the words typed
(`ctx.label`): a refund question starts with the refund. Price answers link to `/pricing`.

**Aegizyn's colours** (1.18.0): the config's `themeClass: "omni-pilot"` puts a class on Pilot's root,
and `app.css` (".pilot-root.omni-pilot") gives the window Aegizyn's warm black with the orange-to-red
edge: core 1.4.1's theming variables (`--pilot-panel-bg`, `--pilot-pill-bg` and the rest) and a few rules of
its own. The core's files are unchanged.

**Armo and Pilot on a phone** (1.15.0): Armo's bubble has **Ask Pilot**, which opens Pilot's window
(`window.Pilot.open()`), since Pilot steps back while Armo's badge has a count. Armo keeps clear of the
page the way Pilot does: `armo.js` (`keepClear`) checks a grid of points under him for controls, status
tags, notices and words, and shrinks him into his corner (`armo-tucked`) where he would cover one; on a
phone (1.16.0) he and Pilot share the corner above the tab bar instead, so the column stays centred. 1.18.0
took away the framed box 1.16.0 drew behind that corner (it covered the page's last lines): the helper sits
whole there only while the corner is free, and steps to the screen's edge (a slice of it still showing) when
it is busy. The picture under the home page's headline and a folded line like "Lost the slips?" are on the
`avoid` list. On a computer (1100 px and wider) the
sections are a side bar, so Pilot's corners there use the core's own 16 px gap.

**Answers with no AI key** (1.17.0, core 1.4.0's pill actions). The pills and suggestions that need no AI
work before a key, with nothing sent anywhere: an `answer` built in the browser from what the page shows
and the facts on the tag, or a `link`.

| Pill or suggestion | What it does with no key |
|---|---|
| What's due or overdue? (and "What's overdue?") | Home: Needs attention (with the totals) and Coming due, a link to each check; an industry page: overdue, blocked or close to a limit, due in 30 days, and how many have no reading; the report: its totals; elsewhere a link to Home |
| Explain this check (and "Explain a check") | on an industry page, the check in the address (`#rule-…`), else the one in view, else the first that needs attention: what it asks, its limit, due date, why it matters, what a miss costs and its rule and source, its status, and "not legal advice"; elsewhere, what a check is and links to the checks that need attention or to the checklists |
| What does this colour mean? | the four statuses, with this page's totals, and a link to Help |
| How do join codes work? | how a student joins (the join page, once, the code's days), the class's student count and missing codes (counts only, never a name), and a link to that class's join codes (or to each class's) |
| Print certificates | a link: the class's certificates on a class page or with one class, else the classes page |
| What does Aegizyn do? / See the prices | an answer from the plans' facts, with links to the demo and the industries / a link to the prices on the Help page |
| Is it safe for students? / How does the free trial work? | answers from the site's own facts, with links to the privacy page and the classroom prices |

**1.19.0: one helper, and the due list everywhere.** On a tablet or a computer (721 px and wider) a page with
Pilot (`#pilot-core`) hides Armo (app.css, "One helper per page"); on a phone they already share one corner.
Where there is no Pilot, Armo sits in the bottom-right corner on a computer, clear of the side bar. What Armo
pointed at comes to Pilot on the tag's `data-due` (pilot.py: Armo's `live_issues`, at most `DUE_ITEMS`: level,
title, checklist and the check's own link; like `data-checklists` it is never sent to the AI by itself), so
"What's due or overdue?" lists the real items with links on every business page: the report, History,
Reminders and Settings too, and an industry page adds what needs attention on the other checklists. A visitor's
answers never link to a signed-in page: "How do reminders work?" points to Help instead of Settings.

**1.18.0: every welcome button answers with no key**; only "Add my AI key" and typed questions need the AI.

| Pill or suggestion | What it does with no key (1.18.0) |
|---|---|
| Which checklist fits me? | asks what kind of business it is, with a link to each trade's page (`trades` on the tag: the industry list's lead trades and the other trade pages) and to every industry |
| Which plan fits me? (and "What do the plans include?") | the plans side by side from the tag's facts (`pro`, `pro_price`, `pro_yearly`, `pro_summary`, the same for Plus; for a teacher or the schools pages, Classroom and Whole school), and which fits whom |
| Explain this page | the screen's name, its heading, what it says it is for (`.page-head .sub`, the lead) and its section headings, never anything marked private |
| Add students (a teacher's) | on a class page: Pilot closes and the Add students box gets the cursor; elsewhere a link to `/app/academy/classes/<id>#add-students` (`page.js` puts the cursor in a form reached by its `#add-…` address) or to each class's, or to add a class first |
| Plan a week of lessons (and "Plan a week") | five days, a world a day, from the Classroom track in order (`class_plan` on the tag: each world's title, lessons and first talk question, from `academy.class_guide()`), with minutes and a link to the teacher guide |
| Summarise my report | on the report: every check counted, the blocked ones to fix first and the next ones close to a limit (each a link: the report's rows carry `data-check` and `data-days`), and the first with no reading; elsewhere a link to the report |
| What's in History? / Export it / Add a reminder / Invite a colleague / Choose my emails / What can I try? | short answers with links |

Some page suggestions answer too (reminders, What's a check?, Is this legal advice?, exporting the report,
Classroom or Whole school, lesson length, Is anything saved in the demo). An answer never reads anything
marked `data-pilot-private` and never lists a student: the class page is counted (`data-total`,
`data-codes-missing`), never its table. Under an answer, "Want more? Add your AI key to ask anything."
(`answerMore`) offers the key until one is added. Once a chat has started, the suggestions end with "Explain this
page" (core 1.4.2's `screenChip`, Aegizyn's own answer), never the core's "Summarise this", which used the AI.

"Add my AI key" opens key settings. The taglines fit on one line at
320 px. A pill pressed before there is a key stays waiting in the box and is sent once a key is saved (the
core). The picture and video key sections are hidden (`hideKeySections`): Pilot here has no use for them.

The chat window shows Aegizyn's own suggestions for the page under the pills, leaving out any that
asks what a pill already asks (so nothing shows twice), and all of them first once a chat has started
("Add students", "How do join codes work?", "What's overdue?" and the page's own). It keeps the 18+ note
above the message box, so a phone's keyboard never hides it. Aegizyn's note says in one sentence what
an AI key is and where a grown-up gets one.

The page keeps its last lines clear with the core's gutter: on a signed-in page the body keeps room
above the tab bar for Armo or `--pilot-gutter`, whichever is more; on a public page the footer keeps
`--pilot-gutter` free under its last line.

## The security policy

`connect-src` adds exactly the MTRX Horizyn site's provider list (`pilot.PROVIDER_HOSTS`,
`pilot.COMPATIBLE_HOSTS`, and `http://localhost:*` / `http://127.0.0.1:*` for a local model),
`media-src` adds `blob:` (a video made with the person's own key), and the Permissions-Policy allows
`microphone=(self)` for voice. Nothing else was widened: scripts, styles, fonts and pictures stay
this site's own, and no page loads anything from another company. Cores 1.1.0, 1.1.1, 1.2.0, 1.2.1, 1.3.0 and 1.4.0 needed nothing new (1.4.0's answers are built in the browser, with no request): the
moving robot's files and pictures come from this site, it moves with the Web Animations API, and
1.1.1 only reads the page's own layout (`elementsFromPoint`).

## The tools

They work through Aegizyn's own pages and forms, in the browser, with the person's own session
and the form token the page carries. A read opens the same pages the person could open; a change
posts the same form they would press, after they press **Allow** on a card that names the exact check.

| Tool | Kind | Through |
|---|---|---|
| `whats_due`, `explain_check`, `summarise_report` | read | each industry page (`/app/industry/<id>`) |
| `what_colour_means` | read | the pack's own words |
| `my_classes` (teachers) | read | the classes page: names and counts, never students' names |
| `mark_done_today`, `update_check`, `add_reminder` | asks first | a check's own form (`action` save or done_today) |
| `answer_checks` | asks first | "Update several at once" (`/bulk`) |
| `add_students` (teachers) | asks first | the class's add-students form, first names or nicknames only |

- **The bulk-answer rule:** Yes is never given to a check where Yes means a problem ("Is a sick
  employee working?") together with others: `answer_checks` leaves those out and says so, and a plan
  of single answers refuses them. The server refuses them too.
- **Never:** the pack can post only three forms (`ROUTES` in the pack), each with only its own
  fields: no plan, payment, deletion, team, invite, limit, clearing or student-account form, and the
  core engine refuses tool names that pay, delete, change plans or message people.
- Read results carry check names, statuses, dates and rules, never who changed what. Adding students
  returns only what the app said, never the class list.

## Tests

`python -m unittest tests.test_pilot` (pages, student pages, the tag and its pose pictures, the moving
robot fetched late and never under reduce motion, keeping clear of Armo, the security policy, the files,
no model names, the privacy page) also runs the Node tests: `node --test tests/js/pilot.test.js`
(the core's own tests, with the moving robot, where it may sit and core 1.2.0's welcome, keepInViewport and
pop-ups) and `node --test tests/js/omniarmor-pilot.test.js` (the pack, confirm first, the forbidden actions,
the bulk-answer rule, first names only, Aegizyn's own welcome for each audience, and 1.17.0's answers
with no key, on small pages built in the test). `tests/test_core140.py` checks the core's version (1.4.3), the
tag's facts and that a student's pages still have no Pilot; `tests/test_round11_fixes.py` checks the 1.4.3 config.
`tests/test_pilot_welcome.py` checks the stylesheet's keepInViewport rules and the phone rules of 1.13.0.
