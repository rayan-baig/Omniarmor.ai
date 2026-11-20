// Pilot's knowledge pack for OmniArmor, and OmniArmor's tools.
// Fetched only when someone first opens Pilot. Written from the real app,
// its pages and docs (README.md, help.html, docs/HANDBOOK.md): if something
// here stops being true, change it here (tests/test_pilot.py and
// tests/js/omniarmor-pilot.test.js check the main facts are present).
//
// Prices and numbers are never typed here: they come from the server's own
// plans.py and settings through Pilot's script tag (pilot.py), so the pack
// never states a price the app doesn't charge.
//
// The tools work through OmniArmor's own pages and forms, in this browser,
// with the person's own session and the form token those pages carry: a
// read looks at the same pages the person could open, and a change posts the
// same form the person would press. Only a few forms are allowed at all
// (ROUTES below): Pilot never changes a plan, deletes anything, invites or
// removes team members, or touches a student's account.
(function (root) {
  "use strict";

  const W = typeof window !== "undefined" ? window : root;
  const tag = () => (W.document && W.document.getElementById ? W.document.getElementById("pilot-core") : null);
  const data = () => { const t = tag(); return (t && t.dataset) || {}; };
  const facts = () => (W.Pilot && W.Pilot.config && W.Pilot.config.facts) || {};
  const who = () => facts().who || data().who || "";
  const signedIn = () => who() === "business" || who() === "teacher";
  const readOnly = () => facts().readonly === true || data().readonly === "on";

  const KNOWLEDGE = `## OmniArmor
OmniArmor.ai is a compliance tracker by MTRX Horizyn: "Catch the fine before it catches you." Each industry has a checklist of ten checks: the compliance failures that cost businesses in that industry the most, that are common, expensive when missed and cheap to prevent with a deadline, a limit or a yes-or-no control. It is made for small businesses first (restaurants, bars, salons, child care, dental offices, construction, shops) and for schools, with starter lists for many more industries. Each checklist has its own name, like RestoArmor for restaurants or SchoolSafetyArmor for a school's safety routines.
OmniArmor is decision support, not legal advice. Each check names the rule it comes from; rules change and differ by place, so a business should confirm each rule with an expert for its area. OmniArmor only knows what people type in.

## Checks
- A check is one rule to keep: an inspection due every so often, a limit that must not be passed, or a yes-or-no control that must be in place. Each industry page lists its ten checks. Start with the ones marked "Top" (the costliest first), with "Why this matters".
- People enter a date, a number or a yes-or-no answer once and press Save. OmniArmor counts the days from there by itself, every morning, in the company's time zone. Some checks count hours or minutes from a start time ("Done now" starts the clock again from this minute).
- "Rule and source" (under each check): what it costs when it's missed, and the rule it comes from (the citation). The page also shows the question, the limit and when it warns.
- "Done today": duties that repeat (a yearly inspection, a monthly test) have a Done today button. It saves today as the last time it was done, so the next cycle starts.
- Dates: "the date it last happened" for a duty that repeats, or "the due or expiry date" for something that runs out (a licence, a certificate).
- "Set your own limit": a few limits come from common practice, not one fixed law ("policy"); those can be changed. Limits that come from the rule itself can't.
- "Update several at once": on an industry page, tick Select on several checks, then pick Mark done today, Answer Yes, Answer No or Set the date, and press Update selected. Each check is saved and recorded as if changed on its own. If one check can't take that change, nothing is saved and the page says which and why. Answer Yes is never given to a check where Yes means a problem (like "Is a sick employee working?"): those are answered on their own.

## Statuses and colours
- Blocked (red): past the limit, overdue, or a yes-or-no answer that breaks the rule. Fix it now.
- Warning (orange): getting close to the limit or the due date. Plan the fix.
- Cleared (grey, no colour): all good for now.
- No reading (faint grey): nobody has filled this check in yet.
The totals at the top of a page and the thin bar under them use the same colours. Red always means blocked and orange always means warning, so the two stay apart.

## Reminders
- Once a day, every team member gets one email (the daily digest) when a check is 30, 7 or 1 day from due, due today, or overdue (then once a week while it stays overdue). A missed day is caught up; failed emails are retried.
- Checks counted in hours or minutes send a time-limit alert at their warning point and when they become overdue.
- Reminders start once a check counted from a date has its date: entering that date is how you "set a reminder".
- Each person chooses in Settings, under "Your reminder emails", whether they get the daily digest, the time-limit alerts, both or neither. Both start on.
- The Reminders tab keeps a copy of every reminder and account email sent to the team.

## The app's tabs (a business)
- Home: what needs attention (blocked and warnings), what is coming due in the next 60 days, and each checklist's totals. A new workspace sees "Getting started": pick checklists, complete the first check, set the first reminder, invite a teammate or choose reminder emails.
- Report: every check's status, reading, due date, rule and last update, to print or Export CSV for an inspector, auditor or insurer.
- History: the audit trail. Every reading, limit and team change, with who made it and when; Export CSV.
- Reminders: the email log (above).
- Academy: the Future Owner Academy (below).
- Settings: company name, time zone and checklists (the owner), your reminder emails, the team (the owner invites with a link that works once for 7 days, and removes people), locations, the CyberLogix connection, the plan, and deleting the workspace.
- Armo, the little shield above the tab bar, jumps up when something is blocked, overdue, due soon or a reminder email failed, with a link to the fix. People can pick one of 14 personalities or hide him.
- A location is one workspace with its own checks, team and plan; the owner adds and switches locations in Settings.

## Plans for businesses
- A free trial of everything in Plus for every new workspace, from sign-up, with no card, once per owner.
- Pro: the compliance tracker (every check, reminders, reports and exports, updating several checks at once, the team).
- Plus: everything in Pro and the whole Future Owner Academy at no extra cost. The Academy's first worlds stay free for everyone.
- Prices are per location (one workspace), billed through Stripe; the owner manages the plan on the Plans page (Settings, Plan). A monthly plan can be paused or cancelled there; a cancelled plan stays on until the end of the time paid for.
- Without a plan the tracker is read-only: every record can still be seen, printed and downloaded and nothing is deleted, but checks can't be saved and reminders pause. Export and delete always work.
- Kitchen Safety Bundle: with CyberLogix (MTRX Horizyn's fridge and freezer alarm app), a restaurant's cold-holding check fills itself in from CyberLogix's daily readings, and a breach leaves a note to review. The bundle includes Pro while signed CyberLogix reports keep coming.

## OmniArmor for schools and teachers
- Schools have two sides: SchoolSafetyArmor (the school's safety routines: drills, AED and first-aid kits, playground and gym, the nurse's medication log, cafeteria, buses, concussion and heat checks, visitors, lab chemicals, background-check renewals) and the Future Owner Academy for a class.
- Teacher sign-up: name, school email, password and the school's name, with no list of industries. It lands on the Classes page ("Home") and starts the free classroom pilot.
- Adding students: open a class, type each student's first name or nickname, one per line. No email, no last name, no birthdate, no photo. A name that can't be added (it looks like an email, it's too long, or it's already in the class) is listed with the reason and put back in the box.
- Join codes: print one code per student; each works once, on a school device, and lets that device open the student's Academy and nothing else.
- The class page shows each student's lessons done and the class total. Certificates print on one page. The class leaderboard (first names and lessons done, this class only) can be switched off.
- The pilot report: one page with totals only (students, lessons finished, topics covered), no student names, for the school office.
- The Classroom track: the class runs a pretend lemonade stand; each lesson is a few questions and takes a few minutes; the first lesson of each world opens the next world; the Class Challenge at the end earns a certificate. Missed questions come back in "Practice my mistakes" a day, three days and a week later.
- The teacher guide (/classrooms/guide): what each world teaches, how long it takes, and questions to talk about. One world a week works well.
- A teacher's tabs: Home (classes), Checklist (the school safety checklist), Reminders, History, Settings.
- Classroom plans are yearly: Classroom (one class) and Whole school (every class and the school's safety checklist). By card or by invoice.

## Future Owner Academy (families)
A learning game for the kids who may one day run the family business: tracks from Launchpad to Titan Mastery, many business worlds, practice, streaks, friends and duels. A grown-up adds each kid with only a nickname and a picture; a join code lets a kid use the Academy on their own device. Plus includes it all; the first worlds are free.

## Demos
"See a demo" opens a pretend restaurant (some checks done, one overdue, a reminder and a report) or a pretend class, with no sign-up. Nothing in a demo is saved and nothing is sent.

## Data and privacy
No ads, no tracking or analytics, and pages, fonts and pictures all come from OmniArmor's own server. The workspace owner can download everything and delete the workspace at any time (cancel a paid plan first). The Privacy page has the details.

## Pilot (this assistant)
Pilot runs on the person's own AI key (Anthropic, OpenAI, Google Gemini or an OpenAI-compatible API) from their browser; OmniArmor never sees the key or the chat, and the provider bills the key. AI keys are for grown-ups. Pilot is never on a student's pages.
Signed in, Pilot can read what's due or overdue, explain a check and its rule, summarise the report and say what a colour means. After the person presses Allow it can mark a check done today, update a check's answer, number or date, set a reminder date, answer several yes-or-no checks at once (never Yes where Yes means a problem) and, for a teacher, add students by first name. It never changes a plan, deletes anything, invites or removes team members, or does anything on a student's account: people do those themselves in Settings or on the class page.`;

  // Genuine strengths, only from the real features. No rival is named and
  // there are no made-up numbers.
  const STRENGTHS = [
    "Every check names the rule it comes from (\"Rule and source\") and says what it costs when it's missed, so nothing is a black box.",
    "It counts the deadlines by itself, every morning, in your own time zone, including checks that count hours or minutes.",
    "One reminder email per person, 30, 7 and 1 day before, on the day, and weekly while overdue; missed days catch up and failed emails are retried. Everyone chooses their own emails.",
    "Done today restarts a recurring duty's cycle in one press, and several checks can be updated at once, never answering Yes where Yes means a problem.",
    "Every change is kept in the audit trail with who and when, and the report prints or exports to a spreadsheet for an inspector.",
    "Each industry's checklist starts with its costliest failures (the Top checks), so a small business knows where to begin.",
    "Without a plan nothing is deleted: the records stay readable and downloadable, and export and delete always work.",
    "A free trial with no card, and demos you can click around with no sign-up.",
    "No ads, no tracking or analytics, and no other company's fonts, scripts or pictures on its pages.",
    "For schools: students are added by first name or nickname only (no email, birthdate or photo), join codes work once on a school device, and the pilot report has totals only.",
    "A free classroom pilot with no card, a printable teacher guide, and an invoice option for schools.",
    "With the Kitchen Safety Bundle, a restaurant's fridge checks fill themselves in from real CyberLogix readings.",
    "Armo points straight at what's blocked, overdue or due soon, with a one-click link to the fix.",
    "Pilot works with the AI provider you already use, on your own key, and asks before it changes anything.",
  ];

  function liveFacts() {
    const f = facts();
    if (!f.pro) return "";
    const lines = [];
    lines.push(`Plans for businesses (the app's real prices): ${f.pro}, ${f.pro_price}${f.pro_yearly ? ` or ${f.pro_yearly} (${f.free_label})` : ""}; `
      + `${f.plus}, ${f.plus_price}${f.plus_yearly ? ` or ${f.plus_yearly} (${f.free_label})` : ""}. The free trial is ${f.trial_days} days of everything in ${f.plus}, no card.`);
    lines.push(`Kitchen Safety Bundle: ${f.bundle_price} through CyberLogix, which includes ${f.pro}; ${f.plus} then costs only the difference, ${f.bundle_upgrade}.`);
    lines.push(`Classroom plans (yearly): ${f.classroom}, ${f.classroom_price}: ${f.classroom_summary} ${f.school}, ${f.school_price}: ${f.school_summary} `
      + `The free classroom pilot is ${f.pilot_days} days, one class of up to ${f.class_size} students, no card.`);
    lines.push(`The Classroom track: ${f.class_worlds} worlds and ${f.class_lessons} lessons; a lesson is ${f.lesson_questions} questions, about ${f.lesson_minutes} minutes. The class's pretend business is ${f.class_business}.`);
    lines.push(`OmniArmor covers ${f.industries} industries and ${f.checks} checks; start with the top ${f.top_count} of each. Reminder emails go ${(f.reminder_days || []).join(", ")} day(s) before a due date, on the day, and weekly while overdue. A family workspace can add up to ${f.max_learners} Academy learners.`);
    if (f.support) lines.push(`Help: the Help page, or write to ${f.support}.`);
    return lines.join("\n");
  }

  // ---------------------------------------------------------------- reading OmniArmor's own pages

  const io = {
    fetch: (...a) => W.fetch(...a),
    parse: (html) => new W.DOMParser().parseFromString(html, "text/html"),
    doc: () => W.document,
  };

  const text = (node) => (node ? String(node.textContent || "").replace(/\s+/g, " ").trim() : "");
  const norm = (s) => String(s || "").toLowerCase().replace(/[“”"'’‘.,:;!?()]/g, "").replace(/\s+/g, " ").trim();
  const signedOutError = "You're signed out, so nothing changed. Sign in again, then ask me again.";

  function signedOut(response) {
    try { return new URL(response.url, "http://x").pathname === "/login"; } catch (_) { return false; }
  }

  async function page(url) {
    const r = await io.fetch(url, { credentials: "same-origin", headers: { Accept: "text/html" } });
    if (signedOut(r)) throw new Error(signedOutError);
    if (!r.ok) throw new Error(`OmniArmor couldn't open that page (error ${r.status})`);
    return io.parse(await r.text());
  }

  // The checklists this workspace keeps, from Pilot's script tag (pilot.py).
  function checklists() {
    try { return JSON.parse(data().checklists || "[]").filter((c) => Number.isInteger(c.id) && c.name); } catch (_) { return []; }
  }

  // One industry page's checks, as plain data (templates/app/industry.html).
  function checksFrom(doc, list) {
    const out = [];
    for (const li of doc.querySelectorAll("li.rule[id^='rule-']")) {
      const ds = li.dataset || {};
      const days = ds.days === undefined || ds.days === "" ? null : Number(ds.days);
      const why = li.querySelector(".why");
      out.push({
        checklistId: list.id, checklist: list.name,
        key: li.id.slice(5),
        title: text(li.querySelector("h2")),
        level: ds.level || "NONE",
        status: text(li.querySelector(".tag")),
        says: text(li.querySelector("p.msg") || li.querySelector("p.sr")),
        due: text(li.querySelector("p.due")),
        days: Number.isFinite(days) ? days : null,
        kind: ds.kind || "",
        mode: ds.mode || "",
        timed: "timed" in ds,
        top: text(li.querySelector(".top-n")),
        whyItMatters: text(li.querySelector(".why-line")).replace(/^Top \d+ · #\d+/, "").trim(),
        question: text(li.querySelector(".q")),
        limits: text(li.querySelector(".limits")),
        cost: why ? text(why.querySelector("p")) : "",
        rule: why ? text(why.querySelector("p.mono")) : "",
      });
    }
    return out;
  }

  let index = null;
  let indexAt = 0;
  let loading = null;
  const FRESH_MS = 60 * 1000;

  async function loadIndex(fresh) {
    if (!signedIn()) throw new Error("Sign in to OmniArmor first: Pilot reads your checks only inside your own workspace");
    if (!fresh && index && Date.now() - indexAt < FRESH_MS) return index;
    if (!loading) {
      loading = (async () => {
        const all = [];
        for (const list of checklists().slice(0, 30)) all.push(...checksFrom(await page(`/app/industry/${list.id}`), list));
        index = all;
        indexAt = Date.now();
        return all;
      })().finally(() => { loading = null; });
    }
    return loading;
  }

  function resolve(list, check, checklist, strict) {
    const want = norm(check);
    const where = norm(checklist);
    if (!want) return { error: "Which check? Say its name as it shows on the page." };
    let pool = list;
    if (where) {
      pool = list.filter((c) => norm(c.checklist) === where || norm(c.checklist).includes(where));
      if (!pool.length) {
        const names = [...new Set(list.map((c) => c.checklist))].join(", ");
        return { error: `This workspace has no checklist called “${checklist}”. Its checklists: ${names || "none yet"}.` };
      }
    }
    let hits = pool.filter((c) => norm(c.title) === want || c.key === check);
    if (!hits.length && !strict) hits = pool.filter((c) => norm(c.title).includes(want));
    if (!hits.length && !strict) {
      const words = want.split(" ").filter((w) => w.length > 2);
      if (words.length) hits = pool.filter((c) => words.every((w) => norm(c.title).includes(w)));
    }
    if (hits.length === 1) return { check: hits[0] };
    if (!hits.length) {
      return { error: `No check here matches “${check}”${strict ? " exactly" : ""}. Use its name as it shows on the page, or ask me what's due to see your checks.` };
    }
    return { error: `More than one check matches “${check}”: ${hits.slice(0, 6).map((c) => `“${c.title}” (${c.checklist})`).join(", ")}. Which one?` };
  }

  const brief = (c) => ({ check: c.title, checklist: c.checklist, status: c.status || c.level, says: c.says || undefined, due: c.due || undefined });

  // ---------------------------------------------------------------- changing things, only through these forms

  // The only forms Pilot may post, with the only fields and values each may
  // carry. Anything else is refused before it leaves the browser: no plan,
  // payment, deletion, team, invite, limit or student-account form is here.
  const ROUTES = [
    { name: "check", re: /^\/app\/industry\/\d{1,6}\/rule\/[a-z0-9_]{1,60}$/,
      fields: { action: ["save", "done_today"], answer: ["yes", "no"], value: true, date: true } },
    { name: "bulk", re: /^\/app\/industry\/\d{1,6}\/bulk$/,
      fields: { bulk_action: ["yes", "no", "done", "date"], keys: true, date: true } },
    { name: "students", re: /^\/app\/academy\/classes\/\d{1,18}\/students$/, fields: { names: true }, teacher: true },
  ];
  const NEVER = "Pilot can't do that. It only marks checks done, updates a check, sets a reminder date, answers several checks or adds students to a class. "
    + "It never changes a plan, deletes anything, invites or removes team members, or touches a student's account: do those yourself in Settings or on the class page.";

  function refuse(url, fields) {
    const route = ROUTES.find((r) => r.re.test(String(url)));
    if (!route) return NEVER;
    if (route.teacher && who() !== "teacher") return "Adding students is for a teacher's school workspace.";
    for (const [key, value] of Object.entries(fields || {})) {
      const rule = route.fields[key];
      if (!rule) return NEVER;
      const values = Array.isArray(value) ? value : [value];
      if (Array.isArray(rule) && !values.every((v) => rule.includes(v))) return NEVER;
    }
    return "";
  }

  function csrf() {
    const d = io.doc();
    const input = d && d.querySelector ? d.querySelector("input[name='csrf_token']") : null;
    return input ? input.value : "";
  }

  // Posts one of OmniArmor's own forms with the person's session and the
  // page's form token, follows it back to the page, and reads what the app
  // said (its flash messages).
  async function post(url, fields) {
    const why = refuse(url, fields);
    if (why) return { ok: false, error: why };
    const token = csrf();
    if (!token) return { ok: false, error: "Reload the page, then ask me again (the page's form token is missing)." };
    const body = new URLSearchParams();
    body.set("csrf_token", token);
    for (const [key, value] of Object.entries(fields)) {
      for (const v of Array.isArray(value) ? value : [value]) body.append(key, String(v));
    }
    const r = await io.fetch(url, { method: "POST", credentials: "same-origin", body, headers: { Accept: "text/html" } });
    indexAt = 0; // the statuses may have changed: read them again next time (names stay for the cards)
    if (signedOut(r)) return { ok: false, error: signedOutError };
    const doc = io.parse(await r.text());
    const said = [];
    let failed = false;
    for (const f of doc.querySelectorAll(".flashes .flash")) {
      if (f.classList.contains("invite")) continue;
      said.push(text(f));
      if (f.classList.contains("error")) failed = true;
    }
    if (!r.ok && !said.length) return { ok: false, error: r.status === 400 ? "The page's form had expired, so nothing changed. Reload the page and ask me again." : `OmniArmor said no (error ${r.status}).` };
    return { ok: !failed, said, doc };
  }

  const afterChange = "The page on screen shows the change after a reload.";
  function outcome(r, extra) {
    if (r.error) return { error: r.error };
    const out = { done: r.ok, omniarmor_said: r.said };
    if (r.ok) out.note = afterChange;
    else out.error = r.said.join(" ") || "OmniArmor didn't save it.";
    return Object.assign(out, extra || {});
  }

  // What a confirm card showed for a change, so the change that runs is
  // exactly the one the person allowed.
  const shown = new WeakMap();
  const inPlan = new WeakSet();
  const cached = () => index;

  function pickForCard(args) {
    const list = cached();
    if (!list) return null;
    const r = resolve(list, args.check, args.checklist, false);
    if (r.check) shown.set(args, r.check);
    return r.check || null;
  }

  async function pickForRun(args) {
    const seen = shown.get(args);
    if (seen) return { check: seen };
    // The card couldn't name the exact check: only an exact name will do.
    return resolve(await loadIndex(true), args.check, args.checklist, true);
  }

  const named = (c, args) => (c ? `“${c.title}” (${c.checklist})` : `“${args.check}”${args.checklist ? ` (${args.checklist})` : ""}`);
  const ISO_DAY = /^\d{4}-\d{2}-\d{2}$/;
  const ISO_MOMENT = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/;
  const NUMBER = /^-?\d+(?:\.\d+)?$/;
  const yesIsBad = (c) => c && c.kind === "forbidden";
  const yesNo = (c) => c && (c.kind === "forbidden" || c.kind === "required");
  const rulePath = (c) => `/app/industry/${c.checklistId}/rule/${c.key}`;
  const checkParams = {
    check: { type: "string", maxLength: 120, description: "The check's name, as it shows on the page." },
    checklist: { type: "string", maxLength: 60, description: "The checklist it's in (like RestoArmor), if more than one has a check with that name." },
  };

  // ---------------------------------------------------------------- statuses

  const STATUSES = {
    blocked: "Blocked (red): past the limit, overdue, or a yes-or-no answer that breaks the rule. Fix it now.",
    warning: "Warning (orange): getting close to the limit or the due date. Plan the fix.",
    cleared: "Cleared (grey, no colour): all good for now.",
    none: "No reading (faint grey): nobody has filled this check in yet.",
  };
  const COLOURS = { red: "blocked", orange: "warning", amber: "warning", yellow: "warning", grey: "cleared", gray: "cleared", green: "cleared" };

  // ---------------------------------------------------------------- tools

  const canChangeChecks = () => signedIn() && !readOnly();

  const TOOLS = [
    {
      name: "whats_due", kind: "read", available: signedIn,
      description: "What's overdue, blocked, warning, or due soon in this workspace's checklists, and how many checks still have no reading.",
      parameters: { type: "object", properties: { within_days: { type: "integer", description: "Due within this many days (default 30)." } } },
      run: async (args) => {
        const days = Math.min(Math.max(Number.isInteger(args.within_days) ? args.within_days : 30, 1), 365);
        const list = await loadIndex();
        const overdue = list.filter((c) => c.days !== null && c.days < 0);
        const blocked = list.filter((c) => c.level === "BLOCKED" && !overdue.includes(c));
        const warnings = list.filter((c) => c.level === "WARNING" && !overdue.includes(c));
        const soon = list.filter((c) => c.days !== null && c.days >= 0 && c.days <= days && c.level !== "BLOCKED" && c.level !== "WARNING")
          .sort((a, b) => a.days - b.days);
        const empty = list.filter((c) => c.level === "NONE");
        return {
          overdue: overdue.slice(0, 25).map(brief),
          blocked: blocked.slice(0, 25).map(brief),
          warnings: warnings.slice(0, 25).map(brief),
          [`due_within_${days}_days`]: soon.slice(0, 25).map(brief),
          checks_without_a_reading: empty.length,
          start_with: empty.filter((c) => c.top).slice(0, 3).map((c) => ({ check: c.title, checklist: c.checklist })),
          checks_in_all: list.length,
        };
      },
    },
    {
      name: "explain_check", kind: "read", available: signedIn,
      description: "Explain one of this workspace's checks: its status, what it asks, its limit, why it matters, and its \"Rule and source\" (the rule it comes from).",
      parameters: { type: "object", properties: checkParams, required: ["check"] },
      run: async (args) => {
        const r = resolve(await loadIndex(), args.check, args.checklist, false);
        if (r.error) return { error: r.error };
        const c = r.check;
        return {
          check: c.title, checklist: c.checklist, status: c.status, says: c.says, due: c.due || undefined,
          question: c.question, limit: c.limits || undefined,
          answer_that_means_a_problem: c.kind === "forbidden" ? "Yes" : c.kind === "required" ? "No" : undefined,
          repeats: c.mode === "since" ? (c.timed ? "yes: Done now starts its clock again" : "yes: Done today starts its next cycle") : c.mode === "due" ? "no: it has a due or expiry date" : undefined,
          top: c.top || undefined, why_it_matters: c.whyItMatters || undefined,
          rule_and_source: { what_it_costs_when_missed: c.cost, rule: c.rule },
          colour: STATUSES[{ BLOCKED: "blocked", WARNING: "warning", CLEARED: "cleared", NONE: "none" }[c.level]],
          reminder: "Decision support, not legal advice: confirm the rule for your area with an expert.",
        };
      },
    },
    {
      name: "summarise_report", kind: "read", available: signedIn,
      description: "The compliance report in short: each checklist's totals (blocked, warning, cleared, no reading) and the checks that need attention.",
      parameters: { type: "object", properties: {} },
      run: async () => {
        const list = await loadIndex();
        const lists = [...new Set(list.map((c) => c.checklist))].map((name) => {
          const mine = list.filter((c) => c.checklist === name);
          const n = (level) => mine.filter((c) => c.level === level).length;
          return { checklist: name, checks: mine.length, blocked: n("BLOCKED"), warning: n("WARNING"), cleared: n("CLEARED"), no_reading: n("NONE") };
        });
        return {
          checklists: lists,
          needs_attention: list.filter((c) => c.level === "BLOCKED" || c.level === "WARNING")
            .sort((a, b) => (a.level === b.level ? 0 : a.level === "BLOCKED" ? -1 : 1)).slice(0, 30).map(brief),
          due_in_30_days: list.filter((c) => c.days !== null && c.days >= 0 && c.days <= 30 && c.level === "CLEARED").slice(0, 20).map(brief),
          where: "The full report is the Report tab: print it, or press Export CSV for a spreadsheet.",
        };
      },
    },
    {
      name: "what_colour_means", kind: "read", available: () => true,
      description: "What a status or colour on OmniArmor's pages means (Blocked, Warning, Cleared, No reading; red, orange, grey).",
      parameters: { type: "object", properties: { colour_or_status: { type: "string", maxLength: 30, description: "A colour or status word, or leave out for all." } } },
      run: (args) => {
        const w = norm(args.colour_or_status);
        const key = STATUSES[w] ? w : COLOURS[w] || (w.startsWith("no") ? "none" : "");
        return key ? { meaning: STATUSES[key] } : { meanings: Object.values(STATUSES) };
      },
    },
    {
      name: "my_classes", kind: "read", available: () => who() === "teacher",
      description: "The teacher's classes in this school workspace: each class's name and how many students it has (never their names).",
      parameters: { type: "object", properties: {} },
      run: async () => {
        const list = await classes();
        return list.length ? { classes: list.map((c) => ({ name: c.name, students: c.students })) } : "There are no classes yet: add one on the Home (classes) page.";
      },
    },
    {
      name: "mark_done_today", kind: "change", available: canChangeChecks,
      description: "Mark a duty that repeats as done today (or done now, for a check counted in hours), so its next cycle starts. Asks the person first.",
      parameters: { type: "object", properties: checkParams, required: ["check"] },
      describe: (args) => {
        const c = pickForCard(args);
        return c && c.timed ? `mark ${named(c, args)} done now; its clock starts again from this minute`
          : `mark ${named(c, args)} done today; its next cycle starts today`;
      },
      run: async (args) => {
        const r = await pickForRun(args);
        if (r.error) return { error: r.error };
        if (r.check.mode !== "since") return { error: `“${r.check.title}” isn't a duty that repeats, so it can't be marked done. Its date or answer can be updated instead.` };
        return outcome(await post(rulePath(r.check), { action: "done_today" }));
      },
    },
    {
      name: "update_check", kind: "change", available: canChangeChecks,
      description: "Save a new reading for one check: a yes-or-no answer, a number, or a date (YYYY-MM-DD; for a check counted in hours, YYYY-MM-DDTHH:MM when it started). Give exactly one. Asks the person first.",
      parameters: {
        type: "object",
        properties: {
          ...checkParams,
          answer: { type: "string", enum: ["yes", "no"], description: "For a yes-or-no check." },
          value: { type: "string", maxLength: 20, description: "A number, for a check with a limit." },
          date: { type: "string", maxLength: 16, description: "A date (YYYY-MM-DD), or a date and time for a check counted in hours." },
        },
        required: ["check"],
      },
      describe: (args, info) => {
        const c = pickForCard(args);
        const planned = Boolean(info && Array.isArray(info.before));
        if (planned) inPlan.add(args);
        if (args.answer === "yes" && yesIsBad(c) && planned) {
          return `not answer Yes to ${named(c, args)} with other changes: Yes means a problem there, so it's answered on its own`;
        }
        const what = args.answer ? `answer ${args.answer === "yes" ? "Yes" : "No"} to` : args.value ? `save the reading ${args.value} for` : `save the date ${args.date} for`;
        const warn = args.answer === "yes" && yesIsBad(c) ? ". Yes means a problem here, so it will show Blocked"
          : args.answer === "no" && c && c.kind === "required" ? ". No means a problem here, so it will show Blocked" : "";
        return `${what} ${named(c, args)}${warn}`;
      },
      run: async (args) => {
        const given = ["answer", "value", "date"].filter((k) => args[k] !== undefined);
        if (given.length !== 1) return { error: "Give exactly one of: a yes-or-no answer, a number, or a date." };
        const r = await pickForRun(args);
        if (r.error) return { error: r.error };
        const c = r.check;
        if (args.answer !== undefined) {
          if (!yesNo(c)) return { error: `“${c.title}” isn't a yes-or-no check. ${c.question}` };
          if (args.answer === "yes" && yesIsBad(c) && inPlan.has(args)) {
            return { error: `Not done: “${c.title}”: Yes means a problem there, so it isn't answered together with other changes. Answer it on its own.` };
          }
          return outcome(await post(rulePath(c), { action: "save", answer: args.answer }));
        }
        if (yesNo(c)) return { error: `“${c.title}” is a yes-or-no check: answer it Yes or No.` };
        if (args.value !== undefined) {
          const v = String(args.value).replace(/,/g, "").trim();
          if (!NUMBER.test(v)) return { error: "The reading must be a plain number." };
          return outcome(await post(rulePath(c), { action: "save", value: v }));
        }
        if (!c.mode) return { error: `“${c.title}” isn't counted from a date. ${c.question}` };
        if (!(c.timed ? ISO_MOMENT : ISO_DAY).test(args.date)) {
          return { error: c.timed ? "Give when it started as YYYY-MM-DDTHH:MM." : "Give the date as YYYY-MM-DD." };
        }
        return outcome(await post(rulePath(c), { action: "save", date: args.date }));
      },
    },
    {
      name: "add_reminder", kind: "change", available: canChangeChecks,
      description: "Set a reminder: give a check that is counted from a date its date (the last time it was done, or its due or expiry date). The team then gets reminder emails before it's due. Asks the person first.",
      parameters: {
        type: "object",
        properties: { ...checkParams, date: { type: "string", maxLength: 10, description: "YYYY-MM-DD: the last time it was done, or its due or expiry date, as the check asks." } },
        required: ["check", "date"],
      },
      describe: (args) => {
        const c = pickForCard(args);
        const days = (facts().reminder_days || [30, 7, 1]).join(", ");
        if (c && c.mode === "since") return `set ${args.date} as the last time ${named(c, args)} was done; the team gets reminder emails before it's due again (${days} days before, and on the day)`;
        if (c && c.mode === "due") return `set ${named(c, args)} as due on ${args.date}; the team gets reminder emails ${days} days before, and on the day`;
        return `set the date of ${named(c, args)} to ${args.date}, so reminder emails count from it`;
      },
      run: async (args) => {
        const r = await pickForRun(args);
        if (r.error) return { error: r.error };
        const c = r.check;
        if (!c.mode) return { error: `“${c.title}” isn't counted from a date, so it has no reminder emails. ${c.question}` };
        if (c.timed) return { error: `“${c.title}” counts hours from a start time: its alerts come at its warning point and when it's overdue. Give when it started with update_check.` };
        if (!ISO_DAY.test(args.date)) return { error: "Give the date as YYYY-MM-DD." };
        return outcome(await post(rulePath(c), { action: "save", date: args.date }));
      },
    },
    {
      name: "answer_checks", kind: "change", available: canChangeChecks,
      description: "Answer several yes-or-no checks at once, through the industry page's \"Update several at once\". Yes is never given to a check where Yes means a problem: those are left out and must be answered on their own. Asks the person first.",
      parameters: {
        type: "object",
        properties: {
          checks: { type: "array", items: { type: "string", maxLength: 120 }, description: "The checks' names, as they show on the page." },
          answer: { type: "string", enum: ["yes", "no"] },
          checklist: checkParams.checklist,
        },
        required: ["checks", "answer"],
      },
      describe: (args) => {
        const plan = splitBulk(args, cached());
        shown.set(args, plan);
        const word = args.answer === "yes" ? "Yes" : "No";
        const go = plan.go.map((c) => `“${c.title}”`).join(", ");
        let label = plan.go.length ? `answer ${word} to ${plan.go.length} check${plan.go.length === 1 ? "" : "s"}: ${go}` : `answer ${word} to none of them`;
        if (plan.leftOut.length) label += `. Left out: ${plan.leftOut.map((c) => `“${c.title}”`).join(", ")} (Yes would mean a problem there: answer ${plan.leftOut.length === 1 ? "it" : "each"} on its own)`;
        if (plan.problems.length) label += `. Can't: ${plan.problems.join("; ")}`;
        return label;
      },
      run: async (args) => {
        const plan = shown.get(args) && shown.get(args).known ? shown.get(args) : splitBulk(args, await loadIndex(true), true);
        if (!plan.go.length) {
          return { error: [plan.leftOut.length ? `Yes would mean a problem for ${plan.leftOut.map((c) => `“${c.title}”`).join(", ")}, so it isn't given with others: answer each on its own.` : "",
            ...plan.problems].filter(Boolean).join(" ") || "There were no checks to answer." };
        }
        const said = [];
        let ok = true;
        const byList = new Map();
        for (const c of plan.go) byList.set(c.checklistId, (byList.get(c.checklistId) || []).concat([c]));
        for (const [id, mine] of byList) {
          const r = await post(`/app/industry/${id}/bulk`, { bulk_action: args.answer, keys: mine.map((c) => c.key) });
          if (r.error) return { error: r.error };
          said.push(...r.said);
          ok = ok && r.ok;
        }
        return { done: ok, omniarmor_said: said, note: ok ? afterChange : undefined,
          left_out: plan.leftOut.length ? plan.leftOut.map((c) => `${c.title}: Yes would mean a problem, so answer it on its own`) : undefined,
          not_found: plan.problems.length ? plan.problems : undefined };
      },
    },
    {
      name: "add_students", kind: "change", available: () => who() === "teacher",
      description: "Add students to one of the teacher's classes, by first name or nickname only (a last initial is fine to tell two apart). Never last names, emails, birthdates or anything else. Asks the teacher first.",
      parameters: {
        type: "object",
        properties: {
          names: { type: "array", items: { type: "string", maxLength: 30 }, description: "First names or nicknames, as the teacher typed them." },
          class_name: { type: "string", maxLength: 40, description: "The class, like Room 12. Leave out if there is only one." },
        },
        required: ["names"],
      },
      describe: (args) => {
        const names = cleanNames(args.names);
        const cls = classesCache && pickClass(classesCache, args.class_name);
        const where = cls && cls.class ? cls.class.name : args.class_name || "your class";
        if (cls && cls.class) shown.set(args, cls.class);
        const bad = names.bad.length ? `. Not added (first names or nicknames only): ${names.bad.join(", ")}` : "";
        return `add ${names.good.length} student${names.good.length === 1 ? "" : "s"} to ${where}: ${names.good.join(", ") || "none"}${bad}`;
      },
      run: async (args) => {
        const names = cleanNames(args.names);
        if (!names.good.length) return { error: "Give each student's first name or nickname only, like Maya or Sam K. Nothing was added." };
        let cls = shown.get(args);
        if (!cls) {
          const picked = pickClass(await classes(true), args.class_name, true);
          if (picked.error) return { error: picked.error };
          cls = picked.class;
        }
        const r = await post(`/app/academy/classes/${cls.id}/students`, { names: names.good.join("\n") });
        if (r.error) return { error: r.error };
        // Only what the app said, and why any typed name wasn't added: never the class list.
        const rejected = r.doc ? [...r.doc.querySelectorAll("[data-not-added] [data-rejected]")].map(text) : [];
        return { done: r.ok || r.said.some((s) => /^Added \d+/.test(s)), omniarmor_said: r.said,
          not_added: rejected.length || names.bad.length ? rejected.concat(names.bad.map((n) => `${n}: first names or nicknames only`)) : undefined };
      },
    },
  ];

  // Several checks for answer_checks: which go ahead, which are left out
  // because Yes is the bad answer there, and which couldn't be found or
  // aren't yes-or-no. `strict` (no card named them) wants exact names.
  function splitBulk(args, list, strict) {
    const out = { go: [], leftOut: [], problems: [], known: Boolean(list) };
    const names = (Array.isArray(args.checks) ? args.checks : []).map((n) => String(n).trim()).filter(Boolean).slice(0, 40);
    if (!list) { out.go = names.map((n) => ({ title: n })); out.known = false; return out; }
    for (const n of names) {
      const r = resolve(list, n, args.checklist, strict);
      if (r.error) { out.problems.push(r.error); continue; }
      const c = r.check;
      if (out.go.includes(c) || out.leftOut.includes(c)) continue;
      if (!yesNo(c)) { out.problems.push(`“${c.title}” isn't a yes-or-no check`); continue; }
      if (args.answer === "yes" && yesIsBad(c)) { out.leftOut.push(c); continue; }
      out.go.push(c);
    }
    return out;
  }

  // First names or nicknames: letters (any alphabet), an apostrophe or a
  // hyphen, and at most a last initial. No digits, no "@", no full names.
  const FIRST_NAME = /^\p{L}[\p{L}'’-]{0,28}(?: \p{L}\.?)?$/u;
  function cleanNames(raw) {
    const good = [];
    const bad = [];
    for (const n of (Array.isArray(raw) ? raw : []).slice(0, 35)) {
      const name = String(n).replace(/\s+/g, " ").trim();
      if (!name) continue;
      if (FIRST_NAME.test(name) && name.length <= 30) { if (!good.includes(name)) good.push(name); } else bad.push(name.slice(0, 30));
    }
    return { good, bad };
  }

  let classesCache = null;
  async function classes(fresh) {
    if (who() !== "teacher") return [];
    if (classesCache && !fresh) return classesCache;
    const d = io.doc();
    const here = d && d.querySelector && !fresh && d.querySelector("ul[data-classes]") ? d : await page("/app/academy/classes");
    const list = [];
    for (const li of here.querySelectorAll("ul[data-classes] li")) {
      const a = li.querySelector("a[href]");
      const m = a && /\/app\/academy\/classes\/(\d+)$/.exec(a.getAttribute("href"));
      if (!m) continue;
      const count = /(\d+)/.exec(text(li.querySelector(".muted")));
      list.push({ id: Number(m[1]), name: text(a), students: count ? Number(count[1]) : 0 });
    }
    classesCache = list;
    return list;
  }

  function pickClass(list, name, strict) {
    if (!list.length) return { error: "There are no classes yet: add one on the Home (classes) page first." };
    const want = norm(name);
    if (!want) return list.length === 1 ? { class: list[0] } : { error: `Which class? ${list.map((c) => c.name).join(", ")}.` };
    const exact = list.filter((c) => norm(c.name) === want);
    const hits = exact.length || strict ? exact : list.filter((c) => norm(c.name).includes(want));
    if (hits.length === 1) return { class: hits[0] };
    return { error: hits.length ? `More than one class matches: ${hits.map((c) => c.name).join(", ")}.` : `There's no class called “${name}”. Your classes: ${list.map((c) => c.name).join(", ")}.` };
  }

  // Ready the checks and classes when Pilot opens on a signed-in page, so a
  // confirm card can name the exact check. These are OmniArmor's own pages,
  // read in this browser: nothing goes to the AI until a tool runs.
  function warmUp() {
    if (!signedIn() || typeof W.fetch !== "function") return;
    loadIndex().catch(() => { /* a tool will say what went wrong */ });
    if (who() === "teacher") classes().catch(() => {});
  }

  const pack = {
    knowledge: KNOWLEDGE,
    get strengths() { return STRENGTHS; },
    tools: () => TOOLS,
    facts: () => liveFacts(),
    // For tests: the plain parts, and a way to give them a fake browser.
    _test: { io, ROUTES, refuse, post, resolve, splitBulk, cleanNames, checksFrom, pickClass, STATUSES,
      setIndex(list) { index = list; indexAt = Date.now(); }, setClasses(list) { classesCache = list; } },
  };
  W.PilotPack = pack;
  if (typeof module === "object" && module.exports) module.exports = pack;
  else warmUp();
})(typeof window !== "undefined" ? window : globalThis);
