// Share and copy buttons, and cookieless counting when the site owner sets a GoatCounter endpoint
// (meta sb-goatcounter). Do Not Track and Global Privacy Control switch counting off.
(function () {
  "use strict";
  var queue = (window.__sbEvents = window.__sbEvents || []);
  var meta = document.querySelector('meta[name="sb-goatcounter"]');
  var endpoint = meta && meta.content;
  var optedOut = navigator.doNotTrack === "1" || window.doNotTrack === "1" || navigator.globalPrivacyControl === true;

  function count(path, title, isEvent) {
    if (!endpoint || optedOut) return;
    try {
      var img = new Image();
      img.src = endpoint + "?p=" + encodeURIComponent(path) + "&t=" + encodeURIComponent(title || "") + (isEvent ? "&e=true" : "") +
        "&r=" + encodeURIComponent(document.referrer || "") + "&rnd=" + Math.random();
    } catch (e) { /* counting never breaks the page */ }
  }
  window.sbTrack = function (name, detail) {
    queue.push({ name: name, detail: detail || null, at: new Date().toISOString() });
    count(name, detail ? String(detail) : name, true);
  };
  count(location.pathname, document.title, false);

  function copy(text, btn) {
    var done = function () {
      if (!btn) return;
      var old = btn.textContent;
      btn.textContent = "Copied";
      setTimeout(function () { btn.textContent = old; }, 1400);
    };
    if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(text).then(done, done);
    else done();
  }

  document.addEventListener("click", function (ev) {
    var t = ev.target;
    var a = t.closest ? t.closest("a[href*='company/']") : null;
    if (a && !a.closest(".share-row")) window.sbTrack("boxscore_open", a.getAttribute("href"));
    var el = t.closest ? t.closest("[data-share],[data-copy]") : null;
    if (!el) return;
    var row = el.closest(".share-row");
    var slug = row ? row.getAttribute("data-slug") : "";
    if (el.hasAttribute("data-copy")) {
      copy(el.getAttribute("data-copy"), el);
      window.sbTrack("share", "copy:" + slug);
      return;
    }
    var kind = el.getAttribute("data-share");
    if (kind === "native") {
      var url = row.getAttribute("data-share-url"), text = row.getAttribute("data-share-text");
      if (navigator.share) navigator.share({ title: text, text: text, url: url }).catch(function () {});
      else copy(url, el);
    }
    window.sbTrack("share", kind + ":" + slug);
  });

  document.addEventListener("focusin", function (ev) {
    if (ev.target.matches && ev.target.matches("textarea.code[readonly]")) {
      ev.target.select();
      window.sbTrack("embed_copy", ev.target.id);
    }
  });
})();
