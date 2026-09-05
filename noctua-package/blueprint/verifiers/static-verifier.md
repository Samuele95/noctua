# /blueprint — static-mode verifier

A Shape 6 (LLM-as-judge) prompt that re-reads the `/blueprint` skill artifact and audits its coherence, consistency, and absence of structural defects. Run before relying on `/blueprint` in production work, and after any edit to the skill.

`/blueprint` is a single-artifact skill (the orchestrator is also the worker — unlike `/architect`, there is no separate auditor agent). So this verifier audits one file, plus its claimed compatibility with `/architect`'s downstream artifacts.

## How to run

Paste the prompt below into a Claude Code conversation (or any sufficiently capable LLM with file access). Provide the artifacts as inputs:

- `./SKILL.md` (the skill)
- `agents/architect-auditor.md` (downstream schema source — for the compatibility check only)

The verifier returns a checklist with PASS / FAIL / PARTIAL per check and a final verdict.

## Prompt

```
You are auditing a Claude Code skill called /blueprint. It is a greenfield
first-architecture proposal skill: it ingests a /spec-analysis HTML or a
/domain-forge model and proposes a FIRST architecture (no code exists yet),
emitting blueprint.md + findings.json + a self-contained blueprint.html. It is
a human-in-the-loop, multi-turn skill that gates structural decisions one per
turn. It is the sibling of /architect, which audits EXISTING code; /blueprint's
blueprint.md is the design baseline a later /architect run diffs built code
against.

Two invariants define this skill's value and are the focus of this audit:
  (A) TRACE INTEGRITY — because there is no code to verify against, every design
      claim must either cite the spec/model section it derives from, or be
      stamped [DESIGNER'S CHOICE — pressure]. A claim that is neither is a
      hallucination.
  (B) ANCHOR INTEGRITY — every finding's Bloch/SOLID/GoF/FP/DDD/HEX anchor must
      be load-bearing: its justification clause must name what that specific
      principle predicts, such that a different anchor would change the
      reasoning. A bare or retrofitted anchor is decoration and is a defect.

Read the skill file in full before evaluating any check. Do not rely on summaries.

Artifacts:
  - Skill:              ./SKILL.md
  - Downstream schema:  agents/architect-auditor.md  (compatibility check only)

Run each check below. Report PASS / FAIL / PARTIAL with one sentence of
justification per check, quoting the relevant line(s). At the end, give a
verdict: SHIP / REVISE / BLOCK.

CHECKS:

1. Trace-invariant presence and reinforcement. The rule that every design claim
   cites the spec/model OR is stamped [DESIGNER'S CHOICE — pressure] must appear
   (a) as a stated discipline near the top, (b) in the procedure (the per-axis
   and per-bet tagging in Steps 2, 2.5, 4), AND (c) in the failure-modes section.
   Verify all three occurrences. This is the skill's cardinal invariant; absence
   from any of the three is a structural defect.

2. Designer's-choice ledger. §7 of blueprint.md must collect every
   [DESIGNER'S CHOICE] in one place with its justifying pressure, and the final
   summary must count them and report trace integrity (PASS or list unstamped).
   Verify both the §7 spec and the summary's trace-integrity line exist.

3. Anchor-load-bearing rule (invariant B). The skill must require, in Step 5,
   that each finding carries an `anchor_justification` clause per anchor naming
   what the principle predicts, with the explicit test "if the proposal reads
   identically with the anchor deleted, the anchor is decoration — fix or drop."
   This must ALSO appear as a DO-NOT. Verify both occurrences. FAIL if the skill
   only requires an anchor to EXIST without requiring it to be justified.

3b. Scoped EJ corpus + single source of truth. The skill must (a) point the EJ
   anchor set at the auditor's grounded 43-item "Bloch corpus" table as the
   SINGLE source of truth, (b) NOT duplicate the 43 rows into the skill file
   (a second copy is a drift defect), (c) forbid anchoring to an EJ item outside
   that set (in both the Anchor-corpus section AND the load-bearing rule / a
   DO-NOT), and (d) name the source PDF path. Verify all four. FAIL if the skill
   inlines its own EJ table or permits out-of-set EJ anchors.

4. Anchor integrity in the summary. The final summary must include an
   "Anchor integrity" check line (every finding anchor carries a load-bearing
   justification: PASS or list bare anchors). Verify it is present and distinct
   from the trace-integrity line.

5. Architectural-style multi-axis model. Step 2.5 must model style as a POINT
   across independent axes (distribution / internal-dependency / interaction /
   data), NOT as a single label off a flat menu. Verify (a) the four axes are
   named with their selecting forces, (b) the skill says to pick a coherent
   COMBINATION, (c) a coherence check flags incoherent combinations (the
   distributed-monolith example), and (d) the axis list is described as
   vocabulary, not a rigid checklist (a spec may add or drop axes). FAIL if
   style is presented as choosing one named style from a menu.

6. Style is Bet 0, gated first. The skill must make the architectural style
   "Structural bet 0," resolved BEFORE decomposition/paradigm/boundary bets,
   with the stated reason that §3/§4/§6 derive from it. Verify Step 3 lists it
   as bet 0 AND Step 4 gates it first, per-axis.

7. One-bet-per-turn gating. The skill must gate one structural decision per
   turn and explicitly forbid batching the big bets (with the rationale that a
   wrong unreviewed early call wastes the run). Verify the rule in Step 4 AND
   the DO-NOT. Verify the --report-only escape (auto-resolve, surface for
   post-hoc review) is explicit.

8. Schema compatibility with /architect. The skill claims findings.json is
   "diff-compatible" with architect-auditor's output. Read the auditor's JSON
   field rules. Verify the shared fields (id, axis, depth, anchors,
   anchor_justification, title, abstraction_cost, risk, effort, and a
   blueprint-anchor/trace equivalent) align. Verify the ONE intentional
   divergence — blueprint's `depth` omits `surface` because that needs code —
   is stated in the skill, not a silent drift. List any field the skill
   references that the auditor schema lacks, or vice versa, that is NOT
   documented as intentional.

9. Input classification. Step 1 must handle three input cases — prose spec,
   domain model, both — and state how each is grounded (prose = more inference
   risk; model = lift entities, don't re-derive; both = model for entities,
   prose for behavior). Verify all three, AND that "no recognized artifact →
   ask, don't fabricate" is present (in Step 1 AND as a DO-NOT).

10. Don't-re-derive-the-model rule. When the input is a domain-forge model, the
    skill must lift its entities/relationships rather than re-modeling from
    scratch. Verify this appears in Step 2 AND as a DO-NOT.

11. Blueprint section structure. blueprint.md must define §0 (style) through §8
    (risks/open questions), with §0/§1/§2 restated verbatim in chat after
    writing. Verify the section list is complete and the verbatim-restatement
    rule is present. Verify §0 is the style (the downstream /architect diff
    baseline for topology) and §2 carries per-item trace tags.

12. Performance honesty. With no code, §6 perf posture must be intent +
    cost-flagging derived from the §0 distribution axis, NOT measurement. Verify
    Step 5's §6 spec AND a DO-NOT ("don't claim performance numbers") both state
    this.

13. Orchestrator leanness. The skill must dispatch a sub-agent for heavy
    spec/model reads rather than loading the corpus into its own context (Step 2 /
    2.5 AND a DO-NOT), mirroring /architect. Verify both.

14. Flag handling. --blueprint-only, --findings-only, --report-only, --axis,
    --concern must each be handled consistently across Trigger, the relevant
    procedure steps, and Stop criteria. Verify --report-only's gate-skipping is
    consistent everywhere it is mentioned, and that --blueprint-only /
    --findings-only correctly skip the other artifact.

15. Stop criteria. The skill must end with explicit stop criteria covering the
    default flow (all bets resolved + artifacts written + §0/§1/§2 restated +
    summary with both integrity checks) and the three reduced modes. Verify
    completeness and consistency with the procedure.

16. Example validity. Any JSON-shaped or template-shaped example (the
    findings.json field list, the bet-0 gate template, the summary block) must
    be internally consistent — fields named in one place match the other. Flag
    any field named in the summary's integrity checks that the findings schema
    doesn't carry, or vice versa.

17. Information preservation. The load-bearing rules (trace invariant,
    anchor-load-bearing, style-by-force-not-fashion, one-bet-per-turn,
    don't-invent-a-spec) must each appear at least twice in different forms
    (procedural + DO-NOT). Verify these designed-in repetitions exist; a rule
    stated only once is at risk of being dropped under sampling.

VERDICT RULES:

- Any FAIL on checks 1, 3, 5, 6, 8 → BLOCK (these are the structural invariants
  the whole skill rests on: trace integrity, anchor integrity, the multi-axis
  style model, style-as-bet-0, and downstream compatibility).
- Any FAIL on checks 2, 4, 7, 9, 10, 11, 14, 15 → REVISE (coherence issues).
- Checks 12, 13, 16, 17 are quality checks; PARTIAL is acceptable, FAIL
  warrants REVISE.
- Only PASS / PARTIAL on the above → SHIP, with PARTIALs noted as known
  limitations.

Report format:

  ## Static-mode verifier report (/blueprint)

  | # | Check | Verdict | Note (quote the line) |
  |---|-------|---------|------------------------|
  | 1 | Trace-invariant presence | PASS / FAIL / PARTIAL | one sentence |
  ...

  ## Verdict: SHIP / REVISE / BLOCK

  ## Required revisions (if any)
  - <specific change needed>
```

## Notes for the user

- Run this verifier any time you edit `SKILL.md`. Checks 1–4 police the two invariants that give the skill its value (trace + anchor integrity); a regression there is silent and dangerous.
- Check 8 is the coupling to `/architect`. If you change `findings.json`'s shape in either skill, re-run both verifiers — the downstream diff depends on schema alignment.
- A SHIP verdict with PARTIALs is normal. BLOCK and REVISE both require action.
- The intentional `depth` divergence (no `surface` value) is expected — check 8 verifies it's documented, not that it's absent.

## Dynamic-mode verifier (sketch)

A dynamic-mode verifier would observe a real `/blueprint` run end-to-end against an actual spec and check: did the run gate bet 0 (style) FIRST and per-axis? Did every §2 entity and every style axis in the written blueprint.md carry a trace tag or a DESIGNER'S-CHOICE stamp? Did every finding's anchor_justification actually name a principle that drove the design (re-read each and try to delete the anchor — does the reasoning survive)? Did §0/§1/§2 get restated verbatim in chat? Did the coherence check fire on any incoherent style combination? Is the emitted findings.json actually loadable and schema-aligned with a real architect-runs findings.json? This is left as a follow-up; the static verifier catches the structural defects that would make a dynamic run uninterpretable.
