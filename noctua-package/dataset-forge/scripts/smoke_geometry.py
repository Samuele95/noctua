#!/usr/bin/env python3
"""
smoke_geometry.py — headless-Chromium check that the dataset-forge `geometry` layer renders.

    python3 smoke_geometry.py OUT.html [--strict]

Modelled on inferred-questions/scripts/smoke_test.py. The render script only runs in a
browser, so a temporary copy of OUT.html is opened in headless Chromium with a probe script
appended that exercises the page and writes its findings into a <pre id="geometry-smoke">;
the DOM dump is then parsed. Checks:

  1. the tab button (data-tab="geometry") is inside the host's nav.tabs / nav[role=tablist];
  2. the pane section.tab-pane[data-layer="geometry"] is mounted and hidden by default;
  3. the four views exist (data-view = space | derivations | orthogonality | partition);
  4. no uncaught JS errors (window.onerror, console.error, Chromium stderr);
  5. through window.__geometry: reorient(<cycle member>) changes basis() and View D's
     candidates re-render;
  6. on a copy of the file with `explore` removed from the layer data, Views A and C show
     their empty state while B and D still render.

Exit 0 on success, 1 on a failed check (or, with --strict, when no browser is available);
without --strict a missing browser prints WARN and exits 0. Markers: OK: / WARN: / ERROR:.
"""
from __future__ import annotations

import argparse
import json
import re
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

CHROME_CANDIDATES = ("chromium", "google-chrome", "chromium-browser", "chrome")
DATA_RE = re.compile(r'(<script\s+id="layer-geometry-data"[^>]*>)([\s\S]*?)(</script>)', re.IGNORECASE)

PROBE = r"""
<script id="geometry-smoke-probe">
(function(){
  var R = { errors: [], checks: {} };
  window.addEventListener('error', function(e){ R.errors.push('onerror: ' + (e.message || e)); });
  var origErr = console.error;
  console.error = function(){ R.errors.push('console.error: ' + Array.prototype.slice.call(arguments).map(String).join(' ')); if (origErr) origErr.apply(console, arguments); };
  function q(s){ return document.querySelector(s); }
  function qa(s){ return document.querySelectorAll(s); }
  function run(){
    try {
      var nav = q('nav.tabs') || q('nav[role="tablist"]');
      R.checks.tab_button_in_nav = !!(nav && nav.querySelector('button[data-tab="geometry"]'));
      var pane = q('section.tab-pane[data-layer="geometry"]');
      R.checks.pane_mounted = !!pane;
      R.checks.pane_hidden_by_default = !!pane && !pane.classList.contains('active');
      R.checks.views = {};
      ['space','derivations','orthogonality','partition'].forEach(function(v){ R.checks.views[v] = !!(pane && pane.querySelector('[data-view="' + v + '"]')); });
      R.checks.hook = !!(window.__geometry && typeof window.__geometry.reorient === 'function' && typeof window.__geometry.basis === 'function');
      R.checks.empty_A = !!(pane && pane.querySelector('[data-view="space"] .g-empty'));
      R.checks.empty_C = !!(pane && pane.querySelector('[data-view="orthogonality"] .g-empty'));
      R.checks.nodes_B = pane ? pane.querySelectorAll('[data-view="derivations"] .g-node').length : 0;
      R.checks.cards_D = pane ? pane.querySelectorAll('[data-view="partition"] .g-cand').length : 0;
      R.checks.points_A = pane ? pane.querySelectorAll('[data-view="space"] .g-pt').length : 0;
      R.checks.cells_C = pane ? pane.querySelectorAll('[data-view="orthogonality"] .g-hcell').length : 0;
      var member = __CYCLE_MEMBER__;
      if (R.checks.hook && member) {
        var g = window.__geometry;
        var before = g.basis().slice(), candBefore = g.candidates().map(function(c){ return c.label; });
        var dBefore = pane.querySelector('[data-view="partition"]').innerHTML;
        var after = g.reorient(member);
        var candAfter = g.candidates().map(function(c){ return c.label; });
        var dAfter = pane.querySelector('[data-view="partition"]').innerHTML;
        R.checks.reorient = { member: member, before: before, after: after,
          basis_changed: before.join(',') !== after.join(','), member_now_basis: after.indexOf(member) >= 0,
          candidates_before: candBefore, candidates_after: candAfter,
          candidates_rerendered: dBefore !== dAfter, orientation: JSON.stringify(g.state.activeOrientation) };
        R.checks.version = g.version;
      }
    } catch (e) { R.errors.push('probe: ' + (e && e.stack || e)); }
    var pre = document.createElement('pre'); pre.id = 'geometry-smoke'; pre.textContent = JSON.stringify(R); document.body.appendChild(pre);
  }
  function go(){ setTimeout(run, 300); }
  if (document.readyState === 'complete') go(); else window.addEventListener('load', go);
})();
</script>
"""


def find_chrome():
    """$CHROME (path or command) first — the same convention as domain-forge's
    run_query.py and validate_model.py — then the usual candidates on PATH."""
    env = os.environ.get("CHROME")
    if env and (Path(env).is_file() or shutil.which(env)):
        return env if Path(env).is_file() else shutil.which(env)
    for c in CHROME_CANDIDATES:
        if shutil.which(c):
            return c
    return None


def dump_dom(chrome, path, budget_ms=6000):
    proc = subprocess.run(
        [chrome, "--headless=new", "--no-sandbox", "--disable-gpu", f"--virtual-time-budget={budget_ms}",
         "--enable-logging=stderr", "--v=0", "--dump-dom", f"file://{path.resolve()}"],
        capture_output=True, text=True, timeout=90)
    return proc.stdout, proc.stderr


def layer_data(html):
    m = DATA_RE.search(html)
    if not m:
        return None, None
    try:
        return json.loads(m.group(2)), m
    except json.JSONDecodeError:
        return None, m


def pick_cycle_member(doc):
    """A derived column inside a cycle: reorient() must make it a basis member."""
    if not doc:
        return None
    basis = set((doc.get("basis") or {}).get("members") or [])
    for c in doc.get("cycles") or []:
        for m in c.get("members") or []:
            if m not in basis:
                return m
    for d in doc.get("derivations") or []:
        if d.get("cycle"):
            return d.get("column")
    return None


def probe_copy(html, member, tmpdir, name, strip_explore=False):
    doc, m = layer_data(html)
    if strip_explore and doc is not None:
        doc.pop("explore", None)
        html = html[:m.start(2)] + "\n" + json.dumps(doc, ensure_ascii=False, separators=(",", ":")) + "\n" + html[m.end(2):]
    probe = PROBE.replace("__CYCLE_MEMBER__", json.dumps(member) if (member and not strip_explore) else "null")
    idx = html.rfind("</body>")
    html = html[:idx] + probe + html[idx:] if idx >= 0 else html + probe
    p = Path(tmpdir) / name
    p.write_text(html, encoding="utf-8")
    return p


def parse_results(dom):
    m = re.search(r'<pre id="geometry-smoke">([\s\S]*?)</pre>', dom)
    if not m:
        return None
    txt = m.group(1).replace("&quot;", '"').replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&")
    try:
        return json.loads(txt)
    except json.JSONDecodeError:
        return None


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("html", help="layered HTML output to check")
    ap.add_argument("--strict", action="store_true", help="exit 1 when no browser is available")
    a = ap.parse_args(argv)
    path = Path(a.html)
    if not path.is_file():
        print(f"ERROR: {path} not found")
        return 1
    html = path.read_text(encoding="utf-8")
    doc, _ = layer_data(html)
    if doc is None:
        print("ERROR: no parseable layer-geometry-data script in the file")
        return 1
    chrome = find_chrome()
    if not chrome:
        msg = f"no headless browser available (checked {CHROME_CANDIDATES})"
        if a.strict:
            print(f"ERROR: {msg} — failing under --strict")
            return 1
        print(f"WARN: {msg} — skipping the render check")
        return 0

    member = pick_cycle_member(doc)
    findings = []

    def check(ok, name, msg):
        findings.append((bool(ok), name, msg))

    with tempfile.TemporaryDirectory() as td:
        for label, strip in (("full", False), ("no-explore", True)):
            p = probe_copy(html, member, td, f"{label}.html", strip_explore=strip)
            try:
                dom, stderr = dump_dom(chrome, p)
            except subprocess.TimeoutExpired:
                check(False, f"{label}:render", "chromium timed out")
                continue
            R = parse_results(dom)
            if not R:
                check(False, f"{label}:render", "probe results missing from the DOM dump (page did not finish loading?)")
                continue
            C = R.get("checks", {})
            bad = [ln for ln in stderr.splitlines() if re.search(r"\b(Uncaught|ReferenceError|TypeError|SyntaxError)\b", ln)]
            errs = R.get("errors", []) + bad
            check(not errs, f"{label}:no-js-errors", "no JS errors" if not errs else f"{len(errs)} error(s): {errs[0][:200]}")
            check(C.get("tab_button_in_nav"), f"{label}:tab-button", "button[data-tab=geometry] inside nav.tabs")
            check(C.get("pane_mounted"), f"{label}:pane-mounted", "section.tab-pane[data-layer=geometry] mounted")
            check(C.get("pane_hidden_by_default"), f"{label}:pane-hidden", "pane has no `active` class on load")
            views = C.get("views", {})
            missing = [v for v in ("space", "derivations", "orthogonality", "partition") if not views.get(v)]
            check(not missing, f"{label}:four-views", "all four data-view sections present" if not missing else f"missing views: {missing}")
            check(C.get("hook"), f"{label}:hook", "window.__geometry hook exposed")
            check(C.get("nodes_B", 0) > 0, f"{label}:B-nodes", f"{C.get('nodes_B', 0)} graph nodes")
            check(C.get("cards_D", 0) > 0, f"{label}:D-cards", f"{C.get('cards_D', 0)} partition cards")
            if not strip:
                has_explore = isinstance(doc.get("explore"), dict)
                if has_explore:
                    check(C.get("points_A", 0) > 0, "full:A-points", f"{C.get('points_A', 0)} scatter points")
                    if (doc.get("orthogonality") or {}).get("pairs"):
                        check(C.get("cells_C", 0) > 0, "full:C-cells", f"{C.get('cells_C', 0)} heatmap cells")
                    else:
                        check(C.get("empty_C"), "full:C-empty", "no orthogonality.pairs shipped; View C shows its empty state")
                else:
                    print("WARN: the file ships no explore object; A/C are expected empty")
                if member:
                    r = C.get("reorient") or {}
                    check(r.get("basis_changed"), "full:reorient-basis",
                          f"reorient({member!r}): basis {r.get('before')} -> {r.get('after')}")
                    check(r.get("member_now_basis"), "full:reorient-member", f"{member!r} is now a basis member")
                    check(r.get("candidates_rerendered"), "full:reorient-candidates",
                          f"View D re-rendered: {r.get('candidates_before')} -> {r.get('candidates_after')}")
                else:
                    print("WARN: no cycle in the layer data; re-orientation not exercised")
            else:
                check(C.get("empty_A"), "no-explore:A-empty", "View A shows its empty state")
                check(C.get("empty_C"), "no-explore:C-empty", "View C shows its empty state")

    failed = 0
    for ok, name, msg in findings:
        print(f"  {'OK  ' if ok else 'FAIL'} {name:<28} {msg}")
        failed += 0 if ok else 1
    if failed:
        print(f"ERROR: {failed} check(s) failed for {path}")
        return 1
    print(f"OK: geometry layer smoke test passed for {path} ({len(findings)} checks)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
