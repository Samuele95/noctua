# Engine source — per-capability reasoner

The same decomposition pattern that splits the data model into per-entity HTML
files, applied to the inference engine. The reasoner that runs inside every
composed `model.html` is assembled from the files under this directory.

```
engine-source/
├── meta.json                            # capabilities in load order
├── viewer-template.html                 # one-pane viewer shell + placeholders
└── capabilities/
    ├── 00-core/
    │   ├── logic.js                     # initReasonerState + seedAssertedFacts + runReasoner
    │   ├── meta.json                    # auto-derived: id, title, exports
    │   ├── viewer-meta.json             # human-authored: title, description, defaultKB
    │   └── viewer.html                  # built — open in browser, runs reasoner
    ├── 10-subclass-closure/             # RDFS9 transitive subClassOf
    ├── 15-class-membership-inheritance/ # RDFS2: x ∈ A, A ⊑ B → x ∈ B
    ├── 20-subproperty-closure/          # RDFS5 transitive subPropertyOf
    ├── 30-property-characteristics/     # Symmetric, Transitive, InverseOf
    ├── 40-swrl-forward-chain/           # SWRL antecedent matching + firing
    └── 50-consistency/                  # post-fixpoint contradictions pass
```

## The flow

```
   ┌───────────────────────────┐
   │ scripts/explode_engine.py │   slices the engine block out of any
   │                           │   composed HTML or assets/template.html
   └────────────┬──────────────┘
                ▼
   engine-source/capabilities/<id>/logic.js
                │
                ▼
   ┌───────────────────────────┐
   │ scripts/compose_engine.py │   reassembles the engine and substitutes
   │                           │   it back at the @ENGINE_BLOCK markers
   └────────────┬──────────────┘
                ▼
   assets/template.html (or any model.html with the same markers)
                │
                ▼
   ┌───────────────────────────┐
   │ scripts/build_viewers.py  │   generates one standalone viewer per
   │                           │   capability — self-contained, runnable
   └────────────┬──────────────┘
                ▼
   engine-source/capabilities/<id>/viewer.html
```

## How to use the viewers

Open any `capabilities/<id>/viewer.html` in a browser. The viewer:

- Embeds the **full reasoner** (assembled from every `logic.js`) plus a
  **default KB** chosen to demonstrate this capability.
- Shows the **KB editor** on the left (live: typing re-runs the reasoner).
- Shows the **inferred facts** on the right, with this capability's
  provenance kinds **highlighted** so its effect is visible against the
  baseline of other inferences.
- Surfaces a **Contradictions** banner at the top if the consistency pass
  finds anything.
- Offers **Save snapshot** (downloads a new viewer.html with the current KB
  baked in as the snapshot's own "original") and **Revert** (restores the
  KB that shipped in this file).

The shipped `viewer.html` is the source of truth — it is the snapshot of the
current capability + KB at build time. Every user operation either creates a
new snapshot file or modifies the working textarea with revert always
available. The original is never silently mutated.

## Round-trip discipline

Round-trip is symmetric with the data layer:

| Direction | Engine | Data |
|-----------|--------|------|
| explode | `explode_engine.py model.html → engine-source/` | `explode_model.py model.html → source/` |
| compose | `compose_engine.py engine-source/ → model.html` | `compose_model.py source/ → model.html` |

Validator invariant 12 already exercises the engine round-trip for every
composed model: it renders Turtle/RDFS/N-Triples/RDF/XML, re-parses each,
and demands the rdfs:subClassOf triple count matches the canonical. A
broken engine block fails the invariant.

## Modifying a capability

Edit the capability's `logic.js`, then:

```bash
# 1. Recompose the template
python3 scripts/compose_engine.py assets/engine-source \
    --target assets/template.html \
    --out assets/template.html

# 2. Rebuild the viewers (so the new logic is embedded in each viewer's
#    inlined engine block too)
python3 scripts/build_viewers.py
```

Validate any composed model.html after — invariant 12 catches projector +
engine regressions.

## Threat / sharing model

Every viewer is a single-user offline HTML opened from `file://`. The KB
editor accepts user-typed JSON-LD; the reasoner runs in the same page; no
network calls, no shared state. The XSS attack surface that `innerHTML`
would represent in a web context doesn't apply — the user can already
execute arbitrary JS by editing the HTML. Escaping is for output sanity
(well-formed display when names contain `<` etc.), not a security boundary.
