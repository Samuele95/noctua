# dataset-shaper step catalog

The vocabulary of `recipe.steps[].op`. Each entry: what the step does, its `params`, its phase (see `shape-contract.md` §1), whether it is *fitted* (fit on train when a split exists), and the decision that usually sources it. A `/data-lens` transformation candidate must use one of these names; a step outside this catalog is a `custom` op with an inline `code` field, executed in a sandboxed cell and flagged in the layer as unverified.

## Phase 1 — typing and structure

| op | params | fitted | usual source | notes |
|---|---|---|---|---|
| `retype` | `to: numeric \| nominal \| ordinal \| boolean \| datetime \| text`, `order: [...]` for ordinal | no | `geometry:typing/<col>` | the final typing the geometry layer recorded; never re-derived here |
| `drop_identity` | — | no | `geometry:typing/<col>` (role identity / key) | keys leave before any dependency-sensitive step |
| `drop_constant` | `tolerance: 0.0` (share of the dominant value above which a column is quasi-constant) | no | `geometry:typing/<col>` or `analysis:F<n>` | |
| `dedupe` | `on: "all" \| [columns]`, `keep: first \| last`, `near: {cols, tolerance}` optional | no | `analysis:F<n>` | reports removed rows in the manifest |
| `parse_datetime` | `format`, `tz`, `errors: coerce \| raise` | no | `analysis:context.time` | coerced failures become missing and are counted |
| `parse_geometry` | `kind: latlon \| wkt \| geohash \| h3`, `lat`, `lon`, `crs` | no | `analysis:context.spatial` | requires a declared `crs`; without one the step is refused (`FORK` or `WARN`+skip unattended) |

## Phase 2 — geometry

| op | params | fitted | usual source | notes |
|---|---|---|---|---|
| `orient_cycle` | `cycle_id`, `orientation_id` | no | `geometry:cycles/<id>` | selects which member of a derivation cycle is derived; default = the layer's `default: true` orientation |
| `drop_derived` | `orientation: {cycle → orientation}` optional | no | `geometry:derivations` | drops every active rule head; `keep: [...]` lists heads a `user:` step retains (documented as redundant-by-choice) |
| `select_partition` | `label`, `task` | no | `geometry:partitions/<label>` | names the label column; refused if the label is in the features later |
| `drop_leakage` | — | no | `geometry:partitions/<label>.dropped_for_leakage` | drops the leakage set of the selected partition |
| `keep_columns` | `columns: [...]` | no | `user:` | explicit projection to a named column set; must include the basis unless a `user:` rationale says otherwise |

## Phase 3 — split

| op | params | fitted | usual source | notes |
|---|---|---|---|---|
| `split` | `kind: random \| stratified \| group \| time`, `by`, `test`, `valid`, `time_column`, `cutoff` | no | `shaper:default` (stratified when a label exists, time when a datetime is the natural order) or `analysis:F<n>` (a time-series finding forces `time`) | at most one; everything fitted afterwards is fitted on train |

## Phase 4 — values

| op | params | fitted | usual source | notes |
|---|---|---|---|---|
| `impute` | `strategy: median \| mean \| mode \| constant \| group-median \| group-mode \| knn \| iterative`, `by`, `value`, `indicator: bool` | yes | `analysis:F<n>/T<m>` | `indicator` adds `<col>_missing`; the label is never imputed (refused) |
| `clip` | `lower`, `upper` (absolute) | no | `analysis:F<n>` (unit / range anomaly) | |
| `winsorize` | `lower_q`, `upper_q` | yes | `analysis:F<n>` (outliers judged errors) | refused on a column a `stance` declares genuine |
| `transform` | `kind: log1p \| log \| sqrt \| box-cox \| yeo-johnson \| reciprocal` | yes (box-cox / yeo-johnson λ) | `analysis:F<n>` (skew, heteroscedasticity) | applied to every member of a kept derivation together or refused (a log on `qty` alone breaks `total = price × qty`) |
| `bin` | `kind: quantile \| width \| custom`, `k`, `edges` | yes (quantile edges) | `analysis:F<n>` or `user:` | keeps the numeric column unless `replace: true` |
| `datetime_expand` | `parts: [year, month, dow, hour, is_weekend, ...]`, `cyclic: bool` | no | `analysis:F<n>` (time_series) | cyclic encodes month/hour as sin/cos pairs |
| `lag` | `columns`, `lags: [1, 7]`, `group_by`, `time_column` | no | `analysis:F<n>` (autocorrelation) | only after a `time` split or without split; refused after a random split (future leakage) |

### Spatial (phase 4, require `parse_geometry` first)

| op | params | fitted | usual source | notes |
|---|---|---|---|---|
| `spatial_reproject` | `to_crs` | no | `user:` or `shaper:default` (a metric CRS chosen from the data's UTM zone for distance steps) | |
| `spatial_distance` | `to: {point \| layer path}`, `name` | no | `analysis:F<n>` (spatial autocorrelation) | metres, computed in a metric CRS |
| `spatial_join` | `layer: <path>`, `how`, `predicate: within \| intersects \| nearest`, `columns` | no | `user:` | external layer digest recorded in the manifest |
| `spatial_grid` | `kind: h3 \| square`, `resolution \| size_m`, `aggregate: {col: fn}` | no | `analysis:F<n>` or `user:` | adds the cell id; with `aggregate`, adds per-cell aggregates joined back |
| `spatial_features` | `features: [area, perimeter, centroid_x, centroid_y, bearing_to, n_neighbours_within]`, `radius_m` | no | `analysis:F<n>` | |

## Phase 5 — representation

| op | params | fitted | usual source | notes |
|---|---|---|---|---|
| `encode` | `strategy: one-hot \| ordinal \| target \| frequency \| hashing`, `min_frequency`, `handle_unknown`, `order` | yes | `analysis:F<n>` (cardinality) or `shaper:default` | `target` only after `split`, fitted out-of-fold; one-hot on > 50 levels warns and suggests `frequency`/`target` |
| `scale` | `kind: standard \| robust \| minmax \| none`, `columns: "numeric" \| [...]` | yes | `shaper:default` (robust when outliers were judged genuine) | recorded statistics go to the manifest |
| `project` | `kind: pca`, `k \| variance: 0.95`, `columns`, `keep_named: bool` | yes | `geometry:space` (dims_95) or `user:` | loadings in the manifest; `keep_named: true` keeps the original basis columns beside the components — the honest default, because a rotated basis has no names |

## Phase 6 — selection

| op | params | fitted | usual source | notes |
|---|---|---|---|---|
| `select_features` | `kind: importance \| variance \| correlation`, `threshold`, `from: analysis:importance` (reads `modules.importance.evidence.permutation_importance`) | yes | `analysis:F<n>` (importance) | drops by an analysis result, never by an ad-hoc computation here; a column in the basis is never dropped by this step |

## Custom

| op | params | fitted | usual source | notes |
|---|---|---|---|---|
| `custom` | `code` (a pandas function `def step(df, ctx) -> df`), `description`, `phase` (1–6, required) | no | `user:` only | placed by the executor in its declared phase; runs per split part on that part alone (no cross-part fitting possible); the layer marks it *unverified*; the reproduction script inlines it |

## Presets (`--goal`)

`train-ready` = phases 1–6 with defaults where the layers are silent; `clean` = phases 1 and 4 only, no split, no encoding; `basis-only` = phases 1–2 (the basis and the label, nothing fitted); `spatial-features` = phases 1, 2 and the spatial steps; `custom` = only what the layers and the user name. A preset adds steps with `source: shaper:default`, each with a rationale and an alternative, and every one is shown to the user before execution.
