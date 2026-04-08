# Rebuild Audit Note (2026-04-08)

## Current valid
- Bounded state clamping and bounded probability transform exist.
- Driver and source transparency are exposed in UI.
- Diagnostics/history persistence is already wired end-to-end.

## Partially valid
- Event logic existed but was still article-proxied in several scoring paths.
- De-escalation detection was too permissive for rhetorical items.
- Clustering existed but needed tighter time + class coherence.

## Misleading / needed replacement
- Weak de-escalation language could materially move score.
- Commentary could still appear in top drivers during high-volume periods.
- Some filtered driver empty-states were ambiguous to users.

## Replacements in this pass
- Added stricter de-escalation verification gating in classifier.
- Added tier metadata for signal classes.
- Tightened cluster keys with class/time bucket and class-weighted contribution.
- Improved user messaging for hidden non-positive-source-weight drivers.

## Cleanup targets still open
- Split model modules into explicit ingestion/normalization/clustering/scoring files.
- Expand historical validation fixtures beyond minimal unit tests.
- Add explicit backtest report generation and acceptance thresholds.
