# nuclear-risk-dashboard

A static dashboard that estimates global nuclear escalation risk from recent news headlines.

## Freshness model

This site is hosted on GitHub Pages (static hosting), so it cannot safely run the model on every page view.

- ✅ Good approach: refresh data on a schedule in GitHub Actions, then redeploy.
- ❌ Bad approach: trying to run ingestion/classification in the browser on each visit (CORS/rate-limit/reproducibility/security issues).

Current automation:
- `Update Risk` workflow runs every 30 minutes and updates generated artifacts.
- `Deploy Pages` workflow auto-deploys after `Update Risk` succeeds (plus normal push/manual triggers).

## What this does

- Reads recent world-news headlines and summaries.
- Identifies actors and conflict/de-escalation signals.
- Maps events to predefined bilateral state keys.
- Computes state updates with decay/coupling and produces a global probability.
- Publishes `risk.json`, `history_log.json`, `diagnostics_log.json`, and `build_info.json`.

## Long-term realism safeguards

- Fallback pairing disabled by default (no invented second actor from single-actor headlines).
- Class-specific confidence thresholds.
- Ambiguity penalty for mixed escalation/de-escalation text.
- Uncertainty score output and display.
- Diagnostics history for drop-reason drift.
- Evaluation benchmark in CI.

## Files

- `requirements.txt`: runtime dependencies.
- `model_config.json`: model weights/thresholds and source weighting.
- `config.py`: configuration loader.
- `ingest.py`: ingestion + dedupe + summary extraction.
- `events.py`: classifier + confidence + impacts.
- `risk.py`: state update + outputs + diagnostics.
- `index.html`: dashboard UI.
- `tools/evaluate.py`: benchmark/backtest runner.
- `data/eval_events.json`: starter labeled benchmark dataset.
- `GOVERNANCE.md`: change management process.
- `docs/likelihood-assessment.md`: calibration logic for realistic absolute likelihood.
- `docs/policy-driven-back-history.md`: policy model for deterministic historical backfill.

## Local run

```bash
pip install -r requirements.txt
python -m unittest discover -s tests -p 'test_*.py'
python tools/evaluate.py
python risk.py
python tools/backfill_history.py
```
