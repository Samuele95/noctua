#!/usr/bin/env python3
"""The grep the brief asks for: prove no visible English is hardcoded in the page.

Three checks, all of which fail the build:
  1. every key the page or chain.js asks for exists in BOTH dictionaries;
  2. every key in the dictionaries is actually used (a dead key is a translation nobody sees);
  3. no visible text node sits outside a translated element.

The one allowed exception is the skills' own source text — their `description` and their
chain-map row — which stays English inside lang="en", as the brief specifies. Skill names
and slash commands are identifiers, marked translate="no".
"""
from __future__ import annotations

import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PAGES = [ROOT / "index.html", ROOT / "404.html", *sorted((ROOT / "docs").glob("*.html"))]
SKIP_TAGS = {"script", "style"}

problems: list[str] = []
dicts = {p.stem: json.loads(p.read_text()) for p in sorted((ROOT / "i18n").glob("*.json"))}
pages = {p: p.read_text() for p in PAGES}
html = "\n".join(pages.values())

# ── 1. keys asked for exist everywhere ───────────────────────────────────────
known = set().union(*(set(d) for d in dicts.values()))
used = set(re.findall(r'data-i18n="([^"]+)"', html))
used |= {spec.split(":")[1] for attr in re.findall(r'data-i18n-attr="([^"]+)"', html)
         for spec in attr.split(";")}
# The scripts reach keys through variables and tables (FIELDS, labelKey), so matching call
# sites would miss them. Any string literal in the scripts that IS a key counts as a use.
for js in ("chain.js", "theme.js", "i18n.js"):
    src = (ROOT / "assets/js" / js).read_text()
    for _, lit in re.findall(r"""(['"])((?:\\.|(?!\1).)*)\1""", src):
        if lit in known:
            used.add(lit)

for lang, d in dicts.items():
    for k in sorted(used - set(d)):
        problems.append(f"{lang}.json is missing key {k!r}")
    for k in sorted(set(d) - used):
        problems.append(f"{lang}.json has key {k!r} that nothing uses")

# ── 2 & 3. no untranslated visible text ──────────────────────────────────────
class Visible(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack: list[tuple[str, bool]] = []

    def _covered(self) -> bool:
        return any(c for _, c in self.stack)

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        covered = ("data-i18n" in a or a.get("lang") == "en" or a.get("translate") == "no"
                   or tag in SKIP_TAGS)
        if tag not in ("meta", "link", "br", "img", "input", "hr"):
            self.stack.append((tag, covered or self._covered()))

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] == tag:
                del self.stack[i:]
                return

    def handle_data(self, data):
        text = data.strip()
        if not text or self._covered():
            return
        if not re.search(r"[A-Za-z]{2}", text):
            return                       # punctuation and separators carry no language
        problems.append(f"untranslated text: {text[:70]!r}")

for path, src in pages.items():
    n = len(problems)
    Visible().feed(src)
    for i in range(n, len(problems)):
        problems[i] = f"{path.relative_to(ROOT)}: {problems[i]}"

for p in problems:
    print("FAIL " + p)
print(f"{len(pages)} pages · {len(used)} keys used · {' · '.join(f'{l} {len(d)} keys' for l, d in dicts.items())}")
print("OK — every key exists in both dictionaries and no visible string is hardcoded"
      if not problems else "")
sys.exit(1 if problems else 0)
