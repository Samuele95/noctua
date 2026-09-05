# SOURCES — every factual sentence on the site, and the file it comes from

Rule (from `SEED-BRIEF.md`): a claim that cannot be traced to a file under `./noctua-package/`
does not go on the site. This table is the trace. It is filled section by section as the pages
are written; a row exists before the sentence ships, not after.

Paths are relative to `noctua-package/`. "§" names the heading or table the claim sits in.

## Status

C4: the page is bilingual. The Italian is a translation of the English strings below, not new
copy, so **it inherits their traces**: `i18n/it.json` and `i18n/en.json` share one key set, and
`tools/check_i18n.py` fails the build if they ever diverge. See *Italian* at the foot of this file
for what deliberately stays English.

C3: `index.html` is complete and every one of its seven sections has its rows below. *Hero copy*
covers the first screen string by string (written at C2, unchanged); *The finished landing* covers
the sections C3 added. Nothing on the page is untraced.

## Landing

| # | section | claim on the site | source |
|---|---|---|---|
| 1 | hero | Noctua is a family of Claude Code skills forming a neurosymbolic analysis chain; `/noctua` is the orchestrator over it | `noctua/SKILL.md` § "/noctua — the owl over the chain"; frontmatter `description` |
| 2 | hero | The chain accepts a codebase, a data project, a database, prose, a dataset, an existing model, or a blueprint run | `noctua/references/chain-map.md` § Source kinds |
| 3 | hero | Every model is one self-contained HTML file, no network dependencies | `domain-forge/references/html-contract.md` line 3 |
| 4 | hero | The model's own SPARQL / SWRL / Prolog / DMN engines run against it; the LLM proposes, the engines verify | `domain-forge/SKILL.md` § The platform, the forges, and the chain; `model-chat` frontmatter `description` ("Every answer is produced by RUNNING the model's own engines … never by LLM speculation") |
| 5 | chain diagram | Source kinds, their recogniser and their first stage | `noctua/references/chain-map.md` § Source kinds → `content/chain.json` `sourceKinds` |
| 6 | chain diagram | Per stage: consumes, produces, orchestrator's check, human gate, unattended behaviour, re-run flag | `noctua/references/chain-map.md` § Stages → `content/chain.json` `stages` |
| 7 | chain diagram | The five lanes and their order; `questions` and `chat` are optional on every lane | `noctua/references/chain-map.md` § Lanes → `content/chain.json` `lanes`, `optionalStages` |
| 8 | chain diagram | A model's position is read from its layers, never from its file name | `noctua/references/chain-map.md` §§ Reading a model's position from its layers, Stems / naming rule |
| 9 | orchestrator | "You never do a stage's work" — the delegation rule | `noctua/SKILL.md` § The delegation rule |
| 10 | orchestrator | `/noctua` asks what the lane is *for* once per lane, and offers destinations with what each does **not** give you | `noctua/SKILL.md` § Procedure step 4; `noctua/references/chain-map.md` § Destinations |
| 11 | orchestrator | Chain state lives in `.claude/noctua-ledger.md`, separate from the forges' `.claude/domain-forge-memory.md` | `noctua/references/ledger-contract.md` § opening |
| 12 | orchestrator | `/noctua` flags: `<path>`, `--goal`, `--unattended`, `status`, `--lane` | `noctua/SKILL.md` § Trigger and arguments |
| 13 | stages grid | The one-paragraph truth about each of the eight packaged skills | each `<skill>/SKILL.md` frontmatter `description` |
| 14 | stages grid | `document-project` is external — not part of this package — and is described only by its chain-map row | `noctua/references/chain-map.md` § Stages, row `document`; the package has no `document-project/` folder |
| 15 | stages grid | `effective-java` is external too — blueprint's anchor corpus | `noctua/references/chain-map.md` § Stage prerequisites Noctua checks before invoking |
| 16 | how it verifies | Every chain skill is a pure function over the HTML: input read-only, output a strict superset, `strip(apply(x)) == x` byte-for-byte | `domain-forge/references/future-skills.md` §§ The architectural principle — pure-additive, reversible, functional; The platform scripts |
| 17 | how it verifies | The validator checks invariants 1–19; 13–16 are the layer-chain invariants | `domain-forge/references/future-skills.md` § The platform scripts |
| 18 | how it verifies | The acceptance suite passes **78 / 78**, and the v3 build is complete | `CHANGES-v3.md` § opening; § La build (B1–B8) — eseguita |
| 19 | how it verifies | Three independent static verifiers returned SHIP (dataset-shaper after one REVISE round) | `CHANGES-v3.md` § Verifiche eseguite in questa sessione |
| 20 | how it verifies | `validate_model.py` on the v2 example: 16 passed / 2 warned / 0 failed — the two warnings are rdflib and a browser missing in that sandbox | `CHANGES-v3.md` § Verifiche eseguite in questa sessione |
| 21 | how it verifies | The reproduction script is a second implementation, and its digests match byte for byte | `CHANGES-v3.md` § Cosa la build ha dimostrato (e come) |
| 22 | how it verifies | B7 on the real CIC-IDS2017 folder was not executed; a synthetic folder of the same shape was used | `CHANGES-v3.md` § Cosa resta fuori dalla build; `BUILD-PLAN.md` § opening |
| 23 | get started | Install the package's nine skill folders in place of the v2 ones; `effective-java` stays as it is | `NOCTUA-PROMETHEUS-REPORT.md` § 7 Istruzioni d'uso, point 1 (lists the nine folders: `domain-forge`, `dataset-forge`, `model-chat`, `inferred-questions`, `spec-analysis`, `blueprint`, `noctua`, `data-lens`, `dataset-shaper`) |
| 24 | get started | Environment: Python ≥ 3.10 with rdflib, numpy, pandas, scipy, scikit-learn; pyarrow, statsmodels, geopandas/pyproj/shapely optional; headless Chromium; matplotlib | `BUILD-PLAN.md` § Requisiti di ambiente |
| 25 | get started | First run: `/noctua` creates the ledger, classifies the sources, reports state, proposes the next stage and waits | `noctua/SKILL.md` § Procedure steps 1–5 |
| 26 | sketches | `instance-create`, `code-implement`, `countergen`, `model-diff` are design sketches, not implemented | `domain-forge/references/future-skills.md` § Who consumes it — the chain skills (Status column) |
| 27 | sketches | `architect` and `improve` are never scheduled by Noctua; they are named as options | `noctua/references/chain-map.md` § Stages, closing note |
| 28 | footer | The package on this site is `noctua-v3_1.zip`, the v3 package of 3 September 2026 | `CHANGES-v3.md` § title |

## Hero copy — the exact strings of the first screen

Every visible sentence of the hero, with what makes it true. (Written at C2 for the two drafts;
Delta picked hero B, and rows marked "A" describe the draft that was deleted — kept because the
wording survives in the chain section's lede.) A headline is *editorial* when
it frames a traced fact rather than asserting a new one; those rows name the fact they lean on, so
the framing can be judged separately from the claim.

| # | draft | string | source |
|---|---|---|---|
| H1 | both | "a family of Claude Code skills" (eyebrow) | `CHANGES-v3.md` § title and § Nuove — the package is nine skill folders for Claude Code |
| H2 | A | "The routing table is the product." (h1) | **editorial**, leaning on `chain-map.md` § opening: "This is the routing table `/noctua` reads." The framing is ours; the fact that the table is what the orchestrator reads is the source's |
| H3 | A | "Noctua is a neurosymbolic analysis chain." | `noctua/SKILL.md` frontmatter `description`, first clause |
| H4 | A, B | "Nine skills take a codebase, a database schema, prose or a dataset…" | `noctua/SKILL.md` § "/noctua — the owl over the chain" ("Nine skills do the work"); `chain-map.md` § Source kinds for the four inputs named |
| H5 | A, B | "…hand back one self-contained HTML model that carries its own SPARQL, SWRL, Prolog and DMN engines." | `domain-forge/references/html-contract.md` line 3 (one self-contained HTML, no network deps); `domain-forge/SKILL.md` § The platform (the model's own SPARQL / SWRL / Prolog / DMN engines) |
| H6 | A | "Below is the table `/noctua` actually reads to drive them: every stage declares what it consumes, what it produces, how its product is checked, and where it stops for a human." | `chain-map.md` § opening and § Stages (the six columns of that table) |
| H7 | B | "The owl over the chain." (h1) | `noctua/SKILL.md`, the section heading, verbatim |
| H8 | B | "The language model proposes; SPARQL, SWRL, Prolog and DMN decide." | **editorial**, leaning on `model-chat/SKILL.md` `description`: "Every answer is produced by RUNNING the model's own engines … never by LLM speculation" |
| H9 | B | "`/noctua` classifies the sources, drives the right lane stage by stage and verifies each product before proposing the next — it never does a stage's work." | `noctua/SKILL.md` frontmatter `description` and § The delegation rule ("You never do a stage's work") |
| H10 | B | figure "78 / 78 — acceptance suite" | `CHANGES-v3.md` § opening and § La build (B1–B8) — eseguita |
| H11 | B | figure "19 — validator invariants" | `domain-forge/references/future-skills.md` § The platform scripts: `validate_model.py` "invariants 1–19" |
| H12 | B | figure "0 — network dependencies" | `domain-forge/references/html-contract.md` line 3: "no network deps"; `future-skills.md` § The architectural principle, rule 3 (invariant 9, no external network refs) |
| H13 | B | "Download the package" → `noctua-v3_1.zip` | the file in this repo; it is the v3 package `CHANGES-v3.md` describes |
| H14 | B | "This is the routing table `/noctua` reads, drawn: two rails that converge…" | `chain-map.md` § opening and § Lanes (the lane diagram: the software lanes and the dataset lane meeting at `blueprint`) |
| H15 | both | "Ten stages, nine skills: `forge-prose` and `refine` are both `/domain-forge`." | `chain-map.md` § Stages — the two rows name the same skill |
| H16 | both | every stage card field (consumes · produces · orchestrator's check · human gate · unattended · re-run) | `chain-map.md` § Stages, that stage's row, via `content/chain.json` |
| H17 | both | source chip names and their `title` tooltips | `chain-map.md` § Source kinds (`kind` and `recognised by`) |
| H18 | both | the `EXTERNAL` pill on `document` | `chain-map.md` § Stages row `document`; the package has no `document-project/` folder |

## The finished landing — section by section

`index.html`, in page order. Section ids match the anchors in the page.

### `#stages` — the nine skills

| # | string on the page | source |
|---|---|---|
| S1 | "Eight of the nine ship in this package; every card below is condensed from that skill's own `SKILL.md` description, with nothing added." | the method statement itself: the cards are condensations of the frontmatter `description` of each `<skill>/SKILL.md`, shortened but not extended |
| S2 | "`/domain-forge` covers two rows of the chain map — it forges a model from prose and it refines any model — which is why ten stages are nine skills." | `chain-map.md` § Stages, rows `forge-prose` and `refine`, both naming `/domain-forge` |
| S3 | the `/noctua` card: "It reads a project, classifies its sources, reads the ledger, and drives the right lane stage by stage by invoking the specialist skills, verifying each product before proposing the next." | `noctua/SKILL.md` frontmatter `description` |
| S4 | the `/noctua` card: "It never does a stage's work — not a little of it, not the easy part." | `noctua/SKILL.md` § The delegation rule, near-verbatim |
| S5 | the `/noctua` flag chips (`<path>`, `--goal`, `--unattended`, `status`, `--lane`) | `noctua/SKILL.md` § Trigger and arguments |
| S6 | each of the eight packaged cards' paragraph | that skill's `<skill>/SKILL.md` frontmatter `description`, condensed to its leading clauses; `model-chat`'s second sentence and `domain-forge`'s "owns the model platform" are verbatim from theirs |
| S7 | each card's `consumes → produces` line | `chain-map.md` § Stages, that skill's row, via `content/chain.json` |
| S8 | the `document-project` card and its `external` pill: "Not part of this package, and described here only by its row in the chain map… the check the orchestrator runs on it is that the PDF compiles." | `chain-map.md` § Stages, row `document`; the package has no `document-project/` folder |
| S9 | every card's "source:" link target | the file itself, in `noctua-package/` |

### `#verify` — how it verifies

| # | string on the page | source |
|---|---|---|
| V1 | "One file, no network" — one self-contained HTML with no network dependencies, engines inside | `domain-forge/references/html-contract.md` line 3; `domain-forge/SKILL.md` § The platform (SPARQL / SWRL / Prolog / DMN); `future-skills.md` § The architectural principle, rule 3 |
| V2 | "Every step is reversible" — input never modified, output a strict superset, `strip(apply(x)) == x` | `future-skills.md` § The architectural principle, rules 1–2; § The platform scripts (`strip_layer.py`: "strip(apply(x)) == x byte-for-byte") |
| V3 | "Determinism is tested, not declared" — the generated standalone script is a second implementation whose outputs must match the manifest digests byte for byte | `CHANGES-v3.md` § Cosa la build ha dimostrato (e come) |
| V4 | "The validator, not the author" — invariants 1–19, of which 13–16 are the layer-chain ones | `future-skills.md` § The platform scripts |
| V4b | "a product that failed never becomes the current artifact" | `noctua/SKILL.md` § Procedure step 7 |
| V5 | "State on disk, not in a conversation" — the ledger, separate from the forge memory, read-only to Noctua | `noctua/references/ledger-contract.md` § opening |
| V6 | figure "78 / 78 — acceptance suite, 0 failed" | `CHANGES-v3.md` § opening; § La build (B1–B8) — eseguita |
| V7 | figure "3 / 3 — static verifiers at SHIP" | `CHANGES-v3.md` § Verifiche eseguite in questa sessione |
| V8 | figure "16 / 2 / 0 — validator: passed / warned / failed" | `CHANGES-v3.md` § Verifiche eseguite in questa sessione |
| V9 | figure "13 — scripts and assets built" | `CHANGES-v3.md` § La build (B1–B8): "Tredici tra script e asset" |
| V10 | caveat: the two warnings were `rdflib` and a headless browser missing from the sandbox | `CHANGES-v3.md` § Verifiche eseguite in questa sessione |
| V11 | caveat: B7 on the real CIC-IDS2017 folder was **not** executed; a synthetic folder of the same shape was used | `CHANGES-v3.md` § Cosa resta fuori dalla build; `BUILD-PLAN.md` § opening |
| V12 | caveat: PSI against permutation was a wrong test, not a wrong check, documented as a limit in `shape-contract.md` §3 | `CHANGES-v3.md` § Difetti trovati e corretti durante la build |
| V13 | caveat: `dataset-shaper` returned REVISE first and SHIP second | `CHANGES-v3.md` § Verifiche eseguite in questa sessione |

### `#start` — get started

| # | string on the page | source |
|---|---|---|
| G1 | "Copy the package's nine skill folders into your Claude Code skills directory, in place of the v2 ones" + the nine chips | `NOCTUA-PROMETHEUS-REPORT.md` § 7 Istruzioni d'uso, point 1 |
| G2 | "`effective-java` stays as it is — it is blueprint's anchor corpus, an external skill this package does not carry." | same, point 1; `chain-map.md` § Stage prerequisites |
| G3 | the environment list (Python ≥ 3.10, rdflib, numpy, pandas, scipy, scikit-learn, pyarrow, statsmodels, geopandas/pyproj/shapely, matplotlib, headless Chromium on `PATH` or `$CHROME`) | `BUILD-PLAN.md` § Requisiti di ambiente |
| G4 | what the first `/noctua` run does — creates the ledger and says so, checks the environment, classifies the sources, asks once per lane, proposes with the exact invocation, waits | `noctua/SKILL.md` § Procedure steps 1–5 |
| G5 | "offering destinations with what each one does **not** give you" | `chain-map.md` § Destinations, the third column; `noctua/SKILL.md` § Procedure step 4 |

### `#sketches` — specified, not built

| # | string on the page | source |
|---|---|---|
| K1 | the four sketches and their one-line descriptions | `domain-forge/references/future-skills.md` § Who consumes it — the chain skills, rows 1–4 with Status `sketch` |
| K2 | "`/architect` and `/improve` … Noctua never schedules them on its own initiative: it names them as options when their input exists." | `chain-map.md` § Stages, the note closing the table |
| K3 | "a roadmap presented as a feature list is the oldest lie on a project page" (lede) | **editorial** — our reason for the section, not a claim about the package |

### Footer

| # | string on the page | source |
|---|---|---|
| F1 | "A neurosymbolic analysis chain for Claude Code." | `noctua/SKILL.md` frontmatter `description` |
| F2 | "The owl is *Athene noctua*, the little owl." | **brand**, not a package claim — see *Brand* at the foot of this file |
| F3 | "A Knowledge Engineering project at the Università di Camerino, by Samuele "Delta" Stronati." | supplied by Delta (`SEED-BRIEF.md` § C3, footer) |
| F4 | "Download the package (v3, 897 KB)" → `noctua-v3_1.zip` | the file in this repo; 897 KB measured on disk |
| F5 | the two source links (`CHANGES-v3.md`, `chain-map.md`) | the files themselves |

## Docs pages — `docs/<skill>.html`, nine pages, all generated

`tools/build_docs.py` writes them from the package; nothing on them is authored by hand, which
is what makes them un-driftable. Their strings therefore trace by construction:

| # | element | source |
|---|---|---|
| D1 | "What it is" — the **full** `description`, verbatim, in `lang="en"` | `<skill>/SKILL.md` frontmatter `description`, unfolded to one line. Only the source's own backtick spans are rendered as `<code>`; no word is changed, added or reordered |
| D2 | "In the chain" — one block per chain-map row, with consumes · produces · orchestrator's check · human gate · unattended · re-run, plus the invocation | `noctua/references/chain-map.md` § Stages, that skill's row(s), via `content/chain.json`. `domain-forge` gets **two** blocks, `forge (prose)` and `refine` — which is the ten-rows-nine-skills fact, shown rather than asserted |
| D3 | "On the lanes" — the lane chips | `chain-map.md` § Lanes, via the `lanes` field of each stage in `content/chain.json` |
| D4 | "Trigger and flags" — invocation forms and `--flags` | extracted verbatim from that `SKILL.md`: every `` `/skill …` `` form the file writes out, and every `` `--flag` `` it names. The page says on its face that skill-level and script-level flags are not separated, because the files do not mark the difference in a way a generator can read |
| D5 | "Source" — the link | `noctua-package/<skill>/SKILL.md` |
| D6 | `document-project`: no `SKILL.md`, so no "Trigger and flags" section; its "What it is" is the chain-map row and its source link is the chain map | `chain-map.md` § Stages, row `document`; the package has no `document-project/` folder, and the page says that absence is what the external label rests on |

The landing's nine cards now link here (`docs/<skill>.html`) instead of at the package files.
The cards stay the condensations Delta approved at C3; the full description lives on these pages.

`content/page/stages-grid.html` is a generated alternative to those cards, built from the same
descriptions with the landing's own class names. It is **not** wired into `index.html` — swapping
it in would replace approved copy — and it exists so that swap is a one-line change if wanted.

## Italian — what stays English, and why

The Italian dictionary translates every string of the interface and the landing copy. Four
categories stay English on purpose, and the untranslated-text check knows about each one:

| what | how it is marked | why |
|---|---|---|
| the skill cards' paragraphs | `lang="en"` | they are the skills' own `description`, the source text the page quotes; translating them would put words in the package's mouth |
| each card's `consumes → produces` line | `lang="en"` | the chain map's own wording, same reason |
| the stage detail panel's values in the diagram | `lang="en"` on every `dd` and on the invocation | the chain map's own wording, same reason |
| skill names, slash commands, file names, library names | `translate="no"` or inside `<code>` | identifiers, not prose — `/dataset-shaper` is its name in both languages |

Technical vocabulary that an Italian reader of this material would not want translated is kept in
English inside otherwise Italian sentences: *codebase*, *dataset*, *skill*, *layer*, *ledger*,
*digest*, *headless*, *smoke test*, *soprainsieme* excepted. Where a real Italian word exists and
is used in the field, it is used: *corsia* (lane), *stadio* (stage), *sorgente* (source),
*motore* (engine), *invariante* (invariant), *verifica* (check).

## Brand exports and page metadata (C6)

The exports carry no new claims: they are the mark, or they repeat sentences already traced above.

| # | element | source |
|---|---|---|
| B1 | `favicon.svg`, `favicon.ico` (16/32/48), `apple-touch-icon.png`, `logo-mono.svg` | all derived from `brand/logo-mark.svg` by `tools/build_brand.py`; no new content |
| B2 | `og-image.png` — "The owl over the chain." | `noctua/SKILL.md`, the section heading, verbatim (same as row H7) |
| B3 | `og-image.png` — "Nine skills, one self-contained model, engines that verify what the language model proposes." | rows H4, H5 and H8 above, compressed to card length; no claim that is not already traced |
| B4 | `og-image.png` — 78 / 78 acceptance · 19 invariants · 0 network deps | rows H10, H11, H12 above |
| B5 | `og-image.png` — "a family of claude code skills" | row H1 above |
| B6 | `og:image:alt` on every page | describes the card above; it is a description of our own artwork, not a claim about the package |

`brand/BRAND.md` states the idea, the palette with every measured contrast ratio, the type, the
spacing and the do/don't. Its one factual claim about the framework — that *Athene noctua* has no
ear tufts — is ornithology, not package content, and is marked as the brand's own reasoning below.

**Resolved at C7.** The origin is `https://samuele95.github.io/noctua/`, recorded once in
`content/site.json`. From it, `tools/stamp_origin.py` writes the absolute `rel=canonical`,
`hreflang` alternates, `og:url`, `og:image` and `twitter:image` on all ten pages, and
`tools/build_sitemap.py` writes `sitemap.xml` and stamps the `Sitemap:` line into `robots.txt`.
Moving the site to another host is one edit to that file plus those two commands.
`tools/check_links.py` now verifies that every absolute URL on every page sits on that origin
and, where it names a file, that the file exists.

## Brand — not traced to the package, and said so

The mark, the wordmark, the palette and the copy's voice are original design work for this site.
Two things anchor them to the framework and are stated as readings, not as package claims: the
ontology language the engines run is called OWL (`domain-forge/SKILL.md` § The platform), and the
orchestrator is described as "the owl over the chain" (`noctua/SKILL.md` heading). The name
*Athene noctua* — the little owl — is the brand's reading of the skill's name; the package does
not mention the bird.
