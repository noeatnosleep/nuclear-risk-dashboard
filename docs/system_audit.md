# System Audit — Nuclear Risk Dashboard

_Date: 2026-04-08_

| Area | Status | Notes |
|---|---|---|
| ingestion pipeline | partial | Works for live RSS ingestion; historical replay exists but depends on external API reliability. |
| event extraction | partial | Title-first extraction works; article body extraction is not yet robust. |
| source handling | exists but hidden | Source weighting is in config and partly shown in Nerdy details. |
| deduplication / clustering | partial | Exact+near-title dedupe exists; true cross-source event clustering is limited. |
| signal categories | partial | Current classes: rhetoric/movement/action/strategic/deescalation; mapped equivalents shown in Nerdy details. |
| weighting logic | correct | Source and signal weights configurable and bounded by clamps/thresholds. |
| decay / recency | correct | Time decay is applied in classifier and state decay toward baseline is applied. |
| contradiction handling | partial | Ambiguity penalty exists; richer contradiction matrix not yet implemented. |
| normalization / bounding | correct | State clamped to [0,10], uncertainty bounded, logistic probability bounded [0,100]. |
| confidence logic | partial | Confidence includes actors/signals/source/ambiguity; corroboration depth needs improvement. |
| trend logic | exists but hidden | Trend is derivable from history; explanation is now surfaced in Nerdy details. |
| historical storage | partial | history/diagnostics stored; replay backfill available but coverage quality varies. |
| tests | partial | baseline tests exist; deeper scenario/backtest coverage still needed. |
| build metadata | correct | build_info shown on UI and artifacts include timestamps. |

## Misleading risk to avoid

- The top-line percentage should not be interpreted as a validated real-world probability forecast.
- Sparse data periods can flatten trend lines.
- Source-count expansion does not equal source-quality validation.

## Immediate priorities

1. Event clustering across outlets (same event, multi-source).
2. Corroboration-aware confidence boost/penalty.
3. Historical replay quality scoring per day.
4. Scenario tests for duplicate flood + mixed contradiction days.
