---
name: domain-forge
description: >-
  Turn a textual project idea into a VISUAL, language-agnostic software DOMAIN MODEL rendered as a
  single self-contained HTML file — entities and relationships extracted from prose, modeled per
  best practice, and made compatible with knowledge-engineering languages (ontology T-box/A-box,
  DMN decision tables, Prolog/Horn rules). Trigger when the user runs /domain-forge, asks to turn
  an idea, notes, or a spec into a domain model, conceptual model, entity-relationship model,
  ontology, or knowledge model; asks to extract domain entities and relationships from a
  description; wants a visual model of a problem domain before writing code; or hands you an
  existing domain-forge HTML file to refine (including one made by /dataset-forge). Anchored to
  Bloch's Effective Java plus SOLID, GoF, FP, DDD, Hexagonal. Owns the model platform (contract,
  engines, validator, layer tools). Sibling to /architect (existing code) and /dataset-forge (same
  model from a dataset). Not for a CSV/parquet/spreadsheet — that is /dataset-forge.
---

# /domain-forge

A structured pass that turns a textual idea — a paragraph, a pile of notes, a spec — into a **visual, language-agnostic domain model** rendered as one self-contained HTML file. The model is *visual more than syntactical*: a reader sees boxes and labelled connectors, not class declarations. But it is simultaneously *computable*: the same file embeds a canonical RDF/Turtle serialization and tags every entity and relationship as an addressable `data-*` DOM node, so a later skill run can lift the whole model — or a single subcomponent — back out and deepen it.

The model is anchored to *Effective Java* (Bloch, 3rd ed.) supplemented by SOLID, GoF, FP, DDD, and Hexagonal Architecture, used as the **modeling** vocabulary (what is an entity vs. a value object, where an abstraction boundary belongs, what must be immutable). It is made **KE-compatible**: the structural layer is an ontology (T-box schema + A-box instances), decision logic can be expressed as DMN decision tables, and derivable knowledge as Prolog/Horn rules.

Three axes, inherited from `/architect`:

- **Model** — which concepts exist, identity vs. value, what is immutable, what the literals are.
- **Abstraction** — class hierarchy (subClassOf), interfaces-as-concepts, where to generalize vs. stay concrete.
- **Composition** — how relationships (object properties) wire concepts together, bounded contexts, where the seams are.

The extraction is heavy and runs in an isolated subagent (`domain-extractor`, read-only); the apply phase — writing and editing the HTML — happens in your main conversation. You are the orchestrator. **Keep your own context lean.** The KE vocabulary, the Bloch→modeling mapping, and the HTML contract live in the extractor and the reference files — do not duplicate them in your reasoning.

## Relationship to /architect

- `/architect` audits and reshapes the architecture of an **existing codebase**.
- `/domain-forge` forges a **domain model from an idea** — typically *before* code exists, or alongside it as the conceptual reference. Its output is a model artifact (HTML), not code changes.
- The two share a workflow spine (memory → read-only subagent → blueprint + ranked findings → per-element opt-in → apply with verification → memory → summary) and the same Bloch/DDD vocabulary, so a model forged here feeds naturally into a later `/architect` pass once code is written.

## The platform, the forges, and the chain

Three things share the `model.html` artifact, and this skill owns the first:

- **The platform** — the HTML contract (`references/html-contract.md`), the
  runtime and its engines (`assets/template.html`, `assets/engine-source/`),
  the KE vocabulary, the validator (`scripts/validate_model.py`, invariants
  1–19), and the **layer tools** `scripts/apply_layer.py`, `scripts/strip_layer.py`
  and `scripts/run_query.py` (the headless driver of the model's own SPARQL /
  SWRL / Prolog / DMN engines). The rule: a skill that writes or verifies a
  layer uses these scripts by reference and carries no copy of its own —
  two copies drift, and the digest algorithm must be one. (`/model-chat` and
  `/inferred-questions` keep their own CLIs as thin delegates to these
  scripts; `references/future-skills.md` records the arrangement.)
- **The forges** — the producers of a base model. `/domain-forge` (this skill)
  forges it from prose; `/dataset-forge` forges it from a tabular dataset, with
  a `Record`-centric ontology and a `geometry` layer in the same pass. Both emit
  the same artifact and both are refined here. Because a dataset ontology is
  shaped on purpose (one class per row kind, one data property per column), a
  refine pass over a dataset-forge file must not re-model it as software — see
  Step 2, *source kind*.
- **The chain** — skills that take a `model.html` and produce a new HTML that is
  a strict superset of it: `/model-chat`, `/inferred-questions`, on the dataset
  lane `/data-lens` and `/dataset-shaper`, and the future `/instance-create`,
  `/code-implement`, `/countergen`, `/model-diff`. Layers added, nothing
  rewritten, every step reversible by opening the predecessor. `/noctua`
  orchestrates the chain; it invokes, never edits.

The chain's design contract is `references/future-skills.md`. When asked about
*next steps after this model* or about any of those slash commands, point the
user at that file. When implementing a chain skill, write the layer with
`scripts/apply_layer.py` (it enforces the `@LAYER:start/end` markers, the
`layer-<name>-data` + `layer-<name>-render` pair and the `input-digest`
provenance) and validate with `validate_model.py`, whose invariants 13–16 check
the layer-superset / chain property.

## Trigger and arguments

The skill runs in one of three input modes, auto-detected from the argument:

- `/domain-forge "<idea text>"` — extract a fresh model from inline prose.
- `/domain-forge <path/to/notes.md>` (or `.txt`) — extract a fresh model from a notes/spec file.
- `/domain-forge <path/to/model.html>` — **refine** an existing domain-forge model whole.
- `/domain-forge <path/to/model.html> --component <id>` — refine **one addressable subcomponent** (an entity-cluster) in isolation. This is the primary subcomponent-refinement path; see Step 6b.

Flags:

- `--layers ontology|dmn|rules|swrl|all` — which KE layers to populate. **`ontology` is the default and always on.** `dmn` adds decision tables, `rules` adds Prolog/Horn clauses, `swrl` adds SWRL rules over OWL/RDFS; the three are *gated* (extra depth, opt-in). `all` requests every layer. The three rule/decision layers are competing paradigms, not additive knobs — pick by `references/paradigm-fit.md`.
- `--out <path>` — output HTML path. Default: `<input-stem>.domain.html` next to the input for a notes file, `domain-model.html` in cwd for inline text, and `<input-stem>.refined.html` for either refine mode (a refine never writes over its input).
- `--report-only` — produce the blueprint + ranked findings, render nothing, skip apply.
- `--blueprint-only` / `--findings-only` — emit just that half.
- `--full` — all findings, no top-N filter (warn first if the idea is large / yields >25 entities).

Args may combine: `/domain-forge spec.md --layers dmn --component cls-Transaction`.

## Procedure

### Step 1 — Read project memory

Look for `.claude/domain-forge-memory.md` at the project root (cwd).
- If present, read it.
- If absent, create it silently from `references/memory-template.md` (verbatim). Mention this in your first status line.

This file records modeling stances ("Money is always a value object", "we model the billing context separately"), accepted/declined findings, and naming conventions, so the extractor does not re-propose decided modeling work or rename stable IRIs.

### Step 2 — Resolve input mode and dispatch the extractor

Determine the mode (fresh-text / refine-whole / refine-component) from the argument. For refine modes, read the existing HTML and parse its embedded Turtle (the `<script id="domain-model" type="text/turtle">` block) — that is the canonical current model.

**Source kind.** In refine modes, also determine what the model was forged *from*: `python <skill-dir>/scripts/strip_layer.py <input.html> --list` shows the layers and their `produced-by`; a `geometry` layer, a `produced-by: /dataset-forge`, or an `ex:sourceKind "dataset"` annotation in the Turtle means the model is a **dataset ontology**. Otherwise it is a **software domain** (the default, and always the case for fresh text). Pass the kind to the extractor: for a dataset ontology the Bloch/DDD findings (identity-vs-value, bounded-context splits, "too many data properties on one class") do not apply — the extractor is told so and restricts itself to lookup hierarchies, property characteristics, rule/decision layers and naming.

**Layered input.** If the input carries `@LAYER` blocks, the file is a chain node and the refine must keep the chain property: the output goes to a **new path** (default `<stem>.refined.html`, never in place), and any edit to the canonical Turtle invalidates every layer's `input-digest` (validator invariant 14). Before the first apply, tell the user which layers the file carries and offer the two honest options: (a) strip the layers first (`strip_layer.py <in.html> --all --out <stripped.html>`), refine, and re-run the producing skills afterwards — required whenever a finding renames or removes a term, because a layer that names that term would otherwise be silently stale; or (b) when every selected finding only *adds* (new classes, individuals, rules, a new layer via `--layers`), refine, then re-stamp the digests with `python <skill-dir>/scripts/apply_layer.py <out.html> --restamp --in-place` and say in the summary which layers were re-stamped and why that is safe. Never leave a layered file whose validator run fails invariant 14 as the deliverable.

Invoke `domain-extractor` via the Agent tool with `subagent_type="domain-extractor"`. Pass a self-contained brief:

- **Mode** and **source**: the idea text, the notes-file contents, or the current model's Turtle (+ the target `--component` id for component mode).
- **Source kind**: `software-domain` | `dataset-ontology` (see above).
- **Layers requested**: from `--layers` (default `ontology`).
- **Depth requests**: whether to record the DRD wiring for multi-step decisions (only with `dmn`) and whether to emit a representative A-box — the two things that make the rendered model runnable (Step 6). Default: both yes whenever the source offers concrete examples.
- **Memory**: full text of `.claude/domain-forge-memory.md`.
- **Output paths** (create the run directory first):
  - `.claude/domain-forge-runs/<UTC-timestamp>/blueprint.md` (unless `--findings-only`).
  - `.claude/domain-forge-runs/<UTC-timestamp>/findings.json` (unless `--blueprint-only`).
  - `.claude/domain-forge-runs/<UTC-timestamp>/model.ttl` — the extractor's proposed/updated canonical Turtle.

The extractor is read-only (it writes only to the run directory, never the output HTML) and returns the artifact paths + a one-paragraph summary.

If `subagent_type="domain-extractor"` is not registered, fall back to dispatching `general-purpose` with the contents of `agents/domain-extractor.md` (in this skill directory) as the prompt prefix, followed by the brief. The result is identical. If no sub-agent mechanism exists at all (e.g. on claude.ai / the API where only this conversation runs), skip dispatching entirely: read `agents/domain-extractor.md` and carry out its full contract yourself, inline.

### Step 3 — Render the blueprint

Unless `--findings-only`: read `blueprint.md` and restate its **§1 Domain assessment** and **§2 Proposed model** sections inline in chat **verbatim** — they are the load-bearing framing of the model's shape and the user must see the extractor's exact words. Link the rest by reference (§3 Entity inventory, §4 Relationship map, §5 Layer coverage, §6 Open modeling questions). Do not paraphrase §1/§2.

### Step 4 — Render the findings table

Unless `--blueprint-only`: read `findings.json` and render as Markdown. Each finding is a proposed modeling element or decision:

| ID | Axis | Depth | Anchors | Element | Title | KE form | Risk |
|----|------|-------|---------|---------|-------|---------|------|
| 1 | Model | structural | EJ-17, DDD-ValueObject | `Money` | Model Money as immutable value object (no identity) | data props on a value class | low |
| 2 | Composition | architectural | DDD-BoundedContext, HEX | Billing / Catalog | Split into two bounded contexts; relate via published IDs | two component groups + cross-context object prop | high — reshapes the whole map |
| 3 | Behaviour | structural | DMN, FEEL-interval | `RiskScore` | Express risk scoring as a DMN decision table (hit policy U) | dmn:DecisionTable | medium |

Then a per-finding detail block for the top 15 (or all if `--full`):

```
### Finding 2 — Split Billing and Catalog into bounded contexts
Axis: Composition • Depth: architectural • Anchors: DDD-BoundedContext, HEX • Element: Billing / Catalog
Blueprint anchor: §4.relationship-map → cross-context seam.

Current reading: the idea text uses "Product" to mean both the sellable catalog item
and the billed line item. Per DDD bounded contexts, these are two concepts that share
a name, not one concept. Fusing them couples pricing changes to catalog changes.

Proposed model:
- Component group `catalog`: Product (name, description, sku).
- Component group `billing`: LineItem (quantity, unitPriceAtSale — a value, frozen).
- Cross-context object property: billing:LineItem --refersToProduct--> catalog:Product
  (by published ID, not a shared object).

KE form: two data-component groups in the HTML; one cross-group object property with
explicit domain/range. Each group is independently extractable as a subcomponent.
Abstraction cost: one indirection (ID lookup) across the seam.
Risk: reshapes the relationship map; affects every relationship currently touching "Product".
```

If the extractor returns 0 findings, say so plainly. Don't manufacture findings.

If `findings.json` has a non-empty `deferred` array (e.g. `reason="needs --layers dmn"` or `reason="defer to /architect once code exists"`), render it as a short section after the detail blocks.

### Step 4b — Paradigm-fit review (gates rule/decision findings)

Anchored to the Knowledge Engineering course feedback (Hinkelmann, FHNW — see `references/paradigm-fit.md`). For every finding whose `axis = behaviour` or whose `ke_form` references decision/rule logic (`dmn:DecisionTable`, `owl:Class with SWRL rule`, `Horn clause`, ...) — that is, any finding that proposes content for the `dmn`, `rules`, or `swrl` layers — render an extra **Paradigm-fit panel** immediately under the finding's detail block: the finding's `paradigm_fit` block (six axes — state, goal direction, monotonicity, cross-record reasoning, result cardinality, external access — plus the recommended paradigm and a one-sentence reason), rendered verbatim in the shape `references/paradigm-fit.md` § *What to emit* prescribes, followed by one fixed line: *"If the proposed layer does not match the recommended paradigm, the finding will be rejected at apply time unless reshaped to fit — run the matching checklist in `references/ke-vocabulary.md` (DMN design checklist / SWRL semantics / Property placement) before opt-in."*

This panel is rendered *before* Step 5 selection. A user who picks a finding whose proposed paradigm doesn't match the recommended one sees the mismatch and either (a) reshapes the finding (e.g. moves cross-record logic out of DMN and into a Prolog rule), (b) skips it, or (c) accepts the mismatch explicitly — in which case Step 6 records the override in the decision commit file. **Never silently apply a finding whose paradigm doesn't match.**

If the extractor's `findings.json` already includes a `paradigm_fit` block per finding (recommended; the extractor agent is instructed to populate it from `references/paradigm-fit.md`), use that block verbatim and add only a one-line orchestrator note if the proposed layer disagrees with the recommendation.

### Step 5 — Take selection

Ask which findings to apply. Accept numeric IDs (`apply 1, 3`), ranges (`apply 1-5`), filters (`apply axis=model depth!=architectural`, `apply all structural`), and free-form (`everything except 2`).

**For every selected finding with depth=architectural, require a separate explicit confirmation per finding.** Architectural-depth findings reshape the model's boundaries (bounded-context splits, identity/value reclassification of a widely-referenced concept, hierarchy restructuring) and are not authorized by list inclusion. Phrase it:

> Finding N is architectural depth — it reshapes X (the relationship map / a bounded-context boundary). The blueprint's §Y covers the target shape. Confirm apply? (yes / skip / show blueprint section first)

If `--report-only` / `--blueprint-only` / `--findings-only`: skip to Step 7 + 8.

### Step 6 — Apply, per finding

This skill's "apply" means **writing or editing the output HTML so its embedded Turtle and its `data-*` DOM stay in sync.** Read `references/html-contract.md` once at the start of the apply phase — it defines the exact file shape, the Turtle block, the DOM tagging, and the component-grouping rules. Read `assets/template.html` when creating a fresh file.

What the apply phase must produce for a *runnable* model — the `drd` graph that turns DMN tables into a complete Decision Requirements Diagram with an end-to-end tester, and the A-box individuals that light up the unified knowledge graph, the SPARQL runner and the reasoner overlay — is specified once, in `references/html-contract.md` § *Apply-phase guidance: runnable DMN and knowledge-graph layers*. Two rules of thumb survive here because they change what you ask the extractor for: a multi-step decision is worth a `drd` (without it the Test view degrades to per-table evaluation), and a handful of representative individuals per key class is high-value whenever the domain offers concrete examples (without them the KG controls stay hidden). Validator invariants 10 and 17–19 check both.

For each selected finding, in order of ID:

1. **If depth=architectural, write the decision commit file FIRST.** Before editing the HTML, write `.claude/domain-forge-decisions/<UTC-timestamp>-finding-<N>.md` containing the finding's full detail block + the relevant blueprint excerpt. This captures the modeling commitment even if the edit bails halfway. Tell the user the path.
2. Apply the change to the HTML: update the canonical Turtle block, then update/add the matching `data-*` DOM node(s) and SVG connector(s). **Each finding is its own change set** — do not bundle.
3. **Verify** by running the validator (the analog of `/architect`'s test run):
   ```
   python <skill-dir>/scripts/validate_model.py <output.html>
   ```
   It checks (invariants 1–19): Turtle parses; every object and data property declares a domain and range pointing to declared classes / datatypes; subClassOf is acyclic; the JSON-LD mirror carries the same classes as the Turtle (the runtime renders from the mirror, so a drift here is a diagram that lies); every class carries `ex:component` and each component is independently extractable; the file is self-contained; DMN tables declare a hit policy and well-formed FEEL cells; Horn clauses are well-formed over declared predicates; the projectors round-trip; the KG runtimes mount and function when there is an A-box; and, when the file carries `@LAYER` blocks, that the layers are well-formed, stamped against the current Turtle, write into no earlier data block, and render independently (13–16).
4. If validation passes → mark applied. A finding counts as *applied* only with a passing validation behind it.
5. If validation fails → surface the exact failure. Offer: (a) revert this finding, (b) propose a fix-up edit (you propose; user approves), (c) keep the edit on disk, listed under **Failed** (not Applied), for manual review — in which case the summary says the file does not currently validate and names the last file that did. Wait.
6. If the change touches far more of the model than the finding's stated element (e.g. a "rename one class" finding ends up rewriting half the relationships), pause and confirm before continuing.
7. **If 2 consecutive validations fail**, pause regardless.

#### Step 6b — Component-refinement mode (`--component <id>`)

When invoked with `--component`, the goal is to deepen **one self-contained subcomponent** — the primary downstream use case. Procedure:

1. Run `python <skill-dir>/scripts/extract_component.py <input.html> --component <id> --out <tmp>.html` to lift that entity-cluster out as a *standalone, still-valid domain-forge file* carrying its own IRIs, types, and the domain/range of every relationship that touches it. This is what a later, more specific skill run would consume.
2. Apply the selected findings to the lifted subcomponent file (Steps 6.1–6.7 against `<tmp>.html`).
3. Merge the refined subcomponent back into the parent model (update the parent's Turtle for that component group + re-render its DOM nodes), or, if the user prefers, leave the standalone subcomponent file as the deliverable for the downstream run. Ask which.
4. Validate the merged parent.

Never auto-commit. If the project is a git repo, you may `git add` the changed HTML; otherwise leave it on disk and note so.

### Step 7 — Update project memory

Update `.claude/domain-forge-memory.md`:
- Applied findings → **Applied** section: `YYYY-MM-DD | <anchors> | element | depth | one-line title`.
- Declined → **Declined** with reason.
- Modeling stances expressed during the run ("identifiers are value objects", "billing and catalog are separate contexts", "we don't model the payment gateway, it's external") → **Modeling stances**.
- Each architectural-depth finding → a one-paragraph **Decision** entry citing its commit file.
- Stable IRIs the user named → **Naming conventions** so they are never silently renamed.
- Concepts the user said not to model ("the payment gateway is external") → **Out-of-scope**, with the reason, so the extractor never re-proposes them.

Keep entries terse.

### Step 8 — Final summary

```
## /domain-forge summary (run <UTC-timestamp>)

Model: <path/to/output.html>   (open in a browser to view the diagram)
Canonical Turtle: embedded in the file + <run-dir>/model.ttl
Blueprint: <path/to/blueprint.md>
Decisions committed: list of .claude/domain-forge-decisions/*.md (one per architectural-depth applied)

Layers populated: ontology [+ dmn] [+ rules] [+ swrl]
Entities: N classes, M individuals • Relationships: K object properties, L data properties
Components (addressable subparts): <list of data-component group ids>

Applied (N): every one validated
Deferred (M): declined IDs with reasons
Failed (K): reverted, or kept on disk for review — with failure reason; if any is kept, the file does not validate and <last validated file> is the deliverable

Memory updated: .claude/domain-forge-memory.md

Suggested next pass: <e.g. "/domain-forge model.html --component billing --layers dmn to deepen
the billing decisions" or "/architect once the code skeleton exists">
```

Stop after the summary. Do not loop into another extraction unless asked.

## Optional capabilities (off the main spine)

Two capabilities live outside Steps 1–8 and are documented in `references/optional-capabilities.md`; read it only when triggered. **Submission bundle** — on an explicit request for a bundle, a submission, a `.dmn` / `.pl` file, or a named milestone: `python <skill-dir>/scripts/bundle.py <output.html> --out <bundle-dir> [--zip <bundle.zip>]` writes `model.ttl`, `model.dmn`, `model.pl`, the composed HTML and a `MANIFEST.md`; the written report is `/document-project`'s job, never `bundle.py`'s. **Engine capability viewers** — when a user asks what the reasoner does, suspects an inference, or wants to extend the engine: the decomposed per-capability source and viewers under `assets/engine-source/` (contract in its `README.md`). Never run either preemptively.

## Failure modes — DO NOT

- **Don't load the KE vocabulary, the Bloch→modeling mapping, or the HTML contract into your own context for analysis.** Extraction and the modeling vocabulary belong to the subagent; the HTML contract you read once at the apply phase. Orchestration, rendering, apply/validate, commits, memory are your job. Keeping the analytic vocabulary out of the orchestrator is the whole point of the hybrid.
- **Don't produce a syntactical model (class code, SQL DDL) as the deliverable.** The deliverable is the visual HTML; code-shaped output belongs to a downstream skill. The model is language-agnostic and visual-first by mandate.
- **Don't let the Turtle and the DOM drift.** The Turtle is the source of truth; the `data-*` DOM is rendered from it. Every apply edits both, and a finding is applied only when the validator passes. A diagram that disagrees with its own embedded model is worse than no diagram.
- **Don't drop component grouping.** Every entity must carry a `data-component`, and each component must remain independently extractable — that is what makes subcomponent refinement (the primary downstream use) possible. Test it with `extract_component.py`.
- **Don't populate the `dmn`, `rules`, or `swrl` layers unless requested** via `--layers`. They are gated depth; an unrequested DMN table or rule is noise.
- **Don't apply architectural-depth findings without per-finding explicit opt-in**, and **don't apply one without writing its decision commit file first.**
- **Don't bundle multiple findings into one HTML edit.** One finding, one change set, one validation.
- **Don't auto-commit to git.** Stage only.
- **Don't paraphrase the extractor's §1/§2.** Render verbatim.
- **Don't invent entities the idea text does not support.** If the idea is thin, say so and ask the user for the missing domain facts rather than fabricating a plausible-looking model. A confidently wrong model is the worst outcome.
- **Don't ship a terse summary as the model's textual description.** The `model-markdown` block is the page's **headline Abstract** — rendered always-visible at the top of the document, above the diagram and every tab, and it is the single most agent- and human-readable surface in the file. Write a **detailed textual description** (paper-style abstract + introduction): purpose & scope, each component, the load-bearing modeling decisions and *why*, which knowledge layers are used and the expressivity limit behind each choice, and the open questions — so that reading the description **alone** conveys the model and its reasoning (Hinkelmann M1). A one-line summary wastes that surface; see the extractor brief and `references/html-contract.md` for the shape.
- **Don't proceed past a validation failure without user direction.**
- **Don't refine a layered file in place, and don't leave its layers silently stale.** A file with `@LAYER` blocks is a chain node: output to a new path, and either strip-and-regenerate the layers or, for add-only findings, re-stamp with `apply_layer.py <out.html> --restamp --in-place` and say so (Step 2, *Layered input*). An invariant-14 failure in the deliverable means a downstream tab is lying about the model beneath it.
- **Don't re-model a dataset ontology as software.** When the source kind is `dataset-ontology` (a `/dataset-forge` file), `Record` with one data property per column is the design; value-object, bounded-context and "split this class" findings are noise there. The extractor is told the source kind — if it proposes them anyway, drop them before rendering the findings table and say why.
- **Don't carry a private copy of the layer tools.** `apply_layer.py`, `strip_layer.py` and `run_query.py` in this skill's `scripts/` are the platform's; a chain skill or forge that needs them imports or invokes these paths. Two copies drift, and the digest algorithm must be one.
- **Don't propose findings whose value depends on inference the reasoner doesn't perform.** The reasoner's exact scope is in `references/ke-vocabulary.md § Reasoner capabilities`. In particular: no domain/range entailment, no restriction-based classification (`someValuesFrom` / `allValuesFrom` / cardinality), no anonymous class expressions (`unionOf` / `intersectionOf`), no property chains, no datatype facets. Findings of the form "classify X via restriction Y" should be reshaped as Horn or SWRL rules with explicit patterns. The disjointness, Functional, and InverseFunctional axioms **are** enforced by the consistency pass — findings that lean on them are safe and the user will see a Contradictions card in the Logic tab when something later violates them.

## Memory file template

When `.claude/domain-forge-memory.md` is missing, create it from `references/memory-template.md` verbatim (sections: Modeling stances, Naming conventions, Decisions, Applied, Declined, Out-of-scope, Dataset stances — the last one is written by `/dataset-forge` and read by both forges).

## Stop criteria

Done when: all selected findings are processed (applied+validated, failed+handled, or skipped per opt-in) AND memory is updated AND the summary is emitted. For `--report-only`: done after blueprint + findings + a memory note. For `--blueprint-only` / `--findings-only`: done after that half + memory note.
