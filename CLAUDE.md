# CLAUDE.md — Noctua website & logo

Two halves. **Standing rules** do not change. **Project state** is rewritten at every checkpoint, before any question to Delta. Re-read this file at the start of every turn and after more than thirty tool calls since the last read.

## Standing rules

1. You are the design engineer for Noctua's public face; the full brief is `SEED-BRIEF.md`. Taste decisions are shown as rendered variants and picked by Delta; tactical decisions are yours and logged only when surprising.
2. Every factual sentence on the site traces to a file in `./noctua-package/`; the trace lives in `content/SOURCES.md`. Untraceable claims do not ship.
3. Static site, no framework, no bundler; `tools/build_docs.py` regenerates `docs/` from the package. All UI chrome and landing copy in `i18n/en.json` and `i18n/it.json`; skill descriptions on docs pages stay English inside `lang="en"` blocks.
4. A check is reported as passed only with its output quoted in the log below; a check not run is "not run".
5. Stop only at boundaries (Delta picks, approves, or supplies). If the turn's draft ending is a plan or a promise, do the work instead.
6. Speak Italian to Delta; English for code, file names, commits and the site's source copy. Final summaries lead with the outcome.
7. The logo is original SVG drawn in code — never derived from an existing owl logo, mascot or emoji.

## Project state

**Checkpoint:** C7 — **done. The site is live.** <https://samuele95.github.io/noctua/>
**Package:** `./noctua-package/` (v3, acceptance 78/78 per `CHANGES-v3.md`). Eight skill folders + `noctua/`; `document-project` and `effective-java` are external, described only by the chain map.
**On disk and deployed:** `index.html`, `docs/*.html` (9 generated), `sitemap.xml`, `robots.txt`, `.nojekyll`, `README.md`. `i18n/{en.json,it.json}` (112 keys each). `content/{outline.md,chain.json,site.json,SOURCES.md}`, `content/page/stages-grid.html`. `brand/` (mark, 5 exports, `BRAND.md`, the C1 directions). `assets/{css,js,fonts}`. `tools/` (5 generators, 4 checks). `screenshots/` is git-ignored — 39 MB of regenerable build output.
**Repo / hosting:** <https://github.com/Samuele95/noctua> · GitHub Pages from **branch `main`, folder `/`** · origin recorded once in `content/site.json`.

### Picks by Delta (with reason)
- Logo direction: **1, "the verifying pair", with direction 2's palette and type** (2026-09-04). Palette Fieldstone, type Space Grotesk + IBM Plex Sans — the only palette whose accents carry text in both themes.
- Hero direction: **B, "the owl over the chain"** (2026-09-04) — the mark as hero; the chain is section two.
- Landing (C3): **approved** (2026-09-04). Italian copy (C4): **approved** (2026-09-04). Docs pages (C5): **approved** (2026-09-05). Brand exports (C6): **approved** (2026-09-05).
- Repo URL supplied at C7 (2026-09-05): `https://github.com/Samuele95/noctua`.
- `tools/build_docs.py`, `content/page/stages-grid.html`, `dev/` (not written by me): **keep** (2026-09-04).

### Decisions (mine, worth knowing)
- **Pages deploys from branch `main`, folder `/` — not from a GitHub Actions workflow.** Every generated file is committed, so a workflow would only re-run scripts whose outputs are already in the tree: a moving part that can fail without adding a guarantee. Branch deploy publishes exactly what is in the repo, which is what the traceability argument needs — what you read is what is served. It also matches the brief's reason for choosing Pages: no toolchain to maintain.
- **The origin lives in one file**, `content/site.json`. `stamp_origin.py` writes it into canonical / hreflang / og:url / og:image / twitter:image on all ten pages; `build_sitemap.py` writes `sitemap.xml` and stamps `robots.txt`. Both are idempotent, so changing host is one edit plus two commands.
- `.nojekyll` is committed so Pages serves the tree verbatim instead of running Jekyll over it.
- `screenshots/` is git-ignored (39 MB, regenerable, unreferenced by the site).
- **`build_docs.py` was extended, not rewritten** (C5). Its frontmatter parser handles `>-`, `>`, `|` and plain scalars — better than the ad-hoc regex I had — and its stated rule ("no card text is authored here") is C5's requirement.
- The generated grid fragment carries the landing's class names but is **not wired in**: those cards are copy Delta approved at C3.
- Docs pages quote the **full** description verbatim and render only the source's own backtick spans as `<code>` — formatting the quotation without editing it.
- **Flags are not classified.** The pages list every `--flag` a `SKILL.md` names and say so, because the files do not mark skill-level from script-level mechanically.
- **`favicon.ico` is written by hand.** PIL's ICO writer resamples one base image, so it silently produced a single 16×16 frame; the hand-written container embeds three true rasterisations, verified by parsing the file back.
- `brand/logo-mark.svg` is **the one definition**; every icon and the OG card derive from it.
- **Fonts are self-hosted** (deviation below); the C6 font step was already done at C3.
- `tools/shoot.js` fails on console errors, page errors, horizontal overflow, any response ≥ 400, any external request, and an `<html lang>` that does not match the language asked for. It is origin-aware, so the same command checks localhost or the live site (`BASE=… node tools/shoot.js`).
- The primary button is terracotta with **ink** text (4.74:1), lightening to `#D2703A` on hover (5.53:1).

### Deviations (departures from the brief; conservative option taken, why)
- Self-hosted the fonts at C3 instead of C6, because the linked Google Fonts stylesheet made the C3 acceptance criterion (performance ≥ 90) non-deterministic (75 / 89 / 99 on three runs). Fewer runtime dependencies than the brief allows.
- `sitemap.xml` was not written at C6, though that checkpoint lists it: the protocol needs absolute URLs and the origin arrived at C7. The generator was built and tested against an example origin, and the example output reverted. **Resolved at C7** — the file is written and live.

### Open questions
- None blocking. Two offers are in the C7 punch list: a check-only CI workflow, and swapping the landing's hand-written cards for the generated fragment.

### Checks log (one line per run: date · checkpoint · check · result)
- 2026-09-04 · C0 · `json.load(content/chain.json)` · `10 stages, 6 lanes, 7 source kinds, 9 destinations`
- 2026-09-04 · C1 · `xmllint` + `svgo@3.3.5` on 6 direction SVGs · valid, 0 warnings
- 2026-09-04 · C1 · 16 px render of each mark, dark + light, opened and looked at · all three legible
- 2026-09-04 · C3 · contrast of every text token pair (10 pairs) · all ≥ 4.5:1 after the button fix
- 2026-09-04 · C4 · `check_i18n.py` · both dictionaries complete, no hardcoded visible string
- 2026-09-05 · C6 · `svgo@3.3.5` on all 4 brand SVGs · 0 warnings, 0 errors each
- 2026-09-05 · C6 · `favicon.ico` parsed back byte by byte · `type=1, 3 frames`, 16/32/48 each matching an embedded PNG of the same size
- 2026-09-05 · C6 · `brand/og-image.png` opened and looked at at full size · 1200×630, 119 KB
- 2026-09-05 · C7 · `python3 tools/stamp_origin.py` · `origin stamped: https://samuele95.github.io/noctua/ (index.html rewritten; docs pages regenerated)`
- 2026-09-05 · C7 · `python3 tools/build_sitemap.py https://samuele95.github.io/noctua/` · `sitemap.xml written — 10 pages, 3 alternates each; robots.txt Sitemap: line stamped`; `xmllint --noout sitemap.xml` clean, 10 `<url>` entries
- 2026-09-05 · C7 · `python3 tools/check_links.py` · `10 pages · 243 local references · 70 absolute URLs on https://samuele95.github.io/noctua/` · `OK — every link resolves`
- 2026-09-05 · C7 · `python3 tools/check_i18n.py` · `10 pages · 112 keys used · en 112 keys · it 112 keys` · `OK`
- 2026-09-05 · C7 · `npx htmlhint@1 index.html "docs/*.html"` · `Scanned 10 files, no errors found (16 ms)`
- 2026-09-05 · C7 · `gh api -X POST repos/Samuele95/noctua/pages` then poll · `status: built`, `html_url: https://samuele95.github.io/noctua/`
- 2026-09-05 · C7 · 14 live URLs curled (pages, sitemap, robots, every icon, a font, the zip, a package `SKILL.md`) · **all 200**
- 2026-09-05 · C7 · **`npx lighthouse@12` on the LIVE URL**, ×2 per page · landing **99–100 · 100 · 100 · 100**; `docs/data-lens.html` **100 · 100 · 100 · 100**. SEO reached 100: the `hreflang` audit passes now that the alternates are absolute.
- 2026-09-05 · C7 · `BASE=https://samuele95.github.io/noctua node tools/shoot.js` · 48 PNGs against the live site · `OK — no console errors, no page errors, no horizontal overflow, no external requests`, no response ≥ 400
- 2026-09-05 · C7 · diagram driven on the live site in both languages · 10 stages, click pins 1, detail shows the clicked stage, hovering `dataset` dims the 2 off-lane stages
- 2026-09-05 · C7 · live screenshots opened and looked at (IT 1440 light, EN 360 dark, docs 768) · no overflow, no clipped text, mark and type correct in both themes

### Lessons (one per line, with why it mattered; update, don't duplicate)
- `NOCTUA-PROMETHEUS-REPORT.md` § 7 point 2 is **stale**; `CHANGES-v3.md` is the later word and wins.
- The package has no `document-project/` folder: that absence *is* the evidence for the "external" label.
- A pale filled face with dark round eye-holes reads as a **skull**, not an owl. Shape problem, not colour.
- Dashed strokes read as a sun or a gear at logo scale; a polygon reads as the discrete twin of a circle.
- Round line caps on a thick arc over a ring produce accidental **ear tufts**. *Athene noctua* has none.
- A `<dl>` on a CSS grid splits labels from values across columns. Wrap each pair in a `div`.
- A flex container reused across breakpoints carries its `justify-content` into the new axis.
- A sticky header eats anchor targets; `scroll-margin-top` on `section[id]` is the fix.
- Measure, do not squint — a `getBoundingClientRect` beats staring at a screenshot.
- **Run a flaky metric three times before believing it.** 75/89/99 revealed a render-blocking third-party stylesheet a single "89" would have hidden.
- A relative `rel="canonical"` fails Lighthouse SEO outright, and so does a relative `hreflang`. Both need the real origin; keeping them out until C7 cost 9 SEO points for four checkpoints and cost nothing at the end.
- Paper-on-terracotta measures 3.76:1. Accent buttons are where a warm palette quietly fails WCAG.
- **Every scripted `.replace()` needs an assertion.** Three edits to `chain.js` silently no-oped.
- Regex-scanning JS for `"..."` literals desynchronises on the first unbalanced quote.
- **Read inherited code before replacing it.** `build_docs.py`'s frontmatter parser was better than mine.
- Quoting a markdown source verbatim into HTML shows its backticks. Rendering the source's own inline markup is formatting, not editing — but it must be a stated rule.
- **Verify a binary you generated by parsing it back.** The build log was quoting my intent, not the file.
- A 404 on an icon is invisible in both the page and the screenshot. Fail the run on any response ≥ 400.
- **Put the deployed origin in one file.** Five things need it — canonical, hreflang, og:url, og:image, sitemap — and scattering it would make a host change a hunt instead of an edit.
