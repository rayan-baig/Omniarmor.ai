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
    "pilot report", "decision support, not legal advice", "Kitchen Safety Bundle", "Your reminder emails"]) {
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
