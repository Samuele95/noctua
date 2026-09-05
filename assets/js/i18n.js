/* Language switching. English is the source language; Italian is a full translation of the
   same key set, and tools/build_i18n.py refuses to build if the two ever diverge.

   Order of authority: ?lang= in the URL, then the reader's stored choice, then English.
   The URL wins so a link can carry a language — which is what the hreflang alternates in
   the head promise — and choosing from the header stores the choice for next time.

   Dictionary values carry inline markup (<code>, <em>, <strong>), so they are assigned with
   innerHTML. They are ours, shipped in the repo and never derived from anything a visitor
   supplies; nothing on this page writes user input into the DOM. */
(function () {
  "use strict";

  var DICTS = window.NOCTUA_I18N || {};
  var LANGS = Object.keys(DICTS);
  var FALLBACK = "en";
  var KEY = "noctua-lang";
  var current = FALLBACK;

  function stored() {
    try { return localStorage.getItem(KEY); } catch (e) { return null; }
  }

  function resolve() {
    var q = new URLSearchParams(location.search).get("lang");
    if (q && DICTS[q]) return q;
    var s = stored();
    if (s && DICTS[s]) return s;
    return FALLBACK;
  }

  function t(key) {
    var d = DICTS[current] || {};
    return d[key] != null ? d[key] : (DICTS[FALLBACK] || {})[key];
  }

  function apply(lang) {
    current = DICTS[lang] ? lang : FALLBACK;
    document.documentElement.lang = current;

    document.querySelectorAll("[data-i18n]").forEach(function (el) {
      var v = t(el.getAttribute("data-i18n"));
      if (v != null) el.innerHTML = v;
    });
    document.querySelectorAll("[data-i18n-attr]").forEach(function (el) {
      el.getAttribute("data-i18n-attr").split(";").forEach(function (spec) {
        var parts = spec.split(":");
        var v = t(parts[1]);
        if (v != null) el.setAttribute(parts[0], v.replace(/<[^>]+>/g, ""));
      });
    });

    var nav = document.querySelector(".nav");
    if (nav) nav.setAttribute("aria-label", t("a11y.sections"));

    var btn = document.querySelector("[data-lang-toggle]");
    if (btn) {
      var other = LANGS.filter(function (l) { return l !== current; })[0] || FALLBACK;
      btn.textContent = other.toUpperCase();
      btn.setAttribute("aria-label", t("a11y.lang"));
      btn.setAttribute("lang", other);
    }

    document.dispatchEvent(new CustomEvent("noctua:lang", { detail: { lang: current, t: t } }));
  }

  window.noctuaI18n = { t: t, lang: function () { return current; }, apply: apply };

  function init() {
    apply(resolve());
    var btn = document.querySelector("[data-lang-toggle]");
    if (!btn) return;
    btn.addEventListener("click", function () {
      var next = LANGS.filter(function (l) { return l !== current; })[0] || FALLBACK;
      try { localStorage.setItem(KEY, next); } catch (e) { /* private mode: this visit only */ }
      apply(next);
      var url = new URL(location.href);
      url.searchParams.set("lang", next);
      history.replaceState(null, "", url);
    });
  }

  document.readyState === "loading"
    ? document.addEventListener("DOMContentLoaded", init)
    : init();
})();
