# Contributing

Open an issue or pull request with a concrete addition: model adapter, authored task family, attack generator, control, scoring fix, or reproducible result.

For experiment contributions:

1. State the trusted policy, attacker-controlled input, expected labels, and model configuration.
2. Preserve the original base content and include paired clean and neutral controls.
3. Separate attack development from new evaluation items. Freeze selection before held-out requests.
4. Retain unsuccessful attempts, errors and full query budgets. Separate setup failures from completed runs.
5. Distinguish prompt-induced errors from ordinary baseline errors and ambiguous changes in task scope.
6. Use synthetic examples and omit credentials, personal messages, machine addresses, or model weights.

Do not modify the historical `results/2026-09-22` records to improve scores. Add a new dated result directory with its own provenance. Existing public cases are regression tests, not a fresh holdout.

Run `python -m unittest discover -s tests -v` and `python scripts/audit_reference.py` before submitting. CI never calls models or reads API secrets.

For comprehensive v2, keep semantic groups and all their translations within one split. Add offline tests for budget accounting, feedback flow, provenance, and matched-control scoring. Do not describe harness stub results as model measurements.
