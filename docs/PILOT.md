# Pilot on OmniArmor

Pilot is the MTRX Horizyn AI assistant. It runs on **the person's own AI key**, from their browser:
OmniArmor never sees the key or the conversation, has no Pilot address on its server, and pays
nothing for the AI. The shared core (**Pilot core 1.1.0**) is the same in every MTRX Horizyn app and is
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
| `static/pilot/` | the core 1.1.0, copied unchanged from the MTRX Horizyn site: 13 files, the two robot pictures, the robot's three layers (`pilot-rest-body/head/eyes.webp`) and the `poses/` folder |
| `templates/_pilot.html` | the one script tag (included by `base.html`, left out by `error.html`), with the server's facts |
| `pilot.py` | the provider hosts for the security policy, the page lists, the facts on the tag, and the pose pictures (`POSES`, `poses()`) |
| `static/pilot-omniarmor.js` | the config: screens, suggestions, the 18+ note, `kidView()`, `avoid` and `yieldTo` |
| `static/pilot-omniarmor-pack.js` | the knowledge pack, the "why it's better" list and OmniArmor's tools, loaded on first open |

The tag carries: who is there (`visitor`, `business` or `teacher`), whether it's the demo or a
read-only workspace, an opaque account mark (a keyed hash), the workspace's checklists (ids and
names, for the tools), the compatible hosts, the plans' names and prices from `plans.py`, and the
moving robot's files (`data-motion`, `data-actor`, `data-actor-css`, `data-rest-body`, `data-rest-head`,
`data-rest-eyes`) with `data-poses`, the pose pictures in `static/pilot/poses/` (`pilot.poses()`, so a new
pose is added by putting its picture there). Never a
person's name, an email, a business record or a student. The pack never types a price.

## The robot on OmniArmor

The core 1.1.0 robot is smaller on phones (56 px), and once the page is idle it comes to life: it
breathes and blinks, and now and then waves, does a small trick or strolls near its corner and back.
It keeps still while its window is open, and under `prefers-reduced-motion` the moving robot isn't
even fetched (`pilot.js` checks before loading `pilot-motion.js` and `pilot-actor.js`). Like Pilot
itself, it is never on a page a student uses.

Armo lives in the bottom-left corner and the robot in the bottom-right. The config tells the core:

- `yieldTo: [".companion"]`: Armo, with his bubble. While Armo is talking and his bubble reaches the
  robot's corner (on a phone), the robot moves to the first free corner, or tucks half away until
  tapped. The robot doesn't wander while Armo is on the page.
- `avoid: [".tag.BLOCKED", ".companion-bubble", ".companion-fix", ".topbar .nav"]`: a Blocked status,
  Armo's "Fix it" bubble and the menu at the top (with Sign out) are never covered. With Armo talking
  on a phone and the menu in view, no corner is free, so the robot tucks half away at the right edge.

On signed-in pages the tab bar runs along the bottom. `app.css` sets the core's `--pilot-gap` there to
the tab bar's height plus the usual gap (80 px, 76 px on a phone), so the robot sits above the tab bar
and the core measures each corner where the robot really is when it checks the list above. (The tab
bar is always there, so it isn't in `avoid`: the core would count every bottom corner as taken and send
the robot to the top.) The right-hand corners keep the usual distance from the edge, and the window
opens beside the robot, above the tab bar.

The page keeps its last lines clear with the core's gutter: on a signed-in page the body keeps room
above the tab bar for Armo or `--pilot-gutter`, whichever is more; on a public page the footer keeps
`--pilot-gutter` free under its last line. Armo's old `armo-talking` stopgap (1.11.0) is gone.

## The security policy

`connect-src` adds exactly the MTRX Horizyn site's provider list (`pilot.PROVIDER_HOSTS`,
`pilot.COMPATIBLE_HOSTS`, and `http://localhost:*` / `http://127.0.0.1:*` for a local model),
`media-src` adds `blob:` (a video made with the person's own key), and the Permissions-Policy allows
`microphone=(self)` for voice. Nothing else was widened: scripts, styles, fonts and pictures stay
this site's own, and no page loads anything from another company. Core 1.1.0 needed nothing new: the
moving robot's files and pictures come from this site, and it moves with the Web Animations API.

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
(the core's own tests, with the moving robot and where it may sit) and `node --test tests/js/omniarmor-pilot.test.js` (the pack, confirm first,
the forbidden actions, the bulk-answer rule, first names only).
