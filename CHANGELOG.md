# Changelog

## 0.2.1 — Live evidence and semantic-validity safeguard

- Publish the first strict-policy comprehensive campaign, including static tests, BoN transfer and diagnostic LLM-driven searches.
- Live testing found generated wrappers that introduce genuine spam while retaining the original text. Their label changes are not established jailbreaks.
- Block automatic transfer of unreviewed iterative/beam wrappers, flag raw search scores, and strengthen proposer instructions to preserve classification semantics.
- Add an offline evidence audit that reproduces every score and frozen selection; preserve the original v0.2.0 execution records and simple-v1 results.

## 0.2.0 — Comprehensive v2

- Preserve simple v1 commands, frozen cases, and all 1,332 reference records.
- Add explicit `simple` and `comprehensive` command groups.
- Add 72 authored multilingual texts in 24 disjoint scenario groups.
- Add 44 static attack variants, character-length-matched controls, policy conditions, and label-order reversal.
- Implement budgeted Best-of-N, LLM iterative refinement, and beam-search classification adaptations.
- Add development-only attack freezing and cross-model transfer plans.
- Add hashed plans, append-only evidence, error retention, configuration-checked resume, and scenario-cluster scoring.
- Add offline regression tests and CI coverage. No comprehensive live model results claimed.

## 0.1.0 — Simple v1

Original published suite: 180 development/refinement calls and 264 historical held-out calls per model, with Jev, SemIf, and Winnow reference results.
