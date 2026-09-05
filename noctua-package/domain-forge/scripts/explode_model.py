#!/usr/bin/env python3
"""Explode a composed domain-forge HTML back into a per-entity source folder.

The inverse of `compose_model.py`. Given a single composed `model.html` (one
that the agent or a previous compose run produced), this writes:

    <source>/
    ├── model.meta.json                      # @context, prefixes, codegenTargets, components, model-level rationale
    ├── overview.md                          # the Markdown summary
    ├── entities/<component>/<Name>.html     # one fragment per class / individual; carries its owned data properties
    ├── relationships/<component>/<name>.html # one fragment per object property; declares domain → range
    └── logic/{dmn.json, horn.pl, swrl.json} # decision/rule layers if non-empty

After explode, you can edit one fragment (`entities/billing/Money.html`) and
re-run `compose_model.py` to regenerate the composed HTML. Round-trip should
preserve the model's semantics; identity-level byte equivalence is not
guaranteed (fragments are reformatted), but composing the explosion of a
composed model and re-validating should produce the same passing report.

usage:
    explode_model.py <model.html> --out <source-dir>
"""
from __future__ import annotations
import argparse
import json
import os
import re
import shutil
import sys
from html.parser import HTMLParser


HERE = os.path.dirname(os.path.abspath(__file__))


# ---------------------------------------------------------------------------
# Read the composed model
# ---------------------------------------------------------------------------
RE_SCRIPT_BY_ID = re.compile(
    r'<script\s[^>]*id=["\']([^"\']+)["\'][^>]*>([\s\S]*?)</script>', re.I)


def read_canonical_scripts(html_text: str) -> dict[str, str]:
    """Return { script_id: text_content } for every <script id=...> in the doc."""
    out = {}
    for m in RE_SCRIPT_BY_ID.finditer(html_text):
        out[m.group(1)] = m.group(2).strip()
    return out


def local_name(iri: str) -> str:
    return re.sub(r'^[^:]*:', '', iri or '')


def safe_filename(s: str) -> str:
    return re.sub(r'[^A-Za-z0-9_-]', '_', s) or 'untitled'


def as_array(v):
    if v is None: return []
    return v if isinstance(v, list) else [v]


def is_type(node: dict, t: str) -> bool:
    return t in as_array(node.get('@type'))


# ---------------------------------------------------------------------------
# Turtle emission from JSON-LD node
# ---------------------------------------------------------------------------
def turtle_for_class(node: dict, dprops: list[dict]) -> str:
    """Emit Turtle for a class node and the data properties it owns."""
    iri = node['@id']
    parts = [f'{iri} a owl:Class']
    if node.get('component'):
        parts.append(f'ex:component {json_lit(node["component"])}')
    if node.get('valueObject') or node.get('ex:valueObject'):
        parts.append('ex:valueObject "true"')
    for sup in as_array(node.get('subClassOf') or node.get('rdfs:subClassOf')):
        parts.append(f'rdfs:subClassOf {sup}')
    for eq in as_array(node.get('equivalentClass') or node.get('owl:equivalentClass')):
        parts.append(f'owl:equivalentClass {eq}')
    for dj in as_array(node.get('disjointWith') or node.get('owl:disjointWith')):
        parts.append(f'owl:disjointWith {dj}')
    if node.get('label'):
        parts.append(f'rdfs:label {json_lit(node["label"])}')
    if node.get('comment'):
        parts.append(f'rdfs:comment {json_lit(node["comment"])}')
    block = ' ;\n  '.join(parts) + ' .'

    # Data properties owned by this class.
    dp_block = ''
    for p in dprops:
        line = f'{p["@id"]} a owl:DatatypeProperty'
        if p.get('domain') or p.get('rdfs:domain'):
            line += f' ; rdfs:domain {p.get("domain") or p["rdfs:domain"]}'
        if p.get('range') or p.get('rdfs:range'):
            line += f' ; rdfs:range {p.get("range") or p["rdfs:range"]}'
        if p.get('label'):
            line += f' ; rdfs:label {json_lit(p["label"])}'
        line += ' .'
        dp_block += '\n' + line
    return block + dp_block


def turtle_for_individual(node: dict) -> str:
    iri = node['@id']
    types = as_array(node['@type'])
    parts = [f'{iri} a ' + ' , '.join(types)]
    if node.get('component'):
        parts.append(f'ex:component {json_lit(node["component"])}')
    if node.get('label'):
        parts.append(f'rdfs:label {json_lit(node["label"])}')
    if node.get('comment'):
        parts.append(f'rdfs:comment {json_lit(node["comment"])}')
    return ' ;\n  '.join(parts) + ' .'


def turtle_for_objectproperty(node: dict) -> str:
    iri = node['@id']
    types = ['owl:ObjectProperty']
    for ch in as_array(node.get('characteristics') or node.get('ex:characteristic')):
        types.append(f'owl:{ch}Property' if not ch.endswith('Property') else f'owl:{ch}')
    parts = [f'{iri} a ' + ' , '.join(types)]
    if node.get('domain') or node.get('rdfs:domain'):
        parts.append(f'rdfs:domain {node.get("domain") or node["rdfs:domain"]}')
    if node.get('range') or node.get('rdfs:range'):
        parts.append(f'rdfs:range {node.get("range") or node["rdfs:range"]}')
    inv = node.get('inverseOf') or node.get('owl:inverseOf')
    if inv:
        parts.append(f'owl:inverseOf {inv}')
    for sup in as_array(node.get('subPropertyOf') or node.get('rdfs:subPropertyOf')):
        parts.append(f'rdfs:subPropertyOf {sup}')
    if node.get('label'):
        parts.append(f'rdfs:label {json_lit(node["label"])}')
    if node.get('comment'):
        parts.append(f'rdfs:comment {json_lit(node["comment"])}')
    return ' ;\n  '.join(parts) + ' .'


def turtle_for_dataproperty(node: dict) -> str:
    iri = node['@id']
    types = ['owl:DatatypeProperty']
    for ch in as_array(node.get('characteristics') or node.get('ex:characteristic')):
        types.append(f'owl:{ch}Property' if not ch.endswith('Property') else f'owl:{ch}')
    parts = [f'{iri} a ' + ' , '.join(types)]
    if node.get('domain') or node.get('rdfs:domain'):
        parts.append(f'rdfs:domain {node.get("domain") or node["rdfs:domain"]}')
    if node.get('range') or node.get('rdfs:range'):
        parts.append(f'rdfs:range {node.get("range") or node["rdfs:range"]}')
    if node.get('label'):
        parts.append(f'rdfs:label {json_lit(node["label"])}')
    return ' ;\n  '.join(parts) + ' .'


def json_lit(s) -> str:
    """Quote a string literal for Turtle, escaping minimally."""
    if not isinstance(s, str):
        s = str(s)
    s = s.replace('\\', '\\\\').replace('"', '\\"')
    return f'"{s}"'


# ---------------------------------------------------------------------------
# HTML fragment writers
# ---------------------------------------------------------------------------
FRAGMENT_TEMPLATE = """<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><title>{name}</title>
<style>body{{font:14px/1.5 system-ui;max-width:62ch;margin:30px auto;color:#27272a;padding:0 20px}}
h1{{font-size:20px;margin:0 0 6px}}code{{background:#f4f4f5;padding:1px 4px;border-radius:3px;font:12px ui-monospace,Menlo,monospace}}
.kind{{font-size:10px;background:#eef2ff;color:#3730a3;padding:2px 7px;border-radius:3px;letter-spacing:.05em;text-transform:uppercase;font-weight:600;margin-left:6px}}
.kind.value{{background:#e0f2fe;color:#0369a1}}
.rationale{{background:#fefbf0;border-left:4px solid #f59e0b;padding:10px 14px;margin-top:14px;border-radius:6px;font-size:13px}}
.rationale h3{{font-size:11px;color:#92400e;margin:0 0 6px;letter-spacing:.06em;text-transform:uppercase}}
.rationale ul{{margin:6px 0;padding-left:18px}}.rationale em{{color:#78350f}}</style>
</head>
<body>
<h1>{name}{kind_html}</h1>
<code>{iri}</code>{tag_html}
{description_html}
{rationale_html}
<script type="application/x-df-entity-data" id="entity-data">
{data_json}
</script>
<script type="application/x-df-entity-ttl" id="entity-ttl">
{ttl}
</script>
</body></html>
"""


def render_fragment(name: str, iri: str, kind_label: str, kind_class: str,
                    tag_text: str, description: str,
                    rationale: dict | None,
                    data_payload, ttl: str) -> str:
    kind_html = f'<span class="kind {kind_class}">{kind_label}</span>' if kind_label else ''
    tag_html = f' · {tag_text}' if tag_text else ''
    description_html = f'<p>{description}</p>' if description else ''
    rat_html = ''
    if rationale and (rationale.get('choice') or rationale.get('alternatives') or
                       rationale.get('tradeoffs') or rationale.get('anchors')):
        bits = ['<div class="rationale"><h3>Design rationale</h3>']
        if rationale.get('choice'):
            bits.append(f'<p>{html_escape(rationale["choice"])}</p>')
        if rationale.get('alternatives'):
            bits.append('<p><em>Alternatives:</em></p><ul>')
            for a in rationale['alternatives']:
                bits.append(f'<li>{html_escape(a)}</li>')
            bits.append('</ul>')
        if rationale.get('tradeoffs'):
            bits.append(f'<p><em>⚖ {html_escape(rationale["tradeoffs"])}</em></p>')
        if rationale.get('anchors'):
            anchors = ' '.join(f'<code>{html_escape(a)}</code>' for a in rationale['anchors'])
            bits.append(f'<p>{anchors}</p>')
        bits.append('</div>')
        rat_html = ''.join(bits)
    data_json = json.dumps(data_payload, indent=2, ensure_ascii=False)
    return FRAGMENT_TEMPLATE.format(
        name=html_escape(name),
        iri=html_escape(iri),
        kind_html=kind_html,
        tag_html=html_escape(tag_html),
        description_html=description_html,
        rationale_html=rat_html,
        data_json=data_json,
        ttl=ttl.rstrip() + '\n',
    )


def html_escape(s: str) -> str:
    if not isinstance(s, str): s = str(s)
    return (s.replace('&', '&amp;')
             .replace('<', '&lt;')
             .replace('>', '&gt;'))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def explode(html_path: str, out_dir: str) -> None:
    with open(html_path, encoding='utf-8') as fh:
        doc = fh.read()
    scripts = read_canonical_scripts(doc)

    # Parse canonical blocks
    try:
        ld = json.loads(scripts.get('model-jsonld') or '{}')
    except Exception as e:
        raise SystemExit(f"could not parse model-jsonld in {html_path}: {e}")
    ctx = ld.get('@context') or {}
    graph = ld.get('@graph') or []

    markdown   = scripts.get('model-markdown', '') or '# Untitled model\n'
    dmn_raw    = scripts.get('model-dmn', '').strip()    or '{"decisions": []}'
    horn_raw   = scripts.get('model-horn', '').strip()   or '% No Horn rules\n'
    swrl_raw   = scripts.get('model-swrl', '').strip()   or '{"rules": []}'
    rat_raw    = scripts.get('model-rationale', '').strip() or '{}'
    try:
        model_rationale = json.loads(rat_raw)
    except Exception:
        model_rationale = {}

    # Categorise nodes
    classes = [n for n in graph if isinstance(n, dict) and is_type(n, 'owl:Class')]
    objprops = [n for n in graph if isinstance(n, dict) and is_type(n, 'owl:ObjectProperty')]
    dataprops = [n for n in graph if isinstance(n, dict) and is_type(n, 'owl:DatatypeProperty')]
    individuals = []
    for n in graph:
        if not isinstance(n, dict): continue
        ty = as_array(n.get('@type'))
        if ty and not any(t in ('owl:Class', 'owl:ObjectProperty', 'owl:DatatypeProperty') for t in ty):
            individuals.append(n)

    # Component for a node: prefer its `component` field; for properties without
    # one, use the domain class's component.
    by_iri = {n['@id']: n for n in graph if isinstance(n, dict) and n.get('@id')}
    def component_of(n):
        if n.get('component'): return n['component']
        d = (n.get('domain') or n.get('rdfs:domain'))
        if d and d in by_iri:
            return by_iri[d].get('component') or 'unassigned'
        types = as_array(n.get('@type'))
        for t in types:
            if t in by_iri and by_iri[t].get('component'):
                return by_iri[t]['component']
        return 'unassigned'

    base = ctx.get('ex') or 'http://example.org/PROJECT#'

    # Write directory structure
    if os.path.exists(out_dir):
        # only purge entities/ relationships/ logic/ and known top-level files;
        # don't delete arbitrary user content
        for sub in ('entities', 'relationships', 'logic'):
            p = os.path.join(out_dir, sub)
            if os.path.isdir(p): shutil.rmtree(p)
        for f in ('model.meta.json', 'overview.md', 'index.json'):
            p = os.path.join(out_dir, f)
            if os.path.isfile(p): os.remove(p)
    os.makedirs(out_dir, exist_ok=True)

    # model.meta.json
    meta = {
        '@base': base,
        'base': base,
        'prefixes': {
            'ex':   base,
            'owl':  'http://www.w3.org/2002/07/owl#',
            'rdfs': 'http://www.w3.org/2000/01/rdf-schema#',
            'xsd':  'http://www.w3.org/2001/XMLSchema#',
        },
        '@context': ctx,
        'codegenTargets': {},
        'components': {},
        'designRationale': model_rationale,
    }
    with open(os.path.join(out_dir, 'model.meta.json'), 'w', encoding='utf-8') as fh:
        json.dump(meta, fh, indent=2, ensure_ascii=False)

    # overview.md
    with open(os.path.join(out_dir, 'overview.md'), 'w', encoding='utf-8') as fh:
        fh.write(markdown.rstrip() + '\n')

    # logic
    logic_dir = os.path.join(out_dir, 'logic')
    os.makedirs(logic_dir, exist_ok=True)
    with open(os.path.join(logic_dir, 'dmn.json'), 'w', encoding='utf-8') as fh:
        fh.write(dmn_raw + '\n')
    with open(os.path.join(logic_dir, 'horn.pl'), 'w', encoding='utf-8') as fh:
        fh.write(horn_raw.rstrip() + '\n')
    with open(os.path.join(logic_dir, 'swrl.json'), 'w', encoding='utf-8') as fh:
        fh.write(swrl_raw + '\n')

    # entities/<component>/<Name>.html — class fragments carry their owned data properties
    written = 0
    consumed_dprops = set()
    for c in classes:
        iri = c['@id']
        name = local_name(iri)
        comp = component_of(c)
        # Data properties whose domain is this class
        owned = [p for p in dataprops
                 if (p.get('domain') or p.get('rdfs:domain')) == iri]
        consumed_dprops.update(p['@id'] for p in owned)

        kind_label = 'value object' if (c.get('valueObject') or c.get('ex:valueObject')) else 'class'
        kind_class = 'value' if kind_label == 'value object' else ''
        description = c.get('comment') or ''
        rationale = c.get('designRationale') or c.get('ex:designRationale')
        ttl = turtle_for_class(c, owned)
        payload = [c] + owned if owned else c

        path = os.path.join(out_dir, 'entities', safe_filename(comp), f'{safe_filename(name)}.html')
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as fh:
            fh.write(render_fragment(name, iri, kind_label, kind_class,
                                     f'component <code>{comp}</code>', description,
                                     rationale, payload, ttl))
        written += 1

    # Stray data properties (no class found) — write them as their own files.
    for p in dataprops:
        if p['@id'] in consumed_dprops: continue
        iri = p['@id']
        name = local_name(iri)
        comp = component_of(p)
        ttl = turtle_for_dataproperty(p)
        path = os.path.join(out_dir, 'relationships', safe_filename(comp), f'{safe_filename(name)}.html')
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as fh:
            fh.write(render_fragment(name, iri, 'data property', '',
                                     f'component <code>{comp}</code>',
                                     p.get('comment') or '',
                                     p.get('designRationale'),
                                     p, ttl))
        written += 1

    # relationships/<component>/<name>.html — object properties
    for op in objprops:
        iri = op['@id']
        name = local_name(iri)
        comp = component_of(op)
        ttl = turtle_for_objectproperty(op)
        path = os.path.join(out_dir, 'relationships', safe_filename(comp), f'{safe_filename(name)}.html')
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as fh:
            fh.write(render_fragment(
                name, iri, 'object property', '',
                f'<code>{op.get("domain","?")}</code> → <code>{op.get("range","?")}</code>',
                op.get('comment') or '',
                op.get('designRationale'),
                op, ttl))
        written += 1

    # individuals — write into entities/<component>/<name>.html
    for ind in individuals:
        iri = ind['@id']
        name = local_name(iri)
        comp = component_of(ind)
        ttl = turtle_for_individual(ind)
        path = os.path.join(out_dir, 'entities', safe_filename(comp), f'{safe_filename(name)}.html')
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as fh:
            fh.write(render_fragment(name, iri, 'individual', '',
                                     f'component <code>{comp}</code>',
                                     ind.get('comment') or '',
                                     ind.get('designRationale'),
                                     ind, ttl))
        written += 1

    print(f"exploded {html_path} → {out_dir}")
    print(f"  {len(classes)} class{'es' if len(classes)!=1 else ''}, "
          f"{len(objprops)} object propert{'ies' if len(objprops)!=1 else 'y'}, "
          f"{len(dataprops)} data propert{'ies' if len(dataprops)!=1 else 'y'}, "
          f"{len(individuals)} individual{'s' if len(individuals)!=1 else ''} "
          f"→ {written} fragment file{'s' if written!=1 else ''}")
    print(f"  Re-compose with: python3 {os.path.relpath(os.path.join(HERE,'compose_model.py'))} {out_dir} --out <model.html>")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('model_html', help='Path to the composed model HTML to explode')
    ap.add_argument('--out', '-o', required=True, help='Target source directory')
    args = ap.parse_args()
    if not os.path.isfile(args.model_html):
        print(f"file not found: {args.model_html}", file=sys.stderr)
        return 2
    try:
        explode(args.model_html, args.out)
    except SystemExit as e:
        print(e, file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
