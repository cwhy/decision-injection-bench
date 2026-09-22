import sys
import types
import unittest
from unittest.mock import patch
from decision_injection_bench.laya_backend import LayaBackend, token_audit


class Tokenizer:
    mask_token = "[MASK]"
    mask_token_id = 0

    def __call__(self, text, **kwargs):
        return {"input_ids": text.split()}


class LayaTests(unittest.TestCase):
    def test_detects_every_truncation_stage(self):
        module = types.ModuleType("laya.common")
        module.render_options = lambda q: q["options"]
        module.serialize_state = lambda state: state
        agent = types.SimpleNamespace(
            tok=Tokenizer(),
            cfg={"max_len": 64, "head_max_len": 32},
            _to_internal=lambda q: q,
        )
        request = {
            "state": "base text",
            "question": {
                "t": "choice",
                "ins": "Classify this",
                "options": ["yes", "no"],
            },
        }
        with patch.dict(sys.modules, {"laya.common": module}):
            self.assertFalse(token_audit(agent, request)["truncated"])
            for change in ("state", "instructions", "criteria"):
                q = dict(request["question"])
                r = dict(request, question=q)
                if change == "state":
                    r["state"] = "word " * 100
                if change == "instructions":
                    q["ins"] = "word " * 100
                if change == "criteria":
                    q["options"] = ["word " * 60, "no"]
                self.assertTrue(token_audit(agent, r)["truncated"], change)

    def test_refuses_cpu_before_loading(self):
        torch = types.ModuleType("torch")
        torch.cuda = types.SimpleNamespace(is_available=lambda: False)
        laya = types.ModuleType("laya")
        laya.load = lambda *a, **kw: self.fail("Model must not load")
        with patch.dict(sys.modules, {"torch": torch, "laya": laya}):
            with self.assertRaisesRegex(RuntimeError, "CUDA"):
                LayaBackend()

    def test_passes_only_request_to_model_and_records_audit(self):
        seen = []
        backend = LayaBackend.__new__(LayaBackend)
        backend.variant = "english"

        def predict(state, questions):
            seen.append((state, questions))
            return {
                "answers": {
                    "decision": {
                        "choice": "BLOCK",
                        "probabilities": {"ALLOW": 0.0, "BLOCK": 1.0},
                    }
                }
            }

        backend.agent = types.SimpleNamespace(
            predict=predict, device=types.SimpleNamespace(type="cuda")
        )
        request = {
            "state": {"submitted_content": "sample"},
            "question": {
                "type": "choice",
                "instructions": "fixed",
                "criteria": {"BLOCK": "no", "ALLOW": "yes"},
            },
        }
        with patch(
            "decision_injection_bench.laya_backend.token_audit",
            return_value={"truncated": False},
        ):
            result = backend.classify(request)
        self.assertEqual(seen, [(request["state"], {"decision": request["question"]})])
        self.assertFalse(result["raw"]["token_audit"]["truncated"])


if __name__ == "__main__":
    unittest.main()
