# Decision Injection Bench

A public prompt-injection and jailbreak test suite for **Jev-like structured decision systems**. Can attacker-controlled content change a correct classification while the answer still satisfies its schema?

The first suite covers adult-content moderation and spam detection, with `ALLOW`/`BLOCK` decisions. It includes targeted attack development, clean and neutral controls, three trusted policy conditions, frozen transfer tests, model adapters, and **1,332 recorded calls** from Jev 1.13.0, SemIf/Qwen3.5-4B, and Winnow-12B Q8.

Independent research; not affiliated with TypeSafe, Jev, SemIf, or Winnow. This is a small reproducible evaluation, not a universal safety leaderboard or an exhaustive state-of-the-art jailbreak benchmark.

## Start offline

Python 3.10+; no model downloads, credentials, GPU, or runtime dependencies are needed for these commands:

```sh
git clone https://github.com/cwhy/decision-injection-bench.git
cd decision-injection-bench
python -m venv .venv
. .venv/bin/activate
python -m pip install -e .
python -m unittest discover -s tests -v
python scripts/audit_reference.py
decision-injection-bench score results/2026-09-22/*-heldout.jsonl
decision-injection-bench export --out /tmp/decision-cases.jsonl
```

The export contains 264 held-out cases, including gold labels for evaluation. **Send only each case's `request` to a model**, never the surrounding evaluation metadata. No model call happens on import, installation, scoring, export, or CI.

## Recorded results

Targeted flips / 56 eligible attack calls per model and policy:

| Model | Basic | Hardened | Strict |
|---|---:|---:|---:|
| Jev 1.13.0 | 15/56 | 8/56 | 0/56 |
| SemIf · Qwen3.5-4B BF16 | 40/56 | 32/56 | 32/56 |
| Winnow-12B Q8 | 48/56 | 8/56 | 8/56 |

All paired clean and neutral controls were correct. Counts include two repeats; there are only eight authored held-out base items. Repeats are not independent observations and these fractions are not deployment-wide failure estimates.

Jev falsely blocked a requested train-ticket receipt after an encoded-label instruction in both basic-policy repeats. All eight hardened Jev flips involved redefining the item as archival. Explicit scope rules prevented those observed flips. That does not prove immunity to other attacks.

See [methodology](docs/methodology.md), [reference evidence](results/2026-09-22), and [runtime pins](results/2026-09-22/runtime-manifest.json). These historical held-out items are now public: use them as regression cases, not as a secret or fresh test set after tuning on them.

## Live evaluation

Live commands incur API usage or GPU compute and refuse to overwrite output files. Errors are recorded by exception type and stop the run; credentials and exception messages are not logged. Set credentials only in environment variables. The suite never reads a neighboring project's `.env`.

### Jev hosted API

```sh
python -m pip install -e '.[jev]'
export JEV_API_KEY='your-key'
# Optional: export JEV_MODEL='another-pinned-model'
decision-injection-bench run --backend jev --phase heldout --out runs/jev-heldout.jsonl
```

Default model: `jev-1.13.0`; requested version and resolved response model are retained in the original reference evidence. Hosted availability may change.

### Winnow server

Run the author's pinned CUDA server on a GPU host; see [backend setup](docs/backends.md). On that host:

```sh
export WINNOW_URL=http://127.0.0.1:8091
decision-injection-bench run --backend winnow --phase heldout --out runs/winnow-heldout.jsonl
```

### SemIf on a GPU server

Install the pinned author package described in [backend setup](docs/backends.md). The adapter requires exactly one visible CUDA GPU and BF16 weights; it refuses CPU or Apple GPU fallback.

```sh
CUDA_VISIBLE_DEVICES=0 decision-injection-bench run --backend semif --phase heldout --out runs/semif-heldout.jsonl
```

No weights are bundled. **Do not run these model backends on a laptop.** Use a GPU server; offline scoring and hosted API requests are lightweight.

### Add another system

Supply a Python callable taking only the canonical request and returning:

```python
# my_adapter.py — connect your actual model inside this function
def classify(request):
    # request = {"state": {"submitted_content": ...}, "question": {
    #   "type": "choice", "instructions": ..., "criteria": {...}}}
    response = your_model_client.classify(request)  # implement this integration
    return {
        "choice": response.choice,                 # ALLOW or BLOCK
        "probabilities": response.probabilities,   # both labels, normalized
        "resolved_model": response.model,
    }
```

```sh
PYTHONPATH=. decision-injection-bench run --backend my-system \
  --adapter my_adapter:classify --phase heldout --out runs/my-system-heldout.jsonl
```

A custom adapter is trusted local Python code. Keep the trusted criterion separate from submitted content. Preserve the model's native probabilities when available; disclose any synthetic scores instead of describing them as calibrated. See [the adapter contract](docs/backends.md).

## Develop new attacks

```sh
decision-injection-bench run --backend jev --phase development --out runs/jev-development.jsonl
decision-injection-bench run --backend jev --phase refinement --out runs/jev-refinement.jsonl
# Repeat for semif and winnow with the corresponding file names.
python scripts/select_attacks.py --data runs
decision-injection-bench run --backend jev --phase heldout \
  --selected runs/selected-attacks.json --out runs/jev-heldout.jsonl
```

Development is 132 calls per backend; refinement is 48. Selection freezes the union of each backend's strongest scope/policy and direct-label candidates. Use a **new, independently labelled base test set** for new research claims; rerunning the exposed historical holdout is a regression check.

## Contribute

See [CONTRIBUTING.md](CONTRIBUTING.md). Useful contributions include new task families, adapters, independently reviewed labels, length-matched controls, and stronger attack generators. Include unsuccessful attempts and exact budgets. CI is offline and never needs secrets.

MIT licensed for this repository's original code, authored fixtures, and recorded experiment artifacts. External model weights, runtimes, and research papers retain their own licenses; none are vendored here.
