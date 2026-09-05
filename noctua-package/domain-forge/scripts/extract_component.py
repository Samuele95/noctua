#!/usr/bin/env python3
"""Lift one component (entity-cluster) out of a domain-forge model as a
standalone, still-valid domain-forge file — v3 architecture.

v3 reads from the canonical data scripts (Turtle + JSON-LD + Markdown) and
writes a new file by filtering those scripts to the requested component and
substituting them into a fresh copy of the template. Boundary classes (cross-
component endpoints referenced by relationships touching the component) are
emitted as stubs with component "_boundary" so domain/range still resolves.

usage: extract_component.py <model.html> --component <name> [--out <file>]
"""
import json
import os
import re
import sys


HERE = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_PATH = os.path.abspath(os.path.join(HERE, '..', 'assets', 'template.html'))


def script_block(html, sid):
    m = re.search(
        rf'<script\s[^>]*id="{re.escape(sid)}"[^>]*>([\s\S]*?)</script>',
        html, re.I)
    return m.group(1) if m else ''


def replace_script(html, sid, new_content):
    pat = re.compile(
        rf'(<script\s[^>]*id="{re.escape(sid)}"[^>]*>)([\s\S]*?)(</script>)', re.I)
    return pat.sub(lambda m: m.group(1) + '\n' + new_content + '\n' + m.group(3), html, count=1)


def localname(iri):
    return re.sub(r'^[^:]*:', '', str(iri))


def parse_jsonld_graph(text):
    try:
        ld = json.loads(text)
    except Exception:
        return None, []
    return ld, ld.get('@graph', []) if isinstance(ld, dict) else []


def is_type(node, t):
    ty = node.get('@type')
    return (t == ty) or (isinstance(ty, list) and t in ty)


def filter_for_component(graph, target):
    """Return (kept_classes_iris, kept_props, boundary_iris, full_kept_nodes)."""
    classes_in = {n['@id'] for n in graph if is_type(n, 'owl:Class')
                  and n.get('component') == target}
    obj_props = [n for n in graph if is_type(n, 'owl:ObjectProperty')]
    data_props= [n for n in graph if is_type(n, 'owl:DatatypeProperty')]
    indivs = [n for n in graph
              if not (is_type(n,'owl:Class') or is_type(n,'owl:ObjectProperty') or is_type(n,'owl:DatatypeProperty'))
              and n.get('@type')]

    # An object property is kept if either endpoint is in the component.
    kept_op, boundary = [], set()
    for p in obj_props:
        d, r = p.get('domain'), p.get('range')
        if d in classes_in or r in classes_in:
            kept_op.append(p)
            for x in (d, r):
                if x and x not in classes_in: boundary.add(x)
    # Data properties whose domain is in the component come with it.
    kept_dp = [p for p in data_props if p.get('domain') in classes_in]
    # Individuals typed by an in-component class come with it.
    def types(n):
        ty = n.get('@type'); return ty if isinstance(ty, list) else ([ty] if ty else [])
    kept_indiv = [i for i in indivs if any(t in classes_in for t in types(i))]

    return classes_in, kept_op, kept_dp, kept_indiv, boundary


def emit_turtle(classes_in, boundary, kept_op, kept_dp, kept_indiv, target, prefixes):
    out = [prefixes.rstrip(), '']
    for c in sorted(classes_in):
        out.append(f'{c} a owl:Class ; ex:component "{target}" .')
    for b in sorted(boundary):
        out.append(f'{b} a owl:Class ; ex:component "_boundary" .')
    for p in kept_dp:
        out.append(f'{p["@id"]} a owl:DatatypeProperty ; '
                   f'rdfs:domain {p.get("domain","?")} ; rdfs:range {p.get("range","?")} .')
    for p in kept_op:
        out.append(f'{p["@id"]} a owl:ObjectProperty ; '
                   f'rdfs:domain {p.get("domain","?")} ; rdfs:range {p.get("range","?")} .')
    for i in kept_indiv:
        ty = i.get('@type')
        types = ty if isinstance(ty, list) else [ty]
        for t in types:
            out.append(f'{i["@id"]} a {t} .')
    return '\n'.join(out) + '\n'


def emit_jsonld(ctx, classes_in, boundary, kept_op, kept_dp, kept_indiv, target):
    nodes = []
    for c in sorted(classes_in):
        nodes.append({'@id': c, '@type': 'owl:Class', 'component': target})
    for b in sorted(boundary):
        nodes.append({'@id': b, '@type': 'owl:Class', 'component': '_boundary'})
    for p in kept_dp:
        nodes.append({'@id': p['@id'], '@type': 'owl:DatatypeProperty',
                      'domain': p.get('domain'), 'range': p.get('range')})
    for p in kept_op:
        nodes.append({'@id': p['@id'], '@type': 'owl:ObjectProperty',
                      'domain': p.get('domain'), 'range': p.get('range')})
    for i in kept_indiv:
        nodes.append({'@id': i['@id'], '@type': i.get('@type')})
    out = {'@context': ctx, '@graph': nodes}
    return json.dumps(out, indent=2)


def emit_markdown(target, classes_in, boundary, kept_op, kept_dp):
    cls_names = sorted(localname(c) for c in classes_in)
    bnd_names = sorted(localname(b) for b in boundary)
    return ('\n'.join([
        f'# Subcomponent: `{target}`',
        '',
        f'Extracted from a parent domain-forge model so a deeper pass can refine just this cluster.',
        '',
        f'**Classes in `{target}`** — {", ".join(cls_names) if cls_names else "(none)"}.',
        ('**Boundary stubs** — ' + ', '.join(bnd_names) + '.') if bnd_names else '',
        f'**Relationships preserved**: {len(kept_op)} object propert{"y" if len(kept_op)==1 else "ies"}, '
        f'{len(kept_dp)} data propert{"y" if len(kept_dp)==1 else "ies"}.',
        '',
        f'This file is itself a valid `domain-forge` artifact — feed it back to the skill.',
    ]).rstrip()) + '\n'


def main():
    args = sys.argv[1:]
    if not args or '--component' not in args:
        print("usage: extract_component.py <model.html> --component <name> [--out <file>]")
        return 2
    src_path = args[0]
    comp = args[args.index('--component') + 1]
    out_path = args[args.index('--out') + 1] if '--out' in args else None

    html = open(src_path, encoding='utf-8').read()
    if not os.path.exists(TEMPLATE_PATH):
        print(f"could not find template at {TEMPLATE_PATH}")
        return 2
    template = open(TEMPLATE_PATH, encoding='utf-8').read()

    jsonld_text = script_block(html, 'model-jsonld')
    ld, graph = parse_jsonld_graph(jsonld_text)
    if not graph:
        print("source has no JSON-LD @graph; cannot extract")
        return 2

    # If 'comp' is actually an IRI fragment of a class, find its component.
    target = comp
    if comp not in {n.get('component') for n in graph}:
        for n in graph:
            if n.get('@id') == comp or localname(n.get('@id','')) == comp.replace('cls-',''):
                if n.get('component'): target = n['component']; break

    classes_in, kept_op, kept_dp, kept_indiv, boundary = filter_for_component(graph, target)
    if not classes_in:
        print(f"no classes found for component '{target}'")
        return 2

    # Capture prefix declarations from the source Turtle (best-effort)
    ttl_src = script_block(html, 'domain-model')
    prefixes = '\n'.join(re.findall(r'(?m)^\s*@prefix[^\n]*', ttl_src))
    if not prefixes.strip():
        prefixes = """@prefix ex:   <http://example.org/PROJECT#> .
@prefix owl:  <http://www.w3.org/2002/07/owl#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix xsd:  <http://www.w3.org/2001/XMLSchema#> ."""

    new_turtle = emit_turtle(classes_in, boundary, kept_op, kept_dp, kept_indiv, target, prefixes)
    new_jsonld = emit_jsonld(ld.get('@context', {}), classes_in, boundary, kept_op, kept_dp, kept_indiv, target)
    new_md     = emit_markdown(target, classes_in, boundary, kept_op, kept_dp)

    out = template
    out = replace_script(out, 'domain-model',  new_turtle)
    out = replace_script(out, 'model-jsonld',  new_jsonld)
    out = replace_script(out, 'model-markdown', new_md)
    # If the source had DMN or Horn content for this component, we don't carry
    # it across automatically: a fresh subcomponent file is ontology-only by
    # default. (The downstream pass adds those layers if requested.)

    if out_path:
        open(out_path, 'w', encoding='utf-8').write(out)
        print(f"wrote standalone subcomponent '{target}' to {out_path} "
              f"({len(classes_in)} classes, {len(boundary)} boundary, "
              f"{len(kept_op)} object props, {len(kept_dp)} data props, "
              f"{len(kept_indiv)} individuals)")
    else:
        sys.stdout.write(out)
    return 0


if __name__ == '__main__':
    sys.exit(main())
