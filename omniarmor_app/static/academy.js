/* Future Owner Academy: makes a level feel like a game. Everything still works
   without this script: the lesson shows in full and the quiz is checked by the
   server when it's sent. */
(function () {
  "use strict";
  document.documentElement.classList.add("js");

  // --- The celebration when a stage is passed (result.html, 1.16.0) ---------
  // It covers the results until "Keep going" (or Escape). The chime plays only
  // if sound was switched on, on this device; it starts off.
  var SOUND_KEY = "omniarmor-academy-sound";
  document.addEventListener("DOMContentLoaded", function () {
    var party = document.querySelector("[data-celebrate]");
    if (!party) return;
    var close = party.querySelector("[data-celebrate-close]");
    var sound = party.querySelector("[data-sound]");
    var soundOn = false;
    try { soundOn = window.localStorage.getItem(SOUND_KEY) === "on"; } catch (e) { soundOn = false; }
    var showSound = function () {
      if (!sound) return;
      sound.textContent = soundOn ? "Sound: on" : "Sound: off";
      sound.setAttribute("aria-pressed", soundOn ? "true" : "false");
    };
    var done = function () {
      party.classList.remove("show");
      party.hidden = true;
      document.removeEventListener("keydown", onKey);
      var result = document.querySelector(".ac-result");
      if (result) { result.setAttribute("tabindex", "-1"); result.focus({ preventScroll: true }); }
    };
    var onKey = function (e) { if (e.key === "Escape") done(); };
    party.hidden = false;
    party.classList.add("show");
    if (close) close.addEventListener("click", function () { chime(soundOn); done(); });
    if (sound) {
      showSound();
      sound.addEventListener("click", function () {
        soundOn = !soundOn;
        try { window.localStorage.setItem(SOUND_KEY, soundOn ? "on" : "off"); } catch (e) { /* not kept */ }
        showSound();
        chime(soundOn);
      });
    }
    document.addEventListener("keydown", onKey);
    party.focus({ preventScroll: true });
    chime(soundOn);
  });

  // --- "Grown-up? Hold to exit" on a learner's map (base.html, 1.18.0) ------
  // A grown-up presses and holds it (about a second and a half) to leave the
  // kid's screen; a quick tap only says to keep holding, so a kid tapping
  // around stays on their map. Space or Enter held down works the same.
  var HOLD_MS = 1500;
  document.addEventListener("DOMContentLoaded", function () {
    var exit = document.querySelector("[data-hold-exit]");
    if (!exit) return;
    var label = exit.querySelector("[data-hold-label]");
    var said = label ? label.textContent : "";
    var timer = null;
    var hintTimer = null;
    var start = function () {
      if (timer) return;
      exit.classList.add("holding");
      timer = setTimeout(function () {
        timer = null;
        exit.classList.remove("holding");
        exit.classList.add("held");
        window.location.assign(exit.getAttribute("href"));
      }, HOLD_MS);
    };
    var stop = function (tapped) {
      if (timer) { clearTimeout(timer); timer = null; }
      exit.classList.remove("holding");
      if (tapped && label) {
        label.textContent = exit.getAttribute("data-hold-hint") || said;
        clearTimeout(hintTimer);
        hintTimer = setTimeout(function () { label.textContent = said; }, 1800);
      }
    };
    exit.addEventListener("click", function (e) { e.preventDefault(); });
    exit.addEventListener("contextmenu", function (e) { e.preventDefault(); });
    exit.addEventListener("pointerdown", function (e) {
      if (e.button !== undefined && e.button !== 0) return;
      try { exit.setPointerCapture(e.pointerId); } catch (err) { /* fine */ }
      start();
    });
    exit.addEventListener("pointerup", function () { stop(Boolean(timer)); });
    exit.addEventListener("pointercancel", function () { stop(false); });
    exit.addEventListener("keydown", function (e) {
      if (e.key !== "Enter" && e.key !== " ") return;
      e.preventDefault();
      start();
    });
    exit.addEventListener("keyup", function (e) {
      if (e.key !== "Enter" && e.key !== " ") return;
      stop(Boolean(timer));
    });
    exit.addEventListener("blur", function () { stop(false); });
  });

  // A short rising chime (made here, no sound file), only when sound is on.
  var audio = null;
  var chimed = false;
  function chime(on) {
    if (!on || chimed) return;
    var Ctx = window.AudioContext || window.webkitAudioContext;
    if (!Ctx) return;
    try {
      audio = audio || new Ctx();
      if (audio.state === "suspended") { audio.resume(); if (audio.state === "suspended") return; }
      chimed = true;
      var t = audio.currentTime;
      [523.25, 659.25, 783.99, 1046.5].forEach(function (freq, n) {
        var osc = audio.createOscillator();
        var gain = audio.createGain();
        osc.type = "triangle";
        osc.frequency.value = freq;
        gain.gain.setValueAtTime(0.0001, t + n * 0.11);
        gain.gain.exponentialRampToValueAtTime(0.18, t + n * 0.11 + 0.02);
        gain.gain.exponentialRampToValueAtTime(0.0001, t + n * 0.11 + 0.35);
        osc.connect(gain);
        gain.connect(audio.destination);
        osc.start(t + n * 0.11);
        osc.stop(t + n * 0.11 + 0.4);
      });
    } catch (e) { /* no sound: fine */ }
  }

  document.addEventListener("DOMContentLoaded", function () {
    var story = document.querySelector("[data-story]");
    var quiz = document.querySelector("[data-quiz]");
    if (!quiz) return;

    // --- Lesson cards, one at a time ---------------------------------------
    var cards = story ? Array.prototype.slice.call(story.querySelectorAll("[data-card]")) : [];
    if (cards.length) {
      var index = 0;
      quiz.classList.add("waiting");
      var nav = document.createElement("div");
      nav.className = "ac-story-nav";
      var back = button("Back", "btn quiet");
      var next = button("Next", "btn ac-btn");
      nav.appendChild(back);
      nav.appendChild(next);
      story.appendChild(nav);

      var show = function (i) {
        var backwards = i < index;
        index = i;
        cards.forEach(function (card, n) {
          card.classList.toggle("back", backwards);
          card.classList.toggle("active", n === index);
        });
        back.hidden = index === 0;
        next.textContent = index === cards.length - 1 ? "Start the quiz!" : "Next";
      };
      back.addEventListener("click", function () { show(Math.max(0, index - 1)); });
      next.addEventListener("click", function () {
        if (index < cards.length - 1) {
          show(index + 1);
          next.focus();
        } else {
          quiz.classList.remove("waiting");
          story.classList.add("all");
          nav.hidden = true;
          cards.forEach(function (card) { card.classList.add("active"); });
          var first = quiz.querySelector(".ac-q:not(.game-on) input[type=radio], .ac-q.game-on [data-game] button, .ac-q.game-on .ac-game button");
          quiz.scrollIntoView({ behavior: reduceMotion() ? "auto" : "smooth", block: "start" });
          if (first) first.focus({ preventScroll: true });
        }
      });
      show(0);
    }

    // --- Game HUD: progress bar, streaks and Armo's reactions --------------
    var hud = quiz.querySelector("[data-hud]");
    if (hud) hud.hidden = false;
    var progress = quiz.querySelector("[data-progress]");
    var rightEl = quiz.querySelector("[data-right]");
    var streakEl = quiz.querySelector("[data-streak]");
    var toast = quiz.querySelector("[data-toast]");
    var armoSlot = quiz.querySelector("[data-armo]");
    var right = 0;
    var streak = 0;
    var toastTimer = null;
    // Armo's lines come from the personality the learner picked.
    var voice = {};
    try { voice = JSON.parse(quiz.getAttribute("data-voice") || "{}"); } catch (e) { voice = {}; }
    var CHEERS = voice.cheers && voice.cheers.length ? voice.cheers : ["Correct", "Well done", "Good thinking"];
    var STREAKS = voice.streaks || { 3: "3 in a row", 5: "5 in a row", 8: "8 in a row" };
    var TRY_AGAIN = voice.oops && voice.oops.length ? voice.oops : ["Not quite. Read the tip", "Keep going"];

    var face = function (mood) {
      var tpl = document.getElementById("armo-" + mood);
      if (!armoSlot || !tpl) return;
      armoSlot.innerHTML = "";
      armoSlot.appendChild(tpl.content.cloneNode(true));
      armoSlot.classList.remove("bounce", "shake");
      void armoSlot.offsetWidth; // restart the animation
      armoSlot.classList.add(mood === "think" ? "shake" : "bounce");
    };
    var say = function (text, good) {
      if (!toast) return;
      toast.textContent = text;
      toast.classList.remove("show", "good", "oops");
      void toast.offsetWidth;
      toast.classList.add("show", good ? "good" : "oops");
      clearTimeout(toastTimer);
      toastTimer = setTimeout(function () { toast.classList.remove("show"); }, 2200);
    };
    var pick = function (list) { return list[Math.floor(Math.random() * list.length)]; };

    // --- Instant feedback on each answer -----------------------------------
    var questions = Array.prototype.slice.call(quiz.querySelectorAll(".ac-q"));
    var counter = quiz.querySelector("[data-count]");
    var updateCount = function () {
      var done = questions.filter(function (q) { return q.classList.contains("locked"); }).length;
      if (counter) counter.textContent = done + " of " + questions.length + " answered";
      if (progress) progress.style.width = (100 * done / questions.length) + "%";
      if (rightEl) rightEl.textContent = right;
      if (streakEl) streakEl.textContent = streak;
      if (done === questions.length && done > 0) {
        var submit = quiz.querySelector(".ac-submit");
        if (submit) submit.classList.add("ready");
      }
    };
    var react = function (gotIt) {
      if (gotIt) {
        right += 1;
        streak += 1;
        if (hud) hud.classList.toggle("hot", streak >= 3);
        face("cheer");
        say(STREAKS[streak] || pick(CHEERS), true);
      } else {
        streak = 0;
        if (hud) hud.classList.remove("hot");
        face("think");
        say(pick(TRY_AGAIN), false);
      }
      // Move on to the next unanswered question after a short pause.
      var nextQ = questions.filter(function (other) { return !other.classList.contains("locked"); })[0];
      if (nextQ) {
        setTimeout(function () {
          nextQ.scrollIntoView({ behavior: reduceMotion() ? "auto" : "smooth", block: "center" });
        }, gotIt ? 700 : 1400);
      } else {
        setTimeout(function () {
          var submit = quiz.querySelector(".ac-submit");
          if (submit) submit.scrollIntoView({ behavior: reduceMotion() ? "auto" : "smooth", block: "center" });
        }, 900);
      }
    };
    // The page doesn't know the right answers. Each first answer goes to the server,
    // which keeps it (so it can't be changed) and says whether it was right.
    var reveal = function (q, input, verdict) {
      var gotIt = Boolean(verdict.right);
      q.classList.add(gotIt ? "got-it" : "missed");
      if (gotIt) burst(input.closest(".ac-opt"));
      Array.prototype.forEach.call(q.querySelectorAll("input"), function (other) {
        var label = other.closest(".ac-opt");
        if (Number(other.value) === verdict.answer) label.classList.add("right");
        else if (Number(other.value) === verdict.chosen) label.classList.add("wrong");
        if (Number(other.value) === verdict.chosen) other.checked = true;
      });
      revealGame(q, verdict);
      var explain = q.querySelector("[data-explain]");
      if (explain && verdict.explain) {
        explain.textContent = verdict.explain;
        explain.hidden = false;
      }
      react(gotIt);
      updateCount();
    };
    var ask = function (q, input) {
      var body = new FormData();
      ["csrf_token", "attempt", "deck"].forEach(function (name) {
        var field = quiz.querySelector("input[name='" + name + "']");
        if (field) body.append(name, field.value);
      });
      body.append("check", q.getAttribute("data-index"));
      body.append("choice", input.value);
      return fetch(quiz.getAttribute("action") || window.location.href, {
        method: "POST", body: body, credentials: "same-origin", headers: { "Accept": "application/json" }
      }).then(function (response) {
        if (!response.ok) throw new Error("check failed");
        return response.json();
      });
    };
    questions.forEach(function (q) {
      q.addEventListener("change", function (event) {
        var input = event.target;
        if (q.classList.contains("locked")) {
          // First answer counts: put the original choice back.
          var kept = q.querySelector("input[data-first]");
          if (kept) kept.checked = true;
          return;
        }
        input.setAttribute("data-first", "");
        q.classList.add("locked");
        Array.prototype.forEach.call(q.querySelectorAll("input"), function (other) {
          other.setAttribute("aria-disabled", "true");
        });
        updateCount();
        ask(q, input).then(function (verdict) { reveal(q, input, verdict); }, function () {
          // No answer from the server (offline, or the quiz was already checked):
          // the choice still counts when the quiz is handed in.
          q.classList.add("pending");
          updateCount();
        });
      });
    });
    Array.prototype.forEach.call(quiz.querySelectorAll("[data-game]"), setupGame);
    updateCount();
  });

  // --- Matching and sorting games (1.18.0) -----------------------------------
  // Each game is one question. Its radio buttons stay in the page (hidden):
  // when every piece has a place, "Check" picks the radio whose code says where
  // each piece went (match: which idea each word goes with; sort: which bin each
  // item goes in), and the quiz checks it like any other answer.
  function setupGame(q) {
    var kind = q.getAttribute("data-game");
    var box = q.querySelector(kind === "match" ? "[data-match]" : "[data-sort]");
    var radios = Array.prototype.slice.call(q.querySelectorAll("input[type=radio][data-code]"));
    if (!box || !radios.length) return;
    box.hidden = false;
    q.classList.add("game-on");
    radios.forEach(function (r) { r.required = false; });
    var check = box.querySelector("[data-game-check]");
    var help = box.querySelector("[data-game-help]");
    var picks = [];
    var choose = function () {
      var code = picks.join(",");
      var radio = radios.filter(function (r) { return r.getAttribute("data-code") === code; })[0];
      if (!radio) return;
      box.classList.add("done");
      if (help) help.hidden = true;
      Array.prototype.forEach.call(box.querySelectorAll("button"), function (b) { b.disabled = true; });
      radio.checked = true;
      radio.dispatchEvent(new Event("change", { bubbles: true }));
    };
    if (kind === "match") {
      var words = Array.prototype.slice.call(box.querySelectorAll("[data-left]"));
      var ideas = Array.prototype.slice.call(box.querySelectorAll("[data-right]"));
      picks = words.map(function () { return null; });
      var current = null;
      var draw = function () {
        words.forEach(function (w, i) {
          var paired = picks[i] !== null;
          w.className = "ac-chip ac-chip-word" + (paired ? " paired pair-" + i : "") + (current === i ? " picked" : "");
          w.setAttribute("aria-pressed", current === i ? "true" : "false");
          w.querySelector(".ac-pair").textContent = paired ? String(i + 1) : "";
        });
        ideas.forEach(function (idea, j) {
          var owner = picks.indexOf(j);
          idea.className = "ac-chip" + (owner >= 0 ? " paired pair-" + owner : "");
          idea.setAttribute("aria-pressed", owner >= 0 ? "true" : "false");
          idea.querySelector(".ac-pair").textContent = owner >= 0 ? String(owner + 1) : "";
        });
        var ready = picks.every(function (p) { return p !== null; });
        if (check) check.disabled = !ready;
        if (help) help.textContent = ready ? "All matched. Check them, or tap a word to change it."
          : current !== null ? "Now tap the idea that goes with \u201c" + (words[current].querySelector(".ac-chip-text") || words[current]).textContent.trim() + "\u201d."
          : "Tap a word, then the idea that goes with it.";
      };
      words.forEach(function (w, i) {
        w.addEventListener("click", function () { current = i; draw(); });
      });
      ideas.forEach(function (idea, j) {
        idea.addEventListener("click", function () {
          if (current === null) {
            var owner = picks.indexOf(j);
            if (owner >= 0) { current = owner; draw(); }
            return;
          }
          var before = picks.indexOf(j);
          if (before >= 0) picks[before] = null;
          picks[current] = j;
          var next = picks.indexOf(null);
          current = next >= 0 ? next : null;
          draw();
        });
      });
      draw();
    } else {
      var items = Array.prototype.slice.call(box.querySelectorAll("[data-item]"));
      picks = items.map(function () { return null; });
      var drawSort = function () {
        items.forEach(function (item, i) {
          item.className = "ac-sort-item" + (picks[i] !== null ? " in-bin bin-" + picks[i] : "");
          Array.prototype.forEach.call(item.querySelectorAll("[data-bin]"), function (b) {
            b.setAttribute("aria-pressed", String(picks[i] !== null && Number(b.getAttribute("data-bin")) === picks[i]));
          });
        });
        var ready = picks.every(function (p) { return p !== null; });
        if (check) check.disabled = !ready;
        if (help) help.textContent = ready ? "All sorted. Check them, or change one." : "Put each one in a bin.";
      };
      items.forEach(function (item, i) {
        Array.prototype.forEach.call(item.querySelectorAll("[data-bin]"), function (b) {
          b.addEventListener("click", function () { picks[i] = Number(b.getAttribute("data-bin")); drawSort(); });
        });
      });
      drawSort();
    }
    if (check) check.addEventListener("click", choose);
  }

  // The verdict on a game: each piece right or wrong, and where a wrong one goes.
  function revealGame(q, verdict) {
    var kind = q.getAttribute("data-game");
    if (!kind) return;
    var radios = Array.prototype.slice.call(q.querySelectorAll("input[type=radio][data-code]"));
    var right = radios.filter(function (r) { return Number(r.value) === verdict.answer; })[0];
    var chosen = radios.filter(function (r) { return Number(r.value) === verdict.chosen; })[0];
    if (!right) return;
    var truth = right.getAttribute("data-code").split(",").map(Number);
    var mine = (chosen ? chosen.getAttribute("data-code") : "").split(",").map(Number);
    if (kind === "match") {
      var ideas = Array.prototype.slice.call(q.querySelectorAll("[data-right]"));
      // The idea's own words, without its number badge (1.19.0).
      var ideaText = function (idea) {
        var own = idea.querySelector(".ac-chip-text");
        return (own || idea).textContent.trim();
      };
      Array.prototype.forEach.call(q.querySelectorAll("[data-left]"), function (w, i) {
        var ok = mine[i] === truth[i];
        w.classList.add(ok ? "right" : "wrong");
        if (!ok && ideas[truth[i]]) {
          var fix = document.createElement("span");
          fix.className = "ac-fix";
          fix.textContent = "goes with: " + ideaText(ideas[truth[i]]);
          w.appendChild(fix);
        }
      });
      // Each idea now shows the colour and number of the word it really goes with.
      ideas.forEach(function (idea, j) {
        var owner = truth.indexOf(j);
        if (owner < 0) return;
        idea.className = "ac-chip paired pair-" + owner + " answer";
        var badge = idea.querySelector(".ac-pair");
        if (badge) badge.textContent = String(owner + 1);
      });
    } else {
      var bins = Array.prototype.map.call(q.querySelectorAll(".ac-sort-item:first-child [data-bin]"), function (b) { return b.textContent.trim(); });
      Array.prototype.forEach.call(q.querySelectorAll("[data-item]"), function (item, i) {
        var ok = mine[i] === truth[i];
        item.classList.add(ok ? "right" : "wrong");
        if (!ok && bins[truth[i]]) {
          var fix = document.createElement("span");
          fix.className = "ac-fix";
          fix.textContent = "belongs in: " + bins[truth[i]];
          item.appendChild(fix);
        }
      });
    }
  }

  // A little burst of sparks from a right answer.
  function burst(label) {
    if (!label || reduceMotion()) return;
    var spray = document.createElement("span");
    spray.className = "ac-burst";
    spray.setAttribute("aria-hidden", "true");
    for (var n = 0; n < 12; n++) {
      var bit = document.createElement("i");
      bit.style.setProperty("--a", (n * 30 + Math.round(Math.random() * 14)) + "deg");
      bit.style.setProperty("--d", (34 + Math.round(Math.random() * 22)) + "px");
      spray.appendChild(bit);
    }
    label.appendChild(spray);
    setTimeout(function () { spray.remove(); }, 900);
  }

  function button(text, className) {
    var b = document.createElement("button");
    b.type = "button";
    b.className = className;
    b.textContent = text;
    return b;
  }

  function reduceMotion() {
    return window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  }
})();
