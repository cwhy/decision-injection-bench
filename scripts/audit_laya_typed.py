"""Recompute the Laya extension and typed track from archived live evidence."""

import hashlib
import json
import tarfile
import tempfile
from pathlib import Path
from decision_injection_bench.comprehensive.cases import digest
from decision_injection_bench.comprehensive.scoring import score_run
from decision_injection_bench.typed import score, make_plan

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "results/2026-09-22-laya-typed"
manifest = json.loads((DATA / "manifest.json").read_text())
reports = json.loads((DATA / "scores.json").read_text())
fingerprints = {
    digest(json.loads(p.read_text())) for p in DATA.glob("execution-sources-*.json")
}
allowed = {"run.json", "plan.json", "records.jsonl", "complete.json"}
static_reference = json.loads(
    (ROOT / "results/2026-09-22-comprehensive/scores.json").read_text()
)["static-jev"]["plan_sha256"]
total = 0
for name, info in manifest["runs"].items():
    archive = DATA / info["archive"]
    assert hashlib.sha256(archive.read_bytes()).hexdigest() == info["sha256"]
    with tempfile.TemporaryDirectory() as d:
        folder = Path(d)
        with tarfile.open(archive) as t:
            members = t.getmembers()
            assert len({m.name for m in members}) == len(members)
            for m in members:
                assert m.isfile() and m.name in allowed
                (folder / m.name).write_bytes(t.extractfile(m).read())
        meta = json.loads((folder / "run.json").read_text())
        assert meta["runtime"]["implementation_sha256"] in fingerprints
        report = score_run(folder) if info["kind"] == "static" else score(folder)
        assert report["complete"] and report == reports[name], name
        assert report["plan_sha256"] == (
            static_reference if info["kind"] == "static" else make_plan()["sha256"]
        )
        rows = [
            json.loads(line)
            for line in (folder / "records.jsonl").read_text().splitlines()
        ]
        assert len(rows) == info["calls"]
        if name.endswith(("laya", "multilingual")):
            assert all(not r["answer"]["raw"]["token_audit"]["truncated"] for r in rows)
        total += len(rows)
assert total == manifest["total_defender_calls"] == 5100
print(
    "Verified 5,100 live calls, lossless Laya inputs, identical plans, execution-source hashes and all scores."
)
