#!/usr/bin/env python3
"""
build_viewers.py — generate per-capability standalone viewer HTML files.

For each capability under engine-source/capabilities/<id>/, this script
takes:

  - viewer-template.html             (one shared shell with {{placeholders}})
  - capabilities/<id>/viewer-meta.json   (title, description, focus, default KB)
  - capabilities/<id>/logic.js + the other capabilities' logic.js
                                      (assembled engine body)

and writes the standalone viewer to capabilities/<id>/viewer.html.

The viewer is self-contained: full reasoner inlined, KB editable in-browser,
"Save snapshot" downloads a new HTML, "Revert" restores the embedded
original. Honours the user's snapshot principle: the shipped viewer.html is
the source of truth; any new state lives in a new snapshot file or in the
working textarea with revert always available.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

PLACEHOLDERS = (
    '{{TITLE}}', '{{DESCRIPTION}}', '{{DEFAULT_KB_JSONLD}}', '{{CAP_ID}}',
    '{{FOCUS_PROV_KINDS}}', '{{FOCUS_PROV_KINDS_JS}}',
    '{{LOADED_CAPABILITIES}}', '{{ENGINE_BODY}}',
)


def read_capabilities(engine_dir: str) -> list[dict]:
    meta = json.load(open(os.path.join(engine_dir, 'meta.json'), encoding='utf-8'))
    return meta.get('capabilities') or []


def assemble_engine_body(engine_dir: str, caps: list[dict]) -> str:
    parts = []
    for c in caps:
        logic = open(os.path.join(engine_dir, 'capabilities', c['id'], 'logic.js'),
                     encoding='utf-8').read().rstrip()
        # Re-indent every line by two spaces so the body slots cleanly inside
        # the viewer's <script> IIFE indentation level.
        indented = '\n'.join(('  ' + ln if ln.strip() else ln) for ln in logic.splitlines())
        parts.append(indented)
    return '\n\n'.join(parts)


def build(engine_dir: str) -> None:
    template_path = os.path.join(engine_dir, 'viewer-template.html')
    if not os.path.isfile(template_path):
        raise SystemExit(f"viewer template not found: {template_path}")
    template = open(template_path, encoding='utf-8').read()

    caps = read_capabilities(engine_dir)
    engine_body = assemble_engine_body(engine_dir, caps)
    loaded_caps_str = ', '.join(c['id'] for c in caps)

    built = []
    for c in caps:
        cap_id = c['id']
        cap_dir = os.path.join(engine_dir, 'capabilities', cap_id)
        meta_path = os.path.join(cap_dir, 'viewer-meta.json')
        if not os.path.isfile(meta_path):
            print(f"  skip {cap_id} — no viewer-meta.json", file=sys.stderr)
            continue
        vmeta = json.load(open(meta_path, encoding='utf-8'))
        title         = vmeta.get('title', c['title'])
        description   = vmeta.get('description', '')
        focus_kinds   = vmeta.get('focusProvKinds') or []
        default_kb    = vmeta.get('defaultKB') or {'@graph': []}
        # JS-compatible Set literal for focus kinds
        focus_kinds_js = '[' + ', '.join(f'"{k}"' for k in focus_kinds) + ']'

        out = template
        out = out.replace('{{TITLE}}', title)
        out = out.replace('{{DESCRIPTION}}', description)
        out = out.replace('{{CAP_ID}}', cap_id)
        out = out.replace('{{FOCUS_PROV_KINDS}}', ', '.join(focus_kinds) or '(all)')
        out = out.replace('{{FOCUS_PROV_KINDS_JS}}', focus_kinds_js)
        out = out.replace('{{LOADED_CAPABILITIES}}', loaded_caps_str)
        out = out.replace('{{DEFAULT_KB_JSONLD}}',
                          json.dumps(default_kb, indent=2, ensure_ascii=False))
        out = out.replace('{{ENGINE_BODY}}', engine_body)

        # Sanity check: every placeholder substituted.
        unresolved = [p for p in PLACEHOLDERS if p in out]
        if unresolved:
            raise SystemExit(f"{cap_id}: unresolved placeholder(s) {unresolved}")

        viewer_path = os.path.join(cap_dir, 'viewer.html')
        with open(viewer_path, 'w', encoding='utf-8') as fh:
            fh.write(out)
        built.append((cap_id, viewer_path, len(out)))

    print(f'built {len(built)} viewer(s):')
    for cap_id, p, n in built:
        print(f"  {cap_id} → {p}  ({n:,} bytes)")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument('--engine-dir', '-e', default='assets/engine-source',
                    help='Path to engine-source directory (default: assets/engine-source)')
    args = ap.parse_args()
    if not os.path.isdir(args.engine_dir):
        print(f"engine source not found: {args.engine_dir}", file=sys.stderr)
        return 2
    try:
        build(args.engine_dir)
    except SystemExit as e:
        print(e, file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
