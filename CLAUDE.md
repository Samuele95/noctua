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

**Checkpoint:** C6 — done, waiting on Delta's review of the exports. Next: C7 (deploy and final verification).
**Package:** `./noctua-package/` (v3, acceptance 78/78 per `CHANGES-v3.md`). Eight skill folders + `noctua/`; `document-project` and `effective-java` are external, described only by the chain map.
**On disk:** `index.html`, `docs/*.html` (9 generated), `robots.txt`. `i18n/{en.json,it.json}` (112 keys each). `content/{outline.md,chain.json,SOURCES.md}`, `content/page/stages-grid.html`. `brand/{logo.svg,logo-mark.svg,logo-mono.svg,favicon.svg,favicon.ico,apple-touch-icon.png,og-image.png,BRAND.md}` + `brand/directions/`. `assets/css/{fonts,tokens,base,chain,hero,landing,docs}.css`, `assets/js/{i18n-data,i18n,theme,chain-data,chain}.js`, `assets/fonts/*.woff2`. `screenshots/` (48 PNGs). `tools/{render_svg,contact_sheet,build_chain_data,build_i18n,build_docs,build_brand,build_sitemap,check_links,check_i18n}.py` + `tools/{shoot,check_chain}.js`.
**Missing on purpose, blocked on the Pages origin:** `sitemap.xml` (the generator refuses to guess), the `Sitemap:` line in `robots.txt`, `<link rel="canonical">`, absolute `hreflang`, absolute `og:image` / `twitter:image`. All five are one command at C7: `python3 tools/build_sitemap.py <origin>` plus a stamp pass over the ten pages.
**Repo / hosting:** GitHub Pages — repo URL: _to be supplied by Delta at C7_.

### Picks by Delta (with reason)
- Logo direction: **1, "the verifying pair", with direction 2's palette and type** (2026-09-04). Palette Fieldstone, type Space Grotesk + IBM Plex Sans — the only palette whose accents carry text in both themes.
- Hero direction: **B, "the owl over the chain"** (2026-09-04) — the mark as hero; the chain is section two.
- Landing (C3): **approved** (2026-09-04), no changes requested.
- Italian copy (C4): **approved** (2026-09-04), no corrections requested.
- Docs pages (C5): **approved** (2026-09-05), no changes requested — "Trigger and flags" stays as it is, flags unclassified and said so.
- `tools/build_docs.py`, `content/page/stages-grid.html`, `dev/` (not written by me): **keep** (2026-09-04).

### Decisions (mine, worth knowing)
- **`build_docs.py` was extended, not rewritten** (C5). Its frontmatter parser handles `>-`, `>`, `|` and plain scalars — better than the ad-hoc regex I had used — and its stated rule ("no card text is authored here") is C5's requirement. Only its class names were wrong.
- The generated grid fragment carries the landing's class names but is **not wired in**: those cards are copy Delta approved at C3.
- Docs pages quote the **full** description verbatim and render only the source's own backtick spans as `<code>` — formatting the quotation without editing it.
- **Flags are not classified.** The pages list every `--flag` a `SKILL.md` names and say so, because the files do not mark skill-level from script-level mechanically.
- **`favicon.ico` is written by hand**, not by PIL. PIL's ICO writer *resamples one base image* to the sizes given, so it silently produced a single 16×16 frame. The hand-written container embeds three true rasterisations (16/32/48), verified by parsing the file back.
- `brand/logo-mark.svg` is **the one definition**; the favicon, the ICO, the touch icon and the OG card are all derived by `tools/build_brand.py`. Nothing is drawn twice.
- The OG card is an HTML page screenshotted at 1200×630 (rendered 2× and resampled), so its type is the site's real self-hosted type rather than a second approximation of it.
- `logo-mono.svg` drops the iris to negative space. Below ~24 px the eyes lose their holes; BRAND.md says to use it large, and the 16/512 renders were opened and looked at.
- The chain map has **ten stage rows but nine skills**; the diagram footnote, the stages lede and `docs/domain-forge.html`'s two blocks all say so.
- **What stays English on a translated page**: skill descriptions and chain-map values (`lang="en"`), identifiers (`translate="no"` or `<code>`).
- `content/chain.json` → `chain-data.js` and `i18n/*.json` → `i18n-data.js`, compiled and loaded as scripts, not fetched: `fetch()` of a sibling JSON is blocked under `file://`.
- **Fonts are self-hosted** (see the deviation below) — the C6 font step was already done at C3.
- `tools/shoot.js` now also fails on **any response ≥ 400**, because a 404 on a favicon is invisible both in the page and in a screenshot.
- The primary button is terracotta with **ink** text (4.74:1), lightening to `#D2703A` on hover (5.53:1).

### Deviations (departures from the brief; conservative option taken, why)
- Self-hosted the fonts at C3 instead of C6, because the linked Google Fonts stylesheet made the C3 acceptance criterion (performance ≥ 90) non-deterministic (75 / 89 / 99 on three runs). Fewer runtime dependencies than the brief allows.
- **`sitemap.xml` was not written at C6**, though the checkpoint lists it. The protocol requires absolute `<loc>` URLs and the origin arrives at C7; a guessed one would advertise pages that do not exist. The generator is built, tested against an example origin, and the example output reverted. Conservative: no file rather than a wrong file.

### Open questions (only what Delta must answer; asked at the next boundary)
- **C6 boundary: do the exports hold up** — the OG card in particular, since it is the only artwork that is not the mark.
- **Repo URL for GitHub Pages** — now blocking five things at once: the sitemap, the `robots.txt` Sitemap line, the canonical link, the absolute hreflang alternates, and the absolute `og:image`.

### Checks log (one line per run: date · checkpoint · check · result)
- 2026-09-04 · C0 · `json.load(content/chain.json)` · `10 stages, 6 lanes, 7 source kinds, 9 destinations`
- 2026-09-04 · C1 · `xmllint` + `svgo@3.3.5 --multipass` on 6 direction SVGs · valid, 0 warnings
- 2026-09-04 · C1 · 16 px render of each mark, dark + light, opened and looked at · all three legible
- 2026-09-04 · C3 · contrast of every text token pair (10 pairs) · all ≥ 4.5:1 after the button fix
- 2026-09-04 · C4 · `check_i18n.py` · both dictionaries complete, no hardcoded visible string
- 2026-09-05 · C6 · `xmllint --noout` on all 4 brand SVGs + the 6 direction SVGs · all valid, 0 errors
- 2026-09-05 · C6 · `npx svgo@3.3.5 --multipass` on `logo.svg`, `logo-mark.svg`, `logo-mono.svg`, `favicon.svg` · **0 warnings, 0 errors** each
- 2026-09-05 · C6 · `favicon.svg` and `logo-mono.svg` rendered at 16 and 512 px, dark + light, opened and looked at · favicon unmistakable at both; mono legible at 512, eyes fill in below ~24 px (documented in BRAND.md)
- 2026-09-05 · C6 · `favicon.ico` parsed back byte by byte · `type=1, 3 frames` — dir 16/32/48 each matching an embedded PNG of the same size, `OK` on all three; the three frames opened and looked at
- 2026-09-05 · C6 · `brand/og-image.png` opened and looked at at full size · 1200×630, 119 KB; first composition left the right half empty and was recomposed as the hero (mark right, claim and numbers left)
- 2026-09-05 · C6 · `python3 tools/build_sitemap.py` with no origin · `no origin given — nothing written`, exit 2, listing the 10 URLs it would emit. Run against an example origin it produced a valid 10-URL sitemap with 3 alternates each and stamped `robots.txt`; both reverted.
- 2026-09-05 · C6 · `python3 tools/check_i18n.py` · `10 pages · 112 keys used · en 112 keys · it 112 keys` · `OK — every key exists in both dictionaries and no visible string is hardcoded`
- 2026-09-05 · C6 · `python3 tools/check_links.py` · `10 pages · 273 local references checked` · `OK — every link resolves`
- 2026-09-05 · C6 · `node tools/shoot.js` (landing + 2 docs × en/it × 1440/768/360 × dark/light) · `OK — no console errors, no page errors, no horizontal overflow, no external requests`; and with the new rule, **no response ≥ 400** — every favicon, icon and font resolves
- 2026-09-05 · C6 · `node tools/check_chain.js` · **14/14 ok**, 7 per language
- 2026-09-05 · C6 · `npx htmlhint@1 index.html "docs/*.html"` · `Scanned 10 files, no errors found (17 ms)`
- 2026-09-05 · C6 · `npx lighthouse@12` ×2 per page · `index.html` **97 · 100 · 100 · 91**; `docs/blueprint.html` **99 · 100 · 100 · 91**. Identical on repeat runs; the only failing audit on either page is `hreflang` (absolute URLs, C7).

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
- A relative `rel="canonical"` fails Lighthouse SEO outright, and so does a relative `hreflang`.
- Paper-on-terracotta measures 3.76:1. Accent buttons are where a warm palette quietly fails WCAG.
- **Every scripted `.replace()` needs an assertion.** Three edits to `chain.js` silently no-oped.
- Regex-scanning JS for `"..."` literals desynchronises on the first unbalanced quote.
- **Read inherited code before replacing it.** `build_docs.py`'s frontmatter parser was better than mine; rewriting would have cost a regression to fix a class-name mismatch.
- Quoting a markdown source verbatim into HTML shows its backticks. Rendering the source's own inline markup is formatting, not editing — but it must be a stated rule.
- **Verify a binary you generated by parsing it back.** PIL's ICO writer resamples one base image instead of embedding the frames you pass, so `favicon.ico` silently held a single 16×16 frame while the build log claimed three. The log was quoting my intent, not the file.
- A 404 on an icon is invisible in both the page and the screenshot. Fail the screenshot run on any response ≥ 400, or ship broken favicons and never know.
