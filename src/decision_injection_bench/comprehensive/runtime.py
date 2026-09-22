"""Explicit model execution with bounded calls and append-only evidence."""

import copy
import importlib
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from ..cli import validate_answer
from ..suite import Backend
from .cases import digest, verify_plan


def utc():
    return datetime.now(timezone.utc).isoformat()


def runtime_identity():
    from importlib.metadata import PackageNotFoundError, version
    import platform

    root = Path(__file__).resolve().parents[1]
    sources = {
        str(p.relative_to(root)): p.read_text() for p in sorted(root.rglob("*.py"))
    }
    packages = {}
    for name in ("typesafe-sdk", "torch", "transformers", "semif-phase1"):
        try:
            packages[name] = version(name)
        except PackageNotFoundError:
            pass
    return {
        "implementation_sha256": digest(sources),
        "python": platform.python_version(),
        "packages": packages,
    }


def load_callable(path):
    module, symbol = path.split(":", 1)
    fn = getattr(importlib.import_module(module), symbol)
    if not callable(fn):
        raise ValueError("Plugin must be callable")
    return fn


class Defender:
    def __init__(self, name, plugin=None):
        self.name = name
        self.plugin = plugin
        self.native = None if plugin else Backend(name, retries=0)
        self.fn = load_callable(plugin) if plugin else self.native.classify
        if self.native:
            self.native.reuse_prefix = False

    def __call__(self, request):
        answer = self.fn(copy.deepcopy(request))
        validate_answer(answer)
        # Adapters may return raw model diagnostics but never top-level control fields.
        return {
            k: answer[k]
            for k in ("choice", "probabilities", "confidence", "resolved_model", "raw")
            if k in answer
        }


def read_records(path):
    if not path.exists():
        return []
    raw = path.read_bytes()
    if raw and not raw.endswith(b"\n"):
        raise ValueError(
            "Incomplete final JSONL line; preserve it and recover into a new run directory"
        )
    return [json.loads(line) for line in raw.splitlines()]


def append(file, record):
    file.write(json.dumps(record, ensure_ascii=False) + "\n")
    file.flush()
    os.fsync(file.fileno())


def execute_plan(
    plan, out, backend, plugin=None, max_calls=0, resume=False, defender=None
):
    verify_plan(plan)
    if max_calls < len(plan["cases"]):
        raise ValueError(
            f"Plan needs {len(plan['cases'])} logical defender calls; budget is {max_calls}. No calls made."
        )
    out = Path(out)
    metadata = dict(
        version=plan["version"],
        plan_sha256=plan["sha256"],
        backend=backend,
        adapter=plugin,
        requested_model=os.environ.get("JEV_MODEL", "jev-1.13.0")
        if backend == "jev"
        else backend,
        max_calls=max_calls,
        runtime=runtime_identity(),
    )
    if resume:
        old = json.loads((out / "run.json").read_text())
        if any(old[k] != v for k, v in metadata.items()):
            raise ValueError("Resume configuration mismatch")
    else:
        out.mkdir(parents=True, exist_ok=False)
        (out / "run.json").write_text(
            json.dumps(dict(metadata, started_utc=utc()), indent=2) + "\n"
        )
        (out / "plan.json").write_text(json.dumps(plan, ensure_ascii=False) + "\n")
    previous = read_records(out / "records.jsonl")
    if len(previous) > len(plan["cases"]):
        raise ValueError("Unexpected records")
    for sequence, (entry, row) in enumerate(zip(plan["cases"], previous)):
        if (
            row.get("case_id") != entry["case_id"]
            or row.get("plan_sha256") != plan["sha256"]
            or row.get("backend") != backend
            or row.get("sequence") != sequence
        ):
            raise ValueError("Resume evidence mismatch")
        if "error" in row:
            raise ValueError(
                "Failed call retained; start a new run instead of hiding failures"
            )
        validate_answer(row["answer"])
    if len(previous) == len(plan["cases"]):
        completion = {
            "completed": len(previous),
            "finished_utc": utc(),
            "records_sha256": digest(previous),
        }
        if (out / "complete.json").exists():
            saved = json.loads((out / "complete.json").read_text())
            if saved["records_sha256"] != completion["records_sha256"] or saved[
                "completed"
            ] != len(previous):
                raise ValueError("Completion checksum mismatch")
        else:
            (out / "complete.json").write_text(json.dumps(completion, indent=2) + "\n")
        return dict(completion, resumed_without_calls=True)
    model = defender or Defender(backend, plugin)
    with (out / "records.jsonl").open("a") as file:
        for i, entry in enumerate(plan["cases"][len(previous) :], len(previous)):
            record = dict(
                case_id=entry["case_id"],
                plan_sha256=plan["sha256"],
                backend=backend,
                sequence=i,
                timestamp=utc(),
            )
            started = time.monotonic()
            try:
                answer = model(copy.deepcopy(entry["request"]))
                validate_answer(answer)
                record["answer"] = answer
            except Exception as exc:
                record["error"] = type(exc).__name__
            record["elapsed_seconds"] = round(time.monotonic() - started, 6)
            append(file, record)
            if "error" in record:
                raise RuntimeError(
                    "Model call failed; exception type recorded, messages omitted"
                )
    completion = {
        "completed": len(plan["cases"]),
        "finished_utc": utc(),
        "records_sha256": digest(read_records(out / "records.jsonl")),
    }
    (out / "complete.json").write_text(json.dumps(completion, indent=2) + "\n")
    return completion
