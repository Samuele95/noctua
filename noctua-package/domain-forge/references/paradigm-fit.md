# Paradigm fit — which language for which question?

The skill ships three rule/decision layers — **DMN**, **Prolog/Datalog/Horn**, and **SWRL** (over OWL/RDFS). They are not additive depth knobs. They are competing paradigms with different expressive limits. Choosing wrong is a modelling defect even when the result "works": you ship a brittle table, an unmaintainable rule, or a property that silently contradicts itself.

This reference is the **paradigm-fit checklist** the extractor must run *before* a decision/rule finding is applied. It is anchored to feedback from the Knowledge Engineering course (Hinkelmann, FHNW): see the `ke.html` study guide and the worked admission example, where the same domain is encoded in all three paradigms to show exactly what each one can and cannot do.

## The six axes that decide it

| Axis | DMN | Prolog (closed world) | SWRL / RDF rules (open world) |
|---|---|---|---|
| **State** | Stateless. One record in → one decision out. | Stateful KB; can query across all asserted facts. | Stateful graph; can match across all asserted triples. |
| **Goal direction** | Forward only, one decision per call. | **Backward-chaining** from a goal; backtracking enumerates answers. | **Forward-chaining** only; the engine asserts every conclusion that fires, no goals. |
| **Monotonicity** | Per-call deterministic via hit policy. | **Negation-as-failure** (`\+`) → closed-world defaults work. | **Monotonic.** No negation, no overwrite, no default — once asserted, a triple stays. |
| **Cross-record reasoning** | **No.** Cannot compare row A to row B. Cross-record logic belongs *before* DMN. | **Yes.** Two `transaction(T,…), transaction(T2,…), T \= T2, …` calls express "there exists another …". | **Yes for inference** (two `?vars` bound to different individuals), but **not goal-directed**: you cannot ask "is there a fraudulent T?", you only assert it. |
| **Result cardinality** | **Hit policy** controls: `U`/`A`/`P`/`F` → one row; `C`/`R`/`O` → many. | Multiple solutions natural; lists OK as a single solution (e.g. `premaster(Sarah, [bpm, ba])`). | Every firing matches; no hit policy. If two rules can derive *different* values for the same property, you derive *both* — usually a bug. |
| **External access** | **No.** No DB lookups, no service calls. | Yes (the KB *is* a database; query via Prolog). | No I/O; the graph is the world. |

## Decision order — disqualify before you tie-break

The six axes are not six equal votes you average. **Four are hard disqualifiers** — a single "yes" removes a paradigm from contention no matter what the other axes say. **Two are shaping choices** — they don't exclude a paradigm, they tell you which dialect of it to use. Run the disqualifiers first, in this order, and stop as soon as exactly one paradigm survives *for the right reason*. Do not pick a paradigm the disqualifiers ruled out and then bolt on a workaround unless the workaround is the documented one below.

**Hard disqualifiers (any single "yes" is decisive):**

1. **State / cross-record** — does the logic remember anything between calls, or compare one record to another? **Yes → DMN is OUT.** DMN sees one record per call. Select the "other" record upstream and pass it in, or use Prolog/SWRL.
2. **Monotonicity** — does the logic need a negation ("anything but X"), a default ("else 0"), or an overwrite? **Yes → SWRL is OUT directly.** SWRL is monotonic. Either invert into a positive complement class plus a baseline assertion (and *document* it), or use Prolog (`\+`, cut) or DMN (`not(...)`, default `-` row).
3. **External access** — does the rule need data that isn't in the model (a DB lookup, a service call)? **Yes → DMN cannot host it** (the value must arrive as an upstream input); **Prolog can host it only if that data is already asserted in the KB.**

**Shaping choices (they pick the dialect, never exclude a paradigm):**

4. **Goal direction** — "is *this one* X?" (goal-directed) favours Prolog's backward-chaining + backtracking; "materialise *every* X" (bulk) favours SWRL forward-chaining or one DMN call per record.
5. **Result cardinality** — unique answer → DMN `U` (prove disjointness) or a deterministic Prolog clause; many answers → DMN `C+`/`C<`/`C>` or Prolog `findall`.

(The remaining axis, **monotonicity as it bites aggregation**, is the SWRL-baseline trap detailed under "Defaults" below — it disqualifies an *un-baselined* SWRL aggregate, not SWRL as such.)

If two paradigms both survive the disqualifiers, pick the one that needs **fewer workarounds**.

## What each paradigm CAN'T express (and what to do about it)

These are the patterns the KE course flagged in feedback. The skill's extractor should recognise them and steer the finding to the right paradigm.

### "There exists another transaction with …" (cross-record query)

> *Example: "If the credit card is used in a physical store in two different countries within a 5-minute time difference, then the risk value is at least 150."*

| Paradigm | Verdict |
|---|---|
| **DMN** | **Impossible.** DMN is stateless. The "other transaction" must be selected upstream and passed in as an extra input column. The selection logic (which prior transaction? out of millions?) is not DMN's job. |
| **Prolog** | **Natural.** `risk(T, 150) :- transaction(T, Card, _, …, MerchantCountry, Time), transaction(T2, Card, _, …, OtherCountry, OtherTime), T \= T2, MerchantCountry \= OtherCountry, Time - OtherTime =< 300.` Two bindings, disequality, numeric comparison — done. |
| **SWRL** | **Possible but forward-only.** A rule with two object-property atoms binding `?t` and `?t2` plus `differentFrom(?t, ?t2)` works, but it asserts the conclusion as a triple for *every* matching pair found at inference time. You can't ask "give me one if it exists" — you have to compute the closure. |

**Rule of thumb:** if the question is goal-directed ("is *this* transaction fraudulent?") prefer Prolog. If the requirement is to materialise *all* such relations for downstream consumption, SWRL works.

### "Outside Europe" / "anything except X" (negation-as-failure)

> *Example: "If the cardholder lives outside Europe, fee = 7500."*

| Paradigm | Verdict |
|---|---|
| **DMN** | Use FEEL `not("Europe")` in the cell, or a `null` case, or a disjoint `-` row. Add a sub-decision that classifies the input first. |
| **Prolog** | `tuition(X, 7500) :- \+ residence(X, switzerland), \+ residence(X, eu).` Closed-world: "not provable" = false. Works. |
| **SWRL** | **Impossible directly.** No negation. The KE course's workaround: introduce a **positive class** like `:NonEuropeanCountry`. Type each non-European country as a member, then write: `Candidate(?c) ^ residence(?c, ?rc) ^ NonEuropeanCountry(?rc) → tuitionFee(?c, 7500)`. The negation becomes asserted class membership. |

**Rule of thumb:** if the rule body needs "not X", in SWRL you must invert it into "is in the positive complement class" — and that class needs ABox population (every actual country categorised). In Prolog you write `\+`. In DMN you write `not("Europe")` in the cell.

### Defaults / "if no special rule applies, value = 0"

> *Example: "Special risk: Swiss person uses credit card in South Africa → +30. Other transactions: no special risk."*

| Paradigm | Verdict |
|---|---|
| **DMN** | Default-row pattern: a `-` row at the bottom of a Unique table catches everything else and outputs 0. |
| **Prolog** | Order-sensitive clauses + cut, or `\+` rule, or `findall/3` then take the head. Multiple idioms. |
| **SWRL** | **Cannot default to 0.** Values cannot be overwritten. If no special-risk rule fires, no `specialRisk` triple exists at all. Two ways out: (a) **assert a baseline** `specialRisk(?t, 0)` for every `Transaction` so the SUM rule has something to add; (b) **document the limitation** in the report and use `swrlb:add` with optional inputs only when present. The KE course explicitly asks for the limitation to be documented when the choice is (b). |

**Rule of thumb:** an aggregated property (RiskScore = sum) **requires** every contributing part to be asserted for every individual the rule sees. Either assert a 0-baseline up front or accept that the aggregate is missing for individuals without all parts.

### Hit policy / multiple matching rules

> *Example: a query "what are the risks for a shop in Italy?" can match three rules (Italy → 10, Europe → 20, Africa → 60).*

| Paradigm | Verdict |
|---|---|
| **DMN** | **Hit policy decides.** `U` (Unique) forbids overlap — at most one row matches; the modeller proves disjointness. `F` (First) returns the first match in rule order — fragile, requires the modeller to think in rule-order terms. `C+`/`C<`/`C>`/`C#` collect into sum/min/max/count. Prefer `U` and prove disjointness via intervals + `-`. The course feedback consistently questions `F`. |
| **Prolog** | Every matching clause provides an answer via backtracking. The application decides whether to keep the first or collect all. |
| **SWRL** | **Every** matching rule fires and asserts. If two rules derive different values for the same functional property, you derive both — usually a contradiction. |

**Rule of thumb:** if the requirement is "exactly one answer" → DMN `U` or Prolog with a deterministic clause + cut; if "all answers" → Prolog `findall` or DMN `C+`; if "the highest" → DMN `C>`.

### Aggregation (sum, count, max)

| Paradigm | Verdict |
|---|---|
| **DMN** | DMN `C+` (Collect — sum) or compose via a top-level decision whose expression literally adds: `riskScore = amountRisk + merchantRisk + cardholderRisk`. The course feedback's "good example" is exactly this: skip the 27-combination table, compute the sum in one node. |
| **Prolog** | `aggregate_all(sum(R), risk_part(T, R), Total)` or hand-roll. |
| **SWRL** | `swrlb:add(?total, ?amount, ?merchant, ?cardholder)` — only works if every part is asserted (see "defaults" above). |

## Where does each *property* belong?

This is anchored to KE-course feedback (Milestone 3 slide 2 in particular): *the individual risk values should be properties, and they belong on the concept whose change drives the value's change.*

- `MerchantRisk(60)` is **the same for every transaction of that merchant** → `Merchant → merchantRisk → 60`, not `Transaction → merchantRisk → 60` (which duplicates the same value across every transaction touching that merchant).
- Don't reify into an intermediate `Risk` node (`<Transaction> → <Risk> → MerchantRisk 60`) unless multiple distinct risks of the same kind coexist per transaction. The intermediate adds a blank node without expressing anything new.
- Cardholder is **connected to Transaction via Credit Card**, not directly: `Transaction --used--> Creditcard --hasCardholder--> Cardholder`. The shortcut edge `Transaction → hasCardholder → Cardholder` hides the real entity and breaks the moment a card has multiple cardholders or a cardholder has multiple cards.

## Intermediate-entity rule

If A relates to C only through B in the domain, **model the chain A→B→C explicitly**. Don't write a shortcut edge A→C. The chain:

- Makes blame attributable when one link changes (e.g. card reissued)
- Lets B carry its own attributes (card expiry date, scheme, …)
- Survives many-to-many fan-out (one card, many cardholders)

## The paradigm-fit gate — what the extractor must do

For every finding whose `axis = behaviour` or whose `ke_form` mentions a decision/rule:

1. Identify which of the six axes the finding's logic touches (state, goal direction, monotonicity, cross-record, cardinality, external access).
2. Look up the column above. If two columns both work, pick the one that requires fewer workarounds.
3. If the user asked for `--layers dmn` but the logic is cross-record or goal-directed, **flag the mismatch** in the finding's detail block and recommend `--layers rules` (Prolog/Horn) or `--layers swrl` instead. Don't silently force the wrong paradigm.
4. If the logic involves an aggregated property (sum/count/max), check that **every contributing part has a baseline** for the SWRL case. If not, surface the gap in `§6 Open modelling questions` of the blueprint.
5. If a property is being added to `Transaction` that is actually a property of `Merchant` / `Cardholder` / `CreditCard`, **move the property to the upstream concept** and document the move.
6. If two decision tables look like the same lookup (e.g. Country → Continent twice), **extract a BKM** instead of duplicating.

## What to emit — the `paradigm_fit` block

Running the gate is only half the job. For every gated finding the extractor must attach a `paradigm_fit` block, in **exactly** this shape — the orchestrator renders it verbatim as the Paradigm-fit panel and compares `Recommended paradigm` against the finding's proposed layer:

```
State: <stateless | per-record memory needed | cross-record>
Goal direction: <bulk inference | goal-directed query>
Monotonicity: <pure addition | needs default | needs overwrite | needs negation>
Cross-record reasoning: <no | yes>
Result cardinality: <unique | many>
External access: <none | upstream data>
Recommended paradigm: <DMN | Prolog/Horn | SWRL | upstream-of-DMN>
Reason: <one sentence, citing the decisive axis>
```

Rules for the block:

- **Every axis gets a verdict — no blanks.** If the idea text doesn't determine an axis, follow "When an axis is undetermined" below; never leave it empty and never guess silently.
- **`Recommended paradigm` must be consistent with the disqualifiers.** If `Cross-record reasoning: yes` you may not recommend DMN. If `Monotonicity: needs negation | needs default` you may not recommend SWRL without naming the documented workaround. If `External access: upstream data`, DMN may only consume the value, not fetch it.
- **`Reason` cites the *decisive* axis** — the disqualifier that settled it — not a restatement of the finding's text.

## Worked example — one finding through the gate

> Finding: *"If the credit card is used in a physical store in two different countries within a 5-minute time difference, the risk value is at least 150."* User ran `--layers dmn`, so the proposed layer is **DMN**.

Walk the disqualifiers, then the shaping axes:

- **State / cross-record** — the rule references *another* transaction on the same card → cross-record. **DMN is out.**
- **Monotonicity** — no negation, no default, no overwrite; it asserts a risk floor → pure addition.
- **External access** — both transactions are already in the KB → none.
- **Goal direction** — the intent is to flag *this* suspicious transaction → goal-directed.
- **Result cardinality** — one verdict per transaction under test → unique.

The cross-record disqualifier alone settles it. Emit:

```
State: cross-record
Goal direction: goal-directed query
Monotonicity: pure addition
Cross-record reasoning: yes
Result cardinality: unique
External access: none
Recommended paradigm: Prolog/Horn
Reason: the rule compares two transactions on the same card (cross-record), which DMN's stateless one-record-per-call model cannot express.
```

Proposed layer (DMN) ≠ recommended (Prolog/Horn), so the finding is flagged for reshape per step 3 above: move it to `--layers rules`, or pass the prior transaction in as a pre-selected DMN input column. Do not silently emit it as DMN.

## When an axis is undetermined

The idea text will sometimes not say whether a query is goal-directed or bulk, whether a value can be overwritten, or whether cross-record comparison is intended. **Do not collapse the ambiguity by guessing** — that is exactly the silent defect this gate exists to prevent. Instead:

1. **Set the axis to the value that is safest if you're wrong** — the reading whose paradigm has the widest expressive range for that axis. Undetermined goal-direction → assume goal-directed (Prolog, which can also materialise). Undetermined monotonicity → assume a default may be needed (avoid bare SWRL, or add the baseline).
2. **Write `Recommended paradigm` for that safe reading**, so the emitted block is still internally consistent.
3. **Add the unresolved axis to `§6 Open modelling questions`** in the blueprint, phrased as a question the user can answer — e.g. *"Is the 5-minute rule meant to flag one suspicious transaction, or to label all of them?"*

A flagged-but-conservative recommendation is the correct output. A confident recommendation built on a silent guess is the defect.
