# Optional capabilities — off the main spine

These two capabilities belong to `/domain-forge` but are **not** part of a normal forge/refine pass (Steps 1–8 in `SKILL.md`). The orchestrator reads this file only when a user asks for a bundle / submission / `.dmn` / `.pl` file / a milestone, or asks about the reasoner.

## Submission bundle (on request)

When the user is targeting a KE-course milestone or any deliverable that
expects machine-readable artifacts on disk, produce them with:

```
python <skill-dir>/scripts/bundle.py <output.html> --out <bundle-dir> [--zip <bundle.zip>]
```

The bundle contains `model.ttl`, `model.dmn`, `model.pl`, the composed
`model.html` itself, and a `MANIFEST.md`. The DMN-XML and Prolog projectors
are Python ports of the runtime projectors in `assets/template.html`, so the
on-disk artifacts are byte-identical to "Download" from the browser. No PDF
is produced — `bundle.py` is deterministic, the report.pdf is not its job.

**The written `report.pdf` is owned by the `/document-project` skill.** A
submission report must be narrative — motivated prose, generated TikZ /
PlantUML figures, chapter structure — not a print of the HTML page. Mixing
that responsibility into `bundle.py` would reinvent a skill that already
exists. After running the bundle, point the user at `/document-project`
inside the bundle directory; `MANIFEST.md` carries the brief that skill
should be given. Domain-forge owns the model; document-project owns the
documentation.

Do NOT run this preemptively. Offer it only when the user asks for a
bundle, a submission, a `.dmn` / `.pl` file, or names a milestone.

## Engine capability viewers (decomposed reasoner)

The reasoner inside every composed `model.html` is itself decomposed
explode/compose-style into per-capability source under
`assets/engine-source/` (subclass closure, class-membership inheritance,
subproperty closure, property characteristics, SWRL forward chaining,
consistency). The full build/viewer contract — the three engine scripts
(`explode_engine.py`, `compose_engine.py`, `build_viewers.py`), the
`@ENGINE_BLOCK` markers, and the **snapshot principle** (shipped HTML is the
source of truth; every operation creates a new HTML or a revertable working
copy; the original is never silently mutated) — lives in
`assets/engine-source/README.md`. Read it once if a user touches the engine;
don't carry it in your context otherwise.

When to surface the viewers to a user:

- They ask "what does the reasoner actually do?" — point them at
  `assets/engine-source/README.md` and the per-capability `viewer.html` files.
- They suspect an inference is wrong — open the matching capability's viewer,
  paste a minimal KB, see what fires.
- They want to extend the engine — edit that capability's `logic.js`, then
  run `compose_engine.py` and `build_viewers.py`.

Round-trip is verified by the engine round-trip invariant (validator
invariant 12): a broken engine block fails the validator.

