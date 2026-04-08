# System Audit — Nuclear Risk Dashboard

_Date: 2026-04-08_

| Area | Status | Notes |
|---|---|---|
| ingestion pipeline | complete | Live RSS ingestion plus replayed historical ingestion from GDELT for back-history generation. |
| event extraction | partial | Title+summary classification is stable; full body extraction remains a future enhancement. |
| source handling | complete | Source weighting is in `model_config.json` and surfaced in UI details. |
| deduplication / clustering | complete | Near-duplicate dedupe plus cross-source driver clustering with corroboration counts. |
| signal categories | complete | rhetoric/movement/action/strategic/deescalation with contradiction matrix adjustments. |
| weighting logic | complete | Source and signal weights configurable and bounded by clamps/thresholds. |
| decay / recency | complete | Time decay and baseline decay are both applied. |
| contradiction handling | complete | Explicit contradiction matrix penalties reduce mixed-signal overstatement. |
| normalization / bounding | complete | State clamped to [0,10], uncertainty bounded, probability bounded [0,100]. |
| confidence logic | complete | Confidence includes actors/signals/source/ambiguity/corroboration depth. |
| trend logic | complete | Trend derives from full historical timeline with mode-specific bucketing. |
| historical storage | complete | history/diagnostics are replay-generated and include per-point driver lists. |
| tests | complete | Guardrails, contradiction handling, clustering, and boundedness checks are covered. |
| build metadata | complete | build info shown in UI and artifacts include timestamps. |

## Misleading risk to avoid

- The top-line percentage should not be interpreted as a validated real-world probability forecast.
- Data-source quality can vary by day; corroboration depth should be inspected per driver cluster.
- Source-count expansion does not equal source-quality validation.

## Completed priorities

1. Event clustering across outlets (same event, multi-source) is implemented with corroboration-aware driver clusters.
2. Corroboration-aware confidence boost/penalty is implemented in driver aggregation and uncertainty computation.
3. Historical replay quality is visible via diagnostics and deterministic replay-backed history generation.
4. Scenario tests include contradiction-heavy and boundedness guard cases.
