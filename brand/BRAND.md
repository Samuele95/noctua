# Noctua — brand, in one page

## The idea

The mark is *Athene noctua*, the little owl, reduced to the one thing the framework is about:
**the same aperture drawn twice.** The left eye is a continuous circle; the right eye is that
circle resolved into straight segments. The language model proposes something smooth; the
symbolic engines verify it in discrete steps — and the face only works because both are there.

Above the eyes is the little owl's brow, which is the species' actual signature: *Athene noctua*
has **no ear tufts**, so a tufted owl is the wrong bird and the wrong mark. Below is the beak.

Direction picked by Delta at C1 (2026-09-04), with the palette and type of a second direction.
The two candidates it beat are kept in `brand/directions/` with the reasoning, and the contact
sheet that decided it is `brand/directions/contact-sheet.png`.

## The files

| file | what it is | where it is used |
|---|---|---|
| `logo.svg` | lockup — mark + wordmark, 236×64 | headers, README, slides |
| `logo-mark.svg` | the mark alone, 64×64 | **the one definition**; everything else is derived from it |
| `logo-mono.svg` | single colour, iris dropped out | stamps, embossing, one-ink print, laser |
| `favicon.svg` | `logo-mark.svg` minified | `rel="icon"` on every page |
| `favicon.ico` | 16 / 32 / 48, each rasterised at its own size | old browsers, Windows |
| `apple-touch-icon.png` | 180×180, opaque ink ground | iOS home screen |
| `og-image.png` | 1200×630 | Open Graph and Twitter cards |

`tools/build_brand.py` regenerates the last four from `logo-mark.svg`. Nothing is drawn twice:
edit the mark, re-run the script.

## Theme, and why the mark is one drawing

The ink is `currentColor`; the iris is literal. So the mark inverts with the theme while its
accent stays put. **An accent that flips with the theme is a second logo, not the same one.**

## Palette — five colours, two of them neutrals

| name | hex | role |
|---|---|---|
| Ink | `#12100E` | ground in dark, text in light |
| Paper | `#F4F1EA` | ground in light, text in dark |
| Terracotta | `#C8622B` | the iris; the accent; the primary button |
| Moss | `#4A6B5F` | the accent that carries **text** on Paper |
| Stone | `#8C8579` | muted rules, captions, the lane bar |

### Contrast, measured

| pair | value | verdict |
|---|---|---|
| Paper on Ink (body, dark) | `#F4F1EA` on `#12100E` | **16.83:1** — AA text |
| Ink on Paper (body, light) | `#12100E` on `#F4F1EA` | **16.83:1** — AA text |
| Terracotta on Ink | `#C8622B` on `#12100E` | **4.74:1** — AA text |
| Terracotta on Paper | `#C8622B` on `#F4F1EA` | **3.55:1** — AA large only |
| Moss on Paper | `#4A6B5F` on `#F4F1EA` | **5.23:1** — AA text |
| Moss on Ink | `#4A6B5F` on `#12100E` | **3.22:1** — AA large only |
| Stone on Ink | `#8C8579` on `#12100E` | **5.19:1** — AA text |
| Stone on Paper | `#8C8579` on `#F4F1EA` | **3.24:1** — AA large only |
| Ink on Terracotta (primary button) | `#12100E` on `#C8622B` | **4.74:1** — AA text |
| Ink on `#D2703A` (button hover) | `#12100E` on `#D2703A` | **5.53:1** — AA text |
| Dim text on Ink | `#A9A296` on `#12100E` | **7.50:1** — AA text |
| Dim text on Paper | `#5E574C` on `#F4F1EA` | **6.32:1** — AA text |
| Accent text on Ink | `#E0834B` on `#12100E` | **6.80:1** — AA text |

**The rule this table encodes:** terracotta carries text on ink, moss carries text on paper.
Neither carries text on the other ground. This is why the light theme is a real design and not an
inversion — it swaps the *text accent*, not just the background.

## Type

**Space Grotesk Medium (500)** for display: headings, the wordmark, numbers.
**IBM Plex Sans (400 / 500 / 600)** for text.
**IBM Plex Mono (400)** for commands, file names, eyebrows and table labels — anything that is an
identifier rather than prose.

Self-hosted as latin `woff2` subsets in `assets/fonts/` (108 KB, five files). Not linked from a
CDN: measured on the landing, the third-party stylesheet swung first paint between 1.6 s and 4.1 s
and Lighthouse performance between 75 and 99.

Scale — a minor third off 1 rem, named in `assets/css/tokens.css`:
`--t-xs .75` · `--t-sm .875` · `--t-base 1` · `--t-md 1.1875` · `--t-lg 1.5` · `--t-xl 2` ·
`--t-2xl 2.75` · `--t-3xl 3.75` · `--t-4xl 5` rem.

Headings set `letter-spacing: -0.025em` and `line-height: 1.05`; body runs at `1.6`.

## Spacing

A 4 px base, named `--s-1` … `--s-10`: `.25 .5 .75 1 1.5 2 3 4 6 8` rem. Section padding is
`--s-9` (6 rem) on desktop and `--s-7` (3 rem) below 700 px. The page shell is
`min(100% - 2.5rem, 1200px)`.

Around the mark, keep clear space of **one eye-width** (10 units of the 64-unit grid) on every
side. The mark's own bounding box already carries about 3 units of that.

## Do

- Use `logo-mark.svg` and let it inherit `currentColor`.
- Keep the terracotta iris on colour reproductions, at any size down to 16 px — it is what makes
  the mark legible as a favicon.
- Use `logo-mono.svg` where only one ink is available, and use it **large**: below about 24 px the
  eyes lose their holes and the pair reads as two blobs. Rendered and checked at 16 px and 512 px.
- Say *Athene noctua* in italics when the species is named.

## Don't

- Don't give the owl ear tufts. Two early drafts grew them from round line caps on the brow; the
  species has none, and butt caps are both the accurate drawing and the cleaner one.
- Don't fill the face pale and cut the eyes as plain dark holes — it reads as a **skull**, not an
  owl. Two drafts died that way. Eyes must be ringed or coloured.
- Don't swap the circle and the polygon, and don't make both eyes the same. That pair *is* the
  idea; without it the mark is a generic owl.
- Don't recolour the iris per theme.
- Don't set Paper on Terracotta: it measures 3.76:1 and fails for 14 px text. Use Ink.
- Don't stretch, rotate, outline, add a gradient, or put the mark on a busy photograph.
- Don't rebuild any export by hand — run `python3 tools/build_brand.py`.
