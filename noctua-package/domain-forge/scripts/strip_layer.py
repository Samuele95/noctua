#!/usr/bin/env python3
"""
strip_layer.py — remove @LAYER blocks from a domain-forge model, or list them.

Purpose
-------
The inverse of apply_layer.py. Stripping the layer apply_layer.py just added
returns bytes identical to the original input (the block plus the one
trailing newline the writer appends). Any combination of layers can be
stripped because layers are pure-additive; the result is a well-formed model.

/model-chat and /inferred-questions write their layers through apply_layer.py,
so those layers strip the same way. Legacy tolerance: a `chat` layer written
by model-chat's former private writer (render tag without a `type` attribute)
also loses the single newline that writer prepended, so old files round-trip
byte-exactly too (see apply_layer.strip_layer / _is_legacy_model_chat_block).

CLI
---
    strip_layer.py MODEL.html --layer NAME --out OUT.html   remove one layer
    strip_layer.py MODEL.html --all --out OUT.html          remove every layer
    strip_layer.py MODEL.html --list                        print the layers
                                                            (produced-by / produced-at /
                                                            input-digest, and whether the
                                                            digest matches the current Turtle)

Markers printed on stdout: `OK:` / `WARN:` / `ERROR:`.

Exit codes
----------
    0 — done (for --list: listed, even when there are no layers)
    1 — the requested layer is not present / nothing to strip / OUT == MODEL
    2 — could not read the input / usage error
"""
import argparse
import os
import sys

sys.dont_write_bytecode = True  # never leave a __pycache__ inside the skill directory

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from apply_layer import list_layers, strip_layer, domain_digest  # noqa: E402


def main(argv=None):
    ap = argparse.ArgumentParser(description="Strip or list @LAYER blocks.")
    ap.add_argument("model", help="input MODEL.html (never modified)")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--layer", help="layer NAME to strip")
    g.add_argument("--all", action="store_true", help="strip every layer")
    g.add_argument("--list", action="store_true", help="list the layers and exit")
    ap.add_argument("--out", help="output path (required with --layer / --all)")
    a = ap.parse_args(argv)

    try:
        with open(a.model, encoding="utf-8") as fh:
            html = fh.read()
    except OSError as e:
        print(f"ERROR: cannot read {a.model}: {e}")
        return 2

    layers = list_layers(html)

    if a.list:
        cur = domain_digest(html)
        if not layers:
            print(f"OK: {a.model} carries no @LAYER blocks (current Turtle digest {cur})")
            return 0
        print(f"OK: {len(layers)} layer(s) in {a.model} (current Turtle digest {cur})")
        for L in layers:
            match = "matches" if L["input_digest"] == cur else "STALE"
            print(f"  - {L['name']}"
                  f"{' v' + str(L['version']) if L['version'] is not None else ''}"
                  f"  produced-by={L['produced_by'] or '?'}"
                  f"  produced-at={L['produced_at'] or '?'}"
                  f"  input-digest={L['input_digest'] or '?'} ({match})"
                  f"  span={L['start']}..{L['end']}")
        return 0

    if not a.out:
        print("ERROR: --out is required with --layer / --all")
        return 2
    if os.path.abspath(a.out) == os.path.abspath(a.model) or (
            os.path.exists(a.out) and os.path.samefile(a.out, a.model)):
        print(f"ERROR: --out resolves to the input path {a.model}; the input is never modified")
        return 1

    if a.all:
        if not layers:
            print(f"ERROR: {a.model} carries no @LAYER blocks; nothing to strip")
            return 1
        out = html
        names = []
        # Strip from the last layer backwards so earlier offsets stay valid.
        for L in reversed(layers):
            out = strip_layer(out, L["name"])
            names.append(L["name"])
        names.reverse()
    else:
        try:
            out = strip_layer(html, a.layer)
        except KeyError:
            have = ", ".join(L["name"] for L in layers) or "none"
            print(f"ERROR: no layer {a.layer!r} in {a.model} (layers present: {have})")
            return 1
        names = [a.layer]

    with open(a.out, "w", encoding="utf-8") as fh:
        fh.write(out)
    print(f"OK: stripped layer(s) {', '.join(names)} -> {a.out} "
          f"(-{len(html) - len(out)} chars)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
