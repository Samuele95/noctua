#!/usr/bin/env python3
"""Generate the package-derived HTML: the nine docs pages, and the stages grid fragment.

The pages must not be able to drift from the package, so no skill text is authored here.
Each page carries the FULL `description` from that skill's SKILL.md frontmatter, lifted
verbatim and wrapped in lang="en" — the site quotes the skill, it does not summarise it.
Everything else on the page is a cell of the chain map, read from content/chain.json.

`document-project` has no SKILL.md in this package: its page is built from its row in
noctua/references/chain-map.md and is labelled external, which is the same evidence that
justifies the label — the folder is not there.

Extended at C5 from the version that generated only the grid fragment; that generator's
frontmatter parser and its "quote, never paraphrase" rule are kept as they were, and the
fragment now carries the landing's own class names so it can replace the hand-written grid
whenever that is wanted. It is not wired into index.html: those cards are condensations
Delta approved at C3, and the full description lives here instead.
"""
from __future__ import annotations

import html
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PKG = ROOT / "noctua-package"
DOCS = ROOT / "docs"
GRID = ROOT / "content" / "page" / "stages-grid.html"

# order follows the lanes in chain-map.md, not the alphabet
PACKAGED = [
    ("spec-analysis", "spec", "/spec-analysis"),
    ("domain-forge", "forge (prose) · refine", "/domain-forge"),
    ("dataset-forge", "forge (dataset)", "/dataset-forge"),
    ("data-lens", "lens", "/data-lens"),
    ("dataset-shaper", "shape", "/dataset-shaper"),
    ("inferred-questions", "questions", "/inferred-questions"),
    ("model-chat", "chat", "/model-chat"),
    ("blueprint", "blueprint", "/blueprint"),
]

EXTERNAL = {
    "slug": "document-project",
    "stage": "document",
    "command": "/document-project",
    # every clause below is a cell of the chain-map `document` row
    "sentence": "Consumes everything above and produces LaTeX / PDF, chapter by chapter; "
                "the orchestrator's check is that the PDF compiles.",
    "source": "noctua-package/noctua/references/chain-map.md",
    "source_label": "noctua/references/chain-map.md § Stages, row document",
}

SITE = json.loads((ROOT / "content" / "site.json").read_text()) \
    if (ROOT / "content" / "site.json").exists() else {}
ORIGIN = (SITE.get("origin") or "").rstrip("/")
ORIGIN = ORIGIN + "/" if ORIGIN else ""

CHAIN = json.loads((ROOT / "content" / "chain.json").read_text())
STAGES = {s["id"]: s for s in CHAIN["stages"]}
LANES = {l["id"]: l for l in CHAIN["lanes"]}


def description(slug: str) -> str:
    """The frontmatter `description`, unfolded to a single line."""
    text = (PKG / slug / "SKILL.md").read_text()
    block = text.split("---", 2)[1]
    m = re.search(r"^description:\s*(>-|>|\|)?\s*\n?(.*?)(?=^\w+:|\Z)", block, re.S | re.M)
    raw = m.group(2) if m.group(1) else m.group(0).split(":", 1)[1]
    return " ".join(raw.split())


MIN_CARD, MAX_CARD = 105, 330


def opening(text: str) -> str:
    """The skill's own opening definition, verbatim, elided where it runs long.

    Some descriptions open with a 700-character sentence, so a card cannot always hold
    a whole one. Where the quote is cut, it ends in an ellipsis — the ordinary mark for
    an elided quotation — and the full description is on the skill's docs page. A quote
    is never paraphrased to make it fit.
    """
    for m in re.finditer(r"(?:\.(?=\s)|:(?=\s)|;(?=\s)|\s—\s)", text):
        head = text[: m.start()].rstrip()
        if len(head) < MIN_CARD:
            continue
        if len(head) > MAX_CARD:
            break
        return head + "." if text[m.start()] == "." else head + " …"
    cut = text.rfind(" ", 0, MAX_CARD)
    return text[:cut].rstrip(" ,;—") + " …"


def flags(slug: str) -> list[str]:
    """Every `--flag` the skill's own SKILL.md names, verbatim and de-duplicated.

    Skill-level and script-level flags are not separated, because the files do not mark
    the difference in a way that can be read mechanically — so the page says plainly that
    this is every flag the file names, and links to the file.
    """
    body = (PKG / slug / "SKILL.md").read_text().split("---", 2)[2]
    return sorted(set(re.findall(r"`(--[a-z][a-z-]*)`", body)))


def invocations(slug: str) -> list[str]:
    """Invocation forms the SKILL.md writes out, verbatim. Some files give none."""
    body = (PKG / slug / "SKILL.md").read_text().split("---", 2)[2]
    out: list[str] = []
    for raw in re.findall(rf"`(/{re.escape(slug)}[^`]*)`", body):
        form = " ".join(raw.split())
        if form not in out:
            out.append(form)
    return out


def stages_of(slug: str) -> list[dict]:
    return [s for s in CHAIN["stages"] if s["skill"] == slug]


def lanes_of(slug: str) -> list[str]:
    ids: list[str] = []
    for st in stages_of(slug):
        for lane in st.get("lanes", []):
            if lane not in ids:
                ids.append(lane)
    return ids


def esc(text: str) -> str:
    return html.escape(text, quote=False)


def quoted(text: str) -> str:
    """Escape, then render the source's own backtick spans as <code>.

    This formats the quotation, it does not edit it: `analysis` becomes <code>analysis</code>
    and no word changes. Leaving the backticks as literal characters would show markdown
    source in a rendered page, which reads as a defect rather than as fidelity.
    """
    return re.sub(r"`([^`]+)`", r"<code>\1</code>", esc(text))


# ── the grid fragment (kept from the earlier generator, re-classed) ──────────
def card(stage: str, command: str, sentence: str, slug: str, external: bool) -> str:
    pill = '\n            <span class="ext" data-i18n="skill.external">external</span>' if external else ""
    return f"""        <article class="skill">
          <div class="skill-top">
            <h3 translate="no">{esc(slug)}</h3>
            <code class="cmd">{esc(command)}</code>{pill}
          </div>
          <p lang="en">{esc(sentence)}</p>
          <p class="skill-src"><a href="docs/{slug}.html"><span data-i18n="skill.source">source</span>: <span lang="en">{esc(stage)}</span></a></p>
        </article>"""


# ── the docs pages ───────────────────────────────────────────────────────────
MARK = ('<svg viewBox="0 0 64 64" aria-hidden="true" focusable="false">'
        '<path d="M6.5 20.5C16 14.5 25 19 32 23.5 39 19 48 14.5 57.5 20.5" fill="none" '
        'stroke="currentColor" stroke-width="6" stroke-linecap="round"/>'
        '<circle cx="20" cy="35" r="10.5" fill="none" stroke="currentColor" stroke-width="5.5"/>'
        '<circle cx="20" cy="35" r="5.4" fill="#C8622B"/>'
        '<path d="M44 24.5l9.09 5.25v10.5L44 45.5l-9.09-5.25v-10.5z" fill="none" '
        'stroke="currentColor" stroke-width="5.5" stroke-linejoin="round"/>'
        '<path d="M44 29.6l4.68 2.7v5.4L44 40.4l-4.68-2.7v-5.4z" fill="#C8622B"/>'
        '<path d="M27.8 46.8h8.4L32 56.2z" fill="currentColor"/></svg>')

ROW_FIELDS = [("consumes", "chain.f.consumes"), ("produces", "chain.f.produces"),
              ("check", "chain.f.check"), ("gate", "chain.f.gate"),
              ("unattended", "chain.f.unattended"), ("rerun", "chain.f.rerun")]


def stage_block(st: dict) -> str:
    pairs = "".join(
        f"""
            <div class="detail-pair">
              <dt data-i18n="{key}">{key}</dt>
              <dd lang="en">{quoted(st[field])}</dd>
            </div>"""
        for field, key in ROW_FIELDS if st.get(field))
    return f"""      <section class="doc-stage">
        <h3><span class="doc-stage-name" translate="no">{esc(st['label'])}</span>
            <code lang="en">{esc(st['invocation'])}</code></h3>
        <dl class="detail-grid">{pairs}
        </dl>
      </section>"""


def page(slug: str, command: str, desc: str, source_href: str, source_label: str,
         external: bool) -> str:
    sts = stages_of(slug)
    lane_chips = "".join(
        f'<code data-i18n="lane.{lid}">{esc(LANES[lid]["label"] if lid in LANES else lid)}</code>'
        for lid in lanes_of(slug))
    flag_chips = "".join(f"<code>{esc(f)}</code>" for f in (flags(slug) if not external else []))
    invs = invocations(slug) if not external else []
    inv_list = "".join(f"<li><code lang=\"en\">{esc(i)}</code></li>" for i in invs)

    parts = [f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(slug)} — Noctua</title>
<meta name="description" data-i18n-attr="content:docs.metaDescription" content="What this Noctua stage consumes, what it produces, how the orchestrator checks its product and where it stops for a human — read from the chain map and the skill's own description.">
<meta property="og:type" content="article">
<meta property="og:title" content="{esc(slug)} — Noctua">
<meta property="og:description" data-i18n-attr="content:docs.metaDescription" content="What this Noctua stage consumes, what it produces, how the orchestrator checks its product and where it stops for a human.">
<link rel="canonical" href="{ORIGIN}docs/{esc(slug)}.html">
<meta property="og:url" content="{ORIGIN}docs/{esc(slug)}.html">
<meta property="og:image" content="{ORIGIN or '../'}brand/og-image.png">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:image:alt" data-i18n-attr="content:meta.ogImageAlt" content="The Noctua mark — two owl eyes, one a circle and one a polygon — beside the words &ldquo;The owl over the chain&rdquo; and three numbers.">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:image" content="{ORIGIN or '../'}brand/og-image.png">
<link rel="alternate" hreflang="en" href="{ORIGIN}docs/{esc(slug)}.html?lang=en">
<link rel="alternate" hreflang="it" href="{ORIGIN}docs/{esc(slug)}.html?lang=it">
<link rel="alternate" hreflang="x-default" href="{ORIGIN}docs/{esc(slug)}.html">
<link rel="icon" href="../brand/favicon.svg" type="image/svg+xml">
<link rel="icon" href="../brand/favicon.ico" sizes="any">
<link rel="apple-touch-icon" href="../brand/apple-touch-icon.png">
<link rel="preload" href="../assets/fonts/plex-sans-400.woff2" as="font" type="font/woff2" crossorigin>
<link rel="preload" href="../assets/fonts/space-grotesk-500.woff2" as="font" type="font/woff2" crossorigin>
<link rel="stylesheet" href="../assets/css/fonts.css">
<link rel="stylesheet" href="../assets/css/tokens.css">
<link rel="stylesheet" href="../assets/css/base.css">
<link rel="stylesheet" href="../assets/css/chain.css">
<link rel="stylesheet" href="../assets/css/landing.css">
<link rel="stylesheet" href="../assets/css/docs.css">
<script src="../assets/js/i18n-data.js"></script>
<script src="../assets/js/i18n.js" defer></script>
<script src="../assets/js/theme.js"></script>
</head>
<body>
<a class="skip" href="#main" data-i18n="a11y.skip">Skip to content</a>

<header class="site-head">
  <div class="shell">
    <a class="brand" href="../index.html" translate="no">{MARK}<b>noctua</b></a>
    <nav class="nav" aria-label="Sections">
      <a href="../index.html#chain" data-i18n="nav.chain">the chain</a>
      <a href="../index.html#stages" data-i18n="nav.stages">the stages</a>
      <a href="../index.html#verify" data-i18n="nav.verify">how it verifies</a>
      <a href="../index.html#start" data-i18n="nav.start">get started</a>
    </nav>
    <div class="head-tools">
      <button class="tool-btn" type="button" data-lang-toggle>IT</button>
      <button class="tool-btn" type="button" data-theme-toggle>light</button>
    </div>
  </div>
</header>

<main id="main">
  <article class="shell doc">
    <nav class="crumbs" aria-label="Breadcrumb">
      <a href="../index.html" data-i18n="docs.home">Noctua</a>
      <span aria-hidden="true">/</span>
      <a href="../index.html#stages" data-i18n="docs.stages">the stages</a>
      <span aria-hidden="true">/</span>
      <span aria-current="page" translate="no">{esc(slug)}</span>
    </nav>

    <header class="doc-head">
      <h1 translate="no">{esc(slug)}</h1>
      <code class="doc-cmd">{esc(command)}</code>"""]

    if external:
        parts.append('\n      <span class="ext" data-i18n="skill.external">external</span>')
    parts.append("""
    </header>""")

    if external:
        parts.append("""
    <p class="doc-note" data-i18n="docs.externalNote">This skill is not part of the package.
      Everything below is read from its row in the chain map, which is the only place the
      package describes it — and that absence is what the label rests on.</p>""")

    parts.append(f"""
    <section class="doc-section">
      <h2 data-i18n="docs.what">What it is</h2>
      <p class="doc-note" data-i18n="{'docs.rowVerbatim' if external else 'docs.descVerbatim'}">{'The chain map row, in the package&rsquo;s own words.' if external else 'The skill&rsquo;s own description, unedited. It stays in English because it is the package&rsquo;s text, not ours.'}</p>
      <p class="doc-desc" lang="en">{quoted(desc)}</p>
    </section>

    <section class="doc-section">
      <h2 data-i18n="docs.inChain">In the chain</h2>
      <p class="doc-note" data-i18n="docs.rowNote">Every value below is a cell of
        <code>noctua/references/chain-map.md</code> &sect; Stages, kept in its own words.</p>
{chr(10).join(stage_block(st) for st in sts)}
    </section>

    <section class="doc-section">
      <h2 data-i18n="docs.lanes">On the lanes</h2>
      <p class="doc-note" data-i18n="docs.lanesNote">The lanes whose default order includes this
        stage, from the chain map &sect; Lanes.</p>
      <p class="chips">{lane_chips}</p>
    </section>""")

    if not external:
        parts.append(f"""

    <section class="doc-section">
      <h2 data-i18n="docs.trigger">Trigger and flags</h2>""")
        if invs:
            parts.append(f"""
      <p class="doc-note" data-i18n="docs.invNote">Invocation forms its <code>SKILL.md</code>
        writes out, verbatim.</p>
      <ul class="doc-invocations">{inv_list}</ul>""")
        if flag_chips:
            parts.append(f"""
      <p class="doc-note" data-i18n="docs.flagsNote">Every <code>--flag</code> that file names.
        Skill-level and script-level flags are not separated here, because the file does not mark
        the difference in a way a generator can read; open the source for the distinction.</p>
      <p class="chips">{flag_chips}</p>""")
        parts.append("""
    </section>""")

    parts.append(f"""

    <section class="doc-section">
      <h2 data-i18n="docs.source">Source</h2>
      <p><a class="doc-source" href="../{source_href}"><span lang="en">{esc(source_label)}</span></a></p>
    </section>
  </article>
</main>

<footer class="site-foot">
  <div class="shell">
    <p class="foot-brand" translate="no">{MARK}<b>noctua</b></p>
    <p data-i18n="foot.note" style="margin-top:var(--s-3)">Every factual sentence on this page
      traces to a file in the package; the trace table is <code>content/SOURCES.md</code> in this
      repository.</p>
  </div>
</footer>
</body>
</html>
""")
    return "".join(parts)


def main() -> int:
    DOCS.mkdir(exist_ok=True)
    GRID.parent.mkdir(parents=True, exist_ok=True)

    cards, pages = [], 0
    for slug, stage, cmd in PACKAGED:
        desc = description(slug)
        cards.append(card(stage, cmd, opening(desc), slug, False))
        (DOCS / f"{slug}.html").write_text(
            page(slug, cmd, desc, f"noctua-package/{slug}/SKILL.md",
                 f"{slug}/SKILL.md", False))
        pages += 1

    cards.append(card(EXTERNAL["stage"], EXTERNAL["command"], EXTERNAL["sentence"],
                      EXTERNAL["slug"], True))
    (DOCS / f"{EXTERNAL['slug']}.html").write_text(
        page(EXTERNAL["slug"], EXTERNAL["command"], EXTERNAL["sentence"],
             EXTERNAL["source"], EXTERNAL["source_label"], True))
    pages += 1

    GRID.write_text(
        "<!-- GENERATED by tools/build_docs.py from noctua-package/*/SKILL.md — do not edit.\n"
        "     Not wired into index.html: those cards are condensations Delta approved at C3.\n"
        "     This fragment carries the landing's class names so it can replace them on request. -->\n"
        '<div class="skill-grid">\n' + "\n".join(cards) + "\n</div>\n")

    print(f"docs/ written — {pages} pages "
          f"({len(PACKAGED)} from SKILL.md, 1 from the chain map); "
          f"stages-grid.html regenerated with {len(cards)} cards")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
