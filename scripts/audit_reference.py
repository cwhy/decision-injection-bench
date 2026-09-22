"""Verify the complete original experiment, including frozen selection provenance."""

import hashlib
import json
from pathlib import Path

from decision_injection_bench.cli import (
    heldout_cases,
    request_for,
    score,
    selected_attacks,
    validate_answer,
)

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "results/2026-09-22"
manifest = json.loads((DATA / "selection-manifest.json").read_text())
assert (
    manifest["selection_sha256"]
    == hashlib.sha256((DATA / "selected-attacks.json").read_bytes()).hexdigest()
)
for name, digest in manifest["sources"].items():
    assert hashlib.sha256((DATA / name).read_bytes()).hexdigest() == digest, name
expected = {
    (item["id"], attack["name"], defense, repeat): request_for(item, attack, defense)
    for item, attack, defense, repeat in heldout_cases(selected_attacks())
}
assert len(expected) == 264
all_heldout = []
for backend in ("jev", "semif", "winnow"):
    for phase, count in [("development", 132), ("refinement", 48), ("heldout", 264)]:
        rows = [
            json.loads(line)
            for line in (DATA / f"{backend}-{phase}.jsonl").read_text().splitlines()
        ]
        assert len(rows) == count
        for row in rows:
            assert row["backend"] == backend and "error" not in row
            validate_answer(row)
        if phase != "heldout":
            continue
        assert min(row["timestamp"] for row in rows) > manifest["frozen_utc"]
        actual = {
            (r["item"]["id"], r["attack"]["name"], r["defense"], r["repeat"]): r[
                "request"
            ]
            for r in rows
        }
        assert len(actual) == len(rows) and actual == expected
        all_heldout.extend(rows)
metrics = score(all_heldout)
reference = json.loads((DATA / "summary.json").read_text())
for backend, defenses in reference["models"].items():
    for defense, original in defenses.items():
        current = metrics[backend + "/" + defense]
        assert current["flips"] == original["flips"]
        assert current["eligible_attacks"] == original["eligible"]
        assert len(current["affected_items"]) == original["affected_items"]
        assert current["clean_errors"] == original["clean_errors"]
        assert current["neutral_errors"] == original["neutral_errors"]
for entry in reference["files"]:
    assert (
        hashlib.sha256((DATA / entry["file"]).read_bytes()).hexdigest()
        == entry["sha256"]
    )
print(
    "Verified 1,332 calls: file hashes, counts, probabilities, frozen selection, identical held-out requests, and reference scores."
)
