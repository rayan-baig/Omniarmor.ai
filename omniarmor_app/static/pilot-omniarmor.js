// Pilot on OmniArmor: the small per-app config (docs/PILOT.md).
// The shared core is in static/pilot/ (copied unchanged from the MTRX
// Horizyn site); this file only says who we are, who is using it, which
// screen they are on, which suggestions fit it, and where the knowledge pack
// and OmniArmor's tools are (pilot-omniarmor-pack.js, fetched only when
// Pilot is first opened). pilot.js loads this file once the page has loaded.
//
// Pilot is for grown-ups: business owners, their teams and teachers. The
// server never puts it on a page a student uses (pilot.py), and this config
// refuses to start anywhere it can't tell who is there.
(function () {
  "use strict";
  if (!window.Pilot) return;
  const me = document.getElementById("pilot-core");
  const d = (me && me.dataset) || {};
  const who = d.who || "";
  let facts = {};
  try { facts = JSON.parse(d.facts || "{}") || {}; } catch (_) { facts = {}; }
  const path = (window.location.pathname.replace(/\/+$/, "") || "/");

  // A student's page or a kid's device: never Pilot (the server already
  // leaves it out; this is the second lock).
  const studentPath = /^\/kids(\/|$)|^\/app\/academy\/\d+(\/|$)/.test(path);
  const kidView = () => studentPath || !["visitor", "business", "teacher"].includes(who);

  const heading = () => {
    const h = document.querySelector("main h1");
    return h ? h.textContent.replace(/\s+/g, " ").trim() : "";
  };

  function screenName() {
    if (path === "/") return "Home page (for businesses and schools)";
    if (path === "/industries") return "Industries: every checklist";
    if (path.startsWith("/industries/")) return `Industry checklist page: ${heading()}`;
    if (path.startsWith("/for/")) return `Trade page: ${heading()}`;
    if (path === "/classrooms") return "The Academy for schools and teachers";
    if (path === "/classrooms/guide") return "Teacher guide (the Classroom track)";
    if (path === "/demo") return "Demos: try OmniArmor without signing up";
    if (path === "/app") return who === "teacher" ? "Checklist: the school safety checklist overview" : "Home: what needs attention";
    if (path.startsWith("/app/industry/")) return `${who === "teacher" ? "Checklist" : "Industry page"}: ${heading()} (its checks)`;
    if (path === "/app/report") return "Report: the compliance report";
    if (path === "/app/audit") return "History: the audit trail";
    if (path === "/app/notifications") return "Reminders: the reminder email log";
    if (path === "/app/settings") return "Settings";
    if (path === "/app/plan") return "Plans";
    if (path === "/app/academy/classes") return "Home: your classes";
    if (/^\/app\/academy\/classes\/\d+$/.test(path)) return `Class page: ${heading()} (students, join codes, progress)`;
    if (/^\/app\/academy\/classes\/\d+\/join-codes$/.test(path)) return `Join codes for ${heading()}`;
    if (path === "/app/academy") return "The Future Owner Academy: the family's learners";
    if (path === "/app/armo") return "Armo: what needs attention, and Armo's personality";
    return document.title;
  }

  function screen() {
    const lines = [];
    if (who === "visitor") lines.push("The person isn't signed in: they are looking at OmniArmor's public pages.");
    if (who === "business") lines.push("The person is signed in to a business's workspace.");
    if (who === "teacher") lines.push("The person is signed in to a school's workspace as a teacher or school staff.");
    if (d.demo === "on") lines.push("This is the demo, with pretend data: nothing is saved and no emails go out.");
    if (d.readonly === "on") lines.push(who === "teacher"
      ? "The school safety checklist is read-only on this workspace's plan: checks can be seen but not saved (classes still work)."
      : "The workspace is read-only (no plan right now): checks can be seen, printed and downloaded, but not saved.");
    return { name: screenName(), facts: lines.join("\n") };
  }

  // ---------------------------------------------------------------- answers with no AI key (core 1.4.0)
  //
  // The common questions are answered at once, with no AI key and nothing
  // sent anywhere: from what this page already shows (its checks, totals and
  // links) and the plain facts on Pilot's script tag (pilot.py). Never a
  // student's name: a class is counted, never listed, and nothing marked
  // data-pilot-private is ever read. An answer stays in this tab's chat (and
  // is part of what the AI sees once a key is added), so it is kept short.

  let CLASSES = [];
  try { CLASSES = JSON.parse(d.classes || "[]").filter((c) => c && Number.isInteger(c.id) && typeof c.name === "string"); } catch (_) { CLASSES = []; }
  let CHECKLISTS = [];
  try { CHECKLISTS = JSON.parse(d.checklists || "[]").filter((c) => c && Number.isInteger(c.id) && typeof c.name === "string"); } catch (_) { CHECKLISTS = []; }

  // Words from the page, kept as plain words in Pilot's markdown.
  const words = (t) => String(t || "").replace(/[*_`[\]#<>|\\]/g, "").replace(/\s+/g, " ").trim();
  const count = (n, one, many) => `${n} ${n === 1 ? one : (many || `${one}s`)}`;
  const all = (sel, under) => Array.from((under || document).querySelectorAll(sel) || []);
  const one = (sel, under) => (under || document).querySelector(sel);
  // An element's words, leaving out anything marked private (a person's name).
  function said(el) {
    if (!el) return "";
    if (typeof el.cloneNode === "function") {
      const copy = el.cloneNode(true);
      if (copy.querySelectorAll) for (const p of copy.querySelectorAll("[data-pilot-private]")) p.remove();
      return words(copy.textContent);
    }
    return words(el.textContent);
  }
  // A link of this site's own (a path), or "".
  const pathOf = (a) => { const h = a && a.getAttribute ? a.getAttribute("href") || "" : ""; return /^\/(?![/\\])\S*$/.test(h) ? h : ""; };
  const linked = (label, href) => (href ? `[${label}](${href})` : label);
  const NOT_ADVICE = "OmniArmor is decision support, not legal advice: confirm the rule with an expert for your area.";
  const STATUS = [
    "- **Blocked** (red): past the limit, overdue, or a yes-or-no answer that breaks the rule. Fix it now.",
    "- **Warning** (orange): getting close to the limit or the due date. Plan the fix.",
    "- **Cleared** (no colour): all good for now.",
    "- **No reading** (faint): nobody has filled this check in yet.",
  ].join("\n");
  const LEVEL_WORD = { BLOCKED: "blocked", WARNING: "warning", CLEARED: "cleared", NONE: "with no reading" };

  // This page's checks (an industry page, templates/app/industry.html).
  function pageChecks() {
    return all("li.rule[id^='rule-']").map((li) => {
      const ds = li.dataset || {};
      const days = ds.days === undefined || ds.days === "" ? null : Number(ds.days);
      return {
        li, href: `${path}#${li.id}`, level: ds.level || "NONE", days: Number.isFinite(days) ? days : null,
        title: said(one("h2", li)), tag: said(one(".tag", li)), due: said(one("p.due", li)),
      };
    });
  }
  // How many of each status this page shows: its totals, or its checks.
  function pageCounts() {
    const totals = one(".totals");
    if (totals) {
      const n = (sel) => { const b = one(`${sel} b`, totals); return b ? Number(said(b)) || 0 : 0; };
      const none = all("span", totals).find((s) => /without a reading/.test(s.textContent || ""));
      return { BLOCKED: n(".BLOCKED"), WARNING: n(".WARNING"), CLEARED: n("span:not(.BLOCKED):not(.WARNING)"), NONE: none ? Number(said(one("b", none))) || 0 : 0 };
    }
    const checks = pageChecks();
    if (!checks.length) return null;
    const out = { BLOCKED: 0, WARNING: 0, CLEARED: 0, NONE: 0 };
    for (const c of checks) out[c.level in out ? c.level : "NONE"] += 1;
    return out;
  }
  const countsLine = (c) => ["BLOCKED", "WARNING", "CLEARED", "NONE"].filter((k) => c[k] || k === "BLOCKED")
    .map((k) => (k === "WARNING" ? count(c[k], "warning") : `${c[k]} ${LEVEL_WORD[k]}`)).join(", ");
  const firstChecklist = () => (CHECKLISTS.length ? `/app/industry/${CHECKLISTS[0].id}` : "/app");

  // "What's due or overdue?"
  function dueAnswer() {
    const attention = one("[data-needs-attention]");
    if (attention) {
      const rows = all("a.row[data-level]", attention);
      const coming = all("[data-coming-due] a.row");
      const c = pageCounts() || { BLOCKED: 0, WARNING: 0 };
      const out = [];
      if (rows.length) {
        out.push(`**Needs attention: ${c.BLOCKED} blocked, ${count(c.WARNING, "warning")}.**`);
        for (const a of rows.slice(0, 5)) out.push(`- ${linked(said(one(".title", a)), pathOf(a))}: ${said(one(".tag", a))}`);
        if (rows.length > 5) out.push(`- and ${rows.length - 5} more under Needs attention on this page`);
      } else {
        out.push(said(one(".empty", attention)) || "Nothing is blocked or close to a limit right now.");
      }
      out.push("");
      if (coming.length) {
        out.push(`**Coming due in the next 60 days: ${coming.length}.**`);
        for (const a of coming.slice(0, 5)) out.push(`- ${linked(said(one(".title", a)), pathOf(a))}: ${said(one(".mono", a))}`);
      } else {
        out.push(said(one("[data-coming-due] .empty")) || "Nothing is coming due in the next 60 days.");
      }
      return out.join("\n");
    }
    const checks = pageChecks();
    if (checks.length) {
      const overdue = checks.filter((x) => x.days !== null && x.days < 0);
      const problems = checks.filter((x) => (x.level === "BLOCKED" || x.level === "WARNING") && !overdue.includes(x));
      const soon = checks.filter((x) => x.days !== null && x.days >= 0 && x.days <= 30 && !problems.includes(x)).sort((a, b) => a.days - b.days);
      const line = (x) => `- ${linked(x.title, x.href)}: ${x.due || x.tag}`;
      const out = [];
      if (overdue.length) out.push(`**Overdue: ${overdue.length}.**`, ...overdue.slice(0, 5).map(line), "");
      if (problems.length) out.push(`**Blocked or close to a limit: ${problems.length}.**`, ...problems.slice(0, 5).map((x) => `- ${linked(x.title, x.href)}: ${x.tag}`), "");
      if (soon.length) out.push(`**Due in the next 30 days: ${soon.length}.**`, ...soon.slice(0, 5).map(line), "");
      if (!out.length) out.push("Nothing on this checklist is overdue, blocked, close to a limit or due in the next 30 days.", "");
      const none = checks.filter((x) => x.level === "NONE").length;
      if (none) out.push(`${count(none, "check")} here still ${none === 1 ? "has" : "have"} no reading.`);
      out.push("[Home](/app) shows every checklist together.");
      return out.join("\n").trim();
    }
    const report = all("[data-report-table] tbody tr:not([data-entry-row]) .tag");
    if (report.length) {
      const n = (lvl) => report.filter((t) => t.classList && t.classList.contains(lvl)).length;
      return `This report shows ${n("BLOCKED")} blocked and ${count(n("WARNING"), "warning")} among ${count(report.length, "check")}.\n\n`
        + "[Home](/app) lists what needs attention and what's coming due in the next 60 days, with a link to each.";
    }
    return "[Home](/app) lists what needs attention (blocked and warnings) and what's coming due in the next 60 days, with a link straight to each check.";
  }

  // "Explain this check": the one asked for in the address, else the one in
  // view, else the first that needs attention.
  function explainAnswer() {
    const checks = pageChecks();
    if (checks.length) {
      const hash = (window.location && window.location.hash) || "";
      const h = (typeof window.innerHeight === "number" && window.innerHeight) || 800;
      const inView = (x) => { try { const r = x.li.getBoundingClientRect(); return r.bottom > h * 0.15 && r.top < h * 0.7; } catch (_) { return false; } };
      const c = checks.find((x) => `#${x.li.id}` === hash) || checks.find(inView)
        || checks.find((x) => x.level === "BLOCKED" || x.level === "WARNING") || checks[0];
      const li = c.li;
      const why = one(".why", li);
      const out = [`**${c.title}**: ${c.tag}`];
      const msg = said(one("p.msg", li) || one("p.sr", li));
      if (msg) out.push("", msg);
      const facts2 = [["What it asks", said(one(".q", li))], ["Limit", said(one(".limits", li))], ["Due", c.due],
        ["Why it matters", said(one(".why-line", li)).replace(/^Top \d+ · #?\d+\s*/, "").replace(/^Why this matters:\s*/, "")],
        ["If it's missed", why ? said(one("p", why)) : ""], ["Rule and source", why ? said(one("p.mono", why)) : ""]];
      out.push("", ...facts2.filter(([, v]) => v).map(([k, v]) => `- **${k}:** ${v}`));
      out.push("", STATUS.split("\n")[["BLOCKED", "WARNING", "CLEARED", "NONE"].indexOf(c.level in LEVEL_WORD ? c.level : "NONE")].replace(/^- /, "Status: "));
      out.push("", NOT_ADVICE, "", "To explain another check, scroll to it and press this again.");
      return out.join("\n");
    }
    const rows = all("[data-needs-attention] a.row[data-level]").slice(0, 3);
    const open = rows.length ? `Open one to see it explained:\n${rows.map((a) => `- ${linked(said(one(".title", a)), pathOf(a))}`).join("\n")}`
      : CHECKLISTS.length ? `Open a checklist and scroll to a check:\n${CHECKLISTS.slice(0, 4).map((x) => `- [${words(x.name)}](/app/industry/${x.id})`).join("\n")}`
        : "[Open your checklist](/app) and scroll to a check.";
    return "A check is one rule to keep: an inspection due every so often, a limit that must not be passed, or a yes-or-no "
      + "control that must be in place. Each one shows what it asks, its status, and under **Rule and source** what it costs "
      + `when missed and the rule it comes from.\n\n${open}\n\nThen press **Explain this check** again.\n\n${NOT_ADVICE}`;
  }

  // "What does this colour mean?"
  function colourAnswer() {
    const c = pageCounts();
    return `Each check's tag shows its status:\n\n${STATUS}${c ? `\n\nOn this page: ${countsLine(c)}.` : ""}\n\n[More in Help](/help#lights)`;
  }

  // A teacher's class: the one this page is about, else the only one.
  const classHere = () => {
    const m = /^\/app\/academy\/classes\/(\d+)(\/|$)/.exec(path);
    if (m) return { id: Number(m[1]), name: (CLASSES.find((c) => c.id === Number(m[1])) || {}).name || "" };
    return CLASSES.length === 1 ? CLASSES[0] : null;
  };
  const classLinks = (tail) => CLASSES.slice(0, 6).map((c) => `- [${words(c.name) || "Class"}](/app/academy/classes/${c.id}${tail})`).join("\n");

  // "How do join codes work?" (counts only: never a student's name)
  function joinAnswer(f) {
    const facts1 = f || {};
    const days = Number(facts1.join_code_days) || 7;
    const where = typeof facts1.join_path === "string" && /^\/[\w/-]*$/.test(facts1.join_path) ? facts1.join_path : "/kids";
    const out = [`Each student gets a join code. On a school device, the student opens **${where}** on this site and types it: `
      + `a code works once, for ${days} days, and that device then opens only that student's lessons. Print the codes page and cut it `
      + "into slips; make new codes any time (a student who has joined doesn't need one again)."];
    const cls = classHere();
    if (cls) {
      const students = one("[data-total='students']");
      const missing = one("[data-codes-missing]");
      const n = missing ? Number(missing.getAttribute("data-codes-missing")) || 0 : 0;
      if (students) out.push("", `This class has ${count(Number(said(students)) || 0, "student")}${n ? `; ${n} ${n === 1 ? "has" : "have"} no code yet` : ""}.`);
      out.push("", `[Open the join codes${cls.name ? ` for ${words(cls.name)}` : ""}](/app/academy/classes/${cls.id}/join-codes)`);
    } else if (CLASSES.length) {
      out.push("", `Open a class's join codes:\n${classLinks("/join-codes")}`);
    } else {
      out.push("", "[Add your class](/app/academy/classes#add-class) first, then its students: their codes are on the class page.");
    }
    return out.join("\n");
  }

  // "Print certificates" goes straight to the class's certificates.
  function certificatesLink() {
    const cls = classHere();
    return cls ? `/app/academy/classes/${cls.id}/certificates` : "/app/academy/classes";
  }

  // A visitor's: what OmniArmor does, the free trial, and safety for students.
  function whatAnswer(f) {
    const x = f || {};
    const days = (x.reminder_days || []).join(", ");
    return "OmniArmor keeps a small business's compliance checks in one place, so nothing slips past a deadline or a limit.\n\n"
      + `- **Starter checklists** for ${x.industries || "many"} industries (${x.checks || "hundreds of"} checks), the failures that cost each industry the most, with the rule each comes from.\n`
      + "- **Enter a date, a number or a yes-or-no answer once.** It counts the days every morning and shows each check as Cleared, Warning or Blocked.\n"
      + `- **Reminder emails** to your team${days ? ` ${days} days before a due date,` : ""} on the day, and weekly while overdue.\n`
      + "- **A report** to print or export for an inspector, auditor or insurer.\n\n"
      + `${x.trial_days ? `Free for ${x.trial_days} days, no card. ` : ""}[See a demo](/demo) or [find your industry](/industries).`;
  }
  function trialAnswer(f) {
    const x = f || {};
    return `Try the Academy free for ${x.pilot_days || 30} days: one class of up to ${x.class_size || 30} students and the whole Classroom track. No card, one trial per account.\n\n`
      + "1. Sign up with your school's name: you land on the Classes page.\n2. Start the free trial there.\n"
      + "3. Add your class and type your students' first names or nicknames.\n4. Print the join codes; students play on school devices.\n\n"
      + `After the trial: ${x.classroom ? `**${words(x.classroom)}** ${words(x.classroom_price)}` : "Classroom"} or ${x.school ? `**${words(x.school)}** ${words(x.school_price)}` : "Whole school"}, paid yearly. [See the prices](/classrooms#price)`;
  }
  const SAFE = "Students are added by **first name or nickname only**: no email, birthdate or photo, and no student accounts.\n\n"
    + "- A student joins on a school device with a one-time join code, and sees only their own lessons.\n"
    + "- The class leaderboard starts off; the teacher can turn it on (first names and lessons done, this class only).\n"
    + "- The trial report for the school office shows totals only.\n- Pilot, this helper, is never on a student's page.\n\n"
    + "[Read the privacy page](/privacy)";

  // Short answers for page suggestions.
  function reminderAnswer(f) {
    const days = ((f || {}).reminder_days || []).join(", ");
    return `Once a day each person on the team gets one email, the daily digest, when a check is ${days ? `${days} days` : "close to"} from due, due today or overdue `
      + "(then once a week while it stays overdue). A missed day is caught up. Checks counted in hours also send an alert at their warning point and when they become overdue.\n\n"
      + "Each person chooses their own emails in [Settings](/app/settings), and every email is kept under Reminders. [More in Help](/help#reminders)";
  }
  const CHECK = "A check is one compliance rule to keep: an inspection due every so often, a limit that must not be passed, or a yes-or-no control that must be in place. "
    + "Each industry's checks are the failures that cost it the most; start with the ones marked **Top**. Open **Rule and source** on a check to see what it costs when missed and the rule it comes from.\n\n"
    + `${NOT_ADVICE} [More in Help](/help#check)`;
  const ADVICE = `No. ${NOT_ADVICE} Each check names the rule it comes from, so you can look it up or ask.`;
  const EXPORT = "On this page, press **Print** for a paper copy (or save it as a PDF from the print window), or **Export CSV** for a spreadsheet. Both have every check's status, reading, due date and rule.";
  const DEMO_SAVED = "No. The demos use pretend data: nothing you do is saved and no emails go out. To keep your own checks, [start a free trial](/signup).";
  function plansAnswer(f) {
    const x = f || {};
    return `- **${words(x.classroom) || "Classroom"}** (${words(x.classroom_price)} a year): ${words(x.classroom_summary)}\n`
      + `- **${words(x.school) || "Whole school"}** (${words(x.school_price)} a year): ${words(x.school_summary)}\n\n[See the prices](/classrooms#price)`;
  }
  function lessonAnswer(f) {
    const x = f || {};
    return `A lesson is ${x.lesson_questions || 5} questions and takes about ${x.lesson_minutes || 3} minutes. The first lesson of each world opens the next world; `
      + "after the first lesson of every world comes the Class Challenge, which earns a certificate. [Open the teacher guide](/classrooms/guide)";
  }

  // A page suggestion: an AI prompt (words), or an answer given at once.
  const C = (label, what) => (typeof what === "string" ? { label, prompt: what } : { label, ...what });
  const A = (fn) => ({ answer: (ctx) => fn((ctx && ctx.facts) || {}) });
  function pageChips() {
    if (path === "/") return [C("What does OmniArmor do?", A(whatAnswer)),
      C("Which plan fits me?", "Which OmniArmor plan would fit me? Ask me one or two questions first."),
      C("How do reminders work?", A(reminderAnswer))];
    if (path === "/industries" || path.startsWith("/industries/") || path.startsWith("/for/")) {
      return [C("Which checklist fits me?", "Which OmniArmor checklist fits my business? Ask me what kind of business it is first."),
        C("What's a check?", { answer: CHECK }),
        C("Is this legal advice?", { answer: ADVICE })];
    }
    if (path === "/classrooms") return [C("How does the free trial work?", A(trialAnswer)),
      C("Is it safe for students?", { answer: SAFE }),
      C("Classroom or Whole school?", A(plansAnswer))];
    if (path === "/classrooms/guide") return [C("Plan a week", "Help me plan one world a week for my class."),
      C("How long is a lesson?", A(lessonAnswer))];
    if (path === "/demo") return [C("What can I try?", "What can I try in the demos?"), C("Is anything saved?", { answer: DEMO_SAVED })];
    // A teacher's pages: OmniArmor's own suggestions, about their classes. The
    // school checklist's "What's overdue?" only on Whole school.
    if (path === "/app/academy/classes" || /^\/app\/academy\/classes\/\d+(\/join-codes)?$/.test(path)) {
      return [C("Add students", "Add students to my class."),
        C("How do join codes work?", A(joinAnswer)),
        facts.school_checklist ? C("What's overdue?", { answer: dueAnswer })
          : C("Plan a week", "Help me plan one world a week for my class.")];
    }
    if (path === "/app" || path.startsWith("/app/industry/")) return [C("What's overdue?", { answer: dueAnswer }),
      C("Explain a check", { answer: explainAnswer }),
      C("What do the colours mean?", { answer: colourAnswer })];
    if (path === "/app/report") return [C("Summarise my report", "Summarise my report."),
      C("What's overdue?", { answer: dueAnswer }), C("How do I export it?", { answer: EXPORT })];
    if (path === "/app/audit") return [C("What's in History?", "What does the History page record?"), C("Export it", "How do I export the audit trail?")];
    if (path === "/app/notifications") return [C("When do reminders go out?", A(reminderAnswer)),
      C("Add a reminder", "Add a reminder for one of my checks.")];
    if ((path === "/app/settings" || path === "/app/plan") && who === "teacher" && !facts.school_checklist) {
      return [C("Classroom or Whole school?", A(plansAnswer)),
        C("Invite a colleague", "How do I invite another teacher to our school's workspace?")];
    }
    if (path === "/app/settings" || path === "/app/plan") return [C("Choose my emails", "How do I choose which reminder emails I get?"),
      C("What do the plans include?", "What does each plan include?")];
    // Anywhere else: OmniArmor's own suggestions for who is here.
    if (who === "teacher") return [C("Add students", "Add students to my class."),
      C("How do join codes work?", A(joinAnswer))];
    if (who === "business") return [C("What's overdue?", { answer: dueAnswer }),
      C("How do reminders work?", A(reminderAnswer))];
    return [C("What does OmniArmor do?", A(whatAnswer))];
  }

  const TASKS = {
    "/app": "Mark this check done today: ",
    "/app/report": "Summarise my report and tell me what to fix first",
    "/app/notifications": "Add a reminder for: ",
    "/app/academy/classes": "Add these students to my class (first names only): ",
  };
  function taskPrompt() {
    if (path.startsWith("/app/industry/")) return "Mark this check done today: ";
    if (TASKS[path]) return TASKS[path];
    return who === "visitor" ? "Help me pick the right OmniArmor checklist for my business: " : "Help me with this page.";
  }

  // Core 1.2.0: the welcome is OmniArmor's own (docs/PILOT.md), and fits who
  // is here: a business owner gets their checklist's questions, a teacher
  // their class's. A visitor gets the questions for the side of the site
  // they are looking at (the schools pages, or the business pages), under
  // "Your OmniArmor helper". Each pill's icon fits what it does: certificates
  // are sheets of paper (copy), not a chart. The key pill is the welcome's
  // one ask for a key (core 1.3.0 shows no key card beside it).
  // Core 1.4.0 (OmniArmor 1.17.0): the pills that need no AI work with no key:
  // an answer from this page and the site's facts, or a link. Summing up a
  // report, adding students and planning lessons still need the AI.
  const P = (icon, label, action, send) => ({ icon, label, action, send: Boolean(send) });
  const ANSWER = (icon, label, answer) => ({ icon, label, answer });
  const LINK = (icon, label, link) => ({ icon, label, link });
  const KEY = P("key", "Add my AI key", "settings");
  const schoolSide = who === "teacher" || (who === "visitor" && /^\/classrooms(\/|$)/.test(path));
  const WELCOME = {
    business: {
      tagline: "Your checklist helper",
      pills: [ANSWER("bolt", "What's due or overdue?", dueAnswer),
        ANSWER("help", "Explain this check", explainAnswer),
        P("bars", "Summarise my report", "Summarise my report and tell me what to fix first.", true),
        ANSWER("spark", "What does this colour mean?", colourAnswer),
        KEY],
    },
    teacher: {
      tagline: "Your classroom helper",
      pills: [P("chat", "Add students", "Add these students to my class (first names only): "),
        ANSWER("help", "How do join codes work?", (ctx) => joinAnswer(ctx && ctx.facts)),
        P("spark", "Plan a week of lessons", "Help me plan a week of Academy lessons for my class. Ask me one or two questions first.", true),
        LINK("copy", "Print certificates", certificatesLink()),
        KEY],
    },
    school: {
      tagline: "Your OmniArmor helper",
      pills: [ANSWER("help", "Is it safe for students?", SAFE),
        ANSWER("bolt", "How does the free trial work?", (ctx) => trialAnswer(ctx && ctx.facts)),
        P("spark", "Plan a week of lessons", "Help me plan a week of Academy lessons for my class. Ask me one or two questions first.", true),
        P("bars", "Explain this page", "explain-screen"),
        KEY],
    },
    visitor: {
      tagline: "Your OmniArmor helper",
      pills: [ANSWER("chat", "What does OmniArmor do?", (ctx) => whatAnswer(ctx && ctx.facts)),
        P("help", "Which checklist fits me?", "Which OmniArmor checklist fits my business? Ask me what kind of business it is first.", true),
        LINK("bolt", "See the prices", "/help#prices"),
        P("bars", "Explain this page", "explain-screen"),
        KEY],
    },
  };
  const welcome = who === "business" ? WELCOME.business : who === "teacher" ? WELCOME.teacher
    : schoolSide ? WELCOME.school : WELCOME.visitor;

  // The core shows this page's suggestions under the welcome's pills too.
  // There, a suggestion that asks what a pill already asks is left out, so
  // nothing shows twice; once a chat has started (the pills fold away) every
  // suggestion for the page is back.
  const SAME = {
    "What's overdue?": "What's due or overdue?", "Explain a check": "Explain this check",
    "What do the colours mean?": "What does this colour mean?", "Plan a week": "Plan a week of lessons",
  };
  const pillLabels = new Set(welcome.pills.map((p) => p.label));
  function chips() {
    const list = pageChips();
    let chatting = false;
    try { chatting = window.Pilot.store.loadChat().length > 0; } catch (_) { chatting = false; }
    return chatting ? list : list.filter((c) => !pillLabels.has(c.label) && !pillLabels.has(SAME[c.label]));
  }

  const mounted = window.Pilot.mount({
    appName: "OmniArmor",
    name: "Pilot",
    tagline: welcome.tagline,
    welcomePills: welcome.pills,
    // Core 1.4.0: under an answer Pilot gives without a key.
    answerMore: "Want more? Add your AI key to ask anything.",
    // Pilot here answers in words and works the checklist; it has no use for
    // making pictures or videos, so their key sections are left out.
    hideKeySections: ["image", "video"],
    // Tucked away, the robot shrinks into its corner instead of hanging off
    // the screen's edge (on a phone, in the one corner: app.css).
    keepInViewport: true,
    // No `modals`: OmniArmor has no pop-ups that aren't marked as dialogs
    // (Armo's bubble is a helper's, in yieldTo below), and the core already
    // steps back for anything covering the whole screen.
    storagePrefix: "omniarmor-pilot",
    pack: d.pack || "",
    // Exactly the hosts the security policy lets a browser reach for an
    // OpenAI-compatible API (pilot.COMPATIBLE_HOSTS and the person's own computer).
    compatibleHosts: (d.hosts || "").split(/\s+/).filter(Boolean),
    privacyUrl: "/privacy",
    // One plain sentence on what an AI key is and where a grown-up gets one;
    // the window shows it under the pills (before a key is set) and in the
    // key settings.
    keyNote: "An AI key is a private code from an AI company that lets Pilot think for you, billed to the key's owner: "
      + "a grown-up gets one by signing up on that company's website. AI keys are for grown-ups (the AI companies require 18+).",
    // Core 1.3.0: the one line the welcome shows above the box (the full note
    // stays beside the key settings and in help).
    keyNoteShort: "AI keys are for grown-ups (18+).",
    audienceNote: "The people using Pilot here are grown-ups: small-business owners and their teams, and teachers or school staff. "
      + "Students never use Pilot. Never ask for or repeat students' names; a teacher may type first names for adding students, and that's all. "
      + "OmniArmor is decision support, not legal advice: for what a rule means in their area, suggest checking with an expert.",
    kidView,
    // Pilot core 1.2.0 keeps the robot out of the way: it keeps off the
    // page's own words and buttons wherever the page is scrolled to, and off
    // a box being typed in. On top of that it gives Armo (the companion, with
    // his bubble) room, and never sits on a status tag (NO READING, BLOCKED
    // and the rest), a Top 5 badge, the Kitchen Safety Bundle note, a check's
    // message, a flash or banner, Armo's bubble and badge, the "First name
    // only?" card or the menu and the OmniArmor name at the top (Sign out among it). When one of
    // those is where it sits, it moves to a free corner, or tucks away at the
    // edge until tapped, shrunk into its corner (keepInViewport). The tab bar
    // is kept clear by app.css, which puts the robot's bottom corners above it.
    yieldTo: [".companion"],
    // 1.16.0: also a check's "Select" box (.pick), and the teacher guide's
    // lines, headings and list items, where the core's own sense of the
    // page's words still let the robot touch them.
    avoid: [".tag", ".top-n", ".bundle", ".msg", ".entry-top", ".flash", ".plan-banner", ".ac-badge",
      ".companion-bubble", ".companion-fix", ".companion-badge", "[data-confirm-names]", ".topbar .nav", ".lockup",
      ".pick", "[data-teacher-guide] p", "[data-teacher-guide] li", "[data-teacher-guide] h2", "[data-teacher-guide] h3"],
    // On a phone the robot stays in the bottom-right corner, the one corner
    // it shares with Armo, and only one of them shows (app.css, "One helper,
    // one corner"); tucked away it shrinks there, never off the edge. The
    // page's column keeps the core's side room (30px on a phone) so line ends
    // stop before the small robot. The column is main's .wrap (main itself
    // has no side padding). On a signed-in page (the tab bar) the robot has
    // its own corner above the tab bar instead (app.css, 1.16.0), so the
    // column keeps its own even room and no side room is added.
    gutter: document.body && document.body.classList.contains("has-tabs") ? false : ["main > .wrap"],
    screen,
    chips,
    taskPrompt,
    facts: { who, demo: d.demo === "on", readonly: d.readonly === "on", ...facts },
  });

  // A different account in this tab (someone signed out, or a kid used the
  // device): forget the last person's chat, and their key if it was kept
  // for this tab only. A key someone chose to remember on this device stays.
  if (mounted && window.Pilot.store) {
    const store = window.Pilot.store;
    const mark = `${store.prefix}-account`;
    let before = null;
    try { before = window.sessionStorage.getItem(mark); } catch (_) { before = null; }
    const now = d.account || "";
    if (before && before !== now) {
      store.clearChat();
      store.setUi({ open: false });
      if (!store.all().remember) store.forget();
    }
    try { window.sessionStorage.setItem(mark, now); } catch (_) { /* private mode: nothing kept */ }
  }
})();
