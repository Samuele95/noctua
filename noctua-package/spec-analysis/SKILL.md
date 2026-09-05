---
name: spec-analysis
description: >-
  Analyze an EXISTING software project — or a DATA PROJECT (notebooks, ETL, DAGs) or a DATABASE
  (DDL, migrations, ORM; a live DB only via a user-supplied read-only connection) — and explain
  it back as a read-only HTML report: what it does, its components and responsibilities, its
  behaviors and business rules, its decision logic, its data model, its control and data flows,
  as connected prose, reading the code but never modifying it. Reach for it when someone hands
  you a codebase or schema to understand or explain rather than change: onboarding a legacy
  system, capturing how a service works before a rewrite. The
  artifact is deliberately the INPUT to /domain-forge: describe the domain in prose, leave the
  ontology to that step. Trigger on requests to analyze, describe, spec out, document, or make
  sense of a project's architecture and logic, or /spec-analysis. Not for: document-to-HTML
  (/htmlify), a domain model (/domain-forge), a dataset's contents (/dataset-forge,
  /data-lens), or refactoring code (/architect).
---

# Spec Analysis

This skill is a thin dispatcher. The actual work is done by the **`spec-analysis` subagent**,
which crawls the codebase in an isolated context — keeping the large, token-heavy exploration
out of this conversation — and returns a compact summary plus the path to the artifact it wrote.

## What to do

1. **Establish the target and its kind.** Default to the current working directory. If the user
   named a specific project path, subdirectory, or subsystem to scope the analysis to, pass that
   along. If the scope is genuinely ambiguous (e.g., a monorepo with several independent projects
   and no indication which one), ask one clarifying question before dispatching — otherwise just go; under `--unattended` (an orchestrator passes it) do not ask: analyse the largest coherent root and state the choice in the summary.

   The **kind** is `codebase` (default), `data-project` (notebooks, ETL / pipeline code, DAG
   definitions, SQL alongside data files — the *code around the data*, not the data itself) or
   `database` (DDL / schema files, migrations, ORM models; or a live database, only when the user
   supplies a **read-only** connection string). Infer it from the tree; `--kind <kind>` overrides.
   Pass it in the brief, with `--out <path>` when given (default: `spec-analysis.html` at the analysed root). Dataset *contents* are never this skill's subject — a `.csv` next to the
   code is mentioned as an input of the flows and left to `/dataset-forge`; the same holds for a
   database's rows beyond the small catalog samples the agent reads to describe a column.

2. **Run the analysis.** The full method — investigation approach, the pre-render checkpoint,
   narrative discipline, the HTML spec, and the "describe-the-domain-in-prose-but-don't-formalize-it"
   rule that keeps it from stepping on `/domain-forge` — lives in `agents/spec-analysis.md`,
   bundled in this skill. Two ways to run it, in order of preference for the environment:
   - **If a sub-agent mechanism is available** (Claude Code): dispatch it with
     `subagent_type: "spec-analysis"` (or, if that type is unregistered, `general-purpose` with
     the contents of `agents/spec-analysis.md` as the prompt prefix). This keeps the token-heavy
     crawl out of this conversation. Prompt: *"Produce a spec-analysis.html for the project at
     <path>. Kind: <codebase | data-project | database>. <Connection string, read-only, if the
     user gave one.> <Any scoping notes from the user.>"*
   - **If no sub-agent mechanism exists** (e.g. on claude.ai / the API where only this
     conversation runs): read `agents/spec-analysis.md` and carry out its full contract yourself,
     inline — crawl the codebase and write `spec-analysis.html` directly.
   Either way the work is read-only: it never modifies the project; its only write is the output HTML.

3. **Relay the result.** The subagent returns the artifact path plus a structured summary — the
   module map, one traced flow, and any open questions it flagged. Surface that summary to the
   user and point them at `spec-analysis.html`. The summary is the cheap inspection point: if the
   module map or flow looks thin, the document is thin, and a re-run with a tighter scope or more
   depth is warranted.

4. **Offer the handoff.** The artifact is built to be the input to `/domain-forge`, which
   extracts the formal domain model (entities, relationships, rules) from its prose. Offer that
   as the natural next step in the pipeline: `/spec-analysis` → `/domain-forge` → `/blueprint`,
   `/architect` or `/document-project`. For a `data-project`, also name the datasets the flows
   consume and point them at `/dataset-forge` — the two lanes meet at `/blueprint --mode pipeline`,
   which reads this spec for the flows and the dataset model for the data. When `/noctua` invoked
   this skill, it records the hand-off itself; just return the summary.

## Notes

- **Prefer the subagent when one exists.** The whole point of the subagent is context
  isolation — running the crawl inline is the *fallback* for environments without sub-agents
  (see Step 2), not the default when dispatch is available.
- **Multiple targets** (e.g., several repos or subprojects) can be dispatched as parallel
  subagents in a single turn, each producing its own `spec-analysis.html`.
- The agent's full contract — investigation method, the pre-render checkpoint, narrative
  discipline, the HTML spec, and the "describe-the-domain-in-prose-but-don't-formalize-it" rule
  that keeps it from stepping on `/domain-forge` — lives in the agent definition at
  `agents/spec-analysis.md`. Consult it only if you need to adjust the agent's behavior.
