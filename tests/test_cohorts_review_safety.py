import csv
import json
import random
import threading
import urllib.error
import urllib.request
from collections import Counter
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest

import check_no_secrets
import serve
from glm_enrich import review
from glm_enrich.cohorts import allocate, select_enriched, select_unenriched, stratum, venue

ROOT = Path(__file__).resolve().parents[1]


def synthetic(n=4000, seed=1):
    rng = random.Random(seed)
    journals = [f"Journal {i}" for i in range(300)] + ["Big Journal"] * 300
    rows = []
    for i in range(n):
        preprint = rng.random() < 0.15
        rows.append({"record_id": f"r{i:05d}", "year": rng.choice([2008, 2014, 2017, 2021, 2023, 2024, 2025, 2026, None]),
                     "epmc_source": "PPR" if preprint else "MED",
                     "journal": "" if preprint else rng.choice(journals),
                     "preprint_server": rng.choice(["bioRxiv", "medRxiv", "arXiv", ""]) if preprint else ""})
    return rows


def test_allocate_sums_and_respects_floor_and_availability():
    alloc = allocate({"a": 1000, "b": 50, "c": 5, "d": 0}, 300, 10)
    assert sum(alloc.values()) == 300
    assert alloc["c"] == 5 and alloc["d"] == 0 and alloc["b"] >= 10


def test_select_unenriched_is_diverse_balanced_and_deterministic():
    rows = synthetic()
    picked = select_unenriched(rows, 500, 10, 2, seed=7)
    assert len(picked) == 500 and len({r["record_id"] for r in picked}) == 500
    assert Counter(r["wave"] for r in picked) == {1: 250, 2: 250}
    per_venue = Counter(venue(r) for r in picked if venue(r))
    assert max(per_venue.values()) <= 2
    available = Counter(stratum(r) for r in rows)
    got = Counter(r["stratum"] for r in picked)
    for cell, n in available.items():
        assert got[cell] >= min(n, 10) - 2, cell  # floor, less what the venue cap can take away
        waves = Counter(r["wave"] for r in picked if r["stratum"] == cell)
        assert abs(waves[1] - waves[2]) <= 1
    assert [r["record_id"] for r in picked] == [r["record_id"] for r in select_unenriched(rows, 500, 10, 2, seed=7)]


def test_select_enriched_round_robins_domains():
    rng = random.Random(3)
    domains = [f"D{i}" for i in range(13)]
    weights = [60, 40, 30, 20, 12, 10, 8, 6, 5, 4, 2, 2, 1]
    rows = []
    for d, w in zip(domains, weights):
        for k in range(w):
            rows.append({"record_id": f"{d}-{k}", "domain_tier1": d, "journal": f"J{rng.randint(0, 150)}"})
    picked = select_enriched(rows, 100, 3, seed=5)
    assert len(picked) == 100
    counts = Counter(r["stratum"] for r in picked)
    assert set(counts) == set(domains)
    for d, w in zip(domains, weights):
        assert counts[d] >= min(w, 5)  # every small domain is taken whole before big ones fill up
    assert max(Counter(venue(r) for r in picked).values()) <= 3


def test_ratings_append_and_latest_wins(tmp_path):
    path = tmp_path / "ratings.csv"
    review.append_rating({"record_id": "x", "field": "model_type", "verdict": "wrong"}, path)
    review.append_rating({"record_id": "x", "field": "model_type", "verdict": "correct"}, path)
    assert review.latest_ratings(path)[("x", "model_type")]["verdict"] == "correct"
    assert len(list(csv.DictReader(path.open()))) == 2
    with pytest.raises(ValueError):
        review.append_rating({"record_id": "x", "field": "title", "verdict": "correct"}, path)
    with pytest.raises(ValueError):
        review.append_rating({"record_id": "x", "field": "model_type", "verdict": "great"}, path)


def write(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def test_records_join_events_reference_and_ratings(tmp_path, monkeypatch):
    monkeypatch.setattr(review, "REPO", tmp_path)
    write(tmp_path / "data/input_enriched_100.csv",
          [{"record_id": "x", "title": "T", "abstract": "A", "journal": "J", "year": "2025"},
           {"record_id": "y", "title": "T2", "abstract": "A2", "journal": "J", "year": "2025"}])
    lists = lambda **kw: {f: json.dumps(kw.get(f, [])) for f in review.FIELDS}  # noqa: E731
    write(tmp_path / "runs/events_enriched100.csv",
          [{"record_id": "x", **lists(domain_tier1=["Biology", "Medicine"], model_type=["CNN"]), "rationale": "r",
            "vocab_violations": "[]", "parse_status": "ok", "finish_reason": "stop", "output_tokens": "9",
            "batch_id": "b", "timestamp": "2026-10-25T00:00:00"}])
    write(tmp_path / "data/reference_deepseek_100.csv",
          [{"record_id": "x", **lists(domain_tier1=["biology"], model_type=["U-Net"]), "rationale": "d",
            "vocab_violations": "[]", "model_id": "deepseek-v4-flash", "batch_id": "e"}])
    ratings = tmp_path / "ratings.csv"
    review.append_rating({"record_id": "x", "field": "model_type", "verdict": "partly", "preference": "deepseek"}, ratings)
    recs = {r["record_id"]: r for r in review.records("enriched100", ratings)}
    fields = {f["field"]: f for f in recs["x"]["fields"]}
    assert fields["domain_tier1"]["same"] is True  # first tier-1 term only, case-folded
    assert fields["model_type"]["same"] is False and fields["model_type"]["verdict"] == "partly"
    assert fields["model_type"]["preference"] == "deepseek"
    assert recs["y"]["glm"] is None and all(f["glm"] is None for f in recs["y"]["fields"])


def test_viewer_server_guards_and_saves(tmp_path):
    ratings = tmp_path / "ratings.csv"
    server = ThreadingHTTPServer(("127.0.0.1", 0), None)
    port = server.server_address[1]
    server.RequestHandlerClass = serve.make_handler(port, "tester", ratings)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{port}"

    def post(body, ctype="application/json", host=None):
        req = urllib.request.Request(f"{base}/api/rating", data=body, method="POST", headers={"Content-Type": ctype})
        if host:
            req.add_unredirected_header("Host", host)
        try:
            return urllib.request.urlopen(req).status
        except urllib.error.HTTPError as e:
            return e.code

    try:
        assert json.load(urllib.request.urlopen(f"{base}/api/config"))["rater"] == "tester"
        assert urllib.request.urlopen(f"{base}/").status == 200
        good = json.dumps({"record_id": "x", "field": "model_family", "verdict": "correct"}).encode()
        assert post(good, ctype="application/x-www-form-urlencoded") == 415
        assert post(good, host="evil.example:80") == 403
        assert post(good) == 200
        assert review.latest_ratings(ratings)[("x", "model_family")]["rater"] == "tester"
    finally:
        server.shutdown()


FORBIDDEN = ["insert_one", "insert_many", "update_one", "update_many", "replace_one", "ReplaceOne", "UpdateOne",
             "delete_one", "delete_many", "bulk_write", "find_one_and_", "drop(", "drop_index", "create_index",
             "$out", "$merge", "SafeWriter", "moros_write", "load_enrichment", "load_documents", "load_fields"]


def test_nothing_here_can_write_to_moros():
    offenders = []
    for path in ROOT.rglob("*.py"):
        if path.name == Path(__file__).name or "__pycache__" in path.parts:
            continue
        text = path.read_text(encoding="utf-8")
        offenders += [f"{path.relative_to(ROOT)}: {token}" for token in FORBIDDEN if token in text]
    assert offenders == []


def test_secret_scanner_catches_and_passes():
    bad = ("key " + "a" * 32 + "." + "B" * 16 + "\n" + "mongodb" + "://x:27017\n" + ".".join(["10", "1", "2", "3"]) + "\n"
           + "/" + "home/someone/x\n" + "ZAI_API_KEY=" + "realvalue123\n")
    labels = {f.split(": ", 1)[1] for f in check_no_secrets.scan("f", bad)}
    assert {"Z.ai API key", "database URI", "private IPv4 address", "home-directory path",
            "filled-in ZAI_API_KEY"} <= labels
    key_var = "ZAI_API_KEY" + "="
    assert check_no_secrets.scan("f", f"{key_var}\n{key_var}<paste key here>\nBearer {{self._api_key}}\n") == []
    assert check_no_secrets.scan(".env.example", (ROOT / ".env.example").read_text()) == []
