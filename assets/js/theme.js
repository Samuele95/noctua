/* Theme toggle. The nocturnal palette is the identity, so the default is dark unless the
   OS says otherwise; an explicit choice is remembered and wins over the OS from then on.

   The attribute is stamped on <html> before first paint, which is why this script is in the
   head and not deferred: a theme applied after paint is a flash of the wrong one. The
   button's label is filled in later, when the dictionary has loaded and on every language
   change, because the label is copy like any other. */
(function () {
  "use strict";
  var KEY = "noctua-theme";
  var root = document.documentElement;

  function stored() {
    try { return localStorage.getItem(KEY); } catch (e) { return null; }
  }
  function isDark() {
    var s = stored();
    return s ? s === "dark" : !window.matchMedia("(prefers-color-scheme: light)").matches;
  }
  function label() {
    var btn = document.querySelector("[data-theme-toggle]");
    if (!btn || !window.noctuaI18n) return;
    var dark = isDark();
    btn.textContent = window.noctuaI18n.t(dark ? "theme.light" : "theme.dark");
    btn.setAttribute("aria-label", window.noctuaI18n.t(dark ? "a11y.toLight" : "a11y.toDark"));
  }
  function apply(theme) {
    if (theme) root.setAttribute("data-theme", theme); else root.removeAttribute("data-theme");
    label();
  }

  apply(stored());

  document.addEventListener("noctua:lang", label);
  document.addEventListener("DOMContentLoaded", function () {
    apply(stored());
    var btn = document.querySelector("[data-theme-toggle]");
    if (!btn) return;
    btn.addEventListener("click", function () {
      var next = isDark() ? "light" : "dark";
      try { localStorage.setItem(KEY, next); } catch (e) { /* private mode: this visit only */ }
      apply(next);
    });
  });
})();
