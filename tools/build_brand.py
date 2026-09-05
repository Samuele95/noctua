#!/usr/bin/env python3
"""Every brand export, from the two source SVGs and one HTML template.

Nothing here is drawn twice. `brand/logo-mark.svg` is the only definition of the mark;
the favicon is that file, the ICO and the touch icon are true rasterisations of it at the
sizes they are used at (never a downscale of a bigger render), and the Open Graph card is
an HTML page screenshotted at exactly 1200x630 so its type is the site's real type.
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from render_svg import render

ROOT = Path(__file__).resolve().parent.parent
BRAND = ROOT / "brand"
MARK = BRAND / "logo-mark.svg"

INK, PAPER, TERRACOTTA, STONE = "#12100E", "#F4F1EA", "#C8622B", "#8C8579"
ICO_SIZES = (16, 32, 48)
TOUCH = 180
OG = (1200, 630)


def favicon_svg() -> None:
    """The favicon is the mark itself, minified — one definition, not a copy."""
    out = BRAND / "favicon.svg"
    subprocess.run(["npx", "--yes", "svgo@3", "--multipass", "--quiet",
                    "-i", str(MARK), "-o", str(out)], check=True, capture_output=True)
    print(f"  favicon.svg          {out.stat().st_size} B")


def favicon_ico() -> None:
    """A real multi-size ICO: each frame rasterised at its own size, PNG-compressed.

    The container is written by hand because PIL's ICO writer *resamples* one base image to
    the sizes it is given — pass it a 16 px image and you get a one-frame file, pass it a
    48 px one and the 16 px frame is a downscale. A 48 px render shrunk to 16 px is mush;
    a true 16 px rasterisation keeps the strokes on the pixel grid, which is the whole
    reason the mark was drawn with 16 px in mind. ICO has allowed PNG frames since Vista.
    """
    import struct

    with tempfile.TemporaryDirectory() as tmp:
        blobs = []
        for size in ICO_SIZES:
            p = Path(tmp) / f"{size}.png"
            render(MARK, p, size, INK, PAPER)
            blobs.append((size, p.read_bytes()))

        offset = 6 + 16 * len(blobs)
        header = struct.pack("<HHH", 0, 1, len(blobs))
        entries, payload = b"", b""
        for size, blob in blobs:
            entries += struct.pack("<BBBBHHII", size % 256, size % 256, 0, 0, 1, 32,
                                   len(blob), offset)
            payload += blob
            offset += len(blob)
        out = BRAND / "favicon.ico"
        out.write_bytes(header + entries + payload)

    frames = ", ".join(f"{s}x{s}" for s, _ in blobs)
    print(f"  favicon.ico          {out.stat().st_size} B  ({frames}, each rasterised at its own size)")


def apple_touch_icon() -> None:
    """180x180, opaque, with the mark inset: iOS rounds the corners and ignores alpha."""
    from PIL import Image
    with tempfile.TemporaryDirectory() as tmp:
        inner = int(TOUCH * 0.68)
        p = Path(tmp) / "mark.png"
        render(MARK, p, inner, PAPER, None)
        canvas = Image.new("RGB", (TOUCH, TOUCH), INK)
        mark = Image.open(p).convert("RGBA")
        canvas.paste(mark, ((TOUCH - inner) // 2, (TOUCH - inner) // 2), mark)
        out = BRAND / "apple-touch-icon.png"
        canvas.save(out, optimize=True)
    print(f"  apple-touch-icon.png {out.stat().st_size // 1024} KB  ({TOUCH}x{TOUCH})")


OG_HTML = """<!doctype html><meta charset="utf-8"><style>
  @font-face {{ font-family:"Space Grotesk"; src:url("{fonts}/space-grotesk-500.woff2") format("woff2"); font-weight:500 }}
  @font-face {{ font-family:"IBM Plex Sans"; src:url("{fonts}/plex-sans-400.woff2") format("woff2"); font-weight:400 }}
  @font-face {{ font-family:"IBM Plex Mono"; src:url("{fonts}/plex-mono-400.woff2") format("woff2"); font-weight:400 }}
  * {{ margin:0; box-sizing:border-box }}
  body {{ width:{w}px; height:{h}px; background:{ink}; color:{paper};
         font-family:"IBM Plex Sans",sans-serif; display:grid;
         grid-template-columns:1fr 322px; align-items:center; gap:58px;
         padding:66px 80px; overflow:hidden; position:relative }}
  .left {{ display:flex; flex-direction:column; gap:30px }}
  .eyebrow {{ font-family:"IBM Plex Mono",monospace; font-size:19px; letter-spacing:.11em;
              text-transform:uppercase; color:#E0834B; max-width:none }}
  h1 {{ font-family:"Space Grotesk",sans-serif; font-weight:500; font-size:80px;
        letter-spacing:-.035em; line-height:.98; max-width:12ch }}
  p {{ font-size:26px; line-height:1.42; color:#A9A296; max-width:34ch }}
  .figs {{ display:flex; gap:56px; margin-top:8px }}
  .fig b {{ font-family:"Space Grotesk",sans-serif; font-weight:500; font-size:40px;
            letter-spacing:-.03em; display:block; line-height:1 }}
  .fig span {{ font-family:"IBM Plex Mono",monospace; font-size:15px; letter-spacing:.05em;
               color:{stone}; text-transform:uppercase }}
  .mark {{ display:grid; place-items:center }}
  .mark svg {{ width:302px; height:302px; color:{paper} }}
  .rule {{ position:absolute; left:0; bottom:0; height:11px; width:100%;
           background:linear-gradient(90deg,{terracotta} 0 34%,#241F1B 34% 100%) }}
</style>
<div class="left">
  <p class="eyebrow">a family of claude code skills</p>
  <h1>The owl over the chain.</h1>
  <p>Nine skills, one self-contained model, engines that verify what the language
     model proposes.</p>
  <div class="figs">
    <div class="fig"><b>78 / 78</b><span>acceptance</span></div>
    <div class="fig"><b>19</b><span>invariants</span></div>
    <div class="fig"><b>0</b><span>network deps</span></div>
  </div>
</div>
<div class="mark">{mark}</div>
<div class="rule"></div>
"""


def og_image() -> None:
    """1200x630, rendered at 2x and resampled, so the type is crisp at the delivered size."""
    from PIL import Image
    mark = MARK.read_text()
    mark = mark[mark.index("<path"):mark.rindex("</svg>")]
    mark = f'<svg viewBox="0 0 64 64" xmlns="http://www.w3.org/2000/svg">{mark}</svg>'
    with tempfile.TemporaryDirectory() as tmp:
        page = Path(tmp) / "og.html"
        page.write_text(OG_HTML.format(w=OG[0], h=OG[1], ink=INK, paper=PAPER,
                                       terracotta=TERRACOTTA, stone=STONE, mark=mark,
                                       fonts=(ROOT / "assets" / "fonts").as_uri()))
        shot = Path(tmp) / "og.png"
        subprocess.run(["google-chrome", "--headless", "--disable-gpu", "--hide-scrollbars",
                        "--force-device-scale-factor=2",
                        f"--window-size={OG[0]},{OG[1]}",
                        f"--screenshot={shot}", str(page)],
                       check=True, capture_output=True)
        out = BRAND / "og-image.png"
        Image.open(shot).convert("RGB").resize(OG, Image.LANCZOS).save(out, optimize=True)
    print(f"  og-image.png         {out.stat().st_size // 1024} KB  ({OG[0]}x{OG[1]})")


def main() -> int:
    print("brand exports:")
    favicon_svg()
    favicon_ico()
    apple_touch_icon()
    og_image()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
