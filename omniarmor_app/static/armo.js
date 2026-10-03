/* Armo, the companion above the tab bar. While things are calm he does his
   own thing (coffee, a book, juggling, a nap) and now and then says something
   in his personality's voice. When something needs attention he jumps up and
   points at it. Every minute he checks for new issues while the page is open.
   Without this script he's a plain link to the Armo page. */
(function () {
  "use strict";
  var root = document.querySelector("[data-companion]");
  if (!root) return;

  var stage = root.querySelector("[data-stage]");
  var button = root.querySelector("[data-armo-button]");
  var bubble = root.querySelector("[data-bubble]");
  var text = root.querySelector("[data-bubble-text]");
  var fix = root.querySelector("[data-bubble-fix]");
  var close = root.querySelector("[data-bubble-close]");
  var count = root.querySelector("[data-count]");

  var lines = {
    idle: parse("data-idle"), alert: parse("data-alert"), clear: parse("data-clear"), acts: parse("data-acts"),
    fixed: parse("data-fixed"), poke: parse("data-poke")
  };
  var state = {
    needs: parseInt(root.getAttribute("data-needs"), 10) || 0,
    signature: root.getAttribute("data-signature") || "",
    title: root.getAttribute("data-top-title") || "",
    url: root.getAttribute("data-top-url") || ""
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

  function say(message, options) {
    options = options || {};
    text.textContent = message;
    if (options.url) {
      fix.href = options.url;
      fix.textContent = root.getAttribute("data-fix") || "Fix it";
      fix.hidden = false;
    } else {
      fix.hidden = true;
    }
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

  function jump() {
    root.classList.remove("jump");
    void root.offsetWidth;
    root.classList.add("jump");
  }

  function soundTheAlarm() {
    if (!state.needs || !state.title) return;
    alerting = true;
    clearTimeout(restTimer);
    pose("alert");
    jump();
    say(pick(lines.alert).replace("{title}", state.title), { url: state.url, sticky: true });
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
    var roll = Math.random();
    say(pick(roll < 0.45 ? lines.poke : roll < 0.7 ? lines.clear : lines.idle));
  });
  close.addEventListener("click", function () {
    if (alerting) store("armo-dismissed", state.signature);
    standDown();
    button.focus();
  });
  document.addEventListener("keydown", function (event) {
    if (event.key === "Escape" && !bubble.hidden) close.click();
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
        if (Math.random() < 0.65) setTimeout(function () { if (!alerting) say(pick(lines.idle)); }, 1200);
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
        state.title = data.top ? data.top.title : "";
        state.url = data.top ? data.top.url : "";
        updateBadge();
        if (state.needs && changed && store("armo-dismissed") !== state.signature) {
          soundTheAlarm();
        } else if (!state.needs && hadIssues) {
          alerting = false;
          pose("cheer");
          jump();
          say(pick(lines.fixed.length ? lines.fixed : lines.clear));
          restTimer = setTimeout(function () { pose("idle"); }, 6000);
        }
      })
      .catch(function () { /* offline: try again next minute */ });
  }

  updateBadge();
  if (state.needs && store("armo-dismissed") !== state.signature) {
    setTimeout(soundTheAlarm, 1200);
  } else if (!store("armo-greeted")) {
    store("armo-greeted", "1");
    setTimeout(function () { if (!alerting) say(pick(state.needs ? lines.idle : lines.clear.concat(lines.idle))); }, 2500);
  }
  idleTick();
  setInterval(poll, 60000);
})();
