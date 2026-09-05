#!/usr/bin/env python3
"""Rasterise a mark/lockup SVG at a given size, in a named theme.

librsvg resolves `currentColor` from the inherited `color` property, so a theme is
applied by stamping `style="color:…"` on the root <svg> before handing the file to
rsvg-convert. Nothing else about the drawing changes between themes: the accent
colours are literal in the SVG on purpose, because an accent that flips with the
theme is a second logo, not the same one.
"""
from __future__ import annotations

import re
import subprocess
import tempfile
from pathlib import Path

def render(svg_path: Path, out_path: Path, size: int, ink: str, background: str | None = None,
           height: int | None = None) -> Path:
    svg = svg_path.read_text()
    svg = re.sub(r"<svg\b", f'<svg style="color:{ink}"', svg, count=1)
    with tempfile.NamedTemporaryFile("w", suffix=".svg", delete=False) as tmp:
        tmp.write(svg)
        tmp_path = Path(tmp.name)
    cmd = ["rsvg-convert", "-w", str(size)]
    if height is not None:
        cmd += ["-h", str(height)]
    if background:
        cmd += ["-b", background]
    cmd += [str(tmp_path), "-o", str(out_path)]
    subprocess.run(cmd, check=True, capture_output=True)
    tmp_path.unlink()
    return out_path
