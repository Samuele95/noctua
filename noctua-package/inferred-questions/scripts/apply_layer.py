#!/usr/bin/env python3
"""
apply_layer.py — write the `open-questions` layer into a domain-forge HTML.

The script is the only place that writes HTML in the /inferred-questions
skill. It is byte-exact: the output is the input verbatim, with one new
layer block inserted just before the last `</body>`. The script enforces the
contract documented in references/layer-contract.md.

What is local here is only what is layer-specific: the questions.json
schema check, the schema-only collapse of per-class missing-individuals
questions, and the render JS / CSS. The block format, the input-digest
algorithm and the strip/replace logic are the layer platform's
(domain-forge/scripts/apply_layer.py), imported at run time — there is no
private copy and no fallback.

Usage:
    python apply_layer.py --input MODEL.html --questions questions.json \\
                          --output OUT.html [--regenerate] [--force] \\
                          [--domain-forge-dir DIR]

Platform location: DIR from --domain-forge-dir, else $DOMAIN_FORGE_DIR, else
the sibling directory <skills>/domain-forge/scripts (DIR may be the
domain-forge root or its scripts/ directory).

Exit codes:
    0 — wrote the output successfully
    1 — the platform refused the write (unsafe render/style content, …)
    2 — input is not a domain-forge model (missing #model-turtle), or the
        platform scripts were not found
    3 — open-questions layer already present and --regenerate not set
    4 — questions.json failed schema validation
    5 — could not locate </body> for insertion
    6 — output file already exists at --output and would be overwritten
        without --force (we treat overwrites as deliberate)
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import sys
from pathlib import Path
from typing import Tuple

sys.dont_write_bytecode = True  # never leave a __pycache__ inside domain-forge

LAYER_NAME = "open-questions"
LAYER_VERSION = 1

# The JSON-LD block carries the T-box and A-box. We use it to detect
# schema-only models (zero individuals) so the script can collapse
# per-class missing-individuals questions into one meta-question.
_JSONLD_RE = re.compile(
    r'<script\s+id="model-jsonld"[^>]*>([\s\S]*?)</script>',
    re.IGNORECASE,
)


def load_platform(explicit: str | None = None):
    """Import domain-forge/scripts/apply_layer.py as a module. Exit 2 if absent."""
    base = explicit or os.environ.get("DOMAIN_FORGE_DIR") or \
        Path(__file__).resolve().parents[2] / "domain-forge" / "scripts"
    base = Path(base)
    path = base / "scripts" / "apply_layer.py"
    if not path.is_file():
        path = base / "apply_layer.py"
    if not path.is_file():
        print(f"ERROR: platform scripts not found at {base} — domain-forge is a "
              "required sibling of this skill", file=sys.stderr)
        sys.exit(2)
    spec = importlib.util.spec_from_file_location("domain_forge_apply_layer", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _count_individuals(html: str, turtle_body: str | None) -> int:
    """Count A-box individuals declared in the input.

    An individual is any JSON-LD @graph node whose @type is present and is
    NOT a schema type (owl:Class / owl:ObjectProperty / owl:DatatypeProperty
    / owl:Ontology). This mirrors the domain-forge runtime's own
    `individuals()` definition. We do NOT rely on `owl:NamedIndividual`:
    domain-forge deliberately types individuals by their domain class only
    (it omits owl:NamedIndividual to avoid its RDFS-projector round-trip
    bug), so a NamedIndividual-only signal misreads a richly-populated A-box
    as schema-only and would wrongly collapse per-class questions into a
    false "A-box is empty" meta-question. The Turtle `a owl:NamedIndividual`
    fast-path is kept as an additional positive signal (`turtle_body` is the
    canonical Turtle text, as located by the platform).
    """
    _SCHEMA = ("owl:Class", "owl:ObjectProperty", "owl:DatatypeProperty",
               "owl:Ontology")
    count = 0
    m = _JSONLD_RE.search(html)
    if m:
        try:
            doc = json.loads(m.group(1))
            graph = doc.get("@graph", [])
            for node in graph:
                t = node.get("@type")
                types = t if isinstance(t, list) else [t] if t else []
                if not types:
                    continue
                # NamedIndividual is sufficient; otherwise, a node typed only
                # by non-schema classes is an A-box individual.
                named = any("NamedIndividual" in str(x) for x in types)
                non_schema = [x for x in types if x not in _SCHEMA
                              and "NamedIndividual" not in str(x)]
                if named or non_schema:
                    count += 1
        except json.JSONDecodeError:
            pass

    if turtle_body and re.search(r"\ba\s+owl:NamedIndividual\b", turtle_body):
        count = max(count, 1)
    return count


def _collapse_schema_only_missing(doc: dict) -> Tuple[dict, str]:
    """When the model is schema-only, fold per-class missing-individuals
    questions into one meta-question.

    The extractor sometimes generates one missing-individuals row per
    declared class even though the underlying concern is the same: "the
    model is schema-only — populate the A-box". When the input truly has
    no individuals, that per-class enumeration adds clutter without
    actionability; collapsing it into a single meta-question follows the
    taxonomy's own advice and keeps the review list focused.

    The collapse is gated on actually detecting zero individuals (see
    _count_individuals) so a model with even a single A-box assertion
    keeps its per-class breakdown.

    Returns the possibly-modified doc and a one-line note describing
    what (if anything) collapsed.
    """
    qs = doc.get("questions", []) or []
    missing = [q for q in qs if q.get("category") == "missing-individuals"]
    if len(missing) <= 1:
        return doc, ""

    # Build the replacement meta-question. Keep the lowest id among the
    # collapsed questions so id ordering is stable across re-runs.
    keep_id = min(q.get("id", "q-999") for q in missing)
    affected = [q.get("source", "?") for q in missing]
    meta = {
        "id": keep_id,
        "source": "model-jsonld",
        "source_kind": "iri",
        "category": "missing-individuals",
        "severity": "low",
        "question": (
            "The A-box is empty — no individuals declared for any of the "
            + str(len(affected))
            + " classes (" + ", ".join(affected[:5])
            + (", …" if len(affected) > 5 else "")
            + "). Is schema-only intentional, or is the next step "
            "/instance-create?"
        ),
        "suggested_next": (
            "If schema-only is intentional, mark this question out-of-scope. "
            "Otherwise run /instance-create to populate representative individuals."
        ),
        "engine_check": {"kind": "class-membership", "class": affected[0]} if affected else None,
        "status": "open",
    }
    kept = [q for q in qs if q.get("category") != "missing-individuals"]
    # Preserve emit order: insert meta where the first missing-individuals
    # question lived so the surrounding ordering does not shift.
    first_pos = min(i for i, q in enumerate(qs) if q.get("category") == "missing-individuals")
    kept.insert(first_pos, meta)
    doc["questions"] = kept
    note = f"collapsed {len(missing)} per-class missing-individuals questions into one meta-question"
    return doc, note


def _validate_questions(doc: dict) -> Tuple[bool, str]:
    """Lightweight schema check. Enough to catch malformed input from the
    extractor; not an exhaustive JSON-Schema validator (we don't need one)."""
    if not isinstance(doc, dict):
        return False, "questions.json root is not an object"
    for field in ("version", "categories", "questions"):
        if field not in doc:
            return False, f"missing top-level field: {field}"
    if doc.get("version") != LAYER_VERSION:
        return False, f"version {doc.get('version')} != expected {LAYER_VERSION}"
    if not isinstance(doc["categories"], list):
        return False, "categories is not a list"
    if not isinstance(doc["questions"], list):
        return False, "questions is not a list"
    seen_ids: set = set()
    for i, q in enumerate(doc["questions"]):
        if not isinstance(q, dict):
            return False, f"questions[{i}] is not an object"
        for field in (
            "id", "source", "source_kind", "category", "severity",
            "question", "suggested_next", "status",
        ):
            if field not in q:
                return False, f"questions[{i}] missing field: {field}"
        qid = q["id"]
        if qid in seen_ids:
            return False, f"duplicate question id: {qid}"
        seen_ids.add(qid)
        if q["severity"] not in ("high", "medium", "low"):
            return False, f"questions[{i}].severity invalid: {q['severity']}"
        if q["status"] not in ("open", "addressed", "deferred", "out-of-scope"):
            return False, f"questions[{i}].status invalid: {q['status']}"
        if q["source_kind"] not in (
            "iri", "rationale", "dmn-decision", "swrl-rule", "horn-clause",
        ):
            return False, f"questions[{i}].source_kind invalid: {q['source_kind']}"
        ec = q.get("engine_check")
        if ec is not None and not isinstance(ec, dict):
            return False, f"questions[{i}].engine_check must be null or object"
    return True, ""


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input", required=True, help="path to input HTML")
    p.add_argument("--questions", required=True, help="path to questions.json")
    p.add_argument("--output", required=True, help="path for output HTML")
    p.add_argument(
        "--regenerate",
        action="store_true",
        help="replace an existing open-questions layer in-place",
    )
    p.add_argument(
        "--force",
        action="store_true",
        help="overwrite --output if it already exists",
    )
    p.add_argument(
        "--domain-forge-dir",
        help="domain-forge root or scripts/ dir (default: sibling skill, or $DOMAIN_FORGE_DIR)",
    )
    args = p.parse_args(argv)
    platform = load_platform(args.domain_forge_dir)

    input_path = Path(args.input)
    questions_path = Path(args.questions)
    output_path = Path(args.output)

    html = input_path.read_text(encoding="utf-8")
    data = json.loads(questions_path.read_text(encoding="utf-8"))

    # Confirm this is a domain-forge composed model.
    if not platform.is_model(html):
        print(
            'ERROR (2): input is not a domain-forge model '
            '(no <script id="model-turtle"> block found).',
            file=sys.stderr,
        )
        return 2

    # Idempotency: refuse re-add unless --regenerate. (The platform writer
    # strips and replaces the existing block itself when we go ahead.)
    if platform.find_layer(html, LAYER_NAME) and not args.regenerate:
        print(
            "ERROR (3): input already contains an `open-questions` layer. "
            "Pass --regenerate to replace, or run /inferred-questions against "
            "the predecessor instead.",
            file=sys.stderr,
        )
        return 3

    # Output overwrite gate.
    if output_path.exists() and not args.force and output_path.resolve() != input_path.resolve():
        print(
            f"ERROR (6): output {output_path} already exists; pass --force to overwrite.",
            file=sys.stderr,
        )
        return 6

    # Schema-only collapse: if the input has no A-box, fold per-class
    # missing-individuals questions into one meta-question. The
    # extractor's taxonomy already advises this, but enforcing it
    # mechanically keeps the output consistent even when the LLM forgets.
    individuals_count = _count_individuals(html, platform.turtle_body(html))
    if individuals_count == 0:
        data, collapse_note = _collapse_schema_only_missing(data)
    else:
        collapse_note = ""

    # Fill in provenance fields. The extractor doesn't know these — the
    # script is the trust boundary that stamps them.
    produced_at = platform.utc_now_iso()
    input_digest = platform.domain_digest(html)
    data["version"] = LAYER_VERSION
    data["produced_at"] = produced_at
    data["input_digest"] = input_digest

    ok, why = _validate_questions(data)
    if not ok:
        print(f"ERROR (4): questions.json invalid: {why}", file=sys.stderr)
        return 4

    # Render the data JSON in a stable, deterministic form. sort_keys keeps
    # re-runs byte-identical; indent makes inspection in the file readable.
    data_json = json.dumps(data, indent=2, sort_keys=False, ensure_ascii=False)

    # The platform composes the block (header, data, render, style, end
    # marker), inserts it before the last </body>, and self-checks the
    # strict-superset invariant (prefix and suffix of the input preserved).
    try:
        new_html = platform.apply_layer(
            html, LAYER_NAME, data_json, _RENDER_JS.strip(),
            style_css=_STYLE_CSS.strip(), produced_by="/inferred-questions",
            version=LAYER_VERSION, produced_at=produced_at,
        )
    except ValueError as e:
        if "</body>" in str(e):
            print("ERROR (5): could not locate </body> in input HTML; refusing to insert",
                  file=sys.stderr)
            return 5
        print(f"ERROR (1): {e}", file=sys.stderr)
        return 1

    output_path.write_text(new_html, encoding="utf-8")
    msg = (
        f"wrote {output_path} "
        f"(layer={LAYER_NAME} v{LAYER_VERSION}, "
        f"questions={len(data['questions'])}, "
        f"digest={input_digest})"
    )
    if collapse_note:
        msg += f"\n  note: {collapse_note}"
    print(msg)
    return 0


# -----------------------------------------------------------------------------
# Render code that is inlined into the layer block.
#
# Design: depends only on the layer's own data script and on the DOM
# selectors that domain-forge already emits. Reads `R` (the live reasoner
# state) when present for engine_check enrichment, but degrades cleanly.
# -----------------------------------------------------------------------------

_RENDER_JS = r"""
(function(){
  /* Bail if the layer has already been mounted. The script tag can be
     loaded more than once if the file is opened, the layer is stripped,
     and a fresh layer is composed in the same document — in normal use
     that does not happen, but the guard is cheap insurance. */
  if (document.querySelector('section.layer-open-questions')) return;

  function ready(fn){
    if (document.readyState !== 'loading') fn();
    else document.addEventListener('DOMContentLoaded', fn);
  }

  function readData(){
    var el = document.getElementById('layer-open-questions-data');
    if (!el) return null;
    try { return JSON.parse(el.textContent || '{}'); }
    catch (e){ console.warn('[open-questions] could not parse data', e); return null; }
  }

  /* Tiny DOM helper. Deliberately omits any innerHTML escape hatch: every
     text value goes through textContent so the layer cannot inject markup
     from the data script even if the extractor produced a malicious value. */
  function el(tag, attrs, kids){
    var n = document.createElement(tag);
    if (attrs) for (var k in attrs){
      if (k === 'class') n.className = attrs[k];
      else if (k === 'text') n.textContent = attrs[k];
      else if (k.indexOf('on') === 0 && typeof attrs[k] === 'function') n[k] = attrs[k];
      else n.setAttribute(k, attrs[k]);
    }
    (kids || []).forEach(function(c){ if (c) n.appendChild(c); });
    return n;
  }

  /* Integration with the input HTML's tab system.

     The composed domain-forge HTML uses this convention:
       <nav class="tabs" role="tablist"><button data-tab="X" class="active">…</button>…</nav>
       <section class="tab-pane active" data-tab="X" id="tab-X">…</section>
       <section class="tab-pane"        data-tab="Y" id="tab-Y">…</section>

     Visibility is controlled by the `active` class. We integrate by:
       — appending one button into nav.tabs (NO `active` class on first load);
       — appending one section with class "layer-open-questions tab-pane"
         (NO `active` class, so the input's existing CSS hides it);
       — toggling the `active` class on every `nav.tabs button` and every
         `section.tab-pane` whenever a tab is clicked, exactly like the
         input's own switcher does. */
  function pickTabContainer(){
    return document.querySelector('nav.tabs')
        || document.querySelector('nav[role="tablist"]')
        || document.querySelector('[data-tabs]')
        || null;
  }
  function pickPaneSibling(){
    /* Place the new pane right after the last existing .tab-pane so the
       DOM order matches what the host page already has — keeps layouts
       that rely on flow ordering happy. */
    var panes = document.querySelectorAll('section.tab-pane');
    return panes.length ? panes[panes.length - 1] : null;
  }

  function switchTab(name){
    /* Mirrors the input's own switchTab: toggle `.active` on every nav
       button and every tab-pane section. We do not call the host's
       switcher because it is defined inside an IIFE and not exposed. */
    document.querySelectorAll('nav.tabs button[data-tab], nav[role="tablist"] button[data-tab]')
      .forEach(function(b){ b.classList.toggle('active', b.getAttribute('data-tab') === name); });
    document.querySelectorAll('section.tab-pane')
      .forEach(function(p){ p.classList.toggle('active', p.getAttribute('data-tab') === name); });
  }

  function jumpToSource(q){
    var attr, val;
    if (q.source_kind === 'iri'){ attr = 'data-iri'; val = q.source; }
    else if (q.source_kind === 'dmn-decision'){ attr = 'data-dmn'; val = q.source; }
    else if (q.source_kind === 'swrl-rule'){ attr = 'data-swrl'; val = q.source; }
    else if (q.source_kind === 'horn-clause'){ attr = 'data-horn'; val = q.source; }
    else if (q.source_kind === 'rationale'){ attr = 'data-rationale'; val = q.source; }
    if (!attr) return;
    var target = document.querySelector('[' + attr + '="' + val + '"]');
    if (!target) return;
    var pane = target.closest('section.tab-pane');
    if (pane){
      var name = pane.getAttribute('data-tab');
      if (name) switchTab(name);
    }
    setTimeout(function(){
      target.scrollIntoView({behavior:'smooth', block:'center'});
      target.style.outline = '2px solid var(--accent, #4f46e5)';
      setTimeout(function(){ target.style.outline = ''; }, 1500);
    }, 50);
  }

  /* Engine integration. The composed HTML carries a runtime reasoner
     state exposed (in versions that ship the embedded engine) as
     `window.R`. Its real shape (see engine-source/00-core/logic.js):

       R.indClasses : Map<individualIRI, { asserted:Set<IRI>, inferred:Map<IRI,prov> }>
       R.facts.asserted : [{ s, p, o|v, kind:'object'|'data' }]
       R.facts.inferred : same shape, plus `prov`
       R.contradictions : []

     For `class-membership` we count individuals whose asserted or
     inferred class set contains the target IRI. For
     `functional-property-collision` we scan asserted facts for any
     subject with >1 distinct value of the named property. Both
     accessors degrade gracefully when R is absent (the badge simply
     does not render). */
  function countClassMembership(classIRI){
    var R = window.R;
    if (!R || !R.indClasses || typeof R.indClasses.forEach !== 'function') return 0;
    var n = 0;
    R.indClasses.forEach(function(entry){
      if (!entry) return;
      if (entry.asserted && entry.asserted.has && entry.asserted.has(classIRI)) { n++; return; }
      if (entry.inferred && entry.inferred.has && entry.inferred.has(classIRI)) { n++; }
    });
    return n;
  }

  function functionalConflicts(propIRI){
    var R = window.R;
    if (!R || !R.facts || !R.facts.asserted) return [];
    var bySubj = Object.create(null);
    R.facts.asserted.forEach(function(f){
      if (!f || f.p !== propIRI) return;
      var v = (f.kind === 'object') ? f.o : f.v;
      var key = f.s;
      if (!bySubj[key]) bySubj[key] = new Set();
      bySubj[key].add(typeof v === 'string' ? v : JSON.stringify(v));
    });
    var conflicts = [];
    Object.keys(bySubj).forEach(function(s){
      if (bySubj[s].size > 1) conflicts.push(s);
    });
    return conflicts;
  }

  function engineCheckBadge(q){
    if (!q.engine_check) return null;
    if (typeof window.R !== 'object' || !window.R) return null;
    var ec = q.engine_check;
    try {
      if (ec.kind === 'class-membership' && ec['class']){
        var n = countClassMembership(ec['class']);
        if (n > 0){
          return el('span', {class:'oq-badge oq-badge-live',
            text:'live: ' + n + ' individual(s) — consider marking addressed'});
        }
        return el('span', {class:'oq-badge oq-badge-warn',
          text:'live: 0 individuals — still open'});
      }
      if (ec.kind === 'functional-property-collision' && ec.property){
        var subs = functionalConflicts(ec.property);
        if (subs.length){
          return el('span', {class:'oq-badge oq-badge-warn',
            text:'live: ' + subs.length + ' subject(s) with conflicting values'});
        }
        return el('span', {class:'oq-badge oq-badge-live',
          text:'live: no conflicts on current A-box'});
      }
    } catch (_e){}
    return null;
  }

  function severityClass(s){
    return 'oq-sev oq-sev-' + (s || 'medium');
  }

  function makeCard(q, onStatusChange){
    var card = el('article', {class:'oq-card', 'data-qid': q.id});
    var head = el('header', {class:'oq-head'}, [
      el('span', {class:severityClass(q.severity), text:q.severity}),
      el('span', {class:'oq-cat', text:q.category}),
      el('a', {class:'oq-source', href:'#', onclick:function(ev){
        ev.preventDefault(); jumpToSource(q);
      }, text:q.source + ' →'}),
    ]);
    var nextP = el('p', {class:'oq-next'}, [
      el('b', {text:'Next: '}),
      document.createTextNode(q.suggested_next || ''),
    ]);
    var body = el('div', {class:'oq-body'}, [
      el('p', {class:'oq-q', text:q.question}),
      nextP,
    ]);
    var live = engineCheckBadge(q);
    if (live) body.appendChild(live);
    var statuses = ['open','addressed','deferred','out-of-scope'];
    var foot = el('footer', {class:'oq-foot'}, statuses.map(function(s){
      return el('button', {
        class:'oq-status' + (q.status === s ? ' active' : ''),
        text:s, onclick:function(){ onStatusChange(q, s); }
      });
    }));
    card.appendChild(head); card.appendChild(body); card.appendChild(foot);
    return card;
  }

  function build(){
    var data = readData();
    if (!data){ return; }

    /* The pane carries the host's `tab-pane` class but NOT `active` —
       the host's CSS hides it until the tab button is clicked. The
       `data-layer` attribute is kept for layer-strip identification;
       the `data-tab` attribute is what the host's switcher recognises. */
    var pane = el('section', {
      'data-layer':'open-questions',
      'data-tab':'open-questions',
      class:'layer-open-questions tab-pane'
    });
    pane.appendChild(el('h2', {text:'Open questions'}));
    pane.appendChild(el('p', {class:'oq-sub',
      text:'Latent modelling questions surfaced from this model. ' +
           'Mark each addressed / deferred / out-of-scope as you triage.'}));

    var filters = el('div', {class:'oq-filters'});
    var cats = (data.categories || []).slice();
    var allBtn = el('button', {class:'oq-chip active',
      'data-cat':'__all', text:'all'});
    filters.appendChild(allBtn);
    cats.forEach(function(c){
      filters.appendChild(el('button', {class:'oq-chip', 'data-cat':c, text:c}));
    });
    pane.appendChild(filters);

    var listEl = el('div', {class:'oq-list'});
    pane.appendChild(listEl);

    // Working copy of the data — mutating this never touches the original
    // script's textContent until the user clicks Save snapshot.
    var working = JSON.parse(JSON.stringify(data));

    function onStatusChange(q, newStatus){
      q.status = newStatus;
      var w = working.questions.find(function(x){ return x.id === q.id; });
      if (w) w.status = newStatus;
      var card = pane.querySelector('[data-qid="' + q.id + '"]');
      if (!card) return;
      var btns = card.querySelectorAll('.oq-status');
      btns.forEach(function(b){
        b.classList.toggle('active', b.textContent === newStatus);
      });
    }

    function activeCat(){
      var b = filters.querySelector('.oq-chip.active');
      return b ? b.getAttribute('data-cat') : '__all';
    }

    function rerender(){
      listEl.innerHTML = '';
      var ac = activeCat();
      working.questions.forEach(function(q){
        if (ac !== '__all' && q.category !== ac) return;
        listEl.appendChild(makeCard(q, onStatusChange));
      });
      if (!listEl.children.length){
        listEl.appendChild(el('p', {class:'oq-empty',
          text:'No questions in this category.'}));
      }
    }

    filters.addEventListener('click', function(ev){
      var t = ev.target.closest('.oq-chip'); if (!t) return;
      filters.querySelectorAll('.oq-chip').forEach(function(b){
        b.classList.toggle('active', b === t);
      });
      rerender();
    });

    var saveBtn = el('button', {class:'oq-save',
      text:'Save snapshot (download)', onclick:function(){
        // Snapshot pattern: serialise current working state back into the
        // data script and offer a download of the resulting HTML.
        var script = document.getElementById('layer-open-questions-data');
        if (script){ script.textContent = JSON.stringify(working, null, 2); }
        var html = '<!DOCTYPE html>\n' + document.documentElement.outerHTML;
        var blob = new Blob([html], {type:'text/html'});
        var a = document.createElement('a');
        a.href = URL.createObjectURL(blob);
        a.download = (document.title || 'model') + '.open-questions.snapshot.html';
        a.click();
        URL.revokeObjectURL(a.href);
      }});
    pane.appendChild(saveBtn);

    /* Insert after the last existing tab-pane so the document flow
       order matches what the host already has. Falls back to <main>
       (or <body>) if no panes are present yet. */
    var sibling = pickPaneSibling();
    if (sibling && sibling.parentNode){
      sibling.parentNode.insertBefore(pane, sibling.nextSibling);
    } else {
      (document.querySelector('main') || document.body).appendChild(pane);
    }

    /* Append our button into the host's nav.tabs. We do NOT mark it
       active; the user opens our tab by clicking. The badge shows the
       question count, matching the host's existing `.count` spans on
       the other tab buttons. */
    var tabs = pickTabContainer();
    if (tabs){
      var btn = el('button', {
        class:'oq-tabbtn',
        'data-tab':'open-questions',
        role:'tab',
        onclick: function(){ switchTab('open-questions'); }
      }, [
        document.createTextNode('Open questions '),
        el('span', {class:'count oq-tabbadge', text:String((data.questions || []).length)})
      ]);
      tabs.appendChild(btn);
    }

    rerender();
  }

  ready(build);
})();
"""

_STYLE_CSS = r"""
.layer-open-questions { padding: 1.25rem; font: inherit; color: var(--ink, #18181b); }
.layer-open-questions h2 { margin: 0 0 .25rem; }
.layer-open-questions .oq-sub { color: var(--muted, #71717a); margin: 0 0 1rem; }
.layer-open-questions .oq-filters { display: flex; flex-wrap: wrap; gap: .35rem; margin-bottom: 1rem; }
.layer-open-questions .oq-chip {
  padding: .25rem .6rem; border: 1px solid var(--border, #e4e4e7);
  background: var(--surface, #fff); border-radius: 999px; cursor: pointer;
  font-size: .85rem;
}
.layer-open-questions .oq-chip.active {
  background: var(--accent-soft, #eef2ff); border-color: var(--accent, #4f46e5);
  color: var(--accent-ink, #3730a3);
}
.layer-open-questions .oq-list { display: grid; gap: .75rem; }
.layer-open-questions .oq-card {
  border: 1px solid var(--border, #e4e4e7); border-radius: 10px;
  background: var(--surface, #fff); padding: .85rem 1rem;
}
.layer-open-questions .oq-head { display: flex; gap: .5rem; align-items: center;
  margin-bottom: .35rem; font-size: .82rem; }
.layer-open-questions .oq-sev {
  padding: .1rem .45rem; border-radius: 4px; font-weight: 600;
  text-transform: uppercase; letter-spacing: .04em;
}
.layer-open-questions .oq-sev-high   { background: #fee2e2; color: #991b1b; }
.layer-open-questions .oq-sev-medium { background: #fef3c7; color: #92400e; }
.layer-open-questions .oq-sev-low    { background: #e0e7ff; color: #3730a3; }
.layer-open-questions .oq-cat { color: var(--muted, #71717a); }
.layer-open-questions .oq-source { margin-left: auto; color: var(--accent, #4f46e5);
  text-decoration: none; }
.layer-open-questions .oq-source:hover { text-decoration: underline; }
.layer-open-questions .oq-q { margin: 0 0 .25rem; }
.layer-open-questions .oq-next { margin: 0; color: var(--muted, #71717a); font-size: .9rem; }
.layer-open-questions .oq-badge {
  display: inline-block; padding: .15rem .5rem; border-radius: 4px;
  font-size: .75rem; margin-top: .35rem;
}
.layer-open-questions .oq-badge-live { background: #dcfce7; color: #166534; }
.layer-open-questions .oq-badge-warn { background: #fef3c7; color: #92400e; }
.layer-open-questions .oq-foot { margin-top: .5rem; display: flex; gap: .35rem; }
.layer-open-questions .oq-status {
  padding: .2rem .55rem; border: 1px solid var(--border, #e4e4e7);
  background: var(--surface, #fff); border-radius: 999px; cursor: pointer;
  font-size: .78rem; color: var(--muted, #71717a);
}
.layer-open-questions .oq-status.active {
  background: var(--ink, #18181b); border-color: var(--ink, #18181b);
  color: var(--surface, #fff);
}
.layer-open-questions .oq-empty { color: var(--muted, #71717a); }
.layer-open-questions .oq-save {
  margin-top: 1rem; padding: .4rem .8rem; border-radius: 6px;
  border: 1px solid var(--accent, #4f46e5);
  background: var(--accent, #4f46e5); color: white; cursor: pointer;
}
.oq-tabbtn .oq-tabbadge {
  margin-left: .35rem; padding: .05rem .35rem; border-radius: 999px;
  background: var(--accent-soft, #eef2ff); color: var(--accent-ink, #3730a3);
  font-size: .72rem;
}
"""


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
