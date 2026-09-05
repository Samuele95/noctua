# The HTML layer contract — for `/inferred-questions`

This file is the per-skill restatement of the chain-wide contract defined in
`domain-forge/references/future-skills.md` ("The HTML layer contract") — that
file is canonical. Read it for the full chain rationale; read this one for the
precise contract the `open-questions` layer must satisfy. The block format,
the digest and the strip logic are implemented once, by the layer platform
(`domain-forge/scripts/apply_layer.py` / `strip_layer.py`); this skill's
`scripts/apply_layer.py` and `scripts/strip_layer.py` import that module and
own only the questions-specific data shaping, render code and styles.

## The two hard guarantees

1. **Strict byte superset.** The output HTML contains every byte of the input
   verbatim, in the same order, plus the new layer block inserted at a
   defined position (just before `</body>`). A reader can recover the input
   by stripping the layer block.

2. **Self-contained.** No layer introduces external HTTP refs. All required
   render code, helpers, and styles are inlined. The composed HTML opens
   cleanly with `file://`.

## Block shape

```html
<!-- @LAYER:start open-questions v1
     produced-by: /inferred-questions
     produced-at: 2026-05-30T14:00:00Z
     input-digest: sha256:<hex>
     reverts-by: open the file at input-digest (the predecessor)
 -->
<script id="layer-open-questions-data" type="application/json">
{
  "version": 1,
  "produced_at": "2026-05-30T14:00:00Z",
  "input_digest": "sha256:<hex>",
  "categories": [ ... ],
  "questions": [ { ... }, { ... } ]
}
</script>
<script id="layer-open-questions-render" type="text/javascript">
/* Bundled render code. Runs once on DOMContentLoaded. Idempotent. */
(function(){
  if (document.querySelector('[data-layer="open-questions"]')) return; /* already rendered */
  /* ...render code... */
})();
</script>
<style id="layer-open-questions-style">/* .layer-open-questions scoped CSS */</style>
<!-- @LAYER:end open-questions -->
```

## `questions.json` schema (data script body)

```json
{
  "version": 1,
  "produced_at": "ISO-8601 UTC timestamp",
  "input_digest": "sha256:<hex>  // SHA-256 of the input's #domain-model textContent",
  "categories": [
    "boundary", "coverage-gap", "rationale-gap",
    "restriction-edge", "multi-typing", "functional-race",
    "missing-individuals", "naming-stability", "paradigm-mismatch"
  ],
  "questions": [
    {
      "id": "q-<NNN>",
      "source": "<IRI | rationale-id | dmn-decision-id>",
      "source_kind": "iri | rationale | dmn-decision | swrl-rule | horn-clause",
      "category": "one of the strings in `categories`",
      "severity": "high | medium | low",
      "question": "One-sentence question phrased to the modeller.",
      "suggested_next": "One-sentence concrete next step.",
      "engine_check": null | {
        "kind": "dmn-interval-coverage | class-membership | functional-property-collision",
        "decision": "<dmn id>"     /* kind=dmn-interval-coverage */,
        "missing_interval": "[a..b)",
        "class":    "<IRI>"        /* kind=class-membership */,
        "property": "<IRI>"        /* kind=functional-property-collision */
      },
      "status": "open"
    }
  ]
}
```

`id` numbering is sequential per file (`q-001`, `q-002`, …), assigned by the
extractor in the final emit order.

## Insertion position

The layer is inserted **immediately before** the closing `</body>` tag.

If the input has multiple `</body>` occurrences (it should not), use the
**last** one. If the input has none (it should — the validator catches
that), refuse the operation.

## Input-digest computation

`input_digest = sha256(textContent of #domain-model)`.

- Use the body of the `<script id="domain-model" type="text/turtle">` block.
- Use the exact bytes between the opening tag's `>` and the closing
  `</script>` — do **not** strip whitespace or normalise newlines. The
  Turtle block is canonical because `compose_model.py` re-emits it in a
  stable form; whatever bytes are in the input are the contract.
- The hash format is `sha256:` + lowercase hex digest.
- The computation is the platform's `domain_digest()` in
  `domain-forge/scripts/apply_layer.py`; the skill calls it and has no
  private implementation, so digests are comparable across skills.

## What the render script must do

- **Mount once.** Guard against re-execution by checking
  `document.querySelector('[data-layer="open-questions"]')` and bailing if
  already present.

- **Append a new tab.** Find the existing tab nav (in domain-forge models
  it is `nav[data-tabs]` or similar — read the input to find the right
  selector and embed the chosen selector at write time). Append one new
  tab button with `data-tab="open-questions"`, label "Open questions",
  badge showing the question count.

- **Mount the pane.** Create a `<section data-layer="open-questions"
  class="layer-open-questions tab-pane">` after the existing panes in the
  tab container. Render the category chip-bar, severity filter, and one
  card per question.

- **Source jump-link.** Clicking the `source` link should:
  - For `iri`: switch to the Ontology tab, locate the element with
    `[data-iri="<the iri>"]`, and `scrollIntoView({behavior:'smooth'})`.
  - For `dmn-decision`: switch to the DMN/Rules tab, locate
    `[data-dmn="<id>"]`.
  - For `swrl-rule`: switch to the same tab, locate `[data-swrl="<id>"]`.
  - For `horn-clause`: switch to the same tab, locate `[data-horn="<id>"]`.
  - For `rationale`: switch to whichever tab holds rationale
    (`[data-rationale="<id>"]`).

  If the target selector is absent (older model layout), fall back to a
  silent no-op — never throw.

- **Engine integration.** For each question with a non-null `engine_check`,
  consult the live runtime state (the engine exposes it as `R.facts` /
  `R.inferred` / similar — check the input's existing inline JS to find
  the canonical accessor). Use it to:
  - For `class-membership`: count individuals of the class; if > 0, dim
    the question and add a footnote "currently N individuals exist".
  - For `dmn-interval-coverage`: nothing live to check (the gap is
    structural), but render a button "Try value at the gap" that injects
    a transient input value and shows what the DMN evaluator returns.
  - For `functional-property-collision`: scan the A-box for any subject
    with >1 value for the named property; expand the question with
    those subjects.

- **Status edits.** Each card has a status chip
  (`open/addressed/deferred/out-of-scope`). Clicking toggles. The change
  is written into the **layer's own data script** in memory via
  `JSON.parse(JSON.stringify(...))` (never mutate the original script
  text). A "Save snapshot" button serialises the current state back into
  the data script and offers a download of the updated HTML — the same
  snapshot pattern engine viewers use today.

- **Survive missing engine.** If the live runtime `R` is not present
  (e.g. the user opened the HTML in a non-JS-friendly viewer), every
  engine_check action is hidden, but the static cards render normally.

## Style scoping

Every CSS rule in `#layer-open-questions-style` is prefixed with
`.layer-open-questions`. Use CSS variables already defined by the base
theme (`--bg`, `--ink`, `--border`, `--accent`, etc.) where possible, so
the layer respects the parent's light/dark scheme.

## Validator invariants 13–16 (implemented in `domain-forge/scripts/validate_model.py`)

A composed model containing this layer must pass (canonical wording in
`domain-forge/references/future-skills.md`):

13. Every `@LAYER:start` has a matching `@LAYER:end` in the right order.
14. The layer's `input-digest` equals `sha256` of the file's current
    `#domain-model` body.
15. The render script does not write to any `#model-*` or earlier
    `#layer-*-data` script (static scan).
16. The render script, run on a copy of the page with all OTHER layers
    removed, still renders without throwing and mounts its `[data-layer]`
    element (headless browser; WARN-skipped when none is available).

The platform writer emits a block that satisfies 13–16; `strip_layer.py`
is its exact inverse (`strip(apply(x)) == x`, byte-for-byte), which is
what makes the layer reversible.
