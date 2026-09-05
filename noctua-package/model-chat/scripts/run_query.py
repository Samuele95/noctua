#!/usr/bin/env python3
"""
run_query.py — execute ONE query against a domain-forge model's OWN engines.

This is the grounding core of /model-chat. It never answers from an LLM: it
drives the engines the model already ships, headlessly, and returns their raw
result as JSON. The input HTML is treated read-only (a temp copy is used).

This file is a thin shim: the headless engine driver is the layer platform's
(domain-forge/scripts/run_query.py) and is executed here with the same argv,
same stdout JSON and same exit code — no private copy, no fallback.

Usage (unchanged; see the platform script for the engine details):
  run_query.py MODEL.html --engine sparql --query 'SELECT ?t WHERE { ?t a ex:Transaction }'
  run_query.py MODEL.html --engine swrl   --query 'SELECT ?t WHERE { ?t a ex:FraudulentTransaction }'
  run_query.py MODEL.html --engine prolog --query 'outcome(tx_r2, O).'
  run_query.py MODEL.html --engine dmn    --dmn-inputs '{"Payment Amount":11234, ...}'
  [--timeout N] [--domain-forge-dir DIR]

Prints a JSON object to stdout:
  { "ok": bool, "engine": str, "query": str, "result": <any>, "raw": str, "error": str|null }
Exit code 0 if the query executed (ok=true), 1 otherwise; 2 if the platform
script cannot be found.

Platform location: DIR from --domain-forge-dir, else $DOMAIN_FORGE_DIR, else the
sibling directory <skills>/domain-forge/scripts. A browser is found via $CHROME
or PATH (google-chrome / chromium / …).
"""
import os, runpy, sys
from pathlib import Path

sys.dont_write_bytecode = True  # never leave a __pycache__ inside domain-forge


def locate_platform(explicit=None):
    """Path of domain-forge/scripts/run_query.py. Exit 2 if absent."""
    base = explicit or os.environ.get("DOMAIN_FORGE_DIR") or \
        Path(__file__).resolve().parents[2] / "domain-forge" / "scripts"
    base = Path(base)
    path = base / "scripts" / "run_query.py"
    if not path.is_file():
        path = base / "run_query.py"
    if not path.is_file():
        print(f"ERROR: platform scripts not found at {base} — domain-forge is a "
              "required sibling of this skill", file=sys.stderr)
        sys.exit(2)
    return path


def main():
    # Pull our one local flag out of argv; everything else is forwarded verbatim.
    argv, explicit, i = [], None, 1
    while i < len(sys.argv):
        arg = sys.argv[i]
        if arg == "--domain-forge-dir" and i + 1 < len(sys.argv):
            explicit = sys.argv[i + 1]; i += 2; continue
        if arg.startswith("--domain-forge-dir="):
            explicit = arg.split("=", 1)[1]; i += 1; continue
        argv.append(arg); i += 1
    path = locate_platform(explicit)
    sys.argv = [sys.argv[0]] + argv
    runpy.run_path(str(path), run_name="__main__")

if __name__ == "__main__":
    main()
