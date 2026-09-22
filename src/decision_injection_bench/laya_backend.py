"""Pinned Laya integration, with explicit CUDA and lossless token-budget checks."""

import os
import hashlib
from .comprehensive.cases import digest
from pathlib import Path

MODEL_REVISION = "1c5edc17a7acd8701df6fc341c0d179f1c62c982"
CODE_REVISION = "573e5b62696ba441230cd6be71d593331b5d23af"

SOURCE_SHA256 = "febfbf20bd5f915fe769eb17896c81beb2326069ded64fb1b75d12fda8ca95b3"
WEIGHT_SHA256 = {
    "english": "891102d372688fc2a094dac56a384bc537b87c63f21f9f3dac0be2b7cbc8d86c",
    "multilingual": "9d628fd971b700382ac6f65920a86f149777b2e748e0c955fb3b19695aa8f204",
}


def verify_pin(laya, path, variant):
    source = Path(laya.__file__).parent
    if (
        digest({p.name: p.read_text() for p in sorted(source.glob("*.py"))})
        != SOURCE_SHA256
    ):
        raise ValueError("Laya runtime differs from the pinned upstream source")
    file = path / (
        "multilingual/model.safetensors"
        if variant == "multilingual"
        else "model.safetensors"
    )
    sha = hashlib.sha256()
    with file.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            sha.update(block)
    if sha.hexdigest() != WEIGHT_SHA256[variant]:
        raise ValueError("Laya weights differ from the pinned checkpoint")


class ContextBudgetExceeded(ValueError):
    pass


def token_audit(agent, request):
    # Match the pinned author's sequence builder; detect every truncation stage.
    from laya.common import render_options, serialize_state

    tok = agent.tok
    q = agent._to_internal(request["question"])

    def encode(s):
        return tok(s.replace(tok.mask_token, " "), add_special_tokens=False)[
            "input_ids"
        ]

    options = [[tok.mask_token_id] + encode(" " + s) for s in render_options(q)]
    head = encode(q["t"] + " question: " + q["ins"])
    head_limit = agent.cfg.get("head_max_len", 192)
    limit = agent.cfg.get("max_len", 512)
    capped = [o[:49] for o in options]
    budget = head_limit - sum(map(len, capped))
    if budget < 16:
        per = max(4, (head_limit - 16) // max(1, len(capped)))
        capped = [o[:per] for o in capped]
        budget = head_limit - sum(map(len, capped))
    kept_head = min(len(head), max(8, budget))
    state = encode(serialize_state(request["state"]))
    room = max(0, limit - (kept_head + sum(map(len, capped)) + 4))
    result = dict(
        state_tokens=len(state),
        state_budget=room,
        instruction_tokens=len(head),
        instruction_budget=max(8, budget),
        max_len=limit,
        head_max_len=head_limit,
    )
    result["truncated"] = (
        len(state) > room
        or kept_head < len(head)
        or any(len(a) != len(b) for a, b in zip(options, capped))
    )
    return result


class LayaBackend:
    def __init__(self, multilingual=False):
        import torch
        import laya

        if not torch.cuda.is_available() or torch.cuda.device_count() != 1:
            raise RuntimeError(
                "Laya requires one visible CUDA GPU; laptop/CPU inference is disabled"
            )
        path = Path(os.environ["LAYA_MODEL_PATH"])
        if not path.is_dir():
            raise ValueError(
                "LAYA_MODEL_PATH must be a locally downloaded pinned checkpoint"
            )
        self.variant = "multilingual" if multilingual else "english"
        verify_pin(laya, path, self.variant)
        self.agent = laya.load(
            str(path), subfolder="multilingual" if multilingual else None, device="cuda"
        )
        for key, env in (
            ("max_len", "LAYA_MAX_LEN"),
            ("head_max_len", "LAYA_HEAD_MAX_LEN"),
        ):
            if env in os.environ:
                self.agent.cfg[key] = int(os.environ[env])
        if self.agent.device.type != "cuda":
            raise RuntimeError("Laya fell back from CUDA; evaluation refused")

    def classify(self, request):
        audit = token_audit(self.agent, request)
        if audit["truncated"]:
            raise ContextBudgetExceeded(
                "Laya would truncate state, policy or criteria; choose an explicit configuration or shared supported subset"
            )
        result = self.agent.predict(request["state"], {"decision": request["question"]})
        if self.agent.device.type != "cuda":
            raise RuntimeError("Laya changed inference device")
        answer = dict(result["answers"]["decision"])
        answer["resolved_model"] = (
            "convaiinnovations/laya/" + self.variant + "@" + MODEL_REVISION
        )
        answer["raw"] = {
            "native": result,
            "token_audit": audit,
            "runtime_commit": CODE_REVISION,
        }
        return answer
