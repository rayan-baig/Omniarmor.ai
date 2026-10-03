/* Future Owner Academy: makes a level feel like a game. Everything still works
   without this script: the lesson shows in full and the quiz is checked by the
   server when it's sent. */
(function () {
  "use strict";
  document.documentElement.classList.add("js");

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
        index = i;
        cards.forEach(function (card, n) { card.classList.toggle("active", n === index); });
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
          nav.hidden = true;
          cards.forEach(function (card) { card.classList.add("active"); });
          var first = quiz.querySelector("input[type=radio]");
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
    var CHEERS = ["Correct", "Well done", "Good thinking", "Sharp answer"];
    var STREAKS = { 3: "3 in a row", 5: "5 in a row. Excellent work", 8: "8 in a row. Outstanding" };
    var TRY_AGAIN = ["Not quite. Read the tip", "Good try. Every mistake teaches something", "Keep going"];

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
        face("cheer");
        say(STREAKS[streak] || pick(CHEERS), true);
      } else {
        streak = 0;
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
    questions.forEach(function (q) {
      var answer = q.getAttribute("data-answer");
      q.addEventListener("change", function (event) {
        var input = event.target;
        if (q.classList.contains("locked")) {
          // First answer counts: put the original choice back.
          var kept = q.querySelector("input[data-first]");
          if (kept) kept.checked = true;
          return;
        }
        input.setAttribute("data-first", "");
        var gotIt = input.value === answer;
        q.classList.add("locked", gotIt ? "got-it" : "missed");
        Array.prototype.forEach.call(q.querySelectorAll("input"), function (other) {
          var label = other.closest(".ac-opt");
          if (other.value === answer) label.classList.add("right");
          else if (other === input) label.classList.add("wrong");
          other.setAttribute("aria-disabled", "true");
        });
        var explain = q.querySelector("[data-explain]");
        if (explain) explain.hidden = false;
        react(gotIt);
        updateCount();
      });
    });
    updateCount();
  });

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
