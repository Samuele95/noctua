---
name: model-chat
description: Hold an engine-grounded conversation with a domain-forge HTML model. Every answer is produced by RUNNING the model's own engines — SPARQL over the asserted graph, the RDFS/SWRL reasoner over the inferred graph, the Prolog runner, and the DMN tester — never by LLM speculation; when no engine can ground a question, the skill refuses and names the gap. Emits a pure-additive `chat` transcript layer on the input HTML (input never modified); each turn in the rendered layer carries a live "re-run" button. Use whenever the user runs `/model-chat`, hands you a domain-forge `model.html` and wants to "ask the model", "query it in Prolog/SWRL/SPARQL/DMN", "what does the model say about…", "is this transaction fraudulent according to the model", "interrogate the model", or to discuss specific `/inferred-questions` against the live engines. Sibling to `/domain-forge` (forges/refines the model) and `/inferred-questions` (asks open questions; this one answers, with proof).
---

# /model-chat

An **interactive, engine-grounded Q&A session** over a composed `/domain-forge`
model. You ask questions in natural language; for each one the skill routes to the
right paradigm, **formalises the question as a real query, runs it against the
model's own engine, and answers from the result** — citing the engine, the query,
and the raw output. At session end it writes a pure-additive `chat` transcript
layer → `model.chat.html`, a strict byte-superset of the input (input untouched).

It is one link in the domain-forge functional pipeline. The layer contract —
`@LAYER:start/end` markers, byte-exact preservation, `input-digest` provenance,
validator invariants 13–16 — is binding (`references/layer-contract.md`).

## The grounding principle (the rule that defines this skill)

**An answer that an engine could compute MUST be computed by that engine, not
asserted by you.** The model ships runnable reasoning; this skill's job is to
*drive it*, not to paraphrase the Turtle. Concretely, for every question:

- Pick the engine that grounds it (`references/paradigm-routing.md`).
- Write the query in that engine's language.
- Run it with `scripts/run_query.py` (headless; uses the model's `window.__kg`
  SPARQL+reasoner, `window.__plRun`/the Prolog runner UI, or the DMN tester).
- Compose the answer **from the returned result**. Every factual claim traces to it.
- If **no** engine can ground it — the question needs a layer the model lacks, or
  is outside the formal model (costs, opinions, plans) — **refuse and name the
  gap**. Do not fall back to an LLM guess. (This is the user-chosen policy.)

A turn that was not executed is not an answer. If `run_query.py` errors or returns
something unexpected, report that — never smooth it over.

## Relationship to neighbouring skills

- `/domain-forge` forges/refines the model and owns `.claude/domain-forge-memory.md`
  **and the layer platform**: this skill's `scripts/apply_layer.py`, `strip_layer.py`
  and `run_query.py` keep their CLIs but delegate to `domain-forge/scripts/` (the
  one writer of `@LAYER` blocks and digests, the one headless engine driver), so
  `domain-forge` must be installed as a sibling skill directory (or `DOMAIN_FORGE_DIR`
  / `--domain-forge-dir` must point at it).
- `/inferred-questions` *asks* latent modeling questions; `/model-chat` *answers*
  questions, with engine proof. A natural flow: run `/inferred-questions`, then
  `/model-chat` to interrogate specific gaps against the live engines.
- `/countergen` produces adversarial A-box test inputs; this skill produces a
  human-facing, reproducible transcript.

## Trigger and arguments

```
/model-chat <path/to/model.html>
```

- `--out <path>` — output. Default `<input-stem>.chat.html` next to the input.
- `--continue` — append this session's turns to an existing `chat` layer (default:
  refuse if a `chat` layer already exists, to avoid clobbering).
- `--questions <file>` — non-interactive batch: answer one NL question per line,
  then write the layer (CI/self-explanation use).
- `--report-only` — write the transcript JSON + a markdown summary, skip the HTML.

## Procedure — the interactive session loop

1. **Open the model (read-only).** Confirm it is a domain-forge file (`#domain-model`
   present). Detect which engines it actually exposes by a probe run:
   `window.__kg` (SPARQL+reasoner) is near-universal; `window.__plRun` or
   `.pl-input` means Prolog is driveable; `#dmn-tester` means DMN is. Read the
   `model-markdown`, `model-horn`/`model-prolog`, `model-dmn`, and the Turtle so you
   know the real class names, predicate arities, and DMN input names. Read
   `.claude/domain-forge-memory.md` if present (the model's decided stances).

2. **Greet + state scope.** One line: which paradigms are live for this model, and
   that every answer will be engine-run. Then take the first question.

3. **For each question, run the per-turn discipline (below).** Show the user the
   grounded answer immediately, with the engine badge, the query, and the result.

4. **Loop** until the user ends the session ("done", "that's all", empty input).

5. **Write the layer.** Build the transcript JSON (all turns) and run
   `scripts/apply_layer.py <model> --transcript <tr>.json --out <out>`. Then
   **verify**: run `domain-forge/scripts/validate_model.py <out>` (must pass,
   including the layer invariants) and confirm `strip_layer.py` recovers the input
   byte-for-byte. Report the path + turn count.

### The per-turn discipline (reasoning steps — do every one)

- **Understand.** What is actually being asked? A stated fact? A derived one? A
  goal/“is *this* X?”? A per-record decision? A counterfactual “what if the amount
  were €20000?” (a fresh DMN/Prolog input)? Restate it to yourself in one clause.
- **Route.** Apply `references/paradigm-routing.md` top-to-bottom. Decide the engine.
  Mind the **asserted-vs-reasoned trap**: any query touching a *derived* class/property
  routes to `swrl` (reasoned), not `sparql`.
- **Formalise.** Write the exact query using the model's real names (PREFIX on its
  own line for SPARQL; correct predicate/arity for Prolog; real input names for DMN).
- **Execute.** `python scripts/run_query.py <model> --engine <e> --query '<q>'`
  (or `--dmn-inputs '<json>'`). Read the JSON `result`.
- **Ground / verify.** Compose the answer from the result. If the result is surprising,
  re-read the query (often the asserted-vs-reasoned trap or a wrong predicate name) and
  re-run — do not narrate around a wrong result. If no engine fits, refuse + name the gap.
- **Record the turn** `{q, paradigm, reasoned?, query, result, answer, grounded}`.

## Failure modes — DO NOT

- **Don't answer from the Turtle/markdown when an engine could compute it.** Reading
  a triple off the model and paraphrasing it is the failure this skill exists to prevent.
  If it's a fact in the A-box, `SELECT` it; if derived, run the reasoner; if goal-directed,
  prove it in Prolog.
- **Don't route a derived-fact query to `sparql` (asserted).** It returns the wrong
  answer silently. Derived ⇒ `swrl`.
- **Don't route a cross-record or "is *this* one X" question to DMN** — DMN is stateless,
  one record per call (`paradigm-routing.md`). Use Prolog.
- **Don't claim a result the engine did not return**, and don't hide an engine error
  behind prose. A refused turn is honest; a fabricated one corrupts the transcript.
- **Don't modify the input file.** Output is a new path; the input is the reversal.
- **Don't leave a grounded turn's `query` unexecuted** or its `result` hand-written.
- **Don't put `PREFIX` and `SELECT` on the same line** — the engine strips whole
  `PREFIX` lines and will eat the query.

## Worked example (one turn, fraud model)

> User: *"Which transactions are fraudulent, and is tx_r2 really one of them?"*

Two sub-questions, two paradigms:

1. *"which are fraudulent"* — `FraudulentTransaction` is **derived** → route `swrl`.
   Query (PREFIX on its own line):
   `SELECT ?t WHERE { ?t a ex:FraudulentTransaction }` →
   `run_query.py --engine swrl` → rows `Mensoni, Suter, R1, R2`.
2. *"is tx_r2 really one"* — goal-directed "is *this* one" → route `prolog`.
   `outcome(tx_r2, O).` → `run_query.py --engine prolog` → `O = declined`.

Answer (grounded): "Four are fraudulent — Mensoni, Suter, R1, R2 — derived by the
reasoner once it runs (riskScore ≥ 100). And yes: Prolog proves `outcome(tx_r2, O)`
→ **declined** (risk 220, above the 150 threshold), so tx_r2 is one of them. The two
paradigms agree." Both queries + raw results are shown in the turn.

> User: *"What's the bank's quarterly profit forecast?"*

No engine/layer represents finance → **refuse**: "Unanswerable from this model — it
covers fraud-risk scoring only; there is no financial-forecasting layer or data to query."
