# dataset-shaper contract — the recipe, the outputs, the `shape` layer

`/dataset-shaper` turns *decisions already taken* into a new dataset. The decisions live in the layers of the input HTML — `geometry` (from `/dataset-forge`: typing, basis, derivations, cycle orientations, partition and leakage set) and `analysis` (from `/data-lens`: findings and their transformation candidates, user stances) — and in what the user says during the run. The skill compiles them into a **recipe**, executes the recipe with a script, verifies the result, and records everything as one additive `shape` layer. The recipe is the truth: the script does exactly what it says, the reproduction script does the same without the skill, and the layer shows it.

## 1. The recipe (`recipe.json`)

```json
{
  "schema": "dataset-shaper/recipe@1",
  "input": { "path": "orders.csv", "digest": "sha256:<file digest>", "rows": 600, "columns": 15,
             "model": "orders.domain.analysis.html", "model_digest": "sha256:<canonical Turtle digest>",
             "layers_read": ["geometry", "analysis"] },
  "seed": 7,
  "goal": "train-ready | clean | basis-only | spatial-features | custom",
  "target": "late | null",
  "steps": [
    {
      "id": "S1", "op": "retype", "columns": ["zip"], "params": { "to": "nominal" },
      "source": "geometry:typing/zip",
      "rationale": "postal code parsed as integer; categorical by meaning",
      "alternatives": [],
      "consequences": { "rows": "none", "columns": "none", "downstream": "one-hot or target encoding later, not scaling" },
      "reversible": true
    },
    {
      "id": "S4", "op": "drop_derived", "columns": ["total", "subtotal"],
      "params": { "orientation": { "price-qty-total": "total-derived" } },
      "source": "geometry:cycles/price-qty-total",
      "rationale": "keep the basis; total and subtotal are rule heads under the chosen orientation",
      "alternatives": [ { "params": { "orientation": { "price-qty-total": "unit-price-derived" } }, "when": "if unit_price is the unobservable quantity at prediction time" } ],
      "consequences": { "rows": "none", "columns": "−2", "downstream": "a linear model no longer sees an exactly collinear column" },
      "reversible": false
    },
    {
      "id": "S6", "op": "impute", "columns": ["delivered_days"],
      "params": { "strategy": "group-median", "by": ["zip"], "indicator": true, "fit_on": "train" },
      "source": "analysis:F1/T1",
      "rationale": "missing not at random across zip (F1)",
      "alternatives": [ { "params": { "strategy": "median" }, "when": "if the zip dependence is judged spurious" } ],
      "consequences": { "rows": "none", "columns": "+1 (delivered_days_missing)", "downstream": "the indicator lets a model use the missingness itself" },
      "reversible": false
    },
    {
      "id": "S9", "op": "split", "columns": [], "params": { "kind": "stratified", "by": "late", "test": 0.2, "valid": 0.1 },
      "source": "shaper:default",
      "rationale": "no time column; stratify on the label so rare positives survive in every split",
      "alternatives": [ { "params": { "kind": "group", "by": "customer_id" }, "when": "if rows of one customer must not straddle splits" } ],
      "consequences": { "rows": "600 → 420 / 60 / 120", "columns": "none", "downstream": "every fitted step after this one is fitted on train only" },
      "reversible": true
    }
  ],
  "outputs": { "dir": "shaped/", "format": "parquet | csv", "files": ["orders.train.parquet", "orders.valid.parquet", "orders.test.parquet"],
               "recipe": "shaped/recipe.json", "manifest": "shaped/manifest.json", "lineage": "shaped/lineage.json", "reproduce": "shaped/reproduce_orders.py" }
}
```

**Sources** are the provenance tags of every step and the rule that makes the recipe honest: `geometry:<path>` (a typing entry, a derivation, a cycle orientation, the partition — paths use the geometry layer's own key names: `geometry:typing/zip`, `geometry:derivations/total`, `geometry:cycles/price-qty-total`, `geometry:partitions/late`), `analysis:F<n>/T<m>` or `analysis:turn<N>/T<m>` (a transformation candidate, from a finding or a dialogue turn), `user:<turn or stance>` (something the user said in this run, or `user:stance/ST<n>` for a recorded analysis stance), `shaper:default` (a step the skill added on its own because the goal requires it — always with a `rationale` and at least one alternative). A step with no `source` is refused by the executor. A step whose `source` names a layer path that does not exist in the input HTML is refused too.

**The label is not a droppable column.** The executor pre-scans the recipe for `select_partition`, so the target is known before the first step runs: a step that would remove it — `drop_derived` on a rule head that happens to be the label, `drop_constant` on a rare one — keeps it and reports that it did. Only a `user:` step that *names* the label in its `columns` may remove it.

**Order** is semantic, and the executor enforces the phases: (1) typing and structure — `retype`, `drop_identity`, `drop_constant`, `dedupe`, `parse_datetime`, `parse_geometry`; (2) geometry — `orient_cycle`, `drop_derived`, `select_partition`, `drop_leakage`, `keep_columns`; (3) split — `split` (at most one; after this every *fitted* step is fitted on the train part and applied to all parts); (4) values — `impute`, `clip`, `winsorize`, `transform`, `bin`, `datetime_expand`, `lag`, `spatial_*`; (5) representation — `encode`, `scale`, `project`; (6) selection — `select_features`. A `custom` step declares its `phase` and the executor places it there; it runs once per split part on that part's frame alone, so it cannot fit across parts, and the layer marks it *unverified*. The executor rejects a recipe whose steps are out of phase (an `encode` before `split` when a split exists is the classic leakage) and says which step and why.

Every step carries `consequences` with three entries (`rows`, `columns`, `downstream`), each a concrete effect or "none"; `alternatives` are the ones actually weighed (empty when forced, and `rationale` says why); `reversible` says whether the step can be undone from the output alone (a retype or a split can; a drop, an imputation or a projection cannot — the input file is the reversal, as in every chain skill).

## 2. The executor and its outputs (`scripts/shape.py`)

`python3 scripts/shape.py --recipe recipe.json --out-dir shaped/` reads the input dataset named in the recipe, checks the recipe (schema, phases, sources against the model's layers when `--model` is given, no step without a source, no label in the feature set of a `select_partition`, no leakage column surviving `drop_leakage`, no basis member dropped unless a `user:` step says so, no step contradicting an `analysis` stance — a `winsorize` or `clip` on a column a `genuine-outliers` stance names, an `impute` against a `missingness-mechanism` stance's strategy, any step on an `out-of-scope` column — unless a `user:` step overrides it and says so), executes the steps deterministically under `seed`, and writes:

- the dataset file(s) in the chosen format — one file, or one per split part;
- `manifest.json` — `{ input digest, recipe digest, per-step {id, op, rows_before, rows_after, columns_added, columns_removed, fitted_on, parameters_fitted (e.g. medians, encoders' categories, scaler statistics, PCA loadings)}, output schema (column → dtype, role, origin step), output digests, seed, library versions }`;
- `fitted.json` — every step's fitted parameters (and the split's index sets) in one file, which the reproduction script reads rather than carrying inline;
- `reproduce_<slug>.py` — a standalone script (pandas + numpy + scikit-learn, optional geopandas/pyproj for spatial steps) that re-executes the recipe from the input path without this skill installed, one readable block per step, and asserts the output digests recorded in the manifest. It is a second implementation of the same recipe, which is what makes `--check` a test rather than a tautology;
- `lineage.json` — column → the steps that touched it, for the layer's lineage graph.

`--dry-run` writes the recipe, the manifest skeleton and the reproduction script, materializes nothing (large data, or a user who prefers to run it elsewhere). `--check` re-executes the reproduction script and compares digests (the determinism test the summary reports).

**Fitted steps** (`impute` with a statistic, `encode`, `scale`, `project`, `bin` with quantiles, `winsorize` with quantiles) record `fit_on: "train"` when a split exists and are fitted on that part only; without a split they fit on the whole data and the manifest says `fit_on: "all"` so a later reader knows the estimate leaked nothing only because there was nothing to leak into. `encode` with `strategy: "target"` is refused outside a split (it needs out-of-fold fitting, which the executor performs only when `split` precedes it).

## 3. Verification (`scripts/verify_shape.py`)

Runs after execution and before the layer is written; the summary reports its markers.

- **Structural:** the label is absent from the feature columns; the leakage set is absent; every derivation head whose orientation is active is absent unless a `user:` step kept it (then the manifest carries `kept_derived: [...]` and the layer says so); no basis member missing unless a `user:` step dropped it.
- **Semantic, when parents were kept:** for every derivation whose body columns survive, recompute the rule empirically on the output (the formula, on retained rows) and report agreement — a transformation that silently broke a definitional relationship (a log on `qty` but not on `total`) is the defect this check exists for. When the model exposes the rule and a headless browser is present, also run the SWRL/Horn rule on a sample of the shaped rows through `domain-forge/scripts/run_query.py` and record `symbolic: confirmed | refuted | untested` as `/dataset-forge` does.
- **Distributional:** per-column PSI between input and output on the columns that were *not* meant to change (a `dedupe` or `clip` should not move a column it did not name); any drift above the threshold is a `WARN` naming the step suspected. PSI compares *distributions*: it sees a column that moved, and it cannot see a column that was merely reordered — row-level integrity is the semantic check's job, through the alignment described above, and the two checks are complementary rather than redundant.
- **Split hygiene:** no row in two parts; group and time constraints honoured; label rate per part within the stratification tolerance.
- **Determinism:** `--check` re-runs the reproduction script; digests must match.
- **Spatial sanity, when spatial steps ran:** every geometry valid, CRS declared on output, no coordinate outside the CRS bounds.

## 4. The `shape` layer

```html
<!-- @LAYER:start shape v1
     produced-by: /dataset-shaper
     produced-at: <UTC ISO timestamp>
     input-digest: sha256:<digest of the canonical Turtle script>
     reverts-by: open the predecessor
 -->
<script id="layer-shape-data" type="application/json"> { ...below... } </script>
<script id="layer-shape-render" type="text/javascript"> (function(){ ... })(); </script>
<style id="layer-shape-style"> .layer-shape ... </style>
<!-- @LAYER:end shape -->
```

`layer-shape-data`:

```json
{
  "schema": "dataset-shaper/shape@1",
  "recipe": { "...": "recipe.json verbatim" },
  "manifest": { "...": "manifest.json verbatim, minus fitted parameters larger than 20 KB, which are referenced by path" },
  "verification": { "structural": "pass", "semantic": [ { "rule_id": "swrl-total", "empirical": "confirmed 480/480", "symbolic": "untested" } ],
                    "distributional": [ { "column": "qty", "psi": 0.01, "expected": true } ], "split": "pass", "determinism": "pass", "spatial": "n/a",
                    "markers": ["OK: ...", "WARN: ..."] },
  "before_after": { "rows": [600, 600], "columns": [15, 11], "basis_kept": 8, "derived_dropped": 2, "leakage_dropped": 1, "added": ["delivered_days_missing"] },
  "lineage": { "...": "lineage.json verbatim" },
  "forks": [ { "step": "S6", "asked": "group-median vs global median", "answer": "group-median (user)", "or": "default applied (unattended)" } ],
  "readings": { "abstract": "<paragraph: what was decided, what the dataset became, and why>", "per_phase": { "typing": "<...>", "geometry": "<...>", "split": "<...>", "values": "<...>", "representation": "<...>", "selection": "<...>" } }
}
```

Required: `schema`, `recipe`, `manifest`, `verification` (with `structural` and `determinism`), `before_after`, `readings.abstract`. The apply script (`scripts/apply_shape_layer.py`) validates this, injects `assets/shape-render.js` + `assets/shape-layer.css` through the platform writer, adds a `<noscript>` fallback (the recipe table, before/after, the verification markers). Output path default `<input-stem>.shaped.html`; the input HTML is never modified; the shaped dataset files sit in `outputs.dir` next to it.

The render mounts one tab, `data-layer="shape"`, labelled **Shape**: a recipe table (step, op, columns, source chip linking to the geometry/analysis element it cites, rationale, consequences, alternatives folded), a before/after strip, a lineage graph (input columns → steps → output columns; dropped columns end at the step that dropped them, with the reason), the verification panel with its markers, and the forks with what was asked and answered. It reads only `layer-shape-data`, idempotent, empty state when missing, ≤ 60 KB, SVG only, keyboard-operable, `window.__shape = { steps(), lineage(), version }` for tests.

## 5. Naming, memory, hand-off

Output: `<input-stem>.shaped.html` next to the input (the chain's append rule: `orders.domain.analysis.html` → `orders.domain.analysis.shaped.html`); dataset files `<dataset-stem>.<part>.<ext>`, `recipe.json`, `manifest.json`, `lineage.json` and `reproduce_<slug>.py` in `shaped/` (or `--out-dir`); the working files in `.claude/dataset-shaper-runs/<UTC-timestamp>/`. Memory: `.claude/domain-forge-memory.md` § **Shaping stances** — one line per fork resolved (`YYYY-MM-DD | <dataset> | impute delivered_days: group-median by zip (indicator)`), read before compiling so a re-run does not re-ask. Hand-off: the summary names the shaped files and the `manifest.json` as the input for training, `/blueprint <out> --mode pipeline` for the pipeline architecture (the recipe phases are its ingestion/feature stages), and `/data-lens <out> --dataset shaped/<train file>` to re-analyse the shaped data if the user wants the drift module to compare before and after (`<out>` is the full output path).
