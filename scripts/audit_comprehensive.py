"""Offline fixture and planning audit; does not query any model."""

from collections import Counter
from decision_injection_bench.comprehensive.cases import (
    corpus,
    digest,
    make_plan,
    static_attacks,
    verify_plan,
)

data = corpus()
assert len(data["items"]) == 72
assert len({i["group"] for i in data["items"]}) == 24
assert Counter(i["split"] for i in data["items"]) == {
    "development": 24,
    "validation": 24,
    "test": 24,
}
assert Counter(i["language"] for i in data["items"]) == {"en": 24, "es": 24, "zh": 24}
assert all(len(static_attacks(i)) == 44 for i in data["items"])
plan = make_plan(data, defenses=["strict"], orders=["normal"], repeats=1)
verify_plan(plan)
assert len(plan["cases"]) == 2160
assert sum(e["kind"] == "attack" for e in plan["cases"]) == 1056
assert sum(e["kind"] == "length-control" for e in plan["cases"]) == 1056
print(
    f"Comprehensive fixtures verified: 72 texts, 24 groups, 44 attacks/item; full default plan = {len(plan['cases']) * 12:,} calls. No model calls. Corpus SHA256: {digest(data)}"
)
