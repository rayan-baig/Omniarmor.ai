// Pilot on OmniArmor: the small per-app config (docs/PILOT.md).
// The shared core is in static/pilot/ (copied unchanged from the company's
// main site); this file only says who we are, who is using it, which
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
  // 1.24.0: the company's and the assistant's names come from the server (names.py, on Pilot's script tag), so
  // they are typed in one place only.
  const N = Object.assign({ company: "", app: "OmniArmor", assistant: "Pilot", fridge_app: "Kryozyn" }, facts.names || {});
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
  // 1.19.0: what needs attention and what's coming due across the workspace (pilot.py, Armo's list), each with
  // its check's link, so "What's due or overdue?" lists the real items on every page.
  let DUE = [];
  try {
    DUE = JSON.parse(d.due || "[]").filter((x) => x && typeof x.title === "string" && typeof x.url === "string"
      && /^\/(?![/\\])\S*$/.test(x.url) && ["urgent", "soon", "info"].includes(x.level));
  } catch (_) { DUE = []; }
  let CHECKLISTS = [];
  try { CHECKLISTS = JSON.parse(d.checklists || "[]").filter((c) => c && Number.isInteger(c.id) && typeof c.name === "string"); } catch (_) { CHECKLISTS = []; }

  // Words from the page, kept as plain words in Pilot's markdown.
  const words = (t) => String(t || "").replace(/[*_`[\]#<>|\\]/g, "").replace(/\s+/g, " ").trim();
  const count = (n, one, many) => `${n} ${n === 1 ? one : (many || `${one}s`)}`;
  // A yearly price, said once: "$299 a year" stays as it is, "$299" gets " a year".
  // "30, 7 and 1 day": the reminder days said as a person would (1.18.0; was "30, 7, 1 days").
  const dayList = (days) => {
    const d = (Array.isArray(days) ? days : []).filter((n) => Number.isInteger(n));
    if (!d.length) return "";
    const last = d[d.length - 1];
    return `${d.length > 1 ? `${d.slice(0, -1).join(", ")} and ` : ""}${last} day${last === 1 ? "" : "s"}`;
  };
  const yearly = (price) => { const p = words(price); return !p ? "" : /\ba year\b/.test(p) ? p : `${p} a year`; };
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

  // The workspace's own list (DUE), for any page: what needs attention, then what's coming up.
  const dueLine = (x) => `- ${linked(words(x.title), pathOf({ getAttribute: () => x.url }))}${x.where ? ` · ${words(x.where)}` : ""}`;
  function dueList() {
    const now = DUE.filter((x) => x.level !== "info");
    const later = DUE.filter((x) => x.level === "info");
    const line = dueLine;
    const out = [];
    if (now.length) out.push(`**Needs attention: ${now.length}.**`, ...now.slice(0, 8).map(line), "");
    if (later.length) out.push("**Coming up, or still to fill in:**", ...later.slice(0, 6).map(line), "");
    return out;
  }

  // 1.27.0: "What's due this week?": what's overdue or blocked, then what falls due in the next 7 days, each with
  // its date, from the workspace's own list (DUE), on every page. It listed every warning, even one 41 days away,
  // with no dates.
  const WEEK_DAYS = 7;
  const WEEK_WORDS = /\bweek\b/i;
  const daysOf = (x) => (Number.isInteger(x.days) ? x.days : null);
  const dueOn = (x) => (typeof x.due === "string" ? words(x.due) : "");
  function weekDueAnswer() {
    const late = DUE.filter((x) => x.level === "urgent" || (daysOf(x) !== null && daysOf(x) < 0));
    const soon = DUE.filter((x) => !late.includes(x) && daysOf(x) !== null && daysOf(x) >= 0 && daysOf(x) <= WEEK_DAYS)
      .sort((a, b) => daysOf(a) - daysOf(b));
    const when = (x) => (!dueOn(x) ? "" : daysOf(x) !== null && daysOf(x) < 0 ? ` · was due ${dueOn(x)}` : ` · due ${dueOn(x)}`);
    const out = [];
    if (late.length) out.push(`**Overdue or blocked: ${late.length}.**`, ...late.slice(0, 8).map((x) => `${dueLine(x)}${when(x)}`), "");
    if (soon.length) out.push(`**Due in the next ${WEEK_DAYS} days: ${soon.length}.**`, ...soon.slice(0, 8).map((x) => `${dueLine(x)}${when(x)}`), "");
    if (!out.length) out.push(`Nothing is overdue, blocked or due in the next ${WEEK_DAYS} days.`, "");
    out.push("[Home](/app) lists everything that needs attention, and what's coming due in the next 60 days.");
    return out.join("\n");
  }

  // "What's due or overdue?"
  function dueAnswer(ctx) {
    if (ctx && typeof ctx.label === "string" && WEEK_WORDS.test(ctx.label)) return weekDueAnswer();
    const attention = one("[data-needs-attention]");
    if (attention) {
      const rows = all("a.row[data-level]", attention);
      const coming = all("[data-coming-due] a.row");
      // 1.28.0: the rows themselves are counted (one per tracked item, as Home lists them; the totals count each
      // check once), and each says its detail line beside its tag ("Blocked · 4 days overdue · last done 35 days
      // ago"), as "What's due this week?" gives each its date.
      const level = (a) => a.getAttribute("data-level");
      const blocked = rows.filter((a) => level(a) === "BLOCKED").length;
      const out = [];
      if (rows.length) {
        out.push(`**Needs attention: ${blocked} blocked, ${count(rows.length - blocked, "warning")}.**`);
        for (const a of rows.slice(0, 5)) {
          const detail = said(one("[data-attention-detail]", a));
          out.push(`- ${linked(said(one(".title", a)), pathOf(a))}: ${said(one(".tag", a))}${detail ? ` · ${detail}` : ""}`);
        }
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
      if (none) out.push(`${count(none, "check")} here still ${none === 1 ? "has" : "have"} no reading.`, "");
      // 1.19.0: what needs attention on the workspace's other checklists too.
      const elsewhere = DUE.filter((x) => x.level !== "info" && x.url.split("#")[0] !== path);
      if (elsewhere.length) {
        out.push(`**On your other checklists: ${elsewhere.length}.**`,
          ...elsewhere.slice(0, 5).map(dueLine), "");
      }
      out.push("[Home](/app) shows every checklist together.");
      return out.join("\n").trim();
    }
    // 1.19.0: any other page (the report, History, Reminders, Settings): the workspace's own list, with links.
    const out = [];
    const report = all("[data-report-table] tbody tr:not([data-entry-row]) .tag");
    if (report.length) {
      const n = (lvl) => report.filter((t) => t.classList && t.classList.contains(lvl)).length;
      out.push(`This report shows ${n("BLOCKED")} blocked and ${count(n("WARNING"), "warning")} among ${count(report.length, "check")}.`, "");
    }
    out.push(...dueList());
    if (!DUE.length) out.push("Nothing is blocked, close to a limit or due in the next 30 days.", "");
    out.push("[Home](/app) also lists what's coming due in the next 60 days.");
    return out.join("\n").trim();
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
      // "Why it matters" is cut from "If it's missed" (catalog.why_line): when one holds the other, the
      // longer is said once (1.18.0: the same sentence used to show twice).
      let matters = said(one(".why-line", li)).replace(/^Top \d+ · #?\d+\s*/, "").replace(/^Why this matters:\s*/, "");
      let missed = why ? said(one("p", why)) : "";
      const bare = (t) => t.toLowerCase().replace(/[.\s]+$/, "");
      if (matters && missed && (bare(missed).startsWith(bare(matters)) || bare(matters).startsWith(bare(missed)))) {
        missed = bare(missed).length >= bare(matters).length ? missed : matters;
        matters = "";
      }
      const facts2 = [["What it asks", said(one(".q", li))], ["Limit", said(one(".limits", li))], ["Due", c.due],
        ["Why it matters", matters], ["If it's missed", missed], ["Rule and source", why ? said(one("p.mono", why)) : ""]];
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
    const days = dayList(x.reminder_days);
    return "OmniArmor keeps a small business's compliance checks in one place, so nothing slips past a deadline or a limit.\n\n"
      + `- **Starter checklists** for ${x.industries || "many"} industries (${x.checks || "hundreds of"} checks), the failures that cost each industry the most, with the rule each comes from.\n`
      + "- **Enter a date, a number or a yes-or-no answer once.** It counts the days every morning and shows each check as Cleared, Warning or Blocked.\n"
      + `- **Reminder emails** to your team${days ? ` ${days} before a due date,` : ""} on the day, and weekly while overdue.\n`
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
    + `- The trial report for the school office shows totals only.\n- ${N.assistant}, this helper, is never on a student's page.\n\n`
    + "[Security and your data](/security): where it's kept, backups, who can see a name and how to delete it. [The privacy page](/privacy)";

  // Short answers for page suggestions.
  function reminderAnswer(f) {
    const days = dayList((f || {}).reminder_days);
    return `Once a day each person on the team gets one email, the daily digest, when a check is ${days || "close to"} from due, due today or overdue `
      + "(then once a week while it stays overdue). A missed day is caught up. Checks counted in hours also send an alert at their warning point and when they become overdue.\n\n"
      + (who === "visitor"
        // 1.19.0: a visitor isn't signed in, so a Settings link would only ask them to sign in.
        ? "Once signed in, each person chooses their own emails in Settings, and every email is kept under Reminders. [How reminders work](/help#reminders)"
        : "Each person chooses their own emails in [Settings](/app/settings), and every email is kept under Reminders. [More in Help](/help#reminders)");
  }
  const CHECK = "A check is one compliance rule to keep: an inspection due every so often, a limit that must not be passed, or a yes-or-no control that must be in place. "
    + "Each industry's checks are the failures that cost it the most; start with the ones marked **Top**. Open **Rule and source** on a check to see what it costs when missed and the rule it comes from.\n\n"
    + `${NOT_ADVICE} [More in Help](/help#check)`;
  const ADVICE = `No. ${NOT_ADVICE} Each check names the rule it comes from, so you can look it up or ask.`;
  const EXPORT = "On this page, press **Print** for a paper copy (or save it as a PDF from the print window), or **Export CSV** for a spreadsheet. Both have every check's status, reading, due date and rule. "
    + "For one page to show an inspector or your accountant, open the [Inspection-ready summary](/app/report/summary): what's current, what needs action, what's due soon, the last checks and who recorded them.";
  const DEMO_SAVED = "No. The demos use pretend data: nothing you do is saved and no emails go out. To keep your own checks, [start a free trial](/signup).";
  function plansAnswer(f) {
    const x = f || {};
    // The prices already say "a year" (plans.price_label): 1.18.0 stops "$299 a year a year".
    return `- **${words(x.classroom) || "Classroom"}** (${yearly(x.classroom_price)}): ${words(x.classroom_summary)}\n`
      + `- **${words(x.school) || "Whole school"}** (${yearly(x.school_price)}): ${words(x.school_summary)}\n\n[See the prices](/classrooms#price)`;
  }
  function lessonAnswer(f) {
    const x = f || {};
    return `A lesson is ${x.lesson_questions || 5} questions and takes about ${x.lesson_minutes || 3} minutes. The first lesson of each world opens the next world; `
      + "after the first lesson of every world comes the Class Challenge, which earns a certificate. [Open the teacher guide](/classrooms/guide)";
  }

  // ---------------------------------------------------------------- 1.18.0: every welcome button answers with no key

  // "Which checklist fits me?": asks what kind of business it is, with a link to each trade's page.
  function checklistAnswer(f) {
    const x = f || {};
    const list = (Array.isArray(x.trades) ? x.trades : []).filter((t) => t && typeof t.name === "string" && /^\/[\w/-]*$/.test(t.path || ""));
    const links = list.slice(0, 12).map((t) => `- [${words(t.name)}](${t.path})`).join("\n");
    return `**What kind of business is it?** Pick yours to see the checklists that fit it, what each one checks, and what OmniArmor doesn't cover:\n\n${links || "- [Every industry](/industries)"}\n\n`
      + `Not there? [All ${x.industries || ""} industries](/industries) each have their own starter list of ${x.top_count ? "the checks that cost them the most" : "checks"}. `
      + "You can pick more than one when you sign up. [Or see a demo](/demo) first.";
  }

  // "Which plan fits me?": the plans side by side, from plans.py's own names and prices.
  function planFitAnswer(f) {
    const x = f || {};
    const school = who === "teacher" || schoolSide;
    if (school) {
      return `**For a class or a school, paid yearly:**\n\n${plansAnswer(x).replace(/\n\n\[See the prices\]\(\/classrooms#price\)$/, "")}\n\n`
        + `Pick **${words(x.classroom) || "Classroom"}** for one class, **${words(x.school) || "Whole school"}** for every class and the school safety checklist. `
        + `Both start with a free ${x.pilot_days || 30}-day trial for one class, no card. [See the prices](/classrooms#price)`;
    }
    const year = (y) => (y ? `, or ${words(y)}${x.free_label ? ` (${words(x.free_label)})` : ""}` : "");
    return "**Two plans, one question:** do you want the Academy for your kids too?\n\n"
      + `- **${words(x.pro) || "Pro"}** (${words(x.pro_price)}${year(x.pro_yearly)}): ${words(x.pro_summary)}.\n`
      + `- **${words(x.plus) || "Plus"}** (${words(x.plus_price)}${year(x.plus_yearly)}): ${words(x.plus_summary)}.\n\n`
      + `Pick **${words(x.pro) || "Pro"}** if you only need the checklist; **${words(x.plus) || "Plus"}** if someone in the family may run the business one day. `
      + `${x.trial_days ? `Every plan starts with ${x.trial_days} days free, no card. ` : ""}`
      + `Teaching a class? [The classroom plans](/classrooms#price) are yearly. [All the prices](/pricing)`;
  }

  // "Explain this page": from its own headings and what it says it's for. 1.26.0: the page's name once ("Report:
  // the compliance report", not "...: Compliance report" after it), no heading that only repeats it, and no link
  // to the page you're already on (on /help, no "Read the help page").
  function explainPageAnswer() {
    const main = one("main") || document.body;
    const low = (t) => String(t || "").toLowerCase();
    const bare = words(document.title).replace(/\s+[·|–—-]\s+[^·|–—]*$/, "");
    const title = heading() || bare;
    const purpose = said(one(".page-head .sub, .hero p.lead, p.lead, p.sub, p.ac-lead", main));
    const where = words(screenName());
    const same = (a, b) => !!a && !!b && (low(a).includes(low(b)) || low(b).includes(low(a)));
    const named = !where || where === words(document.title) ? (title || "This page") : same(where, title) || !title ? where : `${where}: ${title}`;
    const parts = all("main h2", main).map((h) => said(h)).filter((t) => t && t.length < 90 && !same(t, title));
    const seen = new Set();
    const uniq = parts.filter((t) => { const k = t.toLowerCase(); if (seen.has(k)) return false; seen.add(k); return true; }).slice(0, 7);
    const out = [`**${named}**`];
    if (purpose && !same(purpose, title)) out.push("", purpose);
    if (uniq.length) out.push("", "**On this page:**", ...uniq.map((t) => `- ${t}`));
    const c = pageCounts();
    if (c) out.push("", `Right now: ${countsLine(c)}.`);
    if (who === "visitor") {
      const elsewhere = [["/help", "Read the help page", "for the common questions"], ["/demo", "see a demo", "with pretend data"]]
        .filter(([to]) => path !== to && !path.startsWith(`${to}/`));
      const offers = elsewhere.map(([to, label, why], n) => `[${n ? label : label[0].toUpperCase() + label.slice(1)}](${to}) ${why}`);
      out.push("", offers.length ? `${offers.join(", or ")}.` : "Ask me about anything you see here.");
    } else {
      out.push("", "Ask me about anything you see here, or press another button above.");
    }
    return out.join("\n");
  }

  // Teacher's "Add students": straight to the class page's Add students box (focused), or a link to it.
  function addStudentsAnswer() {
    const box = one("form#add-students textarea");
    if (box) {
      setTimeout(() => {
        try { window.Pilot.close(); } catch (_) { /* fine */ }
        try { box.scrollIntoView({ block: "center" }); } catch (_) { /* old browser */ }
        try { box.focus({ preventScroll: true }); } catch (_) { box.focus(); }
      }, 60);
      return "The **Add students** box is open on this page: type each student's first name or nickname, one on each line, then press **Add students**. "
        + "No email, last name, birthdate or photo. Each student then gets a join code.";
    }
    const cls = classHere();
    if (cls) return `[Open the Add students box${cls.name ? ` for ${words(cls.name)}` : ""}](/app/academy/classes/${cls.id}#add-students): type first names or nicknames, one on each line.`;
    if (CLASSES.length) return `Which class? Each one's page has the Add students box:\n${classLinks("#add-students")}`;
    return "[Add your class](/app/academy/classes#add-class) first: then its page has the Add students box, for first names or nicknames.";
  }

  // "Plan a week of lessons": a world a day for five days, from the Classroom track's worlds in order (the
  // teacher guide's), each with its lessons, about how long they take and a question to talk about.
  function weekAnswer(f) {
    const x = f || {};
    const worlds = (Array.isArray(x.class_plan) ? x.class_plan : []).filter((w) => w && typeof w.title === "string" && Number.isInteger(w.lessons) && w.lessons > 0);
    const minutes = Number(x.lesson_minutes) || 3;
    if (!worlds.length) return "[Open the teacher guide](/classrooms/guide): it lists every world in order, how long it takes and questions to talk about.";
    const days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"];
    const out = ["**A first week: one world a day.** Play its lessons in one sitting or split them across the day, then talk about it together.", ""];
    days.forEach((day, n) => {
      const w = worlds[n];
      if (!w) return;
      out.push(`- **${day}: ${words(w.title)}.** ${count(w.lessons, "lesson")}, about ${w.lessons * minutes} minutes.${w.talk ? ` Talk: "${words(w.talk)}"` : ""}`);
    });
    out.push("", "The first lesson of each world opens the next one, so nobody gets stuck waiting. A student who misses a day catches up on a school device. "
      + "[The teacher guide](/classrooms/guide) has every world, in order, with more questions.");
    return out.join("\n");
  }

  // "Summarise my report": from the report's own counts and rows (or this page's), no AI.
  function reportAnswer() {
    const rows = all("[data-report-table] tbody tr[data-check]").map((tr) => {
      const tag = one(".tag", tr);
      const level = ["BLOCKED", "WARNING", "CLEARED", "NONE"].find((l) => tag && tag.classList && tag.classList.contains(l)) || "NONE";
      const cells = all("td", tr);
      const days = tr.getAttribute("data-days");
      return { level, title: said(cells[0]), due: said(cells[3]).replace(/^—$/, ""), href: tr.getAttribute("data-check") || "",
        days: days === null || days === "" ? null : Number(days) };
    }).filter((r) => r.title);
    if (!rows.length) {
      const c = pageCounts();
      // 1.27.0: "What should I do first?" off the report names the check to fix first, with its link, from the
      // workspace's own list (it only said to open the report and ask again).
      const top = DUE.find((x) => x.level === "urgent") || DUE.find((x) => x.level === "soon");
      if (top) {
        return `**Fix first:** ${dueLine(top).slice(2)}${dueOn(top) ? ` (${daysOf(top) !== null && daysOf(top) < 0 ? "was due" : "due"} ${dueOn(top)})` : ""}.\n\n`
          + `${c ? `Right now: ${countsLine(c)}.\n\n` : ""}[Open the report](/app/report) for every check, and press this again there for what comes next.`;
      }
      return `${c ? `Right now: ${countsLine(c)}.\n\n` : ""}[Open the report](/app/report) and press this again for a summary of every check, with what to fix first.`;
    }
    const c = { BLOCKED: 0, WARNING: 0, CLEARED: 0, NONE: 0 };
    for (const r of rows) c[r.level] += 1;
    const link = (r) => linked(r.title, /^\/(?![/\\])\S*$/.test(r.href) ? r.href : "");
    const first = rows.filter((r) => r.level === "BLOCKED").sort((a, b) => (a.days ?? 0) - (b.days ?? 0));
    const warn = rows.filter((r) => r.level === "WARNING").sort((a, b) => (a.days ?? 9e9) - (b.days ?? 9e9));
    const empty = rows.filter((r) => r.level === "NONE");
    const out = [`**Your report: ${count(rows.length, "check")}.** ${countsLine(c)}.`];
    const when = (r) => (!r.due ? "" : r.days !== null && r.days < 0 ? `: overdue, it was due ${r.due}` : `: due ${r.due}`);
    if (first.length) out.push("", "**Fix first (blocked):**", ...first.slice(0, 4).map((r) => `- ${link(r)}${when(r)}`));
    if (warn.length) out.push("", "**Next (close to a limit or a date):**", ...warn.slice(0, 3).map((r) => `- ${link(r)}${when(r)}`));
    if (!first.length && !warn.length) out.push("", "Nothing is blocked or close to a limit. Well kept!");
    if (empty.length) out.push("", `${count(empty.length, "check")} still ${empty.length === 1 ? "has" : "have"} no reading: start with ${link(empty[0])}.`);
    out.push("", "For an inspector, press **Print** or **Export CSV** at the top of the report.");
    return out.join("\n");
  }

  // Short answers for the other page suggestions.
  function demoAnswer() {
    return "Two demos, both pretend and nothing saved:\n\n"
      + "- [The business demo](/demo/business): a restaurant with a few checks done, one overdue, a reminder email and the report. Or one for a [salon](/demo/salon), [tattoo studio](/demo/tattoo), [gym](/demo/gym) or [shop](/demo/shop).\n"
      + "- [The classroom demo](/demo/classroom): a class with its progress, join codes and a sample lesson.\n\nA demo lasts a while and then closes; open it again any time.";
  }
  const HISTORY = "History is the audit trail: every check saved, every reading and date, and every team or settings change, each with who made it and when. "
    + "It's the record an inspector asks for. Nothing in it can be edited. Press **Export CSV** on the History page for a spreadsheet of it all.";
  const HISTORY_EXPORT = "On the [History](/app/audit) page, press **Export CSV** at the top: you get every change, with who made it and when, as a spreadsheet.";
  const REMINDER_HOW = "Reminders come by themselves from each check's due date: give a check its date (when it was last done, or when it expires) on its checklist, "
    + "and the team is emailed before it's due, on the day, and each week while it's overdue. Each person picks their own emails in [Settings](/app/settings).";
  const INVITE = "In [Settings](/app/settings), under the team, press **Create invite link** and send the link to your colleague: it works once, for a few days. "
    + "They sign up with it and join this workspace. Only the owner can remove someone.";
  const EMAILS = "In [Settings](/app/settings), under **Your reminder emails**, choose the daily digest, the time-limit alerts, both or neither. Each person chooses their own; every reminder email links back there.";

  // 1.25.0: the Kitchen Safety Bundle in a few lines, from the tag's prices (the pricing page's one line, longer).
  function bundleAnswer(f) {
    const x = f || {};
    const app = words(N.fridge_app) || "the fridge app";
    return `**The Kitchen Safety Bundle** is for kitchens that use ${app}, ${N.company}'s fridge and freezer alarm app. `
      + `You pay ${app} ${words(x.bundle_price) || "for the bundle"}, and it includes OmniArmor's ${words(x.pro) || "Pro"} for that location while ${app} sends its daily reports, `
      + "which fill in your fridge temperature checks by themselves.\n\n"
      + `Want the Academy too? ${words(x.plus) || "Plus"} costs only the difference${x.bundle_upgrade ? `, ${words(x.bundle_upgrade)}` : ""}. [See every plan](/pricing)`;
  }

  // A page suggestion: an AI prompt (words), or an answer given at once.
  const C = (label, what) => (typeof what === "string" ? { label, prompt: what } : { label, ...what });
  const A = (fn) => ({ answer: (ctx) => fn((ctx && ctx.facts) || {}) });
  // One answer function each for a question a pill and a suggestion both ask (in their own words): core 1.4.3
  // counts them as one item (sameItem), so a typed question never ties between them and the row under an
  // answer shows it once.
  const WEEK = A(weekAnswer);
  const JOIN = A(joinAnswer);
  function pageChips() {
    if (path === "/") return [C("What does OmniArmor do?", A(whatAnswer)),
      C("Which plan fits me?", A(planFitAnswer)),
      C("How do reminders work?", A(reminderAnswer))];
    if (path === "/industries" || path.startsWith("/industries/") || path.startsWith("/for/")) {
      return [C("Which checklist fits me?", A(checklistAnswer)),
        C("What's a check?", { answer: CHECK }),
        C("Is this legal advice?", { answer: ADVICE })];
    }
    if (path === "/classrooms") return [C("How does the free trial work?", A(trialAnswer)),
      C("Is it safe for students?", { answer: SAFE }),
      C("Classroom or Whole school?", A(plansAnswer))];
    if (path === "/classrooms/guide") return [C("Plan a week", WEEK),
      C("How long is a lesson?", A(lessonAnswer))];
    if (path === "/demo") return [C("What can I try?", { answer: demoAnswer }), C("Is anything saved?", { answer: DEMO_SAVED })];
    // 1.25.0: Pilot on the pricing, Help and security pages too (a visitor's), each with its page's own questions.
    if (path === "/pricing") return [C("Which plan fits me?", A(planFitAnswer)),
      C("What's the Kitchen Safety Bundle?", A(bundleAnswer)),
      C("How do I cancel?", { answer: cancelAnswer })];
    if (path === "/help") return [C("How do I add a teammate?", A(teammateAnswer)),
      C("How do I change my password?", A(passwordAnswer)),
      C("How do reminder emails work?", A(reminderAnswer))];
    if (path === "/security") return [C("Is my data safe?", { answer: (ctx) => safeAnswer(ctx && ctx.facts, ctx && ctx.label) }),
      C("How do I delete my workspace?", A(deleteAnswer)),
      C("How do I export the report?", { answer: exportAnswer })];
    // A teacher's pages: OmniArmor's own suggestions, about their classes. The
    // school checklist's "What's overdue?" only on Whole school.
    if (path === "/app/academy/classes" || /^\/app\/academy\/classes\/\d+(\/join-codes)?$/.test(path)) {
      return [C("Add students", { answer: addStudentsAnswer }),
        C("How do join codes work?", JOIN),
        facts.school_checklist ? C("What's overdue?", { answer: dueAnswer })
          : C("Plan a week", WEEK)];
    }
    if (path === "/app" || path.startsWith("/app/industry/")) return [C("What's overdue?", { answer: dueAnswer }),
      C("Explain a check", { answer: explainAnswer }),
      C("What do the colours mean?", { answer: colourAnswer })];
    if (path === "/app/report") return [C("Summarise my report", { answer: reportAnswer }),
      C("What's overdue?", { answer: dueAnswer }), C("How do I export it?", { answer: EXPORT })];
    if (path === "/app/audit") return [C("What's in History?", { answer: HISTORY }), C("Export it", { answer: HISTORY_EXPORT })];
    if (path === "/app/notifications") return [C("When do reminders go out?", A(reminderAnswer)),
      C("Add a reminder", { answer: REMINDER_HOW })];
    if ((path === "/app/settings" || path === "/app/plan") && who === "teacher" && !facts.school_checklist) {
      return [C("Classroom or Whole school?", A(plansAnswer)),
        C("Invite a colleague", { answer: INVITE })];
    }
    if (path === "/app/settings" || path === "/app/plan") return [C("Choose my emails", { answer: EMAILS }),
      C("What do the plans include?", A(planFitAnswer))];
    // Anywhere else: OmniArmor's own suggestions for who is here.
    if (who === "teacher") return [C("Add students", { answer: addStudentsAnswer }),
      C("How do join codes work?", JOIN)];
    if (who === "business") return [C("What's overdue?", { answer: dueAnswer }),
      C("How do reminders work?", A(reminderAnswer))];
    return [C("What does OmniArmor do?", A(whatAnswer))];
  }

  // ---------------------------------------------------------------- 1.21.0: answers on every grown-up page
  //
  // Five questions people type on any page, not only where a button asks them: is my data safe, what does it
  // cost (the real plans, from pilot.py's facts), is this legal advice, how do I cancel and how do I export the
  // report. They are never buttons; with no key, a typed question that clearly asks one of them gets its answer
  // at once (chips() below hands it to the core's typed matching), unless this page's own buttons and
  // suggestions already answer it.
  const signedIn = who === "business" || who === "teacher";
  // 1.23.0: it starts with the answer to the question most people mean and says where the data is kept, in the
  // Security page's own words (one database on one server at the hosting company, and the second storage company
  // only when off-site backups are on). `asked` is what was typed or pressed. 1.26.0: the first words answer the
  // question asked: "Is my data safe?" starts "Yes.", "Do you sell my data?" "No, we don't sell your data.",
  // "Do you use tracking cookies?" "No tracking cookies.", "Where is my data stored?" with where.
  const SELL_WORDS = /\b(sell|sells|selling|sold|share|shares|sharing|shared|ads|advertis\w*|third|partners?)\b/i;
  const COOKIE_WORDS = /\b(cookies?|track|tracks|tracking|tracked|analytics)\b/i;
  const WHERE_WORDS = /\b(where|stored|store|kept|keep|server|servers|hosted|hosting|located|country)\b/i;
  function safeLead(asked) {
    const q = String(asked || "");
    if (SELL_WORDS.test(q)) return "No, we don't sell your data. We don't share it for ads, and no ad, analytics or tracking company sees the pages you open.";
    if (COOKIE_WORDS.test(q)) return "No tracking cookies, and no ad or analytics company sees the pages you open. OmniArmor uses one cookie, to keep you signed in. We don't sell your data.";
    if (WHERE_WORDS.test(q)) return "With our hosting company, in one place: the details are just below. We don't sell your data or share it for ads.";
    if (/\b(encrypt\w*|https|ssl|tls)\b/i.test(q)) return "On its way to and from you, yes: every page comes over a secure connection (HTTPS). Passwords are stored scrambled. We don't sell your data.";
    return "Yes. We don't sell your data, we don't share it for ads, and no ad, analytics or tracking company sees the pages you open.";
  }
  function storedLine(x) {
    const kept = Number(x.backup_keep) > 0 ? ` The newest ${count(Number(x.backup_keep), "daily copy", "daily copies")} are kept.` : "";
    return `- **Where it's stored:** in one database on one server, run for ${N.company} (who make OmniArmor) by our hosting company. `
      + `It is copied once a day, and each copy is checked before it is kept.${kept}`
      + (x.offsite_backup ? " A copy of each day's backup also goes to a second, separate storage company." : "");
  }
  function safeAnswer(f, asked) {
    const x = f || {};
    const security = typeof x.security_path === "string" && /^\/[\w/-]*$/.test(x.security_path) ? x.security_path : "/security";
    const out = [safeLead(asked), "",
    storedLine(x),
    "- Every page comes over a secure connection (HTTPS). Passwords are stored scrambled, so nobody can read them, and card numbers go straight to Stripe, never to OmniArmor.",
    `- ${N.assistant}, this helper, runs in your browser on your own AI key: OmniArmor's server never sees the key or the chat.`];
    if (who === "teacher" || schoolSide) {
      out.push(`- Students are added by first name or nickname only, have no accounts, and ${N.assistant} is never on a student's page.`);
    }
    out.push(`- Delete a record, a class or the whole workspace any time${signedIn ? " (the owner, in [Settings](/app/settings))" : ""}: it is gone from the app at once.`,
      "", `[Security and your data](${security}) has every detail, and [the privacy page](/privacy) says who can see what.`);
    return out.join("\n");
  }
  // 1.23.0: Help's top how-tos, answered with no key wherever they're typed (GLOBAL below).
  function teammateAnswer(f) {
    const days = Number((f || {}).invite_days) || 7;
    if (!signedIn) {
      return `Once your workspace is set up, the owner opens Settings and, under **Team**, presses **Create invite link**. The link works once, for ${count(days, "day")}: `
        + "your teammate signs up with it and joins your workspace. Every plan includes your whole team. [Start a free trial](/signup)";
    }
    return `In [Settings](/app/settings#team), under **Team**, the owner presses **Create invite link** and sends the link to the teammate: it works once, for ${count(days, "day")}. `
      + "They sign up with it and join this workspace, and get their own reminder emails. Only the owner can create links or remove someone (Remove, beside their name).";
  }
  function industryAnswer() {
    if (!signedIn) {
      return "You pick your industries when you sign up, and can add or remove one any time after in Settings: each brings its own checklist, with its top checks first. "
        + "[See every industry](/industries)";
    }
    if (who === "teacher") {
      return "A school's checklists are in [Settings](/app/settings#workspace), under **Your school checklists** (the owner ticks the ones you keep, then saves). "
        + "They come with the Whole school plan.";
    }
    return "The workspace owner opens [Settings](/app/settings#workspace), ticks the industry under **Industries** and presses **Save company settings**. "
      + "Its checklist shows in the menu at once, with its top checks first. Unticking one hides its checklist; the readings stay in History. [Every industry](/industries)";
  }
  function deleteAnswer(f) {
    const keep = Number((f || {}).backup_keep);
    const backups = keep > 0 ? `about ${count(keep, "day")}` : "a while";
    const where = signedIn ? "[Settings](/app/settings)" : "Settings";
    const what = who === "teacher" ? "every class, its students and their progress, the checklist records" : "every record, the audit trail, the reminder log and every learner";
    return "**Deleting your workspace closes your account; it isn't the same as cancelling your plan.** Cancelling stops the charges and keeps your records to see and download. "
      + "Deleting removes everything for good.\n\n"
      + `- **To delete:** the workspace owner opens ${where}, goes to **Delete workspace** at the bottom and types the ${who === "teacher" ? "school" : "company"} name. `
      + `That deletes ${what}, at once. With no other workspace, your sign-in goes too.\n`
      + "- **Paying for a plan?** Cancel it first on the Plans page (Manage billing); you can delete right away after that.\n"
      + `- **Download the report and History first** if you need them. Backups keep a copy for ${backups}.\n\n`
      + "[Only cancel the plan instead](/help#cancel) · [Deleting, in Help](/help#delete)";
  }
  // 1.25.0: resetting a forgotten password is the emailed link. 1.26.0: signed in, a password is changed in
  // Settings (Your password: the current one and a new one), so that comes first; the link is for a forgotten one.
  function passwordAnswer(f) {
    const hours = Number((f || {}).reset_hours) || 1;
    const link = `We email you a link that works once, for ${count(hours, "hour")}: open it and choose the new password.`;
    if (signedIn) {
      return "In [Settings](/app/settings#password), under **Your password**, type your current password and a new one, then press **Change password**. "
        + "Every other device you're signed in on is signed out.\n\n"
        + `**Forgot the current one?** Sign out, then on the sign-in page press **Forgot your password?** and type your email. ${link} [Reset my password](/forgot)`;
    }
    return `On the sign-in page, press **Forgot your password?** and type your email. ${link} `
      + "Every other device you were signed in on is signed out. No email? Check spam, or ask again after a few minutes. "
      + "Once you're signed in, you can also change it in Settings, under **Your password**. [Reset my password](/forgot)";
  }
  // "What does it cost?": the plans' real names and prices.
  function pricesAnswer(f) {
    const x = f || {};
    const year = (y) => (y ? `, or ${words(y)}${x.free_label ? ` (${words(x.free_label)})` : ""}` : "");
    const cap = (t) => { const w = words(t); return w ? w[0].toUpperCase() + w.slice(1) : ""; };
    const business = [`- **${words(x.pro) || "Pro"}: ${words(x.pro_price)}${year(x.pro_yearly)}.** ${cap(x.pro_summary)}.`,
      `- **${words(x.plus) || "Plus"}: ${words(x.plus_price)}${year(x.plus_yearly)}.** ${cap(x.plus_summary)}.`];
    const school = [`- **${words(x.classroom) || "Classroom"}: ${yearly(x.classroom_price)}.** ${words(x.classroom_summary)}`,
      `- **${words(x.school) || "Whole school"}: ${yearly(x.school_price)}.** ${words(x.school_summary)}`];
    if (who === "teacher" || schoolSide) {
      return ["**For a class or a school, paid yearly:**", "", ...school, "",
        `Both start with a free ${x.pilot_days || 30}-day trial for one class, no card.`,
        who === "teacher" ? "Your plan and its renewal date are on the [Plans page](/app/plan)." : "[See the prices](/classrooms#price)"].join("\n");
    }
    const out = ["**For a business, billed monthly" + (x.pro_yearly || x.plus_yearly ? " or yearly" : "") + ":**", "", ...business, ""];
    if (x.trial_days) out.push(`Every new workspace starts with ${x.trial_days} days free, no card.`);
    out.push(`For a school: **${words(x.classroom) || "Classroom"}** ${yearly(x.classroom_price)} or **${words(x.school) || "Whole school"}** ${yearly(x.school_price)}.`, "",
      who === "business" ? "Your own plan is on the [Plans page](/app/plan). [All the prices](/pricing)" : "[All the prices](/pricing)");
    return out.join("\n");
  }
  // 1.26.0: "Do you have a free plan?" and "Is there a yearly discount?", from the real plans (pilot.py's facts).
  function freePlanAnswer(f) {
    const x = f || {};
    if (who === "teacher" || schoolSide) {
      return `**No free plan, but a free trial:** one class, for ${x.pilot_days || 30} days, with no card. `
        + `After it, **${words(x.classroom) || "Classroom"}** is ${yearly(x.classroom_price)} and **${words(x.school) || "Whole school"}** ${yearly(x.school_price)}. `
        + "When a trial ends nothing is deleted: the class and its progress are kept. "
        + (who === "teacher" ? "[Your plan](/app/plan)" : "[See the prices](/classrooms#price)");
    }
    const yearlyToo = x.pro_yearly || x.plus_yearly ? ` (or yearly, ${words(x.free_label) || "for less"})` : "";
    return "**No free plan for the compliance tracker, but a free trial:** "
      + `${x.trial_days ? `every new workspace gets ${x.trial_days} days of everything in ${words(x.plus) || "Plus"}` : "every new workspace starts with a free trial"}, with no card. `
      + `After it, **${words(x.pro) || "Pro"}** is ${words(x.pro_price)} and **${words(x.plus) || "Plus"}** ${words(x.plus_price)}${yearlyToo}.\n\n`
      + "Without a plan nothing is deleted: you can still see, print and download your records, but new checks can't be saved and reminders pause. "
      + "The Academy's first worlds stay free for everyone. "
      + (who === "business" ? "[Your plan](/app/plan) · [All the prices](/pricing)" : "[All the prices](/pricing)");
  }
  // 1.28.0: "What happens when my trial ends?", from the real plans (plans.py, Help's "Is there a free trial?"): no card,
  // so nothing is charged; nothing is deleted; without a plan the tracker is read-only until a plan is chosen.
  function trialEndAnswer(f) {
    const x = f || {};
    if (who === "teacher" || schoolSide) {
      return `**When the free class trial ends, nothing is deleted:** the classes, their progress and the trial report are kept. `
        + `It needs no card, so nothing is charged. To go on, the school chooses **${words(x.classroom) || "Classroom"}** (${yearly(x.classroom_price)}) `
        + `or **${words(x.school) || "Whole school"}** (${yearly(x.school_price)}). `
        + (who === "teacher" ? "[Your plan](/app/plan)" : "[See the prices](/classrooms#price)");
    }
    const yearlyToo = yearlyOffered(x) ? `, or yearly (${words(x.free_label) || "for less"})` : "";
    return "**When the free trial ends, nothing is deleted and nothing is charged.** "
      + `${x.trial_days ? `The trial is ${x.trial_days} days of everything in ${words(x.plus) || "Plus"}, from the day you sign up, with no card. ` : "The trial needs no card. "}`
      + "After it, without a plan, the compliance tracker is read-only: you can still see, print and download every record, but new checks can't be saved and reminders pause "
      + `until the workspace owner chooses **${words(x.pro) || "Pro"}** (${words(x.pro_price)}) or **${words(x.plus) || "Plus"}** (${words(x.plus_price)})${yearlyToo}. `
      + "The Academy's first worlds stay free for everyone.\n\n"
      + (who === "business" ? "Your trial's days left are on the [Plans page](/app/plan). [All the prices](/pricing)"
        : "[Start your free trial](/signup) · [All the prices](/pricing)");
  }
  function yearlyAnswer(f) {
    const x = f || {};
    if (who === "teacher" || schoolSide) {
      return `A school's plans are paid yearly only: **${words(x.classroom) || "Classroom"}** ${yearly(x.classroom_price)}, `
        + `**${words(x.school) || "Whole school"}** ${yearly(x.school_price)}. There's no monthly price to compare, so no yearly discount. `
        + (who === "teacher" ? "[Your plan](/app/plan)" : "[See the prices](/classrooms#price)");
    }
    const lines = [[x.pro, x.pro_price, x.pro_yearly, "Pro"], [x.plus, x.plus_price, x.plus_yearly, "Plus"]]
      .filter(([, , y]) => y).map(([name, month, y, fallback]) => `- **${words(name) || fallback}:** ${words(month)}, or ${words(y)} paid yearly.`);
    if (!lines.length) {
      return `Not right now: **${words(x.pro) || "Pro"}** and **${words(x.plus) || "Plus"}** are billed monthly (${words(x.pro_price)} and ${words(x.plus_price)}). [All the prices](/pricing)`;
    }
    const where = who === "business" ? "the [Plans page](/app/plan)" : "the Plans page, once you're signed in";
    return `**Yes: paying yearly gives ${words(x.free_label) || "a lower price"}.**\n\n${lines.join("\n")}\n\n`
      + `The workspace owner picks yearly, or switches a monthly plan to it, on ${where}. `
      + "A yearly plan isn't refunded for the part of the year left if you cancel. [All the prices](/pricing)";
  }
  // The words for "Is this legal advice?", here and on the industry pages' own button (MATCH). 1.22.0: "Does
  // this guarantee I'm compliant?", "Will I get fined?".
  const LEGAL_WORDS = ["legal", "advice", "lawyer", "attorney", "law", "liable", "liability",
    "compliant", "compliance", "guarantee", "guaranteed", "fine", "fined", "sue", "sued", "court"];
  const LEGAL = `No. ${NOT_ADVICE}\n\n`
    + "Each check names the rule it comes from (open **Rule and source**), so you can look it up or ask. Rules change, and a city or state can add its own, "
    + "so for what a rule means for your business, ask your inspector, your local agency or a lawyer. OmniArmor keeps the dates, readings and reminders; it doesn't decide what the law requires of you.";
  // 1.25.0: "Can I get a refund?" starts with the answer to that, then how to cancel.
  const REFUND_WORDS = /\b(refunds?|refunded|money|back)\b/i;
  // 1.27.0: a business plan is yearly only where a yearly price is set up (plans.py; pilot.py's pro_yearly and
  // plus_yearly), as "Is there a yearly discount?" says: with none, the cancel answers say nothing about a year.
  const yearlyOffered = (f) => Boolean((f || {}).pro_yearly || (f || {}).plus_yearly);
  function refundLead(f) {
    if (who === "teacher" || schoolSide) {
      return "**No refund for the part of the year left.** A school's plan is paid yearly: cancelling stops the next year's charge, and the plan stays on until the end of the year paid for. "
        + "The free class trial needs no card, so it never costs anything.";
    }
    return "**No refund for time already paid for, and nothing more is charged once you cancel.** "
      + `The plan stays on until the end of the month paid for${yearlyOffered(f) ? " (or the year, for a yearly plan)" : ""}. `
      + "The free trial needs no card, so it never costs anything.";
  }
  function cancelAnswer(ctx) {
    const asked = ctx && typeof ctx.label === "string" ? ctx.label : "";
    const f = (ctx && ctx.facts) || facts;
    const body = cancelSteps(f);
    return REFUND_WORDS.test(asked) ? `${refundLead(f)}\n\n**To cancel:** ${body[0].toLowerCase()}${body.slice(1)}` : body;
  }
  function cancelSteps(f) {
    // 1.22.0: on the schools pages a visitor gets the school plans' answer too (it was the business plans' monthly
    // and pause options, which a school's plan doesn't have).
    if (who === "visitor" && schoolSide) {
      return "A school's plan (Classroom or Whole school) is paid yearly. The person who started it cancels on the Plans page, under Settings: "
        + "press **Cancel your plan**. It stays on until the end of the year paid for and isn't charged again (no refund for the part left). "
        + "Nothing is deleted when it ends. The free trial needs no card, so nothing is charged when it ends. [Classroom prices](/classrooms#price)";
    }
    if (who === "teacher") {
      return "The person who started the school's plan cancels on the [Plans page](/app/plan): press **Cancel your plan**. "
        + "A classroom plan is paid yearly, so it stays on until the end of the year paid for and isn't charged again (no refund for the part left). "
        + "Nothing is deleted when it ends. To delete a class or its students, use the class's own page.";
    }
    const where = who === "business" ? "the [Plans page](/app/plan)" : "the Plans page (Settings, Plan)";
    return `The workspace owner cancels on ${where}: press **Cancel or pause your plan**, then **Cancel my plan**. Nothing stops at once:\n\n`
      + "- **Monthly:** it stays on until the end of the month paid for, and isn't charged again.\n"
      + (yearlyOffered(f) ? "- **Yearly:** it stays on until the end of the year paid for, with no refund for the months left.\n" : "")
      + "- **A break instead?** A monthly plan can be paused for a few months: no charges, reminders stop, and it starts again by itself.\n\n"
      + "When the plan ends nothing is deleted: you can still see, print and download every record. [Cancelling, in Help](/help#cancel)";
  }
  function exportAnswer() {
    if (!signedIn) {
      return "Once signed in, the **Report** tab shows every check's status, reading, due date and rule: press **Print** for paper or a PDF, or **Export CSV** for a spreadsheet. "
        + "The **History** tab exports every change, with who and when, the same way. [See it in the demo](/demo/business)";
    }
    if (who === "teacher" && !facts.school_checklist) {
      return "Each class has a one-page report to print: on the class page, open its report and use your browser's **Print** (or save it as a PDF). "
        + "The [History](/app/audit) page exports every change, with who and when, as a spreadsheet (**Export CSV**).";
    }
    return "Open the [Report](/app/report) and press **Print** for a paper copy (or save it as a PDF from the print window), or **Export CSV** for a spreadsheet: "
      + "both have every check's status, reading, due date and rule. [History](/app/audit) has its own **Export CSV**, with who changed what and when. "
      + "For one page to show an inspector or an accountant, there's the [Inspection-ready summary](/app/report/summary).";
  }
  const GLOBAL = [
    { label: "Is my data safe?", answer: (ctx) => safeAnswer(ctx && ctx.facts, ctx && ctx.label),
      // The core reads at most 20 words per item. 1.22.0: "Do you sell my data?", "Who do you share it with?",
      // "Where is my data stored?", "Do you use tracking cookies?".
      match: ["safe", "safety", "secure", "security", "privacy", "private", "data", "encrypted", "hacked", "breach", "gdpr", "coppa", "ferpa",
        "sell", "sold", "share", "shared", "tracking", "cookies", "stored"],
      // 1.27.0: these alone ask it, whatever else is typed (aloneFor).
      alone: ["cookies", "kept"] },
    { label: "What does it cost?", answer: (ctx) => pricesAnswer(ctx && ctx.facts),
      match: ["price", "prices", "cost", "costs", "much", "pricing", "expensive", "cheap", "pay", "fee", "subscription", "dollars",
        "billing", "bill", "charge", "charged", "afford", "monthly"] },
    // 1.26.0: "Do you have a free plan?", "Is there a yearly discount?" (two words each, so they win over the price
    // answer, which no longer has "yearly").
    { label: "Is there a free plan?", answer: (ctx) => freePlanAnswer(ctx && ctx.facts),
      match: ["free", "forever", "freemium", "tier", "unpaid"] },
    { label: "Is there a yearly discount?", answer: (ctx) => yearlyAnswer(ctx && ctx.facts),
      match: ["yearly", "annual", "annually", "year", "discount", "discounts", "save", "saving", "savings", "deal", "cheaper"],
      // 1.28.0: "Is there a yearly plan?" and "Can I pay yearly?" tied with the free plan's "plan" and the price's "pay".
      alone: ["yearly", "annual", "annually"] },
    // 1.28.0: "What happens when my trial ends?", "after the free trial?" (nothing had "trial").
    { label: "What happens when the trial ends?", answer: (ctx) => trialEndAnswer(ctx && ctx.facts),
      match: ["trial", "trials", "end", "ends", "ended", "ending", "over", "expire", "expires", "expired", "after", "happen", "happens", "afterwards"],
      alone: ["trial"] },
    { label: "Is this legal advice?", answer: LEGAL, match: LEGAL_WORDS },
    // 1.23.0: "close" and "account" are deleting the workspace now (below), which isn't cancelling.
    { label: "How do I cancel?", answer: cancelAnswer, match: ["cancel", "cancelling", "canceling", "cancellation", "refund", "refunds", "refunded", "downgrade", "quit", "pause", "anytime", "contract", "commitment",
      "money", "back", "terminate"] },
    { label: "How do I export the report?", answer: exportAnswer,
      // 1.25.0: "How do I export my data?", "Can I download my records?" ("data" is in the safety and delete answers too, so
      // only "export", "download"... with it decides).
      match: ["export", "csv", "download", "print", "spreadsheet", "excel", "pdf", "inspector", "auditor", "data", "records", "record", "copy"] },
    // 1.23.0: the header button's own words, typed ("Explain this page"), get its answer; and Help's top how-tos.
    { label: "Explain this page", answer: explainPageAnswer, match: ["page", "screen", "overview", "summarise", "summarize"] },
    { label: "How do I add a teammate?", answer: (ctx) => teammateAnswer(ctx && ctx.facts),
      match: ["teammate", "invite", "colleague", "coworker", "employee", "employees", "worker", "workers", "team", "member", "members", "user", "users", "manager", "add"] },
    { label: "How do reminder emails work?", answer: (ctx) => reminderAnswer((ctx && ctx.facts) || {}),
      match: ["reminder", "email", "digest", "alert", "notification", "remind", "inbox", "unsubscribe"] },
    { label: "How do I add an industry?", answer: industryAnswer,
      match: ["industry", "industries", "checklist", "sector", "trade", "another", "add"] },
    { label: "How do I delete my workspace?", answer: (ctx) => deleteAnswer(ctx && ctx.facts),
      match: ["delete", "deleting", "deleted", "erase", "wipe", "workspace", "close", "closing", "account", "everything", "data", "remove", "shut"] },
    // 1.25.0: "How do I change my password?", "I forgot my password", "reset password".
    { label: "How do I change my password?", answer: (ctx) => passwordAnswer(ctx && ctx.facts),
      match: ["password", "passwords", "passcode", "reset", "forgot", "forgotten", "locked", "login", "signin"] },
  ];

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
  // an answer from this page and the site's facts, or a link. 1.18.0: every
  // welcome button does (summing up the report, adding students, planning a
  // week, which checklist or plan fits, explaining the page); only the key
  // pill and typed questions need the AI.
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
        ANSWER("bars", "Summarise my report", reportAnswer),
        ANSWER("spark", "What does this colour mean?", colourAnswer),
        KEY],
    },
    teacher: {
      tagline: "Your classroom helper",
      pills: [ANSWER("chat", "Add students", addStudentsAnswer),
        ANSWER("help", "How do join codes work?", JOIN.answer),
        ANSWER("spark", "Plan a week of lessons", WEEK.answer),
        LINK("copy", "Print certificates", certificatesLink()),
        KEY],
    },
    school: {
      tagline: "Your OmniArmor helper",
      pills: [ANSWER("help", "Is it safe for students?", SAFE),
        ANSWER("bolt", "How does the free trial work?", (ctx) => trialAnswer(ctx && ctx.facts)),
        ANSWER("spark", "Plan a week of lessons", WEEK.answer),
        ANSWER("bars", "Explain this page", explainPageAnswer),
        KEY],
    },
    visitor: {
      tagline: "Your OmniArmor helper",
      pills: [ANSWER("chat", "What does OmniArmor do?", (ctx) => whatAnswer(ctx && ctx.facts)),
        ANSWER("help", "Which checklist fits me?", (ctx) => checklistAnswer(ctx && ctx.facts)),
        // 1.21.0: the real plans and prices, with the link to Help under them (was only the link).
        ANSWER("bolt", "See the prices", (ctx) => pricesAnswer(ctx && ctx.facts)),
        ANSWER("bars", "Explain this page", explainPageAnswer),
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

  // Core 1.4.2: with no key, a typed question that clearly asks what one of these pills or suggestions is about gets
  // its answer at once, in this browser, nothing sent (the core's matchTyped: two of the typed words in the label or
  // in these words, or one word that is in these). Each list is the words people use for that question, with the
  // label's main word when it may be typed alone; a word that fits two questions is in both only where the other
  // words tell them apart ("What does blocked mean?" is the colours, "What's blocked?" is neither: it waits for a key).
  const MATCH = {
    // A business's
    // 1.25.0: "What's due this week?", "What's due soon?", "anything coming up next month?".
    "What's due or overdue?": ["overdue", "late", "today", "attention", "urgent", "expired", "expiring", "deadline", "upcoming", "blocked", "warning",
      "due", "week", "soon", "coming", "next", "month", "tomorrow"],
    "Explain this check": ["rule", "mean", "means", "source", "law", "regulation"],
    // 1.28.0: "Which check should I do first?", "Where do I start?", "What's my priority?".
    "Summarise my report": ["summary", "summarize", "summarise", "report", "inspector", "fix", "first", "start", "priority", "priorities"],
    "What does this colour mean?": ["color", "colors", "colour", "red", "orange", "faint", "status", "blocked", "warning", "cleared"],
    "How do I export it?": ["export", "csv", "download", "print", "spreadsheet", "excel", "report"],
    "What's in History?": ["history", "audit", "trail", "log", "changes"],
    "Export it": ["export", "csv", "download", "spreadsheet", "excel"],
    "When do reminders go out?": ["email", "emails", "sent", "send", "time"],
    "Add a reminder": ["set", "create", "new", "reminder"],
    "Choose my emails": ["email", "emails", "digest", "unsubscribe", "stop", "alerts", "notifications"],
    "Invite a colleague": ["invite", "colleague", "teammate", "staff", "coworker", "team", "member"],
    // A teacher's
    "Add students": ["pupil", "pupils", "kid", "kids", "child", "children", "roster", "enrol", "enroll"],
    "How do join codes work?": ["code", "codes", "slip", "slips", "lost", "forgot", "login", "log", "student", "students"],
    "Plan a week of lessons": ["schedule", "timetable", "monday", "curriculum", "teach", "plan", "week"],
    "Print certificates": ["certificate", "certificates", "award", "awards", "diploma"],
    "Classroom or Whole school?": ["price", "prices", "cost", "much", "pricing", "yearly", "plan", "plans", "classroom", "school"],
    // The schools pages'
    "Is it safe for students?": ["privacy", "private", "data", "safety", "secure", "security", "coppa", "ferpa",
      "sell", "sold", "share", "shared", "stored", "tracking"],
    "How does the free trial work?": ["trial", "free", "card"],
    "How long is a lesson?": ["minute", "minutes", "long", "time"],
    // A visitor's
    "What does OmniArmor do?": ["omniarmor", "aegizyn", "about", "work"],
    "Which checklist fits me?": ["checklist", "industry", "trade", "restaurant", "cafe", "salon", "barber", "gym", "shop", "tattoo", "pharmacy", "kind"],
    "See the prices": ["price", "prices", "cost", "much", "pricing", "expensive", "pay"],
    "Explain this page": ["page", "about", "summary", "summarise", "summarize", "overview"],
    "Which plan fits me?": ["plan", "plans", "pro", "plus", "difference", "compare", "choose"],
    "What do the plans include?": ["plan", "plans", "pro", "plus", "difference", "compare", "include", "includes"],
    "How do reminders work?": ["reminder", "reminders", "email", "emails", "remind", "alert"],
    "What's a check?": ["check"],
    "Is this legal advice?": LEGAL_WORDS,
    "What can I try?": ["demo", "try", "sample", "example"],
    "What's the Kitchen Safety Bundle?": ["bundle", "kitchen", "fridge", "fridges", "freezer", "sensor", "sensors", "temperature", String(N.fridge_app || "").toLowerCase()].filter(Boolean),
    "Is anything saved?": ["save", "saved", "stored", "kept", "delete"],
  };
  // 1.28.0: a pill's word that asks for it alone, whatever else is typed (aloneFor).
  const PILL_ALONE = { "Summarise my report": ["first"] };
  // 1.25.0: a page suggestion in the words of an answer on every page (GLOBAL: "How do I cancel?" on the pricing page)
  // takes that answer's words too; the page's own button stands in for it there, so "Can I get a refund?" still fits.
  const globalWords = (label) => (GLOBAL.find((x) => x.label === label) || {}).match;
  const withMatch = (x) => (MATCH[x.label] ? { ...x, match: MATCH[x.label] }
    : globalWords(x.label) ? { ...x, match: globalWords(x.label) } : x);
  welcome.pills = welcome.pills.map(withMatch);

  // On the welcome, a suggestion that asks what a pill asks stays out (the core lists both there). Once chatting,
  // every suggestion is back, in the pill's own words: core 1.4.3 counts a suggestion and a pill with one answer
  // (or one label) as one item (sameItem), so a typed question never ties between them and the row under an
  // answer shows it once. (1.20.0 kept them out with no key, a workaround 1.4.3 makes unnecessary.)
  function shownChips() {
    const list = pageChips().map(withMatch);
    let chatting = false;
    try { chatting = window.Pilot.store.loadChat().length > 0; } catch (_) { chatting = false; }
    if (!chatting) return list.filter((c) => !pillLabels.has(c.label) && !pillLabels.has(SAME[c.label]));
    return list.map((c) => (pillLabels.has(SAME[c.label]) ? withMatch({ ...c, label: SAME[c.label] }) : c));
  }

  // 1.21.0: the answers on every page (GLOBAL) for a typed question. The core compares a question typed with no
  // key with the welcome's pills and this page's suggestions (its typedHere, which asks chips() for them as the
  // question is sent). Just then, and only when none of those fits, chips() hands it the one GLOBAL answer that
  // clearly fits, found by the core's own matchTyped; nothing else changes and nothing shows on the screen. This
  // page's own buttons win: "How much does it cost?" on the classroom plans' page is still "Classroom or Whole
  // school?". `typed` is the question being sent, taken once.
  let typed = "";
  try {
    document.addEventListener("submit", (e) => {
      const form = e && e.target;
      if (!form || !form.classList || !form.classList.contains("pilot-compose")) return;
      const box = form.querySelector("textarea");
      typed = box ? String(box.value || "").trim() : "";
      setTimeout(() => { typed = ""; }, 0);
    }, true);
  } catch (_) { /* no document events: the page's own answers only */ }
  function globalFor(question, list) {
    const P = window.PilotPanel;
    if (!question || !P || typeof P.matchTyped !== "function") return null;
    const base = window.location.href || `https://omniarmor.invalid${path}`;
    const pills = P.ownPills(welcome.pills, base);
    if (P.matchTyped(question, pills.concat(P.cleanChips(list, base)))) return null;
    const here = new Set(pills.map((p) => p.label).concat(list.map((c) => c.label)));
    const extra = GLOBAL.filter((x) => !here.has(x.label));
    const hit = P.matchTyped(question, pills.concat(...extra.map((x) => P.cleanChips([x], base))));
    if (hit) return !hit.icon ? extra.find((x) => x.label === hit.label) || null : null;
    return aloneFor(question, pills.concat(P.cleanChips(list, base)));
  }
  // 1.27.0: a word that says on its own which answer is meant ("Do you use cookies?", "Where is my data kept?", where
  // the core wants two words to match): that GLOBAL answer, with the words typed as its match words so the core finds
  // it. Never when one of this page's own buttons lists that word under another label ("Is anything kept?" on the
  // demos page stays "Is anything saved?"), and never when two answers have it.
  // 1.28.0: a welcome pill can have such a word too (PILL_ALONE): "Which check should I do first?" tied between "Explain
  // this check" and "Summarise my report", which names the check to fix first.
  function aloneFor(question, items) {
    const P = window.PilotPanel;
    if (typeof P.wordsOf !== "function") return null;
    const asked = P.wordsOf(question);
    const said = (x) => P.wordsOf((x.alone || []).join(" ")).filter((w) => asked.includes(w));
    const pillsAlone = welcome.pills.filter((p) => PILL_ALONE[p.label] && p.answer)
      .map((p) => ({ label: p.label, answer: p.answer, match: p.match, alone: PILL_ALONE[p.label] }));
    const fits = GLOBAL.concat(pillsAlone).filter((x) => said(x).length);
    if (fits.length !== 1) return null;
    const pick = fits[0];
    const theirs = items.some((i) => i.label !== pick.label && (i.match || []).some((w) => said(pick).includes(w)));
    return theirs ? null : { ...pick, match: asked.concat(pick.match || []).slice(0, 20) };
  }
  function chips() {
    let keyed = false;
    try { keyed = Boolean(window.Pilot.store.ready()); } catch (_) { keyed = false; }
    const list = shownChips();
    const question = typed;
    typed = "";
    if (keyed || !question) return list;
    const extra = globalFor(question, list);
    return extra ? [extra] : list;
  }

  const mounted = window.Pilot.mount({
    appName: "OmniArmor",
    name: N.assistant,
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
    // Core 1.4.1 fades the robot out rather than cover a link or a bar that stays put; 1.4.2 measures a corner
    // raised above the tab bar (app.css) where it really is, so signed-in pages use that rule too (1.19.0 kept
    // 1.4.0's "tuck where it covers least" there). Hidden with the page still, the core's handle (a slice of the
    // robot at the screen's edge, where it covers nothing) opens Pilot; on by default.
    // Core 1.4.2: the suggestion after this page's own is OmniArmor's built-in look at the page (its headings,
    // what it is for and its counts), with or without a key, instead of "Summarise this" (AI only).
    screenChip: { label: "Explain this page", answer: explainPageAnswer },
    // No `modals`: OmniArmor has no pop-ups that aren't marked as dialogs
    // (Armo's bubble is a helper's, in yieldTo below), and the core already
    // steps back for anything covering the whole screen.
    storagePrefix: "omniarmor-pilot",
    // 1.18.0: OmniArmor's own colours for the window (app.css, ".pilot-root.omni-pilot"): warm black with the
    // orange-to-red edge, not the core's navy and violet. Layout and words stay the core's.
    themeClass: "omni-pilot",
    pack: d.pack || "",
    // Exactly the hosts the security policy lets a browser reach for an
    // OpenAI-compatible API (pilot.COMPATIBLE_HOSTS and the person's own computer).
    compatibleHosts: (d.hosts || "").split(/\s+/).filter(Boolean),
    privacyUrl: "/privacy",
    // One plain sentence on what an AI key is and where a grown-up gets one;
    // the window shows it under the pills (before a key is set) and in the
    // key settings.
    keyNote: `An AI key is a private code from an AI company that lets ${N.assistant} think for you, billed to the key's owner: `
      + "a grown-up gets one by signing up on that company's website. AI keys are for grown-ups (the AI companies require 18+).",
    // Core 1.3.0: the one line the welcome shows above the box (the full note
    // stays beside the key settings and in help).
    keyNoteShort: "AI keys are for grown-ups (18+).",
    audienceNote: `The people using ${N.assistant} here are grown-ups: small-business owners and their teams, and teachers or school staff. `
      + `Students never use ${N.assistant}. Never ask for or repeat students' names; a teacher may type first names for adding students, and that's all. `
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
      ".pick", "[data-teacher-guide] p", "[data-teacher-guide] li", "[data-teacher-guide] h2", "[data-teacher-guide] h3",
      // 1.18.0: the app's picture under the headline (its Blocked and Warning rows) and a folded line like the
      // join codes page's "Lost the slips?": the robot steps aside rather than sit on them.
      ".hero-shot", "details > summary",
      // 1.21.0: a page's small notes, like the class page's "A lesson is one level passed..." just above the tab
      // bar, where the peeking robot covered a word.
      ".hint"],
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
