#!/usr/bin/env python3
"""
strip_layer.py — remove a layer block from a domain-forge HTML.

The inverse of apply_layer.py for the `open-questions` layer (and any
other layer following the @LAYER:start/end convention). Reading the file
before and after a strip should produce a still-valid composed model.

The strip logic itself is the layer platform's (domain-forge/scripts/
apply_layer.py: strip_layer), imported at run time — no private copy, no
fallback. `strip(apply(x)) == x` byte-for-byte.

Usage:
    python strip_layer.py <input.html> --layer open-questions [--output out.html]
                          [--domain-forge-dir DIR]

If --output is omitted, the script writes to stdout.

Platform location: DIR from --domain-forge-dir, else $DOMAIN_FORGE_DIR, else
the sibling directory <skills>/domain-forge/scripts.

Exit codes:
    0 — wrote (or printed) successfully
    1 — generic error
    2 — platform scripts not found
    3 — no matching layer block found
"""

from __future__ import annotations

import argparse
import importlib.util
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True  # never leave a __pycache__ inside domain-forge


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


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("input", help="path to input HTML")
    p.add_argument("--layer", required=True, help="layer name to strip")
    p.add_argument("--output", help="output path (default: stdout)")
    p.add_argument(
        "--domain-forge-dir",
        help="domain-forge root or scripts/ dir (default: sibling skill, or $DOMAIN_FORGE_DIR)",
    )
    args = p.parse_args(argv)
    platform = load_platform(args.domain_forge_dir)

    html = Path(args.input).read_text(encoding="utf-8")
    try:
        new = platform.strip_layer(html, args.layer)
    except KeyError:
        print(f"ERROR: no `{args.layer}` layer found in {args.input}", file=sys.stderr)
        return 3
    if args.output:
        Path(args.output).write_text(new, encoding="utf-8")
        print(f"stripped layer `{args.layer}` (1 block(s)); wrote {args.output}")
    else:
        sys.stdout.write(new)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
