---
name: inferred-questions
description: Surface latent modeling questions in a domain-forge HTML model — gaps in DMN coverage, edges of OWL restrictions, SWRL antecedents that never bind, multi-typing under disjointness, rationale that names an external system without defining its failure mode. Emits a pure-additive `open-questions` layer on the input HTML; the input file is never modified. Use this skill whenever the user runs `/inferred-questions`, hands you a domain-forge `model.html` and asks "what is this model not covering", "what open questions does this leave", "surface the gaps", "what should I refine next"; or whenever the next sensible step in the domain-forge workflow chain is a refinement-review pass against an existing model. Sibling to `/domain-forge` (which forges or refines the model itself) and `/countergen` (which generates adversarial *test inputs* — by contrast this skill produces *open modeling questions for the human*).
---

# /inferred-questions

A pass over a composed `/domain-forge` HTML model that surfaces **latent modeling questions** — gaps the modeller did not fully answer. The output is a new HTML file that is a strict superset of the input: every byte preserved verbatim, plus one new `open-questions` layer (data + render + style) appended.

The skill is one link in the domain-forge functional pipeline. The chain's contract — pure-additive layers, byte-exact input preservation, `@LAYER:start/end` markers, `input-digest` provenance, validator invariants 13–16 — is binding. See `references/layer-contract.md` for the precise spec.

## What "latent" means here

Every rationale block in a model implicitly raises questions the modeller didn't fully answer. Every DMN table with rules for `[1000..10000)` and `[10000..)` implicitly asks "is the `[0..1000)` case really zero?". Every SWRL rule with an antecedent atom whose class has zero instances implicitly asks "does this rule ever fire?". A model with `Person ⊓ ¬Cardholder` and `disjointWith(Person, Merchant)` implicitly asks "what about an internal employee paying — is that a Person or a Cardholder?".

The skill's job is to **find these gaps mechanically where it can** (DMN interval coverage, antecedent-class emptiness, restriction edges, disjointness traps, functional-property races, missing-individuals against declared classes) and **rationale-driven gaps using judgment** (a rationale block that names an external system without modelling its failure, an entity whose immutability stance is unstated, a bounded-context boundary that is named but not separated). Both kinds become rows in the `open-questions` layer.

The skill **does not auto-resolve**. The output is a *human-review checklist*; the user marks each question addressed / deferred / out-of-scope in the rendered UI, typically before going back to `/domain-forge` for refinement.

## Relationship to neighbouring skills

- `/domain-forge` forges or refines the model. Its memory file (`.claude/domain-forge-memory.md`) records accepted/declined modeling stances. This skill **reads that memory** so it does not surface questions the user has already decided.
- `/countergen` produces adversarial *test inputs* exercising DMN/SWRL/Horn rules. That is data for the A-box. **This skill produces open *modeling questions for the human*.** Different deliverable, different audience.
- `/model-chat` answers questions; this skill *asks* them. After this skill produces an open-questions layer, the user might invoke `/model-chat` to discuss specific ones, or go back to `/domain-forge` to address them, or simply mark them deferred.

## Trigger and arguments

```
/inferred-questions <path/to/model.html>
```

Flags:

- `--out <path>` — output HTML path. Default: `<input-stem>.questions.html` next to the input.
- `--regenerate` — replace an existing `open-questions` layer in the file (refuses by default).
- `--severity-min low|medium|high` — drop questions below the threshold. Default: keep all; UI filters at view time.
- `--max-questions N` — cap the total count. Default: unlimited; UI ranks and paginates.
- `--report-only` — produce the questions.json and write a markdown summary, skip the HTML write.

## Procedure

### Step 1 — Read project memory

Look for `.claude/domain-forge-memory.md` at the project root (cwd).

- If present, read it. The "Accepted findings" and "Declined findings" sections tell you what the user has already decided; the extractor should not re-surface these as open questions.
- If absent, proceed without it; mention "(no memory file found)" in your first status line.

This skill does **not** maintain its own memory file. Open-questions are inherently per-snapshot — once addressed, the answer lives in the next `/domain-forge` refinement, not in this skill's history.

### Step 2 — Validate the input

Read the input HTML and confirm:

- It is a domain-forge composed model (contains `<script id="domain-model" type="text/turtle">` (or the legacy `id="model-turtle"`)).
- It does **not** already contain an `open-questions` layer (unless `--regenerate`).

If validation fails, stop with a precise error referencing the actual missing/conflicting marker.

### Step 3 — Dispatch the extractor subagent

Invoke `question-extractor` via the Agent tool. The extractor is read-only — it returns a `questions.json` artifact and a one-paragraph summary. The brief contains:

- **Mode**: fresh extraction.
- **Source**: the input HTML path.
- **Memory**: full text of `.claude/domain-forge-memory.md` (or "no memory" sentinel).
- **Output path**: `.claude/inferred-questions-runs/<UTC-timestamp>/questions.json`.
- **Severity filter** and **max-questions** from flags.

The extractor's complete instructions live in `agents/question-extractor.md`. Do **not** duplicate them in the orchestrator's reasoning.

If `subagent_type="question-extractor"` is not registered, fall back to dispatching `general-purpose` with the contents of `agents/question-extractor.md` as the prompt prefix, followed by the brief. The result is identical. If no sub-agent mechanism exists at all (e.g. on claude.ai / the API where only this conversation runs), skip dispatching entirely: read `agents/question-extractor.md` and carry out its full contract yourself, inline.

### Step 4 — Render the findings table inline

Read `questions.json` and render the question list as a Markdown table. Group by category; include id, source-anchor (the IRI / rationale block / DMN decision the question stems from), severity, and the one-line question. This is the user's first read — it must be skim-friendly.

If `--report-only`, stop here after writing a sibling `questions.summary.md`.

### Step 5 — Apply the layer

Invoke `scripts/apply_layer.py`:

```
python scripts/apply_layer.py \
  --input <input.html> \
  --questions <run-dir>/questions.json \
  --output <out.html> \
  [--regenerate]
```

The script is the **only** place that writes HTML. It guarantees:

- The output's leading bytes equal the input's leading bytes up to the chosen insertion point (just before `</body>`).
- The `@LAYER:start open-questions` comment carries `produced-by: /inferred-questions`, `produced-at` (UTC), and `input-digest` (SHA-256 of the input's canonical Turtle script body).
- The data, render, and style scripts use the IDs `layer-open-questions-data|render|style`. The render code mounts a new "Open questions" tab that integrates with the input's `nav.tabs` / `.tab-pane.active` convention — the pane stays hidden until its tab button is clicked, so the host's first-load layout is unaffected.
- When the input model has **zero individuals**, the script collapses per-class `missing-individuals` questions into a single meta-question. The taxonomy already advises this, but enforcing it mechanically keeps the output focused even when the extractor over-enumerates.
- Re-running against a file that already has the layer **refuses** unless `--regenerate`, in which case the script strips the previous block precisely and writes the new one in the same position.

If the script exits non-zero, surface its error and stop. The script's invariants are the trust boundary — never paper over a failure by editing the HTML inline.

### Step 5b — Smoke-test the render

The render script ships inline in the layer and only executes when a browser opens the file — so a malformed layer can slip past `apply_layer.py` and only surface as a broken tab when the user actually views the output. The smoke test runs headless Chrome on the produced HTML and inspects the rendered DOM:

```
python scripts/smoke_test.py --html <out.html>
```

It confirms: the pane is mounted but starts hidden (no `active` class), the tab button has been appended to `nav.tabs` with a count badge that matches the questions JSON, the card count matches, and no JS errors fired.

Treat it as a **soft gate**: if it reports any failure, surface the specific failed check, stop, and do not claim the output is ready. If `google-chrome`/`chromium` is not installed, the script warns and exits 0 — the layer is still valid as static HTML and the layer-write invariants were already enforced by `apply_layer.py`; the user simply gets no automated render check.

### Step 6 — Report

Print to chat:

- The output HTML path.
- A one-paragraph summary citing the highest-severity question(s) by source-anchor.
- A reminder that the input file is unchanged on disk (reversal = open the predecessor).

## What the layer renders

A new top-level tab labelled **"Open questions"** with `data-layer="open-questions"`. Inside:

- A category filter chip-bar (`boundary`, `coverage-gap`, `rationale-gap`, `restriction-edge`, `multi-typing`, `functional-race`, `missing-individuals`, plus any custom categories the extractor used).
- A severity filter.
- One card per question with:
  - The question prose.
  - A `source` jump-link into the relevant IRI / DMN decision / rationale block in the existing Ontology tab. Click → that tab opens and scrolls to the anchor.
  - A `suggested-next` line.
  - A status chip (`open` / `addressed` / `deferred` / `out-of-scope`). Edits are stored in the layer's data and survive snapshot-save via the same pattern the engine viewers use.
  - For categories where the **embedded engine** can verify the concern live (e.g. `missing-individuals` against `R.facts.inferred`), a small **"Check live"** action that consults the runtime reasoner state and either dims the question (already covered) or expands it with the current inferred state.

The render code is bundled and idempotent (running it twice does not double-render). It reads only its own data script; it never mutates any `model-*` or earlier `layer-*` data block.

## Layer JSON schema (the contract)

```json
{
  "version": 1,
  "produced_at": "2026-05-30T14:00:00Z",
  "input_digest": "sha256:abc123…",
  "categories": [
    "boundary", "coverage-gap", "rationale-gap", "restriction-edge",
    "multi-typing", "functional-race", "missing-individuals"
  ],
  "questions": [
    {
      "id": "q-001",
      "source": "rationale-014",
      "source_kind": "rationale",
      "category": "rationale-gap",
      "severity": "medium",
      "question": "Rationale 14 names the payment gateway as external. What happens when the gateway times out?",
      "suggested_next": "Add an upstream input to RiskScore representing gateway availability, or document the timeout policy in a rationale block.",
      "engine_check": null,
      "status": "open"
    },
    {
      "id": "q-002",
      "source": "ex:RiskScore",
      "source_kind": "dmn-decision",
      "category": "coverage-gap",
      "severity": "high",
      "question": "RiskScore covers [10000..] and [1000..10000) but not [0..1000). Is the low-value case meant to be zero, or is it an unmodelled state?",
      "suggested_next": "Add a baseline rule [0..1000) → 0, or document the deliberate gap in the decision's rationale.",
      "engine_check": {
        "kind": "dmn-interval-coverage",
        "decision": "ex:RiskScore",
        "missing_interval": "[0..1000)"
      },
      "status": "open"
    }
  ]
}
```

`engine_check` is optional and tells the render script how (if at all) to consult the embedded reasoner at view time. Static questions (no live verification) leave it `null`.

## Idempotency, determinism, reversal

- **Deterministic.** Same input HTML + same flags → byte-identical output. Question ids are derived from `source_kind + source + category + hash(question-prose)`, not random.
- **Idempotent.** Re-running against a file that already has the layer refuses unless `--regenerate`. Re-running against the *predecessor* with the same flags reproduces the same questions in the same order.
- **Reversal.** Open the input file — it is unchanged on disk. Or strip the layer with `python scripts/strip_layer.py model.questions.html --layer open-questions` (helper script included).

## Dependencies and engine integration

This skill depends on `/domain-forge` twice over: it produces the input, and it owns the **layer platform** — `scripts/apply_layer.py` (the only writer of `@LAYER` blocks and of the `input-digest`), `scripts/strip_layer.py`, and `validate_model.py` invariants 13–16. This skill's `scripts/apply_layer.py` and `scripts/strip_layer.py` keep their own CLIs but delegate to that platform, so `domain-forge` must be installed as a sibling skill directory (or `DOMAIN_FORGE_DIR` / `--domain-forge-dir` must point at it); without it they stop with `ERROR: platform scripts not found`. Layer contract: `domain-forge/references/future-skills.md`.

The composed input HTML carries the **full reasoner engine** (`R` runtime state, the 7 capabilities under `engine-source/`, the SWRL forward-chainer, the consistency pass). The Python extractor does **not** execute the engine — it reads the static model. But for question categories where live reasoning is informative (`missing-individuals`, `multi-typing`, `functional-race`), the layer's render script consults the live `R` state in the browser to either dim the question (the concern is already resolved in the current A-box) or annotate it with concrete state ("currently 0 individuals of class `ex:Person`").

This keeps the build deterministic and the view dynamic — the right division of labour for a pure-additive HTML pipeline.

## Output paths and naming

The default `<input-stem>.questions.html` follows the workflow convention:

```
model.html           →  /inferred-questions  →  model.questions.html
model.instances.html →  /inferred-questions  →  model.instances.questions.html
```

A run directory `.claude/inferred-questions-runs/<UTC-timestamp>/` holds the intermediate `questions.json` and `summary.md` for the run, mirroring the `/domain-forge` convention.

## Memory file template

This skill does not maintain its own memory file. The questions are inherently per-snapshot.
