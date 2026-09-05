#!/usr/bin/env python3
"""
strip_layer.py — remove the `chat` layer from a model, recovering the predecessor.

The reversal of apply_layer.py: deletes the @LAYER:start chat … @LAYER:end chat
block and writes the result. Used by --regenerate (rebuild the layer) and as the
manual "open the predecessor" step the chain contract guarantees.

The strip logic itself is the layer platform's (domain-forge/scripts/
apply_layer.py: strip_layer), imported at run time — no private copy, no
fallback. `strip(apply(x)) == x` byte-for-byte.

Usage:  strip_layer.py MODEL.chat.html --out MODEL.html [--domain-forge-dir DIR]

Platform location: DIR from --domain-forge-dir, else $DOMAIN_FORGE_DIR, else the
sibling directory <skills>/domain-forge/scripts.
"""
import argparse, importlib.util, os, sys
from pathlib import Path

sys.dont_write_bytecode = True  # never leave a __pycache__ inside domain-forge


def load_platform(explicit=None):
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("model"); ap.add_argument("--out", required=True)
    ap.add_argument("--domain-forge-dir", help="domain-forge root or scripts/ dir (default: sibling skill, or $DOMAIN_FORGE_DIR)")
    a = ap.parse_args()
    platform = load_platform(a.domain_forge_dir)
    html = open(a.model, encoding="utf-8").read()
    try:
        new = platform.strip_layer(html, "chat")
    except KeyError:
        print("no chat layer found", file=sys.stderr); sys.exit(1)
    open(a.out, "w", encoding="utf-8").write(new)
    print("stripped chat layer -> %s" % a.out)

if __name__ == "__main__":
    main()
