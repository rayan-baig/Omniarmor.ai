// Sign-up: pick the browser's own timezone, so most people never touch the
// box. The server checks the name like any other choice; without JavaScript
// the box keeps its default.
(function () {
  var box = document.querySelector('select[data-auto-timezone]');
  if (!box) return;
  var zone;
  try { zone = Intl.DateTimeFormat().resolvedOptions().timeZone; } catch (e) { return; }
  if (!zone || !/^[A-Za-z_]+(\/[A-Za-z0-9_+-]+)*$/.test(zone)) return;
  var match = Array.prototype.find.call(box.options, function (o) { return o.value === zone; });
  if (!match) {
    match = new Option(zone.replace(/_/g, ' '), zone);
    box.add(match, 0);
  }
  box.value = zone;
})();
