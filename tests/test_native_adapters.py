"""Verify adapter serialization offline; never load models or make network calls."""

import json
import sys
import types
import unittest
from unittest.mock import patch
from decision_injection_bench.suite import Backend

REQUEST = {
    "state": {"submitted_content": "synthetic fixture"},
    "question": {
        "type": "choice",
        "instructions": "Fixed trusted criterion",
        "criteria": {"BLOCK": "Blocked", "ALLOW": "Allowed"},
    },
}


class NativeAdapterTests(unittest.TestCase):
    def test_jev_preserves_reversed_criteria(self):
        captured = {}

        class Choice:
            def __init__(self, **kwargs):
                captured.update(kwargs)

        module = types.ModuleType("typesafe_sdk")
        module.Choice = Choice

        class Client:
            def system_one(self, state, questions):
                captured["state"] = state
                return types.SimpleNamespace(
                    answers={
                        "decision": types.SimpleNamespace(
                            choice="BLOCK",
                            probabilities={"BLOCK": 1.0, "ALLOW": 0.0},
                            confidence=1,
                        )
                    },
                    model="fixture-model",
                )

        backend = Backend.__new__(Backend)
        backend.name = "jev"
        backend.client = Client()
        with patch.dict(sys.modules, {"typesafe_sdk": module}):
            result = backend.classify(REQUEST)
        self.assertEqual(list(captured["criteria"]), ["BLOCK", "ALLOW"])
        self.assertEqual(captured["instructions"], REQUEST["question"]["instructions"])
        self.assertEqual(result["resolved_model"], "fixture-model")

    def test_winnow_preserves_request(self):
        backend = Backend.__new__(Backend)
        backend.name = "winnow"
        backend.endpoint = "http://localhost:8091"
        seen = []

        class Response:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                pass

            def read(self):
                return json.dumps(
                    {
                        "answers": {
                            "decision": {
                                "choice": "BLOCK",
                                "probabilities": {"BLOCK": 1.0, "ALLOW": 0.0},
                            }
                        }
                    }
                ).encode()

        def fake_open(request, timeout):
            seen.append(json.loads(request.data))
            return Response()

        with patch("urllib.request.urlopen", side_effect=fake_open):
            backend.classify(REQUEST)
        self.assertEqual(seen[0]["questions"]["decision"], REQUEST["question"])
        self.assertEqual(
            list(seen[0]["questions"]["decision"]["criteria"]), ["BLOCK", "ALLOW"]
        )
        self.assertFalse(seen[0]["winnow"]["reuse_prefix"])

    def test_semif_preserves_option_order(self):
        seen = []
        module = types.ModuleType("semif_phase1.direct")

        def fake_score(model, tokenizer, row, metadata, max_tokens):
            seen.append(row)
            return {"option_ids": ["BLOCK", "ALLOW"], "probabilities": [1.0, 0.0]}

        module.score = fake_score
        backend = Backend.__new__(Backend)
        backend.name = "semif"
        backend.loaded = (None, None, {})
        with patch.dict(sys.modules, {"semif_phase1.direct": module}):
            backend.classify(REQUEST)
        self.assertEqual([o["id"] for o in seen[0]["options"]], ["BLOCK", "ALLOW"])
        self.assertNotIn("expected", seen[0])


if __name__ == "__main__":
    unittest.main()
