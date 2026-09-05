# /domain-forge project memory

This file persists across /domain-forge runs. It records modeling decisions,
stances, naming conventions, and applied/declined findings so the extractor
does not re-propose decided modeling work or rename stable IRIs. Edit by hand
if the extractor gets something wrong.

## Modeling stances
<!-- Domain-level commitments. Examples:
       "Money / identifiers / dates are value objects (no identity)"
       "Billing and Catalog are separate bounded contexts"
       "Payment gateway is external — modeled as a boundary, not detailed"
       "Prefer composition; subClassOf only for true is-a subsets" -->

## Naming conventions
<!-- Stable IRIs and the namespace. Never silently rename these.
     Example:  base IRI = http://example.org/<project>#
               Transaction, not Txn; LineItem, not OrderLine -->

## Decisions
<!-- One short paragraph per architectural-depth decision, linking the
     commit file in .claude/domain-forge-decisions/. -->

## Applied
<!-- YYYY-MM-DD | <anchors> | element | depth | one-line title
     Anchors: EJ-N (Bloch items); SOLID-S/O/L/I/D; GoF-<pattern>; FP;
     DDD-Entity/ValueObject/Aggregate/BoundedContext/AntiCorruption;
     HEX; DMN; HORN; FEEL-interval. -->

## Declined
<!-- YYYY-MM-DD | <anchors> | element | depth | title — reason -->

## Out-of-scope
<!-- Concepts deliberately not modeled, with why. -->

## Dataset stances
<!-- Written by /dataset-forge, read by both forges, /data-lens and /dataset-shaper. One line per decision:
       YYYY-MM-DD | <dataset> | retype zip: nominal — postal code parsed as integer
       YYYY-MM-DD | <dataset> | cycle price-qty-total: basis = unit_price, qty (total derived)
       YYYY-MM-DD | <dataset> | partition: late (leakage: delivered_days)
       YYYY-MM-DD | <dataset> | out of scope: note (free text, no embedding requested) -->

## Analysis stances
<!-- Written by /data-lens, read by /data-lens and /dataset-shaper. One line per fact the
     user asserted or a turn settled:
       YYYY-MM-DD | <dataset> | outliers unit_price > 900 genuine (premium SKUs)
       YYYY-MM-DD | <dataset> | delivered_days missing: MAR on zip -->

## Shaping stances
<!-- Written by /dataset-shaper. One line per fork resolved:
       YYYY-MM-DD | <dataset> | S6 impute delivered_days: group-median by zip, indicator
       YYYY-MM-DD | <dataset> | split: stratified on late, 70/10/20 -->
