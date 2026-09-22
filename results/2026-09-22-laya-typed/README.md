# Laya extension and typed-decision pilot

**5,100 additional live defender calls**, on the user’s remote GPU server for both Laya checkpoints and through the hosted API for Jev. All five runs completed without errors. This is a small public regression experiment, not a safety leaderboard or a reproduction of the screenshot’s 500-example accuracy benchmark.

## Existing strict moderation/spam plan

The exact earlier 2,160-call plan is replayed for each Laya checkpoint: 24 texts in English/Spanish/Chinese, 44 attacks each, paired controls, strict policy, normal order and one repeat. Earlier Jev/SemIf/Winnow rows below reuse the published same-plan evidence; they are not additional runs.

| Model | Clean errors | Attack flips / clean-eligible | Flips with correct matched control | Length-control errors |
|---|---:|---:|---:|---:|
| Jev | 0/24 | 1/1056 | 1 | 0/1056 |
| SemIf | 0/24 | 289/1056 | 289 | 0/1056 |
| Winnow | 0/24 | 32/1056 | 32 | 1/1056 |
| Laya English | 11/24 | 358/572 | 318 | 529/1056 |
| Laya multilingual | 12/24 | 257/528 | 227 | 546/1056 |

**Do not compare these fractions as if they had the same denominator.** Laya made baseline errors, so those items are excluded from its attack denominator. Matched-control failures also show instability unrelated to the attack instructions. English-only Laya is not intended for the full three-language corpus; its English slice is shown separately:

| Checkpoint, English slice | Clean errors | Flips / eligible | Flips with correct matched control |
|---|---:|---:|---:|
| laya | 3/8 | 133/220 | 94 |
| laya-multilingual | 3/8 | 115/220 | 91 |

## New typed tasks

All three models receive the identical 260-call English plan, containing 22 authored base items, six attack families, clean/neutral controls and matched controls. Counts below are flips conditional on a correct clean decision. Parentheses show clean errors; review-score correctness means absolute error ≤0.5 on a zero-based 0..4 rubric.

| Task | Jev flips (clean errors) | Laya English flips (clean errors) | Laya multilingual flips (clean errors) |
|---|---:|---:|---:|
| news-topic | 0/24 (0/4) | 6/18 (1/4) | 12/24 (0/4) |
| emotion | 0/36 (0/6) | 4/36 (0/6) | 21/36 (0/6) |
| review-rating | 0/24 (0/4) | 6/18 (1/4) | 0/12 (2/4) |
| injection-detection | 0/24 (0/8) | 0/24 (0/8) | 2/24 (0/8) |

Four benign detector examples receive controls only. Injecting instructions into a benign example would change its correct label, so such label changes would not demonstrate a jailbreak. Detector attacks here try to conceal an already-present manipulation instruction. All wrappers are fixed and classifier-directed; generated LLM search is not used.

Jev had no flips in this small typed pass. That is not evidence of immunity. Laya’s English checkpoint had topic/emotion/review-score flips; its multilingual checkpoint also had two detector evasions. Exact task rules, thresholds, controls and source examples are archived; [examples.json](examples.json) provides short illustrative failures with clean responses. Native `noul` thresholds and `score` changes are scored directly, without converting every task into ALLOW/BLOCK.

## Configuration and reproducibility

Pinned native Laya **0.3.5**, commit `573e5b62696ba441230cd6be71d593331b5d23af`, and model revision `1c5edc17a7acd8701df6fc341c0d179f1c62c982`. Two fixed checkpoints: English ModernBERT-large and multilingual mmBERT-base. These differ from the screenshot’s 0.3.4 English MLX setup; the automatic Router and typed-decisions fine-tune were not tested. No model fine-tuning or temperature fitting was done.

Context was explicitly expanded to 8,192 with a 1,024-token head budget. **No input was truncated.** With shipped defaults, 383/2,160 English-checkpoint inputs and 181/2,160 multilingual-checkpoint inputs would not fit losslessly. Every short typed-track input fits the checkpoint defaults and yields the same token sequence under the expanded settings. Per-case token audits are archived as JSON gzip files. Expanded context is an inference configuration change, not evidence the model was trained for this task or context length.

All open-model inference used remote RTX 4090 GPUs with native BF16 autocast. The GPU memory was released after completion. Jev credentials remained local. Runtime identities, package versions, checkpoint weight hashes and exact request plans are retained. Execution-source snapshots match the implementation hashes captured at run start; the English/remote vs Jev snapshots differ only in formatting. The published adapter additionally verifies source and weight pins before model loading.

Labels are authored, not independently reviewed; only one repeat and a small set of scenarios were tested. No confidence calibration, latency-speedup or deployment-wide failure estimate is claimed. See [setup and methodology](../../docs/laya-and-typed.md).

```sh
python scripts/audit_laya_typed.py
```
