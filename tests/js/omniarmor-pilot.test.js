// OmniArmor's Pilot pack and tools, run in Node:
// `node --test tests/js/omniarmor-pilot.test.js` (tests/test_pilot.py runs it too).
// The browser is faked: OmniArmor's pages, its forms and the AI provider.
// Nothing leaves this machine.
"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const path = require("node:path");

const core = (f) => path.join(__dirname, "..", "..", "omniarmor_app", "static", "pilot", f);
const site = (f) => path.join(__dirname, "..", "..", "omniarmor_app", "static", f);
const Store = require(core("pilot-store.js"));
const Providers = require(core("pilot-providers.js"));
globalThis.PilotProviders = Providers;
const Engine = require(core("pilot-engine.js"));

const FACTS = { pro: "Pro", pro_price: "PRO-PRICE", plus: "Plus", plus_price: "PLUS-PRICE", pro_yearly: "", plus_yearly: "",
  free_label: "2 months free", trial_days: 14, bundle_price: "BUNDLE-PRICE", bundle_upgrade: "UPGRADE-PRICE",
  classroom: "Classroom", classroom_price: "CLASSROOM-PRICE", classroom_summary: "One class.", school: "Whole school",
  school_price: "SCHOOL-PRICE", school_summary: "Every class.", pilot_days: 30, class_size: 35, class_worlds: 16,
  class_lessons: 107, lesson_questions: 5, lesson_minutes: 3, class_business: "Sunny Cup Lemonade", industries: 51,
  checks: 510, top_count: 3, reminder_days: [30, 7, 1], max_learners: 12, support: "" };

// The pack, loaded fresh for one kind of visitor ("business", "teacher" or "visitor").
function loadPack(who, extra = {}) {
  globalThis.window = { Pilot: { config: { facts: { who, demo: false, readonly: false, ...FACTS, ...extra } } } };
  delete require.cache[site("pilot-omniarmor-pack.js")];
  const pack = require(site("pilot-omniarmor-pack.js"));
  delete globalThis.window;
  return pack;
}

// A pretend browser: the form token on the page, and OmniArmor answering a
// form with its flash messages (and, after adding students, any name it
// couldn't add).
function fakeBrowser(pack, answer = () => ({ flashes: [{ kind: "ok", text: "Saved." }] })) {
  const posts = [];
  const io = pack._test.io;
  io.doc = () => ({ querySelector: (sel) => (sel.includes("csrf_token") ? { value: "page-token" } : null) });
  io.fetch = async (url, init) => {
    const fields = {};
    for (const [k, v] of init.body.entries()) fields[k] = k in fields ? [].concat(fields[k], v) : v;
    posts.push({ url, fields, method: init.method, credentials: init.credentials });
    const body = answer(url, fields);
    return { ok: true, status: 200, url: "https://omniarmor.test/app/industry/2", text: async () => JSON.stringify(body) };
  };
  io.parse = (html) => {
    const page = JSON.parse(html);
    const node = (t, kind) => ({ textContent: t, classList: { contains: (c) => c === kind } });
    return {
      querySelectorAll: (sel) => {
        if (sel === ".flashes .flash") return (page.flashes || []).map((f) => node(f.text, f.kind));
        if (sel === "[data-not-added] [data-rejected]") return (page.rejected || []).map((t) => node(t));
        return [];
      },
    };
  };
  return posts;
}

const CHECKS = [
  { checklistId: 2, checklist: "RestoArmor", key: "date_marking", title: "Date marking of ready-to-eat food", level: "BLOCKED", status: "Blocked",
    says: "Overdue by 2 days", due: "Overdue by 2 days · 2026-11-18", days: -2, kind: "max", mode: "since", timed: false, top: "Top 3 · #1",
    question: "When were the labels last checked?", limits: "Limit 7 days", cost: "Food made people sick.", rule: "FDA Food Code 3-501.17" },
  { checklistId: 2, checklist: "RestoArmor", key: "sick_worker", title: "Sick employee working", level: "NONE", status: "No reading",
    says: "", due: "", days: null, kind: "forbidden", mode: "", timed: false, top: "", question: "Is a sick employee working?", limits: "", cost: "", rule: "FDA Food Code 2-201.12" },
  { checklistId: 2, checklist: "RestoArmor", key: "handwash_sink", title: "Handwashing sink stocked", level: "NONE", status: "No reading",
    says: "", due: "", days: null, kind: "required", mode: "", timed: false, top: "Top 3 · #2", question: "Is every handwashing sink stocked?", limits: "", cost: "", rule: "FDA Food Code 6-301.12" },
  { checklistId: 30, checklist: "HRArmor", key: "i9_new_hire", title: "Form I-9 for a new hire", level: "WARNING", status: "Warning",
    says: "Due tomorrow", due: "Due in 1 day · 2026-11-21", days: 1, kind: "max", mode: "due", timed: false, top: "", question: "When is it due?", limits: "", cost: "", rule: "8 CFR 274a.2" },
  { checklistId: 30, checklist: "HRArmor", key: "poster", title: "Labor law posters up", level: "CLEARED", status: "Cleared",
    says: "", due: "Due in 20 days · 2026-12-10", days: 20, kind: "max", mode: "due", timed: false, top: "", question: "", limits: "", cost: "", rule: "29 CFR 516.4" },
];

function engineFor(pack, { replies, confirm = [], plan = "all" }) {
  const store = Store.create({ prefix: "oa", local: null, session: null });
  store.saveSettings({ provider: "anthropic", key: "test-key", model: "test-model" });
  const sent = [];
  const asked = { confirm: [], plan: [] };
  const providers = { ...Providers, chat: async (s, req) => { sent.push(req); return { raw: {}, toolCalls: [], stop: "done", ...replies.shift() }; } };
  const host = {
    confirm: async (label) => { asked.confirm.push(label); return confirm.length ? confirm.shift() : false; },
    plan: async (labels) => { asked.plan.push(labels); return plan; },
  };
  const engine = Engine.create({ store, providers, host, config: { appName: "OmniArmor", tools: pack.tools, kidView: () => false,
    knowledge: pack.knowledge, strengths: pack.strengths } });
  return { engine, asked, sent };
}
const call = (name, args, id = name) => ({ id, name, args });
const toolResult = (sent, id) => sent[sent.length - 1].messages.find((m) => m.role === "tool").results.find((r) => r.id === id).content;

// ---------------------------------------------------------------- the pack

test("the knowledge pack is written from the real app, with prices only from the server", () => {
  const pack = loadPack("business");
  for (const fact of ["Rule and source", "Done today", "Blocked (red)", "Warning (orange)", "Cleared", "No reading", "30, 7 or 1 day",
    "Update several at once", "Pro", "Plus", "Classroom", "Whole school", "first name or nickname", "join code", "teacher guide",
    "trial report", "decision support, not legal advice", "Kitchen Safety Bundle", "Your reminder emails"]) {
    assert.ok(pack.knowledge.toLowerCase().includes(fact.toLowerCase()), fact);
  }
  assert.doesNotMatch(pack.knowledge, /\$\s?\d/, "no price is typed into the pack");
  assert.doesNotMatch(pack.strengths.join(" "), /\$\s?\d|\d+%/, "no made-up numbers in the strengths");
  assert.ok(pack.strengths.length >= 10);
  const live = pack.facts();
  for (const price of ["PRO-PRICE", "PLUS-PRICE", "CLASSROOM-PRICE", "SCHOOL-PRICE", "BUNDLE-PRICE"]) assert.ok(live.includes(price), price);
});

test("OmniArmor's tools: four kinds of reading, five changes that ask first", () => {
  const pack = loadPack("teacher");
  const tools = pack.tools();
  assert.deepEqual(tools.filter((t) => t.kind === "read").map((t) => t.name),
    ["whats_due", "explain_check", "summarise_report", "what_colour_means", "my_classes"]);
  assert.deepEqual(tools.filter((t) => t.kind === "change").map((t) => t.name),
    ["mark_done_today", "update_check", "add_reminder", "answer_checks", "add_students"]);
  for (const t of tools) assert.ok(Engine.checkTool(t), t.name);
  for (const t of tools) assert.doesNotMatch(t.name, /plan|delete|remove|invite|member|team|subscri|pay|student_account|learner/, t.name);
});

test("a visitor gets no workspace tools, a business no student tools, and a read-only workspace no check changes", () => {
  const offered = (pack) => pack.tools().filter((t) => t.available()).map((t) => t.name);
  assert.deepEqual(offered(loadPack("visitor")), ["what_colour_means"]);
  assert.ok(!offered(loadPack("business")).includes("add_students"));
  assert.ok(!offered(loadPack("business")).includes("my_classes"));
  assert.ok(offered(loadPack("teacher")).includes("add_students"));
  const ro = offered(loadPack("business", { readonly: true }));
  assert.deepEqual(ro, ["whats_due", "explain_check", "summarise_report", "what_colour_means"]);
});

test("no tools at all on a child's view", () => {
  const pack = loadPack("teacher");
  const store = Store.create({ prefix: "k", local: null, session: null });
  const engine = Engine.create({ store, providers: Providers, host: {}, config: { tools: pack.tools, kidView: () => true } });
  assert.deepEqual(engine.tools(), []);
});

// ---------------------------------------------------------------- reading

test("what's due: overdue, warnings and due soon, from the workspace's own checks", async () => {
  const pack = loadPack("business");
  pack._test.setIndex(CHECKS);
  const due = await pack.tools().find((t) => t.name === "whats_due").run({ within_days: 30 });
  assert.deepEqual(due.overdue.map((c) => c.check), ["Date marking of ready-to-eat food"]);
  assert.deepEqual(due.warnings.map((c) => c.check), ["Form I-9 for a new hire"]);
  assert.deepEqual(due.due_within_30_days.map((c) => c.check), ["Labor law posters up"]);
  assert.equal(due.checks_without_a_reading, 2);
  assert.ok(!JSON.stringify(due).includes("updated"), "never who changed what");
});

test("explain a check: its rule and source, and which answer means a problem", async () => {
  const pack = loadPack("business");
  pack._test.setIndex(CHECKS);
  const explain = pack.tools().find((t) => t.name === "explain_check");
  const one = await explain.run({ check: "date marking" });
  assert.equal(one.rule_and_source.rule, "FDA Food Code 3-501.17");
  assert.match(one.colour, /Blocked \(red\)/);
  assert.equal((await explain.run({ check: "Sick employee working" })).answer_that_means_a_problem, "Yes");
  assert.match((await explain.run({ check: "a" })).error, /More than one|No check/);
  const colours = pack.tools().find((t) => t.name === "what_colour_means");
  assert.match(colours.run({ colour_or_status: "orange" }).meaning, /^Warning/);
});

// ---------------------------------------------------------------- changes ask first

test("a change waits for Allow: Cancel posts nothing, Allow posts the app's own form with the page's token", async () => {
  for (const [allow, posted] of [[false, 0], [true, 1]]) {
    const pack = loadPack("business");
    pack._test.setIndex(CHECKS);
    const posts = fakeBrowser(pack, () => ({ flashes: [{ kind: "ok", text: "Marked done today; the next cycle has started." }] }));
    const { engine, asked, sent } = engineFor(pack, { confirm: [allow],
      replies: [{ toolCalls: [call("mark_done_today", { check: "Date marking of ready-to-eat food" })] }, { text: "ok" }] });
    await engine.send("Mark date marking done today");
    assert.deepEqual(asked.confirm, ["Mark “Date marking of ready-to-eat food” (RestoArmor) done today; its next cycle starts today"]);
    assert.equal(posts.length, posted);
    if (allow) {
      assert.deepEqual(posts[0], { url: "/app/industry/2/rule/date_marking", fields: { csrf_token: "page-token", action: "done_today" },
        method: "POST", credentials: "same-origin" });
      assert.match(toolResult(sent, "mark_done_today"), /Marked done today/);
    } else {
      assert.match(toolResult(sent, "mark_done_today"), /said no/);
    }
  }
});

test("update a check, add a reminder: each asks first and says exactly what will change", async () => {
  const pack = loadPack("business");
  pack._test.setIndex(CHECKS);
  const posts = fakeBrowser(pack);
  const { engine, asked } = engineFor(pack, { confirm: [true, true],
    replies: [{ toolCalls: [call("update_check", { check: "Handwashing sink stocked", answer: "no" })] }, { text: "ok" },
      { toolCalls: [call("add_reminder", { check: "Form I-9 for a new hire", date: "2026-12-01" })] }, { text: "ok" }] });
  await engine.send("The sinks aren't stocked");
  await engine.send("Remind us about the I-9");
  assert.deepEqual(asked.confirm, [
    "Answer No to “Handwashing sink stocked” (RestoArmor). No means a problem here, so it will show Blocked",
    "Set “Form I-9 for a new hire” (HRArmor) as due on 2026-12-01; the team gets reminder emails 30, 7, 1 days before, and on the day"]);
  assert.deepEqual(posts.map((p) => [p.url, p.fields.action, p.fields.answer || p.fields.date]),
    [["/app/industry/2/rule/handwash_sink", "save", "no"], ["/app/industry/30/rule/i9_new_hire", "save", "2026-12-01"]]);
});

test("a check the card couldn't name exactly is never guessed at", async () => {
  const pack = loadPack("business");
  const posts = fakeBrowser(pack);
  const tool = pack.tools().find((t) => t.name === "mark_done_today");
  assert.equal(tool.describe({ check: "marking" }), "mark “marking” done today; its next cycle starts today");
  assert.match((await tool.run({ check: "marking" })).error, /No check here matches “marking” exactly/);
  assert.equal(posts.length, 0);
});

// ---------------------------------------------------------------- never

test("forbidden actions are refused before anything leaves the browser", async () => {
  const pack = loadPack("teacher");
  const posts = fakeBrowser(pack);
  const { refuse, post } = pack._test;
  for (const url of ["/app/plan/switch", "/app/plan/cancel", "/app/plan/pause", "/app/plan/checkout", "/app/plan/manage",
    "/app/academy/classes/checkout", "/app/settings/delete", "/app/settings/invite", "/app/settings/member/3/remove",
    "/app/settings/company", "/app/academy/classes/4/delete", "/app/academy/classes/4/students/9/remove",
    "/app/academy/classes/4/join-codes", "/app/academy/classes/4/leaderboard", "/app/academy/9/delete",
    "/app/academy/9/join-code", "/app/academy/9/devices/sign-out", "/app/academy/9/track", "/app/academy/learners",
    "/app/settings/connections/cyberlogix/revoke", "/logout", "https://example.com/app/industry/2/rule/x"]) {
    assert.match(refuse(url, {}), /Pilot can't do that/, url);
    assert.match((await post(url, {})).error, /Pilot can't do that|for a teacher/, url);
  }
  // The allowed forms carry only their own fields: no clearing a reading, no changing a limit.
  for (const fields of [{ action: "clear" }, { action: "override", limit: "9" }, { action: "reset_override" }, { action: "save", limit: "1" }]) {
    assert.match(refuse("/app/industry/2/rule/date_marking", fields), /Pilot can't do that/, JSON.stringify(fields));
  }
  assert.match(refuse("/app/industry/2/bulk", { bulk_action: "clear" }), /Pilot can't do that/);
  assert.equal(posts.length, 0, "nothing was sent");
  assert.equal(refuse("/app/academy/classes/4/students", { names: "Maya" }), "");
  assert.match(loadPack("business")._test.refuse("/app/academy/classes/4/students", { names: "Maya" }), /teacher/);
});

test("asked to change the plan, delete or invite, Pilot has no tool for it, and the engine refuses such names", async () => {
  const pack = loadPack("business");
  const posts = fakeBrowser(pack);
  const { engine, sent } = engineFor(pack, {
    replies: [{ toolCalls: [call("delete_workspace", {}), call("upgrade_plan", {}), call("invite_member", {})] }, { text: "I can't do that." }] });
  await engine.send("Upgrade my plan, delete the old data and invite Sam");
  const offered = sent[0].tools.map((t) => t.name);
  assert.ok(!offered.some((n) => /delete|plan|invite|remove|member/.test(n) && n !== "pilot_plan"), offered.join(","));
  for (const id of ["delete_workspace", "upgrade_plan", "invite_member"]) assert.match(toolResult(sent, id), /no such tool/);
  for (const name of ["delete_check", "remove_member", "invite_teammate", "upgrade_plan", "cancel_subscription", "pay_invoice"]) {
    assert.equal(Engine.checkTool({ name, kind: "change", describe: () => "", run: () => {} }), null, name);
  }
  assert.equal(posts.length, 0);
});

// ---------------------------------------------------------------- the bulk-answer rule

test("several answers at once never give Yes where Yes means a problem", async () => {
  const pack = loadPack("business");
  pack._test.setIndex(CHECKS);
  const posts = fakeBrowser(pack, () => ({ flashes: [{ kind: "ok", text: "Updated 1 check: answer yes." }] }));
  const tool = pack.tools().find((t) => t.name === "answer_checks");
  const args = { checks: ["Handwashing sink stocked", "Sick employee working"], answer: "yes" };
  assert.equal(tool.describe(args), "answer Yes to 1 check: “Handwashing sink stocked”. Left out: “Sick employee working”"
    + " (Yes would mean a problem there: answer it on its own)");
  const out = await tool.run(args);
  assert.deepEqual(posts.map((p) => [p.url, p.fields.bulk_action, p.fields.keys]), [["/app/industry/2/bulk", "yes", "handwash_sink"]]);
  assert.deepEqual(out.left_out, ["Sick employee working: Yes would mean a problem, so answer it on its own"]);

  // Only checks where Yes is the bad answer: nothing is sent at all.
  const only = { checks: ["Sick employee working"], answer: "yes" };
  tool.describe(only);
  assert.match((await tool.run(only)).error, /Yes would mean a problem/);
  assert.equal(posts.length, 1);
  // No is a fine answer to give together.
  const no = { checks: ["Sick employee working", "Handwashing sink stocked"], answer: "no" };
  tool.describe(no);
  await tool.run(no);
  assert.deepEqual(posts[1].fields.keys, ["sick_worker", "handwash_sink"]);
});

test("a plan of single answers can't slip Yes onto a check where Yes means a problem", async () => {
  const pack = loadPack("business");
  pack._test.setIndex(CHECKS);
  const posts = fakeBrowser(pack);
  const { engine, asked, sent } = engineFor(pack, { plan: "all", replies: [{ toolCalls: [
    call("update_check", { check: "Handwashing sink stocked", answer: "yes" }, "a"),
    call("update_check", { check: "Sick employee working", answer: "yes" }, "b")] }, { text: "ok" }] });
  await engine.send("Answer yes to both");
  assert.deepEqual(asked.plan, [["Answer Yes to “Handwashing sink stocked” (RestoArmor)",
    "Not answer Yes to “Sick employee working” (RestoArmor) with other changes: Yes means a problem there, so it's answered on its own"]]);
  assert.deepEqual(posts.map((p) => p.url), ["/app/industry/2/rule/handwash_sink"]);
  assert.match(toolResult(sent, "a"), /Not done: “Sick employee working”/);
});

// ---------------------------------------------------------------- students: first names only

test("add students: first names or nicknames only, through the class's own form, and never the class list back", async () => {
  const pack = loadPack("teacher");
  pack._test.setClasses([{ id: 7, name: "Room 12", students: 3 }, { id: 8, name: "Club", students: 0 }]);
  const posts = fakeBrowser(pack, () => ({ flashes: [{ kind: "ok", text: "Added 2 students to Room 12." }], rejected: [] }));
  const { engine, asked, sent } = engineFor(pack, { confirm: [true], replies: [{ toolCalls: [call("add_students",
    { class_name: "Room 12", names: ["Maya", "Leo R.", "Sam Lopez", "kid@example.com", "Ava2"] })] }, { text: "ok" }] });
  await engine.send("Add Maya and Leo R. to Room 12");
  assert.deepEqual(asked.confirm, ["Add 2 students to Room 12: Maya, Leo R.. Not added (first names or nicknames only): Sam Lopez, kid@example.com, Ava2"]);
  assert.deepEqual(posts, [{ url: "/app/academy/classes/7/students", fields: { csrf_token: "page-token", names: "Maya\nLeo R." },
    method: "POST", credentials: "same-origin" }]);
  const result = JSON.parse(toolResult(sent, "add_students"));
  assert.deepEqual(result.omniarmor_said, ["Added 2 students to Room 12."]);
  assert.equal(result.done, true);
  assert.deepEqual(Object.keys(result).sort(), ["done", "not_added", "omniarmor_said"]);
  assert.deepEqual(pack._test.cleanNames(["Zoë", "Mary-Kate", "O'Neil", "José M", "Ana Maria Lopez", "x".repeat(31)]),
    { good: ["Zoë", "Mary-Kate", "O'Neil", "José M"], bad: ["Ana Maria Lopez", "x".repeat(30)] });
});

// ---------------------------------------------------------------- students: where the names go

test("before the Allow card for adding students, a line says the names go to the teacher's own AI provider", async () => {
  const pack = loadPack("teacher");
  const made = [];
  const node = (tag) => {
    const n = { tag, kids: [], attrs: {}, listeners: {}, textContent: "", className: "",
      append(...xs) { for (const x of xs) { this.kids.push(x); this.textContent += typeof x === "string" ? x : x.textContent; } },
      setAttribute(k, v) { this.attrs[k] = v; }, hasAttribute(k) { return k in this.attrs; },
      addEventListener(k, fn) { this.listeners[k] = fn; } };
    made.push(n);
    return n;
  };
  let cancelled = false;
  const cancel = { textContent: "Cancel", click() { cancelled = true; } };
  const card = { textContent: "Pilot wants to: add 1 student to Room 12: Maya", previousElementSibling: null,
    isConnected: true, parentNode: {}, querySelectorAll: () => [{ textContent: "Allow" }, cancel],
    before(n) { this.previousElementSibling = n; } };
  globalThis.document = { querySelectorAll: () => [card], createElement: node };
  globalThis.MutationObserver = class { observe() {} disconnect() {} };
  try {
    pack._test.namesNote({ id: 7, name: "Room 12" });
    await new Promise((r) => setTimeout(r, 20));
    const note = card.previousElementSibling;
    assert.ok(note && note.hasAttribute("data-names-note"));
    assert.match(note.textContent, /sent to your own AI provider/);
    const link = note.kids.find((k) => typeof k !== "string");
    assert.equal(link.textContent, "Type them myself instead");
    assert.equal(link.href, "/app/academy/classes/7#add-students");
    link.listeners.click();
    assert.ok(cancelled, "typing them myself cancels the card");
  } finally {
    delete globalThis.document;
    delete globalThis.MutationObserver;
  }
});

// ---------------------------------------------------------------- 1.14.0: OmniArmor's own welcome (core 1.2.0)

const fs = require("node:fs");
const vm = require("node:vm");

// OmniArmor's config, run for one person on one page: what it gives Pilot.mount.
// chat: the messages already in this tab's chat (the welcome shows before any).
function mountFor(who, pathname, { facts = {}, chat = [] } = {}) {
  let given = null;
  const store = { prefix: "omniarmor-pilot", loadChat: () => chat, clearChat() {}, setUi() {}, all: () => ({}), forget() {} };
  const dataset = { who, facts: JSON.stringify(facts), account: "a1" };
  const sessionStorage = { getItem: () => null, setItem() {} };
  vm.runInNewContext(fs.readFileSync(site("pilot-omniarmor.js"), "utf8"), {
    window: { Pilot: { mount: (c) => { given = c; return true; }, store }, location: { pathname }, sessionStorage },
    document: { getElementById: () => ({ dataset }), title: "OmniArmor", querySelector: () => null },
  });
  // Values from the config's own realm, made plain so deepEqual compares them fairly.
  const plain = (v) => JSON.parse(JSON.stringify(v));
  return { ...given, plain: plain(given), chipLabels: (screen = {}) => plain(given.chips(screen)).map((x) => x.label) };
}
// The core's own cleaning of the pills, as the window does it.
// Core 1.4.0: a link is read against this page's address (base).
function cleaned(pills, base = "https://omniarmor.example/app") {
  const sandbox = { window: {}, document: {}, URL };
  vm.runInNewContext(fs.readFileSync(core("pilot-panel.js"), "utf8"), sandbox);
  return JSON.parse(JSON.stringify(sandbox.window.PilotPanel.welcomePills(pills, base)));
}
const labels = (c) => cleaned(c.welcomePills).map((p) => p.label);

test("1.14.0 welcome: a business owner gets their checklist's five pills and tagline", () => {
  const c = mountFor("business", "/app");
  assert.equal(c.tagline, "Your checklist helper");
  assert.deepEqual(labels(c), ["What's due or overdue?", "Explain this check", "Summarise my report", "What does this colour mean?", "Add my AI key"]);
  const pills = cleaned(c.welcomePills);
  // Every pill survives the core's cleaning as given: a known icon, a prompt, a built-in or (1.17.0) an answer.
  assert.deepEqual(pills.map((p) => p.icon), c.plain.welcomePills.map((p) => p.icon));
  // 1.17.0 (core 1.4.0): what's due, explain this check and the colours answer at once with no key;
  // 1.18.0: summing up the report too. Only the key pill is left.
  assert.deepEqual([...c.welcomePills].map((p) => typeof p.answer), ["function", "function", "function", "function", "undefined"]);
  assert.deepEqual(pills.map((p) => [p.builtin, p.send]), [[false, false], [false, false], [false, false], [false, false], [true, false]]);
  assert.equal(pills[4].action, "settings");
});

test("1.14.0 welcome: a teacher gets their class's five pills and tagline, on every teacher page", () => {
  for (const where of ["/app/academy/classes", "/app/settings", "/app", "/app/notifications"]) {
    const c = mountFor("teacher", where);
    assert.equal(c.tagline, "Your classroom helper", where);
    assert.deepEqual(labels(c), ["Add students", "How do join codes work?", "Plan a week of lessons", "Print certificates", "Add my AI key"], where);
  }
  // 1.18.0: adding students and planning a week answer with no key too (the box, the five days).
  const given = [...mountFor("teacher", "/app/academy/classes").welcomePills];
  assert.deepEqual(given.map((p) => typeof p.answer), ["function", "function", "function", "undefined", "undefined"]);
  assert.equal(typeof given[3].link, "string");
});

test("1.14.0 welcome: a visitor gets the pills for the side of the site they are on (1.15.0: under \"Your OmniArmor helper\")", () => {
  for (const where of ["/", "/industries", "/for/salons-and-barbershops", "/demo"]) {
    const c = mountFor("visitor", where);
    assert.equal(c.tagline, "Your OmniArmor helper", where);
    assert.deepEqual(labels(c), ["What does OmniArmor do?", "Which checklist fits me?", "See the prices", "Explain this page", "Add my AI key"], where);
  }
  for (const where of ["/classrooms", "/classrooms/guide"]) {
    const c = mountFor("visitor", where);
    assert.equal(c.tagline, "Your OmniArmor helper", where);
    assert.deepEqual(labels(c), ["Is it safe for students?", "How does the free trial work?", "Plan a week of lessons", "Explain this page", "Add my AI key"], where);
  }
});

test("1.14.0 welcome: short taglines and labels, no picture or video keys, kept on screen, the column's side room", () => {
  for (const [who, where] of [["business", "/app"], ["teacher", "/app/academy/classes"], ["visitor", "/"], ["visitor", "/classrooms"]]) {
    const c = mountFor(who, where);
    // One line at 320px under "Pilot" (about 158px of room).
    assert.ok(c.tagline.length <= 21, c.tagline);
    assert.ok(c.welcomePills.every((p) => p.label.length <= 40));
    assert.deepEqual(c.plain.hideKeySections, ["image", "video"]);
    assert.equal(c.keepInViewport, true);
    assert.deepEqual(c.plain.gutter, ["main > .wrap"]);
    // Armo's room and the things never covered are kept.
    assert.deepEqual(c.plain.yieldTo, [".companion"]);
    assert.ok(c.avoid.includes(".companion-badge") && c.avoid.includes(".topbar .nav"));
  }
});

test("1.14.0 welcome: a suggestion that repeats a pill is left off the welcome, and is back once a chat has started", () => {
  // A business's Home: "What's overdue?", "Explain a check" and "What do the colours mean?" are all pills.
  assert.deepEqual(mountFor("business", "/app").chipLabels(), []);
  assert.deepEqual(mountFor("business", "/app/report").chipLabels(), ["How do I export it?"]);
  const chatting = [{ role: "user", content: "hi" }];
  assert.deepEqual(mountFor("business", "/app", { chat: chatting }).chipLabels(),
    ["What's overdue?", "Explain a check", "What do the colours mean?"]);
  // A teacher's classes page: all three are pills (or "What's overdue?" with the school checklist).
  assert.deepEqual(mountFor("teacher", "/app/academy/classes").chipLabels(), []);
  assert.deepEqual(mountFor("teacher", "/app/academy/classes", { facts: { school_checklist: true } }).chipLabels(),
    ["What's overdue?"]);
  assert.deepEqual(mountFor("teacher", "/app/academy/classes", { chat: chatting }).chipLabels(),
    ["Add students", "How do join codes work?", "Plan a week"]);
  assert.deepEqual(mountFor("visitor", "/classrooms").chipLabels(), ["Classroom or Whole school?"]);
});

test("1.14.0 welcome: never on a student's page or a kid's device, whatever the welcome says", () => {
  assert.equal(mountFor("visitor", "/kids").kidView(), true);
  assert.equal(mountFor("teacher", "/app/academy/12").kidView(), true);
  assert.equal(mountFor("teacher", "/app/academy/12/world/x/stage/1").kidView(), true);
  assert.equal(mountFor("", "/").kidView(), true);
  assert.equal(mountFor("kid", "/").kidView(), true);
  assert.equal(mountFor("teacher", "/app/academy/classes").kidView(), false);
  assert.equal(mountFor("business", "/app").kidView(), false);
});

test("1.15.0: Print certificates shows sheets of paper, not a chart; the welcome's grown-ups note is one line", () => {
  const c = mountFor("teacher", "/app/academy/classes");
  const pills = cleaned(c.welcomePills);
  const certs = pills.find((p) => p.label === "Print certificates");
  assert.equal(certs.icon, "copy");
  assert.notEqual(certs.icon, "bars");
  // Only Summarise my report is a chart.
  for (const who of ["business", "teacher", "visitor"]) {
    for (const p of cleaned(mountFor(who, "/").welcomePills)) {
      if (p.icon === "bars") assert.match(p.label, /report|page/i, `${who}: ${p.label}`);
    }
  }
  assert.equal(c.keyNoteShort, "AI keys are for grown-ups (18+).");
  assert.ok(!/\bAPI key\b/.test(c.keyNote + c.keyNoteShort));
});

// ---------------------------------------------------------------- 1.17.0: Pilot core 1.4.0, useful before an AI key

// A very small page, enough for the answers: elements with classes,
// attributes and words, and selectors made of tag.class[attr][attr=v]
// [attr^=v]:not(...) parts joined by spaces.
function h(tag, attrs = {}, ...kids) {
  const node = { tag: tag.toUpperCase(), attrs: { ...attrs }, kids: [], parent: null, rect: attrs.rect || null };
  delete node.attrs.rect;
  for (const k of kids.flat()) {
    const child = typeof k === "string" ? { text: k, parent: node } : k;
    child.parent = node;
    node.kids.push(child);
  }
  return dress(node);
}
function dress(node) {
  const classes = () => String(node.attrs.class || "").split(/\s+/).filter(Boolean);
  Object.defineProperties(node, {
    id: { get: () => node.attrs.id || "" },
    textContent: { get: () => node.kids.map((k) => (k.tag ? k.textContent : k.text)).join("") },
    dataset: { get: () => Object.fromEntries(Object.entries(node.attrs).filter(([k]) => k.startsWith("data-"))
      .map(([k, v]) => [k.slice(5).replace(/-(\w)/g, (_, c) => c.toUpperCase()), String(v)])) },
    classList: { get: () => ({ contains: (c) => classes().includes(c) }) },
  });
  node.getAttribute = (n) => (n in node.attrs ? String(node.attrs[n]) : null);
  node.getBoundingClientRect = () => node.rect || { top: 2000, bottom: 2100, left: 0, right: 300 };
  node.remove = () => { if (node.parent) node.parent.kids = node.parent.kids.filter((k) => k !== node); node.parent = null; };
  node.cloneNode = () => {
    const copy = h(node.tag.toLowerCase(), { ...node.attrs }, ...node.kids.map((k) => (k.tag ? k.cloneNode(true) : k.text)));
    copy.rect = node.rect;
    return copy;
  };
  node.matches = (part) => matchPart(node, part, classes());
  node.querySelectorAll = (sel) => select(node, sel);
  node.querySelector = (sel) => select(node, sel)[0] || null;
  return node;
}
function parts(compound) {
  const out = { tag: "", cls: [], attr: [], not: [] };
  const re = /^([a-z0-9]+)|\.([\w-]+)|\[([\w-]+)(?:(\^?=)'?([^'\]]*)'?)?\]|:not\(([^)]*\)?)\)|#([\w-]+)/gi;
  let m;
  while ((m = re.exec(compound))) {
    if (m[7]) out.attr.push(["id", "=", m[7]]);
    else if (m[1]) out.tag = m[1].toUpperCase();
    else if (m[2]) out.cls.push(m[2]);
    else if (m[3]) out.attr.push([m[3], m[4], m[5]]);
    else if (m[6]) out.not.push(parts(m[6]));
  }
  return out;
}
function matchPart(node, p, classes) {
  if (p.tag && node.tag !== p.tag) return false;
  if (!p.cls.every((c) => classes.includes(c))) return false;
  for (const [name, op, val] of p.attr) {
    if (!(name in node.attrs)) return false;
    const v = String(node.attrs[name]);
    if (op === "=" && v !== val) return false;
    if (op === "^=" && !v.startsWith(val)) return false;
  }
  return !p.not.some((n) => node.matches(n));
}
function select(root, sel) {
  // "a, b": every element either finds, in page order (1.18.0).
  const list = sel.split(/,(?![^(]*\))/);
  if (list.length > 1) {
    const hits = new Set(list.flatMap((one) => select(root, one)));
    const order = [];
    const walk = (node) => { for (const k of node.kids) if (k.tag) { if (hits.has(k)) order.push(k); walk(k); } };
    walk(root);
    return order;
  }
  const steps = sel.trim().split(/\s+(?![^(]*\))/).map(parts);
  const found = [];
  const walk = (node) => {
    for (const k of node.kids) {
      if (!k.tag) continue;
      let at = k;
      let ok = at.matches(steps[steps.length - 1]);
      for (let i = steps.length - 2; ok && i >= 0; i -= 1) {
        at = at.parent;
        while (at && at !== root.parent && !(at.tag && at.matches(steps[i]))) at = at.parent;
        ok = Boolean(at) && at !== root.parent;
      }
      if (ok) found.push(k);
      walk(k);
    }
  };
  walk(root);
  return found;
}

// OmniArmor's config on one page: what it gives Pilot.mount, with that page.
function mountOn(who, pathname, page, { facts = {}, classes = [], checklists = [], hash = "", due = [] } = {}) {
  let given = null;
  const store = { prefix: "omniarmor-pilot", loadChat: () => [], clearChat() {}, setUi() {}, all: () => ({}), forget() {} };
  const dataset = { who, facts: JSON.stringify({ ...FACTS, join_code_days: 7, join_path: "/kids", ...facts }), account: "a1",
    classes: JSON.stringify(classes), checklists: JSON.stringify(checklists), due: JSON.stringify(due) };
  const body = page || h("main");
  const sent = [];
  const closed = [];
  vm.runInNewContext(fs.readFileSync(site("pilot-omniarmor.js"), "utf8"), {
    setTimeout: (fn) => fn(),
    window: { Pilot: { mount: (c) => { given = c; return true; }, store, close: () => closed.push(true) }, location: { pathname, hash }, innerHeight: 800,
      sessionStorage: { getItem: () => null, setItem() {} }, fetch: (...a) => { sent.push(a); throw new Error("no network"); } },
    document: { getElementById: () => ({ dataset }), title: "OmniArmor", querySelector: (s) => body.querySelector(s),
      querySelectorAll: (s) => body.querySelectorAll(s) },
    fetch: (...a) => { sent.push(a); throw new Error("no network"); },
  });
  const ctx = { facts: given.facts, ready: false, screen: {} };
  const pill = (label) => [...given.welcomePills].find((p) => p.label === label);
  const answer = (label) => {
    const p = pill(label) || [...given.chips()].find((c) => c.label === label);
    return typeof p.answer === "function" ? p.answer(ctx) : p.answer;
  };
  return { ...given, pill, answer, sent, closed };
}

const Render = require(core("pilot-render.js"));
// The links an answer shows, as the window renders an app's own answer.
function linksIn(text) {
  const out = [];
  const walk = (list) => { for (const p of list || []) { if (Array.isArray(p)) { walk(p); continue; } if (p.t === "a") out.push(p.href); walk(p.c); walk(p.items); } };
  walk(Render.parse(text, { local: true }));
  return out;
}

// A business's Home (templates/app/overview.html), in short.
function overviewPage() {
  return h("main", {},
    h("div", { class: "totals" }, h("span", { class: "BLOCKED" }, h("b", {}, "1"), "blocked"),
      h("span", { class: "WARNING" }, h("b", {}, "2"), "warnings"), h("span", {}, h("b", {}, "5"), "cleared"),
      h("span", {}, h("b", {}, "3"), "without a reading")),
    h("section", { "data-needs-attention": "" }, h("ul", { class: "list" },
      h("li", {}, h("a", { class: "row", "data-level": "BLOCKED", href: "/app/industry/2#rule-hood" },
        h("span", {}, h("span", { class: "title" }, "Hood cleaning"), h("span", { class: "meta" }, " · RestoArmor")),
        h("span", { class: "tag BLOCKED" }, "OVERDUE"))),
      h("li", {}, h("a", { class: "row", "data-level": "WARNING", href: "/app/industry/2#rule-fridge" },
        h("span", {}, h("span", { class: "title" }, "Walk-in fridge *temperature*")), h("span", { class: "tag WARNING" }, "Warning"))))),
    h("section", { "data-coming-due": "" }, h("ul", { class: "list" },
      h("li", {}, h("a", { class: "row", href: "/app/industry/2#rule-permit" },
        h("span", {}, h("span", { class: "title" }, "Health permit")), h("span", { class: "meta mono" }, "in 12 days · Dec 4"))))));
}

// One industry page (templates/app/industry.html), in short.
function industryPage() {
  const rule = (key, level, days, title, extra = []) => h("li", { class: "rule", id: `rule-${key}`, "data-level": level,
    ...(days === null ? {} : { "data-days": String(days) }), rect: key === "fridge" ? { top: 200, bottom: 500, left: 0, right: 300 } : undefined },
  h("div", { class: "rule-top" }, h("h2", {}, title), h("span", { class: `tag ${level}` }, level === "NONE" ? "No reading" : level)), ...extra);
  return h("main", {}, h("h1", {}, "RestoArmor"), h("ul", { class: "list" },
    rule("hood", "BLOCKED", -3, "Hood cleaning", [h("p", { class: "msg BLOCKED" }, "Overdue by 3 days."), h("p", { class: "due mono" }, "3 days overdue · Nov 19")]),
    rule("fridge", "WARNING", null, "Walk-in fridge", [
      h("p", { class: "why-line" }, h("span", { class: "top-n" }, "Top 3 · #1"), "Why this matters: food kept cold stays safe."),
      h("p", { class: "msg WARNING" }, "Fridge 2: 6°C, close to the limit", h("span", { "data-pilot-private": "" }, " (by Jordan Lee)")),
      h("details", {}, h("summary", {}, "Rule and source"), h("div", { class: "why" }, h("p", {}, "Food poisoning fines up to $1,000."),
        h("p", { class: "mono" }, "FDA Food Code 3-501.16"), h("p", { class: "faint" }, "Last updated Nov 2", h("span", { "data-pilot-private": "" }, " by Jordan Lee")))),
      h("p", { class: "q" }, "Fridge temperature (°C)"), h("span", { class: "limits" }, "Limit 5 °C · warns from 4 °C")]),
    rule("permit", "CLEARED", 12, "Health permit", [h("p", { class: "sr" }, "Valid."), h("p", { class: "due mono" }, "in 12 days · Dec 4")]),
    rule("sink", "NONE", null, "Hand sink stocked")));
}

// A teacher's class page (templates/academy/class.html), with its students' names.
function classPage() {
  return h("main", {}, h("h1", { class: "ac-title" }, "Room 12"),
    h("ul", { "data-class-totals": "" }, h("li", {}, h("span", { class: "ac-stat-num", "data-total": "students" }, "3"))),
    h("form", { class: "ac-missing", "data-codes-missing": "2" }, h("button", {}, "Make codes for them")),
    h("table", { "data-class-progress": "", "data-pilot-private": "" },
      h("tr", { "data-student": "Ava" }, h("td", {}, "Ava")), h("tr", { "data-student": "Liam" }, h("td", {}, "Liam")),
      h("tr", { "data-student": "Noah" }, h("td", {}, "Noah"))));
}

test("1.17.0: what's due on Home answers at once from the page, with links to each check, and nothing sent", () => {
  const c = mountOn("business", "/app", overviewPage());
  const text = c.answer("What's due or overdue?");
  assert.match(text, /\*\*Needs attention: 1 blocked, 2 warnings\.\*\*/);
  assert.match(text, /\[Hood cleaning\]\(\/app\/industry\/2#rule-hood\): OVERDUE/);
  // Words from the page can't add markdown of their own.
  assert.match(text, /\[Walk-in fridge temperature\]\(\/app\/industry\/2#rule-fridge\): Warning/);
  assert.match(text, /\*\*Coming due in the next 60 days: 1\.\*\*\n- \[Health permit\]\(\/app\/industry\/2#rule-permit\): in 12 days · Dec 4/);
  assert.deepEqual(linksIn(text), ["/app/industry/2#rule-hood", "/app/industry/2#rule-fridge", "/app/industry/2#rule-permit"]);
  assert.deepEqual(c.sent, []);
  // The colours, with this page's own totals.
  const colours = c.answer("What does this colour mean?");
  assert.match(colours, /\*\*Blocked\*\* \(red\): past the limit/);
  assert.match(colours, /On this page: 1 blocked, 2 warnings, 5 cleared, 3 with no reading\./);
  assert.ok(linksIn(colours).includes("/help#lights"));
  // Home has no rule to explain: it points at the checks that need attention.
  const explain = c.answer("Explain this check");
  assert.match(explain, /Open one to see it explained:\n- \[Hood cleaning\]\(\/app\/industry\/2#rule-hood\)/);
  assert.match(explain, /not legal advice/);
});

test("1.17.0: explain this check reads the check asked for (or in view), its rule and source, and never a person's name", () => {
  const inView = mountOn("business", "/app/industry/2", industryPage()).answer("Explain this check");
  assert.match(inView, /^\*\*Walk-in fridge\*\*: WARNING/);
  assert.match(inView, /- \*\*What it asks:\*\* Fridge temperature \(°C\)/);
  assert.match(inView, /- \*\*Limit:\*\* Limit 5 °C · warns from 4 °C/);
  assert.match(inView, /- \*\*Why it matters:\*\* food kept cold stays safe\./);
  assert.match(inView, /- \*\*If it's missed:\*\* Food poisoning fines up to \$1,000\./);
  assert.match(inView, /- \*\*Rule and source:\*\* FDA Food Code 3-501\.16/);
  assert.match(inView, /Status: \*\*Warning\*\* \(orange\)/);
  assert.match(inView, /not legal advice/);
  assert.ok(!inView.includes("Jordan"), "a name marked private is never read");
  // The check in the address wins.
  const asked = mountOn("business", "/app/industry/2", industryPage(), { hash: "#rule-hood" }).answer("Explain this check");
  assert.match(asked, /^\*\*Hood cleaning\*\*: BLOCKED\n\nOverdue by 3 days\./);
  assert.match(asked, /- \*\*Due:\*\* 3 days overdue · Nov 19/);
  // What's due on one checklist: overdue, close to a limit, due soon, and the ones with no reading.
  const due = mountOn("business", "/app/industry/2", industryPage()).answer("What's due or overdue?");
  assert.match(due, /\*\*Overdue: 1\.\*\*\n- \[Hood cleaning\]\(\/app\/industry\/2#rule-hood\): 3 days overdue · Nov 19/);
  assert.match(due, /\*\*Blocked or close to a limit: 1\.\*\*\n- \[Walk-in fridge\]\(\/app\/industry\/2#rule-fridge\): WARNING/);
  assert.match(due, /\*\*Due in the next 30 days: 1\.\*\*\n- \[Health permit\]/);
  assert.match(due, /1 check here still has no reading\./);
  assert.ok(!due.includes("Jordan"));
  // Away from a page with checks: a link to Home, still with no key.
  assert.match(mountOn("business", "/app/settings", h("main")).answer("What's due or overdue?"), /\[Home\]\(\/app\)/);
  assert.match(mountOn("business", "/app/settings", h("main"), { checklists: [{ id: 2, name: "RestoArmor" }] }).answer("Explain this check"),
    /\[RestoArmor\]\(\/app\/industry\/2\)/);
});

test("1.17.0: a teacher's join codes answer counts, never names, and goes to that class's codes; certificates is a link", () => {
  const classes = [{ id: 12, name: "Room 12" }, { id: 14, name: "Art club" }];
  const c = mountOn("teacher", "/app/academy/classes/12", classPage(), { classes });
  const text = c.answer("How do join codes work?");
  assert.match(text, /opens \*\*\/kids\*\* on this site/);
  assert.match(text, /works once, for 7 days/);
  assert.match(text, /This class has 3 students; 2 have no code yet\./);
  assert.match(text, /\[Open the join codes for Room 12\]\(\/app\/academy\/classes\/12\/join-codes\)/);
  for (const name of ["Ava", "Liam", "Noah"]) assert.ok(!text.includes(name), name);
  assert.deepEqual(c.sent, []);
  // Print certificates goes straight to this class's certificates.
  assert.equal(c.pill("Print certificates").link, "/app/academy/classes/12/certificates");
  assert.equal(cleaned(c.welcomePills, "https://omniarmor.example/app/academy/classes/12")[3].link,
    "https://omniarmor.example/app/academy/classes/12/certificates");
  // With one class, from any teacher page; with several, a link to each; with none, add a class first.
  const onlyOne = mountOn("teacher", "/app/settings", h("main"), { classes: [classes[0]] });
  assert.equal(onlyOne.pill("Print certificates").link, "/app/academy/classes/12/certificates");
  assert.match(onlyOne.answer("How do join codes work?"), /\(\/app\/academy\/classes\/12\/join-codes\)/);
  const several = mountOn("teacher", "/app/academy/classes", h("main"), { classes });
  assert.equal(several.pill("Print certificates").link, "/app/academy/classes");
  assert.deepEqual(linksIn(several.answer("How do join codes work?")), ["/app/academy/classes/12/join-codes", "/app/academy/classes/14/join-codes"]);
  assert.match(mountOn("teacher", "/app/academy/classes", h("main")).answer("How do join codes work?"), /\[Add your class\]\(\/app\/academy\/classes#add-class\)/);
  // 1.18.0: adding students and planning lessons answer with no key too.
  assert.equal(typeof c.pill("Add students").answer, "function");
  assert.equal(typeof c.pill("Plan a week of lessons").answer, "function");
});

test("1.17.0: a visitor learns what OmniArmor does and the free trial with no key; the prices are a link", () => {
  const c = mountOn("visitor", "/", h("main"));
  const what = c.answer("What does OmniArmor do?");
  assert.match(what, /\*\*Starter checklists\*\* for 51 industries \(510 checks\)/);
  assert.match(what, /to your team 30, 7 and 1 day before a due date/);
  assert.match(what, /Free for 14 days, no card\./);
  assert.deepEqual(linksIn(what), ["/demo", "/industries"]);
  assert.equal(c.pill("See the prices").link, "/help#prices");
  assert.equal(cleaned(c.welcomePills, "https://omniarmor.example/")[2].link, "https://omniarmor.example/help#prices");
  assert.equal(c.answerMore, "Want more? Add your AI key to ask anything.");
  // The schools side: safety and the free trial, from the site's own facts.
  const school = mountOn("visitor", "/classrooms", h("main"));
  assert.match(school.answer("Is it safe for students?"), /first name or nickname only\*\*: no email, birthdate or photo/);
  const trial = school.answer("How does the free trial work?");
  assert.match(trial, /free for 30 days: one class of up to 35 students/);
  assert.match(trial, /\*\*Classroom\*\* CLASSROOM-PRICE or \*\*Whole school\*\* SCHOOL-PRICE/);
  assert.ok(linksIn(trial).includes("/classrooms#price"));
  // Page suggestions that are answers too.
  assert.match(school.answer("Classroom or Whole school?"), /\*\*Whole school\*\* \(SCHOOL-PRICE a year\): Every class\./);
  assert.match(mountOn("visitor", "/demo", h("main")).answer("Is anything saved?"), /nothing you do is saved/);
  assert.match(mountOn("visitor", "/industries", h("main")).answer("Is this legal advice?"), /^No\. OmniArmor is decision support/);
  assert.match(mountOn("business", "/app/report", h("main")).answer("How do I export it?"), /\*\*Export CSV\*\*/);
});

test("1.17.0: every answer and link survives the core's cleaning, links stay on this site, and none needs a key", () => {
  const sandbox = { window: {}, document: {}, URL };
  vm.runInNewContext(fs.readFileSync(core("pilot-panel.js"), "utf8"), sandbox);
  const P = sandbox.window.PilotPanel;
  const pages = [["business", "/app", overviewPage()], ["business", "/app/industry/2", industryPage()], ["business", "/app/report", h("main")],
    ["business", "/app/notifications", h("main")], ["teacher", "/app/academy/classes/12", classPage()], ["visitor", "/", h("main")],
    ["visitor", "/industries", h("main")], ["visitor", "/classrooms", h("main")], ["visitor", "/classrooms/guide", h("main")], ["visitor", "/demo", h("main")]];
  for (const [who, where, page] of pages) {
    const c = mountOn(who, where, page, { classes: [{ id: 12, name: "Room 12" }], checklists: [{ id: 2, name: "RestoArmor" }] });
    const base = `https://omniarmor.example${where}`;
    const pills = P.welcomePills(c.welcomePills, base);
    assert.equal(pills.length, 5, `${who} ${where}`);
    const chips = P.cleanChips([...c.chips()], base);
    for (const item of [...pills, ...chips]) {
      if (item.link) assert.ok(item.link.startsWith("https://omniarmor.example/"), item.link);
      if (item.answer === undefined) continue;
      const text = typeof item.answer === "function" ? item.answer({ facts: c.facts, ready: false, screen: {} }) : item.answer;
      assert.ok(typeof text === "string" && text.length > 20 && text.length <= 4000, `${where}: ${item.label}`);
      for (const href of linksIn(text)) assert.match(href, /^\/(?![/\\])/, `${where}: ${item.label}: ${href}`);
      for (const name of ["Ava", "Liam", "Noah", "Jordan"]) assert.ok(!text.includes(name), `${where}: ${item.label}: ${name}`);
    }
    assert.deepEqual(c.sent, [], `${who} ${where}`);
  }
});

// ---------------------------------------------------------------- 1.18.0: every welcome button answers with no key

const TRADES = [{ name: "Restaurants and cafés", path: "/industries/restoarmor" }, { name: "Salons and barbershops", path: "/for/salons-and-barbershops" },
  { name: "Evil", path: "https://evil.example/x" }];
const CLASS_PLAN = [{ title: "Meet the Class Stand", lessons: 5, talk: "What would we sell?" }, { title: "Business Words", lessons: 8, talk: "Which word was new?" },
  { title: "Rules at the Stand", lessons: 6, talk: "Why keep it cold?" }, { title: "Money at the Stand", lessons: 6, talk: "" },
  { title: "Talk Like a Pro", lessons: 7, talk: "How do we answer the phone?" }, { title: "Work as a Team", lessons: 5, talk: "Who does what?" }];

test("1.18.0: every welcome button but the key answers with no key, for everyone, on every page", () => {
  const pages = [["business", "/app"], ["business", "/app/report"], ["business", "/app/settings"], ["teacher", "/app/academy/classes/12"],
    ["teacher", "/app/settings"], ["visitor", "/"], ["visitor", "/industries"], ["visitor", "/classrooms"], ["visitor", "/classrooms/guide"]];
  for (const [who, where] of pages) {
    const c = mountOn(who, where, h("main"), { classes: [{ id: 12, name: "Room 12" }], facts: { trades: TRADES, class_plan: CLASS_PLAN } });
    for (const p of [...c.welcomePills]) {
      if (p.action === "settings") continue;
      assert.ok(typeof p.answer === "function" || typeof p.answer === "string" || typeof p.link === "string", `${who} ${where}: ${p.label}`);
      if (p.answer !== undefined) assert.ok(c.answer(p.label).length > 20, `${who} ${where}: ${p.label}`);
    }
    // The page's suggestions answer too.
    for (const chip of [...c.chips()]) assert.ok(chip.answer !== undefined || chip.link !== undefined, `${who} ${where}: ${chip.label}`);
    assert.deepEqual(c.sent, []);
  }
});

test("1.18.0: which checklist fits asks what kind of business, with a link to each trade's page, only on this site", () => {
  const text = mountOn("visitor", "/industries", h("main"), { facts: { trades: TRADES } }).answer("Which checklist fits me?");
  assert.match(text, /^\*\*What kind of business is it\?\*\*/);
  assert.deepEqual(linksIn(text), ["/industries/restoarmor", "/for/salons-and-barbershops", "/industries", "/demo"]);
  assert.ok(!text.includes("evil"));
});

test("1.18.0: which plan fits compares the plans from the app's own data, and the yearly price says 'a year' once", () => {
  const facts = { pro_summary: "the tracker", plus_summary: "the tracker and the Academy", pro_yearly: "PRO-YEAR", free_label: "2 months free" };
  const biz = mountOn("visitor", "/", h("main"), { facts }).answer("Which plan fits me?");
  assert.match(biz, /\*\*Pro\*\* \(PRO-PRICE, or PRO-YEAR \(2 months free\)\): the tracker\./);
  assert.match(biz, /\*\*Plus\*\* \(PLUS-PRICE\): the tracker and the Academy\./);
  assert.match(biz, /14 days free, no card/);
  const school = mountOn("teacher", "/app/settings", h("main"), { facts: { classroom_price: "$299 a year", school_price: "$1,490 a year" } });
  const plans = school.answer("Classroom or Whole school?");
  assert.match(plans, /\*\*Classroom\*\* \(\$299 a year\): One class\./);
  assert.ok(!/a year a year/.test(plans), plans);
  assert.match(mountOn("visitor", "/classrooms", h("main")).answer("Classroom or Whole school?"), /\*\*Whole school\*\* \(SCHOOL-PRICE a year\)/);
});

test("1.18.0: explain this page says what it's for and lists its parts, from its own headings, never a private name", () => {
  const page = h("main", {}, h("div", { class: "page-head" }, h("h1", {}, "Try OmniArmor"),
    h("p", { class: "sub" }, "Click around a workspace that's already in use.")), h("h2", {}, "For a business"), h("h2", {}, "For a class"),
  h("h2", {}, h("span", { "data-pilot-private": "" }, "Jordan Lee")));
  const text = mountOn("visitor", "/demo", page).answer("Explain this page");
  assert.match(text, /^\*\*Demos: try OmniArmor without signing up\*\*: Try OmniArmor/);
  assert.match(text, /Click around a workspace that's already in use\./);
  assert.match(text, /\*\*On this page:\*\*\n- For a business\n- For a class/);
  assert.ok(!text.includes("Jordan"));
});

test("1.18.0: a teacher's Add students goes to the class page's box and puts the cursor in it, or links to it", () => {
  const focused = [];
  const box = h("textarea", { name: "names" });
  box.focus = () => focused.push("names");
  box.scrollIntoView = () => {};
  const page = h("main", {}, h("form", { id: "add-students" }, box));
  const c = mountOn("teacher", "/app/academy/classes/12", page, { classes: [{ id: 12, name: "Room 12" }] });
  assert.match(c.answer("Add students"), /The \*\*Add students\*\* box is open on this page/);
  assert.deepEqual(focused, ["names"]);
  assert.equal(c.closed.length, 1, "Pilot steps aside so the box shows");
  const other = mountOn("teacher", "/app/settings", h("main"), { classes: [{ id: 12, name: "Room 12" }] });
  assert.deepEqual(linksIn(other.answer("Add students")), ["/app/academy/classes/12#add-students"]);
  const two = mountOn("teacher", "/app/settings", h("main"), { classes: [{ id: 12, name: "Room 12" }, { id: 14, name: "Art" }] });
  assert.deepEqual(linksIn(two.answer("Add students")), ["/app/academy/classes/12#add-students", "/app/academy/classes/14#add-students"]);
  assert.deepEqual(linksIn(mountOn("teacher", "/app/settings", h("main")).answer("Add students")), ["/app/academy/classes#add-class"]);
});

test("1.18.0: plan a week is five days from the Classroom worlds, in order, with lessons, minutes and a question", () => {
  const text = mountOn("teacher", "/app/academy/classes", h("main"), { facts: { class_plan: CLASS_PLAN } }).answer("Plan a week of lessons");
  assert.match(text, /- \*\*Monday: Meet the Class Stand\.\*\* 5 lessons, about 15 minutes\. Talk: "What would we sell\?"/);
  assert.match(text, /- \*\*Friday: Talk Like a Pro\.\*\* 7 lessons, about 21 minutes\./);
  assert.match(text, /- \*\*Thursday: Money at the Stand\.\*\* 6 lessons, about 18 minutes\.\n/);
  assert.ok(!text.includes("Work as a Team"), "five days, five worlds");
  assert.deepEqual(linksIn(text), ["/classrooms/guide"]);
});

test("1.18.0: summarise my report counts every check and says what to fix first, with links, and never a name", () => {
  const row = (title, level, due, days, href) => h("tr", { "data-check": href, ...(days === null ? {} : { "data-days": String(days) }) },
    h("td", {}, title), h("td", {}, h("span", { class: `tag ${level}` }, level)), h("td", {}, "—"), h("td", {}, due),
    h("td", {}, "Rule"), h("td", {}, "Nov 2", h("span", { "data-pilot-private": "" }, " · Jordan Lee")));
  const page = h("main", {}, h("table", { "data-report-table": "" }, h("tbody", {},
    row("Hood cleaning", "BLOCKED", "2026-11-18", -4, "/app/industry/2#rule-hood"),
    row("Walk-in fridge", "WARNING", "2026-11-25", 3, "/app/industry/2#rule-fridge"),
    row("Health permit", "CLEARED", "2027-01-01", 40, "/app/industry/2#rule-permit"),
    row("Hand sink", "NONE", "—", null, "/app/industry/2#rule-sink"))));
  const text = mountOn("business", "/app/report", page).answer("Summarise my report");
  assert.match(text, /^\*\*Your report: 4 checks\.\*\* 1 blocked, 1 warning, 1 cleared, 1 with no reading\./);
  assert.match(text, /\*\*Fix first \(blocked\):\*\*\n- \[Hood cleaning\]\(\/app\/industry\/2#rule-hood\): overdue, it was due 2026-11-18/);
  assert.match(text, /\*\*Next \(close to a limit or a date\):\*\*\n- \[Walk-in fridge\]\(\/app\/industry\/2#rule-fridge\): due 2026-11-25/);
  assert.match(text, /1 check still has no reading: start with \[Hand sink\]/);
  assert.ok(!text.includes("Jordan"));
  // Away from the report: a link to it.
  assert.ok(linksIn(mountOn("business", "/app", h("main")).answer("Summarise my report")).includes("/app/report"));
});

test("1.18.0: explain this check says a sentence once, not under both 'Why it matters' and 'If it's missed'", () => {
  const page = h("main", {}, h("ul", {}, h("li", { class: "rule", id: "rule-hood", "data-level": "BLOCKED", "data-days": "-3", rect: { top: 200, bottom: 500 } },
    h("h2", {}, "Hood cleaning"), h("span", { class: "tag BLOCKED" }, "BLOCKED"),
    h("p", { class: "why-line" }, h("span", { class: "top-n" }, "Top 3 · #1"), "Why this matters: Grease fires spread fast."),
    h("details", {}, h("summary", {}, "Rule and source"), h("div", { class: "why" }, h("p", {}, "Grease fires spread fast."),
      h("p", { class: "mono" }, "NFPA 96"))))));
  const text = mountOn("business", "/app/industry/2", page).answer("Explain this check");
  assert.equal(text.split("Grease fires spread fast").length - 1, 1, text);
  assert.match(text, /- \*\*If it's missed:\*\* Grease fires spread fast\./);
});

test("1.18.0: the window wears OmniArmor's colours through the app's own theme class, not the core's files", () => {
  const c = mountFor("visitor", "/");
  assert.equal(c.themeClass, "omni-pilot");
  const css = fs.readFileSync(site("app.css"), "utf8");
  assert.ok(css.includes(".pilot-root.omni-pilot{--pilot-blue:#F7743A"));
  assert.ok(css.includes(".pilot-root.omni-pilot .pilot-panel{"));
});

// ---------------------------------------------------------------- 1.19.0

const DUE = [
  { level: "urgent", title: "Hood cleaning: overdue by 3 days", where: "RestoArmor", url: "/app/industry/2#rule-hood" },
  { level: "soon", title: "Form I-9: due in 1 day", where: "HRArmor", url: "/app/industry/30#rule-i9" },
  { level: "info", title: "Health permit: due in 12 days", where: "RestoArmor", url: "/app/industry/2#rule-permit" },
  { level: "urgent", title: "Sneaky [link](https://evil.example)", where: "X", url: "https://evil.example/x" },
];

test("1.19.0: what's due lists the real items with links on every page, the report and History too", () => {
  for (const where of ["/app/report", "/app/audit", "/app/notifications", "/app/settings", "/app/plan"]) {
    const text = mountOn("business", where, h("main"), { due: DUE }).answer("What's due or overdue?");
    assert.match(text, /\*\*Needs attention: 2\.\*\*/, where); // the one with a link off the site is left out
    assert.match(text, /- \[Hood cleaning: overdue by 3 days\]\(\/app\/industry\/2#rule-hood\) · RestoArmor/, where);
    assert.match(text, /\*\*Coming up, or still to fill in:\*\*\n- \[Health permit: due in 12 days\]/, where);
    const links = linksIn(text);
    assert.ok(links.includes("/app/industry/30#rule-i9"), where);
    assert.ok(links.every((l) => l.startsWith("/")), `${where}: only this site's links`);
    assert.ok(!text.includes("evil.example"), where);
  }
  // An industry page adds what needs attention on the other checklists.
  const other = mountOn("business", "/app/industry/30", h("main", {}, h("ul", {},
    h("li", { class: "rule", id: "rule-i9", "data-level": "WARNING", "data-days": "1" }, h("h2", {}, "Form I-9"), h("span", { class: "tag WARNING" }, "Warning")))),
  { due: DUE }).answer("What's due or overdue?");
  assert.match(other, /\*\*On your other checklists: 1\.\*\*\n- \[Hood cleaning: overdue by 3 days\]/);
  // Nothing due: it says so, still with no key.
  assert.match(mountOn("business", "/app/report", h("main")).answer("What's due or overdue?"), /Nothing is blocked/);
});

test("1.19.0: a visitor is never sent to a signed-in page like Settings; the public explanation instead", () => {
  for (const where of ["/", "/industries", "/industries/restoarmor", "/for/salons-and-barbershops", "/classrooms", "/classrooms/guide", "/demo"]) {
    const c = mountOn("visitor", where, h("main", {}, h("h1", {}, "Page")), { facts: { trades: TRADES, class_plan: CLASS_PLAN } });
    const answers = [...c.welcomePills].filter((p) => p.answer !== undefined).map((p) => c.answer(p.label))
      .concat([...c.chips()].filter((x) => x.answer !== undefined).map((x) => c.answer(x.label)));
    for (const text of answers) {
      for (const link of linksIn(text)) assert.ok(!link.startsWith("/app"), `${where}: ${link}`);
    }
  }
  const reminders = mountOn("visitor", "/", h("main")).answer("How do reminders work?");
  assert.deepEqual(linksIn(reminders), ["/help#reminders"]);
  // Signed in, Settings is where the emails are chosen.
  assert.ok(linksIn(mountOn("business", "/app/notifications", h("main")).answer("When do reminders go out?")).includes("/app/settings"));
});
