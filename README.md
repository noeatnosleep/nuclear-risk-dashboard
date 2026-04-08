# nuclear-risk-dashboard

A static dashboard that estimates global nuclear escalation risk from recent news headlines.

## What this project does

- Ingests headlines from selected world-news RSS feeds.
- Extracts actors and conflict/de-escalation signals from headline text.
- Maps events to predefined bilateral geopolitical state pairs.
- Applies time decay, source weighting, and cross-state coupling to update pair-level risk state.
- Converts weighted state values to a headline probability (0-100%) for display.
- Publishes `risk.json`, `history_log.json`, and `build_info.json` for static UI rendering.

## Important limitations

- This is a **signal model**, not a predictive system.
- Output reflects heuristic weighting over headlines and does **not** represent intelligence-grade forecasts.
- Headlines can be noisy, duplicated, or incomplete, and may cause false positives/negatives.
- Treat this tool as exploratory analytics only.

## Core files

- `ingest.py`: RSS ingestion, deduplication, and source weighting.
- `actors.py`: actor extraction and conflict-signal detection.
- `events.py`: event classification (including de-escalation) and impact scoring.
- `states.py`: canonical state configuration and weights.
- `risk.py`: end-to-end state update and probability generation.
- `index.html`: static UI that reads generated JSON artifacts.

## Local run

```bash
pip install feedparser
python risk.py
```

Then open `index.html` in a static server (or publish via GitHub Pages).

## CI/CD

- `.github/workflows/update.yml`: scheduled and manual risk refresh.
- `.github/workflows/pages.yml`: deploy static site to GitHub Pages.
