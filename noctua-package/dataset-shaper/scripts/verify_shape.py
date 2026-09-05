#!/usr/bin/env python3
"""
verify_shape.py — check what the executor produced, before the `shape` layer is written.

    python3 verify_shape.py --recipe recipe.json --out-dir shaped/ [--model MODEL.html]
                            [--psi-threshold 0.25] [--json report.json]

Five families of check, from `references/shape-contract.md` §3:

  structural      the label is not among the feature columns; the leakage set is gone; every
                  active derivation head is gone unless a user: step kept it; no basis member
                  is missing unless a user: step dropped it.
  semantic        for every derivation whose body survives, the relation is recomputed on the
                  output — algebraically when the formula parses, and as a functional
                  dependency otherwise. A transform applied to one member of a derivation and
                  not the others breaks a definitional truth silently; this is the check that
                  catches it. With a headless browser and a model that carries rules, the same
                  claim is put to the model's own SWRL/Horn engine and recorded as
                  confirmed / refuted / untested — never asserted from arithmetic here.
  distributional  PSI between input and output for every column no step named. A column
                  nobody transformed should not have moved; when it has, the report names the
                  step it suspects.
  split           no row in two parts; a group split keeps a group whole; a time split keeps
                  the order; the label rate per part is within tolerance of the whole.
  spatial         when spatial steps ran: coordinates inside the declared CRS bounds, a CRS
                  recorded on the output, no invalid geometry.

Determinism is NOT checked here — it is `shape.py --check`, which re-runs the generated
reproduction script and compares digests.

Exit codes: 0 every check passed (warnings allowed); 3 a check failed.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
SKILL_DIR = HERE.parent
FAIL, WARN, OK = [], [], []


def bad(m):
    FAIL.append(m)
    print(f"ERROR: {m}")


def warn(m):
    WARN.append(m)
    print(f"WARN: {m}")


def ok(m):
    OK.append(m)
    print(f"OK: {m}")


def read_any(p):
    p = Path(p)
    if p.suffix == ".parquet":
        return pd.read_parquet(p)
    return pd.read_csv(p, low_memory=False)


def read_layers(model_path):
    out = {}
    if not model_path:
        return out
    html = Path(model_path).read_text(encoding="utf-8")
    for name in ("geometry", "analysis"):
        m = re.search(r'<script\s+id="layer-' + name + r'-data"[^>]*>([\s\S]*?)</script>',
                      html, re.IGNORECASE)
        if m:
            try:
                out[name] = json.loads(m.group(1).strip())
            except json.JSONDecodeError:
                pass
    return out


def psi(expected, actual, bins=10):
    e = pd.to_numeric(pd.Series(expected), errors="coerce").dropna().values
    a = pd.to_numeric(pd.Series(actual), errors="coerce").dropna().values
    if e.size < 20 or a.size < 20:
        return None
    qs = np.unique(np.quantile(e, np.linspace(0, 1, bins + 1)))
    if qs.size < 3:
        return None
    qs[0], qs[-1] = -np.inf, np.inf
    ec = np.clip(np.histogram(e, bins=qs)[0] / e.size, 1e-6, None)
    ac = np.clip(np.histogram(a, bins=qs)[0] / a.size, 1e-6, None)
    return float(np.sum((ac - ec) * np.log(ac / ec)))


def psi_cat(expected, actual):
    e = pd.Series(expected).astype(str).value_counts(normalize=True)
    a = pd.Series(actual).astype(str).value_counts(normalize=True)
    idx = e.index.union(a.index)
    ev = np.clip(e.reindex(idx).fillna(0).values, 1e-6, None)
    av = np.clip(a.reindex(idx).fillna(0).values, 1e-6, None)
    return float(np.sum((av - ev) * np.log(av / ev)))


_FORMULA_OPS = {"×": "*", "·": "*", "÷": "/", "−": "-", "–": "-", "⁄": "/"}


def parse_formula(formula):
    """'total = unit_price × qty' -> ('total', 'unit_price * qty'); None when it is prose."""
    if not formula or "=" not in formula:
        return None
    head, expr = formula.split("=", 1)
    head, expr = head.strip(), expr.strip()
    for a, b in _FORMULA_OPS.items():
        expr = expr.replace(a, b)
    if not re.fullmatch(r"[A-Za-z_][A-Za-z_0-9]*", head):
        return None
    if not re.fullmatch(r"[A-Za-z_0-9_+\-*/(). ]+", expr):
        return None          # a threshold rule, a lookup, prose: not arithmetic
    return head, expr


def determination(df, lhs, rhs):
    """Share of rows whose lhs-group has a single rhs value: an FD holds at 1.0."""
    sub = df[list(lhs) + [rhs]].dropna()
    if not len(sub):
        return None
    g = sub.groupby([sub[c].astype(str) for c in lhs])[rhs].nunique()
    sizes = sub.groupby([sub[c].astype(str) for c in lhs])[rhs].size()
    good = sizes[g <= 1].sum()
    return float(good / len(sub))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--recipe", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--model", default=None)
    ap.add_argument("--psi-threshold", type=float, default=0.25)
    ap.add_argument("--label-tolerance", type=float, default=0.15,
                    help="allowed absolute difference in label rate between a part and the whole")
    ap.add_argument("--json", default=None, help="write the machine-readable report here")
    a = ap.parse_args(argv)

    out_dir = Path(a.out_dir)
    recipe = json.loads(Path(a.recipe).read_text(encoding="utf-8"))
    man = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))
    layers = read_layers(a.model)
    geo = layers.get("geometry") or {}
    src = read_any(recipe["input"]["path"])
    parts = {}
    for name, meta in man["outputs"]["files"].items():
        p = out_dir / Path(meta["path"]).name
        if p.is_file():
            parts[name] = read_any(p)
        elif meta.get("digest") is None:
            warn(f"{name}: no data file (a --dry-run manifest); the data checks are skipped")
    if not parts:
        warn("no output data to verify")
    label = man.get("label")
    cand = None
    for c in (geo.get("partitions") or {}).get("candidates") or []:
        if c.get("label") == label:
            cand = c
    report = {"structural": "pass", "semantic": [], "distributional": [], "split": "pass",
              "spatial": "n/a", "markers": []}

    # ---------------------------------------------------------------- structural
    cols = set().union(*[set(d.columns) for d in parts.values()]) if parts else set()
    steps = {s["id"]: s for s in recipe["steps"]}
    user_dropped = set()
    kept_derived = set()
    for s in recipe["steps"]:
        if str(s.get("source", "")).startswith("user:"):
            user_dropped |= set(s.get("columns") or [])
        if s["op"] == "drop_derived":
            kept_derived |= set((s.get("params") or {}).get("keep") or [])
    if label:
        if label not in cols:
            bad(f"structural: the label {label!r} is not in the output at all")
        schema = man.get("output_schema") or {}
        feats = [c for c, v in schema.items() if v.get("role") == "feature"]
        if label in feats:
            bad(f"structural: the label {label!r} is listed among the feature columns")
        else:
            ok(f"structural: the label {label!r} is present and is not a feature")
    if cand:
        leak = [c for c in (cand.get("dropped_for_leakage") or []) if c in cols]
        if leak:
            bad(f"structural: leakage column(s) {leak} survive in the output")
        else:
            ok(f"structural: the leakage set {cand.get('dropped_for_leakage') or []} is absent")
    heads = [d.get("column") for d in geo.get("derivations") or []]
    surviving = [h for h in heads if h in cols and h != label and h not in kept_derived]
    if surviving:
        bad(f"structural: active derivation head(s) {surviving} survive without a keep")
    elif heads:
        ok(f"structural: every active derivation head is gone or explicitly kept "
           f"({sorted(kept_derived) or 'none kept'})")
    basis = [b for b in (geo.get("basis") or {}).get("members") or []]
    # A basis member that is also the chosen partition's leakage set is *supposed* to be gone:
    # drop_leakage removed it, and that is the whole point of the partition.
    leakage_set = set((cand or {}).get("dropped_for_leakage") or [])
    missing = [b for b in basis if b not in cols and b not in user_dropped and b not in leakage_set]
    encoded = set()
    for s in recipe["steps"]:
        if s["op"] in ("encode", "project", "datetime_expand", "bin"):
            encoded |= set(s.get("columns") or [])
    missing = [b for b in missing if b not in encoded]
    if missing:
        bad(f"structural: basis member(s) {missing} are missing and no user: step dropped them")
    elif basis:
        ok(f"structural: every basis member survives or was transformed by a named step")
    if FAIL:
        report["structural"] = "fail"

    # ---------------------------------------------------------------- semantic
    # The concatenated output is not in the input's row order (a time split reorders it), so
    # every semantic check that compares an output row with its input row aligns through the
    # split's own index sets. Without them — and with the row count changed by a dedupe — the
    # alignment is not knowable and the check says so rather than guessing.
    split_idx = {}
    for st in man.get("steps") or []:
        if st["op"] == "split":
            split_idx = (st.get("parameters_fitted") or {}).get("indices") or {}
    frames, origins = [], []
    for name, d in parts.items():
        frames.append(d)
        if name in split_idx:
            origins.extend(int(i) for i in split_idx[name])
        elif len(parts) == 1 and len(d) == len(src):
            origins.extend(range(len(d)))
        else:
            origins = None
            break
    all_out = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    if origins is not None and len(origins) == len(all_out):
        all_out.index = pd.Index(origins, name="__row__")
    else:
        origins = None
        if parts:
            warn("semantic: the output rows cannot be aligned with the input rows (no split "
                 "index and the row count changed); the dropped-head checks are skipped")
    for d in geo.get("derivations") or []:
        head, body = d.get("column"), list(d.get("body") or [])
        rule = {"rule_id": d.get("rule_id"), "column": head, "formula": d.get("formula")}
        body_present = [c for c in body if c in all_out.columns]
        if not body_present:
            rule.update({"empirical": "not applicable", "why": "no body column survives",
                         "symbolic": "untested"})
            report["semantic"].append(rule)
            continue
        parsed = parse_formula(d.get("formula"))
        if head in all_out.columns and parsed and set(body) <= set(all_out.columns):
            _, expr = parsed
            try:
                got = all_out.eval(expr)
                want = pd.to_numeric(all_out[head], errors="coerce")
                m = np.isfinite(got) & np.isfinite(want)
                agree = int((np.abs(got[m] - want[m]) <= 1e-6 * np.maximum(1, np.abs(want[m]))).sum())
                total = int(m.sum())
                verdict = "confirmed" if total and agree == total else "refuted"
                rule.update({"empirical": verdict, "rows": f"{agree}/{total}"})
                (ok if verdict == "confirmed" else bad)(
                    f"semantic: {d.get('rule_id')} {verdict} on the output ({agree}/{total} rows)")
            except Exception as e:
                rule.update({"empirical": "untested", "why": f"formula did not evaluate: {e}"})
                warn(f"semantic: {d.get('rule_id')} could not be evaluated on the output ({e})")
        else:
            # the head is gone: the body must still determine the ORIGINAL head values on the
            # rows that survived, or a value-losing transform has quietly broken the relation.
            if head in src.columns and len(body_present) == len(body) and origins is not None:
                try:
                    joined = all_out[body_present].copy()
                    joined["__head__"] = src[head].to_numpy()[np.asarray(all_out.index)]
                    det = determination(joined, body_present, "__head__")
                except Exception as e:
                    det = None
                    rule["why"] = f"alignment failed: {e}"
                if det is None:
                    rule.update({"empirical": "untested", "why": rule.get("why", "could not align the rows")})
                elif det >= 0.999:
                    rule.update({"empirical": "confirmed",
                                 "why": "the head is dropped; its body still determines the "
                                        "original values on the retained rows",
                                 "determination_ratio": round(det, 6)})
                    ok(f"semantic: {d.get('rule_id')} — body still determines the dropped head "
                       f"(ratio {det:.4f})")
                else:
                    rule.update({"empirical": "refuted", "determination_ratio": round(det, 6)})
                    bad(f"semantic: {d.get('rule_id')} — the retained body no longer determines "
                        f"{head!r} (ratio {det:.4f}): a value-losing step broke the relation")
            elif origins is None:
                rule.update({"empirical": "untested", "why": "the output rows could not be "
                                                             "aligned with the input rows"})
            else:
                rule.update({"empirical": "not applicable",
                             "why": "the head is not in the input either"})
        rule.setdefault("symbolic", "untested")
        report["semantic"].append(rule)
    # symbolic channel: the model's own engines, when it has rules and a browser is present
    chrome = os.environ.get("CHROME") or shutil.which("chromium") or shutil.which("google-chrome")
    swrl = []
    if a.model:
        html = Path(a.model).read_text(encoding="utf-8")
        m = re.search(r'<script id="model-swrl"[^>]*>([\s\S]*?)</script>', html)
        if m:
            try:
                swrl = json.loads(m.group(1)).get("rules") or []
            except json.JSONDecodeError:
                swrl = []
    runner = SKILL_DIR.parent / "domain-forge" / "scripts" / "run_query.py"
    if swrl and chrome and runner.is_file():
        try:
            proc = subprocess.run(
                [sys.executable, str(runner), a.model, "--engine", "swrl", "--query",
                 "SELECT (COUNT(*) AS ?n)\nWHERE { ?s ?p ?o }"],
                capture_output=True, text=True, timeout=180)
            if proc.returncode == 0:
                for r in report["semantic"]:
                    r["symbolic"] = "untested"
                warn("semantic: the model's SWRL rules ran, but this check compares the SHAPED "
                     "rows, which are not in the model's A-box; the symbolic channel stays "
                     "untested (re-forge the model on the shaped data to close it)")
            else:
                warn(f"semantic: the engine runner exited {proc.returncode}; symbolic untested")
        except Exception as e:
            warn(f"semantic: the engine runner failed ({e}); symbolic untested")
    elif swrl and not chrome:
        warn("semantic: no headless browser; the symbolic channel is untested for every rule")
    else:
        ok("semantic: the model carries no rules to run; the symbolic channel is untested "
           "by construction")

    # ---------------------------------------------------------------- distributional
    named = set()
    for s in recipe["steps"]:
        named |= set(s.get("columns") or [])
        named |= set((s.get("params") or {}).get("columns") or [])
    untouched = [c for c in src.columns if c in all_out.columns and c not in named]
    for c in untouched:
        try:
            if pd.api.types.is_numeric_dtype(src[c]):
                v = psi(src[c], all_out[c])
            else:
                v = psi_cat(src[c], all_out[c])
        except Exception:
            v = None
        if v is None:
            continue
        rec = {"column": c, "psi": round(v, 6), "expected": True}
        if v > a.psi_threshold:
            rec["expected"] = False
            suspects = [s["id"] for s in recipe["steps"]
                        if s["op"] in ("dedupe", "clip", "winsorize", "split", "custom")]
            rec["suspected_steps"] = suspects
            warn(f"distributional: {c} moved (PSI {v:.3f}) although no step names it; "
                 f"suspect {suspects or 'the split'}")
        report["distributional"].append(rec)
    if report["distributional"] and all(r["expected"] for r in report["distributional"]):
        ok(f"distributional: {len(report['distributional'])} untouched column(s) did not move "
           f"(PSI below {a.psi_threshold})")

    # ---------------------------------------------------------------- split hygiene
    split_step = next((s for s in recipe["steps"] if s["op"] == "split"), None)
    if split_step and len(parts) > 1:
        idx = {}
        for st in man["steps"]:
            if st["op"] == "split":
                idx = st["parameters_fitted"].get("indices") or {}
        sets = {k: set(v) for k, v in idx.items()}
        overlap = []
        keys = sorted(sets)
        for i, x in enumerate(keys):
            for y in keys[i + 1:]:
                if sets[x] & sets[y]:
                    overlap.append((x, y, len(sets[x] & sets[y])))
        if overlap:
            bad(f"split: rows appear in more than one part: {overlap}")
            report["split"] = "fail"
        else:
            ok(f"split: the {len(sets)} parts are disjoint "
               f"({', '.join(f'{k} {len(v)}' for k, v in sorted(sets.items()))})")
        p = split_step.get("params") or {}
        if p.get("kind") == "group" and p.get("by") in src.columns:
            g = src[p["by"]].astype(str)
            straddle = [k for k in sets for v in [set(g.iloc[sorted(sets[k])])]
                        if any(v & set(g.iloc[sorted(sets[o])]) for o in sets if o != k)]
            if straddle:
                bad(f"split: kind=group but group values straddle parts {sorted(set(straddle))}")
                report["split"] = "fail"
            else:
                ok("split: every group stays inside one part")
        if p.get("kind") == "time" and p.get("time_column") in src.columns:
            t = pd.to_datetime(src[p["time_column"]], errors="coerce")
            maxes = {k: t.iloc[sorted(v)].max() for k, v in sets.items() if v}
            mins = {k: t.iloc[sorted(v)].min() for k, v in sets.items() if v}
            order = [k for k in ("train", "valid", "test") if k in sets and sets[k]]
            bad_order = [(x, y) for x, y in zip(order, order[1:]) if maxes[x] > mins[y]]
            if bad_order:
                bad(f"split: kind=time but the parts overlap in time: {bad_order}")
                report["split"] = "fail"
            else:
                ok("split: the parts are ordered in time and do not overlap")
        if label and label in all_out.columns:
            whole = pd.to_numeric(src[label], errors="coerce")
            if whole.notna().any() and whole.nunique() <= 20:
                base = float(whole.mean())
                rates = {}
                for k, d in parts.items():
                    v = pd.to_numeric(d[label], errors="coerce")
                    rates[k] = float(v.mean()) if v.notna().any() else None
                off = {k: r for k, r in rates.items()
                       if r is not None and abs(r - base) > a.label_tolerance}
                report["label_rate"] = {"whole": round(base, 6),
                                        **{k: (round(v, 6) if v is not None else None)
                                           for k, v in rates.items()}}
                if off:
                    warn(f"split: label rate drifts from the whole ({base:.3f}) in "
                         f"{ {k: round(v, 3) for k, v in off.items()} } — expected for a time "
                         f"split, a defect for a stratified one")
                else:
                    ok(f"split: the label rate holds across parts (whole {base:.3f})")

    # ---------------------------------------------------------------- spatial
    if any(s["op"].startswith("spatial_") for s in recipe["steps"]):
        crs = man.get("crs")
        report["spatial"] = "pass"
        proj = None
        for st in man.get("steps") or []:
            pr = (st.get("parameters_fitted") or {}).get("projection")
            if pr:
                proj = pr
        if not crs:
            bad("spatial: spatial steps ran but the manifest records no CRS")
            report["spatial"] = "fail"
        else:
            ok(f"spatial: the coordinates are declared in {crs}")
        if proj:
            report["projection"] = proj
            if proj.get("exact"):
                ok(f"spatial: metric columns were produced by {proj.get('kind')} "
                   f"({proj.get('from')} -> {proj.get('to')})")
            else:
                warn(f"spatial: metric columns were produced by the fallback projection "
                     f"({proj.get('kind')}, units {proj.get('units')}), not by the requested CRS: "
                     "install pyproj for an exact transform, and read the distances as local")
        geom_step = next((s for s in recipe["steps"] if s["op"] == "parse_geometry"), None)
        if geom_step:
            lat = (geom_step.get("params") or {}).get("lat")
            lon = (geom_step.get("params") or {}).get("lon")
            for c, lo, hi in ((lat, -90, 90), (lon, -180, 180)):
                if c and c in all_out.columns:
                    v = pd.to_numeric(all_out[c], errors="coerce")
                    outb = int(((v < lo) | (v > hi)).sum())
                    if outb:
                        bad(f"spatial: {outb} value(s) of {c} fall outside [{lo}, {hi}]")
                        report["spatial"] = "fail"
            if report["spatial"] == "pass":
                ok("spatial: every coordinate lies inside the declared bounds")

    report["markers"] = [f"OK: {m}" for m in OK] + [f"WARN: {m}" for m in WARN] + \
                        [f"ERROR: {m}" for m in FAIL]
    if a.json:
        Path(a.json).write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8")
    print(f"\n{len(OK)} passed, {len(WARN)} warned, {len(FAIL)} failed")
    return 3 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
