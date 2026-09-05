# Noctua — the site

The public face of **Noctua**, a family of Claude Code skills that form a neurosymbolic
analysis chain. Live at **<https://samuele95.github.io/noctua/>**.

A Knowledge Engineering project at the Università di Camerino, by Samuele "Delta" Stronati.

## What is in here

| path | what |
|---|---|
| `index.html` | the landing page — hero, the chain, the nine stages, how it verifies, get started, sketches |
| `docs/*.html` | one page per stage, nine of them, **generated** from the package |
| `assets/` | CSS, JS, and the five self-hosted `woff2` subsets |
| `brand/` | the mark and every export, plus `BRAND.md` and the three C1 candidates |
| `i18n/` | `en.json` and `it.json` — every visible string, one key set |
| `content/` | `chain.json` (the chain map, transcribed), `SOURCES.md` (the trace table), `outline.md`, `site.json` |
| `tools/` | the generators and the checks |
| `noctua-package/` | the v3 package the site describes; `noctua-v3_1.zip` is the same, packed |

The site is static: no framework, no bundler, no build step at deploy time. Every generated
file is committed, so what you read in the repo is what is served.

## The rule this site is built on

Every factual sentence traces to a file in `noctua-package/`, and the trace lives in
[`content/SOURCES.md`](content/SOURCES.md) — section by section, string by string, including
the rows marked *editorial* (a headline framing a traced fact) and *brand* (our reading, not
the package's word). A claim that cannot be traced does not ship.

The skills' own words stay in English inside `lang="en"`, in both language versions, because
they are the package's text and not ours to translate.

## Regenerating

Nothing under `docs/`, `assets/js/chain-data.js`, `assets/js/i18n-data.js`,
`content/page/stages-grid.html`, `brand/favicon.*`, `brand/apple-touch-icon.png`,
`brand/og-image.png` or `sitemap.xml` is edited by hand. Change the source, re-run the
generator, commit the output.

```bash
python3 tools/build_chain_data.py    # content/chain.json  -> assets/js/chain-data.js
python3 tools/build_i18n.py          # i18n/*.json         -> assets/js/i18n-data.js
python3 tools/build_docs.py          # noctua-package/     -> docs/*.html + the grid fragment
python3 tools/build_brand.py         # brand/logo-mark.svg -> favicon.svg/.ico, touch icon, OG card
python3 tools/stamp_origin.py        # content/site.json   -> canonical, hreflang, og:image
python3 tools/build_sitemap.py https://samuele95.github.io/noctua/   # + robots.txt
```

`build_i18n.py` refuses to write if the two dictionaries have different key sets.
`build_sitemap.py` refuses to write without an origin, because a guessed one advertises pages
that do not exist.

Moving the site to another host is one edit to `content/site.json`, then `stamp_origin.py` and
`build_sitemap.py`.

## Checking

```bash
python3 tools/check_i18n.py          # every key in both dictionaries; no hardcoded visible string
python3 tools/check_links.py         # every local ref, anchor and absolute URL resolves
node tools/check_chain.js            # the diagram is usable with a keyboard, in both languages
node tools/shoot.js                  # screenshots + console, overflow, 4xx and external-request checks
npx htmlhint@1 index.html "docs/*.html"
npx lighthouse@12 <url> --only-categories=performance,accessibility,best-practices,seo
```

`tools/shoot.js` and `tools/check_chain.js` need a local server and the system Chrome:

```bash
python3 -m http.server 8765 --bind 127.0.0.1
npm i -D playwright-core
```

Screenshots land in `screenshots/`, which is git-ignored — it is 39 MB of build output.

## CI

[`.github/workflows/checks.yml`](.github/workflows/checks.yml) runs on every push and pull
request. It does **not** deploy — Pages publishes the branch directly. What it guards is the
property that makes that safe: it regenerates everything deterministic and fails if the working
tree moved, so a generated file cannot quietly stop matching its source. Then it runs the same
checks a working session runs by hand: the dictionaries, the links, the HTML, the diagram's
keyboard behaviour, and a screenshot pass that fails on console errors, horizontal overflow,
any response ≥ 400 and any external request.

The brand exports are deliberately outside the drift check: they are PNG and ICO, and two
librsvg or Chrome versions do not produce identical bytes. Their source is one SVG, and
`tools/build_brand.py` is the only thing that ever writes them.

## Design notes

[`brand/BRAND.md`](brand/BRAND.md) is one page: the idea behind the mark, the palette with
every measured contrast ratio, the type, the spacing, and do/don't. `CLAUDE.md` is the working
memory of the sessions that built this — the decisions, the deviations, every check with its
output, and the lessons.
