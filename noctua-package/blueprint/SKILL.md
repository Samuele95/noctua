---
name: blueprint
description: >-
  First-architecture proposal pass for a greenfield project — ingest a spec-analysis HTML or a
  domain-forge model, derive a proposed architectural style and world model plus ranked design
  findings, every claim traced to the spec or stamped as a designer's choice. With a DATASET
  model (/dataset-forge, /data-lens, /dataset-shaper HTML) it proposes the data / ML pipeline
  the geometry, analysis and recipe imply (--mode pipeline). Trigger when the user runs
  /blueprint, asks to propose a first architecture from a spec, choose between monolithic /
  microservices / layered / event-driven / distributed styles for a new system, design something
  not yet built, turn a spec, domain model or dataset model into a buildable blueprint, or
  scaffold the module / boundary / paradigm shape of a new system before code exists. Anchored
  to Bloch's Effective Java plus SOLID, GoF, FP, DDD and Hexagonal Architecture. Sibling to
  /architect — /architect reshapes an EXISTING codebase; /blueprint proposes the FIRST one.
---

# /blueprint

A first-architecture proposal pass for a system that does **not yet have code**. Same three axes as `/architect` — **Model / Abstraction / Composition** — anchored to *Effective Java* (Bloch, 3rd ed.) supplemented by SOLID, GoF, FP, DDD, and Hexagonal Architecture. Where `/architect` audits what the code *is*, `/blueprint` proposes what the code *should be*, derived from a prose spec or a domain model.

## Anchor corpus (single source of truth)

The EJ anchor set is **deliberately scoped** to the same 43 items as `/architect` — the items whose frontmatter `sets:` contains `architect` in the `effective-java` skill's corpus (`items/EJ-N.md`; verify: `grep -lE 'sets:.*architect' items/EJ-*.md` → 43). `blueprint` owns no corpus of its own — it inherits the architect set. That `effective-java` directory is the single source of truth (full per-item guidance + verbatim titles + the per-item "anchor must justify" clause); do **not** maintain a second copy here (drift between two copies is a defect). When you need the corpus for a breadth read, dispatch a sub-agent that loads the relevant `items/EJ-N.md` files — do not inline them into your own context. **Do not anchor a finding to an EJ item outside that 43-item set**; if no listed item fits, anchor to SOLID / GoF / FP / DDD / HEX / CQRS / MEASURED-PERF and say so in the `rationale`. Source PDF: `~/Documenti/Effective Java (2017, Addison-Wesley).pdf`.

The procedure is human-in-the-loop and multi-turn: **ingest → derive the architectural style → derive the world model → gate the structural bets → emit architect-compatible artifacts.** Big structural decisions (the architectural style, the decomposition, the paradigm per subsystem, the bounded contexts) are surfaced one per turn for your approval. Tactical calls — naming, field types, which GoF pattern inside a settled boundary — the skill makes itself.

Because there is no code to verify against, the skill's discipline is the **trace-to-spec invariant**: every design claim either cites the spec/model section it derives from, or is stamped `[DESIGNER'S CHOICE — pressure]` with the design pressure that justifies it. A claim that is neither is a hallucination and must not ship.

## Relationship to the family

- `/spec-analysis` produces the prose spec (`spec-analysis.html`) — a common **input** to this skill (for a `data-project`, the spec of the code around the data).
- `/domain-forge` produces the formal domain model (`model.html`) — the other accepted input.
- `/dataset-forge`, `/data-lens` and `/dataset-shaper` produce a **dataset model** (`ex:sourceKind "dataset"` with `geometry`, `analysis`, `shape` layers) — the third accepted input, handled in `--mode pipeline` (see *Dataset models* below).
- `/blueprint` (this skill) turns any of them into a **proposed** architecture: `blueprint.md` + `findings.json` + a self-contained `blueprint.html`.
- `/architect` later reshapes the **built** code — and can diff it against this skill's `blueprint.md` as the intended baseline.
- `/noctua` schedules this skill as the `blueprint` stage of every lane and passes `--mode`.

Position in the chain: `/spec-analysis → /domain-forge → /blueprint → (build) → /architect`, and on the data lane `/dataset-forge → /data-lens → /dataset-shaper → /blueprint --mode pipeline → (build) → /architect`.

## Trigger

User invokes:

- `/blueprint` — auto-detect the input artifact in the cwd (spec-analysis HTML or domain-forge model); propose a whole-system architecture.
- `/blueprint <path>` — point at a specific spec-analysis HTML or domain-forge model file.
- `/blueprint --concern "<text>"` — focused lens (e.g., `--concern "propose the audio-pipeline decomposition only"`).
- `/blueprint --axis model|abstraction|composition` — single-axis proposal.
- `/blueprint --blueprint-only` — world-model blueprint, skip the ranked findings.
- `/blueprint --findings-only` — ranked design findings, skip the blueprint prose.
- `/blueprint --report-only` — derive + render artifacts, skip the interactive gating turns (one-shot; you review the finished blueprint).
- `/blueprint --mode system|pipeline` — `system` (default for prose specs and software models) proposes the software system; `pipeline` (default for a dataset model, allowed for a `data-project` spec) proposes the data / ML pipeline that consumes the dataset.

Args may combine.

## Procedure

### Step 1 — Ingest and classify the input

Locate the input artifact (from `<path>` or by scanning the cwd for `spec-analysis*.html`, `model.html`, or a domain-forge HTML). Classify it:

- **Prose spec** (`spec-analysis.html` or any prose description) → you derive entities, boundaries, and flows from prose. Lower structural fidelity; more designer inference.
- **Domain model** (`domain-forge model.html`, with embedded Turtle / `data-*` nodes) → entities, relationships, and constraints are already formalized. Higher fidelity; your job is the *architecture over* the model, not re-deriving it.
- **Both present** → prefer the domain model for entity/relationship grounding, use the prose spec for behavior, flows, and business rules. Note which artifact grounds which claim.
- **Dataset model** (a domain-forge HTML whose Turtle carries `ex:sourceKind "dataset"`, listed by `python3 <domain-forge>/scripts/strip_layer.py <file> --list` as carrying `geometry`, and possibly `analysis` and `shape`) → `--mode pipeline`. The entities are *not* the software's: the `Record` class and its properties describe the data; the system to design is the one that ingests, shapes, trains on and serves that data. See *Dataset models* below. A `data-project` spec-analysis alongside it grounds the existing flows; the dataset model grounds the data.

If no recognized artifact is found, say so and ask for a path or a prose description. Do **not** invent a spec.

#### Dataset models (`--mode pipeline`)

Read, and cite by tag, the three layers' data scripts — never the rendered prose alone:

- `geometry` (`layer-geometry-data`): `typing` (roles), `basis`, `derivations` and `cycles` with the active orientation, the chosen partition (`partitions.chosen` is a label; `features`, `dropped_for_leakage`, `input_dim`, `task` are on the `partitions.candidates[]` entry with that label); `disagreements`; `space` and `source.rows`. Tags use the layer's key names: `[geometry:basis]`, `[geometry:derivations/total]`, `[geometry:partitions/late]`, `[geometry:cycles/price-qty-total]`.
- `analysis` (`layer-analysis-data`, when present): `findings[]` with `severity` and `so_what`, `context.time`, `context.spatial`, `modules.drift`, `modules.importance` (learnability, importance, leakage probe). Tags: `[analysis:F3]`, `[analysis:importance]`, `[analysis:context.time]`.
- `shape` (`layer-shape-data`, when present): `recipe.steps[]` by phase, `manifest` (`fit_on`, fitted parameters), `verification`. Tags: `[shape:S6]`, `[shape:phase/split]`, `[shape:manifest]`.

The world model of a pipeline (Step 2) is: the **data contract** at each boundary (raw → typed → shaped → features → predictions; the shaped schema in `shape.manifest` *is* the feature contract), the **stages** (ingestion, validation against the quality findings, the recipe's phases as transformation stages, training on the partition, evaluation with the CV protocol the analysis used, serving, monitoring for the drift the analysis measured), and the **artifacts** (the recipe, the fitted parameters, the model, the metrics) as value objects with versions. The style axes (Step 2.5) read: *distribution* — a script, a scheduled pipeline, a service (forces: data volume from `geometry.source.rows`, latency of the use the user states); *internal* — ports for the data source, the feature transformer (the recipe as the one implementation), the model, the store; *interaction* — batch, streaming, online inference (forces: `context.time` regularity, the split kind `shape:phase/split`); *data* — files, warehouse, feature store, model registry (forces: reproducibility from `shape.manifest`, the drift findings). The **model-family posture** (linear / tree / neural / none yet) is a Structural bet derived from `[geometry:partitions/<label>]` (task, `input_dim`), `[analysis:importance]` (learnability, which features carry it) and `[analysis:*]` on distributions — it is a *posture with forces*, never a training decision or a performance claim. **Monitoring** derives from the analysis's drift and quality findings: what to watch is what was found fragile.

Anchors keep their corpus: the EJ items apply to the pipeline's code (immutability of the feature contract, the recipe as a value object, builders for configuration, no leaking of fitted state), and where no item fits, SOLID / HEX / CQRS / MEASURED-PERF as today. `location` accepts the three new tag families beside `spec §` and `model:`.

State in your first status line: which artifact(s) you ingested, their classification, and (for prose) the inherent inference risk.

### Step 2 — Derive the candidate world model (internal)

Read the spec/model and build, in your own working notes, a first-pass model along the three axes:

- **Model** — entities (identity + lifecycle), value objects (equality by value), aggregates, bounded contexts. For a domain-forge input, lift these from the model; for prose, extract them and mark each with its source span.
- **Abstraction** — the ports/interfaces the system needs, where the abstraction surface should be widest, where concrete implementation grounds execution.
- **Composition** — module map, dependency direction, paradigm per subsystem (OOP for stateful identity, FP for transformation), where hexagonal/ports-and-adapters earns its indirection.

Every line you write here carries a tag: `[spec §X]`, `[model:Entity]`, or `[DESIGNER'S CHOICE — pressure]`. This tagging is not cosmetic; it is the input to the gate in Step 4 and the final artifact's honesty.

For a heavy spec, dispatch an `Explore` or `general-purpose` sub-agent scoped to reading the artifact and returning the extracted entity/flow inventory — keep only its conclusion in your context.

### Step 2.5 — Derive the architectural style (multi-axis)

Before any decomposition, fix the system's architectural style — but **not** as a single label off a menu. A style is a **point across independent axes**; pick a coherent combination, each axis driven by a force the spec actually exhibits. "We'll use microservices" with no per-axis force is the cardinal failure of this step.

The axes (vocabulary, not a rigid checklist — add an axis a spec demands, drop one it doesn't exercise):

- **Distribution** — single process → modular monolith → service-oriented → microservices. Selected by: independent scaling needs, deploy-boundary / team-boundary pressure, failure-isolation requirements.
- **Internal dependency** — layered (n-tier) / hexagonal (ports-and-adapters) / clean / pipes-and-filters. Selected by: how many implementations of a port the spec implies (swappable backends → hexagonal earns its indirection), testability demands.
- **Interaction** — request-response / event-driven / streaming / batch. Selected by: latency tolerance, long-running async work, fan-out, ordering and delivery guarantees the spec states.
- **Data** — shared database / database-per-service / CQRS / event-sourced. Selected by: consistency-vs-availability needs, multi-tenancy, audit/history requirements, read/write asymmetry.

For each axis, write the chosen point and either the **spec force** that drives it (`[spec §X]` / `[model:Y]`), or `[DESIGNER'S CHOICE — pressure]` when the spec is silent and you're committing on a design pressure (e.g. "no multi-tenant requirement stated yet → shared DB, revisit if tenancy lands").

Then **check coherence**: the combination must hold together. Flag tensions explicitly — e.g. "microservices distribution + shared-DB data" is the distributed-monolith anti-pattern; surface it rather than emit it silently. The output is one coherent style-point plus the forces that justify each axis.

For a heavy spec, this can ride the same scoped sub-agent read as Step 2.

### Step 3 — Identify the structural bets

If `--axis model|abstraction|composition` was passed, scope Steps 2–5 to that single axis — derive, gate, and emit findings only for it (style bet 0 still runs, since every axis lives inside the chosen style). If `--concern "<text>"` was passed, bias the lens of Steps 2–5 toward that concern and note it in §1.

From the candidate model and the style-point, list the **structural decisions** — the choices that, if wrong, invalidate large parts of the blueprint. The architectural style from Step 2.5 is **Structural bet 0** and is gated **first**: §3 ports, §4 module map, and §6 perf posture all derive from it, and the decomposition only has meaning *inside* the chosen style. The rest typically:

- **Bet 0** — the architectural style (the multi-axis point).
- **Bet 1** — the top-level decomposition (services / modules / bounded contexts), *inside* the chosen style. In `--mode pipeline`: the stage decomposition and where the recipe's phases fall.
- **Bet 2** — the paradigm assignment per subsystem. In `--mode pipeline`: also the model-family posture.
- **Bet 3** — the hard boundaries (anti-corruption layers, ports). In `--mode pipeline`: the feature contract (the shaped schema) and the monitoring boundary.
- plus any decision the spec underdetermines and you had to invent.

These are what you gate. Everything else (naming, field types, intra-boundary pattern choice) you decide yourself and note as tactical.

### Step 4 — Gate the structural bets, one per turn

This is the human-in-the-loop core. For each structural bet, in dependency order **starting with bet 0**:

1. Surface it as a **decision**, not a fait accompli: state the proposal, the spec/model evidence behind it, the designer's-choice elements, and 2–3 alternatives with trade-offs.
2. Recommend one. Lead with the evidence, not the conclusion.
3. Wait for approval, redirection, or a redraw of the boundary.
4. Record the resolved decision (and any stance the user expressed) before moving to the next bet.

Gate bet 0 per-axis, because that is where the leverage and the trade-offs live:

> **Structural bet 0 — architectural style.** I propose: distribution = `<X>` [spec §A]; internal = `<Y>` [spec §B]; interaction = `<Z>` [DESIGNER'S CHOICE — pressure]; data = `<W>` [model:C]. Coherence: `<holds / named tension>`. Alternatives on the axis that matters most: `<A>` (trade-off), `<B>` (trade-off). I recommend this combination because `<evidence>`. Approve, change an axis, or redraw?

Subsequent bets are framed *inside* the approved style:

> **Structural bet N — <name>.** I propose <X>, derived from <spec §Y / model:Z>; the <W> part is a designer's choice driven by <pressure>. Alternatives: <A> (trade-off), <B> (trade-off). I recommend <X> because <evidence>. Approve, pick another, or redraw?

If `--report-only` was passed, skip the gating turns: make each call yourself, stamp it, surface all of them together in the final artifact for post-hoc review, and note in the summary that gates were auto-resolved.

One structural decision per turn. Do not batch the big bets — batching is what produces a whole blueprint built on a wrong early call that the user then has to reject wholesale.

### Step 5 — Compose the blueprint and findings

Once the structural bets are resolved, write the two artifacts to a run directory `blueprint-runs/<UTC-timestamp>/`:

**`blueprint.md`** — same section shape as the `/architect` auditor's output, so a later `/architect` run can diff against it. Sections, in order:

- **§0 Architectural style** — the multi-axis style-point, each axis with its trace tag and the coherence check. Precedes everything; it is the topology the eventual code was *supposed* to inhabit.
- **§1 Domain & spec basis** — what the system is, which input artifact(s) ground it, the inherent inference risk. (Replaces architect's "current world-model assessment" — there is no current code, so this grounds in the spec instead.)
- **§2 Proposed world model** — entities, value objects, aggregates, bounded contexts. **Every item carries its trace tag.** This is the load-bearing section and the design baseline.
- **§3 Proposed interfaces / ports** — the abstraction surface.
- **§4 Module map** — modules, dependency direction, paradigm per subsystem (the style of §0 made concrete).
- **§5 Abstraction inventory** — where abstraction is widest, where concrete grounds it, the concrete-to-abstract intent.
- **§6 Performance posture** — the cost of each proposed abstraction, flagged explicitly; in-process vs network-hop costs follow from §0's distribution axis.
- **§7 Designer's-choice ledger** — every `[DESIGNER'S CHOICE]` collected in one place with its justifying pressure, so the user sees exactly what was invented beyond the spec.
- **§8 Risk register & open questions** — what the spec couldn't resolve.

**`findings.json`** — ranked **design proposals** (not audit findings), using the **same field names** architect-auditor emits so a later `/architect` run can diff against them. Each finding carries, with names matching the auditor exactly:

- `id`, `axis`, `anchors`, `anchor_justification` (one clause per anchor — see the load-bearing rule below), `title`, `rationale` (the prose argument — this is where each anchor's principle does its load-bearing work, same field the auditor uses), `proposed_change` (NOT `proposal`), `abstraction_cost`, `performance_implication`, `impact`, `risk`, `effort_estimate_min` (NOT `effort`), `leverage_score`, `blueprint_anchor` (the `§N.section` it links to — the same field the auditor uses).
- `depth` — `structural | architectural` only. **Documented divergence:** the auditor also allows `surface`; `/blueprint` omits it because surface-depth findings require existing code to be tactical against.

Two greenfield-specific field semantics, **documented as intentional divergences** (not silent drift) so the downstream diff still resolves:

- `location` → carries the **spec/model span** the finding derives from (e.g. `spec §3.2` or `model:Segment`) instead of a `file:line`, since no code exists. This doubles as the trace tag: it is either a spec/model citation **or** the literal `DESIGNER'S CHOICE: <pressure>`.
- `concrete_reduction_loc` → set to `null` (no code to reduce). The auditor treats it as an integer; `null` is the explicit "not applicable pre-code" signal, and `leverage_score` must be computed without it.

Rank by must / should / could.

**The anchor must be load-bearing, not decorative** (inherited hard from `/architect`'s auditor): the EJ anchor must come from the 43-item grounded corpus (see **Anchor corpus** above), and each anchor's `anchor_justification` must name what *that specific item's principle predicts here* — ideally echoing the corpus table's "anchor must justify" clause for that item — such that swapping a different anchor would change the reasoning. Test: if the proposal would read identically with the anchor deleted, the anchor is decoration — find the one that actually drove the design, or drop it. A bare anchor tag, or one citing an EJ item outside the corpus, is an incomplete finding.

Restate §0, §1, and §2 inline in chat **verbatim** after writing — they are the load-bearing framing the user must see.

### Step 6 — Render the HTML

Produce a single self-contained `blueprint.html` in the run directory, matching the prose-first, scrollable, offline style of the existing `spec-analysis.html` artifacts: no external scripts, no network deps. It contains the blueprint sections as connected prose, the ranked-findings scorecard (anchors rendered **with** their justification clause, never bare), the architectural-style axis table, and the designer's-choice ledger as a callout. End with a MD + JSON export of the underlying artifacts.

### Step 7 — Final summary

```
## /blueprint summary (run <UTC-timestamp>)

Input ingested: <artifact path(s)> (<prose | model | dataset model | both>) — mode <system | pipeline>
Artifacts: blueprint.md • findings.json • blueprint.html  (paths)

Architectural style: <distribution / internal / interaction / data> — coherence <holds | tension noted>
Structural bets resolved (N): list with the chosen option
Designer's choices (M): count — full ledger in §7
Open questions (K): count — see §8

Trace integrity: every §2 entity, every style axis, and every finding carries a
spec/model citation or a DESIGNER'S-CHOICE stamp. <PASS | list any unstamped>
Anchor integrity: every finding anchor carries a load-bearing justification clause. <PASS | list bare anchors>

Suggested next step: build against this baseline, then run /architect on the
code to diff it against blueprint.md §0 (style) and §2 (world model).
```

## Failure modes — DO NOT

- **Don't pick an architectural style by fashion or single label.** Style is a coherent multi-axis point, each axis traced to a spec force or stamped a designer's choice. A flat "we'll use microservices" with no per-axis force is the cardinal failure of Step 2.5. And never emit an incoherent combination (e.g. distributed monolith) without flagging it.
- **Don't present a designer's choice as a spec derivation.** If the spec doesn't say it, it is `[DESIGNER'S CHOICE]` with a named pressure — never silently promoted to "the spec requires." Greenfield's whole failure mode is confident invention.
- **Don't ship a decorative anchor.** Each finding anchor must carry a justification clause naming what its principle predicts here. If the proposal reads identically with the anchor removed, the anchor is decoration — fix or drop it.
- **Don't batch the structural bets.** One per turn, gated, starting with bet 0. A blueprint built on a wrong unreviewed early call wastes the run.
- **Don't invent a spec.** No recognized input artifact → ask, don't fabricate.
- **Don't re-derive a domain-forge model from scratch.** When a formal model is the input, lift its entities and relationships; your job is the architecture over them, not re-modeling.
- **Don't drift the artifact schema.** `blueprint.md` and `findings.json` must stay diff-compatible with `/architect`'s output, or the downstream chain breaks.
- **Don't load the Bloch corpus into your own context for breadth-reads — dispatch a sub-agent.** Keep the orchestrator lean, same as `/architect`.
- **Don't one-shot the HTML before §0/§1/§2 are approved** (except under `--report-only`).
- **Don't claim performance numbers.** With no code, perf posture is *intent and cost-flagging* derived from the §0 distribution axis, not measurement. Label it as such.
- **Don't re-analyse the dataset in `--mode pipeline`.** The basis, the partition, the findings and the recipe are the layers' — cite them by tag. A blueprint that recomputes a correlation or picks a label the geometry did not is inventing a spec. And don't turn the model-family posture into a promise: it is a bet with forces, gated like the others, and the first training run is what settles it.

## Stop criteria

The command is done when:
1. All structural bets (style + decomposition + paradigm + boundaries) are resolved (gated, or auto-resolved under `--report-only`), AND
2. The three artifacts are written and §0/§1/§2 restated verbatim in chat, AND
3. Final summary emitted with trace-integrity and anchor-integrity checks.

For `--blueprint-only`: done after the blueprint + HTML, no findings phase.
For `--findings-only`: done after ranked findings, no blueprint prose.
For `--report-only`: done after artifacts rendered + a note that gates were auto-resolved.
For `--axis`: done when the single named axis is derived, gated (after bet 0), and emitted; other axes are explicitly skipped in the summary.
For `--concern`: the full flow runs, lensed to the concern, which is named in §1 and the summary.
