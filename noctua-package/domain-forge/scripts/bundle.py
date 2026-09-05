#!/usr/bin/env python3
"""
bundle.py — produce the KE-course submission bundle from one composed model.html.

The Knowledge Engineering course expects a per-milestone submission containing:

    model.ttl    — the canonical Turtle ontology
    model.dmn    — the DMN 1.5 XML for decision tables
    model.pl     — the Prolog projection of the T-box (+ optional Horn rules)
    report.pdf   — a written report (NOT produced here — see below)

This script reads a composed model.html (produced by compose_model.py or by
domain-forge directly) and writes the three machine-readable artifacts plus
a MANIFEST.md. Optionally zips the result for one-click submission.

Why a script and not a "Download all" button: course submissions go through
a learning-management system, the grader unzips and grades each file on its
own. A bundle that materialises the artifacts on disk is the unit of work the
workflow actually needs.

The report.pdf is delegated to the /document-project skill.

  Rationale: report.pdf must be a *narrative document* explaining the model —
  motivated prose, generated diagrams, chapter structure — not a print of the
  HTML page. /document-project is the dedicated skill for that work: it
  authors LaTeX one chapter at a time, generates PlantUML/TikZ figures, and
  compiles to a real PDF. Domain-forge owns the model; document-project owns
  the documentation. We don't mix those concerns.

  After running bundle.py, invoke /document-project against the same project
  directory; it will pick up MANIFEST.md to know which artifacts feed the
  technical chapters.
"""

from __future__ import annotations

import argparse
import html
import json
import os
import re
import sys
import zipfile
from typing import Any


# ---------------------------------------------------------------------------
# 1. Read the composed HTML — strip canonical scripts and metadata
# ---------------------------------------------------------------------------

# Match only the canonical layer: <script id="..." at the start of the tag,
# never `<script type="..." id="..."` (the runtime). The canonical scripts in
# the template all use the form `<script id="..." type="...">` — id comes
# first. We also keep the FIRST occurrence per id, because the runtime body
# contains literal source code like `<script id="model-dmn">` inside its
# template strings, which a greedier regex would otherwise stash into the dict.
SCRIPT_RE = re.compile(
    r'<script\s+id="([^"]+)"[^>]*>([\s\S]*?)</script>', re.I
)


def read_scripts(html_text: str) -> dict[str, str]:
    """Return id → text body for every canonical <script id="..."> block."""
    out: dict[str, str] = {}
    for m in SCRIPT_RE.finditer(html_text):
        sid = m.group(1)
        if sid in out:
            continue
        out[sid] = m.group(2).strip()
    return out


def derive_base_iri(jsonld: dict) -> str:
    """The base IRI lives in the JSON-LD @context.ex prefix."""
    ctx = jsonld.get('@context') or {}
    if isinstance(ctx, dict) and isinstance(ctx.get('ex'), str):
        return ctx['ex']
    return 'http://example.org/PROJECT#'


def derive_model_name(markdown_src: str, html_text: str) -> str:
    """Pick a model name: first '# Heading' in markdown, else <title>, else 'DomainForgeModel'."""
    m = re.search(r'^\s*#\s+(.+?)\s*$', markdown_src, re.M)
    if m:
        return m.group(1).strip()
    m = re.search(r'<title>([^<]+)</title>', html_text, re.I)
    if m:
        return m.group(1).strip()
    return 'DomainForgeModel'


def slug(name: str) -> str:
    """Make a name safe as an XML id / Prolog atom."""
    return re.sub(r'[^A-Za-z0-9_]+', '_', name).strip('_') or 'X'


# ---------------------------------------------------------------------------
# 2. Helpers shared with the template's JSON-LD projectors (ported to Python)
# ---------------------------------------------------------------------------

def local_name(iri: Any) -> str:
    """`ex:Person` → `Person`. `http://x/Person` → `Person`. Mirrors localName()."""
    s = '' if iri is None else str(iri)
    if ':' in s and not s.startswith('http'):
        return s.split(':', 1)[1]
    if '#' in s:
        return s.rsplit('#', 1)[1]
    if '/' in s:
        return s.rsplit('/', 1)[1]
    return s


def pl_name(iri: Any) -> str:
    """Snake-case so it's a valid unquoted Prolog atom (matches plName() in template)."""
    s = local_name(iri)
    s = re.sub(r'([a-z0-9])([A-Z])', r'\1_\2', s).lower()
    return re.sub(r'[^a-z0-9_]', '_', s) or 'x'


def as_array(v):
    if v is None:
        return []
    if isinstance(v, list):
        return v
    return [v]


def is_type(node: dict, t: str) -> bool:
    return t in as_array(node.get('@type'))


def prop_domain(p: dict):
    return p.get('rdfs:domain') or p.get('domain')


def prop_range(p: dict):
    return p.get('rdfs:range') or p.get('range')


def class_component(c: dict):
    return c.get('component') or c.get('ex:component')


def is_value_object(c: dict) -> bool:
    v = c.get('valueObject') or c.get('ex:valueObject')
    return v in (True, 'true', 'True', 1, '1')


def model_by_entity(graph: list[dict]) -> list[dict]:
    """Group classes + individuals by component (sorted), each with its props.

    Mirrors the template's `modelByEntity()` so projector output matches what
    the in-browser Syntax tab produces — same ordering, same grouping.
    """
    classes = [n for n in graph if is_type(n, 'owl:Class') or is_type(n, 'rdfs:Class')]
    obj_props = [n for n in graph if is_type(n, 'owl:ObjectProperty')]
    data_props = [n for n in graph if is_type(n, 'owl:DatatypeProperty')]
    individuals = [n for n in graph if is_type(n, 'owl:NamedIndividual')]

    by_comp: dict[str, dict] = {}
    for c in classes:
        comp = class_component(c) or 'core'
        by_comp.setdefault(comp, {'classes': [], 'individuals': []})['classes'].append(c)
    for i in individuals:
        # Individual's component = its declared type's component, else its own, else 'core'.
        comp = i.get('component') or i.get('ex:component')
        if not comp:
            for t in as_array(i.get('@type')):
                for c in classes:
                    if c.get('@id') == t:
                        comp = class_component(c)
                        break
                if comp:
                    break
        comp = comp or 'core'
        by_comp.setdefault(comp, {'classes': [], 'individuals': []})['individuals'].append(i)

    out = []
    for name in sorted(by_comp):
        comp = by_comp[name]
        if not comp['classes'] and not comp['individuals']:
            continue
        entries = []
        for c in comp['classes']:
            entries.append({
                'kind': 'class', 'node': c,
                'dataProps': [p for p in data_props if prop_domain(p) == c['@id']],
                'objProps':  [p for p in obj_props  if prop_domain(p) == c['@id']],
            })
        for i in comp['individuals']:
            entries.append({'kind': 'individual', 'node': i})
        out.append({'component': name, 'entries': entries})
    return out


def comp_banner(name: str, marker: str = '%') -> list[str]:
    bar = '═' * 56
    return [f'{marker} {bar}', f'{marker} Component: {name}', f'{marker} {bar}']


def entity_header(name: str, marker: str = '%') -> str:
    return f'{marker} ── {name} ──'


# ---------------------------------------------------------------------------
# 3. Prolog projector — port of prologSrc(false) in template.html
# ---------------------------------------------------------------------------

def prolog_src(jsonld: dict, horn: str) -> str:
    """Mirror of the template's prologSrc(datalog=false), with Horn rules appended."""
    lines = [
        '% Prolog projection of the domain-forge model.',
        '% Generated by scripts/bundle.py — do not hand-edit; regenerate from model.html.',
        '%',
        '% Conventions:',
        '%   class(C)               — every class is a unary predicate (declared :- dynamic).',
        '%   prop(X, Y)             — every property is a binary predicate.',
        '%   Super(X) :- Sub(X).    — subclass hierarchy as a rule.',
        '%   component(C, comp).    — schema metadata.',
        '%   value_object(C).       — DDD value-object marker.',
        '%',
        '% Example Horn rule against this vocabulary:',
        '%   high_value(T) :- transaction(T), has_amount(T, A), A >= 10000.',
    ]
    graph = jsonld.get('@graph') or []
    for block in model_by_entity(graph):
        lines.append('')
        lines.extend(comp_banner(block['component'], '%'))
        for entry in block['entries']:
            lines.append('')
            if entry['kind'] == 'class':
                c = entry['node']
                cln = pl_name(c['@id'])
                lines.append(entity_header(local_name(c['@id']), '%'))
                lines.append(f':- dynamic {cln}/1.')
                if class_component(c):
                    comp = re.sub(r'[^a-z0-9_]', '_', str(class_component(c)).lower())
                    lines.append(f'component({cln}, {comp}).')
                if is_value_object(c):
                    lines.append(f'value_object({cln}).')
                sup_raw = c.get('subClassOf') or c.get('rdfs:subClassOf')
                # subClassOf can be a single IRI string or a list (multi-inheritance).
                # Emit one rule per parent so the Prolog reader doesn't see
                # bracketed garbage like `['ex:Parent', 'ex:Man'](X)`.
                for sup in as_array(sup_raw):
                    if not isinstance(sup, str):
                        continue
                    sup_n = pl_name(sup)
                    lines.append(
                        f'{sup_n}(X) :- {cln}(X).   % every {local_name(c["@id"])} is a {local_name(sup)}'
                    )
                if entry['dataProps']:
                    lines.append(f'% Data properties on {cln}:')
                    for p in entry['dataProps']:
                        pn = pl_name(p['@id'])
                        rng = prop_range(p)
                        # range may be a list (multi-typed); take the first IRI.
                        if isinstance(rng, list):
                            rng = next((x for x in rng if isinstance(x, str)), None)
                        rn = re.sub(r'[^a-z0-9_]', '_', local_name(rng or 'literal').lower())
                        lines.append(f':- dynamic {pn}/2.   % {pn}(X, V) where {cln}(X), V :: {rn}')
                if entry['objProps']:
                    lines.append(f'% Object properties from {cln}:')
                    for p in entry['objProps']:
                        pn = pl_name(p['@id'])
                        rng = prop_range(p)
                        if isinstance(rng, list):
                            rng = next((x for x in rng if isinstance(x, str)), None)
                        rn = pl_name(rng or 'thing')
                        lines.append(f':- dynamic {pn}/2.   % {pn}(X, Y) where {cln}(X), {rn}(Y)')
            else:
                i = entry['node']
                iln = pl_name(i['@id'])
                lines.append(entity_header(local_name(i['@id']) + ' (individual)', '%'))
                for t in as_array(i.get('@type')):
                    lines.append(f'{pl_name(t)}({iln}).')

    if horn.strip():
        lines.append('')
        lines.append('% ══════════════════════════════════════════════════════════')
        lines.append('% Horn rules and ground facts (from <script id="model-horn">)')
        lines.append('% ══════════════════════════════════════════════════════════')
        lines.append(horn.strip())

    return '\n'.join(lines) + '\n'


# ---------------------------------------------------------------------------
# 4. DMN XML projector — port of dmnxmlSrc() in template.html
# ---------------------------------------------------------------------------

DMN_HIT_POLICY = {
    'U': 'UNIQUE', 'A': 'ANY', 'P': 'PRIORITY', 'F': 'FIRST',
    'C': 'COLLECT', 'R': 'RULE ORDER', 'O': 'OUTPUT ORDER',
    'C+': 'COLLECT', 'C<': 'COLLECT', 'C>': 'COLLECT', 'C#': 'COLLECT',
}
DMN_AGGREGATION = {'C+': 'SUM', 'C<': 'MIN', 'C>': 'MAX', 'C#': 'COUNT'}


def feel_type_for(col: str) -> str:
    """Mirror of feelTypeFor() in the template — best-effort FEEL typeRef from naming."""
    if re.search(r'\.has(Amount|Age|Price|Score|Quantity|Year|Number|Count|Total|Cost|Fee|Rate|Balance|Limit|Tax|Discount|Weight|Length|Height|Width|Size|Duration|Days|Hours|Minutes)\b',
                 col, re.I):
        return 'number'
    if re.search(r'\.is(Active|Enabled|Allowed|Required|Valid|Eligible|Verified|Approved)\b', col, re.I):
        return 'boolean'
    if re.search(r'\.has(Country|Name|Sku|Type|Status|Category|Label|Code|Email|Phone|Address|City|Region|Currency|Description)\b',
                 col, re.I):
        return 'string'
    if re.search(r'\.has(Date|Created|Updated|Modified|Expires|Issued|StartDate|EndDate)\b', col, re.I):
        return 'date'
    return 'string'


def infer_output_type(decisions: list[dict]) -> str:
    samples = []
    for d in decisions:
        for r in d.get('rules', []):
            o = r.get('output')
            if isinstance(o, list):
                samples.extend(o)
            else:
                samples.append(o)
    if not samples:
        return 'string'
    for s in samples:
        if s is None:
            continue
        if not re.match(r'^-?\d+(\.\d+)?$', str(s).strip()):
            return 'string'
    return 'number'


def dmn_xml(dmn_json: dict, model_name: str, base_ns: str) -> str:
    """Mirror of dmnxmlSrc() in the template — same XML, same id scheme."""
    decisions = dmn_json.get('decisions') or []
    safe_name = re.sub(r'[^A-Za-z0-9_]+', '', model_name)
    if not decisions:
        return ('<?xml version="1.0" encoding="UTF-8"?>\n'
                '<!-- No DMN decisions in this model. -->\n'
                '<definitions xmlns="https://www.omg.org/spec/DMN/20191111/MODEL/" '
                f'id="defs_empty" name="{html.escape(safe_name)}" '
                f'namespace="{html.escape(base_ns)}"/>\n')
    out_type = infer_output_type(decisions)
    L: list[str] = []
    L.append('<?xml version="1.0" encoding="UTF-8"?>')
    L.append('<definitions xmlns="https://www.omg.org/spec/DMN/20191111/MODEL/"')
    L.append('             xmlns:dmndi="https://www.omg.org/spec/DMN/20191111/DMNDI/"')
    L.append('             xmlns:dc="http://www.omg.org/spec/DMN/20180521/DC/"')
    L.append('             xmlns:di="http://www.omg.org/spec/DMN/20180521/DI/"')
    L.append('             xmlns:feel="https://www.omg.org/spec/DMN/20191111/FEEL/"')
    L.append(f'             id="defs_{html.escape(safe_name)}"')
    L.append(f'             name="{html.escape(safe_name)}"')
    L.append(f'             namespace="{html.escape(base_ns)}"')
    L.append('             exporter="domain-forge" exporterVersion="3.1">')

    all_inputs: list[str] = []
    seen = set()
    for d in decisions:
        for c in d.get('inputs') or []:
            if c not in seen:
                seen.add(c)
                all_inputs.append(c)
    for idx, col in enumerate(all_inputs):
        safe = f'input_{idx+1}_{re.sub(r"[^A-Za-z0-9_]", "_", col)}'
        tref = feel_type_for(col)
        L.append('')
        L.append(f'  <inputData id="{safe}" name="{html.escape(col)}">')
        L.append(f'    <variable id="{safe}_var" name="{html.escape(col)}" typeRef="{tref}"/>')
        L.append('  </inputData>')

    for di, d in enumerate(decisions):
        did = re.sub(r'[^A-Za-z0-9_]', '_', d.get('id') or f'decision_{di+1}')
        dname = d.get('label') or local_name(d.get('id') or f'Decision_{di+1}')
        hp = str(d.get('hitPolicy') or 'U')
        dmn_hp = DMN_HIT_POLICY.get(hp, 'UNIQUE')
        aggregation = DMN_AGGREGATION.get(hp)
        outputs = d.get('outputs') if isinstance(d.get('outputs'), list) else [d.get('output') or 'result']
        out_name_safe = re.sub(r'[^A-Za-z0-9_]', '_', str(outputs[0]))

        L.append('')
        L.append(f'  <decision id="{html.escape(did)}" name="{html.escape(dname)}">')
        L.append(f'    <variable id="{html.escape(did)}_var" name="{html.escape(out_name_safe)}" typeRef="{out_type}"/>')
        for ii, col in enumerate(d.get('inputs') or []):
            ref = f'input_{all_inputs.index(col)+1}_{re.sub(r"[^A-Za-z0-9_]", "_", col)}'
            L.append(f'    <informationRequirement id="{did}_ir_{ii+1}">')
            L.append(f'      <requiredInput href="#{ref}"/>')
            L.append('    </informationRequirement>')
        dt_attrs = f'hitPolicy="{dmn_hp}"' + (f' aggregation="{aggregation}"' if aggregation else '')
        L.append(f'    <decisionTable id="{did}_table" {dt_attrs}>')
        for ii, col in enumerate(d.get('inputs') or []):
            tref = feel_type_for(col)
            L.append(f'      <input id="{did}_input_{ii+1}" label="{html.escape(col)}">')
            L.append(f'        <inputExpression id="{did}_inputExpr_{ii+1}" typeRef="{tref}">')
            L.append(f'          <text>{html.escape(col)}</text>')
            L.append('        </inputExpression>')
            L.append('      </input>')
        for oi, on in enumerate(outputs):
            safe = re.sub(r'[^A-Za-z0-9_]', '_', str(on))
            L.append(f'      <output id="{did}_output_{oi+1}" label="{html.escape(str(on))}" '
                     f'name="{html.escape(safe)}" typeRef="{out_type}"/>')
        for ri, r in enumerate(d.get('rules') or []):
            L.append(f'      <rule id="{did}_rule_{ri+1}">')
            for ci, cell in enumerate(r.get('inputs') or []):
                cs = '-' if cell is None else str(cell)
                L.append(f'        <inputEntry id="{did}_rule_{ri+1}_in_{ci+1}">')
                L.append(f'          <text>{html.escape(cs)}</text>')
                L.append('        </inputEntry>')
            out_vals = r.get('output') if isinstance(r.get('output'), list) else [r.get('output')]
            for oi, ov in enumerate(out_vals):
                L.append(f'        <outputEntry id="{did}_rule_{ri+1}_out_{oi+1}">')
                L.append(f'          <text>{html.escape(str(ov))}</text>')
                L.append('        </outputEntry>')
            L.append('      </rule>')
        L.append('    </decisionTable>')
        L.append('  </decision>')
    L.append('</definitions>')
    return '\n'.join(L) + '\n'


# ---------------------------------------------------------------------------
# 5. Orchestrator — emit the machine-readable artifacts. report.pdf is the
# /document-project skill's responsibility; we hand it everything it needs.
# ---------------------------------------------------------------------------

def bundle(model_html: str, out_dir: str, make_zip: str | None) -> None:
    with open(model_html, encoding='utf-8') as fh:
        text = fh.read()
    scripts = read_scripts(text)
    required = ['domain-model', 'model-jsonld', 'model-markdown']
    missing = [s for s in required if s not in scripts]
    if missing:
        raise SystemExit(f"{model_html}: missing required script(s): {', '.join(missing)}")

    turtle = scripts['domain-model']
    jsonld_text = scripts['model-jsonld']
    markdown_text = scripts['model-markdown']
    dmn_text = scripts.get('model-dmn', '{"decisions":[]}')
    horn_text = scripts.get('model-horn', '')

    try:
        jsonld = json.loads(jsonld_text)
    except json.JSONDecodeError as e:
        raise SystemExit(f"{model_html}: model-jsonld is not valid JSON: {e}")
    try:
        dmn_json = json.loads(dmn_text) if dmn_text.strip() else {'decisions': []}
    except json.JSONDecodeError as e:
        raise SystemExit(f"{model_html}: model-dmn is not valid JSON: {e}")

    model_name = derive_model_name(markdown_text, text)
    base_iri = derive_base_iri(jsonld)

    os.makedirs(out_dir, exist_ok=True)

    # --- model.ttl: canonical Turtle, as-is ---
    ttl_path = os.path.join(out_dir, 'model.ttl')
    with open(ttl_path, 'w', encoding='utf-8') as fh:
        fh.write(turtle.rstrip() + '\n')

    # --- model.dmn: DMN 1.5 XML ---
    dmn_path = os.path.join(out_dir, 'model.dmn')
    with open(dmn_path, 'w', encoding='utf-8') as fh:
        fh.write(dmn_xml(dmn_json, model_name, base_iri))

    # --- model.pl: Prolog projection + Horn rules ---
    pl_path = os.path.join(out_dir, 'model.pl')
    with open(pl_path, 'w', encoding='utf-8') as fh:
        fh.write(prolog_src(jsonld, horn_text))

    # --- model.html: the composed source, copied alongside the artifacts so
    # /document-project has the full data layer (JSON-LD, SWRL, rationale,
    # diagram SVG) without having to chase the original path. ---
    composed_html_path = os.path.join(out_dir, 'model.html')
    with open(composed_html_path, 'w', encoding='utf-8') as fh:
        fh.write(text)

    # --- MANIFEST.md: index + provenance + handoff brief for /document-project ---
    manifest_path = os.path.join(out_dir, 'MANIFEST.md')
    swrl_present = bool(scripts.get('model-swrl', '').strip()
                        and scripts['model-swrl'].strip() not in ('{"rules":[]}', '{ "rules": [] }'))
    with open(manifest_path, 'w', encoding='utf-8') as fh:
        fh.write(
            f'# {model_name} — submission bundle\n\n'
            f'Generated by `domain-forge/scripts/bundle.py` from '
            f'`{os.path.basename(model_html)}`.\n\n'
            f'## Machine-readable artifacts\n\n'
            f'| File | Format | Source in HTML | Open it with |\n'
            f'|---|---|---|---|\n'
            f'| `model.ttl`  | Turtle (OWL/RDFS) | `<script id="domain-model">` (canonical) | Protégé, rdflib, Apache Jena |\n'
            f'| `model.dmn`  | DMN 1.5 XML       | Projected from `<script id="model-dmn">` | Camunda Modeler, Trisotech, Signavio |\n'
            f'| `model.pl`   | Prolog (T-box + Horn) | JSON-LD + `<script id="model-horn">` | SWI-Prolog, GNU Prolog |\n'
            f'| `model.html` | The composed model | The composed source itself | Any browser (interactive diagram) |\n\n'
            f'**Base IRI:** `{base_iri}`\n\n'
            f'## report.pdf — produced separately by /document-project\n\n'
            f'`bundle.py` deliberately does **not** render a PDF. A submission report\n'
            f'is a narrative document — motivated prose, hand-drawn-quality figures,\n'
            f'chapter structure — not a print of the HTML page. To produce it:\n\n'
            f'```\n'
            f'cd <this bundle directory>\n'
            f'/document-project\n'
            f'```\n\n'
            f'The `/document-project` skill is an interactive LaTeX author. Give it\n'
            f'this brief when it asks:\n\n'
            f'> Document the domain model in `model.html`. The four canonical files in\n'
            f'> this directory are the project under documentation: `model.ttl` is the\n'
            f'> OWL ontology, `model.dmn` carries the decision tables, `model.pl`\n'
            f'> carries the T-box plus Horn rules, and `model.html` is the interactive\n'
            f'> diagram + ontology catalog + rationale. Chapters should cover: the\n'
            f'> problem context (from the model-markdown summary inside the HTML), the\n'
            f'> ontology design (per component, with TikZ diagrams), the decision\n'
            f'> logic (DMN tables rendered + Horn rules with motivation), and the\n'
            f'> design rationale (from the rationale data block).\n\n'
            f'## What this bundle does **not** include\n\n'
            f'- **No `report.pdf`** — produced by `/document-project` (see above).\n'
            f'- **No code stubs** — codegen is a separate agentic workflow per the\n'
            f'  user\'s direction; `model.html` carries codegen hints (`@target` per\n'
            f'  fragment) ready for that pass.\n'
            f'- **No source folder** — round-trip exploding the HTML is\n'
            f'  `scripts/explode_model.py` in domain-forge, run on demand.\n'
        )
        if swrl_present:
            fh.write('\n*Note: this model also carries SWRL rules; they are embedded'
                     ' in `model.html` (`<script id="model-swrl">`) and surface in '
                     'the Logic tab. SWRL is not extracted as a separate file because'
                     ' KE-course submissions do not require it.*\n')

    # --- optional zip ---
    if make_zip:
        zip_path = make_zip if make_zip.endswith('.zip') else make_zip + '.zip'
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            for name in os.listdir(out_dir):
                zf.write(os.path.join(out_dir, name), arcname=name)

    # --- report ---
    print(f'bundle: {model_html} → {out_dir}')
    print(f'  model.ttl   ({os.path.getsize(ttl_path):,} bytes)')
    print(f'  model.dmn   ({os.path.getsize(dmn_path):,} bytes)')
    print(f'  model.pl    ({os.path.getsize(pl_path):,} bytes)')
    print(f'  model.html  ({os.path.getsize(composed_html_path):,} bytes — original)')
    print(f'  MANIFEST.md ({os.path.getsize(manifest_path):,} bytes)')
    if make_zip:
        print(f'  zipped:     {zip_path} ({os.path.getsize(zip_path):,} bytes)')
    print()
    print('Next step for the written report:')
    print(f'  cd {out_dir} && /document-project')
    print('  (the brief is in MANIFEST.md)')


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument('model_html', help='Composed model.html')
    ap.add_argument('--out', '-o', required=True, help='Output directory for the bundle')
    ap.add_argument('--zip', '-z', metavar='PATH',
                    help='Also write a zip of the bundle to this path')
    args = ap.parse_args()
    if not os.path.isfile(args.model_html):
        print(f'model HTML not found: {args.model_html}', file=sys.stderr)
        return 2
    try:
        bundle(args.model_html, args.out, args.zip)
    except SystemExit as e:
        print(e, file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
