# dataset-forge report contract — the `geometry` layer

The output file is a domain-forge model (canonical Turtle, JSON-LD mirror, Markdown abstract, optional `model-swrl` / `model-horn`) plus **one additive layer** named `geometry`, appended before `</body>` per domain-forge's `references/future-skills.md` layer contract:

```html
<!-- @LAYER:start geometry v1
     produced-by: /dataset-forge
     produced-at: <UTC ISO timestamp>
     input-digest: sha256:<digest of the canonical Turtle script>
     reverts-by: open the predecessor (or the base model without this layer)
 -->
<script id="layer-geometry-data" type="application/json"> { ...schema below... } </script>
<script id="layer-geometry-render" type="text/javascript"> (function(){ ... })(); </script>
<style id="layer-geometry-style"> .layer-geometry ... </style>
<!-- @LAYER:end geometry -->
```

The block is written by `scripts/apply_geometry_layer.py`, which validates the data document against §1, then calls domain-forge's platform writer (`domain-forge/scripts/apply_layer.py`) with this skill's shipped `assets/geometry-render.js` and `assets/geometry-layer.css`, and adds a `<noscript>` fallback (the readings, the derivations table, the stats table). The render script mounts one tab, `data-layer="geometry"`, labelled **Geometry**, as a `section.tab-pane` next to the host's tabs (the same convention `/inferred-questions` uses); it reads only `layer-geometry-data`, is idempotent, and renders an explanatory empty state if the data script is missing. It never touches the base runtime or earlier layers. The analyst authors the JSON; nobody authors the JavaScript per run.

## 1. `layer-geometry-data` schema

```json
{
  "schema": "dataset-forge/geometry@1",
  "source": { "path": "orders.csv", "rows": 600, "columns": 15, "geometry_json": "<run-dir>/geometry.json" },
  "markers": ["OK: ...", "WARN: ...", "FORK: ..."],
  "typing": [
    { "column": "zip", "script_type": "ordinal", "final_type": "nominal",
      "reason": "postal code parsed as integer; categorical by meaning",
      "role": "dimension | derived | identity | key | degenerate | constant | text",
      "consequences": { "...": "see §3 — every retyping carries one; a one-sentence block whose downstream entries say none when nothing changes" } }
  ],
  "space": { "ambient_dim": 10, "exact_rank": 10, "near_rank": 10, "dims_95": 6, "dims_99": 8,
             "participation_ratio": 5.0, "intrinsic_dim_twonn": 7.1, "condition_number": 41.2,
             "numeric_columns": ["unit_price", "qty", "..."],
             "singular_values": [ "...verbatim, for the scree" ], "explained_variance_ratio": [ "..." ],
             "reading": "<one paragraph: what these numbers mean for this dataset>" },
  "basis": {
    "members": ["unit_price", "qty", "discount_pct", "zip", "order_date", "delivered_days", "weight_kg", "note"],
    "size": 8, "intrinsic_dim": 7.1,
    "reading": "<paragraph: basis size vs intrinsic dimension, what may still be hiding>"
  },
  "derivations": [
    {
      "column": "total", "rule_id": "swrl-total", "layer": "swrl | horn",
      "formula": "total = unit_price × qty", "body": ["unit_price", "qty"],
      "provenance": {
        "semantic":  { "status": "confirmed", "note": "price times quantity, by meaning" },
        "symbolic":  { "status": "confirmed", "verified_rows": 200, "of_rows": 200 },
        "empirical": { "status": "confirmed", "evidence": "degree-2 R²=1.000000 on 600 rows" }
      },
      "cycle": ["unit_price", "qty", "total"], "cycle_id": "price-qty-total",
      "consequences": { "...": "see §3" }
    }
  ],
  "cycles": [
    { "id": "price-qty-total", "members": ["unit_price", "qty", "total"],
      "reading": "<why the derivation is symmetric and which orientation was chosen>",
      "orientations": [
        { "id": "total-derived", "default": true, "basis": ["unit_price", "qty"],
          "rules": ["swrl-total"], "consequences": { "...": "see §3" } },
        { "id": "unit-price-derived", "default": false, "basis": ["total", "qty"],
          "rules": [ { "rule_id": "swrl-unit-price", "column": "unit_price", "formula": "unit_price = total / qty",
                       "body": ["total", "qty"], "provenance": { "...": "three channels" } } ],
          "consequences": { "...": "see §3" } }
      ] }
  ],
  "functional_dependencies": [ { "lhs": ["zip"], "rhs": "city", "exact": true, "determination_ratio": 1.0, "groups": 5 } ],
  "disagreements": [
    { "column": "weight_kg", "kind": "empirical-without-semantic",
      "evidence": "pearson 0.966 with qty", "reading": "<why: weight is qty times a per-unit weight the dataset does not carry; not derivable, but nearly collinear — a hidden dimension (unit weight) is the honest explanation>" }
  ],
  "orthogonality": {
    "measures": "<which measure per type pair, one line>",
    "thresholds": { "nmi": 0.5, "pearson": 0.9, "eta2": 0.8, "cramers_v": 0.8 },
    "pairs": [ { "a": "qty", "b": "weight_kg", "nmi": 0.63, "pearson": 0.97, "independence": "definitional, not statistical" } ],
    "reading": "<paragraph>"
  },
  "partitions": {
    "chosen": "late",
    "provenance": "user-chosen | single-candidate | abstained | none",
    "candidates": [
      { "label": "late", "task": "binary classification", "rule_id": "swrl-late",
        "features": ["unit_price", "qty", "discount_pct", "zip", "order_date", "weight_kg", "note"],
        "dropped_for_leakage": ["delivered_days"],
        "input_dim": 7,
        "consequences": { "...": "see §3" } }
    ]
  },
  "stats": { "<column>": { "...": "verbatim from geometry.json stats" } },
  "handoff": { "nn_data_artifact": "nn-data-orders.html | null", "note": "<one sentence>" }
}
```

Every `reading` and every `consequences` field is **prose** obeying §4. Numbers come verbatim from `geometry.json`; the layer never recomputes.

Required keys (the apply script refuses without them): `schema`, `source` (with `path`), `typing`, `space` (with `ambient_dim`, `exact_rank`, `reading`), `basis` (with `size == len(members)`), `derivations`, `partitions`; each derivation needs `column`, `rule_id`, `layer`, `formula`, a non-empty `body`, and `provenance` with the three channels each in `{confirmed, refuted, untested}`; no column may head two derivations; a derivation head may not sit in `basis.members`; `basis.members` must exclude identity/key/degenerate/constant columns; a candidate's label may not appear in its own `features`. Optional, tolerated when absent (the explorer degrades view by view): `cycles`, `functional_dependencies`, `disagreements`, `orthogonality.pairs`, `stats`, `handoff`, `explore`. `cycles[].orientations` is where the per-orientation consequence blocks live — one per orientation the analyst weighed, `default: true` on the one chosen; `orthogonality.pairs` should cover every non-identity pair (not only the current basis) so the heatmap stays complete after a re-orientation.

## 2. The provenance triple

Each derivation carries three independent verdicts. They are not a hierarchy; they are three instruments pointed at the same claim.

| channel | who | confirmed means | refuted means | untested means |
|---|---|---|---|---|
| `semantic` | the model | derivable by meaning, rule stated | not derivable by meaning | — (the model always has a view) |
| `symbolic` | the domain-forge engines (SWRL reasoner or Prolog runner via `domain-forge/scripts/run_query.py`) on the A-box sample | the rule fires and its output equals the observed value on every sampled row (`verified_rows == of_rows`, taken from the runner's output) | fires but disagrees on ≥1 row (report the rows) | no engine could run the rule (runner error, unsupported operation) |
| `empirical` | `geometry.py` on the full data | derivability established (R² ≥ threshold, exact FD) | tested and not derivable | not testable (text, no numeric form) |

A derivation with `semantic: confirmed` and both others `untested` is still a derivation — but the report says so in those words. A `symbolic: refuted` with `empirical: confirmed` almost always means the formula is right and the rule encoding is wrong (units, rounding, a null); say which you think it is.

## 3. The consequence block

Attached to every decision (a retyping — on its `typing` entry — a basis choice inside a cycle, a derivation kept or rejected, a partition candidate). Fields:

```json
{
  "decision": "unit_price and qty enter the basis; total is derived",
  "alternatives": ["total and qty in the basis; unit_price derived", "all three kept as features"],
  "downstream": {
    "preprocessing": "total needs no scaling decision of its own; it inherits from its parents",
    "model_family": "linear models: keeping all three adds an exactly collinear column — coefficients unidentifiable; trees: harmless but split budget wasted",
    "leakage": "if total is ever the label, unit_price and qty must leave the features or the model learns the multiplication",
    "dimensionality": "the downstream model sees 2 inputs for this cycle, not 3",
    "interpretability": "unit_price is a price the business sets; total is an outcome — the chosen direction keeps the controllable quantities as inputs"
  }
}
```

Rules: every `downstream` entry names a concrete effect on *this* dataset or says "none". Alternatives are the ones the analyst actually weighed, not an exhaustive list. If the decision was forced (only one candidate), `alternatives` is empty and `decision` says why it was forced.

## 4. Narrative register

The Abstract (`model-markdown`) and every `reading` field obey five rules (the same register `/document-project` asks of a chapter):

- **Motive before mechanism.** Introduce a measure by the question it answers, never cold. Not "TwoNN = 7.1" but "the rank test says nothing is linearly redundant, so the next question is whether the data still lives on fewer dimensions than it has columns — the two-nearest-neighbour estimate answers that: about seven."
- **Connected paragraphs.** Each section opens by recalling what the previous one established and closes by handing off to the next question.
- **No argument in bullets.** Lists are for enumerable material (the basis members, the stats table); reasoning is prose.
- **Length follows substance.** A consequence with nothing downstream is one sentence.
- **Terms defined in flow.** Define *basis*, *derivation*, *intrinsic dimension*, *functional dependency* the first time each appears, inside the sentence.

The Abstract alone must let a reader understand the space the dataset occupies, its basis, the derivations, the chosen partition and why — the standard domain-forge sets for its Markdown block, applied to a dataset.

## 5. nn-data hand-off (when a partition is chosen AND an nn-* skill family is installed)

This section applies only when a skill family with an nn artifact contract is present in the session (look for a `references/artifact-contract.md` under a skill whose name starts with `nn-`). When it is absent, `handoff.nn_data_artifact` is `null`, the note says what the partition would materialize, and nothing else is emitted — never invent the contract. When present, emit `nn-data-<slug>.html` per that contract: `stage: "data"`, `source: "user-validated"`, `upstream` all null, `generator.process` = the partition in prose (which columns, which encoding, which rows), `generator.formulas` = the derivation rules that justify the label, `dataset.X`/`dataset.Y` inline if ≤ 500 rows else `inline: false` with the reproduction code in the human view. Record the dataset-forge file path in `generator.process` so the downstream skill can trace the partition back to its geometry.

## 6. The interactive explorer (inside the Geometry tab)

The Geometry tab is not a printed report with a table at the bottom; it is the surface the analyst *moves through*. **The render script is `assets/geometry-render.js`, a fixed asset of this skill** — written once, checked by `scripts/smoke_geometry.py`, injected by `apply_geometry_layer.py`; a run never regenerates it, and a view that needs data the schema does not carry is a change to the schema and the asset, not a per-run patch. It draws four linked views from `layer-geometry-data` alone — plain DOM + hand-written inline SVG, no libraries, no network — and every view answers a question the report raised in prose. The data it needs ships in the layer: `explore` (a columnar sample of ≤ 2000 rows, text columns omitted, plus precomputed PCA scores and loadings — the script's `explore` object, verbatim) and the `derivations`, `basis`, `orthogonality`, `partitions` objects above. The JS never recomputes rank, PCA or dependencies; it filters, projects, joins and redraws.

**View A — Space.** The scree of singular values (bar) beside a 2-D scatter of the sample on any pair of *named* basis members (two selects), with a third select that colours points by a nominal or a label candidate. A toggle switches the axes to the two leading PCA components: the rotated view, labelled as such, with a loadings panel that says which named columns each component is made of. Hovering a point shows the row: its basis values, and its derived values each tagged with the rule that produced them and the provenance triple's status. Brushing a rectangle filters every other view to the selected rows.

**View B — Derivation graph.** Columns as nodes, derivations as directed edges (body → head), functional dependencies as dashed edges, cycles drawn as such. Basis members are filled, derived columns hollow, identities greyed. Clicking a node opens its card: type and retyping reason, provenance triple, the consequence block, the `WARN`/disagreement entries that mention it. Inside a cycle, the card offers **"make this the basis member"**: choosing it re-orients the cycle, recomputes the basis in JS (the set of columns that are the head of no active rule), updates View D's candidates, and shows the consequence block the analyst pre-wrote for that orientation — so "what does a different basis imply" is one click, not a re-run.

**View C — Orthogonality.** A heatmap of the residual-dependence measures among the current basis members (the measure chosen by type pair, NMI as the common scale), colour-scaled with the thresholds from `geometry.json`. Clicking a cell opens that pair as the axes of View A. The `independence` reading of the pair ("definitional, not statistical") appears beside the value.

**View D — Partition.** The label candidates as selectable cards. Selecting one highlights on the graph the features that remain, strikes the leakage set, shows the input dimension `nn-architect` would receive and the candidate's consequence block, and colours View A by the label. A "materialize" note explains that the chosen partition becomes a hand-off artifact when the skill is re-run with `--partition <label>` *and* an nn-* skill family is installed (§5); the layer itself cannot write files.

**Cross-view state** is one object (`selectedRows`, `axes`, `colourBy`, `activeOrientation` — a map `cycleId → orientationId`, since a dataset may have several independent cycles — `activeCandidate`) that every view reads; a change anywhere redraws the others. The state is not persisted — reload restores the report's own choices, which are the analyst's pre-written decisions.

**Constraints.** Render script ≤ 80 KB; SVG only (no canvas), so the figures can be copied out; keyboard-operable selects and buttons; a `<noscript>` fallback that shows the prose and the stats table; if `explore` is missing or has fewer than 10 rows, Views A and C render their empty state and B and D still work (they need only the derivations). The render never mutates `layer-geometry-data` or earlier layers. For tests it exposes `window.__geometry = { state, reorient(column), basis(), candidates(), version }` and nothing else.

**View D, precisely.** Candidates come from two sources joined by label: the analyst's `partitions.candidates` (cards with a consequence block, marked *stated by the report*) and the structural candidates the current orientation implies (every active rule head whose body ⊆ current basis, plus FD-determined columns), marked *structural only* with no invented consequences. That join is what lets a re-orientation update the candidates without a re-run. Re-orienting a derived column that has no pre-written orientation deactivates its rule and grows the basis by one, labelled *ad hoc, no pre-written consequences* — the honest fallback, not a refusal.
