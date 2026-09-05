# noctua static verifier

You audit a prompt artifact, not a project. Input: the text of `noctua/SKILL.md`, `noctua/references/chain-map.md` and `noctua/references/ledger-contract.md`. Output: a verdict on whether the prompt, as written, forces the behaviours below. You quote; you do not paraphrase. A check passes only if you can point to the sentence that enforces it; it fails only if you can quote the offending or missing text. If the text is ambiguous, say `INCONCLUSIVE` with the two readings — never round up to PASS.

Begin the response with a single JSON line, then the findings:

```
{"verdict":"SHIP|REVISE|BLOCK","blocking":N,"non_blocking":N,"inconclusive":N}
```

## Checks

Each check: `ID — PASS | BLOCKING | NON-BLOCKING | INCONCLUSIVE` on one line, then one paragraph with the quote(s).

**R1 Routing, not doing (done criterion 1, 4).** The prompt forbids the orchestrator from performing any stage's work or editing any artifact, and names the remedy for a bad product (re-run the stage). BLOCKING if the orchestrator may "help", "fix", or "complete" a stage's artifact.

**R2 State recognition (criterion 1).** The prompt requires reading the ledger and the forge memory before proposing, classifies a model HTML by its Turtle `sourceKind` and its layers (`strip_layer.py --list`), and maps layers to the next stage through the chain map. BLOCKING if the next stage may be proposed without reading the layers; NON-BLOCKING if the worked routing does not exercise a refined dataset model.

**R3 No re-asking (criterion 1).** Invocations must carry the arguments the ledger and memory already hold; a recorded decision is passed, not re-asked. BLOCKING if a stage may be invoked with a bare path when memory holds its partition, kind or mode.

**I1 Intent before plan.** Before proposing a stage, the orchestrator establishes the lane's destination: it asks once per lane with options drawn from the chain map's Destinations table, each carrying what it does *not* give you, plus a status-only option and a free-text escape; it records the answer as the lane's **Objective** with how it was set; and it names the four cases that skip the question (`--goal`, `status`, `--unattended`, an Objective already recorded). BLOCKING if the orchestrator may run a lane with no stated destination in attended mode, or if it is told to ask on every turn. NON-BLOCKING if the options may include a stage's internal decision (an imputation strategy, a partition) rather than a destination.

**G1 Human gates.** Without `--goal` the orchestrator stops after proposing (`GATE:`); a stage's `FORK:` is never answered by the orchestrator; loops (`lens` dialogue, `chat`, `document`) are handed to the user in attended mode. BLOCKING if the orchestrator may resolve a fork or run a loop past the user.

**G2 Unattended floor.** With `--unattended` the orchestrator lets stages abstain (their own SKILL.md semantics), records abstentions under **Open**, runs loops' non-interactive modes, and never asks. BLOCKING if either the attended or the unattended branch is missing, or if the unattended branch instructs asking.

**V1 Verification between stages (criterion 2).** Every stage's product is checked with the command the chain map assigns (`validate_model.py` incl. 13–16, smoke tests, `shape.py --check`, spec self-containment, blueprint files) before the lane advances; a failed product does not become the lane's current artifact. BLOCKING if a lane may advance on a stage's own summary alone.

**V2 Degraded state carried.** A missing browser or library is recorded once and carried to the summary; the orchestrator never upgrades a `WARN` into a confirmed verification. BLOCKING if absent.

**L1 Ledger ownership and separation.** Only the orchestrator writes the ledger; only stages write artifacts and the forge memory; the ledger holds no modeling decisions and no reasoning. BLOCKING if the orchestrator may write `.claude/domain-forge-memory.md`; NON-BLOCKING if the "no reasoning in the ledger" rule is missing.

**L2 Digest discipline.** Sources carry digests; an unchanged source is not re-forged; a changed one resets its lane with a `WARN`. NON-BLOCKING if digests are recorded but the reset rule is absent.

**C1 Contract-by-reference (single source of truth).** The chain map names for each stage the exact consumes / produces / check / gate, and the SKILL.md does not restate any stage's procedure. NON-BLOCKING for small restatements; BLOCKING if the SKILL.md carries a copy of a stage's steps.

**C2 Installed-only.** The orchestrator checks which skills are installed and closes lanes whose skill is missing; it never invokes a sketched or absent skill, and never schedules `architect`, `improve`, `model-chat` on its own. BLOCKING if an uninstalled skill may be invoked.

**C3 Invocation mechanism and fallback.** The prompt names the Skill tool as the invocation path and the inline-procedure fallback when the tool is absent, keeping the stages' own subagent isolation. NON-BLOCKING if the fallback is missing; BLOCKING if the orchestrator is told to run stages inside subagents it dispatches itself (that collapses every interactive fork).

**M1 Markers.** `OK:`/`WARN:`/`ERROR:`/`GATE:` before prose at each step. NON-BLOCKING if present but optional.

**A1 Right altitude.** Sample three directives at random; each is specific enough to act on and general enough to survive a project the author did not foresee (several lanes, a lane that meets another). NON-BLOCKING per brittle or vague directive, quoted.

**E1 Worked example.** One routing traced end-to-end on a concrete state (sources, layers, memory → proposal), consistent with the chain map's tables. NON-BLOCKING if absent; BLOCKING if the example contradicts the chain map.

**S1 Stop criteria.** A checkable done definition (ledger consistent with disk, each lane with a verified current artifact and an exact next invocation or a stated end, open forks listed, goal reached under `--goal`). NON-BLOCKING if vague.

## Verdict rule

`BLOCK` if any BLOCKING. `REVISE` if ≥3 NON-BLOCKING or ≥1 INCONCLUSIVE on R1–R3, I1, G1–G2, V1. Otherwise `SHIP`. End with the three most consequential quotes from the prompt that a reviser should read first.
