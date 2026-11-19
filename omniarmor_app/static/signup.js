// Sign-up: pick the browser's own timezone, so most people never touch the
// box. The server checks the name like any other choice; without JavaScript
// the box keeps its default.
(function () {
  var box = document.querySelector('[data-auto-timezone]');
  if (!box) return;
  var zone;
  try { zone = Intl.DateTimeFormat().resolvedOptions().timeZone; } catch (e) { return; }
  if (!zone || !/^[A-Za-z_]+(\/[A-Za-z0-9_+-]+)*$/.test(zone)) return;
  if (box.tagName === 'INPUT') {
    // The teacher sign-up has no timezone box: a hidden field takes the device's.
    box.value = zone;
    return;
  }
  var match = Array.prototype.find.call(box.options, function (o) { return o.value === zone; });
  if (!match) {
    match = new Option(zone.replace(/_/g, ' '), zone);
    box.add(match, 0);
  }
  box.value = zone;
})();

// Sign-up: a box to find your industry among the many, by name or sector.
// Ticked ones always stay in view. Without JavaScript the box stays hidden
// and the whole list shows.
(function () {
  var wrap = document.querySelector('[data-industry-find]');
  var box = document.querySelector('[data-industry-filter]');
  var none = document.querySelector('[data-industry-none]');
  var more = document.querySelector('[data-more-industries]');
  if (!wrap || !box) return;
  var items = Array.prototype.slice.call(document.querySelectorAll('[data-industry-name]'));
  wrap.hidden = false;
  box.addEventListener('input', function () {
    var words = box.value.toLowerCase().split(/\s+/).filter(Boolean);
    if (more && words.length) more.open = true;
    var shown = 0;
    items.forEach(function (item) {
      var name = item.getAttribute('data-industry-name');
      var ticked = item.querySelector('input').checked;
      var match = ticked || words.every(function (w) { return name.indexOf(w) !== -1; });
      item.hidden = !match;
      if (match) shown += 1;
    });
    if (none) none.hidden = shown > 0;
  });
})();
