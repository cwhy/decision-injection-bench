"""Verify archived v2 evidence and reproduce scores and frozen selection offline."""

import hashlib
import json
import tarfile
import tempfile
from pathlib import Path

from decision_injection_bench.comprehensive.cases import corpus, selection_load
from decision_injection_bench.comprehensive.scoring import score_run, score_search
from decision_injection_bench.comprehensive.search import freeze

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "results/2026-09-22-comprehensive"
manifest = json.loads((DATA / "manifest.json").read_text())
reports = json.loads((DATA / "scores.json").read_text())
allowed = {"run.json", "search.json", "plan.json", "records.jsonl", "complete.json"}
total = 0
with tempfile.TemporaryDirectory() as tmp:
    workspace = Path(tmp)
    for name, info in manifest["runs"].items():
        archive = DATA / info["archive"]
        assert hashlib.sha256(archive.read_bytes()).hexdigest() == info["sha256"], name
        folder = workspace / name
        folder.mkdir()
        with tarfile.open(archive, "r:gz") as file:
            members = file.getmembers()
            assert len({m.name for m in members}) == len(members)
            for member in members:
                assert member.isfile() and member.name in allowed, member.name
                (folder / member.name).write_bytes(file.extractfile(member).read())
        search = info["kind"] == "search"
        report = score_search(folder) if search else score_run(folder)
        assert report["complete"] and report == reports[name], name
        count = (
            report["defender_calls"]
            if search
            else report["overall"]["successful_calls"]
        )
        assert count == info["defender_calls"], name
        total += count
    for prefix in ("preflight", "static", "transfer"):
        hashes = {
            reports[f"{prefix}-{b}"]["plan_sha256"] for b in ("jev", "semif", "winnow")
        }
        assert len(hashes) == 1, prefix
    saved = selection_load(DATA / "selected.json", corpus())
    # Use the original source order; ordering contributes to the frozen artifact.
    search_dirs = [workspace / name for name in manifest["selection_sources"]]
    replay = freeze(corpus(), search_dirs, workspace / "reselected.json", top_k=1)
    for key in ("sources", "attacks", "origins", "rule", "corpus_sha256"):
        assert replay[key] == saved[key], key
    for backend in ("jev", "semif", "winnow"):
        folder = workspace / f"transfer-{backend}"
        plan = json.loads((folder / "plan.json").read_text())
        assert plan["selection_sha256"] == saved["sha256"]
        records = [
            json.loads(line)
            for line in (folder / "records.jsonl").read_text().splitlines()
        ]
        assert min(r["timestamp"] for r in records) > saved["frozen_utc"]
print(
    f"Verified {len(reports)} archived runs and {total} defender calls; scores and selection reproduced."
)
