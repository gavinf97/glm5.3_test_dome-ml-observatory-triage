#!/usr/bin/env python3
"""Human rating app for the tag validation. Standard library only, bound to 127.0.0.1.

    python3 validation/rate_app.py --rater gf                              # rate the 150 human papers
    python3 validation/rate_app.py --adjudicate --rater gf --judge opus-5-5  # settle disagreements

Then open http://127.0.0.1:8766. Every click saves straight away to validation/ratings/<rater>.csv
(append-only; the latest row per paper and unit counts). Adjudication saves to ratings/consensus.csv.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (CONFIG_PATH, ERROR_CODES, RUBRIC_PATH, UNIT_FIELDS, UNIT_LABELS, VERDICTS,  # noqa: E402
                    append_rating, latest_ratings, load_config, load_items, load_sample, needs_adjudication,
                    tagger_prompt)

PAGE = Path(__file__).resolve().parent / "rate.html"
CONSENSUS = "consensus"
HERE = Path(__file__).resolve().parent
CLOSED_FIELDS = ("domain_tier1", "domain_tier2", "domain_tier3", "model_use", "learning_paradigm", "model_family")


def closed_vocab() -> dict[str, tuple[int, set[str]]]:
    """Closed vocabularies and caps, read from the frozen e2 tagger prompt (the same text both raters see)."""
    text = tagger_prompt()
    out = {}
    for field in CLOSED_FIELDS:
        m = re.search(field + r" \(choose at most (\d+)[^\n]*\n(.*?)\n---", text, re.S)
        if not m:
            raise SystemExit(f"could not read the {field} vocabulary from the tagger prompt")
        body = m.group(2).strip()
        if field.startswith("domain_"):  # comma-separated EDAM labels; some labels contain ", <lowercase>"
            terms = re.split(r", (?=[A-Z])", body)
        else:
            terms = re.findall(r"^- ([^:\n]+?)(?::|$)", body, re.M)
        out[field] = (int(m.group(1)), {t.strip() for t in terms})
    return out


def canonical_model_types() -> dict[str, dict]:
    """Canonical model_type spellings with their aliases and family, from the tagger prompt."""
    text = tagger_prompt()
    block = text.split("Canonical model-type spellings", 1)[1].split("MODEL_TYPE RULES", 1)[0]
    out = {}
    for line in block.splitlines():
        m = re.match(r"^- (?P<name>.+?)(?: \(aliases: (?P<al>.*?)\))?(?: -> family: (?P<fam>.*))?$", line.strip())
        if m:
            out[m.group("name").lower()] = {"name": m.group("name"), "aliases": m.group("al") or "",
                                            "family": m.group("fam") or ""}
    return out


def vocab_check(item: dict, vocab: dict, canon: dict) -> dict:
    """Per unit: off-vocabulary terms and cap breaches for closed fields; canonical/alias info for model_type."""
    out = {}
    for unit, fields in UNIT_FIELDS.items():
        if unit == "model_type":
            out[unit] = {"closed": False,
                         "canonical": {t: canon[t.lower()] for t in item["tags"]["model_type"] if t.lower() in canon}}
            continue
        off, over = [], []
        for f in fields:
            cap, terms = vocab[f]
            values = item["tags"][f]
            off += [t for t in values if t not in terms]
            if len(values) > cap:
                over.append(f"{f}: {len(values)} terms, cap {cap}")
        out[unit] = {"closed": True, "off": off, "over_cap": over}
    return out


def load_recheck(rater: str, own: dict) -> dict:
    """Units flagged for re-rating (validation/recheck_<rater>.json). A flag clears once the rater saves a
    new rating for that unit after the flag was raised. Never touches the ratings CSV."""
    path = HERE / f"recheck_{rater}.json"
    if not path.exists():
        return {}
    active: dict[str, dict] = {}
    for flag in json.loads(path.read_text(encoding="utf-8")):
        latest = own.get((flag["record_id"], flag["unit"]), {}).get("timestamp", "")
        if latest <= flag["flagged_at"]:
            active.setdefault(flag["record_id"], {})[flag["unit"]] = flag["reason"]
    return active


def build_state(config: dict, rater: str, adjudicate: bool, judge: str | None) -> dict:
    rdir = config["_ratings_dir"]
    items = [it for it in load_items(config, load_sample(config["_sample_path"])) if it["human"]]
    own = latest_ratings(CONSENSUS if adjudicate else rater, rdir)
    vocab, canon = closed_vocab(), canonical_model_types()
    state = {"rater": rater, "mode": "adjudicate" if adjudicate else "rate",
             "units": [{"key": u, "label": UNIT_LABELS[u], "fields": list(f)} for u, f in UNIT_FIELDS.items()],
             "verdicts": list(VERDICTS), "error_codes": ERROR_CODES, "items": [], "ratings": {},
             "recheck": {} if adjudicate else load_recheck(rater, own)}
    human = latest_ratings(rater, rdir) if adjudicate else {}
    judged = latest_ratings(judge, rdir) if adjudicate and judge else {}
    for it in items:
        rid = it["record_id"]
        entry = dict(it)
        entry["vocab"] = vocab_check(it, vocab, canon)
        if adjudicate:
            pairs = {}
            for u in UNIT_FIELDS:
                h, j = human.get((rid, u), {}), judged.get((rid, u), {})
                if needs_adjudication(h.get("verdict", ""), j.get("verdict", "")):
                    pairs[u] = {"human": {k: h.get(k, "") for k in ("verdict", "error_codes", "note")},
                                "judge": {k: j.get(k, "") for k in ("verdict", "error_codes", "note")}}
            if not pairs:
                continue
            entry["adjudicate"] = pairs
        state["items"].append(entry)
        state["ratings"][rid] = {u: {k: r.get(k, "") for k in ("verdict", "error_codes", "note")}
                                 for (r_id, u), r in own.items() if r_id == rid}
    return state


def make_handler(port: int, config: dict, rater: str, adjudicate: bool, judge: str | None):
    allowed_hosts = {f"127.0.0.1:{port}", f"localhost:{port}"}
    save_as = CONSENSUS if adjudicate else rater
    save_type = "consensus" if adjudicate else "human"

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            pass

        def _send(self, status, body: bytes, ctype: str):
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _json(self, status, payload):
            self._send(status, json.dumps(payload).encode("utf-8"), "application/json")

        def _host_ok(self) -> bool:
            if self.headers.get("Host") not in allowed_hosts:  # DNS-rebinding guard
                self._json(HTTPStatus.FORBIDDEN, {"error": "bad host"})
                return False
            return True

        def do_GET(self):
            if not self._host_ok():
                return
            path = urlparse(self.path).path
            if path in ("/", "/index.html"):
                self._send(HTTPStatus.OK, PAGE.read_bytes(), "text/html; charset=utf-8")
            elif path == "/api/state":
                self._json(HTTPStatus.OK, build_state(config, rater, adjudicate, judge))
            elif path == "/rubric":
                self._send(HTTPStatus.OK, RUBRIC_PATH.read_bytes(), "text/plain; charset=utf-8")
            elif path == "/tagger-prompt":
                self._send(HTTPStatus.OK, tagger_prompt().encode("utf-8"), "text/plain; charset=utf-8")
            else:
                self._json(HTTPStatus.NOT_FOUND, {"error": "not found"})

        def do_POST(self):
            if not self._host_ok():
                return
            if urlparse(self.path).path != "/api/rating":
                self._json(HTTPStatus.NOT_FOUND, {"error": "not found"})
                return
            if (self.headers.get("Content-Type") or "").split(";")[0].strip() != "application/json":
                self._json(HTTPStatus.UNSUPPORTED_MEDIA_TYPE, {"error": "json only"})
                return
            length = min(int(self.headers.get("Content-Length") or 0), 64_000)
            try:
                p = json.loads(self.rfile.read(length) or b"{}")
                row = append_rating(save_as, save_type, p.get("record_id", ""), p.get("unit", ""),
                                    p.get("verdict", ""), p.get("error_codes") or [], p.get("note", ""),
                                    ratings_dir=config["_ratings_dir"])
            except (ValueError, json.JSONDecodeError) as exc:
                self._json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
                return
            self._json(HTTPStatus.OK, {"saved": row})

    return Handler


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--rater", required=True, help="Your rater id, e.g. gf (letters, digits, - _ .).")
    parser.add_argument("--adjudicate", action="store_true", help="Settle human/judge disagreements.")
    parser.add_argument("--judge", default=None, help="Judge rater id for --adjudicate (default from config).")
    parser.add_argument("--config", type=Path, default=CONFIG_PATH)
    parser.add_argument("--port", type=int, default=8766)
    args = parser.parse_args()
    config = load_config(args.config)
    judge = args.judge or config["judge_rater_id"]
    if args.rater in (CONSENSUS, judge):
        print(f"Pick a personal rater id, not {args.rater!r}.")
        return 1
    state = build_state(config, args.rater, args.adjudicate, judge)  # fail early on a bad sample/config
    server = ThreadingHTTPServer(("127.0.0.1", args.port),
                                 make_handler(args.port, config, args.rater, args.adjudicate, judge))
    what = (f"adjudicating {len(state['items'])} papers with disagreements ({args.rater} vs {judge}) -> consensus"
            if args.adjudicate else f"rating {len(state['items'])} papers as {args.rater}")
    print(f"{what}\nopen http://127.0.0.1:{args.port}   (Ctrl-C to stop; every click is saved)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
