#!/usr/bin/env python3
"""
explode_engine.py — extract the inference engine from a composed HTML
                   (or assets/template.html) into per-capability source files.

The engine lives in assets/template.html (and in every composed model.html)
between the markers:

    /* @ENGINE_BLOCK_START — ... */
    ... functions ...
    /* @ENGINE_BLOCK_END */

Within the block, each capability is delimited by a header comment:

    // ── capability: NN-name ──...

This script slices on those headers and writes each capability to
assets/engine-source/capabilities/NN-name/logic.js. It also derives a
small meta.json per capability (id, title, exported function names) so
compose_engine.py can reassemble them in load order.

Run this any time you want to refresh the source folder from a composed
model.html (round-trip). The reverse — assembling a composed file from
the source folder — is compose_engine.py.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys

# IMPORTANT: use [ \t]* not \s* — the greedy `\s*` eats preceding newlines,
# which makes m.start() land at the start of an earlier blank line and pulls
# leading blank lines into the capability's slice. That drift compounds with
# every round-trip (1 extra blank line per pass per capability boundary).
CAP_HEADER_RE = re.compile(
    r'^([ \t]*// ── capability:\s*([0-9a-zA-Z\-]+)\s*──[^\n]*)\n',
    re.M,
)
BLOCK_START = '/* @ENGINE_BLOCK_START'
BLOCK_END   = '/* @ENGINE_BLOCK_END */'

# matchAntecedent / matchAtom / unify are pure dependencies of capability
# 40-swrl-forward-chain. They live OUTSIDE the marker block in the template
# (historical reasons). We pull them in and PREPEND them to 40's logic.js
# so the capability is self-contained when read in isolation — and the
# composer doesn't need a separate substitution anchor.


def slice_engine_block(template_text: str) -> str:
    """Return the text between @ENGINE_BLOCK_START and @ENGINE_BLOCK_END."""
    s = template_text.find(BLOCK_START)
    e = template_text.find(BLOCK_END)
    if s < 0 or e < 0:
        raise SystemExit("engine block markers not found in template — has the "
                         "reasoner been refactored under @ENGINE_BLOCK_START/_END?")
    # Skip past the opening comment terminator */
    s = template_text.find('*/', s) + 2
    return template_text[s:e].strip('\n')


def split_into_capabilities(block: str) -> list[tuple[str, str]]:
    """Slice on `// ── capability: NN-name ──` headers. Returns [(id, body)]."""
    matches = list(CAP_HEADER_RE.finditer(block))
    if not matches:
        raise SystemExit("no capability headers found inside engine block")
    out = []
    for i, m in enumerate(matches):
        cap_id = m.group(2)
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(block)
        out.append((cap_id, block[start:end].rstrip() + '\n'))
    return out


def derive_exports(body: str) -> list[str]:
    """List the function names defined at the top level of a logic.js body."""
    return re.findall(r'^\s*function\s+([A-Za-z_][\w$]*)\s*\(', body, re.M)


def derive_title(cap_id: str) -> str:
    """`30-property-characteristics` → `Property characteristics`."""
    parts = cap_id.split('-', 1)
    name = parts[1] if len(parts) > 1 else cap_id
    return name.replace('-', ' ').capitalize()


def find_swrl_helpers(template_text: str) -> str:
    """
    On older templates, matchAntecedent / matchAtom / unify lived AFTER the
    engine block. Pull them in if they're there so capability 40 ends up
    self-contained.

    Critically: we ONLY look after `/* @ENGINE_BLOCK_END */`. If the helpers
    are already inside the engine block (the canonical layout after one
    round-trip), we leave them alone — re-extracting them would create a
    duplicate when explode prepends them into capability 40's logic.js.
    """
    end_marker = '/* @ENGINE_BLOCK_END */'
    end_idx = template_text.find(end_marker)
    search_region = template_text[end_idx:] if end_idx >= 0 else template_text
    region_offset = end_idx if end_idx >= 0 else 0
    out = []
    for name in ('matchAntecedent', 'unify', 'matchAtom'):
        m = re.search(
            rf'^\s*function\s+{re.escape(name)}\s*\([^)]*\)\s*\{{',
            search_region, re.M,
        )
        if not m:
            continue
        # Walk braces in the original text to find the function's closing }.
        i = region_offset + m.end() - 1
        depth, j = 1, i + 1
        while j < len(template_text) and depth > 0:
            if template_text[j] == '{':
                depth += 1
            elif template_text[j] == '}':
                depth -= 1
            j += 1
        out.append(template_text[region_offset + m.start():j].rstrip() + '\n')
    return '\n'.join(out)


def explode(template_path: str, out_dir: str) -> None:
    with open(template_path, encoding='utf-8') as fh:
        template = fh.read()

    block = slice_engine_block(template)
    caps = split_into_capabilities(block)

    os.makedirs(os.path.join(out_dir, 'capabilities'), exist_ok=True)

    # The SWRL antecedent-matching helpers live outside the marker block in
    # the original template but are pure dependencies of capability 40. Pull
    # them in and prepend them to 40's logic.js so the capability is
    # self-contained when read alone (and the composer has one less anchor).
    swrl_extras_raw = find_swrl_helpers(template)
    swrl_extras = '\n'.join(
        (ln[2:] if ln.startswith('  ') else ln) for ln in swrl_extras_raw.splitlines()
    ) + ('\n' if swrl_extras_raw else '')

    cap_index = []
    for cap_id, body in caps:
        cap_dir = os.path.join(out_dir, 'capabilities', cap_id)
        os.makedirs(cap_dir, exist_ok=True)
        # Strip a single leading indent of 2 spaces so logic.js reads naturally
        # as a top-level module. The composer re-indents on the way back in.
        normalised = '\n'.join(
            (ln[2:] if ln.startswith('  ') else ln) for ln in body.splitlines()
        ) + '\n'
        # For capability 40, prepend the SWRL helpers as antecedent-matching
        # support. They are pure functions with no side effects.
        if cap_id.startswith('40-swrl') and swrl_extras:
            normalised = (
                '// ── support: SWRL antecedent matching ──\n'
                '// Pure helpers used by inferSWRL(). matchAtom dispatches on\n'
                '// atom.type (class/objectProperty/dataProperty/builtin/sameAs/\n'
                '// differentFrom); matchAntecedent threads bindings; unify\n'
                '// implements first-order unification on variables/literals.\n'
                + swrl_extras
                + '\n'
                + normalised
            )
        with open(os.path.join(cap_dir, 'logic.js'), 'w', encoding='utf-8') as fh:
            fh.write(normalised)
        meta = {
            'id': cap_id,
            'title': derive_title(cap_id),
            'exports': derive_exports(normalised),
        }
        with open(os.path.join(cap_dir, 'meta.json'), 'w', encoding='utf-8') as fh:
            json.dump(meta, fh, indent=2)
        cap_index.append(meta)

    # Top-level meta — the load order. The composer reassembles in this order.
    top = {
        'version': '1.0',
        'description': 'domain-forge inference engine — per-capability source',
        'capabilities': cap_index,
    }
    with open(os.path.join(out_dir, 'meta.json'), 'w', encoding='utf-8') as fh:
        json.dump(top, fh, indent=2)

    print(f'exploded engine from {template_path} → {out_dir}')
    for c in cap_index:
        n = len(c['exports'])
        print(f"  capabilities/{c['id']}/logic.js  ({n} function{'' if n==1 else 's'}: "
              f"{', '.join(c['exports'])})")
    if swrl_extras:
        print(f"  (matchAntecedent/unify/matchAtom prepended into 40-swrl-forward-chain)")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument('template', help='Path to a composed HTML or assets/template.html')
    ap.add_argument('--out', '-o', required=True, help='Output engine-source directory')
    args = ap.parse_args()
    if not os.path.isfile(args.template):
        print(f"template not found: {args.template}", file=sys.stderr)
        return 2
    try:
        explode(args.template, args.out)
    except SystemExit as e:
        print(e, file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
