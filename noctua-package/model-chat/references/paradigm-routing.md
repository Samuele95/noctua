# Paradigm routing — which engine grounds which question

`/model-chat` never answers from the LLM. For each question it picks the **one
engine that can ground the answer with the fewest assumptions**, formalises the
question in that engine's language, runs it (`scripts/run_query.py`), and answers
from the result. This file is the routing decision procedure. It is the dual of
`domain-forge/references/paradigm-fit.md` — that decides where *logic* belongs;
this decides where a *question* goes.

## The four engines a domain-forge model ships

| Engine (`--engine`) | Grounds questions about… | How it runs |
|---|---|---|
| `sparql` | facts/relationships **as asserted** — who/what/which, links, counts over the A-box | `window.__kg.runSparql(q)` over the asserted graph |
| `swrl`   | **derived** facts — classifications, computed scores, anything an RDFS/SWRL rule produces | `window.__kg.setReasoned(true)` then `runSparql(q)` (run the reasoner, then SELECT) |
| `prolog` | **goal-directed / cross-record / closed-world** — "is *this* an X?", "is there another record such that…", anything needing negation-as-failure | the Prolog runner (`window.__plRun` or the `.pl-input`/`.pl-run` UI) |
| `dmn`    | a **single-record decision outcome and its trace** — "for these inputs, what is the verdict and why" | the DMN Test view (`#dmn-tester`) |

## Decision procedure (run top to bottom; stop at the first match)

1. **Is the answer a value the model only knows after reasoning?** (a classification,
   a summed/derived property, a `FraudulentTransaction`/`ATransaction`-style membership)
   → **`swrl`** (reasoner + SPARQL). You MUST run reasoned; the asserted graph does
   not contain derived triples. See the trap below.
2. **Is it goal-directed, cross-record, or does it need negation?** ("is tx_r2 fraud?",
   "is there another transaction on the same card in a different country?", "which
   transactions are *not* X" where X is closed-world) → **`prolog`**. Prolog quantifies
   over all records and has `\+`.
3. **Is it "what does the decision model output for this one record, and through which
   rules"?** → **`dmn`** (drive the Test view; read the outcome + per-step trace).
4. **Otherwise it's a fact/relationship/count over what is stated** → **`sparql`**
   (asserted).
5. **No engine can ground it** (needs a layer the model lacks, or it's outside the
   formal model — costs, opinions, future plans) → **refuse**: state plainly it's
   unanswerable from the model and name the missing layer/paradigm. Never fabricate.

When two engines could answer (e.g. a complement is reachable by `prolog` NAF *and*
by `swrl`+SPARQL `NOT EXISTS`), prefer the one whose paradigm the question is phrased
in, and note in the answer that the other agrees — that cross-check is high value.

## The asserted-vs-reasoned trap (read this)

A SPARQL query whose pattern targets a **derived** class returns **nothing** over the
asserted graph and the right answer over the reasoned graph. Example from a fraud model:

```
SELECT ?t WHERE { ?t a ex:Transaction . FILTER NOT EXISTS { ?t a ex:ATransaction } }
```
- `--engine sparql` (asserted): returns **all** transactions — `ATransaction` is derived,
  so nothing is typed it yet. **Wrong answer.**
- `--engine swrl` (reasoned): returns the true B-transactions — the reasoner has fired
  the A-rule first. **Correct.**

Rule: if any class/property in the query is produced by a rule (not asserted in the
A-box), route to `swrl`, not `sparql`.

## Formalisation skeletons

- **sparql / swrl** — a `SELECT`. Put each `PREFIX` on its **own line** (the engine
  strips whole `PREFIX` lines; `PREFIX … SELECT …` on one line is eaten). Supported:
  basic graph patterns (`;` `,` `.`, `a`, prefixed IRIs), `DISTINCT`, and
  `FILTER NOT EXISTS { … }` / `MINUS { … }`. Not supported: `OPTIONAL`, aggregation,
  property paths, arbitrary `FILTER(expr)`.
- **prolog** — a goal ending in `.`, e.g. `outcome(tx_r2, O).`, `impossible_travel(T).`,
  `\+ a_transaction(tx_suter).`. Read the model's `model-horn`/`model-prolog` block to
  use the actual predicate names and arities.
- **dmn** — a JSON object of input-name → value matching the model's input data, e.g.
  `{"Payment Amount": 11234, "Merchant Country": "South Africa", "Service Type": "physical"}`.
  Read `model-dmn` for the exact input names.

## Grounding the answer

The NL answer is composed **from the returned result only**. Always surface, in the
transcript turn: the chosen engine, the exact query, and the raw result. If the engine
errored or returned unexpectedly, say so — do not paper over it with an LLM guess. The
answer may add brief interpretation ("220 is above the 150 decline threshold"), but
every factual claim must trace to the result.
