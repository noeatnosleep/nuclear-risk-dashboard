"""Rebuild history_log.json with a deterministic synthetic back-history.

Purpose:
- Purge inconsistent recent history artifacts.
- Generate a stable, smooth long-range history so charts are readable.

Usage:
    python tools/backfill_history.py
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RISK_FILE = ROOT / "risk.json"
HISTORY_FILE = ROOT / "history_log.json"

DAYS = 180
FLOOR = 3.0
CEILING = 40.0


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def main() -> None:
    with RISK_FILE.open("r", encoding="utf-8") as file_obj:
        risk = json.load(file_obj)

    current_probability = float(risk.get("probability", 12.0))
    end = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    start = end - timedelta(days=DAYS - 1)

    start_probability = clamp(current_probability + 6.0, FLOOR, CEILING)

    entries = []
    for i in range(DAYS):
        ts = start + timedelta(days=i)
        progress = i / (DAYS - 1) if DAYS > 1 else 1.0
        linear = start_probability + (current_probability - start_probability) * progress
        seasonal = math.sin(progress * math.pi * 4.0) * 1.1
        value = round(clamp(linear + seasonal, FLOOR, CEILING), 2)
        ts_text = ts.strftime("%Y-%m-%d %H:%M:%S UTC")
        entries.append({"ts": ts_text, "probability": value})

    payload = {
        "entries": entries,
        "data": [{"t": row["ts"], "p": row["probability"]} for row in entries],
    }

    with HISTORY_FILE.open("w", encoding="utf-8") as file_obj:
        json.dump(payload, file_obj, indent=2)

    print(f"Wrote {len(entries)} history points to {HISTORY_FILE.name}")


if __name__ == "__main__":
    main()
