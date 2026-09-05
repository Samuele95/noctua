# The HTML layer contract — for `/model-chat`

Per-skill restatement of the chain-wide contract in
`domain-forge/references/future-skills.md` (canonical). Read that for the rationale;
read this for what the `chat` layer must satisfy. The block format, the digest and
the strip logic are the layer platform's (`domain-forge/scripts/apply_layer.py` /
`strip_layer.py`); `scripts/apply_layer.py` and `scripts/strip_layer.py` import that
module and own only the transcript shaping, render code and styles — verified
reversible (`strip(apply(x)) == x`, byte-identical) and validator-clean
(invariants 13–16).

## The two hard guarantees

1. **Strict byte superset.** The output contains every byte of the input verbatim,
   in order, plus the `chat` block inserted just before `</body>`. Stripping the
   block recovers the input exactly. The input file is **never modified**.
2. **Self-contained.** No external HTTP refs (validator invariant 9). Render code,
   styles, and the transcript data are inlined; the file opens from `file://`.

## Block shape (emitted by apply_layer.py)

```html
<!-- @LAYER:start chat v1
     produced-by: /model-chat
     produced-at: <ISO-8601 UTC>
     input-digest: sha256:<hex of #domain-model textContent>
     reverts-by: open the file at input-digest (the predecessor)
 -->
<script id="layer-chat-data" type="application/json"> { …transcript… } </script>
<script id="layer-chat-render" type="text/javascript"> /* idempotent; reads ONLY #layer-chat-data */ </script>
<style id="layer-chat-style">/* .layer-chat-scoped CSS */</style>
<!-- @LAYER:end chat -->
```

## Transcript schema (`#layer-chat-data` body)

```json
{
  "version": 1,
  "produced_at": "ISO-8601 UTC",
  "input_digest": "sha256:<hex>",
  "turns": [
    {
      "q": "the natural-language question",
      "paradigm": "sparql | swrl | prolog | dmn | refused",
      "reasoned": true,                 // optional; for sparql/swrl
      "query": "the exact formal query that was run ('' for refused)",
      "result": { },                    // the raw structured result from run_query.py
      "answer": "the grounded NL answer (composed from result)",
      "grounded": true                  // false for refused turns
    }
  ]
}
```

## Render-script requirements (binding)

- **Idempotent.** Guards on `[data-layer="chat"]`; running twice does nothing extra.
- **Reads only its own data script.** Never mutates earlier layers' DOM or data.
- **Mounts into a new `section.layer-chat`** appended to `main` (or `body`).
- **Reproducible, not static.** Every engine-grounded turn carries a **re-run**
  button that re-executes its query against the LIVE engine
  (`window.__kg.runSparql` with the right `setReasoned`; `window.__plRun` for Prolog)
  and shows the fresh result — so a reader can confirm the baked answer. Refused
  turns carry no button.
- **CSS scoped** under `.layer-chat` so it can't bleed into the base page or other
  layers; it reads the base palette via `var(--…)` with literal fallbacks.

## Updating vs. creating

`apply_layer.py` strips any existing `chat` block before writing, so re-running it
with the full transcript both creates and updates. `--continue` in the skill means:
read the existing transcript, append the session's new turns, re-emit. The predecessor
is always recoverable with `strip_layer.py`.
