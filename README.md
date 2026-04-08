# nuclear-risk-dashboard

A static dashboard that estimates global nuclear escalation risk from recent news headlines.

## What this does (plain language)

- The system reads recent world-news headlines and summaries.
- It identifies actors and conflict/de-escalation signals.
- It maps events to predefined bilateral state keys.
- It computes state updates with decay/coupling and produces a global probability.
- It publishes `risk.json`, `history_log.json`, `diagnostics_log.json`, and `build_info.json`.

## Changes for long-term realism

- **Fallback pairing is disabled by default** to avoid inventing second actors from single-actor headlines.
- **Confidence thresholds are class-specific** (action/strategic need more confidence than rhetoric).
- **Ambiguity penalty** lowers confidence when headlines include both escalation and de-escalation terms.
- **Uncertainty score** is now output and shown in the UI.
- **Diagnostics history** records drop-reason trends over time.
- **Benchmark evaluation** runs in CI with `tools/evaluate.py` over `data/eval_events.json`.

## Files

- `model_config.json`: model weights/thresholds and source weighting.
- `config.py`: configuration loader.
- `ingest.py`: ingestion + dedupe + summary extraction.
- `events.py`: classifier + confidence + impacts.
- `risk.py`: state update + outputs + diagnostics.
- `index.html`: dashboard UI.
- `tools/evaluate.py`: benchmark/backtest runner.
- `data/eval_events.json`: starter labeled benchmark dataset.
- `GOVERNANCE.md`: change management process.

## Local run

```bash
pip install feedparser
python -m unittest discover -s tests -p 'test_*.py'
python tools/evaluate.py
python risk.py
```

## CI/CD

- `.github/workflows/update.yml`: tests, evaluation benchmark, risk run, publish artifacts.
