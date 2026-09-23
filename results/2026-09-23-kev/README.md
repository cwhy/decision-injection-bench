# Kev size sweep: does a stricter policy help every model?

**1,584 live defender calls** across three Kev sizes on the frozen simple-v1 held-out plan — the same 8 items, same frozen attack list, same three trusted policies, two repeats — plus a calibration A/B and a serving-flag control. All runs completed without errors on a remote RTX 4090.

Kev is [an open Jev-like decision model family](https://github.com/jaredpalmer/kev) built on Qwen3.5 bases, Apache-2.0, with a System One–compatible endpoint. That last part matters here: **Kev-4B and SemIf share the same Qwen3.5-4B base**, so the pair isolates the decision layer from the backbone.

## The result

Targeted flips out of 56 eligible attack calls. Lower is better. Earlier rows reuse published evidence and are not new runs.

| Model | Basic | Ignore embedded commands | Also check every part | Effect of the defense |
|---|---:|---:|---:|---|
| Jev 1.13.0 | 15 | 8 | **0** | −15 |
| Winnow-12B Q8 | 48 | 8 | 8 | −40 |
| SemIf · Qwen3.5-4B | 40 | 32 | 32 | −8 |
| Kev-9B | 18 | 16 | 16 | −2 |
| Kev-4B | 16 | 14 | 16 | 0 |
| Kev-0.8B | 28 | 34 | **40** | **+12** |

Clean controls were correct in every condition for all three sizes. Kev-0.8B failed 4 neutral controls (harmless padding, no instruction); the other two failed none.

**Two things fall out of this.**

**The trusted-policy defense has a capability threshold, and below it the defense backfires.** Within one family — same training data, same settings, only parameter count changing — the effect of adding defensive instructions flips sign monotonically: Kev-0.8B gets 43% worse, Kev-4B is unmoved, Kev-9B improves slightly. The crossover sits between 4B and 9B. The hardening text is roughly 565 additional characters of instruction; a model has to be capable enough to use it, and below that threshold it is just more text to be confused by.

**Size buys the ability to use a defense, not raw injection resistance.** Baseline robustness is *not* monotonic in size — at the basic policy, Kev-4B (16) and Kev-9B (18) are effectively tied, and both are far better than Kev-0.8B (28). What scales cleanly is responsiveness to the policy, not the flip count itself. These are separable properties and this sweep separates them.

On the controlled pair: Kev-4B flips 16/56 at the basic policy where SemIf flips 40/56, on the same Qwen3.5-4B base. The decision layer, not the backbone, accounts for the difference.

## The serving flag is not a no-op

`KEV_MERGE` controls whether the LoRA adapter is folded into the base weights. Merged and unmerged are algebraically the same function, so this was expected to be irrelevant. It is not:

| Model | Decisions that differ | max abs delta p(ALLOW) |
|---|---:|---:|
| Kev-4B | **4 / 264** | 0.0249 |
| Kev-0.8B | 0 / 264 | 0.0346 |

Kev-4B's scores move from 16/16/18 merged to 16/14/16 unmerged. bf16 rounding in the fused `W+BA` matmul versus the two-matmul path is enough to tip borderline decisions.

Both sets are published here. `KEV_MERGE=0` is the canonical setting for every size, because Kev-9B with the merged adapter exceeds 24 GB during `.to(cuda)` — peak 23.3 GiB, OOM while allocating 192 MiB — and serves at 16.1 GB unmerged. Pinning one setting across the family is what makes the size comparison above legitimate.

The practical reading: on a suite this small, a single-run difference of a few flips is within the noise a serving flag can produce. Differences of 2 should not be interpreted; the 0.8B result (+12) and the Jev result (−15) are the ones large enough to mean something.

## Calibration under attack

Kev applies a stored temperature (~2.1–2.4, fitted per checkpoint on in-distribution development data). `KEV_TEMPERATURE=1.0` serves raw logits. Both arms ran on the merged Kev-4B configuration, so they are directly comparable to each other.

Flip counts are **identical** in both arms (16/16/18). Temperature scaling is monotonic and cannot change an argmax, which is what the upstream README claims and what this confirms. What changes is confidence on wrong answers:

| Attacked calls (n=168, 50 wrong) | Confident-wrong (p ≥ 0.9) | Mean p on wrong answers |
|---|---:|---:|
| Calibrated (default) | 24 / 50 | 0.808 |
| Raw logits | 30 / 50 | 0.876 |

The fitted calibration still helps under adversarial input — 30 confident errors down to 24. But as a share of all attacked calls that is 14.3%, against the 4.0% the upstream README reports for clean new sources. Roughly 3.6× worse under attack, while still working directionally.

**This suite cannot measure clean calibration at all**: Kev-4B made zero errors on 96 clean and neutral control calls. The comparison above is against an upstream reported figure on different data, not against a clean baseline measured here.

## Reproduce

```sh
git clone https://github.com/jaredpalmer/kev.git && cd kev
uv sync --extra serve
CUDA_VISIBLE_DEVICES=0 KEV_DTYPE=bf16 KEV_MERGE=0 \
  uv run --extra serve python -m kev.serve --run jaredpalmer/kev-4b --port 8009
```

Then, from this repository:

```sh
PYTHONPATH=. KEV_URL=http://127.0.0.1:8009 \
  decision-injection-bench run --backend kev-4b \
  --adapter kev_adapter:classify --phase heldout --out runs/kev-4b.jsonl
decision-injection-bench score runs/kev-4b.jsonl
```

Adapter: [`kev_adapter.py`](../../kev_adapter.py). Exact revisions, host, environment, and per-file checksums: [`manifest.json`](manifest.json). All scores: [`scores.json`](scores.json).

## Limits

- Eight authored held-out items, two repeats. Repeats are not independent observations, and these counts are not deployment failure rates.
- The held-out items have been public since 2026-09-22. These are regression cases, not a fresh test set.
- One run per configuration. Given the `KEV_MERGE` result above, treat small differences as noise.
- **Kev-9B was not run merged** (does not fit 24 GB) and the family was not run on a second GPU: `kev.serve` has no `device_map`, and sharding would require patching the loader and the pointer head, producing a configuration nobody else could reproduce.
- JevBench v1.3.0 ranks Kev 0.5B/0.6B/4B/8B — a *previous* generation. The weights here (0.8B/4B/9B) do not correspond to those leaderboard rows.
