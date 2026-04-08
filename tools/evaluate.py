"""Simple backtest/evaluation runner for headline classifier quality."""

import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from events import classify_event

DATASET_FILE = ROOT / "data" / "eval_events.json"
OUTPUT_FILE = ROOT / "evaluation_report.json"


def direction_from_impact(impact):
    if impact > 0.05:
        return "up"
    if impact < -0.05:
        return "down"
    return "down_or_flat"


def run_evaluation():
    with open(DATASET_FILE, "r", encoding="utf-8") as file_obj:
        dataset = json.load(file_obj)

    total = len(dataset)
    pair_match = 0
    direction_match = 0
    dropped = 0
    rows = []

    for row in dataset:
        pred = classify_event(row)
        if not pred.get("ok"):
            dropped += 1
            rows.append({"title": row["title"], "ok": False, "reason": pred.get("reason")})
            continue

        pair_ok = pred.get("state_key") == row.get("expected_state_key")
        dir_ok = direction_from_impact(pred.get("impact", 0)) == row.get("expected_direction")

        pair_match += 1 if pair_ok else 0
        direction_match += 1 if dir_ok else 0

        rows.append(
            {
                "title": row["title"],
                "ok": True,
                "pred_state_key": pred.get("state_key"),
                "expected_state_key": row.get("expected_state_key"),
                "pred_direction": direction_from_impact(pred.get("impact", 0)),
                "expected_direction": row.get("expected_direction"),
                "pair_ok": pair_ok,
                "direction_ok": dir_ok,
            }
        )

    report = {
        "total": total,
        "dropped": dropped,
        "pair_accuracy": round(pair_match / total, 3) if total else 0,
        "direction_accuracy": round(direction_match / total, 3) if total else 0,
        "rows": rows,
    }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as file_obj:
        json.dump(report, file_obj, indent=2)

    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    run_evaluation()
