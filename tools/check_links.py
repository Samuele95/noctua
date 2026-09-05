#!/usr/bin/env python3
"""Every reference on every page must resolve.

Local refs must exist on disk, anchors must have a matching id, and the five absolute URLs
the site is allowed to carry — canonical, the hreflang alternates, og:url, og:image,
twitter:image — must sit on this site's own origin and, where they name a file, point at one
that exists. Any other absolute URL is a failure: this site makes no external requests.
"""
import json
import re
import sys
from urllib.parse import urlsplit
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PAGES = [ROOT / "index.html", ROOT / "404.html", *sorted((ROOT / "docs").glob("*.html"))]
LANGS = {p.stem for p in (ROOT / "i18n").glob("*.json")}
SITE = json.loads((ROOT / "content" / "site.json").read_text()) \
    if (ROOT / "content" / "site.json").exists() else {}
ORIGIN = (SITE.get("origin") or "").rstrip("/") + "/" if SITE.get("origin") else ""
# 404.html is served for any unmatched path, so its refs are absolute from the site root
BASE_PATH = urlsplit(ORIGIN).path if ORIGIN else "/"

# <link rel="canonical"> and <link rel="alternate"> are checked as origin URLs, not as files
SELF_LINK = re.compile(r'<link\s+rel="(?:canonical|alternate)"[^>]*>')
ABSOLUTE_META = re.compile(
    r'<(?:link\s+rel="(?:canonical|alternate)"[^>]*href|'
    r'meta\s+(?:property="og:(?:url|image)"|name="twitter:image")[^>]*content)="([^"]+)"')

bad, checked, absolute = [], 0, 0
for page in PAGES:
    rel = page.relative_to(ROOT)
    html = page.read_text()
    ids = set(re.findall(r'\sid="([^"]+)"', html))

    for url in ABSOLUTE_META.findall(html):
        absolute += 1
        if not ORIGIN:
            if not url.startswith(("?", "./", "../", "brand/")):
                bad.append(f"{rel}: {url} — no origin recorded, so this must stay relative")
            continue
        if not url.startswith(ORIGIN):
            bad.append(f"{rel}: {url} — not on this site's origin ({ORIGIN})")
            continue
        tail = url[len(ORIGIN):].split("?")[0].split("#")[0]
        if tail and not (ROOT / tail).exists():
            bad.append(f"{rel}: {url} — origin URL names a file that does not exist")

    body = SELF_LINK.sub("", html)
    for ref in re.findall(r'(?:href|src)="([^"]+)"', body):
        if ref.startswith(("http://", "https://", "data:", "mailto:")):
            bad.append(f"{rel}: {ref} — external reference on a site that must make none")
            continue
        checked += 1
        if ref.startswith("?"):
            val = ref.split("=", 1)[1] if "=" in ref else ""
            if not ref.startswith("?lang=") or val not in LANGS:
                bad.append(f"{rel}: {ref} — not a language this site has")
        elif ref.startswith("#"):
            if ref[1:] not in ids:
                bad.append(f"{rel}: {ref} — no element with that id")
        elif ref.startswith("/"):
            if not ref.startswith(BASE_PATH):
                bad.append(f"{rel}: {ref} — root-absolute but not under {BASE_PATH}")
            elif not (ROOT / ref[len(BASE_PATH):].split("#")[0] or ROOT).exists():
                bad.append(f"{rel}: {ref} — file not found")
        else:
            target = (page.parent / ref.split("#")[0]).resolve()
            if not target.exists():
                bad.append(f"{rel}: {ref} — file not found")
            elif "#" in ref and target.suffix == ".html":
                frag = ref.split("#", 1)[1]
                if frag not in set(re.findall(r'\sid="([^"]+)"', target.read_text())):
                    bad.append(f"{rel}: {ref} — no element with id {frag!r} in {target.name}")

print(f"{len(PAGES)} pages · {checked} local references · {absolute} absolute URLs on "
      f"{ORIGIN or '(no origin yet)'}")
for b in bad:
    print("FAIL " + b)
print("OK — every link resolves" if not bad else "")
sys.exit(1 if bad else 0)
