#!/usr/bin/env python3
"""
smoke_test.py — headless verification that the open-questions layer
renders correctly in the output HTML.

The render script is bundled inline and never executes during
apply_layer.py — only when a browser opens the file. This smoke test
spawns headless Chrome to render the file, then inspects the resulting
DOM to confirm:

  1. The pane has class `tab-pane` but NOT `active` — i.e. it is hidden
     until its tab button is clicked. (A previous regression mounted the
     pane as visible alongside the host's active tab.)
  2. A tab button has been appended to the host's `nav.tabs`, with the
     correct `data-tab` and a count badge matching the data script's
     question count.
  3. The number of rendered question cards equals the number of
     questions in the data script.
  4. No uncaught JS errors fired during render.

Soft-fail by design: if `google-chrome` (or `chromium`) is not installed,
the script prints a warning and exits 0 — the layer is still valid as
HTML, we just couldn't verify the dynamic behaviour automatically.

Usage:
    python smoke_test.py --html OUT.html
    python smoke_test.py --html OUT.html --strict   # exit 1 on warnings

Exit codes:
    0 — smoke test passed (or chrome absent and --strict not set)
    1 — render produced a verifiable defect (with --strict, also for warnings)
    2 — chrome could not run the page at all
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path


CHROME_CANDIDATES = ("google-chrome", "chromium", "chromium-browser", "chrome")


def find_chrome() -> str | None:
    for c in CHROME_CANDIDATES:
        if shutil.which(c):
            return c
    return None


def dump_dom(chrome: str, file_url: str, virtual_time_ms: int = 2000) -> tuple[str, str]:
    """Render the file with headless Chrome and return (dom, stderr)."""
    proc = subprocess.run(
        [
            chrome,
            "--headless",
            "--disable-gpu",
            "--no-sandbox",
            f"--virtual-time-budget={virtual_time_ms}",
            "--dump-dom",
            file_url,
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    return proc.stdout, proc.stderr


def check_render(html_path: Path, strict: bool) -> int:
    chrome = find_chrome()
    if not chrome:
        msg = f"[smoke_test] no headless browser available (checked {CHROME_CANDIDATES})"
        if strict:
            print(msg + " — failing under --strict", file=sys.stderr)
            return 1
        print(msg + " — skipping (layer remains valid as static HTML)")
        return 0

    file_url = f"file://{html_path.resolve()}"
    try:
        dom, stderr = dump_dom(chrome, file_url)
    except subprocess.TimeoutExpired:
        print(f"[smoke_test] chrome timed out rendering {html_path}", file=sys.stderr)
        return 2

    if not dom:
        print(f"[smoke_test] chrome produced no output; stderr: {stderr[:400]}",
              file=sys.stderr)
        return 2

    findings: list[tuple[bool, str, str]] = []

    # Read the data script to know the expected question count.
    src = html_path.read_text(encoding="utf-8")
    m = re.search(
        r'<script\s+id="layer-open-questions-data"[^>]*>([\s\S]*?)</script>',
        src,
    )
    expected_n = 0
    if m:
        try:
            expected_n = len(json.loads(m.group(1)).get("questions", []))
        except json.JSONDecodeError:
            findings.append((False, "data-script-json", "layer data script is not valid JSON"))

    # (1) Pane is rendered without `active` so the host's CSS keeps it hidden.
    pane_pattern = re.compile(
        r'<section[^>]*class="[^"]*layer-open-questions[^"]*tab-pane(?:[^"]*)?"[^>]*>',
        re.IGNORECASE,
    )
    pane_match = pane_pattern.search(dom)
    if not pane_match:
        findings.append((False, "pane-mounted", "no section.layer-open-questions.tab-pane found"))
    else:
        is_active = " active" in pane_match.group(0) or 'tab-pane active' in pane_match.group(0)
        findings.append((not is_active, "pane-hidden-by-default",
                         "pane has the `active` class on load — should be hidden until tab click"
                         if is_active else "pane is hidden by default"))

    # (2) Tab button appended to nav.tabs (or nav[role=tablist]).
    # Strip the contents of script and style tags before matching so the
    # nav-pattern in our own inline render script (which appears as a
    # *string* in the DOM) does not get mistaken for a real nav element.
    dom_no_scripts = re.sub(
        r'<script\b[^>]*>[\s\S]*?</script>', '<script></script>',
        re.sub(r'<style\b[^>]*>[\s\S]*?</style>', '<style></style>', dom,
               flags=re.IGNORECASE),
        flags=re.IGNORECASE,
    )
    nav_match = re.search(
        r'<nav[^>]*(?:class="[^"]*tabs|role="tablist")[^>]*>([\s\S]*?)</nav>',
        dom_no_scripts,
        re.IGNORECASE,
    )
    if nav_match:
        nav_body = nav_match.group(1)
        btn_match = re.search(r'data-tab="open-questions"', nav_body)
        findings.append((bool(btn_match), "tab-button-in-nav",
                         "tab button appended to nav.tabs"
                         if btn_match else
                         "tab button NOT found inside nav.tabs — clicking it from the navbar will not work"))
        # Badge with the right count.
        badge_match = re.search(r'data-tab="open-questions"[^>]*>[\s\S]*?>(\d+)<', nav_body)
        if badge_match:
            n_shown = int(badge_match.group(1))
            ok = (n_shown == expected_n)
            findings.append((ok, "badge-count-matches",
                             f"badge shows {n_shown}, data says {expected_n}"))
        else:
            findings.append((False, "badge-count-matches",
                             "no count badge found on tab button"))
    else:
        # The host page may simply have no nav.tabs (small fixtures). Don't
        # fail; record an info-level note.
        findings.append((True, "tab-button-in-nav",
                         "no nav.tabs present in host page — skipping tab-button check"))

    # (3) Card count matches.
    cards = re.findall(r'data-qid="q-\d+"', dom)
    findings.append((len(cards) == expected_n, "card-count-matches",
                     f"rendered {len(cards)} cards for {expected_n} questions"))

    # (4) No uncaught errors visible in chrome stderr. Chrome --headless
    # writes errors to stderr; we look for the typical patterns. Some
    # benign warnings always show; filter them out.
    bad_lines = [
        ln for ln in stderr.splitlines()
        if re.search(r"\b(Uncaught|ReferenceError|TypeError|Syntax\s*Error)\b", ln)
    ]
    findings.append((len(bad_lines) == 0, "no-js-errors",
                     "no JS errors" if not bad_lines
                     else f"{len(bad_lines)} JS error line(s): {bad_lines[0][:160]}"))

    # Report.
    failed = 0
    for ok, name, msg in findings:
        mark = "OK  " if ok else "FAIL"
        print(f"  {mark} {name:<28} {msg}")
        if not ok:
            failed += 1

    if failed:
        print(f"\n[smoke_test] {failed} check(s) failed for {html_path}", file=sys.stderr)
        return 1
    print(f"\n[smoke_test] all checks passed for {html_path}")
    return 0


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--html", required=True, help="path to the layered HTML output")
    p.add_argument("--strict", action="store_true",
                   help="exit 1 when chrome is absent (default: warn and exit 0)")
    args = p.parse_args(argv)
    return check_render(Path(args.html), args.strict)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
