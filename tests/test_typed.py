import copy
import json
import tempfile
import unittest
import sys
import types
from pathlib import Path
from unittest.mock import patch
from decision_injection_bench import typed


class TypedTests(unittest.TestCase):
    def test_plan_deterministic_and_no_negative_detector_attacks(self):
        p = typed.make_plan()
        typed.verify_plan(p)
        self.assertEqual(p, typed.make_plan())
        self.assertEqual(len(p["cases"]), 260)
        for c in p["cases"]:
            if c["item"]["task"] == "injection-detection" and c["kind"] == "attack":
                self.assertTrue(c["item"]["expected"])
        bad = copy.deepcopy(p)
        bad["cases"][0]["request"]["state"]["submitted_content"] = "changed"
        with self.assertRaises(ValueError):
            typed.verify_plan(bad)

    def test_no_loading_over_budget(self):
        with (
            tempfile.TemporaryDirectory() as d,
            patch.object(typed, "Defender") as factory,
        ):
            with self.assertRaises(ValueError):
                typed.run(typed.make_plan(), Path(d) / "run", "jev", 1)
            factory.assert_not_called()

    def test_typed_scoring_and_integrity(self):
        plan = typed.make_plan()
        by_request = {
            json.dumps(c["request"], sort_keys=True): c for c in plan["cases"]
        }

        def stub(request):
            c = by_request[json.dumps(request, sort_keys=True)]
            item = c["item"]
            kind = item["question"]["type"]
            value = item["target"] if c["kind"] == "attack" else item["expected"]
            if kind == "choice":
                return dict(
                    choice=value,
                    probabilities={
                        k: float(k == value) for k in item["question"]["criteria"]
                    },
                )
            return {kind: float(value)}

        with tempfile.TemporaryDirectory() as d:
            folder = Path(d) / "run"
            typed.run(plan, folder, "fixture", 260, defender=stub)
            r = typed.score(folder)
            self.assertTrue(r["complete"])
            self.assertEqual(sum(m["flips"] for m in r["tasks"].values()), 108)
            self.assertEqual(r["tasks"]["injection-detection"]["clean_calls"], 8)
            records = folder / "records.jsonl"
            records.write_text(
                records.read_text() + records.read_text().splitlines()[0] + "\n"
            )
            with self.assertRaises(ValueError):
                typed.score(folder)

    def test_jev_uses_native_score_and_noul(self):
        for kind, value in (("score", 2.75), ("noul", 0.82)):
            captured = {}
            module = types.ModuleType("typesafe_sdk")

            class Question:
                def __init__(self, **kwargs):
                    captured.update(kwargs)

            setattr(module, "Score" if kind == "score" else "Noul", Question)

            def call(state, questions):
                captured["state"] = state
                return types.SimpleNamespace(
                    answers={"decision": types.SimpleNamespace(**{kind: value})},
                    model="fixture",
                )

            native = types.SimpleNamespace(
                client=types.SimpleNamespace(system_one=call)
            )
            item = next(
                c["item"]
                for c in typed.make_plan()["cases"]
                if c["item"]["question"]["type"] == kind
            )
            request = {
                "state": {"submitted_content": item["content"]},
                "question": item["question"],
            }
            with (
                patch.object(typed, "Backend", return_value=native),
                patch.dict(sys.modules, {"typesafe_sdk": module}),
            ):
                answer = typed.Defender("jev")(request)
            self.assertEqual(answer[kind], value)
            self.assertEqual(captured["criteria"], request["question"]["criteria"])
            self.assertNotIn("expected", captured)

    def test_score_and_noul_boundaries(self):
        p = typed.make_plan()
        item = next(
            c["item"] for c in p["cases"] if c["item"]["question"]["type"] == "score"
        )
        self.assertTrue(typed.correct(item, {"score": item["expected"] + 0.5}, p))
        with self.assertRaises(ValueError):
            typed.validate({"noul": float("nan")}, {"type": "noul"})
        with self.assertRaises(ValueError):
            typed.validate({"score": 5}, {"type": "score", "criteria": ["a", "b"]})


if __name__ == "__main__":
    unittest.main()
