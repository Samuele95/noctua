# Noctua — site outline (C0)

The site is one landing page plus one docs page per stage. Every line below names the message
the section carries and the file that makes it true. Nothing is on this page that a source does
not say; where a source hedges ("sketch", "external", "not part of this package"), the site hedges
with the same word.

Reading order used to build it: `CHANGES-v3.md` → `noctua/SKILL.md` → `noctua/references/chain-map.md`
→ the nine `SKILL.md` frontmatter descriptions → `NOCTUA-PROMETHEUS-REPORT.md`, `BUILD-PLAN.md`,
`domain-forge/references/future-skills.md`.

---

## Landing — `index.html`

### 0. Header
**Message.** Noctua, a family of Claude Code skills; EN/IT and dark/light live here.
**Content.** Logo mark + wordmark, nav (chain · stages · verification · start · docs), language toggle, theme toggle.
**Source.** Brand is ours. The name is `noctua/SKILL.md` (skill name) — the owl reading is stated as ours in the brand note, not as a package claim.

### 1. Hero
**Message.** Noctua is the owl over a neurosymbolic analysis chain: nine stages that take a codebase, a schema, prose or a dataset and hand back a model whose engines can be run — the LLM proposes, the symbolic engines verify.
**Content.** One sentence of positioning, one sentence of mechanism, two actions (see the chain · get started), and the chain's own shape as the visual.
**Source.** `noctua/SKILL.md` § "/noctua — the owl over the chain" (nine skills, orchestrator not analyst); `domain-forge/SKILL.md` § The platform (the model's own SPARQL / SWRL / Prolog / DMN engines); `noctua/references/chain-map.md` § Source kinds (codebase, data-project, database, prose, dataset, model, blueprint).
**Not said.** No performance claim, no "powered by AI", no benchmark. The package makes none.

### 2. The chain — the centrepiece
**Message.** Sources become artifacts through stages, and every stage says what it consumes, what it produces, how its product is checked and where it stops for a human.
**Content.** Interactive diagram rendered from `content/chain.json`: seven source kinds on the left, ten stage rows, five lanes that light up on hover/focus; selecting a stage opens its consumes / produces / check / gate / unattended / re-run panel. Keyboard navigable; the same information is readable as a table when motion is off.
**Source.** `noctua/references/chain-map.md` §§ Source kinds, Stages, Lanes, Reading a model's position from its layers — transcribed into `content/chain.json`, nothing added.
**Note.** Ten stage rows, nine skills: `forge-prose` and `refine` are both `/domain-forge`. The site says so rather than rounding.

### 3. What the orchestrator does
**Message.** `/noctua` routes, invokes, verifies and records — it never does a stage's work, and it asks what the lane is *for* before proposing anything.
**Content.** The delegation rule quoted; the destinations table (what you get · what it runs · what it does **not** give you); the ledger `.claude/noctua-ledger.md` as chain state, separate from the forges' memory.
**Source.** `noctua/SKILL.md` §§ The delegation rule, Trigger and arguments, Procedure steps 4–8; `chain-map.md` § Destinations; `noctua/references/ledger-contract.md`.

### 4. The stages — the grid
**Message.** Nine skills, each with one job, each stated in its own words.
**Content.** Nine cards. Eight from the `SKILL.md` frontmatter `description` of `spec-analysis`, `domain-forge`, `dataset-forge`, `data-lens`, `dataset-shaper`, `inferred-questions`, `model-chat`, `blueprint`; the ninth, `document-project`, from its chain-map row only and labelled **external — not part of this package**. Each card links to its docs page. `/noctua` sits above the grid, not in it.
**Source.** the nine `SKILL.md` frontmatter descriptions; `chain-map.md` § Stages row `document`.
**Also labelled external.** `effective-java`, blueprint's anchor corpus — `chain-map.md` § Stage prerequisites.

### 5. How it verifies
**Message.** The claims in this framework are checked by machines, and the numbers are published.
**Content.** Four facts, each with its number: the artifact is one self-contained HTML with its engines inside (SPARQL / SWRL / Prolog / DMN, no network deps); every chain skill is a pure function over that file — input read-only, output a strict superset, `strip(apply(x)) == x` byte-for-byte; the validator's invariants 1–19, of which 13–16 are the layer-chain invariants; the acceptance suite at **78 passed / 0 failed**, three static verifiers at SHIP, `validate_model.py` 16 passed / 2 warned / 0 failed on the v2 example.
**Source.** `CHANGES-v3.md` (opening paragraph, § Verifiche eseguite, § La build (B1–B8) — eseguita); `domain-forge/references/future-skills.md` § The architectural principle and § The platform scripts; `domain-forge/references/html-contract.md` line 3.
**Hedges kept.** The 2 warnings were rdflib and a browser absent in that sandbox — said, not dropped. B7 on the real CIC-IDS2017 folder was **not** executed; the equivalent ran on a synthetic folder of the same shape — said.

### 6. Get started
**Message.** Copy nine folders into your skills directory, have Python and a headless Chromium, then run `/noctua`.
**Content.** The install line (package folders replace the v2 ones; `effective-java` stays as it is, an external dependency of blueprint), the environment requirements, the first command, and what `/noctua` does on a first run (creates the ledger, classifies sources, asks the destination once per lane).
**Source.** `NOCTUA-PROMETHEUS-REPORT.md` § Consegna (install list); `BUILD-PLAN.md` § Requisiti di ambiente; `noctua/SKILL.md` §§ Trigger and arguments, Procedure 1–4.

### 7. Sketches — what is specified but not built
**Message.** Four chain skills exist as design sketches only, and the site says sketch because the source says sketch.
**Content.** `instance-create`, `code-implement`, `countergen`, `model-diff` — one line each, marked *sketch*. `architect` and `improve` named as skills Noctua never schedules on its own initiative.
**Source.** `domain-forge/references/future-skills.md` § Who consumes it (status column); `chain-map.md` § Stages closing note.

### 8. Footer
**Message.** Who made it, in what context, and where the package is.
**Content.** Samuele "Delta" Stronati · Knowledge Engineering, Università di Camerino · package download (`noctua-v3_1.zip`) · repository link · language and theme toggles repeated.
**Source.** Delta (supplied at C7 for the repo URL); the package file is in this repo.

---

## Docs — `docs/<skill>.html`, generated by `tools/build_docs.py`

One page per stage, nine pages. Each carries: the skill's own `description` verbatim, in English,
inside `lang="en"` (it is the skill's source text, not UI copy); the trigger and flags read from
the `SKILL.md`; the chain-map row (consumes · produces · orchestrator's check · human gate ·
unattended behaviour · re-run flag); its position in the lanes; and a link to the source
`SKILL.md` in the package. `document-project` has no `SKILL.md` here: its page is built from the
chain-map row alone and is labelled external, and it links to that row instead.

The generator reads the package and writes `docs/`, so the pages cannot drift from the source;
its output is committed.

---

## 404

**Message.** The owl looked; there is nothing here.
**Content.** Mark, one line, links back to the chain and the stage index. Same brand, same toggles.

---

## What is deliberately absent

- Any number the package does not state (no "10× faster", no user counts, no benchmarks).
- Any claim that a sketched skill works.
- Any suggestion that `document-project` or `effective-java` ships in this package.
- Any wording that makes `/noctua` sound like it does the analysis — it routes, invokes, verifies, records.
