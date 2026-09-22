# Backend setup and adapter contract

Original model/runtime pins are in `results/2026-09-22/runtime-manifest.json`. The model choices came from the [JevBench composite ranking](https://benchmarkheaven.com/jev-models), not a safety ranking. djev was invite-only and was not tested.

## Jev

Install the `jev` extra. `JEV_API_KEY` is read only from the environment. `JEV_MODEL` defaults to `jev-1.13.0`; the resolved response model is recorded when returned. API calls use TypeSafe's `Choice` primitive, fixed criteria, and an SDK timeout/retry policy. A future server revision may differ from the original.

## SemIf

On a CUDA GPU host, clone [SemIf](https://github.com/TheoLeeCJ/SemIf), check out commit `1f2dea3e25379f9dfc98cb83c324f00ab5deda37`, then install its package in the same environment as this suite:

```sh
git clone https://github.com/TheoLeeCJ/SemIf.git
cd SemIf
git checkout 1f2dea3e25379f9dfc98cb83c324f00ab5deda37
python -m pip install -e .
```

The suite uses the author's PyTorch direct option-logit scorer, BF16, maximum 8192 tokens, and `Qwen/Qwen3.5-4B` revision `851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a`. Expose exactly one GPU using `CUDA_VISIBLE_DEVICES`. The original run used an RTX 4090 24 GB. This adapter deliberately prevents laptop/CPU fallback.

The adapter maps the state into `evidence`, the trusted policy into `criterion`, and label descriptions into letter options. Native system instructions and chat serialization come from the pinned author code. It chooses the maximum-scoring option; ties follow option order.

## Winnow

Clone the [official runtime](https://github.com/EldanRing/winnow-inference), pin commit `6c2b3c04e248a319f2cb43832628eba03e55fe38`, and follow its CUDA build instructions. The original build used CUDA 13.0.88 and compute capability 89 for an RTX 4090:

```sh
python scripts/build.py --backend cuda --cuda-arch 89 --jobs 8
python scripts/serve.py --model /path/to/Winnow-12B-Q8_0.gguf \
  --context 8192 --decision-parallel 1 --chat-parallel 1 \
  --cache q8_0 --memory exclusive --gpu 0 --port 8091
```

Download `gguf/Winnow-12B-Q8_0.gguf` from `EldanRing/Winnow-12B`, revision `b6ac22b0d51b69b18200acacb3fbdd98073fffe8`. SHA-256: `b710efc4c0d048ee61eed92c5fef5ce323a4d17e7c51f9f0533cc72ae50818ea`.

`WINNOW_URL` defaults to `http://127.0.0.1:8091`. Run the harness on the GPU host or use an SSH tunnel to its localhost port; no public server exposure is needed. The native `/v1/systemone` endpoint returns choice probabilities and diagnostics. Temperature is 1.0; prefix reuse is on for held-out requests and off for development/refinement.

## Laya

Native `laya` and `laya-multilingual` adapters use pinned upstream code and weights on a CUDA server. They reject truncated policies, criteria or state; see [Laya setup and typed-task track](laya-and-typed.md). The live comparison uses explicitly expanded token budgets, not silently truncated defaults.

## Custom adapters

`--adapter module:function` imports a trusted Python callable, invoked as `function(request)`. It receives only the canonical `state` and trusted `question`; no expected label, task ID, attack target or split metadata is passed. Return a dictionary with:

- `choice`: exactly `ALLOW` or `BLOCK`.
- `probabilities`: both labels, finite numbers in [0, 1], summing to one within 0.001.
- Optional provenance such as `resolved_model`, `confidence`, or `raw` native response.

Do not return credentials, authorization headers, personal data or unrelated server metadata. Keep policy and content separate when mapping the request. Document serialization, option order, sampling, model revision, hardware and score semantics. The suite does not assume native probabilities are calibrated across models.

The core suite installs no inference dependencies. Offline commands remain available without any backend package. New live integrations should be verified on controlled examples and publish their configuration differences.
