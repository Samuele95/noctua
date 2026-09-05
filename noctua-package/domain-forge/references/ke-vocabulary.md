# Knowledge-engineering vocabulary (the target formalisms)

The domain model must be expressible in these formalisms so it is KE-compatible and re-consumable. This file is the extractor's reference for *what shapes the model may take*. Distilled from a knowledge-engineering course; the notation below is the contract.

## Layer 1 — Ontology (always present)

An ontology is built from a small fixed vocabulary. Five pieces carry the weight.

- **Classes (concepts)** — the KINDS of things in the domain. Drawn as ovals/boxes. `ex:Person a owl:Class`.
- **Class hierarchy (subClassOf)** — a class can be a strict SUBSET of another. Drawn as an open arrow upward. `ex:Cardholder rdfs:subClassOf ex:Person`. Use ONLY for genuine is-a subsets (every Cardholder *is a* Person). Do not use it for "has-a" or "plays-role" — that is the single most common ontology-modeling error.
- **Individuals (instances)** — the SPECIFIC things in the world. Drawn as dashed ovals. `ex:mensoni a ex:Cardholder`. Only model individuals when the idea names concrete examples.
- **Object properties (relationships)** — a labelled link between TWO individuals. `ex:hasMerchant a owl:ObjectProperty`. They lead to another node you can keep traversing.
- **Data properties (attributes)** — a labelled link from an individual to a LITERAL (number/string/date). `ex:hasAmount a owl:DatatypeProperty`. They lead to a leaf you can compare but not navigate from.

The object/data distinction is load-bearing: what is on the right-hand side determines what you can do next. An object property's right side is a node (keep traversing); a data property's right side is a value (a leaf).

**Domain and range** — every property declares constraints: its `rdfs:domain` (which class it applies to) and `rdfs:range` (what it points to — a class for object properties, an `xsd:` datatype for data properties). `hasMerchant` has domain `Transaction`, range `Merchant`. This is what lets a tool catch `mensoni hasMerchant 42` as a type error. **A relationship without honest domain/range is incomplete.**

### Two layers: T-box and A-box

- **Schema layer (T-box, "terminological")** — the classes, the hierarchy, the property declarations with their domains/ranges, the constraints. *What kinds of thing can exist.* This is the bulk of a domain model.
- **Instance layer (A-box, "assertional")** — the actual individuals and the property values that hold between them. *What is actually out there.* Often sparse or empty in a forged model; populate it only when the idea gives concrete examples worth pinning down.

A domain model that is all A-box and no T-box is a data dump; one that is all T-box is the usual and correct shape for an idea-stage model.

**Emitting an A-box now has visual payoff.** When the model carries individuals, the Diagram tab renders them in the course KG convention (KE-07 "Schema vs. Instances/Data"): one graph with a blue **Schema (T-box)** frame of class *ellipses* over an orange **Individuals / Data (A-box)** frame of individual *ellipses*, joined by blue `rdf:type` edges (`subClassOf` red). The reasoner can then be run on the graph to fade in the inferred memberships/classifications, and the Logic→SPARQL view becomes runnable over the (optionally inferred) instances. So when a domain offers a few concrete examples, a handful of representative individuals per key class is worth pinning down — it lights up the unified diagram, the SPARQL runner, and the reasoner overlay.

### Property placement — where does the property belong?

This is the modelling decision the KE-course feedback returns to repeatedly. Two anchors:

- **Place the property on the concept whose state drives the value.** `MerchantRisk` is the same for every transaction of a merchant → it belongs on `Merchant`, not on `Transaction` (where it would be duplicated across thousands of transactions). Conversely, `transactionAmount` varies per transaction → it belongs on `Transaction`. The test: if I imagine the value changing, which concept's *identity* did I change?
- **Don't reify into an intermediate node unless it carries its own attributes.** Adding a `Risk` node between `Transaction` and a number (`Transaction → hasRisk → Risk → riskAmount → 60`) only earns its keep if a `Risk` has properties of its own (timestamp, reason, weight) or if multiple risks coexist per transaction. Otherwise the blank node is noise; write `Transaction → riskAmount → 60` directly.

### Intermediate-entity rule

If A relates to C only through B in the real domain, **model the chain A → B → C explicitly** rather than the shortcut edge A → C. The chain:

- attributes blame when one link changes (a card reissued doesn't move the previous transactions to a new cardholder),
- lets the intermediate carry its own attributes (`Creditcard.expiryDate`, `Creditcard.scheme`),
- survives many-to-many relationships (one card, several cardholders).

Worked example from the KE feedback: a transaction is **used** with a **Creditcard**, which **hasCardholder** a **Cardholder**. Writing `Transaction --hasCardholder--> Cardholder` collapses the card and falls apart the moment a card has multiple cardholders.

## Layer 2 — DMN decision tables (gated: `--layers dmn`)

For domain logic that is *decision-shaped* — "given these inputs, which outcome?". A decision table has, per row (rule): **input entries** (conditions per input column) and **output entries** (what the rule produces).

- Entries are written in **FEEL** (Friendly Enough Expression Language): a literal (`"Italy"`), a comparison (`>10000`), a negation (`not("Italy")`), a dash `-` ("this input is irrelevant for this rule"), or — important — an **interval** in bracket notation: `[1000..10000]` inclusive both ends, `[0..1000)` excludes the upper, `(100..150]` excludes the lower. Prefer intervals over enumerating values.
- The top-left cell is the **hit policy** — it answers "when more than one row matches, which output wins?". Single-hit: **U** (Unique — at most one row matches), **A** (Any), **P** (Priority), **F** (First). Multiple-hit: **C** (Collect — with aggregation variants `C+` sum, `C#` count, `C<` min, `C>` max), **R** (Rule order), etc. **Every decision table must declare a hit policy** — it is the heart of the table, not an afterthought.

Model a decision table when the idea contains scoring, eligibility, classification, or routing logic. Reference the ontology's classes/data-properties as the table's inputs (e.g. input = `Transaction.hasAmount`).

### DMN design checklist (KE-course feedback)

The course's milestone feedback is consistent — these are the recurrent design defects to avoid:

- **Prefer `U` (Unique) over `F` (First).** `F` is a fragile choice: it makes the table order-dependent, hides the modeller's assumption that rules overlap, and forbids the reviewer from spot-checking individual rows. Use `U` and *prove disjointness* via interval partitions (`[0..1000)`, `[1000..10000)`, then `>=10000` for the unbounded top bucket — a FEEL interval needs both endpoints, so cap an open-ended range with a comparison, not `[10000..]`) and `-` for irrelevant columns. The course feedback flags `F` every time it sees it.
- **Use intervals, not value enumerations or chained inequalities.** Write `[1000..10000]` in one cell, not `>=1000 AND <=10000`, not `1000, 2000, 5000, 10000`. Intervals are the FEEL idiom; enumerations are a list-input smell and force the reader to enumerate edge cases.
- **Outputs are single values, not lists.** An output cell `10, 60, 90` is the wrong dimension — those should be three rows under hit policy `U`, each producing one value.
- **Inputs must match the upstream system's data type.** If the upstream system supplies `Country`, the table inputs must be countries — not regions/continents. Mapping `Country → Continent` lives in a **separate sub-decision** that feeds this one. The course feedback's typical question: *"The input is COUNTRY, not region. Who maps the country to the region?"*
- **Decompose into a DRD with sub-decisions; one input + one output per table** is the limit case (less is more). The course's "good example" is exactly this: instead of a 27-row, 3-input table, three sub-decisions (`AmountRisk`, `MerchantRisk`, `ResidenceRisk`) each with one input, then a top-level `TotalRiskScore = sum-of-parts` expression node.
- **Reuse lookup mappings via a BKM (Business Knowledge Model)** — don't write the same `Country → Continent` table twice for Location and Residence. One BKM, two invocations.
- **Avoid intentional ambiguity.** `Italy` appearing in two rules where the reviewer must guess which fires is a defect. Cover the negative case explicitly: `Italy`, `not("Italy")`, `null` — three disjoint rows.
- **DMN is stateless.** It cannot store, query, or compare *other* records. A rule like "if there is another transaction with the same card in a different country within 5 minutes" is **not DMN territory**. Either accept an extra input column ("previous transaction") populated by the upstream system, or move the rule to the Prolog/SWRL layer. See `references/paradigm-fit.md`.
- **Hit policy `C+` for additive scoring.** When the user says "rule A adds 90, rule B adds 30, rule C adds 40" the policy is `C+` (Collect with sum), not `U` followed by post-table addition. The course's "good example" again: skip the 27-combination table; compute the sum in a single expression node downstream.

## Layer 3 — Prolog / Horn clauses (gated: `--layers rules`)

For *derivable* knowledge — implicit facts the engine can infer rather than facts you assert one by one. A Horn clause has the shape:

```
H :- B1, B2, ..., Bn.        (H holds if B1 and ... and Bn all hold)
```

Three sub-cases — the entire vocabulary of logic programming:

- **Fact** — head, no body: `is_a_sailor(popeye).`
- **Rule** — head with body: `strong_sailor(X) :- sailor(X), eats(X, spinach).`
- **Query** — body, no head: `?- strong_sailor(popeye).` (a goal to prove; not part of the stored model, but useful to record example queries the model should answer).

Capitalized terms are variables; lowercase are atoms/constants. A predicate's identity includes its arity (`parent/2` ≠ `parent/3`). Model rules when the idea says "X counts as Y when …", "Z is eligible if …", or describes consequences that follow from other facts. Reference only predicates that correspond to declared classes/properties so the rule layer stays coherent with the ontology.

### Three Prolog representation styles

The KE feedback shows the same domain (a transaction with credit card, merchant, amount, timestamp) encoded three ways. They are all valid Prolog; they differ in how the data flows into the rules.

1. **Direct from the ontology** — classes are unary predicates, object/data properties are binary:
   ```prolog
   transaction(t1).
   has_credit_card(t1, k1).
   has_merchant(t1, h1).
   has_amount(t1, 500).
   merchant(h1).
   merchant_country(h1, morocco).
   ```
   *Mirrors the RDF triple shape 1:1.* Easy to extend; verbose; many small predicates.

2. **Database-oriented** — multi-place predicate, positional arguments:
   ```prolog
   transaction(t1, k1, h1, 500, 1770293096).
   retailer(h1, "World of Africa", south_africa).
   credit_card(k1, sutter).
   ```
   Compact; fast to write when data is tabular. **Brittle**: every rule must know the position of each argument, and renaming/inserting a column breaks every caller.

3. **Compromise** — multi-place facts plus *binary property rules* layered on top:
   ```prolog
   transaction(t1, k1, h1, 500, 1770293096).
   amount(T, A) :- transaction(T, _, _, A, _).
   merchant(T, M) :- transaction(T, _, M, _, _).
   ```
   Rules call by name (`amount(T, A)`), not by position. Adding a column doesn't break callers. **This is the style the course recommends** when the data is naturally tabular but the rules are domain-shaped.

### Closed world: what only Prolog offers

Prolog has **negation as failure** (`\+`): "not provable, therefore false". This lets you write `tuition(X, 7500) :- \+ residence(X, eu), \+ residence(X, switzerland).` SWRL cannot do this (see below). The KE-course feedback explicitly compares the two paradigms on a tuition-fee example: the Prolog clause uses `\+`, the SWRL version has to invent a positive class `:NonEuropeanCountry` and type every non-European country into it.

## Layer 4 — SWRL rules (gated: `--layers swrl`)

SWRL is the Semantic Web Rule Language. A rule is an antecedent (conjunction of atoms) implying a consequent (assertion onto the graph). Protégé-compatible.

```
Class(?x) ∧ objectProperty(?x, ?y) ∧ dataProperty(?x, ?n) ∧ swrlb:greaterThan(?n, 18) → Class2(?x)
```

Atom types: **class** atom (`Person(?x)`), **object property** atom (`hasParent(?x, ?y)`), **data property** atom (`hasAge(?x, 18)`), **built-in** atom (`swrlb:greaterThan(?n, 0)`), **sameAs**/`differentFrom`. See `references/html-contract.md` for the JSON shape.

### SWRL semantics — the three "no"s

These are the three constraints the KE course returns to. **An extractor that ignores them ships a broken rule layer.**

1. **No negation.** You cannot write `not(EuropeanCountry(?c))` in an antecedent. Workaround: classify the complement positively. Define `NonEuropeanCountry rdfs:subClassOf Country` and assert membership for each non-European country. Then write `NonEuropeanCountry(?c)` in the antecedent. The rules become longer but the inference holds.
2. **No overwriting.** Once a triple is asserted, it stays. If two SWRL rules can derive *different* values for the same functional data property, you derive *both* — which usually contradicts intent. Write the rules so that they cannot simultaneously fire with different outputs, or split into named sub-properties (`amountRisk`, `merchantRisk`) and aggregate via `swrlb:add`.
3. **No defaults.** If no rule fires that derives `specialRisk(?t, ?n)`, no `specialRisk` triple exists. An aggregation `riskScore = swrlb:add(amountRisk, merchantRisk, specialRisk)` needs `specialRisk` to exist — for every transaction the rule sees. Two patterns to handle this:
   - **Baseline assertion:** for every `Transaction`, assert `specialRisk(?t, 0)` up front. Subsequent rules that fire for the actual special-risk case must use a different property (`bonusSpecialRisk(?t, 30)`) and the aggregation adds both.
   - **Document the gap.** If you cannot enumerate every contributing part, the aggregated `riskScore` will be missing for individuals where a contribution is absent. The KE feedback explicitly asks for the limitation to be written into the report.

### SWRL has no hit policy

DMN's hit policy is a *first-class control over rule conflict*. SWRL has no equivalent — every rule that matches fires and asserts. The modeller must ensure the consequents of any two co-firing rules don't conflict. In practice this means:

- Split into named sub-properties (`merchantRisk` vs `cardholderRisk`) so two rules don't both write to `riskScore`.
- For categorical outputs, use class membership (`Eligible(?c)`), not a string data property (`status(?c, "eligible")`) where two rules might write `"eligible"` and `"pending"` for the same individual.
- Aggregations are the natural endpoint: `riskScore = swrlb:add(...)` collects every contributing part into one value.

### Goal direction

SWRL is **forward-chaining only** — the engine asserts every conclusion that fires; you cannot ask it a goal-directed question ("is this transaction fraudulent?"). For goal-directed queries you go to **SPARQL** (over the inferred graph) or to **Prolog**. The course feedback states this explicitly: *"In Knowledge Graphs we can have data about many transactions and compare a transaction with all the other transactions — but not goal-directed."*

### SPARQL — the queryable view over the (optionally inferred) graph

SPARQL is the query language for the knowledge graph, and in a forged model it is **runnable in-browser** (the `@KG_RUNTIME` SPARQL runner in the Logic→SPARQL view), not just a set of copy-paste examples. It runs `SELECT` over the model's triples with an asserted ↔ asserted+inferred toggle: this is exactly where the goal-directed questions SWRL cannot answer get answered. The supported subset is deliberately small — basic graph patterns (`; , .` shorthand, the `a` keyword, prefixed IRIs, `DISTINCT`); no `OPTIONAL`/`FILTER`/aggregation/property-paths. The pedagogically important consequence: a query for a SWRL-derived class (e.g. `?t a ex:FraudulentTransaction`) returns **nothing until the reasoner is run** — the runner says so — which is the cleanest demonstration of the asserted-vs-inferred distinction. Curate a few example queries (they seed the runner's chips); at least one should target an inferred class.

## Reasoner capabilities — what domain-forge actually infers

The runtime ships a **forward-chaining reasoner** that runs at load time and
produces an "inferred" view of the model. It is a positive-Horn engine: every
fact it can derive, it asserts. What it covers, and what it does not, sets the
boundary of what an extractor's findings can lean on. **Don't propose a finding
whose value depends on inference the reasoner doesn't perform** — the validator
will accept the canonical Turtle but the Logic / Hierarchy / Diagram views won't
show the expected entailments.

### Implemented

- **RDFS-plus**: subClassOf transitive closure, class membership inheritance
  (individual ∈ subclass ⟹ individual ∈ superclass), subPropertyOf transitive
  closure and propagation onto every object/data property fact, owl:equivalentClass
  as bidirectional subClassOf.
- **OWL property characteristics**: `Symmetric` (R(x,y) ⟹ R(y,x)),
  `Transitive` (R(x,y) ∧ R(y,z) ⟹ R(x,z)), `owl:inverseOf` (R(x,y) ⟹ R⁻¹(y,x)).
- **SWRL forward chaining**: every rule whose antecedent matches fires its
  consequent. Atom types: class, objectProperty, dataProperty, sameAs,
  differentFrom, the six numeric comparator `swrlb:` built-ins (`greaterThan`,
  `greaterThanOrEqual`, `lessThan`, `lessThanOrEqual`, `equal`, `notEqual`), and
  the four arithmetic-assignment built-ins (`swrlb:add`, `subtract`, `multiply`,
  `divide`) whose first argument is the result — so an aggregate like
  `riskScore = swrlb:add(...)` is computed and bound, not just compared.
- **Provenance**: every inferred fact carries its derivation chain
  (which characteristic / which SWRL rule / which subClassOf path).
- **Consistency pass** (post-fixpoint): detects (a) an individual belonging to
  two `owl:disjointWith` classes (transitively), (b) a class inheriting from
  two disjoint parents (transitively), (c) `owl:FunctionalProperty` with more
  than one distinct value for the same subject, (d) `owl:InverseFunctionalProperty`
  with more than one distinct subject for the same object. Surfaced in the
  Logic tab as a red Contradictions card pinned at the top.

### Not implemented (do not propose findings that depend on them)

- **Domain/range inference**: `rdfs:domain(P, C) ∧ P(x, y) ⟹ x ∈ C`. The
  validator checks that declared `rdfs:domain` and `rdfs:range` point at
  declared classes, but the reasoner does not classify individuals by them.
- **Property restrictions** as classification: `owl:someValuesFrom`,
  `allValuesFrom`, `hasValue`, cardinality. Restrictions can be carried on the
  class (the Ontology tab renders them) but they do **not** entail membership.
- **Anonymous class expressions**: `owl:unionOf`, `intersectionOf`,
  `complementOf`. Treated as opaque IRIs.
- **Property chains**: OWL 2 `owl:propertyChainAxiom` (R₁ ∘ R₂ ⊑ R₃).
- **Functional / InverseFunctional as sameAs entailment**: the reasoner
  *flags the contradiction* (consistency pass above) but does not enrich the
  graph with `owl:sameAs(o1, o2)` when a Functional property forces it.
- **Reflexive / Irreflexive / Asymmetric** property characteristics: declared
  but not enforced.
- **hasKey** (functional combination of properties).
- **Datatype subsumption / facets** (xsd:int ⊑ xsd:integer; xsd restrictions).
- **SWRL non-numeric built-ins**: no string ops, date arithmetic, list ops. (The
  numeric comparators and `add`/`subtract`/`multiply`/`divide` *are* implemented — see above.)
- **Open-vs-closed world**: implicit OWA — `not P(x, y)` cannot be asserted
  or used in an antecedent. The "no negation" SWRL rule above applies.

### What this means for extractor findings

- A "classify individual via restriction" finding should be a Horn rule or a
  SWRL rule on the explicit pattern, not an OWL restriction expecting
  classification.
- A "split into two disjoint contexts" finding is **safe** — the consistency
  pass enforces disjointness, the user sees a violation if anything later
  bridges them.
- A "single contact per customer" finding can be expressed as
  `owl:FunctionalProperty` on `hasContact`. The reasoner will flag violations.
- A "no two transactions sharing the same external reference id" finding can
  be expressed as `owl:InverseFunctionalProperty` on `hasExternalId`.
- Domain/range checks are *static* (validator invariant 2/3); don't propose
  findings of the form "this fact is invalid because its subject is not in
  the property's domain" — the reasoner doesn't compute that.

## The six coordinates (diagnostic, not output)

When unsure whether a piece of knowledge belongs in the model and in which layer, classify it on these axes (from the course): **paradigm** (symbolic here), **derivation** (explicit/asserted vs. implicit/derivable — derivable → rules layer), **kind/articulation** (tacit → formal), **reliability** (precise/uncertain/incomplete/vague — flag vague knowledge in §6 Open questions), **level of formalization** (conceptual → executable), **representation** (declarative vs. procedural; structural vs. rules-and-facts — structural → ontology, rules-and-facts → Horn/DMN). A good knowledge base is *small in explicit knowledge, rich in implicit* — prefer a few rules that unfold many consequences over enumerating every case.
