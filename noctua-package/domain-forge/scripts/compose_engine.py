#!/usr/bin/env python3
"""
compose_engine.py — reassemble the inference engine from per-capability source
                   files back into assets/template.html (or any composed HTML).

Pairs with explode_engine.py:

    explode_engine.py  template.html → engine-source/
    compose_engine.py  engine-source/ → template.html  (substitutes the block
                                                       between the markers)

The substitution target is the region between:

    /* @ENGINE_BLOCK_START — ... */
    ...                                  ← REPLACED
    /* @ENGINE_BLOCK_END */

Reads engine-source/meta.json for the capability load order and reads each
capability's logic.js (re-indented to match the template's leading two spaces).
00-core's extras.js (if present — SWRL antecedent/atom helpers) is inserted
right after the engine block, where those helpers historically lived. The
composed file is a self-contained domain-forge HTML, byte-identical to what
the user would have written by editing the template directly — that's the
guarantee of the round-trip.

This script does NOT touch the data scripts (Turtle, JSON-LD, etc.). Pair
with compose_model.py if you want to assemble a model from data sources too.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys

BLOCK_START_PAT = re.compile(
    r'/\*\s*@ENGINE_BLOCK_START[\s\S]*?\*/',
)
BLOCK_END_MARKER = '/* @ENGINE_BLOCK_END */'

SWRL_HELPER_NAMES = ('matchAntecedent', 'unify', 'matchAtom')
SWRL_HEADER = '/* SWRL antecedent matching */'


def strip_standalone_swrl_helpers(text: str) -> str:
    """Remove the standalone matchAntecedent/unify/matchAtom block left over
    from the pre-modular template. We walk braces rather than regex so the
    inner braces of for/if/forEach don't trick a non-greedy match into
    stopping early (the bug that left fragments of matchAntecedent behind).
    Idempotent — leaves text alone if the helpers are already gone."""
    # Step 1: find the comment if it exists.
    start = text.find(SWRL_HEADER)
    if start < 0:
        # No comment header — try jumping straight to the first standalone helper.
        for name in SWRL_HELPER_NAMES:
            m = re.search(rf'\n\s*function\s+{name}\s*\(', text)
            if m:
                start = m.start()
                break
    if start < 0:
        return text  # nothing to strip

    # Step 2: walk forward, brace-balancing through each helper function.
    i = start
    # Eat the leading newline so we don't leave a blank line.
    while i > 0 and text[i - 1] in ' \t':
        i -= 1
    j = start
    consumed_any = False
    while True:
        # Skip whitespace + the comment line if present
        m = re.match(r'\s*(?:/\*\s*SWRL antecedent matching\s*\*/\s*)?', text[j:])
        if m:
            j += m.end()
        m = re.match(r'\s*function\s+(' + '|'.join(SWRL_HELPER_NAMES) + r')\s*\([^)]*\)\s*\{',
                     text[j:])
        if not m:
            break
        # Walk braces from after the opening '{'
        depth, k = 1, j + m.end()
        while k < len(text) and depth > 0:
            if text[k] == '{':
                depth += 1
            elif text[k] == '}':
                depth -= 1
            k += 1
        j = k
        consumed_any = True
    if not consumed_any:
        return text
    # Step 3: also eat one trailing newline so removal is clean.
    if j < len(text) and text[j] == '\n':
        j += 1
    return text[:i] + text[j:]


def read_capabilities(engine_dir: str) -> list[dict]:
    meta_path = os.path.join(engine_dir, 'meta.json')
    if not os.path.isfile(meta_path):
        raise SystemExit(f"{meta_path} not found — run explode_engine.py first "
                         f"or hand-write meta.json with a 'capabilities' list")
    with open(meta_path, encoding='utf-8') as fh:
        meta = json.load(fh)
    caps = meta.get('capabilities') or []
    if not caps:
        raise SystemExit("meta.json has no capabilities list")
    return caps


def indent_2(text: str) -> str:
    """Re-add the two-space leading indent the runtime IIFE uses."""
    return '\n'.join(('  ' + ln if ln.strip() else ln) for ln in text.splitlines())


def assemble_block(engine_dir: str, caps: list[dict]) -> str:
    parts = []
    for c in caps:
        cap_id = c['id']
        logic_path = os.path.join(engine_dir, 'capabilities', cap_id, 'logic.js')
        if not os.path.isfile(logic_path):
            raise SystemExit(f"missing logic.js for capability {cap_id}: {logic_path}")
        with open(logic_path, encoding='utf-8') as fh:
            parts.append(indent_2(fh.read().rstrip()))
    return '\n\n'.join(parts)


def compose(engine_dir: str, target_html: str, out_html: str) -> None:
    caps = read_capabilities(engine_dir)
    block = assemble_block(engine_dir, caps)

    with open(target_html, encoding='utf-8') as fh:
        text = fh.read()

    # 1. Strip the standalone SWRL helpers (matchAntecedent/unify/matchAtom)
    # that used to live below the engine block. They are now inside capability
    # 40 and would otherwise be duplicated.
    text = strip_standalone_swrl_helpers(text)

    # 2. Replace the engine block between markers.
    start_m = BLOCK_START_PAT.search(text)
    if not start_m:
        raise SystemExit("could not find /* @ENGINE_BLOCK_START ... */ in target")
    end_idx = text.find(BLOCK_END_MARKER, start_m.end())
    if end_idx < 0:
        raise SystemExit("could not find /* @ENGINE_BLOCK_END */ in target")

    # Reconstruct: keep the opening comment, replace body, keep the closer.
    opening = text[start_m.start():start_m.end()]
    closing = BLOCK_END_MARKER
    new_block = f"{opening}\n\n{block}\n\n  {closing}"
    text = text[:start_m.start()] + new_block + text[end_idx + len(BLOCK_END_MARKER):]

    os.makedirs(os.path.dirname(os.path.abspath(out_html)) or '.', exist_ok=True)
    with open(out_html, 'w', encoding='utf-8') as fh:
        fh.write(text)

    print(f'composed engine from {engine_dir} → {out_html}')
    print(f'  {len(caps)} capability/capabilities: '
          f"{', '.join(c['id'] for c in caps)}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument('engine_dir', help='Path to engine-source/')
    ap.add_argument('--target', '-t', required=True,
                    help='Target HTML (template or composed model)')
    ap.add_argument('--out', '-o', required=True, help='Output HTML path')
    args = ap.parse_args()
    if not os.path.isdir(args.engine_dir):
        print(f"engine source not found: {args.engine_dir}", file=sys.stderr)
        return 2
    if not os.path.isfile(args.target):
        print(f"target HTML not found: {args.target}", file=sys.stderr)
        return 2
    try:
        compose(args.engine_dir, args.target, args.out)
    except SystemExit as e:
        print(e, file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
