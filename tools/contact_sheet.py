#!/usr/bin/env python3
"""Build brand/directions/contact-sheet.png — the C1 artefact Delta actually looks at.

Every mark size on the sheet is a *true* rasterisation at that size (rsvg-convert at 16, 64
and 512), never a downscale of the big one: a 16 px favicon that was made by shrinking a 512 px
render tells you nothing about how the favicon will look. The 16 px tile is shown twice, at its
real size and magnified with nearest-neighbour, so the pixel grid is visible.

The sheet itself is laid out in HTML and screenshotted with headless Chrome, so the type
pairings render in the real faces rather than being described in a caption.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from render_svg import render

ROOT = Path(__file__).resolve().parent.parent
DIRS = ROOT / "brand" / "directions"
SIZES = (512, 64, 16)
SPECIMEN = "The chain is a functional pipeline of immutable snapshots."


def build_tiles(work: Path) -> dict:
    """Rasterise each mark and lockup at every size, in both themes."""
    meta = json.loads((DIRS / "directions.json").read_text())
    tiles: dict[tuple[int, str, str], Path] = {}
    for d in meta["directions"]:
        n = d["n"]
        for theme in ("dark", "light"):
            ink, bg = d[theme]["ink"], d[theme]["bg"]
            for size in SIZES:
                out = work / f"d{n}-{theme}-{size}.png"
                render(DIRS / str(n) / "mark.svg", out, size, ink, bg)
                tiles[(n, theme, str(size))] = out
            out = work / f"d{n}-{theme}-lockup.png"
            render(DIRS / str(n) / "logo.svg", out, 732, ink, bg, height=192)
            tiles[(n, theme, "lockup")] = out
    return meta, tiles


def panel(d: dict, theme: str, tiles: dict, work: Path) -> str:
    t = d[theme]
    n = d["n"]
    rel = lambda key: tiles[(n, theme, key)].name
    swatches = "".join(
        f'<div class="sw"><span style="background:{c["hex"]}"></span>'
        f'<b>{c["name"]}</b><i>{c["hex"]}</i></div>'
        for c in d["palette"]
    )
    return f"""
    <section class="panel" style="background:{t['bg']};color:{t['ink']}">
      <header class="ph">{theme}</header>
      <div class="big"><img src="{rel('512')}" width="330" height="330" alt=""></div>
      <div class="side">
        <img class="lockup" src="{rel('lockup')}" alt="">
        <div class="sizes">
          <figure><img src="{rel('64')}" width="64" height="64" alt=""><figcaption>64</figcaption></figure>
          <figure><img class="px" src="{rel('16')}" width="96" height="96" alt=""><figcaption>16 &times;6</figcaption></figure>
          <figure class="real"><img src="{rel('16')}" width="16" height="16" alt=""><figcaption>16</figcaption></figure>
        </div>
        <div class="palette">{swatches}</div>
        <div class="type">
          <p class="disp" style="font-family:{d['type']['displayStack']}">noctua</p>
          <p class="body" style="font-family:{d['type']['textStack']}">{SPECIMEN}</p>
          <p class="names">{d['type']['display']} &middot; {d['type']['text']}</p>
        </div>
      </div>
    </section>"""


def main() -> int:
    work = Path(tempfile.mkdtemp(prefix="noctua-sheet-"))
    meta, tiles = build_tiles(work)
    rows = "".join(
        f"""<article class="row">
              <h2><span class="num">{d['n']}</span>{d['name']}<em>{d['idea']}</em></h2>
              <div class="panels">{panel(d,'dark',tiles,work)}{panel(d,'light',tiles,work)}</div>
            </article>"""
        for d in meta["directions"]
    )
    html = f"""<!doctype html><meta charset="utf-8"><style>
      *{{box-sizing:border-box;margin:0;padding:0}}
      body{{width:1680px;background:#1C1E22;font-family:Inter,system-ui,sans-serif;padding:28px}}
      h1{{color:#fff;font-size:20px;font-weight:600;letter-spacing:-.2px;margin-bottom:4px}}
      .sub{{color:#8A8F98;font-size:13px;margin-bottom:24px}}
      .row{{margin-bottom:26px}}
      h2{{color:#E9EBEF;font-size:16px;font-weight:600;margin-bottom:10px;display:flex;align-items:center;gap:10px}}
      .num{{background:#3A3F48;color:#fff;width:24px;height:24px;border-radius:6px;
            display:grid;place-items:center;font-size:13px}}
      h2 em{{color:#8A8F98;font-style:normal;font-weight:400;font-size:13px}}
      .panels{{display:grid;grid-template-columns:1fr 1fr;gap:14px}}
      .panel{{border-radius:14px;padding:22px 24px;display:grid;
              grid-template-columns:330px 1fr;gap:22px;position:relative;min-height:376px}}
      .ph{{position:absolute;top:10px;right:14px;font-size:10px;letter-spacing:.14em;
           text-transform:uppercase;opacity:.42}}
      .big{{display:grid;place-items:center}}
      .side{{display:flex;flex-direction:column;gap:16px;justify-content:center}}
      .lockup{{width:305px;height:80px;object-fit:contain;object-position:left}}
      .sizes{{display:flex;align-items:flex-end;gap:20px}}
      .sizes figure{{display:flex;flex-direction:column;align-items:center;gap:5px}}
      .sizes figcaption{{font-size:9px;letter-spacing:.1em;opacity:.5}}
      .real{{padding-bottom:0}}
      .px{{image-rendering:pixelated}}
      .palette{{display:flex;gap:7px}}
      .sw{{display:flex;flex-direction:column;gap:3px;width:63px}}
      .sw span{{height:26px;border-radius:5px;box-shadow:inset 0 0 0 1px rgba(128,128,128,.35)}}
      .sw b{{font-size:9.5px;font-weight:600}}
      .sw i{{font-size:8.5px;font-style:normal;opacity:.55;font-variant-numeric:tabular-nums}}
      .disp{{font-size:34px;line-height:1;margin-bottom:6px}}
      .body{{font-size:12.5px;line-height:1.45;opacity:.8;max-width:330px}}
      .names{{font-size:9.5px;letter-spacing:.06em;opacity:.45;margin-top:5px;text-transform:uppercase}}
    </style>
    <h1>Noctua — three logo directions</h1>
    <p class="sub">C1 contact sheet. Every mark is rasterised at its real size: 512, 64 and 16 px.
       The 16 px tile appears twice, magnified &times;6 and at true size.</p>
    {rows}"""
    (work / "sheet.html").write_text(html)

    out = DIRS / "contact-sheet.png"
    subprocess.run(
        ["google-chrome", "--headless", "--disable-gpu", "--hide-scrollbars",
         "--force-device-scale-factor=2", "--window-size=1680,1600",
         f"--screenshot={work / 'shot.png'}", str(work / "sheet.html")],
        check=True, capture_output=True,
    )
    shutil.copy(work / "shot.png", out)
    print(f"contact-sheet.png written ({out.stat().st_size // 1024} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
