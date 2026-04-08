"""Rebuild history_log.json and diagnostics_log.json from a policy-driven back-history."""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config import load_config
from states import BASELINE_STATE, STATE_WEIGHTS

RISK_FILE = ROOT / "risk.json"
HISTORY_FILE = ROOT / "history_log.json"
DIAGNOSTICS_FILE = ROOT / "diagnostics_log.json"
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


def load_policy(path: Path, current_probability: float) -> dict:
    if not path.exists():
        end = datetime.now(timezone.utc)
        return {
            "days": 365,
            "floor": 2.0,
            "ceiling": 35.0,
            "anchors": [
                {"date": (end - timedelta(days=364)).strftime("%Y-%m-%d"), "probability": round(current_probability + 4.0, 2)},
                {"date": end.strftime("%Y-%m-%d"), "probability": round(current_probability, 2)},
            ],
            "volatility_bands": [],
        }
    with path.open("r", encoding="utf-8") as file_obj:
        return json.load(file_obj)


def build_anchors(policy: dict, floor: float, ceiling: float, end_date: datetime, current_probability: float) -> list[Anchor]:
    anchors = [
        Anchor(date=parse_utc_date(row["date"]), probability=clamp(float(row["probability"]), floor, ceiling))
        for row in policy.get("anchors", [])
    ]
    if not anchors:
        anchors = [
            Anchor(date=end_date - timedelta(days=364), probability=clamp(current_probability + 4.0, floor, ceiling)),
            Anchor(date=end_date, probability=clamp(current_probability, floor, ceiling)),
        ]
    anchors = sorted(anchors, key=lambda x: x.date)
    if anchors[-1].date != end_date:
        anchors.append(Anchor(date=end_date, probability=clamp(current_probability, floor, ceiling)))
    return anchors


def build_bands(policy: dict) -> list[VolatilityBand]:
    return [
        VolatilityBand(start=parse_utc_date(row["start_date"]), end=parse_utc_date(row["end_date"]), amplitude=float(row.get("amplitude", 0.0)))
        for row in policy.get("volatility_bands", [])
    ]


def interpolate_probability(day: datetime, anchors: list[Anchor]) -> float:
    if day <= anchors[0].date:
        return anchors[0].probability
    for i in range(1, len(anchors)):
        left = anchors[i - 1]
        right = anchors[i]
        if left.date <= day <= right.date:
            span = max((right.date - left.date).days, 1)
            offset = (day - left.date).days
            return left.probability + (right.probability - left.probability) * (offset / span)
    return anchors[-1].probability


def volatility_adjustment(day: datetime, bands: list[VolatilityBand]) -> float:
    amp = 0.0
    for band in bands:
        if band.start <= day <= band.end:
            amp = max(amp, band.amplitude)
    return math.sin(day.toordinal() * 0.42) * amp if amp > 0 else 0.0


def invert_probability_to_state_scale(probability: float, config: dict) -> float:
    p = clamp(probability / 100.0, 1e-6, 1 - 1e-6)
    z = math.log(p / (1 - p))
    center = float(config.get("probability_center", 4.8))
    steepness = float(config.get("probability_steepness", 0.9))
    avg_state = center + (z / steepness)
    baseline_avg = sum(BASELINE_STATE[k] * STATE_WEIGHTS[k] for k in BASELINE_STATE) / sum(STATE_WEIGHTS.values())
    return clamp(avg_state / baseline_avg, 0.35, 2.1)


def synth_state_for_probability(probability: float, current_state: dict, config: dict) -> dict:
    current = {k: float(current_state.get(k, BASELINE_STATE[k])) for k in BASELINE_STATE}
    curr_avg = sum(current[k] * STATE_WEIGHTS[k] for k in current) / sum(STATE_WEIGHTS.values())
    target_scale = invert_probability_to_state_scale(probability, config)
    target_avg = (sum(BASELINE_STATE[k] * STATE_WEIGHTS[k] for k in BASELINE_STATE) / sum(STATE_WEIGHTS.values())) * target_scale
    delta = target_avg - curr_avg
    out = {}
    for key in current:
        out[key] = clamp(current[key] + delta, 0, 10)
    return out


def build_entries(days: int, floor: float, ceiling: float, anchors: list[Anchor], bands: list[VolatilityBand]) -> list[dict]:
    end = anchors[-1].date
    start = end - timedelta(days=days - 1)
    rows = []
    for i in range(days):
        day = start + timedelta(days=i)
        prob = interpolate_probability(day, anchors) + volatility_adjustment(day, bands)
        rows.append({"ts": day.strftime("%Y-%m-%d 00:00:00 UTC"), "probability": round(clamp(prob, floor, ceiling), 2)})
    return rows


def save_history(entries: list[dict]) -> None:
    payload = {"entries": entries, "data": [{"t": r["ts"], "p": r["probability"]} for r in entries]}
    with HISTORY_FILE.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)


def save_diagnostics(entries: list[dict], current_state: dict, config: dict) -> None:
    rows = []
    for row in entries:
        rows.append(
            {
                "ts": row["ts"],
                "probability": row["probability"],
                "uncertainty": 18.0,
                "state": synth_state_for_probability(row["probability"], current_state, config),
                "drop_reasons": {
                    "missing_title": 0,
                    "no_actor": 0,
                    "no_signal": 0,
                    "invalid_pair": 0,
                    "low_confidence": 0,
                    "classifier_error": 0,
                },
                "event_count": 0,
                "classified_count": 0,
            }
        )
    with DIAGNOSTICS_FILE.open("w", encoding="utf-8") as f:
        json.dump(rows[-400:], f, indent=2)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--policy", default=str(DEFAULT_POLICY_FILE))
    args = parser.parse_args()

    with RISK_FILE.open("r", encoding="utf-8") as f:
        risk = json.load(f)

    config = load_config()
    current_probability = float(risk.get("probability", 12.0))
    current_state = risk.get("state", BASELINE_STATE)

    policy_path = Path(args.policy)
    policy = load_policy(policy_path, current_probability)
    days = int(policy.get("days", 365))
    floor = float(policy.get("floor", 2.0))
    ceiling = float(policy.get("ceiling", 35.0))
    end_date = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

    anchors = build_anchors(policy, floor, ceiling, end_date, current_probability)
    bands = build_bands(policy)
    entries = build_entries(days, floor, ceiling, anchors, bands)

    save_history(entries)
    save_diagnostics(entries, current_state, config)

    print(f"Policy: {policy_path}")
    print(f"Anchors: {len(anchors)} | Volatility bands: {len(bands)}")
    print(f"Wrote {len(entries)} history points to {HISTORY_FILE.name}")
    print(f"Wrote {min(len(entries), 400)} diagnostics points to {DIAGNOSTICS_FILE.name}")


if __name__ == "__main__":
    main()
