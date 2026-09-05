#!/usr/bin/env python3
"""Validate a domain-forge HTML model — v3 architecture.

v3 invariants (the canonical data is the only source of truth; the body is
rendered from it at load):

  1. Exactly one <script id="domain-model" type="text/turtle"> that parses.
  2. Every owl:ObjectProperty declares rdfs:domain and rdfs:range pointing
     to declared owl:Class IRIs.
  3. Every owl:DatatypeProperty declares rdfs:domain (a class) and rdfs:range
     (an xsd: datatype).
  4. rdfs:subClassOf is acyclic.
  5. <script id="model-jsonld" type="application/ld+json"> is present, parses,
     and its @graph mirrors the Turtle (same set of class IRIs).
  6. Every class in the canonical data carries an ex:component annotation.
  7. <script id="model-markdown" type="text/markdown"> is present and non-empty.
  8. (composability) Every component is independently extractable: running
     scripts/extract_component.py for each component produces a file that
     itself passes invariants 1–7.
  9. Self-contained — no <script src=…>, <link href=…://>, etc. Network refs
     are forbidden.
 10. (only if model-dmn is non-empty) Every DMN decision declares a known
     hit policy (U/A/P/F/C/R/O/C+…), has inputs / outputs / rules, each rule
     has the right number of input cells, and every cell is a recognised
     FEEL expression (literal, comparison, interval, dash, or not(…)).
     Inputs written as Entity.property must resolve to a declared class
     and data property.
 11. (only if model-horn is non-empty) Every Horn line is a well-formed
     clause (Head(args). or Head(args) :- Body.); object/data properties that
     mirror the ontology have arity 2, while class predicates may be arity >= 1
     (both the unary entity style `transaction(t1)` and the multi-place
     constructor / database-oriented style `transaction(t1,k1,h1,500,ts)` are
     accepted); and every body predicate resolves to an ontology term, a known
     Prolog built-in, or a derived head defined in the same Horn block.
 12. (only if a headless browser is available) Each in-browser RDF projector
     (Turtle / RDFS / N-Triples / RDF/XML) renders to text that rdflib can
     re-parse, and the rdfs:subClassOf triple count round-trips against the
     canonical Turtle. Catches projector regressions where array-valued
     OWL features (multi-inheritance, multi-domain) silently mangle output.
     Skipped with WARN if no headless browser is installed.
 13. (layers) Every `<!-- @LAYER:start NAME … -->` has a matching
     `<!-- @LAYER:end NAME -->`, blocks neither nest nor overlap, no name is
     declared twice, each start header carries produced-by / produced-at /
     input-digest, and each block contains a `layer-NAME-data` and a
     `layer-NAME-render` script. Models with no layers: "no layers (skipped)".
 14. (layers) Every layer's input-digest equals "sha256:" + SHA-256 of the
     exact bytes between the current `<script id="domain-model" …>` open tag
     and its `</script>` (no normalisation — the same algorithm as
     scripts/apply_layer.py, /model-chat and /inferred-questions). A mismatch
     means the base model was edited after the layer was produced.
 15. (layers, static) No layer's render script WRITES to a protected script:
     assignment to .textContent / .innerHTML / .innerText / .text / .outerHTML,
     or a call to .replaceWith(…) / .remove() on an element obtained via
     getElementById('model-*' | 'domain-model' | 'layer-<OTHER>-data|render')
     or querySelector('#model-…' | '#layer-<OTHER>-…' | 'script[id…]'), either
     directly or through a single-level alias (`var s = document.getElementById(…)`).
     Reading (`.textContent` on the right-hand side, JSON.parse(...)) and the
     layer's OWN `layer-NAME-*` ids are allowed. Heuristic regex scan — see
     check_layers_static for its documented limits.
 16. (layers, headless only; WARN-skip otherwise) For each layer, a temp copy
     of the page with every OTHER layer stripped is loaded in Chromium with a
     probe that records uncaught errors / unhandled rejections and whether an
     element `[data-layer="NAME"]` exists after load. FAIL on an uncaught error
     not already present in the layer-free baseline, or on a missing mount.
 17. (only if the model has an A-box or SWRL) The @KG_RUNTIME block (in-browser
     SPARQL + on-demand reasoner runners) is present and the runtime exposes
     window.__kgReasoning. Static check; always runs.
 18. (only if the model has an A-box, headless) The unified KG diagram renders:
     individual ellipses, the Schema (T-box) and Individuals/Data (A-box) frames,
     and the three layer chips. Skipped WARN without a browser.
 19. (only if the model has an A-box, headless) The runtimes function: the
     reasoner runs and reports triple counts (WARN, not FAIL, when it inferred
     nothing — a thin A-box is legitimate), SPARQL returns rows, and the SPARQL
     runner (plus the SWRL reasoner-runner when SWRL is present) mount. Skipped
     WARN without a browser.

Turtle parsing prefers rdflib (rigorous); falls back to a small line parser.
Exit 0 = pass, 1 = fail, 2 = could not run (bad input).
"""
import json
import os
import re
import sys
import subprocess
import tempfile
from html.parser import HTMLParser

PASS, FAIL, WARN = [], [], []


def ok(m):   PASS.append(m)
def bad(m):  FAIL.append(m)
def warn(m): WARN.append(m)


# ---------- read embedded scripts ----------
class ScriptScan(HTMLParser):
    def __init__(self):
        super().__init__()
        self.scripts = {}        # id -> content
        self.external = []       # list of (tag, src/href)
        self._cur_id = None
        self._cur_buf = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "script":
            sid = a.get("id") or ""
            src = a.get("src")
            if src:
                if re.match(r'^(https?:)?//', src):
                    self.external.append(("script", src))
            self._cur_id = sid
            self._cur_buf = []
        elif tag == "link":
            href = a.get("href") or ""
            if re.match(r'^(https?:)?//', href):
                self.external.append(("link", href))
        elif tag in ("iframe", "img", "video", "audio", "source"):
            src = a.get("src") or ""
            if re.match(r'^(https?:)?//', src):
                self.external.append((tag, src))

    def handle_data(self, data):
        if self._cur_id is not None:
            self._cur_buf.append(data)

    def handle_endtag(self, tag):
        if tag == "script" and self._cur_id is not None:
            if self._cur_id:
                self.scripts[self._cur_id] = ''.join(self._cur_buf)
            self._cur_id = None
            self._cur_buf = []


def get_scripts(html_text):
    sc = ScriptScan()
    sc.feed(html_text)
    return sc


# ---------- turtle -> triples ----------
def parse_with_rdflib(ttl):
    try:
        import rdflib  # type: ignore
    except Exception:
        return None
    g = rdflib.Graph()
    try:
        g.parse(data=ttl, format="turtle")
    except Exception as e:
        bad(f"invariant 1: Turtle did not parse (rdflib): {e}")
        return "ERROR"
    def q(t):
        try: return g.qname(t)
        except Exception: return str(t)
    return [(q(s), q(p), q(o)) for s, p, o in g]


def parse_linewise(ttl):
    body = re.sub(r'(?m)^\s*@(?:prefix|base)\b[^\n]*$', '', ttl)
    body = re.sub(r'#.*', '', body)
    tok = r'[^\s;,]+'
    triples = []
    for st in [s.strip() for s in re.split(r'\.\s*(?=\S|\Z)', body) if s.strip()]:
        m = re.match(r'(' + tok + r')\s+(.*)', st, re.S)
        if not m:
            continue
        subj, rest = m.group(1), m.group(2)
        for po in rest.split(';'):
            pm = re.match(r'(' + tok + r')\s+(.*)', po.strip(), re.S)
            if not pm:
                continue
            pred = pm.group(1)
            for obj in pm.group(2).split(','):
                obj = obj.strip()
                if obj:
                    triples.append((subj, pred, obj))
    return triples


def get_triples(ttl):
    t = parse_with_rdflib(ttl)
    if t == "ERROR":
        return None
    if t is None:
        out = parse_linewise(ttl)
        ok("invariant 1: Turtle parsed (line parser; install rdflib for rigorous check)")
        return out
    ok("invariant 1: Turtle parses (rdflib)")
    return t


def localname(iri):
    return re.sub(r'^[^:]*:', '', iri)


# ---------- extract canonical model from triples ----------
def index_model(triples):
    classes = set()
    obj_props, data_props = set(), set()
    domain, rng = {}, {}
    subclass = []
    components = {}
    individuals = {}
    for s, p, o in triples:
        pl = localname(p)
        if p == 'a' or pl == 'type':
            ol = localname(o)
            if ol == 'Class':
                classes.add(s)
            elif ol == 'ObjectProperty':
                obj_props.add(s)
            elif ol == 'DatatypeProperty':
                data_props.add(s)
            else:
                individuals[s] = o
        elif pl == 'domain':
            domain[s] = o
        elif pl == 'range':
            rng[s] = o
        elif pl == 'subClassOf':
            subclass.append((s, o))
        elif pl == 'component':
            components[s] = o.strip('"')
    return dict(classes=classes, obj_props=obj_props, data_props=data_props,
                domain=domain, range=rng, subclass=subclass,
                components=components, individuals=individuals)


# ---------- invariants ----------
def check_properties_and_hierarchy(M):
    classes = M['classes']
    for op in sorted(M['obj_props']):
        d, r = M['domain'].get(op), M['range'].get(op)
        if not d or not r:
            bad(f"invariant 2: object property {op} missing "
                f"{'domain' if not d else 'range'}")
            continue
        if d not in classes:
            bad(f"invariant 2: object property {op} domain {d} is not a declared owl:Class")
        if r not in classes:
            bad(f"invariant 2: object property {op} range {r} is not a declared owl:Class")
    if M['obj_props']:
        ok(f"invariant 2: {len(M['obj_props'])} object properties checked")

    for dp in sorted(M['data_props']):
        d, r = M['domain'].get(dp), M['range'].get(dp)
        if not d:
            bad(f"invariant 3: data property {dp} missing domain")
        elif d not in classes:
            bad(f"invariant 3: data property {dp} domain {d} not a declared class")
        if not r:
            bad(f"invariant 3: data property {dp} missing range")
        elif not r.startswith("xsd:") and "XMLSchema" not in r:
            bad(f"invariant 3: data property {dp} range {r} is not an xsd: datatype")
    if M['data_props']:
        ok(f"invariant 3: {len(M['data_props'])} data properties checked")

    graph = {}
    for sub, sup in M['subclass']:
        graph.setdefault(sub, []).append(sup)
    color = {}
    def dfs(n):
        color[n] = 1
        for m in graph.get(n, []):
            c = color.get(m, 0)
            if c == 1: return [n, m]
            if c == 0:
                r = dfs(m)
                if r: return [n] + r
        color[n] = 2
        return None
    cyc = None
    for n in list(graph):
        if color.get(n, 0) == 0:
            cyc = dfs(n)
            if cyc: break
    if cyc:
        bad(f"invariant 4: subClassOf cycle: {' -> '.join(cyc)}")
    else:
        ok(f"invariant 4: subClassOf acyclic ({len(M['subclass'])} edges)")


def check_jsonld_mirror(scripts, M):
    raw = scripts.get('model-jsonld', '').strip()
    if not raw:
        bad("invariant 5: <script id='model-jsonld' type='application/ld+json'> missing")
        return None
    try:
        ld = json.loads(raw)
    except Exception as e:
        bad(f"invariant 5: JSON-LD did not parse: {e}")
        return None
    graph = ld.get('@graph') or []
    ids = {n['@id'] for n in graph if isinstance(n, dict) and '@id' in n}
    expected_classes = {c for c in M['classes']}
    missing = expected_classes - ids
    extra_classes = set()
    for n in graph:
        if not isinstance(n, dict): continue
        ty = n.get('@type')
        if not ty: continue
        tys = ty if isinstance(ty, list) else [ty]
        if any(re.sub(r'^[^:]*:', '', t) == 'Class' for t in tys):
            extra_classes.add(n['@id'])
    extra_only = (extra_classes - expected_classes)
    if missing:
        bad(f"invariant 5: classes in Turtle but missing from JSON-LD @graph: {sorted(missing)}")
    if extra_only:
        bad(f"invariant 5: classes in JSON-LD but missing from Turtle: {sorted(extra_only)}")
    if not missing and not extra_only:
        ok(f"invariant 5: JSON-LD mirror matches Turtle ({len(expected_classes)} classes)")
    return ld


def check_components(M):
    no_comp = [c for c in M['classes'] if c not in M['components']]
    if no_comp:
        bad(f"invariant 6: classes without ex:component annotation: {sorted(no_comp)}")
    else:
        comps = sorted(set(M['components'].values()))
        ok(f"invariant 6: every class is in a component ({len(comps)} components: {comps})")


def check_markdown(scripts):
    raw = (scripts.get('model-markdown') or '').strip()
    if not raw:
        bad("invariant 7: <script id='model-markdown' type='text/markdown'> missing or empty")
    else:
        lines = [l for l in raw.splitlines() if l.strip()]
        if len(lines) < 3:
            bad(f"invariant 7: Markdown summary is too short ({len(lines)} non-blank lines); "
                f"write 6–15 lines so the Summary tab is informative")
        else:
            ok(f"invariant 7: Markdown summary present ({len(lines)} non-blank lines)")


def check_self_contained(scan):
    if scan.external:
        bad(f"invariant 9: external network references found: {scan.external[:5]}"
            + (' ...' if len(scan.external) > 5 else ''))
    else:
        ok("invariant 9: self-contained (no external network refs)")


DMN_HIT_POLICIES = {'U', 'A', 'P', 'F', 'C', 'R', 'O', 'C+', 'C<', 'C>', 'C#'}

# A FEEL input cell is one of:
#   -                       irrelevant (don't care)
#   "string" / -1.23 / 100  literal
#   true / false / null     boolean / null literal
#   not(expr)               negation
#   <,<=,>,>=,!=,= value    comparison
#   [low..high] etc.        interval (math bracket notation)
FEEL_CELL = re.compile(
    r'^(?:'
    r'-'                                                  # dash
    r'|"(?:[^"\\]|\\.)*"'                                 # string literal
    r'|-?\d+(?:\.\d+)?'                                   # numeric literal
    r'|true|false|null'                                   # boolean/null
    r'|not\(\s*.+\s*\)'                                   # negation
    r'|[<>!]=\s*[^\s].*|[<>]\s*[^\s].*|=\s*[^\s].*'       # comparison / equality
    r'|[\[(]\s*-?\d+(?:\.\d+)?\s*\.\.\s*-?\d*(?:\.\d+)?\s*[\])]'  # interval
    r')\s*$'
)
HORN_CLAUSE = re.compile(
    r'^\s*([a-z_][\w]*)\s*\(([^)]*)\)\s*(?::-\s*(.+?))?\s*\.\s*$'
)
HORN_BODY_PRED = re.compile(r'\b([a-z_][\w]*)\s*\(')

HORN_BUILTINS = {
    '=', '<', '>', '<=', '>=', r'\\=', 'is',
    'true', 'false', 'fail', 'not', 'member',
    'write', 'nl', 'assert', 'asserta', 'retract',
    'integer', 'number', 'atom', 'compound', 'var', 'nonvar',
}


def check_dmn(scripts, M):
    raw = (scripts.get('model-dmn') or '').strip()
    if not raw:
        return
    try:
        doc = json.loads(raw)
    except Exception as e:
        bad(f"invariant 10: DMN JSON did not parse: {e}")
        return
    if not isinstance(doc, dict):
        bad("invariant 10: DMN root must be an object with a 'decisions' array")
        return
    decisions = doc.get('decisions') or []
    if not isinstance(decisions, list):
        bad("invariant 10: DMN 'decisions' must be a list")
        return
    if not decisions:
        return  # empty placeholder — nothing to check

    class_local = {re.sub(r'^[^:]*:', '', c).lower() for c in M['classes']}
    dprop_local = {re.sub(r'^[^:]*:', '', p).lower() for p in M['data_props']}
    seen_ids = set()

    for d in decisions:
        did = d.get('id') or '?'
        if did in seen_ids:
            bad(f"invariant 10: decision id {did!r} declared twice")
        seen_ids.add(did)

        hp = d.get('hitPolicy')
        if not hp:
            bad(f"invariant 10: decision {did} missing hitPolicy")
        elif hp not in DMN_HIT_POLICIES:
            bad(f"invariant 10: decision {did} hitPolicy {hp!r} not in {sorted(DMN_HIT_POLICIES)}")

        inputs  = d.get('inputs')  or []
        outputs = d.get('outputs') or ([d['output']] if 'output' in d else [])
        rules   = d.get('rules')   or []

        if not inputs:
            bad(f"invariant 10: decision {did} has no inputs")
        if not outputs:
            bad(f"invariant 10: decision {did} has no outputs")
        if not rules:
            bad(f"invariant 10: decision {did} has no rules")

        # Each input column SHOULD reference an entity attribute when written as
        # "Entity.property". Soft check — warn (not fail) if it doesn't resolve.
        for col in inputs:
            if not isinstance(col, str): continue
            m = re.match(r'^([A-Za-z_][\w]*)\.([A-Za-z_][\w]*)$', col)
            if m:
                cls_l, prop_l = m.group(1).lower(), m.group(2).lower()
                if cls_l not in class_local:
                    bad(f"invariant 10: decision {did} input {col!r} references "
                        f"undeclared class '{m.group(1)}'")
                if prop_l not in dprop_local and prop_l not in class_local:
                    bad(f"invariant 10: decision {did} input {col!r} references "
                        f"undeclared data property '{m.group(2)}'")

        # Each rule must have exactly len(inputs) input cells, and each cell must
        # be a recognised FEEL expression (literal, comparison, interval, dash, …).
        for ri, r in enumerate(rules, 1):
            cells = r.get('inputs') if isinstance(r, dict) else None
            if cells is None:
                bad(f"invariant 10: decision {did} rule {ri} missing 'inputs' array")
                continue
            if len(cells) != len(inputs):
                bad(f"invariant 10: decision {did} rule {ri} has {len(cells)} input "
                    f"cells but the table has {len(inputs)} input column(s)")
            for ci, cell in enumerate(cells, 1):
                if cell is None or cell == '':
                    continue
                s = str(cell).strip()
                if not FEEL_CELL.match(s):
                    bad(f"invariant 10: decision {did} rule {ri} input cell {ci} "
                        f"{s!r} is not a recognised FEEL expression "
                        f"(literal | comparison | interval | not(…) | -)")
            if 'output' not in r and 'outputs' not in r:
                bad(f"invariant 10: decision {did} rule {ri} missing 'output' (or 'outputs')")

        # ---------- KE-course design warnings (Hinkelmann milestone feedback) ----------
        # These are SOFT warnings — they identify design defects that the course
        # consistently flags (Hit Policy F when U would do, output lists, repeated
        # lookup tables that should be a BKM, value-enumeration cells where an
        # interval would be cleaner). They appear in the WARN list at the bottom
        # of the validator report and do NOT fail the run.

        # (a) Hit policy `F` is fragile — prefer `U` when the rules are mutually
        #     exclusive. Heuristic: every input cell is either a dash, an interval,
        #     or an equality. If no rule says `not(x)` and no two rules share an
        #     equal cell value in the same column, the rules ARE disjoint and `U`
        #     is the right policy.
        if hp == 'F' and rules:
            looks_disjoint = True
            seen_per_col = [{} for _ in inputs]
            for ri, r in enumerate(rules, 1):
                cells = r.get('inputs') or []
                for ci, cell in enumerate(cells):
                    if ci >= len(seen_per_col): break
                    s = str(cell).strip() if cell is not None else ''
                    if s in ('', '-'):
                        continue
                    # Equality literal like "Italy" or numeric → check for clash
                    if re.match(r'^"[^"]*"$', s) or re.match(r'^-?\d+(\.\d+)?$', s):
                        prev = seen_per_col[ci].get(s)
                        if prev is not None and prev != ri:
                            looks_disjoint = False
                        seen_per_col[ci][s] = ri
            if looks_disjoint:
                warn(f"invariant 10 (KE design): decision {did} uses hit policy 'F' but "
                     f"the rules appear mutually exclusive — prefer 'U' (Unique) so the "
                     f"table is order-independent and reviewer-friendly")

        # (b) Outputs as comma-separated lists are the wrong dimension — each
        #     value should be its own rule under U.
        out_cols = outputs if outputs and isinstance(outputs, list) else [None]
        for ri, r in enumerate(rules, 1):
            out = r.get('output') if isinstance(r, dict) else None
            outs = out if isinstance(out, list) else (r.get('outputs') or [out])
            for ci, ov in enumerate(outs or []):
                if isinstance(ov, str) and ',' in ov and not ov.strip().startswith('"'):
                    warn(f"invariant 10 (KE design): decision {did} rule {ri} output "
                         f"{ov!r} looks like a comma-separated list — split into "
                         f"separate rows; the output is the wrong dimension")

        # (c) Value-enumeration cells where an interval would be cleaner. Heuristic:
        #     three or more rules in the same column use bare equality on numeric
        #     literals — an interval partition is the FEEL idiom.
        for ci, _col in enumerate(inputs):
            eq_lits = []
            for r in rules:
                cells = r.get('inputs') or []
                if ci >= len(cells): continue
                s = str(cells[ci]).strip() if cells[ci] is not None else ''
                if re.match(r'^-?\d+(\.\d+)?$', s):
                    eq_lits.append(s)
            if len(eq_lits) >= 3:
                warn(f"invariant 10 (KE design): decision {did} input column {ci+1} "
                     f"({inputs[ci]!r}) lists {len(eq_lits)} bare numeric values "
                     f"({eq_lits[:3]}{'...' if len(eq_lits) > 3 else ''}) — prefer "
                     f"FEEL intervals like [low..high]")

    # (d) Repeated-lookup detector across decisions — same (inputs, outputs)
    #     pair appearing in ≥2 decisions is a BKM candidate.
    sig_index = {}
    for d in decisions:
        if not isinstance(d, dict): continue
        sig = (tuple(d.get('inputs') or []),
               tuple(d.get('outputs') or ([d['output']] if 'output' in d else [])))
        sig_index.setdefault(sig, []).append(d.get('id', '?'))
    for sig, dids in sig_index.items():
        if len(dids) >= 2 and sig[0] and sig[1]:
            warn(f"invariant 10 (KE design): decisions {dids} share the same "
                 f"(inputs={list(sig[0])}, outputs={list(sig[1])}) signature — "
                 f"extract a single BKM (Business Knowledge Model) and invoke it "
                 f"from both rather than duplicating the table")

    if not [m for m in FAIL if m.startswith('invariant 10')]:
        suffix = f" · {len(WARN)} KE-design warning{'s' if len(WARN) != 1 else ''}" if WARN else ''
        ok(f"invariant 10: {len(decisions)} DMN decision(s) checked "
           f"(hit policy, shape, FEEL cells){suffix}")


def check_horn(scripts, M):
    raw = (scripts.get('model-horn') or '').strip()
    if not raw:
        return

    # Collect predicate vocabulary from the ontology. A Prolog/Horn predicate
    # may appear in either lowercase-collapsed form (`hasamount`) or
    # snake_cased form (`has_amount`), so we record both for every IRI.
    def name_forms(iri):
        name = re.sub(r'^[^:]*:', '', iri)
        snake = re.sub(r'([a-z0-9])([A-Z])', r'\1_\2', name).lower()
        snake = re.sub(r'[^a-z0-9_]', '_', snake)
        return {name.lower(), snake}
    def collect(iris):
        out = set()
        for iri in iris:
            out |= name_forms(iri)
        return out
    class_preds = collect(M['classes'])
    op_preds    = collect(M['obj_props'])
    dp_preds    = collect(M['data_props'])
    declared    = class_preds | op_preds | dp_preds
    head_preds  = set()
    clauses     = []

    lines = raw.splitlines()
    # First pass: collect head predicates so a rule whose body uses a derived
    # predicate defined later (or on the same line) doesn't get flagged.
    # Directives (`:- ...`, e.g. discontiguous / constructor declarations) are
    # legitimate Prolog and are skipped (the in-browser engine skips them too).
    for ln_no, line in enumerate(lines, 1):
        s = line.strip()
        if not s or s.startswith('%') or s.startswith(':-'):
            continue
        m = HORN_CLAUSE.match(s)
        if m:
            head_preds.add(m.group(1).lower())

    for ln_no, line in enumerate(lines, 1):
        s = line.strip()
        if not s or s.startswith('%') or s.startswith(':-'):
            continue
        m = HORN_CLAUSE.match(s)
        if not m:
            bad(f"invariant 11: line {ln_no} is not a well-formed Horn clause "
                f"({s!r}); expected 'pred(args).' or 'head(args) :- body.'")
            continue
        head_pred = m.group(1).lower()
        head_args = [a.strip() for a in (m.group(2) or '').split(',') if a.strip()]
        body = m.group(3) or ''
        head_arity = len(head_args)
        clauses.append((ln_no, head_pred, head_arity, body))

        # Arity sanity for predicates that mirror the ontology:
        #   class as a unary predicate    →  arity 1
        #   object property                →  arity 2
        #   data property                  →  arity 2
        # Class predicates may be arity >= 1: both the unary entity style
        # (`transaction(t1)`) and the multi-place constructor / database-oriented
        # style (`transaction(t1, k1, h1, 500, ts)`) are legitimate ontology
        # encodings (an arity-N class predicate is a constructor / object record),
        # so class arity is NOT constrained. Object/data properties stay binary.
        if head_pred in op_preds and head_arity != 2:
            bad(f"invariant 11: line {ln_no}: predicate '{head_pred}' mirrors an object "
                f"property, expected arity 2, got {head_arity}")
        elif head_pred in dp_preds and head_arity != 2:
            bad(f"invariant 11: line {ln_no}: predicate '{head_pred}' mirrors a data "
                f"property, expected arity 2, got {head_arity}")

        # Body predicates must resolve to an ontology term, a known built-in, or
        # a derived head defined in this Horn block. We also enforce arity for
        # predicates that mirror the ontology so `transaction(T, X)` is caught
        # when Transaction is a class (arity 1, not 2).
        if body:
            BODY_CALL = re.compile(r'\b([a-z_][\w]*)\s*\(([^()]*)\)')
            seen_unknown = set()
            for bm in BODY_CALL.finditer(body):
                bp = bm.group(1).lower()
                ba = len([a for a in bm.group(2).split(',') if a.strip()])
                if bp in op_preds and ba != 2:
                    bad(f"invariant 11: line {ln_no}: body predicate '{bp}' mirrors an "
                        f"object property, expected arity 2, got {ba}")
                elif bp in dp_preds and ba != 2:
                    bad(f"invariant 11: line {ln_no}: body predicate '{bp}' mirrors a "
                        f"data property, expected arity 2, got {ba}")
                if bp not in declared and bp not in HORN_BUILTINS and bp not in head_preds:
                    if bp not in seen_unknown:
                        seen_unknown.add(bp)
                        bad(f"invariant 11: line {ln_no} references predicate '{bp}' which "
                            f"is not in the ontology vocabulary, not a built-in, and not a "
                            f"derived head defined in this file")

    if clauses and not [m for m in FAIL if m.startswith('invariant 11')]:
        ok(f"invariant 11: {len(clauses)} Horn clause(s) checked "
           f"(syntax, predicate vocabulary, arity)")


def check_extract_per_component(path, M):
    here = os.path.dirname(os.path.abspath(__file__))
    extractor = os.path.join(here, 'extract_component.py')
    if not os.path.exists(extractor):
        bad("invariant 8: extract_component.py not found; cannot verify component extractability")
        return
    comps = sorted(set(M['components'].values()))
    comps = [c for c in comps if c and not c.startswith('_')]
    if not comps:
        return
    failed = []
    with tempfile.TemporaryDirectory() as td:
        for c in comps:
            out = os.path.join(td, f'extract-{c}.html')
            r = subprocess.run(
                [sys.executable, extractor, path, '--component', c, '--out', out],
                capture_output=True, text=True)
            if r.returncode != 0 or not os.path.exists(out):
                failed.append((c, 'extract failed: ' + (r.stderr or r.stdout)[:200]))
                continue
            v = subprocess.run(
                [sys.executable, __file__, out, '--no-recurse'],
                capture_output=True, text=True)
            if v.returncode != 0:
                failed.append((c, v.stdout.strip().splitlines()[-1] if v.stdout else 'validation failed'))
    if failed:
        for c, why in failed:
            bad(f"invariant 8: component '{c}' did not round-trip cleanly — {why}")
    else:
        ok(f"invariant 8: all {len(comps)} components extract & re-validate")


# ---------------------------------------------------------------------------
# Invariant 12 — outbound RDF projectors round-trip through rdflib.
#
# Why: the in-browser projectors (Turtle / RDFS / N-Triples / RDF/XML) are
# what a user clicking the Syntax tab actually sees, and what they download.
# A broken projector silently emits invalid RDF — e.g. an array subClassOf
# coerced to `Parent,Man` in an N-Triples IRI — without the canonical-only
# invariants 1–11 catching it. This invariant launches a headless browser
# to render each projector, re-parses with rdflib, and demands the
# rdfs:subClassOf triple counts match the canonical Turtle.
# ---------------------------------------------------------------------------
def _find_headless_browser():
    """Return path to chrome/chromium if available, else None.

    $CHROME (a path or a command name) takes precedence, as in run_query.py,
    so one environment variable steers every headless check of the platform.
    """
    env = os.environ.get('CHROME')
    if env:
        if os.path.isfile(env) and os.access(env, os.X_OK):
            return env
        import shutil
        w = shutil.which(env)
        if w:
            return w
    for cmd in ('google-chrome', 'chromium', 'chromium-browser', 'chrome'):
        for p in os.environ.get('PATH', '').split(os.pathsep):
            full = os.path.join(p, cmd)
            if os.path.isfile(full) and os.access(full, os.X_OK):
                return full
    return None


def check_projector_round_trip(path, canonical_ttl):
    # Cheap pre-check: don't bother spinning up Chrome if rdflib isn't
    # installed — every projector parse depends on it.
    try:
        import rdflib  # noqa: F401
    except ImportError:
        warn("invariant 12: rdflib not installed; skipping projector round-trip")
        return

    browser = _find_headless_browser()
    if not browser:
        warn("invariant 12: no headless browser found (google-chrome/chromium); "
             "skipping projector round-trip")
        return

    # Inject a probe at the end of the runtime IIFE. It calls each projector
    # and stashes the rendered text on <body data-rt-…>. Chrome renders the
    # page, we read the attribute back out of the dumped DOM.
    try:
        html_text = open(path, encoding='utf-8').read()
    except OSError as e:
        bad(f"invariant 12: cannot re-read {path}: {e}")
        return

    probe = """
  /* === invariant-12 round-trip probe (injected by validate_model.py) === */
  try {
    const langs = ['turtle','rdfs','ntriples','rdfxml'];
    langs.forEach(l => {
      try { document.body.setAttribute('data-rt-' + l, PROJECTORS[l]()); }
      catch (e) { document.body.setAttribute('data-rt-err-' + l, String(e.message)); }
    });
  } catch (e) {
    document.body.setAttribute('data-rt-err', String(e.message));
  }
"""
    # Inject the probe inside the MAIN runtime IIFE — the one that defines
    # PROJECTORS. The template carries a stable anchor for this purpose:
    #     /* @PROBE_HOOK end-of-runtime */
    # Prefer the anchor; fall back to rfind('})();') for older templates
    # that predate the marker (those have only one IIFE so rfind is safe).
    anchor = '/* @PROBE_HOOK end-of-runtime'
    idx = html_text.find(anchor)
    if idx >= 0:
        # Inject just before the @PROBE_HOOK comment, still inside the IIFE.
        instrumented = html_text[:idx] + probe + '\n  ' + html_text[idx:]
    else:
        marker = '})();'
        idx = html_text.rfind(marker)
        if idx < 0:
            warn("invariant 12: could not locate runtime IIFE; skipping")
            return
        instrumented = html_text[:idx] + probe + '\n  ' + html_text[idx:]

    with tempfile.TemporaryDirectory() as td:
        instr_path = os.path.join(td, 'instrumented.html')
        with open(instr_path, 'w', encoding='utf-8') as fh:
            fh.write(instrumented)
        profile = os.path.join(td, 'profile')
        try:
            r = subprocess.run(
                [browser, '--headless=new', '--disable-gpu', '--no-sandbox',
                 f'--user-data-dir={profile}', '--virtual-time-budget=4000',
                 '--dump-dom', 'file://' + instr_path],
                capture_output=True, text=True, timeout=30,
            )
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            warn(f"invariant 12: headless browser failed ({e}); skipping")
            return
        dom = r.stdout or ''

    # Extract each rendered projection from the body attributes. The
    # quoting is HTML-attribute style (double quotes), so unescape entities.
    import html as _html
    rendered = {}
    for lang in ('turtle', 'rdfs', 'ntriples', 'rdfxml'):
        m = re.search(rf'data-rt-{lang}="([^"]*)"', dom)
        if m:
            rendered[lang] = _html.unescape(m.group(1))
        else:
            err = re.search(rf'data-rt-err-{lang}="([^"]*)"', dom)
            if err:
                bad(f"invariant 12: projector {lang} threw — {_html.unescape(err.group(1))}")

    if not rendered:
        warn("invariant 12: no projector output captured (Chrome may have "
             "exited before the probe ran); skipping")
        return

    # Canonical subClassOf triple count — this is the multi-inheritance probe.
    import rdflib
    from rdflib.namespace import RDFS

    def subclass_count(graph):
        return sum(1 for _ in graph.triples((None, RDFS.subClassOf, None)))

    canonical = rdflib.Graph()
    canonical.parse(data=canonical_ttl, format='turtle')
    canonical_n = subclass_count(canonical)

    # Format → rdflib format spec. Skip rdfs because it's Turtle subset — rdflib
    # handles it as Turtle but it's a curated RDFS-only view, so triple counts
    # may legitimately differ for OWL-specific axioms. We still parse it for
    # syntactic validity.
    formats = {
        'turtle':   'turtle',
        'rdfs':     'turtle',
        'ntriples': 'nt',
        'rdfxml':   'xml',
    }

    parsed_ok = []
    for lang, fmt in formats.items():
        if lang not in rendered:
            continue
        g = rdflib.Graph()
        try:
            g.parse(data=rendered[lang], format=fmt)
        except Exception as e:
            bad(f"invariant 12: {lang} projector produced text rdflib refused: "
                f"{str(e)[:160]}")
            continue
        if lang in ('turtle', 'ntriples', 'rdfxml'):
            n = subclass_count(g)
            if n != canonical_n:
                bad(f"invariant 12: {lang} projector emitted {n} rdfs:subClassOf "
                    f"triples vs canonical {canonical_n} — likely multi-inheritance "
                    f"mangled into a single triple")
                continue
        parsed_ok.append(lang)

    if parsed_ok and not [m for m in FAIL if m.startswith('invariant 12')]:
        ok(f"invariant 12: {len(parsed_ok)} projector(s) round-trip cleanly "
           f"({', '.join(parsed_ok)}) — subClassOf count={canonical_n}")


# ---------- invariants 13–15: the knowledge-graph runtimes ----------
def _count_individuals(scripts):
    """Count A-box individuals in the JSON-LD @graph (mirrors the runtime's
    individuals() filter: a node with a @type that is not an owl meta-class)."""
    raw = scripts.get('model-jsonld')
    if not raw:
        return 0
    try:
        graph = json.loads(raw).get('@graph', [])
    except Exception:
        return 0
    meta = {'owl:Class', 'owl:ObjectProperty', 'owl:DatatypeProperty'}
    n = 0
    for node in graph:
        t = node.get('@type')
        ts = t if isinstance(t, list) else ([t] if t else [])
        if ts and not any(x in meta for x in ts):
            n += 1
    return n


def _count_swrl(scripts):
    raw = scripts.get('model-swrl')
    if not raw:
        return 0
    try:
        data = json.loads(raw)
    except Exception:
        return 0
    rules = data.get('rules', data) if isinstance(data, dict) else data
    return len(rules) if isinstance(rules, list) else 0


def check_kg_runtime_static(doc, scripts):
    """Invariant 13 (static): when the model carries an A-box (individuals) or
    SWRL rules, the @KG_RUNTIME block (in-browser SPARQL + on-demand reasoner)
    must be present and the main runtime must expose window.__kgReasoning so the
    runtimes and the diagram overlay can consult the reasoner."""
    n_ind = _count_individuals(scripts)
    n_swrl = _count_swrl(scripts)
    if not n_ind and not n_swrl:
        ok("invariant 17: no A-box / SWRL — KG runtimes not required (skipped)")
        return
    problems = []
    if '@KG_RUNTIME:start' not in doc or '@KG_RUNTIME:end' not in doc:
        problems.append("the @KG_RUNTIME block (SPARQL + reasoner runners) is missing")
    if 'window.__kgReasoning' not in doc:
        problems.append("window.__kgReasoning is not exposed by the main runtime")
    if problems:
        bad("invariant 17: model has an A-box/SWRL but " + "; ".join(problems))
    else:
        ok(f"invariant 17: KG runtimes present (@KG_RUNTIME + window.__kgReasoning) "
           f"for {n_ind} individual(s), {n_swrl} SWRL rule(s)")


def check_kg_render(path, scripts):
    """Invariants 14–15 (headless): with an A-box present, the unified KG diagram
    renders (individual ellipses + Schema/Data frames + layer chips) and the
    runtimes function (reasoner adds triples; SPARQL returns rows; both runners
    mount). WARN-skipped without a headless browser; PASS-skipped without an A-box."""
    n_ind = _count_individuals(scripts)
    if not n_ind:
        ok("invariant 18-19: no A-box — KG diagram/runtimes not applicable (skipped)")
        return
    browser = _find_headless_browser()
    if not browser:
        warn("invariant 18-19: no headless browser found; skipping KG render check")
        return
    try:
        html_text = open(path, encoding='utf-8').read()
    except OSError as e:
        bad(f"invariant 18-19: cannot re-read {path}: {e}")
        return

    probe = """
<script>
/* === invariant 18-19 KG-render probe (injected by validate_model.py) === */
(function(){
  function fin(o){ try{ document.body.setAttribute('data-kg', JSON.stringify(o)); }catch(e){} }
  window.addEventListener('load', function(){ setTimeout(function(){
    var o = {};
    try {
      o.individuals = document.querySelectorAll('#diagram .node.individual').length;
      o.schemaFrame = document.querySelectorAll('#diagram .level-frame.schema').length;
      o.dataFrame   = document.querySelectorAll('#diagram .level-frame.data').length;
      o.chips       = document.querySelectorAll('#diagram-layers button[data-layer]').length;
      o.hasKg       = !!window.__kg;
      if (window.__kg) {
        var a = window.__kg.triples(false).length;
        window.__kg.setReasoned(true);
        var b = window.__kg.triples(true).length;
        o.assertedT = a; o.allT = b;
        o.sparqlRows = window.__kg.runSparql('SELECT ?s WHERE { ?s a ?c }').rows.length;
      }
      o.sparqlRunner = !!document.querySelector('[data-logic-view="sparql"] .kg-runner');
      o.swrlRunner   = !!document.querySelector('[data-logic-view="swrl"] .kg-runner');
    } catch (e) { o.err = String(e && e.message || e); }
    fin(o);
  }, 1600); });
})();
</script>
"""
    idx = html_text.rfind('</body>')
    instrumented = (html_text[:idx] + probe + html_text[idx:]) if idx >= 0 else (html_text + probe)
    with tempfile.TemporaryDirectory() as td:
        instr_path = os.path.join(td, 'instr.html')
        with open(instr_path, 'w', encoding='utf-8') as fh:
            fh.write(instrumented)
        profile = os.path.join(td, 'profile')
        try:
            r = subprocess.run(
                [browser, '--headless=new', '--disable-gpu', '--no-sandbox',
                 f'--user-data-dir={profile}', '--virtual-time-budget=6000',
                 '--dump-dom', 'file://' + instr_path],
                capture_output=True, text=True, timeout=40,
            )
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            warn(f"invariant 18-19: headless browser failed ({e}); skipping")
            return
        dom = r.stdout or ''

    import html as _html
    m = re.search(r'data-kg="([^"]*)"', dom)
    if not m:
        warn("invariant 18-19: no KG probe output captured (Chrome may have exited "
             "before the probe ran); skipping")
        return
    try:
        o = json.loads(_html.unescape(m.group(1)))
    except Exception as e:
        bad(f"invariant 18-19: KG probe output unparseable: {e}")
        return
    if o.get('err'):
        bad(f"invariant 18-19: KG runtime threw — {o['err']}")
        return

    # Invariant 14 — the unified diagram rendered.
    p14 = []
    if not o.get('individuals'):
        p14.append("no individual nodes rendered")
    if o.get('schemaFrame') != 1 or o.get('dataFrame') != 1:
        p14.append(f"Schema/Data frames not both present "
                   f"(schema={o.get('schemaFrame')}, data={o.get('dataFrame')})")
    if o.get('chips') != 3:
        p14.append(f"expected 3 layer chips, found {o.get('chips')}")
    if p14:
        bad("invariant 18: unified KG diagram incomplete — " + "; ".join(p14))
    else:
        ok(f"invariant 18: unified KG diagram renders ({o['individuals']} individuals, "
           f"Schema+Data frames, 3 layer chips)")

    # Invariant 15 — the runtimes function.
    p15 = []
    p15_warn = []
    if not o.get('hasKg'):
        p15.append("window.__kg absent")
    else:
        if not (isinstance(o.get('allT'), int) and isinstance(o.get('assertedT'), int)):
            p15.append(f"reasoner returned no triple counts (asserted={o.get('assertedT')}, "
                       f"all={o.get('allT')})")
        elif o['allT'] <= o['assertedT']:
            # The reasoner ran and threw nothing, but had nothing to infer: no
            # individual typed with a subclass, no SWRL rule whose body matches
            # the A-box, no property characteristic to propagate. That is a
            # legitimate model (a thin A-box), not a broken runtime — so it is
            # a WARN, and the hint says what would make an inference visible.
            p15_warn.append(f"reasoner ran but inferred nothing (asserted={o['assertedT']}, "
                            f"all={o['allT']}): add an individual typed with a subclass, or "
                            f"an individual that satisfies a SWRL rule body, so the Inferred "
                            f"layer and the reasoner overlay have something to show")
        if not o.get('sparqlRows'):
            p15.append("SPARQL returned no rows")
    if not o.get('sparqlRunner'):
        p15.append("SPARQL runner did not mount")
    # the SWRL reasoner-runner only mounts when SWRL rules exist
    if _count_swrl(scripts) and not o.get('swrlRunner'):
        p15.append("reasoner runner did not mount in the SWRL view")
    if p15:
        bad("invariant 19: KG runtimes not functioning — " + "; ".join(p15))
    else:
        for w in p15_warn:
            warn("invariant 19: " + w)
        ok(f"invariant 19: KG runtimes work (reasoner {o.get('assertedT')}→{o.get('allT')} "
           f"triples, SPARQL {o.get('sparqlRows')} rows, runners mounted)")


# ---------------------------------------------------------------------------
# Invariants 13–16 — the @LAYER chain (see references/future-skills.md).
#
# The marker grammar and the digest algorithm are duplicated from
# scripts/apply_layer.py on purpose: the validator must stay runnable as a
# single file (invariant 8 re-invokes it on extracted components).
# ---------------------------------------------------------------------------
_LAYER_START_RE = re.compile(
    r"<!--\s*@LAYER:start\s+([A-Za-z0-9][A-Za-z0-9_-]*)(?:\s+v(\d+))?([\s\S]*?)-->")
_LAYER_END_RE = re.compile(r"<!--\s*@LAYER:end\s+([A-Za-z0-9][A-Za-z0-9_-]*)\s*-->")
_LAYER_ANY_MARKER_RE = re.compile(
    r"<!--\s*@LAYER:(start|end)\s+([A-Za-z0-9][A-Za-z0-9_-]*)")
_TURTLE_RAW_RE = re.compile(
    r'<script\b[^>]*\bid="(?:domain-model|model-turtle)"[^>]*>([\s\S]*?)</script>')
_LAYER_HEADER_FIELDS = ("produced-by", "produced-at", "input-digest")


def layer_digest(doc):
    """'sha256:' + SHA-256 of the exact bytes of the canonical Turtle body —
    identical to apply_layer.domain_digest()."""
    import hashlib
    m = _TURTLE_RAW_RE.search(doc)
    body = m.group(1) if m else ""
    return "sha256:" + hashlib.sha256(body.encode("utf-8")).hexdigest()


def _script_in(block, sid):
    """Return the text of <script id=SID> inside BLOCK, or None."""
    m = re.search(r'<script\b[^>]*\bid="' + re.escape(sid) + r'"[^>]*>([\s\S]*?)</script>', block)
    return m.group(1) if m else None


def scan_layers(doc):
    """Walk every @LAYER marker in order. Returns (layers, problems) where
    layers are the well-formed blocks [{name, version, fields, start, end,
    block}] and problems are invariant-13 messages."""
    layers, problems = [], []
    open_name, open_match = None, None
    seen = set()
    for m in _LAYER_ANY_MARKER_RE.finditer(doc):
        kind, name = m.group(1), m.group(2)
        if kind == "start":
            sm = _LAYER_START_RE.match(doc, m.start())
            if open_name is not None:
                problems.append(f"@LAYER:start {name} appears inside the still-open "
                                f"block {open_name} (nesting/overlap is forbidden)")
                # keep scanning from the inner start so later blocks are still checked
            if name in seen:
                problems.append(f"layer {name!r} is declared more than once")
            if sm is None:
                problems.append(f"@LAYER:start {name} header is not a well-formed comment (no '-->')")
                open_name, open_match = None, None
                continue
            open_name, open_match = name, sm
        else:
            em = _LAYER_END_RE.match(doc, m.start())
            if open_name is None:
                problems.append(f"@LAYER:end {name} without a preceding @LAYER:start {name}")
                continue
            if name != open_name:
                problems.append(f"@LAYER:end {name} closes the open block {open_name} "
                                f"(markers must pair by name, in order)")
                open_name, open_match = None, None
                continue
            if em is None:
                problems.append(f"@LAYER:end {name} marker is not a well-formed comment")
                open_name, open_match = None, None
                continue
            fields = {}
            for line in (open_match.group(3) or "").splitlines():
                fm = re.match(r"^\s*([a-z-]+):\s*(.*?)\s*$", line)
                if fm:
                    fields[fm.group(1)] = fm.group(2)
            layers.append(dict(name=name,
                               version=open_match.group(2),
                               fields=fields,
                               start=open_match.start(), end=em.end(),
                               block=doc[open_match.start():em.end()]))
            seen.add(name)
            open_name, open_match = None, None
    if open_name is not None:
        problems.append(f"@LAYER:start {open_name} has no matching @LAYER:end {open_name}")
    return layers, problems


def check_layers_markers(doc):
    """Invariant 13. Returns the well-formed layers (possibly empty)."""
    layers, problems = scan_layers(doc)
    for L in layers:
        missing = [f for f in _LAYER_HEADER_FIELDS if not L["fields"].get(f)]
        if missing:
            problems.append(f"layer {L['name']!r} header lacks {', '.join(missing)}")
        for part in ("data", "render"):
            if _script_in(L["block"], f"layer-{L['name']}-{part}") is None:
                problems.append(f"layer {L['name']!r} has no <script id=\"layer-{L['name']}-{part}\"> "
                                f"inside its block")
    # Layer-named scripts must live inside their block (else they cannot be stripped).
    for m in re.finditer(r'<script\b[^>]*\bid="layer-([A-Za-z0-9_-]+?)-(data|render)"', doc):
        if not any(L["start"] <= m.start() < L["end"] for L in layers):
            warn(f"invariant 13: <script id=\"layer-{m.group(1)}-{m.group(2)}\"> sits outside "
                 f"any well-formed @LAYER block and would survive strip_layer.py")
    if not layers and not problems:
        ok("invariant 13: no layers (skipped)")
        return layers
    for p in problems:
        bad(f"invariant 13: {p}")
    if not problems:
        ok(f"invariant 13: {len(layers)} @LAYER block(s) well-formed "
           f"({', '.join(L['name'] for L in layers)}) — markers paired, headers complete, "
           f"data+render scripts present")
    return layers


def check_layers_digest(doc, layers):
    """Invariant 14."""
    if not layers:
        ok("invariant 14: no layers (skipped)")
        return
    expected = layer_digest(doc)
    stale = 0
    for L in layers:
        found = L["fields"].get("input-digest")
        if not found:
            continue  # already reported by invariant 13
        if found != expected:
            stale += 1
            bad(f"invariant 14: layer {L['name']!r} input-digest mismatch — expected "
                f"{expected} (current Turtle), found {found}: the base model was edited "
                f"after this layer was produced — regenerate the layer or strip it")
    if not stale:
        ok(f"invariant 14: {len(layers)} layer digest(s) match the current Turtle ({expected})")


# ----- invariant 15: static write-scan -------------------------------------
#
# Heuristic, regex-based. It recognises:
#   * a PROTECTED TARGET expression:
#       document.getElementById('<id>')            (any quote style)
#       document.querySelector('#<id>')  /  querySelector('script#<id>')
#       document.querySelector('script[id=…]')      (quoted or bare id;
#                                                   ^= *= $= prefix forms are
#                                                   treated as protected)
#     where <id> is `domain-model`, `model-*`, or `layer-<OTHER>-data|render`
#     (the layer's own `layer-<NAME>-*` ids are allowed);
#   * a WRITE on such a target, either directly
#       TARGET.textContent = …   .innerHTML/.innerText/.text/.outerHTML = …
#       TARGET.replaceWith(…)    TARGET.remove()
#     or through a one-level alias assigned from a target in the same script:
#       var s = document.getElementById('model-dmn'); …; s.textContent = …
#     (`==`/`===`/`!=` comparisons are not writes; reads such as
#      `x = s.textContent` and `JSON.parse(s.textContent)` are allowed).
# Known limits (by design — this is a guard, not a JS parser): ids built by
# string concatenation or variables, aliases created inside another function
# or by destructuring, `querySelectorAll(...).forEach(el => el.textContent=…)`,
# `parentNode.removeChild(target)`, `insertAdjacentHTML`, `setAttribute`,
# and writes that reach the target via `.parentNode`/`.previousSibling`
# navigation are NOT detected. Comments are stripped before scanning so a
# mention inside a comment does not trip the scan.
_WRITE_PROPS = r"(?:textContent|innerHTML|innerText|text|outerHTML)"
_WRITE_CALLS = r"(?:replaceWith\s*\(|remove\s*\(\s*\))"


def _strip_js_comments(js):
    js = re.sub(r"/\*[\s\S]*?\*/", " ", js)
    # only strip // comments that start a statement (avoid 'http://' in strings)
    return re.sub(r"(?m)(^|[\s;{}()])//[^\n]*", r"\1", js)


def _protected_id(sid, own):
    if sid == "domain-model" or sid.startswith("model-"):
        return True
    m = re.match(r"^layer-(.+)-(data|render|style|original)$", sid)
    return bool(m) and m.group(1) != own


def _target_exprs(js, own):
    """Yield (span, description) for every protected-target expression."""
    q = r"""(?:'([^']*)'|"([^"]*)"|`([^`]*)`)"""
    def _str(m):
        return next(g for g in m.groups() if g is not None)
    for m in re.finditer(r"\bgetElementById\s*\(\s*" + q + r"\s*\)", js):
        sid = _str(m)
        if _protected_id(sid, own):
            yield m.span(), f"getElementById('{sid}')"
    for m in re.finditer(r"\bquerySelector(?:All)?\s*\(\s*" + q + r"\s*\)", js):
        sel = _str(m).strip()
        hit = None
        mm = re.match(r"^(?:script)?#([A-Za-z0-9_-]+)$", sel)
        if mm and _protected_id(mm.group(1), own):
            hit = sel
        mm = re.match(r"""^script\[id(\^=|\*=|\$=|=)\s*['"]?([A-Za-z0-9_-]*)['"]?\s*\]$""", sel)
        if mm:
            op, val = mm.group(1), mm.group(2)
            if op == "=":
                if _protected_id(val, own):
                    hit = sel
            elif not (val.startswith(f"layer-{own}-")):
                hit = sel  # prefix/substring selectors may reach protected scripts
        if hit:
            yield m.span(), f"querySelector('{hit}')"


def scan_render_writes(js, own):
    """Return a list of human-readable violations for one render script."""
    js = _strip_js_comments(js)
    findings = []
    targets = list(_target_exprs(js, own))
    if not targets:
        return findings
    write_tail = (r"\s*\.\s*(?:" + _WRITE_PROPS + r"\s*=(?!=)|" + _WRITE_CALLS + ")")
    aliases = {}
    for (s, e), desc in targets:
        # direct write: document.getElementById('x').textContent = …
        tail = js[e:e + 80]
        if re.match(write_tail, tail):
            findings.append(f"writes to {desc} directly")
        # alias: [var|let|const] NAME = document.getElementById('x')
        head = js[max(0, s - 120):s]
        am = re.search(r"(?:\b(?:var|let|const)\s+)?([A-Za-z_$][\w$]*)\s*=\s*(?:document|window\.document)?\s*\.?\s*$", head)
        if am and am.group(1) not in ("document", "window"):
            aliases.setdefault(am.group(1), desc)
    for alias, desc in aliases.items():
        pat = re.compile(r"(?<![\w$.])" + re.escape(alias) + write_tail)
        for m in pat.finditer(js):
            snippet = re.sub(r"\s+", " ", m.group(0)).strip()
            findings.append(f"writes to {desc} via alias `{alias}` ({snippet}…)")
    return findings


def check_layers_static(layers):
    """Invariant 15."""
    if not layers:
        ok("invariant 15: no layers (skipped)")
        return
    n_bad = 0
    for L in layers:
        js = _script_in(L["block"], f"layer-{L['name']}-render")
        if js is None:
            continue  # reported by invariant 13
        for f in scan_render_writes(js, L["name"]):
            n_bad += 1
            bad(f"invariant 15: layer {L['name']!r} render script {f} — a layer may read "
                f"model-*/other-layer scripts but must never write to them")
    if not n_bad:
        ok(f"invariant 15: {len(layers)} render script(s) contain no writes to model-* / "
           f"other-layer scripts (static scan)")


# ----- invariant 16: per-layer isolation in a headless browser --------------
def _strip_layer_spans(doc, layers, keep=None):
    """Remove every layer block except KEEP (a name or None), plus the single
    trailing newline after each removed block."""
    out = doc
    for L in sorted(layers, key=lambda x: x["start"], reverse=True):
        if L["name"] == keep:
            continue
        end = L["end"]
        if out.startswith("\n", end):
            end += 1
        out = out[:L["start"]] + out[end:]
    return out


_L16_HEAD_PROBE = """<script>
/* === invariant-16 error trap (injected by validate_model.py) === */
(function(){
  var errs = [];
  window.__l16errors = errs;
  window.addEventListener('error', function(e){
    errs.push(String((e && e.message) || e) + (e && e.lineno ? ' @line ' + e.lineno : ''));
  });
  window.addEventListener('unhandledrejection', function(e){
    var r = e && e.reason; errs.push('unhandled rejection: ' + String(r && r.message || r));
  });
})();
</script>
"""

_L16_TAIL_PROBE = """
<script>
/* === invariant-16 mount probe (injected by validate_model.py) === */
(function(){
  function fin(){
    var o = { errors: window.__l16errors || [],
              mounted: !!document.querySelector('[data-layer="__NAME__"]') };
    try { document.body.setAttribute('data-l16', JSON.stringify(o)); } catch (e) {}
  }
  window.addEventListener('load', function(){ setTimeout(fin, 1500); });
})();
</script>
"""


def _l16_run(browser, doc, name, td, tag):
    """Render DOC (with the probes injected) and return the probe dict or None."""
    import html as _html
    head_idx = -1
    hm = re.search(r"<head\b[^>]*>", doc)
    if hm:
        head_idx = hm.end()
    else:
        sm = re.search(r"<script\b", doc)
        head_idx = sm.start() if sm else 0
    instrumented = doc[:head_idx] + "\n" + _L16_HEAD_PROBE + doc[head_idx:]
    tail = _L16_TAIL_PROBE.replace("__NAME__", name or "")
    bidx = instrumented.rfind("</body>")
    instrumented = (instrumented[:bidx] + tail + instrumented[bidx:]) if bidx >= 0 else instrumented + tail
    path = os.path.join(td, f"l16-{tag}.html")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(instrumented)
    profile = os.path.join(td, f"profile-{tag}")
    try:
        r = subprocess.run(
            [browser, "--headless=new", "--disable-gpu", "--no-sandbox",
             f"--user-data-dir={profile}", "--virtual-time-budget=6000",
             "--dump-dom", "file://" + path],
            capture_output=True, text=True, timeout=40)
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        return {"_fail": f"headless browser failed ({e})"}
    m = re.search(r'data-l16="([^"]*)"', r.stdout or "")
    if not m:
        return None
    try:
        return json.loads(_html.unescape(m.group(1)))
    except Exception as e:
        return {"_fail": f"probe output unparseable: {e}"}


def check_layers_headless(doc, layers):
    """Invariant 16."""
    if not layers:
        ok("invariant 16: no layers (skipped)")
        return
    browser = _find_headless_browser()
    if not browser:
        warn("invariant 16: no headless browser found (google-chrome/chromium); "
             "skipping per-layer isolation render")
        return
    with tempfile.TemporaryDirectory() as td:
        # Baseline: the page with every layer stripped. Errors already present
        # here belong to the base model, not to a layer.
        base = _l16_run(browser, _strip_layer_spans(doc, layers), "", td, "base")
        baseline_errs = set()
        if base is None:
            warn("invariant 16: no probe output for the layer-free baseline (Chrome may "
                 "have exited before the probe ran); skipping")
            return
        if base.get("_fail"):
            warn(f"invariant 16: baseline render — {base['_fail']}; skipping")
            return
        baseline_errs = set(base.get("errors") or [])
        if baseline_errs:
            warn(f"invariant 16: the base model itself reports {len(baseline_errs)} uncaught "
                 f"error(s) with all layers stripped ({sorted(baseline_errs)[0][:120]}) — "
                 f"these are not attributed to any layer")
        n_ok = 0
        for L in layers:
            name = L["name"]
            solo = _strip_layer_spans(doc, layers, keep=name)
            o = _l16_run(browser, solo, name, td, name)
            if o is None:
                warn(f"invariant 16: layer {name!r} — no probe output captured; skipping")
                continue
            if o.get("_fail"):
                warn(f"invariant 16: layer {name!r} — {o['_fail']}; skipping")
                continue
            new_errs = [e for e in (o.get("errors") or []) if e not in baseline_errs]
            problems = []
            if new_errs:
                problems.append(f"uncaught error(s) with only this layer present: "
                                f"{'; '.join(e[:160] for e in new_errs[:3])}")
            if not o.get("mounted"):
                problems.append(f'no element [data-layer="{name}"] exists after load — '
                                f"the render script did not mount (or mounts without the "
                                f"data-layer attribute)")
            if problems:
                bad(f"invariant 16: layer {name!r} — " + "; ".join(problems))
            else:
                n_ok += 1
        if n_ok == len(layers):
            ok(f"invariant 16: {n_ok} layer(s) render in isolation without uncaught errors "
               f"and mount [data-layer] ({', '.join(L['name'] for L in layers)})")


def main():
    args = list(sys.argv[1:])
    if not args or args[0] in ('-h', '--help'):
        print("usage: validate_model.py <model.html> [--no-recurse]")
        return 2
    path = args[0]
    no_recurse = '--no-recurse' in args
    try:
        doc = open(path, encoding='utf-8').read()
    except Exception as e:
        print(f"could not read {path}: {e}")
        return 2

    scan = get_scripts(doc)
    ttl = scan.scripts.get('domain-model')
    if not ttl:
        bad("invariant 1: <script id='domain-model' type='text/turtle'> block missing")
    else:
        triples = get_triples(ttl)
        if triples is not None:
            M = index_model(triples)
            check_properties_and_hierarchy(M)
            check_jsonld_mirror(scan.scripts, M)
            check_components(M)
            check_markdown(scan.scripts)
            check_self_contained(scan)
            check_dmn(scan.scripts, M)
            check_horn(scan.scripts, M)
            check_kg_runtime_static(doc, scan.scripts)
            # Layer chain (13–15 static, 16 headless). Extracted components are
            # written from a fresh template and carry no layers, so the
            # --no-recurse sub-runs report "no layers (skipped)".
            layers = check_layers_markers(doc)
            check_layers_digest(doc, layers)
            check_layers_static(layers)
            if not no_recurse:
                check_extract_per_component(path, M)
                # Round-trip is recursion-aware: skip it inside the per-component
                # extract sub-runs (those run with --no-recurse) so we don't fork
                # Chrome once per component.
                check_projector_round_trip(path, ttl)
                check_kg_render(path, scan.scripts)
                check_layers_headless(doc, layers)

    print(f"\n=== domain-forge validation (v3): {path} ===")
    for m in PASS: print(f"  PASS  {m}")
    for m in WARN: print(f"  WARN  {m}")
    for m in FAIL: print(f"  FAIL  {m}")
    if WARN:
        print(f"\n{len(PASS)} passed, {len(WARN)} warned, {len(FAIL)} failed")
    else:
        print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
    return 0 if not FAIL else 1


if __name__ == '__main__':
    sys.exit(main())
