# Dataset → ontology mapping

This file is to `/dataset-forge` what `references/bloch-mapping.md` is to `/domain-forge`: the modeling vocabulary of the source. Domain-forge reads a software domain out of prose with Bloch and DDD; dataset-forge reads a *space* out of a table, and the ontology it emits is shaped so that the domain-forge engines can verify what the analysis claims. Read it once, at the point where the typed columns and the proposed derivations become Turtle. The HTML mechanics (which `<script>` blocks, the JSON-LD mirror, the SWRL atom shapes, the Horn grammar) stay in domain-forge's `references/html-contract.md`; this file only says *what* goes in them.

## The one-sentence design

The dataset is an A-box over a T-box you derive from its columns: one class for the row kind, one data property per column, nominal columns as classes with individuals, identifiers as inverse-functional properties, lookups as functional object properties, and every proposed derivation as a rule the reasoner can fire on a declared sample of rows. Every choice below exists to make a claim of the analysis *checkable by an engine* rather than asserted in prose.

## Mapping table

| Column role (from step 0) | Ontology element | Why this and not something else |
|---|---|---|
| the row itself | `ex:Record a owl:Class` (rename to the entity the rows are — `ex:Order`, `ex:Flow` — when the dataset has one obvious row kind; keep `Record` when it does not) | one class per row kind; a dataset with several row kinds mixed in one table is a `WARN:` and a modeling question, not two classes guessed from a column |
| numeric, ordinal, date, free-text dimension | `owl:DatatypeProperty` with `rdfs:domain ex:Record` and an `xsd:` range (`decimal`, `integer`, `date`, `dateTime`, `string`, `boolean`) | one data property per column keeps the derivation rules literal: `total = unit_price × qty` is three data properties, one twin property and one SWRL rule, with no intermediate entity to explain |
| low-cardinality nominal (a handful of values that name kinds) | a class per column (`ex:Region`) with one `owl:NamedIndividual` per value (`ex:Region-North`), disjoint classes when the values are mutually exclusive kinds, and an `owl:ObjectProperty` `ex:region` from `ex:Record` to it | individuals make the value a node the reasoner and SPARQL can join on; disjointness lets the consistency pass catch a row that claims two values |
| high-cardinality nominal (postal codes, SKUs) | a data property with `xsd:string` range, **not** a class per value | hundreds of individuals buy nothing an engine can use and bloat the diagram; the lookup that makes such a column meaningful is modeled below |
| identity (unique on every row) | `owl:DatatypeProperty ... a owl:InverseFunctionalProperty`, role `identity`, **outside the basis and outside every rule body** | a key determines every column, so it would make every dependency measure and every rule trivially true; inverse-functional is exactly the axiom that says "one value, one record", and the consistency pass enforces it |
| foreign key (repeated identifier of another entity) | `owl:ObjectProperty` to a second class (`ex:Customer`) whose individuals are the distinct key values, role `key`, outside the basis | it is a dimension of the *other* entity; recording it as an object property says so without inventing that entity's attributes |
| degenerate / constant column | recorded in `typing` with role `degenerate`; no property | a constant spans nothing |
| lookup hierarchy (`zip → city → region`, a chain of exact functional dependencies) | intermediate classes (`ex:City`, `ex:Region`) with individuals; object properties `ex:zipCity`, `ex:cityRegion` declared `owl:FunctionalProperty`; the Horn clause that derives the higher level from the lower | the functional dependency the script measured becomes an axiom the consistency pass can *violate* — a row with a zip that maps to two cities is a contradiction card in the Logic tab, not a number in a table |
| numeric derivation (`total = unit_price × qty`, `subtotal = total × (1 − discount/100)`) | a SWRL rule in `model-swrl` with `swrlb:multiply` / `add` / `subtract` / `divide`, whose consequent is a **twin property** on the same `?r` (`ex:derived_total`, declared like `ex:total`), never the stored property | the stored column stays what the dataset asserts; the twin is what the reasoner computes; `run_query.py --engine swrl` counts rows where the two agree — a rule that wrote into `ex:total` would only re-assert an existing triple and verify nothing |
| threshold classification (`late ⇔ delivered_days > 7`) | a SWRL rule with `swrlb:greaterThan` (or the matching comparator) whose consequent is a **class** (`ex:LateOrder rdfs:subClassOf ex:Record`), plus the boolean data property the dataset actually carries | the class is what the reasoner infers; the data property is what the dataset stores; the rule's symbolic verification is "every sampled row typed `LateOrder` has `late = true` and vice versa" — a SPARQL count over the reasoned graph |
| non-numeric mapping (`city` from `zip`, `age` from `birth_date`, a string normalisation) | a Horn clause in `model-horn`, verified through `run_query.py --engine prolog` | SWRL here has no string, date or list built-ins (domain-forge `ke-vocabulary.md` § *Not implemented*); a rule no engine can fire is a claim, not a verification, and is recorded `symbolic: untested` |
| free text | a data property with `xsd:string` range, profiled in `stats`, **outside the span** unless the user asks for an embedding | text has no numeric form for the empirical channel and no rule form for the symbolic one; saying so is better than pretending a length statistic is a dimension |

## Component grouping

Every class carries `ex:component`. Group by the **dimension the column belongs to**, not by column type: the price/quantity/total cycle is one component, the geography lookup chain another, the delivery/lateness pair a third, the row class and its identifiers a fourth. A component is what `extract_component.py` can lift out alone, and what the derivation graph in the Geometry tab will cluster — the two views should agree.

## The A-box sample

The A-box is `abox_sample.rows` from `geometry.py` (default 200 rows, deterministic seed), one `owl:NamedIndividual` per row with the IRI `ex:Record-<index>` where `<index>` is the row's index in the source file, so a row in the explorer, a row in the Turtle and a row in the CSV are the same row. Nominal values point at their individuals (`ex:region ex:Region-North`); everything else is a typed literal. Keep the sample at the size the browser reasoner can chain over — the `--sample` flag exists because a 5 000-row A-box turns "Run reasoner" into a hang.

## Provenance in the Turtle

Declare an ontology node right after the prefixes and annotate it:

```turtle
<http://example.org/orders> a owl:Ontology ;
    ex:sourceKind "dataset" ;
    ex:sourcePath "orders.csv" .
```

The validator accepts it (no class/property invariant touches an `owl:Ontology` node), and it is what lets `/domain-forge`'s refine mode recognise a dataset ontology and keep its Bloch/DDD findings off it. The `geometry` layer's `produced-by: /dataset-forge` header is the second, redundant signal.

## What not to model

Do not invent an entity the columns do not carry (a `Product` class because there is a `unit_price`): the dataset has a price per row, and that is all the ontology may say. Do not turn a near-collinear pair (`weight_kg ≈ qty × hidden unit weight`) into a rule — it is a *disagreement* entry in the geometry layer, and the honest reading is a hidden dimension. Do not model `nn-data` or any downstream artifact inside this ontology; the hand-off is a separate file.
