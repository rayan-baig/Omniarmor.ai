/* Small helpers on every page with the top menu (base.html), 1.16.0. Everything works without them.
   - The phone's Menu button (a <details>) opens and closes with no script; this also closes it with Escape
     or a tap or focus anywhere outside it.
   - A Print button ([data-print], on the report) prints the page. It stays hidden without this script. */
(function () {
  "use strict";
  Array.prototype.forEach.call(document.querySelectorAll("[data-print]"), function (b) { b.hidden = false; });
  document.addEventListener("click", function (e) {
    var t = e.target && e.target.closest ? e.target.closest("[data-print]") : null;
    if (t) { e.preventDefault(); window.print(); }
  });
  // A link to a form's own place ("#add-students", "#add-class": an empty state's button, or Pilot's "Add
  // students") puts the cursor in its first box, ready to type (1.18.0).
  function focusForm() {
    var id = (window.location.hash || "").slice(1);
    if (!/^add-[a-z-]+$/.test(id)) return;
    var form = document.getElementById(id);
    if (!form || form.tagName !== "FORM") return;
    var box = form.querySelector("textarea, input:not([type=hidden]):not([type=submit]):not([type=checkbox]):not([type=radio])");
    if (box) { try { box.focus({ preventScroll: true }); } catch (e) { box.focus(); } }
  }
  focusForm();
  window.addEventListener("hashchange", focusForm);
  var menu = document.querySelector("[data-nav-menu]");
  if (!menu) return;
  var summary = menu.querySelector("summary");
  function close(focus) {
    if (!menu.open) return;
    menu.open = false;
    if (focus && summary) summary.focus();
  }
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape" && menu.open) { e.preventDefault(); close(true); }
  });
  document.addEventListener("pointerdown", function (e) {
    if (menu.open && !menu.contains(e.target)) close(false);
  });
  document.addEventListener("focusin", function (e) {
    if (menu.open && !menu.contains(e.target)) close(false);
  });
})();
