# nuclear-risk-dashboard

A static dashboard that estimates global nuclear escalation risk from recent news headlines.

## What this does

- The system reads recent world-news headlines.
- It looks for country/actor names (US, China, Iran, etc.).
- It looks for escalation words (strike, missile, drill) and de-escalation words (ceasefire, talks, withdrawal).
- It converts those signals into a risk score for predefined country pairs.
- It applies time decay so old headlines matter less.
- It aggregates pair scores into one global risk percent shown on the dashboard.

## Why this is better for long-term accuracy

- **Mixed-signal scoring**: Headlines can contain both positive and negative signals; we now net them instead of picking only one label.
- **Deterministic pair selection**: If a headline mentions multiple countries, selection is stable and based on configured state weight priority.
- **Confidence filtering**: Weak/noisy events are dropped.
- **Drop-reason telemetry**: Debug output shows why events were ignored, which improves model tuning over time.

## Important limitations

- This is a **signal model**, not a predictive intelligence system.
- It is only as good as the headline quality and source coverage.
- Use this as exploratory analytics, not operational decision support.

## Core files

- `ingest.py`: RSS ingestion, deduplication, and source weighting.
- `actors.py`: actor extraction and conflict-signal detection.
- `events.py`: mixed-signal classification and impact scoring.
- `states.py`: canonical state configuration and weights.
- `risk.py`: end-to-end state update and probability generation.
- `index.html`: static UI that reads generated JSON artifacts.

## Local run

```bash
pip install feedparser
python -m unittest discover -s tests -p 'test_*.py'
python risk.py
```

Then open `index.html` in a static server (or publish via GitHub Pages).

## CI/CD

- `.github/workflows/update.yml`: scheduled/manual refresh + tests.
- `.github/workflows/pages.yml`: deploy static site to GitHub Pages.
