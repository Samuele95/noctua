# Future skills — the domain-forge workflow chain

This file specifies the skills that consume the HTML produced by a forge
and extend the workflow, and the layer contract they all obey. It is the
design contract for whoever (a future implementer, this session, or another
agent) builds or changes one of them.

## Who produces the base model — the forges

Two skills produce a base `model.html`; both emit the same artifact and
both are refined by `/domain-forge`:

| Forge | Input | Base model shape | Also adds |
|---|---|---|---|
| `/domain-forge` | prose (idea, notes, spec) | software domain: entities / value objects / bounded contexts per Bloch + DDD | — |
| `/dataset-forge` | a tabular dataset (csv, parquet, xlsx, json) | dataset ontology: `Record` with one data property per column, nominal classes with individuals, lookup hierarchies as functional object properties, an A-box row sample, SWRL/Horn derivation rules | the `geometry` layer (its own layer contract: `dataset-forge/references/report-contract.md`) |

A forge is not a chain skill: it *creates* the canonical Turtle rather than
adding to it. `/dataset-forge` is a hybrid — a forge that, in the same pass,
appends one layer with the platform writer below. A file's origin is
readable from the Turtle (`ex:sourceKind "dataset"`) and from its layers'
`produced-by`; `/domain-forge`'s refine mode uses this to pick the right
modeling discipline (see its Step 2, *Source kind*).

## Who consumes it — the chain skills

The skills, in the order they typically appear in a workflow. Four are
implemented (`/model-chat`, `/inferred-questions`, and on the dataset lane
`/data-lens` and `/dataset-shaper`); the other four remain design sketches:

| ID | Slash command | Adds | Status |
|---|---|---|---|
| 1 | `/instance-create`     | A-box individuals (data instances) against the T-box | sketch |
| 2 | `/code-implement`      | Target-language source code per component | sketch |
| 3 | `/countergen`          | Adversarial test inputs probing DMN / SWRL / Horn | sketch |
| 4 | `/model-diff`          | A diff layer comparing this file to a chosen prior layer or reference | sketch |
| 5 | `/model-chat`          | A transcript of Q&A grounded in the model | implemented |
| 6 | `/inferred-questions`  | A list of open modeling questions latent in the rationale | implemented |
| 7 | `/data-lens`           | `analysis`: findings with evidence, method and consequence, a reproducible dialogue transcript, transformation candidates (dataset models only; contract: `data-lens/references/analysis-contract.md`) | implemented |
| 8 | `/dataset-shaper`      | `shape`: the provenance-traced recipe, manifest, verification and lineage of a materialized dataset (dataset models only; contract: `dataset-shaper/references/shape-contract.md`) | implemented |

The orchestrator `/noctua` (its own skill; `noctua/references/chain-map.md`) routes a project across forges and chain skills and keeps `.claude/noctua-ledger.md`; it writes no layer.

## The platform scripts (owned by domain-forge, used by everyone)

| Script (`domain-forge/scripts/`) | Does |
|---|---|
| `apply_layer.py` | writes one `@LAYER` block — byte-superset on create; on update it strips the same-named layer first and reports that (the one non-superset case) — input never modified; importable (`apply_layer`, `domain_digest`, `list_layers`, `strip_layer`, `restamp_layers`); `--restamp` re-stamps digests after an add-only refine |
| `strip_layer.py` | `--layer NAME` / `--all` / `--list`; `strip(apply(x)) == x` byte-for-byte |
| `run_query.py` | drives the model's own engines headlessly (`--engine sparql\|swrl\|prolog\|dmn`); the grounding core of `/model-chat` and the symbolic channel of `/dataset-forge` |
| `validate_model.py` | invariants 1–19, of which 13–16 are the layer-chain invariants below |

Skills that were written before these existed (`/model-chat`,
`/inferred-questions`) keep their own `scripts/apply_layer.py` /
`strip_layer.py` (and model-chat's `run_query.py`) as thin delegates: same
CLI, but they locate `domain-forge/scripts` as a sibling directory
(overridable with `--domain-forge-dir` or `$DOMAIN_FORGE_DIR`), import the
platform module, and own only their layer-specific data shaping, render JS
and CSS. There is no second copy of the block format, the digest, the strip
logic or the engine driver, and no fallback: without domain-forge they exit 2.
New skills do the same.

---

## The architectural principle — pure-additive, reversible, functional

Every one of these skills is a **pure function** over HTML files:

```
                                ┌────────────┐
   modelₙ.html  ──────────────► │  /skill_X  │ ──────────► modelₙ₊₁.html
                                └────────────┘
                                      │
                                      └─ modelₙ.html UNCHANGED on disk
```

Three hard rules:

1. **Input is read-only.** The skill never modifies the input file. The output
   is a new HTML at a new path. The user can always re-open the input
   unchanged — that *is* the reversal.

2. **Output is a strict superset** of the input. Every byte the input
   carries is preserved verbatim in the output (canonical Turtle, JSON-LD,
   existing layers, every comment, every whitespace decision). The output
   adds new layers in dedicated script blocks marked with `@LAYER` comments.
   Nothing is rewritten, reformatted, or deleted.

3. **The HTML stays self-contained.** Validator invariant 9 (no external
   network refs) holds across the chain. Each skill's additions live inline
   in the file.

The chain is therefore a **functional pipeline of immutable snapshots**.
At any point the user has a chronological tree of HTML files on disk, each
one a complete, valid, openable document. To revert any step, open the
predecessor. To branch, run a skill twice against the same input with
different parameters.

```
idea.md ──► /domain-forge ──► model.html
data.csv ──► /dataset-forge ──► data.domain.html   (base model + geometry layer)
                                   │
                                   └──► /data-lens ─► data.domain.analysis.html ──► /dataset-shaper ─► data.domain.analysis.shaped.html (+ shaped/)

model.html
   │
   ├──► /instance-create  ─► model.instances.html
   │                              │
   │                              ├──► /code-implement(java)   ─► model.instances.java.html
   │                              │                                    │
   │                              │                                    └──► /countergen ─► model.instances.java.cgen.html
   │                              │
   │                              └──► /code-implement(typescript) ─► model.instances.ts.html
   │
   └──► /inferred-questions ─► model.questions.html
                                    │
                                    └──► /model-chat ─► model.questions.chat.html
```

Naming convention: each skill appends its short tag to the input's full stem
(`.instances`, `.java`, `.cgen`, `.diff`, `.chat`, `.questions`, `.analysis`, `.shaped`),
so `orders.domain.html` → `orders.domain.analysis.html` → `orders.domain.analysis.shaped.html`;
the two forge tags (`.domain`, `.refined`) are the only ones that name a base model rather than a layer. The user
can choose any path with `--out`, but this default keeps lineage visible.

---

## The HTML layer contract

A "layer" is a labelled addition to an HTML file. Each skill emits one or
more layers. A layer has four parts, in this exact order in the file:

```html
<!-- @LAYER:start instances v1
     produced-by: /instance-create
     produced-at: 2026-05-30T12:34:56Z
     input-digest: sha256:abc123…
     reverts-by: open the file at input-digest (the predecessor)
 -->
<script id="layer-instances-data" type="application/ld+json">
  { ... structured data the layer adds ... }
</script>
<script id="layer-instances-render" type="text/javascript">
  /* Render code for this layer. Runs on DOMContentLoaded, after the base
     runtime. Idempotent. Reads only this layer's data scripts; never
     mutates earlier layers' data scripts. */
  (function(){ ... })();
</script>
<style id="layer-instances-style">/* layer-scoped CSS */</style>
<!-- @LAYER:end instances -->
```

Why each part:

- **`@LAYER:start` / `@LAYER:end` comment markers**: the validator and any
  inspector can find the layer's bounds without parsing JS. They also let
  the file declare provenance (who produced this, when, against what input).
- **`layer-<name>-data` script**: the structured data the layer carries.
  Type depends on the layer: `application/ld+json` for entities/individuals,
  `application/json` for derived facts (counterexamples, chat log), or
  `text/javascript` for generated code held as a string literal.
- **`layer-<name>-render` script**: the JS that draws this layer's UI.
  Bundles every render dependency it needs (DOM helpers, parsers). Reads
  ONLY its own data script. Mounts into a new section it creates. **Never**
  modifies earlier layers' DOM nodes or data scripts.
- **`layer-<name>-style` (optional)**: CSS scoped via a layer-specific
  class prefix (`.layer-instances ...`) so it doesn't bleed into other layers.

A layer's render script must:

- **Be lazy and idempotent.** Running it twice does nothing extra.
- **Mount into a NEW container** appended to `<main>`. Never replace an
  existing tab or pane.
- **Add at most ONE new tab** (or sub-tab) to the existing navigation, with
  a `data-layer="<name>"` attribute and a clear label.
- **Survive missing dependencies.** If an earlier layer it expected isn't
  there, render an explanatory empty state — never throw.

`input-digest` in the layer header is a SHA-256 of the input file's
canonical Turtle script. That makes it possible to verify a chain's
integrity: each layer in a file must record the digest of the canonical
Turtle of the file it was produced against, and that digest must match
across all layers in a single file.

### Validator invariants for layered files (implemented in `validate_model.py`)

| # | What it checks | Why |
|---|---|---|
| 13 | Every `@LAYER:start` has a matching `@LAYER:end`, in the right order. | Layers can be sliced; markers are the contract. |
| 14 | Every layer's `input-digest` equals the digest of the file's canonical Turtle. | Catches divergence (a layer drift-pasted from another file). |
| 15 | No layer's render script writes to a data script with id `model-*` or `layer-*-data` of an *earlier* layer. | Pure-additive guarantee. Verified by static AST scan. |
| 16 | Each layer's render script, when run on a copy of the page with all OTHER layers removed, still renders without throwing. | Layers are independent. |

These are implemented in `scripts/validate_model.py`. A composed model at
step N must pass invariants 1–12 and 17–19 plus 13–16 for every layer it
carries. 15 is a static regex scan with documented limits (direct writes and
one-level aliases are caught; dynamically built ids are not); 16 needs a
headless browser and is WARN-skipped without one. A file with no layers
reports 13–16 as skipped and passes.

**When the base model is edited under its layers** (a `/domain-forge` refine
of a layered file) invariant 14 fails by design. The honest resolutions are
to strip the layers and re-run their producers, or — only when the edit
merely *added* terms — `apply_layer.py --restamp`, which is a named,
reported operation, not a silent fix.

### The reversal mechanism, precisely

**File-level reversal**: open the predecessor file. The skill never wrote
into the predecessor; it is unchanged on disk.

**Layer-level reversal within a file**: strip the layer's
`<!-- @LAYER:start name -->`…`<!-- @LAYER:end name -->` block. A small
helper `scripts/strip_layer.py model.html --layer instances` produces a
copy with one layer removed. Because layers are pure-additive, stripping
any combination is safe and the result is well-formed.

**In-viewer revert** (for snapshot-style editing surfaces like the engine
viewers): the layer's render script stores the SHIPPED data in a
sibling `<script id="layer-<name>-original">` block. The user edits via
UI; "Revert" copies original → data and re-renders. Same snapshot
principle as `assets/engine-source/capabilities/<id>/viewer.html` uses
today.

---

## The skills

### 1. `/instance-create` — populate the A-box

**Intent.** The T-box is the schema; the A-box is the data. After
`/domain-forge` produces a model with classes, properties, and DMN/Horn
rules, `/instance-create` populates it with **example individuals** that
exercise the schema. The result is an HTML you can open in a browser to
see the diagram with actual named instances in it, decision tables with
real input rows, Horn queries with ground facts.

**Trigger phrases.** "Add instances", "populate the model with examples",
"create test data", "instantiate the A-box", `/instance-create`.

**Input contract.** A composed `model.html` carrying at least the
ontology layer (canonical Turtle + JSON-LD with classes / object props /
data props all declared). DMN, Horn, SWRL layers optional; if present,
this skill should generate instances that meaningfully exercise them.

**Output additions.** A new layer named `instances`:

- `layer-instances-data` (JSON-LD): an `@graph` of additional nodes typed
  as `owl:NamedIndividual` and assigned one or more declared classes,
  carrying values for the data properties declared in their domain and
  object-property links to other individuals. The graph references only
  IRIs declared in the input — never invents new classes or properties.

- `layer-instances-render`: appends a new sub-tab "Instances" under the
  Ontology tab. Lists individuals grouped by class. Clicking an individual
  jumps to the details panel (which already exists in the runtime; the
  layer just feeds it data).

- The diagram's individuals layer (already rendered by the base runtime)
  picks up the new individuals automatically because the runtime walks
  `@graph` for `owl:NamedIndividual` types. **No change to the base
  runtime is needed** for this layer to integrate with the diagram.

**Idempotency.** Re-running `/instance-create` against the *same* input
HTML with the *same* arguments produces the *same* output HTML (deterministic
IRIs derived from class + index). Re-running against the previous output
detects the layer is already present and either: (a) refuses (default —
"instances layer already present; produce against the predecessor to
generate fresh"), or (b) extends with `--more` (appends additional
individuals with continuing indices, preserving the existing ones).

**Reversal.** Open the predecessor or
`scripts/strip_layer.py … --layer instances`.

**Dependencies.** Only `/domain-forge`. May read DMN/Horn/SWRL to bias
generation (e.g., produce a Transaction with amount=12000 to exercise the
HighValue rule).

**Open design question.** Should instance generation be deterministic
(IRI = `ex:Person-001`, ...) or labeled (`ex:alice` with a chosen name)?
Deterministic is reproducible; labels are more readable. Probably
deterministic IRIs with `rdfs:label` carrying a chosen display name.

---

### 2. `/code-implement` — generate target-language code

**Intent.** Take a domain-forge model (T-box, optionally A-box from the
prior step) and emit application-language source code per bounded context,
honoring the `codegen.target` hints carried per-fragment in `index.json`.
Currently planned targets: Java records, TypeScript interfaces, SQL DDL,
Pydantic models, Rust structs.

This is the skill the user pre-committed to back in the codegen
discussion: "the codegen will be another AGENTIC workflow."

**Trigger phrases.** "Generate code", "implement the model in <language>",
"produce Java records for this model", `/code-implement <language>`.

**Input contract.** A composed `model.html` with valid ontology. Each
class fragment in the input may carry a `codegen` block:

```json
{ "target": ["java", "typescript"],
  "options": { "java": { "package": "com.example.billing" } } }
```

The skill respects these targets; if unspecified, the user's argument
selects.

**Output additions.** A new layer named `code-<language>` (one per target
language; running against three languages produces three sibling layers in
one output file, or three sibling files if the user invokes with one
target at a time):

- `layer-code-<lang>-data` (`application/json`): a manifest
  `{ files: [{ path, content, component, sourceIRI }, ...] }` listing every
  generated file as a string. Embedded inline, no external file refs.

- `layer-code-<lang>-render`: appends a new tab "Code (<lang>)" to the
  top nav. Renders a per-component file tree with syntax-highlighted code
  panes. Each file has a Download button that produces it on disk via
  `Blob` + `<a download>`.

- A "Download all" action on the tab packages every file as a zip
  in-browser (using a small inlined zip-writer; no library import).

**Idempotency.** Same input + same target → same code, byte-for-byte
(deterministic generation, no timestamps or random ids in the output).
Re-running against a file that already has `layer-code-<lang>` either
refuses or replaces ONLY that layer (with explicit `--replace`); never
modifies other layers or the data.

**Reversal.** Open the predecessor.

**Dependencies.** `/domain-forge`. Benefits from `/instance-create` (the
generated code can include a sample-data seed file derived from the A-box).

**Open design question.** Should code generation know about DMN tables —
emit Java methods that translate DMN rule rows into `if`/`switch`
expressions? Or is DMN code generation a separate skill (`/dmn-engine`)?
Probably the latter: `/code-implement` covers DDD-shape code (records,
repositories, value objects); `/dmn-engine` is a dedicated skill for
executable decision logic.

---

### 3. `/countergen` — adversarial test inputs

**Intent.** The validator confirms the model is well-formed. The
*reasoner's consistency pass* (since `Land all`) catches violations.
Neither asks: **what inputs would expose a gap in the model's coverage?**
`/countergen` is the adversary: read DMN tables, SWRL rules, Horn clauses,
OWL restrictions, and synthesize edge-case inputs the modeller should
think about. Boundary intervals, missing-value cases, multi-typing traps,
combinations no rule covers.

**Trigger phrases.** "Find edge cases", "what is this model not covering",
"generate counterexamples", `/countergen`.

**Input contract.** Composed `model.html` with at least DMN, SWRL, or
Horn layers populated. (A pure-ontology model produces few counter
inputs — mostly boundary individuals at restriction edges.)

**Output additions.** A new layer named `counterexamples`:

- `layer-counterexamples-data` (`application/json`):

  ```json
  {
    "categories": [
      { "name": "DMN boundary intervals",
        "items": [
          { "target": "ex:RiskScore",
            "input": { "Transaction.hasAmount": 10000.00 },
            "concern": "Rule boundary [10000..) vs [1000..10000). Which fires for exactly 10000?",
            "severity": "high"
          },
          ...
        ]
      },
      { "name": "SWRL antecedent unsatisfied", "items": [...] },
      { "name": "Multi-typing under disjointWith", "items": [...] },
      { "name": "Functional property race", "items": [...] }
    ]
  }
  ```

- `layer-counterexamples-render`: appends a "Counterexamples" tab. Renders
  each category as a card with the input shape, the concern in prose, the
  severity badge, and a "Test against the runtime" button that injects
  the input into the live JSON-LD and re-runs the reasoner so the user
  can SEE what fires (or doesn't fire) for that case.

**Idempotency.** Same input → same counterexamples (generation is
deterministic: scan rules, enumerate boundary cases, compute uncovered
combinations). Re-run replaces only `layer-counterexamples` with
`--regenerate`; default refuses.

**Reversal.** Open the predecessor.

**Dependencies.** `/domain-forge`. Optionally `/instance-create` (so
counterexamples can suggest individuals to add or modify against the
existing A-box).

**Open design question.** Should counterexample generation be exhaustive
(every boundary, every interval edge, every Cartesian rule miss) or
prioritised (top-K by severity)? Probably both — exhaustive in the data
script, ranked in the UI with a "show all" expansion.

---

### 4. `/model-diff` — compare layers within a file or across files

**Intent.** Models evolve. After several iterations of `/domain-forge`
refinement, or after `/code-implement` produced code that diverges from a
later model edit, the user wants to see what changed. `/model-diff`
compares two snapshots and emits a diff layer.

**Trigger phrases.** "Diff this model against <other>", "what changed
since version 3", `/model-diff <other.html>`, `/model-diff --vs-layer instances`.

**Input contract.** ONE primary HTML file (the "current"). The reference is
specified either:

- **As an argument**: `--vs <other.html>`. The skill embeds the other
  file's data scripts under `<script id="reference-snapshot">` so the
  diff layer can reach them at render time, and the output remains
  self-contained.
- **As a prior layer in the same file**: `--vs-layer <name>`. Diffs the
  current canonical state against the state implied by stripping every
  layer after that point. Only meaningful if the workflow has chained
  layered transformations.

**Output additions.** A new layer named `diff-<id>` (id is the short hash
of the reference):

- `layer-diff-<id>-data` (`application/json`):

  ```json
  {
    "from": "ref-digest",
    "to":   "current-digest",
    "classes": {
      "added":   ["ex:Refund", ...],
      "removed": ["ex:OldName", ...],
      "changed": [{ "iri": "ex:Order", "changes": [
        {"kind": "subClassOf added", "value": "ex:Aggregate"},
        {"kind": "data property added", "value": "ex:hasTotal"},
        ...
      ]}]
    },
    "properties": { "added": [...], "removed": [...], "changed": [...] },
    "dmn":        { "added": [...], "removed": [...], "changed": [...] },
    "rules":      { "added": [...], "removed": [...], "changed": [...] }
  }
  ```

  The data is structural delta, not a textual patch — it survives Turtle
  reformatting that doesn't change the underlying model.

- `layer-diff-<id>-render`: appends a "Diff" tab. Renders each category
  with green/red/amber indicators per change, jump-links into the
  affected entity in the Ontology tab, and a "Generate migration plan"
  button that derives a plain-English summary (schema migrations, DMN
  rule changes, Horn rule diffs — feeds the `/document-project` skill if
  invoked downstream).

**Idempotency.** Diff is deterministic given fixed `from` and `to`. The
output is `model.diff-<refid>.html`. Two diffs against different
references produce two distinct files; both refer back to the same
predecessor.

**Reversal.** Open the predecessor.

**Dependencies.** Two snapshot inputs (either from disk or via prior
layers). Doesn't require any specific layers in the inputs beyond the
canonical ontology.

**Open design question.** Should diff include semantic comparison
(`R(x,y) ∧ Symmetric ⇒ R(y,x)` — does inferring the symmetric closure
of "from" match "to" with one rule removed)? That requires running the
reasoner on both snapshots and diffing R.facts.inferred. Useful but heavy.
Worth investigating once we have a few real evolutions in hand.

---

### 5. `/model-chat` — grounded Q&A over the model  *(implemented)*

**As implemented** (the skill's own `SKILL.md` is the contract; this is the
summary that keeps the chain document truthful). Every answer is produced by
**running the model's own engines** — SPARQL over the asserted graph, the
RDFS/SWRL reasoner over the inferred graph, the Prolog runner, the DMN
tester — through the headless driver `run_query.py`; the agent never answers
from its reading of the file, and when no engine can ground a question it
refuses and names the gap. The output is a `chat` layer
(`layer-chat-data` = the transcript with each turn's paradigm, query, raw
result, answer and a `grounded` flag; the render draws the transcript with a
live *re-run* button per turn that re-executes the query against the page's
engines). Default output `<input-stem>.chat.html`; `--continue` appends turns
to an existing `chat` layer (the layer is replaced, the base is untouched).
The earlier sketch's "answer from the rationale layer with citations" design
was **not** built — citation of prose is exactly what the implemented skill
refuses to do without an engine behind it. Open design questions from the
sketch are closed: the chat has access to inference results (it runs the
reasoner), and re-opening the file never starts new turns (the render only
re-runs stored queries on demand).

---

### 6. `/inferred-questions` — surface latent modeling questions  *(implemented)*

**As implemented** (see the skill's own `SKILL.md`). Emits one `open-questions`
layer: rows found **mechanically** (DMN interval-coverage gaps, SWRL
antecedent classes with no possible individuals, OWL restriction edges the
reasoner cannot classify, multi-typing under disjointness, functional-property
races, declared classes without individuals) and rows found **by judgment
over the rationale** (an external system named but its failure mode
unmodelled, an unstated immutability stance, a bounded context named but not
separated). Each row carries its source anchor (the IRI, rationale block or
DMN decision it stems from), a severity, the one-line question, a
`suggested_next` action, and a status chip (`open` / `addressed` /
`deferred` / `out-of-scope`) the user sets in the rendered UI — the skill
never auto-resolves. Default output `<input-stem>.questions.html`;
`--severity-min` filters; a headless smoke test checks the tab renders.
The layer is pure-additive and passes invariants 13–16; the input is never
modified. It asks; `/model-chat` answers.

---

## Workflow examples

### Example 1 — KE-course milestone delivery

```
/domain-forge "Payments with risk scoring..."   →  model.html
/instance-create                                 →  model.instances.html
/code-implement java                             →  model.instances.java.html
/countergen                                      →  model.instances.java.cgen.html
/inferred-questions                              →  model.instances.java.cgen.questions.html
bundle.py model.instances.java.cgen.questions.html → bundle/
                                                     ↓
                                                /document-project
```

Each step's HTML is on disk. The user can revert to any step by opening
its predecessor. The final HTML carries seven layers (canonical,
instances, code-java, counterexamples, open-questions, plus the original
DMN/Horn/SWRL). The KE submission is the bundle produced from that
seven-layer artifact; the report is a `/document-project` LaTeX book
written *about* it.

### Example 2 — Iterative refinement

```
/domain-forge "Order management..."            →  model.v1.html
/inferred-questions                            →  model.v1.questions.html
                       (user reviews questions, edits)
/domain-forge model.v1.questions.html          →  model.v2.html
/model-diff --vs model.v1.html  (run from v2) →  model.v2.diff.html
                       (user inspects the diff, accepts)
/code-implement typescript                     →  model.v2.diff.ts.html
```

`/model-diff` produces a file that shows the v1→v2 evolution side-by-side
*and* embeds both states for further chaining. The user can branch from
v2 in different directions and diff each branch against v2 later.

### Example 3 — Chat after a long pause

```
            model.html
                │
   ┌────────────┴────────────┐
   │                          │
/model-chat ────► model.chat.html
                     │
                     └─ user asks "which transactions does the model
                        classify high-risk?". The skill runs the SWRL
                        reasoner + a SPARQL SELECT over the inferred
                        graph and answers from the result rows, with the
                        query stored so the turn can be re-run in the page.
                        Output (--continue): model.chat.v2.html
```

`model.chat.v2.html` has TWO turns of chat. `model.chat.html` (the
prior) still has ONE turn — both files coexist on disk. The conversation
is reproducible, citable, shareable.

---

## What the implementer of each skill needs from this document

1. **The intent**: the one-paragraph framing at the top of each skill's
   section.
2. **The input/output contract**: what must be in the input HTML and
   what exactly the output adds (as labelled layers).
3. **The idempotency rule**: what re-running does.
4. **The reversal rule**: how the user undoes.
5. **The dependency rule**: what other layers improve this skill's output.
6. **The validator extensions**: invariants 13–16 every layered file must
   satisfy.

Things deliberately left UNspecified (to be designed at implementation
time):

- The exact JSON shape of each layer's data script beyond the sketches
  above.
- Whether each skill is a Claude Code skill (interactive, agent-driven)
  or a deterministic Python script. Likely most are skill + script
  hybrids: the agent decides *what* to add, a script writes the layer
  cleanly.
- The exact CSS / DOM structure of each layer's UI tab.
- How `/model-chat` is hosted (in-browser sandbox? external runtime?
  required: re-opening must NOT auto-start new chat turns).
- Whether layers can DEPEND on each other (read each other's data
  scripts) — current design says yes for READ, never for WRITE.

---

## Cross-cutting invariants

For the chain to behave as a true functional pipeline, every skill
together must enforce:

1. **Read-only input.** The input file's bytes never change.
2. **Strict superset output.** The output contains every byte of the
   input verbatim, plus the new layer's bytes, plus the closing markers —
   with one named exception: a skill re-run against a file that already
   carries *its own* layer (`/model-chat --continue`, `/data-lens
   --continue`, a `/dataset-forge` refine, a `/dataset-shaper` re-run)
   replaces that layer through the platform writer, which strips the
   same-named block first and reports it; the base and every other layer
   remain byte-identical, and the predecessor file stays on disk.
   Otherwise, diff `input` and `output` and the only change is one inserted layer
   block before `</body>` (verifiable: `strip_layer.py output --layer NAME
   --out back.html` must give a `back.html` byte-identical to `input`;
   `domain-forge/scripts/tests/test_layers.sh` checks exactly this).
3. **Self-contained output.** No skill introduces external refs. Validator
   invariant 9 remains a hard requirement.
4. **Layer independence.** Stripping any layer with `strip_layer.py`
   produces a still-valid composed model. Invariant 16 is the test.
5. **Provenance.** Every layer carries `produced-by`, `produced-at`,
   `input-digest` in its start marker. The chain is auditable.
6. **No cross-layer mutation.** A render script may *read* an earlier
   layer but never *write* to its data script. Static AST scan in
   invariant 15.

A skill that breaks any of these stops being part of the chain — it's a
data lossy operation, and the user lose reversibility. Design new skills
under the same rules.
