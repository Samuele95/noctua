#!/usr/bin/env python3
"""Stamp the deployed origin into every page's head.

Five things need a fully-qualified URL and cannot be written until the site has an origin:
`rel=canonical`, the `hreflang` alternates, `og:url`, `og:image` and `twitter:image`. Until
C7 they were relative or absent, because a guessed origin is worse than none. The origin now
lives in content/site.json; this script is idempotent, so re-running it after a rebuild is
safe and is the intended way to change hosts.

The docs pages are generated, so this stamps them through tools/build_docs.py, which reads
the same file; only index.html is rewritten in place.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent.parent
SITE = json.loads((ROOT / "content" / "site.json").read_text())
ORIGIN = SITE["origin"].rstrip("/") + "/"
BASE = urlsplit(ORIGIN).path or "/"


def stamp_index() -> int:
    p = ROOT / "index.html"
    s = p.read_text()
    before = s

    # canonical + og:url are inserted once, then kept in sync
    s = re.sub(r'\n<link rel="canonical" href="[^"]*">', "", s)
    s = re.sub(r'\n<meta property="og:url" content="[^"]*">', "", s)
    s = s.replace('<meta property="og:type" content="website">',
                  f'<link rel="canonical" href="{ORIGIN}">\n'
                  f'<meta property="og:url" content="{ORIGIN}">\n'
                  '<meta property="og:type" content="website">')

    s = re.sub(r'(<link rel="alternate" hreflang="(?:en|it)" href=")[^"]*(">)',
               lambda m: f'{m.group(1)}{ORIGIN}?lang={"en" if "en" in m.group(0) else "it"}{m.group(2)}', s)
    s = re.sub(r'(<link rel="alternate" hreflang="x-default" href=")[^"]*(">)',
               rf'\g<1>{ORIGIN}\g<2>', s)
    s = re.sub(r'((?:property="og:image"|name="twitter:image") content=")[^"]*(")',
               rf'\g<1>{ORIGIN}brand/og-image.png\g<2>', s)

    p.write_text(s)
    return 0 if s == before else 1


def main() -> int:
    changed = stamp_index()
    subprocess.run([sys.executable, str(ROOT / "tools" / "build_docs.py")], check=True)
    subprocess.run([sys.executable, str(ROOT / "tools" / "build_404.py")], check=True)
    print(f"origin stamped: {ORIGIN}  (base path {BASE}; index.html "
          f"{'rewritten' if changed else 'already current'}; "
          "docs pages and 404.html regenerated)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
