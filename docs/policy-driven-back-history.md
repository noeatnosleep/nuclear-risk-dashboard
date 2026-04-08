# Policy-Driven Back-History (Design + Operations)

## Why policy-driven back-history exists

A pure synthetic curve is clean, but it is opaque and hard to govern. A policy-driven approach makes the generated history:

1. **Explainable**: every shape change ties back to explicit policy fields.
2. **Auditable**: reviewers can diff policy JSON to understand why charts changed.
3. **Repeatable**: same policy + code yields deterministic output.
4. **Editable without code changes**: maintainers can tune anchors and volatility with data-only edits.

## Conceptual model

Back-history is generated in three layers:

1. **Anchor trajectory (macro trend)**
   - The policy defines key date/level anchor points.
   - The generator linearly interpolates between anchors day-by-day.

2. **Volatility bands (micro variation)**
   - Optional time windows add bounded sinusoidal variation.
   - This avoids perfectly straight lines while preserving deterministic behavior.

3. **Risk bounds (safety rails)**
   - `floor` and `ceiling` clamp all generated probabilities.
   - Prevents unrealistic spikes or negative values.

## Policy schema

File: `data/backhistory_policy.json`

- `days` *(int)*: number of daily points to emit.
- `floor` *(float)*: lower hard bound.
- `ceiling` *(float)*: upper hard bound.
- `anchors` *(array)*:
  - `date` (YYYY-MM-DD)
  - `probability` (float)
- `volatility_bands` *(array, optional)*:
  - `start_date` (YYYY-MM-DD)
  - `end_date` (YYYY-MM-DD)
  - `amplitude` (float)

## Generation algorithm

For each day in the configured period:

1. Compute base value from anchor interpolation.
2. If day falls in a volatility band, add deterministic periodic offset.
3. Clamp to `[floor, ceiling]`.
4. Write to `history_log.json` as both:
   - `entries[]`: `{ts, probability}`
   - `data[]`: `{t, p}`

## Governance recommendations

Use this policy process when adjusting back-history:

1. **Anchor change review**
   - Require short rationale for each anchor edit (geopolitical context or calibration intent).

2. **Volatility discipline**
   - Keep amplitude low unless there is a clear reason.
   - Avoid amplitudes that visually imply crisis events absent supporting narrative.

3. **Change control**
   - Treat policy updates similarly to model-weight changes (review + checksumable diff).

4. **Consistency with top-line calibration**
   - If `probability_center`/`steepness` changes materially, re-evaluate anchors so history remains coherent.

## Operational commands

```bash
python tools/backfill_history.py
python tools/backfill_history.py --policy data/backhistory_policy.json
```

## Practical extension ideas

- Add **regime labels** (e.g., "baseline", "crisis", "de-escalation") and generate piecewise volatility per regime.
- Add a **CI check** ensuring policy dates are sorted and within generated range.
- Add a small **policy visualizer** for local review before committing regenerated history.
