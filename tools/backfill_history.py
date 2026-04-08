"""Rebuild history_log.json using a policy-driven back-history configuration.

Usage:
    python tools/backfill_history.py
    python tools/backfill_history.py --policy data/backhistory_policy.json
"""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RISK_FILE = ROOT / "risk.json"
HISTORY_FILE = ROOT / "history_log.json"
DEFAULT_POLICY_FILE = ROOT / "data" / "backhistory_policy.json"


@dataclass(frozen=True)
class Anchor:
    date: datetime
    probability: float


@dataclass(frozen=True)
class VolatilityBand:
    start: datetime
    end: datetime
    amplitude: float


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def parse_utc_date(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%d").replace(tzinfo=timezone.utc)


def load_policy(policy_path: Path, current_probability: float) -> dict:
    if not policy_path.exists():
        return {
            "days": 180,
            "floor": 3.0,
            "ceiling": 40.0,
            "anchors": [
                {
                    "date": (datetime.now(timezone.utc) - timedelta(days=179)).strftime("%Y-%m-%d"),
                    "probability": round(clamp(current_probability + 6.0, 3.0, 40.0), 2),
                },
                {
                    "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                    "probability": round(current_probability, 2),
                },
            ],
            "volatility_bands": [],
        }

    with policy_path.open("r", encoding="utf-8") as file_obj:
        return json.load(file_obj)


def build_anchors(policy: dict, floor: float, ceiling: float, end_date: datetime, current_probability: float) -> list[Anchor]:
    anchors = []
    for row in policy.get("anchors", []):
        anchors.append(
            Anchor(
                date=parse_utc_date(row["date"]),
                probability=clamp(float(row["probability"]), floor, ceiling),
            )
        )

    if not anchors:
        anchors = [
            Anchor(date=end_date - timedelta(days=179), probability=clamp(current_probability + 6.0, floor, ceiling)),
            Anchor(date=end_date, probability=clamp(current_probability, floor, ceiling)),
        ]

    anchors = sorted(anchors, key=lambda row: row.date)

    if anchors[-1].date < end_date:
        anchors.append(Anchor(date=end_date, probability=clamp(current_probability, floor, ceiling)))
    elif anchors[-1].date > end_date:
        anchors[-1] = Anchor(date=end_date, probability=clamp(current_probability, floor, ceiling))

    return anchors


def build_bands(policy: dict) -> list[VolatilityBand]:
    bands = []
    for row in policy.get("volatility_bands", []):
        bands.append(
            VolatilityBand(
                start=parse_utc_date(row["start_date"]),
                end=parse_utc_date(row["end_date"]),
                amplitude=float(row.get("amplitude", 0.0)),
            )
        )
    return bands


def interpolate_probability(day: datetime, anchors: list[Anchor]) -> float:
    if day <= anchors[0].date:
        return anchors[0].probability

    for i in range(1, len(anchors)):
        left = anchors[i - 1]
        right = anchors[i]
        if left.date <= day <= right.date:
            total = (right.date - left.date).days or 1
            offset = (day - left.date).days
            progress = offset / total
            return left.probability + (right.probability - left.probability) * progress

    return anchors[-1].probability


def volatility_adjustment(day: datetime, bands: list[VolatilityBand]) -> float:
    amplitude = 0.0
    for band in bands:
        if band.start <= day <= band.end:
            amplitude = max(amplitude, band.amplitude)
    if amplitude <= 0:
        return 0.0

    ordinal = day.toordinal()
    return math.sin(ordinal * 0.45) * amplitude


def build_entries(days: int, floor: float, ceiling: float, anchors: list[Anchor], bands: list[VolatilityBand]) -> list[dict]:
    end = anchors[-1].date
    start = end - timedelta(days=days - 1)
    entries = []

    for i in range(days):
        day = start + timedelta(days=i)
        base = interpolate_probability(day, anchors)
        noise = volatility_adjustment(day, bands)
        value = round(clamp(base + noise, floor, ceiling), 2)
        ts_text = day.strftime("%Y-%m-%d 00:00:00 UTC")
        entries.append({"ts": ts_text, "probability": value})

    return entries


def main() -> None:
    parser = argparse.ArgumentParser(description="Rebuild history_log.json from policy anchors and bands")
    parser.add_argument("--policy", default=str(DEFAULT_POLICY_FILE), help="Path to back-history policy JSON")
    args = parser.parse_args()

    with RISK_FILE.open("r", encoding="utf-8") as file_obj:
        risk = json.load(file_obj)

    current_probability = float(risk.get("probability", 12.0))
    policy_path = Path(args.policy)
    policy = load_policy(policy_path, current_probability)

    days = int(policy.get("days", 180))
    floor = float(policy.get("floor", 3.0))
    ceiling = float(policy.get("ceiling", 40.0))
    end_date = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

    anchors = build_anchors(policy, floor, ceiling, end_date, current_probability)
    bands = build_bands(policy)
    entries = build_entries(days, floor, ceiling, anchors, bands)

    payload = {
        "entries": entries,
        "data": [{"t": row["ts"], "p": row["probability"]} for row in entries],
    }

    with HISTORY_FILE.open("w", encoding="utf-8") as file_obj:
        json.dump(payload, file_obj, indent=2)

    print(f"Policy: {policy_path}")
    print(f"Anchors: {len(anchors)} | Volatility bands: {len(bands)}")
    print(f"Wrote {len(entries)} history points to {HISTORY_FILE.name}")


if __name__ == "__main__":
    main()
