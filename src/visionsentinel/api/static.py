"""Serve the statically exported dashboard with a per-page Content-Security-Policy.

The Next.js static export contains a few inline bootstrap scripts. Instead of allowing ``'unsafe-inline'``
for scripts, every HTML page is scanned once at start-up and the SHA-256 of each inline script is placed in
that page's CSP. Paths are confined to the export directory; unknown paths fall back to ``404.html``.
"""

from __future__ import annotations

import base64
import hashlib
import mimetypes
import re
from pathlib import Path

from starlette.responses import FileResponse, Response

_INLINE_SCRIPT = re.compile(rb"<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>", re.S | re.I)
BASE_CSP = ("default-src 'self'; img-src 'self' data: blob:; font-src 'self'; style-src 'self' 'unsafe-inline'; "
            "connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'; object-src 'none'")


class DashboardFiles:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.csp: dict[Path, str] = {}
        for page in self.root.rglob("*.html"):
            hashes = sorted({"'sha256-" + base64.b64encode(hashlib.sha256(m).digest()).decode() + "'"
                             for m in _INLINE_SCRIPT.findall(page.read_bytes())})
            self.csp[page.resolve()] = f"script-src 'self' {' '.join(hashes)}; {BASE_CSP}"

    def _resolve(self, path: str) -> Path | None:
        rel = path.lstrip("/")
        if "\x00" in rel or ".." in Path(rel).parts:
            return None
        candidates = [self.root / rel, self.root / rel / "index.html", self.root / f"{rel}.html"] if rel else \
            [self.root / "index.html"]
        for c in candidates:
            try:
                r = c.resolve()
            except OSError:
                continue
            if r.is_file() and (r == self.root or self.root in r.parents):
                return r
        return None

    def response(self, path: str) -> Response:
        target = self._resolve(path)
        status = 200
        if target is None:
            target = self.root / "404.html"
            status = 404
            if not target.is_file():
                return Response("not found", status_code=404, media_type="text/plain")
        media = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        headers = {"Cache-Control": "no-cache" if target.suffix == ".html" else "public, max-age=31536000, immutable"}
        if target.suffix == ".html":
            headers["Content-Security-Policy"] = self.csp.get(target, f"script-src 'self'; {BASE_CSP}")
        return FileResponse(target, status_code=status, media_type=media, headers=headers)
