# Model Governance

## Goal
Maintain realism, reproducibility, and stability over long-term operation.

## Change policy

1. Every model-logic change must include:
   - unit test updates (`tests/test_model.py`),
   - benchmark run (`tools/evaluate.py`),
   - brief rationale in PR body.

2. Changes to `model_config.json` require:
   - benchmark comparison before/after,
   - explicit mention of expected impact,
   - rollback note.

3. If benchmark direction accuracy drops by >5 points, do not merge without review.

## Operations

- Keep `diagnostics_log.json` for drop-reason trend monitoring.
- Watch for sudden jumps in `no_actor`, `no_signal`, or `invalid_pair` counts.
- Recalibrate source and signal weights on a regular schedule (e.g. monthly).
