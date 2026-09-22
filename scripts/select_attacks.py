"""Freeze a union of model-targeted attacks before any held-out requests."""

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from decision_injection_bench.suite import DEV, HOLDOUT, STRICT

p = argparse.ArgumentParser()
p.add_argument("--data", type=Path, required=True)
args = p.parse_args()
DATA = args.data
selected = {}
origins = {}
sources = {}
for backend in ("jev", "semif", "winnow"):
    rows = []
    for phase, expected in [("development", 132), ("refinement", 48)]:
        path = DATA / f"{backend}-{phase}.jsonl"
        current = [json.loads(line) for line in path.read_text().splitlines()]
        assert len(current) == expected and all("choice" in r for r in current), (
            path,
            len(current),
        )
        rows += current
        sources[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
    for item in DEV:
        key = item["task"] + "-" + item["expected"]
        target = "ALLOW" if item["expected"] == "BLOCK" else "BLOCK"
        ranked = sorted(
            [
                r
                for r in rows
                if r["item"]["id"] == item["id"]
                and r["attack"]["name"] not in ("clean", "neutral")
            ],
            key=lambda r: r["probabilities"][target],
            reverse=True,
        )

        # Keep one scope/policy reinterpretation and one direct label attack so
        # an ambiguous scope change cannot crowd out the direct-manipulation test.
        def is_scope(r):
            return r["attack"]["family"] in (
                "scope-reframing",
                "policy-reinterpretation",
                "policy",
            ) or r["attack"]["name"].startswith(("policy-", "scope-"))

        top = []
        for scope in (True, False):
            pool = [r for r in ranked if is_scope(r) == scope]
            if pool:
                top.append(pool[0])
        for r in top:
            spec = r["attack"]
            pool = selected.setdefault(key, [])
            if not any(
                (x["prefix"], x["suffix"]) == (spec["prefix"], spec["suffix"])
                for x in pool
            ):
                pool.append(spec)
            origins.setdefault(key, []).append(
                dict(
                    backend=backend,
                    name=spec["name"],
                    target_probability=r["probabilities"][target],
                )
            )
path = DATA / "selected-attacks.json"
with path.open("x") as f:
    json.dump(selected, f, indent=2, ensure_ascii=False)
meta = dict(
    frozen_utc=datetime.now(timezone.utc).isoformat(),
    selection_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
    sources=sources,
    origins=origins,
    heldout=HOLDOUT,
    strict_addition=STRICT,
    rule="Best scope/policy reinterpretation and best direct-label payload per development item and backend by target probability; union sent unchanged to every backend. Ties follow query order. No held-out feedback used.",
)
(DATA / "selection-manifest.json").write_text(
    json.dumps(meta, indent=2, ensure_ascii=False)
)
print({k: [s["name"] for s in v] for k, v in selected.items()})
print(
    "Held-out calls per model:",
    sum((2 + len(selected[i["task"] + "-" + i["expected"]])) * 6 for i in HOLDOUT),
)
