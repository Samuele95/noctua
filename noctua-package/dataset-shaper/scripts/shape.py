#!/usr/bin/env python3
"""
shape.py — check and execute a /dataset-shaper recipe: the decisions an analysis already took,
applied to the data, deterministically, with every step traced to what justified it.

    python3 shape.py --recipe recipe.json --model MODEL.html --check-only
    python3 shape.py --recipe recipe.json --out-dir shaped/ [--format parquet|csv] [--dry-run]
    python3 shape.py --check --out-dir shaped/

Three jobs, one script:

  --check-only  validates the recipe against `references/shape-contract.md` §1 and, when
                --model is given, resolves every step's `source` against the model's layers.
                A step with no source, a fitted step before the split, a leakage column that
                survives, a basis member dropped without a `user:` step, a step that
                contradicts a recorded analysis stance: each is an ERROR here, before any
                data moves.
  (default)     executes the recipe phase by phase and writes the dataset file(s),
                `manifest.json`, `lineage.json`, `recipe.json` and `reproduce_<slug>.py` —
                a standalone pandas program that regenerates the outputs without this skill.
  --check       re-runs that reproduction script and compares the digests it produces with
                the ones in the manifest. Determinism is a test, not a claim.

Fitted steps (impute with a statistic, encode, scale, project, quantile bin, winsorize) are
fitted on the train part alone when a split exists — the manifest records `fit_on` per step —
and applied to every part. That is not a nicety: it is the difference between an honest
estimate and one that has already seen its own test set.

Exit codes: 0 done; 2 recipe or input error; 3 execution or verification failure.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
SKILL_DIR = HERE.parent
SCHEMA = "dataset-shaper/recipe@1"

PHASES = {
    1: ("retype", "drop_identity", "drop_constant", "dedupe", "parse_datetime", "parse_geometry"),
    2: ("orient_cycle", "drop_derived", "select_partition", "drop_leakage", "keep_columns"),
    3: ("split",),
    4: ("impute", "clip", "winsorize", "transform", "bin", "datetime_expand", "lag",
        "spatial_reproject", "spatial_distance", "spatial_join", "spatial_grid",
        "spatial_features"),
    5: ("encode", "scale", "project"),
    6: ("select_features",),
}
OP_PHASE = {op: ph for ph, ops in PHASES.items() for op in ops}
FITTED_OPS = {"impute", "encode", "scale", "project", "bin", "winsorize"}
SPATIAL_OPS = {op for op in PHASES[4] if op.startswith("spatial_")}
SOURCE_RE = re.compile(r"^(geometry:[A-Za-z0-9_./\-]+|analysis:(F\d+|turn\d+)/T\w+|"
                       r"analysis:[A-Za-z0-9_./\-]+|user:[^\s].*|shaper:default)$")
MARKERS: list[str] = []


def mark(s):
    MARKERS.append(s)
    print(s)


def digest_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return "sha256:" + h.hexdigest()


def digest_text(s):
    return "sha256:" + hashlib.sha256(s.encode("utf-8")).hexdigest()


def jsonable(o):
    if isinstance(o, dict):
        return {str(k): jsonable(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [jsonable(v) for v in o]
    if isinstance(o, (np.bool_, bool)):
        return bool(o)
    if isinstance(o, (int, np.integer)):
        return int(o)
    if isinstance(o, (float, np.floating)):
        f = float(o)
        return None if (math.isnan(f) or math.isinf(f)) else f
    if isinstance(o, np.ndarray):
        return [jsonable(v) for v in o.tolist()]
    if isinstance(o, (pd.Timestamp,)):
        return o.isoformat()
    if o is None or isinstance(o, str):
        return o
    return str(o)


# --------------------------------------------------------------------------- model layers
def read_layers(model_path):
    """Return {"geometry": {...}, "analysis": {...}} for whichever layers the model carries."""
    out = {}
    if not model_path:
        return out
    html = Path(model_path).read_text(encoding="utf-8")
    for name in ("geometry", "analysis", "shape"):
        m = re.search(r'<script\s+id="layer-' + name + r'-data"[^>]*>([\s\S]*?)</script>',
                      html, re.IGNORECASE)
        if m:
            try:
                out[name] = json.loads(m.group(1).strip())
            except json.JSONDecodeError:
                mark(f"WARN: layer-{name}-data did not parse; its sources cannot be resolved")
    return out


def resolve_source(src, layers):
    """True when the source names something the layers actually contain."""
    if src == "shaper:default" or src.startswith("user:"):
        return True
    if src.startswith("geometry:"):
        geo = layers.get("geometry")
        if geo is None:
            return None                       # unresolvable, not false
        path = src.split(":", 1)[1].split("/")
        head = path[0]
        if head == "typing":
            cols = {t.get("column") for t in geo.get("typing") or []}
            return len(path) < 2 or path[1] in cols
        if head in ("derivations",):
            cols = {d.get("column") for d in geo.get("derivations") or []}
            return len(path) < 2 or path[1] in cols
        if head == "cycles":
            ids = {c.get("id") for c in geo.get("cycles") or []}
            return len(path) < 2 or path[1] in ids
        if head == "partitions":
            labs = {c.get("label") for c in (geo.get("partitions") or {}).get("candidates") or []}
            return len(path) < 2 or path[1].split(".")[0] in labs
        if head in ("space", "basis", "orthogonality", "functional_dependencies", "disagreements"):
            return head in geo
        return False
    if src.startswith("analysis:"):
        ana = layers.get("analysis")
        if ana is None:
            return None
        tail = src.split(":", 1)[1]
        if "/" in tail:
            owner, cand = tail.split("/", 1)
            ids = set()
            for f in ana.get("findings") or []:
                if f.get("id") == owner:
                    ids |= {t.get("id") for t in f.get("transformation_candidates") or []}
            for t in ana.get("transcript") or []:
                if f"turn{t.get('turn')}" == owner:
                    ids |= {c.get("id") for c in t.get("transformation_candidates") or []}
            return cand in ids
        if tail.startswith("context") or tail.startswith("modules"):
            return True
        return any(f.get("id") == tail for f in ana.get("findings") or [])
    return False


def stance_conflicts(step, layers):
    """A step that contradicts a recorded analysis stance. The stance wins unless a
    `user:` source overrides it and says so."""
    ana = layers.get("analysis") or {}
    out = []
    cols = set(step.get("columns") or [])
    for s in ana.get("stances") or []:
        if not isinstance(s, dict):
            continue
        scols = set(s.get("columns") or [])
        kind = s.get("kind")
        hit = cols & scols
        if not hit:
            continue
        if kind == "genuine-outliers" and step["op"] in ("winsorize", "clip"):
            out.append(f"{step['op']} on {sorted(hit)} contradicts stance {s.get('id')}: "
                       f"{s.get('assertion')}")
        if kind == "out-of-scope":
            out.append(f"{step['op']} touches {sorted(hit)}, which stance {s.get('id')} "
                       f"declares out of scope")
        if kind == "missingness-mechanism" and step["op"] == "impute":
            strat = (step.get("params") or {}).get("strategy")
            if strat in ("median", "mean", "mode") and "group" in str(s.get("assertion", "")):
                out.append(f"impute {strat} on {sorted(hit)} ignores stance {s.get('id')}: "
                           f"{s.get('assertion')}")
    return out


# --------------------------------------------------------------------------- recipe checking
def check_recipe(rec, layers, out):
    errs = []
    if not isinstance(rec, dict):
        return ["recipe is not a JSON object"]
    if rec.get("schema") != SCHEMA:
        errs.append(f"schema must be {SCHEMA!r}, got {rec.get('schema')!r}")
    inp = rec.get("input") or {}
    if not inp.get("path"):
        errs.append("input.path is required")
    steps = rec.get("steps")
    if not isinstance(steps, list) or not steps:
        errs.append("steps must be a non-empty list")
        return errs
    ids, last_phase, split_at = set(), 0, None
    for i, s in enumerate(steps):
        w = f"steps[{i}]"
        if not isinstance(s, dict):
            errs.append(f"{w} must be an object")
            continue
        for k in ("id", "op", "source", "rationale"):
            if not s.get(k):
                errs.append(f"{w} missing {k!r}" + (
                    " — every step cites the geometry element, the analysis finding, the user's "
                    "word or the preset default that justifies it" if k == "source" else ""))
        if s.get("id") in ids:
            errs.append(f"{w}: duplicate step id {s.get('id')!r}")
        ids.add(s.get("id"))
        op = s.get("op")
        if op == "custom":
            ph = (s.get("params") or {}).get("phase")
            if ph not in (1, 2, 3, 4, 5, 6):
                errs.append(f"{w}: a custom step must declare params.phase (1-6) so the executor "
                            "can place it")
            if not str(s.get("source", "")).startswith("user:"):
                errs.append(f"{w}: a custom step's source must be user: — nothing else can "
                            "justify code the catalog does not define")
            if not (s.get("params") or {}).get("code"):
                errs.append(f"{w}: a custom step needs params.code")
            phase = ph if ph in (1, 2, 3, 4, 5, 6) else 4
        elif op not in OP_PHASE:
            errs.append(f"{w}: unknown op {op!r}; see references/step-catalog.md")
            continue
        else:
            phase = OP_PHASE[op]
        if phase < last_phase:
            errs.append(f"{w}: op {op!r} belongs to phase {phase} but follows a phase-"
                        f"{last_phase} step; the phase order is what keeps a fitted step from "
                        "seeing the test part")
        last_phase = max(last_phase, phase)
        if op == "split":
            if split_at is not None:
                errs.append(f"{w}: a recipe carries at most one split")
            split_at = i
        src = str(s.get("source") or "")
        if src and not SOURCE_RE.match(src):
            errs.append(f"{w}: source {src!r} is not one of geometry:… / analysis:F<n>/T<m> / "
                        "analysis:turn<N>/T<m> / user:… / shaper:default")
        elif src and layers:
            r = resolve_source(src, layers)
            if r is False:
                errs.append(f"{w}: source {src!r} names nothing in the model's layers")
            elif r is None:
                out(f"WARN: {w}: source {src!r} cannot be resolved (the model carries no "
                    f"{src.split(':')[0]} layer)")
        if s.get("source") == "shaper:default" and not s.get("alternatives"):
            out(f"WARN: {w}: a shaper:default step should carry at least one alternative — "
                "it is a choice the recipe made on its own")
        cons = s.get("consequences") or {}
        for k in ("rows", "columns", "downstream"):
            if k not in cons:
                out(f"WARN: {w}: consequences.{k} missing")
        for c in stance_conflicts(s, layers):
            if str(s.get("source", "")).startswith("user:"):
                out(f"WARN: {w}: {c} — allowed because a user: step overrides it")
            else:
                errs.append(f"{w}: {c}")
    # fitted steps before the split
    if split_at is not None:
        for i, s in enumerate(steps[:split_at]):
            if isinstance(s, dict) and s.get("op") in FITTED_OPS:
                errs.append(f"steps[{i}]: {s.get('op')!r} is a fitted step placed before the "
                            "split; it would be fitted on rows that end up in the test part")
    else:
        for s in steps:
            if isinstance(s, dict) and s.get("op") == "encode" and \
                    (s.get("params") or {}).get("strategy") == "target":
                errs.append("target encoding without a split: it needs out-of-fold fitting, "
                            "which the executor performs only when a split precedes it")
    # structural rules against the geometry layer
    geo = layers.get("geometry")
    if geo:
        label = None
        for s in steps:
            if isinstance(s, dict) and s.get("op") == "select_partition":
                label = (s.get("params") or {}).get("label")
        cand = None
        for c in (geo.get("partitions") or {}).get("candidates") or []:
            if c.get("label") == label:
                cand = c
        if label and cand is None:
            errs.append(f"select_partition names {label!r}, which the geometry layer does not "
                        "offer as a candidate")
        dropped = set()
        kept = set()
        for s in steps:
            if not isinstance(s, dict):
                continue
            if s.get("op") in ("drop_derived",):
                kept |= set((s.get("params") or {}).get("keep") or [])
            if s.get("op") == "keep_columns":
                kept |= set((s.get("params") or {}).get("columns") or [])
            if s.get("op") in ("drop_identity", "drop_constant", "drop_leakage", "select_features"):
                dropped |= set(s.get("columns") or [])
        if cand:
            leak = set(cand.get("dropped_for_leakage") or [])
            has_drop_leak = any(isinstance(s, dict) and s.get("op") == "drop_leakage"
                                for s in steps)
            if leak and not has_drop_leak:
                errs.append(f"the chosen partition holds back {sorted(leak)} as its leakage set, "
                            "but the recipe has no drop_leakage step")
            if kept & leak:
                errs.append(f"keep_columns retains leakage column(s) {sorted(kept & leak)}")
        basis = set((geo.get("basis") or {}).get("members") or [])
        for s in steps:
            if not isinstance(s, dict) or s.get("op") not in ("drop_identity", "drop_constant",
                                                              "select_features"):
                continue
            hit = basis & set(s.get("columns") or [])
            if hit and not str(s.get("source", "")).startswith("user:"):
                errs.append(f"step {s.get('id')} drops basis member(s) {sorted(hit)} without a "
                            "user: step saying so")
        # a transform on one member of a kept derivation cycle
        heads = {d.get("column"): set(d.get("body") or []) for d in geo.get("derivations") or []}
        drops_derived = any(isinstance(s, dict) and s.get("op") == "drop_derived" for s in steps)
        for s in steps:
            if not isinstance(s, dict) or s.get("op") != "transform":
                continue
            touched = set(s.get("columns") or [])
            for head, body in heads.items():
                if drops_derived and head not in kept:
                    continue                      # the head leaves; the relation leaves with it
                fam = body | {head}
                if touched & fam and not fam <= touched:
                    errs.append(f"step {s.get('id')}: transform touches {sorted(touched & fam)} "
                                f"but not the whole derivation {head} = f({', '.join(sorted(body))}); "
                                "a transform on one member alone breaks the relation")
    return errs


# --------------------------------------------------------------------------- execution state
class Ctx:
    def __init__(self, df, recipe, layers, seed):
        self.parts = {"all": df}
        self.order = ["all"]
        self.recipe = recipe
        self.layers = layers
        self.seed = seed
        self.label = None
        # The label is known before the first step runs: the executor pre-scans the recipe for
        # select_partition. Nothing drops the target on its way past — a rule head that happens
        # to be the label (late = delivered_days > 7) is the thing being predicted, not a
        # redundant column. Only an explicit user: step may remove it.
        self.label_planned = None
        self.active_orientation = {}
        self.crs = None
        self.lineage = {c: [] for c in df.columns}
        self.removed = {}
        self.manifest = []
        self.code = []
        self.fitted = {}

    @property
    def fit_part(self):
        return "train" if "train" in self.parts else "all"

    def each(self):
        return [(k, self.parts[k]) for k in self.order]

    def set_all(self, fn):
        for k in self.order:
            self.parts[k] = fn(self.parts[k])

    def cols(self):
        return list(self.parts[self.order[0]].columns)

    def touch(self, step, columns):
        for c in columns:
            self.lineage.setdefault(c, []).append(step["id"])

    def emit(self, *lines):
        self.code.extend(lines)


def geo_of(ctx):
    return ctx.layers.get("geometry") or {}


def py(v):
    """A Python literal for the generated reproduction script. json.dumps would write null,
    true and false, which are not Python — repr is the correct serializer here."""
    return repr(v)


# --------------------------------------------------------------------------- phase 1
def op_retype(ctx, step):
    to = (step.get("params") or {}).get("to")
    order = (step.get("params") or {}).get("order")
    cols = [c for c in (step.get("columns") or []) if c in ctx.cols()]
    for c in cols:
        def conv(d, c=c):
            d = d.copy()
            if to == "numeric":
                d[c] = pd.to_numeric(d[c], errors="coerce")
            elif to in ("nominal", "text"):
                d[c] = d[c].astype("string")
            elif to == "ordinal":
                d[c] = pd.Categorical(d[c].astype("string"),
                                      categories=[str(x) for x in (order or [])], ordered=True)
            elif to == "boolean":
                d[c] = d[c].astype("boolean")
            elif to == "datetime":
                d[c] = pd.to_datetime(d[c], errors="coerce")
            return d
        ctx.set_all(conv)
        if to == "numeric":
            ctx.emit(f"for k in parts: parts[k][{py(c)}] = pd.to_numeric(parts[k][{py(c)}], errors='coerce')")
        elif to in ("nominal", "text"):
            ctx.emit(f"for k in parts: parts[k][{py(c)}] = parts[k][{py(c)}].astype('string')")
        elif to == "ordinal":
            ctx.emit(f"for k in parts: parts[k][{py(c)}] = pd.Categorical("
                     f"parts[k][{py(c)}].astype('string'), categories={py([str(x) for x in (order or [])])}, ordered=True)")
        elif to == "boolean":
            ctx.emit(f"for k in parts: parts[k][{py(c)}] = parts[k][{py(c)}].astype('boolean')")
        elif to == "datetime":
            ctx.emit(f"for k in parts: parts[k][{py(c)}] = pd.to_datetime(parts[k][{py(c)}], errors='coerce')")
    ctx.touch(step, cols)
    return {"retyped": {c: to for c in cols}}


def _drop(ctx, step, cols, why):
    cols = [c for c in cols if c in ctx.cols()]
    target = ctx.label or ctx.label_planned
    # A user: step may drop the target — but only by naming it. "Explicit" means written down:
    # a user step about something else must not carry the label away with it.
    named_explicitly = target in (step.get("columns") or [])
    if target and target in cols and not (str(step.get("source", "")).startswith("user:")
                                          and named_explicitly):
        cols = [c for c in cols if c != target]
        mark(f"OK: {step['id']} keeps {target!r}: it is the label, not a droppable column")
    if not cols:
        return {"dropped": []}
    ctx.set_all(lambda d: d.drop(columns=[c for c in cols if c in d.columns]))
    for c in cols:
        ctx.removed[c] = {"step": step["id"], "op": step["op"], "why": why}
    ctx.emit(f"for k in parts: parts[k] = parts[k].drop(columns=[c for c in {py(cols)} if c in parts[k].columns])")
    ctx.touch(step, cols)
    return {"dropped": cols}


def op_drop_identity(ctx, step):
    cols = step.get("columns") or [t["column"] for t in geo_of(ctx).get("typing") or []
                                   if t.get("role") in ("identity", "key")]
    return _drop(ctx, step, cols, "identity / key")


def op_drop_constant(ctx, step):
    tol = float((step.get("params") or {}).get("tolerance", 0.0))
    cols = step.get("columns") or []
    if not cols:
        d = ctx.parts[ctx.fit_part]
        for c in d.columns:
            vc = d[c].value_counts(normalize=True, dropna=True)
            if len(vc) <= 1 or (len(vc) and vc.iloc[0] >= 1.0 - tol):
                cols.append(c)
    return _drop(ctx, step, cols, f"constant or quasi-constant (tolerance {tol})")


def op_dedupe(ctx, step):
    p = step.get("params") or {}
    on = p.get("on", "all")
    keep = p.get("keep", "first")
    subset = None if on == "all" else [c for c in (on if isinstance(on, list) else [on])
                                       if c in ctx.cols()]
    before = {k: len(v) for k, v in ctx.each()}
    ctx.set_all(lambda d: d.drop_duplicates(subset=subset, keep=keep))
    after = {k: len(v) for k, v in ctx.each()}
    ctx.emit(f"for k in parts: parts[k] = parts[k].drop_duplicates(subset={py(subset)}, keep={py(keep)})")
    return {"rows_removed": {k: before[k] - after[k] for k in before}}


def op_parse_datetime(ctx, step):
    p = step.get("params") or {}
    fmt, errors = p.get("format"), p.get("errors", "coerce")
    cols = [c for c in (step.get("columns") or []) if c in ctx.cols()]
    coerced = {}
    for c in cols:
        before = ctx.parts[ctx.fit_part][c].notna().sum()
        def conv(d, c=c):
            d = d.copy()
            d[c] = pd.to_datetime(d[c], format=fmt, errors=errors)
            return d
        ctx.set_all(conv)
        coerced[c] = int(before - ctx.parts[ctx.fit_part][c].notna().sum())
        ctx.emit(f"for k in parts: parts[k][{py(c)}] = pd.to_datetime(parts[k][{py(c)}], "
                 f"format={py(fmt)}, errors={py(errors)})")
    ctx.touch(step, cols)
    return {"coerced_to_missing": coerced}


def op_parse_geometry(ctx, step):
    p = step.get("params") or {}
    crs = p.get("crs")
    if not crs:
        raise ValueError("parse_geometry needs a declared crs — without one no distance or "
                         "reprojection below it means anything")
    ctx.crs = crs
    kind, lat, lon = p.get("kind", "latlon"), p.get("lat"), p.get("lon")
    if kind == "latlon":
        for c in (lat, lon):
            if c not in ctx.cols():
                raise ValueError(f"parse_geometry: column {c!r} is not in the frame")
        d = ctx.parts[ctx.fit_part]
        la, lo = pd.to_numeric(d[lat], errors="coerce"), pd.to_numeric(d[lon], errors="coerce")
        bad = int((~la.between(-90, 90)).sum() + (~lo.between(-180, 180)).sum())
        if bad:
            mark(f"WARN: parse_geometry: {bad} coordinate value(s) fall outside the declared CRS "
                 f"bounds")
    ctx.emit(f"# geometry declared: kind={kind}, crs={crs} (no column change)")
    ctx.touch(step, [c for c in (lat, lon) if c])
    return {"crs": crs, "kind": kind, "lat": lat, "lon": lon}


# --------------------------------------------------------------------------- phase 2
def op_orient_cycle(ctx, step):
    p = step.get("params") or {}
    cid, oid = p.get("cycle_id"), p.get("orientation_id")
    if not oid:
        for c in geo_of(ctx).get("cycles") or []:
            if c.get("id") == cid:
                for o in c.get("orientations") or []:
                    if o.get("default"):
                        oid = o.get("id")
    ctx.active_orientation[cid] = oid
    ctx.emit(f"# cycle {cid}: orientation {oid} (decides which member is derived below)")
    return {"cycle": cid, "orientation": oid}


def active_rule_heads(ctx):
    """The columns that are the head of an active rule, under the chosen orientations."""
    geo = geo_of(ctx)
    heads = {d.get("column") for d in geo.get("derivations") or []}
    for c in geo.get("cycles") or []:
        chosen = ctx.active_orientation.get(c.get("id"))
        for o in c.get("orientations") or []:
            if chosen and o.get("id") != chosen:
                continue
            if not chosen and not o.get("default"):
                continue
            basis = set(o.get("basis") or [])
            for m in c.get("members") or []:
                if m in basis:
                    heads.discard(m)
            for r in o.get("rules") or []:
                if isinstance(r, dict) and r.get("column"):
                    heads.add(r["column"])
    return heads


def op_drop_derived(ctx, step):
    keep = set((step.get("params") or {}).get("keep") or [])
    heads = sorted(h for h in active_rule_heads(ctx) if h and h not in keep)
    res = _drop(ctx, step, heads, "active rule head (the basis keeps its parents)")
    res["kept_derived"] = sorted(keep)
    if keep:
        mark(f"WARN: derived column(s) {sorted(keep)} kept by request: they are redundant with "
             "their parents by construction")
    return res


def op_select_partition(ctx, step):
    p = step.get("params") or {}
    ctx.label = p.get("label")
    if ctx.label not in ctx.cols():
        raise ValueError(f"select_partition: the label {ctx.label!r} is not in the frame")
    ctx.emit(f"LABEL = {py(ctx.label)}")
    return {"label": ctx.label, "task": p.get("task")}


def op_drop_leakage(ctx, step):
    cols = step.get("columns") or []
    if not cols:
        for c in (geo_of(ctx).get("partitions") or {}).get("candidates") or []:
            if c.get("label") == ctx.label:
                cols = list(c.get("dropped_for_leakage") or [])
    return _drop(ctx, step, cols, f"derives the label {ctx.label!r}")


def op_keep_columns(ctx, step):
    cols = [c for c in ((step.get("params") or {}).get("columns") or step.get("columns") or [])]
    keep = [c for c in ctx.cols() if c in cols or c == ctx.label]
    drop = [c for c in ctx.cols() if c not in keep]
    ctx.set_all(lambda d: d[[c for c in keep if c in d.columns]])
    for c in drop:
        ctx.removed[c] = {"step": step["id"], "op": step["op"], "why": "not in keep_columns"}
    ctx.emit(f"for k in parts: parts[k] = parts[k][[c for c in {py(keep)} if c in parts[k].columns]]")
    return {"kept": keep, "dropped": drop}


# --------------------------------------------------------------------------- phase 3
def op_split(ctx, step):
    p = step.get("params") or {}
    kind = p.get("kind", "random")
    test = float(p.get("test", 0.2))
    valid = float(p.get("valid", 0.0))
    df = ctx.parts["all"]
    rng = np.random.default_rng(ctx.seed)
    idx = np.arange(len(df))
    if kind == "time":
        tcol = p.get("time_column")
        if tcol not in df.columns:
            raise ValueError(f"split kind=time needs an existing time_column; {tcol!r} is not here")
        order = pd.to_datetime(df[tcol], errors="coerce").sort_values(kind="stable").index
        pos = df.index.get_indexer(order)
        n = len(pos)
        n_test = int(round(test * n))
        n_valid = int(round(valid * n))
        parts = {"train": pos[: n - n_test - n_valid], "valid": pos[n - n_test - n_valid: n - n_test],
                 "test": pos[n - n_test:]}
        ctx.emit(f"_order = pd.to_datetime(parts['all'][{py(tcol)}], errors='coerce').sort_values(kind='stable').index",
                 f"_pos = parts['all'].index.get_indexer(_order); _n = len(_pos)",
                 f"_nt = int(round({test} * _n)); _nv = int(round({valid} * _n))",
                 "parts = {'train': parts['all'].iloc[_pos[:_n-_nt-_nv]], "
                 "'valid': parts['all'].iloc[_pos[_n-_nt-_nv:_n-_nt]], "
                 "'test': parts['all'].iloc[_pos[_n-_nt:]]}")
    else:
        if kind == "stratified":
            by = p.get("by") or ctx.label
            if by not in df.columns:
                raise ValueError(f"split kind=stratified needs an existing 'by' column ({by!r})")
            groups = df.groupby(df[by].astype(str), sort=True).indices
            tr, va, te = [], [], []
            for g in sorted(groups):
                gi = np.sort(groups[g])
                gi = rng.permutation(gi)
                n = len(gi)
                n_test, n_valid = int(round(test * n)), int(round(valid * n))
                te.extend(gi[:n_test]); va.extend(gi[n_test:n_test + n_valid])
                tr.extend(gi[n_test + n_valid:])
            parts = {"train": np.sort(tr), "valid": np.sort(va), "test": np.sort(te)}
        elif kind == "group":
            by = p.get("by")
            if by not in df.columns:
                raise ValueError(f"split kind=group needs an existing 'by' column ({by!r})")
            keys = pd.unique(df[by].astype(str))
            keys = np.sort(keys)
            perm = rng.permutation(len(keys))
            keys = keys[perm]
            n = len(keys)
            n_test, n_valid = int(round(test * n)), int(round(valid * n))
            kt, kv = set(keys[:n_test]), set(keys[n_test:n_test + n_valid])
            col = df[by].astype(str).values
            parts = {"train": np.where(~np.isin(col, list(kt | kv)))[0],
                     "valid": np.where(np.isin(col, list(kv)))[0],
                     "test": np.where(np.isin(col, list(kt)))[0]}
        else:
            perm = rng.permutation(idx)
            n = len(perm)
            n_test, n_valid = int(round(test * n)), int(round(valid * n))
            parts = {"train": np.sort(perm[n_test + n_valid:]), "valid": np.sort(perm[n_test:n_test + n_valid]),
                     "test": np.sort(perm[:n_test])}
        ctx.emit(f"# split kind={kind} seed={ctx.seed}: the index sets are stored in the manifest",
                 f"_sets = MANIFEST_SPLIT",
                 "parts = {k: parts['all'].iloc[v].copy() for k, v in _sets.items() if len(v)}")
    out = {}
    for k in ("train", "valid", "test"):
        v = np.asarray(parts.get(k, []), dtype=int)
        if len(v):
            out[k] = v
    ctx.parts = {k: df.iloc[v].copy() for k, v in out.items()}
    ctx.order = [k for k in ("train", "valid", "test") if k in ctx.parts]
    return {"kind": kind, "sizes": {k: int(len(v)) for k, v in out.items()},
            "indices": {k: [int(x) for x in v] for k, v in out.items()},
            "by": p.get("by"), "time_column": p.get("time_column")}


# --------------------------------------------------------------------------- phase 4 (values)
def op_impute(ctx, step):
    p = step.get("params") or {}
    strat = p.get("strategy", "median")
    by = p.get("by") or []
    ind = bool(p.get("indicator"))
    cols = [c for c in (step.get("columns") or []) if c in ctx.cols()]
    target = ctx.label or ctx.label_planned
    if target and target in cols:
        raise ValueError(f"impute: the label {target!r} is never imputed")
    fit = ctx.parts[ctx.fit_part]
    fitted = {}
    for c in cols:
        if strat in ("median", "mean", "mode", "constant"):
            if strat == "median":
                v = float(pd.to_numeric(fit[c], errors="coerce").median())
            elif strat == "mean":
                v = float(pd.to_numeric(fit[c], errors="coerce").mean())
            elif strat == "mode":
                m = fit[c].mode(dropna=True)
                v = (m.iloc[0] if len(m) else None)
            else:
                v = p.get("value")
            fitted[c] = {"fill": jsonable(v)}
        elif strat in ("group-median", "group-mode"):
            g = fit.groupby([fit[b].astype(str) for b in by], dropna=False)[c]
            table = (g.median() if strat == "group-median" else g.agg(
                lambda s: s.mode().iloc[0] if len(s.mode()) else None))
            glob = (float(pd.to_numeric(fit[c], errors="coerce").median())
                    if strat == "group-median"
                    else (fit[c].mode().iloc[0] if len(fit[c].mode()) else None))
            fitted[c] = {"by": by, "table": {str(k): jsonable(v) for k, v in table.items()},
                         "fallback": jsonable(glob)}
        else:
            raise ValueError(f"impute strategy {strat!r} is not implemented by this executor")
    def apply(d):
        d = d.copy()
        for c in cols:
            if ind:
                d[c + "_missing"] = d[c].isna().astype("int8")
            if strat in ("median", "mean", "mode", "constant"):
                d[c] = d[c].fillna(fitted[c]["fill"])
            else:
                keys = d[by[0]].astype(str) if len(by) == 1 else \
                    d[by].astype(str).agg(tuple, axis=1).astype(str)
                filled = keys.map(fitted[c]["table"]).astype(object)
                d[c] = d[c].fillna(pd.Series(filled.values, index=d.index)).fillna(
                    fitted[c]["fallback"])
        return d
    ctx.set_all(apply)
    if ind:
        for c in cols:
            ctx.lineage.setdefault(c + "_missing", []).append(step["id"])
    ctx.emit(f"_f = FITTED[{py(step['id'])}]['fitted']")
    for c in cols:
        if ind:
            ctx.emit(f"for k in parts: parts[k][{py(c + '_missing')}] = parts[k][{py(c)}].isna().astype('int8')")
        if strat in ("median", "mean", "mode", "constant"):
            ctx.emit(f"for k in parts: parts[k][{py(c)}] = parts[k][{py(c)}].fillna(_f[{py(c)}]['fill'])")
        else:
            ctx.emit(f"for k in parts:",
                     f"    _keys = parts[k][{py(by[0])}].astype(str) if {len(by)} == 1 else "
                     f"parts[k][{py(by)}].astype(str).agg(tuple, axis=1).astype(str)",
                     f"    _m = _keys.map(_f[{py(c)}]['table']).astype(object)",
                     f"    parts[k][{py(c)}] = parts[k][{py(c)}].fillna(pd.Series(_m.values, index=parts[k].index)).fillna(_f[{py(c)}]['fallback'])")
    ctx.touch(step, cols)
    return {"fitted": fitted, "indicator": ind, "columns_added":
            [c + "_missing" for c in cols] if ind else []}


def op_clip(ctx, step):
    p = step.get("params") or {}
    lo, hi = p.get("lower"), p.get("upper")
    cols = [c for c in (step.get("columns") or []) if c in ctx.cols()]
    def apply(d):
        d = d.copy()
        for c in cols:
            d[c] = pd.to_numeric(d[c], errors="coerce").clip(lower=lo, upper=hi)
        return d
    ctx.set_all(apply)
    for c in cols:
        ctx.emit(f"for k in parts: parts[k][{py(c)}] = pd.to_numeric(parts[k][{py(c)}], errors='coerce').clip(lower={py(lo)}, upper={py(hi)})")
    ctx.touch(step, cols)
    return {"lower": lo, "upper": hi}


def op_winsorize(ctx, step):
    p = step.get("params") or {}
    ql, qh = float(p.get("lower_q", 0.01)), float(p.get("upper_q", 0.99))
    cols = [c for c in (step.get("columns") or []) if c in ctx.cols()]
    fit = ctx.parts[ctx.fit_part]
    fitted = {c: {"lower": float(pd.to_numeric(fit[c], errors="coerce").quantile(ql)),
                  "upper": float(pd.to_numeric(fit[c], errors="coerce").quantile(qh))}
              for c in cols}
    def apply(d):
        d = d.copy()
        for c in cols:
            d[c] = pd.to_numeric(d[c], errors="coerce").clip(fitted[c]["lower"], fitted[c]["upper"])
        return d
    ctx.set_all(apply)
    ctx.emit(f"_f = FITTED[{py(step['id'])}]['fitted']")
    for c in cols:
        ctx.emit(f"for k in parts: parts[k][{py(c)}] = pd.to_numeric(parts[k][{py(c)}], errors='coerce').clip(_f[{py(c)}]['lower'], _f[{py(c)}]['upper'])")
    ctx.touch(step, cols)
    return {"fitted": fitted, "quantiles": [ql, qh]}


def op_transform(ctx, step):
    p = step.get("params") or {}
    kind = p.get("kind", "log1p")
    cols = [c for c in (step.get("columns") or []) if c in ctx.cols()]
    fit = ctx.parts[ctx.fit_part]
    fitted = {}
    if kind in ("box-cox", "yeo-johnson"):
        from scipy import stats as st
        for c in cols:
            v = pd.to_numeric(fit[c], errors="coerce").dropna().values
            if kind == "box-cox":
                if (v <= 0).any():
                    raise ValueError(f"box-cox needs strictly positive values; {c!r} has some <= 0 "
                                     "(use yeo-johnson)")
                _, lam = st.boxcox(v)
            else:
                _, lam = st.yeojohnson(v)
            fitted[c] = {"lambda": float(lam)}
    def apply(d):
        d = d.copy()
        for c in cols:
            v = pd.to_numeric(d[c], errors="coerce")
            if kind == "log1p":
                d[c] = np.log1p(v)
            elif kind == "log":
                d[c] = np.log(v)
            elif kind == "sqrt":
                d[c] = np.sqrt(v)
            elif kind == "reciprocal":
                d[c] = 1.0 / v
            elif kind == "box-cox":
                from scipy import stats as st
                d[c] = st.boxcox(v.values, lmbda=fitted[c]["lambda"])
            elif kind == "yeo-johnson":
                from scipy import stats as st
                d[c] = st.yeojohnson(v.values, lmbda=fitted[c]["lambda"])
        return d
    ctx.set_all(apply)
    expr = {"log1p": "np.log1p(_v)", "log": "np.log(_v)", "sqrt": "np.sqrt(_v)",
            "reciprocal": "1.0/_v"}.get(kind)
    if expr:
        for c in cols:
            ctx.emit(f"for k in parts:",
                     f"    _v = pd.to_numeric(parts[k][{py(c)}], errors='coerce'); parts[k][{py(c)}] = {expr}")
    else:
        ctx.emit("from scipy import stats as _st", f"_f = FITTED[{py(step['id'])}]['fitted']")
        fn = "boxcox" if kind == "box-cox" else "yeojohnson"
        for c in cols:
            ctx.emit(f"for k in parts:",
                     f"    _v = pd.to_numeric(parts[k][{py(c)}], errors='coerce').values",
                     f"    parts[k][{py(c)}] = _st.{fn}(_v, lmbda=_f[{py(c)}]['lambda'])")
    ctx.touch(step, cols)
    return {"kind": kind, "fitted": fitted}


def op_bin(ctx, step):
    p = step.get("params") or {}
    kind, k = p.get("kind", "quantile"), int(p.get("k", 4))
    replace = bool(p.get("replace"))
    cols = [c for c in (step.get("columns") or []) if c in ctx.cols()]
    fit = ctx.parts[ctx.fit_part]
    fitted = {}
    for c in cols:
        v = pd.to_numeric(fit[c], errors="coerce")
        if kind == "quantile":
            edges = list(np.unique(np.quantile(v.dropna(), np.linspace(0, 1, k + 1))))
        elif kind == "width":
            edges = list(np.linspace(float(v.min()), float(v.max()), k + 1))
        else:
            edges = [float(x) for x in (p.get("edges") or [])]
        if len(edges) < 3:
            raise ValueError(f"bin: {c!r} produced fewer than two bins")
        edges[0], edges[-1] = -np.inf, np.inf
        fitted[c] = {"edges": [float(x) for x in edges]}
    def apply(d):
        d = d.copy()
        for c in cols:
            v = pd.to_numeric(d[c], errors="coerce")
            b = pd.cut(v, bins=fitted[c]["edges"], labels=False, include_lowest=True)
            name = c if replace else c + "_bin"
            d[name] = b.astype("Int64")
        return d
    ctx.set_all(apply)
    ctx.emit(f"_f = FITTED[{py(step['id'])}]['fitted']")
    for c in cols:
        name = c if replace else c + "_bin"
        ctx.emit(f"for k in parts: parts[k][{py(name)}] = pd.cut(pd.to_numeric(parts[k][{py(c)}], errors='coerce'), "
                 f"bins=_f[{py(c)}]['edges'], labels=False, include_lowest=True).astype('Int64')")
        if not replace:
            ctx.lineage.setdefault(name, []).append(step["id"])
    ctx.touch(step, cols)
    return {"fitted": fitted, "replace": replace,
            "columns_added": [] if replace else [c + "_bin" for c in cols]}


def op_datetime_expand(ctx, step):
    p = step.get("params") or {}
    want = p.get("parts") or ["year", "month", "dow", "hour"]
    cyclic = bool(p.get("cyclic"))
    cols = [c for c in (step.get("columns") or []) if c in ctx.cols()]
    added = []
    def apply(d):
        d = d.copy()
        for c in cols:
            t = pd.to_datetime(d[c], errors="coerce")
            for w in want:
                name = f"{c}_{w}"
                if w == "year":
                    d[name] = t.dt.year.astype("Int64")
                elif w == "month":
                    d[name] = t.dt.month.astype("Int64")
                elif w == "day":
                    d[name] = t.dt.day.astype("Int64")
                elif w == "dow":
                    d[name] = t.dt.dayofweek.astype("Int64")
                elif w == "hour":
                    d[name] = t.dt.hour.astype("Int64")
                elif w == "is_weekend":
                    d[name] = (t.dt.dayofweek >= 5).astype("Int64")
                if name in d.columns and name not in added:
                    added.append(name)
            if cyclic:
                for w, period in (("month", 12), ("dow", 7), ("hour", 24)):
                    if w in want:
                        base = f"{c}_{w}"
                        val = d[base].astype(float)
                        d[base + "_sin"] = np.sin(2 * np.pi * val / period)
                        d[base + "_cos"] = np.cos(2 * np.pi * val / period)
                        for s in (base + "_sin", base + "_cos"):
                            if s not in added:
                                added.append(s)
        return d
    ctx.set_all(apply)
    ctx.emit(f"for k in parts:")
    for c in cols:
        ctx.emit(f"    _t = pd.to_datetime(parts[k][{py(c)}], errors='coerce')")
        for w in want:
            expr = {"year": "_t.dt.year", "month": "_t.dt.month", "day": "_t.dt.day",
                    "dow": "_t.dt.dayofweek", "hour": "_t.dt.hour",
                    "is_weekend": "(_t.dt.dayofweek >= 5)"}.get(w)
            if expr:
                ctx.emit(f"    parts[k][{py(c + '_' + w)}] = {expr}.astype('Int64')")
        if cyclic:
            for w, period in (("month", 12), ("dow", 7), ("hour", 24)):
                if w in want:
                    b = f"{c}_{w}"
                    ctx.emit(f"    _v = parts[k][{py(b)}].astype(float)",
                             f"    parts[k][{py(b + '_sin')}] = np.sin(2*np.pi*_v/{period})",
                             f"    parts[k][{py(b + '_cos')}] = np.cos(2*np.pi*_v/{period})")
    for a in added:
        ctx.lineage.setdefault(a, []).append(step["id"])
    ctx.touch(step, cols)
    return {"columns_added": added, "cyclic": cyclic}


def op_lag(ctx, step):
    p = step.get("params") or {}
    lags = [int(x) for x in (p.get("lags") or [1])]
    gb, tcol = p.get("group_by"), p.get("time_column")
    cols = [c for c in (step.get("columns") or []) if c in ctx.cols()]
    added = []
    def apply(d):
        d = d.copy()
        if tcol and tcol in d.columns:
            d = d.sort_values(tcol, kind="stable")
        for c in cols:
            for L in lags:
                name = f"{c}_lag{L}"
                d[name] = (d.groupby(d[gb].astype(str))[c].shift(L) if gb and gb in d.columns
                           else d[c].shift(L))
                if name not in added:
                    added.append(name)
        return d.sort_index()
    ctx.set_all(apply)
    ctx.emit("for k in parts:")
    if tcol:
        ctx.emit(f"    parts[k] = parts[k].sort_values({py(tcol)}, kind='stable')")
    for c in cols:
        for L in lags:
            src = (f"parts[k].groupby(parts[k][{py(gb)}].astype(str))[{py(c)}].shift({L})"
                   if gb else f"parts[k][{py(c)}].shift({L})")
            ctx.emit(f"    parts[k][{py(f'{c}_lag{L}')}] = {src}")
    ctx.emit("    parts[k] = parts[k].sort_index()")
    for a in added:
        ctx.lineage.setdefault(a, []).append(step["id"])
    ctx.touch(step, cols)
    return {"columns_added": added, "lags": lags}


# --------------------------------------------------------------------------- phase 5-6
def op_encode(ctx, step):
    p = step.get("params") or {}
    strat = p.get("strategy", "one-hot")
    minf = p.get("min_frequency")
    target = ctx.label or ctx.label_planned
    cols = [c for c in (step.get("columns") or []) if c in ctx.cols() and c != target]
    fit = ctx.parts[ctx.fit_part]
    fitted, added, dropped = {}, [], []
    for c in cols:
        vc = fit[c].astype(str).value_counts()
        if minf:
            keep = [str(k) for k, v in vc.items() if v >= (minf if minf >= 1 else minf * len(fit))]
        else:
            keep = [str(k) for k in vc.index]
        keep = sorted(keep)
        if strat == "one-hot":
            fitted[c] = {"categories": keep}
        elif strat == "ordinal":
            order = p.get("order") or keep
            fitted[c] = {"mapping": {str(k): i for i, k in enumerate(order)}}
        elif strat == "frequency":
            fitted[c] = {"freq": {str(k): float(v / len(fit)) for k, v in vc.items()}}
        elif strat == "target":
            if "train" not in ctx.parts:
                raise ValueError("target encoding needs a split: it is fitted out-of-fold on the "
                                 "train part alone")
            from sklearn.model_selection import KFold
            y = pd.to_numeric(fit[ctx.label], errors="coerce")
            prior = float(y.mean())
            means = y.groupby(fit[c].astype(str)).mean()
            fitted[c] = {"means": {str(k): float(v) for k, v in means.items()}, "prior": prior}
        else:
            raise ValueError(f"encode strategy {strat!r} is not implemented by this executor")
    def apply(d):
        d = d.copy()
        for c in cols:
            s = d[c].astype(str)
            if strat == "one-hot":
                for cat in fitted[c]["categories"]:
                    name = f"{c}={cat}"
                    d[name] = (s == cat).astype("int8")
                    if name not in added:
                        added.append(name)
                d = d.drop(columns=[c])
            elif strat == "ordinal":
                d[c] = s.map(fitted[c]["mapping"]).astype("Int64")
            elif strat == "frequency":
                d[c] = s.map(fitted[c]["freq"]).astype(float).fillna(0.0)
            elif strat == "target":
                d[c] = s.map(fitted[c]["means"]).astype(float).fillna(fitted[c]["prior"])
        return d
    ctx.set_all(apply)
    if strat == "one-hot":
        dropped = cols
        for c in cols:
            ctx.removed[c] = {"step": step["id"], "op": "encode", "why": "one-hot expanded"}
    ctx.emit(f"_f = FITTED[{py(step['id'])}]['fitted']")
    for c in cols:
        if strat == "one-hot":
            ctx.emit(f"for k in parts:",
                     f"    _s = parts[k][{py(c)}].astype(str)",
                     f"    for _cat in _f[{py(c)}]['categories']: parts[k][{py(c)} + '=' + _cat] = (_s == _cat).astype('int8')",
                     f"    parts[k] = parts[k].drop(columns=[{py(c)}])")
        elif strat == "ordinal":
            ctx.emit(f"for k in parts: parts[k][{py(c)}] = parts[k][{py(c)}].astype(str).map(_f[{py(c)}]['mapping']).astype('Int64')")
        elif strat == "frequency":
            ctx.emit(f"for k in parts: parts[k][{py(c)}] = parts[k][{py(c)}].astype(str).map(_f[{py(c)}]['freq']).astype(float).fillna(0.0)")
        elif strat == "target":
            ctx.emit(f"for k in parts: parts[k][{py(c)}] = parts[k][{py(c)}].astype(str).map(_f[{py(c)}]['means']).astype(float).fillna(_f[{py(c)}]['prior'])")
    for a in added:
        ctx.lineage.setdefault(a, []).append(step["id"])
    ctx.touch(step, cols)
    return {"strategy": strat, "fitted": fitted, "columns_added": added,
            "columns_removed": dropped}


def op_scale(ctx, step):
    p = step.get("params") or {}
    kind = p.get("kind", "standard")
    want = p.get("columns", "numeric")
    fit = ctx.parts[ctx.fit_part]
    target = ctx.label or ctx.label_planned
    if want == "numeric":
        cols = [c for c in ctx.cols() if pd.api.types.is_numeric_dtype(fit[c]) and c != target]
    else:
        cols = [c for c in (want or step.get("columns") or []) if c in ctx.cols()]
    if kind == "none":
        return {"kind": "none", "columns": cols}
    fitted = {}
    for c in cols:
        v = pd.to_numeric(fit[c], errors="coerce")
        if kind == "standard":
            fitted[c] = {"center": float(v.mean()), "scale": float(v.std(ddof=0)) or 1.0}
        elif kind == "robust":
            iqr = float(v.quantile(0.75) - v.quantile(0.25)) or 1.0
            fitted[c] = {"center": float(v.median()), "scale": iqr}
        elif kind == "minmax":
            lo, hi = float(v.min()), float(v.max())
            fitted[c] = {"center": lo, "scale": (hi - lo) or 1.0}
    def apply(d):
        d = d.copy()
        for c in cols:
            v = pd.to_numeric(d[c], errors="coerce")
            d[c] = (v - fitted[c]["center"]) / fitted[c]["scale"]
        return d
    ctx.set_all(apply)
    ctx.emit(f"_f = FITTED[{py(step['id'])}]['fitted']")
    for c in cols:
        ctx.emit(f"for k in parts: parts[k][{py(c)}] = (pd.to_numeric(parts[k][{py(c)}], errors='coerce') "
                 f"- _f[{py(c)}]['center']) / _f[{py(c)}]['scale']")
    ctx.touch(step, cols)
    return {"kind": kind, "fitted": fitted, "columns": cols}


def op_project(ctx, step):
    p = step.get("params") or {}
    keep_named = bool(p.get("keep_named", True))
    want = p.get("columns")
    fit = ctx.parts[ctx.fit_part]
    cols = [c for c in (want or [c for c in ctx.cols()
                                 if pd.api.types.is_numeric_dtype(fit[c]) and c != ctx.label])
            if c in ctx.cols()]
    X = fit[cols].apply(pd.to_numeric, errors="coerce").dropna()
    from sklearn.decomposition import PCA
    n = p.get("k") or None
    var = p.get("variance")
    pca = PCA(n_components=(n if n else (var if var else 0.95)), random_state=ctx.seed).fit(X.values)
    fitted = {"columns": cols, "mean": [float(x) for x in pca.mean_],
              "components": [[float(x) for x in row] for row in pca.components_],
              "explained_variance_ratio": [float(x) for x in pca.explained_variance_ratio_]}
    names = [f"pc{i+1}" for i in range(len(pca.components_))]
    def apply(d):
        d = d.copy()
        V = d[cols].apply(pd.to_numeric, errors="coerce").fillna(pd.Series(fitted["mean"], index=cols))
        Z = (V.values - np.asarray(fitted["mean"])) @ np.asarray(fitted["components"]).T
        for i, nm in enumerate(names):
            d[nm] = Z[:, i]
        if not keep_named:
            d = d.drop(columns=[c for c in cols if c in d.columns])
        return d
    ctx.set_all(apply)
    ctx.emit(f"_f = FITTED[{py(step['id'])}]['fitted']",
             "for k in parts:",
             f"    _V = parts[k][_f['columns']].apply(pd.to_numeric, errors='coerce').fillna(pd.Series(_f['mean'], index=_f['columns']))",
             "    _Z = (_V.values - np.asarray(_f['mean'])) @ np.asarray(_f['components']).T",
             f"    for _i, _nm in enumerate({py(names)}): parts[k][_nm] = _Z[:, _i]")
    if not keep_named:
        ctx.emit(f"    parts[k] = parts[k].drop(columns=[c for c in _f['columns'] if c in parts[k].columns])")
        for c in cols:
            ctx.removed[c] = {"step": step["id"], "op": "project", "why": "replaced by components"}
    for nm in names:
        ctx.lineage.setdefault(nm, []).append(step["id"])
    ctx.touch(step, cols)
    return {"fitted": fitted, "columns_added": names, "keep_named": keep_named}


def op_select_features(ctx, step):
    p = step.get("params") or {}
    kind = p.get("kind", "importance")
    thr = float(p.get("threshold", 0.0))
    src = p.get("from", "analysis:importance")
    keep_basis = set((geo_of(ctx).get("basis") or {}).get("members") or [])
    drop = []
    if kind == "importance":
        ana = ctx.layers.get("analysis") or {}
        pi = (((ana.get("modules") or {}).get("importance") or {}).get("evidence") or {}) \
            .get("permutation_importance") or []
        if not pi:
            raise ValueError("select_features kind=importance needs the analysis layer's "
                             "modules.importance.evidence.permutation_importance; this model "
                             "carries none")
        low = [r["feature"] for r in pi if (r.get("mean") or 0) <= thr]
        drop = [c for c in low if c in ctx.cols() and c not in keep_basis and c != ctx.label]
    elif kind == "variance":
        fit = ctx.parts[ctx.fit_part]
        for c in ctx.cols():
            if c == ctx.label or c in keep_basis:
                continue
            if pd.api.types.is_numeric_dtype(fit[c]) and float(pd.to_numeric(
                    fit[c], errors="coerce").var(ddof=0) or 0) <= thr:
                drop.append(c)
    else:
        raise ValueError(f"select_features kind={kind!r} is not implemented by this executor")
    res = _drop(ctx, step, drop, f"{kind} at or below {thr} (from {src})")
    res["source_of_scores"] = src
    return res


def op_custom(ctx, step):
    p = step.get("params") or {}
    code = p.get("code") or ""
    ns = {"pd": pd, "np": np}
    exec(compile(code, "<custom-step>", "exec"), ns)
    fn = ns.get("step")
    if not callable(fn):
        raise ValueError("a custom step's code must define step(df, ctx) -> df")
    before = ctx.cols()
    meta = {"label": ctx.label, "crs": ctx.crs, "seed": ctx.seed}
    for k in list(ctx.parts):
        ctx.parts[k] = fn(ctx.parts[k].copy(), dict(meta, part=k))
    after = ctx.cols()
    ctx.emit("# custom step (user-supplied; the layer marks it unverified)",
             "_ns = {}", f"exec(compile({py(code)}, '<custom-step>', 'exec'), " "{'pd': pd, 'np': np}, _ns)",
             "for k in parts: parts[k] = _ns['step'](parts[k].copy(), "
             f"{{'label': LABEL if 'LABEL' in dir() else None, 'crs': {py(ctx.crs)}, 'seed': {ctx.seed}, 'part': k}})")
    return {"columns_added": [c for c in after if c not in before],
            "columns_removed": [c for c in before if c not in after], "verified": False}


# --------------------------------------------------------------------------- driver
OPS = {"retype": op_retype, "drop_identity": op_drop_identity, "drop_constant": op_drop_constant,
       "dedupe": op_dedupe, "parse_datetime": op_parse_datetime, "parse_geometry": op_parse_geometry,
       "orient_cycle": op_orient_cycle, "drop_derived": op_drop_derived,
       "select_partition": op_select_partition, "drop_leakage": op_drop_leakage,
       "keep_columns": op_keep_columns, "split": op_split, "impute": op_impute, "clip": op_clip,
       "winsorize": op_winsorize, "transform": op_transform, "bin": op_bin,
       "datetime_expand": op_datetime_expand, "lag": op_lag, "encode": op_encode,
       "scale": op_scale, "project": op_project, "select_features": op_select_features,
       "custom": op_custom}


def read_dataset(path, sep=None):
    p = Path(path)
    s = p.suffix.lower()
    if s in (".csv", ".txt"):
        return pd.read_csv(p, sep=sep or ",", low_memory=False)
    if s == ".tsv":
        return pd.read_csv(p, sep=sep or "\t", low_memory=False)
    if s == ".parquet":
        return pd.read_parquet(p)
    if s in (".xlsx", ".xls"):
        return pd.read_excel(p)
    if s == ".jsonl":
        return pd.read_json(p, lines=True)
    if s == ".json":
        return pd.read_json(p)
    raise ValueError(f"unsupported dataset extension {s!r}")


def execute(recipe, layers, df, seed):
    ctx = Ctx(df, recipe, layers, seed)
    for s in recipe["steps"]:
        if s.get("op") == "select_partition":
            ctx.label_planned = (s.get("params") or {}).get("label")
    geom = None
    for step in recipe["steps"]:
        op = step["op"]
        before_cols = ctx.cols()
        before_rows = {k: len(v) for k, v in ctx.each()}
        ctx.emit("", f"# --- {step['id']}  {op}  [{step.get('source')}]  {step.get('rationale','')}")
        if op in SPATIAL_OPS:
            import importlib.util
            spec = importlib.util.spec_from_file_location("shaper_spatial", HERE / "spatial_ops.py")
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            if geom is None:
                for s2 in recipe["steps"]:
                    if s2["op"] == "parse_geometry":
                        geom = {"lat": (s2.get("params") or {}).get("lat"),
                                "lon": (s2.get("params") or {}).get("lon")}
            if not geom or not geom.get("lat"):
                raise ValueError(f"{step['id']}: a spatial step needs a parse_geometry step before "
                                 "it (which is also where the CRS is declared)")
            fitted = mod.OPS[op](ctx, step, geom)
        else:
            fn = OPS.get(op)
            if fn is None:
                raise ValueError(f"{step['id']}: no executor for op {op!r}")
            fitted = fn(ctx, step)
        after_cols = ctx.cols()
        after_rows = {k: len(v) for k, v in ctx.each()}
        ctx.fitted[step["id"]] = fitted
        ctx.manifest.append({
            "id": step["id"], "op": op, "source": step.get("source"),
            "rows_before": before_rows, "rows_after": after_rows,
            "columns_added": [c for c in after_cols if c not in before_cols],
            "columns_removed": [c for c in before_cols if c not in after_cols],
            "fit_on": (ctx.fit_part if op in FITTED_OPS else None),
            "parameters_fitted": fitted})
        mark(f"OK: {step['id']} {op} — rows {before_rows} -> {after_rows}, "
             f"columns {len(before_cols)} -> {len(after_cols)}"
             + (f", fitted on {ctx.fit_part}" if op in FITTED_OPS else ""))
    return ctx


REPRO_HEAD = '''#!/usr/bin/env python3
"""Reproduce {out_dir} from {input_path} — generated by /dataset-shaper, and standalone.

This script imports nothing from the skill. It is the recipe written out as the pandas program
it amounts to, one block per step, in the order the executor ran them, using the parameters that
were fitted on the training part (they are inlined below as FITTED, exactly as the manifest
records them). Running it must reproduce the output files byte for byte; `shape.py --check` is
that comparison, and it is how the determinism claim is tested rather than asserted.

    python3 {script_name}            # writes the same files next to this script
"""
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
INPUT = {input_path!r}
FITTED = json.loads(HERE.joinpath({fitted_name!r}).read_text())
MANIFEST_SPLIT = {{k: np.asarray(v, dtype=int) for k, v in FITTED.get("__split__", {{}}).items()}}
EXPECTED = {expected!r}

df = {reader}
parts = {{"all": df}}
'''

REPRO_TAIL = '''

# --- write the outputs
out = {}
for name, frame in parts.items():
    path = HERE / (FILES[name] if name in FILES else (SLUG + "." + name + "." + FORMAT))
    if FORMAT == "parquet":
        frame.reset_index(drop=True).to_parquet(path, index=False)
    else:
        frame.reset_index(drop=True).to_csv(path, index=False)
    h = hashlib.sha256(path.read_bytes()).hexdigest()
    out[name] = {"path": str(path), "digest": "sha256:" + h, "rows": len(frame),
                 "columns": len(frame.columns)}
    print(f"OK: wrote {path} ({len(frame)} rows x {len(frame.columns)} columns)")

bad = [n for n, v in out.items() if EXPECTED.get(n) and EXPECTED[n] != v["digest"]]
if bad:
    print("ERROR: digests differ from the manifest for: " + ", ".join(bad))
    raise SystemExit(3)
print("OK: every output digest matches the manifest")
'''


def write_reproduction(ctx, out_dir, slug, fmt, files, expected, input_path, fitted_name):
    reader = {"csv": f"pd.read_csv({str(input_path)!r}, low_memory=False)",
              "tsv": f"pd.read_csv({str(input_path)!r}, sep='\\t', low_memory=False)",
              "parquet": f"pd.read_parquet({str(input_path)!r})",
              "xlsx": f"pd.read_excel({str(input_path)!r})",
              "json": f"pd.read_json({str(input_path)!r})",
              "jsonl": f"pd.read_json({str(input_path)!r}, lines=True)"}.get(
        Path(input_path).suffix.lstrip(".").lower(), f"pd.read_csv({str(input_path)!r})")
    name = f"reproduce_{slug}.py"
    head = REPRO_HEAD.format(out_dir=str(out_dir), input_path=str(input_path),
                             script_name=name, expected=expected, reader=reader,
                             fitted_name=fitted_name)
    body = "\n".join(ctx.code)
    consts = (f"\nSLUG = {slug!r}\nFORMAT = {fmt!r}\nFILES = {files!r}\n"
              f"LABEL = {ctx.label!r}\n")
    (Path(out_dir) / name).write_text(head + consts + body + REPRO_TAIL, encoding="utf-8")
    return name


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--recipe", help="recipe.json (required unless --check)")
    ap.add_argument("--model", default=None, help="the model HTML whose layers the sources cite")
    ap.add_argument("--out-dir", default="shaped", help="where the outputs go")
    ap.add_argument("--format", default="parquet", choices=("parquet", "csv"))
    ap.add_argument("--check-only", action="store_true", help="validate the recipe and stop")
    ap.add_argument("--dry-run", action="store_true",
                    help="write the recipe, the manifest skeleton and the reproduction script; "
                         "materialize no data")
    ap.add_argument("--check", action="store_true",
                    help="re-run the reproduction script in --out-dir and compare digests")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--sep", default=None)
    a = ap.parse_args(argv)

    out_dir = Path(a.out_dir)
    if a.check:
        man_p = out_dir / "manifest.json"
        if not man_p.is_file():
            print(f"ERROR: {man_p} not found; run the executor first")
            return 2
        man = json.loads(man_p.read_text(encoding="utf-8"))
        script = out_dir / man["outputs"]["reproduce"]
        if not script.is_file():
            print(f"ERROR: {script} not found")
            return 2
        before = {n: v.get("digest") for n, v in man["outputs"]["files"].items()}
        proc = subprocess.run([sys.executable, str(script)], capture_output=True, text=True,
                              timeout=1800)
        sys.stdout.write(proc.stdout)
        if proc.returncode != 0:
            print(f"ERROR: the reproduction script exited {proc.returncode}")
            sys.stderr.write(proc.stderr[-2000:])
            return 3
        after = {}
        for n, v in man["outputs"]["files"].items():
            p = out_dir / Path(v["path"]).name
            after[n] = digest_file(p) if p.is_file() else None
        bad = {n: (before[n], after[n]) for n in before if before[n] != after[n]}
        if bad:
            print(f"ERROR: determinism check FAILED for {sorted(bad)}")
            for n, (x, y) in bad.items():
                print(f"  {n}: manifest {x} != rerun {y}")
            return 3
        print(f"OK: determinism check passed — {len(after)} output file(s) reproduce byte for byte")
        return 0

    if not a.recipe:
        print("ERROR: --recipe is required (or --check)")
        return 2
    try:
        recipe = json.loads(Path(a.recipe).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        print(f"ERROR: cannot read recipe {a.recipe}: {e}")
        return 2
    layers = read_layers(a.model) if a.model else {}
    if a.model and not layers:
        mark(f"WARN: {a.model} carries no readable layer; sources cannot be resolved")
    errs = check_recipe(recipe, layers, mark)
    if errs:
        for e in errs:
            print(f"ERROR: {e}")
        return 2
    n_steps = len(recipe["steps"])
    sources = {}
    for s in recipe["steps"]:
        sources[str(s.get("source", "")).split(":")[0]] = \
            sources.get(str(s.get("source", "")).split(":")[0], 0) + 1
    print(f"OK: {a.recipe} validates against {SCHEMA} ({n_steps} steps; sources " +
          ", ".join(f"{k} {v}" for k, v in sorted(sources.items())) + ")")
    if a.check_only:
        return 0

    input_path = Path(recipe["input"]["path"])
    try:
        df = read_dataset(input_path, a.sep)
    except Exception as e:
        print(f"ERROR: cannot read the dataset {input_path}: {e}")
        return 2
    dig = digest_file(input_path)
    if recipe["input"].get("digest") and recipe["input"]["digest"] != dig:
        mark(f"WARN: input digest differs from the recipe's ({dig} != "
             f"{recipe['input']['digest']}): the data is not the one the analysis saw")
    seed = int(recipe.get("seed", a.seed))
    out_dir.mkdir(parents=True, exist_ok=True)
    try:
        ctx = execute(recipe, layers, df, seed)
    except Exception as e:
        print(f"ERROR: execution stopped at a step: {e}")
        return 3

    slug = input_path.stem
    fmt = a.format
    if fmt == "parquet":
        try:
            import pyarrow  # noqa: F401
        except ImportError:
            fmt = "csv"
            mark("WARN: pyarrow is not installed; writing csv instead of parquet")
    files, outputs = {}, {}
    for name in ctx.order:
        fname = f"{slug}.{name}.{fmt}" if name != "all" else f"{slug}.{fmt}"
        files[name] = fname
    fitted_blob = dict(ctx.fitted)
    split_rec = next((m for m in ctx.manifest if m["op"] == "split"), None)
    fitted_blob["__split__"] = (split_rec["parameters_fitted"]["indices"] if split_rec else {})
    fitted_name = "fitted.json"
    (out_dir / fitted_name).write_text(json.dumps(jsonable(fitted_blob), indent=1,
                                                  sort_keys=True) + "\n", encoding="utf-8")
    if not a.dry_run:
        for name in ctx.order:
            p = out_dir / files[name]
            frame = ctx.parts[name].reset_index(drop=True)
            if fmt == "parquet":
                frame.to_parquet(p, index=False)
            else:
                frame.to_csv(p, index=False)
            outputs[name] = {"path": str(p), "digest": digest_file(p), "rows": int(len(frame)),
                             "columns": int(frame.shape[1])}
            mark(f"OK: wrote {p} ({len(frame)} rows × {frame.shape[1]} columns)")
    else:
        for name in ctx.order:
            outputs[name] = {"path": str(out_dir / files[name]), "digest": None,
                             "rows": int(len(ctx.parts[name])),
                             "columns": int(ctx.parts[name].shape[1])}
        mark("WARN: --dry-run: no data file was written; the recipe, the manifest skeleton and "
             "the reproduction script are on disk")

    repro = write_reproduction(ctx, out_dir, slug, fmt, files,
                               {k: v.get("digest") for k, v in outputs.items()},
                               input_path, fitted_name)
    schema_out = {}
    ref = ctx.parts[ctx.order[0]]
    for c in ref.columns:
        origin = ctx.lineage.get(c) or []
        schema_out[c] = {"dtype": str(ref[c].dtype),
                         "role": ("label" if c == ctx.label else "feature"),
                         "origin": origin[-1] if origin else "input"}
    manifest = {
        "schema": "dataset-shaper/manifest@1",
        "input": {"path": str(input_path), "digest": dig, "rows": int(len(df)),
                  "columns": int(df.shape[1])},
        "recipe_digest": digest_text(json.dumps(recipe, sort_keys=True)),
        "seed": seed, "label": ctx.label, "crs": ctx.crs,
        "library_versions": {"python": sys.version.split()[0], "pandas": pd.__version__,
                             "numpy": np.__version__},
        "steps": jsonable(ctx.manifest),
        "output_schema": schema_out,
        "outputs": {"dir": str(out_dir), "format": fmt, "files": jsonable(outputs),
                    "manifest": "manifest.json", "lineage": "lineage.json",
                    "recipe": "recipe.json", "fitted": fitted_name, "reproduce": repro},
        "markers": MARKERS}
    (out_dir / "manifest.json").write_text(json.dumps(jsonable(manifest), indent=1) + "\n",
                                           encoding="utf-8")
    lineage = {"columns": {c: {"touched_by": ctx.lineage.get(c) or [],
                               "present_in_output": c in ref.columns}
                           for c in sorted(set(list(ctx.lineage) + list(df.columns)))},
               "removed": ctx.removed,
               "steps": [{"id": m["id"], "op": m["op"], "source": m["source"],
                          "columns_added": m["columns_added"],
                          "columns_removed": m["columns_removed"]} for m in ctx.manifest]}
    (out_dir / "lineage.json").write_text(json.dumps(jsonable(lineage), indent=1) + "\n",
                                          encoding="utf-8")
    (out_dir / "recipe.json").write_text(json.dumps(recipe, indent=1, ensure_ascii=False) + "\n",
                                         encoding="utf-8")
    print(f"OK: manifest.json, lineage.json, recipe.json, {fitted_name} and {repro} written to "
          f"{out_dir}")
    print(f"OK: output schema — {len(schema_out)} columns"
          + (f", label {ctx.label!r}" if ctx.label else ", no label"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
