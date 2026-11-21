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

  const C = (label, prompt) => ({ label, prompt });
  function chips() {
    if (path === "/") return [C("What does OmniArmor do?", "In plain words, what does OmniArmor do for a small business?"),
      C("Which plan fits me?", "Which OmniArmor plan would fit me? Ask me one or two questions first."),
      C("How do reminders work?", "How do OmniArmor's reminder emails work?")];
    if (path === "/industries" || path.startsWith("/industries/") || path.startsWith("/for/")) {
      return [C("Which checklist fits me?", "Which OmniArmor checklist fits my business? Ask me what kind of business it is first."),
        C("What's a check?", "What is a check, and what does “Rule and source” show?"),
        C("Is this legal advice?", "Is OmniArmor legal advice?")];
    }
    if (path === "/classrooms") return [C("How does the free trial work?", "How does the free classroom trial work?"),
      C("Is it safe for students?", "What does OmniArmor keep about my students?"),
      C("Classroom or Whole school?", "What's the difference between Classroom and Whole school?")];
    if (path === "/classrooms/guide") return [C("Plan a week", "Help me plan one world a week for my class."),
      C("How long is a lesson?", "How long does a lesson take, and how does a student unlock the next one?")];
    if (path === "/demo") return [C("What can I try?", "What can I try in the demos?"), C("Is anything saved?", "Is anything I do in the demo saved?")];
    // A teacher's pages: OmniArmor's own suggestions, about their classes. The
    // school checklist's "What's overdue?" only on Whole school.
    if (path === "/app/academy/classes" || /^\/app\/academy\/classes\/\d+(\/join-codes)?$/.test(path)) {
      return [C("Add students", "Add students to my class."),
        C("How do join codes work?", "How do join codes work for my students?"),
        facts.school_checklist ? C("What's overdue?", "What's due or overdue on the school checklist?")
          : C("Plan a week", "Help me plan one world a week for my class.")];
    }
    if (path === "/app" || path.startsWith("/app/industry/")) return [C("What's overdue?", "What's due or overdue?"),
      C("Explain a check", "Explain one of my checks and the rule it comes from."),
      C("What do the colours mean?", "What does each colour and status mean?")];
    if (path === "/app/report") return [C("Summarise my report", "Summarise my report."),
      C("What's overdue?", "What's due or overdue?"), C("How do I export it?", "How do I print or export the report for an inspector?")];
    if (path === "/app/audit") return [C("What's in History?", "What does the History page record?"), C("Export it", "How do I export the audit trail?")];
    if (path === "/app/notifications") return [C("When do reminders go out?", "When do reminder emails go out?"),
      C("Add a reminder", "Add a reminder for one of my checks.")];
    if ((path === "/app/settings" || path === "/app/plan") && who === "teacher" && !facts.school_checklist) {
      return [C("Classroom or Whole school?", "What's the difference between Classroom and Whole school?"),
        C("Invite a colleague", "How do I invite another teacher to our school's workspace?")];
    }
    if (path === "/app/settings" || path === "/app/plan") return [C("Choose my emails", "How do I choose which reminder emails I get?"),
      C("What do the plans include?", "What does each plan include?")];
    // Anywhere else: OmniArmor's own suggestions for who is here.
    if (who === "teacher") return [C("Add students", "Add students to my class."),
      C("How do join codes work?", "How do join codes work for my students?")];
    if (who === "business") return [C("What's overdue?", "What's due or overdue?"),
      C("How do reminders work?", "How do OmniArmor's reminder emails work?")];
    return [C("What does OmniArmor do?", "In plain words, what does OmniArmor do for a small business?")];
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

  const mounted = window.Pilot.mount({
    appName: "OmniArmor",
    name: "Pilot",
    tagline: "Your AI copilot. Powered by you.",
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
    audienceNote: "The people using Pilot here are grown-ups: small-business owners and their teams, and teachers or school staff. "
      + "Students never use Pilot. Never ask for or repeat students' names; a teacher may type first names for adding students, and that's all. "
      + "OmniArmor is decision support, not legal advice: for what a rule means in their area, suggest checking with an expert.",
    kidView,
    // Pilot core 1.1.1 keeps the robot out of the way: it keeps off the
    // page's own words and buttons wherever the page is scrolled to, and off
    // a box being typed in. On top of that it gives Armo (the companion, with
    // his bubble) room, and never sits on a status tag (NO READING, BLOCKED
    // and the rest), a Top 5 badge, the Kitchen Safety Bundle note, a check's
    // message, a flash or banner, Armo's bubble and badge, the "First name
    // only?" card or the menu at the top (Sign out among it). When one of
    // those is where it sits, it moves to a free corner, or tucks away at the
    // edge until tapped, with only a slice showing. The tab bar is kept clear
    // by app.css, which puts the robot's bottom corners above it.
    yieldTo: [".companion"],
    avoid: [".tag", ".top-n", ".bundle", ".msg", ".entry-top", ".flash", ".plan-banner", ".ac-badge",
      ".companion-bubble", ".companion-fix", ".companion-badge", "[data-confirm-names]", ".topbar .nav"],
    // On a phone the robot never tucks at an edge: it stays whole in the
    // bottom-right corner, the one corner it shares with Armo, and only one
    // of them shows (app.css, "One helper, one corner"). So the page's column
    // needs no side room for it.
    gutter: false,
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
