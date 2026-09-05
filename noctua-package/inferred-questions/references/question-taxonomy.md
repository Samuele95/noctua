# Question taxonomy — what each category looks like

Reference catalogue of the question categories the extractor uses. Each
section gives:
- **Detection rule** (mechanical or judgmental) — the signal that triggers
  a question in this category.
- **Source kind** — the `source_kind` value the question carries.
- **Severity bias** — how the extractor should default the severity.
- **One-line question template** — a shape the extractor adapts; never
  copy verbatim, always anchor in the actual model element.

The extractor must surface a real example pulled from the input HTML.
Generic boilerplate questions are useless.

---

## boundary

Two rules or restrictions abut an exact value without overlap; or a
restriction is one-sided.

**Detection.**
- DMN: two rules whose intervals share an endpoint (`[a..b)` and `[b..c)`
  share `b`). Ask which fires for exactly `b`. (In FEEL, `)` means
  exclusive so the first rule does NOT include `b`, the second does — but
  the human modeller often did not write that intentionally.)
- DMN: a numeric input dimension with rules covering a strict subset of
  the natural domain, with no `else` and no `--`/`-` catch-all rule. The
  boundary at the lower end of the covered subset is suspect.
- OWL: an `owl:Restriction someValuesFrom` on a property whose A-box has
  only one individual satisfying the restriction — the restriction is
  technically met, but fragile.

**Source kind.** `dmn-decision` (typical), `iri` (for OWL).

**Severity.** Usually `high` for DMN (the boundary case will be hit in
production); `medium` for OWL fragility.

**Template.** "Decision `<id>` boundary at <value>: the rule
`[<lo>..<hi>)` excludes the endpoint while `[<hi>..<next>)` includes it.
Is the asymmetry intentional?"

---

## coverage-gap

The union of rule input-regions misses a region inside the natural domain.

**Detection.**
- DMN: enumerate the rule intervals for each numeric input. Compute the
  union. If the union does not cover `[domain_min..domain_max]` (where
  `domain_min` is `0` for non-negative inputs like amounts, otherwise
  `-∞`), flag the missing region.
- SWRL: a rule's antecedent depends on a class whose `@graph` shows zero
  members → the rule never fires (a different shape of coverage gap).
- Horn: a predicate appearing in a clause body but never as a head — it
  needs an A-box assertion or it can never bind.

**Source kind.** `dmn-decision`, `swrl-rule`, `horn-clause`.

**Severity.** `high` if the gap is in the middle of the domain (e.g. DMN
covers `[1000..)` and the modeller forgot `[0..1000)`). `medium` if the
gap is at the natural boundary (negative values for an amount; the modeller
may have ruled these out implicitly).

**Template.** "Decision `<id>` covers <intervals> but not `<missing>`.
Is the uncovered region meant to be zero, or an unmodelled state?"

---

## rationale-gap

A rationale block names something not modelled.

**Detection.**
- Read each rationale block (likely under `#model-rationale` or rendered
  as HTML blocks with `data-rationale-id`).
- Phrase patterns that indicate a gap:
  - **External-system mention**: "the payment gateway", "the external
    auth service", "the upstream queue". If no class with that name (or
    obvious synonym) exists in the T-box, the gap is *what happens when
    that external system fails/delays/lies*.
  - **Deferral phrases**: "for now", "out of scope", "we'll address
    this", "we don't model X yet". Each deferral is a question
    ("why deferred? when revisited?").
  - **Invariant claims**: "X is immutable", "Y is unique", "Z must
    always". Check the T-box for `owl:FunctionalProperty`,
    `owl:InverseFunctionalProperty`, value-object framing. If absent,
    the claim is not enforced — question.

**Source kind.** `rationale`.

**Severity.** `medium` is the default. Bumps to `high` if the named
unmodelled thing is a failure mode of a core decision (e.g. external
gateway feeding a high-severity DMN decision). Drops to `low` if the
deferral is clearly cosmetic ("we'll prettier-print the labels later").

**Template.** "Rationale `<id>` names `<thing>` as `<external|deferred|
invariant>` without modelling its `<failure|policy|enforcement>`. What
is the intended behaviour?"

---

## restriction-edge

OWL restrictions whose A-box just barely satisfies them.

**Detection.**
- For each `owl:Restriction someValuesFrom <Class>`, count A-box
  individuals satisfying the restriction. If the count is exactly 1, the
  restriction is fragile — losing that one individual breaks it.
- For `owl:Restriction allValuesFrom <Class>`, scan the A-box for any
  edge that would violate the restriction; flag near-misses.
- Cardinality restrictions (`owl:minCardinality`, `owl:maxCardinality`)
  where the A-box sits exactly at the boundary.

**Source kind.** `iri`.

**Severity.** `medium`. A restriction-edge is informational — it tells
the modeller the model is tight in a way that may surprise them.

**Template.** "Restriction `<id>` requires `<rest>`, and the current
A-box satisfies it with exactly one individual. Was a tighter or looser
form intended?"

---

## multi-typing

Disjointness clashes with implied use cases.

**Detection.**
- For each pair `(A, B)` with `owl:disjointWith` between them: look at
  the rationale, markdown, or DMN inputs for any indication that some
  real-world object might be both `A` and `B`. Hard to detect mechanically
  — judgment-driven. Examples:
  - `Person disjointWith Merchant`, but rationale mentions "internal
    employees who purchase".
  - `Asset disjointWith Liability` in a finance model, but the rationale
    mentions "convertible bonds" or "contingent positions".

**Source kind.** `iri`.

**Severity.** `medium` to `high` depending on how central the disjoint
pair is.

**Template.** "Classes `<A>` and `<B>` are declared `owl:disjointWith`,
but `<rationale-snippet>` implies an instance that belongs to both. Add
a common superclass, weaken the disjointness, or document why the
exception is impossible."

---

## functional-race

A functional property whose A-box already has (or under the rules could
have) multiple values per subject.

**Detection.**
- For each `owl:FunctionalProperty p`: scan the A-box for any subject `s`
  with more than one assertion of `p`. If found → high-severity question.
- For each `p`: scan SWRL/Horn rules that infer `p(s, v)` for some `s, v`.
  If multiple rules could fire for the same `s` with different `v`, flag.

**Source kind.** `iri`.

**Severity.** `high` if the A-box already shows a conflict; `medium` if
it is only a derived rule possibility.

**Template.** "Property `<p>` is functional, but `<reason>`. Two values
for the same subject is a contradiction — does the modeller want stricter
inputs, or to remove the functional declaration?"

---

## missing-individuals

A T-box class with no individuals.

**Detection.**
- For each `owl:Class C`: count individuals `i` with
  `(i rdf:type C)` in the A-box. If zero, flag.
- Bias against flagging classes that are clearly abstract — those marked
  with a rationale of "abstract type", or whose label starts with
  "Abstract", or that have only subclasses and no direct typing.

**Source kind.** `iri`.

**Severity.** `low` for purely schema-only models (no A-box at all). `medium`
if other classes have individuals but this one does not — strongly suggests
the modeller intended to populate it.

**Template.** "Class `<C>` is declared in the T-box but has no individuals
in the A-box. What is a real example, or is `<C>` intended as abstract?"

The render layer's `engine_check` with kind `class-membership` lets the
viewer dim this question when an `/instance-create` run has populated the
class.

---

## naming-stability

Provisional names still in use.

**Detection.**
- Phrase patterns in rationale: "we'll rename", "working name", "TBD",
  "placeholder".
- IRIs with naming smells: trailing `2`, `New`, `Old`, `Tmp`.

**Source kind.** `iri` or `rationale`.

**Severity.** `low`.

**Template.** "IRI `<x>` is flagged provisional in rationale `<id>`. Was
a stable name decided?"

---

## paradigm-mismatch

DDD vocabulary tag without the structural commitments.

**Detection.**
- Look for `ex:ddd "ValueObject" | "Entity" | "Aggregate" |
  "AggregateRoot" | "Repository" | "Service" | "DomainEvent"` (or
  whatever tagging convention the model uses; consult the markdown).
- For each tag, check the structural form:
  - **ValueObject**: no identifying property; equality by value.
    Identifying-property smell: a data property whose name ends in
    `Id`, `Uuid`, `Key`.
  - **Entity**: has identity.
  - **Aggregate**: has a root; external references must go through the
    root. Smell: external object properties pointing at non-root
    members.
  - **Repository**: an interface (no data properties, only object
    properties to the aggregates it manages).
  - **DomainEvent**: immutable timestamped record; should have an
    `occurredAt` property and no setters (in code terms — in OWL terms,
    a functional `dataProperty` and no incoming object properties from
    transactions that "edit" it).

**Source kind.** `iri`.

**Severity.** `medium`. Paradigm-mismatch questions push the model toward
its intended shape; not urgent but worth surfacing.

**Template.** "Class `<C>` is tagged `<DDD-kind>` but `<observed
structural detail>`. Either the tag should change or the structure
should align."

---

## When NOT to surface a question

- The concern is already in the **memory file** (Accepted findings → the
  modeller decided it; Declined findings → the modeller declined).
- The model is clearly schema-only (no A-box) and the category is
  inherently A-box-dependent (`missing-individuals`, `functional-race`,
  `restriction-edge`). One meta-question "no A-box yet — run
  `/instance-create`?" is enough; don't generate per-class questions.
- The model is a fresh `/domain-forge` output with no rationale layer
  yet. Surface a single question "no rationale present — re-run
  `/domain-forge` with `--layers all` to populate rationale?", not one
  per class.
