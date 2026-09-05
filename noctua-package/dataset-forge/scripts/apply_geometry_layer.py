#!/usr/bin/env python3
"""
apply_geometry_layer.py — validate a `layer-geometry-data` document and inject the
dataset-forge `geometry` layer (data + fixed render script + style + <noscript>) into a
domain-forge model HTML.

    python3 apply_geometry_layer.py MODEL.html --data LAYER.json --out OUT.html
                                    [--produced-by /dataset-forge]
                                    [--domain-forge-dir PATH]

Validation (references/report-contract.md §1): prints `ERROR:` and exits 2 on a schema
violation, `WARN:` for missing optional sections. The layer block is written ONLY by the
platform writer domain-forge/scripts/apply_layer.py (import first, CLI second) — this script
carries no copy of the block format or the digest algorithm, so there is exactly one of each.
If the platform writer cannot be found or fails, the script stops with `ERROR:` (exit 3) and
names the path it looked for; domain-forge is a hard dependency of dataset-forge anyway
(template, validator, engines). The input file is never modified.

Exit codes: 0 wrote OUT; 2 validation or input error; 3 platform writer missing or failed.
"""
from __future__ import annotations

import argparse
import html as _html
import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILL_DIR = HERE.parent
ASSETS = SKILL_DIR / "assets"
RENDER_JS = ASSETS / "geometry-render.js"
STYLE_CSS = ASSETS / "geometry-layer.css"
LAYER = "geometry"
SCHEMA = "dataset-forge/geometry@1"
STATUSES = {"confirmed", "refuted", "untested"}
REQUIRED_TOP = ("schema", "source", "typing", "space", "basis", "derivations", "partitions")
OPTIONAL_TOP = ("markers", "cycles", "disagreements", "orthogonality", "stats", "handoff", "explore",
                "functional_dependencies")
EXCLUDED_ROLES = {"identity", "key", "degenerate", "constant"}

_TURTLE_RE = re.compile(r'<script\s+id="domain-model"[^>]*>([\s\S]*?)</script>', re.IGNORECASE)
_BLOCK_RE = re.compile(r"[ \t]*<!--\s*@LAYER:start\s+" + LAYER + r"\b[\s\S]*?@LAYER:end\s+" + LAYER + r"\s*-->[ \t]*\n?")


# --------------------------------------------------------------------------- validation
def validate(doc, out):
    """Return list of errors; warnings are printed through `out`."""
    errs = []
    if not isinstance(doc, dict):
        return ["layer document is not a JSON object"]
    for k in REQUIRED_TOP:
        if k not in doc:
            errs.append(f"missing required top-level key {k!r}")
    if errs:
        return errs
    if doc.get("schema") != SCHEMA:
        errs.append(f"schema must be {SCHEMA!r}, got {doc.get('schema')!r}")
    src = doc["source"]
    if not isinstance(src, dict) or not src.get("path"):
        errs.append("source must be an object with at least 'path'")
    cols = src.get("columns") if isinstance(src, dict) else None
    if isinstance(cols, int):
        cols = None  # §1 allows a count; column names then come from typing
    if cols is not None and not (isinstance(cols, list) and all(isinstance(c, str) for c in cols)):
        errs.append("source.columns must be a list of column names (or an integer count)")
        cols = None

    typing = doc["typing"]
    if not isinstance(typing, list):
        errs.append("typing must be a list")
        typing = []
    roles = {}
    for i, t in enumerate(typing):
        if not isinstance(t, dict) or not t.get("column"):
            errs.append(f"typing[{i}] must be an object with 'column'")
            continue
        roles[t["column"]] = t.get("role", "dimension")
    known = list(cols) if cols else list(roles.keys())
    if not known:
        errs.append("no column names available (source.columns or typing)")

    space = doc["space"]
    if not isinstance(space, dict):
        errs.append("space must be an object")
    else:
        for k in ("ambient_dim", "exact_rank", "reading"):
            if k not in space:
                errs.append(f"space.{k} is required")

    basis = doc["basis"]
    members = []
    if not isinstance(basis, dict) or not isinstance(basis.get("members"), list):
        errs.append("basis must be an object with a 'members' list")
    else:
        members = basis["members"]
        non_identity = [c for c in known if roles.get(c, "dimension") not in EXCLUDED_ROLES]
        bad = [m for m in members if m not in non_identity]
        if bad:
            errs.append(f"basis.members must be a subset of the non-identity columns; offending: {bad}")
        if "size" in basis and basis["size"] != len(members):
            errs.append(f"basis.size {basis['size']} != len(members) {len(members)}")
        if "reading" not in basis:
            out(f"WARN: basis.reading missing")

    ders = doc["derivations"]
    if not isinstance(ders, list):
        errs.append("derivations must be a list")
        ders = []
    heads = {}
    for i, d in enumerate(ders):
        where = f"derivations[{i}]"
        if not isinstance(d, dict):
            errs.append(f"{where} must be an object")
            continue
        for k in ("column", "rule_id", "layer", "formula", "body", "provenance"):
            if k not in d:
                errs.append(f"{where} missing {k!r}")
        if not isinstance(d.get("body"), list) or not d.get("body"):
            errs.append(f"{where}.body must be a non-empty list")
        prov = d.get("provenance")
        if not isinstance(prov, dict):
            errs.append(f"{where}.provenance must be an object")
        else:
            for ch in ("semantic", "symbolic", "empirical"):
                st = (prov.get(ch) or {}).get("status") if isinstance(prov.get(ch), dict) else None
                if st not in STATUSES:
                    errs.append(f"{where}.provenance.{ch}.status must be one of {sorted(STATUSES)}, got {st!r}")
        col = d.get("column")
        if col in heads:
            errs.append(f"{where}: column {col!r} is the head of more than one derivation ({heads[col]}, {d.get('rule_id')})")
        heads[col] = d.get("rule_id")
        if col in members:
            errs.append(f"{where}: {col!r} is both a basis member and a derivation head")
        if known and col not in known:
            out(f"WARN: {where}: column {col!r} is not among the known columns")
        for b in d.get("body") or []:
            if known and b not in known:
                out(f"WARN: {where}: body column {b!r} is not among the known columns")
        if "consequences" not in d:
            out(f"WARN: {where} ({col}) has no consequence block")

    parts = doc["partitions"]
    if not isinstance(parts, dict):
        errs.append("partitions must be an object")
    else:
        if "candidates" not in parts:
            out("WARN: partitions.candidates missing (View D will list structural candidates only)")
        else:
            for i, c in enumerate(parts.get("candidates") or []):
                if not isinstance(c, dict) or not c.get("label"):
                    errs.append(f"partitions.candidates[{i}] must be an object with 'label'")
                    continue
                for k in ("features", "dropped_for_leakage"):
                    if k in c and not isinstance(c[k], list):
                        errs.append(f"partitions.candidates[{i}].{k} must be a list")
                if c.get("label") in (c.get("features") or []):
                    errs.append(f"partitions.candidates[{i}]: label {c['label']!r} is listed among its own features")
        if parts.get("provenance") not in (None, "user-chosen", "single-candidate", "abstained"):
            out(f"WARN: partitions.provenance {parts.get('provenance')!r} is not one of user-chosen | single-candidate | abstained")

    for k in ("disagreements", "stats", "handoff"):
        if k not in doc:
            out(f"WARN: optional section {k!r} missing")
    if "orthogonality" not in doc or not isinstance(doc.get("orthogonality"), dict) or "pairs" not in doc["orthogonality"]:
        out("WARN: orthogonality.pairs missing (View C renders its empty state)")
    ex = doc.get("explore")
    if not isinstance(ex, dict) or not isinstance(ex.get("columns"), dict):
        out("WARN: explore missing (Views A and C render their empty state)")
    else:
        n = max((len(v) for v in ex["columns"].values() if isinstance(v, list)), default=0)
        if n < 10:
            out(f"WARN: explore has {n} rows (< 10): Views A and C render their empty state")
        pca = ex.get("pca")
        if isinstance(pca, dict) and isinstance(pca.get("scores"), list) and len(pca["scores"]) != n:
            out(f"WARN: explore.pca.scores has {len(pca['scores'])} rows but columns have {n}; the rotated view is disabled")
    cyc = doc.get("cycles")
    if isinstance(cyc, list):
        rule_ids = {d.get("rule_id") for d in ders if isinstance(d, dict)}
        for i, c in enumerate(cyc):
            if not isinstance(c, dict) or not isinstance(c.get("members"), list):
                errs.append(f"cycles[{i}] must be an object with a 'members' list")
                continue
            for j, o in enumerate(c.get("orientations") or []):
                for r in o.get("rules") or []:
                    if isinstance(r, str) and r not in rule_ids:
                        errs.append(f"cycles[{i}].orientations[{j}] references unknown rule_id {r!r}")
                    elif isinstance(r, dict):
                        prov = r.get("provenance") or {}
                        for ch in ("semantic", "symbolic", "empirical"):
                            st = (prov.get(ch) or {}).get("status") if isinstance(prov.get(ch), dict) else None
                            if st not in STATUSES:
                                errs.append(f"cycles[{i}].orientations[{j}] rule {r.get('rule_id')!r}: provenance.{ch}.status must be one of {sorted(STATUSES)}")
    return errs


# --------------------------------------------------------------------------- noscript fallback
def _esc(s):
    return _html.escape("" if s is None else str(s), quote=True)


def _fmt(v):
    if isinstance(v, float):
        return f"{v:.6g}"
    return "" if v is None else str(v)


def noscript_html(doc):
    parts = ['<section class="layer-geometry-noscript">', "<h2>Geometry</h2>"]
    src = doc.get("source") or {}
    parts.append(f"<p><em>{_esc(src.get('path', 'dataset'))}</em></p>")
    parts.append("<h3>The space</h3>")
    parts.append(f"<p>{_esc((doc.get('space') or {}).get('reading', ''))}</p>")
    parts.append("<h3>The basis</h3>")
    b = doc.get("basis") or {}
    parts.append(f"<p>{_esc(', '.join(b.get('members') or []))}</p>")
    parts.append(f"<p>{_esc(b.get('reading', ''))}</p>")
    parts.append("<h3>Derivations</h3>")
    parts.append("<table><thead><tr><th>column</th><th>rule</th><th>layer</th><th>formula</th><th>body</th>"
                 "<th>semantic</th><th>symbolic</th><th>empirical</th></tr></thead><tbody>")
    for d in doc.get("derivations") or []:
        p = d.get("provenance") or {}
        parts.append("<tr>" + "".join(f"<td>{_esc(x)}</td>" for x in (
            d.get("column"), d.get("rule_id"), d.get("layer"), d.get("formula"), ", ".join(d.get("body") or []),
            (p.get("semantic") or {}).get("status"), (p.get("symbolic") or {}).get("status"),
            (p.get("empirical") or {}).get("status"))) + "</tr>")
    parts.append("</tbody></table>")
    if doc.get("orthogonality", {}).get("reading"):
        parts.append("<h3>Orthogonality</h3>")
        parts.append(f"<p>{_esc(doc['orthogonality']['reading'])}</p>")
    P = doc.get("partitions") or {}
    if P.get("candidates"):
        parts.append("<h3>Partition</h3>")
        for c in P["candidates"]:
            parts.append(f"<p><strong>{_esc(c.get('label'))}</strong> ({_esc(c.get('task', ''))}): features "
                         f"{_esc(', '.join(c.get('features') or []))}; dropped for leakage "
                         f"{_esc(', '.join(c.get('dropped_for_leakage') or []) or 'none')}.</p>")
    stats = doc.get("stats") or {}
    if stats:
        keys = []
        for col in stats.values():
            for k in (col or {}):
                if k not in keys:
                    keys.append(k)
        parts.append("<h3>Statistics</h3>")
        parts.append("<table><thead><tr><th>column</th>" + "".join(f"<th>{_esc(k)}</th>" for k in keys) + "</tr></thead><tbody>")
        for col, vals in stats.items():
            parts.append(f"<tr><th>{_esc(col)}</th>" + "".join(f"<td>{_esc(_fmt((vals or {}).get(k)))}</td>" for k in keys) + "</tr>")
        parts.append("</tbody></table>")
    parts.append("<p>Enable JavaScript for the interactive explorer (space, derivation graph, orthogonality, partition).</p>")
    parts.append("</section>")
    return "\n".join(parts)


# --------------------------------------------------------------------------- platform writer
def platform_writer_path(domain_forge_dir):
    p = Path(domain_forge_dir) / "scripts" / "apply_layer.py"
    return p if p.is_file() else None


def platform_apply(writer, html, data_text, render_js, style_css, produced_by, noscript, tmpdir, model_path, out_path):
    """Try the importable API first, then the CLI. Returns (html_or_None, how)."""
    notes = []
    sys.dont_write_bytecode = True  # never leave a __pycache__ inside domain-forge/
    try:
        spec = importlib.util.spec_from_file_location("df_apply_layer", str(writer))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        fn = getattr(mod, "apply_layer")
        result = fn(html, LAYER, data_text, render_js, style_css=style_css, data_type="application/json",
                    produced_by=produced_by, noscript_html=noscript)
        if isinstance(result, str) and f"@LAYER:start {LAYER}" in result:
            return result, "platform writer (import)"
        notes.append("import path returned no layer block")
    except Exception as e:  # noqa: BLE001 — fall through to the CLI
        notes.append(f"import path failed: {e}")
    try:
        tmp = Path(tmpdir)
        d = tmp / "layer.json"; d.write_text(data_text, encoding="utf-8")
        r = tmp / "geometry-render.js"; r.write_text(render_js, encoding="utf-8")
        s = tmp / "geometry-layer.css"; s.write_text(style_css, encoding="utf-8")
        n = tmp / "noscript.html"; n.write_text(noscript, encoding="utf-8")
        o = tmp / "out.html"
        cmd = [sys.executable, str(writer), str(model_path), "--layer", LAYER, "--data", str(d), "--render", str(r),
               "--style", str(s), "--data-type", "application/json", "--produced-by", produced_by,
               "--noscript", str(n), "--out", str(o)]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if proc.returncode == 0 and o.is_file():
            return o.read_text(encoding="utf-8"), "platform writer (CLI)"
        notes.append(f"CLI path failed (exit {proc.returncode}): {(proc.stderr or proc.stdout).strip()[:300]}")
    except Exception as e:  # noqa: BLE001
        notes.append(f"CLI path failed: {e}")
    return None, "; ".join(notes)


# --------------------------------------------------------------------------- main
def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("model", help="input MODEL.html (never modified)")
    ap.add_argument("--data", required=True, help="layer-geometry-data JSON document")
    ap.add_argument("--out", required=True, help="output HTML path (must differ from MODEL)")
    ap.add_argument("--produced-by", default="/dataset-forge")
    ap.add_argument("--domain-forge-dir", default=None,
                    help="domain-forge skill directory (default: sibling of dataset-forge)")
    ap.add_argument("--render", default=str(RENDER_JS), help=argparse.SUPPRESS)
    ap.add_argument("--style", default=str(STYLE_CSS), help=argparse.SUPPRESS)
    a = ap.parse_args(argv)

    model_path = Path(a.model)
    out_path = Path(a.out)
    if model_path.resolve() == out_path.resolve():
        print("ERROR: --out must differ from the input model (the input is never modified)")
        return 2
    try:
        html = model_path.read_text(encoding="utf-8")
    except OSError as e:
        print(f"ERROR: cannot read model {model_path}: {e}")
        return 2
    try:
        data_text = Path(a.data).read_text(encoding="utf-8")
        doc = json.loads(data_text)
    except (OSError, json.JSONDecodeError) as e:
        print(f"ERROR: cannot read layer data {a.data}: {e}")
        return 2
    for p in (Path(a.render), Path(a.style)):
        if not p.is_file():
            print(f"ERROR: asset missing: {p}")
            return 2
    render_js = Path(a.render).read_text(encoding="utf-8").rstrip()
    style_css = Path(a.style).read_text(encoding="utf-8").rstrip()
    if len(render_js.encode("utf-8")) > 80 * 1024:
        print(f"ERROR: render script is {len(render_js.encode('utf-8'))} bytes; contract §6 caps it at 80 KB")
        return 2

    errs = validate(doc, print)
    if errs:
        for e in errs:
            print(f"ERROR: {e}")
        return 2
    print(f"OK: {a.data} validates against {SCHEMA} "
          f"({len(doc.get('derivations') or [])} derivations, basis of {len((doc.get('basis') or {}).get('members') or [])})")

    # Serialize the data compactly-but-readably; sort_keys=False keeps the author's order.
    data_text = json.dumps(doc, ensure_ascii=False, separators=(",", ":"))
    noscript = noscript_html(doc)

    domain_forge_dir = Path(a.domain_forge_dir) if a.domain_forge_dir else SKILL_DIR.parent / "domain-forge"
    writer = platform_writer_path(domain_forge_dir)
    if not writer:
        print(f"ERROR: platform writer not found at {domain_forge_dir / 'scripts' / 'apply_layer.py'}; "
              "dataset-forge writes layers only through domain-forge's apply_layer.py "
              "(pass --domain-forge-dir if the skill lives elsewhere)")
        return 3
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        result, how = platform_apply(writer, html, data_text, render_js, style_css, a.produced_by, noscript,
                                     td, model_path, out_path)
    if result is None:
        print(f"ERROR: platform writer {writer} failed ({how})")
        return 3
    if _BLOCK_RE.search(html):
        print("WARN: input already carried a geometry layer; it was replaced")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(result, encoding="utf-8")
    print(f"OK: wrote {out_path} via {how}")
    print(f"OK: render script {len(render_js.encode('utf-8'))} bytes, data {len(data_text.encode('utf-8'))} bytes, "
          f"output {len(result.encode('utf-8'))} bytes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
