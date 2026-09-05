# Bloch → domain-modeling mapping

*Effective Java* (Joshua Bloch, **3rd edition**) items are about Java APIs, but the principles underneath them are **modeling** principles. Every `EJ-N` token below is a real 3rd-edition item number — cite it as the book numbers it. This file translates them into **domain-model** decisions so the extractor anchors every finding to a named principle rather than to taste — supplemented by SOLID, GoF, FP discipline, DDD, and Hexagonal architecture.

**The one rule this file enforces:** every finding carries an `anchors` array of one or more tokens drawn from the **anchor vocabulary** below, and is filed under one of the **four axes**. A token you cannot find in the table is not a valid anchor — pick the closest real one or leave the finding unanchored and say so, rather than inventing an item number.

`axis ∈ { model, abstraction, composition, behaviour }`. (The first three are *structural* — what concepts exist and how they wire; `behaviour` covers derived/decision knowledge that lives in the DMN/Horn/SWRL layers.)

## Anchor vocabulary

Cite these exact tokens, one per item — never a compound like `EJ-10/11` (write `["EJ-10", "EJ-11"]`).

| Token | Item / principle | Use it when a finding… |
|---|---|---|
| `EJ-10`, `EJ-11` | Obey the general contract when overriding equals / Always override hashCode when you override equals | …decides identity-vs-value (do two instances match by id or by attributes?) |
| `EJ-17` | Minimize mutability | …makes an attribute-defined concept an immutable value object |
| `EJ-15`, `EJ-50` | Minimize the accessibility of classes and members / Make defensive copies when needed | …shrinks a concept's writable surface; separates intrinsic from derived state |
| `EJ-34` | Use enums instead of int constants | …turns a fixed named set into a closed enumeration (status, band, category) |
| `EJ-18` | Favor composition over inheritance | …replaces a wrong `subClassOf` with a relationship |
| `EJ-20`, `EJ-22` | Prefer interfaces to abstract classes / Use interfaces only to define types | …models a capability as a role a concept can play |
| `EJ-64` | Refer to objects by their interfaces | …relates a concept to a role rather than to a specific variant |
| `EJ-51` | Design method signatures carefully | …splits a concept accreting unrelated responsibilities |
| `SOLID-S` | single responsibility | …finds two concepts fused into one |
| `SOLID-O` | open/closed | …moves volatile policy into a decision table instead of code |
| `SOLID-L` | Liskov substitution | …admits or rejects an is-a subset by substitutability |
| `SOLID-D` | depend on abstractions | …relates concepts (or contexts) through a role / published id, not a variant |
| `GoF-Composite` | part-whole tree | …names a Folder/File, Category/Product recursion |
| `GoF-Strategy` | interchangeable policy | …routes a swappable policy to a role + DMN table |
| `GoF-State` | lifecycle | …models an entity lifecycle as an enum + transitions |
| `DDD-Entity` | entity | …a concept has identity and a mutable lifecycle |
| `DDD-ValueObject` | value object | …a concept is defined entirely by its attributes |
| `DDD-Aggregate` | aggregate root | …draws an invariant-owning boundary around a cluster |
| `DDD-BoundedContext` | bounded context | …splits one word that means two things into two concepts |
| `DDD-AntiCorruption` | anti-corruption layer | …couples across a seam by published id, not shared mutable state |
| `HEX` | hexagonal boundary | …marks an external system as a boundary, not an internal concept |
| `FP` | FP discipline | …keeps a calculation derived-and-pure rather than stored |
| `DMN`, `Horn`, `SWRL` | the rule formalisms | …a behaviour finding names the layer it belongs in |

## The four axes

- **Model** — which concepts exist; identity vs. value; immutability; what the literals are.
- **Abstraction** — hierarchy and generalization; concepts-as-roles; generalize only where it earns its keep.
- **Composition** — how concepts wire together; seams / bounded contexts; coupling across seams.
- **Behaviour** — where *derived and decision* knowledge lives, and in which paradigm (DMN / Horn / SWRL). Structure says what *is*; behaviour says what is *computed or inferred*.

### Model axis

- **EJ-17 (minimize mutability)** → a concept defined entirely by its attributes is a **value object** and should be immutable: Money, EmailAddress, DateRange, Coordinate, Color. In the ontology it is a class whose data properties are set at creation and never change; it has no meaningful identity. Reclassifying "a bare number/string with meaning" into a value object is high-leverage. Anchor: `["EJ-17", "DDD-ValueObject"]`.
- **EJ-10 / EJ-11 (equals/hashCode) → identity vs. value** → ask: are two of these "the same" because of a stable identifier (→ **entity**: Customer, Order, Account — has an id, a lifecycle, mutable state) or because all attributes match (→ **value object**)? This single decision shapes the whole model and is usually `structural` or `architectural`. Anchor entities `["EJ-10", "EJ-11", "DDD-Entity"]`.
- **EJ-15 / EJ-50 (accessibility / defensive copies)** → which data properties are intrinsic vs. derived; do not model derivable values as stored state (link them to the rules layer instead — see the Behaviour axis). Keep the model's writable surface small.
- **EJ-34 (enums over int constants)** → a fixed set of named domain values (OrderStatus, RiskBand, Continent) is an enumeration concept, not a free string. Model as a class with a closed set of individuals, or an `xsd` enumerated range.

### Abstraction axis

- **EJ-18 (favor composition over inheritance)** → the strongest guard on `subClassOf`. Use subclassing ONLY for genuine is-a subsets where Liskov substitution holds (every Cardholder is substitutable as a Person — `SOLID-L`). When tempted to subclass for "has-a" or "is-implemented-using," model a relationship (object property) instead. Over-deep hierarchies are a smell.
- **EJ-64 (refer to objects by interface) / SOLID-D (depend on abstractions)** → a concept that several others satisfy is a *role*: PaymentMethod (Card, BankTransfer, Wallet), Notifiable, Priceable. Model the role as a class and the variants as subclasses or implementers, and relate other concepts to the role, not the variant.
- **EJ-20 / EJ-22 (interfaces over abstract classes; interfaces define types)** → prefer modeling capabilities as roles a concept can play rather than baking them into a rigid hierarchy. A concept can play several roles.
- **GoF where it clarifies the domain** — `GoF-Composite` (part-whole trees: Folder/File, Category/Product), `GoF-Strategy` (interchangeable policies → often a role + a DMN table; see Behaviour), `GoF-State` (lifecycle of an entity → often an enum + transitions). Cite only when the pattern genuinely names a domain shape, not decoratively.

### Composition axis

- **DDD-BoundedContext** → the highest-leverage composition move. When the same word means two things in two parts of the domain (Product = catalog item *and* billed line item; User = authenticated principal *and* profile), that is two concepts in two contexts, not one. Split into component groups; relate across the seam by **published identifier**, not a shared mutable object (`DDD-AntiCorruption` / `SOLID-D`). These are `architectural`.
- **DDD-Aggregate** → a cluster of entities/values with one root that owns invariants (Order owns its LineItems; you don't edit a LineItem except through its Order). Model the aggregate boundary as a component and the root as the entry concept.
- **HEX (hexagonal)** → things outside the domain (payment gateway, email provider, external catalog) are *boundaries*, not detailed concepts. Model them as a single boundary class with the relationship the domain needs, and mark them out-of-scope for internal detail.
- **SOLID-S (single responsibility) / EJ-51 (design method signatures carefully)** → each concept should have one reason to change; a class accreting unrelated data properties is two concepts fused.

### Behaviour axis

The structural axes say what concepts *are*. The behaviour axis decides what is **derived or inferred** — and, critically, **which paradigm** hosts it. Choosing the wrong paradigm is a quality defect, not a stylistic one, so this axis hands the *selection* off to a dedicated gate.

- **FP discipline (`FP`) + EJ-17** → a *calculation* (risk score, total, tax, eligibility) is a pure function of its inputs: derived, not stored. Do not model it as a data property that can drift out of sync. Push it to the rules/DMN layer and let the value be (re)computed. This is the behaviour axis's founding move — every "stored result" you find is a candidate behaviour finding.
- **SOLID-O (open/closed) + GoF-Strategy** → volatile policy that business users change (pricing bands, approval thresholds, routing rules) belongs in a **DMN decision table**, not in branching logic. A table extends by adding rows without touching code, and a Strategy-shaped family of policies maps cleanly onto one table keyed by its discriminator.
- **GoF-State + EJ-34** → an entity lifecycle (draft → submitted → paid → shipped) is a closed enum of states plus a transition relation. Model the states as an enumeration and the legal transitions as rules; don't scatter the lifecycle across boolean flags.
- **Paradigm choice is a hard gate, not a free axis.** Once you know a finding is behaviour, name the candidate layer (`DMN`, `Horn`, or `SWRL`) but run the actual selection through **`references/paradigm-fit.md`** — the six-question gate (state, goal-direction, monotonicity, cross-record, cardinality, external access). DMN, Prolog/Horn, and SWRL are competing paradigms with different expressive limits, not additive depth knobs. A behaviour finding that proposes DMN for cross-record logic, or SWRL for logic needing negation/defaults, is rejected at apply time. Do **not** duplicate the gate here — anchor the finding, then defer the choice to that file.

## Ranking findings by leverage — and assigning `depth`

Rank findings so the cascading ones come first, and let leverage tier set the `depth` value the orchestrator gates on:

| Rank | Decision | `depth` |
|---|---|---|
| 1 | Identity-vs-value, and bounded-context **seams** — they cascade through every relationship | `architectural` (a widely-referenced reclassification or boundary move) → else `structural` |
| 2 | Hierarchy-vs-composition — determines the abstraction surface | `architectural` if it restructures an existing hierarchy → else `structural` |
| 3 | Value-object / enum / role extraction; the paradigm-fit of a behaviour finding | `structural` |
| 4 | Attribute / label additions and renames | `surface` |

Be honest about `depth`: **surface** = add/rename one attribute or label; **structural** = introduce/reclassify a concept, add a relationship, set identity-vs-value, or place a derived value in the rules layer; **architectural** = move a boundary, restructure a hierarchy, or reclassify a widely-referenced concept. The orchestrator requires explicit per-finding opt-in for `architectural` depth, so under-claiming it to slip a change through is a defect.

## Worked example

Idea fragment: *"Customers place orders; each order has a total in dollars and a status of new, paid, or shipped. Orders over $10 000 need manager approval."*

Three findings, anchored and ranked:

```json
{ "axis": "model", "depth": "structural",
  "anchors": ["EJ-10", "EJ-11", "DDD-Entity"], "element": "Customer",
  "title": "Customer is an entity (stable id, lifecycle), not a value" }

{ "axis": "model", "depth": "structural",
  "anchors": ["EJ-17", "DDD-ValueObject"], "element": "Money",
  "title": "Model the order total as an immutable Money value (amount, currency), not a bare number" }

{ "axis": "behaviour", "depth": "structural",
  "anchors": ["FP", "SOLID-O", "DMN"], "element": "ApprovalDecision",
  "title": "Approval is a derived decision (DMN table on order total), not a stored flag —
            confirm paradigm via paradigm-fit.md before emitting" }
```

The full `findings.json` shape (`current`, `proposed`, `abstraction_cost`, `risk`, `component`, …) lives in `agents/domain-extractor.md`; this file governs only the `axis`, `depth`, and `anchors` fields.
