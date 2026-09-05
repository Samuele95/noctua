/* Builds the chain diagram from window.NOCTUA_CHAIN (generated from content/chain.json,
   itself transcribed from noctua/references/chain-map.md). No value here is authored:
   every string a stage card shows is a cell of that table.

   Interaction contract: hover or focus previews a stage, click pins it, Escape unpins,
   arrow keys walk the rail. Everything the hover shows is also reachable by keyboard,
   and the detail region is announced, so the diagram carries no meaning that a keyboard
   or a screen reader cannot get to. */
(function () {
  "use strict";

  var CHAIN = window.NOCTUA_CHAIN;
  if (!CHAIN) return;

  var RAILS = [
    { id: "software", labelKey: "chain.railSoftware", sources: ["codebase", "database", "prose"],
      stages: ["spec", "forge-prose"] },
    { id: "data", labelKey: "chain.railData", sources: ["dataset", "data-project"],
      stages: ["forge-data", "lens", "shape"] }
  ];

  /* Strings come from the dictionary; the stage values do not — they are the chain map's
     own English and are marked lang="en" wherever they are shown. */
  function t(key) {
    return window.noctuaI18n ? window.noctuaI18n.t(key) : key;
  }
  var JOIN = ["blueprint", "document"];
  var OPTIONAL = ["refine", "questions", "chat"];

  var byId = {};
  CHAIN.stages.forEach(function (s) { byId[s.id] = s; });
  var kindById = {};
  CHAIN.sourceKinds.forEach(function (k) { kindById[k.id] = k; });

  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text != null) n.textContent = text;
    return n;
  }

  function stageButton(id, tagKey) {
    var s = byId[id];
    var b = el("button", "stage");
    b.type = "button";
    b.dataset.stage = id;
    b.dataset.lanes = (s.lanes || []).join(" ");
    b.setAttribute("aria-pressed", "false");
    b.appendChild(el("span", "s-name", s.label));
    b.appendChild(el("span", "s-skill", s.command));
    if (tagKey) b.appendChild(el("span", "s-tag", t(tagKey)));
    return b;
  }

  function cell(id, hasNext, tagKey) {
    var c = el("div", "cell" + (hasNext ? " has-next" : ""));
    c.appendChild(stageButton(id, tagKey));
    return c;
  }

  /* ---- build -------------------------------------------------------- */
  function build(root) {
    var wrap = el("div", "chain");
    var grid = el("div", "chain-grid");

    RAILS.forEach(function (rail) {
      var sources = el("div", "rail-sources");
      sources.appendChild(el("div", "rail-label", t(rail.labelKey)));
      rail.sources.forEach(function (kid) {
        var b = el("button", "src", kid);
        b.type = "button";
        b.dataset.lane = kid;
        b.title = kindById[kid] ? kindById[kid].recognisedBy : "";
        sources.appendChild(b);
      });
      grid.appendChild(sources);

      rail.stages.forEach(function (sid, i) {
        grid.appendChild(cell(sid, i < rail.stages.length - 1));
      });
      for (var pad = rail.stages.length; pad < 3; pad++) grid.appendChild(el("div"));
    });

    var join = el("div", "join");
    join.appendChild(el("div", "join-note", t("chain.bothRails")));
    JOIN.forEach(function (sid, i) {
      join.appendChild(cell(sid, false, byId[sid].external ? "chain.external" : null));
      if (i === 0) join.appendChild(el("div", "join-note", t("chain.then")));
    });
    grid.appendChild(join);
    wrap.appendChild(grid);

    var opt = el("div", "optional");
    opt.appendChild(el("div", "rail-label", t("chain.anyLane")));
    OPTIONAL.forEach(function (sid) { opt.appendChild(stageButton(sid, null)); });
    wrap.appendChild(opt);

    var detail = el("div", "chain-detail");
    detail.id = "chain-detail";
    detail.setAttribute("role", "region");
    detail.setAttribute("aria-live", "polite");
    detail.setAttribute("aria-label", t("chain.detailRegion"));
    wrap.appendChild(detail);

    var foot = el("p", "chain-foot");
    foot.innerHTML = t("chain.foot");
    wrap.appendChild(foot);

    root.appendChild(wrap);
    return { detail: detail, stages: Array.prototype.slice.call(wrap.querySelectorAll(".stage")),
             sources: Array.prototype.slice.call(wrap.querySelectorAll(".src")) };
  }

  /* ---- detail rendering --------------------------------------------- */
  var FIELDS = [
    ["consumes", "chain.f.consumes"], ["produces", "chain.f.produces"],
    ["check", "chain.f.check"], ["gate", "chain.f.gate"],
    ["unattended", "chain.f.unattended"], ["rerun", "chain.f.rerun"]
  ];

  function idle(detail) {
    detail.textContent = "";
    var p = el("p", "detail-idle");
    p.innerHTML = t("chain.idle");
    detail.appendChild(p);
  }

  function show(detail, id) {
    var s = byId[id];
    detail.textContent = "";
    var head = el("div", "detail-head");
    head.appendChild(el("h3", null, s.label));
    var inv = el("code", "inv", s.invocation);
    inv.lang = "en";
    head.appendChild(inv);
    if (s.external) head.appendChild(el("span", "ext", t("chain.external")));
    detail.appendChild(head);

    var dl = el("dl", "detail-grid");
    FIELDS.forEach(function (f) {
      if (!s[f[0]]) return;
      var pair = el("div", "detail-pair");
      pair.appendChild(el("dt", null, t(f[1])));
      var dd = el("dd", null, s[f[0]]);
      dd.lang = "en";          /* the chain map's own wording, not ours to translate */
      pair.appendChild(dd);
      dl.appendChild(pair);
    });
    detail.appendChild(dl);
  }

  /* ---- wiring -------------------------------------------------------- */
  var built = false;

  function init() {
    var root = document.getElementById("chain-diagram");
    if (!root) return;
    root.textContent = "";
    built = true;
    var ui = build(root);
    var pinned = null;

    idle(ui.detail);

    function preview(id) { show(ui.detail, id); }
    function restore() { pinned ? show(ui.detail, pinned) : idle(ui.detail); }

    function setLane(lane) {
      ui.stages.forEach(function (b) {
        var lanes = (b.dataset.lanes || "").split(" ");
        var on = !lane || lanes.indexOf(lane) > -1 || lanes.indexOf("any") > -1;
        b.classList.toggle("is-off", !on);
      });
    }

    function pin(btn) {
      var id = btn.dataset.stage;
      if (pinned === id) { pinned = null; btn.setAttribute("aria-pressed", "false"); idle(ui.detail); return; }
      ui.stages.forEach(function (b) { b.setAttribute("aria-pressed", "false"); });
      pinned = id;
      btn.setAttribute("aria-pressed", "true");
      show(ui.detail, id);
    }

    ui.stages.forEach(function (btn) {
      btn.addEventListener("mouseenter", function () { preview(btn.dataset.stage); });
      btn.addEventListener("mouseleave", restore);
      btn.addEventListener("focus", function () { preview(btn.dataset.stage); });
      btn.addEventListener("blur", restore);
      btn.addEventListener("click", function () { pin(btn); });
      btn.addEventListener("keydown", function (e) {
        if (e.key !== "ArrowRight" && e.key !== "ArrowLeft") return;
        e.preventDefault();
        var i = ui.stages.indexOf(btn);
        var next = ui.stages[(i + (e.key === "ArrowRight" ? 1 : -1) + ui.stages.length) % ui.stages.length];
        next.focus();
      });
    });

    ui.sources.forEach(function (b) {
      b.addEventListener("mouseenter", function () { setLane(b.dataset.lane); });
      b.addEventListener("mouseleave", function () { setLane(null); });
      b.addEventListener("focus", function () { setLane(b.dataset.lane); });
      b.addEventListener("blur", function () { setLane(null); });
    });

    document.addEventListener("keydown", function (e) {
      if (e.key !== "Escape" || !pinned) return;
      ui.stages.forEach(function (b) { b.setAttribute("aria-pressed", "false"); });
      pinned = null;
      idle(ui.detail);
    });
  }

  document.readyState === "loading"
    ? document.addEventListener("DOMContentLoaded", init)
    : init();

  /* A language switch rebuilds the diagram: the labels change, and a pinned stage is
     released, which is the honest outcome of changing the page under the reader. */
  document.addEventListener("noctua:lang", function () {
    if (built) init();   /* the first build happens on DOMContentLoaded, already localised */
  });
})();
