---
name: dataset-shaper
description: >-
  Materialize decisions an analysis already took: from a /dataset-forge model (its `geometry`
  layer — typing, basis, cycle orientation, partition and leakage set) and, when present, the
  /data-lens `analysis` layer (findings with transformation candidates), compile a declarative,
  provenance-traced RECIPE of transformations — feature-space geometry (keep the basis, drop
  derived and leakage columns, orient cycles, project), value transforms (impute, clip, transform,
  bin, encode, scale), split hygiene, temporal and geographic/spatial features (reproject,
  distances, spatial joins, grid aggregation) — execute it deterministically, verify it, and emit
  the shaped dataset, a manifest, a standalone reproduction script and an additive `shape` layer
  on the model HTML. Trigger on requests for the cleaned / transformed / training-ready /
  basis-only dataset, applying the analysis's recommendations, building spatial features, or
  /dataset-shaper. Not for discovering what to transform (/data-lens) or the basis (/dataset-forge).
---

# /dataset-shaper — decisions become data

You are the engineer who turns an analysis into a dataset, and the rule you never bend is **no step without a traced decision**. Every transformation in the recipe cites the geometry element, the analysis finding, the user's word, or the preset default that justifies it; the executor refuses a step that cites nothing, and the layer shows the citation next to the step. You do not analyse — the geometry and the analysis are done — and you do not transform by hand: you compile a recipe, a script executes it, a second script verifies it, and a third writes the layer.

## Where this skill sits

A chain skill on the dataset lane: input `model.html` (read-only; a `/dataset-forge` file, ideally after `/data-lens`) → output `<stem>.shaped.html` plus the shaped dataset files in `shaped/`. Upstream: `/dataset-forge` (`geometry`) and `/data-lens` (`analysis`). Downstream: training (the manifest and the reproduction script are the hand-off), `/blueprint --mode pipeline` (the recipe's phases are the pipeline's stages), `/data-lens --dataset shaped/…` to compare before and after. `/noctua` schedules you after the lens.

## Inputs

1. `<model>.html` with a `geometry` layer (required unless `--recipe` supplies every source as `user:`); an `analysis` layer when `/data-lens` ran. The dataset path comes from the geometry layer's `source.path`; `--dataset <path>` overrides.
2. Flags: `--goal train-ready|clean|basis-only|spatial-features|custom` (preset, default `train-ready` when a partition is chosen, `clean` otherwise), `--target <label>` (select a partition candidate by name; overrides the layer's `chosen`), `--recipe <recipe.json>` (apply a given or edited recipe — the compile step is skipped, the checks are not; also how a fork answered outside the run comes back), `--unattended` (no user present: never ask; defaults applied and marked, spatial steps without a CRS skipped with `WARN:`), `--out-dir <dir>` (default `shaped/` next to the model), `--format csv|parquet` (default parquet, csv when pandas lacks pyarrow), `--crs <EPSG>` (declare the coordinate reference system when the data does not), `--dry-run` (recipe + manifest skeleton + reproduction script, no data written), `--out <path>` (default `<input-stem>.shaped.html`, the chain's append rule), `--seed` (default 7). Working files go to `.claude/dataset-shaper-runs/<UTC-timestamp>/` (`<run-dir>` below); the recipe and its companions are written to the output directory.

## Dependencies — read, do not duplicate

`domain-forge` (sibling; `--domain-forge-dir` overrides): `scripts/validate_model.py`, `scripts/apply_layer.py` (called by `scripts/apply_shape_layer.py`), `scripts/strip_layer.py --list`, `scripts/run_query.py` (the optional symbolic check in verification), `references/future-skills.md`. `dataset-forge/references/report-contract.md` §1–3 (what the geometry layer carries) and `data-lens/references/analysis-contract.md` §1 and §4 (findings and transformation candidates). This skill's own: `references/shape-contract.md` (recipe schema, sources, phases, executor outputs, verification, the `shape` layer, memory, hand-off) and `references/step-catalog.md` (every `op` with its params, phase, fitted-ness and usual source; the presets). Scripts: `scripts/shape.py` (compile-check + execute; `--check` for determinism), `scripts/verify_shape.py`, `scripts/apply_shape_layer.py`, `scripts/smoke_shape.py`; assets `shape-render.js` + `shape-layer.css` (shipped, never rewritten). Open these when needed; do not restate them.

## Procedure

`OK:` / `WARN:` / `ERROR:` before prose at every stage; `FORK:` when you stop to ask.

**M. Read memory.** `.claude/domain-forge-memory.md`: **Dataset stances** (the partition, the orientation, retypings — facts), **Analysis stances** (outliers declared genuine, mechanisms asserted — they constrain steps: a `winsorize` on a column declared genuine is refused), **Shaping stances** (create the section if missing: forks already resolved in an earlier run). A recorded decision is applied and cited as `user:stance/<memory line>` (or `user:stance/ST<n>` for a structured analysis stance), never re-asked.

**0. Read the layers.** `strip_layer.py --list`; read `layer-geometry-data` per `report-contract.md` §1 (typing, basis, derivations, cycles, the chosen partition's candidate entry, the space) and, if present, `layer-analysis-data` per `analysis-contract.md` §1 (the time and spatial context, the transformation candidates in hand-off order, the stances). Load the dataset; confirm its digest against the geometry's `source` (rows and columns) — a mismatch is `WARN: dataset differs from the one analysed` and, unless the user confirms, `ERROR:`.

**1. Compile the recipe.** Build `recipe.json` per `shape-contract.md` §1, in phase order:

- *Typing and structure* from `geometry.typing`: one `retype` per retyping, `drop_identity` for identity/key roles, `drop_constant` for degenerate/constant, then the `analysis` candidates of this phase (`dedupe`, `parse_datetime`, `parse_geometry` — the last only with a CRS from `context.spatial`, `--crs`, or a `FORK:`).
- *Geometry* from the layer: `orient_cycle` for every cycle (the default orientation unless memory or the user chose another), `drop_derived` for the active rule heads, `select_partition` + `drop_leakage` when a partition is chosen (by the layer, by memory, or by `--target`; with two or more candidates and none chosen, `FORK:` naming them and the difference — unattended, abstain: no partition, `--goal clean` semantics, and say so).
- *Split* — the preset's default (`stratified` on the label; `time` when `context.time` exists — a time-ordered dataset is never split at random; `group` when the user names a grouping key), source `shaper:default` with the alternatives.
- *Values, representation, selection* from the `analysis` candidates in `handoff.shaper_candidates` order, each with `source: analysis:F<n>/T<m>` and the candidate's alternatives; then the preset's defaults for what the analysis did not cover (a `scale` for a linear-model-ready set, an `encode` for the nominals), each `shaper:default` with a rationale and an alternative. A `transform` on a member of a kept derivation is extended to the whole cycle or refused (contract: a log on `qty` alone breaks `total`).
- *Spatial* steps only when `context.spatial` is present and non-empty: reproject to a metric CRS before any distance, then the candidates the analysis proposed; a spatial join or an external layer only when the user supplies the path.

Every step: `id, op, columns, params, source, rationale, alternatives, consequences {rows, columns, downstream}, reversible`. Run `python3 scripts/shape.py --recipe recipe.json --model <model.html> --check-only` — it validates schema, phases, sources against the layers, and the structural rules (label out of features, leakage dropped, no basis member dropped without a `user:` step, no fitted step before `split`). Fix the recipe until `OK:`.

**2. Present and gate.** Show the recipe as a table (id, op, columns, source, one-line rationale, consequence on columns/rows) grouped by phase. Every step with non-empty `alternatives` and a `shaper:default` or `analysis:` source that memory does not already settle is a decision to surface: `FORK:` per phase (not per step — batch the forks of one phase in one question, each named with its alternatives and the one difference that separates them). Wait. Under `--unattended`: apply the defaults, mark each `forks[].or: "default applied (unattended)"`, and continue. With `--recipe`, skip the compile but still show and still gate the steps whose `source` is `shaper:default`.

**3. Execute.** `python3 scripts/shape.py --recipe recipe.json --out-dir <dir> [--format …] [--dry-run]`. It writes the dataset file(s), `manifest.json`, `lineage.json`, `fitted.json`, a copy of `recipe.json`, and `reproduce_<slug>.py` — a standalone pandas program, one block per step, that regenerates the outputs without this skill (contract §2). Its `OK:`/`WARN:` lines are the first entries of the layer's `verification.markers`. Fitted steps are fitted on the train part when a split exists — the manifest's `fit_on` says so per step, and you report it. The label is never dropped on the way past: a step that would remove it keeps it and says so, unless a `user:` step names the label explicitly.

**4. Verify.** `python3 scripts/verify_shape.py --recipe recipe.json --out-dir <dir> --model <model.html>`: structural, semantic (recompute every retained derivation on the output; symbolic through `run_query.py` when a browser is present, else `untested`), distributional (PSI on columns no step named), split hygiene, spatial sanity; then `python3 scripts/shape.py --check --out-dir <dir>` re-runs the reproduction script and compares digests. A structural or determinism failure is `ERROR:` — fix the recipe, re-run 3; a semantic `refuted` is `ERROR:` unless the user kept the parent columns on purpose and accepts the broken relationship (then it is a stance and a `WARN:`). A distributional `WARN:` names the suspected step and is carried to the summary.

**5. Write the layer.** Author `<run-dir>/shape-layer.json` per contract §4 — and author only the **judgement**: `readings.abstract`, one paragraph per phase that ran, and the `forks` with what was asked and what answered them. Set `"from_run": "<out-dir>"` and the apply script splices in the executor's half verbatim (the recipe, the manifest, the lineage and `verification.json`), eliding any fitted blob too large to read and referencing it on disk. Then run `python3 scripts/apply_shape_layer.py <model.html> --data <run-dir>/shape-layer.json --out <out>`. It refuses a layer whose `verification.structural`, `split`, `determinism` or `spatial` is `fail`, or whose semantic channel is `refuted`: a failure is fixed by re-running the recipe, never published as a result. You write no JavaScript, and you do not append the block by hand.

**6. Verify the layered file.** `validate_model.py <out>` (exit 0, 13–16) and `python3 scripts/smoke_shape.py <out> --strict` (tab mounts, recipe table and lineage render, no JS error; non-strict without a browser, and the summary says so).

**7. Update memory.** § **Shaping stances**: one line per fork resolved (date, dataset, step, choice), plus the model path, output path and output directory.

**8. Summary.** Output HTML, output directory and files with rows × columns per part, the recipe in one line per phase, before/after (basis kept, derived dropped, leakage dropped, added), forks asked and answered (or defaults applied), verification results including `fit_on` and determinism, memory updated, and the hand-off: the manifest and reproduction script for training, `/blueprint <out> --mode pipeline`, `/data-lens <out> --dataset <train file>` for a before/after drift reading. Stop.

## Failure modes — do not

- Do not apply a step without a `source`, and do not invent a source: a step you added is `shaper:default` with a rationale and an alternative, shown to the user. An untraced transformation is the failure this skill exists to prevent.
- Do not fit an imputer, encoder, scaler, binning or projection on data that includes the test part when a split exists, and do not target-encode outside out-of-fold fitting. The executor enforces the phase order; do not work around it with a `custom` step.
- Do not drop a basis member or keep a leakage column, unless a `user:` step says so — and then the layer says it too. The label is the exception with no exception: it is never imputed, and the executor refuses an `impute` step that names it whatever the source, a `user:` step included.
- Do not transform one member of a kept derivation cycle alone.
- Do not reproject or compute distances without a declared CRS; ask, or unattended skip the spatial steps with a `WARN:`. When `pyproj` is absent the executor falls back to a local equirectangular projection about the data's own centroid, in metres — accurate to a fraction of a percent over a city, degrading with extent — and records `exact: false` in the manifest; report that in the summary rather than presenting a local approximation as a CRS transform.
- Do not materialize alternative partitions or alternative recipes; one recipe, one output set — alternatives are described in the steps, and a different choice is a re-run.
- Do not hand-transform in pandas outside the recipe, do not edit the shaped files after the executor wrote them (the digests would no longer match the manifest), and do not write or edit the renderer or the layer block.
- Do not re-ask a fork memory already records.

## Done when

The output HTML validates (exit 0, 13–16 included) and passes the smoke test (or the non-strict run is reported as unverified); every recipe step carries a source that resolves to a layer element, a stance, a user turn or a preset default with its rationale; the structural checks pass; every retained derivation is empirically confirmed on the output (or the exception is a recorded stance); the reproduction script regenerates the outputs byte-for-byte; the manifest names what was fitted on what; memory holds the forks; and the summary gives the training hand-off and the next passes.
