# Nuclear Strike Likelihood Calibration Notes

_Last updated: 2026-04-08 UTC._

## Why the dashboard can look too high

The dashboard score is an event-intensity indicator driven by current headlines. It is useful for relative movement (up/down), but it should not be interpreted directly as a literal annual probability of a nuclear detonation.

## Working estimate for real-world baseline likelihood

For a **single-year horizon**, a defensible planning baseline for "at least one deliberate or accidental nuclear strike anywhere" is likely in the **low single digits or below** (roughly **0.1% to 1% per year**, with very wide uncertainty).

This range is intentionally conservative and should be treated as a calibration prior, not a forecast.

## Logic used to reach that estimate

1. **Base-rate reasoning**: Nuclear weapons have existed for decades with repeated severe crises but no wartime use since 1945; this implies low annual base rates.
2. **Trend stressors**: Modern deterioration factors (arms-control erosion, regional wars, missile modernization, command-and-control cyber risk) push risk upward from historical peacetime baseline.
3. **Tail-risk compounding**: Multiple nuclear dyads increase aggregate global risk even when each pair’s annual probability is small.
4. **Uncertainty dominance**: Expert disagreement is large; model outputs should preserve wide uncertainty bands and avoid overconfident point estimates.

## Practical model implications

- Keep event-driven directionality (useful for near-term movement).
- Anchor absolute probability with a lower baseline prior.
- Distinguish:
  - **Relative risk index** (headline-reactive), vs
  - **Calibrated annual probability** (base-rate anchored).
- Expand source coverage and include institutional/government feeds to reduce media-source bias.

## Near-term implementation in this repo

- Expanded ingestion feeds to include government and institutional channels (UN, IAEA, U.S. State, U.S. DoD, NATO) plus additional major media feeds.
- Added `signal_sources` to `risk.json` and surfaced them in the UI.
- Lowered logistic calibration aggressiveness in `model_config.json` (`probability_center`, `probability_steepness`) to reduce inflated top-line percentages while preserving movement sensitivity.
