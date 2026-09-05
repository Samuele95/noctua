#!/usr/bin/env python3
"""Serve the repo locally under the SAME base path the site is deployed at.

`python3 -m http.server` serves the tree at `/`, but the site lives at `/noctua/`, and
404.html has to use root-absolute references because GitHub Pages serves it for any
unmatched path at any depth. Serving at `/` therefore fails checks that production
passes, and — worse — would pass checks production fails. This makes the two match.

    python3 tools/serve.py [port]        # http://127.0.0.1:8765/noctua/
"""
from __future__ import annotations

import functools
import json
import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent.parent
SITE = json.loads((ROOT / "content" / "site.json").read_text())
BASE = urlsplit(SITE["origin"]).path or "/"


class Handler(SimpleHTTPRequestHandler):
    def translate_path(self, path: str) -> str:
        split = urlsplit(path).path
        if BASE != "/" and split.startswith(BASE.rstrip("/")):
            path = "/" + split[len(BASE.rstrip("/")):].lstrip("/")
        return super().translate_path(path)

    def send_error(self, code, message=None, explain=None):
        page = ROOT / "404.html"
        if code == 404 and page.exists():
            body = page.read_bytes()
            self.send_response(404)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(body)
            return
        super().send_error(code, message, explain)

    def log_message(self, *a):  # quiet
        pass


def main() -> int:
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
    handler = functools.partial(Handler, directory=str(ROOT))
    print(f"serving {ROOT} at http://127.0.0.1:{port}{BASE}  (404.html served for misses)")
    ThreadingHTTPServer(("127.0.0.1", port), handler).serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
