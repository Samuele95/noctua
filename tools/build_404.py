#!/usr/bin/env python3
"""Generate 404.html.

GitHub Pages serves this file for any unmatched path at any depth, so every reference in
it must be absolute from the site root: a relative one would resolve against the URL that
does not exist. The root is the base path of the origin in content/site.json, which is why
this page is generated rather than hand-written — the base path is interpolated once
instead of being search-and-replaced later.
"""
from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent.parent
SITE = json.loads((ROOT / "content" / "site.json").read_text())
BASE = urlsplit(SITE["origin"]).path or "/"

MARK = ('<svg viewBox="0 0 64 64" aria-hidden="true" focusable="false">'
        '<path d="M6.5 20.5C16 14.5 25 19 32 23.5 39 19 48 14.5 57.5 20.5" fill="none" '
        'stroke="currentColor" stroke-width="6" stroke-linecap="round"/>'
        '<circle cx="20" cy="35" r="10.5" fill="none" stroke="currentColor" stroke-width="5.5"/>'
        '<circle cx="20" cy="35" r="5.4" fill="#C8622B"/>'
        '<path d="M44 24.5l9.09 5.25v10.5L44 45.5l-9.09-5.25v-10.5z" fill="none" '
        'stroke="currentColor" stroke-width="5.5" stroke-linejoin="round"/>'
        '<path d="M44 29.6l4.68 2.7v5.4L44 40.4l-4.68-2.7v-5.4z" fill="#C8622B"/>'
        '<path d="M27.8 46.8h8.4L32 56.2z" fill="currentColor"/></svg>')

PAGE = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title data-i18n="e404.title">Not here — Noctua</title>
<meta name="robots" content="noindex">
<link rel="icon" href="{BASE}brand/favicon.svg" type="image/svg+xml">
<link rel="icon" href="{BASE}brand/favicon.ico" sizes="any">
<link rel="apple-touch-icon" href="{BASE}brand/apple-touch-icon.png">
<link rel="preload" href="{BASE}assets/fonts/plex-sans-400.woff2" as="font" type="font/woff2" crossorigin>
<link rel="preload" href="{BASE}assets/fonts/space-grotesk-500.woff2" as="font" type="font/woff2" crossorigin>
<link rel="stylesheet" href="{BASE}assets/css/fonts.css">
<link rel="stylesheet" href="{BASE}assets/css/tokens.css">
<link rel="stylesheet" href="{BASE}assets/css/base.css">
<link rel="stylesheet" href="{BASE}assets/css/landing.css">
<link rel="stylesheet" href="{BASE}assets/css/notfound.css">
<script src="{BASE}assets/js/i18n-data.js"></script>
<script src="{BASE}assets/js/i18n.js" defer></script>
<script src="{BASE}assets/js/theme.js"></script>
</head>
<body>
<header class="site-head">
  <div class="shell">
    <a class="brand" href="{BASE}" translate="no">{MARK}<b>noctua</b></a>
    <div class="head-tools">
      <button class="tool-btn" type="button" data-lang-toggle>IT</button>
      <button class="tool-btn" type="button" data-theme-toggle>light</button>
    </div>
  </div>
</header>

<main class="shell notfound">
  <div class="notfound-mark" aria-hidden="true">{MARK}</div>
  <p class="eyebrow">404</p>
  <h1 data-i18n="e404.heading">The owl looked. There is nothing here.</h1>
  <p class="lede" data-i18n="e404.body">That address does not match a page on this site. The chain
    is on the landing page, and every stage has its own page.</p>
  <div class="cta-row">
    <a class="btn btn-primary" href="{BASE}#chain" data-i18n="e404.chain">See the chain</a>
    <a class="btn btn-ghost" href="{BASE}docs/index.html" data-i18n="e404.pages">The nine stage pages</a>
  </div>
</main>
</body>
</html>
"""

(ROOT / "404.html").write_text(PAGE)
print(f"404.html written — root-absolute from {BASE}")
