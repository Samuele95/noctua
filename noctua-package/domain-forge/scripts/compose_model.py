#!/usr/bin/env python3
"""Compose a domain-forge model from a source folder of per-entity HTML fragments.

The source folder layout is:

    <model-source>/
    ├── model.meta.json          # base IRI, prefixes, components, model-level rationale
    ├── overview.md              # the model-markdown content (the prose summary)
    ├── entities/
    │   ├── <ClassName>.html     # one self-contained HTML fragment per class/individual
    │   └── ...
    ├── relationships/
    │   ├── <propName>.html      # one fragment per object / data property
    │   └── ...
    └── logic/                   # optional
        ├── dmn.json
        ├── horn.pl
        └── swrl.json

Each entity / relationship HTML fragment is itself a self-contained, browsable
HTML file. Inside it, the canonical data lives in two `<script>` blocks that
the composer extracts:

    <script type="application/x-df-entity-data">{ JSON-LD node for this entity }</script>
    <script type="application/x-df-entity-ttl">  Turtle for this entity   </script>

The composer:
  1. Reads every entity / relationship file and extracts the JSON-LD + Turtle.
  2. Reads model.meta.json for the @context and the model-level rationale.
  3. Reads overview.md for the prose summary.
  4. Reads logic/* for the DMN / Horn / SWRL blocks (if present).
  5. Injects everything into the appropriate `<script>` blocks in a fresh copy
     of assets/template.html and writes the composed model.html.

This means editing ONE entity fragment is sufficient to update the composed
model — re-run compose and the new HTML is regenerated. That is the
"sub-HTML file update" principle the user asked for.

usage:
    compose_model.py <source-dir> --out <model.html>

The reverse operation (split a composed HTML back into per-entity fragments) is
in `scripts/explode_model.py`.
"""
from __future__ import annotations
import argparse
import json
import os
import re
import sys
from typing import Any


HERE = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_PATH = os.path.abspath(os.path.join(HERE, '..', 'assets', 'template.html'))


# ---------------------------------------------------------------------------
# Fragment readers
# ---------------------------------------------------------------------------
RE_SCRIPT = re.compile(
    r'<script\s[^>]*type=["\']application/x-df-entity-(data|ttl)["\'][^>]*>'
    r'([\s\S]*?)</script>', re.I)


def extract_fragment(html_text: str, path: str) -> dict:
    """Pull (jsonld_node(s), turtle_chunk) out of one entity / relationship fragment.

    The `application/x-df-entity-data` script may hold either:
      - a single JSON-LD node (back-compat, for relationship files):
            { "@id": "ex:hasName", "@type": "owl:ObjectProperty", ... }
      - an array of JSON-LD nodes (for entity files that carry their owned data
        properties as siblings):
            [ { "@id": "ex:Product", "@type": "owl:Class", ... },
              { "@id": "ex:hasSku", "@type": "owl:DatatypeProperty",
                "domain": "ex:Product", "range": "xsd:string" },
              ... ]
    The composer flattens arrays into the final @graph so a class fragment can
    own its data-property declarations without scattering them across files.
    """
    data = None
    ttl = ''
    for m in RE_SCRIPT.finditer(html_text):
        kind = m.group(1).lower()
        body = m.group(2).strip()
        if kind == 'data':
            try:
                data = json.loads(body)
            except Exception as e:
                raise SystemExit(f"{path}: x-df-entity-data is not valid JSON: {e}")
        elif kind == 'ttl':
            ttl = body
    if data is None:
        raise SystemExit(f"{path}: missing <script type=\"application/x-df-entity-data\">")
    nodes = data if isinstance(data, list) else [data]
    for n in nodes:
        if not isinstance(n, dict) or not n.get('@id'):
            raise SystemExit(f"{path}: x-df-entity-data node has no @id")
    return {'data': nodes[0], 'nodes': nodes, 'ttl': ttl, 'source_path': path}


def load_fragments(source_dir: str, subdir: str) -> list[dict]:
    """Walk `<source_dir>/<subdir>/` recursively. Directory layout can be flat
    (`entities/Product.html`) or grouped by bounded context
    (`entities/catalog/Product.html`). Codegen prefers the grouped layout because
    each component then maps 1:1 to a target-language package; the composer
    accepts either."""
    root = os.path.join(source_dir, subdir)
    if not os.path.isdir(root):
        return []
    out = []
    for dirpath, _dirs, files in os.walk(root):
        for name in sorted(files):
            if not name.endswith('.html'):
                continue
            full = os.path.join(dirpath, name)
            with open(full, encoding='utf-8') as fh:
                f = extract_fragment(fh.read(), full)
            # Component hint inferred from the directory if not in the JSON node
            rel = os.path.relpath(full, root)
            parts = rel.split(os.sep)
            if len(parts) > 1 and 'component' not in f['data']:
                f['data']['component'] = parts[0]
            f['_relpath'] = rel
            out.append(f)
    return out


def read_optional(src_dir: str, *parts: str, default: str = '') -> str:
    p = os.path.join(src_dir, *parts)
    if not os.path.exists(p):
        return default
    with open(p, encoding='utf-8') as fh:
        return fh.read()


# ---------------------------------------------------------------------------
# Composition
# ---------------------------------------------------------------------------
def compose(source_dir: str, out_path: str) -> None:
    if not os.path.exists(TEMPLATE_PATH):
        raise SystemExit(f"template not found at {TEMPLATE_PATH}")
    template = open(TEMPLATE_PATH, encoding='utf-8').read()

    # 1. Model metadata
    meta_path = os.path.join(source_dir, 'model.meta.json')
    if not os.path.exists(meta_path):
        raise SystemExit(f"{meta_path} not found — source must declare base IRI / components / @context")
    meta = json.loads(open(meta_path, encoding='utf-8').read())

    base = meta.get('base') or meta.get('@base') or 'http://example.org/PROJECT#'
    prefixes = meta.get('prefixes') or {
        'ex':   base,
        'owl':  'http://www.w3.org/2002/07/owl#',
        'rdfs': 'http://www.w3.org/2000/01/rdf-schema#',
        'xsd':  'http://www.w3.org/2001/XMLSchema#',
    }
    ctx = meta.get('@context') or {
        'ex': base, 'owl': prefixes['owl'], 'rdfs': prefixes['rdfs'], 'xsd': prefixes['xsd'],
        'component': 'ex:component', 'valueObject': 'ex:valueObject',
        'domain': {'@id': 'rdfs:domain', '@type': '@id'},
        'range':  {'@id': 'rdfs:range',  '@type': '@id'},
        'subClassOf': {'@id': 'rdfs:subClassOf', '@type': '@id', '@container': '@set'},
        'subPropertyOf': {'@id': 'rdfs:subPropertyOf', '@type': '@id', '@container': '@set'},
        'label': 'rdfs:label', 'comment': 'rdfs:comment',
        'equivalentClass': {'@id': 'owl:equivalentClass', '@type': '@id', '@container': '@set'},
        'disjointWith':    {'@id': 'owl:disjointWith',    '@type': '@id', '@container': '@set'},
        'inverseOf': {'@id': 'owl:inverseOf', '@type': '@id'},
        'characteristics': 'ex:characteristic',
        'restrictions':    'ex:restriction',
        'designRationale': 'ex:designRationale',
    }
    model_rationale = meta.get('designRationale') or meta.get('rationale') or {
        'choice': '', 'alternatives': [], 'tradeoffs': '', 'anchors': []
    }

    # 2. Fragments
    entities = load_fragments(source_dir, 'entities')
    rels     = load_fragments(source_dir, 'relationships')

    # 3. Prose summary
    overview_md = read_optional(source_dir, 'overview.md', default='# Untitled model\n')

    # 4. Logic
    dmn  = read_optional(source_dir, 'logic', 'dmn.json',  default='{"decisions": []}').strip()
    horn = read_optional(source_dir, 'logic', 'horn.pl',   default='% No Horn rules.\n')
    swrl = read_optional(source_dir, 'logic', 'swrl.json', default='{"rules": []}').strip()

    # 5. Compose Turtle: prefixes + entity-by-entity + relationship-by-relationship
    ttl_parts: list[str] = []
    for short, full in prefixes.items():
        ttl_parts.append(f'@prefix {short}: <{full}> .')
    ttl_parts.append('')
    for f in entities + rels:
        ln = f['data'].get('@id', '').split(':')[-1] or 'fragment'
        ttl_parts.append(f'# ── {ln} ──')
        ttl_parts.append(f['ttl'].strip())
        ttl_parts.append('')
    turtle = '\n'.join(ttl_parts)

    # 6. Compose JSON-LD @graph — flatten any per-fragment arrays so a class
    # fragment can carry its own data properties as sibling nodes. De-duplicate
    # on @id so a property re-declared in two fragments keeps the first.
    graph = []
    seen_ids = set()
    for f in entities + rels:
        for node in f.get('nodes', [f['data']]):
            iri = node.get('@id')
            if iri in seen_ids:
                continue
            seen_ids.add(iri)
            graph.append({k: v for k, v in node.items() if not k.startswith('_')})
    jsonld = json.dumps({'@context': ctx, '@graph': graph}, indent=2, ensure_ascii=False)

    # 7. Substitute into the template
    def sub_script(t: str, sid: str, content: str) -> str:
        pat = re.compile(
            rf'(<script\s[^>]*id="{re.escape(sid)}"[^>]*>)([\s\S]*?)(</script>)', re.I)
        if not pat.search(t):
            raise SystemExit(f"template missing <script id='{sid}'>")
        return pat.sub(lambda m: m.group(1) + '\n' + content + '\n' + m.group(3), t, count=1)

    out = sub_script(template, 'domain-model',     turtle)
    out = sub_script(out,      'model-jsonld',     jsonld)
    out = sub_script(out,      'model-markdown',   overview_md.rstrip() + '\n')
    out = sub_script(out,      'model-dmn',        dmn)
    out = sub_script(out,      'model-horn',       horn)
    out = sub_script(out,      'model-swrl',       swrl)
    out = sub_script(out,      'model-rationale',  json.dumps(model_rationale, indent=2))

    os.makedirs(os.path.dirname(os.path.abspath(out_path)) or '.', exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as fh:
        fh.write(out)

    # Emit index.json — an IRI → source-file map for downstream codegen tools.
    # Codegen walks this to know "which file owns ex:Product" without reparsing
    # every fragment. Each entry also carries the codegen hints from the JSON-LD
    # node so a generator can dispatch on `kind`/`codegen.target` directly.
    index_entries = []
    for f in entities + rels:
        n = f['data']
        index_entries.append({
            'iri':       n.get('@id'),
            'kind':      'entity' if 'rdfs:domain' not in n and 'domain' not in n else 'relationship',
            'type':      n.get('@type'),
            'component': n.get('component'),
            'source':    f.get('_relpath') or os.path.relpath(f['source_path'], source_dir),
            'codegen':   n.get('codegen'),
            'valueObject': bool(n.get('valueObject') or n.get('ex:valueObject')),
        })
    index = {
        'base': base,
        'codegenTargets': meta.get('codegenTargets') or {},
        'components': meta.get('components') or {},
        'entities': [e for e in index_entries if e['kind'] == 'entity'],
        'relationships': [e for e in index_entries if e['kind'] == 'relationship'],
    }
    index_path = os.path.join(source_dir, 'index.json')
    with open(index_path, 'w', encoding='utf-8') as fh:
        json.dump(index, fh, indent=2, ensure_ascii=False)

    # Report
    print(f"composed {len(entities)} entit{'y' if len(entities)==1 else 'ies'} + "
          f"{len(rels)} relationship{'' if len(rels)==1 else 's'} → {out_path} "
          f"({len(out):,} bytes)")
    print(f"  index:    {index_path}")
    print(f"  base IRI: {base}")
    print(f"  source:   {source_dir}")
    if model_rationale.get('choice'):
        print(f"  rationale: {model_rationale['choice'][:80]}{'...' if len(model_rationale['choice'])>80 else ''}")


# ---------------------------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('source', help='Path to the source directory')
    ap.add_argument('--out', '-o', required=True, help='Path to the composed HTML file')
    args = ap.parse_args()

    if not os.path.isdir(args.source):
        print(f"source directory not found: {args.source}", file=sys.stderr)
        return 2
    try:
        compose(args.source, args.out)
    except SystemExit as e:
        print(e, file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
