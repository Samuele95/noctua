#!/usr/bin/env python3
"""Write sitemap.xml — and refuse to write a wrong one.

The sitemap protocol requires a fully-qualified URL in every <loc>; a relative path is not
valid and a guessed origin is worse than no file at all, because a wrong sitemap tells
crawlers about pages that do not exist. So the origin is required, not defaulted:

    python3 tools/build_sitemap.py https://<user>.github.io/<repo>/

Without it the script prints the URLs it would emit and exits 2, which is the state this
repo is in until Delta supplies the Pages URL (C7). The same run should also stamp the
`Sitemap:` line into robots.txt.
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path
from urllib.parse import urljoin

ROOT = Path(__file__).resolve().parent.parent
LANGS = sorted(p.stem for p in (ROOT / "i18n").glob("*.json"))


def pages() -> list[str]:
    out = ["index.html"]
    out += sorted(f"docs/{p.name}" for p in (ROOT / "docs").glob("*.html"))
    return out


def main(argv: list[str]) -> int:
    paths = pages()
    if len(argv) < 2:
        print("no origin given — nothing written.\n"
              "sitemap.xml needs absolute URLs, and a guessed origin is worse than no file.\n"
              f"it would list {len(paths)} pages, each with {len(LANGS)} hreflang alternates:")
        for p in paths:
            print(f"  <origin>/{p}")
        print("\nrun:  python3 tools/build_sitemap.py https://<user>.github.io/<repo>/")
        return 2

    origin = argv[1].rstrip("/") + "/"
    today = date.today().isoformat()
    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"',
             '        xmlns:xhtml="http://www.w3.org/1999/xhtml">']
    for p in paths:
        loc = urljoin(origin, p)
        lines.append("  <url>")
        lines.append(f"    <loc>{loc}</loc>")
        for lang in LANGS:
            lines.append(f'    <xhtml:link rel="alternate" hreflang="{lang}" '
                         f'href="{loc}?lang={lang}"/>')
        lines.append(f'    <xhtml:link rel="alternate" hreflang="x-default" href="{loc}"/>')
        lines.append(f"    <lastmod>{today}</lastmod>")
        lines.append("  </url>")
    lines.append("</urlset>")
    (ROOT / "sitemap.xml").write_text("\n".join(lines) + "\n")

    robots = ROOT / "robots.txt"
    body = [ln for ln in robots.read_text().splitlines() if not ln.startswith("Sitemap:")]
    body.append(f"Sitemap: {urljoin(origin, 'sitemap.xml')}")
    robots.write_text("\n".join(body) + "\n")

    print(f"sitemap.xml written — {len(paths)} pages, "
          f"{len(LANGS) + 1} alternates each; robots.txt Sitemap: line stamped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
