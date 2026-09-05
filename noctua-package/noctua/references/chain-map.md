# Noctua chain map — sources, stages, artifacts, gates

This is the routing table `/noctua` reads. One row per stage: what it consumes, what it produces, how the orchestrator checks the product, and whether the stage stops for a human. The orchestrator never restates a stage's procedure — it invokes the stage's skill and checks the artifact against this table.

## Source kinds

Noctua classifies what it finds at the project root (or at the path given) into one or more **sources**. A project can have several; each opens its own lane, and lanes meet at the model.

| kind | recognised by | first stage |
|---|---|---|
| `codebase` | source files with an entry point (build manifest, `main`, server bootstrap) and no dataset | `spec-analysis` |
| `data-project` | notebooks, ETL / pipeline code, DAG definitions, SQL migrations alongside data files | `spec-analysis --kind data-project` (the code) and `dataset-forge` (each dataset) |
| `database` | DDL / schema files, ORM models, migrations, or a connection string the user gives | `spec-analysis --kind database` |
| `prose` | `.md` / `.txt` notes, an idea typed by the user, an existing `spec-analysis*.html` | `domain-forge` |
| `dataset` | `.csv .tsv .parquet .xlsx .json .jsonl` with tabular content | `dataset-forge` |
| `model` | an HTML with `<script id="domain-model" type="text/turtle">`; its `ex:sourceKind` and its layers (`strip_layer.py --list`) say where it is in a lane | the next stage its layers imply (below) |
| `blueprint` | a `blueprint-runs/<ts>/` directory with `blueprint.md` + `findings.json` | `architect` once code exists, or `document-project` |

## Stages

| stage | skill | consumes | produces | orchestrator's check | human gate (attended) | unattended behaviour | re-run |
|---|---|---|---|---|---|---|---|
| spec | `/spec-analysis [path] [--kind codebase\|data-project\|database] [--out …]` | codebase / data code / schema | `spec-analysis.html` (prose; no formal model) | file exists, self-contained (no external refs), the return summary carries a module map and one traced flow | none (one clarifying question only on an ambiguous monorepo) | `--unattended`: the largest coherent root is analysed and the choice stated | invoke again with a tighter scope |
| forge-prose | `/domain-forge <spec-analysis.html \| notes> [--layers …]` | prose | `<stem>.domain.html` | `validate_model.py` exit 0 | findings opt-in, architectural-depth confirmations | not run (announced as pending — the apply phase is an opt-in gate; `--report-only` produces no model) | pass the model path (refine) |
| forge-data | `/dataset-forge <dataset> [--partition …]` | dataset | `<stem>.domain.html` with `geometry` layer, memory § Dataset stances | `validate_model.py` exit 0 (13–16), `smoke_geometry.py` | `FORK:` on ≥ 2 label candidates | `--unattended`: partition `provenance: abstained`, ranked candidates | pass the model path (refine) |
| refine | `/domain-forge <model.html>` | any model | `<stem>.refined.html` (layers stripped-and-regenerated or `--restamp`) | `validate_model.py` exit 0, invariant 14 not failing | findings opt-in | not run (announced as pending) | pass the model path |
| lens | `/data-lens <model.html> [--dataset …]` | dataset model (+ dataset) | `<stem>.analysis.html` with `analysis` layer; memory § Analysis stances | `validate_model.py` exit 0, `smoke_analysis.py`; `handoff.shaper_candidates` present (may be empty) | step-2 `FORK:`s, then the dialogue loop (user-ended) | `--unattended` (+ `--questions <file>` if supplied): forks become open questions in `markers`, automatic pass only | `--continue` |
| shape | `/dataset-shaper <model.html> [--goal …] [--target …]` | model with `geometry` (+ `analysis`) | `<stem>.shaped.html` with `shape` layer; `shaped/` dataset + `recipe.json` + `manifest.json` + `lineage.json` + `reproduce_*.py`; memory § Shaping stances | `validate_model.py` exit 0, `shape.py --check` determinism pass, `verify_shape.py` structural pass | one `FORK:` per phase, batching that phase's steps with alternatives | `--unattended`: defaults applied and marked; CRS-less spatial steps skipped | `--recipe <edited recipe.json>` (a fork answered later comes back this way) |
| questions | `/inferred-questions <model.html>` | any model | `<stem>.questions.html` | `validate_model.py` exit 0 | none (status chips are set by the user in the page) | runs as is | `--regenerate` |
| chat | `/model-chat <model.html>` | any model | `<stem>.chat.html` | `validate_model.py` exit 0 | the session loop (user-ended) | `--questions <file>` only; otherwise not run | `--continue` |
| blueprint | `/blueprint <spec-analysis.html \| model.html> [--mode pipeline\|system]` | prose spec or model (software or dataset) | `blueprint-runs/<ts>/{blueprint.md, findings.json, blueprint.html}` | the three files exist; summary reports trace and anchor integrity PASS | structural bets, one per turn | `--report-only` (gates auto-resolved and stamped) | invoke again with `--concern` or a new input |
| document | `/document-project` | everything above | LaTeX / PDF | PDF compiles | chapter-by-chapter | not run (announced as pending) | chapter by chapter |

Stems follow the chain's append rule (`domain-forge/references/future-skills.md` § naming): `orders.csv` → `orders.domain.html` → `orders.domain.analysis.html` → `orders.domain.analysis.shaped.html`; a user-chosen `--out` is recorded in the ledger and routing reads the file's layers, never its name.

`architect`, `improve` and the sketched chain skills (`instance-create`, `code-implement`, `countergen`, `model-diff`) are **not** stages Noctua schedules: they are named in the summary as options when their input exists and the skill is installed, never invoked on its own initiative.

## Destinations — what the user may be after

Step 4 of the procedure reads this table and keeps the rows this project's state and environment allow. A destination is a place to stop, not a stage: it names the goal stage, the lane that reaches it, and — the column that keeps the choice honest — what it does **not** give you.

| the user wants | goal stage | runs | does not give you |
|---|---|---|---|
| to know where the project stands | none (`status`) | nothing | any new artifact |
| to understand a dataset before deciding anything | `lens` | `forge-data` → `lens` | transformed data, an architecture |
| a cleaned / training-ready dataset | `shape` | … → `lens` → `shape` | a trained model, a pipeline to run it in |
| the data / ML pipeline architecture | `blueprint --mode pipeline` | … → `shape` → `blueprint` | code, a deployment |
| to understand an existing codebase | `spec` | `spec` | a formal model, a refactor |
| a queryable domain model | `forge-prose` | `spec` → `forge-prose` | an architecture |
| an answer to one specific question, now | none — `/model-chat` or the `lens` dialogue | one loop, no lane advance | any lane progress (nothing is recorded as a stage) |
| the open questions a model leaves | `questions` | `questions` on the current model | answers |
| book-quality documentation | `document` | everything above, then `document` | anything the earlier stages did not settle |

Two rows are deliberately outside the lane order: a *question now* is answered by a loop skill and advances nothing, and *status* produces no artifact at all. Offering them keeps the menu honest — a user who only wanted to look should not be routed into a forge.

## Lanes — the default order per source

```
codebase ──► spec ──► forge-prose ──► [questions | chat] ──► blueprint(system) ──► document
prose ────────────► forge-prose ──► [questions | chat] ──► blueprint(system) ──► document
database ─► spec(database) ──► forge-prose ──► … (same as codebase)
dataset ──► forge-data ──► lens ──► shape ──► blueprint(pipeline) ──► document
data-project ─► spec(data-project) ┐
               dataset ► forge-data ┴─► lens ──► shape ──► blueprint(pipeline: both inputs) ──► document
model ────► (read its layers) ──► the first stage of its lane whose product is missing
```

`questions` and `chat` are optional stages on every lane: Noctua proposes `questions` after a forge when the model has rule layers or a rationale with named external systems, and never schedules `chat` on its own — it names it.

## Reading a model's position from its layers

| Turtle / layers found | lane | next stage |
|---|---|---|
| `ex:sourceKind "dataset"`, no layers | dataset (a stripped or standalone model) | `forge-data` refine (`/dataset-forge <model>`) to regenerate `geometry`; `lens --standalone` only if the user says geometry is not wanted (Noctua proposes the refine) |
| `geometry` | dataset | `lens` |
| `geometry` + `analysis` | dataset | `shape` |
| `geometry` + `analysis` + `shape` | dataset | `blueprint --mode pipeline` |
| `geometry` + `shape` (no `analysis`) | dataset | `blueprint --mode pipeline` (Noctua notes that `lens` was skipped) |
| software model, no layers | software | `questions` (proposed) or `blueprint --mode system` |
| any model + `open-questions` with open rows | any | `refine` (the questions are the refine's brief) or `chat` |
| any model + `chat` | any | whatever the lane says next; the chat is context, not a stage |

A refine's output supersedes its predecessor for routing — recognised by the ledger's History (Noctua recorded the refine) or, for a file produced before the ledger existed, by the user's word and the memory stances; the predecessor stays in the ledger as history.

## Stage prerequisites Noctua checks before invoking

`python3 noctua/scripts/env_check.py --env` answers all of this in one line and one exit code; the list below is what it checks and why.

- Every stage: the consuming skill is installed (its `SKILL.md` is listed by the runtime) **and its scripts exist** — `env_check.py --env` checks exactly this, because a skill whose `SKILL.md` names a script the directory lacks is a specified-but-unbuilt stage: `ERROR:` naming the script, lane closed there. `domain-forge` is installed for any stage that reads or writes a model; `effective-java` (an external skill, not part of this package) for `blueprint`.
- `forge-data`, `lens`, `shape`: Python 3 with `pandas`, `numpy`; `scipy`/`scikit-learn` for `lens` and `shape`; `geopandas` + `pyproj` only when `context.spatial` is non-empty; a headless Chromium for symbolic verification and smoke tests (without one the stages degrade as their own SKILL.md says — Noctua records `WARN: no headless browser` once in the ledger, not once per stage).
- `blueprint`: the `effective-java` skill for the anchor corpus.
- `document`: a LaTeX toolchain.

A missing prerequisite is an `ERROR:` for that stage and a `WARN:` for the plan; Noctua proposes the stages that can still run.
