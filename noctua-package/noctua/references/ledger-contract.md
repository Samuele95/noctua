# The Noctua ledger — `.claude/noctua-ledger.md`

The ledger is the orchestrator's working memory across turns and sessions: **where each lane stands**, which artifact is current, what was verified, what is waiting for the user. It is deliberately separate from `.claude/domain-forge-memory.md`, which the forges own and which records *modeling decisions* (stances, retypings, partitions, shaping choices). Noctua reads that file but never writes to it; the stages do. The ledger records *chain state* and nothing a stage already records elsewhere.

Created from the template below on the first run (say so in the first status line). Rewritten — not appended forever — at the end of every stage: the **Lanes** table is the current truth, the **History** section is the append-only log.

```markdown
# Noctua ledger — <project name or root path>

## Sources
<!-- one line per source Noctua classified: kind | path | digest (sha256 of the file, or of the file list for a codebase) | first seen -->
dataset | data/orders.csv | sha256:… | 2026-09-03
codebase | src/ | sha256:… (tree) | 2026-09-03

## Lanes
<!-- one row per lane: the objective (the destination the user chose, with how it was set — user | --goal | assumed), the current artifact, the stages done in order, the next stage Noctua would propose, and the last verification -->
| lane | source | objective | current artifact | stages done | next | last check |
|---|---|---|---|---|---|---|
| dataset:orders | data/orders.csv | blueprint(pipeline) — user, 2026-09-03 | orders.domain.analysis.html | forge-data, lens | shape | validate 19/19 · smoke_analysis 12/12 · 2026-09-03T10:12Z |
| software:src | src/ | spec — user, 2026-09-03 | spec/spec-analysis.html | spec | forge-prose | self-contained · module map 7 · 2026-09-03T09:40Z |

## Open
<!-- forks or gates a stage left pending, one line each, with the stage and what it needs. Removed when resolved. -->
- shape: phase *values* — S6 impute delivered_days: group-median vs median; S8 transform unit_price: log vs none (waiting for user; answer returns via `--recipe`)

## Environment
<!-- prerequisites checked once, with the date; re-checked when a stage fails on one -->
python 3.12 · pandas 2.2 · scipy 1.14 · scikit-learn 1.5 · geopandas absent · chromium present · latex absent · checked 2026-09-03

## History
<!-- append-only: timestamp | lane | stage | outcome | artifact | note -->
2026-09-03T09:40Z | software:src | spec | OK | spec/spec-analysis.html | 7 modules, 1 flow, 2 open questions
2026-09-03T10:12Z | dataset:orders | lens | OK | orders.domain.analysis.html | 6 findings, 4 turns, 3 shaper candidates
```

## Rules

- **Only Noctua writes the ledger; only the stages write artifacts.** Noctua never edits an HTML, a dataset, a recipe or the forge memory. If a stage's product is wrong, the fix is to re-run the stage (a refine, a `--continue`, a new recipe), never a hand edit by the orchestrator.
- **A lane's `current artifact` is the last one that passed its check.** A stage whose product failed verification is recorded in History with `FAIL` and the artifact path, and the lane's current artifact stays the predecessor; `next` becomes the same stage with the failure as the brief.
- **Digests make re-runs cheap.** A source whose digest is unchanged and whose lane has a current artifact is not re-forged; Noctua proposes the next stage. A changed digest resets the lane to its first stage and says so (`WARN: data/orders.csv changed since orders.domain.html was forged`).
- **The objective is a decision, and decisions are asked once.** A lane's `objective` is the destination from `chain-map.md` § Destinations, with how it was set: `user` (chosen at step 4), `--goal` (stated), or `assumed` (unattended, and the summary says so). While it is recorded and the source digest is unchanged, Noctua does not re-ask it — the same rule that keeps a partition from being re-asked. It is cleared, and asked again, when the lane reaches it, when the source changes, or when the user moves it.
- **Open items are questions for the user, never answered by Noctua.** A `FORK:` a stage emitted is copied here verbatim with the stage name; when the user answers, Noctua re-invokes the stage with the answer in the form the stage accepts — a flag (`--partition late` for the forge), an edited recipe (`--recipe` for the shaper), or the first message of its loop (the lens, the chat) — it does not decide in the user's place.
- **Nothing that memory holds is duplicated.** A retyping, a partition, a shaping choice lives in `.claude/domain-forge-memory.md`; the ledger says only that the stage ran and what it produced.
- **The ledger is prose-free.** Tables and one-line entries; the reasoning behind a routing decision goes in the chat turn where Noctua proposed it, not here.
