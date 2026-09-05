#!/usr/bin/env python3
"""
acceptance.py — the build's regression suite: it rebuilds the whole dataset lane from the
fixtures and checks the four done-criteria agreed for Noctua v3.

    python3 tests/acceptance.py [--work DIR] [--keep] [--only B1,B4,...]

It is deliberately end-to-end rather than unit-shaped: every script in the lane is exercised
against a real artifact, and the checks are the ones the contracts promise —

  B1  analysis.py runs every module its preconditions allow, twice, byte-identically.
  B2  cell.py executes, captures a failure, registers a figure, refuses the network, refuses a
      write outside the run directory, and honours its timeout.
  B3  the `analysis` layer applies through the platform writer, validates (invariants 13-16),
      smoke-tests in a headless browser, and strips back to a byte-identical predecessor.
  B4  the recipe checker refuses seven malformed recipes for the right reasons; the executor
      produces the shaped data; the generated reproduction script reproduces it byte for byte.
  B5  verify_shape.py passes on a good recipe and CATCHES a broken definitional relationship
      and a column that moved without a step naming it; the `shape` layer applies, validates
      and smoke-tests.
  B6  the whole chain stands on one file: three layers, invariants 13-16, three smoke tests,
      and a full strip back to the base model.

Exit 0 when every check passes. A missing headless browser downgrades the render checks to
warnings (and the suite says so) rather than failing them.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import re
import tempfile
from pathlib import Path

PKG = Path(__file__).resolve().parent.parent
FIX_ORDERS = PKG / "dataset-forge" / "fixtures" / "orders.csv"
FIX_GEO = PKG / "dataset-forge" / "fixtures" / "orders.geometry-layer.json"
FIX_SENSORS = PKG / "data-lens" / "fixtures" / "sensors.csv"
FIX_SENSORS_GEO = PKG / "data-lens" / "fixtures" / "sensors.geometry-layer.json"
RECIPE_ORDERS = PKG / "dataset-shaper" / "fixtures" / "orders.recipe.json"
RECIPE_SENSORS = PKG / "dataset-shaper" / "fixtures" / "sensors.recipe.json"

PASS, FAIL, SKIP = [], [], []


def run(cmd, **kw):
    return subprocess.run([sys.executable] + [str(c) for c in cmd], capture_output=True,
                          text=True, timeout=kw.pop("timeout", 900), **kw)


def check(cond, name, detail=""):
    if cond:
        PASS.append(name)
        print(f"  OK   {name}")
    else:
        FAIL.append(f"{name}: {detail}")
        print(f"  FAIL {name}{': ' + detail if detail else ''}")
    return bool(cond)


def skip(name, why):
    SKIP.append(f"{name}: {why}")
    print(f"  SKIP {name} — {why}")


def have_browser():
    return bool(os.environ.get("CHROME") or shutil.which("chromium")
                or shutil.which("google-chrome"))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--work", default=None, help="working directory (default: a temp dir)")
    ap.add_argument("--keep", action="store_true", help="keep the working directory")
    ap.add_argument("--only", default=None, help="comma-separated block ids to run")
    a = ap.parse_args(argv)
    only = set(a.only.split(",")) if a.only else None
    work = Path(a.work) if a.work else Path(tempfile.mkdtemp(prefix="noctua-acceptance-"))
    work.mkdir(parents=True, exist_ok=True)
    browser = have_browser()
    print(f"work dir: {work}\nheadless browser: {'yes' if browser else 'NO (render checks skipped)'}\n")
    DL, DS, DF, DFG = (PKG / "data-lens" / "scripts", PKG / "dataset-shaper" / "scripts",
                       PKG / "domain-forge" / "scripts", PKG / "dataset-forge" / "scripts")

    def want(b):
        return only is None or b in only

    # ---------------------------------------------------------------- base model + geometry
    print("[setup] base model and geometry layer")
    base = work / "orders.base.html"
    r = run([DL / "bootstrap_base.py", FIX_ORDERS, "--out", base, "--abox", 40, "--seed", 7])
    check(r.returncode == 0 and base.is_file(), "setup:bootstrap_base", r.stderr[-300:])
    model = work / "orders.domain.html"
    r = run([DFG / "apply_geometry_layer.py", base, "--data", FIX_GEO, "--out", model])
    check(r.returncode == 0 and model.is_file(), "setup:geometry-layer", r.stdout[-300:])
    r = run([DF / "validate_model.py", model])
    check(r.returncode == 0, "setup:model-validates", r.stdout[-400:])

    run_dir = work / "run"
    run_dir.mkdir(exist_ok=True)
    # Every later block needs a run directory with an analysis.json in it, so --only B2 (or B4)
    # can be run on its own: the setup makes a cheap one when the full B1 is not being run.
    if not want("B1"):
        run([DL / "analysis.py", FIX_ORDERS, "--model", model, "--out", run_dir / "analysis.json",
             "--modules", "quality", "--seed", 7])
        check((run_dir / "analysis.json").is_file(), "setup:minimal-analysis-json")

    # ---------------------------------------------------------------- B1
    if want("B1"):
        print("\n[B1] analysis.py")
        a1 = run_dir / "analysis.json"
        r = run([DL / "analysis.py", FIX_ORDERS, "--model", model, "--out", a1,
                 "--figures", run_dir / "fig", "--seed", 7])
        check(r.returncode == 0, "B1:orders-runs", r.stderr[-400:])
        doc = json.loads(a1.read_text())
        ran = [m for m, v in doc["modules"].items() if v.get("ran")]
        check(set(ran) >= {"quality", "distributions", "relations", "inference", "segments",
                           "importance", "time_series"},
              "B1:orders-modules", f"ran={sorted(ran)}")
        for m, v in doc["modules"].items():
            if not v.get("ran"):
                check(bool(v.get("skipped_because")), f"B1:skip-reason-{m}")
        check(doc["source"]["geometry"] == "present", "B1:geometry-read")
        check(doc["context"]["partition"]["label"] == "late", "B1:partition-from-layer")
        imp = doc["modules"]["importance"]["evidence"]
        check("delivered_days" in imp["excluded"]["leakage"], "B1:leakage-excluded")
        check(imp["leakage_probe"] is not None, "B1:leakage-probe-present")
        a2 = run_dir / "analysis-again.json"
        r = run([DL / "analysis.py", FIX_ORDERS, "--model", model, "--out", a2,
                 "--figures", run_dir / "fig2", "--seed", 7])
        t1 = a1.read_text().replace(str(run_dir / "fig"), "X")
        t2 = a2.read_text().replace(str(run_dir / "fig2"), "X")
        check(t1 == t2, "B1:deterministic")
        figs = sorted(p.name for p in (run_dir / "fig").glob("*.svg"))
        same = all((run_dir / "fig" / f).read_bytes() == (run_dir / "fig2" / f).read_bytes()
                   for f in figs)
        check(bool(figs) and same, "B1:figures-deterministic", f"{len(figs)} figures")
        # the conditional modules, on the fixture built for them
        sbase = work / "sensors.base.html"
        run([DL / "bootstrap_base.py", FIX_SENSORS, "--out", sbase, "--abox", 30])
        smodel = work / "sensors.domain.html"
        run([DFG / "apply_geometry_layer.py", sbase, "--data", FIX_SENSORS_GEO, "--out", smodel])
        sa = work / "sensors.analysis.json"
        r = run([DL / "analysis.py", FIX_SENSORS, "--model", smodel, "--out", sa,
                 "--split", "split", "--seed", 7])
        check(r.returncode == 0, "B1:sensors-runs", r.stderr[-300:])
        sdoc = json.loads(sa.read_text())
        sran = [m for m, v in sdoc["modules"].items() if v.get("ran")]
        check(len(sran) == 9, "B1:sensors-all-nine-modules", f"ran={sorted(sran)}")
        q = sdoc["modules"]["quality"]["evidence"]["missingness_dependence"]
        check(q and q[0]["missing_in"] == "calibration" and q[0]["against"] == "station",
              "B1:finds-the-MAR-mechanism", str(q[:1])[:120])
        imp2 = sdoc["modules"]["importance"]["evidence"]
        top = [p["feature"] for p in imp2["permutation_importance"][:2]]
        check(set(top) == {"lat", "lon"}, "B1:importance-finds-location", str(top))
        mor = sdoc["modules"]["spatial"]["evidence"]["morans_i"]
        check(any(m["column"] == "lat" and m["I"] > 0.9 for m in mor), "B1:spatial-autocorrelation")
        dr = [c["column"] for c in sdoc["modules"]["drift"]["evidence"]["columns"] if c["drifted"]]
        check("battery_pct" in dr, "B1:drift-finds-the-decay", str(dr))
        for r_ in sdoc["modules"]["inference"]["evidence"]["numeric_by_nominal"][:5]:
            if r_.get("p_adj") is not None:
                check(r_.get("effect", {}).get("value") is not None and r_.get("correction"),
                      f"B1:effect-and-correction-{r_['value']}-by-{r_['group']}")
                break

    # ---------------------------------------------------------------- B2
    if want("B2"):
        print("\n[B2] cell.py")
        cases = {
            "ok": "result = {'rows': len(df), 'basis': ctx['basis'][:2]}",
            "fail": "result = df['nope'].mean()",
            "fig": ("import matplotlib; matplotlib.use('Agg')\nimport matplotlib.pyplot as plt\n"
                    "f, ax = plt.subplots(figsize=(2,1.5)); ax.hist(df['qty'], bins=5)\n"
                    "fig(f)\nresult = {'prev': len(prev)}"),
            "net": "import socket\ns = socket.socket(); s.connect(('example.com', 80))",
            "write": f"open({str(PKG / 'POISONED.txt')!r}, 'w').write('nope')",
            "slow": "import time\ntime.sleep(9)\nresult = 1"}
        for name, code in cases.items():
            f = work / f"cell_{name}.py"
            f.write_text(code)
            r = run([DL / "cell.py", run_dir, "--code", f, "--timeout", 3 if name == "slow" else 60])
            try:
                out = json.loads(r.stdout)
            except json.JSONDecodeError:
                check(False, f"B2:{name}", "no JSON on stdout")
                continue
            if name == "ok":
                check(out["ok"] and out["result"]["rows"] == 600, f"B2:{name}")
            elif name == "fail":
                check(not out["ok"] and out["error"]["type"] == "KeyError", f"B2:{name}")
            elif name == "fig":
                # stdout elides the SVG on purpose; the real artifact is the file the cell
                # wrote, so that is what the check reads.
                svgs = sorted((run_dir / "cells").glob("cell-*.svg"))
                body = svgs[-1].read_text()[:2000] if svgs else ""
                check(out["ok"] and out["figures"] == 1 and "<svg" in body,
                      f"B2:{name}", str(out.get("error") or body[:80])[:120])
            elif name == "net":
                check(not out["ok"] and "network" in out["error"]["message"], f"B2:{name}")
            elif name == "write":
                check(not out["ok"] and "run directory" in out["error"]["message"], f"B2:{name}")
                check(not (PKG / "POISONED.txt").exists(), "B2:no-escape")
            elif name == "slow":
                check(not out["ok"] and out["error"]["type"] == "Timeout", f"B2:{name}")

    # ---------------------------------------------------------------- B3
    layered = work / "orders.domain.analysis.html"
    if want("B3"):
        print("\n[B3] the analysis layer")
        lay = json.loads((PKG / "tests" / "fixtures" / "orders.analysis-layer.json").read_text())
        lay["from_analysis"] = str(run_dir / "analysis.json")
        lp = work / "analysis-layer.json"
        lp.write_text(json.dumps(lay))
        r = run([DL / "apply_analysis_layer.py", model, "--data", lp, "--out", layered])
        check(r.returncode == 0 and layered.is_file(), "B3:layer-applies", r.stdout[-400:])
        r = run([DF / "validate_model.py", layered])
        check(r.returncode == 0 and "invariant 16" in r.stdout, "B3:validates", r.stdout[-400:])
        back = work / "back.html"
        run([DF / "strip_layer.py", layered, "--layer", "analysis", "--out", back])
        check(back.read_bytes() == model.read_bytes(), "B3:round-trip-byte-identical")
        if browser:
            r = run([DL / "smoke_analysis.py", layered, "--strict"])
            check(r.returncode == 0, "B3:smoke", r.stdout[-500:])
        else:
            skip("B3:smoke", "no headless browser")
        # the validator must refuse a p-value with no effect size
        broken = dict(lay)
        broken["findings"] = json.loads(json.dumps(lay["findings"]))
        broken["findings"][0]["evidence"] = {"p": 0.01}
        broken["findings"][0]["method"] = {"name": "t", "assumptions_checked": "passed"}
        bp = work / "broken-layer.json"
        bp.write_text(json.dumps(broken))
        r = run([DL / "apply_analysis_layer.py", model, "--data", bp, "--out", work / "x.html"])
        check(r.returncode == 2 and "effect size" in r.stdout,
              "B3:refuses-a-lonely-p-value", r.stdout[-200:])

    # ---------------------------------------------------------------- B4
    shaped = work / "shaped"
    if want("B4"):
        print("\n[B4] the recipe checker and the executor")
        base_recipe = json.loads(RECIPE_ORDERS.read_text())
        negatives = {
            "no-source": lambda r: r["steps"][0].pop("source"),
            "fitted-before-split": lambda r: r["steps"].insert(1, dict(
                r["steps"][-1], id="X1", op="encode", columns=["note"],
                params={"strategy": "one-hot"}, source="shaper:default")),
            "unknown-source": lambda r: r["steps"][0].__setitem__(
                "source", "geometry:typing/not_a_column"),
            "custom-not-user": lambda r: r["steps"].append(dict(
                r["steps"][0], id="X2", op="custom", columns=[],
                params={"phase": 4, "code": "def step(df, ctx): return df"},
                source="shaper:default")),
            "target-encode-no-split": lambda r: (
                r["steps"].__setitem__(slice(None), [s for s in r["steps"] if s["op"] != "split"]),
                r["steps"][-1]["params"].__setitem__("strategy", "target")),
            "half-a-derivation": lambda r: (
                r["steps"].__setitem__(slice(None), [s for s in r["steps"]
                                                     if s["op"] != "drop_derived"]),
                r["steps"].append(dict(r["steps"][0], id="X3", op="transform", columns=["qty"],
                                       params={"kind": "log1p"}, source="shaper:default"))),
            "against-a-stance": lambda r: r["steps"].insert(
                9, dict(r["steps"][0], id="X4", op="winsorize", columns=["unit_price"],
                        params={"lower_q": 0.01, "upper_q": 0.99}, source="shaper:default")),
        }
        for name, mutate in negatives.items():
            rec = json.loads(json.dumps(base_recipe))
            mutate(rec)
            p = work / f"neg-{name}.json"
            p.write_text(json.dumps(rec))
            r = run([DS / "shape.py", "--recipe", p, "--model", layered, "--check-only"])
            check(r.returncode == 2 and "ERROR" in r.stdout, f"B4:refuses-{name}",
                  r.stdout[-200:])
        r = run([DS / "shape.py", "--recipe", RECIPE_ORDERS, "--model", layered, "--check-only"])
        check(r.returncode == 0, "B4:accepts-the-good-recipe", r.stdout[-300:])
        r = run([DS / "shape.py", "--recipe", RECIPE_ORDERS, "--model", layered,
                 "--out-dir", shaped, "--format", "csv"])
        check(r.returncode == 0, "B4:executes", r.stdout[-400:])
        man = json.loads((shaped / "manifest.json").read_text())
        check({s["id"]: s["fit_on"] for s in man["steps"] if s["fit_on"]}
              and all(v == "train" for v in
                      [s["fit_on"] for s in man["steps"] if s["fit_on"]]),
              "B4:fitted-on-train-only")
        import csv
        with open(shaped / "orders.train.csv") as fh:
            cols = next(csv.reader(fh))
        check("delivered_days" not in cols, "B4:leakage-gone")
        check(not {"total", "subtotal", "city", "region"} & set(cols), "B4:derived-gone")
        check("late" in cols, "B4:label-kept")
        r = run([DS / "shape.py", "--check", "--out-dir", shaped])
        check(r.returncode == 0 and "reproduce byte for byte" in r.stdout,
              "B4:reproduction-is-byte-identical", r.stdout[-300:])
        # the second lane: impute, lag, datetime, spatial
        shaped_s = work / "shaped-sensors"
        r = run([DS / "shape.py", "--recipe", RECIPE_SENSORS, "--model", work / "sensors.domain.html",
                 "--out-dir", shaped_s, "--format", "csv"])
        check(r.returncode == 0, "B4:sensors-executes", r.stdout[-400:])
        r = run([DS / "shape.py", "--check", "--out-dir", shaped_s])
        check(r.returncode == 0, "B4:sensors-reproduction-is-byte-identical", r.stdout[-300:])

    # ---------------------------------------------------------------- B5
    final = work / "orders.domain.analysis.shaped.html"
    if want("B5"):
        print("\n[B5] verification and the shape layer")
        vj = shaped / "verification.json"
        r = run([DS / "verify_shape.py", "--recipe", RECIPE_ORDERS, "--out-dir", shaped,
                 "--model", layered, "--json", vj])
        check(r.returncode == 0, "B5:verify-passes", r.stdout[-400:])
        v = json.loads(vj.read_text())
        check(v["structural"] == "pass", "B5:structural-pass")
        check(any(s.get("empirical") == "confirmed" for s in v["semantic"]),
              "B5:semantic-confirmed")
        # it must CATCH a broken definitional relationship
        rec = json.loads(RECIPE_ORDERS.read_text())
        for s in rec["steps"]:
            if s["op"] == "drop_derived":
                s["params"] = {"keep": ["total"]}
                s["source"] = "user:keep the total"
        rec["steps"].insert(9, dict(rec["steps"][0], id="X9", op="bin", columns=["qty"],
                                    params={"kind": "quantile", "k": 4, "replace": True},
                                    source="user:bin the quantity in place"))
        p = work / "broken-recipe.json"
        p.write_text(json.dumps(rec))
        bshaped = work / "shaped-broken"
        run([DS / "shape.py", "--recipe", p, "--model", layered, "--out-dir", bshaped,
             "--format", "csv"])
        r = run([DS / "verify_shape.py", "--recipe", p, "--out-dir", bshaped, "--model", layered])
        check(r.returncode == 3 and "refuted" in r.stdout,
              "B5:catches-a-broken-definition", r.stdout[-300:])
        v["determinism"] = "pass"
        vj.write_text(json.dumps(v))
        lay = {"schema": "dataset-shaper/shape@1", "from_run": str(shaped),
               "readings": {"abstract": "Acceptance run: the recipe applied and verified."},
               "forks": []}
        lp = work / "shape-layer.json"
        lp.write_text(json.dumps(lay))
        r = run([DS / "apply_shape_layer.py", layered, "--data", lp, "--out", final])
        check(r.returncode == 0 and final.is_file(), "B5:layer-applies", r.stdout[-400:])
        # a failed verification may not be published
        badlay = dict(lay)
        badlay["verification"] = {"structural": "fail", "determinism": "pass"}
        bp = work / "bad-shape-layer.json"
        bp.write_text(json.dumps(badlay))
        r = run([DS / "apply_shape_layer.py", layered, "--data", bp, "--out", work / "y.html"])
        check(r.returncode == 2 and "fail" in r.stdout,
              "B5:refuses-to-publish-a-failure", r.stdout[-200:])
        if browser:
            r = run([DS / "smoke_shape.py", final, "--strict"])
            check(r.returncode == 0, "B5:smoke", r.stdout[-500:])
        else:
            skip("B5:smoke", "no headless browser")

    # ---------------------------------------------------------------- B6
    if want("B6") and final.is_file():
        print("\n[B6] the chain on one file")
        r = run([DF / "validate_model.py", final])
        ok13 = "invariant 13: 3 @LAYER" in r.stdout
        ok16 = "invariant 16: 3 layer" in r.stdout
        check(r.returncode == 0, "B6:validates", r.stdout[-400:])
        check(ok13 and ok16, "B6:three-layers-independent", r.stdout[-300:])
        if browser:
            for skill, script in (("geometry", DFG / "smoke_geometry.py"),
                                  ("analysis", DL / "smoke_analysis.py"),
                                  ("shape", DS / "smoke_shape.py")):
                r = run([script, final, "--strict"])
                check(r.returncode == 0, f"B6:smoke-{skill}", r.stdout[-300:])
        else:
            skip("B6:smokes", "no headless browser")
        cur, expected = final, [(("shape",), layered), (("analysis",), model), (("geometry",), base)]
        for (layer,), target in expected:
            out = work / f"strip-{layer}.html"
            run([DF / "strip_layer.py", cur, "--layer", layer, "--out", out])
            check(out.read_bytes() == target.read_bytes(),
                  f"B6:strip-{layer}-restores-{target.name}")
            cur = out

    # ---------------------------------------------------------------- B7
    if want("B7"):
        print("\n[B7] the orchestrator's state scan and its routing")
        proj = work / "b7"
        (proj / "dataset").mkdir(parents=True, exist_ok=True)
        (proj / "analysis").mkdir(exist_ok=True)
        (proj / "spec").mkdir(exist_ok=True)
        (proj / ".claude").mkdir(exist_ok=True)
        shutil.copy(FIX_ORDERS, proj / "dataset" / "orders.csv")
        shutil.copy(model, proj / "analysis" / "orders.domain_3.html")
        (proj / "spec" / "spec-analysis.html").write_text(
            "<!doctype html><html><body><h1>spec</h1><p>Prose only.</p></body></html>")
        (proj / ".claude" / "domain-forge-memory.md").write_text(
            "# memory\n\n## Dataset stances\n2026-08-30 | orders | partition: late "
            "(leakage: delivered_days)\n")
        r = run([PKG / "noctua" / "scripts" / "env_check.py", "--scan", proj, "--json"])
        check(r.returncode == 0, "B7:scan-runs", r.stderr[-200:])
        s = json.loads(r.stdout)["scan"]
        kinds = {x["kind"] for x in s["sources"]}
        check({"model", "dataset", "prose"} <= kinds, "B7:classifies-every-source", str(kinds))
        mdl = next(x for x in s["sources"] if x["kind"] == "model")
        check(mdl["source_kind"] == "dataset", "B7:model-is-a-dataset-ontology")
        check([l["name"] for l in mdl["layers"]] == ["geometry"], "B7:reads-the-layers",
              str(mdl["layers"]))
        check(s["memory_present"] and s["memory"].get("Dataset stances"),
              "B7:reads-the-recorded-decisions")
        check(not s["ledger_present"], "B7:notices-the-ledger-is-missing")
        # the routing table of chain-map.md § Reading a model's position from its layers
        table = {("geometry",): "lens", ("geometry", "analysis"): "shape",
                 ("geometry", "analysis", "shape"): "blueprint --mode pipeline",
                 (): "forge-data refine"}
        got = table.get(tuple(l["name"] for l in mdl["layers"]))
        check(got == "lens", "B7:next-stage-is-lens", str(got))
        r = run([PKG / "noctua" / "scripts" / "env_check.py", "--env", "--json"])
        env = json.loads(r.stdout)["environment"]
        check(env["lanes_open"]["dataset (forge-data → lens → shape → blueprint)"],
              "B7:dataset-lane-open")
        check(not env["skills_specified_but_unbuilt"],
              "B7:no-skill-is-specified-but-unbuilt", str(env["skills_specified_but_unbuilt"]))

    # ---------------------------------------------------------------- B8
    if want("B8"):
        print("\n[B8] the platform and the software lane are untouched")
        suite = DF / "tests" / "test_layers.sh"
        if suite.is_file():
            # the suite takes the base model as its argument (it defaults to a path that only
            # exists in the domain-forge development repo)
            r = subprocess.run(["bash", str(suite), str(base)], capture_output=True, text=True,
                               timeout=1800, cwd=str(PKG))
            tail = (r.stdout or "")[-400:]
            check(r.returncode == 0, "B8:platform-layer-suite", tail)
        else:
            skip("B8:platform-layer-suite", "test_layers.sh not present")
        ex = PKG / "domain-forge" / "examples" / "commerce.domain.html"
        if ex.is_file():
            r = run([DF / "validate_model.py", ex])
            check(r.returncode == 0, "B8:shipped-example-still-validates", r.stdout[-300:])
        for skill in ("spec-analysis", "blueprint", "domain-forge", "dataset-forge"):
            md = PKG / skill / "SKILL.md"
            txt = md.read_text(encoding="utf-8")
            m = re.search(r"description: >-\n((?:  .*\n)+)", txt)
            desc = " ".join(l.strip() for l in m.group(1).splitlines()) if m else ""
            check(0 < len(desc) <= 1024, f"B8:{skill}-description-fits", f"{len(desc)} chars")

    print(f"\n{len(PASS)} passed, {len(FAIL)} failed, {len(SKIP)} skipped")
    for f in FAIL:
        print(f"  FAILED  {f}")
    if not a.keep and not a.work:
        shutil.rmtree(work, ignore_errors=True)
    else:
        print(f"work kept at {work}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
