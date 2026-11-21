/* Armo, the companion above the tab bar. While things are calm he does his
   own thing (coffee, a book, juggling, a nap). When something needs
   attention his badge shows how many, and he jumps. Every minute he checks
   for new issues while the page is open. Without this script he's a plain
   link to the Armo page.

   He keeps out of the way: his bubble opens when someone taps him. By
   itself it opens at most once a day on this device, and only where it fits
   beside the page's content column (a wide screen), never over it, so on a
   phone or a laptop he shows just his badge until tapped. On a phone he and
   Pilot share one corner and only one of them shows (app.css): Armo while
   his badge has a count, Pilot the rest of the time. */
(function () {
  "use strict";
  var root = document.querySelector("[data-companion]");
  if (!root) return;

  var stage = root.querySelector("[data-stage]");
  var button = root.querySelector("[data-armo-button]");
  var bubble = root.querySelector("[data-bubble]");
  var text = root.querySelector("[data-bubble-text]");
  var fix = root.querySelector("[data-bubble-fix]");
  var detail = root.querySelector("[data-bubble-detail]");
  var next = root.querySelector("[data-bubble-next]");
  var close = root.querySelector("[data-bubble-close]");
  var count = root.querySelector("[data-count]");

  var lines = {
    idle: parse("data-idle"), alert: parse("data-alert"), clear: parse("data-clear"), acts: parse("data-acts"),
    fixed: parse("data-fixed"), poke: parse("data-poke")
  };
  var pageHelp = root.getAttribute("data-page-help") || "";
  var helpedHere = false;
  var state = {
    needs: parseInt(root.getAttribute("data-needs"), 10) || 0,
    signature: root.getAttribute("data-signature") || "",
    issues: parse("data-issues"),   // every pressing issue: title, url, action, where
    tips: parse("data-tips"),       // useful suggestions from the company's real data
    index: 0                        // which issue Armo is showing
  };
  var alerting = false;
  var hideTimer = null;
  var restTimer = null;
  var lastLine = "";

  function parse(attr) {
    try { return JSON.parse(root.getAttribute(attr) || "[]"); } catch (e) { return []; }
  }
  function store(key, value) {
    try {
      if (value === undefined) return window.sessionStorage.getItem(key);
      window.sessionStorage.setItem(key, value);
    } catch (e) { /* storage may be blocked; Armo still works */ }
    return null;
  }
  // At most once a day, and only beside the content column (mayOpenByItself).
  var BUBBLE_ROOM = 340;   // the bubble's widest (300px) plus its margins
  function localDay() {
    var d = new Date();
    return d.getFullYear() + "-" + (d.getMonth() + 1) + "-" + d.getDate();
  }
  function remember(key, value) {
    try {
      if (value === undefined) return window.localStorage.getItem(key);
      window.localStorage.setItem(key, value);
    } catch (e) { /* storage may be blocked: then he never opens by himself */ return value === undefined ? localDay() : null; }
    return null;
  }
  function roomBeside() {
    var column = document.querySelector("main .wrap");
    if (!column) return 0;
    var box = column.getBoundingClientRect();
    var pad = parseFloat(window.getComputedStyle(column).paddingLeft) || 0;
    return box.left + pad - root.getBoundingClientRect().left;
  }
  function mayOpenByItself() {
    return remember("armo-bubble-day") !== localDay() && roomBeside() >= BUBBLE_ROOM;
  }
  function openByItself(show) {
    if (!mayOpenByItself()) return false;
    remember("armo-bubble-day", localDay());
    show();
    return true;
  }

  function pick(list) {
    if (!list.length) return "";
    var choice = list[Math.floor(Math.random() * list.length)];
    if (choice === lastLine && list.length > 1) return pick(list);
    lastLine = choice;
    return choice;
  }

  function pose(name) {
    var tpl = root.querySelector('template[data-pose="' + name + '"]') ||
              root.querySelector('template[data-pose="idle"]');
    stage.innerHTML = "";
    stage.appendChild(tpl.content.cloneNode(true));
    root.setAttribute("data-pose-now", name);
  }

  // options: url and label for the action link, detail for a second line,
  // next to show a "Next" button, sticky to keep the bubble open.
  function say(message, options) {
    options = options || {};
    text.textContent = message;
    detail.textContent = options.detail || "";
    detail.hidden = !options.detail;
    if (options.url) {
      fix.href = options.url;
      fix.textContent = options.label || root.getAttribute("data-fix") || "Fix it";
      fix.hidden = false;
    } else {
      fix.hidden = true;
    }
    next.textContent = options.next || "";
    next.hidden = !options.next;
    bubble.hidden = false;
    bubble.classList.remove("pop");
    void bubble.offsetWidth; // restart the pop animation
    bubble.classList.add("pop");
    clearTimeout(hideTimer);
    if (!options.sticky) hideTimer = setTimeout(hide, 7000);
  }

  function hide() {
    bubble.hidden = true;
    clearTimeout(hideTimer);
  }

  // While Armo's bubble (an alert, a "Fix it", a tip) is showing, Pilot's
  // robot steps aside by itself: OmniArmor's Pilot config lists Armo in its
  // yieldTo (pilot-omniarmor.js, Pilot core 1.1.1), so nothing is needed here.

  function jump() {
    root.classList.remove("jump");
    void root.offsetWidth;
    root.classList.add("jump");
  }

  // Show one issue: what's wrong, what to do, a link to fix it, and a way
  // to step through the rest.
  function showIssue(i) {
    var total = state.issues.length;
    if (!total) return;
    state.index = (i + total) % total;
    var issue = state.issues[state.index];
    say(pick(lines.alert).replace("{title}", issue.title), {
      detail: issue.action ? "What to do: " + issue.action : "",
      url: issue.url,
      next: total > 1 ? "Next (" + (state.index + 1) + " of " + total + ")" : "",
      sticky: true
    });
  }

  function soundTheAlarm() {
    if (!state.needs || !state.issues.length) return;
    alerting = true;
    clearTimeout(restTimer);
    pose("alert");
    jump();
    showIssue(0);
  }

  function giveTip() {
    var tip = state.tips.length ? state.tips[Math.floor(Math.random() * state.tips.length)] : null;
    if (!tip) return false;
    say(tip.text, { url: tip.url, label: "Show me" });
    return true;
  }

  function standDown() {
    alerting = false;
    hide();
    pose("idle");
  }

  function updateBadge() {
    count.textContent = state.needs;
    count.hidden = !state.needs;
    button.setAttribute("aria-label", state.needs
      ? "Armo: " + state.needs + (state.needs === 1 ? " thing needs" : " things need") + " attention"
      : "Armo");
  }

  // Click Armo: show the issue if there is one, otherwise chat.
  button.addEventListener("click", function (event) {
    event.preventDefault();
    if (!bubble.hidden) { hide(); return; }
    if (state.needs) { soundTheAlarm(); return; }
    jump();
    if (pageHelp && !helpedHere) {   // first click on a page: explain the page
      helpedHere = true;
      say(pick(lines.poke), { detail: pageHelp });
      return;
    }
    var roll = Math.random();
    if (roll < 0.4 && giveTip()) return;
    say(pick(roll < 0.7 ? lines.poke : roll < 0.85 ? lines.clear : lines.idle));
  });
  next.addEventListener("click", function () { showIssue(state.index + 1); });
  close.addEventListener("click", function () {
    if (alerting) store("armo-dismissed", state.signature);
    standDown();
    button.focus();
  });
  document.addEventListener("keydown", function (event) {
    if (event.key === "Escape" && !bubble.hidden) close.click();
  });
  // A tap anywhere else closes his bubble, so it never stays over the page.
  document.addEventListener("click", function (event) {
    // (A tap on Armo can swap his picture for a new pose, so its target may
    // no longer be in the page: that tap was his, not somewhere else.)
    if (!bubble.hidden && event.target.isConnected && !root.contains(event.target)) {
      if (alerting) store("armo-dismissed", state.signature);
      standDown();
    }
  });

  // Idle life: every so often, do an activity and maybe say something.
  function idleTick() {
    var wait = 22000 + Math.random() * 20000;
    setTimeout(function () {
      if (!alerting && bubble.hidden && document.visibilityState === "visible") {
        var act = pick(lines.acts.concat(["idle"]));
        if (act === "wave") {
          pose("idle");
          root.classList.add("waving");
          setTimeout(function () { root.classList.remove("waving"); }, 2400);
        } else {
          pose(act);
        }
        // He only talks when tapped: idle life is a pose, never a bubble.
        clearTimeout(restTimer);
        restTimer = setTimeout(function () { if (!alerting) pose("idle"); }, 14000);
      }
      idleTick();
    }, wait);
  }

  // Live updates: check for new issues every minute while the page is visible.
  function poll() {
    if (document.visibilityState !== "visible" || !window.fetch) return;
    fetch(root.getAttribute("data-status"), { credentials: "same-origin", headers: { Accept: "application/json" } })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (data) {
        if (!data) return;
        var hadIssues = state.needs > 0;
        var changed = data.signature !== state.signature;
        state.needs = data.needs;
        state.signature = data.signature;
        state.issues = data.issues || [];
        state.tips = data.tips || state.tips;
        updateBadge();
        if (state.needs && changed && store("armo-dismissed") !== state.signature) {
          pose("alert");
          jump();
          openByItself(soundTheAlarm);
        } else if (!state.needs && hadIssues) {
          alerting = false;
          pose("cheer");
          jump();
          if (!bubble.hidden) say(pick(lines.fixed.length ? lines.fixed : lines.clear));
          restTimer = setTimeout(function () { pose("idle"); }, 6000);
        }
      })
      .catch(function () { /* offline: try again next minute */ });
  }

  updateBadge();
  if (state.needs && store("armo-dismissed") !== state.signature) {
    setTimeout(function () {
      pose("alert");
      jump();
      openByItself(soundTheAlarm);
    }, 1200);
  }
  idleTick();
  setInterval(poll, 60000);
})();
