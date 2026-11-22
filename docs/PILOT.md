# Pilot on OmniArmor

Pilot is the MTRX Horizyn AI assistant. It runs on **the person's own AI key**, from their browser:
OmniArmor never sees the key or the conversation, has no Pilot address on its server, and pays
nothing for the AI. The shared core (**Pilot core 1.2.1**) is the same in every MTRX Horizyn app and is
described in full in the MTRX Horizyn site's `docs/PILOT.md`: the robot and the window, keys and
providers, what is sent and to whom, confirm cards and plans, voice, memory, the moving robot, and the
security rules. This page covers only what is OmniArmor's own.

## Who gets Pilot, and where

Pilot is for grown-ups: business owners and their teams, and teachers. `omniarmor_app/pilot.py`
lists its pages, by endpoint; anything not listed has no Pilot.

| Who | Pages |
|---|---|
| Visitors | the landing page, Industries and each industry page, `/for/*`, `/classrooms`, the teacher guide, the demos page |
| A business | Home (with each industry page), Report, History, Reminders, Settings (with Plans) |
| A teacher (a school's workspace) | Home (classes), Checklist (with each industry page and the report), Reminders, History, Settings (with Plans) |

**Never** on a page a student uses: the Academy's lessons, map, results, practice, certificates and
class page, and the kids' join page (every `academy.*` and `kids.*` endpoint and `classes.my_class`),
whoever is signed in, and never on a kid's device, even on a public page. The config
(`static/pilot-omniarmor.js`) is a second lock: its `kidView()` is true on any `/kids` or
`/app/academy/<student>` address, or whenever it can't tell who is there, and then Pilot doesn't start.
Pilot is also left off sign-in, password, Help, legal, error and class-roster pages.

When the account in a tab changes (someone signs out, or a kid uses the device next), the config
forgets the last person's chat and any key kept for that tab only.

## The files

| File | What it is |
|---|---|
| `static/pilot/` | the core 1.2.1, copied unchanged from the MTRX Horizyn site: 13 files, the two robot pictures, the robot's three layers (`pilot-rest-body/head/eyes.webp`) and the `poses/` folder |
| `templates/_pilot.html` | the one script tag (included by `base.html`, left out by `error.html`), with the server's facts |
| `pilot.py` | the provider hosts for the security policy, the page lists, the facts on the tag, and the pose pictures (`POSES`, `poses()`) |
| `static/pilot-omniarmor.js` | the config: OmniArmor's own welcome for each audience (`tagline`, `welcomePills`), screens, suggestions, the AI key and 18+ note, `hideKeySections`, `kidView()`, `avoid`, `yieldTo`, `keepInViewport` and `gutter` |
| `static/pilot-omniarmor-pack.js` | the knowledge pack, the "why it's better" list and OmniArmor's tools, loaded on first open |

The tag carries: who is there (`visitor`, `business` or `teacher`), whether it's the demo or a
read-only workspace, an opaque account mark (a keyed hash), the workspace's checklists (ids and
names, for the tools), the compatible hosts, the plans' names and prices from `plans.py`, and the
moving robot's files (`data-motion`, `data-actor`, `data-actor-css`, `data-rest-body`, `data-rest-head`,
`data-rest-eyes`) with `data-poses`, the pose pictures in `static/pilot/poses/` (`pilot.poses()`, so a new
pose is added by putting its picture there). Never a
person's name, an email, a business record or a student. The pack never types a price.

## The robot on OmniArmor

The core robot is smaller on phones (56 px), and once the page is idle it comes to life: it
breathes and blinks, and now and then waves, does a small trick or strolls near its corner and back.
It keeps still while its window is open, and under `prefers-reduced-motion` the moving robot isn't
even fetched (`pilot.js` checks before loading `pilot-motion.js` and `pilot-actor.js`). Like Pilot
itself, it is never on a page a student uses.

Since core 1.1.1 (OmniArmor 1.12.0) the robot keeps off the page's own words and buttons wherever the
page is scrolled to, and off a box being typed in. While the page scrolls it only checks its own spot
(and tucks away there if words are under it); once scrolling stops it may move to a free corner. With no
free corner it tucks away until tapped. Since core 1.2.0 (OmniArmor 1.14.0, `keepInViewport: true`) tucked
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
- `gutter: ["main > .wrap"]` (1.14.0): on a phone the page's column keeps the core's side room (30 px,
  for the small tucked-away robot), so line ends stop before it. `main` itself has no side padding; its
  `.wrap` does, so that is the column. (1.13.0 had `gutter: false`, when the robot never tucked on a phone.)
- No `modals`: OmniArmor has no pop-ups that aren't marked as dialogs (Armo's bubble is a helper's, and is
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

**OmniArmor's own welcome** (1.14.0, core 1.2.0's `tagline` and `welcomePills`; the owner approved
app-specific pills on websites). The config picks it from who is there (`data-who` on Pilot's tag):

| Who | Tagline | Pills |
|---|---|---|
| A business | Your checklist helper | What's due or overdue?, Explain this check, Summarise my report, What does this colour mean?, Add my AI key |
| A teacher | Your classroom helper | Add students, How do join codes work?, Plan a week of lessons, Print certificates, Add my AI key |
| A visitor on `/classrooms` or the teacher guide | Your classroom helper | Is it safe for students?, How does the free trial work?, Plan a week of lessons, Explain this page, Add my AI key |
| Any other visitor | Your checklist helper | What does OmniArmor do?, Which checklist fits me?, Which plan fits me?, Explain this page, Add my AI key |

Questions are sent at once (each has a tool or the pack's answer); "Explain this check" and "Add
students" put a prompt in the box to finish (the check's name; first names only). "Explain this page" is
the core's `explain-screen` and "Add my AI key" opens key settings. The taglines fit on one line at
320 px. A pill pressed before there is a key stays waiting in the box and is sent once a key is saved (the
core). The picture and video key sections are hidden (`hideKeySections`): Pilot here has no use for them.

The chat window shows OmniArmor's own suggestions for the page under the pills, leaving out any that
asks what a pill already asks (so nothing shows twice), and all of them first once a chat has started
("Add students", "How do join codes work?", "What's overdue?" and the page's own). It keeps the 18+ note
above the message box, so a phone's keyboard never hides it. OmniArmor's note says in one sentence what
an AI key is and where a grown-up gets one.

The page keeps its last lines clear with the core's gutter: on a signed-in page the body keeps room
above the tab bar for Armo or `--pilot-gutter`, whichever is more; on a public page the footer keeps
`--pilot-gutter` free under its last line.

## The security policy

`connect-src` adds exactly the MTRX Horizyn site's provider list (`pilot.PROVIDER_HOSTS`,
`pilot.COMPATIBLE_HOSTS`, and `http://localhost:*` / `http://127.0.0.1:*` for a local model),
`media-src` adds `blob:` (a video made with the person's own key), and the Permissions-Policy allows
`microphone=(self)` for voice. Nothing else was widened: scripts, styles, fonts and pictures stay
this site's own, and no page loads anything from another company. Cores 1.1.0, 1.1.1, 1.2.0 and 1.2.1 needed nothing new: the
moving robot's files and pictures come from this site, it moves with the Web Animations API, and
1.1.1 only reads the page's own layout (`elementsFromPoint`).

## The tools

They work through OmniArmor's own pages and forms, in the browser, with the person's own session
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
the bulk-answer rule, first names only, and OmniArmor's own welcome for each audience).
`tests/test_pilot_welcome.py` checks the stylesheet's keepInViewport rules and the phone rules of 1.13.0.
