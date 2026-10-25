#!/usr/bin/env python3
"""Local review viewer for the enrichment outcomes. Standard library only, bound to 127.0.0.1, and
never reads the API key.

    python3 viewer/serve.py                 # http://127.0.0.1:8765
    python3 viewer/serve.py --port 9000 --rater gf

Ratings append to ratings/ratings.csv; the latest row per record and field wins.
"""

from __future__ import annotations

import argparse
import json
import sys
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from glm_enrich import COHORTS, REPO  # noqa: E402
from glm_enrich.review import append_rating, records  # noqa: E402

INDEX = Path(__file__).resolve().parent / "index.html"


def make_handler(port: int, rater: str, ratings_path: Path):
    allowed_hosts = {f"127.0.0.1:{port}", f"localhost:{port}"}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):  # quiet
            pass

        def _send(self, status: int, body: bytes, ctype: str) -> None:
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _json(self, status: int, payload) -> None:
            self._send(status, json.dumps(payload).encode("utf-8"), "application/json")

        def _host_ok(self) -> bool:
            # Refuse anything not addressed to this machine by name (DNS-rebinding guard).
            if self.headers.get("Host") not in allowed_hosts:
                self._json(HTTPStatus.FORBIDDEN, {"error": "bad host"})
                return False
            return True

        def do_GET(self):
            if not self._host_ok():
                return
            url = urlparse(self.path)
            if url.path in ("/", "/index.html"):
                self._send(HTTPStatus.OK, INDEX.read_bytes(), "text/html; charset=utf-8")
            elif url.path == "/api/config":
                cohorts = [{"name": name, "available": (REPO / spec["input"]).exists(),
                            "has_reference": "reference" in spec} for name, spec in COHORTS.items()]
                self._json(HTTPStatus.OK, {"rater": rater, "cohorts": cohorts})
            elif url.path == "/api/records":
                cohort = (parse_qs(url.query).get("cohort") or [""])[0]
                if cohort not in COHORTS:
                    self._json(HTTPStatus.BAD_REQUEST, {"error": "unknown cohort"})
                elif not (REPO / COHORTS[cohort]["input"]).exists():
                    self._json(HTTPStatus.OK, {"records": [], "missing": COHORTS[cohort]["input"]})
                else:
                    self._json(HTTPStatus.OK, {"records": records(cohort, ratings_path)})
            else:
                self._json(HTTPStatus.NOT_FOUND, {"error": "not found"})

        def do_POST(self):
            if not self._host_ok():
                return
            if urlparse(self.path).path != "/api/rating":
                self._json(HTTPStatus.NOT_FOUND, {"error": "not found"})
                return
            # application/json only: a cross-site form cannot send it without a CORS preflight,
            # which this server never answers.
            if (self.headers.get("Content-Type") or "").split(";")[0].strip() != "application/json":
                self._json(HTTPStatus.UNSUPPORTED_MEDIA_TYPE, {"error": "json only"})
                return
            length = min(int(self.headers.get("Content-Length") or 0), 64_000)
            try:
                payload = json.loads(self.rfile.read(length) or b"{}")
                row = append_rating({**payload, "rater": rater}, ratings_path)
            except (ValueError, json.JSONDecodeError) as exc:
                self._json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
                return
            self._json(HTTPStatus.OK, {"saved": row})

    return Handler


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--rater", default="rater1", help="Recorded with every rating.")
    args = parser.parse_args()
    from glm_enrich.review import RATINGS
    server = ThreadingHTTPServer(("127.0.0.1", args.port), make_handler(args.port, args.rater, RATINGS))
    print(f"viewer on http://127.0.0.1:{args.port}  (ratings -> {RATINGS.relative_to(REPO)}; Ctrl-C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
